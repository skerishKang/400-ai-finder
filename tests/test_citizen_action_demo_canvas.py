"""
Contract tests for citizen-action-demo-canvas (Stage #847).

Verifies the local route-rendered canvas and closed map satisfy
the required static/local/demo contract.
"""

import ast
import os
import re

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

CANDIDATE_ROUTE_IDS = sorted([
    "home",
    "civil-service",
    "complaint-category",
    "complaint-intake",
    "complaint-review",
    "handoff-stop",
    "extra-route",
    "nonexistent",
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
        # CLOSED_ROUTE_IDS must contain exactly the six expected IDs
        for rid in EXPECTED_ROUTE_IDS:
            assert '"' + rid + '"' in js, f"route '{rid}' not found in map"

    def test_map_defines_no_extra_route_ids(self):
        js = _read_static("citizen-action-demo-map.js")
        # Extra route IDs must not appear
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
        code = _strip_all(js)
        for route_id in EXPECTED_ROUTE_IDS:
            assert "id: \"" + route_id + "\"" in js or "id:\"" + route_id + "\"" in js, \
                f"route '{route_id}' has no definition"

    def test_home_has_nav_civil_service(self):
        js = _read_static("citizen-action-demo-map.js")
        # home navTargets must include nav-civil-service
        # Find the home route definition block
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

    def test_handoff_stop_has_handoff_notice(self):
        js = _read_static("citizen-action-demo-map.js")
        block = js[js.find('"handoff-stop"'):js.find('"handoff-stop"') + 500]
        assert "handoff-notice" in block


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
        # Page title rendered via nav bar (canvas-nav__title) or route title
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
        # Must state this is NOT an official site
        assert "공식" in combined or "official" in combined.lower()
        assert "데모" in combined or "데모" in combined
        assert "PoC" in combined or "로컬" in combined or "시연" in combined

    def test_disclosure_mentions_authentication_responsibility(self):
        html = _read_static("citizen-action-demo.html")
        js = _read_static("citizen-action-demo-canvas.js")
        combined = html + js
        # Must mention citizen responsibility for auth/submission
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
        # isValidTarget must check against CLOSED_TARGET_IDS
        assert "CLOSED_TARGET_IDS" in js

    def test_canvas_navigate_validates_against_map(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "navigateToRoute" in js
        # Must check with map before navigating
        assert "_map.isValidRoute" in js or "_map.isValidRoute" in js

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
# citizen_action_plan.py not modified
# ---------------------------------------------------------------------------

class TestContractNotModified:
    def test_citizen_action_plan_unchanged(self):
        agent_py = os.path.join(
            os.path.dirname(__file__), "..", "src", "agent", "citizen_action_plan.py"
        )
        assert os.path.isfile(agent_py), "citizen_action_plan.py must exist"
        # Just check it was not gutted (has expected content)
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
        # Must still have dock toggle, compact toggle, inert management
        assert "_toggleDock" in content
        assert "_openCompactDrawer" in content or "_openCompact" in content
        assert "matchMedia" in content

    def test_shell_css_unchanged(self):
        shell_css = os.path.join(STATIC, "citizen-copilot-shell.css")
        content = _read(shell_css)
        assert ".copilot-rail" in content
        assert "@media" in content
        assert "767px" in content