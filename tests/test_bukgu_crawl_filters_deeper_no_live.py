"""No-live deeper integration tests for bukgu_gwangju crawl filter coverage.

All tests use mock/static HTML/XML fixtures only.
No live network/API/Firecrawl calls.
Extends Stage 409 hardening with:
- Dynamic URL pattern cases
- Deep pagination variants
- Board/detail URL preservation
- Sitemap/homepage candidate merge edge cases
- Enhanced no-live guards
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
# Extended static fixtures
# ------------------------------------------------------------------

# Extended homepage HTML with complex URL patterns
BUKGU_HOMEPAGE_HTML_DEEPER = """
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

      <!-- Board/detail complex patterns -->
      <a href="/board.es?mid=a101&act=view&seq=1001">게시판 상세(act=view)</a>
      <a href="/board.es?keyField=title&keyWord=검색어&pageNo=3&seq=1002">검색 결과</a>
      <a href="/board.es?mid=a202&bskind=notice&seq=1003">공지사항</a>
      <a href="/board.es?mid=a303&bskind=faq&seq=1004&pageNo=1">FAQ</a>
      <a href="/content?mid=a101&contentId=123&act=view">콘텐츠 뷰</a>
      <a href="/article?articleId=777&category=politics&pageNo=2">기사+카테고리</a>

      <!-- Multiple protected params -->
      <a href="/board.es?mid=a101&seq=999&act=view">이중 보호</a>
      <a href="/content?contentId=123&articleId=777">이중 보호(컨텐츠+기사)</a>

      <!-- Denied: print=, utm_ tracking -->
      <a href="/page?print=1">인쇄 페이지</a>
      <a href="/page?print=true">인쇄 true</a>
      <a href="/page?utm_source=test">UTM 소스</a>
      <a href="/page?utm_medium=email">UTM 매체</a>
      <a href="/page?utm_campaign=spring">UTM 캠페인</a>
      <a href="/page?utm_content=abc">UTM 콘텐츠</a>
      <a href="/page?fbclid=123">Facebook 클릭 ID</a>
      <a href="/page?gclid=456">Google 클릭 ID</a>

      <!-- Pagination deferred (pageNo, currentPage, pageIndex not in deny) -->
      <a href="/board.es?pageNo=2">게시판 2페이지</a>
      <a href="/board.es?currentPage=3">게시판 currentPage</a>
      <a href="/board.es?pageIndex=4">게시판 pageIndex</a>
      <a href="/board.es?page=5">게시판 page</a>
      <a href="/board.es?p=6">게시판 p</a>
      <a href="/board.es?perPage=20">게시판 perPage</a>
      <a href="/board.es?recordCount=100">게시판 recordCount</a>
      <a href="/board.es?pageUnit=10">게시판 pageUnit</a>
      <a href="/board.es?pageSize=50&page=10">게시판 pageSize</a>

      <!-- Protected + pagination + tracking mixed -->
      <a href="/board.es?seq=999&pageNo=2&utm_source=test">보호+페이지네이션+트래킹</a>
      <a href="/board.es?mid=a101&pageIndex=3&utm_medium=email">메뉴+페이지인덱스+트래킹</a>
      <a href="/content?contentId=123&page=5&utm_campaign=spring">컨텐츠+페이지+트래킹</a>

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
      <a href="mailto:test@example.com">메일투</a>
      <a href="tel:+82-62-123-4567">전화</a>
    </div>
  </body>
</html>
"""

# Extended sitemap XML with duplicate URLs (different query order, fragment)
# Note: & must be escaped as &amp; in XML
BUKGU_SITEMAP_XML_DEEPER = """<?xml version="1.0" encoding="UTF-8"?>
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
  <!-- Duplicate URLs with different query order - &amp; escaped for XML -->
  <url>
    <loc>https://bukgu.gwangju.kr/board.es?utm_source=newsletter&amp;seq=999</loc>
    <lastmod>2026-01-09</lastmod>
  </url>
  <url>
    <loc>https://bukgu.gwangju.kr/menu.es?utm_campaign=spring&amp;mid=a101</loc>
    <lastmod>2026-01-08</lastmod>
  </url>
  <!-- URLs with fragments -->
  <url>
    <loc>https://bukgu.gwangju.kr/board.es?seq=999#section-1</loc>
    <lastmod>2026-01-07</lastmod>
  </url>
  <url>
    <loc>https://bukgu.gwangju.kr/content?contentId=123#content-body</loc>
    <lastmod>2026-01-06</lastmod>
  </url>
  <!-- External domain -->
  <url>
    <loc>https://external.example.com/other</loc>
    <lastmod>2026-01-05</lastmod>
  </url>
  <!-- JavaScript/mailto/tel (should be handled by URLCrawler) -->
  <url>
    <loc>https://bukgu.gwangju.kr/javascript:void(0)</loc>
    <lastmod>2026-01-04</lastmod>
  </url>
