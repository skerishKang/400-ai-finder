"""Tests for the mobile chat UI demo — create_app, HTTP endpoints."""

from __future__ import annotations

import json
import os
import threading
import time
from http.client import HTTPConnection

import pytest

from src.web.mobile_demo import create_app, _load_template

FIXTURE_SNAPSHOT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "tests", "fixtures", "bukgu_gwangju_demo_snapshot.json",
)

# Load the mobile HTML template once for unit tests
_MOBILE_HTML = _load_template("전남광주통합특별시 북구")


@pytest.fixture
def demo_server(tmp_path):
    """Start a demo server on a random port in a background thread."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = create_app(
        site_id="bukgu_gwangju", provider="mock",
        snapshot=FIXTURE_SNAPSHOT, host="127.0.0.1", port=port,
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    yield {"port": port, "server": server}
    server.shutdown()
    server.server_close()


@pytest.fixture
def timeout_demo_server(tmp_path, monkeypatch):
    """Start a demo server whose SiteDemoRunner pipeline always times out.

    This isolates the ``PR #799`` behavior under HTTP: a site_search request
    must still return HTTP 200 with a structured JSON body containing the
    timeout warning, ``source_weak=True`` and ``route=site_search``.
    """
    import socket
    import time as _time
    from src.demo import site_demo_runner as runner_module

    class _HangingPipelineRunner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, url, query):
            # Hang well past the runner budget.
            _time.sleep(5.0)
            return {"ok": True, "steps": [], "answer_markdown": ""}

    monkeypatch.setattr(runner_module, "PipelineRunner", _HangingPipelineRunner)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    # ``pipeline_timeout_s`` flows through SiteDemoRunner's kwargs.
    server = create_app(
        site_id="bukgu_gwangju",
        provider="mock",
        snapshot=None,  # do NOT use snapshot; force live pipeline path
        host="127.0.0.1",
        port=port,
        pipeline_timeout_s=0.3,
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    _time.sleep(0.3)
    yield {"port": port, "server": server}
    server.shutdown()
    server.server_close()


class TestMobileDemoUnit:
    """Unit tests — no HTTP server needed."""

    def test_mobile_html_has_site_name(self):
        assert "전남광주통합특별시 북구" in _MOBILE_HTML

    def test_mobile_html_has_quick_question_chips(self):
        assert "민원서식 어디서 받아?" in _MOBILE_HTML
        assert "교육접수는 어디서 해?" in _MOBILE_HTML

    def test_mobile_html_has_composer_and_input(self):
        assert "composer-box" in _MOBILE_HTML
        assert 'id="input"' in _MOBILE_HTML
        assert 'id="sendBtn"' in _MOBILE_HTML

    def test_mobile_html_has_message_area(self):
        assert 'id="messages"' in _MOBILE_HTML
        assert "welcome" in _MOBILE_HTML

    def test_mobile_html_responsive_meta(self):
        assert "viewport" in _MOBILE_HTML
        assert "width=device-width" in _MOBILE_HTML

    def test_mobile_html_has_sidebar(self):
        assert "sidebar" in _MOBILE_HTML
        assert "topbar" in _MOBILE_HTML

    def test_mobile_html_has_send_button(self):
        assert "send-btn" in _MOBILE_HTML

    def test_mobile_html_links_external_css_js(self):
        html = _MOBILE_HTML
        assert 'href="/static/mobile/mobile_base.css"' in html
        assert 'href="/static/mobile/mobile_reset.css"' in html
        assert 'href="/static/mobile/mobile_layout.css"' in html
        assert 'href="/static/mobile/mobile_sidebar.css"' in html
        assert 'href="/static/mobile/mobile_header.css"' in html
        assert 'href="/static/mobile/mobile_chat.css"' in html
        assert 'href="/static/mobile/mobile_composer.css"' in html
        assert 'href="/static/mobile/mobile_responsive.css"' in html
        assert 'src="/static/mobile/mobile_demo.js"' in html

    def test_mobile_html_has_theme_toggle(self):
        assert "theme-toggle" in _MOBILE_HTML
        assert "toggleTheme" in _MOBILE_HTML

    def test_mobile_html_has_new_chat_button(self):
        assert "new-chat-btn" in _MOBILE_HTML

    def test_mobile_html_has_template_variables(self):
        assert "SITE_NAME" in _MOBILE_HTML
        assert "API_ENDPOINT" in _MOBILE_HTML

    def test_create_app_returns_server(self):
        from http.server import HTTPServer, ThreadingHTTPServer
        server = create_app(
            site_id="bukgu_gwangju", provider="mock",
            snapshot=FIXTURE_SNAPSHOT, host="127.0.0.1", port=0,
        )
        assert isinstance(server, HTTPServer)
        server.server_close()

    def test_create_app_resolves_site_name(self):
        server = create_app(
            site_id="bukgu_gwangju", provider="mock",
            snapshot=FIXTURE_SNAPSHOT, host="127.0.0.1", port=0,
        )
        handler_cls = server.RequestHandlerClass
        assert "북구" in handler_cls._site_name
        server.server_close()


class TestMobileDemoHTTP:
    """HTTP integration tests — uses a running server."""

    def test_get_homepage(self, demo_server):
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "text/html" in resp.getheader("Content-Type", "")
        conn.close()

    def test_get_health(self, demo_server):
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/health")
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert data["ok"] is True
        assert data["site_id"] == "bukgu_gwangju"
        conn.close()

    def test_get_mvp_route_redirects_to_mvp_query(self, demo_server):
        """GET /mvp must 302-redirect to /mvp?mvp=1 (no redirect loop)."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/mvp")
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 302
        assert resp.getheader("Location") == "/mvp?mvp=1"
        conn.close()

    def test_get_mvp_route_with_query_serves_first_use_demo(self, demo_server):
        """GET /mvp?mvp=1 serves citizen-action-demo.html (the first-use shell)."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/mvp?mvp=1")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "text/html" in resp.getheader("Content-Type", "")
        assert "citizen-first-use-shell.js" in body
        assert "citizen-first-choreography.js" in body
        conn.close()

    def test_default_root_still_mobile_demo(self, demo_server):
        """The default static entry (GET /) must remain the mobile demo."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "composer" in body
        conn.close()

    def test_get_static_base_css(self, demo_server):
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/static/mobile/mobile_base.css")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "text/css" in resp.getheader("Content-Type", "")
        assert "--sidebar-width" in body
        conn.close()

    def test_get_static_chat_css(self, demo_server):
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/static/mobile/mobile_chat.css")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "text/css" in resp.getheader("Content-Type", "")
        assert "msg-row" in body
        conn.close()

    def test_get_static_js(self, demo_server):
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/static/mobile/mobile_demo.js")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "javascript" in resp.getheader("Content-Type", "")
        assert "toggleSidebar" in body
        conn.close()

    def test_get_static_404(self, demo_server):
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/static/nonexistent.css")
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 404
        conn.close()

    def test_post_ask_minwonseo(self, demo_server):
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        body = json.dumps({"question": "민원서식 어디서 받아?"}).encode()
        conn.request("POST", "/api/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 200
        assert len(data["sources"]) >= 1
        assert data["answer_ok"] is True
        assert data["llm_live"] is False
        assert data["llm_status"] == "snapshot_no_api"
        assert "저장된 source 자료 기반" in data["llm_label"]
        conn.close()

    def test_post_ask_gyoyukjeopsu(self, demo_server):
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        body = json.dumps({"question": "교육접수는 어디서 해?"}).encode()
        conn.request("POST", "/api/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 200
        assert len(data["sources"]) >= 1
        conn.close()

    def test_post_ask_empty_question(self, demo_server):
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": ""}).encode()
        conn.request("POST", "/api/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()

    def test_post_ask_invalid_json(self, demo_server):
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("POST", "/api/ask", body=b"not json",
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()

    def test_post_ask_returns_json_when_pipeline_times_out(self, timeout_demo_server):
        """When the underlying pipeline hangs longer than the runner
        budget, the HTTP endpoint must still answer with a JSON body
        (not 500, not hang), preserving ``route=site_search`` and
        recording ``source_weak=True`` plus a timeout warning.
        """
        import time as _time

        port = timeout_demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=8)
        body = json.dumps({"question": "민원서식 어디서 받아?"}).encode()
        started = _time.monotonic()
        conn.request(
            "POST", "/api/ask", body=body,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        elapsed = _time.monotonic() - started
        data = json.loads(resp.read())
        conn.close()

        assert resp.status == 200, f"expected 200, got {resp.status}"
        assert elapsed < 5.0, f"server blocked {elapsed:.2f}s (expected <5s)"
        assert data["route"] == "site_search"
        assert data["should_search_site"] is True
        assert data["answer_mode"] == "retrieval_answer"
        assert data["ok"] is False
        assert data["answer_ok"] is False
        assert data["source_weak"] is True
        # warnings must include a timeout/fetch-failure marker
        joined = " ".join(data.get("warnings", [])).lower()
        assert "timed out" in joined or "timeout" in joined
        # soft answer must still be non-empty
        assert data["answer"]

    def test_get_404(self, demo_server):
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/nonexistent")
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 404
        conn.close()

    def test_homepage_contains_site_name(self, demo_server):
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert "북구" in body
        conn.close()

    def test_homepage_has_chat_structure(self, demo_server):
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert "topbar" in body
        assert "sidebar" in body
        assert "composer" in body
        assert "welcome" in body
        conn.close()

    def test_mobile_html_no_site_select_ui(self):
        """Mobile template must not expose site selection or technical terms."""
        html = _MOBILE_HTML
        # No site selection dropdown
        assert "siteSelect" not in html
        assert "site_id" not in html
        # No technical terms visible to end users
        assert "provider" not in html.lower()
        assert "preset" not in html.lower()
        assert "stub" not in html.lower()
        assert "mock" not in html.lower()


_MOBILE_DEMO_JS = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "src", "web", "static", "mobile", "mobile_demo.js",
)


class TestMobileDemoLinkSafety:
    """Static contract tests for #1102 mobile link safety.

    The mobile demo renders untrusted answer markdown and untrusted source
    URLs into the DOM. Both insertion paths MUST go through a single
    ``sanitizeMobileUrl`` guard that rejects every non-http(s) scheme
    (javascript:, data:, vbscript:, file:, blob:, protocol-relative //host)
    and any credentialed/malformed URL. Unsafe answer links render as inert
    text (no <a>, no href). Unsafe source cards are omitted entirely.
    """

    @staticmethod
    def _js():
        with open(_MOBILE_DEMO_JS, "r", encoding="utf-8") as f:
            return f.read()

    def test_sanitize_mobile_url_is_defined(self):
        js = self._js()
        assert "function sanitizeMobileUrl" in js, \
            "sanitizeMobileUrl must be defined as the single URL guard"

    def test_source_card_uses_sanitizer(self):
        js = self._js()
        # Old vulnerable direct assignment must be gone.
        assert "s.url || '#'" not in js, \
            "raw source url must never be assigned as href"
        # The source loop must sanitize before using the url.
        assert "sanitizeMobileUrl(s.url)" in js, \
            "source card must call sanitizeMobileUrl(s.url)"
        # Unsafe sources must be skipped (the loop `return`s early).
        assert "if (!safe) return" in js, \
            "unsafe source urls must be omitted (early return in loop)"
        # extractDomain must only see already-sanitized hrefs.
        assert "extractDomain(safe.href)" in js, \
            "extractDomain must be fed the sanitized href, not the raw url"

    def test_markdown_link_replacement_is_callback_not_raw(self):
        js = self._js()
        # The dangerous raw-attribute interpolation must be gone.
        assert '"$2"' not in js, \
            "markdown link regex must not interpolate the raw url into href"
        # The replacement must invoke the sanitizer inside a callback.
        assert "sanitizeMobileUrl(url)" in js, \
            "markdown link replacement must sanitize the captured url"
        # Callback form (arrow function) must be used, not a string replacement.
        assert "(m, label, url) =>" in js, \
            "markdown link replacement should use a callback"

    def test_sanitizer_rejects_non_http_schemes(self):
        """Sanitizer must reject javascript:, data:, protocol-relative, etc.

        This is a lightweight contract mirror of the browser E2E: it ensures
        the function exists with the expected rejection shape (returns null
        for unsafe, an object with href/external for safe). The full runtime
        behavior is covered by verify_mobile_link_safety.mjs.
        """
        js = self._js()
        # Guard clauses that prove the policy is enforced in source.
        assert "scheme !== 'http:' && scheme !== 'https:'" in js, \
            "sanitizer must allow only http: and https: schemes"
        assert r"/^\/\//.test(trimmed)" in js, \
            "sanitizer must reject protocol-relative URLs (//host)"
        assert "parsed.username || parsed.password" in js, \
            "sanitizer must reject credentialed URLs"
        assert r"[\x00-\x1f\x7f]" in js, \
            "sanitizer must reject control characters before trim"
