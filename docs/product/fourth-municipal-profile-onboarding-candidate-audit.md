# Audit: Fourth Municipal Profile Onboarding Candidate

## Stage
Stage 408

## 1. Current Readiness Summary

### Stage 394–407 Progress Overview

| Stage | Scope | Status |
|-------|-------|--------|
| 394 | First real crawl_filters config (bukgu_gwangju) | Completed |
| 395 | Post-merge audit | Completed |
| 396 | Bukgu pipeline regression (no-live) | Completed |
| 397 | Second config (gwangju_go_kr) | Completed |
| 398 | Gwangju pipeline regression (no-live) | Completed |
| 399 | First/second rollout comparison audit | Completed |
| 400 | Invalidated — conflated onboarding with rollout | Closed not planned |
| 401 | Source preservation regression (2 profiles) | Completed |
| 402 | Onboarding boundary definition | Completed |
| 403 | Third profile onboarding (seogu_gwangju) | Completed |
| 404 | All-configured source preservation regression | Completed |
| 405 | Controlled live smoke boundary | Completed |
| 406 | Edge-case regression (83 tests) | Completed |
| 407 | Sitemap/homepage integration (50 tests) | Completed |

### 3 Configured Profiles with Complete No-Live Coverage

| # | Profile | Site ID | Config File | No-Live Coverage |
|---|---------|---------|-------------|------------------|
| 1 | 광주광역시 북구청 | `bukgu_gwangju` | `configs/sites/bukgu_gwangju.yml` | Config validation, pipeline regression, source preservation, all-configured, edge cases, sitemap/homepage integration |
| 2 | 광주광역시청 | `gwangju_go_kr` | `configs/sites/gwangju_go_kr.yml` | Config validation, pipeline regression, source preservation, all-configured, edge cases, sitemap/homepage integration |
| 3 | 광주광역시 서구청 | `seogu_gwangju` | `configs/sites/seogu_gwangju.yml` | Full onboarding validation, all-configured, edge cases, sitemap/homepage integration |

### Test Coverage Inventory (246 Tests Total)

| Test File | Tests | Scope |
|-----------|-------|-------|
| `tests/test_site_profile.py::TestBukguCrawlFiltersConfig` | 5 | Loader, deny/protected/allow exact match, forbidden deny, static HTML |
| `tests/test_bukgu_crawl_filters_pipeline_regression.py` | 12 | Profile load, static HTML filter, PipelineRunner no-live path |
| `tests/test_site_profile.py::TestGwangjuGoKrCrawlFiltersConfig` | 5 | Loader, deny/protected/allow exact match, forbidden deny, static HTML |
| `tests/test_gwangju_crawl_filters_pipeline_regression.py` | 14 | Profile load, static HTML filter, PipelineRunner no-live path |
| `tests/test_seogu_profile_onboarding_no_live.py` | 29 | Full onboarding validation: loader schema, homepage map, URL classification, pipeline, crawl_filters behavior, inventory, no-live guards |
| `tests/test_crawl_filters_source_preservation_regression.py` | 21 | 2-profile inventory, shared candidate, source preservation, cross-profile consistency, no-live guards |
| `tests/test_all_configured_crawl_filters_source_preservation.py` | 27 | 3-profile inventory, shared candidate, parameterized source preservation, homepage map, cross-profile regression, no-live guards |
| `tests/test_crawl_filters_edge_case_regression.py` | 83 | Recursive/deep protected, mixed protected+denied precedence, pure denied duplicates, pagination deferred, cross-profile parametrize, source candidate preservation, no-live/network, no mutation |
| `tests/test_sitemap_homepage_crawl_filters_integration.py` | 50 | Sitemap XML fixture, homepage HTML fixture, merged candidate pool, cross-profile parametrize, order invariance, no-live/network, no mutation |

**Total no-live crawl_filters tests: 246 tests across 9 test files**

### Shared Conservative Candidate (All 3 Profiles)

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

### Full Suite Status

- **Total pytest: 1147 passed, 4 skipped**
- **No config/production code/live calls/scenario changes in Stages 394-407**
- **Stage 407 added 50 sitemap/homepage integration tests (no-live, mock/static fixtures only)**

---

## 2. Why Stage 408 Is Audit-Only

### Stage 400 Historical Lesson

| Item | Detail |
|------|--------|
| **Stage** | 400 |
| **PR** | #744 |
| **Issue** | #745 |
| **Status** | Closed not planned / not merged |
| **Root Cause** | Stage 400 required selecting an **existing** municipal profile without crawl_filters from `configs/sites/`. At the time, `configs/sites/` contained only `bukgu_gwangju.yml` and `gwangju_go_kr.yml` (both already with crawl_filters). The PR attempted to add `seogu_gwangju.yml` as a **new file**, which violated the "existing profile only" constraint. |
| **Lesson** | Adding a new YAML to `configs/sites/` = **profile onboarding**, not crawl_filters rollout. These are separate tracks with different validation requirements. |

