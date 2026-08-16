# Seo-gu G3 Visual Polish — Correction Review Evidence

- Candidate commit (renderer candidate under review by this evidence): `b0fe78e9c2836a46295668c6f6195b7fce79cd33`
- Stacked base: `feat/1312-seogu-g3-board-fidelity` @ `3a2dea0d901e39481cffd344514eff24b0d909bf` (PR #1313)
- Authoritative main: `d288c8453734a21759addc89259e9fa0ba35016b`
- G1 capture id: `20260812T231018-0900`
- Browser/tool: chromium `145.0.7632.116` (Playwright 1.61.0, headless, full-page screenshots)
- External network count (total across all states + interactions): `0` (expected 0)

> This evidence artifact set / evidence-only child commit does not promote the
> clone. Lifecycle gates remain closed: `visual_review=pending`,
> `owner_visual_approved=false`, `clone_mvp_ready=false`, `exact=false`,
> `golden=false`, `resident_default=false`, `production_ready=false`,
> `actual_site_integrated=false`, `asset_byte_fidelity_complete=false`.

## What this slice corrects (relative to the prior `b6d7a1b` polish)

The prior polish pass introduced several treatments that were **not** grounded
in the committed G1 source DOM. This correction removes them and restores
source-backed structure:

- **Breadcrumb separator removed.** The prior pass injected a literal `›`
  separator (`<span class="rc-crumb-sep" aria-hidden="true">›</span>`). The `›`
  glyph is not source-proven for the visible breadcrumb, so it is removed.
  The visible location hierarchy continues to render the source-backed
  `홈 → 구정소식 → 공지사항` trail. Critically, the source's
  `분야별정보 > 행정 > 행정소식 > 공지사항` string is a **blind (screen-reader
  only) search fieldset legend**, NOT a visible breadcrumb; it is not promoted
  into the visible navigation.
- **New-post marker restored to source DOM.** The prior bordered
  `.rc-new-badge` "새글" text chip is removed. The source DOM is
  `<i class="xi-new"></i><span class="sr_only">새글</span>` followed by the
  title. The `xi-new` glyph treatment depends on the XEIcon font whose body
  bytes are not materialized in the controlled clone asset set
  (TECHNICAL_CAPTURE_GAP), so only the source element + screen-reader "새글"
  label are emitted. No fabricated visible bordered chip.
- **List attachment chip removed.** The prior bordered `.rc-attach-indicator`
  "첨부 N" chip is removed. The source renders an attachment icon
  (e.g. `/upload/skin/board/basic/attach.png`) whose body bytes are not
  materialized (TECHNICAL_CAPTURE_GAP). The attachment **count semantics** are
  preserved via an `sr_only` label; no fake bordered chip and no external /
  relative asset URL is emitted (runtime external requests stay 0).
- **Pager glyphs removed.** The prior `«`/`‹` prefix and `›`/`»` suffix on the
  처음/이전/다음/마지막 pager buttons were invented (justified only by a generic
  "Korean public-sector pager convention", which is not source evidence). They
  are removed; the source-backed text labels 처음/이전/다음/마지막 remain, and
  the semantic first/prev/next/last functions are unchanged.
- **Detail prev/next arbitrary literals removed.** The `padding:12px 0`,
  `margin-right:8px`, and `border-bottom:1px solid #ddd` literals on the
  `.rc-prevnext` rows were not measured/provenance-bound and are removed; the
  source-backed row-separation structure (`<ul class="prevnext">` with
  `.prev`/`.next` items and 이전글/다음글 labels) is preserved.

All changes are CSS/HTML-only in `reference_clone_renderer.py`; no
architectural, semantic, or board-data-model changes. No site-specific literal
was introduced (renderer stays generic and model-driven).

## Asset / poster status — TECHNICAL_CAPTURE_GAP (not #1234)

The `notice.detail.desktop` body is the source poster image. Its exact identity
is **known** from committed G1 provenance:

- state: `notice.detail.desktop`
- SHA-256: `98a133748712ef260803e8fb8b3bc1da28acaf6ced5b1ad3174400ea1cf427bf`
- byte length: `1811506`
- content type: `image/jpeg`

Local search across the G1 capture staging, fixture caches, and controlled
asset set found **no matching body bytes**; `local_path` remains `null`. The
correct classification is:

> TECHNICAL_CAPTURE_GAP: Exact source asset identity is known from committed G1
> provenance, but matching source body bytes are not currently materialized in
> the controlled clone asset set.

This is **not** caused by a rights block or any governance hold on the bytes.
`#1234` is separate future Production/public-release governance and is not
causal to this Phase-A fidelity gap. The clone therefore renders a bounded
structural placeholder for the poster; title, metadata, attachment, and
back-to-list hierarchy are source-backed.

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
- source PNG: canonical committed G1 (`data/official_captures/seogu_gwangju/g1/20260812T231018-0900/states/notice.list.desktop/source.png`), full-page.
- clone screenshot: local offline full-page at matched viewport (SHA-256 in manifest).
- side-by-side: `data/official_clone_reviews/seogu/g3/b0fe78e9c2836a46295668c6f6195b7fce79cd33/states/notice.list.desktop/side_by_side.png`.
- external network count: **0** (non-loopback requests aborted + counted).
- correction applied: removed invented `›` breadcrumb separator; removed bordered `.rc-new-badge` / `.rc-attach-indicator` chips; visible hierarchy stays `홈/구정소식/공지사항`.

### `notice.detail.desktop` — `/seogu/notice/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1, full-page.
- clone screenshot: local offline full-page at matched viewport (SHA-256 in manifest).
- side-by-side: `data/official_clone_reviews/seogu/g3/b0fe78e9c2836a46295668c6f6195b7fce79cd33/states/notice.detail.desktop/side_by_side.png`.
- external network count: **0**.
- **KNOWN GAP (source richer than clone)**: Exact source poster identity is known (SHA-256 `98a13374…`, image/jpeg, 1811506 bytes) but matching body bytes are not materialized in the controlled clone asset set (TECHNICAL_CAPTURE_GAP — see Asset/poster section; not caused by #1234). The clone renders a bounded structural placeholder; title, metadata, attachment and back-to-list hierarchy are source-backed.
- correction applied: pager glyphs `«‹›»` removed (text 처음/이전/다음/마지막 retained); prev/next arbitrary padding/border literals removed.

### `gosi.list.desktop` — `/seogu/gosi/` @ 1440x900 (viewport)
- source PNG: canonical committed G1, full-page.
- clone screenshot: local offline full-page at matched viewport (SHA-256 in manifest).
- side-by-side: `data/official_clone_reviews/seogu/g3/b0fe78e9c2836a46295668c6f6195b7fce79cd33/states/gosi.list.desktop/side_by_side.png`.
- external network count: **0**.
- correction applied: removed invented `›` separator and bordered chips.

### `gosi.detail.desktop` — `/seogu/gosi/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1, full-page.
- clone screenshot: local offline full-page at matched viewport (SHA-256 in manifest).
- side-by-side: `data/official_clone_reviews/seogu/g3/b0fe78e9c2836a46295668c6f6195b7fce79cd33/states/gosi.detail.desktop/side_by_side.png`.
- external network count: **0**.
- correction applied: pager glyphs removed; prev/next arbitrary literals removed.

### `civil_form.list.desktop` — `/seogu/civil-form/` @ 1440x900 (viewport)
- source PNG: canonical committed G1, full-page.
- clone screenshot: local offline full-page at matched viewport (SHA-256 in manifest).
- side-by-side: `data/official_clone_reviews/seogu/g3/b0fe78e9c2836a46295668c6f6195b7fce79cd33/states/civil_form.list.desktop/side_by_side.png`.
- external network count: **0**.
- correction applied: removed invented `›` separator and bordered chips.

### `civil_form.detail.desktop` — `/seogu/civil-form/detail/` @ 1440x900 (viewport)
- source PNG: canonical committed G1, full-page.
- clone screenshot: local offline full-page at matched viewport (SHA-256 in manifest).
- side-by-side: `data/official_clone_reviews/seogu/g3/b0fe78e9c2836a46295668c6f6195b7fce79cd33/states/civil_form.detail.desktop/side_by_side.png`.
- external network count: **0**.
- correction applied: pager glyphs removed; prev/next arbitrary literals removed.

## Source parity legend / closures

- **assets = FAIL**: `asset_byte_fidelity_complete=false` — the clone renders structural placeholders only; no real Seo-gu asset bytes (images/fonts/css) are fetched or committed. Holds for the #1313 six-state slice and is unchanged.
- **poster = TECHNICAL_CAPTURE_GAP (NOT #1234)**: exact identity known from G1 provenance; body bytes not materialized. `#1234` is separate future governance and is not causal.
- **visual/material = DIFFER (expected G2-B)**: source is the real municipal site with full visual styling, photographs, fonts and iconography; clone is the modeled layout tokens with the unsupported-polish literals now removed. Unchanged status; `visual_review` stays `pending`.
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
- **poster TECHNICAL_CAPTURE_GAP** — `notice.detail.desktop` body poster identity is known from G1 provenance (SHA-256 `98a13374…`) but body bytes are not materialized; reported as source-parity `content=DIFFER`. This is NOT caused by #1234 and NOT source-parity PASS.
- `visual_review=pending` / `owner_visual_approved=false` — side-by-side evidence is provided for owner visual approval only; no automated visual pass is asserted.

## Scope / non-mutation statement

- G1 canonical capture bytes: UNCHANGED (SHA-256 verified each state).
- This evidence-only child commit does NOT modify the renderer, G2-A semantic model, visual contract, or tests beyond the renderer correction committed in `b0fe78e9c2836a46295668c6f6195b7fce79cd33`.
- No live recapture of the Seo-gu site; source side is the committed G1 PNG.
- No production/Cloudflare/DB mutation; no actual site integration.
- Prior evidence roots `data/official_clone_reviews/seogu/g3/b6d7a1b` and
  `data/official_clone_reviews/seogu/g3/fbf029b5da49d81eb1303eabf3d491db36bd864d`
  are left UNCHANGED (historical / rejected evidence). This new root
  (`b0fe78e9c2836a46295668c6f6195b7fce79cd33`) supersedes both.
