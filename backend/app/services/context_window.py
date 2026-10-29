import re
from typing import Optional, Any
from pydantic import BaseModel, Field

BENEFIT_KEYWORD_PATTERNS = {
    "major surgical": re.compile(r"\b(major\s+surgery|major\s+surgical|surgery|surgical|surgeries|operation|operations|category\s+[1-4]|categories\s+1\s+to\s+4)\b", re.IGNORECASE),
    "hospital cash": re.compile(r"\b(hospital\s+cash|daily\s+cash|daily\s+allowance|cash\s+benefit)\b", re.IGNORECASE),
    "icu benefit": re.compile(r"\b(icu|intensive\s+care|icu\s+benefit|icu\s+cash|icu\s+allowance)\b", re.IGNORECASE),
    "day-care": re.compile(r"\b(day-?care|day\s+care|minor\s+surgery)\b", re.IGNORECASE),
    "waiting period": re.compile(r"\b(waiting\s+period|waiting\s+periods|pre-?existing|ped|lookback|look-?back)\b", re.IGNORECASE),
    "health check-up": re.compile(r"\b(health\s+check-?up|check-?up|medical\s+check-?up)\b", re.IGNORECASE),
    "ambulance": re.compile(r"\b(ambulance|transport\s+allowance)\b", re.IGNORECASE),
    "quick cash": re.compile(r"\b(quick\s+cash|cash\s+advance|surgery\s+advance)\b", re.IGNORECASE),
    "restored cover": re.compile(r"\b(restored\s+cover|restoration|cover\s+restoration)\b", re.IGNORECASE),
    "claims": re.compile(r"\b(claim|claims|reimbursement|post-?discharge|submission\s+window)\b", re.IGNORECASE),
}

PLAN_KEYWORD_PATTERNS = {
    "HS-BASIC-001": re.compile(r"\b(health\s+shield\s+[–-]\s*basic|hs-basic|basic\s+plan|under\s+basic)\b", re.IGNORECASE),
    "HS-GOLD-001": re.compile(r"\b(health\s+shield\s+[–-]\s*gold|hs-gold|gold\s+plan|under\s+gold)\b", re.IGNORECASE),
    "HS-PREMIUM-001": re.compile(r"\b(health\s+shield\s+[–-]\s*premium|hs-premium|premium\s+plan|under\s+premium)\b", re.IGNORECASE),
    "EMP-INS-001": re.compile(r"\b(executive\s+employee|emp-ins|employee\s+plan|under\s+employee)\b", re.IGNORECASE),
}

class ContextMessage(BaseModel):
    role: str
    content: str

class ContextTurn(BaseModel):
    turn_index: int
    user_message: str
    assistant_message: str
    mentioned_benefits: list[str] = Field(default_factory=list)
    mentioned_plans: list[str] = Field(default_factory=list)
    estimated_tokens: int = 0

class ContextWindowResult(BaseModel):
    messages: list[ContextMessage] = Field(default_factory=list)
    selected_turns: list[ContextTurn] = Field(default_factory=list)
    discussed_benefits: list[str] = Field(default_factory=list)
    discussed_plans: list[str] = Field(default_factory=list)
    last_user_query: Optional[str] = None
    last_assistant_answer: Optional[str] = None
    formatted_history_text: str = ""
    is_truncated: bool = False
    estimated_tokens: int = 0

