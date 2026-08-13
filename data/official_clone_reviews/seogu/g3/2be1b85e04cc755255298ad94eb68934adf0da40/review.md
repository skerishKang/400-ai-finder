# Seo-gu G3 Phase 1 — Source-vs-Clone Review Evidence

- Candidate commit (exact main): `2be1b85e04cc755255298ad94eb68934adf0da40`
- G1 capture id: `20260812T231018-0900`
- Browser/tool: chromium `138.0.7204.23` (Playwright 1.53.0, headless, full-page screenshots)
- External network count (total across all states + interactions): `0` (expected 0)

> This PR is EVIDENCE-ONLY. Lifecycle gates remain closed: `visual_review=pending`, `owner_visual_approved=false`, `clone_mvp_ready=false`, `exact=false`, `golden=false`, `resident_default=false`, `production_ready=false`, `actual_site_integrated=false`.

## Lifecycle (rendered `rc-lifecycle` JSON-LD, all 11 states)

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
| `faithful_clone_candidate` | `True` |

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
| 1 | `home.desktop.default` | 1440x900 | `/seogu/` | 0 | DIFFER | DIFFER | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 2 | `home.mobile.default` | 390x844 | `/seogu/home/mobile/` | 0 | DIFFER | DIFFER | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 3 | `home.desktop.gnb_open` | 1440x900 | `/seogu/home/gnb-open/` | 0 | DIFFER | DIFFER | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 4 | `notice.list.desktop` | 1440x900 | `/seogu/notice/` | 0 | NOT_ASSESSED | NOT_ASSESSED | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 5 | `notice.detail.desktop` | 1440x900 | `/seogu/notice/detail/` | 0 | DIFFER | DIFFER | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 6 | `gosi.list.desktop` | 1440x900 | `/seogu/gosi/` | 0 | NOT_ASSESSED | NOT_ASSESSED | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 7 | `gosi.detail.desktop` | 1440x900 | `/seogu/gosi/detail/` | 0 | DIFFER | DIFFER | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 8 | `civil_form.list.desktop` | 1440x900 | `/seogu/civil-form/` | 0 | NOT_ASSESSED | NOT_ASSESSED | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 9 | `civil_form.detail.desktop` | 1440x900 | `/seogu/civil-form/detail/` | 0 | DIFFER | DIFFER | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 10 | `organization.chart.desktop` | 1440x900 | `/seogu/organization/` | 0 | DIFFER | DIFFER | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |
| 11 | `staff.directory.desktop` | 1440x900 | `/seogu/staff/` | 0 | DIFFER | DIFFER | FAIL | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | DIFFER |

## Source parity per-state notes

### `home.desktop.default` — `/seogu/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/home.desktop.default/source.png`), SHA-256 e7533aed61bd4d05…, full-page dims 1440x2276.
- clone screenshot: local offline full-page at matched viewport, SHA-256 3fca778e1084911e….
- side-by-side: `data/official_clone_reviews/seogu/g3/2be1b85e04cc755255298ad94eb68934adf0da40/states/home.desktop.default/side_by_side.png`, SHA-256 7a526a23f6fdb65d….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`DIFFER`, content=`DIFFER`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- **KNOWN GAP (source richer than clone)**: Source home renders full real content (news, banners, menus, widgets); the clone models only the layout skeleton.

### `home.mobile.default` — `/seogu/home/mobile/` @ 390x844 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/home.mobile.default/source.png`), SHA-256 db7052c6d946d7fd…, full-page dims 390x3873.
- clone screenshot: local offline full-page at matched viewport, SHA-256 4b169918141746a3….
- side-by-side: `data/official_clone_reviews/seogu/g3/2be1b85e04cc755255298ad94eb68934adf0da40/states/home.mobile.default/side_by_side.png`, SHA-256 6e31f23c534b01aa….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`DIFFER`, content=`DIFFER`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- **KNOWN GAP (source richer than clone)**: Source mobile renders full responsive real content; the clone models only the layout skeleton at the mobile viewport.

