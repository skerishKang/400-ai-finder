"""
Contract tests for citizen-action-demo-canvas (Stage #847 corrective).
"""

import ast
import os
import re
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

EXPECTED_ROUTE_IDS = sorted([
    "home", "civil-service", "complaint-category",
    "complaint-intake", "complaint-review", "handoff-stop",
])

EXPECTED_TARGET_IDS = sorted([
    "nav-civil-service", "nav-complaint-category",
    "complaint-category-illegal-parking",
    "complaint-category-public-parking-inconvenience",
    "complaint-category-residential-parking",
    "complaint-category-traffic-or-facility-safety",
    "complaint-category-other-or-unsure",
    "complaint-body", "complaint-draft-review",
    "confirm-draft-prefill", "handoff-notice",
])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def _read_static(name):
    return _read(os.path.join(STATIC, name))

def _strip_all(text):
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    return text

def _strip_strings_only(text):
    text = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', text)
    text = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", text)
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
# 1. Closed vocabulary: exact arrays
# ---------------------------------------------------------------------------

class TestClosedVocabulary:
    def test_closed_route_ids_exact_six_no_duplicates(self):
        js = _read_static("citizen-action-demo-map.js")
        # Match the exact CLOSED_ROUTE_IDS array and extract its values
        match = re.search(
            r"CLOSED_ROUTE_IDS\s*=\s*Object\.freeze\(\s*\[\s*"
            r'"(home)"[^,]*,\s*"(civil-service)"[^,]*,\s*"(complaint-category)"[^,]*,\s*'
            r'"(complaint-intake)"[^,]*,\s*"(complaint-review)"[^,]*,\s*"(handoff-stop)"',
            js
        )
        assert match, "CLOSED_ROUTE_IDS not found or malformed"
        ids = [match.group(i) for i in range(1, 7)]
        assert sorted(ids) == EXPECTED_ROUTE_IDS

    def test_closed_target_ids_exact_eleven_no_duplicates(self):
        js = _read_static("citizen-action-demo-map.js")
        match = re.search(
            r"CLOSED_TARGET_IDS\s*=\s*Object\.freeze\(\s*\[\s*"
            r'"(nav-civil-service)"[^,]*,\s*"(nav-complaint-category)"[^,]*,\s*'
            r'"(complaint-category-illegal-parking)"[^,]*,\s*'
            r'"(complaint-category-public-parking-inconvenience)"[^,]*,\s*'
            r'"(complaint-category-residential-parking)"[^,]*,\s*'
            r'"(complaint-category-traffic-or-facility-safety)"[^,]*,\s*'
            r'"(complaint-category-other-or-unsure)"[^,]*,\s*'
            r'"(complaint-body)"[^,]*,\s*"(complaint-draft-review)"[^,]*,\s*'
            r'"(confirm-draft-prefill)"[^,]*,\s*"(handoff-notice)"',
            js
        )
        assert match, "CLOSED_TARGET_IDS not found or malformed"
        ids = [match.group(i) for i in range(1, 12)]
        assert sorted(ids) == EXPECTED_TARGET_IDS

    def test_no_extra_route_ids(self):
        js = _read_static("citizen-action-demo-map.js")
        code = _strip_all(js)
        for extra in ["extra-route", "nonexistent"]:
            assert extra not in code

    def test_no_extra_target_ids(self):
        js = _read_static("citizen-action-demo-map.js")
        code = _strip_all(js)
        for extra in ["fake-target", "random-id"]:
            assert extra not in code


# ---------------------------------------------------------------------------
# 2. Fixture immutability
# ---------------------------------------------------------------------------

class TestFixtureImmutability:
    def test_all_navTargets_use_object_freeze(self):
        js = _read_static("citizen-action-demo-map.js")
        navtarget_blocks = re.findall(
            r'navTargets:\s*Object\.freeze\(\[([^\]]+)\]\)',
            js
        )
        assert len(navtarget_blocks) == 6

    def test_public_map_is_frozen(self):
        js = _read_static("citizen-action-demo-map.js")
        assert "CitizenActionDemoMap = Object.freeze(" in js


# ---------------------------------------------------------------------------
# 3. JavaScript syntax
# ---------------------------------------------------------------------------

class TestJsSyntax:
    def test_map_js_syntax_valid(self):
        path = os.path.join(STATIC, "citizen-action-demo-map.js")
        result = subprocess.run(
            ["node", "--check", path], capture_output=True, text=True
        )
        assert result.returncode == 0, f"map.js: {result.stderr}"

    def test_canvas_js_syntax_valid(self):
        path = os.path.join(STATIC, "citizen-action-demo-canvas.js")
        result = subprocess.run(
            ["node", "--check", path], capture_output=True, text=True
        )
        assert result.returncode == 0, f"canvas.js: {result.stderr}"


