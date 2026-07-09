# MVP Golden Quest Fidelity Matrix

This document locks the fidelity contract for the 5 resident-task golden quests
in the Buk-gu Gwangju MVP. It exists so that future PRs cannot silently
regress these quests back to generic pages, invented internal submission forms,
or unsafe submission-like behavior.

> **Boundary:** The MVP is a **local / static** surface. It never performs
> live, provider-dependent, or site-affecting actions. It does not navigate to
> or request the real Buk-gu site, Government24, SafetyReport, or 여기로. It does
> not collect personal data, authenticate, submit searches, file complaints /
> reports / defects / payments, initiate phone calls, or perform any action
> that affects an external system.

## Locked golden quest set

| # | quest_id | resident task | source_mode | stop_condition |
|---|----------|---------------|-------------|----------------|
| 1 | `housing_department_lookup` | 아파트 정보 안내 | local_static | STOP_FOR_USER_CONFIRMATION |
| 2 | `illegal_parking_report_guidance` | 불법 주정차 신고 안내 | local_static | STOP_FOR_USER_CONFIRMATION |
| 3 | `bulky_waste_disposal_guidance` | 대형폐기물 배출 안내 | local_static | STOP_FOR_USER_CONFIRMATION |
| 4 | `move_in_report_guidance` | 전입신고 안내 | local_static | STOP_FOR_USER_CONFIRMATION |
| 5 | `public_health_center_guidance` | 보건소 위치·진료 안내 | local_static | STOP_FOR_USER_CONFIRMATION |

---

## 1. housing_department_lookup — 아파트 정보 안내

- **primary official_path**
  `북구청 홈 > 분야별정보 > 건축 > 아파트정보 > 아파트현황`
- **related / handoff path**
  `분야별정보 > 건축 > 아파트생활정보 > 하자발생` (reflected as a related guidance card)
- **source_mode**: `local_static`
- **stop_condition**: `STOP_FOR_USER_CONFIRMATION`
- **left surface fidelity**
  - LNB: `분야별정보 > 건축` with sub-items
    `건축민원 / 기계설비법 / 아파트정보(active) / 건축물대장말소신고 / 아파트생활정보 / 정비사업(재개발재건축)`
  - `아파트현황` table: `전체 428 건, 1/43 페이지`
  - columns: `번호 / 아파트명 / 새주소명 / 사용검사 / 동수 / 층수 / 세대수 / 관리사무소`
  - representative rows: `제일맨션 / 오치아파트 / 송광아파트 / 두암아파트`
  - `관리사무소` values are intentionally neutral (`-`); do **not** insert
    unverified public phone numbers.
  - related card: `아파트생활정보` (`하자발생 / 생활요령 / 생활수칙 / 관리비`)
  - search box is `disabled` (static demo only, no external request)
- **right-panel quest card**
  - `quest_card_type`: `action_plan`
  - action labels include `아파트정보 화면 이동`, `아파트생활정보 관련 안내 확인`
  - text includes `STOP_FOR_USER_CONFIRMATION`, `local_static`
- **prohibited behavior**
  - Must **not** regress to a generic `공동주택과 전화번호 lookup` (북구소개 > 구청안내 > 업무 및 전화번호 안내) surface.
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
  `여기로` app / 북구청 홁페이지 신청 (reflected as handoff note, not a live action)
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

## 4. move_in_report_guidance — 전입신고 안내

- **primary official_path**
  `북구청 홈 > 종합민원 > 전자민원창구 > 정부24`
- **related / handoff path**
  `정부24` (external) — the demo stops before any action; user proceeds on the
  real Government24 / 주민센터 channel
- **source_mode**: `local_static`
- **stop_condition**: `STOP_FOR_USER_CONFIRMATION`
- **left surface fidelity**
  - LNB: `종합민원` with sub-items
    `종합민원 / 전자민원창구 / 민원서식 / 민원 신청(active)`
  - body: `정부24 전입신고 연결 안내` (handoff), no internal 신청 page simulation
- **right-panel quest card**
  - `quest_card_type`: `action_plan`
  - action labels include `정부24 전입신고 연결 안내 화면 이동`, `정부24 전입신고 연결 안내 카드 확인`
  - text includes `STOP_FOR_USER_CONFIRMATION`, `local_static`
- **prohibited behavior**
  - Must **not** present a 북구청-internal `전입신고 신청` page (form-filling) surface.
  - No real Government24 navigation or request, no 본인인증 / 세대주·주소·가족관계 input,
    no submission.
- **E2E verifier**: `tests/browser/verify_move_in_quest_e2e.mjs`

---

## 5. public_health_center_guidance — 보건소 위치·진료 안내

- **primary official_path**
  `북구청 홈 > 보건소 > 보건소소개 > 찾아오시는 길`
- **related / handoff path**
  보건소 공식 채널 (location / hours / departments / vaccination / tests)
- **source_mode**: `local_static`
- **stop_condition**: `STOP_FOR_USER_CONFIRMATION`
- **left surface fidelity**
  - LNB: `보건소` with sub-items
    `보건소소개 / 진료안내 / 예방접종 / 검사 / 민원 / 찾아오시는 길(active)`
  - body: location, operating hours, departments, vaccination, tests info
- **right-panel quest card**
  - `quest_card_type`: `action_plan`
  - action labels include `보건소 위치·진료 안내 화면 이동`, `보건소 위치·진료 안내 카드 확인`
  - text includes `STOP_FOR_USER_CONFIRMATION`, `local_static`
- **prohibited behavior**
  - No 의료 판단 / 진단 / 처방 / 응급 판단 / 예약 simulation.
  - No 본인인증 / 건강정보 input, no appointment/prescription submission.
- **E2E verifier**: `tests/browser/verify_public_health_center_quest_e2e.mjs`

---

## Regression guardrails (enforced by tests)

`tests/test_mvp_golden_quest_fidelity_matrix.py` asserts, for every locked quest:

- the `quest_id` exists in the registry
- `official_path` matches the locked value exactly
- `source_mode == "local_static"`
- `ai_can_prefill == false`
- `ai_can_submit == false`
- `stop_condition == "STOP_FOR_USER_CONFIRMATION"`
- the expected route / action labels are present at a high level
- the quest has **not** regressed to prohibited wording (e.g. invented internal
  submission-form paths, payment/sticker issuance, generic department lookup,
  diagnosis/prescription/appointment flows)

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
