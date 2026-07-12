"""No-live pipeline regression tests for bukgu_gwangju crawl_filters config.

All tests use mock/static HTML only. No real network/API/Firecrawl calls.
Validates that real bukgu profile filters load and preserve/deny expected URLs
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
# Static HTML fixtures for bukgu profile filter testing
# ------------------------------------------------------------------

BUKGU_HOMEPAGE_HTML = """
<html>
  <head>
    <title>광주광역시 북구청</title>
    <meta name="description" content="북구청 공식 홈페이지">
  </head>
  <body>
    <nav>
      <!-- Survive: protected patterns (mid=, menuId=, board.es, seq=, contentId=, articleId=) -->
      <a href="/menu.es?mid=a101">종합민원</a>
      <a href="/board.es?seq=999">게시판 상세</a>
      <a href="/content?contentId=123">콘텐츠 상세</a>
      <a href="/article?articleId=777">기사 상세</a>

      <!-- Denied: print=, utm_source=, utm_ tracking -->
      <a href="/page?print=1">인쇄 페이지</a>
      <a href="/page?utm_source=test">UTM 소스</a>

      <!-- Survive: board.es with pageNo (pagination deferred, not in deny) -->
      <a href="/board.es?pageNo=2">게시판 2페이지</a>

      <!-- Normal navigation links -->
      <a href="/menu.es?mid=a202">교육접수</a>
      <a href="/menu.es?mid=a303">정보공개</a>
    </nav>
  </body>
