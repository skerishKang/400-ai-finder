# #868 Home Lower Card Crop Manifest

Status: approved mechanical extraction plan for the lower-home card row.

## Source authority

- Reference: `R-HOME-02`
- Source: `docs/artifacts/863-reference/source/CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png`
- SHA-256: `e0c1d451312056a5314fa2dc5b77d62fb53ef6dc90352797d78e4bb57eae3c49`
- Canvas: `1344x1833`

All coordinates are `[left, top, right, bottom)` on the immutable source. Extraction must write lossless PNG without resizing, filtering, recoloring, or source mutation.

## Approved derived assets

| Output path | Box | Expected size | Visible role |
|---|---:|---:|---|
| `src/web/static/images/bukgu-current/home-lower-hometown-donation.png` | `[217, 1040, 385, 1208)` | `168x168` | 고향사랑기부제 card image |
| `src/web/static/images/bukgu-current/home-lower-field-sketch.png` | `[400, 1040, 638, 1208)` | `238x168` | 현장스케치 card image |
| `src/web/static/images/bukgu-current/home-lower-card-news.png` | `[650, 1040, 818, 1208)` | `168x168` | 카드뉴스 card image |
| `src/web/static/images/bukgu-current/home-lower-notifier.png` | `[830, 1040, 1127, 1208)` | `297x168` | 알리미 card image |

## Boundary

- These are individual visual cards only, never an entire page, section, or background surface.
- Do not implement HTML, CSS, JavaScript, tests, render evidence, or footer work in the extraction commit.
- Do not derive additional assets.
- The following lower sections remain semantic DOM/CSS work for a later owner-issued patch: card labels/pagers, 분야별 정보, banner row, and footer.

## Required checks

1. Source SHA-256 and source dimensions match exactly.
2. Every output is PNG and matches its expected size.
3. `git diff --check` succeeds.
4. The changed-file allowlist contains only the four derived PNG files.
