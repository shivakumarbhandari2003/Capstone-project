import pytest
import time
import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import jwt

from backend.app.main import app
from backend.app.core.config import settings, get_jwt_secret
from backend.app.services.jwt_service import jwt_service
from backend.app.services.auth_service import hash_password, verify_password
from backend.app.db.sqlite_manager import sqlite_db

client = TestClient(app)

# Dynamic test user prefix to prevent DB collision
TEST_RUN_ID = uuid.uuid4().hex[:8]

def get_unique_email(prefix: str = "jwt_user") -> str:
    return f"{prefix}_{TEST_RUN_ID}_{uuid.uuid4().hex[:6]}@example.com"

# =========================================================================
# 1. CORE CRYPTOGRAPHIC & TOKEN CREATION TESTS
# =========================================================================

def test_jwt_access_token_creation_and_payload_structure():
    """Verify access token contains required claims and minimal data."""
    user_id = f"user_test_{uuid.uuid4().hex[:6]}"
    role = "customer"
    token, jti = jwt_service.create_access_token(user_id=user_id, role=role)

    assert isinstance(token, str)
    assert token.startswith("eyJ")
    assert jti.startswith("jwt_")

    # Decode directly using secret to inspect claims
    secret = get_jwt_secret()
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    assert payload["sub"] == user_id
    assert payload["role"] == role
    assert payload["type"] == "access"
    assert payload["jti"] == jti
    assert "exp" in payload
    assert "iat" in payload
    assert "nbf" in payload

    # Ensure sensitive fields are NEVER included in JWT
    assert "password" not in payload
    assert "health" not in payload
    assert "plan_details" not in payload

def test_jwt_signature_validation_and_tampering():
    """Verify signature validation rejects tokens signed with wrong key or tampered payloads."""
    token, _ = jwt_service.create_access_token(user_id="user_123", role="customer")

    # 1. Valid token decodes successfully
    decoded = jwt_service.decode_access_token(token)
    assert decoded["sub"] == "user_123"

    # 2. Tampered token payload
    parts = token.split(".")
    tampered_token = f"{parts[0]}.eyJzdWIiOiAiaGFja2VyIn0.{parts[2]}"
    with pytest.raises(Exception):
        jwt_service.decode_access_token(tampered_token)

    # 3. Wrong secret key
    with pytest.raises(Exception):
        jwt.decode(token, "wrong_secret_key_12345678901234567890", algorithms=["HS256"])

def test_jwt_expiration_enforcement():
    """Verify that expired JWT access tokens are strictly rejected."""
    # Create token expired 1 minute ago
    expired_token, _ = jwt_service.create_access_token(
        user_id="user_exp",
        role="customer",
        expires_delta=timedelta(seconds=-60)
    )

    with pytest.raises(Exception) as excinfo:
        jwt_service.decode_access_token(expired_token)
    assert "expired" in str(excinfo.value.detail).lower()

def test_jwt_malformed_token_rejection():
    """Verify malformed or garbage tokens are rejected."""
    for malformed in ["garbage", "header.payload", "a.b.c.d", "", "Bearer"]:
        with pytest.raises(Exception):
            jwt_service.decode_access_token(malformed)

# =========================================================================
# 2. AUTHENTICATION & LOGIN FLOW TESTS (HTTP)
# =========================================================================

def test_signup_issues_jwt_and_httponly_cookie():
    """Verify signup returns access JWT and sets HttpOnly refresh cookie."""
    email = get_unique_email("signup")
    res = client.post("/api/auth/signup", json={
        "email": email,
        "password": "Password123!",
        "role": "customer",
        "full_name": "JWT Test User"
    })
    assert res.status_code == 201
    data = res.json()

    # Access token in response body
    assert "token" in data
    assert "access_token" in data
    assert data["token"].startswith("eyJ")
    assert data["access_token"] == data["token"]
    assert data["token_type"] == "Bearer"
    assert data["user"]["email"] == email

    # HttpOnly refresh cookie set by backend
    assert settings.REFRESH_COOKIE_NAME in res.cookies
    refresh_cookie = res.cookies[settings.REFRESH_COOKIE_NAME]
    assert refresh_cookie.startswith("refr_")

    # In browser flow, refresh_token is NOT exposed in response body
    assert data.get("refresh_token") is None

def test_login_success_and_invalid_credentials():
    """Verify login authentication against SQLite with valid and invalid passwords."""
    email = get_unique_email("login")
    signup_res = client.post("/api/auth/signup", json={
        "email": email,
        "password": "CorrectPassword123!",
        "role": "customer"
    })
    assert signup_res.status_code == 201

    # 1. Invalid password
    bad_res = client.post("/api/auth/login", json={
        "email": email,
        "password": "WrongPassword!"
    })
    assert bad_res.status_code == 401
    assert "Invalid email or password" in bad_res.json()["detail"]

    # 2. Correct password
    good_res = client.post("/api/auth/login", json={
        "email": email,
        "password": "CorrectPassword123!"
    })
    assert good_res.status_code == 200
    good_data = good_res.json()
    assert good_data["token"].startswith("eyJ")
    assert settings.REFRESH_COOKIE_NAME in good_res.cookies

