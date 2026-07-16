# #1145 Phase A notes

## Starting point on origin/main

Main already contained substantial Page Agent parity scaffolding:

- Direct final-route nav targets (not `nav-civil-service` early stop)
- Mock final-route check via `getCurrentRouteId`
- Closed map targets for apartment / bulky / passport / complaint-board
- Resident e2e + comparison harness

Audit baseline (1/5 Page Agent) described the pre-fix intermediate-done path. On current main + Phase A hardening, Page Agent reaches true final routes.

## Phase A changes

1. **Fail-closed mock plans**
   - Exact expected route required
   - Forbidden intermediate routes rejected
   - `requiredVisible` content (any-of) required before `success=true`

2. **Comparison harness detector hardening**
   - Prefer `CitizenActionDemoCanvas.getCurrentRouteId()`
   - Route criteria are exact (`routeMatchesExact`) — no text-only route pass
   - Page Agent success also requires mock `lastSuccess === true`

3. **Contracts / fixtures**
   - Expectations carry `required_visible_any` + `forbidden_intermediate_routes`
   - New offline test module `tests/test_page_agent_final_route_parity.py`
   - Browser mock unit tests for success + intermediate failure paths

4. **Docs / evidence**
   - Inventory + this note
   - Comparison evidence under `docs/artifacts/1145-phase-a/`

## Safety counters (Phase A)

- live provider calls: 0
- API keys: 0
- Firecrawl: 0
- actual 북구청 site: 0
- external navigation: 0
- arbitrary model JS: 0

## Shared integration blockers

None required for current 5-scenario offline path on main canvas targets.

If future canvas refactor removes home field-info targets, Phase B must restore semantic targets in canvas (shared file) after #1182 merge — record as `blocked shared integration` if reintroduced.
