"""Time-sensitive civic question classification (narrow Phase-1 scope).

Deterministic, non-LLM. Rejects civic-action intents and out-of-scope
jurisdictions before matching supported current-fact patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import ErrorCode, FactKind

_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ClassificationResult:
    supported: bool
    fact_kind: FactKind | None
    reason: str
    failure_code: ErrorCode | None
    normalized_question: str

    # Alias used by the Phase-1 brief (fact_type).
    @property
    def fact_type(self) -> str | None:
        return self.fact_kind.value if self.fact_kind else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported": self.supported,
            "fact_type": self.fact_type,
            "fact_kind": self.fact_type,
            "reason": self.reason,
            "failure_code": self.failure_code.value if self.failure_code else None,
            "normalized_question": self.normalized_question,
        }


def _normalize(question: object) -> str | None:
    if question is None:
        return None
    if not isinstance(question, str):
        return None
    return _WS_RE.sub(" ", question.strip().lower())


# Reject civic actions / other jurisdictions / broad lists first.
_REJECT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"민원"), "civic_action_complaint"),
    (re.compile(r"신청"), "civic_action_application"),
    (re.compile(r"신고"), "civic_action_report"),
    (re.compile(r"전국"), "out_of_scope_nationwide"),
    (re.compile(r"목록"), "out_of_scope_list"),
    (re.compile(r"광주\s*시장|시장\s*(은|이|가)\s*누구"), "out_of_scope_city_mayor"),
    (re.compile(r"날씨"), "out_of_scope_weather"),
)

_MAYOR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"현재\s*(광주\s*)?북구\s*구청장"),
    re.compile(r"지금\s*(광주\s*)?북구\s*구청장"),
    re.compile(r"(광주\s*)?북구\s*구청장\s*(이|은|가)?\s*누구"),
    re.compile(r"(광주\s*)?북구\s*구청장\s*(성함|성명|이름)"),
    re.compile(r"현재\s*북구청장"),
    re.compile(r"지금\s*북구청장"),
    re.compile(r"북구청장\s*(이|은|가)?\s*누구"),
    re.compile(r"(who\s+is\s+)?(the\s+)?(current\s+)?buk[- ]?gu\s+mayor"),
)

_JURISDICTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"북구청의\s*현재\s*기관명"),
    re.compile(r"현재\s*공식\s*자치구\s*명칭"),
    re.compile(r"(공식\s*)?(자치구|기관|조직)\s*(명칭|이름)"),
    re.compile(r"북구청\s*(공식\s*)?(이름|명칭|기관명)"),
    re.compile(r"(관할|행정)\s*구역\s*(이름|명칭)?"),
    re.compile(r"(jurisdiction|organization)\s*name"),
)


def classify_question(question: object) -> ClassificationResult:
    """Classify a resident question into a supported time-sensitive fact."""
    if question is None or not isinstance(question, str):
        return ClassificationResult(
            supported=False,
            fact_kind=None,
            reason="invalid_input_type",
            failure_code=ErrorCode.INVALID_REQUEST,
            normalized_question="",
        )

    normalized = _normalize(question)
    assert normalized is not None
    if not normalized:
        return ClassificationResult(
            supported=False,
            fact_kind=None,
            reason="empty_question",
            failure_code=ErrorCode.INVALID_REQUEST,
            normalized_question=normalized,
        )

    for pattern, reason in _REJECT_PATTERNS:
        if pattern.search(normalized):
            return ClassificationResult(
                supported=False,
                fact_kind=None,
                reason=reason,
                failure_code=ErrorCode.UNSUPPORTED_QUESTION,
                normalized_question=normalized,
            )

    for pattern in _MAYOR_PATTERNS:
        if pattern.search(normalized):
            return ClassificationResult(
                supported=True,
                fact_kind=FactKind.CURRENT_MAYOR,
                reason="matched_current_mayor",
                failure_code=None,
                normalized_question=normalized,
            )

    for pattern in _JURISDICTION_PATTERNS:
        if pattern.search(normalized):
            return ClassificationResult(
                supported=True,
                fact_kind=FactKind.JURISDICTION_NAME,
                reason="matched_jurisdiction_name",
                failure_code=None,
                normalized_question=normalized,
            )

    return ClassificationResult(
        supported=False,
        fact_kind=None,
        reason="unsupported_time_sensitive_fact",
        failure_code=ErrorCode.UNSUPPORTED_QUESTION,
        normalized_question=normalized,
    )


__all__ = [
    "ClassificationResult",
    "classify_question",
]
