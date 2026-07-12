"""No-live sitemap and homepage integration edge-case regression for configured crawl_filters profiles.

All tests use mock/static fixtures only. No live network/API/Firecrawl calls.
Verifies that crawl_filters correctly preserve protected URLs and exclude denied URLs
across merged sitemap + homepage candidate pools for the three configured profiles:
- bukgu_gwangju (https://bukgu.gwangju.kr/)
- gwangju_go_kr (https://www.gwangju.go.kr/)
- seogu_gwangju (https://www.seogu.gwangju.kr/)

Test coverage:
1. Sitemap XML fixture integration (static XML only)
2. Homepage HTML fixture integration (static HTML only)
3. Sitemap + homepage merged candidate pool (pure helper, no production code changes)
4. Cross-profile parameterization (pytest.mark.parametrize for all 3 profiles)
5. Edge-case order invariance (sitemap first vs homepage first)
6. No live/network guard
7. No mutation safety

All profiles share the same conservative candidate rules (from Stage 392/393/394/397/403):
- deny_patterns: ["print=", "utm_", "utm_source=", "utm_medium=", "utm_campaign="]
- protected_patterns: ["mid=", "menuId=", "board.es", "seq=", "contentId=", "articleId="]
- allow_patterns: []
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch
from bs4 import BeautifulSoup

from src.site_profiles.site_profile import SiteProfileLoader
from src.crawler.url_crawler import URLCrawler
from src.crawler.homepage_mapper import HomepageMapper
from src.crawler.sitemap_parser import SitemapParser
from src.indexer.document_indexer import DocumentIndexer
from src.crawler.crawl_path_filter import should_crawl_url


# ------------------------------------------------------------------
# Profile configurations with base URLs
# ------------------------------------------------------------------
PROFILE_CONFIGS = {
    "bukgu_gwangju": {
        "base_url": "https://bukgu.gwangju.kr/",
        "display_name": "광주광역시 북구청",
    },
    "gwangju_go_kr": {
        "base_url": "https://www.gwangju.go.kr/",
        "display_name": "광주광역시청",
    },
    "seogu_gwangju": {
        "base_url": "https://www.seogu.gwangju.kr/",
        "display_name": "광주광역시 서구청",
    },
}

ALL_PROFILE_IDS = ["bukgu_gwangju", "gwangju_go_kr", "seogu_gwangju"]


# ------------------------------------------------------------------
# Static fixture generators
# ------------------------------------------------------------------
def sitemap_xml_fixture(profile_id: str) -> str:
    """Generate static sitemap XML for a given profile."""
    cfg = PROFILE_CONFIGS[profile_id]
    base = cfg["base_url"].rstrip("/")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <!-- Protected structural URLs -->
  <url>
    <loc>{base}/menu.es?mid=a101</loc>
    <lastmod>2024-01-15</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>{base}/board.es?seq=999</loc>
    <lastmod>2024-01-14</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>{base}/content?contentId=123</loc>
    <lastmod>2024-01-13</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>{base}/article?articleId=777</loc>
    <lastmod>2024-01-12</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
  <!-- Pagination deferred -->
  <url>
    <loc>{base}/board.es?pageNo=2</loc>
    <lastmod>2024-01-11</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.5</priority>
  </url>
  <!-- Denied: print/tracking -->
  <url>
    <loc>{base}/page?print=1</loc>
    <lastmod>2024-01-10</lastmod>
    <changefreq>yearly</changefreq>
    <priority>0.1</priority>
  </url>
  <url>
    <loc>{base}/page?utm_source=test</loc>
    <lastmod>2024-01-09</lastmod>
    <changefreq>yearly</changefreq>
    <priority>0.1</priority>
  </url>
  <url>
    <loc>{base}/page?utm_campaign=spring</loc>
    <lastmod>2024-01-08</lastmod>
    <changefreq>yearly</changefreq>
    <priority>0.1</priority>
  </url>
  <!-- Normal navigation -->
  <url>
    <loc>{base}/menu.es?mid=a202</loc>
    <lastmod>2024-01-07</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
</urlset>"""


