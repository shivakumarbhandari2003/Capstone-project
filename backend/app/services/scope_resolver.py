import re
from typing import Optional
from pydantic import BaseModel, Field
from backend.app.services.auth_service import AuthorizationService, EMPLOYEE_ONLY_PLANS
from backend.app.registry.plans import get_plan_by_id
from backend.app.core.logging_config import logger

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
    clarification_prompt: Optional[str] = None
    resolved_query: Optional[str] = None
    denied_plans: list[str] = Field(default_factory=list)

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

GREETING_PATTERN = re.compile(
    r"^(?:hello|hi|hey|greetings|howdy|good\s+(?:morning|afternoon|evening)|hi\s+there|hello\s+there)[!.,\s]*$",
    re.IGNORECASE
)

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
        q_lower = query.lower().strip()
        authorized_set = AuthorizationService.get_authorized_plans(role)
        authorized_list = sorted(list(authorized_set))

        # Ensure selected plan is authorized
        if selected_plan_id not in authorized_set:
            selected_plan_id = "HS-BASIC-001" if "HS-BASIC-001" in authorized_set else authorized_list[0]

        # 0. Check for Greeting query
        if GREETING_PATTERN.match(q_lower):
            p_info = get_plan_by_id(selected_plan_id)
            p_name = p_info.plan_name if p_info else selected_plan_id
            greeting_msg = f"Hello! I can help you understand the benefits, limits, waiting periods, and claim conditions described in {p_name}. What would you like to know?"
            return ScopeResolutionResult(
                selected_plan_id=selected_plan_id,
                authorized_plans=authorized_list,
                effective_scope=[selected_plan_id],
                reason="greeting",
                is_comparison=False,
                is_ambiguous=False,
                is_greeting=True,
                greeting_message=greeting_msg
            )

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
                    refusal_message="I cannot disclose internal system instructions, configuration directives, or private prompts. I am an AI Health Insurance Assistant designed to help you understand health insurance policy benefits, claims, waiting periods, and eligibility."
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

        # Check follow-up context if pronouns used
        follow_up_tokens = ["its", "it", "that", "those", "this", "these", "does it", "is there", "what about", "is it covered", "how much is covered"]
        has_followup_pronouns = any(re.search(rf"\b{re.escape(t)}\b", q_lower) for t in follow_up_tokens)
        if conversation_history and has_followup_pronouns:
            has_insurance_intent = True

        # Handle Mixed Query (Insurance Question + Unrelated Question)
        if matched_oos_topic and has_insurance_intent:
            logger.info(f"Mixed query detected. Insurance intent present alongside unrelated topic: {matched_oos_topic}")
            # Isolate insurance sub-query by stripping out-of-scope clause
            split_patterns = [r"\s+(?:and\s+also|and\s+who|and\s+what|also|as\s+well\s+as)\s+"]
            insurance_part = query
            for sp in split_patterns:
                parts = re.split(sp, query, flags=re.IGNORECASE)
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
                refusal_message=f"I'm a health insurance assistant and can help with policy benefits, eligibility, claims, and related insurance questions. I can't answer questions about {matched_oos_topic} because they are outside my scope."
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
                refusal_message="I'm a health insurance assistant and can help with policy benefits, eligibility, claims, and related insurance questions. I can't answer this question because it is outside my scope."
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
                    denied_plans=denied_plans
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
                    denied_plans=denied_plans
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
                denied_plans=denied_plans
            )

        # 6. Follow-up / Default Selected Plan Scope
        reason = "default_selected_plan"
        resolved_q = query
        if any(re.search(rf"\b{t}\b", q_lower) for t in follow_up_tokens):
            reason = "follow_up"
            if conversation_history:
                last_turn = conversation_history[-1]
                last_q = last_turn.get("user_query") or last_turn.get("query") or ""
                if last_q and any(p in q_lower.split() for p in ["its", "it", "that", "those", "this", "there", "what", "how"]):
                    resolved_q = f"{last_q} — {query}"

        return ScopeResolutionResult(
            selected_plan_id=selected_plan_id,
            authorized_plans=authorized_list,
            effective_scope=[selected_plan_id],
            reason=reason,
            is_comparison=False,
            is_ambiguous=False,
            resolved_query=resolved_q,
            denied_plans=denied_plans
        )
