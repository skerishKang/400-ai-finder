# Municipal Service Crawl/Index Completeness Audit

## Stage
Stage 384

## Scope
Evaluation of site profile configurations, crawl pipelines, and indexing completeness for Korean public-sector/municipal services (specifically Gwangju Bukgu and Gwangju City Hall profiles). Assessment of page discoverability, crawl rules, classification mapping, index field sufficiency, and testing coverage for six target categories of volatile municipal services.

## Files inspected
- [`configs/sites/bukgu_gwangju.yml`](../../configs/sites/bukgu_gwangju.yml)
- [`configs/sites/gwangju_go_kr.yml`](../../configs/sites/gwangju_go_kr.yml)
- [`src/site_profiles/site_profile.py`](../../src/site_profiles/site_profile.py)
- [`src/crawler/url_crawler.py`](../../src/crawler/url_crawler.py)
- [`src/crawler/homepage_mapper.py`](../../src/crawler/homepage_mapper.py)
- [`src/crawler/sitemap_parser.py`](../../src/crawler/sitemap_parser.py)
- [`src/indexer/document_indexer.py`](../../src/indexer/document_indexer.py)
- [`src/indexer/document_enricher.py`](../../src/indexer/document_enricher.py)
- [`tests/test_url_crawler.py`](../../tests/test_url_crawler.py)
- [`tests/test_homepage_mapper.py`](../../tests/test_homepage_mapper.py)
- [`tests/test_sitemap_parser.py`](../../tests/test_sitemap_parser.py)
- [`tests/test_document_indexer.py`](../../tests/test_document_indexer.py)
- [`tests/test_document_enricher.py`](../../tests/test_document_enricher.py)
- [`tests/test_retrieval_integration_public_sector.py`](../../tests/test_retrieval_integration_public_sector.py)



## Municipal service categories reviewed
| Category | Example queries | Current coverage | Risk | Notes |
|---|---|---|---|---|
| 조직도 / 직원검색 / 부서안내 | "세무과 조직도 보여줘", "부서별 전화번호안내" | **Poor** (Classified as `menu`/`unknown`) | High (Search keywords like `조직도`, `직원검색`, `부서안내` are missing in `classify_url()`) | Falls back to generic menu matching; relies entirely on anchor tag presence in navigation. |
| 담당자 / 연락처 / 전화번호 | "여권 담당자 전화번호", "구청 전화번호부" | **Fragile** (Only `연락` matches; others are `menu`/`unknown`) | High (`전화번호`, `담당자` are missing in `classify_url()` contact keywords) | Pure keyword match is fragile. If sitemap lacks detailed subpages, depth limit (3) cuts it off. |
| 청사안내 / 오시는 길 / 주차안내 | "구청 주차요금", "오시는길 대중교통", "청사 위치" | **Poor** (Classified as `menu`/`unknown`) | High (None of `청사`, `오시는 길`, `주차`, `위치` match any category keywords) | Cannot be mapped to `contact` or other high-priority categories. Remains as `menu`/`unknown`. |
| 민원 / 민원서식 / 신청 / 접수 | "민원 신청 서식", "여권 접수처" | **Good** (Classified as `document`/`apply`) | Low (`서식` matches `document`, `신청`/`접수` match `apply`) | Best performing category due to specific keywords in global crawler configuration. |
| 고시공고 / 공지사항 / 새소식 / 채용공고 | "채용공고 일정", "구청 고시공고" | **Fragile** (Classified as `menu`/`unknown`/`notice`) | Medium (`공고` is missing from `notice_keywords` in `classify_url()`) | Vague menu names (like `새소식`, `공지사항`) match, but `공고` matches nothing. board paginations are not filtered. |
| 구청장실 / 기관장 소개 / 인사말 / 프로필 | "구청장 인사말", "구청장 약력" | **Fragile** (Classified as `menu`/`unknown`) | Medium (No custom keywords in `classify_url()`) | Relies on presence inside homepage navigation elements to be mapped as `menu`. |

## Site profile findings
- **Lack of Path Rules**: Both `bukgu_gwangju.yml` and `gwangju_go_kr.yml` contain no explicit inclusion/exclusion (whitelist/blacklist) rules for crawler paths. The crawler relies on recursive depth-3 link traversal, which sweeps up massive amounts of duplicate pagination parameters, print templates, and irrelevant page views.
- **Sitemap Discrepancy**: Gwangju Bukgu has no functional sitemap (marked in notes), which forces the system to rely completely on homepage menu scanning and recursive link crawling. If the menu navigation elements do not explicitly link to a subpage, or if it is deeper than 3 clicks, the page is completely undiscoverable.
- **Redundant Synonym dictionary**: Synonyms defined in `bukgu_gwangju.yml` (e.g., `민원`, `공고`, `교육`) merely duplicate global rewrite rules, offering no localized value (like department names or specific regional service abbreviations).