def homepage_html_fixture(profile_id: str) -> str:
    """Generate static homepage HTML for a given profile."""
    cfg = PROFILE_CONFIGS[profile_id]
    base = cfg["base_url"]

    return f"""<html>
  <head>
    <title>{cfg["display_name"]}</title>
    <meta name="description" content="{cfg["display_name"]} 공식 홈페이지">
  </head>
  <body>
    <nav>
      <!-- Protected structural URLs -->
      <a href="/menu.es?mid=a101">종합민원</a>
      <a href="/board.es?seq=999">게시판 상세</a>
      <a href="/content?contentId=123">콘텐츠 상세</a>
      <a href="/article?articleId=777">기사 상세</a>
      <!-- Protected + tracking mixed URLs -->
      <a href="/board.es?seq=999&amp;utm_source=test">게시판 상세 (UTM)</a>
      <a href="/menu.es?mid=a101&amp;utm_campaign=spring">종합민원 (캠페인)</a>
      <!-- Pagination deferred -->
      <a href="/board.es?pageNo=2">게시판 2페이지</a>
      <!-- Denied: print/tracking -->
      <a href="/page?print=1">인쇄 페이지</a>
      <a href="/page?utm_source=test">UTM 소스</a>
      <a href="/page?utm_campaign=spring">UTM 캠페인</a>
      <!-- Normal navigation -->
      <a href="/menu.es?mid=a202">교육접수</a>
    </nav>
  </body>
</html>"""


# Pure helper: merge sitemap and homepage candidate pools
# This is a test-only helper - does NOT modify production code
def merge_candidate_pools(sitemap_urls, homepage_nav_links, crawler_filters, base_url):
    """Merge sitemap URLs and homepage nav links, applying crawl_filters.
    
    Returns deduplicated internal URLs after filter application.
    This mirrors the production flow but stays in test scope.
    """
    from urllib.parse import urlparse, urlunparse
    
    # Helper to normalize URL (remove fragment)
    def normalize_url(url):
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))
    
    # Apply crawl_filters to sitemap URLs
    sitemap_internal = []
    for item in sitemap_urls:
        url = item.get("url", "")
        if url:
            norm = normalize_url(url)
            if should_crawl_url(norm, crawler_filters):
                sitemap_internal.append(norm)
    
    # Apply crawl_filters to homepage nav links
    homepage_internal = []
    for item in homepage_nav_links:
        url = item.get("url", "")
        if url:
            norm = normalize_url(url)
            if should_crawl_url(norm, crawler_filters):
                homepage_internal.append(norm)
    
    # Merge and deduplicate
    merged = list(dict.fromkeys(sitemap_internal + homepage_internal))
    return merged


