"""Tests for the question logging boundary (Stage 351)."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import pytest

from src.analytics.question_logger import (
    QuestionLogEvent,
    build_question_log_event,
    NoOpQuestionLogger,
    JsonlQuestionLogger,
    sanitize_text,
)
from src.pipeline.pipeline_runner import PipelineRunner


# ------------------------------------------------------------------
# Test Cases for build_question_log_event
# ------------------------------------------------------------------

def test_build_question_log_event_preserves_sanitized_question():
    """Assert raw question is preserved but sanitized, and normalized question is derived."""
    event = build_question_log_event(
        site_id="bukgu_gwangju",
        question="구청장이 누구야? 내 api_key는 sk-12345678901234567890 이다.",
    )
    assert event.site_id == "bukgu_gwangju"
    # Key sk-... should be redacted
    assert "[REDACTED]" in event.raw_question
    assert "sk-12345678901234567890" not in event.raw_question
    # Normalized question derived (stripping particles)
    assert "구청장이 누구야" in event.normalized_question


def test_build_question_log_event_extracts_source_domains():
    """Assert domains are extracted from source URLs only and sanitized."""
    sources = [
        {"url": "https://bukgu.gwangju.kr/menu.es?mid=a101010"},
        {"canonical_url": "http://eminwon.bukgu.gwangju.kr/civil/index.do"},
        {"url": "https://invalid-secret-key-api_key:secretval@test.com/path"},
    ]
    event = build_question_log_event(
        site_id="bukgu_gwangju",
        question="테스트 질문",
        sources=sources,
    )
    assert "bukgu.gwangju.kr" in event.source_domains
    assert "eminwon.bukgu.gwangju.kr" in event.source_domains
    # Secret-like user/pass in URL should be redacted/filtered
    for domain in event.source_domains:
        assert "secretval" not in domain


def test_build_question_log_event_includes_query_rewrite_metadata():
    """Assert query rewrite strategy and candidates are preserved in metadata."""
    query_rewrite = {
        "strategy": "deterministic_v1",
        "queries": ["구청장", "북구청장", "구청장 프로필"],
    }
    event = build_question_log_event(
        site_id="bukgu_gwangju",
        question="구청장이 누구야?",
        query_rewrite=query_rewrite,
    )
    assert event.query_rewrite_strategy == "deterministic_v1"
    assert event.query_rewrite_queries == ("구청장", "북구청장", "구청장 프로필")


def test_question_log_event_redacts_api_key_like_values():
    """Assert key-like credentials in question text or custom fields are redacted."""
    sensitive_inputs = [
        "NVIDIA_API_KEY=abcdef1234567890abcdef1234567890",
        "Authorization: Bearer mytokenval123",
        "password: supersecretpassword",
        "AI_FINDER_LLM_API_KEY: 'sk-OpenAIKeyWithValueOfSuperLongLength'",
    ]
    for inp in sensitive_inputs:
        sanitized = sanitize_text(inp)
        assert "[REDACTED]" in sanitized
        # The original credential values should be removed
        assert "abcdef1234567890" not in sanitized
        assert "mytokenval123" not in sanitized
        assert "supersecretpassword" not in sanitized
        assert "sk-OpenAIKey" not in sanitized


# ------------------------------------------------------------------
# Test Cases for QuestionLoggers
# ------------------------------------------------------------------

def test_noop_question_logger_does_nothing():
    """Assert NoOpQuestionLogger does nothing without throwing errors."""
    logger = NoOpQuestionLogger()
    event = build_question_log_event(site_id="test", question="test question")
    # Should not raise any error
    result = logger.log(event)
    assert result is None


def test_jsonl_question_logger_writes_one_event_per_line(tmp_path):
    """Assert JsonlQuestionLogger creates path and appends serialized events properly."""
    log_file = tmp_path / "questions.jsonl"
    logger = JsonlQuestionLogger(log_file)
    
    event1 = build_question_log_event(site_id="site1", question="First question?")
    event2 = build_question_log_event(site_id="site2", question="Second question?")
    
    logger.log(event1)
    logger.log(event2)
    
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    
    data1 = json.loads(lines[0])
    data2 = json.loads(lines[1])
    assert data1["site_id"] == "site1"
    assert data1["raw_question"] == "First question?"
    assert data2["site_id"] == "site2"
    assert data2["raw_question"] == "Second question?"


def test_jsonl_question_logger_redacts_secrets_before_writing(tmp_path):
    """Assert JsonlQuestionLogger redacts all secrets recursively in the serialized log."""
    log_file = tmp_path / "questions.jsonl"
    logger = JsonlQuestionLogger(log_file)
    
    event = build_question_log_event(
        site_id="site1",
        question="My api key is sk-12345678901234567890",
        provider_mode="NVIDIA_API_KEY=somevaluehere",
    )
    
    logger.log(event)
    
    content = log_file.read_text(encoding="utf-8")
    assert "sk-12345678901234567890" not in content
    assert "somevaluehere" not in content
    assert "[REDACTED]" in content


# ------------------------------------------------------------------
# Boundary / Offline / Integration Checks
# ------------------------------------------------------------------

def test_build_question_log_event_preserves_correlation_id():
    """Assert correlation_id is passed through unchanged to the event."""
    correlation_id = "0123456789abcdef0123456789abcdef"
    event = build_question_log_event(
        site_id="bukgu_gwangju",
        question="구청장이 누구야?",
        correlation_id=correlation_id,
    )
    assert event.correlation_id == correlation_id


def test_jsonl_question_logger_preserves_correlation_id(tmp_path):
    """Assert correlation_id survives JSONL serialization."""
    log_file = tmp_path / "questions.jsonl"
    logger = JsonlQuestionLogger(log_file)

    correlation_id = "0123456789abcdef0123456789abcdef"
    event = build_question_log_event(
        site_id="site1",
        question="First question?",
        correlation_id=correlation_id,
    )
    logger.log(event)

    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["correlation_id"] == correlation_id


def test_build_question_log_event_defaults_correlation_id_none():
    """Assert existing callers without correlation_id keep it None."""
    event = build_question_log_event(site_id="site1", question="no correlation")
    assert event.correlation_id is None


def test_question_logger_imports_no_provider_or_network_modules():
    """Verify that question_logger.py is pure and imports no network/LLM modules."""
    logger_path = Path(__file__).parent.parent / "src" / "analytics" / "question_logger.py"
    with open(logger_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    banned_prefixes = (
        "src.llm",
        "src.fetch",
        "firecrawl",
        "requests",
        "httpx",
        "urllib3",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(banned_prefixes):
                    pytest.fail(f"question_logger should not import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(banned_prefixes):
                pytest.fail(f"question_logger should not import from: {node.module}")


def test_pipeline_can_emit_question_log_event_with_noop_logger(tmp_path):
    """Assert that PipelineRunner accepts logger and runs log logic correctly."""
    # Build mini index
    doc = {
        "id": "doc-01",
        "title": "민원서식",
        "url": "https://bukgu.gwangju.kr/menu.es?mid=a10101040000",
        "category": "document",
        "matched_terms": ["민원서식"],
        "snippet": "민원서식 안내",
    }
    index_path = tmp_path / "enriched-index.jsonl"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    # Custom spy logger to verify interaction
    class SpyLogger(NoOpQuestionLogger):
        def __init__(self):
            self.logged_events = []
        def log(self, event: QuestionLogEvent):
            self.logged_events.append(event)
            
    spy = SpyLogger()
    runner = PipelineRunner(
        output_dir=str(tmp_path),
        provider="mock",
        question_logger=spy,
    )
    
    # Run step search & answer to simulate pipeline execution
    search_step = runner._step_search("민원서식 어디서 받아?", str(index_path))
    assert search_step["ok"] is True
    
    answer_step = runner._step_answer("민원서식 어디서 받아?", search_step["output"])
    assert answer_step["ok"] is True
    
    # Trigger log emission
    runner._emit_question_log(
        url="https://bukgu.gwangju.kr",
        query="민원서식 어디서 받아?",
        steps=[search_step, answer_step]
    )
    
    assert len(spy.logged_events) == 1
    event = spy.logged_events[0]
    assert event.raw_question == "민원서식 어디서 받아?"
    assert event.site_id == "bukgu_gwangju"  # resolved from https://bukgu.gwangju.kr
    assert "bukgu.gwangju.kr" in event.source_domains
    assert event.answer_status in ("success", "no_results")


def test_pipeline_question_logging_does_not_change_answer_behavior(tmp_path):
    """Verify that logging logic is side-effect free and doesn't change outputs."""
    doc = {
        "id": "doc-01",
        "title": "민원서식",
        "url": "https://bukgu.gwangju.kr/menu.es?mid=a10101040000",
        "category": "document",
        "matched_terms": ["민원서식"],
        "snippet": "민원서식 안내",
    }
    index_path = tmp_path / "enriched-index.jsonl"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    # Setup runner with JSONL logger
    log_file = tmp_path / "run_logs.jsonl"
    logger = JsonlQuestionLogger(log_file)
    
    runner_with_logger = PipelineRunner(
        output_dir=str(tmp_path / "run1"),
        provider="mock",
        question_logger=logger,
    )
    
    runner_without_logger = PipelineRunner(
        output_dir=str(tmp_path / "run2"),
        provider="mock",
    )
    
    # Both run keyword search & answer step
    s1 = runner_with_logger._step_search("민원서식", str(index_path))
    a1 = runner_with_logger._step_answer("민원서식", s1["output"])
    
    s2 = runner_without_logger._step_search("민원서식", str(index_path))
    a2 = runner_without_logger._step_answer("민원서식", s2["output"])
    
    # Read answer markdown output
    ans1_md = Path(a1["markdown_output"]).read_text(encoding="utf-8")
    ans2_md = Path(a2["markdown_output"]).read_text(encoding="utf-8")
    
    assert ans1_md == ans2_md
