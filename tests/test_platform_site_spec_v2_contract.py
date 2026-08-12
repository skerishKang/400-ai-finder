"""Contract test for the generic SiteSpec v2 schema + synthetic fixtures (#1287 Slice B).

Pure stdlib + pytest only. No network, no provider, no Firecrawl, no browser harness.

This validates the NEW v2 namespace (configs/platform + tests/fixtures/platform). It is
deliberately separate from the v1 Buk-gu SiteSpec (configs/sitespec.schema.json,
configs/sites/*.sitespec.json). Cross-field invariants that JSON Schema cannot express
(identity collision, entry-point host ownership, capability entry-point references,
safety/state coupling, archetype/extension separation) are enforced here by small in-test
stdlib semantic helpers and fail closed.
"""

import copy
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "platform" / "site-spec-v2"
SCHEMA_FILE = REPO_ROOT / "configs" / "platform" / "site-spec-v2.schema.json"
V1_SITES_DIR = REPO_ROOT / "configs" / "sites"

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
HOSTNAME_PATTERN = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)+$"
)

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
ENTRY_POINT_KINDS = {
    "homepage",
    "search",
    "service",
    "notice",
    "document",
    "directory",
    "other",
}
ACQUISITION_MODES = {"offline_fixture", "synthetic"}
SURFACE_MODES = {"generated_preview", "controlled_clone"}
REVIEW_STATES = {"synthetic", "review_required", "reviewed"}
ALLOWED_EXTENSIONS = {"municipality", "university", "financial"}

REQUIRED_TOP_LEVEL = [
    "$schema",
    "schema_version",
    "identity",
    "domains",
    "entry_points",
    "archetype",
    "capabilities",
    "capture_policy",
    "browser_policy",
    "knowledge_policy",
    "action_policy",
    "provenance",
    "extensions",
]


class ContractViolation(Exception):
    """Raised when a v2 SiteSpec violates a fail-closed semantic contract rule."""


def _require(cond, msg):
    if not cond:
        raise ContractViolation(msg)


