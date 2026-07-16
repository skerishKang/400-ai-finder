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
| `mayor-complaint-receipt` | Local simulated/demo receipt | map + canvas | **Not** an official receipt; no external submission occurred | Frozen safety |
| `bulky-waste-disposal` | Guidance terminal | map + official snapshot content | Bulky waste | Frozen |
| `passport-guidance` | Guidance terminal | map + official snapshot content | Passport | Frozen |
| `unmanned-kiosk-guidance` | Guidance terminal | map + official snapshot content | Kiosk | Frozen |
| `apartment-info` | Guidance | map + canvas | Apartment info | Frozen |
| `apartment-dept` | **Terminal** dept surface | map + canvas + dept journey | Housing contact / dept | Frozen terminal |

**Breaking-change rule:** no silent rename/removal of any closed route ID without a dedicated migration issue, dual mapping period, updated golden contracts, and exact-head CI.

**Additive rule:** new routes require map vocabulary update + renderer + tests; must not repurpose existing IDs.

---

## 3. Complete closed action-target vocabulary

**Source of truth:** `CLOSED_TARGET_IDS` in `citizen-action-demo-map.js`.

**Count at golden SHA:** **28** closed target IDs (complete set — every ID is listed below; do not treat this as a selected subset).

**DOM producer owner:** `citizen-action-demo-canvas.js` (and home fixture projection for home-region nav targets) via `data-action-target`.

**Navigation owner:** canvas `_targetToNextRoute` / special-case handlers (and category → `complaint-intake` branch).

**Breaking-change rule (all rows):** no silent rename/removal of any target ID without a dedicated migration issue, dual mapping or versioning plan, updated golden contracts/tests, exact-head CI, and stakeholder impact review.

| Target ID | Producer / owner | Consumer or journey | Next route or non-navigation behavior | Classification | Breaking-change rule |
|-----------|------------------|---------------------|---------------------------------------|----------------|----------------------|
| `nav-civil-service` | Canvas home GNB / fixture home | Civil-service entry; executor choreography | → `civil-service` | **Frozen** | Migration issue required |
| `nav-apartment-dept` | Home fixture region / home nav | Housing parity (`apartment_contact`) | → `apartment-dept` | Frozen | Migration issue required |
| `nav-bulky-waste-disposal` | Home fixture region / home nav | Bulky parity (`bulky_waste_menu`) | → `bulky-waste-disposal` | Frozen | Migration issue required |
| `nav-passport-guidance` | Home fixture region / home nav | Passport parity (`passport_procedure`) | → `passport-guidance` | Frozen | Migration issue required |
| `nav-complaint-category` | Civil-service LNB | Category tree entry | → `complaint-category` | Frozen | Migration issue required |
| `nav-complaint-board` | Home GNB / fixture | Complaint parity step 1 | → `complaint-board` | Frozen | Migration issue required |
| `complaint-category-illegal-parking` | Category cards (canvas) | Illegal-parking category selection | → `complaint-intake` (stores selected category) | Frozen | Migration issue required |
| `complaint-category-public-parking-inconvenience` | Category cards (canvas) | Public-parking category selection | → `complaint-intake` | Frozen | Migration issue required |
| `complaint-category-residential-parking` | Category cards (canvas) | Residential-parking category selection | → `complaint-intake` | Frozen | Migration issue required |
| `complaint-category-traffic-or-facility-safety` | Category cards (canvas) | Traffic/facility category selection | → `complaint-intake` | Frozen | Migration issue required |
| `complaint-category-other-or-unsure` | Category cards (canvas) | Other/unsure category selection | → `complaint-intake` | Frozen | Migration issue required |
| `complaint-illegal-parking-report` | Illegal-parking guidance card | Parking journey handoff | → `handoff-stop` (no real report submit) | Frozen safety | Migration issue required |
| `complaint-write` | Board write control (`#btn-board-write`) | Complaint parity step 2 | → `complaint-write` | Frozen | Migration issue required |
| `complaint-board-return` | Complaint write “이전으로” | Return from write form | → `complaint-board` | Frozen | Migration issue required |
| `mayor-office-open` | Home fixture / shell / `#btn-open-mayor-office` | Mayor parity + mayor E2E + a11y | → `mayor-office` | Frozen | Migration issue required |
| `mayor-message-write` | Mayor office CTA | Mayor proposal writing choreography | → `mayor-complaint-write` (then may start `mayor_message_assist`) | Frozen | Migration issue required |
| `mayor-write-return` | Mayor write “이전으로” | Return from mayor form | → `mayor-office` | Frozen | Migration issue required |
| `mayor-receipt-home` | Local simulated receipt UI | Demo-only return home | → `home` | Frozen safety | Migration issue required |
| `complaint-body` | Intake / write textarea | Executor prefill / draft highlight | **Non-navigation** form field (no route change) | Frozen | Migration issue required |
| `complaint-draft-review` | Intake form link | Review path | → `complaint-review` | Frozen | Migration issue required |
| `confirm-draft-prefill` | Disabled submit-like control | Safety boundary (must stay non-submitting) | → `handoff-stop` when activated in flow; control remains disabled for real submit | Frozen safety | Migration issue required |
| `handoff-notice` | Handoff / safety-stop UI | Explicit no-submit handoff | → `handoff-stop` | Frozen safety | Migration issue required |
| `bulky-waste-guidance-card` | Bulky guidance page card | Bulky guidance highlight / choreography | **Non-navigation** surface anchor (route already `bulky-waste-disposal`) | Frozen | Migration issue required |
| `passport-guidance-card` | Passport guidance page card | Passport guidance highlight | **Non-navigation** surface anchor | Frozen | Migration issue required |
| `unmanned-kiosk-card` | Kiosk guidance page card | Kiosk guidance highlight | **Non-navigation** surface anchor | Frozen | Migration issue required |
| `apartment-guidance-card` | Apartment-info page card | Apartment info highlight | **Non-navigation** surface anchor | Frozen | Migration issue required |
| `apartment-dept-card` | Apartment-dept official table | Housing dept terminal highlight | **Non-navigation** surface anchor (route `apartment-dept`) | Frozen | Migration issue required |
| `apartment-life-card` | Apartment-info life card | Apartment info secondary card | **Non-navigation** surface anchor | Frozen | Migration issue required |