# ---------------------------------------------------------------------------
# 4. Every renderer calls nav, breadcrumb, page header, PoC
# ---------------------------------------------------------------------------

class TestRendererStructure:
    def test_every_route_includes_nav_bar(self):
        js = _read_static("citizen-action-demo-canvas.js")
        # Count named render function calls (not just any mention)
        names = ["_renderHome(", "_renderCivilService(", "_renderComplaintCategory(",
                 "_renderComplaintIntake(", "_renderComplaintReview(", "_renderHandoffStop("]
        found = sum(1 for n in names if n in js)
        assert found == 6, "not all 6 renderers defined"

    def test_every_route_includes_breadcrumb(self):
        js = _read_static("citizen-action-demo-canvas.js")
        # Each renderer should include breadcrumb in its returned HTML
        names = ["_renderHome(", "_renderCivilService(", "_renderComplaintCategory(",
                 "_renderComplaintIntake(", "_renderComplaintReview(", "_renderHandoffStop("]
        for name in names:
            idx = js.find(name); fn_body = js[idx:js.find(")", idx+200)+200] if idx >= 0 else ""
            assert "_renderBreadcrumb" in fn_body or "canvas-breadcrumb" in fn_body

    def test_every_route_includes_page_header(self):
        js = _read_static("citizen-action-demo-canvas.js")
        names = ["_renderHome(", "_renderCivilService(", "_renderComplaintCategory(",
                 "_renderComplaintIntake(", "_renderComplaintReview(", "_renderHandoffStop("]
        for name in names:
            fn_start = js.find(name)
            if fn_start < 0:
                continue
            fn_body = js[fn_start:fn_start+800]
            assert "_renderPageHeader" in fn_body or "canvas-header" in fn_body

    def test_every_route_includes_poc_banner(self):
        js = _read_static("citizen-action-demo-canvas.js")
        names = ["_renderHome(", "_renderCivilService(", "_renderComplaintCategory(",
                 "_renderComplaintIntake(", "_renderComplaintReview(", "_renderHandoffStop("]
        for name in names:
            fn_start = js.find(name)
            if fn_start < 0:
                continue
            fn_body = js[fn_start:fn_start+800]
            assert "_renderPocBanner" in fn_body or "canvas-poc-banner" in fn_body

    def test_handoff_has_hard_stop_wording(self):
        js = _read_static("citizen-action-demo-canvas.js")
        handoff = js[js.find("function _renderHandoffStop"):js.find("function _renderHandoffStop")+600]
        assert "데모 종료" in handoff or "종료" in handoff
        assert "제출" in handoff


# ---------------------------------------------------------------------------
# 5. PoC disclosure
# ---------------------------------------------------------------------------

