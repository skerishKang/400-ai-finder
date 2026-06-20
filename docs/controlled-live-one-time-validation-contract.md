# Controlled-Live One-Time Validation Execution Contract

## Stage

Stage 821

---

## 1. Purpose and Scope

This document is the **execution contract** for a future one-time
controlled-live validation. It freezes the exact shape of the
request, the exact shape of the result, and the exact non-goals so
that any future code path that wants to perform a real controlled
validation **must match this contract line-by-line** or it cannot be
considered approved.

**This contract does NOT approve, schedule, or trigger any real
controlled validation.** Live execution remains blocked in Stage
821. This document is a **pre-execution lock**, not an authorization
to run anything.

- No real network call is permitted by reading this document.
- No provider, LLM, Firecrawl, browser, subprocess, thread, or
  asyncio execution is permitted by reading this document.
- The runner code path in `src/demo/controlled_live_ux_runner.py`
  is **not** modified by this issue. The runner remains a dry-run
  surface that only invokes injected stub seams in tests.

The intent is to make the future validation **safe by construction**
so that no future contributor can accidentally widen the runner
into live execution without first updating this contract and passing
review.

---

## 2. Required Preconditions (must hold before any future execution)

All of the following MUST be true before a one-time controlled
validation may be considered for execution:

- [ ] **Stage #817 one-shot runner seam merged.** The
  `one_shot_runner` keyword-only seam exists in
  `src/demo/controlled_live_ux_runner.py` and the runner accepts
  exactly one injected callable per invocation.
- [ ] **Stage #819 command guard merged.** The
  `src/demo.controlled_live_command_guard` module exists, exports
  `CommandDecision` and `evaluate_command`, and the runner uses
  the guard as the LAST gate before any seam call.
- [ ] **Default dry-run remains unchanged.** Any request that fails
  the guard still returns `mode="dry_run"`,
  `execution_allowed=False`, and the Stage #806
  `fallback_no_match` envelope. No future change may silently
  change the default.
- [ ] **Explicit human approval required.** Even when the guard
  approves, the seam must be an **injected stub** in any
  pre-execution test. Wiring a real executor is a separate
  human-approved change that must be reviewed in a follow-up
  issue, never silently enabled.

If any of the above is not true, no future execution contract
revision may be considered valid.

---

## 3. Future Controlled Validation Request — Required Fields

A future controlled validation request MUST specify **all** of the
following fields, explicitly, with no defaults and no placeholders
silently accepted. Every field is mandatory; missing field = invalid
request = dry-run.

| Field                     | Type / Shape                                  | Notes |
| ------------------------- | --------------------------------------------- | ----- |
| `question`                | nonblank `str`, ≤ 500 chars                   | The exact user question. The runner echoes nothing of this. |
| `site_id`                 | `str` exactly equal to `"bukgu_gwangju"`     | Closed allowlist; no other site is allowed. |
| `fetch_provider`          | `str` exactly equal to `"requests"`           | Closed allowlist; no other fetch provider. |
| `llm_provider`            | `str` exactly equal to `"stub"`               | Closed allowlist; no real LLM provider. |
| `fetch_mode`              | `str` exactly equal to `"subprocess_process_group"` | Closed allowlist; isolated process group. |
| `expected_result_envelope`| `dict` matching Stage #806 schema              | See §5. |
| `operator_acknowledgement`| `str` exactly equal to `"I_ACKNOWLEDGE_CONTROLLED_LIVE"` | Exact, case-sensitive, no whitespace tolerance. |
| `rollback_procedure`      | `str` nonblank, "no-persist"                  | Must explicitly state that scenario / snapshot / cache / config / source-grounding is **not** persisted and any temporary artifact is cleaned up deterministically. |

### 3.1 Field Semantics

- **`question`**: passed through the Stage #811 question validator
  (`str`, nonblank, ≤ 500 chars). Failure raises
  `LockedControlledLiveUxError("question_invalid")` with a fixed
  safe code. The raw question is **never** echoed in the result,
  any exception, or any repr.
- **`site_id` / `fetch_provider` / `llm_provider`**: must match
  the Stage #807 closed allowlist exactly. Any other value fails
  the Stage #807 contract validation and is treated as
  `invalid_request`.
- **`fetch_mode`**: must be `"subprocess_process_group"` to honor
  the Stage #807 isolated-process-group and
  `kill_process_group_on_timeout` flags. Any other value fails
  the Stage #807 contract.
- **`expected_result_envelope`**: the caller MUST explicitly
  declare which Stage #806 status it expects. The runner does not
  invent a result; the seam is responsible for producing one of
  the four closed states, and the runner normalizes the seam's
  output to the canonical Stage #806 envelope.
- **`operator_acknowledgement`**: must be **exactly**
  `"I_ACKNOWLEDGE_CONTROLLED_LIVE"`. No substring, no
  case-folding, no leading/trailing whitespace.
- **`rollback_procedure`**: must state the no-persist policy
  explicitly. Default values are not allowed.

