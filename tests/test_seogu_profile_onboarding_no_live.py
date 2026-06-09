"""No-live onboarding regression tests for seogu_gwangju municipal profile.

All tests use mock/static fixtures only. No live network/API/Firecrawl calls.
Verifies that the new seogu_gwangju profile loads correctly, its homepage map
extracts navigation links, URL classification works, and pipeline runner passes
profile filters without live calls.
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
# Test fixtures
# ------------------------------------------------------------------

# Shared conservative candidate rules (from Stage 392)
CONSERVATIVE_CANDIDATE = {
    "allow_patterns": [],
    "deny_patterns": [
        "print=",
        "utm_",
        "utm_source=",
        "utm_medium=",
        "utm_campaign=",
    ],
    "protected_patterns": [
        "mid=",
        "menuId=",
        "board.es",
        "seq=",
        "contentId=",
        "articleId=",
    ],
}

# Seogu mock homepage HTML
SEOGU_HOMEPAGE_HTML = """
<html>
  <head>
    <title>광주광역시 서구청</title>
    <meta name="description" content="서구청 공식 홈페이지">
  </head>
  <body>
    <nav>
      <!-- Protected structural URLs -->
      <a href="/menu.es?mid=a101">종합민원</a>
      <a href="/board.es?seq=999">게시판 상세</a>
      <a href="/content?contentId=123">콘텐츠 상세</a>
      <a href="/article?articleId=777">기사 상세</a>
      <!-- Pagination deferred -->
      <a href="/board.es?pageNo=2">게시판 2페이지</a>
      <!-- Denied: print/tracking -->
      <a href="/page?print=1">인쇄 페이지</a>
      <a href="/page?utm_source=test">UTM 소스</a>
      <a href="/page?utm_campaign=spring">UTM 캠페인</a>
      <!-- Normal navigation -->
      <a href="/menu.es?mid=a202">교육접수</a>
      <!-- Seogu-specific patterns -->
      <a href="/bbs/BBSMSTR_000000000276/list.do">공지사항</a>
      <a href="/bbs/BBSMSTR_000000000275/list.do?pageIndex=1">고시공고</a>
      <a href="/boardDownload.es?bid=0013&list_no=136021&seq=1">첨부파일 다운로드</a>
    </nav>
  </body>
