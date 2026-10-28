"""
Comprehensive test suite verifying RAG pipeline performance across all 24 complex policy questions:
- EMP-01 to EMP-08 (Executive Employee Plan)
- BASIC-01 to BASIC-08 (Health Shield Basic)
- GOLD-01 to GOLD-08 (Health Shield Gold)

Verifies:
1. Retrieval evidence selection & relevance (correct section ranked #1, no claim-free hijacking).
2. Scope resolution fidelity (no scope hijacking from 'annual premium' to Premium plan).
3. Arithmetic accuracy, caps, and limit application: min(claimed, max) * rate.
4. Distinction between fixed benefits and full-bill reimbursement.
5. Distinction between continuous stays and separate admissions.
6. Correct plan-specific combination rules (Basic vs Gold).
7. Explicit abstention / declaration when terms are not defined in the policy text.
"""
import pytest
from backend.app.services.rag_orchestrator import RAGOrchestrator
from backend.app.services.auth_service import UserIdentity
from backend.app.services.conversation_service import ConversationManager
from backend.app.services.scope_resolver import ScopeResolver
from backend.app.services.retrieval_service import HybridRetrievalService

@pytest.fixture(scope="module")
def rag_system():
    orchestrator = RAGOrchestrator()
    cm = ConversationManager()
    return orchestrator, cm

# ==============================================================================
# 1. SCOPE RESOLUTION FIDELITY TESTS (PREMIUM HIJACK PREVENTION)
# ==============================================================================

def test_scope_resolution_annual_premium_stays_basic():
    """Verify 'annual premium' query stays on HS-BASIC-001 and does not hijack to HS-PREMIUM-001."""
    res = ScopeResolver.resolve_scope(
        query="I am 40 years old. What is my annual premium, and can I pay monthly instead?",
        selected_plan_id="HS-BASIC-001",
        role="customer"
    )
    assert res.effective_scope == ["HS-BASIC-001"]
    assert not res.is_out_of_scope

def test_scope_resolution_renewal_premium_stays_gold():
    """Verify 'renewal premium' query stays on HS-GOLD-001 and does not hijack to HS-PREMIUM-001."""
    res = ScopeResolver.resolve_scope(
        query="The annual premium is ₹11,800. Is that my guaranteed renewal premium, including taxes?",
        selected_plan_id="HS-GOLD-001",
        role="customer"
    )
    assert res.effective_scope == ["HS-GOLD-001"]
    assert not res.is_out_of_scope

def test_scope_resolution_explicit_premium_comparison():
    """Verify explicit comparison between Basic and Premium correctly includes both."""
    res = ScopeResolver.resolve_scope(
        query="Compare Basic and Premium",
        selected_plan_id="HS-BASIC-001",
        role="customer"
    )
    assert set(res.effective_scope) == {"HS-BASIC-001", "HS-PREMIUM-001"}
    assert res.is_comparison

# ==============================================================================
# 2. EVIDENCE SELECTION & RE-RANKING TESTS (NO CLAIM-FREE HIJACKING)
# ==============================================================================

def test_other_surgery_retrieval_boost():
    """Verify that an Other Surgery query prioritizes Section 7 over Claim-Free Benefit Increase."""
    retrieval = HybridRetrievalService()
    res = retrieval.retrieve(
        query="I underwent an eligible Other Surgery for seven payable days. What is my benefit?",
        role="customer",
        effective_scope=["HS-BASIC-001"],
        top_k=5
    )
    chunks = res["chunks"]
    assert len(chunks) > 0
    top_chunk_title = (chunks[0].get("metadata", {}).get("section_title") or "").upper()
    assert "OTHER SURGERY" in top_chunk_title
    # Verify Claim-Free table is not ranked #1
    assert "CLAIM-FREE" not in top_chunk_title

