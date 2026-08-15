# 400 AI Finder 현재 기준 문서

- 상태: `canonical`
- 기준일: 2026-08-16
- 기준 main: `75739ab2b89f3181abfbc88475205909d16fe127`
- lifecycle/governance 정렬: #1301 완료
- active onboarding validation: #1232 -> #1303 -> #1312

이 문서는 저장소의 **현재 제품상태, 제품단계, 안전경계, 개발순서와 운영기준을 찾기 위한 최상위 인덱스**다.

저장소에는 장기간 축적된 단계별 기록과 실험문서가 많다. 문서의 존재만으로 현재 구현·승인·운영 상태를 추정하지 않는다. 현재 상태는 이 문서와 아래 canonical 문서의 우선순위를 따른다.

## 문서 우선순위

1. `docs/CURRENT_STATUS.md` — current state/index
2. `docs/product/clone-first-general-site-platform-strategy.md` — ordinary pre-integration product lifecycle
3. `docs/product/PRODUCT_TRACKS_AND_BOUNDARIES.md` — track separation
4. `docs/product/exact-official-site-clone-invariant.md` — `exact` claim invariant
5. `docs/product/clone-visual-fidelity-and-promotion-policy.md` — visual/promotion authority
6. `docs/implementation/RELEASE_GATES.md` — readiness gates
7. `docs/operations/REPOSITORY_GOVERNANCE.md` / `CONTRIBUTING.md` — change-control workflow
8. network/security/runtime/provenance docs — their narrower technical boundaries

Historical issues, stage docs, audit records and superseded plans do not override the current canonical lifecycle.

## 문서 상태 분류

| 상태 | 의미 |
|---|---|
| `canonical` | 현재 구현과 운영판단의 기준 |
| `active-plan` | 승인된 후속 작업계획. 구현완료를 의미하지 않음 |
| `golden` | 북구 frozen baseline과 회귀계약 |
| `operator` | 실행·검증·배포 운영절차 |
| `historical` | 당시 의사결정·증거. 현재 상태는 별도 확인 필요 |
| `planning-only` | 구현·live 실행·배포를 승인하지 않는 설계자료 |
| `superseded` | 새 문서·이슈가 대체. 역사기록으로만 보존 |

## 현재 제품단계 — 가장 중요한 구분

400-ai-finder는 현재 **faithful-clone MVP 단계**다.

### 현재 단계: pre-integration faithful-clone MVP

기관이 실제 production 사이트의 운영·통합 권한을 제공하기 전에는 다음 제품형태를 사용한다.

```text
실제 대상 사이트
  -> 필요 시 scoped read-only reference capture
  -> point-in-time reference baseline
  -> repository-controlled faithful clone candidate
  -> reference vs clone 비교
  -> clone MVP
  -> AI Finder / Browser가 clone에서 search / click / navigate / answer
```

일반적인 stakeholder/development MVP에서:

```text
left  = target site's faithful clone
right = AI conversation / answer / search / navigation / bounded Browser Use
```

실제 production 사이트는 현재 runtime이 아니다. 실제 사이트는 clone을 만들기 위한 reference source이며, 이미 승인된 clone은 source-site 변경에 따라 실시간으로 자동 변형되지 않는다.

필요한 경우 재캡처하여 **새 reference / 새 clone candidate version**을 만든 뒤 다시 검토한다.

### 나중 단계: authorized first-party actual-site integration

기관의 명시적 도입·운영·통합 승인이 생긴 뒤에만 실제 기관사이트 단계가 열린다.

그때 실제 환경을 기준으로 다음을 검토한다.

- credentials / deployment ownership
- information security
- privacy / PII
- authentication
- real submissions / payments / write actions
- internal-system integration
- incident / support ownership
- staging / rollback

이러한 **미래 actual-site production 조건은 현재 faithful-clone MVP를 만들고 검증하기 위한 선행 blocker가 아니다.**

Clone MVP 완료는 actual-site control을 의미하지 않고, actual-site integration 역시 clone MVP를 만들기 위한 선행조건이 아니다.

