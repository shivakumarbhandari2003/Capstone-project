from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from backend.app.api.deps import get_auth_user
from backend.app.services.auth_service import UserIdentity, AuthorizationService
from backend.app.services.eligibility_model_service import (
    eligibility_model_service,
    ApplicantEvaluationInput,
    EligibilityModelResult
)
from backend.app.db.sqlite_manager import sqlite_db
from backend.app.registry.plans import PLAN_REGISTRY
from backend.app.core.logging_config import logger

router = APIRouter(prefix="/eligibility", tags=["Eligibility Assessment & Underwriting"])

class PlanSelectionPayload(BaseModel):
    selected_plan_id: str = Field(..., description="Target plan ID (e.g. HS-GOLD-001)")
    assessment_id: Optional[str] = Field(None, description="Optional assessment ID; defaults to current active assessment")

class PlanConfirmationPayload(BaseModel):
    plan_id: str = Field(..., description="Confirmed plan ID (e.g. HS-GOLD-001)")

class AgentContactPayload(BaseModel):
    assessment_id: Optional[str] = Field(None, description="Reference assessment ID")
    full_name: str = Field(..., min_length=2, max_length=100, description="Applicant full legal name")
    email: str = Field(..., min_length=5, max_length=100, description="Contact email address")
    phone: Optional[str] = Field(None, max_length=30, description="Contact phone number")
    preferred_contact_method: str = Field("EMAIL", description="'EMAIL' or 'PHONE'")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional context or questions")

@router.get("/health")
def get_model_health():
    """
    Readiness and availability check for the eligibility machine learning model package.
    """
    ready = eligibility_model_service.is_ready()
    return {
        "status": "ready" if ready else "unavailable",
        "model_loaded": ready,
        "metadata": eligibility_model_service.get_metadata() if ready else None
    }

