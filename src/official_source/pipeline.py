"""Current-information pipeline: route + official-first search + fail-closed.

Never fills current facts from model memory or hard-coded civic constants.
Default providers are empty mocks (fail closed until tests inject hits).
"""

from __future__ import annotations

from typing import Callable
from datetime import datetime

from .freshness import InvalidTimestampError, assess_freshness
from .models import (
    Clock,
    CurrentInformationAnswer,
    ErrorCode,
    FactKind,
    FreshnessStatus,
    QueryRoute,
    RequestContext,
    SearchScope,
    SourceType,
    build_request_context,
    failed_current_answer,
    public_message_for,
)
from .routing import RoutingDecision, route_question
from .search_providers import (
    MockGeneralWebSearchProvider,
    MockOfficialSearchProvider,
    OfficialFirstSearchOrchestrator,
    SearchHit,
)


class CurrentInformationPipeline:
    """Mock-only current-information orchestrator (#1150 expanded)."""

    def __init__(
        self,
        *,
        orchestrator: OfficialFirstSearchOrchestrator | None = None,
        clock: Clock | None = None,
    ) -> None:
        if orchestrator is not None:
            self._orchestrator = orchestrator
        else:
            # Empty mocks: no hits configured → retrieval fails closed.
            self._orchestrator = OfficialFirstSearchOrchestrator(
                official=MockOfficialSearchProvider(),
                general=MockGeneralWebSearchProvider(),
                allow_general=True,
            )
        self._clock = clock

    @property
    def orchestrator(self) -> OfficialFirstSearchOrchestrator:
        return self._orchestrator

    def answer(
        self,
        question: str,
        *,
        request_context: RequestContext | None = None,
        evaluated_at: str | None = None,
    ) -> CurrentInformationAnswer:
        ctx = request_context or build_request_context(
            clock=self._clock,
            evaluated_at=evaluated_at,
        )
        decision = route_question(question, ctx)
        return self._answer_for_decision(question, ctx, decision)

    def _answer_for_decision(
        self,
        question: str,
        ctx: RequestContext,
        decision: RoutingDecision,
    ) -> CurrentInformationAnswer:
        if decision.route is QueryRoute.DETERMINISTIC_JOURNEY:
            if not decision.needs_freshness_enrichment:
                return CurrentInformationAnswer(
                    ok=True,
                    answer=(
                        f"안내 경로로 연결합니다. (action={decision.journey_action})"
                    ),
                    query_type="deterministic_journey",
                    fact_kind=None,
                    current_as_of=None,
                    retrieved_at=None,
                    freshness_status=FreshnessStatus.UNKNOWN,
                    source_url=None,
                    source_title=None,
                    source_type=SourceType.JOURNEY,
                    search_scope=SearchScope.NONE,
                    warnings=("journey_only_no_current_fact_claim",),
                    failure_code=None,
                    route=QueryRoute.DETERMINISTIC_JOURNEY,
                    journey_action=decision.journey_action,
                    value=None,
                )
            # Journey + volatile fact enrichment
            enriched = self._retrieve_current_fact(
                question,
                ctx,
                fact_kind=decision.fact_kind,
                route=QueryRoute.DETERMINISTIC_JOURNEY,
                query_type="deterministic_journey_with_freshness",
                journey_action=decision.journey_action,
            )
            if not enriched.ok:
                # Do not invent fees/hours from memory; keep journey but warn.
                return CurrentInformationAnswer(
                    ok=True,
                    answer=(
                        f"안내 경로는 유지합니다. 변동 가능 사실 검증에 실패했습니다. "
                        f"({public_message_for(enriched.failure_code)})"
                    ),
                    query_type="deterministic_journey_with_freshness",
                    fact_kind=decision.fact_kind,
                    current_as_of=None,
                    retrieved_at=None,
                    freshness_status=FreshnessStatus.UNKNOWN,
                    source_url=None,
                    source_title=None,
                    source_type=SourceType.JOURNEY,
                    search_scope=decision.search_scope,
                    warnings=(
                        "freshness_enrichment_failed",
                        "no_model_memory_fill",
                    ),
                    failure_code=enriched.failure_code,
                    route=QueryRoute.DETERMINISTIC_JOURNEY,
                    journey_action=decision.journey_action,
                    value=None,
                )
            return enriched

        if decision.route is QueryRoute.SAFE_UNSUPPORTED:
            return failed_current_answer(
                failure_code=ErrorCode.UNSUPPORTED_QUESTION,
                query_type="safe_unsupported",
                route=QueryRoute.SAFE_UNSUPPORTED,
                fact_kind=None,
            )

        if decision.route in (
            QueryRoute.OFFICIAL_FRESHNESS_SEARCH,
            QueryRoute.GENERAL_WEB_SEARCH,
        ):
            return self._retrieve_current_fact(
                question,
                ctx,
                fact_kind=decision.fact_kind,
                route=decision.route,
                query_type=decision.route.value,
                journey_action=None,
            )

        return failed_current_answer(
            failure_code=ErrorCode.INTERNAL_ERROR,
            query_type="unknown_route",
            route=QueryRoute.SAFE_UNSUPPORTED,
        )

    def _retrieve_current_fact(
        self,
        question: str,
        ctx: RequestContext,
        *,
        fact_kind: FactKind | None,
        route: QueryRoute,
        query_type: str,
        journey_action: str | None,
    ) -> CurrentInformationAnswer:
        evaluated_at = ctx.request_started_at_utc
        result, source_type = self._orchestrator.search(
            question, fact_kind=fact_kind, evaluated_at=evaluated_at
        )
        if not result.ok or not result.hits:
            return failed_current_answer(
                failure_code=ErrorCode.RETRIEVAL_FAILED,
                query_type=query_type,
                route=QueryRoute.SAFE_UNSUPPORTED
                if route is not QueryRoute.DETERMINISTIC_JOURNEY
                else route,
                fact_kind=fact_kind,
                answer=public_message_for(ErrorCode.RETRIEVAL_FAILED),
                warnings=("no_model_memory_fill", "retrieval_failed"),
                search_scope=SearchScope.OFFICIAL_THEN_GENERAL,
                journey_action=journey_action,
            )

        hit = result.hits[0]
        # Stale / invalid timestamps cannot be presented as verified_current.
        try:
            assessment = assess_freshness(
                retrieved_at=hit.retrieved_at,
                max_age_seconds=ctx.retrieval_policy.max_age_seconds,
                evaluated_at=evaluated_at,
            )
        except InvalidTimestampError:
            return failed_current_answer(
                failure_code=ErrorCode.INVALID_TIMESTAMP,
                query_type=query_type,
                route=QueryRoute.SAFE_UNSUPPORTED,
                fact_kind=fact_kind,
                warnings=("invalid_retrieved_at",),
                search_scope=SearchScope.OFFICIAL_THEN_GENERAL,
                journey_action=journey_action,
            )

        if assessment.status is FreshnessStatus.STALE:
            return failed_current_answer(
                failure_code=ErrorCode.STALE_SOURCE,
                query_type=query_type,
                route=QueryRoute.SAFE_UNSUPPORTED,
                fact_kind=fact_kind,
                answer=public_message_for(ErrorCode.STALE_SOURCE),
                warnings=("stale_not_presented_as_current",),
                search_scope=SearchScope.OFFICIAL_THEN_GENERAL,
                journey_action=journey_action,
            )

        if assessment.status is FreshnessStatus.UNKNOWN or not hit.source_url:
            return failed_current_answer(
                failure_code=ErrorCode.NO_VERIFIED_SOURCE,
                query_type=query_type,
                route=QueryRoute.SAFE_UNSUPPORTED,
                fact_kind=fact_kind,
                warnings=("missing_source_or_timestamp",),
                search_scope=SearchScope.OFFICIAL_THEN_GENERAL,
                journey_action=journey_action,
            )

        if not hit.value or not str(hit.value).strip():
            return failed_current_answer(
                failure_code=ErrorCode.FACT_NOT_FOUND,
                query_type=query_type,
                route=QueryRoute.SAFE_UNSUPPORTED,
                fact_kind=fact_kind,
                journey_action=journey_action,
            )

        # Build answer text only from retrieved hit fields (no extra proper nouns).
        answer_text = self._format_answer(hit, evaluated_at)
        return CurrentInformationAnswer(
            ok=True,
            answer=answer_text,
            query_type=query_type,
            fact_kind=hit.fact_kind,
            current_as_of=evaluated_at,
            retrieved_at=hit.retrieved_at,
            freshness_status=FreshnessStatus.VERIFIED_CURRENT,
            source_url=hit.source_url,
            source_title=hit.source_title,
            source_type=source_type
            if source_type is not SourceType.NONE
            else hit.source_type,
            search_scope=SearchScope.OFFICIAL_THEN_GENERAL,
            warnings=(),
            failure_code=None,
            route=route,
            journey_action=journey_action,
            value=hit.value,
        )

    @staticmethod
    def _format_answer(hit: SearchHit, current_as_of: str) -> str:
        title = hit.source_title or "출처"
        return (
            f"{hit.value} "
            f"(출처: {title}, {hit.source_url}, "
            f"검색 시각: {hit.retrieved_at}, 기준 시각: {current_as_of})"
        )


def assert_no_hallucinated_names(
    answer: CurrentInformationAnswer,
    *,
    forbidden_names: tuple[str, ...] = (),
) -> None:
    """Test helper: successful answers may only contain retrieved value tokens.

    Forbidden names (e.g. fixture office-holders) must not appear unless they
    are exactly the retrieved ``value``.
    """
    if not answer.ok:
        for name in forbidden_names:
            assert name not in (answer.answer or ""), (
                f"failure answer must not leak name {name!r}"
            )
        return
    if not forbidden_names:
        return
    for name in forbidden_names:
        if name == answer.value:
            continue
        assert name not in (answer.answer or ""), (
            f"answer must not invent name {name!r} outside retrieved value"
        )


__all__ = [
    "CurrentInformationPipeline",
    "assert_no_hallucinated_names",
]
