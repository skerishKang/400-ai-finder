"""Routing for deterministic journeys vs current-information search.

Mirrors MVP ``classifyAction`` term sets as a read-only Python mirror.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .aliases import resolve_aliases
from .classification import classify_question
from .models import (
    FactKind,
    QueryRoute,
    RequestContext,
    SearchScope,
    TemporalMode,
    TemporalPrecision,
)

_WS_RE = re.compile(r"\s+")

# #1215 — indirect litter-dumping classification cues. Used only by
# ``_classify_indirect_litter`` after the explicit ``_JOURNEY_RULES`` loop.
_LITTER_TARGET_CUES = (
    "쓰레기",
    "폐기물",
    "종량제봉투",
    "쓰레기봉투",
)

_LITTER_DUMPING_CUES = (
    "몰래 버",
    "버리고 갔",
    "버렸",
    "두고 도망",
    "두고 갔",
)

_LITTER_INTENT_CUES = (
    "신고",
    "민원",
    "제보",
)

_LITTER_COLLECTION_COMPLAINT_CUES = (
    "수거가 안",
    "수거 안",
    "가져가지 않",
    "수거 일정",
)

_JOURNEY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("illegal_parking", ("불법 주정차", "불법주정차", "주차 단속", "주정차 신고")),
    ("housing_department", ("공동주택", "아파트 부서", "아파트 문의")),
    ("bulky_waste", ("대형폐기물", "매트리스", "가구 버리", "침대 버리")),
    ("passport_guidance", ("여권",)),
    ("unmanned_kiosk", ("무인민원발급기", "무인 발급기")),
    ("streetlight_report", ("가로등 고장", "가로등 신고", "가로등이 고장")),
    ("litter_ai_assist", ("쓰레기 무단투기", "무단 투기 신고", "방치 쓰레기 신고")),
    (
        "mayor_message_assist",
        ("구청장에게 제안", "구청장 제안", "제안하고 싶어", "구청장 바란다"),
    ),
)

_VOLATILE_CUES: tuple[tuple[re.Pattern[str], FactKind], ...] = (
    (re.compile(r"수수료|요금|비용"), FactKind.FEE),
    (re.compile(r"운영\s*시간|근무\s*시간|몇\s*시|휴무|휴관"), FactKind.OFFICE_HOURS),
    (re.compile(r"전화|연락처|담당\s*부서|문의처"), FactKind.CONTACT_INFORMATION),
    (re.compile(r"접수\s*기간|신청\s*기간|마감"), FactKind.APPLICATION_PERIOD),
    (re.compile(r"조례|법령|법률"), FactKind.CURRENT_LAW),
    (re.compile(r"정책"), FactKind.CURRENT_POLICY),
    (re.compile(r"공고|고시"), FactKind.CURRENT_NOTICE),
    (re.compile(r"행사|축제"), FactKind.CURRENT_EVENT),
)


@dataclass(frozen=True)
class RoutingDecision:
    route: QueryRoute
    journey_action: str | None
    fact_kind: FactKind | None
    current_information_required: bool
    needs_freshness_enrichment: bool
    search_scope: SearchScope
    reason: str
    historical: bool
    temporal_mode: TemporalMode
    as_of_date: str | None
    as_of_year: int | None
    temporal_precision: TemporalPrecision
    matched_aliases: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route.value,
            "journey_action": self.journey_action,
            "fact_kind": self.fact_kind.value if self.fact_kind else None,
            "current_information_required": self.current_information_required,
            "needs_freshness_enrichment": self.needs_freshness_enrichment,
            "search_scope": self.search_scope.value,
            "reason": self.reason,
            "historical": self.historical,
            "temporal_mode": self.temporal_mode.value,
            "as_of_date": self.as_of_date,
            "as_of_year": self.as_of_year,
            "temporal_precision": self.temporal_precision.value,
            "matched_aliases": list(self.matched_aliases),
        }


def classify_journey_action(question: str) -> str | None:
    if not isinstance(question, str):
        return None
    normalized = _WS_RE.sub(" ", question.strip().lower())
    if not normalized:
        return None
    for action, terms in _JOURNEY_RULES:
        for term in terms:
            if term.lower() in normalized:
                return action
    return _classify_indirect_litter(normalized)


def _classify_indirect_litter(normalized: str) -> str | None:
    # #1215 — indirect litter-dumping detection. Runs only after the explicit
    # ``_JOURNEY_RULES`` loop misses, so explicit terms always win. Requires a
    # target cue (waste), a dumping cue (surreptitious/abandoned act), and an
    # intent cue (report/complaint). Collection complaints (sorted waste not
    # yet collected) are explicitly excluded even if all three cues match.
    has_target = any(cue in normalized for cue in _LITTER_TARGET_CUES)
    has_dumping = any(cue in normalized for cue in _LITTER_DUMPING_CUES)
    has_intent = any(cue in normalized for cue in _LITTER_INTENT_CUES)

    if not (has_target and has_dumping and has_intent):
        return None

    if any(cue in normalized for cue in _LITTER_COLLECTION_COMPLAINT_CUES):
        return None

    return "litter_ai_assist"


def _volatile_fact_kind(normalized: str) -> FactKind | None:
    for pattern, kind in _VOLATILE_CUES:
        if pattern.search(normalized):
            return kind
    return None


def _looks_like_general_current(normalized: str) -> bool:
    if not normalized:
        return False
    cues = ("날씨", "선거", "투표", "오늘", "현재", "지금", "최신", "weather", "current")
    return any(c in normalized for c in cues)


def route_question(
    question: str,
    context: RequestContext | None = None,
) -> RoutingDecision:
    aliases = resolve_aliases(question if isinstance(question, str) else "")
    journey = classify_journey_action(question) if isinstance(question, str) else None
    classification = classify_question(question)
    normalized = (
        _WS_RE.sub(" ", question.strip().lower()) if isinstance(question, str) else ""
    )
    volatile = _volatile_fact_kind(normalized) if normalized else None
    temporal_mode = aliases.temporal_mode
    historical = aliases.historical

    def _base(**kwargs: Any) -> RoutingDecision:
        defaults = dict(
            historical=historical,
            temporal_mode=temporal_mode,
            as_of_date=aliases.as_of_date,
            as_of_year=aliases.as_of_year,
            temporal_precision=aliases.temporal_precision,
            matched_aliases=aliases.matched_aliases,
        )
        defaults.update(kwargs)
        return RoutingDecision(**defaults)  # type: ignore[arg-type]

    if journey is not None:
        enrich = volatile is not None and not historical
        return _base(
            route=QueryRoute.DETERMINISTIC_JOURNEY,
            journey_action=journey,
            fact_kind=volatile if enrich else None,
            current_information_required=enrich,
            needs_freshness_enrichment=enrich,
            search_scope=(
                SearchScope.OFFICIAL_THEN_GENERAL if enrich else SearchScope.NONE
            ),
            reason="matched_deterministic_journey",
        )

    if historical and (
        classification.supported or aliases.preferred_fact_kind is not None
    ):
        kind = classification.fact_kind or aliases.preferred_fact_kind
        return _base(
            route=QueryRoute.OFFICIAL_FRESHNESS_SEARCH,
            journey_action=None,
            fact_kind=kind,
            current_information_required=True,
            needs_freshness_enrichment=False,
            search_scope=SearchScope.OFFICIAL_THEN_GENERAL,
            reason="historical_fact_search",
        )

    if classification.supported and classification.fact_kind is not None:
        if classification.fact_kind is FactKind.GENERAL_CURRENT_INFORMATION:
            route = QueryRoute.GENERAL_WEB_SEARCH
        else:
            route = QueryRoute.OFFICIAL_FRESHNESS_SEARCH
        return _base(
            route=route,
            journey_action=None,
            fact_kind=classification.fact_kind,
            current_information_required=True,
            needs_freshness_enrichment=False,
            search_scope=SearchScope.OFFICIAL_THEN_GENERAL,
            reason=classification.reason or "matched_current_fact",
        )

    if aliases.force_current_entity and aliases.preferred_fact_kind is not None:
        return _base(
            route=QueryRoute.OFFICIAL_FRESHNESS_SEARCH,
            journey_action=None,
            fact_kind=aliases.preferred_fact_kind,
            current_information_required=True,
            needs_freshness_enrichment=False,
            search_scope=SearchScope.OFFICIAL_THEN_GENERAL,
            reason="alias_current_entity",
        )

    if volatile is not None or _looks_like_general_current(normalized):
        kind = volatile or FactKind.GENERAL_CURRENT_INFORMATION
        return _base(
            route=QueryRoute.GENERAL_WEB_SEARCH,
            journey_action=None,
            fact_kind=kind,
            current_information_required=True,
            needs_freshness_enrichment=False,
            search_scope=SearchScope.OFFICIAL_THEN_GENERAL,
            reason="general_current_information",
        )

    return _base(
        route=QueryRoute.SAFE_UNSUPPORTED,
        journey_action=None,
        fact_kind=None,
        current_information_required=bool(
            context.current_information_required if context else False
        ),
        needs_freshness_enrichment=False,
        search_scope=SearchScope.NONE,
        reason="safe_unsupported",
    )


__all__ = [
    "RoutingDecision",
    "classify_journey_action",
    "route_question",
]