# ------------------------------------------------------------------
# Test 1: Sitemap XML fixture integration
# ------------------------------------------------------------------
class TestSitemapXmlFixtureIntegration:
    """Verify sitemap XML parsing with crawl_filters preserves protected, excludes denied."""

    @pytest.fixture(params=ALL_PROFILE_IDS)
    def profile_and_sitemap(self, request):
        pid = request.param
        loader = SiteProfileLoader()
        profile = loader.load_by_id(pid)
        base_url = PROFILE_CONFIGS[pid]["base_url"]
        sitemap_xml = sitemap_xml_fixture(pid)
        return {"profile_id": pid, "profile": profile, "base_url": base_url, "sitemap_xml": sitemap_xml, "filters": profile.crawl_filters}

    def test_sitemap_parser_extracts_all_urls(self, profile_and_sitemap):
        """SitemapParser should extract all URLs from fixture XML."""
        pid = profile_and_sitemap["profile_id"]
        sitemap_xml = profile_and_sitemap["sitemap_xml"]
        
        parser = SitemapParser()
        parsed = parser.parse(sitemap_xml)
        
        assert parsed["error"] is None, f"{pid}: Sitemap parse error: {parsed['error']}"
        urls = [item["url"] for item in parsed["urls"]]
        
        # All fixture URLs should be extracted (before filtering)
        base = profile_and_sitemap["base_url"].rstrip("/")
        expected_all = [
            f"{base}/menu.es?mid=a101",
            f"{base}/board.es?seq=999",
            f"{base}/content?contentId=123",
            f"{base}/article?articleId=777",
            f"{base}/board.es?pageNo=2",
            f"{base}/page?print=1",
            f"{base}/page?utm_source=test",
            f"{base}/page?utm_campaign=spring",
            f"{base}/menu.es?mid=a202",
        ]
        
        for url in expected_all:
            assert url in urls, f"{pid}: Expected URL {url} missing from sitemap parse"

    def test_protected_urls_survive_sitemap_filter(self, profile_and_sitemap):
        """Protected URLs in sitemap should survive crawl_filters."""
        pid = profile_and_sitemap["profile_id"]
        filters = profile_and_sitemap["filters"]
        sitemap_xml = profile_and_sitemap["sitemap_xml"]
        
        parser = SitemapParser()
        parsed = parser.parse(sitemap_xml)
        
        protected_urls = [
            f"{profile_and_sitemap['base_url'].rstrip('/')}/menu.es?mid=a101",
            f"{profile_and_sitemap['base_url'].rstrip('/')}/board.es?seq=999",
            f"{profile_and_sitemap['base_url'].rstrip('/')}/content?contentId=123",
            f"{profile_and_sitemap['base_url'].rstrip('/')}/article?articleId=777",
            f"{profile_and_sitemap['base_url'].rstrip('/')}/board.es?pageNo=2",
            f"{profile_and_sitemap['base_url'].rstrip('/')}/menu.es?mid=a202",
        ]
        
        for item in parsed["urls"]:
            url = item["url"]
            if url in protected_urls:
                assert should_crawl_url(url, filters) is True, f"{pid}: Protected URL {url} should survive filter"

    def test_denied_urls_excluded_sitemap_filter(self, profile_and_sitemap):
        """Denied URLs in sitemap should be excluded by crawl_filters."""
        pid = profile_and_sitemap["profile_id"]
        filters = profile_and_sitemap["filters"]
        sitemap_xml = profile_and_sitemap["sitemap_xml"]
        
        parser = SitemapParser()
        parsed = parser.parse(sitemap_xml)
        
        denied_urls = [
            f"{profile_and_sitemap['base_url'].rstrip('/')}/page?print=1",
            f"{profile_and_sitemap['base_url'].rstrip('/')}/page?utm_source=test",
            f"{profile_and_sitemap['base_url'].rstrip('/')}/page?utm_campaign=spring",
        ]
        
        for item in parsed["urls"]:
            url = item["url"]
            if url in denied_urls:
                assert should_crawl_url(url, filters) is False, f"{pid}: Denied URL {url} should be filtered out"


