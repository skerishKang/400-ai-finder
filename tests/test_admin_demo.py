"""Tests for the desktop admin dashboard — admin_demo.py."""

from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

import pytest

from src.web.admin_demo import _load_template, _resolve_effective_snapshot, create_admin_app

# Load admin HTML template once for unit tests
_ADMIN_HTML = _load_template()

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
FIXTURE_SNAPSHOT = str(FIXTURES_DIR / "bukgu_gwangju_demo_snapshot.json")


class TestAdminDemoUnit:
    """Unit tests for admin HTML and create_admin_app."""

    def test_admin_html_contains_title(self):
        assert "운영자 화면" in _ADMIN_HTML

    def test_admin_html_contains_profile_section(self):
        assert "사이트 프로필" in _ADMIN_HTML

    def test_admin_html_contains_snapshot_section(self):
        assert "snapshot" in _ADMIN_HTML.lower()

    def test_admin_html_contains_test_panel(self):
        assert "데모 질문 테스트" in _ADMIN_HTML
        assert "testQuestion" in _ADMIN_HTML

    def test_admin_html_contains_quick_buttons(self):
        assert "민원서식" in _ADMIN_HTML
        assert "교육접수" in _ADMIN_HTML
        assert "정보공개" in _ADMIN_HTML
        assert "고시공고" in _ADMIN_HTML

    def test_admin_html_contains_table(self):
        assert "<table>" in _ADMIN_HTML
        assert "제목" in _ADMIN_HTML
        assert "URL" in _ADMIN_HTML

    def test_admin_html_responsive_meta(self):
        assert "viewport" in _ADMIN_HTML
        assert "width=device-width" in _ADMIN_HTML

    def test_admin_html_links_external_css_js(self):
        assert 'href="/static/admin/admin_demo.css"' in _ADMIN_HTML
        assert 'src="/static/admin/admin_demo.js"' in _ADMIN_HTML

    def test_create_admin_app_returns_server(self):
        from http.server import HTTPServer
        server = create_admin_app(
            site_id="bukgu_gwangju", provider="mock",
            snapshot=FIXTURE_SNAPSHOT, port=40901,
        )
        assert isinstance(server, HTTPServer)
        server.server_close()

    def test_create_admin_app_resolves_site_name(self):
        server = create_admin_app(site_id="bukgu_gwangju", port=40902)
        handler = server.RequestHandlerClass
        assert handler._site_name == "광주광역시 북구청"
        server.server_close()

    def test_resolve_effective_snapshot_does_not_cross_site_boundaries(self):
        snapshot = _resolve_effective_snapshot(
            startup_snapshot=FIXTURE_SNAPSHOT,
            server_site_id="bukgu_gwangju",
            effective_site_id="gwangju_go_kr",
        )
        assert snapshot is None


