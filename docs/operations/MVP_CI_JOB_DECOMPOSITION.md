# MVP CI Job Decomposition

Status: #1231-A implementation contract.

Canonical clone-fidelity invariant: `docs/product/exact-official-site-clone-invariant.md`.

## Purpose

`MVP Contract Checks` historically ran the entire offline MVP validation matrix in one serial `mvp-contracts` job. The suite is intentionally broad, but a failure in an early browser contract can skip unrelated later contracts and the serial wall-clock obscures which subsystem is responsible.

This slice changes CI orchestration only. It does **not** weaken assertions, remove tests, add skips/xfails, change browser thresholds, or replace deterministic/offline fixtures with live network calls. The exact official-site clone-fidelity invariant remains authoritative and unchanged.

## Historical baseline

Pre-split PR run `31354508444` / job `93351556015` executed from approximately `2026-08-10T04:07:14Z` to `2026-08-10T04:19:46Z`, about **12m32s wall-clock** for the single serial job. This timing is historical evidence only, not a promised post-split target.

## Parallel domains

The workflow keeps the top-level name `MVP Contract Checks` and splits the existing commands into eight independent fail-closed jobs:

| Job | Existing contract ownership |
|---|---|
| `python-contracts` | core MVP pytest, legacy requests, crawler fallback |
| `snapshot-provenance` | official snapshot/fidelity matrix, golden docs |
| `site-adapter` | canonical site adapter matrix |
| `build-packaging` | Cloudflare Pages static build contracts, CI decomposition self-contract, whitespace gate |
| `cloudflare-function` | offline Cloudflare MVP Function contracts |
| `citizen-browser` | shell runtime and resident-facing browser contracts |
| `page-agent` | Page Agent lab/runtime/resident contracts |
| `comparison-evidence` | Page Agent comparison/evidence/Stage 3 harness |

A final `mvp-contracts` compatibility aggregator depends on all eight jobs and fails unless every dependency is `success`. This preserves the established `MVP Contract Checks / mvp-contracts` check identity for branch-protection consumers while allowing the expensive domains to execute concurrently.

## Coverage invariant

`tests/test_mvp_ci_job_decomposition.py` is executed by `build-packaging` and verifies:

1. all eight domain jobs plus the compatibility aggregator exist;
2. the aggregator depends on every domain job and runs with `always()`;
3. every pre-split named test/evidence/whitespace step remains present exactly once across the domain jobs;
4. the aggregator explicitly checks every dependency result and exits non-zero on any failure.

This is an orchestration guard. Product tests remain authoritative for product behavior.

## Network boundary

The decomposition preserves the existing offline/mock/fixture behavior. Local `127.0.0.1` HTTP servers used by browser E2E remain local test infrastructure. This slice does not add provider, Firecrawl, production, or official-site network validation.

## Follow-up

#1231-B remains separate: dependency reproducibility/locking should be handled independently so a lockfile or action-version change is not mixed into the job-topology change.
