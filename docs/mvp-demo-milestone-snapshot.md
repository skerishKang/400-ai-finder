# MVP Demo Milestone Snapshot

Short closeout snapshot for the Buk-gu Gwangju **local/static** MVP demo.
It records what is complete now, what the demo is not, and what remains on the
live/production tracks.

> 좌측 시민 사이트 화면 철칙(Exact Official-Site Clone)을 따른다:
> [docs/product/exact-official-site-clone-invariant.md](docs/product/exact-official-site-clone-invariant.md)
> 이전 방향은 폐기되었다. 현재 계약은 exact official-site clone이다.

> **Not a changelog.** Prefer the runbook and fidelity matrix for day-to-day
> operator and regression detail.

---

## 1. Milestone status

| Status | Statement |
|--------|-----------|
| Complete | Current MVP demo milestone is complete for **local/static stakeholder review**. |
| Not production | The demo is **not** a production rebuild. |
| Not live integration | The demo is **not** a live official-site integration. |
| What it is | A **local/static, scripted demonstration surface** for five locked resident-task flows. |

> **Scope note:** this milestone closes out the local/static demo surface only.
> It is **not** the entire product. The intended product also answers unknown
> questions via an LLM fallback (see
> [`docs/hybrid-scripted-llm-architecture-intent.md`](hybrid-scripted-llm-architecture-intent.md));
> the current static demo simply has no LLM/API/network in its build.

---

## 2. Completed capabilities

- First-use question entry
- Split left website surface / right AI assistant shell
- Five locked local/static golden quests
- Interaction shell mechanics
- Scripted choreography mechanics
- Local demo execution mechanics
- Shell/build contracts
- Current five-quest registry alignment
- Quest fidelity matrix
- Matrix regression test
- Operator runbook
- README entry-point discoverability

Closeout docs/tests for this milestone are summarized in §7.

---

## 3. Locked golden quest set

All five quests use `source_mode: local_static` and
`stop_condition: STOP_FOR_USER_CONFIRMATION`.

| # | quest_id | resident task | primary path |
|---|----------|---------------|--------------|
| A | `housing_department_lookup` | 공동주택과 안내 또는 공동주택 관련 부서 안내 | 홈 > 북구소개 > 구청안내 > 행정조직 > 공동주택과 > 조직 및 업무안내 |
| B | `illegal_parking_report_guidance` | 불법 주정차 신고 안내 | 북구청 홈 > 분야별정보 > 차량교통 > 지도단속 |
| C | `bulky_waste_disposal_guidance` | 대형폐기물 배출 안내 | 북구청 홈 > 분야별정보 > 환경재활용 > 대형폐기물 배출방법 |
| D | `passport_guidance` | 여권 발급 안내 | 북구청 홈 > 종합민원 > 여권민원 |
| E | `unmanned_kiosk_guidance` | 무인민원발급기 안내 | 북구청 홈 > 종합민원 > 무인민원발급기 |

Do not add a sixth golden quest in this milestone without a new issue and
matrix update.

---

## 4. Boundary

This MVP demo surface is intentionally constrained **for safe stakeholder
review**, but live LLM answering is the **intended next capability**, not a
forbidden one. Live work is gated (operational guardrails), not banned.

**Demo surface constraints (local/static default):**

- **local/static default** for the five golden quests in this milestone
- **no** live / provider behavior **in the demo shell by default** (scripted mode)
- **no** external request / navigation in the *demo shell* (real Buk-gu, Government24, SafetyReport, 여기로, etc.) — unless operator-enabled live mode
- **no** personal-data input
- **no** login / authentication
- **no** submission / payment / receipt / completion simulation
- **no** confidential business / client / person details in public docs, issues, or PRs

**Intended live product (gated, see `docs/live-transition-decision-record.md`):**

- Backend `/api/mvp/ask` may use **`tencent/hy3:free` via `kilocode`** (pre-approved)
  for resident-question answering with fail-closed sanitized diagnostics (#930/#931)
- Unknown questions route via LLM intent router → scripted simulation (known
  intent) or direct hy3 answer fallback (unknown intent)
- Live navigation of the real site is operator-approved, bounded, allowlisted host = `bukgu.gwangju.kr`

These constraints describe the **demo surface default**, not the whole product.
The product goal is an AI that answers and **actually navigates the real
Buk-gu site**. If a path requires live/provider behavior, open a new issue on
the appropriate track (#862 live integration) — do not treat this demo as the
entire product.

---

## 5. Verification references

### Docs

- [`docs/mvp-demo-operator-runbook.md`](mvp-demo-operator-runbook.md) — how to run, verify, and present the five locked flows
- [`docs/mvp-golden-quest-fidelity-matrix.md`](mvp-golden-quest-fidelity-matrix.md) — locked paths, stop behavior, prohibited regressions
- [`docs/product/exact-official-site-clone-invariant.md`](docs/product/exact-official-site-clone-invariant.md) — canonical invariant for left surface

### Matrix regression test

- `tests/test_mvp_golden_quest_fidelity_matrix.py`

### Browser E2E verifiers

- `tests/browser/verify_housing_quest_e2e.mjs`
- `tests/browser/verify_illegal_parking_quest_e2e.mjs`
- `tests/browser/verify_bulky_waste_quest_e2e.mjs`
- `tests/browser/verify_passport_quest_e2e.mjs`
- `tests/browser/verify_unmanned_kiosk_quest_e2e.mjs`
- `tests/browser/verify_citizen_first_use_pages.mjs`

---

## 6. Incomplete: official fixture capture

The following work is **not** part of this local/static MVP closeout:

- Complete official fixture capture (manifest has `capture_required`)
- Semantic/content parity with official pages
- Renderer-to-fixture parity
- Route별 official source verification
- Exact official clone completion

Current demo mechanics are complete, but exact official page parity is separate.
The interaction route/action contract matching correctly does **not** mean
official fixture parity is done.

---

## 7. Deferred work

Live/production/integration work that is **not** part of this local/static MVP
closeout is tracked on the broad epics. Note that an **LLM fallback for unknown
questions** is an **intended product path** (see
[`docs/hybrid-scripted-llm-architecture-intent.md`](hybrid-scripted-llm-architecture-intent.md)),
not an exclusion — it is gated by the live-transition decision record, not
forbidden.

| Epic | Track |
|------|--------|
| [#862](https://github.com/skerishKang/400-ai-finder/issues/862) | official-site action navigator and live integration track (includes the intended LLM fallback path) |
| [#873](https://github.com/skerishKang/400-ai-finder/issues/873) | full Buk-gu website rebuild planning and integration track |

**Deferred scope (belongs on #862 / #873, not this closeout):**

- live / provider-assisted reference collection
- live-dependent experiments
- operational form submission
- authentication
- production deployment
- full-site rebuild
- live official-site integration

---

## 8. Recent closeout PRs

Compact list only (not a full history):

| PR | Role |
|----|------|
| [#991](https://github.com/skerishKang/400-ai-finder/pull/991) | fidelity matrix |
| [#993](https://github.com/skerishKang/400-ai-finder/pull/993) | operator runbook |
| [#995](https://github.com/skerishKang/400-ai-finder/pull/995) | README discoverability |

Earlier closeout and quest realignment completed before this snapshot (e.g. #987 / #989 and #1079 quest realignment).
