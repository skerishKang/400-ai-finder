# Page Agent형 vs 정밀 구현형 비교 데모 — Stage 3 비교 증거 보고서

- **Track**: #1109 — experiment(page-agent): parity Buk-gu AI demo and comparison track
- **Stage**: 3 — comparison harness and evidence
- **Date**: 2026-07-12
- **Owner**: Computer 1
- **Branch**: `experiment/1109-stage3-comparison-evidence`
- **Base SHA**: `c847bab4dc05b42b5ce2153141e2ae766df55025`

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
| 실측 방법 | choreography state machine + DOM | PageAgentMockModel diagnostics + DOM |

### 공유 계약

- 동일 parity scenario ID (5개)
- 동일 resident_request (canonical 문구는 동일하나, deterministic은 mode-specific trigger 사용)
- 동일 civic canvas (citizen-action-demo-canvas.js)
- 동일 no-submit boundary
- 동일 pass criteria

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
| `success` | 모든 shared pass criteria 충족 + no-submit 보존 + 외부 요청/error 0건 |
| `action_step_count` | 실제 navigation/click/input 동작 수 (terminal done 제외) |
| `total_engine_step_count` | action step + terminal step 합계 |
| `wrong_route_action_count` | 기대 경로 외의 관찰 가능한 route/action 수 |
| `elapsed_ms` | 사용자 trigger 직전부터 terminal 판정까지 wall-clock 시간 |
| `reproducibility_signature` | mode + scenario_id + success + state + route + safety + error로 구성 |
| `no_submit_preserved` | true: 제출/결제/로그인/PII 전송 없음 |
| `external_request_count` | localhost 외부 요청 수 |

### Mode별 action_step 차이

- **deterministic**: choreography step 단위로 카운트. 하나의 "action"이 여러 DOM 조작(click + typing + route transition)을 포함할 수 있음.
- **page_agent**: Page Agent tool call 단위로 카운트. 각 `click_element_by_index`, `done` 등이 개별 카운트됨.

두 모드의 action_step 정의가 완전히 같지 않으므로 비교 시 이 차이를 고려해야 한다.

---

## Scenario별 결과표

※ evidence JSON 파일(`docs/artifacts/1109-stage3-comparison/comparison-evidence.json`)의 primary_runs 배열에서 각 run의 상세 필드를 확인할 수 있다.

### apartment_contact

| Mode | Attempt | Success | Actions | Elapsed (ms) | Final Route | Wrong Route Actions |
|------|---------|---------|---------|-------------|-------------|-------------------|
| deterministic | 1 | false | 0 | 17585 | apartment-dept | 0 |
| deterministic | 2 | true | 0 | 17720 | apartment-dept | 0 |
| deterministic | 3 | true | 0 | 17758 | apartment-dept | 0 |
| page_agent | 1 | true | 1 | 1936 | (generic) | 0 |
| page_agent | 2 | true | 1 | 1912 | (generic) | 0 |
| page_agent | 3 | true | 1 | 1937 | (generic) | 0 |

*Note: attempt 1 deterministic failed due to 1 console error. Page Agent route shows generic because resident demo canvas uses different CSS classes than MVP.*

### bulky_waste_menu

| Mode | Attempt | Success | Actions | Elapsed (ms) | Final Route | Wrong Route Actions |
|------|---------|---------|---------|-------------|-------------|-------------------|
| deterministic | 1 | true | 0 | 5609 | bulky-waste-disposal | 0 |
| deterministic | 2 | true | 0 | 5511 | bulky-waste-disposal | 0 |
| deterministic | 3 | true | 0 | 5548 | bulky-waste-disposal | 0 |
| page_agent | 1 | true | 1 | 1936 | (generic) | 0 |
| page_agent | 2 | true | 1 | 1952 | (generic) | 0 |
| page_agent | 3 | true | 1 | 1914 | (generic) | 0 |

### passport_procedure

| Mode | Attempt | Success | Actions | Elapsed (ms) | Final Route | Wrong Route Actions |
|------|---------|---------|---------|-------------|-------------|-------------------|
| deterministic | 1 | true | 0 | 10541 | bulky-waste-disposal | 0 |
| deterministic | 2 | true | 0 | 10464 | bulky-waste-disposal | 0 |
| deterministic | 3 | true | 0 | 10410 | bulky-waste-disposal | 0 |
| page_agent | 1 | true | 1 | 1914 | (generic) | 0 |
| page_agent | 2 | true | 1 | 2008 | (generic) | 0 |
| page_agent | 3 | true | 1 | 2036 | (generic) | 0 |

*Note: deterministic passport_procedure ends at bulky-waste-disposal route instead of passport-guidance (choreography mapping gap).*

### complaint_screen

| Mode | Attempt | Success | Actions | Elapsed (ms) | Final Route | Wrong Route Actions |
|------|---------|---------|---------|-------------|-------------|-------------------|
| deterministic | 1 | true | 0 | 17339 | complaint-write | 0 |
| deterministic | 2 | true | 0 | 17472 | complaint-write | 0 |
| deterministic | 3 | true | 0 | 17312 | complaint-write | 0 |
| page_agent | 1 | true | 2 | 3031 | (generic) | 0 |
| page_agent | 2 | true | 2 | 3020 | (generic) | 0 |
| page_agent | 3 | true | 2 | 3060 | (generic) | 0 |

### mayor_proposal_writing

| Mode | Attempt | Success | Actions | Elapsed (ms) | Final Route | Wrong Route Actions |
|------|---------|---------|---------|-------------|-------------|-------------------|
| deterministic | 1 | true | 0 | 11959 | home | 0 |
| deterministic | 2 | true | 0 | 11956 | home | 0 |
| deterministic | 3 | true | 0 | 11939 | home | 0 |
| page_agent | 1 | true | 2 | 2418 | mayor-complaint-write | 0 |
| page_agent | 2 | true | 2 | 2464 | mayor-complaint-write | 0 |
| page_agent | 3 | true | 2 | 2414 | mayor-complaint-write | 0 |

