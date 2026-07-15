"""Time-sensitive civic question classification (narrow Phase-1 scope).

Maps resident questions to a supported ``FactKind`` or marks them
unsupported. Does not perform retrieval, network I/O, or fact invention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import FactKind

_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ClassificationResult:
    supported: bool
    fact_kind: FactKind | None
    reason: str
    normalized_question: str

    def to_dict(self) -> dict[str, object]:
        return {
            "supported": self.supported,
            "fact_kind": self.fact_kind.value if self.fact_kind else None,
            "reason": self.reason,
            "normalized_question": self.normalized_question,
        }


def _normalize(question: str) -> str:
    return _WS_RE.sub(" ", (question or "").strip().lower())


# Mayor: current office-holder questions only (not biography essays).
_MAYOR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(현재\s*)?(북구\s*)?구청장(이|은|은\s*누구|가\s*누구| 이름)?"),
    re.compile(r"(who\s+is\s+)?(the\s+)?(current\s+)?(buk[- ]?gu\s+)?mayor"),
    re.compile(r"구청장\s*(성함|성명|이름|누구)"),
    re.compile(r"지금\s*구청장"),
)

# Jurisdiction / organization name.
_JURISDICTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(관할|관할\s*구역|행정\s*구역)\s*(이름|명칭)?"),
    re.compile(r"(기관|조직|공식)\s*(명칭|이름)"),
    re.compile(r"(북구청|북구)\s*(공식\s*)?(이름|명칭|기관명)"),
    re.compile(r"(jurisdiction|organization)\s*(name)?"),
    re.compile(r"이\s*사이트가\s*어디\s*기관"),
)


def classify_question(question: str) -> ClassificationResult:
    """Classify a resident question into a supported time-sensitive fact.

    Returns ``supported=False`` for anything outside the Phase-1 vocabulary
    (weather, arbitrary web search, procedures, etc.).
    """
    normalized = _normalize(question)
    if not normalized:
        return ClassificationResult(
            supported=False,
            fact_kind=None,
            reason="empty_question",
            normalized_question=normalized,
        )

    for pattern in _MAYOR_PATTERNS:
        if pattern.search(normalized):
            return ClassificationResult(
                supported=True,
                fact_kind=FactKind.CURRENT_MAYOR,
                reason="matched_current_mayor",
                normalized_question=normalized,
            )

    for pattern in _JURISDICTION_PATTERNS:
        if pattern.search(normalized):
            return ClassificationResult(
                supported=True,
                fact_kind=FactKind.JURISDICTION_NAME,
                reason="matched_jurisdiction_name",
                normalized_question=normalized,
            )

    return ClassificationResult(
        supported=False,
        fact_kind=None,
        reason="unsupported_time_sensitive_fact",
        normalized_question=normalized,
    )


__all__ = [
    "ClassificationResult",
    "classify_question",
]
