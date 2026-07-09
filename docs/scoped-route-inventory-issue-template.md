# Scoped Route Inventory Issue Template

A planning-only **template** for opening a scoped future route/content inventory
issue under the
[#862](https://github.com/skerishKang/400-ai-finder/issues/862) official-site
action navigator track.

> **Planning only — NOT live/provider/API/network authorization.**
> This template does **not** grant permission to run live network, provider,
> API, fetch, crawling, external navigation, Firecrawl, form submission,
> authentication, payment, or any site-affecting action. It does **not** collect
> a route inventory dataset and does **not** record new official-site facts or
> route URLs. Authorization for live/provider steps requires a separately scoped
> issue filled from this template **plus** the gates in
> [`docs/live-transition-decision-record.md`](live-transition-decision-record.md).

Companion documents:

- [`docs/official-site-route-inventory-plan.md`](official-site-route-inventory-plan.md) — schema, classification, and report format for future inventory.
- [`docs/official-site-route-inventory-authorization-checklist.md`](official-site-route-inventory-authorization-checklist.md) — pre-flight authorization checklist before any future collection.
- [`docs/official-site-route-inventory-prioritization-rubric.md`](official-site-route-inventory-prioritization-rubric.md) — scoring dimensions and candidate buckets for prioritizing future inventory.

---

## Issue title format

Pick a title that states mode and scope. Examples:

- **Planning-only inventory selection:**
  `plan: Buk-gu route/content inventory selection (no live crawl yet)`
- **Provider-assisted reference / inventory:**
  `ops: provider-assisted reference collection for allowlisted hosts`
- **Controlled live validation (opt-in only):**
  `ops: controlled live validation for <named path> (opt-in only)`

Controlled live validation titles must explicitly mark **opt-in only** — it is
never the default path for CI or unattended runs.

---

## Required front matter / fields

Fill every field before opening the issue:

| Field | Required value |
|-------|----------------|
| Parent issue | [#862](https://github.com/skerishKang/400-ai-finder/issues/862) or a scoped child issue |
| Chosen work mode | Exactly **one** mode from [`docs/live-transition-decision-record.md`](live-transition-decision-record.md) §2 |
| Explicit user approval | State whether explicit user approval is required before live/provider/API/network execution (`required` / `not required for this mode`) |
| Allowed hosts / providers | Explicit allowlist only; everything else is **deny-by-default** |
| Route families / candidate labels in scope | Named allowed route families or route labels |
| Explicit out-of-scope items | Items explicitly excluded from this issue |

If the work mode is unset, the default is **local/static demo replay**.

A concrete filled example for the first local/static scope is in
[`docs/official-site-route-inventory-first-scope-issue-draft.md`](official-site-route-inventory-first-scope-issue-draft.md)
(planning-only, no live collection).

---

## Checklist block

Before any collection, complete the pre-flight checklist:

- Link: [`docs/official-site-route-inventory-authorization-checklist.md`](official-site-route-inventory-authorization-checklist.md)
- Requirement: the authorization checklist must be **fully completed** before any collection.
- Reminder: **planning docs alone are not authorization** to run live/provider/API/network steps.

---

## Prioritization block

- Link: [`docs/official-site-route-inventory-prioritization-rubric.md`](official-site-route-inventory-prioritization-rubric.md)
- Requirement: selected candidates must include their **scores/buckets** or a
  **planning-only rationale** for why they were chosen.
- Constraint: **no whole-site cataloging** — prefer resident-task-relevant
  routes over a full-site map.

---

## Safety / confidentiality block

Every issue opened from this template must confirm:

- **no** secrets
- **no** confidential business / client / person details
- **no** personal data values
- **no** auth / payment / form payloads
- **no** uncontrolled crawling
- **no** site-affecting actions unless **separately** approved and scoped

High safety risk overrides high resident/demo value; uncertain items default to
do-not-demo / unsafe candidate until reclassified under an approved issue.

---

## Test and reporting block

- Default CI / local tests remain **offline-capable**.
- Live/provider validation is **separate and opt-in only**.
- A **post-action report** (per
  [`docs/official-site-route-inventory-plan.md`](official-site-route-inventory-plan.md) §7) is
  required before any future inventory data PR merge.

---

## Explicit non-goals

This template does **not**:

- authorize live work by itself,
- collect inventory data,
- change golden quests or route metadata,
- authorize Firecrawl, API keys, crawling, or external navigation,
- include confidential business / client / person details.

Authorization for live/provider steps remains in
[`docs/live-transition-decision-record.md`](live-transition-decision-record.md)
plus a separately scoped and explicitly approved issue.
