# Page Agent형 vs 정밀 구현형 비교 데모 — Stage 3 비교 증거 보고서

- **Track**: #1109 — experiment(page-agent): parity Buk-gu AI demo and comparison track
- **Stage**: 3 — comparison harness and evidence (수정됨)
- **Date**: 2026-07-13
- **Owner**: Computer 2
- **Branch**: `experiment/1109-stage3-comparison-evidence`
- **Base SHA**: `5ad20ad027f993cb522a49c90f39523211e6c5cd`

---

## 목적

정밀 구현형(deterministic MVP choreography)과 Page Agent형(vendored Page Agent runtime + resident mock adapter)이 동일한 parity 시나리오 5개를 실행했을 때의 행동을 비교하고 구조화된 증거를 생성한다. 이 비교는 orchestration 구조와 현재 demo implementation의 차이를 이해하기 위한 것이며, 실제 LLM 품질·비용·latency 비교가 아니다.

### 제한 사항 (미리 명시)

- deterministic 모드는 의도적인 UI animation delay(thinking text, cursor, typing simulation)를 포함하므로 elapsed time이 부풀려진다.
- Page Agent 모드는 실제 LLM이 아니라 deterministic resident mock adapter를 사용한다.
- 따라서 단순 elapsed 차이로 한 모드가 우수하다고 결론 내리지 않는다.

---

## 비교 대상과 동일성 조건

| 항목 | 정밀 구현형 (deterministic) | Page Agent형 |
|------|---------------------------|-------------|
| 제품 라벨 | 정밀 구현형 AI 북구청 | Page Agent형 AI 북구청 |
| 라우트 | `mvp/` | `examples/page-agent/resident/` |
| 엔진 | CitizenFirstChoreography (handcrafted deterministic step list) | Vendored Page Agent runtime + resident mock adapter |
| 상태 | production (기존 MVP) | 실험적 비교 데모 |
| 실행 방식 | CitizenFirstChoreography.start(key) 호출 | 실제 chat input을 통해 PageAgent.execute() |
| 실측 방법 | choreography state machine + DOM action trace + DOM content | PageAgentMockModel diagnostics + DOM content |

### 공유 계약

- 동일 parity scenario ID (5개)
- 동일 resident_request (canonical 문구는 동일하나, deterministic은 mode-specific trigger 사용)
- 동일 civic canvas (citizen-action-demo-canvas.js)
- 동일 no-submit boundary
- 동일 pass criteria (DOM 증거 기반 평가)
- 동일 route expectations (fixture 기반 검증)

### Trigger 차이

deterministic 모드의 JOURNEY_MAP은 canonical parity 문구와 다른 키를 사용한다. 비교 시 evidence에 `canonical_request`와 `actual_trigger`를 모두 기록한다.

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
- **Browser**: Google Chrome (channel), headless
- **Viewport**: 1440x900 (desktop)
- **Artifact**: Cloudflare Pages static build (`dist/cloudflare-pages/`)
- **HTTP Server**: Python http.server, localhost 전용 포트
- **Repetitions**: scenario/mode 조합당 3회 (총 30회 primary runs)

---

## 측정 정의

| 지표 | 정의 |
|------|------|
| `success` | 모든 shared pass criteria 충족 + 기대 route 일치 + no-submit 보존 + 외부 요청/error 0건 |
| `action_step_count` | 실제 navigation/click/input 동작 수 (terminal done 제외) |
| `total_engine_step_count` | deterministic: choreography step 수 / page_agent: diagnostics call 수 |
| `wrong_route_action_count` | 1 if final_route != expected_final_route, else 0 |
| `pass_criteria_results` | parity-contract.json의 각 scenario별 pass criteria를 DOM canvas 텍스트·route 기반으로 평가한 결과 배열 |
| `elapsed_ms` | 사용자 trigger 직전부터 terminal 판정까지 wall-clock 시간 |
| `reproducibility_signature` | mode + scenario_id + success + state + route + safety + error로 구성 |
| `no_submit_preserved` | true: 제출/결제/로그인/PII 전송 없음 |
| `external_request_count` | localhost 외부 요청 수 |

### Pass criteria 평가 방식

