# Crawl Budget Path Filtering Policy

## Stage
Stage 386

## Goal
Design a safe and robust crawl budget protection and URL path filtering policy for public-sector websites. This design ensures that recursive crawling does not exhaust the crawler's page budget on duplicate pages, pagination loops, or print views, while protecting critical query parameters that identify core municipal services.

---

## Background
- **Stage 384 Audit Summary**: The audit of the crawling pipeline revealed a critical Crawl Budget Starvation risk. Because the crawler uses recursive depth-3 link traversal, it is highly vulnerable to wasting its limited page budget (`max_pages: 200/300`) on paginated boards (e.g., page 1 to 50 of announcements), print views, and duplicate query parameters.
- **Stage 385 Context**: Stage 385 expanded the menu/URL keyword classification categories (`classify_url()`) without changing the crawling traversal logic.
- **Stage 386 Context**: This stage establishes the filtering policy, identifying safe and dangerous parameters before any code implementation. No code behavior changes or crawler traversal edits are made in this stage.

---

## Non-Goals
- No runtime crawler behavior changes
- No `allow_patterns` / `deny_patterns` implementation
- No `SiteProfile` schema changes
- No config changes
- No live/network/API/Firecrawl calls
- No source grounding changes
- No scenario/snapshot/cache generation
- No volatile fact hardcoding

---

## Safe Deny Candidates
The following URL components and query parameters are safe to block or strip because they contain duplicate page content or search index noise:

1. **Print Views**:
   - Parameters: `print=`, `view=print`, `printPage`, `/print/`
   - Rationale: Print layouts duplicate the main HTML content, wasting crawl budget and creating search index duplicates.
2. **Tracking and Duplicate Parameters**:
   - Parameters: `utm_source=`, `utm_medium=`, `fbclid=`, `gclid=`
   - Rationale: Tracking parameters are used for marketing analytics and do not represent distinct page content.
3. **Repeated Board Pagination**:
   - Parameters: `page=`, `pageNo=`, `currentPage=`, `pageIndex=`
   - Rationale: Recursive crawling of deep page listings (e.g., page 5, 6, 7...) of notice boards wastes page budget.
   - **Crucial Rule**: Pagination should only be denied if the page index is greater than a low threshold (e.g. page > 2) or inside a board list context to ensure the first page is crawled for discovery.
4. **Sort and Search Noise**:
   - Parameters: `sort=`, `order=`, `searchKeyword=`
   - Rationale: Sorting parameters present the same documents in different orders. Search keywords inside local search features can lead to infinite URL generation.

---

## Dangerous Deny Candidates
The following parameters must **NEVER** be blocked by default. In Korean J2EE/EGOV public-sector sites, these parameters represent the unique identifiers of static pages, departments, and services:

- **Menu Identifiers**: `mid=`, `menuId=`, `menu=`, `menu.es`
- **Article and Content Identifiers**: `articleId=`, `seq=`, `contentId=`, `board.es`
- **Department/Category Identifiers**: `deptId=`, `category=`
- **Rationale**: If a global pattern bans `mid` or `seq`, the crawler will fail to discover almost all of Gwangju Bukgu's or Gwangju City Hall's core pages, causing complete retrieval failure.

---

## Precedence Policy
When determining whether a URL should be crawled, the filtering logic should follow a strict precedence hierarchy:

1. **Default Action**: If the `SiteProfile` has no crawl filter rules defined, all internal URLs are allowed.
2. **Allow over Deny**: If a URL matches both an `allow_patterns` rule and a `deny_patterns` rule, the allow rule takes precedence (i.e. it is allowed).
3. **Explicit Deny**: Deny rules must be explicitly defined (e.g., no wildcard broad blocking of query parameters).
4. **Local overrides Global**: Site-specific profile rules override global defaults.
5. **Escape Hatch (Protected Patterns)**: Even if a deny filter matches (such as a generic `board` keyword deny), if the URL contains a protected parameter like `mid=`, the URL must be allowed to protect core municipal menus.
6. **Pure Function Helper**: The decision logic must be implemented as a pure function first (without dependencies on disk, network, or crawler state).

---

## Proposed Schema (Not Implemented in Stage 386)
> **Note**: Stage 386 does not implement this schema or alter `SiteProfile`.

```yaml
crawl_filters:
  allow_patterns:
    - "menu.es?mid="
  deny_patterns:
    - "print="
    - "pageNo="
  protected_patterns:
    - "mid="
    - "menuId="
```

---

## Test Matrix for Stage 387

The following test matrix will govern the verification of the filter decision helper in Stage 387:

| Case | URL example | Expected decision | Reason |
|---|---|---|---|
| menu mid page | `https://bukgu.gwangju.kr/menu.es?mid=a10103000000` | **allow** | Core municipal menu |
| staff search | `https://bukgu.gwangju.kr/staffSearch?dept=123` | **allow** | Contact/org page |
| board page 1 | `https://bukgu.gwangju.kr/board.es?mid=a1010&pageNo=1` | **allow** | Seed/discovery page |
| board page 37 | `https://bukgu.gwangju.kr/board.es?mid=a1010&pageNo=37` | **deny** | Pagination budget protection |
| print view | `https://bukgu.gwangju.kr/board.es?mid=a1010&print=1` | **deny** | Duplicate content prevention |
| tracking param | `https://bukgu.gwangju.kr/menu.es?mid=a1010&utm_source=facebook` | **deny** or **strip** | Duplicate URL prevention |

---

## Recommended Next Stage: Stage 387
- **Title**: `[TECH] Add crawl path filter decision helper without wiring crawler traversal`
- **Scope**: Implement the pure helper function and focused tests based on the test matrix above.
- **Rationale**: Implementing the helper logic and verifying it in isolation avoids side effects on crawl runs. Wiring the crawler traversal can be safely deferred to Stage 388.
