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
_MOBILE_HTML = _load_template("광주광역시 북구청")


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


class TestMobileDemoUnit:
    """Unit tests — no HTTP server needed."""

    def test_mobile_html_has_site_name(self):
        assert "광주광역시 북구청" in _MOBILE_HTML

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
