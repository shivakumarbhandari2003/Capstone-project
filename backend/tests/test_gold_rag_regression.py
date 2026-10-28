import json
import pytest
from unittest.mock import patch, MagicMock

from backend.app.services.auth_service import UserIdentity
from backend.app.services.scope_resolver import ScopeResolver
from backend.app.services.retrieval_service import HybridRetrievalService, RRF_K_DEFAULT
from backend.app.services.generation_service import AnswerGenerationService
from backend.app.services.rag_orchestrator import RAGOrchestrator
from backend.app.services.conversation_service import ConversationManager
from backend.app.core.prompt import RAG_SYSTEM_PROMPT, format_rag_prompt

# --------------------------------------------------------------------------
# 1. Greeting without unnecessary retrieval
# --------------------------------------------------------------------------
def test_greeting_without_unnecessary_retrieval():
    scope_res = ScopeResolver.resolve_scope(
        query="Hello",
        selected_plan_id="HS-GOLD-001",
        role="customer"
    )
    assert scope_res.is_greeting is True
    assert scope_res.reason == "greeting"
    assert "Health Shield – Gold" in scope_res.greeting_message
    assert scope_res.is_comparison is False

    # Test orchestrator handling
    mock_retrieval = MagicMock()
    mock_gen = MagicMock()
    mock_conv = MagicMock()
    mock_msg = MagicMock()
    mock_msg.model_dump.return_value = {"answer": scope_res.greeting_message}
    mock_conv.add_turn.return_value = mock_msg

    orchestrator = RAGOrchestrator(
        retrieval_service=mock_retrieval,
        generation_service=mock_gen,
        conversation_manager=mock_conv
    )
    mock_session = MagicMock()
    mock_session.selected_plan_id = "HS-GOLD-001"
    mock_session.messages = []
    mock_conv.get_conversation.return_value = mock_session

    user = UserIdentity(user_id="cust1", username="c", email="c@test.com", role="customer")
    result = orchestrator.process_query("conv-123", user, "Hello")

    # Retrieval and LLM generation MUST NOT be called for a greeting
    mock_retrieval.retrieve.assert_not_called()
    mock_gen.generate_answer.assert_not_called()
    assert result["scope_resolution"]["is_greeting"] is True
    assert result["retrieval_diagnostics"] == {"greeting": True}

# --------------------------------------------------------------------------
# 2. Daily Hospital Cash retrieval and answer correctness
# --------------------------------------------------------------------------
def test_daily_hospital_cash_retrieval_and_answer():
    retrieval = HybridRetrievalService()
    res = retrieval.retrieve(
        query="What is the Daily Hospital Cash benefit, and what are its limits?",
        role="customer",
        effective_scope=["HS-GOLD-001"],
        top_k=5
    )
    chunks = res["chunks"]
    assert len(chunks) > 0
    # Must retrieve Section 3
    sec_numbers = [str(c.get("metadata", {}).get("section_number")) for c in chunks]
    assert "3" in sec_numbers

    # Verify content contains key facts
    all_content = "\n".join([c.get("content", "") for c in chunks])
    assert "5,000" in all_content or "5000" in all_content
    assert "24 hours" in all_content
    assert "20 days" in all_content

# --------------------------------------------------------------------------
# 3. ICU benefit and undefined annual limit
# --------------------------------------------------------------------------
def test_icu_benefit_retrieval():
    retrieval = HybridRetrievalService()
    res = retrieval.retrieve(
        query="What is the ICU limit per day and per year?",
        role="customer",
        effective_scope=["HS-GOLD-001"],
        top_k=5
    )
    chunks = res["chunks"]
    sec_numbers = [str(c.get("metadata", {}).get("section_number")) for c in chunks]
    assert "4" in sec_numbers

    all_content = "\n".join([c.get("content", "") for c in chunks])
    assert "Not defined" in all_content or "not defined" in all_content or "not officially defined" in all_content.lower()

# --------------------------------------------------------------------------
# 4. Major Surgery Category 2 calculation
# --------------------------------------------------------------------------
def test_major_surgery_category_2_retrieval():
    retrieval = HybridRetrievalService()
    res = retrieval.retrieve(
        query="What is the payout for Major Surgery Category 2?",
        role="customer",
        effective_scope=["HS-GOLD-001"],
        top_k=5
    )
    chunks = res["chunks"]
    sec_numbers = [str(c.get("metadata", {}).get("section_number")) for c in chunks]
    assert "5" in sec_numbers

    all_content = "\n".join([c.get("content", "") for c in chunks])
    assert "5,00,000" in all_content or "500000" in all_content
    assert "60%" in all_content
    assert "3,00,000" in all_content or "300000" in all_content