# =========================================================================
# 3. REFRESH TOKEN ROTATION & REUSE DETECTION TESTS
# =========================================================================

def test_refresh_token_rotation_flow():
    """Verify that using a refresh token rotates it and issues a new access token."""
    email = get_unique_email("rotate")
    login_res = client.post("/api/auth/signup", json={
        "email": email,
        "password": "Password123!",
        "role": "customer"
    })
    initial_access_token = login_res.json()["token"]
    initial_refresh_cookie = login_res.cookies[settings.REFRESH_COOKIE_NAME]

    # Call /api/auth/refresh with the cookie
    refresh_res = client.post(
        "/api/auth/refresh",
        cookies={settings.REFRESH_COOKIE_NAME: initial_refresh_cookie}
    )
    assert refresh_res.status_code == 200
    refresh_data = refresh_res.json()

    # New access token issued
    new_access_token = refresh_data["access_token"]
    assert new_access_token.startswith("eyJ")
    assert new_access_token != initial_access_token

    # New rotated refresh cookie returned
    new_refresh_cookie = refresh_res.cookies[settings.REFRESH_COOKIE_NAME]
    assert new_refresh_cookie.startswith("refr_")
    assert new_refresh_cookie != initial_refresh_cookie

    # Old refresh token is marked revoked and cannot be used again
    old_hash = jwt_service.hash_token(initial_refresh_cookie)
    old_record = sqlite_db.get_refresh_token_record(old_hash)
    assert old_record["revoked_at"] is not None
    assert old_record["replaced_by_token_id"] is not None

def test_refresh_token_reuse_detection_and_lockout():
    """Verify that replaying a rotated refresh token revokes all user sessions (theft protection)."""
    email = get_unique_email("reuse")
    login_res = client.post("/api/auth/signup", json={
        "email": email,
        "password": "Password123!",
        "role": "customer"
    })
    initial_refresh_cookie = login_res.cookies[settings.REFRESH_COOKIE_NAME]

    # 1. Legitimate user rotates the token once
    first_refresh = client.post(
        "/api/auth/refresh",
        cookies={settings.REFRESH_COOKIE_NAME: initial_refresh_cookie}
    )
    assert first_refresh.status_code == 200
    legitimate_new_cookie = first_refresh.cookies[settings.REFRESH_COOKIE_NAME]

    # 2. Attacker attempts to reuse the already-spent initial token
    breach_attempt = client.post(
        "/api/auth/refresh",
        cookies={settings.REFRESH_COOKIE_NAME: initial_refresh_cookie}
    )
    assert breach_attempt.status_code == 401
    assert "reuse detected" in breach_attempt.json()["detail"].lower()

    # 3. As a result of reuse detection, the user's active session is also revoked
    active_try = client.post(
        "/api/auth/refresh",
        cookies={settings.REFRESH_COOKIE_NAME: legitimate_new_cookie}
    )
    assert active_try.status_code == 401

def test_expired_refresh_token_rejected():
    """Verify expired refresh tokens are rejected with 401."""
    # First create a valid user so foreign key constraint succeeds
    email = get_unique_email("expired")
    signup_res = client.post("/api/auth/signup", json={
        "email": email,
        "password": "Password123!",
        "role": "customer"
    })
    user_id = signup_res.json()["user"]["user_id"]

    # Insert an already-expired refresh token record for this user
    expired_token = f"refr_expired_{uuid.uuid4().hex}"
    exp_hash = jwt_service.hash_token(expired_token)

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    exp_iso = (now - timedelta(days=1)).isoformat()
    with sqlite_db._get_connection() as conn:
        conn.execute("""
            INSERT INTO refresh_tokens (token_id, token_hash, user_id, role, created_at, expires_at)
            VALUES (?, ?, ?, 'customer', ?, ?)
        """, (f"rftk_{uuid.uuid4().hex[:8]}", exp_hash, user_id, now_iso, exp_iso))
        conn.commit()

    res = client.post(
        "/api/auth/refresh",
        cookies={settings.REFRESH_COOKIE_NAME: expired_token}
    )
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()

# =========================================================================
# 4. LOGOUT & REVOCATION TESTS
# =========================================================================

