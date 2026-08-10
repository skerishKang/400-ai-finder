from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "mvp-contracts.yml"
REQUIREMENTS = REPO_ROOT / "requirements.txt"

SECURITY_JOB = "security-quality"
LEGACY_DOMAIN_JOBS = {
    "python-contracts",
    "snapshot-provenance",
    "site-adapter",
    "build-packaging",
    "cloudflare-function",
    "citizen-browser",
    "page-agent",
    "comparison-evidence",
}
ARTIFACT_PATHS = {
    "citizen-browser": "/tmp/mvp-failure-artifacts-citizen-browser",
    "page-agent": "/tmp/mvp-failure-artifacts-page-agent",
    "comparison-evidence": "/tmp/mvp-failure-artifacts-comparison-evidence",
}
GITLEAKS_ACTION = "gitleaks/gitleaks-action@v3.0.0"
RUFF_VERSION = "0.16.2"
PIP_AUDIT_VERSION = "2.10.1"

BLOCKED_SECRET_ENVS = {
    "GEMINI_API_KEY",
    "KILOCODE_API_KEY",
    "FIRECRAWL_API_KEY",
}
BLOCKED_ASSIGNMENTS = (
    re.compile(r"(?im)(?:^|[;&]\s*|\bexport\s+)MVP_AI_MODE\s*=\s*['\"]?enabled\b"),
    re.compile(
        r"(?im)(?:^|[;&]\s*|\bexport\s+)AI_FINDER_FETCH_PROVIDER\s*=\s*"
        r"['\"]?(?:requests|firecrawl)\b"
    ),
    re.compile(
        r"(?im)(?:^|[;&]\s*|\bexport\s+)"
        r"(?:GEMINI_API_KEY|KILOCODE_API_KEY|FIRECRAWL_API_KEY)\s*="
    ),
)
URL_RE = re.compile(r"https?://[^\s'\"`\\]+")


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _steps(job: dict) -> list[dict]:
    return list(job.get("steps", []))


def _named_step(job: dict, name: str) -> dict:
    matches = [step for step in _steps(job) if step.get("name") == name]
    assert len(matches) == 1, name
    return matches[0]


def _all_env(job: dict) -> list[dict]:
    envs = []
    if isinstance(job.get("env"), dict):
        envs.append(job["env"])
    for step in _steps(job):
        if isinstance(step.get("env"), dict):
            envs.append(step["env"])
    return envs


def _run_text(job: dict) -> str:
    return "\n".join(str(step.get("run", "")) for step in _steps(job))


def test_security_quality_job_is_independent_and_required_by_aggregator() -> None:
    jobs = _workflow()["jobs"]
    assert LEGACY_DOMAIN_JOBS <= set(jobs)
    assert SECURITY_JOB in jobs

    aggregator = jobs["mvp-contracts"]
    assert SECURITY_JOB in aggregator["needs"]
    run = _run_text(aggregator)
    assert '${{ needs.security-quality.result }}' in run
    assert 'test "${{ needs.security-quality.result }}" = "success" || exit 1' in run


def test_ruff_correctness_gate_is_narrow_and_pinned() -> None:
    job = _workflow()["jobs"][SECURITY_JOB]
    install = _named_step(job, "Install security CI tooling")["run"]
    ruff = _named_step(job, "Run Ruff correctness gate")["run"]

    assert f'"ruff=={RUFF_VERSION}"' in install
    assert ruff.strip() == "ruff check --select E9,F63,F7,F82 --output-format=github ."
    assert "--fix" not in ruff
    assert "ruff format" not in ruff


def test_gitleaks_is_official_pinned_and_full_history() -> None:
    job = _workflow()["jobs"][SECURITY_JOB]
    checkout = next(step for step in _steps(job) if step.get("uses") == "actions/checkout@v4")
    scan = _named_step(job, "Scan repository secrets with Gitleaks")

    assert checkout["with"]["fetch-depth"] == 0
    assert scan["uses"] == GITLEAKS_ACTION
    assert scan["env"]["GITLEAKS_ENABLE_COMMENTS"] == "false"
    assert scan["env"]["GITLEAKS_ENABLE_UPLOAD_ARTIFACT"] == "false"
    assert "GITHUB_TOKEN" in scan["env"]


