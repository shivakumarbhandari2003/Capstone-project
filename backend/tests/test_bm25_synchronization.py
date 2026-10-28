"""
Focused regression test suite for BM25 synchronization, updates, failed ingestion resilience, and concurrent retrieval.

Verifies:
1. Indexing: Basic build, exact keyword matching, plan-level authorization filtering, scoring, and ranking.
2. Document updates: Newly ingested or updated chunks become searchable immediately without restarting backend.
3. Failed ingestion resilience: Ingestion or rebuild errors preserve the existing index without data corruption or clearing to None.
4. Concurrent retrieval: Multiple simultaneous search threads running while an update/sync occurs execute safely without race conditions.
"""
import time
import threading
import pytest
from unittest.mock import MagicMock
from backend.app.services.bm25_service import BM25SearchService, simple_tokenize
from backend.app.services.chroma_service import ChromaStorageService

@pytest.fixture(scope="module")
def chroma_svc():
    return ChromaStorageService()

@pytest.fixture(scope="module")
def bm25_svc(chroma_svc):
    return BM25SearchService(chroma_svc)

# ==============================================================================
# 1. INDEXING & BASIC SEARCH TESTS
# ==============================================================================

def test_bm25_indexing_basic(bm25_svc):
    """Verify that BM25 indexes documents from storage and reports healthy status."""
    status = bm25_svc.get_status()
    assert status["is_indexed"] is True
    assert status["total_indexed_chunks"] > 0
    assert status["last_built"] is not None
    assert status["is_stale"] is False

def test_bm25_indexing_tokenization():
    """Verify simple_tokenize handles punctuation, case-folding, and tokens."""
    tokens = simple_tokenize("Emergency ICU Benefit: Up to ₹10,000/day (100% covered).")
    assert "emergency" in tokens
    assert "icu" in tokens
    assert "benefit" in tokens
    assert "10" in tokens or "10000" in tokens or "000" in tokens

def test_bm25_search_authorized_plan_filtering(bm25_svc):
    """Verify that BM25 search strictly filters results by authorized plan scope."""
    results_basic = bm25_svc.search("hospital cash daily benefit", ["HS-BASIC-001"], top_k=5)
    for r in results_basic:
        assert r["plan_id"] == "HS-BASIC-001"
        assert "bm25_rank" in r
        assert r["score"] > 0.0

    results_gold = bm25_svc.search("hospital cash daily benefit", ["HS-GOLD-001"], top_k=5)
    for r in results_gold:
        assert r["plan_id"] == "HS-GOLD-001"

    # Search with disjoint plan ID returns 0 matches for non-existent plan
    results_none = bm25_svc.search("hospital cash daily benefit", ["NON_EXISTENT_PLAN_XYZ"], top_k=5)
    assert len(results_none) == 0

# ==============================================================================
# 2. DOCUMENT UPDATES & AUTOMATIC SYNCHRONIZATION
# ==============================================================================

def test_bm25_sync_on_new_document_ingestion(chroma_svc, bm25_svc):
    """Verify that newly ingested chunks become searchable immediately without backend restart."""
    test_chunk_id = f"TEST_SYNC_NEW_{int(time.time()*1000)}"
    unique_keyword = f"pneumonoultramicroscopicsilicovolcanoconiosis_{int(time.time())}"
    
    # 1. Verify keyword does not exist initially
    initial_res = bm25_svc.search(unique_keyword, ["HS-BASIC-001"])
    assert len(initial_res) == 0

    try:
        # 2. Ingest new chunk and record mutation
        chroma_svc.collection.upsert(
            ids=[test_chunk_id],
            documents=[f"Coverage benefit for rare respiratory illness: {unique_keyword}."],
            embeddings=[[0.05] * 384],
            metadatas=[{"plan_id": "HS-BASIC-001", "section_number": "88", "section_title": "SPECIAL RESPIRATORY"}]
        )
        chroma_svc.record_mutation()

        # 3. Verify BM25 immediately identifies index is stale
        assert bm25_svc.is_stale() is True

        # 4. Search should auto-sync and retrieve the new document without restart
        synced_res = bm25_svc.search(unique_keyword, ["HS-BASIC-001"])
        assert len(synced_res) > 0
        assert synced_res[0]["chunk_id"] == test_chunk_id
        assert test_chunk_id in [r["chunk_id"] for r in synced_res]

    finally:
        # Clean up test chunk from storage
        chroma_svc.collection.delete(ids=[test_chunk_id])
        chroma_svc.record_mutation()
        bm25_svc.sync(force=True)

