# Municipality AI Finder Onboarding Playbook (#1329 Stage B)

- status: Stage B candidate
- audited current main: `a1d0841e9dda3cf7e4d0179785355ef6ee3d04c6`
- evidence family: Buk-gu protected golden + Seo-gu accepted AI-on-clone proof
- parent: #1232
- input reference: `docs/product/bukgu-ai-mvp-reference-spec.md` (Stage A audit artifact; historical audited base, revalidated here against current main where used)
- final two-municipality acceptance evidence: #1328, #1339
- implementation slices: PR #1332 / #1334 / #1336 / #1338
- current full main-push proof: MVP Contract Checks run #776 / `32023796558` = SUCCESS
- current model-only proof: General Model Fallback Contract main-push #3 / `32023796557` = SUCCESS

This document converts the first two municipal implementations into an operational onboarding method. It is not permission to clone the Buk-gu route IDs into every institution, and it is not a claim that two municipalities prove arbitrary websites.

## 0. Non-claims and authority rules

The accepted evidence supports a **municipality-family onboarding pattern**. It does not establish:

- arbitrary-site or cross-domain completion;
- actual public-site control, login, submission, payment, upload, or write automation;
- Production/resident-default promotion for Seo-gu;
- arbitrary Seo-gu clone-grounded question coverage beyond declared journey data;
- a measured 70–80% automation result on a third institution;
- live-provider availability in routine CI.

Current repository code/tests on the audited SHA outrank historical issue prose. Buk-gu golden identities remain compatibility constraints; Seo-gu exposed several Buk-gu-only assumptions that were generalized without replacing the Buk-gu golden runtime.

# 1. What the two-municipality proof established

The accepted product shape is:

```text
LEFT  = repository-controlled institution clone
RIGHT = AI conversation / answer / bounded navigation / evidence / explicit model-only fallback
```

The reusable lesson is not “make every site look like Buk-gu.” The reusable lesson is:

```text
institution identity
 -> bounded source/reference capture
 -> route/content/asset inventory
 -> faithful clone model
 -> clone rendering
 -> source-vs-clone QA
 -> site surface registration
 -> capability/journey data
 -> bounded local navigation/action
 -> post-navigation visible-text READ
 -> grounded answer with repository-clone provenance
 -> explicit resident-opt-in model-only fallback when clone evidence is absent
 -> deterministic/offline CI
 -> direct product/visual review
 -> versioned candidate / rollback / exception queue
```

Buk-gu and Seo-gu do not share the same route vocabulary. They share the **contract around how a route/capability becomes evidence and how evidence becomes a resident answer**.

# 2. Canonical onboarding pipeline

Every later municipality must pass the following stages. A worker must not skip forward because a later-stage artifact can be hand-authored quickly.

