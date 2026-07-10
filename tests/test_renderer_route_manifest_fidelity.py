"""Renderer route ↔ manifest fidelity tests (Issue #1078 CTO clarification).

Enforces the CTO directive: the official page fixture manifest MUST be derived
from the *actual* production renderer route vocabulary — not from a hand-maintained
literal list. These tests dynamically extract the route set from the production
renderer source (JS map + Python action-plan vocabulary) and assert the manifest's
`capture_required` route set is EXACTLY that set.

No `amend`/`rebase`/test-weakening: assertions are strict and complete.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "official_site_clone_manifest.json"

MAP_JS = ROOT / "src" / "web" / "static" / "citizen-action-demo-map.js"
PLAN_PY = ROOT / "src" / "agent" / "citizen_action_plan.py"

# Canonical 13-route set from the CTO clarification (the expected dynamic result).
EXPECTED_ROUTES = [
    "home",
    "civil-service",
    "complaint-category",
    "complaint-illegal-parking",
    "bulky-waste-disposal",
    "passport-guidance",
    "unmanned-kiosk-guidance",
    "apartment-dept",
    "apartment-info",
    "complaint-intake",
    "complaint-board",
    "complaint-review",
    "handoff-stop",
]


# ---------------------------------------------------------------------------
# Dynamic extraction from production renderer sources
# ---------------------------------------------------------------------------

def _extract_closed_route_ids_from_js() -> set[str]:
    """Parse CLOSED_ROUTE_IDS from citizen-action-demo-map.js (frozen array)."""
    text = MAP_JS.read_text(encoding="utf-8")
    start = text.index("CLOSED_ROUTE_IDS = Object.freeze([")
    body = text[start:]
    end = body.index("]);")
    body = body[:end]
    ids = re.findall(r'"([a-z0-9\-]+)"', body)
    return set(ids)


def _extract_valid_route_ids_from_py() -> set[str]:
    """Parse _VALID_ROUTE_IDS frozenset from citizen_action_plan.py."""
    text = PLAN_PY.read_text(encoding="utf-8")
    start = text.index("_VALID_ROUTE_IDS: frozenset[str] = frozenset({")
    body = text[start:]
    end = body.index("})")
    body = body[:end]
    ids = re.findall(r'"([a-z0-9\-]+)"', body)
    return set(ids)


def _manifest_capture_routes() -> set[str]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {e["route_id"] for e in manifest.get("capture_required", [])}


# ---------------------------------------------------------------------------
# 1. Both renderer sources declare exactly the canonical 13-route set
# ---------------------------------------------------------------------------

def test_js_closed_route_ids_match_canonical_set():
    got = _extract_closed_route_ids_from_js()
    assert got == set(EXPECTED_ROUTES), (
        f"CLOSED_ROUTE_IDS in map.js = {sorted(got)}; "
        f"expected {sorted(EXPECTED_ROUTES)}"
    )


def test_py_valid_route_ids_match_canonical_set():
    got = _extract_valid_route_ids_from_py()
    assert got == set(EXPECTED_ROUTES), (
        f"_VALID_ROUTE_IDS in plan.py = {sorted(got)}; "
        f"expected {sorted(EXPECTED_ROUTES)}"
    )


def test_js_and_py_route_vocabularies_agree():
    js = _extract_closed_route_ids_from_js()
    py = _extract_valid_route_ids_from_py()
    assert js == py, (
        f"renderer route vocabularies disagree — js={sorted(js)} py={sorted(py)}"
    )


# ---------------------------------------------------------------------------
# 2. Manifest capture_required set is EXACTLY the dynamic renderer route set
#    (not a separately hand-maintained literal)
# ---------------------------------------------------------------------------

def test_manifest_capture_routes_equal_renderer_js_routes():
    manifest_routes = _manifest_capture_routes()
    renderer_routes = _extract_closed_route_ids_from_js()
    assert manifest_routes == renderer_routes, (
        f"manifest capture_required routes {sorted(manifest_routes)} do not equal "
        f"renderer (map.js) routes {sorted(renderer_routes)}"
    )


def test_manifest_capture_routes_equal_renderer_py_routes():
    manifest_routes = _manifest_capture_routes()
    renderer_routes = _extract_valid_route_ids_from_py()
    assert manifest_routes == renderer_routes, (
        f"manifest capture_required routes {sorted(manifest_routes)} do not equal "
        f"renderer (plan.py) routes {sorted(renderer_routes)}"
    )


def test_manifest_capture_routes_count_is_thirteen():
    manifest_routes = _manifest_capture_routes()
    assert len(manifest_routes) == 13, (
        f"expected exactly 13 capture_required routes, got {len(manifest_routes)}"
    )


# ---------------------------------------------------------------------------
# 3. Remove-discipline: deprecated quests must NOT leak into the manifest
# ---------------------------------------------------------------------------

def test_manifest_excludes_deprecated_quests():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    all_ids = {e["route_id"] for e in manifest.get("capture_required", [])}
    manifest_text = MANIFEST.read_text(encoding="utf-8").lower()
    assert "move_in_report_guidance" not in manifest_text, (
        "move_in_report_guidance must not appear in the manifest (not a renderer route)"
    )
    assert "public_health_center_guidance" not in manifest_text, (
        "public_health_center_guidance must not appear in the manifest (not a renderer route)"
    )
    # Neither is a route_id entry
    assert "move_in_report_guidance" not in all_ids
    assert "public_health_center_guidance" not in all_ids
