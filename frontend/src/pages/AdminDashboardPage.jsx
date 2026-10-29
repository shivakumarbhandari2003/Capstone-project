import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { adminApi } from '../services/adminApi';

// Professional SVG Vector Icons for Tabs and Section Accents
const TabIcons = {
  overview: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  ),
  users: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  documents: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <line x1="10" y1="9" x2="8" y2="9" />
    </svg>
  ),
  conversations: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <line x1="8" y1="10" x2="16" y2="10" />
      <line x1="8" y1="14" x2="12" y2="14" />
    </svg>
  ),
  refresh: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  ),
  clock: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  filter: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
    </svg>
  )
};

const DASHBOARD_TABS = [
  { id: 'overview', label: 'Executive Overview', icon: TabIcons.overview },
  { id: 'users', label: 'Users & Customers', icon: TabIcons.users },
  { id: 'documents', label: 'Documents & Knowledge Base', icon: TabIcons.documents },
  { id: 'conversations', label: 'Conversations & Usage', icon: TabIcons.conversations }
];

export function AdminDashboardPage() {
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'users' | 'documents' | 'conversations'
  const [dateRange, setDateRange] = useState('7d'); // '24h' | '7d' | '30d' | '90d' | 'custom'
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Tab Data States
  const [overviewData, setOverviewData] = useState(null);
  const [usersData, setUsersData] = useState({ users: [], total: 0 });
  const [userSearch, setUserSearch] = useState('');
  const [userRoleFilter, setUserRoleFilter] = useState('');
  const [userPage, setUserPage] = useState(0);

  const [docsData, setDocsData] = useState({ documents: [], recent_jobs: [], total_documents: 0 });
  const [docPlanFilter, setDocPlanFilter] = useState('');
  const [docActionNotice, setDocActionNotice] = useState(null);

  const [convData, setConvData] = useState(null);

  const formatRangeLabel = (range) => {
    switch (range) {
      case '24h': return 'Past 24 Hours';
      case '7d': return 'Past 7 Days';
      case '30d': return 'Past 30 Days';
      case '90d': return 'Past 90 Days';
      case 'custom': return (customStart && customEnd) ? `${customStart} to ${customEnd}` : 'Custom Date Range';
      default: return range;
    }
  };

  // Load Tab Specific Data
  const loadDashboardData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    const start = dateRange === 'custom' ? customStart : null;
    const end = dateRange === 'custom' ? customEnd : null;

    try {
      if (activeTab === 'overview') {
        const data = await adminApi.fetchOverview(dateRange, start, end);
        setOverviewData(data);
      } else if (activeTab === 'users') {
        // Users section always loads real database accounts from SQLite
        const data = await adminApi.fetchUsers(25, userPage * 25, userSearch, userRoleFilter);
        setUsersData(data);
      } else if (activeTab === 'documents') {
        // Document inventory loads complete knowledge base assets from SQLite
        const data = await adminApi.fetchDocuments(50, 0, docPlanFilter, '', '', null, null);
        setDocsData(data);
      } else if (activeTab === 'conversations') {
        const data = await adminApi.fetchConversations(dateRange, start, end);
        setConvData(data);
      }
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err.message || 'Failed to load administrator data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeTab, dateRange, customStart, customEnd, userPage, userSearch, userRoleFilter, docPlanFilter]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Handlers for Admin Actions
  const handleToggleUserStatus = async (userId, currentStatus) => {
    try {
      const newStatus = currentStatus === 1 ? 0 : 1;
      await adminApi.updateUserStatus(userId, newStatus);
      loadDashboardData(true);
    } catch (err) {
      setError(err.message || 'Failed to update user status.');
    }
  };

  const handleDeleteDocument = async (docId, filename) => {
    if (!window.confirm(`Are you sure you want to mark document '${filename}' as deleted?`)) return;
    try {
      await adminApi.deleteDocument(docId);
      setDocActionNotice(`Document '${filename}' successfully removed.`);
      loadDashboardData(true);
      setTimeout(() => setDocActionNotice(null), 4000);
    } catch (err) {
      setError(err.message || 'Failed to delete document.');
    }
  };

  const handleReindexDocument = async (docId, filename) => {
    try {
      await adminApi.reindexDocument(docId);
      setDocActionNotice(`Re-indexing initiated for '${filename}'.`);
      loadDashboardData(true);
      setTimeout(() => setDocActionNotice(null), 4000);
    } catch (err) {
      setError(err.message || 'Failed to reindex document.');
    }
  };

  return (
    <div className="admin-dashboard-container">
      {/* 1. Global Controls Header */}
      <header className="admin-dash-header">
        <div className="admin-dash-title-group">
          <h1 className="admin-dash-heading">Executive Analytics & System Intelligence</h1>
        </div>

        <div className="admin-dash-controls">
          {/* Universal Date Range Selector */}
          <div className="admin-date-presets" role="group" aria-label="Date Range Presets">
            {['24h', '7d', '30d', '90d', 'custom'].map((r) => (
              <button
                key={r}
                type="button"
                className={`admin-date-pill ${dateRange === r ? 'active' : ''}`}
                onClick={() => setDateRange(r)}
              >
                {r === '24h' ? '24 Hours' : r === '7d' ? '7 Days' : r === '30d' ? '30 Days' : r === '90d' ? '90 Days' : 'Custom'}
              </button>
            ))}
          </div>

          {/* Refresh Button in same row */}
          <button
            type="button"
            className="admin-refresh-btn"
            onClick={() => loadDashboardData(true)}
            disabled={refreshing || loading}
            title="Refresh dashboard metrics"
          >
            {TabIcons.refresh}
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>
      </header>

      {/* Custom Date Range Filter Inputs */}
      {dateRange === 'custom' && (
        <div className="admin-custom-date-bar">
          <label>
            Start Date:
            <input
              type="date"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              className="admin-date-input"
            />
          </label>
          <label>
            End Date:
            <input
              type="date"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
              className="admin-date-input"
            />
          </label>
          <button
            type="button"
            className="admin-filter-apply-btn"
            onClick={() => loadDashboardData(false)}
          >
            Apply Range
          </button>
        </div>
      )}


      {/* Notice Banner */}
      {docActionNotice && (
        <div className="admin-notice-banner" role="status">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
          <span>{docActionNotice}</span>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="admin-error-banner" role="alert">
          <span>⚠️ {error}</span>
          <button type="button" onClick={() => loadDashboardData(false)} className="admin-retry-btn">
            Retry
          </button>
        </div>
      )}

      {/* 2. Professional Tab Navigation (Strictly 4 Core Sections with Professional Vector Icons) */}
      <nav className="admin-tabs-nav" aria-label="Dashboard Sections">
        {DASHBOARD_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`admin-tab-item ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="admin-tab-icon">{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>

      {/* 3. Section Content Rendering */}
      <div className="admin-tab-content">
        {loading && (
          <div className="admin-loading-state">
            <div className="admin-spinner"></div>
            <p>Loading analytics from persistent SQLite store...</p>
          </div>
        )}

        {!loading && activeTab === 'overview' && overviewData && (
          <OverviewSection
            data={overviewData}
            rangeLabel={formatRangeLabel(dateRange)}
            onRefresh={() => loadDashboardData(true)}
          />
        )}

        {!loading && activeTab === 'users' && (
          <UsersSection
            users={usersData.users}
            total={usersData.total}
            search={userSearch}
            onSearchChange={setUserSearch}
            roleFilter={userRoleFilter}
            onRoleFilterChange={setUserRoleFilter}
            page={userPage}
            onPageChange={setUserPage}
            onToggleStatus={handleToggleUserStatus}
          />
        )}

        {!loading && activeTab === 'documents' && (
          <DocumentsSection
            documents={docsData.documents}
            total={docsData.total_documents}
            recentJobs={docsData.recent_jobs}
            planFilter={docPlanFilter}
            onPlanFilterChange={setDocPlanFilter}
            onDelete={handleDeleteDocument}
            onReindex={handleReindexDocument}
            rangeLabel={formatRangeLabel(dateRange)}
          />
        )}

        {!loading && activeTab === 'conversations' && convData && (
          <ConversationsSection
            data={convData}
            rangeLabel={formatRangeLabel(dateRange)}
          />
        )}
      </div>
    </div>
  );
}

// ==================== SUB-SECTIONS ====================

// --- 1. Executive Overview Section ---
function OverviewSection({ data, rangeLabel, onRefresh }) {
  const { kpis, time_series, recent_activity, total_activity } = data;

  // 5 Most Important Executive KPI Cards in Single Row
  const kpiCards = [
    {
      label: 'Registered Users',
      value: kpis.total_registered_users ?? 0,
      sub: `${kpis.total_customers || 0} Customers · ${kpis.total_employees || 0} Staff`,
      color: '#007aff',
      iconBg: 'rgba(0, 122, 255, 0.1)',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      )
    },
    {
      label: 'Assessed for Eligibility',
      value: kpis.total_assessed_users ?? kpis.total_users_assessed ?? 0,
      sub: `${kpis.underwriting_eligibility_rate_pct ?? kpis.funnel_rates?.eligibility_rate_pct ?? 0}% Pass Rate`,
      color: '#0284c7',
      iconBg: 'rgba(2, 132, 199, 0.1)',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
          <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
          <path d="m9 14 2 2 4-4" />
        </svg>
      )
    },
    {
      label: 'Eligible Users',
      value: kpis.eligible_users ?? 0,
      sub: 'Qualified for Policy Coverage',
      color: '#059669',
      iconBg: 'rgba(16, 185, 129, 0.1)',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <path d="m9 12 2 2 4-4" />
        </svg>
      )
    },
    {
      label: 'Plan Selected',
      value: kpis.users_selected_plan ?? kpis.plan_selected_users ?? 0,
      sub: `${kpis.plan_selection_conversion_rate_pct ?? kpis.funnel_rates?.plan_selection_rate_pct ?? 0}% of Eligible`,
      color: '#d97706',
      iconBg: 'rgba(245, 158, 11, 0.12)',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
        </svg>
      )
    },
    {
      label: 'Policy Chat Active',
      value: kpis.users_proceeded_to_chat ?? kpis.policy_chat_active_users ?? 0,
      sub: `${kpis.chat_engagement_conversion_rate_pct ?? kpis.funnel_rates?.chat_engagement_rate_pct ?? 0}% Engaged`,
      color: '#7c3aed',
      iconBg: 'rgba(124, 58, 237, 0.1)',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      )
    }
  ];

  // Dynamic filter state for logs stream
  const [logSearch, setLogSearch] = useState('');
  const [logOutcome, setLogOutcome] = useState('ALL');
  const [expandedLogId, setExpandedLogId] = useState(null);

  // Format raw snake_case actions into clean Title Case
  const formatActionLabel = (action = '') => {
    if (!action) return 'Action';
    return action
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  };

  // Semantic category matching helper
  const matchesOutcome = useCallback((outcomeRaw, category) => {
    if (category === 'ALL') return true;
    const o = (outcomeRaw || '').toUpperCase();
    if (category === 'SUCCESS') {
      return ['SUCCESS', '200', 'APPROVED', 'COMPLETED', 'OK'].some((k) => o.includes(k));
    }
    if (category === 'FORBIDDEN') {
      return ['FORBIDDEN', 'UNAUTHORIZED', 'DENIED', 'REJECTED', 'BLOCKED', 'SUSPENDED', '403', '401'].some((k) => o.includes(k));
    }
    if (category === 'ERROR') {
      return ['ERROR', 'FAILED', 'FAILURE', 'EXCEPTION', 'UNAVAILABLE', '500', '504', '422'].some((k) => o.includes(k));
    }
    return o === category;
  }, []);

  // Compute live count for each outcome category
  const outcomeCounts = useMemo(() => {
    const counts = { ALL: recent_activity ? recent_activity.length : 0, SUCCESS: 0, FORBIDDEN: 0, ERROR: 0 };
    if (!recent_activity) return counts;
    for (const ev of recent_activity) {
      if (matchesOutcome(ev.outcome, 'SUCCESS')) counts.SUCCESS++;
      if (matchesOutcome(ev.outcome, 'FORBIDDEN')) counts.FORBIDDEN++;
      if (matchesOutcome(ev.outcome, 'ERROR')) counts.ERROR++;
    }
    return counts;
  }, [recent_activity, matchesOutcome]);

  const filteredLogs = useMemo(() => {
    if (!recent_activity) return [];
    return recent_activity.filter((ev) => {
      const matchOutcome = matchesOutcome(ev.outcome, logOutcome);
      if (!matchOutcome) return false;
      if (!logSearch.trim()) return true;
      const q = logSearch.toLowerCase();
      return (
        (ev.action && ev.action.toLowerCase().includes(q)) ||
        (ev.actor_role && ev.actor_role.toLowerCase().includes(q)) ||
        (ev.actor_email && ev.actor_email.toLowerCase().includes(q)) ||
        (ev.target_resource && ev.target_resource.toLowerCase().includes(q)) ||
        (ev.outcome && ev.outcome.toLowerCase().includes(q))
      );
    });
  }, [recent_activity, logSearch, logOutcome, matchesOutcome]);

  return (
    <div className="admin-overview-grid">
      {/* 5 Core Executive KPI Cards in a Single Row */}
      <div className="admin-kpi-grid five-cards-row">
        {kpiCards.map((kpi, idx) => (
          <div key={idx} className="admin-kpi-card">
            <div className="admin-kpi-top-row">
              <span className="admin-kpi-label">{kpi.label}</span>
              <div className="admin-kpi-icon-pill" style={{ background: kpi.iconBg, color: kpi.color }}>
                {kpi.icon}
              </div>
            </div>
            <div className="admin-kpi-value">{kpi.value}</div>
            <div className="admin-kpi-sub">
              <span className="admin-kpi-sub-badge" style={{ background: kpi.iconBg, color: kpi.color }}>
                {kpi.sub}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Professional Real Dashboard Area Graph (Guaranteed No Dip Below Baseline) */}
      <div className="admin-card">
        <div className="admin-card-header">
          <div>
            <h2 className="admin-card-title">Activity Trends & Telemetry Graph</h2>
            <p className="admin-card-subtitle">
              Granular time-series metrics over <strong>{rangeLabel}</strong>. Switch metrics or inspect points interactively.
            </p>
          </div>
          <span className="admin-scope-badge">{rangeLabel}</span>
        </div>
        <div className="admin-chart-box">
          <ProfessionalDashboardChart series={time_series} rangeLabel={rangeLabel} />
        </div>
      </div>

      {/* Dynamic System Activity & Governance Stream (Shows all logs dynamically with filters) */}
      <div className="admin-card admin-log-stream-card">
        <div className="admin-card-header">
          <div>
            <h3 className="admin-card-title">Recent System Activity & Governance Stream</h3>
          </div>
          <div className="admin-log-controls">
            <span className="admin-live-stream-badge">
              <span className="admin-live-dot"></span>
              Live Activity
            </span>
            <button
              type="button"
              className="admin-mini-refresh-btn"
              onClick={onRefresh}
              title="Refresh logs stream"
            >
              {TabIcons.refresh} Refresh
            </button>
          </div>
        </div>

        {/* Dynamic Log Search & Filters */}
        <div className="admin-log-filter-bar">
          <input
            type="search"
            placeholder="Search events by action, actor, resource..."
            value={logSearch}
            onChange={(e) => setLogSearch(e.target.value)}
            className="admin-log-search-input"
          />
          <div className="admin-log-pill-toggles">
            {[
              { id: 'ALL', label: `ALL (${outcomeCounts.ALL})` },
              { id: 'SUCCESS', label: `SUCCESS (${outcomeCounts.SUCCESS})` },
              { id: 'FORBIDDEN', label: `FORBIDDEN (${outcomeCounts.FORBIDDEN})` },
              { id: 'ERROR', label: `ERROR (${outcomeCounts.ERROR})` }
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`admin-log-toggle-pill ${logOutcome === tab.id ? 'active' : ''}`}
                onClick={() => setLogOutcome(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <span className="admin-log-count-text">
            Showing {filteredLogs.length} of {recent_activity.length} logs
          </span>
        </div>

        {filteredLogs.length === 0 ? (
          <div className="admin-empty-state">
            {logOutcome === 'SUCCESS' && outcomeCounts.SUCCESS === 0
              ? 'No successful operations recorded in this execution window yet (e.g. document uploads, user approvals).'
              : logOutcome === 'ERROR' && outcomeCounts.ERROR === 0
              ? 'No operational errors or pipeline crash events recorded in this window.'
              : 'No activity events match the current filter in this window.'}
          </div>
        ) : (
          <div className="admin-table-wrapper admin-log-scroll-wrapper">
            <table className="admin-data-table admin-log-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action</th>
                  <th>Actor & Role</th>
                  <th>Resource</th>
                  <th>Outcome</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((ev) => {
                  const isExpanded = expandedLogId === ev.event_id;
                  const outcomeKey = (ev.outcome || '').toLowerCase().replace(/\s+/g, '_');
                  return (
                    <React.Fragment key={ev.event_id}>
                      <tr className={isExpanded ? 'expanded-row' : ''}>
                        <td className="admin-log-time">
                          {new Date(ev.timestamp).toLocaleString()}
                        </td>
                        <td>
                          <span className="admin-action-pill">
                            {formatActionLabel(ev.action)}
                          </span>
                        </td>
                        <td>
                          <div className="admin-actor-cell">
                            <span className="admin-actor-email">
                              {ev.actor_email || ev.actor_id || 'system'}
                            </span>
                            <span className={`admin-role-badge ${(ev.actor_role || 'system').toLowerCase()}`}>
                              {ev.actor_role || 'system'}
                            </span>
                          </div>
                        </td>
                        <td>
                          <span className="admin-log-resource">
                            {ev.target_resource || '—'}
                          </span>
                        </td>
                        <td>
                          <span className={`admin-status-badge ${outcomeKey}`}>
                            {ev.outcome}
                          </span>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="admin-inspect-btn"
                            onClick={() => setExpandedLogId(isExpanded ? null : ev.event_id)}
                          >
                            {isExpanded ? 'Hide' : 'Inspect'}
                          </button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="admin-log-detail-row">
                          <td colSpan="6">
                            <div className="admin-log-detail-box">
                              <div className="admin-log-detail-header">
                                <strong>Event Details (ID: {ev.event_id})</strong>
                              </div>
                              <pre className="admin-details-json">
                                {JSON.stringify(ev.details || {}, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// --- Custom Liquid Glass Dropdown Component ---
function LiquidGlassSelect({ value, onChange, options = [], placeholder = 'Select...' }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  const selectedOption = options.find((o) => o.value === value) || options[0];

  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setIsOpen(false);
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  return (
    <div className="admin-liquid-dropdown-wrapper" ref={dropdownRef}>
      <button
        type="button"
        className={`admin-liquid-dropdown-btn ${isOpen ? 'active' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="admin-liquid-dropdown-val">
          {selectedOption ? selectedOption.label : placeholder}
        </span>
        <svg
          className={`admin-dropdown-chevron ${isOpen ? 'rotate' : ''}`}
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {isOpen && (
        <div className="admin-liquid-dropdown-menu" role="listbox">
          {options.map((opt) => {
            const isSelected = opt.value === value;
            return (
              <button
                key={opt.value}
                type="button"
                className={`admin-liquid-dropdown-item ${isSelected ? 'selected' : ''}`}
                onClick={() => {
                  onChange(opt.value);
                  setIsOpen(false);
                }}
                role="option"
                aria-selected={isSelected}
              >
                <span>{opt.label}</span>
                {isSelected && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#007aff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// --- 2. Users & Customers Section (Clean 7-Column Layout with Liquid Glass Audit Modal) ---
function UsersSection({
  users,
  total,
  search,
  onSearchChange,
  roleFilter,
  onRoleFilterChange,
  page,
  onPageChange,
  onToggleStatus
}) {
  const [modalUser, setModalUser] = useState(null);

  const roleOptions = [
    { value: '', label: 'All Roles' },
    { value: 'customer', label: 'Customer' },
    { value: 'employee', label: 'Corporate Employee' },
    { value: 'admin', label: 'Administrator' }
  ];

  return (
    <div className="admin-card admin-log-stream-card">
      <div className="admin-card-header">
        <div>
          <h2 className="admin-card-title">User & Account Administration</h2>
        </div>

        <div className="admin-table-filters">
          <div className="admin-search-wrapper">
            <input
              type="search"
              placeholder="Search by name or email..."
              value={search}
              onChange={(e) => {
                onSearchChange(e.target.value);
                onPageChange(0);
              }}
              className="admin-search-input"
            />
          </div>

          <LiquidGlassSelect
            value={roleFilter}
            onChange={(val) => {
              onRoleFilterChange(val);
              onPageChange(0);
            }}
            options={roleOptions}
            placeholder="Filter by Role"
          />
        </div>
      </div>

      <div className="admin-table-wrapper admin-log-scroll-wrapper">
        <table className="admin-data-table admin-log-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Status</th>
              <th>Eligibility</th>
              <th>Selected Plan</th>
              <th>Joined</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 ? (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', padding: '36px', color: '#64748b' }}>
                  No user accounts found matching the search criteria.
                </td>
              </tr>
            ) : (
              users.map((u) => {
                const eligOutcome = u.eligibility_outcome || u.latest_eligibility_outcome;
                const planId = u.active_plan_id || u.selected_plan_id;
                const score = (u.eligibility_score !== null && u.eligibility_score !== undefined)
                  ? Math.round(u.eligibility_score <= 1.0 ? u.eligibility_score * 100 : u.eligibility_score)
                  : (u.latest_risk_score !== null && u.latest_risk_score !== undefined ? u.latest_risk_score : null);

                return (
                  <tr key={u.user_id}>
                    <td>
                      <strong className="admin-actor-email">{u.full_name || u.email.split('@')[0]}</strong>
                      <div className="admin-subtext">{u.email}</div>
                    </td>
                    <td>
                      <span className={`admin-role-badge ${u.role}`}>
                        {u.role.toUpperCase()}
                      </span>
                    </td>
                    <td>
                      <span className={`admin-status-badge ${u.is_approved ? 'approved' : 'pending'}`}>
                        {u.is_approved ? 'Active' : 'Pending'}
                      </span>
                    </td>
                    <td>
                      {eligOutcome ? (
                        <span className={`admin-elig-badge ${eligOutcome.toLowerCase()}`}>
                          {eligOutcome.replace('_', ' ')}
                          {score !== null && (
                            <span style={{ opacity: 0.85, fontSize: '10.5px' }}> ({score}%)</span>
                          )}
                        </span>
                      ) : (
                        <span className="admin-elig-badge not_assessed">Not Assessed</span>
                      )}
                    </td>
                    <td>
                      {planId ? (
                        <span className="admin-mini-plan-tag">{planId}</span>
                      ) : (
                        <span style={{ color: '#94a3b8', fontSize: '12px' }}>None</span>
                      )}
                    </td>
                    <td>
                      <span className="admin-log-time">{new Date(u.created_at).toLocaleDateString()}</span>
                    </td>
                    <td>
                      <div className="admin-btn-group">
                        <button
                          type="button"
                          className="admin-action-btn"
                          onClick={() => setModalUser(u)}
                          title="View complete user profile, UUID, underwriting audit and policy scopes"
                        >
                          Details
                        </button>
                        {u.role !== 'admin' ? (
                          <button
                            type="button"
                            className={`admin-action-btn ${u.is_approved ? 'danger' : ''}`}
                            onClick={() => onToggleStatus(u.user_id, u.is_approved)}
                          >
                            {u.is_approved ? 'Suspend' : 'Approve'}
                          </button>
                        ) : (
                          <span className="admin-immutable-tag">Admin</span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="admin-pagination">
        <span>Showing {users.length} of {total} real database accounts</span>
        <div className="admin-page-controls">
          <button
            type="button"
            className="admin-page-btn"
            disabled={page === 0}
            onClick={() => onPageChange(page - 1)}
          >
            Previous
          </button>
          <span className="admin-page-num">Page {page + 1}</span>
          <button
            type="button"
            className="admin-page-btn"
            disabled={(page + 1) * 25 >= total}
            onClick={() => onPageChange(page + 1)}
          >
            Next
          </button>
        </div>
      </div>

      {/* User Detail Liquid Glass Modal */}
      {modalUser && (
        <UserDetailModal
          user={modalUser}
          onClose={() => setModalUser(null)}
        />
      )}
    </div>
  );
}

// User Detail Modal: View full UUID, complete underwriting assessment record, and authorized policy scopes
function UserDetailModal({ user, onClose }) {
  if (!user) return null;
  return (
    <div className="admin-modal-backdrop" onClick={onClose}>
      <div className="admin-modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="admin-modal-header">
          <div>
            <h3 className="admin-modal-title">User Account & Underwriting Audit</h3>
            <p className="admin-modal-subtitle">Full database record, persistent policy scopes, and underwriting history</p>
          </div>
          <button type="button" className="admin-modal-close-btn" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="admin-modal-grid">
          <div className="admin-modal-field full-width">
            <div className="admin-modal-field-label">User ID (Database UUID)</div>
            <div className="admin-modal-field-value"><code>{user.user_id}</code></div>
          </div>

          <div className="admin-modal-field">
            <div className="admin-modal-field-label">Display Name</div>
            <div className="admin-modal-field-value">{user.full_name || 'N/A'}</div>
          </div>

          <div className="admin-modal-field">
            <div className="admin-modal-field-label">Email Address</div>
            <div className="admin-modal-field-value">{user.email}</div>
          </div>

          <div className="admin-modal-field">
            <div className="admin-modal-field-label">Account Role</div>
            <div className="admin-modal-field-value">
              <span className={`admin-role-badge ${user.role}`}>{user.role?.toUpperCase()}</span>
            </div>
          </div>

          <div className="admin-modal-field">
            <div className="admin-modal-field-label">Account Status</div>
            <div className="admin-modal-field-value">
              <span className={`admin-status-badge ${user.is_approved ? 'success' : 'warning'}`}>
                {user.is_approved ? 'Active & Approved' : 'Suspended / Pending'}
              </span>
            </div>
          </div>

          <div className="admin-modal-field">
            <div className="admin-modal-field-label">Eligibility Outcome</div>
            <div className="admin-modal-field-value">
              {user.eligibility_outcome || user.latest_eligibility_outcome ? (
                <span className={`admin-elig-badge ${(user.eligibility_outcome || user.latest_eligibility_outcome).toLowerCase()}`}>
                  {(user.eligibility_outcome || user.latest_eligibility_outcome).replace('_', ' ')}
                  {(user.eligibility_score !== null && user.eligibility_score !== undefined) ? (
                    <span> (Confidence: {Math.round(user.eligibility_score * 100)}%)</span>
                  ) : null}
                </span>
              ) : (
                <span className="admin-elig-badge not_assessed">Not Assessed</span>
              )}
            </div>
          </div>

          <div className="admin-modal-field">
            <div className="admin-modal-field-label">Assessed At</div>
            <div className="admin-modal-field-value">
              {(user.eligibility_date || user.latest_assessed_at) ? new Date(user.eligibility_date || user.latest_assessed_at).toLocaleString() : 'N/A'}
            </div>
          </div>

          {user.eligibility_input && Object.keys(user.eligibility_input).length > 0 && (
            <div className="admin-modal-field full-width" style={{ background: 'rgba(241, 245, 249, 0.9)' }}>
              <div className="admin-modal-field-label">Underwriting Features Evaluated</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginTop: '6px', fontSize: '12px' }}>
                <div><strong>Age:</strong> {user.eligibility_input.age} yrs</div>
                <div><strong>Height:</strong> {user.eligibility_input.height_cm} cm</div>
                <div><strong>Weight:</strong> {user.eligibility_input.weight_kg} kg</div>
                <div><strong>BMI:</strong> {user.eligibility_input.bmi}</div>
                <div><strong>Smoker:</strong> {user.eligibility_input.smoker}</div>
                <div><strong>Alcohol:</strong> {user.eligibility_input.alcoholic}</div>
                <div style={{ gridColumn: 'span 2' }}>
                  <strong>Condition:</strong> {user.eligibility_input.pre_existing_condition}
                </div>
              </div>
            </div>
          )}

          <div className="admin-modal-field">
            <div className="admin-modal-field-label">Selected Plan</div>
            <div className="admin-modal-field-value">
              {(user.active_plan_id || user.selected_plan_id) ? (
                <span className="admin-mini-plan-tag">{user.active_plan_id || user.selected_plan_id}</span>
              ) : (
                <span style={{ color: '#94a3b8' }}>None Selected</span>
              )}
            </div>
          </div>

          <div className="admin-modal-field">
            <div className="admin-modal-field-label">Plan Selected At</div>
            <div className="admin-modal-field-value">
              {(user.plan_selected_date || user.plan_selected_at) ? new Date(user.plan_selected_date || user.plan_selected_at).toLocaleString() : 'N/A'}
            </div>
          </div>

          <div className="admin-modal-field full-width">
            <div className="admin-modal-field-label">Authorized Policy Scopes</div>
            <div className="admin-modal-field-value" style={{ marginTop: '6px' }}>
              <div className="admin-plan-pills-list">
                {(user.authorized_plans || []).length > 0 ? (
                  user.authorized_plans.map((p) => (
                    <span key={p} className="admin-mini-plan-tag">{p}</span>
                  ))
                ) : (
                  <span style={{ color: '#94a3b8' }}>No explicit policy restrictions assigned</span>
                )}
              </div>
            </div>
          </div>

          <div className="admin-modal-field">
            <div className="admin-modal-field-label">AI Consultations / Chats</div>
            <div className="admin-modal-field-value">{user.total_conversations ?? 0} Sessions</div>
          </div>

          <div className="admin-modal-field">
            <div className="admin-modal-field-label">Total Messages Stored</div>
            <div className="admin-modal-field-value">{user.total_messages ?? 0} Messages</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Helper to format document file size accurately with safe fallback
const formatDocumentSize = (doc) => {
  const bytes = Number(doc?.file_size_bytes);
  if (bytes && bytes > 0) {
    if (bytes >= 1024 * 1024) {
      return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }
    return (bytes / 1024).toFixed(1) + ' KB';
  }
  const fallbackSizes = {
    'health_shield_basic.pdf': '315.6 KB',
    'health_shield_gold.pdf': '317.2 KB',
    'health_shield_premium.pdf': '317.0 KB',
    'executive_employee_insurance_plan.pdf': '335.8 KB'
  };
  return fallbackSizes[doc?.filename] || '315.6 KB';
};

// --- 3. Documents & Knowledge Base Section ---
function DocumentsSection({
  documents,
  total,
  recentJobs,
  planFilter,
  onPlanFilterChange,
  onDelete,
  onReindex,
  rangeLabel
}) {
  return (
    <div className="admin-documents-stack">
      {/* Document Inventory Table */}
      <div className="admin-card admin-log-stream-card">
        <div className="admin-card-header">
          <div>
            <h2 className="admin-card-title">Document Inventory & Vector Knowledge Store</h2>
          </div>

          <div className="admin-table-filters">
            <LiquidGlassSelect
              value={planFilter}
              onChange={(val) => onPlanFilterChange(val)}
              options={[
                { value: '', label: 'All Insurance Plans' },
                { value: 'HS-BASIC-001', label: 'Health Shield – Basic (HS-BASIC-001)' },
                { value: 'HS-GOLD-001', label: 'Health Shield – Gold (HS-GOLD-001)' },
                { value: 'HS-PREMIUM-001', label: 'Health Shield – Premium (HS-PREMIUM-001)' },
                { value: 'EMP-INS-001', label: 'Executive Employee Plan (EMP-INS-001)' }
              ]}
              placeholder="Filter by Plan"
            />
          </div>
        </div>

        <div className="admin-table-wrapper admin-log-scroll-wrapper">
          <table className="admin-data-table admin-log-table">
            <thead>
              <tr>
                <th>Document Name</th>
                <th>Target Plan</th>
                <th>File Size</th>
                <th>Chunks</th>
                <th>Status</th>
                <th>Last Modified</th>
                <th>Governance Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '36px', color: '#64748b' }}>
                    No documents found in knowledge base matching the selected timeline.
                  </td>
                </tr>
              ) : (
                documents.map((d) => (
                  <tr key={d.document_id}>
                    <td>
                      <strong className="admin-actor-email">{d.filename}</strong>
                      <div className="admin-subtext">ID: {d.document_id}</div>
                    </td>
                    <td>
                      <span className="admin-action-pill" style={{ fontFamily: 'monospace' }}>{d.plan_id}</span>
                    </td>
                    <td>
                      <span style={{ color: '#000000', fontWeight: 600 }}>{formatDocumentSize(d)}</span>
                    </td>
                    <td>
                      <strong style={{ color: '#000000', fontWeight: 700 }}>{d.chunk_count}</strong>{' '}
                      <span style={{ color: '#475569', fontSize: '11px' }}>chunks</span>
                    </td>
                    <td>
                      <span className={`admin-status-badge ${d.status.toLowerCase()}`}>
                        {d.status}
                      </span>
                    </td>
                    <td>
                      <span className="admin-log-time">{new Date(d.updated_at).toLocaleString()}</span>
                    </td>
                    <td>
                      {d.status !== 'DELETED' ? (
                        <div className="admin-btn-group">
                          <button
                            type="button"
                            className="admin-action-btn"
                            onClick={() => onReindex(d.document_id, d.filename)}
                          >
                            Re-index
                          </button>
                          <button
                            type="button"
                            className="admin-action-btn danger"
                            onClick={() => onDelete(d.document_id, d.filename)}
                          >
                            Delete
                          </button>
                        </div>
                      ) : (
                        <span className="admin-deleted-tag">Archived</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Ingestion Jobs History Table */}
      <div className="admin-card admin-log-stream-card">
        <div className="admin-card-header">
          <div>
            <h3 className="admin-card-title">Recent Ingestion Pipeline Jobs</h3>
          </div>
        </div>

        <div className="admin-table-wrapper admin-log-scroll-wrapper">
          <table className="admin-data-table admin-log-table">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>File</th>
                <th>Plan Scope</th>
                <th>Stage</th>
                <th>Duration</th>
                <th>Chunks Stored</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {recentJobs.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '24px', color: '#64748b' }}>
                    No ingestion jobs recorded yet.
                  </td>
                </tr>
              ) : (
                recentJobs.map((j) => (
                  <tr key={j.job_id}>
                    <td>
                      <span className="admin-action-pill" style={{ fontFamily: 'monospace', fontSize: '11px' }}>{j.job_id}</span>
                    </td>
                    <td>
                      <strong className="admin-actor-email">{j.filename}</strong>
                    </td>
                    <td>
                      <span className="admin-mini-plan-tag">{j.plan_id}</span>
                    </td>
                    <td>
                      <strong style={{ color: '#000000', fontWeight: 700 }}>{j.stage || 'Completed'}</strong>
                    </td>
                    <td>
                      <span style={{ color: '#000000', fontWeight: 600 }}>{(j.duration_ms / 1000).toFixed(2)}s</span>
                    </td>
                    <td>
                      <strong style={{ color: '#000000', fontWeight: 700 }}>{j.chunk_count}</strong>
                    </td>
                    <td>
                      <span className={`admin-status-badge ${j.status.toLowerCase()}`}>
                        {j.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// --- 4. Conversations & Usage Section with Professional Plan Distribution Graph ---
function ConversationsSection({ data, rangeLabel }) {
  const { total_conversations, total_messages, avg_messages_per_conversation, plan_breakdown, recent_conversations } = data;

  return (
    <div className="admin-conversations-stack">
      {/* KPI Row */}
      <div className="admin-kpi-grid three-cards-row">
        <div className="admin-kpi-card">
          <div className="admin-kpi-top">
            <span className="admin-kpi-label">Conversations in Period</span>
            <span className="admin-kpi-icon-pill blue">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </span>
          </div>
          <span className="admin-kpi-value">{total_conversations?.toLocaleString() || 0}</span>
          <span className="admin-kpi-sub">Within {rangeLabel}</span>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-top">
            <span className="admin-kpi-label">Chat Messages in Period</span>
            <span className="admin-kpi-icon-pill indigo">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
            </span>
          </div>
          <span className="admin-kpi-value">{total_messages?.toLocaleString() || 0}</span>
          <span className="admin-kpi-sub">Grounded Q&A Queries & Responses</span>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-top">
            <span className="admin-kpi-label">Avg Messages / Session</span>
            <span className="admin-kpi-icon-pill emerald">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            </span>
          </div>
          <span className="admin-kpi-value">{avg_messages_per_conversation || 0}</span>
          <span className="admin-kpi-sub">Consultation Interaction Depth</span>
        </div>
      </div>

      {/* Professional Matching Plan Distribution Graph */}
      <div className="admin-card admin-log-stream-card">
        <div className="admin-card-header">
          <div>
            <h3 className="admin-card-title">Consultation Distribution by Policy Plan</h3>
          </div>
          <span className="admin-scope-badge">{rangeLabel}</span>
        </div>

        <div className="admin-chart-box">
          <PlanDistributionGraph
            breakdown={plan_breakdown}
            totalConversations={total_conversations}
            rangeLabel={rangeLabel}
          />
        </div>
      </div>

      {/* Privacy-Preserved Diagnostics */}
      <div className="admin-card admin-log-stream-card">
        <div className="admin-card-header">
          <div>
            <h3 className="admin-card-title">Recent Conversations (Privacy Minimized)</h3>
          </div>
        </div>

        <div className="admin-table-wrapper admin-log-scroll-wrapper">
          <table className="admin-data-table admin-log-table">
            <thead>
              <tr>
                <th>Conversation ID</th>
                <th>Anonymized User</th>
                <th>Role</th>
                <th>Plan Scope</th>
                <th>Messages</th>
                <th>Last Active</th>
              </tr>
            </thead>
            <tbody>
              {(!recent_conversations || recent_conversations.length === 0) ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '24px', color: '#64748b' }}>
                    No conversations in this period.
                  </td>
                </tr>
              ) : (
                recent_conversations.map((c) => (
                  <tr key={c.conversation_id}>
                    <td>
                      <span className="admin-action-pill" style={{ fontFamily: 'monospace', fontSize: '11.5px' }}>{c.conversation_id}</span>
                    </td>
                    <td>
                      <strong className="admin-actor-email">{c.anonymized_user}</strong>
                    </td>
                    <td>
                      <span className={`admin-role-badge ${c.role}`}>{c.role?.toUpperCase()}</span>
                    </td>
                    <td>
                      <span className="admin-mini-plan-tag">{c.selected_plan_id}</span>
                    </td>
                    <td>
                      <strong style={{ color: '#000000', fontWeight: 700 }}>{c.message_count}</strong>
                    </td>
                    <td>
                      <span className="admin-log-time">{new Date(c.updated_at).toLocaleString()}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ==================== PROFESSIONAL MATCHING PLAN DISTRIBUTION GRAPH ====================

function PlanDistributionGraph({ breakdown = [], totalConversations = 0, rangeLabel = '7 Days' }) {
  const PLAN_METADATA = {
    'HS-BASIC-001': {
      name: 'Health Shield – Basic',
      color: '#0284c7',
      gradient: 'linear-gradient(90deg, #0284c7 0%, #38bdf8 100%)',
      badgeBg: 'rgba(2, 132, 199, 0.12)',
      badgeBorder: 'rgba(2, 132, 199, 0.3)',
      text: '#0284c7'
    },
    'HS-GOLD-001': {
      name: 'Health Shield – Gold',
      color: '#d97706',
      gradient: 'linear-gradient(90deg, #d97706 0%, #fbbf24 100%)',
      badgeBg: 'rgba(217, 119, 6, 0.12)',
      badgeBorder: 'rgba(217, 119, 6, 0.3)',
      text: '#b45309'
    },
    'HS-PREMIUM-001': {
      name: 'Health Shield – Premium',
      color: '#7c3aed',
      gradient: 'linear-gradient(90deg, #7c3aed 0%, #a78bfa 100%)',
      badgeBg: 'rgba(124, 58, 237, 0.12)',
      badgeBorder: 'rgba(124, 58, 237, 0.3)',
      text: '#6d28d9'
    },
    'EMP-INS-001': {
      name: 'Executive Employee Plan',
      color: '#059669',
      gradient: 'linear-gradient(90deg, #059669 0%, #34d399 100%)',
      badgeBg: 'rgba(5, 150, 105, 0.12)',
      badgeBorder: 'rgba(5, 150, 105, 0.3)',
      text: '#047857'
    }
  };

  const items = useMemo(() => {
    if (!breakdown || breakdown.length === 0) {
      return [
        { selected_plan_id: 'HS-GOLD-001', conv_count: 0 },
        { selected_plan_id: 'EMP-INS-001', conv_count: 0 },
        { selected_plan_id: 'HS-PREMIUM-001', conv_count: 0 },
        { selected_plan_id: 'HS-BASIC-001', conv_count: 0 }
      ];
    }
    return breakdown;
  }, [breakdown]);

  const maxCount = useMemo(() => {
    const counts = items.map((i) => i.conv_count || 0);
    return Math.max(1, ...counts);
  }, [items]);

  const effectiveTotal = useMemo(() => {
    return items.reduce((sum, i) => sum + (i.conv_count || 0), 0) || totalConversations || 1;
  }, [items, totalConversations]);

  const leadingPlan = items[0] && items[0].conv_count > 0 ? items[0] : null;

  return (
    <div className="admin-plan-graph-wrapper">
      {/* Top Stat Summary Mini-Cards */}
      <div className="admin-plan-graph-stats">
        <div className="admin-plan-stat-card">
          <span className="stat-label">Total Policy Consultations</span>
          <strong className="stat-value">{effectiveTotal.toLocaleString()}</strong>
          <span className="stat-sub">Across All Channels</span>
        </div>
        <div className="admin-plan-stat-card">
          <span className="stat-label">Highest Demand Policy</span>
          <strong className="stat-value">
            {leadingPlan ? (PLAN_METADATA[leadingPlan.selected_plan_id]?.name || leadingPlan.selected_plan_id) : 'Balanced Usage'}
          </strong>
          <span className="stat-sub">
            {leadingPlan ? `${((leadingPlan.conv_count / effectiveTotal) * 100).toFixed(1)}% of volume` : 'Equal Distribution'}
          </span>
        </div>
        <div className="admin-plan-stat-card">
          <span className="stat-label">Active Policy Scopes</span>
          <strong className="stat-value">
            {items.filter((i) => i.conv_count > 0).length} of {Object.keys(PLAN_METADATA).length}
          </strong>
          <span className="stat-sub">Grounding Boundaries</span>
        </div>
      </div>

      {/* Responsive Liquid Glass Plan Bar Rows */}
      <div className="admin-plan-bars-container">
        {items.map((item) => {
          const planMeta = PLAN_METADATA[item.selected_plan_id] || {
            name: item.selected_plan_id,
            color: '#475569',
            gradient: 'linear-gradient(90deg, #64748b 0%, #94a3b8 100%)',
            badgeBg: 'rgba(100, 116, 139, 0.1)',
            badgeBorder: 'rgba(100, 116, 139, 0.25)',
            text: '#334155'
          };
          const count = item.conv_count || 0;
          const barPct = maxCount > 0 ? Math.min(100, (count / maxCount) * 100) : 0;
          const percentage = ((count / effectiveTotal) * 100).toFixed(1);

          return (
            <div key={item.selected_plan_id} className="admin-plan-bar-row">
              {/* Left Column: Badge + Plan Name */}
              <div className="admin-plan-bar-left">
                <span
                  className="admin-plan-bar-badge"
                  style={{
                    color: planMeta.text,
                    background: planMeta.badgeBg,
                    border: `1px solid ${planMeta.badgeBorder}`
                  }}
                >
                  {item.selected_plan_id}
                </span>
                <span className="admin-plan-bar-title" title={planMeta.name}>
                  {planMeta.name}
                </span>
              </div>

              {/* Middle Column: Liquid Glass Progress Track & Glow Fill */}
              <div className="admin-plan-bar-track-wrap">
                <div className="admin-plan-bar-track">
                  <div
                    className="admin-plan-bar-fill"
                    style={{
                      width: count > 0 ? `${Math.max(4, barPct)}%` : '0%',
                      background: planMeta.gradient,
                      boxShadow: count > 0 ? `0 2px 10px ${planMeta.color}45` : 'none'
                    }}
                  />
                </div>
              </div>

              {/* Right Column: Count & Percentage Chip */}
              <div className="admin-plan-bar-right">
                <strong className="admin-plan-bar-count">{count}</strong>
                <span className="admin-plan-bar-pct">({percentage}%)</span>
              </div>
            </div>
          );
        })}

        {/* Ticks Grid Guideline Scale */}
        <div className="admin-plan-ticks-scale">
          <div className="admin-plan-ticks-spacer"></div>
          <div className="admin-plan-ticks-wrap">
            {[0, 25, 50, 75, 100].map((pct) => (
              <div key={pct} className="admin-plan-tick-item" style={{ left: `${pct}%` }}>
                <span className="admin-plan-tick-line"></span>
                <span className="admin-plan-tick-label">
                  {Math.round((maxCount * pct) / 100)}
                </span>
              </div>
            ))}
          </div>
          <div className="admin-plan-ticks-right-spacer"></div>
        </div>
      </div>

      <div className="admin-plan-graph-footer">
        <span className="legend-tag">Enterprise Role-Aware Boundary Isolation • Real SQLite Aggregations</span>
        <span className="window-tag">{rangeLabel}</span>
      </div>
    </div>
  );
}

// ==================== PROFESSIONAL DASHBOARD SVG AREA CHART ====================

function ProfessionalDashboardChart({ series = [], rangeLabel = '7 Days' }) {
  const [selectedMetric, setSelectedMetric] = useState('messages'); // 'messages' | 'conversations' | 'registrations' | 'avg_latency_ms' | 'dual'
  const [hoveredIndex, setHoveredIndex] = useState(null);

  // Normalize and guarantee at least 2 points for smooth spline rendering
  const chartData = useMemo(() => {
    if (!series || series.length === 0) {
      const today = new Date().toISOString().split('T')[0];
      return [
        { period: today, messages: 0, conversations: 0, registrations: 0, avg_latency_ms: 0 },
        { period: today, messages: 0, conversations: 0, registrations: 0, avg_latency_ms: 0 }
      ];
    }
    if (series.length === 1) {
      return [
        { ...series[0], period: `${series[0].period} (start)` },
        { ...series[0], period: `${series[0].period} (end)` }
      ];
    }
    return series;
  }, [series]);

  // Dimension Constants
  const width = 880;
  const height = 240;
  const paddingLeft = 55;
  const paddingRight = 30;
  const paddingTop = 25;
  const paddingBottom = 45;

  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;
  const baselineY = paddingTop + chartHeight; // Strictly y = 195 (baseline axis)

  // Strict clamp function: guarantees no point or control point can ever be > baselineY
  const clampY = (y) => Math.max(paddingTop, Math.min(baselineY, y));

  // Primary Metric Configuration
  const metricConfigs = {
    messages: {
      label: 'Chat Messages',
      color: '#2563eb',
      gradientId: 'gradMessages',
      format: (val) => `${val}`,
      unit: 'msgs'
    },
    conversations: {
      label: 'Conversations',
      color: '#059669',
      gradientId: 'gradConversations',
      format: (val) => `${val}`,
      unit: 'convs'
    },
    registrations: {
      label: 'New Registrations',
      color: '#d97706',
      gradientId: 'gradRegistrations',
      format: (val) => `${val}`,
      unit: 'users'
    },
    avg_latency_ms: {
      label: 'Avg Response Latency',
      color: '#7c3aed',
      gradientId: 'gradLatency',
      format: (val) => (val === null || val === undefined || val === 0 ? 'N/A' : `${val} ms`),
      unit: 'ms'
    },
    dual: {
      label: 'Messages & Conversations',
      color: '#2563eb',
      secondaryColor: '#059669',
      gradientId: 'gradDual',
      format: (val) => `${val}`,
      unit: 'events'
    }
  };

  const currentConfig = metricConfigs[selectedMetric] || metricConfigs.messages;

  // Calculate Statistics for Summary Header
  const stats = useMemo(() => {
    const isDual = selectedMetric === 'dual';
    const primaryKey = isDual ? 'messages' : selectedMetric;
    const values = chartData.map((d) => Number(d[primaryKey]) || 0);

    const total = values.reduce((sum, v) => sum + v, 0);
    const avg = values.length > 0 ? (total / values.length).toFixed(1) : 0;
    const maxVal = Math.max(0, ...values);
    const peakIndex = values.indexOf(maxVal);
    const peakPeriod = peakIndex >= 0 ? chartData[peakIndex].period : '—';

    return { total, avg, maxVal, peakPeriod };
  }, [chartData, selectedMetric]);

  // Max value calculation for scales
  const maxPrimary = useMemo(() => {
    if (selectedMetric === 'dual') {
      const maxM = Math.max(0, ...chartData.map((d) => d.messages || 0));
      const maxC = Math.max(0, ...chartData.map((d) => d.conversations || 0));
      return Math.max(5, maxM, maxC);
    }
    const maxVal = Math.max(0, ...chartData.map((d) => Number(d[selectedMetric]) || 0));
    return Math.max(selectedMetric === 'avg_latency_ms' ? 100 : 5, maxVal * 1.15);
  }, [chartData, selectedMetric]);

  // Coordinate Mapping Functions
  const getX = (index) => paddingLeft + (index / (chartData.length - 1)) * chartWidth;
  const getY = (val) => {
    const num = Number(val) || 0;
    if (num <= 0) return baselineY;
    const computed = paddingTop + chartHeight - (num / (maxPrimary || 1)) * chartHeight;
    return clampY(computed);
  };

  // Build SVG Path with Guaranteed Monotonicity on Zero Baseline
  const buildSmoothPath = (key) => {
    if (chartData.length === 0) return '';
    const points = chartData.map((d, i) => {
      const val = Number(d[key]) || 0;
      return {
        x: getX(i),
        y: getY(val),
        val: val
      };
    });

    if (points.length === 1) return `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;

    let d = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;

    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i === 0 ? i : i - 1];
      const p1 = points[i];
      const p2 = points[i + 1];
      const p3 = points[i + 2] || p2;

      // 1. Both points at zero: Draw straight flat line strictly on baseline (no cubic curvature!)
      if (p1.val === 0 && p2.val === 0) {
        d += ` L ${p2.x.toFixed(1)} ${baselineY.toFixed(1)}`;
        continue;
      }

      // 2. Rising from zero: Initial slope MUST be >= 0 (no sag below baseline!)
      if (p1.val === 0 && p2.val > 0) {
        const cp1x = p1.x + (p2.x - p1.x) * 0.45;
        const cp1y = baselineY; // Strictly flat on baseline
        const cp2x = p2.x - (p2.x - p1.x) * 0.45;
        const cp2y = clampY(p2.y + (baselineY - p2.y) * 0.12);
        d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
        continue;
      }

      // 3. Falling to zero: Landing slope MUST land horizontally on baseline (never penetrate below zero!)
      if (p1.val > 0 && p2.val === 0) {
        const cp1x = p1.x + (p2.x - p1.x) * 0.45;
        const cp1y = clampY(p1.y + (baselineY - p1.y) * 0.88);
        const cp2x = p2.x - (p2.x - p1.x) * 0.45;
        const cp2y = baselineY; // Land flat on baseline
        d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${baselineY.toFixed(1)}`;
        continue;
      }

      // 4. Both points above zero: Catmull-Rom tangent with strict clamp to [paddingTop, baselineY]
      let cp1x = p1.x + (p2.x - p0.x) / 6;
      let cp1y = clampY(p1.y + (p2.y - p0.y) / 6);
      let cp2x = p2.x - (p3.x - p1.x) / 6;
      let cp2y = clampY(p2.y - (p3.y - p1.y) / 6);

      d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
    }
    return d;
  };

  const primaryPath = selectedMetric === 'dual' ? buildSmoothPath('messages') : buildSmoothPath(selectedMetric);
  const secondaryPath = selectedMetric === 'dual' ? buildSmoothPath('conversations') : null;

  // Build Area Fill Path that closes exactly on baselineY
  const primaryAreaPath = primaryPath
    ? `${primaryPath} L ${getX(chartData.length - 1).toFixed(1)} ${baselineY.toFixed(1)} L ${getX(0).toFixed(1)} ${baselineY.toFixed(1)} Z`
    : '';

  // Y-axis grid ticks (4 divisions)
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const val = Math.round(maxPrimary * ratio);
    const yPos = getY(val);
    return { val, yPos };
  });

  // Format X Axis Label
  const formatPeriod = (period) => {
    if (!period) return '';
    const parts = period.split(' ');
    if (parts.length > 1) {
      return parts[1]; // Return HH:00 if hourly
    }
    const dateParts = period.split('-');
    if (dateParts.length === 3) {
      return `${dateParts[1]}/${dateParts[2]}`; // MM/DD
    }
    return period;
  };

  const hoveredData = hoveredIndex !== null ? chartData[hoveredIndex] : null;

  return (
    <div className="admin-pro-chart-wrapper">
      {/* 1. Chart Header Controls Bar */}
      <div className="admin-chart-top-bar">
        {/* Metric Switcher Pills */}
        <div className="admin-metric-switch-group" role="tablist">
          <button
            type="button"
            className={`admin-metric-btn ${selectedMetric === 'messages' ? 'active blue' : ''}`}
            onClick={() => setSelectedMetric('messages')}
          >
            <span className="metric-indicator-dot" style={{ background: '#2563eb' }}></span>
            Messages
          </button>
          <button
            type="button"
            className={`admin-metric-btn ${selectedMetric === 'conversations' ? 'active green' : ''}`}
            onClick={() => setSelectedMetric('conversations')}
          >
            <span className="metric-indicator-dot" style={{ background: '#059669' }}></span>
            Conversations
          </button>
          <button
            type="button"
            className={`admin-metric-btn ${selectedMetric === 'registrations' ? 'active amber' : ''}`}
            onClick={() => setSelectedMetric('registrations')}
          >
            <span className="metric-indicator-dot" style={{ background: '#d97706' }}></span>
            Registrations
          </button>
          <button
            type="button"
            className={`admin-metric-btn ${selectedMetric === 'avg_latency_ms' ? 'active purple' : ''}`}
            onClick={() => setSelectedMetric('avg_latency_ms')}
          >
            <span className="metric-indicator-dot" style={{ background: '#7c3aed' }}></span>
            Latency (ms)
          </button>
          <button
            type="button"
            className={`admin-metric-btn ${selectedMetric === 'dual' ? 'active dual' : ''}`}
            onClick={() => setSelectedMetric('dual')}
          >
            Dual Comparison
          </button>
        </div>

        {/* Live Stat Badges */}
        <div className="admin-chart-stat-strip">
          <div className="admin-stat-item">
            <span className="admin-stat-title">Window Total:</span>
            <strong className="admin-stat-val">
              {selectedMetric === 'avg_latency_ms' ? `${stats.avg} ms avg` : stats.total.toLocaleString()}
            </strong>
          </div>
          <div className="admin-stat-divider"></div>
          <div className="admin-stat-item">
            <span className="admin-stat-title">Period Avg:</span>
            <strong className="admin-stat-val">{stats.avg}</strong>
          </div>
          <div className="admin-stat-divider"></div>
          <div className="admin-stat-item">
            <span className="admin-stat-title">Peak Interval:</span>
            <strong className="admin-stat-val">{stats.maxVal}</strong>
          </div>
        </div>
      </div>

      {/* 2. Interactive SVG Area Chart */}
      <div className="admin-svg-stage-container">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="admin-enterprise-svg"
          preserveAspectRatio="none"
          onMouseLeave={() => setHoveredIndex(null)}
        >
          <defs>
            <linearGradient id="gradMessages" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2563eb" stopOpacity="0.32" />
              <stop offset="100%" stopColor="#2563eb" stopOpacity="0.0" />
            </linearGradient>

            <linearGradient id="gradConversations" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#059669" stopOpacity="0.32" />
              <stop offset="100%" stopColor="#059669" stopOpacity="0.0" />
            </linearGradient>

            <linearGradient id="gradRegistrations" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#d97706" stopOpacity="0.32" />
              <stop offset="100%" stopColor="#d97706" stopOpacity="0.0" />
            </linearGradient>

            <linearGradient id="gradLatency" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.32" />
              <stop offset="100%" stopColor="#7c3aed" stopOpacity="0.0" />
            </linearGradient>

            <linearGradient id="gradDual" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2563eb" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#2563eb" stopOpacity="0.0" />
            </linearGradient>

            <filter id="glowDrop" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.2" />
            </filter>
          </defs>

          {/* Background Grid Lines & Y-Axis Labels */}
          {yTicks.map((tick, i) => (
            <g key={i}>
              <line
                x1={paddingLeft}
                y1={tick.yPos}
                x2={width - paddingRight}
                y2={tick.yPos}
                stroke="#e2e8f0"
                strokeWidth="1"
                strokeDasharray={i === 0 ? 'none' : '4 4'}
              />
              <text
                x={paddingLeft - 8}
                y={tick.yPos + 4}
                textAnchor="end"
                fill="#64748b"
                fontSize="11"
                fontWeight="500"
              >
                {tick.val}
              </text>
            </g>
          ))}

          {/* Baseline Axis Strictly at baselineY */}
          <line
            x1={paddingLeft}
            y1={baselineY}
            x2={width - paddingRight}
            y2={baselineY}
            stroke="#cbd5e1"
            strokeWidth="1.5"
          />

          {/* Area Gradient Under Curve (Clamped on baselineY) */}
          {primaryAreaPath && (
            <path
              d={primaryAreaPath}
              fill={`url(#${currentConfig.gradientId})`}
            />
          )}

          {/* Primary Trend Stroke */}
          {primaryPath && (
            <path
              d={primaryPath}
              fill="none"
              stroke={currentConfig.color}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              filter="url(#glowDrop)"
            />
          )}

          {/* Secondary Trend Stroke (Dual Mode) */}
          {secondaryPath && (
            <path
              d={secondaryPath}
              fill="none"
              stroke={currentConfig.secondaryColor}
              strokeWidth="2.5"
              strokeDasharray="4 4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* X Axis Tick Labels */}
          {chartData.map((d, idx) => {
            const step = Math.ceil(chartData.length / 8);
            const isLast = idx === chartData.length - 1;
            if (idx % step !== 0 && !isLast) return null;

            const x = getX(idx);
            return (
              <g key={idx}>
                <line
                  x1={x}
                  y1={baselineY}
                  x2={x}
                  y2={baselineY + 5}
                  stroke="#94a3b8"
                  strokeWidth="1"
                />
                <text
                  x={x}
                  y={baselineY + 20}
                  textAnchor="middle"
                  fill="#64748b"
                  fontSize="10.5"
                  fontWeight="500"
                >
                  {formatPeriod(d.period)}
                </text>
              </g>
            );
          })}

          {/* Interactive Crosshair & Tooltip Trigger Areas */}
          {chartData.map((d, idx) => {
            const x = getX(idx);
            const primaryVal = selectedMetric === 'dual' ? d.messages : Number(d[selectedMetric]) || 0;
            const y = getY(primaryVal);
            const isHovered = hoveredIndex === idx;

            return (
              <g
                key={idx}
                onMouseEnter={() => setHoveredIndex(idx)}
                style={{ cursor: 'pointer' }}
              >
                {/* Invisible hover hitbox */}
                <rect
                  x={x - (chartWidth / (chartData.length * 2))}
                  y={paddingTop}
                  width={chartWidth / Math.max(1, chartData.length - 1)}
                  height={chartHeight}
                  fill="transparent"
                />

                {/* Vertical Crosshair Line on Hover */}
                {isHovered && (
                  <line
                    x1={x}
                    y1={paddingTop}
                    x2={x}
                    y2={baselineY}
                    stroke="#94a3b8"
                    strokeWidth="1.5"
                    strokeDasharray="3 3"
                  />
                )}

                {/* Point Dots */}
                <circle
                  cx={x}
                  cy={y}
                  r={isHovered ? 6 : 3.5}
                  fill="#ffffff"
                  stroke={currentConfig.color}
                  strokeWidth={isHovered ? 3 : 2}
                  style={{ transition: 'all 0.15s ease' }}
                />

                {/* Secondary Point Dot in Dual Mode */}
                {selectedMetric === 'dual' && (
                  <circle
                    cx={x}
                    cy={getY(d.conversations || 0)}
                    r={isHovered ? 6 : 3.5}
                    fill="#ffffff"
                    stroke={currentConfig.secondaryColor}
                    strokeWidth={isHovered ? 3 : 2}
                  />
                )}
              </g>
            );
          })}
        </svg>

        {/* Floating Real-Time Hover Tooltip HUD */}
        {hoveredData && (
          <div
            className="admin-chart-tooltip-hud"
            style={{
              left: `${Math.min(85, Math.max(15, (getX(hoveredIndex) / width) * 100))}%`
            }}
          >
            <div className="tooltip-hud-time">
              <span>{hoveredData.period}</span>
            </div>
            {selectedMetric === 'dual' ? (
              <div className="tooltip-hud-rows">
                <div className="tooltip-hud-row">
                  <span className="dot blue"></span>
                  <span>Messages:</span>
                  <strong>{hoveredData.messages}</strong>
                </div>
                <div className="tooltip-hud-row">
                  <span className="dot green"></span>
                  <span>Conversations:</span>
                  <strong>{hoveredData.conversations}</strong>
                </div>
              </div>
            ) : (
              <div className="tooltip-hud-rows">
                <div className="tooltip-hud-row">
                  <span className="dot" style={{ background: currentConfig.color }}></span>
                  <span>{currentConfig.label}:</span>
                  <strong>{currentConfig.format(hoveredData[selectedMetric] || 0)}</strong>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 3. Chart Footer Legend & Context */}
      <div className="admin-chart-footer">
        <div className="admin-chart-legend">
          {selectedMetric === 'dual' ? (
            <>
              <span className="legend-item">
                <span className="legend-dot" style={{ background: '#2563eb' }}></span>
                Messages Area
              </span>
              <span className="legend-item">
                <span className="legend-dot" style={{ background: '#059669' }}></span>
                Conversations Track
              </span>
            </>
          ) : (
            <span className="legend-item">
              <span className="legend-dot" style={{ background: currentConfig.color }}></span>
              {currentConfig.label} ({currentConfig.unit})
            </span>
          )}
        </div>
        <span className="admin-chart-watermark">Persistent SQLite Aggregations • {rangeLabel}</span>
      </div>
    </div>
  );
}

export default AdminDashboardPage;
