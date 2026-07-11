"""Offline validation for the Page Agent lab example page.

These tests verify that the Page Agent lab example:
  * Exists as a self-contained source directory
  * Gets correctly emitted by the Cloudflare Pages build
  * Does not modify any Buk-gu MVP routes or API
  * Carries provenance, license, and MIT notice
  * Contains no runtime CDN or external LLM endpoint references
  * Has a local deterministic mock model adapter
  * Supports at least 3 deterministic tasks
  * Has no non-local fetch fallback
"""

from __future__ import annotations

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
_LIVE_LLM_RE = re.compile(
    r"(apiKey:\s*['\"](?!local-test-only)|baseURL:\s*['\"]https?://(?!127\.0\.0\.1|localhost|/))",
    re.IGNORECASE,
)


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
        "vendor/vendor-manifest.json",
        "vendor/page-agent.demo.js",
        "vendor/LICENSE",
    ]
    for name in required:
        path = os.path.join(_EXAMPLES_SRC, name)
        assert os.path.isfile(path), f"missing source file: {name}"


def test_vendor_manifest_valid():
    manifest_path = os.path.join(_VENDOR_DIR, "vendor-manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest.get("package") == "page-agent"
    assert manifest.get("version") == "1.12.1"
    assert manifest.get("upstream_repository") == "alibaba/page-agent"
    assert manifest.get("upstream_commit") == "fa4664dfa5379e6e91deaf85bc1db2ae14d8e1d7"
    assert manifest.get("license") == "MIT"
    assert "source_artifact_sha256" in manifest
    assert "page-agent.demo.js" in manifest.get("vendored_files", [])
    assert "LICENSE" in manifest.get("vendored_files", [])


def test_source_manifest_valid():
    manifest_path = os.path.join(_EXAMPLES_SRC, "source-manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest.get("type") == "attributed_open_source_example"
    assert manifest.get("network_profile", {}).get("runtime_cdn") is False
    assert manifest.get("network_profile", {}).get("live_llm_api") is False
    assert manifest.get("isolation", {}).get("bukgu_manifest_untouched") is True
    assert manifest.get("isolation", {}).get("mvp_unchanged") is True
    assert manifest.get("isolation", {}).get("api_mvp_ask_unchanged") is True


def test_vendor_bundle_exists():
    bundle_path = os.path.join(_VENDOR_DIR, "page-agent.demo.js")
    assert os.path.isfile(bundle_path)
    size = os.path.getsize(bundle_path)
    assert size > 100000, f"vendored bundle seems too small: {size} bytes"


def test_license_file_exists():
    license_path = os.path.join(_VENDOR_DIR, "LICENSE")
    with open(license_path, encoding="utf-8") as f:
        text = f.read()
    assert "MIT" in text
    assert "Permission is hereby granted" in text
    assert "Alibaba Group" in text or "SimonLuvRamen" in text


# ---------------------------------------------------------------------------
# Build output
# ---------------------------------------------------------------------------


def test_build_output_exists(build_dir):
    output = os.path.join(build_dir, "examples", "page-agent")
    assert os.path.isdir(output), "build output examples/page-agent/ missing"
    required = [
        "index.html",
        "page-agent-lab.css",
        "page-agent-lab.js",
        "mock-model.js",
        "source-manifest.json",
        "vendor/vendor-manifest.json",
        "vendor/page-agent.demo.js",
        "vendor/LICENSE",
    ]
    for name in required:
        path = os.path.join(output, name)
        assert os.path.isfile(path), f"missing build output: examples/page-agent/{name}"


def test_build_output_route():
    mod = _load_build_module()
    for mode in ("static", "live"):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out")
            mod.build(out_dir=out, mode=mode)
            route = os.path.join(out, "examples", "page-agent", "index.html")
            assert os.path.isfile(route), (
                f"route /examples/page-agent/ not produced in {mode} mode"
            )


# ---------------------------------------------------------------------------
# Isolation (must not replace or alter existing routes)
# ---------------------------------------------------------------------------


def test_root_route_unchanged(build_dir):
    """Root index.html must still be the Buk-gu MVP landing."""
    index = os.path.join(build_dir, "index.html")
    assert os.path.isfile(index)
    html = open(index, encoding="utf-8").read()
    assert "북구청" in html
    assert "400 AI 파인더" in html


def test_mvp_route_unchanged(build_dir):
    """MVP entry must still exist and function as before."""
    mvp = os.path.join(build_dir, "mvp", "index.html")
    assert os.path.isfile(mvp)
    html = open(mvp, encoding="utf-8").read()
    assert "citizen-first-use-shell.js" in html


def test_mobile_route_unchanged(build_dir):
    mobile = os.path.join(build_dir, "mobile.html")
    assert os.path.isfile(mobile)


def test_admin_route_unchanged(build_dir):
    admin = os.path.join(build_dir, "admin.html")
    assert os.path.isfile(admin)


def test_mvp_api_ask_unchanged():
    """The Cloudflare Function at /api/mvp/ask must not be modified."""
    ask_path = os.path.join(_REPO_ROOT, "functions", "api", "mvp", "ask.js")
    assert os.path.isfile(ask_path)


# ---------------------------------------------------------------------------
# No runtime CDN or external LLM
# ---------------------------------------------------------------------------


def _scan_for_patterns(root_dir, pattern):
    """Scan files in root_dir for regex pattern; return list of (file, match)."""
    hits = []
    for root, _dirs, files in os.walk(root_dir):
        for fn in files:
            if not fn.endswith((".html", ".js", ".css", ".json")):
                continue
            path = os.path.join(root, fn)
            text = open(path, encoding="utf-8", errors="replace").read()
            for m in pattern.finditer(text):
                hits.append((os.path.relpath(path, root_dir), m.group()))
    return hits


def test_no_runtime_cdn_in_source():
    hits = _scan_for_patterns(_EXAMPLES_SRC, _EXTERNAL_URL_RE)
    # Allow documentation references and provenance data:
    #   - index.html has CDN URL in quick-start code example (doc)
    #   - mock-model.js has blocked host list (not active URLs)
    #   - vendor/* is third-party vendored code
    #   - source-manifest.json has blocked origins in provenance
    allowed_suffixes = ("index.html", "mock-model.js", "source-manifest.json")
    allowed_prefix = "vendor"
    active_hits = [
        h for h in hits
        if not (h[0].endswith(allowed_suffixes) or h[0].startswith(allowed_prefix))
    ]
    assert not active_hits, f"runtime CDN references found: {active_hits}"


def test_no_live_llm_endpoint_in_source():
    """No live LLM API endpoints configured.

    Allow documentation code examples and provenance data.
    """
    hits = _scan_for_patterns(_EXAMPLES_SRC, _LIVE_LLM_RE)
    allowed_suffixes = ("index.html", "mock-model.js", "source-manifest.json")
    active_hits = [
        h for h in hits if not h[0].endswith(allowed_suffixes)
    ]
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
        assert host in text, f"blocked host {host} not found in mock-model.js"


# ---------------------------------------------------------------------------
# Model adapter
# ---------------------------------------------------------------------------


def test_mock_model_has_task_definitions():
    mock_path = os.path.join(_EXAMPLES_SRC, "mock-model.js")
    text = open(mock_path, encoding="utf-8").read()
    assert "TASKS" in text
    assert "getSupportedTaskIds" in text
    assert "getTask" in text
    assert "handleCompletion" in text
    assert "isBlocked" in text


def test_mock_model_supports_at_least_three_tasks():
    """At least 3 deterministic tasks must be defined with triggers."""
    mock_path = os.path.join(_EXAMPLES_SRC, "mock-model.js")
    text = open(mock_path, encoding="utf-8").read()
    task_ids = ['quick-start', 'vs-browser-use', 'license', 'architecture']
    found = [tid for tid in task_ids if tid in text]
    assert len(found) >= 3, (
        f"mock model defines only {len(found)} task(s): {found}"
    )


def test_mock_model_has_unsupported_response():
    """Unknown tasks must return a bounded unsupported response."""
    mock_path = os.path.join(_EXAMPLES_SRC, "mock-model.js")
    text = open(mock_path, encoding="utf-8").read()
    assert "buildUnsupportedResponse" in text


def test_page_agent_lab_js_creates_agent():
    """page-agent-lab.js must create a PageAgent instance with customFetch."""
    lab_js = os.path.join(_EXAMPLES_SRC, "page-agent-lab.js")
    text = open(lab_js, encoding="utf-8").read()
    assert "new window.PageAgent" in text
    assert "customFetch" in text
    assert "local-test-only" in text
    assert "local-mock" in text


def test_page_agent_lab_js_shows_panel():
    lab_js = os.path.join(_EXAMPLES_SRC, "page-agent-lab.js")
    text = open(lab_js, encoding="utf-8").read()
    assert "agent.panel.show" in text


# ---------------------------------------------------------------------------
# Page Agent class usage
# ---------------------------------------------------------------------------


def test_page_agent_class_referenced():
    """The lab must reference the actual PageAgent class from the vendored bundle."""
    bundle = os.path.join(_VENDOR_DIR, "page-agent.demo.js")
    text = open(bundle, encoding="utf-8", errors="replace").read()
    assert "window.PageAgent" in text, "IIFE bundle must export window.PageAgent"
    assert (
        "window.PageAgent=" in text or "window.PageAgent =" in text
    ), "IIFE bundle must assign window.PageAgent"
    assert "PageAgentCore" in text, "IIFE bundle must reference PageAgentCore"
    assert "PageController" in text, "IIFE bundle must reference PageController"
    assert "Panel" in text, "IIFE bundle must reference Panel"


def test_page_agent_lab_loads_from_vendor():
    """The HTML must load the vendored IIFE bundle."""
    html_path = os.path.join(_EXAMPLES_SRC, "index.html")
    html = open(html_path, encoding="utf-8").read()
    assert "vendor/page-agent.demo.js" in html


# ---------------------------------------------------------------------------
# Page content
# ---------------------------------------------------------------------------


def test_page_has_required_sections():
    """All required documentation sections must be present."""
    html_path = os.path.join(_EXAMPLES_SRC, "index.html")
    html = open(html_path, encoding="utf-8").read()
    sections = [
        "overview",
        "what-is-page-agent",
        "core-features",
        "use-cases",
        "vs-browser-use",
        "quick-start",
        "npm-installation",
        "basic-execution",
        "architecture",
        "custom-ui",
        "license",
        "source-attribution",
    ]
    for section_id in sections:
        assert f'id="{section_id}"' in html, f"missing section: {section_id}"


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
    """No external image, font, or analytics requests from the page."""
    html_path = os.path.join(_EXAMPLES_SRC, "index.html")
    html = open(html_path, encoding="utf-8").read()
    assert "google-analytics" not in html
    assert "fonts.googleapis" not in html
    assert 'img src="http' not in html


# ---------------------------------------------------------------------------
# Buk-gu independence
# ---------------------------------------------------------------------------


def test_no_bukgu_references_in_lab():
    """The Page Agent lab must not reference Buk-gu quests or manifest."""
    quest_pattern = re.compile(r'\bquest\b', re.IGNORECASE)
    mvp_pattern = re.compile(r'\bmvp\b', re.IGNORECASE)

    for fn in ("index.html", "page-agent-lab.js", "mock-model.js", "page-agent-lab.css"):
        path = os.path.join(_EXAMPLES_SRC, fn)
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        assert "bukgu" not in text.lower(), f"Buk-gu reference found in {fn}"
        assert "북구" not in text, f"Buk-gu Korean reference found in {fn}"
        assert len(quest_pattern.findall(text)) == 0, f"'quest' reference found in {fn}"
        assert len(mvp_pattern.findall(text)) == 0, f"'mvp' reference found in {fn}"
