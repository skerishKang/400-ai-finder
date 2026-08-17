"""#1331 Slice A — shared site-aware MVP runtime identity + fail-closed dispatch.

Deterministic / offline. No provider, no network, no official-site / Firecrawl
calls. The Python resolver (``src.llm.site_aware_mvp_dispatch``) is the single
ownership point; the Cloudflare Function mirrors it (see
``tests/functions/test_site_runtime_contract.mjs``). These tests pin the
contract both runtimes must agree on:

  - omitted / empty / malformed site id  -> never silently becomes Buk-gu
  - well-formed unrecognized site id     -> UNKNOWN (fail closed)
  - seogu_gwangju                        -> RECOGNIZED_UNCONFIGURED (no execution)
  - bukgu_gwangju                        -> CONFIGURED (Buk-gu runtime runs)
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from http.client import HTTPConnection

import pytest

from src.llm import site_aware_mvp_dispatch as dispatch
from src.llm.site_aware_mvp_dispatch import (
    DEFAULT_SITE_ID,
    SITE_FAILURE_UNKNOWN,
    SITE_FAILURE_UNCONFIGURED,
    SITE_RUNTIME_CONFIGURED,
    SITE_RUNTIME_RECOGNIZED_UNCONFIGURED,
    SITE_RUNTIME_UNKNOWN,
    SiteRuntimeStatus,
    is_valid_site_id_format,
    resolve_site_runtime,
)
from src.web.mobile_demo import create_app

FIXTURE_SNAPSHOT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "tests", "fixtures", "bukgu_gwangju_demo_snapshot.json",
)


# --------------------------------------------------------------------------- #
# Resolver contract (the vocabulary both runtimes must share 1:1)             #
# --------------------------------------------------------------------------- #
class TestResolverVocabulary:
    def test_status_values_are_canonical_strings(self):
        # These exact strings are mirrored in functions/api/mvp/site_runtime.js.
        assert SITE_RUNTIME_CONFIGURED == "configured"
        assert SITE_RUNTIME_RECOGNIZED_UNCONFIGURED == "recognized_unconfigured"
        assert SITE_RUNTIME_UNKNOWN == "unknown"

    def test_default_site_is_bukgu(self):
        assert DEFAULT_SITE_ID == "bukgu_gwangju"

    def test_supported_registry_only_two_entries(self):
        assert set(dispatch.SUPPORTED_SITE_RUNTIMES) == {
            "bukgu_gwangju",
            "seogu_gwangju",
        }
        assert (
            dispatch.SUPPORTED_SITE_RUNTIMES["bukgu_gwangju"]
            is SiteRuntimeStatus.CONFIGURED
        )
        assert (
            dispatch.SUPPORTED_SITE_RUNTIMES["seogu_gwangju"]
            is SiteRuntimeStatus.RECOGNIZED_UNCONFIGURED
        )

    def test_failure_codes_are_distinct_from_provider_vocab(self):
        # Site-dispatch failure codes MUST stay separate from the provider/model
        # failure_code vocabulary in src.llm.openai_compatible_provider.
        assert SITE_FAILURE_UNKNOWN == "unknown_site"
        assert SITE_FAILURE_UNCONFIGURED == "site_unconfigured_for_slice"


class TestResolverResolution:
    def test_omitted_resolves_to_default_bukgu(self):
        res = resolve_site_runtime(None)
        assert res.site_id == "bukgu_gwangju"
        assert res.status is SiteRuntimeStatus.CONFIGURED

    def test_empty_string_resolves_to_default_bukgu(self):
        res = resolve_site_runtime("")
        assert res.site_id == "bukgu_gwangju"
        assert res.status is SiteRuntimeStatus.CONFIGURED

    def test_whitespace_only_resolves_to_default_bukgu(self):
        res = resolve_site_runtime("   ")
        assert res.site_id == "bukgu_gwangju"
        assert res.status is SiteRuntimeStatus.CONFIGURED

    def test_explicit_bukgu_is_configured(self):
        res = resolve_site_runtime("bukgu_gwangju")
        assert res.status is SiteRuntimeStatus.CONFIGURED

    def test_seogu_is_recognized_unconfigured(self):
        res = resolve_site_runtime("seogu_gwangju")
        assert res.status is SiteRuntimeStatus.RECOGNIZED_UNCONFIGURED

    def test_well_formed_unknown_is_unknown_fail_closed(self):
        res = resolve_site_runtime("atlantis_gov")
        assert res.status is SiteRuntimeStatus.UNKNOWN

    def test_malformed_uppercase_is_unknown_fail_closed(self):
        # Never silently defaults to Buk-gu.
        res = resolve_site_runtime("Bukgu")
        assert res.status is SiteRuntimeStatus.UNKNOWN

    def test_malformed_dash_is_unknown_fail_closed(self):
        res = resolve_site_runtime("buk-gu")
        assert res.status is SiteRuntimeStatus.UNKNOWN

    def test_malformed_too_short_is_unknown_fail_closed(self):
        res = resolve_site_runtime("ab")
        assert res.status is SiteRuntimeStatus.UNKNOWN

    def test_malformed_too_long_is_unknown_fail_closed(self):
        res = resolve_site_runtime("a" * 65)
        assert res.status is SiteRuntimeStatus.UNKNOWN

    def test_non_string_resolves_to_default_bukgu(self):
        res = resolve_site_runtime(12345)
        assert res.site_id == "bukgu_gwangju"
        assert res.status is SiteRuntimeStatus.CONFIGURED


class TestSiteIdFormat:
    def test_valid_examples(self):
        for sid in ("bukgu_gwangju", "seogu_gwangju", "site_1", "abc"):
            assert is_valid_site_id_format(sid) is True

    def test_invalid_examples(self):
        for sid in ("Bukgu", "buk-gu", "ab", "a" * 65, "", 123, None):
            assert is_valid_site_id_format(sid) is False


# --------------------------------------------------------------------------- #
# HTTP dispatch seam (mobile_demo _handle_mvp_ask)                            #
# --------------------------------------------------------------------------- #
def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(site_id: str):
    port = _free_port()
    server = create_app(
        site_id=site_id,
        provider="mock",
        snapshot=FIXTURE_SNAPSHOT,
        host="127.0.0.1",
        port=port,
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    return server, port


def _post_mvp(port: int, question: str) -> dict:
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    body = json.dumps({"question": question}).encode()
    conn.request(
        "POST", "/api/mvp/ask", body=body,
        headers={"Content-Type": "application/json"},
    )
    resp = conn.getresponse()
    data = json.loads(resp.read())
    conn.close()
    return data


@pytest.fixture
def bukgu_server():
    server, port = _start("bukgu_gwangju")
    yield port
    server.shutdown()
    server.server_close()


@pytest.fixture
def seogu_server():
    server, port = _start("seogu_gwangju")
    yield port
    server.shutdown()
    server.server_close()


@pytest.fixture
def unknown_server():
    server, port = _start("atlantis_gov")
    yield port
    server.shutdown()
    server.server_close()


@pytest.fixture
def malformed_server():
    server, port = _start("Bukgu")
    yield port
    server.shutdown()
    server.server_close()


class TestMvpAskDispatch:
    def test_bukgu_still_runs_bukgu_runtime(self, bukgu_server):
        data = _post_mvp(bukgu_server, "공동주택 문의는 어디로 해요?")
        assert data["ok"] is True
        # Buk-gu runtime executed (not the site_dispatch guard).
        assert data["provider"] != "site_dispatch"
        assert data["site_id"] == "bukgu_gwangju"
        assert data["site_status"] == "configured"

    def test_seogu_never_executes_bukgu(self, seogu_server):
        data = _post_mvp(seogu_server, "공동주택 문의는 어디로 해요?")
        assert data["ok"] is False
        assert data["action"] == "none"
        assert data["provider"] == "site_dispatch"
        assert data["failure_code"] == SITE_FAILURE_UNCONFIGURED
        assert data["site_status"] == "recognized_unconfigured"
        assert data["site_id"] == "seogu_gwangju"
        assert data["fallback_to_bukgu"] is False
        # No Buk-gu quest/action leaked through.
        assert "quest" not in data

    def test_unknown_site_fails_closed(self, unknown_server):
        data = _post_mvp(unknown_server, "안녕하세요")
        assert data["ok"] is False
        assert data["action"] == "none"
        assert data["provider"] == "site_dispatch"
        assert data["failure_code"] == SITE_FAILURE_UNKNOWN
        assert data["site_status"] == "unknown"
        assert data["fallback_to_bukgu"] is False

    def test_malformed_site_fails_closed(self, malformed_server):
        data = _post_mvp(malformed_server, "안녕하세요")
        assert data["ok"] is False
        assert data["failure_code"] == SITE_FAILURE_UNKNOWN
        assert data["site_status"] == "unknown"
        assert data["fallback_to_bukgu"] is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
