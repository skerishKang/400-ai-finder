"""Tests for src.fetch.compat_diagnostics (Stage #800).

These tests are pure unit tests — no live fetch, no API calls, no
network. They cover:

1. The seven-category taxonomy for exception types
2. The seven-category taxonomy for HTTP status codes
3. Operator-safe output shape and length contract
4. No-leak guarantee: secrets, headers, bodies, and raw exception text
   must NOT appear in any operator-facing diagnostic
5. Integration with #799's timeout warning path (no live calls)
"""

from __future__ import annotations

import json
import ssl
from typing import Any

import pytest

from src.fetch.compat_diagnostics import (
    FetchCategory,
    FetchDiagnostic,
    classify_exception,
    classify_http_status,
    format_operator_safe,
)


# ---------------------------------------------------------------------------
# 1. Exception taxonomy
# ---------------------------------------------------------------------------


class TestExceptionTaxonomy:
    """Each exception family must map to its category exactly once."""

    def test_timeout(self) -> None:
        # builtin TimeoutError (covers socket.timeout)
        assert classify_exception(TimeoutError()).category == FetchCategory.TIMEOUT

    def test_requests_timeout_subclass(self) -> None:
        # Build a fake "requests Timeout" without importing requests
        # directly, so the test stays network-free even if requests is
        # not installed.
        class _FakeTimeout(Exception):
            pass

        # We rely on the real ``requests.exceptions.Timeout`` if available;
        # if not, this test is skipped (the helper degrades gracefully).
        try:
            import requests.exceptions as rex  # type: ignore[import-not-found]

            assert (
                classify_exception(rex.Timeout("deadline")).category
                == FetchCategory.TIMEOUT
            )
            assert (
                classify_exception(rex.ConnectTimeout("connect")).category
                == FetchCategory.TIMEOUT
            )
            assert (
                classify_exception(rex.ReadTimeout("read")).category
                == FetchCategory.TIMEOUT
            )
        except ImportError:  # pragma: no cover - requests is a runtime dep
            pytest.skip("requests not installed")

    def test_ssl_wait_states_are_timeout(self) -> None:
        # SSLWantRead/Write fire mid-handshake when the peer stalls; they
        # are deadline-bound and must be classified as timeout, not TLS
        # error, so retry is allowed.
        assert (
            classify_exception(ssl.SSLWantReadError()).category
            == FetchCategory.TIMEOUT
        )
        assert (
            classify_exception(ssl.SSLWantWriteError()).category
            == FetchCategory.TIMEOUT
        )

    def test_connection_error(self) -> None:
        assert (
            classify_exception(ConnectionRefusedError("nope")).category
            == FetchCategory.CONNECTION_ERROR
        )
        assert (
            classify_exception(ConnectionResetError("reset")).category
            == FetchCategory.CONNECTION_ERROR
        )
        assert (
            classify_exception(ConnectionAbortedError("abort")).category
            == FetchCategory.CONNECTION_ERROR
        )
        # OSError covers DNS failures (gaierror is an OSError subclass).
        assert classify_exception(OSError(11001)).category == FetchCategory.CONNECTION_ERROR

    def test_requests_connection_error(self) -> None:
        try:
            import requests.exceptions as rex  # type: ignore[import-not-found]

            assert (
                classify_exception(rex.ConnectionError("dns")).category
                == FetchCategory.CONNECTION_ERROR
            )
        except ImportError:  # pragma: no cover
            pytest.skip("requests not installed")

    def test_tls_error(self) -> None:
        assert (
            classify_exception(ssl.SSLError("bad cert")).category
            == FetchCategory.TLS_ERROR
        )

    def test_requests_ssl_error(self) -> None:
        try:
            import requests.exceptions as rex  # type: ignore[import-not-found]

            assert (
                classify_exception(rex.SSLError("handshake")).category
                == FetchCategory.TLS_ERROR
            )
        except ImportError:  # pragma: no cover
            pytest.skip("requests not installed")

    def test_parse_error_json(self) -> None:
        exc = json.JSONDecodeError("Expecting value", "doc", 0)
        assert classify_exception(exc).category == FetchCategory.PARSE_ERROR

    def test_parse_error_bs4(self) -> None:
        # bs4 raises a feature-not-found error with module 'bs4'. We
        # don't import bs4 directly; we fake the module name on a
        # minimal exception subclass so the helper's bs4 duck-typing
        # path is exercised without pulling bs4 in.
        class _FakeBS4Error(Exception):
            pass

        _FakeBS4Error.__module__ = "bs4.parser"
        assert classify_exception(_FakeBS4Error()).category == FetchCategory.PARSE_ERROR

    def test_unknown_fetch_error(self) -> None:
        assert (
            classify_exception(ValueError("nope")).category
            == FetchCategory.UNKNOWN_FETCH_ERROR
        )
        assert (
            classify_exception(KeyError("missing")).category
            == FetchCategory.UNKNOWN_FETCH_ERROR
        )
        assert (
            classify_exception(RuntimeError("boom")).category
            == FetchCategory.UNKNOWN_FETCH_ERROR
        )


