# Official home-route source inventory (capture-only)

Issue: #1160
Parent: #1080
Status: **capture_only** — not integrated into civic canvas; route remains `capture_required`.

## Source

- Requested URL: `https://bukgu.gwangju.kr/`
- Final resolved URL: `https://bukgu.gwangju.kr/`
- HTTP status: `200`
- Content-Type: `text/html;charset=UTF-8`
- Encoding: `utf-8`
- Official page title: `전남광주통합특별시 북구`
- Captured at: `2026-07-15T17:12:33+09:00`
- Source-visible update date: `not-shown-on-homepage-html`
- Raw SHA-256: `b47910217ecdb58b508cfd69d34a9a3a6e2c731f84a6db877ad01ebb04f5a6f5`
- Metadata SHA-256: `52aa1a64745d6f6d570f03ef38a245ba6ba0b2475fbe3e8bbf032783ac06df5d`

## Redirect chain

```json
[
  {
    "url": "https://bukgu.gwangju.kr/",
    "status": 200,
    "location": null
  }
]
```

## Inventory counts

- Navigation items: 722
- Blank labels (with explicit absence reason): 2
- Section counts: {'document': 210, 'footer': 147, 'header': 365}
- Assets listed: 174
- Asset type counts: {'css': 13, 'favicon': 2, 'image': 150, 'javascript': 9}
- Same-origin assets: 174
- External assets: 0
- Missing/failed probes: 0
- Partial-hash assets: 40

## Hierarchy (observed order)

- 1. header (header)
- 2. footer (footer)

## Method

Read-only Python `urllib` GET of the public homepage with manual redirect
recording and bounded approved same-origin asset probes.
No Firecrawl, provider API, login, form submission, payment, or PII.

## Sanitization

1. normalize CRLF and CR to LF
2. expand tabs to spaces
3. strip trailing whitespace per line
4. redact all session-bound `_csrf` meta/input values to `[REDACTED_SESSION_CSRF]`

Checksums and byte lengths are computed from the sanitized committed bytes only.

## Non-integration

This capture does **not**:

- change `home` route rendering
- change manifest status from `capture_required` to `exact`
- localize assets into `src/web/static`
- execute any official-site write action
