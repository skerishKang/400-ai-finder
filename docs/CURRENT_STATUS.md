# 400 AI Finder 현재 기준 문서

- 상태: `canonical`
- 기준일: 2026-08-22
- 기준 main: `219737199e8f1a5c09ba1648172b23742fd8f4c6` (squash merge of PR #1381)
- 현재 제품축: Buk-gu Golden Master authoritative · Seo-gu agent-side parity recovery 완료 (agent-verified)
- 운영 교리 authority: #1366 / `docs/operations/multi-site-onboarding-golden-master.md`
- **소유자 정식 수용: PENDING** — 에이전트 검증 수용만 존재. third-site 포함 다음 단계의 전제조건
- Golden parity CI gate: 상시 강제 (#1368 / #1370 완료, required checks 12개)
- third-site onboarding: BLOCKED_PENDING_OWNER_ACCEPTANCE (+ 스코프 질문 미정)

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
- canonical click-by-click visual/interaction baseline: #1348 (CLOSED 2026-08-22 — 목적 완료; baseline 자체는 저장소 제품 + Golden parity CI gate에 상주, 이슈 코멘트는 audit history);
- behavior must not drift merely to make a second-site implementation easier;
- exact/golden compatibility and no-submit boundaries remain protected.

### Seo-gu

Agent-side parity recovery is **complete** (PARITY CLOSURE record: #1380 close comment @ main `2197371`). All 8 primary chip scenarios follow the Buk-gu Golden state graph:

| Unit | Final disposition | Evidence |
|---|---|---|
| S0 entry | PASS | canonical composition/branding parity |
| S1 공동주택 부서 문의 | DIRECT_REUSE | Golden choreography via shared engine |
| S2 불법 주정차 신고 | guidance/handoff-stop | PR #1381 (S-final) — external anchor surface 제거, 안전신문고는 안내 텍스트로만 |
| S3 가로등 고장 (AI) | complaint write | PR #1375 |
| S4 쓰레기 무단투기 (AI) | complaint write | PR #1375 |
| S5 여권 발급 안내 | DIRECT_REUSE | PR #1358/#1359 |
| S6 무인민원발급기 안내 | DIRECT_REUSE | PR #1362 |
| S7 구청장에게 제안 | complaint write/receipt | PR #1377 |

```text
SOURCE_CAPTURE_NEEDED = 0
EXTERNAL_CHANNEL_LINK_SURFACE = 0
ENGINE = 단일 resident behavior engine + 기관 데이터 치환만
```

**Acceptance status caveat:** the above is agent-verified acceptance (CI + paired PNG review). It is NOT yet owner-witnessed formal acceptance. Owner acceptance is a separate mandatory gate before any further site onboarding.

### Third site / cross-domain

```text
THIRD_SITE = BLOCKED_PENDING_OWNER_ACCEPTANCE
```

Do not resume third-site onboarding because agent-side parity closed. Prerequisites, in order:

1. owner-witnessed click-through acceptance of the deployed Seo-gu surface (all 8 scenarios), formally recorded;
2. owner scope answers: which institution, does owner intent exist, who authorizes official-site boundary;
3. cheap-debt items below cleared.

## 5. Current GitHub recovery state

At this document update snapshot:

```text
CURRENT_MAIN = 219737199e8f1a5c09ba1648172b23742fd8f4c6
OPEN_PRS = 0
main CI = success (12 required checks + Cloudflare Pages)

OPEN_ISSUES:
  #1232  multi-site onboarding parent (third-site 검토 해금 조건 = 소유자 수용)
  #1378  P2 shared engine '북구청' 리터럴 파라미터화
  #1234  BLOCKED: license/provenance owner decision (Production 전환 시에만)
  #1290  BLOCKED: Google Drive mirror resync (로컬 접근 복귀 시)

RECENTLY CLOSED (2026-08-21~22):
  #1348  visual baseline authority — 목적 완료 close
  #1364 #1365 #1366 #1368 #1369 #1370 #1371 #1363
```

Do not treat these SHAs as permanent authority. Re-query GitHub before any new decision or mutation.

## 6. Current critical path

The active order is:

```text
1. OWNER ACCEPTANCE GATE (최우선)
   → 소유자를 배포된 Seo-gu 표면(https://cgbukku.pages.dev/static/seogu-citizen-action-demo) 앞에 세움
   → 8개 시나리오 정식 클릭 수용, 서명/기록 남김
   → green CI와 에이전트 PNG 리뷰는 state-graph 드리프트를 가릴 수 있음 (#1348 사례)

2. CHEAP DEBT (third-site 전 정리)
   → #1378 shared engine '북구청' 리터럴 파라미터화 (기관 추가 시 노출 배수)
   → seogu_mattrass_disposal journey_id 오타 수정 (참조 붕괴 전)
   → 로컬 디스크 의존 자산 정리 (아래 §10a)

3. THIRD-SITE SCOPE QUESTIONS (소유자 질문 — 엔지니어링 이전 단계)
   → 어떤 기관인가 / 소유자 의도 존재 여부 / 공식 사이트 경계 허가자

4. only then third-site / cross-domain onboarding
```

## 6a. Decision DNA map (새 CTO/워커 필독 3개)

역사는 이슈 코멘트에 산재해 있다. 결정의 근거는 다음 3곳만 읽으면 된다:

1. `docs/operations/multi-site-onboarding-golden-master.md` (#1366) — 규칙/교리
2. PR #1377 리뷰 코멘트 — 외부 채널 링크/handoff 표면 금지 결정의 이유 (2026-08-21 owner decision)
3. #1380 본문 — Golden 원형(state graph) 추출 방법

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

Technical enforcement (since 2026-08-21, #1370): main branch protection ON, squash-only, 12 required status contexts including the Golden parity gate.

**Known hole:** `enforce_admins = false` (enforcement_level = `non_admins`). Administrators can still push directly to main. This was the initial protection configuration; whether it is intentional (emergency exception path) or an oversight is a pending owner decision. If unintentional, close it; if intentional, record the rationale here.

### 10a. Local-disk-dependent assets (evidence-loss risk)

The following exist only on local disk and are not committed/pushed. Loss of local access destroys them:

```text
worktree wt-1360-glm2 (refactor/1365-bukgu-golden-informational-parity @ 46d2e19)
  - uncommitted modifications: citizen-action-demo.html,
    citizen-first-use-shell.js, seogu-citizen-action-demo.html,
    seogu-citizen-action-shell.js,
    tests/browser/verify_seogu_resident_surface_focused_e2e.mjs
  - untracked: src/web/static/citizen-confirmation-gate.js,
    s6_visual_evidence/
  - note: parent branch's purpose (#1367) was superseded by later merged work;
    disposition (commit-as-archive vs discard) is a pending owner decision

local stashes: 7 entries across multiple branches (incl. WIP on main,
  feat/1355 harness, fix/1295 egress policy)

local HOLD branches: ~10 refs inventoried in #1371 (closed with reasons)
```

GitHub remote remains authoritative. These items must be either committed to an archive ref or explicitly discarded before third-site work begins.

## 11. Current issue index

### Critical path

- #1232 — multi-site onboarding parent (gate = owner acceptance + scope answers)
- #1378 — P2 shared engine '북구청' 리터럴 파라미터화 (third-site 전 정리 대상)

### Lower-priority operations

- #1290 — Google Drive working-mirror resync; GitHub remains authoritative

### Deferred owner/public-release governance

- #1234 — Production/public-release license/provenance owner decision; not a general blocker to the current controlled faithful-clone MVP.

### Closed authority records (audit history)

- #1348 — Buk-gu canonical visual baseline (목적 완료 close 2026-08-22)
- #1364/#1365/#1366/#1368/#1369/#1370/#1371/#1363 — Golden Master recovery 체계
- #1380 — Seo-gu PARITY CLOSURE 증거 기록

## 12. Historical execution order superseded

Older current-status text identified #1303/#1312 and related G3 slices as the active execution order, and later text identified #1364/PR #1367/PR #1372 as active. Both are superseded: the Golden resident parity recovery they describe is **complete** (agent-verified; owner acceptance pending). Those items remain historical evidence.

No history is rewritten: prior issues, PRs and Git history remain evidence of how the product reached the current state.
