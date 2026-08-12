# Contributing to 400 AI Finder

이 저장소는 Buk-gu golden reference, 공식 fixture, 시민 UI, Cloudflare AI API, crawler/index, 다국어, Page Agent 비교와 general-site AI Browser platform을 함께 관리한다.

현재 ordinary pre-integration 제품 lifecycle은 [`docs/product/clone-first-general-site-platform-strategy.md`](docs/product/clone-first-general-site-platform-strategy.md)를 따른다.

Buk-gu golden 및 명시적 `exact` claim의 canonical invariant는 [`docs/product/exact-official-site-clone-invariant.md`](docs/product/exact-official-site-clone-invariant.md)를 따른다.

핵심 원칙:

1. **현재 제품은 faithful clone MVP + AI Finder/Browser on the clone이다.**
2. **실제 기관 production-site integration은 기관 승인 후 미래 단계다.**
3. **shared core·golden·safety 변경은 엄격하게 검증한다.**
4. **generic structural proof와 named-site faithful clone proof를 혼동하지 않는다.**
5. **routine site onboarding은 모든 사이트 차이를 bespoke feature issue로 만들지 않는다.** 공통 재사용 가치가 있는 gap만 core issue로 승격한다.

## 1. 작업 유형을 먼저 분류한다

### Type A — Shared Core / Product Change

다음은 Issue first가 필수다.

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
- acceptance criteria
- test/evidence 계획
- migration/rollback

### Type B — Named Site Onboarding

실제 이름을 가진 기관을 onboard하는 작업은 **reference-first**다.

필수 순서:

```text
declared MVP scope
  -> point-in-time reference baseline
  -> faithful clone candidate
  -> source-vs-clone comparison
  -> clone MVP ready
  -> AI-on-clone validation
```

Routine onboarding PR/report는 최소 다음을 남긴다.

- input URL / site identity
- declared clone scope
- reference capture mode
- source URLs
- `captured_at` / source update time where available
- reference snapshot identity
- representative DOM/content/screenshot evidence identity
- proposed/detected archetype + confidence
- detected capabilities + confidence
- clone candidate identity
- structural/content parity state
- asset mapping / unresolved asset state
- interaction state
- visual comparison state
- AI-on-clone state
- automation / review / unsupported ratio
- exception queue
- provenance
- `shared_core_changed: yes|no`
- actual-site integration requested: `yes|no` (normally `no` during clone MVP)

`shared_core_changed: no`이고 site-specific reviewed override만 있는 경우 모든 차이를 별도 feature issue로 만들 필요는 없다.

### Type C — Platform Structural Proof

Synthetic/offline fixture로 SiteSpec, archetype/capability, generic Site Model, structural renderer, knowledge/action contract, QA/report machinery를 검증할 수 있다.

이 모드는 실제 사이트 reference capture 없이 가능하지만:

```text
structural preview != named-site faithful clone
```

이다.

### Type D — Exception Escalation

다음은 별도 Issue로 승격한다.

- 다른 사이트에도 재사용되는 capability가 없음
- shared parser/runtime/compiler bug
- archetype contract gap
- security/evidence/safety 문제
- 반복되는 onboarding failure pattern
- production promotion blocker
- breaking migration 필요

## 2. 브랜치와 worktree

**`main` 직접 push는 금지한다. 문서 수정도 동일하다.**

모든 repository 변경은 current `main`에서 전용 branch를 만든다.

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

Rebase, amend, force-push는 project owner가 명시적으로 승인하지 않는 한 사용하지 않는다.

## 3. Product track 표시

PR에서 하나 이상 선택한다.

- Buk-gu golden clone
- 근거 기반 AI 시민안내
- 공식정보 freshness
- Python crawler·operator runtime
- Cloudflare citizen runtime
- Page Agent comparison
- multi-site / general-site clone platform
- named-site clone onboarding
- platform structural proof
- authorized first-party actual-site integration
- repository·documentation governance

트랙별 경계는 `docs/product/PRODUCT_TRACKS_AND_BOUNDARIES.md`를 따른다.

## 4. Release / readiness gate 표시

