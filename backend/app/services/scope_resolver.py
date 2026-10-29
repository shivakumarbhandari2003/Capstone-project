import re
from typing import Optional
from pydantic import BaseModel, Field
from backend.app.services.auth_service import AuthorizationService, EMPLOYEE_ONLY_PLANS
from backend.app.registry.plans import get_plan_by_id
from backend.app.core.logging_config import logger
from backend.app.services.context_window import ContextWindowManager, ContextWindowResult

class ScopeResolutionResult(BaseModel):
    selected_plan_id: str
    authorized_plans: list[str]
    effective_scope: list[str]
    reason: str  # "greeting", "default_selected_plan", "explicit_comparison", "follow_up", "clarification_needed", "access_restricted", "disclosure_request", "out_of_scope", "mixed_query"
    is_comparison: bool = False
    is_ambiguous: bool = False
    is_greeting: bool = False
    is_disclosure_request: bool = False
    is_out_of_scope: bool = False
    is_mixed: bool = False
    refusal_message: Optional[str] = None
    mixed_insurance_query: Optional[str] = None
    mixed_unrelated_topic: Optional[str] = None
    greeting_message: Optional[str] = None
    greeting_prefix: Optional[str] = None
    clarification_prompt: Optional[str] = None
    resolved_query: Optional[str] = None
    search_query: Optional[str] = None
    denied_plans: list[str] = Field(default_factory=list)
    context_window: Optional[ContextWindowResult] = None
    is_context_related: bool = False

PLAN_KEYWORDS: dict[str, str] = {
    "basic": "HS-BASIC-001",
    "hs-basic": "HS-BASIC-001",
    "hs-basic-001": "HS-BASIC-001",
    "gold": "HS-GOLD-001",
    "hs-gold": "HS-GOLD-001",
    "hs-gold-001": "HS-GOLD-001",
    "health shield premium": "HS-PREMIUM-001",
    "premium plan": "HS-PREMIUM-001",
    "premium policy": "HS-PREMIUM-001",
    "premium tier": "HS-PREMIUM-001",
    "hs-premium": "HS-PREMIUM-001",
    "hs-premium-001": "HS-PREMIUM-001",
    "employee": "EMP-INS-001",
    "executive": "EMP-INS-001",
    "emp-ins": "EMP-INS-001",
    "emp-ins-001": "EMP-INS-001"
}

GREETING_CORE = r"(?:hello\b|hi\b|hey\b|howdy\b|greetings\b|hiya\b|good\s+(?:morning|afternoon|evening|day)\b)"
COURTESY_CORE = r"(?:how(?:['’]?s|\s+is)\s+it\s+going\b|how\s+are\s+you(?:\s+doing)?\b|how\s+do\s+you\s+do\b|hope\s+you\s+are\s+(?:doing\s+)?well\b|what['’]?s\s+up\b)"
ASSIST_CORE = r"(?:can\s+you\s+(?:please\s+)?help(?:\s+me)?(?:\s+please)?\b|could\s+you\s+(?:please\s+)?help(?:\s+me)?(?:\s+please)?\b|can\s+you\s+(?:please\s+)?assist(?:\s+me)?(?:\s+please)?\b|i\s+need\s+(?:some\s+)?help\b|need\s+(?:some\s+)?help\b|help\s+me(?:\s+please)?\b|are\s+you\s+there\b|what\s+can\s+you\s+do\b|who\s+are\s+you\b)"

PURE_GREETING_PATTERN = re.compile(
    rf"^\s*(?:{GREETING_CORE}(?:\s+there\b)?|{COURTESY_CORE}|{ASSIST_CORE})"
    rf"(?:[\s,!.;:\-]+(?:{GREETING_CORE}(?:\s+there\b)?|{COURTESY_CORE}|{ASSIST_CORE}))*[\s!?.~]*$",
    re.IGNORECASE
)

