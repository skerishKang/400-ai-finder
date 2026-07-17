"""#1198: fail-closed visual approval gate for resident-default home promotion.

Records existing #1197 / PR #1200 restoration provenance only. Does not invent
a new project-owner visual approval event. Fixture integrity remains independent
of resident-default selection.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
CANVAS = STATIC / "citizen-action-demo-canvas.js"
REGISTRY = STATIC / "clone-renderer-approval-registry.js"
GATE = STATIC / "clone-renderer-approval-gate.js"
HTML = STATIC / "citizen-action-demo.html"
CANONICAL = ROOT / "data" / "official_clone_fixtures" / "bukgu_gwangju" / "home.json"

APPROVED_RENDERER_ID = "bukgu_gwangju.home.designed.approved"
FIXTURE_RENDERER_ID = "bukgu_gwangju.home.fixture.candidate"
MARKER_BEGIN = "CLONE_APPROVED_HOME_RENDERER_BEGIN"
MARKER_END = "CLONE_APPROVED_HOME_RENDERER_END"
APPROVED_SOURCE_COMMIT = "87db3e1ce7d01646a8fc0e8eed6ce2fc63b7ebaa"
EXPECTED_FIXTURE_SHA = (
    "81b27b98fadc091ca852079f89ea93da45b93f250372835b8b352726b2faeaed"
)
EXPECTED_UNRESOLVED_ASSETS = 174


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_static(name: str) -> str:
    return _read(STATIC / name)


def extract_approved_home_source(canvas_js: str) -> str:
    """Deterministic marker-boundary extraction shared with registry pin."""
    assert canvas_js.count(MARKER_BEGIN) == 1
    assert canvas_js.count(MARKER_END) == 1
    begin_idx = canvas_js.index(MARKER_BEGIN)
    start = canvas_js.index("\n", begin_idx) + 1
    end_idx = canvas_js.index(MARKER_END)
    end_line = canvas_js.rfind("\n", 0, end_idx) + 1
    return canvas_js[start:end_line]


def approved_home_source_sha256(canvas_js: str | None = None) -> str:
    body = extract_approved_home_source(canvas_js or _read(CANVAS))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _run_node(script: str, timeout: int = 30) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(script)
        path = handle.name
    try:
        return subprocess.run(
            ["node", path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    finally:
        os.unlink(path)


def _load_registry_via_node(registry_js: str | None = None) -> dict:
    script = """
'use strict';
var vm = require('vm');
var sandbox = { window: {}, console: console };
sandbox.window = sandbox;
var cx = vm.createContext(sandbox);
vm.runInContext(%s, cx);
process.stdout.write(JSON.stringify(sandbox.__CLONE_RENDERER_APPROVAL_REGISTRY__));
""" % json.dumps(registry_js if registry_js is not None else _read_static(
        "clone-renderer-approval-registry.js"
    ))
    result = _run_node(script)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _render_home(
    search: str = "",
    *,
    include_registry: bool = True,
    include_gate: bool = True,
    registry_js: str | None = None,
    gate_js: str | None = None,
) -> str:
    parts = [
        json.dumps(_read_static("bukgu-official-snapshots.js")),
        json.dumps(_read_static("bukgu-home-clone-fixture.js")),
    ]
    run_lines = [
        "vm.runInContext(snapshotJS, cx);",
        "vm.runInContext(homeFixtureJS, cx);",
    ]
    if include_registry:
        parts.append(
            json.dumps(
                registry_js
                if registry_js is not None
                else _read_static("clone-renderer-approval-registry.js")
            )
        )
        run_lines.append("vm.runInContext(approvalRegistryJS, cx);")
    if include_gate:
        parts.append(
            json.dumps(
                gate_js if gate_js is not None else _read_static("clone-renderer-approval-gate.js")
            )
        )
        run_lines.append("vm.runInContext(approvalGateJS, cx);")
    parts.extend(
        [
            json.dumps(_read_static("citizen-action-demo-map.js")),
            json.dumps(_read_static("citizen-action-demo-canvas.js")),
        ]
    )
    run_lines.extend(
        [
            "vm.runInContext(mapJS, cx);",
            "vm.runInContext(canvasJS, cx);",
        ]
    )

    decl = ["var snapshotJS = %s;", "var homeFixtureJS = %s;"]
    if include_registry:
        decl.append("var approvalRegistryJS = %s;")
    if include_gate:
        decl.append("var approvalGateJS = %s;")
    decl.extend(["var mapJS = %s;", "var canvasJS = %s;"])

    script = """
