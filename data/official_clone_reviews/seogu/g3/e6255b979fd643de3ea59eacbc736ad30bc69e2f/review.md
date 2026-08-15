# Seo-gu G3 Phase 1 — Source-vs-Clone Review Evidence

- Candidate commit (renderer candidate under review by this evidence): `e6255b979fd643de3ea59eacbc736ad30bc69e2f`
- Authoritative main: `2c18c74b22d6d95c143a1108a4c874c5e30460b0`
- G1 capture id: `20260812T231018-0900`
- Browser/tool: chromium `138.0.7204.23` (Playwright 1.53.0, headless, full-page screenshots)
- External network count (total across all states + interactions): `0` (expected 0)

> This evidence artifact set / evidence-only child commit does not promote the clone. Lifecycle gates remain closed: `visual_review=pending`, `owner_visual_approved=false`, `clone_mvp_ready=false`, `exact=false`, `golden=false`, `resident_default=false`, `production_ready=false`, `actual_site_integrated=false`, `asset_byte_fidelity_complete=false`.

## Lifecycle (rendered `rc-lifecycle` JSON-LD, #1312 board six-state slice)

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

These results describe the **clone's own** route/browser behavior as verified by the offline interaction evidence. They are intentionally kept separate from source parity and MUST NOT be reused as source-vs-clone PASS. (Requirement: modeled-contract PASS is not reused as source-parity PASS.)

- `route_browser`: PASS
- `gnb_interaction`: PASS
- `list_detail_nav`: PASS
- `inert_attachment`: PASS
- `overflow`: PASS
- `focus`: PASS

## Source parity (G1 committed evidence grounded)

structural / content / asset / interaction_navigation / responsive / a11y / visual are assessed against the **committed G1 source** evidence only. `NOT_ASSESSED` = insufficient committed source-vs-clone comparison evidence (fail-closed; no PASS claimed). `DIFFER` = source demonstrably richer than the modeled clone. `FAIL` = known defect. This matrix is NOT an auto-approval: `visual_review` stays `pending`.

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
- clone screenshot: local offline full-page at matched viewport, SHA-256 7cb8acf87e871077….
- side-by-side: `data/official_clone_reviews/seogu/g3/e6255b979fd643de3ea59eacbc736ad30bc69e2f/states/notice.list.desktop/side_by_side.png`, SHA-256 6bea41e6b008a6d0….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`NOT_ASSESSED`, content=`NOT_ASSESSED`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- source parity structural/content = NOT_ASSESSED: committed automated source-vs-clone comparison evidence is insufficient; no PASS is claimed (fail-closed). Owner visual review pending.

### `notice.detail.desktop` — `/seogu/notice/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/notice.detail.desktop/source.png`), SHA-256 e10df62680ea9926…, full-page dims 1440x3086.
- clone screenshot: local offline full-page at matched viewport, SHA-256 ffc05665b8ef4d56….
- side-by-side: `data/official_clone_reviews/seogu/g3/e6255b979fd643de3ea59eacbc736ad30bc69e2f/states/notice.detail.desktop/side_by_side.png`, SHA-256 abcadca62ebc4107….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`NOT_ASSESSED`, content=`DIFFER`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- **KNOWN GAP (source richer than clone)**: Source body is the poster image (/upload/namo/images/000064/(홍보물)3차_참여청년_모집_웹포스터.jpg); the clone renders a bounded asset-gate placeholder because no image bytes are committed under #1234 — body content materially differs. Title, metadata, attachment and back-to-list hierarchy are source-backed.

### `gosi.list.desktop` — `/seogu/gosi/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/gosi.list.desktop/source.png`), SHA-256 61e9b804b0830da1…, full-page dims 1440x1877.
- clone screenshot: local offline full-page at matched viewport, SHA-256 6303bf3792a45875….
- side-by-side: `data/official_clone_reviews/seogu/g3/e6255b979fd643de3ea59eacbc736ad30bc69e2f/states/gosi.list.desktop/side_by_side.png`, SHA-256 6da46e8bcbd43fdd….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`NOT_ASSESSED`, content=`NOT_ASSESSED`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- source parity structural/content = NOT_ASSESSED: committed automated source-vs-clone comparison evidence is insufficient; no PASS is claimed (fail-closed). Owner visual review pending.

