# ADR: Clone-first multi-site platform (Buk-gu golden first)

| Field | Value |
|-------|--------|
| Status | **Accepted** for planning and compatibility gates (docs-only at #1188) |
| Date | 2026-07-16 |
| Issue | [#1188](https://github.com/skerishKang/400-ai-finder/issues/1188) |
| Freeze decision | [#1187](https://github.com/skerishKang/400-ai-finder/issues/1187) — READY TO FREEZE |
| Golden baseline | `7217c0f738a6aa4468bdde3119d8c2d1ec9dd610` (`fix(a11y): hide decorative AI labels in clone controls (#1186)`) |
| Companion contract | [`docs/bukgu-golden-compatibility-manifest.md`](../bukgu-golden-compatibility-manifest.md) |
| Parent platform track | [#1181](https://github.com/skerishKang/400-ai-finder/issues/1181) (multi-site platform — **not implemented by this ADR**) |

---

## Status

This ADR records an **architecture decision** and **compatibility-first migration
rules**. It does **not** implement SiteSpec schemas, generic compilers, or a
second municipal adapter. Runtime code remains Buk-gu-shaped at the golden SHA.

---

## Context

400-ai-finder currently ships a **controlled clone-first Buk-gu product**:

- chat-first citizen entry with deterministic civic journeys
- fixture-backed home clone surface (`#1170`) plus closed route vocabulary
- optional vendored Page Agent resident path with **deterministic mock** comparison
- permanent offline CI contracts and no-submit / no-actual-site-control safety

Stakeholders need a durable golden reference. Product strategy also needs a path
to multi-site operation (#1181) **without** breaking the frozen Buk-gu demo.

Risks if we do not decide now:

1. Silent renames of routes, action targets, state attributes, or public APIs
2. Treating “fixture-backed clone” as “full exact official clone of every route”
3. Folding deferred tracks (#1080, #1150 live, #862 live navigator, Stage 5) into
   platform extraction and destabilizing the golden demo
4. Making Page Agent mandatory for every future site

---

## Decision

1. **Buk-gu is the first golden reference adapter**, not the permanent identity
   of the product.
2. **400-ai-finder is not permanently Buk-gu-only.** Future multi-site work must
   be extracted so the frozen Buk-gu product continues to pass golden contracts.
3. **Compatibility-first:** preserve golden URLs, closed route IDs, action
   targets, DOM contracts, choreography/plan states, public window APIs, fixture
   provenance rules, and permanent CI before introducing generic layers.
4. **Native deterministic AI Finder remains first-class.** Page Agent is an
   optional runtime path; comparison declares **no winner**.
5. **Platform implementation is a separate track** from exact-fixture expansion,
   live retrieval, live official-site control, and live LLM Stage 5.

---

## Golden baseline

| Item | Value |
|------|--------|
| Repository | `skerishKang/400-ai-finder` |
| Commit | `7217c0f738a6aa4468bdde3119d8c2d1ec9dd610` |
| Freeze | Issue #1187 READY TO FREEZE |
| Compatibility manifest | `docs/bukgu-golden-compatibility-manifest.md` |

### This baseline means

- controlled clone-first product
- deterministic civic journeys
- fixture-backed Buk-gu clone surface
- vendored Page Agent + deterministic resident mock adapter
- canonical offline comparison evidence
- permanent CI contracts
- no-submit / no-live-provider-in-golden-comparison / no-actual-site-control

### This baseline does **not** mean

- not a complete exact clone of every current official-site route
- not a live LLM quality comparison
- not actual Buk-gu site control or real civic submission
- not live answer-time official retrieval
- not multi-site platform implementation completed

Exact-clone policy for civic surfaces:
[`docs/product/exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md).
Home fixture identity may still record `exact_clone_claimed=false` /
`capture_required` (fixture-backed renderer ≠ full exact official clone).

---

## Architecture boundaries (layers)

Layers are named for future extraction. **Do not invent presence.**

| Layer | Exists today? | Current Buk-gu owner (examples) | Extraction seam | Not yet implemented | Forbidden exaggeration |
|-------|---------------|---------------------------------|-----------------|---------------------|------------------------|
| SiteSpec / onboarding input | Partial / profile-shaped only | site profile configs, municipal crawl filter configs | `configs/`, site profile modules | Portable SiteSpec schema for arbitrary cities | “SiteSpec compiler already ships” |
| Authorized / public reference capture | Yes (local artifacts) | `data/official_captures/…`, design reference ledgers | capture inventory + authorization docs | Automated multi-site capture service | Live recapture in CI |
| Route / content inventory | Planning + closed demo vocabulary | `#862` planning docs; `CLOSED_ROUTE_IDS` (17) | map vocabulary + inventory schemas | Full official inventory dataset for all routes | “14-route inventory is production closed set” |
| Generic Site Model | No | Implicit in map + canvas + quests | Interface over routes/targets/content | Shared model types | Treating Buk-gu map as generic API |
| Clone compiler | Partial (home only) | `generate_bukgu_home_clone_fixture.py` | generator boundary | Multi-page / multi-site compiler | Hand-editing generated JS |
| Asset pipeline | Yes (home-focused) | fixture JSON → projection JS; asset identity audits | identity + generator | Full unresolved-asset resolution for all pages | Remote `img` in controlled demo |
| Knowledge / index layer | Partial offline | snapshots, quest content, crawl/index modules | offline knowledge sources | Answer-time live official retrieval (#1150 deferred) | Claiming Phase 1 already enables live answer-time retrieval |
| Action graph | Yes (closed, Buk-gu) | `CLOSED_TARGET_IDS` (28), canvas producers, executor | target ID + navigate contracts | Generic action graph DSL | Silent target renames |
| Deterministic AI Finder runtime | Yes | shell, choreography, canvas, MVP ask path (mode-dependent) | shell/canvas public APIs | Fully site-parameterized runtime | Claiming all sites share current hard-coded routes |
| Optional Page Agent runtime | Yes (vendored) | `examples/page-agent/**`, resident mock | parity scenarios + mock adapter | Live LLM Stage 5 quality validation | “Page Agent is the only product path” |
| Reviewable clone deployment | Yes | `build_cloudflare_pages.py` static/live packaging | build output contract | Multi-tenant deploy matrix | Live build == live network in CI |
| Automated QA | Yes | `.github/workflows/mvp-contracts.yml` + offline pytest/browser | permanent CI contracts | Generic multi-site CI matrix | Calling local-only tests “permanent CI” |

---

## Buk-gu-specific responsibilities

These stay **adapter-owned** until an extraction issue lands:

| Area | Current owners |
|------|----------------|
| Closed route vocabulary (17 IDs) | `src/web/static/citizen-action-demo-map.js` |
| Closed action targets (28 IDs) | same map + canvas producers |
| Home clone fixture identity | `data/official_clone_fixtures/bukgu_gwangju/home.json` + generator |
| Home browser projection | `src/web/static/bukgu-home-clone-fixture.js` (**generated**) |
| Civic visual renderer | `citizen-action-demo-canvas.js` |
| Civic copy / quest content | quest registry, official snapshots, canvas strings |
| Parity scenario → route mappings | `parity-scenarios.js` / expectations fixture |
| Mayor / complaint / housing journeys | shell + choreography + journey modules |
| Buk-gu safety stop surfaces | `handoff-stop`, disabled submit, pre-submit receipts |

---

## Generic extraction seams (evidence-based only)

Candidates that already have a **clear seam** in the golden tree:

| Seam | Evidence | Notes |
|------|----------|-------|
| Site profile / municipal config | `configs/`, crawl filter contracts, profile onboarding docs | Onboarding boundary docs exist; not a full SiteSpec |
| Capture → canonical fixture → generator → browser artifact | home pipeline | Proven pattern for other pages later |
| Closed route/target interface | map `isKnownRoute` / `isKnownTarget` | Generic interface can wrap, not rename, Buk-gu IDs |
| Canvas public API | `window.CitizenActionDemoCanvas` | Consumers already depend on freeze surface |
| Shell / choreography state axes | `data-first-use-state`, `data-journey-state`, `data-choreography-state` | Additive states only with tests |
| Safety policy | no-submit, no external nav in controlled tests, fail-closed | Must remain site-agnostic policy |
| Comparison / QA framework | Stage 3 harness, expectations schema, permanent CI steps | Modes stay equal; no winner |
| Deployment packaging | Cloudflare Pages builder modes | Static default for offline contracts |

Do **not** record seams that only exist as future issues without code.

---

## Native AI Finder and Page Agent

| Principle | Rule |
|-----------|------|
| Deterministic / native implementation | **First-class product path** for civic journeys |
| Page Agent | **Optional** runtime for supported surfaces; not mandatory for every future site |
| Comparison | Two equal primaries on `/compare/`; **no winner declaration** |
| Future adapters | May ship native only, Page Agent only, or both — with contracts per adapter |
| Golden comparison model | Deterministic mock adapter — **not** live LLM quality validation |
| Stage 5 | Blocked / not executed on golden CI; separate approval track |

---

## Compatibility rules

Full tables live in the [golden compatibility manifest](../bukgu-golden-compatibility-manifest.md). Summary:

1. **URLs:** `/`, `/mvp/`, `/compare/`, `/examples/page-agent/resident/` stay stable for golden demos.
2. **Routes / targets:** closed sets are freeze surfaces; additive only with map + renderer + tests.
3. **DOM / state attributes:** no silent renames of IDs or vocabulary values.
4. **Public window APIs:** freeze surface; internal helpers are not public contracts.
5. **Fixtures:** never hand-edit generated projection; change via canonical JSON + generator.
6. **Evidence:** Phase B / `1109-stage3-comparison` is canonical; `1145-phase-a` is historical only.
7. **CI:** only steps in `mvp-contracts.yml` are “permanent CI.”

### Breaking-change rule

No route / action / state / API / schema rename without **all** of:

1. dedicated migration issue
2. compatibility adapter or versioning plan
3. updated golden contracts and tests
4. exact-head CI green
5. explicit stakeholder impact review

---

## Compatibility-first migration sequence

Each step must leave the Buk-gu golden demo green.

| Step | Action | Exit criteria |
|------|--------|---------------|
| 1 | Golden compatibility manifest + this ADR (#1188) | Docs + small consistency contracts |
| 2 | Pure schema / interface extraction (no behavior change) | Types/interfaces only; Buk-gu still sole consumer |
| 3 | Wrap current Buk-gu implementation as **reference adapter** | Same URLs/routes/targets/states |
| 4 | Preserve golden contracts during refactors | Manifest still true; permanent CI green |
| 5 | Introduce **generic tests beside** existing Buk-gu tests | No replacement of Buk-gu suites |
| 6 | Onboard a **second synthetic or approved** site | Explicit approval; safety policy intact |
| 7 | Only then broader migration / multi-tenant packaging | Stakeholder review |

Skipping to step 6–7 without 1–5 is out of policy.

---

## Separate / deferred tracks (do not mix into #1181 runtime extraction)

| Track | Issue / note | Relationship to this ADR |
|-------|--------------|---------------------------|
| Exact fixture long-term program | #1080 | Expands fidelity; must not break closed vocabulary |
| Official freshness / retrieval | #1150 — Phase 1 mocked/offline/fail-closed; **live retrieval deferred** | Phase 1 completion does **not** mean live answer-time retrieval is enabled |
| Official-site navigator / live integration | #862 parent | Live actual-site control is **not** golden |
| Full rebuild / integration | #873 parent | Separate product rebuild track |
| Multi-site platform parent | #1181 | Consumes this ADR; not implemented here |
| Live LLM Stage 5 | comparison roadmap | Blocked until clone + approval gates |
| Actual-site operational control | product intent, gated | Outside golden freeze |

### #1150 boundary (docs alignment)

| Phase | Meaning |
|-------|---------|
| Phase 1 (present boundary) | mocked / offline / fail-closed backend boundary |
| Deferred | real official DOM validation, production transport, answer-time retrieval, resident UI live integration |

### Renderer vs fixture identity (docs alignment)

| Concept | Current golden fact |
|---------|---------------------|
| Runtime home renderer | **Wired** (#1170) on canvas |
| Fixture identity field `status` / generator vocabulary | May still say `fixture_ready_renderer_not_wired` inside identity-frozen blobs |
| `capture_required` / `exact_clone_claimed=false` | Orthogonal to “renderer wired”; do not flip casually |
| Fix path | Canonical JSON + generator + identity program — **not** hand-edit of generated JS |

### Route inventory wording

- **Closed demo route vocabulary today:** **17** IDs in `CLOSED_ROUTE_IDS` (includes `home`).
- Historical design reports (e.g. early #863 six-route tables) and smoke-eval “14 scenarios” are **not** the production closed route set.
- GitHub issue bodies (#1080, #1181) are not edited from this branch.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Platform work renames Buk-gu IDs | Breaking-change rule + dual-read adapters |
| Docs claim full exact clone | Manifest non-claims + exact-clone invariant discipline |
| Live retrieval folded into golden CI | Keep Stage 5 / live provider blocked in golden comparison |
| Page Agent becomes mandatory | Explicit optional runtime principle |
| Historical Phase A rewritten as current | Canonical = 1109 / Phase B notes; Phase A read-only |
| Fixture identity hand-edits | Generator-only rule + asset identity `--check` |

---

## Consequences

### Positive

- Clear freeze surface for regression reviewers and CI owners
- Explicit multi-site direction without claiming completion
- Separates adapter extraction from live/exact/Stage-5 work

### Negative / cost

- Multi-site features move slower (compatibility first)
- Some fixture metadata strings may remain historically worded until a regeneration program
- Second site cannot ship until steps 1–5 complete

### Neutral

- Native + Page Agent dual path continues on Buk-gu golden
- Cloudflare static packaging remains the offline contract vehicle

---

## Non-goals

This ADR does **not**:

- implement #1181 runtime or a second municipal product
- recapture official pages or expand #1080 fixtures
- enable #1150 live answer-time retrieval
- implement #862 actual-site navigator control
- run or authorize Stage 5 live LLM validation
- rename routes, action targets, states, or public APIs
- declare a winner between deterministic and Page Agent paths
- claim that fixture-backed home equals exact clone of every official route

---

## References

- [`docs/bukgu-golden-compatibility-manifest.md`](../bukgu-golden-compatibility-manifest.md)
- [`docs/product/exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md)
- [`docs/page-agent-stage3-comparison-report.md`](../page-agent-stage3-comparison-report.md)
- [`docs/artifacts/1145-phase-b/phase-b-notes.md`](../artifacts/1145-phase-b/phase-b-notes.md)
- [`docs/artifacts/1109-stage3-comparison/comparison-evidence.json`](../artifacts/1109-stage3-comparison/comparison-evidence.json)
- [`docs/artifacts/1145-phase-a/`](../artifacts/1145-phase-a/) (historical only)
- [`docs/live-transition-decision-record.md`](../live-transition-decision-record.md)
- [`docs/hybrid-scripted-llm-architecture-intent.md`](../hybrid-scripted-llm-architecture-intent.md)
- [`.github/workflows/mvp-contracts.yml`](../../.github/workflows/mvp-contracts.yml)