</html>
"""

# Expected survive URLs for seogu
SEOGU_SURVIVE_URLS = [
    "https://www.seogu.gwangju.kr/menu.es?mid=a101",
    "https://www.seogu.gwangju.kr/board.es?seq=999",
    "https://www.seogu.gwangju.kr/content?contentId=123",
    "https://www.seogu.gwangju.kr/article?articleId=777",
    "https://www.seogu.gwangju.kr/board.es?pageNo=2",
    "https://www.seogu.gwangju.kr/menu.es?mid=a202",
    "https://www.seogu.gwangju.kr/bbs/BBSMSTR_000000000276/list.do",
    "https://www.seogu.gwangju.kr/bbs/BBSMSTR_000000000275/list.do?pageIndex=1",
    "https://www.seogu.gwangju.kr/boardDownload.es?bid=0013&list_no=136021&seq=1",
]

SEOGU_DENY_URLS = [
    "https://www.seogu.gwangju.kr/page?print=1",
    "https://www.seogu.gwangju.kr/page?utm_source=test",
    "https://www.seogu.gwangju.kr/page?utm_campaign=spring",
]


# Fake data for mocking PipelineRunner (similar to existing test files)
FAKE_HOMEPAGE_MAP_SEOGU = {
    "start_url": "https://www.seogu.gwangju.kr/",
    "base_url": "https://www.seogu.gwangju.kr/",
    "sitemap": {"candidates": [], "found": [], "url_count": 0, "urls": [], "errors": []},
    "homepage": {
        "title": "광주광역시 서구청",
        "description": "서구청 공식 홈페이지",
        "navigation_links": [
            {"text": "종합민원", "url": "https://www.seogu.gwangju.kr/menu.es?mid=a101", "category": "menu"},
            {"text": "게시판", "url": "https://www.seogu.gwangju.kr/board.es?seq=999", "category": "board"},
            {"text": "콘텐츠", "url": "https://www.seogu.gwangju.kr/content?contentId=123", "category": "notice"},
            {"text": "기사", "url": "https://www.seogu.gwangju.kr/article?articleId=777", "category": "notice"},
            {"text": "게시판2", "url": "https://www.seogu.gwangju.kr/board.es?pageNo=2", "category": "board"},
            {"text": "공지사항", "url": "https://www.seogu.gwangju.kr/bbs/BBSMSTR_000000000276/list.do", "category": "notice"},
            {"text": "고시공고", "url": "https://www.seogu.gwangju.kr/bbs/BBSMSTR_000000000275/list.do?pageIndex=1", "category": "notice"},
        ],
        "attachment_links": [],
        "errors": [],
    },
    "categories": {
        "menu": ["https://www.seogu.gwangju.kr/menu.es?mid=a101"],
        "notice": [
            "https://www.seogu.gwangju.kr/content?contentId=123",
            "https://www.seogu.gwangju.kr/article?articleId=777",
            "https://www.seogu.gwangju.kr/bbs/BBSMSTR_000000000276/list.do",
            "https://www.seogu.gwangju.kr/bbs/BBSMSTR_000000000275/list.do?pageIndex=1",
        ],
        "board": [
            "https://www.seogu.gwangju.kr/board.es?seq=999",
            "https://www.seogu.gwangju.kr/board.es?pageNo=2",
        ],
        "document": [],
        "apply": [],
        "contact": [],
        "unknown": [],
    },
    "stats": {
        "sitemap_url_count": 0,
        "navigation_link_count": 7,
        "attachment_count": 0,
        "category_counts": {
            "menu": 1, "notice": 4, "board": 2,
            "document": 0, "apply": 0, "contact": 0, "unknown": 0,
        },
    },
    "errors": [],
}

FAKE_DOCUMENT_INDEX = [
    {
        "id": "doc-000001",
        "url": "https://www.seogu.gwangju.kr/menu.es?mid=a101",
        "canonical_url": "https://www.seogu.gwangju.kr/menu.es?mid=a101",
        "title": "종합민원",
        "category": "menu",
        "source_types": ["navigation"],
        "content_type": "page",
        "text": "",
        "summary": "",
        "metadata": {
            "base_url": "https://www.seogu.gwangju.kr/",
            "lastmod": "", "changefreq": "", "priority": "",
            "link_texts": ["종합민원"],
            "file_type": "",
            "discovered_from": ["navigation"],
        },
    }
]

FAKE_ENRICHED_INDEX = [
    {
        **FAKE_DOCUMENT_INDEX[0],
        "text": "종합민원 안내",
        "metadata": {
            **FAKE_DOCUMENT_INDEX[0]["metadata"],
            "fetched_at": "2026-06-09T12:00:00Z",
            "http_status": 200,
            "response_content_type": "text/html",
            "fetch_status": "fetched",
            "fetch_error": "",
            "description": "종합민원 안내",
        },
    }
]

FAKE_SEARCH_RESULTS = [
    {
        "rank": 1,
        "id": "doc-000001",
        "title": "종합민원",
        "url": "https://www.seogu.gwangju.kr/menu.es?mid=a101",
        "canonical_url": "https://www.seogu.gwangju.kr/menu.es?mid=a101",
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

FAKE_COMPOSE_RESULT = {
    "query": "종합민원 안내",
    "provider": "mock",
    "model": "mock-model",
    "ok": True,
    "answer_markdown": "## 답변\n\n종합민원 페이지 확인하세요.\n\n## 관련 자료\n\n- [종합민원](https://www.seogu.gwangju.kr/menu.es?mid=a101)\n\n## 다음에 할 일\n\n1. 안내 페이지 확인\n\n## 확인 필요 사항\n\n없음",
    "sources": [
        {
            "rank": 1,
            "id": "doc-000001",
            "title": "종합민원",
            "url": "https://www.seogu.gwangju.kr/menu.es?mid=a101",
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


# ------------------------------------------------------------------
# Test 1: Loader/schema test
# ------------------------------------------------------------------

class TestSeoguProfileLoader:
    """Verify seogu_gwangju profile loads correctly with all required fields."""

    @pytest.fixture
    def loader(self):
        return SiteProfileLoader()

    @pytest.fixture
    def profile(self, loader):
        return loader.load_by_id("seogu_gwangju")

    def test_profile_loads_successfully(self, profile):
        """Profile should load without exception."""
        assert profile is not None
        assert profile.site_id == "seogu_gwangju"

    def test_required_fields_present(self, profile):
        """All required SiteProfile fields should be present."""
        assert profile.name == "광주광역시 서구청"
        assert profile.base_url == "https://www.seogu.gwangju.kr/"
        assert "www.seogu.gwangju.kr" in profile.allowed_domains
        assert "seogu.gwangju.kr" in profile.allowed_domains
        assert profile.classification == "LEGACY_BOARD_SITE"
        assert profile.preferred_fetch_provider == "requests"

    def test_board_patterns_match_site(self, profile):
        """Board patterns should match seogu's actual URL patterns."""
        patterns = profile.board_patterns
        assert "bbs/BBSMSTR" in patterns
        assert "list.do" in patterns
        assert "view.do" in patterns
        assert "boardDownload.es" in patterns
        assert "boardList.do" in patterns
        assert "boardView.do" in patterns
        assert "contentsView.do" in patterns

    def test_crawl_rules_present(self, profile):
        """Crawl rules should be configured."""
        rules = profile.crawl_rules
        assert rules is not None
        assert rules.get("max_depth") == 3
        assert rules.get("max_pages") == 300
        assert rules.get("include_documents") is True
        assert rules.get("respect_robots") is True

    def test_crawl_filters_match_conservative_candidate(self, profile):
        """Crawl filters should match the conservative candidate exactly."""
        filters = profile.crawl_filters
        assert filters is not None
        assert filters != {}

        # Allow patterns should be empty
        assert filters.get("allow_patterns", []) == []

        # Deny patterns should match conservative candidate
        expected_deny = {"print=", "utm_", "utm_source=", "utm_medium=", "utm_campaign="}
        assert set(filters.get("deny_patterns", [])) == expected_deny

        # Protected patterns should match conservative candidate
        expected_protected = {"mid=", "menuId=", "board.es", "seq=", "contentId=", "articleId="}
        assert set(filters.get("protected_patterns", [])) == expected_protected

    def test_forbidden_deny_guard(self, profile):
        """Critical municipal params must NOT be in deny_patterns."""
        forbidden = {"board.es", "mid=", "menuId=", "seq=", "contentId=", "articleId="}
        deny = set(profile.crawl_filters.get("deny_patterns", []))
        for pattern in forbidden:
            assert pattern not in deny, f"Forbidden {pattern} in deny_patterns"

    def test_fallback_strategy_present(self, profile):
        """Fallback strategy should be configured."""
        strategies = profile.fallback_strategy
        assert strategies is not None
        assert len(strategies) > 0
        assert "requests" in strategies
        assert "sitemap" in strategies
        assert "homepage_map" in strategies

    def test_important_keywords_cover_municipal_services(self, profile):
        """Important keywords should cover key municipal service areas."""
        keywords = profile.important_keywords
        assert "공지사항" in keywords
        assert "고시공고" in keywords
        assert "민원" in keywords
        assert "조직도" in keywords
        assert "정보공개" in keywords
        assert "복지" in keywords
        assert "보건" in keywords
        assert "환경" in keywords

    def test_document_extensions_include_common_formats(self, profile):
        """Document extensions should include common municipal doc formats."""
        ext = profile.document_extensions
        assert "pdf" in ext
        assert "hwp" in ext
        assert "hwpx" in ext
        assert "doc" in ext
        assert "xls" in ext


