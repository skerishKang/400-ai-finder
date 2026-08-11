# Contributing to 400 AI Finder

이 저장소는 Buk-gu golden reference, 공식 fixture, 시민 UI, Cloudflare AI API, crawler/index, 다국어, Page Agent 비교와 앞으로의 general-site AI Browser platform을 함께 관리한다.

핵심 원칙은 두 가지다.

1. **shared core·golden·safety 변경은 엄격하게 검증한다.**
2. **routine site onboarding은 모든 사이트 차이를 bespoke feature issue로 만들지 않는다.** 자동 생성 결과와 exception을 우선하고, 공통 재사용 가치가 있는 gap만 core issue로 승격한다.

## 1. 작업 유형을 먼저 분류한다

### Type A — Shared Core / Product Change

다음은 기존처럼 Issue first가 필수다.

- shared runtime / provider / evidence / safety
- SiteSpec/schema/runtime vocabulary
- archetype/capability contract
- generic Site Model / clone or preview compiler
- crawler/parser/indexer common behavior
- browser/action engine
- API/schema/public contract
- Buk-gu golden compatibility surface
- security/privacy/live-public/deployment behavior
- production promotion

Issue에는 최소 다음을 포함한다.

- 문제와 사용자 영향
- product track
- include/exclude scope
- 안전·개인정보·network 영향
- acceptance criteria
- test/evidence 계획
- migration/rollback

### Type B — Routine Site Onboarding

공통 onboarding pipeline이 존재한 이후, 새 사이트를 분석·생성하는 작업 자체는 매번 bespoke feature issue를 요구하지 않는 것을 목표로 한다.

Routine onboarding은 다음을 하나의 reviewable onboarding report/PR bundle로 남길 수 있다.

- input URL/SiteSpec identity
- network/acquisition mode
- detected archetype + confidence
- detected capabilities + confidence
- generated Site Model/knowledge/action/browser artifacts
- automation / review / unsupported ratio
- exception queue
- provenance
- `shared_core_changed: yes|no`
- production promotion 여부

`shared_core_changed: no`이고 generated preview만 만드는 경우, 단순 site-specific override나 low-confidence content 하나하나를 별도 Issue로 만들 필요는 없다.

### Type C — Exception Escalation

Routine onboarding exception 중 다음은 별도 Issue로 승격한다.

- 다른 사이트에도 재사용되는 capability가 없음
- shared parser/runtime/compiler bug
- archetype contract gap
- security/privacy/evidence/safety 문제
- 반복되는 onboarding failure pattern
- production promotion blocker
- breaking migration 필요

사이트 하나에서만 발생하는 명시적 reviewed override는 공통 issue보다 onboarding artifact/config로 남기는 것을 우선한다.

## 2. 브랜치와 worktree

Shared core와 문서/정책 변경은 `main`에서 전용 branch를 만든다.

권장:

```text
feat/<issue>-<scope>
fix/<issue>-<scope>
security/<issue>-<scope>
refactor/<issue>-<scope>
test/<issue>-<scope>
docs/<issue>-<scope>
```

동시 작업은 별도 worktree를 사용한다. 다른 active branch의 파일을 섞지 않는다.

Routine onboarding의 branch/PR 자동화 방식은 해당 pipeline이 구현될 때 별도 contract로 고정한다. 현재 존재하지 않는 자동화를 구현된 것처럼 주장하지 않는다.

## 3. Product track 표시

PR에서 하나 이상 선택한다.

- Buk-gu golden clone
- 근거 기반 AI 시민안내
- 공식정보 freshness
- Python crawler·operator runtime
- Cloudflare citizen runtime
- Page Agent comparison
- multi-site / general-site platform
- routine site onboarding
- authorized first-party integration
- repository·documentation governance

트랙별 경계는 `docs/product/PRODUCT_TRACKS_AND_BOUNDARIES.md`를 따른다.

## 4. Release / readiness gate 표시

PR이 목표로 하는 Gate를 명시한다.

- Gate A: frozen controlled demo
- Gate B: protected public pilot
- Gate C: evidence-safe AI pilot
- Gate D: unified platform foundation
- Gate E: modular runtime
- Gate F: official freshness staging
- Gate G1: generated onboarding preview
- Gate G2: archetype golden validation
- Gate G3: resident/default or production promotion
- Gate H: authorized operational integration
- No promotion

`generated_preview`는 `exact`, `archetype_golden`, `resident_default_approved`, `production approved`와 같은 상태가 아니다.

## 5. Data·secret·개인정보

커밋 금지:

- API key·token·credential
- `.env`
- raw citizen transcript
- 주민번호·전화·이메일·상세주소 등 불필요한 PII
- 고객·기관 비공개자료
- production logs
- 내부 URL·account ID
- unreviewed screenshots with private data

테스트는 합성·익명화 fixture를 사용한다.

공식 공개 fixture도 source URL, capture/verified time, checksum과 usage 목적을 기록한다. 공개되어 있다는 사실과 재배포 권리는 별개다.

## 6. Network mode

PR/onboarding report에 하나를 명시한다.

- `offline/mock`
- `fixture-only`
- `controlled read-only live`
- `provider staging`
- `production integration`

routine CI는 외부 network·provider를 호출하지 않는다.

**URL supplied != live network authorized.** URL이 입력되었다는 사실만으로 crawl/provider/live fetch가 승인되는 것은 아니다.

live test가 필요하면 target·method·limit·credentials owner·output sanitization·cleanup·approval을 기록한다.

## 7. Buk-gu golden 보호

다음은 frozen contract다.

