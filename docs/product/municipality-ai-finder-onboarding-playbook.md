# Municipality AI Finder Onboarding Playbook

- Status: `active-plan` for source/capture/platform onboarding
- Resident-journey authority: **superseded by #1366 / `docs/operations/multi-site-onboarding-golden-master.md` where conflict exists**
- Historical origin: #1329 Stage B
- Historical evidence family: Buk-gu protected golden + Seo-gu AI-on-clone proof
- Parent program: #1232
- Current authority snapshot: main `dbc785e0dd16e4d2a73c7c0245747cfbb9459271`

This playbook preserves the operational lessons learned while onboarding Buk-gu and Seo-gu, especially around identity, reference capture, clone modeling, evidence, provenance, offline CI and failure boundaries.

It is **not** the authority for inventing a different resident UX for each institution. For resident interaction semantics, use:

[`../operations/multi-site-onboarding-golden-master.md`](../operations/multi-site-onboarding-golden-master.md)

## 0. Authority correction

Earlier versions of this playbook correctly generalized site identity, clone/evidence ownership and bounded READ, but were too permissive about resident choreography. In particular, statements such as “do not make every site look like Buk-gu” could be read as permission to replace Buk-gu's canonical resident state graph with a shorter institution-specific journey.

That interpretation is superseded.

Current rule:

```text
Visual/content identity may differ.
Routes/evidence/facts may differ.
Resident Golden state graph does not silently differ.
```

Architecture:

```text
                 ┌─ Buk-gu adapter/data/evidence
Golden UX Engine ┤
                 ├─ Seo-gu adapter/data/evidence
                 └─ future institution adapter/data/evidence
```

A site-specific layer may not own a second top-level resident behavior engine.

## 1. What remains valid from the two-municipality proof

The accepted clone-first product pattern remains:

```text
LEFT  = repository-controlled faithful institution clone
RIGHT = AI conversation / answer / bounded local navigation / evidence
```

The reusable platform lessons remain:

```text
institution identity
→ scoped source/reference capture
→ route/content/asset inventory
→ faithful clone model
→ deterministic clone rendering
→ source-vs-clone QA
→ site surface registration
→ institution capability/journey data
→ bounded local action
→ visible-text READ
→ evidence-derived answer + provenance
→ deterministic/offline CI
→ direct product/visual review
→ versioned candidate / rollback / exception queue
```

What changed is the **resident choreography rule**: capability/journey data fills site-specific facts into the Golden resident flow; it does not authorize a replacement state machine.

## 2. Canonical onboarding pipeline

| Stage | Required input | Required output | Gate |
|---|---|---|---|
| 0. Golden scenario freeze | Buk-gu canonical resident journey | scenario ID + exact material state graph + desktop/mobile references | no new-site design before Golden inventory |
| 1. Institution identity | institution id/domain/scope | canonical `site_id`, source scope, allowlist | unknown/malformed identity fails closed |
| 2. Bounded source capture | approved public scope | reproducible point-in-time reference | GET/read only; no login/submit/payment/PII mutation |
| 3. Route/content/asset inventory | captured reference | route/state/content/asset inventory | unresolved items explicit; no fabrication |
| 4. Faithful Site Model | inventory + evidence | deterministic site model | source-backed only |
| 5. Clone render | site model + visual contract | repository-controlled faithful clone | no actual-site runtime dependency |
| 6. Source-vs-clone QA | source + clone | structural/content/asset/responsive/visual evidence | direct fidelity review required |
| 7. Surface registration | accepted clone | site config + allowed routes + readable roots | data/config ownership; unknown fails closed |
| 8. Institution data mapping | Golden scenario + source evidence | routes, contacts, markers, safe-stop facts | site data only, not a second state machine |
| 9. Golden engine adapter | site data + clone surface | thin adapter into canonical resident engine | no site-local canonical sequencing |
| 10. State-by-state browser parity | Golden + new-site implementation | exact ordered state proof | missing state fails |
| 11. Grounding/provenance | post-transition clone READ | evidence-derived answer | fail closed on missing required evidence |
| 12. Security/egress | exact candidate | offline/no-submit proof | routine external request count = 0 |
| 13. Paired visual acceptance | Golden + new-site material states | desktop/mobile paired direct-PNG review | final-screen-only review insufficient |
| 14. Promotion/rollback | all accepted evidence | versioned candidate/default decision | no implicit Production/default promotion |

