# Page Agent Server-Side Model Adapter

## Architecture

```
┌──────────────┐     same-origin POST      ┌───────────────────────────┐
│   Browser    │  ─────────────────────→   │  Cloudflare Pages Function │
│  (resident   │                           │  /api/page-agent/v1/       │
│   demo JS)   │  ←── OpenAI-compatible ── │  chat/completions.js       │
│              │      AgentOutput tool call │                           │
└──────────────┘                           │  ┌──────────┐  ┌────────┐ │
                                            │  │_policy.js│  │_adapter│ │
                                            │  │(policy + │  │.js     │ │
                                            │  │ schemas) │  │(logic) │ │
                                            │  └──────────┘  └───┬────┘ │
                                            │                     │      │
                                            │          exactly 1  │      │
                                            │          fetch     ↓       │
                                            │          [gemini | hy3]     │
                                            └───────────────────────────┘
```

The browser **never** receives a provider key. The `_adapter.js` module parses the
inbound PageAgent request, validates it against `_policy.js` constants, builds a
**new** provider payload, calls the configured provider exactly once (no retry),
validates the response, and emits a strictly validated `AgentOutput` tool call.

## Default mock path

| Condition            | Behaviour                        |
| -------------------- | -------------------------------- |
| No query parameter   | `resident-mock-model.js`         |
|                      | Same-origin `customFetch`        |
|                      | Zero external requests           |
|                      | Deterministic local mock         |

The 5 parity suggestions and the `done(success:false)` for unsupported prompts
continue to work exactly as before. The server adapter is opt-in only.

## Opt-in server path

| Condition                               | Behaviour                        |
| --------------------------------------- | -------------------------------- |
| `?page_agent_adapter=server`            | Same-origin `/api/page-agent/v1/chat/completions` |
| `?page_agent_adapter=server` + disabled | Safe `done(success:false)`       |
| No query / default                      | Local deterministic mock (unchanged) |

The browser opt-in is a **developer flag**, not a security boundary.  The real
security boundary is the server-side enable flag plus provider configuration.

## Endpoint

```
POST /api/page-agent/v1/chat/completions
```

Only same-origin requests from the browser are accepted.  The adapter reads
the PageAgent runtime's `{ messages, tools, tool_choice }` body, extracts the
`<user_request>` and `<browser_state>` from the last user message, validates
each, builds a NEW provider payload, and returns a validated OpenAI-compatible
tool-call response.

### Request schema (inbound)

```json
{
  "messages": [
    { "role": "system", "content": "..." },
    { "role": "user", "content": "<agent_state><user_request>...</user_request><browser_state>...</browser_state></agent_state>" }
  ],
  "tools": [
    {
      "type": "function",
      "function": { "name": "AgentOutput", "parameters": {} }
    }
  ],
  "tool_choice": { "type": "function", "function": { "name": "AgentOutput" } }
}
```

Only `AgentOutput` is accepted as the macro function name.  Any other name
returns 400.

### Response schema (outbound, OpenAI-compatible)

```json
{
  "id": "chatcmpl-page-agent-<timestamp>",
  "object": "chat.completion",
  "created": <unix>,
  "model": "page-agent-server-adapter",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_page_agent_<timestamp>",
            "type": "function",
            "function": {
              "name": "AgentOutput",
              "arguments": "{\"action\":{\"<actionName>\":{...}}}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ]
}
```

## Origin and CORS policy

The adapter is fail-closed on origin. Every request (both `POST` and `OPTIONS`
preflight) must carry an `Origin` header that passes `isAllowedOrigin`:

- `https://cgbukku.pages.dev` and any `https://<branch>.cgbukku.pages.dev`
  preview subdomain are accepted **only over HTTPS**. `http://` on the
  pages.dev host (production or preview) is rejected.
- `http://localhost` and `http://127.0.0.1` are accepted over HTTP only, with
  an (optionally empty) numeric port. Other hosts, credentials, paths, query
  strings, or hashes are rejected.
- A missing or invalid `Origin` returns `403 forbidden_origin` /
  `missing_origin`. An `OPTIONS` preflight with a missing/invalid origin is
  also rejected with `403`.
- The `Access-Control-Allow-Origin` response header is set by `corsHeaders()`:
  it reflects the request origin **only when that origin is itself allowed**,
  and otherwise defaults to the production origin. An attacker-controlled
  origin is therefore never reflected.

## Action allowlist

| Action                    | Schema                                                    |
| ------------------------- | --------------------------------------------------------- |
| `click_element_by_index`  | `{ "index": <integer> }`                                  |
| `scroll`                  | `{ "num_pages": <float> }` (clamped to ±5 pages)          |
| `done`                    | `{ "text": "<string>", "success": <boolean> }`            |

