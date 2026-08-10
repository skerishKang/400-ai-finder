# MVP AI Runtime Contract

Status: **canonical operational contract**

Related canonical site-fidelity invariant: [`docs/product/exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md).

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
| non-JSON media type | 415 | `ok:false`, `failure_code:"unsupported_media_type"` |
| request body exceeds configured byte cap | 413 | `ok:false`, `failure_code:"payload_too_large"` |
| malformed JSON / invalid typed input | 200 | `ok:false`, `failure_code:"invalid_input"` |
| resident-ID-like or fully-redacted high-risk input | 200 | `ok:false`, `failure_code:"sensitive_input_rejected"` |
| missing/malformed/oversized Turnstile token on protected model path | 403 | `ok:false`, `failure_code:"bot_verification_required"` |
| rejected/expired/duplicate/action-mismatch/hostname-mismatch Turnstile result | 403 | `ok:false`, `failure_code:"bot_verification_failed"` |
| Turnstile Siteverify timeout/network/HTTP/malformed response | 503 | `ok:false`, `failure_code:"bot_verification_unavailable"` |
| required Turnstile server/client configuration missing | 503 | `ok:false`, `failure_code:"bot_verification_config_error"` |
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
- `unsupported_media_type`
- `payload_too_large`
- `sensitive_input_rejected`
- `bot_verification_required`
- `bot_verification_failed`
- `bot_verification_unavailable`
- `bot_verification_config_error`
- `service_disabled`
- `snapshot_only`

`error.retryable` is true only for `upstream_error`, `upstream_timeout`, and `bot_verification_unavailable`. Challenge-required, rejected, configuration, ingress, and privacy failures are not automatically retryable by the API contract.

#1224-A establishes the public request-ingress boundary:

- `Content-Type` must be `application/json`;
- the default application body limit is 8,192 bytes; `MVP_MAX_BODY_BYTES` may override it only within 1,024..32,768 bytes and invalid values fall back to 8,192;
- `Content-Length` is rejected before body read when it already exceeds the cap; streamed request bodies are cancelled as soon as accumulated bytes exceed the cap;
- the separate semantic question limit remains 300 characters;
- the accepted top-level request fields are `question`, optional `locale`, optional `session_id`, and optional `turnstile_token`;
- `session_id` is a pseudonymous correlation/rate-limit input, not authentication, and its raw value is not emitted in runtime metadata/logs;
- resident-ID-like input fails closed before provider execution; phone/email/precise-address-like spans are redacted before provider execution.

#1224-B establishes the protected-model bot-verification boundary:

- normal production/default mode is `required`; an invalid or missing mode also fails closed to `required`;
- `MVP_TURNSTILE_MODE=disabled` is honored only for exact loopback development/test hosts and cannot disable production verification;
- the browser obtains the public site key/action from same-origin `/api/mvp/turnstile-config`; the secret is never returned to the browser;
- each protected model request obtains a fresh challenge token and sends it only as `turnstile_token` in the request body;
- the server verifies that token with Cloudflare Siteverify before any provider call, checks the expected action, and checks an exact hostname allowlist when configured;
- resident-ID-like/high-risk privacy rejection runs **before** Siteverify, so rejected sensitive input causes zero Siteverify/provider calls;
- `snapshot_only`, AI-disabled, and all-provider-disabled paths do not perform protected model work and remain free of Turnstile/provider calls;
- Siteverify receives only the server secret and challenge response in the current implementation; resident question text, anonymous session ID, and `remoteip` are not forwarded;
- challenge token/secret values are not copied into response metadata or runtime logs;
- Siteverify uses the existing deadline-aware outbound fetch helper and is capped by both `MVP_TURNSTILE_TIMEOUT_MS` (default 3,000 ms, accepted 250..10,000 ms) and the remaining global request deadline;
- production activation requires an actual Turnstile site key, encrypted secret, expected action, and exact allowed hostname configuration. Code merge/deploy must not precede that configuration because the production default is fail-closed.

The ingress/privacy and bot-verification mappings above are contract-tested offline. Later #1224 durable rate-limit, concurrency, provider budget, and infrastructure controls must add their own documented status + `failure_code` mappings before deployment.

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
- Turnstile Siteverify deadline: 3,000 ms;
- provider/request timeout overrides are bounded between 10 ms and 60,000 ms;
- Turnstile timeout override is bounded between 250 ms and 10,000 ms.

Provider and Siteverify fetches use the deadline-aware `AbortController` path. A provider deadline or exhausted overall provider budget produces `upstream_timeout`; fallback is attempted only while the total request budget remains. A Siteverify deadline/network failure produces `bot_verification_unavailable` and provider execution is not attempted.

Timeouts are explicitly represented in provider-attempt telemetry with `timed_out:true`. Turnstile verification status is represented separately in sanitized `meta.bot_defense` metadata and does not expose the challenge token or secret.

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
- sanitized privacy/bot-defense state;
- normalized token usage;
- explicit cost-unavailable state.

It MUST NOT include by default:

- resident question text;
- model answer text;
- provider raw response bodies;
- Turnstile challenge tokens or secret keys;
- anonymous session ID raw values;
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

Turnstile has a separate deployment/testing switch:

- `MVP_TURNSTILE_MODE=required` — canonical production/default behavior;
- `MVP_TURNSTILE_MODE=disabled` — accepted only on exact loopback request hosts for local/offline testing.

The Turnstile switch is not a production emergency bypass. Production `disabled` is rejected and resolves to required verification.

## 9. Change review checklist

Any PR changing `/api/mvp/ask` public/runtime semantics must answer:

1. Does the response schema add/remove/rename/retype a field?
2. Does `failure_code` or HTTP status meaning change?
3. Does system/corrective prompt behavior materially change?
4. Does provider selection/fallback behavior change?
5. Does a new log field contain resident/model/provider raw content, anonymous session IDs, or challenge tokens?
6. Does token/cost reporting remain provider-reported or explicitly versioned?
7. Are browser bridge compatibility and failure envelopes preserved?
8. Are timeout, fallback, kill-switch, locale, privacy, and bot-verification contracts covered by offline tests?
9. If bot verification is enabled, are the site key, encrypted secret, expected action, and allowed deployment hostnames prepared before deployment?

Do not perform live provider/network validation merely to satisfy this checklist. Live validation requires its own controlled stage and explicit authorization.
