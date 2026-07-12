# Live Smoke Result Artifact Schema

Stage 56 defines the persisted result artifact shape for a future live smoke eval run. Stage 58 adds the reusable offline helper that converts this artifact shape into the existing Stage 43 pipeline-shaped result format and can immediately evaluate it through the existing response judge path. Stage 60 adds the offline writer helper that serializes already-produced result dictionaries into this artifact shape. Stage 62 defines the minimal payload contract that a future live runner should pass into the Stage 60 writer. Stage 65 adds a single-scenario dry runner skeleton that writes one offline/dummy payload through the same artifact writer boundary.

This document is design-only for the artifact and runner payload shapes. It does not enable live provider calls, fetch calls, network calls, Firecrawl calls, or app pipeline execution. The current writer/export/helper/test paths are fully offline and only normalize already-produced or deterministic dry-run JSON.

## 1. Boundary

There are five related but different JSON shapes:

1. **Live runner result payload**
   - Minimal already-produced result dictionaries expected from a future live runner before Stage 60 artifact writing.
   - Captured by `tests/fixtures/live_runner_result_payloads.json` and `tests/test_live_runner_result_payload_contract.py`.
   - Contains the core answer/source/status fields needed by the writer.
   - Does not require artifact-level `timing_ms` or `diagnostics`.

2. **Single-scenario dry runner payload**
   - A deterministic offline payload produced by `scripts/run_single_live_smoke_dry.py` for exactly one scenario id.
   - It uses the same Stage 62-compatible result payload fields.
   - It must reject broad selectors such as `all` or `*`.
   - It exists only to prove the payload -> writer -> artifact -> export helper boundary before any real provider/fetch call is introduced.

3. **Live smoke result artifact**
   - Captures one live smoke run or one dry-run artifact, depending on the producing command.
   - Contains run metadata, scenario-level status, normalized answers, normalized sources, fallback/error summaries, and redaction-safe diagnostics.
   - Stage 60 can write this shape from already-produced result dictionaries.
   - Stage 65 writes a one-result artifact with `live_opt_in=false` and offline provider/fetch labels.

4. **Stage 43 pipeline/demo-shaped result**
   - Intermediate structure accepted by `scripts/export_smoke_responses.py`.
   - Contains `results[]` items with `{scenario_id, result}`.
   - Stage 58 converts live artifacts into this shape.
   - Stage 60 can also accept this shape as input when writing an artifact.

5. **Stage 42 response fixture**
   - The compact judge input already accepted by `scripts/run_smoke_eval.py --responses`.
   - Contains only `scenario_id`, `site_id`, `answer`, `sources`, and `fallback` per response.
   - This remains the canonical input to the existing response judge.

The Stage 62 contract proves the full-matrix offline route:

```text
live_runner_result_payloads.json
  -> Stage 60 writer
  -> Stage 56/57-compatible live artifact
  -> Stage 58 export helper
  -> Stage 43 pipeline-shaped result
  -> Stage 42 response judge
```

The Stage 65 skeleton proves the single-scenario dry route:

```text
one scenario id
  -> deterministic offline dummy payload
  -> Stage 62-compatible result payload
  -> Stage 60 writer
  -> one-result live smoke artifact
  -> Stage 58 export helper
  -> Stage 43 pipeline-shaped result
  -> Stage 42 response judge for that single scenario slice
```

## 2. Top-level shape

A persisted live smoke result artifact should be a JSON object with this shape:

```json
{
  "_meta": {
    "version": "1.0.0",
    "artifact_type": "live_smoke_eval_results",
    "stage": 60,
    "created_at": "2026-05-30T12:00:00Z",
    "matrix_path": "tests/fixtures/smoke_scenario_matrix.json",
    "scenario_count": 1,
    "offline_boundary": false,
    "redaction": {
      "secrets_persisted": false,
      "cookies_persisted": false,
      "request_headers_persisted": false,
      "raw_provider_payloads_persisted": false,
      "raw_prompts_persisted": false
    }
  },
  "run": {
    "status": "completed",
    "live_opt_in": false,
    "provider_name": "offline-dry-run",
    "fetch_provider_name": "offline-dry-run",
    "started_at": "2026-05-30T15:00:00Z"
  },
  "results": []
}
```

`results` must be a non-empty array when the run reaches scenario execution. Stage 65 dry-run artifacts intentionally contain exactly one result. A future all-scenario live run may contain all matrix scenarios, but that is not enabled by Stage 65/66.

## 3. Required run metadata

`_meta` should include:

| Field | Required | Description |
|---|---:|---|
| `version` | yes | Artifact schema version. Start with `1.0.0`. |
| `artifact_type` | yes | Must be `live_smoke_eval_results`. |
| `stage` | yes | Stage that introduced or last revised the writer output. Stage 60 writer currently records `60`. |
| `created_at` | yes | UTC ISO-8601 timestamp. |
| `matrix_path` | yes | Matrix path used by the run. |
| `scenario_count` | yes | Number of scenario results stored in the artifact. Stage 65 dry-run uses `1`. |
| `offline_boundary` | yes | Historical schema flag. Redaction and run metadata still define the real safety boundary. |
| `redaction` | yes | Boolean proof flags confirming sensitive content was not persisted. |