### `home.desktop.gnb_open` — `/seogu/home/gnb-open/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/home.desktop.gnb_open/source.png`), SHA-256 8af9929cdf6c0976…, full-page dims 1440x2480.
- clone screenshot: local offline full-page at matched viewport, SHA-256 6341ab21377f5d35….
- side-by-side: `data/official_clone_reviews/seogu/g3/2be1b85e04cc755255298ad94eb68934adf0da40/states/home.desktop.gnb_open/side_by_side.png`, SHA-256 d27230c40d1eb2ce….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`DIFFER`, content=`DIFFER`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- **KNOWN GAP (source richer than clone)**: Source GNB/mega-menu open renders the full 전체메뉴 tree; the clone models only the GNB toggle/panel shell.

### `notice.list.desktop` — `/seogu/notice/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/notice.list.desktop/source.png`), SHA-256 72690d6a8e1f7d42…, full-page dims 1440x1878.
- clone screenshot: local offline full-page at matched viewport, SHA-256 f8078da69f2bebfd….
- side-by-side: `data/official_clone_reviews/seogu/g3/2be1b85e04cc755255298ad94eb68934adf0da40/states/notice.list.desktop/side_by_side.png`, SHA-256 fbb60b58e7102dce….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`NOT_ASSESSED`, content=`NOT_ASSESSED`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- source parity structural/content = NOT_ASSESSED: committed automated source-vs-clone comparison evidence is insufficient; no PASS is claimed (fail-closed). Owner visual review pending.

### `notice.detail.desktop` — `/seogu/notice/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/notice.detail.desktop/source.png`), SHA-256 e10df62680ea9926…, full-page dims 1440x3086.
- clone screenshot: local offline full-page at matched viewport, SHA-256 f587006e8d45648b….
- side-by-side: `data/official_clone_reviews/seogu/g3/2be1b85e04cc755255298ad94eb68934adf0da40/states/notice.detail.desktop/side_by_side.png`, SHA-256 2f19d24c95863694….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`DIFFER`, content=`DIFFER`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- **KNOWN GAP (source richer than clone)**: Source renders the full 공고문 article body, attachments and metadata; the clone models only the detail shell with inert attachments.

### `gosi.list.desktop` — `/seogu/gosi/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/gosi.list.desktop/source.png`), SHA-256 61e9b804b0830da1…, full-page dims 1440x1877.
- clone screenshot: local offline full-page at matched viewport, SHA-256 252d6563a99aaa0f….
- side-by-side: `data/official_clone_reviews/seogu/g3/2be1b85e04cc755255298ad94eb68934adf0da40/states/gosi.list.desktop/side_by_side.png`, SHA-256 12ba78462cc59a77….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`NOT_ASSESSED`, content=`NOT_ASSESSED`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- source parity structural/content = NOT_ASSESSED: committed automated source-vs-clone comparison evidence is insufficient; no PASS is claimed (fail-closed). Owner visual review pending.

### `gosi.detail.desktop` — `/seogu/gosi/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/gosi.detail.desktop/source.png`), SHA-256 1680ea74bb151a2a…, full-page dims 1440x1814.
- clone screenshot: local offline full-page at matched viewport, SHA-256 dda81c5e26a43502….
- side-by-side: `data/official_clone_reviews/seogu/g3/2be1b85e04cc755255298ad94eb68934adf0da40/states/gosi.detail.desktop/side_by_side.png`, SHA-256 dcf12e022c2bd8b5….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`DIFFER`, content=`DIFFER`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- **KNOWN GAP (source richer than clone)**: Source renders the full 고시/공고 notice body and metadata; the clone models only the detail shell.

### `civil_form.list.desktop` — `/seogu/civil-form/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/civil_form.list.desktop/source.png`), SHA-256 ac6d1f985f2e1533…, full-page dims 1440x1850.
- clone screenshot: local offline full-page at matched viewport, SHA-256 0e54ba622534909c….
- side-by-side: `data/official_clone_reviews/seogu/g3/2be1b85e04cc755255298ad94eb68934adf0da40/states/civil_form.list.desktop/side_by_side.png`, SHA-256 e0030b1c928da1f2….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`NOT_ASSESSED`, content=`NOT_ASSESSED`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- source parity structural/content = NOT_ASSESSED: committed automated source-vs-clone comparison evidence is insufficient; no PASS is claimed (fail-closed). Owner visual review pending.

