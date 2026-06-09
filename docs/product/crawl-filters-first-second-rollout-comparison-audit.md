# Crawl Filters First and Second Rollout Comparison Audit

## Stage
Stage 399

## 1. Purpose

This document compares the first two real municipal site profile rollouts of conservative `crawl_filters` candidates (`bukgu_gwangju` and `gwangju_go_kr`) before deciding on further expansion. The goal is to establish a documented baseline of what has been achieved, what risks remain, and what the safest Stage 400 path should be.

---

## 2. Rollout Inventory

### Profile 1: bukgu_gwangju (광주광역시 북구청)

| Item | Detail |
|------|--------|
| **Site ID** | `bukgu_gwangju` |
| **Config File** | `configs/sites/bukgu_gwangju.yml` |
| **Classification** | LEGACY_BOARD_SITE |
| **Base URL** | `https://bukgu.gwangju.kr/` |
| **Real Config Applied** | Stage 394 (PR #735, merge commit `ceeb29f`) |
| **Loader/Unit Tests** | Stage 394 (`tests/test_site_profile.py::TestBukguCrawlFiltersConfig`) |
| **No-Live Pipeline Regression** | Stage 396 (`tests/test_bukgu_crawl_filters_pipeline_regression.py`, 12 tests) |
| **Post-Merge Audit** | Stage 395 (`docs/product/first-real-crawl-filters-post-merge-audit.md`) |

### Profile 2: gwangju_go_kr (광주광역시청)

| Item | Detail |
|------|--------|
| **Site ID** | `gwangju_go_kr` |
| **Config File** | `configs/sites/gwangju_go_kr.yml` |
| **Classification** | LEGACY_BOARD_SITE |
| **Base URL** | `https://www.gwangju.go.kr/` |
| **Real Config Applied** | Stage 397 (PR #738, merge commit `741e0de`) |
| **Loader/Unit Tests** | Stage 397 (`tests/test_site_profile.py::TestGwangjuGoKrCrawlFiltersConfig`, 5 tests) |
| **No-Live Pipeline Regression** | Stage 398 (`tests/test_gwangju_crawl_filters_pipeline_regression.py`, 14 tests) |
| **Post-Merge Audit** | Stage 398 merged directly (PR #740, merge commit `f0dfa71`) |

---

## 3. Shared Candidate Rules

Both profiles use the **exact same conservative candidate** derived from Stage 392 audit:

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

**Design Rationale** (from Stage 392):
- `allow_patterns` empty by default to avoid accidentally overriding deny rules
- `deny_patterns`: print layouts + standard tracking params (UTM) — zero/low risk
- `protected_patterns`: structural municipal URL parameters that must NEVER be blocked

---

## 4. Test Coverage Comparison

| Test Category | bukgu_gwangju (Stage 394/396) | gwangju_go_kr (Stage 397/398) | Notes |
|---------------|------------------------------|------------------------------|-------|
| **Profile Loader Verification** | 1 test | 1 test | `load_by_id` + non-empty check |
| **Deny Patterns Exact Match** | 1 test | 1 test | 5 patterns verified |
| **Protected Patterns Exact Match** | 1 test | 1 test | 6 patterns verified |
| **Allow Patterns Empty** | 1 test | 1 test | `[]` verified |
| **Forbidden Deny Guard** | 1 test | 1 test | 6 params NOT in deny |
| **Static HTML Preserve** | 1 test (5 URLs) | 1 test (7 URLs) | mid=, seq=, contentId=, articleId=, board.es, pagination |
| **Static HTML Deny** | 1 test (2 URLs) | 1 test (3 URLs) | print=, utm_source=, utm_campaign= |
| **Pagination Deferred** | 1 test | 1 test | pageNo survives |
| **should_crawl_url Pure Function** | 1 test | 1 test | All pattern types |
| **HomepageMapper Static HTML** | 1 test | 1 test | nav links extraction |
| **PipelineRunner → HomepageMapper** | 1 test | 1 test | Filters passed correctly |
| **PipelineRunner No-Live Guard** | 1 test | 1 test | Mock provider, no fetch |
| **PipelineRunner No Cache Mutation** | 1 test | 1 test | tmp_path only |
| **Total Tests** | **12 tests** | **14 tests** | gwangju has more granular tests |

### Test File Mapping

| Test File | Profile | Purpose |
|-----------|---------|---------|
| `tests/test_site_profile.py::TestBukguCrawlFiltersConfig` | bukgu | Loader + static HTML (5 tests) |
| `tests/test_bukgu_crawl_filters_pipeline_regression.py` | bukgu | Pipeline regression (12 tests) |
| `tests/test_site_profile.py::TestGwangjuGoKrCrawlFiltersConfig` | gwangju | Loader + static HTML (5 tests) |
| `tests/test_gwangju_crawl_filters_pipeline_regression.py` | gwangju | Pipeline regression (14 tests) |

### Coverage Gaps (Both Profiles)

- No live smoke validation (deferred by design)
- No deep crawl traversal beyond homepage map (recursive `URLCrawler` not tested end-to-end)
- No sitemap + homepage map + document index integration test with real filters
- No source preservation regression (beyond URL filtering)

---

## 5. Risk Comparison

| Risk Factor | bukgu_gwangju | gwangju_go_kr | Assessment |
|-------------|--------------|---------------|------------|
| **Print (`print=`)** | Low Risk | Low Risk | Print pages duplicate content; both sites have functional non-print pages. Still technically non-zero if a site uses print as primary fallback. |
| **UTM Tracking** | Near-Zero | Near-Zero | Analytics params never change content. Safe to deny globally. |
| **Pagination (`pageNo`, `currentPage`)** | Deferred | Deferred | Not in deny list. Both profiles allow all pagination. Safe but budget risk if deep pagination exists. |
| **Structural Params** | Protected (6) | Protected (6) | mid=, menuId=, board.es, seq=, contentId=, articleId= explicitly protected. Zero crawl loss expected. |
| **Live Smoke** | Deferred | Deferred | No live validation performed. Unknown real-world behavior. |
| **Source Grounding** | Unchanged | Unchanged | No modifications to grounding/query rewrite/composition. |
| **Cache/Snapshots** | Unchanged | Unchanged | No scenario/snapshot/cache mutations. |

### Residual Risks

1. **Live behavior unknown**: No actual HTTP requests against target sites with filters active
2. **Pagination depth**: Deep pagination (page 50+) still allowed → could exhaust budget on large boards
3. **Edge case params**: `fbclid`, `gclid` not in deny list (lower priority than UTM)
4. **Site-specific quirks**: Each site may have unique URL patterns not covered by shared candidate

---

## 6. Decision Options for Stage 400

### Option A: Add Third Municipal Config Candidate (One YAML Only)
- **Pros**: Continues rollout momentum; validates candidate on diverse site
- **Cons**: Multiplies regression surface if latent bug exists; should add no-live regression for third profile before fourth
- **Safety**: Add no-live pipeline regression test for third profile immediately after config

### Option B: Add Source Preservation / Homepage Map Consistency No-Live Regression
- **Pros**: Deepens confidence in existing two profiles; catches issues like filter → map → index → search pipeline integrity
- **Cons**: Delays rollout; tests are harder to design (need synthetic enriched index + search results)
- **Safety**: Highest — validates end-to-end data flow, not just URL filtering

### Option C: Controlled Live Smoke for bukgu/gwangju
- **Pros**: Real-world validation
- **Cons**: Highest risk; can alter snapshots; requires explicit operator approval
- **Safety**: Only with explicit approval + rollback plan

### Option D (Hybrid): Third Config + Source Preservation Test Before Fourth Config
- Add one more config (Option A) with immediate no-live regression
- Then add source preservation regression (Option B) before profile #4
- Live smoke remains deferred

---

## 7. Stage 400 Recommendation

**Recommended: Option D (Hybrid)**

1. **Stage 400**: Add third municipal config candidate (one YAML only) + its no-live pipeline regression test
2. **Stage 401**: Add source preservation / homepage map consistency no-live regression test covering both existing profiles
3. **Stage 402+**: Live smoke only with explicit operator approval

**Rationale**:
- Two profiles now have complete no-live regression baselines — safe to add third
- Source preservation gap exists and should be closed before further expansion
- Live smoke remains highest risk; keep explicit-approval boundary
- This path maintains the "one config + regression test" cadence established in Stages 394-398

---

## 8. Files Not Modified

| Category | Status |
|----------|--------|
| `configs/sites/` | No changes (bukgu + gwangju only) |
| `src/` production code | No changes |
| `tests/` files | No changes |
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

- **Stage 400**: Implement recommended Option D (third config candidate + regression test)
- **Stage 401**: Source preservation no-live regression before fourth config
- **Live Smoke**: Remains explicit-approval only, no automatic schedule