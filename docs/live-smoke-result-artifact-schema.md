# Live Smoke Result Artifact Schema

Stage 56 defines the persisted result artifact shape for a future live smoke eval run.

This document is design-only. It does not enable live provider calls, fetch calls, network calls, or app pipeline execution. The goal is to make the future live path compatible with the existing offline export and response judge flow before any live execution is implemented.

## 1. Boundary

There are two related but different JSON shapes:

1. **Live smoke result artifact**
   - Captures one full live smoke eval run.
   - Contains run metadata, scenario-level status, timing summaries, normalized answers, normalized sources, fallback/error summaries, and redaction-safe diagnostics.
   - This is the future persisted output of a live run.

2. **Stage 42 response fixture**
   - The compact judge input already accepted by `scripts/run_smoke_eval.py --responses`.
   - Contains only `scenario_id`, `site_id`, `answer`, `sources`, and `fallback` per response.
   - This remains the canonical input to the existing response judge.

A future converter should transform the live smoke result artifact into the existing pipeline/demo-shaped result structure, then reuse `scripts/export_smoke_responses.py --eval` or the underlying exporter functions.

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

## 7. Conversion to existing judge path

A future converter should transform each live artifact result into the Stage 43 exporter input shape:

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

Then the existing offline command can be reused:

```bash
python scripts/export_smoke_responses.py \
  /tmp/live_pipeline_results.json \
  --matrix tests/fixtures/smoke_scenario_matrix.json \
  --eval
```

This keeps live execution, result persistence, export normalization, and judge evaluation separate.

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
9. the converted result can be evaluated through `scripts/export_smoke_responses.py --eval`.

## 10. Recommended next implementation stages

Recommended narrow order after this design:

1. Add a static fixture for this artifact shape.
2. Add schema validation tests for the fixture.
3. Add a converter from live artifact shape to Stage 43 exporter input shape.
4. Add an offline roundtrip test from live artifact fixture to `--eval`.
5. Only after that, add a guarded live runner that can write this artifact under explicit opt-in.