def validate_site_spec_v2(doc):
    """Fail-closed semantic validation of a SiteSpec v2 document.

    JSON Schema expresses shape; this adds the cross-field invariants that the
    schema draft cannot. Raises ContractViolation on the first violation.
    """
    _require(isinstance(doc, dict), "SiteSpec v2 must be a JSON object")

    for key in REQUIRED_TOP_LEVEL:
        _require(key in doc, f"missing required top-level group: {key}")

    _require(doc["schema_version"] == "2.0.0", "schema_version must be exactly 2.0.0")

    # ---- identity ----
    identity = doc["identity"]
    _require(isinstance(identity, dict), "identity must be an object")
    site_id = identity.get("site_id")
    _require(isinstance(site_id, str) and ID_PATTERN.match(site_id),
             "identity.site_id must match machine ID pattern")
    legacy_ids = identity.get("legacy_ids")
    _require(isinstance(legacy_ids, list), "identity.legacy_ids must be an array")
    seen = set()
    for lid in legacy_ids:
        _require(isinstance(lid, str) and ID_PATTERN.match(lid),
                 "each legacy_id must match machine ID pattern")
        _require(lid not in seen, f"duplicate legacy alias: {lid!r}")
        seen.add(lid)
    _require(site_id not in legacy_ids,
             "canonical site_id must not appear in legacy_ids")
    display = identity.get("display")
    _require(isinstance(display, dict), "identity.display must be an object")
    _require(isinstance(display.get("default_label"), str) and display["default_label"],
             "identity.display.default_label must be a non-empty string")
    locale_labels = display.get("locale_labels")
    _require(isinstance(locale_labels, dict), "identity.display.locale_labels must be an object")
    for loc, label in locale_labels.items():
        _require(isinstance(label, str) and label,
                 f"locale label {loc!r} must be a non-empty string")

    # ---- domains ----
    domains = doc["domains"]
    _require(isinstance(domains, dict), "domains must be an object")
    public = domains.get("public")
    _require(isinstance(public, list) and len(public) >= 1,
             "domains.public must be a non-empty array")
    public_set = set()
    for host in public:
        _require(isinstance(host, str) and HOSTNAME_PATTERN.match(host),
                 f"domain host {host!r} must be a declarative hostname")
        _require(host not in public_set, f"duplicate public domain: {host!r}")
        public_set.add(host)

    # ---- entry points ----
    entry_points = doc["entry_points"]
    _require(isinstance(entry_points, list) and len(entry_points) >= 1,
             "entry_points must be a non-empty array")
    ep_ids = set()
    for ep in entry_points:
        _require(isinstance(ep, dict), "each entry point must be an object")
        ep_id = ep.get("id")
        _require(isinstance(ep_id, str) and ID_PATTERN.match(ep_id),
                 "entry point id must match machine ID pattern")
        _require(ep_id not in ep_ids, f"duplicate entry-point id: {ep_id!r}")
        ep_ids.add(ep_id)
        _require(ep.get("kind") in ENTRY_POINT_KINDS,
                 f"entry point kind {ep.get('kind')!r} not in closed vocabulary")
        url = ep.get("url")
        _require(isinstance(url, str) and url, "entry point url must be a non-empty string")
        parsed = urlparse(url)
        _require(parsed.scheme in ("http", "https"),
                 f"entry point url must be absolute http(s): {url!r}")
        _require(bool(parsed.netloc), f"entry point url must have a host: {url!r}")
        _require(parsed.hostname in public_set,
                 f"entry-point host {parsed.hostname!r} is not declared in domains.public")

    # ---- archetype ----
    archetype = doc["archetype"]
    _require(isinstance(archetype, dict), "archetype must be an object")
    _require(archetype.get("id") in ARCHETYPE_IDS,
             f"archetype id {archetype.get('id')!r} not in closed vocabulary")
    _require(archetype.get("state") in ARCHETYPE_STATES,
             f"archetype state {archetype.get('state')!r} not in closed vocabulary")
    conf = archetype.get("confidence")
    _require(isinstance(conf, (int, float)) and 0.0 <= conf <= 1.0,
             "archetype confidence must be 0.0..1.0")
    _require(isinstance(archetype.get("evidence_refs"), list),
             "archetype.evidence_refs must be an array")

    # ---- capabilities ----
    capabilities = doc["capabilities"]
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
        _require(isinstance(cconf, (int, float)) and 0.0 <= cconf <= 1.0,
                 "capability confidence must be 0.0..1.0")
        safety = cap.get("safety_level")
        _require(safety in SAFETY_LEVELS,
                 f"safety_level {safety!r} not in closed vocabulary")
        refs = cap.get("entry_points")
        _require(isinstance(refs, list), "capability.entry_points must be an array")
        for ref in refs:
            _require(isinstance(ref, str) and ref in ep_ids,
                     f"capability {cap_id!r} references unknown entry point: {ref!r}")
        _require(isinstance(cap.get("evidence_refs"), list),
                 "capability.evidence_refs must be an array")
        # state/safety coupling
        if cap.get("state") in ("unsupported", "not_detected"):
            _require(safety not in ("navigate", "prepare_input"),
                     f"{cap.get('state')} capability cannot advertise {safety}")
        # financial auth boundary must stay high_risk_boundary or unsupported
        if cap_id == "auth_boundary":
            _require(safety in ("high_risk_boundary", "unsupported"),
                     "auth_boundary safety must be high_risk_boundary (or unsupported)")

    # ---- policy groups ----
    cp = doc["capture_policy"]
    _require(isinstance(cp, dict), "capture_policy must be an object")
    _require(cp.get("acquisition_mode") in ACQUISITION_MODES,
             "capture_policy.acquisition_mode not in closed vocabulary")
    _require(isinstance(cp.get("live_network_authorized"), bool),
             "capture_policy.live_network_authorized must be boolean")
    bp = doc["browser_policy"]
    _require(isinstance(bp, dict), "browser_policy must be an object")
    _require(bp.get("surface_mode") in SURFACE_MODES,
             "browser_policy.surface_mode not in closed vocabulary")
    _require(isinstance(bp.get("actual_site_control_authorized"), bool),
             "browser_policy.actual_site_control_authorized must be boolean")
    kp = doc["knowledge_policy"]
    _require(isinstance(kp, dict), "knowledge_policy must be an object")
    _require(isinstance(kp.get("grounding_required"), bool),
             "knowledge_policy.grounding_required must be boolean")
    _require(isinstance(kp.get("provenance_required"), bool),
             "knowledge_policy.provenance_required must be boolean")
    ap = doc["action_policy"]
    _require(isinstance(ap, dict), "action_policy must be an object")
    _require(isinstance(ap.get("external_write_authorized"), bool),
             "action_policy.external_write_authorized must be boolean")
    _require(isinstance(ap.get("high_risk_actions_authorized"), bool),
             "action_policy.high_risk_actions_authorized must be boolean")

    # ---- provenance ----
    prov = doc["provenance"]
    _require(isinstance(prov, dict), "provenance must be an object")
    srefs = prov.get("source_refs")
    _require(isinstance(srefs, list) and len(srefs) >= 1,
             "provenance.source_refs must be a non-empty array")
    _require(prov.get("review_state") in REVIEW_STATES,
             "provenance.review_state not in closed vocabulary")

    # ---- extensions ----
    extensions = doc["extensions"]
    _require(isinstance(extensions, dict), "extensions must be an object")
    for key in extensions:
        _require(key in ALLOWED_EXTENSIONS,
                 f"extension key {key!r} not in allowed set")
    archetype_id = archetype["id"]
    if archetype_id == "municipality":
        _require("municipality" in extensions,
                 "municipality archetype must carry extensions.municipality")
        _validate_municipality_extension(extensions["municipality"])
    if archetype_id == "university":
        _require("university" in extensions,
                 "university archetype must carry extensions.university")
        _require("municipality" not in extensions,
                 "university must not carry municipal jurisdiction")
    if archetype_id == "bank":
        _require("financial" in extensions,
                 "bank archetype must carry extensions.financial")
        _require("municipality" not in extensions,
                 "bank must not carry municipal jurisdiction")
    return True