**Additive rule:** new targets require map `CLOSED_TARGET_IDS` + canvas producer + tests; must not repurpose existing IDs.

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

Export source of truth: `window.* = Object.freeze({...})` in each owner file.
Internal helpers that are not exported are **not** public API.

### `window.CitizenActionDemoMap` (`citizen-action-demo-map.js`)

| Method | Owner | Known consumers | Classification | Breaking-change requirement |
|--------|-------|-----------------|----------------|------------------------------|
| `getRouteIds` | map.js | canvas, tests, docs contracts | **Frozen public** | Migration issue + dual-read |
| `getTargetIds` | map.js | canvas, tests, docs contracts | Frozen public | Migration issue + dual-read |
| `getRoute` | map.js | canvas click/category flow | Frozen public | Migration issue + dual-read |
| `getCategoryLabel` | map.js | canvas category labels | Frozen public | Migration issue + dual-read |
| `isValidRoute` | map.js | canvas navigation guards | Frozen public | Migration issue + dual-read |
| `isValidTarget` | map.js | canvas click delegation | Frozen public | Migration issue + dual-read |

Closed-vocabulary validation uses `isValidRoute` / `isValidTarget` only.

### `window.CitizenActionDemoCanvas` (`citizen-action-demo-canvas.js`)

| Method | Owner | Known consumers | Classification | Breaking-change requirement |
|--------|-------|-----------------|----------------|------------------------------|
| `navigateToRoute` | canvas.js | shell, choreography, executor, Page Agent, tests | **Frozen public** | Migration issue + dual-read |
| `getCurrentRouteId` | canvas.js | journeys, executor, tests | Frozen public | Migration issue + dual-read |
| `hasRoute` | canvas.js | consumers checking route availability | Frozen public | Migration issue + dual-read |
| `getTargetElement` | canvas.js | executor highlight/click, tests | Frozen public | Migration issue + dual-read |
| `showCursorAt` | canvas.js | choreography cursor | Frozen public | Migration issue + dual-read |
| `hideCursor` | canvas.js | choreography cancel/cleanup | Frozen public | Migration issue + dual-read |
| `clickAnimation` | canvas.js | choreography click cue | Frozen public | Migration issue + dual-read |
| `fitToViewport` | canvas.js | mobile/desktop fit, resize | Frozen public | Migration issue + dual-read |

### Other frozen globals

| API | Owner | Known consumers | Classification | Breaking-change requirement |
|-----|-------|-----------------|----------------|------------------------------|
| `window.CitizenFirstUseShell` | shell.js | canvas, tests | Frozen public | Migration issue + dual-read |
| `window.CitizenFirstChoreography` | choreography.js | shell, canvas, tests | Frozen public | Migration issue + dual-read |
| `window.__BUKGU_HOME_CLONE_FIXTURE__` | generated projection | canvas home | Frozen global name | Generator + identity program |
| `window.__BUKGU_OFFICIAL_SNAPSHOTS__` | snapshots | canvas official routes | Frozen global name | Migration issue |
| `window.PageAgentMockModel` | resident-mock-model.js | resident, comparison | Frozen mock diagnostics | Migration issue |
| `window.PageAgentParityScenarios` | parity-scenarios.js | mock model | Frozen scenario vocabulary | Migration issue |
| `window.PageAgentResidentRuntime` | resident-demo.js | tests/diagnostics | Frozen read-only control | Migration issue |

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
| No real civic submission | Disabled submit; handoff-stop; `mayor-complaint-receipt` is a **local simulated/demo receipt route** only — **no external submission** occurred and it **must not** be interpreted as an **official receipt** or proof of submission |
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
