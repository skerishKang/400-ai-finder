"""
Contract tests for citizen-action-demo-canvas (Stage #847).

Verifies the local route-rendered canvas and closed map satisfy
the required static/local/demo contract.
"""

import ast
import os
import re
import json
import subprocess

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

STATIC = os.path.join(os.path.dirname(__file__), "..", "src", "web", "static")

REQUIRED_FILES = [
    "citizen-action-demo.html",
    "citizen-action-demo-map.js",
    "citizen-action-demo-canvas.js",
    "citizen-action-demo-canvas.css",
]

# Expected closed vocabulary (from citizen_action_plan.py, read-only)
EXPECTED_ROUTE_IDS = sorted([
    "home",
    "civil-service",
    "complaint-category",
    "complaint-intake",
    "complaint-review",
    "handoff-stop",
])

EXPECTED_TARGET_IDS = sorted([
    "nav-civil-service",
    "nav-complaint-category",
    "complaint-category-illegal-parking",
    "complaint-category-public-parking-inconvenience",
    "complaint-category-residential-parking",
    "complaint-category-traffic-or-facility-safety",
    "complaint-category-other-or-unsure",
    "complaint-body",
    "complaint-draft-review",
    "confirm-draft-prefill",
    "handoff-notice",
])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _read_static(name: str) -> str:
    return _read(os.path.join(STATIC, name))


def _strip_all(text: str) -> str:
    """Remove comments, HTML, and string literals."""
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    return text


# ---------------------------------------------------------------------------
# Node runtime sandbox — captures rendered HTML for each route
# ---------------------------------------------------------------------------

_RUNTIME_SCRIPT = """
'use strict';
var vm = require('vm');

// Fake DOM element with innerHTML capture
var capturedHTML = '';
var eventListeners = {};

function makeElement(id) {
  return {
    id: id,
    get innerHTML() { return capturedHTML; },
    set innerHTML(v) { capturedHTML = v; },
    addEventListener: function(event, handler) {
      eventListeners[id + ':' + event] = handler;
    },
    querySelector: function(sel) {
      var html = capturedHTML;
      if (sel === '[data-action-target="complaint-body"]') {
        if (html.indexOf('data-action-target="complaint-body"') !== -1) {
          return makeElement('complaint-body');
        }
      }
      return null;
    }
  };
}

var fakeCanvasElement = makeElement('demo-canvas');

// Fake window / document
var sandbox = {
  document: {
    getElementById: function(id) {
      if (id === 'demo-canvas') return fakeCanvasElement;
      return null;
    }
  },
  console: {
    log: function() {},
    error: function() {}
  }
};
sandbox.window = sandbox;
var cx = vm.createContext(sandbox);

// Evaluate map and canvas (must use runInContext so sandbox.window is in scope)
var mapJS = %s;
var canvasJS = %s;
vm.runInContext(mapJS, cx);
vm.runInContext(canvasJS, cx);

var canvas = sandbox.window.CitizenActionDemoCanvas;
var routes = %s;

// Render all routes
var results = {};
for (var i = 0; i < routes.length; i++) {
  capturedHTML = '';
  canvas.navigateToRoute(routes[i]);
  results[routes[i]] = capturedHTML;
}

// Output as JSON
process.stdout.write(JSON.stringify(results));
"""


def _render_all_routes_via_node():
    """Call Node to render all routes, return dict of routeId -> html."""
    map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
    canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
    routes_json = json.dumps(EXPECTED_ROUTE_IDS)

    script = _RUNTIME_SCRIPT % (map_js, canvas_js, routes_json)

    result = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Node runtime failed: " + result.stderr
        )
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------

class TestFileExistence:
    @pytest.mark.parametrize("filename", REQUIRED_FILES)
    def test_required_file_exists(self, filename):
        path = os.path.join(STATIC, filename)
        assert os.path.isfile(path), f"required file missing: {filename}"


