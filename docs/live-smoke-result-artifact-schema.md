# Live Smoke Result Artifact Schema

Stage 56 defines the persisted result artifact shape for a future live smoke eval run. Stage 58 adds the reusable offline helper that converts this artifact shape into the existing Stage 43 pipeline-shaped result format and can immediately evaluate it through the existing response judge path. Stage 60 adds the offline writer helper that serializes already-produced result dictionaries into this artifact shape.

This document is design-only for the artifact shape itself. It does not enable live provider calls, fetch calls, network calls, or app pipeline execution. The current writer/export helper paths are also fully offline and only normalize already-produced JSON.

## 1. Boundary

There are three related but different JSON shapes:

1. **Live smoke result artifact**
   - Captures one full live smoke eval run.
   - Contains run metadata, scenario-level status, timing summaries, normalized answers, normalized sources, fallback/error summaries, and redaction-safe diagnostics.
   - This is the future persisted output of a live run.
   - Stage 60 can write this shape from already-produced result dictionaries.

2. **Stage 43 pipeline/demo-shaped result**
   - Intermediate structure accepted by `scripts/export_smoke_responses.py`.
   - Contains `results[]` items with `{scenario_id, result}`.
   - Stage 60 can accept this shape as input when writing an artifact.

3. **Stage 42 response fixture**
   - The compact judge input already accepted by `scripts/run_smoke_eval.py --responses`.
   - Contains only `scenario_id`, `site_id`, `answer`, `sources`, and `fallback` per response.
   - This remains the canonical input to the existing response judge.

Stage 60 provides the current offline writer bridge:

```bash
python scripts/write_live_smoke_artifact.py \
  tests/fixtures/smoke_pipeline_results_roundtrip.json \
  --output /tmp/written_live_artifact.json \
  --created-at 2026-05-30T13:15:00Z
```

Stage 58 provides the current offline export/eval bridge:

```bash
python scripts/export_live_smoke_artifact.py \
  /tmp/written_live_artifact.json \
  --eval
```

Together, these commands prove that already-produced result dictionaries can be persisted as a live smoke artifact and re-evaluated through the existing judge path without performing live execution.

## 2. Top-level shape

A persisted live smoke result artifact should be a JSON object with this shape:

```json
{
  "_meta": {
    "version": "1.0.0",
    "artifact_type": "live_smoke_eval_results",
    "stage": 56,
    "created_at": "2026-05-30T12:00:00Z",
    "matrix_path": "tests/fixtures/smoke_scenario_matrix.json",
    "scenario_count": 14,
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
    "live_opt_in": true,
    "provider_name": "redacted-provider-label",
    "fetch_provider_name": "redacted-fetch-label",
    "started_at": "2026-05-30T12:00:00Z",
    "finished_at": "2026-05-30T12:02:00Z",
    "duration_ms": 120000
  },
  "results": []
}
```

`results` must be a non-empty array when the run reaches scenario execution. A preflight-only run should not use this artifact shape unless the runner explicitly records `run.status` as `preflight_only` and leaves `results` empty.

## 3. Required run metadata

`_meta` should include:

| Field | Required | Description |
|---|---:|---|
| `version` | yes | Artifact schema version. Start with `1.0.0`. |
| `artifact_type` | yes | Must be `live_smoke_eval_results`. |
| `stage` | yes | Stage that introduced or last revised the schema. |
| `created_at` | yes | UTC ISO-8601 timestamp. |
| `matrix_path` | yes | Matrix path used by the run. |
| `scenario_count` | yes | Number of scenarios loaded from the matrix. |
| `offline_boundary` | yes | Must be `false` for true live runs. Dry-runs should continue using existing offline fixture formats. |
| `redaction` | yes | Boolean proof flags confirming sensitive content was not persisted. |

Stage 60 writer output currently records `stage: 60` to show that the artifact was produced by the writer helper. Future live-run artifacts may update the stage value when the writer contract changes.

`run` should include:

| Field | Required | Description |
|---|---:|---|
| `status` | yes | One of `completed`, `partial`, `failed`, `preflight_only`. |
| `live_opt_in` | yes | Whether explicit live opt-in was active. |
| `provider_name` | yes | Safe provider label only. Do not store keys or private endpoints. |
| `fetch_provider_name` | yes | Safe fetch provider label only. |
| `started_at` | yes | UTC ISO-8601 timestamp. |
| `finished_at` | no | UTC ISO-8601 timestamp if the run ended normally. |
| `duration_ms` | no | Total elapsed time in milliseconds. |

## 4. Scenario result shape

Each item in `results` should contain exactly one scenario result:

```json
{
  "scenario_id": "bukgu-01",
  "site_id": "bukgu_gwangju",
  "query": "민원서식 어디서 받아요?",
  "status": "answered",
  "answer": "민원서식은 북구청 종합민원 메뉴에서 확인할 수 있습니다.",
  "sources": [
    {
      "title": "민원서식",
      "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000"
    }
  ],
  "fallback_used": false,
  "ok": true,
  "answer_ok": true,
  "timing_ms": {
    "total": 8200,
    "fetch": 3100,
    "provider": 4200
  },
  "diagnostics": {
    "source_count": 1,
    "normalized_source_count": 1,
    "error_type": null,
    "error_message": null
  }
}
```

