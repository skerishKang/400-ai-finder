# 400 AI Finder 출시·온보딩 게이트

- 상태: `canonical`
- 기준일: 2026-08-12
- 현재 lifecycle/governance 정렬: #1301
- active onboarding validation: #1232
- Buk-gu Frozen Demo closeout: #1235 (`completed`)
- Clone lifecycle canonical: [`docs/product/clone-first-general-site-platform-strategy.md`](../product/clone-first-general-site-platform-strategy.md)
- Exact clone canonical: [`docs/product/exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md)

기능이 동작하거나 CI가 통과했다는 이유만으로 다음 운영단계에 자동 승격하지 않는다.

```text
implemented
!= structural generated preview
!= reference baseline ready
!= faithful clone candidate
!= clone MVP ready
!= exact
!= visually approved
!= deployed
!= live validated
!= production approved
!= actual-site authorized/integrated
```

현재 ordinary pre-integration 제품은 **faithful clone MVP + AI Finder/Browser on the clone**이다. 실제 기관 production 사이트 integration은 기관 승인 후 별도 Gate H에서 시작한다.

## Gate A — Frozen controlled demo

### 목적

북구 golden clone과 결정형 시민 여정을 재현 가능한 데모로 유지한다.

### 필수조건

- exact golden SHA·manifest
- canonical fixture·checksum
- no-submit·no-login·no-payment
- no actual-site control claim
- offline CI
- desktop·mobile browser contract
- accessibility·link safety
- static fallback
- rollback artifact

### 허용

- stakeholder demo
- fixture 기반 안내
- local/static Page Agent comparison
- pre-submit writing assistance

### 비주장

- 실제 민원접수 완료
- actual production-site 운영
- 실제 login/payment/PII integration

## Gate B — Protected public AI pilot

### 목적

공개 URL에서 AI 기능을 실제 운영하려는 경우 비용·abuse·장애 통제를 검증한다.

### historical prerequisite tracks

- #1224
- #1227

### 필수조건

- server-side rate limit
- bot defense
- request body·question limit
- provider·global timeout
- concurrency limit
- daily/monthly cost cap
- request ID·latency·attempt telemetry
- kill switch
- provider disable
- snapshot-only fallback
- privacy warning
- incident runbook
- staging abuse·timeout·budget smoke

### 승인증거

- exact deployed SHA
- environment·secret owner
- rate-limit config snapshot
- budget threshold
- kill switch test
- no raw PII/key logs

이 Gate는 controlled/internal stakeholder clone MVP를 만들기 위한 선행조건이 아니다.

## Gate C — Evidence-safe AI pilot

### 목적

AI 답변이 공식근거 수준을 벗어나 고위험 행정정보를 확정하지 않도록 한다.

### historical prerequisite tracks

- #1226
- #1080 relevant route coverage

### 필수조건

- evidence enum
- high-risk claim taxonomy
- claim별 minimum evidence level
- model-only fail-closed validator
- stale·unavailable 표시
- canonical vs supplementary citation separation
- locale contract
- source·policy version metadata

### 승인증거

- 근거 없는 전화·기한·수수료·서류 차단 테스트
- 기만 URL·오래된 snapshot 테스트
- 주민용 fallback copy review

이 Gate는 AI factual output의 신뢰도 경계이며, faithful clone의 화면 fidelity를 낮추는 근거로 사용하지 않는다.

## Gate D — Unified platform foundation

### 목적

Python·Cloudflare·compatibility registry가 공통 site·provider·action·evidence 계약을 사용한다.

### foundation tracks

- #1225
- #1228
- #1287 (`completed`)

### 현재 구현 사실

- versioned Generic SiteSpec vNext contract foundation 존재
- archetype/capability/onboarding-report contract foundation 존재
- Buk-gu compatibility/projection foundation 존재
- Seo-gu offline generic Site Model/structural preview evidence 존재

이 foundation이 arbitrary site의 faithful clone/runtime wiring이 완료됐다는 뜻은 아니다.

### 필수조건

- versioned SiteSpec foundation
- canonical ID·legacy alias compatibility
- shared provider/action/evidence/API vocabulary
- runtime drift contract
- reproducible dependency install
- split CI jobs와 required checks
- golden compatibility tests

## Gate E — Modular maintainable runtime

### 목적

거대 단일파일의 기능확장 위험을 낮춘다.

### historical/deferred tracks

- #1229
- #1230

### 필수조건

- Cloudflare handler façade
- request·provider·evidence·locale·telemetry module
- citizen state·chat·history·locale·accessibility module
- public API·DOM·state façade compatibility
- browser·Function·build contract

이 Gate는 필요가 실제 platform work에서 발생할 때 재개한다. 단순 구조정리를 위해 named-site faithful clone work를 선행 차단하지 않는다.

## Gate F — Official freshness staging

### 목적

시간에 따라 변하는 공식정보를 별도 freshness workflow에서 조회한다.

### historical/deferred tracks

- #1150
- #1224
- #1227

### 필수조건 when this mode is actually used

- exact URL/domain policy
- redirect·malformed URL handling
- timeout·rate limit·cache
- source·retrieval·update time
- outage·stale behavior
- snapshot/live precedence
- routine CI remains offline

### 중요한 구분

Answer freshness와 clone visible-surface freshness는 동일한 상태가 아니다.

새 live evidence가 존재해도 approved clone이 자동으로 live mirror가 되지 않는다. Clone refresh는 별도 recapture/version/review다.

## Gate G — Multi-site clone MVP onboarding

Gate G는 **platform structural proof**, **named-site reference/clone proof**, **AI-on-clone proof**, **optional exact/default promotion**을 분리한다.

### Gate G0 — Generic structural/platform proof

#### 목적

실제 named site clone 완료를 주장하지 않고 shared contract/engine을 synthetic/offline evidence로 검증한다.

#### 허용

- synthetic/offline SiteSpec fixtures
- archetype/capability contract tests
- generic Site Model bundle
- structural renderer/preview
- knowledge/action schema proof
- QA/report/exception contract proof

#### 비주장

- named real site cloned
- visual parity
- clone MVP ready
- exact
- resident/default approved

Seo-gu #1298~#1300의 현재 의미는 이 Gate의 generic platform evidence다.

### Gate G1 — Named-site scoped reference baseline

#### 목적

실제 이름을 가진 target site의 declared MVP scope를 point-in-time reference로 고정한다.

#### 필수입력

- site identity
- declared MVP scope
- representative routes/states
- desktop/mobile viewport scope where relevant
- capture mode/method

#### 필수산출물

- source URLs
- `captured_at`
- source update time where available
- route/state inventory
- DOM/content reference evidence where applicable
- visual reference/screenshots where applicable
- important asset inventory
- unresolved/`capture_required` items
- deterministic snapshot/reference identity

#### 성공의 의미

`reference_baseline_ready`

아직 clone 완료가 아니다.

### Gate G2 — Faithful clone candidate

#### 목적

G1 reference를 기준으로 repository-controlled clone candidate를 만든다.

#### 필수조건

Declared scope 안에서:

- header/footer/global navigation fidelity
- layout/theme/typography/color fidelity appropriate to the reference
- representative text/content structure fidelity
- important image/asset mapping or explicit unresolved state
- key control/interaction mapping
- outside-scope route fabrication 금지

Shared engine은 generic할 수 있지만 rendered clone은 target site처럼 보여야 한다.

#### 필수산출물

- clone candidate identity
- source commit/generator identity
- structural/content comparison
- asset mapping/unresolved report
- browser interaction evidence
- responsive/accessibility QA where applicable
- explicit exception queue

### Gate G3 — Clone MVP review / readiness

#### 목적

Target-site stakeholder가 자기 사이트에 AI가 들어간 모습을 실제처럼 체험할 수 있을 정도로 declared scope의 clone을 검증한다.

#### 필수조건

- G1 reference baseline 존재
- G2 clone candidate 존재
- reference-vs-clone side-by-side review
- material differences recorded
- unresolved items explicit
- no generic redesign substitution
- applicable project-owner visual review for the declared stakeholder surface

#### 성공의 의미

`clone_mvp_ready`

이는 모든 route의 `exact` claim 또는 public resident-default approval과 동일하지 않다.

### Gate G4 — AI-on-clone onboarding proof

#### 목적

Faithful clone surface에서 AI Finder/Browser의 실제 사용자 가치를 검증한다.

#### 필수산출물

- knowledge index / answer grounding state
- action graph / browser target model
- search / click / navigation / read behavior evidence
- representative resident task simulations
- answer-from-site and applicable model-assisted fallback behavior
- automation ratio
- human-review ratio
- unsupported ratio
- explicit exception queue
- shared-core-changed `YES/NO`

#### 원칙

AI layer는 오른쪽에 추가될 수 있지만 구현 편의를 위해 왼쪽 official-site clone을 redesign하지 않는다.

### Gate G5 — Optional exact / archetype golden / resident-default promotion

#### 목적

더 강한 `exact`, archetype golden, resident/default 또는 production claim이 실제로 필요한 경우 추가 promotion을 검토한다.

#### 필수조건

- applicable exact-clone invariant
- applicable visual-promotion policy
- promotion-specific browser/safety/evidence regression
- explicit approval/evidence required by that promotion state
- deployment/rollback evidence when deployment is actually in scope

`clone_mvp_ready`만으로 이 상태가 자동 부여되지 않는다.

### Gate G 공통 성공증거

- site-specific renderer 없이 또는 최소 reviewed override로 onboarding
- declared clone scope
- reference snapshot identity
- clone candidate identity
- structural/content/asset/interaction/visual status
- AI-on-clone status
- automation/human review/unsupported ratio
- shared-core change와 site-specific change 분리
- failed onboarding isolation
- golden resident-default unchanged before explicit promotion
- cross-site reuse evidence

## Gate H — Authorized first-party actual-site integration — 미래 단계

### 목적

기관이 우리 회사에 실제 production 사이트의 구축·운영·유지보수 또는 AI integration 권한을 명시적으로 부여한 뒤, clone에서 검증한 AI Finder/Browser를 실제 환경에 통합한다.

### 시작조건

이 Gate는 current clone MVP의 기본 개발단계가 아니다.

기관 승인 후 해당 실제 환경을 기준으로 다음을 정의한다.

- credentials / secret owner
- deployment / hosting owner
- information-security requirements
- privacy / PII responsibility
- authentication boundary
- data retention / deletion
- real form / submission / payment / write boundaries
- internal-system integration
- monitoring / incident / support owner
- staging / rollback
- audit logging where required

### 중요한 원칙

Gate H 요구사항은 **Gate H가 실제로 열릴 때** 검토한다.

Gate G의 faithful clone development, visual fidelity, stakeholder evaluation, AI-on-clone validation을 위한 선행 blocker로 Gate H의 production requirements를 임의로 끌어오지 않는다.

Clone MVP 완료는 actual-site control을 의미하지 않는다.

## 공통 gate evidence template

```text
Gate:
Environment:
Base SHA:
Head/Release SHA:
Date/time:
Target site / clone scope:
Reference snapshot identity:
Clone candidate identity:
Network/provider mode:
Tests:
Browser/visual evidence:
AI-on-clone evidence:
Automation / review / unsupported ratio:
Exceptions:
Known limitations:
Rollback/isolation:
Decision: PASS / HOLD / FAIL
```

Production/deployment fields는 실제 deployment가 scope일 때만 추가한다.

## HOLD 조건

- exact current SHA 불명확
- required CI 일부 미실행·skip·xfail
- named-site clone claim인데 G1 reference baseline 없음
- named-site clone claim인데 structural preview만 존재
- declared clone scope가 불명확
- clone candidate의 unresolved items가 숨겨짐
- 해당 promotion level에서 요구되는 visual evidence 누락
- issue/PR head 변경 후 재검증 없음
- automation ratio를 fidelity evidence처럼 사용

## FAIL 조건

- named-site structural preview를 faithful clone 완료라고 허위 주장
- actual production site control을 근거 없이 주장
- secret·PII를 repository/public artifact에 노출
- golden route·DOM·state breaking regression
- public production operation을 승인 없이 활성화
- unsupported/low-confidence 항목을 숨겨 success ratio 부풀림
- future Gate H의 요구를 이유 없이 현재 faithful-clone fidelity 축소의 근거로 사용