| Stage | Required input | Required output | Primary current owners / examples | Gate |
|---|---|---|---|---|
| 0. Identity intake | institution id, source URL/domain, scope | canonical `site_id`, allowlist, source scope | `configs/sites/*`, `src/site_profiles/*`, `functions/api/mvp/site_runtime.js` | unknown/malformed identity fails closed |
| 1. Bounded source capture | approved site scope | reproducible capture/reference plan | `configs/reference-plans/*`, official-clone capture contracts | GET/read only; no login/submit/payment/PII mutation |
| 2. Route/content/asset inventory | captured evidence | route/state/content/asset inventory | site reference plan + clone fixture/model artifacts | unsupported/unresolved items explicit |
| 3. Faithful Site Model | inventory + source evidence | deterministic model | `src/official_clone/reference_clone_model.py` | no fabricated state/asset/content |
| 4. Visual/provenance contract | source measurements/assets | evidence-bound visual contract and asset identity | `src/official_clone/visual_contract.py`, site-specific visual artifacts | every promoted visual claim traceable |
| 5. Clone render | Site Model + visual contract | local repository clone | `src/official_clone/reference_clone_renderer.py` or approved compatibility renderer | no actual-site runtime dependency |
| 6. Source-vs-clone QA | source reference + rendered clone | route/content/asset/a11y/responsive/visual evidence | site-specific renderer/browser contracts | direct fidelity review before promotion |
| 7. Surface registration | accepted clone | site config: clone root, readable root, allowed routes | `src/web/static/municipal-site-surface-registry.js` | data/config ownership; unknown site fails closed |
| 8. Resident capability/journey data | observed resident needs + route inventory | minimum deterministic journey registry | `src/web/static/municipal-resident-journey-registry.js` | questions/routes/markers in config, not shared-core site branches |
| 9. Bounded action + READ | registered clone + journey | same-origin route transition/action + visible-text evidence | `municipal-clone-surface.js`, `municipal-resident-journey.js` | allowlisted routes only; no query/hash/cross-origin; bounded visible text |
| 10. Grounded chat answer | READ evidence | answer + `repository_clone/clone_dom/route` provenance | `municipal-ai-shell.js` | answer must fail closed if required evidence is missing |
| 11. Site-miss model path | unmatched question + explicit user choice | model-only answer or honest failure | `/api/mvp/general`, `CitizenMvpBridge.askGeneralModel()` | never automatic; no clone/official provenance; no web-search tools |
| 12. Automated evidence | exact candidate SHA | contract/browser/CI evidence | `tests/`, `.github/workflows/`, MVP Contract Checks | routine provider/official-site network = 0 |
| 13. Product review | accepted candidate/preview | desktop/mobile visual + interaction acceptance | issue/PR evidence + screenshots | CI GREEN alone is insufficient |
| 14. Promotion/rollback | accepted evidence | versioned candidate/default decision/rollback identity | release/promotion docs and build outputs | no Production/default promotion by implication |

## 2.1 Mandatory sequencing

Do not begin AI journey work before the clone/reference surface is accepted enough to support the scoped journey. Do not treat navigation as READ. Do not treat a model answer as site evidence. Do not mark a new site “supported” merely because its id appears in a registry.

# 3. Municipal capability vocabulary from observed evidence

This vocabulary is evidence-derived. `BOTH` means observed in both municipality tracks. `BUKGU` or `SEOGU` means observed in that track only and therefore a **candidate family capability**, not yet proven universal.

| Capability family | Evidence scope | Current evidence | Onboarding treatment |
|---|---|---|---|
| homepage / entry surface | BOTH | Buk-gu golden home; Seo-gu clone home/mobile home | standard inventory item |
| global/local navigation | BOTH | Buk-gu frozen route/target graph; Seo-gu GNB/local routes | model as route/capability data, not shared raw site branches |
| resident AI conversation pane | BOTH product pattern | Buk-gu legacy resident shell; Seo-gu generic municipal shell | reuse interaction/trust-boundary pattern; preserve Buk-gu compatibility |
| bounded local route transition | BOTH | Buk-gu frozen choreography; Seo-gu allowlisted clone navigation | route ids remain site data |
| notice / announcement list-detail | SEOGU | `notice/` -> `notice/detail/` accepted journey | candidate reusable board capability |
| official notice / gosi list-detail | SEOGU | `gosi/` -> `gosi/detail/` clone routes | candidate reusable board capability |
| civil form list-detail | SEOGU | `civil-form/` -> `civil-form/detail/` | candidate reusable forms capability |
| organization chart | SEOGU | `organization/`; accepted grounded journey | candidate municipal organization capability |
| staff/contact directory | SEOGU | `staff/` clone route | candidate directory capability; privacy/scraping scope still applies |
| complaint/proposal guidance | BUKGU | frozen complaint/mayor routes and no-submit choreography | candidate municipal civic-action capability; high-risk boundary |
| bulky-waste guidance | BUKGU | frozen route + snapshot-backed guidance | candidate service-guidance capability |
| passport guidance | BUKGU | frozen route + snapshot-backed guidance | candidate service-guidance capability |
| unmanned kiosk guidance | BUKGU | frozen route + snapshot-backed guidance | candidate service-guidance capability |
| apartment/housing guidance | BUKGU | frozen apartment routes/targets | candidate resident-service capability |
| post-navigation DOM READ -> answer | SEOGU accepted pattern | `notice/detail/` and `organization/` grounded flows | preferred new-onboarding evidence path; Buk-gu legacy quests remain compatibility-only |
| explicit general-model fallback | shared new contract | `/api/mvp/general`; resident opt-in; non-clone provenance | reusable across known sites subject to provider/runtime policy |