## Crawl/index pipeline findings
- **Keyword Gaps in `classify_url()`**: The classification function in `src/crawler/homepage_mapper.py` determines document categories that are critical for retrieval scoring and priority. However, key municipal keywords are completely missing from its classification rules:
  - `contact_keywords`: Missing `조직도`, `직원검색`, `부서안내`, `전화번호`, `담당자`. Only `연락` is present.
  - `notice_keywords`: Missing `공고` (a highly frequent term in Korean public sites).
  - `location/parking`: Lacks a dedicated category and contains no keywords like `청사`, `오시는 길`, `주차`, `위치`, `parking`.
- **Crawl Budget Exhaustion (Starvation)**: With `max_pages` limited to 200 (Bukgu) and 300 (Gwangju), a recursive crawler can easily exhaust the entire quota crawling board lists and paginated article views (e.g., page 1 to 50 of general announcements) before ever reaching static department/service directories or location maps.
- **URL Normalization Limitations**: `make_canonical_url()` strips fragments but preserves query parameters. Public sector sites use complex J2EE/EGOV parameters where the same page can be represented by multiple param order permutations or print/mobile views, causing indexing duplicates or document text overwrite.

## Index field sufficiency
- **Keyword Fields are Sufficient**: Fields like `title`, `text`, `metadata.link_texts`, and `canonical_url` provide strong raw material for KeywordSearcher matching.
- **Summary Field is Unused**: Although `summary` has a weight of 4.0 in `KeywordSearcher`, the enrichment stage (`DocumentEnricher`) does not generate summaries (it retrieves raw `text` and `description` only). Thus, the `summary` field remains empty and its retrieval weight is wasted.
- **Misclassified Categories Lower Retrieval Scores**: In `KeywordSearcher.search()`, category matching relies on exact string comparison with the English category name (e.g., matching `"notice"`, `"contact"`). Since Korean search queries do not typically contain English terms, and the `category` field is heavily misclassified as `unknown` or `menu`, documents miss out on the +5.0 category score boost.

## Test coverage findings
- **No Direct Completeness Tests**: The existing test suite contains units for link extraction, indexing schemas, and query rewriter expansion. However, there are no tests that verify index completeness or coverage for actual public-sector sites (e.g., checking if the final index contains essential contact/location pages or department maps).
- **Mock-Only Boundaries**: Since live crawling tests are restricted and disabled (`RUN_LIVE_*_TESTS=1` is forbidden), validation of crawl completeness is isolated to static local mock/snapshot fixtures, which do not reflect real-world site structure changes or crawling boundary failures.

## Risks
- **Crawl Starvation Risk**: Official pages for contacts/parking may be omitted entirely if the page budget is consumed by board page loops or document downloads.
- **Retrieval Failure on Natural Phrasing**: Vague classification and lack of category-specific synonym mapping leads to low search ranking or source mismatch rejection by the `source_match_guard`, dropping the user into empty generic fallbacks.
- **Robots.txt Exclusion Risk**: If the site bans all user-agents (`Disallow: /`), setting `respect_robots: true` results in zero indexed pages, causing complete retrieval failure.

## Non-goals confirmed
- No live/network/API/Firecrawl calls
- No API keys/secrets
- No source grounding changes
- No volatile fact hardcoding
- No scenario/snapshot/cache generation

## Recommended next stage
- **Stage Title**: Stage 385: Expand site profile classification keywords and introduce targeted crawl rules
- **Recommended Actions**:
  1. Update `classify_url()` in `src/crawler/homepage_mapper.py` to include missing municipal keywords (`조직도`, `직원검색`, `부서안내`, `전화번호`, `담당자`, `공고`, `주차`, `오시는 길`, `청사`, `위치`).
  2. Add a `deny_patterns` rule structure in `SiteProfile` to exclude paginated board URLs (e.g., `&page=`, `pageNo=`, `currentPage=`) and print views, ensuring the page budget is reserved for unique menu paths.
  3. Expand synonyms in site profile configurations (`configs/sites/bukgu_gwangju.yml` and `configs/sites/gwangju_go_kr.yml`) to include local department names and specific municipal services.
