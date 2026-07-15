"""Phase-1 official-source freshness retrieval contracts (#1150).

Covers:

* time-sensitive question classification
* official Buk-gu allowlist policy
* mock transport retrieval
* HTML parsing / fact normalization
* freshness timestamps (fresh / stale / invalid)
* fail-closed error taxonomy
* no-network import and construction boundary

No live official-page, Firecrawl, paid provider, or external API call.
"""

from __future__ import annotations

import ast
import socket
from pathlib import Path

import pytest

from src.official_source import (
    ERROR_CODES,
    ErrorCode,
    FactKind,
    FreshnessStatus,
    MockOfficialSourceTransport,
    OfficialSourceFreshnessService,
    OfficialSourceRequest,
    OfficialSourceResult,
    TransportResponse,
    assess_freshness,
    classify_question,
    get_policy_for_fact,
    is_url_allowlisted,
)
from src.official_source.extraction import (
    AmbiguousValueError,
    FactAbsentError,
    MalformedHtmlError,
    extract_fact_candidates,
    resolve_single_fact,
)
from src.official_source.freshness import InvalidTimestampError, parse_utc_timestamp
from src.official_source.normalize import normalize_fact_value
from src.official_source.policy import (
    OFFICIAL_HOST,
    allowlisted_urls,
    canonicalize_official_url,
)
from src.official_source.transport import LiveTransportNotAuthorized

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "official_source"

MAYOR_URL = "https://bukgu.gwangju.kr/menu.es?mid=a10101010100"
JURISDICTION_URL = "https://bukgu.gwangju.kr/"
EVALUATED_AT = "2026-07-15T12:00:00Z"
FRESH_RETRIEVED_AT = "2026-07-15T10:00:00Z"
STALE_RETRIEVED_AT = "2026-06-01T10:00:00Z"


def _read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _ok_response(
    url: str,
    html: str,
    *,
    title: str = "",
    retrieved_at: str = FRESH_RETRIEVED_AT,
    final_url: str | None = None,
    redirected: bool = False,
) -> TransportResponse:
    return TransportResponse(
        ok=True,
        requested_url=url,
        final_url=final_url or url,
        status_code=200,
        title=title,
        html=html,
        content_type="text/html; charset=utf-8",
        retrieved_at=retrieved_at,
        redirected=redirected,
    )


def _service_with(responses: dict[str, TransportResponse]) -> OfficialSourceFreshnessService:
    return OfficialSourceFreshnessService(
        transport=MockOfficialSourceTransport(responses=responses)
    )


# ---------------------------------------------------------------------------
# No-network boundary
# ---------------------------------------------------------------------------


