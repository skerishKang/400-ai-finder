# Official-Site Route Inventory Planning Workflow Index

A planning-only **index** that ties together the route/content inventory
planning documents for the
[#862](https://github.com/skerishKang/400-ai-finder/issues/862) official-site
action navigator track.

> **Planning only — NOT live/provider/API/network authorization.**
> This index does **not** grant permission to run live network, provider, API,
> fetch, crawling, external navigation, Firecrawl, form submission,
> authentication, payment, or any site-affecting action. It does **not** collect
> a route inventory dataset and does **not** record new official-site facts or
> route URLs. Authorization for live/provider steps requires a separately scoped
> issue plus the gates in
> [`docs/live-transition-decision-record.md`](live-transition-decision-record.md).

---

## Planning-only warning

This PR and this index must keep:

- **no** live browsing, crawling, fetch, provider/API, Firecrawl, or network execution
- **no** route inventory dataset rows collected or committed
- **no** new official-site facts or route URLs collected in this PR
- **no** confidential business / client / person details
- this index **does not authorize live work** by itself

---

## Workflow order

Follow these steps for any future route/content inventory planning:

1. **Read** [`docs/live-transition-decision-record.md`](live-transition-decision-record.md) — the live-transition gate and work modes.
2. **Read** [`docs/official-site-route-inventory-plan.md`](official-site-route-inventory-plan.md) — schema, classification, and report format.
3. **Use** [`docs/official-site-route-inventory-prioritization-rubric.md`](official-site-route-inventory-prioritization-rubric.md) — score and bucket candidates.
4. **Complete** [`docs/official-site-route-inventory-authorization-checklist.md`](official-site-route-inventory-authorization-checklist.md) — pre-flight authorization before any collection.
5. **Open** future work from [`docs/scoped-route-inventory-issue-template.md`](scoped-route-inventory-issue-template.md) — a scoped issue with all required fields.
6. **Attach** the required post-action report (use [`docs/official-site-route-inventory-post-action-report-template.md`](official-site-route-inventory-post-action-report-template.md)) before any future inventory data PR merge.

When the planning package is complete, see the
[`docs/official-site-route-inventory-planning-closeout.md`](official-site-route-inventory-planning-closeout.md)
for the planning package closeout.

---

## Mode-selection summary

From [`docs/live-transition-decision-record.md`](live-transition-decision-record.md) §2:

- **local/static demo replay** remains the default when the mode is unset.
- Exactly **one** work mode must be selected for any future scoped work.
- Live/provider validation is **opt-in only and separate** — never the default for CI or unattended runs.
- High safety risk overrides resident/demo value; uncertain items default to do-not-demo / unsafe candidate until reclassified under an approved issue.

---

## Quick decision table

| Situation | Use |
|-----------|-----|
| Planning-only docs work | This index + the linked planning docs (no live step) |
| Inventory selection / prioritization | [`docs/official-site-route-inventory-prioritization-rubric.md`](official-site-route-inventory-prioritization-rubric.md) |
| Provider-assisted reference collection | Allowlisted mode via [`docs/scoped-route-inventory-issue-template.md`](scoped-route-inventory-issue-template.md) |
| Controlled live validation | Opt-in only, allowlist + report, via the issue template |
| Operational integration | High-bar, separate approval, via the issue template |
| Full production rebuild / #873 escalation | [#873](https://github.com/skerishKang/400-ai-finder/issues/873) when findings imply production / full-site rebuild |
| Do-not-demo / unsafe candidate | Document as out-of-demo; do not add golden quest or live demo path |
| First-scope selection example | [`docs/official-site-route-inventory-first-scope-selection.md`](official-site-route-inventory-first-scope-selection.md) — repo-local/static planning-only selection plan |

---

## Public wording rules

For any public issue, PR, or report:

- product/technical scope only,
- no confidential business / client / person details,
- no secrets or personal data values,
- no site-affecting actions unless **separately** approved and scoped.

---

## Relationship to #862 and #873

- [#862](https://github.com/skerishKang/400-ai-finder/issues/862) is the **primary parent track** for official-site action navigator / route inventory planning.
- [#873](https://github.com/skerishKang/400-ai-finder/issues/873) applies **only** when inventory findings imply production / full-site rebuild decisions.

This index does not authorize live work by itself; each future step still
requires the linked gates and a separately scoped, explicitly approved issue.
See [`docs/official-site-route-inventory-planning-closeout.md`](official-site-route-inventory-planning-closeout.md)
for the planning package closeout.
