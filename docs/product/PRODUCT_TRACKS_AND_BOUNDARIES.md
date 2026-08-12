# 제품 트랙과 운영경계

- 상태: `canonical`
- 기준일: 2026-08-12
- 현재 lifecycle 정렬: #1301
- active onboarding validation: #1232

`400-ai-finder`에는 서로 다른 목적·위험·완료조건을 가진 여러 제품트랙이 있다. 모든 트랙을 하나의 “AI Finder 기능”으로 취급하면 clone MVP, 실시간 조회, actual-site 통제와 production 운영이 혼동된다.

가장 중요한 제품단계 구분은 다음이다.

```text
현재: faithful clone MVP + AI Finder/Browser on the clone
나중: 기관 승인 후 first-party actual-site integration
```

현재 ordinary pre-integration lifecycle의 canonical 문서는 [`clone-first-general-site-platform-strategy.md`](./clone-first-general-site-platform-strategy.md)다.

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

이 조건들은 공개 AI 운영과 사실확정 경계에 관한 것이며, faithful clone의 화면을 원본 일치 기준으로 재현하는 작업 자체의 blocker가 아니다.

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

각 단계는 자신의 network/runtime 경계를 가진다.

Clone visible surface의 freshness와 AI answer evidence freshness는 동일한 상태라고 가정하지 않는다. 최신 AI evidence를 사용하더라도 기존 clone이 자동으로 live mirror로 변하는 것은 아니다.

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

- live fetch는 해당 실행모드와 project scope를 명시한다.
- routine CI는 offline fixture 사용
- data/raw·processed·index·runs를 기본 Git 추적하지 않음
- 고객·기관 비공개자료는 public repo에 반입하지 않음

## 5. 트랙 E — Cloudflare 시민 runtime

### 목적

Pages의 citizen surface와 `/api/mvp/ask` Function을 통해 공개 시연 또는 제한된 pilot을 제공한다.

### 현재 범위

- Gemini default provider path
- canonical snapshot context
- deterministic action override
- locale 답변정책
- server-side secrets
- static fallback build

### production 전 별도 검토항목

- rate limit·bot defense·cost cap
- provider timeout
- request ID·latency·attempt metadata
- PII warning·redaction·retention
- evidence-gated high-risk claim policy
- kill switch·snapshot-only fallback

이 항목들은 public/production runtime을 실제 운영하려는 때 적용한다. 내부/controlled clone MVP의 faithful reproduction을 선행 차단하는 조건으로 사용하지 않는다.

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
- 실제 provider 비교는 별도 staging·비용·runtime 조건을 따른다.

## 7. 트랙 G — Clone-first 다기관 플랫폼 / faithful clone MVP

### 목적

새 기관을 대상으로 **실제 사이트를 대체 운영하기 전에**, 해당 기관의 현재 홈페이지를 이해하고 faithful clone MVP를 생성한 뒤 그 clone 위에서 AI Finder/Browser를 검증한다.

### Stable product shape

```text
left  = repository-controlled faithful clone of the target site's reference baseline
right = AI conversation / answer / search / navigation / bounded Browser Use
```

### Named-site onboarding pipeline

```text
actual target site
  -> scoped point-in-time reference baseline
  -> SiteSpec / archetype / capabilities
  -> generic Site Model
  -> faithful clone candidate
  -> asset/provenance mapping
  -> structural/content/interaction/visual comparison
  -> clone MVP ready
  -> knowledge index
  -> action graph / browser model
  -> AI-on-clone validation
  -> QA + exception queue
```

### Platform/core structural development

Synthetic/offline fixture를 사용해 SiteSpec, archetype/capability, generic Site Model, structural preview, QA, report schema 등을 검증할 수 있다.

하지만 이 evidence는 named real site의 clone 완료 증거가 아니다.

```text
structural generated preview
!= faithful clone candidate
!= clone MVP ready
```

### Clone scope

기관 전체 route를 첫 MVP에서 모두 exact하게 복제할 필요는 없다.

대신 MVP scope를 명시하고:

- scope 안의 page/state는 reference를 임의 재설계하지 않는다.
- scope 밖은 fabricate하지 않고 `capture_required`/exception으로 남긴다.
- `clone_mvp_ready`와 stronger `exact` claim을 구분한다.

### Clone freshness

clone은 continuous live mirror가 아니다.

```text
approved clone v1
  + explicit recapture
  -> new reference
  -> clone v2 candidate
  -> review
```

