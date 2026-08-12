"""Archetype + capability contract tests for generic SiteSpec v2 (#1287 Slice B).

Pure stdlib + pytest only. No network, no provider, no Firecrawl.

Focuses on the archetype and capability closed vocabularies, confidence bounds,
entry-point reference integrity, state/safety coupling, the financial auth_boundary
safety floor, and the rule that university/bank sites must not carry municipal
jurisdiction. Reuses the synthetic fixtures from tests/fixtures/platform/site-spec-v2.
"""

import copy
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "platform" / "site-spec-v2"

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

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


class ContractViolation(Exception):
    """Raised when an archetype/capability contract rule is violated."""


def _require(cond, msg):
    if not cond:
        raise ContractViolation(msg)


def validate_archetype_and_capabilities(doc):
    """Fail-closed archetype + capability semantic validation of a SiteSpec v2 doc."""
    _require(isinstance(doc, dict), "SiteSpec v2 must be a JSON object")

    # ---- entry-point id set (for reference integrity) ----
    ep_ids = set()
    for ep in doc.get("entry_points", []):
        _require(isinstance(ep, dict), "each entry point must be an object")
        _require(isinstance(ep.get("id"), str) and ID_PATTERN.match(ep["id"]),
                 "entry point id must match machine ID pattern")
        ep_ids.add(ep["id"])

    # ---- archetype ----
    archetype = doc["archetype"]
    _require(isinstance(archetype, dict), "archetype must be an object")
    _require(archetype.get("id") in ARCHETYPE_IDS,
             f"archetype id {archetype.get('id')!r} not in closed vocabulary")
    _require(archetype.get("state") in ARCHETYPE_STATES,
             f"archetype state {archetype.get('state')!r} not in closed vocabulary")
    conf = archetype.get("confidence")
    _require(isinstance(conf, (int, float)), "archetype confidence must be numeric")
    _require(conf >= 0.0, "archetype confidence must be >= 0.0")
    _require(conf <= 1.0, "archetype confidence must be <= 1.0")

    # ---- capabilities ----
    capabilities = doc.get("capabilities", [])
    _require(isinstance(capabilities, list), "capabilities must be an array")
    cap_ids = set()
    for cap in capabilities:
        _require(isinstance(cap, dict), "each capability must be an object")
        cap_id = cap.get("id")
        _require(cap_id in CAPABILITY_IDS,
                 f"capability id {cap_id!r} not in closed vocabulary")
        _require(cap_id not in cap_ids, f"duplicate capability id: {cap_id!r}")
        cap_ids.add(cap_id)
        _require(cap.get("state") in CAPABILITY_STATES,
                 f"capability state {cap.get('state')!r} not in closed vocabulary")
        cconf = cap.get("confidence")
        _require(isinstance(cconf, (int, float)), "capability confidence must be numeric")
        _require(cconf >= 0.0, "capability confidence must be >= 0.0")
        _require(cconf <= 1.0, "capability confidence must be <= 1.0")
        safety = cap.get("safety_level")
        _require(safety in SAFETY_LEVELS,
                 f"safety_level {safety!r} not in closed vocabulary")
        for ref in cap.get("entry_points", []):
            _require(isinstance(ref, str) and ref in ep_ids,
                     f"capability {cap_id!r} references unknown entry point: {ref!r}")
        # state/safety coupling: unsupported / not_detected cannot advertise
        # active navigation or input preparation.
        if cap.get("state") in ("unsupported", "not_detected"):
            _require(safety not in ("navigate", "prepare_input"),
                     f"{cap.get('state')} capability cannot advertise {safety}")
        # financial auth boundary must stay at/above high_risk_boundary.
        if cap_id == "auth_boundary":
            _require(safety in ("high_risk_boundary", "unsupported"),
                     "auth_boundary safety must be high_risk_boundary (or unsupported)")

    # archetype/extension separation
    extensions = doc.get("extensions", {})
    archetype_id = archetype["id"]
    if archetype_id == "university":
        _require("municipality" not in extensions,
                 "university must not carry municipal jurisdiction")
    if archetype_id == "bank":
        _require("municipality" not in extensions,
                 "bank must not carry municipal jurisdiction")
    return True