@pytest.fixture
def admin_server():
    """Start an admin server on a random port, yield port, then shutdown."""
    import socket
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = create_admin_app(
        site_id="bukgu_gwangju", provider="mock",
        snapshot=FIXTURE_SNAPSHOT, port=port,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield {"port": port, "server": server}
    server.shutdown()
    server.server_close()


@pytest.fixture
def admin_server_without_startup_snapshot():
    """Start admin server without explicit snapshot path."""
    import socket
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = create_admin_app(
        site_id="bukgu_gwangju", provider="mock",
        snapshot=None, port=port,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield {"port": port, "server": server}
    server.shutdown()
    server.server_close()


class TestAdminDemoHTTP:
    """HTTP integration tests for the admin dashboard."""

    def test_get_homepage(self, admin_server):
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "text/html" in resp.getheader("Content-Type", "")
        assert "운영자 화면" in body
        conn.close()

    def test_get_health(self, admin_server):
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/health")
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert data["ok"] is True
        assert data["site_id"] == "bukgu_gwangju"
        conn.close()

    def test_get_info(self, admin_server):
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/info")
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 200
        assert data["summary"]["site_id"] == "bukgu_gwangju"
        assert data["summary"]["site_name"] == "광주광역시 북구청"
        assert data["profile"]["name"] == "광주광역시 북구청"
        assert data["snapshot"]["loaded"] is True
        assert data["snapshot"]["nav_link_count"] >= 1
        conn.close()

    def test_get_info_uses_bundled_snapshot_without_startup_snapshot(self, admin_server_without_startup_snapshot):
        port = admin_server_without_startup_snapshot["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/info")
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 200
        assert data["summary"]["site_id"] == "bukgu_gwangju"
        assert data["snapshot"]["loaded"] is True
        assert data["snapshot"]["path"].endswith("bukgu_gwangju_demo_snapshot.json")
        assert data["snapshot"]["nav_link_count"] >= 1
        conn.close()

    def test_get_static_css(self, admin_server):
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/static/admin/admin_demo.css")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "text/css" in resp.getheader("Content-Type", "")
        assert "--primary" in body
        conn.close()

    def test_get_static_js(self, admin_server):
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/static/admin/admin_demo.js")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "javascript" in resp.getheader("Content-Type", "")
        assert "runTest" in body
        conn.close()

    def test_post_test_minwonseo(self, admin_server):
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        body = json.dumps({"question": "민원서식 어디서 받아?"})
        conn.request("POST", "/api/test", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 200
        assert data["question"] == "민원서식 어디서 받아?"
        assert len(data["sources"]) >= 1
        assert data["answer"] != ""
        conn.close()

    def test_post_test_gyoyukjeopsu(self, admin_server):
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        body = json.dumps({"question": "교육접수는 어디서 해?"})
        conn.request("POST", "/api/test", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 200
        assert len(data["sources"]) >= 1
        conn.close()

    def test_post_test_empty_question(self, admin_server):
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": ""})
        conn.request("POST", "/api/test", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 400
        assert "error" in data
        conn.close()

    def test_post_test_invalid_json(self, admin_server):
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("POST", "/api/test", body="not-json",
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()

    def test_get_404(self, admin_server):
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/nonexistent")
        resp = conn.getresponse()
        assert resp.status == 404
        conn.close()

    def test_info_json_serializable(self, admin_server):
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/info")
        resp = conn.getresponse()
        data = json.loads(resp.read())
        json.dumps(data, ensure_ascii=False)
        conn.close()

    # --- Stage 38: profiles list, site_id override ---

    def test_info_contains_profiles_list(self, admin_server):
        """Verify /api/info returns a profiles list with known site_ids."""
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/info")
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 200
        profiles = data.get("profiles", [])
        assert isinstance(profiles, list)
        assert len(profiles) >= 2
        site_ids = [p["site_id"] for p in profiles]
        assert "bukgu_gwangju" in site_ids
        assert "gwangju_go_kr" in site_ids
        # Each profile must have required keys
        for p in profiles:
            assert "site_id" in p
            assert "name" in p
            assert "base_url" in p
            assert "classification" in p
        conn.close()

    def test_post_test_with_site_id_override_bukgu(self, admin_server):
        """Verify /api/test accepts site_id=bukgu_gwangju and returns bukgu results."""
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        body = json.dumps({"question": "민원서식 어디서 받아?", "site_id": "bukgu_gwangju"})
        conn.request("POST", "/api/test", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 200
        assert data["site_id"] == "bukgu_gwangju"
        assert "북구청" in data.get("site_name", "")
        assert len(data["sources"]) >= 1
        conn.close()

    def test_post_test_uses_site_snapshot_when_startup_snapshot_missing(self, admin_server_without_startup_snapshot):
        """Verify /api/test can use bundled site snapshot without startup snapshot."""
        port = admin_server_without_startup_snapshot["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        body = json.dumps({"question": "민원서식 어디서 받아?", "site_id": "bukgu_gwangju"})
        conn.request("POST", "/api/test", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 200
        assert data["site_id"] == "bukgu_gwangju"
        assert data["snapshot_mode"] is True
        assert len(data["sources"]) >= 1
        conn.close()

    def test_post_test_with_site_id_override_unknown(self, admin_server):
        """Verify /api/test returns 400 for unknown site_id."""
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": "고시공고는 어디서 봐?", "site_id": "nonexistent_site"})
        conn.request("POST", "/api/test", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 400
        assert "error" in data
        assert "nonexistent_site" in data["error"]
        conn.close()

    def test_admin_html_contains_site_select(self):
        """Verify admin HTML contains site selection dropdown."""
        assert "siteSelect" in _ADMIN_HTML
        assert "기관 선택" in _ADMIN_HTML

    def test_admin_js_sends_site_id(self):
        """Verify admin JS sends site_id in /api/test payload."""
        with open("src/web/static/admin/admin_demo.js", encoding="utf-8") as f:
            js = f.read()
        assert "selectedSiteId" in js
        assert "payload.site_id" in js
        assert "allProfiles" in js
