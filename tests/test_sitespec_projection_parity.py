"""Contract test for canonical SiteSpec projection parity (#1225-C).

Pure stdlib + pytest only. No network, no provider, no new runtime loader.

This phase is **projection parity / drift detection only** — it verifies that
the canonical SiteSpec instance and the existing system projections (Python
site profile, frozen compatibility registry, Cloudflare adapter identity,
golden metadata) intentionally agree, or intentionally disagree only as
declared legacy projections. No runtime wiring is introduced here.

Parity surface under test (Buk-gu):

| Concept                      | Canonical SiteSpec value  | Existing projection            |
|------------------------------|---------------------------|--------------------------------|
| canonical site_id            | ``bukgu_gwangju``         | Python profile ``site_id``     |
| legacy compatibility ID      | ``bukgu`` (legacy_ids)    | registry adapter / default ID  |
| Python profile projection    | ``runtime.python_profile``| profile ``site_id``            |
| Cloudflare adapter projection| ``runtime.cloudflare_adapter`` | registry adapter ``site_id``|
| public domain                | ``domains.public``        | profile ``base_url``/``allowed_domains`` |
| golden commit                | ``clone.golden_commit``   | registry adapter ``golden_commit`` |

The registry remains the frozen compatibility contract; this phase never
migrates ``configs/site-registry.json`` or any runtime path.
"""

import copy
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

