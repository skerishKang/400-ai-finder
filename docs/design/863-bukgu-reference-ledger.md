# #863 Current Buk-gu Reference Ledger

> Product-scope notice (2026-07-10): the project owner has superseded the
> narrow local/static scope restrictions in this ledger with
> `docs/design/bukgu-ai-agent-product-directive.md`. This ledger remains
> authoritative for capture provenance, hashes, and reference-backed visual
> facts. It no longer prohibits authorized interactive MVP routes, live public
> content synchronization, agent typing, form preparation, or rich motion.

Status: approved for #868 home implementation, #869 J-DEPT-01 department-directory journey, #869 J-PARK-01 parking-information journey, and #869 J-KIOSK-01 approved narrow static-information journey; #867 is completed; external-transaction journeys remain out of scope.

## Home-only approval scope

The R-HOME-01 and R-HOME-02 source captures, their recorded hashes,
the owner-confirmed identity baseline `전남광주통합특별시북구`, the candidate
home inventory, and the separated carousel rules are approved solely for
issue #868 home reconstruction.

This approval does not authorize implementation of the `종합민원` menu/list,
online civil-service, form-preparation, login, data-entry, upload, payment,
or submission states. Those states remain blocked pending the missing
reference captures recorded in this ledger and issue #869.

The approved home scope remains local-fixture-only. Full-page captures are
reference/comparison artifacts only and must never become runtime surfaces.

## Authority

The approved current identity baseline is `전남광주통합특별시북구`.

Earlier conclusions based on legacy-looking or incomplete captures are superseded. Do not replace this label with `광주광역시 북구`, and do not invent an alternative logo, utility bar, GNB taxonomy, banner, or footer.

The current identity baseline is owner-confirmed. Source-capture review must not
replace, normalize, or append a previous jurisdiction name based on uncertain
small-logo pixel transcription. Use the approved local identity crop only as the
visual asset, and retain `전남광주통합특별시북구` as the authoritative text baseline.

## Current source captures

| ID | Filename | SHA-256 | Display size | Use | Carousel |
|---|---|---|---:|---|---|
| R-HOME-01 | `CaptureX_2026-07-05_150817_bukgu.gwangju.kr.png` | e851f990a710b13251700177e8355f18477fcceb5c5e8497a9504e085e2d2397 | 1344×756 | initial desktop home viewport | `소속 공무원 사칭 피해주의 알림` |
| R-HOME-02 | `CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png` | e0c1d451312056a5314fa2dc5b77d62fb53ef6dc90352797d78e4bb57eae3c49 | 1344×1833 | full home flow and footer | `노무사와 함께하는 무료 노동상담데스크` |

The files must be imported unchanged into `docs/artifacts/863-reference/source/`. Full captures are reference and comparison artifacts only. They must never be used as a runtime page background, canvas surface, or full-page image overlay.

## Home hierarchy observed in the current captures

1. Government notice strip.
2. Weather / air-quality / utility row.
3. Current integrated identity/logo and six-item desktop GNB.
4. Civic-brand search region.
5. Mayor card beside one selected carousel slide.
6. Quick-service strip.
7. Notice and major-site modules.
8. Lower media, field-information, partner, and footer modules.

### Approved home reference inventory for #868

