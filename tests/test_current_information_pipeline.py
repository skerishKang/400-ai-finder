"""Hardened #1150 current-information pipeline contracts (mock/offline only)."""

from __future__ import annotations

import ast
import socket
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from src.official_source import (
    CurrentInformationPipeline,
    FactKind,
    FreshnessStatus,
    InvalidTimezoneError,
    MockGeneralWebSearchProvider,
    MockOfficialSearchProvider,
    OfficialFirstSearchOrchestrator,
    QueryRoute,
    SearchHit,
    SearchHitKey,
    SourceType,
    TemporalMode,
    TemporalPrecision,
    assert_no_hallucinated_names,
    build_request_context,
    classify_journey_action,
    classify_question,
    make_search_key,
    resolve_aliases,
    route_question,
)
from src.official_source.aliases import alias_table_for_tests, detect_historical_reference
from src.official_source.models import ErrorCode

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPO_ROOT / "src" / "official_source"

EVALUATED_AT = "2026-07-16T09:00:00Z"
FRESH_RETRIEVED_AT = "2026-07-16T08:30:00Z"
STALE_RETRIEVED_AT = "2026-01-01T08:30:00Z"
HIST_RETRIEVED_AT = "2026-07-16T08:00:00Z"

_MOCK_REGIONAL = "예시통합시장"
_MOCK_REGIONAL_2020 = "예시과거시장"
_MOCK_DISTRICT = "예시구청장"
_FORBIDDEN = ("민형배", "신수정", "전남광주통합특별시", "전남광주특별시")


def _key(
    kind: FactKind,
    mode: TemporalMode = TemporalMode.CURRENT,
    as_of: str | None = None,
) -> SearchHitKey:
    return SearchHitKey(kind, mode, as_of)


def _hit(
    kind: FactKind,
    value: str,
    *,
    source_type: SourceType = SourceType.OFFICIAL,
    url: str = "https://bukgu.gwangju.kr/mock-official",
    title: str = "mock official page",
    retrieved_at: str = FRESH_RETRIEVED_AT,
    temporal_mode: TemporalMode = TemporalMode.CURRENT,
    as_of_date: str | None = None,
    as_of_year: int | None = None,
    temporal_precision: TemporalPrecision = TemporalPrecision.UNSPECIFIED,
    provider_name: str = "",
) -> SearchHit:
    return SearchHit(
        fact_kind=kind,
        value=value,
        source_url=url,
        source_title=title,
        source_type=source_type,
        retrieved_at=retrieved_at,
        temporal_mode=temporal_mode,
        as_of_date=as_of_date,
        as_of_year=as_of_year,
        temporal_precision=temporal_precision,
        provider_name=provider_name,
    )


def _pipe(
    official: dict[SearchHitKey, SearchHit] | None = None,
    general: dict[SearchHitKey, SearchHit] | None = None,
) -> CurrentInformationPipeline:
    return CurrentInformationPipeline(
        orchestrator=OfficialFirstSearchOrchestrator(
            official=MockOfficialSearchProvider(official or {}),
            general=MockGeneralWebSearchProvider(general or {}),
            allow_general=True,
        )
    )


class TestNetworkFree:
    def test_import_and_pipeline_zero_network(self, monkeypatch):
        calls: list[object] = []

        def blocked(*a, **k):
            calls.append((a, k))
            raise AssertionError("network")

        monkeypatch.setattr(socket.socket, "connect", blocked)
        monkeypatch.setattr(socket.socket, "connect_ex", blocked)
        pipe = CurrentInformationPipeline()
        pipe.answer("불법 주정차 신고는 어디서 하나요?", evaluated_at=EVALUATED_AT)
        assert calls == []

    def test_no_network_imports(self):
        forbidden_modules = {
            "urllib.request",
            "urllib.client",
            "http.client",
            "requests",
            "httpx",
            "aiohttp",
            "firecrawl",
            "socket",
        }
        forbidden_roots = {"requests", "httpx", "aiohttp", "firecrawl"}
        for path in PACKAGE_DIR.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name not in forbidden_modules
                        assert alias.name.split(".")[0] not in forbidden_roots
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module not in forbidden_modules
                    assert node.module.split(".")[0] not in forbidden_roots