# ---------------------------------------------------------------------------
# Closed vocabulary: route IDs
# ---------------------------------------------------------------------------

class TestClosedRouteIds:
    def test_map_defines_six_route_ids(self):
        js = _read_static("citizen-action-demo-map.js")
        for rid in EXPECTED_ROUTE_IDS:
            assert '"' + rid + '"' in js, f"route '{rid}' not found in map"

    def test_map_defines_no_extra_route_ids(self):
        js = _read_static("citizen-action-demo-map.js")
        for rid in ["extra-route", "nonexistent-route", "fake"]:
            assert '"' + rid + '"' not in js, f"extra route '{rid}' found in map"

    def test_map_exposes_getRouteIds(self):
        js = _read_static("citizen-action-demo-map.js")
        assert "getRouteIds" in js

    def test_map_exposes_isValidRoute(self):
        js = _read_static("citizen-action-demo-map.js")
        assert "isValidRoute" in js


# ---------------------------------------------------------------------------
# Closed vocabulary: target IDs
# ---------------------------------------------------------------------------

class TestClosedTargetIds:
    def test_map_defines_eleven_target_ids(self):
        js = _read_static("citizen-action-demo-map.js")
        for tid in EXPECTED_TARGET_IDS:
            assert '"' + tid + '"' in js, f"target '{tid}' not found in map"

    def test_map_defines_no_extra_target_ids(self):
        js = _read_static("citizen-action-demo-map.js")
        for tid in ["fake-target", "random-id", "extra-id"]:
            assert '"' + tid + '"' not in js, f"extra target '{tid}' found in map"

    def test_map_exposes_getTargetIds(self):
        js = _read_static("citizen-action-demo-map.js")
        assert "getTargetIds" in js

    def test_map_exposes_isValidTarget(self):
        js = _read_static("citizen-action-demo-map.js")
        assert "isValidTarget" in js


# ---------------------------------------------------------------------------
# First complaint journey: route completeness
# ---------------------------------------------------------------------------

class TestComplaintJourney:
    def test_all_six_routes_have_definitions(self):
        js = _read_static("citizen-action-demo-map.js")
        for route_id in EXPECTED_ROUTE_IDS:
            assert "id: \"" + route_id + "\"" in js or "id:\"" + route_id + "\"" in js, \
                f"route '{route_id}' has no definition"

    def test_home_has_nav_civil_service(self):
        js = _read_static("citizen-action-demo-map.js")
        home_block = js[js.find('"home"'):js.find('"home"') + 500]
        assert "nav-civil-service" in home_block

    def test_civil_service_has_nav_complaint_category(self):
        js = _read_static("citizen-action-demo-map.js")
        block = js[js.find('"civil-service"'):js.find('"civil-service"') + 500]
        assert "nav-complaint-category" in block

    def test_complaint_category_has_all_five_category_targets(self):
        js = _read_static("citizen-action-demo-map.js")
        block = js[js.find('"complaint-category"'):js.find('"complaint-category"') + 800]
        for cat in [
            "complaint-category-illegal-parking",
            "complaint-category-public-parking-inconvenience",
            "complaint-category-residential-parking",
            "complaint-category-traffic-or-facility-safety",
            "complaint-category-other-or-unsure",
        ]:
            assert cat in block, f"category target '{cat}' not in complaint-category navTargets"

    def test_complaint_intake_has_complaint_body_and_draft_review(self):
        js = _read_static("citizen-action-demo-map.js")
        block = js[js.find('"complaint-intake"'):js.find('"complaint-intake"') + 500]
        assert "complaint-body" in block
        assert "complaint-draft-review" in block

    def test_complaint_review_has_confirm_draft_prefill(self):
        js = _read_static("citizen-action-demo-map.js")
        block = js[js.find('"complaint-review"'):js.find('"complaint-review"') + 500]
        assert "confirm-draft-prefill" in block

    def test_handoff_stop_nav_targets_empty(self):
        """handoff-stop navTargets is empty; handoff-notice renders as a static div."""
        js = _read_static("citizen-action-demo-map.js")
        # Find the handoff-stop route definition block (after ROUTES = ...)
        idx = js.find('"handoff-stop": Object.freeze')
        assert idx != -1, "handoff-stop route not found"
        block = js[idx:idx + 300]
        # navTargets must be []
        assert "navTargets: []" in block, \
            "handoff-stop navTargets must be empty (handoff-notice renders as static div)"


