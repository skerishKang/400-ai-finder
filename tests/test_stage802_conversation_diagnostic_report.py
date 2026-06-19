"""Tests for Stage #802 — fetch diagnostic aggregation report.

These tests exercise ``summarize_conversation_log`` and the CLI wrapper.
No live fetch / network / API / Firecrawl calls.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

import pytest


# Canary strings — must never appear in any aggregated report output.
_CANARIES: tuple[str, ...] = (
    "sk-LIV...cdef",
    "Bearer c4n4ry-token-zzzzzzzzzzzzzzzz",
    "X-Internal-Secret: top-secret",
    "secret_body=THIS_IS_THE_BODY",
    "https://user:p4ssw0rd@host.example/path",
    "VERY_SPECIFIC_STAGE802_CANARY_DO_NOT_LEAK",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_jsonl(path: str, records: list[dict[str, Any]]) -> None:
    """Write ``records`` as JSONL to ``path``."""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _make_record(
    *,
    site_id: str = "bukgu_gwangju",
    route: str = "site_search",
    source_weak: bool = False,
    answer_ok: bool = True,
    warnings: list[str] | None = None,
    fetch_diagnostic_category: str | None = None,
    fetch_diagnostic_retry_hint: str | None = None,
    fetch_diagnostic_is_transient: bool | None = None,
    llm_status: str = "mock_no_api",
    question: str | None = None,
    answer: str | None = None,
) -> dict[str, Any]:
    """Build a single conversation-log record with safe defaults."""
    return {
        "timestamp": "2026-06-19T00:00:00Z",
        "site_id": site_id,
        "site_name": "광주광역시 북구청",
        "question": question or "민원서식 어디서 받아?",
        "answer": answer if answer is not None else "...",
        "provider": "stub",
        "model": "stub",
        "llm_status": llm_status,
        "llm_live": False,
        "answer_ok": answer_ok,
        "sources_count": 0,
        "source_weak": source_weak,
        "sources": [],
        "fallback_used": False,
        "warnings": warnings if warnings is not None else [],
        "route": route,
        "should_search_site": route == "site_search",
        "route_confidence": 0.9,
        "route_reason": "match",
        "search_query": "민원서식",
        "answer_mode": "retrieval_answer",
        "fetch_diagnostic_category": fetch_diagnostic_category,
        "fetch_diagnostic_short_reason": (
            "Request exceeded its deadline."
            if fetch_diagnostic_category == "timeout"
            else None
        ),
        "fetch_diagnostic_retry_hint": fetch_diagnostic_retry_hint,
        "fetch_diagnostic_is_transient": fetch_diagnostic_is_transient,
    }


# ---------------------------------------------------------------------------
# 1. Aggregation helper — well-formed records
# ---------------------------------------------------------------------------


class TestAggregateWellFormed:
    def test_multiple_records_aggregate_correctly(self, tmp_path: Any) -> None:
        from src.demo.conversation_log_report import summarize_conversation_log

        log_path = str(tmp_path / "conversations.jsonl")
        records = [
            _make_record(route="site_search", source_weak=True, answer_ok=False,
                         warnings=["w1"],
                         fetch_diagnostic_category="timeout",
                         fetch_diagnostic_retry_hint="retry",
                         fetch_diagnostic_is_transient=True),
            _make_record(route="direct_answer", answer_ok=True,
                         fetch_diagnostic_category=None,
                         fetch_diagnostic_retry_hint=None,
                         fetch_diagnostic_is_transient=None),
            _make_record(route="clarify", answer_ok=True),
            _make_record(route="site_search", source_weak=True, answer_ok=False,
                         warnings=["w2"],
                         fetch_diagnostic_category="blocked_or_forbidden",
                         fetch_diagnostic_retry_hint="do_not_retry",
                         fetch_diagnostic_is_transient=False),
        ]
        _write_jsonl(log_path, records)

        summary = summarize_conversation_log(log_path)

        assert summary["total_records"] == 4
        assert summary["malformed_line_count"] == 0
        assert summary["source_weak_count"] == 2
        assert summary["answer_ok_false_count"] == 2
        assert summary["records_with_warnings_count"] == 2
        assert summary["fetch_diagnostic_transient_count"] == 1

        assert summary["route_counts"] == {
            "site_search": 2,
            "direct_answer": 1,
            "clarify": 1,
        }
        assert summary["fetch_diagnostic_category_counts"] == {
            "timeout": 1,
            "blocked_or_forbidden": 1,
            "none": 2,
        }
        assert summary["fetch_diagnostic_retry_hint_counts"] == {
            "retry": 1,
            "do_not_retry": 1,
            "none": 2,
        }

    def test_only_count_is_transient_true(self, tmp_path: Any) -> None:
        """The aggregator counts only the ``True`` value for transient
        — the False / None buckets are noise on this metric.
        """
        from src.demo.conversation_log_report import summarize_conversation_log

        log_path = str(tmp_path / "conversations.jsonl")
        records = [
            _make_record(fetch_diagnostic_is_transient=True),
            _make_record(fetch_diagnostic_is_transient=False),
            _make_record(fetch_diagnostic_is_transient=None),
            _make_record(fetch_diagnostic_is_transient=True),
        ]
        _write_jsonl(log_path, records)
        summary = summarize_conversation_log(log_path)

        assert summary["fetch_diagnostic_transient_count"] == 2


# ---------------------------------------------------------------------------
# 2. Malformed line handling
# ---------------------------------------------------------------------------


class TestMalformedLines:
    def test_malformed_line_skipped_and_counted(self, tmp_path: Any) -> None:
        from src.demo.conversation_log_report import summarize_conversation_log

        log_path = str(tmp_path / "conversations.jsonl")
        # Mix of valid + malformed lines.
        lines = [
            json.dumps(_make_record()),
            "{not valid json",
            "   ",
            json.dumps(_make_record()),
            '["not a dict"]',  # valid JSON but not a dict
            "",
        ]
        with open(log_path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")

        summary = summarize_conversation_log(log_path)

        # Two valid dict records, one malformed (JSON parse) and one
        # not-a-dict line. Trailing blanks are not counted as malformed.
        assert summary["total_records"] == 2
        assert summary["malformed_line_count"] == 2

    def test_malformed_content_never_returned(self, tmp_path: Any) -> None:
        """The aggregator must never echo raw malformed-line content
        (which could contain secrets) back to the caller.
        """
        from src.demo.conversation_log_report import summarize_conversation_log

        log_path = str(tmp_path / "conversations.jsonl")
        # Inject canary inside the malformed line.
        bad_line = "this line contains sk-LIV...cdef and Bearer c4n4ry-token-zzzzzzzzzzzzzzzz"
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(bad_line + "\n")

        summary = summarize_conversation_log(log_path)
        serialized = json.dumps(summary, ensure_ascii=False)
        for canary in _CANARIES:
            assert canary not in serialized


# ---------------------------------------------------------------------------
# 3. Missing / unknown field handling
# ---------------------------------------------------------------------------


class TestMissingFields:
    def test_missing_route_bucketed_as_none(self, tmp_path: Any) -> None:
        from src.demo.conversation_log_report import summarize_conversation_log

        log_path = str(tmp_path / "conversations.jsonl")
        records = [
            _make_record(route="site_search"),
            {"timestamp": "2026-06-19T00:00:00Z"},  # no route key at all
        ]
        _write_jsonl(log_path, records)

        summary = summarize_conversation_log(log_path)
        assert summary["total_records"] == 2
        assert summary["route_counts"] == {
            "site_search": 1,
            "none": 1,
        }

    def test_missing_fetch_diagnostic_bucketed_as_none(
        self, tmp_path: Any
    ) -> None:
        from src.demo.conversation_log_report import summarize_conversation_log

        log_path = str(tmp_path / "conversations.jsonl")
        records = [
            _make_record(
                fetch_diagnostic_category=None,
                fetch_diagnostic_retry_hint=None,
                fetch_diagnostic_is_transient=None,
            ),
            # Record with no diagnostic columns at all (legacy shape).
            {"timestamp": "2026-06-19T00:00:00Z", "route": "site_search"},
        ]
        _write_jsonl(log_path, records)

        summary = summarize_conversation_log(log_path)
        assert summary["fetch_diagnostic_category_counts"] == {"none": 2}
        assert summary["fetch_diagnostic_retry_hint_counts"] == {"none": 2}
        assert summary["fetch_diagnostic_transient_count"] == 0

    def test_empty_file_returns_empty_summary(self, tmp_path: Any) -> None:
        from src.demo.conversation_log_report import summarize_conversation_log

        log_path = str(tmp_path / "conversations.jsonl")
        # File exists but is empty.
        open(log_path, "w", encoding="utf-8").close()

        summary = summarize_conversation_log(log_path)
        assert summary == {
            "total_records": 0,
            "malformed_line_count": 0,
            "route_counts": {},
            "site_id_counts": {},
            "llm_status_counts": {},
            "source_weak_count": 0,
            "answer_ok_false_count": 0,
            "records_with_warnings_count": 0,
            "fetch_diagnostic_category_counts": {},
            "fetch_diagnostic_retry_hint_counts": {},
            "fetch_diagnostic_transient_count": 0,
            # Stage #803: closed-vocab answer_status aggregation. The
            # empty summary carries an empty dict so downstream
            # consumers can rely on the key being present.
            "answer_status_counts": {},
        }

    def test_missing_file_returns_empty_summary(self, tmp_path: Any) -> None:
        from src.demo.conversation_log_report import summarize_conversation_log

        missing = str(tmp_path / "does-not-exist.jsonl")
        summary = summarize_conversation_log(missing)
        assert summary["total_records"] == 0
        assert summary["malformed_line_count"] == 0

    def test_empty_path_returns_empty_summary(self) -> None:
        from src.demo.conversation_log_report import summarize_conversation_log

        assert summarize_conversation_log("")["total_records"] == 0


# ---------------------------------------------------------------------------
# 4. No canary leakage from any record field
# ---------------------------------------------------------------------------


class TestNoCanaryLeakage:
    """The aggregator must never echo raw ``question``, ``answer``,
    ``warnings``, exception text, headers, bodies, provider payloads,
    API keys, or URL credentials — even if those fields are crammed
    with canary strings.
    """

    def test_question_canary_not_in_summary(self, tmp_path: Any) -> None:
        from src.demo.conversation_log_report import summarize_conversation_log

        log_path = str(tmp_path / "conversations.jsonl")
        records = [
            _make_record(
                question=(
                    "민원서식 sk-LIV...cdef Bearer c4n4ry-token-zzzzzzzzzzzzzzzz"
                ),
                warnings=[
                    "X-Internal-Secret: top-secret secret_body=THIS_IS_THE_BODY"
                ],
                answer=(
                    "answer https://user:p4ssw0rd@host.example/path "
                    "VERY_SPECIFIC_STAGE802_CANARY_DO_NOT_LEAK"
                ),
            ),
        ]
        _write_jsonl(log_path, records)

        summary = summarize_conversation_log(log_path)
        serialized = json.dumps(summary, ensure_ascii=False)
        for canary in _CANARIES:
            assert canary not in serialized, (
                f"canary {canary!r} leaked into summary"
            )

    def test_text_summary_format_does_not_leak_canary(self, tmp_path: Any) -> None:
        from src.demo.conversation_log_report import (
            format_text_summary,
            summarize_conversation_log,
        )

        log_path = str(tmp_path / "conversations.jsonl")
        records = [
            _make_record(
                question="sk-LIV...cdef",
                answer="Bearer c4n4ry-token-zzzzzzzzzzzzzzzz",
                warnings=["X-Internal-Secret: top-secret"],
            ),
        ]
        _write_jsonl(log_path, records)

        summary = summarize_conversation_log(log_path)
        text = format_text_summary(summary)
        for canary in _CANARIES:
            assert canary not in text


# ---------------------------------------------------------------------------
# 5. CLI smoke
# ---------------------------------------------------------------------------


def _run_cli(log_path: str, *extra_args: str) -> tuple[int, str, str]:
    """Run the CLI as a subprocess and return (rc, stdout, stderr).

    We always set ``PYTHONPATH=.`` and use ``sys.executable`` so the
    subprocess sees the same venv as the test runner.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    project_root = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    cmd = [
        sys.executable,
        os.path.join(project_root, "scripts", "report_conversation_diagnostics.py"),
        "--log-path",
        log_path,
        *extra_args,
    ]
    proc = subprocess.run(
        cmd,
        env=env,
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestCLI:
    def test_cli_text_output_runs(self, tmp_path: Any) -> None:
        log_path = str(tmp_path / "conversations.jsonl")
        _write_jsonl(
            log_path,
            [
                _make_record(
                    fetch_diagnostic_category="timeout",
                    fetch_diagnostic_retry_hint="retry",
                    fetch_diagnostic_is_transient=True,
                )
            ],
        )
        rc, stdout, stderr = _run_cli(log_path)
        assert rc == 0, stderr
        assert "Conversation log summary" in stdout
        assert "total_records: 1" in stdout
        assert "route_counts:" in stdout

    def test_cli_json_output_is_parseable(self, tmp_path: Any) -> None:
        log_path = str(tmp_path / "conversations.jsonl")
        _write_jsonl(
            log_path,
            [
                _make_record(
                    fetch_diagnostic_category="blocked_or_forbidden",
                    fetch_diagnostic_retry_hint="do_not_retry",
                    fetch_diagnostic_is_transient=False,
                ),
                _make_record(route="direct_answer"),
            ],
        )
        rc, stdout, stderr = _run_cli(log_path, "--json")
        assert rc == 0, stderr
        summary = json.loads(stdout)
        assert summary["total_records"] == 2
        assert summary["fetch_diagnostic_category_counts"] == {
            "blocked_or_forbidden": 1,
            "none": 1,
        }

    def test_cli_text_does_not_leak_canary(self, tmp_path: Any) -> None:
        log_path = str(tmp_path / "conversations.jsonl")
        _write_jsonl(
            log_path,
            [
                _make_record(
                    question="sk-LIV...cdef Bearer c4n4ry-token-zzzzzzzzzzzzzzzz",
                    answer="X-Internal-Secret: top-secret secret_body=THIS_IS_THE_BODY",
                    warnings=[
                        "https://user:p4ssw0rd@host.example/path "
                        "VERY_SPECIFIC_STAGE802_CANARY_DO_NOT_LEAK"
                    ],
                )
            ],
        )
        rc, stdout, stderr = _run_cli(log_path)
        assert rc == 0, stderr
        for canary in _CANARIES:
            assert canary not in stdout
        # No warning content either.
        assert "Pipeline raised" not in stdout

    def test_cli_json_does_not_leak_canary(self, tmp_path: Any) -> None:
        log_path = str(tmp_path / "conversations.jsonl")
        _write_jsonl(
            log_path,
            [
                _make_record(
                    question="sk-LIV...cdef",
                    answer="Bearer c4n4ry-token-zzzzzzzzzzzzzzzz",
                    warnings=["X-Internal-Secret: top-secret"],
                )
            ],
        )
        rc, stdout, stderr = _run_cli(log_path, "--json")
        assert rc == 0, stderr
        summary = json.loads(stdout)
        for canary in _CANARIES:
            assert canary not in stdout
        # The summary must round-trip through json.dumps without
            # echoing the canary, even via the loader.
        assert "question" not in summary
        assert "answer" not in summary
        assert "warnings" not in summary

    def test_cli_missing_file_returns_empty_summary(
        self, tmp_path: Any
    ) -> None:
        log_path = str(tmp_path / "does-not-exist.jsonl")
        rc, stdout, stderr = _run_cli(log_path, "--json")
        assert rc == 0, stderr
        summary = json.loads(stdout)
        assert summary["total_records"] == 0
        assert summary["malformed_line_count"] == 0
