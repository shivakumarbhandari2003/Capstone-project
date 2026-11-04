import re
from datetime import datetime, timezone
from typing import Optional, Set
import jwt
from pydantic import BaseModel
from fastapi import Request, HTTPException, status
import bcrypt
from backend.app.db.sqlite_manager import sqlite_db
from backend.app.core.config import settings, get_jwt_secret
from backend.app.core.logging_config import logger
from backend.app.services.jwt_service import jwt_service

class UserIdentity(BaseModel):
    user_id: str
    role: str  # "customer", "employee", or "admin"
    full_name: str = "User"
    email: Optional[str] = None

# Canonical plans authorized per role
ROLE_PLAN_PERMISSIONS: dict[str, Set[str]] = {
    "customer": {"HS-BASIC-001", "HS-GOLD-001", "HS-PREMIUM-001"},
    "employee": {"HS-BASIC-001", "HS-GOLD-001", "HS-PREMIUM-001", "EMP-INS-001"},
    "admin": {"HS-BASIC-001", "HS-GOLD-001", "HS-PREMIUM-001", "EMP-INS-001"}
}

EMPLOYEE_ONLY_PLANS: Set[str] = {"EMP-INS-001"}

# Pre-authorized corporate domain patterns for employee verification
AUTHORIZED_EMPLOYEE_DOMAINS = ("@insurance.corp", "@corporate.internal")

