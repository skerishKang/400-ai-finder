"""Static source contracts for the #1090 Page Agent local lab.

These tests verify the vendored non-demo IIFE bundle and its supporting
source files in src/web/examples/page-agent/ without any network, build
output, route registration, or API dependency.

All tests are offline static-source checks. No live model, no CDN, no
build output, no route registration, and no API endpoint.
"""

from __future__ import annotations

import hashlib
import json
import os
import re

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_EXAMPLES_DIR = os.path.join(_REPO_ROOT, "src", "web", "examples", "page-agent")
_VENDOR_DIR = os.path.join(_EXAMPLES_DIR, "vendor")

# ── Required files ────────────────────────────────────────────────────────

REQUIRED_SOURCE_FILES = [
    "index.html",
    "mock-model.js",
    "page-agent-lab.js",
    "page-agent-lab.css",
    "source-manifest.json",
    "vendor-manifest.json",
]

REQUIRED_VENDOR_FILES = [
    "LICENSE",
    "page-agent.iife.js",
]

# ── Hosts that must appear in mocked blocklists ───────────────────────────

REQUIRED_BLOCKED_HOSTS = [
    "cdn.jsdelivr.net",
    "dashscope.aliyuncs.com",
    "api.openai.com",
    "generativelanguage.googleapis.com",
]

# ── Demo strings that must NOT appear outside documentation code examples ──

FORBIDDEN_DEMO_PATTERNS = [
    "page-ag-testing-ohftxirgbn",  # demo testing API key
    "DEMO_BASE_URL",
    "autoInit",
]

# ── Supports ──────────────────────────────────────────────────────────────


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


# ── File existence ────────────────────────────────────────────────────────


class TestSourceExistence:
    def test_required_source_files_exist(self):
        for name in REQUIRED_SOURCE_FILES:
            path = os.path.join(_EXAMPLES_DIR, name)
            assert os.path.isfile(path), f"required source file missing: {name}"

    def test_required_vendor_files_exist(self):
        for name in REQUIRED_VENDOR_FILES:
            path = os.path.join(_VENDOR_DIR, name)
            assert os.path.isfile(path), f"required vendor file missing: {name}"

    def test_vendor_bundle_is_substantial(self):
        path = os.path.join(_VENDOR_DIR, "page-agent.iife.js")
        size = os.path.getsize(path)
        assert size > 100_000, f"vendor bundle too small: {size} bytes"

    def test_vendor_license_is_mit(self):
        text = _read(os.path.join(_VENDOR_DIR, "LICENSE"))
        assert "MIT License" in text
        assert "Permission is hereby granted" in text


# ── Vendor manifest integrity ─────────────────────────────────────────────


class TestVendorManifestIntegrity:
    def test_manifest_parses(self):
        path = os.path.join(_EXAMPLES_DIR, "vendor-manifest.json")
        manifest = json.loads(_read(path))
        assert "vendored_files" in manifest

    def test_manifest_sha256_parity(self):
        manifest = json.loads(
            _read(os.path.join(_EXAMPLES_DIR, "vendor-manifest.json"))
        )
        for entry in manifest["vendored_files"]:
            file_path = os.path.join(_EXAMPLES_DIR, entry["path"])
            assert os.path.isfile(file_path), f"vendored file not found: {entry['path']}"
            content = _read_bytes(file_path)
            actual_sha = hashlib.sha256(content).hexdigest().upper()
            assert actual_sha == entry["sha256"].upper(), (
                f"SHA-256 mismatch for {entry['path']}: "
                f"expected {entry['sha256']}, got {actual_sha}"
            )
            assert len(content) == entry["bytes"], (
                f"byte count mismatch for {entry['path']}: "
                f"expected {entry['bytes']}, got {len(content)}"
            )


# ── Source manifest ───────────────────────────────────────────────────────


