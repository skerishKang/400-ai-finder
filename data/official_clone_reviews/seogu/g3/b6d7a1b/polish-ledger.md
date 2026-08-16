# Seo-gu #1313 Board Visual Polish Ledger

Candidate commit: `b6d7a1bef43749057dbd3e5f314125ba61d13438`
Base: `feat/1312-seogu-g3-board-fidelity` @ `3a2dea0d901e39481cffd344514eff24b0d909bf`

## Method

Because the reviewer cannot view the side-by-side PNGs directly, every change in
this polish pass is grounded in (1) the committed G1 source DOM landmarks /
controls (`visible-region-inventory.json`), (2) the validated `visual-contract.json`
measurements, and (3) the renderer's own model-driven output. No change was
based on guessed pixels.

## Observations (source vs clone)

| # | region | source evidence | clone before | clone after |
|---|---|---|---|---|
| 1 | Board breadcrumb | G1 landmark shows `분야별정보 > 행정 > 행정소식 > 공지사항` with visible `>` separators | adjacent text spans, no separators | `›` separator spans between crumbs (`<span class="rc-crumb-sep" aria-hidden="true">›</span>`) |
| 2 | Pager | Korean public-sector pager convention renders arrow glyphs on 처음/이전/다음/마지막 | text-only buttons | `«`/`‹` prefix, `›`/`»` suffix (aria-hidden glyph spans) |
| 3 | New-post marker | G1 list shows `새글` prefix on new rows (e.g. row 10852) | plain text prefix | bordered `.rc-new-badge` chip (`새글`) |
| 4 | List attachment column | source shows a clipped attachment count cell | text `첨부 N` | bordered `.rc-attach-indicator` chip |
| 5 | Detail prev/next | source renders 이전글/다음글 rows in a bordered band | adjacent rows | rule separator between 이전글 and 다음글 with 12px vertical padding |
| 6 | Emblem / logo | real logo image bytes not committed (`TECHNICAL_CAPTURE_GAP`, SHA-256 `98a13374…`) | CSS circle placeholder | unchanged (asset gate — no AI/fake logo) |

## Renderer changes (`src/official_clone/reference_clone_renderer.py`)

1. `_board_nav_html`: insert `rc-crumb-sep` spans between breadcrumb crumbs.
2. `_render_board_pagination`: wrap arrow glyphs in aria-hidden spans on the
   처음/이전/다음/마지막 pager buttons.
3. `_render_list_main` (model-backed board path): split `새글` out of the title
   into a `.rc-new-badge` chip; escape the remaining title only.
4. `_render_css`: add `.rc-crumb-sep`, `.rc-new-badge`, `.rc-attach-indicator`
   chip styling, and `.rc-pn-prev`/`.rc-pn-next` separator + padding.

No `border-radius`, no guessed colors outside the visual-contract palette, no
new `font-size:…rem` tokens, and no changes to the forbidden-css-token list
(the renderer test suite enforces those gates and passes).

## Test changes (renderer contracts only, not behavior)

- `tests/test_reference_clone_renderer.py::test_board_list_rows_without_detail_record_id_are_inert`
  — inert-span regex widened to allow the nested `.rc-new-badge` markup.
- `tests/test_reference_clone_renderer_board_candidate_gate.py::test_linked_rows_exactly_match_family_detail_record_id`
  — anchor regex widened to capture nested markup; text comparison strips tags.

## Not changed (explicitly out of scope)

- List → detail link assertion (known CTO-identified E2E concern; semantic, not visual).
- notice.detail body poster image (asset gate #1234; `TECHNICAL_CAPTURE_GAP`).
- Any board data model, routing, or G2-A semantic content.

## Verification

- `pytest tests/test_reference_clone_renderer.py` — 78 passed.
- `pytest tests/test_reference_clone_renderer_board_candidate_gate.py` — 3 passed.
- `pytest tests/test_renderer_route_manifest_fidelity.py` — 12 passed.
- `pytest tests/test_clone_visual_approval_gate.py tests/test_exact_official_site_clone_invariant.py` — 63 passed.
- `git diff --check` — clean.
- Evidence: fresh 6-state capture (chromium 138.0.7204.23, Playwright 1.53.0)
  at `data/official_clone_reviews/seogu/g3/b6d7a1b/`, external network total 0.
