"""Contracts for generic official content snapshots and the mayor proposal journey."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from src.bukgu_official_snapshot import canonical_snapshot_sha256, load_official_snapshot


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = ROOT / "data" / "official_snapshots" / "bukgu_gwangju"
BROWSER = ROOT / "src" / "web" / "static" / "bukgu-official-snapshots.js"
FUNCTION = ROOT / "functions" / "api" / "mvp" / "bukgu-official-snapshots.js"
CANVAS = ROOT / "src" / "web" / "static" / "citizen-action-demo-canvas.js"
MAP = ROOT / "src" / "web" / "static" / "citizen-action-demo-map.js"
CHOREOGRAPHY = ROOT / "src" / "web" / "static" / "citizen-first-choreography.js"
SHELL = ROOT / "src" / "web" / "static" / "citizen-first-use-shell.js"
MANIFEST = ROOT / "tests" / "fixtures" / "official_site_clone_manifest.json"

OFFICIAL_CONTENT_ROUTES = {
    "bulky-waste-disposal": {
        "source_url": "https://bukgu.gwangju.kr/menu.es?mid=a10406070000",
        "quest_id": "bulky_waste_disposal_guidance",
        "minimum_rows": 160,
    },
    "passport-guidance": {
        "source_url": "https://bukgu.gwangju.kr/menu.es?mid=a10101060200",
        "quest_id": "passport_guidance",
        "minimum_rows": 10,
    },
    "unmanned-kiosk-guidance": {
        "source_url": "https://bukgu.gwangju.kr/menu.es?mid=a10101020100",
        "quest_id": "unmanned_kiosk_guidance",
        "minimum_rows": 50,
    },
}


def _browser_payload() -> dict:
    text = BROWSER.read_text(encoding="utf-8")
    raw = text.split("root.__BUKGU_OFFICIAL_SNAPSHOTS__ = ", 1)[1]
    raw = raw.split(";\n})(typeof", 1)[0]
    return json.loads(raw)


def _function_payload() -> dict:
    text = FUNCTION.read_text(encoding="utf-8")
    raw = text.split("Object.freeze(", 1)[1].rsplit(");\n", 1)[0]
    return json.loads(raw)


def test_generic_content_snapshots_preserve_provenance_and_sanitized_content():
    for route_id, expected in OFFICIAL_CONTENT_ROUTES.items():
        snapshot = load_official_snapshot(route_id)
        page = snapshot["page"]
        html = page["content_html"]

        assert snapshot["schema_version"] == 2
        assert snapshot["snapshot_kind"] == "official_content_page"
        assert snapshot["source"]["url"] == expected["source_url"]
        assert snapshot["source"]["capture_method"]
        assert page["table_row_count"] >= expected["minimum_rows"]
        assert page["text_length"] > 1000
        assert "<script" not in html.lower()
        assert "<style" not in html.lower()
        assert not re.search(r"\son[a-z]+\s*=", html, re.IGNORECASE)
        assert 'target="_blank"' not in html.lower()


def test_localized_official_assets_exist_and_match_recorded_hashes():
    for route_id in OFFICIAL_CONTENT_ROUTES:
        snapshot = load_official_snapshot(route_id)
        for local_url, expected_hash in snapshot["page"].get("asset_sha256", {}).items():
            assert local_url.startswith("/static/")
            path = ROOT / "src" / "web" / "static" / local_url.removeprefix("/static/")
            assert path.is_file(), f"missing localized asset for {route_id}: {path}"
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash


def test_generated_consumers_match_every_canonical_snapshot():
    expected_payload = {}
    for path in sorted(SNAPSHOT_ROOT.glob("*.json")):
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        expected = dict(snapshot)
        expected["canonical_sha256"] = canonical_snapshot_sha256(snapshot)
        expected_payload[snapshot["route_id"]] = expected

    assert _browser_payload() == expected_payload
    assert _function_payload() == expected_payload


def test_manifest_promotes_three_content_routes_and_keeps_proposals_separate():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    exact = {entry["route_id"]: entry for entry in manifest["pages"]}
    pending = {entry["route_id"] for entry in manifest["capture_required"]}
    proposals = {entry["route_id"] for entry in manifest["product_transitions"]}

    assert set(OFFICIAL_CONTENT_ROUTES).issubset(exact)
    for route_id, expected in OFFICIAL_CONTENT_ROUTES.items():
        entry = exact[route_id]
        snapshot = load_official_snapshot(route_id)
        assert route_id not in pending
        assert entry["content_mode"] == "exact"
        assert entry["network_required_at_runtime"] is False
        assert entry["quest_ids"] == [expected["quest_id"]]
        assert entry["canonical_sha256"] == canonical_snapshot_sha256(snapshot)

    assert {
        "complaint-board",
        "complaint-write",
        "complaint-review",
        "handoff-stop",
        "mayor-office",
        "mayor-complaint-write",
        "mayor-complaint-receipt",
    }.issubset(proposals)
    assert set(OFFICIAL_CONTENT_ROUTES).isdisjoint(proposals)


def test_canvas_uses_official_snapshots_and_mayor_journey_is_independent():
    canvas = CANVAS.read_text(encoding="utf-8")
    route_map = MAP.read_text(encoding="utf-8")
    choreography = CHOREOGRAPHY.read_text(encoding="utf-8")

    assert "function _renderOfficialContentPage" in canvas
    for route_id in OFFICIAL_CONTENT_ROUTES:
        assert f'"{route_id}"' in canvas

    for route_id in ("mayor-office", "mayor-complaint-write", "mayor-complaint-receipt"):
        assert f'"{route_id}"' in route_map
        assert f'case "{route_id}"' in canvas

    assert 'id="btn-open-mayor-office"' in canvas
    assert 'data-action-target="mayor-office-open"' in canvas
    assert 'data-action-target="mayor-message-write"' in canvas
    assert 'querySelector: "#mayor-write-title"' in choreography
    assert 'contentSelector: "#mayor-write-content"' in choreography
    assert 'navigateToRoute("mayor-complaint-receipt")' in choreography
    assert 'var isMayorJourney = _currentJourneyId === "mayor-message-assist"' in choreography
    assert 'var titleSelector = isMayorJourney ? "#mayor-write-title" : "#board-write-title"' in choreography
    assert "window.open" not in canvas


def test_split_transition_reuses_canonical_home_renderer():
    shell = SHELL.read_text(encoding="utf-8")
    start = shell.index("function _renderBukguHomeFixture()")
    delegate = shell.index('window.CitizenActionDemoCanvas.navigateToRoute("home")', start)
    fallback = shell.index('var assets = "/static/images/bukgu-current"', start)
    assert delegate < fallback