| Region | Source | Candidate visible labels / structure | Ledger status |
|---|---|---|---|
| Government notice strip | both | `본 누리집은 전남광주통합특별시 북구청 공식 누리집입니다.` | Owner-confirmed identity text |
| Utility/weather row | both | `26°C`, `미세먼지 좋음`, `초미세먼지 좋음`, `주요사이트`, `SNS`, `KOR` | Approved for #868 home-only reconstruction |
| Identity/logo treatment | both | approved local identity crop; authoritative identity text is `전남광주통합특별시북구` | Owner-confirmed baseline |
| GNB | both | `종합민원` → `소통광장` → `더불어복지` → `분야별정보` → `정보공개` → `북구소개` | Approved for #868 home-only reconstruction |
| Civic-brand/search region | both | civic-brand copy, keyword search field, and hashtag row | Approved for #868 home-only reconstruction |
| Mayor card | both | portrait card, mayor-message region, two outbound-style action links | Approved for #868 home-only reconstruction |
| Main carousel | R-HOME-01: `소속 공무원 사칭 피해주의 알림`<br>R-HOME-02: `노무사와 함께하는 무료 노동상담데스크` | N/A | Separate carousel states — do not combine |
| Quick-service strip | both | `업무검색`, `청사안내`, `고향사랑기부제`, `부끄머니`, `통합예약`, `일반민원 대기현황` | Approved for #868 home-only reconstruction |
| Notice module | both | notice tabs and compact list module | Approved for #868 home-only reconstruction |
| Major-site module | both | `통계정보`, `평생학습관`, `청년센터`, `문화센터`, `공원시설 예약`, `체육시설 예약` | Approved for #868 home-only reconstruction |
| Lower media row | R-HOME-02 | `고향사랑기부제`, `현장스케치`, `카드뉴스`, `알리미` | Approved individual local crops where available |
| Field-information module | R-HOME-02 | Heading/tabs: `분야별 정보`; `구민`, `기업/경제`, `관광`<br>Links: `행정조직도`, `주정차단속문자알림`, `여권 발급`, `보건증 발급`, `대형폐기물 처리`, `온라인 민원발급(정부24)`, `취업지원프로그램안내`, `소화기 사용법`, `정보화교육`, `공공데이터` | Approved for #868 home-only reconstruction |
| Partner strip | R-HOME-02 | `농림축산식품부`, `Smart K-Factory`, `PIS 행정정보공동이용센터`, `소비자24`, `수유시설` | Approved for #868 home-only reconstruction |
| Footer navigation | R-HOME-02 | `누리집이용안내`, `개인정보처리방침`, `저작권 보호정책`, `이메일무단수집거부`, `영상정보처리기기 운영·관리방침` | Approved for #868 home-only reconstruction |
| Footer legal/contact/badges | R-HOME-02 | contact/hours/copyright text block plus small certification badges | Legal text and badges require owner approval or higher-resolution source |

### Approved exact home transcriptions for limited #868 text alignment

The following source-backed strings are approved only for the listed #868
home-renderer text alignment. This approval is limited to the civic-brand
alternative text, hashtag order, and notice-tab order in
`src/web/static/citizen-action-demo-canvas.js`.

- Approved civic-brand text:
  `빛나는 북구, 함께하는 북구 - 행복한 구민을 위한 따뜻한 변화`
- Approved hashtag order:
  `#공동주택과` → `#위생과` → `#폐기물` → `#부끄머니`
- Approved notice-tab order:
  `공지사항` → `보도자료` → `고시/공고`

The search placeholder remains intentionally unresolved. Do not change,
approve, or infer it from this section.

Footer legal/contact/copyright wording and certification badges remain pending
under the existing higher-resolution or owner-approval requirement.

### Initial static carousel rule

The two supplied home captures show different carousel slides. The initial static local home state must select exactly one approved above-fold slide and keep it fixed. The lower-page capture controls lower-page layout and footer only; do not blend its carousel content into the initial viewport.

### Carousel state separation

- R-HOME-01과 R-HOME-02의 banner는 서로 다른 state다.
- R-HOME-01 default state와 R-HOME-02 query state를 절대 한 화면 비교 기준으로 섞지 않는다.
- mayor card는 carousel banner와 별도의 layout element다.
- R-HOME-02 full-home evidence는 `?home-reference=R-HOME-02`일 때만 비교한다.

## #869 approved first information journey — J-DEPT-01

> Historical reference note: this section records the earlier #869 directory-search
> capture and is not the current runtime source of truth. Issue #1062 supersedes its
> reduced `전체 9명` result with the complete official 19-row 공동주택과 organization/work
> snapshot. `062-410-6033` remains an official 과장 row, not the department representative
> number; the separately verified representative number is `062-410-6841`.

### Scope

J-DEPT-01 is one local, source-backed information-finding journey only:

