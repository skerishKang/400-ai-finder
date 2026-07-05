# #868 Current Home Top Crop Manifest

Status: approved derivation plan for the first home viewport patch.

## Source authority

- `R-HOME-01`: `docs/artifacts/863-reference/source/CaptureX_2026-07-05_150817_bukgu.gwangju.kr.png`
- SHA-256: `e851f990a710b13251700177e8355f18477fcceb5c5e8497a9504e085e2d2397`
- Canvas: 1344×756

All coordinates use `[left, top, right, bottom)` pixels on the source canvas. The extraction must use lossless PNG output and no resampling.

## Derived runtime crops

| Output path | Box | Render role | Rule |
|---|---:|---|---|
| `src/web/static/images/bukgu-current/home-identity.png` | `[220, 70, 390, 112)` | Header official identity | image only, visible `<img>` at the official logo position |
| `src/web/static/images/bukgu-current/home-civic-brand.png` | `[220, 165, 505, 220)` | Civic-brand line | image only, visible `<img>` in the branded search region |
| `src/web/static/images/bukgu-current/home-mayor-card.png` | `[210, 258, 555, 555)` | Mayor card | semantic `<article>` with one approved card image; no duplicated overlay text/buttons |
| `src/web/static/images/bukgu-current/home-alert-banner.png` | `[562, 258, 1123, 555)` | Frozen initial carousel slide | semantic `<article>` with one approved banner image; no automatic rotation |
| `src/web/static/images/bukgu-current/home-quick-work.png` | `[379, 605, 420, 646)` | 업무검색 icon | image only inside a DOM quick-link item |
| `src/web/static/images/bukgu-current/home-quick-office.png` | `[472, 605, 513, 646)` | 청사안내 icon | image only inside a DOM quick-link item |
| `src/web/static/images/bukgu-current/home-quick-donation.png` | `[588, 605, 629, 646)` | 고향사랑기부제 icon | image only inside a DOM quick-link item |
| `src/web/static/images/bukgu-current/home-quick-money.png` | `[694, 605, 735, 646)` | 부꾸머니 icon | image only inside a DOM quick-link item |
| `src/web/static/images/bukgu-current/home-quick-reservation.png` | `[807, 605, 848, 646)` | 통합예약 icon | image only inside a DOM quick-link item |
| `src/web/static/images/bukgu-current/home-quick-waiting.png` | `[914, 605, 955, 646)` | 일반민원 대기현황 icon | image only inside a DOM quick-link item |

## Extraction boundary

- Do not crop the entire header, quick-service row, or page surface.
- Do not use crop assets to replace the DOM hierarchy.
- The mayor and banner cards are approved indivisible visual cards for this first top-viewport patch; their visible typography/button detail must not be duplicated in DOM.
- All surrounding grid, spacing, utility controls, GNB, search field, quick-link labels, pager controls, notice/site panels, and footer remain semantic DOM/CSS.
- Lower-home crop extraction is deferred until the first top viewport render is reviewed.

## Required derived-asset checks

1. Every crop must be PNG and retain the exact pixel rectangle above.
2. `Pillow.Image.open()` must report the expected width/height.
3. The extractor must reject a source hash mismatch.
4. No source file may be rewritten.
5. The asset extraction commit must change only the extractor, this manifest if correction is required, and the derived crop files.