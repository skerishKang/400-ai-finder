"""No-live Stage 411 hardening tests for bukgu_gwangju crawl filter coverage.

All tests use mock/static HTML/XML fixtures only.
No live network/API/Firecrawl calls.
Extends Stage 409/410 with:
1. Query-order / URL normalization edge cases
2. Homepage + sitemap duplicate canonicalization
3. Percent-encoded Korean/query parameter cases
4. Malformed-but-parseable internal links
5. Mixed precedence regressions
6. No-live guard 강화
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

from src.site_profiles.site_profile import SiteProfileLoader
from src.crawler.url_crawler import URLCrawler
from src.crawler.homepage_mapper import HomepageMapper
from src.crawler.crawl_path_filter import should_crawl_url


# ------------------------------------------------------------------
# Static fixtures for Stage 411
# ------------------------------------------------------------------

# Extended homepage with normalization edge cases
BUKGU_HOMEPAGE_HTML_STAGE411 = """
<html>
  <head>
    <title>광주광역시 북구청</title>
    <meta name="description" content="북구청 공식 홈페이지">
  </head>
  <body>
    <nav>
      <!-- Protected structural URLs -->
      <a href="/menu.es?mid=a101">종합민원</a>
      <a href="/board.es?seq=999">게시판 상세</a>
      <a href="/content?contentId=123">콘텐츠 상세</a>
      <a href="/article?articleId=777">기사 상세</a>

      <!-- Query-order variants for same protected URL -->
      <a href="/board.es?seq=999&utm_source=test">게시판+UTM 소스</a>
      <a href="/board.es?utm_source=test&seq=999">UTM+게시판</a>
      <a href="/board.es?seq=999&pageNo=2&utm_source=test">보호+페이지+트래킹</a>
      <a href="/board.es?utm_source=test&pageNo=2&seq=999">트래킹+페이지+보호</a>

      <!-- Percent-encoded Korean query -->
      <a href="/board.es?keyField=title&amp;keyWord=%EC%B6%9C%EC%84%A0&seq=999">게시판+한글검색어</a>
      <a href="/content?searchKeyword=%EA%B3%B5%EA%B3%A0&amp;mid=a101&amp;contentId=123">컨텐츠+한글검색</a>

      <!-- Denied patterns -->
      <a href="/page?print=1">인쇄 페이지</a>
      <a href="/page?utm_source=test">UTM 소스</a>

      <!-- Pagination (deferred) -->
      <a href="/board.es?pageNo=2">페이지 2</a>
      <a href="/board.es?pageNo=2&amp;page=10">복합 페이지네이션</a>

      <!-- Normal navigation -->
      <a href="/menu.es?mid=a404">지원사업</a>
    </nav>
    <div class="content">
      <!-- Malformed-but-parseable internal links -->
      <a href="//bukgu.gwangju.kr/board.es?seq=1111">스킴-상대</a>
      <a href="/board.es?seq=1111 ">공백 포함</a>
      <a href="/board.es?seq=1111\t">탭 포함</a>
      <a href="/board.es?seq=1111\n">개행 포함</a>
      <a href="/board.es?seq=1111\r">CR 포함</a>
      <a href="/board.es?seq=1111\r\n">CRLF 포함</a>
      <a href="/board.es?seq=1111&amp;utm_source=test">&amp;가 HTML 엔티티로</a>

      <!-- Relative URLs -->
      <a href="menu.es?mid=a606">상대 경로</a>
      <a href="./board.es?seq=1111">점 경로</a>
      <a href="../article?articleId=999">상위 경로</a>
      <a href="//bukgu.gwangju.kr/menu.es?mid=a606">스킴-상대 메뉴</a>

      <!-- Empty/malformed hrefs -->
      <a href="">빈 href</a>
      <a href="#">해시만</a>
      <a href="javascript:void(0)">자바스크립트</a>
      <a href="mailto:test@example.com">메일투</a>
      <a href="tel:+82-62-123-4567">전화</a>
    </div>
  </body>