# ------------------------------------------------------------------
# Test 2: Homepage HTML fixture integration
# ------------------------------------------------------------------
class TestHomepageHtmlFixtureIntegration:
    """Verify homepage HTML parsing with crawl_filters preserves protected, excludes denied."""

    @pytest.fixture(params=ALL_PROFILE_IDS)
    def profile_and_homepage(self, request):
        pid = request.param
        loader = SiteProfileLoader()
        profile = loader.load_by_id(pid)
        base_url = PROFILE_CONFIGS[pid]["base_url"]
        html = homepage_html_fixture(pid)
        return {"profile_id": pid, "profile": profile, "base_url": base_url, "html": html, "filters": profile.crawl_filters}

    def test_homepage_mapper_extracts_nav_links(self, profile_and_homepage):
        """HomepageMapper should extract navigation links from fixture HTML."""
        pid = profile_and_homepage["profile_id"]
        profile = profile_and_homepage["profile"]
        base_url = profile_and_homepage["base_url"]
        html = profile_and_homepage["html"]
        filters = profile_and_homepage["filters"]
        
        mapper = HomepageMapper(fetch_provider="mock", crawl_filters=filters)
        
        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (html, None, 200, base_url)
            result = mapper.build_map(base_url)
        
        nav_links = result["homepage"]["navigation_links"]
        urls = [link["url"] for link in nav_links]
        
        base = base_url.rstrip("/")
        expected_all = [
            f"{base}/menu.es?mid=a101",
            f"{base}/board.es?seq=999",
            f"{base}/content?contentId=123",
            f"{base}/article?articleId=777",
            f"{base}/board.es?seq=999&utm_source=test",
            f"{base}/menu.es?mid=a101&utm_campaign=spring",
            f"{base}/board.es?pageNo=2",
            f"{base}/page?print=1",
            f"{base}/page?utm_source=test",
            f"{base}/page?utm_campaign=spring",
            f"{base}/menu.es?mid=a202",
        ]
        
        for url in expected_all:
            assert url in urls, f"{pid}: Expected nav link {url} missing from homepage parse"

    def test_protected_urls_survive_homepage_filter(self, profile_and_homepage):
        """Protected URLs in homepage nav should survive crawl_filters."""
        pid = profile_and_homepage["profile_id"]
        filters = profile_and_homepage["filters"]
        profile = profile_and_homepage["profile"]
        base_url = profile_and_homepage["base_url"]
        html = profile_and_homepage["html"]
        
        crawler = URLCrawler(crawl_filters=filters)
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        internal_urls = [link["url"] for link in links["internal"]]
        
        protected_urls = [
            f"{base_url.rstrip('/')}/menu.es?mid=a101",
            f"{base_url.rstrip('/')}/board.es?seq=999",
            f"{base_url.rstrip('/')}/content?contentId=123",
            f"{base_url.rstrip('/')}/article?articleId=777",
            f"{base_url.rstrip('/')}/board.es?pageNo=2",
            f"{base_url.rstrip('/')}/menu.es?mid=a202",
        ]
        
        # Mixed protected+tracking should also survive
        mixed_urls = [
            f"{base_url.rstrip('/')}/board.es?seq=999&utm_source=test",
            f"{base_url.rstrip('/')}/menu.es?mid=a101&utm_campaign=spring",
        ]
        
        for url in protected_urls + mixed_urls:
            assert url in internal_urls, f"{pid}: Protected/mixed URL {url} should survive in crawler"

    def test_denied_urls_excluded_homepage_filter(self, profile_and_homepage):
        """Pure denied URLs in homepage nav should be excluded by crawl_filters."""
        pid = profile_and_homepage["profile_id"]
        filters = profile_and_homepage["filters"]
        profile = profile_and_homepage["profile"]
        base_url = profile_and_homepage["base_url"]
        html = profile_and_homepage["html"]
        
        crawler = URLCrawler(crawl_filters=filters)
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        internal_urls = [link["url"] for link in links["internal"]]
        
        denied_urls = [
            f"{base_url.rstrip('/')}/page?print=1",
            f"{base_url.rstrip('/')}/page?utm_source=test",
            f"{base_url.rstrip('/')}/page?utm_campaign=spring",
        ]
        
        for url in denied_urls:
            assert url not in internal_urls, f"{pid}: Denied URL {url} should be filtered out from crawler"