# --------------------------------------------------------------------------
# 5. Waiting-period uncertainty
# --------------------------------------------------------------------------
def test_waiting_period_retrieval():
    retrieval = HybridRetrievalService()
    res = retrieval.retrieve(
        query="What are the waiting periods for pre-existing conditions?",
        role="customer",
        effective_scope=["HS-GOLD-001"],
        top_k=5
    )
    chunks = res["chunks"]
    sec_numbers = [str(c.get("metadata", {}).get("section_number")) for c in chunks]
    assert "15" in sec_numbers

# --------------------------------------------------------------------------
# 6. Dense retrieval and BM25 provenance
# --------------------------------------------------------------------------
def test_dense_and_bm25_provenance():
    retrieval = HybridRetrievalService()
    dense_res = retrieval._dense_search("Hospital Cash", ["HS-GOLD-001"], top_k=5)
    for d in dense_res:
        assert "chunk_id" in d
        assert "dense_rank" in d
        assert "dense_distance" in d
        assert d["plan_id"] == "HS-GOLD-001"

    bm25_res = retrieval.bm25_service.search("Hospital Cash", ["HS-GOLD-001"], top_k=5)
    for b in bm25_res:
        assert "chunk_id" in b
        assert "bm25_rank" in b
        assert b["plan_id"] == "HS-GOLD-001"

# --------------------------------------------------------------------------
# 7. RRF ranking and deduplication
# --------------------------------------------------------------------------
def test_rrf_ranking_and_deduplication():
    retrieval = HybridRetrievalService()
    dense_mock = [
        {"chunk_id": "C1", "content": "Same content table", "metadata": {}, "plan_id": "P1", "dense_rank": 1},
        {"chunk_id": "C2", "content": "Same content table", "metadata": {}, "plan_id": "P1", "dense_rank": 2},
        {"chunk_id": "C3", "content": "Different unique content", "metadata": {}, "plan_id": "P1", "dense_rank": 3}
    ]
    bm25_mock = [
        {"chunk_id": "C1", "content": "Same content table", "metadata": {}, "plan_id": "P1", "bm25_rank": 1},
        {"chunk_id": "C3", "content": "Different unique content", "metadata": {}, "plan_id": "P1", "bm25_rank": 2}
    ]

    fused = retrieval._reciprocal_rank_fusion(dense_mock, bm25_mock, rrf_k=RRF_K_DEFAULT, top_k=5)
    # C1 and C2 have identical content; only C1 should be kept
    fused_cids = [f["chunk_id"] for f in fused]
    assert "C1" in fused_cids
    assert "C2" not in fused_cids  # Deduplicated!
    assert "C3" in fused_cids

# --------------------------------------------------------------------------
# 8. Parent expansion correctness
# --------------------------------------------------------------------------
def test_parent_expansion_correctness():
    retrieval = HybridRetrievalService()
    test_chunks = [
        {"metadata": {"parent_section_id": "HS-GOLD-001-SEC-03", "data_status": "illustrative_unverified"}}
    ]
    parents, contains_unverified = retrieval._expand_parents(test_chunks, ["HS-GOLD-001"])
    assert contains_unverified is True
    assert len(parents) == 1
    assert parents[0]["parent_id"] == "HS-GOLD-001-SEC-03"
    assert parents[0]["section_number"] == "3"

# --------------------------------------------------------------------------
# 9. Exact final Gemini evidence context & no duplicate markdown tables
# --------------------------------------------------------------------------
def test_exact_final_gemini_evidence_context():
    retrieval = HybridRetrievalService()
    chunks = [
        {
            "content": "| Col A | Col B |\n| --- | --- |\n| Val 1 | Val 2 |",
            "metadata": {
                "plan_name": "Health Shield – Gold",
                "plan_id": "HS-GOLD-001",
                "section_number": "3",
                "section_title": "HOSPITAL CASH",
                "source_page_start": 2,
                "source_page_end": 3,
                "data_status": "illustrative_unverified"
            }
        }
    ]
    parents = [{"section_number": "3", "section_title": "HOSPITAL CASH", "plan_id": "HS-GOLD-001"}]
    ctx = retrieval._build_context(chunks, parents)
    assert "### [Source 1] Plan: Health Shield – Gold" in ctx
    assert "[ILLUSTRATIVE / UNVERIFIED]" in ctx
    assert "--- Document Structure Reference ---" in ctx
    # Ensure raw table is not duplicated twice
    assert ctx.count("| Col A | Col B |") == 1