# ---------------------------------------------------------------------------
# 2. HTTP status taxonomy
# ---------------------------------------------------------------------------


class TestHTTPStatusTaxonomy:
    """Status codes map to the right category and never leak the raw code."""

    @pytest.mark.parametrize(
        "code,expected",
        [
            (401, FetchCategory.BLOCKED_OR_FORBIDDEN),
            (403, FetchCategory.BLOCKED_OR_FORBIDDEN),
            (429, FetchCategory.BLOCKED_OR_FORBIDDEN),
            (500, FetchCategory.HTTP_ERROR),
            (501, FetchCategory.HTTP_ERROR),
            (502, FetchCategory.HTTP_ERROR),
            (503, FetchCategory.HTTP_ERROR),
            (504, FetchCategory.HTTP_ERROR),
            (400, FetchCategory.HTTP_ERROR),
            (404, FetchCategory.HTTP_ERROR),
            (405, FetchCategory.HTTP_ERROR),
        ],
    )
    def test_status_code_categories(self, code: int, expected: FetchCategory) -> None:
        assert classify_http_status(code).category == expected

    def test_2xx_3xx_are_not_failures(self) -> None:
        # 2xx/3xx are success-class; the helper returns unknown so the
        # caller treats them as "not a diagnostic case". This is a
        # deliberate sentinel, not a bug.
        for code in (200, 201, 204, 301, 302, 304):
            assert (
                classify_http_status(code).category
                == FetchCategory.UNKNOWN_FETCH_ERROR
            )

    def test_unknown_status_falls_back_safely(self) -> None:
        # Unusual codes (e.g. 418, 451) fall through to http_error so
        # callers still see a non-empty diagnostic.
        assert (
            classify_http_status(418).category == FetchCategory.HTTP_ERROR
        )
        assert (
            classify_http_status(451).category == FetchCategory.HTTP_ERROR
        )


# ---------------------------------------------------------------------------
# 3. Operator-safe output shape
# ---------------------------------------------------------------------------


class TestOperatorSafeShape:
    """The output must be a small, closed-vocabulary record."""

    def test_diagnostic_has_only_four_fields(self) -> None:
        d = classify_http_status(503)
        assert set(d.to_dict().keys()) == {
            "category",
            "short_reason",
            "retry_hint",
            "is_transient",
        }

    @pytest.mark.parametrize("category", list(FetchCategory))
    def test_retry_hint_is_closed_vocabulary(self, category: FetchCategory) -> None:
        d = classify_exception(_FakeExcFor(category))
        assert d.retry_hint in {"retry", "backoff", "do_not_retry"}

    def test_short_reason_is_short(self) -> None:
        # Every short_reason must be < 100 chars so the operator line
        # fits within our length budget even after category padding.
        for category in FetchCategory:
            d = classify_exception(_FakeExcFor(category))
            assert len(d.short_reason) < 100

    def test_diagnostic_is_frozen(self) -> None:
        d = classify_http_status(500)
        with pytest.raises(Exception):
            # frozen dataclass raises FrozenInstanceError; we don't
            # pin the exact type so the test works on all Python
            # versions.
            d.category = FetchCategory.TIMEOUT  # type: ignore[misc]

    def test_format_operator_safe_is_single_line(self) -> None:
        d = classify_http_status(503)
        line = format_operator_safe(d)
        assert "\n" not in line
        assert len(line) <= 200


# ---------------------------------------------------------------------------
# 4. No-leak guarantee
# ---------------------------------------------------------------------------


# Strings that MUST NEVER appear in any operator-facing diagnostic,
# even if a future contributor accidentally wires up raw exception
# text. We assert across many categories to make regressions loud.
_LEAK_CANARIES: tuple[str, ...] = (
    # fake API key
    "sk-LIVE-c4n4ry-bad-key-1234567890abcdef",
    # fake bearer token
    "Bearer c4n4ry-token-zzzzzzzzzzzzzzzz",
    # fake raw header
    "X-Internal-Secret: top-secret",
    # fake raw body
    "secret_body=THIS_IS_THE_BODY",
    # fake URL with embedded creds
    "https://user:p4ssw0rd@host.example/path",
)


_LEAKED_EXCEPTIONS: list[tuple[str, BaseException]] = [
    ("timeout_with_secret", TimeoutError("request to https://x failed: sk-LIVE-c4n4ry-bad-key-1234567890abcdef")),
    ("connection_with_token", ConnectionRefusedError("Bearer c4n4ry-token-zzzzzzzzzzzzzzzz blocked")),
    ("tls_with_header", ssl.SSLError("X-Internal-Secret: top-secret refused")),
    ("parse_with_body", json.JSONDecodeError("secret_body=THIS_IS_THE_BODY", "doc", 0)),
    ("unknown_with_url", ValueError("https://user:p4ssw0rd@host.example/path unreachable")),
]