### 3.2 Rollback / No-Persist Procedure

The future request MUST include a `rollback_procedure` field that
**explicitly** commits to:

- No scenario persistence (`persist_scenarios=False`).
- No snapshot persistence (`persist_snapshots=False`).
- No cache persistence (`persist_cache=False`).
- No config persistence (`persist_config=False`).
- No source-grounding persistence
  (`persist_source_grounding=False`).
- `temp_only_output=True` for any artifact written.
- `deterministic_cleanup=True` for the cleanup path.
- `audit_path=None` (no audit trail written to disk).
- `retain_artifacts=False` (no long-term retention).
- An explicit `separate_fetch_attempts_observable=True` so that
  each fetch attempt is recorded for review (without persisting
  any of the actual fetched content beyond the temporary
  envelope).

If `rollback_procedure` is blank, missing, or contradicts the
above, the request is treated as **not approved** and the runner
returns `mode="dry_run"`.

---

## 4. Hard Non-Goals (forbidden in this issue and the next issues)

The following are **explicitly forbidden** at the time of Stage 821
and remain forbidden in any follow-up issue that touches this
contract. They are non-goals, not "we'll add them later". Each item
is listed separately so it can be cross-referenced in PR review:

- **No live validation in this issue.** Stage 821 does not run
  any real network call, fetch, provider, or LLM. The runner
  remains a dry-run surface.
- **No network.** No outbound network call, no inbound listener,
  no socket bind, no port open. `requests`, `httpx`, `urllib`,
  and friends are not imported.
- **No API.** No public API endpoint, no serverless function, no
  webhook receiver, no HTTP route is added to the runner.
- **No Firecrawl.** No Firecrawl SDK, no Firecrawl-style crawl
  payload, no Firecrawl envelope in the result.
- **No live LLM.** No real LLM provider SDK. `llm_provider` is
  pinned to `"stub"`; no OpenAI / Anthropic / other SDK import.
- **No LLM.** No LLM provider SDK at all (alias of the rule above
  for grep-able coverage).
- **No provider.** No third-party provider SDK is wired in. The
  runner is provider-agnostic at the seam; the seam itself is
  always an injected stub in this stage.
- **No browser.** No Playwright, no Selenium, no headless
  browser launch.
- **No crawler.** No Crawl4AI, no Scrapy, no provider crawl SDK.
- **No subprocess.** No `subprocess` import, no shell exec, no
  process group management from the runner / guard / seam.
- **No thread.** No `threading` import, no background worker, no
  daemon thread.
- **No asyncio.** No `asyncio` import, no coroutine, no event
  loop from the runner / guard / seam.
- **No concurrent.** No `concurrent.futures` import, no thread
  pool, no process pool.
- **No durable logging.** No file-based or networked logging may
  be added to the runner / guard / seam.
- **No scenario persistence.** `persist_scenarios` is pinned to
  `False` in the Stage #807 plan.
- **No cache persistence.** `persist_cache` is pinned to `False`.
- **No snapshot persistence.** `persist_snapshots` is pinned to
  `False`.
- **No config persistence.** `persist_config` is pinned to
  `False`.
- **No source-grounding persistence.** `persist_source_grounding`
  is pinned to `False`.
- **No persistence.** No scenario / snapshot / cache / config /
  source-grounding persistence at all (alias of the rules above
  for grep-able coverage).
- **No automatic promotion.** A successful future execution does
  NOT trigger any merge, deploy, or config change.
- **No public endpoint.** The runner / guard must not be exposed
  via any HTTP handler, websocket, serverless function, or other
  network-reachable surface in this issue.
- **No `scripts/run_all_demos.py` live conversion.** That script
  must continue to operate without any controlled-live execution
  path added to it.

If a follow-up issue needs to amend any of the above, it must
explicitly retract this section and pass review.

---

## 5. Safe Result Envelope (Stage #806 four states)

The runner MUST normalize any future seam output to one of the
following four closed-vocabulary states. The four states are
mutually exclusive and exhaustive for the result envelope:

| `answer_status`         | `ok`   | `answer_ok` | `source_weak` | Meaning |
| ----------------------- | ------ | ----------- | ------------- | ------- |
| `answered_with_evidence` | `true` | `true`      | `false`       | Both the seam's `ok` and `answer_ok` are strictly `True`, `answer_markdown` is a nonblank string, and at least one source has both a valid `id` (nonblank str or non-bool int) and a valid `url` (nonblank str, with URL userinfo stripped). |
| `fallback_no_match`     | `true` | `false`     | `true`        | The seam's `ok` is strictly `True`, but at least one of the other three evidence conditions is missing (no valid sources, blank / non-string `answer_markdown`, or `answer_ok != True`). |
| `fallback_unavailable`  | `false`| `false`     | `true`        | The seam raised `TimeoutError`. `fetch_diagnostic = {"category": "timeout"}`. |
| `error`                 | `false`| `false`     | `true`        | Any other failure mode: the seam raised a generic exception, returned `ok != True` (including `False`, missing key, non-bool truthy values such as `"true"`, `1`, `None`), returned a non-dict, or no seam was injected under an approved guard. |