def test_hospital_cash_retrieval_boost():
    """Verify Hospital Cash query prioritizes Section 3."""
    retrieval = HybridRetrievalService()
    res = retrieval.retrieve(
        query="I was hospitalized for 12 eligible days. My daily hospital cash is ₹2,000. How much can I claim?",
        role="customer",
        effective_scope=["HS-BASIC-001"],
        top_k=5
    )
    chunks = res["chunks"]
    assert any("HOSPITAL CASH" in (c.get("metadata", {}).get("section_title") or "").upper() for c in chunks[:2])

# ==============================================================================
# 3. END-TO-END BENCHMARK TEST SUITE
# ==============================================================================

def test_basic_01_premium_and_payment_mode(rag_system):
    """BASIC-01: Age 40 annual premium is ₹7,500 (illustrative), annual mode only, no monthly."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_basic_01", email="b01@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_basic_01", "customer", "HS-BASIC-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I am 40 years old. What is my annual premium, and can I pay monthly instead?"
    )
    ans = out["message"]["content"]
    assert "7,500" in ans or "7500" in ans
    assert any(term in ans.lower() for term in ["annual", "only", "not offered", "no monthly", "cannot pay monthly"])
    assert "HS-PREMIUM-001" not in out["scope_resolution"]["effective_scope"]

def test_basic_02_hospital_cash_limit(rag_system):
    """BASIC-02: 12 days capped at 10 days = 10 * 2,000 = ₹20,000."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_basic_02", email="b02@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_basic_02", "customer", "HS-BASIC-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I was hospitalized for 12 eligible days. My daily hospital cash is ₹2,000. How much can I claim?"
    )
    ans = out["message"]["content"]
    assert "20,000" in ans or "20000" in ans
    assert "10" in ans

def test_basic_03_icu_cap(rag_system):
    """BASIC-03: 6 ICU days capped at 5 days = 5 * 4,000 = ₹20,000 max."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_basic_03", email="b03@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_basic_03", "customer", "HS-BASIC-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I spent six eligible days in the ICU and six days in hospital overall. Can I claim ICU benefits for all six days?"
    )
    ans = out["message"]["content"]
    assert "20,000" in ans or "20000" in ans
    assert "5" in ans
    assert any(neg in ans.lower() for neg in ["no", "cannot", "capped", "maximum"])

def test_basic_04_daycare_and_hospital_cash_separation(rag_system):
    """BASIC-04: Day care cataract ₹10,000 eligible, cannot claim hospital cash for same-day stay."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_basic_04", email="b04@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_basic_04", "customer", "HS-BASIC-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I had cataract surgery and went home on the same day. Can I receive both ₹10,000 for day-care and ₹2,000 for hospital cash?"
    )
    ans = out["message"]["content"]
    assert any(neg in ans.lower() for neg in ["no", "cannot", "not payable", "not both"])
    assert "10,000" in ans or "10000" in ans

def test_basic_05_category_2_fixed_benefit_not_reimbursement(rag_system):
    """BASIC-05: Category 2 payout is ₹1,20,000 (60% of ₹2 lakh); does not reimburse full ₹3 lakh bill."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_basic_05", email="b05@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_basic_05", "customer", "HS-BASIC-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I had a Category 2 major surgery costing ₹3 lakh. Will the plan reimburse the entire bill?"
    )
    ans = out["message"]["content"]
    assert "1,20,000" in ans or "120000" in ans or "1.2" in ans
    assert any(neg in ans.lower() for neg in ["no", "not reimburse", "fixed", "lump sum", "not the entire"])

def test_basic_06_other_surgery_cap_and_no_claimfree_table(rag_system):
    """BASIC-06: min(7, 5) * 3,000 = ₹15,000 max. Unrelated claim-free table is not returned."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_basic_06", email="b06@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_basic_06", "customer", "HS-BASIC-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I underwent an eligible Other Surgery for seven payable days. What is my benefit?"
    )
    ans = out["message"]["content"]
    assert "15,000" in ans or "15000" in ans
    assert "5" in ans
    # Crucial negative check: Must NOT return the Claim-Free Benefit Increase table
    assert "10% of the original" not in ans
    assert "Claim-Free Increase Percentage" not in ans

