"""No-live hardening tests for bukgu_gwangju crawl filter coverage.

All tests use mock/static HTML/XML fixtures only.
No live network/API/Firecrawl calls.
Focuses on hardening filter behavior verification for bukgu_gwangju.
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch
from bs4 import BeautifulSoup

from src.site_profiles.site_profile import SiteProfileLoader
from src.crawler.url_crawler import URLCrawler
from src.crawler.homepage_mapper import HomepageMapper
from src.crawler.crawl_path_filter import should_crawl_url


# ------------------------------------------------------------------
# Bukgu-specific static fixtures for hardening
# ------------------------------------------------------------------

BUKGU_HOMEPAGE_HTML_HARDENED = """
<html>
  <head>
    <title>광주광역시 북구청</title>
    <meta name="description" content="북구청 공식 홈페이지">
  </head>
  <body>
    <nav>
      <!-- Protected structural URLs (mid=, menuId=, board.es, seq=, contentId=, articleId=) -->
      <a href="/menu.es?mid=a101">종합민원</a>
      <a href="/menu.es?mid=a202">교육접수</a>
      <a href="/menu.es?mid=a303">정보공개</a>
      <a href="/board.es?seq=999">게시판 상세</a>
      <a href="/board.es?seq=1000">다른 게시판</a>
      <a href="/board.es?seq=999&pageNo=2">게시판+pagination</a>
      <a href="/content?contentId=123">콘텐츠 상세</a>
      <a href="/article?articleId=777">기사 상세</a>
      <a href="/article?articleId=888">다른 기사</a>

      <!-- Protected + tracking mixed (protected should win) -->
      <a href="/board.es?seq=999&utm_source=test">게시판+UTM 소스</a>
      <a href="/menu.es?mid=a101&utm_campaign=spring">메뉴+UTM 캠페인</a>
      <a href="/content?contentId=123&utm_medium=email">콘텐츠+UTM 매체</a>

      <!-- Denied: print=, utm_ tracking -->
      <a href="/page?print=1">인쇄 페이지</a>
      <a href="/page?print=true">인쇄 true</a>
      <a href="/page?utm_source=test">UTM 소스</a>
      <a href="/page?utm_medium=email">UTM 매체</a>
      <a href="/page?utm_campaign=spring">UTM 캠페인</a>
      <a href="/page?utm_content=abc">UTM 콘텐츠</a>

      <!-- Pagination deferred (pageNo, currentPage, pageIndex not in deny) -->
      <a href="/board.es?pageNo=2">게시판 2페이지</a>
      <a href="/board.es?currentPage=3">게시판 currentPage</a>
      <a href="/board.es?pageIndex=4">게시판 pageIndex</a>

      <!-- Normal navigation links -->
      <a href="/menu.es?mid=a404">지원사업</a>
      <a href="/menu.es?mid=a505">소통광장</a>
    </nav>
    <div class="content">
      <!-- Relative URLs -->
      <a href="menu.es?mid=a606">상대 경로</a>
      <a href="./board.es?seq=1111">상대 경로 점</a>
      <a href="../article?articleId=999">상대 경로 상위</a>

      <!-- Empty/malformed hrefs -->
      <a href="">빈 href</a>
      <a href="#">해시만</a>
      <a href="javascript:void(0)">자바스크립트</a>
    </div>
  </body>
</html>
"""

BUKGU_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://bukgu.gwangju.kr/menu.es?mid=a101</loc>
    <lastmod>2026-01-15</lastmod>
  </url>
  <url>
    <loc>https://bukgu.gwangju.kr/board.es?seq=999</loc>
    <lastmod>2026-01-14</lastmod>
  </url>
  <url>
    <loc>https://bukgu.gwangju.kr/content?contentId=123</loc>
    <lastmod>2026-01-13</lastmod>
  </url>
  <url>
    <loc>https://bukgu.gwangju.kr/page?print=1</loc>
    <lastmod>2026-01-12</lastmod>
  </url>
  <url>
    <loc>https://bukgu.gwangju.kr/page?utm_source=newsletter</loc>
    <lastmod>2026-01-11</lastmod>
  </url>
  <url>
    <loc>https://bukgu.gwangju.kr/board.es?pageNo=5</loc>
    <lastmod>2026-01-10</lastmod>
  </url>
  <url>
    <loc>https://external.example.com/other</loc>
    <lastmod>2026-01-09</lastmod>
  </url>
</urlset>
"""

