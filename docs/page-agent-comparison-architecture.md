# Page Agent형 vs 정밀 구현형 비교 데모 — 아키텍처 및 라우트 계약 (Stage 1)

- Issue: #1109 — experiment(page-agent): build a parity Buk-gu AI demo and comparison track
- Stage: 1 — comparison architecture and route contract
- Owner: Computer 1
- Branch: `experiment/1109-stage1-comparison-contract`
- Refs: #862, #873, #1104, #1108, #1068, #1101(Computer 2, 격리)

이 문서는 #1109 Stage 1의 설계 조사 결과와 제품·안전 경계 결정을 기록한다. 실제 Page Agent형
대화형 데모 구현은 Stage 2로 분리된다.

## 1. 기존 구조 조사 결과 (architecture findings)

### 1.1 정밀 구현형 MVP entry (deterministic)
- 정적 엔트리: `src/web/static/citizen-action-demo.html` → 빌드 후 `mvp/index.html` (`build_mvp_entry_html`).
- 첫 화면 셸 + 안무: `citizen-first-use-shell.js`, `citizen-first-choreography.js`, `citizen-copilot-shell.js`.
- 정적 스냅샷 데이터/`api` shim: `snapshot-data.js`, `static-api-shim.js` (빌드 시 주입, 모든 `/api/*` 외부 fetch 차단).
- 라우트: `mvp/` (공개 엔트리, 쿼리 sanitize로 live bridge 차단).

### 1.2 civic canvas (controlled same-origin)
- `citizen-action-demo-canvas.js` + `citizen-action-demo-canvas.css`: 북구청 안내 화면을 본뜬
  controlled same-origin civic canvas. Page Agent형도 이 동일 표면을 재사용한다(Stage 2).

### 1.3 assistant shell
- `citizen-copilot-shell.js` + `.css`, `citizen-first-use-shell.js`: 우측 보조 UI.
  "좌측 civic-site / 우측 assistant" 정신 모델을 두 모드가 공유.

### 1.4 기존 Page Agent Local Lab (developer artifact)
- 위치: `src/web/examples/page-agent/` (영어 문서 `Page Agent · Local Lab`).
- 구성: `index.html`, `mock-model.js`, `page-agent-lab.js`, `page-agent-lab.css`,
  `vendor/page-agent.iife.js` (vendored alibaba/page-agent@1.12.1, MIT), `*-manifest.json`.
- 역할: vendored runtime이 mock OpenAI-compatible adapter로 결정적 DOM 작업을 수행함을 증명하는
  독립 오프라인 기술 실험. 제품 데모 아님.
- 격리: #1108로 root gateway 카드로 노출되었으나, MVP/mobile/admin 경로에는 runtime/discovery
  시그니처가 없도록 route-isolation 계약(`tests/test_page_agent_lab.py`)으로 잠혀 있음.

### 1.5 Page Agent runtime boundary
- vendor/upstream 코드는 별도 정당성 없이 수정하지 않음(절대 원칙).
- Stage 2에서 real vendored Page Agent action loop를 통과해야 하며, 최종 route를 직접 dispatch하여
  runtime을 우회하면 안 됨.

## 2. 주민용 Page Agent 데모 신규 라우트 결정 (proposed resident route)

- 신규 라우트: **`examples/page-agent/resident/`**
  - 정당성: 개발자 lab(`examples/page-agent/`)과 동일 examples 그룹에 두어 기존
    route-isolation 경계(MVP/mobile/admin 오염 금지)를 그대로 유지하면서, 제품 카드에서는
    명확히 분리된다.
  - 이 페이지는 Stage 1에서 라우트/라벨링 계약을 잠그는 자리 표시자이며, 대화형 구현은 Stage 2.
- developer lab 접근: `examples/page-agent/`는 그대로 유지(삭제 금지). 단 root 카드에서
  **주 제품 카드가 아닌 2차/개발자 링크**로 격하.

## 3. root / product labeling 결정

빌드 게이트웨이(`scripts/build_cloudflare_pages.py::build_index_html`) 카드:

