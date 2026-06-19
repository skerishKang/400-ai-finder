# Fetch compatibility diagnostic boundary (Stage #800)

## Purpose

PR #799 prevents the site-search pipeline from hanging on slow external
fetches by enforcing a wall-clock budget and returning a structured
soft JSON when the budget is exceeded. That fix guarantees the demo
**keeps responding**, but it does not classify *why* a fetch failed.

Stage #800 adds a small, operator-safe diagnostic taxonomy so future
operators (and the CLI / dashboards they read) can distinguish a
**timeout** from a **TLS error** from a **403 / 429 block** without
ever exposing raw exception text, response bodies, headers, provider
payloads, or API keys.

This boundary is **diagnostic-only** and **does not perform any live
fetch, network call, provider call, or Firecrawl call**. Real
`bukgu_gwangju` live-compatibility validation is a separate controlled
live-validation stage.

## Scope

In scope for Stage #800:

1. `src/fetch/compat_diagnostics.py`
   * Seven closed categories: `timeout`, `connection_error`,
     `tls_error`, `http_error`, `blocked_or_forbidden`, `parse_error`,
     `unknown_fetch_error`.
   * `classify_exception(exc)` and `classify_http_status(code)` produce
     a `FetchDiagnostic` record.
   * `format_operator_safe(diagnostic)` renders the record as a single
     sanitized line.
2. `tests/test_fetch_compat_diagnostics.py`
   * Taxonomy unit tests (each exception family → its category).
   * No-leak guarantees: secrets, headers, bodies, raw URLs, raw
     exception text never appear in operator-facing output.
   * Integration with PR #799's timeout warning path (no live calls).
3. Operator-safe wiring in `src/demo/site_demo_runner.py`
   * The demo runner now emits the diagnostic category alongside the
     existing "Pipeline raised" / "Pipeline timed out" warning lines.
   * Raw exception text is **never** included in operator-facing
     warnings or in `pipeline_result.error`.
4. Documentation: this file.

Out of scope for Stage #800:

* Any actual live fetch / network call / provider call / Firecrawl
  call.
* Any `bukgu_gwangju` live-compatibility validation.
* Any change to `validate_matrix()`, `evaluate_response()`, or
  source-grounding / query-rewrite / answer-composition code.
* Any change to scenario / snapshot / cache artifact promotion.

## The taxonomy

Each `FetchDiagnostic` exposes only four fields, drawn from closed
vocabularies:

| field          | shape                                                |
| -------------- | ---------------------------------------------------- |
| `category`     | one of seven `FetchCategory` enum values             |
| `short_reason` | fixed string from the taxonomy                       |
| `retry_hint`   | one of `retry`, `backoff`, `do_not_retry`            |
| `is_transient` | bool                                                 |

Sample operator-safe line:

```text
category=parse_error; short_reason=Response payload could not be parsed.; retry_hint=do_not_retry; is_transient=false
```

### Category mapping (exceptions)

| signal                                           | category              |
| ------------------------------------------------ | --------------------- |
| `requests.exceptions.Timeout` (incl. connect/read) | `timeout`            |
| builtin `TimeoutError`, `ssl.SSLWantRead/Write`  | `timeout`             |
| `requests.exceptions.ConnectionError`            | `connection_error`    |
| `ConnectionRefusedError`, `ConnectionResetError`, `ConnectionAbortedError`, `OSError` (incl. DNS) | `connection_error` |
| `requests.exceptions.SSLError`, `ssl.SSLError`   | `tls_error`           |
| `json.JSONDecodeError`, `bs4.*` exceptions       | `parse_error`         |
| anything else                                    | `unknown_fetch_error` |

### Category mapping (HTTP status)

| status code | category                |
| ----------- | ----------------------- |
| 401, 403, 429 | `blocked_or_forbidden` |
| 500, 501, 502, 503, 504, 505 | `http_error` |
| 400, 404, 405, 418, 451, … | `http_error` (non-transient) |
| 2xx, 3xx | `unknown_fetch_error` (sentinel — not a failure) |

## Boundaries — what is **not** in this Stage

* **No live fetch.** This Stage adds a classification helper; it never
  opens a socket, never resolves a DNS record, and never calls any
  upstream provider.
* **No API key use.** No API key is required, read, or transmitted by
  any helper in this Stage.
* **No Firecrawl call.** The Firecrawl provider path is untouched.
* **No raw exception / body / header / URL exposure.** The operator-
  facing output is a closed-vocabulary record. The raw exception stays
  in the debug log only (it is never echoed in the user-facing
  warning, the `pipeline_result.error` field, or the demo response).
* **No scenario / snapshot / cache auto-generation.** This Stage does
  not produce or promote any live artifact.
