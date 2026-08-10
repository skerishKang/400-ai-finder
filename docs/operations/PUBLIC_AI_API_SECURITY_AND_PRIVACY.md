# 공개 AI API 보안·개인정보 운영모델

- 상태: `canonical`
- 기준일: 2026-08-10
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
+ bot verification
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

Current #1224-A/B request-boundary values:

- default body cap: `8192` bytes
- operator override: `MVP_MAX_BODY_BYTES`, accepted only from `1024` through `32768` bytes
- invalid/out-of-range override: fail-safe fallback to `8192` bytes
- question semantic limit: `300` characters, independent of body bytes
- accepted top-level fields: `question`, optional `locale`, optional `session_id`, optional `turnstile_token`
- anonymous browser session: random/pseudonymous, `sessionStorage` only, page-memory fallback, never `localStorage`
- `turnstile_token`: protected model path에서만 요구되는 단기 challenge response; browser storage에 보관하지 않고 provider로 전달하지 않는다.

These numbers cover request ingress and the Turnstile token envelope only. Rate, concurrency, and provider budget values remain separate #1224 slices and must not be inferred from this body-size policy.

### 4.2 개인정보 경고

composer 근처에 다음 취지의 안내를 표시한다.

> 주민등록번호, 계좌번호, 상세주소, 전화번호, 민원대상자의 이름 등 개인정보를 입력하지 마세요. AI Finder는 공식 안내경로를 찾는 용도이며 실제 민원접수 창구가 아닙니다.

### 4.3 최소탐지

Current #1224-A 최소탐지는 다음을 적용한다.

- 주민번호 형태: fail-closed
- 전화번호: provider 전달 전 redaction
- 이메일: provider 전달 전 redaction
- 상세주소 가능성이 높은 조합: provider 전달 전 redaction
- redaction 결과가 사실상 비어버리는 고위험 입력: fail-closed

아직 별도 정책/구현이 필요한 항목:

- 외국인등록번호의 별도 정밀 규칙
- 카드·계좌 형태의 긴 숫자
- 자유서술 민감정보의 의미 기반 DLP

탐지는 완전한 DLP가 아니다. 목적은 경고·redaction·로그비저장의 방어층을 추가하는 것이다.

### 4.4 질문보관

기본 원칙:

- 원문을 장기보관하지 않는다.
- 반복질문 분석이 필요하면 비식별화·정규화한 intent 또는 hash를 사용한다.
- 원문 sample이 필요한 연구는 별도 opt-in, 최소기간, 접근권한과 삭제일을 둔다.
- 운영로그에 Authorization, key, cookie, raw body를 남기지 않는다.
- 익명 `session_id` 원문과 Turnstile challenge token도 기본 운영로그에 남기지 않는다.

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

### 5.3 봇방어 — #1224-B 구현계약

Protected model request는 Cloudflare Turnstile server verification을 통과해야 한다.

Client:

- same-origin `/api/mvp/turnstile-config`에서 공개 site key와 action만 읽는다.
- Turnstile secret은 browser에 노출하지 않는다.
- 공식 Cloudflare explicit-render script만 로드한다.
- widget은 `execution: execute`, `appearance: interaction-only`로 동작한다.
- 각 protected `ask()`마다 fresh token을 획득한다.
- token을 `localStorage`, `sessionStorage`, cookie에 저장하지 않는다.
- protected request 종료·취소 후 widget을 reset한다.
- config/script/challenge 실패 시 `/api/mvp/ask` provider path를 호출하지 않고 fail-closed한다.

Server:

- Siteverify endpoint를 기존 #1227 deadline-aware outbound fetch로 호출한다.
- Siteverify에는 현재 `secret`과 `response` challenge token만 전달한다.
- 시민 질문, 익명 `session_id`, `remoteip`는 Siteverify에 전달하지 않는다.
- expected action을 검증한다.
- `MVP_TURNSTILE_ALLOWED_HOSTNAMES`가 설정되면 exact hostname allowlist를 검증한다.
- expired/duplicate/rejected/action mismatch/hostname mismatch는 provider 호출 전에 차단한다.
- Siteverify timeout/network/HTTP/malformed response도 provider 호출 전에 차단한다.
- privacy assessment는 Siteverify보다 먼저 실행한다. 주민번호성 고위험 입력은 Turnstile 외부호출조차 없이 차단한다.

Runtime configuration:

- `MVP_TURNSTILE_MODE=required`: production/default canonical mode
- `MVP_TURNSTILE_MODE=disabled`: exact loopback request host에서만 local/offline test용으로 허용
- production에서 `disabled`를 지정해도 bypass하지 않고 `required`로 fail-closed한다.
- `MVP_TURNSTILE_SITE_KEY`: 공개 site key
- `MVP_TURNSTILE_SECRET_KEY`: encrypted Cloudflare secret으로만 관리
- `MVP_TURNSTILE_EXPECTED_ACTION=mvp_ask`
- `MVP_TURNSTILE_ALLOWED_HOSTNAMES`: comma-separated exact hostname allowlist
- `MVP_TURNSTILE_TIMEOUT_MS`: 기본 `3000`, 허용 `250..10000` ms; global request deadline의 남은 budget도 동시에 적용

