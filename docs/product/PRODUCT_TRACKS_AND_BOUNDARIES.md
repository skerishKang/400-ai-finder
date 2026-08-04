# 제품 트랙과 운영경계

- 상태: `canonical`
- 기준일: 2026-08-04
- 총괄: #1235

`400-ai-finder`에는 서로 다른 목적·위험·완료조건을 가진 여러 제품트랙이 있다. 모든 트랙을 하나의 “AI Finder 기능”으로 취급하면 데모완료, 실시간 조회, actual-site 통제와 production 운영이 혼동된다.

## 1. 트랙 A — 북구 golden clone

### 목적

공식 공개페이지를 근거로 한 controlled clone에서 시민이 검색·안내·화면이동·문서작성 지원을 체험하도록 한다.

### 현재 자산

- frozen compatibility manifest
- closed route·target·DOM·state vocabulary
- canonical fixture와 checksum
- desktop·mobile browser contract
- deterministic journey
- Page Agent resident comparison
- no-submit·no-login·no-payment 경계

### 완료의 의미

- fixture·structure·asset·interaction·visual review가 분리돼 기록됨
- resident-default 승인이 명시됨
- exact main/golden SHA와 rollback artifact가 있음

### 비주장

- 모든 북구 공식 route가 exact clone이라는 의미가 아님
- actual 북구사이트를 제어한다는 의미가 아님
- 실제 민원제출·로그인·결제가 가능하다는 의미가 아님

### 추적

- #1080
- `docs/bukgu-golden-compatibility-manifest.md`
- `docs/product/exact-official-site-clone-invariant.md`
- `docs/product/clone-visual-fidelity-and-promotion-policy.md`

## 2. 트랙 B — 근거 기반 AI 시민안내

### 목적

주민 질문을 action·route와 연결하고 공식 snapshot 또는 검증된 출처에 근거해 답한다.

### 신뢰등급

| 등급 | 의미 | 허용범위 |
|---|---|---|
| canonical snapshot | owner-approved fixture·checksum | 근거범위 내 확정안내 |
| verified live source | 승인된 실시간 공식출처·조회시각 | 시각·출처 표시 후 안내 |
| supplementary citation | 공식도메인 citation이나 canonical 검증 전 | 참고표시 |
| model only / unavailable | 검증근거 없음 | 일반방향만, 고위험 사실 확정 금지 |

### 고위험 정보

- 담당부서·기관
- 전화·주소·운영시간
- 수수료
- 신청·접수기한
- 제출서류
- 자격요건
- 법적효과
- 실제 신청 URL

### 운영 전 조건

- #1226 evidence policy
- #1224 public API protection
- #1227 timeout·observability·kill switch

## 3. 트랙 C — 공식정보 freshness

### 목적

시간에 따라 바뀌는 기관명·담당자·운영시간·공고·기한을 답변시점 또는 승인된 갱신작업에서 확인한다.

### 현재 상태

- offline/mock freshness boundary와 snapshot semantics는 존재
- 실제 answer-time official-site retrieval은 별도 후속
- live-ready 또는 production-ready로 표현하지 않음

### 실행모드

1. fixture capture·scheduled refresh
2. controlled read-only validation
3. staging answer-time retrieval
4. protected production retrieval

각 단계는 별도 승인·network boundary·timeout·rate limit·provenance evidence가 필요하다.

### 추적

- #1150
- #1227
- `docs/provider-fetch-network-boundary.md`

## 4. 트랙 D — Python crawler·index·operator runtime

### 목적

사이트 profile을 이용해 공개페이지·게시판·첨부문서를 수집·가공·색인하고 운영자가 결과를 시험한다.

### 현재 범위

- YAML site profile
- requests·mock 등 fetch abstraction
- document parsing
- search·answer pipeline
- operator dashboard·CLI
- snapshot 기반 offline demo

### 경계

