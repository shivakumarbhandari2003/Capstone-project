import React, { useState, useEffect, useRef, useMemo } from 'react';
import MarkdownContent from './MarkdownContent';
import { ChatActionsSidebar } from './ChatActionsSidebar';
import { ClaimPredictorDrawer } from './ClaimPredictorDrawer';
import { LiquidThinkingOrb } from './ui/orb_animation';


function getInitialSuggestedQuestions(plan) {
  const planId = (plan?.plan_id || '').toUpperCase();

  if (planId.includes('GOLD')) {
    return [
      "What are Hospital Cash & ICU limits?",
      "How do surgical cash tiers payout?",
      "What waiting periods apply to diseases?"
    ];
  } else if (planId.includes('BASIC')) {
    return [
      "What are Basic ICU & Cash limits?",
      "What waiting periods apply to pre-existing?",
      "What are Major Surgery category payouts?"
    ];
  } else if (planId.includes('EMP')) {
    return [
      "What are daily cash & ICU allowances?",
      "What are Major Surgery category limits?",
      "Is pre-existing waiting period waived?"
    ];
  }

  return [
    "What are Hospital Cash & ICU limits?",
    "Which surgical procedures are covered?",
    "What are the policy waiting periods?"
  ];
}

function getContextualFollowUps(query, plan) {
  const q = (query || '').toLowerCase();
  const planId = (plan?.plan_id || '').toUpperCase();
  const planName = plan?.display_title || plan?.plan_name || 'this policy';

  // Sourced strictly from the Confirm & Review schedule
  if (planId.includes('GOLD')) {
    if (q.includes('surg') || q.includes('doctor') || q.includes('fee') || q.includes('operation') || q.includes('procedure') || q.includes('tier') || q.includes('cataract') || q.includes('surgeon')) {
      return [
        "What are the Category 1 to 4 Major Surgery payout amounts under Health Shield – Gold?",
        "Can I claim a Quick Cash advance of up to Rs. 50,000 for surgery?"
      ];
    } else if (q.includes('icu') || q.includes('room') || q.includes('daily') || q.includes('stay') || q.includes('hospital cash') || q.includes('admission')) {
      return [
        "What is the daily ICU benefit amount and maximum days under Health Shield – Gold?",
        "How much is the daily Hospital Cash allowance for stays exceeding 24 hours?"
      ];
    } else if (q.includes('wait') || q.includes('pre-existing') || q.includes('ped') || q.includes('exclusion') || q.includes('condition') || q.includes('disease')) {
      return [
        "What is the waiting period for pre-existing diseases under Health Shield – Gold?",
        "Which specified diseases have a 24-month waiting period under Health Shield – Gold?"
      ];
    } else if (q.includes('claim') || q.includes('file') || q.includes('document') || q.includes('submit') || q.includes('deadline') || q.includes('emergency')) {
      return [
        "What is the deadline for submitting post-discharge claim documents?",
        "Within what timeframe must emergency hospitalizations be notified?"
      ];
    } else if (q.includes('advance') || q.includes('quick cash') || q.includes('restore') || q.includes('check') || q.includes('ambulance') || q.includes('extended')) {
      return [
        "What is the day-care procedure benefit and claim limit per year?",
        "How does the restored cover benefit work under Health Shield – Gold?"
      ];
    }
    return [
      "What is the Major Surgery benefit basis under Health Shield – Gold?",
      "What are the ICU and Hospital Cash daily benefit limits under Health Shield – Gold?"
    ];
  } else if (planId.includes('BASIC')) {
    if (q.includes('surg') || q.includes('doctor') || q.includes('fee') || q.includes('operation') || q.includes('procedure') || q.includes('tier') || q.includes('surgeon')) {
      return [
        "What are the Major Surgery category payouts under Health Shield – Basic?",
        "What is the day-care procedure benefit under Health Shield – Basic?"
      ];
    } else if (q.includes('icu') || q.includes('room') || q.includes('daily') || q.includes('stay') || q.includes('hospital cash') || q.includes('admission')) {
      return [
        "What is the daily ICU benefit and maximum days under Health Shield – Basic?",
        "What is the Hospital Cash daily benefit under Health Shield – Basic?"
      ];
    } else if (q.includes('wait') || q.includes('pre-existing') || q.includes('ped') || q.includes('exclusion') || q.includes('condition')) {
      return [
        "What is the pre-existing disease waiting period under Health Shield – Basic?",
        "Are accidental injuries covered from day 1 under Health Shield – Basic?"
      ];
    } else if (q.includes('claim') || q.includes('file') || q.includes('document') || q.includes('submit')) {
      return [
        "What is the post-discharge claim document submission window under Basic?",
        "What is the premium payment grace period under Health Shield – Basic?"
      ];
    }
    return [
      "What are the Hospital Cash and ICU daily benefits under Health Shield – Basic?",
      "What are the Category 1 to 4 surgical payout limits under Health Shield – Basic?"
    ];
  } else if (planId.includes('EMP')) {
    if (q.includes('surg') || q.includes('doctor') || q.includes('fee') || q.includes('procedure') || q.includes('tier') || q.includes('surgeon')) {
      return [
        "What are the Category 1 to 4 Major Surgery limits for employees?",
        "How many day-care surgical procedures are covered per year?"
      ];
    } else if (q.includes('icu') || q.includes('daily') || q.includes('stay') || q.includes('hospital cash')) {
      return [
        "What is the daily ICU benefit allowance for executive employees?",
        "What are the Hospital Cash limits in the first year versus later years?"
      ];
    } else if (q.includes('wait') || q.includes('pre-existing') || q.includes('ped') || q.includes('exclusion')) {
      return [
        "Is the pre-existing disease waiting period waived for active employees?",
        "What is the initial illness waiting period under the employee plan?"
      ];
    }
    return [
      "What are the daily Hospital Cash and ICU allowances for employees?",
      "What is the Major Surgery benefit basis for executive employees?"
    ];
  }

  // Default / Premium plan fallbacks
  if (q.includes('surg') || q.includes('doctor') || q.includes('fee') || q.includes('surgeon')) {
    return [
      `What are the Major Surgery benefit payouts under ${planName}?`,
      `What is the day-care surgical benefit limit under ${planName}?`
    ];
  } else if (q.includes('icu') || q.includes('room') || q.includes('daily')) {
    return [
      `What is the daily ICU allowance and annual limit under ${planName}?`,
      `What is the Hospital Cash daily payout under ${planName}?`
    ];
  } else if (q.includes('wait') || q.includes('pre-existing') || q.includes('ped')) {
    return [
      `What are the waiting periods for specified illnesses under ${planName}?`,
      `What is the lookback period for pre-existing diseases under ${planName}?`
    ];
  }
  return [
    `What is the Major Surgery benefit basis under ${planName}?`,
    `What is the daily ICU benefit amount under ${planName}?`
  ];
}