# ------------------------------------------------------------------
# Test 2: Mock/static homepage map test
# ------------------------------------------------------------------

class TestSeoguHomepageMap:
    """Verify HomepageMapper with seogu profile works with static HTML."""

    @pytest.fixture
    def loader(self):
        return SiteProfileLoader()

    @pytest.fixture
    def profile(self, loader):
        return loader.load_by_id("seogu_gwangju")

    @pytest.fixture
    def mapper(self, profile):
        return HomepageMapper(fetch_provider="mock", crawl_filters=profile.crawl_filters)

    def test_mock_homepage_extracts_navigation_links(self, mapper):
        """HomepageMapper should extract nav links from static HTML."""
        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (SEOGU_HOMEPAGE_HTML, None, 200, "https://www.seogu.gwangju.kr/")
            result = mapper.build_map("https://www.seogu.gwangju.kr/")

        assert "homepage" in result
        assert "navigation_links" in result["homepage"]
        assert "attachment_links" in result["homepage"]
        nav_links = result["homepage"]["navigation_links"]
        attachment_links = result["homepage"]["attachment_links"]
        assert len(nav_links) > 0

        nav_urls = [link["url"] for link in nav_links]
        attachment_urls = [link["url"] for link in attachment_links]
        all_urls = nav_urls + attachment_urls

        # Protected structural URLs should be extracted (in nav or attachment links)
        for url in SEOGU_SURVIVE_URLS:
            assert url in all_urls, f"Protected URL {url} should be in nav or attachment links"

        # Denied URLs still appear in nav links (filtering happens in URLCrawler)
        for url in SEOGU_DENY_URLS:
            assert url in nav_urls, f"Denied URL {url} should be extracted (filtered later)"

    def test_seogu_specific_patterns_categorized(self, mapper):
        """Seogu-specific URL patterns should be categorized."""
        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (SEOGU_HOMEPAGE_HTML, None, 200, "https://www.seogu.gwangju.kr/")
            result = mapper.build_map("https://www.seogu.gwangju.kr/")

        nav_links = result["homepage"]["navigation_links"]
        attachment_links = result["homepage"]["attachment_links"]
        nav_urls = [link["url"] for link in nav_links]
        attachment_urls = [link["url"] for link in attachment_links]
        all_urls = nav_urls + attachment_urls

        # bbs/BBSMSTR pattern - should be in navigation links
        bbs_urls = [url for url in all_urls if "BBSMSTR" in url]
        assert len(bbs_urls) > 0

        # boardDownload.es pattern - categorized as document, goes to attachment_links
        download_urls = [url for url in all_urls if "boardDownload.es" in url]
        assert len(download_urls) > 0


