import json
import math
from typing import Optional
from backend.app.services.chroma_service import ChromaStorageService
from backend.app.services.embedding_service import LocalEmbeddingService
from backend.app.services.bm25_service import BM25SearchService
from backend.app.services.auth_service import AuthorizationService
from backend.app.core.config import settings
from backend.app.core.logging_config import logger

RRF_K_DEFAULT = 60

class HybridRetrievalService:
    """
    Modular Hybrid Retrieval Engine combining:
    1. Dense Semantic Vector Search (BGE-Small 384 via ChromaDB)
    2. BM25 Lexical Search (Rank-BM25)
    3. Reciprocal Rank Fusion (RRF)
    4. Durable Parent Section Expansion (parent_store.json)
    5. Strict multi-layer Role Authorization
    """

    def __init__(
        self,
        chroma_service: Optional[ChromaStorageService] = None,
        embedding_service: Optional[LocalEmbeddingService] = None,
        bm25_service: Optional[BM25SearchService] = None
    ):
        self.chroma_service = chroma_service or ChromaStorageService()
        self.embedding_service = embedding_service or LocalEmbeddingService()
        self.bm25_service = bm25_service or BM25SearchService(self.chroma_service)
        self._parent_store_mtime: float = 0.0
        self.parent_store_data: dict[str, dict] = self._load_parent_store()

    def _load_parent_store(self) -> dict[str, dict]:
        if settings.PARENT_STORE_PATH.exists():
            try:
                st = settings.PARENT_STORE_PATH.stat()
                self._parent_store_mtime = st.st_mtime
                with open(settings.PARENT_STORE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} parent records into in-memory cache.")
                    return data
            except Exception as e:
                logger.error(f"Failed to load parent store from {settings.PARENT_STORE_PATH}: {e}")
        return {}

    def get_parent_store(self) -> dict[str, dict]:
        """Returns in-memory cached parent store, auto-refreshing if file on disk was modified."""
        if settings.PARENT_STORE_PATH.exists():
            try:
                current_mtime = settings.PARENT_STORE_PATH.stat().st_mtime
                if current_mtime > self._parent_store_mtime or not self.parent_store_data:
                    self.parent_store_data = self._load_parent_store()
            except Exception:
                pass
        return self.parent_store_data

    def refresh_indexes(self) -> None:
        """Explicitly reloads parent store and rebuilds the BM25 lexical index (e.g. post-ingestion)."""
        logger.info("Refreshing HybridRetrievalService parent store and BM25 index...")
        self.parent_store_data = self._load_parent_store()
        self.bm25_service.build_index()

    def retrieve(
        self,
        query: str,
        role: str,
        effective_scope: list[str],
        top_k: int = 5,
        rrf_k: int = RRF_K_DEFAULT
    ) -> dict:
        """
        Execute full authorized hybrid retrieval pipeline.
        Returns:
            {
                "chunks": [...],
                "parents": [...],
                "effective_scope": [...],
                "formatted_context": str,
                "contains_unverified": bool,
                "diagnostics": {...}
            }
        """
        # Step 1: Intersect effective_scope with role authorization
        authorized_scope = AuthorizationService.filter_authorized_plans(role, effective_scope)
        if not authorized_scope:
            logger.warning(f"No authorized plans in effective scope {effective_scope} for role {role}")
            return {
                "chunks": [],
                "parents": [],
                "effective_scope": [],
                "formatted_context": "No authorized policy documents available for this request.",
                "contains_unverified": False,
                "diagnostics": {"error": "Scope not authorized"}
            }

        # Step 2: Dense Retrieval
        dense_results = self._dense_search(query, authorized_scope, top_k=top_k * 2)

        # Step 3: BM25 Lexical Retrieval
        bm25_results = self.bm25_service.search(query, authorized_scope, top_k=top_k * 2)

        # Step 4: Reciprocal Rank Fusion (RRF) with targeted benefit alignment
        fused_chunks = self._reciprocal_rank_fusion(dense_results, bm25_results, query=query, rrf_k=rrf_k, top_k=top_k)

        # Step 5: Post-fusion Security Filter
        sanitized_chunks = AuthorizationService.sanitize_retrieved_chunks(role, fused_chunks)

        # Step 6: Parent Section Expansion
        expanded_parents, contains_unverified = self._expand_parents(sanitized_chunks, authorized_scope)

        # Step 7: Bounded Context Construction
        formatted_context = self._build_context(sanitized_chunks, expanded_parents)

        return {
            "chunks": sanitized_chunks,
            "parents": expanded_parents,
            "effective_scope": authorized_scope,
            "formatted_context": formatted_context,
            "contains_unverified": contains_unverified,
            "diagnostics": {
                "dense_count": len(dense_results),
                "bm25_count": len(bm25_results),
                "fused_count": len(sanitized_chunks),
                "parents_expanded": len(expanded_parents),
                "rrf_k": rrf_k
            }
        }

    def _dense_search(self, query: str, authorized_plans: list[str], top_k: int) -> list[dict]:
        """Generate query vector and search ChromaDB with plan scope filter."""
        # Generate and validate query embedding
        query_vector = self.embedding_service.generate_embeddings([query])[0]
        if len(query_vector) != settings.EMBEDDING_DIMENSION or not all(math.isfinite(v) for v in query_vector):
            raise ValueError(f"Invalid query embedding generated. Expected finite {settings.EMBEDDING_DIMENSION}-dim vector.")

        # Construct ChromaDB where clause
        if len(authorized_plans) == 1:
            where_filter = {"plan_id": authorized_plans[0]}
        else:
            where_filter = {"plan_id": {"$in": authorized_plans}}

        try:
            results = self.chroma_service.collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            logger.error(f"ChromaDB query error with filter {where_filter}: {e}")
            return []

        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        dense_list = []
        for rank, (cid, doc, meta, dist) in enumerate(zip(ids, docs, metas, dists), start=1):
            dense_list.append({
                "chunk_id": cid,
                "content": doc,
                "metadata": meta,
                "plan_id": meta.get("plan_id", ""),
                "dense_rank": rank,
                "dense_distance": float(dist)
            })
        return dense_list

    def _reciprocal_rank_fusion(
        self,
        dense_results: list[dict],
        bm25_results: list[dict],
        query: str = "",
        rrf_k: int = RRF_K_DEFAULT,
        top_k: int = 5
    ) -> list[dict]:
        """
        Calculates RRF score: score = sum(1 / (k + rank)) across available systems.
        Preserves original ranks and applies deterministic tie-breaking.
        Applies plan-scoped benefit section alignment boost when query explicitly names a benefit.
        """
        candidates: dict[str, dict] = {}

        for item in dense_results:
            cid = item["chunk_id"]
            candidates[cid] = {
                "chunk_id": cid,
                "content": item["content"],
                "metadata": item["metadata"],
                "plan_id": item["plan_id"],
                "dense_rank": item["dense_rank"],
                "dense_distance": item.get("dense_distance"),
                "bm25_rank": None,
                "rrf_score": 1.0 / (rrf_k + item["dense_rank"])
            }

        for item in bm25_results:
            cid = item["chunk_id"]
            if cid in candidates:
                candidates[cid]["bm25_rank"] = item["bm25_rank"]
                candidates[cid]["rrf_score"] += 1.0 / (rrf_k + item["bm25_rank"])
            else:
                candidates[cid] = {
                    "chunk_id": cid,
                    "content": item["content"],
                    "metadata": item["metadata"],
                    "plan_id": item["plan_id"],
                    "dense_rank": None,
                    "dense_distance": None,
                    "bm25_rank": item["bm25_rank"],
                    "rrf_score": 1.0 / (rrf_k + item["bm25_rank"])
                }

        # Benefit-specific section alignment boost
        if query:
            q_lower = query.lower()
            benefit_title_keywords = [
                ("other surgery", ["other surgery"]),
                ("hospital cash", ["hospital cash"]),
                ("icu", ["icu", "intensive care"]),
                ("day-care", ["day-care", "day care"]),
                ("day care", ["day-care", "day care"]),
                ("cataract", ["day-care", "day care"]),
                ("medical management", ["medical management"]),
                ("extended stay", ["extended hospital stay", "extended stay"]),
                ("health check", ["health check", "check-up", "checkup"]),
                ("restor", ["restored cover", "restoration", "additional benefits"]),
                ("quick cash", ["quick cash", "additional benefits"]),
                ("annual premium", ["premium and payment", "premium details"]),
                ("renewal premium", ["premium and payment", "premium details"]),
            ]
            for cand in candidates.values():
                sec_title = (cand.get("metadata", {}).get("section_title") or "").lower()
                for q_term, title_terms in benefit_title_keywords:
                    if q_term in q_lower and any(tt in sec_title for tt in title_terms):
                        cand["rrf_score"] += 0.05
                        break

                # Penalize unrelated claim-free table when claim-free or increase is not in query
                if "claim-free" in sec_title and not any(w in q_lower for w in ["claim-free", "claim free", "bonus", "increase", "no claim"]):
                    cand["rrf_score"] -= 0.03

        # Deterministic sorting: RRF score descending, then dense rank ascending, then chunk_id string
        sorted_candidates = sorted(
            candidates.values(),
            key=lambda x: (
                -x["rrf_score"],
                x["dense_rank"] if x["dense_rank"] is not None else 9999,
                x["chunk_id"]
            )
        )

        # Deduplicate identical chunk content and filter poor semantic matches
        deduped: list[dict] = []
        seen_texts = set()
        for cand in sorted_candidates:
            # Semantic noise filter: If candidate has no lexical BM25 match and high cosine distance (> 0.68), it is irrelevant noise
            if cand.get("bm25_rank") is None and cand.get("dense_distance") is not None and cand["dense_distance"] > 0.68:
                continue

            clean_body = " ".join(cand.get("content", "").split())
            if clean_body in seen_texts:
                continue
            seen_texts.add(clean_body)
            deduped.append(cand)
            if len(deduped) == top_k:
                break

        return deduped

    def _expand_parents(self, chunks: list[dict], authorized_scope: list[str]) -> tuple[list[dict], bool]:
        """
        Expands candidate chunks to their parent section records from parent_store.json.
        Verifies plan authorization for parents and detects illustrative status.
        """
        parents_map = {}
        contains_unverified = False
        authorized_set = set(authorized_scope)
        parent_store = self.get_parent_store()

        for c in chunks:
            meta = c.get("metadata", {})
            if meta.get("data_status") == "illustrative_unverified":
                contains_unverified = True

            parent_id = meta.get("parent_section_id")
            if not parent_id or parent_id in parents_map:
                continue

            if parent_id in parent_store:
                p_record = parent_store[parent_id]
                # Enforce that parent plan matches authorized scope
                if p_record.get("plan_id") in authorized_set:
                    parents_map[parent_id] = p_record

        return list(parents_map.values()), contains_unverified

    def _build_context(self, chunks: list[dict], parents: list[dict]) -> str:
        """Assembles structured, bounded, source-attributed context string without duplicate tables."""
        if not chunks:
            return "No matching policy evidence found."

        context_blocks = []
        seen_blocks = set()

        for idx, chunk in enumerate(chunks, start=1):
            meta = chunk.get("metadata", {})
            plan_name = meta.get("plan_name", meta.get("plan_id", "Policy"))
            sec_num = meta.get("section_number", "")
            sec_title = meta.get("section_title", "")
            p_start = meta.get("source_page_start", "")
            p_end = meta.get("source_page_end", "")
            status = meta.get("data_status", "verified")
            content = chunk.get("content", "").strip()

            clean_content = " ".join(content.split())
            if clean_content in seen_blocks:
                continue
            seen_blocks.add(clean_content)

            status_label = " [ILLUSTRATIVE / UNVERIFIED]" if status == "illustrative_unverified" else ""
            header = f"### [Source {idx}] Plan: {plan_name} | Section {sec_num}: {sec_title} (Pages {p_start}-{p_end}){status_label}"
            context_blocks.append(f"{header}\n{content}\n")

        # Provide document structure summary if parents exist, without reproducing raw tables
        if parents:
            structure_lines = ["--- Document Structure Reference ---"]
            for p in parents[:3]:
                sec_no = p.get("section_number", "")
                sec_title = p.get("section_title", "")
                pid = p.get("plan_id", "")
                structure_lines.append(f"- Section {sec_no}: {sec_title} (Plan: {pid})")
            context_blocks.append("\n".join(structure_lines))

        return "\n\n".join(context_blocks)
