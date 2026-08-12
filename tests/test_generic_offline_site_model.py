"""Offline generic Site Model bundle tests (#1232).

Pure stdlib + pytest. No network / provider / Firecrawl / API calls. Reuses the
checked-in Seo-gu pre-SiteSpec v2 candidate (tests/fixtures/platform/site-spec-v2/
seogu_candidate.json) and the checked-in static homepage HTML + URL sets from
tests/test_seogu_profile_onboarding_no_live.py.

The in-memory homepage_map is built purely from HomepageMapper.extract_menu_links
(no live fetch). The bundle is produced by the generic
src.site_profiles.offline_site_model.build_offline_site_model_bundle helper, which
has no site-id-specific branching.
"""

import copy
import json
from pathlib import Path

import pytest
from src.crawler.homepage_mapper import HomepageMapper
from src.site_profiles.offline_site_model import (
    OfflineSiteModelError,
    build_offline_site_model_bundle,
)

from tests.test_seogu_profile_onboarding_no_live import (
    SEOGU_DENY_URLS,
    SEOGU_HOMEPAGE_HTML,
    SEOGU_SURVIVE_URLS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "platform" / "site-spec-v2" / "seogu_candidate.json"
)
MODEL_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "platform" / "site-model" / "seogu.json"

HOMEPAGE_BASE = "https://www.seogu.gwangju.kr/"
SOURCE_REF = "configs/sites/seogu_gwangju.yml"
STATIC_EVIDENCE_REF = "tests/test_seogu_profile_onboarding_no_live.py"