class TestSourceManifest:
    def test_source_manifest_parses(self):
        path = os.path.join(_EXAMPLES_DIR, "source-manifest.json")
        manifest = json.loads(_read(path))
        assert manifest["experiment_id"] == "1090"
        assert manifest["type"] == "attributed_open_source_example"
        assert manifest["upstream"]["repository"] == "alibaba/page-agent"

    def test_network_profile(self):
        manifest = json.loads(
            _read(os.path.join(_EXAMPLES_DIR, "source-manifest.json"))
        )
        profile = manifest["network_profile"]
        assert profile["runtime_cdn"] is False
        assert profile["live_llm_api"] is False
        assert profile["non_local_requests"] == 0
        assert len(profile["blocked_origins"]) > 0

    def test_isolation(self):
        manifest = json.loads(
            _read(os.path.join(_EXAMPLES_DIR, "source-manifest.json"))
        )
        isolation = manifest["isolation"]
        assert isolation["bukgu_manifest_untouched"] is True
        assert isolation["bukgu_registry_untouched"] is True
        assert isolation["mvp_unchanged"] is True
        assert isolation["api_mvp_ask_unchanged"] is True


# ── No demo strings (outside doc examples) ────────────────────────────────


class TestNoDemoStrings:
    def test_bundle_no_demo_strings(self):
        """Vendor IIFE bundle must not contain demo-only API keys or auto-init references."""
        text = _read(os.path.join(_VENDOR_DIR, "page-agent.iife.js"))
        for pattern in FORBIDDEN_DEMO_PATTERNS:
            assert pattern not in text, f"forbidden demo pattern found in bundle: {pattern}"

    def test_lab_init_no_demo_strings(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.js"))
        for pattern in FORBIDDEN_DEMO_PATTERNS:
            assert pattern not in text, f"forbidden demo pattern found in lab init: {pattern}"

    def test_vendor_bundle_no_auto_init(self):
        """Vendor bundle must not contain autoInit or auto-init."""
        text = _read(os.path.join(_VENDOR_DIR, "page-agent.iife.js"))
        assert "autoInit" not in text, "vendor bundle must not contain autoInit"


# ── page-agent-lab.js contracts ───────────────────────────────────────────


class TestPageAgentLabInit:
    def test_instantiates_actual_page_agent(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.js"))
        assert "new window.PageAgent(" in text
        assert "window.PageAgent" in text

    def test_uses_custom_fetch(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.js"))
        assert "customFetch:" in text
        assert "localCustomFetch" in text

    def test_shows_built_in_panel(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.js"))
        assert "agent.panel.show()" in text

    def test_enables_execute_javascript_tool(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.js"))
        assert "experimentalScriptExecutionTool: true" in text

    def test_uses_mock_model_respond(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.js"))
        assert "PageAgentLabMockModel.respond" in text

    def test_no_native_fetch(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.js"))
        # The IIFE bundle may internally use fetch, but the lab init must not.
        assert "fetch(" not in text

    def test_no_direct_scroll(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.js"))
        assert "scrollIntoView" not in text


# ── mock-model.js contracts ───────────────────────────────────────────────


class TestMockModel:
    def test_exports_page_agent_mock_model(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "mock-model.js"))
        assert "window.PageAgentMockModel" in text

    def test_exports_required_functions(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "mock-model.js"))
        assert "respond:" in text
        assert "handleCompletion:" in text
        assert "isBlocked:" in text
        assert "getSupportedTaskIds:" in text
        assert "getTask:" in text
        assert "isSupportedTask:" in text
        assert "getAllTasks:" in text
        assert "getDiagnostics:" in text

    def test_has_supported_tasks(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "mock-model.js"))
        assert "TASKS" in text
        # At least 4 tasks
        assert text.count("id:") >= 4

    def test_has_url_blocklist(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "mock-model.js"))
        assert "BLOCKED_HOSTS" in text
        for host in REQUIRED_BLOCKED_HOSTS:
            assert host in text, f"required blocked host missing: {host}"

    def test_agent_output_tool_call_contract(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "mock-model.js"))
        assert "AgentOutput" in text
        assert "tool_calls" in text
        assert "execute_javascript" in text
        assert "finish_reason" in text
        assert "function:" in text

    def test_diagnostic_tracking(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "mock-model.js"))
        assert "callCount" in text
        assert "toolNames" in text
        assert "actionNames" in text
        assert "taskIds" in text

    def test_legacy_alias(self):
        text = _read(os.path.join(_EXAMPLES_DIR, "mock-model.js"))
        assert "PageAgentLabMockModel" in text


# ── index.html contracts ──────────────────────────────────────────────────


class TestIndexHtml:
    def test_script_load_order(self):
        html = _read(os.path.join(_EXAMPLES_DIR, "index.html"))
        bundle_idx = html.index("./vendor/page-agent.iife.js")
        mock_idx = html.index("./mock-model.js")
        lab_idx = html.index("./page-agent-lab.js")
        assert bundle_idx < mock_idx < lab_idx, "script load order must be: bundle → mock → lab"

    def test_has_documentation_sections(self):
        html = _read(os.path.join(_EXAMPLES_DIR, "index.html"))
        required_sections = [
            "what-is-page-agent",
            "core-features",
            "use-cases",
            "vs-browser-use",
            "quick-start",
            "npm-installation",
            "basic-execution",
            "architecture",
            "custom-ui",
            "local-integration",
            "license",
            "source-attribution",
        ]
        for section_id in required_sections:
            assert f'id="{section_id}"' in html, f"required section #{section_id} missing"

    def test_hero_badges(self):
        html = _read(os.path.join(_EXAMPLES_DIR, "index.html"))
        assert "MIT License" in html
        assert "Offline Experiment" in html

    def test_lab_footer(self):
        html = _read(os.path.join(_EXAMPLES_DIR, "index.html"))
        assert "Local interoperability experiment" in html
        assert "Page Agent 1.12.1" in html

    def test_source_attribution_table(self):
        html = _read(os.path.join(_EXAMPLES_DIR, "index.html"))
        assert "alibaba/page-agent" in html
        assert "fa4664dfa5379e6e91deaf85bc1db2ae14d8e1d7" in html

    def test_no_demo_api_key_in_markup(self):
        html = _read(os.path.join(_EXAMPLES_DIR, "index.html"))
        # Doc examples may show placeholders like 'YOUR_API_KEY'
        # but must NOT contain the actual demo testing key.
        assert "page-ag-testing-ohftxirgbn" not in html


# ── Source isolation ──────────────────────────────────────────────────────


class TestSourceIsolation:
    """Page Agent lab must not reference Buk-gu or MVP concepts."""

    SOURCE_FILES = ["index.html", "mock-model.js", "page-agent-lab.js", "page-agent-lab.css"]

    @pytest.mark.parametrize("filename", SOURCE_FILES)
    def test_no_bukgu_reference(self, filename):
        text = _read(os.path.join(_EXAMPLES_DIR, filename))
        assert "bukgu" not in text.lower(), f"{filename} must not reference bukgu"

    @pytest.mark.parametrize("filename", SOURCE_FILES)
    def test_no_quest_reference(self, filename):
        text = _read(os.path.join(_EXAMPLES_DIR, filename))
        # Use word-boundary regex to avoid matching 'quest' inside 'request'
        assert not re.search(r'\bquest\b', text, re.IGNORECASE), (
            f"{filename} must not reference the 'quest' concept"
        )

    @pytest.mark.parametrize("filename", SOURCE_FILES)
    def test_no_mvp_reference(self, filename):
        text = _read(os.path.join(_EXAMPLES_DIR, filename))
        assert "mvp" not in text.lower(), f"{filename} must not reference mvp"


# ── page-agent-lab.css contracts ──────────────────────────────────────────


class TestLabCss:
    def test_target_active_marker(self):
        css = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.css"))
        assert ".page-agent-target-active" in css
        assert "outline" in css
        assert "transition" in css

    def test_smooth_scroll(self):
        css = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.css"))
        assert "scroll-behavior: smooth" in css

    def test_navigation_style(self):
        css = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.css"))
        assert ".lab-nav" in css
        assert "backdrop-filter" in css

    def test_architecture_diagram(self):
        css = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.css"))
        assert ".arch-diagram" in css
        assert ".arch-layer" in css

    def test_comparison_table(self):
        css = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.css"))
        assert ".comparison-table" in css

    def test_prefers_reduced_motion(self):
        css = _read(os.path.join(_EXAMPLES_DIR, "page-agent-lab.css"))
        assert "prefers-reduced-motion" not in css  # not required for this lab
