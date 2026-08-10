# MVP AI Runtime Contract

Status: **canonical operational contract**

This document defines the public/runtime compatibility boundary for the Cloudflare Pages Function at `POST /api/mvp/ask`. It covers schema/version metadata, failure semantics, provider-attempt telemetry, privacy-safe structured logging, runtime kill switches, and token/cost reporting.

It does **not** authorize live provider testing, live official-site retrieval, or storage of resident prompts/responses.

## 1. Version fields

Every JSON response decorated by the runtime control layer carries:

- `schema_version`: shape/compatibility version of the response contract;
- `policy_version`: server-side safety/selection policy version;
- `prompt_version`: system/corrective prompt contract version;
- `request_id`: per-request opaque correlation identifier.

The same version values are repeated inside `meta` where relevant to operator diagnostics. The browser bridge may preserve only sanitized `request_id` and `schema_version`; it does not expose internal failure diagnostics by default.

### Compatibility rules

Current schema version: `1.0`.

Within the current schema line:

- additive fields are backward-compatible;
- clients MUST ignore unknown fields;
- optional telemetry may be absent or `null` when the provider/runtime did not report it;
- existing fields MUST NOT be silently renamed, removed, or change type/meaning.

A removal, rename, incompatible type change, or semantic reinterpretation requires an explicit schema migration and version change. During a migration, the old and new representation must coexist for a defined transition window or the dependent client must be migrated in the same reviewed change.

`policy_version` and `prompt_version` are operational versions, not client feature-negotiation signals. They change when safety/provider-selection policy or prompt semantics materially change, even when the response shape remains compatible.

## 2. HTTP and failure semantics

The current contract intentionally preserves legacy HTTP behavior while making failure meaning machine-readable.

| Situation | HTTP | JSON contract |
| --- | ---: | --- |
| `OPTIONS` | 200 | empty response with restricted CORS headers |
| unsupported HTTP method | 405 | `ok:false` |
| missing/blank question | 400 | `ok:false` |
| malformed JSON / invalid typed input | 200 | `ok:false`, `failure_code:"invalid_input"` |
| provider/config/runtime failure | 200 | `ok:false`, stable `failure_code` |
| successful answer | 200 | `ok:true`, `failure_code:""` |

Current runtime failure-code vocabulary includes:

- `config_error`
- `upstream_error`
- `upstream_timeout`
- `malformed_response`
- `empty_response`
- `answer_locale_mismatch`
- `invalid_input`
- `service_disabled`
- `snapshot_only`

`error.retryable` is currently true only for `upstream_error` and `upstream_timeout`.

Future public-API controls such as media-type/body-byte rejection, rate limiting, challenge verification, or infrastructure-unavailable responses are owned by #1224. If they introduce 4xx/5xx statuses, the corresponding status + `failure_code` mapping must be documented and contract-tested before deployment.

## 3. Request and correlation identity

The Function generates a new opaque `request_id` for each request and returns it in both:

- `X-Request-ID` response header;
- response JSON `request_id`.

The browser bridge accepts a sanitized identifier from either location. If both header and body IDs exist but disagree, the bridge fails closed and exposes an empty request ID.

Cloudflare `CF-Ray`, when present and syntactically safe, is retained only as `meta.correlation_id` / operator-log correlation metadata.

Neither identifier is derived from resident content.

## 4. Deadlines and timeout semantics

Defaults:

- total request deadline: 20,000 ms;
- per-provider deadline: 8,000 ms;
- overrides are bounded between 10 ms and 60,000 ms.

Provider fetches use `AbortController`. A provider deadline or exhausted overall deadline produces `upstream_timeout`; fallback is attempted only while the total request budget remains.

Timeouts are explicitly represented in provider-attempt telemetry with `timed_out:true`.

## 5. Provider-attempt telemetry

Each attempted provider call records a sanitized event with:

- `ordinal`
- `provider`
- `model`
- `attempt` (`primary` or `locale_correction`)
- `outcome`
- `timed_out`
- `selected`
- `selection_reason`
- `latency_ms`
- `timeout_ms`
- normalized `token_usage` when reported
- `cost_status`
- `estimated_cost_usd`

Selection reasons currently include:

- `primary_provider`
- `provider_fallback`
- `corrective_retry`
- `provider_fallback_corrective_retry`
- `locale_mismatch_rejected` for a non-selected locale-mismatched attempt

A locale-mismatched provider response is not recorded as a successful selected attempt merely because the HTTP/provider call succeeded.

## 6. Token and cost semantics

Provider token usage is normalized only from provider-reported non-negative safe integers. Supported normalized fields are:

- `input_tokens`
- `output_tokens`
- `total_tokens`
- `reasoning_tokens`
- `cached_tokens`
- `tool_use_tokens`

Arbitrary provider usage objects, modality arrays, or raw billing structures are not copied into the public/operator contract.

The runtime does **not** hard-code provider prices and does not infer cost from an unversioned external price table. Until an explicitly versioned operator pricing/billing source is implemented:

```json
{
  "status": "unavailable",
  "estimated_usd": null,
  "reason": "provider_cost_not_reported"
}
```

is the canonical cost state. `null` means unavailable, not zero cost.

## 7. Structured logging and privacy

Runtime structured logs are enabled by default and can be suppressed for controlled tests with `MVP_RUNTIME_LOGS=0`.

The emitted `mvp_ai_request` event is allowlist-built. It may contain:

- request/correlation IDs;
- schema/policy/prompt versions;
- success/failure code;
- selected provider/model and selection reason;
- latency;
- AI runtime mode;
- sanitized provider-attempt metadata;
- normalized token usage;
- explicit cost-unavailable state.

It MUST NOT include by default:

- resident question text;
- model answer text;
- provider raw response bodies;
- API keys/secrets;
- arbitrary request body fields;
- arbitrary provider usage fields.

Logging failure is fail-soft: inability to write an operator log must not break the resident-facing response.

## 8. Runtime kill switches

`MVP_AI_MODE` supports:

- `enabled` — normal configured provider flow;
- `snapshot_only` — no model provider call; only canonical official snapshot metadata may be returned;
- `disabled` — all AI provider work stopped.

An invalid non-empty mode fails closed to `disabled`.

Provider-specific emergency switches:

- `MVP_DISABLE_GEMINI`
- `MVP_DISABLE_HY3`

Any non-empty value other than explicit `0` disables that provider. If all configured providers are disabled, the request fails closed without a provider fetch.

## 9. Change review checklist

Any PR changing `/api/mvp/ask` public/runtime semantics must answer:

1. Does the response schema add/remove/rename/retype a field?
2. Does `failure_code` or HTTP status meaning change?
3. Does system/corrective prompt behavior materially change?
4. Does provider selection/fallback behavior change?
5. Does a new log field contain resident/model/provider raw content?
6. Does token/cost reporting remain provider-reported or explicitly versioned?
7. Are browser bridge compatibility and failure envelopes preserved?
8. Are timeout, fallback, kill-switch, locale, and privacy contracts covered by offline tests?

Do not perform live provider/network validation merely to satisfy this checklist. Live validation requires its own controlled stage and explicit authorization.