Canonical lifecycle: [`product/clone-first-general-site-platform-strategy.md`](product/clone-first-general-site-platform-strategy.md)

## 현재 제품 상태

- **Buk-gu Frozen Demo:** 완료. 북구는 첫 번째 protected municipality golden reference다.
- **Generic contract foundation:** #1287 완료. Versioned Generic SiteSpec vNext / archetype / capability / onboarding-report contract foundation과 Buk-gu compatibility/projection 기반이 존재한다.
- **Generic Site Model / structural preview evidence:** 구현됨. #1298~#1300의 Seo-gu offline structural work는 generic platform evidence로 유효하다.
- **Seo-gu named-site proof:** #1303 아래에서 G1 point-in-time reference baseline과 G2-A semantic model, G2-B faithful-clone candidate까지 완료·병합되었다. #1310 / PR #1311의 homepage desktop/mobile/GNB fidelity slice는 accepted 상태다. 현재 #1312 / Draft PR #1313에서 notice/gosi/civil-form list+detail six-state fidelity를 교정 중이며, fresh evidence는 생성됐지만 현재 candidate는 visual/source-parity review에서 아직 accepted가 아니다. organization/staff는 그 다음 bounded slice다.
- **General-site / multi-site AI Browser:** #1232가 active 상태다. Seo-gu G3 representative-surface acceptance가 완료되기 전에는 AI-on-clone 후속이나 materially different third-site proof로 넘어가지 않는다.
- **Live-public AI:** 별도 public operating approval이 있는 것으로 자동 간주하지 않는다.
- **Actual-site first-party integration:** 기관의 실제 운영·통합 승인이 있기 전에는 시작하지 않는다.
- **Rights/license #1234:** public/open-source redistribution 또는 별도 release 판단을 위한 owner/rights 트랙으로 유지한다. 현재 controlled faithful-clone MVP의 기능·fidelity·stakeholder evaluation 자체를 자동 차단하는 일반 개발 blocker로 사용하지 않는다.

## Platform structural proof와 named-site onboarding 분리

### Platform/core structural development

Synthetic/offline fixture로 다음을 검증할 수 있다.

- SiteSpec
- archetype/capability
- generic Site Model
- structural preview/renderer
- knowledge/action graph contracts
- QA/report schema
- exception handling

이 작업은 실제 사이트 capture 없이도 가능하다.

그러나 synthetic/offline structural proof는 named real site의 clone 완료 증거가 아니다.

### Named real-site onboarding

실제 이름을 가진 기관을 onboard한다고 주장하려면 먼저 scoped point-in-time reference baseline을 확보한 뒤 clone candidate를 비교한다.

```text
generated structural preview
!= reference_baseline_ready
!= clone_candidate
!= clone_mvp_ready
!= exact
!= resident_default_approved
!= actual_site_integrated
```

## 현재 #1232 순서

1. Buk-gu — protected golden reference
2. Seo-gu G1 — scoped point-in-time actual-site reference baseline 완료
3. Seo-gu G2-A — semantic model 완료
4. Seo-gu G2-B — faithful-clone candidate 병합 완료
5. Seo-gu G3 homepage — #1310 / PR #1311 accepted
6. Seo-gu G3 board/list/detail — #1312 / Draft PR #1313 active; current evidence는 아직 visual acceptance 전
7. organization chart / staff directory — board slice acceptance 후 다음 bounded correction
8. Seo-gu G3의 required structural/content/asset/interaction/visual gates를 모두 충족하고 owner visual review와 별도 `clone_mvp_ready` gate가 명시적으로 승인된 뒤 clone 위 AI search/navigation/Browser Use 검증
9. 그 후 materially different third-site / cross-domain proof

제3 사이트를 먼저 진행하거나 CI/Preview 성공만으로 Seo-gu G3 visual acceptance 또는 clone MVP 완료를 표현하지 않는다.

## 현재 기준 문서

### 제품 lifecycle / track / release

