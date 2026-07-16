# Buk-gu golden compatibility manifest

## Header

| Field | Value |
|-------|--------|
| Golden repository | `skerishKang/400-ai-finder` |
| Golden commit | `7217c0f738a6aa4468bdde3119d8c2d1ec9dd610` |
| Golden commit subject | `fix(a11y): hide decorative AI labels in clone controls (#1186)` |
| Freeze decision | Issue **#1187** — READY TO FREEZE |
| Scope | Controlled **clone-first** Buk-gu golden reference |

### Explicit non-claims

This freeze **is**:

- a controlled clone-first product baseline
- deterministic civic journeys on fixture-backed Buk-gu surfaces
- vendored Page Agent runtime + **deterministic resident mock adapter**
- canonical offline comparison evidence + permanent CI contracts
- no-submit / no-live-provider / no-actual-site-control safety boundary

This freeze **is not**:

- not a complete exact clone of every current official-site route
- not a live LLM quality comparison
- not actual Buk-gu site control or real civic submission
- not live answer-time official retrieval
- not multi-site platform implementation completed

Clone fidelity policy still applies to the civic left surface where exact-clone
is claimed; home fixture currently sets `exact_clone_claimed=false` /
`capture_required`. See
[`product/exact-official-site-clone-invariant.md`](product/exact-official-site-clone-invariant.md).

Related architecture decision: [`architecture/clone-first-platform-adr.md`](architecture/clone-first-platform-adr.md).

---

## 1. Public product URLs

Owner of packaging: `scripts/build_cloudflare_pages.py` (static/live modes).

| URL | Owner / source | Purpose | Classification | Related contracts | Compatibility rule |
|-----|----------------|---------|----------------|-------------------|--------------------|
| `/` | Citizen root `index.html` from build | Primary citizen chat-first entry (MVP shell forced) | **Primary** | `verify_mvp_shell_runtime`, first-use responsive, home fixture E2E | Do not rename or remove without migration issue |
| `/mvp/` | Compatibility copy of citizen root | Same product surface for older links | **Secondary / compatibility** | Same as `/` | Keep URL forever; may redirect later only with dual-serve |
| `/compare/` | `src/web/compare/` | Stakeholder comparison gateway (deterministic vs Page Agent) | **Primary comparison** | comparison contract tests, Stage 3 harness | Two equal primaries only; no “winner” |
| `/examples/page-agent/resident/` | `src/web/examples/page-agent/resident/` | Page Agent resident demo (vendored runtime + mock) | **Primary Page Agent** | resident E2E, cancellation E2E, production-gap | Load home fixture before canvas; mock adapter only in golden CI |
| `/examples/page-agent/` | `src/web/examples/page-agent/` | Developer Page Agent lab | **Internal / secondary** | lab runtime + lab E2E | Not a stakeholder primary |
| `/internal/` | Build-generated operator index | Operator artifact chooser | **Internal** | build contracts | Not citizen primary |
| `/mobile.html` | Mobile demo template + shim | Mobile standalone demo surface | **Secondary** | mobile link safety | Safety: same-origin only |
| `/admin.html` | Admin template + shim | Operator admin demo | **Internal** | admin contracts when present | Not citizen primary |

---

## 2. Closed civic route vocabulary

**Source of truth (read-only freeze):**
`src/web/static/citizen-action-demo-map.js` → `CLOSED_ROUTE_IDS` / `ROUTES`.

**Count at golden SHA:** **17** closed route IDs (including `home`).

