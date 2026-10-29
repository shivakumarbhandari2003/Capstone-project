import React, { useState, useEffect, useRef } from 'react';
import { claimPredictorApi } from '../services/claimPredictorApi';

/**
 * LiquidGlassSelect — Reusable Liquid Glass dropdown matching EligibilityScreen.jsx.
 * Explicitly sets var(--font-family) on trigger, text, and option items.
 */
function LiquidGlassSelect({ id, value, onChange, options, ariaLabel }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const selectedOption = options.find((opt) => opt.value === value) || options[0];

  return (
    <div ref={dropdownRef} style={{ position: 'relative', width: '100%', minWidth: 0, boxSizing: 'border-box' }}>
      <button
        type="button"
        id={id}
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label={ariaLabel || id}
        aria-expanded={isOpen}
        style={{
          width: '100%',
          minWidth: 0,
          height: '38px',
          minHeight: '38px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 10px',
          background: 'rgba(255, 255, 255, 0.88)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: isOpen ? '1.5px solid #007AFF' : '1.5px solid rgba(214, 214, 216, 0.95)',
          borderRadius: '10px',
          boxShadow: isOpen
            ? '0 0 0 2.5px rgba(0, 122, 255, 0.18)'
            : '0 1px 3px rgba(0, 0, 0, 0.04), inset 0 1px 1px rgba(255, 255, 255, 0.95)',
          cursor: 'pointer',
          textAlign: 'left',
          transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          outline: 'none',
          boxSizing: 'border-box',
          fontFamily: 'var(--font-family, inherit)'
        }}
      >
        <span
          style={{
            fontSize: '12.5px',
            fontWeight: 700,
            fontFamily: 'var(--font-family, inherit)',
            color: '#000000',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            minWidth: 0,
            flex: 1,
            paddingRight: '4px'
          }}
        >
          {selectedOption ? selectedOption.label : 'Select...'}
        </span>
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#000000"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease',
            flexShrink: 0
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 5px)',
            left: 0,
            right: 0,
            zIndex: 200,
            background: 'rgba(255, 255, 255, 0.98)',
            backdropFilter: 'blur(28px)',
            WebkitBackdropFilter: 'blur(28px)',
            border: '1.5px solid rgba(255, 255, 255, 0.95)',
            borderRadius: '12px',
            boxShadow: '0 12px 30px rgba(0, 0, 0, 0.16), 0 4px 10px rgba(0, 0, 0, 0.06)',
            padding: '4px',
            maxHeight: '210px',
            overflowY: 'auto',
            overflowX: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            gap: '3px',
            animation: 'authCardFadeIn 0.18s ease-out',
            fontFamily: 'var(--font-family, inherit)',
            boxSizing: 'border-box'
          }}
        >
          {options.map((opt) => {
            const isSelected = opt.value === value;
            return (
              <div
                key={String(opt.value)}
                onClick={() => {
                  onChange(opt.value);
                  setIsOpen(false);
                }}
                style={{
                  padding: '8px 10px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  background: isSelected ? 'rgba(0, 122, 255, 0.12)' : 'transparent',
                  border: isSelected ? '1px solid rgba(0, 122, 255, 0.3)' : '1px solid transparent',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  transition: 'all 0.15s ease',
                  fontFamily: 'var(--font-family, inherit)'
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) e.currentTarget.style.background = 'rgba(241, 245, 249, 0.95)';
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{ minWidth: 0, flex: 1, fontFamily: 'var(--font-family, inherit)' }}>
                  <div
                    style={{
                      fontSize: '12.5px',
                      fontWeight: isSelected ? 800 : 700,
                      color: '#000000',
                      fontFamily: 'var(--font-family, inherit)'
                    }}
                  >
                    {opt.label}
                  </div>
                  {opt.desc && (
                    <div
                      style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        color: '#000000',
                        marginTop: '1px',
                        fontFamily: 'var(--font-family, inherit)'
                      }}
                    >
                      {opt.desc}
                    </div>
                  )}
                </div>
                {isSelected && (
                  <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#007AFF"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{ flexShrink: 0, marginLeft: '6px' }}
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * ClaimPredictorDrawer — Employee-Only Predictive Claim Payout Inline Right Sidebar.
 * Locked to 360px width matching ChatActionsSidebar with zero jitter, zero horizontal overflow,
 * and universal Google font enforcement.
 */
export function ClaimPredictorDrawer({
  isOpen,
  onClose,
  authToken,
  currentConversationId,
  selectedPlan,
  onPredictionStart,
  onPredictionSuccess,
  onPredictionError
}) {
  const initialFormState = {
    age: 45,
    days_hospitalised: 4,
    icu_days: 1,
    procedures_claimed: 2,
    prior_daycare_claims_year: 0,
    extended_stay_flag: 0,
    plan: selectedPlan?.plan_category === 'Basic'
      ? 'Basic'
      : selectedPlan?.plan_category === 'Premium'
      ? 'Premium'
      : 'Gold',
    pre_existing: 'no',
    claim_type: 'Major surgery',
    documents_complete: 'yes'
  };

  const [formData, setFormData] = useState(initialFormState);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastResult, setLastResult] = useState(null);

  // Sync plan if selectedPlan changes
  useEffect(() => {
    if (selectedPlan?.plan_category) {
      const cat = selectedPlan.plan_category;
      if (cat === 'Basic' || cat === 'Gold' || cat === 'Premium') {
        setFormData((prev) => ({ ...prev, plan: cat }));
      }
    }
  }, [selectedPlan]);

  if (!isOpen) return null;

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setError(null);
  };

  const handleReset = () => {
    setFormData(initialFormState);
    setError(null);
    setLastResult(null);
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (loading) return;

    if (formData.age < 18 || formData.age > 70) {
      setError('Policyholder age must be between 18 and 70.');
      return;
    }
    if (formData.days_hospitalised < 0 || formData.days_hospitalised > 365) {
      setError('Days hospitalised must be between 0 and 365.');
      return;
    }
    if (formData.icu_days < 0 || formData.icu_days > 5) {
      setError('ICU days must be between 0 and 5.');
      return;
    }
    if (formData.procedures_claimed < 0 || formData.procedures_claimed > 50) {
      setError('Procedures claimed must be between 0 and 50.');
      return;
    }
    if (formData.prior_daycare_claims_year < 0 || formData.prior_daycare_claims_year > 20) {
      setError('Prior daycare claims must be between 0 and 20.');
      return;
    }

    setLoading(true);
    setError(null);

    // Notify parent to show chat assistant loading animation (no user query bubble per requirement)
    if (onPredictionStart) {
      onPredictionStart();
    }

    const payload = {
      age: parseInt(formData.age, 10),
      days_hospitalised: parseInt(formData.days_hospitalised, 10),
      icu_days: parseInt(formData.icu_days, 10),
      procedures_claimed: parseInt(formData.procedures_claimed, 10),
      prior_daycare_claims_year: parseInt(formData.prior_daycare_claims_year, 10),
      extended_stay_flag: parseInt(formData.extended_stay_flag, 10),
      plan: formData.plan,
      pre_existing: formData.pre_existing,
      claim_type: formData.claim_type,
      documents_complete: formData.documents_complete,
      conversation_id: currentConversationId || null,
      plan_id: selectedPlan?.plan_id || null
    };

    const startTime = Date.now();

    try {
      const apiFn = claimPredictorApi.predictClaimPayout || claimPredictorApi.predict;
      const res = await apiFn.call(claimPredictorApi, payload, authToken);
      setLastResult(res);

      // Enforce proper 6 seconds of animation duration (3 steps, 2s per step)
      const elapsed = Date.now() - startTime;
      const remainingDelay = Math.max(0, 6000 - elapsed);
      if (remainingDelay > 0) {
        await new Promise((resolve) => setTimeout(resolve, remainingDelay));
      }

      const predRaw = res?.prediction ?? 0;
      const formattedVal = Number(predRaw).toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
      const claimType = formData.claim_type || 'Major surgery';
      const planName = `Health Shield – ${formData.plan || 'Gold'}`;
      const extFlag = Number(formData.extended_stay_flag || 0);
      const extStr = extFlag === 1 ? 'Yes (≥ 8 days)' : 'No (< 8 days, if No)';
      const preExStr = formData.pre_existing === 'yes' ? 'Yes (Declared)' : 'No (None declared)';

      const fallbackContent = [
        '### ESTIMATED CLAIM PAYOUT',
        `# Rs. ${formattedVal}`,
        `*ML-Generated Estimate | ${claimType}*`,
        '',
        '---',
        '',
        '### CLAIM ASSESSMENT DETAILS',
        '',
        '| Policyholder Age | Days Hospitalised | ICU Days |',
        '| :--- | :--- | :--- |',
        `| **${formData.age}** years | **${formData.days_hospitalised}** days | **${formData.icu_days}** days |`,
        '',
        '| Procedures Claimed | Prior Daycare Claims | Plan Type |',
        '| :--- | :--- | :--- |',
        `| **${formData.procedures_claimed}** procedures | **${formData.prior_daycare_claims_year}** procedures | **${planName}** |`,
        '',
        '| Claim Type | Extended Stay | Pre-existing |',
        '| :--- | :--- | :--- |',
        `| **${claimType}** | **${extStr}** | **${preExStr}** |`,
        '',
        '> **Note:** Please verify original documents/policies/rules before reimbursement.'
      ].join('\n');

      const assistantMsg = res?.message || res?.assistant_message || {
        message_id: 'pred-' + Date.now(),
        role: 'assistant',
        content: fallbackContent,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: []
      };
      if (onPredictionSuccess) {
        onPredictionSuccess(assistantMsg);
      }
    } catch (err) {
      const elapsed = Date.now() - startTime;
      const remainingDelay = Math.max(0, 6000 - elapsed);
      if (remainingDelay > 0) {
        await new Promise((resolve) => setTimeout(resolve, remainingDelay));
      }
      setError(err.message || 'Failed to generate claim payout prediction.');
      if (onPredictionError) {
        onPredictionError();
      }
    } finally {
      setLoading(false);
    }
  };

  const planOptions = [
    { value: 'Basic', label: 'Basic Plan' },
    { value: 'Gold', label: 'Gold Plan' },
    { value: 'Premium', label: 'Premium Plan' }
  ];

  const claimTypeOptions = [
    { value: 'Major surgery', label: 'Major surgery' },
    { value: 'Hospitalisation', label: 'Hospitalisation' },
    { value: 'Medical management', label: 'Medical mgmt' },
    { value: 'Other surgery', label: 'Other surgery' }
  ];

  const extendedStayOptions = [
    { value: 0, label: 'No (< 8 days)' },
    { value: 1, label: 'Yes (≥ 8 days)' }
  ];

  const preExistingOptions = [
    { value: 'no', label: 'No (None)' },
    { value: 'yes', label: 'Yes (Declared)' }
  ];

  const documentOptions = [
    { value: 'yes', label: 'Yes (Complete)' },
    { value: 'no', label: 'No (Pending)' }
  ];

  return (
    <aside className="claim-predictor-sidebar" aria-label="Insurance Claim Predictor">
      {/* Top Header matching Menu sidebar */}
      <div className="claim-predictor-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #0284c7 0%, #007aff 100%)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 6px rgba(0, 122, 255, 0.25)',
              flexShrink: 0
            }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </div>
          <div style={{ minWidth: 0 }}>
            <span
              style={{
                fontSize: '15px',
                fontWeight: 800,
                color: '#000000',
                display: 'block',
                lineHeight: 1.2,
                fontFamily: 'var(--font-family, inherit)'
              }}
            >
              Claim Predictor
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          aria-label="Close Claim Predictor sidebar"
          title="Close Claim Predictor"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '5px',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#000000',
            flexShrink: 0
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#000000" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {/* Sidebar Body with form controls */}
      <div className="claim-predictor-body">
        {/* Error Banner */}
        {error && (
          <div
            style={{
              background: 'rgba(239, 68, 68, 0.08)',
              border: '1.2px solid rgba(239, 68, 68, 0.4)',
              borderRadius: '10px',
              padding: '10px 12px',
              color: '#b91c1c',
              fontSize: '12.5px',
              fontWeight: 700,
              fontFamily: 'var(--font-family, inherit)'
            }}
          >
            {error}
          </div>
        )}

        {/* Predictor Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '100%', boxSizing: 'border-box' }}>
          {/* Section 1: Demographics & Hospital Stay */}
          <div
            style={{
              background: 'rgba(255, 255, 255, 0.85)',
              border: '1.2px solid rgba(214, 214, 216, 0.9)',
              borderRadius: '14px',
              padding: '12px',
              boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
              width: '100%',
              boxSizing: 'border-box'
            }}
          >
            <div
              style={{
                fontSize: '12px',
                fontWeight: 800,
                color: '#000000',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                marginBottom: '10px',
                fontFamily: 'var(--font-family, inherit)'
              }}
            >
              1. Hospitalization &amp; Metrics
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '10px', width: '100%' }}>
              {/* Age */}
              <div style={{ minWidth: 0 }}>
                <label
                  htmlFor="cp-age"
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 800,
                    color: '#000000',
                    marginBottom: '4px',
                    lineHeight: 1.2,
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  Policyholder Age
                </label>
                <input
                  id="cp-age"
                  type="number"
                  min="18"
                  max="70"
                  value={formData.age}
                  onChange={(e) => handleChange('age', e.target.value)}
                  required
                  style={{
                    width: '100%',
                    height: '38px',
                    padding: '6px 10px',
                    borderRadius: '10px',
                    border: '1.5px solid rgba(214, 214, 216, 0.95)',
                    background: 'rgba(255, 255, 255, 0.9)',
                    fontSize: '14px',
                    fontWeight: 700,
                    color: '#000000',
                    outline: 'none',
                    boxSizing: 'border-box',
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                />
                <span
                  style={{
                    display: 'inline-block',
                    fontSize: '10.5px',
                    fontWeight: 700,
                    color: '#000000',
                    marginTop: '2px',
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  18 – 70 yrs
                </span>
              </div>

              {/* Days Hospitalised */}
              <div style={{ minWidth: 0 }}>
                <label
                  htmlFor="cp-days-hospitalised"
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 800,
                    color: '#000000',
                    marginBottom: '4px',
                    lineHeight: 1.2,
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  Days Hospitalised
                </label>
                <input
                  id="cp-days-hospitalised"
                  type="number"
                  min="0"
                  max="365"
                  value={formData.days_hospitalised}
                  onChange={(e) => handleChange('days_hospitalised', e.target.value)}
                  required
                  style={{
                    width: '100%',
                    height: '38px',
                    padding: '6px 10px',
                    borderRadius: '10px',
                    border: '1.5px solid rgba(214, 214, 216, 0.95)',
                    background: 'rgba(255, 255, 255, 0.9)',
                    fontSize: '14px',
                    fontWeight: 700,
                    color: '#000000',
                    outline: 'none',
                    boxSizing: 'border-box',
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                />
                <span
                  style={{
                    display: 'inline-block',
                    fontSize: '10.5px',
                    fontWeight: 700,
                    color: '#000000',
                    marginTop: '2px',
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  0 – 365 days
                </span>
              </div>

              {/* ICU Days */}
              <div style={{ minWidth: 0 }}>
                <label
                  htmlFor="cp-icu-days"
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 800,
                    color: '#000000',
                    marginBottom: '4px',
                    lineHeight: 1.2,
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  ICU Days
                </label>
                <input
                  id="cp-icu-days"
                  type="number"
                  min="0"
                  max="5"
                  value={formData.icu_days}
                  onChange={(e) => handleChange('icu_days', e.target.value)}
                  required
                  style={{
                    width: '100%',
                    height: '38px',
                    padding: '6px 10px',
                    borderRadius: '10px',
                    border: '1.5px solid rgba(214, 214, 216, 0.95)',
                    background: 'rgba(255, 255, 255, 0.9)',
                    fontSize: '14px',
                    fontWeight: 700,
                    color: '#000000',
                    outline: 'none',
                    boxSizing: 'border-box',
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                />
                <span
                  style={{
                    display: 'inline-block',
                    fontSize: '10.5px',
                    fontWeight: 700,
                    color: '#000000',
                    marginTop: '2px',
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  Max 5 days
                </span>
              </div>

              {/* Procedures Claimed */}
              <div style={{ minWidth: 0 }}>
                <label
                  htmlFor="cp-procedures"
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 800,
                    color: '#000000',
                    marginBottom: '4px',
                    lineHeight: 1.2,
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  Procedures Claimed
                </label>
                <input
                  id="cp-procedures"
                  type="number"
                  min="0"
                  max="50"
                  value={formData.procedures_claimed}
                  onChange={(e) => handleChange('procedures_claimed', e.target.value)}
                  required
                  style={{
                    width: '100%',
                    height: '38px',
                    padding: '6px 10px',
                    borderRadius: '10px',
                    border: '1.5px solid rgba(214, 214, 216, 0.95)',
                    background: 'rgba(255, 255, 255, 0.9)',
                    fontSize: '14px',
                    fontWeight: 700,
                    color: '#000000',
                    outline: 'none',
                    boxSizing: 'border-box',
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                />
                <span
                  style={{
                    display: 'inline-block',
                    fontSize: '10.5px',
                    fontWeight: 700,
                    color: '#000000',
                    marginTop: '2px',
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  0 – 50 count
                </span>
              </div>

              {/* Prior Daycare Claims */}
              <div style={{ gridColumn: 'span 2', minWidth: 0 }}>
                <label
                  htmlFor="cp-prior-daycare"
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 800,
                    color: '#000000',
                    marginBottom: '4px',
                    lineHeight: 1.2,
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  Prior Daycare Claims (Past Year)
                </label>
                <input
                  id="cp-prior-daycare"
                  type="number"
                  min="0"
                  max="20"
                  value={formData.prior_daycare_claims_year}
                  onChange={(e) => handleChange('prior_daycare_claims_year', e.target.value)}
                  required
                  style={{
                    width: '100%',
                    height: '38px',
                    padding: '6px 10px',
                    borderRadius: '10px',
                    border: '1.5px solid rgba(214, 214, 216, 0.95)',
                    background: 'rgba(255, 255, 255, 0.9)',
                    fontSize: '14px',
                    fontWeight: 700,
                    color: '#000000',
                    outline: 'none',
                    boxSizing: 'border-box',
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                />
                <span
                  style={{
                    display: 'inline-block',
                    fontSize: '10.5px',
                    fontWeight: 700,
                    color: '#000000',
                    marginTop: '2px',
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  0 – 20 procedures
                </span>
              </div>
            </div>
          </div>

          {/* Section 2: Policy & Status Flags (Liquid Glass Dropdowns) */}
          <div
            style={{
              background: 'rgba(255, 255, 255, 0.85)',
              border: '1.2px solid rgba(214, 214, 216, 0.9)',
              borderRadius: '14px',
              padding: '12px',
              boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
              width: '100%',
              boxSizing: 'border-box'
            }}
          >
            <div
              style={{
                fontSize: '12px',
                fontWeight: 800,
                color: '#000000',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                marginBottom: '10px',
                fontFamily: 'var(--font-family, inherit)'
              }}
            >
              2. Policy Scope &amp; Eligibility
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '10px', width: '100%' }}>
              {/* Plan Type Liquid Glass Dropdown */}
              <div style={{ minWidth: 0 }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 800,
                    color: '#000000',
                    marginBottom: '4px',
                    lineHeight: 1.2,
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  Plan Type
                </label>
                <LiquidGlassSelect
                  id="cp-plan"
                  value={formData.plan}
                  onChange={(val) => handleChange('plan', val)}
                  options={planOptions}
                  ariaLabel="Select Policy Plan Tier"
                />
              </div>

              {/* Claim Type Liquid Glass Dropdown */}
              <div style={{ minWidth: 0 }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 800,
                    color: '#000000',
                    marginBottom: '4px',
                    lineHeight: 1.2,
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  Claim Type
                </label>
                <LiquidGlassSelect
                  id="cp-claim-type"
                  value={formData.claim_type}
                  onChange={(val) => handleChange('claim_type', val)}
                  options={claimTypeOptions}
                  ariaLabel="Select Claim Type"
                />
              </div>

              {/* Extended Stay Flag Liquid Glass Dropdown */}
              <div style={{ minWidth: 0 }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 800,
                    color: '#000000',
                    marginBottom: '4px',
                    lineHeight: 1.2,
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  Extended Stay Flag
                </label>
                <LiquidGlassSelect
                  id="cp-extended-stay"
                  value={formData.extended_stay_flag}
                  onChange={(val) => handleChange('extended_stay_flag', val)}
                  options={extendedStayOptions}
                  ariaLabel="Select Extended Stay Flag"
                />
              </div>

              {/* Pre-existing Condition Liquid Glass Dropdown */}
              <div style={{ minWidth: 0 }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 800,
                    color: '#000000',
                    marginBottom: '4px',
                    lineHeight: 1.2,
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  Pre-existing Condition
                </label>
                <LiquidGlassSelect
                  id="cp-pre-existing"
                  value={formData.pre_existing}
                  onChange={(val) => handleChange('pre_existing', val)}
                  options={preExistingOptions}
                  ariaLabel="Select Pre-existing Condition Status"
                />
              </div>

              {/* Documents Complete Liquid Glass Dropdown */}
              <div style={{ gridColumn: 'span 2', minWidth: 0 }}>
                <label
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 800,
                    color: '#000000',
                    marginBottom: '4px',
                    lineHeight: 1.2,
                    fontFamily: 'var(--font-family, inherit)'
                  }}
                >
                  Documents Complete
                </label>
                <LiquidGlassSelect
                  id="cp-documents-complete"
                  value={formData.documents_complete}
                  onChange={(val) => handleChange('documents_complete', val)}
                  options={documentOptions}
                  ariaLabel="Select Documents Completeness"
                />
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '8px', marginTop: '6px', width: '100%', boxSizing: 'border-box' }}>
            <button
              type="submit"
              disabled={loading}
              className="auth-submit-btn"
              style={{
                flex: 2,
                margin: 0,
                padding: '10px 14px',
                minHeight: '40px',
                height: '40px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, #0284c7 0%, #007aff 100%)',
                boxShadow: '0 3px 10px rgba(0, 122, 255, 0.32)',
                fontSize: '13.5px',
                fontWeight: 800,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                cursor: loading ? 'not-allowed' : 'pointer',
                color: '#ffffff',
                fontFamily: 'var(--font-family, inherit)',
                boxSizing: 'border-box'
              }}
            >
              {loading ? (
                <>
                  <div
                    className="chat-submit-spinner"
                    style={{
                      width: '15px',
                      height: '15px',
                      borderWidth: '2.5px',
                      borderColor: 'rgba(255, 255, 255, 0.35)',
                      borderTopColor: '#ffffff',
                      flexShrink: 0
                    }}
                  />
                  <span>Predicting...</span>
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                  </svg>
                  <span>Predict Claim Payout</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleReset}
              disabled={loading}
              style={{
                flex: 1,
                padding: '10px 12px',
                minHeight: '40px',
                height: '40px',
                borderRadius: '10px',
                border: '1.2px solid rgba(214, 214, 216, 0.9)',
                background: '#ffffff',
                color: '#000000',
                fontSize: '13px',
                fontWeight: 700,
                cursor: 'pointer',
                fontFamily: 'var(--font-family, inherit)',
                boxSizing: 'border-box'
              }}
            >
              Reset
            </button>
          </div>
        </form>
      </div>
    </aside>
  );
}

export default ClaimPredictorDrawer;
