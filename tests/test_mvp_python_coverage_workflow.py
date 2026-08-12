from __future__ import annotations

import re
from pathlib import Path

import yaml

from scripts.run_mvp_python_coverage_baseline import (
    COVERAGE_TEST_FILES,
    _percent,
)
from tests.test_mvp_ci_job_decomposition import DOMAIN_JOBS


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "mvp-contracts.yml"
RUNNER = REPO_ROOT / "scripts" / "run_mvp_python_coverage_baseline.py"
REQUIREMENTS_CI_COVERAGE = REPO_ROOT / "requirements-ci-coverage.txt"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
COVERAGE_JOB = "python-coverage-baseline"
COVERAGE_PIN = "coverage==7.15.2"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _workflow_pytest_files() -> set[str]:
    """Union of tests/*.py run by `python -m pytest` in every job EXCEPT the
    coverage job itself (recursion guard)."""
    jobs = _workflow()["jobs"]
    found: set[str] = set()
    for job_id, job in jobs.items():
        if job_id == COVERAGE_JOB:
            continue
        for step in job.get("steps", []):
            run = str(step.get("run", ""))
            if "python -m pytest" not in run:
                continue
            found.update(re.findall(r"tests/[A-Za-z0-9_.-]+\.py", run))
    return found


def test_coverage_test_files_match_workflow_pytest_union() -> None:
    """Drift guard: any new `python -m pytest tests/*.py` step outside the
    coverage job must be mirrored in COVERAGE_TEST_FILES."""
    workflow_files = _workflow_pytest_files()
    runner_files = set(COVERAGE_TEST_FILES)
    assert workflow_files == runner_files
    assert len(COVERAGE_TEST_FILES) == len(set(COVERAGE_TEST_FILES))
    assert len(COVERAGE_TEST_FILES) == 29, (
        f"expected 29 coverage test files, got {len(COVERAGE_TEST_FILES)}"
    )


def test_coverage_test_files_all_exist() -> None:
    for rel in COVERAGE_TEST_FILES:
        assert (REPO_ROOT / rel).is_file(), rel


def test_coverage_dependency_is_exactly_pinned_and_separate() -> None:
    text = REQUIREMENTS_CI_COVERAGE.read_text(encoding="utf-8").strip()
    assert text == COVERAGE_PIN
    # Never mixed into the runtime requirements, and pytest-cov is forbidden.
    assert "coverage" not in REQUIREMENTS.read_text(encoding="utf-8")
    assert "pytest-cov" not in text
    assert "pytest-cov" not in WORKFLOW.read_text(encoding="utf-8")


def test_coverage_job_present_with_python311() -> None:
    jobs = _workflow()["jobs"]
    assert COVERAGE_JOB in jobs
    job = jobs[COVERAGE_JOB]
    assert job["runs-on"] == "ubuntu-latest"
    assert job["timeout-minutes"] == 10
    py_steps = [s for s in job["steps"] if s.get("name") == "Set up Python"]
    assert len(py_steps) == 1
    assert py_steps[0]["with"]["python-version"] == "3.11"
    run = "\n".join(str(s.get("run", "")) for s in job["steps"])
    assert "run_mvp_python_coverage_baseline.py" in run
    assert "requirements-ci-coverage.txt" in run


def test_no_fail_under_or_branch_in_coverage_path() -> None:
    job_run = "\n".join(
        str(s.get("run", ""))
        for s in _workflow()["jobs"][COVERAGE_JOB]["steps"]
    )
    runner_text = RUNNER.read_text(encoding="utf-8")
    assert "--fail-under" not in job_run
    assert "--fail-under" not in runner_text
    assert "--branch" not in job_run
    assert "--branch" not in runner_text


def test_aggregator_requires_coverage_job_and_all_domains() -> None:
    aggregator = _workflow()["jobs"]["mvp-contracts"]
    assert COVERAGE_JOB in aggregator["needs"]
    run = "\n".join(str(s.get("run", "")) for s in aggregator["steps"])
    assert f'${{{{ needs.{COVERAGE_JOB}.result }}}}' in run
    assert "exit 1" in run
    for job_id in sorted(DOMAIN_JOBS):
        assert f'${{{{ needs.{job_id}.result }}}}' in run


def test_runner_measures_only_src_line_coverage() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert "source=[str(SRC_DIR)]" in text
    assert "coverage.Coverage" in text
    assert 'label": "CI-owned Python src line-coverage baseline' in text
    assert '"source": "src"' in text
    assert "show_missing=True" in text
    assert "coverage_version" in text


def test_no_js_or_browser_coverage_claims() -> None:
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    runner_text = RUNNER.read_text(encoding="utf-8")
    for forbidden in ("browser coverage", "js coverage", "javascript coverage"):
        assert forbidden not in workflow_text.lower()
        assert forbidden not in runner_text.lower()


def test_percent_rounding_is_fixed_2_decimals() -> None:
    assert _percent(100, 33) == 33.0
    assert _percent(3, 1) == 33.33
    assert _percent(7, 2) == 28.57
    assert _percent(0, 0) == 100.0
    assert _percent(10, 0) == 0.0