Do not add a capability because municipal sites “usually have it.” Add it only when source/reference evidence shows it and the scoped product needs it.

# 4. Difference ownership model

A later institution must put differences in the narrowest correct ownership layer.

| Difference class | Belongs in | Examples | Must not become |
|---|---|---|---|
| institution identity/domain | SiteSpec/site profile/central site runtime registry | `site_id`, host allowlist, clone root | scattered `if site_id == ...` logic |
| route/capability vocabulary | site model / surface registry / action config | Seo-gu allowed routes; Buk-gu frozen route ids | hardcoded routes in generic orchestrator |
| question/journey phrases | journey data/config | Seo-gu two accepted exact questions | duplicated site-specific shell implementation |
| evidence markers | journey data/config | `사회연대경제`, organization markers | prewritten factual answer in config |
| content/knowledge | captured fixture/model/snapshot/READ evidence | clone DOM visible text; Buk-gu compatibility snapshots | AI-generated substitute for source facts |
| visual theme/assets | site visual contract/theme/assets | source-backed CSS measurements/assets | arbitrary shared-core styling fork |
| parser/source quirks | parser profile or reviewed generic parser improvement | host/DOM differences | hidden site branch in generic renderer |
| action graph differences | route/target/action data | local detail activation vs guidance terminal | second AI engine |
| unavoidable special behavior | explicit reviewed override | only after generic representation is proven insufficient | silent exception |
| unsupported feature | exception queue | actual-site login/submit/payment/write | fake “automation” |

## 4.1 Raw site-id branch rule

Current-main direct audit of the new shared orchestration found **0 `seogu_gwangju` literals** in:

- `src/web/static/municipal-ai-shell.js`
- `src/web/static/municipal-clone-surface.js`
- `src/web/static/municipal-resident-journey.js`
- `functions/api/mvp/general.js`

Site ids are intentionally enumerated in central registries such as `functions/api/mvp/site_runtime.js`, `municipal-site-surface-registry.js`, and `municipal-resident-journey-registry.js`.

For a later site, a new raw site-id branch in generic shell/READ/orchestration/provider code is a **presumptive design failure**. The worker must stop and justify why config/data cannot represent the difference.

# 5. Buk-gu <-> Seo-gu transfer matrix