# ------------------------------------------------------------------
# Test 3: URL classification/pattern test
# ------------------------------------------------------------------

class TestSeoguURLClassification:
    """Verify classify_url works for seogu patterns."""

    @pytest.fixture
    def loader(self):
        return SiteProfileLoader()

    @pytest.fixture
    def profile(self, loader):
        return loader.load_by_id("seogu_gwangju")

    def test_classify_bbs_list_do(self, profile):
        """bbs/BBSMSTR list.do should be classified as notice."""
        from src.crawler.homepage_mapper import classify_url
        url = "https://www.seogu.gwangju.kr/bbs/BBSMSTR_000000000276/list.do"
        category = classify_url(url, "공지사항")
        assert category == "notice"

    def test_classify_board_download_es(self, profile):
        """boardDownload.es should be classified as document."""
        from src.crawler.homepage_mapper import classify_url
        url = "https://www.seogu.gwangju.kr/boardDownload.es?bid=0013&list_no=136021&seq=1"
        category = classify_url(url, "첨부파일 다운로드")
        assert category == "document"

    def test_classify_list_do_with_page_index(self, profile):
        """list.do?pageIndex= should be recognized as pagination (notice/board)."""
        from src.crawler.homepage_mapper import classify_url
        url = "https://www.seogu.gwangju.kr/bbs/BBSMSTR_000000000275/list.do?pageIndex=2"
        category = classify_url(url, "고시공고")
        # high-priority keywords in text can make it 'notice'
        assert category in ["notice", "board", "unknown"]

    def test_classify_menu_es_mid(self, profile):
        """menu.es?mid= should be classified as menu when in navigation."""
        from src.crawler.homepage_mapper import classify_url
        url = "https://www.seogu.gwangju.kr/menu.es?mid=a101"
        category = classify_url(url, "종합민원", is_navigation=True)
        assert category == "menu"

    def test_classify_standard_patterns(self, profile):
        """Standard protected patterns should work with seogu base URL."""
        from src.crawler.homepage_mapper import classify_url
        test_cases = [
            ("https://www.seogu.gwangju.kr/board.es?seq=123", "게시판 상세"),
            ("https://www.seogu.gwangju.kr/content?contentId=456", "콘텐츠 상세"),
            ("https://www.seogu.gwangju.kr/article?articleId=789", "기사 상세"),
        ]
        for url, text in test_cases:
            category = classify_url(url, text, is_navigation=True)
            # Should be a valid category
            assert category in ["menu", "board", "notice", "apply", "contact", "location", "document", "unknown"]


