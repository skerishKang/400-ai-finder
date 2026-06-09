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

---

## 8. Stage 398 Implementation Status (Completed)

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

---

## 9. Stage 399 Implementation Status (Completed)

- **Status**: Comparison audit completed in `docs/product/crawl-filters-first-second-rollout-comparison-audit.md`.
- **Scope**: Docs-only comparison of first two rollouts (bukgu_gwangju Stage 394/396, gwangju_go_kr Stage 397/398).
- **Comparison Coverage**:
  - Rollout inventory (config files, stages, test files)
  - Shared candidate rules (identical conservative config)
  - Test coverage matrix (12 vs 14 tests, both complete)
  - Risk comparison (print, UTM, pagination, structural params)
  - Stage 400 decision options (A: third config, B: source preservation, C: live smoke, D: hybrid)
- **Decision**: Stage 400 should follow Option D (Hybrid) — add third config candidate + its no-live regression, then source preservation regression before fourth config.
- **No Config/Code/Test Changes**.
- **Live Smoke Still Deferred**: Explicit approval required.

## 10. Stage 400 Actual Outcome

**Stage 400 (PR #744) was closed not planned / not merged.**

- **Reason**: Stage 400 required selecting an *existing* municipal profile without crawl_filters from `configs/sites/`. At the time, `configs/sites/` contained only `bukgu_gwangju.yml` and `gwangju_go_kr.yml` (both already with crawl_filters). The PR attempted to add `seogu_gwangju.yml` as a **new file**, which violated the "existing profile only" constraint.
- **Lesson**: Adding a new YAML to `configs/sites/` = **profile onboarding**, not crawl_filters rollout. These are separate tracks with different validation requirements.

## 11. Stage 401 Implementation Status (Completed)

- **Status**: Source preservation / homepage map consistency no-live regression added in `tests/test_crawl_filters_source_preservation_regression.py` (21 tests).
- **Coverage**:
  - Configured profiles inventory verification (exactly 2 profiles with crawl_filters)
  - Homepage map consistency for both bukgu_gwangju and gwangju_go_kr
  - Protected URLs remain source candidates; denied URLs excluded
  - Cross-profile consistency (identical conservative candidate rules)
  - No live/network/API guard
  - No scenario/snapshot/cache mutation
- **Verification**: 21 new tests pass; full suite 960 passed.
- **No Config/Production/Source Grounding/Scenario/Cache Changes**.

## 12. Stage 402 Implementation Status (Completed)

- **Status**: New municipal profile onboarding boundary defined in `docs/product/new-municipal-profile-onboarding-boundary.md`.
- **Scope**: Docs-only audit defining the boundary between crawl_filters rollout and new profile onboarding.
- **Key Deliverables**:
  - Current configured profile inventory (exactly 2: bukgu_gwangju, gwangju_go_kr)
  - Stage 400 invalidation summary
  - Boundary decision: two separate tracks (rollout vs onboarding)
  - New profile onboarding requirements checklist
  - Seogu_gwangju handling guidance
  - Stage 403 decision options
- **No Config/Code/Test Changes**.

## 13. Stage 403 Implementation Status (Completed)

- **Status**: New municipal profile `seogu_gwangju` onboarded with full validation.
- **Config Changes**: Single new file `configs/sites/seogu_gwangju.yml` added with conservative `crawl_filters` candidate.
- **Test Changes**: New test file `tests/test_seogu_profile_onboarding_no_live.py` (29 tests) covering:
  - SiteProfileLoader schema and required fields validation
  - Mock/static homepage map extraction and navigation link categorization
  - URL classification for seogu-specific patterns (bbs/BBSMSTR, boardDownload.es, list.do)
  - PipelineRunner no-live path with crawl_filters pass-through
  - crawl_filters behavior (preserve protected, deny print/UTM, defer pagination)
  - Updated configured profiles inventory (3 profiles with crawl_filters)
  - No live/network/API/Firecrawl calls; tmp_path only
- **Updated Existing Test**: `tests/test_crawl_filters_source_preservation_regression.py` inventory test updated from 2 to 3 profiles.
- **Verification**: 29 new tests + 1 updated test pass; full suite 987 passed.
- **No Production Code Changes**: `src/` untouched.
- **Existing Profiles Unchanged**: `bukgu_gwangju.yml`, `gwangju_go_kr.yml` not modified.
- **Live Smoke Still Deferred**: Explicit approval required.

## 14. Stage 404 Implementation Status (Completed)

- **Status**: All-configured-profiles source preservation / homepage map consistency no-live regression added in `tests/test_all_configured_crawl_filters_source_preservation.py` (27 tests).
- **Coverage**:
  - Configured profiles inventory verification (exactly 3 profiles with crawl_filters)
  - Shared candidate consistency (all 3 profiles use identical conservative candidate)
  - Parameterized source preservation test (protect/deny URLs for all 3 profiles)
  - Homepage map consistency (navigation and attachment links)
  - Cross-profile regression (base_url isolation, candidate rules identical, classification)
  - No live/network/API guard
  - No scenario/snapshot/cache mutation
- **Verification**: 27 new tests pass; full suite 1014 passed.
- **No Config/Production/Source Grounding/Scenario/Cache Changes**.

## 15. Stage 405 Implementation Status (Completed)

- **Status**: Controlled live smoke boundary defined in `docs/product/controlled-live-smoke-boundary-for-crawl-filters.md`.
- **Scope**: Docs-only audit defining prerequisites, pass/fail criteria, rollback conditions, and Stage 406 options for controlled live smoke.
- **Key Deliverables**:
  - Current no-live readiness summary (3 profiles, 113 total tests)
  - Live smoke remains not executed (explicit-approval only)
  - Controlled live smoke prerequisites (operator approval, exact command, rollback plan, no secrets)
  - Suggested first live candidate (`bukgu_gwangju` recommended)
  - Pass/fail criteria (7 criteria, all must pass)
  - Rollback/stop conditions (6 conditions)
  - Stage 406 options (A: live smoke if approved, B: onboarding, C: more no-live)
- **No Config/Code/Test/Live Changes**.

## 16. Stage 406 Recommended Next

1. Controlled live smoke for one approved profile only if explicitly approved; otherwise continue no-live edge-case coverage.