`run` should include:

| Field | Required | Description |
|---|---:|---|
| `status` | yes | One of `completed`, `partial`, `failed`, `preflight_only`. |
| `live_opt_in` | yes | Whether explicit live opt-in was active. Stage 65 dry-run writes `false`. |
| `provider_name` | yes | Safe provider label only. Do not store keys or private endpoints. |
| `fetch_provider_name` | yes | Safe fetch provider label only. |
| `started_at` | yes | UTC ISO-8601 timestamp. |
| `finished_at` | no | UTC ISO-8601 timestamp if the run ended normally. |
| `duration_ms` | no | Total elapsed time in milliseconds. |

## 4. Scenario result shape

Each item in an artifact `results` array should contain exactly one scenario result:

```json
{
  "scenario_id": "bukgu-01",
  "site_id": "bukgu_gwangju",
  "query": "민원서식 어디서 받아?",
  "status": "answered",
  "answer": "민원서식 관련 정보는 bukgu_gwangju 홈페이지의 Stage 65 dry-run 출처에서 확인할 수 있습니다.",
  "sources": [
    {
      "title": "민원서식 service_navigation",
      "url": "https://bukgu.gwangju.kr/stage65-dry/bukgu-01"
    }
  ],
  "fallback_used": false,
  "ok": true,
  "answer_ok": true,
  "diagnostics": {
    "source_count": 1,
    "normalized_source_count": 1,
    "error_type": null,
    "error_message": null
  }
}
```

Artifact result fields:

| Field | Required | Description |
|---|---:|---|
| `scenario_id` | yes | Must match a scenario id in `smoke_scenario_matrix.json`. |
| `site_id` | yes | Site profile id used for the scenario. |
| `query` | yes | Scenario question text. |
| `status` | yes | One of `answered`, `fallback`, `error`, `skipped`, `pending_configuration`. |
| `answer` | yes | Normalized user-facing answer. Empty string is allowed only for hard errors. |
| `sources` | yes | Array of normalized source objects. Empty array is valid for fallback/error paths. |
| `fallback_used` | yes | Boolean fallback flag. |
| `ok` | yes | Whether the scenario completed without runner-level failure. |
| `answer_ok` | yes | Whether the answer is usable enough for judge conversion. |
| `timing_ms` | no | Optional timing summary. Not required in the minimal payload contract. |
| `diagnostics` | yes | Redaction-safe status details only. Stage 60 writer can derive this from sources. |

If Stage 60 writer receives Stage 43 pipeline/demo-shaped input, missing `query` is filled with the `scenario_id`, and missing `status` is inferred from `fallback_used`. This is a compatibility fallback for offline fixtures only. A future real live runner should provide real `query` and `status` values directly.

## 5. Minimal live runner payload contract

Stage 62 defines the minimal shape for future live runner result dictionaries in `tests/fixtures/live_runner_result_payloads.json`. Stage 65 reuses that same shape for its deterministic single-scenario dry payload.

Each runner payload result must include exactly these core fields:

| Field | Required | Description |
|---|---:|---|
| `scenario_id` | yes | Must match a scenario id in `tests/fixtures/smoke_scenario_matrix.json`. |
| `site_id` | yes | Site profile id used for the scenario. |
| `query` | yes | Scenario question text. |
| `status` | yes | One of `answered`, `fallback`, `error`, `skipped`, `pending_configuration`. |
| `answer` | yes | Normalized user-facing answer. |
| `sources` | yes | Array of normalized source objects. Empty array is valid for fallback/error paths. |
| `fallback_used` | yes | Boolean fallback flag. |
| `ok` | yes | Whether the scenario completed without runner-level failure. |
| `answer_ok` | yes | Whether the answer is usable enough for judge conversion. |

The minimal runner payload contract intentionally does **not** require `timing_ms` or `diagnostics`. Those fields belong to the richer persisted artifact layer. The Stage 60 writer can derive or attach redaction-safe diagnostics such as `source_count`, `normalized_source_count`, and generic error metadata while preserving the same answer/source/status contract.

Targeted contract tests:

```bash
pytest tests/test_live_runner_result_payload_contract.py
pytest tests/test_single_live_smoke_dry.py
```

## 6. Single-scenario dry-run behavior

`scripts/run_single_live_smoke_dry.py` is a skeleton, not a live runner. It accepts one scenario id and writes one artifact.

```bash
python scripts/run_single_live_smoke_dry.py \
  --scenario-id bukgu-01 \
  --output /tmp/single_live_dry_artifact.json \
  --created-at 2026-05-30T15:00:00Z
```

Required safety behavior:

