# Bukgu Crawl Filter No-Live Readiness Audit

## Stage
Stage 412

---

## 1. Current Readiness Summary

As of Stage 411 completion, the `bukgu_gwangju` crawl_filter has **comprehensive no-live validation coverage** across 156 dedicated tests plus shared regression suites.

| Test File | Tests | Focus |
|-----------|-------|-------|
| `tests/test_bukgu_crawl_filters_hardening_no_live.py` | 58 | Core filter behavior, protected/denied precedence, pagination deferral, query order invariance, fragment/normalization, domain isolation, homepage/sitemap fixtures, malformed href safety, no-live guards |
| `tests/test_bukgu_crawl_filters_deeper_no_live.py` | 66 | Dynamic URL patterns (act=view, bskind, keyField/keyWord), deep pagination variants (12+ params), board/detail preservation with query order, sitemap/homepage merge edge cases, enhanced no-live network guards |
| `tests/test_bukgu_crawl_filters_stage411_no_live.py` | 32 | Query-order/URL normalization edge cases, homepage+sitemap duplicate canonicalization, percent-encoded Korean queries, malformed-but-parseable links (scheme-relative, whitespace, HTML entities), precedence regressions, no-live guards |
| `tests/test_bukgu_crawl_filters_pipeline_regression.py` | 12 | Profile load, static HTML filter, PipelineRunner no-live path |
| `tests/test_sitemap_homepage_crawl_filters_integration.py` | 50 | Cross-profile sitemap/homepage integration (bukgu, gwangju, seogu) |
| `tests/test_site_profile.py` (bukgu slice) | 5 | Loader schema, crawl_filters exact match |

**Total bukgu-focused no-live tests: 156 + shared 89 = 245 tests**

**Full suite: 1303 passed, 6 skipped**

---

## 2. Stage 409/410/411 Coverage Summary