- live fetch는 명시적 opt-in과 scoped profile이 필요
- routine CI는 offline fixture 사용
- data/raw·processed·index·runs를 기본 Git 추적하지 않음
- 고객·기관 비공개자료는 public repo에 반입하지 않음

## 5. 트랙 E — Cloudflare 시민 runtime

### 목적

Pages의 citizen surface와 `/api/mvp/ask` Function을 통해 공개 시연 또는 제한된 pilot을 제공한다.

### 현재 범위

- Gemini·HY3 provider order
- canonical snapshot context
- deterministic action override
- 5 locale 답변정책
- server-side secrets
- static fallback build

### production 전 차단항목

- rate limit·bot defense·cost cap
- provider timeout
- request ID·latency·attempt metadata
- PII warning·redaction·retention
- evidence-gated high-risk claim policy
- kill switch·snapshot-only fallback

### 추적

- #1224
- #1226
- #1227
- #1229

## 6. 트랙 F — Native AI Finder vs Page Agent 연구

### 목적

같은 controlled clone과 동일 task definition에서 deterministic/native 방식과 model-planned DOM action 방식을 비교한다.

### 비교항목

- task success
- wrong action
- step count
- latency
- reproducibility
- maintenance cost
- cancellation
- no-submit safety
- external request count

### 경계

- architecture 선호만으로 승자를 정하지 않음
- hybrid 결과 허용
- golden CI의 Page Agent는 deterministic mock adapter를 사용
- 실제 provider 비교는 별도 staging·비용·safety 승인 필요

## 7. 트랙 G — Clone-first 다기관 플랫폼

### 목적

새 기관 URL 또는 SiteSpec으로 capture, Site Model, clone, knowledge, action graph와 QA를 생성한다.

### 목표 pipeline

```text
SiteSpec
  -> bounded capture
  -> generic Site Model
  -> asset/provenance manifest
  -> clone compiler
  -> knowledge index
  -> action graph
  -> QA + exception queue
  -> human approval
```

### 검증단계

1. 북구 generic preview와 golden parity
2. 다른 지자체 onboarding
3. 대학·지원사업 포털 등 교차도메인 onboarding

### 경계

- 기관별 bespoke renderer 누적 금지
- site-specific 차이는 data·config·theme·parser profile·reviewed override로 표현
- 북구 golden을 parity 전 교체하지 않음
- 70~80% supervised automation을 첫 목표로 삼음

### 추적

- #1181
- #1225
- #1228
- #1232

## 8. 트랙 H — 실제 기관사이트 first-party integration

### 목적

기관이 명시적으로 승인한 환경에서 실제사이트에 AI Finder를 삽입하거나 인증·제출·업무시스템과 연동한다.

### 시작조건

- 기관의 서면 권한
- credentials와 secret owner
- deployment owner
- security review
- 개인정보 처리책임
- 운영·장애·민원 대응책임
- staging·rollback

### 이 단계 전 금지

- actual-site control 주장
- 실제 form submit
- login·payment
- PII 처리
- production write action

### 추적

- #862
- #873

## 9. 트랙 간 승격규칙

다음 상태는 자동 연결되지 않는다.

```text
code merged
!= CI passed
!= visual approved
!= deployed
!= live validated
!= production approved
!= actual-site authorized
```

각 PR·issue·보고서는 자신이 어느 트랙과 상태에 속하는지 명시한다.

## 10. 공통 안전원칙

- snapshot·fixture·official citation의 신뢰등급을 구분한다.
- 모델은 공식사실 원본이 아니다.
- 실제 제출·로그인·결제·PII는 first-party authorization 전 금지한다.
- public issue·PR·artifact에 비공개 business/client/person 정보를 남기지 않는다.
- 북구 golden behavior는 generic refactor보다 먼저 보호한다.
- visual approval은 자동화 검사로 대체하지 않는다.
- routine CI는 외부 network와 provider 호출 없이 재현 가능해야 한다.