def hash_password(plain_password: str) -> str:
    """Hash plaintext password using bcrypt with salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.error(f"Error checking password: {e}")
        return False

def register_user(
    email: str,
    password: str,
    requested_role: str = "customer",
    full_name: Optional[str] = None,
    device_info: str = ""
) -> tuple[dict, str, str, Optional[str]]:
    """
    Registers a new user, hashes password, enforces employee protection,
    issues a short-lived access JWT and rotating opaque refresh token,
    and returns (user_record, access_token, refresh_token, message).
    """
    clean_email = email.strip().lower()
    existing = sqlite_db.get_user_by_email(clean_email)
    if existing:
        logger.warning(f"Registration rejected: duplicate email '{clean_email}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists. Please log in."
        )

    # Server-enforced role protection:
    req_role = requested_role.strip().lower()
    if req_role == "admin":
        logger.warning(f"Registration attempt with restricted 'admin' role rejected for email '{clean_email}'")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator accounts cannot be created via public registration. Contact system governance."
        )

    # 2. Corporate domain validation for employee role
    effective_role = "customer"
    is_approved = 1
    notice_message = None

    if req_role == "employee":
        if any(clean_email.endswith(d) for d in AUTHORIZED_EMPLOYEE_DOMAINS):
            effective_role = "employee"
            is_approved = 1
            notice_message = "Corporate employee identity verified."
        else:
            effective_role = "customer"
            is_approved = 0
            notice_message = (
                "Employee role registration submitted. For security governance, "
                "standard customer access is granted pending administrative verification."
            )
            logger.info(f"User {clean_email} requested employee role; assigned customer access pending approval.")
    else:
        effective_role = "customer"
        is_approved = 1

    pw_hash = hash_password(password)
    display_name = full_name.strip() if full_name and full_name.strip() else ("Employee Staff" if effective_role == "employee" else "Customer Member")

    user_record = sqlite_db.create_user(
        email=clean_email,
        password_hash=pw_hash,
        requested_role=req_role,
        effective_role=effective_role,
        is_approved=is_approved,
        full_name=display_name
    )

    # Generate JWT access token
    access_token, _ = jwt_service.create_access_token(user_record["user_id"], user_record["role"])

    # Generate opaque refresh token and persist hash
    raw_refresh_token = jwt_service.generate_refresh_token()
    refresh_hash = jwt_service.hash_token(raw_refresh_token)
    sqlite_db.save_refresh_token(
        token_hash=refresh_hash,
        user_id=user_record["user_id"],
        role=user_record["role"],
        duration_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
        device_info=device_info
    )

    # Also maintain backward-compatible opaque session during transition
    sqlite_db.create_session(user_record["user_id"], user_record["role"], token=access_token)

    logger.info(f"User registered successfully: id={user_record['user_id']} role={user_record['role']}")
    return user_record, access_token, raw_refresh_token, notice_message

def authenticate_user(
    email: str,
    password: str,
    device_info: str = ""
) -> tuple[dict, str, str]:
    """
    Authenticates user credentials against SQLite database.
    Generates a 15-minute access JWT and rotating opaque refresh token.
    Returns (user_dict, access_token, refresh_token) on success or raises 401.
    """
    clean_email = email.strip().lower()
    user = sqlite_db.get_user_by_email(clean_email)
    if not user:
        logger.warning(f"Authentication failed: user not found '{clean_email}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not verify_password(password, user["password_hash"]):
        logger.warning(f"Authentication failed: invalid password for '{clean_email}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # Generate JWT access token
    access_token, _ = jwt_service.create_access_token(user["user_id"], user["effective_role"])

    # Generate opaque refresh token and persist hash
    raw_refresh_token = jwt_service.generate_refresh_token()
    refresh_hash = jwt_service.hash_token(raw_refresh_token)
    sqlite_db.save_refresh_token(
        token_hash=refresh_hash,
        user_id=user["user_id"],
        role=user["effective_role"],
        duration_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
        device_info=device_info
    )

    # Also maintain backward-compatible opaque session during transition
    sqlite_db.create_session(user["user_id"], user["effective_role"], token=access_token)

    logger.info(f"User authenticated successfully: id={user['user_id']} role={user['effective_role']}")
    return user, access_token, raw_refresh_token

def refresh_user_tokens(refresh_token: str, device_info: str = "") -> tuple[dict, str, str]:
    """
    Validates rotating refresh token against SQLite registry.
    Detects replay attacks / token reuse and revokes entire token family if breached.
    Rotates old token, issues a brand new opaque refresh token, and generates a new 15-minute access JWT.
    """
    clean_token = refresh_token.strip()
    token_hash = jwt_service.hash_token(clean_token)
    record = sqlite_db.get_refresh_token_record(token_hash)

    if not record:
        logger.warning("Refresh token not found or invalid.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token. Please log in again."
        )

    # REUSE DETECTION: If token was already revoked, someone is replaying a consumed token
    if record.get("revoked_at") is not None:
        user_id = record["user_id"]
        logger.critical(f"SECURITY ALERT: Refresh token reuse detected for user {user_id}! Revoking all sessions.")
        sqlite_db.revoke_all_user_refresh_tokens(user_id)
        sqlite_db.record_audit_event(
            action="token_reuse_detected",
            actor_id=user_id,
            actor_role=record.get("role", "unknown"),
            target_resource="/api/auth/refresh",
            outcome="SECURITY_ALERT",
            details={
                "reason": "Rotated refresh token presented a second time",
                "token_id": record.get("token_id"),
                "replaced_by": record.get("replaced_by_token_id")
            }
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Security alert: Token reuse detected. All active sessions have been invalidated for security. Please log in again."
        )

    # EXPIRATION CHECK
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromisoformat(record["expires_at"])
    if now > expires_at:
        sqlite_db.revoke_refresh_token(token_hash)
        logger.info(f"Refresh token expired for user {record['user_id']}.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired. Please log in again."
        )

    # APPROVAL CHECK
    if not record.get("is_approved", 1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is pending verification."
        )

    # ROTATION: Revoke old token and insert new token
    new_refresh_token = jwt_service.generate_refresh_token()
    new_token_hash = jwt_service.hash_token(new_refresh_token)
    sqlite_db.rotate_refresh_token(
        old_token_hash=token_hash,
        new_token_hash=new_token_hash,
        user_id=record["user_id"],
        role=record["role"],
        duration_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
        device_info=device_info
    )

    # Generate new access JWT
    new_access_token, _ = jwt_service.create_access_token(
        user_id=record["user_id"],
        role=record["effective_role"]
    )
    sqlite_db.create_session(record["user_id"], record["effective_role"], token=new_access_token)

    logger.info(f"Successfully rotated refresh token and issued new JWT for user {record['user_id']}")
    return record, new_access_token, new_refresh_token

def logout_session(token: Optional[str] = None, refresh_token: Optional[str] = None) -> bool:
    """
    Invalidates active session:
    - Revokes refresh token in SQLite.
    - Blacklists access token JTI until its natural expiry.
    - Deletes legacy opaque session if presented.
    """
    success = False
    if refresh_token:
        ref_hash = jwt_service.hash_token(refresh_token.strip())
        if sqlite_db.revoke_refresh_token(ref_hash):
            success = True

    if token:
        clean_token = token.strip()
        if clean_token.startswith("sess_"):
            if sqlite_db.delete_session(clean_token):
                success = True
        else:
            try:
                secret = get_jwt_secret()
                payload = jwt.decode(
                    clean_token,
                    secret,
                    algorithms=[settings.JWT_ALGORITHM],
                    options={"verify_exp": False}
                )
                jti = payload.get("jti")
                exp = payload.get("exp")
                sub = payload.get("sub", "unknown")
                if jti and exp:
                    exp_iso = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()
                    sqlite_db.revoke_access_token_jti(jti, sub, exp_iso)
                    success = True
            except Exception as e:
                logger.warning(f"Could not parse access token JTI for revocation: {e}")

    return success

class AuthorizationService:
    """
    Centralized server-side authorization service enforcing strict
    role-based access control (RBAC) across plans, search scopes, and citations.
    """

    @staticmethod
    def get_authorized_plans(role: str) -> Set[str]:
        """Return the immutable set of canonical plan IDs authorized for a role."""
        return ROLE_PLAN_PERMISSIONS.get(role.lower().strip(), set())

    @staticmethod
    def is_plan_authorized(role: str, plan_id: str) -> bool:
        """Check if a specific canonical plan ID is accessible by the role."""
        authorized = AuthorizationService.get_authorized_plans(role)
        return plan_id in authorized

    @staticmethod
    def filter_authorized_plans(role: str, requested_plans: list[str]) -> list[str]:
        """
        Intersect requested plans with the role's authorized plans.
        Never grants access to unauthorized plans even if requested by client.
        """
        authorized = AuthorizationService.get_authorized_plans(role)
        return [p for p in requested_plans if p in authorized]

    @staticmethod
    def validate_plan_access(role: str, plan_id: str) -> None:
        """Raise 403 Forbidden if the user role is not authorized for the plan."""
        if not AuthorizationService.is_plan_authorized(role, plan_id):
            logger.warning(f"Unauthorized access attempt: role='{role}' attempted to access plan='{plan_id}'")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Your account role ({role}) does not have permission to access plan '{plan_id}'."
            )

    @staticmethod
    def sanitize_retrieved_chunks(role: str, chunks: list[dict]) -> list[dict]:
        """
        Secondary defense layer: Filter out any chunks that belong to unauthorized plans
        before fusion, parent expansion, or response generation.
        """
        authorized = AuthorizationService.get_authorized_plans(role)
        sanitized = []
        for c in chunks:
            pid = c.get("plan_id") or c.get("metadata", {}).get("plan_id")
            if pid in authorized:
                sanitized.append(c)
            else:
                logger.warning(f"Security filter caught unauthorized chunk from plan {pid} for role {role}")
        return sanitized

def get_current_user(request: Request) -> UserIdentity:
    """
    Extracts and verifies authenticated user identity from request.
    Priority 1: Bearer token or X-Session-Token.
      - If starts with 'sess_', validates legacy Phase 1 opaque session.
      - If standard JWT, validates signature, algorithm, expiration, and JTI revocation.
    Priority 2: Derives trusted profile from SQLite.
    Fails closed with 401 Unauthorized if missing, expired, or invalid.
    """
    auth_header = request.headers.get("Authorization", "").strip()
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "X-Session-Token" in request.headers:
        token = request.headers["X-Session-Token"].strip()

    if token:
        # 1. Enforce session expiration if recorded in SQLite store
        sess_record = sqlite_db.get_raw_session(token)
        if sess_record:
            expires_at = datetime.fromisoformat(sess_record["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                sqlite_db.delete_session(token)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication session has expired. Please log in again."
                )

        # 2. Legacy opaque session support (Option B backward compatibility)
        if token.startswith("sess_"):
            session = sqlite_db.get_session(token)
            if not session:
                logger.warning("Invalid or expired session token presented.")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired authentication session. Please log in again."
                )
            return UserIdentity(
                user_id=session["user_id"],
                role=session["effective_role"],
                full_name=session["full_name"] or "User",
                email=session["email"]
            )

        # JWT Access Token Verification
        payload = jwt_service.decode_access_token(token)
        jti = payload.get("jti")
        if jti and sqlite_db.is_access_token_jti_revoked(jti):
            logger.warning(f"Revoked JWT access token presented: jti={jti}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token has been revoked. Please log in again."
            )

        user_id = payload.get("sub")
        db_user = sqlite_db.get_user_by_id(user_id)
        if not db_user:
            logger.warning(f"User '{user_id}' not found in database for valid JWT.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account no longer exists."
            )

        return UserIdentity(
            user_id=db_user["user_id"],
            role=db_user["effective_role"],
            full_name=db_user["full_name"] or "User",
            email=db_user["email"]
        )

    # Unauthenticated requests rejected
    logger.warning(f"Unauthenticated request to protected endpoint '{request.url.path}'.")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please provide a valid session token."
    )

def require_admin_user(request: Request) -> UserIdentity:
    """
    Enforces server-side administrator authorization.
    Returns HTTP 401 for unauthenticated requests,
    and HTTP 403 for authenticated non-administrators.
    """
    auth_header = request.headers.get("Authorization", "").strip()
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "X-Session-Token" in request.headers:
        token = request.headers["X-Session-Token"].strip()

    if not token and "X-User-Role" in request.headers:
        client_role = request.headers["X-User-Role"].lower().strip()
        sqlite_db.record_audit_event(
            action="admin_endpoint_forbidden",
            actor_id=request.headers.get("X-User-Id", "unknown"),
            actor_role=client_role,
            target_resource=str(request.url.path),
            outcome="FORBIDDEN",
            details={"reason": f"Role '{client_role}' lacks admin privileges"}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrator privileges required."
        )

    user = get_current_user(request)
    if user.role != "admin":
        sqlite_db.record_audit_event(
            action="admin_endpoint_forbidden",
            actor_id=user.user_id,
            actor_email=user.email,
            actor_role=user.role,
            target_resource=str(request.url.path),
            outcome="FORBIDDEN",
            details={"reason": f"Authenticated user has role '{user.role}', not 'admin'"}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrator privileges required."
        )
    return user

def require_employee_user(request: Request) -> UserIdentity:
    """
    Enforces server-side employee-only authorization.
    Rejects unauthenticated requests with HTTP 401.
    Rejects authenticated non-employees (customers, admins) with HTTP 403 Forbidden.
    """
    auth_header = request.headers.get("Authorization", "").strip()
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "X-Session-Token" in request.headers:
        token = request.headers["X-Session-Token"].strip()

    if not token and "X-User-Role" in request.headers:
        client_role = request.headers["X-User-Role"].lower().strip()
        sqlite_db.record_audit_event(
            action="claim_predictor_forbidden",
            actor_id=request.headers.get("X-User-Id", "unknown"),
            actor_role=client_role,
            target_resource=str(request.url.path),
            outcome="FORBIDDEN",
            details={"reason": f"Role '{client_role}' lacks employee privileges"}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Employee role authorization required to access the Claim Predictor."
        )

    user = get_current_user(request)
    if user.role != "employee":
        sqlite_db.record_audit_event(
            action="claim_predictor_forbidden",
            actor_id=user.user_id,
            actor_email=user.email,
            actor_role=user.role,
            target_resource=str(request.url.path),
            outcome="FORBIDDEN",
            details={"reason": f"Authenticated user has role '{user.role}', not 'employee'"}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Employee role authorization required to access the Claim Predictor."
        )
    return user