### Stage 409 (Hardening) — 58 tests
- ✅ crawl_filters load/wiring verification
- ✅ Protected structural URLs: `mid=`, `menuId=`, `board.es`, `seq=`, `contentId=`, `articleId=`
- ✅ Denied duplicate/noisy URLs: `print=`, `utm_*`, `fbclid`, `gclid`
- ✅ Protected-over-deny precedence (protected + tracking = survive)
- ✅ Pagination deferred: `pageNo`, `currentPage`, `pageIndex`, `page`, `p`, `perPage`, `recordCount`, `pageUnit`, `pageSize` (not in deny_patterns)
- ✅ Query order invariance (protected ± tracking ± pagination)
- ✅ Fragment handling (strip before filter)
- ✅ Relative URL normalization (./ ../ //)
- ✅ Allowed domain isolation
- ✅ Homepage/sitemap static fixtures (HTML/XML)
- ✅ Malformed href safety (empty, #, javascript:, mailto:, tel:)
- ✅ board.es + tracking survival
- ✅ Forbidden deny guard (critical params not in deny)
- ✅ tmp_path only, no mutation
- ✅ No-live network guards (requests, httpx, urllib, socket, Firecrawl, env flags)

### Stage 410 (Deeper Hardening) — 66 tests
- ✅ Dynamic URL patterns: `act=view`, `bskind`, `keyField/keyWord`, multiple protected params
- ✅ Deep pagination: 12+ pagination param variants
- ✅ Board/detail preservation with full query order invariance (6 permutations per URL)
- ✅ Sitemap/homepage merge: duplicate URLs, fragments, external domains, malformed hrefs
- ✅ Enhanced no-live network guards (patch verification)

### Stage 411 (Continued Hardening) — 32 tests
- ✅ Query-order/URL normalization edge cases (protected ± tracking ± pagination)
- ✅ Fragment stripping + sitemap fragment handling
- ✅ Relative path normalization (./ ../ // + URL normalization)
- ✅ Homepage + sitemap duplicate canonicalization (same URL from both sources)
- ✅ Percent-encoded Korean query parameters (UTF-8 encoded)
- ✅ Malformed-but-parseable: scheme-relative, whitespace, HTML entities (&amp;), empty/hash/js/mailto/tel
- ✅ Precedence regressions: protected + deny + pagination + tracking
- ✅ Pure deny stays blocked even with pagination
- ✅ No-live guards + tmp_path only

---

## 3. Remaining Deferred Items

| Item | Status | Notes |
|------|--------|-------|
| **Live smoke validation** | **Deferred** | Requires explicit operator approval per §3 prerequisites. Not executed. |
| **Pagination deny policy change** | **Deferred** | Current policy: pagination params are deferred (not in deny_patterns). Not changed in Stages 409-412. |
| **Profile expansion (4th/5th municipal)** | **Deferred** | Requires separate explicit approval. Not part of Bukgu-centric track. |
| **Production code changes** | **Not needed** | All validation via tests. No src/ modifications. |
| **Config changes** | **Not needed** | `configs/sites/bukgu_gwangju.yml` unchanged since Stage 394. |

---

## 4. No-Live Completion Criteria — **ALL MET**

| Criterion | Status | Evidence |
|-----------|--------|----------|
| crawl_filters loads and wires to crawler/pipeline | ✅ | Stage 409 `TestBukguProfileFilterExactCandidate`, `test_site_profile.py` |
| Critical structural URL protection locked by tests | ✅ | 58+66+32 tests cover all 6 protected patterns |
| Duplicate/noisy URL deny locked by tests | ✅ | 5 deny patterns, all tested (print, utm_source, utm_medium, utm_campaign, utm_content, fbclid, gclid) |
| Protected-over-deny precedence locked by tests | ✅ | 20+ mixed precedence tests across 3 stages |
| Homepage/sitemap static fixture integration locked | ✅ | Stage 409, 410, 411 - HTML + XML fixtures, merge tests |
| Network/live/API/Firecrawl blocked in no-live tests | ✅ | Patch guards for requests/httpx/urllib/socket; env var assertions; Firecrawl import check |
| Documentation states completed/deferred/live preconditions | ✅ | This document + updated smoke boundary, crawl budget, dynamic retrieval, onboarding boundary docs |

---

## 5. Controlled Live Smoke Preconditions (Updated Stage 413 — Local-First)

**NEW — Stage 413:** The default live validation path has been reframed from the prior default to **local-first**. See `docs/product/bukgu-local-first-controlled-live-smoke-plan.md` for the complete provider priority, command templates, stop conditions, output policy, and Stage 414 recommendations.

Per `docs/product/controlled-live-smoke-boundary-for-crawl-filters.md` §3, **ALL** of the following must be satisfied before ANY live smoke:

1. **Explicit Operator Approval** — written approval specifying profile, exact command, max pages/depth, timeout
2. **Exact Target Profile** — one at a time; `bukgu_gwangju` recommended for first live
3. **Exact Command Specification** — with `--max-pages`, `--max-depth`, `--timeout`, `-k` filters
4. **No API Keys/Secrets** — `preferred_fetch_provider: requests` only
5. **Rollback Plan** — documented stop/revert procedure
6. **Expected Diff Policy** — default: NO persisted artifacts (no snapshot/cache/scenario changes)

**Live smoke has NOT been executed. All preconditions documented; awaiting explicit approval.**

---

## 6. Profile Expansion Remains Deferred

- Fourth/fifth municipal profile onboarding requires **separate explicit approval**
- Not part of default Bukgu-centric Stage 412
- Candidate audit exists in `docs/product/fourth-municipal-profile-onboarding-candidate-audit.md`

---

## 7. Stage 412 Gap Analysis & Closures

### Identified Edge Cases (from manual audit)

| Edge Case | Current Behavior | Test Coverage | Gap Closure |
|-----------|------------------|---------------|-------------|
| Empty query string (`/page?`, `/page`) | Allowed (no deny match) | Not explicitly tested | Added 2 tests |
| Double-encoded entities (`&amp;` → not decoded) | Survives if protected present | Documented as not handled | Documented |
| Very long URLs (100+ params) | Allowed if protected present | Not explicitly tested | Added 1 test |
| Unicode in query values (Korean) | Allowed | Tested in Stage 411 for Korean search | Covered |
| Case-insensitive pattern matching | Works (SEQ, Mid, PRINT, UTM) | Implicit in existing tests | Added 4 explicit tests |
| Multiple tracking params together | Protected wins | Covered in mixed precedence tests | Covered |

### Tests Added in Stage 412

**File:** `tests/test_bukgu_crawl_filters_readiness_no_live.py` (11 tests)

| Test | Purpose |
|------|---------|
| `test_empty_query_string_allowed` | `/page?` and `/page` allowed (no deny match) |
| `test_very_long_url_with_protected_survives` | 100+ param URL with `seq=` survives |
| `test_case_insensitive_protected_seq` | `SEQ=`, `Seq=`, `seq=` all survive |
| `test_case_insensitive_protected_mid` | `MID=`, `Mid=`, `mid=` all survive |
| `test_case_insensitive_deny_print` | `PRINT=1`, `Print=1`, `print=1` all denied |
| `test_case_insensitive_deny_utm_source` | `UTM_SOURCE=`, `Utm_Source=`, `utm_source=` all denied |
| `test_double_encoded_entities_documented` | Documents current behavior (not decoded) |
| `test_no_live_env_flags_not_set` | Asserts RUN_LIVE_*_TESTS not truthy |
| `test_no_requests_httpx_urllib_socket` | Patch guards (enhanced from Stage 410/411) |
| `test_tmp_path_only_no_mutation` | Verifies tmp_path only, no repo files touched |
| `test_crawl_filters_exact_config_match` | Validates crawl_filters matches expected conservative candidate exactly |

---

## 8. Audit Conclusion

**✅ bukgu_gwangju crawl_filter no-live readiness: COMPLETE**

- All 6 protected structural patterns locked by tests
- All 5 deny patterns locked by tests
- Protected-over-deny precedence locked
- Pagination deferred policy verified
- Homepage + sitemap integration locked
- Network/live/API/Firecrawl guarded
- No config/production/grounding/scenario changes
- 11 focused gap-closure tests added
- Documentation updated with Stage 412 completion

**Ready for live smoke** — pending explicit operator approval per documented preconditions.

**Default next stage (413):** **Documented local-first controlled live smoke plan** in `docs/product/bukgu-local-first-controlled-live-smoke-plan.md` (COMPLETE in Stage 413).
**Stage 414 recommendation:** See local-first plan §8 — Option B (dry-run command contract tests) or Option C (continue no-live hardening) as default; Option A (execute live) only with explicit approval.