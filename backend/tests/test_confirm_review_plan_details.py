import pytest
import uuid
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.policy_review_service import (
    policy_review_service,
    CANONICAL_PLAN_REVIEW_DATA,
    PLAN_DOCUMENT_MAPPING
)

client = TestClient(app)

def test_policy_review_mapping_and_provenance():
    """Verify each canonical plan ID maps to the exact authorized TXT document."""
    assert PLAN_DOCUMENT_MAPPING["HS-BASIC-001"] == "basic.txt"
    assert PLAN_DOCUMENT_MAPPING["HS-GOLD-001"] == "gold.txt"
    assert PLAN_DOCUMENT_MAPPING["HS-PREMIUM-001"] == "premium.txt"

def test_plan_specific_extracted_values_basic():
    """Verify Basic plan strictly contains HS-BASIC-001 values with zero leakage."""
    basic = policy_review_service.get_review_data_for_plan("HS-BASIC-001")
    details = basic["plan_details"]
    limits = basic["benefits_coverage_limits"]
    
    assert details["plan_name"] == "Health Shield – Basic"
    assert details["plan_id"] == "HS-BASIC-001"
    assert details["annual_premium"] == "Rs. 5,500*"
    assert details["payment_frequency"] == "Annual only"
    assert details["official_plan_number"] == "Not assigned"
    
    assert limits["hospital_cash"]["daily_benefit"] == "Rs. 2,000 / day"
    assert limits["hospital_cash"]["max_days"] == "Maximum 10 days"
    assert limits["icu_benefit"]["daily_benefit"] == "Rs. 4,000 / day"
    assert limits["icu_benefit"]["relationship"] == "Additional to hospital cash*"
    assert limits["surgery_benefit"]["basis"] == "Basis: Rs. 2,00,000"
    assert limits["surgery_benefit"]["overall_max"] == "Rs. 6,00,000*"

def test_plan_specific_extracted_values_gold():
    """Verify Gold plan strictly contains HS-GOLD-001 values with zero leakage."""
    gold = policy_review_service.get_review_data_for_plan("HS-GOLD-001")
    details = gold["plan_details"]
    limits = gold["benefits_coverage_limits"]
    
    assert details["plan_name"] == "Health Shield – Gold"
    assert details["plan_id"] == "HS-GOLD-001"
    assert details["annual_premium"] == "Rs. 11,800*"
    assert details["payment_frequency"] == "Annual"
    
    assert limits["hospital_cash"]["daily_benefit"] == "Rs. 5,000 / day"
    assert limits["hospital_cash"]["max_days"] == "Max 20 days"
    assert limits["icu_benefit"]["daily_benefit"] == "Rs. 10,000 / day"
    assert limits["icu_benefit"]["relationship"] == "ICU and hospital cash combination subject to terms*"
    assert limits["surgery_benefit"]["basis"] == "Basis: Rs. 5,00,000"
    assert limits["surgery_benefit"]["overall_max"] == "Rs. 25,00,000*"

def test_plan_specific_extracted_values_premium():
    """Verify Premium plan strictly contains HS-PREMIUM-001 values with zero leakage."""
    prem = policy_review_service.get_review_data_for_plan("HS-PREMIUM-001")
    details = prem["plan_details"]
    limits = prem["benefits_coverage_limits"]
    
    assert details["plan_name"] == "Health Shield – Premium"
    assert details["plan_id"] == "HS-PREMIUM-001"
    assert details["annual_premium"] == "Rs. 22,500*"
    assert details["payment_frequency"] == "Annual"
    
    assert limits["hospital_cash"]["daily_benefit"] == "Rs. 10,000 / day"
    assert limits["hospital_cash"]["max_days"] == "Max 30 days"
    assert limits["icu_benefit"]["daily_benefit"] == "Rs. 20,000 / day"
    assert limits["icu_benefit"]["relationship"] == "ICU replaces hospital cash"
    assert limits["surgery_benefit"]["basis"] == "Basis: Rs. 10,00,000"

def test_cross_plan_data_isolation():
    """Verify that no premium values leak into Basic or Gold plans."""
    basic = policy_review_service.get_review_data_for_plan("HS-BASIC-001")
    gold = policy_review_service.get_review_data_for_plan("HS-GOLD-001")
    prem = policy_review_service.get_review_data_for_plan("HS-PREMIUM-001")
    
    # Premium Rs. 22,500 must not appear in Basic or Gold
    assert basic["plan_details"]["annual_premium"] != prem["plan_details"]["annual_premium"]
    assert gold["plan_details"]["annual_premium"] != prem["plan_details"]["annual_premium"]
    
    # ICU replacement rule in Premium must not appear in Basic
    assert basic["benefits_coverage_limits"]["icu_benefit"]["relationship"] != "ICU replaces hospital cash"
    assert basic["benefits_coverage_limits"]["icu_benefit"]["relationship"] == "Additional to hospital cash*"

def test_api_review_details_endpoint_authenticated():
    """Test GET /api/plans/{plan_id}/review-details with valid customer auth token."""
    email = f"test_rev_{uuid.uuid4().hex[:8]}@example.com"
    signup_resp = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "Password123!",
            "role": "customer",
            "full_name": "Review Tester"
        }
    )
    assert signup_resp.status_code == 201
    token = signup_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get("/api/plans/HS-GOLD-001/review-details", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["plan_details"]["plan_id"] == "HS-GOLD-001"
    assert data["plan_details"]["annual_premium"] == "Rs. 11,800*"
    assert data["benefits_coverage_limits"]["hospital_cash"]["daily_benefit"] == "Rs. 5,000 / day"

def test_api_review_details_invalid_plan_403_or_404():
    """Test GET /api/plans/{plan_id}/review-details returns 403 or 404 for unauthorized/invalid plan."""
    email = f"test_rev_{uuid.uuid4().hex[:8]}@example.com"
    signup_resp = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "Password123!",
            "role": "customer",
            "full_name": "Review Tester"
        }
    )
    assert signup_resp.status_code == 201
    token = signup_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Non-existent or unauthorized plan ID
    response = client.get("/api/plans/NON-EXISTENT-PLAN/review-details", headers=headers)
    assert response.status_code in [403, 404]