| 순서 | 카드 | 라우트 | 성격 |
|----|------|--------|------|
| 1 | 시민 행정 도우미 (정밀 구현형) | `mvp/` | 기존 MVP, 설명 보강 |
| 2 | **Page Agent형 AI 북구청** | `examples/page-agent/resident/` | **주민용 주요 Page Agent 카드** |
| 3 | 모바일 챗 안내 | `mobile.html` | 기존 |
| 4 | 운영자 화면 | `admin.html` | 기존 |
| 5 | Page Agent 개발자 실험실 | `examples/page-agent/` | **격하된 developer lab** |

- 기존 카드명 `Page Agent 실험실` → `Page Agent 개발자 실험실`로 변경(영어 기술 실험임을 명시).
- `examples/page-agent/` 링크는 root에 정확히 1개만 존재(격리 계약 유지).
- 라이브 모드(`?mvp=1`)에서도 동일 라벨링 적용.

## 4. 공유 비교 시나리오 계약 (shared parity contract)

정의 파일: `src/web/examples/page-agent/parity-contract.json` (5개 시나리오, 공유 pass criteria, no-submit 경계).

| id | resident_request | category |
|----|------------------|----------|
| `apartment_contact` | 공동주택과 연락처 찾아줘 | information_lookup |
| `bulky_waste_menu` | 대형폐기물 신청 메뉴 찾아줘 | menu_navigation |
| `passport_procedure` | 여권 발급 절차를 찾아줘 | procedure_navigation |
| `complaint_screen` | 민원 작성 화면을 열어줘 | form_assist |
| `mayor_proposal_writing` | 구청장에게 제안할 글 작성을 도와줘 | writing_assist |

- 두 모드 모두 동일 시민 화면 + 동일 완료 경계에서 동일 task 시도.
- no-submit 경계: 실제 제출·결제·로그인·PII 전송·외부 도메인 이동·임의 JS 실행 금지.
  허용: click/input/select/scroll/read/same-origin navigation.

## 5. 장기 track 이슈와의 충돌 여부

- **#1068 (ux(root): make / the citizen service entry)**: 충돌 없음. 본 비교 게이트웨이는 실험/제품평가
  표면이며, `/` 를 최종 시민 서비스 엔트리로 할지에 대한 별도 추적을 폐기/침묵 supersede 하지 않음.
  본 Stage는 root 카드 라벨링만 변경하고 `/` 의미(정적 랜딩)는 그대로 둠.
- **#862 (official-site action navigator / live integration)**: 충돌 없음. 본 데모는 controlled
  same-origin civic canvas에서만 동작하며 실제 공식 사이트 직접 제어 주장 안 함.
- **#873 (full Buk-gu website rebuild)**: 충돌 없음. 전체 재구축이 아님.
- **#1104 / #1108 (Page Agent lab 생성·링크)**: 본 Stage가 그 위에 비교 트랙을 추가. lab 자체는 변경 안 함.
- **#1101 (Computer 2)**: 격리. 본 Stage는 #1101 브랜치/파일을 수정·병합하지 않음.

## 6. Stage 1 범위 밖 (명시)

- Page Agent형 대화형 데모 구현 → Stage 2.
- 비교 하네스/증거 → Stage 3.
- 비활성 서버측 LLM adapter → Stage 4.
- controlled live validation → Stage 5 (소유자 명시 승인 전 차단).
- live/network 호출( provider/LLM/Firecrawl/official-site fetch/외부 API) → 전 단계 금지(Stage 4까지 mock/default-offline).

## 7. 검증 계약 ( Stage 1 validation )

- `tests/test_page_agent_comparison_contract.py` (신규): 라우트 격리, 제품 라벨링, parity 시나리오,
  no-submit 경계, resident 라우트 자리 표시자 격리.
- 기존 `tests/test_page_agent_lab.py` root discovery 단언을 새 라벨링에 맞게 갱신(격리 계약 유지).
- 정적/라이브 빌드 계약, route isolation, responsive 기존 회귀는 기존 테스트로 보존.