class TestTimezone:
    def test_asia_seoul(self):
        ctx = build_request_context(
            evaluated_at="2026-07-16T00:00:00Z", timezone_name="Asia/Seoul"
        )
        assert ctx.timezone == "Asia/Seoul"
        assert ctx.request_started_at_local.startswith("2026-07-16T09:00:00")
        assert "+09:00" in ctx.request_started_at_local

    def test_utc(self):
        ctx = build_request_context(
            evaluated_at="2026-07-16T12:00:00Z", timezone_name="UTC"
        )
        assert ctx.timezone == "UTC"
        assert "+00:00" in ctx.request_started_at_local or ctx.request_started_at_local.endswith(
            "+0000"
        ) or "12:00:00" in ctx.request_started_at_local

    def test_america_new_york(self):
        # July → EDT UTC-4
        ctx = build_request_context(
            evaluated_at="2026-07-16T12:00:00Z", timezone_name="America/New_York"
        )
        assert ctx.timezone == "America/New_York"
        assert "08:00:00" in ctx.request_started_at_local
        assert "-04:00" in ctx.request_started_at_local

    def test_invalid_timezone(self):
        with pytest.raises(InvalidTimezoneError):
            build_request_context(
                evaluated_at=EVALUATED_AT, timezone_name="Not/AZone"
            )

    def test_pipeline_invalid_timezone(self):
        pipe = CurrentInformationPipeline()
        ans = pipe.answer(
            "현재 북구청장은 누구인가요?",
            evaluated_at=EVALUATED_AT,
            timezone_name="Not/AZone",
        )
        assert ans.ok is False
        assert ans.failure_code is ErrorCode.INVALID_TIMEZONE