All other PageAgent actions (`input_text`, `select_option`, `go_to`,
`execute_javascript`, `wait`, etc.) are **rejected** by the validation gateway.
The adapter returns a safe `done(success:false)` so the browser loop
terminates gracefully.

### Target validation for `click_element_by_index`

A click action is only accepted when ALL of the following hold:

1.  `index` is a non-negative integer.
2.  An element at that index exists in the current `<browser_state>`.
3.  The element carries a `data-action-target` attribute.
4.  The target value matches one of the `SAFE_TARGET_PREFIXES`:
    - `nav-civil-service`
    - `nav-complaint-category`
    - `mayor-office-open`
    - `mayor-message-write`
    - `complaint-write`
    - `complaint-category-` (any category)
    - `mayor-receipt-home`
    - `apartment-guidance-card`
    - `apartment-life-card`
    - `bulky-waste-guidance-card`
    - `passport-guidance-card`
    - `unmanned-kiosk-card`
    - `complaint-illegal-parking-report`
    - `complaint-draft-review`
5.  The target does NOT contain any of the forbidden substrings:
    `submit`, `confirm-draft`, `login`, `auth`, `pay`, `payment`, `password`,
    `token`, `external`, `signup`, `sign-in`.
6.  The element's `href` (if present) must be **same-origin**. `#` and empty
    hrefs are allowed. Relative (`/path`) and absolute same-origin links are
    allowed. The comparison is **exact-origin** (scheme + host + port): a
    mismatched port or a different preview subdomain is rejected. The schemes
    `javascript:`, `data:`, `blob:`, `file:`, `mailto:`, `tel:`, and `about:`
    are always rejected.
7.  The element's text / type / target does not match
    `FORBIDDEN_ELEMENT_KEYWORDS` (`제출`, `로그인`, `결제`, `인증`, `외부`, etc.).

### `done` text validation

- Maximum 1000 characters.
- HTML / JavaScript injection rejected.
- Deceptive patterns rejected: `제출.*완료`, `신청.*완료`,
  `submitted successfully`, etc.

## Provider configuration

### Environment variables

| Variable                              | Purpose                            | Default                               |
| ------------------------------------- | ---------------------------------- | ------------------------------------- |
| `PAGE_AGENT_LLM_ENABLED`             | Master enable flag                 | *(absent)* = disabled                 |
| `PAGE_AGENT_LLM_PROVIDER`            | Provider: `gemini` or `hy3`       | *(none)*                              |
| `GEMINI_API_KEY`                     | Gemini API key (secret)            | *(none)*                              |
| `KILOCODE_API_KEY`                   | KiloCode API key (secret)          | *(none)*                              |
| `PAGE_AGENT_GEMINI_MODEL`            | Gemini model override               | `gemini-2.0-flash`                    |
| `PAGE_AGENT_HY3_MODEL`               | Hy3 model override                  | `tencent/hy3:free`                    |
| `PAGE_AGENT_LLM_TIMEOUT_MS`          | Per-step timeout                    | `15000` (max `30000`)                 |
| `PAGE_AGENT_LLM_MAX_OUTPUT_TOKENS`   | Max output tokens per call          | `600` (max `1000`)                    |
| `PAGE_AGENT_LLM_MAX_STEPS`           | Max Page Agent steps                | `8` (max `12`)                        |

### Default endpoints

| Provider | Endpoint                                                           |
| -------- | ------------------------------------------------------------------ |
| gemini   | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` |
| hy3      | `https://api.kilo.ai/api/gateway/v1/chat/completions`             |

Endpoint override variables `PAGE_AGENT_GEMINI_ENDPOINT` and
`PAGE_AGENT_HY3_ENDPOINT` are accepted **only** if the value is an HTTPS URL
with a hostname in the allowlist (`generativelanguage.googleapis.com`,
`api.kilo.ai`); otherwise the default is used.

### Disabled behaviour

When `PAGE_AGENT_LLM_ENABLED` is absent, `false`, or the provider/secret is
misconfigured, the adapter returns a safe `done(success:false)` with text
`"서버 모델이 비활성 상태입니다."` and makes **zero** upstream provider calls.

## Cost bounds

| Parameter                   | Default  | Absolute maximum |
| --------------------------- | -------- | ---------------- |
| Steps per request           | 8        | 12               |
| Upstream calls per request  | **1**    | 1                |
| Automatic retry             | 0        | 0                |
| Provider-fallback chain     | None     | None             |
| Timeout per call (ms)       | 15 000   | 30 000           |
| Max output tokens           | 600      | 1 000            |
| Max user request (chars)    | 300      | (same)           |
| Max browser state (chars)   | 40 000   | (same)           |
| Max request body (KiB)      | 96       | (same)           |