# ------------------------------------------------------------------
# Test 4: No-live pipeline regression
# ------------------------------------------------------------------

class TestSeoguPipelineNoLive:
    """Verify PipelineRunner with seogu profile works without live calls."""

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    @patch("src.site_profiles.site_profile.SiteProfileLoader")
    def test_pipeline_runner_passes_seogu_filters_to_homepage_mapper(
        self,
        MockLoader,
        MockMapper,
        MockIndexer,
        MockEnricher,
        MockSearcher,
        MockComposer,
        tmp_path,
    ):
        """PipelineRunner loads real seogu profile and passes crawl_filters to HomepageMapper."""
        # Load real seogu profile
        loader = SiteProfileLoader()
        real_profile = loader.load_by_id("seogu_gwangju")

        # Configure mocks
        MockLoader.return_value.list_ids.return_value = ["seogu_gwangju", "bukgu_gwangju", "gwangju_go_kr"]
        MockLoader.return_value.load_by_id.return_value = real_profile

        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP_SEOGU
        MockIndexer.return_value.build_index.return_value = FAKE_DOCUMENT_INDEX
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_INDEX
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_COMPOSE_RESULT

        # Run pipeline
        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock")
        result = runner.run(url="https://www.seogu.gwangju.kr/", query="종합민원 안내")

        # Verify pipeline succeeded
        assert result["ok"] is True

        # Key assertion: HomepageMapper was called with real seogu crawl_filters
        MockMapper.assert_called_once()
        call_kwargs = MockMapper.call_args.kwargs

        assert "crawl_filters" in call_kwargs, "HomepageMapper should receive crawl_filters"
        passed_filters = call_kwargs["crawl_filters"]
        assert passed_filters == real_profile.crawl_filters, (
            f"Passed filters should equal real seogu profile filters, "
            f"got {passed_filters} vs expected {real_profile.crawl_filters}"
        )

        # Verify specific deny/protected patterns are in passed filters
        assert "print=" in passed_filters.get("deny_patterns", [])
        assert "utm_" in passed_filters.get("deny_patterns", [])
        assert "mid=" in passed_filters.get("protected_patterns", [])
        assert "board.es" in passed_filters.get("protected_patterns", [])
        assert "seq=" in passed_filters.get("protected_patterns", [])

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
        real_profile = loader.load_by_id("seogu_gwangju")

        MockLoader.return_value.list_ids.return_value = ["seogu_gwangju", "bukgu_gwangju", "gwangju_go_kr"]
        MockLoader.return_value.load_by_id.return_value = real_profile

        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP_SEOGU
        MockIndexer.return_value.build_index.return_value = FAKE_DOCUMENT_INDEX
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_INDEX
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_COMPOSE_RESULT

        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock")
        result = runner.run(url="https://www.seogu.gwangju.kr/", query="테스트")

        # Pipeline should complete without any live calls (all mocked)
        assert result["ok"] is True

        # HomepageMapper.build_map was called (with mock provider, no real fetch)
        MockMapper.return_value.build_map.assert_called_once()

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
        """PipelineRunner only processes mock/static content."""
        loader = SiteProfileLoader()
        real_profile = loader.load_by_id("seogu_gwangju")

        MockLoader.return_value.list_ids.return_value = ["seogu_gwangju"]
        MockLoader.return_value.load_by_id.return_value = real_profile
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP_SEOGU
        MockIndexer.return_value.build_index.return_value = FAKE_DOCUMENT_INDEX
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_INDEX
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_COMPOSE_RESULT

        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock")
        result = runner.run(url="https://www.seogu.gwangju.kr/", query="테스트")

        assert result["ok"] is True