| Route ID | Terminal? | Owner | Primary journeys / notes | Classification |
|----------|-----------|-------|--------------------------|----------------|
| `home` | Entry surface | map + canvas `_renderHome` (fixture) | All journeys start; fixture-backed | **Frozen** |
| `civil-service` | Intermediate | map + canvas | Path into complaint tree | Frozen intermediate |
| `complaint-category` | Intermediate | map + canvas | Category choice | Frozen intermediate |
| `complaint-illegal-parking` | Guidance terminal-ish | map + canvas | Illegal parking guidance | Frozen |
| `complaint-intake` | Intermediate | map + canvas | Intake | Frozen |
| `complaint-board` | Intermediate | map + canvas | Board before write | Frozen intermediate (not Page Agent final success) |
| `complaint-write` | **Terminal** (pre-submit form) | map + canvas + bilingual draft | Complaint writing / AI draft | Frozen terminal |
| `complaint-review` | Review surface | map + canvas | Draft review | Frozen |
| `handoff-stop` | **Terminal safety** | map + canvas | Explicit no-submit handoff | Frozen safety |
| `mayor-office` | Intermediate | map + canvas | Open mayor office | Frozen intermediate (not Page Agent final success) |
| `mayor-complaint-write` | **Terminal** (pre-submit) | map + canvas + choreography | Mayor proposal writing | Frozen terminal |
| `mayor-complaint-receipt` | Pre-submit receipt | map + canvas | Truthful pre-submit receipt | Frozen |
| `bulky-waste-disposal` | Guidance terminal | map + official snapshot content | Bulky waste | Frozen |
| `passport-guidance` | Guidance terminal | map + official snapshot content | Passport | Frozen |
| `unmanned-kiosk-guidance` | Guidance terminal | map + official snapshot content | Kiosk | Frozen |
| `apartment-info` | Guidance | map + canvas | Apartment info | Frozen |
| `apartment-dept` | **Terminal** dept surface | map + canvas + dept journey | Housing contact / dept | Frozen terminal |

**Breaking-change rule:** no silent rename/removal of any closed route ID without a dedicated migration issue, dual mapping period, updated golden contracts, and exact-head CI.

**Additive rule:** new routes require map vocabulary update + renderer + tests; must not repurpose existing IDs.

---

## 3. Action-target contracts (selected closed set)

**Source:** `CLOSED_TARGET_IDS` in `citizen-action-demo-map.js` + producers in `citizen-action-demo-canvas.js` / fixture mappings / shell.

| Target ID | Producer | Consumers | Typical terminal route | Classification |
|-----------|----------|-----------|------------------------|----------------|
| `mayor-office-open` | Home fixture / shell / canvas | Page Agent parity, mayor E2E, a11y | `mayor-office` | **Frozen** |
| `mayor-message-write` | Mayor office page | Parity, mayor journey | `mayor-complaint-write` | Frozen |
| `mayor-receipt-home` | Receipt UI | Journey return | `home` | Frozen |
| `nav-civil-service` | GNB / home | Flows into civil tree | intermediate | Frozen |
| `nav-complaint-board` | GNB / home | Complaint path | → `complaint-board` | Frozen |
| `nav-apartment-dept` | Home fixture/compat | Housing parity | `apartment-dept` | Frozen |
| `nav-bulky-waste-disposal` | Home fixture region | Bulky parity | `bulky-waste-disposal` | Frozen |
| `nav-passport-guidance` | Home fixture/compat | Passport parity | `passport-guidance` | Frozen |
| `nav-complaint-category` | Civil service LNB | Category path | intermediate | Frozen |
| `complaint-write` | Board write control | Complaint parity step 2 | `complaint-write` | Frozen |
| `complaint-body` | Write form | Executor / draft | form surface | Frozen |
| `complaint-draft-review` | Write UI | Review path | review | Frozen |
| `confirm-draft-prefill` | Submit-like control | Must stay disabled / pre-submit | safety | Frozen safety |
| `handoff-notice` | Handoff UI | No real submit | `handoff-stop` | Frozen safety |
| `complaint-illegal-parking-report` | Parking card | Parking journey | parking surface | Frozen |
| `bulky-waste-guidance-card` | Guidance card | Bulky | bulky | Frozen |
| `passport-guidance-card` | Guidance card | Passport | passport | Frozen |
| `unmanned-kiosk-card` | Guidance card | Kiosk | kiosk | Frozen |
| `apartment-guidance-card` / `apartment-dept-card` / `apartment-life-card` | Apt surfaces | Housing | apt routes | Frozen |

Full closed list is code-owned in `CLOSED_TARGET_IDS` — this table highlights golden demo critical targets.

---

## 4. Stable DOM IDs and state attributes

