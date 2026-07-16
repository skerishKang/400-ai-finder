# Page Agent형 vs 정밀 구현형 비교 데모 — Phase B 비교 증거 보고서

- **Track**: #1109 / #1145 — stakeholder comparison gate and five-scenario parity
- **Stage**: Phase B (merged with #1170 / PR #1182 home fixture renderer)
- **Date**: 2026-07-16
- **Owner**: Computer 1-2
- **Branch**: `feat/1145-page-agent-final-parity`
- **Merged main SHA**: `2cc1e7d4a317a4859e2c24384d046f74a27af801`
- **Evidence (canonical Phase B)**: `docs/artifacts/1109-stage3-comparison/comparison-evidence.json`
- **Evidence generated_at**: `2026-07-16T02:45:53.138Z`
- **Phase A offline artifacts (pre-#1170 merge)**: `docs/artifacts/1145-phase-a/` — historical baseline only; not the Phase B verdict

---

## 목적

정밀 구현형(deterministic MVP choreography)과 Page Agent형(vendored Page Agent runtime + resident mock adapter)이 동일한 parity 시나리오 5개를 실행했을 때의 행동을 비교하고 구조화된 증거를 생성한다. 이 비교는 orchestration 구조와 현재 demo implementation의 차이를 이해하기 위한 것이며, 실제 LLM 품질·비용·latency 비교가 아니다.

### 제한 사항 (미리 명시)

- deterministic 모드는 의도적인 UI animation delay(thinking text, cursor, typing simulation)를 포함하므로 elapsed time이 부풀려진다.
- Page Agent 모드는 실제 LLM이 아니라 deterministic resident mock adapter를 사용한다.
- 따라서 단순 elapsed 차이로 한 모드가 우수하다고 결론 내리지 않는다.
- Phase A evidence / production browser baseline과 이 Phase B offline static-build evidence는 목적이 다르다.

---

## 비교 대상과 동일성 조건

| 항목 | 정밀 구현형 (deterministic) | Page Agent형 |
|------|---------------------------|-------------|
| 제품 라벨 | 정밀 구현형 AI 북구청 | Page Agent형 AI 북구청 |
| 라우트 | `mvp/` | `examples/page-agent/resident/` |
| 비교 게이트 | `/compare/` primary card | `/compare/` primary card |
| 엔진 | CitizenFirstChoreography (handcrafted deterministic step list) | Vendored Page Agent runtime + resident mock adapter |
| 상태 | production (기존 MVP) | offline/mock 비교 데모 |
| 실행 방식 | CitizenFirstChoreography.start(key) 호출 | 실제 chat input을 통해 PageAgent.execute() |
| 실측 방법 | choreography state machine + DOM action trace + DOM content | PageAgentMockModel diagnostics + getCurrentRouteId + DOM content |

### 공유 계약

- 동일 parity scenario ID (5개)
- 동일 resident_request (canonical 문구는 동일하나, deterministic은 mode-specific trigger 사용)
- 동일 civic canvas (`citizen-action-demo-canvas.js` + #1170 `bukgu-home-clone-fixture.js`)
- 동일 no-submit boundary
- 동일 pass criteria (DOM 증거 기반 평가)
- 동일 route expectations (fixture 기반 검증)
- Page Agent fail-closed: exact final route + required visible content + mock `lastSuccess===true`
- intermediate routes (`home`, `civil-service`, `complaint-category`, `complaint-board`, `mayor-office`, `official-content`) are never success

### Trigger 차이

| Scenario ID | Canonical Request | Deterministic Trigger | Page Agent Trigger |
|-------------|-------------------|---------------------|-------------------|
| apartment_contact | 공동주택과 연락처 찾아줘 | `housing_department` | 공동주택과 연락처 찾아줘 |
| bulky_waste_menu | 대형폐기물 신청 메뉴 찾아줘 | `bulky_waste` | 대형폐기물 신청 메뉴 찾아줘 |
| passport_procedure | 여권 발급 절차를 찾아줘 | `passport_guidance` | 여권 발급 절차를 찾아줘 |
| complaint_screen | 민원 작성 화면을 열어줘 | `streetlight_report` | 민원 작성 화면을 열어줘 |
| mayor_proposal_writing | 구청장에게 제안할 글 작성을 도와줘 | `mayor_message_assist` | 구청장에게 제안할 글 작성을 도와줘 |

---

## 실행 환경

- **Harness**: `scripts/run_page_agent_comparison.mjs` (Playwright)
- **Browser**: Google Chrome (channel), headless v150.0.7871.115
- **Viewport**: 1440x900 (desktop comparison harness primary)
- **Artifact**: Cloudflare Pages static offline build (`_phaseB_build/`) after merge of #1170
- **HTTP Server**: Python http.server, localhost 전용 포트
- **Repetitions**: scenario/mode 조합당 3회 (총 30회 primary runs)
- **Current methodology**: offline/static-build parity comparison with a deterministic resident mock adapter for Page Agent (not a live LLM provider)

Resident browser E2E (separate): desktop 1440×900 five scenarios + mobile 390×844 surface contract — all passed on the same Phase B build.

---

## 측정 정의

| 지표 | 정의 |
|------|------|
| `success` | 모든 shared pass criteria 충족 + 기대 route 일치 + no-submit 보존 + 외부 요청/error 0건 (+ Page Agent: mock lastSuccess===true) |
| `action_step_count` | 실제 navigation/click/input 동작 수 (terminal done 제외) |
| `total_engine_step_count` | deterministic: choreography step 수 / page_agent: diagnostics call 수 |
| `wrong_route_action_count` | 1 if final_route != expected_final_route, else 0 |
| `pass_criteria_results` | parity-contract.json의 각 scenario별 pass criteria를 DOM canvas 텍스트·route 기반으로 평가한 결과 배열 |
| `elapsed_ms` | 사용자 trigger 직전부터 terminal 판정까지 wall-clock 시간 |
| `reproducibility_signature` | mode + scenario_id + success + state + route + safety + error로 구성 |
| `no_submit_preserved` | true: 제출/결제/로그인/PII 전송 없음 |
| `external_request_count` | localhost 외부 요청 수 |

### Pass criteria 평가 방식

- **routeMatchesExact(expectedRoutes)**: final_route가 expectedRoutes와 정확히 일치해야 통과. 텍스트-only / intermediate route는 실패.
- **textContains(keywords)**: canvasText에 keywords 중 하나가 포함되면 통과
- **textExcludes(keywords)**: canvasText에 keywords 중 어떤 것도 포함되지 않으면 통과
- Route detection prefers `CitizenActionDemoCanvas.getCurrentRouteId()` with DOM marker reconciliation for deterministic housing replay.

---

## Aggregate 결과 (30 runs)

| 지표 | Deterministic | Page Agent |
|------|--------------|------------|
| 총 실행 | 15 | 15 |
| 성공 | 15 | 15 |
| 실패 | 0 | 0 |
| 성공률 | 100% | 100% |
| Median elapsed (ms) (All runs) | 17,664 | 2,032 |
| Median elapsed (ms) (Successful runs only) | 17,664 | 2,032 |
| Median action steps (All runs) | 4 | 1 |
| Median action steps (Successful runs only) | 4 | 1 |
| Total wrong route actions | 0 | 0 |
| 외부 요청 | 0 | 0 |
| No-submit 위반 | 0 | 0 |

*(elapsed는 intentional delay / mock path 차이로 직접 비교 대상이 아니다.)*

### Overall (both modes, 30 runs)

| 지표 | 값 |
|------|-----|
| 총 실행 / 성공 / 실패 | 30 / 30 / 0 |
| 성공률 | 100% |
| Median elapsed (ms) — All runs | (mode-specific; see by_mode) |
| Total wrong route actions | 0 (deterministic 0 + page_agent 0) |
| Console error (합계) | 0 |
| Page error (합계) | 0 |
| HTTP error responses (합계) | 0 |
| Request failure (합계) | 0 |
| External request (합계) | 0 |
| No-submit 위반 | 0 |
| Reproducibility | true |

Mode totals: **deterministic 15/15**, **Page Agent: 15/15**.

### Scenario별 결과

| Scenario | Mode | 성공/전체 | 관찰된 Route (3회) | Wrong Route |
|----------|------|----------|-------------------|-------------|
| apartment_contact | deterministic | 3/3 | apartment-dept | 0 |
| apartment_contact | page_agent | 3/3 | apartment-dept | 0 |
| bulky_waste_menu | deterministic | 3/3 | bulky-waste-disposal | 0 |
| bulky_waste_menu | page_agent | 3/3 | bulky-waste-disposal | 0 |
| passport_procedure | deterministic | 3/3 | passport-guidance | 0 |
| passport_procedure | page_agent | 3/3 | passport-guidance | 0 |
| complaint_screen | deterministic | 3/3 | complaint-write | 0 |
| complaint_screen | page_agent | 3/3 | complaint-write | 0 |
| mayor_proposal_writing | deterministic | 3/3 | mayor-complaint-write | 0 |
| mayor_proposal_writing | page_agent | 3/3 | mayor-complaint-write | 0 |

#### Failure 분석

현재 Phase B evidence 기준 **primary run 실패는 0건**이다.

- deterministic: 15/15 성공, wrong route 0
- Page Agent: 15/15 성공, wrong route 0
- 외부 요청 / request failure / console error / page error / no-submit 위반: 모두 0
- reproducibility: true

---

## Unsupported / Cancellation 결과 (offline harness)

### Unsupported prompt ("오늘 날씨 알려줘")

| Mode | 감지 방식 | 결과 |
|------|-----------|------|
| deterministic | `hasJourney()` returns false | Journey 없음 → choreography 시작 안 함, safe terminal |
| page_agent | Mock model: done/success=false | click 없이 safe response 반환 |

### Cancellation (offline harness, desktop chat-cancel)

| Mode | 취소 방식 | 지원 여부 |
|------|-----------|----------|
| deterministic | `CitizenFirstChoreography.cancel()` API | supported (terminal cancelled) |
| page_agent | `#chat-cancel` button click | supported (terminal 취소됨) |

### Known blocker (#1183 — out of #1145 scope)

Production mobile cancellation was measured separately as **0/6 fail-closed click effectiveness** on production (not fixed here).
#1183 is owned by Computer 1-1. This Phase B branch **does not** modify mobile cancel runtime/CSS/tests/workflows and **does not claim** mobile cancel is fixed.

Offline harness cancellation above uses desktop `#chat-cancel` path and is **not** a substitute for the production mobile cancel defect.

---

## 알려진 Parity Gap

1. **complaint_screen / deterministic trigger mapping**: 정확히 일치하는 journey가 없어 `streetlight_report`로 대체 실행한다.
2. **Mock adapter scope**: Page Agent 모드는 실제 LLM이 아니라 deterministic resident mock adapter를 사용한다.
3. **Action-step / elapsed 정의 차이**: 모드 간 직접 비교로 승패를 가리지 않는다.
4. **#1183 mobile cancel**: production mobile cancel remains a known blocker outside this branch.

---

## Safety / No-Submit 검증

| 검증 항목 | 통과 여부 |
|----------|----------|
| 모든 run에서 no_submit = True | **통과** (30/30) |
| 모든 run에서 external request = 0 | **통과** (30/30) |
| 모든 run에서 console error = 0 | **통과** (30/30) |
| 모든 run에서 request failure = 0 | **통과** (30/30) |
| 모든 run에서 page error = 0 | **통과** (30/30) |
| Unsupported prompt: 외부 요청 없음 | 통과 |
| Unsupported prompt: submit 없음 | 통과 |
| Cancellation: terminal cancelled/중단 | 통과 (deterministic: cancelled, page_agent: 취소됨) |

---

## 한계

1. **Elapsed time 불일치**: deterministic 모드는 의도적인 UI animation delay를 포함하므로 elapsed times are not directly comparable.
2. **Mock vs Real**: Page Agent 모드는 실제 LLM이 아니라 deterministic resident mock adapter를 사용한다.
3. **Action step 정의 차이**: 두 정의는 구조가 다르므로 직접 비교할 수 없다.
4. **Trigger 불일치**: deterministic JOURNEY_MAP 키와 canonical parity 문구가 다를 수 있다.
5. **Chrome 전용**: harness는 Playwright + Chrome/Chromium 범위다.
6. **로컬 빌드 전용**: Phase B evidence는 merged-branch static offline build 범위다.

---

## Hybrid Boundary 관찰

- **고위험·공식 완료·제출 직전**: 두 모드 모두 **no-submit 경계를 보존**한다.
- **탐색·메뉴 이동·정보 발견**: page_agent는 mock navSteps + click_element_by_index; deterministic은 choreography step list.
- **폼 작성 보조**: deterministic은 typing/confirmation; page_agent mock은 navigation + done 중심.

---

## Stage 5 Live-Provider Validation

- Status: BLOCKED / NOT EXECUTED
- No live provider/API call was performed.
- Execution requires separate explicit owner approval, provider selection,
  credential configuration, cost boundary, and controlled-live validation scope.
- The current result is offline/mock parity evidence only.

---

## 결론

#1170 merge 이후 Phase B 30회 offline 비교 실행 증거:

- **총 실행 / 성공 / 실패**: 30 / 30 / 0 (성공률 100%)
- **모드별 성공**: deterministic 15/15, Page Agent 15/15
- **Wrong route**: deterministic 0, Page Agent 0
- **Safety**: external requests 0, request failures 0, console errors 0, page errors 0, no-submit 위반 0
- **Reproducibility**: true
- **#1170 home fixture targets**: resident Page Agent e2e 5/5 유지
- **#1183 mobile cancel**: known blocker (not fixed in this branch)

**위너 선언 없음** — 성공률이 동일(100%)하고 safety 지표도 동일하므로, 이 결과는 offline/mock parity 증거일 뿐 한 모드의 우수성을 주장하지 않는다. Stage 5 live-provider validation은 BLOCKED / NOT EXECUTED 상태다.