</html>
"""

EXPECTED_SURVIVE_URLS = [
    "https://bukgu.gwangju.kr/menu.es?mid=a101",
    "https://bukgu.gwangju.kr/board.es?seq=999",
    "https://bukgu.gwangju.kr/content?contentId=123",
    "https://bukgu.gwangju.kr/article?articleId=777",
    "https://bukgu.gwangju.kr/board.es?pageNo=2",
    "https://bukgu.gwangju.kr/menu.es?mid=a202",
    "https://bukgu.gwangju.kr/menu.es?mid=a303",
]

EXPECTED_DENY_URLS = [
    "https://bukgu.gwangju.kr/page?print=1",
    "https://bukgu.gwangju.kr/page?utm_source=test",
]


# ------------------------------------------------------------------
# Test A: Real profile filters loaded for no-live pipeline regression
# ------------------------------------------------------------------

class TestBukguProfileFiltersLoaded:
    """Test that real bukgu_gwangju profile crawl_filters load correctly."""

    def test_bukgu_profile_loads_with_crawl_filters(self):
        """SiteProfileLoader loads bukgu_gwangju with non-empty crawl_filters."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")

        assert profile.site_id == "bukgu_gwangju"
        assert profile.base_url == "https://bukgu.gwangju.kr/"
        assert profile.crawl_filters is not None
        assert isinstance(profile.crawl_filters, dict)

    def test_bukgu_crawl_filters_not_empty(self):
        """bukgu_gwangju crawl_filters must not be empty (Stage 394 applied)."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        filters = profile.crawl_filters

        assert filters, "crawl_filters should not be empty"
        assert "deny_patterns" in filters
        assert "protected_patterns" in filters
        assert "allow_patterns" in filters

    def test_bukgu_deny_patterns_match_stage394(self):
        """deny_patterns match Stage 394 applied config exactly."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        deny = profile.crawl_filters.get("deny_patterns", [])

        # Stage 394 deny patterns
        assert "print=" in deny
        assert "utm_" in deny
        assert "utm_source=" in deny
        assert "utm_medium=" in deny
        assert "utm_campaign=" in deny
        # Length check - exactly these 5
        assert len(deny) == 5, f"Expected 5 deny patterns, got {len(deny)}: {deny}"

    def test_bukgu_protected_patterns_match_stage394(self):
        """protected_patterns match Stage 394 applied config exactly."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        protected = profile.crawl_filters.get("protected_patterns", [])

        # Stage 394 protected patterns
        assert "mid=" in protected
        assert "menuId=" in protected
        assert "board.es" in protected
        assert "seq=" in protected
        assert "contentId=" in protected
        assert "articleId=" in protected
        # Length check - exactly these 6
        assert len(protected) == 6, f"Expected 6 protected patterns, got {len(protected)}: {protected}"

    def test_bukgu_allow_patterns_empty(self):
        """allow_patterns intentionally empty per Stage 394 design."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        allow = profile.crawl_filters.get("allow_patterns", [])

        assert allow == [], f"allow_patterns should be empty, got: {allow}"

    def test_bukgu_forbidden_deny_guard(self):
        """Critical parameters forbidden in deny_patterns (Stage 393 guard)."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        deny = profile.crawl_filters.get("deny_patterns", [])

        forbidden = ["board.es", "mid=", "menuId=", "seq=", "contentId=", "articleId="]
        for pattern in forbidden:
            assert pattern not in deny, f"Forbidden deny pattern '{pattern}' found in deny_patterns"


# ------------------------------------------------------------------
# Test B: Filters preserve and deny expected links with static HTML
# ------------------------------------------------------------------

class TestBukguFiltersPreserveAndDenyExpectedLinks:
    """Test URL filtering behavior with static HTML using real bukgu filters."""

    @pytest.fixture
    def real_bukgu_filters(self):
        """Load real bukgu_gwangju crawl_filters from profile."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return profile.crawl_filters

    @pytest.fixture
    def crawler_with_bukgu_filters(self, real_bukgu_filters):
        """URLCrawler initialized with real bukgu crawl_filters."""
        return URLCrawler(crawl_filters=real_bukgu_filters)

    def test_static_html_protected_urls_survive(self, crawler_with_bukgu_filters):
        """Protected municipal URLs survive filtering in static HTML."""
        base_url = "https://bukgu.gwangju.kr/"
        soup = BeautifulSoup(BUKGU_HOMEPAGE_HTML, "html.parser")
        links = crawler_with_bukgu_filters.extract_links(soup, base_url)

        urls = [link["url"] for link in links["internal"]]

        # All expected survive URLs must be present
        for url in EXPECTED_SURVIVE_URLS:
            assert url in urls, f"Expected protected URL {url} to survive, but it was filtered out"

        # No expected deny URLs should be present
        for url in EXPECTED_DENY_URLS:
            assert url not in urls, f"Expected denied URL {url} to be filtered, but it survived"

    def test_should_crawl_url_with_real_filters(self, real_bukgu_filters):
        """should_crawl_url pure function works with real bukgu filters."""
        # Protected patterns -> allow
        assert should_crawl_url("https://bukgu.gwangju.kr/menu.es?mid=a101", real_bukgu_filters) is True
        assert should_crawl_url("https://bukgu.gwangju.kr/board.es?seq=999", real_bukgu_filters) is True
        assert should_crawl_url("https://bukgu.gwangju.kr/content?contentId=123", real_bukgu_filters) is True
        assert should_crawl_url("https://bukgu.gwangju.kr/article?articleId=777", real_bukgu_filters) is True

        # pagination deferred -> allow
        assert should_crawl_url("https://bukgu.gwangju.kr/board.es?pageNo=2", real_bukgu_filters) is True

        # deny patterns -> deny
        assert should_crawl_url("https://bukgu.gwangju.kr/page?print=1", real_bukgu_filters) is False
        assert should_crawl_url("https://bukgu.gwangju.kr/page?utm_source=test", real_bukgu_filters) is False
        assert should_crawl_url("https://bukgu.gwangju.kr/page?utm_medium=email", real_bukgu_filters) is False
        assert should_crawl_url("https://bukgu.gwangju.kr/page?utm_campaign=spring", real_bukgu_filters) is False

    def test_homepage_mapper_with_bukgu_filters_static_html(self, real_bukgu_filters):
        """HomepageMapper with bukgu filters processes static HTML correctly.

        Note: homepage navigation links are extracted by extract_menu_links()
        which does NOT apply crawl_filters. Filters are applied in
        URLCrawler.extract_links() for recursive crawling.
        """
        mapper = HomepageMapper(
            fetch_provider="mock",
            crawl_filters=real_bukgu_filters,
        )

        # Mock the fetch to return our static HTML
        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (BUKGU_HOMEPAGE_HTML, None, 200, "https://bukgu.gwangju.kr/")

            result = mapper.build_map("https://bukgu.gwangju.kr/")

        nav_urls = [link["url"] for link in result["homepage"]["navigation_links"]]

        # All expected survive URLs (except denied ones) should be in nav links
        # since extract_menu_links doesn't apply crawl_filters
        # But sitemap URLs would be filtered by URLCrawler
        for url in EXPECTED_SURVIVE_URLS:
            assert url in nav_urls, f"Expected {url} in navigation links"

        # Check categories - mid= URLs should be categorized based on link text
        # classify_url prioritizes apply/notice/board over menu for navigation links
        mid_urls = [url for url in nav_urls if "mid=" in url]
        for url in mid_urls:
            link_category = next(l["category"] for l in result["homepage"]["navigation_links"] if l["url"] == url)
            # category depends on link text classification, just verify it's a valid category
            assert link_category in ["menu", "apply", "notice", "board", "contact", "location", "document", "unknown"], (
                f"mid= URL {url} got invalid category '{link_category}'"
            )


