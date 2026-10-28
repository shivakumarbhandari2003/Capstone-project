import json
import time
import threading
from pathlib import Path
from typing import Optional, Any
import chromadb
from chromadb.config import Settings as ChromaSettings
from backend.app.models.chunk import ValidatedChunk, ParentChunk
from backend.app.core.config import settings
from backend.app.core.logging_config import logger

class ChromaStorageService:
    """
    Manages ChromaDB storage (Chroma Cloud, Remote HTTP, or Local Persistent).
    Implements staged two-phase safe replacement and hash deduplication.
    """
    _shared_client: Any = None
    _shared_collections: dict = {}
    _lock = threading.Lock()
    _mutation_version: int = 0
    _last_mutation_timestamp: float = 0.0

    @classmethod
    def record_mutation(cls) -> int:
        """Records a storage mutation (ingest, update, delete) to track index staleness."""
        with cls._lock:
            cls._mutation_version += 1
            cls._last_mutation_timestamp = time.time()
            return cls._mutation_version

    @classmethod
    def get_mutation_version(cls) -> int:
        """Returns the current mutation version of ChromaDB storage."""
        return cls._mutation_version

    def __init__(self, persist_path: Optional[Path] = None):
        self.collection_name = settings.CHROMA_COLLECTION_NAME
        with self._lock:
            if ChromaStorageService._shared_client is None or persist_path is not None:
                client = self._initialize_client(persist_path)
                if persist_path is None:
                    ChromaStorageService._shared_client = client
                self.client = client
            else:
                self.client = ChromaStorageService._shared_client

            if self.collection_name in ChromaStorageService._shared_collections and persist_path is None:
                self.collection = ChromaStorageService._shared_collections[self.collection_name]
            else:
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"description": "AI Insurance Assistant Knowledge Base"}
                )
                if persist_path is None:
                    ChromaStorageService._shared_collections[self.collection_name] = self.collection
                logger.info(f"Initialized ChromaDB collection '{self.collection_name}'. Current count: {self.collection.count()}")

    def _initialize_client(self, persist_path: Optional[Path] = None):
        """
        Dynamically initializes ChromaDB client based on configuration:
        1. CloudClient if CHROMA_API_KEY is provided
        2. HttpClient if CHROMA_SERVER_HOST is provided
        3. PersistentClient local fallback
        """
        if settings.CHROMA_API_KEY:
            logger.info(f"Connecting to Chroma Cloud at {settings.CHROMA_CLOUD_HOST} (Tenant: {settings.CHROMA_TENANT}, DB: {settings.CHROMA_DATABASE})...")
            try:
                return chromadb.CloudClient(
                    api_key=settings.CHROMA_API_KEY,
                    tenant=settings.CHROMA_TENANT,
                    database=settings.CHROMA_DATABASE
                )
            except Exception as e:
                logger.error(f"Failed to connect to Chroma Cloud: {e}. Falling back to local storage.")
        
        if settings.CHROMA_SERVER_HOST:
            logger.info(f"Connecting to remote Chroma HTTP server at {settings.CHROMA_SERVER_HOST}:{settings.CHROMA_SERVER_PORT}...")
            try:
                headers = {}
                if settings.CHROMA_SERVER_AUTH_TOKEN:
                    headers["Authorization"] = f"Bearer {settings.CHROMA_SERVER_AUTH_TOKEN}"
                return chromadb.HttpClient(
                    host=settings.CHROMA_SERVER_HOST,
                    port=settings.CHROMA_SERVER_PORT,
                    ssl=settings.CHROMA_SERVER_SSL,
                    headers=headers if headers else None
                )
            except Exception as e:
                logger.error(f"Failed to connect to remote Chroma HTTP server: {e}. Falling back to local storage.")

        # Local persistent fallback
        local_path = str(persist_path or settings.CHROMA_DB_DIR)
        logger.info(f"Using local ChromaDB client at: {local_path} (Awaiting Chroma Cloud credentials)")
        return chromadb.PersistentClient(
            path=local_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )

    def get_existing_file_hash(self, source_filename: str) -> Optional[str]:
        """Check persistent history store for existing document hash, only if chunks actually exist in ChromaDB."""
        if not settings.HISTORY_STORE_PATH.exists():
            return None
        try:
            # Verify records actually exist in ChromaDB collection
            existing = self.collection.get(
                where={"source_document": source_filename},
                limit=1
            )
            if not existing.get("ids"):
                logger.info(f"No existing chunks found in ChromaDB for '{source_filename}'. Ingestion allowed.")
                return None

            with open(settings.HISTORY_STORE_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
            for record in reversed(history):
                if record.get("source_document") == source_filename and record.get("status") == "SUCCESS":
                    return record.get("content_hash")
        except Exception as e:
            logger.warning(f"Could not verify existing file hash in ChromaDB/history: {e}")
        return None

    def staged_replace_document_chunks(
        self,
        source_filename: str,
        plan_id: str,
        chunks: list[ValidatedChunk],
        parents: list[ParentChunk]
    ) -> dict[str, Any]:
        """
        Two-phase staged replacement:
        1. Query existing IDs for this specific source_document.
        2. Upsert new validated records.
        3. Verify insertion by read-back.
        4. Prune obsolete IDs for this document only.
        5. Persist parent records durably.
        NEVER touches other plans' data.
        """
        logger.info(f"Starting staged replacement for {source_filename} ({len(chunks)} chunks)...")

        existing_results = self.collection.get(
            where={"source_document": source_filename}
        )
        old_ids: list[str] = existing_results.get("ids", [])
        logger.info(f"Found {len(old_ids)} existing chunks for {source_filename} in ChromaDB")

        new_ids = [c.chunk_id for c in chunks]
        new_documents = [c.content for c in chunks]
        new_embeddings = [c.embedding for c in chunks]
        new_metadatas = [c.metadata for c in chunks]

        # Batch upsert
        batch_size = 100
        for i in range(0, len(new_ids), batch_size):
            end_idx = i + batch_size
            self.collection.upsert(
                ids=new_ids[i:end_idx],
                documents=new_documents[i:end_idx],
                embeddings=new_embeddings[i:end_idx],
                metadatas=new_metadatas[i:end_idx]
            )

        # Verification by ID read-back
        verification_sample = self.collection.get(ids=new_ids[:min(10, len(new_ids))])
        if len(verification_sample.get("ids", [])) == 0:
            raise RuntimeError(f"Storage verification failed: Could not read back newly inserted chunks for {source_filename}")

        # Prune obsolete old IDs
        ids_to_delete = [oid for oid in old_ids if oid not in set(new_ids)]
        if ids_to_delete:
            logger.info(f"Pruning {len(ids_to_delete)} obsolete chunk IDs from previous version...")
            self.collection.delete(ids=ids_to_delete)

        # Persist parent records to durable parent store
        self._persist_parent_records(parents)

        # Record storage mutation to notify lexical indexers of fresh data
        self.record_mutation()

        total_in_collection = self.collection.count()
        logger.info(
            f"Staged replacement complete for {source_filename}. "
            f"Inserted: {len(new_ids)}, Pruned: {len(ids_to_delete)}, Total Collection Count: {total_in_collection}"
        )

        return {
            "source_document": source_filename,
            "plan_id": plan_id,
            "inserted_count": len(new_ids),
            "pruned_count": len(ids_to_delete),
            "total_collection_count": total_in_collection,
            "parent_count": len(parents)
        }

    def _persist_parent_records(self, parents: list[ParentChunk]) -> None:
        """Persist full parent section records to local JSON document store."""
        parent_store_data: dict[str, Any] = {}
        if settings.PARENT_STORE_PATH.exists():
            try:
                with open(settings.PARENT_STORE_PATH, "r", encoding="utf-8") as f:
                    parent_store_data = json.load(f)
            except Exception as e:
                logger.warning(f"Error reading existing parent store: {e}")

        for p in parents:
            parent_store_data[p.parent_id] = p.model_dump()

        with open(settings.PARENT_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(parent_store_data, f, indent=2)

    def verify_records_by_ids(self, record_ids: list[str]) -> bool:
        if not record_ids:
            return True
        sample_ids = record_ids[:min(20, len(record_ids))]
        results = self.collection.get(ids=sample_ids)
        return len(results.get("ids", [])) == len(sample_ids)
