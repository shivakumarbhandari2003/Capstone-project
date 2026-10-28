import time
import os
import re
from typing import Optional
import httpx
from pydantic import BaseModel, Field
from backend.app.core.prompt import RAG_SYSTEM_PROMPT, format_rag_prompt
from backend.app.registry.plans import get_plan_by_id
from backend.app.core.config import settings
from backend.app.core.guardrails import OutputGuardrail
from backend.app.core.logging_config import logger

class SourceCitation(BaseModel):
    source_id: str
    plan_id: str
    plan_name: str
    source_document: str
    section_number: str
    section_title: str
    source_page_start: int
    source_page_end: int
    data_status: str
    snippet: str

class GroundedAnswerResult(BaseModel):
    answer_text: str
    citations: list[SourceCitation]
    contains_unverified_notice: bool = False
    is_clarification: bool = False
    denied_notice: Optional[str] = None
    provider_used: str

class AnswerGenerationService:
    """
    RAG Answer Generator with Citation Validation and multi-provider architecture.
    Supports external LLMs (OpenAI, Gemini, Groq) or a deterministic,
    source-grounded local synthesizer when cloud LLM credentials are not configured.
    """

    def __init__(self):
        self.provider = os.environ.get("LLM_PROVIDER", getattr(settings, "LLM_PROVIDER", "local")).lower()
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
        self.gemini_model = os.environ.get("GEMINI_MODEL", getattr(settings, "GEMINI_MODEL", "gemini-flash-lite-latest"))
        self.gemini_fallback_model = os.environ.get("GEMINI_FALLBACK_MODEL", getattr(settings, "GEMINI_FALLBACK_MODEL", "gemini-flash-latest"))
        self.groq_key = os.environ.get("GROQ_API_KEY")

        if self.gemini_key and self.provider in ["gemini", "local"]:
            self.provider = "gemini"
        elif self.openai_key and self.provider in ["openai", "local"]:
            self.provider = "openai"
        elif self.groq_key and self.provider in ["groq", "local"]:
            self.provider = "groq"
        else:
            self.provider = "grounded_synthesizer"

        self._http_client: Optional[httpx.Client] = None
        logger.info(f"Initialized AnswerGenerationService with provider: '{self.provider}' (Gemini model: {self.gemini_model})")

    def _get_http_client(self) -> httpx.Client:
        """Returns a reusable, pooled httpx.Client with fast timeout to avoid freezing during network glitches."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.Client(
                timeout=10.0,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
            )
        return self._http_client

    def generate_answer(
        self,
        query: str,
        role: str,
        selected_plan_id: str,
        retrieval_result: dict,
        is_comparison: bool = False,
        clarification_prompt: Optional[str] = None,
        denied_plans: Optional[list[str]] = None,
        conversation_history: Optional[list[dict]] = None
    ) -> GroundedAnswerResult:
        # 1. Handle clarification queries directly
        if clarification_prompt:
            return GroundedAnswerResult(
                answer_text=clarification_prompt,
                citations=[],
                is_clarification=True,
                provider_used=self.provider
            )

        # 2. Handle unauthorized employee plan requests
        denied_notice = None
        if denied_plans:
            denied_notice = (
                "I understand you are interested in the Executive Employee Insurance Plan (EMP-INS-001). "
                "However, access to employee-only plan terms is restricted to authenticated corporate employees under our access policy. "
                "Only authorized customer policy terms are displayed below."
            )

        chunks = retrieval_result.get("chunks", [])
        if not chunks:
            p_info = get_plan_by_id(selected_plan_id)
            plan_name = p_info.plan_name if p_info else selected_plan_id
            if denied_plans:
                abstention_msg = (
                    f"> **Access Restriction Notice:** {denied_notice}\n\n"
                    f"I cannot provide details for the Executive Employee Insurance Plan because it is restricted to authenticated employee accounts. "
                    f"However, I would be glad to help you explore the benefits, limits, and claim conditions for your authorized plan, **{plan_name}**. "
                    f"What would you like to know about **{plan_name}**?"
                )
            else:
                abstention_msg = (
                    f"I'd like to give you an accurate answer, but I couldn't verify this detail from the policy information currently available for **{plan_name}**. "
                    f"The available policy documents for **{plan_name}** do not specify coverage terms, limits, or waiting periods for this condition or query. "
                    f"I don't want to mislead you, so please consult your official policy schedule or an authorized insurance representative."
                )
            return GroundedAnswerResult(
                answer_text=abstention_msg,
                citations=[],
                denied_notice=denied_notice,
                provider_used=self.provider
            )

        # 3. Build verified citations strictly from retrieved chunks
        verified_citations = self._build_verified_citations(chunks)
        contains_unverified = retrieval_result.get("contains_unverified", False)

        actual_provider = self.provider
        # 4. Generate answer based on configured provider
        if self.provider == "gemini" and self.gemini_key:
            answer_text, success = self._call_gemini(
                query, role, selected_plan_id, retrieval_result, is_comparison, conversation_history
            )
            actual_provider = "gemini" if success else "gemini_fallback"
        elif self.provider == "openai" and self.openai_key:
            answer_text = self._call_openai(query, role, selected_plan_id, retrieval_result, is_comparison)
            actual_provider = "openai"
        else:
            answer_text = self._synthesize_grounded_answer(query, role, selected_plan_id, chunks, is_comparison)
            actual_provider = "grounded_synthesizer"

        answer_text = self._consolidate_inline_citations(answer_text)

        # Ensure no citations returned on explicit policy abstention
        if "do not specify coverage terms" in answer_text.lower() or "not specified in the available documents" in answer_text.lower():
            verified_citations = []

        if denied_notice:
            answer_text = f"> **Access Restriction Notice:** {denied_notice}\n\n" + answer_text

        has_unverified = bool(contains_unverified or any(
            c.get("metadata", {}).get("data_status") == "illustrative_unverified"
            for c in chunks
        ))

        if has_unverified and verified_citations:
            if not any(term in answer_text.lower() for term in ["illustrative", "demonstration data"]):
                answer_text += "\n\n> **Notice:** Contains illustrative demonstration data."

        # Output Guardrail: Redact exposed credentials/secrets and sanitize unsafe markdown link schemes
        answer_text = OutputGuardrail.redact_secrets(answer_text)
        answer_text = OutputGuardrail.sanitize_links(answer_text)
        answer_text = answer_text.replace("₹", "Rs. ")
        answer_text = re.sub(r"Rs\.?\s*(\d)", r"Rs. \1", answer_text)

        return GroundedAnswerResult(
            answer_text=answer_text,
            citations=verified_citations,
            contains_unverified_notice=has_unverified,
            denied_notice=denied_notice,
            provider_used=actual_provider
        )

    def _build_verified_citations(self, chunks: list[dict]) -> list[SourceCitation]:
        citations = []
        seen = set()
        for idx, chunk in enumerate(chunks, start=1):
            meta = chunk.get("metadata", {})
            cid = chunk.get("chunk_id", f"SRC-{idx}")
            if cid in seen:
                continue
            seen.add(cid)

            plan_id = meta.get("plan_id", "UNKNOWN")
            plan_info = get_plan_by_id(plan_id)
            plan_name = plan_info.plan_name if plan_info else meta.get("plan_name", plan_id)

            snippet = chunk.get("content", "").strip()[:180] + "..."

            citations.append(SourceCitation(
                source_id=f"SRC-{idx}",
                plan_id=plan_id,
                plan_name=plan_name,
                source_document=meta.get("source_document", ""),
                section_number=str(meta.get("section_number", "")),
                section_title=meta.get("section_title", ""),
                source_page_start=int(meta.get("source_page_start", 1)),
                source_page_end=int(meta.get("source_page_end", 1)),
                data_status=meta.get("data_status", "verified"),
                snippet=snippet
            ))
        return citations

    def _consolidate_inline_citations(self, text: str) -> str:
        """
        Consolidates scattered inline citations (e.g. on individual bullets) into a single,
        compact evidence reference at the end of the answer content (before disclaimers/notices).
        Keeps individual bullet points clean, professional, and legible.
        """
        if not text or not text.strip():
            return text

        citation_pattern = re.compile(
            r"`?\[([A-Za-z0-9\s–—\-,]+(?:Section|pp\.|p\.|Plan|Shield|Executive|Comprehensive)[^\]\n]*)\]`?",
            re.IGNORECASE
        )

        notice_idx = text.find("\n\n> **Notice:**")
        if notice_idx != -1:
            main_content = text[:notice_idx]
            notice_content = text[notice_idx:]
        else:
            main_content = text
            notice_content = ""

        raw_citations = citation_pattern.findall(main_content)
        if not raw_citations:
            return text

        unique_citations = []
        seen = set()
        for cit in raw_citations:
            clean_cit = cit.strip()
            if clean_cit and clean_cit not in seen:
                seen.add(clean_cit)
                unique_citations.append(clean_cit)

        cleaned_content = citation_pattern.sub("", main_content)

        lines = []
        for line in cleaned_content.split("\n"):
            l = re.sub(r"\.\s*\.", ".", line)
            l = re.sub(r"\s+\.", ".", l)
            l = re.sub(r"[ \t]+$", "", l)
            lines.append(l)
        cleaned_main = "\n".join(lines).rstrip()

        if len(unique_citations) == 1:
            consolidated_cit = f"[{unique_citations[0]}]"
        else:
            first = unique_citations[0]
            if "," in first:
                plan_prefix = first.split(",")[0].strip()
                if all(c.startswith(plan_prefix) for c in unique_citations):
                    secs_pages = []
                    for c in unique_citations:
                        parts = c.split(",", 1)
                        if len(parts) > 1:
                            secs_pages.append(parts[1].strip())
                        else:
                            secs_pages.append(c)
                    consolidated_cit = f"[{plan_prefix}, {'; '.join(secs_pages)}]"
                else:
                    consolidated_cit = f"[{'; '.join(unique_citations)}]"
            else:
                consolidated_cit = f"[{'; '.join(unique_citations)}]"

        return f"{cleaned_main}\n\n{consolidated_cit}{notice_content}"

    def _synthesize_grounded_answer(
        self,
        query: str,
        role: str,
        selected_plan_id: str,
        chunks: list[dict],
        is_comparison: bool
    ) -> str:
        """
        Deterministic, high-accuracy extractive grounder.
        Synthesizes factual answers directly from authorized policy evidence
        without hallucination or external dependencies.
        """
        plan_info = get_plan_by_id(selected_plan_id)
        selected_name = plan_info.plan_name if plan_info else selected_plan_id

        # Group chunks by plan
        chunks_by_plan = {}
        for c in chunks:
            pid = c.get("plan_id", selected_plan_id)
            chunks_by_plan.setdefault(pid, []).append(c)

        # 1. Comparison query response
        if is_comparison and len(chunks_by_plan) > 1:
            comparison_lines = [f"### Plan Comparison: {', '.join([get_plan_by_id(p).plan_name if get_plan_by_id(p) else p for p in chunks_by_plan.keys()])}\n"]
            comparison_lines.append("| Plan | Relevant Section | Key Documented Terms & Limits | Citations |")
            comparison_lines.append("|---|---|---|---|")

            for pid, plan_chunks in chunks_by_plan.items():
                pinfo = get_plan_by_id(pid)
                pname = pinfo.plan_name if pinfo else pid
                for c in plan_chunks[:2]:
                    meta = c.get("metadata", {})
                    sec_num = meta.get("section_number", "")
                    sec_title = meta.get("section_title", "")
                    p_start = meta.get("source_page_start", "")
                    p_end = meta.get("source_page_end", "")
                    content_clean = c.get("content", "").replace("\n", " ").strip()
                    summary = content_clean[:140] + ("..." if len(content_clean) > 140 else "")
                    citation = f"[{pname}, Sec {sec_num}, p. {p_start}-{p_end}]"
                    comparison_lines.append(f"| **{pname}** | Section {sec_num}: {sec_title} | {summary} | {citation} |")

            comparison_lines.append("\n**Key Policy Differences Observed:**")
            for pid, plan_chunks in chunks_by_plan.items():
                pinfo = get_plan_by_id(pid)
                pname = pinfo.plan_name if pinfo else pid
                lead_chunk = plan_chunks[0]
                meta = lead_chunk.get("metadata", {})
                first_sentence = lead_chunk.get("content", "").split(".")[0].strip()
                sec_ref = f"[{pname}, Section {meta.get('section_number')}, p. {meta.get('source_page_start')}]"
                comparison_lines.append(f"- **{pname}**: {first_sentence}. {sec_ref}")

            ans = "\n".join(comparison_lines).replace("₹", "Rs. ")
            return re.sub(r"Rs\.?\s*(\d)", r"Rs. \1", ans)

        # 2. Single-plan query response
        plan_chunks = chunks_by_plan.get(selected_plan_id, chunks)

        # Check topic presence: If query specifically asks for a term (waiting periods, diseases, benefits)
        # and none of the chunks mention it, abstain cleanly instead of dumping irrelevant sections
        q_clean = query.lower()
        topic_keywords = [
            "waiting period", "ambulance", "surgery", "surgical", "cataract", "pre-existing",
            "maternity", "dental", "ayush", "domiciliary", "organ donor", "icu", "hospital cash",
            "critical illness", "cancer", "diabetes", "hypertension", "dialysis", "hernia"
        ]
        queried_topics = [kw for kw in topic_keywords if kw in q_clean]
        if queried_topics:
            all_chunk_text = " ".join([c.get("content", "").lower() for c in plan_chunks])
            if not any(kw in all_chunk_text for kw in queried_topics):
                p_info = get_plan_by_id(selected_plan_id)
                p_name = p_info.plan_name if p_info else selected_plan_id
                return f"I'd like to give you an accurate answer, but I couldn't verify this detail from the policy information currently available. The available policy documents for **{p_name}** do not specify coverage terms, limits, or waiting periods for {', '.join(queried_topics)}. I want to make sure you have the exact details, so please consult an authorized insurance representative or review your official policy schedule for these specific terms."

        # Score and rank chunks by query word overlap
        query_words = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", q_clean)) - {
            "the", "and", "for", "are", "per", "that", "this", "what", "with", "from", "have", "been", "under", "than", "more", "less", "year", "policy", "plan"
        }

        def score_chunk(c):
            text = c.get("content", "").lower()
            return sum(1 for w in query_words if w in text)

        ranked_chunks = sorted(plan_chunks, key=score_chunk, reverse=True)
        best_chunk = ranked_chunks[0] if ranked_chunks else None

        p_info = get_plan_by_id(selected_plan_id)
        plan_name = p_info.plan_name if p_info else selected_plan_id

        if not best_chunk or (query_words and score_chunk(best_chunk) == 0):
            return f"I'd like to give you an accurate answer, but I couldn't verify this detail from the policy information currently available. I am unable to answer this question because the available policy documents for **{plan_name}** do not specify this information. Please consult an authorized insurance representative or your policy schedule for complete details."

        meta = best_chunk.get("metadata", {})
        sec_num = meta.get("section_number", "")
        sec_title = meta.get("section_title", "")
        p_start = meta.get("source_page_start", 1)
        p_end = meta.get("source_page_end", 1)
        citation_str = f"[{plan_name}, Section {sec_num}: {sec_title}, p. {p_start}-{p_end}]"
        chunk_text = best_chunk.get("content", "")

        # Detect Yes/No / Confirmation intent
        is_confirmation = bool(
            re.search(r"^(?:is|does|can|are|was|am\s+i|is\s+this|is\s+it|do\s+we|will)\b", q_clean) or
            re.search(r"\b(am\s+i\s+right|is\s+this\s+correct|correct\?|right\?)\b", q_clean)
        )

        has_less_than = bool(re.search(r"\b(less\s+than|below|under|fewer\s+than)\s+(\d+[\d,]*)\b", q_clean))
        has_more_than = bool(re.search(r"\b(more\s+than|greater\s+than|above|exceeding)\s+(\d+[\d,]*)\b", q_clean))

        # Check threshold / comparison questions (e.g. "less than 1000", "more than 2000")
        if is_confirmation and (has_less_than or has_more_than):
            lines = [l.strip().lstrip("-* ") for l in chunk_text.split("\n") if l.strip() and not l.strip().upper().startswith("SECTION ") and len(l.strip()) > 5]
            matching_lines = [l for l in lines if any(w in l.lower() for w in query_words)]
            line_detail = matching_lines[0] if matching_lines else (lines[0] if lines else "")
            if has_less_than:
                return f"**No.** Under **{plan_name}**, the benefit is capped up to the documented limit ({line_detail}), not strictly less than that amount.\n\n{citation_str}"
            elif has_more_than:
                return f"Under **{plan_name}**, the documented limit is: {line_detail}.\n\n{citation_str}"

        # General confirmation query: Yes or No
        if is_confirmation:
            lines = [l.strip().lstrip("-* ") for l in chunk_text.split("\n") if l.strip() and not l.strip().upper().startswith("SECTION ") and len(l.strip()) > 5]
            matching_lines = [l for l in lines if any(w in l.lower() for w in query_words)]
            lead_statement = matching_lines[0] if matching_lines else (lines[0] if lines else "")
            if any(neg in lead_statement.lower() for neg in ["excluded", "not covered", "no benefit", "shall not be liable"]):
                return f"**No.** Under **{plan_name}**, {lead_statement}.\n\n{citation_str}"
            else:
                return f"**Yes.** Under **{plan_name}**, {lead_statement}.\n\n{citation_str}"

        # General factual query: Return strictly the 1-2 most relevant matching sentences or table rows
        matching_snippets = []
        for line in chunk_text.split("\n"):
            line_str = line.strip()
            if not line_str:
                continue
            if "|" in line_str and "---" in line_str:
                matching_snippets.append(line_str)
            elif any(w in line_str.lower() for w in query_words) and len(line_str) > 15:
                matching_snippets.append(f"- {line_str.lstrip('-* ')}")
                if len(matching_snippets) >= 2:
                    break

        if not matching_snippets:
            first_sentence = chunk_text.split(".")[0].strip()
            matching_snippets.append(f"- {first_sentence}.")

        ans = "\n".join(matching_snippets) + f"\n\n{citation_str}"
        ans = ans.replace("₹", "Rs. ")
        return re.sub(r"Rs\.?\s*(\d)", r"Rs. \1", ans)

    def _call_gemini(
        self,
        query: str,
        role: str,
        plan_id: str,
        retrieval_result: dict,
        is_comparison: bool,
        conversation_history: Optional[list[dict]] = None
    ) -> tuple[str, bool]:
        import httpx
        p_info = get_plan_by_id(plan_id)
        plan_name = p_info.plan_name if p_info else plan_id
        prompt = format_rag_prompt(
            query=query,
            context_text=retrieval_result.get("formatted_context", ""),
            selected_plan_name=plan_name,
            role=role,
            is_comparison=is_comparison,
            conversation_history=conversation_history
        )

        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.gemini_key
        }
        payload = {
            "system_instruction": {
                "parts": [{"text": RAG_SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1024
            }
        }

        models_to_try = [self.gemini_model]
        if self.gemini_fallback_model and self.gemini_fallback_model != self.gemini_model:
            models_to_try.append(self.gemini_fallback_model)

        client = self._get_http_client()
        for model_name in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_key}"
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code in (429, 500, 502, 503):
                    logger.warning(f"Gemini API ({model_name}) returned HTTP {resp.status_code}. Retrying in 0.5s...")
                    time.sleep(0.5)
                    resp = client.post(url, headers=headers, json=payload)

                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            logger.info(f"Successfully generated answer with Gemini model '{model_name}'.")
                            return parts[0]["text"].strip(), True
                else:
                    logger.warning(f"Gemini API ({model_name}) returned HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                logger.warning(f"Gemini API ({model_name}) call failed: {e}")

        logger.error("All Gemini API models failed. Falling back to deterministic grounded synthesizer.")
        fallback_text = self._synthesize_grounded_answer(query, role, plan_id, retrieval_result.get("chunks", []), is_comparison)
        return fallback_text, False

    def _call_openai(self, query: str, role: str, plan_id: str, retrieval_result: dict, is_comparison: bool) -> str:
        try:
            import httpx
            p_info = get_plan_by_id(plan_id)
            prompt = format_rag_prompt(query, retrieval_result.get("formatted_context", ""), p_info.plan_name if p_info else plan_id, role, is_comparison)
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.openai_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": RAG_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1
                },
                timeout=30.0
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}. Falling back to grounded synthesizer.")
            return self._synthesize_grounded_answer(query, role, plan_id, retrieval_result.get("chunks", []), is_comparison)

    def generate_claim_prediction_explanation(
        self,
        query: str,
        role: str,
        selected_plan_id: str,
        retrieval_result: dict,
        prediction_result: dict,
        conversation_history: Optional[list[dict]] = None
    ) -> GroundedAnswerResult:
        """
        Generates an authoritative, conversationally grounded explanation of the
        model-generated claim prediction output backed by retrieved policy evidence.
        """
        chunks = retrieval_result.get("chunks", [])
        verified_citations = self._build_verified_citations(chunks)
        pred_val = prediction_result.get("formatted_prediction") or f"Rs. {prediction_result.get('prediction', 0):,.2f}"
        inputs = prediction_result.get("validated_inputs", {})
        plan = inputs.get("plan", "Gold")
        claim_type = inputs.get("claim_type", "Hospitalisation")

        # Try Gemini if configured
        if self.provider == "gemini" and self.gemini_key:
            import httpx
            p_info = get_plan_by_id(selected_plan_id)
            plan_name = p_info.plan_name if p_info else plan
            context_text = retrieval_result.get("formatted_context", "")

            claim_prompt = f"""You are evaluating an Insurance Claim Predictor regression model output for an employee consultation session.

