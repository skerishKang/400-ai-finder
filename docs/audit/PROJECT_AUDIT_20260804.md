# 400 AI Finder 프로젝트 감사 — 2026-08-04

- 상태: `canonical`
- 감사 기준 `main`: `d0c20501def59015d8e419f2b675dff991b0e522`
- 감사 방식: GitHub 저장소·이슈·PR·CI·주요 설정·시민 UI·Cloudflare Function 읽기 전용 검토
- 코드 변경: 없음
- 실서비스 traffic·Cloudflare dashboard·secrets·WAF 설정: 이번 감사에서 직접 검증하지 않음

## 1. 요약 판정

`400-ai-finder`는 단순한 홈페이지 검색기가 아니다. 현재 저장소에는 다음 제품이 함께 존재한다.

1. 기관 사이트 profile·crawler·document index
2. 근거 기반 질문답변과 provider abstraction
3. 북구 공식사이트 고정밀 clone surface
4. 결정형 시민 journey와 안전한 문서작성 지원
5. Cloudflare Pages 실시간 AI API
6. 다국어 답변·접근성·모바일 UI
7. Page Agent 비교실험
8. clone-first 다기관 플랫폼 foundation

현재 가장 정확한 상태는 다음과 같다.

> **북구 golden clone과 강한 안전·브라우저 계약을 갖춘 통제형 고급 MVP. 실제 시민 대상 상시 운영과 범용 다기관 플랫폼 전환은 진행 전 또는 일부 foundation 단계다.**

## 2. 확인된 강점

### 2.1 북구 golden compatibility