각 pass criterion은 DOM canvas의 `final_route`와 `innerText`를 기반으로 평가된다:

- **routeMatches(expectedRoutes, keywords)**: final_route가 expectedRoutes 중 하나이거나 canvasText에 keywords 중 하나가 포함되면 통과
- **textContains(keywords)**: canvasText에 keywords 중 하나가 포함되면 통과
- **textExcludes(keywords)**: canvasText에 keywords 중 어떤 것도 포함되지 않으면 통과

이 평가는 deterministic과 page_agent 두 모드에 동일하게 적용된다.

---

## 수정된 측정 항목

초기 harness 대비 다음 항목이 수정되었다:

1. **pass_criteria_results**: harness 초기 버전에서는 빈 배열 또는 harness-specific criterion(terminal_state_safe, no_submit_badge 등)만 기록했으나, 수정된 버전에서는 parity-contract.json의 **공유 pass criteria**를 실제 DOM 증거(canvas route + 텍스트)로 평가한다.

2. **Route 검증**: `final_route`를 expectations fixture의 `expected_final_route`와 비교하여 `wrong_route_action_count`를 계산하고, route 불일치 시 `success = false`가 된다.

3. **Deterministic action trace**: `CitizenFirstChoreography`에 `getCurrentStepIndex()`, `getTotalSteps()`, `getSteps()` API를 추가하여 deterministic 모드의 `action_step_count`, `total_engine_step_count`, `action_sequence`를 실제로 기록한다.

4. **No-submit 강제 true 제거**: `record.no_submit_preserved = true` 강제 할당을 제거하고, 실제 상태 머신 terminal state + DOM badge 검사 결과를 사용한다.

5. **CI test weakening 제거**: `|| echo` conditional failure suppression을 제거했다.

6. **Evidence 검증 강화**: CI evidence 검증 스크립트와 offline test가 pass_criteria_results, action_step_count 일관성, wrong_route_action_count 집계를 검사한다.

---

## 예상 시나리오별 route

| Scenario | Mode | Expected Route |
|----------|------|---------------|
| apartment_contact | deterministic | apartment-dept (부서 디렉토리 뷰) |
| apartment_contact | page_agent | apartment-dept |
| bulky_waste_menu | deterministic | bulky-waste-disposal |
| bulky_waste_menu | page_agent | bulky-waste-disposal |
| passport_procedure | deterministic | passport-guidance |
| passport_procedure | page_agent | passport-guidance |
| complaint_screen | deterministic | complaint-write |
| complaint_screen | page_agent | complaint-write |
| mayor_proposal_writing | deterministic | mayor-complaint-write |
| mayor_proposal_writing | page_agent | mayor-complaint-write |

---

## Unsupported / Cancellation 결과

### Unsupported prompt ("오늘 날씨 알려줘")

| Mode | 감지 방식 | 결과 |
|------|-----------|------|
| deterministic | `hasJourney()` returns false | Journey 없음 → choreography 시작 안 함, safe terminal |
| page_agent | Mock model: done/success=false | click_element_by_index 또는 execute_javascript 없이 safe response 반환 |

### Cancellation

| Mode | 취소 방식 | 지원 여부 |
|------|-----------|----------|
| deterministic | `CitizenFirstChoreography.cancel()` API | supported |
| page_agent | `#chat-cancel` button click | supported |

---

## 알려진 Parity Gap

1. ~~passport_procedure / deterministic: 기대 route는 `passport-guidance`이나 `bulky-waste-disposal`로 잘못 탐지됨~~ → **해결됨**. Canvas route 클래스 매핑에서 `bg-page--official-content`가 bulky-waste로 우선 분류되던 문제를 수정했다. 새 evidence에서는 passport_procedure가 `passport-guidance` route로 정상 탐지된다.

2. **complaint_screen / deterministic**: 정확히 일치하는 journey가 없어 `streetlight_report`(가로등 고장 신고)로 대체 실행. pass criteria는 통과할 수 있으나 의도한 "민원 작성 화면 열기" 범위와 다름. 향후 Stage에서 전용 journey 추가가 필요.

