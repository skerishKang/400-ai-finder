# MVP Golden Quest Fidelity Matrix

> 좌측 시민 사이트 화면 철칙(Exact Official-Site Clone)을 따른다: [docs/product/exact-official-site-clone-invariant.md](docs/product/exact-official-site-clone-invariant.md)
> 이전 방향은 폐기되었다. 현재 계약은 exact official-site clone이다.

This matrix locks the left-surface fidelity contract for the five golden resident-task flows
in the Buk-gu Gwangju MVP. It exists so that future PRs cannot silently
regress these quests back to generic pages, invented internal submission forms,
or unsafe submission-like behavior.

> **Boundary (five golden quests):** These five golden quests are a **local /
> static** surface. They never perform live, provider-dependent, or
> site-affecting actions. They do not navigate to or request the real Buk-gu
> site, Government24, SafetyReport, or 여기로. They do not collect personal data,
> authenticate, submit searches, file complaints / reports / defects / payments,
> initiate phone calls, or perform any action that affects an external system.
>
> This contract locks the five known golden quests only. It does **not** fix the
> entire product as permanently bounded-demo: unknown questions are intended to
> use an LLM fallback (see
> [`docs/hybrid-scripted-llm-architecture-intent.md`](hybrid-scripted-llm-architecture-intent.md)).
> The current static demo has no LLM/API/network in its build, which is a
> deployment constraint rather than the final product intent.

## Locked golden quest set

| # | quest_id | resident task | source_mode | stop_condition |
|---|----------|---------------|-------------|----------------|
| 1 | `housing_department_lookup` | 공동주택과 안내 또는 공동주택 관련 부서 안내 | local_static | STOP_FOR_USER_CONFIRMATION |
| 2 | `illegal_parking_report_guidance` | 불법 주정차 신고 안내 | local_static | STOP_FOR_USER_CONFIRMATION |
| 3 | `bulky_waste_disposal_guidance` | 대형폐기물 배출 안내 | local_static | STOP_FOR_USER_CONFIRMATION |
| 4 | `passport_guidance` | 여권 발급 안내 | local_static | STOP_FOR_USER_CONFIRMATION |
| 5 | `unmanned_kiosk_guidance` | 무인민원발급기 안내 | local_static | STOP_FOR_USER_CONFIRMATION |

---

## 1. housing_department_lookup — 공동주택과 안내

- **quest name**: `공동주택과 안내`
- **primary official_path**
  `북구청 홈 > 북구소개 > 구청안내 > 업무 및 전화번호 안내 > 도시관리국 > 공동주택과`
- **source_mode**: `local_static`
- **stop_condition**: `STOP_FOR_USER_CONFIRMATION`
- **route**: `apartment-dept`
- **target**: `apartment-dept-card`
- **action labels** (exact ordered):
  1. `공동주택과 안내 화면 이동`
  2. `공동주택과 업무 및 연락처 확인`
  3. `사용자 확인 대기`
- **exact-clone status**
  - `apartment-dept` is currently `capture_required` — complete official fixture not yet committed.
  - Complete official page fixture is tracked in #1062.
  - When fixture is secured, the full official organization info table (rows, columns, order, phone numbers, responsibilities, update metadata) must be preserved verbatim.
  - A single representative phone number, a synthetic card, or a summary description is **not** an exact official page clone.
  - The interaction route/action contract matching correctly is separate from official fixture parity being complete.
- **right-panel quest card**
  - `quest_card_type`: `action_plan`
  - action labels include `공동주택과 안내 화면 이동`, `공동주택과 업무 및 연락처 확인`
  - text includes `STOP_FOR_USER_CONFIRMATION`, `local_static`
- **prohibited behavior**
  - Must **not** regress to the old `분야별정보 > 건축 > 아파트정보 > 아파트현황` surface.
  - `062-410-6033` regression guard: the answer must not contain this single phone number as a representative of the full official table.
  - No invented internal department form, no contact-lookup submission UI.