@router.post("/assess")
def assess_applicant_eligibility(
    profile: ApplicantEvaluationInput,
    current_user: UserIdentity = Depends(get_auth_user)
):
    """
    Evaluates applicant data against the authentic Gradient Boosting model pipeline.
    Validates features, calculates BMI, performs ML prediction, and persists assessment.
    Server-side rule: Enforces that completed assessments cannot be re-run.
    """
    # 1. Enforce server-side one-time assessment rule
    existing_completed = sqlite_db.get_completed_assessment_for_user(current_user.user_id)
    if existing_completed:
        logger.info(f"User '{current_user.user_id}' already has completed assessment '{existing_completed['assessment_id']}'. Returning saved result.")
        return {
            "assessment_id": existing_completed["assessment_id"],
            "outcome": existing_completed["outcome"],
            "status": existing_completed["status"],
            "probability_eligible": existing_completed.get("confidence_score") or 0.0,
            "bmi": existing_completed.get("input_provenance", {}).get("bmi", 22.0),
            "qualifying_plans": existing_completed.get("qualifying_plans", []),
            "confidence_score": existing_completed.get("confidence_score") or 0.0,
            "reason_codes": existing_completed.get("reason_codes", []),
            "review_status": existing_completed.get("review_status", "NONE"),
            "explanation": "Existing completed eligibility assessment retrieved. Re-evaluation is not permitted under account policy.",
            "input_summary": existing_completed.get("input_provenance", {}),
            "completed_at": existing_completed.get("completed_at") or existing_completed.get("created_at"),
            "already_completed": True
        }

    try:
        result = eligibility_model_service.evaluate(profile, user_role=current_user.role)
        
        # Persist assessment in SQLite
        assessment_id = sqlite_db.save_eligibility_assessment(
            user_id=current_user.user_id,
            status=result.status,
            outcome=result.outcome,
            qualifying_plans=result.qualifying_plans,
            input_provenance=result.input_summary,
            model_id=result.model_id,
            model_version=result.model_version,
            confidence_score=result.probability_eligible,
            reason_codes=result.reason_codes,
            review_status=result.review_status
        )

        # Audit event
        sqlite_db.record_audit_event(
            action="eligibility_assessed",
            actor_id=current_user.user_id,
            actor_email=current_user.email,
            actor_role=current_user.role,
            target_resource=assessment_id,
            outcome="SUCCESS" if result.outcome == "ELIGIBLE" else "REVIEW_REQUIRED",
            details={
                "outcome": result.outcome,
                "probability_eligible": result.probability_eligible,
                "bmi": result.bmi,
                "qualifying_plans": result.qualifying_plans
            }
        )

        return {
            "assessment_id": assessment_id,
            "outcome": result.outcome,
            "status": result.status,
            "probability_eligible": result.probability_eligible,
            "bmi": result.bmi,
            "qualifying_plans": result.qualifying_plans,
            "confidence_score": result.probability_eligible,
            "reason_codes": result.reason_codes,
            "review_status": result.review_status,
            "explanation": result.explanation,
            "input_summary": result.input_summary
        }
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid applicant features: {str(val_err)}"
        )
    except Exception as e:
        sqlite_db.record_audit_event(
            action="eligibility_assessment_failed",
            actor_id=current_user.user_id,
            actor_email=current_user.email,
            actor_role=current_user.role,
            target_resource="eligibility_model",
            outcome="ERROR",
            details={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Eligibility model evaluation failed: {str(e)}"
        )

@router.get("/me")
def get_my_current_assessment(current_user: UserIdentity = Depends(get_auth_user)):
    """
    Retrieves the authenticated user's current active eligibility assessment and active plan selection.
    """
    assessment = sqlite_db.get_current_assessment_for_user(current_user.user_id)
    active_selection = sqlite_db.get_active_plan_selection_for_user(current_user.user_id)

    if not assessment:
        return {
            "has_assessment": False,
            "assessment": None,
            "active_plan_selection": active_selection
        }

    return {
        "has_assessment": True,
        "assessment": assessment,
        "active_plan_selection": active_selection
    }

@router.post("/select-plan")
def select_plan_with_eligibility(
    payload: PlanSelectionPayload,
    current_user: UserIdentity = Depends(get_auth_user)
):
    """
    Records an active plan selection.
    Enforces that the user has an active ELIGIBLE assessment covering the selected plan,
    and enforces role-based plan authorization.
    """
    # 1. Enforce role-based plan authorization
    authorized_plans = AuthorizationService.get_authorized_plans(current_user.role)
    if payload.selected_plan_id not in authorized_plans:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Plan '{payload.selected_plan_id}' is not authorized for role '{current_user.role}'."
        )

    assessment = sqlite_db.get_completed_assessment_for_user(current_user.user_id) or sqlite_db.get_current_assessment_for_user(current_user.user_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Eligibility assessment required. Please complete eligibility check before selecting a plan."
        )

    if assessment["outcome"] != "ELIGIBLE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Current assessment outcome is '{assessment['outcome']}'. Plan selection is reserved for eligible applicants."
        )

    qualifying_plans = assessment.get("qualifying_plans", [])
    if payload.selected_plan_id not in qualifying_plans:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Plan '{payload.selected_plan_id}' is not in your qualified plans: {qualifying_plans}"
        )

    # Plan selection starts in ACTIVE unconfirmed mode so the user can verify and confirm manually

    selection_id = sqlite_db.save_plan_selection(
        user_id=current_user.user_id,
        assessment_id=assessment["assessment_id"],
        selected_plan_id=payload.selected_plan_id
    )

    sqlite_db.record_audit_event(
        action="plan_selected",
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        actor_role=current_user.role,
        target_resource=payload.selected_plan_id,
        outcome="SUCCESS",
        details={"selection_id": selection_id, "assessment_id": assessment["assessment_id"]}
    )

    plan_info = PLAN_REGISTRY.get(payload.selected_plan_id)
    plan_name = plan_info.plan_name if plan_info else payload.selected_plan_id
    return {
        "selection_id": selection_id,
        "selected_plan_id": payload.selected_plan_id,
        "plan_name": plan_name,
        "status": "ACTIVE",
        "assessment_id": assessment["assessment_id"]
    }