class TestNoNetworkBoundary:
    def test_import_and_construction_do_not_open_sockets(self, monkeypatch):
        calls: list[tuple] = []

        def blocked(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("network call attempted during import/construction")

        monkeypatch.setattr(socket.socket, "connect", blocked)
        monkeypatch.setattr(socket.socket, "connect_ex", blocked)

        # Re-import path already loaded; still construct service + classify.
        service = OfficialSourceFreshnessService()
        assert service.transport_name == "mock_official_source"
        result = classify_question("북구 구청장 누구야")
        assert result.supported is True
        assert calls == []

    def test_package_source_has_no_network_imports(self):
        package_dir = REPO_ROOT / "src" / "official_source"
        forbidden = {
            "urllib.request",
            "urllib.client",
            "http.client",
            "requests",
            "httpx",
            "aiohttp",
            "firecrawl",
            "socket",
        }
        for path in package_dir.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        assert alias.name not in forbidden and root not in {
                            "requests",
                            "httpx",
                            "aiohttp",
                            "firecrawl",
                        }, f"{path.name} imports {alias.name}"
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module not in forbidden, (
                        f"{path.name} imports from {node.module}"
                    )
                    root = node.module.split(".")[0]
                    assert root not in {"requests", "httpx", "aiohttp", "firecrawl"}

    def test_live_transport_not_authorized_fails_closed(self):
        transport = LiveTransportNotAuthorized()
        service = OfficialSourceFreshnessService(transport=transport)
        result = service.retrieve("현재 북구 구청장은 누구인가요?", evaluated_at=EVALUATED_AT)
        assert result.success is False
        assert result.fact is None
        assert result.error_code is ErrorCode.TRANSPORT_FAILURE


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class TestClassification:
    @pytest.mark.parametrize(
        "question",
        [
            "현재 북구 구청장은 누구인가요?",
            "구청장 이름 알려줘",
            "지금 구청장",
            "Who is the current Buk-gu mayor?",
        ],
    )
    def test_classifies_current_mayor(self, question: str):
        result = classify_question(question)
        assert result.supported is True
        assert result.fact_kind is FactKind.CURRENT_MAYOR

    @pytest.mark.parametrize(
        "question",
        [
            "북구청 공식 기관 명칭이 뭐야?",
            "관할 구역 이름",
            "organization name",
            "이 사이트가 어디 기관이야?",
        ],
    )
    def test_classifies_jurisdiction(self, question: str):
        result = classify_question(question)
        assert result.supported is True
        assert result.fact_kind is FactKind.JURISDICTION_NAME

    @pytest.mark.parametrize(
        "question",
        [
            "오늘 날씨 알려줘",
            "대형폐기물 신청 방법",
            "여권 발급 절차",
            "",
            "   ",
            "arbitrary web search about politics",
        ],
    )
    def test_unsupported_questions(self, question: str):
        result = classify_question(question)
        assert result.supported is False
        assert result.fact_kind is None


# ---------------------------------------------------------------------------
# Allowlist policy
# ---------------------------------------------------------------------------


class TestAllowlistPolicy:
    def test_official_policies_are_allowlisted(self):
        for kind in FactKind:
            policy = get_policy_for_fact(kind)
            assert is_url_allowlisted(policy.url, kind)
            assert OFFICIAL_HOST in policy.url

    def test_non_allowlisted_url_rejected(self):
        assert is_url_allowlisted("https://example.com/", FactKind.CURRENT_MAYOR) is False
        assert is_url_allowlisted("https://www.gwangju.go.kr/", FactKind.CURRENT_MAYOR) is False
        assert (
            is_url_allowlisted(
                "https://bukgu.gwangju.kr/menu.es?mid=not-allowlisted",
                FactKind.CURRENT_MAYOR,
            )
            is False
        )

    def test_wrong_fact_url_not_allowlisted_for_other_kind(self):
        mayor_policy = get_policy_for_fact(FactKind.CURRENT_MAYOR)
        assert is_url_allowlisted(mayor_policy.url, FactKind.JURISDICTION_NAME) is False

    def test_canonicalize_strips_default_noise(self):
        a = canonicalize_official_url(
            "https://bukgu.gwangju.kr/menu.es?mid=a10101010100"
        )
        b = canonicalize_official_url(
            "https://BUKGU.GWANGJU.KR/menu.es?mid=a10101010100"
        )
        assert a == b
        assert a is not None

    def test_allowlisted_urls_closed_set(self):
        urls = allowlisted_urls()
        assert len(urls) == 2
        assert all(OFFICIAL_HOST in u for u in urls)


# ---------------------------------------------------------------------------
# Extraction / parsing / normalization
# ---------------------------------------------------------------------------


class TestExtractionAndNormalize:
    def test_extract_mayor_from_fixture(self):
        html = _read_fixture("mayor_page.html")
        fact, title = resolve_single_fact(
            html,
            fact_kind=FactKind.CURRENT_MAYOR,
            fact_marker="current_mayor",
        )
        assert fact.value == "문인"
        assert "구청장" in title

    def test_extract_jurisdiction_from_fixture(self):
        html = _read_fixture("jurisdiction_page.html")
        fact, _title = resolve_single_fact(
            html,
            fact_kind=FactKind.JURISDICTION_NAME,
            fact_marker="jurisdiction_name",
        )
        assert fact.value == "광주광역시 북구청"

    def test_malformed_html_raises(self):
        html = _read_fixture("malformed.html")
        with pytest.raises(MalformedHtmlError):
            extract_fact_candidates(
                html,
                fact_kind=FactKind.CURRENT_MAYOR,
                fact_marker="current_mayor",
            )

    def test_missing_fact_raises(self):
        html = _read_fixture("missing_fact.html")
        with pytest.raises(FactAbsentError):
            resolve_single_fact(
                html,
                fact_kind=FactKind.CURRENT_MAYOR,
                fact_marker="current_mayor",
            )

    def test_ambiguous_values_raise(self):
        html = _read_fixture("ambiguous_mayor.html")
        with pytest.raises(AmbiguousValueError):
            resolve_single_fact(
                html,
                fact_kind=FactKind.CURRENT_MAYOR,
                fact_marker="current_mayor",
            )

    def test_normalize_strips_honorific(self):
        fact = normalize_fact_value(FactKind.CURRENT_MAYOR, "문인 구청장")
        assert fact is not None
        assert fact.value == "문인"
        assert fact.raw_value == "문인 구청장"

    def test_heuristic_mayor_extraction(self):
        html = "<html><body><p>구청장 : 문인</p></body></html>"
        fact, _ = resolve_single_fact(
            html,
            fact_kind=FactKind.CURRENT_MAYOR,
            fact_marker="current_mayor",
        )
        assert fact.value == "문인"

    def test_heuristic_does_not_match_prose_without_separator(self):
        html = "<html><body><p>이 페이지에는 구청장 정보가 없습니다.</p></body></html>"
        with pytest.raises(FactAbsentError):
            resolve_single_fact(
                html,
                fact_kind=FactKind.CURRENT_MAYOR,
                fact_marker="current_mayor",
            )


# ---------------------------------------------------------------------------
# Freshness timestamps
# ---------------------------------------------------------------------------


class TestFreshnessTimestamp:
    def test_fresh_within_max_age(self):
        assessment = assess_freshness(
            retrieved_at=FRESH_RETRIEVED_AT,
            max_age_seconds=7 * 24 * 3600,
            evaluated_at=EVALUATED_AT,
        )
        assert assessment.status is FreshnessStatus.FRESH
        assert assessment.age_seconds == 2 * 3600

    def test_stale_beyond_max_age(self):
        assessment = assess_freshness(
            retrieved_at=STALE_RETRIEVED_AT,
            max_age_seconds=7 * 24 * 3600,
            evaluated_at=EVALUATED_AT,
        )
        assert assessment.status is FreshnessStatus.STALE
        assert assessment.age_seconds is not None
        assert assessment.age_seconds > 7 * 24 * 3600

    def test_invalid_timestamp_rejected(self):
        with pytest.raises(InvalidTimestampError):
            parse_utc_timestamp("not-a-timestamp")
        with pytest.raises(InvalidTimestampError):
            parse_utc_timestamp("2026-07-15T12:00:00")  # naive
        with pytest.raises(InvalidTimestampError):
            parse_utc_timestamp("")
        with pytest.raises(InvalidTimestampError):
            assess_freshness(
                retrieved_at="2026-07-16T00:00:00Z",  # future vs evaluated
                max_age_seconds=100,
                evaluated_at=EVALUATED_AT,
            )


# ---------------------------------------------------------------------------
# Mock retrieval success path
# ---------------------------------------------------------------------------


class TestMockRetrievalSuccess:
    def test_current_mayor_success_payload(self):
        service = _service_with(
            {
                MAYOR_URL: _ok_response(
                    MAYOR_URL,
                    _read_fixture("mayor_page.html"),
                    title="구청장 소개",
                )
            }
        )
        result = service.retrieve(
            "현재 북구 구청장은 누구인가요?",
            evaluated_at=EVALUATED_AT,
        )
        assert result.success is True
        assert result.error_code is None
        assert result.fact is not None
        assert result.fact.kind is FactKind.CURRENT_MAYOR
        assert result.fact.value == "문인"
        assert result.source is not None
        assert result.source.url == MAYOR_URL
        assert result.source.retrieved_at == FRESH_RETRIEVED_AT
        assert result.source.title
        assert result.freshness_status is FreshnessStatus.FRESH
        assert result.max_age_seconds == 7 * 24 * 3600
        payload = result.to_dict()
        assert payload["success"] is True
        assert payload["fact"]["value"] == "문인"
        assert payload["source"]["url"] == MAYOR_URL

    def test_jurisdiction_success_payload(self):
        service = _service_with(
            {
                JURISDICTION_URL: _ok_response(
                    JURISDICTION_URL,
                    _read_fixture("jurisdiction_page.html"),
                    title="광주광역시 북구청",
                )
            }
        )
        result = service.retrieve(
            "북구청 공식 기관 명칭이 뭐야?",
            evaluated_at=EVALUATED_AT,
        )
        assert result.success is True
        assert result.fact is not None
        assert result.fact.kind is FactKind.JURISDICTION_NAME
        assert "북구" in result.fact.value

    def test_explicit_fact_kind_request(self):
        service = _service_with(
            {
                MAYOR_URL: _ok_response(MAYOR_URL, _read_fixture("mayor_page.html"))
            }
        )
        result = service.retrieve_request(
            OfficialSourceRequest(
                question="ignored when fact_kind set",
                fact_kind=FactKind.CURRENT_MAYOR,
                evaluated_at=EVALUATED_AT,
            )
        )
        assert result.success is True
        assert result.fact is not None
        assert result.fact.value == "문인"


# ---------------------------------------------------------------------------
# Fail-closed error taxonomy
# ---------------------------------------------------------------------------


class TestFailClosedTaxonomy:
    def test_error_codes_are_closed_vocabulary(self):
        assert "unsupported_question" in ERROR_CODES
        assert "stale_retrieval" in ERROR_CODES
        assert "external_origin" in ERROR_CODES
        assert len(ERROR_CODES) >= 12

    def _assert_fail_closed(self, result: OfficialSourceResult, code: ErrorCode):
        assert result.success is False
        assert result.fact is None
        assert result.error_code is code
        assert result.error_message
        payload = result.to_dict()
        assert payload["fact"] is None
        assert payload["error_code"] == code.value

    def test_unsupported_question(self):
        service = OfficialSourceFreshnessService()
        result = service.retrieve("오늘 날씨 알려줘", evaluated_at=EVALUATED_AT)
        self._assert_fail_closed(result, ErrorCode.UNSUPPORTED_QUESTION)

    def test_missing_source(self):
        # Empty mock → no configured response.
        service = OfficialSourceFreshnessService(transport=MockOfficialSourceTransport())
        result = service.retrieve("구청장 누구야", evaluated_at=EVALUATED_AT)
        self._assert_fail_closed(result, ErrorCode.MISSING_SOURCE)

    def test_transport_failure(self):
        service = _service_with(
            {
                MAYOR_URL: TransportResponse(
                    ok=False,
                    requested_url=MAYOR_URL,
                    status_code=500,
                    error="upstream_5xx",
                    retrieved_at=FRESH_RETRIEVED_AT,
                )
            }
        )
        result = service.retrieve("구청장 누구야", evaluated_at=EVALUATED_AT)
        self._assert_fail_closed(result, ErrorCode.TRANSPORT_FAILURE)

    def test_transport_timeout(self):
        service = _service_with(
            {
                MAYOR_URL: TransportResponse(
                    ok=False,
                    requested_url=MAYOR_URL,
                    timed_out=True,
                    error="deadline exceeded",
                    retrieved_at="",
                )
            }
        )
        result = service.retrieve("구청장 누구야", evaluated_at=EVALUATED_AT)
        self._assert_fail_closed(result, ErrorCode.TRANSPORT_TIMEOUT)

    def test_malformed_html(self):
        service = _service_with(
            {
                MAYOR_URL: _ok_response(MAYOR_URL, _read_fixture("malformed.html"))
            }
        )
        result = service.retrieve("구청장 누구야", evaluated_at=EVALUATED_AT)
        self._assert_fail_closed(result, ErrorCode.MALFORMED_HTML)

    def test_fact_absent(self):
        service = _service_with(
            {
                MAYOR_URL: _ok_response(MAYOR_URL, _read_fixture("missing_fact.html"))
            }
        )
        result = service.retrieve("구청장 누구야", evaluated_at=EVALUATED_AT)
        self._assert_fail_closed(result, ErrorCode.FACT_ABSENT)

    def test_ambiguous_multiple_values(self):
        service = _service_with(
            {
                MAYOR_URL: _ok_response(
                    MAYOR_URL, _read_fixture("ambiguous_mayor.html")
                )
            }
        )
        result = service.retrieve("구청장 누구야", evaluated_at=EVALUATED_AT)
        self._assert_fail_closed(result, ErrorCode.AMBIGUOUS_VALUE)

    def test_stale_retrieval_metadata(self):
        service = _service_with(
            {
                MAYOR_URL: _ok_response(
                    MAYOR_URL,
                    _read_fixture("mayor_page.html"),
                    retrieved_at=STALE_RETRIEVED_AT,
                )
            }
        )
        result = service.retrieve("구청장 누구야", evaluated_at=EVALUATED_AT)
        self._assert_fail_closed(result, ErrorCode.STALE_RETRIEVAL)
        assert result.freshness_status is FreshnessStatus.STALE
        assert result.source is not None
        assert result.source.retrieved_at == STALE_RETRIEVED_AT

    def test_invalid_timestamp(self):
        service = _service_with(
            {
                MAYOR_URL: _ok_response(
                    MAYOR_URL,
                    _read_fixture("mayor_page.html"),
                    retrieved_at="yesterday-ish",
                )
            }
        )
        result = service.retrieve("구청장 누구야", evaluated_at=EVALUATED_AT)
        self._assert_fail_closed(result, ErrorCode.INVALID_TIMESTAMP)

    def test_missing_timestamp(self):
        service = _service_with(
            {
                MAYOR_URL: TransportResponse(
                    ok=True,
                    requested_url=MAYOR_URL,
                    final_url=MAYOR_URL,
                    status_code=200,
                    html=_read_fixture("mayor_page.html"),
                    retrieved_at="",
                )
            }
        )
        result = service.retrieve("구청장 누구야", evaluated_at=EVALUATED_AT)
        self._assert_fail_closed(result, ErrorCode.INVALID_TIMESTAMP)

    def test_unexpected_redirect_to_other_official_path(self):
        service = _service_with(
            {
                MAYOR_URL: _ok_response(
                    MAYOR_URL,
                    _read_fixture("mayor_page.html"),
                    final_url="https://bukgu.gwangju.kr/menu.es?mid=other",
                    redirected=True,
                )
            }
        )
        result = service.retrieve("구청장 누구야", evaluated_at=EVALUATED_AT)
        self._assert_fail_closed(result, ErrorCode.UNEXPECTED_REDIRECT)

    def test_external_origin_redirect(self):
        service = _service_with(
            {
                MAYOR_URL: _ok_response(
                    MAYOR_URL,
                    _read_fixture("mayor_page.html"),
                    final_url="https://evil.example/phish",
                    redirected=True,
                )
            }
        )
        result = service.retrieve("구청장 누구야", evaluated_at=EVALUATED_AT)
        self._assert_fail_closed(result, ErrorCode.EXTERNAL_ORIGIN)

    def test_non_allowlisted_final_url_without_redirect_flag(self):
        # External final URL still fails closed even if redirected=False.
        service = _service_with(
            {
                MAYOR_URL: TransportResponse(
                    ok=True,
                    requested_url=MAYOR_URL,
                    final_url="https://not-bukgu.example/",
                    status_code=200,
                    html=_read_fixture("mayor_page.html"),
                    retrieved_at=FRESH_RETRIEVED_AT,
                    redirected=False,
                )
            }
        )
        result = service.retrieve("구청장 누구야", evaluated_at=EVALUATED_AT)
        self._assert_fail_closed(result, ErrorCode.EXTERNAL_ORIGIN)

    def test_unsuccessful_never_guesses_fact(self):
        service = OfficialSourceFreshnessService()
        for question in ("날씨", "구청장 누구야", "관할 구역 이름"):
            result = service.retrieve(question, evaluated_at=EVALUATED_AT)
            if not result.success:
                assert result.fact is None
                assert result.error_code is not None
