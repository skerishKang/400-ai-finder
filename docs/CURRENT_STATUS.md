# 400 AI Finder 현재 기준 문서

- 상태: `canonical`
- 기준일: 2026-08-21
- 기준 main: `dbc785e0dd16e4d2a73c7c0245747cfbb9459271`
- 현재 제품축: Buk-gu Golden Master resident product → Seo-gu state-by-state parity recovery
- 운영 교리 authority: #1366 / `docs/operations/multi-site-onboarding-golden-master.md`
- active product recovery: #1364 → #1365 / PR #1367
- stacked parity CI: #1368 / PR #1372
- paused onboarding: #1363 HOLD; third site blocked pending Seo-gu Golden parity

이 문서는 저장소의 **현재 제품상태, 안전경계, 개발순서와 운영기준을 찾기 위한 최상위 current-state 인덱스**다.

GitHub remote가 실행상태의 Source of Truth다. 이 문서에 기록된 SHA/PR 상태는 작성 시점의 snapshot이며, mutation/merge/readiness 판단 직전에는 반드시 fresh remote를 다시 확인한다.

## 1. 현재 문서 authority

문서 간 해석이 충돌할 때 다음 순서를 따른다.

1. product owner's latest explicit decision
2. `docs/operations/multi-site-onboarding-golden-master.md` / #1366 — multi-site resident journey doctrine
3. `docs/CURRENT_STATUS.md` — current state / execution index
4. `docs/operations/PROJECT_OWNER_AUTHORITY_AND_MVP_BOUNDARY.md` — Phase-A owner authority / actual-site boundary
5. `docs/product/clone-first-general-site-platform-strategy.md` — ordinary clone-first lifecycle
6. `docs/product/PRODUCT_TRACKS_AND_BOUNDARIES.md`
7. `docs/product/exact-official-site-clone-invariant.md`
8. `docs/product/clone-visual-fidelity-and-promotion-policy.md`
9. `docs/implementation/RELEASE_GATES.md`
10. `docs/operations/REPOSITORY_GOVERNANCE.md` / `CONTRIBUTING.md`
11. narrower security/network/runtime/provenance documents for their specific technical scope

Historical issues, audit records, old stage documents and superseded playbooks do not override the current Golden Master doctrine.

`docs/product/municipality-ai-finder-onboarding-playbook.md` remains a useful historical/platform onboarding reference, but its older resident-journey generalization is superseded wherever it conflicts with the Golden Master doctrine.

## 2. Current product invariant

Buk-gu is the authoritative **Golden Master resident product**.

The required architecture is:

```text
                 ┌─ Buk-gu institution adapter / data / evidence
Golden UX Engine ┤
                 ├─ Seo-gu institution adapter / data / evidence
                 └─ future institution adapter / data / evidence
```

A new institution may change:

- branding/media;
- official route/menu structure;
- department/contact/facts;
- captured repository evidence;
- provenance markers;
- verified safe-stop/external-channel facts;
- thin surface adapter details.

It may not silently change or remove the canonical resident state graph.

For relevant scenarios, parity means the same materially observable sequence, including answer, explicit confirmation, YES/NO decision, transition/navigation, result/provenance, and the scenario-specific choice/write/review/pre-submit STOP states that exist in the Buk-gu Golden flow.

`grounded=true`, green CI, a good final screen, or a more realistic external handoff do not independently prove parity.

Canonical doctrine: [`operations/multi-site-onboarding-golden-master.md`](operations/multi-site-onboarding-golden-master.md).

## 3. Current product stage

400-ai-finder remains in the **pre-integration faithful-clone MVP** stage.

```text
real target site
→ separately scoped read-only reference capture where needed
→ point-in-time reference baseline
→ repository-controlled faithful clone
→ reference-vs-clone QA
→ resident AI/search/navigation on the clone
```

The actual production institution site is not the current runtime.

Actual login, PII processing, identity verification, payment, upload, submission/write and receipt semantics remain outside the current product boundary unless a later first-party integration stage is explicitly authorized.

## 4. Current product state

### Buk-gu

- protected/frozen Golden resident baseline: **authoritative**;
- canonical click-by-click visual/interaction authority: #1348;
- behavior must not drift merely to make a second-site implementation easier;
- exact/golden compatibility and no-submit boundaries remain protected.

### Seo-gu

The source/capture/clone/evidence work remains materially reusable, but resident orchestration parity is under active remediation.

Current corrected acceptance matrix:

| Unit | Current disposition | Reason |
|---|---|---|
| S0 entry | PASS | canonical composition/control hierarchy already accepted |
| S1 housing | ACTIVE RECOVERY | shared Golden engine required |
| S2 illegal parking | ACTIVE RECOVERY | external-channel fact must not replace canonical flow |
| S3 streetlight | PENDING AFTER #1367 | complaint/write/review Golden flow required |
| S4 litter | PENDING AFTER #1367 | complaint choice/write/review Golden flow required |
| S5 passport | ACTIVE RECOVERY | Golden choreography + current mobile chip-rail blocker |
| S6 unmanned kiosk | ACTIVE RECOVERY | accepted evidence/routes; Golden choreography recovery required |
| S7 mayor | HOLD | #1363 remains paused until Golden parity recovery |
| bulky waste / mattress | PENDING | derive from Buk-gu high-risk Golden STOP shape first |