GREETING_PREFIX_PATTERN = re.compile(
    rf"^\s*({GREETING_CORE}(?:\s+there\b)?|{COURTESY_CORE}|{ASSIST_CORE})"
    rf"(?:[\s,!.;:\-]+(?:{GREETING_CORE}(?:\s+there\b)?|{COURTESY_CORE}|{ASSIST_CORE}))*"
    rf"[\s,!.;:\-]+",
    re.IGNORECASE
)

GREETING_PATTERN = PURE_GREETING_PATTERN

DISCLOSURE_PATTERNS = [
    re.compile(r"what\s+(is|are)\s+(the|your|its|all)\s+.*system\s+(prompt|instruction|directive|rule)s?", re.IGNORECASE),
    re.compile(r"(reveal|print|disclose|dump|output|show|tell|share|display|give)\s+(?:me\s+)?(?:your\s+|the\s+|all\s+)?(?:system\s+|developer\s+|internal\s+|hidden\s+)?(?:prompts?|instructions?|rules?|directives?|secrets?|api\s*keys?|backend\s+config)", re.IGNORECASE),
    re.compile(r"what\s+(is|are)\s+(the|your|its)\s+(hidden|internal|developer)\s+(instruction|prompt|directive)s?", re.IGNORECASE),
    re.compile(r"repeat\s+(everything|the\s+text|all\s+system\s+prompts?)\s*(above|before|starting\s+with|verbatim)?", re.IGNORECASE),
    re.compile(r"what\s+instructions\s+were\s+you\s+given", re.IGNORECASE),
    re.compile(r"what\s+is\s+your\s+prompt\b", re.IGNORECASE),
]

OUT_OF_SCOPE_PATTERNS = [
    (re.compile(r"\b(ipl(\s+20\d\d)?|indian\s+premier\s+league)\b", re.IGNORECASE), "IPL"),
    (re.compile(r"\b(cricket(\s+match|\s+score|\s+world\s+cup)?|bcci|icc|test\s+match)\b", re.IGNORECASE), "cricket"),
    (re.compile(r"\b(football|soccer|fifa|champions\s+league|premier\s+league)\b", re.IGNORECASE), "football"),
    (re.compile(r"\b(nba|basketball|tennis|wimbledon|olympics|badminton)\b", re.IGNORECASE), "sports"),
    (re.compile(r"\b(recipe|bake\s+(a\s+)?cake|cake\s+recipe|how\s+to\s+cook|ingredients\s+for)\b", re.IGNORECASE), "recipes and cooking"),
    (re.compile(r"\b(movies?|cinema|actors?|actress|bollywood|hollywood|netflix|marvel|box\s+office)\b", re.IGNORECASE), "movies and entertainment"),
    (re.compile(r"\b(weather\s+in|weather\s+today|temperature\s+in|forecast)\b", re.IGNORECASE), "weather forecasting"),
    (re.compile(r"\b(capital\s+of|population\s+of|president\s+of|prime\s+minister\s+of)\b", re.IGNORECASE), "general world trivia"),
    (re.compile(r"\b(write\s+(a\s+)?python|write\s+code|programming|leetcode|sql\s+query|function\s+to\s+sort)\b", re.IGNORECASE), "programming"),
]

INSURANCE_TERMS_PATTERNS = [
    re.compile(r"\b(insurance|policy|plan|plans|benefit|benefits|cover|covered|coverage|claim|claims)\b", re.IGNORECASE),
    re.compile(r"\b(hospital|hospitali[sz]ation|hospitali[sz]ed|inpatient|daycare|day\s+care)\b", re.IGNORECASE),
    re.compile(r"\b(icu|intensive\s+care|room\s+rent|ambulance|emergency\s+van|medicines?|doctor)\b", re.IGNORECASE),
    re.compile(r"\b(surgery|surgical|surgeries|treatment|treatments|illness|illnesses|disease|diseases)\b", re.IGNORECASE),
    re.compile(r"\b(waiting\s+period|waiting\s+periods|exclusion|exclusions|co-?pay(ment)?|deductible)\b", re.IGNORECASE),
    re.compile(r"\b(cashless|reimbursement|pre-?existing|ayush|cataract|hernia|accident|maternity)\b", re.IGNORECASE),
    re.compile(r"\b(sum\s+insured|sub-?limit|limit|limits|cap|caps|premium|premiums|eligibility|eligible)\b", re.IGNORECASE),
    re.compile(r"\b(cancel|cancellation|grievance|ombudsman|tpa|out\s+of\s+pocket|reimburse)\b", re.IGNORECASE),
    re.compile(r"\b(admit|admitted|discharge|stay|expenses?|payout|operation|money\s+back)\b", re.IGNORECASE),
]

