import React, { useState, useEffect, useMemo, useRef } from 'react';
import { eligibilityApi } from '../services/eligibilityApi';

export function EligibilityScreen({ user, onAssessmentComplete, onCancel }) {
  // Model Features: age, height_cm, weight_kg, smoker, alcoholic, pre_existing_condition
  const [age, setAge] = useState('');
  const [heightCm, setHeightCm] = useState('');
  const [weightKg, setWeightKg] = useState('');
  const [smoker, setSmoker] = useState(''); // '' | 'No' | 'Yes'
  const [alcoholic, setAlcoholic] = useState(''); // '' | 'No' | 'Yes'
  const [condition, setCondition] = useState('');
  const [isConditionDropdownOpen, setIsConditionDropdownOpen] = useState(false);
  const [dropUp, setDropUp] = useState(true);
  const conditionDropdownRef = useRef(null);

  const updateDropdownPosition = () => {
    if (conditionDropdownRef.current) {
      const rect = conditionDropdownRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;
      // All 8 options without description take ~310px height
      if (spaceBelow >= 320 && spaceBelow > spaceAbove) {
        setDropUp(false);
      } else {
        setDropUp(true);
      }
    }
  };

  const [loading, setLoading] = useState(false);
  const [checkingExisting, setCheckingExisting] = useState(true);
  const [error, setError] = useState(null);
  const [assessmentResult, setAssessmentResult] = useState(null);

  // Simple Fluid Glass Agent Confirmation Popup State
  const [showAgentPopup, setShowAgentPopup] = useState(false);

  // Authoritative condition list from model_info.json
  const allowedConditions = [
    { id: 'None', label: 'None / No Known Conditions' },
    { id: 'Hypertension', label: 'Hypertension' },
    { id: 'Diabetes', label: 'Diabetes' },
    { id: 'Heart_Disease', label: 'Heart Disease' },
    { id: 'Thyroid_Disorder', label: 'Thyroid Disorder' },
    { id: 'Other condition', label: 'Other Condition' },
    { id: 'Multiple', label: 'Multiple Conditions' },
    { id: 'Not sure', label: 'Not Sure' }
  ];

  // Live BMI Calculation: weight_kg / (height_cm / 100) ** 2
  const bmiData = useMemo(() => {
    const h = parseFloat(heightCm);
    const w = parseFloat(weightKg);
    if (!h || !w || h <= 0) return { bmi: '—', category: 'Pending Entry', color: '#64748b' };
    const calculated = (w / ((h / 100) ** 2)).toFixed(1);
    const val = parseFloat(calculated);

    let category = 'Normal';
    let color = '#10b981'; // Green
    if (val < 18.5) {
      category = 'Underweight';
      color = '#f59e0b';
    } else if (val >= 25.0 && val < 30.0) {
      category = 'Overweight';
      color = '#f59e0b';
    } else if (val >= 30.0) {
      category = 'Obese';
      color = '#ef4444';
    }
    return { bmi: calculated, category, color };
  }, [heightCm, weightKg]);

  // Load existing current assessment if available
  useEffect(() => {
    let mounted = true;
    async function loadCurrent() {
      try {
        const data = await eligibilityApi.getMyAssessment();
        if (mounted && data.has_assessment && data.assessment) {
          setAssessmentResult(data.assessment);
          const prov = data.assessment.input_provenance || data.assessment.input_summary || {};
          if (prov.age !== undefined && prov.age !== '') setAge(prov.age);
          if (prov.height_cm !== undefined && prov.height_cm !== '') setHeightCm(prov.height_cm);
          if (prov.weight_kg !== undefined && prov.weight_kg !== '') setWeightKg(prov.weight_kg);
          if (prov.smoker) setSmoker(prov.smoker);
          if (prov.alcoholic) setAlcoholic(prov.alcoholic);
          if (prov.pre_existing_condition) setCondition(prov.pre_existing_condition);
        }
      } catch {
        // Allow fresh submission
      } finally {
        if (mounted) setCheckingExisting(false);
      }
    }
    loadCurrent();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    function handleClickOutside(event) {
      if (conditionDropdownRef.current && !conditionDropdownRef.current.contains(event.target)) {
        setIsConditionDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  useEffect(() => {
    if (isConditionDropdownOpen) {
      updateDropdownPosition();
      window.addEventListener('resize', updateDropdownPosition);
      window.addEventListener('scroll', updateDropdownPosition, true);
      return () => {
        window.removeEventListener('resize', updateDropdownPosition);
        window.removeEventListener('scroll', updateDropdownPosition, true);
      };
    }
  }, [isConditionDropdownOpen]);

  const handleToggleDropdown = () => {
    if (!isConditionDropdownOpen) {
      updateDropdownPosition();
    }
    setIsConditionDropdownOpen((prev) => !prev);
  };

  const selectedConditionObj = useMemo(() => {
    if (!condition) {
      return { id: '', label: 'Select Pre-existing Condition' };
    }
    return allowedConditions.find((c) => c.id === condition) || allowedConditions[0];
  }, [condition, allowedConditions]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // Client validation matching model_info.json constraints
    const ageNum = parseInt(age, 10);
    const heightNum = parseFloat(heightCm);
    const weightNum = parseFloat(weightKg);

    if (age === '' || isNaN(ageNum) || ageNum < 18 || ageNum > 100) {
      setError('Please enter a valid age between 18 and 100.');
      setLoading(false);
      return;
    }
    if (heightCm === '' || isNaN(heightNum) || heightNum < 100 || heightNum > 250) {
      setError('Please enter a valid height between 100 cm and 250 cm.');
      setLoading(false);
      return;
    }
    if (weightKg === '' || isNaN(weightNum) || weightNum < 20 || weightNum > 300) {
      setError('Please enter a valid weight between 20 kg and 300 kg.');
      setLoading(false);
      return;
    }
    if (!smoker) {
      setError('Please select your tobacco/smoking status.');
      setLoading(false);
      return;
    }
    if (!alcoholic) {
      setError('Please select your alcohol consumption status.');
      setLoading(false);
      return;
    }
    if (!condition) {
      setError('Please select a pre-existing condition category.');
      setLoading(false);
      return;
    }

    try {
      const payload = {
        age: ageNum,
        height_cm: heightNum,
        weight_kg: weightNum,
        smoker: smoker,
        alcoholic: alcoholic,
        pre_existing_condition: condition
      };

      const result = await eligibilityApi.assess(payload);
      setAssessmentResult(result);
    } catch (err) {
      setError(err.message || 'Failed to complete eligibility assessment.');
    } finally {
      setLoading(false);
    }
  };

  const handleProceed = () => {
    if (onAssessmentComplete && assessmentResult) {
      onAssessmentComplete(assessmentResult);
    }
  };

  if (checkingExisting) {
    return (
      <div className="auth-card-container">
        <div className="auth-card" style={{ textAlign: 'center', padding: '48px 32px' }}>
          <div className="auth-spinner" style={{ margin: '0 auto 16px' }} />
          <p style={{ color: '#000000', fontWeight: 600 }}>Verifying Existing Underwriting Profile...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-card-container" style={{ maxWidth: '640px' }}>
      <div className="auth-card" style={{ overflow: 'visible' }}>
        <div className="auth-card-shine" />

        {/* Header */}
        <div className="auth-header">
          <h2 className="auth-title" style={{ marginBottom: '18px' }}>Health Insurance Eligibility Check</h2>
        </div>

        {error && (
          <div className="auth-error-banner" role="alert" style={{ marginBottom: '16px' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        {/* Evaluated Outcome Panel: Simple, Effective, Attractive & Fluid Glass */}
        {assessmentResult ? (
          <div
            style={{
              textAlign: 'center',
              padding: '12px 6px 6px',
              animation: 'authCardFadeIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
            }}
          >
            {/* Fluid Glass Status Badge */}
            <div
              style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                background: assessmentResult.outcome === 'ELIGIBLE'
                  ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
                  : 'linear-gradient(135deg, #f59e0b 0%, #ea580c 100%)',
                boxShadow: assessmentResult.outcome === 'ELIGIBLE'
                  ? '0 12px 28px -6px rgba(16, 185, 129, 0.45)'
                  : '0 12px 28px -6px rgba(234, 88, 12, 0.35)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 18px',
                color: '#ffffff'
              }}
            >
              {assessmentResult.outcome === 'ELIGIBLE' ? (
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              )}
            </div>

            {/* Title */}
            <h3
              style={{
                fontSize: '24px',
                fontWeight: 800,
                color: '#0f172a',
                margin: '0 0 8px',
                letterSpacing: '-0.02em'
              }}
            >
              {assessmentResult.outcome === 'ELIGIBLE'
                ? "You're Eligible!"
                : 'Specialized Review Recommended'}
            </h3>

            {(assessmentResult.completed_at || assessmentResult.created_at) && (
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '14.5px',
                  color: '#1D1D1F',
                  marginBottom: '14px',
                  fontWeight: 600
                }}
              >
                <span style={{ color: '#1D1D1F', fontWeight: 600 }}>Assessment Date:</span>
                <strong style={{ color: '#1D1D1F', fontWeight: 700 }}>
                  {new Date(assessmentResult.completed_at || assessmentResult.created_at).toLocaleString(undefined, {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </strong>
              </div>
            )}

            {assessmentResult.outcome !== 'ELIGIBLE' && (
              <p
                style={{
                  fontSize: '15px',
                  color: '#475569',
                  margin: '0 auto 20px',
                  maxWidth: '480px',
                  lineHeight: 1.55
                }}
              >
                Based on underwriting standards, direct online enrollment is paused. Our licensed agents specialize in alternative coverage options for your profile.
              </p>
            )}

            {/* If Eligible: Clean, Beautiful Plan Tier Badges */}
            {assessmentResult.outcome === 'ELIGIBLE' && assessmentResult.qualifying_plans?.length > 0 && (
              <div style={{ marginBottom: '22px' }}>
                <div
                  style={{
                    fontSize: '14px',
                    fontWeight: 800,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    color: '#1D1D1F',
                    marginBottom: '10px'
                  }}
                >
                  Authorized Plan Tiers Available
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '8px' }}>
                  {assessmentResult.qualifying_plans.map((p) => {
                    const cleanName = typeof p === 'string'
                      ? p.toUpperCase().includes('PLATINUM')
                        ? 'Platinum Tier'
                        : p.toUpperCase().includes('GOLD')
                        ? 'Gold Tier'
                        : p.toUpperCase().includes('SILVER')
                        ? 'Silver Tier'
                        : p.toUpperCase().includes('PREMIUM')
                        ? 'Premium Tier'
                        : p.toUpperCase().includes('BASIC')
                        ? 'Basic Tier'
                        : p.toUpperCase().includes('BRONZE')
                        ? 'Bronze Tier'
                        : p.replace(/^HS-/, '').replace(/-\d+$/, '').replace(/_/g, ' ')
                      : p;
                    return (
                      <span
                        key={p}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '7px 16px',
                          borderRadius: '9999px',
                          background: 'rgba(16, 185, 129, 0.09)',
                          border: '1.2px solid rgba(16, 185, 129, 0.28)',
                          color: '#047857',
                          fontSize: '13px',
                          fontWeight: 700
                        }}
                      >
                        ✓ {cleanName}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Verified Underwriting Criteria Grid (Read-Only) */}
            <div
              style={{
                background: 'linear-gradient(175deg, rgba(255, 255, 255, 0.92) 0%, rgba(248, 250, 252, 0.88) 100%)',
                backdropFilter: 'blur(16px)',
                WebkitBackdropFilter: 'blur(16px)',
                border: '1.2px solid rgba(226, 232, 240, 0.95)',
                borderRadius: '16px',
                padding: '16px',
                marginBottom: '22px',
                textAlign: 'left',
                boxShadow: '0 4px 16px -2px rgba(0, 0, 0, 0.04), inset 0 1px 1px rgba(255, 255, 255, 0.9)'
              }}
            >
              <div
                style={{
                  fontSize: '13px',
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  color: '#1D1D1F',
                  marginBottom: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}
              >
                <span style={{ color: '#1D1D1F', fontWeight: 800 }}>Verified Underwriting Criteria</span>
                <span
                  style={{
                    fontSize: '10.5px',
                    fontWeight: 700,
                    color: '#059669',
                    background: 'rgba(16, 185, 129, 0.1)',
                    border: '1px solid rgba(16, 185, 129, 0.25)',
                    padding: '1.5px 7px',
                    borderRadius: '9999px',
                    textTransform: 'none',
                    letterSpacing: 'normal'
                  }}
                >
                  🔒 Locked &amp; Non-Editable
                </span>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                  gap: '10px'
                }}
              >
                <div style={{ background: '#ffffff', borderRadius: '10px', padding: '10px 12px', border: '1px solid rgba(226, 232, 240, 0.8)' }}>
                  <div style={{ fontSize: '12px', color: '#1D1D1F', fontWeight: 700, marginBottom: '2px' }}>Applicant Age</div>
                  <div style={{ fontSize: '14.5px', color: '#1D1D1F', fontWeight: 800 }}>
                    {(assessmentResult.input_provenance?.age || assessmentResult.input_summary?.age || age) ? `${assessmentResult.input_provenance?.age || assessmentResult.input_summary?.age || age} yrs` : '—'}
                  </div>
                </div>

                <div style={{ background: '#ffffff', borderRadius: '10px', padding: '10px 12px', border: '1px solid rgba(226, 232, 240, 0.8)' }}>
                  <div style={{ fontSize: '12px', color: '#1D1D1F', fontWeight: 700, marginBottom: '2px' }}>Height &amp; Weight</div>
                  <div style={{ fontSize: '14.5px', color: '#1D1D1F', fontWeight: 800 }}>
                    {(assessmentResult.input_provenance?.height_cm || assessmentResult.input_summary?.height_cm || heightCm)} cm / {(assessmentResult.input_provenance?.weight_kg || assessmentResult.input_summary?.weight_kg || weightKg)} kg
                  </div>
                </div>

                <div style={{ background: '#ffffff', borderRadius: '10px', padding: '10px 12px', border: '1px solid rgba(226, 232, 240, 0.8)' }}>
                  <div style={{ fontSize: '12px', color: '#1D1D1F', fontWeight: 700, marginBottom: '2px' }}>Calculated BMI</div>
                  <div style={{ fontSize: '14.5px', color: '#1D1D1F', fontWeight: 800 }}>
                    {assessmentResult.bmi || assessmentResult.input_provenance?.bmi || bmiData.bmi || '—'}
                  </div>
                </div>

                <div style={{ background: '#ffffff', borderRadius: '10px', padding: '10px 12px', border: '1px solid rgba(226, 232, 240, 0.8)' }}>
                  <div style={{ fontSize: '12px', color: '#1D1D1F', fontWeight: 700, marginBottom: '2px' }}>Tobacco / Smoker</div>
                  <div style={{ fontSize: '14.5px', color: '#1D1D1F', fontWeight: 800 }}>
                    {assessmentResult.input_provenance?.smoker || assessmentResult.input_summary?.smoker || smoker || 'No'}
                  </div>
                </div>

                <div style={{ background: '#ffffff', borderRadius: '10px', padding: '10px 12px', border: '1px solid rgba(226, 232, 240, 0.8)' }}>
                  <div style={{ fontSize: '12px', color: '#1D1D1F', fontWeight: 700, marginBottom: '2px' }}>Alcohol Usage</div>
                  <div style={{ fontSize: '14.5px', color: '#1D1D1F', fontWeight: 800 }}>
                    {assessmentResult.input_provenance?.alcoholic || assessmentResult.input_summary?.alcoholic || alcoholic || 'No'}
                  </div>
                </div>

                <div style={{ background: '#ffffff', borderRadius: '10px', padding: '10px 12px', border: '1px solid rgba(226, 232, 240, 0.8)' }}>
                  <div style={{ fontSize: '12px', color: '#1D1D1F', fontWeight: 700, marginBottom: '2px' }}>Pre-existing Condition</div>
                  <div style={{ fontSize: '14.5px', color: '#1D1D1F', fontWeight: 800 }}>
                    {assessmentResult.input_provenance?.pre_existing_condition || assessmentResult.input_summary?.pre_existing_condition || condition || 'None'}
                  </div>
                </div>
              </div>
            </div>

            {/* Primary Action Button */}
            {assessmentResult.outcome === 'ELIGIBLE' ? (
              <button
                type="button"
                className="auth-submit-btn"
                onClick={handleProceed}
                style={{
                  width: '100%',
                  minHeight: '48px',
                  fontSize: '16px',
                  fontWeight: 700,
                  borderRadius: '14px',
                  background: 'linear-gradient(135deg, #0284c7 0%, #007aff 100%)',
                  boxShadow: '0 6px 20px rgba(0, 122, 255, 0.3)',
                  marginBottom: '12px'
                }}
              >
                Continue to Choose Plan ➔
              </button>
            ) : (
              <button
                type="button"
                className="auth-submit-btn"
                onClick={() => setShowAgentPopup(true)}
                style={{
                  width: '100%',
                  minHeight: '48px',
                  fontSize: '16px',
                  fontWeight: 700,
                  borderRadius: '14px',
                  background: 'linear-gradient(135deg, #0284c7 0%, #007aff 100%)',
                  boxShadow: '0 6px 20px rgba(0, 122, 255, 0.3)',
                  marginBottom: '12px'
                }}
              >
                Contact a Licensed Agent ➔
              </button>
            )}

            {/* Permanent One-Time Assessment Policy Notice */}
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                borderRadius: '10px',
                background: 'rgba(16, 185, 129, 0.08)',
                border: '1px solid rgba(16, 185, 129, 0.25)',
                color: '#065f46',
                fontSize: '12.5px',
                fontWeight: 600
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span>Assessment Completed & Persisted • One-time evaluation policy</span>
            </div>
          </div>
        ) : (
          /* Form for Entering Authentic Model Features */
          <form onSubmit={handleSubmit} className="auth-form" noValidate>
            {/* Age Field: Enterable Numeric Input */}
            <div className="auth-field-group">
              <label className="auth-label" htmlFor="applicant-age" style={{ fontSize: '15px', fontWeight: 700, color: '#000000' }}>
                Applicant Age
              </label>
              <div className="auth-input-wrapper">
                <input
                  id="applicant-age"
                  type="number"
                  min="18"
                  max="100"
                  value={age}
                  onChange={(e) => setAge(e.target.value === '' ? '' : parseInt(e.target.value, 10))}
                  className="auth-input"
                  placeholder="Enter age (18–100)"
                  required
                  style={{
                    fontSize: '16.5px',
                    fontWeight: 600,
                    color: '#000000',
                    padding: '12px 16px',
                    height: '48px'
                  }}
                />
              </div>
            </div>

            {/* Biometric Row: Height (cm) and Weight (kg) */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
              <div className="auth-field-group" style={{ margin: 0 }}>
                <label className="auth-label" htmlFor="applicant-height" style={{ fontSize: '15px', fontWeight: 700, color: '#000000' }}>
                  Height (cm)
                </label>
                <div className="auth-input-wrapper">
                  <input
                    id="applicant-height"
                    type="number"
                    min="100"
                    max="250"
                    value={heightCm}
                    onChange={(e) => setHeightCm(e.target.value)}
                    className="auth-input"
                    placeholder="Height (cm)"
                    required
                    style={{
                      fontSize: '16.5px',
                      fontWeight: 600,
                      color: '#000000',
                      padding: '12px 16px',
                      height: '48px'
                    }}
                  />
                </div>
              </div>

              <div className="auth-field-group" style={{ margin: 0 }}>
                <label className="auth-label" htmlFor="applicant-weight" style={{ fontSize: '15px', fontWeight: 700, color: '#000000' }}>
                  Weight (kg)
                </label>
                <div className="auth-input-wrapper">
                  <input
                    id="applicant-weight"
                    type="number"
                    min="20"
                    max="300"
                    value={weightKg}
                    onChange={(e) => setWeightKg(e.target.value)}
                    className="auth-input"
                    placeholder="Weight (kg)"
                    required
                    style={{
                      fontSize: '16.5px',
                      fontWeight: 600,
                      color: '#000000',
                      padding: '12px 16px',
                      height: '48px'
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Live BMI Display Indicator */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.75)',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              border: '1.5px solid rgba(214, 214, 216, 0.85)',
              borderRadius: '14px',
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '18px',
              boxShadow: '0 1px 3px rgba(0, 0, 0, 0.03), inset 0 1px 1px rgba(255, 255, 255, 0.9)'
            }}>
              <div>
                <span style={{ fontSize: '13px', fontWeight: 'bold', textTransform: 'uppercase', color: '#000000', display: 'block', letterSpacing: '0.04em' }}>
                  Computed BMI
                </span>
                <div style={{ fontSize: '18px', fontWeight: 800, color: '#000000', marginTop: '2px' }}>
                  {bmiData.bmi} <span style={{ fontSize: '13px', fontWeight: 600, color: '#000000' }}>kg/m²</span>
                </div>
              </div>
              <span style={{
                background: bmiData.color,
                color: '#ffffff',
                padding: '4px 12px',
                borderRadius: '9999px',
                fontSize: '12px',
                fontWeight: 700,
                boxShadow: `0 2px 8px ${bmiData.color}44`
              }}>
                {bmiData.category}
              </span>
            </div>

            {/* Lifestyle Toggles: Smoker & Alcoholic (Fluid Glass) */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '18px' }}>
              <div className="auth-field-group" style={{ margin: 0 }}>
                <label className="auth-label" style={{ marginBottom: '8px', display: 'block' }}>
                  Tobacco / Smoker
                </label>
                <div style={{
                  display: 'flex',
                  background: 'rgba(255, 255, 255, 0.65)',
                  backdropFilter: 'blur(16px)',
                  WebkitBackdropFilter: 'blur(16px)',
                  border: '1.5px solid rgba(214, 214, 216, 0.85)',
                  borderRadius: '14px',
                  padding: '4px',
                  gap: '6px',
                  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.03), inset 0 1px 1px rgba(255, 255, 255, 0.9)'
                }}>
                  <button
                    type="button"
                    onClick={() => setSmoker('No')}
                    style={{
                      flex: 1,
                      padding: '9px 0',
                      border: 'none',
                      borderRadius: '10px',
                      cursor: 'pointer',
                      fontSize: '13.5px',
                      fontWeight: 700,
                      fontFamily: 'inherit',
                      transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                      background: smoker === 'No'
                        ? 'linear-gradient(135deg, #0284c7 0%, #007aff 100%)'
                        : 'transparent',
                      color: smoker === 'No' ? '#ffffff' : '#000000',
                      boxShadow: smoker === 'No'
                        ? '0 3px 10px rgba(0, 122, 255, 0.32), inset 0 1px 1px rgba(255, 255, 255, 0.5)'
                        : 'none'
                    }}
                  >
                    No
                  </button>
                  <button
                    type="button"
                    onClick={() => setSmoker('Yes')}
                    style={{
                      flex: 1,
                      padding: '9px 0',
                      border: 'none',
                      borderRadius: '10px',
                      cursor: 'pointer',
                      fontSize: '13.5px',
                      fontWeight: 700,
                      fontFamily: 'inherit',
                      transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                      background: smoker === 'Yes'
                        ? 'linear-gradient(135deg, #f59e0b 0%, #ea580c 100%)'
                        : 'transparent',
                      color: smoker === 'Yes' ? '#ffffff' : '#000000',
                      boxShadow: smoker === 'Yes'
                        ? '0 3px 10px rgba(234, 88, 12, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.5)'
                        : 'none'
                    }}
                  >
                    Yes
                  </button>
                </div>
              </div>

              <div className="auth-field-group" style={{ margin: 0 }}>
                <label className="auth-label" style={{ marginBottom: '8px', display: 'block' }}>
                  Alcohol Consumption
                </label>
                <div style={{
                  display: 'flex',
                  background: 'rgba(255, 255, 255, 0.65)',
                  backdropFilter: 'blur(16px)',
                  WebkitBackdropFilter: 'blur(16px)',
                  border: '1.5px solid rgba(214, 214, 216, 0.85)',
                  borderRadius: '14px',
                  padding: '4px',
                  gap: '6px',
                  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.03), inset 0 1px 1px rgba(255, 255, 255, 0.9)'
                }}>
                  <button
                    type="button"
                    onClick={() => setAlcoholic('No')}
                    style={{
                      flex: 1,
                      padding: '9px 0',
                      border: 'none',
                      borderRadius: '10px',
                      cursor: 'pointer',
                      fontSize: '13.5px',
                      fontWeight: 700,
                      fontFamily: 'inherit',
                      transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                      background: alcoholic === 'No'
                        ? 'linear-gradient(135deg, #0284c7 0%, #007aff 100%)'
                        : 'transparent',
                      color: alcoholic === 'No' ? '#ffffff' : '#000000',
                      boxShadow: alcoholic === 'No'
                        ? '0 3px 10px rgba(0, 122, 255, 0.32), inset 0 1px 1px rgba(255, 255, 255, 0.5)'
                        : 'none'
                    }}
                  >
                    No
                  </button>
                  <button
                    type="button"
                    onClick={() => setAlcoholic('Yes')}
                    style={{
                      flex: 1,
                      padding: '9px 0',
                      border: 'none',
                      borderRadius: '10px',
                      cursor: 'pointer',
                      fontSize: '13.5px',
                      fontWeight: 700,
                      fontFamily: 'inherit',
                      transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                      background: alcoholic === 'Yes'
                        ? 'linear-gradient(135deg, #f59e0b 0%, #ea580c 100%)'
                        : 'transparent',
                      color: alcoholic === 'Yes' ? '#ffffff' : '#000000',
                      boxShadow: alcoholic === 'Yes'
                        ? '0 3px 10px rgba(234, 88, 12, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.5)'
                        : 'none'
                    }}
                  >
                    Yes
                  </button>
                </div>
              </div>
            </div>

            {/* Pre-Existing Condition Selection: Liquid Glass Dropdown */}
            <div className="auth-field-group" style={{ marginBottom: '24px' }}>
              <label className="auth-label" htmlFor="applicant-condition" style={{ fontSize: '15px', fontWeight: 700, color: '#000000' }}>
                Pre-existing Condition Category
              </label>
              <div ref={conditionDropdownRef} style={{ position: 'relative' }}>
                <button
                  type="button"
                  id="applicant-condition"
                  onClick={handleToggleDropdown}
                  style={{
                    width: '100%',
                    minHeight: '48px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 16px',
                    background: 'rgba(255, 255, 255, 0.75)',
                    backdropFilter: 'blur(16px)',
                    WebkitBackdropFilter: 'blur(16px)',
                    border: isConditionDropdownOpen ? '1.5px solid #007AFF' : '1.5px solid rgba(214, 214, 216, 0.85)',
                    borderRadius: '14px',
                    boxShadow: isConditionDropdownOpen
                      ? '0 0 0 3px rgba(0, 122, 255, 0.18)'
                      : '0 1px 3px rgba(0, 0, 0, 0.03), inset 0 1px 1px rgba(255, 255, 255, 0.9)',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                    outline: 'none'
                  }}
                >
                  <div style={{ minWidth: 0, flex: 1, fontSize: '15.5px', fontWeight: condition ? 700 : 500, color: condition ? '#000000' : '#64748b' }}>
                    {selectedConditionObj.label}
                  </div>
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#000000"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{
                      transform: isConditionDropdownOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                      transition: 'transform 0.2s ease',
                      flexShrink: 0,
                      marginLeft: '12px'
                    }}
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>

                {isConditionDropdownOpen && (
                  <div
                    style={{
                      position: 'absolute',
                      ...(dropUp
                        ? { bottom: 'calc(100% + 8px)', top: 'auto' }
                        : { top: 'calc(100% + 8px)', bottom: 'auto' }),
                      left: 0,
                      right: 0,
                      zIndex: 100,
                      background: 'rgba(255, 255, 255, 0.98)',
                      backdropFilter: 'blur(28px)',
                      WebkitBackdropFilter: 'blur(28px)',
                      border: '1.5px solid rgba(226, 232, 240, 0.95)',
                      borderRadius: '16px',
                      boxShadow: dropUp
                        ? '0 -16px 40px rgba(0, 0, 0, 0.14), 0 -4px 12px rgba(0, 0, 0, 0.05)'
                        : '0 16px 40px rgba(0, 0, 0, 0.14), 0 4px 12px rgba(0, 0, 0, 0.05)',
                      padding: '6px',
                      overflow: 'visible',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '2px',
                      animation: 'authCardFadeIn 0.18s ease-out'
                    }}
                  >
                    {allowedConditions.map((c) => {
                      const isSelected = condition === c.id;
                      return (
                        <div
                          key={c.id}
                          onClick={() => {
                            setCondition(c.id);
                            setIsConditionDropdownOpen(false);
                          }}
                          style={{
                            padding: '9px 14px',
                            borderRadius: '10px',
                            cursor: 'pointer',
                            background: isSelected ? 'rgba(0, 122, 255, 0.1)' : 'transparent',
                            border: isSelected ? '1px solid rgba(0, 122, 255, 0.25)' : '1px solid transparent',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            transition: 'all 0.15s ease'
                          }}
                          onMouseEnter={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.background = 'rgba(241, 245, 249, 0.85)';
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.background = 'transparent';
                            }
                          }}
                        >
                          <span style={{ fontSize: '15px', fontWeight: isSelected ? 700 : 500, color: isSelected ? '#007AFF' : '#000000' }}>
                            {c.label}
                          </span>
                          {isSelected && (
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#007AFF" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginLeft: '8px' }}>
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              className="auth-submit-btn"
              disabled={loading}
              style={{ width: '100%', minHeight: '46px' }}
            >
              {loading ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div className="auth-spinner" style={{ width: '18px', height: '18px', borderWidth: '2px' }} />
                  <span>Evaluating Model Pipeline...</span>
                </div>
              ) : (
                'Run Underwriting Assessment ➔'
              )}
            </button>
          </form>
        )}
      </div>

      {/* Simple Fluid Glass Agent Confirmation Popup */}
      {showAgentPopup && (
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
          onClick={() => setShowAgentPopup(false)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '430px',
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
              onClick={() => setShowAgentPopup(false)}
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

            {/* Glowing Fluid Circular Icon */}
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
                color: '#0f172a',
                margin: '0 0 8px',
                letterSpacing: '-0.02em'
              }}
            >
              Request has been sent
            </h3>

            {/* Subtitle */}
            <p
              style={{
                fontSize: '16px',
                fontWeight: 600,
                color: '#0284c7',
                margin: '0 0 16px'
              }}
            >
              An agent will contact you soon.
            </p>

            {/* Context Notice */}
            <div
              style={{
                background: 'rgba(2, 132, 199, 0.05)',
                border: '1px solid rgba(2, 132, 199, 0.15)',
                borderRadius: '14px',
                padding: '12px 16px',
                fontSize: '13px',
                color: '#475569',
                lineHeight: 1.5,
                marginBottom: '24px'
              }}
            >
              A licensed health insurance specialist will review your underwriting health profile and reach out directly to explore alternative coverage options.
            </div>

            {/* Action Done Button */}
            <button
              type="button"
              onClick={() => setShowAgentPopup(false)}
              className="auth-submit-btn"
              style={{
                width: '100%',
                minHeight: '48px',
                fontSize: '15.5px',
                fontWeight: 700,
                borderRadius: '14px',
                background: 'linear-gradient(135deg, #0284c7 0%, #007aff 100%)',
                boxShadow: '0 6px 20px rgba(0, 122, 255, 0.3)'
              }}
            >
              Got it
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