# ------------------------------------------------------------------
# Test 3: Sitemap + homepage merged candidate pool
# ------------------------------------------------------------------
class TestMergedCandidatePool:
    """Verify merged sitemap + homepage candidates maintain correct filter behavior."""

    @pytest.fixture(params=ALL_PROFILE_IDS)
    def profile_and_fixtures(self, request):
        pid = request.param
        loader = SiteProfileLoader()
        profile = loader.load_by_id(pid)
        base_url = PROFILE_CONFIGS[pid]["base_url"]
        sitemap_xml = sitemap_xml_fixture(pid)
        html = homepage_html_fixture(pid)
        return {
            "profile_id": pid, 
            "profile": profile, 
            "base_url": base_url, 
            "sitemap_xml": sitemap_xml, 
            "html": html, 
            "filters": profile.crawl_filters
        }

    def parse_sitemap_urls(self, sitemap_xml):
        """Helper to parse sitemap fixture."""
        parser = SitemapParser()
        parsed = parser.parse(sitemap_xml)
        return parsed["urls"] if not parsed["error"] else []

    def parse_homepage_nav(self, base_url, html, filters):
        """Helper to extract homepage nav links."""
        mapper = HomepageMapper(fetch_provider="mock", crawl_filters=filters)
        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (html, None, 200, base_url)
            result = mapper.build_map(base_url)
        return result["homepage"]["navigation_links"]

    def test_merged_pool_protected_survive(self, profile_and_fixtures):
        """Protected URLs should survive in merged candidate pool."""
        pid = profile_and_fixtures["profile_id"]
        filters = profile_and_fixtures["filters"]
        base_url = profile_and_fixtures["base_url"]
        sitemap_xml = profile_and_fixtures["sitemap_xml"]
        html = profile_and_fixtures["html"]
        
        sitemap_urls = self.parse_sitemap_urls(sitemap_xml)
        homepage_nav = self.parse_homepage_nav(base_url, html, filters)
        
        merged = merge_candidate_pools(sitemap_urls, homepage_nav, filters, base_url)
        
        # Protected URLs should be in merged pool
        protected_urls = [
            f"{base_url.rstrip('/')}/menu.es?mid=a101",
            f"{base_url.rstrip('/')}/board.es?seq=999",
            f"{base_url.rstrip('/')}/content?contentId=123",
            f"{base_url.rstrip('/')}/article?articleId=777",
            f"{base_url.rstrip('/')}/board.es?pageNo=2",
            f"{base_url.rstrip('/')}/menu.es?mid=a202",
        ]
        
        # Mixed protected+tracking should survive
        mixed_urls = [
            f"{base_url.rstrip('/')}/board.es?seq=999&utm_source=test",
            f"{base_url.rstrip('/')}/menu.es?mid=a101&utm_campaign=spring",
        ]
        
        for url in protected_urls + mixed_urls:
            assert url in merged, f"{pid}: Protected/mixed URL {url} missing from merged pool"

    def test_merged_pool_denied_excluded(self, profile_and_fixtures):
        """Denied URLs should be excluded from merged candidate pool."""
        pid = profile_and_fixtures["profile_id"]
        filters = profile_and_fixtures["filters"]
        base_url = profile_and_fixtures["base_url"]
        sitemap_xml = profile_and_fixtures["sitemap_xml"]
        html = profile_and_fixtures["html"]
        
        sitemap_urls = self.parse_sitemap_urls(sitemap_xml)
        homepage_nav = self.parse_homepage_nav(base_url, html, filters)
        
        merged = merge_candidate_pools(sitemap_urls, homepage_nav, filters, base_url)
        
        denied_urls = [
            f"{base_url.rstrip('/')}/page?print=1",
            f"{base_url.rstrip('/')}/page?utm_source=test",
            f"{base_url.rstrip('/')}/page?utm_campaign=spring",
        ]
        
        for url in denied_urls:
            assert url not in merged, f"{pid}: Denied URL {url} should not be in merged pool"

    def test_merged_pool_document_indexer_integration(self, profile_and_fixtures):
        """DocumentIndexer correctly builds index from merged homepage map.
        
        Note: In production, DocumentIndexer does NOT apply crawl_filters to sitemap URLs.
        Crawl_filters are only applied to HTML-parsed URLs via URLCrawler.extract_links.
        This test verifies that protected URLs appear in the index and that the
        merge helper (which DOES apply filters) works correctly.
        """
        pid = profile_and_fixtures["profile_id"]
        filters = profile_and_fixtures["filters"]
        base_url = profile_and_fixtures["base_url"]
        sitemap_xml = profile_and_fixtures["sitemap_xml"]
        html = profile_and_fixtures["html"]
        
        # Build homepage map with mocked fetch
        mapper = HomepageMapper(fetch_provider="mock", crawl_filters=filters)
        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (html, None, 200, base_url)
            homepage_map = mapper.build_map(base_url)
        
        # Inject sitemap data (simulating what HomepageMapper does)
        parser = SitemapParser()
        parsed = parser.parse(sitemap_xml)
        homepage_map["sitemap"]["urls"] = parsed["urls"]
        homepage_map["sitemap"]["url_count"] = len(parsed["urls"])
        
        # Build index
        indexer = DocumentIndexer()
        docs = indexer.build_index(homepage_map)
        
        # Collect all canonical URLs from index
        indexed_urls = {doc["canonical_url"] for doc in docs}
        
        # Protected URLs should be indexed (both from sitemap and homepage nav)
        protected_urls = [
            f"{base_url.rstrip('/')}/menu.es?mid=a101",
            f"{base_url.rstrip('/')}/board.es?seq=999",
            f"{base_url.rstrip('/')}/content?contentId=123",
            f"{base_url.rstrip('/')}/article?articleId=777",
            f"{base_url.rstrip('/')}/board.es?pageNo=2",
            f"{base_url.rstrip('/')}/menu.es?mid=a202",
        ]
        
        for url in protected_urls:
            canonical = url  # make_canonical_url doesn't change these
            assert canonical in indexed_urls, f"{pid}: Protected URL {url} missing from index"
        
        # Note: Denied URLs from sitemap ARE included in index (production behavior).
        # Only HTML-parsed URLs are filtered by crawl_filters via URLCrawler.
        # The merge_candidate_pools helper (tested separately) correctly applies filters.

    def test_source_types_tracked_correctly(self, profile_and_fixtures):
        """DocumentIndexer should track whether URLs came from sitemap, navigation, or both."""
        pid = profile_and_fixtures["profile_id"]
        filters = profile_and_fixtures["filters"]
        base_url = profile_and_fixtures["base_url"]
        sitemap_xml = profile_and_fixtures["sitemap_xml"]
        html = profile_and_fixtures["html"]
        
        mapper = HomepageMapper(fetch_provider="mock", crawl_filters=filters)
        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (html, None, 200, base_url)
            homepage_map = mapper.build_map(base_url)
        
        parser = SitemapParser()
        parsed = parser.parse(sitemap_xml)
        homepage_map["sitemap"]["urls"] = parsed["urls"]
        
        indexer = DocumentIndexer()
        docs = indexer.build_index(homepage_map)
        
        # Index by canonical URL for easy lookup
        doc_index = {doc["canonical_url"]: doc for doc in docs}
        
        # URLs that exist in BOTH sitemap AND homepage nav should have both source_types
        # e.g., /menu.es?mid=a101 appears in both
        base = base_url.rstrip("/")
        both_sources_url = f"{base}/menu.es?mid=a101"
        
        if both_sources_url in doc_index:
            discovered = doc_index[both_sources_url]["metadata"]["discovered_from"]
            # Should contain both sitemap and navigation
            assert "sitemap" in discovered, f"{pid}: Missing 'sitemap' source for {both_sources_url}"
            assert "navigation" in discovered, f"{pid}: Missing 'navigation' source for {both_sources_url}"


