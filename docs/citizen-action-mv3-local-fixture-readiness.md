# Citizen Action MV3 Local Fixture Readiness

## Scope of this Stage

This document describes the MV3 content-script transport/validation scaffold
for the `citizen-action-local-bridge` Chrome extension.

**Current capability**: This stage is a **local fixture transport/validation
scaffold only**. It does NOT:

- Execute any DOM click, scroll, route navigation, or draft prefill
- Interact with the Buk-gu administrative host
- Submit any form or upload any file
- Access browser storage (localStorage, sessionStorage, indexedDB, chrome.storage)
- Make any network requests (fetch, XMLHttpRequest, WebSocket)
- Access cookies, authentication state, or identity information
- Evaluate arbitrary code (eval, new Function, import())

## Canonical Static Server Path

The local fixture HTML entry point is served at:

```
http://localhost:8000/static/citizen-action-demo.html
```

The root path variant (`/citizen-action-demo.html`) is a compatibility
fixture path for local static-directory test servers that serve from the
project root rather than from `/static/`. It is not a general-purpose path
and is explicitly scoped to localhost/127.0.0.1 in the manifest matches.

## Architecture

```
Chrome Extension (MV3 content-script)
  └── protocol.js       — UMD module, closed-vocabulary message validation
  └── content-script.js — chrome.runtime.onMessage listener, fixture guard,
                           status marker, delegates to protocol.js
  NO background worker (service_worker)
  NO popup / options page
  NO web_accessible_resources
```

## Protocol Message Contract

Inbound message shape (exactly):

```js
{
  type: "CITIZEN_ACTION_BRIDGE_EXECUTE_V1",
  action: {
    action_type: string,          // 6 allowed types only
    route_id: string | null,      // route_id or null depending on action_type
    target_id: string | null,     // target_id or null depending on action_type
    explanation_id: string,       // closed vocabulary
    requires_user_confirmation: boolean,
    choice_ids: string[],         // must be empty []
  }
}
```

Accepted action types:

```
HIGHLIGHT_ALLOWLISTED_ELEMENT
SCROLL_TO_ALLOWLISTED_ELEMENT
OPEN_ALLOWLISTED_ROUTE
CLICK_ALLOWLISTED_ELEMENT
PREFILL_APPROVED_DRAFT
STOP_FOR_USER_CONFIRMATION
```

Blocked action types (non-negotiable):

```
ASK_CLARIFYING_QUESTION  — not exposed to content-script bridge
PRESENT_CHOICES           — not exposed to content-script bridge
LOGIN                     — forbidden
SUBMIT                    — forbidden
UPLOAD_FILE               — forbidden
PAY                       — forbidden
ENTER_IDENTITY            — forbidden
```

## No Raw Payload Fields

The protocol deliberately omits all raw/free-text fields:

- No `question`, `draft_text`, `answer`, `location`, `identity`
- No `text`, `content`, `message`, `body`
- No CSS selectors, xpath, or arbitrary strings

The bridge validates **symbolic action tokens** only. Actual content
rendering is handled by the local fixture HTML/JS on the same page,
which is isolated from the extension by the ISOLATED world.

## Allowed Host/Path Combinations (Manifest Matches)

Only the following 4 URL patterns are matched:

```
http://localhost/static/citizen-action-demo.html
http://127.0.0.1/static/citizen-action-demo.html
http://localhost/citizen-action-demo.html
http://127.0.0.1/citizen-action-demo.html
```

**Explicitly prohibited**:
- `<all_urls>` — never
- `https://*/*` — never
- `file://` — never
- Any actual municipal domain (e.g., `bukgu.go.kr`) — never in this stage
- Wildcard hosts (e.g., `http://*/*`) — never

## Future Authorized Municipal Pilot — Prerequisites

Before extending this scaffold to any live administrative host,
ALL of the following conditions must be met:

1. **Written domain authorization** — explicit written approval from the
   municipal authority for the specific origin(s) to be added
2. **Exact HTTPS origin allowlist** — only the exact authorized origins;
   no broad patterns
3. **Per-page DOM allowlist review** — every target DOM element ID
   must be reviewed and approved for the specific page
4. **Explicit user confirmation before any sensitive step** — any action
   that reveals personal information or triggers an external state change
   requires a dedicated user-visible confirmation dialog
5. **No login/upload/payment/identity/e-sign/final submit** — the bridge
   is scoped to read-only navigation guidance only
6. **Privacy and security review** — by qualified personnel before any
   pilot deployment
7. **Controlled validation and rollback plan** — ability to disable the
   extension instantly and verify no residual state

## Prohibited in This Stage

The following are explicitly prohibited for this stage and require a
separate security review and new issue before implementation:

```
- Adding any background / service worker
- Adding any storage capability (chrome.storage, localStorage, etc.)
- Adding any network capability (fetch, WebSocket, etc.)
- Adding any popup or options UI
- Adding any web_accessible_resources
- Changing manifest matches to any live domain
- Adding any telemetry or analytics
- Exposing any raw question/draft/identity fields
- Allowing LOGIN, SUBMIT, UPLOAD_FILE, PAY, ENTER_IDENTITY action types
- Supporting any CSS selector or xpath input
- Supporting any URL redirect or navigation outside closed route vocabulary
```

## Version

Document version: 0.1.0 (Stage #852 — spike/mv3-local-fixture-bridge)