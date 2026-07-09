# Official-Site Route Inventory Post-Action Report Template

A planning-only **post-action report template** for the
[#862](https://github.com/skerishKang/400-ai-finder/issues/862) official-site
action navigator track. It defines what any future scoped route/content
inventory issue must report after a collection action, before its inventory data
PR merges.

> **Planning only — NOT live/provider/API/network authorization.**
> This template does **not** grant permission to run live network, provider,
> API, fetch, crawling, external navigation, Firecrawl, form submission,
> authentication, payment, or any site-affecting action. This PR performs **no**
> live browsing, crawling, fetch, provider/API, Firecrawl, or network execution,
> collects **no** route inventory dataset rows, and adds **no** new official-site
> facts, route URLs, selectors, or screenshots. Authorization for live/provider
> steps requires a separately scoped issue plus the gates in
> [`docs/live-transition-decision-record.md`](live-transition-decision-record.md).

---

## Planning-only warning

This PR and this template must keep:

- **no** live browsing, crawling, fetch, provider/API, Firecrawl, or network execution in this PR
- **no** route inventory dataset rows collected or committed
- **no** new official-site facts, route URLs, selectors, or screenshots collected in this PR
- **no** confidential business / client / person details
- the template **does not authorize live/provider work** by itself

---

## When this template is required

- before any future **inventory data PR merge**,
- after any scoped route/content inventory **collection action**, even local/static,
- after **provider-assisted reference collection**,
- after **controlled live validation**,
- **not** required for docs-only planning PRs unless they claim to have performed collection.

---

## Report header fields

| Field | Fill with |
|-------|-----------|
| Parent issue | [#862](https://github.com/skerishKang/400-ai-finder/issues/862) or scoped child issue |
| Scoped issue number | GitHub issue that authorized the work |
| PR number | GitHub PR carrying the inventory data |
| Work mode selected | Exactly **one** from [`docs/live-transition-decision-record.md`](live-transition-decision-record.md) §2 |
| Base / head SHA | Base and head commit SHAs of the PR |
| Date / time | Collection window |
| Operator / report source | Human operator, local worker, or named script/report source |

---

## Authorization and boundary confirmation

- Authorization checklist completed or marked **N/A** with reason (per [`docs/official-site-route-inventory-authorization-checklist.md`](official-site-route-inventory-authorization-checklist.md)).
- Explicit user approval status (required / not required for this mode).
- Allowed hosts / providers used (explicit allowlist only).
- **Deny-by-default** confirmation for everything not on the allowlist.
- Whether any live/provider/API/network step occurred.

---

## Source and collection summary

- Repo-local/static inputs used (list the planning docs and golden-quest references).
- External sources used — **only if** approved and scoped.
- Providers used — **only if** approved and scoped.
- Collected item counts — **only if** inventory data is actually part of the future PR.
- Skipped / blocked items.

---

## Safety and confidentiality checks

- **no** secrets,
- **no** personal data values,
- **no** auth / payment / site-affecting action unless separately approved and reported,
- **no** confidential business / client / person details in public issue/PR/docs,
- high-risk / do-not-demo candidates handled as out-of-demo.

---

## Output / diff summary

- Changed files (explicitly listed).
- Inventory files added/updated, if any.
- Quest metadata / fixtures / tests changed or **not changed**.
- For docs-only work: no unintended route URLs / selectors / screenshots / live facts.

---

## Validation summary

- Offline tests / checks run.
- Live tests run — **only if** explicitly approved and scoped.
- GitHub Actions status.
- Known limitations.

---

## Decision / merge recommendation

- Safe to merge / needs changes / block.
- Reviewer notes.
- Follow-up issue suggestions.

---

## Copy-paste Markdown template

Compact fenced block for the future real issue/PR:

```markdown
## Route Inventory Post-Action Report

### Header
- Parent issue: #862
- Scoped issue: <number>
- PR number: <number>
- Work mode selected: <exactly one from live-transition-decision-record.md §2>
- Base / head SHA: <base> / <head>
- Date / time: <window>
- Operator / report source: <human | local worker | script>

### Authorization & boundary
- Authorization checklist: completed | N/A (<reason>)
- Explicit user approval: <required | not required for this mode>
- Allowed hosts/providers used: <explicit allowlist>
- Deny-by-default: confirmed for everything else
- Live/provider/API/network step occurred: <yes | no>

### Source & collection
- Repo-local/static inputs: <listed>
- External sources used: <none | approved list>
- Providers used: <none | approved list>
- Collected item counts: <none | counts>
- Skipped/blocked items: <listed>

### Safety & confidentiality
- No secrets: confirmed
- No personal data values: confirmed
- No auth/payment/site-affecting action unless separately approved: confirmed
- No confidential business/client/person details in public docs: confirmed
- High-risk / do-not-demo candidates: <handled as out-of-demo>

### Output / diff
- Changed files: <listed>
- Inventory files added/updated: <none | listed>
- Quest metadata / fixtures / tests: not changed
- No unintended route URLs/selectors/screenshots/live facts: confirmed

### Validation
- Offline tests/checks: <run>
- Live tests: <none | approved+scoped>
- GitHub Actions: <status>
- Known limitations: <listed>

### Decision
- Recommendation: safe to merge | needs changes | block
- Reviewer notes: <notes>
- Follow-up issues: <suggestions>

Note: no live/provider/API/network by default; confidentiality boundary applies.
Planning docs alone do not authorize live work.
```