- [`product/clone-first-general-site-platform-strategy.md`](product/clone-first-general-site-platform-strategy.md) — `canonical`, ordinary pre-integration lifecycle owner
- [`product/PRODUCT_TRACKS_AND_BOUNDARIES.md`](product/PRODUCT_TRACKS_AND_BOUNDARIES.md) — `canonical`
- [`implementation/RELEASE_GATES.md`](implementation/RELEASE_GATES.md) — `canonical`
- [`product/exact-official-site-clone-invariant.md`](product/exact-official-site-clone-invariant.md) — `canonical` for explicit `exact` claim
- [`product/clone-visual-fidelity-and-promotion-policy.md`](product/clone-visual-fidelity-and-promotion-policy.md) — `canonical`

### 아키텍처

- [`architecture/UNIFIED_RUNTIME_AND_SITESPEC.md`](architecture/UNIFIED_RUNTIME_AND_SITESPEC.md) — current platform architecture/status
- [`architecture/clone-first-platform-adr.md`](architecture/clone-first-platform-adr.md) — `historical` architecture decision / compatibility reference
- [`bukgu-golden-compatibility-manifest.md`](bukgu-golden-compatibility-manifest.md) — `golden`

### 보안·개인정보·운영

- [`operations/PUBLIC_AI_API_SECURITY_AND_PRIVACY.md`](operations/PUBLIC_AI_API_SECURITY_AND_PRIVACY.md) — `canonical` for applicable public API operation
- [`operations/REPOSITORY_GOVERNANCE.md`](operations/REPOSITORY_GOVERNANCE.md) — `canonical`
- [`../SECURITY.md`](../SECURITY.md) — vulnerability/secret handling policy
- [`provider-fetch-network-boundary.md`](provider-fetch-network-boundary.md) — external provider/network technical boundary
- [`live-transition-decision-record.md`](live-transition-decision-record.md) — historical/operational live transition record
- [`operator-quickstart.md`](operator-quickstart.md) — operator execution guide

### 라이선스와 자산

- [`legal/LICENSING_AND_PROVENANCE_DECISION.md`](legal/LICENSING_AND_PROVENANCE_DECISION.md) — owner/public-release/provenance decision track

### 개발기여