3. **Page Agent canvas route**: resident mock model이 canvas navigation을 route API 대신 click_element_by_index로만 수행하므로, canvas의 bg-page--* class가 제대로 갱신되지 않아 route detection이 실패할 수 있음. mayor_complaint_write는 canvas route가 정상 탐지됨.

---

## Aggregate 결과 (30 runs)

| 지표 | Deterministic | Page Agent |
|------|--------------|------------|
| 총 실행 | 15 | 15 |
| 성공 | 12 | 3 |
| 실패 | 3 | 12 |
| 성공률 | 80.0% | 20.0% |
| Median elapsed (ms) (All runs) | 11,875 | 1,962 |
| Median elapsed (ms) (Successful runs only) | 13,927.5 | 2,420 |
| Median action steps (All runs) | 4 | 1 |
| Median action steps (Successful runs only) | 4 | 2 |
| Total wrong route actions | 3 | 12 |
| 외부 요청 | 0 | 0 |
| No-submit 위반 | 0 | 0 |

*(상세 집계는 evidence JSON 파일의 aggregate 필드 참조)*

### Overall (both modes, 30 runs)

| 지표 | 값 |
|------|-----|
| 총 실행 / 성공 / 실패 | 30 / 15 / 15 |
| 성공률 | 50.0% |
| Median elapsed (ms) — All runs | 4,281 |
| Median elapsed (ms) — Successful runs only | 10,498 |
| Median action steps — All runs | 2 |
| Median action steps — Successful runs only | 4 |
| Total wrong route actions | 15 (deterministic 3 + page_agent 12) |
| Console error (합계) | 0 |
| Page error (합계) | 0 |
| HTTP error responses (합계) | 0 |
| Request failure (합계) | 0 |
| External request (합계) | 0 |
| No-submit 위반 | 0 |

### Scenario별 결과

| Scenario | Mode | 성공/전체 | 관찰된 Route (3회) | Wrong Route |
|----------|------|----------|-------------------|-------------|
| apartment_contact | deterministic | 3/3 | apartment-dept | 0 |
| apartment_contact | page_agent | 0/3 | official-content | 3 |
| bulky_waste_menu | deterministic | 3/3 | bulky-waste-disposal | 0 |
| bulky_waste_menu | page_agent | 0/3 | official-content | 3 |
| passport_procedure | deterministic | 3/3 | passport-guidance | 0 |
| passport_procedure | page_agent | 0/3 | official-content | 3 |
| complaint_screen | deterministic | 3/3 | complaint-write | 0 |
| complaint_screen | page_agent | 0/3 | official-content | 3 |
| mayor_proposal_writing | deterministic | 0/3 | home | 3 |
| mayor_proposal_writing | page_agent | 3/3 | mayor-complaint-write | 0 |

#### Failure 분석

**Deterministic mayor_proposal_writing (0/3)**: choreography 완료 후 `mayor-complaint-write`가 아닌 `home` route로 복귀. 기대 route 불일치로 wrong_route=3.

**Page Agent (4/5 scenarios 0/3)**: canvas route가 `official-content`로 탐지되어 거의 모든 시나리오에서 route 불일치 발생. `mayor-complaint-write`만 유일하게 canvas route가 정상 탐지됨.

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

1. **Elapsed time 불일치**: deterministic 모드는 의도적인 UI animation delay(thinking text, cursor animation, typing simulation)를 포함하므로 elapsed_ms가 page_agent보다 크게 나타난다. 이는 LLM latency나 엔진 성능 차이가 아니라 의도된 demo UX 설계 때문이다.

2. **Mock vs Real**: Page Agent 모드는 실제 LLM이 아니라 deterministic resident mock adapter를 사용한다. 따라서 action 선택 품질, 경로 이탈율, 에러 복구 등 LLM 관련 지표는 이 비교의 대상이 아니다.

3. **Action step 정의 차이**: deterministic 모드는 choreography step을, page_agent 모드는 Page Agent tool call을 각각 action_step으로 카운트한다. 두 정의는 구조가 다르므로 직접 비교할 수 없다.