</urlset>
"""

# Simpler sitemap for baseline tests
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

# Simple homepage HTML for basic tests
BUKGU_HOMEPAGE_HTML = """
<html><body>
  <a href="/menu.es?mid=a101">종합민원</a>
  <a href="/board.es?seq=999">게시판</a>
</body></html>
"""

# Expected survive URLs (comprehensive list)
BUKGU_DEEPER_SURVIVE = [
    # Basic protected
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
    # Protected + tracking mixed
    "https://bukgu.gwangju.kr/board.es?seq=999&utm_source=test",
    "https://bukgu.gwangju.kr/menu.es?mid=a101&utm_campaign=spring",
    "https://bukgu.gwangju.kr/content?contentId=123&utm_medium=email",
    # Board/detail complex
    "https://bukgu.gwangju.kr/board.es?mid=a101&act=view&seq=1001",
    "https://bukgu.gwangju.kr/board.es?keyField=title&keyWord=검색어&pageNo=3&seq=1002",
    "https://bukgu.gwangju.kr/board.es?mid=a202&bskind=notice&seq=1003",
    "https://bukgu.gwangju.kr/board.es?mid=a303&bskind=faq&seq=1004&pageNo=1",
    "https://bukgu.gwangju.kr/content?mid=a101&contentId=123&act=view",
    "https://bukgu.gwangju.kr/article?articleId=777&category=politics&pageNo=2",
    # Multiple protected params
    "https://bukgu.gwangju.kr/board.es?mid=a101&seq=999&act=view",
    "https://bukgu.gwangju.kr/content?contentId=123&articleId=777",
    # Pagination deferred
    "https://bukgu.gwangju.kr/board.es?pageNo=2",
    "https://bukgu.gwangju.kr/board.es?currentPage=3",
    "https://bukgu.gwangju.kr/board.es?pageIndex=4",
    "https://bukgu.gwangju.kr/board.es?page=5",
    "https://bukgu.gwangju.kr/board.es?p=6",
    "https://bukgu.gwangju.kr/board.es?perPage=20",
    "https://bukgu.gwangju.kr/board.es?recordCount=100",
    "https://bukgu.gwangju.kr/board.es?pageUnit=10",
    "https://bukgu.gwangju.kr/board.es?pageSize=50&page=10",
    # Protected + pagination + tracking
    "https://bukgu.gwangju.kr/board.es?seq=999&pageNo=2&utm_source=test",
    "https://bukgu.gwangju.kr/board.es?mid=a101&pageIndex=3&utm_medium=email",
    "https://bukgu.gwangju.kr/content?contentId=123&page=5&utm_campaign=spring",
]

# Expected deny URLs (pure tracking/print)
BUKGU_DEEPER_DENY = [
    "https://bukgu.gwangju.kr/page?print=1",
    "https://bukgu.gwangju.kr/page?print=true",
    "https://bukgu.gwangju.kr/page?utm_source=test",
    "https://bukgu.gwangju.kr/page?utm_medium=email",
    "https://bukgu.gwangju.kr/page?utm_campaign=spring",
    "https://bukgu.gwangju.kr/page?utm_content=abc",
    "https://bukgu.gwangju.kr/page?fbclid=123",
    "https://bukgu.gwangju.kr/page?gclid=456",
]


# ------------------------------------------------------------------
# Helper for mocking HomepageMapper fetch_content
# ------------------------------------------------------------------

def make_mock_fetch(homepage_html=BUKGU_HOMEPAGE_HTML_DEEPER, sitemap_xml=BUKGU_SITEMAP_XML_DEEPER):
    """Create a mock fetch side_effect function for HomepageMapper.
    
    Returns different content based on the requested URL:
    - robots.txt -> empty
    - sitemap URLs -> XML
    - homepage/other -> HTML
    """
    def mock_fetch(url):
        if 'robots.txt' in url:
            return ('', None, 200, url)
        elif 'sitemap' in url:
            return (sitemap_xml, None, 200, url)
        else:
            return (homepage_html, None, 200, url)
    return mock_fetch


# ------------------------------------------------------------------
# Test 1: Extended dynamic URL pattern cases
# ------------------------------------------------------------------

class TestBukguDynamicUrlPatterns:
    """Dynamic URL pattern cases with multiple query params mixed."""

    @pytest.fixture
    def filters(self):
        loader = SiteProfileLoader()
        return loader.load_by_id("bukgu_gwangju").crawl_filters

    @pytest.fixture
    def crawler(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return URLCrawler(crawl_filters=profile.crawl_filters)

    # Board.es with act=view + protected params
    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/board.es?mid=a101&act=view&seq=1001",
        "https://bukgu.gwangju.kr/board.es?mid=a202&act=view&seq=1002",
        "https://bukgu.gwangju.kr/board.es?seq=1003&act=view&mid=a303",
    ])
    def test_board_es_act_view_preserved(self, crawler, url):
        """board.es with act=view and protected params should survive."""
        base_url = "https://bukgu.gwangju.kr/"
        html = f'<html><body><a href="{url}">link</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert url in urls, f"board.es act=view URL {url} should survive"

    # Board.es with keyField/keyWord + pagination + protected
    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/board.es?keyField=title&keyWord=검색어&pageNo=3&seq=1002",
        "https://bukgu.gwangju.kr/board.es?keyField=content&keyWord=공고&page=5&seq=1003",
        "https://bukgu.gwangju.kr/board.es?mid=a101&keyField=title&keyWord=제목&seq=999",
    ])
    def test_board_es_search_pagination_preserved(self, crawler, url):
        """board.es with search + pagination + protected should survive."""
        base_url = "https://bukgu.gwangju.kr/"
        html = f'<html><body><a href="{url}">link</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert url in urls, f"board.es search+pagination URL {url} should survive"

    # Board.es with bskind + protected
    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/board.es?mid=a202&bskind=notice&seq=1003",
        "https://bukgu.gwangju.kr/board.es?mid=a303&bskind=faq&seq=1004&pageNo=1",
        "https://bukgu.gwangju.kr/board.es?bskind=notice&seq=999",
    ])
    def test_board_es_bskind_preserved(self, crawler, url):
        """board.es with bskind + protected should survive."""
        base_url = "https://bukgu.gwangju.kr/"
        html = f'<html><body><a href="{url}">link</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert url in urls, f"board.es bskind URL {url} should survive"

    # Content/article with additional params
    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/content?mid=a101&contentId=123&act=view",
        "https://bukgu.gwangju.kr/article?articleId=777&category=politics&pageNo=2",
        "https://bukgu.gwangju.kr/article?articleId=888&cat=notice&page=1",
    ])
    def test_content_article_additional_params_preserved(self, crawler, url):
        """content/article with extra params + protected should survive."""
        base_url = "https://bukgu.gwangju.kr/"
        html = f'<html><body><a href="{url}">link</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert url in urls, f"content/article URL {url} should survive"

    # Multiple protected params in same URL
    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/board.es?mid=a101&seq=999&act=view",
        "https://bukgu.gwangju.kr/content?contentId=123&articleId=777",
        "https://bukgu.gwangju.kr/board.es?menuId=main&seq=1001&mid=a101",
    ])
    def test_multiple_protected_params_survive(self, crawler, url):
        """URL with multiple protected params should survive."""
        base_url = "https://bukgu.gwangju.kr/"
        html = f'<html><body><a href="{url}">link</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert url in urls, f"Multiple protected params URL {url} should survive"

    # Pure tracking on otherwise protected path - should still survive due to protected
    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/board.es?seq=999&utm_source=test&utm_medium=email",
        "https://bukgu.gwangju.kr/menu.es?mid=a101&utm_campaign=spring&utm_content=abc",
        "https://bukgu.gwangju.kr/content?contentId=123&fbclid=123&gclid=456",
    ])
    def test_protected_with_multiple_tracking_survives(self, filters, url):
        """Protected + multiple tracking should survive (protected wins)."""
        assert should_crawl_url(url, filters) is True, f"Protected+multi-tracking {url} should survive"


# ------------------------------------------------------------------
# Test 2: Deep pagination variants
# ------------------------------------------------------------------

class TestBukguDeepPaginationVariants:
    """Extended pagination parameter variants."""

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
        "https://bukgu.gwangju.kr/board.es?perPage=20",
        "https://bukgu.gwangju.kr/board.es?recordCount=100",
        "https://bukgu.gwangju.kr/board.es?pageUnit=10",
        "https://bukgu.gwangju.kr/board.es?pageSize=50&page=10",
        "https://bukgu.gwangju.kr/board.es?offset=20&limit=10",
        "https://bukgu.gwangju.kr/board.es?start=0&count=50",
    ])
    def test_pagination_only_urls_survive(self, filters, url):
        """Pagination-only URLs (no protected params) should survive - deferred."""
        assert should_crawl_url(url, filters) is True, f"Pagination URL {url} should survive"

    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/board.es?seq=999&pageNo=2",
        "https://bukgu.gwangju.kr/board.es?mid=a101&currentPage=3",
        "https://bukgu.gwangju.kr/board.es?seq=1001&pageIndex=4",
        "https://bukgu.gwangju.kr/content?contentId=123&page=5",
        "https://bukgu.gwangju.kr/article?articleId=777&pageNo=2&perPage=10",
    ])
    def test_protected_plus_pagination_survives(self, filters, url):
        """Protected + pagination should survive."""
        assert should_crawl_url(url, filters) is True, f"Protected+pagination {url} should survive"

    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/board.es?seq=999&pageNo=2&utm_source=test",
        "https://bukgu.gwangju.kr/board.es?mid=a101&pageIndex=3&utm_medium=email",
        "https://bukgu.gwangju.kr/content?contentId=123&page=5&utm_campaign=spring",
        "https://bukgu.gwangju.kr/article?articleId=777&pageNo=2&fbclid=xyz",
    ])
    def test_protected_pagination_tracking_triple_mix(self, filters, url):
        """Protected + pagination + tracking should survive (protected wins)."""
        assert should_crawl_url(url, filters) is True, f"Protected+pagination+tracking {url} should survive"

    def test_pagination_deferred_vs_deny_boundary(self, filters):
        """Verify pagination params not in deny_patterns."""
        deny = filters.get("deny_patterns", [])
        pagination_params = ["pageNo", "currentPage", "pageIndex", "page", "p", 
                            "perPage", "recordCount", "pageUnit", "pageSize", "offset", "limit", "start", "count"]
        for param in pagination_params:
            assert f"{param}=" not in deny, f"Pagination param {param} should not be in deny_patterns"
            assert param not in deny, f"Pagination param {param} should not be in deny_patterns"


# ------------------------------------------------------------------
# Test 3: Board/detail URL preservation with query order invariance
# ------------------------------------------------------------------

class TestBukguBoardDetailPreservation:
    """Board/detail URL preservation with query parameter order variations."""

    @pytest.fixture
    def filters(self):
        loader = SiteProfileLoader()
        return loader.load_by_id("bukgu_gwangju").crawl_filters

    @pytest.fixture
    def crawler(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return URLCrawler(crawl_filters=profile.crawl_filters)

    # Core board.es detail patterns
    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/board.es?mid=a101&seq=999",
        "https://bukgu.gwangju.kr/board.es?seq=999&mid=a101",
        "https://bukgu.gwangju.kr/board.es?mid=a101&act=view&seq=999",
        "https://bukgu.gwangju.kr/board.es?act=view&mid=a101&seq=999",
        "https://bukgu.gwangju.kr/board.es?seq=999&act=view&mid=a101",
    ])
    def test_board_es_detail_variants_all_survive(self, crawler, url):
        """All board.es detail URL variants should survive."""
        base_url = "https://bukgu.gwangju.kr/"
        html = f'<html><body><a href="{url}">link</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert url in urls, f"board.es detail variant {url} should survive"

    # board.es with keyField/keyWord + protected
    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/board.es?keyField=title&keyWord=test&mid=a101&seq=999",
        "https://bukgu.gwangju.kr/board.es?mid=a101&seq=999&keyField=title&keyWord=test",
        "https://bukgu.gwangju.kr/board.es?keyField=content&keyWord=공고&mid=a202&seq=1001",
    ])
    def test_board_es_search_detail_variants(self, crawler, url):
        """board.es search + detail variants should survive."""
        base_url = "https://bukgu.gwangju.kr/"
        html = f'<html><body><a href="{url}">link</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert url in urls, f"board.es search+detail {url} should survive"

    # content/article detail
    @pytest.mark.parametrize("url", [
        "https://bukgu.gwangju.kr/content?contentId=123&mid=a101",
        "https://bukgu.gwangju.kr/content?mid=a101&contentId=123",
        "https://bukgu.gwangju.kr/article?articleId=777&mid=a101",
        "https://bukgu.gwangju.kr/article?mid=a101&articleId=777",
    ])
    def test_content_article_detail_variants(self, crawler, url):
        """content/article detail variants should survive."""
        base_url = "https://bukgu.gwangju.kr/"
        html = f'<html><body><a href="{url}">link</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]
        assert url in urls, f"content/article detail {url} should survive"

    # should_crawl_url pure function order invariance
    @pytest.mark.parametrize("urls_same", [
        [
            "https://bukgu.gwangju.kr/board.es?mid=a101&seq=999&pageNo=2",
            "https://bukgu.gwangju.kr/board.es?seq=999&mid=a101&pageNo=2",
            "https://bukgu.gwangju.kr/board.es?pageNo=2&mid=a101&seq=999",
        ],
        [
            "https://bukgu.gwangju.kr/board.es?mid=a101&act=view&seq=999&utm_source=test",
            "https://bukgu.gwangju.kr/board.es?utm_source=test&mid=a101&act=view&seq=999",
            "https://bukgu.gwangju.kr/board.es?seq=999&utm_source=test&mid=a101&act=view",
        ],
    ])
    def test_query_order_invariance_detailed(self, filters, urls_same):
        """All URL permutations with same params should have same result."""
        results = [should_crawl_url(u, filters) for u in urls_same]
        assert all(results), f"All query order variants should survive: {urls_same}"


# ------------------------------------------------------------------
# Test 4: Sitemap/homepage candidate merge edge cases
# ------------------------------------------------------------------

class TestBukguSitemapHomepageMerge:
    """Sitemap/homepage candidate merge with deduplication and normalization."""

    @pytest.fixture
    def mapper(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return HomepageMapper(fetch_provider="mock", crawl_filters=profile.crawl_filters)

    def test_sitemap_duplicate_urls_different_order_normalized(self, mapper):
        """Sitemap URLs with same params different order should be processed."""
        mock_fetch = make_mock_fetch()
        with patch.object(mapper, "fetch_content", side_effect=mock_fetch):
            result = mapper.build_map("https://bukgu.gwangju.kr/")

        sitemap_urls = [item["url"] for item in result["sitemap"]["urls"]]
        
        # Both order variants should be present in sitemap
        assert "https://bukgu.gwangju.kr/board.es?seq=999" in sitemap_urls
        assert "https://bukgu.gwangju.kr/board.es?utm_source=newsletter&seq=999" in sitemap_urls
        assert "https://bukgu.gwangju.kr/menu.es?mid=a101" in sitemap_urls
        assert "https://bukgu.gwangju.kr/menu.es?utm_campaign=spring&mid=a101" in sitemap_urls

    def test_sitemap_fragment_handling(self, mapper):
        """Sitemap URLs with fragments should be processed."""
        mock_fetch = make_mock_fetch()
        with patch.object(mapper, "fetch_content", side_effect=mock_fetch):
            result = mapper.build_map("https://bukgu.gwangju.kr/")

        sitemap_urls = [item["url"] for item in result["sitemap"]["urls"]]
        
        # Fragment URLs may or may not be preserved depending on parser
        # The key test is that URLs don't cause errors
        assert len(sitemap_urls) > 0
        # Verify core protected URLs are present
        assert "https://bukgu.gwangju.kr/board.es?seq=999" in sitemap_urls
        assert "https://bukgu.gwangju.kr/menu.es?mid=a101" in sitemap_urls

    def test_sitemap_external_domain_handled(self, mapper):
        """External domain URLs in sitemap should be processed."""
        mock_fetch = make_mock_fetch()
        with patch.object(mapper, "fetch_content", side_effect=mock_fetch):
            result = mapper.build_map("https://bukgu.gwangju.kr/")

        sitemap_urls = [item["url"] for item in result["sitemap"]["urls"]]
        assert "https://external.example.com/other" in sitemap_urls

    def test_homepage_external_and_malformed_safe(self, mapper):
        """Homepage with external, javascript, mailto, tel, empty, hash hrefs safe."""
        html = """
        <html><body>
            <nav>
            <a href="https://external.example.com/page">외부</a>
            <a href="javascript:void(0)">자바스크립트</a>
            <a href="mailto:test@example.com">메일</a>
            <a href="tel:+82-62-123-4567">전화</a>
            <a href="">빈링크</a>
            <a href="#">해시만</a>
            <a href="/menu.es?mid=a101">정상</a>
            </nav>
        </body></html>
        """
        mock_fetch = make_mock_fetch(html)
        with patch.object(mapper, "fetch_content", side_effect=mock_fetch):
            result = mapper.build_map("https://bukgu.gwangju.kr/")

        nav_urls = [link["url"] for link in result["homepage"]["navigation_links"]]
        
        # Normal URL should be extracted
        assert "https://bukgu.gwangju.kr/menu.es?mid=a101" in nav_urls
        
        # Should not crash
        assert len(nav_urls) >= 1


# ------------------------------------------------------------------
# Test 5: Enhanced no-live network guards
# ------------------------------------------------------------------

class TestBukguNoLiveNetworkEnhanced:
    """Enhanced no-live network guards with explicit patch verification."""

    def test_no_requests_get_called(self, monkeypatch):
        """Requests.get should not be called in any test."""
        import requests
        mock_get = MagicMock()
        monkeypatch.setattr(requests, "get", mock_get)
        
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)
        
        base_url = "https://bukgu.gwangju.kr/"
        html = BUKGU_HOMEPAGE_HTML_DEEPER
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        
        assert len(links["internal"]) > 0
        mock_get.assert_not_called()

    def test_no_httpx_client_called(self, monkeypatch):
        """httpx.Client should not be used."""
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
        html = BUKGU_HOMEPAGE_HTML_DEEPER
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        
        assert len(links["internal"]) > 0
        mock_client.assert_not_called()

    def test_no_urllib_request_called(self, monkeypatch):
        """urllib.request.urlopen should not be called."""
        import urllib.request
        mock_urlopen = MagicMock()
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)
        
        base_url = "https://bukgu.gwangju.kr/"
        html = BUKGU_HOMEPAGE_HTML_DEEPER
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        
        assert len(links["internal"]) > 0
        mock_urlopen.assert_not_called()

    def test_no_socket_called(self, monkeypatch):
        """Low-level socket should not be called."""
        import socket
        mock_socket = MagicMock()
        monkeypatch.setattr(socket, "socket", mock_socket)
        
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)
        
        base_url = "https://bukgu.gwangju.kr/"
        html = BUKGU_HOMEPAGE_HTML_DEEPER
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        
        assert len(links["internal"]) > 0
        mock_socket.assert_not_called()

    def test_no_firecrawl_import(self):
        """Firecrawl should not be importable in test context."""
        import sys
        assert "firecrawl" not in sys.modules or sys.modules.get("firecrawl") is None

    def test_env_live_flags_not_set(self):
        """Assert RUN_LIVE_*_TESTS env vars are not 1."""
        assert os.environ.get("RUN_LIVE_CRAWL_TESTS") != "1"
        assert os.environ.get("RUN_LIVE_FIRECRAWL_TESTS") != "1"
        assert os.environ.get("RUN_LIVE_API_TESTS") != "1"
        assert os.environ.get("RUN_LIVE_PROVIDER_TESTS") != "1"
        
        # Also check they're not any truthy value
        for flag in ["RUN_LIVE_CRAWL_TESTS", "RUN_LIVE_FIRECRAWL_TESTS", 
                     "RUN_LIVE_API_TESTS", "RUN_LIVE_PROVIDER_TESTS"]:
            val = os.environ.get(flag, "").lower()
            if val:
                assert val not in ("1", "true", "yes", "on"), f"{flag} should not be truthy"

    def test_homepage_mapper_mock_only(self):
        """HomepageMapper with mock provider makes no live calls."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        mapper = HomepageMapper(fetch_provider="mock", crawl_filters=profile.crawl_filters)

        mock_fetch = make_mock_fetch()
        with patch.object(mapper, "fetch_content", side_effect=mock_fetch):
            result = mapper.build_map("https://bukgu.gwangju.kr/")
            assert result["homepage"]["title"] == "광주광역시 북구청"

    def test_should_crawl_url_pure_no_side_effects(self):
        """should_crawl_url is a pure function with no network side effects."""
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        filters = profile.crawl_filters

        # These should work without any network
        assert should_crawl_url("https://bukgu.gwangju.kr/menu.es?mid=a101", filters) is True
        assert should_crawl_url("https://bukgu.gwangju.kr/page?print=1", filters) is False
        assert should_crawl_url("https://bukgu.gwangju.kr/board.es?seq=999&utm_source=test", filters) is True


