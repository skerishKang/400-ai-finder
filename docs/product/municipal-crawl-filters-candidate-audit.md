# Audit: Municipal Crawl Filters Config Candidates

## Stage
Stage 392

## 1. Goal & Context
Stage 391 established the technical path mapping `SiteProfile.crawl_filters` directly into `URLCrawler` via `HomepageMapper` during pipeline runs. In Stage 392, we establish an **audit-only safety boundary** to design and analyze the candidate crawl filter rules before making any changes to real site profile YAML configuration files.

Because introducing `deny_patterns` alters link extraction and traversal at runtime, any error or overly aggressive rule can lead to **crawl loss**—dropping critical municipal service pages, contacts, or notice details. Therefore, this audit serves as a conservative design check.

---

## 2. Proposed Candidate Rule Set
We propose a highly conservative candidate rule set to serve as the initial template:

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
```

### Allow Patterns Design Decision
- **Decision**: `allow_patterns` is left **empty** (`[]`) by default for all candidates.
- **Rationale**: Allow patterns override deny rules under the established precedence policy. If allow patterns are added prematurely without site-specific reasons, they might accidentally bypass our deny rules, weakening the effectiveness of the crawl budget protection. Allow patterns will only be introduced from Stage 393+ onwards under controlled, site-specific overrides.

---

## 3. Protected Municipal URL Catalogue
To prevent crawl loss on Korean public-sector J2EE/EGOV platforms, the following parameters and keywords represent structural identifiers and **must never be blocked**. They are protected explicitly:

- **Menu & Navigation**:
  - `menu.es?mid=`
  - `mid=`
  - `menuId=`
  - `menu=`
- **Notices & Detail Pages**:
  - `board.es`
  - `seq=`
  - `contentId=`
  - `articleId=`
- **Sub-pages & Departments**:
  - `deptId=`
  - `staffSearch`
- **Location, Map & Parking**:
  - `office-guide`, `map`, `parking`, `주차`, `위치`
- **Civil Forms & Downloads**:
  - `civil`, `download`, `form`

---

## 4. Deny Candidate Risk Analysis
We analyze the risks of candidate deny rules to define strict safety boundaries:

| Deny Candidate | Potential Risk | Safety Recommendation |
| :--- | :--- | :--- |
| `print=` | **Low Risk**. Print layouts duplicate the main content. However, rare legacy sites might use a print page URL structure as the primary indexable link. | Allow print layouts only if no primary HTML layout URL exists. |
| `utm_*` | **Zero Risk**. Marketing and tracking parameters (e.g. `utm_source=`) are safe to block as they contain identical content to regular URLs. | Safe to deny globally. |
| `pageNo=` | **High Risk**. Banning deep pagination protects the crawl budget, but banning `pageNo=` completely would block page 1/seed pages, preventing the crawler from discovering notices. | **Excluded from candidate rules**. Keep pagination parameters out of global deny rules until safe thresholds or specific fixture guards are verified. |
| `board.es` | **Critical Risk**. Banning notice board engines completely prevents indexing announcements. | **Strictly Forbidden to Deny**. Must remain protected. |
| `mid=`, `menuId=` | **Critical Risk**. Blocks overall site menu traversal. | **Strictly Forbidden to Deny**. Must remain protected. |
| `seq=`, `contentId=` | **Critical Risk**. Blocks notice detail pages. | **Strictly Forbidden to Deny**. Must remain protected. |

---

## 5. Pre-Stage 393/394 Verification Test Plan
Before any real YAML configuration files are modified (planned for Stage 394), the following verification contract tests must pass:

1. **Synthetic Config Fixture Test**:
   - Verify that synthetic profiles load, merge, and clean crawl rules without mutating the global environment.
2. **Profile Loader Test**:
   - Ensure the loader safely handles profiles with empty, missing, or malformed `crawl_filters` keys.
3. **Homepage Mapper Test**:
   - Verify that `HomepageMapper` forwards the configuration block to `URLCrawler` correctly.
4. **Pipeline Runner Test**:
   - Verify the pipeline runner resolves matched profiles and applies candidate filters.
5. **Mock Static HTML Crawl Preservation Test**:
   - Assert that `/menu.es?mid=a101` and `/normal` survive, while `/page?print=1` is correctly filtered using synthetic profiles.
6. **Flat-Link Provider Fallback Test**:
   - Verify that non-HTML provider fallback flat link lists filter internal links without mutating external or attachment list counts.
7. **No Source Grounding Change Test**:
   - Verify that applying path filters does not alter the source grounding or query rewrites during pipeline execution.
8. **No Scenario/Snapshot/Cache Generation Test**:
   - Assert that no files are modified in `scenario/`, `snapshot/`, or `cache/` during crawl filter validation.

---

## 6. Recommended Next Steps
- **Stage 393**: Add config fixture contract tests only. No real YAML configuration modifications are allowed.
- **Stage 394**: Apply the candidate configurations to real municipal YAML files only after all Stage 393 contract tests pass successfully.
- **Stage 395+**: Execute controlled live smoke tests with the updated configs, subject to explicit user approval.

---

## Stage 393 Implementation Status (Completed)
- **Status**: Implemented the full contract validation suite in `tests/test_municipal_crawl_filters_config_contract.py`.
- **Validation**:
  1. Synthetic Candidate Config Fixture Test: Verified config parser sanitizes candidate filters accurately.
  2. Protected Municipal URL Preservation Test: Checked that `/menu.es?mid=`, `/some/path?menuId=`, `/board.es?seq=`, `/content?contentId=`, `/article?articleId=` links are preserved.
  3. Deny Duplicate/Tracking Test: Checked print and UTM links are filtered out.
  4. Pagination Deferred Test: Checked `pageNo` and `currentPage` continue to be allowed.
  5. Forbidden Deny Rule Guard Test: Checked critical parameters are never present in the deny lists.
  6. Pipeline Synthetic Profile Fixture Test: Verified mapping propagation in `PipelineRunner`.
  7. No Real Config Mutation: Statically ensured no config YAML files are touched.
  8. No Live/Network/API: All tests executed locally with BeautifulSoup mocks.
- **Next Step**: Stage 394.
