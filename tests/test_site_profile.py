"""Tests for site profiles — SiteProfile, SiteProfileLoader, load_profile."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from src.site_profiles import SiteProfile, SiteProfileLoader, load_profile
from src.site_profiles.site_profile import DEFAULT_BOARD_PATTERNS, DEFAULT_CRAWL_RULES

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def loader() -> SiteProfileLoader:
    """Loader pointing at the real configs/sites/ directory."""
    return SiteProfileLoader()


@pytest.fixture
def temp_dir() -> Path:
    """A temporary directory for ad-hoc profile files."""
    d = tempfile.mkdtemp()
    return Path(d)


def _write_yaml(path: Path, data: dict) -> Path:
    """Write a dict as YAML to *path*."""
    import yaml
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    return path


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestSiteProfile:
    """Core SiteProfile data-class behaviour."""

    def test_required_fields(self):
        """A profile with all fields works."""
        p = SiteProfile({
            "site_id": "test_site",
            "name": "Test Site",
            "base_url": "https://example.com/",
        })
        assert p.site_id == "test_site"
        assert p.name == "Test Site"
        assert p.base_url == "https://example.com/"

    def test_default_allowed_domains(self):
        """allowed_domains defaults to domain from base_url."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://bukgu.gwangju.kr/",
        })
        assert p.allowed_domains == ["bukgu.gwangju.kr"]

    def test_default_crawl_rules(self):
        """crawl_rules defaults apply."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
        })
        rules = p.crawl_rules
        assert rules["max_depth"] == 3
        assert rules["max_pages"] == 200
        assert rules["include_documents"] is True
        assert rules["respect_robots"] is True

    def test_crawl_rules_override(self):
        """crawl_rules overrides merge correctly."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
            "crawl_rules": {"max_depth": 5},
        })
        assert p.crawl_rules["max_depth"] == 5
        assert p.crawl_rules["max_pages"] == 200  # default kept

    def test_default_document_extensions(self):
        """document_extensions has sensible defaults."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
        })
        exts = p.document_extensions
        assert "pdf" in exts
        assert "hwp" in exts
        assert "docx" in exts

    def test_default_board_patterns(self):
        """board_patterns has sensible defaults."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
        })
        patterns = p.board_patterns
        assert "board" in patterns
        assert "notice" in patterns

    # ------------------------------------------------------------------
    # #955: lock board-pattern and crawl-rule defaults before extraction.
    # These pin the exact default values and the defensive-copy / merge /
    # replace semantics so the later constants refactor (#833) cannot change
    # observable behavior. Source behavior is intentionally NOT changed.
    # ------------------------------------------------------------------
    def test_default_board_patterns_exact_order(self):
        """#955 / no network. Lock the exact ordered default board patterns."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
        })
        assert p.board_patterns == ["board", "bbs", "list", "view", "article", "notice"]
        assert p.board_patterns == list(DEFAULT_BOARD_PATTERNS)

    def test_board_patterns_returns_defensive_copy(self):
        """#955 / no network. board_patterns must not leak mutations back to
        the property or the module-level default."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
        })
        first = p.board_patterns
        first.append("mutated")
        second = p.board_patterns
        assert "mutated" not in second
        assert second == ["board", "bbs", "list", "view", "article", "notice"]
        # Module-level default is untouched, too.
        assert "mutated" not in DEFAULT_BOARD_PATTERNS

    def test_board_patterns_override_replaces_defaults(self):
        """#955 / no network. A profile-provided board_patterns fully replaces
        (not merges with) the defaults, preserving the override order."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
            "board_patterns": ["custom", "notice"],
        })
        assert p.board_patterns == ["custom", "notice"]
        assert "board" not in p.board_patterns

    def test_default_crawl_rules_exact_values(self):
        """#955 / no network. Lock the exact default crawl rules dict."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
        })
        assert p.crawl_rules == {
            "max_depth": 3,
            "max_pages": 200,
            "include_documents": True,
            "respect_robots": True,
        }
        assert p.crawl_rules == dict(DEFAULT_CRAWL_RULES)

    def test_crawl_rules_returns_defensive_copy(self):
        """#955 / no network. crawl_rules must not leak mutations back to the
        property or the module-level default."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
        })
        first = p.crawl_rules
        first["max_depth"] = 999
        first["new_key"] = "mutated"
        second = p.crawl_rules
        assert second == {
            "max_depth": 3,
            "max_pages": 200,
            "include_documents": True,
            "respect_robots": True,
        }
        assert "new_key" not in second
        # Module-level default is untouched, too.
        assert DEFAULT_CRAWL_RULES.get("new_key") != "mutated"
        assert DEFAULT_CRAWL_RULES["max_depth"] == 3

    def test_crawl_rules_partial_override_merges_defaults(self):
        """#955 / no network. A partial crawl_rules override merges with the
        defaults: given keys are replaced, missing keys keep their defaults."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
            "crawl_rules": {"max_depth": 5, "include_documents": False},
        })
        assert p.crawl_rules == {
            "max_depth": 5,
            "max_pages": 200,
            "include_documents": False,
            "respect_robots": True,
        }

    def test_match_url(self):
        """match_url checks allowed_domains."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://bukgu.gwangju.kr/",
            "allowed_domains": ["bukgu.gwangju.kr"],
        })
        assert p.match_url("https://bukgu.gwangju.kr/menu.es?mid=xxx")
        assert not p.match_url("https://other-site.com/")

    def test_to_dict(self):
        """to_dict returns all fields as a plain dict."""
        p = SiteProfile({
            "site_id": "test",
            "name": "Test",
            "base_url": "https://example.com/",
        })
        d = p.to_dict()
        assert d["site_id"] == "test"
        assert d["name"] == "Test"
        assert "allowed_domains" in d
        assert "preferred_fetch_provider" in d
        assert "crawl_rules" in d

    def test_json_serializable(self):
        """to_dict output is JSON-serializable."""
        p = SiteProfile({
            "site_id": "test",
            "name": "Test",
            "base_url": "https://example.com/",
            "important_keywords": ["키워드"],
        })
        dumped = json.dumps(p.to_dict(), ensure_ascii=False)
        loaded = json.loads(dumped)
        assert loaded["site_id"] == "test"
        assert loaded["important_keywords"] == ["키워드"]


class TestSiteProfileLoader:
    """SiteProfileLoader — loading profiles from YAML files."""

    def test_load_bukgu_profile(self, loader):
        """1. 북구청 프로필 파일 로드."""
        profile = loader.load_file(
            Path(__file__).resolve().parent.parent / "configs" / "sites" / "bukgu_gwangju.yml"
        )
        assert profile.site_id == "bukgu_gwangju"
        assert "북구" in profile.name
        assert profile.base_url == "https://bukgu.gwangju.kr/"

    def test_load_by_id(self, loader):
        """2. site_id 기반 프로필 로드."""
        profile = loader.load_by_id("bukgu_gwangju")
        assert profile.site_id == "bukgu_gwangju"
        assert profile.base_url == "https://bukgu.gwangju.kr/"

    def test_required_fields_validated(self, temp_dir):
        """3. 필수 필드 검증 — missing field raises ValueError."""
        path = _write_yaml(temp_dir / "bad.yml", {
            "name": "No ID",
            "base_url": "https://example.com/",
        })
        with pytest.raises(ValueError, match="Missing required field 'site_id'"):
            SiteProfileLoader(temp_dir).load_file(path)

    def test_empty_field_validated(self, temp_dir):
        """Required field empty raises ValueError."""
        path = _write_yaml(temp_dir / "empty.yml", {
            "site_id": "",
            "name": "Empty ID",
            "base_url": "https://example.com/",
        })
        with pytest.raises(ValueError, match="'site_id'.*must not be empty"):
            SiteProfileLoader(temp_dir).load_file(path)

    def test_base_url_must_be_http(self, temp_dir):
        """base_url must start with http."""
        path = _write_yaml(temp_dir / "bad-url.yml", {
            "site_id": "bad",
            "name": "Bad",
            "base_url": "ftp://example.com/",
        })
        with pytest.raises(ValueError, match="'base_url'.*must start with http"):
            SiteProfileLoader(temp_dir).load_file(path)

    def test_invalid_yaml(self, temp_dir):
        """Malformed YAML raises ValueError."""
        p = temp_dir / "broken.yml"
        p.write_text("{{{not: yaml: }}}", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid YAML"):
            SiteProfileLoader(temp_dir).load_file(p)

    def test_file_not_found(self, loader):
        """Missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            loader.load_file("/nonexistent/path.yml")

    def test_load_by_id_not_found(self, loader):
        """Unknown site_id raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            loader.load_by_id("definitely_not_a_real_site")

    def test_allowed_domains_from_profile(self, loader):
        """4. allowed_domains 기본 검증."""
        profile = loader.load_by_id("bukgu_gwangju")
        assert "bukgu.gwangju.kr" in profile.allowed_domains

    def test_document_extensions_access(self, loader):
        """5. document_extensions 접근."""
        profile = loader.load_by_id("bukgu_gwangju")
        exts = profile.document_extensions
        assert "pdf" in exts
        assert "hwp" in exts
        assert "zip" in exts

    def test_board_patterns_access(self, loader):
        """6. board_patterns 접근."""
        profile = loader.load_by_id("bukgu_gwangju")
        patterns = profile.board_patterns
        assert "board" in patterns
        assert "bbs" in patterns

    def test_important_keywords_access(self, loader):
        """7. important_keywords 접근."""
        profile = loader.load_by_id("bukgu_gwangju")
        keywords = profile.important_keywords
        assert "종합민원" in keywords
        assert "민원서식" in keywords
        assert len(keywords) >= 5

    def test_fallback_strategy_access(self, loader):
        """8. fallback_strategy 접근."""
        profile = loader.load_by_id("bukgu_gwangju")
        strategy = profile.fallback_strategy
        assert "requests" in strategy
        assert "sitemap" in strategy
        assert "browser_provider_candidate" in strategy

    def test_dict_json_serializable(self, loader):
        """9. dict 변환 결과가 JSON 직렬화 가능."""
        profile = loader.load_by_id("bukgu_gwangju")
        d = profile.to_dict()
        dumped = json.dumps(d, ensure_ascii=False)
        loaded = json.loads(dumped)
        assert loaded["site_id"] == "bukgu_gwangju"
        assert "종합민원" in loaded["important_keywords"]

    def test_bad_profile_raises_clear_exception(self, temp_dir):
        """10. 잘못된 프로필은 명확한 예외 발생."""
        path = _write_yaml(temp_dir / "bad.yml", {
            "site_id": 123,  # wrong type
            "name": "Bad Type",
            "base_url": "https://example.com/",
        })
        with pytest.raises(ValueError, match="must be str"):
            SiteProfileLoader(temp_dir).load_file(path)

    def test_defaults_applied(self, loader):
        """11. 기본값 적용 확인."""
        profile = loader.load_by_id("bukgu_gwangju")
        rules = profile.crawl_rules
        assert rules["max_pages"] == 200
        assert rules["include_documents"] is True

    def test_bukgu_classification_and_provider(self, loader):
        """12. 북구청 프로필이 LEGACY_BOARD_SITE와 requests provider."""
        profile = loader.load_by_id("bukgu_gwangju")
        assert profile.classification == "LEGACY_BOARD_SITE"
        assert profile.preferred_fetch_provider == "requests"

    def test_missing_crawl_filters(self):
        """Verify that missing crawl_filters config defaults to an empty dict."""
        p = SiteProfile({
            "site_id": "test",
            "name": "Test",
            "base_url": "https://example.com/",
        })
        assert p.crawl_filters == {}

    def test_valid_crawl_filters(self):
        """Verify that a valid crawl_filters dictionary is parsed correctly."""
        p = SiteProfile({
            "site_id": "test",
            "name": "Test",
            "base_url": "https://example.com/",
            "crawl_filters": {
                "allow_patterns": ["menu.es?mid="],
                "deny_patterns": ["print=", "pageNo="],
                "protected_patterns": ["mid=", "menuId="],
            }
        })
        assert p.crawl_filters == {
            "allow_patterns": ["menu.es?mid="],
            "deny_patterns": ["print=", "pageNo="],
            "protected_patterns": ["mid=", "menuId="],
        }

    def test_invalid_crawl_filters_block(self):
        """Verify that an invalid crawl_filters block defaults safely to an empty dict."""
        p1 = SiteProfile({
            "site_id": "test",
            "name": "Test",
            "base_url": "https://example.com/",
            "crawl_filters": "not-a-dict",
        })
        assert p1.crawl_filters == {}

        p2 = SiteProfile({
            "site_id": "test",
            "name": "Test",
            "base_url": "https://example.com/",
            "crawl_filters": ["list", "of", "items"],
        })
        assert p2.crawl_filters == {}

    def test_invalid_pattern_values(self):
        """Verify that invalid/non-list/non-string values inside crawl_filters are sanitized."""
        p = SiteProfile({
            "site_id": "test",
            "name": "Test",
            "base_url": "https://example.com/",
            "crawl_filters": {
                "allow_patterns": "not-a-list",
                "deny_patterns": ["print=", 123, "   ", ""],
                "protected_patterns": ["mid=", None, "menuId="],
            }
        })
        assert p.crawl_filters == {
            "allow_patterns": [],
            "deny_patterns": ["print="],
            "protected_patterns": ["mid=", "menuId="],
        }

    def test_unknown_keys_ignored(self):
        """Verify that unknown keys in the crawl_filters block are ignored."""
        p = SiteProfile({
            "site_id": "test",
            "name": "Test",
            "base_url": "https://example.com/",
            "crawl_filters": {
                "allow_patterns": ["menu.es?mid="],
                "regex_patterns": ["^abc$"],
                "thresholds": 5,
            }
        })
        assert p.crawl_filters == {
            "allow_patterns": ["menu.es?mid="],
            "deny_patterns": [],
            "protected_patterns": [],
        }

    def test_traversal_wiring_implemented(self):
        """Ensure url_crawler.py references crawl_filters and should_crawl_url."""
        import inspect
        try:
            import src.crawler.url_crawler as uc
            source = inspect.getsource(uc)
            assert "crawl_filters" in source
            assert "should_crawl_url" in source
        except ImportError:
            pass


class TestLoadProfileConvenience:
    """load_profile() convenience function."""

    def test_by_site_id(self):
        """Load by site_id string."""
        profile = load_profile("bukgu_gwangju")
        assert profile.site_id == "bukgu_gwangju"

    def test_by_file_path(self):
        """Load by explicit file path."""
        path = Path(__file__).resolve().parent.parent / "configs" / "sites" / "bukgu_gwangju.yml"
        profile = load_profile(str(path))
        assert profile.site_id == "bukgu_gwangju"

    def test_not_found(self):
        """Unknown site_id raises."""
        with pytest.raises(FileNotFoundError):
            load_profile("definitely_not_a_real_site_profile")


class TestListProfiles:
    """list_ids() — discover available profiles."""

    def test_list_ids(self, loader):
        """bukgu_gwangju should be in the list."""
        ids = loader.list_ids()
        assert "bukgu_gwangju" in ids
        assert len(ids) >= 1

    def test_empty_dir(self, temp_dir):
        """Empty configs directory returns empty list."""
        loader = SiteProfileLoader(temp_dir)
        assert loader.list_ids() == []


class TestListProfilesFunc:
    """list_profiles() — enumerate profiles with metadata."""

    def test_returns_list_of_dicts(self):
        """list_profiles() returns list with site_id, name, base_url, classification."""
        from src.site_profiles import list_profiles
        profiles = list_profiles()
        assert isinstance(profiles, list)
        assert len(profiles) >= 2
        site_ids = [p["site_id"] for p in profiles]
        assert "bukgu_gwangju" in site_ids
        assert "gwangju_go_kr" in site_ids
        for p in profiles:
            assert "site_id" in p
            assert "name" in p
            assert "base_url" in p
            assert "classification" in p


class TestIntegrationNotes:
    """Integration checks — profile data coherence."""

    def test_profile_matches_diagnostics(self, loader):
        """북구청 profile should align with Stage 10D diagnostics findings."""
        profile = loader.load_by_id("bukgu_gwangju")
        # LEGACY_BOARD_SITE implies board patterns exist
        assert "board" in profile.board_patterns
        # requests provider was confirmed working in Stage 10F
        assert profile.preferred_fetch_provider == "requests"
        # should detect bukgu URLs
        assert profile.match_url("https://bukgu.gwangju.kr/menu.es?mid=a10101000000")
        # should NOT detect non-bukgu URLs
        assert not profile.match_url("https://www.gwangju.go.kr/")


class TestSynonymDictionary:
    """Tests for the optional ``synonym_dictionary`` field on SiteProfile.

    Added in Stage 363. Profiles that omit the field must still load
    correctly, and invalid entries must be filtered, not hard-failed.
    """

    def test_synonym_dictionary_defaults_to_empty(self):
        """Profiles without synonym_dictionary return an empty dict."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
        })
        assert p.synonym_dictionary == {}

    def test_synonym_dictionary_loads_optional_mapping(self):
        """A well-formed synonym_dictionary is exposed unchanged."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
            "synonym_dictionary": {
                "민원": ["종합민원", "온라인 민원", "민원서식"],
                "공고": ["고시공고", "공지사항"],
            },
        })
        assert p.synonym_dictionary["민원"] == [
            "종합민원", "온라인 민원", "민원서식",
        ]
        assert p.synonym_dictionary["공고"] == ["고시공고", "공지사항"]

    def test_synonym_dictionary_filters_invalid_entries(self):
        """Invalid entries are silently filtered, not raised."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
            "synonym_dictionary": {
                "민원": ["종합민원", "", "종합민원", 123, "온라인 민원"],
                "": ["should-drop"],
                123: ["should-drop"],
                "공고": "not-a-list",
            },
        })
        assert p.synonym_dictionary == {
            "민원": ["종합민원", "온라인 민원"],
        }

    def test_synonym_dictionary_in_to_dict_and_json_serializable(self):
        """synonym_dictionary is included in to_dict() and JSON-safe."""
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
            "synonym_dictionary": {
                "민원": ["종합민원"],
            },
        })
        d = p.to_dict()
        assert d["synonym_dictionary"] == {"민원": ["종합민원"]}
        dumped = json.dumps(d, ensure_ascii=False)
        loaded = json.loads(dumped)
        assert loaded["synonym_dictionary"]["민원"] == ["종합민원"]


