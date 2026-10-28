import re
import time
import threading
from typing import Optional
from rank_bm25 import BM25Okapi
from backend.app.services.chroma_service import ChromaStorageService
from backend.app.core.config import settings
from backend.app.core.logging_config import logger

def simple_tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric tokens for BM25 matching."""
    return re.findall(r"\b[a-zA-Z0-9_\-\.\%]+\b", text.lower())

class BM25SearchService:
    """
    In-memory BM25 lexical search engine over persisted ChromaDB chunks.
    Filters candidate matches strictly by authorized plan IDs before ranking.
    Maintains thread-safe atomic snapshots and automatic synchronization with storage mutations.
    """

    def __init__(self, chroma_service: Optional[ChromaStorageService] = None):
        self.chroma_service = chroma_service or ChromaStorageService()
        self._build_lock = threading.RLock()
        self._swap_lock = threading.RLock()
        self.bm25: Optional[BM25Okapi] = None
        self.chunk_ids: list[str] = []
        self.documents: list[str] = []
        self.metadatas: list[dict] = []
        self.plan_ids: list[str] = []
        self.last_built_timestamp: Optional[str] = None
        self._synced_mutation_version: int = -1
        self._parent_store_mtime: float = 0.0
        self._last_count_check: float = 0.0
        self._known_collection_count: int = -1
        self.build_index()

    def is_stale(self) -> bool:
        """
        Determines if the in-memory BM25 index is out of sync with storage.
        Checks in-process mutation counter and parent store modification time.
        Avoids remote HTTP network calls during search.
        """
        with self._swap_lock:
            if self.bm25 is None or not self.chunk_ids:
                return True

        # Check 1: In-process mutation version from ChromaStorageService
        curr_mutation_version = self.chroma_service.get_mutation_version()
        if curr_mutation_version != self._synced_mutation_version:
            return True

        # Check 2: Parent store JSON modification on disk (external ingestion / worker sync)
        if settings.PARENT_STORE_PATH.exists():
            try:
                mtime = settings.PARENT_STORE_PATH.stat().st_mtime
                if mtime > self._parent_store_mtime:
                    return True
            except Exception:
                pass

        return False

    def sync(self, force: bool = False) -> int:
        """Explicit synchronization hook to refresh the BM25 index if stale or forced."""
        if force or self.is_stale():
            return self.build_index()
        with self._swap_lock:
            return len(self.chunk_ids)

    def build_index(self) -> int:
        """Fetch all chunks from ChromaDB and build the BM25 index safely and atomically."""
        logger.info("Building BM25 index from ChromaDB storage...")
        with self._build_lock:
            try:
                results = self.chroma_service.collection.get(include=["documents", "metadatas"])
                new_chunk_ids = results.get("ids", [])
                new_documents = results.get("documents", [])
                new_metadatas = results.get("metadatas", [])
                new_plan_ids = [m.get("plan_id", "") for m in new_metadatas]

                tokenized_corpus = [simple_tokenize(doc) for doc in new_documents]
                if tokenized_corpus:
                    new_bm25 = BM25Okapi(tokenized_corpus)
                    new_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                else:
                    new_bm25 = None
                    new_ts = None
                    logger.warning("BM25 index is empty; 0 documents retrieved from ChromaDB.")

                parent_mtime = 0.0
                if settings.PARENT_STORE_PATH.exists():
                    try:
                        parent_mtime = settings.PARENT_STORE_PATH.stat().st_mtime
                    except Exception:
                        pass

                # Thread-safe atomic pointer swap
                with self._swap_lock:
                    self.chunk_ids = new_chunk_ids
                    self.documents = new_documents
                    self.metadatas = new_metadatas
                    self.plan_ids = new_plan_ids
                    self.bm25 = new_bm25
                    self.last_built_timestamp = new_ts
                    self._synced_mutation_version = self.chroma_service.get_mutation_version()
                    self._parent_store_mtime = parent_mtime
                    self._last_count_check = time.time()
                    self._known_collection_count = len(new_chunk_ids)

                if new_bm25 is not None:
                    logger.info(f"BM25 index built successfully with {len(new_chunk_ids)} documents.")
                return len(new_chunk_ids)

            except Exception as e:
                logger.error(f"Failed to build BM25 index: {e}")
                # Resilience: If index already exists, do not clear it on transient error!
                with self._swap_lock:
                    if self.bm25 is not None:
                        logger.warning("Preserving existing BM25 index despite rebuild error.")
                        return len(self.chunk_ids)
                    self.bm25 = None
                return 0

    def search(
        self,
        query: str,
        authorized_plan_ids: list[str],
        top_k: int = 10
    ) -> list[dict]:
        """
        Execute BM25 lexical search against authorized plan scope.
        Automatically detects staleness and synchronizes before query execution.
        Operates on an atomic immutable snapshot for full thread safety during concurrent retrieval.
        """
        if self.is_stale():
            self.build_index()

        with self._swap_lock:
            bm25_inst = self.bm25
            chunk_ids = list(self.chunk_ids)
            documents = list(self.documents)
            metadatas = list(self.metadatas)
            plan_ids = list(self.plan_ids)

        if not bm25_inst or not chunk_ids:
            return []

        tokens = simple_tokenize(query)
        if not tokens:
            return []

        raw_scores = bm25_inst.get_scores(tokens)
        authorized_set = set(authorized_plan_ids)

        scored_candidates = []
        for idx, score in enumerate(raw_scores):
            if score <= 0.0:
                continue
            if idx >= len(plan_ids):
                break
            plan_id = plan_ids[idx]
            if plan_id not in authorized_set:
                continue

            scored_candidates.append({
                "chunk_id": chunk_ids[idx],
                "content": documents[idx],
                "metadata": metadatas[idx],
                "plan_id": plan_id,
                "score": float(score)
            })

        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        top_results = scored_candidates[:top_k]

        for rank, item in enumerate(top_results, start=1):
            item["bm25_rank"] = rank

        return top_results

    def get_status(self) -> dict:
        stale_flag = self.is_stale()
        with self._swap_lock:
            return {
                "total_indexed_chunks": len(self.chunk_ids),
                "is_indexed": self.bm25 is not None,
                "last_built": self.last_built_timestamp,
                "synced_mutation_version": self._synced_mutation_version,
                "is_stale": stale_flag
            }