4. **Trigger 불일치**: deterministic 모드의 JOURNEY_MAP은 canonical parity 문구와 다른 trigger key를 사용한다. 이로 인해 complaint_screen 시나리오는 deterministic에서 가장 유사한 journey(streetlight_report → complaint-board-write)로 대체되었다.

5. **Coverage gap**: deterministic 모드는 complaint_screen 시나리오에 정확히 일치하는 journey가 없다. 가장 가까운 streetlight_report(report streetlight malfunction) journey로 실행했으며, 이는 "민원 작성 화면 열기"와 범위가 다르다.

6. **Chrome 전용**: harness는 Playwright + Chrome/Chromium에서만 검증되었다. 다른 브라우저에서의 동작은 보장되지 않는다.

7. **로컬 빌드 전용**: 모든 테스트는 `dist/cloudflare-pages` 정적 빌드에서 실행되었다. live 모드 또는 Cloudflare Pages Functions 환경은 테스트되지 않았다.

---

## Hybrid Boundary 관찰

증거 기반 hybrid boundary 검토:

- **고위험·공식 완료·제출 직전**: 두 모드 모두 **no-submit 경계를 보존**한다. 실제 제출·결제·로그인은 발생하지 않았다. deterministic 모드는 명시적인 `requiresConfirmation` 단계에서 멈추고, page_agent 모드는 DOM click navigation만 수행하고 실제 form submission은 하지 않는다.

- **탐색·메뉴 이동·정보 발견**: page_agent 모드는 resident mock model이 미리 정의된 navSteps를 통해 click_element_by_index로 페이지를 탐색한다. deterministic 모드는 choreography step list를 통해 navigateToRoute()와 clickTarget으로 탐색한다.

- **폼 작성 보조**: deterministic 모드는 typing simulation(typeQuery, typeContent)과 confirmation prompt를 지원한다. Page Agent 모드는 resident mock model이 실제로 typing action을 하지 않고 navigation만 수행한 후 "done"으로 완료한다.

- **관찰된 차이**: orchestration 구조의 핵심 차이는 deterministic 모드가 사전에 정의된 전체 step sequence를 실행하는 반면, Page Agent 모드는 각 단계마다 mock model이 결정한 다음 action을 실행하는 구조라는 점이다.

---

## 결론

수정된 harness로 30회 비교 실행을 완료했다. 핵심 측정 결과:

- **Pass criteria 평가**: 각 run의 3개 pass criteria를 DOM canvas route와 텍스트 증거로 실제 평가. criterion별 `passed: true/false`와 `evidence` 문자열 기록 완료.
- **Route 검증**: `final_route`를 expectations fixture의 `expected_final_route`와 비교. deterministic 3건, page_agent 12건의 route 불일치 탐지.
- **Action trace 기록**: deterministic action step count median 4 (all/success 동일), page_agent median 1 (all) / 2 (success only). Choreography step과 tool call의 구조적 차이 반영.
- **No-submit**: 30/30 run에서 실제 제출 없음 확인. 강제 true 없이 상태 머신 + DOM badge로 검증.
- **Console error**: 30/30 run 모두 0건. Fresh static build 기준, 브라우저 자동 `/favicon.ico` 요청(벤ign resource 404)은 애플리케이션 console error 계측에서 제외됨.
- **Request failure**: 30/30 run 모두 0건.
- **외부 요청**: 모든 run에서 0건.

**알려진 parity gap**:
- deterministic mayor_proposal_writing: 완료 후 home으로 복귀하여 route 불일치 (3/15 wrong route의 전부)
- Page Agent canvas route: 4/5 시나리오에서 `official-content`로 탐지되어 route 검증 실패 (12/15 wrong route)
- complaint_screen: deterministic에 정확히 일치하는 journey 없음 (streetlight_report로 대체)

**위너 선언 없음** — 단순 성공률(det 80.0% vs pa 20.0%)과 elapsed time 차이로 한 모드가 우수하다고 결론 내리지 않는다. 두 모드는 서로 다른 설계 철학을 대표하며, 수정된 harness는 더 엄격한 pass criteria 평가와 route 검증을 제공한다. 모든 변경사항은 `experiment/1109-stage3-comparison-evidence` 브랜치에 additive commit으로 커밋되었다.