- **E2E verifier**: `tests/browser/verify_housing_quest_e2e.mjs`

---

## 2. illegal_parking_report_guidance — 불법 주정차 신고 안내

- **primary official_path**
  `북구청 홈 > 분야별정보 > 차량교통 > 지도단속`
- **related / handoff path**
  `북구청 홈 > 종합민원 > 민원신고 > 안전신문고` (reflected as the official-report-channel handoff)
- **source_mode**: `local_static`
- **stop_condition**: `STOP_FOR_USER_CONFIRMATION`
- **left surface fidelity**
  - LNB: `분야별정보 > 차량교통` with sub-items
    `등록변경민원 / 지도단속(active) / 기타민원 / 화물운송신고 / 공영주차장 / 차량등록민원 대기현황`
  - body: `지도단속` guidance + `안전신문고` handoff note
  - visible safety context: `공식 신고 채널 / 본인인증 / 사진 / 위치 / 차량번호 / 제출 / STOP_FOR_USER_CONFIRMATION`
- **right-panel quest card**
  - `quest_card_type`: `action_plan`
  - action labels include `지도단속 안내 화면 이동`, `안전신문고 신고 경로 안내 확인`
  - text includes `STOP_FOR_USER_CONFIRMATION`, `local_static`
- **prohibited behavior**
  - Must **not** present an internal `불법 주정차 신고` form-like surface.
  - No real SafetyReport (`safetyreport.go.kr`) navigation or request.
  - No login/authentication, no photo/location/vehicle-number/personal-data input,
    no report submission.
- **E2E verifier**: `tests/browser/verify_illegal_parking_quest_e2e.mjs`

---

## 3. bulky_waste_disposal_guidance — 대형폐기물 배출 안내

- **primary official_path**
  `북구청 홈 > 분야별정보 > 환경재활용 > 대형폐기물 배출방법`
- **related / handoff path**
  `여기로` app / 북구청 홈페이지 신청 (reflected as handoff note, not a live action)
- **source_mode**: `local_static`
- **stop_condition**: `STOP_FOR_USER_CONFIRMATION`
- **left surface fidelity**
  - LNB: `분야별정보 > 환경재활용` with sub-items
    `환경정책 / 대형폐기물 배출방법(active) / 재활용품 분리배출 / 음식물류폐기물`
  - body includes: `배출방법 / 수탁업체(녹색환경) / 월~금 수거 / 062-572-1336, 1337 / 여기로 / 인터넷 배출하기 / 수수료 납부 방법 / 배출변경·취소 / 폐가전 배출방법`
  - `인터넷 배출하기` is shown as handoff guidance only (no external move/request)
- **right-panel quest card**
  - `quest_card_type`: `action_plan`
  - action labels include `대형폐기물 배출방법 화면 이동`, `대형폐기물 배출방법 안내 확인`
  - text includes `STOP_FOR_USER_CONFIRMATION`, `local_static`
- **prohibited behavior**
  - No payment / receipt / sticker / `배출번호` issuance simulation.
  - No item/address/phone input form, no 여기로 external request.
- **E2E verifier**: `tests/browser/verify_bulky_waste_quest_e2e.mjs`

---

## 4. passport_guidance — 여권 발급 안내

- **primary official_path**
  `북구청 홈 > 종합민원 > 여권민원`
- **source_mode**: `local_static`
- **stop_condition**: `STOP_FOR_USER_CONFIRMATION`
- **route sequence**:
  1. `civil-service` — 종합민원 메뉴 확인
  2. `passport-guidance` — 여권민원 안내 화면 이동
  3. `passport-guidance-card` — 여권민원 안내 카드 확인
- **action labels**:
  - `종합민원 메뉴 확인`
  - `여권민원 안내 화면 이동`
  - `여권민원 안내 카드 확인`
  - `사용자 확인 대기`
- **left surface fidelity**
  - LNB: `종합민원 > 여권민원`
  - body: 여권 종류, 유효기간, 발급수수료, 신청절차, 구비서류 안내