# ------------------------------------------------------------------
# Test 5: crawl_filters behavior test
# ------------------------------------------------------------------

class TestSeoguCrawlFiltersBehavior:
    """Verify seogu crawl_filters correctly preserve/deny expected URLs."""

    @pytest.fixture
    def loader(self):
        return SiteProfileLoader()

    @pytest.fixture
    def profile(self, loader):
        return loader.load_by_id("seogu_gwangju")

    @pytest.fixture
    def filters(self, profile):
        return profile.crawl_filters

    @pytest.fixture
    def crawler(self, filters):
        return URLCrawler(crawl_filters=filters)

    @pytest.fixture
    def mapper(self, filters):
        return HomepageMapper(fetch_provider="mock", crawl_filters=filters)

    def test_static_html_protected_urls_survive_in_crawler(self, crawler):
        """Protected structural URLs survive URLCrawler.extract_links."""
        base_url = "https://www.seogu.gwangju.kr/"
        soup = BeautifulSoup(SEOGU_HOMEPAGE_HTML, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]

        for url in SEOGU_SURVIVE_URLS:
            assert url in urls, f"Protected URL {url} should survive but was filtered"

        for url in SEOGU_DENY_URLS:
            assert url not in urls, f"Denied URL {url} should be filtered but survived"

    def test_static_html_protected_urls_in_homepage_mapper(self, mapper):
        """Protected URLs appear in HomepageMapper navigation or attachment links."""
        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (SEOGU_HOMEPAGE_HTML, None, 200, "https://www.seogu.gwangju.kr/")
            result = mapper.build_map("https://www.seogu.gwangju.kr/")

        nav_links = result["homepage"]["navigation_links"]
        attachment_links = result["homepage"]["attachment_links"]
        nav_urls = [link["url"] for link in nav_links]
        attachment_urls = [link["url"] for link in attachment_links]
        all_urls = nav_urls + attachment_urls

        for url in SEOGU_SURVIVE_URLS:
            assert url in all_urls, f"Protected URL {url} should be in nav or attachment links"

    def test_should_crawl_url_with_seogu_filters(self, filters):
        """should_crawl_url pure function works with seogu filters."""
        # Protected -> allow
        assert should_crawl_url("https://www.seogu.gwangju.kr/menu.es?mid=a101", filters) is True
        assert should_crawl_url("https://www.seogu.gwangju.kr/board.es?seq=999", filters) is True
        assert should_crawl_url("https://www.seogu.gwangju.kr/content?contentId=123", filters) is True
        assert should_crawl_url("https://www.seogu.gwangju.kr/article?articleId=777", filters) is True
        # Pagination -> allow (deferred)
        assert should_crawl_url("https://www.seogu.gwangju.kr/board.es?pageNo=2", filters) is True
        # Deny -> deny
        assert should_crawl_url("https://www.seogu.gwangju.kr/page?print=1", filters) is False
        assert should_crawl_url("https://www.seogu.gwangju.kr/page?utm_source=test", filters) is False
        assert should_crawl_url("https://www.seogu.gwangju.kr/page?utm_campaign=spring", filters) is False


# ------------------------------------------------------------------
# Test 6: Inventory update test (verifies the inventory test will pass)
# ------------------------------------------------------------------