- User question:
  `공동주택 관련 문의는 어느 부서에 해야 하나요?`
- Source-backed route:
  `북구소개` → `구청안내` → `업무 및 전화번호 안내`
- Search term:
  `공동주택`
- Source-backed first result:
  `공동주택과` / `062-410-6033` / `공동주택과 업무전반`
- Search-result count:
  `전체 9명, 현재 페이지 1/1`

### Approved source inventory

| ID | Source state | Purpose |
|---|---|---|
| R-DEPT-01 | `북구소개` mega-menu expanded | route discovery and visible `구청안내 → 업무 및 전화번호 안내` entry |
| R-DEPT-02 | directory initial 1344×756 viewport | title, breadcrumb, LNB, filter/search bar, default table geometry |
| R-DEPT-03 | directory full default page | pagination, feedback region, footer shell |
| R-DEPT-04 | `공동주택` query 1344×756 viewport | entered search term, result count, visible result rows |
| R-DEPT-05 | `공동주택` query full page | query-result table extent, pagination, feedback region, footer shell |

### Approval and boundaries

- Implement semantic local DOM/CSS only. The five source captures are never runtime
  page surfaces, backgrounds, full-page images, or coordinate overlays.
- Reconstruct only the visible route elements needed for J-DEPT-01:
  desktop header/GNB, `북구소개` mega-menu state, directory LNB/breadcrumb,
  search controls, result count, result table, pagination, and footer shell.
- The local journey may animate or reveal the approved chat-copy progression:
  1. User: `공동주택 관련 문의는 어느 부서에 해야 하나요?`
  2. Assistant: `북구청 업무 및 전화번호 안내에서 담당 부서를 찾아보겠습니다.`
  3. Assistant: `북구소개 메뉴에서 구청안내를 확인했습니다.`
  4. Assistant: `업무 및 전화번호 안내에서 ‘공동주택’을 검색하고 있습니다.`
  5. Assistant: `공동주택 관련 문의는 공동주택과에서 담당합니다. 대표 연락처는 062-410-6033입니다.`
- The final answer must not invent a team, person, escalation path, submission
  process, external link, or transaction.
- No login, personal-data entry, upload, payment, electronic signature,
  complaint filing, external navigation, or final submission behavior.
- `전남광주통합특별시북구` remains the authoritative identity baseline.
- R-DEPT-01, R-DEPT-02, R-DEPT-03, R-DEPT-04, and R-DEPT-05 are approved only
  for J-DEPT-01. They do not approve a second journey.

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

4. Higher-resolution footer badge crop if exact certification names or marks are required.
5. Higher-resolution close-up only for any small text that cannot be verified from the existing captures.

## Review sequence

1. Import source PNGs unchanged and record file hashes.
2. Confirm this ledger against uploaded screenshots.
3. Implement home only under #868.
4. Implement only ledger-approved local information-finding journeys under #869; do not add civil-service submission, pre-submit form, or external-transaction states without a separate approved source set.
5. Implement the separate chat shell under #870.
6. Re-render matched viewports and review before any deployment or merge.

## #869 approved second information journey — J-PARK-01

### Scope

J-PARK-01 is one local, source-backed parking-information journey only:

- User question:
  `북구청 청사부설주차장은 몇 시까지 유료이고 요금은 어떻게 되나요?`
- Source-backed route:
  `북구소개` → `구청안내` → `주차장 이용안내`
- Page title:
  `주차장 이용안내`
- Approved facts only:
  - `청사부설주차장 현황`
  - `주차면수: 130면`
  - `주차타워: 111면(1층 42, 2층 29, 3층 40)`
  - `기타: 19면`
  - `1시간(모든 민원인)`
  - `30분 500원(무료시간 이후 최초 30분)`
  - `10분당 200원(기본 30분 이후)`
  - `평일(월~금) 유료운영: 08:00 ~ 19:00`
  - `야간 및 휴일 무료개방`

### Approved source inventory