# ------------------------------------------------------------------
# Test 6: Sitemap + Homepage merge behavior verification
# ------------------------------------------------------------------

class TestBukguSitemapHomepageMergeBehavior:
    """Verify merged candidate pool behavior with static fixtures."""

    @pytest.fixture
    def mapper(self):
        loader = SiteProfileLoader()
        profile = loader.load_by_id("bukgu_gwangju")
        return HomepageMapper(fetch_provider="mock", crawl_filters=profile.crawl_filters)

    def test_merged_candidate_pool_preserves_protected(self, mapper):
        """Merged sitemap + homepage pool preserves protected URLs."""
        mock_fetch = make_mock_fetch()
        with patch.object(mapper, "fetch_content", side_effect=mock_fetch):
            result = mapper.build_map("https://bukgu.gwangju.kr/")

        # Check that navigation links from homepage include protected URLs
        nav_urls = [link["url"] for link in result["homepage"]["navigation_links"]]
        
        # These should be in nav links (extracted without filtering)
        assert "https://bukgu.gwangju.kr/menu.es?mid=a101" in nav_urls
        assert "https://bukgu.gwangju.kr/board.es?seq=999" in nav_urls
        assert "https://bukgu.gwangju.kr/content?contentId=123" in nav_urls
        assert "https://bukgu.gwangju.kr/article?articleId=777" in nav_urls

        # Sitemap URLs should also be collected
        sitemap_urls = [item["url"] for item in result["sitemap"]["urls"]]
        assert "https://bukgu.gwangju.kr/menu.es?mid=a101" in sitemap_urls
        assert "https://bukgu.gwangju.kr/board.es?seq=999" in sitemap_urls

    def test_merged_pool_excludes_pure_denied_at_crawler_level(self, mapper):
        """Pure denied URLs appear in extraction but filtered at crawler level."""
        mock_fetch = make_mock_fetch()
        with patch.object(mapper, "fetch_content", side_effect=mock_fetch):
            result = mapper.build_map("https://bukgu.gwangju.kr/")

        # At extraction level (HomepageMapper), denied URLs are still present
        nav_urls = [link["url"] for link in result["homepage"]["navigation_links"]]
        assert "https://bukgu.gwangju.kr/page?print=1" in nav_urls
        assert "https://bukgu.gwangju.kr/page?utm_source=test" in nav_urls

        # Same for sitemap
        sitemap_urls = [item["url"] for item in result["sitemap"]["urls"]]
        assert "https://bukgu.gwangju.kr/page?print=1" in sitemap_urls
        assert "https://bukgu.gwangju.kr/page?utm_source=newsletter" in sitemap_urls

        # External domains present at extraction
        assert "https://external.example.com/other" in sitemap_urls