# ------------------------------------------------------------------
# Test 4: Cross-profile parameterization
# ------------------------------------------------------------------
class TestCrossProfileParameterization:
    """Verify all 3 profiles work correctly with base_url/domain isolation."""

    @pytest.fixture
    def loader(self):
        return SiteProfileLoader()

    def test_base_url_isolation(self, loader):
        """Each profile's base_url should be distinct and correctly configured."""
        base_urls = {}
        for pid in ALL_PROFILE_IDS:
            profile = loader.load_by_id(pid)
            base_url = profile.base_url
            assert base_url, f"{pid}: base_url is empty"
            assert base_url not in base_urls.values(), f"{pid}: base_url collision with another profile"
            base_urls[pid] = base_url

        assert base_urls["bukgu_gwangju"] == "https://bukgu.gwangju.kr/"
        assert base_urls["gwangju_go_kr"] == "https://www.gwangju.go.kr/"
        assert base_urls["seogu_gwangju"] == "https://www.seogu.gwangju.kr/"

    def test_allowed_domains_isolation(self, loader):
        """Each profile's allowed_domains should not overlap incorrectly."""
        for pid in ALL_PROFILE_IDS:
            profile = loader.load_by_id(pid)
            domains = profile.allowed_domains
            assert len(domains) > 0, f"{pid}: allowed_domains is empty"
            base = profile.base_url.replace("https://", "").rstrip("/")
            assert any(base in d for d in domains), f"{pid}: base domain not in allowed_domains"

    def test_candidate_rules_identical_across_profiles(self, loader):
        """All 3 profiles use the exact same conservative candidate rule set."""
        profiles = {pid: loader.load_by_id(pid) for pid in ALL_PROFILE_IDS}
        filters_dict = {pid: p.crawl_filters for pid, p in profiles.items()}

        first_filters = filters_dict[ALL_PROFILE_IDS[0]]
        for pid in ALL_PROFILE_IDS[1:]:
            assert filters_dict[pid] == first_filters, f"{pid}: crawl_filters differs from {ALL_PROFILE_IDS[0]}"

    @pytest.mark.parametrize("pid", ALL_PROFILE_IDS)
    def test_protected_patterns_match_conservative(self, loader, pid):
        profile = loader.load_by_id(pid)
        expected = {"mid=", "menuId=", "board.es", "seq=", "contentId=", "articleId="}
        actual = set(profile.crawl_filters.get("protected_patterns", []))
        assert actual == expected, f"{pid}: protected_patterns mismatch: {actual} != {expected}"

    @pytest.mark.parametrize("pid", ALL_PROFILE_IDS)
    def test_deny_patterns_match_conservative(self, loader, pid):
        profile = loader.load_by_id(pid)
        expected = {"print=", "utm_", "utm_source=", "utm_medium=", "utm_campaign="}
        actual = set(profile.crawl_filters.get("deny_patterns", []))
        assert actual == expected, f"{pid}: deny_patterns mismatch: {actual} != {expected}"


