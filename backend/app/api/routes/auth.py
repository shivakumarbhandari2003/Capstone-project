from fastapi import APIRouter, HTTPException, Depends, Request, status
from backend.app.api.schemas.auth import (
    SignupRequest,
    LoginRequest,
    AuthResponse,
    UserPayload,
    UserProfileResponse
)
from backend.app.services.auth_service import (
    register_user,
    authenticate_user,
    logout_session,
    UserIdentity,
    get_current_user,
    AuthorizationService
)
from backend.app.registry.plans import PLAN_REGISTRY
from backend.app.db.sqlite_manager import sqlite_db
from backend.app.core.logging_config import logger

router = APIRouter(prefix="/auth", tags=["Authentication & User Management"])

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest):
    """
    Registers a new account securely.
    - Hashes password using bcrypt.
    - Role is derived server-side.
    - Returns session token and user profile without exposing sensitive credentials.
    """
    user_record, token, notice = register_user(
        email=req.email,
        password=req.password,
        requested_role=req.role,
        full_name=req.full_name
    )

    return AuthResponse(
        token=token,
        user=UserPayload(
            user_id=user_record["user_id"],
            email=user_record["email"],
            role=user_record["role"],
            full_name=user_record["full_name"],
            is_approved=bool(user_record["is_approved"]),
            requested_role=user_record["requested_role"]
        ),
        message=notice or "Registration successful."
    )

@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest):
    """
    Authenticates email and password against SQLite store.
    Generates a secure session token and returns the authenticated user identity.
    """
    user_record, token = authenticate_user(
        email=req.email,
        password=req.password
    )

    return AuthResponse(
        token=token,
        user=UserPayload(
            user_id=user_record["user_id"],
            email=user_record["email"],
            role=user_record["effective_role"],
            full_name=user_record["full_name"],
            is_approved=bool(user_record["is_approved"]),
            requested_role=user_record["requested_role"]
        ),
        message="Login successful."
    )

@router.post("/logout")
def logout(request: Request):
    """
    Invalidates the active user session token.
    """
    auth_header = request.headers.get("Authorization", "").strip()
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "X-Session-Token" in request.headers:
        token = request.headers["X-Session-Token"].strip()

    if token:
        logout_session(token)

    return {"status": "SUCCESS", "message": "Session invalidated successfully."}

@router.get("/me", response_model=UserProfileResponse)
def get_me(user: UserIdentity = Depends(get_current_user)):
    """
    Retrieves profile and permissions for the currently authenticated session,
    including persisted eligibility status, active plan selection, and confirmation state.
    """
    db_user = sqlite_db.get_user_by_id(user.user_id)
    email = db_user["email"] if db_user else (user.email or f"{user.user_id}@test.local")
    role = db_user["effective_role"] if db_user else user.role
    full_name = db_user["full_name"] if db_user and db_user.get("full_name") else user.full_name
    is_approved = bool(db_user["is_approved"]) if db_user else True
    created_at = db_user["created_at"] if db_user else None
    governance_status = "active" if is_approved else "pending_verification"
    account_status = "ACTIVE" if is_approved else "PENDING_VERIFICATION"

    # Query persistent eligibility assessment
    asmt = sqlite_db.get_completed_assessment_for_user(user.user_id) or sqlite_db.get_current_assessment_for_user(user.user_id)
    eligibility_status = "NOT_STARTED"
    eligibility_outcome = None
    assessment_completed_at = None
    if asmt:
        eligibility_status = asmt.get("status", "NOT_STARTED")
        eligibility_outcome = asmt.get("outcome")
        assessment_completed_at = asmt.get("completed_at") or asmt.get("created_at")

    # Query persistent plan selection & confirmation
    confirmed_sel = sqlite_db.get_confirmed_plan_selection_for_user(user.user_id) if hasattr(sqlite_db, 'get_confirmed_plan_selection_for_user') else None
    active_sel = sqlite_db.get_active_plan_selection_for_user(user.user_id)
    selected_plan_id = None
    selected_plan_name = None
    plan_selection_status = None
    is_confirmed = False
    confirmation_status = "NOT_CONFIRMED"
    confirmed_at = None
    confirmed_plan_id = None

    if confirmed_sel:
        confirmed_plan_id = confirmed_sel.get("selected_plan_id")
        confirmed_at = confirmed_sel.get("confirmed_at")

    if active_sel:
        selected_plan_id = active_sel.get("selected_plan_id")
        plan_obj = PLAN_REGISTRY.get(selected_plan_id)
        selected_plan_name = plan_obj.plan_name if plan_obj else selected_plan_id
        plan_selection_status = active_sel.get("status")
        if active_sel.get("status") == "CONFIRMED":
            is_confirmed = True
            confirmation_status = "CONFIRMED"
            confirmed_at = active_sel.get("confirmed_at")
            confirmed_plan_id = active_sel.get("selected_plan_id")
        elif confirmed_sel and confirmed_plan_id == selected_plan_id:
            is_confirmed = True
            confirmation_status = "CONFIRMED"
        else:
            is_confirmed = False
            confirmation_status = "PENDING_CONFIRMATION"

    authorized_plans = sorted(list(AuthorizationService.get_authorized_plans(role)))

    return UserProfileResponse(
        user_id=user.user_id,
        email=email,
        role=role,
        full_name=full_name,
        is_approved=is_approved,
        governance_status=governance_status,
        created_at=created_at,
        account_status=account_status,
        eligibility_status=eligibility_status,
        eligibility_outcome=eligibility_outcome,
        assessment_completed_at=assessment_completed_at,
        selected_plan_id=selected_plan_id,
        selected_plan_name=selected_plan_name,
        plan_selection_status=plan_selection_status,
        is_confirmed=is_confirmed,
        confirmation_status=confirmation_status,
        confirmed_at=confirmed_at,
        confirmed_plan_id=confirmed_plan_id,
        authorized_plans=authorized_plans
    )
