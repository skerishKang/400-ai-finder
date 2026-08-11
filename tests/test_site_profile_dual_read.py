"""#1225-D1 — Python SiteProfile identifier dual-read migration tests.

Contract scope (D1 slice):
* ``SiteProfileLoader.load_by_id`` / ``load_profile`` accept both the
  canonical site ID and SiteSpec legacy aliases, projecting through
  ``runtime.python_profile`` to the YAML profile.
* SiteSpec is the single source of truth for identifier→profile mapping;
  no separate alias table is introduced.
* Unmigrated exact-YAML profiles (no SiteSpec yet) keep loading.
* SiteSpec-resolved identifiers fail closed on missing/malformed
  ``runtime.python_profile`` (no requested-ID fallback).
* Display labels / historical aliases / unknown identifiers fail closed.
* Explicit file-path loading semantics are unchanged.

Pure stdlib + pytest only. No network, no provider, no Firecrawl.
Generic second-site fixtures live only in pytest temp directories.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.site_profiles import (
    SiteProfileLoader,
    list_profiles,
    load_profile,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIGS_SITES = REPO_ROOT / "configs" / "sites"

REAL_CANONICAL = "bukgu_gwangju"
REAL_LEGACY = "bukgu"

# Generic fixture: canonical ID deliberately differs from the
# runtime.python_profile filename so an implementation that hard-codes
# ``canonical_site_id + ".yml"`` is caught.
GENERIC_CANONICAL = "sample_city"
GENERIC_LEGACY = "sample"
GENERIC_PROFILE = "sample_runtime"


def _write_yaml(path: Path, data: dict) -> Path:
    """Write a dict as YAML to *path*."""
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    return path


def _write_sitespec(
    tmp_path: Path,
    *,
    site_id: str,
    legacy_ids: list[str],
    python_profile: str,
    filename: str | None = None,
) -> Path:
    """Write a realistic generic SiteSpec fixture."""
    doc = {
        "$schema": "configs/sitespec.schema.json",
        "schema_version": "1.0.0",
        "site_id": site_id,
        "legacy_ids": legacy_ids,
        "jurisdiction": {
            "canonical_name": f"Sample {site_id}",
            "short_name": "Sample",
            "effective_from": "2026-07-01",
            "historical_aliases": [],
        },
        "display": {
            "default_label": f"Sample {site_id}",
            "locale_labels": {
                "ko": f"Sample {site_id}",
                "en": f"Sample {site_id}",
            },
        },
        "domains": {"public": [f"{site_id}.example.kr"]},
        "runtime": {
            "python_profile": python_profile,
            "cloudflare_adapter": site_id,
        },
        "clone": {
            "golden_commit": "0" * 40,
            "golden_commit_subject": "sample",
        },
    }
    name = filename if filename is not None else site_id
    path = tmp_path / f"{name}.sitespec.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def loader() -> SiteProfileLoader:
    """Loader pointing at the real configs/sites/ directory."""
    return SiteProfileLoader()


@pytest.fixture
def generic_dir(tmp_path: Path) -> Path:
    """A temp directory with the generic canonical/legacy fixture.

    SiteSpec: ``sample_city`` (legacy ``sample``) →
    ``runtime.python_profile = sample_runtime``. The YAML profile is
    ``sample_runtime.yml`` with ``site_id: sample_city``.
    """
    _write_sitespec(
        tmp_path,
        site_id=GENERIC_CANONICAL,
        legacy_ids=[GENERIC_LEGACY],
        python_profile=GENERIC_PROFILE,
    )
    _write_yaml(tmp_path / f"{GENERIC_PROFILE}.yml", {
        "site_id": GENERIC_CANONICAL,
        "name": "Sample City",
        "base_url": "https://example.test/",
    })
    return tmp_path


# ------------------------------------------------------------------
# Real Buk-gu canonical / legacy identifier loading (regressions 1-4)
# ------------------------------------------------------------------


class TestBukguDualRead:
    def test_load_by_id_canonical(self, loader):
        """1. load_by_id('bukgu_gwangju') succeeds."""
        profile = loader.load_by_id(REAL_CANONICAL)
        assert profile.site_id == REAL_CANONICAL

    def test_load_by_id_legacy(self, loader):
        """2. load_by_id('bukgu') succeeds via legacy alias."""
        profile = loader.load_by_id(REAL_LEGACY)
        assert profile.site_id == REAL_CANONICAL

    def test_canonical_legacy_semantic_equality(self, loader):
        """3. canonical/legacy results are semantically equal."""
        canonical = loader.load_by_id(REAL_CANONICAL)
        legacy = loader.load_by_id(REAL_LEGACY)
        assert canonical.to_dict() == legacy.to_dict()

    def test_both_resolve_to_canonical_site_id(self, loader):
        """4. Both resolve to profile.site_id == 'bukgu_gwangju'."""
        canonical = loader.load_by_id(REAL_CANONICAL)
        legacy = loader.load_by_id(REAL_LEGACY)
        assert canonical.site_id == REAL_CANONICAL
        assert legacy.site_id == REAL_CANONICAL


# ------------------------------------------------------------------
# load_profile convenience (regressions 5-6)
# ------------------------------------------------------------------


class TestLoadProfileDualRead:
    def test_load_profile_canonical(self):
        """5. load_profile('bukgu_gwangju') succeeds."""
        profile = load_profile(REAL_CANONICAL)
        assert profile.site_id == REAL_CANONICAL

    def test_load_profile_legacy(self):
        """6. load_profile('bukgu') loads the same canonical profile."""
        canonical = load_profile(REAL_CANONICAL)
        legacy = load_profile(REAL_LEGACY)
        assert legacy.site_id == REAL_CANONICAL
        assert legacy.to_dict() == canonical.to_dict()


# ------------------------------------------------------------------
# Fail-closed identifiers (regressions 7-10)
# ------------------------------------------------------------------


class TestFailClosedIdentifiers:
    @pytest.mark.parametrize(
        "identifier",
        [
            "북구청",            # display label (ko)
            "Gwangju Buk-gu",   # display label (en)
            "광주광역시 북구",  # jurisdiction historical alias
            "unknown_site",
        ],
    )
    def test_non_identifiers_rejected(self, loader, identifier):
        """7-10. Display/historical/unknown identifiers fail closed."""
        with pytest.raises(FileNotFoundError):
            loader.load_by_id(identifier)

    def test_unknown_identifier_public_behavior(self, loader):
        """Existing public behavior: unknown identifier raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            loader.load_by_id("definitely_not_a_real_site")


