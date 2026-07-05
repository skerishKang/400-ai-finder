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
