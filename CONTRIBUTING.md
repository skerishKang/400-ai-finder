# Contributing to 400 AI Finder

이 저장소는 북구 golden clone, 공식 fixture, 시민 UI, Cloudflare AI API, crawler·index, 다국어와 Page Agent 비교를 함께 관리한다. 작은 변경도 route·source·안전·배포 계약에 영향을 줄 수 있으므로 아래 절차를 따른다.

## 1. Issue first

코드·설정·fixture·배포·구조변경 전 관련 issue를 만든다.

Issue에는 최소 다음을 포함한다.

- 문제와 사용자 영향
- product track
- include·exclude scope
- 안전·개인정보·network 영향
- acceptance criteria
- test·evidence 계획
- migration·rollback

문서 오탈자처럼 독립적인 초소형 변경은 예외가 될 수 있지만 PR 설명에 이유를 남긴다.

## 2. 브랜치와 worktree

`main`에서 전용 branch를 만든다.

권장:

```text
feat/<issue>-<scope>
fix/<issue>-<scope>
security/<issue>-<scope>
refactor/<issue>-<scope>
test/<issue>-<scope>
docs/<scope>
```

동시 작업은 별도 worktree를 사용한다. 다른 active branch의 파일을 섞지 않는다.

## 3. Product track 표시

PR에서 하나 이상 선택한다.

- 북구 golden clone
- 근거 기반 AI 시민안내
- 공식정보 freshness
- Python crawler·operator runtime
- Cloudflare citizen runtime
- Page Agent comparison
- multi-site platform
- authorized first-party integration
- repository·documentation governance

트랙별 경계는 `docs/product/PRODUCT_TRACKS_AND_BOUNDARIES.md`를 따른다.

## 4. Release gate 표시

PR이 목표로 하는 Gate를 명시한다.

- Gate A: frozen controlled demo
- Gate B: protected public pilot
- Gate C: evidence-safe AI pilot
- Gate D: unified platform foundation
- Gate E: modular runtime
- Gate F: official freshness staging
- Gate G: multi-site supervised pilot
- Gate H: authorized operational integration

Gate 통과를 주장하지 않는 PR은 `No promotion`으로 표시한다.

## 5. Data·secret·개인정보

커밋 금지:

- API key·token·credential
- `.env`
- raw citizen transcript
- 주민번호·전화·이메일·상세주소 등 PII
- 고객·기관 비공개자료
- production logs
- 내부 URL·account ID
- unreviewed screenshots with private data

테스트는 합성·익명화 fixture를 사용한다.

공식 공개 fixture도 source URL, capture/verified time, checksum과 usage 목적을 기록한다.

## 6. Network mode

PR에 하나를 명시한다.

- `offline/mock`
- `fixture-only`
- `controlled read-only live`
- `provider staging`
- `production integration`

routine CI는 외부 network·provider를 호출하지 않는다.

live test가 필요하면 target·method·limit·credentials owner·output sanitization·cleanup·approval을 기록한다.

## 7. 북구 golden 보호

다음은 frozen contract다.

- closed route IDs
- closed action target IDs
- public window API
- DOM IDs·data state
- canonical fixture identity
- no-submit boundary
- golden comparison evidence

변경 전 dedicated migration issue와 dual compatibility 계획이 필요하다.

fixture structure가 valid하다는 이유만으로 resident-default로 승격하지 않는다. visual side-by-side와 project-owner approval이 필요하다.

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
- fallback·retry budget
- secret·raw error sanitization
- kill switch·rollback

model output의 action·URL·JSON을 신뢰하지 않고 closed schema·allowlist로 검증한다.

## 9. Site·crawler 변경

- canonical site ID·legacy alias
- domain allowlist
- robots·crawl budget
- include·deny·protected patterns
- redirect·final URL policy
- attachment type
- source provenance
- duplicate·stale handling
- live opt-in

새 기관은 bespoke renderer보다 SiteSpec·data·theme·parser profile을 우선한다.

## 10. UI 변경

필요 evidence:

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

북구 clone UI는 accepted reference와 side-by-side를 제출한다.

## 11. Refactor

구조분리와 behavior change를 한 PR에 섞지 않는다.

- public façade 유지
- contract test 먼저
- 좁은 extraction
- no circular dependency
- generated artifact 여부 명시
- behavior-equivalence evidence

## 12. Test

최소 실행:

```bash
python -m pytest -q tests/
npm ci --ignore-scripts
```

PR scope에 따라 repository workflow의 관련 browser·Function·build contract를 실행한다.

금지:

- assertion 약화
- skip·xfail로 회귀 숨김
- 일부 scenario 선택 누락
- model-only visual approval
- live test 결과를 routine offline CI 결과로 표현

## 13. PR 작성

필수:

- related issue
- summary
- include·exclude
- base/head SHA
- changed files
- track·gate
- network/provider mode
- data·PII·secret statement
- validation
- browser·visual evidence
- deployment impact
- rollback
- known limitations

## 14. Review 우선순위

1. actual submit·login·payment·PII 위험
2. secret·endpoint·SSRF·abuse·cost
3. official source·evidence correctness
4. golden route·DOM·state compatibility
5. data loss·migration·rollback
6. accessibility·mobile·locale
7. maintainability

## 15. 병합 전 exact-head 확인

- current PR head SHA
- base and behind state
- exact-head CI
- mergeability
- review submissions
- unresolved threads
- changed filenames
- secrets·PII·unexpected artifacts

head가 변경되면 재검증한다.

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

public URL 응답만으로 deployed SHA를 확정하지 않는다.

## 17. Issue closeout

완료 comment 또는 body update에 다음을 남긴다.

- PR·merge SHA
- tests·evidence
- deployment state
- acceptance criteria
- known limitations
- follow-up issues

자세한 기준:

- `docs/CURRENT_STATUS.md`
- `docs/implementation/ROADMAP_20260804.md`
- `docs/implementation/RELEASE_GATES.md`
- `docs/operations/REPOSITORY_GOVERNANCE.md`