### Not implemented in Stage 4

- Global daily budget / cost cap. The stateless Function cannot enforce a
  reliable global limit. Use Cloudflare Rate Limiting, Access controls, or
  a Durable Object if needed.
- Per-user rate limiting. Same reason — stateless.
- Provider fallback chain. Exactly one provider per request.
- Provider retry on failure. Always exactly one attempt.

**Deployment controls**:
- Provider console quota (Gemini / Hy3 dashboard)
- Cloudflare Rate Limiting / Access / preview-only enablement
- Immediate rollback by setting `PAGE_AGENT_LLM_ENABLED=false` (no code deploy needed)

## PII / credential redaction

**Accuracy note (best-effort, not a guarantee)**: The adapter attempts to
block known high-risk PII patterns (resident registration numbers, card
numbers, account numbers, phone numbers, email addresses, password/auth
keywords) before provider invocation. Browser-state credentials and known
secret-bearing fields are redacted on a best-effort basis. These are defense-in-depth
filters, not a provable guarantee: arbitrary DOM content cannot be proven
PII-free, and novel PII shapes may not match the patterns.

### User request

The resident's free-text `<user_request>` is checked against
`USER_REQUEST_PII_PATTERNS` before the provider call. Matching patterns:

- Resident Registration Number (`\d{6}-\d{7}`)
- Card number (16 digits)
- Account number (`\d{3}-\d{4}-\d{4}`)
- Personal phone (`010-xxxx-xxxx`)
- Email address
- `비밀번호`, `password`, `인증번호`, `auth code`, `OTP`, API key / token
- `계좌번호`, `카드번호`, and explicit credential-input phrasing

If matched, the adapter returns `done(success:false)` with `pii_risk`
text and makes **zero** upstream calls.

### Browser state

Before forwarding the `<browser_state>` to the provider, the adapter:

- Strips `<input value="...">` attributes.
- Drops lines containing `type=password`, `token`, `cookie`,
  `authorization`, `autocomplete` with credential/cc values.
- Drops lines for `data-action-target="complaint-body"` (free-text input).

Public phone numbers, menu names, and department names are **not** redacted
(they are public DOM).

**Controlled live validation remains blocked pending explicit owner approval.**

## Logging policy

When `PAGE_AGENT_LLM_DEBUG=1` is set, the adapter logs a single JSON line per
request with **only** these fields:

```json
{
  "request_id": "...",
  "provider": "gemini",
  "model": "gemini-2.0-flash",
  "adapter_enabled": true,
  "result_category": "success|rejected|provider_error|disabled",
  "failure_code": "...",
  "duration_ms": 1234,
  "request_bytes": 5678,
  "step_number": 3,
  "validated_action_name": "click_element_by_index"
}
```

**Never logged**: raw user request, raw browser state, `messages`, `tools`
array, provider response body, API keys, stack traces, cookies, tokens,
input values, PII, or environment variable values.

## Rollback procedure

1.  Cloudflare Dashboard → Page Agent Functions → Environment variables.
2.  Set `PAGE_AGENT_LLM_ENABLED=false` and deploy.
3.  Zero upstream calls are made from that point on (the adapter returns
    safe `done(success:false)` immediately).
4.  If the environment change does not take effect immediately, revert the
    GitHub branch and redeploy.

## Controlled-live validation

The script `scripts/validate_page_agent_live_adapter.mjs` performs **offline fixture validation** of the adapter policy by reusing the same validation functions (`validateAction`, `validateProviderResponse`) that the actual server adapter uses. It validates that the policy correctly rejects dangerous actions (execute_javascript, go_to, input_text, select_option, unknown actions, multiple actions, invalid href protocol, external href) without making any live provider calls.

Gated behind:

```bash
RUN_PAGE_AGENT_LIVE_VALIDATION=1
```

No real submission, no external navigation, no provider secrets accessed.

## Known limitations (Stage 4)

| Limitation                                         | Rationale                                           |
| -------------------------------------------------- | --------------------------------------------------- |
| `input_text` / `select_option` / `go_to` fail-closed | Safe target vocabulary not established for parity surface; deferred to Stage 5 |
| `scroll` allowed numerically bounded only          | Conservative; no free-form scroll script            |
| No global daily budget                             | Stateless Function; Cloudflare Rate Limiting recommended |
| No provider fallback chain                         | Designed for repeatability: one provider per request |
| No user-level rate limiting                        | Stateless Function; Cloudflare Access recommended   |
| `data-action-target` allowlist limited to parity surface | Expanding requires explicit target review       |