class ScopeResolver:
    """
    Determines effective retrieval scope and query intent for a plan-scoped session.
    Distinguishes legitimate policy questions, greetings, comparisons, disclosure requests,
    out-of-scope non-insurance queries, and mixed queries before policy retrieval executes.
    """

    @staticmethod
    def resolve_scope(
        query: str,
        selected_plan_id: str,
        role: str,
        conversation_history: Optional[list[dict]] = None
    ) -> ScopeResolutionResult:
        # Extract bounded 6-message context window first (sub-millisecond in-memory)
        context_win = ContextWindowManager.extract_context_window(
            conversation_history or [],
            max_messages=6,
            max_tokens=1200
        )

        q_lower = query.lower().strip()
        authorized_set = AuthorizationService.get_authorized_plans(role)
        authorized_list = sorted(list(authorized_set))

        # Ensure selected plan is authorized
        if selected_plan_id not in authorized_set:
            selected_plan_id = "HS-BASIC-001" if "HS-BASIC-001" in authorized_set else authorized_list[0]

        # 0. Check for Greeting query
        if PURE_GREETING_PATTERN.match(q_lower):
            p_info = get_plan_by_id(selected_plan_id)
            p_name = p_info.plan_name if p_info else selected_plan_id
            greeting_msg = (
                f"Hello! I'm here to help you navigate your health insurance coverage. "
                f"Under **{p_name}**, I can assist you with understanding your benefits, daily cash & ICU allowances, "
                f"surgical tiers, waiting periods, or filing a claim. How can I assist you today?"
            )
            return ScopeResolutionResult(
                selected_plan_id=selected_plan_id,
                authorized_plans=authorized_list,
                effective_scope=[selected_plan_id],
                reason="greeting",
                is_comparison=False,
                is_ambiguous=False,
                is_greeting=True,
                greeting_message=greeting_msg,
                context_window=context_win
            )

        # 0.1 Check for Mixed Intent: Greeting Prefix with Substantive Insurance / Policy Query
        # (e.g. "Hey there, can you explain my Gold plan?", "Good morning, what is the hospital cash benefit?")
        greeting_prefix = None
        cleaned_subquery = query
        prefix_match = GREETING_PREFIX_PATTERN.match(query)
        if prefix_match:
            candidate_prefix = prefix_match.group(0).strip(" ,!.;:-")
            candidate_remainder = query[prefix_match.end():].strip()
            if candidate_remainder:
                greeting_prefix = candidate_prefix
                cleaned_subquery = candidate_remainder
                q_lower = cleaned_subquery.lower()

        # 1. Check for System Prompt / Disclosure Request
        for pattern in DISCLOSURE_PATTERNS:
            if pattern.search(query):
                logger.warning(f"Disclosure request detected by ScopeResolver: '{query[:80]}'")
                return ScopeResolutionResult(
                    selected_plan_id=selected_plan_id,
                    authorized_plans=authorized_list,
                    effective_scope=[selected_plan_id],
                    reason="disclosure_request",
                    is_disclosure_request=True,
                    refusal_message="I cannot disclose internal system instructions, configuration directives, or private prompts. I am an AI Health Insurance Assistant designed to help you understand health insurance policy benefits, claims, waiting periods, and eligibility.",
                    context_window=context_win
                )

        # 2. Check for Out-of-Scope and Mixed Queries
        matched_oos_topic = None
        for pattern, topic_name in OUT_OF_SCOPE_PATTERNS:
            m = pattern.search(query)
            if m:
                # Capture specific match if available (e.g. IPL 2026)
                matched_text = m.group(0).strip()
                if "ipl" in matched_text.lower():
                    matched_oos_topic = "IPL 2026" if "2026" in query else ("IPL 2024" if "2024" in query else "IPL")
                else:
                    matched_oos_topic = topic_name
                break

        has_insurance_intent = any(pat.search(query) for pat in INSURANCE_TERMS_PATTERNS)
        
        # Check plan keywords
        detected_plans = set()
        for word, pid in PLAN_KEYWORDS.items():
            if re.search(rf"\b{re.escape(word)}\b", q_lower):
                detected_plans.add(pid)
                has_insurance_intent = True

        # Special check for bare "premium": Only treat as HS-PREMIUM-001 if explicitly used as plan name or comparison
        if "HS-PREMIUM-001" not in detected_plans and re.search(r"\bpremium\b", q_lower):
            is_cost_context = bool(
                re.search(r"\b(annual|monthly|renewal|guaranteed|total|quarterly|half-yearly|tax|taxes|pay|paying|deduct|deducted|salary|rate|amount|waiver|protection)\s+premium\b", q_lower) or
                re.search(r"\bpremium\s+(?:of|is|rate|amount|cost|payment|waiver|protection|table|schedule|deducted|due)\b", q_lower) or
                re.search(r"\bmy\s+premium\b", q_lower) or
                re.search(r"\bpremium\s+(?:will\s+be\s+deducted|would\s+be)\b", q_lower)
            )
            is_plan_context = bool(
                re.search(r"\b(compare|versus|vs|between|or|with)\s+.*?\bpremium\b", q_lower) or
                re.search(r"\bpremium\s+(?:and|or|vs|versus)\b", q_lower)
            )
            if is_plan_context and not is_cost_context:
                detected_plans.add("HS-PREMIUM-001")
            has_insurance_intent = True

        # Check follow-up context using 6-message context window
        follow_up_tokens = [
            "its", "it", "that", "those", "this", "these", "does it", "is there",
            "what about", "is it covered", "how much is covered", "the above",
            "the above table", "above table", "this table", "the table", "above data",
            "the above data", "in simple words", "in simple terms", "simplify", "break down"
        ]
        has_followup_pronouns = any(re.search(rf"\b{re.escape(t)}\b", q_lower) for t in follow_up_tokens)
        is_related_to_context = ContextWindowManager.is_query_related(cleaned_subquery, context_win)
        if (conversation_history or context_win.selected_turns) and (has_followup_pronouns or is_related_to_context):
            has_insurance_intent = True

        # Handle Mixed Query (Insurance Question + Unrelated Question)
        if matched_oos_topic and has_insurance_intent:
            logger.info(f"Mixed query detected. Insurance intent present alongside unrelated topic: {matched_oos_topic}")
            # Isolate insurance sub-query by stripping out-of-scope clause
            split_patterns = [r"\s+(?:and\s+also|and\s+who|and\s+what|also|as\s+well\s+as)\s+"]
            insurance_part = cleaned_subquery
            for sp in split_patterns:
                parts = re.split(sp, cleaned_subquery, flags=re.IGNORECASE)
                if len(parts) > 1:
                    # Keep the part that contains insurance terms
                    for p in parts:
                        if any(ipat.search(p) for ipat in INSURANCE_TERMS_PATTERNS) or any(re.search(rf"\b{k}\b", p.lower()) for k in PLAN_KEYWORDS):
                            insurance_part = p.strip()
                            break

            return ScopeResolutionResult(
                selected_plan_id=selected_plan_id,
                authorized_plans=authorized_list,
                effective_scope=[selected_plan_id],
                reason="mixed_query",
                is_mixed=True,
                mixed_insurance_query=insurance_part,
                mixed_unrelated_topic=matched_oos_topic,
                greeting_prefix=greeting_prefix,
                resolved_query=insurance_part
            )

        # Handle Pure Out-of-Scope Query
        if matched_oos_topic and not has_insurance_intent:
            logger.info(f"Pure out-of-scope query rejected without retrieval: topic='{matched_oos_topic}'")
            return ScopeResolutionResult(
                selected_plan_id=selected_plan_id,
                authorized_plans=authorized_list,
                effective_scope=[selected_plan_id],
                reason="out_of_scope",
                is_out_of_scope=True,
                greeting_prefix=greeting_prefix,
                refusal_message=(
                    f"I'd love to help, but I'm a health insurance assistant and can help with policy benefits, eligibility, "
                    f"claims, and related insurance questions. I can't answer questions about {matched_oos_topic} because they are outside my scope. "
                    f"If you have any questions about your health insurance policy, please let me know!"
                ),
                context_window=context_win
            )

        # Handle General Out-of-Scope Query with zero insurance context
        # (e.g. "What is the capital of France?", "Who is Elon Musk?")
        general_trivia_patterns = [
            r"^(?:what\s+is\s+the\s+capital\s+of|who\s+is|who\s+won|tell\s+me\s+a\s+joke|how\s+to\s+make|recipe\s+for)",
        ]
        if not has_insurance_intent and not has_followup_pronouns and any(re.search(p, q_lower) for p in general_trivia_patterns):
            logger.info(f"General trivia query rejected without retrieval: '{query[:60]}'")
            return ScopeResolutionResult(
                selected_plan_id=selected_plan_id,
                authorized_plans=authorized_list,
                effective_scope=[selected_plan_id],
                reason="out_of_scope",
                is_out_of_scope=True,
                greeting_prefix=greeting_prefix,
                refusal_message=(
                    "I'd love to help, but I'm a health insurance assistant and can help with policy benefits, eligibility, "
                    "claims, and related insurance questions. I can't answer this question because it is outside my scope. "
                    "If you have any questions regarding your health insurance coverage, feel free to ask!"
                ),
                context_window=context_win
            )

        # 3. Check for Ambiguous Comparisons
        general_compare_patterns = [
            r"^(?:compare|difference\s+between|which\s+is\s+better)\s+(?:the\s+)?plans\??$",
            r"^(?:which\s+plan\s+is\s+better|which\s+one\s+is\s+better)\??$",
            r"^(?:compare\s+all|compare\s+them|how\s+do\s+they\s+compare)\??$"
        ]
        if any(re.search(pat, q_lower) for pat in general_compare_patterns):
            logger.info("Ambiguous comparison detected. Requesting clarification.")
            return ScopeResolutionResult(
                selected_plan_id=selected_plan_id,
                authorized_plans=authorized_list,
                effective_scope=[selected_plan_id],
                reason="clarification_needed",
                is_comparison=True,
                is_ambiguous=True,
                clarification_prompt="Which plans would you like to compare? You can compare Basic, Gold, and Premium (or ask to compare all customer plans)."
            )

        # 4. Check for "compare all three" / "compare customer plans"
        all_customer_patterns = [
            r"compare\s+all\s+(?:three|3)",
            r"all\s+(?:three|3)\s+(?:customer\s+)?plans",
            r"compare\s+(?:all\s+)?customer\s+plans"
        ]
        if any(re.search(pat, q_lower) for pat in all_customer_patterns):
            customer_plans = ["HS-BASIC-001", "HS-GOLD-001", "HS-PREMIUM-001"]
            effective = [p for p in customer_plans if p in authorized_set]
            return ScopeResolutionResult(
                selected_plan_id=selected_plan_id,
                authorized_plans=authorized_list,
                effective_scope=effective,
                reason="explicit_comparison",
                is_comparison=True,
                is_ambiguous=False
            )

        # 5. Detect explicitly mentioned plans in query
        comparison_triggers = ["compare", "versus", "vs", "difference between", "better than", "instead of", "as opposed to"]
        has_comparison_trigger = any(t in q_lower for t in comparison_triggers)

        # Check for unauthorized employee plan request by a customer
        denied_plans = []
        for pid in list(detected_plans):
            if pid not in authorized_set:
                detected_plans.remove(pid)
                denied_plans.append(pid)
                logger.warning(f"Role '{role}' attempted to request unauthorized plan '{pid}' in query.")

        # If a comparison trigger exists and at least one other plan is mentioned:
        if has_comparison_trigger and detected_plans:
            combined_scope = set(detected_plans)
            if len(combined_scope) == 1 and selected_plan_id in authorized_set:
                combined_scope.add(selected_plan_id)

            effective = [p for p in authorized_list if p in combined_scope]
            if len(effective) > 1:
                reason = "explicit_comparison"
                if denied_plans:
                    reason = "access_restricted"
                return ScopeResolutionResult(
                    selected_plan_id=selected_plan_id,
                    authorized_plans=authorized_list,
                    effective_scope=effective,
                    reason=reason,
                    is_comparison=True,
                    is_ambiguous=False,
                    denied_plans=denied_plans,
                    greeting_prefix=greeting_prefix,
                    mixed_insurance_query=cleaned_subquery if greeting_prefix else None,
                    resolved_query=cleaned_subquery
                )

        # If user explicitly asked ONLY for a different plan without a comparison trigger
        if detected_plans and len(detected_plans) == 1 and not has_comparison_trigger:
            only_plan = list(detected_plans)[0]
            if only_plan != selected_plan_id:
                return ScopeResolutionResult(
                    selected_plan_id=selected_plan_id,
                    authorized_plans=authorized_list,
                    effective_scope=[only_plan],
                    reason="explicit_named_plan",
                    is_comparison=False,
                    is_ambiguous=False,
                    denied_plans=denied_plans,
                    greeting_prefix=greeting_prefix,
                    mixed_insurance_query=cleaned_subquery if greeting_prefix else None,
                    resolved_query=cleaned_subquery
                )

        # If customer asked solely for an employee plan
        if denied_plans and not detected_plans:
            return ScopeResolutionResult(
                selected_plan_id=selected_plan_id,
                authorized_plans=authorized_list,
                effective_scope=[selected_plan_id],
                reason="access_restricted",
                is_comparison=False,
                is_ambiguous=False,
                denied_plans=denied_plans,
                greeting_prefix=greeting_prefix,
                mixed_insurance_query=cleaned_subquery if greeting_prefix else None,
                resolved_query=cleaned_subquery
            )

        # 6. Optimized 6-Message Context-Aware Follow-up & Default Selected Plan Scope
        p_info = get_plan_by_id(selected_plan_id)
        p_name = p_info.plan_name if p_info else selected_plan_id
        reason = "default_selected_plan"
        resolved_q = cleaned_subquery
        search_q = cleaned_subquery
        is_related = ContextWindowManager.is_query_related(cleaned_subquery, context_win)

        immediate_turn = context_win.selected_turns[-1] if context_win.selected_turns else None
        immediate_benefits = immediate_turn.mentioned_benefits if immediate_turn else []
        all_benefits = context_win.discussed_benefits
        last_uq = context_win.last_user_query or ""
        last_ans = (context_win.last_assistant_answer or "").lower()

        # Word to integer mapping for duration queries
        word_to_num = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30
        }

        # 6.1 Duration / Calculation Follow-Up (e.g. "What about 5 days?", "Calculate for 10 days")
        duration_m = re.search(
            r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve|fifteen|twenty|thirty)\s+days?\b",
            q_lower
        )
        if is_related and duration_m and any(term in q_lower for term in ["what about", "how much", "for", "calculate", "cost", "payout"]):
            val_str = duration_m.group(1).lower()
            num_days = int(val_str) if val_str.isdigit() else word_to_num.get(val_str, 5)
            target_b = "Hospital Cash"
            if "icu" in q_lower or (immediate_benefits and "icu benefit" in immediate_benefits):
                target_b = "ICU Benefit"
            elif immediate_benefits and "hospital cash" in immediate_benefits:
                target_b = "Hospital Cash"
            elif all_benefits:
                target_b = all_benefits[0].title()

            reason = "follow_up"
            resolved_q = f"Calculate the {target_b} payout under {p_name} for {num_days} days of hospitalization."
            search_q = f"{p_name} {target_b} daily benefit allowance rate maximum payable days cap per policy year inpatient"

        # 6.2 Plain-Language Explanation & Table Breakdown Follow-Up
        # (e.g. "Explain the above table in simple words", "Simplify this table", "What does this mean?")
        elif is_related and (
            re.search(r"\b(?:the\s+above\s+table|above\s+table|this\s+table|the\s+table|the\s+above\s+data|above\s+data|the\s+above)\b", q_lower) or
            re.search(r"\b(?:explain|simplify|break\s+down|clarify|what\s+does\s+(?:this|it|the\s+above)\s+mean|in\s+simple\s+(?:words|terms)|simply)\b", q_lower)
        ):
            reason = "follow_up"
            if any("surg" in b for b in immediate_benefits + all_benefits) or "surgery" in last_ans or "major surgery" in last_uq.lower() or "category 1" in last_ans:
                resolved_q = f"Explain the Major Surgery Benefit categories, payout rules, and conditions for {p_name} in simple words."
                search_q = f"{p_name} Section 5 Major Surgery Benefit basis category 1 2 3 4 payout percentage limits conditions inpatient"
            elif any("cash" in b or "icu" in b for b in immediate_benefits + all_benefits) or "hospital cash" in last_ans or "icu" in last_ans:
                resolved_q = f"Explain the Hospital Cash and ICU daily allowances, duration limits, and conditions for {p_name} in simple words."
                search_q = f"{p_name} Sections 3 4 Hospital Cash ICU daily benefit limits inpatient 24 hours"
            elif any("wait" in b for b in immediate_benefits + all_benefits) or "waiting" in last_ans:
                resolved_q = f"Explain the waiting periods and exclusions for {p_name} in simple words."
                search_q = f"{p_name} Section 15 waiting periods initial 30 days specific conditions 24 months pre-existing 36 months"
            elif any("day-care" in b for b in immediate_benefits + all_benefits) or "day-care" in last_ans:
                resolved_q = f"Explain the Day-Care procedure benefit for {p_name} in simple words."
                search_q = f"{p_name} Section 6 Day-Care procedure benefit payout limits 24 hours"
            elif last_uq:
                resolved_q = f"Explain the policy details discussed previously ({last_uq}) for {p_name} in simple words."
                search_q = f"{p_name} {last_uq}"

        # 6.3 Coreference Pronouns ("its", "it", "that", "this")
        elif is_related and any(re.search(rf"\b{t}\b", q_lower) for t in ["its", "it", "that", "this", "these", "those"]):
            reason = "follow_up"
            if "waiting period" in q_lower or "waiting" in q_lower:
                resolved_q = f"What are the waiting periods under {p_name}?"
                search_q = f"{p_name} waiting period initial 30 days specific diseases pre-existing illnesses exclusions"
            elif last_uq:
                resolved_q = f"{last_uq} — {cleaned_subquery}"
                search_q = resolved_q

        # 6.4 Generic Limit / Sub-limit Follow-ups (e.g. "What is the maximum limit?", "Is there a cap?")
        elif is_related and re.search(r"^\s*(?:what\s+is\s+(?:the\s+|its\s+)?(?:maximum|max|cap|limit)|is\s+there\s+a\s+(?:cap|limit|maximum)|what\s+are\s+the\s+limits)[\s?.!]*$", q_lower):
            target_b = all_benefits[0].title() if all_benefits else "Major Surgery Benefit"
            reason = "follow_up"
            resolved_q = f"What is the maximum limit and financial cap for {target_b} under {p_name}?"
            search_q = f"{p_name} {target_b} maximum limit financial cap category tiers basis amount"

        elif is_related and last_uq:
            reason = "follow_up"
            resolved_q = f"{last_uq} — {cleaned_subquery}"
            search_q = resolved_q

        return ScopeResolutionResult(
            selected_plan_id=selected_plan_id,
            authorized_plans=authorized_list,
            effective_scope=[selected_plan_id],
            reason=reason,
            is_comparison=False,
            is_ambiguous=False,
            resolved_query=resolved_q,
            search_query=search_q,
            greeting_prefix=greeting_prefix,
            mixed_insurance_query=cleaned_subquery if greeting_prefix else None,
            denied_plans=denied_plans,
            context_window=context_win,
            is_context_related=(reason == "follow_up")
        )
