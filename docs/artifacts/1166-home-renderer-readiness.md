# #1166 Home renderer readiness

**Status:** canonical fixture preparation only  
**Home route clone status:** `capture_required` (unchanged)  
**Exact clone claim:** **not made**

Governing policy: [`docs/product/exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md) (`exact-official-site-clone-invariant.md`).

This report describes readiness after promoting the committed #1160 home capture inventory into a structured offline clone fixture. It does **not** claim that the product canvas renders an exact official homepage clone.

## Management mode

| Choice | Selected |
|--------|----------|
| A. Commit generator output + regeneration lock tests | **Yes** |
| B. Raw capture remains source-of-truth | **Yes (combined)** |

- **Source of truth:** `data/official_captures/bukgu_gwangju/home/*`
- **Generated fixture:** `data/official_clone_fixtures/bukgu_gwangju/home.json`
- **Generator:** `scripts/build_official_home_clone_fixture.py` (`GENERATOR_VERSION=1.0.0`)
- **Schema:** `schema_version=1`, `fixture_kind=official_home_clone_fixture`

Regeneration:

```powershell
python scripts/build_official_home_clone_fixture.py
python scripts/build_official_home_clone_fixture.py --check
```

## Source identity

| Field | Value |
|-------|--------|
| route_id | `home` |
| requested URL | `https://bukgu.gwangju.kr/` |
| final URL | `https://bukgu.gwangju.kr/` |
| title | 전남광주통합특별시 북구 |
| captured_at | `2026-07-15T17:12:33+09:00` |
| raw capture SHA-256 | `b47910217ecdb58b508cfd69d34a9a3a6e2c731f84a6db877ad01ebb04f5a6f5` |
| capture metadata SHA-256 | `52aa1a64745d6f6d570f03ef38a245ba6ba0b2475fbe3e8bbf032783ac06df5d` |
| generated fixture SHA-256 | `cbd933edd81f387e4462a7319ba594ef4cd8696986c0be0b1508e372de9d2110` |

## Counts

| Metric | Count |
|--------|------:|
| Capture hierarchy nodes | 2 |
| Regions total | 13 |
| Regions ready / fixture-ready | 7 |
| Regions unresolved | 6 |
| Navigation items | 722 |
| Blank navigation labels (from capture) | 2 |
| Assets total | 174 |
| Assets ready with local exact identity | 0 |
| Assets unresolved | 174 |

## Region readiness

Classification keys used:

- `ready` — capture hierarchy node with represented navigation
- `fixture-ready-renderer-not-wired` — deterministic capture evidence present; product renderer not wired to this fixture
- `unresolved` / `unresolved-dynamic-region` — no deterministic source boundary in #1160 inventory
- `unresolved-asset` — asset inventory row without exact local identity evidence
- `product-transition-not-official-content` — not applicable in this fixture slice (no product-only regions invented)

| Region | Status | Source evidence | Fixture path | Local assets | Remaining blocker |
|--------|--------|-----------------|--------------|--------------|-------------------|
| hierarchy_header | ready | navigation hierarchy `header` | `regions[hierarchy_header]` + header nav items | none exact | renderer not wired |
| hierarchy_footer | ready | navigation hierarchy `footer` | `regions[hierarchy_footer]` + footer nav items | none exact | renderer not wired |
| government_notice | fixture-ready-renderer-not-wired | nav label prefix from capture | `regions[government_notice]` | n/a | renderer not wired |
| site_identity_logo | fixture-ready-renderer-not-wired | nav order 3 (logo alt label) | `regions[site_identity_logo]` | logo image unresolved | renderer + exact logo asset |
| utility_navigation | unresolved | none | unresolved marker | n/a | no deterministic boundary vs header |
| global_navigation | fixture-ready-renderer-not-wired | section=`header` items | `navigation` where `region_identity=header` | CSS/images unresolved | renderer + assets |
| main_banner | unresolved | none | unresolved marker | n/a | capture hierarchy lacks main/banner node |
| resident_service_shortcuts | unresolved | none | unresolved marker | n/a | no deterministic boundary |
| notice_news | unresolved | none | unresolved marker | n/a | no deterministic boundary |
| related_site_controls | unresolved | none | unresolved marker | n/a | no deterministic boundary |
| footer_navigation | fixture-ready-renderer-not-wired | section=`footer` items | `navigation` where `region_identity=footer` | unresolved | renderer + assets |
| footer_identity_contact | unresolved | footer links only | unresolved marker | n/a | contact/copyright blocks not separately bounded |
| document_skip_and_misc | fixture-ready-renderer-not-wired | section=`document` items | document nav items | n/a | renderer not wired |

## Asset readiness

- Every #1160 asset inventory row is represented in the fixture (`assets` length 174).
- **Exact local mapping requires full-file identity evidence** (full SHA-256 match against a repo file, or hashed window that covers the entire file).
- Partial `first_65536_bytes` hashes are **not** treated as full-file identity.
- Current local exact mappings: **0**.
- All 174 assets remain `unresolved-asset` with explicit reasons.

## What this slice does **not** do

- Does not mark home as `exact` in the clone manifest
- Does not wire `CitizenActionDemoCanvas` / first-use UI to this fixture
- Does not download or re-fetch the official site
- Does not invent labels, contacts, phone numbers, or asset paths
- Does not claim that the home route is finished as an exact official clone

## Follow-up blockers (informational)

1. Deeper region segmentation from raw HTML with deterministic selectors (still offline from committed raw)
2. Exact local asset vendoring with full-file checksum evidence
3. Separate product PR to wire renderer read path — out of scope for #1166
