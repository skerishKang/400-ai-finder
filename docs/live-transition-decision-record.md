# Live Transition Decision Record

Decision gate between the completed **local/static MVP demo closeout** and any
future live / provider-assisted / operational / production work.

> **This document is not live-work authorization.**  
> Recording a decision here (or linking this file) does **not** approve live
> provider calls, network fetch, crawling, external navigation, Firecrawl, API
> usage, form submission, authentication, payment, site-affecting actions, or
> production deployment. Those require a separately scoped issue plus explicit
> approval where required below.

---

## 1. Current state

| Item | Status |
|------|--------|
| Local/static MVP demo milestone | **Complete** (stakeholder-review surface) |
| Golden quests | Remain **local/static** and **locked** (five quests) |
| README discoverability | MVP demo docs are exposed under `### MVP demo docs` |

**Entry docs:**

- [`docs/mvp-demo-milestone-snapshot.md`](mvp-demo-milestone-snapshot.md) — one-page closeout
- [`docs/mvp-demo-operator-runbook.md`](mvp-demo-operator-runbook.md) — run / verify / present
- [`docs/mvp-golden-quest-fidelity-matrix.md`](mvp-golden-quest-fidelity-matrix.md) — fidelity contract

The current demo is **not** a production rebuild and **not** a live official-site
integration. Default CI and local tests must continue to pass **without** live
network.

---

## 2. Decision needed before live work

Before any live/provider/API/network work starts, record answers to at least:

| Decision | What to record |
|----------|----------------|
| Repository role | Does this repo remain **MVP/demo only**, or will production work live here? |
| Production rebuild home | Does full production rebuild stay in this repo, or move to a **separate repo**? |
| Work mode | Which mode is in use for the next issue/PR? (choose one; do not mix silently) |
| Explicit user approval | Is **explicit user approval** required before live/API/network execution? |
| External-request authority | Who/what is allowed to make external requests (human operator, named script, CI job, never-by-default)? |
| Post-action report | What must be reported after any controlled live action? |

**Work modes (pick exactly one per issue):**

1. **local/static demo replay** — no live network (default; current MVP)
2. **provider-assisted reference / inventory** — limited, allowlisted reference collection
3. **controlled live-dependent experiment** — opt-in live path with stop conditions
4. **operational integration** — integration against real operational systems (high bar)
5. **full production rebuild** — product/repo/deploy rebuild track (high bar)

Unset mode defaults to **local/static demo replay**. Live modes never become the
default for CI or unattended runs.

---

## 3. Transition gates before any live-dependent PR

A live-dependent PR (or issue that enables live work) must clear **all** of the
following gates before merge/execution:

| Gate | Requirement |
|------|-------------|
| Explicit issue scope | Named issue with purpose, in/out of scope, and chosen work mode |
| Public / confidentiality boundary | No confidential business / client / person details in public docs, issues, PRs, logs, fixtures |
| Allowed host / provider list | Explicit allowlist; everything else is deny-by-default |
| No secret leakage | No secrets in repo, logs, artifacts, screenshots, or PR text |
| No uncontrolled crawling | No open-ended crawl; inventory/collection is bounded and listed |
| No site-affecting action | No form submission / authentication / payment / receipt / completion unless **separately** approved and scoped |
| Rollback plan | How to stop, disable, or revert the live path |
| Test plan split | Local/static tests remain default; live-only validation is opt-in and separate |
| Report format | What was fetched / clicked / called (host, method/purpose, time, outcome) — without confidential payloads |
| CI / local default | Confirm CI and default local tests **do not require live network** |

If any gate is missing, treat the work as **blocked** — do not execute live
paths “just to explore.”

---

## 4. Relationship to broad epics

This decision record sits **between** local/static MVP closeout and the remaining
broad tracks.

| Epic | Track summary |
|------|----------------|
| [#862](https://github.com/skerishKang/400-ai-finder/issues/862) | Official-site action navigator and **live integration** track — route/content inventory, controlled live integration path |
| [#873](https://github.com/skerishKang/400-ai-finder/issues/873) | Full Buk-gu website **rebuild planning** and integration track — repository / deployment / security / operations decisions |

**How to use this gate:**

- #862-style work (navigator, inventory, controlled live integration) must pass §2–§3 first.
- #873-style work (rebuild, production repo/deploy, operations) must pass §2–§3 first, especially repository role and production-home decisions.
- Completing local/static MVP docs **does not** open either epic for unattended live execution.

---

## 5. Explicit non-goals for this document

This file does **not**:

- authorize or perform live provider / fetch / network execution
- authorize Firecrawl, API keys, or external API calls
- authorize crawling or external navigation
- change source code or quest metadata
- add a new golden quest
- make a production deployment decision
- include confidential business / client / person details
- grant live-work authorization by existence alone

Implementation plans, allowlists, and execution reports belong in **separate
scoped issues**, not as silent expansion of this gate document.

---

## 6. Recommended next-track issue templates

Short templates only. Each issue must still satisfy §2–§3 before any live step.

### A. Route / content inventory planning

**Title example:** `plan: Buk-gu route/content inventory (no live crawl yet)`

**Required fields:** scope · mode · allowed hosts/providers · explicit approval requirement · no-secret / no-confidentiality check · validation/reporting plan · rollback/stop condition

### B. Provider-assisted reference collection

**Title example:** `ops: provider-assisted reference collection for allowlisted hosts`

**Required fields:** scope · mode · allowed hosts/providers · explicit approval requirement · no-secret / no-confidentiality check · validation/reporting plan · rollback/stop condition

### C. Controlled live validation

**Title example:** `ops: controlled live validation for <named path> (opt-in only)`

**Required fields:** scope · mode · allowed hosts/providers · explicit approval requirement · no-secret / no-confidentiality check · validation/reporting plan · rollback/stop condition

### D. Production repo / deployment decision

**Title example:** `decision: production rebuild stays in-repo vs separate repo`

**Required fields:** scope · mode · allowed hosts/providers · explicit approval requirement · no-secret / no-confidentiality check · validation/reporting plan · rollback/stop condition

---

## How to cite this record

When opening a live-adjacent issue or PR, link this document and state:

1. chosen **work mode**,
2. gates from §3 that are satisfied (or still open),
3. that **this file alone is not authorization** to run live/network steps.