## 2.1 Mandatory sequencing

Do not start by implementing what appears easiest on the new institution.

The required order is:

```text
Golden resident scenario
→ institution fact/evidence mapping
→ clone capability
→ thin adapter
→ canonical behavior
→ browser state parity
→ evidence/provenance
→ paired visual acceptance
```

A local route existing in the clone does not authorize jumping directly to that route on chip click.

## 3. Difference ownership model

| Difference class | Correct owner | Forbidden interpretation |
|---|---|---|
| institution identity/domain | SiteSpec / site profile / central registry | scattered behavior branches |
| route vocabulary | site model / surface registry | generic engine hardcodes one institution route |
| question labels / resident copy | journey/site data | duplicate resident state machine |
| department/contact facts | site evidence/config | generated/fabricated fact |
| evidence markers | journey data/config | prewritten factual answer replacing READ |
| visual theme/assets | site visual contract/assets | unrelated shared-core visual fork |
| parser/source quirks | parser profile or reviewed generic improvement | hidden site branch in canonical UX engine |
| low-level surface API | thin adapter | top-level behavior owner |
| verified external official channel | safe-stop metadata/content | replacement for Golden choice/write/review flow |
| unsupported feature | exception queue / HOLD | fake automation |

## 4. Golden compatibility rule

Every relevant new-site scenario must record:

```text
GOLDEN_SCENARIO_ID =
GOLDEN_STATE_GRAPH =
NEW_SITE_STATE_GRAPH =
STATE_GRAPH_EQUAL = YES / NO
BUKGU_BEHAVIOR_DRIFT = NONE / <detail>
NEW_SITE_BEHAVIOR_FORK = NO / <detail>
CANONICAL_STATES_SKIPPED = 0 / <count>
```

Golden parity is about materially observable resident behavior, not identical institution text or route strings.

Allowed differences:

- institution name/logo/colors;
- official route/menu names;
- department/contact values;
- source-backed evidence content;
- provenance labels;
- verified downstream official-channel facts.

Not silently allowed:

- skipping the first answer;
- skipping explicit confirmation;
- navigation before YES;
- deleting choice/write/review states;
- replacing pre-submit STOP with an external link;
- a new-site-only state engine;
- changing Buk-gu behavior to make the new site easier.

## 5. `DIRECT_REUSE` clarification

Historical Seo-gu implementation used `DIRECT_REUSE` to describe valid reuse of captured local clone pages and source evidence.

The current meaning is narrow:

```text
DIRECT_REUSE = source/evidence reuse
```

It does not mean:

```text
DIRECT_REUSE = resident choreography may be shortened
```

The Golden resident flow must still be applied around the reused evidence.

## 6. External official channel and high-risk actions

External institution channels may be shown only at the appropriate canonical safe boundary.

Routine onboarding must never imply:

- actual submission completed;
- receipt issued;
- resident identity verified;
- payment completed;
- form data sent to a real institution;
- external destination automatically opened.

For complaint/writing scenarios where the Golden product has a deterministic AI draft/review/pre-submit STOP, preserve those states before disclosing institution-specific downstream handling.

## 7. Browser parity evidence

For each applicable scenario, use fresh contexts for NO and YES paths.

Required informational proof:

```text
question/chip
→ ANSWER observed
→ route unchanged
→ CONFIRM observed
→ route unchanged
→ YES/NO controls
```

NO path:

```text
execution count = 0
navigation = 0
READ = 0
handoff = 0
external requests = 0
```

YES path:

```text
canonical execution = exactly 1
→ institution route
→ bounded repository evidence
→ expected result/provenance
→ stable STOP/result boundary
```

