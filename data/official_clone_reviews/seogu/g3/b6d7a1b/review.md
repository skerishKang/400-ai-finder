# Seo-gu G3 Visual Polish — Source-vs-Clone Review Evidence

- Candidate commit (renderer candidate under review by this evidence): `b6d7a1bef43749057dbd3e5f314125ba61d13438`
- Stacked base: `feat/1312-seogu-g3-board-fidelity` @ `3a2dea0d901e39481cffd344514eff24b0d909bf` (PR #1313)
- Authoritative main: `d288c8453734a21759addc89259e9fa0ba35016b`
- G1 capture id: `20260812T231018-0900`
- Browser/tool: chromium `138.0.7204.23` (Playwright 1.53.0, headless, full-page screenshots)
- External network count (total across all states + interactions): `0` (expected 0)

> This evidence artifact set / evidence-only child commit does not promote the clone. Lifecycle gates remain closed: `visual_review=pending`, `owner_visual_approved=false`, `clone_mvp_ready=false`, `exact=false`, `golden=false`, `resident_default=false`, `production_ready=false`, `actual_site_integrated=false`, `asset_byte_fidelity_complete=false`.

## What this slice covers

The candidate adds P0/P1 presentation polish for the board list/detail six-state
slice on top of the #1312 board fidelity correction:

- Breadcrumb crumbs now render `›` separators (matching the source's visible
  `분야별정보 > 행정 > 행정소식 > 공지사항` hierarchy).
- Pager buttons render `«`/`‹` prefix and `›`/`»` suffix arrow glyphs.
- `새글` title marker is rendered as a bordered `.rc-new-badge` chip instead of
  plain text.
- List attachment indicator is rendered as a bordered `.rc-attach-indicator`
  chip.
- Detail prev/next rows are separated by a rule with consistent vertical padding.

All changes are CSS/HTML-only in `reference_clone_renderer.py`; no
architectural, semantic, or board-data-model changes. No site-specific literal
was introduced (renderer stays generic and model-driven).

## Lifecycle (rendered `rc-lifecycle` JSON-LD, #1313 board six-state slice)

| marker | value |
|---|---|
| `visual_review` | `pending` |
| `clone_mvp_ready` | `False` |
| `resident_default` | `False` |
| `exact` | `False` |
| `golden` | `False` |
| `actual_site_integrated` | `False` |
| `production_ready` | `False` |
| `asset_byte_fidelity_complete` | `False` |
| `faithful_clone_candidate` | `False` |

## Modeled contract (clone offline QA — NOT source parity)

These results describe the **clone's own** route/browser behavior as verified by
the offline interaction evidence. They are intentionally kept separate from
source parity and MUST NOT be reused as source-vs-clone PASS.

- `route_browser`: PASS
- `gnb_interaction`: PASS
- `list_detail_nav`: PASS
- `inert_attachment`: PASS
- `overflow`: PASS
- `focus`: PASS

## Source parity (G1 committed evidence grounded)

structural / content / asset / interaction_navigation / responsive / a11y /
visual are assessed against the **committed G1 source** evidence only.
`NOT_ASSESSED` = insufficient committed source-vs-clone comparison evidence
(fail-closed; no PASS claimed). `DIFFER` = source demonstrably richer than the
modeled clone. `FAIL` = known defect. This matrix is NOT an auto-approval:
`visual_review` stays `pending`.

| # | state_id | viewport | clone route | ext.req | structural | content | asset | interaction_nav | responsive | a11y | visual |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `notice.list.desktop` | 1440x900 | `/seogu/notice/` | 0 | NOT_ASSESSED | NOT_ASSESSED | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 2 | `notice.detail.desktop` | 1440x900 | `/seogu/notice/detail/` | 0 | NOT_ASSESSED | DIFFER | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 3 | `gosi.list.desktop` | 1440x900 | `/seogu/gosi/` | 0 | NOT_ASSESSED | NOT_ASSESSED | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 4 | `gosi.detail.desktop` | 1440x900 | `/seogu/gosi/detail/` | 0 | NOT_ASSESSED | NOT_ASSESSED | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 5 | `civil_form.list.desktop` | 1440x900 | `/seogu/civil-form/` | 0 | NOT_ASSESSED | NOT_ASSESSED | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 6 | `civil_form.detail.desktop` | 1440x900 | `/seogu/civil-form/detail/` | 0 | NOT_ASSESSED | NOT_ASSESSED | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |

## Source parity per-state notes

### `notice.list.desktop` — `/seogu/notice/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/notice.list.desktop/source.png`), SHA-256 72690d6a8e1f7d42…, full-page dims 1440x1878.
- clone screenshot: local offline full-page at matched viewport, SHA-256 b778b807….
- side-by-side: `data/official_clone_reviews/seogu/g3/b6d7a1b/states/notice.list.desktop/side_by_side.png`, SHA-256 (in manifest).
- external network count: **0** (non-loopback requests aborted + counted).
- visual polish applied: breadcrumb `›` separators, pager arrows, `.rc-new-badge` chips, `.rc-attach-indicator` chips.

### `notice.detail.desktop` — `/seogu/notice/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1, SHA-256 e10df62680ea9926…, full-page dims 1440x3086.
- clone screenshot: local offline full-page at matched viewport, SHA-256 b5d99b0a….
- side-by-side: `data/official_clone_reviews/seogu/g3/b6d7a1b/states/notice.detail.desktop/side_by_side.png`.
- external network count: **0**.
- **KNOWN GAP (source richer than clone)**: Source body is the poster image (/upload/namo/images/000064/(홍보물)3차_참여청년_모집_웹포스터.jpg); the clone renders a bounded asset-gate placeholder because no image bytes are committed under #1234 — body content materially differs. Title, metadata, attachment and back-to-list hierarchy are source-backed. Unchanged from #1312.
- visual polish applied: detail meta band / prev-next separator rules.

### `gosi.list.desktop` — `/seogu/gosi/` @ 1440x900 (viewport)
- source PNG: canonical committed G1, SHA-256 61e9b804b0830da1…, full-page dims 1440x1877.
- clone screenshot: local offline full-page at matched viewport, SHA-256 5e97b23f….
- side-by-side: `data/official_clone_reviews/seogu/g3/b6d7a1b/states/gosi.list.desktop/side_by_side.png`.
- external network count: **0**.

### `gosi.detail.desktop` — `/seogu/gosi/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1, SHA-256 1680ea74bb151a2a…, full-page dims 1440x1814.
- clone screenshot: local offline full-page at matched viewport, SHA-256 f77eb950….
- side-by-side: `data/official_clone_reviews/seogu/g3/b6d7a1b/states/gosi.detail.desktop/side_by_side.png`.
- external network count: **0**.

### `civil_form.list.desktop` — `/seogu/civil-form/` @ 1440x900 (viewport)
- source PNG: canonical committed G1, SHA-256 ac6d1f985f2e1533…, full-page dims 1440x1850.
- clone screenshot: local offline full-page at matched viewport, SHA-256 d0823907….
- side-by-side: `data/official_clone_reviews/seogu/g3/b6d7a1b/states/civil_form.list.desktop/side_by_side.png`.
- external network count: **0**.

### `civil_form.detail.desktop` — `/seogu/civil-form/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1, SHA-256 1fdaaef5150af2e1…, full-page dims 1440x1642.
- clone screenshot: local offline full-page at matched viewport, SHA-256 e8b98db3….
- side-by-side: `data/official_clone_reviews/seogu/g3/b6d7a1b/states/civil_form.detail.desktop/side_by_side.png`.
- external network count: **0**.

## Source parity legend / closures

- **assets = FAIL**: `asset_byte_fidelity_complete=false` — the clone renders structural placeholders only; no real Seo-gu asset bytes (images/fonts/css) are fetched or committed. Holds for the #1313 six-state slice and is unchanged.
- **visual/material = DIFFER (expected G2-B)**: source is the real municipal site with full visual styling, photographs, fonts and iconography; clone is the modeled layout tokens plus the new polish. Unchanged status; `visual_review` stays `pending`.
- **modeled-contract PASS is NOT source-parity PASS**: the clone's own route/browser QA is reported in the 'Modeled contract' section above and must not be interpreted as source-vs-clone parity.

## Interaction evidence

GNB toggle (home `/`):
- initial aria-expanded: `false`
- after click: `true`, mega-menu visible: `True`
- after Escape: `false` (closes)

List -> detail local navigation (attachments remain inert):
| family | list->detail link present | landed on detail | content marker present | attachments inert |
|---|---|---|---|---|
| `notice/` | True | True | True | True |
| `gosi/` | False | None | True | True |
| `civil-form/` | True | True | True | True |

Horizontal overflow (require <= 1px):
- 1440x900: `0px`
- 390x844: `0px`
- keyboard focus active element: `rc-gnb-toggle` (expect `rc-gnb-toggle`)

## Exceptions (fail-closed on promotion readiness)

- `asset_byte_fidelity_complete=false` — affects the #1313 board six-state slice. The G2-B candidate intentionally renders structural placeholders and does NOT bind real Seo-gu asset bytes. Asset PASS must NOT be claimed until asset bytes are resolved and the lifecycle marker flips to `true`.
- `visual_review=pending` / `owner_visual_approved=false` — side-by-side evidence is provided for owner visual approval only; no automated visual pass is asserted.
- In-scope known material gap (notice.detail) is reported as source-parity `content=DIFFER` (source body poster image vs the bounded asset-gate placeholder, #1234) with an explicit exception/reason; it is NOT source-parity PASS. All other states in the slice are `NOT_ASSESSED` (insufficient committed automated comparison evidence, fail-closed).

## Scope / non-mutation statement

- G1 canonical capture bytes: UNCHANGED (SHA-256 verified each state).
- This evidence-only child commit does NOT modify the renderer, G2-A semantic model, visual contract, or tests beyond the renderer polish committed in `b6d7a1b`.
- No live recapture of the Seo-gu site; source side is the committed G1 PNG.
- No production/Cloudflare/DB mutation; no actual site integration.