| Dimension | Buk-gu reference | Seo-gu accepted proof | Classification | Rule for next municipality |
|---|---|---|---|---|
| clone structure | protected designed/golden resident canvas plus fixture/provenance contracts | source-backed generic reference clone under `/seogu/` | `SITE_SPECIFIC_DATA_CONFIG` + shared clone contracts | preserve source-recognizable clone; do not copy Buk-gu DOM/routes |
| clone renderer | Buk-gu compatibility renderer remains protected | generic `reference_clone_renderer.py` path used for Seo-gu reference proof | `REUSED_UNCHANGED` for generic renderer mechanism | prefer model-driven generic renderer; reviewed compatibility renderer only where existing golden requires it |
| site identity | legacy Buk-gu default | Seo-gu recognized centrally; old Buk-gu runtime cannot be entered silently | `GENERALIZED_AFTER_SECOND_SITE` | explicit/validated identity; unknown fails closed |
| left-clone/right-AI surface | Buk-gu legacy shell | generic municipal split shell | `GENERALIZED_AFTER_SECOND_SITE` | new municipalities use shared shell/config, not copied site shell |
| navigation | 17 frozen Buk-gu route ids / 28 client target ids | site-config allowlisted clone routes | `GENERALIZED_AFTER_SECOND_SITE` | capability semantics shared; ids/paths remain site data |
| board/detail action | not the core Buk-gu golden pattern | captured detail activation under strict same-origin guards | `GENERALIZED_AFTER_SECOND_SITE` | action must prove exact expected local route |
| READ/evidence | Buk-gu golden answers are pre-resolved before choreography | post-navigation visible-text `main.rc-main` READ | `GENERALIZED_AFTER_SECOND_SITE` | for new journey claims, prefer explicit evidence-to-answer coupling; do not rewrite Buk-gu golden merely for symmetry |
| AI question routing | Buk-gu quest/router compatibility path | site-keyed exact journey registry for declared Seo-gu proof | `GENERALIZED_AFTER_SECOND_SITE` | site question vocabulary belongs in data/config; shared orchestration stays site-neutral |
| grounded answer | snapshot/quest-backed Buk-gu compatibility answer | answer derived from final clone READ excerpt | `GENERALIZED_AFTER_SECOND_SITE` | provenance must identify evidence class and route |
| model fallback | Stage A recorded product-level gap | explicit resident opt-in `/api/mvp/general` with `general_model/none` provenance | `GENERALIZED_AFTER_SECOND_SITE` | never automatic; never masquerade as institution evidence |
| privacy/no-submit | protected Buk-gu safety boundary | retained for Seo-gu; no actual-site control | `REUSED_UNCHANGED` | high-risk actions stay fail-closed/handoff-only until separately authorized |
| external network in routine CI | zero live provider/actual-site control | zero; deterministic mock/function/browser proof | `REUSED_UNCHANGED` | loopback/offline only in routine CI |
| desktop/mobile | Buk-gu golden responsive contracts | generic shell desktop + 390x844 Gate C sanity | `GENERALIZED_AFTER_SECOND_SITE` | both must be reviewed; no unusable horizontal overflow |
| visual acceptance | Buk-gu protected golden review | Seo-gu direct preview review #1339 | `REUSED_UNCHANGED` governance pattern | product review required after CI |
| deployment/entrypoint | `/` remains protected Buk-gu primary | Seo-gu proof uses generic shell + site id; no resident-default promotion | `REVIEWED_OVERRIDE` / current product state | do not change default/Production as a side effect of onboarding |
| arbitrary-question grounded coverage | limited golden scope | exactly declared 2 grounded goldens | `UNSUPPORTED_EXCEPTION` | publish supported journey/capability scope; do not imply general site QA coverage |
| cross-domain generality | not proven | not proven | `UNSUPPORTED_EXCEPTION` | remains under #1232 |

## 5.1 Important runtime distinction

`functions/api/mvp/site_runtime.js` still marks `bukgu_gwangju` as `configured` and `seogu_gwangju` as `recognized_unconfigured` for the legacy `/api/mvp/ask` runtime dispatch seam. This is intentional: explicit Seo-gu requests must never fall through to Buk-gu logic.

Seo-gu's accepted clone-grounded resident journeys use the **generic municipal shell + surface registry + journey registry + bounded READ path**, not a duplicated Seo-gu legacy router. Do not flip the legacy runtime status merely to make terminology look symmetric.

# 6. Shared-core inventory learned from Slices A-D

These are the load-bearing shared changes that enabled the second municipality.

## Slice A — site identity / fail-closed dispatch (PR #1332)

- `functions/api/mvp/ask.js`
- `functions/api/mvp/request-safety.js`
- `functions/api/mvp/site_runtime.js`
- `src/llm/site_aware_mvp_dispatch.py`
- `src/web/mobile_demo.py`
- `tests/functions/test_site_runtime_contract.mjs`
- `tests/test_site_aware_mvp_dispatch.py`

Lesson: establish one identity resolver before adding second-site product behavior. Omitted legacy calls may keep the protected default; explicit unknown/malformed identities must not fall back to it.

## Slice B — generic clone surface / bounded READ (PR #1334)

