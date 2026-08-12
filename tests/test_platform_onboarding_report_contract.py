"""Onboarding Report contract tests for generic SiteSpec v2 (#1287 Slice B).

Pure stdlib + pytest only. No network, no provider, no Firecrawl.

Focuses on the onboarding-report schema validity, the deterministic ratio accounting
rule (automation + human_review + unsupported == 1.0), the closed exception vocabulary,
and the rule that a generated-preview / synthetic report must NOT request Production
promotion by default.
"""

import copy
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "platform" / "onboarding-report"

ARCHETYPE_IDS = {
    "municipality",
    "university",
    "bank",
    "public_agency",
    "support_portal",
    "company",
    "unknown",
}
ARCHETYPE_STATES = {"configured", "detected", "unknown", "review_required"}
CAPABILITY_IDS = {
    "site_search",
    "notice_board",
    "document_library",
    "directory",
    "service_catalog",
    "faq",
    "calendar",
    "form",
    "contact",
    "map_or_location",
    "auth_boundary",
}
CAPABILITY_STATES = {
    "configured",
    "detected",
    "unsupported",
    "review_required",
    "not_detected",
}
SAFETY_LEVELS = {
    "read_only",
    "navigate",
    "prepare_input",
    "high_risk_boundary",
    "unsupported",
}
EXCEPTION_CATEGORIES = {
    "low_confidence_classification",
    "unsupported_component",
    "unsupported_capability",
    "unresolved_asset",
    "source_or_provenance_gap",
    "auth_or_high_risk_boundary",
    "generic_parser_or_runtime_gap",
    "site_specific_override_required",
}
SEVERITIES = {"info", "warning", "blocking"}
EXC_REVIEW_STATES = {"open", "review_required", "resolved"}
REVIEW_STATES = {"synthetic", "review_required", "reviewed"}
ACQUISITION_MODES = {"offline_fixture", "synthetic"}
RATIO_TOLERANCE = 1e-9

REQUIRED_TOP_LEVEL = [
    "schema_version",
    "run_id",
    "input",
    "acquisition",
    "site_identity",
    "archetype",
    "capabilities",
    "artifacts",
    "metrics",
    "exceptions",
    "provenance",
    "change_scope",
    "promotion",
]


class ContractViolation(Exception):
    """Raised when an onboarding-report contract rule is violated."""


def _require(cond, msg):
    if not cond:
        raise ContractViolation(msg)


def assert_metrics_sum_to_one(metrics):
    total = (
        metrics["automation_ratio"]
        + metrics["human_review_ratio"]
        + metrics["unsupported_ratio"]
    )
    if abs(total - 1.0) > RATIO_TOLERANCE:
        raise ContractViolation(f"ratio sum {total} != 1.0")


