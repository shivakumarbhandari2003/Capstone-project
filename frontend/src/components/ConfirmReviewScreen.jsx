import React, { useState, useEffect } from 'react';
import { eligibilityApi } from '../services/eligibilityApi';

// Fallback canonical data sourced strictly and deterministically from basic.txt, gold.txt, and premium.txt
const FALLBACK_PLAN_REVIEW_DATA = {
  'HS-BASIC-001': {
    plan_details: {
      plan_name: 'Health Shield – Basic',
      plan_id: 'HS-BASIC-001',
      category: 'Basic',
      product_type: 'Proposed Fixed-Benefit Health Insurance',
      policy_term: 'Illustrative 1 year',
      annual_premium: 'Rs. 5,500*',
      payment_frequency: 'Annual only',
      taxes: 'Excluded*',
      official_plan_number: 'Not assigned',
      uin: 'Not assigned'
    },
    benefits_coverage_limits: {
      annual_coverage: {
        title: 'ANNUAL COVER',
        overall_limit: 'Overall annual coverage limit not specified in source document',
        status: 'not_specified'
      },
      hospital_cash: {
        title: 'HOSPITAL CASH',
        daily_benefit: 'Rs. 2,000 / day',
        min_stay: 'Min stay >24 hrs',
        max_days: 'Maximum 10 days',
        max_amount: 'Max Rs. 20,000'
      },
      icu_benefit: {
        title: 'ICU BENEFIT',
        daily_benefit: 'Rs. 4,000 / day',
        max_days: 'Maximum 5 days',
        max_amount: 'Max Rs. 20,000',
        relationship: 'Additional to hospital cash*'
      },
      surgery_benefit: {
        title: 'MAJOR SURGERY',
        basis: 'Basis: Rs. 2,00,000',
        category_payouts: [
          'Cat. 1: Rs. 2,00,000',
          'Cat. 2: Rs. 1,20,000',
          'Cat. 3: Rs. 80,000',
          'Cat. 4: Rs. 40,000'
        ],
        overall_max: 'Rs. 6,00,000*'
      }
    },
    other_benefits: [
      { name: 'Day-care', amount: 'Rs. 10,000/procedure', frequency: 'Max 1 procedure/year', annual_limit: 'Max Rs. 10,000/year', status: 'included' },
      { name: 'Other surgery', amount: 'Rs. 3,000/day', frequency: 'Max 5 days/year', annual_limit: 'Max Rs. 15,000/year', status: 'included' },
      { name: 'Medical care', amount: 'Rs. 5,000/claim', frequency: 'Max 1 claim/year', annual_limit: 'Max Rs. 5,000/year', status: 'included' },
      { name: 'Extended stay', amount: 'Rs. 15,000', frequency: 'Hospitalization >30 days', annual_limit: 'Max 1 claim/year', status: 'included' },
      { name: 'Health check', amount: 'Up to Rs. 1,000/year', frequency: 'Once per policy year', annual_limit: 'Rs. 1,000/year', status: 'included' },
      { name: 'Ambulance', amount: 'Up to Rs. 250/event', frequency: 'Max 1 claim/year', annual_limit: 'Rs. 250/year', status: 'included' },
      { name: 'Restored cover', amount: 'Not included in this plan', frequency: 'N/A', annual_limit: 'N/A', status: 'not_included' },
      { name: 'Quick cash', amount: 'Not included in this plan', frequency: 'N/A', annual_limit: 'N/A', status: 'not_included' },
      { name: 'Optional riders', amount: 'Premium waiver: Rs. 300/year* | Auto Health Cover: Rs. 500/year*', frequency: 'Annual rider', annual_limit: 'Not included in base premium', status: 'optional_rider' }
    ],
    waiting_periods: [
      { condition: 'Initial illness', duration: '30 days*' },
      { condition: 'Specified conditions', duration: '24 months*' },
      { condition: 'Pre-existing disease (PED)', duration: '36 months*' },
      { condition: 'PED lookback period', duration: 'Previous 36 months*' },
      { condition: 'Accident cover', duration: 'From policy start*' },
      { condition: 'Health check-up', duration: '30 days*' },
      { condition: 'Premium waiver rider', duration: '90 days*' },
      { condition: 'Auto Health Cover rider', duration: 'From rider start*' }
    ],
    exclusions: [
      'Intentional self-injury',
      'Intoxication / non-prescribed substance use',
      'Non-medically necessary cosmetic treatment',
      'Non-medical expenses',
      'Treatment outside eligible provider/geographical scope',
      'Other approved policy exclusions'
    ],
    claim_requirements: [
      'Notify insurer promptly*',
      'Documents submission: within 30 days of discharge*',
      'Required: Claim form, identity/policy details, admission/discharge summary, doctor\'s notes, bills, receipts and diagnostic reports',
      'Eligible treatment within India*',
      'Eligible registered hospital/provider*',
      'Annual premium grace period: 15 days*',
      'Revival request: within 90 days, subject to arrears and underwriting approval*'
    ]
  },
  'HS-GOLD-001': {
    plan_details: {
      plan_name: 'Health Shield – Gold',
      plan_id: 'HS-GOLD-001',
      category: 'Gold',
      product_type: 'Fixed-Benefit Health Insurance',
      policy_term: 'Illustrative 1 year',
      annual_premium: 'Rs. 11,800*',
      payment_frequency: 'Annual',
      taxes: 'Excluded*',
      official_plan_number: 'Not assigned',
      uin: 'Not assigned'
    },
    benefits_coverage_limits: {
      annual_coverage: {
        title: 'ANNUAL COVER',
        overall_limit: 'Overall annual coverage limit not specified in source document',
        status: 'not_specified'
      },
      hospital_cash: {
        title: 'HOSPITAL CASH',
        daily_benefit: 'Rs. 5,000 / day',
        min_stay: 'Min stay >24 hrs',
        max_days: 'Max 20 days',
        max_amount: 'Max Rs. 1,00,000'
      },
      icu_benefit: {
        title: 'ICU BENEFIT',
        daily_benefit: 'Rs. 10,000 / day',
        max_days: 'Max 10 days',
        max_amount: 'Max Rs. 1,00,000',
        relationship: 'ICU and hospital cash combination subject to terms*'
      },
      surgery_benefit: {
        title: 'MAJOR SURGERY',
        basis: 'Basis: Rs. 5,00,000',
        category_payouts: [
          'Cat. 1: Rs. 5,00,000',
          'Cat. 2: Rs. 3,00,000',
          'Cat. 3: Rs. 2,00,000',
          'Cat. 4: Rs. 1,00,000'
        ],
        overall_max: 'Rs. 25,00,000*'
      }
    },
    other_benefits: [
      { name: 'Day-care', amount: 'Rs. 25,000/procedure', frequency: 'Max 2 claims/year', annual_limit: 'Max Rs. 50,000/year', status: 'included' },
      { name: 'Other surgery', amount: 'Rs. 10,000/day', frequency: 'Max 10 days/year', annual_limit: 'Max Rs. 1,00,000/year', status: 'included' },
      { name: 'Medical care', amount: 'Rs. 15,000/claim', frequency: 'Max 2 claims/year', annual_limit: 'Max Rs. 30,000/year', status: 'included' },
      { name: 'Extended stay', amount: 'Rs. 50,000', frequency: 'Hospitalization >30 days', annual_limit: 'Max 1 claim/year', status: 'included' },
      { name: 'Health check', amount: 'Up to Rs. 3,00,0/year', frequency: 'Once per policy year', annual_limit: 'Rs. 3,000/year', status: 'included' },
      { name: 'Ambulance', amount: 'Rs. 500/trip', frequency: 'Max 2 trips/year', annual_limit: 'Rs. 1,000/year', status: 'included' },
      { name: 'Restored cover', amount: 'Up to Rs. 5,00,000*', frequency: 'Once per policy year', annual_limit: 'Rs. 5,00,000', status: 'included' },
      { name: 'Quick cash', amount: 'Up to 25% of eligible surgery benefit; capped at Rs. 50,000*', frequency: 'Per eligible claim', annual_limit: 'Rs. 50,000', status: 'included' }
    ],
    waiting_periods: [
      { condition: 'Initial illness', duration: '30 days*' },
      { condition: 'Specified diseases', duration: '24 months*' },
      { condition: 'Pre-existing disease (PED)', duration: '36 months*' },
      { condition: 'PED lookback period', duration: 'Previous 48 months*' },
      { condition: 'Accident cover', duration: 'From policy start*' },
      { condition: 'Health check-up', duration: '30 days*' },
      { condition: 'Critical illness rider', duration: '90 days*' },
      { condition: 'Premium waiver rider', duration: '90 days*' }
    ],
    exclusions: [
      'Cosmetic treatment',
      'Non-medical expenses',
      'Self-inflicted injury',
      'Substance misuse-related events',
      'Unproven treatment',
      'Material misrepresentation',
      'Claims during waiting periods'
    ],
    claim_requirements: [
      'Emergency notification: within 24 hours',
      'Complete documents: within 30 days of discharge*',
      'Treatment in India; overseas treatment excluded*',
      'Registered eligible hospitals; conditions apply*',
      'Annual/half-yearly premium grace: 30 days*',
      'Monthly premium grace: 15 days*',
      'Revival request: within 90 days, subject to conditions*'
    ]
  },
  'HS-PREMIUM-001': {
    plan_details: {
      plan_name: 'Health Shield – Premium',
      plan_id: 'HS-PREMIUM-001',
      category: 'Premium',
      product_type: 'Fixed-Benefit Health Insurance',
      policy_term: 'Illustrative 1 year',
      annual_premium: 'Rs. 22,500*',
      payment_frequency: 'Annual',
      taxes: 'Excluded*',
      official_plan_number: 'Not assigned',
      uin: 'Not assigned'
    },
    benefits_coverage_limits: {
      annual_coverage: {
        title: 'ANNUAL COVER',
        overall_limit: 'Not specified in source document',
        status: 'not_specified'
      },
      hospital_cash: {
        title: 'HOSPITAL CASH',
        daily_benefit: 'Rs. 10,000 / day',
        min_stay: 'Not specified in provided plan document',
        max_days: 'Max 30 days',
        max_amount: 'Max Rs. 3,00,000'
      },
      icu_benefit: {
        title: 'ICU BENEFIT',
        daily_benefit: 'Rs. 20,000 / day',
        max_days: 'Max 15 days',
        max_amount: 'Max Rs. 3,00,000',
        relationship: 'ICU replaces hospital cash'
      },
      surgery_benefit: {
        title: 'MAJOR SURGERY',
        basis: 'Basis: Rs. 10,00,000',
        category_payouts: [
          'Rs. 10L / Rs. 6L / Rs. 4L / Rs. 2L'
        ],
        overall_max: 'Not specified in source document'
      }
    },
    other_benefits: [
      { name: 'Day-care', amount: 'Rs. 50,000/procedure', frequency: 'Max 3 claims/year', annual_limit: 'Max Rs. 1,50,000/year', status: 'included' },
      { name: 'Other surgery', amount: 'Rs. 25,000/day', frequency: 'Max 15 days/year', annual_limit: 'Max Rs. 3,75,000/year', status: 'included' },
      { name: 'Medical care', amount: 'Rs. 25,000/claim', frequency: 'Max 3 claims/year', annual_limit: 'Max Rs. 75,000/year', status: 'included' },
      { name: 'Extended stay', amount: 'Rs. 1,00,000', frequency: 'Hospitalization >30 days', annual_limit: 'Not specified in provided plan document', status: 'included' },
      { name: 'Health check', amount: 'Up to Rs. 5,000/year', frequency: 'Once per policy year', annual_limit: 'Up to Rs. 5,000/year', status: 'included' },
      { name: 'Ambulance', amount: 'Rs. 1,000/claim', frequency: 'Per claim', annual_limit: 'Not specified in provided plan document', status: 'included' },
      { name: 'Restored cover', amount: 'Not specified in the provided plan document', frequency: 'N/A', annual_limit: 'N/A', status: 'not_specified' },
      { name: 'Quick cash', amount: 'Not specified in the provided plan document', frequency: 'N/A', annual_limit: 'N/A', status: 'not_specified' }
    ],
    waiting_periods: [
      { condition: 'Initial illness', duration: '30 days*' },
      { condition: 'Specified ailments', duration: '24 months*' },
      { condition: 'Pre-existing disease (PED)', duration: '36 months*' },
      { condition: 'PED lookback period', duration: 'Previous 48 months*' },
      { condition: 'Accident cover', duration: 'From policy start*' },
      { condition: 'Rider illness', duration: '30 days*' }
    ],
    exclusions: [
      'Non-medical expenses',
      'Cosmetic treatment',
      'Self-inflicted injury, where excluded',
      'Unproven treatment',
      'Applicable waiting-period claims',
      'Other documented exclusions'
    ],
    claim_requirements: [
      'Emergency notification: within 24 hours*',
      'Planned admission: within 48 hours*',
      'Documents submission: within 30 days of discharge*',
      'Eligible registered hospitals, subject to the stated hospital requirements',
      'Treatment in India, subject to exceptions*'
    ]
  },
  'EMP-INS-001': {
    plan_details: {
      plan_name: 'Executive Employee Insurance Plan',
      plan_id: 'EMP-INS-001',
      category: 'Employee Exclusive',
      product_type: 'Fixed-Benefit Health Insurance',
      policy_term: '1 Year',
      annual_premium: 'Rs. 5,000',
      employer_pays: 'Rs. 2,000',
      employee_pays: 'Rs. 3,000',
      payment_frequency: 'Annual (default)',
      taxes: 'Not defined',
      official_plan_number: 'Not assigned in the document',
      uin: 'Not specified'
    },
    benefits_coverage_limits: {
      annual_coverage: {
        title: 'ANNUAL COVERAGE',
        overall_limit: 'Not defined',
        major_surgery_basis: 'Rs. 10,00,000',
        major_surgery_max: 'Rs. 1,00,00,000* (10× benefit basis)',
        status: 'not_specified'
      },
      hospital_cash: {
        title: 'HOSPITAL CASH',
        daily_benefit: 'Rs. 10,000 / day',
        min_stay: 'More than 24 hours',
        max_days: 'First Year: Max 30 days | Later: Max 90 days/yr',
        max_amount: 'Overall Maximum: 900 days*'
      },
      icu_benefit: {
        title: 'ICU BENEFIT',
        daily_benefit: 'Rs. 20,000 / day',
        max_days: 'Maximum ICU days not specified in document',
        max_amount: 'Overall ICU limit: Not defined',
        relationship: 'Hospital cash combo: Subject to policy terms'
      },
      surgery_benefit: {
        title: 'MAJOR SURGERY BENEFIT',
        basis: 'Benefit Basis: Rs. 10,00,000',
        category_payouts: [
          'Cat. 1 (100%): Rs. 10,00,000',
          'Cat. 2 (60%): Rs. 6,00,000',
          'Cat. 3 (40%): Rs. 4,00,000',
          'Cat. 4 (20%): Rs. 2,00,000'
        ],
        overall_max: 'Rs. 1,00,00,000* (Up to 10× benefit basis)'
      }
    },
    other_benefits: [
      { name: 'Day-Care Procedure', amount: 'Rs. 50,000/procedure', frequency: 'Max 3 procedures/year', annual_limit: 'Overall: 30 procedures*', status: 'included' },
      { name: 'Other Surgery', amount: 'Rs. 25,000/day', frequency: 'Min stay >24 hrs • Yr 1: Max 15 days | Later: Max 45 days/yr', annual_limit: 'Overall Maximum: 450 days*', status: 'included' },
      { name: 'Medical Management', amount: 'Rs. 25,000/eligible claim', frequency: 'Max 2 claims/year', annual_limit: 'Overall Claims: 20*', status: 'included' },
      { name: 'Extended Hospital Stay', amount: 'Rs. 1,00,000 lump sum', frequency: 'Qualifying Stay >30 continuous days', annual_limit: 'Max 1 claim/year; 10 overall*', status: 'included' },
      { name: 'Health Check-Up', amount: 'Rs. 5,000 reimbursement', frequency: 'Available after 3 years of cover*', annual_limit: 'Subsequent: 3 years after previous check-up', status: 'included' },
      { name: 'Restored Cover', amount: 'Not confirmed for employee plan (Reference: Up to Rs. 10,00,000*)', frequency: 'N/A', annual_limit: 'N/A', status: 'not_included' },
      { name: 'Ambulance', amount: 'Rs. 1,000 illustrative (availability and claim limit not confirmed)', frequency: 'Illustrative', annual_limit: 'Not confirmed', status: 'not_included' },
      { name: 'Quick Cash', amount: 'Not confirmed (reference describes 50% advance for eligible surgery)', frequency: 'N/A', annual_limit: 'N/A', status: 'not_included' },
      { name: 'Claim-Free Increase', amount: 'Not confirmed (no increase calculation permitted without approved rules)', frequency: 'N/A', annual_limit: 'N/A', status: 'not_included' },
      { name: 'Premium Waiver & Auto Health Cover', amount: 'Availability and conditions not defined', frequency: 'N/A', annual_limit: 'N/A', status: 'not_included' }
    ],
    waiting_periods: [
      { condition: 'Initial illness wait', duration: 'Not specified in employee document' },
      { condition: 'Accident coverage', duration: 'Not specified in employee document' },
      { condition: 'Specified diseases', duration: 'Not specified in employee document' },
      { condition: 'Pre-existing diseases (PED)', duration: 'Not specified in employee document' },
      { condition: 'Geographic limits', duration: 'Not specified in employee document' },
      { condition: 'Hospital eligibility', duration: 'Not specified in employee document' },
      { condition: 'Grace period & Revival', duration: 'Not specified in employee document' },
      { condition: 'Claim deadline', duration: 'Not specified in employee document' },
      { condition: 'Employment continuity & leave', duration: 'Not defined in employee document' },
      { condition: 'Dependent coverage', duration: 'Not defined in employee document' }
    ],
    exclusions: [
      'Exclusions not specified in the employee-plan document',
      'Medical disclosures requirements not specified',
      'Employee eligibility and minimum service requirements not specified',
      'Dependent eligibility and coverage not defined',
      'Employment change rules (resignation, retirement, termination) not defined'
    ],
    claim_requirements: [
      'Claim process must be confirmed from approved employee policy',
      'Required documents not specified in the employee-plan document',
      'HR corporate verification of active employment status',
      'Hospital registration requirements to be confirmed from employer policy'
    ]
  }
};

