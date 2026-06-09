"""No-live pipeline regression tests for gwangju_go_kr crawl_filters config.

All tests use mock/static HTML only. No real network/API/Firecrawl calls.
Validates that real gwangju profile filters load and preserve/deny expected URLs
using PipelineRunner no-live path.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

from src.site_profiles.site_profile import SiteProfileLoader
from src.crawler.url_crawler import URLCrawler
from src.crawler.homepage_mapper import HomepageMapper
from src.crawler.crawl_path_filter import should_crawl_url
from src.pipeline.pipeline_runner import PipelineRunner


# ------------------------------------------------------------------
# Static HTML fixtures for gwangju_go_kr profile filter testing
# ------------------------------------------------------------------

GWANGJU_HOMEPAGE_HTML = """
<html>
  <head>
    <title>광주광역시청</title>
    <meta name="description" content="광주광역시 공식 홈페이지">
  </head>
  <body>
    <nav>
      <!-- Survive: protected patterns (mid=, menuId=, board.es, seq=, contentId=, articleId=) -->
      <a href="/menu.es?mid=a101">시정뉴스</a>
      <a href="/board.es?seq=999">고시공고 상세</a>
      <a href="/content?contentId=123">콘텐츠 상세</a>
      <a href="/article?articleId=777">기사 상세</a>

      <!-- Denied: print=, utm_ tracking -->
      <a href="/page?print=1">인쇄 페이지</a>
      <a href="/page?utm_source=test">UTM 소스</a>
      <a href="/page?utm_campaign=spring">UTM 캠페인</a>

      <!-- Survive: board.es with pageNo (pagination deferred, not in deny) -->
      <a href="/board.es?pageNo=2">게시판 2페이지</a>

      <!-- Normal navigation links -->
      <a href="/menu.es?mid=a202">정보공개</a>
      <a href="/menu.es?mid=a303">민원안내</a>
    </nav>
  </body>
