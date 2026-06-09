# New Municipal Profile Onboarding Boundary

## Stage
Stage 402

---

## 1. Purpose

This document defines the boundary between **crawl_filters rollout** (adding filters to *existing* profiles) and **new municipal profile onboarding** (adding a brand new site profile to `configs/sites/`). Stage 400 was closed not planned because it conflated these two distinct tracks.

Going forward, any new municipal profile must follow a dedicated onboarding process with explicit validation requirements before crawl_filters can be applied to it.

---

## 2. Current Configured Profile Inventory (as of Stage 403 merge)

| # | Profile | Site ID | Config File | crawl_filters Applied |
|---|---------|---------|-------------|----------------------|
| 1 | 광주광역시 북구청 | bukgu_gwangju | `configs/sites/bukgu_gwangju.yml` | Yes (Stage 394) |
| 2 | 광주광역시청 | gwangju_go_kr | `configs/sites/gwangju_go_kr.yml` | Yes (Stage 397) |
| 3 | 광주광역시 서구청 | seogu_gwangju | `configs/sites/seogu_gwangju.yml` | Yes (Stage 403) |

**Total profiles with crawl_filters: exactly 3**

---

## 3. Stage 400 Invalidation Summary

| Item | Detail |
|------|--------|
| **PR** | #744 |
| **Issue** | #745 |
| **Status** | Closed not planned / not merged |
| **Branch** | `config-test/stage-400-third-municipal-crawl-filters-with-no-live-regression` (discarded) |
| **Root Cause** | Stage 400 required selecting an **existing** municipal profile without crawl_filters from `configs/sites/`. At the time, `configs/sites/` contained only `bukgu_gwangju.yml` and `gwangju_go_kr.yml` (both already with crawl_filters). The PR attempted to add `seogu_gwangju.yml` as a **new file**, which violated the "existing profile only" constraint. |
| **Lesson** | Adding a new YAML to `configs/sites/` = **profile onboarding**, not crawl_filters rollout. These are separate tracks with different validation requirements. |

---

## 4. Boundary Decision: Two Separate Tracks

| Track | Action | Trigger | Validation Required |
|-------|--------|---------|---------------------|
| **Crawl Filters Rollout** | Add/update `crawl_filters` on an **existing** profile | Profile already onboards and loaded by `SiteProfileLoader` | - Loader test<br>- Static HTML filter test<br>- No-live pipeline regression test |
| **New Profile Onboarding** | Add a **new** YAML file to `configs/sites/` | New municipal/public-sector site needs support | Full onboarding checklist (see §5) |

**These tracks must never be conflated in a single Stage/PR.**

---

## 5. New Profile Onboarding Requirements

Before a new municipal site profile can be added to `configs/sites/` and before crawl_filters can be applied to it, the following checklist must be satisfied:

### 5.1 Profile Definition Requirements
- [ ] **site_id** naming rule: lowercase, snake_case, format `{district}_{city}` or `{city}_go_kr` (e.g., `bukgu_gwangju`, `gwangju_go_kr`, `seogu_gwangju`)
- [ ] **base_url**: Official HTTPS URL of the municipal site homepage
- [ ] **allowed_domains**: List of domains/subdomains the crawler may visit
- [ ] **classification**: One of `LEGACY_BOARD_SITE`, `MODERN_CMS_SITE`, `PORTAL_SITE`, `UNKNOWN`
- [ ] **important_keywords**: Korean/English service keywords relevant to the site
- [ ] **document_extensions**: File extensions for document indexing
- [ ] **board_patterns**: URL patterns for notice/board pages
- [ ] **crawl_rules**: max_depth, max_pages, include_documents, respect_robots
- [ ] **notes**: Diagnostic notes (how classification was determined, User-Agent requirements, etc.)

### 5.2 Loader & Configuration Validation
- [ ] **Loader test**: `SiteProfileLoader().load_by_id("<new_site_id>")` succeeds and returns valid `SiteProfile`
- [ ] **Schema validation**: All required fields present; `crawl_filters` initially empty or omitted
- [ ] **Backward compatibility**: Profile without `crawl_filters` loads and runs with default-allow behavior

### 5.3 Homepage Map & Static HTML Validation (No-Live)
- [ ] **Mock homepage HTML fixture**: Representative static HTML of the site's homepage with navigation links
- [ ] **HomepageMapper test**: `HomepageMapper(fetch_provider="mock")` extracts and categorizes nav links correctly
- [ ] **URL classification**: `classify_url()` correctly categorizes the site's characteristic URL patterns (e.g., `boardList.do`, `contentsView.do`, `menu.es`)
- [ ] **No live calls**: All validation uses mock/static fixtures only

### 5.4 No-Live Pipeline Regression Test
- [ ] **PipelineRunner test**: `PipelineRunner(provider="mock")` executes full pipeline with the new profile without exceptions
- [ ] **Filter pass-through**: Profile's `crawl_filters` (even if empty) are correctly passed to `HomepageMapper` → `URLCrawler`
- [ ] **No cache/scenario mutation**: Tests use `tmp_path` only; no repo files touched

### 5.5 Crawl Filters Candidate (Optional — Only After Profile Validated)
- [ ] **Conservative candidate**: If applying the shared conservative candidate (deny: print/UTM; protect: mid=, menuId=, board.es, seq=, contentId=, articleId=)
- [ ] **Site-specific adjustments**: Any additional protected/deny patterns justified by site-specific audit
- [ ] **Forbidden guard**: Critical municipal params NOT in deny_patterns (enforced by test)

### 5.6 One Profile Per Stage
- Only **one** new municipal profile may be added per Stage/PR
- This ensures validation focus and rollback simplicity

---

## 6. Seogu_gwangju Onboarding (Stage 403 Completed)

| Aspect | Decision |
|--------|----------|
| **Status** | **Onboarded in Stage 403** — `configs/sites/seogu_gwangju.yml` added to main |
| **Profile Source** | Verified via public website (www.seogu.gwangju.kr) — LEGACY_BOARD_SITE |
| **Onboarding Checklist** | All §5 requirements satisfied (loader, static HTML, URL classification, pipeline, crawl_filters) |
| **Tests Added** | `tests/test_seogu_profile_onboarding_no_live.py` (29 tests) |
| **Crawl Filters** | Applied conservative candidate (same as bukgu/gwangju) |
| **Inventory Test Updated** | `test_crawl_filters_source_preservation_regression.py` now expects 3 profiles |

---

## 7. Stage 404 Implementation Status (Completed)

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

## 8. Stage 405 Implementation Status (Completed)

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

## 10. Files Not Modified in This Stage

| Category | Status |
|----------|--------|
| `configs/sites/` | No changes |
| `src/` production code | No changes |
| `tests/` | No changes |
| `scenario/` `snapshot/` `cache/` | No mutations |
| `README.md` | No changes |
| `validate_matrix()` / `evaluate_response()` | No changes |
| Live/Network/API/Firecrawl | No calls made |

---

## 11. Validation

```bash
git diff --check  # PASS
# No pytest required (docs-only change)
```

---

## 12. Next Steps

- **Stage 406**: Controlled live smoke for one approved profile only if explicitly approved; otherwise continue no-live edge-case coverage.
- **Live Smoke**: Remains explicit-approval only, no automatic schedule.
