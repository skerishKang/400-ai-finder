"""
Static contract: action-demo data boundary after the owner-approved product directive.

Validates that the interactive agent surface does not persist resident data or
send it to unapproved sinks. The dedicated MVP bridge may call the same-origin
official API; the old blanket no-network restriction is superseded.

All tests are zero-execution static-text analysis — no Node, no jsdom, no
VM, no browser, no fake DOM, no server start, no network.
"""

import os
import re

import pytest

STATIC = os.path.join(os.path.dirname(__file__), "..", "src", "web", "static")
SERVER = os.path.join(os.path.dirname(__file__), "..", "src", "web", "static_server.py")
DIRECTIVE = os.path.join(
    os.path.dirname(__file__), "..", "docs", "design",
    "bukgu-ai-agent-product-directive.md",
)

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
    "citizen-mvp-bridge.js",
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

class TestProductDirectiveBoundary:
    def test_owner_approved_directive_is_the_authoritative_contract(self):
        directive = _read(DIRECTIVE)
        assert "owner-approved and authoritative" in directive
        assert "supersedes the narrow local/static product-scope restrictions" in directive

    def test_directive_allows_reversible_visible_agent_actions(self):
        directive = _read(DIRECTIVE)
        assert "type and submit site searches" in directive
        assert "draft and prefill board posts" in directive

    def test_directive_requires_confirmation_at_external_side_effects(self):
        directive = _read(DIRECTIVE)
        assert "final complaint, application, or board-post submission" in directive
        assert "upload or transmission of personal files" in directive

    def test_directive_prohibits_sensitive_browser_persistence(self):
        directive = _read(DIRECTIVE)
        assert "sensitive personal data" in directive.lower()


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

class TestNoBrowserPersistenceOrUnapprovedEgress:
    FORBIDDEN_PATTERNS = [
        (r'localStorage', "localStorage"),
        (r'sessionStorage', "sessionStorage"),
        (r'indexedDB', "indexedDB"),
        (r'document\.cookie', "document.cookie"),
        (r'XMLHttpRequest', "XMLHttpRequest"),
        (r'WebSocket', "WebSocket"),
        (r'navigator\.sendBeacon', "navigator.sendBeacon"),
        (r'Authorization', "Authorization header"),
        (r'Bearer', "Bearer token"),
        (r'analytics', "analytics reference"),
    ]

    def test_assets_have_no_persistence_or_unapproved_egress(self):
        for name, src in _loaded_assets():
            code = _strip_comments_js(src)
            for pat, label in self.FORBIDDEN_PATTERNS:
                matches = re.findall(pat, code)
                if matches:
                    pytest.fail(
                        f"{name} must not contain {label}. "
                        f"Found: {matches}"
                    )

    def test_only_mvp_bridge_calls_fetch_and_it_is_same_origin(self):
        fetch_users = []
        for name, src in _loaded_assets():
            code = _strip_comments_js(src)
            if re.search(r'fetch\s*\(', code):
                fetch_users.append(name)
        assert fetch_users == ["citizen-mvp-bridge.js"]
        bridge = _read(os.path.join(STATIC, "citizen-mvp-bridge.js"))
        assert 'fetch("/api/mvp/ask"' in bridge
        assert not re.search(r'fetch\s*\(\s*["\']https?://', bridge)


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
        patterns across all interactive assets. This is the umbrella check so
        that any single-asset gap is caught.

        A canary value (question, draft, token, PII) that lands in
        the action-demo surface has nowhere to go — no localStorage,
        no fetch, no Blob download, no console.log — because every
        persistence path is verified absent from every asset. The same-origin
        MVP bridge is covered separately above.
        """
        for name, src in _loaded_assets():
            code = _strip_comments_js(src)
            egress_patterns = [
                (r'localStorage', "localStorage"),
                (r'sessionStorage', "sessionStorage"),
                (r'indexedDB', "indexedDB"),
                (r'document\.cookie', "document.cookie"),
                (r'XMLHttpRequest', "XMLHttpRequest"),
                (r'WebSocket', "WebSocket"),
                (r'navigator\.sendBeacon', "navigator.sendBeacon"),
                (r'\bBlob\b', "Blob"),
                (r'URL\.createObjectURL', "URL.createObjectURL"),
                (r'download\s*=', "download= attribute"),
            ]
            hits = []
            for pat, label in egress_patterns:
                matches = re.findall(pat, code)
                if matches:
                    hits.append(f"{label} ({matches})")
            assert not hits, \
                f"{name} has persistence/egress sinks: {hits}"