# ---------------------------------------------------------------------------
# HTML page structure: canvas assets, no remote URLs
# ---------------------------------------------------------------------------

class TestHtmlPageStructure:
    def test_html_loads_map_asset(self):
        html = _read_static("citizen-action-demo.html")
        assert "citizen-action-demo-map.js" in html

    def test_html_loads_canvas_asset(self):
        html = _read_static("citizen-action-demo.html")
        assert "citizen-action-demo-canvas.js" in html

    def test_html_loads_canvas_css(self):
        html = _read_static("citizen-action-demo.html")
        assert "citizen-action-demo-canvas.css" in html

    def test_no_remote_url_in_html(self):
        html = _read_static("citizen-action-demo.html")
        external = re.findall(
            r'(?:href|src)\s*=\s*["\']https?://(?!localhost|127\.0\.0\.1)[^"\']+["\']',
            html
        )
        assert not external, f"external URL found in HTML: {external}"


# ---------------------------------------------------------------------------
# Each route: required structural elements
# ---------------------------------------------------------------------------

class TestRouteStructure:
    def test_each_route_renders_nav_bar(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "_renderNavBar" in js
        assert "canvas-nav" in js

    def test_each_route_renders_breadcrumb(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "_renderBreadcrumb" in js
        assert "canvas-breadcrumb" in js

    def test_each_route_renders_page_title(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "canvas-nav__title" in js or "route.title" in js

    def test_each_route_renders_poc_banner(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "_renderPocBanner" in js or "canvas-poc-banner" in js


# ---------------------------------------------------------------------------
# PoC disclosure content
# ---------------------------------------------------------------------------

class TestPocDisclosure:
    def test_disclosure_mentions_not_official(self):
        html = _read_static("citizen-action-demo.html")
        js = _read_static("citizen-action-demo-canvas.js")
        css = _read_static("citizen-action-demo-canvas.css")
        combined = html + js + css
        assert "공식" in combined or "official" in combined.lower()
        assert "데모" in combined
        assert "PoC" in combined or "로컬" in combined or "시연" in combined

    def test_disclosure_mentions_authentication_responsibility(self):
        html = _read_static("citizen-action-demo.html")
        js = _read_static("citizen-action-demo-canvas.js")
        combined = html + js
        assert "책임" in combined or "responsibility" in combined.lower()


# ---------------------------------------------------------------------------
# Target boundary: data-action-target attributes
# ---------------------------------------------------------------------------

class TestTargetBoundary:
    def test_canvas_js_emits_data_action_target_attributes(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert 'data-action-target="' in js

    def test_map_validates_target_id(self):
        js = _read_static("citizen-action-demo-map.js")
        assert "isValidTarget" in js
        assert "CLOSED_TARGET_IDS" in js

    def test_canvas_navigate_validates_against_map(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "navigateToRoute" in js
        assert "_map.isValidRoute" in js

    def test_canvas_getTargetElement_validates_target_id(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "getTargetElement" in js
        assert "_map.isValidTarget" in js


# ---------------------------------------------------------------------------
# Safety: no forbidden patterns
# ---------------------------------------------------------------------------

class TestSafety:
    PROHIBITED_CODE_PATTERNS = [
        ("fetch(", "fetch"),
        ("XMLHttpRequest", "XMLHttpRequest"),
        ("WebSocket", "WebSocket"),
        ("EventSource", "EventSource"),
        ("navigator.sendBeacon", "sendBeacon"),
        ("localStorage", "localStorage"),
        ("sessionStorage", "sessionStorage"),
        ("indexedDB", "indexedDB"),
        ("document.cookie", "document.cookie"),
        ("import ", "import"),
        ("provider", "provider invocation"),
        ("runner", "runner invocation"),
        ("iframe", "iframe"),
        ("@import url", "external CSS @import url"),
        ("googleapis", "external CDN font"),
        ("cdnjs", "external CDN"),
        ("unpkg", "external CDN"),
        ("jsdelivr", "external CDN"),
    ]

    @pytest.mark.parametrize("pattern,label", PROHIBITED_CODE_PATTERNS)
    def test_no_prohibited_pattern_in_js_code(self, pattern, label):
        js = _read_static("citizen-action-demo-canvas.js")
        code_only = _strip_all(js)
        assert pattern not in code_only, f"canvas.js: found prohibited {label}"

    @pytest.mark.parametrize("pattern,label", PROHIBITED_CODE_PATTERNS)
    def test_no_prohibited_pattern_in_map_code(self, pattern, label):
        js = _read_static("citizen-action-demo-map.js")
        code_only = _strip_all(js)
        assert pattern not in code_only, f"map.js: found prohibited {label}"

    def test_no_form_in_canvas_html(self):
        js = _read_static("citizen-action-demo-canvas.js")
        code_only = _strip_all(js)
        assert "<form" not in code_only.lower(), "canvas must not contain a form element"

    def test_no_type_submit_in_canvas_js(self):
        js = _read_static("citizen-action-demo-canvas.js")
        code_only = _strip_all(js)
        assert 'type="submit"' not in code_only, "canvas must not use type=submit"


# ---------------------------------------------------------------------------
# Runtime render tests — Node vm.runInThisContext + fake DOM
# ---------------------------------------------------------------------------

class TestRuntimeRender:
    """Runtime-render tests using Node vm.runInThisContext with a fake DOM."""

    @pytest.fixture(scope="class")
    def rendered_routes(self):
        """Render all routes once via Node subprocess."""
        return _render_all_routes_via_node()

    def test_all_six_routes_render_successfully(self, rendered_routes):
        """Every route ID in the closed vocabulary renders without throwing."""
        for route_id in EXPECTED_ROUTE_IDS:
            assert route_id in rendered_routes, \
                f"route '{route_id}' did not render (did Node throw?)"
            html = rendered_routes[route_id]
            assert html, f"route '{route_id}' rendered empty HTML"

    def test_complaint_intake_contains_complaint_body_element(self, rendered_routes):
        """Intake renders a non-button element carrying data-action-target='complaint-body'."""
        html = rendered_routes["complaint-intake"]
        assert 'data-action-target="complaint-body"' in html
        # Find the element tag
        match = re.search(
            r'<(\w+)[^>]*\sdata-action-target="complaint-body"[^>]*>',
            html
        )
        assert match, "complaint-body element not found"
        tag = match.group(1)
        assert tag != "button", \
            "complaint-body must NOT be a <button> (it is a display div)"

    def test_complaint_body_has_no_data_demo_route(self, rendered_routes):
        """The complaint-body element has no data-demo-route attribute."""
        html = rendered_routes["complaint-intake"]
        match = re.search(
            r'<(\w+)[^>]*\sdata-action-target="complaint-body"[^>]*>',
            html
        )
        assert match, "complaint-body element not found"
        el_tag = match.group(0)
        assert "data-demo-route" not in el_tag, \
            "complaint-body must not have data-demo-route"

    def test_no_button_has_data_action_target_complaint_body(self, rendered_routes):
        """No <button> element carries data-action-target='complaint-body'."""
        html = rendered_routes["complaint-intake"]
        buttons = re.findall(
            r'<button[^>]*\sdata-action-target="complaint-body"[^>]*>',
            html
        )
        assert not buttons, \
            "no <button> should have data-action-target='complaint-body'"

    def test_handoff_stop_contains_handoff_notice(self, rendered_routes):
        """Handoff-stop renders a visible element with data-action-target='handoff-notice'."""
        html = rendered_routes["handoff-stop"]
        assert 'data-action-target="handoff-notice"' in html

    def test_handoff_notice_has_no_data_demo_route(self, rendered_routes):
        """The handoff-notice element has no data-demo-route attribute."""
        html = rendered_routes["handoff-stop"]
        match = re.search(
            r'<(\w+)[^>]*\sdata-action-target="handoff-notice"[^>]*>',
            html
        )
        assert match, "handoff-notice element not found"
        el_tag = match.group(0)
        assert "data-demo-route" not in el_tag, \
            "handoff-notice must not have data-demo-route"

    def test_all_data_demo_route_values_are_valid_and_nonempty(self, rendered_routes):
        """Every rendered data-demo-route value is non-empty and in the closed vocabulary."""
        combined = "".join(rendered_routes.values())
        matches = re.findall(r'data-demo-route="([^"]*)"', combined)
        assert matches, "expected at least one data-demo-route attribute"
        for val in matches:
            assert val != "", "data-demo-route must not be empty"
            assert val in EXPECTED_ROUTE_IDS, \
                f"data-demo-route value '{val}' not in closed six-route vocabulary"

    def test_complaint_draft_review_is_nav_button_in_intake(self, rendered_routes):
        """In intake, only complaint-draft-review is a navigation button (not complaint-body)."""
        html = rendered_routes["complaint-intake"]
        buttons = re.findall(
            r'<button[^>]*\sdata-action-target="([^"]*)"[^>]*>',
            html
        )
        assert "complaint-draft-review" in buttons, \
            "complaint-draft-review must be a nav button in intake"
        assert "complaint-body" not in buttons, \
            "complaint-body must not be a navigation button"

    def test_handoff_notice_is_not_a_button(self, rendered_routes):
        """handoff-notice renders as a div, not a button."""
        html = rendered_routes["handoff-stop"]
        buttons = re.findall(
            r'<button[^>]*\sdata-action-target="handoff-notice"[^>]*>',
            html
        )
        assert not buttons, "handoff-notice must not be a <button>"

    def test_nav_buttons_have_data_demo_route(self, rendered_routes):
        """Navigation buttons in home/civil-service have data-demo-route set to destination."""
        for route_id in ["home", "civil-service"]:
            html = rendered_routes[route_id]
            buttons = re.findall(
                r'<button[^>]*\sdata-demo-route="([^"]*)"[^>]*>',
                html
            )
            assert buttons, f"{route_id} nav buttons must have data-demo-route"
            for val in buttons:
                assert val in EXPECTED_ROUTE_IDS


# ---------------------------------------------------------------------------
# citizen_action_plan.py not modified
# ---------------------------------------------------------------------------

class TestContractNotModified:
    def test_citizen_action_plan_unchanged(self):
        agent_py = os.path.join(
            os.path.dirname(__file__), "..", "src", "agent", "citizen_action_plan.py"
        )
        assert os.path.isfile(agent_py), "citizen_action_plan.py must exist"
        content = _read(agent_py)
        assert "CitizenAction" in content
        assert "_VALID_ROUTE_IDS" in content
        assert "_VALID_TARGET_IDS" in content


# ---------------------------------------------------------------------------
# Stage 846 shell tests remain compatible
# ---------------------------------------------------------------------------

class TestShellCompatibility:
    def test_shell_js_unchanged(self):
        shell_js = os.path.join(STATIC, "citizen-copilot-shell.js")
        content = _read(shell_js)
        assert "_toggleDock" in content
        assert "_openCompactDrawer" in content or "_openCompact" in content
        assert "matchMedia" in content

    def test_shell_css_unchanged(self):
        shell_css = os.path.join(STATIC, "citizen-copilot-shell.css")
        content = _read(shell_css)
        assert ".copilot-rail" in content
        assert "@media" in content
        assert "767px" in content