class TestBukguSynonymDictionarySlice:
    """Tests for the first approved synonym_dictionary slice on the
    real ``bukgu_gwangju`` profile (Stage 365).

    The slice is limited to stable official menu vocabulary for
    ``민원``, ``공고``, and ``교육``. Deferred groups are intentionally
    excluded and must not appear in the first slice.
    """

    def test_bukgu_profile_loads_synonym_dictionary(self, loader):
        """Real bukgu profile exposes the first approved slice."""
        profile = loader.load_by_id("bukgu_gwangju")
        synonyms = profile.synonym_dictionary

        assert synonyms["민원"] == ["종합민원", "온라인 민원", "민원서식"]
        assert synonyms["공고"] == ["고시공고", "공지사항", "새소식"]
        assert synonyms["교육"] == [
            "교육접수", "평생교육", "강좌", "프로그램",
        ]

    def test_bukgu_profile_synonym_dictionary_contains_no_deferred_groups(
        self, loader
    ):
        """First slice must not include deferred or volatile groups."""
        profile = loader.load_by_id("bukgu_gwangju")
        synonyms = profile.synonym_dictionary

        assert "구청장" not in synonyms
        assert "열린구청장" not in synonyms
        assert "복지" not in synonyms
        assert "정보공개" not in synonyms
        assert "청년일자리" not in synonyms

    def test_bukgu_profile_synonym_dictionary_json_serializable(self, loader):
        """Real profile synonym dictionary remains JSON serializable."""
        import json

        profile = loader.load_by_id("bukgu_gwangju")
        data = profile.to_dict()

        dumped = json.dumps(data, ensure_ascii=False)
        loaded = json.loads(dumped)

        assert loaded["synonym_dictionary"]["민원"] == [
            "종합민원", "온라인 민원", "민원서식",
        ]


