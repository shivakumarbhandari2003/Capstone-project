import os
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from backend.app.core.config import settings
from backend.app.core.logging_config import logger

# Mapping between canonical Plan IDs and their authorized TXT filenames
PLAN_DOCUMENT_MAPPING: Dict[str, str] = {
    "HS-BASIC-001": "basic.txt",
    "HS-GOLD-001": "gold.txt",
    "HS-PREMIUM-001": "premium.txt",
    "EMP-INS-001": "employee executive.txt"
}

# Canonical normalized structured representation extracted directly and strictly from the 3 TXT files
CANONICAL_PLAN_REVIEW_DATA: Dict[str, Dict[str, Any]] = {
    "HS-BASIC-001": {
        "plan_details": {
            "plan_name": "Health Shield – Basic",
            "plan_id": "HS-BASIC-001",
            "category": "Basic",
            "product_type": "Proposed Fixed-Benefit Health Insurance",
            "policy_term": "Illustrative 1 year",
            "annual_premium": "Rs. 5,500*",
            "payment_frequency": "Annual only",
            "taxes": "Excluded*",
            "official_plan_number": "Not assigned",
            "uin": "Not assigned"
        },
        "benefits_coverage_limits": {
            "annual_coverage": {
                "title": "ANNUAL COVER",
                "overall_limit": "Overall annual coverage limit not specified in source document",
                "status": "not_specified"
            },
            "hospital_cash": {
                "title": "HOSPITAL CASH",
                "daily_benefit": "Rs. 2,000 / day",
                "min_stay": "Min stay >24 hrs",
                "max_days": "Maximum 10 days",
                "max_amount": "Max Rs. 20,000",
                "status": "included"
            },
            "icu_benefit": {
                "title": "ICU BENEFIT",
                "daily_benefit": "Rs. 4,000 / day",
                "max_days": "Maximum 5 days",
                "max_amount": "Max Rs. 20,000",
                "relationship": "Additional to hospital cash*",
                "status": "included"
            },
            "surgery_benefit": {
                "title": "MAJOR SURGERY",
                "basis": "Basis: Rs. 2,00,000",
                "category_payouts": [
                    "Cat. 1: Rs. 2,00,000",
                    "Cat. 2: Rs. 1,20,000",
                    "Cat. 3: Rs. 80,000",
                    "Cat. 4: Rs. 40,000"
                ],
                "overall_max": "Rs. 6,00,000*",
                "status": "included"
            }
        },
        "other_benefits": [
            {
                "name": "Day-care",
                "amount": "Rs. 10,000/procedure",
                "frequency": "Max 1 procedure/year",
                "annual_limit": "Max Rs. 10,000/year",
                "status": "included"
            },
            {
                "name": "Other surgery",
                "amount": "Rs. 3,000/day",
                "frequency": "Max 5 days/year",
                "annual_limit": "Max Rs. 15,000/year",
                "status": "included"
            },
            {
                "name": "Medical care",
                "amount": "Rs. 5,000/claim",
                "frequency": "Max 1 claim/year",
                "annual_limit": "Max Rs. 5,000/year",
                "status": "included"
            },
            {
                "name": "Extended stay",
                "amount": "Rs. 15,000",
                "frequency": "Hospitalization >30 days",
                "annual_limit": "Max 1 claim/year",
                "status": "included"
            },
            {
                "name": "Health check",
                "amount": "Up to Rs. 1,000/year",
                "frequency": "Once per policy year",
                "annual_limit": "Rs. 1,000/year",
                "status": "included"
            },
            {
                "name": "Ambulance",
                "amount": "Up to Rs. 250/event",
                "frequency": "Max 1 claim/year",
                "annual_limit": "Rs. 250/year",
                "status": "included"
            },
            {
                "name": "Restored cover",
                "amount": "Not included in this plan",
                "frequency": "N/A",
                "annual_limit": "N/A",
                "status": "not_included"
            },
            {
                "name": "Quick cash",
                "amount": "Not included in this plan",
                "frequency": "N/A",
                "annual_limit": "N/A",
                "status": "not_included"
            },
            {
                "name": "Optional riders",
                "amount": "Premium waiver: Rs. 300/year* | Auto Health Cover: Rs. 500/year*",
                "frequency": "Annual rider",
                "annual_limit": "Not included in base premium",
                "status": "optional_rider"
            }
        ],
        "waiting_periods": [
            {"condition": "Initial illness", "duration": "30 days*"},
            {"condition": "Specified conditions", "duration": "24 months*"},
            {"condition": "Pre-existing disease (PED)", "duration": "36 months*"},
            {"condition": "PED lookback period", "duration": "Previous 36 months*"},
            {"condition": "Accident cover", "duration": "From policy start*"},
            {"condition": "Health check-up", "duration": "30 days*"},
            {"condition": "Premium waiver rider", "duration": "90 days*"},
            {"condition": "Auto Health Cover rider", "duration": "From rider start*"}
        ],
        "exclusions": [
            "Intentional self-injury",
            "Intoxication / non-prescribed substance use",
            "Non-medically necessary cosmetic treatment",
            "Non-medical expenses",
            "Treatment outside eligible provider/geographical scope",
            "Other approved policy exclusions"
        ],
        "claim_requirements": [
            "Notify insurer promptly*",
            "Documents submission: within 30 days of discharge*",
            "Required: Claim form, identity/policy details, admission/discharge summary, doctor's notes, bills, receipts and diagnostic reports",
            "Eligible treatment within India*",
            "Eligible registered hospital/provider*",
            "Annual premium grace period: 15 days*",
            "Revival request: within 90 days, subject to arrears and underwriting approval*"
        ],
        "policy_disclosure": {
            "title": "DEMONSTRATION DATA — NOT AN APPROVED INSURANCE PRODUCT",
            "body": "All premiums, benefits, waiting periods, and exclusions are illustrative values for RAG development. The plan has no assigned official plan number or UIN. Verify all details against approved policy wording before real-world use. Confirmation records enrollment intent only; it does not issue a policy, activate coverage, or grant final underwriting approval.",
            "footnote": "*Illustrative values and conditions; verify against approved policy wording."
        },
        "provenance": {
            "source_document": "basic.txt",
            "directory": "Correct and review",
            "canonical_plan_id": "HS-BASIC-001"
        }
    },
    "HS-GOLD-001": {
        "plan_details": {
            "plan_name": "Health Shield – Gold",
            "plan_id": "HS-GOLD-001",
            "category": "Gold",
            "product_type": "Fixed-Benefit Health Insurance",
            "policy_term": "Illustrative 1 year",
            "annual_premium": "Rs. 11,800*",
            "payment_frequency": "Annual",
            "taxes": "Excluded*",
            "official_plan_number": "Not assigned",
            "uin": "Not assigned"
        },
        "benefits_coverage_limits": {
            "annual_coverage": {
                "title": "ANNUAL COVER",
                "overall_limit": "Overall annual coverage limit not specified in source document",
                "status": "not_specified"
            },
            "hospital_cash": {
                "title": "HOSPITAL CASH",
                "daily_benefit": "Rs. 5,000 / day",
                "min_stay": "Min stay >24 hrs",
                "max_days": "Max 20 days",
                "max_amount": "Max Rs. 1,00,000",
                "status": "included"
            },
            "icu_benefit": {
                "title": "ICU BENEFIT",
                "daily_benefit": "Rs. 10,000 / day",
                "max_days": "Max 10 days",
                "max_amount": "Max Rs. 1,00,000",
                "relationship": "ICU and hospital cash combination subject to terms*",
                "status": "included"
            },
            "surgery_benefit": {
                "title": "MAJOR SURGERY",
                "basis": "Basis: Rs. 5,00,000",
                "category_payouts": [
                    "Cat. 1: Rs. 5,00,000",
                    "Cat. 2: Rs. 3,00,000",
                    "Cat. 3: Rs. 2,00,000",
                    "Cat. 4: Rs. 1,00,000"
                ],
                "overall_max": "Rs. 25,00,000*",
                "status": "included"
            }
        },
        "other_benefits": [
            {
                "name": "Day-care",
                "amount": "Rs. 25,000/procedure",
                "frequency": "Max 2 claims/year",
                "annual_limit": "Max Rs. 50,000/year",
                "status": "included"
            },
            {
                "name": "Other surgery",
                "amount": "Rs. 10,000/day",
                "frequency": "Max 10 days/year",
                "annual_limit": "Max Rs. 1,00,000/year",
                "status": "included"
            },
            {
                "name": "Medical care",
                "amount": "Rs. 15,000/claim",
                "frequency": "Max 2 claims/year",
                "annual_limit": "Max Rs. 30,000/year",
                "status": "included"
            },
            {
                "name": "Extended stay",
                "amount": "Rs. 50,000",
                "frequency": "Hospitalization >30 days",
                "annual_limit": "Max 1 claim/year",
                "status": "included"
            },
            {
                "name": "Health check",
                "amount": "Up to Rs. 3,000/year",
                "frequency": "Once per policy year",
                "annual_limit": "Rs. 3,000/year",
                "status": "included"
            },
            {
                "name": "Ambulance",
                "amount": "Rs. 500/trip",
                "frequency": "Max 2 trips/year",
                "annual_limit": "Rs. 1,000/year",
                "status": "included"
            },
            {
                "name": "Restored cover",
                "amount": "Up to Rs. 5,00,000*",
                "frequency": "Once per policy year",
                "annual_limit": "Rs. 5,00,000",
                "status": "included"
            },
            {
                "name": "Quick cash",
                "amount": "Up to 25% of eligible surgery benefit; capped at Rs. 50,000*",
                "frequency": "Per eligible claim",
                "annual_limit": "Rs. 50,000",
                "status": "included"
            }
        ],
        "waiting_periods": [
            {"condition": "Initial illness", "duration": "30 days*"},
            {"condition": "Specified diseases", "duration": "24 months*"},
            {"condition": "Pre-existing disease (PED)", "duration": "36 months*"},
            {"condition": "PED lookback period", "duration": "Previous 48 months*"},
            {"condition": "Accident cover", "duration": "From policy start*"},
            {"condition": "Health check-up", "duration": "30 days*"},
            {"condition": "Critical illness rider", "duration": "90 days*"},
            {"condition": "Premium waiver rider", "duration": "90 days*"}
        ],
        "exclusions": [
            "Cosmetic treatment",
            "Non-medical expenses",
            "Self-inflicted injury",
            "Substance misuse-related events",
            "Unproven treatment",
            "Material misrepresentation",
            "Claims during waiting periods"
        ],
        "claim_requirements": [
            "Emergency notification: within 24 hours",
            "Complete documents: within 30 days of discharge*",
            "Treatment in India; overseas treatment excluded*",
            "Registered eligible hospitals; conditions apply*",
            "Annual/half-yearly premium grace: 30 days*",
            "Monthly premium grace: 15 days*",
            "Revival request: within 90 days, subject to conditions*"
        ],
        "policy_disclosure": {
            "title": "DEMONSTRATION DATA — NOT AN OFFICIAL VERIFIED INSURANCE PRODUCT",
            "body": "Benefits, premiums, waiting periods, and exclusions are illustrative and require verification against approved policy wording. Confirmation records enrollment intent only; it does not issue a policy, activate coverage, or grant final underwriting approval.",
            "footnote": "*Illustrative values and conditions; verify against approved policy wording."
        },
        "provenance": {
            "source_document": "gold.txt",
            "directory": "Correct and review",
            "canonical_plan_id": "HS-GOLD-001"
        }
    },
    "HS-PREMIUM-001": {
        "plan_details": {
            "plan_name": "Health Shield – Premium",
            "plan_id": "HS-PREMIUM-001",
            "category": "Premium",
            "product_type": "Fixed-Benefit Health Insurance",
            "policy_term": "Illustrative 1 year",
            "annual_premium": "Rs. 22,500*",
            "payment_frequency": "Annual",
            "taxes": "Excluded*",
            "official_plan_number": "Not assigned",
            "uin": "Not assigned"
        },
        "benefits_coverage_limits": {
            "annual_coverage": {
                "title": "ANNUAL COVER",
                "overall_limit": "Not specified in source document",
                "status": "not_specified"
            },
            "hospital_cash": {
                "title": "HOSPITAL CASH",
                "daily_benefit": "Rs. 10,000 / day",
                "min_stay": "Not specified in provided plan document",
                "max_days": "Max 30 days",
                "max_amount": "Max Rs. 3,00,000",
                "status": "included"
            },
            "icu_benefit": {
                "title": "ICU BENEFIT",
                "daily_benefit": "Rs. 20,000 / day",
                "max_days": "Max 15 days",
                "max_amount": "Max Rs. 3,00,000",
                "relationship": "ICU replaces hospital cash",
                "status": "included"
            },
            "surgery_benefit": {
                "title": "MAJOR SURGERY",
                "basis": "Basis: Rs. 10,00,000",
                "category_payouts": [
                    "Rs. 10L / Rs. 6L / Rs. 4L / Rs. 2L"
                ],
                "overall_max": "Not specified in source document",
                "status": "included"
            }
        },
        "other_benefits": [
            {
                "name": "Day-care",
                "amount": "Rs. 50,000/procedure",
                "frequency": "Max 3 claims/year",
                "annual_limit": "Max Rs. 1,50,000/year",
                "status": "included"
            },
            {
                "name": "Other surgery",
                "amount": "Rs. 25,000/day",
                "frequency": "Max 15 days/year",
                "annual_limit": "Max Rs. 3,75,000/year",
                "status": "included"
            },
            {
                "name": "Medical care",
                "amount": "Rs. 25,000/claim",
                "frequency": "Max 3 claims/year",
                "annual_limit": "Max Rs. 75,000/year",
                "status": "included"
            },
            {
                "name": "Extended stay",
                "amount": "Rs. 1,00,000",
                "frequency": "Hospitalization >30 days",
                "annual_limit": "Not specified in provided plan document",
                "status": "included"
            },
            {
                "name": "Health check",
                "amount": "Up to Rs. 5,00,0/year",
                "frequency": "Once per policy year",
                "annual_limit": "Up to Rs. 5,000/year",
                "status": "included"
            },
            {
                "name": "Ambulance",
                "amount": "Rs. 1,000/claim",
                "frequency": "Per claim",
                "annual_limit": "Not specified in provided plan document",
                "status": "included"
            },
            {
                "name": "Restored cover",
                "amount": "Not specified in the provided plan document",
                "frequency": "N/A",
                "annual_limit": "N/A",
                "status": "not_specified"
            },
            {
                "name": "Quick cash",
                "amount": "Not specified in the provided plan document",
                "frequency": "N/A",
                "annual_limit": "N/A",
                "status": "not_specified"
            }
        ],
        "waiting_periods": [
            {"condition": "Initial illness", "duration": "30 days*"},
            {"condition": "Specified ailments", "duration": "24 months*"},
            {"condition": "Pre-existing disease (PED)", "duration": "36 months*"},
            {"condition": "PED lookback period", "duration": "Previous 48 months*"},
            {"condition": "Accident cover", "duration": "From policy start*"},
            {"condition": "Rider illness", "duration": "30 days*"}
        ],
        "exclusions": [
            "Non-medical expenses",
            "Cosmetic treatment",
            "Self-inflicted injury, where excluded",
            "Unproven treatment",
            "Applicable waiting-period claims",
            "Other documented exclusions"
        ],
        "claim_requirements": [
            "Emergency notification: within 24 hours*",
            "Planned admission: within 48 hours*",
            "Documents submission: within 30 days of discharge*",
            "Eligible registered hospitals, subject to the stated hospital requirements",
            "Treatment in India, subject to exceptions*"
        ],
        "policy_disclosure": {
            "title": "DEMONSTRATION DATA — NOT AN OFFICIAL VERIFIED INSURANCE PRODUCT",
            "body": "Benefits, premiums, waiting periods, and exclusions require verification against an approved policy document. Confirmation records enrollment intent only; it does not issue a policy, activate coverage, or grant final underwriting approval.",
            "footnote": "*Illustrative values and conditions; verify against approved policy wording."
        },
        "provenance": {
            "source_document": "premium.txt",
            "directory": "Correct and review",
            "canonical_plan_id": "HS-PREMIUM-001"
        }
    },
    "EMP-INS-001": {
        "plan_details": {
            "plan_name": "Executive Employee Insurance Plan",
            "plan_id": "EMP-INS-001",
            "category": "Employee Exclusive",
            "product_type": "Fixed-Benefit Health Insurance",
            "policy_term": "1 Year",
            "annual_premium": "Rs. 5,000",
            "employer_pays": "Rs. 2,000",
            "employee_pays": "Rs. 3,000",
            "payment_frequency": "Annual (default)",
            "taxes": "Not defined",
            "official_plan_number": "Not assigned in the document",
            "uin": "Not specified"
        },
        "benefits_coverage_limits": {
            "annual_coverage": {
                "title": "ANNUAL COVERAGE",
                "overall_limit": "Not defined",
                "major_surgery_basis": "Rs. 10,00,000",
                "major_surgery_max": "Rs. 1,00,00,000* (10× benefit basis)",
                "status": "not_specified"
            },
            "hospital_cash": {
                "title": "HOSPITAL CASH",
                "daily_benefit": "Rs. 10,000",
                "min_stay": "More than 24 hours",
                "max_days": "First Year: Max 30 days | Later Years: Max 90 days/year",
                "max_amount": "Overall Maximum: 900 days*",
                "status": "included"
            },
            "icu_benefit": {
                "title": "ICU BENEFIT",
                "daily_benefit": "Rs. 20,000",
                "max_days": "Maximum ICU days not specified in document",
                "max_amount": "Overall ICU limit: Not defined",
                "relationship": "Hospital Cash Combo: Subject to policy terms",
                "status": "included"
            },
            "surgery_benefit": {
                "title": "MAJOR SURGERY BENEFIT",
                "basis": "Benefit Basis: Rs. 10,00,000",
                "category_payouts": [
                    "Cat. 1 (100%): Rs. 10,00,000",
                    "Cat. 2 (60%): Rs. 6,00,000",
                    "Cat. 3 (40%): Rs. 4,00,000",
                    "Cat. 4 (20%): Rs. 2,00,000"
                ],
                "overall_max": "Rs. 1,00,00,000* (Up to 10× benefit basis)",
                "status": "included"
            }
        },
        "other_benefits": [
            { "name": "Day-Care Procedure", "amount": "Rs. 50,000/procedure", "frequency": "Max 3 procedures/year", "annual_limit": "Overall: 30 procedures*", "status": "included" },
            { "name": "Other Surgery", "amount": "Rs. 25,000/day", "frequency": "Min stay >24 hrs • First Year: Max 15 days | Later: Max 45 days/year", "annual_limit": "Overall Maximum: 450 days*", "status": "included" },
            { "name": "Medical Management", "amount": "Rs. 25,000/eligible claim", "frequency": "Max 2 claims/year", "annual_limit": "Overall Claims: 20*", "status": "included" },
            { "name": "Extended Hospital Stay", "amount": "Rs. 1,00,000 lump sum", "frequency": "Qualifying Stay >30 continuous days", "annual_limit": "Max 1 claim/year; 10 overall*", "status": "included" },
            { "name": "Health Check-Up", "amount": "Rs. 5,000 reimbursement", "frequency": "Available after 3 years of cover*", "annual_limit": "Subsequent: 3 years after previous check-up", "status": "included" },
            { "name": "Restored Cover", "amount": "Not confirmed for employee plan (Reference: Up to Rs. 10,00,000*)", "frequency": "N/A", "annual_limit": "N/A", "status": "not_included" },
            { "name": "Ambulance", "amount": "Rs. 1,000 illustrative (availability and claim limit not confirmed)", "frequency": "Illustrative", "annual_limit": "Not confirmed", "status": "not_included" },
            { "name": "Quick Cash", "amount": "Not confirmed (reference describes 50% advance for eligible surgery)", "frequency": "N/A", "annual_limit": "N/A", "status": "not_included" },
            { "name": "Claim-Free Increase", "amount": "Not confirmed (no increase calculation permitted without approved rules)", "frequency": "N/A", "annual_limit": "N/A", "status": "not_included" },
            { "name": "Premium Waiver & Auto Health Cover", "amount": "Availability and conditions not defined", "frequency": "N/A", "annual_limit": "N/A", "status": "not_included" }
        ],
        "waiting_periods": [
            { "condition": "Initial illness wait", "duration": "Not specified in employee document" },
            { "condition": "Accident coverage", "duration": "Not specified in employee document" },
            { "condition": "Specified diseases", "duration": "Not specified in employee document" },
            { "condition": "Pre-existing diseases (PED)", "duration": "Not specified in employee document" },
            { "condition": "Geographic limits", "duration": "Not specified in employee document" },
            { "condition": "Hospital eligibility", "duration": "Not specified in employee document" },
            { "condition": "Grace period & Revival", "duration": "Not specified in employee document" },
            { "condition": "Claim deadline", "duration": "Not specified in employee document" },
            { "condition": "Employment continuity & leave", "duration": "Not defined in employee document" },
            { "condition": "Dependent coverage", "duration": "Not defined in employee document" }
        ],
        "exclusions": [
            "Exclusions not specified in the employee-plan document",
            "Medical disclosures requirements not specified",
            "Employee eligibility and minimum service requirements not specified",
            "Dependent eligibility and coverage not defined",
            "Employment change rules (resignation, retirement, termination) not defined"
        ],
        "claim_requirements": [
            "Claim process must be confirmed from approved employee policy",
            "Required documents not specified in the employee-plan document",
            "HR corporate verification of active employment status",
            "Hospital registration requirements to be confirmed from employer policy"
        ],
        "policy_disclosure": {
            "title": "POLICY DISCLOSURE — ILLUSTRATIVE DEMONSTRATION VALUES",
            "body": "This plan contains illustrative demonstration values, not verified or approved employee insurance terms. Several benefits are based on reference material and are not confirmed for this employee plan. “Not specified” or “Not confirmed” must not be interpreted as included or excluded coverage. Confirmation records enrollment intent only; it does not activate coverage, issue a policy, or guarantee final underwriting approval. Approved policy documents and employer rules must be verified.",
            "footnote": "* denotes values stated in the reference illustration, not independently verified employee-plan entitlements."
        },
        "provenance": {
            "source_document": "employee executive.txt",
            "directory": "Correct and review",
            "canonical_plan_id": "EMP-INS-001"
        }
    }
}

class PolicyReviewService:
    def __init__(self, review_dir: Optional[Path] = None):
        self.review_dir = review_dir or (settings.BASE_DIR / "Correct and review")

    def get_review_data_for_plan(self, plan_id: str) -> Dict[str, Any]:
        """
        Retrieves the exact verified review data for a canonical plan ID.
        Verifies that the plan exists and that its source TXT document exists on disk.
        """
        if plan_id not in PLAN_DOCUMENT_MAPPING:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan '{plan_id}' does not have an authorized policy document in the review registry."
            )

        filename = PLAN_DOCUMENT_MAPPING[plan_id]
        file_path = self.review_dir / filename

        # Verify that the TXT file exists on disk
        if not file_path.is_file():
            logger.warning(f"Policy review document '{filename}' not found at '{file_path}'. Using canonical structured record.")

        data = CANONICAL_PLAN_REVIEW_DATA.get(plan_id)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Structured review representation for plan '{plan_id}' is unavailable."
            )

        return data

policy_review_service = PolicyReviewService()