| Contract | Owner | Screens | Why frozen | Allowed extension |
|----------|-------|---------|------------|-------------------|
| `#demo-canvas` | HTML shell + canvas | All MVP | Canonical guidance surface | Additive children only |
| `#chat-shell` | HTML shell | All MVP | Conversation chrome; #1174 dock | No rename |
| `#chat-composer-input` / send | HTML shell | All MVP | Composer identity | Additive attrs only |
| `#mayor-open-office-control` | Shell entry hero | Entry | Entry mayor entrypoint | State-gated visibility OK |
| `#btn-open-mayor-office` | Canvas home / fixture | Split/home | Canvas mayor entry + action target | Must keep `data-action-target="mayor-office-open"` when interactive |
| `#chat-cancel` | Resident chat | Desktop running | Desktop cancel owner | Mobile may hide |
| `#page-agent-mobile-cancel` | Resident switch | Mobile running | Mobile cancel owner (#1183) | Keep terminal cancel semantics |
| `data-first-use-state` | Shell | MVP body | `entry` \| `transitioning` \| `split` | No silent rename |
| `data-mobile-surface` | Shell | MVP mobile | `conversation` \| `guidance` | No silent rename |
| `data-journey-state` | Shell | MVP body | `entry` \| `answer` \| `confirm` \| `navigate` \| `result` | Additive states need tests |
| `data-choreography-state` | Choreography | MVP body | See §5 | Additive states need tests |
| `data-page-agent-plan-state` | Resident demo | Resident | plan vocabulary §6 | No silent rename |
| `data-page-agent-mobile-surface` | Resident demo | Resident | independent of plan state | No silent rename |

**Consumers:** browser verifiers under `tests/browser/verify_*.mjs`, shell/canvas Python static contracts.

---

## 5. Deterministic layout, journey, and choreography states

### Layout (`data-first-use-state`) — `CitizenFirstUseShell.states`

| State | Meaning |
|-------|---------|
| `entry` | Chat-first, canvas unavailable |
| `transitioning` | Animated transition into split |
| `split` | Chat + guidance co-present |

### Journey (`data-journey-state`) — `CitizenFirstUseShell.journeyStates`

| State | Meaning |
|-------|---------|
| `entry` | Fresh |
| `answer` | Answered / waiting decision |
| `confirm` | Confirm-run prompt |
| `navigate` | Canvas choreography running |
| `result` | Terminal result on canvas |

### Choreography (`data-choreography-state` / `CitizenFirstChoreography.states`)

| State | Meaning |
|-------|---------|
| `idle` | No run |
| `running` | Steps executing |
| `done` | Finished |
| `cancelled` | User/system cancel |
| `waiting_choice` | Write-myself vs AI help |
| `waiting_confirmation` | Confirm before continue |
| `waiting_resident_draft` | Bilingual stage 1 |
| `waiting_korean_draft` | Bilingual stage 2 |
| `waiting_form_review` | Form review gate |

### Draft stages (`CitizenFirstChoreography.draftStages`)

| Stage | Meaning |
|-------|---------|
| `idle` | No draft |
| `resident_draft_review` | Original language draft |
| `korean_draft_review` | Korean draft |
| `form_populated` | Form fields filled (still pre-submit) |

---

## 6. Page Agent contracts

### Runtime shape

| Item | Golden fact |
|------|-------------|
| Runtime | Vendored Page Agent IIFE under `examples/page-agent/vendor/` |
| Resident UI | `examples/page-agent/resident/` |
| Comparison model | **Deterministic mock adapter** (`resident-mock-model.js`), not live LLM |
| Civic surface | Same canvas + home fixture as MVP |

### Five canonical parity scenarios

Owner: `parity-scenarios.js` / expectations fixture.

| ID | Terminal route | Nav targets (summary) |
|----|----------------|------------------------|
| `apartment_contact` | `apartment-dept` | `nav-apartment-dept` |
| `bulky_waste_menu` | `bulky-waste-disposal` | `nav-bulky-waste-disposal` |
| `passport_procedure` | `passport-guidance` | `nav-passport-guidance` |
| `complaint_screen` | `complaint-write` | `nav-complaint-board` → `complaint-write` |
| `mayor_proposal_writing` | `mayor-complaint-write` | `mayor-office-open` → `mayor-message-write` |

**Forbidden success routes** (must not count as final success):
`home`, `civil-service`, `complaint-category`, `complaint-board`, `mayor-office`, `official-content`.

### Plan / mobile axes (resident)

| Attribute | Vocabulary |
|-----------|------------|
| `data-page-agent-plan-state` | `idle`, `planning`, `executing`, `result`, `unsupported`, `disabled`, `error`, `cancelled` |
| `data-page-agent-mobile-surface` | `conversation`, `guidance` (independent of plan mode) |

### Cancellation

| Viewport | Canonical control | Terminal plan state |
|----------|-------------------|---------------------|
| Desktop | `#chat-cancel` | `cancelled` |
| Mobile | `#page-agent-mobile-cancel` | `cancelled` |

Post-cancel: no success rewrite; no further tool-loop traffic; permanent contract
`tests/browser/verify_mobile_resident_cancellation_e2e.mjs`.

### Diagnostics API (mock)

`window.PageAgentMockModel`: `getDiagnostics`, `resetDiagnostics`, `resetSession`, `respond`, scenario list.
Golden comparison **does not** validate live LLM quality.

---

## 7. Public JavaScript / window APIs

| API | Owner | Known consumers | Classification |
|-----|-------|-----------------|----------------|
| `window.CitizenActionDemoCanvas` | canvas.js | shell, choreography, executor, tests, Page Agent | **Frozen public** |
| `.navigateToRoute` / `.getCurrentRouteId` / `.getTargetElement` | canvas | journeys, tests | Frozen |
| `.showCursorAt` / `.hideCursor` / `.clickAnimation` / `.fitToViewport` | canvas | choreography, mobile fit | Frozen / additive methods need review |
| `window.CitizenActionDemoMap` | map.js | canvas | Frozen closed vocabulary |
| `window.CitizenFirstUseShell` | shell.js | canvas, tests | Frozen public |
| `window.CitizenFirstChoreography` | choreography.js | shell, canvas, tests | Frozen public |
| `window.__BUKGU_HOME_CLONE_FIXTURE__` | generated projection | canvas home | Frozen global name |
| `window.__BUKGU_OFFICIAL_SNAPSHOTS__` | snapshots | canvas official routes | Frozen global name |
| `window.PageAgentMockModel` | resident-mock-model.js | resident, comparison | Frozen mock diagnostics surface |
| `window.PageAgentParityScenarios` | parity-scenarios.js | mock model | Frozen scenario vocabulary |
| `window.PageAgentResidentRuntime` | resident-demo.js | tests/diagnostics | Frozen read-only control surface |

Internal helpers (non-exported functions) are **not** public API.

---

## 8. Fixture and generated-output provenance

```text
authorized capture sources
  data/official_captures/bukgu_gwangju/home/*  (when present)
        ↓
canonical fixture JSON
  data/official_clone_fixtures/bukgu_gwangju/home.json
        ↓ scripts/generate_bukgu_home_clone_fixture.py
browser projection (AUTO-GENERATED)
  src/web/static/bukgu-home-clone-fixture.js
  → window.__BUKGU_HOME_CLONE_FIXTURE__
        ↓
renderer
  citizen-action-demo-canvas.js (_renderHome / fail-closed unavailable)
        ↓
contracts
  home fixture E2E, parity tests, asset identity --check
```

| Field | Golden value / meaning |
|-------|-------------------------|
| `fixture_id` | `bukgu_gwangju.home.clone.2026-07-15` |
| `fixture_sha256` | `81b27b98fadc091ca852079f89ea93da45b93f250372835b8b352726b2faeaed` |
| `clone_status` | `capture_required` — home is **not** claimed exact |
| `boundaries.exact_clone_claimed` | `false` |
| `status` (fixture JSON) | Generator-era vocabulary `fixture_ready_renderer_not_wired` may remain frozen inside the identity blob; **runtime renderer is wired** (#1170). Do not hand-edit the JSON to “fix” the string without a regeneration + identity program. |

**Rules:**

- Never hand-edit `bukgu-home-clone-fixture.js`
- Change only via generator + committed canonical JSON process
- Unresolved official assets: no remote `img src` (metadata only)
- Fixture-backed renderer ≠ full exact official clone of every route

Asset identity audits:
`data/official_clone_asset_audits/bukgu_gwangju/*` with frozen scan manifest (#1177); normal tests use `--check` only.

---

## 9. Canonical evidence

| Artifact | Role |
|----------|------|
| `docs/artifacts/1109-stage3-comparison/comparison-evidence.json` | **Canonical** offline 5×2 comparison evidence |
| `docs/page-agent-stage3-comparison-report.md` | **Canonical** public-safe Stage 3 report |
| `docs/artifacts/1145-phase-b/phase-b-notes.md` | **Supporting** Phase B notes (points at 1109 evidence) |
| `docs/artifacts/1145-phase-a/*` | **Historical only** — do not rewrite as current |
| `tests/fixtures/page_agent_comparison_expectations.json` | Permanent expectations fixture (schema 1.0.0, 5 scenarios) |

Stage 5 live LLM: **blocked / not executed** in golden CI.

---

## 10. Build and permanent CI

### Build commands

```bash
python scripts/build_cloudflare_pages.py --mode static
python scripts/build_cloudflare_pages.py --mode live
```

Live mode packages the citizen MVP for LLM-backed deploy shape but **golden CI browser contracts** stay offline (localhost, mocks, no Firecrawl).

### Permanent workflow

`.github/workflows/mvp-contracts.yml` — job `mvp-contracts` (PR + push to `main`).

| Step (workflow name) | Command / role |
|----------------------|----------------|
| MVP contract pytest suite | shell/canvas/mobile contracts |
| Canonical official snapshot contracts | snapshots, fidelity, exact-clone invariant, quest matrix |
| Legacy transport / crawler suites | offline transport contracts |
| Static Pages build contract tests | `test_build_cloudflare_pages.py` |
| MVP shell runtime harness | `verify_mvp_shell_runtime.mjs` |
| npm ci | Node deps (no browser download policy in workflow) |
| Home fixture canvas (#1170) | `verify_home_fixture_canvas_e2e.mjs` |
| Responsive first-use | `verify_first_use_responsive.mjs` |
| Decorative AI a11y (#1175) | `verify_decorative_ai_labels_a11y.mjs` |
| Mobile multistep composer (#1174) | `verify_mobile_multistep_composer_e2e.mjs` |
| Desktop scroll (#1173) | `verify_desktop_chat_scroll_containment_e2e.mjs` |
| Mobile link safety | live build + localhost 8769 |
| Housing + mayor + header | live build + localhost 8768 |
| Two-stage bilingual draft | `verify_two_stage_bilingual_draft_e2e.mjs` |
| Cloudflare MVP Function contract | opt-in env function test |
| Page Agent lab Python / runtime / E2E | lab suite |
| Comparison contract + evidence tests | Python |
| Expectations fixture integrity | 5 scenarios + base_sha check |
| Resident E2E | live build + 8766 |
| Mobile cancellation (#1183) | `verify_mobile_resident_cancellation_e2e.mjs` |
| Resident mock model | unit browser contract |
| Production-gap E2E | fail-closed gaps |
| Stage 3 harness (1 rep) | static build + 8765 + comparison script |
| Stage 3 evidence schema verify | counters / pass_criteria |

Local-only tests that are **not** in this workflow must not be described as permanent CI.

---

## 11. Safety contracts

| Boundary | Golden enforcement |
|----------|--------------------|
| No actual official-site control | Clone/fixture only in product paths |
| No real civic submission | Disabled submit; handoff-stop; pre-submit receipts |
| No login / payment / PII transmission | Browser contracts assert zero |
| No external navigation in controlled tests | Origin allow-lists; request filters |
| No live provider / Firecrawl in golden comparison | Mock / offline adapters |
| Stage 5 live validation | Blocked / not executed |
| Evidence counters (Stage 3 / resident) | `external_request_count`, `no_submit_preserved`, console/page errors = 0 |

---

## 12. Breaking-change requirements

Any change to frozen routes, action targets, state attribute values, public window APIs, golden SHA identity fields, or permanent CI removals requires **all** of:

1. Dedicated migration issue
2. Compatibility adapter or dual-read period
3. Updated golden compatibility contracts + tests
4. Exact-head CI green
5. Explicit stakeholder impact review

Silent renames are forbidden.

---

## Classification legend

| Tag | Meaning |
|-----|---------|
| Frozen | Must not change without migration process above |
| Additive | New IDs/states allowed if they do not overload existing ones |
| Internal | Operator/lab only; not citizen primary |
| Historical | Evidence of past phases; not current truth |