from src.site_profiles import SiteProfileLoader
from src.site_profiles.sitespec import (
    SiteSpecNotFoundError,
    resolve_site_id,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SITESPEC_PATH = REPO_ROOT / "configs" / "sites" / "bukgu_gwangju.sitespec.json"
REGISTRY_PATH = REPO_ROOT / "configs" / "site-registry.json"
PROFILE_PATH = REPO_ROOT / "configs" / "sites" / "bukgu_gwangju.yml"

CANONICAL_ID = "bukgu_gwangju"
LEGACY_ADAPTER_ID = "bukgu"
PUBLIC_DOMAIN = "bukgu.gwangju.kr"
GOLDEN_COMMIT = "7217c0f738a6aa4468bdde3119d8c2d1ec9dd610"
HEX40 = re.compile(r"^[0-9a-f]{40}$")


# ----------------------------------------------------------------------
# Loading helpers (existing loaders only — no new runtime loader)
# ----------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    assert isinstance(doc, dict), f"{path.name}: not a JSON object"
    return doc


def _load_sitespec() -> dict:
    return _load_json(SITESPEC_PATH)


def _load_registry() -> dict:
    return _load_json(REGISTRY_PATH)


def _load_profile_dict() -> dict:
    """Load the real Python profile via the existing SiteProfileLoader."""
    profile = SiteProfileLoader().load_by_id(CANONICAL_ID)
    return {
        "site_id": profile.site_id,
        "base_url": profile.base_url,
        "allowed_domains": list(profile.allowed_domains),
    }


def _registry_adapter(registry: dict) -> dict:
    return registry["adapters"][0]


def _host_of(url: str) -> str:
    """Normalize a URL to its lowercase host (scheme/path/port ignored)."""
    netloc = urlparse(url).netloc
    return netloc.split(":")[0].strip().lower()


def _normalize_domain(value: str) -> str:
    """Normalize a domain entry to a lowercase host-only token.

    Handles both bare hosts (``bukgu.gwangju.kr``) and full URLs
    (``https://bukgu.gwangju.kr/``) so set comparison never misses on
    scheme/path/port differences.
    """
    v = value.strip().lower()
    if "://" in v:
        return _host_of(v)
    return v.split("/")[0].split(":")[0].strip().lower()


# ----------------------------------------------------------------------
# Pure parity helper (in-test only, mirrors the contract; not shipped)
# ----------------------------------------------------------------------


def parity_errors(
    sitespec: dict,
    registry: dict,
    profile: dict,
) -> list[str]:
    """Return a list of projection-parity violations (empty list = parity OK).

    A violation means the canonical SiteSpec and an existing projection
    disagree on an identity that must intentionally match. Display labels and
    jurisdiction historical aliases are deliberately never consulted here —
    they are not site identifiers, so they cannot satisfy parity.
    """
    errors: list[str] = []
    adapter = _registry_adapter(registry)
    spec_site_id = sitespec.get("site_id")
    legacy_ids = sitespec.get("legacy_ids", [])
    runtime = sitespec.get("runtime", {})
    public_domains = sitespec.get("domains", {}).get("public", [])
    clone = sitespec.get("clone", {})

    # A. Python profile identity
    profile_id = profile.get("site_id")
    if runtime.get("python_profile") != profile_id:
        errors.append(
            f"python_profile {runtime.get('python_profile')!r} != "
            f"profile site_id {profile_id!r}"
        )
    if profile_id != spec_site_id:
        errors.append(
            f"profile site_id {profile_id!r} != canonical site_id {spec_site_id!r}"
        )

    # B. Public domain parity — exact allowlist equality, no silent expansion.
    # The canonical SiteSpec public-domain set and the Python profile
    # allowed-domain set must be exactly equal; membership checks alone would
    # let an unexpected domain sneak into either allowlist undetected.
    spec_domains = {_normalize_domain(d) for d in public_domains}
    profile_domains = {
        _normalize_domain(d) for d in profile.get("allowed_domains", [])
    }
    if not spec_domains:
        errors.append("SiteSpec domains.public is empty")
    if spec_domains != profile_domains:
        errors.append(
            f"domain set mismatch: SiteSpec {sorted(spec_domains)!r} != "
            f"profile {sorted(profile_domains)!r}"
        )
    base_host = _host_of(profile.get("base_url", ""))
    if not base_host:
        errors.append("profile base_url has no host")
    elif base_host not in spec_domains:
        errors.append(
            f"profile base_url host {base_host!r} not in SiteSpec public-domain set"
        )

    # C. Compatibility registry projection
    adapter_id = adapter.get("site_id")
    if runtime.get("cloudflare_adapter") != adapter_id:
        errors.append(
            f"cloudflare_adapter {runtime.get('cloudflare_adapter')!r} != "
            f"registry adapter {adapter_id!r}"
        )
    if adapter_id not in legacy_ids:
        errors.append(
            f"registry adapter {adapter_id!r} not declared in SiteSpec legacy_ids"
        )

    # D. Default compatibility ID
    default_id = registry.get("default_site_id")
    if default_id not in legacy_ids:
        errors.append(
            f"registry default_site_id {default_id!r} is not a declared legacy alias"
        )

    # E. Golden parity
    if clone.get("golden_commit") != adapter.get("golden_commit"):
        errors.append(
            f"golden_commit {clone.get('golden_commit')!r} != "
            f"registry golden_commit {adapter.get('golden_commit')!r}"
        )

    return errors


# ----------------------------------------------------------------------
# A. Python profile identity
# ----------------------------------------------------------------------


def test_python_profile_identity_parity():
    spec = _load_sitespec()
    profile = _load_profile_dict()
    assert spec["runtime"]["python_profile"] == profile["site_id"] == CANONICAL_ID
    assert profile["site_id"] == spec["site_id"] == CANONICAL_ID


# ----------------------------------------------------------------------
# B. Public domain parity
# ----------------------------------------------------------------------


def test_public_domain_parity():
    """SiteSpec public-domain set == Python allowed-domain set (exact)."""
    spec = _load_sitespec()
    profile = _load_profile_dict()
    spec_domains = {_normalize_domain(d) for d in spec["domains"]["public"]}
    profile_domains = {
        _normalize_domain(d) for d in profile["allowed_domains"]
    }
    assert spec_domains == profile_domains == {PUBLIC_DOMAIN}
    # base_url host must be a member of the canonical public-domain set.
    assert _host_of(profile["base_url"]) in spec_domains


def test_canonical_public_domain_frozen_assertion():
    """Product-specific frozen fact: bukgu.gwangju.kr is the canonical public
    domain today.

    This is an explicit product assertion, not the parity mechanism — exact
    set equality is what detects allowlist drift. Keeping this assertion
    documents the frozen value without weakening parity detection.
    """
    spec = _load_sitespec()
    profile = _load_profile_dict()
    assert PUBLIC_DOMAIN in spec["domains"]["public"]
    assert PUBLIC_DOMAIN in profile["allowed_domains"]


# ----------------------------------------------------------------------
# C. Compatibility registry projection
# ----------------------------------------------------------------------


def test_registry_projection_parity():
    spec = _load_sitespec()
    registry = _load_registry()
    adapter = _registry_adapter(registry)
    assert spec["runtime"]["cloudflare_adapter"] == adapter["site_id"] == LEGACY_ADAPTER_ID
    # The registry's bukgu adapter is a declared legacy alias, not canonical.
    assert LEGACY_ADAPTER_ID in spec["legacy_ids"]
    assert LEGACY_ADAPTER_ID != spec["site_id"]


# ----------------------------------------------------------------------
# D. Default compatibility ID
# ----------------------------------------------------------------------


def test_default_compatibility_id_parity():
    spec = _load_sitespec()
    registry = _load_registry()
    assert registry["default_site_id"] == LEGACY_ADAPTER_ID
    assert registry["default_site_id"] in spec["legacy_ids"]


# ----------------------------------------------------------------------
# E. Golden parity
# ----------------------------------------------------------------------


def test_golden_parity():
    spec = _load_sitespec()
    registry = _load_registry()
    adapter = _registry_adapter(registry)
    assert spec["clone"]["golden_commit"] == adapter["golden_commit"] == GOLDEN_COMMIT
    assert HEX40.match(GOLDEN_COMMIT) is not None


# ----------------------------------------------------------------------
# F. Resolver parity (cross-contract, no resolver-test duplication)
# ----------------------------------------------------------------------


def test_resolver_cross_contract_parity():
    canonical = resolve_site_id(CANONICAL_ID)
    legacy = resolve_site_id(LEGACY_ADAPTER_ID)
    assert canonical["site_id"] == CANONICAL_ID
    assert legacy["site_id"] == CANONICAL_ID
    # Both reads project to the same canonical identity.
    assert canonical["site_id"] == legacy["site_id"]


def test_real_config_parity_clean():
    """The live Buk-gu config satisfies every parity contract."""
    assert parity_errors(_load_sitespec(), _load_registry(), _load_profile_dict()) == []


# ----------------------------------------------------------------------
# Fail-closed drift regressions (deep-copied configs only; product config
# files are never mutated)
# ----------------------------------------------------------------------


def test_drift_python_profile_mismatch_rejected():
    spec = _load_sitespec()
    spec = copy.deepcopy(spec)
    spec["runtime"]["python_profile"] = "other_site"
    errors = parity_errors(spec, _load_registry(), _load_profile_dict())
    assert any("python_profile" in e for e in errors), errors


def test_drift_profile_site_id_mismatch_rejected():
    profile = _load_profile_dict()
    profile = copy.deepcopy(profile)
    profile["site_id"] = "other_site"
    errors = parity_errors(_load_sitespec(), _load_registry(), profile)
    assert any("profile site_id" in e for e in errors), errors


def test_drift_registry_adapter_undeclared_rejected():
    spec = _load_sitespec()
    spec = copy.deepcopy(spec)
    spec["legacy_ids"] = []
    errors = parity_errors(spec, _load_registry(), _load_profile_dict())
    assert any("not declared in SiteSpec legacy_ids" in e for e in errors), errors


def test_drift_default_id_undeclared_rejected():
    registry = _load_registry()
    registry = copy.deepcopy(registry)
    registry["default_site_id"] = "undeclared_alias"
    errors = parity_errors(_load_sitespec(), registry, _load_profile_dict())
    assert any("default_site_id" in e for e in errors), errors


def test_drift_cloudflare_adapter_mismatch_rejected():
    spec = _load_sitespec()
    spec = copy.deepcopy(spec)
    spec["runtime"]["cloudflare_adapter"] = "other_adapter"
    errors = parity_errors(spec, _load_registry(), _load_profile_dict())
    assert any("cloudflare_adapter" in e for e in errors), errors


def test_drift_domain_mismatch_rejected():
    profile = _load_profile_dict()
    profile = copy.deepcopy(profile)
    profile["base_url"] = "https://other.example.kr/"
    errors = parity_errors(_load_sitespec(), _load_registry(), profile)
    assert any("base_url host" in e for e in errors), errors


def test_drift_extra_sitespec_public_domain_rejected():
    """An extra domain silently added to the SiteSpec allowlist must fail."""
    spec = _load_sitespec()
    spec = copy.deepcopy(spec)
    spec["domains"]["public"].append("unexpected.example")
    errors = parity_errors(spec, _load_registry(), _load_profile_dict())
    assert any("domain set mismatch" in e for e in errors), errors


def test_drift_extra_profile_allowed_domain_rejected():
    """An extra domain silently added to the Python allowlist must fail."""
    profile = _load_profile_dict()
    profile = copy.deepcopy(profile)
    profile["allowed_domains"].append("unexpected.example")
    errors = parity_errors(_load_sitespec(), _load_registry(), profile)
    assert any("domain set mismatch" in e for e in errors), errors


def test_drift_missing_canonical_domain_rejected():
    """Removing the canonical public domain from SiteSpec must fail."""
    spec = _load_sitespec()
    spec = copy.deepcopy(spec)
    spec["domains"]["public"] = ["other.example"]
    errors = parity_errors(spec, _load_registry(), _load_profile_dict())
    assert any("domain set mismatch" in e for e in errors), errors


def test_drift_mismatched_profile_allowed_domain_rejected():
    """Replacing the Python allowed-domain set with a different host must fail."""
    profile = _load_profile_dict()
    profile = copy.deepcopy(profile)
    profile["allowed_domains"] = ["other.example"]
    errors = parity_errors(_load_sitespec(), _load_registry(), profile)
    assert any("domain set mismatch" in e for e in errors), errors


def test_drift_golden_mismatch_rejected():
    spec = _load_sitespec()
    spec = copy.deepcopy(spec)
    spec["clone"]["golden_commit"] = "0" * 40
    errors = parity_errors(spec, _load_registry(), _load_profile_dict())
    assert any("golden_commit" in e for e in errors), errors


def test_display_label_not_identity():
    """Display labels are not site identifiers and never satisfy parity."""
    spec = _load_sitespec()
    labels = [spec["display"]["default_label"]]
    labels += list(spec["display"]["locale_labels"].values())
    for label in labels:
        assert label != spec["site_id"]
        assert label not in spec["legacy_ids"]
        with pytest.raises(SiteSpecNotFoundError):
            resolve_site_id(label)


def test_historical_jurisdiction_alias_not_identity():
    """Historical jurisdiction aliases are not runtime identifiers."""
    spec = _load_sitespec()
    aliases = [
        alias["value"] for alias in spec["jurisdiction"]["historical_aliases"]
    ]
    assert aliases, "fixture should carry a historical alias"
    for alias in aliases:
        assert alias != spec["site_id"]
        assert alias not in spec["legacy_ids"]
        with pytest.raises(SiteSpecNotFoundError):
            resolve_site_id(alias)