원본 사이트가 바뀌었다는 사실만으로 기존 clone이 자동 변경되지 않는다.

### 검증단계

1. Buk-gu protected golden reference
2. Seo-gu faithful second-site proof
3. materially different third-site/cross-domain proof

현재 Seo-gu #1298~#1300은 generic structural/platform evidence다. 실제 Seo-gu reference baseline과 faithful visual clone proof가 추가돼야 named-site clone 완료로 볼 수 있다.

### 경계

- 기관별 bespoke renderer 누적 금지
- shared engine은 generic하되 rendered clone은 target site처럼 보여야 함
- site-specific 차이는 data·config·theme·parser profile·reviewed override로 표현
- 북구 golden을 parity 전 교체하지 않음
- 70~80% supervised automation을 첫 목표로 삼음
- automation ratio는 fidelity evidence가 아님
- low-confidence/unsupported/capture-required 항목을 숨기지 않음
- 현재 clone MVP 단계의 fidelity 작업에 미래 actual-site 운영조건을 임의의 선행 blocker로 추가하지 않음

### Controlled stakeholder evaluation

기관의 production 운영권한을 받기 전 clone은 개발·검증·stakeholder evaluation surface다.

이 단계의 목적은 의사결정자가 자기 기관 홈페이지에 AI가 들어간 모습을 실제처럼 체험하도록 하는 것이다. 따라서 left-side fidelity를 일반적인 prototype 수준으로 낮추는 것은 제품 요구와 맞지 않는다.

고객·기관의 비공개 사업관계 정보는 public repo에 기록하지 않는다.

### 추적

- #1181 historical foundation
- #1287 generic contract foundation — completed
- #1232 active onboarding validation
- #1301 lifecycle/governance alignment

## 8. 트랙 H — 실제 기관사이트 first-party integration — 미래 단계

### 목적

기관이 우리 회사에 실제 production 홈페이지의 구축·운영·유지보수 또는 AI 통합 권한을 명시적으로 부여한 이후, clone에서 검증한 AI Finder/Browser 개념을 실제 사이트에 first-party 방식으로 통합한다.

### 시작조건

이 트랙은 현재 clone MVP의 기본 개발단계가 아니다.

기관의 실제 도입·운영 승인이 생긴 뒤 그 기관 환경을 기준으로 다음을 확정한다.

- credentials와 secret owner
- deployment/hosting owner
- information-security requirements
- privacy / PII responsibility
- authentication boundary
- real submission/payment/write boundary
- internal-system integration
- monitoring / incident / support ownership
- staging / rollback

### 중요한 경계

위 production 조건은 **Track H가 실제로 열릴 때** 다룬다.

Track G의 controlled faithful-clone MVP를 만들고, 원본과 비교하고, AI를 clone 위에서 검증하기 위한 선행조건으로 Track H의 production 요구사항을 끌어오지 않는다.

### 이 단계 전 비주장

- actual production site를 현재 제어한다고 주장하지 않음
- 실제 form submit/login/payment/PII 처리를 clone MVP 완료와 동일시하지 않음
- clone 시연을 production integration 완료라고 표현하지 않음

### 추적

- #862
- #873

## 9. 트랙 간 승격규칙

다음 상태는 자동 연결되지 않는다.

```text
code merged
!= structural preview
!= reference baseline ready
!= clone candidate
!= clone MVP ready
!= exact
!= resident/default approved
!= deployed
!= live validated
!= production approved
!= actual-site authorized/integrated
```

각 PR·issue·보고서는 자신이 어느 트랙과 상태에 속하는지 명시한다.

## 10. 공통 원칙

- 현재 pre-integration default는 faithful clone MVP다.
- 실제 기관사이트 운영/통합은 기관 승인 후 미래 Track H다.
- generic structural proof와 named-site faithful clone proof를 혼동하지 않는다.
- snapshot·fixture·official citation의 신뢰등급을 구분한다.
- 모델은 공식사실 원본이 아니다.
- public issue·PR·artifact에 비공개 business/client/person 정보를 남기지 않는다.
- 북구 golden behavior는 generic refactor보다 먼저 보호한다.
- visual approval은 자동화 검사로 대체하지 않는다.
- routine CI는 외부 network와 provider 호출 없이 재현 가능해야 한다.
- public/open-source redistribution 판단과 controlled faithful-clone fidelity 판단을 동일한 gate로 취급하지 않는다.