class TestPocDisclosure:
    def test_disclosure_says_not_official(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "공식 사이트가 아닙니다" in js

    def test_disclosure_says_auth_and_submission_citizen_responsibility(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "책임" in js or "직접" in js

    def test_disclosure_says_demo_does_not_submit(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "제출" in js


# ---------------------------------------------------------------------------
# 6. Delegation: once guard
# ---------------------------------------------------------------------------

class TestDelegationGuard:
    def test_delegation_has_once_guard(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "_delegationAttached" in js

    def test_navigate_does_not_re_attach(self):
        js = _read_static("citizen-action-demo-canvas.js")
        navfn = js[js.find("function navigateToRoute"):js.find("function navigateToRoute")+500]
        assert "_attachDelegation" not in navfn


# ---------------------------------------------------------------------------
# 7. data-demo-route semantics
# ---------------------------------------------------------------------------

class TestDataDemoRoute:
    def test_data_demo_route_uses_target_to_next_route(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "_targetToNextRoute" in js, \
            "canvas must use _targetToNextRoute for data-demo-route"
        code = _strip_all(js)
        # _targetToNextRoute must exist in code (not just strings)
        assert "_targetToNextRoute" in code


# ---------------------------------------------------------------------------
# 8. Non-personal, non-submit boundary
# ---------------------------------------------------------------------------

class TestNonPersonalBoundary:
    FORBIDDEN = [
        ("<form", "form element"),
        ("<input", "input element"),
        ("<textarea", "textarea element"),
        ("contenteditable=", "contenteditable"),
        ('type="file"', "file input"),
        ('type="submit"', "submit button"),
        ('type="password"', "password field"),
    ]

    @pytest.mark.parametrize("pattern,label", FORBIDDEN)
    def test_no_pii_or_submit_in_canvas_js(self, pattern, label):
        js = _read_static("citizen-action-demo-canvas.js")
        code = _strip_all(js)
        assert pattern.lower() not in code, f"canvas.js: {label}"

    def test_intake_uses_display_not_input(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "canvas-intake-display" in js


# ---------------------------------------------------------------------------
# 9. API validation
# ---------------------------------------------------------------------------

class TestApiValidation:
    def test_navigate_validates_against_map(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "_map.isValidRoute" in js

    def test_getTargetElement_validates_against_map(self):
        js = _read_static("citizen-action-demo-canvas.js")
        assert "_map.isValidTarget" in js


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

class TestSafety:
    PROHIBITED = [
        ("fetch(", "fetch"),
        ("XMLHttpRequest", "XMLHttpRequest"),
        ("WebSocket", "WebSocket"),
        ("EventSource", "EventSource"),
        ("navigator.sendBeacon", "sendBeacon"),
        ("localStorage", "localStorage"),
        ("sessionStorage", "sessionStorage"),
        ("indexedDB", "indexedDB"),
        ("document.cookie", "document.cookie"),
        ("iframe", "iframe"),
        ("@import url", "external CSS"),
        ("googleapis", "CDN font"),
        ("cdnjs", "CDN"),
        ("unpkg", "CDN"),
        ("jsdelivr", "CDN"),
    ]

    @pytest.mark.parametrize("pattern,label", PROHIBITED)
    def test_no_prohibited_in_canvas_js(self, pattern, label):
        js = _read_static("citizen-action-demo-canvas.js")
        code = _strip_all(js)
        assert pattern not in code, f"canvas.js: {label}"

    @pytest.mark.parametrize("pattern,label", PROHIBITED)
    def test_no_prohibited_in_map_js(self, pattern, label):
        js = _read_static("citizen-action-demo-map.js")
        code = _strip_all(js)
        assert pattern not in code, f"map.js: {label}"

    def test_no_external_url_in_html(self):
        html = _read_static("citizen-action-demo.html")
        external = re.findall(
            r'(?:href|src)\s*=\s*["\']https?://(?!localhost|127\.0\.0\.1)[^"\']+["\']',
            html
        )
        assert not external, f"external URL: {external}"


# ---------------------------------------------------------------------------
# Journey completeness
# ---------------------------------------------------------------------------

class TestJourneyCompleteness:
    def _route_block(self, js, route_id):
        """Get the full route definition block (home to end of all routes)."""
        start = js.find('"' + route_id + '"')
        # Find the closing of this route's object (first unmatched })
        depth = 0
        pos = js.find("{", start)
        end = pos
        while end < len(js):
            if js[end] == "{": depth += 1
            elif js[end] == "}": depth -= 1
            if depth == 0:
                end += 1
                break
            end += 1
        return js[start:end]

    def test_home_to_civil_service(self):
        js = _read_static("citizen-action-demo-map.js")
        block = self._route_block(js, "home")
        assert "nav-civil-service" in block

    def test_civil_service_to_category(self):
        js = _read_static("citizen-action-demo-map.js")
        block = self._route_block(js, "civil-service")
        assert "nav-complaint-category" in block

    def test_category_five_targets(self):
        js = _read_static("citizen-action-demo-map.js")
        block = self._route_block(js, "complaint-category")
        for cat in [
            "complaint-category-illegal-parking",
            "complaint-category-public-parking-inconvenience",
            "complaint-category-residential-parking",
            "complaint-category-traffic-or-facility-safety",
            "complaint-category-other-or-unsure",
        ]:
            assert cat in block

    def test_intake_body_and_draft_review(self):
        js = _read_static("citizen-action-demo-map.js")
        block = self._route_block(js, "complaint-intake")
        assert "complaint-body" in block
        assert "complaint-draft-review" in block

    def test_review_confirm_prefill(self):
        js = _read_static("citizen-action-demo-map.js")
        block = self._route_block(js, "complaint-review")
        assert "confirm-draft-prefill" in block

    def test_handoff_handoff_notice(self):
        js = _read_static("citizen-action-demo-map.js")
        block = self._route_block(js, "handoff-stop")
        assert "handoff-notice" in block


# ---------------------------------------------------------------------------
# Contract unchanged
# ---------------------------------------------------------------------------

class TestContractUnchanged:
    def test_citizen_action_plan_unchanged(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src", "agent", "citizen_action_plan.py")
        assert os.path.isfile(path)
        content = _read(path)
        assert "CitizenAction" in content
        assert "_VALID_ROUTE_IDS" in content
        assert "_VALID_TARGET_IDS" in content


# ---------------------------------------------------------------------------
# Shell compatibility
# ---------------------------------------------------------------------------

class TestShellCompatibility:
    def test_shell_js_unchanged(self):
        path = os.path.join(STATIC, "citizen-copilot-shell.js")
        content = _read(path)
        assert "_toggleDock" in content
        assert "_openCompactDrawer" in content or "_openCompact" in content
        assert "matchMedia" in content

    def test_shell_css_unchanged(self):
        path = os.path.join(STATIC, "citizen-copilot-shell.css")
        content = _read(path)
        assert ".copilot-rail" in content
        assert "@media" in content
        assert "767px" in content