"""
Static contract: action-demo non-persistence audit (Stage #850).

Validates that every static asset in the citizen action-demo surface meets
the non-persistence, no-network, no-console-logging, local-DOM-only contract.

All tests are zero-execution static-text analysis — no Node, no jsdom, no
VM, no browser, no fake DOM, no server start, no network.
"""

import os
import re

import pytest

STATIC = os.path.join(os.path.dirname(__file__), "..", "src", "web", "static")
SERVER = os.path.join(os.path.dirname(__file__), "..", "src", "web", "static_server.py")

# ======================================================================
# Stage #850: the entire action-demo static surface (11 assets).
# ======================================================================

ASSET_ALLOWLIST = [
    "citizen-action-demo.html",
    "citizen-action-demo-map.js",
    "citizen-action-demo-canvas.js",
    "citizen-action-demo-canvas.css",
    "citizen-action-demo-home-decor.css",
    "citizen-action-executor.js",
    "citizen-action-executor.css",
    "citizen-copilot-shell.js",
    "citizen-copilot-shell.css",
    "citizen-complaint-journey.js",
    "citizen-complaint-journey-ui.js",
    "citizen-complaint-journey.css",
    "citizen-first-choreography.js",
    "citizen-first-use-shell.js",
    "citizen-first-use-shell.css",
]


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _all_asset_paths():
    return [os.path.join(STATIC, name) for name in ASSET_ALLOWLIST]


def _loaded_assets():
    """Yield (filename, source_text) for each allowlisted asset."""
    for name in ASSET_ALLOWLIST:
        path = os.path.join(STATIC, name)
        yield name, _read(path)


def _strip_comments_js(src):
    """Remove JS line and block comments so production code is testable."""
    return re.sub(r'/\*[\s\S]*?\*/', '', re.sub(r'//.*', '', src))


# ======================================================================
# Test 1: Asset surface completeness
# ======================================================================

class TestAssetSurface:
    def test_all_eleven_assets_exist(self):
        for path in _all_asset_paths():
            assert os.path.isfile(path), f"Missing asset: {path}"

    def test_no_extra_action_demo_files_outside_allowlist(self):
        """Fail if unknown .js/.html/.css files appear in the static dir
        that match the action-demo prefix but are not in the allowlist."""
        actual = set()
        for entry in os.listdir(STATIC):
            if entry.startswith("citizen-"):
                actual.add(entry)
        expected = set(ASSET_ALLOWLIST)
        extra = actual - expected
        assert not extra, \
            f"Unexpected citizen-* files not in allowlist: {extra}"


# ======================================================================
# Test 2: Visible non-persistence disclosure
# ======================================================================

class TestNonPersistenceDisclosure:
    def test_disclosure_section_exists(self):
        html = _read(os.path.join(STATIC, "citizen-action-demo.html"))
        assert 'id="action-demo-nonpersistence-disclosure"' in html, \
            "Disclosure section not found"

    def test_disclosure_heading_contains_expected_text(self):
        html = _read(os.path.join(STATIC, "citizen-action-demo.html"))
        assert "시연 데이터 안내" in html, \
            "Disclosure heading text not found"

    def test_disclosure_mentions_no_submit(self):
        html = _read(os.path.join(STATIC, "citizen-action-demo.html"))
        assert "실제로 제출하지 않" in html, \
            "Disclosure must state 'does not actually submit'"

    def test_disclosure_mentions_no_storage(self):
        html = _read(os.path.join(STATIC, "citizen-action-demo.html"))
        assert "저장하지 않" in html, \
            "Disclosure must state 'does not persist'"

    def test_disclosure_mentions_session_volatility(self):
        html = _read(os.path.join(STATIC, "citizen-action-demo.html"))
        assert "새로 고치거나 닫으면" in html, \
            "Disclosure must mention session loss on refresh/close"

    def test_disclosure_before_terminal_notice(self):
        """The disclosure must appear earlier in the HTML source than
        the journey-terminal-notice so it is always visible regardless
        of terminal status."""
        html = _read(os.path.join(STATIC, "citizen-action-demo.html"))
        disp_pos = html.find('id="action-demo-nonpersistence-disclosure"')
        term_pos = html.find('id="journey-terminal-notice"')
        assert disp_pos != -1, "Disclosure not found"
        assert term_pos != -1, "Terminal notice not found"
        assert disp_pos < term_pos, \
            "Disclosure must appear before journey-terminal-notice"