- `src/web/static/citizen-mvp-bridge.js`
- `src/web/static/municipal-ai-shell.css`
- `src/web/static/municipal-ai-shell.html`
- `src/web/static/municipal-ai-shell.js`
- `src/web/static/municipal-clone-surface.js`
- `src/web/static/municipal-site-surface-registry.js`
- `tests/browser/municipal_ai_shell_contract.mjs`
- `tests/browser/verify_housing_quest_e2e.mjs`

Lesson: keep the clone renderer independent. The AI surface selects a repository clone and reads only configured same-origin resident-visible content.

## Slice C — journey data / evidence-derived answer (PR #1336)

- `src/web/static/municipal-resident-journey-registry.js`
- `src/web/static/municipal-resident-journey.js`
- shared shell/surface files above
- `tests/browser/municipal_ai_shell_contract.mjs`
- `tests/browser/verify_housing_quest_e2e.mjs`

Lesson: site-specific questions/routes/markers belong in the registry. The final factual answer must not be stored there; it is derived from final READ evidence.

## Slice D — explicit model-only trust boundary (PR #1338)

- `.github/workflows/general-model-fallback.yml`
- `functions/api/mvp/general.js`
- `src/web/static/citizen-mvp-bridge.js`
- `src/web/static/municipal-ai-shell.css`
- `src/web/static/municipal-ai-shell.js`
- `tests/browser/municipal_ai_shell_contract.mjs`
- `tests/functions/test_general_model_fallback_contract.mjs`

Lesson: a site miss is not permission to silently call a model. The resident explicitly opts in; successful responses are structurally non-grounded (`source_kind=general_model`, `evidence_kind=none`, `answer_scope=general_model`, empty site sources/search queries).

# 7. Safety and trust-boundary requirements

Every municipality onboarding must preserve these invariants.

## 7.1 Actual-site boundary

Routine runtime proof is against repository-controlled clones. No actual-site:

- login;
- POST/submit;
- payment;
- file upload;
- write/update/delete;
- resident identity entry;
- automated PII submission.

An eventual first-party integration is a separate authorization and contract.

## 7.2 Clone READ boundary

`municipal-clone-surface.js` demonstrates the required shape:

- same origin only;
- path must stay under configured clone root;
- route must be allowlisted;
- query/hash/backslash/path traversal rejected;
- configured semantic read root only;
- `innerText`/resident-visible text, not arbitrary DOM serialization;
- bounded evidence length;
- captured detail activation requires one exact local link and exact expected route.

## 7.3 Grounded vs model-only provenance

Grounded clone answer:

```text
grounded=true
source_kind=repository_clone
evidence_kind=clone_dom
route=<accepted local route>
```

Model-only answer:

```text
grounded=false
source_kind=general_model
evidence_kind=none
answer_scope=general_model
sources=[]
search_queries=[]
action=none
```

A model-only failure must not receive a successful provenance label.

## 7.4 PII precision

Do not claim “no PII anywhere.” The guided action contract avoids dedicated identity collection, but free-text questions can contain incidental PII. Request privacy gates must remain active, and any logging/persistence path must be audited separately before a resident-default deployment.

# 8. Automation, review, and exception metrics

The #1232 target of 70–80% automation is a **target to measure on later onboarding**, not an achieved result from Buk-gu + Seo-gu.

A later onboarding must define a denominator before implementation. The recommended unit is an **inventory capability unit**: one source-observed route/state/capability that the scoped product intends to support. Every unit receives exactly one final outcome.

## 8.1 Required outcome classes

- `AUTO_PRODUCED` — generated/mapped by existing pipeline without institution-specific code; automated QA passes.
- `REVIEWED_OVERRIDE` — bounded explicit institution-specific config/profile/override accepted by review.
- `HUMAN_REVIEW_REQUIRED` — pipeline produced a candidate but fidelity/product approval remains human-owned.
- `UNSUPPORTED_EXCEPTION` — intentionally not supported; fail-closed/exception queue.
- `UNRESOLVED` — evidence insufficient; cannot be counted as successful automation.

## 8.2 Ratios

