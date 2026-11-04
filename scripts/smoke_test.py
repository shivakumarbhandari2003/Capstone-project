"""
Automated Smoke Test Suite — AI Health Insurance Assistant
Validates end-to-end critical paths across:
1. Health check & system metadata
2. Multi-role authentication (Customer, Employee, Admin)
3. RBAC plan filtering & document review details
4. Eligibility & confirmed policy persistence
5. Plan exploration without demoting confirmed policy
6. Conversation management & plan-scoped RAG access
7. Claim predictor model inference & RBAC
8. Admin workspace & governance telemetry
"""

import sys
import os
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

# Initialize FastAPI test client
from backend.app.main import app
from backend.app.db.sqlite_manager import sqlite_db
from backend.app.services.claim_predictor_service import claim_predictor_service
from backend.app.api.schemas.claim_predictor import ClaimPredictionInput

client = TestClient(app)

class SmokeTestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
        self.results = []

    def check(self, name: str, condition: bool, details: str = ""):
        self.total += 1
        if condition:
            self.passed += 1
            print(f"  [PASS] {name} {details}")
            self.results.append((name, "PASS", details))
        else:
            self.failed += 1
            print(f"  [FAIL] {name} {details}")
            self.results.append((name, "FAIL", details))

    def run_all(self):
        t0 = time.time()
        print("\n" + "=" * 75)
        print(" STARTING PRODUCTION SMOKE TEST SUITE — AI HEALTH INSURANCE ASSISTANT")
        print("=" * 75 + "\n")

        # ---------------------------------------------------------
        # Section 1: Health & Root Endpoints
        # ---------------------------------------------------------
        print("[1/8] Verifying Health & System Endpoints...")
        h_resp = client.get("/api/health")
        self.check("Health endpoint status 200", h_resp.status_code == 200)
        h_data = h_resp.json()
        self.check("Health status is HEALTHY", h_data.get("status") == "HEALTHY")
        self.check("Embedding dimension is 384", h_data.get("embedding_dimensions") == 384)

        root_resp = client.get("/")
        self.check("API Root status 200", root_resp.status_code == 200)

        # ---------------------------------------------------------
        # Section 2: Multi-Role Authentication
        # ---------------------------------------------------------
        print("\n[2/8] Verifying Multi-Role Authentication & Profile Restoration...")
        sqlite_db.provision_demo_accounts(force_reconcile=True)

        # Customer: Shivu
        c_login = client.post("/api/auth/login", json={"email": "shivu@gmail.com", "password": "12345678"})
        self.check("Customer login (shivu@gmail.com) 200", c_login.status_code == 200)
        c_token = c_login.json().get("token")
        c_headers = {"Authorization": f"Bearer {c_token}"}

        c_me = client.get("/api/auth/me", headers=c_headers)
        self.check("Customer /auth/me returns 200", c_me.status_code == 200)
        c_profile = c_me.json()
        self.check("Customer role is 'customer'", c_profile.get("role") == "customer")
        self.check("Customer confirmed status is True", c_profile.get("is_confirmed") is True)
        self.check("Customer confirmed plan is HS-GOLD-001", c_profile.get("confirmed_plan_id") == "HS-GOLD-001")

        # Employee: Murali
        e_login = client.post("/api/auth/login", json={"email": "murali@gmail.com", "password": "12345678"})
        self.check("Employee login (murali@gmail.com) 200", e_login.status_code == 200)
        e_token = e_login.json().get("token")
        e_headers = {"Authorization": f"Bearer {e_token}"}

        e_me = client.get("/api/auth/me", headers=e_headers)
        self.check("Employee role is 'employee'", e_me.json().get("role") == "employee")

        # Admin: Administrator
        a_login = client.post("/api/auth/login", json={"email": "admin@gmail.com", "password": "admin@123"})
        self.check("Admin login (admin@gmail.com) 200", a_login.status_code == 200)
        a_token = a_login.json().get("token")
        a_headers = {"Authorization": f"Bearer {a_token}"}

        a_me = client.get("/api/auth/me", headers=a_headers)
        self.check("Admin role is 'admin'", a_me.json().get("role") == "admin")

        # ---------------------------------------------------------
        # Section 3: Plan Listing & RBAC Filtering
        # ---------------------------------------------------------
        print("\n[3/8] Verifying Plan Registry & Role-Based Access Control...")
        c_plans_resp = client.get("/api/plans", headers=c_headers)
        self.check("Customer GET /api/plans status 200", c_plans_resp.status_code == 200)
        c_plan_ids = [p["plan_id"] for p in c_plans_resp.json().get("plans", [])]
        self.check("Customer plans count is 3", len(c_plan_ids) == 3)
        self.check("Customer CANNOT see employee plan EMP-INS-001", "EMP-INS-001" not in c_plan_ids)

        e_plans_resp = client.get("/api/plans", headers=e_headers)
        e_plan_ids = [p["plan_id"] for p in e_plans_resp.json().get("plans", [])]
        self.check("Employee can access employee plan EMP-INS-001", "EMP-INS-001" in e_plan_ids)
        self.check("Employee plans count is 4", len(e_plan_ids) == 4)

        # ---------------------------------------------------------
        # Section 4: Policy Review Details & Currency Consistency
        # ---------------------------------------------------------
        print("\n[4/8] Verifying Structured Policy Review Details & Currency Format...")
        rev_resp = client.get("/api/plans/HS-GOLD-001/review-details", headers=c_headers)
        self.check("Review details status 200", rev_resp.status_code == 200)
        rev_data = rev_resp.json()
        premium_str = rev_data["plan_details"].get("annual_premium", "")
        self.check("Annual premium shows 'Rs.' currency format", "Rs." in premium_str and "₹" not in premium_str, f"({premium_str})")
        hosp_cash_str = rev_data["benefits_coverage_limits"]["hospital_cash"].get("daily_benefit", "")
        self.check("Hospital cash shows 'Rs.' currency format", "Rs." in hosp_cash_str and "₹" not in hosp_cash_str, f"({hosp_cash_str})")

        # Customer blocked from employee review details
        rev_emp_resp = client.get("/api/plans/EMP-INS-001/review-details", headers=c_headers)
        self.check("Customer blocked from employee review details with 403", rev_emp_resp.status_code == 403)

        # ---------------------------------------------------------
        # Section 5: Plan Exploration & Confirmed Policy Preservation
        # ---------------------------------------------------------
        print("\n[5/8] Verifying Plan Exploration & Confirmed Policy Preservation...")
        # Shivu visits Premium plan
        sel_resp = client.post("/api/eligibility/select-plan", json={"selected_plan_id": "HS-PREMIUM-001"}, headers=c_headers)
        self.check("Select-plan returns 200 during exploration", sel_resp.status_code == 200)
        sel_data = sel_resp.json()
        self.check("Exploration mode acknowledged", sel_data.get("mode") == "CHATBOT_EXPLORATION")
        self.check("Confirmed plan remains HS-GOLD-001", sel_data.get("confirmed_plan_id") == "HS-GOLD-001")

        # Verify /auth/me still reports Gold as confirmed
        c_me_after = client.get("/api/auth/me", headers=c_headers)
        self.check("Auth me confirms policy remains Gold after exploration", c_me_after.json().get("confirmed_plan_id") == "HS-GOLD-001")

        # Verify /eligibility/me still reports Gold as active confirmed selection
        elig_me = client.get("/api/eligibility/me", headers=c_headers)
        self.check("Eligibility me reports status CONFIRMED", elig_me.json()["active_plan_selection"]["status"] == "CONFIRMED")
        self.check("Eligibility me reports plan HS-GOLD-001", elig_me.json()["active_plan_selection"]["selected_plan_id"] == "HS-GOLD-001")

        # ---------------------------------------------------------
        # Section 6: Conversation Creation & RBAC Plan Scoping
        # ---------------------------------------------------------
        print("\n[6/8] Verifying RAG Conversation Management & Scoping...")
        # Chat for confirmed plan
        chat_gold = client.post("/api/conversations", json={"selected_plan_id": "HS-GOLD-001"}, headers=c_headers)
        self.check("Customer can initiate chat on confirmed Gold plan (201)", chat_gold.status_code == 201)

        # Chat for explored plan
        chat_prem = client.post("/api/conversations", json={"selected_plan_id": "HS-PREMIUM-001"}, headers=c_headers)
        self.check("Customer can initiate chat on explored Premium plan (201)", chat_prem.status_code == 201)

        # Unauthorized plan chat attempt
        chat_emp = client.post("/api/conversations", json={"selected_plan_id": "EMP-INS-001"}, headers=c_headers)
        self.check("Customer blocked from chatting on Employee Exclusive plan (403)", chat_emp.status_code == 403)

        # ---------------------------------------------------------
        # Section 7: Claim Predictor Model Inference & RBAC
        # ---------------------------------------------------------
        print("\n[7/8] Verifying Claim Predictor ML Inference & RBAC...")
        claim_payload = {
            "age": 42,
            "days_hospitalised": 3,
            "icu_days": 1,
            "procedures_claimed": 1,
            "prior_daycare_claims_year": 0,
            "extended_stay_flag": 0,
            "plan": "Gold",
            "pre_existing": "no",
            "claim_type": "Major surgery",
            "documents_complete": "yes"
        }

        # Customer forbidden from claim predictor
        c_pred = client.post("/api/claim-predictor/predict", json=claim_payload, headers=c_headers)
        self.check("Customer blocked from Claim Predictor with 403", c_pred.status_code == 403)

        # Employee authorized for claim predictor
        e_pred = client.post("/api/claim-predictor/predict", json=claim_payload, headers=e_headers)
        self.check("Employee claim prediction returns 200 OK", e_pred.status_code == 200)
        e_pred_data = e_pred.json()
        self.check("Prediction payout is positive float", e_pred_data.get("prediction", 0) > 0, f"(Payout: {e_pred_data.get('formatted_prediction')})")
        self.check("Prediction output contains validated inputs", e_pred_data.get("validated_inputs", {}).get("age") == 42)

        # Direct singleton model test
        inp = ClaimPredictionInput(**claim_payload)
        direct_res = claim_predictor_service.predict(inp)
        self.check("Direct ClaimPredictorService produces numerical prediction", direct_res["prediction"] > 0)

        # ---------------------------------------------------------
        # Section 8: Admin Dashboard Governance & Persistence
        # ---------------------------------------------------------
        print("\n[8/8] Verifying Admin Governance & Database Integrity...")
        # Non-admin blocked
        kpis_bad = client.get("/api/admin/overview", headers=c_headers)
        self.check("Customer blocked from Admin Overview with 403", kpis_bad.status_code == 403)

        # Admin authorized
        kpis_ok = client.get("/api/admin/overview", headers=a_headers)
        self.check("Admin GET /api/admin/overview returns 200", kpis_ok.status_code == 200)
        overview_data = kpis_ok.json()
        kpis_data = overview_data.get("kpis", {})
        self.check("KPIs include total_registered_users", "total_registered_users" in kpis_data, f"(Count: {kpis_data.get('total_registered_users')})")
        self.check("KPIs include total_conversations", "total_conversations" in kpis_data, f"(Count: {kpis_data.get('total_conversations')})")

        # Database session sliding renewal test
        sess = sqlite_db.get_session(c_token)
        self.check("Customer session exists and is active in SQLite", sess is not None)
        self.check("Customer session role is 'customer'", sess.get("role") == "customer")

        elapsed = time.time() - t0
        print("\n" + "=" * 75)
        print(f" SMOKE TEST COMPLETE in {elapsed:.2f}s: {self.passed}/{self.total} PASSED ({self.failed} FAILED)")
        print("=" * 75 + "\n")

        if self.failed > 0:
            sys.exit(1)
        else:
            sys.exit(0)

if __name__ == "__main__":
    runner = SmokeTestRunner()
    runner.run_all()