* **No `RUN_LIVE_*_TESTS=1`.** Tests are pure unit tests that monkey-
  patch or stub; nothing in this Stage respects that environment
  variable.

## Relation to PR #799

PR #799's runner still emits the "Pipeline raised" / "Pipeline timed
out" warning. Stage #800 extends that warning with a sanitized
diagnostic line so the operator-facing category is visible without
leaking the original exception. Concretely:

```text
Pipeline raised: category=parse_error; short_reason=Response payload could not be parsed.; retry_hint=do_not_retry; is_transient=false
```

The previous raw-exception message ("Pipeline raised: Expecting value:
line 1 column 1 (char 0)") is replaced by the diagnostic line.
Operators who need the raw text can still read the debug log; the
public warning and the user-facing JSON never include it.

## Follow-up

Real `bukgu_gwangju` live-compatibility validation runs in a separate
**controlled live validation** Stage, gated on:

* A completed approval packet (per the Stage 418 completeness gate).
* Explicit human approval.
* `RUN_LIVE_BUKGU_LIVE_COMPAT=1` (or equivalent) set by the operator.

Until that Stage lands, the diagnostic helper is exercised only through
unit tests and the demo's mocked pipelines.

## Stage #801 — Sanitized fetch diagnostic persistence

Stage #800 added the classification helper. Stage #801 persists its
output so operators and dashboards can correlate `source_weak` with
the underlying fetch failure category without re-running anything.

### What is persisted

When `SiteDemoRunner` produces a structured result, the result dict
now carries a `fetch_diagnostic` field. On the normal / non-failure
path the field is `None`. On the failure path it is a small
closed-vocabulary dict:

```json
{
  "category": "timeout",
  "short_reason": "Request exceeded its deadline.",
  "retry_hint": "retry",
  "is_transient": true
}
```

The mobile and admin HTTP endpoints surface the same field under the
same name so the dashboard UI can show the category without parsing
nested structures.

`SiteDemoRunner.answer_from_snapshot()` always emits
`fetch_diagnostic: None` because snapshots bypass the live pipeline.
`SiteDemoRunner._build_non_search_result()` (direct_answer / clarify)
emits `fetch_diagnostic: None` for the same reason.

### Conversation log columns

`logs/conversations.jsonl` writes four scalar columns alongside the
existing `route` / `source_weak` / `fallback_used` columns:

| column                              | closed vocabulary                              |
| ----------------------------------- | ---------------------------------------------- |
| `fetch_diagnostic_category`         | one of the seven `FetchCategory` enum values   |
| `fetch_diagnostic_short_reason`     | fixed string from the taxonomy                 |
| `fetch_diagnostic_retry_hint`       | one of `retry`, `backoff`, `do_not_retry`      |
| `fetch_diagnostic_is_transient`     | bool                                           |

The columns are flattened (rather than a nested dict) so JSONL
readers can grep or aggregate on `category` and `retry_hint`
directly without parsing nested structures.

### Boundary preserved

Stage #801 does not relax any Stage #800 safety boundary:

* No live fetch / network / API / Firecrawl call is added.
* No raw exception text, header, body, provider payload, API key, or
  URL credential is ever persisted to the JSONL log.
* The log surface (warning / error / debug) remains sanitized as in
  Stage #800.
* Canary strings (synthetic secrets used in tests) are asserted
  against every persisted record via the Stage #801 leak tests.

### Why this matters for future live validation

Once `bukgu_gwangju` live-compatibility validation is approved, the
JSONL records carry enough structured signal to distinguish:

* `route=site_search` + `source_weak=true` + `fetch_diagnostic_category=timeout`
  → upstream TCP/TLS or WAF blocks the read; retry might work.
* `route=site_search` + `source_weak=true` + `fetch_diagnostic_category=blocked_or_forbidden`
  → upstream is rate-limiting or refusing; retry will not help.
* `route=site_search` + `source_weak=true` + `fetch_diagnostic_category=connection_error`
  → DNS or TCP failure; check network egress.
* `route=site_search` + `source_weak=true` + `fetch_diagnostic_category=parse_error`
  → upstream responded but the body could not be parsed.

Without these columns, every soft-fail looks the same in the log and
operators cannot tell network problems apart from response-format
problems.

## Stage #802 — Fetch diagnostic aggregation report

Stage #800 added the classification helper. Stage #801 persists its
output. Stage #802 reads the persisted JSONL file and produces an
operator-safe aggregation report so operators can spot patterns
without re-running anything.

### Scope of the report

The aggregation helper (`src/demo/conversation_log_report.py`) and the
CLI (`scripts/report_conversation_diagnostics.py`) **never** print:

* raw question text
* raw answer text
* raw warning text
* raw exception / header / body / provider response text
* URL credentials or API keys
* raw conversation contents in any form

The report is **count-based only**. It surfaces counts of routes,
source_weak records, answer_ok failures, fetch diagnostic categories,
retry hints, transient failures, and similar bucketed values. This
is intentional — once real user questions start landing in the log,
the question text becomes sensitive on its own, and operators should
not need it to see whether timeouts are trending up.

### Output shape

```json
{
  "total_records": 12,
  "malformed_line_count": 1,
  "route_counts": {
    "site_search": 9,
    "direct_answer": 2,
    "clarify": 1
  },
  "site_id_counts": {
    "bukgu_gwangju": 12
  },
  "llm_status_counts": {
    "mock_no_api": 8,
    "degraded": 4
  },
  "source_weak_count": 4,
  "answer_ok_false_count": 4,
  "records_with_warnings_count": 4,
  "fetch_diagnostic_category_counts": {
    "timeout": 3,
    "blocked_or_forbidden": 1,
    "none": 8
  },
  "fetch_diagnostic_retry_hint_counts": {
    "retry": 3,
    "do_not_retry": 1,
    "none": 8
  },
  "fetch_diagnostic_transient_count": 3
}
```

Missing or `None` fields are bucketed under `"none"` rather than
silently dropped. `is_transient=True` is counted (false / null is the
trivial default and would dilute the metric), and the `records_with_warnings_count`
field tells operators how many rows in the file carry at least one
warning.

### Malformed-line handling

A malformed line (invalid JSON, a JSON list instead of a dict, or a
non-empty string of garbage) is **skipped** and counted under
`malformed_line_count`. The raw malformed content is **never**
returned to the caller — the helper only emits counts.

### CLI usage

```bash
PYTHONPATH=. python3 scripts/report_conversation_diagnostics.py \
  --log-path logs/conversations.jsonl \
  --json
```

The `--log-path` flag is optional and defaults to
`logs/conversations.jsonl`. With `--json`, the report is emitted as a
JSON object suitable for piping into `jq`. Without `--json`, the
report is a human-readable multi-line text block.

If the log file is missing or empty, the report returns an
empty-summary shape — the CLI never crashes on a missing log.

### Boundary preserved

Stage #802 does not relax any Stage #800 / Stage #801 safety boundary:

* No live fetch / network / API / Firecrawl call is added.
* The aggregator is **read-only** — it reads the local JSONL file and
  emits counts.
* Canary strings (synthetic secrets used in tests) are asserted
  against every output surface (helper dict, `format_text_summary`,
  CLI text, CLI JSON) in the Stage #802 leak tests.
* The CLI never prints the contents of malformed lines; only their
  count.

### What this is **not**

The aggregation report is **not** a live validation tool. It does not
issue fetches, does not resolve hostnames, does not touch any
provider API, and does not produce scenario / snapshot / cache
artifacts. It reads a sanitized local file and emits counts.

Real `bukgu_gwangju` live-compatibility validation remains a separate
**controlled live validation** Stage, gated on the Stage 418 approval
packet.

## Stage #803 — answer_ok / answer_status contract (Issue #803)

Issue #803 root cause: ``snapshot_helper.answer_from_snapshot_helper``
rebuilt the user-facing answer from an empty fallback source set
without touching ``ok`` / ``answer_ok``. The fixture snapshot had
``ok=True, answer_ok=True`` (matched state), and that envelope
followed the demo response even though the answer body had been
replaced by a generic "관련 정보를 찾지 못했습니다" fallback. Operators
seing the response could not tell from the envelope alone whether the
answer was evidence-based or a fallback.

Stage #803 closes that gap with two changes:

### 1. ``answer_ok`` redefined as evidence-based

> ``answer_ok=true`` is true iff the answer was generated from
> grounded source content or from an allowed direct-response path
> (direct_answer / clarify / matched snapshot / grounded site_search
> / LLM degraded direct response).
>
> ``answer_ok=false`` means the response is a generic fallback
> (snapshot unmatched / site_search no-source / timeout / pipeline
> exception).

The previous interpretation — "the pipeline did not crash and a
non-empty answer string was produced" — is now expressed by the
``ok`` field, which keeps its transport/pipeline-success meaning.

### 2. ``answer_status`` closed-vocab enum

A new closed-vocab scalar field is exposed on every demo response
(snapshot / mobile / admin) and persisted as a separate column in the
conversation log:

| value | meaning | typical envelope |
|---|---|---|
| `answered_with_evidence` | 근거 source 기반 답변 또는 허용된 직접 응답 경로가 정상 생성 | `ok=true, answer_ok=true` |
| `fallback_no_match`      | source/snapshot 매칭 없음, generic fallback 반환 | `ok=true, answer_ok=false, source_weak=true` |
| `fallback_unavailable`   | timeout으로 데이터 미수신, soft fallback 반환 | `ok=false, answer_ok=false, source_weak=true` |
| `error`                  | pipeline 예외 등 처리 불가능 상태 | `ok=false, answer_ok=false, source_weak=true` |

Definitions live in ``src/answer/answer_status.py`` (the closed vocab
and a ``normalize_answer_status`` defensive default that maps unknown
values to ``"error"``).

### 9-path behavior matrix (before → after)

| # | route / scenario                          | before                                                                  | after                                                                                              |
|---|-------------------------------------------|-------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| 1 | direct_answer                              | ok=t, answer_ok=t, source_weak=F, fetch_diag=null                       | ok=t, answer_ok=t, source_weak=F, fetch_diag=null, **answer_status=`answered_with_evidence`**     |
| 2 | clarify                                    | ok=t, answer_ok=t, source_weak=F, fetch_diag=null                       | ok=t, answer_ok=t, source_weak=F, fetch_diag=null, **answer_status=`answered_with_evidence`**     |
| 3 | snapshot matched                            | ok=t, answer_ok=t, source_weak=F, fetch_diag=null                       | ok=t, answer_ok=t, source_weak=F, fetch_diag=null, **answer_status=`answered_with_evidence`**     |
| 4 | snapshot unmatched fallback (Issue #803)    | ok=t, answer_ok=t, source_weak=T, fetch_diag=null   ⚠️ **모순**           | ok=t, answer_ok=F, source_weak=T, fetch_diag=null, **answer_status=`fallback_no_match`**         |
| 5 | site_search grounded success                | ok=t, answer_ok=t, source_weak=F, fetch_diag=null                       | ok=t, answer_ok=t, source_weak=F, fetch_diag=null, **answer_status=`answered_with_evidence`**     |
| 6 | site_search no-source / fallback used       | ok=t, answer_ok=t, source_weak=T, fetch_diag=null   ⚠️ 부분 모순          | ok=t, answer_ok=F, source_weak=T, fetch_diag=null, **answer_status=`fallback_no_match`**         |
| 7 | site_search timeout                         | ok=F, answer_ok=F, source_weak=T, fetch_diag=category=timeout           | ok=F, answer_ok=F, source_weak=T, fetch_diag=category=timeout, **answer_status=`fallback_unavailable`** |
| 8 | pipeline exception soft-fail                | ok=F, answer_ok=F, source_weak=T, fetch_diag=category=connection_error  | ok=F, answer_ok=F, source_weak=T, fetch_diag=category=connection_error, **answer_status=`error`** |
| 9 | LLM degraded direct response                | ok=t, answer_ok=t, source_weak=F, llm_status=live_provider_error        | ok=t, answer_ok=t, source_weak=F, llm_status=live_provider_error, **answer_status=`answered_with_evidence`** |

Note on path 8 vs 7: the previous code classified any non-ok pipeline
with a non-empty warning as `fallback_unavailable`, which conflated
timeout with non-timeout exceptions. Stage #803 keys the
classification off ``pipeline_diagnostic.category`` so that timeout
diagnostics map to `fallback_unavailable` and every other closed-vocab
fetch diagnostic (connection_error / tls_error / http_error /
blocked_or_forbidden / parse_error / unknown_fetch_error) maps to
`error`.

### Operational impact

- Conversation log JSONL gains a 26th scalar column `answer_status`.
- Stage #802 aggregation report gains an `answer_status_counts` field
  with a `"none"` bucket for legacy / malformed records.
- Existing `answer_ok_false_count` semantics tighten: it now counts
  only the records whose answer was a generic fallback (path 4, 6, 7,
  8). Records that previously reported `answer_ok=false` because the
  runner classified an exception as such continue to be counted; what
  changes is that path 4 (snapshot unmatched) and path 6 (site_search
  no-source) now also count, where they did not before.

### Boundary preserved

Stage #803 does not relax any Stage #800 / Stage #801 / Stage #802
safety boundary:

- No live fetch / network / API / Firecrawl call is added.
- No raw exception text is exposed in any operator-visible field.
- Canary strings (synthetic secrets used in tests) are asserted
  against the new `answer_status` and the full envelope on both
  `answer_from_snapshot` and `runner.answer` (pipeline exception) paths.
- The conversation log writer normalizes unknown `answer_status`
  values to `"error"`, so legacy or malformed snapshots never inject a
  free-form string into the JSONL.