# ------------------------------------------------------------------
# Explicit file-path semantics unchanged (regressions 11-12)
# ------------------------------------------------------------------


class TestExplicitFilePath:
    def test_explicit_real_yaml_path(self, loader):
        """11. Explicit real YAML path behavior is unchanged."""
        path = CONFIGS_SITES / f"{REAL_CANONICAL}.yml"
        profile = loader.load_file(path)
        assert profile.site_id == REAL_CANONICAL

        profile2 = load_profile(str(path))
        assert profile2.site_id == REAL_CANONICAL

    def test_explicit_temp_yaml_path(self, tmp_path):
        """12. Explicit temp YAML path behavior is unchanged."""
        p = _write_yaml(tmp_path / "custom.yml", {
            "site_id": "custom",
            "name": "Custom",
            "base_url": "https://custom.example/",
        })
        loader = SiteProfileLoader(tmp_path)
        assert loader.load_file(p).site_id == "custom"
        assert load_profile(str(p)).site_id == "custom"

    def test_load_file_not_reinterpreted_as_site_id(self, tmp_path):
        """load_file() never applies SiteSpec resolution to a path."""
        p = _write_yaml(tmp_path / "whatever.yml", {
            "site_id": "whatever",
            "name": "Whatever",
            "base_url": "https://whatever.example/",
        })
        loader = SiteProfileLoader(tmp_path)
        assert loader.load_file(p).site_id == "whatever"


# ------------------------------------------------------------------
# Generic fixture: canonical ID != runtime.python_profile filename
# (regressions 13-15)
# ------------------------------------------------------------------


class TestGenericDualRead:
    def test_generic_canonical_projects_to_runtime_profile(self, generic_dir):
        """13. load_by_id('sample_city') loads sample_runtime.yml."""
        loader = SiteProfileLoader(generic_dir)
        profile = loader.load_by_id(GENERIC_CANONICAL)
        assert profile.site_id == GENERIC_CANONICAL
        assert profile.name == "Sample City"

    def test_generic_legacy_projects_to_runtime_profile(self, generic_dir):
        """14. load_by_id('sample') loads sample_runtime.yml via alias."""
        loader = SiteProfileLoader(generic_dir)
        profile = loader.load_by_id(GENERIC_LEGACY)
        assert profile.site_id == GENERIC_CANONICAL

    def test_generic_canonical_legacy_semantic_equality(self, generic_dir):
        """15. Generic canonical/legacy results are semantically equal."""
        loader = SiteProfileLoader(generic_dir)
        canonical = loader.load_by_id(GENERIC_CANONICAL)
        legacy = loader.load_by_id(GENERIC_LEGACY)
        assert canonical.to_dict() == legacy.to_dict()

    def test_generic_projection_uses_python_profile_not_canonical_id(
        self, generic_dir
    ):
        """The loader must read sample_runtime.yml, never sample_city.yml."""
        assert not (generic_dir / f"{GENERIC_CANONICAL}.yml").exists()
        loader = SiteProfileLoader(generic_dir)
        profile = loader.load_by_id(GENERIC_CANONICAL)
        assert profile.site_id == GENERIC_CANONICAL
        assert (generic_dir / f"{GENERIC_PROFILE}.yml").exists()


# ------------------------------------------------------------------
# Missing / malformed runtime.python_profile fail closed
# (regressions 16-17)
# ------------------------------------------------------------------