def validate_onboarding_report(doc):
    """Fail-closed semantic validation of an onboarding report document."""
    _require(isinstance(doc, dict), "onboarding report must be a JSON object")
    for key in REQUIRED_TOP_LEVEL:
        _require(key in doc, f"missing required top-level group: {key}")

    _require(doc["schema_version"] == "2.0.0", "schema_version must be exactly 2.0.0")
    _require(isinstance(doc.get("run_id"), str) and doc["run_id"], "run_id required")

    # input
    inp = doc["input"]
    _require(isinstance(inp, dict), "input must be an object")
    _require(inp.get("source_kind") in ACQUISITION_MODES,
             "input.source_kind not in closed vocabulary")

    # acquisition
    acq = doc["acquisition"]
    _require(isinstance(acq, dict), "acquisition must be an object")
    _require(acq.get("acquisition_mode") in ACQUISITION_MODES,
             "acquisition.acquisition_mode not in closed vocabulary")
    _require(isinstance(acq.get("live_network_authorized"), bool),
             "acquisition.live_network_authorized must be boolean")

    # site_identity
    sid = doc["site_identity"]
    _require(isinstance(sid, dict), "site_identity must be an object")
    _require(isinstance(sid.get("site_id"), str) and sid["site_id"],
             "site_identity.site_id required")

    # archetype
    arch = doc["archetype"]
    _require(isinstance(arch, dict), "archetype must be an object")
    _require(arch.get("id") in ARCHETYPE_IDS, "archetype id not in closed vocabulary")
    _require(arch.get("state") in ARCHETYPE_STATES, "archetype state not in closed vocabulary")
    ac = arch.get("confidence")
    _require(isinstance(ac, (int, float)) and 0.0 <= ac <= 1.0,
             "archetype confidence must be 0.0..1.0")
    _require(isinstance(arch.get("evidence_refs"), list),
             "archetype.evidence_refs must be an array")

    # capabilities
    caps = doc["capabilities"]
    _require(isinstance(caps, list), "capabilities must be an array")
    cap_ids = set()
    for cap in caps:
        _require(isinstance(cap, dict), "each capability must be an object")
        _require(cap.get("id") in CAPABILITY_IDS, "capability id not in closed vocabulary")
        _require(cap["id"] not in cap_ids, f"duplicate capability id: {cap['id']!r}")
        cap_ids.add(cap["id"])
        _require(cap.get("state") in CAPABILITY_STATES, "capability state not in vocabulary")
        cc = cap.get("confidence")
        _require(isinstance(cc, (int, float)) and 0.0 <= cc <= 1.0,
                 "capability confidence must be 0.0..1.0")
        _require(cap.get("safety_level") in SAFETY_LEVELS, "safety_level not in vocabulary")
        _require(isinstance(cap.get("entry_points"), list), "entry_points must be array")
        _require(isinstance(cap.get("evidence_refs"), list), "evidence_refs must be array")

    # artifacts
    arts = doc["artifacts"]
    _require(isinstance(arts, list), "artifacts must be an array")
    for art in arts:
        _require(isinstance(art, dict), "each artifact must be an object")
        for k in ("id", "kind", "path", "generated"):
            _require(k in art, f"artifact missing {k}")
        _require(isinstance(art["generated"], bool), "artifact.generated must be boolean")

    # metrics (bounded + accounting)
    metrics = doc["metrics"]
    _require(isinstance(metrics, dict), "metrics must be an object")
    for k in ("automation_ratio", "human_review_ratio", "unsupported_ratio"):
        v = metrics.get(k)
        _require(isinstance(v, (int, float)) and 0.0 <= v <= 1.0,
                 f"metric {k} must be 0.0..1.0")
    assert_metrics_sum_to_one(metrics)

    # exceptions
    excs = doc["exceptions"]
    _require(isinstance(excs, list), "exceptions must be an array")
    for exc in excs:
        _require(isinstance(exc, dict), "each exception must be an object")
        for k in ("id", "category", "severity", "review_state", "summary", "affected_refs"):
            _require(k in exc, f"exception missing {k}")
        _require(exc["category"] in EXCEPTION_CATEGORIES,
                 f"exception category {exc['category']!r} not in closed vocabulary")
        _require(exc["severity"] in SEVERITIES,
                 f"exception severity {exc['severity']!r} not in closed vocabulary")
        _require(exc["review_state"] in EXC_REVIEW_STATES,
                 f"exception review_state {exc['review_state']!r} not in closed vocabulary")
        _require(isinstance(exc["affected_refs"], list), "affected_refs must be array")

    # provenance
    prov = doc["provenance"]
    _require(isinstance(prov, dict), "provenance must be an object")
    _require(isinstance(prov.get("source_refs"), list) and len(prov["source_refs"]) >= 1,
             "provenance.source_refs must be non-empty")
    _require(prov.get("review_state") in REVIEW_STATES,
             "provenance.review_state not in closed vocabulary")

    # change_scope / promotion (both boolean)
    cs = doc["change_scope"]
    _require(isinstance(cs, dict), "change_scope must be an object")
    _require(isinstance(cs.get("shared_core_changed"), bool),
             "change_scope.shared_core_changed must be boolean")
    promo = doc["promotion"]
    _require(isinstance(promo, dict), "promotion must be an object")
    _require(isinstance(promo.get("production_promotion_requested"), bool),
             "promotion.production_promotion_requested must be boolean")
    # A synthetic / generated-preview report must NOT request Production promotion.
    if promo["production_promotion_requested"] is True:
        _require(prov["review_state"] != "synthetic",
                 "synthetic report must not request Production promotion")
        _require(acq["acquisition_mode"] not in ("synthetic", "offline_fixture"),
                 "synthetic/offline acquisition must not request Production promotion")
    return True


