# Audit: Municipal Crawl Filters Config Candidates

## Stage
Stage 392

## 1. Goal & Context
Stage 391 established the technical path mapping `SiteProfile.crawl_filters` directly into `URLCrawler` via `HomepageMapper` during pipeline runs. In Stage 392, we establish an **audit-only safety boundary** to design and analyze the candidate crawl filter rules before making any changes to real site profile YAML configuration files.

Because introducing `deny_patterns` alters link extraction and traversal at runtime, any error or overly aggressive rule can lead to **crawl loss**—dropping critical municipal service pages, contacts, or notice details. Therefore, this audit serves as a conservative design check.

---

## 2. Proposed Candidate Rule Set
We propose a highly conservative candidate rule set to serve as the initial template:

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
```

### Allow Patterns Design Decision
- **Decision**: `allow_patterns` is left **empty** (`[]`) by default for all candidates.
- **Rationale**: Allow patterns override deny rules under the established precedence policy. If allow patterns are added prematurely without site-specific reasons, they might accidentally bypass our deny rules, weakening the effectiveness of the crawl budget protection. Allow patterns will only be introduced from Stage 393+ onwards under controlled, site-specific overrides.

---

## 3. Protected Municipal URL Catalogue
To prevent crawl loss on Korean public-sector J2EE/EGOV platforms, the following parameters and keywords represent structural identifiers and **must never be blocked**. They are protected explicitly:

- **Menu & Navigation**:
  - `menu.es?mid=`
  - `mid=`
  - `menuId=`
  - `menu=`
- **Notices & Detail Pages**:
  - `board.es`
  - `seq=`
  - `contentId=`
  - `articleId=`
- **Sub-pages & Departments**:
  - `deptId=`
  - `staffSearch`
- **Location, Map & Parking**:
  - `office-guide`, `map`, `parking`, `주차`, `위치`
- **Civil Forms & Downloads**:
  - `civil`, `download`, `form`

---

## 4. Deny Candidate Risk Analysis
We analyze the risks of candidate deny rules to define strict safety boundaries:

| Deny Candidate | Potential Risk | Safety Recommendation |
| :--- | :--- | :--- |
| `print=` | **Low Risk**. Print layouts duplicate the main content. However, rare legacy sites might use a print page URL structure as the primary indexable link. | Allow print layouts only if no primary HTML layout URL exists. |
| `utm_*` | **Zero Risk**. Marketing and tracking parameters (e.g. `utm_source=`) are safe to block as they contain identical content to regular URLs. | Safe to deny globally. |
| `pageNo=` | **High Risk**. Banning deep pagination protects the crawl budget, but banning `pageNo=` completely would block page 1/seed pages, preventing the crawler from discovering notices. | **Excluded from candidate rules**. Keep pagination parameters out of global deny rules until safe thresholds or specific fixture guards are verified. |
| `board.es` | **Critical Risk**. Banning notice board engines completely prevents indexing announcements. | **Strictly Forbidden to Deny**. Must remain protected. |
| `mid=`, `menuId=` | **Critical Risk**. Blocks overall site menu traversal. | **Strictly Forbidden to Deny**. Must remain protected. |
| `seq=`, `contentId=` | **Critical Risk**. Blocks notice detail pages. | **Strictly Forbidden to Deny**. Must remain protected. |

---

## 5. Pre-Stage 393/394 Verification Test Plan
Before any real YAML configuration files are modified (planned for Stage 394), the following verification contract tests must pass:

1. **Synthetic Config Fixture Test**:
   - Verify that synthetic profiles load, merge, and clean crawl rules without mutating the global environment.
2. **Profile Loader Test**:
   - Ensure the loader safely handles profiles with empty, missing, or malformed `crawl_filters` keys.
3. **Homepage Mapper Test**:
   - Verify that `HomepageMapper` forwards the configuration block to `URLCrawler` correctly.
4. **Pipeline Runner Test**:
   - Verify the pipeline runner resolves matched profiles and applies candidate filters.
5. **Mock Static HTML Crawl Preservation Test**:
   - Assert that `/menu.es?mid=a101` and `/normal` survive, while `/page?print=1` is correctly filtered using synthetic profiles.
6. **Flat-Link Provider Fallback Test**:
   - Verify that non-HTML provider fallback flat link lists filter internal links without mutating external or attachment list counts.
7. **No Source Grounding Change Test**:
   - Verify that applying path filters does not alter the source grounding or query rewrites during pipeline execution.
8. **No Scenario/Snapshot/Cache Generation Test**:
   - Assert that no files are modified in `scenario/`, `snapshot/`, or `cache/` during crawl filter validation.

---

## 6. Recommended Next Steps
- **Stage 393**: Add config fixture contract tests only. No real YAML configuration modifications are allowed.
- **Stage 394**: Apply the candidate configurations to real municipal YAML files only after all Stage 393 contract tests pass successfully.
- **Stage 395+**: Execute controlled live smoke tests with the updated configs, subject to explicit user approval.

---

## Stage 393 Implementation Status (Completed)
- **Status**: Implemented the full contract validation suite in `tests/test_municipal_crawl_filters_config_contract.py`.
- **Validation**:
  1. Synthetic Candidate Config Fixture Test: Verified config parser sanitizes candidate filters accurately.
  2. Protected Municipal URL Preservation Test: Checked that `/menu.es?mid=`, `/some/path?menuId=`, `/board.es?seq=`, `/content?contentId=`, `/article?articleId=` links are preserved.
  3. Deny Duplicate/Tracking Test: Checked print and UTM links are filtered out.
  4. Pagination Deferred Test: Checked `pageNo` and `currentPage` continue to be allowed.
  5. Forbidden Deny Rule Guard Test: Checked critical parameters are never present in the deny lists.
  6. Pipeline Synthetic Profile Fixture Test: Verified mapping propagation in `PipelineRunner`.
  7. No Real Config Mutation: Statically ensured no config YAML files are touched.
  8. No Live/Network/API: All tests executed locally with BeautifulSoup mocks.
- **Next Step**: Stage 394.

---

## Stage 394 Implementation Status (Completed)
- **Status**: First real YAML profile candidate applied. Changed exactly only one profile: `configs/sites/bukgu_gwangju.yml`.
- **Validation**:
  - Loader Test: Verified `SiteProfileLoader` loads `bukgu_gwangju.yml` and exposes candidate rules correctly.
  - Guard Test: Verified no critical parameters exist in `deny_patterns`.
  - Static HTML safety: Verified allowed, denied, and pagination deferred behaviors locally.
- **No Live**: No live validation performed (no live/network/API/Firecrawl calls).
- **Stage 395 Recommended Next**: Either add second municipal config candidate after reviewing Stage 394 diff, or controlled live smoke only if explicitly approved.

---

## Stage 395 Implementation Status (Completed)
- **Status**: Post-merge audit completed without live validation.
- **Key Findings**:
  - Confirmed exactly one real config (`configs/sites/bukgu_gwangju.yml`) changed in Stage 394.
  - Deferred live validation and confirmed no network calls or `RUN_LIVE_*_TESTS=1` changes.
  - Evaluated regression risk factors (print parameters, UTMs, deferred pagination, protected parameters).
- **Stage 396 Recommended Next**: Option B: Add no-live pipeline regression test for bukgu profile filters.

---

## Stage 396 Implementation Status (Completed)
- **Status**: No-live pipeline regression test added in `tests/test_bukgu_crawl_filters_pipeline_regression.py`.
- **Coverage**: 12 focused tests for profile load, static HTML filtering, and pipeline mapping.
- **Verification**: Full suite (920 tests) green.

---

## Stage 397 Implementation Status (Completed)
- **Status**: Second municipal crawl_filters candidate applied to **exactly one additional real YAML**: `configs/sites/gwangju_go_kr.yml` (광주광역시청 / `gwangju_go_kr`).
- **Selection Reasoning**:
  - Real municipal/public-sector site profile already loaded by SiteProfileLoader
  - LEGACY_BOARD_SITE classification with boardList.do/contentsView.do URL patterns
  - No existing crawl_filters configuration
  - URL structure uses parameters compatible with the candidate protected patterns (mid=, seq=, etc.)
- **Config Changes**: Single file `configs/sites/gwangju_go_kr.yml` appended with conservative candidate.
- **Test Changes**: Added `TestGwangjuGoKrCrawlFiltersConfig` (5 tests) in `tests/test_site_profile.py`:
  1. Profile loader verification (`crawl_filters` match candidate exactly)
  2. Protected patterns verification (all 6 required parameters present)
  3. Deny patterns verification (all 5 required parameters present)
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

---

## Stage 399 Implementation Status (Completed)

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

## Stage 400 Actual Outcome

**Stage 400 (PR #744) was closed not planned / not merged.**

- **Reason**: Stage 400 required selecting an *existing* municipal profile without crawl_filters from `configs/sites/`. At the time, `configs/sites/` contained only `bukgu_gwangju.yml` and `gwangju_go_kr.yml` (both already with crawl_filters). The PR attempted to add `seogu_gwangju.yml` as a **new file**, which violated the "existing profile only" constraint.
- **Lesson**: Adding a new YAML to `configs/sites/` = **profile onboarding**, not crawl_filters rollout. These are separate tracks with different validation requirements.

## Stage 401 Implementation Status (Completed)

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

## Stage 402 Implementation Status (Completed)

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

### Stage 403 Recommended Next

1. Add one new municipal profile via onboarding rules, or continue no-live coverage for existing profiles.
2. Live smoke only with explicit approval.
