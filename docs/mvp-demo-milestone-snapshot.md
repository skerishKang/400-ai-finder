# MVP Demo Milestone Snapshot

Short closeout snapshot for the Buk-gu Gwangju **local/static** MVP demo.
It records what is complete now, what the demo is not, and what remains on the
live/production tracks.

> **Not a changelog.** Prefer the runbook and fidelity matrix for day-to-day
> operator and regression detail.

---

## 1. Milestone status

| Status | Statement |
|--------|-----------|
| Complete | Current MVP demo milestone is complete for **local/static stakeholder review**. |
| Not production | The demo is **not** a production rebuild. |
| Not live integration | The demo is **not** a live official-site integration. |
| What it is | A **local/static, high-fidelity demonstration surface** for five locked resident-task flows. |

---

## 2. Completed capabilities

- First-use question entry
- Split left website surface / right AI assistant shell
- Five locked local/static golden quests
- Real-page fidelity hardening for the five quests
- Quest fidelity matrix
- Matrix regression test
- Operator runbook
- README entry-point discoverability

Real-page fidelity hardening for the five quests was completed earlier
(including #987 / #989 and related follow-ups). Closeout docs/tests for this
milestone are summarized in §7.

---

## 3. Locked golden quest set

All five quests use `source_mode: local_static` and
`stop_condition: STOP_FOR_USER_CONFIRMATION`.

| # | quest_id | resident task | primary path |
|---|----------|---------------|--------------|
| A | `housing_department_lookup` | 아파트 정보 안내 | 북구청 홈 > 분야별정보 > 건축 > 아파트정보 > 아파트현황 |
| B | `illegal_parking_report_guidance` | 불법 주정차 신고 안내 | 북구청 홈 > 분야별정보 > 차량교통 > 지도단속 |
| C | `bulky_waste_disposal_guidance` | 대형폐기물 배출 안내 | 북구청 홈 > 분야별정보 > 환경재활용 > 대형폐기물 배출방법 |
| D | `move_in_report_guidance` | 전입신고 안내 | 북구청 홈 > 종합민원 > 전자민원창구 > 정부24 |
| E | `public_health_center_guidance` | 보건소 위치·진료 안내 | 북구청 홈 > 보건소 > 보건소소개 > 찾아오시는 길 |

Do not add a sixth golden quest in this milestone without a new issue and
matrix update.

---

## 4. Boundary

This MVP demo surface is intentionally constrained:

- **local/static only**
- **no** live / provider-dependent behavior
- **no** external request / navigation (real Buk-gu, Government24, SafetyReport, 여기로, etc.)
- **no** personal-data input
- **no** login / authentication
- **no** submission / payment / receipt / completion simulation
- **no** confidential business / client / person details in public docs, issues, or PRs

If a path would require any of the above, stop and open a new issue on the
appropriate deferred track. Do **not** treat this demo as production or live
integration.

---

## 5. Verification references

### Docs

- [`docs/mvp-demo-operator-runbook.md`](mvp-demo-operator-runbook.md) — how to run, verify, and present the five locked flows
- [`docs/mvp-golden-quest-fidelity-matrix.md`](mvp-golden-quest-fidelity-matrix.md) — locked paths, stop behavior, prohibited regressions

### Matrix regression test

- `tests/test_mvp_golden_quest_fidelity_matrix.py`

### Browser E2E verifiers

- `tests/browser/verify_housing_quest_e2e.mjs`
- `tests/browser/verify_illegal_parking_quest_e2e.mjs`
- `tests/browser/verify_bulky_waste_quest_e2e.mjs`
- `tests/browser/verify_move_in_quest_e2e.mjs`
- `tests/browser/verify_public_health_center_quest_e2e.mjs`
- `tests/browser/verify_citizen_first_use_pages.mjs`

---

## 6. Deferred work

Live/production/integration work is **explicitly deferred**. It is **not**
part of this local/static MVP closeout.

| Epic | Track |
|------|--------|
| [#862](https://github.com/skerishKang/400-ai-finder/issues/862) | official-site action navigator and live integration track |
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

## 7. Recent closeout PRs

Compact list only (not a full history):

| PR | Role |
|----|------|
| [#991](https://github.com/skerishKang/400-ai-finder/pull/991) | fidelity matrix |
| [#993](https://github.com/skerishKang/400-ai-finder/pull/993) | operator runbook |
| [#995](https://github.com/skerishKang/400-ai-finder/pull/995) | README discoverability |

Earlier real-page fidelity hardening completed before this closeout (e.g. #987 / #989 and related quest fidelity PRs).