Required fields:

| Field | Required | Description |
|---|---:|---|
| `scenario_id` | yes | Must match a scenario id in `smoke_scenario_matrix.json`. |
| `site_id` | yes | Site profile id used for the run. |
| `query` | yes | Scenario question text. |
| `status` | yes | One of `answered`, `fallback`, `error`, `skipped`, `pending_configuration`. |
| `answer` | yes | Normalized user-facing answer. Empty string is allowed only for hard errors. |
| `sources` | yes | Array of normalized source objects. Empty array is valid for fallback/error paths. |
| `fallback_used` | yes | Boolean fallback flag. |
| `ok` | yes | Whether the scenario completed without runner-level failure. |
| `answer_ok` | yes | Whether the answer is usable enough for judge conversion. |
| `timing_ms` | no | Optional timing summary. |
| `diagnostics` | yes | Redaction-safe status details only. |

If Stage 60 writer receives Stage 43 pipeline/demo-shaped input, missing `query` is filled with the `scenario_id`, and missing `status` is inferred from `fallback_used`. This is a compatibility fallback for offline fixtures only. A future live runner should provide real `query` and `status` values directly.

## 5. Source shape

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

## 6. Error and fallback handling

Fallback and error paths should still be convertible to the Stage 42 response fixture shape.

Recommended status mapping:

| Live artifact status | `ok` | `answer_ok` | `fallback_used` | Stage 42 `fallback` |
|---|---:|---:|---:|---:|
| `answered` | true | true | false | false |
| `fallback` | true | true | true | true |
| `error` | false | false | true | true |
| `skipped` | false | false | true | true |
| `pending_configuration` | false | false | true | true |

For errors, persist only redaction-safe summaries:

```json
{
  "status": "error",
  "answer": "출처가 부족하므로 홈페이지에서 직접 확인해 주세요.",
  "sources": [],
  "fallback_used": true,
  "ok": false,
  "answer_ok": false,
  "diagnostics": {
    "error_type": "fetch_timeout",
    "error_message": "Fetch timed out after configured timeout.",
    "source_count": 0,
    "normalized_source_count": 0
  }
}
```

`error_message` must be generic. It must not contain provider keys, request headers, cookies, private URLs, user-specific account data, or full raw payload excerpts.

## 7. Writer and conversion to existing judge path

Stage 60 writer can serialize already-produced results into the live artifact shape:

```bash
python scripts/write_live_smoke_artifact.py \
  tests/fixtures/smoke_pipeline_results_roundtrip.json \
  --output /tmp/written_live_artifact.json \
  --created-at 2026-05-30T13:15:00Z
```

Then Stage 58 converter transforms each live artifact result into the Stage 43 exporter input shape:

```json
{
  "results": [
    {
      "scenario_id": "bukgu-01",
      "result": {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 메뉴에서 확인할 수 있습니다.",
        "sources": [
          {
            "title": "민원서식",
            "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000"
          }
        ],
        "ok": true,
        "answer_ok": true,
        "fallback_used": false
      }
    }
  ]
}
```

Direct eval command for an artifact:

```bash
python scripts/export_live_smoke_artifact.py \
  /tmp/written_live_artifact.json \
  --eval
```

Expected result:

```text
Smoke response eval loaded
Evaluated responses: 14
Passed: 14
Failed: 0

Status: response eval passed
```

Two-step export and eval is also supported:

```bash
python scripts/export_live_smoke_artifact.py \
  /tmp/written_live_artifact.json \
  --output /tmp/live_pipeline_results.json

python scripts/export_smoke_responses.py \
  /tmp/live_pipeline_results.json \
  --matrix tests/fixtures/smoke_scenario_matrix.json \
  --eval
```

This keeps live execution, result persistence, artifact writing, export normalization, and judge evaluation separate.

## 8. Redaction rules

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

## 9. Validation checklist for future implementation

Before a future code stage writes this artifact, it should validate that:

1. `artifact_type` is `live_smoke_eval_results`.
2. `scenario_count` matches the loaded matrix.
3. every executed scenario has a unique `scenario_id`.
4. each `scenario_id` exists in the matrix.
5. every source URL is public and belongs to the expected scenario domain when applicable.
6. all redaction flags are explicitly false for persisted sensitive data.
7. no raw keys, cookies, headers, prompts, or provider payloads appear in the serialized JSON.
8. the artifact can be converted to the Stage 43 exporter input shape.
9. the converted result can be evaluated through `scripts/export_live_smoke_artifact.py --eval`.
10. writer-generated artifacts remain fully offline unless a future live runner explicitly provides already-produced result dictionaries.

## 10. Recommended next implementation stages

Recommended narrow order after this writer/helper baseline:

1. Add a minimal live runner result payload contract for the data passed into Stage 60 writer.
2. Add provider/fetch opt-in wiring behind `AI_FINDER_LIVE_EVAL=true` without executing scenario loops yet.
3. Add a single-scenario guarded live runner path that writes an artifact through Stage 60 writer.
4. Add live runner execution in a strictly sequential, rate-limited path.
5. Add optional report import/export UI only after CLI artifacts are stable.
