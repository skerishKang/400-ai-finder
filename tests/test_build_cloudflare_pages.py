"""Offline validation for the static Cloudflare Pages demo build.

These tests run the build script into a temporary output directory and assert
the Issue #906 hardening requirements:

  * Every /api/* interception is local; all other fetches are hard-blocked.
  * The Jinja ``{{site_name}}`` token is fully substituted in mobile.html.
  * A static 404.html is produced.
  * Out-of-scope questions get a bounded, honest demo response (no same
    snapshot answer masquerading as an answer to any question).
  * No external script/link/fetch auto-calls are emitted (human-clickable
    source URL data is allowed).

No network, no live site, no LLM, no Firecrawl, no API calls.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import tempfile

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_MODULE_PATH = os.path.join(_REPO_ROOT, "scripts", "build_cloudflare_pages.py")

_SCRIPT_SRC_RE = re.compile(r"<script[^>]+src=[\"']https?://", re.IGNORECASE)
_LINK_HREF_RE = re.compile(r"<link[^>]+href=[\"']https?://", re.IGNORECASE)
_FETCH_HTTP_RE = re.compile(r"fetch\(\s*[\"']https?://", re.IGNORECASE)
_CSS_URL_HTTP_RE = re.compile(r"url\(\s*[\"']?https?://", re.IGNORECASE)


def _load_build_module():
    spec = importlib.util.spec_from_file_location("build_cloudflare_pages", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def build_dir():
    mod = _load_build_module()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out")
        mod.build(out_dir=out)
        yield out


def test_required_files_exist(build_dir):
    required = [
        "index.html",
        "mobile.html",
        "admin.html",
        "404.html",
        "snapshot-data.js",
        "static-api-shim.js",
    ]
    for name in required:
        assert os.path.isfile(os.path.join(build_dir, name)), f"missing {name}"

    # source static assets copied
    static_root = os.path.join(build_dir, "static")
    assert os.path.isdir(static_root), "static assets not generated"
    assert os.listdir(static_root), "static assets empty"


def test_mobile_has_no_jinja_site_name(build_dir):
    mobile = os.path.join(build_dir, "mobile.html")
    content = open(mobile, encoding="utf-8").read()
    assert "{{site_name}}" not in content, "{{site_name}} token leaked into mobile.html"
    # SITE_NAME JS var must be the real Buk-gu name, not the token.
    assert "var SITE_NAME = '광주광역시 북구청';" in content
    assert "광주광역시 북구청 AI 안내" in content


def test_shim_blocks_unapproved_fetch(build_dir):
    shim = open(os.path.join(build_dir, "static-api-shim.js"), encoding="utf-8").read()
    # No native fetch fallback must remain.
    assert "_nativeFetch" not in shim, "shim still delegates to native fetch"
    assert "window.fetch.bind" not in shim, "shim binds native fetch"
    # The only non-/api path must be a hard reject.
    assert "Promise.reject(new Error('Static demo: network disabled'))" in shim
    # /api/* endpoints are still intercepted (not rejected).
    assert "/api/ask" in shim
    assert "/api/test" in shim
    assert "/api/info" in shim


def test_shim_question_boundary(build_dir):
    shim = open(os.path.join(build_dir, "static-api-shim.js"), encoding="utf-8").read()
    # Out-of-scope answers must be bounded, not the snapshot answer.
    assert "demo_out_of_scope" in shim
    assert "buildBoundedResponse" in shim
    # The snapshot question is the only approved (supported) question.
    assert "isSupported" in shim
    # Unsupported responses carry no sources/search_results noise.
    assert "sources: []" in shim
    assert "search_results: []" in shim


def test_no_external_auto_calls(build_dir):
    scanned = 0
    for root, _dirs, files in os.walk(build_dir):
        for fn in files:
            if not fn.endswith((".html", ".js", ".css", ".json")):
                continue
            path = os.path.join(root, fn)
            text = open(path, encoding="utf-8", errors="replace").read()
            scanned += 1
            assert not _SCRIPT_SRC_RE.search(text), f"external <script src> in {path}"
            assert not _LINK_HREF_RE.search(text), f"external <link href> in {path}"
            assert not _FETCH_HTTP_RE.search(text), f"external fetch() call in {path}"
            # CSS url(http...) would be an auto network fetch; data: URIs are fine.
            assert not _CSS_URL_HTTP_RE.search(text), f"external url() in {path}"
    assert scanned > 0


def test_snapshot_data_has_demo_profiles(build_dir):
    data = open(os.path.join(build_dir, "snapshot-data.js"), encoding="utf-8").read()
    assert "window.__BUKGU_SNAPSHOT__" in data
    # Extract the JSON payload.
    payload = json.loads(data.split("=", 1)[1].rstrip(";\n"))
    profiles = payload.get("profiles") or []
    site_ids = [p.get("site_id") for p in profiles]
    assert "bukgu_gwangju" in site_ids, "bukgu profile missing from demo"
    # Single fixed demo: only the baked site should be selectable.
    assert site_ids == ["bukgu_gwangju"], f"demo exposes more than one profile: {site_ids}"


def test_admin_model_preset_disabled(build_dir):
    admin = open(os.path.join(build_dir, "admin.html"), encoding="utf-8").read()
    assert "Snapshot 데모 · 모델 전환 없음" in admin
    assert 'id="modelPresetSelect" disabled' in admin


def _node_available() -> bool:
    import shutil

    return shutil.which("node") is not None


@pytest.mark.skipif(not _node_available(), reason="node not available")
def test_shim_execution_boundary(build_dir):
    """Execute the shim in Node to verify runtime behaviour (offline)."""
    import subprocess

    shim = os.path.join(build_dir, "static-api-shim.js")
    data = os.path.join(build_dir, "snapshot-data.js")
    harness = """
    const fs = require('fs');
    const vm = require('vm');
    const code = fs.readFileSync(process.argv[3],'utf8') + '\\n' + fs.readFileSync(process.argv[2],'utf8');
    const sandbox = { window: {}, setTimeout, Promise, console };
    vm.createContext(sandbox);
    vm.runInContext(code, sandbox);
    const w = sandbox.window;
    (async () => {
      try { await w.fetch('https://example.com/x'); console.log('NETWORK_BLOCK_FAIL'); }
      catch (e) { console.log('NETWORK_BLOCK_OK:' + e.message); }
      const r1 = await w.fetch('/api/ask', { method:'POST', body: JSON.stringify({question:'민원서식 어디서 받아?'}) });
      const d1 = await r1.json();
      console.log('SUPPORTED:' + d1.answer_status + ':' + d1.sources.length + ':' + d1.answer_ok);
      const r2 = await w.fetch('/api/ask', { method:'POST', body: JSON.stringify({question:'교육접수는 어디서 해?'}) });
      const d2 = await r2.json();
      console.log('UNSUPPORTED:' + d2.answer_status + ':' + d2.sources.length + ':' + d2.answer_ok);
      const r3 = await w.fetch('/api/info');
      const d3 = await r3.json();
      console.log('INFO_PROFILES:' + d3.profiles.map(p => p.site_id).join(','));
    })();
    """
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(harness)
        harness_path = f.name
    try:
        out = subprocess.run(
            ["node", harness_path, shim, data],
            capture_output=True, text=True, timeout=30, cwd=_REPO_ROOT,
        )
        assert out.returncode == 0, out.stderr
        text = out.stdout
        assert "NETWORK_BLOCK_OK:Static demo: network disabled" in text, text
        assert "SUPPORTED:answered:2:true" in text, text
        assert "UNSUPPORTED:demo_out_of_scope:0:false" in text, text
        assert "INFO_PROFILES:bukgu_gwangju" in text, text
    finally:
        os.unlink(harness_path)

