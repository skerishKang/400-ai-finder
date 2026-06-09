# Dynamic Retrieval and Query Learning Strategy

## 1. Purpose

400-ai-finder should not become a static scenario-answer system. The product goal is to let users ask natural questions about a target official site.

* **New or long-tail questions** should use live retrieval + LLM.
* **Repeated, high-confidence, stable questions** may be promoted into scenarios/snapshots/cache for speed and reliability.

> **Principle**:  
> LLM/live retrieval is the default path.  
> Scenario/snapshot/cache is the acceleration path.

---

## 2. Problem Discovered in Stage 340

> Stage 340 found that a scenario-outside question such as "구청장이 누구야?" could be incorrectly routed to unrelated snapshot sources.
> The immediate stale-source bug was fixed in Stage 341.
> However, the broader product issue remains: the system lacks dynamic query rewriting, query learning, and scenario promotion.

* Stage 341 fixed stale source reuse.
* But fixing stale sources only prevents bad grounding.
* It does not make the system good at finding new answers.

---

## 3. Current Architecture Limits

```txt
- KeywordSearcher uses raw query tokenization.
- Korean particle stripping and n-gram fallback exist, but semantic query expansion does not.
- No LLM query rewriter exists.
- No synonym or menu-term expansion exists.
- No question logging exists.
- No repeated-question analytics exists.
- No dynamic scenario/cache promotion exists.
- Snapshot/scenario data is useful for demos and regression tests, but cannot cover all user questions.
```

---

## 4. Target Product Architecture

```
User question
  ↓
Question normalization
  ↓
Fast-path lookup:
  - exact scenario/cache hit
  - high-confidence repeated question hit
  ↓
If no high-confidence hit:
  dynamic query rewrite / expansion
  ↓
live retrieval from target site
  ↓
source ranking and domain grounding
  ↓
LLM grounded answer composition
  ↓
answer + source URLs
  ↓
question/result logging
  ↓
analytics and scenario/cache promotion candidate generation
```

### Fast Path vs Default Path

| Path | Use Case | Data Source |
|------|----------|-------------|
| **Fast path** | Stable, repeated, already-validated questions | scenario/snapshot/cache |
| **Default path** | New, changing, long-tail, time-sensitive questions | live retrieval + LLM |

---

## 5. Scenario/Snapshot Role

### Scenarios/snapshots ARE for:

```txt
- demo stability
- smoke tests
- regression tests
- repeated FAQ acceleration
- offline mode
- known stable pages
```

### Scenarios/snapshots are NOT for:

```txt
- covering every possible user question
- replacing live retrieval
- answering changing information without source refresh
- hardcoding one-off answers
```

> Adding a "구청장" scenario is not the product-level solution.  
> The product-level solution is better retrieval and question learning.

---

## 6. Dynamic Query Rewrite Strategy

### First-Stage Query Rewriting

| User Question | Candidate Retrieval Queries |
|--------------|----------------------------|
| 구청장이 누구야? | 북구청장, 구청장 인사말, 구청장 프로필, 열린구청장, 북구청장 소개 |
| 청년 일자리 어디서 봐? | 청년, 일자리, 채용, 고용, 경제, 비즈광주북구 |

### Design Requirements

```txt
- Query rewrite should be provider-optional at first.
- It should support mock/stub tests.
- It must never fabricate answers.
- It should output search terms, not final answers.
- It should be auditable in logs.
- It should preserve the original user question.
```

---

## 7. No-Results and Source Mismatch Guard

### If retrieval returns no relevant sources:

```txt
- answer should say relevant official source was not found
- do not answer using stale or unrelated sources
- suggest alternative keywords or official menu terms
```

### If sources are weak:

```txt
- return WARN-style answer
- show sources
- say that the result may require official-site confirmation
```

### If source topic and question topic mismatch:

```txt
- do not compose a confident answer
- prefer no-results or low-confidence response
```

> Stage 341 implemented the first guard by clearing stale snapshot sources when fallback matching returns empty.
> Stage 378/379 established the strict safety boundaries for no-source fallback responses to prevent rule-expansion drift. For detailed policies, see the [No-Source Fallback Scope and Rule-Expansion Policy](./no-source-fallback-scope-and-rule-expansion-policy.md).

---

## 8. Question Logging and Analytics

### Log Fields (conceptual design only — not implemented)