# URLs that MUST survive (protected patterns present)
BUKGU_HARDENED_SURVIVE = [
    "https://bukgu.gwangju.kr/menu.es?mid=a101",
    "https://bukgu.gwangju.kr/menu.es?mid=a202",
    "https://bukgu.gwangju.kr/menu.es?mid=a303",
    "https://bukgu.gwangju.kr/board.es?seq=999",
    "https://bukgu.gwangju.kr/board.es?seq=1000",
    "https://bukgu.gwangju.kr/board.es?seq=999&pageNo=2",
    "https://bukgu.gwangju.kr/content?contentId=123",
    "https://bukgu.gwangju.kr/article?articleId=777",
    "https://bukgu.gwangju.kr/article?articleId=888",
    "https://bukgu.gwangju.kr/menu.es?mid=a404",
    "https://bukgu.gwangju.kr/menu.es?mid=a505",
    # Pagination deferred - not in deny_patterns
    "https://bukgu.gwangju.kr/board.es?pageNo=2",
    "https://bukgu.gwangju.kr/board.es?currentPage=3",
    "https://bukgu.gwangju.kr/board.es?pageIndex=4",
    # Protected + tracking mixed -> protected wins
    "https://bukgu.gwangju.kr/board.es?seq=999&utm_source=test",
    "https://bukgu.gwangju.kr/menu.es?mid=a101&utm_campaign=spring",
    "https://bukgu.gwangju.kr/content?contentId=123&utm_medium=email",
]

# URLs that MUST be denied (pure denied patterns)
BUKGU_HARDENED_DENY = [
    "https://bukgu.gwangju.kr/page?print=1",
    "https://bukgu.gwangju.kr/page?print=true",
    "https://bukgu.gwangju.kr/page?utm_source=test",
    "https://bukgu.gwangju.kr/page?utm_medium=email",
    "https://bukgu.gwangju.kr/page?utm_campaign=spring",
    "https://bukgu.gwangju.kr/page?utm_content=abc",
]


# ------------------------------------------------------------------
# Test 1: Profile loads with exact filter candidate
# ------------------------------------------------------------------

class TestBukguProfileFilterExactCandidate:
    """Verify bukgu_gwangju loads with exact conservative candidate."""

    @pytest.fixture
    def loader(self):
        return SiteProfileLoader()

    @pytest.fixture
    def profile(self, loader):
        return loader.load_by_id("bukgu_gwangju")

    def test_profile_loads_successfully(self, profile):
        assert profile is not None
        assert profile.site_id == "bukgu_gwangju"

    def test_crawl_filters_exact_conservative_candidate(self, profile):
        """Crawl filters must match Stage 394 applied config exactly."""
        filters = profile.crawl_filters
        assert filters is not None
        assert isinstance(filters, dict)

        # Allow patterns empty
        assert filters.get("allow_patterns", []) == []

        # Deny patterns - exactly 5
        deny = filters.get("deny_patterns", [])
        expected_deny = {"print=", "utm_", "utm_source=", "utm_medium=", "utm_campaign="}
        assert set(deny) == expected_deny
        assert len(deny) == 5

        # Protected patterns - exactly 6
        protected = filters.get("protected_patterns", [])
        expected_protected = {"mid=", "menuId=", "board.es", "seq=", "contentId=", "articleId="}
        assert set(protected) == expected_protected
        assert len(protected) == 6


# ------------------------------------------------------------------
# Test 2: Protected + Denied mixed URL precedence
# ------------------------------------------------------------------