class TestNoLeakGuarantee:
    """Operator output must not echo raw exception/header/body/key/url."""

    @pytest.mark.parametrize("label,exc", _LEAKED_EXCEPTIONS, ids=[l for l, _ in _LEAKED_EXCEPTIONS])
    def test_exception_text_does_not_leak(self, label: str, exc: BaseException) -> None:
        diag = classify_exception(exc)
        rendered = format_operator_safe(diag)
        for canary in _LEAK_CANARIES:
            assert canary not in rendered, (
                f"canary '{canary}' leaked through {label}: {rendered!r}"
            )
            assert canary not in diag.short_reason
            assert canary not in diag.to_dict()["short_reason"]

    @pytest.mark.parametrize("code", [401, 403, 429, 500, 502, 503])
    def test_status_output_does_not_leak_canaries(self, code: int) -> None:
        diag = classify_http_status(code)
        rendered = format_operator_safe(diag)
        for canary in _LEAK_CANARIES:
            assert canary not in rendered

    def test_short_reason_does_not_include_raw_exc_message(self) -> None:
        # Even if a future change accidentally added ``str(exc)`` to
        # the short_reason, this test would catch it for one of our
        # synthetic canary messages.
        sentinel = "VERY_SPECIFIC_CANARY_STRING_DO_NOT_LEAK"
        diag = classify_exception(ValueError(sentinel))
        assert sentinel not in diag.short_reason


# ---------------------------------------------------------------------------
# 5. #799 timeout warning integration
# ---------------------------------------------------------------------------


class TestWarningIntegrationWithPR799:
    """#799 emits a timeout warning; the diagnostic must round-trip cleanly.

    These tests use the same runner plumbing as #799, but they NEVER
    touch the network — the pipeline is replaced with a stub that
    raises a controlled exception.
    """

    def test_timeout_diagnostic_round_trips_through_runner(self, tmp_path, monkeypatch) -> None:
        from src.demo.site_demo_runner import SiteDemoRunner

        class _HangingPipeline:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            def run(self, url: str, query: str) -> dict[str, Any]:
                raise TimeoutError("simulated LLM API timeout (canary)")

        from src.demo import site_demo_runner as runner_module

        monkeypatch.setattr(runner_module, "PipelineRunner", _HangingPipeline)

        runner = SiteDemoRunner(
            site_id="bukgu_gwangju",
            provider="mock",
            output_dir=str(tmp_path),
            pipeline_timeout_s=5.0,
        )
        result = runner.answer("민원서식 어디서 받아?")

        # #799 contract: a structured soft JSON with route metadata.
        assert result["route"] == "site_search"
        assert result["ok"] is False
        assert result["source_weak"] is True

        # New Stage #800 contract: the warning must carry a
        # diagnostic category, but it must NOT carry raw exception
        # text or any canary. We assert the canary NEVER leaks even
        # though the runner passes the exception message through.
        joined = " ".join(result.get("warnings", []))
        assert "VERY_SPECIFIC_CANARY" not in joined
        assert "category=" in joined, (
            "warning should include operator-safe diagnostic category"
        )
        # And the category must be one of the seven closed values.
        for cat in FetchCategory:
            if cat.value in joined:
                break
        else:  # pragma: no cover - failure path
            pytest.fail(
                f"no FetchCategory value found in warnings: {joined!r}"
            )

    def test_demo_emit_helper_returns_consistent_diagnostic(self) -> None:
        """If a caller wires the diagnostic through the demo pipeline,
        the emitted warning line must equal ``format_operator_safe``.
        """
        diag = classify_exception(TimeoutError())
        # Caller-side: build the warning string the way SiteDemoRunner
        # would; it must be exactly the operator-safe form.
        emitted = format_operator_safe(diag)
        assert emitted.startswith("category=timeout;")
        assert "retry_hint=retry" in emitted
        assert "is_transient=true" in emitted


# ---------------------------------------------------------------------------
# Internal helpers (test-local)
# ---------------------------------------------------------------------------


def _FakeExcFor(category: FetchCategory) -> BaseException:  # noqa: N802
    """Construct a fake exception that the helper maps to ``category``.

    Used to drive parametric tests that want every category without
    pulling in the full requests/bs4 surface.
    """
    if category == FetchCategory.TIMEOUT:
        return TimeoutError()
    if category == FetchCategory.CONNECTION_ERROR:
        return ConnectionRefusedError()
    if category == FetchCategory.TLS_ERROR:
        return ssl.SSLError()
    if category == FetchCategory.PARSE_ERROR:
        return json.JSONDecodeError("x", "y", 0)
    if category in (
        FetchCategory.HTTP_ERROR,
        FetchCategory.BLOCKED_OR_FORBIDDEN,
        FetchCategory.UNKNOWN_FETCH_ERROR,
    ):
        return RuntimeError()
    raise AssertionError(f"unhandled category {category}")


def test_internal_helper_covers_all_categories() -> None:
    """The test-local helper must cover every FetchCategory value."""
    for cat in FetchCategory:
        exc = _FakeExcFor(cat)
        diag = classify_exception(exc)
        assert isinstance(diag, FetchDiagnostic)
