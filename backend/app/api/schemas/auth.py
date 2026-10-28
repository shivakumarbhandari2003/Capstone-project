import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

class SignupRequest(BaseModel):
    email: str = Field(..., description="Valid user email address")
    password: str = Field(..., min_length=8, description="Password (at least 8 characters)")
    role: str = Field("customer", description="Requested role: customer or employee")
    full_name: Optional[str] = Field("Member", description="User full display name")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if not re.match(EMAIL_REGEX, clean):
            raise ValueError("Invalid email address format.")
        return clean

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return v

    @field_validator("role")
    @classmethod
    def validate_role_type(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ["customer", "employee"]:
            raise ValueError("Role must be either 'customer' or 'employee'.")
        return clean

class LoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if not re.match(EMAIL_REGEX, clean):
            raise ValueError("Invalid email address format.")
        return clean

class UserPayload(BaseModel):
    user_id: str
    email: str
    role: str
    full_name: str
    is_approved: bool = True
    requested_role: Optional[str] = None

class AuthResponse(BaseModel):
    token: str
    user: UserPayload
    message: Optional[str] = None

class UserProfileResponse(BaseModel):
    user_id: str
    email: str
    role: str
    full_name: str
    is_approved: bool
    governance_status: Optional[str] = "active"
    last_login: Optional[str] = None
    created_at: Optional[str] = None
    account_status: Optional[str] = "ACTIVE"
    eligibility_status: Optional[str] = "NOT_STARTED"
    eligibility_outcome: Optional[str] = None
    assessment_completed_at: Optional[str] = None
    selected_plan_id: Optional[str] = None
    selected_plan_name: Optional[str] = None
    plan_selection_status: Optional[str] = None
    is_confirmed: Optional[bool] = False
    confirmation_status: Optional[str] = None
    confirmed_at: Optional[str] = None
    confirmed_plan_id: Optional[str] = None
    authorized_plans: Optional[list[str]] = None