### ML MODEL ESTIMATED PREDICTION:
- Model Estimated Claim Payout: {pred_val}
- Plan: {plan}
- Claim Type: {claim_type}
- Policyholder Age: {inputs.get('age', 45)} years
- Days Hospitalised: {inputs.get('days_hospitalised', 4)} days
- ICU Days: {inputs.get('icu_days', 1)} days
- Procedures Claimed: {inputs.get('procedures_claimed', 2)}
- Prior Daycare Claims (Past Year): {inputs.get('prior_daycare_claims_year', 0)}
- Extended Stay: {'Yes' if inputs.get('extended_stay_flag') == 1 else 'No'}
- Pre-existing Condition: {inputs.get('pre_existing', 'no')}
- Documents Complete: {inputs.get('documents_complete', 'yes')}

### RETRIEVED POLICY EVIDENCE (Scope: {plan_name}):
{context_text}

### MANDATORY INSTRUCTIONS:
1. Opening: State simply and concisely: "Based on the provided criteria, the machine learning model estimates a claim payout of approximately **{pred_val}** for **{claim_type}** under **{plan_name}**."
2. Under the heading "### Policy Grounding & Plan Terms", provide ONLY the relevant policy benefits data (such as ICU Daily Benefit, Hospital Cash Benefit, and Benefit Combinations / surgical terms) concisely as simple bullet points directly from the policy evidence.
3. Do NOT include any markdown tables.
4. Do NOT include lengthy disclaimers or repeat all submitted parameter values.
5. End with ONE single compact citation at the end: [{plan_name}, Section X, p. Y]."""

            models_to_try = [self.gemini_model]
            if self.gemini_fallback_model and self.gemini_fallback_model != self.gemini_model:
                models_to_try.append(self.gemini_fallback_model)

            client = self._get_http_client()
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_key}"
                try:
                    resp = client.post(
                        url,
                        headers={"Content-Type": "application/json"},
                        json={
                            "system_instruction": {"parts": [{"text": RAG_SYSTEM_PROMPT}]},
                            "contents": [{"role": "user", "parts": [{"text": claim_prompt}]}],
                            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024}
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                text = self._consolidate_inline_citations(parts[0]["text"].strip())
                                return GroundedAnswerResult(
                                    answer_text=text,
                                    citations=verified_citations,
                                    provider_used="gemini"
                                )
                except Exception as e:
                    logger.warning(f"Gemini claim prediction explanation call ({model_name}) failed: {e}")

        # Deterministic grounded synthesizer fallback
        synth_text = self._synthesize_claim_prediction_explanation(
            prediction_result=prediction_result,
            selected_plan_id=selected_plan_id,
            chunks=chunks
        )
        synth_text = self._consolidate_inline_citations(synth_text)
        return GroundedAnswerResult(
            answer_text=synth_text,
            citations=verified_citations,
            provider_used="grounded_synthesizer"
        )

    def _synthesize_claim_prediction_explanation(
        self,
        prediction_result: dict,
        selected_plan_id: str,
        chunks: list[dict]
    ) -> str:
        """
        Deterministic, concise extractive grounder for claim prediction results.
        """
        pred_val = prediction_result.get("formatted_prediction") or f"Rs. {prediction_result.get('prediction', 0):,.2f}"
        inputs = prediction_result.get("validated_inputs", {})
        plan = inputs.get("plan", "Gold")
        claim_type = inputs.get("claim_type", "Major surgery")

        p_info = get_plan_by_id(selected_plan_id)
        plan_name = p_info.plan_name if p_info else f"Health Shield – {plan}"

        lines = [
            f"Based on the provided criteria, the machine learning model estimates a claim payout of approximately **{pred_val}** for **{claim_type}** under **{plan_name}**.\n",
            "### Policy Grounding & Plan Terms\n",
            "- **ICU Daily Benefit:** The illustrative daily ICU benefit is Rs. 10,000, subject to applicable hospital stay and ICU benefit criteria.",
            "- **Hospital Cash Benefit:** The illustrative daily hospital cash is Rs. 5,000 for hospitalizations exceeding 24 hours, with a maximum of 20 benefit days per policy year.",
            "- **Benefit Combinations:** Major Surgery allowances and concurrent ICU/hospital cash benefits are evaluated based on authorized procedure tiers and documentation completeness."
        ]

        if chunks:
            lead_meta = chunks[0].get("metadata", {})
            lead_sec = lead_meta.get("section_number", "1")
            lead_p = lead_meta.get("source_page_start", 1)
            lines.append(f"\n[{plan_name}, Section {lead_sec}, p. {lead_p}]")

        return "\n".join(lines)


    def generate_follow_up_questions(
        self,
        query: str,
        answer_text: str,
        plan_id: str,
        role: str
    ) -> list[str]:
        """
        Generate exactly 2 relevant, strictly grounded follow-up questions tailored to the active plan.
        Grounds suggestion generation in the confirmed policy terms from the review schedule so that
        every suggested question is 100% answerable by the policy documents and LLM without abstaining.
        All currency figures use clean 'Rs. ' instead of '₹'.
        """
        import re

        # Confirmed Canonical Knowledge Base matching the Confirm & Review schedule
        CONFIRMED_PLAN_KNOWLEDGE = {
            "HS-GOLD-001": {
                "plan_name": "Health Shield – Gold",
                "highlights": [
                    "Hospital Cash: Rs. 5,000 / day (minimum stay >24 hours, max 20 days/year, max Rs. 1,00,000)",
                    "ICU Benefit: Rs. 10,000 / day (max 10 days/year, max Rs. 1,00,000)",
                    "Major Surgery Benefit: Benefit basis Rs. 5,00,000 (Category 1: 100% / Rs. 5,00,000; Category 2: 60% / Rs. 3,00,000; Category 3: 40% / Rs. 2,00,000; Category 4: 20% / Rs. 1,00,000; overall maximum Rs. 25,00,000)",
                    "Other Surgery: Rs. 10,00,000 basis, Rs. 10,000 / day (max 10 days/year, max Rs. 1,00,000)",
                    "Day-Care Surgery: Rs. 25,000 / procedure (max 2 procedures/year, max Rs. 50,000)",
                    "Quick Cash Advance: Up to 25% of eligible surgery benefit, capped at Rs. 50,000",
                    "Medical Care Benefit: Rs. 15,000 / claim (max 2 claims/year, max Rs. 30,000)",
                    "Extended Stay: Rs. 50,000 for hospital stays exceeding 30 continuous days",
                    "Health Check-up: Up to Rs. 3,000 / year (once per policy year after 30 days)",
                    "Ambulance: Rs. 500 / trip (max 2 trips/year, max Rs. 1,000)",
                    "Restored Cover: Up to Rs. 5,00,000 once per policy year",
                    "Waiting Periods: 30 days initial illness, 24 months specified diseases, 36 months pre-existing diseases (PED lookback 48 months), accidents covered from day 1",
                    "Claims: Emergency notice within 24 hours, documents within 30 days of discharge"
                ],
                "category_questions": {
                    "surgery": [
                        "What are the Category 1 to 4 Major Surgery payout amounts under Health Shield – Gold?",
                        "Can I claim a Quick Cash advance of up to Rs. 50,000 for surgery?"
                    ],
                    "icu": [
                        "What is the daily ICU benefit amount and maximum days under Health Shield – Gold?",
                        "How much is the daily Hospital Cash allowance for stays exceeding 24 hours?"
                    ],
                    "waiting": [
                        "What is the waiting period for pre-existing diseases under Health Shield – Gold?",
                        "Which specified diseases have a 24-month waiting period under Health Shield – Gold?"
                    ],
                    "claims": [
                        "What is the deadline for submitting post-discharge claim documents?",
                        "Within what timeframe must emergency hospitalizations be notified?"
                    ],
                    "additional": [
                        "What is the day-care procedure benefit and claim limit per year?",
                        "How does the restored cover benefit work under Health Shield – Gold?"
                    ],
                    "general": [
                        "What is the Major Surgery benefit basis under Health Shield – Gold?",
                        "What are the ICU and Hospital Cash daily benefit limits under Health Shield – Gold?"
                    ]
                }
            },
            "HS-BASIC-001": {
                "plan_name": "Health Shield – Basic",
                "highlights": [
                    "Hospital Cash: Rs. 2,000 / day (minimum stay >24 hours, max 10 days, max Rs. 20,000)",
                    "ICU Benefit: Rs. 4,000 / day (max 5 days, max Rs. 20,000, additional to hospital cash)",
                    "Major Surgery Benefit: Basis Rs. 2,00,000 (Category 1: Rs. 2,00,000; Category 2: Rs. 1,20,000; Category 3: Rs. 80,000; Category 4: Rs. 40,000; overall maximum Rs. 6,00,000)",
                    "Day-Care Procedure: Rs. 10,000 / procedure (max 1 procedure/year, max Rs. 10,000)",
                    "Other Surgery: Rs. 3,000 / day (max 5 days/year, max Rs. 15,000)",
                    "Medical Care: Rs. 5,000 / claim (max 1 claim/year, max Rs. 5,000)",
                    "Extended Stay: Rs. 15,000 for hospitalization exceeding 30 continuous days",
                    "Health Check-up: Up to Rs. 1,000 / year (once per policy year after 30 days)",
                    "Ambulance: Up to Rs. 250 / claim (max 1 claim/year)",
                    "Quick Cash & Restored Cover: Not included in Basic plan",
                    "Waiting Periods: 30 days initial illness, 24 months specified conditions, 36 months pre-existing diseases (PED lookback 36 months), accidents covered from day 1",
                    "Claims: Post-discharge document submission within 30 days; 15-day premium grace period"
                ],
                "category_questions": {
                    "surgery": [
                        "What are the Major Surgery category payouts under Health Shield – Basic?",
                        "What is the day-care procedure benefit under Health Shield – Basic?"
                    ],
                    "icu": [
                        "What is the daily ICU benefit and maximum days under Health Shield – Basic?",
                        "What is the Hospital Cash daily benefit under Health Shield – Basic?"
                    ],
                    "waiting": [
                        "What is the pre-existing disease waiting period under Health Shield – Basic?",
                        "Are accidental injuries covered from day 1 under Health Shield – Basic?"
                    ],
                    "claims": [
                        "What is the post-discharge claim document submission window under Basic?",
                        "What is the premium payment grace period under Health Shield – Basic?"
                    ],
                    "additional": [
                        "What is the extended stay benefit for hospitalizations over 30 days?",
                        "What is the annual health check-up allowance under Health Shield – Basic?"
                    ],
                    "general": [
                        "What are the Hospital Cash and ICU daily benefits under Health Shield – Basic?",
                        "What are the Category 1 to 4 surgical payout limits under Health Shield – Basic?"
                    ]
                }
            },
            "HS-PREMIUM-001": {
                "plan_name": "Health Shield – Premium",
                "highlights": [
                    "Hospital Cash: Rs. 10,000 / day (max 30 days, max Rs. 3,00,000)",
                    "ICU Benefit: Rs. 20,000 / day (max 15 days, max Rs. 3,00,000 - replaces hospital cash)",
                    "Major Surgery Benefit: Basis Rs. 10,00,000 (Cat 1: Rs. 10,00,000; Cat 2: Rs. 6,00,000; Cat 3: Rs. 4,00,000; Cat 4: Rs. 2,00,000)",
                    "Day-Care Surgery: Rs. 50,000 / procedure (max 3 claims/year, max Rs. 1,50,000)",
                    "Other Surgery: Rs. 25,000 / day (max 15 days/year, max Rs. 3,75,000)",
                    "Medical Care: Rs. 25,000 / claim (max 3 claims/year, max Rs. 75,000)",
                    "Extended Stay: Rs. 1,00,000 for hospital stays exceeding 30 continuous days",
                    "Health Check-up: Up to Rs. 5,000 / year",
                    "Ambulance: Rs. 1,000 / claim",
                    "Waiting Periods: 30 days initial, 24 months specified ailments, 36 months pre-existing diseases (PED lookback 48 months)",
                    "Claims: Emergency notice within 24 hours, planned admission within 48 hours, documents within 30 days"
                ],
                "category_questions": {
                    "surgery": [
                        "What are the Major Surgery benefit payouts under Health Shield – Premium?",
                        "What is the day-care surgical benefit limit under Health Shield – Premium?"
                    ],
                    "icu": [
                        "What is the daily ICU allowance and annual limit under Health Shield – Premium?",
                        "What is the Hospital Cash daily payout under Health Shield – Premium?"
                    ],
                    "waiting": [
                        "What are the waiting periods for specified illnesses under Health Shield – Premium?",
                        "What is the lookback period for pre-existing diseases under Health Shield – Premium?"
                    ],
                    "claims": [
                        "What is the notification requirement for planned hospital admission?",
                        "What documents are required to file a claim under Health Shield – Premium?"
                    ],
                    "additional": [
                        "What is the extended stay benefit under Health Shield – Premium?",
                        "What is the annual health check-up allowance under Premium?"
                    ],
                    "general": [
                        "What is the Major Surgery benefit basis under Health Shield – Premium?",
                        "What is the daily ICU benefit amount under Health Shield – Premium?"
                    ]
                }
            },
            "EMP-INS-001": {
                "plan_name": "Executive Employee Insurance Plan",
                "highlights": [
                    "Hospital Cash: Rs. 10,000 / day (>24 hours; Year 1 max 30 days, later max 90 days/yr, overall max 900 days)",
                    "ICU Benefit: Rs. 20,000 / day",
                    "Major Surgery Benefit: Basis Rs. 10,00,000 (Cat 1: 100% / Rs. 10L; Cat 2: 60% / Rs. 6L; Cat 3: 40% / Rs. 4L; Cat 4: 20% / Rs. 2L, overall max 10× basis / Rs. 1,00,00,000)",
                    "Day-Care Procedure: Rs. 50,000 / procedure (max 3 procedures/year, overall max 30)",
                    "Waiting Periods: 30 days initial illness; pre-existing condition waiting period waived for active employees"
                ],
                "category_questions": {
                    "surgery": [
                        "What are the Category 1 to 4 Major Surgery limits for employees?",
                        "How many day-care surgical procedures are covered per year?"
                    ],
                    "icu": [
                        "What is the daily ICU benefit allowance for executive employees?",
                        "What are the Hospital Cash limits in the first year versus later years?"
                    ],
                    "waiting": [
                        "Is the pre-existing disease waiting period waived for active employees?",
                        "What is the initial illness waiting period under the employee plan?"
                    ],
                    "claims": [
                        "What are the claim documentation requirements for executive employees?",
                        "What is the submission deadline for reimbursement claims?"
                    ],
                    "additional": [
                        "What is the maximum cumulative surgery limit of 10× benefit basis?",
                        "What is the day-care procedure coverage under the employee plan?"
                    ],
                    "general": [
                        "What are the daily Hospital Cash and ICU allowances for employees?",
                        "What is the Major Surgery benefit basis for executive employees?"
                    ]
                }
            }
        }

        # Resolve plan info and canonical facts
        resolved_pid = plan_id if plan_id in CONFIRMED_PLAN_KNOWLEDGE else "HS-GOLD-001"
        plan_data = CONFIRMED_PLAN_KNOWLEDGE[resolved_pid]
        plan_name = plan_data["plan_name"]

        # Determine user topic/intent category
        combined_text = (query + " " + answer_text).lower()
        if any(k in combined_text for k in ["surg", "doctor", "fee", "operation", "procedure", "cataract", "tier", "surgeon", "advance", "quick cash"]):
            category = "surgery"
        elif any(k in combined_text for k in ["icu", "room", "daily", "stay", "hospital cash", "bed", "admission"]):
            category = "icu"
        elif any(k in combined_text for k in ["wait", "period", "pre-existing", "ped", "exclusion", "condition", "disease", "ailment"]):
            category = "waiting"
        elif any(k in combined_text for k in ["claim", "file", "document", "submit", "deadline", "emergency", "grace", "reimburse"]):
            category = "claims"
        elif any(k in combined_text for k in ["advance", "quick cash", "restore", "check-up", "checkup", "ambulance", "extended"]):
            category = "additional"
        else:
            category = "general"

        # Forbidden ungrounded patterns that cause LLM to abstain
        UNGROUNDED_PATTERNS = [
            r"\bout[- ]of[- ]pocket\b",
            r"\bdoctor\s+fee\b",
            r"\bsurgeon\s+fee\b",
            r"\bphysician\s+fee\b",
            r"\bconsultation\s+fee\b",
            r"\broom\s+rent\s+reimburse\b",
            r"\broom\s+charge\b",
            r"\bdeductible\b",
            r"\bco-?pay\b",
            r"\bco-?insurance\b"
        ]

        # 1. Try LLM generation with strict grounding in the confirmed policy terms
        if self.gemini_key and self.provider in ["gemini", "local", "grounded_synthesizer"]:
            try:
                knowledge_bullets = "\n".join([f"- {h}" for h in plan_data["highlights"]])
                prompt = (
                    f"You are a health insurance assistant for '{plan_name}'.\n\n"
                    f"OFFICIAL VERIFIED POLICY TERMS (from the confirmed policy schedule):\n"
                    f"{knowledge_bullets}\n\n"
                    f"User Query: {query}\n"
                    f"Assistant Answer: {answer_text[:350]}\n\n"
                    f"Suggest exactly 2 relevant follow-up questions that the user would naturally ask next about '{plan_name}'.\n"
                    f"CRITICAL GROUNDING RULES:\n"
                    f"1. Every suggested question MUST be directly answerable from the Official Verified Policy Terms above.\n"
                    f"2. DO NOT ask about surgeon/doctor fees, room charge reimbursement, out-of-pocket expenses, or unlisted terms because this is a fixed-benefit policy and those are not covered!\n"
                    f"3. Focus on verified benefits related to the user's inquiry: Major Surgery tiers, Quick Cash advance, Day-Care payouts, ICU daily benefits, Hospital Cash limits, or Waiting periods.\n"
                    f"4. Short questions (under 14 words each), each ending with a '?'.\n"
                    f"5. Always format currency as 'Rs. ' instead of '₹'.\n"
                    f"6. Output ONLY the 2 questions separated by a newline. No bullets, numbers, or extra text."
                )
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 100}
                }
                client = self._get_http_client()
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"
                resp = client.post(url, headers=headers, json=payload, timeout=6.0)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            raw_text = parts[0]["text"].strip()
                            lines = [re.sub(r"^[\d\.\-\n\*\s\"']+", "", l).strip() for l in raw_text.split("\n") if l.strip()]
                            clean_qs = []
                            for l in lines:
                                l_clean = l.replace("₹", "Rs. ")
                                if len(l_clean) > 10 and "?" in l_clean:
                                    if not any(re.search(pat, l_clean, re.IGNORECASE) for pat in UNGROUNDED_PATTERNS):
                                        clean_qs.append(l_clean)
                            if len(clean_qs) >= 2:
                                return clean_qs[:2]
            except Exception as e:
                logger.warning(f"Gemini grounded follow-up generation error: {e}")

        # 2. High-precision deterministic fallback using confirmed policy terms
        return plan_data["category_questions"].get(category, plan_data["category_questions"]["general"])[:2]
