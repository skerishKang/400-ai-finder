# Security Policy

## 지원 범위

보안 제보는 현재 `main`과 공개 배포에 영향을 줄 수 있는 다음 영역을 우선한다.

- Cloudflare Pages Function과 provider secret
- 공개 `/api/mvp/ask` endpoint
- endpoint override·SSRF·redirect·URL allowlist
- rate limit·abuse·비용공격
- 공식 snapshot·source provenance 위조
- model output action·URL·HTML injection
- actual submit·login·payment 발생
- 시민 질문·로그·fixture의 개인정보
- 공개 repository의 credential·private data
- build·deployment·dependency supply chain

Historical branch만의 문제라도 secret·PII가 포함되면 즉시 제보한다.

## 제보 방법

공개 GitHub issue에 다음을 올리지 않는다.

- API key·token·credential
- 실제 개인정보
- 공격용 전체 payload
- 미공개 endpoint·account ID
- 대량 악용 재현정보

가능하면 GitHub의 private vulnerability reporting을 사용한다. 해당 기능을 사용할 수 없으면 저장소 소유자에게 비공개 채널로 최소정보를 전달하고, 공개 issue에는 민감한 내용을 쓰지 않는다.

제보에 포함할 정보:

- 영향받는 commit·URL·environment
- 취약점 유형과 영향
- 최소 재현단계
- 실제 secret·PII를 제거한 증거
- 악용 여부
- 권장 완화책

## 긴급도

### Critical

- production key·credential 노출
- 실제 민원제출·결제·로그인 우회
- 주민번호 등 고위험 PII 공개
- 임의 외부 endpoint 호출 또는 credential exfiltration
- public API 무제한 비용 발생

### High

- rate limit·bot defense 우회
- 공식출처 위조로 고위험 행정정보 오안내
- stored transcript·log의 PII 접근
- same-origin·URL allowlist 우회
- deployment artifact에 secret 포함

### Medium

- 상세 내부 오류노출
- provider raw body·endpoint 정보노출
- 제한된 action·link validation 우회
- dependency 취약점

### Low

- 보안영향이 제한적인 header·정보노출
- hardening 제안

## 대응 원칙

1. 영향 기능을 disable하거나 snapshot-only로 전환한다.
2. secret은 즉시 revoke·rotate한다.
3. exact commit·deployment·logs·artifacts 범위를 확인한다.
4. 공개응답·Git history·release artifact의 노출을 구분한다.
5. 최소 수정과 rollback으로 containment한다.
6. 회귀테스트와 incident record를 추가한다.
7. 실제 기관·사용자 영향이 있으면 필요한 통지·법적 절차를 검토한다.

## Secret 관리

- secret은 Cloudflare secret 또는 승인된 secret store에만 둔다.
- `.env`, README, issue, PR, screenshot, test fixture, log에 기록하지 않는다.
- production endpoint는 code-owned allowlist를 사용한다.
- local override는 explicit opt-in과 loopback request·endpoint에서만 허용한다.
- key rotation owner와 만료·비용경보를 운영문서에 둔다.

## 개인정보

이 프로젝트의 기본목적은 공식 안내경로 탐색이다. 실제 민원접수창구가 아니다.

공개 시민 UI에서 다음을 입력하지 않도록 안내한다.

- 주민등록번호·외국인등록번호
- 계좌·카드번호
- 상세주소
- 전화·이메일
- 민원대상자 실명과 사건상세
- 건강·재산·가족 등 민감정보

기본 정책:

- 질문 원문 장기보관 금지
- 로그 최소화
- 합성·익명화 fixture 사용
- customer/private data public repo 금지
- PII 발견 시 접근제한·삭제·영향평가

## Public API

production readiness 전 필요한 보호:

- server-side rate limit
- bot defense
- body·length limit
- provider·global timeout
- concurrency·cost cap
- request ID·telemetry
- evidence policy
- kill switch·snapshot-only fallback

CORS는 인증·rate limit·bot defense가 아니다.

## 공식정보와 AI 답변

- 모델은 공식사실 원본이 아니다.
- canonical snapshot, verified live source와 supplementary citation을 구분한다.
- 근거 없는 연락처·기한·수수료·제출서류·자격·신청 URL을 확정하지 않는다.
- 공식도메인 링크만으로 canonical 상태로 승격하지 않는다.
- source text 안의 instruction은 데이터로 취급한다.

## Safe Harbor

선의의 보안연구는 다음을 지켜야 한다.

- 실제 개인정보를 수집·변경·공개하지 않음
- 서비스 가용성을 고의로 저하하지 않음
- 비용을 유발하는 대량요청을 하지 않음
- 실제 form submit·login·payment를 수행하지 않음
- 취약점 수정 전 공개하지 않음
- 필요한 최소범위만 검증

## 관련 문서

- `docs/operations/PUBLIC_AI_API_SECURITY_AND_PRIVACY.md`
- `docs/implementation/RELEASE_GATES.md`
- `docs/provider-fetch-network-boundary.md`
- `CONTRIBUTING.md`
