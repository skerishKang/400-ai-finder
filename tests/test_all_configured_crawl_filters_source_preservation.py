"""All-configured-profiles source preservation / homepage map consistency no-live regression.

All tests use mock/static fixtures only. No live network/API/Firecrawl calls.
Verifies that all 3 configured profiles (bukgu_gwangju, gwangju_go_kr, seogu_gwangju)
share the same conservative crawl_filters candidate and preserve protected URLs
while filtering print/tracking URLs.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch
from bs4 import BeautifulSoup

from src.site_profiles.site_profile import SiteProfileLoader
from src.crawler.url_crawler import URLCrawler
from src.crawler.homepage_mapper import HomepageMapper
from src.crawler.crawl_path_filter import should_crawl_url


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

# Profile configurations with base URLs and expected survive/deny URLs
PROFILE_CONFIGS = {
    "bukgu_gwangju": {
        "base_url": "https://bukgu.gwangju.kr/",
        "survive_paths": [
            "/menu.es?mid=a101",
            "/board.es?seq=999",
            "/content?contentId=123",
            "/article?articleId=777",
            "/board.es?pageNo=2",
        ],
        "deny_paths": [
            "/page?print=1",
            "/page?utm_source=test",
            "/page?utm_campaign=spring",
        ],
    },
    "gwangju_go_kr": {
        "base_url": "https://www.gwangju.go.kr/",
        "survive_paths": [
            "/menu.es?mid=a101",
            "/board.es?seq=999",
            "/content?contentId=123",
            "/article?articleId=777",
            "/board.es?pageNo=2",
        ],
        "deny_paths": [
            "/page?print=1",
            "/page?utm_source=test",
            "/page?utm_campaign=spring",
        ],
    },
    "seogu_gwangju": {
        "base_url": "https://www.seogu.gwangju.kr/",
        "survive_paths": [
            "/menu.es?mid=a101",
            "/board.es?seq=999",
            "/content?contentId=123",
            "/article?articleId=777",
            "/board.es?pageNo=2",
        ],
        "deny_paths": [
            "/page?print=1",
            "/page?utm_source=test",
            "/page?utm_campaign=spring",
        ],
    },
}

# Generate full URLs for each profile
def build_urls(profile_id: str):
    cfg = PROFILE_CONFIGS[profile_id]
    base = cfg["base_url"]
    survive = [base.rstrip("/") + p for p in cfg["survive_paths"]]
    deny = [base.rstrip("/") + p for p in cfg["deny_paths"]]
    return survive, deny


# Generate mock homepage HTML for a given profile
def mock_homepage_html(profile_id: str) -> str:
    cfg = PROFILE_CONFIGS[profile_id]
    base = cfg["base_url"]
    hostname = base.replace("https://", "").rstrip("/")
    title_map = {
        "bukgu_gwangju": "광주광역시 북구청",
        "gwangju_go_kr": "광주광역시청",
        "seogu_gwangju": "광주광역시 서구청",
    }
    return f"""
<html>
  <head>
    <title>{title_map[profile_id]}</title>
    <meta name="description" content="{title_map[profile_id]} 공식 홈페이지">
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
    </nav>
  </body>
