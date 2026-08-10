from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "mvp-contracts.yml"

DOMAIN_JOBS = {
    "python-contracts",
    "snapshot-provenance",
    "site-adapter",
    "build-packaging",
    "cloudflare-function",
    "citizen-browser",
    "page-agent",
    "comparison-evidence",
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
    "Check whitespace errors",
}


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_domain_jobs_and_compatibility_aggregator_are_present() -> None:
    jobs = _workflow()["jobs"]
    assert set(jobs) == DOMAIN_JOBS | {"mvp-contracts"}

    aggregator = jobs["mvp-contracts"]
    assert set(aggregator["needs"]) == DOMAIN_JOBS
    assert aggregator["if"] == "always()"


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