```txt
- timestamp
- site_id
- normalized question
- raw question
- provider mode
- retrieval mode
- search terms used
- result count
- source domains
- answer status: PASS / WARN / NO_RESULTS / ERROR
- fallback_used
- user feedback if available
```

### Privacy/Security Rules

```txt
- do not log API keys
- do not log secrets
- avoid storing personally sensitive information unless necessary
- consider hashing user/session identifiers if added later
```

---

## 9. Query Learning and Scenario Promotion

### Promotion Flow

```
Question logs
  ↓
Cluster similar questions
  ↓
Detect repeated questions
  ↓
Check retrieval quality and answer success
  ↓
Generate scenario/cache candidate
  ↓
Human review
  ↓
Promote to validated scenario/snapshot/cache
```

### Candidate Promotion Criteria

```txt
- repeated more than a threshold, e.g. 3+ times per week
- stable answer source
- official-domain grounded
- low failure rate
- no sensitive or personal query content
- reviewer approval
```

> Do not auto-promote directly to committed fixtures without review.

---

## 10. Metrics

```txt
- no-results rate
- fallback rate
- source mismatch rate
- official-domain grounding rate
- repeated-question rate
- scenario/cache hit rate
- user re-question rate
- low-confidence answer rate
- query rewrite success rate
```

### Why These Matter

* They show where retrieval is failing.
* They show which questions should become scenario/cache candidates.
* They help distinguish product gaps from site-structure gaps.

---

## 11. Implementation Roadmap

### Completed
- Clear stale snapshot sources when fallback matching returns empty (Stage 341).
- Add deterministic query rewriter design and test boundary (Stage 343).
- Integrate query rewrite candidates into the pipeline search path (Stage 344a).
- Add source mismatch / no-results guard hardening (Stage 344b).
- Add offline-safe question logging boundary (Stage 351).
- Add repeated-question analyzer and human-review promotion planning (Stage 352).
- Add repeated-question analytics dry-run report CLI (Stage 353).
- Add operator question log guide, promotion review workflow, review template, synthetic dry-run guide, and docs audit cleanup (Stages 354-358).

### Remaining candidates

#### Retrieval quality
- Audit hybrid keyword + vector search options.
- Audit semantic menu matching options.
- Audit site-specific synonym dictionary strategy.
- Evaluate whether query rewrite coverage should expand beyond the current deterministic patterns.

#### Operator workflow
- Run the first real sanitized-log operator dry-run only when actual sanitized logs exist.
- Keep real-log review local/offline/report-only unless a separate production logging policy is approved.

#### Promotion workflow
- Keep scenario/cache promotion manual.
- Create cache, scenario, snapshot, or retrieval-improvement implementation issues only after human review.
- Do not automatically create scenarios, snapshots, caches, commits, or pull requests from repeated-question analytics.

---

## 12. Non-Goals

```txt
- Do not create scenarios for every possible question.
- Do not hardcode "구청장" or other one-off answers.
- Do not make LLM answer without grounded sources.
- Do not require live provider for offline tests.
- Do not break existing snapshot/demo behavior.
```

---

## Implementation Status

### Stage 341 — P0 Bug Fix (Completed)
- Clear stale snapshot sources when fallback matching returns empty.

### Stage 343 — Query Rewriter Contract (Completed)
- Added `src/search/query_rewriter.py` with offline-safe deterministic query rewriter.
- Produces retrieval query candidates only — does not generate answers.
- Supports mayor, youth/jobs, civil service, notice, welfare, and education query patterns.
- Preserves original question exactly, deduplicates candidates, limits to `max_queries`.
- No live LLM/API/network calls.
- 18 contract tests added in `tests/test_query_rewriter.py`.

### Stage 344a — Query Rewriter Pipeline Integration (Completed)
- Integrates deterministic query rewrite candidates into the offline-testable pipeline search path.
- Original question preserved for answer composition in `query_rewrite` metadata.
- Results across rewritten queries are deduplicated by canonical URL.
- Existing keyword search behavior preserved for ordinary questions.
- 8 integration tests added in `tests/test_query_rewriter_pipeline_integration.py`.

### Stage 344b — Source Mismatch Guard Hardening (Completed)
- Stage 344b adds source mismatch guard hardening for weak retrieval results. The guard prevents confident answers from being composed when retrieved sources do not sufficiently align with the original user question.