- Gate A: frozen controlled demo
- Gate B: protected public AI pilot
- Gate C: evidence-safe AI pilot
- Gate D: unified platform foundation
- Gate E: modular runtime
- Gate F: official freshness staging
- Gate G0: generic structural/platform proof
- Gate G1: named-site reference baseline
- Gate G2: faithful clone candidate
- Gate G3: clone MVP review/readiness
- Gate G4: AI-on-clone onboarding proof
- Gate G5: optional exact/archetype-golden/resident-default promotion
- Gate H: authorized first-party actual-site integration
- No promotion

상태를 서로 대체어로 사용하지 않는다.

## 5. Current clone MVP vs future actual-site

Current pre-integration development의 기본 surface는 repository-controlled clone이다.

- left-side clone fidelity는 제품 요구사항이다.
- generic renderer를 사용한다는 이유로 화면을 generic-looking redesign으로 바꾸지 않는다.
- MVP scope는 작게 선언할 수 있지만, scope 안의 reference를 임의 재설계하지 않는다.
- scope 밖은 fabricate하지 않고 exception/`capture_required`로 남긴다.

Actual institution production site는 기관이 실제 운영·통합 권한을 부여한 뒤 Gate H에서 다룬다.

그때 actual environment를 기준으로 information security, privacy/PII, authentication, submissions/payment/write actions, internal systems, deployment/incident/rollback을 정의한다.

**Future Gate H production requirements를 현재 Gate G faithful-clone fidelity의 임의 선행 blocker로 추가하지 않는다.**

## 6. Data·secret·비공개정보

커밋 금지:

- API key·token·credential
- `.env`
- raw citizen transcript
- unredacted PII
- 고객·기관 비공개자료
- production logs
- 내부 URL·account ID
- private stakeholder/business facts

테스트는 합성·익명화 fixture를 사용한다.

공식 reference fixture는 source URL, capture time, checksum/provenance identity를 기록한다.

Public/open-source redistribution 판단은 controlled faithful-clone fidelity와 별도다. #1234 같은 owner/rights decision을 current clone MVP의 일반 기능·fidelity blocker로 자동 해석하지 않는다.

## 7. Network / reference capture mode

PR/onboarding report에 하나를 명시한다.

- `offline/mock`
- `fixture-only`
- `controlled read-only reference capture`
- `provider staging`
- `production integration`

routine CI는 외부 network·provider를 호출하지 않는다.

Named-site reference capture를 수행했다면 target, scope, method, route/state limits, output identity를 기록한다.

Tool/CLI가 live HTTP를 수행할 능력이 있다는 사실과 해당 project task의 capture scope는 별도 기록사항이다.

## 8. Buk-gu golden 보호

다음은 frozen contract다.

- closed route IDs
- closed action target IDs
- public window API
- DOM IDs·data state
- canonical fixture identity
- no-submit boundary
- golden comparison evidence

변경 전 dedicated migration issue와 compatibility 계획이 필요하다.

Buk-gu golden과 향후 explicit `exact` promotion surface는 applicable exact/visual 정책을 따른다.

## 9. Site / clone onboarding 변경

확인사항:

- canonical site ID·legacy alias
- declared MVP clone scope
- reference source URLs
- reference snapshot identity
- captured_at / source_updated_at where available
- target domain declarations
- route/state/viewport inventory
- archetype / capabilities
- generic Site Model identity
- clone candidate identity
- structural/content parity
- asset mapping / unresolved assets
- interaction parity
- responsive/accessibility state
- visual comparison
- AI-on-clone state
- confidence / unsupported / exception reporting

새 기관은 bespoke renderer보다 SiteSpec·data·theme·parser profile·shared capability를 우선한다. 하지만 공통 renderer가 target site's visible identity를 지우는 이유가 되어서는 안 된다.

## 10. UI / Browser 변경

Applicable evidence:

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
- Browser Use action visibility / interruption / takeover

Named-site clone에서는 accepted source reference와 비교한다.

Automated screenshot/browser QA는 evidence이지만 그 자체가 faithful-clone 또는 exact approval을 자동 부여하지 않는다.