| ID | Filename | SHA-256 | Display size | Purpose | State |
|---|---|---|---:|---|---|
| R-PARK-01 | `CaptureX_2026-07-06_014330_bukgu.gwangju.kr_park.png` | f6a73282408faeb6e0fad54fe252d64bceb78f9e7e1137d03f5123ac39619837 | 1344×756 | desktop parking-info viewport | initial parking page |
| R-PARK-02 | `CaptureX_2026-07-06_014332_bukgu.gwangju.kr_park_full.png` | c127c14eaa614c7383dcf74b3177100f896ef2dda1828bc992d3285284c947ff | 1344×1311 | full parking-info page and footer | full parking detail page |

### Approval and boundaries

- Implement semantic local DOM/CSS only. The two source captures are never runtime page surfaces, backgrounds, full-page images, or coordinate overlays.
- Reconstruct only the static elements needed for J-PARK-01: GNB layout, breadcrumbs, content tables, and footer shell.
- No menu-click choreography (such as sub-dropdown toggle animations) is required or approved, as no source capture confirms the route-entry menu transition item itself.
- Do not show live parking availability counters or map integrations.
- No reservation, payment, map, route guidance, login, personal-data entry, upload, submission, external navigation, or transaction is permitted.
- `전남광주통합특별시북구` remains the authoritative identity baseline.

## #869 approved third information journey — J-KIOSK-01

### Scope

J-KIOSK-01 is one local, source-backed narrow static-information journey only:

- User question:
  `북구청 무인민원발급기는 어디에 있고 언제 이용할 수 있나요?`
- Direct local route:
  `?journey=J-KIOSK-01`
- Source-backed route:
  `종합민원` → `무인민원발급기` → `설치장소`
- Page title:
  `무인민원발급기`
- Visible tabs:
  `설치장소` / `발급종류 및 처리순서` / `발급가능 민원서류`
- Table heading:
  `무인민원발급기 설치장소(50개소)`
- Factual rendering allowed rows (exactly these two only):
  1. `북구청 민원실` / `우치로 77` / `24시간` / `122종` / `장애인겸용`
  2. `북구청 민원실 2` / `우치로 77` / `24시간` / `121종` / `장애인겸용`
- Approved final answer:
  `북구청 민원실과 북구청 민원실 2는 우치로 77에 있으며 24시간 이용할 수 있습니다. 발급 가능 민원서류는 각각 122종과 121종입니다.`

### Source-supported observations only

- route/state: 종합민원 → 무인민원발급기 → 설치장소
- page title: 무인민원발급기
- visible tabs: 설치장소, 발급종류 및 처리순서, 발급가능 민원서류
- visible table heading: 무인민원발급기 설치장소(50개소)
- visible table columns: 구분, 시설명, 도로명주소, 운영시간, 발급종수, 발급기형태, 비고

### Source records

| ID | Filename | SHA-256 | Display size | Purpose |
|---|---|---|---:|---|
| J-KIOSK-01 | `jkiosk-01-installation-desktop.png` | 5a277039d723bf3010d4b4fc814aaf9fcf81179739cd29534af78c11cdb958d5 | 1536×864 | readable initial desktop installation-location viewport |
| J-KIOSK-02 | `jkiosk-02-installation-full.png` | b7e6a53c57573e82ac508cad198446fbc89a3cef46fa3ec3de70fd8067739853 | 524×1536 | full table flow, lower explanatory regions, and footer |

### Hard boundaries

- Both captures are reference/comparison artifacts only; never runtime backgrounds, page surfaces, `<img>` page substitutes, or coordinate overlays.
- Full-page source is for table-extent and lower-structure reference only; rendering unreadable rows, small text, or footer wording is not approved.
- Full 50-location reproduction is prohibited.
- No implementation is authorized beyond the two approved factual rows and the approved final answer.
- No search, menu-click choreography, map, route guidance, live availability, reservation, payment, login, personal-data entry, external navigation, or submission behavior.
- Authoritative identity baseline remains 전남광주통합특별시북구.
- Do not infer or add unreadable table rows, addresses, hours, certificate counts, or footer/legal wording.
