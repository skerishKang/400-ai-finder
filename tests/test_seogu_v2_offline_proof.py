"""Offline Seo-gu v2 candidate + onboarding-report proof (#1232).

Pure stdlib + pytest + yaml only. No live network / crawl / Firecrawl / API calls.
Reuses the generic legacy-profile -> v2 helper (src.site_profiles.legacy_profile_v2_projection)
which has NO site_id-specific branching. Reuses the Slice B onboarding-report semantic
validator to prove the generated report is a valid v2 report contract.

This is a CANDIDATE proof: a real municipality (Seo-gu) that has no checked-in canonical
jurisdiction keeps archetype=muncipality with state=review_required, an explicit
source_or_provenance_gap exception, and NO fabricated extensions.municipality.jurisdiction.
"""

import copy
import json
import sys
from pathlib import Path

import pytest
import yaml

from src.site_profiles.legacy_profile_v2_projection import (
    LegacyProfileProjectionError,
    legacy_profile_to_onboarding_report,
    legacy_profile_to_v2_candidate,
)

# Reuse the authoritative Slice B onboarding-report semantic validator.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_platform_onboarding_report_contract import (  # noqa: E402
    ContractViolation,
    validate_onboarding_report,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = REPO_ROOT / "configs" / "sites" / "seogu_gwangju.yml"
CANDIDATE_FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "platform" / "site-spec-v2" / "seogu_candidate.json"
)
REPORT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "platform" / "onboarding-report" / "seogu.json"
SOURCE_REF = "configs/sites/seogu_gwangju.yml"


