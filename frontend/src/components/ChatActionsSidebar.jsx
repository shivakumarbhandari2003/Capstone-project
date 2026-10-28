import React, { useState, useEffect, useMemo } from 'react';

function formatHistoryTime(isoString) {
  if (!isoString) return 'Just now';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (isToday) {
      return `Today, ${timeStr}`;
    }
    const month = d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    return `${month}, ${timeStr}`;
  } catch {
    return isoString;
  }
}

function getPlanBadgeClass(planId = '') {
  const p = planId.toLowerCase();
  if (p.includes('gold')) return 'gold';
  if (p.includes('basic')) return 'basic';
  if (p.includes('prem')) return 'premium';
  if (p.includes('emp')) return 'employee';
  return 'default';
}

function formatPlanLabel(planId = '') {
  const p = planId.toUpperCase();
  if (p.includes('BASIC')) return 'Basic';
  if (p.includes('GOLD')) return 'Gold';
  if (p.includes('PREMIUM')) return 'Premium';
  if (p.includes('EMP')) return 'Staff';
  return planId;
}

/**
 * ChatActionsSidebar — Right Sidebar dedicated to Quick Actions and ChatGPT-style Conversation History.
 * Saves and lists user conversations with a structured history table, filterable by plan and search query.
 */
export function ChatActionsSidebar({
  isOpen,
  activeTab = 'history', // 'quick_actions' | 'history'
  onSelectTab,
  onClose,
  messages = [],
  quickActions = [],
  currentConversationId = null,
  selectedPlan = null,
  authToken = null,
  userRole = 'customer',
  historyRefreshTrigger = 0,
  onTriggerAction,
  onLoadConversation,
  onStartNewChat,
  onSelectHistory
}) {
  const [conversations, setConversations] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch saved conversations from backend whenever panel opens or refresh is triggered
  useEffect(() => {
    if (!isOpen || activeTab !== 'history') return;

    let isMounted = true;
    const fetchHistory = async () => {
      setLoadingHistory(true);
      setHistoryError(null);
      try {
        const headers = {
          'Content-Type': 'application/json',
          'X-User-Role': userRole
        };
        if (authToken) {
          headers['Authorization'] = `Bearer ${authToken}`;
        }

        let res;
        try {
          res = await fetch('/api/conversations', { headers });
        } catch {
          res = await fetch('http://127.0.0.1:8000/api/conversations', { headers });
        }

        if (!res.ok) {
          throw new Error(`Failed to load history (${res.status})`);
        }

        const data = await res.json();
        if (isMounted) {
          setConversations(Array.isArray(data) ? data : []);
        }
      } catch (err) {
        if (isMounted) {
          setHistoryError(err.message);
        }
      } finally {
        if (isMounted) {
          setLoadingHistory(false);
        }
      }
    };

    fetchHistory();

    return () => {
      isMounted = false;
    };
  }, [isOpen, activeTab, historyRefreshTrigger, authToken, userRole]);

  // Filter conversations based on search query
  const filteredConversations = useMemo(() => {
    let list = conversations;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter((c) =>
        (c.preview_title && c.preview_title.toLowerCase().includes(q)) ||
        (c.selected_plan_id && c.selected_plan_id.toLowerCase().includes(q))
      );
    }
    return list;
  }, [conversations, searchQuery]);

  if (!isOpen) return null;

  const currentPlanId = selectedPlan?.plan_id || '';
  const currentPlanCount = conversations.filter((c) => c.selected_plan_id === currentPlanId).length;

  return (
    <aside className="chat-actions-sidebar" aria-label="Quick Actions and History">
      {/* Top Header with Tab Switcher & Close Button */}
      <div className="actions-sidebar-header">
        <div className="actions-tab-switcher">
          <button
            type="button"
            className={`actions-tab-btn ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => onSelectTab('history')}
            title="View saved conversation history table"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            <span>History</span>
            {conversations.length > 0 && (
              <span className="actions-count-pill">{conversations.length}</span>
            )}
          </button>

          <button
            type="button"
            className={`actions-tab-btn ${activeTab === 'quick_actions' ? 'active' : ''}`}
            onClick={() => onSelectTab('quick_actions')}
            title="View suggested policy quick actions"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
            </svg>
            <span>Quick Actions</span>
          </button>
        </div>

        <button
          type="button"
          className="actions-close-btn"
          onClick={onClose}
          aria-label="Close sidebar"
          title="Close panel"
        >
          ✕
        </button>
      </div>

      {/* Sidebar Content Area */}
      <div className="actions-sidebar-body">
        {/* TAB 1: CONVERSATION HISTORY TABLE (ChatGPT Style) */}
        {activeTab === 'history' && (
          <div className="actions-panel-content">
            <div className="history-panel-topbar">
              <div className="history-panel-headline">
                <h4 className="actions-panel-title">History</h4>
              </div>

              {/* Search Input */}
              <div className="history-filter-bar">
                <div className="history-search-box">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8"></circle>
                    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                  </svg>
                  <input
                    type="text"
                    className="history-search-input"
                    placeholder="Search past conversations..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      className="history-search-clear"
                      onClick={() => setSearchQuery('')}
                      title="Clear search"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                      </svg>
                    </button>
                  )}
                </div>
              </div>
            </div>

            {loadingHistory && conversations.length === 0 ? (
              <div className="actions-empty-state">
                <div className="auth-spinner" style={{ width: '22px', height: '22px', margin: '0 auto 10px auto' }}></div>
                <div className="actions-empty-text">Loading saved conversations...</div>
              </div>
            ) : historyError ? (
              <div className="chat-error-banner" style={{ margin: '8px 0' }}>
                <span>{historyError}</span>
              </div>
            ) : filteredConversations.length === 0 ? (
              <div className="actions-empty-state">
                <div className="actions-empty-icon">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--text-light)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                  </svg>
                </div>
                <div className="actions-empty-title">
                  {searchQuery ? 'No matching conversations' : 'No conversation history'}
                </div>
                <div className="actions-empty-text">
                  {searchQuery
                    ? 'Try searching with different keywords.'
                    : 'Any question you ask is automatically saved. Start a chat to begin building your policy history!'}
                </div>
              </div>
            ) : (
              /* Structured Real Chatbot History List */
              <div className="chatbot-history-list">
                {filteredConversations.map((conv) => {
                  const isActive = conv.conversation_id === currentConversationId;
                  const timeStr = formatHistoryTime(conv.updated_at || conv.created_at);

                  return (
                    <div
                      key={conv.conversation_id}
                      className={`chatbot-history-card ${isActive ? 'active' : ''}`}
                      onClick={() => onLoadConversation && onLoadConversation(conv.conversation_id, conv.selected_plan_id)}
                      title="Click to resume conversation"
                      role="button"
                      tabIndex={0}
                    >
                      <div className="chatbot-history-card-header">
                        <div className="chatbot-history-card-icon">
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                          </svg>
                        </div>
                        <span className="chatbot-history-card-title">
                          {conv.preview_title || 'Policy Discussion'}
                        </span>
                        {isActive && (
                          <span className="chatbot-history-status-badge">Active</span>
                        )}
                      </div>

                      <div className="chatbot-history-card-footer">
                        <span className="chatbot-history-card-time">{timeStr}</span>
                        {conv.selected_plan_id && (
                          <span className="chatbot-history-plan-pill">
                            {formatPlanLabel(conv.selected_plan_id)}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: QUICK ACTIONS */}
        {activeTab === 'quick_actions' && (
          <div className="actions-panel-content">
            <div className="actions-panel-intro">
              <h4 className="actions-panel-title">Policy Quick Actions</h4>
            </div>

            <div className="actions-cards-stack">
              {quickActions.map((action) => (
                <button
                  key={action.id}
                  type="button"
                  className="action-card-item"
                  onClick={() => onTriggerAction(action.prompt)}
                  title={`Run: "${action.prompt}"`}
                >
                  <div className="action-card-icon-box">{action.icon}</div>
                  <div className="action-card-info">
                    <div className="action-card-title">{action.title}</div>
                  </div>
                  <svg
                    className="action-card-arrow"
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                    <polyline points="12 5 19 12 12 19"></polyline>
                  </svg>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

export default ChatActionsSidebar;
