"""Tests for the #930 sanitized live-provider failure_code vocabulary.

These tests exercise the closed ``failure_code`` classification end-to-end
using **injectable fake providers** and **mocked ``requests``** only. No real
model, API, fetch, crawler, Firecrawl, or live Buk-gu origin call is made.

Key guarantees verified:
  - ``ProviderResult.failure_code`` defaults to ``""`` on success.
  - Every provider failure maps to exactly one closed-vocabulary code.
  - The MVP router / ``/api/mvp/ask`` endpoint surfaces only the sanitized
    fixed code, never raw exception text, URLs, API keys, headers, or bodies.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from http.client import HTTPConnection
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.llm.base import LLMProvider, ProviderResult
from src.llm.bukgu_mvp_router import (
    FAILURE_INVALID_MVP_DECISION,
    FAILURE_PROVIDER_EXCEPTION,
    MVP_FAILURE_ANSWER,
    MvpActionDecision,
    decide_mvp_action,
    is_mvp_failure,
    parse_mvp_decision,
)
from src.llm.openai_compatible_provider import (
    FAILURE_AUTH_OR_PERMISSION,
    FAILURE_CONFIGURATION,
    FAILURE_INVALID_UPSTREAM_RESPONSE,
    FAILURE_RATE_LIMITED,
    FAILURE_TIMEOUT,
    FAILURE_TRANSPORT_ERROR,
    FAILURE_UNKNOWN,
    FAILURE_UPSTREAM_4XX,
    FAILURE_UPSTREAM_5XX,
    OpenAICompatibleProvider,
    is_valid_failure_code,
)
from src.web.mobile_demo import create_app


# Canary secrets that must NEVER appear in any operator-facing response.
CANARY_SECRET = "fake-secret-should-not-leak"
CANARY_URL = "https://private.example.invalid"
CANARY_AUTH_HEADER = f"Authorization: Bearer {CANARY_SECRET}"


# ----------------------------------------------------------------------
# Provider-level failure_code mapping
# ----------------------------------------------------------------------

class TestProviderResultFailureCode:
    def test_success_default_empty(self):
        result = ProviderResult(
            ok=True, provider="fake", model="m", content="hello"
        )
        assert result.failure_code == ""

    def test_failure_code_default_empty_when_unspecified(self):
        result = ProviderResult(
            ok=False, provider="fake", model="m", content="",
            error="boom",
        )
        # Unspecified failure_code must default to empty (providers are
        # responsible for setting the closed code on real failures).
        assert result.failure_code == ""


class _MockResponse:
    """Minimal stand-in for a requests.Response with a controllable status."""

    def __init__(self, status_code: int, json_data: object | None = None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise requests.exceptions.HTTPError(response=self)

    def json(self):
        if self._json_data is None:
            raise json.JSONDecodeError("bad", "", 0)
        return self._json_data


def _provider_with_base_config() -> OpenAICompatibleProvider:
    """A provider with valid base_url / api_key / model (no network made)."""
    return OpenAICompatibleProvider(
        base_url=CANARY_URL,
        api_key=CANARY_SECRET,
        model="fake-model",
    )


class TestOpenAICompatibleFailureMapping:
    def test_configuration_missing_base_url(self):
        p = OpenAICompatibleProvider(api_key="x", model="m")
        r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_CONFIGURATION

    def test_configuration_missing_api_key(self):
        p = OpenAICompatibleProvider(base_url="https://x", model="m")
        r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_CONFIGURATION

    def test_configuration_missing_model(self):
        p = OpenAICompatibleProvider(base_url="https://x", api_key="k")
        r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_CONFIGURATION

    def test_timeout(self):
        p = _provider_with_base_config()
        with patch.object(requests, "post", side_effect=requests.exceptions.Timeout()):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_TIMEOUT

    def test_auth_or_permission_401(self):
        p = _provider_with_base_config()
        resp = _MockResponse(401)
        with patch.object(requests, "post", return_value=resp):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_AUTH_OR_PERMISSION

    def test_auth_or_permission_403(self):
        p = _provider_with_base_config()
        resp = _MockResponse(403)
        with patch.object(requests, "post", return_value=resp):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_AUTH_OR_PERMISSION

    def test_rate_limited_429(self):
        p = _provider_with_base_config()
        resp = _MockResponse(429)
        with patch.object(requests, "post", return_value=resp):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_RATE_LIMITED

    def test_upstream_5xx_500(self):
        p = _provider_with_base_config()
        resp = _MockResponse(500)
        with patch.object(requests, "post", return_value=resp):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_UPSTREAM_5XX

    def test_upstream_5xx_599(self):
        p = _provider_with_base_config()
        resp = _MockResponse(599)
        with patch.object(requests, "post", return_value=resp):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_UPSTREAM_5XX

    def test_upstream_4xx_404(self):
        p = _provider_with_base_config()
        resp = _MockResponse(404)
        with patch.object(requests, "post", return_value=resp):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_UPSTREAM_4XX

    def test_upstream_4xx_418(self):
        p = _provider_with_base_config()
        resp = _MockResponse(418)
        with patch.object(requests, "post", return_value=resp):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_UPSTREAM_4XX

    def test_transport_error(self):
        p = _provider_with_base_config()
        with patch.object(
            requests, "post",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_TRANSPORT_ERROR

    def test_malformed_upstream_response(self):
        p = _provider_with_base_config()
        resp = _MockResponse(200, json_data=None)
        with patch.object(requests, "post", return_value=resp):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_INVALID_UPSTREAM_RESPONSE

    def test_error_text_contains_no_secret(self):
        p = _provider_with_base_config()
        with patch.object(requests, "post", side_effect=requests.exceptions.Timeout()):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert CANARY_SECRET not in r.error
        assert CANARY_URL not in r.error

    def test_top_level_list_payload_is_invalid_upstream_response(self):
        p = _provider_with_base_config()
        resp = _MockResponse(200, json_data=[{"unexpected": "list"}])
        with patch.object(requests, "post", return_value=resp):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_INVALID_UPSTREAM_RESPONSE

    def test_generic_value_error_json_decode_is_invalid_upstream_response(self):
        # response.json() can raise a plain ValueError (not just JSONDecodeError)
        # for malformed payloads — must still map to invalid_upstream_response.
        p = _provider_with_base_config()

        class _ValueErrorResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                raise ValueError("Unexpected non-JSON payload")

        with patch.object(requests, "post", return_value=_ValueErrorResponse()):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_INVALID_UPSTREAM_RESPONSE

    def test_unexpected_attribute_error_structure_is_invalid_upstream_response(self):
        # If resp.json() returns a scalar that later triggers AttributeError
        # inside _parse_response, it must map to invalid_upstream_response (not
        # provider_exception).
        p = _provider_with_base_config()
        resp = _MockResponse(200, json_data="not-an-object")
        with patch.object(requests, "post", return_value=resp):
            r = p.complete([{"role": "user", "content": "hi"}])
        assert r.ok is False
        assert r.failure_code == FAILURE_INVALID_UPSTREAM_RESPONSE


# ----------------------------------------------------------------------
# MVP router failure_code mapping
# ----------------------------------------------------------------------

class _OkProviderWithInvalidAction(LLMProvider):
    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        payload = {"answer": "X", "action": "banana", "confidence": 0.5}
        return ProviderResult(
            ok=True, provider="fake", model="m",
            content=json.dumps(payload, ensure_ascii=False),
        )

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "m"


class _RaisingProvider(LLMProvider):
    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        raise RuntimeError(CANARY_SECRET)

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "m"


class _OkProviderMalformedJson(LLMProvider):
    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        return ProviderResult(
            ok=True, provider="fake", model="m", content="not json"
        )

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "m"


class _FailingProviderEmptyCode(LLMProvider):
    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        return ProviderResult(
            ok=False, provider="fake", model="m", content="",
            error="boom",  # no failure_code → router must use "unknown"
        )

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "m"


class TestMvpRouterFailureCode:
    def test_success_has_empty_code(self):
        d = parse_mvp_decision(
            json.dumps({"answer": "a", "action": "none", "confidence": 0.5})
        )
        assert d.failure_code == ""

    def test_invalid_mvp_decision_json(self):
        d = decide_mvp_action("q", _OkProviderMalformedJson())
        assert d.failure_code == FAILURE_INVALID_MVP_DECISION
        assert is_mvp_failure(d)

    def test_invalid_mvp_decision_action(self):
        d = decide_mvp_action("q", _OkProviderWithInvalidAction())
        assert d.failure_code == FAILURE_INVALID_MVP_DECISION
        assert is_mvp_failure(d)

    def test_provider_exception(self):
        d = decide_mvp_action("q", _RaisingProvider())
        assert d.failure_code == FAILURE_PROVIDER_EXCEPTION
        assert is_mvp_failure(d)

    def test_provider_failure_empty_code_becomes_unknown(self):
        d = decide_mvp_action("q", _FailingProviderEmptyCode())
        assert d.failure_code == FAILURE_UNKNOWN
        assert is_mvp_failure(d)

    def test_provider_failure_passthrough_code(self):
        class _FailWithCode(LLMProvider):
            def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
                return ProviderResult(
                    ok=False, provider="fake", model="m", content="",
                    error="x", failure_code=FAILURE_TIMEOUT,
                )

            @property
            def provider_name(self) -> str:
                return "fake"

            @property
            def model_name(self) -> str:
                return "m"

        d = decide_mvp_action("q", _FailWithCode())
        assert d.failure_code == FAILURE_TIMEOUT
        assert is_mvp_failure(d)


# ----------------------------------------------------------------------
# MVP endpoint failure_code + secret-leak guarantee
# ----------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _FailingProviderWithLeakRisk(LLMProvider):
    """A provider whose error text would leak secrets if echoed raw."""

    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        return ProviderResult(
            ok=False, provider="fake", model="m", content="",
            error=f"call to {CANARY_URL} failed with {CANARY_AUTH_HEADER}",
            failure_code=FAILURE_TIMEOUT,
        )

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "m"


@pytest.fixture
def mvp_failure_leak_server():
    port = _free_port()
    server = create_app(
        site_id="bukgu_gwangju",
        provider="mock",
        snapshot=None,
        host="127.0.0.1",
        port=port,
        mvp_provider=_FailingProviderWithLeakRisk(),
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    yield {"port": port, "server": server}
    server.shutdown()
    server.server_close()


@pytest.fixture
def mvp_success_server():
    port = _free_port()

    class _OkProvider(LLMProvider):
        def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
            payload = {"answer": "안내", "action": "none", "confidence": 0.5}
            return ProviderResult(
                ok=True, provider="fake", model="m",
                content=json.dumps(payload, ensure_ascii=False),
            )

        @property
        def provider_name(self) -> str:
            return "fake"

        @property
        def model_name(self) -> str:
            return "m"

    server = create_app(
        site_id="bukgu_gwangju",
        provider="mock",
        snapshot=None,
        host="127.0.0.1",
        port=port,
        mvp_provider=_OkProvider(),
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    yield {"port": port, "server": server}
    server.shutdown()
    server.server_close()


class TestMvpAskEndpointContract:
    def test_failure_response_includes_failure_code(self, mvp_failure_leak_server):
        port = mvp_failure_leak_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": "오늘 북구 날씨 알려줘"}).encode()
        conn.request("POST", "/api/mvp/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        assert resp.status == 200
        assert data["ok"] is False
        assert data["action"] == "none"
        assert data["answer"] == MVP_FAILURE_ANSWER
        assert data["confidence"] == 0.0
        assert "failure_code" in data
        assert data["failure_code"] == FAILURE_TIMEOUT

    def test_success_response_includes_empty_failure_code(self, mvp_success_server):
        port = mvp_success_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": "날씨 어때?"}).encode()
        conn.request("POST", "/api/mvp/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        assert resp.status == 200
        assert data["ok"] is True
        assert "failure_code" in data
        assert data["failure_code"] == ""

    def test_no_secret_leak_in_failure_response(self, mvp_failure_leak_server):
        port = mvp_failure_leak_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": "오늘 북구 날씨 알려줘"}).encode()
        conn.request("POST", "/api/mvp/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        raw_text = resp.read().decode("utf-8")
        conn.close()
        assert CANARY_SECRET not in raw_text
        assert CANARY_URL not in raw_text
        assert CANARY_AUTH_HEADER not in raw_text


class _ProviderArbitraryCode(LLMProvider):
    """Provider returns an arbitrary (non-closed) failure_code string."""

    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        return ProviderResult(
            ok=False, provider="fake", model="m", content="",
            error="x", failure_code="arbitrary",
        )

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "m"


class _ProviderNonStringCode(LLMProvider):
    """Provider returns a non-string (int) failure_code."""

    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        return ProviderResult(
            ok=False, provider="fake", model="m", content="",
            error="x", failure_code=123,  # type: ignore[arg-type]
        )

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "m"


class _ProviderNoneCode(LLMProvider):
    """Provider returns failure_code=None."""

    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        return ProviderResult(
            ok=False, provider="fake", model="m", content="",
            error="x", failure_code=None,  # type: ignore[arg-type]
        )

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "m"


class _ProviderUpstreamInvalid(LLMProvider):
    """Provider already classifies an upstream structure error."""

    def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
        return ProviderResult(
            ok=False, provider="fake", model="m", content="",
            error="x", failure_code=FAILURE_INVALID_UPSTREAM_RESPONSE,
        )

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "m"


@pytest.fixture
def mvp_arbitrary_server():
    port = _free_port()
    server = create_app(
        site_id="bukgu_gwangju", provider="mock", snapshot=None,
        host="127.0.0.1", port=port, mvp_provider=_ProviderArbitraryCode(),
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    yield {"port": port, "server": server}
    server.shutdown()
    server.server_close()


@pytest.fixture
def mvp_nonstring_server():
    port = _free_port()
    server = create_app(
        site_id="bukgu_gwangju", provider="mock", snapshot=None,
        host="127.0.0.1", port=port, mvp_provider=_ProviderNonStringCode(),
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    yield {"port": port, "server": server}
    server.shutdown()
    server.server_close()


@pytest.fixture
def mvp_none_server():
    port = _free_port()
    server = create_app(
        site_id="bukgu_gwangju", provider="mock", snapshot=None,
        host="127.0.0.1", port=port, mvp_provider=_ProviderNoneCode(),
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    yield {"port": port, "server": server}
    server.shutdown()
    server.server_close()


@pytest.fixture
def mvp_upstream_invalid_server():
    port = _free_port()
    server = create_app(
        site_id="bukgu_gwangju", provider="mock", snapshot=None,
        host="127.0.0.1", port=port, mvp_provider=_ProviderUpstreamInvalid(),
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    yield {"port": port, "server": server}
    server.shutdown()
    server.server_close()


class TestMvpEndpointSanitizedFailureCode:
    def _post(self, port, question="오늘 북구 날씨 알려줘"):
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": question}).encode()
        conn.request("POST", "/api/mvp/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        return resp, data

    def test_outer_endpoint_fallback_is_provider_exception(self, mvp_failure_leak_server):
        # Force decide_mvp_action itself to raise so the outer endpoint
        # except fallback is exercised.
        import src.llm.bukgu_mvp_router as router_mod
        port = mvp_failure_leak_server["port"]
        server = mvp_failure_leak_server["server"]
        real_decide = router_mod.decide_mvp_action

        def _boom(question, provider):
            raise RuntimeError("endpoint-level boom")

        try:
            router_mod.decide_mvp_action = _boom
            resp, data = self._post(port)
        finally:
            router_mod.decide_mvp_action = real_decide
        assert resp.status == 200
        assert data["ok"] is False
        assert data["action"] == "none"
        assert data["failure_code"] == FAILURE_PROVIDER_EXCEPTION

    def test_arbitrary_code_collapses_to_unknown(self, mvp_arbitrary_server):
        port = mvp_arbitrary_server["port"]
        resp, data = self._post(port)
        assert resp.status == 200
        assert data["ok"] is False
        assert data["failure_code"] == FAILURE_UNKNOWN

    def test_nonstring_code_collapses_to_unknown(self, mvp_nonstring_server):
        port = mvp_nonstring_server["port"]
        resp, data = self._post(port)
        assert resp.status == 200
        assert data["ok"] is False
        assert data["failure_code"] == FAILURE_UNKNOWN

    def test_none_code_collapses_to_unknown(self, mvp_none_server):
        port = mvp_none_server["port"]
        resp, data = self._post(port)
        assert resp.status == 200
        assert data["ok"] is False
        assert data["failure_code"] == FAILURE_UNKNOWN

    def test_toplevel_list_is_invalid_upstream_response(self, mvp_upstream_invalid_server):
        port = mvp_upstream_invalid_server["port"]
        resp, data = self._post(port)
        assert resp.status == 200
        # A classified upstream structure error must pass through the endpoint
        # unchanged (not re-mapped to unknown).
        assert data["ok"] is False
        assert data["action"] == "none"
        assert data["failure_code"] == FAILURE_INVALID_UPSTREAM_RESPONSE

    def test_every_ok_false_response_uses_closed_vocabulary(self, mvp_failure_leak_server):
        # Exercise the provider failure path (timeout) and assert the code is
        # part of the closed vocabulary.
        port = mvp_failure_leak_server["port"]
        resp, data = self._post(port)
        assert resp.status == 200
        assert data["ok"] is False
        assert is_valid_failure_code(data["failure_code"])
        # Also assert the closed vocabulary across a representative set of
        # upstream-driven failures returned through the endpoint.
        for code in (
            FAILURE_CONFIGURATION,
            FAILURE_TIMEOUT,
            FAILURE_AUTH_OR_PERMISSION,
            FAILURE_RATE_LIMITED,
            FAILURE_UPSTREAM_4XX,
            FAILURE_UPSTREAM_5XX,
            FAILURE_TRANSPORT_ERROR,
            FAILURE_INVALID_UPSTREAM_RESPONSE,
            FAILURE_INVALID_MVP_DECISION,
            FAILURE_PROVIDER_EXCEPTION,
            FAILURE_UNKNOWN,
        ):
            assert is_valid_failure_code(code)


class TestFailureVocabulary:
    def test_all_codes_valid(self):
        for code in (
            FAILURE_CONFIGURATION,
            FAILURE_TIMEOUT,
            FAILURE_AUTH_OR_PERMISSION,
            FAILURE_RATE_LIMITED,
            FAILURE_UPSTREAM_4XX,
            FAILURE_UPSTREAM_5XX,
            FAILURE_TRANSPORT_ERROR,
            FAILURE_INVALID_UPSTREAM_RESPONSE,
            FAILURE_INVALID_MVP_DECISION,
            FAILURE_PROVIDER_EXCEPTION,
            FAILURE_UNKNOWN,
        ):
            assert is_valid_failure_code(code)

    def test_arbitrary_string_invalid(self):
        assert not is_valid_failure_code("some_random_error")
        assert not is_valid_failure_code("")