- **right-panel quest card**
  - `quest_card_type`: `action_plan`
  - action labels include `종합민원 메뉴 확인`, `여권민원 안내 화면 이동`, `여권민원 안내 카드 확인`
  - text includes `STOP_FOR_USER_CONFIRMATION`, `local_static`
- **safety boundary**
  - 실제 신청·본인확인·사진·서류 제출은 사용자가 직접 진행
  - 안내에서 멈춤 — 실제 신청 완료, 여권 발급 완료, 본인인증 또는 사진·서류 제출을 AI가 수행했다고 주장하지 않음
- **prohibited behavior**
  - Must **not** claim the demo completed the passport application or issuance
  - No real Government24 navigation or request, no 본인인증 / 주소 / 사진 / 서류 input, no submission
  - Must **not** regress to the removed move-in quest path
- **E2E verifier**: `tests/browser/verify_passport_quest_e2e.mjs`

---

## 5. unmanned_kiosk_guidance — 무인민원발급기 안내

- **primary official_path**
  `북구청 홈 > 종합민원 > 무인민원발급기`
- **source_mode**: `local_static`
- **stop_condition**: `STOP_FOR_USER_CONFIRMATION`
- **route sequence**:
  1. `civil-service` — 종합민원 메뉴 확인
  2. `unmanned-kiosk-guidance` — 무인민원발급기 안내 화면 이동
  3. `unmanned-kiosk-card` — 무인민원발급기 안내 카드 확인
- **action labels**:
  - `종합민원 메뉴 확인`
  - `무인민원발급기 안내 화면 이동`
  - `무인민원발급기 안내 카드 확인`
  - `사용자 확인 대기`
- **left surface fidelity**
  - LNB: `종합민원 > 무인민원발급기`
  - body: 설치장소, 발급종류, 이용방법 안내
- **right-panel quest card**
  - `quest_card_type`: `action_plan`
  - action labels include `종합민원 메뉴 확인`, `무인민원발급기 안내 화면 이동`, `무인민원발급기 안내 카드 확인`
  - text includes `STOP_FOR_USER_CONFIRMATION`, `local_static`
- **safety boundary**
  - 설치장소·발급종류·이용방법 안내
  - 실제 서류 발급과 본인인증은 현장에서 사용자가 직접 진행
  - 안내에서 멈춤
- **prohibited behavior**
  - Must **not** claim the demo issued documents or completed authentication
  - No health information / diagnosis / prescription / appointment flow regression
  - No real Buk-gu site navigation or request
- **E2E verifier**: `tests/browser/verify_unmanned_kiosk_quest_e2e.mjs`

---

## Regression guardrails (enforced by tests)

`tests/test_mvp_golden_quest_fidelity_matrix.py` asserts, for every locked quest:

- the `quest_id` exists in the registry
- `quest_name` matches the locked value exactly
- `official_path` matches the locked value exactly
- `source_mode == "local_static"`
- `ai_can_prefill == false`
- `ai_can_submit == false`
- `stop_condition == "STOP_FOR_USER_CONFIRMATION"`
- action types match the **exact ordered** expected list
- route IDs match the **exact ordered** expected list (non-None only)
- target IDs match the **exact ordered** expected list (non-None only)
- labels match the **exact ordered** expected list
- the quest has **not** regressed to prohibited wording (e.g. invented internal
  submission-form paths, payment/sticker issuance, generic department lookup,
  diagnosis/prescription/appointment flows, passport/kiosk issuance claims)
- the matrix exactly matches the canonical registry's `phase1_golden` set

## Hard safety boundaries (must never be added)

- new golden quest
- live / provider-dependent behavior
- external non-local request
- real Buk-gu / Government24 / SafetyReport / 여기로 navigation
- personal-data input
- login / authentication
- search submission
- 민원 / 신고 / 하자 / 결제 submission
- phone-call initiation
- site-affecting action
- confidential business / client / person details