def test_pip_audit_is_pinned_and_non_mutating() -> None:
    job = _workflow()["jobs"][SECURITY_JOB]
    install = _named_step(job, "Install security CI tooling")["run"]
    audit = _named_step(job, "Audit locked Python dependencies")["run"]

    assert f'"pip-audit=={PIP_AUDIT_VERSION}"' in install
    assert audit.strip() == (
        "python -m pip_audit --strict --no-deps --disable-pip -r requirements.txt"
    )
    assert "--fix" not in audit
    assert "--ignore-vuln" not in audit


def test_npm_audit_is_lockfile_based_fail_closed_and_non_mutating() -> None:
    job = _workflow()["jobs"][SECURITY_JOB]
    install = _named_step(job, "Install Node dependencies without lifecycle scripts")["run"]
    audit = _named_step(job, "Audit locked Node dependencies")["run"]

    assert install.strip() == "npm ci --ignore-scripts"
    assert audit.strip() == "npm audit --audit-level=low"
    assert "npm audit fix" not in _run_text(job)


def test_security_steps_do_not_bypass_failures() -> None:
    job = _workflow()["jobs"][SECURITY_JOB]
    for step in _steps(job):
        assert step.get("continue-on-error") not in (True, "true", "True")
        run = str(step.get("run", ""))
        assert "|| true" not in run


def test_security_tooling_is_not_added_to_runtime_requirements() -> None:
    requirements = REQUIREMENTS.read_text(encoding="utf-8").lower()
    assert "ruff==" not in requirements
    assert "pip-audit==" not in requirements


def test_blocked_credential_vocabulary_uses_canonical_kilocode_key() -> None:
    assert "KILOCODE_API_KEY" in BLOCKED_SECRET_ENVS
    assert "HY3_API_KEY" not in BLOCKED_SECRET_ENVS

    secret_assignment = BLOCKED_ASSIGNMENTS[-1]
    assert secret_assignment.search("KILOCODE_API_KEY=dummy_value")
    assert secret_assignment.search("export KILOCODE_API_KEY=dummy_value")
    assert secret_assignment.search("HY3_API_KEY=dummy_value") is None


def test_routine_ci_does_not_enable_external_provider_or_live_fetch_modes() -> None:
    jobs = _workflow()["jobs"]
    for job_id in LEGACY_DOMAIN_JOBS:
        job = jobs[job_id]
        for env in _all_env(job):
            assert BLOCKED_SECRET_ENVS.isdisjoint(env), job_id
            if "MVP_AI_MODE" in env:
                assert str(env["MVP_AI_MODE"]).strip().lower() != "enabled", job_id
            if "AI_FINDER_FETCH_PROVIDER" in env:
                assert str(env["AI_FINDER_FETCH_PROVIDER"]).strip().lower() not in {
                    "requests",
                    "firecrawl",
                }, job_id

        run = _run_text(job)
        for pattern in BLOCKED_ASSIGNMENTS:
            assert pattern.search(run) is None, job_id


def test_routine_ci_shell_network_targets_are_loopback_only() -> None:
    jobs = _workflow()["jobs"]
    observed_loopback = set()

    for job_id in LEGACY_DOMAIN_JOBS:
        for raw_url in URL_RE.findall(_run_text(jobs[job_id])):
            host = urlsplit(raw_url.rstrip(".,);]")).hostname
            assert host in {"127.0.0.1", "localhost"}, (job_id, raw_url)
            observed_loopback.add(host)

    assert "127.0.0.1" in observed_loopback


def test_security_job_runs_offline_guard_and_existing_artifact_contract_is_preserved() -> None:
    jobs = _workflow()["jobs"]
    security_tests = _named_step(jobs[SECURITY_JOB], "Run security-quality contract tests")["run"]
    assert "tests/test_mvp_security_quality_workflow.py" in security_tests
    assert "tests/test_mvp_ci_job_decomposition.py" in security_tests

    for job_id, expected_path in ARTIFACT_PATHS.items():
        job = jobs[job_id]
        prepare = _named_step(job, "Prepare privacy-safe failure artifacts")
        upload = _named_step(job, "Upload bounded failure artifacts")
        assert prepare["if"] == "failure()"
        assert upload["if"] == "failure()"
        assert upload["uses"] == "actions/upload-artifact@v7.0.1"
        assert upload["with"]["retention-days"] == 5
        assert upload["with"]["if-no-files-found"] == "warn"
        assert upload["with"]["path"] == expected_path
