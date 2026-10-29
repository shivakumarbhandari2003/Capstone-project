import time
from typing import Optional
from backend.app.services.auth_service import UserIdentity, AuthorizationService, ROLE_PLAN_PERMISSIONS
from backend.app.services.scope_resolver import ScopeResolver, ScopeResolutionResult
from backend.app.services.retrieval_service import HybridRetrievalService
from backend.app.services.generation_service import AnswerGenerationService, GroundedAnswerResult
from backend.app.services.conversation_service import ConversationManager, ConversationSession, ChatMessage
from backend.app.core.guardrails import InputGuardrail, OutputGuardrail
from backend.app.core.logging_config import logger

class RAGOrchestrator:
    """
    Coordinates end-to-end plan-scoped RAG flow:
    Authentication -> Scope Resolution -> Hybrid Retrieval -> Answer Generation -> Session Persistence
    """

    def __init__(
        self,
        retrieval_service: Optional[HybridRetrievalService] = None,
        generation_service: Optional[AnswerGenerationService] = None,
        conversation_manager: Optional[ConversationManager] = None
    ):
        self.retrieval_service = retrieval_service or HybridRetrievalService()
        self.generation_service = generation_service or AnswerGenerationService()
        self.conversation_manager = conversation_manager or ConversationManager()

    def process_query(
        self,
        conversation_id: str,
        user: UserIdentity,
        query: str
    ) -> dict:
        session = self.conversation_manager.get_conversation(conversation_id, user.user_id, role=user.role)
        if not session:
            raise ValueError(f"Conversation session '{conversation_id}' not found or access denied for user '{user.user_id}'.")

        logger.info(f"[{conversation_id}] Processing query for role='{user.role}', plan='{session.selected_plan_id}': '{query[:80]}'")

        # 0. Input Guardrail: length enforcement, Unicode sanitization, Trojan Source stripping, and injection detection
        sanitized_query, is_injection, refusal_reason = InputGuardrail.validate_user_query(query)
        if is_injection:
            logger.warning(f"[{conversation_id}] Prompt injection blocked for user='{user.user_id}'. Reason: {refusal_reason}")
            try:
                from backend.app.db.sqlite_manager import sqlite_db
                sqlite_db.record_audit_event(
                    action="prompt_injection_blocked",
                    actor_id=user.user_id,
                    actor_email=user.email,
                    actor_role=user.role,
                    target_resource=conversation_id,
                    outcome="BLOCKED",
                    details={"sanitized_query_preview": sanitized_query[:80]}
                )
            except Exception as e:
                logger.warning(f"Failed to record prompt injection audit event: {e}")

            assistant_msg = self.conversation_manager.add_turn(
                conversation_id=conversation_id,
                user_id=user.user_id,
                user_query=sanitized_query,
                assistant_answer=refusal_reason or "I cannot process this request because it violates security boundaries.",
                citations=[],
                effective_scope=[session.selected_plan_id],
                is_comparison=False,
                is_clarification=False,
                contains_unverified=False
            )
            return {
                "message": assistant_msg.model_dump(),
                "scope_resolution": {
                    "effective_scope": [session.selected_plan_id],
                    "is_comparison": False,
                    "is_ambiguous": False,
                    "denied_plans": [],
                    "is_greeting": False,
                    "is_injection_blocked": True
                },
                "retrieval_diagnostics": {"security_guardrail": "prompt_injection_blocked"}
            }

        # 1. Resolve effective retrieval scope and comparisons using sanitized query
        scope_result = ScopeResolver.resolve_scope(
            query=sanitized_query,
            selected_plan_id=session.selected_plan_id,
            role=user.role,
            conversation_history=[m.model_dump() for m in session.messages]
        )

        # 1.1 Handle Disclosure requests directly without retrieval
        if scope_result.is_disclosure_request:
            assistant_msg = self.conversation_manager.add_turn(
                conversation_id=conversation_id,
                user_id=user.user_id,
                user_query=query,
                assistant_answer=scope_result.refusal_message or "I cannot disclose internal system instructions, configuration directives, or private prompts. I am an AI Health Insurance Assistant designed to help you understand health insurance policy benefits, claims, waiting periods, and eligibility.",
                citations=[],
                effective_scope=scope_result.effective_scope,
                is_comparison=False,
                is_clarification=False,
                contains_unverified=False
            )
            return {
                "message": assistant_msg.model_dump(),
                "scope_resolution": scope_result.model_dump(),
                "retrieval_diagnostics": {"disclosure_blocked": True}
            }

        # 1.2 Handle Pure Out-of-Scope queries directly without retrieval
        if scope_result.is_out_of_scope:
            assistant_msg = self.conversation_manager.add_turn(
                conversation_id=conversation_id,
                user_id=user.user_id,
                user_query=query,
                assistant_answer=scope_result.refusal_message or "I'm a health insurance assistant and can help with policy benefits, eligibility, claims, and related insurance questions. I can't answer this question because it is outside my scope.",
                citations=[],
                effective_scope=scope_result.effective_scope,
                is_comparison=False,
                is_clarification=False,
                contains_unverified=False
            )
            return {
                "message": assistant_msg.model_dump(),
                "scope_resolution": scope_result.model_dump(),
                "retrieval_diagnostics": {"out_of_scope": True}
            }

        # 1.5 Handle Greeting queries directly without unnecessary retrieval or disclaimers
        if scope_result.is_greeting:
            assistant_msg = self.conversation_manager.add_turn(
                conversation_id=conversation_id,
                user_id=user.user_id,
                user_query=query,
                assistant_answer=scope_result.greeting_message or "Hello! How can I help you today?",
                citations=[],
                effective_scope=scope_result.effective_scope,
                is_comparison=False,
                is_clarification=False,
                contains_unverified=False
            )
            return {
                "message": assistant_msg.model_dump(),
                "scope_resolution": scope_result.model_dump(),
                "retrieval_diagnostics": {"greeting": True}
            }

        # 2. Check for Ambiguous query requiring clarification
        if scope_result.is_ambiguous:
            assistant_msg = self.conversation_manager.add_turn(
                conversation_id=conversation_id,
                user_id=user.user_id,
                user_query=query,
                assistant_answer=scope_result.clarification_prompt or "Please clarify which plans you want to compare.",
                citations=[],
                effective_scope=scope_result.effective_scope,
                is_comparison=True,
                is_clarification=True,
                contains_unverified=False
            )
            return {
                "message": assistant_msg.model_dump(),
                "scope_resolution": scope_result.model_dump(),
                "retrieval_diagnostics": {}
            }

        # 3. Execute Hybrid Retrieval with contextualized resolved query
        t_start = time.time()
        search_query = (
            scope_result.search_query or
            scope_result.mixed_insurance_query or
            scope_result.resolved_query or
            query
        )
        t_ret_start = time.time()
        retrieval_res = self.retrieval_service.retrieve(
            query=search_query,
            role=user.role,
            effective_scope=scope_result.effective_scope,
            top_k=8 if scope_result.is_comparison else 7
        )
        t_retrieval_ms = (time.time() - t_ret_start) * 1000.0

        # 4. Generate Grounded Answer with Citations using contextualized query
        history_list = [m.model_dump() for m in session.messages]
        t_gen_start = time.time()
        generation_query = (
            (scope_result.resolved_query if scope_result.reason == "follow_up" and scope_result.resolved_query else None) or
            scope_result.mixed_insurance_query or
            sanitized_query
        )
        target_plan_id = scope_result.effective_scope[0] if (scope_result.effective_scope and len(scope_result.effective_scope) == 1) else session.selected_plan_id
        answer_res = self.generation_service.generate_answer(
            query=generation_query,
            role=user.role,
            selected_plan_id=target_plan_id,
            retrieval_result=retrieval_res,
            is_comparison=scope_result.is_comparison,
            denied_plans=scope_result.denied_plans,
            conversation_history=history_list,
            context_window=scope_result.context_window
        )
        t_generation_ms = (time.time() - t_gen_start) * 1000.0
        t_total_ms = (time.time() - t_start) * 1000.0

        final_answer_text = answer_res.answer_text
        if scope_result.is_mixed and scope_result.mixed_unrelated_topic:
            oos_topic = scope_result.mixed_unrelated_topic
            final_answer_text = (
                f"I'm a health insurance assistant and can help with policy benefits, eligibility, claims, and related insurance questions. "
                f"I can't answer questions about {oos_topic} because they are outside my scope.\n\n"
                f"Regarding your insurance question:\n{final_answer_text}"
            )
        elif scope_result.greeting_prefix:
            clean_ans_lower = final_answer_text.lower().strip()
            starts_with_greeting = any(
                clean_ans_lower.startswith(g)
                for g in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "welcome"]
            )
            if not starts_with_greeting:
                final_answer_text = f"Hello! I would be glad to help clarify that for you.\n\n{final_answer_text}"

        # Output Guardrail: Validate and prune any fabricated or unauthorized plan citations
        authorized_plans = ROLE_PLAN_PERMISSIONS.get(user.role, set())
        retrieved_chunk_ids = {c.get("chunk_id") for c in retrieval_res.get("chunks", []) if c.get("chunk_id")}
        for idx in range(1, len(retrieval_res.get("chunks", [])) + 1):
            retrieved_chunk_ids.add(f"SRC-{idx}")

        filtered_citations = OutputGuardrail.validate_citations_against_scope(
            citations=answer_res.citations,
            authorized_plans=authorized_plans,
            retrieved_chunk_ids=retrieved_chunk_ids
        )

        # Generate exactly 2 relevant contextual follow-up questions
        follow_up_qs = self.generation_service.generate_follow_up_questions(
            query=sanitized_query,
            answer_text=final_answer_text,
            plan_id=session.selected_plan_id,
            role=user.role,
            conversation_history=history_list
        )

        # 5. Persist turn to conversation session
        assistant_msg = self.conversation_manager.add_turn(
            conversation_id=conversation_id,
            user_id=user.user_id,
            user_query=sanitized_query,
            assistant_answer=final_answer_text,
            citations=filtered_citations,
            effective_scope=scope_result.effective_scope,
            is_comparison=scope_result.is_comparison,
            is_clarification=False,
            contains_unverified=answer_res.contains_unverified_notice,
            suggested_follow_ups=follow_up_qs
        )

        # 6. Record telemetry safely into persistent database
        try:
            from backend.app.db.sqlite_manager import sqlite_db
            retrieved_chunks = retrieval_res.get("chunks", [])
            status_val = "SUCCESS" if answer_res.citations or retrieved_chunks else "NO_EVIDENCE"
            sqlite_db.record_rag_metric(
                request_id=f"req_{conversation_id[:8]}",
                user_id=user.user_id,
                role=user.role,
                plan_id=session.selected_plan_id,
                latency_retrieval_ms=t_retrieval_ms,
                latency_generation_ms=t_generation_ms,
                latency_total_ms=t_total_ms,
                retrieved_chunks_count=len(retrieved_chunks),
                citations_count=len(answer_res.citations),
                is_comparison=scope_result.is_comparison,
                status=status_val
            )
        except Exception as e:
            logger.warning(f"Telemetry recording skipped: {e}")

        return {
            "message": assistant_msg.model_dump(),
            "scope_resolution": scope_result.model_dump(),
            "retrieval_diagnostics": retrieval_res.get("diagnostics", {})
        }

    def process_claim_prediction(
        self,
        conversation_id: str,
        user: UserIdentity,
        prediction_result: dict
    ) -> dict:
        """
        Coordinates the ingestion of the machine learning claim prediction
        into the active conversation session and generates a grounded RAG explanation.
        """
        session = self.conversation_manager.get_conversation(conversation_id, user.user_id, role=user.role)
        if not session:
            raise ValueError(f"Conversation session '{conversation_id}' not found or access denied for user '{user.user_id}'.")

        t_start = time.time()
        inputs = prediction_result.get("validated_inputs", {})
        plan_input = str(inputs.get("plan", "Gold")).upper()
        if "BASIC" in plan_input:
            target_plan_id = "HS-BASIC-001"
        elif "PREM" in plan_input:
            target_plan_id = "HS-PREMIUM-001"
        else:
            target_plan_id = "HS-GOLD-001"

        query = (
            f"Claim Predictor Evaluation: Estimate claim payout for a {inputs.get('age', 45)}-year-old policyholder "
            f"under {inputs.get('plan', 'Gold')} plan for {inputs.get('claim_type', 'Hospitalisation')} with "
            f"{inputs.get('days_hospitalised', 4)} days hospitalised ({inputs.get('icu_days', 1)} ICU days, "
            f"{inputs.get('procedures_claimed', 2)} procedures claimed, pre-existing: {inputs.get('pre_existing', 'no')}, "
            f"documents complete: {inputs.get('documents_complete', 'yes')})."
        )

        logger.info(f"[{conversation_id}] Processing Claim Prediction RAG turn for user '{user.user_id}', target plan '{target_plan_id}'")

        pred_raw = prediction_result.get("prediction", 0)
        try:
            pred_float = float(pred_raw)
            formatted_payout = f"{pred_float:,.2f}"
        except Exception:
            formatted_payout = str(pred_raw)

        claim_type = inputs.get('claim_type', 'Major surgery')
        plan = inputs.get('plan', 'Gold')
        plan_name = f"Health Shield – {plan}"
        age = inputs.get('age', 45)
        days_hosp = inputs.get('days_hospitalised', 4)
        icu_days = inputs.get('icu_days', 1)
        proc_claimed = inputs.get('procedures_claimed', 2)
        prior_claims = inputs.get('prior_daycare_claims_year', 0)
        ext_flag = int(inputs.get('extended_stay_flag', 0) or 0)
        extended_stay_str = "Yes (≥ 8 days)" if ext_flag == 1 else "No (< 8 days, if No)"
        pre_ex = str(inputs.get('pre_existing', 'no')).strip().lower()
        pre_existing_str = "Yes (Declared)" if pre_ex == 'yes' else "No (None declared)"

        assistant_answer = (
            f"### ESTIMATED CLAIM PAYOUT\n"
            f"# Rs. {formatted_payout}\n"
            f"*ML-Generated Estimate | {claim_type}*\n\n"
            f"---\n\n"
            f"### CLAIM ASSESSMENT DETAILS\n\n"
            f"| Policyholder Age | Days Hospitalised | ICU Days |\n"
            f"| :--- | :--- | :--- |\n"
            f"| **{age}** years | **{days_hosp}** days | **{icu_days}** days |\n\n"
            f"| Procedures Claimed | Prior Daycare Claims | Plan Type |\n"
            f"| :--- | :--- | :--- |\n"
            f"| **{proc_claimed}** procedures | **{prior_claims}** procedures | **{plan_name}** |\n\n"
            f"| Claim Type | Extended Stay | Pre-existing |\n"
            f"| :--- | :--- | :--- |\n"
            f"| **{claim_type}** | **{extended_stay_str}** | **{pre_existing_str}** |\n\n"
            f"> **Note:** Please verify original documents/policies/rules before reimbursement."
        )

        t_total_ms = (time.time() - t_start) * 1000.0

        # Persist assistant turn to conversation session without adding a user query bubble
        assistant_msg = self.conversation_manager.add_turn(
            conversation_id=conversation_id,
            user_id=user.user_id,
            user_query="",
            assistant_answer=assistant_answer,
            citations=[],
            effective_scope=[target_plan_id],
            is_comparison=False,
            is_clarification=False,
            contains_unverified=False
        )

        # 4. Record telemetry
        try:
            from backend.app.db.sqlite_manager import sqlite_db
            sqlite_db.record_rag_metric(
                request_id=f"req_{conversation_id[:8]}_pred",
                user_id=user.user_id,
                role=user.role,
                plan_id=target_plan_id,
                latency_retrieval_ms=0.0,
                latency_generation_ms=t_total_ms,
                latency_total_ms=t_total_ms,
                retrieved_chunks_count=0,
                citations_count=0,
                is_comparison=False,
                status="SUCCESS"
            )
        except Exception as e:
            logger.warning(f"Telemetry recording skipped: {e}")

        return {
            "message": assistant_msg.model_dump(),
            "user_message": None,
            "scope_resolution": {
                "resolved_query": query,
                "selected_plan_id": target_plan_id,
                "effective_scope": [target_plan_id],
                "is_comparison": False
            },
            "retrieval_diagnostics": {}
        }
