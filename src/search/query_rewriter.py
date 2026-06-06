"""Query rewriter contract for dynamic retrieval.

Produces retrieval query candidates from a user question.
Does not generate answers. Does not call live providers.
Offline-safe, deterministic expansion for site search optimization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import re


@dataclass(frozen=True)
class QueryRewriteResult:
    """Result of query rewriting.

    Attributes:
        original_question: The exact user question, preserved unchanged.
        queries: Tuple of deduplicated retrieval query candidates (max max_queries).
        strategy: Name of the strategy used for expansion.
        warnings: Optional warnings (e.g., blank input).
    """
    original_question: str
    queries: tuple[str, ...]
    strategy: str
    warnings: tuple[str, ...] = ()


# Deterministic expansion rules
# Maps Korean question patterns to retrieval query terms.
# These are NOT answers — they are search terms for keyword matching.
_EXPANSION_RULES: tuple[tuple[re.Pattern, tuple[str, ...]], ...] = (
    # Mayor / chief official questions
    (
        re.compile(r"구청장|시청장|군수|도지사|청장.*누구|청장.*이름|청장.*프로필|열린.*청장"),
        ("구청장", "북구청장", "구청장 인사말", "구청장 프로필", "열린구청장", "북구청장 소개"),
    ),
    # Youth / jobs questions
    (
        re.compile(r"청년|일자리|채용|고용|취업|알바|아르바이트"),
        ("청년", "일자리", "청년 일자리", "채용", "고용", "경제", "비즈광주북구"),
    ),
    # Civil service / application questions
    (
        re.compile(r"민원|신청|접수|서류|발급|증명|여권|인감|가족관계"),
        ("민원", "민원 신청", "온라인 민원", "종합민원", "민원서식"),
    ),
    # Notice / announcement questions
    (
        re.compile(r"고시|공고|공지|새소식|입법|예고|알림"),
        ("고시공고", "공지사항", "공고", "새소식"),
    ),
    # Information disclosure
    (
        re.compile(r"정보공개|공개청구|계약|예산|결산|재정"),
        ("정보공개", "계약정보", "예산", "재정"),
    ),
    # Welfare / support
    (
        re.compile(r"복지|지원|보조|지원금|기초|수급|장애|노인|아동"),
        ("복지", "지원", "복지 지원", "지원금", "기초수급"),
    ),
    # Education / training
    (
        re.compile(r"교육|강좌|수강|평생교육|프로그램|신청"),
        ("교육", "교육접수", "평생교육", "강좌", "프로그램"),
    ),
)


def _normalize_text(text: str) -> str:
    """Normalize text for matching: lowercase, strip particles."""
    if not text:
        return ""
    text = text.strip().lower()
    # Remove common Korean particles from end
    particles = (
        "에서", "에게", "한테", "께서", "께서", "은", "는", "이", "가",
        "을", "를", "에", "의", "로", "으로", "와", "과", "도", "만"
    )
    for p in particles:
        if text.endswith(p) and len(text) > len(p):
            text = text[:-len(p)]
            break
    return text


def _deduplicate_preserve_order(items: Sequence[str]) -> list[str]:
    """Deduplicate while preserving first occurrence order."""
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def rewrite_query_candidates(
    question: str,
    *,
    site_id: str | None = None,
    max_queries: int = 5,
) -> QueryRewriteResult:
    """Generate retrieval query candidates from a user question.

    This is an offline-safe, deterministic function that expands
    a natural language question into search terms for keyword-based
    retrieval. It does NOT call live providers or generate answers.

    Args:
        question: The user's original question.
        site_id: Optional site identifier (reserved for future site-specific rules).
        max_queries: Maximum number of query candidates to return.

    Returns:
        QueryRewriteResult with original question, query candidates,
        strategy name, and any warnings.
    """
    original = question or ""
    normalized = _normalize_text(original)
    warnings: list[str] = []

    if not normalized:
        return QueryRewriteResult(
            original_question=original,
            queries=(),
            strategy="empty",
            warnings=("blank question provided",),
        )

    candidates = [normalized]

    # Apply expansion rules
    for pattern, expansions in _EXPANSION_RULES:
        if pattern.search(normalized):
            candidates.extend(expansions)

    # Deduplicate while preserving order
    candidates = _deduplicate_preserve_order(candidates)

    # Limit to max_queries
    if len(candidates) > max_queries:
        candidates = candidates[:max_queries]

    return QueryRewriteResult(
        original_question=original,
        queries=tuple(candidates),
        strategy="deterministic_v1",
        warnings=tuple(warnings),
    )