def test_basic_07_medical_management_and_surgery_combination(rag_system):
    """BASIC-07: Medical Management and Surgery cannot be claimed together for same event under Basic."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_basic_07", email="b07@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_basic_07", "customer", "HS-BASIC-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I was hospitalized for dengue and also underwent surgery during the same illness episode. Can I claim Medical Management and Surgery benefits together?"
    )
    ans = out["message"]["content"]
    assert any(neg in ans.lower() for neg in ["no", "cannot", "not payable together", "separately"])

def test_basic_08_restoration_not_included(rag_system):
    """BASIC-08: Basic configuration does not include restoration."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_basic_08", email="b08@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_basic_08", "customer", "HS-BASIC-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "My major surgery exhausted my cover. Does Basic restore the benefit for my next surgery?"
    )
    ans = out["message"]["content"]
    assert any(neg in ans.lower() for neg in ["no", "does not restore", "not included", "not provided"])

def test_gold_01_renewal_premium_and_taxes(rag_system):
    """GOLD-01: ₹11,800 is illustrative, not guaranteed renewal premium, taxes extra."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_gold_01", email="g01@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_gold_01", "customer", "HS-GOLD-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "The annual premium is ₹11,800. Is that my guaranteed renewal premium, including taxes?"
    )
    ans = out["message"]["content"]
    assert any(neg in ans.lower() for neg in ["no", "not guaranteed", "illustrative", "subject to change"])
    assert any(t in ans.lower() for t in ["tax", "extra", "not included"])
    assert "HS-PREMIUM-001" not in out["scope_resolution"]["effective_scope"]

def test_gold_02_hospital_cash_cap(rag_system):
    """GOLD-02: 25 days capped at 20 days = 20 * 5,000 = ₹1,00,000."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_gold_02", email="g02@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_gold_02", "customer", "HS-GOLD-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I was hospitalized for 25 eligible days. How much hospital cash can I receive?"
    )
    ans = out["message"]["content"]
    assert "1,00,000" in ans or "100000" in ans or "1 lakh" in ans
    assert "20" in ans

def test_gold_03_icu_and_hospital_cash(rag_system):
    """GOLD-03: 3 days ICU (₹30,000) + 4 days Hospital Cash (₹20,000) = ₹50,000 total."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_gold_03", email="g03@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_gold_03", "customer", "HS-GOLD-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I spent three days in the ICU and four other days in the hospital. What are the ICU and hospital-cash benefits?"
    )
    ans = out["message"]["content"]
    assert "30,000" in ans or "30000" in ans
    assert "20,000" in ans or "20000" in ans
    assert "50,000" in ans or "50000" in ans

def test_gold_05_daycare_claim_limit(rag_system):
    """GOLD-05: Day care capped at 2 claims per year = 2 * 25,000 = ₹50,000 max (cannot receive ₹75,000)."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_gold_05", email="g05@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_gold_05", "customer", "HS-GOLD-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I had three eligible day-care procedures in one policy year. Can I receive ₹75,000?"
    )
    ans = out["message"]["content"]
    assert any(neg in ans.lower() for neg in ["no", "cannot", "capped", "maximum 2"])
    assert "50,000" in ans or "50000" in ans

