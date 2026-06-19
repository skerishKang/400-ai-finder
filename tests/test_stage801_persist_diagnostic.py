"""Tests for Stage #801 — sanitized fetch diagnostic persistence.

The runner emits ``fetch_diagnostic`` alongside the user-facing response
so dashboards and the conversation log can correlate ``source_weak``
with the underlying fetch failure category (timeout, blocked,
tls_error, etc.) without ever echoing raw exception text, headers,
bodies, provider payloads, API keys, or URL credentials.

These tests cover:

1. The four closed-vocabulary columns land in ``logs/conversations.jsonl``
   on the failure path.
2. The same four columns are ``None`` on the normal / direct_answer /
   clarify / snapshot paths.
3. The ``fetch_diagnostic`` field round-trips through the mobile and
   admin HTTP endpoints.
4. Canary secrets never appear in JSON responses or JSONL records.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from http.client import HTTPConnection
from typing import Any

import pytest


# Canary strings — must never appear in any persisted or response surface.
_CANARIES: tuple[str, ...] = (
    "sk-LIV...cdef",
    "Bearer c4n4ry-token-zzzzzzzzzzzzzzzz",
    "X-Internal-Secret: top-secret",
    "secret_body=THIS_IS_THE_BODY",
    "https://user:p4ssw0rd@host.example/path",
    "VERY_SPECIFIC_STAGE801_CANARY_DO_NOT_PERSIST",
)


# ---------------------------------------------------------------------------
# 1. conversation_log: sanitized diagnostic columns
# ---------------------------------------------------------------------------


class TestConversationLogDiagnosticColumns:
    """The four diagnostic columns must be written on failure paths and
    ``None`` on the normal / non-pipeline paths.
    """

    def test_writes_diagnostic_columns_on_failure(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.demo import conversation_log

        log_path = str(tmp_path / "conversations.jsonl")

        # Simulate the runner's failure-path response shape.
        result = {
            "site_id": "bukgu_gwangju",
            "site_name": "광주광역시 북구청",
            "question": "민원서식 어디서 받아?",
            "answer": "soft fallback",
            "provider": "stub",
            "model": "stub",
            "llm_status": "live",
            "llm_live": True,
            "answer_ok": False,
            "sources": [],
            "fallback_used": False,
            "warnings": ["Pipeline timed out"],
            "route": "site_search",
            "should_search_site": True,
            "route_confidence": 0.9,
            "route_reason": "match",
            "search_query": "민원서식",
            "answer_mode": "retrieval_answer",
            "source_weak": True,
            "fetch_diagnostic": {
                "category": "timeout",
                "short_reason": "Request exceeded its deadline.",
                "retry_hint": "retry",
                "is_transient": True,
            },
        }
        assert conversation_log.log_conversation(result, log_path) is True

        with open(log_path, "r", encoding="utf-8") as f:
            record = json.loads(f.readline())

        assert record["fetch_diagnostic_category"] == "timeout"
        assert record["fetch_diagnostic_short_reason"] == "Request exceeded its deadline."
        assert record["fetch_diagnostic_retry_hint"] == "retry"
        assert record["fetch_diagnostic_is_transient"] is True

    def test_writes_null_columns_on_normal_path(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.demo import conversation_log

        log_path = str(tmp_path / "conversations.jsonl")

        # A direct_answer result has ``fetch_diagnostic: None``.
        result = {
            "site_id": "bukgu_gwangju",
            "site_name": "광주광역시 북구청",
            "question": "안녕",
            "answer": "안녕하세요.",
            "provider": "stub",
            "model": "stub",
            "llm_status": "live",
            "llm_live": True,
            "answer_ok": True,
            "sources": [],
            "fallback_used": False,
            "warnings": [],
            "route": "direct_answer",
            "should_search_site": False,
            "route_confidence": 1.0,
            "route_reason": "greeting",
            "search_query": "",
            "answer_mode": "direct_answer",
            "source_weak": False,
            "fetch_diagnostic": None,
        }
        assert conversation_log.log_conversation(result, log_path) is True

        with open(log_path, "r", encoding="utf-8") as f:
            record = json.loads(f.readline())

        assert record["fetch_diagnostic_category"] is None
        assert record["fetch_diagnostic_short_reason"] is None
        assert record["fetch_diagnostic_retry_hint"] is None
        assert record["fetch_diagnostic_is_transient"] is None

    def test_writes_null_columns_when_diagnostic_missing(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the runner forgot to set ``fetch_diagnostic`` (legacy
        callers), the log helper must still serialize ``None`` rather
        than raise.
        """
        from src.demo import conversation_log

        log_path = str(tmp_path / "conversations.jsonl")

        result = {
            "site_id": "bukgu_gwangju",
            "site_name": "광주광역시 북구청",
            "question": "test",
            "answer": "test",
            "provider": "stub",
            "model": "stub",
            "llm_status": "live",
            "llm_live": True,
            "answer_ok": True,
            "sources": [],
            "fallback_used": False,
            "warnings": [],
            "route": "site_search",
            "should_search_site": True,
            "route_confidence": 0.9,
            "route_reason": "match",
            "search_query": "test",
            "answer_mode": "retrieval_answer",
            "source_weak": False,
            # NOTE: deliberately no fetch_diagnostic key
        }
        assert conversation_log.log_conversation(result, log_path) is True

        with open(log_path, "r", encoding="utf-8") as f:
            record = json.loads(f.readline())

        assert record["fetch_diagnostic_category"] is None
        assert record["fetch_diagnostic_short_reason"] is None
        assert record["fetch_diagnostic_retry_hint"] is None
        assert record["fetch_diagnostic_is_transient"] is None


