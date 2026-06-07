# Query Rewrite to Retrieval Integration Audit

## 1. Purpose

This document presents an engineering audit of the integration between the query rewriter, retrieval/search components, and the answer composer. Following the strict boundary rules established in Stages 378 and 379, the system must not use custom fallback answers to address missing information. Instead, we must ensure that natural language questions about volatile public-sector facts are correctly expanded into valid search queries and executed properly against the search index. This audit systematically inspects the pipeline integration to identify architectural gaps, structural failure causes, and avenues for improvement.

---

## 2. Context After Stages 378–379

- **Stage 378** improved the no-source fallback user experience by intercepting empty search results and outputting structured menu navigation recommendations (e.g., recommending that a user look under `구청장실` or `조직도`).
- **Stage 379** documented the fallback scope and established the rule-expansion policy. It prohibited the practice of hardcoding volatile administrative facts (such as names, numbers, or fee schedules) inside fallback branches.
- **Goal for Stage 380**: Audit the pipeline path to ensure that when a user asks about these volatile facts, the search engine has the best possible chance of retrieving the official source. If a retrieval failure occurs, we must classify why it failed rather than attempting to bypass it with fallback hardcoding.

---

## 3. Current Query Rewrite Components

The query rewrite logic is implemented in [query_rewriter.py](../../src/search/query_rewriter.py):
1. **Normalization (`_normalize_text`)**: Text is cleaned, lowercased, and common Korean grammatical particles (e.g., `은`, `는`, `이`, `가`, `을`, `를`) are stripped from the end.
2. **Expansion Rules (`_EXPANSION_RULES`)**: A static tuple maps regular expression patterns to tuple lists of target search terms.
3. **Site-Specific Synonym Dictionary (`synonym_dictionary`)**: Loaded dynamically from `configs/sites/<site_id>.yml` via `load_profile()`.
4. **Deduplication & Limit**: Rewritten queries are deduplicated while preserving order, then truncated to a maximum limit (default: `max_queries=5`).

---

## 4. Current Retrieval/Search Components