def _load(name):
    with open(FIXTURE_DIR / f"{name}.json", "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---- positive ----

def test_unknown_report_is_valid():
    assert validate_onboarding_report(_load("unknown")) is True


def test_report_metrics_sum_to_one_explicit():
    doc = _load("unknown")
    assert_metrics_sum_to_one(doc["metrics"])


def test_report_schema_file_is_valid_json():
    import json as _json

    with open(REPO_ROOT / "configs" / "platform" / "onboarding-report.schema.json",
              "r", encoding="utf-8") as fh:
        assert _json.load(fh)


# ---- negative matrix ----

def test_ratios_not_summing_to_one_rejected():
    doc = copy.deepcopy(_load("unknown"))
    doc["metrics"]["automation_ratio"] = 0.9
    doc["metrics"]["human_review_ratio"] = 0.9
    doc["metrics"]["unsupported_ratio"] = 0.9
    with pytest.raises(ContractViolation):
        validate_onboarding_report(doc)


def test_ratios_sum_within_tolerance_accepted():
    doc = copy.deepcopy(_load("unknown"))
    # tiny floating noise within tolerance must still pass
    doc["metrics"]["automation_ratio"] = 0.5 + 1e-12
    doc["metrics"]["human_review_ratio"] = 0.3 - 1e-12
    doc["metrics"]["unsupported_ratio"] = 0.2
    assert validate_onboarding_report(doc) is True


def test_unknown_exception_category_rejected():
    doc = copy.deepcopy(_load("unknown"))
    doc["exceptions"][0]["category"] = "made_up_category"
    with pytest.raises(ContractViolation):
        validate_onboarding_report(doc)


def test_unknown_exception_review_state_rejected():
    doc = copy.deepcopy(_load("unknown"))
    doc["exceptions"][0]["review_state"] = "pending"
    with pytest.raises(ContractViolation):
        validate_onboarding_report(doc)


def test_unknown_exception_severity_rejected():
    doc = copy.deepcopy(_load("unknown"))
    doc["exceptions"][0]["severity"] = "critical"
    with pytest.raises(ContractViolation):
        validate_onboarding_report(doc)


def test_generated_preview_requesting_production_promotion_rejected():
    doc = copy.deepcopy(_load("unknown"))
    # synthetic + generated-preview must keep production_promotion_requested false
    doc["promotion"]["production_promotion_requested"] = True
    with pytest.raises(ContractViolation):
        validate_onboarding_report(doc)


def test_negative_ratio_rejected():
    doc = copy.deepcopy(_load("unknown"))
    doc["metrics"]["automation_ratio"] = -0.1
    doc["metrics"]["human_review_ratio"] = 1.1
    doc["metrics"]["unsupported_ratio"] = 0.0
    with pytest.raises(ContractViolation):
        validate_onboarding_report(doc)


def test_change_scope_and_promotion_must_be_boolean():
    doc = copy.deepcopy(_load("unknown"))
    doc["change_scope"]["shared_core_changed"] = "no"
    with pytest.raises(ContractViolation):
        validate_onboarding_report(doc)
    doc = copy.deepcopy(_load("unknown"))
    doc["promotion"]["production_promotion_requested"] = "false"
    with pytest.raises(ContractViolation):
        validate_onboarding_report(doc)


def test_unknown_archetype_in_report_rejected():
    doc = copy.deepcopy(_load("unknown"))
    doc["archetype"]["id"] = "school"
    with pytest.raises(ContractViolation):
        validate_onboarding_report(doc)


# ---- schema-backed regression tests (Slice B narrow correction) ----

def _load_schema():
    with open(REPO_ROOT / "configs" / "platform" / "onboarding-report.schema.json",
              "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_archetype_evidence_refs_must_be_list():
    doc = copy.deepcopy(_load("unknown"))
    doc["archetype"]["evidence_refs"] = "not-a-list"
    with pytest.raises(ContractViolation):
        validate_onboarding_report(doc)


def test_fixture_top_level_keys_within_schema_properties():
    schema = _load_schema()
    doc = _load("unknown")
    # No undeclared top-level key (e.g. $schema) may re-enter the fixture.
    assert set(doc.keys()) <= set(schema["properties"].keys())


def test_artifact_keys_within_schema_properties():
    schema = _load_schema()
    allowed = set(schema["properties"]["artifacts"]["items"]["properties"].keys())
    doc = _load("unknown")
    for art in doc["artifacts"]:
        # No undeclared artifact key (e.g. name) may re-enter the fixture.
        assert set(art.keys()) <= allowed


def test_affected_refs_ep_prefix_resolve_to_source_entry_points():
    doc = _load("unknown")
    source_path = (
        REPO_ROOT
        / "tests"
        / "fixtures"
        / "platform"
        / "site-spec-v2"
        / "unknown.json"
    )
    with open(source_path, "r", encoding="utf-8") as fh:
        source = json.load(fh)
    source_ep_ids = {ep["id"] for ep in source["entry_points"]}
    for exc in doc["exceptions"]:
        for ref in exc["affected_refs"]:
            if ref.startswith("ep_"):
                assert ref in source_ep_ids, (
                    f"affected ref {ref!r} not present in source entry points"
                )
