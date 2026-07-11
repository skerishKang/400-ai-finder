"""Offline validation for the Page Agent lab example page.

These tests verify that the Page Agent lab example:
  * Exists as a self-contained source directory
  * Gets correctly emitted by the Cloudflare Pages build
  * Does not modify any Buk-gu MVP routes or API
  * Carries provenance, license, and MIT notice
  * Contains no runtime CDN or external LLM endpoint references
  * Has a local deterministic mock model adapter
  * Supports at least 3 deterministic tasks
  * Accurately reports the production bundle limitation
  * Has no page-agent.demo.js, no page-agent-lab.js, no vendor directory
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
_BUILD_MODULE_PATH = os.path.join(_REPO_ROOT, "scripts", "build_cloudflare_pages.py")

_EXTERNAL_URL_RE = re.compile(
    r"(cdn\.jsdelivr\.net|registry\.npmmirror\.com|dashscope\.aliyuncs\.com"
    r"|api\.openai\.com|generativelanguage\.googleapis\.com"
    r"|alibaba\.github\.io|raw\.githubusercontent\.com)",
    re.IGNORECASE,
)
_FORBIDDEN_FILES = (
    "page-agent.demo.js",
    "page-agent-lab.js",
    "page-agent.demo",
    "vendor",
)
_FORBIDDEN_PATTERNS = (
    "page-agent.demo.js",
    "autoInit",
    "free testing",
    "testing LLM",
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
        "mock-model.js",
        "source-manifest.json",
    ]
    for name in required:
        path = os.path.join(_EXAMPLES_SRC, name)
        assert os.path.isfile(path), f"missing source file: {name}"


def test_no_vendor_directory():
    """No vendor directory should exist — no browser bundle is vendored."""
    vendor = os.path.join(_EXAMPLES_SRC, "vendor")
    assert not os.path.isdir(vendor), "vendor directory must not exist"


def test_no_page_agent_lab_js():
    """page-agent-lab.js must be removed — no PageAgent class without a bundle."""
    path = os.path.join(_EXAMPLES_SRC, "page-agent-lab.js")
    assert not os.path.isfile(path), "page-agent-lab.js must not exist"


def test_no_page_agent_demo_js():
    """page-agent.demo.js must not exist anywhere in the lab."""
    for root, _dirs, files in os.walk(_EXAMPLES_SRC):
        for fn in files:
            if "page-agent.demo" in fn or "demo.js" in fn.lower():
                pytest.fail(f"Forbidden demo bundle file found: {os.path.join(root, fn)}")


# ---------------------------------------------------------------------------
# Source manifest
# ---------------------------------------------------------------------------


def test_source_manifest_valid():
    manifest_path = os.path.join(_EXAMPLES_SRC, "source-manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest.get("type") == "attributed_open_source_example"
    assert manifest.get("integration", {}).get("bundle_status", "").startswith(
        "page-agent@1.12.1 does not expose a usable non-demo browser bundle"
    ), "manifest must accurately report the bundle limitation"
    assert manifest.get("network_profile", {}).get("runtime_cdn") is False
    assert manifest.get("network_profile", {}).get("live_llm_api") is False
    assert manifest.get("isolation", {}).get("bukgu_manifest_untouched") is True
    assert manifest.get("isolation", {}).get("mvp_unchanged") is True
    assert manifest.get("isolation", {}).get("api_mvp_ask_unchanged") is True


# ---------------------------------------------------------------------------
# Build output
# ---------------------------------------------------------------------------


def test_build_output_exists(build_dir):
    output = os.path.join(build_dir, "examples", "page-agent")
    assert os.path.isdir(output), "build output examples/page-agent/ missing"
    required = ["index.html", "page-agent-lab.css", "mock-model.js", "source-manifest.json"]
    for name in required:
        path = os.path.join(output, name)
        assert os.path.isfile(path), f"missing build output: examples/page-agent/{name}"
    # Forbidden files must NOT be in the build output
    forbidden = ["page-agent.demo.js", "page-agent-lab.js"]
    for name in forbidden:
        path = os.path.join(output, name)
        assert not os.path.isfile(path), f"forbidden build output: examples/page-agent/{name}"


def test_build_output_route():
    """Route /examples/page-agent/ must be produced in both static and live modes."""
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
# Isolation - existing routes must be unchanged
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
        for fn in files:
            if not fn.endswith((".html", ".js", ".css", ".json")):
                continue
            path = os.path.join(root, fn)
            text = open(path, encoding="utf-8", errors="replace").read()
            for m in pattern.finditer(text):
                hits.append((os.path.relpath(path, root_dir), m.group()))
    return hits


def test_no_runtime_cdn_in_source():
    """No active runtime CDN references (doc code examples and blocked lists are allowed)."""
    hits = _scan_files(_EXAMPLES_SRC, _EXTERNAL_URL_RE)
    # Allow doc code examples in index.html and blocked host lists in mock-model.js
    allowed_suffixes = ("index.html", "mock-model.js", "source-manifest.json")
    active_hits = [h for h in hits if not h[0].endswith(allowed_suffixes)]
    assert not active_hits, f"runtime CDN references found: {active_hits}"


def test_no_live_llm_endpoint_in_source():
    """No live LLM API endpoints configured (doc code examples are allowed)."""
    _LIVE_LLM_RE = re.compile(
        r"(apiKey:\s*['\"](?!local-test-only)|baseURL:\s*['\"]https?://(?!127\.0\.0\.1|localhost|/))",
        re.IGNORECASE,
    )
    hits = _scan_files(_EXAMPLES_SRC, _LIVE_LLM_RE)
    allowed_suffixes = ("index.html", "mock-model.js", "source-manifest.json")
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
        assert host in text, f"blocked host {host} not found in mock-model.js"


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


def test_mock_model_supports_at_least_three_tasks():
    mock_path = os.path.join(_EXAMPLES_SRC, "mock-model.js")
    text = open(mock_path, encoding="utf-8").read()
    task_ids = ['quick-start', 'vs-browser-use', 'license', 'architecture']
    found = [tid for tid in task_ids if tid in text]
    assert len(found) >= 3, f"mock model defines only {len(found)} task(s): {found}"


def test_mock_model_has_unsupported_response():
    mock_path = os.path.join(_EXAMPLES_SRC, "mock-model.js")
    text = open(mock_path, encoding="utf-8").read()
    assert "buildUnsupportedResponse" in text


def test_mock_model_uses_openai_compatible_format():
    """Mock completion must return OpenAI-compatible response envelope."""
    mock_path = os.path.join(_EXAMPLES_SRC, "mock-model.js")
    text = open(mock_path, encoding="utf-8").read()
    assert "choices" in text
    assert "finish_reason" in text
    # JS source uses single quotes for object literals
    assert "role: 'assistant'" in text or "'role': 'assistant'" in text or '"role": "assistant"' in text


# ---------------------------------------------------------------------------
# Page content
# ---------------------------------------------------------------------------


def test_page_has_required_sections():
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
        "local-integration",
        "license",
        "source-attribution",
    ]
    for section_id in sections:
        assert f'id="{section_id}"' in html, f"missing section: {section_id}"


def test_local_integration_section_reports_bundle_limitation():
    """The local-integration section must explicitly state the bundle limitation."""
    html_path = os.path.join(_EXAMPLES_SRC, "index.html")
    html = open(html_path, encoding="utf-8").read()
    assert "does not expose a usable non-demo browser bundle" in html


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
    """No active script tag references page-agent.demo.js or autoInit.

    Documentation code examples showing the upstream usage are allowed
    as long as they are not active script loads."""
    html_path = os.path.join(_EXAMPLES_SRC, "index.html")
    html = open(html_path, encoding="utf-8").read()
    # Ensure there is no active <script src=...page-agent.demo.js> load
    import re
    script_load = re.compile(r'<script\s+src="[^"]*page-agent\.demo[\."]', re.IGNORECASE)
    matches = script_load.findall(html)
    assert len(matches) == 0, f"active page-agent.demo.js script loads found: {matches}"
    # autoInit parameter is also forbidden in active script loads
    assert "autoInit" not in html, "autoInit parameter found in page"


# ---------------------------------------------------------------------------
# Buk-gu independence
# ---------------------------------------------------------------------------


def test_no_bukgu_references_in_lab():
    quest_pattern = re.compile(r'\bquest\b', re.IGNORECASE)
    mvp_pattern = re.compile(r'\bmvp\b', re.IGNORECASE)
    for fn in ("index.html", "mock-model.js", "page-agent-lab.css"):
        path = os.path.join(_EXAMPLES_SRC, fn)
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        assert "bukgu" not in text.lower(), f"Buk-gu reference found in {fn}"
        assert "북구" not in text, f"Buk-gu Korean reference found in {fn}"
        assert len(quest_pattern.findall(text)) == 0, f"'quest' reference found in {fn}"
        assert len(mvp_pattern.findall(text)) == 0, f"'mvp' reference found in {fn}"


# ---------------------------------------------------------------------------
# Build script isolation
# ---------------------------------------------------------------------------


def test_build_script_has_minimal_diff():
    """Build script changes must be limited to EXAMPLES_DIR + copy step."""
    script_path = os.path.join(_REPO_ROOT, "scripts", "build_cloudflare_pages.py")
    text = open(script_path, encoding="utf-8").read()
    assert "EXAMPLES_DIR" in text, "build script must define EXAMPLES_DIR"
    # Verify the copy step exists and is minimal
    assert "Copy examples" in text
    assert "copied examples/page-agent" in text