'use strict';
var vm = require('vm');
var capturedHTML = '';
function makeElement(id) {
  return {
    id: id, style: {}, offsetHeight: 0,
    get innerHTML() { return capturedHTML; },
    set innerHTML(v) { capturedHTML = v; },
    addEventListener: function() {},
    querySelector: function() { return null; }
  };
}
var sandbox = {
  document: { getElementById: function(id) {
    if (id === 'demo-canvas') return makeElement('demo-canvas');
    return null;
  }},
  console: { log: function() {}, error: function() {} },
  setTimeout: function(fn) { fn(); return 1; },
  clearTimeout: function() {},
  URLSearchParams: URLSearchParams,
  location: { search: %s }
};
sandbox.window = sandbox;
var cx = vm.createContext(sandbox);
%s
%s
sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
process.stdout.write(capturedHTML);
""" % (
        json.dumps(search),
        "\n".join(decl) % tuple(parts),
        "\n".join(run_lines),
    )
    result = _run_node(script)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _resolve_selection(search: str = "", registry_override_js: str | None = None) -> dict:
    """Call gate.resolveHomeSelection in Node with optional registry override."""
    registry_src = (
        registry_override_js
        if registry_override_js is not None
        else _read_static("clone-renderer-approval-registry.js")
    )
    script = """
