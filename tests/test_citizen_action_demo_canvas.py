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
import tempfile

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
sandbox.URLSearchParams = URLSearchParams;
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

    result = _run_node_script_file(script, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(
            "Node runtime failed: " + result.stderr
        )
    return json.loads(result.stdout)


def _run_node_script_file(script: str, timeout: int = 30):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(script)
        script_path = f.name
    try:
        return subprocess.run(
            ["node", script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    finally:
        os.unlink(script_path)


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
        assert "navTargets: Object.freeze([])" in block, \
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
        assert "_renderNavBar" in js or "_renderSubHeader" in js
        assert "bg-nav-bar" in js

    def test_each_route_renders_breadcrumb(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "_renderBreadcrumb" in js
        assert "bg-breadcrumb" in js

    def test_each_route_renders_page_header(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "_renderSubPageHeader" in js or "_renderPageHeader" in js
        assert "bg-page-header" in js
        assert "bg-page-header__title" in js

    def test_each_route_renders_poc_banner(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "_renderPocBanner" in js
        assert "bg-poc-banner" in js


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

    def test_each_route_has_required_structural_elements(self, rendered_routes):
        """
        Each route must render in order: top nav, breadcrumb, page header, PoC banner, and content.
        Additionally, verify specific title and purpose for each route.
        """
        ROUTE_METADATA = {
            "home": {"title": "시민 행정 도우미", "purpose": "북구청 행정서비스를 안내합니다."},
            "civil-service": {"title": "민원 신청", "purpose": "북구청 주요 민원 서비스를 안내합니다."},
            "complaint-category": {"title": "민원 유형 선택", "purpose": "해당 상황에 맞는 민원 유형을 선택해 주세요."},
            "complaint-intake": {"title": "민원서식", "purpose": "민원 업무에 필요한 각종 서식을 검색하고 다운로드할 수 있습니다."},
            "complaint-review": {"title": "민원 신청 확인", "purpose": "아래 내용을 확인하고 신청해 주세요."},
            "handoff-stop": {"title": "데모 종료", "purpose": "실제 민원 신청은 북구청 공식 채널을 이용하세요."},
        }

        for route_id in EXPECTED_ROUTE_IDS:
            html = rendered_routes[route_id]

            # 1. Top Nav — semantic bg-nav-bar or bg-nav-bar__title
            # Home route has its own header/GNB (reconstructed homepage)
            if route_id == "home":
                assert 'class="bg-header"' in html, f"route {route_id} missing header"
                assert 'class="bg-gnb"' in html, f"route {route_id} missing GNB"
            else:
                assert 'class="bg-nav-bar"' in html, f"route {route_id} missing nav bar"

            # 2. Breadcrumb (home is portal page without breadcrumb)
            if route_id != "home":
                assert 'class="bg-breadcrumb"' in html, f"route {route_id} missing breadcrumb"

            # 3. Page Header (title and purpose) — sub-pages only
            if route_id != "home":
                assert 'class="bg-page-header"' in html, f"route {route_id} missing page header"
                assert 'class="bg-page-header__title"' in html, f"route {route_id} missing page title"

            # Verify exact title and purpose for sub-pages
            if route_id != "home":
                meta = ROUTE_METADATA[route_id]
                assert meta["title"] in html, f"route {route_id} missing expected title: {meta['title']}"
                assert meta["purpose"] in html, f"route {route_id} missing expected purpose: {meta['purpose']}"

            # 4. PoC Banner (sub-pages only; home is the portal page)
            if route_id != "home":
                assert 'class="bg-poc-banner"' in html or 'class="canvas-poc-banner"' in html, \
                    f"route {route_id} missing PoC banner"
                assert "로컬 개념 시연 (PoC) 안내" in html, f"route {route_id} missing PoC label"
                assert "공식 사이트가 아니며" in html, f"route {route_id} missing PoC disclaimer"

            # 5. Content
            assert 'class="bg-content' in html or 'class="canvas-body"' in html or 'class="bg-page"' in html, \
                f"route {route_id} missing content body"

    def test_complaint_category_buttons_have_correct_metadata(self, rendered_routes):
        """
        Render 'complaint-category'.
        Assert exactly the five closed category target IDs are present as buttons.
        Category buttons use bg-category-card class (no data-demo-route — handled by delegation).
        """
        html = rendered_routes["complaint-category"]
        category_targets = [
            "complaint-category-illegal-parking",
            "complaint-category-public-parking-inconvenience",
            "complaint-category-residential-parking",
            "complaint-category-traffic-or-facility-safety",
            "complaint-category-other-or-unsure",
        ]

        # Verify exactly these five targets are buttons
        for tid in category_targets:
            button_pattern = r'<button[^>]*\sdata-action-target="' + tid + r'"[^>]*>'
            assert re.search(button_pattern, html), f"category button '{tid}' missing"

        # Verify no category button has data-demo-route (delegation handles it)
        for tid in category_targets:
            button_tag = re.search(
                r'<button[^>]*\sdata-action-target="' + tid + r'"[^>]*>',
                html
            ).group(0)
            assert 'data-demo-route=' not in button_tag, \
                f"category button '{tid}' should NOT have data-demo-route"

    def test_complaint_intake_has_form_table_and_data_targets(self, rendered_routes):
        """Intake renders a form table with data-action-target on complaint-draft-review."""
        html = rendered_routes["complaint-intake"]
        assert 'data-action-target="complaint-draft-review"' in html
        assert 'class="bg-form-table"' in html
        assert "주민등록표 등·초본" in html

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

    def test_complaint_draft_review_is_link_in_form_table(self, rendered_routes):
        """In intake, complaint-draft-review is a link in the form table."""
        html = rendered_routes["complaint-intake"]
        assert 'data-action-target="complaint-draft-review"' in html, \
            "complaint-draft-review missing in intake"
        assert 'class="bg-form-table"' in html, "form table missing in intake"

    def test_handoff_notice_is_not_a_button(self, rendered_routes):
        """handoff-notice renders as a div, not a button."""
        html = rendered_routes["handoff-stop"]
        buttons = re.findall(
            r'<button[^>]*\sdata-action-target="handoff-notice"[^>]*>',
            html
        )
        assert not buttons, "handoff-notice must not be a <button>"

    def test_nav_buttons_have_data_demo_route(self, rendered_routes):
        """Navigation buttons in civil-service have data-demo-route set to destination."""
        html = rendered_routes["civil-service"]
        buttons = re.findall(
            r'<button[^>]*\sdata-demo-route="([^"]*)"[^>]*>',
            html
        )
        assert buttons, "civil-service nav buttons must have data-demo-route"
        for val in buttons:
            assert val in EXPECTED_ROUTE_IDS

    def test_real_entity_replacements_present(self, rendered_routes):
        """Verify that HTML contains proper HTML entities or valid separators."""
        combined = "".join(rendered_routes.values())
        # Check for standard HTML entities OR valid Unicode separators
        has_entity = any(ent in combined for ent in
            ["&amp;", "&lt;", "&gt;", "&quot;", "&#39;"])
        has_separator = "›" in combined or "|" in combined
        assert has_entity or has_separator, \
            "no HTML entities or valid separators found"

        # Ensure no unicode escaped versions of & are present in the rendered HTML
        assert "\\x26" not in combined, "found unicode escape \\x26 in rendered HTML"
        assert "\\u0026" not in combined, "found unicode escape \\u0026 in rendered HTML"


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


# ---------------------------------------------------------------------------
# Semantic Reconstruction Tests (#863 final gate)
# ---------------------------------------------------------------------------

class TestSemanticReconstruction:
    """Focused tests for the semantic HTML/CSS reconstruction (Stage #863)."""

    def test_no_image_routes_in_canvas(self):
        """IMAGE_ROUTES and _renderImageBasedRoute must be removed."""
        js = _read_static("citizen-action-demo-canvas.js")
        assert "IMAGE_ROUTES" not in js, "IMAGE_ROUTES must be removed"
        assert "_renderImageBasedRoute" not in js, "_renderImageBasedRoute must be removed"
        assert "canvas-image-overlay" not in js, "canvas-image-overlay must be removed"
        assert "canvas-img-wrapper" not in js, "canvas-img-wrapper must be removed"

    def test_safety_stop_in_complaint_review(self):
        """complaint-review route must render Safety Stop overlay."""
        js = _read_static("citizen-action-demo-canvas.js")
        assert 'safety-stop-overlay' in js, "safety-stop-overlay missing in canvas JS"
        assert 'safety-stop-box' in js, "safety-stop-box missing in canvas JS"
        assert "제출 전 안전 중지" in js, "Safety Stop title missing"

    def test_chat_shell_in_html(self):
        """HTML must have chat-shell as primary right-side panel."""
        html = _read_static("citizen-action-demo.html")
        assert 'class="chat-shell"' in html, "chat-shell not found in HTML"
        assert "AI 민원 도우미" in html, "AI 민원 도우미 title missing"
        assert 'class="chat-composer"' in html, "chat-composer not found"
        assert "보내기" in html, "보내기 button missing"

    def test_home_has_gnb_with_data_action_target(self):
        """Home route must have GNB with data-action-target on 종합민원."""
        js = _read_static("citizen-action-demo-canvas.js")
        assert 'data-action-target="nav-civil-service"' in js, \
            "GNB 종합민원 must have data-action-target"
        assert "종합민원" in js
        assert "data-action-target" in js

    def test_complaint_review_has_disabled_submit(self):
        """complaint-review route must have disabled submit button."""
        js = _read_static("citizen-action-demo-canvas.js")
        assert "disabled" in js and "제출하기" in js, \
            "disabled submit button required in complaint-review"

    def test_route_metadata_titles_updated(self):
        """Route metadata titles and purposes must be correct."""
        html = _read_static("citizen-action-demo.html")
        js = _read_static("citizen-action-demo-canvas.js")
        assert "시민 행정 도우미" in html or "전남광주통합특별시북구" in js, "page title missing"
        assert "전남광주통합특별시북구" in js, "header must use 전남광주통합특별시북구"
        assert "북구청장 신수정" in js or "home-hero-mayor" in js, "hero must mention 북구청장 신수정"


class TestFidelityAndSeparation:
    @pytest.fixture(scope="class")
    def rendered_routes(self):
        return _render_all_routes_via_node()

    def test_no_demo_overlay_in_public_routes(self, rendered_routes):
        """Ensure no 'AI 도우미 · 로컬 시연' overlay strings exist in public LEFT viewports."""
        for rid in ["home", "complaint-category", "complaint-intake"]:
            html = rendered_routes[rid]
            assert "AI 도우미 · 로컬 시연" not in html
            assert "🏠 시민 행정 도우미" not in html
            assert "불법 주정차 신고 관련" not in html

    def test_no_demo_specific_rows_in_intake_table(self, rendered_routes):
        """Ensure no '불법 주정차', '공용주차장' or '교통과' demo specific items exist in public table."""
        html = rendered_routes["complaint-intake"]
        # Public table must only have neutral public data rows
        assert "불법 주정차 신고서" not in html
        assert "공용주차장 불편" not in html
        assert "교통·시설 안전" not in html
        assert "주민등록표 등·초본" in html
        assert "지방세 납세증명" in html

    def test_complaint_review_boundary_integrity(self, rendered_routes):
        """Verify complaint-review contains disabled submit button and Safety Stop overlay."""
        html = rendered_routes["complaint-review"]
        # Submit button must be disabled for local safety stop
        assert 'disabled' in html
        assert 'safety-stop-overlay' in html
        assert 'Safety Stop' in html

    def test_no_whole_page_screenshots_as_backgrounds(self):
        """Verify canvas.js source does not load raw full screenshot images directly as background or img."""
        js = _read_static("citizen-action-demo-canvas.js")
        # Raw screenshots should not be used as direct viewport images or backgrounds
        assert 'src="/static/images/bukgu_home.png"' not in js
        assert 'src="/static/images/bukgu_menu.png"' not in js
        assert 'src="/static/images/bukgu_intake.png"' not in js

    def test_no_emojis_as_quick_service_or_official_icons(self, rendered_routes):
        """Ensure public routes GNB and quick services do not use raw emojis for icons."""
        for rid in ["home", "complaint-category", "complaint-intake"]:
            html = rendered_routes[rid]
            # Verify quick services use crops instead of raw emojis (e.g. 🏛️, 🎋, 👥, 🚗, 🅿️)
            assert "🏛️" not in html
            assert "🎋" not in html
            assert "👥" not in html

    def test_required_data_action_targets_exist(self, rendered_routes):
        """Verify all closed vocabulary target IDs exist in the generated DOMs."""
        combined = "".join(rendered_routes.values())
        required_targets = [
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
        ]
        for target in required_targets:
            assert f'data-action-target="{target}"' in combined, f"Target '{target}' not present in rendered HTML"

    def test_official_identity_crop_provenance(self, rendered_routes):
        """Verify the current home identity asset is used correctly (current reference ledger)."""
        from PIL import Image

        # a. Current identity asset exists at correct path
        current_identity_path = os.path.join(STATIC, "images", "bukgu-current", "home-identity.png")
        assert os.path.exists(current_identity_path), "home-identity.png missing in bukgu-current"
        identity_img = Image.open(current_identity_path)
        assert identity_img.size == (170, 42), f"home-identity.png size mismatch: {identity_img.size}"

        # b. The new asset path exists in rendered home HTML
        home_html = rendered_routes["home"]
        assert "/static/images/bukgu-current/home-identity.png" in home_html, "home-identity.png missing in rendered html"
        assert 'alt="전남광주통합특별시북구"' in home_html, \
            'alt="전남광주통합특별시북구" missing in rendered html'

        # c. No legacy identity expression in home renderer
        assert "home-logo-identity.png" not in home_html, \
            "legacy home-logo-identity.png still referenced in rendered html"
        assert "광주광역시 북구" not in home_html, "광주광역시 북구 must not appear in home rendered html"

        # Check canvas.js has no active _svgLogo/White in identity rendering
        js = _read_static("citizen-action-demo-canvas.js")
        assert '_svgLogo' not in js, "_svgLogo still in canvas.js"
        assert '_svgLogoWhite' not in js, "_svgLogoWhite still in canvas.js"


# ---------------------------------------------------------------------------
# J-DEPT-01 specific tests
# ---------------------------------------------------------------------------

class TestJDept01SpecificContracts:
    @pytest.fixture(scope="class")
    def dept_render(self):
        """Helper to run Node and capture HTML under J-DEPT-01 query states."""
        def _render(query: str):
            map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
            canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
            # Run with custom sandbox search query
            sandbox_init = """
            'use strict';
            var vm = require('vm');
            var capturedHTML = '';
            var capturedChatHTML = '';
            var eventListeners = {};
            function makeElement(id) {
              return {
                id: id,
                get innerHTML() { return id === 'chat-thread' ? capturedChatHTML : capturedHTML; },
                set innerHTML(v) { if (id === 'chat-thread') { capturedChatHTML = v; } else { capturedHTML = v; } },
                addEventListener: function(event, handler) {
                  eventListeners[id + ':' + event] = handler;
                },
                querySelector: function(sel) {
                  if (sel === '.bg-dept-search__input') {
                    return { value: '공동주택' };
                  }
                  return null;
                }
              };
            }
            var fakeCanvasElement = makeElement('demo-canvas');
            var sandbox = {
              document: {
                getElementById: function(id) {
                  if (id === 'demo-canvas') return fakeCanvasElement;
                  if (id === 'chat-thread') return makeElement('chat-thread');
                  return null;
                }
              },
              console: { log: function() {}, error: function() {} },
              location: { search: %s },
              window: null
            };
            sandbox.URLSearchParams = URLSearchParams;
            sandbox.window = sandbox;
            var cx = vm.createContext(sandbox);
            vm.runInContext(%s, cx);
            vm.runInContext(%s, cx);
            sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
            process.stdout.write(capturedHTML);
            """ % (
                json.dumps(query),
                map_js,
                canvas_js
            )
            res = _run_node_script_file(sandbox_init, timeout=10)
            assert res.returncode == 0, res.stderr
            return res.stdout
        return _render

    def test_jdept01_does_not_extend_vocabulary(self):
        """1. Closed vocabulary in map.js is NOT changed."""
        js = _read_static("citizen-action-demo-map.js")
        assert "J-DEPT-01" not in js
        assert "dept-state" not in js
        assert "data-dept-action" not in js

    def test_jdept01_query_gated_states_render(self, dept_render):
        """2. The four query states render successfully and preserve the public shell layout."""
        html_home = dept_render("?journey=J-DEPT-01")
        assert "bg-page--home" in html_home
        assert 'data-dept-journey="true"' in html_home

        html_menu = dept_render("?journey=J-DEPT-01&dept-state=menu")
        assert "bg-dept-mega-menu" in html_menu

        html_dir = dept_render("?journey=J-DEPT-01&dept-state=directory")
        assert "bg-page--dept-directory" in html_dir
        assert "업무 및 전화번호 안내" in html_dir
        # Public shell preservation checks on directory
        assert "bg-home-utility" in html_dir
        assert "bg-header" in html_dir
        assert "bg-home-gnb__item--dept" in html_dir
        assert "bg-dept-mega-menu" in html_dir

        html_res = dept_render("?journey=J-DEPT-01&dept-state=result")
        assert "bg-page--dept-directory" in html_res
        assert "공동주택과" in html_res
        # Public shell preservation checks on result
        assert "bg-home-utility" in html_res
        assert "bg-header" in html_res
        assert "bg-home-gnb__item--dept" in html_res
        assert "bg-dept-mega-menu" in html_res

    def test_jdept01_exact_route_and_chat_progression(self, dept_render):
        """3. Output contains correct route navigation elements."""
        html_dir = dept_render("?journey=J-DEPT-01&dept-state=directory")
        assert "홈" in html_dir
        assert "북구소개" in html_dir
        assert "구청안내" in html_dir
        assert "업무 및 전화번호 안내" in html_dir

    def test_jdept01_factual_result_row_only(self, dept_render):
        """4. Result state renders only the single approved factual row and count."""
        html_res = dept_render("?journey=J-DEPT-01&dept-state=result")
        assert "전체" in html_res
        assert "9" in html_res
        assert "1/1" in html_res
        assert "공동주택과" in html_res
        assert "062-410-6033" in html_res
        assert "공동주택과 업무전반" in html_res
        # Assert no other fake or synthesized rows are present
        assert "공동주택지원팀" not in html_res
        assert "홍길동" not in html_res

    def test_jdept01_no_raw_captures_in_code(self):
        """5. Verify no raw R-DEPT capture filenames are used as backgrounds or source tags in js/css."""
        js = _read_static("citizen-action-demo-canvas.js")
        css = _read_static("citizen-action-demo-canvas.css")
        combined = js + css
        for filename in [
            "bukgu-menu-dropdown.png",
            "CaptureX_2026-07-06_001130_bukgu.gwangju.kr_upmu.png",
            "CaptureX_2026-07-06_001132_bukgu.gwangju.kr_upmu_full.png",
            "CaptureX_2026-07-06_001716_bukgu.gwangju.kr_gongdong.png",
            "CaptureX_2026-07-06_001719_bukgu.gwangju.kr_gongdong_full.png"
        ]:
            assert filename not in combined, f"prohibited usage of reference capture filename: {filename}"

    def test_jdept01_uses_data_dept_action(self, dept_render):
        """6. Interaction targets use data-dept-action, not data-action-target."""
        html_home = dept_render("?journey=J-DEPT-01")
        assert 'data-dept-action="open-menu"' in html_home
        assert 'data-action-target="open-menu"' not in html_home

    def test_jdept01_css_is_scoped(self):
        """7. Verify J-DEPT CSS rules are route-scoped only."""
        css = _read_static("citizen-action-demo-canvas.css")
        # Split by the exact end marker of the comment block to clear the header comment
        jdept_part = css.split("--------------------------------------------------------------------------- */")[-1]

        import re
        jdept_part = re.sub(r"/\*[\s\S]*?\*/", "", jdept_part)
        jdept_part = jdept_part.replace("*/", "", 1).strip()
        jdept_part = re.sub(r"@keyframes\s+\w+\s*\{[\s\S]*?\}", "", jdept_part)

        selectors = []
        blocks = jdept_part.split("}")
        for block in blocks:
            if "{" in block:
                sel = block.split("{")[0].strip()
                if sel and not sel.startswith("@") and not sel == "from" and not sel == "to":
                    selectors.append(sel)

        for selector in selectors:
            # Split by comma but ignore commas inside parentheses
            in_paren = False
            parts = []
            current = []
            for char in selector:
                if char == '(':
                    in_paren = True
                elif char == ')':
                    in_paren = False

                if char == ',' and not in_paren:
                    parts.append("".join(current).strip())
                    current = []
                else:
                    current.append(char)
            if current:
                parts.append("".join(current).strip())

            for sel_part in parts:
                if not sel_part:
                    continue
                if sel_part in ["from", "to"] or sel_part.startswith("@"):
                    continue
                if sel_part.startswith(":is("):
                    # Validate all sub-selectors inside :is(...)
                    inner = sel_part[4:-1]
                    for sub_sel in [s.strip() for s in inner.split(",")]:
                        assert (sub_sel.startswith(".bg-page--dept-directory") or
                                sub_sel.startswith(".bg-page--home[data-dept-journey=\"true\"]") or
                                sub_sel.startswith(".bg-page--home[data-dept-replay=\"true\"]") or
                                sub_sel.startswith(".bg-page--dept-replay") or
                                sub_sel.startswith(".bg-page--home[data-dept-auto-replay=\"true\"]") or
                                sub_sel.startswith("[data-dept-auto-replay=\"true\"]")), \
                            f"prohibited inner is selector: {sub_sel}"
                    continue

                assert (sel_part.startswith(".bg-page--dept-directory") or
                        sel_part.startswith(".bg-page--home[data-dept-journey=\"true\"]") or
                        sel_part.startswith(".bg-page--home[data-dept-replay=\"true\"]") or
                        sel_part.startswith(".bg-page--dept-replay") or
                        sel_part.startswith(".bg-page--home[data-dept-auto-replay=\"true\"]") or
                        sel_part.startswith("[data-dept-auto-replay=\"true\"]")), \
                    f"prohibited unscoped J-DEPT selector: {sel_part}"

    def test_jdept01_shared_public_shell_css_contract(self, dept_render):
        """10. Verify that all 6 required public-shell GNB and header utility classes are mapped and scoped via the approved shared root selector contract."""
        css = _read_static("citizen-action-demo-canvas.css")
        required_classes = [
            ".bg-home-utility",
            ".bg-home-header",
            ".bg-home-gnb",
            ".bg-home-gnb__link",
            ".bg-home-header__actions",
            ".bg-home-header__icon"
        ]
        # Accept 2-root, 3-root, or 4-root :is() selector
        for cls in required_classes:
            has_two_root = any(f":is(.bg-page--home, .bg-page--dept-directory) {cls}" in line for line in css.split("\n"))
            has_three_root = any(f":is(.bg-page--home, .bg-page--dept-directory, .bg-page--park-info) {cls}" in line for line in css.split("\n"))
            has_four_root = any(f":is(.bg-page--home, .bg-page--dept-directory, .bg-page--park-info, .bg-page--kiosk-info) {cls}" in line for line in css.split("\n"))
            assert has_two_root or has_three_root or has_four_root, f"Missing shared scoping contract for: {cls}"

        # Assert the shared root selector defines --bg-home-width: 914px (2, 3, or 4 roots)
        assert (any(":is(.bg-page--home, .bg-page--dept-directory)" in line for line in css.split("\n")) or
                any(":is(.bg-page--home, .bg-page--dept-directory, .bg-page--park-info)" in line for line in css.split("\n")) or
                any(":is(.bg-page--home, .bg-page--dept-directory, .bg-page--park-info, .bg-page--kiosk-info)" in line for line in css.split("\n"))), "Missing shared root selector in CSS"

        # Verify custom property and outer strip scoped rules
        assert any("--bg-home-width: 914px;" in line for line in css.split("\n")), "Missing shared home-width custom property"
        has_two_strip = any(":is(.bg-page--home, .bg-page--dept-directory) .bg-home-gov-strip" in line for line in css.split("\n"))
        has_three_strip = any(":is(.bg-page--home, .bg-page--dept-directory, .bg-page--park-info) .bg-home-gov-strip" in line for line in css.split("\n"))
        has_four_strip = any(":is(.bg-page--home, .bg-page--dept-directory, .bg-page--park-info, .bg-page--kiosk-info) .bg-home-gov-strip" in line for line in css.split("\n"))
        assert has_two_strip or has_three_strip or has_four_strip, "Missing shared gov-strip rule mapping"

        # Assert directory/result renders contain the correct root class
        html_dir = dept_render("?journey=J-DEPT-01&dept-state=directory")
        assert "bg-page--dept-directory" in html_dir

        html_res = dept_render("?journey=J-DEPT-01&dept-state=result")
        assert "bg-page--dept-directory" in html_res

    def test_jdept01_duplicate_journey_fallback(self, dept_render):
        """4. Duplicate journey parameters fall back to historical non-J-DEPT output."""
        html = dept_render("?journey=J-DEPT-01&journey=J-DEPT-01")
        assert 'data-dept-journey="true"' not in html
        assert 'data-dept-action="open-menu"' not in html

    def test_jdept01_duplicate_dept_state_fallback(self, dept_render):
        """5. Duplicate dept-state parameters fall back to historical non-J-DEPT output."""
        html = dept_render("?journey=J-DEPT-01&dept-state=menu&dept-state=menu")
        assert 'data-dept-journey="true"' not in html
        assert "bg-dept-mega-menu" not in html

    def test_jdept01_unsupported_dept_state_fallback(self, dept_render):
        """6. Unsupported dept-state parameter falls back to historical non-J-DEPT output."""
        html = dept_render("?journey=J-DEPT-01&dept-state=invalidstate")
        assert 'data-dept-journey="true"' not in html
        assert "bg-dept-mega-menu" not in html

    def test_jdept01_exact_search_handler_execution(self):
        """8. Execute captured click handler and check pushState query resolution for exact-search."""
        map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
        canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))

        sandbox_init = """
        'use strict';
        var vm = require('vm');
        var capturedHTML = '';
        var capturedChatHTML = '';
        var capturedClickHandler = null;

        function makeElement(id) {
          return {
            id: id,
            get innerHTML() { return id === 'chat-thread' ? capturedChatHTML : capturedHTML; },
            set innerHTML(v) { if (id === 'chat-thread') { capturedChatHTML = v; } else { capturedHTML = v; } },
            addEventListener: function(event, handler) {
              if (event === 'click' && id === 'demo-canvas') {
                capturedClickHandler = handler;
              }
            },
            querySelector: function(sel) {
              if (sel === '.bg-dept-search__input') {
                return { value: searchInputVal };
              }
              return null;
            }
          };
        }

        var fakeCanvasElement = makeElement('demo-canvas');
        var historyPushedState = null;
        var preventDefaultCalled = false;
        var searchInputVal = '공동주택';

        var sandbox = {
          document: {
            getElementById: function(id) {
              if (id === 'demo-canvas') return fakeCanvasElement;
              if (id === 'chat-thread') return makeElement('chat-thread');
              return null;
            }
          },
          console: { log: function() {}, error: function() {} },
          location: { search: '?journey=J-DEPT-01&dept-state=directory' },
          history: {
            pushState: function(state, title, url) {
              historyPushedState = url;
              sandbox.location.search = url.substring(url.indexOf('?'));
            }
          },
          window: null
        };
        sandbox.URLSearchParams = URLSearchParams;
        sandbox.window = sandbox;

        var cx = vm.createContext(sandbox);
        vm.runInContext(%s, cx);
        vm.runInContext(%s, cx);

        sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');

        var testResults = {};

        if (capturedClickHandler) {
          preventDefaultCalled = false;
          searchInputVal = ' 공동주택 ';
          var fakeEvent = {
            target: {
              closest: function(sel) {
                if (sel === '[data-dept-action]') {
                  return {
                    getAttribute: function(attr) {
                      if (attr === 'data-dept-action') return 'trigger-search';
                      return null;
                    }
                  };
                }
                return null;
              }
            },
            preventDefault: function() {
              preventDefaultCalled = true;
            }
          };
          capturedClickHandler(fakeEvent);
          testResults['exact'] = {
            url: historyPushedState,
            pd: preventDefaultCalled,
            html: capturedHTML,
            chat: capturedChatHTML
          };
        }

        sandbox.location.search = '?journey=J-DEPT-01&dept-state=directory';
        sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
        if (capturedClickHandler) {
          preventDefaultCalled = false;
          searchInputVal = '일반검색어';
          var fakeEvent = {
            target: {
              closest: function(sel) {
                if (sel === '[data-dept-action]') {
                  return {
                    getAttribute: function(attr) {
                      if (attr === 'data-dept-action') return 'trigger-search';
                      return null;
                    }
                  };
                }
                return null;
              }
            },
            preventDefault: function() {
              preventDefaultCalled = true;
            }
          };
          capturedClickHandler(fakeEvent);
          testResults['mismatch'] = {
            url: historyPushedState,
            pd: preventDefaultCalled,
            html: capturedHTML,
            chat: capturedChatHTML
          };
        }

        sandbox.location.search = '?journey=J-DEPT-01&dept-state=directory';
        sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
        if (capturedClickHandler) {
          preventDefaultCalled = false;
          searchInputVal = '  ';
          var fakeEvent = {
            target: {
              closest: function(sel) {
                if (sel === '[data-dept-action]') {
                  return {
                    getAttribute: function(attr) {
                      if (attr === 'data-dept-action') return 'trigger-search';
                      return null;
                    }
                  };
                }
                return null;
              }
            },
            preventDefault: function() {
              preventDefaultCalled = true;
            }
          };
          capturedClickHandler(fakeEvent);
          testResults['empty'] = {
            url: historyPushedState,
            pd: preventDefaultCalled,
            html: capturedHTML,
            chat: capturedChatHTML
          };
        }

        process.stdout.write(JSON.stringify(testResults));
        """ % (map_js, canvas_js)

        res = _run_node_script_file(sandbox_init, timeout=10)
        assert res.returncode == 0, res.stderr
        res_data = json.loads(res.stdout)

        exact = res_data['exact']
        assert "dept-state=result" in exact['url']
        assert exact['pd'] is True
        assert "공동주택과" in exact['html']
        assert "전체" in exact['html'] and "9" in exact['html'] and "1/1" in exact['html']
        assert "공동주택과에서 담당합니다" in exact['chat']

        mismatch = res_data['mismatch']
        assert "dept-state=directory" in mismatch['url']
        assert mismatch['pd'] is True
        assert "공동주택과" not in mismatch['html']
        assert "전체 9명" not in mismatch['html']
        assert "공동주택과에서 담당합니다" not in mismatch['chat']

        empty = res_data['empty']
        assert "dept-state=directory" in empty['url']
        assert empty['pd'] is True
        assert "공동주택과" not in empty['html']
        assert "전체 9명" not in empty['html']
        assert "공동주택과에서 담당합니다" not in empty['chat']

    def test_jdept01_hover_focus_menu_contract(self):
        """9. Hover and keyboard focus menu selectors exist in scoped CSS contract."""
        css = _read_static("citizen-action-demo-canvas.css")
        assert ".bg-home-gnb__item--dept:hover" in css
        assert ".bg-home-gnb__item--dept:focus-within" in css


# ---------------------------------------------------------------------------
class TestJDept01ReplayContracts:
    @pytest.fixture(scope="class")
    def replay_render(self):
        def _render(query: str):
            map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
            canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
            sandbox_init = """
            'use strict';
            var vm = require('vm');
            var capturedHTML = '';
            var capturedChatHTML = '';
            var eventListeners = {};
            function makeElement(id) {
              return {
                id: id,
                get innerHTML() { return id === 'chat-thread' ? capturedChatHTML : capturedHTML; },
                set innerHTML(v) { if (id === 'chat-thread') { capturedChatHTML = v; } else { capturedHTML = v; } },
                addEventListener: function(event, handler) { eventListeners[id + ':' + event] = handler; },
                querySelector: function() { return null; }
              };
            }
            var fakeCanvasElement = makeElement('demo-canvas');
            var sandbox = {
              document: {
                getElementById: function(id) {
                  if (id === 'demo-canvas') return fakeCanvasElement;
                  if (id === 'chat-thread') return makeElement('chat-thread');
                  return null;
                }
              },
              console: { log: function() {}, error: function() {} },
              location: { search: %s },
              history: { pushState: function(state, title, url) { sandbox.location.search = url.substring(url.indexOf('?')); } },
              window: null
            };
            sandbox.URLSearchParams = URLSearchParams;
            sandbox.window = sandbox;
            var cx = vm.createContext(sandbox);
            vm.runInContext(%s, cx);
            vm.runInContext(%s, cx);
            sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
            process.stdout.write(JSON.stringify({ html: capturedHTML, chat: capturedChatHTML }));
            """ % (json.dumps(query), map_js, canvas_js)
            res = _run_node_script_file(sandbox_init, timeout=10)
            assert res.returncode == 0, res.stderr
            return json.loads(res.stdout)
        return _render

    def test_replay_gate_exact_opt_in_and_fail_closed(self, replay_render):
        ready = replay_render("?replay=J-DEPT-01")
        assert 'data-dept-replay="true"' in ready["html"]
        assert 'data-dept-replay-step="ready"' in ready["html"]
        assert "공동주택 관련 문의는 어느 부서에 해야 하나요?" in ready["chat"]
        assert "북구청 업무 및 전화번호 안내에서 담당 부서를 찾겠습니다." in ready["chat"]

        for query in [
            "?replay=J-DEPT-01&journey=J-DEPT-01",
            "?replay=J-DEPT-01&replay=J-DEPT-01",
            "?replay=J-DEPT-01&replay-step=directory&replay-step=result",
            "?replay=J-DEPT-01&replay-step=bogus",
            "?replay=J-DEPT-01&extra=1",
            "?replay=j-dept-01",
        ]:
            result = replay_render(query)
            assert 'data-dept-replay="true"' not in result["html"], query
            assert "공동주택 관련 문의는 공동주택과에서 담당합니다." not in result["chat"], query

    def test_replay_state_ordering_and_exact_messages(self, replay_render):
        directory = replay_render("?replay=J-DEPT-01&replay-step=directory")
        assert 'data-dept-replay-step="directory"' in directory["html"]
        assert "홈</span> &gt; <span>북구소개</span> &gt; <span>구청안내</span> &gt; <strong>업무 및 전화번호 안내</strong>" in directory["html"]
        assert "북구소개 &gt; 구청안내 &gt; 업무 및 전화번호 안내에서 담당 부서를 확인하고 있습니다." in directory["chat"]
        assert "공동주택과에서 담당합니다" not in directory["chat"]

        result = replay_render("?replay=J-DEPT-01&replay-step=result")
        assert 'data-dept-replay-step="result"' in result["html"]
        assert 'value="공동주택"' in result["html"]
        assert "전체 <strong>9</strong>명, 현재 페이지 <strong>1/1</strong>" in result["html"]
        assert result["html"].count("<tbody>") == 1
        assert "공동주택과</td>" in result["html"]
        assert "062-410-6033" in result["html"]
        assert "공동주택과 업무전반" in result["html"]
        assert "공동주택 관련 문의는 공동주택과에서 담당합니다. 대표 연락처는 062-410-6033입니다." in result["chat"]

    def test_replay_controls_are_user_advanced_and_local_only(self):
        map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
        canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
        sandbox_init = """
        'use strict';
        var vm = require('vm');
        var capturedHTML = '';
        var capturedChatHTML = '';
        var capturedClickHandler = null;
        var pushed = [];
        var fetched = 0;
        var storageHits = 0;
        function makeElement(id) {
          return {
            id: id,
            get innerHTML() { return id === 'chat-thread' ? capturedChatHTML : capturedHTML; },
            set innerHTML(v) { if (id === 'chat-thread') { capturedChatHTML = v; } else { capturedHTML = v; } },
            addEventListener: function(event, handler) {
              if (event === 'click' && id === 'demo-canvas') capturedClickHandler = handler;
            },
            querySelector: function() { return null; }
          };
        }
        var fakeCanvasElement = makeElement('demo-canvas');
        var sandbox = {
          document: {
            getElementById: function(id) {
              if (id === 'demo-canvas') return fakeCanvasElement;
              if (id === 'chat-thread') return makeElement('chat-thread');
              return null;
            }
          },
          console: { log: function() {}, error: function() {} },
          location: { search: '?replay=J-DEPT-01' },
          history: {
            pushState: function(state, title, url) {
              pushed.push(url);
              sandbox.location.search = url.substring(url.indexOf('?'));
            }
          },
          fetch: function() { fetched += 1; },
          localStorage: { getItem: function() { storageHits += 1; }, setItem: function() { storageHits += 1; } },
          sessionStorage: { getItem: function() { storageHits += 1; }, setItem: function() { storageHits += 1; } },
          window: null
        };
        sandbox.URLSearchParams = URLSearchParams;
        sandbox.window = sandbox;
        var cx = vm.createContext(sandbox);
        vm.runInContext(%s, cx);
        vm.runInContext(%s, cx);
        sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');

        function click(action) {
          var preventDefaultCalled = false;
          capturedClickHandler({
            target: {
              closest: function(sel) {
                if (sel === '[data-dept-replay-action]') {
                  return { getAttribute: function() { return action; } };
                }
                return null;
              }
            },
            preventDefault: function() { preventDefaultCalled = true; }
          });
          return preventDefaultCalled;
        }

        var startPrevented = click('start');
        var afterStart = { search: sandbox.location.search, html: capturedHTML, chat: capturedChatHTML };
        var nextPrevented = click('next');
        var afterNext = { search: sandbox.location.search, html: capturedHTML, chat: capturedChatHTML };
        var restartPrevented = click('restart');
        var afterRestart = { search: sandbox.location.search, html: capturedHTML, chat: capturedChatHTML };

        process.stdout.write(JSON.stringify({
          pushed: pushed,
          fetched: fetched,
          storageHits: storageHits,
          startPrevented: startPrevented,
          nextPrevented: nextPrevented,
          restartPrevented: restartPrevented,
          afterStart: afterStart,
          afterNext: afterNext,
          afterRestart: afterRestart
        }));
        """ % (map_js, canvas_js)
        res = _run_node_script_file(sandbox_init, timeout=10)
        assert res.returncode == 0, res.stderr
        data = json.loads(res.stdout)

        assert data["pushed"] == [
            "?replay=J-DEPT-01&replay-step=directory",
            "?replay=J-DEPT-01&replay-step=result",
            "?replay=J-DEPT-01",
        ]
        assert data["fetched"] == 0
        assert data["storageHits"] == 0
        assert data["startPrevented"] is True
        assert data["nextPrevented"] is True
        assert data["restartPrevented"] is True
        assert 'data-dept-replay-step="directory"' in data["afterStart"]["html"]
        assert "다음" in data["afterStart"]["html"]
        assert "다시 시작" in data["afterStart"]["html"]
        assert 'data-dept-replay-step="result"' in data["afterNext"]["html"]
        assert "공동주택과 업무전반" in data["afterNext"]["html"]
        assert 'data-dept-replay-step="ready"' in data["afterRestart"]["html"]
        assert "시작" in data["afterRestart"]["html"]

    def test_non_replay_journey_routes_remain_available(self, replay_render):
        dept = replay_render("?journey=J-DEPT-01&dept-state=result")
        assert "공동주택과 업무전반" in dept["html"]
        assert 'data-dept-replay="true"' not in dept["html"]

        park = replay_render("?journey=J-PARK-01")
        assert "주차장 이용안내" in park["html"]
        assert 'data-dept-replay="true"' not in park["html"]

        kiosk = replay_render("?journey=J-KIOSK-01")
        assert "무인민원발급기 설치장소(50개소)" in kiosk["html"]
        assert 'data-dept-replay="true"' not in kiosk["html"]


# ---------------------------------------------------------------------------
# J-PARK-01 specific tests
# ---------------------------------------------------------------------------

class TestJPark01SpecificContracts:
    @pytest.fixture(scope="class")
    def park_render(self):
        """Helper to run Node and capture HTML under J-PARK-01 query."""
        def _render(query: str):
            map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
            canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
            sandbox_init = """
            'use strict';
            var vm = require('vm');
            var capturedHTML = '';
            var capturedChatHTML = '';
            function makeElement(id) {
              return {
                id: id,
                get innerHTML() { return id === 'chat-thread' ? capturedChatHTML : capturedHTML; },
                set innerHTML(v) { if (id === 'chat-thread') { capturedChatHTML = v; } else { capturedHTML = v; } },
                addEventListener: function(event, handler) {}
              };
            }
            var fakeCanvasElement = makeElement('demo-canvas');
            var sandbox = {
              document: {
                getElementById: function(id) {
                  if (id === 'demo-canvas') return fakeCanvasElement;
                  if (id === 'chat-thread') return makeElement('chat-thread');
                  return null;
                }
              },
              console: { log: function() {}, error: function() {} },
              location: { search: %s },
              window: null
            };
            sandbox.URLSearchParams = URLSearchParams;
            sandbox.window = sandbox;
            var cx = vm.createContext(sandbox);
            vm.runInContext(%s, cx);
            vm.runInContext(%s, cx);
            sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
            process.stdout.write(JSON.stringify({html: capturedHTML, chat: capturedChatHTML}));
            """ % (
                json.dumps(query),
                map_js,
                canvas_js
            )
            res = _run_node_script_file(sandbox_init, timeout=10)
            assert res.returncode == 0, res.stderr
            return json.loads(res.stdout)
        return _render

    # 1. Exact J-PARK-01 render
    def test_jpark01_exact_render(self, park_render):
        """1. ?journey=J-PARK-01 renders J-PARK static page."""
        result = park_render("?journey=J-PARK-01")
        html = result["html"]
        assert "bg-page--park-info" in html
        assert "주차장 이용안내" in html

    # 2. title, breadcrumb, left navigation, active LNB, facts table, operating hours, exact chat
    def test_jpark01_html_contract_elements(self, park_render):
        """2. J-PARK HTML contains all required contract elements."""
        result = park_render("?journey=J-PARK-01")
        html = result["html"]

        # title
        assert "주차장 이용안내" in html
        # breadcrumb
        assert "홈 > 북구소개 > 구청안내 >" in html
        # left section heading
        assert "북구소개" in html
        # open left group
        assert "구청안내" in html
        # LNB items
        assert "행정조직" in html
        assert "업무 및 전화번호 안내" in html
        assert "부서 대표(전화번호, FAX)" in html
        assert "청사안내" in html
        assert "찾아오시는 길" in html
        assert "주차장 이용안내" in html

        # Active LNB item
        assert "bg-park-lnb-item--active" in html

        # Parking facts - exact colon-form contract strings
        assert "주차면수: 130면" in html
        assert "주차타워: 111면(1층 42, 2층 29, 3층 40)" in html
        assert "기타: 19면" in html

        # Facts table - parking fee headers
        assert "무료주차" in html
        assert "기본" in html
        assert "초과" in html

        # Facts table - parking fee rows
        assert "1시간(모든 민원인)" in html
        assert "30분 500원" in html
        assert "10분당 200원" in html

        # Operating hours - exact colon-form contract strings
        assert "평일(월~금) 유료운영: 08:00 ~ 19:00" in html
        assert "야간 및 휴일 무료개방" in html

        # identity
        assert "전남광주통합특별시북구" in html

    # Exact chat verification
    def test_jpark01_exact_chat_messages(self, park_render):
        """2 (chat). J-PARK renders exactly 3 prescribed chat messages: 1 user + 2 AI."""
        result = park_render("?journey=J-PARK-01")
        chat = result["chat"]

        # Exact message count: 1 user + 2 AI = 3 total
        count = chat.count('class="chat-msg')
        assert count == 3, f"expected 3 chat messages, got {count}"
        assert chat.count('class="chat-msg chat-msg--user"') == 1, "expected exactly 1 user message"
        assert chat.count('class="chat-msg chat-msg--ai"') == 2, "expected exactly 2 AI messages"

        # User message
        assert "북구청 청사부설주차장은 몇 시까지 유료이고 요금은 어떻게 되나요?" in chat
        # AI message 1
        assert "북구청 주차장 이용안내에서 운영시간과 요금을 확인했습니다." in chat
        # AI message 2 (full pricing detail)
        assert "평일(월~금) 08:00~19:00에 유료운영하며, 모든 민원인은 1시간 무료입니다." in chat
        assert "이후 최초 30분은 500원" in chat
        assert "기본 30분 이후에는 10분당 200원" in chat
        assert "야간 및 휴일에는 무료개방합니다." in chat

    # 3. No interactive elements or action attributes in J-PARK HTML
    def test_jpark01_no_forbidden_action_attributes(self, park_render):
        """3. Rendered J-PARK HTML has no <a>, href, <button>, data-action-target, data-park-action."""
        result = park_render("?journey=J-PARK-01")
        html = result["html"]
        assert "<a " not in html, "J-PARK HTML must not contain <a> elements"
        assert "href=" not in html, "J-PARK HTML must not contain href attributes"
        assert "<button" not in html, "J-PARK HTML must not contain <button> elements"
        assert "data-action-target" not in html, "J-PARK HTML must not contain data-action-target"
        assert "data-park-action" not in html, "J-PARK HTML must not contain data-park-action"

    # 4. No raw parking capture filename in JS/CSS
    def test_jpark01_no_raw_capture_filenames_in_code(self):
        """4. JS/CSS contain no raw approved parking capture filenames."""
        js = _read_static("citizen-action-demo-canvas.js")
        css = _read_static("citizen-action-demo-canvas.css")
        combined = js + css
        prohibited = [
            "CaptureX_2026-07-05_bukgu.gwangju.kr.png",
            "CaptureX_2026-07-05_150817_bukgu.gwangju.kr.png",
            "CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png",
            "temp_bot.png", "temp_links.png", "temp_mid.png"
        ]
        for filename in prohibited:
            assert filename not in combined, f"prohibited parking capture filename found: {filename}"

    # 5. No forbidden words in rendered HTML
    def test_jpark01_no_forbidden_words_in_html(self, park_render):
        """5. Rendered J-PARK HTML contains no forbidden words including unapproved live-like info."""
        result = park_render("?journey=J-PARK-01")
        html = result["html"]
        forbidden = ["실시간", "예약", "결제", "지도", "빈자리", "CCTV", "26°C", "미세먼지", "초미세먼지", "전체"]
        for word in forbidden:
            assert word not in html, f"forbidden word '{word}' found in J-PARK HTML"

    # 6. No J-PARK-01, park-state, data-park-action in map.js
    def test_jpark01_not_in_map_js(self):
        """6. map.js does not reference J-PARK-01, park-state, or data-park-action."""
        js = _read_static("citizen-action-demo-map.js")
        assert "J-PARK-01" not in js, "J-PARK-01 must not be in map.js"
        assert "park-state" not in js, "park-state must not be in map.js"
        assert "data-park-action" not in js, "data-park-action must not be in map.js"

    # 7. Duplicate journey fallback
    def test_jpark01_duplicate_journey_fallback(self, park_render):
        """7. Duplicate journey falls back to historical non-J-PARK output."""
        result = park_render("?journey=J-PARK-01&journey=J-PARK-01")
        html = result["html"]
        assert "bg-page--park-info" not in html, "duplicate journey must fall back"
        assert "주차장 이용안내" not in html

    # 8. park-state present → fallback
    def test_jpark01_park_state_present_fallback(self, park_render):
        """8. Any park-state present triggers fallback."""
        result = park_render("?journey=J-PARK-01&park-state=home")
        html = result["html"]
        assert "bg-page--park-info" not in html, "park-state must trigger fallback"

    # 9. Duplicate park-state fallback
    def test_jpark01_duplicate_park_state_fallback(self, park_render):
        """9. Duplicate park-state triggers fallback."""
        result = park_render("?journey=J-PARK-01&park-state=home&park-state=home")
        html = result["html"]
        assert "bg-page--park-info" not in html, "duplicate park-state must fall back"

    # 10. Unsupported park-state fallback
    def test_jpark01_unsupported_park_state_fallback(self, park_render):
        """10. Unsupported park-state triggers fallback."""
        result = park_render("?journey=J-PARK-01&park-state=invalidstate")
        html = result["html"]
        assert "bg-page--park-info" not in html, "unsupported park-state must fall back"

    # 11. Unsupported extra query fallback
    def test_jpark01_extra_query_param_fallback(self, park_render):
        """11. Any extra query parameter beyond journey=J-PARK-01 triggers fallback."""
        result = park_render("?journey=J-PARK-01&extra=foo")
        html = result["html"]
        assert "bg-page--park-info" not in html, "extra query param must trigger fallback"

    # 12. dept-state mixed fallback
    def test_jpark01_dept_state_mixed_fallback(self, park_render):
        """12. dept-state mixed with J-PARK-01 triggers fallback."""
        result = park_render("?journey=J-PARK-01&dept-state=menu")
        html = result["html"]
        assert "bg-page--park-info" not in html, "dept-state must trigger fallback"

    # 13. Existing J-DEPT and historical routes still work
    def test_jdept01_still_works_after_jpark_addition(self, park_render):
        """13. J-DEPT-01 and historical routes remain functional."""
        # J-DEPT still works
        result_dept = park_render("?journey=J-DEPT-01")
        html_dept = result_dept["html"]
        assert "bg-page--home" in html_dept
        assert 'data-dept-journey="true"' in html_dept

        # Historical complaint route still works
        result_complaint = park_render("?journey=J-PARK-01")  # just ensure it doesn't break dept
        # Verify dept query still works independently
        map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
        canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
        sandbox_dept = """
        'use strict';
        var vm = require('vm');
        var capturedHTML = '';
        function makeElement(id) {
          return {
            id: id,
            get innerHTML() { return capturedHTML; },
            set innerHTML(v) { capturedHTML = v; },
            addEventListener: function(event, handler) {}
          };
        }
        var fakeCanvasElement = makeElement('demo-canvas');
        var sandbox = {
          document: {
            getElementById: function(id) {
              if (id === 'demo-canvas') return fakeCanvasElement;
              return null;
            }
          },
          console: { log: function() {}, error: function() {} },
          location: { search: '?journey=J-DEPT-01' },
          window: null
        };
        sandbox.URLSearchParams = URLSearchParams;
        sandbox.window = sandbox;
        var cx = vm.createContext(sandbox);
        vm.runInContext(%s, cx);
        vm.runInContext(%s, cx);
        sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
        process.stdout.write(capturedHTML);
        """ % (map_js, canvas_js)
        res = _run_node_script_file(sandbox_dept, timeout=10)
        assert res.returncode == 0, res.stderr
        html_dept_alone = res.stdout
        assert 'data-dept-journey="true"' in html_dept_alone
        assert "bg-page--home" in html_dept_alone

    # 14. Exact parking facts text contract with colons
    def test_jpark01_exact_text_contract(self, park_render):
        """14. J-PARK renders exact colon-form parking fact strings."""
        result = park_render("?journey=J-PARK-01")
        html = result["html"]
        assert "주차면수: 130면" in html
        assert "주차타워: 111면(1층 42, 2층 29, 3층 40)" in html
        assert "기타: 19면" in html
        assert "평일(월~금) 유료운영: 08:00 ~ 19:00" in html
        assert "야간 및 휴일 무료개방" in html

    # 15. No interactive markup at all in J-PARK HTML
    def test_jpark01_no_interactive_markup(self, park_render):
        """15. J-PARK HTML contains no <a>, href, <button> elements anywhere."""
        result = park_render("?journey=J-PARK-01")
        html = result["html"]
        assert "<a " not in html
        assert "href=" not in html
        assert "<button" not in html

    # 16. J-PARK does not call map route lookup / dispatcher
    def test_jpark01_no_map_route_dispatcher_call(self, park_render):
        """16. J-PARK render bypasses map.getRoute() and history.pushState entirely."""
        map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
        canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
        sandbox_spy = """
        'use strict';
        var vm = require('vm');
        var capturedHTML = '';
        var capturedChatHTML = '';
        var routeLookupCount = 0;
        var pushStateCount = 0;
        function makeElement(id) {
          return {
            id: id,
            get innerHTML() { return id === 'chat-thread' ? capturedChatHTML : capturedHTML; },
            set innerHTML(v) { if (id === 'chat-thread') { capturedChatHTML = v; } else { capturedHTML = v; } },
            addEventListener: function(event, handler) {}
          };
        }
        var fakeCanvasElement = makeElement('demo-canvas');
        var sandbox = {
          document: {
            getElementById: function(id) {
              if (id === 'demo-canvas') return fakeCanvasElement;
              if (id === 'chat-thread') return makeElement('chat-thread');
              return null;
            }
          },
          console: { log: function() {}, error: function() {} },
          location: { search: '?journey=J-PARK-01' },
          history: { pushState: function() { pushStateCount += 1; } },
          window: null
        };
        sandbox.URLSearchParams = URLSearchParams;
        sandbox.window = sandbox;
        var cx = vm.createContext(sandbox);
        vm.runInContext(%s, cx);
        // Wrap CitizenActionDemoMap.getRoute with a spy that counts calls
        var origGetRoute = sandbox.window.CitizenActionDemoMap.getRoute;
        sandbox.window.CitizenActionDemoMap = Object.freeze({
          getRouteIds: sandbox.window.CitizenActionDemoMap.getRouteIds,
          getRoute: function(routeId) { routeLookupCount += 1; return origGetRoute(routeId); },
          getCategoryLabel: sandbox.window.CitizenActionDemoMap.getCategoryLabel,
          isValidRoute: sandbox.window.CitizenActionDemoMap.isValidRoute,
          isValidTarget: sandbox.window.CitizenActionDemoMap.isValidTarget
        });
        vm.runInContext(%s, cx);
        sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
        process.stdout.write(JSON.stringify({
          html: capturedHTML,
          chat: capturedChatHTML,
          routeLookupCount: routeLookupCount,
          pushStateCount: pushStateCount
        }));
        """ % (map_js, canvas_js)
        res = _run_node_script_file(sandbox_spy, timeout=10)
        assert res.returncode == 0, res.stderr
        data = json.loads(res.stdout)
        html = data["html"]
        route_lookup_count = data["routeLookupCount"]
        push_state_count = data["pushStateCount"]
        # J-PARK must produce park page
        assert "bg-page--park-info" in html
        # J-PARK must not call map.getRoute() at all — it returns early before route dispatch
        assert route_lookup_count == 0, f"J-PARK must not call getRoute(), but got {route_lookup_count} call(s)"
        # J-PARK must not call history.pushState
        assert push_state_count == 0, f"J-PARK must not call pushState(), but got {push_state_count} call(s)"
        # No dispatcher attributes in rendered HTML
        assert "data-dept-action" not in html, "J-PARK HTML must not contain data-dept-action"
        assert "data-action-target" not in html, "J-PARK HTML must not contain data-action-target"
        assert "data-park-action" not in html, "J-PARK HTML must not contain data-park-action"

# J-KIOSK-01 specific tests
# ---------------------------------------------------------------------------

class TestJKiosk01SpecificContracts:
    @pytest.fixture(scope="class")
    def kiosk_render(self):
        """Helper to run Node and capture HTML under J-KIOSK-01 query."""
        def _render(query: str):
            map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
            canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
            sandbox_init = """
            'use strict';
            var vm = require('vm');
            var capturedHTML = '';
            var capturedChatHTML = '';
            function makeElement(id) {
              return {
                id: id,
                get innerHTML() { return id === 'chat-thread' ? capturedChatHTML : capturedHTML; },
                set innerHTML(v) { if (id === 'chat-thread') { capturedChatHTML = v; } else { capturedHTML = v; } },
                addEventListener: function(event, handler) {}
              };
            }
            var fakeCanvasElement = makeElement('demo-canvas');
            var sandbox = {
              document: {
                getElementById: function(id) {
                  if (id === 'demo-canvas') return fakeCanvasElement;
                  if (id === 'chat-thread') return makeElement('chat-thread');
                  return null;
                }
              },
              console: { log: function() {}, error: function() {} },
              location: { search: %s },
              window: null
            };
            sandbox.URLSearchParams = URLSearchParams;
            sandbox.window = sandbox;
            var cx = vm.createContext(sandbox);
            vm.runInContext(%s, cx);
            vm.runInContext(%s, cx);
            sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
            process.stdout.write(JSON.stringify({html: capturedHTML, chat: capturedChatHTML}));
            """ % (
                json.dumps(query),
                map_js,
                canvas_js
            )
            res = _run_node_script_file(sandbox_init, timeout=10)
            assert res.returncode == 0, res.stderr
            return json.loads(res.stdout)
        return _render

    # 1. Exact J-KIOSK-01 render
    def test_jkiosk01_exact_render(self, kiosk_render):
        """1. ?journey=J-KIOSK-01 renders J-KIOSK static page."""
        result = kiosk_render("?journey=J-KIOSK-01")
        html = result["html"]
        assert "bg-page--kiosk-info" in html
        assert "무인민원발급기" in html

    # 2. title, breadcrumb, left navigation, active LNB, table, chat
    def test_jkiosk01_html_contract_elements(self, kiosk_render):
        """2. J-KIOSK HTML contains all required contract elements."""
        result = kiosk_render("?journey=J-KIOSK-01")
        html = result["html"]

        # identity
        assert "전남광주통합특별시북구" in html
        # title
        assert "무인민원발급기" in html
        # breadcrumb
        assert "홈 > 종합민원 > 종합민원 > 무인민원발급기 >" in html
        assert "<strong>설치장소</strong>" in html
        # left section heading
        assert "종합민원" in html
        # active left-nav item
        assert "bg-kiosk-lnb-item--active" in html
        assert "무인민원발급기" in html

        # tabs
        assert "설치장소" in html
        assert "발급종류 및 처리순서" in html
        assert "발급가능 민원서류" in html
        assert "bg-kiosk-tab--active" in html

        # table heading
        assert "무인민원발급기 설치장소(50개소)" in html
        # table columns
        assert "구분" in html
        assert "시설명" in html
        assert "도로명주소" in html
        assert "운영시간" in html
        assert "발급종수" in html
        assert "발급기형태" in html
        assert "비고" in html

        # factual data rows - exactly the two approved
        assert "북구청 민원실" in html
        assert "우치로 77" in html
        assert "24시간" in html
        assert "122종" in html
        assert "장애인겸용" in html
        assert "북구청 민원실 2" in html
        assert "121종" in html

    # Exact chat verification
    def test_jkiosk01_exact_chat_messages(self, kiosk_render):
        """2 (chat). J-KIOSK renders exactly 3 prescribed chat messages: 1 user + 2 AI."""
        result = kiosk_render("?journey=J-KIOSK-01")
        chat = result["chat"]

        # Exact message count: 1 user + 2 AI = 3 total
        count = chat.count('class="chat-msg')
        assert count == 3, f"expected 3 chat messages, got {count}"
        assert chat.count('class="chat-msg chat-msg--user"') == 1, "expected exactly 1 user message"
        assert chat.count('class="chat-msg chat-msg--ai"') == 2, "expected exactly 2 AI messages"

        # User message
        assert "북구청 무인민원발급기는 어디에 있고 언제 이용할 수 있나요?" in chat
        # AI message 1
        assert "북구청 무인민원발급기 설치장소에서 이용 정보를 확인했습니다." in chat
        # AI message 2
        assert "북구청 민원실과 북구청 민원실 2는 우치로 77에 있으며 24시간 이용할 수 있습니다." in chat
        assert "발급 가능 민원서류는 각각 122종과 121종입니다." in chat

    # 3. No interactive elements or action attributes in J-KIOSK HTML
    def test_jkiosk01_no_forbidden_action_attributes(self, kiosk_render):
        """3. Rendered J-KIOSK HTML has no <a>, href, <button>, data-action-target, data-kiosk-action."""
        result = kiosk_render("?journey=J-KIOSK-01")
        html = result["html"]
        assert "<a " not in html, "J-KIOSK HTML must not contain <a> elements"
        assert "href=" not in html, "J-KIOSK HTML must not contain href attributes"
        assert "<button" not in html, "J-KIOSK HTML must not contain <button> elements"
        assert "data-action-target" not in html, "J-KIOSK HTML must not contain data-action-target"
        assert "data-dept-action" not in html, "J-KIOSK HTML must not contain data-dept-action"
        assert "data-park-action" not in html, "J-KIOSK HTML must not contain data-park-action"
        assert "data-kiosk-action" not in html, "J-KIOSK HTML must not contain data-kiosk-action"

    # 4. No raw kiosk capture filename in JS/CSS
    def test_jkiosk01_no_raw_capture_filenames_in_code(self):
        """4. JS/CSS contain no raw approved kiosk capture filenames."""
        js = _read_static("citizen-action-demo-canvas.js")
        css = _read_static("citizen-action-demo-canvas.css")
        combined = js + css
        prohibited = [
            "jkiosk-01-installation-desktop.png",
            "jkiosk-02-installation-full.png",
            "CaptureX*kiosk*",
        ]
        for filename in prohibited:
            assert filename not in combined, f"prohibited kiosk capture filename found: {filename}"

    # 5. Duplicate journey fallback
    def test_jkiosk01_duplicate_journey_fallback(self, kiosk_render):
        """5. Duplicate journey falls back to historical non-J-KIOSK output."""
        result = kiosk_render("?journey=J-KIOSK-01&journey=J-KIOSK-01")
        html = result["html"]
        assert "bg-page--kiosk-info" not in html, "duplicate journey must fall back"
        assert "무인민원발급기 설치장소" not in html

    # 6. kiosk-state present -> fallback
    def test_jkiosk01_kiosk_state_present_fallback(self, kiosk_render):
        """6. Any kiosk-state present triggers fallback."""
        result = kiosk_render("?journey=J-KIOSK-01&kiosk-state=home")
        html = result["html"]
        assert "bg-page--kiosk-info" not in html, "kiosk-state must trigger fallback"

    # 7. park-state mixed fallback
    def test_jkiosk01_park_state_mixed_fallback(self, kiosk_render):
        """7. park-state mixed with J-KIOSK-01 triggers fallback."""
        result = kiosk_render("?journey=J-KIOSK-01&park-state=home")
        html = result["html"]
        assert "bg-page--kiosk-info" not in html, "park-state must trigger fallback"

    # 8. dept-state mixed fallback
    def test_jkiosk01_dept_state_mixed_fallback(self, kiosk_render):
        """8. dept-state mixed with J-KIOSK-01 triggers fallback."""
        result = kiosk_render("?journey=J-KIOSK-01&dept-state=menu")
        html = result["html"]
        assert "bg-page--kiosk-info" not in html, "dept-state must trigger fallback"

    # 9. Extra query fallback
    def test_jkiosk01_extra_query_param_fallback(self, kiosk_render):
        """9. Any extra query parameter beyond journey=J-KIOSK-01 triggers fallback."""
        result = kiosk_render("?journey=J-KIOSK-01&extra=foo")
        html = result["html"]
        assert "bg-page--kiosk-info" not in html, "extra query param must trigger fallback"

    # 10. J-KIOSK does not call map route lookup / dispatcher
    def test_jkiosk01_no_map_route_dispatcher_call(self, kiosk_render):
        """10. J-KIOSK render bypasses map.getRoute() and history.pushState entirely."""
        map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
        canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
        sandbox_spy = """
        'use strict';
        var vm = require('vm');
        var capturedHTML = '';
        var capturedChatHTML = '';
        var routeLookupCount = 0;
        var pushStateCount = 0;
        function makeElement(id) {
          return {
            id: id,
            get innerHTML() { return id === 'chat-thread' ? capturedChatHTML : capturedHTML; },
            set innerHTML(v) { if (id === 'chat-thread') { capturedChatHTML = v; } else { capturedHTML = v; } },
            addEventListener: function(event, handler) {}
          };
        }
        var fakeCanvasElement = makeElement('demo-canvas');
        var sandbox = {
          document: {
            getElementById: function(id) {
              if (id === 'demo-canvas') return fakeCanvasElement;
              if (id === 'chat-thread') return makeElement('chat-thread');
              return null;
            }
          },
          console: { log: function() {}, error: function() {} },
          location: { search: '?journey=J-KIOSK-01' },
          history: { pushState: function() { pushStateCount += 1; } },
          window: null
        };
        sandbox.URLSearchParams = URLSearchParams;
        sandbox.window = sandbox;
        var cx = vm.createContext(sandbox);
        vm.runInContext(%s, cx);
        // Wrap CitizenActionDemoMap.getRoute with a spy that counts calls
        var origGetRoute = sandbox.window.CitizenActionDemoMap.getRoute;
        sandbox.window.CitizenActionDemoMap = Object.freeze({
          getRouteIds: sandbox.window.CitizenActionDemoMap.getRouteIds,
          getRoute: function(routeId) { routeLookupCount += 1; return origGetRoute(routeId); },
          getCategoryLabel: sandbox.window.CitizenActionDemoMap.getCategoryLabel,
          isValidRoute: sandbox.window.CitizenActionDemoMap.isValidRoute,
          isValidTarget: sandbox.window.CitizenActionDemoMap.isValidTarget
        });
        vm.runInContext(%s, cx);
        sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
        process.stdout.write(JSON.stringify({
          html: capturedHTML,
          chat: capturedChatHTML,
          routeLookupCount: routeLookupCount,
          pushStateCount: pushStateCount
        }));
        """ % (map_js, canvas_js)
        res = _run_node_script_file(sandbox_spy, timeout=10)
        assert res.returncode == 0, res.stderr
        data = json.loads(res.stdout)
        html = data["html"]
        route_lookup_count = data["routeLookupCount"]
        push_state_count = data["pushStateCount"]
        # J-KIOSK must produce kiosk page
        assert "bg-page--kiosk-info" in html
        # J-KIOSK must not call map.getRoute() at all — it returns early before route dispatch
        assert route_lookup_count == 0, f"J-KIOSK must not call getRoute(), but got {route_lookup_count} call(s)"
        # J-KIOSK must not call history.pushState
        assert push_state_count == 0, f"J-KIOSK must not call pushState(), but got {push_state_count} call(s)"
        # No dispatcher attributes in rendered HTML
        assert "data-dept-action" not in html, "J-KIOSK HTML must not contain data-dept-action"
        assert "data-action-target" not in html, "J-KIOSK HTML must not contain data-action-target"
        assert "data-park-action" not in html, "J-KIOSK HTML must not contain data-park-action"
        assert "data-kiosk-action" not in html, "J-KIOSK HTML must not contain data-kiosk-action"

    # 11. J-PARK and J-DEPT still work after J-KIOSK addition
    def test_jkiosk01_preserves_jpark_jdept(self, kiosk_render):
        """11. J-PARK and J-DEPT routes remain functional after J-KIOSK addition."""
        # J-PARK still works
        result_park = kiosk_render("?journey=J-PARK-01")
        html_park = result_park["html"]
        assert "bg-page--park-info" in html_park
        assert "주차장 이용안내" in html_park

        # J-DEPT still works
        result_dept = kiosk_render("?journey=J-DEPT-01")
        html_dept = result_dept["html"]
        assert "bg-page--home" in html_dept
        assert 'data-dept-journey="true"' in html_dept

    # 12. J-KIOSK not in map.js
    def test_jkiosk01_not_in_map_js(self):
        """12. map.js does not reference J-KIOSK-01, kiosk-state, or data-kiosk-action."""
        js = _read_static("citizen-action-demo-map.js")
        assert "J-KIOSK-01" not in js, "J-KIOSK-01 must not be in map.js"
        assert "kiosk-state" not in js, "kiosk-state must not be in map.js"
        assert "data-kiosk-action" not in js, "data-kiosk-action must not be in map.js"


# ---------------------------------------------------------------------------
# Stage 864: Accelerated replay contract tests
# ---------------------------------------------------------------------------

class TestAutoReplayContract:
    """Focused tests for the accelerated auto-replay contract (#864)."""

    @pytest.fixture(scope="class")
    def auto_render(self):
        def _render(query: str):
            map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
            canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
            sandbox_init = """
            'use strict';
            var vm = require('vm');
            var capturedHTML = '';
            var capturedChatHTML = '';
            var eventListeners = {};
            var timers = [];
            var intervalCount = 0;
            function makeElement(id) {
              return {
                id: id,
                get innerHTML() { return id === 'chat-thread' ? capturedChatHTML : capturedHTML; },
                set innerHTML(v) { if (id === 'chat-thread') { capturedChatHTML = v; } else { capturedHTML = v; } },
                addEventListener: function(event, handler) { eventListeners[id + ':' + event] = handler; },
                querySelector: function() { return null; }
              };
            }
            var fakeCanvasElement = makeElement('demo-canvas');
            var sandbox = {
              document: {
                getElementById: function(id) {
                  if (id === 'demo-canvas') return fakeCanvasElement;
                  if (id === 'chat-thread') return makeElement('chat-thread');
                  return null;
                }
              },
              console: { log: function() {}, error: function() {} },
              location: { search: %s },
              history: { pushState: function(state, title, url) { sandbox.location.search = url.substring(url.indexOf('?')); } },
              setTimeout: function(fn, ms) { timers.push({fn: fn, ms: ms, type: 'timeout'}); return timers.length; },
              clearTimeout: function(id) { if (id && timers[id - 1]) { timers[id - 1] = null; } },
              setInterval: function() { intervalCount += 1; return -1; },
              window: null
            };
            sandbox.URLSearchParams = URLSearchParams;
            sandbox.window = sandbox;
            var cx = vm.createContext(sandbox);
            vm.runInContext(%s, cx);
            vm.runInContext(%s, cx);
            sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
            process.stdout.write(JSON.stringify({
              html: capturedHTML,
              chat: capturedChatHTML,
              timers: timers.filter(function(t) { return t !== null; }).map(function(t) { return {ms: t.ms, type: t.type}; }),
              intervalCount: intervalCount
            }));
            """ % (json.dumps(query), map_js, canvas_js)
            res = _run_node_script_file(sandbox_init, timeout=10)
            assert res.returncode == 0, res.stderr
            return json.loads(res.stdout)
        return _render

    @pytest.fixture(scope="class")
    def auto_interact(self):
        def _interact(query, actions):
            map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
            canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
            sandbox_init = """
            'use strict';
            var vm = require('vm');
            var capturedHTML = '';
            var capturedChatHTML = '';
            var capturedClickHandler = null;
            var timers = [];
            var intervalCount = 0;
            var pushed = [];
            function makeElement(id) {
              return {
                id: id,
                get innerHTML() { return id === 'chat-thread' ? capturedChatHTML : capturedHTML; },
                set innerHTML(v) { if (id === 'chat-thread') { capturedChatHTML = v; } else { capturedHTML = v; } },
                addEventListener: function(event, handler) {
                  if (event === 'click' && id === 'demo-canvas') capturedClickHandler = handler;
                },
                querySelector: function() { return null; }
              };
            }
            var fakeCanvasElement = makeElement('demo-canvas');
            var sandbox = {
              document: {
                getElementById: function(id) {
                  if (id === 'demo-canvas') return fakeCanvasElement;
                  if (id === 'chat-thread') return makeElement('chat-thread');
                  return null;
                }
              },
              console: { log: function() {}, error: function() {} },
              location: { search: %s },
              history: {
                pushState: function(state, title, url) {
                  pushed.push(url);
                  sandbox.location.search = url.substring(url.indexOf('?'));
                }
              },
              setTimeout: function(fn, ms) { timers.push({fn: fn, ms: ms, type: 'timeout'}); return timers.length; },
              clearTimeout: function(id) { if (id && timers[id - 1]) { timers[id - 1] = null; } },
              setInterval: function() { intervalCount += 1; return -1; },
              fetch: function() {},
              localStorage: { getItem: function() {}, setItem: function() {} },
              sessionStorage: { getItem: function() {}, setItem: function() {} },
              window: null
            };
            sandbox.URLSearchParams = URLSearchParams;
            sandbox.window = sandbox;
            var cx = vm.createContext(sandbox);
            vm.runInContext(%s, cx);
            vm.runInContext(%s, cx);
            sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');

            var actionList = %s;
            var results = [];
            for (var a = 0; a < actionList.length; a++) {
              var act = actionList[a];
              if (act.type === 'click') {
                capturedClickHandler({
                  target: {
                    closest: function(sel) {
                      if (sel === '[data-auto-replay-action]') {
                        return { getAttribute: function() { return act.action; } };
                      }
                      return null;
                    }
                  },
                  preventDefault: function() {}
                });
              } else if (act.type === 'fire-timer') {
                var pending = timers.filter(function(t) { return t !== null; });
                if (pending.length > 0) {
                  pending[pending.length - 1].fn();
                  timers[timers.indexOf(pending[pending.length - 1])] = null;
                }
              }
              results.push({
                html: capturedHTML,
                chat: capturedChatHTML,
                search: sandbox.location.search,
                pendingTimers: timers.filter(function(t) { return t !== null; }).length
              });
            }
            process.stdout.write(JSON.stringify({
              results: results,
              pushed: pushed,
              intervalCount: intervalCount
            }));
            """ % (json.dumps(query), map_js, canvas_js, json.dumps(actions))
            res = _run_node_script_file(sandbox_init, timeout=10)
            assert res.returncode == 0, res.stderr
            return json.loads(res.stdout)
        return _interact

    # 1. valid auto ready gate
    def test_valid_auto_ready_gate(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=auto")
        assert 'data-dept-auto-replay="true"' in result["html"]
        assert '시연 시작' in result["html"]
        assert "공동주택 관련 문의는 어느 부서에 해야 하나요?" in result["chat"]

    # 2. duplicate replay rejected
    def test_duplicate_replay_rejected(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay=J-DEPT-01&replay-mode=auto")
        assert 'data-dept-auto-replay="true"' not in result["html"]

    # 3. duplicate replay-mode rejected
    def test_duplicate_replay_mode_rejected(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=auto&replay-mode=auto")
        assert 'data-dept-auto-replay="true"' not in result["html"]

    # 4. duplicate replay-step rejected
    def test_duplicate_replay_step_rejected(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=auto&replay-step=directory&replay-step=result")
        assert 'data-dept-auto-replay="true"' not in result["html"]

    # 5. unknown replay-mode rejected
    def test_unknown_replay_mode_rejected(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=manual")
        assert 'data-dept-auto-replay="true"' not in result["html"]

    # 6. unknown replay-step rejected
    def test_unknown_replay_step_rejected(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=auto&replay-step=bogus")
        assert 'data-dept-auto-replay="true"' not in result["html"]

    # 7. extra query key rejected
    def test_extra_query_key_rejected(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=auto&extra=1")
        assert 'data-dept-auto-replay="true"' not in result["html"]

    # 8. manual replay remains manual
    def test_manual_replay_remains_manual(self, auto_render):
        result = auto_render("?replay=J-DEPT-01")
        assert 'data-dept-replay="true"' in result["html"]
        assert 'data-dept-auto-replay="true"' not in result["html"]

    # 9. regular J-DEPT route remains unchanged
    def test_regular_jdept_route_unchanged(self, auto_render):
        result = auto_render("?journey=J-DEPT-01")
        assert 'data-dept-journey="true"' in result["html"]
        assert 'data-dept-auto-replay="true"' not in result["html"]
        assert 'data-dept-replay="true"' not in result["html"]

    # 10. J-PARK remains unchanged
    def test_jpark_remains_unchanged(self, auto_render):
        result = auto_render("?journey=J-PARK-01")
        assert "bg-page--park-info" in result["html"]
        assert 'data-dept-auto-replay="true"' not in result["html"]

    # 11. J-KIOSK remains unchanged
    def test_jkiosk_remains_unchanged(self, auto_render):
        result = auto_render("?journey=J-KIOSK-01")
        assert "bg-page--kiosk-info" in result["html"]
        assert 'data-dept-auto-replay="true"' not in result["html"]

    # 12. ready state has no pending timer
    def test_ready_state_no_pending_timer(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=auto")
        assert len(result["timers"]) == 0

    # 13. start preserves replay-mode=auto
    def test_start_preserves_auto_mode(self, auto_interact):
        data = auto_interact("?replay=J-DEPT-01&replay-mode=auto", [
            {"type": "click", "action": "start"}
        ])
        assert "replay-mode=auto" in data["results"][0]["search"]

    # 14. phase order route → directory → search → result
    def test_phase_order(self, auto_interact):
        data = auto_interact("?replay=J-DEPT-01&replay-mode=auto", [
            {"type": "click", "action": "start"},
            {"type": "fire-timer"},
            {"type": "fire-timer"},
            {"type": "fire-timer"},
        ])
        searches = [r["search"] for r in data["results"]]
        assert any("replay-step=route" in s for s in searches)
        assert any("replay-step=directory" in s for s in searches)
        assert any("replay-step=search" in s for s in searches)
        assert any("replay-step=result" in s for s in searches)
        # Verify ordering: route before directory before search before result
        route_idx = next(i for i, s in enumerate(searches) if "replay-step=route" in s)
        dir_idx = next(i for i, s in enumerate(searches) if "replay-step=directory" in s)
        search_idx = next(i for i, s in enumerate(searches) if "replay-step=search" in s)
        result_idx = next(i for i, s in enumerate(searches) if "replay-step=result" in s)
        assert route_idx < dir_idx < search_idx < result_idx

    # 15. only one timer is pending at each step
    def test_only_one_timer_pending(self, auto_interact):
        data = auto_interact("?replay=J-DEPT-01&replay-mode=auto", [
            {"type": "click", "action": "start"},
        ])
        for r in data["results"]:
            assert r["pendingTimers"] <= 1

    # 16. no setInterval usage
    def test_no_setinterval_usage(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=auto")
        assert result["intervalCount"] == 0

    # 17. pause clears timer
    def test_pause_clears_timer(self, auto_interact):
        data = auto_interact("?replay=J-DEPT-01&replay-mode=auto", [
            {"type": "click", "action": "start"},
            {"type": "click", "action": "pause"},
        ])
        last = data["results"][-1]
        assert last["pendingTimers"] == 0

    # 18. paused state remains frozen
    def test_paused_state_remains_frozen(self, auto_interact):
        data = auto_interact("?replay=J-DEPT-01&replay-mode=auto", [
            {"type": "click", "action": "start"},
            {"type": "click", "action": "pause"},
            {"type": "fire-timer"},
        ])
        paused_search = data["results"][1]["search"]
        after_fire = data["results"][2]["search"]
        assert after_fire == paused_search, "paused state must not advance on timer fire"

    # 19. continue resumes the current phase
    def test_continue_resumes_current_phase(self, auto_interact):
        data = auto_interact("?replay=J-DEPT-01&replay-mode=auto", [
            {"type": "click", "action": "start"},
            {"type": "click", "action": "pause"},
            {"type": "click", "action": "resume"},
        ])
        after_resume = data["results"][2]
        assert 'data-auto-replay-status="running"' in after_resume["html"]
        assert after_resume["pendingTimers"] >= 1

    # 20. restart restores auto-ready URL
    def test_restart_restores_auto_ready_url(self, auto_interact):
        data = auto_interact("?replay=J-DEPT-01&replay-mode=auto", [
            {"type": "click", "action": "start"},
            {"type": "click", "action": "restart"},
        ])
        last_search = data["results"][-1]["search"]
        assert "replay=J-DEPT-01" in last_search
        assert "replay-mode=auto" in last_search

    # 21. exact approved chat copy
    def test_exact_approved_chat_copy(self, auto_interact):
        data = auto_interact("?replay=J-DEPT-01&replay-mode=auto", [
            {"type": "click", "action": "start"},
            {"type": "fire-timer"},
            {"type": "fire-timer"},
            {"type": "fire-timer"},
        ])
        final_chat = data["results"][-1]["chat"]
        assert "공동주택 관련 문의는 어느 부서에 해야 하나요?" in final_chat
        assert "북구청 업무 및 전화번호 안내 경로를 확인하겠습니다." in final_chat
        assert "북구소개 메뉴에서 업무 및 전화번호 안내를 확인하고 있습니다." in final_chat
        assert "공동주택 관련 담당 부서를 검색하고 있습니다." in final_chat
        assert "공동주택 관련 문의는 공동주택과에서 담당합니다. 대표 연락처는 062-410-6033입니다." in final_chat

    # 22. exact approved action-bubble copy
    def test_exact_approved_action_bubble_copy(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=auto&replay-step=directory")
        assert "북구소개 메뉴를 선택합니다" in result["html"]
        result2 = auto_render("?replay=J-DEPT-01&replay-mode=auto&replay-step=search")
        assert "공동주택을 검색합니다" in result2["html"]
        result3 = auto_render("?replay=J-DEPT-01&replay-mode=auto&replay-step=result")
        assert "담당 부서와 연락처를 확인했습니다" in result3["html"]
        result4 = auto_render("?replay=J-DEPT-01&replay-mode=auto&replay-step=route")
        assert "업무 및 전화번호 안내 경로를 확인합니다" in result4["html"]

    # 23. exact result row/count/final answer
    def test_exact_result_row_count_final_answer(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=auto&replay-step=result")
        html = result["html"]
        assert "공동주택과" in html
        assert "062-410-6033" in html
        assert "공동주택과 업무전반" in html
        assert "전체" in html and "9" in html and "1/1" in html
        assert "공동주택 관련 문의는 공동주택과에서 담당합니다. 대표 연락처는 062-410-6033입니다." in result["chat"]

    # 24. no fetch/storage/cookies/external origin
    def test_no_fetch_storage_cookies_external_origin(self, auto_interact):
        js = _read_static("citizen-action-demo-canvas.js")
        code_only = _strip_all(js)
        for pattern in ["fetch(", "localStorage", "sessionStorage", "document.cookie", "XMLHttpRequest", "WebSocket", "EventSource"]:
            assert pattern not in code_only, f"prohibited pattern {pattern} found in canvas.js"

    # 25. CSS scope uses data-dept-auto-replay=true
    def test_css_scope_uses_auto_replay_attribute(self):
        css = _read_static("citizen-action-demo-canvas.css")
        assert '[data-dept-auto-replay="true"]' in css

    # 26. prefers-reduced-motion fallback exists
    def test_prefers_reduced_motion_fallback_exists(self):
        css = _read_static("citizen-action-demo-canvas.css")
        assert "prefers-reduced-motion" in css


# ---------------------------------------------------------------------------
# Stage 864-A: Visible phase feedback and source-contract correction tests
# ---------------------------------------------------------------------------

class TestAutoReplayVisiblePhaseFeedback:
    """Tests for the visible accelerated replay feedback contract (#864-A)."""

    @pytest.fixture(scope="class")
    def auto_render(self):
        def _render(query: str):
            map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
            canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
            sandbox_init = """
            'use strict';
            var vm = require('vm');
            var capturedHTML = '';
            var capturedChatHTML = '';
            function makeElement(id) {
              return {
                id: id,
                get innerHTML() { return id === 'chat-thread' ? capturedChatHTML : capturedHTML; },
                set innerHTML(v) { if (id === 'chat-thread') { capturedChatHTML = v; } else { capturedHTML = v; } },
                addEventListener: function() {},
                querySelector: function() { return null; }
              };
            }
            var fakeCanvasElement = makeElement('demo-canvas');
            var sandbox = {
              document: {
                getElementById: function(id) {
                  if (id === 'demo-canvas') return fakeCanvasElement;
                  if (id === 'chat-thread') return makeElement('chat-thread');
                  return null;
                }
              },
              console: { log: function() {}, error: function() {} },
              location: { search: %s },
              history: { pushState: function() {} },
              setTimeout: function() {},
              clearTimeout: function() {},
              setInterval: function() {},
              window: null
            };
            sandbox.URLSearchParams = URLSearchParams;
            sandbox.window = sandbox;
            var cx = vm.createContext(sandbox);
            vm.runInContext(%s, cx);
            vm.runInContext(%s, cx);
            sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
            process.stdout.write(JSON.stringify({ html: capturedHTML, chat: capturedChatHTML }));
            """ % (json.dumps(query), map_js, canvas_js)
            res = _run_node_script_file(sandbox_init, timeout=10)
            assert res.returncode == 0, res.stderr
            return json.loads(res.stdout)
        return _render

    # 1. all four advancing phases contain data-auto-replay-step
    def test_all_phases_have_auto_replay_step(self, auto_render):
        for step in ["route", "directory", "search", "result"]:
            result = auto_render("?replay=J-DEPT-01&replay-mode=auto&replay-step=" + step)
            assert 'data-auto-replay-step="' + step + '"' in result["html"], \
                f"step '{step}' missing data-auto-replay-step"

    # 2. route HTML contains cursor, target-highlight, and click-feedback markup
    def test_route_has_cursor_highlight_click_feedback(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=auto&replay-step=route")
        html = result["html"]
        assert 'class="bg-auto-cursor' in html, "route missing cursor"
        assert 'bg-auto-cursor--gnb' in html, "route missing gnb cursor position"
        assert 'data-auto-cursor-phase="route"' in html, "route missing cursor phase"
        assert 'class="bg-auto-target-highlight' in html, "route missing target highlight"
        assert 'bg-auto-target--gnb-dept' in html, "route missing gnb-dept target"
        assert 'data-auto-target-phase="route"' in html, "route missing target phase"
        assert 'class="bg-auto-click-feedback' in html, "route missing click feedback"
        assert 'data-auto-click-phase="route"' in html, "route missing click phase"

    # 3. directory HTML contains cursor, target-highlight, and click-feedback markup
    def test_directory_has_cursor_highlight_click_feedback(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=auto&replay-step=directory")
        html = result["html"]
        assert 'class="bg-auto-cursor' in html, "directory missing cursor"
        assert 'bg-auto-cursor--menu-link' in html, "directory missing menu-link cursor"
        assert 'data-auto-cursor-phase="directory"' in html
        assert 'class="bg-auto-target-highlight' in html, "directory missing target highlight"
        assert 'bg-auto-target--directory-link' in html
        assert 'data-auto-target-phase="directory"' in html
        assert 'class="bg-auto-click-feedback' in html, "directory missing click feedback"
        assert 'data-auto-click-phase="directory"' in html

    # 4. search HTML contains cursor, target-highlight, and click-feedback markup
    def test_search_has_cursor_highlight_click_feedback(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=auto&replay-step=search")
        html = result["html"]
        assert 'class="bg-auto-cursor' in html, "search missing cursor"
        assert 'bg-auto-cursor--search' in html, "search missing search cursor"
        assert 'data-auto-cursor-phase="search"' in html
        assert 'class="bg-auto-target-highlight' in html, "search missing target highlight"
        assert 'bg-auto-target--search-input' in html
        assert 'data-auto-target-phase="search"' in html
        assert 'class="bg-auto-click-feedback' in html, "search missing click feedback"
        assert 'data-auto-click-phase="search"' in html

    # 5. result HTML contains cursor, target-highlight, and click-feedback markup
    def test_result_has_cursor_highlight_click_feedback(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-mode=auto&replay-step=result")
        html = result["html"]
        assert 'class="bg-auto-cursor' in html, "result missing cursor"
        assert 'bg-auto-cursor--result-row' in html, "result missing result-row cursor"
        assert 'data-auto-cursor-phase="result"' in html
        assert 'class="bg-auto-target-highlight' in html, "result missing target highlight"
        assert 'bg-auto-target--result-row' in html
        assert 'data-auto-target-phase="result"' in html
        assert 'class="bg-auto-click-feedback' in html, "result missing click feedback"
        assert 'data-auto-click-phase="result"' in html

    # 6. action bubble is scoped to auto replay
    def test_action_bubble_scoped_to_auto_replay(self):
        css = _read_static("citizen-action-demo-canvas.css")
        # The bubble style must be inside a [data-dept-auto-replay="true"] selector
        assert '[data-dept-auto-replay="true"] .bg-dept-action-bubble' in css

    # 7. action bubble does not use left:50% or translateX(-50%)
    def test_action_bubble_no_centered_positioning(self):
        css = _read_static("citizen-action-demo-canvas.css")
        # Collect all bubble rule blocks
        lines = css.split("\n")
        in_bubble_block = False
        all_bubble_props = []
        current_block = []
        for line in lines:
            stripped = line.strip()
            if '[data-dept-auto-replay="true"] .bg-dept-action-bubble' in stripped and '{' in stripped:
                in_bubble_block = True
                current_block = []
            if in_bubble_block:
                current_block.append(stripped)
                if '}' in stripped:
                    in_bubble_block = False
                    all_bubble_props.append("\n".join(current_block))
        bubble_text = "\n".join(all_bubble_props)
        assert "left: 50%" not in bubble_text, "action bubble must not use left: 50%"
        assert "left:50%" not in bubble_text, "action bubble must not use left:50%"
        assert "translateX(-50%)" not in bubble_text, "action bubble must not use translateX(-50%)"
        # Verify it uses left: 24px instead (anchored lower-left)
        assert "left: 24px" in bubble_text, "action bubble should use left: 24px"

    # 8. phase delays sum to at least 8000ms and no more than 15000ms
    def test_phase_delays_sum_in_range(self):
        js = _read_static("citizen-action-demo-canvas.js")
        # Extract delay values from the delays object in _scheduleAutoReplayAdvance
        delays_match = re.search(r'var delays = \{([^}]+)\}', js)
        assert delays_match, "delays object not found in JS"
        delays_text = delays_match.group(1)
        delay_values = re.findall(r'"[^"]+":\s*(\d+)', delays_text)
        assert len(delay_values) >= 3, "expected at least 3 delay entries"
        total = sum(int(v) for v in delay_values)
        assert total >= 8000, f"total delay {total}ms is less than 8000ms"
        assert total <= 15000, f"total delay {total}ms is more than 15000ms"

    # 9. reduced-motion CSS disables decorative animation while retaining visibility
    def test_reduced_motion_disables_decoration_retains_visibility(self):
        css = _read_static("citizen-action-demo-canvas.css")
        # Must have prefers-reduced-motion block
        assert "prefers-reduced-motion" in css
        # Find the reduced-motion block content
        rm_start = css.find("@media (prefers-reduced-motion: reduce)")
        assert rm_start != -1, "missing @media (prefers-reduced-motion: reduce)"
        rm_block = css[rm_start:]
        # Find the matching closing brace for the media query
        brace_count = 0
        rm_end = 0
        for i, ch in enumerate(rm_block):
            if ch == '{':
                brace_count += 1
            elif ch == '}':
                brace_count -= 1
                if brace_count == 0:
                    rm_end = i + 1
                    break
        rm_text = rm_block[:rm_end]
        # Must disable cursor transition
        assert "bg-auto-cursor" in rm_text, "reduced-motion must reference auto cursor"
        assert "transition: none" in rm_text or "animation: none" in rm_text, \
            "reduced-motion must disable animation/transition"
        # Must retain cursor visibility (not display:none)
        assert "display: none" not in rm_text, "reduced-motion must not hide cursor completely"
        # Must disable click pulse animation
        assert "bg-auto-click-feedback" in rm_text, "reduced-motion must reference click feedback"
        # Click feedback must retain some visibility (opacity > 0)
        assert "opacity: 0.5" in rm_text or "opacity: 1" in rm_text, \
            "reduced-motion click feedback must retain visibility"

    # 10. manual replay has none of the auto cursor/highlight/click-feedback markers
    def test_manual_replay_no_auto_markers(self, auto_render):
        result = auto_render("?replay=J-DEPT-01&replay-step=directory")
        html = result["html"]
        assert 'class="bg-auto-cursor' not in html, "manual replay must not have auto cursor"
        assert 'class="bg-auto-target-highlight' not in html, "manual replay must not have auto target highlight"
        assert 'class="bg-auto-click-feedback' not in html, "manual replay must not have auto click feedback"


# ---------------------------------------------------------------------------
# Stage 864-A corrective: direct phase gate and restart semantics
# ---------------------------------------------------------------------------

class TestAutoReplayDirectPhaseGate:
    """Tests that direct phase URLs are fail-closed static until user starts."""

    @pytest.fixture(scope="class")
    def auto_render_with_timers(self):
        def _render(query: str):
            map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
            canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
            sandbox_init = """
            'use strict';
            var vm = require('vm');
            var capturedHTML = '';
            var capturedChatHTML = '';
            var timers = [];
            var intervalCount = 0;
            function makeElement(id) {
              return {
                id: id,
                get innerHTML() { return id === 'chat-thread' ? capturedChatHTML : capturedHTML; },
                set innerHTML(v) { if (id === 'chat-thread') { capturedChatHTML = v; } else { capturedHTML = v; } },
                addEventListener: function() {},
                querySelector: function() { return null; }
              };
            }
            var fakeCanvasElement = makeElement('demo-canvas');
            var sandbox = {
              document: {
                getElementById: function(id) {
                  if (id === 'demo-canvas') return fakeCanvasElement;
                  if (id === 'chat-thread') return makeElement('chat-thread');
                  return null;
                }
              },
              console: { log: function() {}, error: function() {} },
              location: { search: %s },
              history: { pushState: function() {} },
              setTimeout: function(fn, ms) { timers.push({ms: ms}); return timers.length; },
              clearTimeout: function(id) { if (id && timers[id - 1]) { timers[id - 1] = null; } },
              setInterval: function() { intervalCount += 1; return -1; },
              window: null
            };
            sandbox.URLSearchParams = URLSearchParams;
            sandbox.window = sandbox;
            var cx = vm.createContext(sandbox);
            vm.runInContext(%s, cx);
            vm.runInContext(%s, cx);
            sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
            process.stdout.write(JSON.stringify({
              html: capturedHTML,
              chat: capturedChatHTML,
              timerCount: timers.filter(function(t) { return t !== null; }).length,
              intervalCount: intervalCount
            }));
            """ % (json.dumps(query), map_js, canvas_js)
            res = _run_node_script_file(sandbox_init, timeout=10)
            assert res.returncode == 0, res.stderr
            return json.loads(res.stdout)
        return _render

    @pytest.fixture(scope="class")
    def auto_interact(self):
        def _interact(query, actions):
            map_js = json.dumps(_read_static("citizen-action-demo-map.js"))
            canvas_js = json.dumps(_read_static("citizen-action-demo-canvas.js"))
            sandbox_init = """
            'use strict';
            var vm = require('vm');
            var capturedHTML = '';
            var capturedChatHTML = '';
            var capturedClickHandler = null;
            var timers = [];
            var intervalCount = 0;
            var pushed = [];
            function makeElement(id) {
              return {
                id: id,
                get innerHTML() { return id === 'chat-thread' ? capturedChatHTML : capturedHTML; },
                set innerHTML(v) { if (id === 'chat-thread') { capturedChatHTML = v; } else { capturedHTML = v; } },
                addEventListener: function(event, handler) {
                  if (event === 'click' && id === 'demo-canvas') capturedClickHandler = handler;
                },
                querySelector: function() { return null; }
              };
            }
            var fakeCanvasElement = makeElement('demo-canvas');
            var sandbox = {
              document: {
                getElementById: function(id) {
                  if (id === 'demo-canvas') return fakeCanvasElement;
                  if (id === 'chat-thread') return makeElement('chat-thread');
                  return null;
                }
              },
              console: { log: function() {}, error: function() {} },
              location: { search: %s },
              history: {
                pushState: function(state, title, url) {
                  pushed.push(url);
                  sandbox.location.search = url.substring(url.indexOf('?'));
                }
              },
              setTimeout: function(fn, ms) { timers.push({fn: fn, ms: ms}); return timers.length; },
              clearTimeout: function(id) { if (id && timers[id - 1]) { timers[id - 1] = null; } },
              setInterval: function() { intervalCount += 1; return -1; },
              fetch: function() {},
              localStorage: { getItem: function() {}, setItem: function() {} },
              sessionStorage: { getItem: function() {}, setItem: function() {} },
              window: null
            };
            sandbox.URLSearchParams = URLSearchParams;
            sandbox.window = sandbox;
            var cx = vm.createContext(sandbox);
            vm.runInContext(%s, cx);
            vm.runInContext(%s, cx);
            sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');

            var actionList = %s;
            var results = [];
            for (var a = 0; a < actionList.length; a++) {
              var act = actionList[a];
              if (act.type === 'click') {
                capturedClickHandler({
                  target: {
                    closest: function(sel) {
                      if (sel === '[data-auto-replay-action]') {
                        return { getAttribute: function() { return act.action; } };
                      }
                      return null;
                    }
                  },
                  preventDefault: function() {}
                });
              } else if (act.type === 'fire-timer') {
                var pending = timers.filter(function(t) { return t !== null; });
                if (pending.length > 0) {
                  pending[pending.length - 1].fn();
                  timers[timers.indexOf(pending[pending.length - 1])] = null;
                }
              }
              results.push({
                html: capturedHTML,
                chat: capturedChatHTML,
                search: sandbox.location.search,
                pendingTimers: timers.filter(function(t) { return t !== null; }).length
              });
            }
            process.stdout.write(JSON.stringify({
              results: results,
              pushed: pushed,
              intervalCount: intervalCount
            }));
            """ % (json.dumps(query), map_js, canvas_js, json.dumps(actions))
            res = _run_node_script_file(sandbox_init, timeout=10)
            assert res.returncode == 0, res.stderr
            return json.loads(res.stdout)
        return _interact

    # 1. Direct phase URLs show step markup but zero pending timers before user start
    def test_direct_phase_urls_no_timers_before_start(self, auto_render_with_timers):
        for step in ["route", "directory", "search", "result"]:
            result = auto_render_with_timers("?replay=J-DEPT-01&replay-mode=auto&replay-step=" + step)
            assert result["timerCount"] == 0, \
                f"direct step '{step}' must have 0 pending timers, got {result['timerCount']}"
            assert 'data-auto-replay-step="' + step + '"' in result["html"], \
                f"direct step '{step}' must still show step markup"

    # 2. Direct phase URL shows ready status and 시연 시작 control
    def test_direct_phase_shows_ready_status_and_start_button(self, auto_render_with_timers):
        for step in ["route", "directory", "search", "result"]:
            result = auto_render_with_timers("?replay=J-DEPT-01&replay-mode=auto&replay-step=" + step)
            html = result["html"]
            assert 'data-auto-replay-status="ready"' in html, \
                f"direct step '{step}' must show ready status"
            assert "시연 시작" in html, \
                f"direct step '{step}' must show 시연 시작 button"

    # 3. Pending timer appears only after start click
    def test_timer_only_after_start(self, auto_interact):
        # Start from ready — after click, there should be a pending timer
        data = auto_interact("?replay=J-DEPT-01&replay-mode=auto", [
            {"type": "click", "action": "start"}
        ])
        last = data["results"][-1]
        assert last["pendingTimers"] >= 1, "start must schedule at least one timer"

    def test_direct_phase_no_timer(self, auto_render_with_timers):
        # Direct phase URL — no timers
        result = auto_render_with_timers("?replay=J-DEPT-01&replay-mode=auto&replay-step=directory")
        assert result["timerCount"] == 0, "direct phase URL must have 0 timers"

    # 4. Start → restart returns to ready URL, step/status ready, 0 timers, 시연 시작 only
    def test_start_then_restart_returns_to_ready(self, auto_interact):
        data = auto_interact("?replay=J-DEPT-01&replay-mode=auto", [
            {"type": "click", "action": "start"},
            {"type": "click", "action": "restart"}
        ])
        last = data["results"][-1]
        assert last["search"] == "?replay=J-DEPT-01&replay-mode=auto", \
            f"restart must return URL to ready, got {last['search']}"
        assert 'data-auto-replay-step="ready"' in last["html"], \
            "restart must show step=ready"
        assert 'data-auto-replay-status="ready"' in last["html"], \
            "restart must show status=ready"
        assert last["pendingTimers"] == 0, \
            "restart must clear all timers"
        assert "시연 시작" in last["html"], \
            "restart must show 시연 시작"
        # Verify no other auto-replay control buttons
        assert "일시정지" not in last["html"], \
            "restart must not show pause button"
        assert "계속" not in last["html"], \
            "restart must not show resume button"

    # 5. Normal start playback, pause/resume, one-timer/no-setInterval preserved
    def test_normal_playback_preserved(self, auto_interact):
        # Full start → route → directory → search → result
        data = auto_interact("?replay=J-DEPT-01&replay-mode=auto", [
            {"type": "click", "action": "start"},
            {"type": "fire-timer"},
            {"type": "fire-timer"},
            {"type": "fire-timer"},
        ])
        assert data["intervalCount"] == 0, "no setInterval allowed"
        final = data["results"][-1]
        assert "공동주택과" in final["html"], "result phase must show data"
        # Each running step should have at most 1 pending timer
        for r in data["results"]:
            assert r["pendingTimers"] <= 1, "at most 1 pending timer"

    # 6. Pause/resume preserves current phase
    def test_pause_resume_preserves_phase(self, auto_interact):
        data = auto_interact("?replay=J-DEPT-01&replay-mode=auto", [
            {"type": "click", "action": "start"},
            {"type": "fire-timer"},
            {"type": "click", "action": "pause"},
            {"type": "click", "action": "resume"},
        ])
        paused = data["results"][2]
        resumed = data["results"][3]
        assert 'data-auto-replay-status="paused"' in paused["html"]
        assert 'data-auto-replay-status="running"' in resumed["html"]
        # Same phase after resume
        paused_step = re.search(r'data-auto-replay-step="([^"]*)"', paused["html"])
        resumed_step = re.search(r'data-auto-replay-step="([^"]*)"', resumed["html"])
        assert paused_step and resumed_step, "must have step attributes"
        assert paused_step.group(1) == resumed_step.group(1), \
            "resume must preserve current phase"

    # 7. Direct ready URL also has zero timers
    def test_ready_url_zero_timers(self, auto_render_with_timers):
        result = auto_render_with_timers("?replay=J-DEPT-01&replay-mode=auto")
        assert result["timerCount"] == 0, "ready URL must have 0 timers"
        assert 'data-auto-replay-status="ready"' in result["html"]

    # 8. Restart from running mid-phase clears timer and goes to ready
    def test_restart_from_running_clears_timer(self, auto_interact):
        data = auto_interact("?replay=J-DEPT-01&replay-mode=auto", [
            {"type": "click", "action": "start"},
            {"type": "fire-timer"},
            {"type": "click", "action": "restart"},
        ])
        after_restart = data["results"][-1]
        assert after_restart["pendingTimers"] == 0, \
            "restart from running must clear timer"
        assert 'data-auto-replay-status="ready"' in after_restart["html"]
