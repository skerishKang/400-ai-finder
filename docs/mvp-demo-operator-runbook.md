# MVP Demo Operator Runbook

> **Clone invariant:** 좌측 시민 사이트의 공식 페이지 clone은 [canonical invariant](product/exact-official-site-clone-invariant.md)를 따른다. 이 historical/planning 문서의 내용은 exact-clone 계약을 약화하지 않는다. Live retrieval이나 분석은 canonical fixture 기반 왼쪽 화면을 대체하지 않는다.

This runbook lets a reviewer or demo operator run, verify, and present the
Buk-gu Gwangju MVP resident-task shell **without reading implementation
history**. It is docs-only guidance for the locked local/static surface.

> **Related contract:** [`docs/mvp-golden-quest-fidelity-matrix.md`](mvp-golden-quest-fidelity-matrix.md)
> locks the fidelity expectations for the five golden quests. Prefer that
> matrix when a detail in this runbook and the matrix appear to diverge.

---

## 1. Current MVP scope

The current MVP demo surface is intentionally narrow:

| Area | In scope |
|------|----------|
| Left surface | Buk-gu website-like resident path (menu LNB, breadcrumb-style path, body content that mirrors the official local/static page shape) |
| Right surface | AI assistant / quest card / action choreography (action-plan quest card) |
| Flows | Five locked local/static resident-task golden quests — the deterministic scripted tier (see §2) |
| Runtime mode | Local / static only (for the current demo artifact) |

> **Product direction:** the five golden quests are the deterministic scripted
> tier. The intended product also answers **unknown natural-language questions
> via an LLM fallback**; the current static artifact does not because its build
> has no LLM/API/network. That is a deployment constraint, not the final intent.
> See [`docs/hybrid-scripted-llm-architecture-intent.md`](hybrid-scripted-llm-architecture-intent.md).

**Explicitly out of scope for this demo:**

- no live / provider-dependent behavior
- no external request / navigation (real Buk-gu, Government24, SafetyReport, 여기로, etc.)
- no site-affecting action (submit, pay, authenticate, phone connect, form completion)

If a demo path would require any of the above, stop and open a new issue.
Do **not** hot-patch main during a demo.

---

## 2. Golden quest demo scripts

Use **only** these five locked resident prompts. Each quest is `source_mode =
local_static` and stops at `STOP_FOR_USER_CONFIRMATION`.

### A. `housing_department_lookup` — 아파트 정보 안내

| Field | Value |
|-------|-------|
| **Resident task** | 아파트 정보 안내 |
| **Resident prompt (suggested)** | `공동주택 관련 문의는 어느 부서에 해야 하나요?` |
| **quest_id** | `housing_department_lookup` |
| **Expected left surface path** | 북구청 홈 > 분야별정보 > 건축 > 아파트정보 > 아파트현황 |
| **Expected left surface content** | 아파트정보 / 아파트현황 table / 전체 428건 / 관리사무소 column / 아파트생활정보 card |
| **Expected right-panel quest card** | action-plan card showing `local_static` and `STOP_FOR_USER_CONFIRMATION` (labels such as 아파트정보 화면 이동, 아파트생활정보 관련 안내 확인) |
| **source_mode** | `local_static` |
| **stop_condition** | `STOP_FOR_USER_CONFIRMATION` |
| **Must-not-do boundary** | Do **not** regress to generic 공동주택과 전화번호 lookup. No search submit / 하자 접수 / personal-data input / phone connect. |

**E2E verifier:** `tests/browser/verify_housing_quest_e2e.mjs`

---

### B. `illegal_parking_report_guidance` — 불법 주정차 신고 안내