### Stage 351 — Question Logging Boundary (Completed)
- Stage 351 adds an offline-safe question logging boundary. The initial boundary supports sanitized structured question events and optional local JSONL logging, without analytics, clustering, scenario promotion, external storage, or live provider calls.

### Stage 352 — Repeated-Question Analytics and Promotion Planning (Completed)
- Stage 352 adds repeated-question analytics and scenario/cache promotion planning. The boundary treats repeated questions as human-review candidates only and does not automatically create scenarios, snapshots, caches, or pull requests.

### Stage 353 — Repeated-Question Analytics Dry-Run Report (Completed)
- Stage 353 adds a local dry-run repeated-question analytics report for human review. It keeps promotion manual and does not write scenario/snapshot/cache files.
- The CLI reads sanitized JSONL question logs and produces a Markdown report separating promotion candidates from retrieval gaps.
- No live network, LLM, fetch, or external storage calls are used.

### Stage 354 — Operator Question Log Guide (Completed)
- Stage 354 adds an operator guide for collecting sanitized question logs and running local dry-run analytics reports. It keeps logging local/offline and requires human review before any scenario/cache promotion.
- The guide documents safe JSONL format, what must never be logged, the dry-run report command, and the human review workflow.
- No code or test changes. Docs-only.

### Stage 355 — Scenario/Cache Promotion Review Workflow (Completed)
- Stage 355 adds the human review workflow for scenario/cache promotion candidates. It defines how dry-run report candidates should be classified as cache review, scenario review, retrieval gaps, or monitor-only items, without automatic promotion.
- Adds review checklists, a decision matrix, and follow-up issue templates for cache, scenario, and retrieval-gap candidates.
- Cross-linked from the repeated-question analytics promotion plan and the operator quickstart.
- No code or test changes. Docs-only.

### Stage 356 — Promotion Candidate Review Template (Completed)
- Stage 356 adds a copy-pasteable promotion candidate review template for human reviewers. It supports cache, scenario, retrieval gap, monitor-only, and reject decisions without automatic promotion.
- Includes a decision guide table, per-category checklists, and a synthetic completed review example.
- Cross-linked from the scenario/cache promotion review workflow, the repeated-question analytics promotion plan, and the operator quickstart.
- No code or test changes. Docs-only.

### Stage 357 — Synthetic Promotion Dry-Run Operator Guide (Completed)
- Stage 357 adds a synthetic-only operator dry-run guide showing how to run repeated-question analytics with local JSONL examples and copy findings into the promotion candidate review template.
- The guide demonstrates cache candidate, scenario candidate, retrieval gap, and monitor-only review outcomes.
- No code or test changes. Docs-only.
- No live network, LLM, fetch, Firecrawl, scenario, snapshot, cache, PR, or automatic promotion behavior is added.

### Stage 358 — Operator Docs Completeness Audit (Completed)
- Stage 358 audits the Stage 354–357 operator documentation set and confirms that the repeated-question promotion workflow is sufficiently documented for manual, human-reviewed operation.
- It fixes stale roadmap wording in the repeated-question analytics promotion plan so the docs no longer imply automated scenario skeleton generation.
- No code or test changes. Docs-only.
- No live network, LLM, fetch, Firecrawl, scenario, snapshot, cache, PR, or automatic promotion behavior is added.

### Stage 360 — Dynamic Retrieval Roadmap Cleanup (Completed)
- Stage 360 cleans up stale roadmap and follow-up wording in this strategy document after the operator docs track closed.
- It moves completed Stage 343-358 work out of future/next roadmap wording and keeps future candidates focused on genuinely remaining retrieval/productization gaps.
- No code or test changes. Docs-only.
- No live network, LLM, fetch, Firecrawl, scenario, snapshot, cache, PR, or automatic promotion behavior is added.

### Stage 363 — Site-Specific Synonym Dictionary Contract (Completed)
- Stage 363 adds the optional `synonym_dictionary` field to `SiteProfile` and a `site_id`-aware retrieval term expansion path in the offline query rewriter.
- Profiles that omit the field still load unchanged; invalid entries are filtered silently.
- Re-writer load failures are silent fallbacks — global behavior is preserved.
- No live network, LLM, fetch, Firecrawl, scenario, snapshot, cache, PR, or automatic promotion behavior is added.
- 9 new focused tests added; 0 regressions.