For final classified capability units (excluding `UNRESOLVED` from “completed” denominators but reporting it separately):

```text
auto_ratio = AUTO_PRODUCED / final_classified_units
reviewed_override_ratio = REVIEWED_OVERRIDE / final_classified_units
human_review_ratio = HUMAN_REVIEW_REQUIRED / final_classified_units
unsupported_ratio = UNSUPPORTED_EXCEPTION / final_classified_units
```

The report must also include:

```text
unresolved_count
unresolved_asset_count
shared_core_changed = yes|no
shared_core_files = [...]
institution_specific_code_introduced = yes|no
raw_site_id_branches_added = <count>
routine_external_network_calls = <count>
```

Never move hard cases into an unreported bucket to improve the automation percentage.

## 8.3 Current two-municipality bounded metrics

Accepted #1339 evidence recorded:

- Seo-gu declared clone-grounded goldens: **2/2 deterministic E2E PASS**;
- explicit model-only proof: **1/1 deterministic mocked function/browser PASS**;
- routine external provider/official-site network calls: **0**;
- product-runtime site-specific reviewed overrides in the new shared orchestration: **0**;
- test-only reviewed override class: **1** (exact script-disabled sandbox diagnostic allowlist for exercised local Seo-gu routes);
- raw `seogu_gwangju` literals in the audited generic shell/READ/journey/general-model runtime files: **0**;
- arbitrary Seo-gu grounded question coverage: **not claimed**.

These are acceptance metrics for the second-site proof, not an automation ratio for a third site.

# 9. Required evidence package for a later municipality

A worker must report the following before acceptance.

## 9.1 Intake / source evidence

```text
site_id
source_domain
scope_boundary
capture/reference identity
source freshness date
route/state inventory count
asset inventory count
unsupported/unresolved source items
```

## 9.2 Clone evidence

```text
clone model identity
visual contract identity
rendered routes/states
source-vs-clone content/route/asset/a11y/responsive results
external requests observed
visual/product reviewer decision
rollback/candidate identity
```

## 9.3 AI/runtime evidence

```text
surface registry entry
journey/capability registry entries
grounded journey count
multi-step journey count
READ evidence route for each journey
model-only opt-in proof
unknown-site fail-closed proof
shared-core changed yes/no
raw site-id branch inventory
```

## 9.4 Safety evidence

```text
actual_site_navigation_observed
login_controls_exercised
submit/write/payment/upload exercised
PII fields/actions introduced
routine external provider calls
routine official-site calls
```

All should be zero unless a separately authorized integration track explicitly changes the contract.

## 9.5 Final metrics

Report the ratios from §8 and attach the exception queue. A successful-looking preview without these metrics is not framework validation.

# 10. Operational worker sequence for the next municipality

Use this order.

1. **Fresh remote gate** — current main SHA, open PRs/issues, collisions, existing site/profile/branch evidence.
2. **Read-only intake** — SiteSpec/profile + source/reference scope + capture plan.
3. **Capability inventory** — enumerate only observed product-relevant routes/states.
4. **Run generic clone pipeline first** — do not create a bespoke renderer because a source page is inconvenient.
5. **Open exception queue early** — unresolved source/asset/DOM patterns remain visible.
6. **Register accepted clone surface as data/config** — do not add site branches to the shell.
7. **Select minimum materially different resident journeys** — based on observed citizen value, not Buk-gu quest count.
8. **Encode route/question/marker differences in site registry data**.
9. **Use shared bounded navigation/action/READ** — if it cannot express the site, STOP and classify the gap before editing shared core.
10. **Derive answers from final evidence** — no factual final answer embedded in journey config.
11. **Keep model fallback explicit and non-site-grounded**.
12. **Add deterministic/offline tests** — no live provider/site calls in routine CI.
13. **Run Buk-gu regression** — second/third site work must not silently change the golden observable behavior.
14. **Run exact-head browser/CI gates**.
15. **Perform direct desktop/mobile product review**.
16. **Publish automation/override/human/unsupported metrics and raw site-branch inventory**.
17. **Promote only after explicit acceptance**; preserve rollback.

