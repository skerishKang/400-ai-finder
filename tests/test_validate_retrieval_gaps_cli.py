"""Tests for scripts/validate_retrieval_gaps.py"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.validate_retrieval_gaps import (
    _REQUIRED_REPORT_FIELDS,
    _REQUIRED_SOURCE_FIELDS,
    _PROHIBITED_REPORT_FIELDS,
    _ANSWER_GENERATION_FIELDS,
    build_validation_report,
    load_questions_file,
    sanitize_sources,
    validate_question,
    write_json_report,
    write_text_report,
    _retrieval_only,
)


@pytest.fixture()
def questions_file(tmp_path: Path) -> str:
    data = {
        "questions": [
            "민원서식 어디서 받아?",
            "구청장이 누구야?",
            "주차장이 어디있어?",
        ]
    }
    path = tmp_path / "questions.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


@pytest.fixture()
def sample_search_results() -> list[dict[str, Any]]:
    return [
        {
            "title": "광주북구 통합민원안내",
            "url": "https://bukgu.gwangju.kr/menu.es?mid=a10101040000",
            "canonical_url": None,
            "category": "menu",
            "content_type": "page",
            "score": 12.5,
            "matched_terms": ["민원", "서식"],
            "matched_fields": ["title", "text"],
            "snippet": "민원서식 다운로드 안내",
            "description": "북구청 민원서식 목록",
            "metadata": {
                "description": "북구청 민원서식 목록",
                "fetch_status": "ok",
                "source_types": ["navigation", "sitemap"],
            },
        }
    ]


class TestLoadQuestionsFile:
    def test_valid_file(self, questions_file: str) -> None:
        questions = load_questions_file(questions_file)
        assert len(questions) == 3
        assert questions[0] == "민원서식 어디서 받아?"

    def test_missing_file(self) -> None:
        with pytest.raises(SystemExit):
            load_questions_file("/nonexistent/path/questions.json")

    def test_invalid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(SystemExit):
            load_questions_file(str(path))

    def test_missing_questions_key(self, tmp_path: Path) -> None:
        path = tmp_path / "no_key.json"
        path.write_text(json.dumps({"other": []}, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(SystemExit):
            load_questions_file(str(path))

    def test_questions_not_list(self, tmp_path: Path) -> None:
        path = tmp_path / "not_list.json"
        path.write_text(json.dumps({"questions": "string"}, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(SystemExit):
            load_questions_file(str(path))

    def test_questions_empty_list(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.json"
        path.write_text(json.dumps({"questions": []}, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(SystemExit):
            load_questions_file(str(path))

    def test_blank_question_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "blank.json"
        path.write_text(
            json.dumps({"questions": ["valid", "", "  "]}, ensure_ascii=False),
            encoding="utf-8",
        )
        with pytest.raises(SystemExit):
            load_questions_file(str(path))

    def test_non_string_question_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "non_string.json"
        path.write_text(
            json.dumps({"questions": ["valid", 123]}, ensure_ascii=False),
            encoding="utf-8",
        )
        with pytest.raises(SystemExit):
            load_questions_file(str(path))


class TestSanitizeSources:
    def test_basic_sanitization(self, sample_search_results: list[dict[str, Any]]) -> None:
        cleaned = sanitize_sources(sample_search_results)
        assert len(cleaned) == 1
        src = cleaned[0]
        assert "title" in src
        assert "url" in src
        assert src["url"].startswith("https://")

    def test_prohibited_fields_absent(self, sample_search_results: list[dict[str, Any]]) -> None:
        cleaned = sanitize_sources(sample_search_results)
        for src in cleaned:
            assert "full_text" not in src
            assert "prompt" not in src
            assert "raw_provider_response" not in src
            assert "api_key" not in src
            assert "secret" not in src

    def test_empty_input(self) -> None:
        cleaned = sanitize_sources([])
        assert cleaned == []


class TestBuildValidationReport:
    def test_required_fields_present(self, sample_search_results: list[dict[str, Any]]) -> None:
        report = build_validation_report(
            site_id="bukgu_gwangju",
            question="민원서식 어디서 받아?",
            ok=True,
            error="",
            source_count=1,
            guard_status="ok",
            guard_reason="",
            search_results=sample_search_results,
            query_rewrite={"queries": ["민원서식"], "site_id": "bukgu_gwangju"},
        )
        missing = _REQUIRED_REPORT_FIELDS - set(report.keys())
        assert not missing, f"Missing fields: {missing}"

    def test_prohibited_fields_absent(self, sample_search_results: list[dict[str, Any]]) -> None:
        report = build_validation_report(
            site_id="bukgu_gwangju",
            question="민원서식 어디서 받아?",
            ok=True,
            error="",
            source_count=1,
            guard_status="ok",
            guard_reason="",
            search_results=sample_search_results,
            query_rewrite={"queries": ["민원서식"]},
        )
        extra = _PROHIBITED_REPORT_FIELDS & set(report.keys())
        assert not extra, f"Prohibited fields found: {extra}"

    def test_answer_generation_fields_absent(self, sample_search_results: list[dict[str, Any]]) -> None:
        report = build_validation_report(
            site_id="bukgu_gwangju",
            question="test",
            ok=True,
            error="",
            source_count=1,
            guard_status="ok",
            guard_reason="",
            search_results=sample_search_results,
            query_rewrite={},
        )
        for field in _ANSWER_GENERATION_FIELDS:
            assert field not in report, f"Unexpected answer-generation field: {field}"

    def test_top_sources_allowed_fields_only(self, sample_search_results: list[dict[str, Any]]) -> None:
        report = build_validation_report(
            site_id="bukgu_gwangju",
            question="test",
            ok=True,
            error="",
            source_count=1,
            guard_status="ok",
            guard_reason="",
            search_results=sample_search_results,
            query_rewrite={},
        )
        for src in report["top_sources"]:
            assert set(src.keys()) == _REQUIRED_SOURCE_FIELDS


class TestValidateQuestion:
    def test_requires_allow_live_with_live_provider(self) -> None:
        result = validate_question(
            site_id="bukgu_gwangju",
            question="구청장이 누구야?",
            provider=None,
            model=None,
            fetch_provider=None,
            allow_live=False,
        )
        assert result["ok"] is False
        assert result["guard_status"] == "blocked"
        assert "--allow-live" in (result.get("error") or "")

    def test_offline_mock_path_allowed(self) -> None:
        from scripts.validate_retrieval_gaps import _requires_live_opt_in

        assert _requires_live_opt_in(provider="mock", fetch_provider="mock") is False

    def test_cli_main_offline_default_succeeds(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from scripts.validate_retrieval_gaps import main

        questions_path = tmp_path / "questions.json"
        questions_path.write_text(
            json.dumps({"questions": ["민원서식 어디서 받아?"]}, ensure_ascii=False),
            encoding="utf-8",
        )

        main(["--site-id", "bukgu_gwangju", "--questions-file", str(questions_path)])
        captured = capsys.readouterr().out
        assert "민원서식 어디서 받아?" in captured

    def test_live_fetch_blocked_before_retrieval_only(self) -> None:
        result = validate_question(
            site_id="bukgu_gwangju",
            question="구청장이 누구야?",
            provider="openai_compatible",
            fetch_provider="requests",
            allow_live=False,
        )
        assert result["ok"] is False
        assert result["guard_status"] == "blocked"
        assert "--allow-live" in (result.get("error") or "")

    def test_report_excludes_answer_generation_fields_on_blocked(self) -> None:
        result = validate_question(
            site_id="bukgu_gwangju",
            question="구청장이 누구야?",
            provider="openai_compatible",
            fetch_provider="requests",
            allow_live=False,
        )
        for field in [
            "answer",
            "answer_markdown",
            "answer_md",
            "prompt",
            "messages",
            "raw_provider_response",
            "provider_response",
            "completion",
            "full_text",
            "text",
        ]:
            assert field not in result


class TestRetrievalOnlyBoundary:
    def test_does_not_call_answer_composer(self, questions_file: str, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.answer.answer_composer import AnswerComposer as RealAnswerComposer
        from scripts.validate_retrieval_gaps import _retrieval_only

        compose_calls: list[list[Any]] = []

        def fake_compose(self, *args, **kwargs):
            compose_calls.append([args, kwargs])
            raise AssertionError("AnswerComposer.compose must not be called in retrieval-only path")

        monkeypatch.setattr(RealAnswerComposer, "compose", fake_compose)
        _retrieval_only(
            site_id="bukgu_gwangju",
            question="민원서식 어디서 받아?",
            provider="mock",
            fetch_provider="mock",
        )
        assert not compose_calls

    def test_does_not_create_answer_artifacts(self, questions_file: str, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.pipeline.pipeline_runner import PipelineRunner
        from scripts.validate_retrieval_gaps import _retrieval_only

        def fake_step_answer(self, *args, **kwargs):
            raise AssertionError("_step_answer must not be called in retrieval-only path")

        monkeypatch.setattr(PipelineRunner, "_step_answer", fake_step_answer)
        result = _retrieval_only(
            site_id="bukgu_gwangju",
            question="민원서식 어디서 받아?",
            provider="mock",
            fetch_provider="mock",
        )
        assert not result.get("answer_paths")

    def test_does_not_call_provider_complete(self, questions_file: str, monkeypatch: pytest.MonkeyPatch) -> None:
        from scripts.validate_retrieval_gaps import _retrieval_only

        class DummyPipelineRunner:
            def __init__(self, *args, **kwargs):
                pass

            def _step_homepage_map(self, *args, **kwargs):
                return {"ok": True, "output": ""}

            def _load_json(self, *args, **kwargs):
                return {}

            def _step_document_index(self, *args, **kwargs):
                return {"ok": True, "output": ""}

            def _step_enriched_index(self, *args, **kwargs):
                return {"ok": True, "output": ""}

            def _step_search(self, *args, **kwargs):
                return {"ok": True, "output": ""}

        monkeypatch.setattr("src.pipeline.pipeline_runner.PipelineRunner", DummyPipelineRunner)
        _retrieval_only(
            site_id="bukgu_gwangju",
            question="민원서식 어디서 받아?",
            provider="mock",
            fetch_provider="mock",
        )
