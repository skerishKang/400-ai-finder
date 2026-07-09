# Official-Site Route Inventory First-Scope Selection Plan

A planning-only **first-scope selection plan** for the
[#862](https://github.com/skerishKang/400-ai-finder/issues/862) official-site
action navigator track. It selects candidate resident-task routes using
repository-local/static references only.

> **Planning only — NOT live/provider/API/network authorization.**
> This selection plan does **not** grant permission to run live network,
> provider, API, fetch, crawling, external navigation, Firecrawl, form
> submission, authentication, payment, or any site-affecting action. It does
> **not** collect a route inventory dataset, and it does **not** record or add
> new official-site facts or route URLs. Authorization for live/provider steps
> requires a separately scoped issue plus the gates in
> [`docs/live-transition-decision-record.md`](live-transition-decision-record.md).

---

## Planning-only warning

This PR and this selection plan must keep:

- **no** live browsing, crawling, fetch, provider/API, Firecrawl, or network execution
- **no** route inventory dataset rows collected or committed
- **no** new official-site facts or route URLs collected in this PR
- **no** confidential business / client / person details
- this selection plan **does not authorize live work** by itself

---

## Inputs used

All inputs are **repository-local / static docs**. No external source was consulted.

| Input | Used as |
|-------|---------|
| [`docs/official-site-route-inventory-plan.md`](official-site-route-inventory-plan.md) | Inventory goals, schema, classification rules |
| [`docs/official-site-route-inventory-prioritization-rubric.md`](official-site-route-inventory-prioritization-rubric.md) | Scoring dimensions and candidate buckets |
| [`docs/official-site-route-inventory-authorization-checklist.md`](official-site-route-inventory-authorization-checklist.md) | Pre-flight authorization gate |
| [`docs/scoped-route-inventory-issue-template.md`](scoped-route-inventory-issue-template.md) | Future scoped-issue structure |
| [`docs/official-site-route-inventory-workflow-index.md`](official-site-route-inventory-workflow-index.md) | Workflow order |
| [`docs/mvp-demo-milestone-snapshot.md`](mvp-demo-milestone-snapshot.md) | MVP closeout baseline |
| [`docs/mvp-golden-quest-fidelity-matrix.md`](mvp-golden-quest-fidelity-matrix.md) | Existing local/static golden quest references (read-only) |

**No external source consulted.** The existing golden-quest references in
`docs/mvp-golden-quest-fidelity-matrix.md` are used strictly as **read-only
inputs**; they were **not** changed, and no new route URLs or live facts were
derived from them in this PR.

---

## Candidate selection method

- Apply [`docs/official-site-route-inventory-prioritization-rubric.md`](official-site-route-inventory-prioritization-rubric.md) (score each dimension 0/1/2; high safety risk overrides high resident/demo value).
- Follow [`docs/scoped-route-inventory-issue-template.md`](scoped-route-inventory-issue-template.md) structure for any future issue this selection informs.
- Before any actual collection, a future work mode must be selected — **exactly one** from [`docs/live-transition-decision-record.md`](live-transition-decision-record.md) §2.
- If the mode is **unset**, the default is **local/static demo replay**.

---

## First-scope candidate table

Candidate labels are the **existing local/static golden quest labels** (read-only
inputs) plus generic resident-task candidates. No collected route URLs or live
facts are included.

| Candidate label | Resident-task value | Navigation / findability rationale | Safety risk | Bucket | Future work mode |
|-----------------|---------------------|------------------------------------|-------------|--------|------------------|
| `housing_department_lookup` (아파트 정보 안내) | High | Resident needs apartment-status info; path buried in LNB | Low | High-priority local/static candidate | Local/static stays |
| `bulky_waste_disposal_guidance` (대형폐기물 배출 안내) | High | Disposal method is non-obvious; external handoff likely | Low | High-priority local/static candidate | Local/static stays |
| `public_health_center_guidance` (보건소 위치·진료 안내) | High | Location/hours lookup is common; no auth needed | Low | High-priority local/static candidate | Local/static stays |
| `illegal_parking_report_guidance` (불법 주정차 신고 안내) | High | Report channel handoff needed; identity/photo/location involved | Medium (external handoff + personal-data-adjacent inputs) | Guidance-only / do-not-demo until provider-assisted scope | Provider/live opt-in only if later scoped |
| `move_in_report_guidance` (전입신고 안내) | High | Government24 handoff; identity/auth involved | Medium (auth + external handoff) | Guidance-only / do-not-demo until provider-assisted scope | Provider/live opt-in only if later scoped |
| generic: resident-task FAQ routing | Medium | Many resident questions lack a single clear path | Low | Guidance-only candidate | Local/static stays |

**Future work mode note:** the first four local/static candidates need no
provider/live step. The two report/handoff candidates (신고/전입) stay
**do-not-demo / unsafe** until a separately scoped, approved issue selects a
provider-assisted or controlled-live mode with an explicit allowlist.

---

## Exclusions / do-not-demo candidates

Excluded until a separately scoped, approved issue reclassifies them:

- any path requiring **authentication** (본인인증 / login),
- any path requiring **payment** (결제 / 수수료),
- any path requiring **personal data input** (주민번호 / 연락처 / 주소 값 / 차량번호 / 사진),
- any **site-affecting action** (form submission / filing / receipt / completion),
- any **whole-site cataloging** beyond resident-task-relevant routes,
- any newly discovered official-site fact or route URL not already present as a repo-local/static reference.

High safety risk overrides resident/demo value; uncertain items default to
**do-not-demo / unsafe candidate**.

---

## Future scoped issue outline

Copy-paste outline for the first real scoped issue (fill from the issue
template):

```
Title: ops: <scope> route inventory selection/collection (mode: <one mode>)

Parent issue: #862
Chosen work mode: <exactly one from live-transition-decision-record.md §2>
Explicit user approval: <required / not required for this mode>
Allowed hosts / providers: <explicit allowlist; deny-by-default otherwise>
Route families / candidate labels in scope: <named labels only>
Explicit out-of-scope items: <listed>

Checklist: complete docs/official-site-route-inventory-authorization-checklist.md
Prioritization: apply docs/official-site-route-inventory-prioritization-rubric.md
Safety: no secrets / no personal data values / no auth / no payment / no site-affecting action
Reporting: attach post-action report before inventory data PR merge

Note: planning docs alone do not authorize live work.
```

If an external step is requested, state **allowed hosts/providers** explicitly;
everything else is deny-by-default. A post-action report is required before any
future inventory data PR merge.

---

## Relationship to #862 and #873

- [#862](https://github.com/skerishKang/400-ai-finder/issues/862) remains the **parent** for official-site action navigator / route inventory planning.
- [#873](https://github.com/skerishKang/400-ai-finder/issues/873) is only for production / full-site rebuild escalation.

This selection plan does not authorize live work by itself; any future step
still requires the linked gates and a separately scoped, explicitly approved
issue.
