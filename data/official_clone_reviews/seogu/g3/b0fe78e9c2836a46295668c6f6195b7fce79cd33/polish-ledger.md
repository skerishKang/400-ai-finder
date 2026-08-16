# Seo-gu #1313 Board Visual Polish Correction Ledger

Candidate commit: `b0fe78e9c2836a46295668c6f6195b7fce79cd33`
Base: `feat/1312-seogu-g3-board-fidelity` @ `3a2dea0d901e39481cffd344514eff24b0d909bf`

This ledger documents the **correction** to the prior `b6d7a1b` polish pass.
The prior pass added treatments that were not grounded in the committed G1
source DOM; this correction removes them and restores source-backed structure.

## Method

Every change in this correction pass is grounded in (1) the committed G1 source
DOM landmarks / controls (`visible-region-inventory.json`), (2) the validated
`visual-contract.json` measurements, and (3) the renderer's own model-driven
output. No change was based on guessed pixels, conventions, or invented glyphs.

## Corrections (source vs clone)

| # | region | prior (incorrect) treatment | corrected treatment |
|---|---|---|---|
| 1 | Board breadcrumb | invented `›` separator (`<span class="rc-crumb-sep" aria-hidden="true">›</span>`) | separator removed; visible hierarchy `홈/구정소식/공지사항` preserved; blind search legend (`분야별정보 > 행정 > 행정소식 > 공지사항`) NOT promoted to visible nav |
| 2 | Pager | `«`/`‹` prefix, `›`/`»` suffix glyphs justified only by generic "Korean public-sector pager convention" | glyphs removed; source text 처음/이전/다음/마지막 retained; first/prev/next/last semantics unchanged |
| 3 | New-post marker | bordered `.rc-new-badge` chip (`새글`) | source DOM `<i class="xi-new"></i><span class="sr_only">새글</span>`; xi-new glyph is a TECHNICAL_CAPTURE_GAP (XEIcon font bytes not materialized); sr-only label preserved, no fake bordered chip |
| 4 | List attachment column | bordered `.rc-attach-indicator` chip (`첨부 N`) | chip removed; attachment count preserved via `sr_only` label; no external/relative asset URL emitted (runtime external requests stay 0) |
| 5 | Detail prev/next | arbitrary `padding:12px 0`, `margin-right:8px`, `border-bottom:1px solid #ddd` | arbitrary literals removed; source-backed `<ul class="prevnext">` row structure with 이전글/다음글 labels preserved |
| 6 | Poster (notice.detail.desktop) | exact identity known from G1 provenance (SHA-256 `98a1337487…`, image/jpeg, 1811506 bytes) but body bytes not materialized in controlled asset set (`TECHNICAL_CAPTURE_GAP`) | clone renders a bounded structural placeholder; title/metadata/attachment/back-to-list hierarchy source-backed |
| 7 | Emblem / logo | real logo image bytes not committed; separate `TECHNICAL_CAPTURE_GAP` with NO SHA-256 asserted (the `98a1337487…` digest belongs to the notice.detail poster only) | unchanged — no AI/fake logo; logo/emblem gap documented independently of the poster gap |

## Poster / asset gap — TECHNICAL_CAPTURE_GAP (not #1234)

- `notice.detail.desktop` poster: SHA-256 `98a133748712ef260803e8fb8b3bc1da28acaf6ced5b1ad3174400ea1cf427bf`, image/jpeg, 1811506 bytes.
- Local search across G1 capture staging, fixture caches, and the controlled
  asset set found **no matching body bytes**; `local_path` remains `null`.
- Correct classification: exact source asset identity is known from committed G1
  provenance, but matching source body bytes are not currently materialized in
  the controlled clone asset set (TECHNICAL_CAPTURE_GAP).
- This is **not** caused by a rights block or any governance hold on the bytes.
  `#1234` is separate future Production/public-release governance and is not
  causal to this Phase-A fidelity gap.

## Renderer changes (`src/official_clone/reference_clone_renderer.py`)

1. `_board_nav_html`: removed `rc-crumb-sep` `›` separator span; crumbs stay as
   discrete labelled spans (홈 → 구정소식 → 공지사항).
2. `_render_board_pagination`: removed the aria-hidden `«`/`‹`/`›`/`»` glyph
   spans; kept source text 처음/이전/다음/마지막.
3. `_render_list_main` (new-post): replaced `.rc-new-badge` chip with source DOM
   `<i class="xi-new" aria-hidden="true"></i><span class="sr_only">새글</span>`
   + stripped title; screen-reader label preserved.
4. `_render_list_main` (attachment): replaced `.rc-attach-indicator` chip with an
   `sr_only` count label; no external/relative asset URL.
5. `_render_css`: removed `.rc-crumb-sep`, `.rc-new-badge`, `.rc-attach-indicator`
   chip styling; removed arbitrary `.rc-pn-prev`/`.rc-pn-next` padding/border/
   margin literals; added generic `.sr_only` a11y utility.

No `border-radius`, no guessed colors outside the visual-contract palette, no
new `font-size:…rem` tokens, and no changes to the forbidden-css-token list
(the renderer test suite enforces those gates and passes).

## Test changes (renderer contracts + new regressions)

- `tests/test_reference_clone_renderer.py`: added regression tests
  `test_1324_visible_breadcrumb_not_from_blind_search_legend`,
  `test_1324_new_post_semantic_preserved_no_visible_chip`,
  `test_1324_attachment_count_preserved_no_bordered_chip`,
  `test_1324_pager_uses_source_text_not_invented_glyphs` — these strengthen
  behavior/semantic assertions (blind legend not promoted, sr-only 새글 label
  preserved, bordered chips absent, pager glyphs absent, source labels
  preserved). Prior regex tests were not loosened.

## Not changed (explicitly out of scope)

- List → detail link assertion (known CTO-identified E2E concern; semantic, not visual).
- notice.detail body poster image (TECHNICAL_CAPTURE_GAP; not caused by #1234).
- Any board data model, routing, or G2-A semantic content.

## Verification

- `pytest tests/test_reference_clone_renderer.py` — 82 passed (incl. 4 new regressions).
- `pytest tests/test_reference_clone_renderer_board_candidate_gate.py` — 3 passed.
- `pytest tests/test_visual_contract.py tests/test_reference_clone_model.py tests/test_renderer_route_manifest_fidelity.py tests/test_clone_visual_approval_gate.py` — 146 passed.
- `pytest tests/test_bukgu_home_clone_fixture_projection.py` — 9 passed.
- `git diff --check` — clean.
- Evidence: fresh 6-state capture (chromium 145.0.7632.116, Playwright 1.61.0)
  at `data/official_clone_reviews/seogu/g3/b0fe78e9c2836a46295668c6f6195b7fce79cd33/`,
  external network total 0.