Failure mapping:

- missing/malformed/oversized challenge → HTTP 403 / `bot_verification_required`
- rejected/expired/duplicate/action/hostname mismatch → HTTP 403 / `bot_verification_failed`
- Siteverify unavailable/timeout/network/HTTP/malformed → HTTP 503 / `bot_verification_unavailable`
- required key/secret configuration missing → HTTP 503 / `bot_verification_config_error`

`bot_verification_unavailable`만 자동 retryable이다. Required/failed/configuration failure는 자동 retryable이 아니다.

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
- Turnstile Siteverify deadline
- search tool deadline
- fallback에 남은 budget 전달
- client disconnect 또는 deadline 시 abort

### 6.2 fallback

- provider order는 operator-owned config
- 한 request의 최대 provider attempts 제한
- corrective retry는 전역 budget으로 제한
- timeout·rate limit·auth·malformed response를 닫힌 failure code로 분류
- bot verification이 실패하면 provider fallback 자체를 시작하지 않는다.

### 6.3 비용상한

- provider별 일·월 예산
- request당 max output token
- search-enabled request 비율 또는 별도 budget
- 예상비용·실제 usage 기록
- 상한 접근 경보
- 초과 시 provider disable 또는 snapshot-only 전환

## 7. Source·evidence 정책

### 7.1 신뢰등급

- `canonical_snapshot`
- `verified_live_source`
- `supplementary_official_citation`
- `snapshot_unavailable`
- `model_only`
- `unavailable`

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
- schema·prompt·policy version
- provider·model
- attempts·fallback reason
- latency
- token·cost when available
- evidence decision
- privacy category/boolean state
- bot-defense mode/verified/bypassed/reason/action/hostname 같은 sanitized state
- rate-limit·abuse decision

질문 원문·key·Authorization·raw provider body·익명 session ID 원문·Turnstile challenge token/secret은 기본 operator metadata에 포함하지 않는다.

## 9. CORS와 인증

CORS는 보안층 중 하나지만 다음을 보장하지 않는다.

- bot 차단
- direct HTTP 차단
- 인증
- rate limit
- 비용보호

허용 origin은 exact production origin, approved preview pattern과 loopback development로 제한한다. `Vary: Origin`, no-store와 method/header 제한을 유지한다.

Turnstile은 인증 대체수단이 아니다. challenge 통과 여부는 protected anonymous model request의 bot-defense signal일 뿐 사용자 신원·권한을 증명하지 않는다.

## 10. Secret·endpoint

- key는 Cloudflare secret 또는 승인된 secret store에만 둔다.
- `.env`, fixture, screenshot, log, PR body에 real secret을 기록하지 않는다.
- Turnstile site key는 공개값이지만 `MVP_TURNSTILE_SECRET_KEY`는 encrypted deployment secret으로만 관리한다.
- public Turnstile config endpoint는 site key/action만 반환하며 secret을 반환하지 않는다.
- production endpoint는 code-owned allowlist를 사용한다.
- local override는 explicit opt-in + loopback request + loopback endpoint에서만 허용한다.
- Turnstile disable도 exact loopback에서만 허용한다.
- endpoint/config validation 실패는 fail-closed한다.

## 11. 운영 kill switch

최소 제어:

- 전체 AI Function disable
- provider별 disable
- search tool disable
- snapshot-only mode
- 특정 action disable
- 특정 locale disable은 마지막 수단이며 접근성 영향을 기록

전환은 audit event와 operator, 시각, 이유, 복구조건을 남긴다.

Turnstile `disabled`는 production emergency kill switch가 아니다. bot verification을 우회해야 하는 운영 상황에서는 AI를 `snapshot_only` 또는 `disabled`로 전환해야 하며, production challenge bypass를 허용하지 않는다.

## 12. Incident response

### Key 노출

1. provider/Turnstile secret revoke·rotate
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
- [x] Turnstile bot-defense code·offline contract
- [ ] Turnstile production site key·encrypted secret·allowed hostname 설정 및 staging 검증
- [x] request body·question limit
- [x] provider·전체 timeout
- [ ] concurrency limit
- [ ] 일·월 비용상한
- [x] privacy warning
- [x] 최소 DLP·redaction baseline (resident-ID fail-closed + phone/email/precise-address redaction)
- [ ] 확장 DLP (외국인등록번호·카드/계좌·자유서술 민감정보)
- [x] raw transcript 기본 비보관 정책
- [ ] evidence-gated high-risk claims 전체범위
- [x] request ID·latency·attempt telemetry
- [x] kill switch·snapshot-only fallback
- [x] incident runbook
- [ ] staging abuse·timeout·fallback smoke evidence
- [ ] deployed SHA·environment·secret owner 확인

#1224-B 코드는 offline contract 기준으로 구현되어 있어도, 실제 Turnstile site key/secret/hostname 준비와 staging 검증 전에는 production bot-defense 완료로 간주하지 않는다. 이 checklist가 완료되지 않은 공개 endpoint는 제품데모로 분류하며 상시 시민 운영판으로 승인하지 않는다.