class ContextWindowManager:
    """
    Optimized, bounded 6-message conversation context window.
    Maintains up to the last 6 messages (~3 conversational turns) with zero latency overhead.
    Accurately detects whether a new query is related to the conversation context.
    """

    @staticmethod
    def extract_context_window(
        conversation_history: list[dict],
        max_messages: int = 6,
        max_tokens: int = 1200
    ) -> ContextWindowResult:
        if not conversation_history:
            return ContextWindowResult()

        # Take strictly the last 6 messages
        raw_msgs = conversation_history[-max_messages:]
        normalized_msgs: list[ContextMessage] = []
        for m in raw_msgs:
            role = m.get("role", "user")
            content = m.get("content") or m.get("user_query") or m.get("assistant_answer") or m.get("text") or ""
            if content:
                normalized_msgs.append(ContextMessage(role=role, content=content.strip()))

        if not normalized_msgs:
            return ContextWindowResult()

        # Pair into conversational turns
        turns: list[ContextTurn] = []
        pending_user: Optional[str] = None
        turn_idx = 1
        last_uq = None
        last_ans = None

        for m in normalized_msgs:
            if m.role == "user":
                pending_user = m.content
                last_uq = m.content
            elif m.role == "assistant":
                u_text = pending_user or ""
                a_text = m.content
                last_ans = a_text

                # Detect benefits mentioned in this turn
                turn_text = f"{u_text} {a_text}".lower()
                turn_benefits = [
                    b_name for b_name, pat in BENEFIT_KEYWORD_PATTERNS.items()
                    if pat.search(turn_text)
                ]
                turn_plans = [
                    p_id for p_id, pat in PLAN_KEYWORD_PATTERNS.items()
                    if pat.search(turn_text)
                ]

                # Cap assistant message preview in turn representation to keep within token budget
                clean_preview = a_text[:350].replace("\n", " ").strip()
                est_toks = int(len(u_text.split()) * 1.3 + len(clean_preview.split()) * 1.3)

                turns.append(ContextTurn(
                    turn_index=turn_idx,
                    user_message=u_text,
                    assistant_message=a_text,
                    mentioned_benefits=turn_benefits,
                    mentioned_plans=turn_plans,
                    estimated_tokens=est_toks
                ))
                turn_idx += 1
                pending_user = None

        # Gather all discussed benefits and plans preserving recency order
        all_benefits: list[str] = []
        all_plans: list[str] = []
        for t in reversed(turns):
            for b in t.mentioned_benefits:
                if b not in all_benefits:
                    all_benefits.append(b)
            for p in t.mentioned_plans:
                if p not in all_plans:
                    all_plans.append(p)

        # Build clean formatted text for the prompt
        formatted_lines = []
        total_tokens = 0
        is_trunc = False

        for t in turns:
            u_clean = t.user_message.replace("<", "&lt;").replace(">", "&gt;")
            a_clean = t.assistant_message.replace("<", "&lt;").replace(">", "&gt;")
            # Truncate assistant preview to 280 chars to safeguard prompt budget
            if len(a_clean) > 280:
                a_clean = a_clean[:280] + "..."
                is_trunc = True

            line = f"User: {u_clean}\nAssistant: {a_clean}"
            formatted_lines.append(line)
            total_tokens += int(len(line.split()) * 1.3)

        formatted_text = "\n\n".join(formatted_lines)

        return ContextWindowResult(
            messages=normalized_msgs,
            selected_turns=turns,
            discussed_benefits=all_benefits,
            discussed_plans=all_plans,
            last_user_query=last_uq,
            last_assistant_answer=last_ans,
            formatted_history_text=formatted_text,
            is_truncated=is_trunc or total_tokens > max_tokens,
            estimated_tokens=total_tokens
        )

    @staticmethod
    def is_query_related(query: str, context_win: ContextWindowResult) -> bool:
        """
        Determines whether the user query depends on or refers to the preceding conversation.
        """
        if not context_win.selected_turns and not context_win.messages:
            return False

        q_lower = query.lower().strip()

        # 1. Pronoun coreferences
        pronoun_pattern = re.compile(
            r"\b(it|its|that|this|these|those|they|them|does\s+it|is\s+it|can\s+it|is\s+there)\b",
            re.IGNORECASE
        )
        if pronoun_pattern.search(q_lower):
            return True

        # 2. Referential phrases pointing to previous output or table
        referential_pattern = re.compile(
            r"\b(the\s+above\s+table|above\s+table|this\s+table|the\s+table|the\s+above\s+data|"
            r"above\s+data|the\s+above|these\s+tiers|these\s+categories|the\s+percentages|"
            r"the\s+limits|these\s+limits|the\s+figures)\b",
            re.IGNORECASE
        )
        if referential_pattern.search(q_lower):
            return True

        # 3. Plain-language explanation or simplification requests
        explain_pattern = re.compile(
            r"\b(explain\s+(?:the\s+above|this|it|in\s+simple)|in\s+simple\s+(?:words|terms)|"
            r"simplify\s+this|simplify|break\s+down|what\s+does\s+(?:this|it|the\s+above)\s+mean|"
            r"in\s+plain\s+english|for\s+a\s+beginner|tell\s+me\s+more\s+about\s+(?:this|that))\b",
            re.IGNORECASE
        )
        if explain_pattern.search(q_lower):
            return True

        # 4. Duration / day count calculations (e.g. "What about five days?", "How much for 5 days?")
        duration_pattern = re.compile(
            r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve|fifteen|twenty|thirty)\s+days?\b",
            re.IGNORECASE
        )
        if duration_pattern.search(q_lower) and any(term in q_lower for term in ["what about", "how much", "for", "calculate", "cost", "payout"]):
            return True

        # 5. Generic sub-limit / cap follow-ups without naming the benefit
        generic_limit_pattern = re.compile(
            r"^\s*(?:what\s+is\s+(?:the\s+|its\s+)?(?:maximum|max|cap|limit)|"
            r"is\s+there\s+a\s+(?:cap|limit|maximum)|what\s+are\s+the\s+limits|"
            r"how\s+much\s+is\s+the\s+limit|what\s+about\s+its\s+limit)[\s?.!]*$",
            re.IGNORECASE
        )
        if generic_limit_pattern.search(q_lower):
            return True

        # 6. Relative comparisons using referential pronouns (e.g. "Now compare it with Basic")
        if any(w in q_lower for w in ["compare", "versus", "vs", "difference"]) and any(p in q_lower.split() for p in ["it", "its", "that", "this"]):
            return True

        return False

