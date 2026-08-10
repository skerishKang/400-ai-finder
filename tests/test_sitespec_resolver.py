"""Contract test for the dual-read canonical SiteSpec resolver (#1225-B).

Pure stdlib + pytest only. No network, no provider, no Firecrawl.

The resolver reads canonical SiteSpecs from ``configs/sites/*.sitespec.json``
(never ``configs/site-registry.json``) and resolves both canonical and legacy
site IDs to the same canonical SiteSpec, fail-closed otherwise.

Generic second-site fixtures live only in pytest temp directories — no real
second site is onboarded in this phase.
"""

import json
from pathlib import Path

import pytest

from src.site_profiles.sitespec import (
    SiteSpecLoadError,
    SiteSpecNotFoundError,
    SiteSpecResolver,
    load_sitespecs,
    resolve_site_id,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SITES_DIR = REPO_ROOT / "configs" / "sites"
INSTANCE_PATH = SITES_DIR / "bukgu_gwangju.sitespec.json"

CANONICAL_ID = "bukgu_gwangju"
LEGACY_ID = "bukgu"


def _write_sitespec(
    tmp_path: Path,
    filename: str,
    site_id: str,
    legacy_ids: list[str],
) -> Path:
    """Write a realistic generic SiteSpec fixture (schema meaning preserved)."""
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
        "runtime": {"python_profile": site_id, "cloudflare_adapter": site_id},
        "clone": {
            "golden_commit": "0" * 40,
            "golden_commit_subject": "sample",
        },
    }
    path = tmp_path / f"{filename}.sitespec.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---- A. canonical direct lookup ----

def test_canonical_direct_lookup():
    doc = resolve_site_id(CANONICAL_ID)
    assert doc["site_id"] == CANONICAL_ID


def test_load_sitespecs_keyed_by_canonical_id():
    specs = load_sitespecs()
    assert CANONICAL_ID in specs
    assert specs[CANONICAL_ID]["site_id"] == CANONICAL_ID


# ---- B. legacy dual-read ----

def test_legacy_dual_read():
    doc = resolve_site_id(LEGACY_ID)
    assert doc["site_id"] == CANONICAL_ID


def test_canonical_and_legacy_resolve_to_same_site_id():
    resolver = SiteSpecResolver()
    canonical = resolver.resolve(CANONICAL_ID)
    legacy = resolver.resolve(LEGACY_ID)
    assert canonical["site_id"] == legacy["site_id"] == CANONICAL_ID
    assert canonical is legacy


# ---- C. unknown / invalid identifiers fail closed ----

def test_unknown_id_fail_closed():
    with pytest.raises(SiteSpecNotFoundError):
        resolve_site_id("unknown_site")


@pytest.mark.parametrize("identifier", ["", "   ", "\t", "\n"])
def test_empty_and_whitespace_id_fail_closed(identifier):
    with pytest.raises(SiteSpecNotFoundError):
        resolve_site_id(identifier)


def test_invalid_identifier_rejected():
    # Contains characters outside the canonical/legacy ID charset.
    with pytest.raises(SiteSpecNotFoundError):
        resolve_site_id("bukgu_gwangju/extra")


def test_display_label_not_resolved():
    # Display/institution labels are NOT site identifiers.
    with pytest.raises(SiteSpecNotFoundError):
        resolve_site_id("북구청")


def test_historical_alias_not_resolved():
    # Jurisdiction historical legal identity is NOT a site identifier.
    with pytest.raises(SiteSpecNotFoundError):
        resolve_site_id("광주광역시 북구")


# ---- D. collision policy (generic fixtures in temp dirs only) ----

def test_duplicate_canonical_id_rejected(tmp_path):
    _write_sitespec(tmp_path, "bukgu_gwangju", CANONICAL_ID, [LEGACY_ID])
    _write_sitespec(tmp_path, "second", CANONICAL_ID, ["second_legacy"])
    with pytest.raises(SiteSpecLoadError, match="duplicate canonical"):
        SiteSpecResolver(tmp_path)


def test_duplicate_legacy_alias_across_sitespecs_rejected(tmp_path):
    _write_sitespec(tmp_path, "bukgu_gwangju", CANONICAL_ID, [LEGACY_ID])
    _write_sitespec(tmp_path, "sample_city", "sample_city", [LEGACY_ID])
    with pytest.raises(SiteSpecLoadError, match="claimed by multiple"):
        SiteSpecResolver(tmp_path)


def test_canonical_vs_other_legacy_collision_rejected(tmp_path):
    _write_sitespec(tmp_path, "bukgu_gwangju", CANONICAL_ID, [LEGACY_ID])
    # Second SiteSpec claims the first SiteSpec's canonical ID as its own.
    _write_sitespec(tmp_path, "sample_city", LEGACY_ID, ["sample"])
    with pytest.raises(SiteSpecLoadError, match="collides with"):
        SiteSpecResolver(tmp_path)


def test_legacy_alias_colliding_with_canonical_rejected(tmp_path):
    _write_sitespec(tmp_path, "bukgu_gwangju", CANONICAL_ID, [LEGACY_ID])
    # Second SiteSpec uses the first SiteSpec's canonical ID as a legacy alias.
    _write_sitespec(tmp_path, "sample_city", "sample_city", [CANONICAL_ID])
    with pytest.raises(SiteSpecLoadError, match="collides with"):
        SiteSpecResolver(tmp_path)


# ---- E. empty legacy_ids ----

def test_empty_legacy_ids_loads(tmp_path):
    _write_sitespec(tmp_path, "bukgu_gwangju", CANONICAL_ID, [LEGACY_ID])
    _write_sitespec(tmp_path, "sample_city", "sample_city", [])
    resolver = SiteSpecResolver(tmp_path)
    assert resolver.resolve("sample_city")["site_id"] == "sample_city"
    assert resolver.resolve(LEGACY_ID)["site_id"] == CANONICAL_ID
    # A brand-new site with no aliases must still fail closed on unknown names.
    with pytest.raises(SiteSpecNotFoundError):
        resolver.resolve("sample")


# ---- F. deterministic load ----

def test_deterministic_independent_of_file_ordering(tmp_path):
    order_a = tmp_path / "order_a"
    order_b = tmp_path / "order_b"
    order_a.mkdir()
    order_b.mkdir()
    _write_sitespec(order_a, "bukgu_gwangju", CANONICAL_ID, [LEGACY_ID])
    _write_sitespec(order_a, "sample_city", "sample_city", ["sample"])
    # Same two fixtures written in reverse creation order.
    _write_sitespec(order_b, "sample_city", "sample_city", ["sample"])
    _write_sitespec(order_b, "bukgu_gwangju", CANONICAL_ID, [LEGACY_ID])
    resolver_a = SiteSpecResolver(order_a)
    resolver_b = SiteSpecResolver(order_b)
    assert resolver_a.canonical_ids == resolver_b.canonical_ids
    assert load_sitespecs(order_a) == load_sitespecs(order_b)
    assert resolver_a.resolve("sample")["site_id"] == resolver_b.resolve("sample")["site_id"]