- [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
- [`../.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md)

### 역사자료

- [`audit/PROJECT_AUDIT_20260804.md`](audit/PROJECT_AUDIT_20260804.md) — historical audit
- [`implementation/ROADMAP_20260804.md`](implementation/ROADMAP_20260804.md) — historical plan; current execution order로 사용하지 않음

## 북구 golden 기준

북구 golden baseline은 범용 플랫폼 refactor보다 우선 보호한다.

- Golden compatibility manifest: [`bukgu-golden-compatibility-manifest.md`](bukgu-golden-compatibility-manifest.md)
- Exact clone invariant: [`product/exact-official-site-clone-invariant.md`](product/exact-official-site-clone-invariant.md)
- Visual promotion policy: [`product/clone-visual-fidelity-and-promotion-policy.md`](product/clone-visual-fidelity-and-promotion-policy.md)
- Fixture manifest: [`../tests/fixtures/official_site_clone_manifest.json`](../tests/fixtures/official_site_clone_manifest.json)

다음 상태는 별개다.

1. reference/capture provenance
2. clone candidate
3. structure/content parity
4. asset mapping
5. interaction parity
6. visual review
7. clone MVP ready
8. exact/resident-default promotion when explicitly requested

앞 단계가 완료됐다는 이유로 다음 단계가 자동 승인되지 않는다.

## Clone MVP와 `exact` 분리

모든 MVP가 기관의 모든 route를 처음부터 exact하게 복제할 필요는 없다. 대신 declared MVP scope를 명시한다.

범위 밖은 fabricated하지 않고 `capture_required` / exception으로 남긴다. 범위 안에서는 원본 reference를 임의 재설계하지 않는다.

`clone_mvp_ready`는 scoped faithful reproduction을 뜻하며 `exact` 또는 resident-default 승인과 동일하지 않다.

`exact`를 주장하는 surface는 기존 exact-clone invariant와 visual/promotion policy를 추가로 따른다.

## Network / capture 기본 원칙

- routine CI는 external provider / official-site network 0을 유지한다.
- 실제 사이트 reference capture는 named-site onboarding에서 필요한 별도 실행행위이며 target/scope/method를 명시한다.
- URL을 입력값으로 받는 generic runtime capability와, 특정 프로젝트에서 그 URL을 실제로 contact하는 것은 같은 개념이 아니다.
- actual-site production control, login, real submission/payment, PII processing은 미래 first-party integration 단계다.

## 현재 작업 이슈

Active:

- [#1232 multi-site onboarding validation](https://github.com/skerishKang/400-ai-finder/issues/1232)
- [#1303 Seo-gu controlled reference baseline + faithful clone proof](https://github.com/skerishKang/400-ai-finder/issues/1303)
- [#1312 Seo-gu G3 board list/detail fidelity](https://github.com/skerishKang/400-ai-finder/issues/1312)

Separate follow-up/platform hardening:

- #1294 redirect/sitemap acquisition scope — OPEN / active hardening
- #1295 SSRF-safe arbitrary URL acquisition — OPEN P0 follow-up after #1294
- #1291 generic Page Agent target semantics — OPEN P1
- #1293 location discovery taxonomy — OPEN P2

Nonblocking maintenance / operations:

- #1289 comparison-evidence timeout flake — OPEN, observe only; no CI weakening or timeout change justified absent recurrence
- #1290 Google Drive working-mirror resync — OPEN operational/local-access maintenance; GitHub remote remains authoritative

Owner/public-release decision:

- [#1234 code/official capture/third-party asset license & provenance](https://github.com/skerishKang/400-ai-finder/issues/1234)

Completed / historical:

- #1301 clone MVP lifecycle / canonical docs alignment — completed
- #1310 Seo-gu G3 homepage fidelity correction — completed/accepted
- #1292 parsed-host site ownership hardening — completed; prerequisite landed before #1294
- #1283 post-Buk-gu governance alignment — completed
- #1287 Generic SiteSpec vNext contract foundation — completed
- #1235 Buk-gu Frozen Demo closeout — completed
- #1181 clone-first multi-site strategy/epic — CLOSED / not_planned; historical strategy/planning provenance remains useful, but it is no longer the active execution parent
- #1080 Buk-gu official fixture program — historical/deferred
- #1150 official-info freshness retrieval — historical/deferred
- #862 actual-site navigator/integration — future authorized actual-site track
- #873 full Buk-gu rebuild/integration planning — historical planning

## 저장소 변경 규칙 요약

- `main` 직접 push 금지. docs 포함 dedicated branch -> Draft PR을 사용한다.
- 새 작업 직전 remote main FULL SHA, open PR, relevant issues를 다시 확인한다.
- merge 직전 exact current head, diff/changed files, comments/reviews/threads, exact-head CI를 다시 확인한다.
- head가 바뀌면 이전 merge-readiness 증거를 재사용하지 않는다.
- rebase / amend / force-push는 project owner가 명시적으로 승인하지 않는 한 사용하지 않는다.
- merge는 exact current head를 lease로 지정한 squash merge를 사용한다.
- assertion / skip / xfail / coverage threshold를 낮춰 CI를 통과시키지 않는다.

## 문서 갱신 규칙

- 문서에 가능한 경우 exact SHA, 검증일, 환경과 상태를 기록한다.
- `planned`, `generated`, `implemented`, `tested`, `clone_mvp_ready`, `exact`, `deployed`, `approved`, `actual_site_integrated`를 같은 말로 사용하지 않는다.
- public issue·PR·문서에는 고객·기관의 비공개 정보, 개인식별정보, API 키, 내부 URL을 기록하지 않는다.
- actual-site production security/privacy/operations requirements는 실제 first-party 단계가 열릴 때 해당 환경 기준으로 검토한다.
- 기존 문서가 새 기준과 충돌하면 삭제보다 `superseded`/`historical` 표시와 canonical replacement 링크를 우선한다.