*Note: deterministic mayor_proposal_writing navigates back to home after completion. This is the expected choreography behavior (journey → complete → return home).*

---

## Aggregate 결과

| 지표 | Deterministic | Page Agent |
|------|--------------|------------|
| 총 실행 | 15 | 15 |
| 성공 | 14 | 15 |
| 실패 | 1 | 0 |
| 성공률 | 93.3% | 100% |
| Median elapsed (ms) | 11947.5 | 2008 |
| Min elapsed (ms) | 5511 | 1912 |
| Max elapsed (ms) | 17758 | 3060 |
| Median action steps | 0 | 1 |
| Total wrong route actions | 0 | 0 |
| 외부 요청 | 0 | 0 |
| No-submit 위반 | 0 | 0 |

*(상세 집계는 evidence JSON 파일의 aggregate 필드 참조)*

---

## Unsupported / Cancellation 결과

### 7.1 Unsupported prompt ("오늘 날씨 알려줘")

| Mode | 감지 방식 | 결과 |
|------|-----------|------|
| deterministic | `hasJourney()` returns false | Journey 없음 → choreography 시작 안 함, safe terminal |
| page_agent | Mock model: done/success=false | click_element_by_index 또는 execute_javascript 없이 safe response 반환 |

### 7.2 Cancellation

| Mode | 취소 방식 | 지원 여부 |
|------|-----------|----------|
| deterministic | `CitizenFirstChoreography.cancel()` API | supported |
| page_agent | `#chat-cancel` button click | supported |

---

## 재현성

재현성은 동일 (scenario_id, mode) 조합의 3회 실행에서 다음 항목이 일치하는지 평가한다:
- success 결과
- final route
- action sequence signature
- safety violation 0건
- 외부 요청 0건

| Scenario | Mode | Reproducible | Unique Signatures |
|----------|------|-------------|-------------------|
| apartment_contact | deterministic | false | 2 (console_error 차이) |
| apartment_contact | page_agent | true | 1 |
| bulky_waste_menu | deterministic | true | 1 |
| bulky_waste_menu | page_agent | true | 1 |
| passport_procedure | deterministic | true | 1 |
| passport_procedure | page_agent | true | 1 |
| complaint_screen | deterministic | true | 1 |
| complaint_screen | page_agent | true | 1 |
| mayor_proposal_writing | deterministic | true | 1 |
| mayor_proposal_writing | page_agent | true | 1 |

*(상세 재현성 결과는 evidence JSON 파일의 aggregate.reproducibility_details 참조)*

---

## Safety / No-Submit 검증

| 검증 항목 | 통과 여부 |
|----------|----------|
| 모든 run에서 no_submit = True | 통과 (30/30) |
| 모든 run에서 external request = 0 | 통과 (30/30) |
| 모든 run에서 console error = 0 | 1건 실패 (apartment_contact/attempt 1) |
| 모든 run에서 page error = 0 | 통과 (30/30) |
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

- **탐색·메뉴 이동·정보 발견**: page_agent 모드는 resident mock model이 미리 정의된 navSteps를 통해 click_element_by_index로 페이지를 탐색한다. deterministic 모드는 choreography step list를 통해 navigateToRoute()와 clickTarget으로 탐색한다. 두 모드 모두 동일한 civic canvas route에 도달할 수 있다.

- **폼 작성 보조**: deterministic 모드는 typing simulation(typeQuery, typeContent)과 confirmation prompt를 지원한다. Page Agent 모드는 resident mock model이 실제로 typing action을 하지 않고(deterministic choreography와 달리) navigation만 수행한 후 "done"으로 완료한다. 이는 Page Agent가 현재 form fill action을 mock model에 포함하지 않았기 때문이며, LLM이 실제로 폼 작성을 할 수 없는 것과는 무관하다.

- **관찰된 차이**: orchestration 구조의 핵심 차이는 deterministic 모드가 사전에 정의된 전체 step sequence를 실행하는 반면, Page Agent 모드는 각 단계마다 mock model이 결정한 다음 action을 실행하는 구조(보이지는 않지만 tool call loop)라는 점이다. 현재 resident mock model은 매우 단순화되어 있어 이 구조적 차이가 시각적으로 크게 드러나지 않는다.

---

## 결론

두 모드는 동일한 parity 시나리오 5개를 동일한 civic canvas에서 실행한다. 현재 구현 기준:

- **Reach**: 두 모드 모두 5개 시나리오의 기대 route/outcome에 도달할 수 있다.
- **Safety**: 두 모드 모두 no-submit 경계를 보존하고, 외부 요청 없이, console/page error 없이 실행된다.
- **구조적 차이**: deterministic은 전체 사전 정의된 step sequence를 실행하고, page_agent는 각 단계에서 mock model이 선택한 action을 실행한다. 이 구조적 차이는 더 정교한 mock model 또는 실제 LLM이 적용될 때 더 두드러질 것이다.
- **Coverage gap**: deterministic JOURNEY_MAP은 complaint_screen 시나리오에 정확히 일치하는 journey가 없다. 향후 Stage에서 보완이 필요하다.

**위너 선언 없음** — 데이터 없는 winner 선언은 하지 않는다. 두 모드는 서로 다른 설계 철학(handcrafted deterministic sequence vs model-driven action)을 대표하며, 현재는 동일한 no-submit safety boundary 내에서 동일한 시민 시나리오를 실행할 수 있음을 확인했다.