The runner MUST return:

- `ok=True` only when `answer_status="answered_with_evidence"`.
- `ok=False` for all other three states.
- `answer_ok` equal to `answer_status == "answered_with_evidence"`.
- `source_weak=True` for all non-evidence states.
- `sources` non-empty and with `id` + `url` only when evidence;
  `[]` otherwise.
- `fetch_diagnostic` carrying only the closed-vocab
  `{"category": "..."}` field; `message`, `headers`, `body`, and
  any other arbitrary fields are dropped.

---

## 6. Leak Prevention

The runner / guard / seam MUST never place the following into any
log, result, error message, exception text, repr, doc example, or
documentation snippet that leaves the validation envelope:

- **raw question** — the user question as supplied to the runner.
- **exception** — the original exception type or message raised by
  the seam. Only the closed-vocab status code survives.
- **URL credentials** — any `user:pass@` segment in a URL.
- **userinfo** — any userinfo portion of a URL.
- **headers** — any HTTP / API header, including `Authorization`,
  `Cookie`, `X-Api-Key`, etc.
- **body** — any request / response body, including payloads that
  may carry an API key.
- **Bearer token** — any `Bearer ...` token string.
- **API key** — any string that resembles an API key.
- **provider payload** — any provider-specific envelope (Firecrawl,
  LLM, crawl SDK, etc.).

In code, the runner enforces this via:

- `_strip_url_userinfo(url)` — strips `user:pass@` from any URL
  before it enters the response.
- `_safe_source_item(item)` — drops any source missing both
  a valid `id` AND a valid nonblank `url`, and keeps only those
  two fields.
- `_safe_diagnostic(value)` — keeps only the `category` field
  from `fetch_diagnostic` and discards `message`, `headers`, and
  any other arbitrary key.
- Try/except wrappers around the seam call — the original
  exception is caught and the envelope is built from a closed
  vocabulary. The original message is never propagated.

In documentation and examples, the rule is identical: canary
strings (Bearer tokens, `Authorization: ...`, URL userinfo,
header-like strings, body-like strings) MUST NOT appear in any
log line, example, or contract snippet in this repository.

---

## 7. Future Execution Request Template (placeholder, NOT executable)

The template below shows the **exact shape** of a future request.
Every `<...>` placeholder is intentionally unfilled. This template
is a **non-executable** documentation artifact and MUST NOT be
treated as a runnable command.

```text
# docs/controlled-live-one-time-validation-contract.md — Template
# DO NOT EXECUTE. Placeholders only.

future_request = {
    "question":                 "<EXACT_QUESTION_NONBLANK_<=500_CHARS>",
    "site_id":                  "bukgu_gwangju",
    "fetch_provider":           "requests",
    "llm_provider":             "stub",
    "fetch_mode":               "subprocess_process_group",
    "expected_result_envelope": "<EXPECTED_STAGE_806_ENVELOPE_DICT>",
    "operator_acknowledgement": "I_ACKNOWLEDGE_CONTROLLED_LIVE",
    "rollback_procedure":       "<NO_PERSIST_TEXT_EXPLICITLY_STATING_cleanup>",
}
```

The template is intentionally **not** wired into the runner. Any
real future execution MUST:

1. Fill every `<...>` placeholder with a real, human-approved
   value.
2. Pass the request through `evaluate_command(...)` and confirm
   the resulting `CommandDecision.allowed is True`.
3. Inject a stub seam (`one_shot_runner=...`) and verify the
   contract end-to-end in tests.
4. Open a separate follow-up issue that explicitly retracts §4
   and §6 of this document and passes review.

Until all four steps above are met, the runner MUST continue to
return `mode="dry_run"` for any request, including requests that
fully match the template.

---

## 8. Cross-References

- `docs/product/bukgu-controlled-live-smoke-approval-packet.md` —
  Stage 417 approval/preflight packet; required reading before any
  real controlled validation may be considered.
- `docs/product/bukgu-local-first-controlled-live-smoke-plan.md` —
  Stage 415 bounded plan surface; provides the field-level
  allowlist that this contract references.
- `docs/operator-controlled-retrieval-gap-validation.md` —
  operator-side quickstart; explains operator-driven promotion
  flow.
- `src/demo/controlled_live_ux_runner.py` — current dry-run
  surface; **not** modified by this issue.
- `src/demo/controlled_live_command_guard.py` — current
  no-live approval gate; **not** modified by this issue.
- `src/demo/controlled_live_smoke_contract.py` — Stage #807
  bounded plan surface; **not** modified by this issue.

---

## 9. Validation

This contract is locked by:

- `tests/test_controlled_live_one_time_validation_contract.py` —
  pin-tests the required fields, non-goals, Stage #806 statuses,
  no-leak rules, and `scripts/run_all_demos.py` non-modification.
- AST scan of the runner / guard / seam modules — verifies the
  forbidden import set is not widened by any future PR that
  touches this contract.