### Boundary Decision (Stage 402)

|| Track | Action | Trigger | Validation Required |
|-------|--------|---------|---------------------|
| **Crawl Filters Rollout** | Add/update `crawl_filters` on an **existing** profile | Profile already onboards and loaded by `SiteProfileLoader` | Loader test, static HTML filter test, no-live pipeline regression test |
| **New Profile Onboarding** | Add a **new** YAML file to `configs/sites/` | New municipal/public-sector site needs support | Full onboarding checklist (§5 of onboarding boundary doc) |

**These tracks must never be conflated in a single Stage/PR.**

### Stage 408 Rationale

- The 3 existing profiles have achieved comprehensive no-live validation (246 tests)
- Before adding a fourth profile, we must **confirm the candidate selection policy**
- No new YAML config will be created in Stage 408
- This audit documents the criteria, exclusions, and shortlist policy for Stage 409
- Maintains the no-live safety boundary established since Stage 394

---

## 3. Candidate Selection Criteria

A candidate site must satisfy **ALL** of the following:

### 3.1 Mandatory Criteria

| Criterion | Rationale |
|-----------|-----------|
| **Gwangju metropolitan municipal/government profile** | Aligns with existing 3 profiles (all Gwangju) |
| **Public website** | No private/commercial sites |
| **No API key/secret required** | Must work with `fetch_provider: requests` only |
| **Source grounding/query rewrite/answer composition unchanged** | Profile config only; no production code changes needed |
| **LEGACY_BOARD_SITE or board-heavy equivalent** | URL patterns compatible with existing conservative candidate |
| **Comparable crawl_filters candidate applicable** | Can use the same `deny_patterns` (print/UTM) and `protected_patterns` (mid=, seq=, board.es, contentId=, articleId=, menuId=) |
| **Stage 409 verifiable with no-live tests only** | Mock/static fixtures sufficient; no live fetch needed |

### 3.2 Preferred Characteristics

| Characteristic | Priority |
|----------------|----------|
| Gwangju municipal sibling (구/군청) | High |
| Similar J2EE/EGOV board structure (menu.es, board.es) | High |
| Existing `SiteProfileLoader` entry or easily addable | Medium |
| Robots.txt accessible, no aggressive blocking | Medium |
| Sitemap.xml present | Low (nice to have) |

---

## 4. Candidate Exclusion Criteria

A candidate MUST BE EXCLUDED if ANY of the following apply:

| Exclusion Criterion | Examples |
|---------------------|----------|
| **API-based site** | Requires proprietary API, GraphQL, or custom endpoints |
| **Login/authentication required** | Content behind login walls, OAuth, SSO |
| **JS-only dynamic site** | Content rendered exclusively via JavaScript; static HTML fixture impractical |
| **Live provider/fetch validation required** | Cannot be verified with mock/static fixtures alone |
| **Source grounding production code changes needed** | Requires modifications to query rewrite, answer composition, or grounding logic |
| **Current stage requires live URL/HTML verification** | Any manual live access to confirm structure |
| **Non-municipal/government** | Commercial, corporate, or private sites |
| **Outside Gwangju metropolitan area** | Unless explicit strategic reason documented |

---

## 5. Recommended Candidate Shortlist Policy

### 5.1 Documentation Convention

- Candidate names documented as **"candidate"** only in Stage 408
- Exact URL/domain **NOT** finalized in this stage
- Exact selection deferred to **Stage 409** with human review

### 5.2 Priority Shortlist (Gwangju Municipal Siblings)

| Candidate (document as "candidate") | Rationale |
|-------------------------------------|-----------|
| **Gwangju Dong-gu Office (동구청)** | Gwangju sibling; likely LEGACY_BOARD_SITE; same platform family |
| **Gwangju Nam-gu Office (남구청)** | Gwangju sibling; similar structure expected |
| **Gwangju Gwangsan-gu Office (광산구청)** | Gwangju sibling; largest district; public website |

### 5.3 Selection Rules for Stage 409

1. **Only ONE candidate selected per Stage/PR** (enforced by onboarding boundary)
2. **Candidate must pass no-live verification** via mock/static fixtures before config creation
3. **Documented rationale** required for chosen candidate over alternatives
4. **No live fetch** for verification in Stage 409 — static fixtures only

### 5.4 What Stage 408 Does NOT Do