### Stage 365 — First bukgu_gwangju Synonym Dictionary Slice (Completed)
- Stage 365 adds the first config-only `synonym_dictionary` data slice to `configs/sites/bukgu_gwangju.yml`.
- The slice is limited to stable official menu vocabulary for `민원`, `공고`, and `교육`.
- Deferred groups such as `구청장`/`열린구청장`, `복지`, `정보공개`, and `청년일자리` are intentionally excluded.
- 7 new focused tests added; 0 regressions.
- No live network, LLM, fetch, Firecrawl, scenario, snapshot, cache, PR, or automatic promotion behavior is added.

### Stage 368 — Offline Retrieval Evidence for Bukgu Synonym Slice (Completed)
- Stage 368 adds a small synthetic offline enriched-index fixture (`tests/test_bukgu_synonym_offline_retrieval.py`) and confirms that site_id-aware rewrite surfaces the intended menu documents.
- A separate AST-based test documents the integration gap that `PipelineRunner._step_search` does not forward `site_id` to `rewrite_query_candidates`.
- No new synonym data, live network, LLM, fetch, Firecrawl, scenario, snapshot, cache, PR, or automatic promotion behavior is added.

### Stage 369 — Pipeline Site ID Query Rewrite Wiring (Completed)
- Stage 369 wires `PipelineRunner._step_search()` to forward the resolved `site_id` to `rewrite_query_candidates()`.
- `site_id` is now resolved once per `run()` and reused for both the search step and question logging.
- The Stage 368 gap-documenting test is replaced with positive wiring coverage (AST guard + runtime retrieval test + `site_id=None` non-leakage guard).
- Search result metadata now records `query_rewrite.site_id` for observability.
- No new synonym data, live network, LLM, fetch, Firecrawl, scenario, snapshot, cache, PR, or automatic promotion behavior is added.

### Stage 378 — No-Source Guidance Fallback (Completed)
- Stage 378 improves no-source guidance fallback with visible menu hints.
- The fallback path remains entirely provider-free, avoiding LLM calls when sources are absent.
- Adds visible Markdown bullet assertions for public-sector fallback categories (e.g., mayor, contacts, location, forms).

### Stage 379 — Fallback Scope Audit and Policy Definition (Completed)
- Stage 379 audits the fallback scope and defines strict guidelines in `docs/product/no-source-fallback-scope-and-rule-expansion-policy.md` to prevent rule-expansion drift.
- Confirms the boundaries between dynamic RAG retrieval (query rewrite, source match guard, source-backed composer) and the static, provider-free no-source fallback.
- No code or test changes. Docs-only.

### Stage 380 — Query Rewrite and Retrieval Integration Audit (Completed)
- Stage 380 audits the integration path between the query rewriter, keyword searcher, and source match guard for public-sector volatile questions.
- Identifies critical gaps in rewrite rules (missing rules for Contacts and Location), candidate query truncation due to `max_queries=5`, and redundant site synonym mappings.
- Documents findings and maps out a roadmap in [query-rewrite-retrieval-integration-audit.md](./query-rewrite-retrieval-integration-audit.md).
- No code or test changes. Docs-only.

### Stage 384 — Municipal Service Crawl and Index Completeness Audit (Completed)
- Stage 384 audits the site profile configurations, crawl pipelines, and indexing structures for public-sector municipal services.
- Identifies limitations in current link classification keywords (missing mapping for contacts, locations, and announcement synonyms) and crawl budget starvation risks under recursive crawling.
- Outlines recommendations for Stage 385 to expand category keyword classification and introduce targeted crawl rules.
- No code or test changes. Docs-only.

### Stage 385 — Expand Municipal URL Classification Keywords (Completed)
- Stage 385 expands `classify_url()` in `src/crawler/homepage_mapper.py` to support Korean and English public-sector keywords.
- Maps contact/org keywords (`조직도`, `직원검색`, `부서안내`, `전화번호`, `담당자`, `담당업무`) to `contact`.
- Maps notice keywords (`공고`, `고시공고`, `입법예고`, `채용공고`) to `notice`.
- Introduces `location` category output for location/parking keywords (`청사`, `청사안내`, `오시는 길`, `오시는길`, `찾아오시는길`, `주차`, `주차안내`, `위치`, `parking`).
- Keeps crawl traversal behavior unchanged.