| Field | Value |
|-------|-------|
| **Resident task** | 불법 주정차 신고 안내 |
| **Resident prompt (suggested)** | `불법 주정차 신고는 어디서 하나요?` |
| **quest_id** | `illegal_parking_report_guidance` |
| **Expected left surface path** | 북구청 홈 > 분야별정보 > 차량교통 > 지도단속 |
| **Related handoff (guidance only)** | 안전신문고 |
| **Expected right-panel quest card** | action-plan card showing `local_static` and `STOP_FOR_USER_CONFIRMATION` (labels such as 지도단속 안내 화면 이동, 안전신문고 신고 경로 안내 확인) |
| **source_mode** | `local_static` |
| **stop_condition** | `STOP_FOR_USER_CONFIRMATION` |
| **Must-not-do boundary** | No internal 불법 주정차 신고 form. No real `safetyreport.go.kr` navigation/request. No 본인인증 / 사진 / 위치 / 차량번호 / 제출. |

**E2E verifier:** `tests/browser/verify_illegal_parking_quest_e2e.mjs`

---

### C. `bulky_waste_disposal_guidance` — 대형폐기물 배출 안내

| Field | Value |
|-------|-------|
| **Resident task** | 대형폐기물 배출 안내 |
| **Resident prompt (suggested)** | `매트리스 폐기 신청은 어디서 하나요?` |
| **quest_id** | `bulky_waste_disposal_guidance` |
| **Expected left surface path** | 북구청 홈 > 분야별정보 > 환경재활용 > 대형폐기물 배출방법 |
| **Related handoff (guidance only)** | 여기로 app / 북구청 홈페이지 신청 |
| **Expected right-panel quest card** | action-plan card showing `local_static` and `STOP_FOR_USER_CONFIRMATION` (labels such as 대형폐기물 배출방법 화면 이동, 대형폐기물 배출방법 안내 확인) |
| **source_mode** | `local_static` |
| **stop_condition** | `STOP_FOR_USER_CONFIRMATION` |
| **Must-not-do boundary** | No real 여기로 move/request. No 품목/주소/연락처 input. No 결제 / 스티커 / 배출번호 simulation. |

**E2E verifier:** `tests/browser/verify_bulky_waste_quest_e2e.mjs`

---

### D. `move_in_report_guidance` — 전입신고 안내

| Field | Value |
|-------|-------|
| **Resident task** | 전입신고 안내 |
| **Resident prompt (suggested)** | `전입신고는 어디서 하나요?` |
| **quest_id** | `move_in_report_guidance` |
| **Expected left surface path** | 북구청 홈 > 종합민원 > 전자민원창구 > 정부24 |
| **Related handoff (guidance only)** | Government24 / 주민센터 |
| **Expected right-panel quest card** | action-plan card showing `local_static` and `STOP_FOR_USER_CONFIRMATION` (labels such as 정부24 전입신고 연결 안내 화면 이동, 정부24 전입신고 연결 안내 카드 확인) |
| **source_mode** | `local_static` |
| **stop_condition** | `STOP_FOR_USER_CONFIRMATION` |
| **Must-not-do boundary** | No 북구청-internal 전입신고 form. No real Government24 navigation/request. No 본인인증 / 주소 / 세대주 / 가족관계 input. No 제출. |

**E2E verifier:** `tests/browser/verify_move_in_quest_e2e.mjs`

---

### E. `public_health_center_guidance` — 보건소 위치·진료 안내

| Field | Value |
|-------|-------|
| **Resident task** | 보건소 위치·진료 안내 |
| **Resident prompt (suggested)** | `북구 보건소 위치랑 진료 안내 알려줘` |
| **quest_id** | `public_health_center_guidance` |
| **Expected left surface path** | 북구청 홈 > 보건소 > 보건소소개 > 찾아오시는 길 |
| **Expected right-panel quest card** | action-plan card showing `local_static` and `STOP_FOR_USER_CONFIRMATION` (labels such as 보건소 위치·진료 안내 화면 이동, 보건소 위치·진료 안내 카드 확인) |
| **source_mode** | `local_static` |
| **stop_condition** | `STOP_FOR_USER_CONFIRMATION` |
| **Must-not-do boundary** | No 의료 판단 / 진단 / 처방 / 예약 simulation. No 건강정보 input. No appointment / prescription submission. |

