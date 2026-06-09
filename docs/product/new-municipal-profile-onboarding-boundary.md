# New Municipal Profile Onboarding Boundary

## Stage
Stage 402

---

## 1. Purpose

This document defines the boundary between **crawl_filters rollout** (adding filters to *existing* profiles) and **new municipal profile onboarding** (adding a brand new site profile to `configs/sites/`). Stage 400 was closed not planned because it conflated these two distinct tracks.

Going forward, any new municipal profile must follow a dedicated onboarding process with explicit validation requirements before crawl_filters can be applied to it.

---

## 2. Current Configured Profile Inventory (as of Stage 401 merge)

| # | Profile | Site ID | Config File | crawl_filters Applied |
|---|---------|---------|-------------|----------------------|
| 1 | 광주광역시 북구청 | bukgu_gwangju | `configs/sites/bukgu_gwangju.yml` | Yes (Stage 394) |
| 2 | 광주광역시청 | gwangju_go_kr | `configs/sites/gwangju_go_kr.yml` | Yes (Stage 397) |

**Total profiles with crawl_filters: exactly 2**

- `seogu_gwangju` is **NOT** on main branch
- No other municipal profiles exist in `configs/sites/`

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

## 6. Seogu_gwangju Candidate Handling

| Aspect | Decision |
|--------|----------|
| **Status** | Not on main; PR #744's `seogu_gwangju.yml` was a new file addition |
| **Future Consideration** | May be onboarded as a **new profile** (not a crawl_filters rollout) in a future Stage |
| **Process** | Must follow the full onboarding checklist in §5, not just crawl_filters tests |
| **Do Not Reuse** | Do not blindly reuse PR #744's YAML or tests — profile validation steps are mandatory |
| **Dedicated Issue/PR** | If onboarded, it requires its own Issue/PR with full onboarding validation |

---

## 7. Stage 403 Decision Options

| Option | Description | When to Choose |
|--------|-------------|----------------|
| **A: Add New Municipal Profile (Onboarding Track)** | Add one new municipal profile via full onboarding checklist (§5), then optionally apply conservative `crawl_filters` in the same or next Stage | If a validated profile source exists and team wants to expand coverage |
| **B: Continue No-Live Regression (Existing Profiles)** | Deepen no-live regression for `bukgu_gwangju` and `gwangju_go_kr` (e.g., recursive crawl traversal, sitemap+homepage map integration, source preservation edge cases) | If no new profile source is ready, or to build confidence before further expansion |
| **C: Controlled Live Smoke (Existing Profiles Only)** | Run live validation against `bukgu_gwangju` and/or `gwangju_go_kr` with explicit operator approval | Only with explicit approval + rollback plan; never automatic |

**Recommended: Option A only if profile source data can be validated without live calls; otherwise Option B.**

Live smoke for new profiles or existing profiles remains **explicit-approval only**, never automatic.

---

## 8. Files Not Modified in This Stage

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

## 9. Validation

```bash
git diff --check  # PASS
# No pytest required (docs-only change)
```

---

## 10. Next Steps

- **Stage 403**: Either add one new municipal profile via onboarding rules (§5), or continue no-live coverage for existing profiles.
- **Live Smoke**: Remains explicit-approval only, no automatic schedule.