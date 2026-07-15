# #1166 / #1168 Home renderer readiness

**Status:** canonical fixture preparation + offline HTML region segmentation
**Home route clone status:** `capture_required` (unchanged)
**Exact clone claim:** **not made**
**Renderer:** **not wired**

Governing policy: [`docs/product/exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md) (`exact-official-site-clone-invariant.md`).

This report describes readiness after promoting the committed #1160 home capture inventory into a structured offline clone fixture (#1166) and resolving six plan regions from committed raw HTML only (#1168). It does **not** claim that the product canvas renders an exact official homepage clone.

## Management mode

| Choice | Selected |
|--------|----------|
| A. Commit generator output + regeneration lock tests | **Yes** |
| B. Raw capture remains source-of-truth | **Yes (combined)** |

- **Source of truth:** `data/official_captures/bukgu_gwangju/home/*`
- **Generated fixture:** `data/official_clone_fixtures/bukgu_gwangju/home.json`
- **Generator:** `scripts/build_official_home_clone_fixture.py` (`GENERATOR_VERSION=1.1.0`)
- **HTML parser:** `src/official_clone/home_region_parser.py` (`parser_version=1.0.0`)
- **Schema:** `schema_version=1`, `fixture_kind=official_home_clone_fixture`

### Fragment hash rule

`canonical_subtree_serialization_v1`:

- Preorder walk of the selected element subtree
- Emit `E|<tag>|<id or ->|<classes>|<sorted k=v attrs>` lines
- Emit `T|<normalized own text>` when non-empty
- Skip `script` / `style` subtrees for content walks
- `fragment_sha256 = SHA-256(UTF-8 serialization)`

Regeneration:

```powershell
python scripts/build_official_home_clone_fixture.py
python scripts/build_official_home_clone_fixture.py --check
```

## Source identity (unchanged from capture)

| Field | Value |
|-------|--------|
| route_id | `home` |
| requested URL | `https://bukgu.gwangju.kr/` |
| final URL | `https://bukgu.gwangju.kr/` |
| title | 전남광주통합특별시 북구 |
| captured_at | `2026-07-15T17:12:33+09:00` |
| raw capture SHA-256 | `b47910217ecdb58b508cfd69d34a9a3a6e2c731f84a6db877ad01ebb04f5a6f5` |
| capture metadata SHA-256 | `52aa1a64745d6f6d570f03ef38a245ba6ba0b2475fbe3e8bbf032783ac06df5d` |
| generated fixture SHA-256 | `c43469da51236e91b2ba97c70a930a7097f3241093557d1a6c748aa4234e4c85` |

## Counts (summary)

| Metric | Count |
|--------|------:|
| Regions total (plan + hierarchy) | 13 |
| Regions ready / fixture-ready | 13 |
| Regions unresolved | 0 |
| HTML target regions (#1168 six) | 6 |
| HTML target regions fixture-ready | 6 |
| HTML target regions unresolved | 0 |
| Navigation items | 722 |
| Assets total | 174 |
| Assets ready with local exact identity | 0 |
| Assets unresolved | 174 |

## Six target regions (#1168)

| Region | Previous (#1166) | New status | Candidates | Items | Source evidence | Variants (items) | Remaining blocker |
|--------|------------------|------------|------------|------:|-----------------|------------------|-------------------|
| utility_navigation | unresolved | fixture-ready-renderer-not-wired | 1 | 21 | unique `div.slidelist` (+ optional `sitemap-btn`) | from item variants | renderer not wired |
| main_banner | unresolved | fixture-ready-renderer-not-wired | 1 | 31 | unique `div.visual` | from item variants | renderer + assets |
| resident_service_shortcuts | unresolved | fixture-ready-renderer-not-wired | 1 | 14 | unique `#favorites.most-menu` | from item variants | renderer not wired |
| notice_news | unresolved | fixture-ready-renderer-not-wired | 1 | 36 | unique `div.board` (6 article groups) | from item variants | dynamic board bodies remain JS-fed; labels/links from HTML only |
| related_site_controls | unresolved | fixture-ready-renderer-not-wired | 1 | 21 | unique `div.family-site` | from item variants | renderer + assets |
| footer_identity_contact | unresolved | fixture-ready-renderer-not-wired | 1 | 8 | unique `div.address` (+ `p.copyright`, `div.foot-link`) | from item variants | renderer not wired |

### Newly resolved

```text
utility_navigation
main_banner
resident_service_shortcuts
notice_news
related_site_controls
footer_identity_contact
```

**Newly resolved count: 6**
**Still unresolved among the six: 0**

## Asset readiness

- Every #1160 asset inventory row is represented (`assets` length 174).
- Exact local mapping still requires full-file identity evidence.
- Partial `first_65536_bytes` hashes are not full-file identity.
- Current local exact mappings: **0**.

## Duplicate / ambiguity handling

- Desktop/mobile/hidden/template variants are **not** auto-merged.
- Unique structural selectors only; multiple equal candidates → unresolved fail-closed.
- `script` / `style` subtrees excluded from content walks and labels.
- Notice list labels prefer `.title` / `.label` text (not date+title mashups).

## What this slice does **not** do

- Does not mark home as `exact` in the clone manifest
- Does not wire `CitizenActionDemoCanvas` / first-use UI to this fixture
- Does not download or re-fetch the official site
- Does not invent labels, contacts, phone numbers, or asset paths
- Does not claim that the home route is finished as an exact official clone

## Follow-up blockers (informational)

1. Exact local asset vendoring with full-file checksum evidence
2. Optional deeper segmentation of notice board AJAX-only bodies (not in static HTML)
3. Separate product PR to wire renderer read path — out of scope for #1166/#1168
