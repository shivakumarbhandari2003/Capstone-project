from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

class ClaimPredictionInput(BaseModel):
    """
    Validated input features strictly derived from claim_predictor_package/app.py.
    """
    age: int = Field(default=45, ge=18, le=70, description="Policyholder Age between 18 and 70")
    days_hospitalised: int = Field(default=4, ge=0, le=365, description="Days Hospitalised between 0 and 365")
    icu_days: int = Field(default=1, ge=0, le=5, description="ICU Days between 0 and 5")
    procedures_claimed: int = Field(default=2, ge=0, le=50, description="Procedures Claimed between 0 and 50")
    prior_daycare_claims_year: int = Field(default=0, ge=0, le=20, description="Prior Daycare Claims in past year between 0 and 20")
    extended_stay_flag: Literal[0, 1] = Field(default=0, description="Extended Stay Flag: 0 for No, 1 for Yes")
    plan: Literal["Basic", "Gold", "Premium"] = Field(default="Gold", description="Plan Tier: Basic, Gold, or Premium")
    pre_existing: Literal["yes", "no"] = Field(default="no", description="Pre-existing condition: yes or no")
    claim_type: Literal["Hospitalisation", "Major surgery", "Medical management", "Other surgery"] = Field(
        default="Major surgery",
        description="Claim Type category"
    )
    documents_complete: Literal["yes", "no"] = Field(default="yes", description="Documents complete: yes or no")
    conversation_id: Optional[str] = Field(default=None, description="Optional active conversation session ID to attach grounded RAG explanation")

class ClaimPredictionResponse(BaseModel):
    """
    Structured model prediction and RAG response.
    """
    request_id: str
    prediction: float
    formatted_prediction: str
    output_units: str = "INR (Rs.)"
    validated_inputs: Dict[str, Any]
    message: Optional[Dict[str, Any]] = None
    assistant_message: Optional[Dict[str, Any]] = None
    user_message: Optional[Dict[str, Any]] = None
    retrieval_diagnostics: Optional[Dict[str, Any]] = None

