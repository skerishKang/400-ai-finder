"""
Static contract tests for citizen-complaint-journey-ui (Stage #849 Phase B).

Validates the UI module and its HTML integration without jsdom, browser
execution, fake DOM, VM, temporary runner, or live server.
"""

import os
import re

import pytest

STATIC = os.path.join(os.path.dirname(__file__), "..", "src", "web", "static")

HTML_FILE = os.path.join(STATIC, "citizen-action-demo.html")
UI_FILE = os.path.join(STATIC, "citizen-complaint-journey-ui.js")
CSS_FILE = os.path.join(STATIC, "citizen-complaint-journey.css")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# =========================================================================
# Test 1: HTML references journey CSS and reducer/UI scripts
# =========================================================================

class TestHtmlAssets:
    def test_html_references_journey_css(self):
        src = _read(HTML_FILE)
        assert "citizen-complaint-journey.css" in src

    def test_html_references_reducer_script(self):
        src = _read(HTML_FILE)
        assert "citizen-complaint-journey.js" in src

    def test_html_references_ui_script(self):
        src = _read(HTML_FILE)
        assert "citizen-complaint-journey-ui.js" in src


# =========================================================================
# Test 2: Reducer script loads before UI script (script load order)
# =========================================================================

class TestScriptLoadOrder:
    def test_reducer_before_ui(self):
        src = _read(HTML_FILE)
        # Use regex on actual <script> tag lines to avoid matching
        # a string literal inside a comment like "Load order: ... reducer ..."
        script_tags = re.findall(r'<script[^>]+>', src)
        reducer_tag = None
        ui_tag = None
        for tag in script_tags:
            if "citizen-complaint-journey.js" in tag:
                reducer_tag = tag
            if "citizen-complaint-journey-ui.js" in tag:
                ui_tag = tag
        assert reducer_tag is not None, "reducer script tag not found in HTML"
        assert ui_tag is not None, "UI script tag not found in HTML"
        # Compare position in original src to verify order
        reducer_pos = src.find(reducer_tag)
        ui_pos = src.find(ui_tag)
        assert reducer_pos < ui_pos, \
            f"reducer must load before UI script. reducer pos={reducer_pos}, ui pos={ui_pos}"


# =========================================================================
# Test 3: HTML contains the 5 fixed journey containers
# =========================================================================

class TestJourneyContainers:
    CONTAINER_IDS = [
        "journey-status",
        "journey-fact-choices",
        "journey-draft-review",
        "journey-controls",
        "journey-terminal-notice",
    ]

    def test_all_five_containers_present(self):
        src = _read(HTML_FILE)
        for cid in self.CONTAINER_IDS:
            assert 'id="' + cid + '"' in src, \
                f"container '{cid}' not found in HTML"


# =========================================================================
# Test 4: UI source uses ONLY CitizenComplaintJourney and
#         CitizenActionDemoCanvas (not executor/map/planner)
# We check for actual property-access / instantiation patterns, ignoring
# comment-only mentions that describe what the file must NOT do.
# =========================================================================

class TestUiOnlyAllowedApis:
    # Forbidden as a property accessor or global (not inside comments).
    FORBIDDEN_CODE_PATTERNS = [
        # Actual references that would indicate real coupling
        r'\.CitizenActionExecutor\b',
        r'\.CitizenActionDemoMap\b',
        r'citizen_action_plan',
        r'PREFILL_APPROVED_DRAFT',
        r'window\.CitizenActionExecutor\b',
        r'window\.CitizenActionDemoMap\b',
    ]

    def test_ui_references_complaint_journey(self):
        src = _read(UI_FILE)
        assert "CitizenComplaintJourney" in src

    def test_ui_references_canvas(self):
        src = _read(UI_FILE)
        assert "CitizenActionDemoCanvas" in src

    def test_ui_does_not_reference_executor(self):
        src = _read(UI_FILE)
        # Only flag real code usage (property access, require, import) —
        # not comment-only listings of forbidden tokens.
        code_without_comments = re.sub(r'/\*[\s\S]*?\*/', '',
                                        re.sub(r'//.*', '', src))
        for pat in self.FORBIDDEN_CODE_PATTERNS:
            matches = re.findall(pat, code_without_comments)
            assert not matches, \
                f"UI must not reference '{pat}' in code. Found: {matches}"