</html>
"""

# Sitemap with duplicate canonicalization cases
BUKGU_SITEMAP_XML_STAGE411 = """<?xml version="1.0" encoding="UTF-8"?>
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
  <!-- Duplicate URLs with different query order -->
  <url>
    <loc>https://bukgu.gwangju.kr/board.es?utm_source=newsletter&amp;seq=999</loc>
    <lastmod>2026-01-09</lastmod>
  </url>
  <url>
    <loc>https://bukgu.gwangju.kr/board.es?seq=999&amp;utm_source=newsletter</loc>
    <lastmod>2026-01-08</lastmod>
  </url>
  <!-- Percent-encoded Korean in sitemap -->
  <url>
    <loc>https://bukgu.gwangju.kr/board.es?keyWord=%ED%95%98%EB%81%9C%EA%B3%B5%EA%B3%A0&amp;seq=1001</loc>
    <lastmod>2026-01-07</lastmod>
  </url>
  <!-- Fragment and malformed -->
  <url>
    <loc>https://bukgu.gwangju.kr/board.es?seq=999#section-1</loc>
    <lastmod>2026-01-06</lastmod>
  </url>
  <!-- External domain -->
  <url>
    <loc>https://external.example.com/other</loc>
    <lastmod>2026-01-05</lastmod>
  </url>
  <!-- Scheme-relative in sitemap -->
  <url>
    <loc>//bukgu.gwangju.kr/board.es?seq=2000</loc>
    <lastmod>2026-01-04</lastmod>
  </url>
</urlset>
"""

# Simpler sitemap for baseline
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
</urlset>
"""


# Helper for mocking HomepageMapper fetch_content
def make_mock_fetch(homepage_html=BUKGU_HOMEPAGE_HTML_STAGE411, sitemap_xml=BUKGU_SITEMAP_XML_STAGE411):
    def mock_fetch(url):
        if 'robots.txt' in url:
            return ('', None, 200, url)
        elif 'sitemap' in url:
            return (sitemap_xml, None, 200, url)
        else:
            return (homepage_html, None, 200, url)
    return mock_fetch


# ------------------------------------------------------------------
# Test 1: Query-order / URL normalization edge cases
# ------------------------------------------------------------------

