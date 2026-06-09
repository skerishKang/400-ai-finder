# Crawl Budget Path Filtering Policy

## Stage
Stage 386

## Goal
Design a safe and robust crawl budget protection and URL path filtering policy for public-sector websites. This design ensures that recursive crawling does not exhaust the crawler's page budget on duplicate pages, pagination loops, or print views, while protecting critical query parameters that identify core municipal services.

---

## Background
- **Stage 384 Audit Summary**: The audit of the crawling pipeline revealed a critical Crawl Budget Starvation risk. Because the crawler uses recursive depth-3 link traversal, it is highly vulnerable to wasting its limited page budget (`max_pages: 200/300`) on paginated boards (e.g., page 1 to 50 of announcements), print views, and duplicate query parameters.
- **Stage 385 Context**: Stage 385 expanded the menu/URL keyword classification categories (`classify_url()`) without changing the crawling traversal logic.
- **Stage 386 Context**: This stage establishes the filtering policy, identifying safe and dangerous parameters before any code implementation. No code behavior changes or crawler traversal edits are made in this stage.

---

## Non-Goals
- No runtime crawler behavior changes
- No `allow_patterns` / `deny_patterns` implementation
- No `SiteProfile` schema changes
- No config changes
- No live/network/API/Firecrawl calls
- No source grounding changes
- No scenario/snapshot/cache generation
- No volatile fact hardcoding

---

## Safe Deny Candidates
The following URL components and query parameters are safe to block or strip because they contain duplicate page content or search index noise:

1. **Print Views**:
   - Parameters: `print=`, `view=print`, `printPage`, `/print/`
   - Rationale: Print layouts duplicate the main HTML content, wasting crawl budget and creating search index duplicates.
2. **Tracking and Duplicate Parameters**:
   - Parameters: `utm_source=`, `utm_medium=`, `fbclid=`, `gclid=`
   - Rationale: Tracking parameters are used for marketing analytics and do not represent distinct page content.
3. **Repeated Board Pagination**:
   - Parameters: `page=`, `pageNo=`, `currentPage=`, `pageIndex=`
   - Rationale: Recursive crawling of deep page listings (e.g., page 5, 6, 7...) of notice boards wastes page budget.
   - **Crucial Rule**: Pagination should only be denied if the page index is greater than a low threshold (e.g. page > 2) or inside a board list context to ensure the first page is crawled for discovery.
4. **Sort and Search Noise**:
   - Parameters: `sort=`, `order=`, `searchKeyword=`
   - Rationale: Sorting parameters present the same documents in different orders. Search keywords inside local search features can lead to infinite URL generation.

---

## Dangerous Deny Candidates
The following parameters must **NEVER** be blocked by default. In Korean J2EE/EGOV public-sector sites, these parameters represent the unique identifiers of static pages, departments, and services:

- **Menu Identifiers**: `mid=`, `menuId=`, `menu=`, `menu.es`
- **Article and Content Identifiers**: `articleId=`, `seq=`, `contentId=`, `board.es`
- **Department/Category Identifiers**: `deptId=`, `category=`
- **Rationale**: If a global pattern bans `mid` or `seq`, the crawler will fail to discover almost all of Gwangju Bukgu's or Gwangju City Hall's core pages, causing complete retrieval failure.

---

## Precedence Policy
When determining whether a URL should be crawled, the filtering logic should follow a strict precedence hierarchy:

1. **Default Action**: If the `SiteProfile` has no crawl filter rules defined, all internal URLs are allowed.
2. **Allow over Deny**: If a URL matches both an `allow_patterns` rule and a `deny_patterns` rule, the allow rule takes precedence (i.e. it is allowed).
3. **Explicit Deny**: Deny rules must be explicitly defined (e.g., no wildcard broad blocking of query parameters).
4. **Local overrides Global**: Site-specific profile rules override global defaults.
5. **Escape Hatch (Protected Patterns)**: Even if a deny filter matches (such as a generic `board` keyword deny), if the URL contains a protected parameter like `mid=`, the URL must be allowed to protect core municipal menus.
6. **Pure Function Helper**: The decision logic must be implemented as a pure function first (without dependencies on disk, network, or crawler state).

---

## Proposed Schema (Not Implemented in Stage 386)
> **Note**: Stage 386 does not implement this schema or alter `SiteProfile`.

```yaml
crawl_filters:
  allow_patterns:
    - "menu.es?mid="
  deny_patterns:
    - "print="
    - "pageNo="
  protected_patterns:
    - "mid="
    - "menuId="
```

---

## Test Matrix for Stage 387

The following test matrix will govern the verification of the filter decision helper in Stage 387:

