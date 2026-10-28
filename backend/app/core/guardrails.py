import re
import unicodedata
from typing import Optional, Tuple, List, Dict, Any
from fastapi import HTTPException, status
from backend.app.core.config import settings
from backend.app.core.logging_config import logger

# Bidi Trojan Source and invisible formatting characters to strip
DANGEROUS_UNICODE_CHARS = {
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',  # LRE, RLE, PDF, LRO, RLO
    '\u2066', '\u2067', '\u2068', '\u2069',            # LRI, RLI, FSI, PDI
    '\u200b', '\u200c', '\u200d', '\ufeff',            # Zero-width spaces and BOM
    '\x00'                                              # Null byte
}

# Compiled regex patterns for direct prompt injection and instruction override detection
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|directives|prompts|rules)", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(system|developer|all)\s+(prompt|instructions|rules)", re.IGNORECASE),
    re.compile(r"(override|bypass|disable)\s+(all\s+)?(safety|guardrails|security|restrictions|filters)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(in\s+)?(developer\s+mode|dan|unrestricted|jailbreak)", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?(rules|instructions|directives|prompts)\s+(and|to)\s+(reveal|show|print|tell|bypass)", re.IGNORECASE),
    re.compile(r"(roleplay|act)\s+as\s+(an?\s+)?unrestricted\s+ai", re.IGNORECASE),
    re.compile(r"<\s*/?\s*(system|instruction|developer|admin)\s*>", re.IGNORECASE),
]

# Patterns requesting to disclose hidden system prompts, developer instructions, or credentials
SYSTEM_DISCLOSURE_PATTERNS = [
    re.compile(r"what\s+(is|are)\s+(the|your|its|all)\s+.*system\s+(prompt|instruction|directive|rule)s?", re.IGNORECASE),
    re.compile(r"(reveal|print|disclose|dump|output|show|tell|share|display|give)\s+(?:me\s+)?(?:your\s+|the\s+|all\s+)?(?:system\s+|developer\s+|internal\s+|hidden\s+)?(?:prompts?|instructions?|rules?|directives?|secrets?|api\s*keys?|backend\s+config)", re.IGNORECASE),
    re.compile(r"what\s+(is|are)\s+(the|your|its)\s+(hidden|internal|developer)\s+(instruction|prompt|directive)s?", re.IGNORECASE),
    re.compile(r"repeat\s+(everything|the\s+text|all\s+system\s+prompts?)\s*(above|before|starting\s+with|verbatim)?", re.IGNORECASE),
    re.compile(r"what\s+instructions\s+were\s+you\s+given", re.IGNORECASE),
    re.compile(r"what\s+is\s+your\s+prompt\b", re.IGNORECASE),
]