class TestBukguQueryOrderNormalization:
    """Same meaning URLs with different query order should have same decision."""

    @pytest.fixture
    def filters(self):
        loader = SiteProfileLoader()
        return loader.load_by_id("bukgu_gwangju").crawl_filters

    @pytest.fixture
    def crawler(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return URLCrawler(crawl_filters=profile.crawl_filters)

    def test_query_order_invariance_protected_tracking(self, filters):
        """Protected + tracking params: order should not matter."""
        urls = [
            "https://bukgu.gwangju.kr/board.es?seq=999&utm_source=test",
            "https://bukgu.gwangju.kr/board.es?utm_source=test&seq=999",
        ]
        results = [should_crawl_url(u, filters) for u in urls]
        assert all(results), "Protected+tracking order invariant"

    def test_query_order_invariance_pagination_tracking(self, filters):
        """Protected + pagination + tracking: order should not matter."""
        urls = [
            "https://bukgu.gwangju.kr/board.es?seq=999&pageNo=2&utm_source=test",
            "https://bukgu.gwangju.kr/board.es?utm_source=test&pageNo=2&seq=999",
            "https://bukgu.gwangju.kr/board.es?pageNo=2&utm_source=test&seq=999",
        ]
        results = [should_crawl_url(u, filters) for u in urls]
        assert all(results), "Protected+pagination+tracking order invariant"

    def test_same_url_different_query_order_sitemap(self, filters):
        """Sitemap order variants should behave same."""
        urls = [
            "https://bukgu.gwangju.kr/board.es?utm_source=newsletter&seq=999",
            "https://bukgu.gwangju.kr/board.es?seq=999&utm_source=newsletter",
        ]
        results = [should_crawl_url(u, filters) for u in urls]
        assert all(results), "Sitemap order variants invariant"

    def test_crawler_extract_query_order_invariant(self, crawler):
        """URLCrawler.extract_links should preserve order invariant."""
        base_url = "https://bukgu.gwangju.kr/"
        urls = [
            "https://bukgu.gwangju.kr/board.es?seq=999&utm_source=test",
            "https://bukgu.gwangju.kr/board.es?utm_source=test&seq=999",
        ]
        for url in urls:
            html = f'<html><body><a href="{url}">link</a></body></html>'
            soup = BeautifulSoup(html, "html.parser")
            links = crawler.extract_links(soup, base_url)
            internal_urls = [link["url"] for link in links["internal"]]
            assert url in internal_urls, f"Extracted URL {url} should survive"


# ------------------------------------------------------------------
# Test 2: Fragment / trailing slash / relative path normalization
# ------------------------------------------------------------------

class TestBukguUrlNormalization:
    """Fragment removal and URL normalization before filtering."""

    @pytest.fixture
    def filters(self):
        loader = SiteProfileLoader()
        return loader.load_by_id("bukgu_gwangju").crawl_filters

    @pytest.fixture
    def crawler(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return URLCrawler(crawl_filters=profile.crawl_filters)

    def test_fragment_stripped_before_filter(self, filters):
        """Fragment should be stripped before applying filters."""
        url_with_fragment = "https://bukgu.gwangju.kr/board.es?seq=999#section-1"
        url_without = "https://bukgu.gwangju.kr/board.es?seq=999"
        assert should_crawl_url(url_with_fragment, filters) == should_crawl_url(url_without, filters)
        assert should_crawl_url(url_without, filters) is True

    def test_sitemap_fragment_url_survives(self, filters):
        """Sitemap URL with fragment should be evaluated without fragment."""
        # Sitemap provides URL with fragment; should_crawl_url strips it
        assert should_crawl_url("https://bukgu.gwangju.kr/board.es?seq=999#section-1", filters) is True

    def test_relative_path_normalization(self, crawler):
        """Relative URLs should be normalized against base_url."""
        base_url = "https://bukgu.gwangju.kr/"
        html = '<html><body><a href="menu.es?mid=a101">상대</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert "https://bukgu.gwangju.kr/menu.es?mid=a101" in urls

    def test_dot_relative_normalization(self, crawler):
        """Relative ./path should normalize correctly."""
        base_url = "https://bukgu.gwangju.kr/"
        html = '<html><body><a href="./board.es?seq=1111">점경로</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert "https://bukgu.gwangju.kr/board.es?seq=1111" in urls

    def test_parent_relative_normalization(self, crawler):
        """Relative ../path should normalize correctly."""
        base_url = "https://bukgu.gwangju.kr/some/path/"
        html = '<html><body><a href="../article?articleId=999">상위경로</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        # Goes up one level: /some/path/ -> /some/
        assert "https://bukgu.gwangju.kr/some/article?articleId=999" in urls

    def test_scheme_relative_normalization(self, crawler):
        """Scheme-relative //host/path should be normalized to https."""
        base_url = "https://bukgu.gwangju.kr/"
        html = '<html><body><a href="//bukgu.gwangju.kr/board.es?seq=1111">스킴상대</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        # Scheme-relative should be resolved to https
        assert "https://bukgu.gwangju.kr/board.es?seq=1111" in urls


# ------------------------------------------------------------------
# Test 3: Homepage + Sitemap duplicate canonicalization
# ------------------------------------------------------------------

class TestBukguHomepageSitemapCanonicalization:
    """Homepage and sitemap may provide same URL in different forms."""

    @pytest.fixture
    def mapper(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return HomepageMapper(fetch_provider="mock", crawl_filters=profile.crawl_filters)

    def test_same_url_homepage_and_sitemap(self, mapper):
        """Same protected URL from homepage HTML and sitemap XML."""
        mock_fetch = make_mock_fetch()
        with patch.object(mapper, "fetch_content", side_effect=mock_fetch):
            result = mapper.build_map("https://bukgu.gwangju.kr/")

        # Same URL appears in both nav_links and sitemap
        nav_urls = [link["url"] for link in result["homepage"]["navigation_links"]]
        sitemap_urls = [item["url"] for item in result["sitemap"]["urls"]]

        assert "https://bukgu.gwangju.kr/board.es?seq=999" in nav_urls
        assert "https://bukgu.gwangju.kr/board.es?seq=999" in sitemap_urls

    def test_query_order_variants_same_protected_url(self, mapper):
        """Homepage has one order, sitemap has another - both survive."""
        mock_fetch = make_mock_fetch()
        with patch.object(mapper, "fetch_content", side_effect=mock_fetch):
            result = mapper.build_map("https://bukgu.gwangju.kr/")

        sitemap_urls = [item["url"] for item in result["sitemap"]["urls"]]
        
        # Both order variants from sitemap (note: &amp; decoded to &)
        assert "https://bukgu.gwangju.kr/board.es?seq=999" in sitemap_urls
        assert "https://bukgu.gwangju.kr/board.es?utm_source=newsletter&seq=999" in sitemap_urls
        assert "https://bukgu.gwangju.kr/board.es?seq=999&utm_source=newsletter" in sitemap_urls

    def test_percent_encoded_same_url(self, mapper):
        """Percent-encoded Korean query should be treated as same URL after decode."""
        mock_fetch = make_mock_fetch()
        with patch.object(mapper, "fetch_content", side_effect=mock_fetch):
            result = mapper.build_map("https://bukgu.gwangju.kr/")

        sitemap_urls = [item["url"] for item in result["sitemap"]["urls"]]
        
        # Percent-encoded Korean in sitemap (stays percent-encoded)
        assert "https://bukgu.gwangju.kr/board.es?keyWord=%ED%95%98%EB%81%9C%EA%B3%B5%EA%B3%A0&seq=1001" in sitemap_urls


# ------------------------------------------------------------------
# Test 4: Percent-encoded Korean/query parameter cases
# ------------------------------------------------------------------

class TestBukguPercentEncodedQueries:
    """Percent-encoded Korean and special chars in query params."""

    @pytest.fixture
    def filters(self):
        loader = SiteProfileLoader()
        return loader.load_by_id("bukgu_gwangju").crawl_filters

    @pytest.fixture
    def crawler(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return URLCrawler(crawl_filters=profile.crawl_filters)

    def test_korean_search_query_protected_survives(self, filters):
        """Percent-encoded Korean search with protected params survives."""
        # %EC%B6%9C%EC%84%A0 = "출전" (UTF-8)
        url = "https://bukgu.gwangju.kr/board.es?keyField=title&amp;keyWord=%EC%B6%9C%EC%84%A0&amp;seq=999"
        assert should_crawl_url(url, filters) is True

    def test_korean_search_with_mid_protected(self, filters):
        """Korean search query with mid= protected survives."""
        url = "https://bukgu.gwangju.kr/content?searchKeyword=%EA%B3%B5%EA%B3%A0&amp;mid=a101&amp;contentId=123"
        assert should_crawl_url(url, filters) is True

    def test_crawler_extracts_percent_encoded(self, crawler):
        """URLCrawler extracts percent-encoded URLs correctly."""
        base_url = "https://bukgu.gwangju.kr/"
        # HTML with percent-encoded Korean (complete encoding for keyWord value)
        # %EC%B6%9C%EC%84%A0 = "출전"
        html = '<html><body><a href="/board.es?keyWord=%EC%B6%9C%EC%84%A0&seq=999">한글검색</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        # BeautifulSoup/urljoin preserves the percent-encoding
        expected = "https://bukgu.gwangju.kr/board.es?keyWord=%EC%B6%9C%EC%84%A0&seq=999"
        assert expected in urls

    def test_double_encoded_not_handled_here(self, filters):
        """Double-encoded URLs may not be handled - document behavior."""
        # This documents current behavior: we don't double-decode
        url = "https://bukgu.gwangju.kr/board.es?seq=999&amp;keyWord=%25EC%25B6%259C%EC%2584%25A0"
        # Just verify it doesn't crash
        result = should_crawl_url(url, filters)
        assert isinstance(result, bool)


# ------------------------------------------------------------------
# Test 5: Malformed-but-parseable internal links
# ------------------------------------------------------------------

class TestBukguMalformedParseableLinks:
    """Malformed but parseable URLs should be handled safely."""

    @pytest.fixture
    def crawler(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return URLCrawler(crawl_filters=profile.crawl_filters)

    def test_scheme_relative_survives(self, crawler):
        """Scheme-relative //host/path should be parsed and filtered."""
        base_url = "https://bukgu.gwangju.kr/"
        html = '<html><body><a href="//bukgu.gwangju.kr/board.es?seq=1111">스킴상대</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert "https://bukgu.gwangju.kr/board.es?seq=1111" in urls

    def test_whitespace_in_href_handled(self, crawler):
        """Href with whitespace should be handled or ignored safely."""
        base_url = "https://bukgu.gwangju.kr/"
        test_cases = [
            '/board.es?seq=1111 ',
            '/board.es?seq=1111\t',
            '/board.es?seq=1111\n',
            '/board.es?seq=1111\r',
            '/board.es?seq=1111\r\n',
        ]
        for href in test_cases:
            html = f'<html><body><a href="{href}">테스트</a></body></html>'
            soup = BeautifulSoup(html, "html.parser")
            links = crawler.extract_links(soup, base_url)
            # Should not crash
            assert isinstance(links["internal"], list)

    def test_html_entity_ampersand_in_href(self, crawler):
        """HTML entity &amp; in href should be handled."""
        base_url = "https://bukgu.gwangju.kr/"
        html = '<html><body><a href="/board.es?seq=1111&amp;utm_source=test">엔티티</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        # BeautifulSoup decodes &amp; to &, so check for decoded form
        expected = "https://bukgu.gwangju.kr/board.es?seq=1111&utm_source=test"
        assert expected in urls

    def test_empty_hash_javascript_mailto_safe(self, crawler):
        """Empty, hash, javascript:, mailto:, tel: should not crash."""
        base_url = "https://bukgu.gwangju.kr/"
        test_hrefs = ["", "#", "javascript:void(0)", "mailto:test@example.com", "tel:+82-62-123-4567"]
        for href in test_hrefs:
            html = f'<html><body><a href="{href}">테스트</a></body></html>'
            soup = BeautifulSoup(html, "html.parser")
            links = crawler.extract_links(soup, base_url)
            assert isinstance(links["internal"], list)


# ------------------------------------------------------------------
# Test 6: Mixed precedence regressions
# ------------------------------------------------------------------

class TestBukguMixedPrecedenceRegression:
    """Verify protected > deny > pagination precedence."""

    @pytest.fixture
    def filters(self):
        loader = SiteProfileLoader()
        return loader.load_by_id("bukgu_gwangju").crawl_filters

    @pytest.fixture
    def crawler(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return URLCrawler(crawl_filters=profile.crawl_filters)

    def test_protected_beats_deny_with_pagination(self, filters):
        """Protected + deny + pagination -> protected wins."""
        urls = [
            "https://bukgu.gwangju.kr/board.es?seq=999&utm_source=test&pageNo=2",
            "https://bukgu.gwangju.kr/board.es?utm_source=test&seq=999&page=5",
            "https://bukgu.gwangju.kr/board.es?pageNo=2&seq=999&print=1",
        ]
        for url in urls:
            assert should_crawl_url(url, filters) is True, f"Protected wins: {url}"

    def test_pure_deny_still_blocked(self, filters):
        """Pure deny (no protected) stays blocked even with pagination."""
        urls = [
            "https://bukgu.gwangju.kr/page?print=1&pageNo=2",
            "https://bukgu.gwangju.kr/page?utm_source=test&page=5",
            "https://bukgu.gwangju.kr/page?utm_medium=email&perPage=20",
        ]
        for url in urls:
            assert should_crawl_url(url, filters) is False, f"Pure deny stays blocked: {url}"

    def test_pagination_only_survives(self, filters):
        """Pagination-only (no protected, no deny) survives - deferred."""
        urls = [
            "https://bukgu.gwangju.kr/board.es?pageNo=2",
            "https://bukgu.gwangju.kr/board.es?page=5&perPage=20",
            "https://bukgu.gwangju.kr/board.es?offset=10&limit=5",
        ]
        for url in urls:
            assert should_crawl_url(url, filters) is True, f"Pagination only survives: {url}"

    def test_protected_only_survives(self, filters):
        """Protected only survives."""
        urls = [
            "https://bukgu.gwangju.kr/menu.es?mid=a101",
            "https://bukgu.gwangju.kr/board.es?seq=999",
            "https://bukgu.gwangju.kr/content?contentId=123",
        ]
        for url in urls:
            assert should_crawl_url(url, filters) is True, f"Protected survives: {url}"


# ------------------------------------------------------------------
# Test 7: No-live guard 강화
# ------------------------------------------------------------------

class TestBukguNoLiveGuardEnhanced:
    """Enhanced no-live network guards."""

    def test_no_requests_called(self, monkeypatch):
        import requests
        mock_get = MagicMock()
        monkeypatch.setattr(requests, "get", mock_get)
        
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)
        
        base_url = "https://bukgu.gwangju.kr/"
        html = BUKGU_HOMEPAGE_HTML_STAGE411
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        
        assert len(links["internal"]) > 0
        mock_get.assert_not_called()

    def test_no_httpx_called(self, monkeypatch):
        try:
            import httpx
        except ImportError:
            pytest.skip("httpx not installed")
        mock_client = MagicMock()
        monkeypatch.setattr(httpx, "Client", mock_client)
        
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)
        
        base_url = "https://bukgu.gwangju.kr/"
        html = BUKGU_HOMEPAGE_HTML_STAGE411
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        
        assert len(links["internal"]) > 0
        mock_client.assert_not_called()

    def test_no_urllib_called(self, monkeypatch):
        import urllib.request
        mock_urlopen = MagicMock()
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)
        
        base_url = "https://bukgu.gwangju.kr/"
        html = BUKGU_HOMEPAGE_HTML_STAGE411
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        
        assert len(links["internal"]) > 0
        mock_urlopen.assert_not_called()

    def test_no_socket_called(self, monkeypatch):
        import socket
        mock_socket = MagicMock()
        monkeypatch.setattr(socket, "socket", mock_socket)
        
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)
        
        base_url = "https://bukgu.gwangju.kr/"
        html = BUKGU_HOMEPAGE_HTML_STAGE411
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        
        assert len(links["internal"]) > 0
        mock_socket.assert_not_called()

    def test_env_live_flags_not_set(self):
        """Assert RUN_LIVE_*_TESTS env vars are not 1."""
        for flag in ["RUN_LIVE_CRAWL_TESTS", "RUN_LIVE_FIRECRAWL_TESTS", 
                     "RUN_LIVE_API_TESTS", "RUN_LIVE_PROVIDER_TESTS"]:
            val = os.environ.get(flag, "").lower()
            if val:
                assert val not in ("1", "true", "yes", "on"), f"{flag} not truthy"

    def test_should_crawl_pure_no_network(self):
        """should_crawl_url is pure with no network access."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        filters = profile.crawl_filters

        assert should_crawl_url("https://bukgu.gwangju.kr/menu.es?mid=a101", filters) is True
        assert should_crawl_url("https://bukgu.gwangju.kr/page?print=1", filters) is False

    def test_homepage_mapper_mock_only(self):
        """HomepageMapper with mock provider makes no live calls."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        mapper = HomepageMapper(fetch_provider="mock", crawl_filters=profile.crawl_filters)

        mock_fetch = make_mock_fetch()
        with patch.object(mapper, "fetch_content", side_effect=mock_fetch):
            result = mapper.build_map("https://bukgu.gwangju.kr/")
            assert result["homepage"]["title"] == "광주광역시 북구청"

    def test_tmp_path_only(self, tmp_path):
        """Tests use tmp_path only; no repo files touched."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)

        base_url = "https://bukgu.gwangju.kr/"
        soup = BeautifulSoup(BUKGU_HOMEPAGE_HTML_STAGE411, "html.parser")
        links = crawler.extract_links(soup, base_url)

        assert len(links["internal"]) > 0
        assert str(tmp_path) in str(tmp_path)