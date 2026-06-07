"""Tests for the repeated-question analytics dry-run report CLI (Stage 353)."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
import pytest


# ------------------------------------------------------------------
# Test Fixtures
# ------------------------------------------------------------------

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "analyze_question_logs.py"


def make_synthetic_events() -> list[dict]:
    """Create synthetic sanitized question log events for testing."""
    return [
        # Repeated successful question (promotion candidate)
        {
            "timestamp": "2026-06-01T10:00:00Z",
            "site_id": "bukgu_gwangju",
            "raw_question": "구청장이 누구야?",
            "normalized_question": "구청장 누구야",
            "answer_status": "success",
            "fallback_used": False,
            "guard_status": "pass",
            "source_domains": ["bukgu.gwangju.kr"],
            "result_count": 3,
        },
        {
            "timestamp": "2026-06-01T10:05:00Z",
            "site_id": "bukgu_gwangju",
            "raw_question": "구청장 누구야?",
            "normalized_question": "구청장 누구야",
            "answer_status": "success",
            "fallback_used": False,
            "guard_status": "pass",
            "source_domains": ["bukgu.gwangju.kr"],
            "result_count": 4,
        },
        {
            "timestamp": "2026-06-01T10:10:00Z",
            "site_id": "bukgu_gwangju",
            "raw_question": "구청장분 누구세요",
            "normalized_question": "구청장 누구야",
            "answer_status": "success",
            "fallback_used": False,
            "guard_status": "pass",
            "source_domains": ["bukgu.gwangju.kr"],
            "result_count": 2,
        },
        # Repeated NO_RESULTS question (retrieval gap)
        {
            "timestamp": "2026-06-01T11:00:00Z",
            "site_id": "bukgu_gwangju",
            "raw_question": "이상한 질문 테스트",
            "normalized_question": "이상한 질문 테스트",
            "answer_status": "no_results",
            "fallback_used": False,
            "guard_status": "no_results",
            "source_domains": [],
            "result_count": 0,
        },
        {
            "timestamp": "2026-06-01T11:05:00Z",
            "site_id": "bukgu_gwangju",
            "raw_question": "이상한 질문 테스트",
            "normalized_question": "이상한 질문 테스트",
            "answer_status": "no_results",
            "fallback_used": False,
            "guard_status": "no_results",
            "source_domains": [],
            "result_count": 0,
        },
        {
            "timestamp": "2026-06-01T11:10:00Z",
            "site_id": "bukgu_gwangju",
            "raw_question": "이상한 질문 테스트",
            "normalized_question": "이상한 질문 테스트",
            "answer_status": "no_results",
            "fallback_used": False,
            "guard_status": "no_results",
            "source_domains": [],
            "result_count": 0,
        },
    ]


def write_jsonl(events: list[dict], path: Path) -> None:
    """Write events as JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def run_cli(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run the CLI script via subprocess and return (returncode, stdout, stderr)."""
    if cwd is None:
        cwd = Path(__file__).parent.parent
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)] + args,
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )
    return result.returncode, result.stdout, result.stderr


# ------------------------------------------------------------------
# Core CLI Tests
# ------------------------------------------------------------------

def test_cli_generates_markdown_report_for_repeated_successful_questions(tmp_path):
    """Assert CLI produces a Markdown report for repeated successful questions."""
    input_file = tmp_path / "question-log.jsonl"
    output_file = tmp_path / "report.md"
    
    events = make_synthetic_events()
    write_jsonl(events, input_file)
    
    returncode, stdout, stderr = run_cli([
        "--input", str(input_file),
        "--output", str(output_file),
        "--min-count", "3",
    ])
    
    assert returncode == 0, f"CLI failed: {stderr}"
    assert output_file.exists()
    
    content = output_file.read_text(encoding="utf-8")
    assert "# Repeated Question Analytics Dry-Run Report" in content
    assert "Promotion candidates" in content
    assert "Retrieval gaps" in content
    assert "구청장" in content


def test_cli_separates_retrieval_gaps_from_promotion_candidates(tmp_path):
    """Assert CLI separates retrieval gaps from promotion candidates in report."""
    input_file = tmp_path / "question-log.jsonl"
    output_file = tmp_path / "report.md"
    
    events = make_synthetic_events()
    write_jsonl(events, input_file)
    
    returncode, _, stderr = run_cli([
        "--input", str(input_file),
        "--output", str(output_file),
    ])
    
    assert returncode == 0, f"CLI failed: {stderr}"
    
    content = output_file.read_text(encoding="utf-8")
    
    # Both sections should be present
    assert "## Promotion candidates for human review" in content
    assert "## Retrieval gaps" in content
    
    # Summary should report both counts
    assert "Promotion candidates:" in content
    assert "Retrieval gaps:" in content


def test_cli_respects_min_count(tmp_path):
    """Assert CLI only includes questions with count >= min_count."""
    input_file = tmp_path / "question-log.jsonl"
    output_file = tmp_path / "report.md"
    
    # Use min_count=10 — nothing should be included
    write_jsonl(make_synthetic_events(), input_file)
    
    returncode, _, stderr = run_cli([
        "--input", str(input_file),
        "--output", str(output_file),
        "--min-count", "10",
    ])
    
    assert returncode == 0, f"CLI failed: {stderr}"
    
    content = output_file.read_text(encoding="utf-8")
    assert "Promotion candidates: 0" in content
    assert "Retrieval gaps: 0" in content


def test_cli_skips_blank_jsonl_lines(tmp_path):
    """Assert CLI skips blank lines in JSONL input."""
    input_file = tmp_path / "question-log.jsonl"
    output_file = tmp_path / "report.md"
    
    events = make_synthetic_events()
    with open(input_file, "w", encoding="utf-8") as f:
        # Add blank lines interspersed
        f.write("\n")
        for i, e in enumerate(events):
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
            if i % 2 == 0:
                f.write("   \n")  # whitespace-only line
    
    returncode, _, stderr = run_cli([
        "--input", str(input_file),
        "--output", str(output_file),
    ])
    
    assert returncode == 0, f"CLI failed: {stderr}"
    assert output_file.exists()


def test_cli_fails_with_line_number_on_invalid_json(tmp_path):
    """Assert CLI fails with line number when encountering invalid JSON."""
    input_file = tmp_path / "question-log.jsonl"
    output_file = tmp_path / "report.md"
    
    with open(input_file, "w", encoding="utf-8") as f:
        f.write('{"valid": "json"}\n')
        f.write('this is not valid json\n')
        f.write('{"another": "valid"}\n')
    
    returncode, stdout, stderr = run_cli([
        "--input", str(input_file),
        "--output", str(output_file),
    ])
    
    assert returncode != 0
    assert "line" in stderr.lower() or "line" in stdout.lower()


def test_cli_redacts_secret_like_values_in_report(tmp_path):
    """Assert CLI redacts secret-like values in the generated report."""
    input_file = tmp_path / "question-log.jsonl"
    output_file = tmp_path / "report.md"
    
    # Create events with secret-like values in the normalized_question field
    # which will appear in the report
    events = [
        {
            "timestamp": "2026-06-01T10:00:00Z",
            "site_id": "bukgu_gwangju",
            "raw_question": "test question",
            "normalized_question": "test my api_key=SuperSecret1234567890abcdef question",
            "answer_status": "success",
            "fallback_used": False,
            "guard_status": "pass",
            "source_domains": ["bukgu.gwangju.kr"],
            "result_count": 1,
        }
    ] * 3
    
    write_jsonl(events, input_file)
    
    returncode, _, stderr = run_cli([
        "--input", str(input_file),
        "--output", str(output_file),
    ])
    
    assert returncode == 0, f"CLI failed: {stderr}"
    
    content = output_file.read_text(encoding="utf-8")
    
    # Secret should be redacted
    assert "SuperSecret1234567890abcdef" not in content
    assert "[REDACTED]" in content


def test_cli_does_not_create_scenario_snapshot_or_cache_files(tmp_path):
    """Assert CLI only creates the requested output report and nothing else."""
    input_file = tmp_path / "question-log.jsonl"
    output_file = tmp_path / "report.md"
    
    # Use a subdirectory to monitor
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    input_file = work_dir / "question-log.jsonl"
    output_file = work_dir / "report.md"
    
    write_jsonl(make_synthetic_events(), input_file)
    
    # Record files before
    files_before = set(work_dir.rglob("*"))
    
    returncode, _, stderr = run_cli([
        "--input", str(input_file),
        "--output", str(output_file),
    ])
    
    assert returncode == 0, f"CLI failed: {stderr}"
    
    files_after = set(work_dir.rglob("*"))
    
    new_files = files_after - files_before
    
    # Only the output file should be created
    assert new_files == {output_file}, f"Unexpected files created: {new_files}"


def test_cli_imports_no_provider_or_network_modules():
    """Verify that the CLI script does not import network/LLM/provider modules."""
    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        source = f.read()
    
    tree = ast.parse(source)
    banned_prefixes = ("src.llm", "src.fetch", "firecrawl", "requests", "httpx", "urllib3")
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(banned_prefixes):
                    pytest.fail(f"CLI script should not import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(banned_prefixes):
                pytest.fail(f"CLI script should not import from: {node.module}")


def test_cli_report_contains_dry_run_wording(tmp_path):
    """Assert generated report contains dry-run / human review wording."""
    input_file = tmp_path / "question-log.jsonl"
    output_file = tmp_path / "report.md"
    
    write_jsonl(make_synthetic_events(), input_file)
    
    returncode, _, stderr = run_cli([
        "--input", str(input_file),
        "--output", str(output_file),
    ])
    
    assert returncode == 0, f"CLI failed: {stderr}"
    
    content = output_file.read_text(encoding="utf-8")
    content_lower = content.lower()
    
    assert "dry-run" in content_lower
    assert "human review" in content_lower or "human-review" in content_lower


def test_cli_filters_by_site_id(tmp_path):
    """Assert --site-id filter works correctly."""
    input_file = tmp_path / "question-log.jsonl"
    output_file = tmp_path / "report.md"
    
    events = [
        {
            "timestamp": "2026-06-01T10:00:00Z",
            "site_id": "bukgu_gwangju",
            "raw_question": "구청장이 누구야?",
            "normalized_question": "구청장 누구야",
            "answer_status": "success",
            "fallback_used": False,
            "guard_status": "pass",
            "source_domains": ["bukgu.gwangju.kr"],
            "result_count": 3,
        }
    ] * 3
    # Add events for different site
    events.extend([
        {
            "timestamp": "2026-06-01T10:00:00Z",
            "site_id": "gwangju_go_kr",
            "raw_question": "시청장이 누구야?",
            "normalized_question": "시청장 누구야",
            "answer_status": "success",
            "fallback_used": False,
            "guard_status": "pass",
            "source_domains": ["www.gwangju.go.kr"],
            "result_count": 3,
        }
    ] * 3)
    
    write_jsonl(events, input_file)
    
    returncode, _, stderr = run_cli([
        "--input", str(input_file),
        "--output", str(output_file),
        "--site-id", "bukgu_gwangju",
    ])
    
    assert returncode == 0, f"CLI failed: {stderr}"
    
    content = output_file.read_text(encoding="utf-8")
    assert "bukgu_gwangju" in content
    assert "gwangju_go_kr" not in content or "Site filter" in content