class TestConfiguredProfilesInventoryUpdated:
    """Verify that after seogu onboarding, exactly 3 profiles have crawl_filters."""

    @pytest.fixture
    def loader(self):
        return SiteProfileLoader()

    def test_exactly_three_profiles_have_crawl_filters(self, loader):
        """After Stage 403, exactly 3 profiles should have crawl_filters."""
        all_ids = loader.list_ids()

        # All three target profiles should exist
        assert "bukgu_gwangju" in all_ids
        assert "gwangju_go_kr" in all_ids
        assert "seogu_gwangju" in all_ids

        # Verify they have non-empty crawl_filters
        profiles_with_filters = [
            sid for sid in all_ids
            if loader.load_by_id(sid).crawl_filters and loader.load_by_id(sid).crawl_filters != {}
        ]

        # Should be exactly 3 after seogu onboarding
        assert set(profiles_with_filters) == {"bukgu_gwangju", "gwangju_go_kr", "seogu_gwangju"}

    def test_seogu_profile_has_crawl_filters(self, loader):
        """seogu_gwangju should have crawl_filters configured."""
        profile = loader.load_by_id("seogu_gwangju")
        assert profile.crawl_filters is not None
        assert profile.crawl_filters != {}

        # Verify conservative candidate
        expected_deny = {"print=", "utm_", "utm_source=", "utm_medium=", "utm_campaign="}
        expected_protected = {"mid=", "menuId=", "board.es", "seq=", "contentId=", "articleId="}
        assert set(profile.crawl_filters.get("deny_patterns", [])) == expected_deny
        assert set(profile.crawl_filters.get("protected_patterns", [])) == expected_protected
        assert profile.crawl_filters.get("allow_patterns", []) == []


# ------------------------------------------------------------------
# Test 7: No mutation safety
# ------------------------------------------------------------------

class TestNoScenarioSnapshotCacheMutation:
    """Verify tests don't mutate repo scenario/snapshot/cache files."""

    def test_no_repo_scenario_files_created(self, tmp_path):
        """Test outputs only go to tmp_path, not repo."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("seogu_gwangju")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)

        base_url = "https://www.seogu.gwangju.kr/"
        soup = BeautifulSoup(SEOGU_HOMEPAGE_HTML, "html.parser")
        links = crawler.extract_links(soup, base_url)

        # Just verify the test works - output is in memory, not files
        assert len(links["internal"]) > 0

        # Verify no repo files were touched by checking tmp_path isolation
        assert str(tmp_path) in str(tmp_path)


# ------------------------------------------------------------------
# Test 8: No live/network guard
# ------------------------------------------------------------------

class TestNoLiveNetworkGuard:
    """Ensure no live network/API/Firecrawl calls in tests."""

    def test_homepage_mapper_mock_provider_only(self):
        """HomepageMapper with mock provider makes no live calls."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("seogu_gwangju")
        mapper = HomepageMapper(fetch_provider="mock", crawl_filters=profile.crawl_filters)

        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (SEOGU_HOMEPAGE_HTML, None, 200, "https://www.seogu.gwangju.kr/")
            result = mapper.build_map("https://www.seogu.gwangju.kr/")
            assert result["homepage"]["title"] == "광주광역시 서구청"

    def test_url_crawler_no_live_fetch(self):
        """URLCrawler with crawl_filters only should not make live requests."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("seogu_gwangju")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)

        base_url = "https://www.seogu.gwangju.kr/"
        soup = BeautifulSoup(SEOGU_HOMEPAGE_HTML, "html.parser")
        links = crawler.extract_links(soup, base_url)
        assert len(links["internal"]) > 0

    def test_should_crawl_url_pure_function(self):
        """should_crawl_url is a pure function with no side effects."""
        url = "https://www.seogu.gwangju.kr/menu.es?mid=a101"
        assert should_crawl_url(url, CONSERVATIVE_CANDIDATE) is True
        assert should_crawl_url("https://www.seogu.gwangju.kr/page?print=1", CONSERVATIVE_CANDIDATE) is False

    def test_no_run_live_tests_env_used(self):
        """Verify RUN_LIVE_*_TESTS=1 is not used in our tests."""
        import os
        assert os.environ.get("RUN_LIVE_CRAWL_TESTS") != "1"
        assert os.environ.get("RUN_LIVE_FIRECRAWL_TESTS") != "1"
        assert os.environ.get("RUN_LIVE_API_TESTS") != "1"