def _validate_municipality_extension(block):
    _require(isinstance(block, dict), "extensions.municipality must be an object")
    jur = block.get("jurisdiction")
    _require(isinstance(jur, dict), "extensions.municipality.jurisdiction must be an object")
    for field in ("canonical_name", "short_name", "effective_from", "historical_aliases"):
        _require(field in jur, f"extensions.municipality.jurisdiction missing {field}")
    _require(re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", jur["effective_from"]),
             "jurisdiction.effective_from must be YYYY-MM-DD")
    _require(isinstance(jur["historical_aliases"], list),
             "jurisdiction.historical_aliases must be an array")


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


FIXTURE_NAMES = ["municipality", "university", "financial", "unknown"]


def load_fixture(name):
    return load_json(FIXTURE_DIR / f"{name}.json")


# ---- positive: every synthetic fixture is a valid v2 contract ----

@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_fixture_is_valid_v2_contract(name):
    doc = load_fixture(name)
    assert validate_site_spec_v2(doc) is True


def test_schema_file_is_valid_json():
    assert load_json(SCHEMA_FILE)


# ---- identity semantics ----

def test_duplicate_legacy_alias_rejected():
    doc = copy.deepcopy(load_fixture("municipality"))
    doc["identity"]["legacy_ids"] = ["old_a", "old_a"]
    with pytest.raises(ContractViolation):
        validate_site_spec_v2(doc)


def test_canonical_site_id_in_legacy_ids_rejected():
    doc = copy.deepcopy(load_fixture("municipality"))
    doc["identity"]["legacy_ids"] = [doc["identity"]["site_id"]]
    with pytest.raises(ContractViolation):
        validate_site_spec_v2(doc)


def test_empty_legacy_ids_allowed():
    doc = copy.deepcopy(load_fixture("municipality"))
    doc["identity"]["legacy_ids"] = []
    assert validate_site_spec_v2(doc) is True


def test_display_label_is_not_runtime_identity():
    # Two distinct site_ids may share a display label; identity is the site_id.
    a = copy.deepcopy(load_fixture("municipality"))
    a["identity"]["site_id"] = "site_alpha"
    a["identity"]["display"]["default_label"] = "Shared Label"
    b = copy.deepcopy(load_fixture("university"))
    b["identity"]["site_id"] = "site_beta"
    b["identity"]["display"]["default_label"] = "Shared Label"
    assert validate_site_spec_v2(a) is True
    assert validate_site_spec_v2(b) is True


def test_cross_fixture_identity_collision_rejected():
    docs = [load_fixture(n) for n in FIXTURE_NAMES]
    # Force a collision: give university the same site_id as municipality.
    dup = copy.deepcopy(docs[1])
    dup["identity"]["site_id"] = docs[0]["identity"]["site_id"]
    with pytest.raises(ContractViolation):
        assert_identity_inventory_unique(docs[0:1] + [dup] + docs[2:])


def assert_identity_inventory_unique(docs):
    seen_site_ids = set()
    seen_legacy = set()
    for d in docs:
        sid = d["identity"]["site_id"]
        if sid in seen_site_ids or sid in seen_legacy:
            raise ContractViolation(f"cross-fixture identity collision: {sid!r}")
        seen_site_ids.add(sid)
        for lid in d["identity"]["legacy_ids"]:
            if lid in seen_site_ids or lid in seen_legacy:
                raise ContractViolation(f"cross-fixture legacy collision: {lid!r}")
            seen_legacy.add(lid)


# ---- entry points ----

def test_duplicate_entry_point_id_rejected():
    doc = copy.deepcopy(load_fixture("municipality"))
    doc["entry_points"][1]["id"] = doc["entry_points"][0]["id"]
    with pytest.raises(ContractViolation):
        validate_site_spec_v2(doc)


