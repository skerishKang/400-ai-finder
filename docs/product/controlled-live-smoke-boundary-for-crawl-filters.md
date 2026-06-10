# Controlled Live Smoke Boundary for Crawl Filters Profiles

## Stage
Stage 407

---

## 1. Current No-Live Readiness Summary

As of Stage 410, the following no-live validation coverage exists for the three configured `crawl_filters` profiles:

| Profile | Site ID | Config File | Stages Completed |
|---------|---------|-------------|------------------|
| 광주광역시 북구청 | `bukgu_gwangju` | `configs/sites/bukgu_gwangju.yml` | 394 (config), 396 (pipeline), 401 (source preservation), 404 (all-configured), 406 (edge cases), 407 (sitemap/homepage integration), **409 (hardening)**, **410 (deeper hardening)** |
| 광주광역시청 | `gwangju_go_kr` | `configs/sites/gwangju_go_kr.yml` | 397 (config), 398 (pipeline), 401 (source preservation), 404 (all-configured), 406 (edge cases), 407 (sitemap/homepage integration) |
| 광주광역시 서구청 | `seogu_gwangju` | `configs/sites/seogu_gwangju.yml` | 403 (onboarding + config), 404 (all-configured), 406 (edge cases), 407 (sitemap/homepage integration) |

### Test Coverage Inventory

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
| `tests/test_bukgu_crawl_filters_hardening_no_live.py` | 58 | Exact candidate verification, protected+denied mixed precedence, pure denied duplicates, pagination deferred, query order invariance, fragment handling, relative URL normalization, allowed domain isolation, homepage/sitemap static fixtures, malformed href safety, board.es+tracking survival, forbidden deny guard, tmp_path only, no live/network/env guards |
| `tests/test_bukgu_crawl_filters_deeper_no_live.py` | 66 | Dynamic URL patterns, deep pagination variants, board/detail preservation, sitemap/homepage merge edge cases, enhanced no-live network guards |

**Total no-live crawl_filters tests: 370 tests across 11 test files**

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

- **Total pytest: 1271 passed, 5 skipped**
- **No config/production code/live calls/scenario changes in Stages 394-410**
- **Stage 409 added bukgu_gwangju hardening tests (58 tests, no-live only)**
- **Stage 410 added bukgu_gwangju deeper hardening tests (66 tests, no-live only)**

---

## 2. Live Smoke Remains Not Executed

**Stage 408 does NOT execute any live smoke validation.**

- No live/network/API/Firecrawl calls are made in Stage 408
- `RUN_LIVE_*_TESTS=1` is explicitly prohibited
- This document defines the boundary and prerequisites; it does not execute them
- Live validation remains **explicit-approval only**, deferred to Stage 409+

---

## 3. Controlled Live Smoke Prerequisites

Before ANY live smoke validation can be executed, ALL of the following must be satisfied:

### 3.1 Explicit Operator Approval
- A designated operator must explicitly approve the live run in writing (e.g., GitHub Issue comment, PR approval, or documented message)
- Approval must specify: **which profile**, **which exact command**, **max pages/depth**, **timeout**
- No automated or implicit approval; blanket approvals are not valid

### 3.2 Exact Target Profile Selection
- **One profile at a time** — no batch/live runs across multiple profiles
- Profile must be one of the three configured: `bukgu_gwangju`, `gwangju_go_kr`, or `seogu_gwangju`
- Profile must have completed all no-live regression tests (all do as of Stage 408)

### 3.3 Exact Command Specification
The live command must be fully specified in the approval, including:
```bash
# Example format (DO NOT EXECUTE WITHOUT APPROVAL)
PYTHONPATH=. RUN_LIVE_CRAWL_TESTS=1 .venv/bin/python -m pytest \
  tests/test_bukgu_live_smoke.py \
  -k "not test_pagination_deep" \
  --max-pages=50 --max-depth=2 \
  --timeout=300
```

Required parameters:
- `--max-pages`: explicit page budget limit (e.g., 50)
- `--max-depth`: explicit depth limit (e.g., 2)
- `--timeout`: explicit timeout in seconds (e.g., 300)
- `-k` filter to exclude known-risk tests if any

### 3.4 No API Keys or Secrets
- No live API keys (Firecrawl, OpenAI, etc.) may be used
- `preferred_fetch_provider: requests` only — no browser providers
- If Firecrawl or LLM providers are needed, they require **separate explicit approval**

### 3.5 Rollback Plan
A documented rollback plan must exist before execution, including:
- How to stop the run if it goes wrong (Ctrl+C, kill command)
- How to identify and revert any persisted changes (snapshots, cache, scenario files)
- Commit hash to roll back to if config/test changes were made