class TestBukguCrawlFiltersConfig:
    """Stage 394: Real profile crawl filters verification contract tests."""

    def test_bukgu_profile_crawl_filters_loader(self, loader):
        """1. Verify that real bukgu YAML profile loads crawl_filters matching candidate."""
        profile = loader.load_by_id("bukgu_gwangju")
        filters = profile.crawl_filters

        assert filters["allow_patterns"] == []
        assert filters["deny_patterns"] == [
            "print=",
            "utm_",
            "utm_source=",
            "utm_medium=",
            "utm_campaign="
        ]
        assert filters["protected_patterns"] == [
            "mid=",
            "menuId=",
            "board.es",
            "seq=",
            "contentId=",
            "articleId="
        ]

    def test_bukgu_profile_protected_patterns(self, loader):
        """2. Verify that loaded profile's protected_patterns has all required parameters."""
        profile = loader.load_by_id("bukgu_gwangju")
        protected = profile.crawl_filters.get("protected_patterns", [])

        required = ["mid=", "menuId=", "board.es", "seq=", "contentId=", "articleId="]
        for pat in required:
            assert pat in protected

    def test_bukgu_profile_deny_patterns(self, loader):
        """3. Verify that loaded profile's deny_patterns has all required parameters."""
        profile = loader.load_by_id("bukgu_gwangju")
        denied = profile.crawl_filters.get("deny_patterns", [])

        required = ["print=", "utm_", "utm_source=", "utm_medium=", "utm_campaign="]
        for pat in required:
            assert pat in denied

    def test_bukgu_profile_forbidden_deny_guard(self, loader):
        """4. Verify that critical parameters are NOT in the real profile's deny_patterns."""
        profile = loader.load_by_id("bukgu_gwangju")
        denied = profile.crawl_filters.get("deny_patterns", [])

        forbidden = ["board.es", "mid=", "menuId=", "seq=", "contentId=", "articleId="]
        for pat in forbidden:
            assert pat not in denied

    def test_mock_static_html_safety_using_real_profile_filters(self, loader):
        """5. Verify static HTML crawl safety using filters from loaded real profile."""
        from bs4 import BeautifulSoup
        from src.crawler.url_crawler import URLCrawler

        profile = loader.load_by_id("bukgu_gwangju")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)

        base_url = "https://bukgu.gwangju.kr/"
        html = """
        <html>
          <body>
            <a href="/menu.es?mid=a101">Menu ES mid</a>
            <a href="/board.es?seq=999">Board ES seq</a>
            <a href="/content?contentId=123">Content ID</a>
            <a href="/article?articleId=777">Article ID</a>
            <a href="/page?print=1">Print Page</a>
            <a href="/page?utm_source=test">UTM Source</a>
            <a href="/board.es?pageNo=2">Page No 2</a>
          </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]

        # 5a. Check that protected parameter URLs survive
        assert "https://bukgu.gwangju.kr/menu.es?mid=a101" in urls
        assert "https://bukgu.gwangju.kr/board.es?seq=999" in urls
        assert "https://bukgu.gwangju.kr/content?contentId=123" in urls
        assert "https://bukgu.gwangju.kr/article?articleId=777" in urls

        # 5b. Check that deny parameter URLs are filtered out
        assert "https://bukgu.gwangju.kr/page?print=1" not in urls
        assert "https://bukgu.gwangju.kr/page?utm_source=test" not in urls

        # 5c. Check that pageNo survives (pagination deferred)
        assert "https://bukgu.gwangju.kr/board.es?pageNo=2" in urls


class TestGwangjuGoKrCrawlFiltersConfig:
    """Stage 397: Second municipal profile crawl filters verification contract tests.

    Applies the same conservative candidate to gwangju_go_kr (광주광역시청).
    """

    def test_gwangju_go_kr_profile_crawl_filters_loader(self, loader):
        """1. Verify that real gwangju_go_kr YAML profile loads crawl_filters matching candidate."""
        profile = loader.load_by_id("gwangju_go_kr")
        filters = profile.crawl_filters

        assert filters["allow_patterns"] == []
        assert filters["deny_patterns"] == [
            "print=",
            "utm_",
            "utm_source=",
            "utm_medium=",
            "utm_campaign="
        ]
        assert filters["protected_patterns"] == [
            "mid=",
            "menuId=",
            "board.es",
            "seq=",
            "contentId=",
            "articleId="
        ]

    def test_gwangju_go_kr_profile_protected_patterns(self, loader):
        """2. Verify that loaded profile's protected_patterns has all required parameters."""
        profile = loader.load_by_id("gwangju_go_kr")
        protected = profile.crawl_filters.get("protected_patterns", [])

        required = ["mid=", "menuId=", "board.es", "seq=", "contentId=", "articleId="]
        for pat in required:
            assert pat in protected

    def test_gwangju_go_kr_profile_deny_patterns(self, loader):
        """3. Verify that loaded profile's deny_patterns has all required parameters."""
        profile = loader.load_by_id("gwangju_go_kr")
        denied = profile.crawl_filters.get("deny_patterns", [])

        required = ["print=", "utm_", "utm_source=", "utm_medium=", "utm_campaign="]
        for pat in required:
            assert pat in denied

    def test_gwangju_go_kr_profile_forbidden_deny_guard(self, loader):
        """4. Verify that critical parameters are NOT in the real profile's deny_patterns."""
        profile = loader.load_by_id("gwangju_go_kr")
        denied = profile.crawl_filters.get("deny_patterns", [])

        forbidden = ["board.es", "mid=", "menuId=", "seq=", "contentId=", "articleId="]
        for pat in forbidden:
            assert pat not in denied

    def test_mock_static_html_safety_using_second_profile_filters(self, loader):
        """5. Verify static HTML crawl safety using filters from loaded second profile."""
        from bs4 import BeautifulSoup
        from src.crawler.url_crawler import URLCrawler

        profile = loader.load_by_id("gwangju_go_kr")
        crawler = URLCrawler(crawl_filters=profile.crawl_filters)

        base_url = "https://www.gwangju.go.kr/"
        html = """
        <html>
          <body>
            <a href="/menu.es?mid=a101">Menu ES mid</a>
            <a href="/board.es?seq=999">Board ES seq</a>
            <a href="/content?contentId=123">Content ID</a>
            <a href="/article?articleId=777">Article ID</a>
            <a href="/page?print=1">Print Page</a>
            <a href="/page?utm_source=test">UTM Source</a>
            <a href="/board.es?pageNo=2">Page No 2</a>
          </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        links = crawler.extract_links(soup, base_url)
        urls = [link["url"] for link in links["internal"]]

        # 5a. Check that protected parameter URLs survive
        assert "https://www.gwangju.go.kr/menu.es?mid=a101" in urls
        assert "https://www.gwangju.go.kr/board.es?seq=999" in urls
        assert "https://www.gwangju.go.kr/content?contentId=123" in urls
        assert "https://www.gwangju.go.kr/article?articleId=777" in urls

        # 5b. Check that deny parameter URLs are filtered out
        assert "https://www.gwangju.go.kr/page?print=1" not in urls
        assert "https://www.gwangju.go.kr/page?utm_source=test" not in urls

        # 5c. Check that pageNo survives (pagination deferred)
        assert "https://www.gwangju.go.kr/board.es?pageNo=2" in urls


# ------------------------------------------------------------------
# #949: Lock the document-extension taxonomy before constants consolidation.
# These tests pin the *profiles* view of document extensions: the 10-value
# DEFAULT_DOCUMENT_EXTENSIONS profile default and that a profile-provided
# override is returned verbatim (not narrowed to the crawler/classifier 5).
# Source behavior is intentionally NOT changed by this PR.
# ------------------------------------------------------------------
class TestDocumentExtensionTaxonomy:
    """#949 / no network.

    Lock the profile-side document extension taxonomy ahead of the #833
    constants consolidation so a later move cannot silently reorder or
    narrow the default set.
    """

    EXPECTED_DEFAULT_ORDER = [
        "pdf", "hwp", "hwpx", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip",
    ]

    def test_default_document_extensions_exact_order(self):
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
        })
        assert p.document_extensions == self.EXPECTED_DEFAULT_ORDER

    def test_profile_override_not_narrowed_to_five(self):
        # A profile-provided list must be returned verbatim. The crawler/
        # classifier 5-extension policy must not narrow or reorder it.
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
            "document_extensions": ["custom", "pdf"],
        })
        assert p.document_extensions == ["custom", "pdf"]

    def test_default_includes_broad_only_extensions(self):
        # doc/xls/ppt/pptx/zip are profile-default documents even though the
        # crawler attachment / classifier policy only treats 5 of them as
        # attachments/documents by extension. This asymmetry is intentional
        # and must stay locked.
        p = SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://example.com/",
        })
        exts = set(p.document_extensions)
        for ext in ("doc", "xls", "ppt", "pptx", "zip"):
            assert ext in exts


# ------------------------------------------------------------------
# #1292: harden SiteProfile.match_url — fail-closed URL ownership.
# Adds the deceptive-host/path/query/credential regression matrix that the
# old raw-substring match_url never pinned. No network / provider / API.
# ------------------------------------------------------------------
class TestMatchUrlHardened:
    """#1292 / no network. Fail-closed URL ownership matrix.

    Replaces the old raw-substring ``match_url`` contract with an exact,
    normalized hostname ownership decision. Every case below must hold:
    deceptive host/path/query/credential input fails closed, and the valid
    Buk-gu / Seo-gu / Gwangju URLs keep matching by exact host only.
    """

    @staticmethod
    def _profile(allowed: list[str]) -> "SiteProfile":
        return SiteProfile({
            "site_id": "t",
            "name": "T",
            "base_url": "https://%s/" % allowed[0],
            "allowed_domains": list(allowed),
        })

    # ---- VALID -------------------------------------------------------
    def test_valid_existing_bukgu(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert p.match_url("https://bukgu.gwangju.kr/")

    def test_valid_seogu_explicit_www_and_apex(self):
        p = self._profile(["www.seogu.gwangju.kr", "seogu.gwangju.kr"])
        assert p.match_url("https://www.seogu.gwangju.kr/")
        assert p.match_url("https://seogu.gwangju.kr/")

    def test_valid_gwangju_explicit_www_and_apex(self):
        p = self._profile(["www.gwangju.go.kr", "gwangju.go.kr"])
        assert p.match_url("https://www.gwangju.go.kr/")
        assert p.match_url("https://gwangju.go.kr/")

    def test_valid_seogu_with_path_query(self):
        p = self._profile(["www.seogu.gwangju.kr", "seogu.gwangju.kr"])
        assert p.match_url("https://seogu.gwangju.kr/board.es?mid=a10101010000")

    def test_valid_uppercase_host(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert p.match_url("https://BUKGU.GWANGJU.KR/")

    def test_valid_one_trailing_root_dot(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert p.match_url("https://bukgu.gwangju.kr./")

    def test_valid_explicit_port(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert p.match_url("https://bukgu.gwangju.kr:8080/")
        assert p.match_url("https://bukgu.gwangju.kr:443/")

    def test_valid_host_identity_only_path_query_fragment(self):
        p = self._profile(["bukgu.gwangju.kr"])
        # Path/query/fragment presence must not change the host-identity verdict.
        assert p.match_url("https://bukgu.gwangju.kr/menu.es?mid=xxx#frag")

    def test_valid_unicode_allowed_domain(self):
        p = self._profile(["münchen.de"])
        assert p.match_url("https://münchen.de/")

    def test_valid_unicode_idna_alabel_equivalence(self):
        # A configured IDNA A-label must match a Unicode candidate (and vice
        # versa): both normalize to the same ASCII A-label.
        alabel = self._profile(["xn--mnchen-3ya.de"])
        assert alabel.match_url("https://münchen.de/")
        unicode_dom = self._profile(["münchen.de"])
        assert unicode_dom.match_url("https://xn--mnchen-3ya.de/")

    def test_valid_ipv6_literal_explicit(self):
        p = self._profile(["2001:db8::1"])
        assert p.match_url("https://[2001:db8::1]/")

    # ---- INVALID -----------------------------------------------------
    def test_invalid_attacker_suffix(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("https://bukgu.gwangju.kr.evil.example/")

    def test_invalid_domain_only_in_path(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("https://evil.example/path/bukgu.gwangju.kr")

    def test_invalid_domain_only_in_query(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("https://evil.example/?next=bukgu.gwangju.kr")

    def test_invalid_credential_bearing(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("https://user@bukgu.gwangju.kr/")

    def test_invalid_empty_userinfo(self):
        # urlsplit yields '' (not None) for the empty userinfo; presence
        # semantics must reject it.
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("https://@bukgu.gwangju.kr/")

    def test_invalid_protocol_relative(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("//bukgu.gwangju.kr/")

    def test_invalid_scheme_less(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("bukgu.gwangju.kr/path")

    def test_invalid_relative(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("/menu.es")

    def test_invalid_ftp_scheme(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("ftp://bukgu.gwangju.kr/")

    def test_invalid_missing_hostname(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("https:///path")

    def test_invalid_malformed_port(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("https://bukgu.gwangju.kr:abc/")

    def test_invalid_out_of_range_port(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("https://bukgu.gwangju.kr:99999/")

    def test_invalid_idna(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("https://a..b.com/")

    def test_invalid_unlisted_child_subdomain(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("https://foo.bukgu.gwangju.kr/")

    def test_invalid_implicit_www_apex_equivalence(self):
        # No implicit www<->apex equivalence: each must be declared explicitly.
        apex_only = self._profile(["bukgu.gwangju.kr"])
        assert not apex_only.match_url("https://www.bukgu.gwangju.kr/")
        www_only = self._profile(["www.bukgu.gwangju.kr"])
        assert not www_only.match_url("https://bukgu.gwangju.kr/")

    def test_invalid_multiple_trailing_root_dots(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("https://bukgu.gwangju.kr../")

    def test_invalid_ipv6_not_broadly_allowed(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("https://[2001:db8::1]/")

    def test_invalid_ipv4_not_broadly_allowed(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url("http://10.0.0.1/")

    def test_invalid_non_string_input(self):
        p = self._profile(["bukgu.gwangju.kr"])
        assert not p.match_url(None)
        assert not p.match_url("")

    def test_invalid_malformed_ipv6_authority_fails_closed(self):
        # An unterminated IPv6 authority makes stdlib urlsplit() raise
        # ValueError; match_url must fail closed (False) and never leak it.
        p = self._profile(["bukgu.gwangju.kr"])
        result = p.match_url("https://[::1")
        assert result is False

    def test_invalid_nfkc_invalid_netloc_fails_closed(self):
        # A FULLWIDTH SOLIDUS (U+FF0F) in the netloc makes stdlib urlsplit()
        # raise ValueError under NFKC normalization; match_url must fail
        # closed (False) and never leak it.
        p = self._profile(["bukgu.gwangju.kr"])
        result = p.match_url("https://exa\uff0fmple.com/")
        assert result is False