'use strict';
var vm = require('vm');
var sandbox = { window: {}, console: console, URLSearchParams: URLSearchParams, location: { search: %s } };
sandbox.window = sandbox;
var cx = vm.createContext(sandbox);
vm.runInContext(%s, cx);
vm.runInContext(%s, cx);
var sel = sandbox.CloneRendererApprovalGate.resolveHomeSelection({
  search: %s,
  registry: sandbox.__CLONE_RENDERER_APPROVAL_REGISTRY__
});
process.stdout.write(JSON.stringify(sel));
""" % (
        json.dumps(search),
        json.dumps(registry_src),
        json.dumps(_read_static("clone-renderer-approval-gate.js")),
        json.dumps(search),
    )
    result = _run_node(script)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _mutate_registry_js(mutator) -> str:
    """Load registry, apply mutator(dict), re-emit as assignable JS global."""
    data = _load_registry_via_node()
    mutator(data)
    return (
        "(function(root){root.__CLONE_RENDERER_APPROVAL_REGISTRY__="
        + json.dumps(data)
        + ";})(typeof window!=='undefined'?window:globalThis);"
    )


# ---------------------------------------------------------------------------
# Static presence / load order / integrity
# ---------------------------------------------------------------------------


def test_approval_static_files_present():
    assert REGISTRY.is_file()
    assert GATE.is_file()
    assert MARKER_BEGIN in _read(CANVAS)
    assert MARKER_END in _read(CANVAS)
    assert "function _renderApprovedHome" in _read(CANVAS)
    assert "function _resolveHomeRendererSelection" in _read(CANVAS)
    assert "function _renderHomeApprovalUnavailable" in _read(CANVAS)


def test_html_load_order_registry_gate_before_canvas():
    html = _read(HTML)
    reg_idx = html.index("clone-renderer-approval-registry.js")
    gate_idx = html.index("clone-renderer-approval-gate.js")
    map_idx = html.index("citizen-action-demo-map.js")
    canvas_idx = html.index("citizen-action-demo-canvas.js")
    fixture_idx = html.index("bukgu-home-clone-fixture.js")
    assert fixture_idx < reg_idx < gate_idx < map_idx < canvas_idx


def test_approved_renderer_source_integrity_matches_registry():
    registry = _load_registry_via_node()
    entry = registry["routes"]["home"]["renderers"][APPROVED_RENDERER_ID]
    pinned = entry["renderer_integrity"]["sha256"]
    actual = approved_home_source_sha256()
    assert re.fullmatch(r"[a-f0-9]{64}", pinned)
    assert pinned == actual


def test_fixture_source_change_does_not_match_approved_identity():
    """Fixture projection symbol must not be confused with approved integrity body."""
    canvas = _read(CANVAS)
    approved_body = extract_approved_home_source(canvas)
    assert "_renderHomeFixtureProjection" not in approved_body
    assert "bg-home-fixture-root" not in approved_body
    fixture_start = canvas.index("function _renderHomeFixtureProjection")
    fixture_end = canvas.index("function _resolveHomeRendererSelection")
    fixture_body = canvas[fixture_start:fixture_end]
    fixture_hash = hashlib.sha256(fixture_body.encode("utf-8")).hexdigest()
    approved_hash = approved_home_source_sha256(canvas)
    assert fixture_hash != approved_hash


def test_approved_source_drift_fails_contract():
    canvas = _read(CANVAS)
    body = extract_approved_home_source(canvas)
    drifted = body.replace("bg-home-quick-link", "bg-home-quick-link-DRIFTED", 1)
    assert drifted != body
    drifted_hash = hashlib.sha256(drifted.encode("utf-8")).hexdigest()
    pinned = _load_registry_via_node()["routes"]["home"]["renderers"][
        APPROVED_RENDERER_ID
    ]["renderer_integrity"]["sha256"]
    assert drifted_hash != pinned


def test_default_selection_code_requires_registry_gate_not_hardcoded_bypass():
    canvas = _read(CANVAS)
    # Selection must go through gate; no silent designed-home bypass path.
    home_fn = canvas[
        canvas.index("function _renderHome(state)") : canvas.index(
            "function _renderCivilService"
        )
    ]
    assert "_resolveHomeRendererSelection" in home_fn
    assert "mode === \"approved_default\"" in home_fn or "mode === 'approved_default'" in home_fn
    assert "_renderHomeApprovalUnavailable" in home_fn
    # Must not call designed home without selection.
    assert "return _renderApprovedHome(state);" in home_fn
    # Must not fall back to fixture on ordinary path.
    assert "fixture_preview" in home_fn


# ---------------------------------------------------------------------------
# Ordinary approved path
# ---------------------------------------------------------------------------


def test_ordinary_home_uses_approved_designed_renderer():
    html = _render_home("")
    assert 'data-renderer-id="%s"' % APPROVED_RENDERER_ID in html
    assert "home-mayor-card.png" in html
    assert "bg-home-quick-link" in html
    assert "bg-home-fixture-root" not in html
    assert "bg-page--home-fixture" not in html
    assert "bg-page--home-approval-unavailable" not in html


def test_ordinary_home_is_not_fixture_root():
    html = _render_home("")
    assert "bg-home-fixture-root" not in html
    assert 'data-preview-only="true"' not in html


def test_ordinary_home_has_approved_identity_markers():
    html = _render_home("")
    assert 'data-renderer-id="%s"' % APPROVED_RENDERER_ID in html
    assert 'data-visual-review-state="visual_review_approved"' in html
    assert 'data-resident-default-approved="true"' in html


def test_ordinary_home_resident_default_approved_state():
    sel = _resolve_selection("")
    assert sel["mode"] == "approved_default"
    assert sel["resident_default_approved"] is True
    assert sel["renderer_id"] == APPROVED_RENDERER_ID
    entry = sel["entry"]
    assert entry["approval_state"] == "resident_default_approved"
    assert entry["approval_provenance"]["issue"] == "#1197"
    assert entry["approval_provenance"]["pull_request"] == "#1200"
    assert entry["approval_provenance"]["approved_source_commit"] == APPROVED_SOURCE_COMMIT


# ---------------------------------------------------------------------------
# Fail-closed ordinary path
# ---------------------------------------------------------------------------


def test_registry_missing_fail_closed_unavailable():
    html = _render_home("", include_registry=False, include_gate=True)
    assert "bg-page--home-approval-unavailable" in html
    assert "bg-home-fixture-root" not in html
    assert "home-mayor-card.png" not in html
    assert 'data-resident-default-approved="false"' in html


def test_gate_missing_fail_closed_unavailable():
    html = _render_home("", include_registry=True, include_gate=False)
    assert "bg-page--home-approval-unavailable" in html
    assert "bg-home-fixture-root" not in html


def test_registry_malformed_fail_closed_unavailable():
    bad = (
        "(function(root){root.__CLONE_RENDERER_APPROVAL_REGISTRY__="
        "{schema_version:99,routes:null};})(typeof window!=='undefined'?window:globalThis);"
    )
    html = _render_home("", registry_js=bad)
    assert "bg-page--home-approval-unavailable" in html
    assert "bg-home-fixture-root" not in html


def test_route_approval_entry_missing_fail_closed():
    def mut(data):
        data["routes"] = {}

    html = _render_home("", registry_js=_mutate_registry_js(mut))
    assert "bg-page--home-approval-unavailable" in html
    assert "bg-home-fixture-root" not in html


def test_approved_renderer_id_unknown_fail_closed():
    def mut(data):
        data["routes"]["home"]["resident_default_renderer_id"] = "unknown.renderer"
        # keep renderers map without that id

    html = _render_home("", registry_js=_mutate_registry_js(mut))
    assert "bg-page--home-approval-unavailable" in html
    assert "bg-home-fixture-root" not in html


def test_visual_review_pending_not_selectable_as_default():
    def mut(data):
        entry = data["routes"]["home"]["renderers"][APPROVED_RENDERER_ID]
        entry["visual_review_state"] = "visual_review_pending"
        entry["approval_state"] = "visual_review_pending"
        entry["resident_default_approved"] = False

    html = _render_home("", registry_js=_mutate_registry_js(mut))
    assert "bg-page--home-approval-unavailable" in html
    assert "home-mayor-card.png" not in html


def test_visual_review_rejected_not_selectable_as_default():
    def mut(data):
        entry = data["routes"]["home"]["renderers"][APPROVED_RENDERER_ID]
        entry["visual_review_state"] = "visual_review_rejected"
        entry["approval_state"] = "visual_review_rejected"
        entry["resident_default_approved"] = False

    html = _render_home("", registry_js=_mutate_registry_js(mut))
    assert "bg-page--home-approval-unavailable" in html


def test_resident_default_approved_false_not_selectable():
    def mut(data):
        entry = data["routes"]["home"]["renderers"][APPROVED_RENDERER_ID]
        entry["resident_default_approved"] = False

    html = _render_home("", registry_js=_mutate_registry_js(mut))
    assert "bg-page--home-approval-unavailable" in html


def test_missing_approval_provenance_not_selectable():
    def mut(data):
        entry = data["routes"]["home"]["renderers"][APPROVED_RENDERER_ID]
        del entry["approval_provenance"]

    html = _render_home("", registry_js=_mutate_registry_js(mut))
    assert "bg-page--home-approval-unavailable" in html


def test_missing_integrity_sha_not_selectable():
    def mut(data):
        entry = data["routes"]["home"]["renderers"][APPROVED_RENDERER_ID]
        entry["renderer_integrity"]["sha256"] = "not-a-real-sha"

    html = _render_home("", registry_js=_mutate_registry_js(mut))
    assert "bg-page--home-approval-unavailable" in html


# ---------------------------------------------------------------------------
# Fixture candidate / preview
# ---------------------------------------------------------------------------


def test_fixture_candidate_is_pending_preview_only():
    registry = _load_registry_via_node()
    fixture = registry["routes"]["home"]["renderers"][FIXTURE_RENDERER_ID]
    assert fixture["visual_review_state"] == "visual_review_pending"
    assert fixture["resident_default_approved"] is False
    assert fixture["preview_only"] is True
    assert fixture["exact"] is False
    assert fixture["capture_state"] == "capture_required"
    assert fixture["unresolved_asset_count"] == EXPECTED_UNRESOLVED_ASSETS
    assert fixture["fixture_sha256"] == EXPECTED_FIXTURE_SHA
    assert fixture["fixture_id"] == "bukgu_gwangju.home.clone.2026-07-15"


def test_explicit_fixture_query_accesses_fixture_renderer():
    for query in ("?home-fixture=1", "?home-projection=fixture"):
        html = _render_home(query)
        assert "bg-home-fixture-root" in html
        assert 'data-renderer-id="%s"' % FIXTURE_RENDERER_ID in html
        assert 'data-visual-review-state="visual_review_pending"' in html
        assert 'data-resident-default-approved="false"' in html
        assert 'data-preview-only="true"' in html
        assert 'data-home-fixture-sha256="%s"' % EXPECTED_FIXTURE_SHA in html
        assert APPROVED_RENDERER_ID not in html or (
            'data-renderer-id="%s"' % APPROVED_RENDERER_ID not in html
        )


def test_fixture_query_does_not_mutate_ordinary_default_metadata():
    ordinary = _resolve_selection("")
    preview = _resolve_selection("?home-fixture=1")
    ordinary_again = _resolve_selection("")
    assert ordinary["mode"] == "approved_default"
    assert preview["mode"] == "fixture_preview"
    assert ordinary_again["mode"] == "approved_default"
    assert ordinary_again["resident_default_approved"] is True
    # Registry pin unchanged
    registry = _load_registry_via_node()
    approved = registry["routes"]["home"]["renderers"][APPROVED_RENDERER_ID]
    assert approved["resident_default_approved"] is True


def test_debug_fixture_route_not_promoted_to_default():
    sel = _resolve_selection("?home-fixture=1")
    assert sel["mode"] == "fixture_preview"
    assert sel["resident_default_approved"] is False
    assert sel.get("preview_only") is True
    # Ordinary still approved
    assert _resolve_selection("")["mode"] == "approved_default"


def test_unresolved_assets_candidate_not_approved():
    registry = _load_registry_via_node()
    fixture = registry["routes"]["home"]["renderers"][FIXTURE_RENDERER_ID]
    assert fixture["unresolved_asset_count"] == 174
    assert fixture["resident_default_approved"] is False
    assert fixture["visual_review_state"] == "visual_review_pending"
    # Gate must never pick fixture as ordinary default
    sel = _resolve_selection("")
    assert sel["renderer_id"] == APPROVED_RENDERER_ID
    assert sel["mode"] != "fixture_preview"


def test_fixture_integrity_independent_of_selection_gate():
    """Missing registry must not break fixture integrity projection path."""
    html = _render_home(
        "?home-fixture=1", include_registry=False, include_gate=True
    )
    assert "bg-home-fixture-root" in html
    assert 'data-home-fixture-sha256="%s"' % EXPECTED_FIXTURE_SHA in html
    # Canonical fixture JSON still independent
    fixture = json.loads(CANONICAL.read_text(encoding="utf-8"))
    assert fixture["fixture_sha256"] == EXPECTED_FIXTURE_SHA
    assert fixture["clone_status"] == "capture_required"


def test_arbitrary_query_renderer_selection_forbidden():
    for query in (
        "?renderer=bukgu_gwangju.home.fixture.candidate",
        "?renderer-id=" + FIXTURE_RENDERER_ID,
        "?home-renderer=" + FIXTURE_RENDERER_ID,
        "?approval-state=resident_default_approved",
        "?resident-default=true",
    ):
        html = _render_home(query)
        assert "bg-page--home-approval-unavailable" in html, query
        assert "bg-home-fixture-root" not in html, query
        assert "home-mayor-card.png" not in html, query


def test_fixture_preview_with_forbidden_params_stays_preview_not_approved():
    html = _render_home(
        "?home-fixture=1&renderer-id=" + APPROVED_RENDERER_ID
    )
    # Explicit fixture still preview; cannot promote via query.
    assert "bg-home-fixture-root" in html
    assert 'data-resident-default-approved="false"' in html
    assert 'data-preview-only="true"' in html
    assert 'data-visual-review-state="visual_review_pending"' in html


def test_no_hardcoded_bypass_without_registry_in_selection_path():
    html = _render_home("", include_registry=False, include_gate=True)
    assert "home-mayor-card.png" not in html
    assert "bg-page--home-approval-unavailable" in html


# ---------------------------------------------------------------------------
# Build contract (source tree; full build covered in test_build_cloudflare_pages)
# ---------------------------------------------------------------------------


def test_build_source_lists_approval_assets_in_html():
    html = _read(HTML)
    assert "clone-renderer-approval-registry.js" in html
    assert "clone-renderer-approval-gate.js" in html
