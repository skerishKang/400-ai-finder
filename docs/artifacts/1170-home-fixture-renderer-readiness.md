# #1170 Home fixture canvas renderer readiness

**Status:** structural fixture renderer wired
**Home route clone status:** `capture_required` (unchanged)
**Exact clone claim:** **not made**
**Actual-site Stage 5:** deferred
**Unresolved assets:** **174** (exact local mapping still 0)

Governing policy: [`docs/product/exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md).

This report describes wiring the committed #1166/#1168 canonical home fixture into the MVP clone canvas via **build-time browser projection**. It does **not** claim exact visual parity with the live official homepage.

## Architecture

```text
data/official_clone_fixtures/bukgu_gwangju/home.json
    ↓ scripts/generate_bukgu_home_clone_fixture.py
src/web/static/bukgu-home-clone-fixture.js
    ↓ window.__BUKGU_HOME_CLONE_FIXTURE__
citizen-action-demo-canvas.js home renderer
```

| Item | Path / value |
|------|----------------|
| Generator | `scripts/generate_bukgu_home_clone_fixture.py` |
| Browser projection | `src/web/static/bukgu-home-clone-fixture.js` |
| Global name | `window.__BUKGU_HOME_CLONE_FIXTURE__` |
| Script load order | `bukgu-official-snapshots.js` → `bukgu-home-clone-fixture.js` → `map` → `canvas` |
| Renderer entry | `_renderHome` → `_getCanonicalHomeFixture` / `_renderHomeFixtureRegion` |
| CSS | `src/web/static/citizen-action-demo-canvas.css` (`.bg-home-fixture-*` under `.bg-page--home`) |
| Build gate | `scripts/build_cloudflare_pages.py` fails when projection is stale |

### Runtime constraints

- No browser `fetch` of fixture JSON
- No remote `img src` for unresolved official assets (`data-source-asset-url` only)
- Fail-closed unavailable surface when projection is missing/invalid (no synthetic official fallback)

## Canonical fixture identity

| Field | Value |
|-------|--------|
| fixture_id | `bukgu_gwangju.home.clone.2026-07-15` |
| fixture_sha256 | `81b27b98fadc091ca852079f89ea93da45b93f250372835b8b352726b2faeaed` |
| clone_status | `capture_required` |
| exact_clone_claimed | `false` |
| projection generator | `1.0.0` |

Regeneration:

```powershell
python scripts/generate_bukgu_home_clone_fixture.py
python scripts/generate_bukgu_home_clone_fixture.py --check
```

## Rendered regions

Required order:

1. `utility_navigation`
2. `main_banner`
3. `resident_service_shortcuts`
4. `notice_news`
5. `related_site_controls`
6. `footer_identity_contact`

| Region | Items | Variants (fixture) |
|--------|------:|--------------------|
| utility_navigation | 21 | desktop 18 / hidden 3 (ENG/CHN/JPN) |
| main_banner | 31 | desktop 31 |
| resident_service_shortcuts | 14 | desktop 14 |
| notice_news | 36 | desktop 36 (6 groups) |
| related_site_controls | 21 | desktop 21 |
| footer_identity_contact | 8 | desktop 8 |

Hidden language items remain in DOM with `display:none` / non-focusable; they are not deleted and not promoted to desktop.

## Page Agent target mapping

Exact evidence only (closed label + href). Existing target IDs preserved.

| Action target | Source | Exact text | Exact href | Item / nav id |
|---------------|--------|------------|------------|---------------|
| `nav-civil-service` | navigation | 종합민원 | `/menu.es?mid=a10101000000` | nav-0030 |
| `nav-complaint-board` | navigation | 소통광장 | `/menu.es?mid=a10201000000` | nav-0064 |
| `nav-apartment-dept` | navigation | 행정조직도 | `/menu.es?mid=a10602010000` | nav-0521 |
| `nav-passport-guidance` | navigation | 여권 발급 | `/menu.es?mid=a10101060200` | nav-0523 |
| `nav-bulky-waste-disposal` | region_item | 대형폐기물 | `/menu.es?mid=a10406070000` | resident_service_shortcuts-0010 |
| `mayor-office-open` | navigation | 열린구청장실바로가기 | `/mayor/` | nav-0368 |

Navigation-backed targets render in a local compatibility strip (`data-home-compat-targets`) so Page Agent journeys keep stable `data-action-target` IDs without inventing synthetic official chrome.

### Unmapped / blockers

- No unmapped blockers among the six production-gap home targets above.
- Field-info synthetic labels such as historical "대형폐기물 처리" / decorative quick icons are **not** recreated; fixture text wins.
- 174 assets remain unresolved — no emoji/icon/remote substitution.

## Link safety

- Cross-origin items: inert (`span`, no `data-action-target`, no `window.open`)
- Same-origin items without closed route mapping: inert metadata only
- Same-origin items with exact mapping: local canvas action (`href="#"` + `data-action-target`)

## Verification

```powershell
python scripts/generate_bukgu_home_clone_fixture.py --check
pytest tests/test_bukgu_home_clone_fixture_projection.py tests/test_home_fixture_canvas_parity.py -q
pytest tests/test_current_bukgu_home_top_contract.py tests/test_current_bukgu_home_lower_contract.py tests/test_current_bukgu_home_full_state_contract.py -q
pytest tests/test_build_cloudflare_pages.py tests/test_citizen_action_demo_canvas.py -q
node tests/browser/verify_home_fixture_canvas_e2e.mjs
node tests/browser/verify_mvp_shell_runtime.mjs
```

Browser viewports: desktop 1440×1000, mobile 390×844.

Expected counters:

```text
external requests = 0
external navigations = 0
console/page/request errors = 0
form/login/payment/PII = 0
```

## Remaining exact-clone blockers

1. Home remains `capture_required` (not exact).
2. Exact visual parity not claimed.
3. **174** official assets unresolved (no exact local full-file identity).
4. Actual-site Stage 5 deferred.
5. Official header/GNB full visual reconstruction beyond the six regions + compatibility strip is not claimed.
6. Dynamic notice board bodies that are JS-fed on the live site remain limited to committed HTML labels/links.

## Explicit non-claims

```text
structural fixture renderer wired
home remains capture_required
exact visual parity not claimed
174 assets remain unresolved
actual-site Stage 5 deferred
No official-site/network access
No live provider/API/Firecrawl
No asset download
No real civic submission
No login/payment/PII
```