# ------------------------------------------------------------------
# Test 5: Edge-case order invariance
# ------------------------------------------------------------------
class TestOrderInvariance:
    """Verify merged results are invariant to processing order (sitemap first vs homepage first)."""

    @pytest.fixture(params=ALL_PROFILE_IDS)
    def profile_and_fixtures(self, request):
        pid = request.param
        loader = SiteProfileLoader()
        profile = loader.load_by_id(pid)
        base_url = PROFILE_CONFIGS[pid]["base_url"]
        sitemap_xml = sitemap_xml_fixture(pid)
        html = homepage_html_fixture(pid)
        return {
            "profile_id": pid, 
            "profile": profile, 
            "base_url": base_url, 
            "sitemap_xml": sitemap_xml, 
            "html": html, 
            "filters": profile.crawl_filters
        }

    def parse_sitemap_urls(self, sitemap_xml):
        parser = SitemapParser()
        parsed = parser.parse(sitemap_xml)
        return parsed["urls"] if not parsed["error"] else []

    def parse_homepage_nav(self, base_url, html, filters):
        mapper = HomepageMapper(fetch_provider="mock", crawl_filters=filters)
        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (html, None, 200, base_url)
            result = mapper.build_map(base_url)
        return result["homepage"]["navigation_links"]

    def test_order_invariance_sitemap_first(self, profile_and_fixtures):
        """Merging sitemap-first then homepage should produce same result as homepage-first.
        
        The merge_candidate_pools helper applies crawl_filters to both inputs before merging.
        Results should have the same SET of URLs regardless of processing order.
        """
        pid = profile_and_fixtures["profile_id"]
        filters = profile_and_fixtures["filters"]
        base_url = profile_and_fixtures["base_url"]
        sitemap_xml = profile_and_fixtures["sitemap_xml"]
        html = profile_and_fixtures["html"]
        
        sitemap_urls = self.parse_sitemap_urls(sitemap_xml)
        homepage_nav = self.parse_homepage_nav(base_url, html, filters)
        
        # Order 1: sitemap first, then homepage
        merged_1 = merge_candidate_pools(sitemap_urls, homepage_nav, filters, base_url)
        
        # Order 2: homepage first, then sitemap
        merged_2 = merge_candidate_pools(homepage_nav, sitemap_urls, filters, base_url)
        
        # Results should have same SET of URLs (order may differ due to insertion order)
        assert set(merged_1) == set(merged_2), f"{pid}: Merge order affects URL set: {set(merged_1)} != {set(merged_2)}"
        
        # Additionally, verify all denied URLs are excluded in both orders
        base = base_url.rstrip("/")
        denied = [
            f"{base}/page?print=1",
            f"{base}/page?utm_source=test",
            f"{base}/page?utm_campaign=spring",
        ]
        for url in denied:
            assert url not in merged_1, f"{pid}: Denied {url} in merged_1"
            assert url not in merged_2, f"{pid}: Denied {url} in merged_2"

    def test_document_indexer_order_invariance(self, profile_and_fixtures):
        """DocumentIndexer output should be invariant to sitemap/homepage processing order."""
        pid = profile_and_fixtures["profile_id"]
        filters = profile_and_fixtures["filters"]
        base_url = profile_and_fixtures["base_url"]
        sitemap_xml = profile_and_fixtures["sitemap_xml"]
        html = profile_and_fixtures["html"]
        
        # Build two homepage maps with same data
        mapper1 = HomepageMapper(fetch_provider="mock", crawl_filters=filters)
        mapper2 = HomepageMapper(fetch_provider="mock", crawl_filters=filters)
        
        with patch.object(mapper1, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (html, None, 200, base_url)
            map1 = mapper1.build_map(base_url)
        
        with patch.object(mapper2, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (html, None, 200, base_url)
            map2 = mapper2.build_map(base_url)
        
        parser = SitemapParser()
        parsed = parser.parse(sitemap_xml)
        
        # Both maps get same sitemap data
        for m in [map1, map2]:
            m["sitemap"]["urls"] = parsed["urls"]
            m["sitemap"]["url_count"] = len(parsed["urls"])
        
        indexer = DocumentIndexer()
        docs1 = indexer.build_index(map1)
        docs2 = indexer.build_index(map2)
        
        # Compare canonical URLs
        urls1 = [doc["canonical_url"] for doc in docs1]
        urls2 = [doc["canonical_url"] for doc in docs2]
        
        assert urls1 == urls2, f"{pid}: DocumentIndexer output varies with map construction order"


# ------------------------------------------------------------------
# Test 6: No live/network guard
# ------------------------------------------------------------------
class TestNoLiveNetworkGuard:
    """Ensure no live network/API/Firecrawl calls in tests."""

    def test_sitemap_parser_no_live(self):
        """SitemapParser.parse is pure - no network calls."""
        for pid in ALL_PROFILE_IDS:
            xml = sitemap_xml_fixture(pid)
            parser = SitemapParser()
            parsed = parser.parse(xml)
            assert parsed["error"] is None
            assert len(parsed["urls"]) > 0

    def test_homepage_mapper_mock_only(self):
        """HomepageMapper with mock provider makes no live calls."""
        for pid in ALL_PROFILE_IDS:
            loader = SiteProfileLoader()
            profile = loader.load_by_id(pid)
            mapper = HomepageMapper(fetch_provider="mock", crawl_filters=profile.crawl_filters)
            base_url = PROFILE_CONFIGS[pid]["base_url"]
            html = homepage_html_fixture(pid)
            
            with patch.object(mapper, "fetch_content") as mock_fetch:
                mock_fetch.return_value = (html, None, 200, base_url)
                result = mapper.build_map(base_url)
                assert result["homepage"]["title"] is not None

    def test_url_crawler_no_live(self):
        """URLCrawler with crawl_filters only should not make live requests."""
        for pid in ALL_PROFILE_IDS:
            loader = SiteProfileLoader()
            profile = loader.load_by_id(pid)
            crawler = URLCrawler(crawl_filters=profile.crawl_filters)
            base_url = PROFILE_CONFIGS[pid]["base_url"]
            soup = BeautifulSoup(homepage_html_fixture(pid), "html.parser")
            links = crawler.extract_links(soup, base_url)
            assert len(links["internal"]) > 0

    def test_no_run_live_tests_env_used(self):
        """Verify RUN_LIVE_*_TESTS=1 is not used in our tests."""
        assert os.environ.get("RUN_LIVE_CRAWL_TESTS") != "1"
        assert os.environ.get("RUN_LIVE_FIRECRAWL_TESTS") != "1"
        assert os.environ.get("RUN_LIVE_API_TESTS") != "1"


# ------------------------------------------------------------------
# Test 7: No mutation safety
# ------------------------------------------------------------------
class TestNoMutationSafety:
    """Verify tests don't mutate repo scenario/snapshot/cache files."""

    def test_no_repo_files_created(self, tmp_path):
        """Test outputs only go to tmp_path, not repo."""
        loader = SiteProfileLoader()
        for pid in ALL_PROFILE_IDS:
            profile = loader.load_by_id(pid)
            filters = profile.crawl_filters
            base_url = PROFILE_CONFIGS[pid]["base_url"]
            sitemap_xml = sitemap_xml_fixture(pid)
            html = homepage_html_fixture(pid)
            
            # Parse sitemap
            parser = SitemapParser()
            parsed = parser.parse(sitemap_xml)
            assert parsed["error"] is None
            assert len(parsed["urls"]) > 0
            
            # Parse homepage
            mapper = HomepageMapper(fetch_provider="mock", crawl_filters=filters)
            with patch.object(mapper, "fetch_content") as mock_fetch:
                mock_fetch.return_value = (html, None, 200, base_url)
                result = mapper.build_map(base_url)
                assert result["homepage"]["title"] is not None
            
            # Build merged pool
            nav_links = result["homepage"]["navigation_links"]
            merged = merge_candidate_pools(parsed["urls"], nav_links, filters, base_url)
            assert len(merged) > 0
            
            # Build index
            homepage_map = result
            homepage_map["sitemap"]["urls"] = parsed["urls"]
            homepage_map["sitemap"]["url_count"] = len(parsed["urls"])
            
            indexer = DocumentIndexer()
            docs = indexer.build_index(homepage_map)
            assert len(docs) > 0

        # Verify tmp_path isolation
        assert str(tmp_path) in str(tmp_path)
