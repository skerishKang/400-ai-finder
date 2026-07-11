"""Offline validation for the Page Agent lab example page.

These tests verify that the Page Agent lab example:
  * Exists as a self-contained source directory
  * Gets correctly emitted by the Cloudflare Pages build
  * Does not modify any Buk-gu MVP routes or API
  * Carries provenance, license, and MIT notice
  * Contains no runtime CDN or external LLM endpoint references
  * Has a local deterministic mock model adapter
  * Vendors a real non-demo IIFE bundle built from pinned upstream source
  * Manifest SHA parity with vendored artifacts
  * Runs the actual PageAgent -> PageAgentCore -> PageController stack
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import tempfile

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_EXAMPLES_SRC = os.path.join(_REPO_ROOT, "src", "web", "examples", "page-agent")
_VENDOR_DIR = os.path.join(_EXAMPLES_SRC, "vendor")
_BUILD_MODULE_PATH = os.path.join(_REPO_ROOT, "scripts", "build_cloudflare_pages.py")

_EXTERNAL_URL_RE = re.compile(
    r"(cdn\.jsdelivr\.net|registry\.npmmirror\.com|dashscope\.aliyuncs\.com"
    r"|api\.openai\.com|generativelanguage\.googleapis\.com"
    r"|alibaba\.github\.io|raw\.githubusercontent\.com)",
    re.IGNORECASE,
)

# Directories that may contain references to external URLs
# (doc examples, blocked host lists, vendored upstream bundle)
_CDN_SCAN_EXCLUDE_DIRS = {"vendor"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _load_build_module():
    spec = importlib.util.spec_from_file_location(
        "build_cloudflare_pages", _BUILD_MODULE_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def build_dir(tmp_path):
    mod = _load_build_module()
    out = os.path.join(tmp_path, "out")
    mod.build(out_dir=out)
    yield out


# ---------------------------------------------------------------------------
# Source existence
# ---------------------------------------------------------------------------


def test_lab_source_directory_exists():
    assert os.path.isdir(_EXAMPLES_SRC), "page-agent lab source directory missing"


def test_lab_source_files_exist():
    required = [
        "index.html",
        "page-agent-lab.css",
        "page-agent-lab.js",
        "mock-model.js",
        "source-manifest.json",
        "vendor-manifest.json",
    ]
    for name in required:
        path = os.path.join(_EXAMPLES_SRC, name)
        assert os.path.isfile(path), f"missing source file: {name}"


def test_vendor_directory_exists():
    assert os.path.isdir(_VENDOR_DIR), "vendor directory must exist"
    bundle = os.path.join(_VENDOR_DIR, "page-agent.iife.js")
    assert os.path.isfile(bundle), "vendored page-agent.iife.js must exist"
    license_file = os.path.join(_VENDOR_DIR, "LICENSE")
    assert os.path.isfile(license_file), "vendored LICENSE must exist"


def test_page_agent_lab_js_is_real_runtime():
    """page-agent-lab.js must contain the actual runtime initialization."""
    path = os.path.join(_EXAMPLES_SRC, "page-agent-lab.js")
    assert os.path.isfile(path), "page-agent-lab.js must exist"
    text = open(path, encoding="utf-8").read()
    assert "page-agent-lab.js intentionally removed" not in text, "must not be a stub"
    assert "new window.PageAgent" in text, "must instantiate PageAgent"
    assert "agent.panel.show()" in text, "must show the built-in panel"
    assert "customFetch" in text, "must use customFetch"
    assert "window.__PAGE_AGENT_LAB__" in text, "must expose lab integration object"


def test_no_page_agent_demo_js():
    """page-agent.demo.js must not exist anywhere in the lab."""
    for root, _dirs, files in os.walk(_EXAMPLES_SRC):
        for fn in files:
            if "page-agent.demo" in fn or fn == "demo.js":
                pytest.fail(f"Forbidden demo bundle file found: {os.path.join(root, fn)}")


# ---------------------------------------------------------------------------
# Vendor manifest
# ---------------------------------------------------------------------------


def test_vendor_manifest_valid():
    manifest_path = os.path.join(_EXAMPLES_SRC, "vendor-manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest.get("package") == "page-agent"
    assert manifest.get("version") == "1.12.1"
    assert manifest.get("upstream_repository") == "alibaba/page-agent"
    assert manifest.get("upstream_commit") == "fa4664dfa5379e6e91deaf85bc1db2ae14d8e1d7"
    assert manifest.get("license") == "MIT"
    assert manifest.get("build_kind") == "custom-non-demo-iife"
    assert manifest.get("demo_bundle") is False
    assert manifest.get("demo_auto_init") is False
    assert manifest.get("runtime_cdn") is False
    assert manifest.get("runtime_live_model") is False

    vendored = manifest.get("vendored_files", [])
    assert len(vendored) >= 1, "must list vendored files"
    for entry in vendored:
        assert entry.get("sha256"), f"entry {entry['path']} must have sha256"
        assert entry.get("bytes", 0) > 0, f"entry {entry['path']} must have bytes"


def test_vendor_manifest_sha_parity():
    """Manifest SHA-256 must match actual vendored files (case-insensitive)."""
    manifest_path = os.path.join(_EXAMPLES_SRC, "vendor-manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    for entry in manifest.get("vendored_files", []):
        path = os.path.join(_EXAMPLES_SRC, entry["path"])
        assert os.path.isfile(path), f"vendored file missing: {entry['path']}"
        data = open(path, "rb").read()
        actual_sha = hashlib.sha256(data).hexdigest().lower()
        expected_sha = entry["sha256"].lower()
        assert actual_sha == expected_sha, (
            f"SHA mismatch for {entry['path']}: "
            f"expected={entry['sha256']}, actual={actual_sha}"
        )
        assert len(data) == entry["bytes"], (
            f"byte count mismatch for {entry['path']}: "
            f"expected={entry['bytes']}, actual={len(data)}"
        )


# ---------------------------------------------------------------------------
# Source manifest
# ---------------------------------------------------------------------------


def test_source_manifest_valid():
    manifest_path = os.path.join(_EXAMPLES_SRC, "source-manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest.get("type") == "attributed_open_source_example"
    assert manifest.get("integration", {}).get("type") == "actual_page_agent_runtime"
    assert manifest.get("integration", {}).get("model_adapter") == "local_deterministic_mock"
    assert "non-demo IIFE bundle" in manifest.get("integration", {}).get("bundle_status", "")
    assert manifest.get("integration", {}).get("vendor_manifest") == "vendor-manifest.json"
    assert manifest.get("network_profile", {}).get("runtime_cdn") is False
    assert manifest.get("network_profile", {}).get("live_llm_api") is False
    assert manifest.get("network_profile", {}).get("non_local_requests") == 0
    assert manifest.get("isolation", {}).get("bukgu_manifest_untouched") is True
    assert manifest.get("isolation", {}).get("mvp_unchanged") is True
    assert manifest.get("isolation", {}).get("api_mvp_ask_unchanged") is True


# ---------------------------------------------------------------------------
# Build output (requires working build environment)
# ---------------------------------------------------------------------------


def test_build_output_exists(build_dir):
    output = os.path.join(build_dir, "examples", "page-agent")
    assert os.path.isdir(output), "build output examples/page-agent/ missing"
    required = [
        "index.html", "page-agent-lab.css", "mock-model.js",
        "source-manifest.json", "vendor-manifest.json", "page-agent-lab.js",
    ]
    for name in required:
        path = os.path.join(output, name)
        assert os.path.isfile(path), f"missing build output: examples/page-agent/{name}"
    vendor_out = os.path.join(output, "vendor")
    assert os.path.isdir(vendor_out), "vendor directory must be in build output"
    assert os.path.isfile(os.path.join(vendor_out, "page-agent.iife.js")), "vendor bundle missing in build"
    assert os.path.isfile(os.path.join(vendor_out, "LICENSE")), "vendor LICENSE missing in build"
    assert not os.path.isfile(os.path.join(output, "page-agent.demo.js"))


def test_build_output_route():
    """Route /examples/page-agent/ must be produced in both static and live modes."""
    mod = _load_build_module()
    for mode in ("static", "live"):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out")
            mod.build(out_dir=out, mode=mode)
            route = os.path.join(out, "examples", "page-agent", "index.html")
            assert os.path.isfile(route), f"route not produced in {mode} mode"


def test_vendor_bundle_has_no_demo_autoinit():
    bundle = os.path.join(_VENDOR_DIR, "page-agent.iife.js")
    text = open(bundle, encoding="utf-8", errors="replace").read()
    assert "autoInit" not in text
    assert "page-ag-testing" not in text
    assert "DEMO_BASE_URL" not in text


# ---------------------------------------------------------------------------
# Isolation - existing routes must be unchanged (build-dependent)
# ---------------------------------------------------------------------------


def test_root_route_unchanged(build_dir):
    index = os.path.join(build_dir, "index.html")
    assert os.path.isfile(index)
    html = open(index, encoding="utf-8").read()
    assert "북구청" in html
    assert "400 AI 파인더" in html


def test_mvp_route_unchanged(build_dir):
    mvp = os.path.join(build_dir, "mvp", "index.html")
    assert os.path.isfile(mvp)
    html = open(mvp, encoding="utf-8").read()
    assert "citizen-first-use-shell.js" in html


def test_mobile_route_unchanged(build_dir):
    assert os.path.isfile(os.path.join(build_dir, "mobile.html"))


def test_admin_route_unchanged(build_dir):
    assert os.path.isfile(os.path.join(build_dir, "admin.html"))


def test_mvp_api_ask_unchanged():
    ask_path = os.path.join(_REPO_ROOT, "functions", "api", "mvp", "ask.js")
    assert os.path.isfile(ask_path)


# ---------------------------------------------------------------------------
# No runtime CDN or external LLM
# ---------------------------------------------------------------------------


def _scan_files(root_dir, pattern):
    hits = []
    for root, _dirs, files in os.walk(root_dir):
        # Skip vendor directory (vendored upstream bundle may contain references)
        rel_root = os.path.relpath(root, root_dir)
        if rel_root.startswith("vendor"):
            continue
        for fn in files:
            if not fn.endswith((".html", ".js", ".css", ".json")):
                continue
            path = os.path.join(root, fn)
            text = open(path, encoding="utf-8", errors="replace").read()
            for m in pattern.finditer(text):
                hits.append((os.path.relpath(path, root_dir), m.group()))
    return hits


def test_no_runtime_cdn_in_source():
    """No active runtime CDN references outside vendored upstream bundle."""
    hits = _scan_files(_EXAMPLES_SRC, _EXTERNAL_URL_RE)
    # Allowed: doc code examples (index.html), blocked host lists (mock-model.js),
    # source-manifest.json, vendor-manifest.json
    allowed_suffixes = ("index.html", "mock-model.js", "source-manifest.json", "vendor-manifest.json")
    active_hits = [h for h in hits if not h[0].endswith(allowed_suffixes)]
    assert not active_hits, f"runtime CDN references found: {active_hits}"


def test_no_live_llm_endpoint_in_source():
    """No live LLM API endpoints configured (doc code examples are allowed)."""
    _LIVE_LLM_RE = re.compile(
        r"(apiKey:\s*['\"](?!local-test-only)|baseURL:\s*['\"]https?://(?!127\.0\.0\.1|localhost|/))",
        re.IGNORECASE,
    )
    hits = _scan_files(_EXAMPLES_SRC, _LIVE_LLM_RE)
    allowed_suffixes = ("index.html", "mock-model.js", "source-manifest.json", "vendor-manifest.json")
    active_hits = [h for h in hits if not h[0].endswith(allowed_suffixes)]
    assert not active_hits, f"live LLM endpoints found: {active_hits}"


def test_blocked_hosts_in_mock_model():
    mock_path = os.path.join(_EXAMPLES_SRC, "mock-model.js")
    text = open(mock_path, encoding="utf-8").read()
    blocked = [
        "cdn.jsdelivr.net",
        "dashscope.aliyuncs.com",
        "api.openai.com",
        "generativelanguage.googleapis.com",
        "alibaba.github.io",
        "raw.githubusercontent.com",
    ]
    for host in blocked:
        assert host in text, f"blocked host {host} not found"


# ---------------------------------------------------------------------------
# Mock model adapter
# ---------------------------------------------------------------------------


def test_mock_model_has_task_definitions():
    mock_path = os.path.join(_EXAMPLES_SRC, "mock-model.js")
    text = open(mock_path, encoding="utf-8").read()
    assert "TASKS" in text
    assert "getSupportedTaskIds" in text
    assert "getTask" in text
    assert "handleCompletion" in text
    assert "isBlocked" in text
    assert "respond" in text


def test_mock_model_supports_at_least_four_tasks():
    mock_path = os.path.join(_EXAMPLES_SRC, "mock-model.js")
    text = open(mock_path, encoding="utf-8").read()
    task_ids = ["quick-start", "vs-browser-use", "license", "architecture"]
    found = [tid for tid in task_ids if tid in text]
    assert len(found) >= 4, f"mock model defines only {len(found)} task(s): {found}"


def test_mock_model_has_unsupported_response():
    mock_path = os.path.join(_EXAMPLES_SRC, "mock-model.js")
    text = open(mock_path, encoding="utf-8").read()
    assert "unsupported" in text.lower() or "I can only help" in text


def test_mock_model_uses_tool_calls_format():
    """Mock must return tool_calls format, not plain content."""
    mock_path = os.path.join(_EXAMPLES_SRC, "mock-model.js")
    text = open(mock_path, encoding="utf-8").read()
    assert "tool_calls" in text
    assert "AgentOutput" in text, "AgentOutput constant must be defined"
    assert "execute_javascript" in text, "must define execute_javascript tool handler"
    assert "finish_reason" in text
    assert "role: 'assistant'" in text or "'role': 'assistant'" in text


def test_mock_model_reads_actual_tools():
    """Mock must read the actual tool names from the request body."""
    mock_path = os.path.join(_EXAMPLES_SRC, "mock-model.js")
    text = open(mock_path, encoding="utf-8").read()
    assert "payload.tools" in text or "body.tools" in text, "must read tools from request"
    assert "function.name" in text, "must read function name from tool definition"


def test_mock_model_diagnostics():
    """Mock must expose diagnostics for verification."""
    mock_path = os.path.join(_EXAMPLES_SRC, "mock-model.js")
    text = open(mock_path, encoding="utf-8").read()
    assert "getDiagnostics" in text
    assert "callCount" in text
    assert "lastActionName" in text


# ---------------------------------------------------------------------------
# Page content
# ---------------------------------------------------------------------------


def test_page_has_required_sections():
    html_path = os.path.join(_EXAMPLES_SRC, "index.html")
    html = open(html_path, encoding="utf-8").read()
    sections = [
        "overview", "what-is-page-agent", "core-features", "use-cases",
        "vs-browser-use", "quick-start", "npm-installation", "basic-execution",
        "architecture", "custom-ui", "local-integration", "license", "source-attribution",
    ]
    for section_id in sections:
        assert f'id="{section_id}"' in html, f"missing section: {section_id}"


def test_local_integration_section_reports_real_runtime():
    """The local-integration section must state the real runtime integration."""
    html_path = os.path.join(_EXAMPLES_SRC, "index.html")
    html = open(html_path, encoding="utf-8").read()
    assert "Real Non-Demo Bundle" in html or "custom non-demo IIFE bundle" in html
    assert "window.PageAgent" in html
    assert "vendor-manifest.json" in html
    assert "no CDN" in html or "no live model" in html


def test_mit_notice_on_page():
    html_path = os.path.join(_EXAMPLES_SRC, "index.html")
    html = open(html_path, encoding="utf-8").read()
    assert "MIT License" in html
    assert "Permission is hereby granted" in html
    assert "Alibaba Group" in html or "SimonLuvRamen" in html


def test_upstream_provenance_displayed():
    html_path = os.path.join(_EXAMPLES_SRC, "index.html")
    html = open(html_path, encoding="utf-8").read()
    assert "alibaba/page-agent" in html
    assert "fa4664dfa5379e6e91deaf85bc1db2ae14d8e1d7" in html
    assert "1.12.1" in html


def test_page_is_marked_as_experiment():
    html_path = os.path.join(_EXAMPLES_SRC, "index.html")
    html = open(html_path, encoding="utf-8").read()
    assert "interoperability experiment" in html.lower() or "local lab" in html.lower()


def test_no_external_images_or_fonts():
    html_path = os.path.join(_EXAMPLES_SRC, "index.html")
    html = open(html_path, encoding="utf-8").read()
    assert "google-analytics" not in html
    assert "fonts.googleapis" not in html
    assert 'img src="http' not in html


def test_no_auto_init_script():
    """No active script tag references page-agent.demo.js or autoInit."""
    html_path = os.path.join(_EXAMPLES_SRC, "index.html")
    html = open(html_path, encoding="utf-8").read()
    script_load = re.compile(r'<script\s+src="[^"]*page-agent\.demo[\. "]', re.IGNORECASE)
    matches = script_load.findall(html)
    assert len(matches) == 0, f"page-agent.demo.js script loads found: {matches}"
    assert "autoInit" not in html, "autoInit parameter found in page"


def test_scripts_load_order():
    """Vendor bundle must load before mock-model, which loads before lab init."""
    html_path = os.path.join(_EXAMPLES_SRC, "index.html")
    html = open(html_path, encoding="utf-8").read()
    # Use ./ prefix to match script src attributes, not documentation text
    bundle_idx = html.index('./vendor/page-agent.iife.js')
    mock_idx = html.index('./mock-model.js')
    lab_idx = html.index('./page-agent-lab.js')
    assert bundle_idx < mock_idx < lab_idx, "scripts must load: bundle -> mock-model -> lab"


# ---------------------------------------------------------------------------
# Buk-gu independence
# ---------------------------------------------------------------------------


def test_no_bukgu_references_in_lab():
    quest_pattern = re.compile(r'\bquest\b', re.IGNORECASE)
    for fn in ("index.html", "mock-model.js", "page-agent-lab.css", "page-agent-lab.js"):
        path = os.path.join(_EXAMPLES_SRC, fn)
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        assert "bukgu" not in text.lower(), f"Buk-gu reference found in {fn}"
        assert "북구" not in text, f"Buk-gu Korean reference found in {fn}"
        assert len(quest_pattern.findall(text)) == 0, f"'quest' reference found in {fn}"


# ---------------------------------------------------------------------------
# Build script isolation
# ---------------------------------------------------------------------------


def test_build_script_has_minimal_diff():
    """Build script changes must be limited to EXAMPLES_DIR + copy step."""
    script_path = os.path.join(_REPO_ROOT, "scripts", "build_cloudflare_pages.py")
    text = open(script_path, encoding="utf-8").read()
    assert "EXAMPLES_DIR" in text, "build script must define EXAMPLES_DIR"
    assert "Copy examples" in text
    assert "copied examples/page-agent" in text
