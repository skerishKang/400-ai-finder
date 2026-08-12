"""Buk-gu v1 -> SiteSpec v2 offline projection parity tests (#1287 Slice C).

Pure stdlib + pytest only. No network, no provider, no Firecrawl.

This proves the current Buk-gu v1 canonical SiteSpec + YAML operational profile can be
deterministically projected into a generic SiteSpec v2 object without any resident runtime
switch, Cloudflare wiring, capability detection, live network, or Production promotion.

The projected output is also checked against the Slice B v2 semantic contract by reusing
``validate_site_spec_v2`` from the Slice B test module (not by moving the validator into
runtime).
"""

import copy
import json
import sys
from pathlib import Path

import pytest
import yaml

from src.site_profiles.sitespec_v2_projection import (
    ProjectionError,
    extract_v1_compatibility_metadata,
    project_v1_sitespec_to_v2,
)

# Reuse the authoritative Slice B v2 semantic validator without moving it into runtime.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_platform_site_spec_v2_contract import (  # noqa: E402
    ContractViolation,
    validate_site_spec_v2,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
V1_PATH = REPO_ROOT / "configs" / "sites" / "bukgu_gwangju.sitespec.json"
YAML_PATH = REPO_ROOT / "configs" / "sites" / "bukgu_gwangju.yml"
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "platform" / "site-spec-v2" / "bukgu_projected.json"
)
V1_SOURCE_REF = "configs/sites/bukgu_gwangju.sitespec.json"
PROFILE_SOURCE_REF = "configs/sites/bukgu_gwangju.yml"


def _load_v1():
    with open(V1_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_yaml():
    with open(YAML_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_fixture():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _project(v1=None, yaml_profile=None):
    v1 = _load_v1() if v1 is None else v1
    yaml_profile = _load_yaml() if yaml_profile is None else yaml_profile
    return project_v1_sitespec_to_v2(
        v1,
        yaml_profile,
        v1_source_ref=V1_SOURCE_REF,
        profile_source_ref=PROFILE_SOURCE_REF,
    )


# ---- positive ----

def test_projection_is_deterministic():
    a = _project()
    b = _project()
    assert a == b


def test_output_equals_frozen_fixture():
    assert _project() == _load_fixture()


def test_schema_version_is_v2():
    assert _project()["schema_version"] == "2.0.0"


def test_canonical_site_id_exact_parity():
    assert _project()["identity"]["site_id"] == _load_v1()["site_id"] == "bukgu_gwangju"


def test_legacy_alias_exact_parity():
    assert _project()["identity"]["legacy_ids"] == _load_v1()["legacy_ids"]


def test_display_exact_parity():
    assert _project()["identity"]["display"] == _load_v1()["display"]


def test_domains_public_exact_parity():
    assert _project()["domains"]["public"] == _load_v1()["domains"]["public"]


def test_homepage_comes_from_yaml_base_url():
    out = _project()
    assert out["entry_points"][0]["url"] == _load_yaml()["base_url"]


def test_homepage_host_in_v1_public_domains():
    from urllib.parse import urlsplit

    out = _project()
    host = urlsplit(out["entry_points"][0]["url"]).hostname
    assert host in _load_v1()["domains"]["public"]


def test_yaml_allowed_domains_consistent_with_v1():
    v1_public = set(_load_v1()["domains"]["public"])
    yaml_allowed = set(_load_yaml()["allowed_domains"])
    assert v1_public == yaml_allowed


def test_municipality_jurisdiction_lossless_parity():
    out = _project()
    assert out["extensions"]["municipality"]["jurisdiction"] == _load_v1()["jurisdiction"]


def test_archetype_municipality_configured():
    arch = _project()["archetype"]
    assert arch["id"] == "municipality"
    assert arch["state"] == "configured"
    assert arch["confidence"] == 1.0


def test_capabilities_empty():
    assert _project()["capabilities"] == []


def test_no_live_network_authorization():
    out = _project()
    assert out["capture_policy"]["live_network_authorized"] is False
    assert out["action_policy"]["external_write_authorized"] is False
    assert out["action_policy"]["high_risk_actions_authorized"] is False


def test_no_actual_site_control_authorization():
    assert _project()["browser_policy"]["actual_site_control_authorized"] is False


def test_provenance_has_exact_two_source_refs():
    refs = _project()["provenance"]["source_refs"]
    assert refs == [V1_SOURCE_REF, PROFILE_SOURCE_REF]


def test_runtime_clone_absent_from_v2_core():
    out = _project()
    assert "runtime" not in out
    assert "clone" not in out
    for group in out.values():
        if isinstance(group, dict):
            assert "runtime" not in group
            assert "clone" not in group


def test_v1_runtime_clone_compatibility_metadata_unchanged():
    compat = extract_v1_compatibility_metadata(_load_v1())
    v1 = _load_v1()
    assert compat["runtime"]["python_profile"] == v1["runtime"]["python_profile"]
    assert compat["runtime"]["cloudflare_adapter"] == v1["runtime"]["cloudflare_adapter"]
    assert compat["clone"]["golden_commit"] == v1["clone"]["golden_commit"]
    assert compat["clone"]["golden_commit_subject"] == v1["clone"]["golden_commit_subject"]


def test_original_inputs_not_mutated():
    v1_before = _load_v1()
    yaml_before = _load_yaml()
    v1_snapshot = copy.deepcopy(v1_before)
    yaml_snapshot = copy.deepcopy(yaml_before)
    _project(v1_before, yaml_before)
    assert v1_before == v1_snapshot
    assert yaml_before == yaml_snapshot


def test_projected_output_satisfies_slice_b_v2_contract():
    # Reuse the Slice B semantic validator to prove the projection is a valid v2 contract.
    assert validate_site_spec_v2(_project()) is True
    assert validate_site_spec_v2(_load_fixture()) is True


# ---- negative matrix (fail closed) ----

def test_mismatched_identity_rejected():
    yaml_profile = copy.deepcopy(_load_yaml())
    yaml_profile["site_id"] = "not_bukgu"
    with pytest.raises(ProjectionError):
        _project(yaml_profile=yaml_profile)


def test_undeclared_homepage_host_rejected():
    yaml_profile = copy.deepcopy(_load_yaml())
    yaml_profile["base_url"] = "https://evil.example.com/"
    with pytest.raises(ProjectionError):
        _project(yaml_profile=yaml_profile)


def test_yaml_allowed_domain_drift_rejected():
    yaml_profile = copy.deepcopy(_load_yaml())
    yaml_profile["allowed_domains"] = ["evil.example.com"]
    with pytest.raises(ProjectionError):
        _project(yaml_profile=yaml_profile)


def test_malformed_non_http_homepage_rejected():
    yaml_profile = copy.deepcopy(_load_yaml())
    yaml_profile["base_url"] = "ftp://bukgu.gwangju.kr/"
    with pytest.raises(ProjectionError):
        _project(yaml_profile=yaml_profile)


def test_missing_jurisdiction_rejected():
    v1 = copy.deepcopy(_load_v1())
    del v1["jurisdiction"]
    with pytest.raises(ProjectionError):
        _project(v1=v1)


def test_missing_required_runtime_compatibility_data_rejected():
    v1 = copy.deepcopy(_load_v1())
    del v1["runtime"]
    with pytest.raises(ProjectionError):
        extract_v1_compatibility_metadata(v1)