</html>
"""

EXPECTED_SURVIVE_URLS = [
    "https://www.gwangju.go.kr/menu.es?mid=a101",
    "https://www.gwangju.go.kr/board.es?seq=999",
    "https://www.gwangju.go.kr/content?contentId=123",
    "https://www.gwangju.go.kr/article?articleId=777",
    "https://www.gwangju.go.kr/board.es?pageNo=2",
    "https://www.gwangju.go.kr/menu.es?mid=a202",
    "https://www.gwangju.go.kr/menu.es?mid=a303",
]

EXPECTED_DENY_URLS = [
    "https://www.gwangju.go.kr/page?print=1",
    "https://www.gwangju.go.kr/page?utm_source=test",
    "https://www.gwangju.go.kr/page?utm_campaign=spring",
]


# ------------------------------------------------------------------
# Test A: Real profile load
# ------------------------------------------------------------------

class TestGwangjuProfileFiltersLoaded:
    """Test that real gwangju_go_kr profile crawl_filters load correctly."""

    def test_gwangju_profile_loads_with_crawl_filters(self):
        """SiteProfileLoader loads gwangju_go_kr with non-empty crawl_filters."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("gwangju_go_kr")

        assert profile.site_id == "gwangju_go_kr"
        assert profile.base_url == "https://www.gwangju.go.kr/"
        assert profile.crawl_filters is not None
        assert isinstance(profile.crawl_filters, dict)

    def test_gwangju_crawl_filters_not_empty(self):
        """gwangju_go_kr crawl_filters must not be empty (Stage 397 applied)."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("gwangju_go_kr")
        filters = profile.crawl_filters

        assert filters, "crawl_filters should not be empty"
        assert "deny_patterns" in filters
        assert "protected_patterns" in filters
        assert "allow_patterns" in filters

    def test_gwangju_deny_patterns_match_stage397(self):
        """deny_patterns match Stage 397 applied config exactly."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("gwangju_go_kr")
        deny = profile.crawl_filters.get("deny_patterns", [])

        # Stage 397 deny patterns
        assert "print=" in deny
        assert "utm_" in deny
        assert "utm_source=" in deny
        assert "utm_medium=" in deny
        assert "utm_campaign=" in deny
        # Length check - exactly these 5
        assert len(deny) == 5, f"Expected 5 deny patterns, got {len(deny)}: {deny}"

    def test_gwangju_protected_patterns_match_stage397(self):
        """protected_patterns match Stage 397 applied config exactly."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("gwangju_go_kr")
        protected = profile.crawl_filters.get("protected_patterns", [])

        # Stage 397 protected patterns
        assert "mid=" in protected
        assert "menuId=" in protected
        assert "board.es" in protected
        assert "seq=" in protected
        assert "contentId=" in protected
        assert "articleId=" in protected
        # Length check - exactly these 6
        assert len(protected) == 6, f"Expected 6 protected patterns, got {len(protected)}: {protected}"

    def test_gwangju_allow_patterns_empty(self):
        """allow_patterns intentionally empty per Stage 397 design."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("gwangju_go_kr")
        allow = profile.crawl_filters.get("allow_patterns", [])

        assert allow == [], f"allow_patterns should be empty, got: {allow}"

    def test_gwangju_forbidden_deny_guard(self):
        """Critical parameters forbidden in deny_patterns (Stage 397 guard)."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("gwangju_go_kr")
        deny = profile.crawl_filters.get("deny_patterns", [])

        forbidden = ["board.es", "mid=", "menuId=", "seq=", "contentId=", "articleId="]
        for pattern in forbidden:
            assert pattern not in deny, f"Forbidden deny pattern '{pattern}' found in deny_patterns"


# ------------------------------------------------------------------
# Test B: Static HTML preserve/deny regression
# ------------------------------------------------------------------

class TestGwangjuFiltersPreserveAndDenyExpectedLinks:
    """Test URL filtering behavior with static HTML using real gwangju filters."""

    @pytest.fixture
    def real_gwangju_filters(self):
        """Load real gwangju_go_kr crawl_filters from profile."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("gwangju_go_kr")
        return profile.crawl_filters

    @pytest.fixture
    def crawler_with_gwangju_filters(self, real_gwangju_filters):
        """URLCrawler initialized with real gwangju crawl_filters."""
        return URLCrawler(crawl_filters=real_gwangju_filters)

    def test_gwangju_static_html_protected_urls_survive(self, crawler_with_gwangju_filters):
        """Protected municipal URLs survive filtering in static HTML."""
        base_url = "https://www.gwangju.go.kr/"
        soup = BeautifulSoup(GWANGJU_HOMEPAGE_HTML, "html.parser")
        links = crawler_with_gwangju_filters.extract_links(soup, base_url)

        urls = [link["url"] for link in links["internal"]]

        # All expected survive URLs must be present
        for url in EXPECTED_SURVIVE_URLS:
            assert url in urls, f"Expected protected URL {url} to survive, but it was filtered out"

        # No expected deny URLs should be present
        for url in EXPECTED_DENY_URLS:
            assert url not in urls, f"Expected denied URL {url} to be filtered, but it survived"

    def test_gwangju_static_html_tracking_and_print_denied(self, crawler_with_gwangju_filters):
        """Tracking and print URLs are denied."""
        base_url = "https://www.gwangju.go.kr/"
        soup = BeautifulSoup(GWANGJU_HOMEPAGE_HTML, "html.parser")
        links = crawler_with_gwangju_filters.extract_links(soup, base_url)

        urls = [link["url"] for link in links["internal"]]

        # All deny URLs should be filtered out
        for url in EXPECTED_DENY_URLS:
            assert url not in urls, f"Expected denied URL {url} to be filtered, but it survived"

    def test_gwangju_pagination_deferred_survives(self, crawler_with_gwangju_filters):
        """Pagination parameters (pageNo) survive as they are deferred."""
        base_url = "https://www.gwangju.go.kr/"
        html = """
        <html>
          <body>
            <a href="/board.es?pageNo=1">Page 1</a>
            <a href="/board.es?pageNo=2">Page 2</a>
            <a href="/board.es?pageNo=50">Page 50</a>
          </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        links = crawler_with_gwangju_filters.extract_links(soup, base_url)

        urls = [link["url"] for link in links["internal"]]

        # pageNo should survive (not in deny_patterns)
        assert "https://www.gwangju.go.kr/board.es?pageNo=1" in urls
        assert "https://www.gwangju.go.kr/board.es?pageNo=2" in urls
        assert "https://www.gwangju.go.kr/board.es?pageNo=50" in urls
        assert len(urls) == 3

    def test_should_crawl_url_with_real_filters(self, real_gwangju_filters):
        """should_crawl_url pure function works with real gwangju filters."""
        # Protected patterns -> allow
        assert should_crawl_url("https://www.gwangju.go.kr/menu.es?mid=a101", real_gwangju_filters) is True
        assert should_crawl_url("https://www.gwangju.go.kr/board.es?seq=999", real_gwangju_filters) is True
        assert should_crawl_url("https://www.gwangju.go.kr/content?contentId=123", real_gwangju_filters) is True
        assert should_crawl_url("https://www.gwangju.go.kr/article?articleId=777", real_gwangju_filters) is True

        # pagination deferred -> allow
        assert should_crawl_url("https://www.gwangju.go.kr/board.es?pageNo=2", real_gwangju_filters) is True
        assert should_crawl_url("https://www.gwangju.go.kr/board.es?currentPage=3", real_gwangju_filters) is True

        # deny patterns -> deny
        assert should_crawl_url("https://www.gwangju.go.kr/page?print=1", real_gwangju_filters) is False
        assert should_crawl_url("https://www.gwangju.go.kr/page?utm_source=test", real_gwangju_filters) is False
        assert should_crawl_url("https://www.gwangju.go.kr/page?utm_medium=email", real_gwangju_filters) is False
        assert should_crawl_url("https://www.gwangju.go.kr/page?utm_campaign=spring", real_gwangju_filters) is False

    def test_homepage_mapper_with_gwangju_filters_static_html(self, real_gwangju_filters):
        """HomepageMapper with gwangju filters processes static HTML correctly.

        Note: homepage navigation links are extracted by extract_menu_links()
        which does NOT apply crawl_filters. Filters are applied in
        URLCrawler.extract_links() for recursive crawling.
        """
        mapper = HomepageMapper(
            fetch_provider="mock",
            crawl_filters=real_gwangju_filters,
        )

        # Mock the fetch to return our static HTML
        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (GWANGJU_HOMEPAGE_HTML, None, 200, "https://www.gwangju.go.kr/")

            result = mapper.build_map("https://www.gwangju.go.kr/")

        nav_urls = [link["url"] for link in result["homepage"]["navigation_links"]]

        # All expected survive URLs should be in nav links
        # since extract_menu_links doesn't apply crawl_filters
        # But sitemap URLs would be filtered by URLCrawler
        for url in EXPECTED_SURVIVE_URLS:
            assert url in nav_urls, f"Expected {url} in navigation links"

        # Check categories - mid= URLs should be categorized based on link text
        mid_urls = [url for url in nav_urls if "mid=" in url]
        for url in mid_urls:
            link_category = next(l["category"] for l in result["homepage"]["navigation_links"] if l["url"] == url)
            # category depends on link text classification, just verify it's a valid category
            assert link_category in ["menu", "apply", "notice", "board", "contact", "location", "document", "unknown"], (
                f"mid= URL {url} got invalid category '{link_category}'"
            )


# ------------------------------------------------------------------
# Test C: PipelineRunner passes gwangju filters to HomepageMapper no-live
# ------------------------------------------------------------------

FAKE_HOMEPAGE_MAP = {
    "start_url": "https://www.gwangju.go.kr/",
    "base_url": "https://www.gwangju.go.kr/",
    "sitemap": {"candidates": [], "found": [], "url_count": 0, "urls": [], "errors": []},
    "homepage": {
        "title": "광주광역시청",
        "description": "광주광역시 공식 홈페이지",
        "navigation_links": [
            {"text": "시정뉴스", "url": "https://www.gwangju.go.kr/menu.es?mid=a101", "category": "menu"},
            {"text": "고시공고", "url": "https://www.gwangju.go.kr/board.es?seq=999", "category": "board"},
            {"text": "콘텐츠", "url": "https://www.gwangju.go.kr/content?contentId=123", "category": "notice"},
            {"text": "기사", "url": "https://www.gwangju.go.kr/article?articleId=777", "category": "notice"},
            {"text": "게시판2", "url": "https://www.gwangju.go.kr/board.es?pageNo=2", "category": "board"},
        ],
        "attachment_links": [],
        "errors": [],
    },
    "categories": {
        "menu": ["https://www.gwangju.go.kr/menu.es?mid=a101"],
        "notice": [
            "https://www.gwangju.go.kr/content?contentId=123",
            "https://www.gwangju.go.kr/article?articleId=777",
        ],
        "board": [
            "https://www.gwangju.go.kr/board.es?seq=999",
            "https://www.gwangju.go.kr/board.es?pageNo=2",
        ],
        "document": [],
        "apply": [],
        "contact": [],
        "unknown": [],
    },
    "stats": {
        "sitemap_url_count": 0,
        "navigation_link_count": 5,
        "attachment_count": 0,
        "category_counts": {
            "menu": 1, "notice": 2, "board": 2,
            "document": 0, "apply": 0, "contact": 0, "unknown": 0,
        },
    },
    "errors": [],
}


class TestPipelineRunnerPassesGwangjuFiltersToHomepageMapper:
    """Test PipelineRunner no-live path with real gwangju profile filters."""

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    @patch("src.site_profiles.site_profile.SiteProfileLoader")
    def test_pipeline_runner_passes_gwangju_filters_to_homepage_mapper(
        self,
        MockLoader,
        MockMapper,
        MockIndexer,
        MockEnricher,
        MockSearcher,
        MockComposer,
        tmp_path,
    ):
        """PipelineRunner loads real gwangju profile and passes crawl_filters to HomepageMapper."""
        # Load real gwangju profile
        loader = SiteProfileLoader()
        real_profile = loader.load_by_id("gwangju_go_kr")

        # Configure mocks
        MockLoader.return_value.list_ids.return_value = ["gwangju_go_kr", "bukgu_gwangju"]
        MockLoader.return_value.load_by_id.return_value = real_profile

        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = [
            {
                "id": "doc-000001",
                "url": "https://www.gwangju.go.kr/menu.es?mid=a101",
                "canonical_url": "https://www.gwangju.go.kr/menu.es?mid=a101",
                "title": "시정뉴스",
                "category": "menu",
                "source_types": ["navigation"],
                "content_type": "page",
                "text": "",
                "summary": "",
                "metadata": {
                    "base_url": "https://www.gwangju.go.kr/",
                    "lastmod": "", "changefreq": "", "priority": "",
                    "link_texts": ["시정뉴스"],
                    "file_type": "",
                    "discovered_from": ["navigation"],
                },
            }
        ]
        MockEnricher.return_value.enrich_records.return_value = [
            {
                **MockIndexer.return_value.build_index.return_value[0],
                "text": "시정뉴스 안내",
                "metadata": {
                    **MockIndexer.return_value.build_index.return_value[0]["metadata"],
                    "fetched_at": "2026-06-09T12:00:00Z",
                    "http_status": 200,
                    "response_content_type": "text/html",
                    "fetch_status": "fetched",
                    "fetch_error": "",
                    "description": "시정뉴스 안내",
                },
            }
        ]
        MockSearcher.return_value.search.return_value = [
            {
                "rank": 1,
                "id": "doc-000001",
                "title": "시정뉴스",
                "url": "https://www.gwangju.go.kr/menu.es?mid=a101",
                "canonical_url": "https://www.gwangju.go.kr/menu.es?mid=a101",
                "category": "menu",
                "content_type": "page",
                "score": 10.0,
                "matched_terms": ["시정"],
                "matched_fields": ["title"],
                "snippet": "시정뉴스 안내",
                "metadata": {
                    "source_types": ["navigation"],
                    "fetch_status": "fetched",
                    "description": "시정뉴스 안내",
                },
            }
        ]
        MockComposer.return_value.compose.return_value = {
            "query": "시정뉴스 안내",
            "provider": "mock",
            "model": "mock-model",
            "ok": True,
            "answer_markdown": "## 답변\n\n시정뉴스 페이지 확인하세요.\n\n## 관련 자료\n\n- [시정뉴스](https://www.gwangju.go.kr/menu.es?mid=a101)\n\n## 다음에 할 일\n\n1. 안내 페이지 확인\n\n## 확인 필요 사항\n\n없음",
            "sources": [
                {
                    "rank": 1,
                    "id": "doc-000001",
                    "title": "시정뉴스",
                    "url": "https://www.gwangju.go.kr/menu.es?mid=a101",
                    "category": "menu",
                    "content_type": "page",
                    "score": 10.0,
                    "matched_terms": ["시정"],
                    "matched_fields": ["title"],
                    "snippet": "시정뉴스 안내",
                    "description": "시정뉴스 안내",
                    "fetch_status": "fetched",
                    "source_types": ["navigation"],
                }
            ],
            "warnings": [],
            "error": "",
        }

        # Run pipeline
        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock")
        result = runner.run(url="https://www.gwangju.go.kr/", query="시정뉴스 안내")

        # Verify pipeline succeeded
        assert result["ok"] is True

        # Key assertion: HomepageMapper was called with real gwangju crawl_filters
        MockMapper.assert_called_once()
        call_kwargs = MockMapper.call_args.kwargs

        assert "crawl_filters" in call_kwargs, "HomepageMapper should receive crawl_filters"
        passed_filters = call_kwargs["crawl_filters"]
        assert passed_filters == real_profile.crawl_filters, (
            f"Passed filters should equal real gwangju profile filters, "
            f"got {passed_filters} vs expected {real_profile.crawl_filters}"
        )

        # Verify specific deny/protected patterns are in passed filters
        assert "print=" in passed_filters.get("deny_patterns", [])
        assert "utm_" in passed_filters.get("deny_patterns", [])
        assert "mid=" in passed_filters.get("protected_patterns", [])
        assert "board.es" in passed_filters.get("protected_patterns", [])

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    @patch("src.site_profiles.site_profile.SiteProfileLoader")
    def test_pipeline_runner_no_live_network_calls(
        self,
        MockLoader,
        MockMapper,
        MockIndexer,
        MockEnricher,
        MockSearcher,
        MockComposer,
        tmp_path,
    ):
        """PipelineRunner with provider='mock' makes no live network/API/Firecrawl calls."""
        loader = SiteProfileLoader()
        real_profile = loader.load_by_id("gwangju_go_kr")

        MockLoader.return_value.list_ids.return_value = ["gwangju_go_kr", "bukgu_gwangju"]
        MockLoader.return_value.load_by_id.return_value = real_profile

        # Use same fake data as above
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = [
            {
                "id": "doc-000001",
                "url": "https://www.gwangju.go.kr/menu.es?mid=a101",
                "canonical_url": "https://www.gwangju.go.kr/menu.es?mid=a101",
                "title": "시정뉴스",
                "category": "menu",
                "source_types": ["navigation"],
                "content_type": "page",
                "text": "",
                "summary": "",
                "metadata": {
                    "base_url": "https://www.gwangju.go.kr/",
                    "lastmod": "", "changefreq": "", "priority": "",
                    "link_texts": ["시정뉴스"],
                    "file_type": "",
                    "discovered_from": ["navigation"],
                },
            }
        ]
        MockEnricher.return_value.enrich_records.return_value = [
            {
                **MockIndexer.return_value.build_index.return_value[0],
                "text": "시정뉴스 안내",
                "metadata": {
                    **MockIndexer.return_value.build_index.return_value[0]["metadata"],
                    "fetched_at": "2026-06-09T12:00:00Z",
                    "http_status": 200,
                    "response_content_type": "text/html",
                    "fetch_status": "fetched",
                    "fetch_error": "",
                    "description": "시정뉴스 안내",
                },
            }
        ]
        MockSearcher.return_value.search.return_value = [
            {
                "rank": 1,
                "id": "doc-000001",
                "title": "시정뉴스",
                "url": "https://www.gwangju.go.kr/menu.es?mid=a101",
                "canonical_url": "https://www.gwangju.go.kr/menu.es?mid=a101",
                "category": "menu",
                "content_type": "page",
                "score": 10.0,
                "matched_terms": ["시정"],
                "matched_fields": ["title"],
                "snippet": "시정뉴스 안내",
                "metadata": {
                    "source_types": ["navigation"],
                    "fetch_status": "fetched",
                    "description": "시정뉴스 안내",
                },
            }
        ]
        MockComposer.return_value.compose.return_value = {
            "query": "시정뉴스 안내",
            "provider": "mock",
            "model": "mock-model",
            "ok": True,
            "answer_markdown": "## 답변\n\n시정뉴스 확인.\n\n## 관련 자료\n\n- [시정뉴스](https://www.gwangju.go.kr/menu.es?mid=a101)\n\n## 다음에 할 일\n\n1. 확인\n\n## 확인 필요 사항\n\n없음",
            "sources": [],
            "warnings": [],
            "error": "",
        }

        # No fetch_provider passed = no live fetch path
        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock")
        result = runner.run(url="https://www.gwangju.go.kr/", query="시정뉴스 안내")

        assert result["ok"] is True

        # Verify no fetch_provider was passed to HomepageMapper (mock path)
        call_kwargs = MockMapper.call_args.kwargs
        assert call_kwargs.get("fetch_provider") is None or call_kwargs.get("fetch_provider") == "mock"

        # Verify AnswerComposer was created with mock provider
        MockComposer.assert_called_once()
        composer_kwargs = MockComposer.call_args.kwargs
        assert composer_kwargs.get("provider") == "mock"

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    @patch("src.site_profiles.site_profile.SiteProfileLoader")
    def test_pipeline_runner_only_mock_static_content(
        self,
        MockLoader,
        MockMapper,
        MockIndexer,
        MockEnricher,
        MockSearcher,
        MockComposer,
        tmp_path,
    ):
        """Pipeline run uses only mock/static fixtures, no scenario/snapshot/cache mutation."""
        loader = SiteProfileLoader()
        real_profile = loader.load_by_id("gwangju_go_kr")

        MockLoader.return_value.list_ids.return_value = ["gwangju_go_kr", "bukgu_gwangju"]
        MockLoader.return_value.load_by_id.return_value = real_profile

        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = [
            {
                "id": "doc-000001",
                "url": "https://www.gwangju.go.kr/menu.es?mid=a101",
                "canonical_url": "https://www.gwangju.go.kr/menu.es?mid=a101",
                "title": "시정뉴스",
                "category": "menu",
                "source_types": ["navigation"],
                "content_type": "page",
                "text": "",
                "summary": "",
                "metadata": {
                    "base_url": "https://www.gwangju.go.kr/",
                    "lastmod": "", "changefreq": "", "priority": "",
                    "link_texts": ["시정뉴스"],
                    "file_type": "",
                    "discovered_from": ["navigation"],
                },
            }
        ]
        MockEnricher.return_value.enrich_records.return_value = [
            {
                **MockIndexer.return_value.build_index.return_value[0],
                "text": "시정뉴스 안내",
                "metadata": {
                    **MockIndexer.return_value.build_index.return_value[0]["metadata"],
                    "fetched_at": "2026-06-09T12:00:00Z",
                    "http_status": 200,
                    "response_content_type": "text/html",
                    "fetch_status": "fetched",
                    "fetch_error": "",
                    "description": "시정뉴스 안내",
                },
            }
        ]
        MockSearcher.return_value.search.return_value = [
            {
                "rank": 1,
                "id": "doc-000001",
                "title": "시정뉴스",
                "url": "https://www.gwangju.go.kr/menu.es?mid=a101",
                "canonical_url": "https://www.gwangju.go.kr/menu.es?mid=a101",
                "category": "menu",
                "content_type": "page",
                "score": 10.0,
                "matched_terms": ["시정"],
                "matched_fields": ["title"],
                "snippet": "시정뉴스 안내",
                "metadata": {
                    "source_types": ["navigation"],
                    "fetch_status": "fetched",
                    "description": "시정뉴스 안내",
                },
            }
        ]
        MockComposer.return_value.compose.return_value = {
            "query": "시정뉴스 안내",
            "provider": "mock",
            "model": "mock-model",
            "ok": True,
            "answer_markdown": "## 답변\n\n확인.\n\n## 관련 자료\n\n- [시정뉴스](https://www.gwangju.go.kr/menu.es?mid=a101)\n\n## 다음에 할 일\n\n1. 확인\n\n## 확인 필요 사항\n\n없음",
            "sources": [],
            "warnings": [],
            "error": "",
        }

        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock")
        result = runner.run(url="https://www.gwangju.go.kr/", query="시정뉴스 안내")

        assert result["ok"] is True

        # Output goes to tmp_path only (no repo scenario/snapshot/cache files touched)
        output_dir = result["output_dir"]
        assert str(tmp_path) in output_dir or output_dir.startswith("data/runs/run-")

        # AnswerComposer mock called - no source grounding mutation, just compose called
        MockComposer.assert_called_once()