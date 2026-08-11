from __future__ import annotations

import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "mvp-contracts.yml"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
PACKAGE_JSON = REPO_ROOT / "package.json"
PACKAGE_LOCK = REPO_ROOT / "package-lock.json"

DOMAIN_JOBS = {
    "python-contracts",
    "snapshot-provenance",
    "site-adapter",
    "build-packaging",
    "cloudflare-function",
    "citizen-browser",
    "page-agent",
    "comparison-evidence",
    "security-quality",
    "python-coverage-baseline",
}

EXPECTED_TIMEOUT_MINUTES = {
    "python-contracts": 8,
    "snapshot-provenance": 6,
    "site-adapter": 6,
    "build-packaging": 6,
    "cloudflare-function": 8,
    "citizen-browser": 15,
    "page-agent": 12,
    "comparison-evidence": 10,
    "security-quality": 10,
    "python-coverage-baseline": 10,
    "mvp-contracts": 5,
}

EXPECTED_TEST_STEPS = {
    "Run MVP contract pytest suite",
    "Run canonical official snapshot contracts",
    "Run Buk-gu golden docs contract (#1188)",
    "Run site adapter contract matrix (#1221)",
    "Run legacy requests transport contract tests",
    "Run legacy crawler fallback contract suites",
    "Run static Pages build contract tests",
    "Run MVP shell runtime harness",
    "Run home fixture canvas browser contract (#1170)",
    "Run responsive browser contract",
    "Run entry chat space browser contract (#1190)",
    "Run decorative AI labels a11y browser contract (#1175)",
    "Run mobile multistep composer browser contract (#1174)",
    "Run desktop chat scroll containment browser contract (#1173)",
    "Run mobile link safety browser contract (live build, port 8769)",
    "Run housing department browser contract",
    "Run two-stage bilingual draft browser contract",
    "Run Cloudflare MVP Function contract test",
    "Run Page Agent lab Python contracts (full suite)",
    "Run Page Agent lab runtime verification",
    "Run Page Agent lab browser E2E",
    "Run Page Agent comparison contract tests (full suite)",
    "Run Page Agent comparison evidence contract tests",
    "Verify expectations fixture integrity",
    "Run resident demo browser E2E",
    "Run mobile resident cancellation browser contract (#1183)",
    "Run resident mock model contract (unit-level)",
    "Run Page Agent production-gap browser contract",
    "Run Stage 3 browser comparison harness (static build, port 8765, 1 rep)",
    "Verify Stage 3 evidence schema on CI-generated evidence (10 runs)",
    "Run CI job decomposition self-contract (#1231)",
    "Run Python coverage baseline self-contract (#1231-G)",
    "Check whitespace errors",
}

EXPECTED_PYTHON_LOCK = {
    "requests": "2.34.2",
    "beautifulsoup4": "4.15.0",
    "pytest": "9.1.1",
    "pyyaml": "6.0.3",
    "pillow": "12.3.0",
    "certifi": "2026.7.22",
    "charset-normalizer": "3.4.9",
    "idna": "3.18",
    "urllib3": "2.7.0",
    "soupsieve": "2.9.2",
    "typing-extensions": "4.16.0",
    "iniconfig": "2.3.0",
    "packaging": "26.3",
    "pluggy": "1.6.0",
    "pygments": "2.20.0",
}


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _locked_python_requirements() -> dict[str, str]:
    locked: dict[str, str] = {}
    for raw_line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        assert "==" in line, f"CI requirement is not exactly pinned: {line}"
        name, version = line.split("==", 1)
        assert name and version and not any(op in version for op in (">", "<", "~", "*"))
        locked[name.lower()] = version
    return locked


def test_domain_jobs_and_compatibility_aggregator_are_present() -> None:
    jobs = _workflow()["jobs"]
    assert set(jobs) == DOMAIN_JOBS | {"mvp-contracts"}

    aggregator = jobs["mvp-contracts"]
    assert set(aggregator["needs"]) == DOMAIN_JOBS
    assert aggregator["if"] == "always()"


def test_job_timeouts_match_empirical_closeout_contract() -> None:
    jobs = _workflow()["jobs"]
    assert set(EXPECTED_TIMEOUT_MINUTES) == DOMAIN_JOBS | {"mvp-contracts"}

    actual: dict[str, int] = {}
    for job_id, expected_timeout in EXPECTED_TIMEOUT_MINUTES.items():
        timeout = jobs[job_id].get("timeout-minutes")
        assert isinstance(timeout, int) and not isinstance(timeout, bool), (
            f"{job_id} timeout must be an explicit integer"
        )
        assert timeout > 0, f"{job_id} timeout must be positive"
        actual[job_id] = timeout
        assert timeout == expected_timeout, (
            f"{job_id} timeout {timeout} != expected {expected_timeout}"
        )

    assert actual == EXPECTED_TIMEOUT_MINUTES


def test_legacy_test_steps_are_preserved_exactly_once() -> None:
    jobs = _workflow()["jobs"]
    seen: dict[str, list[str]] = {}

    for job_id, job in jobs.items():
        for step in job.get("steps", []):
            name = step.get("name")
            if name in EXPECTED_TEST_STEPS:
                seen.setdefault(name, []).append(job_id)

    assert set(seen) == EXPECTED_TEST_STEPS
    duplicates = {name: owners for name, owners in seen.items() if len(owners) != 1}
    assert duplicates == {}


def test_aggregator_fails_closed_on_any_domain_failure() -> None:
    aggregator = _workflow()["jobs"]["mvp-contracts"]
    run = "\n".join(
        str(step.get("run", "")) for step in aggregator.get("steps", [])
    )
    for job_id in sorted(DOMAIN_JOBS):
        needle = f'${{{{ needs.{job_id}.result }}}}'
        assert needle in run
    assert "exit 1" in run


def test_python_ci_dependency_graph_is_exactly_locked() -> None:
    assert _locked_python_requirements() == EXPECTED_PYTHON_LOCK


def test_node_playwright_dependency_is_exactly_locked_and_ci_uses_npm_ci() -> None:
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))

    assert package["dependencies"]["playwright"] == "1.61.1"
    assert lock["packages"][""]["dependencies"]["playwright"] == "1.61.1"
    assert lock["packages"]["node_modules/playwright"]["version"] == "1.61.1"
    assert lock["packages"]["node_modules/playwright-core"]["version"] == "1.61.1"

    node_jobs = {"cloudflare-function", "citizen-browser", "page-agent", "comparison-evidence"}
    jobs = _workflow()["jobs"]
    for job_id in node_jobs:
        commands = "\n".join(str(step.get("run", "")) for step in jobs[job_id].get("steps", []))
        assert "npm ci --ignore-scripts" in commands, f"{job_id} must install from package-lock"
        assert "npm install " not in commands
