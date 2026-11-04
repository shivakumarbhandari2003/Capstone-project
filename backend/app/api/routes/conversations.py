from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from backend.app.api.schemas.conversations import (
    CreateConversationRequest,
    ConversationResponse,
    ConversationSummaryItem,
    MessageRequest,
    SendMessageResponse,
    MessageResponse
)
from backend.app.services.rag_orchestrator import RAGOrchestrator
from backend.app.services.auth_service import UserIdentity, AuthorizationService
from backend.app.api.deps import get_rag_orchestrator, get_auth_user
from backend.app.core.logging_config import logger

router = APIRouter(prefix="/conversations", tags=["Conversations & RAG Chat"])

@router.get("", response_model=list[ConversationSummaryItem])
def list_conversations(
    plan_id: Optional[str] = None,
    user: UserIdentity = Depends(get_auth_user),
    orchestrator: RAGOrchestrator = Depends(get_rag_orchestrator)
):
    """
    List past conversation history for the authenticated user and authorized role,
    excluding empty chats and unauthorized plans.
    """
    try:
        items = orchestrator.conversation_manager.list_conversations_for_user(
            user_id=user.user_id,
            role=user.role,
            plan_id=plan_id
        )
        return [ConversationSummaryItem(**item) for item in items]
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        return []


from datetime import datetime, timezone
from backend.app.db.sqlite_manager import sqlite_db

@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    req: CreateConversationRequest,
    user: UserIdentity = Depends(get_auth_user),
    orchestrator: RAGOrchestrator = Depends(get_rag_orchestrator)
):
    """
    Create a fresh plan-scoped conversation session.
    Enforces server-side eligibility assessment and active plan selection before conversation initialization.
    Fails closed with 403 Forbidden if unassessed, ineligible, plan mismatched, or unauthorized.
    """
    # 0. Enforce role-based plan authorization first
    if not AuthorizationService.is_plan_authorized(user.role, req.selected_plan_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Plan '{req.selected_plan_id}' is not authorized for role '{user.role}'."
        )

    # For customer users, enforce eligibility assessment and plan selection workflow
    if user.role == "customer":
        # 1. User must have a completed, current, non-expired eligibility assessment
        assessment = sqlite_db.get_current_assessment_for_user(user.user_id)
        if not assessment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Eligibility assessment required. Please complete an underwriting evaluation before starting a conversation."
            )
        if assessment.get("status") != "COMPLETED" or assessment.get("outcome") != "ELIGIBLE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Eligibility assessment outcome is '{assessment.get('outcome')}'. Policy conversations are restricted to verified eligible applicants."
            )
        expires_at = assessment.get("expires_at")
        if expires_at:
            now_iso = datetime.now(timezone.utc).isoformat()
            if expires_at < now_iso:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your eligibility assessment has expired. Please re-evaluate your eligibility before starting a conversation."
                )

        # 2. User must have an active or confirmed plan selection
        confirmed_selection = sqlite_db.get_confirmed_plan_selection_for_user(user.user_id)
        active_selection = confirmed_selection or sqlite_db.get_active_plan_selection_for_user(user.user_id)
        if not active_selection:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No active plan selection found. Please select an eligible plan before initiating policy consultation."
            )
        is_user_confirmed = bool(confirmed_selection) or (active_selection.get("status") == "CONFIRMED")
        if not is_user_confirmed:
            if active_selection.get("selected_plan_id") != req.selected_plan_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requested plan '{req.selected_plan_id}' does not match your active selected plan '{active_selection.get('selected_plan_id')}'."
                )
            if active_selection.get("assessment_id") != assessment.get("assessment_id"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Active plan selection is not associated with your current eligibility assessment."
                )

        # 3. Requested plan must be in the assessment's qualifying plans
        qualifying_plans = assessment.get("qualifying_plans", [])
        if req.selected_plan_id not in qualifying_plans:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requested plan '{req.selected_plan_id}' is not covered by your qualified plan tiers: {qualifying_plans}."
            )

    try:
        session = orchestrator.conversation_manager.create_conversation(
            user_id=user.user_id,
            role=user.role,
            selected_plan_id=req.selected_plan_id
        )
        return ConversationResponse(**session.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    user: UserIdentity = Depends(get_auth_user),
    orchestrator: RAGOrchestrator = Depends(get_rag_orchestrator)
):
    """Retrieve an existing authorized conversation session enforcing RBAC and user boundary."""
    session = orchestrator.conversation_manager.get_conversation(
        conversation_id=conversation_id,
        user_id=user.user_id,
        role=user.role
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found or access denied for role '{user.role}'."
        )
    return ConversationResponse(**session.model_dump())


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
def get_conversation_messages(
    conversation_id: str,
    user: UserIdentity = Depends(get_auth_user),
    orchestrator: RAGOrchestrator = Depends(get_rag_orchestrator)
):
    """Retrieve turn history for an authorized conversation."""
    session = orchestrator.conversation_manager.get_conversation(
        conversation_id=conversation_id,
        user_id=user.user_id,
        role=user.role
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found or access denied for role '{user.role}'."
        )

    return [MessageResponse(**m.model_dump()) for m in session.messages]

@router.post("/{conversation_id}/messages", response_model=SendMessageResponse)
def send_message(
    conversation_id: str,
    req: MessageRequest,
    user: UserIdentity = Depends(get_auth_user),
    orchestrator: RAGOrchestrator = Depends(get_rag_orchestrator)
):
    """
    Process a user message:
    1. Resolve plan scope (selected plan by default, explicit comparison if authorized)
    2. Hybrid retrieve authorized evidence
    3. Generate grounded answer with citations
    4. Persist turn state and return
    """
    try:
        result = orchestrator.process_query(
            conversation_id=conversation_id,
            user=user,
            query=req.query
        )
        return SendMessageResponse(
            message=MessageResponse(**result["message"]),
            scope_resolution=result["scope_resolution"],
            retrieval_diagnostics=result["retrieval_diagnostics"]
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error in send_message: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to process message: {str(e)}")