**E2E verifier:** `tests/browser/verify_public_health_center_quest_e2e.mjs`

---

## 3. Local verification commands

Run from the repository root. Prefer the committed project commands below;
do not invent alternate scripts for this runbook.

### 3.1 Workspace hygiene

```bash
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git status --short
git diff --check
```

### 3.2 Fidelity / contract pytest (docs + matrix lock)

Focused golden-matrix contract:

```bash
PYTHONPATH=. pytest tests/test_mvp_golden_quest_fidelity_matrix.py
```

Broader local/static MVP contract suite used by this runbook:

```bash
PYTHONPATH=. pytest \
  tests/test_bukgu_quest_schema.py \
  tests/test_bukgu_quest_to_action_plan.py \
  tests/test_mvp_action_contract.py \
  tests/test_citizen_first_use_shell.py \
  tests/test_citizen_action_plan.py \
  tests/test_citizen_action_demo_chat_shell_contract.py \
  tests/test_build_cloudflare_pages.py \
  tests/test_static_server_path_traversal.py
```

> CI also runs **MVP Contract Checks** (`.github/workflows/mvp-contracts.yml`)
> on PRs and `main`. Confirm that check is green for the demo commit when
> preparing an external review.

### 3.3 Static Pages build

```bash
PYTHONPATH=. python3 scripts/build_cloudflare_pages.py
```

This produces the backend-free artifact under `dist/cloudflare-pages/`
(gitignored). Details: [`docs/cloudflare-pages-bukgu-mvp.md`](cloudflare-pages-bukgu-mvp.md).

### 3.4 Local static server + browser E2E

1. Build the static artifact (§3.3).
2. Serve `dist/cloudflare-pages/` with the **existing local static server
   command** used in this project (localhost / `127.0.0.1` only). Do not point
   browsers or verifiers at real Buk-gu / Government24 / SafetyReport / 여기로
   hosts.
3. Run the locked E2E verifiers against that origin (replace `<port>` with the
   local port actually serving the artifact):

```bash
node tests/browser/verify_housing_quest_e2e.mjs http://127.0.0.1:<port>
node tests/browser/verify_illegal_parking_quest_e2e.mjs http://127.0.0.1:<port>
node tests/browser/verify_bulky_waste_quest_e2e.mjs http://127.0.0.1:<port>
node tests/browser/verify_move_in_quest_e2e.mjs http://127.0.0.1:<port>
node tests/browser/verify_public_health_center_quest_e2e.mjs http://127.0.0.1:<port>
node tests/browser/verify_citizen_first_use_pages.mjs http://127.0.0.1:<port>
```

Notes:

- E2E scripts accept **only** local `http://` origins (`127.0.0.1`,
  `localhost`, `::1`). External hosts are rejected before browser work starts.
- Quest E2E scripts open the public first-use entry at `/mvp`.
- Report **non-local requests = 0** from each E2E run when summarizing demo
  readiness.

### 3.5 Optional shell runtime harness (no browser server)

The CI MVP contract workflow also runs a Node VM harness that does **not**
require a listening server:

```bash
node tests/browser/verify_mvp_shell_runtime.mjs
```

---

## 4. Demo checklist

### Before demo

- [ ] Confirm branch / `main` SHA (expected baseline for this docs work includes
      `#991` matrix merge `d9b4be5ba868544554fc549fee987f2cd1b692f3` or a later
      `main` that contains it)
- [ ] Confirm clean intended tree (`git status --short` shows only expected
      local artifacts, if any)
- [ ] Confirm no unexpected open PR for the demo branch
- [ ] Confirm **MVP Contract Checks** success on the current PR / `main`
- [ ] Confirm local/static boundary: built artifact only; no live provider keys
      required for the five golden quests
- [ ] Confirm §3 commands needed for the audience have been run (at minimum
      matrix pytest + static build when demoing the `/mvp` surface)

