# #863 Current Buk-gu Reference Ledger

Status: candidate ledger for owner approval under issue #867.

## Authority

The approved current identity baseline is `전남광주통합특별시북구`.

Earlier conclusions based on legacy-looking or incomplete captures are superseded. Do not replace this label with `광주광역시 북구`, and do not invent an alternative logo, utility bar, GNB taxonomy, banner, or footer.

## Current source captures

| ID | Filename | SHA-256 | Display size | Use | Carousel |
|---|---|---|---:|---|---|
| R-HOME-01 | `CaptureX_2026-07-05_150817_bukgu.gwangju.kr.png` | e851f990a710b13251700177e8355f18477fcceb5c5e8497a9504e085e2d2397 | 1344×756 | initial desktop home viewport | `소속 공무원 사칭 피해주의 알림` |
| R-HOME-02 | `CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png` | e0c1d451312056a5314fa2dc5b77d62fb53ef6dc90352797d78e4bb57eae3c49 | 1344×1833 | full home flow and footer | `노무사와 함께하는 무료 노동상담데스크` |

The files must be imported unchanged into `docs/artifacts/863-reference/source/`. Full captures are reference and comparison artifacts only. They must never be used as a runtime page background, canvas surface, or full-page image overlay.

## Home hierarchy observed in the current captures

* identity baseline: `전남광주통합특별시북구`
* GNB: `종합민원` → `소통광장` → `더불어복지` → `분야별정보` → `정보공개` → `북구소개`
* major sites: `평생학습관`
* field-info link: `취업지원프로그램안내`
* field-info links: `행정조직도`, `주정차단속문자알림`, `여권 발급`, `보건증 발급`, `대형폐기물 처리`, `온라인 민원발급(정부24)`, `취업지원프로그램안내`, `소화기 사용법`, `정보화교육`, `공공데이터`

*Note: government notice strip, footer legal, and small thumbnail text are pending owner approval.*

### Initial static carousel rule

The two supplied home captures show different carousel slides. The initial static local home state must select exactly one approved above-fold slide and keep it fixed. The lower-page capture controls lower-page layout and footer only; do not blend its carousel content into the initial viewport.

### Carousel state separation

- R-HOME-01과 R-HOME-02의 banner는 서로 다른 state다.
- R-HOME-01 default state와 R-HOME-02 query state를 절대 한 화면 비교 기준으로 섞지 않는다.
- mayor card는 carousel banner와 별도의 layout element다.
- R-HOME-02 full-home evidence는 `?home-reference=R-HOME-02`일 때만 비교한다.

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