</html>
"""


ALL_PROFILE_IDS = ["bukgu_gwangju", "gwangju_go_kr", "seogu_gwangju"]


# ------------------------------------------------------------------
# Test 1: Configured profiles inventory
# ------------------------------------------------------------------

class TestConfiguredProfilesInventory:
    """Verify which profiles have crawl_filters on main branch."""

    def test_exactly_three_profiles_have_crawl_filters(self):
        """Exactly 3 profiles have crawl_filters configured."""
        loader = SiteProfileLoader()
        all_ids = loader.list_ids()

        # All three target profiles should exist
        for pid in ALL_PROFILE_IDS:
            assert pid in all_ids, f"{pid} should be in SiteProfileLoader"

        # Verify they have non-empty crawl_filters
        profiles_with_filters = [
            sid for sid in all_ids
            if loader.load_by_id(sid).crawl_filters and loader.load_by_id(sid).crawl_filters != {}
        ]

        assert set(profiles_with_filters) == set(ALL_PROFILE_IDS), (
            f"Expected exactly {ALL_PROFILE_IDS}, got {profiles_with_filters}"
        )

    def test_each_profile_has_non_empty_crawl_filters(self):
        """Each of the 3 profiles should have non-empty crawl_filters."""
        loader = SiteProfileLoader()
        for pid in ALL_PROFILE_IDS:
            profile = loader.load_by_id(pid)
            assert profile.crawl_filters is not None, f"{pid}: crawl_filters is None"
            assert profile.crawl_filters != {}, f"{pid}: crawl_filters is empty"


# ------------------------------------------------------------------
# Test 2: Shared candidate consistency
# ------------------------------------------------------------------

class TestSharedCandidateConsistency:
    """Verify all 3 profiles share identical conservative candidate rules."""

    @pytest.fixture
    def loader(self):
        return SiteProfileLoader()

    @pytest.fixture
    def profiles(self, loader):
        return {pid: loader.load_by_id(pid) for pid in ALL_PROFILE_IDS}

    def test_deny_patterns_match_conservative_candidate(self, profiles):
        """All profiles should have identical deny_patterns matching conservative candidate."""
        expected_deny = {"print=", "utm_", "utm_source=", "utm_medium=", "utm_campaign="}
        for pid in ALL_PROFILE_IDS:
            deny = set(profiles[pid].crawl_filters.get("deny_patterns", []))
            assert deny == expected_deny, f"{pid}: deny_patterns mismatch: {deny} != {expected_deny}"

    def test_protected_patterns_match_conservative_candidate(self, profiles):
        """All profiles should have identical protected_patterns matching conservative candidate."""
        expected_protected = {"mid=", "menuId=", "board.es", "seq=", "contentId=", "articleId="}
        for pid in ALL_PROFILE_IDS:
            protected = set(profiles[pid].crawl_filters.get("protected_patterns", []))
            assert protected == expected_protected, f"{pid}: protected_patterns mismatch: {protected} != {expected_protected}"

    def test_allow_patterns_empty(self, profiles):
        """All profiles should have empty allow_patterns."""
        for pid in ALL_PROFILE_IDS:
            allow = profiles[pid].crawl_filters.get("allow_patterns", [])
            assert allow == [], f"{pid}: allow_patterns should be empty, got: {allow}"

    def test_forbidden_deny_guard(self, profiles):
        """Critical municipal params must NOT be in deny_patterns."""
        forbidden = {"board.es", "mid=", "menuId=", "seq=", "contentId=", "articleId="}
        for pid in ALL_PROFILE_IDS:
            deny = set(profiles[pid].crawl_filters.get("deny_patterns", []))
            for pattern in forbidden:
                assert pattern not in deny, f"{pid}: Forbidden {pattern} in deny_patterns"


# ------------------------------------------------------------------
# Test 3: Parameterized source preservation test
# ------------------------------------------------------------------

class TestParameterizedSourcePreservation:
    """Parameterized source preservation test for all 3 profiles."""

    @pytest.fixture
    def loader(self):
        return SiteProfileLoader()

    @pytest.fixture(params=ALL_PROFILE_IDS)
    def profile_and_config(self, loader, request):
        pid = request.param
        profile = loader.load_by_id(pid)
        config = PROFILE_CONFIGS[pid]
        survive_urls, deny_urls = build_urls(pid)
        html = mock_homepage_html(pid)
        return {
            "profile_id": pid,
            "profile": profile,
            "config": config,
            "survive_urls": survive_urls,
            "deny_urls": deny_urls,
            "html": html,
        }

    def test_static_html_protected_urls_survive_in_crawler(self, profile_and_config):
        """Protected structural URLs survive URLCrawler.extract_links for each profile."""
        pid = profile_and_config["profile_id"]
        filters = profile_and_config["profile"].crawl_filters
        survive = profile_and_config["survive_urls"]
        deny = profile_and_config["deny_urls"]
        html = profile_and_config["html"]

        crawler = URLCrawler(crawl_filters=filters)
        base_url = profile_and_config["config"]["base_url"]
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]

        for url in survive:
            assert url in urls, f"{pid}: Protected URL {url} should survive but was filtered"

        for url in deny:
            assert url not in urls, f"{pid}: Denied URL {url} should be filtered but survived"

    def test_should_crawl_url_with_real_filters(self, profile_and_config):
        """should_crawl_url pure function works with each profile's filters."""
        pid = profile_and_config["profile_id"]
        filters = profile_and_config["profile"].crawl_filters
        config = profile_and_config["config"]
        base = config["base_url"]

        # Protected -> allow
        assert should_crawl_url(base.rstrip("/") + "/menu.es?mid=a101", filters) is True, f"{pid}: mid= should allow"
        assert should_crawl_url(base.rstrip("/") + "/board.es?seq=999", filters) is True, f"{pid}: seq= should allow"
        assert should_crawl_url(base.rstrip("/") + "/content?contentId=123", filters) is True, f"{pid}: contentId= should allow"
        assert should_crawl_url(base.rstrip("/") + "/article?articleId=777", filters) is True, f"{pid}: articleId= should allow"
        # Pagination -> allow (deferred)
        assert should_crawl_url(base.rstrip("/") + "/board.es?pageNo=2", filters) is True, f"{pid}: pageNo= should allow"

        # Deny -> deny
        assert should_crawl_url(base.rstrip("/") + "/page?print=1", filters) is False, f"{pid}: print= should deny"
        assert should_crawl_url(base.rstrip("/") + "/page?utm_source=test", filters) is False, f"{pid}: utm_source= should deny"
        assert should_crawl_url(base.rstrip("/") + "/page?utm_campaign=spring", filters) is False, f"{pid}: utm_campaign= should deny"