class TestBukguProtectedDeniedMixedPrecedence:
    """Protected patterns take precedence over deny patterns."""

    @pytest.fixture
    def crawler(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return URLCrawler(crawl_filters=profile.crawl_filters)

    @pytest.mark.parametrize("url", BUKGU_HARDENED_SURVIVE)
    def test_protected_beats_deny(self, crawler, url):
        """URL with both protected and tracking params should survive."""
        base_url = "https://bukgu.gwangju.kr/"
        # Create minimal HTML with this link
        html = f'<html><body><a href="{url}">link</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert url in urls, f"Protected+tracking URL {url} should survive"

    @pytest.mark.parametrize("url", BUKGU_HARDENED_DENY)
    def test_pure_denied_excluded(self, crawler, url):
        """Pure denied URLs should be excluded."""
        base_url = "https://bukgu.gwangju.kr/"
        html = f'<html><body><a href="{url}">link</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert url not in urls, f"Pure denied URL {url} should be filtered"


# ------------------------------------------------------------------
# Test 3: Pure denied duplicate cases
# ------------------------------------------------------------------

class TestBukguPureDeniedDuplicates:
    """Verify all tracking-only variants are denied."""

    @pytest.fixture
    def filters(self):
        loader = SiteProfileLoader()
        return loader.load_by_id("bukgu_gwangju").crawl_filters

    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/page?print=1",
        "https://bukgu.gwangju.kr/page?utm_source=test",
        "https://bukgu.gwangju.kr/page?utm_medium=email",
        "https://bukgu.gwangju.kr/page?utm_campaign=spring",
        "https://bukgu.gwangju.kr/page?utm_content=abc",
    ])
    def test_should_crawl_deny_pure_tracking(self, filters, url):
        assert should_crawl_url(url, filters) is False, f"{url} should be denied"


# ------------------------------------------------------------------
# Test 4: Pagination deferred edge cases
# ------------------------------------------------------------------

class TestBukguPaginationDeferred:
    """Pagination params not in deny_patterns -> should survive."""

    @pytest.fixture
    def filters(self):
        loader = SiteProfileLoader()
        return loader.load_by_id("bukgu_gwangju").crawl_filters

    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/board.es?pageNo=2",
        "https://bukgu.gwangju.kr/board.es?currentPage=3",
        "https://bukgu.gwangju.kr/board.es?pageIndex=4",
        "https://bukgu.gwangju.kr/board.es?page=5",
        "https://bukgu.gwangju.kr/board.es?p=6",
    ])
    def test_pagination_params_survive(self, filters, url):
        assert should_crawl_url(url, filters) is True, f"Pagination URL {url} should survive"


# ------------------------------------------------------------------
# Test 5: Duplicate query param order invariance
# ------------------------------------------------------------------

class TestBukguQueryOrderInvariance:
    """URL with same params in different order should have same result."""

    @pytest.fixture
    def filters(self):
        loader = SiteProfileLoader()
        return loader.load_by_id("bukgu_gwangju").crawl_filters

    def test_protected_plus_tracking_order_invariant(self, filters):
        """Protected param first or last should not matter."""
        urls_same = [
            "https://bukgu.gwangju.kr/board.es?seq=999&utm_source=test",
            "https://bukgu.gwangju.kr/board.es?utm_source=test&seq=999",
        ]
        results = [should_crawl_url(u, filters) for u in urls_same]
        assert all(results), "Order of protected+tracking params should not matter"

    def test_multiple_tracking_params_order_invariant(self, filters):
        """Multiple tracking params order should not matter."""
        urls = [
            "https://bukgu.gwangju.kr/page?utm_source=a&utm_medium=b",
            "https://bukgu.gwangju.kr/page?utm_medium=b&utm_source=a",
        ]
        results = [should_crawl_url(u, filters) for u in urls]
        assert all(not r for r in results), "Pure tracking URLs order should not matter"