# ---------------------------------------------------------------------------
# 2. SiteDemoRunner: fetch_diagnostic in result
# ---------------------------------------------------------------------------


class _CanaryRaisingPipeline:
    """Pipeline stub that raises a ``TimeoutError`` carrying every canary."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def run(self, url: str, query: str) -> dict[str, Any]:
        msg = (
            "transport failed: sk-LIV...cdef "
            "Bearer c4n4ry-token-zzzzzzzzzzzzzzzz "
            "X-Internal-Secret: top-secret "
            "secret_body=THIS_IS_THE_BODY "
            "https://user:p4ssw0rd@host.example/path "
            "VERY_SPECIFIC_STAGE801_CANARY_DO_NOT_PERSIST"
        )
        raise TimeoutError(msg)


class _FastPipeline:
    """Pipeline stub that returns a normal result with no diagnostic."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def run(self, url: str, query: str) -> dict[str, Any]:
        return {
            "ok": True,
            "url": url,
            "query": query,
            "steps": [
                {"name": "search", "ok": True, "output": "", "error": ""},
                {"name": "answer", "ok": True, "output": "", "error": ""},
            ],
            "answer_markdown": "정상 답변",
            "sources": [],
        }


class TestRunnerEmitsFetchDiagnostic:
    """``SiteDemoRunner.answer()`` must attach ``fetch_diagnostic`` to
    every result dict, with the right shape on each route.
    """

    def _build_runner(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any, pipeline_stub: Any
    ) -> Any:
        from src.demo import site_demo_runner as runner_module
        from src.demo.site_demo_runner import SiteDemoRunner

        monkeypatch.setattr(runner_module, "PipelineRunner", pipeline_stub)
        return SiteDemoRunner(
            site_id="bukgu_gwangju",
            provider="mock",
            output_dir=str(tmp_path),
            pipeline_timeout_s=5.0,
        )

    def test_timeout_path_emits_timeout_diagnostic(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = self._build_runner(monkeypatch, tmp_path, _CanaryRaisingPipeline)
        result = runner.answer("민원서식 어디서 받아?")

        # fetch_diagnostic must be a non-empty dict with the four
        # closed-vocabulary fields.
        diag = result["fetch_diagnostic"]
        assert isinstance(diag, dict)
        assert set(diag.keys()) == {
            "category",
            "short_reason",
            "retry_hint",
            "is_transient",
        }
        assert diag["category"] == "timeout"
        assert diag["retry_hint"] == "retry"
        assert diag["is_transient"] is True

    def test_normal_path_emits_none_diagnostic(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = self._build_runner(monkeypatch, tmp_path, _FastPipeline)
        result = runner.answer("안녕")

        assert result["fetch_diagnostic"] is None

    def test_direct_answer_path_emits_none_diagnostic(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Direct_answer and clarify routes never invoke the pipeline,
        so ``fetch_diagnostic`` must be ``None``.
        """
        from src.demo import site_demo_runner as runner_module
        from src.demo.site_demo_runner import SiteDemoRunner, RouterDecision

        runner = SiteDemoRunner(
            site_id="bukgu_gwangju",
            provider="mock",
            output_dir=str(tmp_path),
            pipeline_timeout_s=5.0,
        )

        # Inject a router that always decides direct_answer.
        class _DirectRouter:
            def decide(self, question: str) -> Any:
                return RouterDecision(
                    route="direct_answer",
                    should_search_site=False,
                    confidence=1.0,
                    reason="greeting",
                    search_query="",
                    direct_answer="안녕하세요.",
                )

        monkeypatch.setattr(SiteDemoRunner, "_resolve_router", lambda self: _DirectRouter())
        result = runner.answer("안녕")

        assert result["route"] == "direct_answer"
        assert result["fetch_diagnostic"] is None

    def test_snapshot_path_emits_none_diagnostic(self, tmp_path: Any) -> None:
        """``answer_from_snapshot`` must always emit ``fetch_diagnostic: None``
        because snapshots bypass the live pipeline.
        """
        import json as _json

        from src.demo.site_demo_runner import SiteDemoRunner

        runner = SiteDemoRunner(
            site_id="bukgu_gwangju",
            provider="mock",
            output_dir=str(tmp_path),
        )

        snap_path = tmp_path / "snap.json"
        snap_path.write_text(
            _json.dumps(
                {
                    "site_id": "bukgu_gwangju",
                    "question": "민원서식",
                    "answer": "snapshot answer",
                    "sources": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = runner.answer_from_snapshot(str(snap_path), question="민원서식")
        assert result["fetch_diagnostic"] is None

    def test_no_canary_in_result(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The full result dict (including answer + warnings + diagnostic)
        must not echo raw canary strings.
        """
        runner = self._build_runner(monkeypatch, tmp_path, _CanaryRaisingPipeline)
        result = runner.answer("민원서식 어디서 받아?")

        serialized = json.dumps(result, ensure_ascii=False, default=str)
        for canary in _CANARIES:
            assert canary not in serialized, (
                f"canary {canary!r} leaked into result dict"
            )

    def test_no_canary_in_log_records(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Carrying the previous Stage #800 boundary into Stage #801:
        the runner must not leak canary strings into any log record.
        """
        runner = self._build_runner(monkeypatch, tmp_path, _CanaryRaisingPipeline)
        with caplog.at_level("DEBUG"):
            runner.answer("민원서식 어디서 받아?")

        for record in caplog.records:
            rendered = record.getMessage()
            for canary in _CANARIES:
                assert canary not in rendered, (
                    f"canary {canary!r} leaked into log record: {rendered!r}"
                )
            assert record.exc_info is None


# ---------------------------------------------------------------------------
# 3. End-to-end: HTTP endpoints expose fetch_diagnostic
# ---------------------------------------------------------------------------


def _bind_free_port() -> int:
    """Reserve a free TCP port and return it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestHTTPEndpointExposesFetchDiagnostic:
    """The mobile and admin endpoints must surface ``fetch_diagnostic``
    to the JSON response.
    """

    def _start_demo(
        self, monkeypatch: pytest.MonkeyPatch, app_factory: Any
    ) -> tuple[Any, int]:
        from src.demo import site_demo_runner as runner_module

        monkeypatch.setattr(runner_module, "PipelineRunner", _CanaryRaisingPipeline)
        port = _bind_free_port()
        server = app_factory(
            site_id="bukgu_gwangju",
            provider="mock",
            snapshot=None,
            host="127.0.0.1",
            port=port,
            pipeline_timeout_s=5.0,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.3)
        return server, port

    def test_mobile_response_has_diagnostic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.web.mobile_demo import create_app

        server, port = self._start_demo(monkeypatch, create_app)
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=5)
            body = json.dumps({"question": "민원서식 어디서 받아?"}).encode()
            conn.request(
                "POST",
                "/api/ask",
                body=body,
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            data = json.loads(resp.read())
            conn.close()

            assert resp.status == 200
            assert data["route"] == "site_search"
            diag = data["fetch_diagnostic"]
            assert isinstance(diag, dict)
            assert diag["category"] == "timeout"
            assert diag["retry_hint"] == "retry"
            assert diag["is_transient"] is True

            # No canary in the user-facing JSON response.
            serialized = json.dumps(data, ensure_ascii=False)
            for canary in _CANARIES:
                assert canary not in serialized
        finally:
            server.shutdown()
            server.server_close()

    def test_admin_response_has_diagnostic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.web.admin_demo import create_admin_app
        from src.web import admin_demo as admin_module

        monkeypatch.setattr(admin_module, "_find_site_snapshot", lambda site_id: None)
        monkeypatch.setattr(admin_module.AdminDemoHandler, "_runner_cache", {})

        server, port = self._start_demo(monkeypatch, create_admin_app)
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=5)
            body = json.dumps({"question": "민원서식 어디서 받아?"}).encode()
            conn.request(
                "POST",
                "/api/test",
                body=body,
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            data = json.loads(resp.read())
            conn.close()

            assert resp.status == 200
            assert data["route"] == "site_search"
            diag = data["fetch_diagnostic"]
            assert isinstance(diag, dict)
            assert diag["category"] == "timeout"
            assert diag["retry_hint"] == "retry"
            assert diag["is_transient"] is True

            serialized = json.dumps(data, ensure_ascii=False)
            for canary in _CANARIES:
                assert canary not in serialized
        finally:
            server.shutdown()
            server.server_close()


# ---------------------------------------------------------------------------
# 4. End-to-end: HTTP endpoint + conversation_log JSONL
# ---------------------------------------------------------------------------


class TestHTTPCanaryNotPersistedToJSONL:
    """A full HTTP roundtrip that triggers the canary pipeline must
    not write any canary into the resulting JSONL conversation record.
    """

    def test_mobile_endpoint_jsonl_has_no_canary(
        self,
        tmp_path: Any,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        from src.demo import conversation_log
        from src.web import mobile_demo
        from src.web.mobile_demo import create_app

        log_path = str(tmp_path / "conversations.jsonl")

        # ``log_conversation`` captures ``DEFAULT_LOG_PATH`` at import
        # time, so we wrap the function itself to redirect writes to
        # ``log_path``. This must be patched on every module that
        # imported the symbol — both ``src.demo.conversation_log`` and
        # ``src.web.mobile_demo``.
        original_log = conversation_log.log_conversation

        def _wrap_log(result: dict[str, Any]) -> bool:
            return original_log(result, log_path=log_path)

        monkeypatch.setattr(conversation_log, "log_conversation", _wrap_log)
        monkeypatch.setattr(mobile_demo, "log_conversation", _wrap_log)

        server, port = self._bind_and_start_mobile(monkeypatch)
        try:
            with caplog.at_level("DEBUG"):
                conn = HTTPConnection("127.0.0.1", port, timeout=5)
                body = json.dumps({"question": "민원서식 어디서 받아?"}).encode()
                conn.request(
                    "POST",
                    "/api/ask",
                    body=body,
                    headers={"Content-Type": "application/json"},
                )
                resp = conn.getresponse()
                resp_data = json.loads(resp.read())
                conn.close()
        finally:
            server.shutdown()
            server.server_close()

        # Response carries the diagnostic and zero canaries.
        assert resp_data["fetch_diagnostic"]["category"] == "timeout"
        resp_serialized = json.dumps(resp_data, ensure_ascii=False)
        for canary in _CANARIES:
            assert canary not in resp_serialized

        # Log records carry zero canaries (Stage #800 boundary preserved).
        for record in caplog.records:
            rendered = record.getMessage()
            for canary in _CANARIES:
                assert canary not in rendered

        # JSONL record carries zero canaries and the four diagnostic columns.
        with open(log_path, "r", encoding="utf-8") as f:
            line = f.readline().strip()
        assert line, "expected at least one conversation log line"
        record = json.loads(line)

        for canary in _CANARIES:
            assert canary not in line, f"canary {canary!r} leaked into JSONL"

        assert record["fetch_diagnostic_category"] == "timeout"
        assert record["fetch_diagnostic_short_reason"] == "Request exceeded its deadline."
        assert record["fetch_diagnostic_retry_hint"] == "retry"
        assert record["fetch_diagnostic_is_transient"] is True

    def _bind_and_start_mobile(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[Any, int]:
        from src.demo import site_demo_runner as runner_module
        from src.web.mobile_demo import create_app

        monkeypatch.setattr(runner_module, "PipelineRunner", _CanaryRaisingPipeline)
        port = _bind_free_port()
        server = create_app(
            site_id="bukgu_gwangju",
            provider="mock",
            snapshot=None,
            host="127.0.0.1",
            port=port,
            pipeline_timeout_s=5.0,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.3)
        return server, port