# Sensitive patterns that must never appear in generated responses (Secrets, Keys, Credentials)
SECRET_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z\-_]{30,40}"), "[REDACTED_API_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9\-_]{20,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_\.=]{20,}", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"\$2[abxy]?\$\d{2}\$[A-Za-z0-9\.\/]{53}"), "[REDACTED_HASH]"),
    (re.compile(r"(GEMINI_API_KEY|OPENAI_API_KEY|CHROMA_API_KEY)\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE), "[REDACTED_CONFIG]")
]

class InputGuardrail:
    """
    Validates and sanitizes user input before retrieval or model inference.
    Enforces length limits, removes dangerous Unicode, and screens for direct prompt injection.
    """

    @staticmethod
    def sanitize_text(text: str) -> str:
        """Removes null bytes, zero-width characters, and bidirectional overrides."""
        if not text:
            return ""
        # Normalize Unicode NFC
        normalized = unicodedata.normalize("NFC", text)
        # Strip dangerous invisible and Trojan Source characters
        cleaned = "".join(ch for ch in normalized if ch not in DANGEROUS_UNICODE_CHARS)
        return cleaned.strip()

    @staticmethod
    def validate_user_query(
        query: str,
        max_length: Optional[int] = None,
        block_on_injection: bool = True
    ) -> Tuple[str, bool, Optional[str]]:
        """
        Validates a user message:
        1. Checks non-emptiness.
        2. Enforces maximum character budget.
        3. Sanitizes dangerous Unicode.
        4. Detects direct prompt injection or disclosure requests.
        Returns: (sanitized_query, is_injection_flagged, refusal_reason)
        """
        limit = max_length or settings.MAX_QUERY_CHARS
        if not query or not query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query cannot be empty."
            )

        if len(query) > limit:
            logger.warning(f"Query length {len(query)} exceeded maximum threshold {limit}.")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Query exceeds the maximum allowed length of {limit} characters."
            )

        sanitized = InputGuardrail.sanitize_text(query)

        # 1. Prompt Injection & Override screening
        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(sanitized):
                logger.warning(f"Prompt injection pattern detected: '{pattern.pattern}' in query excerpt: '{sanitized[:80]}...'")
                if block_on_injection:
                    return (
                        sanitized,
                        True,
                        "I'm sorry, but I cannot process this request because it violates security boundaries. To ensure system security and reliable guidance, I cannot override my operating instructions, safety directives, or configuration. I'm here to assist you with questions about your health insurance policy, benefits, and claims."
                    )

        # 2. System Prompt & Instruction Disclosure screening
        for pattern in SYSTEM_DISCLOSURE_PATTERNS:
            if pattern.search(sanitized):
                logger.warning(f"System disclosure pattern detected: '{pattern.pattern}' in query excerpt: '{sanitized[:80]}...'")
                if block_on_injection:
                    return (
                        sanitized,
                        True,
                        "I cannot disclose internal system instructions, configuration directives, or private prompts. I am an AI Health Insurance Assistant designed to help you understand health insurance policy benefits, claims, waiting periods, and eligibility."
                    )

        return (sanitized, False, None)


class OutputGuardrail:
    """
    Validates model output before delivering to the client.
    Redacts exposed credentials/secrets, verifies citations against retrieved chunks,
    and ensures policy grounding fidelity.
    """

    @staticmethod
    def redact_secrets(text: str) -> str:
        """Scans response text and redacts any accidentally exposed API keys, tokens, or hashes."""
        if not text:
            return ""
        redacted = text
        for pattern, replacement in SECRET_PATTERNS:
            if pattern.search(redacted):
                logger.critical(f"OutputGuardrail caught and redacted sensitive secret pattern: {pattern.pattern}")
                redacted = pattern.sub(replacement, redacted)
        return redacted

    @staticmethod
    def validate_citations_against_scope(
        citations: List[Any],
        authorized_plans: set[str],
        retrieved_chunk_ids: set[str]
    ) -> List[Any]:
        """
        Fails closed on hallucinated citations:
        Ensures every citation references a verified chunk retrieved in the current turn
        and belongs to the user's authorized plan scope.
        """
        valid_citations = []
        for c in citations:
            plan_id = getattr(c, "plan_id", None) or (c.get("plan_id") if isinstance(c, dict) else None)
            source_id = getattr(c, "source_id", None) or (c.get("source_id") if isinstance(c, dict) else None)
            chunk_id = getattr(c, "chunk_id", None) or (c.get("chunk_id") if isinstance(c, dict) else None)
            ref_id = source_id or chunk_id

            # Check plan authorization
            if plan_id and plan_id not in authorized_plans:
                logger.warning(f"OutputGuardrail stripped citation from unauthorized plan '{plan_id}'")
                continue

            # Check that citation actually matches retrieved evidence
            if ref_id and retrieved_chunk_ids and ref_id not in retrieved_chunk_ids:
                logger.warning(f"OutputGuardrail stripped fabricated citation ID '{ref_id}' not in retrieved chunks.")
                continue

            valid_citations.append(c)

        return valid_citations

    @staticmethod
    def sanitize_links(text: str) -> str:
        """Strips dangerous URI schemes (javascript:, data:, vbscript:) from markdown links."""
        if not text:
            return ""
        # Match [label](url)
        def replace_link(match):
            label = match.group(1)
            url = match.group(2).strip()
            clean_url = url.lower()
            if clean_url.startswith(("javascript:", "data:", "vbscript:")):
                return label  # Remove malicious link, keep label as plain text
            return f"[{label}]({url})"

        return re.sub(r'\[([^\]]+)\]\(((?:[^()]|\([^()]*\))+)\)', replace_link, text)