class TestRuntimeProjectionFailClosed:
    def test_missing_runtime_python_profile(self, tmp_path):
        """16. SiteSpec without runtime.python_profile fails closed."""
        _write_sitespec(
            tmp_path,
            site_id="missing_runtime",
            legacy_ids=[],
            python_profile="unused",
        )
        # Rewrite with no runtime mapping at all.
        spec_path = tmp_path / "missing_runtime.sitespec.json"
        doc = json.loads(spec_path.read_text(encoding="utf-8"))
        del doc["runtime"]
        spec_path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _write_yaml(tmp_path / "missing_runtime.yml", {
            "site_id": "missing_runtime",
            "name": "Missing Runtime",
            "base_url": "https://missing.example/",
        })

        loader = SiteProfileLoader(tmp_path)
        with pytest.raises(ValueError, match="python_profile"):
            loader.load_by_id("missing_runtime")

    def test_malformed_runtime_python_profile(self, tmp_path):
        """17. Non-string runtime.python_profile fails closed."""
        _write_sitespec(
            tmp_path,
            site_id="malformed_runtime",
            legacy_ids=[],
            python_profile="unused",
        )
        spec_path = tmp_path / "malformed_runtime.sitespec.json"
        doc = json.loads(spec_path.read_text(encoding="utf-8"))
        doc["runtime"]["python_profile"] = 123
        spec_path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _write_yaml(tmp_path / "malformed_runtime.yml", {
            "site_id": "malformed_runtime",
            "name": "Malformed Runtime",
            "base_url": "https://malformed.example/",
        })

        loader = SiteProfileLoader(tmp_path)
        with pytest.raises(ValueError, match="python_profile"):
            loader.load_by_id("malformed_runtime")

    def test_no_fallback_to_requested_id_yaml_after_resolution(self, tmp_path):
        """A resolved SiteSpec never falls back to <requested_id>.yml."""
        _write_sitespec(
            tmp_path,
            site_id="no_fallback",
            legacy_ids=[],
            python_profile="missing_target",
        )
        # The requested-ID YAML exists but the projected profile does not.
        _write_yaml(tmp_path / "no_fallback.yml", {
            "site_id": "no_fallback",
            "name": "No Fallback",
            "base_url": "https://nofallback.example/",
        })

        loader = SiteProfileLoader(tmp_path)
        with pytest.raises(FileNotFoundError, match="missing_target"):
            loader.load_by_id("no_fallback")


# ------------------------------------------------------------------
# list_ids / list_profiles must not expose the alias (regressions 18-19)
# ------------------------------------------------------------------


class TestListAliasAbsence:
    def test_legacy_alias_absent_from_list_ids(self, loader):
        """18. Legacy alias 'bukgu' is absent from list_ids()."""
        ids = loader.list_ids()
        assert REAL_CANONICAL in ids
        assert REAL_LEGACY not in ids

    def test_legacy_alias_not_duplicated_in_list_profiles(self, loader):
        """19. Legacy alias is not duplicated in list_profiles()."""
        profiles = list_profiles()
        site_ids = [p["site_id"] for p in profiles]
        assert REAL_CANONICAL in site_ids
        assert REAL_LEGACY not in site_ids
        assert site_ids.count(REAL_CANONICAL) == 1

    def test_list_ids_yaml_only_dir(self, tmp_path):
        """YAML-only directories keep listing exactly the YAML stems."""
        _write_yaml(tmp_path / "alpha.yml", {
            "site_id": "alpha",
            "name": "Alpha",
            "base_url": "https://alpha.example/",
        })
        _write_yaml(tmp_path / "beta.yml", {
            "site_id": "beta",
            "name": "Beta",
            "base_url": "https://beta.example/",
        })
        assert SiteProfileLoader(tmp_path).list_ids() == ["alpha", "beta"]


# ------------------------------------------------------------------
# Unmigrated exact-YAML profiles still load (regression 20)
# ------------------------------------------------------------------


class TestUnmigratedExactYaml:
    def test_exact_yaml_without_sitespec_still_loads(self, loader):
        """20. Existing exact-YAML profile without SiteSpec still loads."""
        # seogu_gwangju.yml exists in configs/sites and has no SiteSpec.
        profile = loader.load_by_id("seogu_gwangju")
        assert profile.site_id == "seogu_gwangju"

    def test_exact_yaml_without_sitespec_in_temp_dir(self, tmp_path):
        """YAML-only temp directory behaves like the historical loader."""
        _write_yaml(tmp_path / "lonely.yml", {
            "site_id": "lonely",
            "name": "Lonely",
            "base_url": "https://lonely.example/",
        })
        loader = SiteProfileLoader(tmp_path)
        profile = loader.load_by_id("lonely")
        assert profile.site_id == "lonely"

    def test_constructor_compat_yaml_only_dir(self, tmp_path):
        """SiteProfileLoader(temp_dir) works when no *.sitespec.json exists."""
        _write_yaml(tmp_path / "plain.yml", {
            "site_id": "plain",
            "name": "Plain",
            "base_url": "https://plain.example/",
        })
        loader = SiteProfileLoader(tmp_path)
        assert loader.load_by_id("plain").site_id == "plain"
        assert loader.load_file(tmp_path / "plain.yml").site_id == "plain"