class TestTemporal:
    def test_current_regional_success(self):
        pipe = _pipe(
            {
                _key(FactKind.REGIONAL_EXECUTIVE): _hit(
                    FactKind.REGIONAL_EXECUTIVE, _MOCK_REGIONAL
                )
            }
        )
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok
        assert ans.temporal_mode is TemporalMode.CURRENT
        assert ans.freshness_status is FreshnessStatus.VERIFIED_CURRENT
        assert ans.current_as_of == EVALUATED_AT
        assert ans.value == _MOCK_REGIONAL
        assert ans.sources and ans.sources[0].url == ans.source_url

    def test_historical_matching_hit(self):
        pipe = _pipe(
            {
                _key(
                    FactKind.REGIONAL_EXECUTIVE, TemporalMode.HISTORICAL, "2020"
                ): _hit(
                    FactKind.REGIONAL_EXECUTIVE,
                    _MOCK_REGIONAL_2020,
                    temporal_mode=TemporalMode.HISTORICAL,
                    as_of_year=2020,
                    as_of_date="2020",
                    temporal_precision=TemporalPrecision.YEAR,
                    retrieved_at=HIST_RETRIEVED_AT,
                )
            }
        )
        ans = pipe.answer("2020년 당시 광주시장은 누구였나요?", evaluated_at=EVALUATED_AT)
        assert ans.ok
        assert ans.temporal_mode is TemporalMode.HISTORICAL
        assert ans.freshness_status is FreshnessStatus.VERIFIED_AS_OF
        assert ans.freshness_status is not FreshnessStatus.VERIFIED_CURRENT
        assert ans.as_of_year == 2020
        assert ans.temporal_precision is TemporalPrecision.YEAR
        assert ans.value == _MOCK_REGIONAL_2020
        assert ans.current_as_of is None

    def test_historical_plus_current_hit_only_fails(self):
        pipe = _pipe(
            {
                _key(FactKind.REGIONAL_EXECUTIVE): _hit(
                    FactKind.REGIONAL_EXECUTIVE, _MOCK_REGIONAL
                )
            }
        )
        ans = pipe.answer("2020년 당시 광주시장은 누구였나요?", evaluated_at=EVALUATED_AT)
        assert ans.ok is False
        assert ans.value is None
        assert _MOCK_REGIONAL not in ans.answer
        assert ans.route is QueryRoute.OFFICIAL_FRESHNESS_SEARCH

    def test_historical_as_of_mismatch_fails(self):
        pipe = _pipe(
            {
                _key(
                    FactKind.REGIONAL_EXECUTIVE, TemporalMode.HISTORICAL, "2019"
                ): _hit(
                    FactKind.REGIONAL_EXECUTIVE,
                    "다른해",
                    temporal_mode=TemporalMode.HISTORICAL,
                    as_of_year=2019,
                    as_of_date="2019",
                    temporal_precision=TemporalPrecision.YEAR,
                    retrieved_at=HIST_RETRIEVED_AT,
                )
            }
        )
        ans = pipe.answer("2020년 당시 광주시장은 누구였나요?", evaluated_at=EVALUATED_AT)
        assert ans.ok is False
        assert "다른해" not in ans.answer

    def test_current_does_not_use_historical_hit(self):
        pipe = _pipe(
            {
                _key(
                    FactKind.REGIONAL_EXECUTIVE, TemporalMode.HISTORICAL, "2020"
                ): _hit(
                    FactKind.REGIONAL_EXECUTIVE,
                    _MOCK_REGIONAL_2020,
                    temporal_mode=TemporalMode.HISTORICAL,
                    as_of_year=2020,
                    as_of_date="2020",
                    temporal_precision=TemporalPrecision.YEAR,
                    retrieved_at=HIST_RETRIEVED_AT,
                )
            }
        )
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok is False
        assert _MOCK_REGIONAL_2020 not in ans.answer

    def test_year_precision_preserved(self):
        hist, as_of, year, precision = detect_historical_reference("2020년 광주시장")
        assert hist and year == 2020 and precision is TemporalPrecision.YEAR
        assert as_of == "2020"  # not 2020-01-01


