"""Tests for the mobile-first web demo — create_app, HTTP endpoints."""

from __future__ import annotations

import json
import os
import threading
import time
from http.client import HTTPConnection
from unittest.mock import patch, MagicMock

import pytest

from src.web.mobile_demo import create_app, MOBILE_HTML

FIXTURE_SNAPSHOT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "tests", "fixtures", "bukgu_gwangju_demo_snapshot.json",
)


@pytest.fixture
def demo_server(tmp_path):
    """Start a demo server on a random port in a background thread."""
    import socket

    # Find a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    server = create_app(
        site_id="bukgu_gwangju",
        provider="mock",
        snapshot=FIXTURE_SNAPSHOT,
        host="127.0.0.1",
        port=port,
    )

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)  # wait for server to start

    yield {"port": port, "server": server}

    server.shutdown()
    server.server_close()


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestMobileDemoUnit:
    """Unit tests — no HTTP server needed."""

    def test_mobile_html_contains_site_name_placeholder(self):
        """1. HTML에 site_name 플레이스홀더가 포함된다."""
        assert "{{site_name}}" in MOBILE_HTML

    def test_mobile_html_contains_quick_questions(self):
        """2. HTML에 추천 질문 버튼이 포함된다."""
        assert "민원서식 어디서 받아?" in MOBILE_HTML
        assert "교육접수는 어디서 해?" in MOBILE_HTML
        assert "정보공개" in MOBILE_HTML
        assert "고시공고" in MOBILE_HTML

    def test_mobile_html_contains_answer_area(self):
        """3. HTML에 답변 영역이 포함된다."""
        assert "answer-text" in MOBILE_HTML
        assert "sources-section" in MOBILE_HTML

    def test_mobile_html_responsive_meta(self):
        """4. HTML에 모바일 viewport 메타 태그가 있다."""
        assert "viewport" in MOBILE_HTML
        assert "width=device-width" in MOBILE_HTML

    def test_mobile_html_has_search_input(self):
        """5. HTML에 질문 입력창이 있다."""
        assert 'id="question"' in MOBILE_HTML
        assert "찾아보기" in MOBILE_HTML

    def test_create_app_returns_server(self):
        """6. create_app이 HTTPServer 인스턴스를 반환한다."""
        from http.server import HTTPServer
        server = create_app(
            site_id="bukgu_gwangju",
            provider="mock",
            snapshot=FIXTURE_SNAPSHOT,
            host="127.0.0.1",
            port=0,  # port 0 = auto assign
        )
        assert isinstance(server, HTTPServer)
        server.server_close()

    def test_create_app_resolves_site_name(self):
        """7. create_app이 site_name을 프로필에서 로드한다."""
        from http.server import HTTPServer
        server = create_app(
            site_id="bukgu_gwangju",
            provider="mock",
            snapshot=FIXTURE_SNAPSHOT,
            host="127.0.0.1",
            port=0,
        )
        # The handler class should have _site_name set
        handler_cls = server.RequestHandlerClass
        assert "북구" in handler_cls._site_name
        server.server_close()


class TestMobileDemoHTTP:
    """HTTP integration tests — uses a running server."""

    def test_get_homepage(self, demo_server):
        """1. GET /이 HTML을 반환한다."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "text/html" in resp.getheader("Content-Type", "")
        assert "AI 홈페이지 도우미" in body
        assert "찾아보기" in body
        conn.close()

    def test_get_health(self, demo_server):
        """2. GET /health이 ok를 반환한다."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/health")
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert data["ok"] is True
        assert data["site_id"] == "bukgu_gwangju"
        conn.close()

    def test_post_ask_minwonseo(self, demo_server):
        """3. POST /api/ask 민원서식 질문이 답변과 출처를 반환한다."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        body = json.dumps({"question": "민원서식 어디서 받아?"}).encode()
        conn.request("POST", "/api/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 200
        assert data["ok"] is True
        assert data["snapshot_mode"] is True
        assert len(data["sources"]) >= 1
        assert any("민원서식" in s.get("title", "") for s in data["sources"])
        conn.close()

    def test_post_ask_gyoyukjeopsu(self, demo_server):
        """4. POST /api/ask 교육접수 질문에서 fallback 출처가 반환된다."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        body = json.dumps({"question": "교육접수는 어디서 해?"}).encode()
        conn.request("POST", "/api/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 200
        assert data["ok"] is True
        assert data["snapshot_mode"] is True
        assert len(data["sources"]) >= 1
        all_text = str(data["sources"])
        assert any(kw in all_text for kw in ["교육접수", "a10208020000"]), \
            f"Expected 교육접수 in sources: {all_text}"
        conn.close()

    def test_post_ask_empty_question(self, demo_server):
        """5. 빈 질문은 400 에러를 반환한다."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"question": ""}).encode()
        conn.request("POST", "/api/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 400
        assert "error" in data
        conn.close()

    def test_post_ask_missing_question(self, demo_server):
        """5b. question 필드 누락은 400 에러를 반환한다."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({}).encode()
        conn.request("POST", "/api/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 400
        conn.close()

    def test_post_ask_invalid_json(self, demo_server):
        """5c. 잘못된 JSON은 400 에러를 반환한다."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        body = b"not json"
        conn.request("POST", "/api/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()

    def test_post_ask_source_has_title_url(self, demo_server):
        """6. 출처에 title과 url이 포함된다."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        body = json.dumps({"question": "민원서식 어디서 받아?"}).encode()
        conn.request("POST", "/api/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        for src in data.get("sources", []):
            assert "title" in src
            assert "url" in src
            assert len(src["title"]) > 0
        conn.close()

    def test_get_404(self, demo_server):
        """7. 존재하지 않는 경로는 404를 반환한다."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/nonexistent")
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 404
        conn.close()

    def test_homepage_contains_site_name(self, demo_server):
        """8. 홈페이지에 실제 사이트 이름이 표시된다."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        assert "북구" in body
        conn.close()

    def test_ask_response_json_serializable(self, demo_server):
        """9. 응답이 JSON 직렬화 가능하다."""
        port = demo_server["port"]
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        body = json.dumps({"question": "민원서식 어디서 받아?"}).encode()
        conn.request("POST", "/api/ask", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        raw = resp.read()
        data = json.loads(raw)
        # Should round-trip
        dumped = json.dumps(data, ensure_ascii=False)
        assert len(dumped) > 0
        conn.close()