def _load_yaml():
    with open(YAML_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_candidate_fixture():
    with open(CANDIDATE_FIXTURE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_report_fixture():
    with open(REPORT_FIXTURE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _project():
    profile = _load_yaml()
    cand = legacy_profile_to_v2_candidate(profile, source_ref=SOURCE_REF)
    report = legacy_profile_to_onboarding_report(
        cand, profile, source_ref=SOURCE_REF, run_id="seogu-v2-offline-2026-08-12"
    )
    return profile, cand, report


# ---- positive: determinism + frozen parity ----

def test_projection_is_deterministic():
    p1 = _project()
    p2 = _project()
    assert p1 == p2


def test_candidate_matches_frozen_fixture():
    _, cand, _ = _project()
    assert cand == _load_candidate_fixture()


def test_report_matches_frozen_fixture():
    _, _, report = _project()
    assert report == _load_report_fixture()


# ---- positive: candidate invariants ----

def test_schema_version_is_v2():
    _, cand, _ = _project()
    assert cand["schema_version"] == "2.0.0"


def test_site_id_and_display_parity():
    profile, cand, _ = _project()
    assert cand["identity"]["site_id"] == profile["site_id"] == "seogu_gwangju"
    assert cand["identity"]["display"]["default_label"] == profile["name"]


def test_domains_public_exact_parity():
    profile, cand, _ = _project()
    assert cand["domains"]["public"] == profile["allowed_domains"]


def test_homepage_from_base_url_host_declared():
    from urllib.parse import urlsplit

    profile, cand, _ = _project()
    ep = cand["entry_points"][0]
    assert ep["id"] == "homepage"
    assert ep["url"] == profile["base_url"]
    host = urlsplit(ep["url"]).hostname
    assert host in cand["domains"]["public"]


def test_archetype_municipality_review_required_no_fabricated_jurisdiction():
    _, cand, _ = _project()
    arch = cand["archetype"]
    assert arch["id"] == "municipality"
    assert arch["state"] == "review_required"
    assert 0.0 <= arch["confidence"] <= 1.0
    # No fabricated canonical municipality jurisdiction in the v2 core.
    assert cand["extensions"] == {}


def test_evidence_backed_notice_and_document_capabilities():
    _, cand, _ = _project()
    cap_ids = {c["id"] for c in cand["capabilities"]}
    assert "notice_board" in cap_ids
    assert "document_library" in cap_ids
    for cap in cand["capabilities"]:
        # every capability references the declared homepage and a real source ref
        assert "homepage" in cap["entry_points"]
        assert SOURCE_REF in cap["evidence_refs"]
        assert cap["state"] in ("configured", "detected", "unsupported", "review_required", "not_detected")


def test_org_chart_keyword_only_is_review_required():
    _, cand, _ = _project()
    directory = next((c for c in cand["capabilities"] if c["id"] == "directory"), None)
    assert directory is not None
    assert directory["state"] == "review_required"
    assert directory["confidence"] < 0.5


def test_policy_defaults_are_fail_closed():
    _, cand, _ = _project()
    assert cand["capture_policy"] == {
        "acquisition_mode": "offline_fixture",
        "live_network_authorized": False,
    }
    assert cand["browser_policy"] == {
        "surface_mode": "generated_preview",
        "actual_site_control_authorized": False,
    }
    assert cand["knowledge_policy"] == {
        "grounding_required": True,
        "provenance_required": True,
    }
    assert cand["action_policy"] == {
        "external_write_authorized": False,
        "high_risk_actions_authorized": False,
    }


def test_provenance_uses_only_checked_in_source():
    _, cand, _ = _project()
    assert cand["provenance"]["source_refs"] == [SOURCE_REF]


# ---- positive: onboarding report contract ----

def test_report_passes_slice_b_v2_contract():
    _, _, report = _project()
    assert validate_onboarding_report(report) is True
    assert validate_onboarding_report(_load_report_fixture()) is True


def test_report_ratios_sum_to_one():
    _, _, report = _project()
    m = report["metrics"]
    total = m["automation_ratio"] + m["human_review_ratio"] + m["unsupported_ratio"]
    assert abs(total - 1.0) <= 1e-9


def test_report_promotion_and_authorization_false():
    _, cand, report = _project()
    assert report["promotion"]["production_promotion_requested"] is False
    assert report["acquisition"]["live_network_authorized"] is False
    # actual_site_control_authorized lives on the candidate browser_policy
    assert cand["browser_policy"]["actual_site_control_authorized"] is False


def test_missing_canonical_jurisdiction_is_source_or_provenance_gap():
    _, _, report = _project()
    cats = {e["category"] for e in report["exceptions"]}
    assert "source_or_provenance_gap" in cats
    gap = next(e for e in report["exceptions"] if e["category"] == "source_or_provenance_gap")
    assert gap["severity"] == "warning"
    assert gap["review_state"] == "review_required"


def test_org_chart_keyword_only_has_explicit_exception():
    _, _, report = _project()
    assert any(
        e["category"] == "low_confidence_classification" and "directory" in e["affected_refs"]
        for e in report["exceptions"]
    )


# ---- genericity: helper has no seogu-specific branching ----

def test_helper_is_generic_no_site_id_branch():
    university = {
        "site_id": "x_univ",
        "name": "예시대학교",
        "base_url": "https://x.ac.kr/",
        "allowed_domains": ["x.ac.kr"],
        "classification": "UNIVERSITY",
        "important_keywords": ["공지사항"],
        "board_patterns": ["list.do"],
        "document_extensions": ["pdf"],
    }
    cand = legacy_profile_to_v2_candidate(university, source_ref="p")
    assert cand["archetype"]["id"] == "university"
    assert cand["archetype"]["state"] == "detected"

    unknown = {
        "site_id": "y_corp",
        "name": "예시회사",
        "base_url": "https://y.example.com/",
        "allowed_domains": ["y.example.com"],
    }
    cand2 = legacy_profile_to_v2_candidate(unknown, source_ref="p")
    assert cand2["archetype"]["id"] == "unknown"


# ---- negative matrix (fail closed) ----

def test_undeclared_homepage_host_rejected():
    profile = copy.deepcopy(_load_yaml())
    profile["base_url"] = "https://evil.example.com/"
    with pytest.raises(LegacyProfileProjectionError):
        legacy_profile_to_v2_candidate(profile, source_ref=SOURCE_REF)


def test_missing_base_url_rejected():
    profile = copy.deepcopy(_load_yaml())
    del profile["base_url"]
    with pytest.raises(LegacyProfileProjectionError):
        legacy_profile_to_v2_candidate(profile, source_ref=SOURCE_REF)


def test_original_profile_not_mutated():
    profile = _load_yaml()
    snapshot = copy.deepcopy(profile)
    legacy_profile_to_v2_candidate(profile, source_ref=SOURCE_REF)
    assert profile == snapshot


# ---- no-live guard ----

def test_only_local_static_source_used():
    # The only source is a checked-in YAML file under configs/sites; no network call.
    assert YAML_PATH.exists()
    assert str(YAML_PATH).endswith("configs/sites/seogu_gwangju.yml")
