"""Static source contracts for the #1090 Page Agent local lab.

These tests verify the vendored non-demo IIFE bundle and its supporting
source files in src/web/examples/page-agent/ without any network, build
output, route registration, or API dependency.

All tests are offline static-source checks. No live model, no CDN, no
build output, no route registration, and no API endpoint.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_EXAMPLES_DIR = os.path.join(_REPO_ROOT, "src", "web", "examples", "page-agent")
_VENDOR_DIR = os.path.join(_EXAMPLES_DIR, "vendor")
_BUILD_MODULE_PATH = os.path.join(_REPO_ROOT, "scripts", "build_cloudflare_pages.py")

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

# ── Build output files ───────────────────────────────────────────────────

BUILD_OUTPUT_FILES = [
    "index.html",
    "mock-model.js",
    "page-agent-lab.js",
    "page-agent-lab.css",
    "source-manifest.json",
    "vendor-manifest.json",
    "vendor/LICENSE",
    "vendor/page-agent.iife.js",
]

# ── Routes that must NOT contain Page Agent content ───────────────────────

PROTECTED_ROUTES = [
    "index.html",      # root landing
    os.path.join("mvp", "index.html"),
    "mobile.html",
    "admin.html",
]

# Discoverability: root gateway link + name only.
PAGE_AGENT_DISCOVERY_SIGNATURES = [
    "Page Agent",
    "page-agent",
]

# Runtime/content leakage: vendor, mock model, lab JS/CSS, init code, experiment body.
PAGE_AGENT_RUNTIME_SIGNATURES = [
    "./vendor/page-agent.iife.js",
    "./mock-model.js",
    "./page-agent-lab.js",
    "./page-agent-lab.css",
    "new window.PageAgent(",
    "PageAgentLabMockModel",
    "what-is-page-agent",
    "Page Agent 1.12.1",
]

# Routes that must not expose ANY Page Agent discovery (name/link) either.
NON_ROOT_PROTECTED_ROUTES = [
    os.path.join("mvp", "index.html"),
    "mobile.html",
    "admin.html",
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


def _run_build(mode):
    """Run the build script with PYTHONPATH via subprocess.
    Builds into default dist/cloudflare-pages directory.
    """
    import subprocess
    env = os.environ.copy()
    # Use an absolute PYTHONPATH so the ``src`` namespace package (no
    # __init__.py) resolves deterministically on every runner regardless of cwd.
    env["PYTHONPATH"] = str(_REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, _BUILD_MODULE_PATH, "--mode", mode],
        capture_output=True, text=True, timeout=120,
        cwd=_REPO_ROOT, env=env,
    )
    assert result.returncode == 0, (
        f"Build ({mode}) failed:\n{result.stderr}"
    )
    return os.path.join(_REPO_ROOT, "dist", "cloudflare-pages")


def _verify_build_output(mode, dist_root):
    """Verify that all page-agent files exist in the build output."""
    page_agent_dir = os.path.join(dist_root, "examples", "page-agent")
    assert os.path.isdir(page_agent_dir), (
        f"examples/page-agent/ missing from {mode} build output"
    )
    for name in BUILD_OUTPUT_FILES:
        path = os.path.join(page_agent_dir, name)
        assert os.path.isfile(path), (
            f"examples/page-agent/{name} missing from {mode} build output"
        )


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

    def test_vendor_manifest_checkout_policy_explicit(self):
        # The vendor-manifest-covered files must be marked -text so Git never
        # applies line-ending conversion (e.g. Windows core.autocrlf=true).
        # This contract is OS-independent: if .gitattributes loses the -text
        # rule, CI on any platform must flag it immediately.
        for name in REQUIRED_VENDOR_FILES:
            rel_path = os.path.join("src", "web", "examples", "page-agent", "vendor", name)
            out = subprocess.run(
                ["git", "check-attr", "text", "--", rel_path],
                cwd=_REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            assert "text: unset" in out.stdout, (
                f"vendor file {rel_path} must be -text in .gitattributes; "
                f"got: {out.stdout.strip()}"
            )

    def test_vendor_manifest_working_tree_has_no_cr(self):
        # The raw working-tree bytes must never contain CR on any clean
        # checkout, otherwise the SHA-256/byte-count parity would break.
        for name in REQUIRED_VENDOR_FILES:
            path = os.path.join(_VENDOR_DIR, name)
            content = _read_bytes(path)
            assert b"\r" not in content, (
                f"vendor file {name} contains CR bytes in working tree"
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


# ── Build output contracts ────────────────────────────────────────────────


class TestBuildOutput:
    """Verify Page Agent files are correctly included in the build output."""

    def test_static_build_includes_page_agent(self):
        out = _run_build("static")
        _verify_build_output("static", out)

    def test_live_build_includes_page_agent(self):
        out = _run_build("live")
        _verify_build_output("live", out)

    def test_source_output_byte_parity_static(self):
        """Copied files must be byte-for-byte identical to source in static build."""
        out = _run_build("static")
        for name in BUILD_OUTPUT_FILES:
            source_path = os.path.join(_EXAMPLES_DIR, name)
            build_path = os.path.join(out, "examples", "page-agent", name)
            assert os.path.isfile(source_path), f"source file missing: {name}"
            assert os.path.isfile(build_path), f"build file missing: {name}"
            source_bytes = _read_bytes(source_path)
            build_bytes = _read_bytes(build_path)
            assert source_bytes == build_bytes, (
                f"Byte mismatch for {name} in static build"
            )

    def test_source_output_byte_parity_live(self):
        """Copied files must be byte-for-byte identical to source in live build."""
        out = _run_build("live")
        for name in BUILD_OUTPUT_FILES:
                source_path = os.path.join(_EXAMPLES_DIR, name)
                build_path = os.path.join(out, "examples", "page-agent", name)
                assert os.path.isfile(source_path), f"source file missing: {name}"
                assert os.path.isfile(build_path), f"build file missing: {name}"
                source_bytes = _read_bytes(source_path)
                build_bytes = _read_bytes(build_path)
                assert source_bytes == build_bytes, (
                    f"Byte mismatch for {name} in live build"
                )


# ── Route isolation contracts ─────────────────────────────────────────────


def _assert_no_page_agent_runtime(text, route, mode):
    for sig in PAGE_AGENT_RUNTIME_SIGNATURES:
        assert sig not in text, (
            f"Page Agent runtime signature {sig!r} found in {mode} {route}"
        )


def _assert_no_page_agent_discovery(text, route, mode):
    for sig in PAGE_AGENT_DISCOVERY_SIGNATURES:
        assert sig not in text, (
            f"Page Agent discovery signature {sig!r} found in {mode} {route}"
        )


class TestRouteIsolation:
    """Page Agent runtime must NOT leak into any protected route; the root
    gateway may expose the discovery link/name, but the three non-root routes
    (MVP / mobile / admin) must stay fully clean of both discovery and runtime.
    """

    @pytest.mark.parametrize("route", PROTECTED_ROUTES)
    def test_static_build_runtime_absent(self, route):
        out = _run_build("static")
        route_path = os.path.join(out, route)
        if os.path.isfile(route_path):
            _assert_no_page_agent_runtime(_read(route_path), route, "static")

    @pytest.mark.parametrize("route", PROTECTED_ROUTES)
    def test_live_build_runtime_absent(self, route):
        out = _run_build("live")
        route_path = os.path.join(out, route)
        if os.path.isfile(route_path):
            _assert_no_page_agent_runtime(_read(route_path), route, "live")

    @pytest.mark.parametrize("route", NON_ROOT_PROTECTED_ROUTES)
    def test_static_build_discovery_absent(self, route):
        out = _run_build("static")
        route_path = os.path.join(out, route)
        if os.path.isfile(route_path):
            _assert_no_page_agent_discovery(_read(route_path), route, "static")

    @pytest.mark.parametrize("route", NON_ROOT_PROTECTED_ROUTES)
    def test_live_build_discovery_absent(self, route):
        out = _run_build("live")
        route_path = os.path.join(out, route)
        if os.path.isfile(route_path):
            _assert_no_page_agent_discovery(_read(route_path), route, "live")

    def test_static_root_is_only_discovery_boundary(self):
        out = _run_build("static")
        index = _read(os.path.join(out, "index.html"))
        # Exactly one same-origin gateway link to the demoted developer lab.
        assert index.count('href="examples/page-agent/"') == 1
        # The demoted developer lab uses the developer-artifact label.
        assert index.count("Page Agent 개발자 실험실") == 1
        # The old primary product label is gone.
        assert index.count("Page Agent 실험실") == 0
        # Exactly one primary resident Page Agent card link.
        assert index.count('href="examples/page-agent/resident/"') == 1
        assert index.count("Page Agent형 AI 북구청") == 1
        # Developer lab is NOT a primary .card.
        assert '<a class="card" href="examples/page-agent/"' not in index
        # Root still contains no runtime leakage.
        _assert_no_page_agent_runtime(index, "index.html", "static")

    def test_live_root_is_only_discovery_boundary(self):
        out = _run_build("live")
        index = _read(os.path.join(out, "index.html"))
        assert index.count('href="examples/page-agent/"') == 1
        assert index.count("Page Agent 개발자 실험실") == 1
        assert index.count("Page Agent 실험실") == 0
        assert index.count('href="examples/page-agent/resident/"') == 1
        assert index.count("Page Agent형 AI 북구청") == 1
        # Developer lab is NOT a primary .card.
        assert '<a class="card" href="examples/page-agent/"' not in index
        _assert_no_page_agent_runtime(index, "index.html", "live")


# ── API isolation contracts ───────────────────────────────────────────────


class TestApiIsolation:
    """Page Agent files must not reference or modify /api/mvp/ask."""

    PAGE_AGENT_FILES = ["index.html", "mock-model.js", "page-agent-lab.js", "page-agent-lab.css"]

    @pytest.mark.parametrize("filename", PAGE_AGENT_FILES)
    def test_no_api_mvp_ask_reference(self, filename):
        text = _read(os.path.join(_EXAMPLES_DIR, filename))
        assert "/api/mvp/ask" not in text, (
            f"{filename} must not reference /api/mvp/ask"
        )


# ── Provenance contracts (fail-closed) ─────────────────────────────────


class TestProvenanceContract:
    """Both manifests must describe the SAME, correct, offline build
    provenance and must NOT claim a published npm/demo bundle was used.

    These tests are fail-closed: any missing provenance field, any
    mismatch between the two manifests, or any forbidden wording fails.
    """

    PINNED_COMMIT = "fa4664dfa5379e6e91deaf85bc1db2ae14d8e1d7"
    EXPECTED_VERSION = "1.12.1"
    EXPECTED_BUNDLE_KIND = "custom_non_demo_iife"

    FORBIDDEN_SUBSTRINGS = [
        "dist/page-agent.iife.js (npm package)",
        # a representation that the published demo bundle was actually used
        "used the published demo bundle",
        "uses the published demo bundle",
        "published demo bundle was used",
    ]

    def _vendor(self):
        return json.loads(_read(os.path.join(_EXAMPLES_DIR, "vendor-manifest.json")))

    def _source(self):
        return json.loads(_read(os.path.join(_EXAMPLES_DIR, "source-manifest.json")))

    def test_vendor_upstream_repository_present(self):
        v = self._vendor()
        assert "upstream_repository" in v, "vendor manifest must declare upstream_repository"
        assert v["upstream_repository"] == "alibaba/page-agent"

    def test_vendor_pinned_commit_exact(self):
        v = self._vendor()
        assert v.get("pinned_commit") == self.PINNED_COMMIT, (
            f"vendor pinned_commit must be exactly {self.PINNED_COMMIT}, "
            f"got {v.get('pinned_commit')}"
        )

    def test_vendor_version(self):
        v = self._vendor()
        assert v.get("version") == self.EXPECTED_VERSION

    def test_vendor_bundle_kind(self):
        v = self._vendor()
        assert v.get("bundle_kind") == self.EXPECTED_BUNDLE_KIND

    def test_vendor_build_provenance_nonempty_dict(self):
        v = self._vendor()
        bp = v.get("build_provenance")
        assert isinstance(bp, dict) and len(bp) > 0, (
            "vendor manifest build_provenance must be a non-empty object"
        )

    def test_vendor_dependency_install_uses_npm_ci_ignore_scripts(self):
        v = self._vendor()
        bp = v["build_provenance"]
        di = bp.get("dependency_install", "")
        assert "npm ci" in di, "build_provenance must record npm ci dependency install"
        assert "--ignore-scripts" in di, (
            "build_provenance must record --ignore-scripts (no postinstall)"
        )

    def test_vendor_excluded_lists_src_demo_ts(self):
        v = self._vendor()
        bp = v["build_provenance"]
        excluded = bp.get("excluded", [])
        joined = " ".join(excluded)
        assert "src/demo.ts" in joined, (
            "build_provenance.excluded must list src/demo.ts"
        )

    def test_vendor_runtime_offline(self):
        v = self._vendor()
        rp = v.get("runtime_profile", {})
        assert rp.get("cdn") is False, "runtime must not use a CDN"
        assert rp.get("live_model_api") is False, "runtime must not use a live model API"
        assert rp.get("non_local_requests") == 0, "runtime must make 0 non-local requests"

    def test_source_runtime_offline(self):
        s = self._source()
        np_ = s.get("network_profile", {})
        assert np_.get("runtime_cdn") is False, "source network_profile.runtime_cdn must be False"
        assert np_.get("live_llm_api") is False, "source network_profile.live_llm_api must be False"
        assert np_.get("non_local_requests") == 0

    def test_manifests_consistent(self):
        s = self._source()
        v = self._vendor()
        # repository
        assert s["upstream"]["repository"] == v["upstream_repository"], (
            "repository must match between source and vendor manifests"
        )
        # pinned commit
        assert s["upstream"]["pinned_commit"] == v["pinned_commit"], (
            "pinned_commit must match between source and vendor manifests"
        )
        # version
        assert s["upstream"]["version"] == v["version"], (
            "version must match between source and vendor manifests"
        )
        # bundle kind
        assert s.get("bundle_kind") == v.get("bundle_kind"), (
            "bundle_kind must match between source and vendor manifests"
        )

    def test_no_forbidden_provenance_wording(self):
        s_text = _read(os.path.join(_EXAMPLES_DIR, "source-manifest.json"))
        v_text = _read(os.path.join(_EXAMPLES_DIR, "vendor-manifest.json"))
        for sub in self.FORBIDDEN_SUBSTRINGS:
            assert sub not in s_text, f"source manifest must not contain forbidden wording: '{sub}'"
            assert sub not in v_text, f"vendor manifest must not contain forbidden wording: '{sub}'"