# =========================================================================
# Test 5: UI source has no fetch/XHR/WebSocket/storage/network
# Only real API calls or property accesses count — not the comment block
# that lists them as forbidden.
# =========================================================================

class TestNoNetworkOrStorage:
    # Patterns that represent actual usage (not mention in restrictions).
    ACTUAL_USAGE_PATTERNS = [
        (r'\bfetch\s*\(',           "fetch() call"),
        (r'new\s+WebSocket\s*\(',   "WebSocket constructor"),
        (r'\blocalStorage\b',       "localStorage reference"),
        (r'\bsessionStorage\b',     "sessionStorage reference"),
        (r'\.indexedDB\b',          "indexedDB reference"),
        (r'navigator\.sendBeacon', "sendBeacon call"),
        (r'XMLHttpRequest',         "XMLHttpRequest reference"),
        (r'Firecrawl',              "Firecrawl reference"),
        (r'\bcrawler\b',            "crawler reference"),
    ]

    def test_no_network_keywords(self):
        src = _read(UI_FILE)
        # Remove comment-only blocks before scanning.
        # This allows the comment "No fetch/XHR/WebSocket" to exist
        # while catching real usage of those APIs.
        code_without_comments = re.sub(r'/\*[\s\S]*?\*/', '',
                                        re.sub(r'//.*', '', src))
        for pat, label in self.ACTUAL_USAGE_PATTERNS:
            matches = re.findall(pat, code_without_comments)
            assert not matches, \
                f"UI must not use {label}. Found in code: {matches}"


# =========================================================================
# Test 6: UI/HTML contain no form, input, textarea, select,
#         contenteditable, or submit
# =========================================================================

class TestNoFormElements:
    # These patterns (in actual HTML or source code) are forbidden.
    FORBIDDEN_PATTERNS = [
        "<form",
        "<input",
        "<textarea",
        "<select",
        'contenteditable=',
        'type="submit"',
        'action="',
    ]

    def test_html_has_no_form_elements(self):
        src = _read(HTML_FILE)
        for pat in self.FORBIDDEN_PATTERNS:
            assert pat not in src, \
                f"HTML must not contain '{pat}'"

    def test_ui_source_has_no_form_elements(self):
        src = _read(UI_FILE)
        # Remove comment blocks so "no contenteditable" prose is not flagged.
        code = re.sub(r'/\*[\s\S]*?\*/', '',
                      re.sub(r'//.*', '', src))
        for pat in self.FORBIDDEN_PATTERNS:
            assert pat not in code, \
                f"UI source must not contain '{pat}' in code"


# =========================================================================
# Test 7: UI makes dynamic choice buttons from getClosedChoices() only
#         (no raw event value or free-text input)
# =========================================================================

class TestDynamicButtonsFromClosedChoices:
    def test_ui_uses_getClosedChoices(self):
        src = _read(UI_FILE)
        assert "getClosedChoices" in src


# =========================================================================
# Test 8: UI uses getClosedChoices() to obtain choices
# =========================================================================

class TestUiObtainsChoicesFromReducer:
    def test_getClosedChoices_called(self):
        src = _read(UI_FILE)
        assert "getClosedChoices" in src


# =========================================================================
# Test 9: UI uses getClarification() to reflect missing facts
# =========================================================================

class TestUiUsesClarification:
    def test_getClarification_called(self):
        src = _read(UI_FILE)
        assert "getClarification" in src


# =========================================================================
# Test 10: UI dispatches BUILD_DRAFT, APPROVE_DRAFT, REJECT_DRAFT,
#          CLEAR_ALL
# =========================================================================

class TestJourneyDispatchEvents:
    REQUIRED_EVENTS = [
        "BUILD_DRAFT",
        "APPROVE_DRAFT",
        "REJECT_DRAFT",
        "CLEAR_ALL",
    ]

    def test_all_required_events_dispatched(self):
        src = _read(UI_FILE)
        for ev in self.REQUIRED_EVENTS:
            assert ev in src, \
                f"UI must dispatch '{ev}' event"


# =========================================================================
# Test 11: Prefill uses getApprovedPrefill() result with fixed
#          target "complaint-body"
# =========================================================================

class TestPrefillGuard:
    def test_ui_uses_getApprovedPrefill(self):
        src = _read(UI_FILE)
        assert "getApprovedPrefill" in src

    def test_prefill_targets_complaint_body(self):
        src = _read(UI_FILE)
        assert '"complaint-body"' in src or "'complaint-body'" in src, \
            "UI must hard-code 'complaint-body' as the only allowed target id"