### Stage 386 — Crawl Budget Path Filtering Policy (Completed)
- Stage 386 establishes a policy for crawl budget protection and URL path filtering for public-sector websites.
- Identifies safe deny candidates (print layouts, tracking params, sorting noise, and deep pagination) and dangerous parameters that must never be blocked by default (menu, article, and content IDs).
- Establishes a precedence hierarchy (allow overrides deny, explicit deny, site-specific local overrides global, and protected escape hatch rules).
- Recommends Stage 387 for helper-only pure function implementation.
- No code, test, or config changes. Docs/design-only.

### Stage 387 — Add Crawl Path Filter Decision Helper (Completed)
- Stage 387 implements the pure filter decision helper function `should_crawl_url` in `src/crawler/crawl_path_filter.py`.
- Integrates deterministic precedence logic (protected patterns override denies, allow patterns override denies, explicit denies block, default allow).
- Asserts correctness via 8 focused unit tests in `tests/test_crawl_path_filter.py`.
- Keeps the helper completely unwired from the crawler traversal pipeline to prevent runtime side effects.
- Recommends Stage 388 to plan integration and configuration mapping.

### Stage 388 — Crawl Path Filter Integration Boundary Audit (Completed)
- Stage 388 completes an audit of the helper integration boundary in `docs/product/crawl-path-filter-integration-boundary-audit.md`.
- Evaluates the safely selected path (Option 1: SiteProfile schema/config support first) and defer wiring traversal logic to Stage 390.
- Outlines protected municipal URL parameters and required test coverage mapping.
- No code, test, or config changes. Docs-only.

### Stage 389 — SiteProfile Config Schema Support (Completed)
- Stage 389 implements the `crawl_filters` property parsing contract in `SiteProfile` class (`src/site_profiles/site_profile.py`).
- Cleans and formats raw dictionary input: strips/excludes blank strings, filters out non-string items, ignores unknown keys, and defaults safely to empty lists for backward compatibility.
- Asserts parsing contract via 6 new focused tests in `tests/test_site_profile.py`.
- Keeps the helper completely unwired from the runtime crawler traversal logic.
- Recommends Stage 390 to wire the helper in `url_crawler.py` behind a default-allow fallback.

### Stage 390 — Wire Crawl Path Filter into URLCrawler (Completed)
- Stage 390 wires the `should_crawl_url` decision helper and the `SiteProfile.crawl_filters` config properties into `URLCrawler` traversal (`extract_links` phase).
- Default behavior preserves 100% of discovered internal links when `crawl_filters` is `None` or `{}` (default-allow).
- Fully validated via extensive unit tests in `tests/test_url_crawler.py` covering overrides, explicit denies, and municipal structural URL safety.
- Recommends Stage 391 for site-profile-to-crawler integration path.

### Stage 391 — SiteProfile-to-URLCrawler Mapping Integration (Completed)
- Stage 391 integrates the parsed `SiteProfile.crawl_filters` config properties with `URLCrawler` instantiations in the pipeline path.
- Resolves matched profiles in `PipelineRunner` and passes `crawl_filters` down to `HomepageMapper` and the underlying `URLCrawler`.
- Fully tested using synthetic profiles, verifying legacy default-allow compatibility, mock HTML crawl safety, and flat link fallback contracts.
- Recommends Stage 392 for real site profile candidate configurations.

### Stage 392 — Design Municipal candidates Audit (Completed)
- Stage 392 completes an audit of municipal crawl filter candidates in `docs/product/municipal-crawl-filters-candidate-audit.md`.
- Establishes highly conservative candidate configuration rules (deny prints, tracking parameters, protect structural parameters, keep allow patterns empty by default to prevent accidental override of denies).
- Maps a catalogue of protected parameters to prevent crawl loss on Notice Detail and Menu pages, and provides risk analysis for pagination and print views.
- Establishes a comprehensive test validation plan for Stage 393.
- Recommends Stage 393 for config fixture contract tests.

### Stage 393 — Config Fixture Contract Tests (Completed)
- Stage 393 implements the complete contract verification test plan in `tests/test_municipal_crawl_filters_config_contract.py` before any real configs are changed.
- Validates the candidate rules via synthetic mock HTML crawlers, ensuring tracking parameters are denied while protected/structural municipal URLs are kept.
- Locks down pagination parameters (`pageNo`, `currentPage`) as deferred.
- Enforces deny-list forbidden guards statically, preventing critical fields from being denied.
- Recommends Stage 394 to introduce the first real configs.