class TestSourcesAndIntegrity:
    def test_sources_nonempty_and_flat_consistent(self):
        pipe = _pipe(
            {
                _key(FactKind.CURRENT_MAYOR): _hit(
                    FactKind.CURRENT_MAYOR, _MOCK_DISTRICT
                )
            }
        )
        ans = pipe.answer("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT)
        assert ans.ok and len(ans.sources) >= 1
        assert ans.source_url == ans.sources[0].url
        assert ans.source_title == ans.sources[0].title
        assert ans.source_type == ans.sources[0].source_type

    def test_missing_title_not_verified(self):
        pipe = _pipe(
            {
                _key(FactKind.REGIONAL_EXECUTIVE): _hit(
                    FactKind.REGIONAL_EXECUTIVE, _MOCK_REGIONAL, title=""
                )
            }
        )
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok is False
        assert ans.freshness_status is not FreshnessStatus.VERIFIED_CURRENT

    def test_missing_url_not_verified(self):
        pipe = _pipe(
            {
                _key(FactKind.REGIONAL_EXECUTIVE): _hit(
                    FactKind.REGIONAL_EXECUTIVE, _MOCK_REGIONAL, url=""
                )
            }
        )
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok is False

    def test_wrong_source_type_fails(self):
        # Official provider slot with GENERAL_WEB hit
        bad = _hit(
            FactKind.REGIONAL_EXECUTIVE,
            _MOCK_REGIONAL,
            source_type=SourceType.GENERAL_WEB,
            url="https://example.test/x",
            title="web",
        )
        pipe = _pipe({_key(FactKind.REGIONAL_EXECUTIVE): bad})
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok is False
        assert ans.failure_code in {
            ErrorCode.SOURCE_TYPE_MISMATCH,
            ErrorCode.RETRIEVAL_FAILED,
        }
        assert _MOCK_REGIONAL not in ans.answer

    def test_fact_kind_mismatch_fails(self):
        mismatched = _hit(FactKind.FEE, "1000원")
        # stored under REGIONAL key but hit claims FEE
        pipe = _pipe({_key(FactKind.REGIONAL_EXECUTIVE): mismatched})
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok is False
        assert "1000원" not in ans.answer
        assert ans.failure_code in {
            ErrorCode.FACT_KIND_MISMATCH,
            ErrorCode.RETRIEVAL_FAILED,
        }

    def test_official_preferred_and_no_third_value(self):
        off = MockOfficialSearchProvider(
            {
                _key(FactKind.REGIONAL_EXECUTIVE): _hit(
                    FactKind.REGIONAL_EXECUTIVE, "공식값"
                )
            }
        )
        gen = MockGeneralWebSearchProvider(
            {
                _key(FactKind.REGIONAL_EXECUTIVE): _hit(
                    FactKind.REGIONAL_EXECUTIVE,
                    "일반값",
                    source_type=SourceType.GENERAL_WEB,
                    url="https://example.test/g",
                    title="general",
                )
            }
        )
        pipe = CurrentInformationPipeline(
            orchestrator=OfficialFirstSearchOrchestrator(
                official=off, general=gen, allow_general=True
            )
        )
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok and ans.value == "공식값"
        assert "일반값" not in ans.answer
        assert gen.call_log == ()  # general not called when official succeeds


class TestContextPropagation:
    def test_effective_context_current_information_required(self):
        pipe = _pipe(
            {
                _key(FactKind.REGIONAL_EXECUTIVE): _hit(
                    FactKind.REGIONAL_EXECUTIVE, _MOCK_REGIONAL
                )
            }
        )
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.request_context is not None
        assert ans.request_context["current_information_required"] is True
        assert ans.request_context["temporal_mode"] == "current"

    def test_historical_context_synced(self):
        pipe = _pipe(
            {
                _key(
                    FactKind.REGIONAL_EXECUTIVE, TemporalMode.HISTORICAL, "2020"
                ): _hit(
                    FactKind.REGIONAL_EXECUTIVE,
                    _MOCK_REGIONAL_2020,
                    temporal_mode=TemporalMode.HISTORICAL,
                    as_of_year=2020,
                    as_of_date="2020",
                    temporal_precision=TemporalPrecision.YEAR,
                    retrieved_at=HIST_RETRIEVED_AT,
                )
            }
        )
        ans = pipe.answer("2020년 당시 광주시장은 누구였나요?", evaluated_at=EVALUATED_AT)
        assert ans.request_context is not None
        assert ans.request_context["historical_reference"] is True
        assert ans.request_context["as_of_year"] == 2020
        assert ans.request_context["temporal_mode"] == "historical"


class TestJourney:
    def test_journey_only(self):
        pipe = _pipe()
        ans = pipe.answer("불법 주정차 신고는 어디서 하나요?", evaluated_at=EVALUATED_AT)
        assert ans.ok
        assert ans.route is QueryRoute.DETERMINISTIC_JOURNEY
        assert ans.journey_preserved is True
        assert ans.journey_action == "illegal_parking"

    def test_journey_enrichment_success_preserves_guidance(self):
        pipe = _pipe(
            {
                _key(FactKind.FEE): _hit(
                    FactKind.FEE, "예시수수료", title="fee page", url="https://bukgu.gwangju.kr/fee"
                )
            }
        )
        ans = pipe.answer("여권 발급 수수료가 얼마인가요?", evaluated_at=EVALUATED_AT)
        assert ans.ok
        assert ans.route is QueryRoute.DETERMINISTIC_JOURNEY
        assert ans.journey_action == "passport_guidance"
        assert ans.journey_preserved is True
        assert "안내 경로" in ans.answer
        assert ans.enrichment_value == "예시수수료"
        assert ans.sources

    def test_journey_enrichment_failure_no_fact_value(self):
        pipe = _pipe()
        ans = pipe.answer("여권 발급 수수료가 얼마인가요?", evaluated_at=EVALUATED_AT)
        assert ans.route is QueryRoute.DETERMINISTIC_JOURNEY
        assert ans.journey_preserved is True
        assert ans.enrichment_value is None
        assert ans.value is None
        assert "freshness_enrichment_failed" in ans.warnings

    def test_mayor_proposal_not_fact(self):
        d = route_question("구청장에게 제안하고 싶어요")
        assert d.route is QueryRoute.DETERMINISTIC_JOURNEY
        assert d.journey_action == "mayor_message_assist"

    def test_who_is_mayor_not_journey(self):
        d = route_question("현재 북구청장은 누구인가요?")
        assert d.route is QueryRoute.OFFICIAL_FRESHNESS_SEARCH
        assert d.journey_action is None


class TestAttemptedRoute:
    def test_official_failure_keeps_route(self):
        pipe = _pipe()
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok is False
        assert ans.route is QueryRoute.OFFICIAL_FRESHNESS_SEARCH
        assert ans.failure_code is ErrorCode.RETRIEVAL_FAILED

    def test_general_failure_keeps_route(self):
        pipe = _pipe()
        ans = pipe.answer("오늘 날씨 어때?", evaluated_at=EVALUATED_AT)
        assert ans.ok is False
        assert ans.route is QueryRoute.GENERAL_WEB_SEARCH

    def test_unsupported_is_safe_unsupported(self):
        pipe = _pipe()
        ans = pipe.answer("xyzzy 아무말", evaluated_at=EVALUATED_AT)
        assert ans.route is QueryRoute.SAFE_UNSUPPORTED
        assert ans.failure_code is ErrorCode.UNSUPPORTED_QUESTION


class TestHallucination:
    def test_failure_no_forbidden_names(self):
        pipe = _pipe()
        ans = pipe.answer("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT)
        assert_no_hallucinated_names(ans, forbidden_names=_FORBIDDEN)
        assert ans.value is None

    def test_stale_value_not_in_failure_answer(self):
        pipe = _pipe(
            {
                _key(FactKind.REGIONAL_EXECUTIVE): _hit(
                    FactKind.REGIONAL_EXECUTIVE,
                    _MOCK_REGIONAL,
                    retrieved_at=STALE_RETRIEVED_AT,
                )
            }
        )
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok is False
        assert _MOCK_REGIONAL not in ans.answer

    def test_success_only_retrieved_value(self):
        pipe = _pipe(
            {
                _key(FactKind.CURRENT_MAYOR): _hit(
                    FactKind.CURRENT_MAYOR, _MOCK_DISTRICT
                )
            }
        )
        ans = pipe.answer("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT)
        assert ans.ok
        assert_no_hallucinated_names(ans, forbidden_names=_FORBIDDEN + ("다른이름",))


class TestRoutingSmoke:
    def test_aliases_table(self):
        table = {s for s, _e, _k in alias_table_for_tests()}
        for phrase in (
            "광주시장",
            "광주광역시장",
            "광주 시장",
            "통합시장",
            "특별시장",
            "광주광역시",
            "전라남도",
            "광주 북구",
            "광주광역시 북구",
        ):
            assert phrase in table

    def test_fact_kinds(self):
        values = {k.value for k in FactKind}
        assert "regional_executive" in values
        assert "current_mayor" in values

    def test_general_fallback(self):
        pipe = _pipe(
            official={},
            general={
                _key(FactKind.GENERAL_CURRENT_INFORMATION): _hit(
                    FactKind.GENERAL_CURRENT_INFORMATION,
                    "맑음 예시",
                    source_type=SourceType.GENERAL_WEB,
                    url="https://example.test/weather",
                    title="weather",
                )
            },
        )
        ans = pipe.answer("오늘 날씨 어때?", evaluated_at=EVALUATED_AT)
        assert ans.ok and ans.value == "맑음 예시"
        assert ans.source_type is SourceType.GENERAL_WEB
