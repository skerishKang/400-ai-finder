# 저장소·브랜치·릴리스 거버넌스

- 상태: `canonical`
- 기준일: 2026-08-12
- 현재 lifecycle/governance 정렬: #1301
- 관련 historical issue: #1233, #1234

## 1. 목적

`400-ai-finder`는 장기간의 stage·experiment·audit·design·test 작업을 포함한다. 현재와 역사기록을 구분하고, 북구 golden·배포·rollback 자산을 보호하며, 새 개발이 좁은 이슈·브랜치·PR·증거를 따르도록 한다.

제품 lifecycle 자체는 `docs/product/clone-first-general-site-platform-strategy.md`를 따른다.

Buk-gu golden 및 명시적 `exact` claim은 `docs/product/exact-official-site-clone-invariant.md`를 따른다.

## 2. 기본 개발흐름 — 예외 없는 PR-first

```text
remote current-state recheck
→ Issue / approved scope
→ dedicated branch/worktree
→ narrow commits
→ Draft PR
→ exact-head validation
→ review/thread resolution
→ squash merge with exact-head lease
→ deployed SHA verification when deployment is actually in scope
→ issue closeout evidence
```

**`main` 직접 push는 사용하지 않는다. 문서·운영복구도 동일하게 branch -> PR을 사용한다.**

긴급상황에서도 direct-main 예외를 문서에 내장하지 않는다. 정말 별도 긴급정책이 필요하면 project owner의 명시적 승인과 별도 기록을 남긴다.

## 3. 새 작업 전 remote current-state 확인

새 작업을 시작하기 직전에 최소 다음을 원격 GitHub에서 확인한다.

- authoritative `main` FULL SHA
- open PRs
- relevant open issues
- active/conflicting branches where applicable

이전 대화, 로컬 보고, Drive mirror 또는 오래된 `origin/main` 값을 authoritative current state로 사용하지 않는다.

GitHub remote state가 local/Drive mirror와 다르면 remote GitHub를 기준으로 먼저 정렬한다.

## 4. 브랜치 이름

권장 prefix:

- `feat/`
- `fix/`
- `security/`
- `refactor/`
- `test/`
- `docs/`
- `chore/`
- `audit/`
- `experiment/`

가능하면 issue number와 좁은 목적을 포함한다.

예:

```text
security/1224-public-api-controls
docs/1301-clone-mvp-lifecycle
feat/1232-seogu-faithful-clone
```

## 5. Rebase / amend / force-push

기본 금지:

- rebase
- commit amend that rewrites an already-pushed branch
- force push
- force-with-lease

project owner가 특정 상황에 대해 명시적으로 승인한 경우에만 예외적으로 수행한다.

Branch head를 정상적인 새 commit으로 전진시키는 것을 기본으로 한다.

## 6. 브랜치 정리

대규모 일괄삭제하지 않는다.

### 분류

| 분류 | 처리 |
|---|---|
| default/protected | 보존 |
| open PR | 보존 |
| active worktree | 보존 |
| golden/release/rollback | 보존 |
| merged | 삭제 후보 |
| superseded with evidence | 삭제 후보 |
| unmerged unknown | 보존·review |
| tmp/noop | 관계 확인 후 삭제 후보 |

삭제 전 branch head SHA, merge PR/main containment, issue, deployed/artifact/worktree use, replacement, reviewer를 기록한다.

## 7. PR 범위

한 PR은 한 가지 주된 변경목적을 가진다.

분리해야 하는 조합:

- refactor + behavior change
- provider change + UI redesign
- reference capture + unrelated shared-core refactor
- clone candidate + actual production-site integration
- docs + production deployment
- security control + unrelated feature
- branch cleanup + code change

## 8. Product-stage 분류

PR은 자신의 현재 상태를 정확히 명시한다.

```text
platform structural proof
reference baseline
faithful clone candidate
clone MVP ready
AI-on-clone proof
exact/golden/default promotion
actual-site integration
```

Structural preview를 named-site faithful clone으로 표현하거나, clone MVP를 actual-site control로 표현하지 않는다.

현재 ordinary pre-integration default는 **faithful clone MVP**이고, actual-site integration은 기관 승인 후 미래 단계다.

## 9. PR 필수정보

공통:

- related issue
- product track / release gate
- base/head SHA
- changed files
- include/exclude scope
- network/reference/provider mode
- data classification
- secret/private-data statement
- tests
- browser/visual evidence when applicable
- migration
- deployment impact
- rollback/isolation

Named-site onboarding 추가:

- declared clone scope
- source URLs
- reference snapshot identity / capture time
- clone candidate identity
- structural/content/asset/interaction/visual state
- AI-on-clone state
- automation/review/unsupported ratio
- exception queue

## 10. Exact-head 검증

병합 직전 원격 GitHub에서 다음을 다시 확인한다.

