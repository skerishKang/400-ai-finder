# Issue #1078 — Corrective Note: Exact Official-Site Clone Manifest Realignment

> Authoritative CTO clarification recorded under Issue #1078. This note ONLY
> corrects documents that falsely described the current state. The full test
> rewrite for the stale golden-quest contract is split to **#1079** and is
> intentionally NOT mixed into this corrective commit.

## What was wrong (prior CTO directive error)

A prior CTO directive erroneously placed two **deprecated / non-route** quests
into the official page fixture manifest's `complete_capture_required` list:

- `move_in_report_guidance` — not a renderer route, not a current quest in the
  phase-1 golden set.
- `public_health_center_guidance` — not a renderer route, not a current quest
  in the phase-1 golden set.

Those entries described the manifest as if it tracked 6 capture targets when the
production renderer only exposes **13 pages**, none of which are the two
deprecated quests. That was a false description of the current state.

## Corrected direction (this issue, #1078)

1. The manifest's baseline is the **actual production renderer route/page-ID set**,
   not an example list from a prior directive.
2. `move_in_report_guidance` / `public_health_center_guidance` are **removed**
   from the manifest. They are neither quests (phase-1 golden) nor renderer
   routes.
3. The manifest now registers exactly the **13 renderer routes** under
   `capture_required` (status `capture_required`, `network_required_at_runtime`
   `false`), each carrying the §5 mandatory fields.
4. The `capture_required` set is verified by a test that **dynamically extracts**
   the route set from the production renderer source
   (`src/web/static/citizen-action-demo-map.js` `CLOSED_ROUTE_IDS` and
   `src/agent/citizen_action_plan.py` `_VALID_ROUTE_IDS`) and asserts equality
   with the manifest — not a separately hand-maintained literal.
5. `quest_id` is an entry *flow* into a renderer route, not a substitute for the
   manifest `page_id`. Each `capture_required` entry carries a `quest_ids`
   mapping field.
6. `apartment-dept` and `apartment-info` are distinct official pages and are
   registered as **separate** entries.

## Known discrepancy flagged (not resolved here)

- CTO #4 directive maps `housing_department_lookup` → `apartment-info`.
- The **actual** registry (`data/quests/bukgu_gwangju_quests.json`) has
  `housing_department_lookup` OPEN route `apartment-dept` (not `apartment-info`).
- Both pages are registered for capture. The mapping/route reconciliation is
  deferred to **#1079** (test realignment of stale golden-quest expectations).

## Scope boundary

- This commit corrects false documentation only.
- It does **NOT** weaken, xfail, or rewrite
  `test_mvp_golden_quest_fidelity_matrix.py`. That stale baseline defect is
  **#1079**.
- No `amend` / `rebase` / `force push` / PR creation on branch
  `policy/1078-exact-official-site-clone`.