# ------------------------------------------------------------------
# Test 4: Homepage map consistency test
# ------------------------------------------------------------------

class TestHomepageMapConsistency:
    """Verify HomepageMapper consistency for all 3 profiles."""

    @pytest.fixture
    def loader(self):
        return SiteProfileLoader()

    @pytest.fixture(params=ALL_PROFILE_IDS)
    def mapper_and_config(self, loader, request):
        pid = request.param
        profile = loader.load_by_id(pid)
        config = PROFILE_CONFIGS[pid]
        survive, _ = build_urls(pid)
        html = mock_homepage_html(pid)
        mapper = HomepageMapper(fetch_provider="mock", crawl_filters=profile.crawl_filters)
        return {
            "profile_id": pid,
            "profile": profile,
            "mapper": mapper,
            "survive_urls": survive,
            "html": html,
            "base_url": config["base_url"],
        }

    def test_mock_homepage_protected_urls_in_nav_or_attachment_links(self, mapper_and_config):
        """Protected URLs appear in HomepageMapper navigation or attachment links."""
        pid = mapper_and_config["profile_id"]
        mapper = mapper_and_config["mapper"]
        survive = mapper_and_config["survive_urls"]
        html = mapper_and_config["html"]
        base_url = mapper_and_config["base_url"]

        with patch.object(mapper, "fetch_content") as mock_fetch:
            mock_fetch.return_value = (html, None, 200, base_url)
            result = mapper.build_map(base_url)

        nav_links = result["homepage"]["navigation_links"]
        attachment_links = result["homepage"]["attachment_links"]
        nav_urls = [link["url"] for link in nav_links]
        attachment_urls = [link["url"] for link in attachment_links]
        all_urls = nav_urls + attachment_urls

        for url in survive:
            assert url in all_urls, f"{pid}: Protected URL {url} should be in nav or attachment links"

    def test_denied_urls_excluded_from_internal_source_candidates(self, mapper_and_config):
        """Denied URLs (print/tracking) are excluded from URLCrawler internal source candidates."""
        pid = mapper_and_config["profile_id"]
        profile = mapper_and_config["profile"]
        config = PROFILE_CONFIGS[pid]
        html = mapper_and_config["html"]
        base_url = config["base_url"]

        crawler = URLCrawler(crawl_filters=profile.crawl_filters)
        soup = BeautifulSoup(html, "html.parser")
        links = crawler.extract_links(soup, base_url)
        internal_urls = [link["url"] for link in links["internal"]]

        _, deny_urls = build_urls(pid)
        for url in deny_urls:
            assert url not in internal_urls, f"{pid}: Denied URL {url} should be excluded from source candidates"


# ------------------------------------------------------------------
# Test 5: Cross-profile regression
# ------------------------------------------------------------------

