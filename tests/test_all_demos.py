"""Tests for run_all_demos.py — unified demo runner."""

from __future__ import annotations

import json
import signal
import socket
import threading
import time
from http.client import HTTPConnection

import pytest


FIXTURE_SNAPSHOT = "tests/fixtures/bukgu_gwangju_demo_snapshot.json"


def _free_port() -> int:
    """Get a free port."""
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class TestRunAllDemos:
    """Tests for the unified demo runner script."""

    def test_import_run_all_demos(self):
        """1. run_all_demos 모듈을 임포트할 수 있다."""
        import importlib
        spec = importlib.util.spec_from_file_location(
            "run_all_demos", "scripts/run_all_demos.py"
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "main")

    def test_mobile_and_admin_same_args(self):
        """2. 두 서버가 같은 site_id/snapshot 인자를 받을 수 있다."""
        from src.web.mobile_demo import create_app
        from src.web.admin_demo import create_admin_app

        p1, p2 = _free_port(), _free_port()
        m = create_app(site_id="bukgu_gwangju", provider="mock",
                       snapshot=FIXTURE_SNAPSHOT, port=p1)
        a = create_admin_app(site_id="bukgu_gwangju", provider="mock",
                             snapshot=FIXTURE_SNAPSHOT, port=p2)
        assert m is not None
        assert a is not None
        m.server_close()
        a.server_close()

    def test_both_servers_respond_health(self):
        """3. 두 서버가 동시에 health 응답을 반환한다."""
        from src.web.mobile_demo import create_app
        from src.web.admin_demo import create_admin_app

        mp, ap = _free_port(), _free_port()
        mobile = create_app(site_id="bukgu_gwangju", provider="mock",
                            snapshot=FIXTURE_SNAPSHOT, port=mp)
        admin = create_admin_app(site_id="bukgu_gwangju", provider="mock",
                                 snapshot=FIXTURE_SNAPSHOT, port=ap)

        mt = threading.Thread(target=mobile.serve_forever, daemon=True)
        at = threading.Thread(target=admin.serve_forever, daemon=True)
        mt.start()
        at.start()
        time.sleep(0.3)

        try:
            # Mobile health
            c1 = HTTPConnection("127.0.0.1", mp, timeout=5)
            c1.request("GET", "/health")
            d1 = json.loads(c1.getresponse().read())
            assert d1["ok"] is True
            c1.close()

            # Admin health
            c2 = HTTPConnection("127.0.0.1", ap, timeout=5)
            c2.request("GET", "/health")
            d2 = json.loads(c2.getresponse().read())
            assert d2["ok"] is True
            c2.close()
        finally:
            mobile.shutdown()
            admin.shutdown()
            mobile.server_close()
            admin.server_close()

    def test_both_servers_answer_same_question(self):
        """4. 같은 질문에 대해 두 서버가 동일한 답변을 반환한다."""
        from src.web.mobile_demo import create_app
        from src.web.admin_demo import create_admin_app

        mp, ap = _free_port(), _free_port()
        mobile = create_app(site_id="bukgu_gwangju", provider="mock",
                            snapshot=FIXTURE_SNAPSHOT, port=mp)
        admin = create_admin_app(site_id="bukgu_gwangju", provider="mock",
                                 snapshot=FIXTURE_SNAPSHOT, port=ap)

        mt = threading.Thread(target=mobile.serve_forever, daemon=True)
        at = threading.Thread(target=admin.serve_forever, daemon=True)
        mt.start()
        at.start()
        time.sleep(0.3)

        body = json.dumps({"question": "민원서식 어디서 받아?"})
        headers = {"Content-Type": "application/json"}

        try:
            c1 = HTTPConnection("127.0.0.1", mp, timeout=10)
            c1.request("POST", "/api/ask", body=body, headers=headers)
            r1 = json.loads(c1.getresponse().read())
            c1.close()

            c2 = HTTPConnection("127.0.0.1", ap, timeout=10)
            c2.request("POST", "/api/test", body=body, headers=headers)
            r2 = json.loads(c2.getresponse().read())
            c2.close()

            assert r1["answer"] == r2["answer"]
            assert len(r1["sources"]) == len(r2["sources"])
        finally:
            mobile.shutdown()
            admin.shutdown()
            mobile.server_close()
            admin.server_close()

    def test_run_all_demos_module_has_main(self):
        """5. run_all_demos 모듈에 main 함수가 존재한다."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_all_demos", "scripts/run_all_demos.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert callable(mod.main)

    def test_demo_scenario_file_exists(self):
        """6. demo-scenario.md 파일이 존재한다."""
        import os
        assert os.path.isfile("docs/demo-scenario.md")

    def test_demo_scenario_has_sections(self):
        """7. demo-scenario.md에 핵심 섹션이 포함되어 있다."""
        with open("docs/demo-scenario.md", encoding="utf-8") as f:
            content = f.read()
        assert "시연 흐름" in content
        assert "모바일 사용자 화면" in content
        assert "운영자 대시보드" in content
        assert "민원서식" in content
        assert "교육접수" in content

    def test_readme_has_demo_section(self):
        """8. README.md에 데모 실행 섹션이 포함되어 있다."""
        with open("README.md", encoding="utf-8") as f:
            content = f.read()
        assert "데모 실행" in content
        assert "run_all_demos.py" in content
        assert "8400" in content
        assert "8090" in content

    def test_no_api_key_in_new_files(self):
        """9. 새로 추가된 파일에 API 키가 없다."""
        import os
        new_files = [
            "scripts/run_all_demos.py",
            "src/web/admin_demo.py",
            "scripts/run_admin_demo.py",
        ]
        for path in new_files:
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                assert "fc-" not in content, f"API key found in {path}"
                assert "sk-" not in content, f"API key found in {path}"
