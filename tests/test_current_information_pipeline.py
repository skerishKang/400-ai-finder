"""Expanded #1150 current-information pipeline contracts (mock/offline only).

No live network, Firecrawl, provider API, or browser automation.
"""

from __future__ import annotations

import ast
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.official_source import (
    CurrentInformationPipeline,
    FactKind,
    FreshnessStatus,
    MockGeneralWebSearchProvider,
    MockOfficialSearchProvider,
    OfficialFirstSearchOrchestrator,
    QueryRoute,
    SearchHit,
    SourceType,
    assert_no_hallucinated_names,
    build_request_context,
    classify_journey_action,
    classify_question,
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

# Example values for *mock fixtures only* — not product constants.
_MOCK_REGIONAL_NAME = "예시통합시장"
_MOCK_DISTRICT_NAME = "예시구청장"
_MOCK_JURISDICTION = "예시자치구명칭"
_FORBIDDEN_HARDCODED = (
    "민형배",
    "신수정",
    "전남광주통합특별시",  # must not appear unless retrieved value
)


def _official_hit(
    kind: FactKind,
    value: str,
    *,
    url: str = "https://bukgu.gwangju.kr/mock-official",
    title: str = "mock official page",
    retrieved_at: str = FRESH_RETRIEVED_AT,
) -> SearchHit:
    return SearchHit(
        fact_kind=kind,
        value=value,
        source_url=url,
        source_title=title,
        source_type=SourceType.OFFICIAL,
        retrieved_at=retrieved_at,
        snippet=value,
    )


def _general_hit(
    kind: FactKind,
    value: str,
    *,
    url: str = "https://example.test/news",
    title: str = "mock general page",
    retrieved_at: str = FRESH_RETRIEVED_AT,
) -> SearchHit:
    return SearchHit(
        fact_kind=kind,
        value=value,
        source_url=url,
        source_title=title,
        source_type=SourceType.GENERAL_WEB,
        retrieved_at=retrieved_at,
        snippet=value,
    )


def _pipeline(
    official: dict[FactKind, SearchHit] | None = None,
    general: dict[FactKind, SearchHit] | None = None,
    *,
    fail_official: frozenset[FactKind] | None = None,
    fail_general: frozenset[FactKind] | None = None,
) -> CurrentInformationPipeline:
    return CurrentInformationPipeline(
        orchestrator=OfficialFirstSearchOrchestrator(
            official=MockOfficialSearchProvider(
                official or {}, fail_kinds=fail_official
            ),
            general=MockGeneralWebSearchProvider(
                general or {}, fail_kinds=fail_general
            ),
            allow_general=True,
        )
    )


# ---------------------------------------------------------------------------
# Network-free boundary
# ---------------------------------------------------------------------------


class TestNetworkFree:
    def test_import_and_pipeline_zero_network(self, monkeypatch):
        calls: list[object] = []

        def blocked(*a, **k):
            calls.append((a, k))
            raise AssertionError("network")

        monkeypatch.setattr(socket.socket, "connect", blocked)
        monkeypatch.setattr(socket.socket, "connect_ex", blocked)
        pipe = CurrentInformationPipeline()
        ctx = build_request_context(evaluated_at=EVALUATED_AT)
        _ = pipe.answer("불법 주정차 신고는 어디서 하나요?", request_context=ctx)
        assert calls == []

    def test_new_modules_have_no_network_imports(self):
        # Align with Phase-1 package contract: stdlib urllib.parse is allowed;
        # network clients are not.
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


# ---------------------------------------------------------------------------
# RequestContext / clock injection
# ---------------------------------------------------------------------------


class TestRequestContext:
    def test_evaluated_at_injection(self):
        ctx = build_request_context(evaluated_at=EVALUATED_AT)
        assert ctx.request_started_at_utc == EVALUATED_AT
        assert ctx.timezone == "Asia/Seoul"
        assert "2026-07-16" in ctx.request_started_at_local

    def test_clock_callable_injection(self):
        fixed = datetime(2026, 7, 16, 1, 0, 0, tzinfo=timezone.utc)

        def clock():
            return fixed

        ctx = build_request_context(clock=clock)
        assert ctx.request_started_at_utc == "2026-07-16T01:00:00Z"


# ---------------------------------------------------------------------------
# Routing decision table
# ---------------------------------------------------------------------------


class TestRouting:
    def test_deterministic_illegal_parking(self):
        d = route_question("불법 주정차 신고는 어디서 하나요?")
        assert d.route is QueryRoute.DETERMINISTIC_JOURNEY
        assert d.journey_action == "illegal_parking"
        assert d.needs_freshness_enrichment is False

    def test_passport_journey(self):
        d = route_question("여권 발급 안내 해주세요")
        assert d.route is QueryRoute.DETERMINISTIC_JOURNEY
        assert d.journey_action == "passport_guidance"

    def test_passport_fee_enrichment(self):
        d = route_question("여권 발급 수수료가 얼마인가요?")
        assert d.route is QueryRoute.DETERMINISTIC_JOURNEY
        assert d.journey_action == "passport_guidance"
        assert d.needs_freshness_enrichment is True
        assert d.fact_kind is FactKind.FEE

    def test_mayor_message_is_journey_not_district_fact(self):
        d = route_question("구청장에게 제안하고 싶어요")
        assert d.route is QueryRoute.DETERMINISTIC_JOURNEY
        assert d.journey_action == "mayor_message_assist"

    def test_district_mayor_official_freshness(self):
        d = route_question("현재 북구청장은 누구인가요?")
        assert d.route is QueryRoute.OFFICIAL_FRESHNESS_SEARCH
        assert d.fact_kind is FactKind.CURRENT_MAYOR
        assert d.journey_action is None

    def test_regional_mayor_official_freshness(self):
        d = route_question("광주시장은 누구야")
        assert d.route is QueryRoute.OFFICIAL_FRESHNESS_SEARCH
        assert d.fact_kind is FactKind.REGIONAL_EXECUTIVE

    def test_weather_general_search(self):
        d = route_question("오늘 광주 날씨 어때?")
        assert d.route is QueryRoute.GENERAL_WEB_SEARCH
        assert d.fact_kind is FactKind.GENERAL_CURRENT_INFORMATION

    def test_safe_unsupported(self):
        d = route_question("아무 의미 없는 문자열 xyzzy")
        assert d.route is QueryRoute.SAFE_UNSUPPORTED


# ---------------------------------------------------------------------------
# Aliases / historical
# ---------------------------------------------------------------------------


class TestAliases:
    @pytest.mark.parametrize(
        "phrase",
        [
            "광주시장",
            "광주광역시장",
            "광주 시장",
            "전남광주특별시장",
            "통합시장",
            "특별시장",
            "광주광역시",
            "전라남도",
            "광주 북구",
            "광주광역시 북구",
        ],
    )
    def test_surface_aliases_present(self, phrase: str):
        table = {s for s, _e, _k in alias_table_for_tests()}
        assert phrase in table

    def test_current_alias_forces_entity(self):
        r = resolve_aliases("현재 광주시장은 누구인가요?")
        assert r.historical is False
        assert r.force_current_entity is True
        assert "광주시장" in r.matched_aliases or any(
            "시장" in a for a in r.matched_aliases
        )

    def test_historical_does_not_force_current(self):
        r = resolve_aliases("2020년 당시 광주시장은 누구였나요?")
        assert r.historical is True
        hist, as_of = detect_historical_reference(
            "2020년 당시 광주시장은 누구였나요?"
        )
        assert hist is True
        assert as_of is not None and as_of.startswith("2020")


# ---------------------------------------------------------------------------
# Fact kinds expanded
# ---------------------------------------------------------------------------


class TestFactKinds:
    def test_expanded_kinds_exist(self):
        required = {
            "regional_executive",
            "district_executive",
            "jurisdiction_name",
            "agency_name",
            "administrative_status",
            "office_hours",
            "contact_information",
            "fee",
            "application_period",
            "current_notice",
            "current_policy",
            "current_law",
            "current_event",
            "general_current_information",
            "current_mayor",
        }
        values = {k.value for k in FactKind}
        assert required <= values


# ---------------------------------------------------------------------------
# Official-first provider + retrieval success
# ---------------------------------------------------------------------------


class TestOfficialFirstRetrieval:
    def test_regional_executive_from_official_search(self):
        pipe = _pipeline(
            official={
                FactKind.REGIONAL_EXECUTIVE: _official_hit(
                    FactKind.REGIONAL_EXECUTIVE, _MOCK_REGIONAL_NAME
                )
            }
        )
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok is True
        assert ans.value == _MOCK_REGIONAL_NAME
        assert ans.source_url
        assert ans.retrieved_at == FRESH_RETRIEVED_AT
        assert ans.current_as_of == EVALUATED_AT
        assert ans.freshness_status is FreshnessStatus.VERIFIED_CURRENT
        assert ans.source_type is SourceType.OFFICIAL
        assert _MOCK_REGIONAL_NAME in ans.answer
        assert FRESH_RETRIEVED_AT in ans.answer

    def test_district_mayor_from_official_search(self):
        pipe = _pipeline(
            official={
                FactKind.CURRENT_MAYOR: _official_hit(
                    FactKind.CURRENT_MAYOR, _MOCK_DISTRICT_NAME
                )
            }
        )
        ans = pipe.answer("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT)
        assert ans.ok is True
        assert ans.value == _MOCK_DISTRICT_NAME
        assert ans.source_url and ans.retrieved_at and ans.current_as_of

    def test_official_preferred_over_general_conflict(self):
        pipe = _pipeline(
            official={
                FactKind.REGIONAL_EXECUTIVE: _official_hit(
                    FactKind.REGIONAL_EXECUTIVE, "공식값"
                )
            },
            general={
                FactKind.REGIONAL_EXECUTIVE: _general_hit(
                    FactKind.REGIONAL_EXECUTIVE, "일반웹값"
                )
            },
        )
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok is True
        assert ans.value == "공식값"
        assert ans.source_type is SourceType.OFFICIAL
        assert "일반웹값" not in ans.answer

    def test_general_used_when_official_missing(self):
        pipe = _pipeline(
            official={},
            general={
                FactKind.GENERAL_CURRENT_INFORMATION: _general_hit(
                    FactKind.GENERAL_CURRENT_INFORMATION, "맑음 예시"
                )
            },
        )
        ans = pipe.answer("오늘 날씨 어때?", evaluated_at=EVALUATED_AT)
        assert ans.ok is True
        assert ans.value == "맑음 예시"
        assert ans.source_type is SourceType.GENERAL_WEB


# ---------------------------------------------------------------------------
# Fail-closed / no hallucination
# ---------------------------------------------------------------------------


class TestFailClosedNoHallucination:
    def test_no_search_no_mayor_name(self):
        pipe = _pipeline()  # empty mocks
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok is False
        assert ans.value is None
        assert ans.failure_code is ErrorCode.RETRIEVAL_FAILED
        assert ans.freshness_status is not FreshnessStatus.VERIFIED_CURRENT
        for name in _FORBIDDEN_HARDCODED + (_MOCK_REGIONAL_NAME,):
            assert name not in ans.answer

    def test_no_search_no_jurisdiction_name(self):
        pipe = _pipeline()
        ans = pipe.answer("북구청의 현재 기관명은 무엇인가요?", evaluated_at=EVALUATED_AT)
        assert ans.ok is False
        assert ans.value is None
        assert _MOCK_JURISDICTION not in ans.answer

    def test_stale_not_verified_current(self):
        pipe = _pipeline(
            official={
                FactKind.REGIONAL_EXECUTIVE: _official_hit(
                    FactKind.REGIONAL_EXECUTIVE,
                    _MOCK_REGIONAL_NAME,
                    retrieved_at=STALE_RETRIEVED_AT,
                )
            }
        )
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok is False
        assert ans.failure_code is ErrorCode.STALE_SOURCE
        assert ans.freshness_status is not FreshnessStatus.VERIFIED_CURRENT

    def test_no_source_no_verified_current(self):
        hit = SearchHit(
            fact_kind=FactKind.REGIONAL_EXECUTIVE,
            value=_MOCK_REGIONAL_NAME,
            source_url="",
            source_title="",
            source_type=SourceType.OFFICIAL,
            retrieved_at=FRESH_RETRIEVED_AT,
        )
        pipe = _pipeline(official={FactKind.REGIONAL_EXECUTIVE: hit})
        ans = pipe.answer("광주시장은 누구야", evaluated_at=EVALUATED_AT)
        assert ans.ok is False
        assert ans.failure_code is ErrorCode.NO_VERIFIED_SOURCE

    def test_failure_does_not_use_forbidden_hardcoded_names(self):
        pipe = _pipeline()
        ans = pipe.answer("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT)
        assert_no_hallucinated_names(ans, forbidden_names=_FORBIDDEN_HARDCODED)

    def test_success_only_uses_retrieved_value(self):
        pipe = _pipeline(
            official={
                FactKind.CURRENT_MAYOR: _official_hit(
                    FactKind.CURRENT_MAYOR, _MOCK_DISTRICT_NAME
                )
            }
        )
        ans = pipe.answer("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT)
        assert ans.ok is True
        assert_no_hallucinated_names(
            ans, forbidden_names=_FORBIDDEN_HARDCODED + ("다른이름",)
        )


# ---------------------------------------------------------------------------
# Journey isolation
# ---------------------------------------------------------------------------


class TestJourneyIsolation:
    def test_journey_not_converted_to_fact_path(self):
        pipe = _pipeline(
            official={
                FactKind.CURRENT_MAYOR: _official_hit(
                    FactKind.CURRENT_MAYOR, _MOCK_DISTRICT_NAME
                )
            }
        )
        ans = pipe.answer("구청장에게 제안하고 싶어요", evaluated_at=EVALUATED_AT)
        assert ans.ok is True
        assert ans.route is QueryRoute.DETERMINISTIC_JOURNEY
        assert ans.journey_action == "mayor_message_assist"
        # Must not claim a current mayor name from mock.
        assert ans.value is None
        assert _MOCK_DISTRICT_NAME not in ans.answer

    def test_journey_fee_enrichment_fail_closed(self):
        pipe = _pipeline()  # no fee hits
        ans = pipe.answer("여권 발급 수수료가 얼마인가요?", evaluated_at=EVALUATED_AT)
        assert ans.route is QueryRoute.DETERMINISTIC_JOURNEY
        assert ans.journey_action == "passport_guidance"
        # No invented fee amount
        assert not any(ch.isdigit() for ch in (ans.value or ""))

    def test_classify_journey_mirror(self):
        assert classify_journey_action("불법 주정차") == "illegal_parking"
        assert classify_journey_action("현재 북구청장") is None


# ---------------------------------------------------------------------------
# Classification expansion smoke
# ---------------------------------------------------------------------------


class TestClassificationExpanded:
    def test_office_hours(self):
        r = classify_question("북구청 운영 시간이 어떻게 되나요?")
        assert r.supported and r.fact_kind is FactKind.OFFICE_HOURS

    def test_fee(self):
        r = classify_question("여권 수수료 알려줘")
        assert r.supported and r.fact_kind is FactKind.FEE