### 3.6 Expected Diff / No Persisted Artifacts Policy
- **Default expectation**: Live smoke should produce **NO persisted artifacts** (no snapshot, cache, scenario file modifications)
- If artifacts are generated, they must be explicitly reviewed and documented
- Any diff to `configs/`, `scenario/`, `snapshot/`, `cache/` must be part of the approval

---

## 4. Suggested First Live Candidate

| Profile | Risk Assessment | Recommendation |
|---------|-----------------|----------------|
| **`bukgu_gwangju`** | Lowest: First profile, most test coverage (394, 396, 401, 404, 406, 407), conservative config only | **RECOMMENDED** for first live |
| `gwangju_go_kr` | Low: Second profile, full coverage (397, 398, 401, 404, 406, 407), identical config | Acceptable alternative |
| `seogu_gwangju` | Medium: Newest profile, onboarding complete (403, 404, 406, 407) but less live exposure | **Not recommended** for first live |

**Recommendation**: If operator approves live smoke, start with `bukgu_gwangju` using `--max-pages=20 --max-depth=2 --timeout=180` and exact command as specified in §3.3.

---

## 5. Pass/Fail Criteria

A live smoke run **passes** ONLY if **ALL** of the following are true:

| Criterion | Check Method |
|-----------|--------------|
| Process exits successfully (exit code 0) | `echo $?` == 0 |
| No unhandled exceptions in output | `grep -i "traceback\|exception\|error" output.log` returns nothing |
| Protected URLs are not filtered out | Verify `mid=`, `seq=`, `contentId=`, `articleId=`, `board.es`, `menuId=` URLs appear in crawled results |
| Print/UTM duplicates reduced | Verify `print=`, `utm_*` URLs are absent or significantly reduced vs. baseline |
| No source grounding regression | Run existing evaluation suite; no degradation in `validate_matrix()` metrics |
| No scenario/snapshot/cache auto-generation | `git status` shows no changes to `scenario/`, `snapshot/`, `cache/` |
| Logs contain no secrets | `grep -i "api_key\|secret\|token\|password" output.log` returns nothing |

**Any single failure = entire live smoke FAILS**

---

## 6. Rollback / Stop Conditions

The live run **MUST BE STOPPED IMMEDIATELY** if ANY of the following occur:

| Condition | Detection | Action |
|-----------|-----------|--------|
| **Timeout** | Run exceeds `--timeout` | Kill process; investigate before retry |
| **Unexpected crawl explosion** | Page count > `--max-pages` × 2 | Kill process; check pagination filtering |
| **Source candidate count collapses** | Internal URLs discovered < 50% of no-live baseline | Kill process; crawl_filters may be over-filtering |
| **Protected municipal URLs missing** | `mid=`, `seq=`, `board.es` URLs absent from results | Kill process; protected patterns may not be working |
| **Domain leakage** | URLs outside `allowed_domains` being crawled | Kill process; check domain filtering |
| **Error spike** | HTTP 4xx/5xx > 20% of requests | Kill process; site may be blocking or down |

All stop conditions must be documented in the live run log.

---

## 7. Stage 411 Options (Updated Post-Stage 410 — Bukgu-Centric)

| Option | Description | When to Choose |
|--------|-------------|----------------|
| **A: Controlled Live Smoke for Bukgu Only** | Execute live smoke against `bukgu_gwangju` only with all prerequisites from §3 | **Only if operator explicitly approves live**; all §3 prerequisites met; first live validation |
| **B: Bukgu No-Live Continued Hardening** | Add more no-live integration tests for `bukgu_gwangju`: dynamic URL patterns, deep pagination, additional edge cases beyond current 124 tests | **Default recommendation** — no live approval needed; builds confidence on the profile with most coverage |
| **C: Profile Expansion (Deferred)** | Add new municipal profile (fourth/fifth) via onboarding boundary | **Only with explicit separate approval**; not part of default Stage 411 |

**Recommended**: **Option B** as default after Stage 410. Live smoke (Option A) remains explicit-approval only. Profile expansion (Option C) requires separate explicit approval and is deferred.

Live smoke remains **explicit-approval only**, never automatic, never batch, always one profile at a time (`bukgu_gwangju` only for first live).

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

- **Stage 411 (Default)**: Bukgu no-live continued hardening (dynamic URL patterns, deep pagination, more edge cases)
- **Stage 411 (Live)**: Controlled live smoke for `bukgu_gwangju` only — explicit operator approval required, never automatic
- **Profile Expansion**: Deferred — requires separate explicit approval (not part of default Stage 411)