def test_bm25_sync_on_document_content_update(chroma_svc, bm25_svc):
    """Verify that updating an existing document chunk's content immediately updates search results."""
    test_chunk_id = f"TEST_SYNC_UPDATE_{int(time.time()*1000)}"
    v1_keyword = f"telemedicine_robotics_alpha_{int(time.time())}"
    v2_keyword = f"quantum_cryo_surgery_beta_{int(time.time())}"

    try:
        # 1. Insert Version 1
        chroma_svc.collection.upsert(
            ids=[test_chunk_id],
            documents=[f"Section terms for {v1_keyword} coverage."],
            embeddings=[[0.05] * 384],
            metadatas=[{"plan_id": "HS-GOLD-001", "section_number": "77", "section_title": "ADVANCED CARE"}]
        )
        chroma_svc.record_mutation()

        res1 = bm25_svc.search(v1_keyword, ["HS-GOLD-001"])
        assert len(res1) > 0
        assert res1[0]["chunk_id"] == test_chunk_id

        # 2. Update to Version 2 (replace content)
        chroma_svc.collection.upsert(
            ids=[test_chunk_id],
            documents=[f"Section terms updated for {v2_keyword} coverage."],
            embeddings=[[0.05] * 384],
            metadatas=[{"plan_id": "HS-GOLD-001", "section_number": "77", "section_title": "ADVANCED CARE"}]
        )
        chroma_svc.record_mutation()

        # 3. Old keyword should no longer match, new keyword must match
        res_old = bm25_svc.search(v1_keyword, ["HS-GOLD-001"])
        res_new = bm25_svc.search(v2_keyword, ["HS-GOLD-001"])
        assert len(res_old) == 0
        assert len(res_new) > 0
        assert res_new[0]["chunk_id"] == test_chunk_id

    finally:
        chroma_svc.collection.delete(ids=[test_chunk_id])
        chroma_svc.record_mutation()
        bm25_svc.sync(force=True)

# ==============================================================================
# 3. FAILED INGESTION & RESILIENCE TESTS
# ==============================================================================

def test_bm25_resilience_on_failed_rebuild(bm25_svc):
    """Verify that if a storage/network error occurs during index rebuild, existing index is NOT destroyed."""
    initial_count = len(bm25_svc.chunk_ids)
    assert initial_count > 0
    assert bm25_svc.bm25 is not None

    # Mock collection.get to raise a simulated network/storage failure
    mock_coll = MagicMock()
    mock_coll.get.side_effect = ConnectionError("Chroma Cloud connection timed out during staged sync")
    original_coll = bm25_svc.chroma_service.collection

    try:
        bm25_svc.chroma_service.collection = mock_coll

        # Attempt to build index with failed connection
        res_count = bm25_svc.build_index()

        # Index count should remain equal to previous count, and self.bm25 must NOT be None
        assert res_count == initial_count
        assert bm25_svc.bm25 is not None
        assert len(bm25_svc.chunk_ids) == initial_count

        # Search should continue to function normally with the preserved index
        results = bm25_svc.search("waiting period", ["HS-BASIC-001"], top_k=3)
        assert len(results) > 0

    finally:
        bm25_svc.chroma_service.collection = original_coll

# ==============================================================================
# 4. CONCURRENT RETRIEVAL & THREAD SAFETY TESTS
# ==============================================================================

def test_bm25_concurrent_retrieval_during_sync(bm25_svc):
    """
    Verify thread safety when multiple worker threads execute search queries
    concurrently while background index synchronization is occurring.
    """
    errors = []
    completed_searches = []
    num_threads = 8
    searches_per_thread = 15

    # Use in-memory mock collection for high-frequency concurrent rebuilds
    sample_data = {
        "ids": list(bm25_svc.chunk_ids),
        "documents": list(bm25_svc.documents),
        "metadatas": list(bm25_svc.metadatas)
    }
    mock_coll = MagicMock()
    mock_coll.get.return_value = sample_data
    original_coll = bm25_svc.chroma_service.collection

    try:
        bm25_svc.chroma_service.collection = mock_coll

        def reader_worker(worker_id: int):
            queries = ["hospital cash", "icu benefit", "waiting period", "surgery", "premium"]
            try:
                for i in range(searches_per_thread):
                    q = queries[i % len(queries)]
                    res = bm25_svc.search(q, ["HS-BASIC-001", "HS-GOLD-001"], top_k=3)
                    assert isinstance(res, list)
                    for item in res:
                        assert "chunk_id" in item
                        assert "score" in item
                        assert item["score"] > 0.0
                    completed_searches.append(1)
                    time.sleep(0.002)
            except Exception as e:
                errors.append(f"Worker {worker_id} failed: {e}")

        def writer_worker():
            try:
                for _ in range(10):
                    bm25_svc.build_index()
                    time.sleep(0.005)
            except Exception as e:
                errors.append(f"Writer failed: {e}")

        threads = [threading.Thread(target=reader_worker, args=(i,)) for i in range(num_threads)]
        writer = threading.Thread(target=writer_worker)

        # Launch readers and writer simultaneously
        for t in threads:
            t.start()
        writer.start()

        for t in threads:
            t.join(timeout=10.0)
        writer.join(timeout=10.0)

        # Verify zero errors occurred during concurrent read/write
        assert len(errors) == 0, f"Concurrent retrieval errors: {errors}"
        assert len(completed_searches) == num_threads * searches_per_thread

    finally:
        bm25_svc.chroma_service.collection = original_coll
