import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.sqlite_manager import sqlite_db

client = TestClient(app)

def test_confirmed_plan_preserved_and_chatbot_exploration_allowed():
    """
    Test user requirement:
    Once the user has confirmed any plan, they can go back to any other plan, visit it,
    and use the chatbot for that visited plan. The visited plan is strictly used for
    chatbot response, preserving the confirmed policy without overwriting or demoting it.
    """
    # 1. Dedicated test customer to isolate test runs and prevent polluting shared demo accounts
    import uuid
    test_email = f"test_explore_{uuid.uuid4().hex[:8]}@example.com"
    signup_resp = client.post("/api/auth/signup", json={
        "email": test_email,
        "password": "Password123!",
        "role": "customer",
        "full_name": "Test Customer Explore"
    })
    assert signup_resp.status_code == 201
    token = signup_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Complete eligibility assessment with eligible inputs
    elig_payload = {
        "age": 28,
        "height_cm": 175,
        "weight_kg": 68,
        "smoker": "No",
        "alcoholic": "No",
        "pre_existing_condition": "None"
    }
    elig_resp = client.post("/api/eligibility/assess", json=elig_payload, headers=headers)
    assert elig_resp.status_code == 200
    assert elig_resp.json()["outcome"] == "ELIGIBLE"

    # 3. Select HS-BASIC-001 and confirm it
    sel_resp = client.post("/api/eligibility/select-plan", json={"selected_plan_id": "HS-BASIC-001"}, headers=headers)
    assert sel_resp.status_code == 200

    conf_resp = client.post("/api/eligibility/confirm-plan", json={"plan_id": "HS-BASIC-001"}, headers=headers)
    assert conf_resp.status_code == 200
    assert conf_resp.json()["status"] == "CONFIRMED"

    # 4. Verify authoritative selection is confirmed
    me_resp = client.get("/api/eligibility/me", headers=headers)
    assert me_resp.status_code == 200
    active_sel = me_resp.json()["active_plan_selection"]
    assert active_sel["selected_plan_id"] == "HS-BASIC-001"
    assert active_sel["status"] == "CONFIRMED"

    # 5. User visits another plan (HS-GOLD-001) for chatbot exploration
    # select-plan should acknowledge exploration without overwriting the confirmed plan
    exp_sel_resp = client.post("/api/eligibility/select-plan", json={"selected_plan_id": "HS-GOLD-001"}, headers=headers)
    assert exp_sel_resp.status_code == 200
    exp_data = exp_sel_resp.json()
    assert exp_data["status"] == "CONFIRMED"
    assert exp_data["confirmed_plan_id"] == "HS-BASIC-001"
    assert exp_data["mode"] == "CHATBOT_EXPLORATION"

    # 6. Verify confirmed policy in database remains intact
    me_resp_after = client.get("/api/eligibility/me", headers=headers)
    active_sel_after = me_resp_after.json()["active_plan_selection"]
    assert active_sel_after["selected_plan_id"] == "HS-BASIC-001"
    assert active_sel_after["status"] == "CONFIRMED"

    # 7. User starts a chatbot conversation scoped to the visited plan (HS-GOLD-001)
    chat_gold_resp = client.post("/api/conversations", json={"selected_plan_id": "HS-GOLD-001"}, headers=headers)
    assert chat_gold_resp.status_code == 201
    assert chat_gold_resp.json()["selected_plan_id"] == "HS-GOLD-001"

    # 8. User can also chat with their confirmed plan (HS-BASIC-001)
    chat_basic_resp = client.post("/api/conversations", json={"selected_plan_id": "HS-BASIC-001"}, headers=headers)
    assert chat_basic_resp.status_code == 201
    assert chat_basic_resp.json()["selected_plan_id"] == "HS-BASIC-001"

    # 9. Role-based plan isolation is still enforced: customer cannot chat with employee plan
    unauth_resp = client.post("/api/conversations", json={"selected_plan_id": "EMP-INS-001"}, headers=headers)
    assert unauth_resp.status_code == 403