export function ConfirmReviewScreen({
  currentUser,
  selectedPlan,
  assessment,
  onConfirmationSuccess,
  onBackToPlans
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [confirmedState, setConfirmedState] = useState(null);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [reviewData, setReviewData] = useState(null);

  const planId = selectedPlan?.plan_id || 'HS-GOLD-001';
  const activeData = reviewData || FALLBACK_PLAN_REVIEW_DATA[planId] || FALLBACK_PLAN_REVIEW_DATA['HS-GOLD-001'];
  const pDetails = activeData?.plan_details;
  const bLimits = activeData?.benefits_coverage_limits;
  const oBenefits = activeData?.other_benefits || [];
  const wPeriods = activeData?.waiting_periods || [];
  const exclusions = activeData?.exclusions || [];
  const claimReqs = activeData?.claim_requirements || [];

  // Load plan details from backend review endpoint or fallback
  useEffect(() => {
    let isMounted = true;
    async function fetchPlanDetails() {
      try {
        const liveData = await eligibilityApi.getPlanReviewDetails(planId);
        if (isMounted && liveData && liveData.plan_details) {
          setReviewData(liveData);
          return;
        }
      } catch {
        // Fallback to strict canonical structured representation
      }
      if (isMounted) {
        setReviewData(FALLBACK_PLAN_REVIEW_DATA[planId] || FALLBACK_PLAN_REVIEW_DATA['HS-GOLD-001']);
      }
    }
    fetchPlanDetails();
    return () => { isMounted = false; };
  }, [planId]);

  // Sync confirmation state strictly from selectedPlan
  useEffect(() => {
    const isThisPlanConfirmed = Boolean(
      selectedPlan?.is_confirmed === true &&
      selectedPlan?.status === 'CONFIRMED' &&
      selectedPlan?.confirmed_at
    );

    if (isThisPlanConfirmed) {
      setConfirmedState({
        isConfirmed: true,
        confirmedAt: selectedPlan.confirmed_at,
        selectionId: selectedPlan.plan_id || planId,
        planName: pDetails?.plan_name || selectedPlan?.plan_name
      });
    } else {
      setConfirmedState(null);
    }
  }, [selectedPlan, pDetails, planId]);

  const handleConfirmPlan = async () => {
    if (loading || confirmedState?.isConfirmed) return;
    setLoading(true);
    setError(null);

    try {
      const response = await eligibilityApi.confirmPlan(planId);
      const confDate = response.confirmed_at || new Date().toISOString();
      const updatedConf = {
        isConfirmed: true,
        confirmedAt: confDate,
        selectionId: response.selection_id,
        planName: response.plan_name || pDetails.plan_name
      };
      setConfirmedState(updatedConf);
      setShowSuccessModal(true);
      if (onConfirmationSuccess) {
        onConfirmationSuccess(updatedConf, false);
      }
    } catch (err) {
      setError(err.message || 'Plan confirmation could not be persisted. Please check connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleModalClose = () => {
    setShowSuccessModal(false);
  };

  const handleProceedToChat = () => {
    setShowSuccessModal(false);
    if (onConfirmationSuccess) {
      onConfirmationSuccess(confirmedState, true);
    }
  };

  const handlePrintPdf = () => {
    window.print();
  };

  // Dynamic applicant fields
  const applicantName = currentUser?.full_name || 'Not specified in profile';
  const applicantEmail = currentUser?.email || 'Not specified';
  const applicantRole = currentUser?.role
    ? currentUser.role.charAt(0).toUpperCase() + currentUser.role.slice(1)
    : 'Customer';

  const isEligible = assessment?.outcome === 'ELIGIBLE';
  const eligibilityStatusText = assessment?.outcome ? assessment.outcome : 'Pending Assessment';

  const formattedAssessmentDate = assessment?.completed_at || assessment?.created_at
    ? new Date(assessment.completed_at || assessment.created_at).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    : 'Not completed';

  const formattedConfirmationDate = confirmedState?.confirmedAt
    ? new Date(confirmedState.confirmedAt).toLocaleString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    : null;

  // Liquid Glass shared style
  const liquidGlassCardStyle = {
    background: 'linear-gradient(175deg, rgba(255, 255, 255, 0.95) 0%, rgba(248, 250, 252, 0.90) 100%)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1.5px solid rgba(255, 255, 255, 0.95)',
    borderRadius: '22px',
    boxShadow: '0 12px 36px -8px rgba(0, 122, 255, 0.08), 0 2px 8px rgba(0, 0, 0, 0.03), inset 0 1.5px 2px rgba(255, 255, 255, 1)'
  };

  return (
    <div
      className="confirm-review-container"
      style={{
        maxWidth: '1220px',
        margin: '0 auto',
        padding: '16px 20px 48px 20px',
        fontFamily: "var(--font-family, 'BJCree', 'PT Serif', -apple-system, BlinkMacSystemFont, sans-serif)",
        color: '#1D1D1F'
      }}
    >
      {/* Comprehensive Print Stylesheet for flawless multi-page PDF printing */}
      <style>{`
        @media print {
          @page {
            size: A4 portrait;
            margin: 12mm 14mm 14mm 14mm;
          }
          html,
          body,
          #root,
          .app-workspace-root,
          .workspace-main-area,
          .workspace-layout,
          .workspace-col-center,
          .scrollable-page-container,
          .confirm-review-container {
            overflow: visible !important;
            overflow-x: visible !important;
            overflow-y: visible !important;
            height: auto !important;
            min-height: 0 !important;
            max-height: none !important;
            display: block !important;
            position: static !important;
            float: none !important;
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            background: #ffffff !important;
            box-shadow: none !important;
          }
          #root, #root * {
            overflow: visible !important;
          }
          .app-header,
          header,
          .workspace-col-left,
          .process-sidebar,
          .sidebar-top-header,
          .workspace-sidebar,
          aside,
          .chat-actions-sidebar,
          .profile-drawer,
          .confirm-action-bar,
          .auth-submit-btn,
          .print-hide {
            display: none !important;
          }
          .confirm-review-container {
            max-width: 100% !important;
            width: 100% !important;
            padding: 0 !important;
            margin: 0 !important;
            background: #ffffff !important;
            box-shadow: none !important;
          }
          .print-header-brand {
            display: block !important;
            border-top: 3.5px solid #007aff !important;
            border-bottom: 1.5px solid #cbd5e1 !important;
            padding: 8px 0 !important;
            margin-bottom: 16px !important;
          }
          .print-footer-brand {
            display: flex !important;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid #cbd5e1 !important;
            padding-top: 8px !important;
            margin-top: 24px !important;
            font-size: 9.5px !important;
            color: #64748b !important;
          }
          .confirm-print-card {
            break-inside: avoid !important;
            page-break-inside: avoid !important;
            margin-bottom: 14px !important;
            background: #ffffff !important;
            border: 1.2px solid #cbd5e1 !important;
            border-radius: 12px !important;
            box-shadow: none !important;
            backdrop-filter: none !important;
            -webkit-backdrop-filter: none !important;
          }
          .confirm-print-row {
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
            gap: 14px !important;
            margin-bottom: 14px !important;
          }
          .confirm-print-row > .confirm-print-card {
            margin-bottom: 0 !important;
          }
          .benefits-limits-grid {
            display: grid !important;
            grid-template-columns: repeat(4, 1fr) !important;
            gap: 10px !important;
          }
          .exclusions-claims-grid {
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
            gap: 16px !important;
          }
        }
      `}</style>

      {/* Official Print Header: Visible ONLY in print output */}
      <div className="print-header-brand" style={{ display: 'none' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '4px' }}>
          <div>
            <h1 style={{ fontSize: '18px', fontWeight: 800, margin: '0 0 2px 0', color: '#0F172A', letterSpacing: '-0.02em' }}>
              AI HEALTH INSURANCE ASSISTANT
            </h1>
            <div style={{ fontSize: '11px', color: '#475569', fontWeight: 600 }}>
              Official Policy Review &amp; Verification Schedule
            </div>
          </div>
          <div style={{ textAlign: 'right', fontSize: '10px', color: '#059669', fontWeight: 700 }}>
            <div>CONFIRMED ENROLLMENT RECORD</div>
            <div style={{ color: '#64748b', fontWeight: 500 }}>
              {confirmedState?.selectionId ? `ID: ${confirmedState.selectionId}` : 'CONF-REC-001'}
            </div>
          </div>
        </div>
      </div>

      {/* Clean Formal Heading */}
      <div style={{ marginBottom: '22px' }}>
        <h2
          style={{
            fontFamily: "'PT Serif', 'BJCree', serif",
            fontSize: '30px',
            fontWeight: 800,
            color: '#1D1D1F',
            margin: 0,
            letterSpacing: '-0.02em',
            lineHeight: 1.2
          }}
        >
          CONFIRM &amp; REVIEW SELECTED POLICY
        </h2>
      </div>

      {/* Confirmation Status Banner (if confirmed) */}
      {confirmedState?.isConfirmed && (
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(5, 150, 105, 0.08) 100%)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1.5px solid rgba(16, 185, 129, 0.45)',
            borderRadius: '16px',
            padding: '14px 20px',
            marginBottom: '22px',
            boxShadow: '0 8px 24px -6px rgba(16, 185, 129, 0.2), inset 0 1px 2px rgba(255, 255, 255, 0.9)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                color: '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '18px',
                fontWeight: 800,
                boxShadow: '0 4px 12px rgba(16, 185, 129, 0.35)'
              }}
            >
              ✓
            </div>
            <div>
              <div style={{ fontSize: '15px', fontWeight: 800, color: '#065F46' }}>
                Policy Selection Confirmed &amp; Locked
              </div>
              <div style={{ fontSize: '13px', color: '#047857', fontWeight: 500 }}>
                {formattedConfirmationDate ? `Confirmed on ${formattedConfirmationDate}` : 'Recorded in persistent store'} • Document verification agent initiated.
              </div>
            </div>
          </div>
          <span
            style={{
              padding: '6px 14px',
              borderRadius: '9999px',
              background: '#10B981',
              color: '#FFFFFF',
              fontSize: '12.5px',
              fontWeight: 700,
              letterSpacing: '0.02em',
              boxShadow: '0 2px 8px rgba(16, 185, 129, 0.35)'
            }}
          >
            ✓ Confirmed
          </span>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div
          style={{
            background: 'rgba(239, 68, 68, 0.08)',
            border: '1.2px solid rgba(239, 68, 68, 0.35)',
            borderRadius: '14px',
            padding: '12px 18px',
            color: '#B91C1C',
            fontSize: '14px',
            fontWeight: 600,
            marginBottom: '22px',
            backdropFilter: 'blur(16px)'
          }}
        >
          {error}
        </div>
      )}

      {/* FIRST ROW: TWO SIDE-BY-SIDE LIQUID GLASS CARDS (01 CUSTOMER DETAILS & 02 SELECTED PLAN) */}
      <div
        className="confirm-print-row"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))',
          gap: '20px',
          marginBottom: '22px'
        }}
      >
        {/* Left Card: 01 CUSTOMER DETAILS */}
        <div
          className="confirm-print-card"
          style={{
            ...liquidGlassCardStyle,
            padding: '24px 26px',
            display: 'flex',
            flexDirection: 'column'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1.2px solid rgba(214, 214, 216, 0.75)', paddingBottom: '12px', marginBottom: '16px' }}>
            <span
              style={{
                fontSize: '11.5px',
                fontWeight: 800,
                color: 'var(--color-primary, #007AFF)',
                background: 'rgba(0, 122, 255, 0.1)',
                border: '1px solid rgba(0, 122, 255, 0.25)',
                padding: '2px 8px',
                borderRadius: '6px',
                letterSpacing: '0.05em'
              }}
            >
              01
            </span>
            <h3 style={{ fontSize: '16px', fontWeight: 800, color: '#1D1D1F', margin: 0, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
              CUSTOMER / EMPLOYEE DETAILS
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '14.5px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(241, 245, 249, 0.9)', paddingBottom: '8px' }}>
              <span style={{ color: '#1D1D1F', fontWeight: 600 }}>Full Name</span>
              <span style={{ fontWeight: 800, color: '#1D1D1F', fontSize: '15px' }}>{applicantName}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(241, 245, 249, 0.9)', paddingBottom: '8px' }}>
              <span style={{ color: '#1D1D1F', fontWeight: 600 }}>Email</span>
              <span style={{ fontWeight: 700, color: '#1D1D1F' }}>{applicantEmail}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(241, 245, 249, 0.9)', paddingBottom: '8px' }}>
              <span style={{ color: '#1D1D1F', fontWeight: 600 }}>Role</span>
              <span style={{ fontWeight: 700, color: '#1D1D1F' }}>{applicantRole}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(241, 245, 249, 0.9)', paddingBottom: '8px' }}>
              <span style={{ color: '#1D1D1F', fontWeight: 600 }}>Eligibility</span>
              <span
                style={{
                  fontWeight: 800,
                  fontSize: '13px',
                  color: isEligible ? '#059669' : '#D97706',
                  background: isEligible ? 'rgba(16, 185, 129, 0.14)' : 'rgba(217, 119, 6, 0.12)',
                  border: isEligible ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(217, 119, 6, 0.35)',
                  padding: '3px 12px',
                  borderRadius: '9999px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                {isEligible ? '✓ ELIGIBLE (Qualified)' : eligibilityStatusText}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: '#1D1D1F', fontWeight: 600 }}>Assessment Date</span>
              <span style={{ fontWeight: 700, color: '#1D1D1F' }}>{formattedAssessmentDate}</span>
            </div>
          </div>
        </div>

        {/* Right Card: 02 SELECTED PLAN */}
        <div
          className="confirm-print-card"
          style={{
            ...liquidGlassCardStyle,
            padding: '24px 26px',
            display: 'flex',
            flexDirection: 'column'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1.2px solid rgba(214, 214, 216, 0.75)', paddingBottom: '12px', marginBottom: '16px' }}>
            <span
              style={{
                fontSize: '11.5px',
                fontWeight: 800,
                color: 'var(--color-primary, #007AFF)',
                background: 'rgba(0, 122, 255, 0.1)',
                border: '1px solid rgba(0, 122, 255, 0.25)',
                padding: '2px 8px',
                borderRadius: '6px',
                letterSpacing: '0.05em'
              }}
            >
              02
            </span>
            <h3 style={{ fontSize: '16px', fontWeight: 800, color: '#1D1D1F', margin: 0, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
              SELECTED PLAN
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px 18px', fontSize: '14px' }}>
            <div>
              <span style={{ color: '#1D1D1F', display: 'block', fontSize: '12.5px', fontWeight: 600, marginBottom: '2px' }}>Plan Name</span>
              <span style={{ fontWeight: 800, color: 'var(--color-primary, #007AFF)', fontSize: '15.5px' }}>{pDetails.plan_name}</span>
            </div>
            <div>
              <span style={{ color: '#1D1D1F', display: 'block', fontSize: '12.5px', fontWeight: 600, marginBottom: '2px' }}>Plan ID</span>
              <span style={{ fontWeight: 800, color: '#1D1D1F' }}>{pDetails.plan_id}</span>
            </div>
            <div>
              <span style={{ color: '#1D1D1F', display: 'block', fontSize: '12.5px', fontWeight: 600, marginBottom: '2px' }}>Category</span>
              <span style={{ fontWeight: 700, color: '#1D1D1F' }}>{pDetails.category}</span>
            </div>
            <div>
              <span style={{ color: '#1D1D1F', display: 'block', fontSize: '12.5px', fontWeight: 600, marginBottom: '2px' }}>Product Type</span>
              <span style={{ fontWeight: 700, color: '#1D1D1F' }}>{pDetails.product_type}</span>
            </div>
            <div>
              <span style={{ color: '#1D1D1F', display: 'block', fontSize: '12.5px', fontWeight: 600, marginBottom: '2px' }}>Policy Term</span>
              <span style={{ fontWeight: 700, color: '#1D1D1F' }}>{pDetails.policy_term}</span>
            </div>
            <div>
              <span style={{ color: '#1D1D1F', display: 'block', fontSize: '12.5px', fontWeight: 600, marginBottom: '2px' }}>Annual Premium</span>
              <span style={{ fontWeight: 800, color: '#1D1D1F', fontSize: '15.5px' }}>
                {pDetails.annual_premium}
                {pDetails.employer_pays && (
                  <span style={{ fontSize: '12px', fontWeight: 600, color: '#475569', marginLeft: '6px', display: 'block' }}>
                    (Employer: {pDetails.employer_pays} | Employee: {pDetails.employee_pays})
                  </span>
                )}
              </span>
            </div>
            <div>
              <span style={{ color: '#1D1D1F', display: 'block', fontSize: '12.5px', fontWeight: 600, marginBottom: '2px' }}>Payment / Taxes</span>
              <span style={{ fontWeight: 700, color: '#1D1D1F' }}>{pDetails.payment_frequency} | {pDetails.taxes}</span>
            </div>
            <div>
              <span style={{ color: '#1D1D1F', display: 'block', fontSize: '12.5px', fontWeight: 600, marginBottom: '2px' }}>Selection Status</span>
              <span
                style={{
                  fontWeight: 800,
                  fontSize: '12px',
                  color: confirmedState?.isConfirmed ? '#059669' : '#0284C7',
                  background: confirmedState?.isConfirmed ? 'rgba(16, 185, 129, 0.14)' : 'rgba(2, 132, 199, 0.12)',
                  border: confirmedState?.isConfirmed ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid rgba(2, 132, 199, 0.3)',
                  padding: '3px 10px',
                  borderRadius: '6px',
                  display: 'inline-block'
                }}
              >
                {confirmedState?.isConfirmed ? '✓ CONFIRMED' : 'ACTIVE SELECTION'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* SECOND ROW: 03 BENEFITS & COVERAGE LIMITS (4 CARDS IN A SINGLE HORIZONTAL ROW) */}
      <div
        className="confirm-print-card"
        style={{
          ...liquidGlassCardStyle,
          padding: '24px 26px',
          marginBottom: '22px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1.2px solid rgba(214, 214, 216, 0.75)', paddingBottom: '12px', marginBottom: '18px' }}>
          <span
            style={{
              fontSize: '11.5px',
              fontWeight: 800,
              color: 'var(--color-primary, #007AFF)',
              background: 'rgba(0, 122, 255, 0.1)',
              border: '1px solid rgba(0, 122, 255, 0.25)',
              padding: '2px 8px',
              borderRadius: '6px',
              letterSpacing: '0.05em'
            }}
          >
            03
          </span>
          <h3 style={{ fontSize: '16.5px', fontWeight: 800, color: '#1D1D1F', margin: 0, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
            BENEFITS &amp; COVERAGE LIMITS
          </h3>
        </div>

        <div
          className="benefits-limits-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '16px'
          }}
        >
          {/* CARD 1: ANNUAL COVERAGE */}
          <div
            style={{
              background: 'rgba(255, 255, 255, 0.75)',
              backdropFilter: 'blur(16px)',
              border: '1.2px solid rgba(214, 214, 216, 0.9)',
              borderRadius: '16px',
              padding: '16px 14px',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 4px 14px rgba(0, 0, 0, 0.02), inset 0 1px 1px #ffffff'
            }}
          >
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#1D1D1F', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '8px' }}>
              ANNUAL COVER
            </div>
            <div style={{ fontSize: '13.5px', color: '#1D1D1F', fontWeight: 600, lineHeight: 1.5, flex: 1 }}>
              {bLimits?.annual_coverage?.overall_limit || 'Overall annual coverage limit not specified in source document'}
            </div>
          </div>

          {/* CARD 2: HOSPITAL CASH */}
          <div
            style={{
              background: 'rgba(255, 255, 255, 0.75)',
              backdropFilter: 'blur(16px)',
              border: '1.2px solid rgba(214, 214, 216, 0.9)',
              borderRadius: '16px',
              padding: '16px 14px',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 4px 14px rgba(0, 0, 0, 0.02), inset 0 1px 1px #ffffff'
            }}
          >
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#1D1D1F', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>
              HOSPITAL CASH
            </div>
            <div style={{ fontSize: '17px', fontWeight: 800, color: 'var(--color-primary, #007AFF)', marginBottom: '6px' }}>
              {bLimits?.hospital_cash?.daily_benefit}
            </div>
            <div style={{ fontSize: '13px', color: '#1D1D1F', fontWeight: 500, lineHeight: 1.5 }}>
              <div>• {bLimits?.hospital_cash?.min_stay}</div>
              <div>• {bLimits?.hospital_cash?.max_days}</div>
              <div>• {bLimits?.hospital_cash?.max_amount}</div>
            </div>
          </div>

          {/* CARD 3: ICU BENEFIT */}
          <div
            style={{
              background: 'rgba(255, 255, 255, 0.75)',
              backdropFilter: 'blur(16px)',
              border: '1.2px solid rgba(214, 214, 216, 0.9)',
              borderRadius: '16px',
              padding: '16px 14px',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 4px 14px rgba(0, 0, 0, 0.02), inset 0 1px 1px #ffffff'
            }}
          >
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#1D1D1F', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>
              ICU BENEFIT
            </div>
            <div style={{ fontSize: '17px', fontWeight: 800, color: 'var(--color-primary, #007AFF)', marginBottom: '6px' }}>
              {bLimits?.icu_benefit?.daily_benefit}
            </div>
            <div style={{ fontSize: '13px', color: '#1D1D1F', fontWeight: 500, lineHeight: 1.5 }}>
              <div>• {bLimits?.icu_benefit?.max_days}</div>
              <div>• {bLimits?.icu_benefit?.max_amount}</div>
              {bLimits?.icu_benefit?.relationship && (
                <div style={{ color: '#1D1D1F', fontWeight: 700, marginTop: '2px' }}>
                  • {bLimits.icu_benefit.relationship}
                </div>
              )}
            </div>
          </div>

          {/* CARD 4: MAJOR SURGERY */}
          <div
            style={{
              background: 'rgba(255, 255, 255, 0.75)',
              backdropFilter: 'blur(16px)',
              border: '1.2px solid rgba(214, 214, 216, 0.9)',
              borderRadius: '16px',
              padding: '16px 14px',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 4px 14px rgba(0, 0, 0, 0.02), inset 0 1px 1px #ffffff'
            }}
          >
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#1D1D1F', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>
              MAJOR SURGERY
            </div>
            <div style={{ fontSize: '15px', fontWeight: 800, color: '#1D1D1F', marginBottom: '6px' }}>
              {bLimits?.surgery_benefit?.basis}
            </div>
            <div style={{ fontSize: '13px', color: '#1D1D1F', fontWeight: 500, lineHeight: 1.5 }}>
              {Array.isArray(bLimits?.surgery_benefit?.category_payouts) ? (
                bLimits.surgery_benefit.category_payouts.map((cp, idx) => (
                  <div key={idx}>• {cp}</div>
                ))
              ) : (
                <div>• {bLimits?.surgery_benefit?.category_payouts}</div>
              )}
              {bLimits?.surgery_benefit?.overall_max && (
                <div style={{ color: '#1D1D1F', fontWeight: 700, marginTop: '2px' }}>
                  Overall: {bLimits.surgery_benefit.overall_max}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* THIRD ROW: TWO SIDE-BY-SIDE SECTIONS (04 OTHER BENEFITS & 05 WAITING PERIODS) */}
      <div
        className="confirm-print-row"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))',
          gap: '20px',
          marginBottom: '22px'
        }}
      >
        {/* Left Section: 04 OTHER BENEFITS */}
        <div
          className="confirm-print-card"
          style={{
            ...liquidGlassCardStyle,
            padding: '24px 26px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1.2px solid rgba(214, 214, 216, 0.75)', paddingBottom: '12px', marginBottom: '16px' }}>
            <span
              style={{
                fontSize: '11.5px',
                fontWeight: 800,
                color: 'var(--color-primary, #007AFF)',
                background: 'rgba(0, 122, 255, 0.1)',
                border: '1px solid rgba(0, 122, 255, 0.25)',
                padding: '2px 8px',
                borderRadius: '6px',
                letterSpacing: '0.05em'
              }}
            >
              04
            </span>
            <h3 style={{ fontSize: '16.5px', fontWeight: 800, color: '#1D1D1F', margin: 0, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
              OTHER BENEFITS
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '14px' }}>
            {oBenefits.map((item, index) => {
              const isNotIncluded = item.status === 'not_included';
              const isNotSpecified = item.status === 'not_specified';
              const isRider = item.status === 'optional_rider';

              return (
                <div
                  key={index}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    borderBottom: index < oBenefits.length - 1 ? '1px solid rgba(241, 245, 249, 0.9)' : 'none',
                    paddingBottom: '8px'
                  }}
                >
                  <div style={{ flex: 1, paddingRight: '12px' }}>
                    <span style={{ fontWeight: 800, color: '#1D1D1F', fontSize: '14.5px' }}>{item.name}</span>
                    {item.frequency && item.frequency !== 'N/A' && (
                      <span style={{ fontSize: '13px', color: '#1D1D1F', fontWeight: 500, display: 'block', marginTop: '2px' }}>
                        {item.frequency} {item.annual_limit && item.annual_limit !== 'N/A' ? `• ${item.annual_limit}` : ''}
                      </span>
                    )}
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    {isNotIncluded ? (
                      <span style={{ color: '#1D1D1F', fontSize: '13px', fontStyle: 'italic', fontWeight: 500 }}>
                        Not included in this plan
                      </span>
                    ) : isNotSpecified ? (
                      <span style={{ color: '#1D1D1F', fontSize: '13px', fontStyle: 'italic', fontWeight: 500 }}>
                        Not specified in the provided plan document
                      </span>
                    ) : isRider ? (
                      <span style={{ color: '#D97706', fontSize: '13.5px', fontWeight: 700 }}>
                        {item.amount}
                      </span>
                    ) : (
                      <span style={{ color: '#1D1D1F', fontWeight: 800, fontSize: '14.5px' }}>
                        {item.amount}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Section: 05 WAITING PERIODS */}
        <div
          className="confirm-print-card"
          style={{
            ...liquidGlassCardStyle,
            padding: '24px 26px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1.2px solid rgba(214, 214, 216, 0.75)', paddingBottom: '12px', marginBottom: '16px' }}>
            <span
              style={{
                fontSize: '11.5px',
                fontWeight: 800,
                color: 'var(--color-primary, #007AFF)',
                background: 'rgba(0, 122, 255, 0.1)',
                border: '1px solid rgba(0, 122, 255, 0.25)',
                padding: '2px 8px',
                borderRadius: '6px',
                letterSpacing: '0.05em'
              }}
            >
              05
            </span>
            <h3 style={{ fontSize: '16.5px', fontWeight: 800, color: '#1D1D1F', margin: 0, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
              WAITING PERIODS
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '14px' }}>
            {wPeriods.map((wp, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  borderBottom: idx < wPeriods.length - 1 ? '1px solid rgba(241, 245, 249, 0.9)' : 'none',
                  paddingBottom: '8px'
                }}
              >
                <span style={{ color: '#1D1D1F', fontWeight: 600 }}>{wp.condition}</span>
                <span
                  style={{
                    fontWeight: 800,
                    color: '#1D1D1F',
                    background: 'rgba(255, 255, 255, 0.9)',
                    border: '1px solid rgba(214, 214, 216, 0.9)',
                    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
                    padding: '3px 12px',
                    borderRadius: '6px',
                    fontSize: '13.5px'
                  }}
                >
                  {wp.duration}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* FOURTH ROW: 06 EXCLUSIONS & CLAIM REQUIREMENTS */}
      <div
        className="confirm-print-card"
        style={{
          ...liquidGlassCardStyle,
          padding: '24px 26px',
          marginBottom: '26px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1.2px solid rgba(214, 214, 216, 0.75)', paddingBottom: '12px', marginBottom: '16px' }}>
          <span
            style={{
              fontSize: '11.5px',
              fontWeight: 800,
              color: 'var(--color-primary, #007AFF)',
              background: 'rgba(0, 122, 255, 0.1)',
              border: '1px solid rgba(0, 122, 255, 0.25)',
              padding: '2px 8px',
              borderRadius: '6px',
              letterSpacing: '0.05em'
            }}
          >
            06
          </span>
          <h3 style={{ fontSize: '16.5px', fontWeight: 800, color: '#1D1D1F', margin: 0, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
            EXCLUSIONS &amp; CLAIM REQUIREMENTS
          </h3>
        </div>

        <div
          className="exclusions-claims-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
            gap: '26px'
          }}
        >
          {/* Exclusions Column */}
          <div>
            <h4 style={{ fontSize: '14px', fontWeight: 800, color: '#1D1D1F', margin: '0 0 10px 0', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
              Exclusions
            </h4>
            <ul style={{ margin: 0, paddingLeft: '20px', color: '#1D1D1F', fontSize: '13.5px', lineHeight: 1.65, fontWeight: 500 }}>
              {exclusions.map((item, idx) => (
                <li key={idx} style={{ marginBottom: '6px' }}>{item}</li>
              ))}
            </ul>
          </div>

          {/* Claim Requirements Column */}
          <div>
            <h4 style={{ fontSize: '14px', fontWeight: 800, color: '#1D1D1F', margin: '0 0 10px 0', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
              Claim Requirements
            </h4>
            <ul style={{ margin: 0, paddingLeft: '20px', color: '#1D1D1F', fontSize: '13.5px', lineHeight: 1.65, fontWeight: 500 }}>
              {claimReqs.map((item, idx) => (
                <li key={idx} style={{ marginBottom: '6px' }}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* FOOTER ACTIONS: BOTH BUTTONS SIDE-BY-SIDE ON THE RIGHT */}
      <div
        className="confirm-action-bar"
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          gap: '14px',
          paddingTop: '6px'
        }}
      >
        {/* Sole Print / Save as PDF button */}
        <button
          type="button"
          onClick={handlePrintPdf}
          style={{
            background: 'linear-gradient(135deg, #0284c7 0%, #007aff 100%)',
            color: '#ffffff',
            border: 'none',
            borderRadius: '9999px',
            padding: '12px 24px',
            minHeight: '44px',
            fontSize: '14px',
            fontWeight: 700,
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: '0 4px 14px rgba(0, 122, 255, 0.25)',
            transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)'
          }}
          title="Print review report or Save as PDF"
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-1.5px)';
            e.currentTarget.style.boxShadow = '0 6px 20px rgba(0, 122, 255, 0.35)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = '0 4px 14px rgba(0, 122, 255, 0.25)';
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="6 9 6 2 18 2 18 9"></polyline>
            <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path>
            <rect x="6" y="14" width="12" height="8"></rect>
          </svg>
          <span>Print / Save as PDF</span>
        </button>

        {/* Change Plan Button (Shown only if not yet confirmed) */}
        {!confirmedState?.isConfirmed && (
          <button
            type="button"
            onClick={onBackToPlans}
            style={{
              background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.95) 0%, rgba(245, 245, 247, 0.85) 100%)',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              border: '1.2px solid rgba(214, 214, 216, 0.95)',
              borderRadius: '9999px',
              padding: '12px 24px',
              minHeight: '44px',
              fontSize: '14px',
              fontWeight: 700,
              color: '#1D1D1F',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              boxShadow: '0 2px 8px rgba(0, 0, 0, 0.04), inset 0 1px 1px #ffffff',
              transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--color-primary, #007AFF)';
              e.currentTarget.style.transform = 'translateY(-1.5px)';
              e.currentTarget.style.boxShadow = '0 6px 16px rgba(0, 122, 255, 0.15), inset 0 1px 1px #ffffff';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'rgba(214, 214, 216, 0.95)';
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.04), inset 0 1px 1px #ffffff';
            }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            <span>Change Selected Plan</span>
          </button>
        )}

        {/* Continue to Chat Button when Confirmed */}
        {confirmedState?.isConfirmed && (
          <button
            type="button"
            onClick={handleProceedToChat}
            className="auth-submit-btn"
            style={{
              margin: 0,
              padding: '12px 28px',
              minHeight: '44px',
              borderRadius: '9999px',
              background: 'linear-gradient(135deg, #0284c7 0%, #007aff 100%)',
              boxShadow: '0 4px 14px rgba(0, 122, 255, 0.35)',
              border: '1px solid rgba(0, 122, 255, 0.9)',
              color: '#FFFFFF',
              fontSize: '14.5px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <span>Continue to Policy Chat</span>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12"></line>
              <polyline points="12 5 19 12 12 19"></polyline>
            </svg>
          </button>
        )}

        {/* Confirm Plan Button / Confirmed Badge */}
        <button
          type="button"
          onClick={handleConfirmPlan}
          disabled={loading || Boolean(confirmedState?.isConfirmed)}
          className="auth-submit-btn"
          style={{
            margin: 0,
            padding: '12px 28px',
            minHeight: '44px',
            borderRadius: '9999px',
            background: confirmedState?.isConfirmed
              ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
              : 'var(--btn-liquid-gradient, linear-gradient(180deg, #007AFF 0%, #0066D6 100%))',
            boxShadow: confirmedState?.isConfirmed
              ? '0 6px 20px rgba(16, 185, 129, 0.4), inset 0 1px 1px rgba(255, 255, 255, 0.45)'
              : 'var(--btn-liquid-shadow, 0 4px 14px rgba(0, 122, 255, 0.35))',
            border: confirmedState?.isConfirmed
              ? '1px solid rgba(16, 185, 129, 0.9)'
              : '1px solid rgba(0, 122, 255, 0.9)',
            color: '#FFFFFF',
            fontSize: '14.5px',
            fontWeight: 700,
            cursor: confirmedState?.isConfirmed || loading ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          {loading ? (
            <span>Processing Confirmation...</span>
          ) : confirmedState?.isConfirmed ? (
            <>
              <span>✓ Confirmed (Policy Locked)</span>
            </>
          ) : (
            <>
              <span>✓ Confirm Policy Selection</span>
            </>
          )}
        </button>
      </div>

      {/* Official Print Footer: Visible ONLY in print output */}
      <div className="print-footer-brand" style={{ display: 'none' }}>
        <div>
          Official Policy Review Schedule • Generated for Customer Records • AI Health Insurance Assistant
        </div>
        <div>
          {pDetails.plan_name} ({pDetails.plan_id})
        </div>
      </div>

      {/* Fluid Glass Popup Window (Matching EligibilityScreen and standard app modal) */}
      {showSuccessModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 9999,
            background: 'rgba(255, 255, 255, 0.2)',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
            animation: 'authCardFadeIn 0.25s cubic-bezier(0.16, 1, 0.3, 1)'
          }}
          onClick={handleModalClose}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '440px',
              background: 'linear-gradient(160deg, rgba(255, 255, 255, 0.96) 0%, rgba(248, 250, 252, 0.92) 100%)',
              backdropFilter: 'blur(32px) saturate(190%)',
              WebkitBackdropFilter: 'blur(32px) saturate(190%)',
              border: '1.5px solid rgba(255, 255, 255, 0.95)',
              borderRadius: '26px',
              boxShadow: '0 25px 60px -12px rgba(0, 122, 255, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.9), inset 0 1px 2px rgba(255, 255, 255, 1)',
              padding: '36px 30px',
              textAlign: 'center',
              position: 'relative'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close X button */}
            <button
              type="button"
              onClick={handleModalClose}
              style={{
                position: 'absolute',
                top: '18px',
                right: '18px',
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                border: 'none',
                background: 'rgba(0, 0, 0, 0.05)',
                color: '#64748b',
                fontSize: '15px',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s ease'
              }}
              aria-label="Close"
            >
              ✕
            </button>

            {/* Glowing Fluid Circular Emerald Checkmark */}
            <div
              style={{
                width: '68px',
                height: '68px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                boxShadow: '0 10px 25px -4px rgba(16, 185, 129, 0.45)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 20px',
                color: '#ffffff'
              }}
            >
              <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>

            {/* Heading */}
            <h3
              style={{
                fontSize: '22px',
                fontWeight: 800,
                color: '#1D1D1F',
                margin: '0 0 12px 0',
                letterSpacing: '-0.02em',
                fontFamily: "'PT Serif', 'BJCree', serif"
              }}
            >
              Policy Selection Confirmed
            </h3>

            {/* Body */}
            <p
              style={{
                fontSize: '17px',
                fontWeight: 700,
                color: '#1D1D1F',
                lineHeight: 1.6,
                margin: '0 0 20px 0'
              }}
            >
              You have selected the <strong>{pDetails.plan_name}</strong> Plan. Agent will contact you soon for document verification.
            </p>

            {/* Notice Callout */}
            <div
              style={{
                fontSize: '14.5px',
                fontWeight: 700,
                color: '#1D1D1F',
                background: 'rgba(241, 245, 249, 0.85)',
                border: '1.5px solid rgba(203, 213, 225, 0.95)',
                padding: '14px 16px',
                borderRadius: '14px',
                marginBottom: '24px',
                lineHeight: 1.5,
                textAlign: 'left'
              }}
            >
              <strong>Notice:</strong> Confirmation records enrollment intent only; it does not issue an official insurance policy or activate binding coverage.
            </div>

            {/* Modal Actions */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <button
                type="button"
                className="auth-submit-btn"
                onClick={handleProceedToChat}
                style={{
                  width: '100%',
                  padding: '14px 24px',
                  minHeight: '48px',
                  fontSize: '15px',
                  fontWeight: 700,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                  borderRadius: '14px',
                  boxShadow: '0 4px 16px rgba(16, 185, 129, 0.4)',
                  color: '#ffffff',
                  cursor: 'pointer'
                }}
              >
                <span>Continue to Policy Chat</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                  <polyline points="12 5 19 12 12 19"></polyline>
                </svg>
              </button>

              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="button"
                  onClick={handleModalClose}
                  style={{
                    flex: 1,
                    padding: '11px 16px',
                    borderRadius: '12px',
                    border: '1.2px solid rgba(203, 213, 225, 0.9)',
                    background: '#ffffff',
                    color: '#1D1D1F',
                    fontSize: '14px',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  View Confirmed Summary
                </button>

                <button
                  type="button"
                  onClick={handlePrintPdf}
                  style={{
                    flex: 1,
                    padding: '11px 16px',
                    borderRadius: '12px',
                    border: '1.2px solid rgba(203, 213, 225, 0.9)',
                    background: '#ffffff',
                    color: '#1D1D1F',
                    fontSize: '14px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px'
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="6 9 6 2 18 2 18 9"></polyline>
                    <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path>
                    <rect x="6" y="14" width="12" height="8"></rect>
                  </svg>
                  <span>Print PDF</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ConfirmReviewScreen;
