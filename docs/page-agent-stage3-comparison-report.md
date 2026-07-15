# Page Agent형 vs 정밀 구현형 비교 데모 — Stage 3 비교 증거 보고서

- **Track**: #1109 — experiment(page-agent): parity Buk-gu AI demo and comparison track
- **Stage**: 3 — comparison harness and evidence (refreshed for #1145 parity integration)
- **Date**: 2026-07-15
- **Owner**: Computer 2
- **Branch**: `feat/1145-page-agent-parity-integration`
- **Base SHA**: `5ad20ad027f993cb522a49c90f39523211e6c5cd`
- **Evidence**: `docs/artifacts/1109-stage3-comparison/comparison-evidence.json`
- **Evidence generated_at**: `2026-07-15T06:37:53.848Z`

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
- **Current methodology**: offline/static-build parity comparison with a deterministic resident mock adapter for Page Agent (not a live LLM provider)

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

현재 30-run evidence 기준으로 **route/success 실패는 없다**. 남아 있는 gap은 구현 설계 차이와 mock 범위다.

1. **complaint_screen / deterministic trigger mapping**: 정확히 일치하는 journey가 없어 `streetlight_report`(가로등 고장 신고)로 대체 실행한다. 기대 route(`complaint-write`)와 pass criteria는 통과하지만, 의도한 "민원 작성 화면 열기" 범위와 트리거 시맨틱이 완전히 동일하지는 않다. 향후 전용 journey 추가가 필요하다.

2. **Mock adapter scope**: Page Agent 모드는 실제 LLM이 아니라 deterministic resident mock adapter를 사용한다. action 선택 품질, 경로 이탈율, 에러 복구 등 live LLM 지표는 이 비교의 대상이 아니다.

3. **Action-step / elapsed 정의 차이**: deterministic은 choreography step과 의도된 UI animation delay를, page_agent는 tool call 기반 step을 기록한다. elapsed와 action step 수치는 구조가 다르므로 직접 비교해 승패를 가리지 않는다.

4. **실행 범위**: harness는 Chrome + `dist/cloudflare-pages` 정적 빌드(localhost) 범위다. 다른 브라우저, live Functions, 실제공식 사이트 제어는 포함되지 않는다.

---

## Aggregate 결과 (30 runs)

| 지표 | Deterministic | Page Agent |
|------|--------------|------------|
| 총 실행 | 15 | 15 |
| 성공 | 15 | 15 |
| 실패 | 0 | 0 |
| 성공률 | 100% | 100% |
| Median elapsed (ms) (All runs) | 17,660 | 2,068 |
| Median elapsed (ms) (Successful runs only) | 17,660 | 2,068 |
| Median action steps (All runs) | 4 | 1 |
| Median action steps (Successful runs only) | 4 | 1 |
| Total wrong route actions | 0 | 0 |
| 외부 요청 | 0 | 0 |
| No-submit 위반 | 0 | 0 |

*(상세 집계는 evidence JSON 파일의 aggregate 필드 참조. elapsed는 intentional delay / mock path 차이로 직접 비교 대상이 아니다.)*

### Overall (both modes, 30 runs)

| 지표 | 값 |
|------|-----|
| 총 실행 / 성공 / 실패 | 30 / 30 / 0 |
| 성공률 | 100% |
| Median elapsed (ms) — All runs | 4,286 |
| Median elapsed (ms) — Successful runs only | 4,286 |
| Median action steps — All runs | 2 |
| Median action steps — Successful runs only | 2 |
| Total wrong route actions | 0 (deterministic 0 + page_agent 0) |
| Console error (합계) | 0 |
| Page error (합계) | 0 |
| HTTP error responses (합계) | 0 |
| Request failure (합계) | 0 |
| External request (합계) | 0 |
| No-submit 위반 | 0 |
| Reproducibility | true |

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

현재 evidence 기준 **primary run 실패는 0건**이다.

- deterministic: 15/15 성공, wrong route 0
- Page Agent: 15/15 성공, wrong route 0
- 외부 요청 / request failure / console error / page error / no-submit 위반: 모두 0
- reproducibility: true

남아 있는 이슈는 실패가 아니라 설계 gap이다: complaint_screen deterministic trigger가 `streetlight_report` 매핑을 사용하고, Page Agent는 live LLM이 아닌 mock adapter이며, elapsed/action-step 정의가 모드마다 다르다.

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

1. **Elapsed time 불일치**: deterministic 모드는 의도적인 UI animation delay(thinking text, cursor animation, typing simulation)를 포함하므로 elapsed_ms가 page_agent보다 크게 나타난다. 이는 LLM latency나 엔진 성능 차이가 아니라 의도된 demo UX 설계 때문이다. elapsed times are not directly comparable.

2. **Mock vs Real**: Page Agent 모드는 실제 LLM이 아니라 deterministic resident mock adapter를 사용한다. 따라서 action 선택 품질, 경로 이탈율, 에러 복구 등 LLM 관련 지표는 이 비교의 대상이 아니다.

3. **Action step 정의 차이**: deterministic 모드는 choreography step을, page_agent 모드는 Page Agent tool call을 각각 action_step으로 카운트한다. 두 정의는 구조가 다르므로 직접 비교할 수 없다.

4. **Trigger 불일치**: deterministic 모드의 JOURNEY_MAP은 canonical parity 문구와 다른 trigger key를 사용한다. 이로 인해 complaint_screen 시나리오는 deterministic에서 가장 유사한 journey(streetlight_report)로 대체되었다.

5. **Coverage gap**: deterministic 모드는 complaint_screen 시나리오에 정확히 일치하는 journey가 없다. 가장 가까운 streetlight_report journey로 실행했으며, 이는 "민원 작성 화면 열기"와 범위가 다르다.

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

## Stage 5 Live-Provider Validation

- Status: BLOCKED / NOT EXECUTED
- No live provider/API call was performed.
- Execution requires separate explicit owner approval, provider selection,
  credential configuration, cost boundary, and controlled-live validation scope.
- The current result is offline/mock parity evidence only.

---

## 결론

수정된 harness와 #1145 parity 통합 이후 30회 비교 실행 증거:

- **총 실행 / 성공 / 실패**: 30 / 30 / 0 (성공률 100%)
- **모드별 성공**: deterministic 15/15, Page Agent 15/15
- **Wrong route**: deterministic 0, Page Agent 0
- **Safety**: external requests 0, request failures 0, console errors 0, page errors 0, no-submit 위반 0
- **Reproducibility**: true
- **Pass criteria 평가**: 공유 pass criteria를 DOM canvas route·텍스트 증거로 평가
- **Action trace**: deterministic median action steps 4, page_agent median action steps 1 (정의가 다르므로 직접 비교하지 않음)
- **No-submit**: 30/30 run에서 실제 제출 없음 확인

**남아 있는 parity gap (실패가 아닌 설계 한계)**:
- complaint_screen deterministic trigger는 `streetlight_report` 매핑을 사용
- Page Agent는 deterministic resident mock adapter (not a real LLM)
- elapsed time과 action-step 정의는 모드 간 직접 비교 대상이 아님
- Chrome + static-build 범위

**위너 선언 없음** — 성공률이 동일(100%)하고 safety 지표도 동일하므로, 이 결과는 offline/mock parity 증거일 뿐 한 모드의 우수성을 주장하지 않는다. Stage 5 live-provider validation은 BLOCKED / NOT EXECUTED 상태다.
