"""Time-sensitive civic question classification (expanded #1150 scope).

Deterministic, non-LLM. Rejects pure civic-action intents that belong to
deterministic journeys. Supports regional/district executives, jurisdiction,
hours, fees, notices, and general current-information cues.
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


# Pure action intents (journey territory) — not current-fact answers.
# Note: "신청" alone is too broad for fee/period questions; use compound forms.
_REJECT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"민원\s*(넣|접수|제출)"), "civic_action_complaint"),
    (re.compile(r"민원\s*넣어"), "civic_action_complaint"),
    (re.compile(r"북구청에\s*민원"), "civic_action_complaint"),
    (re.compile(r"여권\s*신청해"), "civic_action_application"),
    (re.compile(r"(신고해|신고\s*해\s*줘|신고해줘)"), "civic_action_report"),
    (re.compile(r"전국\s*.*목록"), "out_of_scope_list"),
    (re.compile(r"구청장\s*목록"), "out_of_scope_list"),
)

# District executive (Buk-gu mayor) — Phase-1 CURRENT_MAYOR kept for contracts.
_DISTRICT_EXEC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"현재\s*(광주\s*)?북구\s*구청장"),
    re.compile(r"지금\s*(광주\s*)?북구\s*구청장"),
    re.compile(r"(광주\s*)?북구\s*구청장\s*(이|은|가)?\s*누구"),
    re.compile(r"(광주\s*)?북구\s*구청장\s*(성함|성명|이름)"),
    re.compile(r"현재\s*북구청장"),
    re.compile(r"지금\s*북구청장"),
    re.compile(r"북구청장\s*(이|은|가)?\s*누구"),
    re.compile(r"(who\s+is\s+)?(the\s+)?(current\s+)?buk[- ]?gu\s+mayor"),
)

# Regional executive (city / special-city mayor seat — abstract fact kind).
_REGIONAL_EXEC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"전남광주통합특별시장"),
    re.compile(r"전남광주특별시장"),
    re.compile(r"광주광역시장"),
    re.compile(r"(현재|지금)?\s*광주\s*시장"),
    re.compile(r"광주시장\s*(이|은|가)?\s*누구"),
    re.compile(r"통합시장\s*(이|은|가)?\s*누구"),
    re.compile(r"특별시장\s*(이|은|가)?\s*누구"),
    re.compile(r"(current\s+)?(gwangju\s+)?mayor"),
)

_JURISDICTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"북구청의\s*현재\s*기관명"),
    re.compile(r"현재\s*공식\s*자치구\s*명칭"),
    re.compile(r"(공식\s*)?(자치구|기관|조직)\s*(명칭|이름)"),
    re.compile(r"북구청\s*(공식\s*)?(이름|명칭|기관명)"),
    re.compile(r"(관할|행정)\s*구역\s*(이름|명칭)?"),
    re.compile(r"(jurisdiction|organization)\s*name"),
    re.compile(r"전남광주통합특별시\s*(공식\s*)?(이름|명칭)?"),
    re.compile(r"광주특별시\s*(약칭|이름|명칭)"),
    re.compile(r"현재\s*(시|구)\s*(이름|명칭)"),
)

_AGENCY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"북구청\s*(어디|위치|주소)"),
    re.compile(r"담당\s*기관"),
)

_HOURS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"운영\s*시간"),
    re.compile(r"근무\s*시간"),
    re.compile(r"몇\s*시\s*까지"),
    re.compile(r"휴무|휴관일"),
)

_CONTACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"전화\s*번호"),
    re.compile(r"연락처"),
    re.compile(r"담당\s*부서"),
    re.compile(r"문의처"),
)

_FEE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"수수료"),
    re.compile(r"지원금"),
    re.compile(r"발급\s*비용"),
)

_PERIOD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"접수\s*기간"),
    re.compile(r"신청\s*기간"),
    re.compile(r"마감\s*일"),
)

_NOTICE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"공고"),
    re.compile(r"고시"),
)

_POLICY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"현재\s*정책"),
    re.compile(r"시책"),
)

_LAW_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"조례"),
    re.compile(r"법령"),
    re.compile(r"법률"),
)

_EVENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"행사"),
    re.compile(r"축제"),
    re.compile(r"선거"),
)

_GENERAL_CURRENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"날씨"),
    re.compile(r"weather"),
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

    # District executive first (more specific than regional "시장").
    for pattern in _DISTRICT_EXEC_PATTERNS:
        if pattern.search(normalized):
            # Phase-1 public fact_type remains current_mayor.
            return ClassificationResult(
                supported=True,
                fact_kind=FactKind.CURRENT_MAYOR,
                reason="matched_current_mayor",
                failure_code=None,
                normalized_question=normalized,
            )

    for pattern in _REGIONAL_EXEC_PATTERNS:
        if pattern.search(normalized):
            return ClassificationResult(
                supported=True,
                fact_kind=FactKind.REGIONAL_EXECUTIVE,
                reason="matched_regional_executive",
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

    ordered: tuple[tuple[tuple[re.Pattern[str], ...], FactKind, str], ...] = (
        (_AGENCY_PATTERNS, FactKind.AGENCY_NAME, "matched_agency_name"),
        (_HOURS_PATTERNS, FactKind.OFFICE_HOURS, "matched_office_hours"),
        (_CONTACT_PATTERNS, FactKind.CONTACT_INFORMATION, "matched_contact"),
        (_FEE_PATTERNS, FactKind.FEE, "matched_fee"),
        (_PERIOD_PATTERNS, FactKind.APPLICATION_PERIOD, "matched_application_period"),
        (_NOTICE_PATTERNS, FactKind.CURRENT_NOTICE, "matched_notice"),
        (_POLICY_PATTERNS, FactKind.CURRENT_POLICY, "matched_policy"),
        (_LAW_PATTERNS, FactKind.CURRENT_LAW, "matched_law"),
        (_EVENT_PATTERNS, FactKind.CURRENT_EVENT, "matched_event"),
        (
            _GENERAL_CURRENT_PATTERNS,
            FactKind.GENERAL_CURRENT_INFORMATION,
            "matched_general_current",
        ),
    )
    for patterns, kind, reason in ordered:
        for pattern in patterns:
            if pattern.search(normalized):
                return ClassificationResult(
                    supported=True,
                    fact_kind=kind,
                    reason=reason,
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