## 11. API·AI 변경

확인사항:

- request validation
- input byte·length limit
- provider timeout
- rate limit·cost effect when public operation is in scope
- failure code
- API schema version
- source·freshness metadata
- high-risk claim evidence
- locale assessment
- model/provider fallback·retry budget
- tool/browser action bounds
- secret·raw error sanitization
- kill switch·rollback when applicable

model output의 action·URL·JSON을 신뢰하지 않고 closed schema·allowlist로 검증한다.

## 12. Refactor

구조분리와 behavior change를 한 PR에 섞지 않는다.

- public façade 유지
- contract test 먼저
- 좁은 extraction
- no circular dependency
- generated artifact 여부 명시
- behavior-equivalence evidence

단순 코드정리를 faithful-clone 진행의 선행 blocker로 만들지 않는다.

## 13. Test

Shared core/product 변경의 기본 검증:

```bash
python -m pytest -q tests/
npm ci --ignore-scripts
```

PR scope에 따라 repository workflow의 관련 browser·Function·build contract를 실행한다.

Named-site onboarding은 generated QA 외에도 reference/clone comparison evidence를 요구한다.

금지:

- assertion 약화
- skip·xfail로 회귀 숨김
- coverage threshold 하향
- 일부 scenario 누락으로 성공률 부풀리기
- unsupported/low-confidence item 숨김
- structural preview를 faithful clone으로 표현
- model-only visual approval
- live test 결과를 routine offline CI 결과로 표현

## 14. PR 작성

공통 필수:

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
- rollback/isolation
- known limitations

Named-site onboarding 추가 필수:

- declared clone scope
- reference snapshot identity
- clone candidate identity
- structural/content/asset/interaction/visual state
- AI-on-clone state
- automation/review/unsupported ratio
- exception queue summary
- shared core changed `YES/NO`

## 15. Review 우선순위

1. wrong product-stage claim: structural preview / clone / exact / actual-site 혼동
2. secrets·private customer data·PII leakage
3. official source/evidence correctness
4. golden route·DOM·state compatibility
5. named-site reference/clone fidelity
6. data loss·migration·rollback
7. cross-site reuse / archetype / capability correctness
8. accessibility·mobile·locale
9. maintainability
10. actual production security/privacy/operations when Gate H is actually in scope

## 16. 병합 전 exact-head 확인

모든 product/docs PR은 병합 직전 다음을 다시 확인한다.

- remote `main` current FULL SHA
- open PR / relevant issue state
- current PR exact head SHA
- base and behind state
- exact changed filenames / diff
- mergeability
- comments / review submissions
- unresolved review threads
- exact-head CI
- unexpected artifacts·secrets·PII

head가 변경되면 이전 검증을 재사용하지 않는다.

## 17. Merge rule

- merge method: **squash merge only**
- merge request는 exact current PR head를 `expected_head_sha` 또는 equivalent lease로 지정한다.
- head가 바뀌면 merge하지 말고 재검증한다.
- direct push to `main` 금지
- rebase / amend / force-push는 owner explicit approval 없이는 금지

## 18. 배포 / actual-site integration

merge는 deploy가 아니다.

Production deployment 또는 actual-site integration이 실제 scope라면 다음을 별도로 기록한다.

- environment
- deployment ID
- deployed SHA
- operator/owner
- secrets ownership
- smoke results
- operational boundaries
- rollback

Clone MVP 생성·시연은 actual-site integration 완료와 동일하지 않다.

## 19. Issue closeout

완료 comment/body update에 다음을 남긴다.

- PR·merge SHA
- tests/evidence
- clone/reference state
- deployment state if applicable
- acceptance criteria
- known limitations
- follow-up issues

Routine onboarding은 모든 exception을 issue화하지 않고, 재사용 가능한 공통 gap만 별도 issue로 승격한다.

자세한 기준:

- `docs/CURRENT_STATUS.md`
- `docs/product/clone-first-general-site-platform-strategy.md`
- `docs/implementation/RELEASE_GATES.md`
- `docs/operations/REPOSITORY_GOVERNANCE.md`