| Case | URL example | Expected decision | Reason |
|---|---|---|---|
| menu mid page | `https://bukgu.gwangju.kr/menu.es?mid=a10103000000` | **allow** | Core municipal menu |
| staff search | `https://bukgu.gwangju.kr/staffSearch?dept=123` | **allow** | Contact/org page |
| board page 1 | `https://bukgu.gwangju.kr/board.es?mid=a1010&pageNo=1` | **allow** | Seed/discovery page |
| board page 37 | `https://bukgu.gwangju.kr/board.es?mid=a1010&pageNo=37` | **deny** | Pagination budget protection |
| print view | `https://bukgu.gwangju.kr/board.es?mid=a1010&print=1` | **deny** | Duplicate content prevention |
| tracking param | `https://bukgu.gwangju.kr/menu.es?mid=a1010&utm_source=facebook` | **deny** or **strip** | Duplicate URL prevention |

---

## Recommended Next Stage: Stage 387
- **Title**: `[TECH] Add crawl path filter decision helper without wiring crawler traversal`
- **Scope**: Implement the pure helper function and focused tests based on the test matrix above.
- **Rationale**: Implementing the helper logic and verifying it in isolation avoids side effects on crawl runs. Wiring the crawler traversal can be safely deferred to Stage 388.

---

## Stage 387 Implementation Status (Completed)
- **Status**: Pure filter decision helper `should_crawl_url` was successfully implemented in `src/crawler/crawl_path_filter.py` and validated with 8 focused unit tests in `tests/test_crawl_path_filter.py`.
- **Wiring**: The helper is completely isolated and not wired into the `url_crawler.py` traversal logic. Runtime crawling behavior remains entirely unchanged.

---

## Stage 388 Integration Boundary Audit (Completed)
- **Status**: Completed audit in `docs/product/crawl-path-filter-integration-boundary-audit.md` to evaluate helper integration constraints.
- **Decision**: Recommended Option 1 (SiteProfile schema/config support first) for Stage 389, deferring crawler traversal wiring to Stage 390. This isolates the configuration parsing logic before impacting crawl runtime.
- **Next Step**: Stage 389 is required to add `crawl_filters` properties in `SiteProfile` and tests in `tests/test_site_profile.py`.

---

## Stage 389 SiteProfile Config Schema Support (Completed)
- **Status**: Implemented `crawl_filters` configuration property inside `SiteProfile` with strict formatting checks (filtering non-string values, stripping/filtering blank strings, ignoring unknown keys) and default fallback values.
- **Wiring**: Completely unwired from the runtime crawler traversal logic.
- **Next Step**: Stage 390 is still needed to safely integrate the helper function into crawler traversal logic.

---

## Stage 390 Crawler Integration Wiring (Completed)
- **Status**: Successfully integrated `should_crawl_url` path filtering helper and `SiteProfile.crawl_filters` configs into the `URLCrawler` traversal (`extract_links` phase).
- **Default-Allow**: Assured default-allow behavior where absence or empty state of `crawl_filters` preserves 100% of existing internal link discovery.
- **Safety**: Added rigorous testing covering explicit denies, protected overrides, allow overrides, and municipal structural URL safety (preventing accidental loss of `mid=`, `seq=`, etc. under unrelated deny patterns).
- **Next Step**: Stage 391.

---

## Stage 391 SiteProfile-to-URLCrawler Mapping Integration (Completed)
- **Status**: Implemented the safe mapping path from `SiteProfile` config fields to `URLCrawler` instantiations. Specifically, `PipelineRunner` loads matched profiles and forwards `crawl_filters` via `HomepageMapper` down to `URLCrawler`.
- **Default-Allow**: Profiles without `crawl_filters` continue to run with default empty filters, guaranteeing zero behavior changes for existing sites.
- **Safety**: Added rigorous integration tests verifying profile mapping from synthetic profiles, default-allow backward compatibility, mock static HTML crawl safety, and non-HTML provider fallback flat links contract.
- **Next Step**: Stage 392.

---

## Stage 392 Design Municipal Candidates Audit (Completed)
- **Status**: Audit completed and documented in [municipal-crawl-filters-candidate-audit.md](./municipal-crawl-filters-candidate-audit.md).
- **Candidates**: Proposed initial conservative candidate rules: deny prints/tracking parameters, protect core navigation/article parameters, keep allow patterns empty by default to prevent overriding denies accidentally.
- **Safety Boundaries**: Outlined deny candidates risk analysis (strict ban on denying `board.es`, `mid=`, `seq=`, etc. to prevent crawl loss) and established an 8-point pre-Stage 393/394 validation test plan.
- **Next Step**: Stage 393.

---

## Stage 393 Config Fixture Contract Tests (Completed)
- **Status**: Contract verification tests successfully implemented in `tests/test_municipal_crawl_filters_config_contract.py`.
- **Validation**:
  - Validated synthetic config parsing.
  - Locked preservation of protected parameters (`mid=`, `menuId=`, `board.es`, `seq=`, `contentId=`, `articleId=`).
  - Checked explicit denies of print/tracking URLs.
  - Locked preservation of pagination parameters (`pageNo`, `currentPage`) as deferred.
  - Enforced a forbidden guard on the deny list (no critical parameters in `deny_patterns`).
  - Verified pipeline runner mock mapping.
- **Next Step**: Stage 394.

---