# ======================================================================
# Test 3: Raw logging / legacy demo boundary
# ======================================================================

class TestNoRawLoggingConnection:
    FORBIDDEN_TOKENS = [
        "log_conversation",
        "conversation_log",
        "SiteDemoRunner",
        "mobile_demo",
        "admin_demo",
    ]

    def test_eleven_assets_have_no_log_conversation_reference(self):
        for name, src in _loaded_assets():
            code = _strip_comments_js(src)
            for token in self.FORBIDDEN_TOKENS:
                assert token not in code, \
                    f"{name} must not reference '{token}'"

    def test_static_server_has_no_log_conversation_import(self):
        src = _read(SERVER)
        assert "log_conversation" not in src, \
            "static_server.py must not import or reference log_conversation"
        assert "conversation_log" not in src, \
            "static_server.py must not import or reference conversation_log"


# ======================================================================
# Test 4: Browser persistence / network / analytics / console prohibition
# ======================================================================

class TestNoBrowserPersistenceOrNetwork:
    FORBIDDEN_PATTERNS = [
        (r'localStorage', "localStorage"),
        (r'sessionStorage', "sessionStorage"),
        (r'indexedDB', "indexedDB"),
        (r'document\.cookie', "document.cookie"),
        (r'fetch\s*\(', "fetch("),
        (r'XMLHttpRequest', "XMLHttpRequest"),
        (r'WebSocket', "WebSocket"),
        (r'navigator\.sendBeacon', "navigator.sendBeacon"),
        (r'Authorization', "Authorization header"),
        (r'Bearer', "Bearer token"),
        (r'analytics', "analytics reference"),
        (r'console\.log\b', "console.log"),
        (r'console\.info\b', "console.info"),
        (r'console\.warn\b', "console.warn"),
        (r'console\.error\b', "console.error"),
        (r'console\.debug\b', "console.debug"),
    ]

    def test_eleven_assets_have_no_persistence_or_network(self):
        for name, src in _loaded_assets():
            code = _strip_comments_js(src)
            for pat, label in self.FORBIDDEN_PATTERNS:
                matches = re.findall(pat, code)
                if matches:
                    pytest.fail(
                        f"{name} must not contain {label}. "
                        f"Found: {matches}"
                    )


# ======================================================================
# Test 5: Export / download persistence paths prohibited
# ======================================================================

class TestNoExportDownloadPersistence:
    FORBIDDEN_PATTERNS = [
        (r'\bBlob\b', "Blob"),
        (r'URL\.createObjectURL', "URL.createObjectURL"),
        (r'download\s*=', "download= attribute"),
        (r'createElement\s*\(\s*["\']a["\']\s*\)', "createElement('a')"),
    ]

    def test_eleven_assets_have_no_export_download(self):
        for name, src in _loaded_assets():
            code = _strip_comments_js(src)
            for pat, label in self.FORBIDDEN_PATTERNS:
                matches = re.findall(pat, code)
                if matches:
                    pytest.fail(
                        f"{name} must not contain {label}. "
                        f"Found: {matches}"
                    )


# ======================================================================
# Test 6: Executor trace is DOM-local only
# ======================================================================

class TestExecutorTraceIsDomLocal:
    def test_executor_has_action_trace(self):
        src = _read(os.path.join(STATIC, "citizen-action-executor.js"))
        code = _strip_comments_js(src)
        assert "action-trace" in code, \
            "Executor must reference action-trace DOM id"
        assert "ACTION_TYPES" in code, \
            "Executor must define ACTION_TYPES"
        assert "EXPLANATIONS" in code, \
            "Executor must define EXPLANATIONS"

    def test_executor_has_no_persistence_sink(self):
        src = _read(os.path.join(STATIC, "citizen-action-executor.js"))
        code = _strip_comments_js(src)
        for pat in [
            r'localStorage', r'sessionStorage', r'indexedDB',
            r'fetch\s*\(', r'XMLHttpRequest', r'WebSocket',
            r'console\.log\b', r'console\.info\b', r'console\.warn\b',
            r'console\.error\b',
        ]:
            assert not re.search(pat, code), \
                f"Executor source must not contain '{pat}'"


# ======================================================================
# Test 7: Journey draft/prefill is local DOM scope only
# ======================================================================

