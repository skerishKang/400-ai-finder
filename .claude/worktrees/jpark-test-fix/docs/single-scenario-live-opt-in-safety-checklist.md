# Single-Scenario Live Opt-In Safety Checklist

Stage 67 defines the safety checklist required before adding any real provider/fetch execution to the single-scenario live smoke path. Stage 69 adds a deterministic fake adapter boundary that keeps the path offline while making the future adapter seam explicit.

This document is **documentation-only**. It does not enable live provider calls, fetch calls, network calls, Firecrawl calls, or app pipeline execution. Stage 65 remains a deterministic offline/dummy dry runner, and Stage 69 keeps payload construction behind a fake adapter only.

## 1. Current boundary

Current implemented boundary:

```text
scripts/run_single_live_smoke_dry.py
  -> one scenario id only
  -> scripts/single_live_smoke_fake_adapter.py
  -> deterministic offline dummy payload
  -> Stage 62-compatible result payload
  -> Stage 60 writer
  -> one-result live smoke artifact
  -> Stage 58 export helper
  -> single-scenario judge slice
```

Current fake adapter boundary:

| File | Role |
|---|---|
| `scripts/single_live_smoke_fake_adapter.py` | Deterministic offline adapter that builds one Stage 62-compatible payload. |
| `scripts/run_single_live_smoke_dry.py` | CLI/dry-run wrapper that selects exactly one scenario and delegates payload construction to the fake adapter. |
| `tests/test_single_live_smoke_fake_adapter.py` | Contract tests for fake adapter labels, answered payloads, and fallback payloads. |
| `tests/test_single_live_smoke_dry.py` | End-to-end dry-run tests for selector guards, artifact writing, export, and judge slice compatibility. |

Current non-goals:

- no real provider calls
- no real fetch calls
- no external network calls
- no Firecrawl calls
- no app pipeline execution
- no all-scenario live execution
- no backend, UI, or API changes

A future stage may add real single-scenario provider/fetch execution only after the checklist below is satisfied. That future stage must not replace the fake adapter silently; it must add an explicit opt-in path and keep the fake path available for offline tests.

## 2. Required preconditions before real provider/fetch calls

A future real single-scenario live stage must satisfy all of the following before any network-capable code path is merged.

| Area | Required condition |
|---|---|
| Explicit opt-in | Real execution must require `AI_FINDER_LIVE_EVAL=true`. |
| Single scenario only | The command must require exactly one `--scenario-id`. Broad selectors such as `all`, `*`, empty string, or omitted id must fail before any provider/fetch setup. |
| Fake adapter separation | The offline fake adapter must remain deterministic and clearly named. Real adapters must be separate from `scripts/single_live_smoke_fake_adapter.py`. |
| Provider config | Provider configuration may be checked as `set`/`missing`, but values must not be printed. |
| Fetch config | Fetch provider configuration may be checked as `set`/`missing`, but values must not be printed. |
| Secret redaction | API keys, cookies, headers, raw prompts, and raw provider payloads must not be logged or persisted. |
| Domain boundary | Any normalized source URL must be public and must match the selected scenario's expected domain when the scenario requires a source. |
| Artifact writer | Results must be written through the Stage 60 writer boundary. |
| Artifact review | The produced artifact must be reviewable before any all-scenario live execution is considered. |
| Rate limit | The first real path must be one request path only. No parallel execution. No loop over all 14 scenarios. |
| Rollback | The future PR must be reversible without changing offline smoke eval behavior. |

## 3. Safety gates for the future CLI

A future real command should fail early in this order:

1. reject missing or broad `--scenario-id`,
2. load and validate the matrix,
3. confirm exactly one scenario match,
4. confirm explicit live opt-in,
5. report provider/fetch config only as `set` or `missing`,
6. reject missing required provider/fetch config,
7. perform exactly one provider/fetch execution path,
8. normalize the result into the Stage 62-compatible payload shape,
9. write the artifact through Stage 60 writer,
10. export through Stage 58 helper for review.

The first real implementation must not introduce a loop over all matrix scenarios. It must also keep the fake adapter path usable for deterministic offline regression tests.

## 4. Redaction rules

The future real path must not print or persist:

- API keys or tokens
- cookies or session identifiers
- request headers
- raw provider request payloads
- raw provider response payloads
- raw prompts or hidden prompts
- private endpoints
- signed URLs
- full raw HTML documents
- user-specific private data

Allowed persisted fields are limited to:

- scenario id
- site id
- scenario query text
- normalized answer
- normalized public source title and URL
- short public snippet if already safe
- coarse timing metrics
- redaction-safe error type
- generic redaction-safe error message

## 5. Required artifact review before expanding scope

Before adding any multi-scenario live execution, maintainers should inspect a single real artifact and confirm:

1. `_meta.artifact_type` is `live_smoke_eval_results`.
2. `_meta.scenario_count` is `1` for the first real single-scenario path.
3. `run.live_opt_in` is `true` only when explicit opt-in was provided.
4. `provider_name` and `fetch_provider_name` are safe labels, not secrets.
5. every redaction flag remains `false`.
6. the result has exactly one `scenario_id`.
7. the `scenario_id` exists in the matrix.
8. all source URLs are public and domain-compatible.
9. no raw keys, cookies, headers, prompts, or provider payloads appear in the artifact.
10. the artifact exports through Stage 58 helper.
11. the exported result can be evaluated against the matching single-scenario slice.
12. the fake adapter tests still pass after adding any real adapter path.

## 6. Recommended validation commands

Current Stage 70 documentation-only baseline:

```bash
git diff --check
pytest tests/test_single_live_smoke_fake_adapter.py
pytest tests/test_single_live_smoke_dry.py
pytest tests/test_live_runner_result_payload_contract.py
pytest tests/test_live_smoke_artifact_writer.py
pytest tests/test_live_smoke_artifact_export.py
pytest tests/test_smoke_eval_runner.py
```

Current dry-run command:

```bash
python scripts/run_single_live_smoke_dry.py \
  --scenario-id bukgu-01 \
  --output /tmp/single_live_dry_artifact.json \
  --created-at 2026-05-30T15:00:00Z
```

Artifact export command:

```bash
python scripts/export_live_smoke_artifact.py \
  /tmp/single_live_dry_artifact.json \
  --output /tmp/single_live_pipeline_result.json
```

Preflight command:

```bash
python scripts/run_smoke_eval.py --live-preflight
```

The preflight report must show only `set`/`missing` status and must not print actual configuration values.

## 7. Next safe stage candidates

Recommended next stages, in order:

1. Add a document-only real adapter design note that references the fake adapter seam.
2. Add a real single-scenario provider/fetch interface skeleton that still defaults to fake adapters.
3. Add one real provider/fetch call behind explicit opt-in and one scenario id.
4. Review one real artifact manually.
5. Only after that, design sequential and rate-limited multi-scenario execution.

Do not jump directly from the Stage 65/69 dry runner and fake adapter boundary to full 14-scenario live execution.
