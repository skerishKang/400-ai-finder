"""Offline contracts for #1160 official home-route capture inventory.

Tests consume only committed fixtures under data/official_captures/...
No network is performed.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "data" / "official_captures" / "bukgu_gwangju" / "home"
META_PATH = HOME / "capture-metadata.json"
NAV_PATH = HOME / "navigation-inventory.json"
ASSET_PATH = HOME / "asset-inventory.json"
RAW_PATH = HOME / "raw-homepage.html"
NOTES_PATH = HOME / "CAPTURE-NOTES.md"

APPROVED_ORIGIN_PREFIXES = (
    "https://bukgu.gwangju.kr",
    "http://bukgu.gwangju.kr",
)

SECRET_PATTERNS = (
    re.compile(r"set-cookie\s*:", re.I),
    re.compile(r"\bcookie\s*=", re.I),
    re.compile(r"authorization\s*:", re.I),
    re.compile(r"\bapi[_-]?key\b", re.I),
    re.compile(r"\bsecret\b", re.I),
    re.compile(r"\bpassword\b", re.I),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_capture_files_exist():
    for path in (META_PATH, NAV_PATH, ASSET_PATH, RAW_PATH, NOTES_PATH):
        assert path.is_file(), f"missing capture file: {path}"


def test_metadata_schema_and_source_identity():
    meta = _load_json(META_PATH)
    assert meta["schema_version"] == 1
    assert meta["inventory_kind"] == "official_home_source_inventory"
    assert meta["status"] == "capture_only"
    assert meta["route_id"] == "home"
    assert meta["site_id"] == "bukgu_gwangju"

    source = meta["source"]
    for field in (
        "requested_url",
        "final_resolved_url",
        "http_status",
        "content_type",
        "character_encoding",
        "official_page_title",
        "captured_at",
        "raw_content_sha256",
        "capture_method",
        "capture_tool",
    ):
        assert field in source, f"missing source.{field}"
        assert source[field] not in (None, "", "-"), f"blank/placeholder source.{field}"

    assert any(source["requested_url"].startswith(p) for p in APPROVED_ORIGIN_PREFIXES)
    assert any(source["final_resolved_url"].startswith(p) for p in APPROVED_ORIGIN_PREFIXES)
    assert source["http_status"] == 200
    assert "html" in str(source["content_type"]).lower()
    assert source["official_page_title"].strip()
    assert source["official_page_title"] != "-"

    # Valid timezone-aware capture timestamp
    captured = datetime.fromisoformat(source["captured_at"])
    assert captured.tzinfo is not None

    # Absence of official update date must be explicit, not synthetic
    if source.get("source_updated_at") in (None, ""):
        assert source.get("source_updated_at_absence_reason")
        assert source["source_updated_at_absence_reason"] not in ("-", "unknown")
    else:
        assert source["source_updated_at"] != "-"

    assert isinstance(source.get("redirect_chain"), list)
    assert source["redirect_chain"], "redirect_chain must record at least the final hop"


def test_metadata_checksum_matches():
    meta = _load_json(META_PATH)
    claimed = meta["metadata_sha256"]
    assert re.fullmatch(r"[0-9a-f]{64}", claimed)
    body = {k: v for k, v in meta.items() if k != "metadata_sha256"}
    digest = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert digest == claimed


def test_raw_snapshot_checksum_matches():
    meta = _load_json(META_PATH)
    raw = RAW_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == meta["source"]["raw_content_sha256"]
    assert len(raw) == meta["source"]["raw_byte_length"]
    assert len(raw) > 1000


def test_navigation_inventory_schema_nonempty():
    nav = _load_json(NAV_PATH)
    assert nav["schema_version"] == 1
    assert nav["route_id"] == "home"
    assert nav["item_count"] > 0
    assert isinstance(nav["items"], list)
    assert len(nav["items"]) == nav["item_count"]
    assert nav["section_counts"]

    for item in nav["items"]:
        for field in ("order", "section", "visible_label", "source_url", "capture_result"):
            assert field in item
        # no synthetic dash placeholders for URL when empty should use explicit empty string
        assert item["source_url"] != "-"
        assert item["visible_label"] != "-"
        assert item["capture_result"] != "-"


def test_asset_inventory_schema_valid():
    assets = _load_json(ASSET_PATH)
    assert assets["schema_version"] == 1
    assert assets["route_id"] == "home"
    assert assets["item_count"] > 0
    assert len(assets["items"]) == assets["item_count"]
    assert assets["type_counts"]
    assert assets["same_origin_count"] + assets["external_count"] <= assets["item_count"]

    for item in assets["items"]:
        for field in (
            "source_url",
            "resolved_url",
            "asset_type",
            "capture_result",
            "local_copy_recommendation",
        ):
            assert field in item
        assert item["source_url"] != "-"
        assert item["asset_type"] != "-"
        assert item["capture_result"] != "-"


def test_no_placeholder_dash_values_in_core_metadata_fields():
    meta = _load_json(META_PATH)
    source = meta["source"]
    for key, value in source.items():
        if isinstance(value, str):
            assert value != "-", f"source.{key} must not use '-' placeholder"
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    for ek, ev in entry.items():
                        if isinstance(ev, str):
                            assert ev != "-", f"redirect_chain.{ek} must not use '-'"


def test_no_secrets_or_cookies_committed_in_inventory_json():
    for path in (META_PATH, NAV_PATH, ASSET_PATH, NOTES_PATH):
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            assert not pattern.search(text), f"{path.name} matched secret pattern {pattern.pattern}"


def test_boundaries_declare_no_execution_side_effects():
    meta = _load_json(META_PATH)
    b = meta["boundaries"]
    for key in (
        "firecrawl",
        "provider_api",
        "login",
        "form_submission",
        "payment",
        "pii",
        "canvas_integration",
        "route_status_change",
    ):
        assert b.get(key) is False


def test_capture_only_does_not_claim_exact_integration():
    meta = _load_json(META_PATH)
    assert meta["status"] == "capture_only"
    notes = NOTES_PATH.read_text(encoding="utf-8")
    assert "capture_only" in notes or "capture-only" in notes
    assert "capture_required" in notes
    # Must not claim route is exact/complete
    assert "status: exact" not in notes.lower()


def test_home_manifest_entry_remains_capture_required():
    """#1160 is capture-only; do not flip official clone status."""
    manifest_path = ROOT / "tests" / "fixtures" / "official_site_clone_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cap = [e for e in manifest.get("capture_required", []) if e.get("route_id") == "home"]
    assert cap, "home must remain listed under capture_required"
    assert cap[0].get("status") == "capture_required"
    pages = [e for e in manifest.get("pages", []) if e.get("route_id") == "home"]
    assert not pages, "home must not be registered as exact pages entry in this capture-only slice"


def test_no_login_payment_submission_recorded_as_executed_action():
    meta = _load_json(META_PATH)
    assert meta["boundaries"]["login"] is False
    assert meta["boundaries"]["payment"] is False
    assert meta["boundaries"]["form_submission"] is False
    # Inventory may *list* links that point at login portals, but capture_result must be passive.
    nav = _load_json(NAV_PATH)
    for item in nav["items"]:
        assert item["capture_result"] == "recorded"
        assert "executed" not in str(item.get("capture_result", "")).lower()