class TestJourneyDraftIsDomLocal:
    def test_journey_ui_has_local_target(self):
        src = _read(os.path.join(STATIC, "citizen-complaint-journey-ui.js"))
        code = _strip_comments_js(src)
        assert 'LOCAL_TARGET = "complaint-body"' in code or \
               "LOCAL_TARGET = 'complaint-body'" in code or \
               "LOCAL_TARGET =" in code, \
            "Journey UI must define LOCAL_TARGET"
        assert ".textContent" in code, \
            "Journey UI must use textContent for DOM writes"

    def test_journey_ui_has_no_persistence_sink(self):
        src = _read(os.path.join(STATIC, "citizen-complaint-journey-ui.js"))
        code = _strip_comments_js(src)
        for pat in [
            r'localStorage', r'sessionStorage', r'indexedDB',
            r'fetch\s*\(', r'XMLHttpRequest', r'WebSocket',
            r'console\.log\b', r'console\.info\b', r'console\.warn\b',
            r'console\.error\b',
        ]:
            assert not re.search(pat, code), \
                f"Journey UI source must not contain '{pat}'"

    def test_journey_reducer_has_no_persistence_sink(self):
        src = _read(os.path.join(STATIC, "citizen-complaint-journey.js"))
        code = _strip_comments_js(src)
        for pat in [
            r'localStorage', r'sessionStorage', r'indexedDB',
            r'fetch\s*\(', r'XMLHttpRequest', r'WebSocket',
            r'console\.log\b', r'console\.info\b', r'console\.warn\b',
            r'console\.error\b',
        ]:
            assert not re.search(pat, code), \
                f"Journey reducer must not contain '{pat}'"

    def test_journey_ui_has_clear_local_prefill(self):
        """The UI module should provide a mechanism to clear the local
        prefill target (textContent = ''), ensuring no stale draft
        persists across user actions."""
        src = _read(os.path.join(STATIC, "citizen-complaint-journey-ui.js"))
        assert "_clearLocalPrefill" in src, \
            "Journey UI must define _clearLocalPrefill"

    def test_journey_draft_text_content_only(self):
        """Draft/review text must only use textContent, never innerHTML."""
        src = _read(os.path.join(STATIC, "citizen-complaint-journey-ui.js"))
        code = _strip_comments_js(src)
        # Allow innerHTML in non-draft contexts (e.g. trace icon rendering
        # is a separate concern), but there should be no innerHTML + draft
        # combination.
        assert "innerHTML" not in code, \
            "Journey UI must not use innerHTML"


# ======================================================================
# Test 8: Canary boundary — persistence sinks absent
# ======================================================================

class TestCanaryBoundary:
    """This test does NOT define concrete canary values (no hard-coded
    secrets, tokens, or PII). Instead it verifies that no persistence
    sink exists in the action-demo surface that could receive such
    values if they were accidentally introduced.

    If a persistence sink were later added, this test would catch it.
    """

    def test_no_persistence_sink_in_any_action_demo_asset(self):
        """Re-verify the complete set of forbidden persistence/network
        patterns across ALL 11 assets. This is the umbrella check so
        that any single-asset gap is caught.

        A canary value (question, draft, token, PII) that lands in
        the action-demo surface has nowhere to go — no localStorage,
        no fetch, no Blob download, no console.log — because every
        known egress path is verified absent from every asset.
        """
        for name, src in _loaded_assets():
            code = _strip_comments_js(src)
            egress_patterns = [
                (r'localStorage', "localStorage"),
                (r'sessionStorage', "sessionStorage"),
                (r'indexedDB', "indexedDB"),
                (r'document\.cookie', "document.cookie"),
                (r'fetch\s*\(', "fetch("),
                (r'XMLHttpRequest', "XMLHttpRequest"),
                (r'WebSocket', "WebSocket"),
                (r'navigator\.sendBeacon', "navigator.sendBeacon"),
                (r'\bBlob\b', "Blob"),
                (r'URL\.createObjectURL', "URL.createObjectURL"),
                (r'download\s*=', "download= attribute"),
                (r'console\.log\b', "console.log"),
                (r'console\.info\b', "console.info"),
                (r'console\.warn\b', "console.warn"),
                (r'console\.error\b', "console.error"),
            ]
            hits = []
            for pat, label in egress_patterns:
                matches = re.findall(pat, code)
                if matches:
                    hits.append(f"{label} ({matches})")
            assert not hits, \
                f"{name} has persistence/egress sinks: {hits}"