### During demo

- [ ] Use **only** the five locked resident prompts in §2
- [ ] Confirm left surface shows the expected real-site-like path for each quest
- [ ] Confirm right quest card shows `local_static` and
      `STOP_FOR_USER_CONFIRMATION`
- [ ] Do **not** navigate to real Buk-gu / Government24 / SafetyReport / 여기로
- [ ] Do **not** enter personal data
- [ ] Do **not** submit forms

### After demo

- [ ] Preserve screenshots / logs only if they contain **no** confidential or
      personal data
- [ ] Report non-local requests = 0 from E2E
- [ ] Report any mismatch as a **new issue** rather than hot-patching `main`

---

## 5. Troubleshooting

| Symptom | Likely cause | Operator action |
|---------|--------------|-----------------|
| **Quest not matched** | Prompt drifted from locked phrasing; stale quest registry; wrong `/mvp` entry | Re-type the **exact** suggested prompt from §2. Rebuild static artifact. Confirm `data/quests/bukgu_gwangju_quests.json` on the demo SHA still contains the five `quest_id`s. |
| **Stale local server / build** | Serving an older `dist/cloudflare-pages` or a non-artifact directory | Stop the old server process. Re-run `PYTHONPATH=. python3 scripts/build_cloudflare_pages.py`. Restart the existing local static server against the fresh `dist/cloudflare-pages/`. Hard-refresh the browser. |
| **Browser E2E timeout** | Server not listening; wrong port; page hung | Confirm `http://127.0.0.1:<port>/mvp` loads manually. Re-run the specific `verify_*_quest_e2e.mjs` with the correct origin. Prefer reduced-motion / headless as the scripts already set. |
| **Non-local request detected** | UI attempted external navigation/fetch; wrong base URL; live code path mixed in | Abort demo narrative if needed. Capture E2E non-local request list (no secrets). Open a new issue; do not “fix” by enabling real hosts. |
| **Visual surface looks generic or wrong path** | Fidelity regression (e.g. housing fell back to generic department lookup) | Compare left surface against §2 + [`mvp-golden-quest-fidelity-matrix.md`](mvp-golden-quest-fidelity-matrix.md). Run `PYTHONPATH=. pytest tests/test_mvp_golden_quest_fidelity_matrix.py` and the matching `verify_*_quest_e2e.mjs`. File an issue with screenshots (no PII). |
| **Right panel does not show `STOP_FOR_USER_CONFIRMATION`** | Quest card / action-plan contract drift | Confirm quest card text includes both `local_static` and `STOP_FOR_USER_CONFIRMATION`. Run matrix + action-plan / action-contract pytest listed in §3.2. |
| **Demo accidentally tries to collect personal data** | Wrong quest path, invented form, or operator free-form prompt | Stop immediately. Do not enter name / address / phone / vehicle / health data. Return to a locked §2 prompt. Treat as a safety incident → new issue if the product UI prompted for personal data. |

---

## 6. Pointer to matrix

Fidelity contract (locked paths, prohibited regressions, E2E file mapping):

- [`docs/mvp-golden-quest-fidelity-matrix.md`](mvp-golden-quest-fidelity-matrix.md)

Static Pages build / deploy context (backend-free artifact):

- [`docs/cloudflare-pages-bukgu-mvp.md`](cloudflare-pages-bukgu-mvp.md)

---

## Safety boundary (this runbook does not authorize)

Do **not** add via demo or follow-up “quick fixes” during the demo:

- new quest
- code behavior changes
- quest metadata changes
- test expectation changes
- live / provider-dependent behavior
- external non-local request
- real Buk-gu / Government24 / SafetyReport / 여기로 navigation
- personal-data input
- login / authentication
- submission / payment / receipt / completion simulation
- confidential business / client / person details

This document is operator procedure only. Product contract truth for the five
quests remains the fidelity matrix and its pytest lock.
