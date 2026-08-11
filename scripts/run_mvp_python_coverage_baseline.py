from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

# NOTE: `coverage` is imported lazily inside run_baseline(). The drift
# contract test (tests/test_mvp_python_coverage_workflow.py) imports this
# module from build-packaging, which does NOT install the CI-only coverage
# dependency; a module-level import would break that collection.


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"

# CI-owned Python src line-coverage baseline (first slice, #1231-G).
#
# COVERAGE_TEST_FILES is the set union of every tests/*.py file that the
# existing "MVP Contract Checks" workflow runs via `python -m pytest`
# (coverage job itself excluded). tests/test_mvp_python_coverage_workflow.py
# is the drift contract that keeps this list in sync with the workflow.
COVERAGE_TEST_FILES = (
    "tests/test_mvp_failure_codes.py",
    "tests/test_mobile_demo.py",
    "tests/test_citizen_first_use_shell.py",
    "tests/test_citizen_sitespec_parity.py",
    "tests/test_citizen_action_demo_chat_shell_contract.py",
    "tests/test_citizen_action_demo_canvas.py",
    "tests/test_shared_runtime_vocabulary_contract.py",
    "tests/test_legacy_requests_transport.py",
    "tests/test_url_crawler.py",
    "tests/test_homepage_mapper.py",
    "tests/test_bukgu_official_apartment_snapshot.py",
    "tests/test_bukgu_official_content_snapshots.py",
    "tests/test_renderer_route_manifest_fidelity.py",
    "tests/test_capture_required_entry_spec.py",
    "tests/test_exact_official_site_clone_invariant.py",
    "tests/test_bukgu_quest_schema.py",
    "tests/test_bukgu_quest_to_action_plan.py",
    "tests/test_mvp_golden_quest_fidelity_matrix.py",
    "tests/test_bukgu_golden_docs_contract.py",
    "tests/test_site_adapter_contract_matrix.py",
    "tests/test_build_cloudflare_pages.py",
    "tests/test_mvp_ci_job_decomposition.py",
    "tests/test_page_agent_lab.py",
    "tests/test_page_agent_comparison_contract.py",
    "tests/test_page_agent_comparison_evidence.py",
    "tests/test_mvp_security_quality_workflow.py",
    "tests/test_mvp_failure_artifact_workflow.py",
    "tests/test_mvp_python_coverage_workflow.py",
)


def _percent(statements: int, covered: int) -> float:
    """Fixed rounding rule: 2 decimal places, empty module treated as 100.0."""
    if statements <= 0:
        return 100.0
    return round(100.0 * covered / statements, 2)


def run_baseline(output: str) -> dict[str, object]:
    # CI-only dependency (requirements-ci-coverage.txt); imported here so the
    # drift contract test module can be collected without it.
    import coverage
    import pytest

    tmp_dir = Path(tempfile.gettempdir())
    data_file = str(tmp_dir / "mvp-coverage-baseline.coverage")
    raw_json = tmp_dir / "mvp-coverage-baseline-raw.json"

    # 1) erase existing coverage state
    cov = coverage.Coverage(source=[str(SRC_DIR)], data_file=data_file)
    cov.erase()

    # 2) start
    cov.start()
    # pytest runs IN-PROCESS so the coverage tracer observes every src line
    # (a subprocess would be invisible to the parent's tracer).
    try:
        result_code = pytest.main(["-q", *COVERAGE_TEST_FILES])
    finally:
        # 3) stop/save (always, even on pytest failure/exception)
        cov.stop()
        cov.save()

    # 4) pytest failure propagates its non-zero exit unchanged
    if result_code != 0:
        print(
            f"pytest failed with exit code {result_code}; "
            "coverage baseline aborted (no summary written)",
            file=sys.stderr,
        )
        raise SystemExit(result_code)

    # 5) per-module report with missing lines on stdout
    cov.report(show_missing=True)

    # 6) raw JSON (from coverage.py) -> deterministic baseline summary
    cov.json_report(outfile=str(raw_json))
    raw = json.loads(raw_json.read_text(encoding="utf-8"))
    raw_json.unlink(missing_ok=True)

    files: list[dict[str, object]] = []
    for path, info in raw.get("files", {}).items():
        summary = info.get("summary", {})
        statements = int(summary.get("num_statements", 0))
        covered = int(summary.get("covered_lines", 0))
        missing = int(summary.get("missing_lines", 0))
        files.append(
            {
                "path": os.path.relpath(path, REPO_ROOT).replace(os.sep, "/"),
                "statements": statements,
                "covered": covered,
                "missing": missing,
                "percent": _percent(statements, covered),
            }
        )
    files.sort(key=lambda entry: str(entry["path"]))

    totals_raw = raw.get("totals", {})
    total_statements = int(totals_raw.get("num_statements", 0))
    total_covered = int(totals_raw.get("covered_lines", 0))
    total_missing = int(totals_raw.get("missing_lines", 0))

    summary: dict[str, object] = {
        "schema_version": "1.0.0",
        "label": "CI-owned Python src line-coverage baseline",
        "source": "src",
        "coverage_version": coverage.__version__,
        "test_files": sorted(COVERAGE_TEST_FILES),
        "totals": {
            "statements": total_statements,
            "covered": total_covered,
            "missing": total_missing,
            "percent": _percent(total_statements, total_covered),
        },
        "files": files,
    }

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"\nbaseline JSON: {out_path}")
    print(
        f"totals: statements={total_statements} covered={total_covered} "
        f"missing={total_missing} percent="
        f"{_percent(total_statements, total_covered)}"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the CI-owned Python src line-coverage baseline"
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run_baseline(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