def _load_candidate():
    with open(CANDIDATE_FIXTURE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_model_fixture():
    with open(MODEL_FIXTURE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _build_homepage_map():
    # Pure path: no network. extract_menu_links is a @staticmethod with a stray
    # `self` parameter, so a placeholder first arg fills it (homepage_mapper.py is
    # a protected file and must not be modified).
    nav, att = HomepageMapper.extract_menu_links(
        None, SEOGU_HOMEPAGE_HTML, HOMEPAGE_BASE
    )
    return {
        "base_url": HOMEPAGE_BASE,
        "sitemap": {
            "candidates": [],
            "found": [],
            "url_count": 0,
            "urls": [],
            "errors": [],
        },
        "homepage": {
            "title": "광주광역시 서구청",
            "description": "서구청 공식 홈페이지",
            "navigation_links": nav,
            "attachment_links": att,
            "errors": [],
        },
        "categories": {},
        "stats": {},
        "errors": [],
    }


def _build():
    cand = _load_candidate()
    hp_map = _build_homepage_map()
    return build_offline_site_model_bundle(
        cand,
        hp_map,
        homepage_map_source_ref=STATIC_EVIDENCE_REF,
        capture_urls=SEOGU_SURVIVE_URLS,
    )


# --------------------------------------------------------------------------- #
# Positive: determinism + frozen parity
# --------------------------------------------------------------------------- #


def test_bundle_is_deterministic():
    assert _build() == _build()


def test_bundle_matches_frozen_fixture():
    assert _build() == _load_model_fixture()


def test_input_candidate_not_mutated():
    cand = _load_candidate()
    snapshot = copy.deepcopy(cand)
    _build()
    assert cand == snapshot


def test_input_homepage_map_not_mutated():
    hp_map = _build_homepage_map()
    snapshot = copy.deepcopy(hp_map)
    _build()
    assert hp_map == snapshot


# --------------------------------------------------------------------------- #
# Positive: identity / provenance parity
# --------------------------------------------------------------------------- #


def test_site_id_parity():
    bundle = _build()
    assert bundle["site_id"] == "seogu_gwangju"
    assert bundle["site_model"]["site_id"] == "seogu_gwangju"
    assert bundle["qa_manifest"]["site_id"] == "seogu_gwangju"


def test_provenance_parity():
    bundle = _build()
    expected = [SOURCE_REF, STATIC_EVIDENCE_REF]
    assert bundle["provenance"]["source_refs"] == expected
    assert bundle["capture_plan"]["source_refs"] == expected
    assert bundle["qa_manifest"]["source_refs"] == expected


def test_root_route_from_candidate_homepage():
    bundle = _build()
    routes = bundle["site_model"]["routes"]
    root = next(r for r in routes if r["route_id"] == "route-homepage")
    assert root["url"] == "https://www.seogu.gwangju.kr/"
    assert root["document_id"] is None


def test_captured_urls_exactly_bounded():
    bundle = _build()
    captured = bundle["capture_plan"]["captured_urls"]
    # Exactly the 9 checked-in survive URLs, no more, no less.
    assert len(captured) == len(SEOGU_SURVIVE_URLS)
    assert set(captured) == set(SEOGU_SURVIVE_URLS)


def test_denied_urls_absent():
    bundle = _build()
    captured = bundle["capture_plan"]["captured_urls"]
    for denied in SEOGU_DENY_URLS:
        assert denied not in captured
    # Denied URLs must not model any route either.
    route_urls = {r["url"] for r in bundle["site_model"]["routes"]}
    for denied in SEOGU_DENY_URLS:
        assert denied not in route_urls


def test_document_indexer_doc_ids_preserved():
    bundle = _build()
    docs = bundle["site_model"]["documents"]
    assert [d["id"] for d in docs] == [f"doc-{i:06d}" for i in range(1, len(docs) + 1)]
    # Key inventory fields preserved from DocumentIndexer output.
    for d in docs:
        assert d["canonical_url"]
        assert isinstance(d["source_types"], list)
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"].get("discovered_from"), list)
        assert isinstance(d["metadata"].get("link_texts"), list)


def test_route_ids_deterministic():
    bundle = _build()
    routes = bundle["site_model"]["routes"]
    non_root = [r for r in routes if r["route_id"] != "route-homepage"]
    assert len(non_root) == len(bundle["site_model"]["documents"])
    for i, r in enumerate(non_root, start=1):
        assert r["route_id"] == f"route-{i:06d}"
        assert r["document_id"] == f"doc-{i:06d}"


def test_every_non_root_route_resolves_document_id():
    bundle = _build()
    doc_ids = {d["id"] for d in bundle["site_model"]["documents"]}
    for r in bundle["site_model"]["routes"]:
        if r["route_id"] == "route-homepage":
            assert r["document_id"] is None
            continue
        assert r["document_id"] in doc_ids


def test_every_document_route_exact_allowed_host():
    bundle = _build()
    allowed = set(bundle["capture_plan"]["allowed_domains"])
    from urllib.parse import urlsplit

    for r in bundle["site_model"]["routes"]:
        assert urlsplit(r["url"]).hostname in allowed


# --------------------------------------------------------------------------- #
# Positive: capability bindings
# --------------------------------------------------------------------------- #


def test_notice_board_bound_to_exact_evidence_route():
    bundle = _build()
    nb = next(
        b for b in bundle["capability_bindings"] if b["capability_id"] == "notice_board"
    )
    assert nb["candidate_state"] == "detected"
    assert nb["binding_state"] == "bound"
    rid = nb["route_ids"][0]
    route = next(r for r in bundle["site_model"]["routes"] if r["route_id"] == rid)
    assert (
        route["url"]
        == "https://www.seogu.gwangju.kr/bbs/BBSMSTR_000000000276/list.do"
    )


def test_document_library_bound_to_exact_evidence_route():
    bundle = _build()
    dl = next(
        b
        for b in bundle["capability_bindings"]
        if b["capability_id"] == "document_library"
    )
    assert dl["candidate_state"] == "detected"
    assert dl["binding_state"] == "bound"
    rid = dl["route_ids"][0]
    route = next(r for r in bundle["site_model"]["routes"] if r["route_id"] == rid)
    assert (
        route["url"]
        == "https://www.seogu.gwangju.kr/boardDownload.es?bid=0013&list_no=136021&seq=1"
    )


def test_directory_remains_review_required_unbound():
    bundle = _build()
    d = next(
        b for b in bundle["capability_bindings"] if b["capability_id"] == "directory"
    )
    assert d["candidate_state"] == "review_required"
    assert d["binding_state"] == "review_required"
    assert d["route_ids"] == []


def test_no_capability_promotion():
    bundle = _build()
    # Only candidate-declared capabilities exist; none promoted by keyword/etc.
    bound_ids = {b["capability_id"] for b in bundle["capability_bindings"] if b["binding_state"] == "bound"}
    assert bound_ids == {"notice_board", "document_library"}
    review_ids = {
        b["capability_id"]
        for b in bundle["capability_bindings"]
        if b["candidate_state"] == "review_required"
    }
    assert review_ids == {"directory"}


# --------------------------------------------------------------------------- #
# Positive: action graph
# --------------------------------------------------------------------------- #


def test_action_graph_navigate_only():
    bundle = _build()
    for a in bundle["action_graph"]["actions"]:
        assert a["action_type"] == "navigate"
        assert a["safety_level"] == "navigate"
        assert a["requires_user_confirmation"] is False


def test_all_action_route_refs_resolve():
    bundle = _build()
    route_ids = {r["route_id"] for r in bundle["site_model"]["routes"]}
    for a in bundle["action_graph"]["actions"]:
        assert a["from_route_id"] in route_ids
        assert a["to_route_id"] in route_ids
        assert a["from_route_id"] == "route-homepage"


def test_no_write_or_high_risk_action():
    bundle = _build()
    forbidden = {
        "click", "input", "type", "select", "prefill", "submit", "login",
        "payment", "pay", "upload", "enter_identity", "external_write",
    }
    for a in bundle["action_graph"]["actions"]:
        assert a["action_type"] not in forbidden


# --------------------------------------------------------------------------- #
# Positive: QA manifest
# --------------------------------------------------------------------------- #


def test_qa_manifest_counts_match_artifact():
    bundle = _build()
    qa = bundle["qa_manifest"]
    assert qa["route_count"] == len(bundle["site_model"]["routes"])
    assert qa["document_count"] == len(bundle["site_model"]["documents"])
    assert qa["action_count"] == bundle["action_graph"]["action_count"]
    assert qa["bound_capability_count"] == 2
    assert qa["review_required_capability_count"] == 1
    assert all(qa["checks"].values())


def test_qa_manifest_non_production_flags():
    bundle = _build()
    qa = bundle["qa_manifest"]
    assert qa["offline_preview_input_ready"] is True
    assert qa["production_ready"] is False
    assert qa["production_promotion_requested"] is False
    assert qa["actual_site_control_authorized"] is False
    assert qa["live_network_authorized"] is False


# --------------------------------------------------------------------------- #
# Negative: fail-closed matrix (A-N)
# --------------------------------------------------------------------------- #


def _mutated_candidate(**overrides):
    cand = copy.deepcopy(_load_candidate())
    for k, v in overrides.items():
        if "." in k:
            section, field = k.split(".", 1)
            cand[section][field] = v
        else:
            cand[k] = v
    return cand


def _hp():
    return _build_homepage_map()


def test_A_live_network_authorized_true_rejected():
    cand = _mutated_candidate(**{"capture_policy.live_network_authorized": True})
    with pytest.raises(OfflineSiteModelError):
        build_offline_site_model_bundle(
            cand, _hp(), homepage_map_source_ref=STATIC_EVIDENCE_REF,
            capture_urls=SEOGU_SURVIVE_URLS,
        )


def test_B_actual_site_control_authorized_true_rejected():
    cand = _mutated_candidate(**{"browser_policy.actual_site_control_authorized": True})
    with pytest.raises(OfflineSiteModelError):
        build_offline_site_model_bundle(
            cand, _hp(), homepage_map_source_ref=STATIC_EVIDENCE_REF,
            capture_urls=SEOGU_SURVIVE_URLS,
        )


def test_C_external_write_authorized_true_rejected():
    cand = _mutated_candidate(**{"action_policy.external_write_authorized": True})
    with pytest.raises(OfflineSiteModelError):
        build_offline_site_model_bundle(
            cand, _hp(), homepage_map_source_ref=STATIC_EVIDENCE_REF,
            capture_urls=SEOGU_SURVIVE_URLS,
        )


def test_D_high_risk_actions_authorized_true_rejected():
    cand = _mutated_candidate(**{"action_policy.high_risk_actions_authorized": True})
    with pytest.raises(OfflineSiteModelError):
        build_offline_site_model_bundle(
            cand, _hp(), homepage_map_source_ref=STATIC_EVIDENCE_REF,
            capture_urls=SEOGU_SURVIVE_URLS,
        )


def test_E_cross_domain_capture_url_rejected():
    with pytest.raises(OfflineSiteModelError):
        build_offline_site_model_bundle(
            _load_candidate(), _hp(), homepage_map_source_ref=STATIC_EVIDENCE_REF,
            capture_urls=["https://evil.example.com/foo"],
        )


def test_F_relative_capture_url_rejected():
    with pytest.raises(OfflineSiteModelError):
        build_offline_site_model_bundle(
            _load_candidate(), _hp(), homepage_map_source_ref=STATIC_EVIDENCE_REF,
            capture_urls=["/relative/list.do"],
        )


def test_G_malformed_capture_url_rejected():
    with pytest.raises(OfflineSiteModelError):
        build_offline_site_model_bundle(
            _load_candidate(), _hp(), homepage_map_source_ref=STATIC_EVIDENCE_REF,
            capture_urls=["not a url"],
        )


def test_H_capture_url_not_observed_rejected():
    with pytest.raises(OfflineSiteModelError):
        build_offline_site_model_bundle(
            _load_candidate(), _hp(), homepage_map_source_ref=STATIC_EVIDENCE_REF,
            capture_urls=["https://www.seogu.gwangju.kr/not/in/homepage/map"],
        )


def test_I_homepage_map_source_ref_not_in_provenance_rejected():
    with pytest.raises(OfflineSiteModelError):
        build_offline_site_model_bundle(
            _load_candidate(), _hp(), homepage_map_source_ref="nonexistent.ref",
            capture_urls=SEOGU_SURVIVE_URLS,
        )


def test_J_empty_or_malformed_candidate_provenance_rejected():
    with pytest.raises(OfflineSiteModelError):
        build_offline_site_model_bundle(
            _mutated_candidate(**{"provenance.source_refs": []}),
            _hp(), homepage_map_source_ref=STATIC_EVIDENCE_REF,
            capture_urls=SEOGU_SURVIVE_URLS,
        )
    with pytest.raises(OfflineSiteModelError):
        build_offline_site_model_bundle(
            _mutated_candidate(provenance={"review_state": "synthetic"}),
            _hp(), homepage_map_source_ref=STATIC_EVIDENCE_REF,
            capture_urls=SEOGU_SURVIVE_URLS,
        )


def test_K_detected_capability_evidence_route_omitted_rejected():
    # Drop the BBSMSTR notice-board URL from the capture allowlist; the detected
    # notice_board capability can no longer bind a modeled route -> fail closed.
    narrowed = [u for u in SEOGU_SURVIVE_URLS
                if "BBSMSTR_000000000276" not in u]
    with pytest.raises(OfflineSiteModelError):
        build_offline_site_model_bundle(
            _load_candidate(), _hp(), homepage_map_source_ref=STATIC_EVIDENCE_REF,
            capture_urls=narrowed,
        )


def test_L_route_and_action_references_always_resolve():
    # Invariant: every referenced route id exists in the model (construction).
    bundle = _build()
    route_ids = {r["route_id"] for r in bundle["site_model"]["routes"]}
    referenced = set()
    for b in bundle["capability_bindings"]:
        referenced.update(b["route_ids"])
    for a in bundle["action_graph"]["actions"]:
        referenced.add(a["from_route_id"])
        referenced.add(a["to_route_id"])
    assert referenced.issubset(route_ids)


def test_M_duplicate_canonical_capture_url_deterministic_dedup():
    dup = list(SEOGU_SURVIVE_URLS) + [SEOGU_SURVIVE_URLS[0]]
    bundle = build_offline_site_model_bundle(
        _load_candidate(), _hp(), homepage_map_source_ref=STATIC_EVIDENCE_REF,
        capture_urls=dup,
    )
    captured = bundle["capture_plan"]["captured_urls"]
    assert len(captured) == len(set(captured))
    assert set(captured) == set(SEOGU_SURVIVE_URLS)
    assert bundle["capture_plan"]["url_count"] == len(SEOGU_SURVIVE_URLS)


def test_N_candidate_homepage_host_outside_domains_rejected():
    cand = _mutated_candidate(
        entry_points=[{"id": "homepage", "kind": "homepage", "url": "https://evil.example.com/"}]
    )
    with pytest.raises(OfflineSiteModelError):
        build_offline_site_model_bundle(
            cand, _hp(), homepage_map_source_ref=STATIC_EVIDENCE_REF,
            capture_urls=SEOGU_SURVIVE_URLS,
        )