### `civil_form.detail.desktop` — `/seogu/civil-form/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/civil_form.detail.desktop/source.png`), SHA-256 1fdaaef5150af2e1…, full-page dims 1440x1642.
- clone screenshot: local offline full-page at matched viewport, SHA-256 cd206edcf4c73dcb….
- side-by-side: `data/official_clone_reviews/seogu/g3/2be1b85e04cc755255298ad94eb68934adf0da40/states/civil_form.detail.desktop/side_by_side.png`, SHA-256 0b28ec12c7ecbe44….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`DIFFER`, content=`DIFFER`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- **KNOWN GAP (source richer than clone)**: Source renders the full 민원서식 form/document content; the clone models only the detail shell.

### `organization.chart.desktop` — `/seogu/organization/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/organization.chart.desktop/source.png`), SHA-256 66d3342691e0b0df…, full-page dims 1440x3025.
- clone screenshot: local offline full-page at matched viewport, SHA-256 d3a72957d0890198….
- side-by-side: `data/official_clone_reviews/seogu/g3/2be1b85e04cc755255298ad94eb68934adf0da40/states/organization.chart.desktop/side_by_side.png`, SHA-256 b85c835a5803010e….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`DIFFER`, content=`DIFFER`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- **KNOWN GAP (source richer than clone)**: Source renders the full 행정조직도 hierarchy (2실·1관·7국·1소·18동 with a nested department tree); the clone models only the top-level layout shell.

### `staff.directory.desktop` — `/seogu/staff/` @ 1440x900 (viewport)
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/staff.directory.desktop/source.png`), SHA-256 2b1762bdff2d7b20…, full-page dims 1440x1757.
- clone screenshot: local offline full-page at matched viewport, SHA-256 205db6eb3b45ea47….
- side-by-side: `data/official_clone_reviews/seogu/g3/2be1b85e04cc755255298ad94eb68934adf0da40/states/staff.directory.desktop/side_by_side.png`, SHA-256 803cd31fcb50a7af….
- external network count: **0** (non-loopback requests aborted + counted).
- source parity: structural=`DIFFER`, content=`DIFFER`, asset=`FAIL`, interaction_nav=`NOT_ASSESSED`, responsive=`NOT_ASSESSED`, a11y=`NOT_ASSESSED`, visual=`DIFFER`.
- **KNOWN GAP (source richer than clone)**: Source renders the full 직원 업무안내 staff directory with per-department personnel entries; the clone models only placeholder structure.

## Source parity legend / closures

- **assets = FAIL**: `asset_byte_fidelity_complete=false` — the clone renders structural placeholders only; no real Seo-gu asset bytes (images/fonts/css) are fetched or committed. This holds for all 11 states and is unchanged.
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
| `gosi/` | True | True | True | True |
| `civil-form/` | True | True | True | True |

Horizontal overflow (require <= 1px):
- 1440x900: `0px`
- 390x844: `0px`
- keyboard focus active element: `rc-gnb-toggle` (expect `rc-gnb-toggle`)

## Exceptions (fail-closed on promotion readiness)

- `asset_byte_fidelity_complete=false` — affects all 11 states. The G2-B candidate intentionally renders structural placeholders and does NOT bind real Seo-gu asset bytes. Asset PASS must NOT be claimed until asset bytes are resolved and the lifecycle marker flips to `true`.
- `visual_review=pending` / `owner_visual_approved=false` — side-by-side evidence is provided for owner visual approval only; no automated visual pass is asserted.
- Known material gaps (organization.chart, staff.directory, notice.detail, gosi.detail, civil_form.detail, home.desktop.default, home.mobile.default, home.desktop.gnb_open) are reported as source-parity `DIFFER` (source richer than the modeled clone) with an explicit exception/reason; they are NOT source-parity PASS. All other states are `NOT_ASSESSED` (insufficient committed comparison evidence, fail-closed).

## Scope / non-mutation statement

- G1 canonical capture bytes: UNCHANGED (SHA-256 verified each state).
- G2-B renderer (`src/official_clone/reference_clone_renderer.py`), `visual_contract.py`, G2-A semantic model: UNCHANGED in this PR.
- No live recapture of the Seo-gu site; source side is the committed G1 PNG.
- No production/Cloudflare/DB mutation; no actual site integration.