def test_logout_revokes_refresh_token_and_blacklists_access_token():
    """Verify logout invalidates both the refresh cookie and the access token."""
    email = get_unique_email("logout")
    login_res = client.post("/api/auth/signup", json={
        "email": email,
        "password": "Password123!",
        "role": "customer"
    })
    access_token = login_res.json()["token"]
    refresh_cookie = login_res.cookies[settings.REFRESH_COOKIE_NAME]

    # Verify /api/auth/me works initially
    me_before = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_before.status_code == 200

    # Call /api/auth/logout
    logout_res = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies={settings.REFRESH_COOKIE_NAME: refresh_cookie}
    )
    assert logout_res.status_code == 200

    # 1. Access token is blacklisted immediately
    me_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_after.status_code == 401
    assert "revoked" in me_after.json()["detail"].lower()

    # 2. Refresh token cannot be used to obtain a new token
    refresh_after = client.post(
        "/api/auth/refresh",
        cookies={settings.REFRESH_COOKIE_NAME: refresh_cookie}
    )
    assert refresh_after.status_code == 401

# =========================================================================
# 5. DUAL-TOKEN BACKWARD COMPATIBILITY TESTS
# =========================================================================

def test_legacy_opaque_session_compatibility():
    """Verify Phase 1 opaque session tokens ('sess_...') continue to authenticate."""
    email = get_unique_email("legacy")
    signup_res = client.post("/api/auth/signup", json={
        "email": email,
        "password": "Password123!",
        "role": "customer"
    })
    user_id = signup_res.json()["user"]["user_id"]

    # Manually create legacy opaque session in SQLite
    legacy_sess = sqlite_db.create_session(user_id=user_id, role="customer")
    assert legacy_sess.startswith("sess_")

    # Access protected /api/auth/me using legacy token
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {legacy_sess}"})
    assert me_res.status_code == 200
    assert me_res.json()["user_id"] == user_id
    assert me_res.json()["email"] == email

# =========================================================================
# 6. API CLIENT TRANSPORT & HEADER FALLBACK TESTS
# =========================================================================

def test_api_client_refresh_via_header_or_body():
    """Verify automated API clients can pass refresh tokens via header or body."""
    email = get_unique_email("apiclient")
    # Request body transport via X-Client-Type: api
    login_res = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "Password123!", "role": "customer"},
        headers={"X-Client-Type": "api"}
    )
    assert login_res.status_code == 201
    refresh_token = login_res.json()["refresh_token"]
    assert refresh_token is not None
    assert refresh_token.startswith("refr_")

    # Refresh using X-Refresh-Token header
    ref_header_res = client.post(
        "/api/auth/refresh",
        headers={"X-Refresh-Token": refresh_token}
    )
    assert ref_header_res.status_code == 200
    new_access = ref_header_res.json()["access_token"]
    assert new_access.startswith("eyJ")

# =========================================================================
# 7. ROLE-BASED ACCESS CONTROL (RBAC) WITH JWT
# =========================================================================

def test_jwt_rbac_enforcement_customer_vs_employee_vs_admin():
    """Verify that role claims embedded in JWTs correctly enforce RBAC on server."""
    # 1. Customer
    cust_res = client.post("/api/auth/login", json={"email": "shivu@gmail.com", "password": "12345678"})
    assert cust_res.status_code == 200
    cust_jwt = cust_res.json()["token"]

    # Customer blocked from Claim Predictor
    pred_res = client.post(
        "/api/claim-predictor/predict",
        headers={"Authorization": f"Bearer {cust_jwt}"},
        json={"age": 40, "days_hospitalised": 3, "icu_days": 0, "procedures_claimed": 1,
              "prior_daycare_claims_year": 0, "extended_stay_flag": 0, "plan": "Gold",
              "pre_existing": "no", "claim_type": "Major surgery", "documents_complete": "yes"}
    )
    assert pred_res.status_code == 403

    # Customer blocked from Admin Dashboard
    adm_res = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {cust_jwt}"})
    assert adm_res.status_code == 403

    # 2. Employee
    emp_res = client.post("/api/auth/login", json={"email": "murali@gmail.com", "password": "12345678"})
    assert emp_res.status_code == 200
    emp_jwt = emp_res.json()["token"]

    emp_pred_res = client.post(
        "/api/claim-predictor/predict",
        headers={"Authorization": f"Bearer {emp_jwt}"},
        json={"age": 40, "days_hospitalised": 3, "icu_days": 0, "procedures_claimed": 1,
              "prior_daycare_claims_year": 0, "extended_stay_flag": 0, "plan": "Gold",
              "pre_existing": "no", "claim_type": "Major surgery", "documents_complete": "yes"}
    )
    assert emp_pred_res.status_code == 200

    # 3. Admin
    sys_admin_res = client.post("/api/auth/login", json={"email": "admin@gmail.com", "password": "admin@123"})
    assert sys_admin_res.status_code == 200
    admin_jwt = sys_admin_res.json()["token"]

    admin_overview = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {admin_jwt}"})
    assert admin_overview.status_code == 200
    assert "kpis" in admin_overview.json()
    assert "total_registered_users" in admin_overview.json()["kpis"]
