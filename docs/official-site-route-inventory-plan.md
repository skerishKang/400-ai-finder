# Official-Site Route Inventory Plan

> **Clone invariant:** 좌측 시민 사이트의 공식 페이지 clone은 [canonical invariant](product/exact-official-site-clone-invariant.md)를 따른다. 이 historical/planning 문서의 내용은 exact-clone 계약을 약화하지 않는다. Live retrieval이나 분석은 canonical fixture 기반 왼쪽 화면을 대체하지 않는다.

Planning artifact for future **route/content inventory** that would support the
[#862](https://github.com/skerishKang/400-ai-finder/issues/862) official-site
action navigator track.

> **Planning only.** This PR defines schema and process. It does **not** collect
> inventory data, browse or crawl any site, call providers/APIs, or authorize
> live work. Future collection needs a separate scoped issue and must pass
> [`docs/live-transition-decision-record.md`](live-transition-decision-record.md).

---

## 1. Scope and mode

| Item | Value |
|------|--------|
| Parent track | [#862](https://github.com/skerishKang/400-ai-finder/issues/862) official-site action navigator and live integration |
| Document type | Planning artifact (schema + classification + report template) |
| Work mode for this PR | **local/static demo replay** |
| Live execution in this PR | **None** |

**Future inventory collection** may later use mode
**provider-assisted reference / inventory**, but only after:

1. a separately scoped issue is opened, and  
2. gates in [`docs/live-transition-decision-record.md`](live-transition-decision-record.md) are satisfied.

This document is **not**:

- a whole-site production rebuild plan ([#873](https://github.com/skerishKang/400-ai-finder/issues/873) only if inventory findings later force that path),
- an inventory dataset,
- live-work authorization.

The existing **five golden quests stay local/static and locked**. Inventory
planning must not silently expand or rewrite them.

---

## 2. Inventory goals

Future route/content inventory should capture enough structure for official-site
action navigator work, while staying **resident-task-relevant**.

| Goal | Detail |
|------|--------|
| Navigator readiness | Record routes and content shapes needed to plan action-navigator behavior |
| Resident-task focus | Prefer paths tied to resident tasks (안내, 신고 경로 안내, 위치·절차 안내) over whole-site cataloging |
| Not full rebuild | Do **not** invent a production full-site map or CMS migration plan here |
| Preserve MVP boundary | Keep the five locked golden quests as **local/static**; inventory does not unlock live demo by default |
| Decision support | Use collected records later to judge **demo eligibility**, **external handoff**, and **site-affecting risk** |

How to rank and select candidate routes is defined separately in
[`docs/official-site-route-inventory-prioritization-rubric.md`](official-site-route-inventory-prioritization-rubric.md).

**Illustrative only (already locked in MVP docs — not newly verified here):**

The fidelity matrix already names five primary paths such as
`북구청 홈 > 분야별정보 > 건축 > 아파트정보 > 아파트현황` and related handoff
guidance. Treat those as **existing local/static contracts**, not as freshly
collected inventory rows and not as license to invent additional route facts.

---

## 3. Inventory record schema

Schema for **future** inventory records only. Do **not** fill real `route_url`
values or other collected facts in this document.

| Field | Meaning |
|-------|---------|
| `inventory_id` | Stable unique id for one inventory record (stable across revisions). |
| `source_site` | Logical site label (e.g. Buk-gu official site profile id), not a secret. |
| `route_url` | Canonical public path or URL for the route (filled only after approved collection). |
| `route_title` | Visible page title or primary heading used by residents. |
| `breadcrumb` | Human-readable breadcrumb / official path string when known. |
| `primary_menu` | Top-level menu family (e.g. 분야별정보, 종합민원, 보건소). |
| `secondary_menu` | Secondary LNB / sub-menu item when applicable. |
| `resident_task` | Resident task this route primarily supports (short Korean/English label). |
| `content_summary` | Short non-confidential summary of what the page is for. |
| `required_user_inputs` | Inputs the real flow would ask for (types only; never store personal values). |
| `external_handoff_target` | External service the path may hand off to (name/role only; e.g. Government24 guidance). |
| `site_affecting_actions` | Actions that would change external state (submit, pay, authenticate, file, etc.). |
| `auth_required` | Whether authentication is required for the real official path (`yes` / `no` / `unknown`). |
| `payment_required` | Whether payment is required (`yes` / `no` / `unknown`). |
| `personal_data_required` | Whether personal data is required to complete the real path (`yes` / `no` / `unknown`). |
| `safe_demo_mode` | How a demo may safely represent this route (`local_static` / `guidance_only` / `do_not_demo` / …). |
| `allowed_future_work_mode` | Highest work mode allowed next for this record (see §4). |
| `evidence_reference` | Pointer to approved evidence artifact or doc section (never paste secrets). |
| `last_verified_at` | ISO date when the record was last verified under an approved collection issue. |
| `notes` | Free-form non-confidential notes (risks, open questions, exclusions). |

**Schema rules:**

- Empty/planned records are fine; fabricated “verified” URLs are not.
- Prefer public path shapes and labels over scraping raw HTML into the repo.
- Personal identifiers, credentials, payment data, and confidential client/business details must never appear in inventory values.

---

## 4. Classification rules

Assign each future inventory record one primary category. Categories map to
allowed next steps; they do not authorize execution by themselves.

| Category | When to use | Allowed next step | Stop condition |
|----------|-------------|-------------------|----------------|
| **local/static candidate** | Route can be represented with local/static fixtures and guidance only | Keep or refine local/static demo under existing MVP gates | Any need for live network or site-affecting action |
| **provider-assisted reference candidate** | Structured reference/inventory would help, still no operational submit | Open scoped issue under provider-assisted mode + decision-record gates | Uncontrolled crawl, secret use, or out-of-allowlist host |
| **controlled live validation candidate** | Bounded live check is needed to confirm a public path fact | Opt-in controlled live issue with allowlist, report, rollback | Expand beyond named routes/hosts or skip reporting |
| **operational integration candidate** | Real operational systems must be integrated for the navigator path | High-bar operational integration issue with explicit approval | Auth/submit/pay without separate approval |
| **production rebuild candidate** | Findings imply full-site rebuild / deploy / repo decisions | Defer to [#873](https://github.com/skerishKang/400-ai-finder/issues/873) planning track | Treating rebuild as silent scope inside #862 inventory work |
| **do-not-demo / unsafe candidate** | Personal data, auth, payment, or site-affecting risk cannot be made demo-safe | Document as out-of-demo; do not add golden quest or live demo path | Any attempt to demo submit/auth/pay/personal-data capture |

Default when unsure: **do-not-demo / unsafe candidate** until reclassified under an
approved issue.

See [`docs/official-site-route-inventory-prioritization-rubric.md`](official-site-route-inventory-prioritization-rubric.md)
for the scoring dimensions and bucket assignment that feed this classification.

---

## 5. Safety and confidentiality boundary

This PR and any use of this plan as **planning-only** must keep:

- **no** live / provider / API / fetch / network execution in this PR
- **no** external request / navigation
- **no** crawling
- **no** form submission / authentication / payment / site-affecting action
- **no** personal data capture
- **no** confidential business / client / person details
- **no** new golden quest
- **no** quest metadata changes
- **no** new inventory dataset rows collected from a live run

CI and default local tests remain offline-capable. Live collection never becomes
the default path.

---

## 6. Relationship to existing docs/issues

| Link | Role |
|------|------|
| [`docs/live-transition-decision-record.md`](live-transition-decision-record.md) | Governs **any** future live / provider / API / network step |
| [`docs/mvp-demo-milestone-snapshot.md`](mvp-demo-milestone-snapshot.md) | Records completed local/static MVP closeout baseline |
| [`docs/mvp-golden-quest-fidelity-matrix.md`](mvp-golden-quest-fidelity-matrix.md) | Locks the five golden quests; inventory must not regress them |
| [#862](https://github.com/skerishKang/400-ai-finder/issues/862) | **Primary parent track** — official-site action navigator and live integration |
| [#873](https://github.com/skerishKang/400-ai-finder/issues/873) | Applies **only** when inventory findings imply production / full-site rebuild decisions |
| [`docs/official-site-route-inventory-authorization-checklist.md`](official-site-route-inventory-authorization-checklist.md) | Pre-flight authorization checklist to confirm **before** any future inventory collection |
| [`docs/official-site-route-inventory-prioritization-rubric.md`](official-site-route-inventory-prioritization-rubric.md) | Scoring dimensions and candidate buckets for prioritizing future inventory |
| [`docs/scoped-route-inventory-issue-template.md`](scoped-route-inventory-issue-template.md) | Template for opening a scoped future inventory issue under #862 |
| [`docs/official-site-route-inventory-workflow-index.md`](official-site-route-inventory-workflow-index.md) | Planning-only index tying together the route inventory planning docs and workflow order |
| [`docs/official-site-route-inventory-first-local-static-records.md`](official-site-route-inventory-first-local-static-records.md) | First local/static seed records — local/static placeholders; route URLs were not collected |

**Summary:**

- Plan inventory under **#862**.
- Escalate rebuild/repo/deploy questions to **#873** when classification is
  `production rebuild candidate`.
- Never skip the live-transition decision record for provider or live modes.

---

## 7. Future collection report format

Template for a **future** controlled inventory collection issue/report.
**This template is not used in this PR; no collection is performed here.**

| Field | Fill with |
|-------|-----------|
| Issue number | GitHub issue that authorized the collection |
| Chosen work mode | From live-transition decision record modes |
| Allowed hosts / providers | Explicit allowlist only |
| Operator / tool / script | Who ran what (human, script name, version) |
| Started / ended time | Collection window |
| Routes collected | List of `inventory_id` / path labels collected in this run |
| Requests / clicks / calls summary | Hosts and purpose counts — no confidential payloads |
| Redactions / confidentiality check | Confirmation that secrets and personal/client details were excluded |
| Artifacts produced | Paths to redacted artifacts (if any) |
| Stop / rollback condition | When collection stopped and how live paths were disabled |

**After any future collection:** report must be attached to the authorizing issue
before merge of inventory data. Unreported live collection is out of process.

Before opening such a collection issue/PR, also complete
[`docs/official-site-route-inventory-authorization-checklist.md`](official-site-route-inventory-authorization-checklist.md)
and use
[`docs/scoped-route-inventory-issue-template.md`](scoped-route-inventory-issue-template.md)
to structure the scoped issue. See the
[`docs/official-site-route-inventory-workflow-index.md`](official-site-route-inventory-workflow-index.md)
for the full planning workflow order.

---

## Non-goals for this PR

- Implement navigator code or crawl tooling  
- Collect or commit route inventory datasets  
- Change quest metadata, tests, or golden quest set  
- Authorize live work by document existence alone  
