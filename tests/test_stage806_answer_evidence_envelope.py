"""Focused no-live contract tests for Stage #806 evidence envelope.

The Stage #806 contract is: site_search may be labeled
``answered_with_evidence`` only when both retrieval and answer production
succeeded. Sources alone are not evidence.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, cast

import pytest

from src.demo import site_demo_runner as runner_module
from src.demo.conversation_log import log_conversation
from src.demo.site_demo_runner import SiteDemoRunner
from src.llm.site_search_router import default_fallback_decision


QUESTION = "민원서식 어디서 받아?"


def _write_search_results(path: str, results: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False)


def _write_answer(path: str, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _real_source() -> dict[str, Any]:
    return {
        "id": "r1",
        "title": "민원서식 안내",
        "url": "https://bukgu.gwangju.kr/apply",
        "category": "menu",
        "text": "민원서식은 북구청 홈페이지에서 내려받을 수 있습니다.",
        "score": 5.0,
    }


def _fallback_source() -> dict[str, Any]:
    return {
        "id": "fb1",
        "title": "홈페이지 통합검색",
        "url": "https://bukgu.gwangju.kr/search",
        "category": "navigation",
        "text": "홈페이지에서 다시 검색해 보세요.",
        "score": 5.0,
    }


def _answer_data(
    *,
    ok: bool = True,
    markdown: str = "## 답변\n\n북구청 홈페이지 종합민원 > 민원서식에서 내려받을 수 있습니다.",
) -> dict[str, Any]:
    return {
        "ok": ok,
        "answer_markdown": markdown,
        "sources": [_real_source()],
        "warnings": [],
        "error": "",
    }


def _make_runner(tmp_path: Any, monkeypatch: pytest.MonkeyPatch, pipeline_cls: type[Any]):
    runner = SiteDemoRunner(
        site_id="bukgu_gwangju",
        provider="mock",
        output_dir=str(tmp_path),
        pipeline_timeout_s=10.0,
    )
    monkeypatch.setattr(runner_module, "PipelineRunner", pipeline_cls)
    runner.router = cast(
        Any,
        type(
            "_StubRouter",
            (),
            {"decide": staticmethod(lambda q: default_fallback_decision(q, "광주광역시 북구청"))},
        )(),
    )
    return runner


def _assert_evidence_result(result: dict[str, Any], log_path: Any) -> None:
    assert result["ok"] is True
    assert result["answer_ok"] is True
    assert result["answer_status"] == "answered_with_evidence"
    assert result["source_weak"] is False

    assert log_conversation(result, log_path=str(log_path)) is True
    logged = json.loads(log_path.read_text(encoding="utf-8"))
    assert logged["answer_ok"] is True
    assert logged["answer_status"] == "answered_with_evidence"
    assert logged["source_weak"] is False


def _assert_no_answer_evidence_result(result: dict[str, Any], log_path: Any) -> None:
    assert result["ok"] is True
    assert result["answer_ok"] is False
    assert result["answer_status"] == "fallback_no_match"
    assert result["source_weak"] is True

    assert log_conversation(result, log_path=str(log_path)) is True
    logged = json.loads(log_path.read_text(encoding="utf-8"))
    assert logged["answer_ok"] is False
    assert logged["answer_status"] == "fallback_no_match"
    assert logged["source_weak"] is True


def test_non_fallback_source_and_nonblank_answer_is_evidence(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_path = os.path.join(tmp_path, "search.jsonl")
    answer_path = os.path.join(tmp_path, "answer.json")
    _write_search_results(search_path, [_real_source()])
    _write_answer(answer_path, _answer_data(ok=True))

    class _GroundedPipeline:
        def __init__(self, *a: Any, **kw: Any) -> None:
            pass

        def run(self, url: str, query: str) -> dict[str, Any]:
            return {
                "ok": True,
                "url": url,
                "query": query,
                "output_dir": str(tmp_path),
                "steps": [
                    {"name": "search", "ok": True, "output": search_path, "error": ""},
                    {"name": "answer", "ok": True, "output": answer_path, "error": ""},
                ],
                "answer_markdown": "",
            }

    runner = _make_runner(tmp_path, monkeypatch, _GroundedPipeline)
    result = runner.answer(QUESTION)

    _assert_evidence_result(result, tmp_path / "conv.jsonl")


@pytest.mark.parametrize(
    "case_name",
    [
        "composer_ok_false",
        "whitespace_answer",
        "missing_artifact",
        "malformed_artifact",
        "fallback_only_source",
    ],
)
def test_source_without_usable_answer_is_not_evidence(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    case_name: str,
) -> None:
    search_path = os.path.join(tmp_path, "search.jsonl")
    answer_path = os.path.join(tmp_path, "answer.json")
    _write_search_results(
        search_path,
        [_fallback_source() if case_name == "fallback_only_source" else _real_source()],
    )

    if case_name == "composer_ok_false":
        _write_answer(answer_path, _answer_data(ok=False))
    elif case_name == "whitespace_answer":
        _write_answer(answer_path, _answer_data(ok=True, markdown="   \n\t"))
    elif case_name == "missing_artifact":
        answer_path = os.path.join(tmp_path, "missing-answer.json")
    elif case_name == "malformed_artifact":
        with open(answer_path, "w", encoding="utf-8") as f:
            f.write("{not-json")
    else:
        _write_answer(answer_path, _answer_data(ok=True))

    class _NoAnswerPipeline:
        def __init__(self, *a: Any, **kw: Any) -> None:
            pass

        def run(self, url: str, query: str) -> dict[str, Any]:
            return {
                "ok": True,
                "url": url,
                "query": query,
                "output_dir": str(tmp_path),
                "steps": [
                    {"name": "search", "ok": True, "output": search_path, "error": ""},
                    {"name": "answer", "ok": True, "output": answer_path, "error": ""},
                ],
                "answer_markdown": "",
            }

    runner = _make_runner(tmp_path, monkeypatch, _NoAnswerPipeline)
    result = runner.answer(QUESTION)

    _assert_no_answer_evidence_result(result, tmp_path / "conv.jsonl")


def test_timeout_failure_keeps_fallback_unavailable_contract(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _HangingPipeline:
        def __init__(self, *a: Any, **kw: Any) -> None:
            pass

        def run(self, url: str, query: str) -> dict[str, Any]:
            time.sleep(5.0)
            return {"ok": True, "steps": [], "answer_markdown": ""}

    runner = _make_runner(tmp_path, monkeypatch, _HangingPipeline)
    runner._pipeline_timeout_s = 0.3
    result = runner.answer(QUESTION)

    assert result["ok"] is False
    assert result["answer_ok"] is False
    assert result["answer_status"] == "fallback_unavailable"
    assert result["source_weak"] is True
    assert result["fetch_diagnostic"]["category"] == "timeout"


def test_non_timeout_failure_keeps_error_contract(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _RaisingPipeline:
        def __init__(self, *a: Any, **kw: Any) -> None:
            pass

        def run(self, url: str, query: str) -> dict[str, Any]:
            raise ConnectionError("simulated connection failure")

    runner = _make_runner(tmp_path, monkeypatch, _RaisingPipeline)
    result = runner.answer(QUESTION)

    assert result["ok"] is False
    assert result["answer_ok"] is False
    assert result["answer_status"] == "error"
    assert result["source_weak"] is True
    assert result["fetch_diagnostic"]["category"] == "connection_error"