Lifecycle proof must cover stale controls and double activation where the Golden engine exposes them.

For writing/decision scenarios, add the corresponding choice/write/review/pre-submit states instead of treating informational parity as sufficient.

## 8. Paired visual evidence

Visual acceptance must be state-by-state, not final-screen-only.

For each material state, capture/inspect the Golden and new-site equivalents at applicable desktop/mobile viewports.

Automated DOM assertions or CI green do not replace direct PNG review when a visual acceptance gate is required.

## 9. Security / network contract

Routine CI stays deterministic and loopback-only.

Default prohibitions:

- provider/general-model live call;
- official-site live network;
- Firecrawl;
- login;
- actual civic submission;
- upload;
- payment;
- citizen PII;
- Production mutation.

A separately authorized controlled live validation is a different stage and must explicitly state target/scope/method.

## 10. Historical evidence lineage

The following historical work remains evidence for how the platform generalized and should not be erased:

- #1328 / #1339 — two-municipality acceptance evidence;
- PR #1332 — site identity / fail-closed dispatch;
- PR #1334 — generic clone surface / bounded READ;
- PR #1336 — journey data / evidence-derived answer;
- PR #1338 — explicit model-only fallback / related integration;
- #1303 and G1/G2/G3 Seo-gu source/clone fidelity lineage;
- accepted source captures, clone assets, renderer improvements and provenance artifacts.

These artifacts may remain technically valid even when their old resident-journey interpretation is superseded.

Git history preserves prior versions of this playbook and the exact historical claims made at those stages.

## 11. Current Seo-gu recovery

Current authoritative recovery is tracked under:

- #1364 — parent parity recovery
- #1365 / PR #1367 — S1/S2/S5/S6 shared Golden engine
- #1366 — operating doctrine
- #1368 / PR #1372 — mandatory Golden state-graph CI
- #1363 — S7 HOLD

At the current snapshot:

```text
CURRENT_MAIN = dbc785e0dd16e4d2a73c7c0245747cfbb9459271
BUKGU_GOLDEN_MASTER = AUTHORITATIVE
SEOGU_PARITY_RECOVERY = ACTIVE
THIRD_SITE = BLOCKED_PENDING_SEOGU_GOLDEN_PARITY
```

After informational shared-engine recovery, the next resident behavior work is the Buk-gu-derived complaint/write/review family (S3/S4), then S7 mayor, then bulky-waste/mattress high-risk STOP behavior, followed by full paired visual acceptance.

## 12. Next-institution checklist

Before implementation:

- identify the Golden scenario;
- inventory exact material states;
- map institution-specific data/evidence slots;
- verify no existing shared-engine capability already solves the difference;
- declare unsupported/missing facts rather than inventing them.

Before merge:

```text
STATE_GRAPH_EQUAL = YES
BUKGU_BEHAVIOR_DRIFT = NONE
NEW_SITE_BEHAVIOR_FORK = NO
CANONICAL_STATES_SKIPPED = 0
EXTERNAL_CHANNEL_REPLACES_CANONICAL_FLOW = NO
STATE_BY_STATE_BROWSER_TEST = PASS
PAIRED_DIRECT_PNG_REVIEW = PASS / N/A
SECURITY = PASS
EXACT_HEAD_CI = PASS
```

## 13. Non-claims

Even after two municipalities, the repository does not automatically prove:

- arbitrary-site/cross-domain completion;
- universal municipal capability coverage;
- actual-site first-party control;
- Production/resident-default approval for every new site;
- real submission/payment/login automation;
- a measured automation percentage for an untested third institution.

Third-site/cross-domain proof remains blocked until Seo-gu Golden parity closes.

## 14. Supersession rule

If this playbook conflicts with the Golden resident doctrine, use:

[`../operations/multi-site-onboarding-golden-master.md`](../operations/multi-site-onboarding-golden-master.md)

The source/capture/clone/evidence portions of this playbook remain active where compatible. The older permission to interpret “same purpose” or “generic new-site UX” as sufficient resident parity is retired.