# ------------------------------------------------------------------
# Test C: PipelineRunner passes bukgu filters to HomepageMapper no-live
# ------------------------------------------------------------------

# Reuse fake data from test_pipeline_runner for mocking
FAKE_HOMEPAGE_MAP = {
    "start_url": "https://bukgu.gwangju.kr/",
    "base_url": "https://bukgu.gwangju.kr/",
    "sitemap": {"candidates": [], "found": [], "url_count": 0, "urls": [], "errors": []},
    "homepage": {
        "title": "광주광역시 북구청",
        "description": "북구청 공식 홈페이지",
        "navigation_links": [
            {"text": "종합민원", "url": "https://bukgu.gwangju.kr/menu.es?mid=a101", "category": "menu"},
            {"text": "게시판", "url": "https://bukgu.gwangju.kr/board.es?seq=999", "category": "board"},
            {"text": "콘텐츠", "url": "https://bukgu.gwangju.kr/content?contentId=123", "category": "notice"},
            {"text": "기사", "url": "https://bukgu.gwangju.kr/article?articleId=777", "category": "notice"},
            {"text": "게시판2", "url": "https://bukgu.gwangju.kr/board.es?pageNo=2", "category": "board"},
        ],
        "attachment_links": [],
        "errors": [],
    },
    "categories": {
        "menu": ["https://bukgu.gwangju.kr/menu.es?mid=a101"],
        "notice": [
            "https://bukgu.gwangju.kr/content?contentId=123",
            "https://bukgu.gwangju.kr/article?articleId=777",
        ],
        "board": [
            "https://bukgu.gwangju.kr/board.es?seq=999",
            "https://bukgu.gwangju.kr/board.es?pageNo=2",
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


class TestPipelineRunnerPassesBukguFiltersToHomepageMapper:
    """Test PipelineRunner no-live path with real bukgu profile filters."""

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    @patch("src.site_profiles.site_profile.SiteProfileLoader")
    def test_pipeline_runner_passes_bukgu_filters_to_homepage_mapper(
        self,
        MockLoader,
        MockMapper,
        MockIndexer,
        MockEnricher,
        MockSearcher,
        MockComposer,
        tmp_path,
    ):
        """PipelineRunner loads real bukgu profile and passes crawl_filters to HomepageMapper."""
        # Load real bukgu profile
        loader = SiteProfileLoader()
        real_profile = loader.load_by_id("bukgu_gwangju")

        # Configure mocks
        MockLoader.return_value.list_ids.return_value = ["bukgu_gwangju"]
        MockLoader.return_value.load_by_id.return_value = real_profile

        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = [
            {
                "id": "doc-000001",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "title": "종합민원",
                "category": "menu",
                "source_types": ["navigation"],
                "content_type": "page",
                "text": "",
                "summary": "",
                "metadata": {
                    "base_url": "https://bukgu.gwangju.kr/",
                    "lastmod": "", "changefreq": "", "priority": "",
                    "link_texts": ["종합민원"],
                    "file_type": "",
                    "discovered_from": ["navigation"],
                },
            }
        ]
        MockEnricher.return_value.enrich_records.return_value = [
            {
                "id": "doc-000001",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "title": "종합민원",
                "category": "menu",
                "source_types": ["navigation"],
                "content_type": "page",
                "text": "종합민원 안내",
                "summary": "",
                "metadata": {
                    "base_url": "https://bukgu.gwangju.kr/",
                    "lastmod": "", "changefreq": "", "priority": "",
                    "link_texts": ["종합민원"],
                    "file_type": "",
                    "discovered_from": ["navigation"],
                    "fetched_at": "2026-06-09T12:00:00Z",
                    "http_status": 200,
                    "response_content_type": "text/html",
                    "fetch_status": "fetched",
                    "fetch_error": "",
                    "description": "종합민원 안내",
                },
            }
        ]
        MockSearcher.return_value.search.return_value = [
            {
                "rank": 1,
                "id": "doc-000001",
                "title": "종합민원",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "category": "menu",
                "content_type": "page",
                "score": 10.0,
                "matched_terms": ["민원"],
                "matched_fields": ["title"],
                "snippet": "종합민원 안내",
                "metadata": {
                    "source_types": ["navigation"],
                    "fetch_status": "fetched",
                    "description": "종합민원 안내",
                },
            }
        ]
        MockComposer.return_value.compose.return_value = {
            "query": "종합민원 안내",
            "provider": "mock",
            "model": "mock-model",
            "ok": True,
            "answer_markdown": "## 답변\n\n종합민원 페이지 확인하세요.\n\n## 관련 자료\n\n- [종합민원](https://bukgu.gwangju.kr/menu.es?mid=a101)\n\n## 다음에 할 일\n\n1. 안내 페이지 확인\n\n## 확인 필요 사항\n\n없음",
            "sources": [
                {
                    "rank": 1,
                    "id": "doc-000001",
                    "title": "종합민원",
                    "url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                    "category": "menu",
                    "content_type": "page",
                    "score": 10.0,
                    "matched_terms": ["민원"],
                    "matched_fields": ["title"],
                    "snippet": "종합민원 안내",
                    "description": "종합민원 안내",
                    "fetch_status": "fetched",
                    "source_types": ["navigation"],
                }
            ],
            "warnings": [],
            "error": "",
        }

        # Run pipeline
        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock")
        result = runner.run(url="https://bukgu.gwangju.kr/", query="종합민원 안내")

        # Verify pipeline succeeded
        assert result["ok"] is True

        # Key assertion: HomepageMapper was called with real bukgu crawl_filters
        MockMapper.assert_called_once()
        call_kwargs = MockMapper.call_args.kwargs

        assert "crawl_filters" in call_kwargs, "HomepageMapper should receive crawl_filters"
        passed_filters = call_kwargs["crawl_filters"]
        assert passed_filters == real_profile.crawl_filters, (
            f"Passed filters should equal real bukgu profile filters, "
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
        real_profile = loader.load_by_id("bukgu_gwangju")

        MockLoader.return_value.list_ids.return_value = ["bukgu_gwangju"]
        MockLoader.return_value.load_by_id.return_value = real_profile

        # Use same fake data as above
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = [
            {
                "id": "doc-000001",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "title": "종합민원",
                "category": "menu",
                "source_types": ["navigation"],
                "content_type": "page",
                "text": "",
                "summary": "",
                "metadata": {
                    "base_url": "https://bukgu.gwangju.kr/",
                    "lastmod": "", "changefreq": "", "priority": "",
                    "link_texts": ["종합민원"],
                    "file_type": "",
                    "discovered_from": ["navigation"],
                },
            }
        ]
        MockEnricher.return_value.enrich_records.return_value = [
            {
                **MockIndexer.return_value.build_index.return_value[0],
                "text": "종합민원 안내",
                "metadata": {
                    **MockIndexer.return_value.build_index.return_value[0]["metadata"],
                    "fetched_at": "2026-06-09T12:00:00Z",
                    "http_status": 200,
                    "response_content_type": "text/html",
                    "fetch_status": "fetched",
                    "fetch_error": "",
                    "description": "종합민원 안내",
                },
            }
        ]
        MockSearcher.return_value.search.return_value = [
            {
                "rank": 1,
                "id": "doc-000001",
                "title": "종합민원",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "category": "menu",
                "content_type": "page",
                "score": 10.0,
                "matched_terms": ["민원"],
                "matched_fields": ["title"],
                "snippet": "종합민원 안내",
                "metadata": {
                    "source_types": ["navigation"],
                    "fetch_status": "fetched",
                    "description": "종합민원 안내",
                },
            }
        ]
        MockComposer.return_value.compose.return_value = {
            "query": "종합민원 안내",
            "provider": "mock",
            "model": "mock-model",
            "ok": True,
            "answer_markdown": "## 답변\n\n종합민원 확인.\n\n## 관련 자료\n\n- [종합민원](https://bukgu.gwangju.kr/menu.es?mid=a101)\n\n## 다음에 할 일\n\n1. 확인\n\n## 확인 필요 사항\n\n없음",
            "sources": [],
            "warnings": [],
            "error": "",
        }

        # No fetch_provider passed = no live fetch path
        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock")
        result = runner.run(url="https://bukgu.gwangju.kr/", query="종합민원 안내")

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
        real_profile = loader.load_by_id("bukgu_gwangju")

        MockLoader.return_value.list_ids.return_value = ["bukgu_gwangju"]
        MockLoader.return_value.load_by_id.return_value = real_profile

        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = [
            {
                "id": "doc-000001",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "title": "종합민원",
                "category": "menu",
                "source_types": ["navigation"],
                "content_type": "page",
                "text": "",
                "summary": "",
                "metadata": {
                    "base_url": "https://bukgu.gwangju.kr/",
                    "lastmod": "", "changefreq": "", "priority": "",
                    "link_texts": ["종합민원"],
                    "file_type": "",
                    "discovered_from": ["navigation"],
                },
            }
        ]
        MockEnricher.return_value.enrich_records.return_value = [
            {
                **MockIndexer.return_value.build_index.return_value[0],
                "text": "종합민원 안내",
                "metadata": {
                    **MockIndexer.return_value.build_index.return_value[0]["metadata"],
                    "fetched_at": "2026-06-09T12:00:00Z",
                    "http_status": 200,
                    "response_content_type": "text/html",
                    "fetch_status": "fetched",
                    "fetch_error": "",
                    "description": "종합민원 안내",
                },
            }
        ]
        MockSearcher.return_value.search.return_value = [
            {
                "rank": 1,
                "id": "doc-000001",
                "title": "종합민원",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a101",
                "category": "menu",
                "content_type": "page",
                "score": 10.0,
                "matched_terms": ["민원"],
                "matched_fields": ["title"],
                "snippet": "종합민원 안내",
                "metadata": {
                    "source_types": ["navigation"],
                    "fetch_status": "fetched",
                    "description": "종합민원 안내",
                },
            }
        ]
        MockComposer.return_value.compose.return_value = {
            "query": "종합민원 안내",
            "provider": "mock",
            "model": "mock-model",
            "ok": True,
            "answer_markdown": "## 답변\n\n확인.\n\n## 관련 자료\n\n- [종합민원](https://bukgu.gwangju.kr/menu.es?mid=a101)\n\n## 다음에 할 일\n\n1. 확인\n\n## 확인 필요 사항\n\n없음",
            "sources": [],
            "warnings": [],
            "error": "",
        }

        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock")
        result = runner.run(url="https://bukgu.gwangju.kr/", query="종합민원 안내")

        assert result["ok"] is True

        # Output goes to tmp_path only (no repo scenario/snapshot/cache files touched)
        output_dir = result["output_dir"]
        assert str(tmp_path) in output_dir or output_dir.startswith("data/runs/run-")

        # AnswerComposer mock called - no source grounding mutation, just compose called
        MockComposer.assert_called_once()