- ❌ Create new YAML config
- ❌ Add new tests
- ❌ Modify production code
- ❌ Perform live fetch/API calls
- ❌ Finalize exact site_id, base_url, or allowed_domains

---

## 6. Stage 409 Onboarding Checklist

When Stage 409 proceeds to onboard the selected fourth profile, the following MUST be completed:

### 6.1 Profile Definition

| Field | Naming Rule / Notes |
|-------|---------------------|
| `site_id` | lowercase, snake_case, format `{district}_gwangju` or `gwangju_go_kr` |
| `base_url` | Official HTTPS URL of the municipal site homepage |
| `allowed_domains` | List of domains/subdomains crawler may visit |
| `classification` | `LEGACY_BOARD_SITE` (expected) or `MODERN_CMS_SITE` |
| `important_keywords` | Korean/English service keywords (민원, 공고, 교육, 복지, etc.) |
| `document_extensions` | File extensions for document indexing |
| `board_patterns` | URL patterns for notice/board pages (e.g., `menu.es`, `board.es`, `boardList.do`) |
| `crawl_rules` | max_depth, max_pages, include_documents, respect_robots |
| `notes` | Diagnostic notes (classification basis, UA requirements) |

### 6.2 Loader & Configuration Validation

- [ ] `SiteProfileLoader().load_by_id("<new_site_id>")` succeeds
- [ ] All required fields present; `crawl_filters` initially empty or omitted
- [ ] Backward compatibility: profile without `crawl_filters` runs with default-allow

### 6.3 Homepage Map & Static HTML Validation (No-Live)

- [ ] Mock homepage HTML fixture with representative navigation links
- [ ] `HomepageMapper(fetch_provider="mock")` extracts and categorizes nav links
- [ ] `classify_url()` correctly categorizes site's URL patterns
- [ ] All validation uses mock/static fixtures only

### 6.4 No-Live Pipeline Regression Test

- [ ] `PipelineRunner(provider="mock")` executes full pipeline without exceptions
- [ ] Profile's `crawl_filters` correctly passed to `HomepageMapper` → `URLCrawler`
- [ ] Tests use `tmp_path` only; no repo files touched

### 6.5 Crawl Filters Candidate (After Profile Validated)

- [ ] Apply shared conservative candidate (deny: print/UTM; protect: mid=, menuId=, board.es, seq=, contentId=, articleId=)
- [ ] Any site-specific adjustments justified by audit
- [ ] Forbidden guard: critical municipal params NOT in deny_patterns (enforced by test)

### 6.6 Inventory Tests Update

- [ ] Update profile count tests to expect 4 profiles
- [ ] Add new profile to parameterized cross-profile tests

### 6.7 Documentation Updates

- [ ] Update `new-municipal-profile-onboarding-boundary.md` inventory table
- [ ] Update `controlled-live-smoke-boundary-for-crawl-filters.md` test coverage
- [ ] Update all related strategy/policy docs with Stage 409 status

---

## 7. Required Safety Gates for Stage 409

| Gate | Requirement |
|------|-------------|
| **No live/network/API/Firecrawl** | All validation via mock/static fixtures |
| **No source grounding production changes** | Profile config only |
| **No scenario/snapshot/cache generation** | Tests use `tmp_path` only |
| **No validate_matrix()/evaluate_response() changes** | Evaluation logic unchanged |
| **No query rewrite/answer composition changes** | Composer logic unchanged |
| **Full pytest passes** | 1147+ tests pass if tests/config added |

---

## 8. Stage 410 Options

| Option | Description | When to Choose |
|--------|-------------|----------------|
| **A: Controlled Live Smoke for One Approved Profile Only** | Execute live smoke against exactly one profile (recommended: `bukgu_gwangju`) with all prerequisites | **Only if operator explicitly approves live**; all prerequisites met; first live validation |
| **B: Fourth Municipal Profile Onboarding, No-Live Only** | Add the fourth profile via onboarding boundary, apply conservative `crawl_filters`, no live | **Recommended after Stage 408 audit**; no live approval; safe expansion |
| **C: Continue No-Live Integration Coverage** | Add no-live tests for edge cases: dynamic URL patterns, deep pagination beyond current coverage | If neither A nor B; builds confidence without live risk |

**Recommended**: **Option B** after Stage 408 audit is accepted, unless user explicitly approves live (Option A).

Live smoke remains **explicit-approval only**, never automatic, never batch, always one profile at a time.

---

## 9. Files Not Modified in Stage 408

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

## 10. Validation

```bash
git diff --check  # PASS
# No pytest required (docs-only change)
```

---

## 11. Next Steps

- **Stage 409**: Onboard one fourth municipal profile no-live only after candidate audit is accepted.
- **Live Smoke**: Remains explicit-approval only, no automatic schedule.
