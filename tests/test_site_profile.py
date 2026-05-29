"""Tests for site profiles — SiteProfile, SiteProfileLoader, load_profile."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from src.site_profiles import SiteProfile, SiteProfileLoader, load_profile

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
