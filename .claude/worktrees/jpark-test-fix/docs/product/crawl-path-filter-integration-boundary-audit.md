# Audit: Crawl Path Filter Integration Boundary

## Stage
Stage 388

## Goal
Evaluate and establish the integration boundary for the crawl path filter helper (`should_crawl_url()`) before wiring it into the crawler traversal. This audit defines the safest progression path, schema designs, wiring locations, safety test requirements, and URL protection strategies to prevent critical information loss.

---

## Files inspected
- [`src/crawler/crawl_path_filter.py`](../../src/crawler/crawl_path_filter.py)
- [`tests/test_crawl_path_filter.py`](../../tests/test_crawl_path_filter.py)
- [`src/crawler/url_crawler.py`](../../src/crawler/url_crawler.py)
- [`src/site_profiles/site_profile.py`](../../src/site_profiles/site_profile.py)
- [`docs/product/crawl-budget-path-filtering-policy.md`](../../docs/product/crawl-budget-path-filtering-policy.md)

---

## Status Summary of Stage 387
Stage 387 implemented a pure filter decision helper in `src/crawler/crawl_path_filter.py` with 8 focused unit tests.
- **Current State**: The helper is completely isolated and has no side effects on the `URLCrawler` runtime traversal logic.
- **Constraints Met**: Zero crawler wiring, zero schema changes, and zero config modifications were performed.

---

## Core Questions & Audit Decisions

### 1. Safest next path
- **Options compared**:
  1. *SiteProfile schema/config support first*: Define schema support in `SiteProfile` and `SiteProfileLoader` to load path filters from YAML config, without wiring them to `URLCrawler` traversal.
  2. *Crawler traversal wiring first*: Wire the helper directly into `URLCrawler` with static or hardcoded rules, skipping configuration loader changes.
  3. *Additional contract tests first*: Focus only on adding more unit tests before coding any integration.
  4. *Integration deferred*: Hold off on all schema/wiring work.
- **Decision**: **SiteProfile schema/config support first (Option 1)** is selected.
- **Reason**: Traversal wiring is a high-risk change because a bug in rule execution or wrong global filters can lead to critical page crawl loss (e.g., dropping contact or mayor pages). Adding config loading first allows us to define the contract and parse site-specific filters safely. Traversal wiring can then be done in a subsequent stage behind a default-allow fallback.

### 2. Proposing SiteProfile schema/config shape
We propose adding a `crawl_filters` block to the site profile YAML configurations. It is safe because missing fields default to empty lists, maintaining 100% backward compatibility:
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
Inside `SiteProfile` (in `src/site_profiles/site_profile.py`), the property should clean and return values:
```python
@property
def crawl_filters(self) -> dict[str, list[str]]:
    raw = self._data.get("crawl_filters", {})
    if not isinstance(raw, dict):
        return {}
    return {
        "allow_patterns": [p for p in raw.get("allow_patterns", []) if isinstance(p, str)],
        "deny_patterns": [p for p in raw.get("deny_patterns", []) if isinstance(p, str)],
        "protected_patterns": [p for p in raw.get("protected_patterns", []) if isinstance(p, str)],
    }
```

### 3. Traversal wiring location
If we proceed with traversal wiring in a later stage, `should_crawl_url()` must be invoked inside `URLCrawler.extract_links()` in `src/crawler/url_crawler.py`:
- **Why**: `extract_links()` parses anchor tags and populates `internal_links`. Filtering denied URLs here prevents them from ever entering the crawl queue (frontier), directly protecting the crawl budget from duplicate/noise pages.
- **Implementation sketch**:
  ```python
  if self.is_internal(base_url, normalized_url):
      if self.should_crawl_url(normalized_url): # helper call
          internal_links.append({
              "text": link_text,
              "url": normalized_url
          })
  ```

### 4. Tests required to prevent crawl loss
Before runtime filtering is activated, the following tests are mandatory to assert safety:
1. **Default-Allow Test**: Verify that a site profile with no `crawl_filters` property crawls 100% of discovered internal pages.
2. **Protected Parameter Priority Test**: Assert that a URL containing a protected pattern (e.g. `mid=`) is allowed, even if it matches a broad deny pattern (e.g. matching `deny_patterns: ["menu.es"]`).
3. **Normalizer Case-Insensitivity Test**: Ensure that URL casing variations do not bypass allow lists or cause accidental denies on protected menus.
4. **Mock Crawl Traversal Test**: Execute a mock crawling test using a static mock web directory to verify allowed pages are indexed and denied pages are omitted.

