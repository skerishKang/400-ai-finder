from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.collect_mvp_failure_artifacts import (
    MAX_LOG_BYTES,
    MAX_PNG_BYTES,
    MAX_TRACE_BYTES,
    PNG_MAGIC,
    TRACE_FILENAME,
    VISUAL_FILENAMES,
    ZIP_MAGIC,
    collect,
    sanitize_log_text,
)

EXACT_18_PNGS = [
    "320-entry.png",
    "320-confirm.png",
    "320-first-action.png",
    "320-search-typing.png",
    "320-result.png",
    "320-view-switch.png",
    "320-reset.png",
    "390-entry.png",
    "390-confirm.png",
    "390-first-action.png",
    "390-search-typing.png",
    "390-result.png",
    "390-view-switch.png",
    "390-reset.png",
    "390-writing-route.png",
    "390-writing-typing.png",
    "390-writing-cancelled.png",
    "1440-desktop.png",
]


def _make_visual_tree(source: Path) -> Path:
    """Create a valid visual evidence tree: 18 PNGs + trace (allowlisted)."""
    visual = source / "400-ai-finder-1116"
    visual.mkdir(parents=True, exist_ok=True)
    for name in EXACT_18_PNGS:
        (visual / name).write_bytes(PNG_MAGIC + bytes(range(16)))
    (visual / TRACE_FILENAME).write_bytes(ZIP_MAGIC + bytes(range(32)))
    return visual


def test_log_sanitizer_redacts_sensitive_values_and_bounds_output() -> None:
    bearer_token = "abcdef...op"
    # Secret-bearing lines are placed AFTER the padding so they survive the
    # 128 KiB tail cap; otherwise the redaction assertions would be vacuous
    # (the lines would simply be cut away). Redact-first must still remove
    # every sensitive value before the byte cap is applied.
    raw = (
        "x" * (MAX_LOG_BYTES + 1000)
        + "GET /mvp/?question=full-resident-question HTTP/1.1\n"
        + "email=user@example.com phone=010-1234-5678\n"
        + f"Authorization: Bearer {bearer_token}\n"
        + '"prompt":"do not upload this"\n'
    )
    safe = sanitize_log_text(raw)
    assert "user@example.com" not in safe
    assert "010-1234-5678" not in safe
    assert bearer_token not in safe
    assert "Bearer [redacted]" in safe
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


# ------------------------------------------------------------------
# #1231-F visual evidence regressions
# ------------------------------------------------------------------


def test_visual_allowlist_is_exact_18_pngs_plus_trace() -> None:
    pngs = [name for name in VISUAL_FILENAMES if name.endswith(".png")]
    assert pngs == EXACT_18_PNGS
    assert len(pngs) == 18
    assert VISUAL_FILENAMES[-1] == TRACE_FILENAME
    assert len(VISUAL_FILENAMES) == 19


