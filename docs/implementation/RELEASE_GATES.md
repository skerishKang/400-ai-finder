# 400 AI Finder 출시 게이트

- 상태: `canonical`
- 기준일: 2026-08-04
- 총괄: #1235

기능이 동작하거나 CI가 통과했다는 이유만으로 다음 운영단계에 자동 승격하지 않는다.

```text
implemented
!= tested
!= visually approved
!= deployed
!= live validated
!= production approved
!= actual-site authorized
```

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

### 선행 이슈

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

### 선행 이슈

- #1226
- #1080 relevant route coverage

### 필수조건

- evidence enum
- high-risk claim taxonomy
- claim별 minimum evidence level
- model-only fail-closed validator
- stale·unavailable 표시
- canonical vs supplementary citation separation
- 5 locale contract
- source·policy version metadata

### 승인증거

- 근거 없는 전화·기한·수수료·서류 차단 테스트
- 기만 URL·오래된 snapshot 테스트
- 주민용 fallback copy review

## Gate D — Unified platform foundation

### 목적

Python·Cloudflare·compatibility registry가 공통 site·provider·action·evidence 계약을 사용한다.

### 선행 이슈

- #1225
- #1228
- #1231

### 필수조건

- versioned SiteSpec
- canonical ID·legacy alias migration
- ProviderSpec·ActionSpec·ApiSchema
- runtime drift contract
- reproducible dependency install
- split CI jobs와 required checks
- golden compatibility tests

### 승인증거

- `bukgu`/`bukgu_gwangju` dual-read evidence
- generated/adapter diff review
- no golden route·DOM·state regression

## Gate E — Modular maintainable runtime

### 목적

거대 단일파일의 기능확장 위험을 낮춘다.

### 선행 이슈

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

## Gate F — Official freshness staging

### 목적

시간에 따라 변하는 공식정보를 승인된 staging에서 안전하게 조회한다.

### 선행 이슈

- #1150
- #1224
- #1227

### 필수조건

- exact URL allowlist
- redirect·malformed URL fail-closed
- timeout·rate limit·cache
- real DOM extraction test
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

이 Gate는 actual public site 통제나 실제 제출권한을 의미하지 않는다.

## Gate G — Multi-site supervised pilot

### 목적

generic onboarding을 북구 외 사례로 검증한다.

### 선행 이슈

- #1181
- #1232

### 필수조건

- 북구 generic preview parity
- 다른 지자체 onboarding
- 교차도메인 onboarding
- Site Model·asset manifest·knowledge·action graph
- confidence·exception queue
- automated QA
- human visual approval
- rollback

### 승인증거

- site-specific renderer 없이 onboarding
- automation/human review ratio
- failed onboarding isolation
- golden resident-default unchanged before approval

## Gate H — Authorized operational integration

### 목적

기관이 권한과 운영책임을 제공한 실제 환경에서 first-party integration을 수행한다.

### 선행 이슈

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
Known limitations:
Rollback:
Decision: PASS / HOLD / FAIL
```

## HOLD 조건

- exact SHA 불명확
- CI 일부 미실행·skip·xfail
- external request 범위 미기록
- secret·PII 가능성
- official source provenance 누락
- visual approval 누락
- deployed SHA 불일치
- rollback 미검증
- issue/PR head 변경 후 재검증 없음

## FAIL 조건

- 실제 submit·login·payment가 승인 없이 발생
- 공식근거 없는 고위험 행정정보 확정
- secret·PII 노출
- golden route·DOM·state breaking regression
- public endpoint 무제한 과금·abuse
- actual-site control을 근거 없이 주장
- customer/private data의 public repo 반입
