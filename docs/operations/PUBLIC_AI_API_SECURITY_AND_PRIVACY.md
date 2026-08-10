# 공개 AI API 보안·개인정보 운영모델

- 상태: `canonical`
- 기준일: 2026-08-04
- 관련 이슈: #1224, #1226, #1227
- 좌측 시민 clone canonical invariant: [`docs/product/exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md)

## 1. 적용범위

이 문서는 공개 시민 surface와 Cloudflare Pages `/api/mvp/ask` 같은 익명·반익명 AI endpoint에 적용한다.

포함:

- 시민 질문 입력
- provider API 호출
- 공식 snapshot·live source context
- 응답·source·metadata
- 운영로그·비용·abuse 대응
- static·snapshot-only 비상모드

제외:

- 실제 민원 제출
- 인증 사용자 계정
- 결제
- 주민등록번호 등 고위험 개인정보 처리
- 기관 내부 업무시스템 write action

이 제외항목은 별도 first-party integration과 개인정보 영향평가 전 활성화하지 않는다.

## 2. 위협모델

### 2.1 비용·가용성

- bot의 반복질문
- 직접 HTTP 호출
- 병렬 request 폭주
- provider timeout 누적
- fallback으로 인한 복수 provider 과금
- corrective retry 비용증가
- 긴 response·search tool 비용

### 2.2 개인정보

- 주민번호·외국인등록번호
- 전화·이메일
- 상세주소
- 민원사건·건강·가족·재산·분쟁정보
- 자유서술에 포함된 제3자 개인정보
- 질문·응답·로그의 장기보관

### 2.3 prompt·data injection

- 시민 질문의 instruction injection
- 공식페이지·검색결과 안의 악성 instruction
- provider output의 HTML·URL·action injection
- rejected draft delimiter breakout

### 2.4 source·사실성

- 공식도메인처럼 보이는 기만 URL
- outdated snapshot
- model-only 답변을 공식사실로 표시
- 공식 citation과 canonical provenance 혼동

### 2.5 운영오류

- secret·Authorization·원문 provider error의 로그노출
- 잘못된 endpoint override
- 잘못된 environment·deployment SHA
- kill switch 부재

## 3. 기본 안전모드

개발·CI 기본:

```text
mock or stub
+ canonical fixture
+ no external network
+ no secrets
+ no persistent citizen transcript
```

공개 pilot 기본:

```text
protected anonymous session
+ rate limit
+ cost cap
+ provider timeout
+ evidence policy
+ no-store response
+ privacy warning
+ kill switch
+ snapshot-only fallback
```

## 4. 입력정책

### 4.1 길이와 크기

- 질문 character limit과 request body byte limit을 모두 둔다.
- JSON object와 허용 field만 받는다.
- 배열·중첩 object·예상하지 못한 field는 reject 또는 ignore 정책을 명시한다.
- Content-Type과 method를 제한한다.

Current #1224-A request-boundary values:

- default body cap: `8192` bytes
- operator override: `MVP_MAX_BODY_BYTES`, accepted only from `1024` through `32768` bytes
- invalid/out-of-range override: fail-safe fallback to `8192` bytes
- question semantic limit: `300` characters, independent of body bytes
- accepted top-level fields: `question`, optional `locale`, optional `session_id`
- anonymous browser session: random/pseudonymous, `sessionStorage` only, page-memory fallback, never `localStorage`

These numbers cover request ingress only. Rate, concurrency, challenge, and provider budget values remain separate #1224 slices and must not be inferred from this body-size policy.

### 4.2 개인정보 경고

composer 근처에 다음 취지의 안내를 표시한다.

> 주민등록번호, 계좌번호, 상세주소, 전화번호, 민원대상자의 이름 등 개인정보를 입력하지 마세요. AI Finder는 공식 안내경로를 찾는 용도이며 실제 민원접수 창구가 아닙니다.

### 4.3 최소탐지

운영정책이 승인되면 다음 pattern을 최소 탐지한다.

- 주민번호·외국인등록번호 형태
- 카드·계좌 형태의 긴 숫자
- 전화번호
- 이메일
- 상세주소 가능성이 높은 조합

탐지는 완전한 DLP가 아니다. 목적은 경고·redaction·로그비저장의 방어층을 추가하는 것이다.

### 4.4 질문보관

기본 원칙:

- 원문을 장기보관하지 않는다.
- 반복질문 분석이 필요하면 비식별화·정규화한 intent 또는 hash를 사용한다.
- 원문 sample이 필요한 연구는 별도 opt-in, 최소기간, 접근권한과 삭제일을 둔다.
- 운영로그에 Authorization, key, cookie, raw body를 남기지 않는다.

## 5. Abuse·rate limit

### 5.1 제한단위

- IP 또는 Cloudflare 제공 식별자
- 짧은 익명 세션 token
- browser challenge 결과
- 전체 service global limit
- provider별 concurrency

### 5.2 다층제한

- 초당 burst
- 분당 request
- 시간당 request
- 일일 anonymous session request
- 전체 일일 provider call·token·cost

정확한 수치는 staging traffic과 provider 가격에 따라 #1224에서 결정한다.

### 5.3 봇방어

- Cloudflare Turnstile 또는 동등수단
- 정상 사용자의 접근성을 고려한 challenge
- challenge token server verification
- token reuse·expiry·origin 검증

### 5.4 제한초과 응답

시민에게 내부 비용정보를 노출하지 않는다.

- 잠시 후 재시도
- official site direct link
- snapshot-only answer 가능 여부
- retryable flag

## 6. Provider 비용·가용성

### 6.1 timeout

- request 전체 deadline
- provider별 deadline
- search tool deadline
- fallback에 남은 budget 전달
- client disconnect 또는 deadline 시 abort

### 6.2 fallback

- provider order는 operator-owned config
- 한 request의 최대 provider attempts 제한
- corrective retry는 전역 budget으로 제한
- timeout·rate limit·auth·malformed response를 닫힌 failure code로 분류
- concrete evidence rejection은 non-retryable이며 다른 provider로 우회하지 않는다

### 6.3 비용상한

- provider별 일·월 예산
- request당 max output token
- search-enabled request 비율 또는 별도 budget
- 예상비용·실제 usage 기록
- 상한 접근 경보
- 초과 시 provider disable 또는 snapshot-only 전환

## 7. Source·evidence 정책

### 7.1 신뢰등급

Canonical evidence vocabulary:

- `canonical_snapshot`
- `verified_live_source`
- `supplementary_official_citation`
- `model_only`

Only `canonical_snapshot` and `verified_live_source` authorize covered concrete values. Runtime `official_snapshot` maps to canonical snapshot evidence. Historical `live_official` and any unknown/undeclared level fail closed to `model_only`; they are not verified aliases.

### 7.2 고위험 claim

근거가 부족하면 다음을 확정적으로 반환하지 않는다.

- 담당부서·연락처
- 운영시간
- 수수료
- 기한
- 제출서류
- 자격요건
- 법적효과
- 신청 URL

#1226-A에서 서버 강제가 완료된 concrete-value 범위는 [`MVP_CONCRETE_EVIDENCE_POLICY.md`](MVP_CONCRETE_EVIDENCE_POLICY.md)를 따른다.

현재 강제 신호는 `phone`, `url`, `clock_time`, `money`, `calendar_date`이다. provider 답변에서 concrete signal이 발견되면 sanitized verified evidence 안에 동일한 **semantic identity**의 값이 모두 있어야 한다. 금액은 KRW/USD/EUR currency identity를 포함하며 같은 숫자의 다른 통화는 일치하지 않는다. AM/PM은 24시간 의미로 보존하고, URL fragment는 identity 일부로 보존한다. bounded 국제전화 `+82/+84/+66/+62`는 formatting-equivalent form을 정규화한다. 명확한 날짜 표현만 같은 실제 calendar date로 정규화하며 `08/09/2026` 같은 D/M/Y·M/D/Y ambiguity는 감지한 뒤 임의 해석 없이 fail closed한다. bare `$`처럼 currency identity가 확정되지 않는 bounded signal도 USD로 추정하지 않고 fail closed한다.

하나라도 evidence에 없거나 semantic identity가 다르거나 evidence level이 unverified이면 provider draft를 선택하지 않고 `evidence_required`로 fail closed한다. official-looking domain이나 supplementary citation만으로 evidence level을 승격하지 않는다. blocked raw concrete value는 citizen fallback, public/operator policy metadata, sanitized runtime log에 넣지 않는다.

아직 #1226 후속 구현이 필요한 semantic claim은 담당부서의 실제 소관, 제출서류 목록, 자격·제외조건, 명시적 날짜가 없는 기한 의미, 법적효과, 절차 전제조건, 신청-channel 의미 등이다. #1226-A 완료를 이 전체 semantic 범위의 완료로 해석하지 않는다.

### 7.3 prompt injection 방어

- source content를 instruction과 분리한다.
- source 내부 instruction을 따르지 않는다는 system policy를 둔다.
- source text·rejected draft를 data-only serialization한다.
- model output action은 closed allowlist로 검증한다.
- URL은 protocol·domain·same-origin 또는 approved external policy로 검증한다.

## 8. 응답정책

시민 응답:

- 간결한 안내
- 공식 source와 freshness label
- 한계와 확인필요 표시
- 내부 stack·provider raw error 미노출

operator metadata:

- request ID
- schema·prompt·aggregate runtime policy version
- evidence policy version/decision
- provider·model
- attempts·fallback reason
- latency
- token·cost when available
- rate-limit·abuse decision

Aggregate runtime `policy_version`과 evidence-module version은 별도 ownership이다. evidence detector revision이 runtime policy metadata version을 직접 alias하거나 자동 변경하지 않는다.

질문 원문·key·Authorization·raw provider body·blocked concrete value는 기본 operator metadata에 포함하지 않는다.

## 9. CORS와 인증

CORS는 보안층 중 하나지만 다음을 보장하지 않는다.

- bot 차단
- direct HTTP 차단
- 인증
- rate limit
- 비용보호

허용 origin은 exact production origin, approved preview pattern과 loopback development로 제한한다. `Vary: Origin`, no-store와 method/header 제한을 유지한다.

## 10. Secret·endpoint

- key는 Cloudflare secret 또는 승인된 secret store에만 둔다.
- `.env`, fixture, screenshot, log, PR body에 key를 기록하지 않는다.
- production endpoint는 code-owned allowlist를 사용한다.
- local override는 explicit opt-in + loopback request + loopback endpoint에서만 허용한다.
- endpoint validation 실패는 fail-closed한다.

## 11. 운영 kill switch

최소 제어:

- 전체 AI Function disable
- provider별 disable
- search tool disable
- snapshot-only mode
- 특정 action disable
- 특정 locale disable은 마지막 수단이며 접근성 영향을 기록

전환은 audit event와 operator, 시각, 이유, 복구조건을 남긴다.

## 12. Incident response

### Key 노출

1. provider key revoke·rotate
2. affected deployment disable
3. logs·commits·artifacts 범위확인
4. history cleanup 필요성 판단
5. 비용·abuse 확인
6. incident record

### 개인정보 원문 저장

1. 수집중단
2. 접근제한
3. 영향범위·보관위치 확인
4. 승인된 삭제
5. 법적·기관 reporting 검토
6. redaction·retention control 보완

### 비용·traffic 공격

1. kill switch 또는 snapshot-only
2. offending traffic pattern 차단
3. provider budget 확인
4. rate-limit·Turnstile 조정
5. 정상사용 영향 검증

### 잘못된 행정정보

1. 해당 action 또는 source disable
2. citizen-facing correction 필요성 판단
3. snapshot·source·policy version 확인
4. fixture update·visual/contract review
5. 재배포와 evidence 기록

## 13. Production readiness checklist

- [ ] 서버측 rate limit
- [ ] 봇방어
- [ ] request body·question limit
- [ ] provider·전체 timeout
- [ ] concurrency limit
- [ ] 일·월 비용상한
- [ ] privacy warning
- [ ] 최소 DLP·redaction 정책
- [ ] raw transcript retention 정책
- [ ] evidence-gated high-risk claims
- [ ] request ID·latency·attempt telemetry
- [ ] kill switch·snapshot-only fallback
- [ ] incident runbook
- [ ] staging abuse·timeout·fallback smoke evidence
- [ ] deployed SHA·environment·secret owner 확인

이 checklist가 완료되지 않은 공개 endpoint는 제품데모로 분류하며 상시 시민 운영판으로 승인하지 않는다.
