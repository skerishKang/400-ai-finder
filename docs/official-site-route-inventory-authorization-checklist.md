# Official-Site Route Inventory Authorization Checklist

A pre-flight authorization checklist to confirm **before** any future
**route/content inventory** collection that would support the
[#862](https://github.com/skerishKang/400-ai-finder/issues/862) official-site
action navigator track.

> **Planning only — NOT live/provider/API/network authorization.**
> This document is a planning artifact. It does **not** grant permission to run
> live network, provider, API, fetch, crawling, external navigation, Firecrawl,
> form submission, authentication, payment, or any site-affecting action.
> Authorization for those steps requires a separately scoped issue plus the gates
> in [`docs/live-transition-decision-record.md`](live-transition-decision-record.md).
> This checklist exists only to help you confirm the work mode, scope, and safety
> gates before opening such an issue.

This checklist is the companion gate for
[`docs/official-site-route-inventory-plan.md`](official-site-route-inventory-plan.md).
Read both before proposing future inventory collection.

---

## When to use this checklist

Use this checklist **before** opening or planning any future route/content
inventory work, including:

- a new inventory planning or collection issue under #862,
- a scoped child issue that enables provider-assisted reference collection,
- any PR that would allow, describe, or enable future inventory data collection.

Do **not** treat this checklist as authorization by itself. It is a confirmation
aid. The actual authorization path is the
[live transition decision record](live-transition-decision-record.md) plus an
explicitly approved scoped issue.

---

## Checklist table

Confirm **every** row before opening a future inventory issue/PR.

| # | Area | Check | Required confirmation |
|---|------|-------|------------------------|
| 1 | Parent issue / chosen work mode | Linked parent and exactly one work mode selected | Link [#862](https://github.com/skerishKang/400-ai-finder/issues/862) or a scoped child issue; select exactly **one** mode from `live-transition-decision-record.md` §2; if mode is unset, default to **local/static demo replay** |
| 2 | Scope boundary | Allowed scope and out-of-scope items stated | Named allowed route families or route labels; explicit out-of-scope items; if a full production rebuild is needed, escalate to [#873](https://github.com/skerishKang/400-ai-finder/issues/873) |
| 3 | External request authority | External request policy is explicit | State whether external requests are allowed; if allowed, name the executing party (human operator, named script, CI job, never-by-default); allowed hosts/providers use an explicit allowlist, everything else is deny-by-default |
| 4 | Safety gates | All safety gates satisfied | No confidential business/client/person details; no secrets, credentials, personal data, payment data, auth data, or form payloads; no uncontrolled crawling; no form submission / authentication / payment / site-affecting action; rollback / stop condition defined |
| 5 | Test and reporting split | Tests and reporting are separated | Default local/CI tests remain offline-capable; live/provider validation is opt-in only and separate; a post-action report is required before any future inventory data PR merge |
| 6 | Public issue/PR wording rules | Public wording stays safe | Product/technical scope only; no confidential details; planning docs alone do not authorize live work |

### 1. Parent issue / chosen work mode

- Link the parent issue: [#862](https://github.com/skerishKang/400-ai-finder/issues/862)
  or a scoped child issue.
- Choose **exactly one** work mode from
  [`docs/live-transition-decision-record.md`](live-transition-decision-record.md) §2:
  1. **local/static demo replay** — no live network (default; current MVP)
  2. **provider-assisted reference / inventory** — limited, allowlisted reference collection
  3. **controlled live-dependent experiment** — opt-in live path with stop conditions
  4. **operational integration** — integration against real operational systems (high bar)
  5. **full production rebuild** — product/repo/deploy rebuild track (high bar)
- If the mode is **unset**, the default is **local/static demo replay**. Never
  mix modes silently.

### 2. Scope boundary

- State the allowed **route families** or **route labels** for the work.
- List **explicit out-of-scope** items.
- If a **full production rebuild** is required, escalate to
  [#873](https://github.com/skerishKang/400-ai-finder/issues/873) rather than
  expanding scope inside inventory work.

### 3. External request authority

- State whether **external requests** are allowed (`yes` / `no` / `never-by-default`).
- If allowed, name the **executing party** (human operator, named script, CI job).
- Allowed **hosts/providers** use an explicit **allowlist**; everything else is
  **deny-by-default**.

### 4. Safety gates

All of the following must hold:

- **no** confidential business / client / person details,
- **no** secrets, credentials, personal data, payment data, auth data, or form payloads,
- **no** uncontrolled crawling,
- **no** form submission / authentication / payment / site-affecting action,
- a defined **rollback / stop condition**.

### 5. Test and reporting split

- Default local/CI tests remain **offline-capable**.
- Live/provider validation is **opt-in only** and kept in a **separate** path.
- A **post-action report** is required before any future inventory data PR merge.

### 6. Public issue/PR wording rules

- Keep wording to **product/technical scope** only.
- Include **no confidential details**.
- State explicitly that **planning docs alone do not authorize live work**.

---

## Required PR/issue report fields

For any future issue/PR that enables inventory collection, include:

| Field | Fill with |
|-------|-----------|
| Parent issue | [#862](https://github.com/skerishKang/400-ai-finder/issues/862) or scoped child issue link |
| Chosen work mode | Exactly one mode from `live-transition-decision-record.md` §2 |
| Allowed hosts / providers | Explicit allowlist only; deny-by-default otherwise |
| Scope boundary | Allowed route families/labels + explicit out-of-scope items |
| External request authority | Allowed? Executing party? |
| Safety gates | Confirm no secrets / no personal data / no crawling / no site-affecting action / rollback plan |
| Operator / tool / script | Who ran what (human, script name, version) |
| Started / ended time | Collection window |
| Routes collected | List of `inventory_id` / path labels collected |
| Requests / clicks / calls summary | Hosts and purpose counts — no confidential payloads |
| Redactions / confidentiality check | Confirmation that secrets and personal/client details were excluded |
| Artifacts produced | Paths to redacted artifacts (if any) |
| Stop / rollback condition | When collection stopped and how live paths were disabled |

**After any future collection:** the report must attach to the authorizing issue
before merge of inventory data. Unreported live collection is out of process.

---

## Explicit non-goals

This checklist document does **not**:

- authorize or perform live / provider / API / fetch / network execution,
- authorize Firecrawl, API keys, or external API calls,
- authorize crawling or external navigation,
- change source code, quest metadata, tests, or the golden quest set,
- add a new golden quest or route inventory dataset,
- make a production deployment decision,
- include confidential business / client / person details,
- grant live-work authorization by existence alone.

Authorization for live/provider steps remains in
[`docs/live-transition-decision-record.md`](live-transition-decision-record.md)
plus a separately scoped and explicitly approved issue.