- The command accepts exactly one scenario id.
- `all` and `*` are rejected.
- The command produces deterministic offline dummy data.
- The output payload is Stage 62-compatible.
- The artifact is written through the Stage 60 writer boundary.
- `run.live_opt_in` remains `false`.
- provider/fetch labels are safe offline labels.
- No provider, fetch, network, Firecrawl, or app pipeline calls occur.

The resulting artifact can be converted by Stage 58:

```bash
python scripts/export_live_smoke_artifact.py \
  /tmp/single_live_dry_artifact.json \
  --output /tmp/single_live_pipeline_result.json
```

Because this artifact has one result, it should be evaluated against a single-scenario slice, not the full 14-scenario matrix. `tests/test_single_live_smoke_dry.py` verifies that single-scenario judge boundary.

## 7. Source shape

Each source should use the same normalized source shape accepted by `scripts/export_smoke_responses.py`:

```json
{
  "title": "민원서식",
  "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000"
}
```

Allowed optional source fields for live artifacts:

| Field | Description |
|---|---|
| `title` | Human-readable source title. |
| `url` | Canonical public URL. |
| `snippet` | Short public page snippet if already safe to show. |
| `source_rank` | 1-based rank of the source in the answer. |

Do not store request headers, cookies, raw HTML dumps, private signed URLs, or crawl-provider internal payloads in source objects.

## 8. Error and fallback handling

Fallback and error paths should still be convertible to the Stage 42 response fixture shape.

Recommended status mapping:

| Live artifact status | `ok` | `answer_ok` | `fallback_used` | Stage 42 `fallback` |
|---|---:|---:|---:|---:|
| `answered` | true | true | false | false |
| `fallback` | true | true | true | true |
| `error` | false | false | true | true |
| `skipped` | false | false | true | true |
| `pending_configuration` | false | false | true | true |

For errors, persist only redaction-safe summaries. `error_message` must be generic and must not contain provider keys, request headers, cookies, private URLs, user-specific account data, or full raw payload excerpts.

## 9. Writer and conversion to existing judge path

Stage 60 writer can serialize already-produced results into the live artifact shape:

```bash
python scripts/write_live_smoke_artifact.py \
  tests/fixtures/smoke_pipeline_results_roundtrip.json \
  --output /tmp/written_live_artifact.json \
  --created-at 2026-05-30T13:15:00Z
```

Stage 65 starts from a single scenario id and reaches the same writer boundary:

```bash
python scripts/run_single_live_smoke_dry.py \
  --scenario-id bukgu-01 \
  --output /tmp/single_live_dry_artifact.json \
  --created-at 2026-05-30T15:00:00Z
```

Then Stage 58 converter transforms each live artifact result into the Stage 43 exporter input shape:

```bash
python scripts/export_live_smoke_artifact.py \
  /tmp/single_live_dry_artifact.json \
  --output /tmp/single_live_pipeline_result.json
```

This keeps live execution, result persistence, artifact writing, export normalization, and judge evaluation separate.

## 10. Redaction rules

A live smoke result artifact must not persist:

- API keys or tokens
- cookies or session identifiers
- request headers
- raw provider request payloads
- raw provider response payloads
- raw prompts or hidden system/developer prompts
- private endpoints
- signed URLs
- full raw HTML documents
- personally identifiable user data not already present in the public scenario matrix

A safe artifact may persist:

- scenario id
- site id
- scenario query text
- normalized public answer
- normalized public source title and URL
- short public snippet
- coarse timing metrics
- redaction-safe error type
- generic redaction-safe error message

The minimal runner payload contract and the Stage 65 dry skeleton should follow the same redaction boundary before artifact writing.

## 11. Validation checklist for future implementation

Before a future code stage writes this artifact, it should validate that:

1. `artifact_type` is `live_smoke_eval_results` after artifact writing.
2. `scenario_count` matches the number of results actually stored.
3. single-scenario dry artifacts contain exactly one result.
4. all-scenario live execution is not enabled unless a later explicit stage implements it.
5. every executed scenario has a unique `scenario_id`.
6. each `scenario_id` exists in the matrix.
7. every source URL is public and belongs to the expected scenario domain when applicable.
8. all redaction flags are explicitly false for persisted sensitive data.
9. no raw keys, cookies, headers, prompts, or provider payloads appear in the serialized JSON.
10. the runner payload can be written by the Stage 60 writer.
11. the artifact can be converted to the Stage 43 exporter input shape.
12. one-result artifacts are evaluated against a single-scenario slice unless a later stage adds full-matrix result coverage.
13. writer-generated artifacts remain fully offline unless a future live runner explicitly provides already-produced result dictionaries.

## 12. Recommended next implementation stages

Recommended narrow order after this writer/helper/payload-contract/single-dry baseline:

1. Keep documenting and testing the single-scenario dry-run path before real provider/fetch calls.
2. Add a safety checklist for a real single-scenario provider/fetch opt-in stage.
3. Add real provider/fetch calls only behind explicit opt-in and only for one scenario.
4. Evaluate one real artifact before adding sequential/rate-limited multi-scenario execution.
5. Add optional report import/export UI only after CLI artifacts are stable.