### `gosi.detail.desktop` — `/seogu/gosi/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/gosi.detail.desktop/source.png`), SHA-256 1680ea74bb151a2a…, full-page dims 1440x1814.
- clone screenshot: local offline full-page at matched viewport, SHA-256 e5958e325d757403….
- side-by-side: `data/official_clone_reviews/seogu/g3/e6255b979fd643de3ea59eacbc736ad30bc69e2f/states/gosi.detail.desktop/side_by_side.png`, SHA-256 159e43eb50c81b7e….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`NOT_ASSESSED`, content=`NOT_ASSESSED`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- source parity structural/content = NOT_ASSESSED: committed automated source-vs-clone comparison evidence is insufficient; no PASS is claimed (fail-closed). Owner visual review pending.

### `civil_form.list.desktop` — `/seogu/civil-form/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/civil_form.list.desktop/source.png`), SHA-256 ac6d1f985f2e1533…, full-page dims 1440x1850.
- clone screenshot: local offline full-page at matched viewport, SHA-256 d2468ddb7c3e52f7….
- side-by-side: `data/official_clone_reviews/seogu/g3/e6255b979fd643de3ea59eacbc736ad30bc69e2f/states/civil_form.list.desktop/side_by_side.png`, SHA-256 aa411cac09c31f4e….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`NOT_ASSESSED`, content=`NOT_ASSESSED`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- source parity structural/content = NOT_ASSESSED: committed automated source-vs-clone comparison evidence is insufficient; no PASS is claimed (fail-closed). Owner visual review pending.

### `civil_form.detail.desktop` — `/seogu/civil-form/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/civil_form.detail.desktop/source.png`), SHA-256 1fdaaef5150af2e1…, full-page dims 1440x1642.
- clone screenshot: local offline full-page at matched viewport, SHA-256 811d4559df29bee1….
- side-by-side: `data/official_clone_reviews/seogu/g3/e6255b979fd643de3ea59eacbc736ad30bc69e2f/states/civil_form.detail.desktop/side_by_side.png`, SHA-256 fe6e42a65ae5f24a….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`NOT_ASSESSED`, content=`NOT_ASSESSED`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- source parity structural/content = NOT_ASSESSED: committed automated source-vs-clone comparison evidence is insufficient; no PASS is claimed (fail-closed). Owner visual review pending.

## Source parity legend / closures

- **assets = FAIL**: `asset_byte_fidelity_complete=false` — the clone renders structural placeholders only; no real Seo-gu asset bytes (images/fonts/css) are fetched or committed. This holds for the #1312 board six-state slice and is unchanged.
- **visual/material = DIFFER (expected G2-B)**: source is the real municipal site with full visual styling, photographs, fonts and iconography; clone is the modeled layout tokens only. Unchanged.
- **modeled-contract PASS is NOT source-parity PASS**: the clone's own route/browser QA (GNB toggle, list->detail, inert attachments, no overflow, focus) is reported in the 'Modeled contract' section above and must not be interpreted as source-vs-clone parity.

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

- `asset_byte_fidelity_complete=false` — affects the #1312 board six-state slice. The G2-B candidate intentionally renders structural placeholders and does NOT bind real Seo-gu asset bytes. Asset PASS must NOT be claimed until asset bytes are resolved and the lifecycle marker flips to `true`.
- `visual_review=pending` / `owner_visual_approved=false` — side-by-side evidence is provided for owner visual approval only; no automated visual pass is asserted.
- In-scope known material gap (notice.detail) is reported as source-parity `content=DIFFER` (source body poster image vs the bounded asset-gate placeholder, #1234) with an explicit exception/reason; it is NOT source-parity PASS. All other states in the #1312 board six-state slice are `NOT_ASSESSED` (insufficient committed automated comparison evidence, fail-closed).

## Scope / non-mutation statement

- G1 canonical capture bytes: UNCHANGED (SHA-256 verified each state).
- This evidence-only child commit does NOT modify the renderer, G2-A semantic model, visual contract, or tests. PR #1313 implementation itself contains renderer/model/visual-contract/test changes relative to main (the #1312 board fidelity correction); those changes are not part of this evidence artifact set.
- No live recapture of the Seo-gu site; source side is the committed G1 PNG.
- No production/Cloudflare/DB mutation; no actual site integration.
