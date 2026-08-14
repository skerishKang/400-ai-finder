# Seo-gu G3 Phase 1 — Source-vs-Clone Review Evidence

- Candidate commit (renderer candidate under review by this evidence): `23e087439917aa132c638e4cf06b70bc59f59594`
- Authoritative main: `178dc3a7759e168c626b052c12f8ed819bfe8c5b`
- G1 capture id: `20260812T231018-0900`
- Browser/tool: chromium `145.0.7632.116` (Playwright 1.53.0, headless, full-page screenshots)
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
| 2 | `notice.detail.desktop` | 1440x900 | `/seogu/notice/detail/` | 0 | DIFFER | DIFFER | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 3 | `gosi.list.desktop` | 1440x900 | `/seogu/gosi/` | 0 | NOT_ASSESSED | NOT_ASSESSED | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 4 | `gosi.detail.desktop` | 1440x900 | `/seogu/gosi/detail/` | 0 | DIFFER | DIFFER | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 5 | `civil_form.list.desktop` | 1440x900 | `/seogu/civil-form/` | 0 | NOT_ASSESSED | NOT_ASSESSED | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 6 | `civil_form.detail.desktop` | 1440x900 | `/seogu/civil-form/detail/` | 0 | DIFFER | DIFFER | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |

## Source parity per-state notes

### `notice.list.desktop` — `/seogu/notice/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/notice.list.desktop/source.png`), SHA-256 72690d6a8e1f7d42…, full-page dims 1440x1878.
- clone screenshot: local offline full-page at matched viewport, SHA-256 62eb95674b0c3a10….
- side-by-side: `data/official_clone_reviews/seogu/g3/23e087439917aa132c638e4cf06b70bc59f59594/states/notice.list.desktop/side_by_side.png`, SHA-256 b444776469a750ea….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`NOT_ASSESSED`, content=`NOT_ASSESSED`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- source parity structural/content = NOT_ASSESSED: committed automated source-vs-clone comparison evidence is insufficient; no PASS is claimed (fail-closed). Owner visual review pending.

### `notice.detail.desktop` — `/seogu/notice/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/notice.detail.desktop/source.png`), SHA-256 e10df62680ea9926…, full-page dims 1440x3086.
- clone screenshot: local offline full-page at matched viewport, SHA-256 32918562cdf959db….
- side-by-side: `data/official_clone_reviews/seogu/g3/23e087439917aa132c638e4cf06b70bc59f59594/states/notice.detail.desktop/side_by_side.png`, SHA-256 0d266a7aed3954c5….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`DIFFER`, content=`DIFFER`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- **KNOWN GAP (source richer than clone)**: Source renders the full 공고문 article body, attachments and metadata; the clone models only the detail shell with inert attachments.

### `gosi.list.desktop` — `/seogu/gosi/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/gosi.list.desktop/source.png`), SHA-256 61e9b804b0830da1…, full-page dims 1440x1877.
- clone screenshot: local offline full-page at matched viewport, SHA-256 0112279e644c959f….
- side-by-side: `data/official_clone_reviews/seogu/g3/23e087439917aa132c638e4cf06b70bc59f59594/states/gosi.list.desktop/side_by_side.png`, SHA-256 f6e9af5202befb8a….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`NOT_ASSESSED`, content=`NOT_ASSESSED`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- source parity structural/content = NOT_ASSESSED: committed automated source-vs-clone comparison evidence is insufficient; no PASS is claimed (fail-closed). Owner visual review pending.

### `gosi.detail.desktop` — `/seogu/gosi/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/gosi.detail.desktop/source.png`), SHA-256 1680ea74bb151a2a…, full-page dims 1440x1814.
- clone screenshot: local offline full-page at matched viewport, SHA-256 83bfd7299b54436c….
- side-by-side: `data/official_clone_reviews/seogu/g3/23e087439917aa132c638e4cf06b70bc59f59594/states/gosi.detail.desktop/side_by_side.png`, SHA-256 b6220127f9c120c1….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`DIFFER`, content=`DIFFER`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- **KNOWN GAP (source richer than clone)**: Source renders the full 고시/공고 notice body and metadata; the clone models only the detail shell.

### `civil_form.list.desktop` — `/seogu/civil-form/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/civil_form.list.desktop/source.png`), SHA-256 ac6d1f985f2e1533…, full-page dims 1440x1850.
- clone screenshot: local offline full-page at matched viewport, SHA-256 fe47eb4ba0fc85f0….
- side-by-side: `data/official_clone_reviews/seogu/g3/23e087439917aa132c638e4cf06b70bc59f59594/states/civil_form.list.desktop/side_by_side.png`, SHA-256 0fa0c123beb38443….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`NOT_ASSESSED`, content=`NOT_ASSESSED`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- source parity structural/content = NOT_ASSESSED: committed automated source-vs-clone comparison evidence is insufficient; no PASS is claimed (fail-closed). Owner visual review pending.

### `civil_form.detail.desktop` — `/seogu/civil-form/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/civil_form.detail.desktop/source.png`), SHA-256 1fdaaef5150af2e1…, full-page dims 1440x1642.
- clone screenshot: local offline full-page at matched viewport, SHA-256 3fd2c2de127488e0….
- side-by-side: `data/official_clone_reviews/seogu/g3/23e087439917aa132c638e4cf06b70bc59f59594/states/civil_form.detail.desktop/side_by_side.png`, SHA-256 81829dea56cce539….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`DIFFER`, content=`DIFFER`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- **KNOWN GAP (source richer than clone)**: Source renders the full 민원서식 form/document content; the clone models only the detail shell.

## Source parity legend / closures

- **assets = FAIL**: `asset_byte_fidelity_complete=false` — the clone renders structural placeholders only; no real Seo-gu asset bytes (images/fonts/css) are fetched or committed. This holds for all six states in this #1312 slice and is unchanged.
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

- `asset_byte_fidelity_complete=false` — affects all six states in this #1312 slice. The G2-B candidate intentionally renders structural placeholders and does NOT bind real Seo-gu asset bytes. Asset PASS must NOT be claimed until asset bytes are resolved and the lifecycle marker flips to `true`.
- `visual_review=pending` / `owner_visual_approved=false` — side-by-side evidence is provided for owner visual approval only; no automated visual pass is asserted.
- Known material gaps (notice.detail, gosi.detail, civil_form.detail) are reported as source-parity `DIFFER` (source richer than the modeled clone) with an explicit exception/reason; they are NOT source-parity PASS. The three list states (notice.list, gosi.list, civil_form.list) are `NOT_ASSESSED` (insufficient committed comparison evidence, fail-closed).

## Scope / non-mutation statement

- G1 canonical capture bytes: UNCHANGED (SHA-256 verified each state).
- This evidence-only child commit does not modify the renderer (`src/official_clone/reference_clone_renderer.py`), `visual_contract.py`, the G2-A semantic model, or tests. PR #1313 as a whole does contain renderer/test changes relative to main (`178dc3a`); only this child commit is evidence-only.
- No live recapture of the Seo-gu site; source side is the committed G1 PNG.
- No production/Cloudflare/DB mutation; no actual site integration.