def _load(name):
    import json

    with open(FIXTURE_DIR / f"{name}.json", "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---- positive ----

@pytest.mark.parametrize("name", ["municipality", "university", "financial", "unknown"])
def test_archetype_capability_valid(name):
    assert validate_archetype_and_capabilities(_load(name)) is True


# ---- archetype confidence bounds ----

def test_archetype_confidence_below_zero_rejected():
    doc = copy.deepcopy(_load("municipality"))
    doc["archetype"]["confidence"] = -0.1
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


def test_archetype_confidence_above_one_rejected():
    doc = copy.deepcopy(_load("municipality"))
    doc["archetype"]["confidence"] = 1.2
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


# ---- capability id integrity ----

def test_duplicate_capability_id_rejected():
    doc = copy.deepcopy(_load("municipality"))
    dup = copy.deepcopy(doc["capabilities"][0])
    doc["capabilities"].append(dup)
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


def test_capability_missing_entry_point_reference_rejected():
    doc = copy.deepcopy(_load("municipality"))
    doc["capabilities"][0]["entry_points"] = ["does_not_exist"]
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


# ---- state/safety coupling ----

def test_unsupported_capability_cannot_navigate():
    doc = copy.deepcopy(_load("municipality"))
    doc["capabilities"][0]["state"] = "unsupported"
    doc["capabilities"][0]["safety_level"] = "navigate"
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


def test_unsupported_capability_cannot_prepare_input():
    doc = copy.deepcopy(_load("municipality"))
    doc["capabilities"][0]["state"] = "unsupported"
    doc["capabilities"][0]["safety_level"] = "prepare_input"
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


def test_not_detected_capability_cannot_navigate():
    doc = copy.deepcopy(_load("municipality"))
    doc["capabilities"][0]["state"] = "not_detected"
    doc["capabilities"][0]["safety_level"] = "navigate"
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


def test_not_detected_capability_cannot_prepare_input():
    doc = copy.deepcopy(_load("municipality"))
    doc["capabilities"][0]["state"] = "not_detected"
    doc["capabilities"][0]["safety_level"] = "prepare_input"
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


# ---- closed vocabularies ----

def test_unknown_capability_id_rejected():
    doc = copy.deepcopy(_load("municipality"))
    doc["capabilities"][0]["id"] = "login_form"
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


def test_unknown_capability_state_rejected():
    doc = copy.deepcopy(_load("municipality"))
    doc["capabilities"][0]["state"] = "active"
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


def test_unknown_safety_level_rejected():
    doc = copy.deepcopy(_load("municipality"))
    doc["capabilities"][0]["safety_level"] = "execute"
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


def test_unknown_archetype_id_rejected():
    doc = copy.deepcopy(_load("municipality"))
    doc["archetype"]["id"] = "school"
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


# ---- financial auth boundary safety floor ----

def test_financial_auth_boundary_downgrade_rejected():
    doc = copy.deepcopy(_load("financial"))
    auth = next(c for c in doc["capabilities"] if c["id"] == "auth_boundary")
    auth["safety_level"] = "prepare_input"
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


def test_financial_auth_boundary_read_only_downgrade_rejected():
    doc = copy.deepcopy(_load("financial"))
    auth = next(c for c in doc["capabilities"] if c["id"] == "auth_boundary")
    auth["safety_level"] = "read_only"
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


# ---- archetype/extension separation ----

def test_university_forced_municipal_jurisdiction_rejected():
    doc = copy.deepcopy(_load("university"))
    doc["extensions"]["municipality"] = {
        "jurisdiction": {
            "canonical_name": "X",
            "short_name": "X",
            "effective_from": "2026-01-01",
            "historical_aliases": [],
        }
    }
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


def test_bank_forced_municipal_jurisdiction_rejected():
    doc = copy.deepcopy(_load("financial"))
    doc["extensions"]["municipality"] = {
        "jurisdiction": {
            "canonical_name": "X",
            "short_name": "X",
            "effective_from": "2026-01-01",
            "historical_aliases": [],
        }
    }
    with pytest.raises(ContractViolation):
        validate_archetype_and_capabilities(doc)


# ---- safety levels never authorize external writes (policy assertion) ----

def test_no_safety_level_authorizes_external_write():
    doc = copy.deepcopy(_load("financial"))
    # Even with high_risk_boundary + auth_boundary, external write stays false.
    assert doc["action_policy"]["external_write_authorized"] is False
    assert doc["action_policy"]["high_risk_actions_authorized"] is False