---

## Stage 410 Implementation Status (Completed — Bukgu Deeper Hardening)

- **Focus**: Deepen `bukgu_gwangju` crawl filter integration coverage with no-live static fixture tests only.
- **Scope**:
  - No new configs/sites/*.yml added
  - No new municipal profile onboarding
  - New test file: `tests/test_bukgu_crawl_filters_deeper_no_live.py` (66 tests)
  - Tests cover: dynamic URL patterns (board.es act=view, bskind, keyField, search+pagination), deep pagination variants (pageNo, currentPage, pageIndex, page, p, perPage, recordCount, pageUnit, pageSize, offset, limit, start, count), board/detail URL preservation with query order invariance, sitemap/homepage candidate merge edge cases (duplicate URLs, fragments, external domains, malformed hrefs), enhanced no-live network guards (requests, httpx, urllib, socket patch guards; env var checks)
- **Documentation**: Stage 410 completion recorded in smoke boundary docs, crawl budget policy docs, dynamic retrieval strategy docs, onboarding boundary docs, and candidate audit docs.
- **Verification**: 1271 tests pass; full suite green.

---

## Stage 409 Implementation Status (Completed — Bukgu Hardening)

- **Direction Change**: Stage 409 does **not** add a fourth municipal profile. Operator decision: expand profile count later; first harden `bukgu_gwangju`.
- **Focus**: Harden `bukgu_gwangju` crawl filter coverage with no-live static fixture tests only.
- **Scope**:
  - No new configs/sites/*.yml added
  - No new municipal profile onboarding
  - New test file: `tests/test_bukgu_crawl_filters_hardening_no_live.py` (58 tests)
  - Tests cover: exact candidate verification, protected+denied mixed precedence, pure denied duplicates, pagination deferred, query order invariance, fragment handling, relative URL normalization, allowed domain isolation, homepage/sitemap static fixtures, malformed href safety, board.es+tracking survival, forbidden deny guard, tmp_path only, no live/network/env guards
- **Documentation**: Stage 409 direction change recorded in audit docs, onboarding boundary docs, and smoke boundary docs.
- **Verification**: 1205 tests pass; full suite green.

## Stage 407 Implementation Status (Completed)

- **Status**: No-live sitemap/homepage integration regression for configured crawl_filters profiles added in `tests/test_sitemap_homepage_crawl_filters_integration.py` (50 tests).
- **Coverage**:
  1. **Sitemap XML fixture integration** — static XML only, protected survive / denied excluded
  2. **Homepage HTML fixture integration** — static HTML only, protected+tracking mixed survive / pure denied excluded
  3. **Merged candidate pool** — test helper merges sitemap + homepage, applies crawl_filters, verifies dedupe preserves protected/excludes denied
  4. **Cross-profile parameterized check** — pytest.mark.parametrize for all 3 profiles with base_url isolation
  5. **Edge-case order invariance** — sitemap-first vs homepage-first produce same URL set
  6. **No live/network guard** — mock/static fixtures only, RUN_LIVE_*_TESTS=1 prohibited
  7. **No mutation safety** — tmp_path only, no scenario/snapshot/cache generation
- **Verification**: 50 new tests pass; full suite 1147 passed.
- **No Config/Production/Source Grounding/Scenario/Cache Changes**.
- **Live Smoke Still Deferred**: Explicit approval required.

## Stage 406 Implementation Status (Completed)

- **Status**: No-live edge-case regression for configured crawl_filters profiles added in `tests/test_crawl_filters_edge_case_regression.py` (83 tests).
- **Coverage**:
  1. **Recursive/deep URL edge cases** — protected URLs with tracking/query params survive; pure tracking denied
  2. **Mixed protected + denied query precedence** — protected patterns override deny patterns
  3. **Pure denied duplicate cases** — print, utm_source, utm_medium, utm_campaign, utm_content all denied
  4. **Pagination deferred edge cases** — pageNo, currentPage, pageIndex allowed (not in deny_patterns)
  5. **Cross-profile parameterized check** — pytest.mark.parametrize for all 3 profiles with base_url isolation
  6. **Source candidate preservation** — protected+tracking mixed URLs remain source candidates; pure denied excluded
  7. **No live/network guard** — mock/static fixtures only, RUN_LIVE_*_TESTS=1 prohibited
  8. **No mutation safety** — tmp_path only, no scenario/snapshot/cache generation
- **Verification**: 83 new tests pass; full suite 1097 passed.
- **No Config/Production/Source Grounding/Scenario/Cache Changes**.
- **Live Smoke Still Deferred**: Explicit approval required.
