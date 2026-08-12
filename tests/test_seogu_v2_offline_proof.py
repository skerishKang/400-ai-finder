"""Offline Seo-gu PRE-SITESPEC v2 candidate + onboarding-report proof (#1232).

Pure stdlib + pytest + yaml only. No live network / crawl / Firecrawl / API calls.
Reuses the generic legacy-profile -> v2 helper (src.site_profiles.legacy_profile_v2_projection)
which has NO site_id-specific branching. Reuses the Slice B onboarding-report semantic
validator to prove the generated report is a valid v2 report contract.

CONTRACT BOUNDARY: this artifact is a PRE-SITESPEC ONBOARDING CANDIDATE, not a final valid
SiteSpec v2. A real municipality (Seo-gu) with no checked-in canonical jurisdiction keeps
archetype=muncipality + state=review_required, an explicit source_or_provenance_gap exception,
and NO fabricated extensions.municipality.jurisdiction. It is intentionally NOT asserted as a
final valid SiteSpec via the authoritative Slice-B validator, and it is not promoted until the
required canonical typed extension is acquired.
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

# Reuse the authoritative Slice B semantic validators.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_platform_onboarding_report_contract import (  # noqa: E402
    ContractViolation,
    validate_onboarding_report,
)
from test_platform_site_spec_v2_contract import (  # noqa: E402
    ContractViolation as SitespecContractViolation,
    validate_site_spec_v2,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = REPO_ROOT / "configs" / "sites" / "seogu_gwangju.yml"
CANDIDATE_FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "platform" / "site-spec-v2" / "seogu_candidate.json"
)
REPORT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "platform" / "onboarding-report" / "seogu.json"
SOURCE_REF = "configs/sites/seogu_gwangju.yml"
STATIC_EVIDENCE_REF = "tests/test_seogu_profile_onboarding_no_live.py"
STATIC_EVIDENCE_PATH = REPO_ROOT / "tests" / "test_seogu_profile_onboarding_no_live.py"

# Checked-in no-live observed board evidence (from tests/test_seogu_profile_onboarding_no_live.py).
SEOgu_OBSERVED_EVIDENCE = [
    "https://www.seogu.gwangju.kr/bbs/BBSMSTR_000000000276/list.do",
    "https://www.seogu.gwangju.kr/boardDownload.es?bid=0013&list_no=136021&seq=1",
]


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
    cand = legacy_profile_to_v2_candidate(
        profile,
        source_ref=SOURCE_REF,
        observed_evidence=SEOgu_OBSERVED_EVIDENCE,
        observed_source_refs=[STATIC_EVIDENCE_REF],
    )
    report = legacy_profile_to_onboarding_report(
        cand,
        profile,
        source_ref=SOURCE_REF,
        run_id="seogu-v2-offline-2026-08-12",
    )
    return profile, cand, report


def _make_profile(site_id, name, base_url, allowed, **extra):
    p = {
        "site_id": site_id,
        "name": name,
        "base_url": base_url,
        "allowed_domains": allowed,
    }
    p.update(extra)
    return p


# ---- positive: determinism + frozen parity ----

def test_projection_is_deterministic():
    assert _project() == _project()


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
    # Observed-backed (detected) capabilities must reference the real checked-in evidence URL.
    for cap_id in ("notice_board", "document_library"):
        cap = next(c for c in cand["capabilities"] if c["id"] == cap_id)
        assert cap["state"] == "detected"
        assert "homepage" in cap["entry_points"]
        assert any("bbs/BBSMSTR" in ref or "boardDownload.es" in ref for ref in cap["evidence_refs"])
        # Observed-backed capability provenance also pins the static observed-evidence source.
        assert STATIC_EVIDENCE_REF in cap["evidence_refs"]
    # The keyword-only directory capability is review_required and not observed-backed.
    directory = next(c for c in cand["capabilities"] if c["id"] == "directory")
    assert directory["state"] == "review_required"
    assert directory["evidence_refs"] == [SOURCE_REF]


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
    assert cand["provenance"]["source_refs"] == [SOURCE_REF, STATIC_EVIDENCE_REF]


def test_candidate_provenance_includes_yaml_and_static_source():
    _, cand, _ = _project()
    refs = cand["provenance"]["source_refs"]
    assert refs == [SOURCE_REF, STATIC_EVIDENCE_REF]
    # Both the YAML profile and the checked-in static observed-evidence source.
    assert SOURCE_REF in refs
    assert STATIC_EVIDENCE_REF in refs


def test_report_input_and_provenance_include_yaml_and_static_source():
    _, _, report = _project()
    expected = [SOURCE_REF, STATIC_EVIDENCE_REF]
    assert report["input"]["source_refs"] == expected
    assert report["provenance"]["source_refs"] == expected


def test_seogu_observed_evidence_present_in_static_source():
    # The copied observed URLs must REALLY exist in the checked-in static evidence
    # source, so the proof cannot pass against a vanished/forged source.
    text = STATIC_EVIDENCE_PATH.read_text(encoding="utf-8")
    for url in SEOgu_OBSERVED_EVIDENCE:
        assert url in text, f"observed evidence {url!r} missing from {STATIC_EVIDENCE_PATH}"


def test_mixed_case_bbsmstr_evidence_is_detected():
    # Mixed-case observed URL must still bind notice_board (case-normalized compare).
    p = _make_profile(
        "m", "예시", "https://www.seogu.gwangju.kr/", ["www.seogu.gwangju.kr", "seogu.gwangju.kr"]
    )
    cand = legacy_profile_to_v2_candidate(
        p,
        source_ref="p",
        observed_evidence=["https://www.seogu.gwangju.kr/bbs/BBSMSTR_000000000276/list.do"],
        observed_source_refs=["static.src"],
    )
    assert any(c["id"] == "notice_board" and c["state"] == "detected" for c in cand["capabilities"])


def test_cross_domain_observed_list_do_rejected():
    p = _make_profile("x", "예시", "https://x.example.com/", ["x.example.com"])
    with pytest.raises(LegacyProfileProjectionError):
        legacy_profile_to_v2_candidate(
            p, source_ref="p", observed_evidence=["https://evil.example/list.do"]
        )


def test_cross_domain_observed_board_download_rejected():
    p = _make_profile("x", "예시", "https://x.example.com/", ["x.example.com"])
    with pytest.raises(LegacyProfileProjectionError):
        legacy_profile_to_v2_candidate(
            p,
            source_ref="p",
            observed_evidence=["https://evil.example/boardDownload.es?x=1"],
        )


def test_non_http_observed_evidence_rejected():
    p = _make_profile("x", "예시", "https://x.example.com/", ["x.example.com"])
    for bad in ("javascript:list.do", "ftp://x.example.com/bbs/list.do"):
        with pytest.raises(LegacyProfileProjectionError):
            legacy_profile_to_v2_candidate(
                p, source_ref="p", observed_evidence=[bad]
            )


def test_malformed_or_relative_observed_evidence_rejected():
    p = _make_profile("x", "예시", "https://x.example.com/", ["x.example.com"])
    for bad in ("/relative/list.do", "not a url", "http:///no-host/list.do"):
        with pytest.raises(LegacyProfileProjectionError):
            legacy_profile_to_v2_candidate(
                p, source_ref="p", observed_evidence=[bad]
            )


# ---- positive: onboarding report contract ----

def test_report_passes_slice_b_v2_report_contract():
    _, _, report = _project()
    assert validate_onboarding_report(report) is True
    assert validate_onboarding_report(_load_report_fixture()) is True


def test_report_ratios_sum_to_one():
    _, _, report = _project()
    m = report["metrics"]
    assert abs(m["automation_ratio"] + m["human_review_ratio"] + m["unsupported_ratio"] - 1.0) <= 1e-9


def test_report_promotion_and_authorization_false():
    _, cand, report = _project()
    assert report["promotion"]["production_promotion_requested"] is False
    assert report["acquisition"]["live_network_authorized"] is False
    assert cand["browser_policy"]["actual_site_control_authorized"] is False


def test_report_metric_values_for_seogu():
    _, _, report = _project()
    m = report["metrics"]
    assert m["automation_ratio"] == 0.5
    assert m["human_review_ratio"] == 0.25
    assert m["unsupported_ratio"] == 0.25


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


# ---- contract boundary: pre-SiteSpec candidate, not final valid SiteSpec ----

def test_seogu_candidate_is_pre_sitespec_not_final_valid():
    _, cand, _ = _project()
    # Authoritative Slice-B validator must REJECT (municipality w/o canonical jurisdiction
    # extension). This proves the artifact is NOT claimed to be a final valid SiteSpec v2.
    with pytest.raises(SitespecContractViolation):
        validate_site_spec_v2(cand)


def test_pre_sitespec_not_promoted_before_canonical_extension():
    _, cand, report = _project()
    assert report["promotion"]["production_promotion_requested"] is False
    # Still a candidate: no fabricated municipality extension.
    assert cand["extensions"] == {}


# ---- genericity: helper has no seogu-specific branching ----

def test_helper_is_generic_no_site_id_branch():
    university = _make_profile(
        "x_univ", "예시대학교", "https://x.ac.kr/", ["x.ac.kr"],
        classification="UNIVERSITY", observed_evidence=["https://x.ac.kr/bbs/BBSMSTR_1/list.do"],
    )
    cand = legacy_profile_to_v2_candidate(
        university, source_ref="p", observed_evidence=["https://x.ac.kr/bbs/BBSMSTR_1/list.do"],
        observed_source_refs=["static.src"],
    )
    assert cand["archetype"]["id"] == "university"
    assert cand["archetype"]["state"] == "detected"

    unknown = _make_profile("y_corp", "예시회사", "https://y.example.com/", ["y.example.com"])
    cand2 = legacy_profile_to_v2_candidate(unknown, source_ref="p")
    # unknown archetype -> id=unknown AND state=unknown
    assert cand2["archetype"]["id"] == "unknown"
    assert cand2["archetype"]["state"] == "unknown"


# ---- negative matrix (fail closed) ----

def test_A_document_extensions_alone_not_detected():
    p = _make_profile("a", "예시", "https://a.example.com/", ["a.example.com"],
                      document_extensions=["pdf", "hwp"])
    cand = legacy_profile_to_v2_candidate(p, source_ref="p")
    assert not any(c["id"] == "document_library" for c in cand["capabilities"])


def test_B_notice_keyword_alone_not_detected():
    p = _make_profile("b", "예시", "https://b.example.com/", ["b.example.com"],
                      important_keywords=["공지사항", "고시공고"])
    cand = legacy_profile_to_v2_candidate(p, source_ref="p")
    assert not any(c["id"] == "notice_board" for c in cand["capabilities"])


def test_C_observed_bbs_list_url_enables_notice_board():
    p = _make_profile("c", "예시", "https://c.example.com/", ["c.example.com"])
    cand = legacy_profile_to_v2_candidate(
        p, source_ref="p", observed_evidence=["https://c.example.com/bbs/BBSMSTR_1/list.do"],
        observed_source_refs=["static.src"],
    )
    assert any(c["id"] == "notice_board" and c["state"] == "detected" for c in cand["capabilities"])


def test_D_observed_download_url_enables_document_library():
    p = _make_profile("d", "예시", "https://d.example.com/", ["d.example.com"])
    cand = legacy_profile_to_v2_candidate(
        p, source_ref="p", observed_evidence=["https://d.example.com/boardDownload.es?x=1"],
        observed_source_refs=["static.src"],
    )
    assert any(c["id"] == "document_library" and c["state"] == "detected" for c in cand["capabilities"])


def test_E_unknown_archetype_unknown_state():
    p = _make_profile("e", "예시회사", "https://e.example.com/", ["e.example.com"])
    cand = legacy_profile_to_v2_candidate(p, source_ref="p")
    assert cand["archetype"]["id"] == "unknown"
    assert cand["archetype"]["state"] == "unknown"


def test_F_unknown_no_capabilities_report_no_crash_ratios_sum_one():
    p = _make_profile("f", "예시회사", "https://f.example.com/", ["f.example.com"])
    cand = legacy_profile_to_v2_candidate(p, source_ref="p")
    report = legacy_profile_to_onboarding_report(cand, p, source_ref="p", run_id="r")
    m = report["metrics"]
    assert abs(m["automation_ratio"] + m["human_review_ratio"] + m["unsupported_ratio"] - 1.0) <= 1e-9
    # zero-denominator handling: everything unsupported
    assert m["unsupported_ratio"] == 1.0


def test_G_non_municipality_no_fake_jurisdiction_accounting_slot():
    p = _make_profile("g_univ", "예시대학교", "https://g.ac.kr/", ["g.ac.kr"],
                      classification="UNIVERSITY")
    cand = legacy_profile_to_v2_candidate(
        p, source_ref="p", observed_evidence=["https://g.ac.kr/bbs/BBSMSTR_1/list.do"],
        observed_source_refs=["static.src"],
    )
    report = legacy_profile_to_onboarding_report(cand, p, source_ref="p", run_id="r")
    assert cand["archetype"]["id"] == "university"
    # No fabricated jurisdiction gap for a non-municipality site.
    assert not any(e["category"] == "source_or_provenance_gap" for e in report["exceptions"])
    m = report["metrics"]
    # 1 detected capability, no review, no gap -> automation 1.0
    assert m["automation_ratio"] == 1.0
    assert m["human_review_ratio"] == 0.0
    assert m["unsupported_ratio"] == 0.0
    assert abs(m["automation_ratio"] + m["human_review_ratio"] + m["unsupported_ratio"] - 1.0) <= 1e-9


def test_H_slice_b_validator_unchanged_rejects_candidate():
    # The authoritative Slice-B validator must still reject the pre-SiteSpec candidate,
    # i.e. it was not weakened.
    _, cand, _ = _project()
    with pytest.raises(SitespecContractViolation):
        validate_site_spec_v2(cand)


def test_I_seogu_jurisdiction_unfabricated():
    _, cand, _ = _project()
    assert cand["extensions"] == {}


# ---- input safety ----

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
    legacy_profile_to_v2_candidate(
        profile,
        source_ref=SOURCE_REF,
        observed_evidence=SEOgu_OBSERVED_EVIDENCE,
        observed_source_refs=[STATIC_EVIDENCE_REF],
    )
    assert profile == snapshot


def test_only_local_static_source_used():
    assert YAML_PATH.exists()
    assert str(YAML_PATH).endswith("configs/sites/seogu_gwangju.yml")


# ---- provenance coupling (fail closed) for observed evidence (REQUIRED A-H) ----

def test_A_observed_list_url_without_source_refs_rejected():
    # A valid observed list.do URL but observed_source_refs omitted -> reject.
    p = _make_profile("a", "예시", "https://a.example.com/", ["a.example.com"])
    with pytest.raises(LegacyProfileProjectionError):
        legacy_profile_to_v2_candidate(
            p,
            source_ref="p",
            observed_evidence=["https://a.example.com/bbs/BBSMSTR_1/list.do"],
        )


def test_B_observed_download_url_with_empty_source_refs_rejected():
    # A valid observed download URL but observed_source_refs=[] -> reject.
    p = _make_profile("b", "예시", "https://b.example.com/", ["b.example.com"])
    with pytest.raises(LegacyProfileProjectionError):
        legacy_profile_to_v2_candidate(
            p,
            source_ref="p",
            observed_evidence=["https://b.example.com/boardDownload.es?x=1"],
            observed_source_refs=[],
        )


def test_C_blank_observed_source_ref_rejected():
    p = _make_profile("c", "예시", "https://c.example.com/", ["c.example.com"])
    for bad in ([""], ["   "]):
        with pytest.raises(LegacyProfileProjectionError):
            legacy_profile_to_v2_candidate(
                p,
                source_ref="p",
                observed_evidence=["https://c.example.com/bbs/BBSMSTR_1/list.do"],
                observed_source_refs=bad,
            )


def test_D_non_string_observed_source_ref_rejected():
    p = _make_profile("d", "예시", "https://d.example.com/", ["d.example.com"])
    for bad in ([123], [None]):
        with pytest.raises(LegacyProfileProjectionError):
            legacy_profile_to_v2_candidate(
                p,
                source_ref="p",
                observed_evidence=["https://d.example.com/bbs/BBSMSTR_1/list.do"],
                observed_source_refs=bad,
            )


def test_E_report_input_source_refs_parity_with_candidate():
    _, cand, report = _project()
    cand_refs = cand["provenance"]["source_refs"]
    assert report["input"]["source_refs"] == cand_refs
    assert cand_refs == [SOURCE_REF, STATIC_EVIDENCE_REF]


def test_F_report_provenance_source_refs_parity_with_candidate():
    _, cand, report = _project()
    cand_refs = cand["provenance"]["source_refs"]
    assert report["provenance"]["source_refs"] == cand_refs
    assert cand_refs == [SOURCE_REF, STATIC_EVIDENCE_REF]


def test_G_report_cannot_inject_different_provenance():
    # The report function must NOT accept a separate observed_source_refs argument,
    # so a caller cannot produce provenance that drifts from the candidate.
    import inspect

    params = inspect.signature(legacy_profile_to_onboarding_report).parameters
    assert "observed_source_refs" not in params

    _, cand, report = _project()
    cand_refs = cand["provenance"]["source_refs"]
    # Whatever the candidate provenance is, the report must echo it exactly in both
    # locations, with no separately-authored value injected.
    assert report["input"]["source_refs"] == cand_refs
    assert report["provenance"]["source_refs"] == cand_refs
    # And the report cannot add anything beyond the candidate's own provenance.
    assert set(report["input"]["source_refs"]) == set(cand_refs)


def test_H_malformed_candidate_provenance_rejects_report():
    _, cand, _ = _project()
    # Provenance object missing -> reject.
    broken = copy.deepcopy(cand)
    del broken["provenance"]
    with pytest.raises(LegacyProfileProjectionError):
        legacy_profile_to_onboarding_report(
            broken, _load_yaml(), source_ref=SOURCE_REF, run_id="r"
        )

    # Provenance with empty/missing source_refs -> reject.
    for bad_refs in ([], None):
        broken = copy.deepcopy(cand)
        broken["provenance"] = {"source_refs": bad_refs, "review_state": "synthetic"}
        with pytest.raises(LegacyProfileProjectionError):
            legacy_profile_to_onboarding_report(
                broken, _load_yaml(), source_ref=SOURCE_REF, run_id="r"
            )

    # Provenance with a blank/whitespace source ref -> reject.
    broken = copy.deepcopy(cand)
    broken["provenance"] = {"source_refs": [SOURCE_REF, "  "], "review_state": "synthetic"}
    with pytest.raises(LegacyProfileProjectionError):
        legacy_profile_to_onboarding_report(
            broken, _load_yaml(), source_ref=SOURCE_REF, run_id="r"
        )

    # source_ref not present in candidate provenance -> reject.
    broken = copy.deepcopy(cand)
    broken["provenance"] = {"source_refs": [STATIC_EVIDENCE_REF], "review_state": "synthetic"}
    with pytest.raises(LegacyProfileProjectionError):
        legacy_profile_to_onboarding_report(
            broken, _load_yaml(), source_ref=SOURCE_REF, run_id="r"
        )
