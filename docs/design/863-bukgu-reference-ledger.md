# #863 Current Buk-gu Reference Ledger

Status: draft baseline for issue #867.

## Authority

The approved current identity baseline is `전남광주통합특별시북구`.

Earlier conclusions based on legacy-looking or incomplete captures are superseded. Do not replace this label with `광주광역시 북구`, and do not invent an alternative logo, utility bar, GNB taxonomy, banner, or footer.

## Current source captures

| ID | Filename | Display size | Use |
|---|---|---:|---|
| R-HOME-01 | `CaptureX_2026-07-05_150817_bukgu.gwangju.kr.png` | 1344×756 | Canonical initial desktop home viewport |
| R-HOME-02 | `CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png` | 1344×1833 | Canonical lower-home and footer flow |

The files must be imported unchanged into `docs/artifacts/863-reference/source/`. Full captures are reference and comparison artifacts only. They must never be used as a runtime page background, canvas surface, or full-page image overlay.

## Home hierarchy observed in the current captures

1. Government notice strip.
2. Weather / air-quality / utility row.
3. Current integrated logo and six-item desktop GNB.
4. Civic-brand search region.
5. Mayor card beside one selected carousel slide.
6. Quick-service strip.
7. Notice and major-site modules.
8. Lower media, field-information, partner, and footer modules.

### Exact visible GNB order

`종합민원` → `소통광장` → `더불어복지` → `분야별정보` → `정보공개` → `북구소개`

### Initial static carousel rule

The two supplied home captures show different carousel slides. The initial static local home state must select exactly one approved above-fold slide and keep it fixed. The lower-page capture controls lower-page layout and footer only; do not blend its carousel content into the initial viewport.

### Carousel state separation

- R-HOME-01: ordinary default local home state (above-fold comparison only). Default banner: `home-alert-banner.png`.
- R-HOME-02: selectable via `?home-reference=R-HOME-02` only. Full-home comparison state. Banner: `home-alert-banner-r-home-02.png`.
- R-HOME-01 and R-HOME-02 are different carousel states. A canvas rendered in one state must NOT be compared against the other state's source capture.
- R-HOME-02 full-home evidence must render with `?home-reference=R-HOME-02`.
- The banner crop is `src/web/static/images/bukgu-current/home-alert-banner-r-home-02.png` (box `[562, 258, 1123, 555)`, 561x297).

## Implementation boundaries

- Recreate layout, text containers, borders, spacing, typography, controls, and card surfaces using semantic HTML/CSS.
- Use only approved individual local crops for the integrated logo, portrait, banner artwork, content images, and footer badges where a DOM recreation would lose fidelity.
- Use a fixed-ratio internal official viewport on the left side of the split demo and scale it uniformly; do not collapse the official desktop layout into a made-up mobile layout.
- Keep the right AI chat shell visually separate from the official-left viewport.
- The initial right-side chat thread is:
  - User: `불법 주정차 신고는 어디서 하나요?`
  - Assistant: `북구청 홈페이지에서 신고 경로를 확인하겠습니다.`
  - Assistant: `종합민원 메뉴에서 온라인 민원신청 경로를 찾고 있습니다.`
- The composer is inert with disabled `보내기`.
- No technical trace, browser log, old conversation history, or English reply appears in the primary chat surface.

## Missing reference captures

Before civil-service or pre-submit source work begins, collect:

1. Current desktop `종합민원` menu/list screen, normal viewport and full-page if practical.
2. Current online civil-service or form-preparation screen before login, personal-data entry, upload, or submission.
3. A close-up only when a label or icon cannot be read from a normal capture.

## Review sequence

1. Import source PNGs unchanged and record file hashes.
2. Confirm this ledger against uploaded screenshots.
3. Implement home only under #868.
4. Implement menu and pre-submit states under #869.
5. Implement the separate chat shell under #870.
6. Re-render matched viewports and review before any deployment or merge.