## Stage 394 First Real Profile Candidate Application (Completed)
- **Status**: First real YAML profile candidate applied. Changed exactly only one profile: `configs/sites/bukgu_gwangju.yml`.
- **Validation**: Added unit tests in `tests/test_site_profile.py` verifying that the loader correctly loads the real profile filters and guards against critical parameters inside `deny_patterns`. Evaluated safety behaviors locally using mock/static HTML only.
- **No Live**: No live validation performed (no live/network/API/Firecrawl calls).
- **Stage 395 Recommended Next**: Either add second municipal config candidate after reviewing Stage 394 diff, or controlled live smoke only if explicitly approved.
---

## Stage 395 Review and Audit (Completed)

- **Status**: Post-merge audit completed without live validation.
- **Key Findings**:
  - Confirmed exactly one real config (`configs/sites/bukgu_gwangju.yml`) changed in Stage 394.
  - Deferred live validation and confirmed no network calls or `RUN_LIVE_*_TESTS=1` changes.
  - Evaluated regression risk factors (print parameters, UTMs, deferred pagination, protected parameters).
- **Stage 396 Recommended Next**: Option B: Add no-live pipeline regression test for bukgu profile filters.

---

## Stage 396 No-Live Pipeline Regression Test (Completed)

- **Status**: No-live pipeline regression test added in `tests/test_bukgu_crawl_filters_pipeline_regression.py`.
- **Scope**:
  - Test A: Real `bukgu_gwangju` profile `crawl_filters` load verification (deny/protected patterns match Stage 394).
  - Test B: Static HTML URL filtering — `URLCrawler` with real profile filters preserves protected municipal URLs and denies print/tracking duplicates.
  - Test C: `PipelineRunner(provider="mock")` passes real profile `crawl_filters` to `HomepageMapper`/`URLCrawler` with zero live network calls.
- **Verification**: 12 focused tests pass; full pytest suite (920 tests) clean.
- **No Config/Production/Source Grounding/Scenario/Cache Changes**.
- **Live Smoke Still Deferred**: Explicit approval required.

### Stage 397 Recommended Next

- Add second municipal config candidate (one YAML) or extend no-live regression coverage.
- Live smoke remains explicit-approval only.

---

## Stage 397 Implementation Status (Completed)

- **Status**: Second municipal crawl_filters candidate applied to exactly one additional real YAML: `configs/sites/gwangju_go_kr.yml` (광주광역시청 / `gwangju_go_kr`).
- **Selection Reasoning**:
  - Real municipal/public-sector site profile already loaded by SiteProfileLoader
  - LEGACY_BOARD_SITE classification with boardList.do/contentsView.do URL patterns
  - No existing crawl_filters configuration
  - URL structure compatible with candidate protected patterns (mid=, seq=, etc.)
- **Config Changes**: Single file `configs/sites/gwangju_go_kr.yml` appended with conservative candidate (same as bukgu).
- **Test Changes**: Added `TestGwangjuGoKrCrawlFiltersConfig` (5 tests) in `tests/test_site_profile.py`:
  1. Profile loader verification (crawl_filters match candidate exactly)
  2. Protected patterns verification (all 6 required params present)
  3. Deny patterns verification (all 5 required params present)
  4. Forbidden deny guard (critical params NOT in deny_patterns)
  5. Static HTML behavior using second profile filters (mock gwangju.go.kr URLs)
- **No Live/Network/API/Firecrawl**: All validations via mock/static HTML.
- **No Production Code Changes**: `src/` untouched.
- **Bukgu Config Unchanged**: `configs/sites/bukgu_gwangju.yml` not modified.
- **Verification**: 5 new tests pass; full suite 925 passed.
- **Live Smoke Still Deferred**: Explicit approval required.

### Stage 398 Recommended Next

1. Add no-live pipeline regression test for `gwangju_go_kr` profile (mirroring Stage 396).
2. Compare first/second config rollout behavior before further expansion.
3. Live smoke only with explicit approval.

---

## Stage 398 Implementation Status (Completed)

- **Status**: No-live pipeline regression test added in `tests/test_gwangju_crawl_filters_pipeline_regression.py`.
- **Coverage**: 14 focused tests for profile load, static HTML filtering, and pipeline mapping.
  - A: Profile load verification (6 tests) — crawl_filters loaded, deny/protected patterns match Stage 397
  - B: Static HTML filtering (7 tests) — URLCrawler preserves protected URLs, denies print/tracking, pagination deferred
  - C: PipelineRunner no-live path (3 tests) — passes real gwangju crawl_filters to HomepageMapper/URLCrawler with zero live calls
- **Verification**: 14 new tests pass; full suite 939 passed.
- **No Config/Production/Source Grounding/Scenario/Cache Changes**.
- **Live Smoke Still Deferred**: Explicit approval required.

### Stage 399 Recommended Next

1. Compare first/second config rollout behavior before further expansion.
2. Add third municipal config candidate (one YAML only) after no-live regression baseline established for both profiles.
3. Live smoke only with explicit approval.
