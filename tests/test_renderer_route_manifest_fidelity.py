"""Renderer route ↔ manifest fidelity tests (Issue #1078 CTO clarification).

Enforces the CTO directive: the official page fixture manifest MUST be derived
from the *actual* production renderer route vocabulary — not from a hand-maintained
literal list. These tests dynamically extract the route set from four independent
production sources (JS frozen array, Python frozenset, Canvas JS dispatch,
Manifest capture_required) and assert that all four are EXACTLY the same set.

No hand-maintained literal declares the expected set; the four sources define it
jointly. No `amend`/`rebase`/test-weakening: assertions are strict and complete.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "official_site_clone_manifest.json"

MAP_JS = ROOT / "src" / "web" / "static" / "citizen-action-demo-map.js"
PLAN_PY = ROOT / "src" / "agent" / "citizen_action_plan.py"
CANVAS_JS = ROOT / "src" / "web" / "static" / "citizen-action-demo-canvas.js"

# ---------------------------------------------------------------------------
# Dynamic extraction from four independent sources
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


def _extract_canvas_route_ids() -> set[str]:
    """Parse route dispatch switch from citizen-action-demo-canvas.js.

    Extracts every `case "..."` entry in the _renderRoute function's
    switch(routeId) block.
    """
    text = CANVAS_JS.read_text(encoding="utf-8")
    # Find the switch(routeId) block inside _renderRoute
    start = text.index("switch (routeId) {")
    # Find the closing brace of the switch block
    # Look for the next `default:` after the switch and then the closing `}`
    switch_end = text.index("default:", start)
    # Find closing brace after default
    brace_end = text.index("}", switch_end)
    block = text[start:brace_end]
    ids = re.findall(r'case\s+"([a-z0-9\-]+)"', block)
    return set(ids)


def _extract_manifest_route_ids() -> set[str]:
    """Parse capture_required[].route_id from manifest."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {e["route_id"] for e in manifest.get("capture_required", [])}