### Stage 394 — First Real Profile Config Candidate (Completed)
- Stage 394 applies the first conservative `crawl_filters` config candidate. Changed exactly only one profile: `configs/sites/bukgu_gwangju.yml`.
- Adds targeted loader, validation, and safety unit tests under `tests/test_site_profile.py` using mock/static HTML.
---

### Stage 395 — Post-Merge Audit / No-Live Regression Check (Completed)

- Stage 395 conducts a post-merge audit on the first real config candidate.
- Verifies single-profile isolation and low risk of regression across print and tracking variables.
- Defers live validation completely and keeps testing isolated.
- Recommends Stage 396 Option B (no-live pipeline regression test for bukgu profile filters) to construct an end-to-end integration path test.

---

### Stage 396 — No-Live Pipeline Regression Test for Bukgu Crawl Filters (Completed)

- Stage 396 adds no-live regression tests in `tests/test_bukgu_crawl_filters_pipeline_regression.py` for the real `bukgu_gwangju` `crawl_filters` config.
- **Test Coverage**:
  - **A**: Profile load verification — `SiteProfileLoader.load_by_id("bukgu_gwangju")` loads `crawl_filters` with Stage 394 deny/protected patterns.
  - **B**: Static HTML filtering — `URLCrawler` with real filters preserves protected municipal URLs (`mid=`, `seq=`, `contentId=`, `articleId=`, `board.es`, pagination) and denies print/tracking (`print=`, `utm_*`).
  - **C**: `PipelineRunner(provider="mock")` passes real profile `crawl_filters` to `HomepageMapper` → `URLCrawler` with zero live network/API/Firecrawl calls.
- **Verification**: 12 focused tests pass; full pytest suite (920 tests) clean.
- **No Config/Production/Source Grounding/Scenario/Cache Changes**.
- **Live Smoke Still Deferred**: Explicit approval still required.

### Stage 397 Recommended Next

- Add second municipal config candidate (one YAML) or extend no-live regression coverage.
- Live smoke remains explicit-approval only.

---

### Stage 397 — Add Second Municipal Crawl Filters Candidate (Completed)

- Stage 397 applies the same conservative `crawl_filters` candidate to a second real municipal profile: **`configs/sites/gwangju_go_kr.yml` (광주광역시청 / `gwangju_go_kr`)**.
- **Selection Criteria Met**:
  - Existing real municipal/public-sector SiteProfile loaded by SiteProfileLoader
  - LEGACY_BOARD_SITE classification with compatible URL patterns (boardList.do, contentsView.do)
  - No prior crawl_filters configuration
- **Config Changes**: Single YAML file only (`configs/sites/gwangju_go_kr.yml`), identical conservative candidate to bukgu.
- **Test Changes**: Added `TestGwangjuGoKrCrawlFiltersConfig` (5 tests) in `tests/test_site_profile.py`:
  1. Profile loader verification (crawl_filters match candidate exactly)
  2. Protected patterns verification (all 6 required params)
  3. Deny patterns verification (all 5 required params)
  4. Forbidden deny guard (critical params NOT in deny_patterns)
  5. Static HTML behavior using second profile filters (mock gwangju.go.kr URLs)
- **No Live/Network/API/Firecrawl**: Mock/static HTML only.
- **No Production Code Changes**: `src/` untouched.
- **Bukgu Config Unchanged**: `configs/sites/bukgu_gwangju.yml` not modified.
- **Verification**: 5 new tests pass; full suite 925 tests clean.
- **Live Smoke Still Deferred**: Explicit approval required.

### Stage 398 Recommended Next

- Add no-live pipeline regression test for `gwangju_go_kr` profile (mirroring Stage 396).
- Compare first/second config rollout behavior before further expansion.
- Live smoke remains explicit-approval only.

---

### Stage 398 — No-Live Pipeline Regression Test for Gwangju Crawl Filters (Completed)

