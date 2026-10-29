import React, { useState, useEffect } from 'react';

const formatHighlight = (text) => {
  if (!text) return '';
  return text
    .replace(/[₹\u20B9]/g, 'Rs. ')
    .replace(/\u00e2\u201a\u00b9/g, 'Rs. ')
    .replace(/\u00e2\u0082\u00b9/g, 'Rs. ')
    .replace(/â‚¹/g, 'Rs. ')
    .replace(/â\u0082¹/g, 'Rs. ')
    .replace(/Ã¢â‚¬â„¢/g, 'Rs. ')
    .replace(/â€“/g, '–')
    .replace(/â€”/g, '—')
    .replace(/Rs\.\s*(\d)/g, 'Rs. $1');
};

export function PlanSelectionScreen({
  userRole,
  authToken,
  onSelectPlan,
  onUnauthorized,
  isConfirmed = false,
  confirmedPlanId = null
}) {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submittingPlanId, setSubmittingPlanId] = useState(null);
  const [hoveredId, setHoveredId] = useState(null);

  useEffect(() => {
    fetchPlans();
  }, [userRole, authToken]);

  const handlePlanClick = async (p) => {
    if (submittingPlanId) return;
    setSubmittingPlanId(p.plan_id);
    setError(null);
    try {
      await onSelectPlan(p);
    } catch (err) {
      setError(err.message || 'Plan selection rejected. An active eligible assessment is required.');
    } finally {
      setSubmittingPlanId(null);
    }
  };

  const fetchPlans = async () => {
    setLoading(true);
    setError(null);
    try {
      const headers = {};
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }
      let res;
      try {
        res = await fetch('/api/plans', { headers });
      } catch {
        res = await fetch('http://127.0.0.1:8000/api/plans', { headers });
      }

      if (res.status === 401 && onUnauthorized) {
        onUnauthorized();
        return;
      }
      const text = await res.text();
      let data = {};
      if (text) {
        try { data = JSON.parse(text); } catch { data = { detail: text }; }
      }
      if (!res.ok) {
        throw new Error(data.detail || `Failed to load plans: HTTP ${res.status}`);
      }
      setPlans(data.plans || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getPlanTheme = (planId = '') => {
    const id = planId.toUpperCase();
    if (id.includes('BASIC')) {
      return {
        tag: 'Essential Protection',
        isPopular: false,
        accentColor: '#007aff',
        iconBg: 'rgba(0, 122, 255, 0.1)',
        checkBg: 'rgba(0, 122, 255, 0.1)',
        checkColor: '#007aff',
        buttonGradient: 'linear-gradient(135deg, #0284c7 0%, #007aff 100%)',
        buttonShadow: '0 6px 20px rgba(0, 122, 255, 0.28)',
        hoverBorder: 'rgba(0, 122, 255, 0.45)',
        hoverShadow: '0 24px 50px -12px rgba(0, 122, 255, 0.2)',
        icon: (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#007aff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        )
      };
    }
    if (id.includes('GOLD')) {
      return {
        tag: 'Recommended Choice',
        isPopular: true,
        accentColor: '#d97706',
        iconBg: 'rgba(245, 158, 11, 0.12)',
        checkBg: 'rgba(245, 158, 11, 0.14)',
        checkColor: '#d97706',
        buttonGradient: 'linear-gradient(135deg, #d97706 0%, #f59e0b 100%)',
        buttonShadow: '0 6px 20px rgba(245, 158, 11, 0.35)',
        hoverBorder: 'rgba(245, 158, 11, 0.55)',
        hoverShadow: '0 24px 50px -12px rgba(245, 158, 11, 0.24)',
        icon: (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#d97706" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
        )
      };
    }
    if (id.includes('PREM')) {
      return {
        tag: 'Maximum Coverage',
        isPopular: false,
        accentColor: '#7c3aed',
        iconBg: 'rgba(124, 58, 237, 0.1)',
        checkBg: 'rgba(124, 58, 237, 0.12)',
        checkColor: '#7c3aed',
        buttonGradient: 'linear-gradient(135deg, #7c3aed 0%, #6366f1 100%)',
        buttonShadow: '0 6px 20px rgba(124, 58, 237, 0.3)',
        hoverBorder: 'rgba(124, 58, 237, 0.45)',
        hoverShadow: '0 24px 50px -12px rgba(124, 58, 237, 0.2)',
        icon: (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 3h12l4 6-10 13L2 9z" />
            <path d="M11 3 8 9l4 13 4-13-3-6" />
          </svg>
        )
      };
    }
    return {
      tag: 'Corporate Group',
      isPopular: false,
      accentColor: '#059669',
      iconBg: 'rgba(16, 185, 129, 0.12)',
      checkBg: 'rgba(16, 185, 129, 0.14)',
      checkColor: '#059669',
      buttonGradient: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
      buttonShadow: '0 6px 20px rgba(16, 185, 129, 0.3)',
      hoverBorder: 'rgba(16, 185, 129, 0.45)',
      hoverShadow: '0 24px 50px -12px rgba(16, 185, 129, 0.2)',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
          <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
        </svg>
      )
    };
  };

  return (
    <div style={{ maxWidth: '1180px', margin: '0 auto', padding: '20px 16px 48px' }}>
      {/* Modern Designer Header */}
      <div style={{ textAlign: 'center', marginBottom: '36px' }}>
        <h1
          style={{
            fontSize: '30px',
            fontWeight: 800,
            color: '#0f172a',
            letterSpacing: '-0.025em',
            margin: '0 0 8px 0'
          }}
        >
          Choose Your Insurance Plan
        </h1>
        <p style={{ fontSize: '15.5px', color: '#64748b', margin: 0 }}>
          {isConfirmed
            ? 'You have confirmed your policy. You can visit and chat with any plan to explore coverage details.'
            : 'Select a policy tier to start chatting with your personalized AI assistant.'}
        </p>
      </div>

      {loading && (
        <div
          style={{
            textAlign: 'center',
            padding: '64px 24px',
            background: 'rgba(255, 255, 255, 0.8)',
            borderRadius: '24px',
            border: '1.5px solid rgba(255, 255, 255, 0.9)',
            backdropFilter: 'blur(16px)',
            boxShadow: '0 10px 30px rgba(0, 0, 0, 0.04)'
          }}
        >
          <div className="auth-spinner" style={{ margin: '0 auto 16px' }} />
          <span style={{ color: '#475569', fontSize: '15px', fontWeight: 600 }}>Loading available insurance plans...</span>
        </div>
      )}

      {error && (
        <div
          className="auth-error-banner"
          role="alert"
          style={{
            marginBottom: '24px',
            padding: '14px 20px',
            borderRadius: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}
        >
          <span><strong>Error loading plans:</strong> {error}</span>
          <button
            className="admin-retry-btn"
            onClick={fetchPlans}
            style={{ padding: '6px 14px', borderRadius: '10px' }}
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && (
        <div
          className={plans.length === 4 ? "plans-grid-2x2" : "plans-grid-auto"}
          style={{
            display: 'grid',
            gridTemplateColumns: plans.length === 4
              ? 'repeat(2, minmax(0, 1fr))'
              : 'repeat(auto-fit, minmax(310px, 1fr))',
            gap: '28px',
            alignItems: 'stretch'
          }}
        >
          {plans.map((p) => {
            const isEmployeePlan = p.plan_id === 'EMP-INS-001';
            const theme = getPlanTheme(p.plan_id);
            const isHovered = hoveredId === p.plan_id;

            return (
              <div
                key={p.plan_id}
                onMouseEnter={() => setHoveredId(p.plan_id)}
                onMouseLeave={() => setHoveredId(null)}
                style={{
                  position: 'relative',
                  background: 'linear-gradient(175deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.92) 100%)',
                  backdropFilter: 'blur(28px)',
                  WebkitBackdropFilter: 'blur(28px)',
                  border: isHovered
                    ? `1.5px solid ${theme.hoverBorder}`
                    : theme.isPopular
                    ? '1.5px solid rgba(245, 158, 11, 0.45)'
                    : '1.5px solid rgba(255, 255, 255, 0.95)',
                  borderRadius: '26px',
                  padding: '32px 26px 28px 26px',
                  boxShadow: isHovered
                    ? theme.hoverShadow
                    : theme.isPopular
                    ? '0 20px 48px -12px rgba(245, 158, 11, 0.18), 0 2px 8px rgba(0, 0, 0, 0.03)'
                    : '0 16px 36px -12px rgba(0, 0, 0, 0.06), 0 2px 8px rgba(0, 0, 0, 0.02)',
                  display: 'flex',
                  flexDirection: 'column',
                  transition: 'all 0.28s cubic-bezier(0.16, 1, 0.3, 1)',
                  transform: isHovered ? 'translateY(-6px)' : 'translateY(0)'
                }}
              >
                {/* Confirmed Policy Badge */}
                {isConfirmed && p.plan_id === confirmedPlanId && (
                  <div
                    style={{
                      position: 'absolute',
                      top: '-13px',
                      right: '24px',
                      background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
                      color: '#ffffff',
                      padding: '4px 14px',
                      borderRadius: '9999px',
                      fontSize: '11px',
                      fontWeight: 800,
                      letterSpacing: '0.04em',
                      textTransform: 'uppercase',
                      boxShadow: '0 4px 14px rgba(16, 185, 129, 0.4)',
                      zIndex: 3,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px'
                    }}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <span>Confirmed Policy</span>
                  </div>
                )}

                {/* Most Popular Floating Badge for Gold */}
                {theme.isPopular && (!isConfirmed || p.plan_id !== confirmedPlanId) && (
                  <div
                    style={{
                      position: 'absolute',
                      top: '-13px',
                      left: '50%',
                      transform: 'translateX(-50%)',
                      background: 'linear-gradient(135deg, #d97706 0%, #f59e0b 100%)',
                      color: '#ffffff',
                      padding: '4px 16px',
                      borderRadius: '9999px',
                      fontSize: '11px',
                      fontWeight: 800,
                      letterSpacing: '0.06em',
                      textTransform: 'uppercase',
                      boxShadow: '0 4px 14px rgba(245, 158, 11, 0.4)',
                      zIndex: 2
                    }}
                  >
                    Most Popular
                  </div>
                )}

                {/* Plan Title */}
                <h3
                  style={{
                    fontSize: '22px',
                    fontWeight: 800,
                    color: '#0f172a',
                    margin: '0 0 14px 0',
                    letterSpacing: '-0.02em'
                  }}
                >
                  {p.plan_name.replace('–', '-')}
                </h3>

                <p
                  style={{
                    fontSize: '13.5px',
                    color: '#64748b',
                    lineHeight: 1.5,
                    margin: '0 0 20px 0',
                    minHeight: '40px'
                  }}
                >
                  {p.description}
                </p>

                {/* Benefits / Coverage Highlights */}
                <div
                  style={{
                    borderTop: '1px solid rgba(226, 232, 240, 0.8)',
                    paddingTop: '18px',
                    marginBottom: '24px',
                    flex: 1
                  }}
                >
                  <span
                    style={{
                      fontSize: '14px',
                      fontWeight: 800,
                      color: '#000000',
                      letterSpacing: '0.03em',
                      textTransform: 'uppercase',
                      display: 'block',
                      marginBottom: '14px'
                    }}
                  >
                    Coverage Highlights
                  </span>
                  <ul
                    style={{
                      listStyle: 'none',
                      margin: 0,
                      padding: 0,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '12px'
                    }}
                  >
                    {p.highlights && p.highlights.map((h, idx) => (
                      <li
                        key={idx}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '11px',
                          fontSize: '15.5px',
                          color: '#1e293b',
                          lineHeight: 1.5,
                          fontWeight: 500
                        }}
                      >
                        <div
                          style={{
                            width: '22px',
                            height: '22px',
                            borderRadius: '50%',
                            background: theme.checkBg,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                            marginTop: '1.5px'
                          }}
                        >
                          <svg
                            width="13"
                            height="13"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke={theme.checkColor}
                            strokeWidth="3"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                        </div>
                        <span>{formatHighlight(h)}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {isEmployeePlan && (
                  <div
                    style={{
                      marginBottom: '16px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 12px',
                      borderRadius: '12px',
                      background: 'rgba(245, 158, 11, 0.08)',
                      border: '1px solid rgba(245, 158, 11, 0.2)',
                      fontSize: '12px',
                      color: '#b45309'
                    }}
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                      <line x1="12" y1="9" x2="12" y2="13" />
                      <line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                    <span>Contains illustrative corporate demonstration schedules.</span>
                  </div>
                )}

                {/* Primary Designer Action Button */}
                <button
                  type="button"
                  className="auth-submit-btn"
                  style={{
                    width: '100%',
                    minHeight: '48px',
                    borderRadius: '14px',
                    background: theme.buttonGradient,
                    boxShadow: theme.buttonShadow,
                    color: '#ffffff',
                    fontSize: '15px',
                    fontWeight: 700,
                    border: 'none',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    marginTop: 'auto',
                    transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)'
                  }}
                  onClick={() => handlePlanClick(p)}
                  disabled={submittingPlanId === p.plan_id}
                >
                  {submittingPlanId === p.plan_id ? (
                    <span>{userRole === 'employee' ? 'Opening Chatbot...' : 'Opening Review...'}</span>
                  ) : (
                    <>
                      <span>
                        {isConfirmed && p.plan_id === confirmedPlanId
                          ? 'View Confirmed Plan / Chat'
                          : userRole === 'employee'
                          ? `Explore ${p.display_title || 'Plan'} / Chat`
                          : `Review & Confirm ${p.display_title || 'Plan'}`}
                      </span>
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="5" y1="12" x2="19" y2="12" />
                        <polyline points="12 5 19 12 12 19" />
                      </svg>
                    </>
                  )}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default PlanSelectionScreen;