def test_undeclared_entry_point_host_rejected():
    doc = copy.deepcopy(load_fixture("municipality"))
    doc["entry_points"][0]["url"] = "https://evil.example.com/page"
    with pytest.raises(ContractViolation):
        validate_site_spec_v2(doc)


def test_domain_string_in_path_is_not_ownership():
    doc = copy.deepcopy(load_fixture("municipality"))
    host = doc["domains"]["public"][0]
    doc["entry_points"][0]["url"] = f"https://evil.example.com/{host}/login"
    with pytest.raises(ContractViolation):
        validate_site_spec_v2(doc)


def test_non_http_entry_point_rejected():
    doc = copy.deepcopy(load_fixture("municipality"))
    doc["entry_points"][0]["url"] = "ftp://municipality.example.go.kr/file"
    with pytest.raises(ContractViolation):
        validate_site_spec_v2(doc)


# ---- archetype ----

def test_unknown_archetype_enum_rejected():
    doc = copy.deepcopy(load_fixture("municipality"))
    doc["archetype"]["id"] = "school"
    with pytest.raises(ContractViolation):
        validate_site_spec_v2(doc)


# ---- schema version ----

def test_wrong_schema_version_rejected():
    doc = copy.deepcopy(load_fixture("municipality"))
    doc["schema_version"] = "1.0.0"
    with pytest.raises(ContractViolation):
        validate_site_spec_v2(doc)


# ---- determinism / fail-closed ----

def test_validation_is_deterministic():
    doc = load_fixture("municipality")
    assert validate_site_spec_v2(copy.deepcopy(doc)) is True
    assert validate_site_spec_v2(copy.deepcopy(doc)) is True


def test_any_known_violation_stays_rejected():
    # Mutating a valid fixture in a known-bad way must always fail, not pass.
    doc = copy.deepcopy(load_fixture("financial"))
    doc["schema_version"] = "1.0.0"
    with pytest.raises(ContractViolation):
        validate_site_spec_v2(doc)


# ---- fixture-specific proofs ----

def test_municipality_extension_proof():
    doc = load_fixture("municipality")
    assert doc["archetype"]["id"] == "municipality"
    assert "municipality" in doc["extensions"]
    assert "university" not in doc["extensions"]
    assert "financial" not in doc["extensions"]
    assert validate_site_spec_v2(doc) is True


def test_university_has_no_municipal_jurisdiction():
    doc = load_fixture("university")
    assert doc["archetype"]["id"] == "university"
    assert "university" in doc["extensions"]
    assert "municipality" not in doc["extensions"]


def test_financial_auth_boundary_is_high_risk():
    doc = load_fixture("financial")
    assert doc["archetype"]["id"] == "bank"
    assert "financial" in doc["extensions"]
    assert "municipality" not in doc["extensions"]
    auth = next(c for c in doc["capabilities"] if c["id"] == "auth_boundary")
    assert auth["safety_level"] == "high_risk_boundary"
    assert doc["action_policy"]["external_write_authorized"] is False
    assert doc["action_policy"]["high_risk_actions_authorized"] is False


def test_unknown_archetype_not_fabricated():
    doc = load_fixture("unknown")
    assert doc["archetype"]["id"] == "unknown"
    assert doc["archetype"]["confidence"] < 0.5
    assert doc["extensions"] == {}


# ---- v1 namespace separation (contract #19) ----

def test_v2_files_do_not_enter_v1_resolver_namespace():
    v2_files = [
        SCHEMA_FILE,
        REPO_ROOT / "configs" / "platform" / "archetype.schema.json",
        REPO_ROOT / "configs" / "platform" / "capability.schema.json",
        REPO_ROOT / "configs" / "platform" / "onboarding-report.schema.json",
    ]
    for f in v2_files:
        assert f.exists()
        assert not f.name.endswith(".sitespec.json")

    for name in FIXTURE_NAMES:
        fp = FIXTURE_DIR / f"{name}.json"
        assert fp.exists()
        assert not fp.name.endswith(".sitespec.json")
        assert "configs/sites" not in str(fp)


def test_v1_resolver_still_resolves_only_bukgu_and_ignores_v2():
    from src.site_profiles.sitespec import (
        CONFIGS_SITES_DIR,
        SiteSpecNotFoundError,
        iter_sitespec_paths,
        resolve_site_id,
    )

    paths = iter_sitespec_paths(CONFIGS_SITES_DIR)
    assert paths, "v1 resolver should still find bukgu SiteSpec"
    for p in paths:
        assert p.name.endswith(".sitespec.json")
        assert "platform" not in p.parts
    doc = resolve_site_id("bukgu_gwangju")
    assert doc["site_id"] == "bukgu_gwangju"
    with pytest.raises(SiteSpecNotFoundError):
        resolve_site_id("municipality_synthetic")
