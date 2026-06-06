"""Question logging boundary for retrieval analytics.

Provides structured, privacy-conscious logging of user questions and search/answer
metadata without external storage dependencies, tracking personal details, or logging secrets.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse


@dataclass(frozen=True)
class QuestionLogEvent:
    """Structured event capturing metadata about a question and its processing."""
    timestamp: str
    site_id: str | None
    raw_question: str
    normalized_question: str
    provider_mode: str | None
    retrieval_mode: str | None
    query_rewrite_strategy: str | None
    query_rewrite_queries: tuple[str, ...]
    result_count: int
    source_domains: tuple[str, ...]
    answer_status: str
    fallback_used: bool
    guard_status: str | None = None
    guard_reason: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


# ------------------------------------------------------------------
# Sanitizer / Redaction Helpers
# ------------------------------------------------------------------

SECRET_KEYS_PATTERN = re.compile(
    r'(?:api_key|secret|token|password|authorization|bearer|nvidia_api_key|ai_finder_llm_api_key)',
    re.IGNORECASE
)


def sanitize_text(text: str) -> str:
    """Redact API keys, credentials, and suspicious credentials from text."""
    if not text:
        return ""

    # 1. Redact Bearer tokens: Bearer <token>
    text = re.sub(
        r'(bearer\s+)([a-zA-Z0-9_\-\.\+=/]{6,})',
        r'\1[REDACTED]',
        text,
        flags=re.IGNORECASE
    )

    # 2. Redact key-value pairings like api_key=value or api_key: value
    text = re.sub(
        r'((?:api_key|secret|token|password|authorization|bearer|nvidia_api_key|ai_finder_llm_api_key))([\s:=]+)(["\']?)([a-zA-Z0-9_\-\.\+=/]{4,})\3',
        r'\1\2\3[REDACTED]\3',
        text,
        flags=re.IGNORECASE
    )

    # 3. Redact OpenAI-like API keys: sk-...
    text = re.sub(
        r'\b(sk-[a-zA-Z0-9]{16,})\b',
        '[REDACTED]',
        text
    )

    # 4. Mask suspicious long alphanumeric strings (length >= 32)
    def _mask_credential_like(match: re.Match) -> str:
        val = match.group(0)
        # Avoid redacting base URLs/URLs
        if val.startswith(('http://', 'https://', 'ftp://')):
            return val
        # Check if it has a mix of characters (typical for credentials/hashes)
        if any(c.isdigit() for c in val) and any(c.isalpha() for c in val):
            return "[REDACTED]"
        return val

    text = re.sub(
        r'\b[a-zA-Z0-9_\-\.+=/]{32,}\b',
        _mask_credential_like,
        text
    )

    return text


def _normalize_question(question: str) -> str:
    """Safely normalize a question by lowercasing and stripping common Korean particles."""
    if not question:
        return ""
    text = question.strip().lower()
    particles = (
        "에서", "에게", "한테", "께서", "은", "는", "이", "가",
        "을", "를", "에", "의", "로", "으로", "와", "과", "도", "만"
    )
    for p in particles:
        if text.endswith(p) and len(text) > len(p):
            text = text[:-len(p)]
            break
    return text


# ------------------------------------------------------------------
# Safe Event Construction Helper
# ------------------------------------------------------------------

def build_question_log_event(
    *,
    site_id: str | None,
    question: str,
    provider_mode: str | None = None,
    retrieval_mode: str | None = None,
    query_rewrite: Mapping[str, Any] | None = None,
    search_results: Sequence[Mapping[str, Any]] = (),
    sources: Sequence[Mapping[str, Any]] = (),
    answer_status: str | None = None,
    fallback_used: bool = False,
    guard_status: str | None = None,
    guard_reason: str | None = None,
    warnings: Sequence[str] = (),
) -> QuestionLogEvent:
    """Build a QuestionLogEvent safely with sanitization of all text fields."""
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # 1. Sanitize simple fields
    raw_question = sanitize_text(question)
    normalized_question = _normalize_question(raw_question)
    
    san_provider_mode = sanitize_text(provider_mode) if provider_mode else None
    san_retrieval_mode = sanitize_text(retrieval_mode) if retrieval_mode else None
    
    # 2. Process query rewrite
    rewrite_strategy = None
    rewrite_queries: list[str] = []
    if query_rewrite:
        rewrite_strategy = query_rewrite.get("strategy")
        if "queries" in query_rewrite:
            for q in query_rewrite["queries"]:
                san_q = sanitize_text(q)
                if san_q and san_q not in rewrite_queries:
                    rewrite_queries.append(san_q)
                    
    # 3. Derive result count
    # Count results from search_results first, fallback to sources
    res_count = len(search_results) if search_results else len(sources)
    
    # 4. Extract and sanitize source domains
    source_domains: list[str] = []
    for src in (sources or search_results):
        url = src.get("url") or src.get("canonical_url")
        if url:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split('/')[0]
            domain = sanitize_text(domain)
            if domain and domain not in source_domains:
                source_domains.append(domain)
                
    # 5. Sanitize guard fields and warnings
    san_guard_status = sanitize_text(guard_status) if guard_status else None
    san_guard_reason = sanitize_text(guard_reason) if guard_reason else None
    
    san_warnings = [sanitize_text(w) for w in warnings if w]
    
    return QuestionLogEvent(
        timestamp=timestamp,
        site_id=site_id,
        raw_question=raw_question,
        normalized_question=normalized_question,
        provider_mode=san_provider_mode,
        retrieval_mode=san_retrieval_mode,
        query_rewrite_strategy=rewrite_strategy,
        query_rewrite_queries=tuple(rewrite_queries),
        result_count=res_count,
        source_domains=tuple(source_domains),
        answer_status=answer_status or "unknown",
        fallback_used=fallback_used,
        guard_status=san_guard_status,
        guard_reason=san_guard_reason,
        warnings=tuple(san_warnings),
    )


# ------------------------------------------------------------------
# Logger Implementations
# ------------------------------------------------------------------

class QuestionLogger:
    """Base interface for question logging."""
    
    def log(self, event: QuestionLogEvent) -> None:
        """Record a structured question event."""
        raise NotImplementedError("Logger subclasses must implement log()")


class NoOpQuestionLogger(QuestionLogger):
    """Default logger that silently drops all log events."""
    
    def log(self, event: QuestionLogEvent) -> None:
        return None


class JsonlQuestionLogger(QuestionLogger):
    """Appends question log events to a local JSONL file."""
    
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        
    def log(self, event: QuestionLogEvent) -> None:
        # Create parent directories as needed
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
        # Serialize dataclass to dictionary
        event_dict = asdict(event)
        
        # Double-check redaction for all string values to ensure no leakage
        def _recursive_sanitize(item: Any) -> Any:
            if isinstance(item, dict):
                return {k: _recursive_sanitize(v) for k, v in item.items()}
            elif isinstance(item, (list, tuple)):
                return type(item)(_recursive_sanitize(x) for x in item)
            elif isinstance(item, str):
                return sanitize_text(item)
            return item
            
        sanitized_dict = _recursive_sanitize(event_dict)
        
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(sanitized_dict, ensure_ascii=False) + "\n")