export function PlanChatScreen({
  selectedPlan,
  userRole,
  authToken,
  onBackToPlans,
  onSwitchPlan,
  onUnauthorized,
  isActionsSidebarOpen: propIsActionsSidebarOpen,
  onCloseActionsSidebar,
  isClaimPredictorOpen = false,
  onCloseClaimPredictor,
  newChatTrigger,
  onMessageCountChange
}) {
  const createWelcomeMessage = (plan) => ({
    message_id: 'welcome-' + (plan?.plan_id || 'initial'),
    role: 'assistant',
    content: `You are consulting **${plan?.plan_name || 'Selected Policy'}** (\`${plan?.plan_id || 'ACTIVE'}\`). Ask questions regarding benefit payouts, waiting periods, ICU limits, surgery categories, or ask to compare with other customer plans.`,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    citations: []
  });

  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState(() => (selectedPlan ? [createWelcomeMessage(selectedPlan)] : []));
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingMode, setLoadingMode] = useState('rag');
  const [loadingStatusText, setLoadingStatusText] = useState('Retrieving authorized policy evidence & generating grounded answer...');
  const [error, setError] = useState(null);
  const [expandedSources, setExpandedSources] = useState({});
  const [localIsActionsSidebarOpen, setLocalIsActionsSidebarOpen] = useState(false);
  const isActionsSidebarOpen = propIsActionsSidebarOpen !== undefined ? propIsActionsSidebarOpen : localIsActionsSidebarOpen;
  const [actionsSidebarTab, setActionsSidebarTab] = useState('history'); // Default to history tab
  const [historyRefreshTrigger, setHistoryRefreshTrigger] = useState(0);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const recognitionRef = useRef(null);
  const baseSpeechTextRef = useRef('');
  const activeUtteranceRef = useRef(null);
  const [availableVoices, setAvailableVoices] = useState([]);
  const [feedback, setFeedback] = useState({});
  const [copiedId, setCopiedId] = useState(null);
  const [speakingId, setSpeakingId] = useState(null);
  const [editingMessageId, setEditingMessageId] = useState(null);
  const [followUpQuestions, setFollowUpQuestions] = useState([]);

  // Check if conversation is in initial empty state or fresh new chat
  const isFirstTimeOrNewChat = useMemo(() => {
    if (!messages || !Array.isArray(messages) || messages.length <= 1) return true;
    return messages.every((m) => m?.role !== 'user');
  }, [messages]);

  // Compute active suggestions: strictly 3 initial questions on new chat; 2-3 follow-ups after LLM response
  const activeSuggestions = useMemo(() => {
    try {
      if (isFirstTimeOrNewChat) {
        return (getInitialSuggestedQuestions(selectedPlan) || []).slice(0, 3);
      }
      if (followUpQuestions && Array.isArray(followUpQuestions) && followUpQuestions.length > 0) {
        return followUpQuestions.slice(0, 3);
      }
      if (messages && Array.isArray(messages)) {
        const lastUserMsg = [...messages].reverse().find((m) => m?.role === 'user');
        return (getContextualFollowUps(lastUserMsg?.content, selectedPlan) || []).slice(0, 3);
      }
      return [];
    } catch {
      return [];
    }
  }, [isFirstTimeOrNewChat, selectedPlan, followUpQuestions, messages]);
  const [editContent, setEditContent] = useState('');
  const [isListening, setIsListening] = useState(false);

  // Auto-resize textarea height as content grows vertically
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollH = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(Math.max(scrollH, 24), 140)}px`;
    }
  }, [inputText]);

  // Pre-load synthesis voices for English Text-to-Speech
  useEffect(() => {
    if (!('speechSynthesis' in window)) return;
    const loadVoices = () => {
      const v = window.speechSynthesis.getVoices();
      if (v && v.length) {
        setAvailableVoices(v);
      }
    };
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }, []);

  // Cleanup active audio/speech on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (_) {}
        recognitionRef.current = null;
      }
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  // Speech-to-Text: Click once to activate and listen, click again to stop
  const handleToggleVoiceInput = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser. Please use Google Chrome, Microsoft Edge, or Safari.');
      return;
    }

    // If currently listening, stop it cleanly
    if (isListening) {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {
          try {
            recognitionRef.current.abort();
          } catch (_) {}
        }
        recognitionRef.current = null;
      }
      setIsListening(false);
      return;
    }

    // Cancel any active speaker TTS so microphone does not pick up synthesized audio
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      setSpeakingId(null);
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';
      recognition.maxAlternatives = 1;

      // Remember existing text so speech appends smoothly
      baseSpeechTextRef.current = inputText ? (inputText.endsWith(' ') ? inputText : inputText + ' ') : '';

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';
        for (let i = 0; i < event.results.length; i++) {
          const res = event.results[i];
          if (res.isFinal) {
            finalTranscript += res[0].transcript;
          } else {
            interimTranscript += res[0].transcript;
          }
        }
        const sessionSpeech = finalTranscript || interimTranscript;
        setInputText(baseSpeechTextRef.current + sessionSpeech);
      };

      recognition.onerror = (event) => {
        console.warn('Speech recognition status/error:', event.error);
        if (event.error === 'not-allowed') {
          alert('Microphone access was denied. Please allow microphone permissions in your browser to use voice input.');
        }
        setIsListening(false);
        recognitionRef.current = null;
      };

      recognition.onend = () => {
        setIsListening(false);
        recognitionRef.current = null;
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.error('Failed to start speech recognition:', err);
      setIsListening(false);
      recognitionRef.current = null;
    }
  };

  const handleInputKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!loading && inputText.trim()) {
        if (isListening && recognitionRef.current) {
          try {
            recognitionRef.current.stop();
          } catch (_) {}
          recognitionRef.current = null;
          setIsListening(false);
        }
        handleSendMessage();
      }
    }
  };

  const handleCopy = (messageId, text) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedId(messageId);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  const handleToggleFeedback = (messageId, type) => {
    setFeedback((prev) => ({
      ...prev,
      [messageId]: prev[messageId] === type ? null : type
    }));
  };

  const handleStartEdit = (message) => {
    setEditingMessageId(message.message_id);
    setEditContent(message.content);
  };

  const handleCancelEdit = () => {
    setEditingMessageId(null);
    setEditContent('');
  };

  const handleSaveAndResend = () => {
    if (!editContent.trim()) return;
    const query = editContent.trim();
    setEditingMessageId(null);
    setEditContent('');
    handleSendMessage(query);
  };

  const handleRegenerateResponse = (msgIndex) => {
    for (let i = msgIndex - 1; i >= 0; i--) {
      if (messages[i]?.role === 'user') {
        handleSendMessage(messages[i].content);
        break;
      }
    }
  };

  const handleToggleSpeech = (messageId, rawText) => {
    if (!('speechSynthesis' in window)) {
      alert('Text-to-speech is not supported in this browser. Please use Chrome, Edge, or Safari.');
      return;
    }

    // If currently speaking this message, toggle off
    if (speakingId === messageId) {
      window.speechSynthesis.cancel();
      activeUtteranceRef.current = null;
      setSpeakingId(null);
      return;
    }

    // Stop microphone if currently listening
    if (isListening && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (_) {}
      recognitionRef.current = null;
      setIsListening(false);
    }

    // Cancel any previous speech
    window.speechSynthesis.cancel();
    activeUtteranceRef.current = null;
    setSpeakingId(null);

    // Clean markdown, evidence codes, and tables so it reads natural English sentences
    const cleanEnglishText = (rawText || '')
      .replace(/```[\s\S]*?```/g, '') // remove code blocks
      .replace(/\[HS-[A-Z0-9_\-]+(\s+p\.\d+)?\]/gi, '') // remove citation codes like [HS-BASIC-001]
      .replace(/\[Evidence[^\]]*\]/gi, '')
      .replace(/\[Claim[^\]]*\]/gi, '')
      .replace(/\[http[^\]]*\]/gi, '')
      .replace(/\(([A-Z0-9_\-\.]+)\)/g, '')
      .replace(/[*#_~`>]/g, ' ')
      .replace(/[-•]\s+/g, '. ')
      .replace(/\|/g, ', ')
      .replace(/\s+/g, ' ')
      .trim();

    if (!cleanEnglishText) return;

    const utterance = new SpeechSynthesisUtterance(cleanEnglishText);
    activeUtteranceRef.current = utterance; // Prevent Chromium garbage collection bug mid-speech

    // Select the best available English voice
    const voices = availableVoices.length > 0 ? availableVoices : window.speechSynthesis.getVoices();
    const englishVoice =
      voices.find(v => (v.lang === 'en-US' || v.lang === 'en_US') && (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Samantha') || v.name.includes('David') || v.name.includes('Guy') || v.name.includes('Aria') || v.name.includes('Jenny') || v.name.includes('Zira'))) ||
      voices.find(v => v.lang.startsWith('en-US') || v.lang.startsWith('en_US')) ||
      voices.find(v => v.lang.startsWith('en-GB') || v.lang.startsWith('en_GB')) ||
      voices.find(v => v.lang.toLowerCase().startsWith('en')) ||
      null;

    if (englishVoice) {
      utterance.voice = englishVoice;
      utterance.lang = englishVoice.lang;
    } else {
      utterance.lang = 'en-US';
    }

    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    utterance.onstart = () => {
      setSpeakingId(messageId);
    };

    utterance.onend = () => {
      setSpeakingId(null);
      activeUtteranceRef.current = null;
    };

    utterance.onerror = (e) => {
      console.warn('SpeechSynthesis error:', e);
      setSpeakingId(null);
      activeUtteranceRef.current = null;
    };

    // Small timeout ensures cancel() completes cleanly before speak() in Chromium
    setTimeout(() => {
      try {
        if (window.speechSynthesis.paused) {
          window.speechSynthesis.resume();
        }
        window.speechSynthesis.speak(utterance);
        setSpeakingId(messageId);
      } catch (err) {
        console.error('Failed to speak text:', err);
        setSpeakingId(null);
        activeUtteranceRef.current = null;
      }
    }, 50);
  };

  useEffect(() => {
    // Session preservation across page refresh:
    // Check if an active session was already loaded for this plan and role
    if (!selectedPlan?.plan_id) return;
    const sessionKey = `active_conv_${userRole}_${selectedPlan?.plan_id}`;
    const savedConvId = sessionStorage.getItem(sessionKey);
    if (savedConvId) {
      handleLoadConversation(savedConvId, selectedPlan?.plan_id, true);
    } else {
      setMessages([createWelcomeMessage(selectedPlan)]);
      startNewConversation();
    }
  }, [selectedPlan?.plan_id, userRole, authToken]);

  useEffect(() => {
    if (newChatTrigger && newChatTrigger > 0) {
      setMessages([createWelcomeMessage(selectedPlan)]);
      setFollowUpQuestions([]);
      startNewConversation();
    }
  }, [newChatTrigger]);

  useEffect(() => {
    const userCount = messages.filter((m) => m.role === 'user').length;
    onMessageCountChange?.(userCount);
  }, [messages, onMessageCountChange]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const startNewConversation = async () => {
    if (!selectedPlan) return;
    setError(null);
    setFollowUpQuestions([]);
    setExpandedSources({});
    if (onCloseActionsSidebar) onCloseActionsSidebar();
    setLocalIsActionsSidebarOpen(false);

    try {
      const headers = {
        'Content-Type': 'application/json',
        'X-User-Role': userRole
      };
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }

      const reqPayload = {
        selected_plan_id: selectedPlan.plan_id,
        plan_id: selectedPlan.plan_id
      };

      let res;
      try {
        res = await fetch('/api/conversations', {
          method: 'POST',
          headers,
          body: JSON.stringify(reqPayload)
        });
      } catch {
        res = await fetch('http://127.0.0.1:8000/api/conversations', {
          method: 'POST',
          headers,
          body: JSON.stringify(reqPayload)
        });
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
        let msg = `Server error (HTTP ${res.status})`;
        if (typeof data.detail === 'string') {
          msg = data.detail;
        } else if (Array.isArray(data.detail)) {
          msg = data.detail.map((d) => d.msg || JSON.stringify(d)).join(', ');
        } else if (data.detail && typeof data.detail === 'object') {
          msg = JSON.stringify(data.detail);
        }
        throw new Error(msg);
      }

      setConversationId(data.conversation_id);
      const sessionKey = `active_conv_${userRole}_${selectedPlan.plan_id}`;
      sessionStorage.setItem(sessionKey, data.conversation_id);
      setHistoryRefreshTrigger((prev) => prev + 1);

      setMessages([createWelcomeMessage(selectedPlan)]);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleLoadConversation = async (targetConvId, targetPlanId, isAutoResume = false) => {
    if (!targetConvId) return;

    setError(null);
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
        res = await fetch(`/api/conversations/${targetConvId}`, { headers });
      } catch {
        res = await fetch(`http://127.0.0.1:8000/api/conversations/${targetConvId}`, { headers });
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
        // If 404 Not Found or 403 Forbidden, clean up stale sessionStorage
        const targetKey = targetPlanId || selectedPlan?.plan_id;
        const sessionKey = `active_conv_${userRole}_${targetKey}`;
        sessionStorage.removeItem(sessionKey);

        if (isAutoResume || res.status === 404 || res.status === 403) {
          // Seamless auto-fallback to a fresh conversation without blocking error
          await startNewConversation();
          return;
        }

        throw new Error(data.detail || `Server error (HTTP ${res.status})`);
      }

      setConversationId(data.conversation_id);
      const targetKey = targetPlanId || selectedPlan.plan_id;
      const sessionKey = `active_conv_${userRole}_${targetKey}`;
      sessionStorage.setItem(sessionKey, data.conversation_id);

      if (data.messages && data.messages.length > 0) {
        setMessages(data.messages);
        const lastAssistant = [...data.messages].reverse().find((m) => m.role === 'assistant');
        const lastUser = [...data.messages].reverse().find((m) => m.role === 'user');
        if (lastAssistant?.suggested_follow_ups && lastAssistant.suggested_follow_ups.length > 0) {
          setFollowUpQuestions(lastAssistant.suggested_follow_ups.slice(0, 2));
        } else if (lastUser?.content) {
          setFollowUpQuestions(getContextualFollowUps(lastUser.content, selectedPlan));
        } else {
          setFollowUpQuestions([]);
        }
      } else {
        setMessages([createWelcomeMessage(selectedPlan)]);
        setFollowUpQuestions([]);
      }

      if (targetPlanId && targetPlanId !== selectedPlan.plan_id && onSwitchPlan) {
        onSwitchPlan(targetPlanId);
      }
      setHistoryRefreshTrigger((prev) => prev + 1);

    } catch (err) {
      if (isAutoResume) {
        const targetKey = targetPlanId || selectedPlan?.plan_id;
        const sessionKey = `active_conv_${userRole}_${targetKey}`;
        sessionStorage.removeItem(sessionKey);
        await startNewConversation();
      } else {
        setError(`Failed to resume conversation: ${err.message}`);
      }
    }
  };


  const handleSendMessage = async (textToSend) => {
    const query = textToSend || inputText;
    if (!query || !query.trim() || !conversationId) return;

    const userMessage = {
      message_id: 'user-' + Date.now(),
      role: 'user',
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      citations: []
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputText('');
    setLoadingMode('rag');
    setLoading(true);
    setError(null);

    const startTime = Date.now();

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
        res = await fetch(`/api/conversations/${conversationId}/messages`, {
          method: 'POST',
          headers,
          body: JSON.stringify({ query })
        });
      } catch {
        res = await fetch(`http://127.0.0.1:8000/api/conversations/${conversationId}/messages`, {
          method: 'POST',
          headers,
          body: JSON.stringify({ query })
        });
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
        throw new Error(data.detail || `Server error (HTTP ${res.status})`);
      }

      // Enforce the full 6 seconds of thinking animation (3 steps, 2s per step)
      const elapsed = Date.now() - startTime;
      const remainingDelay = Math.max(0, 6000 - elapsed);
      if (remainingDelay > 0) {
        await new Promise((resolve) => setTimeout(resolve, remainingDelay));
      }

      setMessages((prev) => [...prev, data.message]);
      if (data.message?.suggested_follow_ups && data.message.suggested_follow_ups.length > 0) {
        setFollowUpQuestions(data.message.suggested_follow_ups.slice(0, 2));
      } else {
        setFollowUpQuestions(getContextualFollowUps(query, selectedPlan));
      }
      setHistoryRefreshTrigger((prev) => prev + 1);
    } catch (err) {
      const elapsed = Date.now() - startTime;
      const remainingDelay = Math.max(0, 6000 - elapsed);
      if (remainingDelay > 0) {
        await new Promise((resolve) => setTimeout(resolve, remainingDelay));
      }
      setError(err.message);
    } finally {
      setLoading(false);
    }

  };

  const toggleSources = (msgId) => {
    setExpandedSources((prev) => ({
      ...prev,
      [msgId]: !prev[msgId]
    }));
  };


  // Exactly six RAG-grounded actions tailored to the active policy with professional vector icons
  const quickActionsList = [
    {
      id: 'summary',
      icon: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
        </svg>
      ),
      title: 'Executive Summary',
      prompt: 'Provide an executive summary of key benefits, hospital cash, and limits under this policy.'
    },
    {
      id: 'surgery',
      icon: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
      ),
      title: 'Surgical Benefits & Tiers',
      prompt: 'Explain surgical insurance benefits, categories, and payable percentages.'
    },
    {
      id: 'comparison',
      icon: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="18" cy="18" r="3"></circle>
          <circle cx="6" cy="6" r="3"></circle>
          <path d="M13 6h3a2 2 0 0 1 2 2v7"></path>
          <line x1="6" y1="9" x2="6" y2="21"></line>
        </svg>
      ),
      title: selectedPlan.plan_id === 'HS-BASIC-001' ? 'Compare Basic with Gold' : 'Compare with Basic Plan',
      prompt: selectedPlan.plan_id === 'HS-BASIC-001' ? 'Compare Health Shield Basic and Health Shield Gold' : 'Compare this plan with Health Shield Basic'
    },
    {
      id: 'waiting',
      icon: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <polyline points="12 6 12 12 16 14"></polyline>
        </svg>
      ),
      title: 'Waiting Periods',
      prompt: 'What are the waiting periods for pre-existing diseases and specific conditions?'
    },
    {
      id: 'icu',
      icon: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 21h18"></path>
          <path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16"></path>
          <line x1="9" y1="10" x2="15" y2="10"></line>
          <line x1="12" y1="7" x2="12" y2="13"></line>
        </svg>
      ),
      title: 'ICU & Room Rent Limits',
      prompt: 'What are the ICU daily limits, maximum days, and hospital stay criteria?'
    },
    {
      id: 'claims',
      icon: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
          <polyline points="9 12 11 14 15 10"></polyline>
        </svg>
      ),
      title: 'Claim Filing Process',
      prompt: 'What is the claim filing procedure and documentation requirement?'
    }
  ];


  return (
    <div className={`chat-workspace-shell ${(isActionsSidebarOpen || isClaimPredictorOpen) ? 'actions-open' : ''}`}>
      {/* Primary Chat Column */}
      <div className="chat-main-column">

        {error && (
          <div className="chat-error-banner" role="alert">
            <span><strong>Error:</strong> {error}</span>
            <button
              className="btn btn-secondary"
              style={{ padding: '3px 8px', fontSize: '11px' }}
              onClick={() => {
                if (inputText.trim() && conversationId) {
                  handleSendMessage(inputText);
                } else {
                  startNewConversation();
                }
              }}
            >
              Retry
            </button>
          </div>
        )}

        {/* Scrollable Messages Container */}
        <div className="chat-messages-scroll-area">
          <div className="chat-messages-container">
            {messages.map((m, index) => {
              const isUser = m.role === 'user';
              const hasCitations = m.citations && m.citations.length > 0;
              const isSourcesOpen = !!expandedSources[m.message_id];
              const lastAssistantIndex = messages.map((msg) => msg.role).lastIndexOf('assistant');
              const isLatestAssistant = !isUser && index === lastAssistantIndex && messages.some((msg) => msg.role === 'user');
              const currentFollowUps = (m.suggested_follow_ups && m.suggested_follow_ups.length > 0)
                ? m.suggested_follow_ups
                : (isLatestAssistant ? followUpQuestions : []);

              return (
                <div key={m.message_id} className={`chat-message-row ${isUser ? 'user' : 'assistant'}`}>
                  {/* AI Avatar Badge on the left for Assistant */}
                  {!isUser && (
                    <div className="chat-avatar-badge assistant" title="AI Insurance Assistant">
                      AI
                    </div>
                  )}

                  {/* Message Bubble Card */}
                  <div className={`chat-message-bubble ${isUser ? 'user' : 'assistant'}`}>
                    {isUser ? (
                      editingMessageId === m.message_id ? (
                        <div className="chat-user-edit-container">
                          <textarea
                            className="chat-user-edit-textarea"
                            value={editContent}
                            onChange={(e) => setEditContent(e.target.value)}
                            rows={3}
                            autoFocus
                          />
                          <div className="chat-user-edit-actions">
                            <button
                              type="button"
                              className="chat-edit-cancel-btn"
                              onClick={handleCancelEdit}
                            >
                              Cancel
                            </button>
                            <button
                              type="button"
                              className="chat-edit-submit-btn"
                              onClick={handleSaveAndResend}
                              disabled={!editContent.trim()}
                            >
                              Save & Submit
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="chat-user-bubble-inner">
                          <div className="chat-user-text">{m.content}</div>
                          <div className="chat-msg-actions-row user-actions">
                            <button
                              type="button"
                              className="chat-action-btn user-btn"
                              onClick={() => handleStartEdit(m)}
                              title="Edit query"
                              aria-label="Edit query"
                            >
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                              </svg>
                              <span>Edit</span>
                            </button>
                            <button
                              type="button"
                              className={`chat-action-btn user-btn ${copiedId === m.message_id ? 'copied' : ''}`}
                              onClick={() => handleCopy(m.message_id, m.content)}
                              title={copiedId === m.message_id ? "Copied!" : "Copy query"}
                              aria-label="Copy query"
                            >
                              {copiedId === m.message_id ? (
                                <>
                                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                    <polyline points="20 6 9 17 4 12"></polyline>
                                  </svg>
                                  <span>Copied</span>
                                </>
                              ) : (
                                <>
                                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                                  </svg>
                                  <span>Copy</span>
                                </>
                              )}
                            </button>
                          </div>
                        </div>
                      )
                    ) : (
                      <div className="chat-assistant-body">
                        <MarkdownContent
                          content={
                            (m.content || '')
                              .replace(/>\s*\*\*Notice:\*\*.*?illustrative demonstration data[^\n]*\n?/gi, '')
                              .replace(/Contains illustrative demonstration data\.?\n?/gi, '')
                              .replace(/The.*?cited above is illustrative demonstration data and does not constitute an official insurance policy contract\.?\n?/gi, '')
                              .trim()
                          }
                        />

                        {/* Expandable Citations Drawer */}
                        {hasCitations && (
                          <div className="citation-box">
                            <div className="citation-header" onClick={() => toggleSources(m.message_id)}>
                              <span>Verified Policy Sources ({m.citations.length})</span>
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                <span>{isSourcesOpen ? 'Hide Evidence' : 'View Evidence'}</span>
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                  {isSourcesOpen ? <polyline points="18 15 12 9 6 15"></polyline> : <polyline points="6 9 12 15 18 9"></polyline>}
                                </svg>
                              </span>
                            </div>

                            {isSourcesOpen && (
                              <div style={{ marginTop: '6px' }}>
                                {m.citations.map((c, idx) => (
                                  <div key={idx} className="citation-item">
                                    <div className="citation-meta">
                                      <span>{c.plan_name} — Section {c.section_number}: {c.section_title}</span>
                                      <span style={{ color: 'var(--text-light)', fontSize: '10px' }}>
                                        Pages {c.source_page_start}-{c.source_page_end}
                                      </span>
                                    </div>
                                    <div className="citation-snippet">{c.snippet?.replace(/[\u20B9]\s*/g, "Rs. ")}</div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Assistant Response Actions Toolbar */}
                        <div className="chat-msg-actions-row assistant-actions">
                          <button
                            type="button"
                            className={`chat-action-btn ${feedback[m.message_id] === 'up' ? 'active-up' : ''}`}
                            onClick={() => handleToggleFeedback(m.message_id, 'up')}
                            title="Helpful response"
                            aria-label="Good response"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill={feedback[m.message_id] === 'up' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                            </svg>
                          </button>

                          <button
                            type="button"
                            className={`chat-action-btn ${feedback[m.message_id] === 'down' ? 'active-down' : ''}`}
                            onClick={() => handleToggleFeedback(m.message_id, 'down')}
                            title="Unhelpful response"
                            aria-label="Bad response"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill={feedback[m.message_id] === 'down' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path>
                            </svg>
                          </button>

                          <button
                            type="button"
                            className={`chat-action-btn ${copiedId === m.message_id ? 'copied' : ''}`}
                            onClick={() => handleCopy(m.message_id, m.content)}
                            title={copiedId === m.message_id ? "Copied to clipboard" : "Copy response"}
                            aria-label="Copy response"
                          >
                            {copiedId === m.message_id ? (
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="20 6 9 17 4 12"></polyline>
                              </svg>
                            ) : (
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                              </svg>
                            )}
                          </button>

                          <button
                            type="button"
                            className="chat-action-btn"
                            onClick={() => handleRegenerateResponse(index)}
                            title="Regenerate response"
                            aria-label="Regenerate response"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="23 4 23 10 17 10"></polyline>
                              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                            </svg>
                          </button>

                          <button
                            type="button"
                            className={`chat-action-btn ${speakingId === m.message_id ? 'speaking' : ''}`}
                            onClick={() => handleToggleSpeech(m.message_id, m.content)}
                            title={speakingId === m.message_id ? "Stop English speech" : "Read response aloud in English"}
                            aria-label={speakingId === m.message_id ? "Stop English speech" : "Read response aloud in English"}
                          >
                            {speakingId === m.message_id ? (
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <rect x="6" y="6" width="12" height="12" rx="2"></rect>
                              </svg>
                            ) : (
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                                <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>
                              </svg>
                            )}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Follow-up suggestions rendered below the assistant response */}
                    {!isUser && isLatestAssistant && currentFollowUps && currentFollowUps.length > 0 && !loading && (
                      <div className="response-follow-ups-container">
                        <span className="response-follow-ups-label">
                          <span style={{ fontSize: '11px', color: '#007AFF' }}>✦</span> Suggested follow-ups
                        </span>
                        <div className="response-follow-ups-row">
                          {currentFollowUps.slice(0, 2).map((q, qIdx) => (
                            <button
                              key={qIdx}
                              type="button"
                              className="response-follow-up-pill"
                              onClick={() => handleSendMessage(q)}
                              title={`Ask follow-up: "${q}"`}
                            >
                              <span className="pill-text">{q.replace(/[\u20B9]\s*/g, "Rs. ")}</span>
                              <svg className="pill-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                                <polyline points="12 5 19 12 12 19"></polyline>
                              </svg>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* User Avatar Badge on the right for User Query */}
                  {isUser && (
                    <div className="chat-avatar-badge user" title={userRole === 'employee' ? 'Staff Underwriter' : 'Customer Policyholder'}>
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
                        <circle cx="12" cy="7" r="4" />
                      </svg>
                    </div>
                  )}

                </div>
              );
            })}

            {loading && (
              <div className="chat-message-row assistant thinking-loading-row">
                <LiquidThinkingOrb size={51} color="#007AFF" theme="auto" mode={loadingMode} />
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Elevated Bottom Input Dock */}
        <div className="chat-bottom-dock">
          {/* Liquid Glass Initial Suggested Questions - Strictly on New / First-Time Chat */}
          {isFirstTimeOrNewChat && activeSuggestions && activeSuggestions.length > 0 && !loading && (
            <div className="chat-suggestions-bar">
              <div className="chat-suggestions-chips-row">
                {activeSuggestions.map((q, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="chat-suggestion-chip"
                    onClick={() => handleSendMessage(q)}
                    title={`Ask: "${q}"`}
                  >
                    <span className="chip-sparkle">✦</span>
                    <span className="chip-text">{q.replace(/[\u20B9]\s*/g, "Rs. ")}</span>
                    <svg className="chip-arrow" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="5" y1="12" x2="19" y2="12"></line>
                      <polyline points="12 5 19 12 12 19"></polyline>
                    </svg>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="chat-input-wrapper">
            <div className="chat-input-field-container">
              <span className="chat-input-prefix-icon" title="Query input">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
              </span>
              <textarea
                ref={textareaRef}
                className="chat-input-field"
                placeholder={`Ask about ${selectedPlan.display_title || 'policy'} terms, waiting periods, or limits...`}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleInputKeyDown}
                rows={1}
                disabled={loading}
              />
              <div className="chat-input-actions-group">
                {/* Speech to text mic button: click once to listen, click again to stop */}
                <button
                  type="button"
                  className={`chat-mic-btn ${isListening ? 'listening' : ''}`}
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    handleToggleVoiceInput();
                  }}
                  disabled={loading}
                  title={isListening ? "Listening... Click to stop" : "Click to speak your input (Speech to Text)"}
                  aria-label={isListening ? "Stop listening" : "Start speaking"}
                >
                  {isListening ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="6" y="6" width="12" height="12" rx="2"></rect>
                    </svg>
                  ) : (
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                      <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                      <line x1="12" y1="19" x2="12" y2="23"></line>
                      <line x1="8" y1="23" x2="16" y2="23"></line>
                    </svg>
                  )}
                </button>

                {/* Send Button */}
                <button
                  type="button"
                  className={`chat-submit-circle-btn ${inputText.trim() ? 'has-content' : ''}`}
                  onClick={() => {
                    if (isListening && recognitionRef.current) {
                      recognitionRef.current.stop();
                      setIsListening(false);
                    }
                    handleSendMessage();
                  }}
                  disabled={loading || !inputText.trim()}
                  title={inputText.trim() ? "Send query (Enter)" : "Enter a question about this policy"}
                >
                  {loading ? (
                    <div className="chat-submit-spinner" />
                  ) : (
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="22" y1="2" x2="11" y2="13" />
                      <polygon points="22 2 15 22 11 13 2 9 22 2" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Sidebar: Dedicated for Quick Actions & History Table */}
      <ChatActionsSidebar
        isOpen={isActionsSidebarOpen && !isClaimPredictorOpen}
        activeTab={actionsSidebarTab}
        onSelectTab={(tab) => setActionsSidebarTab(tab)}
        onClose={() => {
          if (onCloseActionsSidebar) onCloseActionsSidebar();
          setLocalIsActionsSidebarOpen(false);
        }}
        messages={messages}
        quickActions={quickActionsList}
        currentConversationId={conversationId}
        selectedPlan={selectedPlan}
        authToken={authToken}
        userRole={userRole}
        historyRefreshTrigger={historyRefreshTrigger}
        onTriggerAction={(prompt) => handleSendMessage(prompt)}
        onLoadConversation={handleLoadConversation}
        onStartNewChat={startNewConversation}
        onSelectHistory={(query) => setInputText(query)}
      />

      {/* Employee-Only Predictive Claim Estimator Drawer */}
      {userRole === 'employee' && (
        <ClaimPredictorDrawer
          isOpen={Boolean(isClaimPredictorOpen)}
          onClose={onCloseClaimPredictor}
          authToken={authToken}
          currentConversationId={conversationId}
          selectedPlan={selectedPlan}
          onPredictionStart={() => {
            setLoadingMode('claim');
            setLoadingStatusText('Estimating claim payout & evaluating parameters...');
            setLoading(true);
            setError(null);
            setTimeout(() => {
              messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
            }, 60);
          }}
          onPredictionSuccess={(newAssistantMsg) => {
            setLoading(false);
            if (newAssistantMsg) {
              setMessages((prev) => {
                if (!prev.some((m) => m.message_id === newAssistantMsg.message_id)) {
                  return [...prev, newAssistantMsg];
                }
                return prev;
              });
              setHistoryRefreshTrigger((prev) => prev + 1);
              setTimeout(() => {
                messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
              }, 60);
            }
          }}
          onPredictionError={() => {
            setLoading(false);
          }}
        />
      )}

    </div>
  );
}

export default PlanChatScreen;