- closed route IDs
- closed action target IDs
- public window API
- DOM IDs·data state
- canonical fixture identity
- no-submit boundary
- golden comparison evidence

변경 전 dedicated migration issue와 compatibility 계획이 필요하다.

Buk-gu golden과 향후 explicit exact/archetype-golden/production promotion surface는 applicable exact/visual 정책을 따른다.

반대로 `generated_preview`는 명시적으로 non-default/non-exact 상태로 존재할 수 있으며, unresolved/low-confidence 항목을 exception으로 표시해야 한다. Generated preview가 resident-default를 자동으로 통제해서는 안 된다.

## 8. API·AI 변경

확인사항:

- request validation
- input byte·length limit
- provider timeout
- rate limit·cost effect
- failure code
- API schema version
- source·freshness metadata
- high-risk claim evidence
- locale assessment
- model/provider fallback·retry budget
- tool/browser action bounds when applicable
- secret·raw error sanitization
- kill switch·rollback

model output의 action·URL·JSON을 신뢰하지 않고 closed schema·allowlist로 검증한다.

## 9. Site·crawler·onboarding 변경

확인사항:

- canonical site ID·legacy alias
- target domain allowlist
- robots·crawl budget
- include·deny·protected patterns
- redirect·final URL policy
- attachment type
- source provenance
- duplicate·stale handling
- live opt-in
- detected/proposed archetype
- detected capabilities
- confidence / unsupported / exception reporting

새 기관은 bespoke renderer보다 SiteSpec·data·theme·parser profile·shared capability를 우선한다. Shared core에 `if site_id == ...`가 누적되는 변경은 별도 설계 근거를 요구한다.

## 10. UI / Browser 변경

Core/golden/production UI 변경에서 applicable evidence:

- desktop
- mobile
- keyboard
- screen-reader semantics
- reduced motion
- long answer·overflow
- locale change
- cancellation
- browser back/forward
- error·loading·empty states
- action visibility / interruption / takeover when Browser Use is in scope

Buk-gu golden clone UI와 explicit promotion surface는 applicable accepted reference/visual policy를 따른다.

Generated onboarding preview는 자동 screenshot/browser QA를 사용할 수 있으나 그것만으로 project-owner visual approval이나 production promotion을 주장하지 않는다.

## 11. Refactor

구조분리와 behavior change를 한 PR에 섞지 않는다.

- public façade 유지
- contract test 먼저
- 좁은 extraction
- no circular dependency
- generated artifact 여부 명시
- behavior-equivalence evidence

단, deferred refactor를 단순히 깔끔함을 위해 multi-site progress의 선행 blocker로 만들지 않는다. 실제 유지보수/플랫폼 필요와 연결한다.

## 12. Test

Shared core/product 변경의 기본 검증:

```bash
python -m pytest -q tests/
npm ci --ignore-scripts
```

PR scope에 따라 repository workflow의 관련 browser·Function·build contract를 실행한다.

Routine onboarding은 향후 onboarding pipeline이 정의한 generated QA + exception report를 우선하며, shared core가 변경되면 해당 core contract도 함께 실행한다.

금지:

- assertion 약화
- skip·xfail로 회귀 숨김
- 일부 scenario 선택 누락으로 성공률 부풀리기
- unsupported/low-confidence item 숨김
- model-only visual approval
- live test 결과를 routine offline CI 결과로 표현

## 13. PR 작성

Shared core/product PR 필수:

- related issue
- summary
- include/exclude
- base/head SHA
- changed files
- track·gate
- network/provider mode
- data·PII·secret statement
- validation
- browser/visual evidence when applicable
- deployment impact
- rollback
- known limitations

Routine onboarding PR/report에서는 추가로 다음을 우선한다.

- input site identity
- archetype/capability result
- automation/review/unsupported ratio
- exception queue summary
- generated artifact identities
- provenance
- shared core changed `YES/NO`
- production promotion `YES/NO`

## 14. Review 우선순위

1. actual submit·login·payment·PII 위험
2. secret·endpoint·SSRF·abuse·cost
3. official source·evidence correctness
4. golden route·DOM·state compatibility
5. generated preview의 잘못된 exact/production claim
6. data loss·migration·rollback
7. cross-site reuse / archetype / capability correctness
8. accessibility·mobile·locale
9. maintainability

## 15. 병합 전 exact-head 확인

Shared core/product/docs PR은 병합 직전 다음을 다시 확인한다.

- current PR head SHA
- base and behind state
- exact-head CI
- mergeability
- review submissions
- unresolved threads
- changed filenames
- secrets·PII·unexpected artifacts

head가 변경되면 이전 검증을 재사용하지 않는다.

## 16. 배포

merge는 deploy가 아니다.

배포 관련 PR은 다음을 기록한다.

- environment
- deployment ID
- deployed SHA
- time·operator
- smoke results
- secrets owner
- rollback

public URL 응답만으로 deployed SHA를 확정하지 않는다. Generated preview 생성도 production deployment 승인과 동일하지 않다.

## 17. Issue closeout

완료 comment 또는 body update에 다음을 남긴다.

- PR·merge SHA
- tests/evidence
- deployment state
- acceptance criteria
- known limitations
- follow-up issues

Routine onboarding은 모든 exception을 issue화하지 않고, Type C 승격기준에 해당하는 공통 gap만 follow-up issue로 만든다.

자세한 기준:

- `docs/CURRENT_STATUS.md`
- `docs/implementation/RELEASE_GATES.md`
- `docs/operations/REPOSITORY_GOVERNANCE.md`