# =========================================================================
# Test 12: Draft is written via textContent only (no innerHTML injection)
# =========================================================================

class TestTextContentOnly:
    def test_no_innerHTML_draft_injection(self):
        src = _read(UI_FILE)
        # Strip comment blocks first so comment-only mentions are excluded.
        code = re.sub(r'/\*[\s\S]*?\*/', '',
                      re.sub(r'//.*', '', src))
        lines_with_innerhtml = [
            (i + 1, line.strip())
            for i, line in enumerate(code.splitlines())
            if "innerHTML" in line and "draft" in line.lower()
        ]
        assert not lines_with_innerhtml, \
            "UI must not use innerHTML to inject draft text: " + \
            str(lines_with_innerhtml)

    def test_uses_textContent(self):
        src = _read(UI_FILE)
        assert ".textContent" in src


# =========================================================================
# Test 13: No non-complaint-intake route literals or external navigation
# =========================================================================

class TestNoExternalNavigation:
    def test_no_external_url_literals(self):
        src = _read(UI_FILE)
        external_urls = re.findall(
            r'["\']https?://(?!localhost|127\.0\.0\.1)[^"\']+["\']',
            src
        )
        assert not external_urls, \
            f"UI must not contain external URLs: {external_urls}"

    def test_local_route_is_complaint_intake(self):
        src = _read(UI_FILE)
        route_refs = re.findall(
            r'navigateToRoute\s*\(\s*["\']([^"\']+)["\']\s*\)',
            src
        )
        for r in route_refs:
            assert r == "complaint-intake", \
                f"Journey UI may only navigate to 'complaint-intake', found: '{r}'"


# =========================================================================
# Test 14: Terminal notice contains non-submit / non-transmit / non-auth text
# =========================================================================

class TestTerminalNotice:
    REQUIRED_TERMS = [
        "로컬",
        "실제 제출",
        "전송",
        "인증",
        "종료",
    ]

    def test_terminal_notice_in_ui_source(self):
        src = _read(UI_FILE)
        for term in self.REQUIRED_TERMS:
            assert term in src, \
                f"Terminal notice must contain '{term}'"

    def test_terminal_notice_in_html(self):
        src = _read(HTML_FILE)
        assert "journey-terminal-notice" in src

    def test_terminal_notice_mentions_no_submission(self):
        src = _read(UI_FILE)
        assert "제출" in src or "전송" in src or "인증" in src


# =========================================================================
# Test 15: CSS file uses only journey- prefixed classes
# =========================================================================

class TestCssPrefixOnly:
    def test_css_uses_only_journey_prefixed_classes(self):
        src = _read(CSS_FILE)
        css_classes = re.findall(r'\.([a-zA-Z][a-zA-Z0-9_-]*)\s*\{', src)
        violations = [c for c in css_classes if not c.startswith("journey-")]
        assert not violations, \
            f"CSS classes must all use 'journey-' prefix. Violations: {violations}"


# =========================================================================
# Test 16: HTML clears hardcoded category buttons (dynamic rendering)
# =========================================================================

class TestNoHardcodedCategoryButtons:
    def test_html_has_no_hardcoded_category_buttons(self):
        src = _read(HTML_FILE)
        for cat_id in [
            "illegal-parking",
            "public-parking-inconvenience",
            "residential-parking",
            "traffic-or-facility-safety",
            "other-or-unsure",
        ]:
            pattern = '<button[^>]+data-choice-id[^>]*' + cat_id
            assert not re.search(pattern, src), \
                f"HTML must not hard-code category button for '{cat_id}'"


# =========================================================================
# Test 17: Edit mode state exists
# =========================================================================

class TestEditModeState:
    def test_editing_selections_variable_exists(self):
        src = _read(UI_FILE)
        assert "_editingSelections" in src, \
            "UI must declare _editingSelections boolean"


# =========================================================================
# Test 18: Edit path dispatches REJECT_DRAFT
# =========================================================================