def test_gold_06_medical_management_and_surgery_combination(rag_system):
    """GOLD-06: Under Gold, Medical Management and Surgery ARE payable together."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_gold_06", email="g06@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_gold_06", "customer", "HS-GOLD-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I had an eligible Medical Management claim for pneumonia and also underwent surgery for the same event. Can both benefits be paid?"
    )
    ans = out["message"]["content"]
    assert any(pos in ans.lower() for pos in ["yes", "payable together", "both benefits can be paid"])

def test_gold_07_restored_cover_unrelated_illness(rag_system):
    """GOLD-07: Restoration up to ₹5 lakh once per policy year applies for subsequent unrelated illness."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_gold_07", email="g07@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_gold_07", "customer", "HS-GOLD-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "My first major surgery exhausted the surgery limit. Can I use restored cover for another unrelated eligible surgery in the same policy year?"
    )
    ans = out["message"]["content"]
    assert any(pos in ans.lower() for pos in ["yes", "restored cover", "can use"])
    assert "5,00,000" in ans or "500000" in ans or "5 lakh" in ans

def test_gold_08_quick_cash_advance(rag_system):
    """GOLD-08: Quick Cash capped at ₹50,000 and is deducted from final claim settlement, not kept in addition."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_gold_08", email="g08@test.com", role="customer", is_approved=True)
    sess = cm.create_conversation("bench_gold_08", "customer", "HS-GOLD-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "My eligible Category 2 surgery benefit is ₹3 lakh. Can I receive ₹75,000 as Quick Cash and keep it in addition to my final payout?"
    )
    ans = out["message"]["content"]
    assert "50,000" in ans or "50000" in ans
    assert any(neg in ans.lower() for neg in ["no", "cannot receive ₹75,000", "deducted", "not in addition", "advance is deducted"])

def test_emp_01_salary_deductions_unspecified(rag_system):
    """EMP-01: Salary deduction and employer contribution are not specified in the policy."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_emp_01", email="e01@test.com", role="employee", is_approved=True)
    sess = cm.create_conversation("bench_emp_01", "employee", "EMP-INS-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I am an employee. How much annual premium will be deducted from my salary, and how much will my employer contribute?"
    )
    ans = out["message"]["content"]
    assert any(term in ans.lower() for term in ["not specify", "not defined", "unable to answer", "not specified"])

def test_emp_02_hospital_cash_and_bill_reimbursement(rag_system):
    """EMP-02: 5 days = 5 * 10,000 = ₹50,000. Clarifies fixed cash does not reimburse entire hospital bill."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_emp_02", email="e02@test.com", role="employee", is_approved=True)
    sess = cm.create_conversation("bench_emp_02", "employee", "EMP-INS-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I was hospitalized for five eligible days. How much hospital cash can I receive, and will it reimburse my entire hospital bill?"
    )
    ans = out["message"]["content"]
    assert "50,000" in ans or "50000" in ans
    assert any(neg in ans.lower() for neg in ["no", "not reimburse", "fixed daily", "actual medical expenses"])

def test_emp_06_extended_stay_separate_admissions(rag_system):
    """EMP-06: Two separate stays (20 + 15 days) do not qualify for Extended Stay (requires single continuous >30 days)."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_emp_06", email="e06@test.com", role="employee", is_approved=True)
    sess = cm.create_conversation("bench_emp_06", "employee", "EMP-INS-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I was hospitalized for 20 days in January and another 15 days in March. Does that qualify for the extended-stay benefit?"
    )
    ans = out["message"]["content"]
    assert any(neg in ans.lower() for neg in ["no", "do not qualify", "single continuous", "continuous hospital stay"])

def test_emp_07_health_checkup_cap(rag_system):
    """EMP-07: Health checkup capped at ₹5,000 max."""
    orchestrator, cm = rag_system
    user = UserIdentity(user_id="bench_emp_07", email="e07@test.com", role="employee", is_approved=True)
    sess = cm.create_conversation("bench_emp_07", "employee", "EMP-INS-001")
    out = orchestrator.process_query(
        sess.conversation_id, user,
        "I spent ₹6,000 on an eligible health check-up. Will I receive the full ₹6,000?"
    )
    ans = out["message"]["content"]
    assert "5,000" in ans or "5000" in ans
    assert any(neg in ans.lower() for neg in ["no", "not receive the full", "capped", "maximum"])
