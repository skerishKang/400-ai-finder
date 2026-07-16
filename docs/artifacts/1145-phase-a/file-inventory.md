# #1145 Phase A — Page Agent file inventory

Worktree: `D:/work/400-ai-finder-1145`  
Branch: `feat/1145-page-agent-final-parity`  
Base: `origin/main` @ `56ba7f9ba011996e5f78db1a01dadb9e8ee15e35`

## Page Agent dedicated surfaces (Phase A allowed)

| Path | Role |
|------|------|
| `src/web/examples/page-agent/resident/parity-scenarios.js` | Canonical browser scenario vocabulary (ids, triggers, navSteps, routeId, requiredVisible) |
| `src/web/examples/page-agent/resident/resident-mock-model.js` | Offline mock planner / fail-closed final route + content gate |
| `src/web/examples/page-agent/resident/resident-demo.js` | Resident UI bootstrap, cancel, mobile surfaces |
| `src/web/examples/page-agent/resident/resident-demo.css` | Resident layout styles |
| `src/web/examples/page-agent/resident/resident-server-plan-client.js` | Optional same-origin plan client (server mode disabled by default) |
| `src/web/examples/page-agent/resident/index.html` | Resident entry |
| `src/web/examples/page-agent/parity-contract.json` | Shared parity scenario contract |
| `src/web/examples/page-agent/vendor/**` | Vendored Page Agent runtime (**do not modify**) |
| `functions/api/page-agent/_parity_scenarios.js` | Server plan vocabulary mirror |
| `functions/api/page-agent/_adapter.js` | Server adapter boundary |
| `functions/api/page-agent/_schema.js` | Plan schema |
| `functions/api/page-agent/_providers.js` | Provider boundary (disabled offline) |
| `functions/api/page-agent/plan.js` | Plan endpoint |
| `scripts/run_page_agent_comparison.mjs` | Stage 3 comparison harness |
| `scripts/merge_comparison_evidence.mjs` | Evidence merge helper |
| `tests/fixtures/page_agent_comparison_expectations.json` | Mode-specific expected routes / nav steps |
| `tests/test_page_agent_comparison_contract.py` | Offline contract tests |
| `tests/test_page_agent_comparison_evidence.py` | Evidence schema contracts |
| `tests/test_page_agent_final_route_parity.py` | #1145 final-route fail-closed contracts (Phase A) |
| `tests/test_page_agent_lab.py` | Lab isolation contracts |
| `tests/browser/verify_resident_mock_model.mjs` | Mock model unit browser tests |
| `tests/browser/verify_resident_e2e.mjs` | Resident e2e (desktop/mobile) |
| `tests/browser/verify_page_agent_*.mjs` | Lab / production-gap browser tests |
| `src/web/compare/index.html` | Stakeholder comparison chooser (existing) |
| `docs/artifacts/1145-phase-a/**` | Phase A evidence + notes |

## Shared surfaces used by Page Agent (read-only in Phase A)

These are loaded by the resident route but **must not be edited** while PR #1182 is open:

| Path | Why blocked |
|------|-------------|
| `src/web/static/citizen-action-demo-canvas.js` | #1182 / shared canvas renderer |
| `src/web/static/citizen-action-demo-canvas.css` | #1182 shared styles |
| `src/web/static/citizen-action-demo.html` | Shared demo entry |
| `scripts/build_cloudflare_pages.py` | Shared build |
| `.github/workflows/mvp-contracts.yml` | Shared CI |
| `src/web/static/bukgu-home-clone-fixture.js` | #1170 fixture |
| Home fixture generators / home contract tests | #1170 |

`citizen-action-demo-map.js` is shared closed vocabulary but **not** on the #1182 forbidden list. Phase A did not need map edits; targets already exist on main.

## Fixed expected final routes

| Scenario | Final route |
|----------|-------------|
| apartment_contact | apartment-dept |
| bulky_waste_menu | bulky-waste-disposal |
| passport_procedure | passport-guidance |
| complaint_screen | complaint-write |
| mayor_proposal_writing | mayor-complaint-write |

## Forbidden success interpretations

- `civil-service` as final success
- `complaint-category` as final success
- generic `official-content` as final success
- text-only keyword hits without exact route id
- navSteps finished ⇒ unconditional `success=true`
- detector-only success without mock `done(success=true)`

## navSteps vs deterministic choreography (current)

| Scenario | Page Agent navSteps | Notes |
|----------|---------------------|-------|
| apartment_contact | `nav-apartment-dept` | Direct home field-info target → apartment-dept |
| bulky_waste_menu | `nav-bulky-waste-disposal` | Direct home target |
| passport_procedure | `nav-passport-guidance` | Direct home target |
| complaint_screen | `nav-complaint-board` → `complaint-write` | Must not stop on board |
| mayor_proposal_writing | `mayor-office-open` → `mayor-message-write` | Full write surface |

Historical audit failure mode (early done after `nav-civil-service`) is locked out by scenario targets + final-route gate.

## getCurrentRouteId boundary

- Public API: `window.CitizenActionDemoCanvas.getCurrentRouteId()`
- Resident mock reads it after all navSteps complete
- Comparison harness prefers API route over class heuristics
- `_currentRouteId` updates synchronously on click; DOM fade may lag content (content also checked via browser_state text)

## Phase B deferred (after #1182 merge)

- Wire any new compare docs into CI / build script if needed
- Canvas semantic targets only if still missing after #1170 renderer lands
- Shared HTML/CSS integration polish
- Re-run 3-repetition stakeholder evidence pack on merged main
