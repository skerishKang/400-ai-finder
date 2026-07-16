"""Current-information pipeline: route + official-first search + fail-closed.

Never fills current facts from model memory or hard-coded civic constants.
"""

from __future__ import annotations

from dataclasses import replace

from .freshness import InvalidTimestampError, assess_freshness
from .models import (
    Clock,
    CurrentInformationAnswer,
    CurrentInformationSource,
    ErrorCode,
    FactKind,
    FreshnessStatus,
    InvalidTimezoneError,
    QueryRoute,
    RequestContext,
    RetrievalPolicy,
    SearchScope,
    SourceType,
    TemporalMode,
    TemporalPrecision,
    build_request_context,
    failed_current_answer,
    public_message_for,
)
from .routing import RoutingDecision, route_question
from .search_providers import (
    CurrentInfoSearchRequest,
    MockGeneralWebSearchProvider,
    MockOfficialSearchProvider,
    OfficialFirstSearchOrchestrator,
    SearchHit,
)


class CurrentInformationPipeline:
    """Mock-only current-information orchestrator (#1150 hardened)."""

    def __init__(
        self,
        *,
        orchestrator: OfficialFirstSearchOrchestrator | None = None,
        clock: Clock | None = None,
        timezone_name: str = "Asia/Seoul",
    ) -> None:
        if orchestrator is not None:
            self._orchestrator = orchestrator
        else:
            self._orchestrator = OfficialFirstSearchOrchestrator(
                official=MockOfficialSearchProvider(),
                general=MockGeneralWebSearchProvider(),
                allow_general=True,
            )
        self._clock = clock
        self._timezone_name = timezone_name

    @property
    def orchestrator(self) -> OfficialFirstSearchOrchestrator:
        return self._orchestrator

    def answer(
        self,
        question: str,
        *,
        request_context: RequestContext | None = None,
        evaluated_at: str | None = None,
        timezone_name: str | None = None,
    ) -> CurrentInformationAnswer:
        tz = timezone_name or self._timezone_name
        try:
            base_ctx = request_context or build_request_context(
                clock=self._clock,
                evaluated_at=evaluated_at,
                timezone_name=tz,
            )
        except InvalidTimezoneError:
            return failed_current_answer(
                failure_code=ErrorCode.INVALID_TIMEZONE,
                query_type="invalid_timezone",
                route=QueryRoute.SAFE_UNSUPPORTED,
            )

        decision = route_question(question, base_ctx)
        effective = self._effective_context(base_ctx, decision)
        return self._answer_for_decision(question, effective, decision)

    def _effective_context(
        self, base: RequestContext, decision: RoutingDecision
    ) -> RequestContext:
        policy = base.retrieval_policy
        if decision.search_scope is not SearchScope.NONE:
            policy = replace(policy, search_scope=decision.search_scope)
        return replace(
            base,
            current_information_required=decision.current_information_required
            or decision.route
            in (
                QueryRoute.OFFICIAL_FRESHNESS_SEARCH,
                QueryRoute.GENERAL_WEB_SEARCH,
            )
            or decision.needs_freshness_enrichment,
            historical_reference=decision.historical,
            temporal_mode=decision.temporal_mode,
            as_of_date=decision.as_of_date,
            as_of_year=decision.as_of_year,
            temporal_precision=decision.temporal_precision,
            retrieval_policy=policy,
        )

    def _answer_for_decision(
        self,
        question: str,
        ctx: RequestContext,
        decision: RoutingDecision,
    ) -> CurrentInformationAnswer:
        ctx_dict = ctx.to_dict()

        if decision.route is QueryRoute.DETERMINISTIC_JOURNEY:
            if not decision.needs_freshness_enrichment:
                return CurrentInformationAnswer(
                    ok=True,
                    answer=(
                        f"안내 경로로 연결합니다. (action={decision.journey_action})"
                    ),
                    query_type="deterministic_journey",
                    fact_kind=None,
                    source_type=SourceType.JOURNEY,
                    search_scope=SearchScope.NONE,
                    warnings=("journey_only_no_current_fact_claim",),
                    route=QueryRoute.DETERMINISTIC_JOURNEY,
                    journey_action=decision.journey_action,
                    journey_preserved=True,
                    temporal_mode=ctx.temporal_mode,
                    as_of_date=ctx.as_of_date,
                    as_of_year=ctx.as_of_year,
                    temporal_precision=ctx.temporal_precision,
                    request_context=ctx_dict,
                )

            enriched = self._retrieve(
                question,
                ctx,
                fact_kind=decision.fact_kind,
                attempted_route=QueryRoute.DETERMINISTIC_JOURNEY,
                query_type="deterministic_journey_with_freshness",
                journey_action=decision.journey_action,
            )
            if not enriched.ok:
                return CurrentInformationAnswer(
                    ok=True,
                    answer=(
                        f"안내 경로로 연결합니다. (action={decision.journey_action}) "
                        f"변동 가능 사실 검증에 실패했습니다. "
                        f"({public_message_for(enriched.failure_code)})"
                    ),
                    query_type="deterministic_journey_with_freshness",
                    fact_kind=decision.fact_kind,
                    source_type=SourceType.JOURNEY,
                    search_scope=decision.search_scope,
                    warnings=(
                        "freshness_enrichment_failed",
                        "no_model_memory_fill",
                    ),
                    failure_code=enriched.failure_code,
                    route=QueryRoute.DETERMINISTIC_JOURNEY,
                    journey_action=decision.journey_action,
                    journey_preserved=True,
                    enrichment_fact_kind=decision.fact_kind,
                    enrichment_value=None,
                    temporal_mode=ctx.temporal_mode,
                    as_of_date=ctx.as_of_date,
                    as_of_year=ctx.as_of_year,
                    temporal_precision=ctx.temporal_precision,
                    request_context=ctx_dict,
                )
            # Preserve journey guidance + attach enrichment fact/sources
            journey_line = f"안내 경로로 연결합니다. (action={decision.journey_action})"
            fact_line = enriched.answer
            return CurrentInformationAnswer(
                ok=True,
                answer=f"{journey_line} | 검증된 부가 사실: {fact_line}",
                query_type="deterministic_journey_with_freshness",
                fact_kind=enriched.fact_kind,
                current_as_of=enriched.current_as_of,
                retrieved_at=enriched.retrieved_at,
                freshness_status=enriched.freshness_status,
                source_url=enriched.source_url,
                source_title=enriched.source_title,
                source_type=enriched.source_type,
                search_scope=enriched.search_scope,
                sources=enriched.sources,
                warnings=("journey_preserved_with_freshness_enrichment",),
                route=QueryRoute.DETERMINISTIC_JOURNEY,
                journey_action=decision.journey_action,
                journey_preserved=True,
                enrichment_fact_kind=enriched.fact_kind,
                enrichment_value=enriched.value,
                value=enriched.value,
                temporal_mode=ctx.temporal_mode,
                as_of_date=ctx.as_of_date,
                as_of_year=ctx.as_of_year,
                temporal_precision=ctx.temporal_precision,
                request_context=ctx_dict,
            )

        if decision.route is QueryRoute.SAFE_UNSUPPORTED:
            return failed_current_answer(
                failure_code=ErrorCode.UNSUPPORTED_QUESTION,
                query_type="safe_unsupported",
                route=QueryRoute.SAFE_UNSUPPORTED,
                request_context=ctx_dict,
                temporal_mode=ctx.temporal_mode,
                as_of_date=ctx.as_of_date,
                as_of_year=ctx.as_of_year,
                temporal_precision=ctx.temporal_precision,
            )

        if decision.route in (
            QueryRoute.OFFICIAL_FRESHNESS_SEARCH,
            QueryRoute.GENERAL_WEB_SEARCH,
        ):
            return self._retrieve(
                question,
                ctx,
                fact_kind=decision.fact_kind,
                attempted_route=decision.route,
                query_type=decision.route.value,
                journey_action=None,
            )

        return failed_current_answer(
            failure_code=ErrorCode.INTERNAL_ERROR,
            query_type="unknown_route",
            route=QueryRoute.SAFE_UNSUPPORTED,
            request_context=ctx_dict,
        )

    def _retrieve(
        self,
        question: str,
        ctx: RequestContext,
        *,
        fact_kind: FactKind | None,
        attempted_route: QueryRoute,
        query_type: str,
        journey_action: str | None,
    ) -> CurrentInformationAnswer:
        ctx_dict = ctx.to_dict()
        if fact_kind is None:
            return failed_current_answer(
                failure_code=ErrorCode.INVALID_REQUEST,
                query_type=query_type,
                route=attempted_route,
                journey_action=journey_action,
                journey_preserved=journey_action is not None,
                search_scope=ctx.retrieval_policy.search_scope,
                request_context=ctx_dict,
                temporal_mode=ctx.temporal_mode,
                as_of_date=ctx.as_of_date,
                as_of_year=ctx.as_of_year,
                temporal_precision=ctx.temporal_precision,
            )

        search_req = CurrentInfoSearchRequest(
            question=question,
            fact_kind=fact_kind,
            temporal_mode=ctx.temporal_mode,
            as_of_date=ctx.as_of_date,
            as_of_year=ctx.as_of_year,
            temporal_precision=ctx.temporal_precision,
            request_started_at_utc=ctx.request_started_at_utc,
            timezone=ctx.timezone,
            search_scope=ctx.retrieval_policy.search_scope,
        )
        result, _source_type = self._orchestrator.search(search_req)
        if not result.ok or not result.hits:
            code = result.failure_code or ErrorCode.RETRIEVAL_FAILED
            return failed_current_answer(
                failure_code=code,
                query_type=query_type,
                route=attempted_route,  # preserve attempted route
                fact_kind=fact_kind,
                answer=public_message_for(code),
                warnings=("no_model_memory_fill", "retrieval_failed"),
                search_scope=ctx.retrieval_policy.search_scope,
                journey_action=journey_action,
                journey_preserved=journey_action is not None,
                temporal_mode=ctx.temporal_mode,
                as_of_date=ctx.as_of_date,
                as_of_year=ctx.as_of_year,
                temporal_precision=ctx.temporal_precision,
                request_context=ctx_dict,
            )

        hit = result.hits[0]
        # Second-pass integrity at pipeline (defense in depth)
        from .search_providers import validate_hit_integrity

        provider_type = hit.source_type
        integrity = validate_hit_integrity(
            hit,
            search_req,
            provider_source_type=provider_type,
            provider_name=hit.provider_name or result.provider_name,
        )
        if integrity is not None:
            return failed_current_answer(
                failure_code=integrity,
                query_type=query_type,
                route=attempted_route,
                fact_kind=fact_kind,
                warnings=("hit_integrity_failed", "no_model_memory_fill"),
                search_scope=ctx.retrieval_policy.search_scope,
                journey_action=journey_action,
                journey_preserved=journey_action is not None,
                temporal_mode=ctx.temporal_mode,
                as_of_date=ctx.as_of_date,
                as_of_year=ctx.as_of_year,
                temporal_precision=ctx.temporal_precision,
                request_context=ctx_dict,
            )

        # Freshness of retrieval timestamp (age) — only for CURRENT mode claims.
        if ctx.temporal_mode is TemporalMode.CURRENT:
            try:
                assessment = assess_freshness(
                    retrieved_at=hit.retrieved_at,
                    max_age_seconds=ctx.retrieval_policy.max_age_seconds,
                    evaluated_at=ctx.request_started_at_utc,
                )
            except InvalidTimestampError:
                return failed_current_answer(
                    failure_code=ErrorCode.INVALID_TIMESTAMP,
                    query_type=query_type,
                    route=attempted_route,
                    fact_kind=fact_kind,
                    warnings=("invalid_retrieved_at",),
                    search_scope=ctx.retrieval_policy.search_scope,
                    journey_action=journey_action,
                    journey_preserved=journey_action is not None,
                    temporal_mode=ctx.temporal_mode,
                    request_context=ctx_dict,
                )
            if assessment.status is FreshnessStatus.STALE:
                return failed_current_answer(
                    failure_code=ErrorCode.STALE_SOURCE,
                    query_type=query_type,
                    route=attempted_route,
                    fact_kind=fact_kind,
                    answer=public_message_for(ErrorCode.STALE_SOURCE),
                    warnings=("stale_not_presented_as_current", "no_model_memory_fill"),
                    search_scope=ctx.retrieval_policy.search_scope,
                    journey_action=journey_action,
                    journey_preserved=journey_action is not None,
                    temporal_mode=ctx.temporal_mode,
                    request_context=ctx_dict,
                )
            freshness = FreshnessStatus.VERIFIED_CURRENT
            current_as_of = ctx.request_started_at_utc
        else:
            # Historical: never verified_current
            freshness = FreshnessStatus.VERIFIED_AS_OF
            current_as_of = None

        source_rec = CurrentInformationSource(
            url=hit.source_url,
            title=hit.source_title,
            source_type=hit.source_type,
            retrieved_at=hit.retrieved_at,
            provider_name=hit.provider_name or result.provider_name,
            rank=hit.rank,
            snippet=hit.snippet,
        )
        sources = (source_rec,)

        # Verified success contract
        if not sources or not source_rec.url or not source_rec.title:
            return failed_current_answer(
                failure_code=ErrorCode.NO_VERIFIED_SOURCE,
                query_type=query_type,
                route=attempted_route,
                fact_kind=fact_kind,
                request_context=ctx_dict,
                temporal_mode=ctx.temporal_mode,
            )
        if source_rec.source_type in (SourceType.NONE, SourceType.JOURNEY):
            return failed_current_answer(
                failure_code=ErrorCode.INVALID_SOURCE_METADATA,
                query_type=query_type,
                route=attempted_route,
                fact_kind=fact_kind,
                request_context=ctx_dict,
                temporal_mode=ctx.temporal_mode,
            )
        if ctx.temporal_mode is TemporalMode.HISTORICAL and (
            ctx.as_of_date is None and ctx.as_of_year is None
        ):
            return failed_current_answer(
                failure_code=ErrorCode.TEMPORAL_SCOPE_MISMATCH,
                query_type=query_type,
                route=attempted_route,
                fact_kind=fact_kind,
                request_context=ctx_dict,
                temporal_mode=ctx.temporal_mode,
            )

        answer_text = self._format_answer(hit, ctx, freshness)
        return CurrentInformationAnswer(
            ok=True,
            answer=answer_text,
            query_type=query_type,
            fact_kind=hit.fact_kind,
            current_as_of=current_as_of,
            retrieved_at=hit.retrieved_at,
            freshness_status=freshness,
            source_url=source_rec.url,
            source_title=source_rec.title,
            source_type=source_rec.source_type,
            search_scope=ctx.retrieval_policy.search_scope,
            sources=sources,
            warnings=(),
            failure_code=None,
            route=attempted_route,
            journey_action=journey_action,
            journey_preserved=journey_action is not None,
            enrichment_fact_kind=hit.fact_kind if journey_action else None,
            enrichment_value=hit.value if journey_action else None,
            value=hit.value,
            temporal_mode=ctx.temporal_mode,
            as_of_date=ctx.as_of_date,
            as_of_year=ctx.as_of_year,
            temporal_precision=ctx.temporal_precision,
            request_context=ctx_dict,
        )

    @staticmethod
    def _format_answer(
        hit: SearchHit,
        ctx: RequestContext,
        freshness: FreshnessStatus,
    ) -> str:
        title = hit.source_title or "출처"
        if ctx.temporal_mode is TemporalMode.HISTORICAL:
            as_of_label = ctx.as_of_date or (
                str(ctx.as_of_year) if ctx.as_of_year is not None else "unknown"
            )
            precision = ctx.temporal_precision.value
            return (
                f"{hit.value} "
                f"(출처: {title}, {hit.source_url}, "
                f"검색 시각: {hit.retrieved_at}, "
                f"기준 시점: {as_of_label}, precision={precision}, "
                f"status={freshness.value})"
            )
        return (
            f"{hit.value} "
            f"(출처: {title}, {hit.source_url}, "
            f"검색 시각: {hit.retrieved_at}, "
            f"기준 시각: {ctx.request_started_at_utc}, "
            f"status={freshness.value})"
        )


def assert_no_hallucinated_names(
    answer: CurrentInformationAnswer,
    *,
    forbidden_names: tuple[str, ...] = (),
) -> None:
    if not answer.ok:
        for name in forbidden_names:
            assert name not in (answer.answer or "")
            assert name != answer.value
        return
    for name in forbidden_names:
        if name == answer.value:
            continue
        assert name not in (answer.answer or "")


__all__ = [
    "CurrentInformationPipeline",
    "assert_no_hallucinated_names",
]
