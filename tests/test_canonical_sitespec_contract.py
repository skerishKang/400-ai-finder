"""Contract test for the canonical SiteSpec foundation (#1225, additive).

Pure stdlib + pytest only. No runtime loader, no new dependency, no network.

This is an additive data foundation: it introduces a canonical SiteSpec schema
and the Buk-gu canonical instance without migrating the compatibility registry
(configs/site-registry.json), changing Python/Cloudflare runtime behavior, or
rewriting historical fixture identities.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "configs" / "sitespec.schema.json"
INSTANCE_PATH = REPO_ROOT / "configs" / "sites" / "bukgu_gwangju.sitespec.json"
REGISTRY_PATH = REPO_ROOT / "configs" / "site-registry.json"

CANONICAL_SITE_ID = "bukgu_gwangju"
LEGACY_ALIAS = "bukgu"
PUBLIC_DOMAIN = "bukgu.gwangju.kr"
GOLDEN_COMMIT = "7217c0f738a6aa4468bdde3119d8c2d1ec9dd610"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
HOSTNAME = re.compile(
    r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)

EXPECTED_TOP_KEYS = {
    "$schema",
    "schema_version",
    "site_id",
    "legacy_ids",
    "jurisdiction",
    "display",
    "domains",
    "runtime",
    "clone",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---- local pure validator (mirrors the schema intent; stdlib only) ----
#
# The repo convention (see test_site_compatibility_registry.py) keeps an
# in-test helper instead of importing a schema engine. It is not shipped as a
# runtime component.

def validate_sitespec(doc):
    """Return a list of human-readable errors, or empty list if acceptable."""
    errors = []
    if not isinstance(doc, dict):
        return ["not an object"]
    unknown = set(doc.keys()) - EXPECTED_TOP_KEYS
    if unknown:
        errors.append(f"unknown top-level keys: {sorted(unknown)}")
    missing = EXPECTED_TOP_KEYS - set(doc.keys())
    if missing:
        errors.append(f"missing required keys: {sorted(missing)}")
    if "$schema" in doc and not isinstance(doc["$schema"], str):
        errors.append("$schema must be a string")
    if "schema_version" in doc and not SEMVER.match(doc.get("schema_version", "")):
        errors.append("schema_version must be x.y.z")
    site_id = doc.get("site_id", "")
    if not isinstance(site_id, str) or not ID_PATTERN.match(site_id):
        errors.append("site_id must be non-empty [a-z0-9_-] string")
    legacy_ids = doc.get("legacy_ids", [])
    if not isinstance(legacy_ids, list) or not legacy_ids:
        errors.append("legacy_ids must be a non-empty array")
    elif len(legacy_ids) != len(set(legacy_ids)):
        errors.append("legacy_ids must not contain duplicates")
    else:
        for lid in legacy_ids:
            if not isinstance(lid, str) or not ID_PATTERN.match(lid):
                errors.append(f"invalid legacy id: {lid!r}")
        if site_id in legacy_ids:
            errors.append("canonical site_id must not appear in legacy_ids")
    jurisdiction = doc.get("jurisdiction", {})
    if not isinstance(jurisdiction, dict):
        errors.append("jurisdiction must be an object")
    else:
        for key in ("canonical_name", "short_name"):
            if not isinstance(jurisdiction.get(key), str) or not jurisdiction.get(key):
                errors.append(f"jurisdiction.{key} must be non-empty")
        aliases = jurisdiction.get("aliases", [])
        if not isinstance(aliases, list) or len(aliases) != len(set(aliases)):
            errors.append("jurisdiction.aliases must be unique array")
    display = doc.get("display", {})
    if not isinstance(display, dict):
        errors.append("display must be an object")
    else:
        if not isinstance(display.get("default_label"), str) or not display.get("default_label"):
            errors.append("display.default_label must be non-empty")
        locale_labels = display.get("locale_labels", {})
        if not isinstance(locale_labels, dict) or not locale_labels:
            errors.append("display.locale_labels must be a non-empty object")
    domains = doc.get("domains", {})
    public = domains.get("public", []) if isinstance(domains, dict) else []
    if not isinstance(public, list) or not public:
        errors.append("domains.public must be a non-empty array")
    elif len(public) != len(set(public)):
        errors.append("domains.public must not contain duplicates")
    else:
        for host in public:
            if not isinstance(host, str) or not HOSTNAME.match(host):
                errors.append(f"invalid public hostname: {host!r}")
    runtime = doc.get("runtime", {})
    if not isinstance(runtime, dict):
        errors.append("runtime must be an object")
    else:
        for key in ("python_profile", "cloudflare_adapter"):
            if not isinstance(runtime.get(key), str) or not runtime.get(key):
                errors.append(f"runtime.{key} must be non-empty")
        if runtime.get("wired") is not False:
            errors.append("runtime.wired must be false (no wiring in this phase)")
    clone = doc.get("clone", {})
    if not isinstance(clone, dict):
        errors.append("clone must be an object")
    else:
        if not HEX40.match(clone.get("golden_commit", "")):
            errors.append("clone.golden_commit must be 40-char lowercase hex SHA")
        if not isinstance(clone.get("golden_commit_subject"), str) or not clone.get("golden_commit_subject"):
            errors.append("clone.golden_commit_subject must be non-empty")
    return errors


# ---- A. JSON parse + canonical instance schema contract ----

def test_schema_and_instance_are_valid_json():
    assert load_json(SCHEMA_PATH) is not None
    assert load_json(INSTANCE_PATH) is not None


def test_instance_passes_schema_contract():
    assert validate_sitespec(load_json(INSTANCE_PATH)) == []


def test_schema_is_fail_closed():
    schema = load_json(SCHEMA_PATH)
    assert schema.get("additionalProperties") is False
    assert schema.get("required") == sorted(EXPECTED_TOP_KEYS) or set(schema.get("required", [])) == EXPECTED_TOP_KEYS
    for section in ("jurisdiction", "display", "domains", "runtime", "clone"):
        assert schema["properties"][section].get("additionalProperties") is False, section


def test_schema_version_required_and_semver():
    schema = load_json(SCHEMA_PATH)
    assert "schema_version" in schema["required"]
    pattern = schema["properties"]["schema_version"]["pattern"]
    assert SEMVER.pattern == pattern


# ---- B. canonical instance contract (Buk-gu) ----

def test_canonical_site_id():
    doc = load_json(INSTANCE_PATH)
    assert doc["site_id"] == CANONICAL_SITE_ID


def test_legacy_alias_present():
    doc = load_json(INSTANCE_PATH)
    assert LEGACY_ALIAS in doc["legacy_ids"]


def test_canonical_id_not_in_legacy_ids():
    doc = load_json(INSTANCE_PATH)
    assert doc["site_id"] not in doc["legacy_ids"]


def test_public_domain_present():
    doc = load_json(INSTANCE_PATH)
    assert PUBLIC_DOMAIN in doc["domains"]["public"]


def test_schema_ref_and_version_present():
    doc = load_json(INSTANCE_PATH)
    assert doc["$schema"] == "configs/sitespec.schema.json"
    assert SEMVER.match(doc["schema_version"])


def test_golden_commit_matches_repository_frozen_baseline():
    doc = load_json(INSTANCE_PATH)
    assert doc["clone"]["golden_commit"] == GOLDEN_COMMIT
    assert HEX40.match(doc["clone"]["golden_commit"])


def test_runtime_not_wired():
    doc = load_json(INSTANCE_PATH)
    assert doc["runtime"]["wired"] is False


# ---- C. fail-closed rejections ----

def test_duplicate_legacy_ids_rejected():
    doc = json.loads(json.dumps(load_json(INSTANCE_PATH)))
    doc["legacy_ids"] = ["bukgu", "bukgu"]
    errors = validate_sitespec(doc)
    assert any("duplicate" in e for e in errors), f"expected duplicate error, got: {errors}"


def test_unknown_top_level_key_rejected():
    doc = json.loads(json.dumps(load_json(INSTANCE_PATH)))
    doc["unknown_field"] = True
    errors = validate_sitespec(doc)
    assert any("unknown" in e for e in errors), f"expected unknown-key error, got: {errors}"


def test_invalid_canonical_identity_rejected():
    # An empty site_id is schema-invalid.
    doc = json.loads(json.dumps(load_json(INSTANCE_PATH)))
    doc["site_id"] = ""
    errors = validate_sitespec(doc)
    assert any("site_id" in e for e in errors), f"expected site_id error, got: {errors}"


def test_canonical_id_colliding_with_legacy_rejected():
    doc = json.loads(json.dumps(load_json(INSTANCE_PATH)))
    doc["legacy_ids"] = ["bukgu", "bukgu_gwangju"]
    errors = validate_sitespec(doc)
    assert any("must not appear in legacy_ids" in e for e in errors), f"expected collision error, got: {errors}"


def test_invalid_hostname_rejected():
    doc = json.loads(json.dumps(load_json(INSTANCE_PATH)))
    doc["domains"]["public"] = ["not a hostname/with/slash"]
    errors = validate_sitespec(doc)
    assert any("hostname" in e for e in errors), f"expected hostname error, got: {errors}"


def test_wired_true_rejected():
    doc = json.loads(json.dumps(load_json(INSTANCE_PATH)))
    doc["runtime"]["wired"] = True
    errors = validate_sitespec(doc)
    assert any("wired" in e for e in errors), f"expected wired error, got: {errors}"


# ---- D. scope: existing compatibility registry untouched ----

def test_site_registry_unchanged_by_scope():
    """The existing compatibility registry must not be modified by this PR."""
    result = subprocess.run(
        ["git", "diff", "HEAD", "--name-only", "--", "configs/site-registry.json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"git diff failed: {result.stderr}"
    assert result.stdout.strip() == "", f"site-registry.json modified: {result.stdout.strip()}"


def test_registry_still_uses_legacy_default():
    reg = load_json(REGISTRY_PATH)
    assert reg["default_site_id"] == LEGACY_ALIAS
    assert reg["adapters"][0]["site_id"] == LEGACY_ALIAS