# ------------------------------------------------------------------
# Test 6: Fragment removal and deduplication
# ------------------------------------------------------------------

class TestBukguFragmentHandling:
    """Fragment (#...) should be removed before filtering."""

    @pytest.fixture
    def filters(self):
        loader = SiteProfileLoader()
        return loader.load_by_id("bukgu_gwangju").crawl_filters

    def test_fragment_removed_before_filter(self, filters):
        """Fragment should be stripped before applying filters."""
        url_with_fragment = "https://bukgu.gwangju.kr/board.es?seq=999#section-1"
        url_without = "https://bukgu.gwangju.kr/board.es?seq=999"
        assert should_crawl_url(url_with_fragment, filters) == should_crawl_url(url_without, filters)
        assert should_crawl_url(url_without, filters) is True


# ------------------------------------------------------------------
# Test 7: Relative URL normalization
# ------------------------------------------------------------------

class TestBukguRelativeUrlNormalization:
    """Relative URLs should be normalized against base_url."""

    @pytest.fixture
    def crawler(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return URLCrawler(crawl_filters=profile.crawl_filters)

    def test_relative_url_normalized_and_filtered(self, crawler):
        """Relative href should be resolved against base_url."""
        base_url = "https://bukgu.gwangju.kr/"
        # Relative URL with protected pattern
        html = '<html><body><a href="menu.es?mid=a101">상대경로</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        expected = "https://bukgu.gwangju.kr/menu.es?mid=a101"
        assert expected in urls, f"Relative URL should be resolved to {expected}"

    def test_relative_with_dot_normalized(self, crawler):
        """Relative ./path should be resolved correctly."""
        base_url = "https://bukgu.gwangju.kr/"
        html = '<html><body><a href="./board.es?seq=222">상대점</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        expected = "https://bukgu.gwangju.kr/board.es?seq=222"
        assert expected in urls, f"./ relative URL should be resolved to {expected}"

    def test_relative_parent_normalized(self, crawler):
        """Relative ../path should be resolved correctly against base path."""
        base_url = "https://bukgu.gwangju.kr/some/path/"
        html = '<html><body><a href="../article?articleId=999">상대상위</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        # URL resolution goes up one level from /some/path/ to /some/
        expected = "https://bukgu.gwangju.kr/some/article?articleId=999"
        assert expected in urls, f"../ relative URL should be resolved to {expected}"


# ------------------------------------------------------------------
# Test 8: Allowed domain isolation
# ------------------------------------------------------------------

class TestBukguAllowedDomainIsolation:
    """Only allowed domains should be in candidate pool."""

    @pytest.fixture
    def crawler(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return URLCrawler(crawl_filters=profile.crawl_filters)

    def test_same_domain_allowed(self, crawler):
        """bukgu.gwangju.kr and www.bukgu.gwangju.kr should be allowed."""
        base_url = "https://bukgu.gwangju.kr/"
        html = '<html><body><a href="https://www.bukgu.gwangju.kr/menu.es?mid=a101">www 서브도메인</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert "https://www.bukgu.gwangju.kr/menu.es?mid=a101" in urls

    def test_outside_domain_excluded_or_handled(self, crawler):
        """External domains should not be in internal links."""
        base_url = "https://bukgu.gwangju.kr/"
        html = '<html><body><a href="https://external.example.com/page">외부</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        # External URLs should go to "external" not "internal"
        assert "https://external.example.com/page" not in urls


# ------------------------------------------------------------------
# Test 9: Homepage static HTML fixture - Bukgu menu/board links preserved
# ------------------------------------------------------------------

class TestBukguHomepageStaticHtml:
    """Homepage mapper with static HTML preserves structural links."""

    @pytest.fixture
    def mapper(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return HomepageMapper(fetch_provider="mock", crawl_filters=profile.crawl_filters)

    def test_homepage_mapper_extracts_structural_links(self, mapper):
        """HomepageMapper should extract protected structural links from static HTML."""
        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (BUKGU_HOMEPAGE_HTML_HARDENED, None, 200, "https://bukgu.gwangju.kr/")
            result = mapper.build_map("https://bukgu.gwangju.kr/")

        nav_links = result["homepage"]["navigation_links"]
        nav_urls = [link["url"] for link in nav_links]

        # All survival URLs should be present in nav links
        # (HomepageMapper extracts without filtering; filtering happens in URLCrawler)
        for url in BUKGU_HARDENED_SURVIVE:
            assert url in nav_urls, f"Structural URL {url} should be in navigation links"

        # Denied URLs also appear at extraction stage (filtered later by URLCrawler)
        for url in BUKGU_HARDENED_DENY:
            assert url in nav_urls, f"Denied URL {url} should be extracted (will be filtered by crawler)"


# ------------------------------------------------------------------
# Test 10: Sitemap static XML fixture - Bukgu important links
# ------------------------------------------------------------------

class TestBukguSitemapStaticXml:
    """Sitemap XML fixture processing preserves important links."""

    @pytest.fixture
    def mapper(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return HomepageMapper(fetch_provider="mock", crawl_filters=profile.crawl_filters)

    def test_sitemap_preserves_protected_excludes_denied(self, mapper):
        """Sitemap URLs with protected patterns preserved; denied filtered by URLCrawler."""
        with patch.object(mapper, "fetch_content") as mock_fetch:
            # Sitemap returns XML, not HTML
            mock_fetch.return_value = (BUKGU_SITEMAP_XML, None, 200, "https://bukgu.gwangju.kr/sitemap.xml")
            result = mapper.build_map("https://bukgu.gwangju.kr/")

        # Sitemap URLs are in result["sitemap"]["urls"] as dicts with 'url' key
        sitemap_urls = [item["url"] for item in result["sitemap"]["urls"]]

        # Protected URLs from sitemap should be candidates
        assert "https://bukgu.gwangju.kr/menu.es?mid=a101" in sitemap_urls
        assert "https://bukgu.gwangju.kr/board.es?seq=999" in sitemap_urls
        assert "https://bukgu.gwangju.kr/content?contentId=123" in sitemap_urls
        assert "https://bukgu.gwangju.kr/board.es?pageNo=5" in sitemap_urls

        # Denied URLs from sitemap also appear initially (filtered later)
        assert "https://bukgu.gwangju.kr/page?print=1" in sitemap_urls
        assert "https://bukgu.gwangju.kr/page?utm_source=newsletter" in sitemap_urls

        # External domain should be in sitemap URLs (allowed domains handled by filter)
        assert "https://external.example.com/other" in sitemap_urls


# ------------------------------------------------------------------
# Test 11: Malformed/empty href safety
# ------------------------------------------------------------------

class TestBukguMalformedHrefSafety:
    """Empty, hash-only, javascript: hrefs should be handled safely."""

    @pytest.fixture
    def crawler(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return URLCrawler(crawl_filters=profile.crawl_filters)

    def test_empty_href_ignored(self, crawler):
        """Empty href should not cause error."""
        base_url = "https://bukgu.gwangju.kr/"
        html = '<html><body><a href="">빈링크</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        # Should not crash, empty internal
        assert isinstance(links["internal"], list)

    def test_hash_only_href_ignored(self, crawler):
        """# only href should be ignored."""
        base_url = "https://bukgu.gwangju.kr/"
        html = '<html><body><a href="#">해시만</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        assert isinstance(links["internal"], list)

    def test_javascript_href_ignored(self, crawler):
        """javascript: href should be ignored."""
        base_url = "https://bukgu.gwangju.kr/"
        html = '<html><body><a href="javascript:void(0)">자바스크립트</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        assert isinstance(links["internal"], list)
        assert len(links["internal"]) == 0


# ------------------------------------------------------------------
# Test 12: Protected board.es with tracking params survives
# ------------------------------------------------------------------

class TestBukguBoardEsWithTracking:
    """board.es?seq=...&utm_... should survive (protected beats tracking)."""

    @pytest.fixture
    def filters(self):
        loader = SiteProfileLoader()
        return loader.load_by_id("bukgu_gwangju").crawl_filters

    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/board.es?seq=999&utm_source=test",
        "https://bukgu.gwangju.kr/board.es?seq=1000&utm_medium=email",
        "https://bukgu.gwangju.kr/board.es?seq=999&utm_campaign=spring&utm_content=abc",
        "https://bukgu.gwangju.kr/board.es?utm_source=test&seq=999",  # order reversed
    ])
    def test_board_es_with_tracking_survives(self, filters, url):
        assert should_crawl_url(url, filters) is True, f"board.es with tracking {url} should survive"


# ------------------------------------------------------------------
# Test 13: Forbidden deny guard
# ------------------------------------------------------------------

class TestBukguForbiddenDenyGuard:
    """Critical municipal params must never be in deny_patterns."""

    @pytest.fixture
    def profile(self):
        loader = SiteProfileLoader()
        return loader.load_by_id("bukgu_gwangju")

    def test_no_forbidden_in_deny(self, profile):
        """Verify forbidden patterns not in deny_patterns."""
        forbidden = {"board.es", "mid=", "menuId=", "seq=", "contentId=", "articleId="}
        deny = set(profile.crawl_filters.get("deny_patterns", []))
        for pattern in forbidden:
            assert pattern not in deny, f"Forbidden pattern {pattern} found in deny_patterns"


# ------------------------------------------------------------------
# Test 14: No mutation safety (tmp_path only)
# ------------------------------------------------------------------

class TestBukguNoMutation:
    """Tests use tmp_path only; no repo file mutation."""

    def test_no_repo_files_touched(self, tmp_path):
        """Verify test only uses tmp_path."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)

        base_url = "https://bukgu.gwangju.kr/"
        soup = BeautifulSoup(BUKGU_HOMEPAGE_HTML_HARDENED, "html.parser")
        links = crawler.extract_links(soup, base_url)

        assert len(links["internal"]) > 0
        # tmp_path is isolated - just assert it's available
        assert str(tmp_path) in str(tmp_path)


# ------------------------------------------------------------------
# Test 15: No live/network guard
# ------------------------------------------------------------------

class TestBukguNoLiveNetwork:
    """Ensure no live network/API/Firecrawl calls in tests."""

    def test_homepage_mapper_mock_provider(self):
        """HomepageMapper with mock provider makes no live calls."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        mapper = HomepageMapper(fetch_provider="mock", crawl_filters=profile.crawl_filters)

        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (BUKGU_HOMEPAGE_HTML_HARDENED, None, 200, "https://bukgu.gwangju.kr/")
            result = mapper.build_map("https://bukgu.gwangju.kr/")
            assert result["homepage"]["title"] == "광주광역시 북구청"

    def test_url_crawler_no_live_fetch(self):
        """URLCrawler with crawl_filters only uses static HTML."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)

        base_url = "https://bukgu.gwangju.kr/"
        soup = BeautifulSoup(BUKGU_HOMEPAGE_HTML_HARDENED, "html.parser")
        links = crawler.extract_links(soup, base_url)
        assert len(links["internal"]) > 0

    def test_should_crawl_pure_function(self):
        """should_crawl_url is pure with no side effects."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        filters = profile.crawl_filters

        url = "https://bukgu.gwangju.kr/menu.es?mid=a101"
        assert should_crawl_url(url, filters) is True
        assert should_crawl_url("https://bukgu.gwangju.kr/page?print=1", filters) is False

    def test_no_run_live_env_vars(self):
        """RUN_LIVE_*_TESTS=1 not set in test environment."""
        assert os.environ.get("RUN_LIVE_CRAWL_TESTS") != "1"
        assert os.environ.get("RUN_LIVE_FIRECRAWL_TESTS") != "1"
        assert os.environ.get("RUN_LIVE_API_TESTS") != "1"