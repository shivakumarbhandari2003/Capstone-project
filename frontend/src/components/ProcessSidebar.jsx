import React from 'react';

/**
 * ProcessSidebar — Persistent Left Navigation Sidebar for Customer and Employee workspaces.
 * Follows the high-end executive pattern established in the Administrator Workspace:
 * - Professional vector SVG icons
 * - Active dot indicators & status pills
 * - Scope authorization footer
 * - Persistent green completion indicator for Stage 1 Eligibility
 * - Customer-only Stage 4 "Confirm & Review"
 */
export function ProcessSidebar({
  activeStage,
  selectedPlan,
  assessment,
  onNavigate,
  onBack,
  userRole,
  currentUser
}) {
  const isEmployee = userRole === 'employee';
  const isEligibilityCompleted = Boolean(
    assessment && (assessment.status === 'COMPLETED' || assessment.outcome)
  );
  const isPlanCompleted = Boolean(selectedPlan);
  // Only consider confirmed if the active selected plan is confirmed or user holds a confirmed plan
  const activeConfId = currentUser?.confirmed_plan_id || (currentUser?.is_confirmed ? selectedPlan?.plan_id : null);
  const isThisPlanConfirmed = Boolean(
    (selectedPlan?.is_confirmed || selectedPlan?.status === 'CONFIRMED') &&
    (selectedPlan?.confirmed_at || (activeConfId && selectedPlan?.plan_id === activeConfId))
  );
  const isConfirmed = isThisPlanConfirmed;

  const stages = [
    {
      id: 'eligibility',
      number: '1',
      title: 'Eligibility Criteria',
      desc: isEligibilityCompleted
        ? (isConfirmed ? 'Verified & Completed' : 'Completed')
        : 'Risk evaluation',
      badge: isEligibilityCompleted ? 'Completed' : null,
      badgeClass: isEligibilityCompleted ? 'gold' : null,
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <path d="M9 12l2 2 4-4" />
        </svg>
      ),
      disabled: false // Always accessible to view assessment parameters
    },
    {
      id: 'plans',
      number: '2',
      title: 'Choose Plan',
      desc: isConfirmed
        ? (selectedPlan ? `Chat Scope: ${selectedPlan.display_title || selectedPlan.plan_name}` : 'Visit any plan for chatbot')
        : (selectedPlan ? selectedPlan.plan_name : (isEmployee ? 'Select employee group plan' : 'Select active policy portfolio')),
      badge: selectedPlan ? (selectedPlan.display_title || selectedPlan.plan_category) : null,
      badgeClass: selectedPlan ? selectedPlan.plan_category?.toLowerCase() : null,
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
          <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
        </svg>
      ),
      disabled: !isEligibilityCompleted
    },
    {
      id: 'chat',
      number: '3',
      title: 'Policy Chat',
      desc: selectedPlan ? `Grounded Q&A (${selectedPlan.plan_id})` : 'Select a plan to start chat',
      badge: activeStage === 'chat' ? 'Active Scope' : null,
      badgeClass: 'active-stage',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          <line x1="9" y1="10" x2="15" y2="10" />
        </svg>
      ),
      disabled: !selectedPlan
    }
  ];

  // Stage 4: Confirm & Review (Always visible & available in reading mode)
  stages.push({
    id: 'confirm',
    number: '4',
    title: 'Confirm & Review',
    desc: isConfirmed
      ? 'Confirmed Policy Summary'
      : selectedPlan
      ? 'Review & finalize selection'
      : 'Select a plan first',
    badge: isConfirmed ? 'Confirmed' : (selectedPlan ? 'Under Review' : null),
    badgeClass: isConfirmed ? 'gold' : 'active-stage',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
    disabled: Boolean(!selectedPlan && !currentUser?.is_confirmed)
  });

  return (
    <aside className="process-sidebar" aria-label="Process Navigation">
      {/* Top Header of Sidebar: Back button on top left when in chat */}
      <div className="sidebar-top-header">
        {activeStage === 'chat' ? (
          <button
            type="button"
            className="sidebar-back-btn"
            onClick={onBack}
            title="Back"
            aria-label="Back"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12"></line>
              <polyline points="12 19 5 12 12 5"></polyline>
            </svg>
            <span>Back</span>
          </button>
        ) : (
          <div className="sidebar-brand-mark">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span>Policy Assistant</span>
          </div>
        )}
      </div>

      <nav className="process-nav-list" role="navigation">
        {stages.map((stage) => {
          const isActive = activeStage === stage.id;
          let isCompleted = false;
          if (stage.id === 'eligibility') {
            isCompleted = isEligibilityCompleted;
          } else if (stage.id === 'plans') {
            isCompleted = isPlanCompleted && (activeStage === 'chat' || activeStage === 'confirm');
          } else if (stage.id === 'confirm') {
            isCompleted = isConfirmed;
          }

          return (
            <button
              key={stage.id}
              type="button"
              className={`process-nav-item ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''} ${stage.disabled ? 'disabled' : ''}`}
              onClick={() => !stage.disabled && onNavigate(stage.id)}
              disabled={stage.disabled}
              title={
                stage.disabled
                  ? isConfirmed && (stage.id === 'eligibility' || stage.id === 'confirm')
                    ? 'Locked: Only one insurance policy can be taken from the company.'
                    : stage.id === 'confirm'
                    ? 'Select a plan first to unlock Confirm & Review'
                    : 'Complete previous stage first'
                  : stage.title
              }
              aria-current={isActive ? 'step' : undefined}
            >
              <div className="process-nav-icon-col">
                <div className={`process-step-circle ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}>
                  {isCompleted ? (
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : (
                    stage.icon
                  )}
                </div>
              </div>

              <div className="process-nav-info" style={{ display: 'flex', flexDirection: 'column', minWidth: 0, gap: '2px' }}>
                <div className="process-nav-title-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '4px', minWidth: 0 }}>
                  <span className="process-nav-title" style={{ fontSize: '13px', fontWeight: 700, color: 'inherit' }}>
                    {stage.title}
                  </span>
                  {isActive && !isCompleted && !isConfirmed && (
                    <span className="admin-active-dot" aria-hidden="true" style={{ marginLeft: 'auto', flexShrink: 0 }}>•</span>
                  )}
                </div>

                {stage.id === 'eligibility' && isCompleted ? (
                  <div style={{ display: 'flex', alignItems: 'center', marginTop: '2px' }}>
                    <span
                      style={{
                        fontSize: '10.5px',
                        fontWeight: 700,
                        color: '#059669',
                        background: 'rgba(16, 185, 129, 0.12)',
                        border: '1px solid rgba(16, 185, 129, 0.3)',
                        padding: '1px 8px',
                        borderRadius: '9999px',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '3px',
                        lineHeight: 1.2
                      }}
                    >
                      ✓ Completed
                    </span>
                  </div>
                ) : stage.id === 'confirm' && isConfirmed ? (
                  <div style={{ display: 'flex', alignItems: 'center', marginTop: '2px' }}>
                    <span
                      style={{
                        fontSize: '10.5px',
                        fontWeight: 700,
                        color: '#059669',
                        background: 'rgba(16, 185, 129, 0.12)',
                        border: '1px solid rgba(16, 185, 129, 0.3)',
                        padding: '1px 8px',
                        borderRadius: '9999px',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '3px',
                        lineHeight: 1.2
                      }}
                    >
                      ✓ Confirmed
                    </span>
                  </div>
                ) : null}
              </div>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}

export default ProcessSidebar;