- current PR head FULL SHA
- current main/base SHA and behind state
- mergeability
- exact changed filenames and diff
- exact-head CI
- PR conversation comments
- review submissions
- unresolved review threads
- accidental artifacts·secrets·PII/private material

**PR head가 바뀌면 이전 readiness 증거는 무효다. 처음부터 다시 확인한다.**

로컬 작업자 보고를 authoritative evidence로 간주하지 않는다.

## 11. Merge rule

- merge method는 **squash only**다.
- merge 시 최신 exact PR head를 `expected_head_sha` 또는 connector/API equivalent lease로 지정한다.
- expected head와 current head가 다르면 merge하지 않는다.
- branch head 변경 후 CI/readiness를 재검증하지 않은 상태에서 merge하지 않는다.
- direct push to `main` 금지

## 12. Test / CI integrity

CI를 green으로 만들기 위한 다음 행위를 금지한다.

- assertion 약화
- skip / xfail 추가로 regression 숨김
- coverage threshold 하향
- scenario 제거 또는 선택적 미실행
- required check 제거
- `continue-on-error`로 실패 무시

Routine CI는 external provider/official-site live network 없이 재현 가능해야 한다.

## 13. Golden·clone·visual 변경

Buk-gu golden 또는 explicit exact/default promotion은 applicable exact/visual policy를 따른다.

Named-site clone MVP에서는 reference-first lifecycle을 따른다.

```text
declared scope
→ point-in-time source reference
→ clone candidate
→ structural/content/asset/interaction/visual comparison
→ clone MVP ready
→ AI-on-clone
```

Scope는 작게 선언할 수 있지만 scope 안의 source reference를 임의로 redesign하지 않는다.

Generic renderer/shared engine은 구현재사용 수단이지 generic-looking UI를 허용하는 근거가 아니다.

## 14. Current clone MVP와 future actual-site

현재 controlled/stakeholder product surface는 clone이다.

Actual institution production-site integration은 기관이 실제 운영·통합 권한을 부여한 후에만 별도 phase로 연다.

그때 실제 환경을 기준으로:

- deployment/hosting ownership
- credentials/secrets
- information security
- privacy/PII
- authentication
- real submission/payment/write actions
- internal-system integration
- monitoring/incident/support
- staging/rollback

을 검토한다.

**이 future production 항목을 current clone fidelity 작업의 임의 선행 blocker로 사용하지 않는다.**

Clone MVP 완료는 actual-site control을 의미하지 않는다.

## 15. Network / reference capture

PR/report에서 execution mode를 명시한다.

- no-network / offline
- fixture-only
- controlled read-only reference capture
- provider staging
- production integration

Named-site reference capture는 target/scope/method/route-state limits/output identity를 기록한다.

CLI/tool이 live network 기능을 가진다는 사실과 project-level capture scope는 구분한다.

Actual production-site control과 reference capture는 같은 작업이 아니다.

## 16. Release / deployment

Git merge와 deployment는 별도 상태다.

실제 deployment가 scope일 때만 다음을 기록한다.

- merged SHA
- deployment ID
- deployed SHA
- environment
- operator
- smoke result
- rollback

public URL만 보고 deployed SHA를 추정하지 않는다.

## 17. 문서 거버넌스

문서 header에 가능한 경우 다음을 포함한다.

- status
- date
- exact SHA or baseline where useful
- related issue

상태:

- canonical
- active-plan
- golden
- operator
- planning-only
- historical
- superseded

오래된 문서를 삭제하기보다 replacement 링크와 상태를 표시한다.

Current canonical precedence는 `docs/CURRENT_STATUS.md`를 따른다.

## 18. Artifact / confidentiality

### Git에 포함 가능

- deterministic fixture
- public-safe schema
- approved comparison evidence
- sanitized screenshot
- test manifest
- license notice

### 기본 제외

- API key
- `.env`
- raw citizen transcript
- customer/institution private files
- confidential stakeholder/business relationship detail
- unredacted PII
- local runtime state
- temporary browser trace with sensitive data
- provider raw response containing private content

## 19. Drive mirror / local working copy

Google Drive mirror 또는 local worktree는 authoritative GitHub remote와 drift할 수 있다.

- Drive `.git/HEAD`, local branch, local `origin/main`을 current remote보다 우선하지 않는다.
- stale mirror에 새 작업을 직접 섞지 않는다.
- 먼저 current GitHub main/PR/issue state를 확인한다.
- unknown/uncommitted local material은 destructive sync 대상으로 취급하지 않는다.

## 20. Issue 종료

issue는 code merge만으로 자동 완료되지 않는다.

종료 evidence:

- implementation/docs PR and squash merge SHA
- tests / browser / comparison evidence
- clone/reference state
- deployment state if applicable
- known limitations
- follow-up issues
- acceptance criteria check

Planning-only issue는 decision/document/next owner가 확정되면 닫을 수 있다.
