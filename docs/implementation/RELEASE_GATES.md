# 400 AI Finder 출시 게이트

- 상태: `canonical`
- 기준일: 2026-08-12
- 현재 platform-governance 정렬: #1283
- Buk-gu Frozen Demo closeout: #1235 (`completed`)

기능이 동작하거나 CI가 통과했다는 이유만으로 다음 운영단계에 자동 승격하지 않는다.

```text
implemented
!= generated preview
!= tested
!= visually approved
!= deployed
!= live validated
!= production approved
!= actual-site authorized
```

`generated_preview`, `archetype_golden`, `resident_default_approved`는 서로 다른 상태다. 자동 onboarding 결과가 존재한다는 이유만으로 exact clone·resident default·production approval을 주장하지 않는다.

## Gate A — Frozen controlled demo

### 목적

북구 golden clone과 결정형 시민 여정을 재현 가능한 데모로 유지한다.

### 필수조건

- exact golden SHA·manifest
- canonical fixture·checksum
- no-submit·no-login·no-payment
- no actual-site control
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

### 금지

- 실제 민원접수 주장
- 실제 로그인·결제
- PII 처리
- 보호 없는 public provider 비용노출

## Gate B — Protected public pilot

### 목적

공개 URL에서 제한된 AI 기능을 비용·abuse·장애 통제하에 제공한다.

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

## Gate D — Unified platform foundation

### 목적

Python·Cloudflare·compatibility registry가 공통 site·provider·action·evidence 계약을 사용한다.

### historical foundation tracks

- #1225
- #1228
- #1231

### 필수조건

- versioned SiteSpec foundation
- canonical ID·legacy alias compatibility
- shared provider/action/evidence/API vocabulary
- runtime drift contract
- reproducible dependency install
- split CI jobs와 required checks
- golden compatibility tests

### 승인증거

- `bukgu`/`bukgu_gwangju` dual-read evidence
- generated/adapter diff review
- no golden route·DOM·state regression

현재 foundation 존재가 임의 사이트용 generic Site Model/compiler/runtime wiring 완료를 뜻하지 않는다.

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

### 승인증거

- behavior-equivalence test
- module ownership map
- no circular dependency
- no event listener duplication

이 Gate는 필요가 실제 platform work에서 발생할 때 재개한다. 단순 구조정리만을 위해 multi-site 진행을 선행 차단하지 않는다.

## Gate F — Official freshness staging

### 목적

시간에 따라 변하는 공식정보를 승인된 staging에서 안전하게 조회한다.

### historical/deferred tracks

- #1150
- #1224
- #1227

### 필수조건

- exact URL/domain allowlist
- redirect·malformed URL fail-closed
- timeout·rate limit·cache
- real DOM/search retrieval validation where separately approved
- source·retrieval·update time
- outage·stale behavior
- snapshot/live precedence
- routine CI remains offline

### 승인증거

- separately approved controlled-live record
- zero write action
- captured response sanitized
- rollback to snapshot-only

### 비주장

이 Gate는 actual public site 통제나 실제 제출권한을 의미하지 않는다. URL이 onboarding 입력으로 제공됐다는 사실만으로 이 Gate의 live network 권한이 생기지 않는다.

## Gate G — Multi-site supervised onboarding

Gate G는 **generated preview**와 **golden/production promotion**을 분리한다. 둘을 같은 승인상태로 취급하지 않는다.

### Gate G1 — Generated onboarding preview

#### 목적

새 사이트를 bespoke renderer 개발 없이 공통 pipeline으로 분석하여 reviewable non-default preview를 생성한다. 초기 현실적 목표는 100% 자동완성이 아니라 **70–80% supervised automation + explicit exception queue**다.

#### 예상 입력

- target URL and/or SiteSpec draft
- separately declared acquisition/network mode

`URL supplied != live network authorized`다. URL은 대상 식별자일 수 있으며 live capture는 별도 승인경계를 따른다.

#### 필수 산출물

- canonical/draft site identity
- detected/proposed archetype + confidence
- detected capabilities + confidence
- capture/route inventory or approved fixture equivalent
- generic Site Model candidate
- asset/provenance manifest or unresolved-asset report
- knowledge artifact/index candidate
- action graph / browser target model candidate
- automated QA report
- automation ratio
- explicit exception queue with low-confidence / unsupported / safety-sensitive items
- rollback/isolation boundary for failed onboarding

#### 허용

