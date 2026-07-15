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
- Captured at: `2026-07-15T16:53:08+09:00`
- Source-visible update date: `not-shown-on-homepage-html`
- Raw SHA-256: `e08513493f831b130f4f6775f0ecc585fbc029cb5e65aa2a55f0867b1281866e`
- Metadata SHA-256: `0aba72b62efc2283f9b7331cd30e7256f1cef65dee2f6adca80b37a3f2dc6a70`

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
- Section counts: {'document': 210, 'footer': 147, 'header': 365}
- Assets listed: 174
- Asset type counts: {'css': 13, 'favicon': 2, 'image': 150, 'javascript': 9}
- Same-origin assets: 174
- External assets: 0
- Missing/failed probes: 0

## Method

Read-only Python `urllib` GET of the public homepage and bounded public asset probes.
No Firecrawl, provider API, login, form submission, payment, or PII.

## Non-integration

This capture does **not**:

- change `home` route rendering
- change manifest status from `capture_required` to `exact`
- localize assets into `src/web/static`
- execute any official-site write action
