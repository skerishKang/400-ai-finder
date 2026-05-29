"""Tests for the desktop admin dashboard — admin_demo.py."""

from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection

import pytest

from src.web.admin_demo import ADMIN_HTML, create_admin_app


FIXTURE_SNAPSHOT = "tests/fixtures/bukgu_gwangju_demo_snapshot.json"


# ------------------------------------------------------------------
# Unit tests (no server)
# ------------------------------------------------------------------


class TestAdminDemoUnit:
    """Unit tests for admin HTML and create_admin_app."""

    def test_admin_html_contains_title(self):
        """1. HTML에 운영자 화면 제목이 있다."""
        assert "운영자 화면" in ADMIN_HTML

    def test_admin_html_contains_profile_section(self):
        """2. HTML에 사이트 프로필 영역이 있다."""
        assert "사이트 프로필" in ADMIN_HTML

    def test_admin_html_contains_snapshot_section(self):
        """3. HTML에 snapshot 상태 영역이 있다."""
        assert "snapshot" in ADMIN_HTML.lower()

    def test_admin_html_contains_test_panel(self):
        """4. HTML에 데모 질문 테스트 패널이 있다."""
        assert "데모 질문 테스트" in ADMIN_HTML
        assert "testQuestion" in ADMIN_HTML

    def test_admin_html_contains_quick_buttons(self):
        """5. HTML에 추천 질문 버튼이 있다."""
        assert "민원서식" in ADMIN_HTML
        assert "교육접수" in ADMIN_HTML
        assert "정보공개" in ADMIN_HTML
        assert "고시공고" in ADMIN_HTML

    def test_admin_html_contains_table(self):
        """6. HTML에 출처 테이블이 있다."""
        assert "<table>" in ADMIN_HTML
        assert "제목" in ADMIN_HTML
        assert "URL" in ADMIN_HTML

    def test_admin_html_responsive_meta(self):
        """7. HTML에 viewport 메타 태그가 있다."""
        assert "viewport" in ADMIN_HTML
        assert "width=device-width" in ADMIN_HTML

    def test_create_admin_app_returns_server(self):
        """8. create_admin_app이 HTTPServer를 반환한다."""
        from http.server import HTTPServer
        server = create_admin_app(
            site_id="bukgu_gwangju",
            provider="mock",
            snapshot=FIXTURE_SNAPSHOT,
            port=40901,
        )
        assert isinstance(server, HTTPServer)
        server.server_close()

    def test_create_admin_app_resolves_site_name(self):
        """9. create_admin_app이 site_name을 해석한다."""
        server = create_admin_app(site_id="bukgu_gwangju", port=40902)
        handler = server.RequestHandlerClass
        assert handler._site_name == "광주광역시 북구청"
        server.server_close()


# ------------------------------------------------------------------
# HTTP integration tests
# ------------------------------------------------------------------


@pytest.fixture
def admin_server():
    """Start an admin server on a random port, yield port, then shutdown."""
    import socket
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = create_admin_app(
        site_id="bukgu_gwangju",
        provider="mock",
        snapshot=FIXTURE_SNAPSHOT,
        port=port,
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
        """10. GET /이 HTML을 반환한다."""
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
        """11. GET /health이 ok를 반환한다."""
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/health")
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert data["ok"] is True
        assert data["site_id"] == "bukgu_gwangju"
        conn.close()

    def test_get_info(self, admin_server):
        """12. GET /api/info가 프로필과 snapshot 정보를 반환한다."""
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

    def test_post_test_minwonseo(self, admin_server):
        """13. 민원서식 질문 테스트가 결과를 반환한다."""
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
        """14. 교육접수 질문 테스트가 결과를 반환한다."""
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
        """15. 빈 질문이 에러를 반환한다."""
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
        """16. 잘못된 JSON이 에러를 반환한다."""
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("POST", "/api/test", body="not-json",
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()

    def test_get_404(self, admin_server):
        """17. 존재하지 않는 경로가 404를 반환한다."""
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/nonexistent")
        resp = conn.getresponse()
        assert resp.status == 404
        conn.close()

    def test_info_json_serializable(self, admin_server):
        """18. /api/info 응답이 JSON 직렬화 가능하다."""
        port = admin_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/info")
        resp = conn.getresponse()
        data = json.loads(resp.read())
        json.dumps(data, ensure_ascii=False)
        conn.close()

    def test_mobile_demo_still_works(self):
        """19. 기존 mobile demo 테스트에 영향이 없다."""
        from src.web.mobile_demo import MOBILE_HTML, create_app
        assert "AI 홈페이지 도우미" in MOBILE_HTML
        from http.server import HTTPServer
        server = create_app(site_id="bukgu_gwangju", port=40903)
        assert isinstance(server, HTTPServer)
        server.server_close()