- localhost/CI/debug generated preview
- incomplete surface with truthful confidence/exception reporting
- unresolved visual/content items if clearly non-exact and non-default
- automated screenshot/browser/semantic QA
- site-specific data/config/explicit reviewed overrides

#### 금지

- `exact` claim without exact-clone criteria
- `resident_default_approved` claim
- production/public promotion merely because generated QA passed
- uncontrolled live provider/crawl/network execution
- actual submit/login/payment/write action
- hiding unsupported/low-confidence items to inflate automation ratio

#### 승인증거

- input identity and acquisition mode
- generated artifact identities
- automation/review/unsupported ratios
- exception summary
- core-changed `YES/NO`
- offline/reproducible validation where applicable

**Human first-promotion visual approval is not required for Gate G1 itself**, because G1 does not grant resident-default or exact status.

### Gate G2 — Archetype golden validation

#### 목적

municipality / university / bank / public agency / support portal / company 등 사이트 유형별 대표 surface를 깊게 검증하여 반복 onboarding의 기준으로 사용한다.

#### 필수조건

- archetype/capability contract defined for the representative scope
- generated preview upgraded through focused human review
- browser task coverage for representative capabilities
- grounding/action/safety coverage
- responsive/accessibility evidence appropriate to the surface
- material exception resolution or explicit accepted limitations
- applicable visual fidelity review
- rollback identity

북구는 첫 municipality golden reference로 보호한다. 미래 archetype golden이 북구 route/DOM/state 계약을 깨뜨리는 이유가 되어서는 안 된다.

### Gate G3 — Resident/default or production promotion

#### 목적

특정 site surface를 실제 기본 사용자 경로나 production candidate로 승격한다.

#### 필수조건

- applicable SiteSpec/provenance/rights state
- applicable exact/high-fidelity policy satisfied for the claim being made
- visual side-by-side evidence where required
- project-owner approval where required by visual promotion policy
- browser/safety/evidence regression
- deployment/rollback evidence when deployed

Generated preview 또는 archetype golden 통과만으로 이 상태가 자동 부여되지 않는다.

### Gate G 공통 성공증거

- site-specific renderer 없이 또는 최소 reviewed override로 onboarding
- automation/human review ratio
- shared-core change와 site-specific change 분리
- failed onboarding isolation
- golden resident-default unchanged before explicit approval
- cross-site reuse evidence

## Gate H — Authorized operational integration

### 목적

기관이 권한과 운영책임을 제공한 실제 환경에서 first-party integration을 수행한다.

### historical prerequisite tracks

- #862
- #873

### 필수조건

- 기관의 명시적 권한
- credentials·secret owner
- deployment owner
- security review
- 개인정보 처리책임
- data retention·deletion
- incident·support owner
- staging·rollback
- audit log

### 이 Gate에서만 검토 가능한 기능

- actual site widget·script
- authenticated flow
- real form integration
- operational system handoff
- PII processing

### 별도 승인이 필요한 고위험 기능

- 자동 제출
- 결제
- 법적효과가 있는 신청
- 주민등록번호·계좌 등 고위험 개인정보

## 공통 gate evidence template

```text
Gate:
Environment:
Base SHA:
Head/Release SHA:
Deployed SHA:
Date/time:
Operator/reviewer:
Data classification:
Network/provider mode:
Tests:
Browser/visual evidence:
Security/privacy evidence:
Generated-preview status (if applicable):
Automation / review / unsupported ratio (if applicable):
Exceptions (if applicable):
Known limitations:
Rollback:
Decision: PASS / HOLD / FAIL
```

## HOLD 조건

- exact SHA 불명확
- required CI 일부 미실행·skip·xfail
- external request 범위 미기록
- secret·PII 가능성
- official source provenance 누락
- 해당 promotion level에서 요구되는 visual approval 누락
- deployed SHA 불일치 when deployment is in scope
- required rollback 미검증
- issue/PR head 변경 후 재검증 없음
- generated preview가 low-confidence/unsupported 항목을 exception으로 기록하지 않음

## FAIL 조건

- 실제 submit·login·payment가 승인 없이 발생
- 공식근거 없는 고위험 행정정보 확정
- secret·PII 노출
- golden route·DOM·state breaking regression
- public endpoint 무제한 과금·abuse
- actual-site control을 근거 없이 주장
- customer/private data의 public repo 반입
- generated preview를 근거 없이 exact/resident-default/production-approved로 주장