The search logic is implemented in [keyword_searcher.py](../../src/search/keyword_searcher.py):
1. **Tokenization (`tokenize`)**: Text is normalized and split on whitespace. Tokens of length > 1 are added, and their particle-stripped variations are added as extra tokens.
2. **Weighting Matrix**: Fields have pre-defined search weights (Title: 8.0, Link Texts: 7.0, Category: 5.0, Summary: 4.0, Text: 2.0).
3. **N-Gram Fallback**: If a compound token of length >= 4 does not match, the searcher breaks it down into bigram/trigram sub-tokens and searches title/link texts.
4. **Phrase Bonus**: If the exact query phrase matches a field, a score bonus (+5.0 for title, +2.0 for text) is applied.
5. **Deduplication and Ranking**: Results from multiple query candidates are merged in [pipeline_runner.py](../../src/pipeline/pipeline_runner.py#L286-L320), sorted by score descending (and canonical URL for determinism), and truncated to `top_k` (default: 5).

---

## 5. Integration Path: From User Question to Retrieval

```
User Query (e.g., "구청장 누구야?")
    │
    ▼
PipelineRunner.run()
    │
    ├─► _resolve_site_id(url)
    ▼
_step_search()
    │
    ├─► rewrite_query_candidates(query, site_id, max_queries=5)
    │     ├── 1. Apply _EXPANSION_RULES (Global)
    │     └── 2. Apply site_synonyms from profile
    ▼
_search_for_candidates(searcher, query_candidates)
    │
    ├─► Loop through each candidate query
    │     └── searcher.search(candidate, top_k=5)
    ├─► Deduplicate results by canonical_url
    ├─► Sort by -score, canonical_url
    └── Truncate to top_k (5)
    ▼
_step_answer()
    │
    ▼
AnswerComposer.compose(search_data)
    │
    ├─► Check if results or sources are empty
    │     └── TRUE: Short-circuit to _build_no_source_guidance() (Specialized Menu Hints)
    ▼
assess_source_match(query, sources, query_rewrite_queries)
    │
    ├─► Check active predefined topics (e.g., "mayor")
    │     └── Match confirmed?
    │           ├── YES: Pass/Warn -> Compose Grounded Answer via LLM
    │           └── NO: return "no_results" (Mismatched Topics)
    ▼
If assess_source_match returns "no_results":
    └── Return _no_results_answer() (Generic "Not Found" response, NO navigation hints)
```

---

## 6. Public-Sector Volatile Question Audit Matrix

We audited the five key volatile categories to identify how they are handled by the rewriter, synonym profiles, and the source match guard:

| Category | Rewrite Rules in `query_rewriter.py` | Synonym Dictionary (`bukgu_gwangju.yml`) | Source Match Guard Topic Mappings | Integration Status & Gaps |
| :--- | :--- | :--- | :--- | :--- |
| **1. Mayor / Leadership** | `구청장`, `시청장`, `군수`, `도지사`, etc. | **None** (Explicitly deferred in comments) | `mayor` topic mappings checked | **Functional with global rules**, but lacks localized profile synonyms. |
| **2. Staff & Contacts** | **None** | **None** | None (Uses generic token overlap fallback) | **CRITICAL GAP**: No rewrite candidates are generated for "담당자" or "전화번호" queries. |
| **3. Location & Directions** | **None** | **None** | None (Uses generic token overlap fallback) | **CRITICAL GAP**: No rewrite candidates are generated for "주차", "위치", or "오시는 길" queries. |
| **4. Civil Service & Forms** | `민원`, `신청`, `접수`, `서식`, `여권`, etc. | `민원` mapping present | `civil` topic mappings checked | **Redundant configuration**: Profile synonyms duplicate the global rules, adding no extra coverage. |
| **5. Notices & Jobs** | `고시`, `공고`, `공지`, `새소식` / `청년`, `일자리`, `채용` | `공고` mapping present | `notice` and `youth_jobs` mappings checked | **Candidate Truncation risk**: Queries matching multiple rules lose later candidate terms due to `max_queries=5`. |

---

## 7. Findings

### Finding 1: Rewrite Expansion Rules Gap for Contacts and Location
While [answer_composer.py](../../src/answer/answer_composer.py#L278-L291) defines specialized menu guidance buckets for contacts (`조직도`, `직원검색`, `부서안내`) and location/parking (`청사안내`, `오시는 길`, `주차안내`), [query_rewriter.py](../../src/search/query_rewriter.py) lacks any expansion rules for these categories. Consequently:
- A query like "주차 공간 있어?" is not expanded to "오시는 길" or "주차안내".
- A query like "세무과 전화번호 알려줘" is not expanded to "조직도" or "부서안내".
- Retrieval relies purely on exact token matching, leading to high failure rates for menu pages that don't match the user's natural phrasing.

### Finding 2: Silent Truncation of Rewritten Queries
When a query matches multiple regex patterns (e.g., "채용공고 어디서 봐?" matches both the Jobs pattern and the Notice/Announcement pattern), the list of candidates accumulates terms from both categories.
- However, since `PipelineRunner` calls `rewrite_query_candidates()` with `max_queries=5`, the list of candidates is sliced to 5.
- The query expands to: `["채용공고 어디서 봐", "청년", "일자리", "청년 일자리", "채용", "고용", "경제", "고시공고", "공지사항", "공고", "새소식"]`
- Slicing limits this to: `["채용공고 어디서 봐", "청년", "일자리", "청년 일자리", "채용"]`
- Search terms like `고시공고` and `공지사항` are **silently discarded**, preventing the notice-board search.

### Finding 3: Redundant Site-Specific Synonym Dictionary Mappings
In `configs/sites/bukgu_gwangju.yml`, the synonym mappings for `민원` and `공고` return identical terms to the global rewrite rules in `query_rewriter.py`. They do not expand search terms beyond what the global rules already cover, while the actual site-specific needs (such as mapping local office slang or specific municipal departments) are not configured.

### Finding 4: Fallback Degradation on Mismatched Sources
There is a logic discrepancy in [answer_composer.py](../../src/answer/answer_composer.py#L112-L135):
- If the searcher returns **zero** results, the pipeline uses `_build_no_source_guidance()`, displaying category-specific navigation hints.
- If the searcher returns **weak/unrelated** results, `assess_source_match` correctly identifies a topic mismatch and returns `status="no_results"`.
- However, the composer handles this by returning `_no_results_answer()`, which only displays generic "Not Found" messages and **omits the helpful navigation menu hints**. Mismatched search runs thus provide a worse UX than empty search runs.

---

## 8. Risks

1. **Hallucination Risk**: If `assess_source_match` is bypassed or weakened, the system may compose confident answers using irrelevant retrieved documents.
2. **Silent Search Term Starvation**: Slicing the candidate queries to 5 without prioritizing category matches leads to high-quality terms (like `고시공고` for announcement searches) being lost.
3. **Stale Information**: Since site-specific dictionaries lack detailed mappings for municipal services, the system fails to retrieve updated documents, pushing users to empty fallbacks.

---

## 9. Non-Goals

- This audit does not propose or implement changes to the active codebase in this stage.
- It does not bypass the source match guard or relax grounding rules.
- It does not conduct live crawling, fetching, or external API calls.

---

## 10. Recommended Next Stage

To address the findings of this audit, we recommend the following technical stage:

* **Stage Title**: `[TEST] Add offline retrieval integration tests for public-sector volatile questions`
* **Objective**: Implement focused offline integration tests that assert that queries regarding mayor/leadership, contacts, locations, and announcements are correctly rewritten to all necessary candidate search terms (without truncation) and successfully match mock/snapshot indexes, verifying the integration pipeline end-to-end.