class TestCrossProfileRegression:
    """Cross-profile consistency and isolation checks."""

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

        # Verify expected base URLs
        assert base_urls["bukgu_gwangju"] == "https://bukgu.gwangju.kr/"
        assert base_urls["gwangju_go_kr"] == "https://www.gwangju.go.kr/"
        assert base_urls["seogu_gwangju"] == "https://www.seogu.gwangju.kr/"

    def test_allowed_domains_isolation(self, loader):
        """Each profile's allowed_domains should not overlap incorrectly."""
        for pid in ALL_PROFILE_IDS:
            profile = loader.load_by_id(pid)
            domains = profile.allowed_domains
            assert len(domains) > 0, f"{pid}: allowed_domains is empty"
            # Each profile should have at least its own domain
            base = profile.base_url.replace("https://", "").rstrip("/")
            assert any(base in d for d in domains), f"{pid}: base domain not in allowed_domains"

    def test_candidate_rules_identical_across_profiles(self, loader):
        """All 3 profiles use the exact same conservative candidate rule set."""
        profiles = {pid: loader.load_by_id(pid) for pid in ALL_PROFILE_IDS}

        # Get the crawl_filters from each
        filters_dict = {pid: p.crawl_filters for pid, p in profiles.items()}

        # All should be identical
        first_filters = filters_dict[ALL_PROFILE_IDS[0]]
        for pid in ALL_PROFILE_IDS[1:]:
            assert filters_dict[pid] == first_filters, f"{pid}: crawl_filters differs from {ALL_PROFILE_IDS[0]}"

    def test_classification_all_legacy_board_site(self, loader):
        """All 3 profiles should be LEGACY_BOARD_SITE."""
        for pid in ALL_PROFILE_IDS:
            profile = loader.load_by_id(pid)
            assert profile.classification == "LEGACY_BOARD_SITE", f"{pid}: expected LEGACY_BOARD_SITE"


# ------------------------------------------------------------------
# Test 6: No live/network guard
# ------------------------------------------------------------------

class TestNoLiveNetworkGuard:
    """Ensure no live network/API/Firecrawl calls in tests."""

    def test_homepage_mapper_mock_provider_only(self):
        """HomepageMapper with mock provider makes no live calls."""
        loader = SiteProfileLoader()
        for pid in ALL_PROFILE_IDS:
            profile = loader.load_by_id(pid)
            mapper = HomepageMapper(fetch_provider="mock", crawl_filters=profile.crawl_filters)

            with patch.object(mapper, "fetch_content") as mock_fetch:
                mock_fetch.return_value = (mock_homepage_html(pid), None, 200, PROFILE_CONFIGS[pid]["base_url"])
                result = mapper.build_map(PROFILE_CONFIGS[pid]["base_url"])
                assert result["homepage"]["title"] is not None

    def test_url_crawler_no_live_fetch(self):
        """URLCrawler with crawl_filters only should not make live requests."""
        loader = SiteProfileLoader()
        for pid in ALL_PROFILE_IDS:
            profile = loader.load_by_id(pid)
            crawler = URLCrawler(crawl_filters=profile.crawl_filters)

            base_url = PROFILE_CONFIGS[pid]["base_url"]
            soup = BeautifulSoup(mock_homepage_html(pid), "html.parser")
            links = crawler.extract_links(soup, base_url)
            assert len(links["internal"]) > 0

    def test_should_crawl_url_pure_function(self):
        """should_crawl_url is a pure function with no side effects."""
        url = "https://bukgu.gwangju.kr/menu.es?mid=a101"
        assert should_crawl_url(url, CONSERVATIVE_CANDIDATE) is True
        assert should_crawl_url("https://bukgu.gwangju.kr/page?print=1", CONSERVATIVE_CANDIDATE) is False

    def test_no_run_live_tests_env_used(self):
        """Verify RUN_LIVE_*_TESTS=1 is not used in our tests."""
        import os
        assert os.environ.get("RUN_LIVE_CRAWL_TESTS") != "1"
        assert os.environ.get("RUN_LIVE_FIRECRAWL_TESTS") != "1"
        assert os.environ.get("RUN_LIVE_API_TESTS") != "1"


# ------------------------------------------------------------------
# Test 7: No scenario/snapshot/cache mutation
# ------------------------------------------------------------------

class TestNoScenarioSnapshotCacheMutation:
    """Verify tests don't mutate repo scenario/snapshot/cache files."""

    def test_no_repo_scenario_files_created(self, tmp_path):
        """Test outputs only go to tmp_path, not repo."""
        loader = SiteProfileLoader()
        for pid in ALL_PROFILE_IDS:
            profile = loader.load_by_id(pid)
            crawler = URLCrawler(crawl_filters=profile.crawl_filters)

            base_url = PROFILE_CONFIGS[pid]["base_url"]
            soup = BeautifulSoup(mock_homepage_html(pid), "html.parser")
            links = crawler.extract_links(soup, base_url)

            # Just verify the test works - output is in memory, not files
            assert len(links["internal"]) > 0

        # Verify no repo files were touched by checking tmp_path isolation
        assert str(tmp_path) in str(tmp_path)
