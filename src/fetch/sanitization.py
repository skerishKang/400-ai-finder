"""Shared sanitization helpers for operator-facing failure surfaces."""

from __future__ import annotations

import json
import re
from typing import Any

from .compat_diagnostics import FetchCategory, FetchDiagnostic, classify_exception, format_operator_safe

SAFE_FAILURE_MESSAGE = "Request failed with a sanitized diagnostic."
SAFE_PIPELINE_FAILURE_MESSAGE = "Pipeline failed with a sanitized diagnostic."

_SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"\bfc-[A-Za-z0-9_-]+", re.IGNORECASE),
    re.compile(
        r"\b[A-Za-z0-9_.-]*(?:api[_-]?key|token|secret|password)"
        r"[A-Za-z0-9_.-]*\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"://[^\s/@:]+:[^\s/@]+@", re.IGNORECASE),
    re.compile(r"\b[A-Z][A-Za-z0-9-]+:\s+\S+"),
    re.compile(r"\b[a-z_]+=[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
)

_SAFE_WARNING_PREFIXES: tuple[str, ...] = (
    "Search returned 0 results; used ",
    "Pipeline partially failed: category=",
    "Pipeline failed: category=",
    "Pipeline raised: category=",
    "Pipeline timed out after ",
    "conversation log write failed",
)


def _contains_sensitive_text(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SENSITIVE_PATTERNS)


def safe_failure_message(exc: BaseException, prefix: str = "Failure") -> str:
    """Return a fixed-prefix message backed only by closed-vocabulary diagnostics."""
    diagnostic = classify_exception(exc)
    return f"{prefix}: {format_operator_safe(diagnostic)}"


def safe_pipeline_failure_message(
    diagnostic: FetchDiagnostic | None,
    fallback: str = SAFE_PIPELINE_FAILURE_MESSAGE,
) -> str:
    """Return a pipeline warning without echoing ``pipeline_result["error"]``."""
    if diagnostic is not None:
        return f"Pipeline failed: {format_operator_safe(diagnostic)}"
    return fallback


def sanitize_warning(value: Any) -> str:
    """Preserve known safe warnings and replace suspicious text with a fixed fallback."""
    text = str(value)
    if _contains_sensitive_text(text):
        return SAFE_FAILURE_MESSAGE
    if text.startswith(_SAFE_WARNING_PREFIXES):
        return text
    return SAFE_FAILURE_MESSAGE


def sanitize_warnings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [sanitize_warning(value) for value in values]


def sanitize_fetch_diagnostic(value: Any) -> dict[str, Any] | None:
    """Keep only the closed-vocabulary fetch diagnostic shape."""
    if not isinstance(value, dict):
        return None

    category = value.get("category")
    category_value = getattr(category, "value", category)
    allowed_categories = {item.value for item in FetchCategory}
    if category_value not in allowed_categories:
        return None

    sanitized = {
        "category": category_value,
        "short_reason": value.get("short_reason", ""),
        "retry_hint": value.get("retry_hint", ""),
        "is_transient": bool(value.get("is_transient", False)),
    }
    rendered = json.dumps(sanitized, ensure_ascii=False, sort_keys=True)
    if _contains_sensitive_text(rendered):
        return None
    return sanitized
