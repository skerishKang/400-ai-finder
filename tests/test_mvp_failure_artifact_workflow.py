from __future__ import annotations

import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "mvp-contracts.yml"
HARNESS = REPO_ROOT / "tests" / "browser" / "verify_first_use_responsive.mjs"
COLLECTOR = REPO_ROOT / "scripts" / "collect_mvp_failure_artifacts.py"
ARTIFACT_JOBS = {"citizen-browser", "page-agent", "comparison-evidence"}
ACTION = "actions/upload-artifact@v7.0.1"


def test_browser_jobs_have_failure_only_bounded_artifact_uploads() -> None:
    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    for job_id in ARTIFACT_JOBS:
        steps = jobs[job_id]["steps"]
        collect = [step for step in steps if step.get("name") == "Prepare privacy-safe failure artifacts"]
        upload = [step for step in steps if step.get("name") == "Upload bounded failure artifacts"]
        assert len(collect) == 1, job_id
        assert len(upload) == 1, job_id
        assert collect[0]["if"] == "failure()"
        assert upload[0]["if"] == "failure()"
        assert "collect_mvp_failure_artifacts.py" in collect[0]["run"]
        assert upload[0]["uses"] == ACTION
        assert upload[0]["with"]["retention-days"] == 5
        assert upload[0]["with"]["if-no-files-found"] == "warn"
        path = upload[0]["with"]["path"]
        assert path.startswith("/tmp/mvp-failure-artifacts-")
        assert "**" not in path and "." not in Path(path).name


def test_artifact_steps_never_upload_repository_or_environment_paths() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    forbidden = (
        "path: .\n",
        "path: ./\n",
        "path: ${{ github.workspace }}",
        "path: /tmp/\n",
        "env >",
        "printenv",
        "set >",
    )
    for token in forbidden:
        assert token not in text


def test_workflow_artifact_action_and_retention_unchanged() -> None:
    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    for job_id in ARTIFACT_JOBS:
        steps = jobs[job_id]["steps"]
        upload = [step for step in steps if step.get("name") == "Upload bounded failure artifacts"]
        assert upload[0]["uses"] == "actions/upload-artifact@v7.0.1"
        assert upload[0]["with"]["retention-days"] == 5
        assert upload[0]["if"] == "failure()"


# ------------------------------------------------------------------
# #1231-F harness trace / evidence allowlist contracts
# ------------------------------------------------------------------


def test_harness_records_only_stage_b_trace_with_sources_off() -> None:
    text = HARNESS.read_text(encoding="utf-8")
    assert "surfCtx.tracing.start({" in text
    # In-trace screenshots are off so the trace stays inside the 32 MiB cap;
    # the deterministic 18 PNGs provide the visual evidence instead.
    assert "screenshots: false" in text
    assert "snapshots: true" in text
    assert "sources: false" in text
    assert "surfCtx.tracing.stop({ path: TRACE_PATH })" in text
    # Broad tracing is forbidden everywhere.
    assert "browser.tracing" not in text
    assert "context.tracing" not in text


def test_harness_producer_validation_and_guard_present() -> None:
    text = HARNESS.read_text(encoding="utf-8")
    assert "MAX_PNG_BYTES" in text
    assert "MAX_TRACE_BYTES" in text
    assert "PNG_MAGIC" in text
    assert "ZIP_MAGIC" in text
    assert "prepareEvidenceDir" in text
    assert "assertRegularBoundedFile" in text


def test_harness_evidence_allowlist_matches_collector() -> None:
    harness = HARNESS.read_text(encoding="utf-8")
    collector = COLLECTOR.read_text(encoding="utf-8")

    harness_block = re.search(
        r"EVIDENCE_FILENAMES = Object\.freeze\(\[(.*?)\]\)", harness, re.S
    ).group(1)
    harness_names = re.findall(r'"([a-z0-9_.-]+)"', harness_block)

    collector_block = re.search(
        r"VISUAL_FILENAMES = \((.*?)\)", collector, re.S
    ).group(1)
    collector_names = re.findall(r'"([a-z0-9_.-]+)"', collector_block)
    # The collector references the trace by its TRACE_FILENAME constant;
    # resolve that constant to build the full 19-entry allowlist.
    trace_const = re.search(
        r'TRACE_FILENAME = "([a-z0-9_.-]+)"', collector
    ).group(1)
    assert trace_const == "responsive-trace.zip"
    full_collector = collector_names + [trace_const]

    # The harness keeps the trace as a separate constant, so the full
    # 19-entry allowlist is EVIDENCE_FILENAMES + TRACE_FILENAME.
    assert harness_names == full_collector[:-1]
    assert full_collector[-1] == "responsive-trace.zip"
    assert len(harness_names) == 18
    assert len(full_collector) == 19
    assert harness_names.count("responsive-trace.zip") == 0
    assert sum(name.endswith(".png") for name in harness_names) == 18


def test_harness_trace_path_inside_evidence_root() -> None:
    text = HARNESS.read_text(encoding="utf-8")
    assert 'const TRACE_PATH = path.join(SCREENSHOT_DIR, TRACE_FILENAME);' in text
    assert 'const TRACE_FILENAME = "responsive-trace.zip";' in text


def test_harness_excludes_360_from_evidence_screenshots() -> None:
    """360 keeps full functional coverage but produces no evidence PNGs."""
    text = HARNESS.read_text(encoding="utf-8")
    assert "const captureEvidence = vp.width === 320 || vp.width === 390;" in text
    assert text.count("if (captureEvidence)") == 7
    for name in (
        "360-entry.png",
        "360-confirm.png",
        "360-first-action.png",
        "360-search-typing.png",
        "360-result.png",
        "360-view-switch.png",
        "360-reset.png",
    ):
        assert name not in text


def test_harness_enforces_exact_evidence_root_membership() -> None:
    """The evidence root must contain exactly the 19 allowlisted entries."""
    text = HARNESS.read_text(encoding="utf-8")
    assert "stageB evidence membership" in text
    assert "readdirSync(SCREENSHOT_DIR)" in text
    assert "[...EVIDENCE_FILENAMES, TRACE_FILENAME]" in text
