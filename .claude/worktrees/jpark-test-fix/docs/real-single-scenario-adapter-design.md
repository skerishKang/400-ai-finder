# Real Single-Scenario Adapter Design Note

Stage 71 defines the design boundary for a future real single-scenario adapter path. This is a documentation-only note. It does not enable provider calls, fetch calls, network calls, Firecrawl calls, or app pipeline execution.

The current implementation remains the Stage 69 fake adapter path:

```text
scripts/run_single_live_smoke_dry.py
  -> select exactly one scenario id
  -> scripts/single_live_smoke_fake_adapter.py
  -> deterministic offline Stage 62-compatible payload
  -> Stage 60 writer
  -> one-result artifact
  -> Stage 58 export helper
  -> single-scenario judge slice
```

## 1. Design goal

The future real adapter path should reuse the same seam introduced by the fake adapter, but it must be opt-in, one-scenario-only, and reviewable before any broader execution is added.

The intended future boundary is:

```text
explicit opt-in + one scenario id
  -> scenario lookup and guard validation
  -> real adapter interface
  -> normalized Stage 62-compatible payload
  -> Stage 60 writer
  -> one-result artifact
  -> Stage 58 export helper
  -> single-scenario judge slice
```

The future real adapter must not bypass the Stage 60 writer or write a separate artifact shape.

## 2. Adapter categories

| Adapter category | Current status | Purpose |
|---|---|---|
| Fake adapter | Implemented in `scripts/single_live_smoke_fake_adapter.py` | Deterministic offline regression path. |
| Fake-compatible interface | Design-only | Shape expected from future adapters. |
| Real adapter | Not implemented | Future one-scenario provider/fetch path behind explicit opt-in. |

The fake adapter must remain available even after a real adapter is added. It is the stable offline test path.

## 3. Future adapter interface expectation

A future real adapter should accept an already-validated scenario dictionary and return one Stage 62-compatible result payload.

Expected input:

```python
scenario: dict[str, Any]
```

Expected output keys:

```text
scenario_id
site_id
query
status
answer
sources
fallback_used
ok
answer_ok
```

Optional artifact-layer fields such as `timing_ms` may be added later, but the minimal payload contract must remain compatible with Stage 60 writer and Stage 58 export helper.

## 4. Required execution guards

A future real path must fail before provider/fetch setup when:

- `AI_FINDER_LIVE_EVAL` is not exactly `true`,
- `--scenario-id` is missing,
- `--scenario-id` is empty or whitespace,
- `--scenario-id` is `all`, `ALL`, padded `all`, or `*`,
- the scenario id does not exist in the matrix,
- more than one scenario would be selected,
- required provider/fetch configuration is missing.

The first real path must not loop over the full matrix.

## 5. Redaction and persistence rules

A future real adapter must not print or persist:

- API keys or tokens,
- cookies or session identifiers,
- request headers,
- raw provider request payloads,
- raw provider response payloads,
- raw prompts or hidden prompts,
- private endpoints,
- signed URLs,
- full raw HTML documents,
- user-specific private data.

The adapter may return only normalized, public, reviewable fields:

- scenario id,
- site id,
- scenario query text,
- normalized answer,
- normalized public source title and URL,
- short public snippet if already safe,
- coarse timing metrics,
- redaction-safe error type,
- generic redaction-safe error message.

## 6. Source-domain requirement

When a scenario requires sources, normalized source URLs must be public and domain-compatible with the scenario's expected domain.

If the adapter cannot produce a safe source, it should return a fallback payload rather than fabricating a source.

## 7. Review requirement before expansion

Before any multi-scenario or all-scenario live execution is designed, maintainers should review one real single-scenario artifact and confirm:

1. it contains exactly one result,
2. its `scenario_id` exists in the matrix,
3. it uses the Stage 60 artifact writer shape,
4. it exports through the Stage 58 helper,
5. it can be judged against the matching single-scenario slice,
6. source URLs are domain-compatible,
7. no sensitive values appear in the artifact,
8. fake adapter tests still pass.

## 8. Recommended validation commands

Current documentation/design baseline:

```bash
git diff --check
pytest tests/test_single_live_smoke_fake_adapter.py
pytest tests/test_single_live_smoke_dry.py
pytest tests/test_live_runner_result_payload_contract.py
pytest tests/test_live_smoke_artifact_writer.py
pytest tests/test_live_smoke_artifact_export.py
pytest tests/test_smoke_eval_runner.py
```

The existing dry-run command remains offline:

```bash
python scripts/run_single_live_smoke_dry.py \
  --scenario-id bukgu-01 \
  --output /tmp/single_live_dry_artifact.json \
  --created-at 2026-05-30T15:00:00Z
```

## 9. Next safe implementation stage

The next safe code stage should add a real-adapter interface skeleton that still defaults to fake adapters. It should not add a real provider/fetch call yet unless the stage explicitly includes opt-in, one-scenario-only, redaction, source-domain, artifact review, and rollback tests.
