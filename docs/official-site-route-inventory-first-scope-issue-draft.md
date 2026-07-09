# Official-Site Route Inventory First-Scope Issue Draft

A planning-only **draft issue package** for the first local/static route
inventory scope under the
[#862](https://github.com/skerishKang/400-ai-finder/issues/862) official-site
action navigator track. It is built from repository-local/static references
only.

> **Planning only — NOT live/provider/API/network authorization.**
> This draft issue package does **not** grant permission to run live network,
> provider, API, fetch, crawling, external navigation, Firecrawl, form
> submission, authentication, payment, or any site-affecting action. It does
> **not** collect a route inventory dataset, and it does **not** record or add
> new official-site facts, route URLs, selectors, or screenshots. Authorization
> for live/provider steps requires a separately scoped issue plus the gates in
> [`docs/live-transition-decision-record.md`](live-transition-decision-record.md).

---

## Planning-only warning

This PR and this draft issue package must keep:

- **no** live browsing, crawling, fetch, provider/API, Firecrawl, or network execution
- **no** route inventory dataset rows collected or committed
- **no** new official-site facts or route URLs collected in this PR
- **no** selectors, screenshots, or live facts added
- **no** confidential business / client / person details
- this draft issue package **does not authorize live work** by itself

---

## Draft issue title and summary

- **Title example:** `ops: first local/static route inventory selection package`
- **Parent issue:** [#862](https://github.com/skerishKang/400-ai-finder/issues/862)
- **Status:** draft / example only — **not** an opened execution issue. This
  package is for review and copy-paste into a future real scoped issue.

---

## Required fields filled from the template

Filled per [`docs/scoped-route-inventory-issue-template.md`](scoped-route-inventory-issue-template.md):

| Field | Value |
|-------|-------|
| Parent issue | [#862](https://github.com/skerishKang/400-ai-finder/issues/862) |
| Chosen work mode | **local/static demo replay** (exactly one) |
| Explicit user approval | Not required for docs-only / local-static planning; **required before** any future live/provider/API/network expansion |
| Allowed hosts / providers | **none**; everything is deny-by-default |
| Route families / candidate labels in scope | First-scope local/static labels only (see Candidate block) |
| Explicit out-of-scope items | auth / payment / personal-data / site-affecting actions / report filing / external live validation / whole-site cataloging |

---

## Checklist status

- **Authorization checklist:** not executed here; must be completed before any real collection per [`docs/official-site-route-inventory-authorization-checklist.md`](official-site-route-inventory-authorization-checklist.md).
- **Prioritization rubric:** applied at planning level only in [`docs/official-site-route-inventory-first-scope-selection.md`](official-site-route-inventory-first-scope-selection.md) per [`docs/official-site-route-inventory-prioritization-rubric.md`](official-site-route-inventory-prioritization-rubric.md).
- **Post-action report:** not applicable yet; required before any future inventory data PR merge.

---

## Candidate block

Selected local/static candidate labels from the first-scope selection plan:

- `housing_department_lookup` (아파트 정보 안내)
- `bulky_waste_disposal_guidance` (대형폐기물 배출 안내)
- `public_health_center_guidance` (보건소 위치·진료 안내)

Constraint: **no** route URLs, selectors, screenshots, or live facts are added
here. The golden quests and their metadata are **not** changed by this draft.

The resulting local/static seed records for these candidates are in
[`docs/official-site-route-inventory-first-local-static-records.md`](official-site-route-inventory-first-local-static-records.md)
— local/static placeholders only; this does **not** authorize live/provider work
and no route URLs were collected.

---

## PR / report requirements for the future real issue

For the future real issue opened from this draft:

- report **changed files** explicitly,
- keep default tests **offline-capable** (no live network required),
- allow **no** live/provider/API/network unless explicitly approved and scoped,
- any future inventory data PR must include the **post-action report** (use
  [`docs/official-site-route-inventory-post-action-report-template.md`](official-site-route-inventory-post-action-report-template.md)).

---

## Copy-paste issue body

Compact fenced block for the future real issue:

```markdown
Title: ops: first local/static route inventory selection package

Parent issue: #862
Chosen work mode: local/static demo replay
Explicit user approval: not required for docs-only/local-static planning;
  required before any future live/provider/API/network expansion
Allowed hosts / providers: none; deny-by-default
Route families / candidate labels in scope:
  - housing_department_lookup (아파트 정보 안내)
  - bulky_waste_disposal_guidance (대형폐기물 배출 안내)
  - public_health_center_guidance (보건소 위치·진료 안내)
Explicit out-of-scope items:
  auth / payment / personal-data / site-affecting actions /
  report filing / external live validation / whole-site cataloging

Checklist: complete docs/official-site-route-inventory-authorization-checklist.md
Prioritization: applied in docs/official-site-route-inventory-first-scope-selection.md
Safety: no secrets / no personal data values / no auth / no payment / no site-affecting action
Reporting: post-action report required before inventory data PR merge

Note: planning docs alone do not authorize live work.
```

---

## Relationship to #862 and #873

- [#862](https://github.com/skerishKang/400-ai-finder/issues/862) remains the **parent** for official-site action navigator / route inventory planning.
- [#873](https://github.com/skerishKang/400-ai-finder/issues/873) is only for production / full-site rebuild escalation.

This draft issue package does not authorize live work by itself; any future step
still requires the linked gates and a separately scoped, explicitly approved
issue.