- Stage 398 adds no-live regression tests in `tests/test_gwangju_crawl_filters_pipeline_regression.py` for the real `gwangju_go_kr` `crawl_filters` config.
- **Test Coverage**:
  - **A**: Profile load verification — `SiteProfileLoader.load_by_id("gwangju_go_kr")` loads `crawl_filters` with Stage 397 deny/protected patterns.
  - **B**: Static HTML filtering — `URLCrawler` with real filters preserves protected municipal URLs (`mid=`, `seq=`, `contentId=`, `articleId=`, `board.es`, pagination) and denies print/tracking (`print=`, `utm_*`).
  - **C**: `PipelineRunner(provider="mock")` passes real profile `crawl_filters` to `HomepageMapper` → `URLCrawler` with zero live network/API/Firecrawl calls.
- **Verification**: 14 focused tests pass; full pytest suite (939 tests) clean.
- **No Config/Production/Source Grounding/Scenario/Cache Changes**.
- **Live Smoke Still Deferred**: Explicit approval still required.

### Stage 399 Recommended Next

- Compare first/second config rollout behavior before further expansion.
- Add third municipal config candidate (one YAML only) after no-live regression baseline established for both profiles.
- Live smoke remains explicit-approval only.

---

### Stage 399 — First/Second Rollout Comparison Audit (Completed)

- Stage 399 adds a comparison audit in `docs/product/crawl-filters-first-second-rollout-comparison-audit.md` for the first two real municipal `crawl_filters` rollouts.
- **Comparison Coverage**:
  - Rollout inventory: bukgu_gwangju (Stage 394/396, 12 tests) vs gwangju_go_kr (Stage 397/398, 14 tests)
  - Shared candidate rules: identical conservative config (empty allow, 5 deny, 6 protected)
  - Test coverage matrix: loader, deny/protected exact match, forbidden deny, static HTML preserve/deny, pagination deferred, pipeline no-live regression
  - Risk comparison: print (low), UTM (near-zero), pagination (deferred), structural (protected)
  - Stage 400 decision options: A (third config), B (source preservation), C (live smoke), D (hybrid)
- **Decision**: Stage 400 should follow Option D (Hybrid) — third config candidate + no-live regression, then source preservation regression before fourth config.
- **No Config/Code/Test Changes** — docs only.
- **Live Smoke Still Deferred**: Explicit approval required.

### Stage 400 Actual Outcome

**Stage 400 (PR #744) was closed not planned / not merged.**

- **Reason**: Stage 400 required selecting an *existing* municipal profile without crawl_filters from `configs/sites/`. At the time, `configs/sites/` contained only `bukgu_gwangju.yml` and `gwangju_go_kr.yml` (both already with crawl_filters). The PR attempted to add `seogu_gwangju.yml` as a **new file**, which violated the "existing profile only" constraint.
- **Lesson**: Adding a new YAML to `configs/sites/` = **profile onboarding**, not crawl_filters rollout. These are separate tracks with different validation requirements.

### Stage 401 Implementation Status (Completed)

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

### Stage 402 Implementation Status (Completed)

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

### Stage 403 Implementation Status (Completed)

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

### Stage 404 Recommended Next

1. Add one new municipal profile via onboarding rules, or continue no-live coverage for existing 3 profiles.
2. Live smoke only with explicit approval.

---

## 13. Example: "구청장이 누구야?"

### Correct Behavior After Stage 341

```txt
Snapshot mode:
- no relevant fallback source
- no stale source reuse
- no-results response
```

### Target Future Behavior

```txt
Live retrieval mode:
- rewrite query to "북구청장", "구청장 프로필", "열린구청장"
- retrieve official source
- compose grounded answer with source URL
```

### Scenario Role

```txt
If many users repeatedly ask this and the source is stable, promote a validated mayor_identity scenario/cache entry after human review.
```

---

## 14. Open Follow-Up Candidates

> List issue candidates only when they represent genuinely remaining work. Do not create all unless instructed.

Recommended follow-ups:

```txt
[TEST] Add offline retrieval integration tests for public-sector volatile questions
[AUDIT] Evaluate hybrid keyword + vector search options
[AUDIT] Evaluate semantic menu matching options
[AUDIT] Evaluate site-specific synonym dictionary strategy
[OPS] Run first real sanitized-log operator dry-run when sanitized logs exist
[PRODUCT] Define production logging/storage policy before any shared or persistent real-log workflow
```

Deferred until real sanitized logs exist:

```txt
[OPS] First real operator dry-run with sanitized logs
[REVIEW] Evaluate cache/scenario candidates from real dry-run report
[TECH] Implement approved retrieval improvement from real retrieval-gap report
```

Do not create scenario, snapshot, cache, or promotion PRs automatically from this list.