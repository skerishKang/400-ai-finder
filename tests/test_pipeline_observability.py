from __future__ import annotations

import ast
import importlib
import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.analytics.question_logger import NoOpQuestionLogger, QuestionLogEvent
from src.pipeline.pipeline_runner import PipelineRunner
from tests.test_pipeline_runner import (
    FAKE_ANSWER_RESULT,
    FAKE_DOCS,
    FAKE_ENRICHED_DOCS,
    FAKE_HOMEPAGE_MAP,
    FAKE_SEARCH_RESULTS,
)


def _extract_pipeline_records(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in caplog.messages:
        if not line.startswith("pipeline_event="):
            continue
        records.append(json.loads(line.split("=", 1)[1]))
    return records


def _configure_successful_pipeline(
    MockMapper,
    MockIndexer,
    MockEnricher,
    MockSearcher,
    MockComposer,
) -> None:
    MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
    MockIndexer.return_value.build_index.return_value = FAKE_DOCS
    MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
    MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
    MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> str:
    return str(tmp_path / "run-observability")


def test_event_logger_import_is_network_free_and_does_not_configure_logging(monkeypatch) -> None:
    basic_config = Mock(side_effect=AssertionError("logging.basicConfig called during import"))
    monkeypatch.setattr(logging, "basicConfig", basic_config)
    sys.modules.pop("src.observability.event_logger", None)
    sys.modules.pop("src.observability", None)

    module = importlib.import_module("src.observability.event_logger")

    assert module is not None
    basic_config.assert_not_called()


def test_event_logger_uses_no_structlog_or_nonstdlib_imports() -> None:
    event_logger_path = Path(__file__).parent.parent / "src" / "observability" / "event_logger.py"
    source = event_logger_path.read_text(encoding="utf-8")
    assert "structlog" not in source

    tree = ast.parse(source)
    allowed_roots = {"json", "logging", "uuid", "typing"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                assert root in allowed_roots, f"unexpected import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            assert root in allowed_roots, f"unexpected import from: {node.module}"


class SpyQuestionLogger(NoOpQuestionLogger):
    def __init__(self) -> None:
        self.logged_events: list[QuestionLogEvent] = []

    def log(self, event: QuestionLogEvent) -> None:
        self.logged_events.append(event)


@patch("src.pipeline.pipeline_runner.AnswerComposer")
@patch("src.pipeline.pipeline_runner.KeywordSearcher")
@patch("src.pipeline.pipeline_runner.DocumentEnricher")
@patch("src.pipeline.pipeline_runner.DocumentIndexer")
@patch("src.pipeline.pipeline_runner.HomepageMapper")
def test_pipeline_run_emits_consistent_stage_events_and_preserves_contract(
    MockMapper,
    MockIndexer,
    MockEnricher,
    MockSearcher,
    MockComposer,
    tmp_output_dir: str,
    caplog: pytest.LogCaptureFixture,
    monkeypatch,
) -> None:
    _configure_successful_pipeline(
        MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer
    )
    spy_logger = SpyQuestionLogger()
    runner = PipelineRunner(
        output_dir=tmp_output_dir,
        provider="mock",
        question_logger=spy_logger,
    )
    monkeypatch.setattr(runner, "_resolve_site_id", lambda url: "test_site")

    with caplog.at_level(logging.INFO, logger="src.pipeline.pipeline_runner"):
        result = runner.run(
            url="https://example.com/path?token=abc123",
            query="질문 api_key=sk-secret https://secret.example.com/page",
        )

    event_records = _extract_pipeline_records(caplog)
    assert result["ok"] is True
    assert set(result.keys()) == {
        "ok",
        "url",
        "query",
        "output_dir",
        "steps",
        "answer_markdown",
        "error",
    }
    assert [set(step.keys()) for step in result["steps"]] == [
        {"name", "ok", "output", "error"},
        {"name", "ok", "output", "error"},
        {"name", "ok", "output", "error"},
        {"name", "ok", "output", "error"},
        {"name", "ok", "output", "error", "markdown_output"},
    ]
    assert len(spy_logger.logged_events) == 1
    assert spy_logger.logged_events[0].raw_question.startswith("질문 api_key=[REDACTED]")
    assert "sk-" not in spy_logger.logged_events[0].raw_question

    expected_events = [
        "pipeline_run_start",
        "pipeline_stage_start",
        "pipeline_stage_end",
        "pipeline_stage_start",
        "pipeline_stage_end",
        "pipeline_stage_start",
        "pipeline_stage_end",
        "pipeline_stage_start",
        "pipeline_stage_end",
        "pipeline_stage_start",
        "pipeline_stage_end",
        "pipeline_run_end",
    ]
    assert [record["event"] for record in event_records] == expected_events

    correlation_ids = {record["correlation_id"] for record in event_records}
    assert len(correlation_ids) == 1
    assert spy_logger.logged_events[0].correlation_id == next(iter(correlation_ids))
    assert next(iter(correlation_ids))
    stage_names = [
        record["stage"]
        for record in event_records
        if record["event"] in {"pipeline_stage_start", "pipeline_stage_end"}
    ]
    assert stage_names == [
        "homepage_map",
        "homepage_map",
        "document_index",
        "document_index",
        "enriched_index",
        "enriched_index",
        "search",
        "search",
        "answer",
        "answer",
    ]
    assert event_records[0]["site_id"] == "test_site"
    assert event_records[-1]["ok"] is True
    assert "site_id" not in event_records[-1]
    assert "stage" not in event_records[-1]
    assert isinstance(event_records[-1]["duration_ms"], int)

    allowed_keys = {
        "event",
        "correlation_id",
        "stage",
        "ok",
        "duration_ms",
        "site_id",
        "failure_code",
    }
    joined_logs = "\n".join(caplog.messages)
    for record in event_records:
        assert set(record).issubset(allowed_keys)
    assert "질문" not in joined_logs
    assert "https://example.com" not in joined_logs
    assert "https://secret.example.com/page" not in joined_logs
    assert FAKE_ANSWER_RESULT["answer_markdown"] not in joined_logs
    assert "sk-" not in joined_logs
    assert "Bearer" not in joined_logs
    assert "api_key" not in joined_logs


@patch("src.pipeline.pipeline_runner.AnswerComposer")
@patch("src.pipeline.pipeline_runner.KeywordSearcher")
@patch("src.pipeline.pipeline_runner.DocumentEnricher")
@patch("src.pipeline.pipeline_runner.DocumentIndexer")
@patch("src.pipeline.pipeline_runner.HomepageMapper")
def test_pipeline_run_uses_injected_correlation_id_unchanged(
    MockMapper,
    MockIndexer,
    MockEnricher,
    MockSearcher,
    MockComposer,
    tmp_output_dir: str,
    caplog: pytest.LogCaptureFixture,
    monkeypatch,
) -> None:
    _configure_successful_pipeline(
        MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer
    )
    runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
    monkeypatch.setattr(runner, "_resolve_site_id", lambda url: None)
    injected_id = "0123456789abcdef0123456789abcdef"

    with caplog.at_level(logging.INFO, logger="src.pipeline.pipeline_runner"):
        runner.run(
            url="https://example.com",
            query="신청서 제출서류",
            correlation_id=injected_id,
        )

    event_records = _extract_pipeline_records(caplog)
    assert event_records
    assert {record["correlation_id"] for record in event_records} == {injected_id}


def test_new_correlation_id_is_opaque_hex() -> None:
    from src.observability.event_logger import new_correlation_id

    correlation_id = new_correlation_id()
    assert len(correlation_id) == 32
    assert all(ch in "0123456789abcdef" for ch in correlation_id)


def test_pipeline_failure_emits_stage_fail_and_run_end_false(tmp_path: Path, caplog) -> None:
    output_dir = str(tmp_path / "failed-run")
    runner = PipelineRunner(output_dir=output_dir, provider="mock")
    caplog.set_level(logging.INFO, logger="src.pipeline.pipeline_runner")

    def fake_homepage_map(url: str) -> dict[str, object]:
        path = os.path.join(output_dir, "homepage-map.json")
        PipelineRunner._write_json(path, FAKE_HOMEPAGE_MAP)
        return {"name": "homepage_map", "ok": True, "output": path, "error": ""}

    def fake_document_index(homepage_map: dict) -> dict[str, object]:
        return {
            "name": "document_index",
            "ok": False,
            "output": os.path.join(output_dir, "document-index.jsonl"),
            "error": "Pipeline step failed",
        }

    with patch.object(runner, "_resolve_site_id", return_value="test_site"), \
         patch.object(runner, "_step_homepage_map", side_effect=fake_homepage_map), \
         patch.object(runner, "_step_document_index", side_effect=fake_document_index):
        result = runner.run(url="https://example.com", query="신청서 제출서류")

    event_records = _extract_pipeline_records(caplog)
    assert result["ok"] is False
    assert [record["event"] for record in event_records] == [
        "pipeline_run_start",
        "pipeline_stage_start",
        "pipeline_stage_end",
        "pipeline_stage_start",
        "pipeline_stage_fail",
        "pipeline_run_end",
    ]
    fail_record = event_records[-2]
    assert fail_record["stage"] == "document_index"
    assert fail_record["ok"] is False
    assert fail_record["failure_code"] == "pipeline_step_failed"
    assert event_records[-1]["ok"] is False
    assert "stage" not in event_records[-1]


def test_pipeline_run_links_question_log_to_correlation_id(
    tmp_output_dir: str,
    caplog: pytest.LogCaptureFixture,
    monkeypatch,
) -> None:
    spy_logger = SpyQuestionLogger()
    runner = PipelineRunner(
        output_dir=tmp_output_dir,
        provider="mock",
        question_logger=spy_logger,
    )
    monkeypatch.setattr(runner, "_resolve_site_id", lambda url: "test_site")
    injected_id = "abcdef0123456789abcdef0123456789"

    with caplog.at_level(logging.INFO, logger="src.pipeline.pipeline_runner"):
        runner.run(
            url="https://example.com",
            query="신청서 제출서류",
            correlation_id=injected_id,
        )

    assert len(spy_logger.logged_events) == 1
    assert spy_logger.logged_events[0].correlation_id == injected_id


def test_pipeline_emit_question_log_defaults_correlation_id_none(
    tmp_output_dir: str,
    caplog: pytest.LogCaptureFixture,
    monkeypatch,
) -> None:
    spy_logger = SpyQuestionLogger()
    runner = PipelineRunner(
        output_dir=tmp_output_dir,
        provider="mock",
        question_logger=spy_logger,
    )
    monkeypatch.setattr(runner, "_resolve_site_id", lambda url: "test_site")

    with caplog.at_level(logging.INFO, logger="src.pipeline.pipeline_runner"):
        runner.run(
            url="https://example.com",
            query="신청서 제출서류",
        )

    event_records = _extract_pipeline_records(caplog)
    assert event_records
    generated_id = next(iter({record["correlation_id"] for record in event_records}))
    assert len(spy_logger.logged_events) == 1
    assert spy_logger.logged_events[0].correlation_id == generated_id


def test_pipeline_run_preserves_empty_injected_correlation_id(
    tmp_output_dir: str,
    caplog: pytest.LogCaptureFixture,
    monkeypatch,
) -> None:
    runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
    monkeypatch.setattr(runner, "_resolve_site_id", lambda url: None)

    with caplog.at_level(logging.INFO, logger="src.pipeline.pipeline_runner"):
        runner.run(
            url="https://example.com",
            query="신청서 제출서류",
            correlation_id="",
        )

    event_records = _extract_pipeline_records(caplog)
    assert event_records
    assert {record["correlation_id"] for record in event_records} == {""}


def test_pipeline_step_answer_forwards_empty_correlation_id_to_composer(tmp_path: Path) -> None:
    """_step_answer must pass a caller-provided empty correlation ID verbatim to compose."""
    output_dir = str(tmp_path / "answer-fwd")
    os.makedirs(output_dir, exist_ok=True)

    search_path = os.path.join(output_dir, "search-results.json")
    with open(search_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(FAKE_SEARCH_RESULTS, ensure_ascii=False))

    runner = PipelineRunner(output_dir=output_dir, provider="mock")

    captured: dict[str, Any] = {}

    class SpyAnswerComposer:
        def __init__(self, *args, **kwargs):
            pass

        def compose(self, search_data, max_sources=None, correlation_id=None):
            captured["correlation_id"] = correlation_id
            return {
                "query": "q",
                "provider": "mock",
                "model": "mock",
                "ok": True,
                "answer_markdown": "x",
                "sources": [],
                "warnings": [],
                "error": "",
                "guard_status": None,
                "guard_reason": None,
            }

    with patch("src.pipeline.pipeline_runner.AnswerComposer", SpyAnswerComposer):
        runner._step_answer(
            query="신청서 제출서류",
            search_path=search_path,
            correlation_id="",
        )

    assert captured["correlation_id"] == ""
