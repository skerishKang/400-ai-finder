from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "mvp-contracts.yml"
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