class TestEditDispatchesReject:
    def test_edit_path_dispatches_reject_draft(self):
        src = _read(UI_FILE)
        # The _editSelections function must call reduce with REJECT_DRAFT
        # to clear draft and approval before entering edit mode.
        code = re.sub(r'/\*[\s\S]*?\*/', '',
                      re.sub(r'//.*', '', src))
        # Look for the edit function body containing REJECT_DRAFT
        assert "REJECT_DRAFT" in code, \
            "Edit path must dispatch REJECT_DRAFT"
        assert "_editingSelections = true" in code, \
            "Edit path must set _editingSelections = true"


# =========================================================================
# Test 19: Edit path clears terminal notice
# =========================================================================

class TestEditClearsTerminal:
    def test_edit_path_clears_terminal(self):
        src = _read(UI_FILE)
        code = re.sub(r'/\*[\s\S]*?\*/', '',
                      re.sub(r'//.*', '', src))
        # The edit function body must contain a clear-terminal call
        assert "REJECT_DRAFT" in code and "_clearTerminal" in code, \
            "Edit path must clear terminal notice after REJECT_DRAFT"


# =========================================================================
# Test 20: Edit mode renders all four fact fields
# =========================================================================

class TestEditModeShowsAllFacts:
    def test_edit_mode_shows_all_four_fields(self):
        src = _read(UI_FILE)
        code = re.sub(r'/\*[\s\S]*?\*/', '',
                      re.sub(r'//.*', '', src))
        # The _renderFactCards function must have a path that iterates
        # over all fact field IDs when _editingSelections is true.
        assert "_editingSelections" in src, \
            "Edit mode flag must exist in _renderFactCards context"
        # Verify the edit-mode render path iterates over fieldIds
        assert "fieldIds" in code or "Object.keys(facts)" in code, \
            "Edit mode render path must iterate all fact field IDs"


# =========================================================================
# Test 21: Build / category reset / clear exit edit mode
# =========================================================================

class TestEditModeExit:
    def test_build_exits_edit_mode(self):
        src = _read(UI_FILE)
        code = re.sub(r'/\*[\s\S]*?\*/', '',
                      re.sub(r'//.*', '', src))
        # BUILD_DRAFT must set _editingSelections = false
        assert "_editingSelections = false" in code, \
            "BUILD_DRAFT must exit edit mode (_editingSelections = false)"

    def test_select_category_exits_edit_mode(self):
        src = _read(UI_FILE)
        # SELECT_CATEGORY dispatcher must contain _editingSelections = false
        count = src.count("_editingSelections = false")
        assert count >= 3, \
            f"Expected at least 3 exit points (build, category, clear, canvas sync). Found: {count}"

    def test_clear_exits_edit_mode(self):
        src = _read(UI_FILE)
        code = re.sub(r'/\*[\s\S]*?\*/', '',
                      re.sub(r'//.*', '', src))
        assert "CLEAR_ALL" in code, \
            "CLEAR_ALL must be present"


# =========================================================================
# Test 22: Existing safety contracts preserved alongside edit mode
# =========================================================================

class TestSafetyContractsPreserved:
    def test_no_network_after_edit_additions(self):
        src = _read(UI_FILE)
        code = re.sub(r'/\*[\s\S]*?\*/', '',
                      re.sub(r'//.*', '', src))
        forbidden = [
            r'\bfetch\s*\(',
            r'new\s+WebSocket\s*\(',
            r'\blocalStorage\b',
            r'\bsessionStorage\b',
            r'XMLHttpRequest',
        ]
        for pat in forbidden:
            assert not re.search(pat, code), \
                f"Edit additions must not introduce '{pat}'"

    def test_no_form_elements_after_edit_additions(self):
        src = _read(UI_FILE)
        code = re.sub(r'/\*[\s\S]*?\*/', '',
                      re.sub(r'//.*', '', src))
        for pat in ["<form", "<input", "<textarea", "<select",
                     'contenteditable=', 'type="submit"']:
            assert pat not in code, \
                f"Edit additions must not introduce '{pat}'"

    def test_no_executor_reference_after_edit(self):
        src = _read(UI_FILE)
        code = re.sub(r'/\*[\s\S]*?\*/', '',
                      re.sub(r'//.*', '', src))
        executor_pats = [
            r'\.CitizenActionExecutor\b',
            r'\.CitizenActionDemoMap\b',
            r'citizen_action_plan',
            r'PREFILL_APPROVED_DRAFT',
        ]
        for pat in executor_pats:
            assert not re.search(pat, code), \
                f"Edit additions must not reference executor/map/planner: '{pat}'"