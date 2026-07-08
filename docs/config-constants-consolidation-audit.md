# Config Constants Consolidation Audit

## Scope
- #953
- Parent #833
- Document extension constants completed by #950/#952

## Current State Summary
`DEFAULT_BOARD_PATTERNS` and `DEFAULT_CRAWL_RULES` reside in `src/site_profiles/site_profile.py`. They act as default values for site-specific profiles (`SiteProfile`). The code is defensive against accidental mutations (they are defensively copied when accessed or merged). There are several similar-looking hardcoded values across the codebase, but they serve different semantic roles (e.g., classification categories vs URL path substrings).

## Inventory

### DEFAULT_BOARD_PATTERNS
| Symbol / value | File | Line / function | Type | Used by | Semantics | Notes |
|---|---|---|---|---|---|---|
| `DEFAULT_BOARD_PATTERNS` | `src/site_profiles/site_profile.py` | 44-46 | `list[str]` | `SiteProfile.board_patterns` | Profile configuration default | Defensively copied via `list(...)` before returning. Used for detecting board/list type pages from URL paths. |

### DEFAULT_CRAWL_RULES
| Symbol / value | File | Line / function | Type | Used by | Semantics | Notes |
|---|---|---|---|---|---|---|
| `DEFAULT_CRAWL_RULES` | `src/site_profiles/site_profile.py` | 35-40 | `dict[str, Any]` | `SiteProfile.crawl_rules` | Profile configuration default | Defines `max_depth`, `max_pages`, `include_documents`, `respect_robots`. Defensively copied via `dict(...)` and merged with YAML overrides. |

### Other duplicate-looking board/crawl values
| Value | File | Context | Same semantics? | Notes |
|---|---|---|---|---|
| `"notice": 5, "board": 4` | `src/crawler/url_classifier.py` | `CATEGORY_PRIORITY` | No | Semantic category names for URL classification, not URL substring path patterns. |
| `"max_depth": 0`, `"max_pages": 1` | `src/demo/controlled_live_ux_runner.py` | `run_demo(...)` | No | Hardcoded demo limits for UX simulation, not generic crawl defaults. |
| `max_depth: int`, `max_pages: int` | `src/demo/controlled_live_smoke_contract.py` | Demo Request models | No | Test/demo contract schema properties, not runtime default values. |
| `"notice"`, `"board"` | `src/crawler/homepage_mapper.py` | Dictionary structure | No | Keys for structural output of the mapper. |
| `"menu", "apply", "notice", "board", "document"` | `src/demo/demo_helpers.py` | `priority_cats` list | No | Keys used to search for candidates by category priorities. |

## Behavior and Override Paths
- `SiteProfile.board_patterns`: Returns `list(self._data.get("board_patterns", DEFAULT_BOARD_PATTERNS))`. The caller gets a new list each time, protecting the default from modification. YAML overrides replace the entire list if present.
- `SiteProfile.crawl_rules`: Merges `DEFAULT_CRAWL_RULES` with `self._data.get("crawl_rules", {})`. Overrides only update the specified keys (e.g., `max_depth`), while defaults like `max_pages` or `respect_robots` are retained if not overridden.

## Risks of Consolidation
1. **Semantic Conflation:** The string "board" in `DEFAULT_BOARD_PATTERNS` is a URL path fragment (e.g., `/bbs/board.php`), while "board" in `url_classifier.py` is an abstract category label. Consolidating them into a single list or constant would confuse profile overriding and classifier logic.
2. **Fragile Overrides:** `SiteProfile` treats `DEFAULT_CRAWL_RULES` as a dictionary to merge. Moving or changing the type (e.g., to a frozen dataclass) could break the existing YAML override logic and tests.
3. **Test Breakage:** Tests like `test_default_crawl_rules` and `test_crawl_rules_override` specifically assert behavior based on these defaults. Uncareful extraction without locking the test behavior first might cause regressions.

## Test Coverage
- `DEFAULT_CRAWL_RULES` defaults and overrides are well-tested in `tests/test_site_profile.py` (`test_default_crawl_rules`, `test_crawl_rules_override`).
- `DEFAULT_BOARD_PATTERNS` default access is tested in `tests/test_site_profile.py` (`test_default_board_patterns`, `test_board_patterns_access`).
However, locking tests that explicitly verify the exact items in `DEFAULT_BOARD_PATTERNS` and `DEFAULT_CRAWL_RULES` (to prevent regressions during constant extraction) would be beneficial before a physical move.

## Recommendation
**Do not consolidate with other duplicate-looking strings.** They have different semantic scopes.
The defaults in `site_profile.py` should only be extracted as separate, dedicated semantic constants (e.g., `PROFILE_DEFAULT_BOARD_PATTERNS`, `PROFILE_DEFAULT_CRAWL_RULES`) in `src/config/constants.py` to keep the file pure. However, since the current structure is safe (defensively copied) and not causing immediate issues, this extraction should be deferred.

**Conclusion:** Consolidate 하지 말고, 별도 semantic constants로만 추출해야 하며, 테스트 락인 작업 후 후속 이슈에서 진행하는 것을 권장. #833은 여기서 닫고 후속 issue로 분리.

## Proposed Follow-up Issues
- **test(config): lock board pattern and crawl rule defaults**
- **refactor(config): extract named board pattern constants**
- **refactor(config): extract named crawl rule constants**
- **docs(config): close constants consolidation audit** (This audit completes #953 and parent #833)

## No-live / No-network Confirmation
- No network requests were made.
- No live Firecrawl API or Cloudflare preview was accessed.
- Static source code analysis only.
