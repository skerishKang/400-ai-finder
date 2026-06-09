# Post-Merge Audit: First Real Crawl Filters Config

This document reviews the integration and validation state of the first real crawl filters candidate applied during Stage 394, assesses regression risks, and plans the safe path forward.

---

## 1. Stage 394 Diff Review Summary

A rigorous post-merge review of the Stage 394 commit (`d46490cb9bd90a9923ddb90095e1006d1907a55e`) was conducted.

* **Single Profile Isolation**: Exactly one real site configuration was modified: `configs/sites/bukgu_gwangju.yml`. No other site profiles or database configurations were touched.
* **Production Integrity**: No production code under `src/` was changed. All changes were limited strictly to the target configuration, test suite additions, and documentation logs.
* **Contract/Loader Alignment**: The schema loading mechanism correctly read the candidate parameters and successfully mapped them to the `URLCrawler` instance without side effects.

---

## 2. Applied Candidate Summary

The following `crawl_filters` config candidate has been successfully applied to the `bukgu_gwangju` site profile:

```yaml
crawl_filters:
  allow_patterns: []
  deny_patterns:
    - "print="
    - "utm_"
    - "utm_source="
    - "utm_medium="
    - "utm_campaign="
  protected_patterns:
    - "mid="
    - "menuId="
    - "board.es"
    - "seq="
    - "contentId="
    - "articleId="
```

### Analysis of Settings:
* **`allow_patterns`**: Left empty (`[]`) by design. This avoids any accidental overriding of the deny list via overly permissive allow rule precedence.
* **`deny_patterns`**: Filters out print pages and standard analytics/tracking query parameters.
* **`protected_patterns`**: Guards critical parameters from being filtered, ensuring structural menu and item pages continue to be parsed.

---

## 3. Why Live Smoke is Still Deferred

Even though the mock/static HTML validation passed successfully, live validation (using active requests/Firecrawl runs against target servers) remains deferred for the following reasons:

1. **Active Configuration Risk**: The candidate filters are now active in the standard profile-loading and execution pathway. A live run could alter existing snapshot datasets or trigger unexpected remote site behaviors.
2. **Edge Cases & Server Variations**: Remote servers may behave differently under varied user-agents or query strings. Controlled simulation of these behaviors under local tests must be established first.
3. **Safety Isolation**: Keeping `RUN_LIVE_*_TESTS=1` disabled guarantees that no external network calls are performed without explicit verification and approval from the operator.

---

## 4. Regression Risk Checklist

Before rolling out more configs, we evaluated potential regression paths:

* **Print View Pages**: Print pages (`print=`) occasionally act as primary fallback links on legacy municipal sites if regular pages fail. However, for `bukgu_gwangju.yml`, normal HTML content pages are fully accessible. Denying `print=` is verified as low-risk.
* **UTM Query Parameters**: Analytics tags (`utm_`, `utm_source=`, etc.) are purely tracking links. Filtering them carries near-zero functional risk.
* **Pagination (pageNo, currentPage)**: Pagination query fields are intentionally omitted from `deny_patterns` and kept as deferred. They will not be blocked, which prevents crawl truncation.
* **Board, Detail, and Menu Pages**: Structural parameters (`mid=`, `menuId=`, `board.es`, `seq=`, `contentId=`, `articleId=`) are explicitly listed in `protected_patterns` to guarantee notice boards and articles survive traversal.
* **Grounding & Answer Generation**: No changes were made to source grounding, answer composition, or evaluation metrics (`validate_matrix`/`evaluate_response`).
* **Storage & Cache**: No modifications were made to scenario files, snapshots, or query cache files.

---

## 5. Stage 396 Decision Options

To determine the safest next step for Stage 396, the following three options were reviewed:

* **Option A: Add second municipal config candidate** (one YAML only)
  * *Pros*: Moves forward with config rollout.
  * *Cons*: If there is a latent loader or pipeline regression in the first profile config, applying it to a second profile multiplies the regression surface area without further verification.
* **Option B: Add no-live pipeline regression test for bukgu profile filters** (Recommended)
  * *Pros*: Allows validating the end-to-end integration path of the newly loaded `bukgu` filters in `PipelineRunner` using mock site content. This guarantees that `PipelineRunner` doesn't throw exceptions or drop essential pages during a full simulated run.
  * *Cons*: Postpones rollout of the second profile configuration by one stage.
* **Option C: Controlled live smoke**
  * *Pros*: Tests real-world response.
  * *Cons*: High risk. Can only be performed under explicit operator approval and guidance.

**Decision**: **Option B** is recommended first. Building a no-live pipeline mock regression test specifically for `bukgu_gwangju` using its loaded profile filters is the most conservative and safest engineering choice before extending changes to other real profiles.
---

## 6. Stage 396 Implementation Status (Completed)

- **Status**: No-live pipeline regression test successfully added in `tests/test_bukgu_crawl_filters_pipeline_regression.py`.
- **Coverage**:
  - Test A: Real profile load verification — `SiteProfileLoader().load_by_id("bukgu_gwangju")` loads crawl_filters correctly, deny/protected patterns match Stage 394.
  - Test B: Static HTML filtering — `URLCrawler` with real bukgu filters preserves protected URLs (`mid=`, `seq=`, `contentId=`, `articleId=`, `board.es`, pagination) and denies print/tracking URLs (`print=`, `utm_*`).
  - Test C: PipelineRunner no-live path — `PipelineRunner(provider="mock")` passes real bukgu `crawl_filters` to `HomepageMapper` → `URLCrawler` without any live network/API/Firecrawl calls.
- **Verification**: 12 new focused tests pass; full suite (920 tests) remains green.
- **No Config Changes**: `configs/sites/bukgu_gwangju.yml` unchanged.
- **No Production Code Changes**: `src/` paths untouched.
- **No Source Grounding/Answer Changes**: Only mock AnswerComposer assertion for compose call.
- **No Scenario/Snapshot/Cache Mutation**: All outputs to `tmp_path` only.
- **Live Smoke Still Deferred**: `RUN_LIVE_*_TESTS=1` not used; explicit approval still required.

### Stage 397 Recommended Next Steps

1. **Option A (Recommended)**: Add second municipal config candidate (one YAML only) now that no-live regression baseline exists.
2. **Option B**: Add another no-live regression around homepage map/source preservation (deeper crawl traversal coverage).
3. **Option C**: Controlled live smoke — **only with explicit operator approval**.

---

## 7. Stage 397 Implementation Status (Completed)

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