- frozen commit과 route·target·DOM·state vocabulary가 문서화되어 있다.
- deterministic journey와 Page Agent 비교가 같은 controlled clone surface를 사용한다.
- no-submit·no-login·no-payment·no-actual-site-control 경계가 있다.
- golden baseline을 일반화 refactor보다 먼저 보호한다.
- Canonical invariant: [`docs/product/exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md)

### 2.2 공식정보 provenance

canonical snapshot은 source URL, snapshot ID, checksum, captured/verified time, source update time과 route/page identity를 가진다.

중요한 장점은 다음 상태를 분리한 점이다.

- 검증된 canonical snapshot
- provider가 반환한 공식도메인 citation
- snapshot unavailable
- model-only answer

공식도메인 링크라는 이유만으로 canonical 상태로 자동 승격하지 않는 방향은 적절하다.

### 2.3 안전·회귀 테스트

`MVP Contract Checks`는 다음을 포함한다.

- Python unit·contract
- official snapshot·fixture 계약
- Cloudflare Pages build
- Cloudflare Function contract
- desktop·mobile browser E2E
- responsive·accessibility
- link safety
- bilingual·multilingual journey
- Page Agent lab·resident demo
- deterministic vs Page Agent comparison evidence
- no-submit·no-external-request 확인

최신 병합 PR의 workflow도 성공했다.

### 2.4 다국어 fail-closed

한국어·영어·베트남어·태국어·인도네시아어를 닫힌 locale 집합으로 관리하고, 잘못된 언어 답변을 문자·어휘 신호로 검사한다. 교정 재시도를 제한하고 실패 시 주민에게 잘못된 언어의 답변을 그대로 노출하지 않는 정책은 강점이다.

### 2.5 로컬 provider override 경계

로컬 endpoint override는 명시적 opt-in, loopback request, loopback endpoint와 명시적 port를 요구한다. 일반 production request에서는 임의 endpoint override를 신뢰하지 않는다.

## 3. 현재 시스템의 세 가지 원본

### 3.1 Python runtime

- `configs/sites/*.yml`
- crawler·fetch·index·search·operator tools
- `src/llm` provider registry와 model preset

### 3.2 Cloudflare citizen runtime

- `functions/api/mvp/ask.js`
- Gemini·HY3 provider routing
- 별도 action·locale·snapshot·prompt·response 정책

### 3.3 compatibility/platform registry

- `configs/site-registry.json`
- 북구 golden commit과 frozen contract source
- generic adapter matrix foundation

세 runtime의 목적은 다르지만 site ID, 기관명, provider, action, freshness와 API 의미가 중복 관리된다. 현재 가장 큰 구조적 위험은 **잘못된 코드 한 줄보다 원본의 분산**이다.

## 4. P0 운영 차단 항목

### 4.1 공개 AI endpoint abuse·비용·개인정보

저장소에서 확인된 보호:

- POST·OPTIONS 제한
- 질문 300자 제한
- 제한된 CORS
- server-side secret
- provider fallback

저장소에서 확인되지 않은 보호:

- 서버측 rate limit
- Turnstile·bot defense
- 일·월 비용 상한
- 동시요청 제한
- request body byte limit
- 반복요청·자동화 탐지
- 개인정보 입력 경고·redaction·보관정책
- 운영 kill switch

CORS는 브라우저 origin 정책이며 직접 HTTP 호출이나 bot을 막지 않는다.

추적: #1224

### 4.2 timeout·관측성·운영중단

필요사항:

- provider와 전체 request deadline
- request/correlation ID
- provider attempts·latency·fallback reason
- token·cost metadata
- schema·prompt·policy version
- provider disable와 snapshot-only fallback
- 비상 kill switch

추적: #1227

### 4.3 근거 없는 행정정보 확정

snapshot이 없는 질문에도 모델은 일반지식으로 문장을 만들 수 있다. prompt에서 “만들지 말라”고 지시하는 것만으로 다음을 보장할 수 없다.

- 담당부서·기관
- 전화·주소·운영시간
- 수수료
- 기한
- 제출서류
- 자격요건
- 법적 효과
- 신청 URL

근거등급과 claim type에 따라 서버 validator가 확정표현을 차단하거나 완화해야 한다.

추적: #1226

### 4.4 기관 identity 불일치

현재 `bukgu`, `bukgu_gwangju`, UI·prompt의 여러 기관명과 alias가 공존한다. 기관명 변경·도메인 변경·다기관 onboarding에 effective date와 canonical metadata가 필요하다.

추적: #1225

## 5. P1 구조 문제

### 5.1 runtime contract drift

Python, Cloudflare와 site registry의 provider·action·site·freshness 계약을 공통 schema와 adapter로 통합해야 한다.

추적: #1228

### 5.2 Cloudflare Function 단일 파일

`functions/api/mvp/ask.js`는 request validation, CORS, action classification, official context, provider config, local override, prompts, locale assessment, parser, fallback와 response를 함께 담당한다.

동작변경 없는 extraction과 façade 유지가 필요하다.

추적: #1229

### 5.3 시민 shell 단일 파일

`citizen-first-use-shell.js`는 layout state, journey, chat, recommendation, API bridge, history, locale, accessibility, motion과 continue-reading을 함께 담당한다.

public DOM·state·window API를 유지한 점진적 분리가 필요하다.

추적: #1230

### 5.4 CI 단일 거대 job

계약범위는 강하지만 하나의 job에 많은 Python·Node·browser step이 순차 배치된다.

개선사항:

- job 분리·병렬화
- cache
- dependency lock
- static·secret·dependency scan
- browser trace·screenshot artifact
- required check·branch protection

추적: #1231

### 5.5 다기관 실제 검증 부족

여러 site profile이 존재하는 것과 generic clone pipeline이 검증된 것은 다르다. 북구, 다른 지자체, 구조가 다른 사이트 유형을 같은 SiteSpec·Site Model·clone compiler로 검증해야 한다.

추적: #1232, 기존 #1181

## 6. P2 저장소 운영

### 6.1 원격 브랜치 과다

감사 시점 branch search 결과는 300개 이상이다. 완료된 stage·docs·test·noop·tmp branch가 혼재한다.

삭제 전 inventory와 merged/superseded evidence가 필요하다. history rewrite나 일괄삭제를 먼저 해서는 안 된다.

추적: #1233

### 6.2 루트 governance 문서 부재

감사 시점 다음 파일이 없었다.

- `CONTRIBUTING.md`
- `SECURITY.md`
- root `LICENSE`
- 공통 PR template
- bug·improvement issue template

이번 문서 PR은 `CONTRIBUTING.md`, `SECURITY.md`와 템플릿을 추가한다. 라이선스는 법적 선택이므로 자동 결정하지 않고 #1234에서 inventory·승인을 거친다.

### 6.3 code·fixture·asset license

공개 저장소에는 자체 코드뿐 아니라 공식사이트 fixture, screenshot, presentation, static asset와 vendored runtime이 있다. 각 분류의 원출처·version·license·notice와 재배포 조건이 필요하다.

추적: #1234

## 7. 기존 장기 이슈 정리

| 이슈 | 현재 역할 |
|---|---|
| #1080 | 북구 route fixture·provenance·visual promotion 프로그램 |
| #1150 | offline/mock freshness foundation 이후 실제 answer-time retrieval 후속 |
| #1181 | clone-first multi-site platform parent |
| #862 | public reference·navigator·authorized operational integration |
| #873 | full Buk-gu rebuild와 integration planning |

기존 이슈는 폐기하지 않는다. 총괄 #1235가 운영안전·single source·modularization·governance gap을 추가로 묶는다.

## 8. 현재 허용·금지 경계

### 허용

- offline snapshot·fixture 기반 개발과 CI
- public reference의 승인된 read-only capture
- clone surface의 결정형 journey
- 실제 제출 없는 문서 초안·pre-fill demo
- 별도 승인된 staging provider test
- exact-head와 artifact를 남긴 visual review

### 운영승인 전 금지

- 보호장치 없는 공개 AI 비용 노출
- 실제 민원 제출
- 실제 로그인·결제
- 주민등록번호 등 고위험 PII 처리
- 공식 근거 없는 연락처·기한·수수료 확정
- 승인 없는 live scraping·provider 실행
- actual public site control 주장
- 고객·기관 비공개 자료의 public repo 반입

## 9. 권장 실행순서

1. #1224 endpoint protection
2. #1227 timeout·observability·kill switch
3. #1226 evidence policy
4. #1225 canonical SiteSpec
5. #1228 shared contracts
6. #1231 CI quality gate
7. #1229 Cloudflare Function modularization
8. #1230 citizen shell modularization
9. #1080 fixture·visual coverage 지속
10. #1150 freshness staging
11. #1232 multi-site onboarding
12. #1233 repository governance
13. #1234 licensing·provenance
14. #862·#873 authorized integration

상세 단계는 [`../implementation/ROADMAP_20260804.md`](../implementation/ROADMAP_20260804.md)를 따른다.

## 10. 최종 결론

이 저장소의 핵심 자산은 단순한 코드량이 아니라 다음 계약이다.

- 북구 golden baseline
- 공식 snapshot provenance
- no-submit 안전경계
- 다국어 fail-closed
- desktop·mobile·accessibility browser evidence
- deterministic vs Page Agent 비교자료

기능을 계속 추가하기 전에 이 자산을 공통 SiteSpec·evidence policy·protected API·modular runtime·release governance로 묶어야 한다. 그 작업이 완료되면 북구 단일 시연판에서 안전한 다기관 AI 홈페이지 플랫폼으로 전환할 수 있다.
