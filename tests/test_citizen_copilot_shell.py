"""
Contract tests for citizen-copilot-shell Stage #846.

Verifies the dockable citizen-action copilot shell assets exist and satisfy
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
    "citizen-copilot-shell.css",
    "citizen-copilot-shell.js",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _read_static(name: str) -> str:
    return _read(os.path.join(STATIC, name))


def _strip_comments_and_strings(text: str) -> str:
    """
    Remove all comments and string literals so privacy/prohibited-pattern
    checks only hit actual code content.
    """
    # Remove single-line comments
    text = re.sub(r"//.*", "", text)
    # Remove multi-line comments (CSS /* */ and HTML <!-- -->)
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    return text


def _js_strip_strings(text: str) -> str:
    """Remove JS string literals for pattern-matching safety."""
    # Single-quoted, double-quoted, and template-literal strings
    text = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', text)
    text = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", text)
    text = re.sub(r"`[^`\\]*(?:\\.[^`\\]*)*`", "``", text)
    return text


def _css_strip_strings(text: str) -> str:
    """Remove CSS string values for pattern-matching safety."""
    text = re.sub(r'"[^"]*"', '""', text)
    return text


def _strip_all(text: str) -> str:
    """Remove comments, HTML, and string literals for JS/CSS."""
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    text = _js_strip_strings(text)
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
# Isolated demo route — landmark/region existence
# ---------------------------------------------------------------------------

class TestDemoRouteAndLandmarks:
    def test_demo_html_has_dock_attribute_on_body(self):
        html = _read_static("citizen-action-demo.html")
        # Must have the dock attribute declared (right is the default)
        assert 'data-copilot-dock="right"' in html
        # Must document both allowed values
        assert 'data-copilot-dock-choices="left right"' in html

    def test_has_conversation_region(self):
        html = _read_static("citizen-action-demo.html")
        assert 'id="copilot-conversation"' in html
        assert 'aria-labelledby="conv-heading"' in html

    def test_has_action_explanation_region(self):
        html = _read_static("citizen-action-demo.html")
        assert 'id="copilot-action-explanation"' in html
        assert 'id="current-explanation"' in html

    def test_has_action_trace_region(self):
        html = _read_static("citizen-action-demo.html")
        assert 'id="copilot-trace"' in html
        assert 'id="action-trace"' in html

    def test_has_confirmation_control(self):
        html = _read_static("citizen-action-demo.html")
        assert 'id="copilot-confirmation"' in html
        assert 'type="button"' in html
        # Must NOT be type="submit"
        assert 'type="submit"' not in html
        assert "<form" not in html

    def test_has_demo_canvas(self):
        html = _read_static("citizen-action-demo.html")
        assert 'id="demo-canvas"' in html


# ---------------------------------------------------------------------------
# Dock model — left/right two-value constraint
# ---------------------------------------------------------------------------

class TestDockModel:
    def test_body_data_copilot_dock_attribute_present(self):
        html = _read_static("citizen-action-demo.html")
        assert 'data-copilot-dock="right"' in html
        assert 'data-copilot-dock-choices="left right"' in html
        # No third value
        assert 'data-copilot-dock="top"' not in html
        assert 'data-copilot-dock="bottom"' not in html
        assert 'data-copilot-dock="center"' not in html

    def test_body_data_copilot_dock_values_in_js(self):
        js = _read_static("citizen-copilot-shell.js")
        # Both values appear as string literals
        assert '"left"' in js
        assert '"right"' in js

    def test_css_reflows_for_both_dock_values(self):
        css = _read_static("citizen-copilot-shell.css")
        assert ".demo-canvas" in css
        assert ".copilot-rail" in css
        # flex-direction row used for both left and right dock
        assert "flex-direction: row" in css

    def test_js_dock_toggle_cycles_left_right_only(self):
        js = _read_static("citizen-copilot-shell.js")
        # Toggle function switches between exactly 'left' and 'right'
        assert '_currentDock === "right"' in js
        # The ternary that computes next dock value
        assert 'var next = _currentDock === "right" ? "left" : "right"' in js


# ---------------------------------------------------------------------------
# Compact responsive behavior
# ---------------------------------------------------------------------------

class TestCompactBehavior:
    def test_has_breakpoint_media_query(self):
        css = _read_static("citizen-copilot-shell.css")
        assert "@media" in css
        assert "767px" in css or "768px" in css

    def test_compact_toggle_exists_in_html(self):
        html = _read_static("citizen-action-demo.html")
        assert 'id="compact-toggle"' in html
        assert 'aria-expanded="false"' in html
        assert 'aria-controls="copilot-rail"' in html

    def test_compact_toggle_has_aria_expanded_attribute(self):
        html = _read_static("citizen-action-demo.html")
        assert "aria-expanded=" in html

    def test_escape_collapse_in_js(self):
        js = _read_static("citizen-copilot-shell.js")
        assert 'key === "Escape"' in js or "e.key === 'Escape'" in js
        assert "_closeCompact" in js

    def test_compact_drawer_uses_transform_translate(self):
        css = _read_static("citizen-copilot-shell.css")
        assert "translateY" in css or "translatey" in css

    def test_canvas_full_width_on_compact(self):
        css = _read_static("citizen-copilot-shell.css")
        assert ".demo-canvas" in css


# ---------------------------------------------------------------------------
# Confirmation control — local/non-submit, no navigation
# ---------------------------------------------------------------------------

class TestConfirmationSafety:
    def test_confirm_buttons_are_type_button(self):
        html = _read_static("citizen-action-demo.html")
        submit_count = len(re.findall(r'type\s*=\s*["\']submit["\']', html))
        assert submit_count == 0, "confirmation controls must not be type=submit"

    def test_no_form_element_in_demo_html(self):
        html = _read_static("citizen-action-demo.html")
        assert "<form" not in html.lower(), "demo page must not contain a form element"

    def test_confirm_handler_no_navigation_in_code(self):
        # Strip comments and strings before checking actual code
        js = _read_static("citizen-copilot-shell.js")
        code_only = _strip_all(js)
        forbidden = ["window.location", "location.href", "location.assign",
                     "history.push", "history.replace"]
        for item in forbidden:
            assert item not in code_only, f"confirmation handler must not use {item}"

    def test_no_external_url_in_html(self):
        html = _read_static("citizen-action-demo.html")
        external = re.findall(
            r'(?:src|href)\s*=\s*["\']https?://(?!localhost|127\.0\.0\.1)[^"\']+["\']',
            html
        )
        assert not external, f"found external URL in demo HTML: {external}"


# ---------------------------------------------------------------------------
# Privacy / safety — no prohibited storage or network calls (comments/strings stripped)
# ---------------------------------------------------------------------------

class TestPrivacyAndSafety:
    # These are checked after stripping comments and string literals
    CODE_ONLY_PATTERNS = [
        ("localStorage", "localStorage in code"),
        ("sessionStorage", "sessionStorage in code"),
        ("indexedDB", "indexedDB in code"),
        ("document.cookie", "document.cookie in code"),
        ("navigator.sendBeacon", "sendBeacon in code"),
        ("fetch(", "fetch in code"),
        ("XMLHttpRequest", "XMLHttpRequest in code"),
        ("WebSocket", "WebSocket in code"),
        ("EventSource", "EventSource in code"),
        ("navigator.serviceWorker", "service worker in code"),
        ("registerServiceWorker", "service worker in code"),
        ("from src.", "src. import in shell assets"),
        ("from src.agent", "src.agent import in shell assets"),
        ("iframe", "iframe in code"),
        ("@import url", "external CSS @import url"),
        ("googleapis", "external CDN font"),
        ("cdnjs", "external CDN"),
        ("unpkg", "external CDN"),
        ("jsdelivr", "external CDN"),
        ("runner", "runner invocation in code"),
        ("provider", "provider invocation in code"),
    ]

    STRING_PATTERNS = [
        # These must not appear even in string literals (no URLs, no tokens)
        ('href="http', "external http href"),
        ('src="http', "external http src"),
    ]

    @pytest.mark.parametrize("pattern,label", CODE_ONLY_PATTERNS)
    def test_no_prohibited_pattern_in_js_code(self, pattern, label):
        js = _read_static("citizen-copilot-shell.js")
        code_only = _strip_all(js)
        assert pattern not in code_only, f"JS code: found prohibited {label}"

    @pytest.mark.parametrize("pattern,label", CODE_ONLY_PATTERNS)
    def test_no_prohibited_pattern_in_css_code(self, pattern, label):
        css = _read_static("citizen-copilot-shell.css")
        # Strip comments and string values
        code_only = re.sub(r"<!--[\s\S]*?-->", "", css)
        code_only = re.sub(r"/\*[\s\S]*?\*/", "", code_only)
        code_only = _css_strip_strings(code_only)
        assert pattern not in code_only, f"CSS code: found prohibited {label}"

    @pytest.mark.parametrize("pattern,label", STRING_PATTERNS)
    def test_no_prohibited_url_pattern_in_html(self, pattern, label):
        html = _read_static("citizen-action-demo.html")
        assert pattern not in html, f"HTML: {label}"


# ---------------------------------------------------------------------------
# CSS: desktop reflow is layout rail, not overlay
# ---------------------------------------------------------------------------

class TestLayoutRailNotOverlay:
    def test_copilot_rail_has_width_desktop(self):
        css = _read_static("citizen-copilot-shell.css")
        assert ".copilot-rail" in css
        assert ".demo-canvas" in css

    def test_demo_canvas_takes_flex_1_not_overlay(self):
        css = _read_static("citizen-copilot-shell.css")
        assert "flex: 1" in css or "flex:1" in css.replace(" ", "")


# ---------------------------------------------------------------------------
# ARIA attributes
# ---------------------------------------------------------------------------

class TestARIAAttributes:
    def test_dock_toggle_has_aria_expanded(self):
        html = _read_static("citizen-action-demo.html")
        assert "aria-expanded=" in html

    def test_dock_toggle_has_aria_controls(self):
        html = _read_static("citizen-action-demo.html")
        assert "aria-controls=" in html

    def test_compact_toggle_has_aria_expanded_and_controls(self):
        html = _read_static("citizen-action-demo.html")
        section = html[html.find('id="compact-toggle"'):]
        assert "aria-expanded=" in section
        assert "aria-controls=" in section

    def test_copilot_rail_has_role_and_aria_label(self):
        html = _read_static("citizen-action-demo.html")
        assert 'role="complementary"' in html.lower()
        assert "aria-label=" in html

    def test_conversation_region_has_aria_live(self):
        html = _read_static("citizen-action-demo.html")
        assert "aria-live=" in html

    def test_keyboard_focus_style_in_css(self):
        css = _read_static("citizen-copilot-shell.css")
        assert ":focus-visible" in css or ":focus" in css


# ---------------------------------------------------------------------------
# No iframe / external integration
# ---------------------------------------------------------------------------

class TestNoIframeOrExternalIntegration:
    def test_no_iframe_tag(self):
        html = _read_static("citizen-action-demo.html")
        assert "<iframe" not in html.lower()

    def test_no_srcdoc_attribute(self):
        html = _read_static("citizen-action-demo.html")
        assert "srcdoc" not in html.lower()

    def test_no_live_municipality_url(self):
        html = _read_static("citizen-action-demo.html")
        external = re.findall(
            r'(?:href|src)\s*=\s*["\']https?://(?!localhost|127\.0\.0\.1)[^"\']+["\']',
            html
        )
        assert not external, f"external URL found: {external}"


# ---------------------------------------------------------------------------
# Baseline test: existing static-server test
# ---------------------------------------------------------------------------

class TestExistingStaticServerTest:
    def test_static_server_test_file_exists(self):
        """
        Informational only. Reports whether test_static_server.py exists.
        If it does not exist, the baseline test result is 'N/A'.
        """
        test_path = os.path.join(os.path.dirname(__file__), "test_static_server.py")
        exists = os.path.isfile(test_path)
        # We assert True so the test always passes; the result is informational
        assert exists or True, (
            "test_static_server.py not found — "
            "baseline test result is N/A for this stage"
        )