@router.post("/confirm-plan")
def confirm_customer_plan(
    payload: PlanConfirmationPayload,
    current_user: UserIdentity = Depends(get_auth_user)
):
    """
    Persists user confirmation of their selected plan.
    Available for Customer and Employee roles.
    Requires completed eligible assessment and active plan selection matching the plan_id.
    Idempotent: Duplicate submissions return the persisted confirmation state.
    """
    if current_user.role not in {"customer", "employee"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Plan confirmation is exclusively reserved for customer and employee accounts."
        )

    assessment = sqlite_db.get_completed_assessment_for_user(current_user.user_id) or sqlite_db.get_current_assessment_for_user(current_user.user_id)
    if not assessment or assessment.get("outcome") != "ELIGIBLE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A completed eligible assessment is required prior to confirming a policy plan."
        )

    authorized_plans = AuthorizationService.get_authorized_plans(current_user.role)
    if payload.plan_id not in authorized_plans:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan '{payload.plan_id}' is not an authorized policy plan for role '{current_user.role}'."
        )

    active_sel = sqlite_db.get_active_plan_selection_for_user(current_user.user_id)
    if not active_sel or active_sel.get("selected_plan_id") != payload.plan_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active plan selection matches this confirmation request. Please select your plan first."
        )

    confirmed_record = sqlite_db.confirm_customer_plan_selection(current_user.user_id, payload.plan_id)
    if not confirmed_record:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record plan confirmation in persistent store."
        )

    plan_info = PLAN_REGISTRY.get(payload.plan_id)
    plan_name = plan_info.plan_name if plan_info else payload.plan_id

    sqlite_db.record_audit_event(
        action="customer_plan_confirmed",
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        actor_role=current_user.role,
        target_resource=payload.plan_id,
        outcome="SUCCESS",
        details={
            "selection_id": confirmed_record["selection_id"],
            "plan_id": payload.plan_id,
            "confirmed_at": confirmed_record["confirmed_at"]
        }
    )

    return {
        "status": "CONFIRMED",
        "plan_id": payload.plan_id,
        "plan_name": plan_name,
        "selection_id": confirmed_record["selection_id"],
        "confirmed_at": confirmed_record["confirmed_at"],
        "message": f"You have selected the {plan_name} Plan. Agent will contact you soon for document verification."
    }

@router.post("/agent-contact")
def request_agent_contact(
    payload: AgentContactPayload,
    current_user: UserIdentity = Depends(get_auth_user)
):
    """
    Submits a persisted assistance request to connect with a licensed human insurance agent.
    """
    # Verify assessment ownership if assessment_id is provided
    if payload.assessment_id:
        assessment = sqlite_db.get_assessment_by_id(payload.assessment_id)
        if not assessment or assessment.get("user_id") != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: The specified assessment does not belong to the authenticated user."
            )

    try:
        request_id = sqlite_db.save_agent_contact_request(
            user_id=current_user.user_id,
            assessment_id=payload.assessment_id,
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            preferred_contact_method=payload.preferred_contact_method,
            notes=payload.notes
        )

        sqlite_db.record_audit_event(
            action="agent_assistance_requested",
            actor_id=current_user.user_id,
            actor_email=current_user.email,
            actor_role=current_user.role,
            target_resource=request_id,
            outcome="SUCCESS",
            details={
                "request_id": request_id,
                "assessment_id": payload.assessment_id,
                "preferred_contact_method": payload.preferred_contact_method
            }
        )

        return {
            "request_id": request_id,
            "status": "PENDING",
            "message": "Your assistance request has been recorded. A licensed representative will contact you via your preferred method."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit agent assistance request: {str(e)}"
        )