# 11. Shared-core change decision tree

Before modifying shared runtime code for a new institution, answer in order:

1. Can SiteSpec/site profile express it?
2. Can Site Model/content/route data express it?
3. Can theme/design tokens express it?
4. Can parser profile express it?
5. Can journey/action graph config express it?
6. Can a narrow reviewed override express it without changing shared semantics?

Only if all are **no** may shared-core change be proposed. The proposal must include:

- failing source evidence;
- why current generic contract cannot represent it;
- at least one existing municipality regression test;
- new generic contract independent of the new site id;
- raw site-id branch count before/after;
- effect on automation/exception metrics.

A patch equivalent to `if site_id == "new_site"` in generic runtime is not an acceptable shortcut.

# 12. Third-municipality validation gate

After this playbook is accepted, the next municipality/city/province task is primarily a **framework validation**.

It must answer:

1. What percentage of the scoped inventory used this playbook unchanged?
2. Which Buk-gu/Seo-gu assumptions failed?
3. Did each failure become a generic contract improvement, data/config difference, reviewed override, or unsupported exception?
4. Did shared-core site-id branching increase?
5. Did automation improve without weakening fidelity/safety?
6. Did Buk-gu and Seo-gu regression gates remain green?

A third institution is **not** a success for this track if it works only because another bespoke renderer or AI engine was added.

# 13. Cross-domain boundary (#1232 remains open)

Municipality-family generalization and arbitrary-site generalization are separate evidence levels.

```text
Buk-gu + Seo-gu accepted proof
 -> this municipality onboarding playbook
 -> optional additional municipality/city/province validation
 -> materially different cross-domain site
 -> broader general-site confidence
```

A university, public agency, support portal, or company site may expose materially different information architecture, interaction, content semantics, authentication, or transaction boundaries. Those must be evaluated under #1232 without assuming municipal capability vocabulary is universal.

# 14. Current acceptance evidence and known limits

## Accepted evidence

- #1328 Phase 0 gap audit accepted: comment `5310267653`.
- Slice A merged: PR #1332.
- Slice B merged: PR #1334.
- Slice C merged: PR #1336.
- Slice D merged: PR #1338.
- Gate A/B transfer and CI audit: #1339 comments `5315351536`, `5315357404`.
- Gate C direct product review accepted: #1339 comment `5315707331`.
- #1328 final acceptance after Gate C: comment `5315713289`, CLOSED/COMPLETED.
- current main full MVP CI: run #776 / `32023796558` = SUCCESS.
- #1232 remains OPEN.

## Direct product review summary

Accepted preview head: `44977b649850a9022549d9a2f17eac92b1ce5f3c`.

- desktop split surface: PASS;
- notice -> detail grounded journey: PASS;
- organization grounded journey: PASS;
- explicit general-model offer before model call: PASS;
- preview provider result: honest configuration failure; not counted as successful live-model proof;
- successful model-only provenance path: proven deterministically in exact-head function/browser CI;
- 390x844 mobile sanity: PASS;
- actual public-site navigation observed: NO.

The iframe intentionally omits `allow-scripts`; Chromium therefore reports script-block diagnostics for the cloned page. Current browser tests allow only the exact expected diagnostics for exercised local clone routes and fail on other browser errors. This is a reviewed **test-only** override, not permission to broadly suppress errors.

## Remaining unsupported scope

- arbitrary Seo-gu grounded questions beyond declared journey registry;
- actual Seo-gu public-site control;
- resident-default/Production promotion;
- live-provider requirement in routine CI;
- third-site proof;
- cross-domain completion.

# 15. Stage B disposition

This playbook is acceptable only if review confirms that it remains faithful to current code/evidence and does not convert bounded two-site proof into a universal claim.

After merge:

- #1329 may close as Stage A + Stage B complete;
- #1232 must remain open;
- the next municipality task must use this document as a framework-validation checklist;
- later cross-domain work must separately test whether the municipality-derived contracts generalize.