### 5. Protected Municipal URL patterns
Korean public sector websites heavily use query parameters to represent their core navigation and content. Banning these parameters globally will break retrieval. The following parameters must be explicitly added to `protected_patterns` in site profiles to prevent accidental denies:
- **Menu/Navigation**: `menu.es?mid=`, `mid=`, `menuId=`, `menu=`
- **Notices/Details**: `board.es`, `articleId=`, `seq=`, `contentId=`
- **Sub-pages**:
  - Staff/contact/org pages: `deptId=`, `staffSearch`
  - Location/parking pages: `office-guide`, `map`
  - Civil form pages: `civil`, `download`

### 6. Recommended Stage 389 path
- **Stage Title**: `Stage 389: Add SiteProfile config schema for crawl path filtering without traversal integration`
- **Objective**: Implement configuration loading and validation of `crawl_filters` in `SiteProfile` and `SiteProfileLoader`, tested in `tests/test_site_profile.py`.
- **Constraint**: No changes to `url_crawler.py` or runtime traversal logic.

---

## Non-Goals Confirmed
- No runtime crawler behavior changes in Stage 388
- No `allow_patterns` / `deny_patterns` implementation in Stage 388
- No `SiteProfile` schema changes in Stage 388
- No config changes in Stage 388
- No live/network/API/Firecrawl calls
- No source grounding changes
- No scenario/snapshot/cache generation
- No volatile fact hardcoding

---

## Stage 389 Implementation Status (Completed)
- **Status**: Implemented configuration schema parsing property `crawl_filters` inside `SiteProfile` class (`src/site_profiles/site_profile.py`). Added 6 focused unit tests under `tests/test_site_profile.py` verifying missing, valid, invalid block, invalid pattern values, unknown keys ignored, and import isolation.
- **Wiring**: Unwired. No logic in `url_crawler.py` references or uses `crawl_filters`.
- **Next Step**: Stage 390 is still needed to safely integrate the decision helper into crawler traversal.

---

## Stage 390 Implementation Status (Completed)
- **Wiring**: Successfully wired `should_crawl_url` decision helper and `SiteProfile.crawl_filters` config into the `URLCrawler` class inside `src/crawler/url_crawler.py` (specifically within the `extract_links()` stage).
- **Aesthetic / Behavior**: Preserves 100% of previous traversal behavior when `crawl_filters` is omitted (i.e. default-allow is fully active).
- **Verification**: Updated `tests/test_site_profile.py` assertions and added comprehensive test cases in `tests/test_url_crawler.py` covering:
  - Default-allow behavior (None and `{}` values)
  - Explicit deny patterns matching & filtering
  - Protected overrides overriding deny rules
  - Allow overrides overriding deny rules
  - Structural municipal URLs surviving unrelated deny rules
  - External link extraction remaining completely unaffected

---

## Stage 391 Implementation Status (Completed)
- **Status**: Wired the integration path from `SiteProfile` config fields to `URLCrawler` instantiations. In `PipelineRunner`, site profiles are loaded, and their parsed `crawl_filters` dictionary is forwarded via `HomepageMapper` down to `URLCrawler`.
- **Safety**: Fully tested with synthetic profiles, verified default-allow behavior for legacy profiles, mock HTML crawl safety for denied/protected parameters, and non-HTML provider fallback flat links contract.
- **Next Step**: Stage 392.

---

## Stage 392 Implementation Status (Completed)
- **Status**: Audit completed and documented in [municipal-crawl-filters-candidate-audit.md](./municipal-crawl-filters-candidate-audit.md).
- **Candidates**: Defined conservative initial configuration rules (deny prints, tracking parameters, protect structural parameters, allow-patterns left empty by default).
- **Plan**: Outlined the pre-Stage 393/394 contract verification test plan.
- **Next Step**: Stage 393.

---

## Stage 393 Implementation Status (Completed)
- **Status**: Implemented the complete 8-point verification plan locally inside `tests/test_municipal_crawl_filters_config_contract.py`.
- **Validation**: Assured that all synthetic candidate configurations correctly filter prints/tracking parameters while leaving core pagination, boards, and structural municipal parameters completely untouched.
- **Next Step**: Stage 394.