def test_visual_evidence_collected_byte_for_byte(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    visual = _make_visual_tree(source)
    output = tmp_path / "output"

    manifest = collect("citizen-browser", source, output)
    assert manifest["missing_visual_sources"] == []
    assert len(manifest["collected"]) == len(VISUAL_FILENAMES)
    for name in VISUAL_FILENAMES:
        assert (output / name).read_bytes() == (visual / name).read_bytes()


def test_unlisted_file_not_collected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    visual = _make_visual_tree(source)
    (visual / "sneaky.png").write_bytes(PNG_MAGIC + b"\x00" * 8)
    output = tmp_path / "output"

    manifest = collect("citizen-browser", source, output)
    assert not (output / "sneaky.png").exists()
    assert manifest["collected"] == sorted(VISUAL_FILENAMES)


def test_360_screenshots_are_not_allowlisted(tmp_path: Path) -> None:
    """Old-harness 360-*.png evidence must never be collected or allowed.

    The canonical #1231-F artifact contract is exact 18 PNG + trace; 360
    keeps functional coverage but produces no evidence screenshots.
    """
    for name in VISUAL_FILENAMES:
        assert not name.startswith("360-")
    source = tmp_path / "source"
    source.mkdir()
    visual = _make_visual_tree(source)
    old_360 = [
        "360-entry.png",
        "360-confirm.png",
        "360-first-action.png",
        "360-search-typing.png",
        "360-result.png",
        "360-view-switch.png",
        "360-reset.png",
    ]
    for name in old_360:
        (visual / name).write_bytes(PNG_MAGIC + b"\x00" * 8)

    output = tmp_path / "output"
    manifest = collect("citizen-browser", source, output)
    for name in old_360:
        assert not (output / name).exists()
    assert manifest["collected"] == sorted(VISUAL_FILENAMES)


def test_screenshot_symlink_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    visual = _make_visual_tree(source)
    (visual / "320-entry.png").unlink()
    target = tmp_path / "target.png"
    target.write_bytes(PNG_MAGIC + b"\x00" * 8)
    (visual / "320-entry.png").symlink_to(target)

    with pytest.raises(ValueError, match="symlink"):
        collect("citizen-browser", source, tmp_path / "output")


def test_trace_symlink_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    visual = _make_visual_tree(source)
    (visual / TRACE_FILENAME).unlink()
    target = tmp_path / "target.zip"
    target.write_bytes(ZIP_MAGIC + b"\x00" * 8)
    (visual / TRACE_FILENAME).symlink_to(target)

    with pytest.raises(ValueError, match="symlink"):
        collect("citizen-browser", source, tmp_path / "output")


def test_evidence_root_symlink_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    real = tmp_path / "real-evidence"
    real.mkdir()
    (source / "400-ai-finder-1116").symlink_to(real, target_is_directory=True)

    with pytest.raises(ValueError, match="evidence root must not be a symlink"):
        collect("citizen-browser", source, tmp_path / "output")


def test_oversized_png_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    visual = _make_visual_tree(source)
    (visual / "1440-desktop.png").write_bytes(
        PNG_MAGIC + b"\x00" * (MAX_PNG_BYTES - len(PNG_MAGIC) + 1)
    )

    with pytest.raises(ValueError, match="exceeds"):
        collect("citizen-browser", source, tmp_path / "output")


def test_oversized_trace_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    visual = _make_visual_tree(source)
    (visual / TRACE_FILENAME).write_bytes(
        ZIP_MAGIC + b"\x00" * (MAX_TRACE_BYTES - len(ZIP_MAGIC) + 1)
    )

    with pytest.raises(ValueError, match="exceeds"):
        collect("citizen-browser", source, tmp_path / "output")


def test_invalid_png_magic_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    visual = _make_visual_tree(source)
    (visual / "320-entry.png").write_bytes(b"NOTAPNG!" + b"\x00" * 8)

    with pytest.raises(ValueError, match="PNG magic"):
        collect("citizen-browser", source, tmp_path / "output")


def test_invalid_zip_signature_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    visual = _make_visual_tree(source)
    (visual / TRACE_FILENAME).write_bytes(b"notazip!!" + b"\x00" * 8)

    with pytest.raises(ValueError, match="ZIP signature"):
        collect("citizen-browser", source, tmp_path / "output")


def test_missing_visual_reported_separately(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "output"

    manifest = collect("citizen-browser", source, output)
    assert manifest["missing_visual_sources"] == sorted(VISUAL_FILENAMES)
    assert manifest["missing_optional_sources"] == [
        "housing-e2e-server.log",
        "mobile-link-safety-server.log",
    ]
    assert manifest["collected"] == []


def test_manifest_includes_visual_limits(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _make_visual_tree(source)

    manifest = collect("citizen-browser", source, tmp_path / "output")
    visual = manifest["visual"]
    assert visual["png_max_bytes"] == MAX_PNG_BYTES
    assert visual["trace_max_bytes"] == MAX_TRACE_BYTES
    assert visual["png_magic_hex"] == PNG_MAGIC.hex()
    assert visual["zip_signature_hex"] == ZIP_MAGIC.hex()
    assert visual["evidence_root"].endswith("400-ai-finder-1116")


def test_visual_not_collected_for_non_visual_jobs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _make_visual_tree(source)
    output = tmp_path / "output"

    manifest = collect("page-agent", source, output)
    assert manifest["missing_visual_sources"] == []
    assert manifest["visual"] is None
    assert manifest["collected"] == []