# --------------------------------------------------------------------------
# 10. Citation correctness
# --------------------------------------------------------------------------
def test_citation_correctness():
    gen_service = AnswerGenerationService()
    chunks = [
        {
            "chunk_id": "CHK-1",
            "content": "Eligible hospital cash of Rs 5,000 per day.",
            "metadata": {
                "plan_id": "HS-GOLD-001",
                "plan_name": "Health Shield – Gold",
                "source_document": "health_shield_gold.pdf",
                "section_number": "3",
                "section_title": "HOSPITAL CASH BENEFIT",
                "source_page_start": 2,
                "source_page_end": 3,
                "data_status": "illustrative_unverified"
            }
        }
    ]
    citations = gen_service._build_verified_citations(chunks)
    assert len(citations) == 1
    c = citations[0]
    assert c.plan_id == "HS-GOLD-001"
    assert c.source_document == "health_shield_gold.pdf"
    assert c.section_number == "3"
    assert c.source_page_start == 2
    assert c.source_page_end == 3

# --------------------------------------------------------------------------
# 11. Gold disclaimer correctness & 12. Employee disclaimer isolation
# --------------------------------------------------------------------------
def test_gold_and_employee_disclaimer_isolation():
    gen_service = AnswerGenerationService()
    # Gold test:
    gold_chunks = [
        {
            "chunk_id": "CHK-G1",
            "content": "Gold benefit content.",
            "metadata": {"plan_id": "HS-GOLD-001", "data_status": "illustrative_unverified"}
        }
    ]
    retrieval_gold = {"chunks": gold_chunks, "contains_unverified": True}
    res_gold = gen_service.generate_answer(
        query="What is the benefit?",
        role="customer",
        selected_plan_id="HS-GOLD-001",
        retrieval_result=retrieval_gold
    )
    assert "Health Shield – Gold" in res_gold.answer_text
    assert "Executive Employee Insurance Plan" not in res_gold.answer_text

    # Employee test:
    emp_chunks = [
        {
            "chunk_id": "CHK-E1",
            "content": "Employee benefit content.",
            "metadata": {"plan_id": "EMP-INS-001", "data_status": "illustrative_unverified"}
        }
    ]
    retrieval_emp = {"chunks": emp_chunks, "contains_unverified": True}
    res_emp = gen_service.generate_answer(
        query="What is the executive cash?",
        role="employee",
        selected_plan_id="EMP-INS-001",
        retrieval_result=retrieval_emp
    )
    assert "Executive Employee Insurance Plan" in res_emp.answer_text

# --------------------------------------------------------------------------
# 13. Gemini failure handling and fallback reporting
# --------------------------------------------------------------------------
def test_gemini_failure_handling_and_fallback():
    gen_service = AnswerGenerationService()
    # Mock httpx failure
    with patch("httpx.Client.post", side_effect=Exception("Simulated API timeout")):
        answer_text, success = gen_service._call_gemini(
            query="What is Hospital Cash?",
            role="customer",
            plan_id="HS-GOLD-001",
            retrieval_result={"chunks": [{"content": "Daily Hospital Cash is Rs 5,000.", "metadata": {"section_number": "3", "section_title": "CASH"}}], "formatted_context": "context"},
            is_comparison=False
        )
        assert success is False
        assert "5,000" in answer_text

# --------------------------------------------------------------------------
# 14. Existing comparisons, plan-scoped conversations, and follow-up
# --------------------------------------------------------------------------
def test_scope_resolution_comparison_and_scoping():
    # Comparison
    comp_res = ScopeResolver.resolve_scope(
        query="Compare Hospital Cash between Basic and Gold",
        selected_plan_id="HS-GOLD-001",
        role="customer"
    )
    assert comp_res.is_comparison is True
    assert "HS-BASIC-001" in comp_res.effective_scope
    assert "HS-GOLD-001" in comp_res.effective_scope

    # Follow up
    follow_up_res = ScopeResolver.resolve_scope(
        query="What are its waiting periods?",
        selected_plan_id="HS-GOLD-001",
        role="customer"
    )
    assert follow_up_res.reason == "follow_up"
    assert follow_up_res.effective_scope == ["HS-GOLD-001"]
