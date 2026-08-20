# Multi-site Onboarding Golden Master Doctrine

- Status: `canonical`
- Scope: multi-site / new-institution resident-product onboarding
- Operating authority: #1366
- Parent program: #1232
- Canonical visual/interaction baseline: #1348
- Exact-clone invariant: [`docs/product/exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md)
- Current recovery: #1364 / #1365 / PR #1367
- Mandatory parity CI work: #1368 / PR #1372

This document is the durable repository authority for **resident journey parity across institutions**. It supersedes any older onboarding interpretation that allowed a new institution to own a different top-level resident interaction flow merely because its routes, evidence, or official downstream channel differed.

## 1. Product invariant

Buk-gu is the **Golden Master resident product**.

A new institution is not a separately designed resident product. The canonical model is:

```text
                 ┌─ Buk-gu institution adapter / data / evidence
Golden UX Engine ┤
                 ├─ Seo-gu institution adapter / data / evidence
                 └─ future institution adapter / data / evidence
```

There must be **one resident behavior engine** for the canonical scenario family.

Institution-specific code may supply only the narrow institution differences required by source truth, including:

- `site_id` / institution identity
- branding, logo, colors and source-backed media
- clone routes and official menu/page hierarchy
- department names and contact facts
- captured HTML/list/table/detail facts
- evidence selectors/markers/provenance
- verified external-channel facts
- a thin surface/bootstrap adapter when the institution clone exposes a different low-level API

Institution-specific code must not independently own canonical resident sequencing such as answer, confirmation, YES/NO decisions, navigation lifecycle, writing flow, review, reset/stale behavior, or pre-submit STOP.

## 2. Golden state graph is a product contract

The observable resident state graph is not an implementation detail.

For each mapped scenario, preserve every materially observable Golden state that exists in Buk-gu. Typical informational flow:

```text
resident question/chip
→ first answer
→ explicit YES/NO confirmation
→ YES is the only transition trigger
→ visible journey/navigation progression
→ institution route/content
→ evidence-backed answer + provenance
→ truthful final stable state / STOP
```

Typical NO path:

```text
question
→ answer
→ confirm
→ NO
→ STOP / answer state
```

NO must produce:

```text
navigation = 0
READ = 0
handoff = 0
provider/external execution = 0
```

For canonical complaint/writing scenarios, the Golden states also include the Buk-gu choice/write/review form and resident-controlled pre-submit STOP. Those states may not be removed merely because a real institution ultimately uses another official channel.

## 3. `DIRECT_REUSE` is source/evidence reuse only

`DIRECT_REUSE` means a real institution page/evidence can be reused as repository-clone evidence.

It does **not** authorize:

```text
chip → route → READ → final answer
```

when the Golden scenario contains intermediate answer/confirm/choice/write/review states.

Source/evidence reuse and resident-journey parity are separate concerns.

## 4. Official source truth changes content, not choreography

Official institution differences determine:

- what facts are shown;
- what local route is navigated;
- what evidence is read;
- what contact or authority is named;
- what downstream official channel is truthfully disclosed.

They do not automatically authorize a different resident UX.

If an exact institution equivalent does not exist, do not silently invent or substitute a shorter journey. Classify the mismatch and STOP for product-owner/CTO decision.

## 5. External channel rule

A verified external official channel is normally **site-specific safe-stop metadata/content**.

It must not replace a Golden interaction flow unless the corresponding Buk-gu Golden scenario itself uses that handoff at the same state.

Example:

```text
Golden:
complaint board → AI draft → resident review → STOP before submit

New institution:
same canonical flow
→ then disclose the verified institution-specific official channel at the safe boundary
```

Never convert a different real-world intake mechanism into permission to delete safe pre-action demo states.

Actual login, identity verification, PII entry, payment, upload, consent, submission and receipt semantics remain outside the current pre-integration MVP boundary unless explicitly authorized.

## 6. Mandatory architecture invariants

### INV-1 — one resident behavior engine

A new institution must not receive a separate top-level resident state machine.

### INV-2 — site-specific = data/evidence/adapter

Site-specific layers may hold copy, routes, selectors, facts, evidence, markers, branding and safe-stop metadata. Canonical UX sequencing remains shared.

### INV-3 — Buk-gu zero drift

Shared refactors must preserve Buk-gu observable behavior:

```text
BUKGU_STATE_GRAPH_BEFORE == BUKGU_STATE_GRAPH_AFTER
```

### INV-4 — canonical states cannot be skipped

Confirmation, decision, write/review and STOP states are product requirements where the Golden scenario owns them.

### INV-5 — evidence success is not parity success

These are independent gates:

```text
SOURCE_TRUTH
GROUNDING
SECURITY
INTERACTION_PARITY
VISUAL_PARITY
```

All required gates must pass independently.

### INV-6 — no silent external substitution

An external URL or handoff cannot silently replace the Golden resident flow.

### INV-7 — no silent behavior fork

If a new-site top-level behavior branch appears, implementation must STOP unless the Golden engine genuinely cannot express the scenario and an explicit product-owner decision authorizes the deviation.

## 7. Required onboarding sequence

### Gate 0 — freeze the Golden scenario

Before implementing a new institution scenario, record:

- Golden scenario ID
- resident question/chip
- exact material state graph
- decision controls
- route transitions
- writing/review states if present
- final STOP semantics
- desktop/mobile Golden visual references where material

### Gate 1 — institution fact mapping

Map only institution-specific data slots: equivalent source page, routes, department/contact, evidence markers, verified official-channel facts.

### Gate 2 — bounded source capture

Capture only separately approved public GET evidence needed to fill those slots. Capture is not behavior authorization.

### Gate 3 — adapter/config implementation

Wire institution data/evidence/surface capability into the canonical engine. Do not copy the state machine.

### Gate 4 — state-by-state browser parity

The test must prove every canonical material state in order and fail if a state is skipped.

At minimum where applicable:

- first answer exists;
- route unchanged after answer;
- explicit confirm exists;
- route unchanged after confirm;
- YES/NO controls exist;
- NO executes no journey and does not navigate/read/handoff;
- YES is the only transition trigger;
- stale controls cannot execute;
- double activation executes once;
- final result/provenance matches expected institution evidence;
- external request count is zero in routine CI.

### Gate 5 — grounding/provenance

After the canonical transition reaches the institution clone:

- bounded repository-clone READ succeeds;
- required markers are present;
- answer is evidence-derived;
- provenance is visible;
- unsupported evidence fails closed.

### Gate 6 — paired direct-PNG review

For each material observable state, compare the Golden state with the corresponding new-site state. Desktop/mobile are required where the canonical product supports them.

Final-screen-only review is insufficient.

### Gate 7 — architecture acceptance

Before Ready/merge, report:

```text
STATE_GRAPH_EQUAL = YES
BUKGU_BEHAVIOR_DRIFT = NONE
NEW_SITE_BEHAVIOR_FORK = NO
CANONICAL_STATES_SKIPPED = 0
EXTERNAL_CHANNEL_REPLACES_CANONICAL_FLOW = NO
```

Any other value blocks merge unless explicitly approved by the product owner.

## 8. Required PR fields

Every relevant multi-site/new-site onboarding PR must provide:

```text
GOLDEN_SCENARIO_ID =
GOLDEN_STATE_GRAPH =
NEW_SITE_STATE_GRAPH =
STATE_GRAPH_EQUAL = YES / NO

BUKGU_BEHAVIOR_DRIFT = NONE / <detail>
NEW_SITE_BEHAVIOR_FORK = NO / <detail>
CANONICAL_STATES_SKIPPED = 0 / <count>

SITE_SPECIFIC_DATA_CHANGED =
SITE_SPECIFIC_BEHAVIOR_CHANGED = NO / <detail>

CANONICAL_CONFIRMATION_PRESERVED = YES / N/A
CANONICAL_CHOICE_PRESERVED = YES / N/A
CANONICAL_WRITE_FORM_PRESERVED = YES / N/A
CANONICAL_PRE_SUBMIT_STOP_PRESERVED = YES / N/A

EXTERNAL_CHANNEL_REPLACES_CANONICAL_FLOW = NO / YES
STATE_BY_STATE_BROWSER_TEST = PASS / FAIL
PAIRED_DIRECT_PNG_REVIEW = PASS / FAIL / N/A
SECURITY = PASS / FAIL
EXACT_HEAD_CI = PASS / FAIL / PENDING
```

## 9. Forbidden parity arguments

None of the following proves Golden Master parity by itself:

- same resident purpose;
- safer behavior;
- the official site works differently;
- `grounded=true`;
- CI is green;
- final page looks good;
- external handoff is more realistic;
- code is generic;
- source evidence is correct.

The acceptance question is whether the **same canonical resident journey** is preserved with institution-specific factual substitution.

## 10. Historical Seo-gu work that remains reusable

Architecture correction does not invalidate valid source/evidence work. Reusable unless separately disproven:

- official Seo-gu captures and provenance;
- faithful Seo-gu shell/branding/assets;
- housing/passport/kiosk local clone routes;
- bounded illegal-parking evidence;
- generic CMS/list/detail renderers;
- responsive/mobile corrections;
- clone-DOM READ and grounding;
- provenance UI;
- offline/security/network guards.

The failed layer was the alternate resident orchestration and the acceptance model that allowed it.

## 11. Current recovery state

At the time this doctrine was materialized:

```text
CURRENT_MAIN = dbc785e0dd16e4d2a73c7c0245747cfbb9459271
BUKGU_GOLDEN_MASTER = AUTHORITATIVE
SEOGU_PARITY_RECOVERY = ACTIVE
#1363 = HOLD
THIRD_SITE = BLOCKED_PENDING_SEOGU_GOLDEN_PARITY
#1366 = OPERATING_DOCTRINE_AUTHORITY
```

Current recovery order:

```text
#1365 / PR #1367
→ shared informational Golden choreography for S1/S2/S5/S6

#1368 / PR #1372
→ mandatory Golden state-graph CI gate

next bounded complaint-writing remediation
→ S3/S4 Golden complaint/write/review flows

then
→ S7 mayor Golden flow
→ bulky-waste/mattress Golden high-risk flow
→ full paired state-by-state visual acceptance
→ only then third-site / cross-domain onboarding
```

The exact SHA/PR state above is a dated implementation snapshot. GitHub remote remains the source of truth for current execution state.

## 12. Authority and supersession

For resident multi-site onboarding interpretation, authority order is:

1. product owner's latest explicit decision;
2. this document / #1366 Golden Master doctrine;
3. `docs/CURRENT_STATUS.md` for current execution state;
4. narrower security/network/production boundaries for their technical scope;
5. older onboarding/playbook/history documents only where they do not conflict.

`docs/product/municipality-ai-finder-onboarding-playbook.md` remains useful for historical source/capture/platform evidence, but any resident-journey interpretation that permits a different new-site state graph is superseded by this document.

This doctrine remains active until an explicit product-owner decision supersedes it.