### Third site / cross-domain

```text
THIRD_SITE = BLOCKED_PENDING_SEOGU_GOLDEN_PARITY
```

Do not resume third-site onboarding merely because source/clone platform pieces exist or a docs issue is completed.

## 5. Current GitHub recovery state

At this document update snapshot:

```text
CURRENT_MAIN = dbc785e0dd16e4d2a73c7c0245747cfbb9459271

PR #1367
  state = OPEN / DRAFT
  branch = refactor/1365-bukgu-golden-informational-parity
  head = 46d2e19f14fe2f2866772ceca95c52d40dd935ba
  purpose = shared Golden informational choreography recovery
  gate = architecture correction still required

PR #1372
  state = OPEN / DRAFT
  base = PR #1367 branch
  branch = ci/1368-golden-master-state-graph-gate
  head = 743b6be661bb5ecc4e6adf56069745f77ecaf14a
  purpose = mandatory Golden state-graph CI gate
  implementation = accepted pending parent reconciliation
```

Do not treat these SHAs as permanent authority. Re-query GitHub before any new decision or mutation.

## 6. Current critical path

The active order is:

```text
#1365 / PR #1367
→ retire Seo-gu resident behavior fork
→ one shared Golden resident engine for S1/S2/S5/S6
→ resolve focused Seo-gu mobile S5 chip-rail failure

#1368 / PR #1372
→ reconcile onto accepted #1367 parent
→ obtain authoritative exact-head Actions
→ make Golden state-graph parity mandatory

#1369
→ repository documentation authority aligned with #1366

#1370
→ after #1368 is established, align repository settings/protection/merge policy

then
→ S3/S4 complaint-writing Golden recovery
→ S7 mayor Golden recovery
→ bulky-waste/mattress Golden recovery
→ full state-by-state desktop/mobile paired visual acceptance
→ Seo-gu parity closure
→ only then third-site / cross-domain onboarding
```

#1363 stays HOLD throughout the current shared-engine/CI recovery.

## 7. Mandatory multi-site acceptance rule

For relevant onboarding PRs, require at minimum:

```text
GOLDEN_SCENARIO_ID =
GOLDEN_STATE_GRAPH =
NEW_SITE_STATE_GRAPH =
STATE_GRAPH_EQUAL = YES
BUKGU_BEHAVIOR_DRIFT = NONE
NEW_SITE_BEHAVIOR_FORK = NO
CANONICAL_STATES_SKIPPED = 0
EXTERNAL_CHANNEL_REPLACES_CANONICAL_FLOW = NO
STATE_BY_STATE_BROWSER_TEST = PASS
PAIRED_DIRECT_PNG_REVIEW = PASS / N/A
```

A final route/result alone is insufficient. A missing materially observable Golden state is a FAIL unless an explicit product-owner decision marks it non-applicable.

## 8. Source/evidence work that remains valid

Current recovery is primarily about resident orchestration and acceptance governance, not discarding good source work.

Preserve unless separately disproven:

- Seo-gu official captures/provenance;
- source-backed clone assets/content;
- housing/passport/kiosk local routes;
- bounded illegal-parking evidence;
- generic list/detail renderers;
- responsive/mobile corrections;
- clone DOM READ/grounding;
- source provenance UI;
- offline/security/network guards.

`DIRECT_REUSE` describes source/evidence reuse only. It is not authority to skip Golden resident states.

## 9. Security and network boundary

Routine CI remains deterministic/offline with external provider and official-site request count = 0 unless a task is explicitly authorized as a controlled live validation.

No current multi-site parity task authorizes:

- Firecrawl;
- general-model/provider live calls;
- actual official-site control;
- login/identity verification;
- citizen PII;
- payment;
- submission/write;
- Production mutation.

## 10. Repository governance state

Documented process remains:

```text
branch
→ Draft PR
→ exact-head validation
→ review/comments/threads recheck
→ squash merge with exact expected head
```

Current repository technical enforcement is weaker than this documented process. #1370 tracks alignment of branch protection, required checks and merge methods.

Do not configure final required status contexts until #1368 Golden parity CI is established and the exact check context is known.

## 11. Current issue index

### Critical path

- #1232 — multi-site onboarding parent
- #1348 — Buk-gu canonical visual/interaction baseline
- #1364 — Seo-gu Golden parity recovery parent
- #1365 / PR #1367 — shared informational choreography
- #1366 — operating doctrine authority
- #1368 / PR #1372 — mandatory Golden state-graph CI
- #1369 — documentation authority reconciliation
- #1370 — repository-settings enforcement after #1368
- #1363 — S7 HOLD

### Lower-priority operations

- #1371 — remote branch hygiene; read-only inventory first, unknown = HOLD
- #1290 — Google Drive working-mirror resync; GitHub remains authoritative

### Deferred owner/public-release governance

- #1234 — Production/public-release license/provenance owner decision; not a general blocker to the current controlled faithful-clone MVP.

## 12. Historical execution order superseded

Older current-status text identified #1303/#1312 and related G3 slices as the active execution order. Those items remain historical evidence of the clone-building phase, but they are **not the present critical path**.

The current authoritative execution path is the Golden resident parity recovery described above.

No history is rewritten: prior issues, PRs and Git history remain evidence of how the product reached the current state.
