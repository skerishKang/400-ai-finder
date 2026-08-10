from __future__ import annotations

import json
from pathlib import Path

from scripts.collect_mvp_failure_artifacts import MAX_LOG_BYTES, collect, sanitize_log_text


def test_log_sanitizer_redacts_sensitive_values_and_bounds_output() -> None:
    raw = (
        "GET /mvp/?question=full-resident-question HTTP/1.1\n"
        "email=user@example.com phone=010-1234-5678\n"
        "Authorization: Bearer abcdefghijklmnop\n"
        '"prompt":"do not upload this"\n'
        "x" * (MAX_LOG_BYTES + 1000)
    )
    safe = sanitize_log_text(raw)
    assert "user@example.com" not in safe
    assert "010-1234-5678" not in safe
    assert "abcdefghijklmnop" not in safe
    assert "do not upload this" not in safe
    assert "full-resident-question" not in safe
    assert len(safe.encode("utf-8")) <= MAX_LOG_BYTES


def test_comparison_artifact_is_whitelisted_summary(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    (source / "comparison-harness-server.log").write_text(
        "GET /examples/page-agent/resident/ HTTP/1.1 200\n",
        encoding="utf-8",
    )
    (source / "comparison-evidence-ci.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "primary_runs": [
                    {
                        "mode": "deterministic",
                        "scenario_id": "apartment_contact",
                        "attempt": 1,
                        "external_request_count": 0,
                        "no_submit_preserved": True,
                        "action_step_count": 2,
                        "question": "resident raw question must not survive",
                        "provider_error": "provider raw error must not survive",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = collect("comparison-evidence", source, output)
    summary_text = (output / "comparison-evidence-summary.json").read_text(encoding="utf-8")
    assert "resident raw question" not in summary_text
    assert "provider raw error" not in summary_text
    summary = json.loads(summary_text)
    assert summary["primary_run_count"] == 1
    assert set(summary["primary_runs"][0]) == {
        "mode",
        "scenario_id",
        "attempt",
        "external_request_count",
        "no_submit_preserved",
        "action_step_count",
    }
    assert manifest["privacy"]["environment_dump_included"] is False
    assert manifest["privacy"]["raw_question_included"] is False


def test_collector_always_writes_manifest_for_missing_optional_logs(tmp_path: Path) -> None:
    output = tmp_path / "output"
    manifest = collect("citizen-browser", tmp_path, output)
    assert (output / "manifest.json").is_file()
    assert manifest["collected"] == []
    assert manifest["missing_optional_sources"] == [
        "housing-e2e-server.log",
        "mobile-link-safety-server.log",
    ]

def test_log_sanitizer_bounds_multibyte_output_by_utf8_bytes() -> None:
    # Korean "가" is 3 UTF-8 bytes. A character-count cap would overshoot
    # the 128 KiB byte limit, so the bound must be enforced on bytes.
    raw = "가" * (MAX_LOG_BYTES + 1000)
    safe = sanitize_log_text(raw)
    assert len(safe.encode("utf-8")) <= MAX_LOG_BYTES


def test_truncation_crossing_secret_is_fully_redacted() -> None:
    # Place the secret line so the OLD truncate-first boundary
    # (text[-MAX_LOG_BYTES:]) would cut through the marker and leave the
    # raw secret tail alive. Redact-first must remove the whole secret.
    unique = "mvp-1231-crossing-secret-9f4e2c7b"
    marker = "Be" + "arer"
    secret_line = "Authorization: " + marker + " " + unique
    prefix = "a" * 64
    suffix = " " * (MAX_LOG_BYTES - 30)
    raw = prefix + secret_line + suffix
    assert len(raw) > MAX_LOG_BYTES

    safe = sanitize_log_text(raw)
    assert unique not in safe
    assert unique[-16:] not in safe
    assert len(safe.encode("utf-8")) <= MAX_LOG_BYTES
