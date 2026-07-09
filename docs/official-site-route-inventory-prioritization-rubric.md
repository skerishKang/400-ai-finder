# Official-Site Route Inventory Prioritization Rubric

A planning-only rubric for **prioritizing** future route/content inventory
candidates that would support the
[#862](https://github.com/skerishKang/400-ai-finder/issues/862) official-site
action navigator track.

> **Planning only — NOT live/provider/API/network authorization.**
> This document is a planning artifact. It does **not** grant permission to run
> live network, provider, API, fetch, crawling, external navigation, Firecrawl,
> form submission, authentication, payment, or any site-affecting action. It
> does **not** collect a route inventory dataset and does **not** record new
> official-site facts or route URLs. Authorization for live/provider steps
> requires a separately scoped issue plus the gates in
> [`docs/live-transition-decision-record.md`](live-transition-decision-record.md).

Companion documents:

- [`docs/official-site-route-inventory-plan.md`](official-site-route-inventory-plan.md) — schema, classification, and report format for future inventory.
- [`docs/official-site-route-inventory-authorization-checklist.md`](official-site-route-inventory-authorization-checklist.md) — pre-flight authorization checklist before any future collection.

---

## Planning-only boundary

This PR and this rubric must keep:

- **no** live browsing, crawling, fetch, provider/API, Firecrawl, or network execution
- **no** route inventory dataset rows collected or committed
- **no** new official-site facts or route URLs collected in this PR
- **no** confidential business / client / person details
- this rubric **does not authorize live work** by itself

All inventory rows, route URLs, and official-site facts remain in **future**
scoped issues. This document only defines how to prioritize candidates.

---

## Prioritization dimensions

Score each future candidate across these dimensions. Summary of each:

| Dimension | What it measures |
|-----------|------------------|
| Resident task value | How directly the route serves a resident task (안내, 신고 경로 안내, 위치·절차 안내) |
| Navigation pain / findability problem | How hard residents currently find or complete the path |
| Demo explainability | How clearly a demo can explain the route's purpose and flow |
| Safe demo feasibility | Whether the route can be represented with local/static fixtures and guidance |
| External handoff risk | Risk of handing off to external services (Government24, etc.) without confusing residents |
| Personal data / auth / payment / site-affecting risk | Whether personal data, authentication, payment, or site-affecting action is involved |
| Alignment with the five locked local/static golden quests | Whether the route supports or extends the existing locked local/static golden quests without regressing them |

---

## Scoring rubric

Use a simple **0 / 1 / 2** (or low / medium / high) scale per dimension. Higher
is stronger priority *within* a safety-acceptable band.

| Score | Meaning |
|-------|---------|
| 0 / low | Weak or unknown contribution on this dimension |
| 1 / medium | Moderate contribution |
| 2 / high | Strong contribution |

**Override rule — safety first:**

- **High safety risk overrides high resident/demo value.** If
  *personal data / auth / payment / site-affecting risk* scores 2 (high), the
  candidate must **not** be treated as a demo or live candidate regardless of
  how high its resident-task or demo value is.
- **Uncertain items default to do-not-demo / unsafe candidate** until
  reclassified under an explicitly approved scoped issue.

---

## Candidate buckets

After scoring, place each candidate in exactly one bucket. Buckets mirror the
classification in
[`docs/official-site-route-inventory-plan.md`](official-site-route-inventory-plan.md)
§4.

| Bucket | When to use |
|--------|-------------|
| **High-priority local/static candidate** | Strong resident value + safe demo feasible + no safety risk; fits local/static demo |
| **Guidance-only candidate** | Useful to explain, but best represented with guidance text rather than a simulated flow |
| **Provider-assisted reference candidate** | Structured reference/inventory would help, still no operational submit; allowlisted only |
| **Controlled live validation candidate** | Bounded live check needed to confirm a public path fact; opt-in with allowlist + report |
| **Operational integration candidate** | Real operational systems must be integrated; high-bar, separate approval |
| **Production rebuild candidate / #873 escalation** | Findings imply full-site rebuild / deploy / repo decisions; escalate to [#873](https://github.com/skerishKang/400-ai-finder/issues/873) |
| **Do-not-demo / unsafe candidate** | Personal data, auth, payment, or site-affecting risk cannot be made demo-safe; document as out-of-demo |

Default when unsure: **do-not-demo / unsafe candidate**.

---

## Future report template

For any future issue that selects routes for inventory, report:

| Field | Fill with |
|-------|-----------|
| Selected routes | `inventory_id` / path labels chosen, and the bucket each was assigned |
| Why selected | Per-dimension scores and the resident-task rationale (no confidential details) |
| Excluded routes | Routes intentionally skipped and the dimension/score that excluded them |
| Safety risk stated | Safety dimension scores and the resulting bucket; state risk without confidential payloads |
| Work mode | Exactly one mode from `live-transition-decision-record.md` §2 |
| Allowed hosts / providers | Explicit allowlist only |
| Report reference | Link to the post-action report required before inventory data PR merge |

**Exclusions and safety risk** must be stated in product/technical terms only —
no confidential business / client / person details, no secrets, no personal
data values.

---

## Relationship to existing docs

| Link | Role |
|------|------|
| [`docs/live-transition-decision-record.md`](live-transition-decision-record.md) | Governs **any** future live / provider / API / network step |
| [`docs/official-site-route-inventory-plan.md`](official-site-route-inventory-plan.md) | Schema, classification, and report format for future inventory |
| [`docs/official-site-route-inventory-authorization-checklist.md`](official-site-route-inventory-authorization-checklist.md) | Pre-flight authorization checklist before any future collection |
| [#862](https://github.com/skerishKang/400-ai-finder/issues/862) | Primary parent track — official-site action navigator and live integration |
| [#873](https://github.com/skerishKang/400-ai-finder/issues/873) | Applies only when inventory findings imply production / full-site rebuild |

**This rubric does not authorize live work by itself.** Selection/prioritization
here is planning only; actual collection still requires the authorization
checklist plus a separately scoped and approved issue.
