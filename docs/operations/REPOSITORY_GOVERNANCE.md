# 저장소·브랜치·릴리스 거버넌스

- 상태: `canonical`
- 기준일: 2026-08-04
- 관련 이슈: #1233, #1234

## 1. 목적

`400-ai-finder`는 장기간의 stage·experiment·audit·design·test 작업을 포함한다. 현재와 역사기록을 구분하고, 북구 golden·배포·rollback 자산을 보호하며, 새 개발이 좁은 이슈·브랜치·PR·증거를 따르도록 한다.

## 2. 기본 개발흐름

```text
Issue
→ dedicated branch/worktree
→ narrow commits
→ Draft PR when incomplete
→ exact-head validation
→ review/thread resolution
→ merge
→ deployed SHA verification when applicable
→ issue closeout evidence
```

`main` 직접 push는 긴급한 문서·운영복구를 제외하고 사용하지 않는다. 기능·보안·배포변경은 PR을 사용한다.

## 3. 브랜치 이름

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
refactor/1229-provider-runner
platform/1225-sitespec-schema
docs/audit-roadmap-20260804
```

## 4. 브랜치 정리

감사시점 원격 브랜치는 300개 이상이다. 즉시 일괄삭제하지 않는다.

### 4.1 분류

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

### 4.2 삭제 전 증거

- branch head SHA
- merge PR 또는 containing main commit
- 관련 issue
- deployed·artifact·worktree 사용 여부
- replacement branch
- 삭제 reviewer

### 4.3 삭제 절차

1. read-only inventory report
2. protected exclusions
3. 후보 review
4. 작은 batch 삭제
5. 링크·automation·deployment 영향 확인
6. report update

### 4.4 예방

repository setting에서 merged head branch 자동삭제를 검토한다. 장기 branch는 명시적 이유와 owner를 기록한다.

## 5. PR 범위

한 PR은 한 가지 주된 변경목적을 가진다.

분리해야 하는 조합:

- refactor + behavior change
- provider change + UI redesign
- fixture capture + resident-default promotion
- docs + production deployment
- security control + unrelated feature
- branch cleanup + code change

## 6. PR 필수정보

- related issue
- product track
- release gate
- base/head SHA
- changed files
- include/exclude scope
- network/provider mode
- data classification
- PII·secret statement
- tests
- browser·visual evidence
- migration
- deployment impact
- rollback

## 7. Exact-head 검증

병합직전 다음을 다시 확인한다.

- PR head SHA
- base SHA·behind state
- mergeability
- CI for exact head
- review state
- unresolved threads
- changed filenames
- accidental artifacts·secrets·PII

head가 바뀌면 이전 검증을 재사용하지 않는다.

## 8. Golden·visual 변경

북구 resident-facing 변경은 다음을 별도로 증명한다.

- fixture provenance
- structure/content parity
- asset mapping
- interaction state
- desktop/mobile screenshots
- accepted reference side-by-side
- material difference list
- project-owner approval

screenshot 생성만으로 visual approval로 간주하지 않는다.

## 9. Live·network 변경

PR에 다음을 명시한다.

- no-network
- mock/stub
- controlled read-only live
- provider staging
- production integration

live action은 target, method, limit, credentials owner, captured outputs, cleanup와 incident boundary를 기록한다.

## 10. Release

### 10.1 태그

release tag는 최소 다음을 포함한다.

- product surface
- version 또는 date
- exact commit
- release gate
- known limitations
- rollback artifact

예:

```text
bukgu-golden-2026-07
public-pilot-v0.2.0
```

### 10.2 Changelog

분류:

- Added
- Changed
- Fixed
- Security
- Data/Fixture
- Deployment
- Deprecated
- Known limitations

### 10.3 배포

Git merge와 Cloudflare deployment는 별도 상태다.

기록:

- merged SHA
- deployment ID
- deployed SHA
- environment
- time
- operator
- smoke result
- rollback

public URL만 보고 deployed SHA를 추정하지 않는다.

## 11. 문서 거버넌스

문서 header에 가능한 경우 다음을 포함한다.

- status
- date
- exact SHA
- owner 또는 related issue
- live authorization 여부

상태:

- canonical
- active-plan
- golden
- operator
- planning-only
- historical
- superseded

오래된 문서를 삭제하기보다 replacement 링크와 상태를 표시한다.

## 12. Artifact

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
- customer/private files
- unredacted PII
- local runtime state
- temporary browser trace with sensitive data
- provider raw response containing private content

artifact는 owner, source, generated time, SHA와 retention을 기록한다.

## 13. Issue 종료

issue는 code merge만으로 자동 완료되지 않는다.

종료 evidence:

- implementation PR·merge SHA
- tests
- runtime/browser evidence
- docs
- deployment state if applicable
- known limitations
- follow-up issues
- acceptance criteria check

planning-only issue는 decision·document·next owner가 확정되면 닫을 수 있다.

## 14. 자동화·에이전트 작업

- active branch·issue·base SHA를 먼저 확인한다.
- current conversation·issue scope를 넘어선 파일을 수정하지 않는다.
- accidental file·no-op commit을 숨기지 않는다.
- destructive actions는 exact target과 rollback evidence를 요구한다.
- model-only visual approval을 인정하지 않는다.
- live execution·merge·deployment authorization을 서로 구분한다.

## 15. 완료조건

- branch inventory report와 안전한 cleanup process
- merged head auto-delete 결정
- required checks와 branch protection
- release tag·changelog·deployment record
- canonical doc index
- PR·issue templates
- contribution·security policy
- license·asset provenance decision
