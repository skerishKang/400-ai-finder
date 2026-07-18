"""Contract test for the additive site compatibility registry (#1219).

Pure stdlib + pytest only. No runtime loader, no new dependency, no network.

The registry is data-only: it records the frozen Buk-gu golden compatibility
surface as the first (and currently only) registered adapter. This test verifies
that contract without asserting any second-site support or runtime activation.
"""

import json
import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "configs" / "site-registry.json"
SCHEMA_PATH = REPO_ROOT / "configs" / "site-registry.schema.json"

GOLDEN_COMMIT = "7217c0f738a6aa4468bdde3119d8c2d1ec9dd610"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
REL_PATH = re.compile(r"^(?!/)[A-Za-z0-9_\-./]+$")
EXPECTED_KINDS = {
    "closed_route_ids",
    "closed_target_ids",
    "resident_public_window_api",
    "fixture_identity",
    "compatibility_manifest",
    "clone_first_adr",
}
CLASSIFICATIONS = {"frozen", "additive", "internal", "historical"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read_text_relative(rel_path):
    target = (REPO_ROOT / rel_path).resolve()
    if REPO_ROOT.resolve() not in target.parents and target != REPO_ROOT.resolve():
        raise ValueError(f"path escapes repo: {rel_path}")
    return target.read_text(encoding="utf-8")


# ---- A. JSON parse and basic schema contract ----

def test_registry_and_schema_are_valid_json():
    assert load_json(REGISTRY_PATH) is not None
    assert load_json(SCHEMA_PATH) is not None


def test_registry_required_top_level_keys():
    reg = load_json(REGISTRY_PATH)
    for key in ("$schema", "schema_version", "default_site_id", "adapters"):
        assert key in reg, f"missing top-level key: {key}"


def test_registry_has_no_unknown_top_level_keys():
    reg = load_json(REGISTRY_PATH)
    allowed = {"$schema", "schema_version", "default_site_id", "adapters"}
    assert set(reg.keys()) == allowed, f"unexpected top-level keys: {set(reg.keys()) - allowed}"


def test_schema_declares_strict_objects():
    schema = load_json(SCHEMA_PATH)
    assert schema.get("additionalProperties") is False
    assert schema["$defs"]["adapter"]["additionalProperties"] is False
    assert schema["$defs"]["contract_source"]["additionalProperties"] is False


def test_expected_schema_version():
    reg = load_json(REGISTRY_PATH)
    assert reg["schema_version"] == "1.0.0"


# ---- B. current registry gate ----

def test_exactly_one_adapter():
    reg = load_json(REGISTRY_PATH)
    assert len(reg["adapters"]) == 1, f"adapter count: {len(reg['adapters'])}"


def test_site_id_and_default_match_bukgu():
    reg = load_json(REGISTRY_PATH)
    assert reg["default_site_id"] == "bukgu"
    assert reg["adapters"][0]["site_id"] == "bukgu"


def test_no_duplicate_site_id():
    reg = load_json(REGISTRY_PATH)
    ids = [a["site_id"] for a in reg["adapters"]]
    assert len(ids) == len(set(ids)), "duplicate site_id present"


def test_second_site_copy_is_rejected():
    reg = load_json(REGISTRY_PATH)
    second = json.loads(json.dumps(reg))
    second["adapters"].append(json.loads(json.dumps(second["adapters"][0])))
    second["adapters"][1]["site_id"] = "namgu"
    second["adapters"][1]["display_name"] = "Nam-gu"
    second["default_site_id"] = "namgu"
    errors = validate_local(second)
    assert errors, "second-site registry should be rejected"


def test_no_runtime_activation_field():
    reg = load_json(REGISTRY_PATH)
    assert "active" not in reg
    assert "activated" not in reg
    assert "runtime_enabled" not in reg
    for adapter in reg["adapters"]:
        assert "active" not in adapter
        assert "enabled" not in adapter


def test_current_registry_passes_validator():
    assert validate_local(load_json(REGISTRY_PATH)) == []


# ---- C. golden identity ----

def test_golden_commit_exact():
    reg = load_json(REGISTRY_PATH)
    assert reg["adapters"][0]["golden_commit"] == GOLDEN_COMMIT


def test_golden_commit_is_40char_hex():
    reg = load_json(REGISTRY_PATH)
    assert HEX40.match(reg["adapters"][0]["golden_commit"]) is not None


def test_role_is_reference_and_frozen_classification():
    adapter = load_json(REGISTRY_PATH)["adapters"][0]
    assert adapter["role"] == "reference_adapter"
    assert "frozen" in adapter["classification_tags"]


# ---- D. frozen sources ----

def test_all_required_contract_kinds_present():
    adapter = load_json(REGISTRY_PATH)["adapters"][0]
    kinds = {s["kind"] for s in adapter["frozen_contract_sources"]}
    missing = EXPECTED_KINDS - kinds
    assert not missing, f"missing contract kinds: {missing}"


def test_frozen_source_paths_exist_and_are_relative():
    adapter = load_json(REGISTRY_PATH)["adapters"][0]
    seen_pairs = set()
    for src in adapter["frozen_contract_sources"]:
        assert REL_PATH.match(src["path"]) is not None, f"not relative: {src['path']}"
        assert not os.path.isabs(src["path"]), f"absolute path: {src['path']}"
        assert ".." not in src["path"].split("/"), f"parent escape: {src['path']}"
        resolved = (REPO_ROOT / src["path"]).resolve()
        assert resolved.is_file(), f"missing frozen source file: {src['path']}"
        assert src["classification"] in CLASSIFICATIONS
        pair = (src["kind"], src["path"])
        assert pair not in seen_pairs, f"duplicate (kind,path): {pair}"
        seen_pairs.add(pair)


def test_frozen_source_symbols_exist_in_file():
    adapter = load_json(REGISTRY_PATH)["adapters"][0]
    for src in adapter["frozen_contract_sources"]:
        if "symbols" not in src:
            continue
        text = read_text_relative(src["path"])
        for symbol in src["symbols"]:
            assert symbol in text, f"symbol {symbol} not found in {src['path']}"


def test_missing_source_copy_is_rejected():
    reg = load_json(REGISTRY_PATH)
    broken = json.loads(json.dumps(reg))
    broken["adapters"][0]["frozen_contract_sources"][0]["path"] = "src/web/static/does-not-exist.js"
    errors = validate_local(broken)
    assert any("missing frozen source" in e for e in errors), f"expected missing-source error, got: {errors}"


def test_second_site_mutation_rejected():
    reg = load_json(REGISTRY_PATH)
    second = json.loads(json.dumps(reg))
    second["adapters"].append(json.loads(json.dumps(second["adapters"][0])))
    second["adapters"][1]["site_id"] = "namgu"
    second["adapters"][1]["display_name"] = "Nam-gu"
    second["default_site_id"] = "namgu"
    errors = validate_local(second)
    assert any("adapter count" in e for e in errors), f"expected adapter-count error, got: {errors}"


def test_duplicate_kind_path_pair_rejected():
    reg = load_json(REGISTRY_PATH)
    dup = json.loads(json.dumps(reg))
    dup["adapters"][0]["frozen_contract_sources"].append(
        json.loads(json.dumps(dup["adapters"][0]["frozen_contract_sources"][0]))
    )
    errors = validate_local(dup)
    pair = (
        dup["adapters"][0]["frozen_contract_sources"][0]["kind"],
        dup["adapters"][0]["frozen_contract_sources"][0]["path"],
    )
    assert any(f"duplicate contract source (kind,path): {pair}" in e for e in errors), \
        f"expected duplicate-pair error, got: {errors}"


def test_different_kinds_same_path_allowed():
    # The real registry references citizen-action-demo-map.js from multiple
    # contract kinds (route IDs, target IDs, public window API). That is valid.
    reg = load_json(REGISTRY_PATH)
    errors = validate_local(reg)
    assert not any("duplicate contract source" in e for e in errors), f"unexpected dup error: {errors}"


# ---- E. no second-site exaggeration ----

def test_no_second_site_identifier():
    reg = load_json(REGISTRY_PATH)
    ids = [a["site_id"] for a in reg["adapters"]]
    assert ids == ["bukgu"]
    for forbidden in ("namgu", "seogu", "nam-gu", "seo-gu"):
        assert forbidden not in json.dumps(reg).lower(), f"second-site id leaked: {forbidden}"


def test_no_runtime_active_or_multi_site_claim():
    text = json.dumps(load_json(REGISTRY_PATH)).lower()
    for claim in ("runtime active", "runtime_active", "activated", "multi-site supported", "multi_site_supported", "second site"):
        assert claim not in text, f"unsupported claim present: {claim}"


# ---- F. schema/types alignment ----

def test_schema_required_fields_match_registry():
    schema = load_json(SCHEMA_PATH)
    assert set(schema["required"]) == {"$schema", "schema_version", "default_site_id", "adapters"}


def test_classification_enum_covers_registry():
    schema = load_json(SCHEMA_PATH)
    enum = set(schema["$defs"]["adapter"]["properties"]["classification_tags"]["items"]["enum"])
    adapter = load_json(REGISTRY_PATH)["adapters"][0]
    for tag in adapter["classification_tags"]:
        assert tag in enum, f"classification {tag} not in schema enum"
    for src in adapter["frozen_contract_sources"]:
        assert src["classification"] in enum


def test_kind_enum_covers_registry():
    schema = load_json(SCHEMA_PATH)
    enum = set(schema["$defs"]["contract_source"]["properties"]["kind"]["enum"])
    adapter = load_json(REGISTRY_PATH)["adapters"][0]
    for src in adapter["frozen_contract_sources"]:
        assert src["kind"] in enum, f"kind {src['kind']} not in schema enum"


def test_schema_no_external_ref():
    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    assert '"$ref": "http' not in schema_text
    assert "localhost" not in schema_text


def test_schema_path_pattern_rejects_traversal_allows_relative():
    import re
    schema = load_json(SCHEMA_PATH)
    pattern = schema["$defs"]["contract_source"]["properties"]["path"]["pattern"]
    rx = re.compile(pattern)
    # Rejected: any parent-traversal component or absolute path.
    assert not rx.match(".."), "bare .. must be rejected"
    assert not rx.match("../secret"), "../secret must be rejected"
    assert not rx.match("src/../secret"), "src/../secret must be rejected"
    assert not rx.match("src/.."), "trailing src/.. must be rejected"
    assert not rx.match("/absolute/path"), "absolute path must be rejected"
    # Allowed: normal repository-relative paths (may contain ".." only as part
    # of a filename, not as a path component).
    assert rx.match("src/web/static/citizen-action-demo-map.js")
    assert rx.match("data/official_clone_fixtures/bukgu_gwangju/home.json")
    assert rx.match("docs/architecture/clone-first-platform-adr.md")
    # Allowed: ".." that is not a path component (e.g. part of a filename).
    assert rx.match("src/web/a..b/citizen-action-demo-map.js")


# ---- local validator (pure helper, mirrors schema intent; no runtime module) ----

def validate_local(reg):
    """Return a list of human-readable errors, or empty list if acceptable.

    This is an in-test pure helper only; it does NOT replace the JSON Schema and
    is not shipped as a runtime component.
    """
    errors = []
    if set(reg.keys()) != {"$schema", "schema_version", "default_site_id", "adapters"}:
        errors.append("top-level keys mismatch")
    if len(reg.get("adapters", [])) != 1:
        errors.append("adapter count != 1")
    ids = [a.get("site_id") for a in reg.get("adapters", [])]
    if len(ids) != len(set(ids)):
        errors.append("duplicate site_id")
    for adapter in reg.get("adapters", []):
        if adapter.get("role") != "reference_adapter":
            errors.append("role not reference_adapter")
        if not HEX40.match(adapter.get("golden_commit", "")):
            errors.append("golden_commit invalid")
        seen_pairs = set()
        for src in adapter.get("frozen_contract_sources", []):
            key = (src.get("kind"), src.get("path"))
            if key in seen_pairs:
                errors.append(f"duplicate contract source (kind,path): {key}")
            seen_pairs.add(key)
            path = src.get("path", "")
            if not REL_PATH.match(path):
                errors.append(f"bad path: {path}")
                continue
            # Reject path components that are exactly ".." (parent traversal).
            if any(component == ".." for component in path.split("/")):
                errors.append(f"parent traversal in path: {path}")
                continue
            resolved = (REPO_ROOT / path).resolve()
            if REPO_ROOT.resolve() not in resolved.parents and resolved != REPO_ROOT.resolve():
                errors.append(f"path escapes repository: {path}")
                continue
            if not resolved.is_file():
                errors.append(f"missing frozen source: {path}")
                continue
            if src.get("classification") not in CLASSIFICATIONS:
                errors.append("bad classification")
    return errors
