from pydantic import BaseModel, Field, model_validator
from typing import Optional
from backend.app.services.generation_service import SourceCitation

class CreateConversationRequest(BaseModel):
    selected_plan_id: Optional[str] = Field(None, description="Canonical Plan ID (e.g., HS-BASIC-001, HS-GOLD-001, HS-PREMIUM-001)")
    plan_id: Optional[str] = Field(None, description="Alternative Plan ID key for client convenience")

    @model_validator(mode="after")
    def resolve_plan_id(self):
        plan = self.selected_plan_id or self.plan_id
        if not plan:
            raise ValueError("selected_plan_id is required.")
        self.selected_plan_id = plan
        return self

class MessageRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="User question regarding insurance policy terms")

class MessageResponse(BaseModel):
    message_id: str
    role: str
    content: str
    timestamp: str
    citations: list[SourceCitation] = []
    effective_scope: list[str] = []
    is_comparison: bool = False
    is_clarification: bool = False
    contains_unverified_notice: bool = False
    suggested_follow_ups: list[str] = []

class ConversationResponse(BaseModel):
    conversation_id: str
    user_id: str
    role: str
    selected_plan_id: str
    created_at: str
    updated_at: str
    messages: list[MessageResponse] = []

class ConversationSummaryItem(BaseModel):
    conversation_id: str
    selected_plan_id: str
    created_at: str
    updated_at: str
    message_count: int = 0
    preview_title: str = "New Insurance Conversation"

class SendMessageResponse(BaseModel):
    message: MessageResponse
    scope_resolution: dict
    retrieval_diagnostics: dict
