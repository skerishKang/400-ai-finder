"""Phase-1 official-source freshness retrieval contracts (#1150).

Offline deterministic tests only. No live network, provider, Firecrawl,
or browser automation.
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
    assess_url_allowlist,
    classify_question,
    get_policy_for_fact,
    is_url_allowlisted,
)
from src.official_source.extraction import (
    AmbiguousValueError,
    FactAbsentError,
    MalformedHtmlError,
    SourceIdentityMismatchError,
    resolve_single_fact,
)
from src.official_source.freshness import InvalidTimestampError, parse_utc_timestamp
from src.official_source.normalize import normalize_fact_value
from src.official_source.policy import (
    OFFICIAL_HOST,
    allowlisted_urls,
    canonicalize_official_url,
    is_official_host,
)
from src.official_source.transport import LiveTransportNotAuthorized

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "official_source"
PACKAGE_DIR = REPO_ROOT / "src" / "official_source"

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
    content_type: str = "text/html; charset=utf-8",
) -> TransportResponse:
    return TransportResponse(
        ok=True,
        requested_url=url,
        final_url=final_url or url,
        status_code=200,
        title=title,
        html=html,
        content_type=content_type,
        retrieved_at=retrieved_at,
        redirected=redirected,
    )


def _service_with(responses: dict[str, TransportResponse]) -> OfficialSourceFreshnessService:
    return OfficialSourceFreshnessService(
        transport=MockOfficialSourceTransport(responses=responses)
    )


# ---------------------------------------------------------------------------
# Import / construction / transport selection — zero network
# ---------------------------------------------------------------------------


class TestNoNetworkBoundary:
    def test_import_and_construction_zero_network(self, monkeypatch):
        calls: list[object] = []

        def blocked(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("network call attempted")

        monkeypatch.setattr(socket.socket, "connect", blocked)
        monkeypatch.setattr(socket.socket, "connect_ex", blocked)

        service = OfficialSourceFreshnessService()
        assert service.transport_name == "mock_official_source"
        assert classify_question("현재 북구청장은 누구인가요?").supported is True
        _ = MockOfficialSourceTransport()
        _ = LiveTransportNotAuthorized()
        assert calls == []

    def test_package_has_no_network_imports(self):
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

    def test_live_transport_not_authorized(self):
        service = OfficialSourceFreshnessService(transport=LiveTransportNotAuthorized())
        result = service.retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        assert result.ok is False
        assert result.value is None
        assert result.failure_code is ErrorCode.TRANSPORT_ERROR


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class TestClassification:
    @pytest.mark.parametrize(
        "question",
        [
            "현재 북구청장은 누구인가요?",
            "지금 광주 북구청장은 누구야?",
            "현재 북구 구청장은 누구인가요?",
        ],
    )
    def test_supported_mayor(self, question: str):
        result = classify_question(question)
        assert result.supported is True
        assert result.fact_kind is FactKind.CURRENT_MAYOR
        assert result.failure_code is None
        assert result.fact_type == "current_mayor"

    @pytest.mark.parametrize(
        "question",
        [
            "북구청의 현재 기관명은 무엇인가요?",
            "현재 공식 자치구 명칭을 알려줘",
        ],
    )
    def test_supported_jurisdiction(self, question: str):
        result = classify_question(question)
        assert result.supported is True
        assert result.fact_kind is FactKind.JURISDICTION_NAME

    @pytest.mark.parametrize(
        "question",
        [
            "북구청에 민원 넣어줘",
            "여권 신청해줘",
            "쓰레기 신고해줘",
            "전국 구청장 목록을 알려줘",
        ],
    )
    def test_unsupported(self, question: str):
        result = classify_question(question)
        assert result.supported is False
        assert result.fact_kind is None
        assert result.failure_code is ErrorCode.UNSUPPORTED_QUESTION

    def test_regional_executive_is_supported_not_rejected(self):
        # Expanded #1150: city-mayor seat is a current-fact kind (values from retrieval).
        result = classify_question("광주시장은 누구야")
        assert result.supported is True
        assert result.fact_kind is FactKind.REGIONAL_EXECUTIVE

    @pytest.mark.parametrize("question", [None, 123, "", "   "])
    def test_invalid_input(self, question):
        result = classify_question(question)
        assert result.supported is False
        assert result.failure_code in {
            ErrorCode.INVALID_REQUEST,
            ErrorCode.UNSUPPORTED_QUESTION,
        }


# ---------------------------------------------------------------------------
# Allowlist policy
# ---------------------------------------------------------------------------


class TestAllowlistPolicy:
    def test_approved_canonical_accepted(self):
        from src.official_source.policy import all_policies

        for policy in all_policies():
            kind = policy.fact_kind
            assert is_url_allowlisted(policy.url, kind)
            assert assess_url_allowlist(policy.url, kind)["allowed"] is True
            assert OFFICIAL_HOST in policy.url

    @pytest.mark.parametrize(
        "url",
        [
            "https://bukgu.example.com/",
            "https://official-bukgu.example.net/",
            "https://approved-host.example.com.evil.test/",
            "https://user@bukgu.gwangju.kr/",
            "http://bukgu.gwangju.kr/",
            "javascript:alert(1)",
            "data:text/html,hi",
            "//bukgu.gwangju.kr/",
            "https://bukgu.gwangju.kr:8443/",
            "https://evil-bukgu.gwangju.kr.evil.test/",
            "https://not-bukgu.gwangju.kr/",
        ],
    )
    def test_rejects_unsafe_urls(self, url: str):
        assert is_url_allowlisted(url) is False
        assert assess_url_allowlist(url)["allowed"] is False

    def test_wrong_fact_path_rejected(self):
        mayor = get_policy_for_fact(FactKind.CURRENT_MAYOR)
        assert is_url_allowlisted(mayor.url, FactKind.JURISDICTION_NAME) is False

    def test_allowlisted_set_closed(self):
        assert len(allowlisted_urls()) == 2

    @pytest.mark.parametrize(
        "url",
        [
            "https://bukgu.gwangju.kr:notaport/",
            "https://bukgu.gwangju.kr:99999/",
            "https://[invalid/",
            r"https://bukgu.gwangju.kr\@evil.test/",
        ],
    )
    def test_malformed_port_and_authority_never_raise(self, url: str):
        assert assess_url_allowlist(url)["allowed"] is False
        assert canonicalize_official_url(url) is None
        assert is_official_host(url) is False
        assert is_url_allowlisted(url) is False


# ---------------------------------------------------------------------------
# Extraction / identity / placeholders
# ---------------------------------------------------------------------------


class TestExtraction:
    def test_mayor_fixture(self):
        fact, title, extractor = resolve_single_fact(
            _read_fixture("mayor_page.html"),
            fact_kind=FactKind.CURRENT_MAYOR,
            fact_marker="current_mayor",
            expected_title_tokens=("구청장",),
        )
        assert fact.value == "픽스처성명"
        assert "구청장" in title
        assert extractor

    def test_jurisdiction_fixture(self):
        fact, _title, _ = resolve_single_fact(
            _read_fixture("jurisdiction_page.html"),
            fact_kind=FactKind.JURISDICTION_NAME,
            fact_marker="jurisdiction_name",
            expected_title_tokens=("북구",),
        )
        assert "북구" in fact.value

    def test_malformed(self):
        with pytest.raises(MalformedHtmlError):
            resolve_single_fact(
                _read_fixture("malformed.html"),
                fact_kind=FactKind.CURRENT_MAYOR,
                fact_marker="current_mayor",
                expected_title_tokens=("구청장",),
            )

    def test_missing(self):
        with pytest.raises(FactAbsentError):
            resolve_single_fact(
                _read_fixture("missing_fact.html"),
                fact_kind=FactKind.CURRENT_MAYOR,
                fact_marker="current_mayor",
                expected_title_tokens=("구청장",),
            )

    def test_ambiguous(self):
        with pytest.raises(AmbiguousValueError):
            resolve_single_fact(
                _read_fixture("ambiguous_mayor.html"),
                fact_kind=FactKind.CURRENT_MAYOR,
                fact_marker="current_mayor",
                expected_title_tokens=("구청장",),
            )

    def test_wrong_identity(self):
        with pytest.raises(SourceIdentityMismatchError):
            resolve_single_fact(
                _read_fixture("wrong_identity.html"),
                fact_kind=FactKind.CURRENT_MAYOR,
                fact_marker="current_mayor",
                expected_title_tokens=("구청장",),
            )

    def test_placeholder_rejected(self):
        with pytest.raises(FactAbsentError):
            resolve_single_fact(
                _read_fixture("placeholder_mayor.html"),
                fact_kind=FactKind.CURRENT_MAYOR,
                fact_marker="current_mayor",
                expected_title_tokens=("구청장",),
            )

    def test_normalize_placeholder(self):
        assert normalize_fact_value(FactKind.CURRENT_MAYOR, "미정") is None
        assert normalize_fact_value(FactKind.CURRENT_MAYOR, "N/A") is None


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------


class TestFreshness:
    def test_fresh(self):
        a = assess_freshness(
            retrieved_at=FRESH_RETRIEVED_AT,
            max_age_seconds=7 * 24 * 3600,
            evaluated_at=EVALUATED_AT,
        )
        assert a.status is FreshnessStatus.FRESH
        assert a.age_seconds == 2 * 3600

    def test_stale(self):
        a = assess_freshness(
            retrieved_at=STALE_RETRIEVED_AT,
            max_age_seconds=7 * 24 * 3600,
            evaluated_at=EVALUATED_AT,
        )
        assert a.status is FreshnessStatus.STALE

    def test_missing_unknown(self):
        a = assess_freshness(
            retrieved_at="",
            max_age_seconds=100,
            evaluated_at=EVALUATED_AT,
        )
        assert a.status is FreshnessStatus.UNKNOWN

    def test_naive_invalid(self):
        with pytest.raises(InvalidTimestampError):
            parse_utc_timestamp("2026-07-15T12:00:00")

    def test_future_beyond_skew_invalid(self):
        with pytest.raises(InvalidTimestampError):
            assess_freshness(
                retrieved_at="2026-07-16T00:00:00Z",
                max_age_seconds=100,
                evaluated_at=EVALUATED_AT,
                clock_skew_seconds=60,
            )

    def test_unparseable_invalid(self):
        with pytest.raises(InvalidTimestampError):
            parse_utc_timestamp("yesterday")


# ---------------------------------------------------------------------------
# Mock retrieval success
# ---------------------------------------------------------------------------


class TestMockSuccess:
    def test_mayor_success_public_fields(self):
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
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        assert result.ok is True
        assert result.success is True
        assert result.failure_code is None
        assert result.fact_type == "current_mayor"
        assert result.value == "픽스처성명"
        assert result.source_url == MAYOR_URL
        assert result.source_title
        assert result.retrieved_at == FRESH_RETRIEVED_AT
        assert result.freshness_status is FreshnessStatus.FRESH
        assert result.public_safe_message == ""
        payload = result.to_dict()
        assert payload["ok"] is True
        assert payload["value"] == "픽스처성명"
        assert "cookie" not in str(payload).lower()
        assert "authorization" not in str(payload).lower()

    def test_jurisdiction_success(self):
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
            "북구청의 현재 기관명은 무엇인가요?", evaluated_at=EVALUATED_AT
        )
        assert result.ok is True
        assert result.fact_kind is FactKind.JURISDICTION_NAME
        assert "북구" in (result.value or "")

    def test_deterministic_repeat(self):
        service = _service_with(
            {MAYOR_URL: _ok_response(MAYOR_URL, _read_fixture("mayor_page.html"))}
        )
        a = service.retrieve("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT)
        b = service.retrieve("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT)
        assert a.to_dict() == b.to_dict()


# ---------------------------------------------------------------------------
# Fail-closed taxonomy
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_error_codes_closed(self):
        required = {
            "unsupported_question",
            "invalid_request",
            "source_not_allowlisted",
            "external_redirect",
            "transport_timeout",
            "transport_error",
            "http_error",
            "invalid_content_type",
            "empty_content",
            "malformed_content",
            "source_identity_mismatch",
            "fact_not_found",
            "ambiguous_fact",
            "invalid_timestamp",
            "stale_source",
        }
        assert required.issubset(ERROR_CODES)

    def _assert_fail(self, result: OfficialSourceResult, code: ErrorCode):
        assert result.ok is False
        assert result.value is None
        assert result.fact is None
        assert result.failure_code is code
        assert result.public_safe_message
        assert "api_key" not in result.public_safe_message.lower()
        assert "cookie" not in result.public_safe_message.lower()

    def test_unsupported_question(self):
        result = OfficialSourceFreshnessService().retrieve(
            "쓰레기 신고해줘", evaluated_at=EVALUATED_AT
        )
        self._assert_fail(result, ErrorCode.UNSUPPORTED_QUESTION)

    def test_transport_missing(self):
        result = OfficialSourceFreshnessService().retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        self._assert_fail(result, ErrorCode.TRANSPORT_ERROR)

    def test_timeout(self):
        service = _service_with(
            {
                MAYOR_URL: TransportResponse(
                    ok=False,
                    requested_url=MAYOR_URL,
                    timed_out=True,
                    error="timeout",
                )
            }
        )
        self._assert_fail(
            service.retrieve("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT),
            ErrorCode.TRANSPORT_TIMEOUT,
        )

    def test_transport_exception(self):
        service = _service_with(
            {
                MAYOR_URL: TransportResponse(
                    ok=False,
                    requested_url=MAYOR_URL,
                    raise_exception=True,
                    exception_message="boom",
                )
            }
        )
        self._assert_fail(
            service.retrieve("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT),
            ErrorCode.TRANSPORT_ERROR,
        )

    def test_http_error(self):
        service = _service_with(
            {
                MAYOR_URL: TransportResponse(
                    ok=False,
                    requested_url=MAYOR_URL,
                    status_code=500,
                    error="server",
                )
            }
        )
        self._assert_fail(
            service.retrieve("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT),
            ErrorCode.HTTP_ERROR,
        )

    def test_wrong_content_type(self):
        service = _service_with(
            {
                MAYOR_URL: _ok_response(
                    MAYOR_URL,
                    _read_fixture("mayor_page.html"),
                    content_type="application/json",
                )
            }
        )
        self._assert_fail(
            service.retrieve("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT),
            ErrorCode.INVALID_CONTENT_TYPE,
        )

    def test_empty_body(self):
        service = _service_with(
            {
                MAYOR_URL: TransportResponse(
                    ok=True,
                    requested_url=MAYOR_URL,
                    final_url=MAYOR_URL,
                    status_code=200,
                    html="   ",
                    content_type="text/html",
                    retrieved_at=FRESH_RETRIEVED_AT,
                )
            }
        )
        self._assert_fail(
            service.retrieve("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT),
            ErrorCode.EMPTY_CONTENT,
        )

    def test_oversized_body(self):
        huge = "<html><body>" + ("x" * 600_000) + "</body></html>"
        service = _service_with({MAYOR_URL: _ok_response(MAYOR_URL, huge)})
        self._assert_fail(
            service.retrieve("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT),
            ErrorCode.MALFORMED_CONTENT,
        )

    def test_malformed_html(self):
        service = _service_with(
            {MAYOR_URL: _ok_response(MAYOR_URL, _read_fixture("malformed.html"))}
        )
        self._assert_fail(
            service.retrieve("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT),
            ErrorCode.MALFORMED_CONTENT,
        )

    def test_fact_not_found(self):
        service = _service_with(
            {MAYOR_URL: _ok_response(MAYOR_URL, _read_fixture("missing_fact.html"))}
        )
        self._assert_fail(
            service.retrieve("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT),
            ErrorCode.FACT_NOT_FOUND,
        )

    def test_ambiguous(self):
        service = _service_with(
            {MAYOR_URL: _ok_response(MAYOR_URL, _read_fixture("ambiguous_mayor.html"))}
        )
        self._assert_fail(
            service.retrieve("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT),
            ErrorCode.AMBIGUOUS_FACT,
        )

    def test_wrong_identity(self):
        service = _service_with(
            {MAYOR_URL: _ok_response(MAYOR_URL, _read_fixture("wrong_identity.html"))}
        )
        self._assert_fail(
            service.retrieve("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT),
            ErrorCode.SOURCE_IDENTITY_MISMATCH,
        )

    def test_stale(self):
        service = _service_with(
            {
                MAYOR_URL: _ok_response(
                    MAYOR_URL,
                    _read_fixture("mayor_page.html"),
                    retrieved_at=STALE_RETRIEVED_AT,
                )
            }
        )
        result = service.retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        self._assert_fail(result, ErrorCode.STALE_SOURCE)
        assert result.freshness_status is FreshnessStatus.STALE

    def test_invalid_timestamp(self):
        service = _service_with(
            {
                MAYOR_URL: _ok_response(
                    MAYOR_URL,
                    _read_fixture("mayor_page.html"),
                    retrieved_at="not-a-ts",
                )
            }
        )
        result = service.retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        self._assert_fail(result, ErrorCode.INVALID_TIMESTAMP)
        assert result.freshness_status is FreshnessStatus.INVALID

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
        result = service.retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        self._assert_fail(result, ErrorCode.INVALID_TIMESTAMP)

    def test_external_redirect(self):
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
        self._assert_fail(
            service.retrieve("현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT),
            ErrorCode.EXTERNAL_REDIRECT,
        )

    def test_explicit_fact_kind_request(self):
        service = _service_with(
            {MAYOR_URL: _ok_response(MAYOR_URL, _read_fixture("mayor_page.html"))}
        )
        result = service.retrieve_request(
            OfficialSourceRequest(
                question="ignored",
                fact_kind=FactKind.CURRENT_MAYOR,
                evaluated_at=EVALUATED_AT,
            )
        )
        assert result.ok is True
        assert result.value == "픽스처성명"


# ---------------------------------------------------------------------------
# Exact requested / final URL boundary (PR-readiness)
# ---------------------------------------------------------------------------


class TestExactResponseUrls:
    def _fail(
        self,
        result: OfficialSourceResult,
        code: ErrorCode,
    ) -> None:
        assert result.ok is False
        assert result.value is None
        assert result.fact is None
        assert result.failure_code is code
        assert result.public_safe_message
        # No raw transport error leakage.
        assert "boom" not in result.public_safe_message.lower()
        assert "traceback" not in result.public_safe_message.lower()
        assert "exception" not in result.public_safe_message.lower()

    def _mayor_service(self, response: TransportResponse) -> OfficialSourceFreshnessService:
        # Key mock by policy URL (what service requests); response fields vary.
        return _service_with({MAYOR_URL: response})

    def test_blank_requested_url(self):
        response = _ok_response(MAYOR_URL, _read_fixture("mayor_page.html"))
        response = TransportResponse(
            ok=True,
            requested_url="",
            final_url=MAYOR_URL,
            status_code=200,
            html=response.html,
            content_type=response.content_type,
            retrieved_at=FRESH_RETRIEVED_AT,
        )
        result = self._mayor_service(response).retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        self._fail(result, ErrorCode.SOURCE_NOT_ALLOWLISTED)

    def test_mismatched_requested_url(self):
        response = _ok_response(
            "https://bukgu.gwangju.kr/menu.es?mid=wrong",
            _read_fixture("mayor_page.html"),
            final_url=MAYOR_URL,
        )
        result = self._mayor_service(response).retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        self._fail(result, ErrorCode.SOURCE_NOT_ALLOWLISTED)

    def test_same_host_wrong_requested_path(self):
        wrong = "https://bukgu.gwangju.kr/menu.es?mid=a10406070000"
        response = _ok_response(
            wrong, _read_fixture("mayor_page.html"), final_url=MAYOR_URL
        )
        result = self._mayor_service(response).retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        self._fail(result, ErrorCode.SOURCE_NOT_ALLOWLISTED)

    def test_external_requested_url(self):
        response = _ok_response(
            "https://evil.example/phish",
            _read_fixture("mayor_page.html"),
            final_url=MAYOR_URL,
        )
        result = self._mayor_service(response).retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        self._fail(result, ErrorCode.SOURCE_NOT_ALLOWLISTED)

    def test_blank_final_url(self):
        response = TransportResponse(
            ok=True,
            requested_url=MAYOR_URL,
            final_url="",
            status_code=200,
            html=_read_fixture("mayor_page.html"),
            content_type="text/html",
            retrieved_at=FRESH_RETRIEVED_AT,
        )
        result = self._mayor_service(response).retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        self._fail(result, ErrorCode.SOURCE_NOT_ALLOWLISTED)

    def test_same_host_wrong_final_path_redirected_false(self):
        wrong = "https://bukgu.gwangju.kr/menu.es?mid=a10406070000"
        response = _ok_response(
            MAYOR_URL,
            _read_fixture("mayor_page.html"),
            final_url=wrong,
            redirected=False,
        )
        result = self._mayor_service(response).retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        self._fail(result, ErrorCode.SOURCE_NOT_ALLOWLISTED)

    def test_same_host_wrong_final_path_redirected_true(self):
        wrong = "https://bukgu.gwangju.kr/menu.es?mid=a10406070000"
        response = _ok_response(
            MAYOR_URL,
            _read_fixture("mayor_page.html"),
            final_url=wrong,
            redirected=True,
        )
        result = self._mayor_service(response).retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        self._fail(result, ErrorCode.SOURCE_NOT_ALLOWLISTED)

    def test_external_final_redirected_false(self):
        response = _ok_response(
            MAYOR_URL,
            _read_fixture("mayor_page.html"),
            final_url="https://evil.example/phish",
            redirected=False,
        )
        result = self._mayor_service(response).retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        self._fail(result, ErrorCode.SOURCE_NOT_ALLOWLISTED)

    def test_external_final_redirected_true(self):
        response = _ok_response(
            MAYOR_URL,
            _read_fixture("mayor_page.html"),
            final_url="https://evil.example/phish",
            redirected=True,
        )
        result = self._mayor_service(response).retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        self._fail(result, ErrorCode.EXTERNAL_REDIRECT)

    def test_exact_final_url_success(self):
        response = _ok_response(
            MAYOR_URL,
            _read_fixture("mayor_page.html"),
            final_url=MAYOR_URL,
            redirected=False,
        )
        result = self._mayor_service(response).retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        assert result.ok is True
        assert result.value == "픽스처성명"

    def test_exact_final_url_success_with_redirected_true(self):
        # redirected flag alone does not block exact canonical equality.
        response = _ok_response(
            MAYOR_URL,
            _read_fixture("mayor_page.html"),
            final_url=MAYOR_URL,
            redirected=True,
        )
        result = self._mayor_service(response).retrieve(
            "현재 북구청장은 누구인가요?", evaluated_at=EVALUATED_AT
        )
        assert result.ok is True
        assert result.value == "픽스처성명"


class TestPhase1DocumentationContract:
    def test_package_docs_state_mock_and_no_live_validation(self):
        init_text = (PACKAGE_DIR / "__init__.py").read_text(encoding="utf-8")
        extract_text = (PACKAGE_DIR / "extraction.py").read_text(encoding="utf-8")
        combined = init_text + "\n" + extract_text
        assert "mock-fixture" in combined or "mock fixture" in combined.lower()
        assert "no live official-page validation was executed" in combined
        assert (
            "live official DOM parsing is not yet verified" in combined
            or "live official DOM parsing not yet verified" in combined
            or "does not prove parsing against the live official mayor page" in combined
        )
        # Must not claim readiness (allow explicit "not live-ready" denials).
        lowered = combined.lower()
        assert "is live-ready" not in lowered
        assert "is production-ready" not in lowered
        assert "answer-time live retrieval complete" not in lowered
        assert "not live-ready" in lowered or "not production-ready" in lowered