def _extract_complete_capture_required() -> set[str]:
    """Parse complete_capture_required list from manifest."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return set(manifest.get("complete_capture_required", []))


def _extract_canvas_render_methods() -> dict[str, str]:
    """Map each route_id to its render method name from the dispatch switch.

    Returns dict like {"home": "_renderHome", "civil-service": "_renderCivilService", ...}
    """
    text = CANVAS_JS.read_text(encoding="utf-8")
    start = text.index("switch (routeId) {")
    switch_end = text.index("default:", start)
    brace_end = text.index("}", switch_end)
    block = text[start:brace_end]
    mapping: dict[str, str] = {}
    for m in re.finditer(
        r'case\s+"([a-z0-9\-]+)":\s*html\s*=\s*(_?[a-zA-Z0-9_]+)\s*\(',
        block,
    ):
        mapping[m.group(1)] = m.group(2)
    return mapping


def _find_defined_functions() -> set[str]:
    """Return set of all function names defined in canvas.js."""
    text = CANVAS_JS.read_text(encoding="utf-8")
    funcs = set()
    for m in re.finditer(r'function\s+(_?[a-zA-Z0-9_]+)\s*\(', text):
        funcs.add(m.group(1))
    return funcs


# ---------------------------------------------------------------------------
# 1. Each source individually is non-empty
# ---------------------------------------------------------------------------

def test_js_route_set_is_not_empty():
    js = _extract_closed_route_ids_from_js()
    assert js, "JS CLOSED_ROUTE_IDS must not be empty"


def test_py_route_set_is_not_empty():
    py = _extract_valid_route_ids_from_py()
    assert py, "Python _VALID_ROUTE_IDS must not be empty"


def test_canvas_route_set_is_not_empty():
    canvas = _extract_canvas_route_ids()
    assert canvas, "Canvas dispatch route set must not be empty"


def test_manifest_route_set_is_not_empty():
    manifest = _extract_manifest_route_ids()
    assert manifest, "Manifest capture_required route set must not be empty"


# ---------------------------------------------------------------------------
# 2. All four sources are identical — not using intersection as expected
# ---------------------------------------------------------------------------

def test_all_four_route_sets_are_identical():
    js = _extract_closed_route_ids_from_js()
    py = _extract_valid_route_ids_from_py()
    canvas = _extract_canvas_route_ids()
    manifest = _extract_manifest_route_ids()
    assert js == py, f"JS != Python — js={sorted(js)} py={sorted(py)}"
    assert py == canvas, f"Python != Canvas — py={sorted(py)} canvas={sorted(canvas)}"
    assert canvas == manifest, (
        f"Canvas != Manifest — canvas={sorted(canvas)} "
        f"manifest={sorted(manifest)}"
    )


# ---------------------------------------------------------------------------
# 3. complete_capture_required matches (if present)
# ---------------------------------------------------------------------------

def test_complete_capture_required_matches_capture_required():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if "complete_capture_required" not in manifest:
        return  # field is optional
    capture = _extract_manifest_route_ids()
    complete = _extract_complete_capture_required()
    assert capture == complete, (
        f"complete_capture_required {sorted(complete)} does not match "
        f"capture_required route_ids {sorted(capture)}"
    )


# ---------------------------------------------------------------------------
# 4. Manifest structural integrity — no duplicate route_id or page_id
# ---------------------------------------------------------------------------

def test_manifest_no_duplicate_route_id():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = manifest.get("capture_required", [])
    ids = [e["route_id"] for e in entries]
    duplicates = {rid for rid in ids if ids.count(rid) > 1}
    assert not duplicates, (
        f"manifest capture_required contains duplicate route_id(s): {duplicates}"
    )


def test_manifest_no_duplicate_page_id():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = manifest.get("capture_required", [])
    ids = [e["page_id"] for e in entries]
    duplicates = {pid for pid in ids if ids.count(pid) > 1}
    assert not duplicates, (
        f"manifest capture_required contains duplicate page_id(s): {duplicates}"
    )


# ---------------------------------------------------------------------------
# 5. Manifest render_target method validation
# ---------------------------------------------------------------------------

def test_manifest_render_target_methods_exist_in_canvas():
    manifest_entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = manifest_entries.get("capture_required", [])
    defined = _find_defined_functions()
    for entry in entries:
        rt = entry.get("render_target", "")
        m = re.search(r'(\._?[a-zA-Z0-9_]+)\s*\(', rt)
        assert m, (
            f"entry '{entry.get('route_id')}' render_target has no parseable "
            f"method: {rt}"
        )
        method = m.group(1).lstrip(".")
        assert method in defined, (
            f"entry '{entry.get('route_id')}' render_target method "
            f"'{method}' not found as a function in canvas.js"
        )


def test_manifest_render_target_matches_dispatch():
    """Every manifest entry's render_target method must be what the dispatch
    switch actually calls for that route_id."""
    dispatch = _extract_canvas_render_methods()
    manifest_entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for entry in manifest_entries.get("capture_required", []):
        rid = entry["route_id"]
        rt = entry.get("render_target", "")
        m = re.search(r'(\._?[a-zA-Z0-9_]+)\s*\(', rt)
        assert m, f"entry '{rid}' render_target unparseable: {rt}"
        manifest_method = m.group(1).lstrip(".")
        dispatch_method = dispatch.get(rid)
        assert dispatch_method is not None, (
            f"route '{rid}' not found in canvas dispatch switch"
        )
        assert manifest_method == dispatch_method, (
            f"route '{rid}': manifest render_target calls '{manifest_method}' "
            f"but canvas dispatch calls '{dispatch_method}'"
        )


def test_manfest_render_target_must_not_reference_nonexistent_method():
    """If a render_target string references a function that does not exist
    in canvas.js, the test must fail."""
    defined = _find_defined_functions()
    manifest_entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for entry in manifest_entries.get("capture_required", []):
        rt = entry.get("render_target", "")
        m = re.search(r'(\._?[a-zA-Z0-9_]+)\s*\(', rt)
        if not m:
            continue  # unparseable is flagged by another test
        method = m.group(1).lstrip(".")
        # This will fail, which is the desired behavior for a bad reference
        method_defined = method in defined
        assert method_defined, (
            f"entry '{entry.get('route_id')}' render_target references "
            f"non-existent method '{method}'"
        )


# ---------------------------------------------------------------------------
# 6. Remove-discipline: deprecated quests must NOT leak into the manifest
# ---------------------------------------------------------------------------

def test_manifest_excludes_deprecated_quests():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    all_ids = {e["route_id"] for e in manifest.get("capture_required", [])}
    manifest_text = MANIFEST.read_text(encoding="utf-8").lower()
    assert "move_in_report_guidance" not in manifest_text
    assert "public_health_center_guidance" not in manifest_text
    assert "move_in_report_guidance" not in all_ids
    assert "public_health_center_guidance" not in all_ids
