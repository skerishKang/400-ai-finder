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
