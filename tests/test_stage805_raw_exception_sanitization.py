"""Focused no-live canary tests for Stage #805 raw-exception sanitization."""

from __future__ import annotations

import io
import json
from typing import Any, cast

import pytest


_CANARIES: tuple[str, ...] = (
    "sk-LIV...cdef",
    "Bearer c4n4ry-token-zzzzzzzzzzzzzzzz",
    "X-Internal-Secret: top-secret",
    "secret_body=THIS_IS_THE_BODY",
    "https://user:p4ssw0rd@host.example/path",
)


def _leaky_exception_message() -> str:
    return (
        "provider failure "
        "sk-LIV...cdef "
        "Bearer c4n4ry-token-zzzzzzzzzzzzzzzz "
        "X-Internal-Secret: top-secret "
        "secret_body=THIS_IS_THE_BODY "
        "https://user:p4ssw0rd@host.example/path"
    )


def _assert_no_canary(blob: str) -> None:
    for canary in _CANARIES:
        assert canary not in blob, f"canary leaked: {canary!r}"


class _RaisingHomepageMapper:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def build_map(self) -> None:
        raise ValueError(_leaky_exception_message())


def test_pipeline_runner_step_failure_sanitizes_pipeline_artifact(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.pipeline.pipeline_runner import PipelineRunner

    monkeypatch.setattr("src.pipeline.pipeline_runner.HomepageMapper", _RaisingHomepageMapper)

    output_dir = str(tmp_path / "run")
    result = PipelineRunner(output_dir=output_dir, provider="mock").run(
        url="https://example.com",
        query="민원서식",
    )

    artifact = tmp_path / "run" / "pipeline-result.json"
    serialized = json.dumps(result, ensure_ascii=False) + artifact.read_text(encoding="utf-8")
    _assert_no_canary(serialized)
    assert result["ok"] is False
    assert result["error"]
    assert "category=" in result["error"]
    assert "Pipeline step failed" in result["error"]


def test_sitedemorunner_build_result_does_not_re_emit_unsafe_pipeline_error(
    tmp_path: Any,
) -> None:
    from src.demo.site_demo_runner import SiteDemoRunner
    from src.llm.site_search_router import default_fallback_decision

    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="mock",
        output_dir=str(tmp_path),
    )
    pipeline_result = {
        "ok": False,
        "error": _leaky_exception_message(),
        "steps": [
            {
                "name": "search",
                "ok": False,
                "output": "",
                "error": _leaky_exception_message(),
            },
            {
                "name": "answer",
                "ok": False,
                "output": "",
                "error": _leaky_exception_message(),
            },
        ],
        "answer_markdown": "",
    }

    result = runner._build_result(
        "민원서식 어디서 받아?",
        pipeline_result,
        run_dir=str(tmp_path),
        router_decision=default_fallback_decision(
            "민원서식 어디서 받아?",
            "광주광역시 북구청",
        ),
        pipeline_warning=_leaky_exception_message(),
        pipeline_diagnostic=None,
    )

    serialized = json.dumps(result, ensure_ascii=False)
    _assert_no_canary(serialized)
    assert result["ok"] is False
    assert result["answer_ok"] is False
    assert result["answer_status"] == "error"
    assert "Pipeline failed with a sanitized diagnostic." in result["warnings"]


def test_mobile_outer_exception_response_and_jsonl_are_sanitized(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from src.demo import conversation_log
    from src.web import mobile_demo
    from src.web.mobile_demo import MobileDemoHandler

    class _RaisingRunner:
        provider = "mock"
        model = None

        def answer(self, question: str) -> None:
            raise ValueError(_leaky_exception_message())

    class _Handler:
        site_id = "bukgu_gwangju"
        provider = "mock"
        model = None
        snapshot_path = None
        pipeline_timeout_s = 5.0
        _runner = _RaisingRunner()
        _site_name = "광주광역시 북구청"

        def _json_response(self, data: dict[str, Any], status: int = 200) -> None:
            nonlocal response_data
            response_data = {"data": data, "status": status}

    response_data: dict[str, Any] = {}
    handler = cast(Any, _Handler())
    body = json.dumps(
        {"question": "민원서식 어디서 받아?"},
        ensure_ascii=False,
    ).encode("utf-8")
    handler.rfile = io.BytesIO(body)
    handler.headers = {"Content-Length": str(len(body))}

    log_path = tmp_path / "conversations.jsonl"

    def _wrap_log(result: dict[str, Any]) -> bool:
        return conversation_log.log_conversation(result, log_path=str(log_path))

    monkeypatch.setattr(mobile_demo, "log_conversation", _wrap_log)

    with caplog.at_level("DEBUG"):
        MobileDemoHandler._handle_ask(cast(Any, handler))

    data = response_data["data"]
    response_blob = json.dumps(data, ensure_ascii=False)
    _assert_no_canary(response_blob)
    assert response_data["status"] == 200
    assert data["ok"] is False
    assert data["answer_ok"] is False
    assert data["answer_status"] == "error"
    assert data["route"] == "site_search"

    log_blob = log_path.read_text(encoding="utf-8")
    _assert_no_canary(log_blob)
    assert "Request failed with a sanitized diagnostic." in log_blob

    for record in caplog.records:
        rendered = record.getMessage()
        _assert_no_canary(rendered)
