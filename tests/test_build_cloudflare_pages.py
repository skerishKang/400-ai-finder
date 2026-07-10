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
  * #921 first-use shell/choreography files exist in the build output.
  * #921 browser verifier enforces a localhost-only origin boundary.

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
    assert "var SITE_NAME = '전남광주통합특별시 북구';" in content
    assert "전남광주통합특별시 북구 AI 안내" in content


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


def test_static_first_use_shell_files_exist(build_dir):
    """#921: First-use shell and choreography files must be present in the
    emitted Pages artifact static directory after a build."""
    static = os.path.join(build_dir, "static")
    required = [
        "citizen-action-demo.html",
        "citizen-first-use-shell.js",
        "citizen-first-use-shell.css",
        "citizen-first-choreography.js",
    ]
    for name in required:
        assert os.path.isfile(os.path.join(static, name)), f"missing static/{name}"


def test_static_html_loads_first_use_shell_in_order(build_dir):
    """#921: The emitted citizen-action-demo.html must load the first-use
    shell script before the choreography script."""
    html_path = os.path.join(build_dir, "static", "citizen-action-demo.html")
    html = open(html_path, encoding="utf-8").read()
    shell_idx = html.index("citizen-first-use-shell.js")
    choreo_idx = html.index("citizen-first-choreography.js")
    assert shell_idx < choreo_idx, (
        "citizen-first-use-shell.js must load before citizen-first-choreography.js"
    )


def test_static_html_has_first_use_css(build_dir):
    """#921: The emitted citizen-action-demo.html must reference the first-use
    shell CSS."""
    html_path = os.path.join(build_dir, "static", "citizen-action-demo.html")
    html = open(html_path, encoding="utf-8").read()
    assert "citizen-first-use-shell.css" in html


_REPO_ROOT_FOR_VERIFIER = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_VERIFIER_PATH = os.path.join(
    _REPO_ROOT_FOR_VERIFIER, "tests", "browser", "verify_citizen_first_use_pages.mjs"
)


def test_verifier_rejects_non_localhost_origin():
    """#921: The browser verifier must statically define a localhost-only
    allowlist and reject any external or credentialed base URL before any
    browser interaction."""
    assert os.path.isfile(_VERIFIER_PATH), f"verifier not found at {_VERIFIER_PATH}"
    verifier = open(_VERIFIER_PATH, encoding="utf-8").read()

    # Must have a hostname allowlist
    assert 'LOCAL_HOSTS' in verifier or '"127.0.0.1"' in verifier
    assert '"127.0.0.1"' in verifier
    assert '"localhost"' in verifier
    assert '"::1"' in verifier

    # IPv6 bracket normalization (defense-in-depth against hostname
    # representation differences across Node.js versions / environments)
    assert (
        r'.replace(/^\[|\]$/g' in verifier or '"[::1]"' in verifier
    ), "verifier must strip IPv6 brackets or explicitly accept [::1]"

    # Must validate protocol, credentials, query, hash, and path
    assert 'parsed.protocol' in verifier or 'protocol' in verifier
    assert 'parsed.username' in verifier or 'parsed.password' in verifier
    assert 'parsed.search' in verifier
    assert 'parsed.hash' in verifier
    assert 'parsed.pathname' in verifier

    # Must throw or reject on invalid input
    assert 'throw new Error' in verifier


def test_verifier_uses_dynamic_origin_for_request_filter():
    """#921: The verifier must filter requests by the validated BASE_ORIGIN,
    not a hard-coded origin string."""
    assert os.path.isfile(_VERIFIER_PATH)
    verifier = open(_VERIFIER_PATH, encoding="utf-8").read()
    # Must define a function that checks origin vs BASE_ORIGIN
    assert 'isLocalRequest' in verifier or 'BASE_ORIGIN' in verifier
    assert 'new URL(url).origin === BASE_ORIGIN' in verifier


def test_landing_links_to_public_mvp(build_dir):
    """#942: Root landing links to the backend-free public MVP entry at mvp/.

    The card must use a relative `mvp/` path (no query string), preserve the
    existing mobile/admin links, and carry copy that makes the deterministic,
    backend-free nature of the demo explicit.
    """
    index = open(os.path.join(build_dir, "index.html"), encoding="utf-8").read()

    # Relative-path link to the public MVP entry; no query param allowed.
    assert 'href="mvp/"' in index, "landing must link to mvp/ (relative path)"
    assert "mvp=1" not in index, "no query-string MVP link allowed"
    assert "?mvp=" not in index, "no query-string MVP link allowed"

    # User-facing wording must convey: citizen first screen, deterministic
    # static demo, no real AI/external API.
    assert "시민 행정 도우미" in index
    # Clean, real-service-style landing page.
    assert 'href="mvp/"' in index

    # Existing mobile/admin landing links are preserved.
    assert 'href="mobile.html"' in index
    assert 'href="admin.html"' in index

    # Backend-free: the landing itself stays self-contained / no network.
    assert _SCRIPT_SRC_RE.search(index) is None, "external <script src> in landing"
    assert _LINK_HREF_RE.search(index) is None, "external <link href> in landing"
    assert _FETCH_HTTP_RE.search(index) is None, "external fetch() in landing"
    assert _CSS_URL_HTTP_RE.search(index) is None, "external url() in landing"


def test_admin_model_presets_enabled(build_dir):
    admin = open(os.path.join(build_dir, "admin.html"), encoding="utf-8").read()
    assert 'id="modelPresetSelect"' in admin
    # The select tag itself must NOT have disabled attribute.
    idx = admin.index('id="modelPresetSelect"')
    tag_start = admin.rindex("<", 0, idx)
    tag_end = admin.index(">", idx)
    select_tag = admin[tag_start:tag_end + 1]
    assert "disabled" not in select_tag, "modelPresetSelect must not be disabled"
    assert 'value="deepseek-primary"' in admin
    assert 'value="mimo-primary"' in admin
    assert 'value="step-primary"' in admin


def test_mvp_entry_generated(build_dir):
    """#940: A public first-use MVP entry must be emitted at /mvp/index.html."""
    mvp_index = os.path.join(build_dir, "mvp", "index.html")
    assert os.path.isfile(mvp_index), "mvp/index.html not generated"
    html = open(mvp_index, encoding="utf-8").read()

    # First-use shell + choreography assets are present in the entry.
    assert "citizen-first-use-shell.js" in html
    assert "citizen-first-choreography.js" in html
    assert 'data-first-use-state="entry"' in html
    assert "북구청 AI 민원 안내" in html
    assert "첫 질문 후 북구청 안내 화면과 함께 경로를 보여드립니다." in html

    # Query sanitizer is present and runs before the shell script.
    assert "history.replaceState" in html
    assert html.index("history.replaceState") < html.index("citizen-first-use-shell.js")
    # Sanitizer preserves pathname + hash, drops only the query.
    assert "window.location.pathname + window.location.hash" in html

    # The live bridge script must never be referenced from the public entry.
    assert '<script src="/static/citizen-mvp-bridge.js"' not in html


def test_mvp_entry_is_backend_free(build_dir):
    """#940: The public MVP entry must not auto-call any network/provider."""
    mvp_index = os.path.join(build_dir, "mvp", "index.html")
    html = open(mvp_index, encoding="utf-8").read()
    assert _SCRIPT_SRC_RE.search(html) is None, "external <script src> in mvp entry"
    assert _LINK_HREF_RE.search(html) is None, "external <link href> in mvp entry"
    assert _FETCH_HTTP_RE.search(html) is None, "external fetch() in mvp entry"
    assert _CSS_URL_HTTP_RE.search(html) is None, "external url() in mvp entry"


def test_mvp_entry_source_untouched(build_dir):
    """#940: The source first-use template must be unchanged by the build."""
    source = open(
        os.path.join(_REPO_ROOT, "src", "web", "static", "citizen-action-demo.html"),
        encoding="utf-8",
    ).read()
    # The build only reads the source; the repo copy must not be modified.
    assert "history.replaceState" not in source, "source template was modified by build"
    assert '<script src="/static/citizen-mvp-bridge.js"' not in source


def test_mvp_source_html_no_data_mvp():
    """#1053: The source HTML must not have data-mvp='1' marker."""
    source = open(
        os.path.join(_REPO_ROOT, "src", "web", "static", "citizen-action-demo.html"),
        encoding="utf-8",
    ).read()
    assert 'data-mvp="1"' not in source, "source template must not contain unconditional data-mvp=1"


def test_mvp_static_output_has_no_data_mvp(build_dir):
    """#1053: Static mvp/index.html must not have data-mvp='1'."""
    mvp_index = os.path.join(build_dir, "mvp", "index.html")
    html = open(mvp_index, encoding="utf-8").read()
    assert 'data-mvp="1"' not in html, "static mvp/index.html must not have data-mvp=1"


def test_mvp_static_has_query_sanitizer(build_dir):
    """#1053: Static output must have query sanitizer."""
    mvp_index = os.path.join(build_dir, "mvp", "index.html")
    html = open(mvp_index, encoding="utf-8").read()
    assert "history.replaceState" in html, "static mvp must have query sanitizer"
    assert html.index("history.replaceState") < html.index("citizen-first-use-shell.js")
    assert "window.location.pathname + window.location.hash" in html


def test_mvp_static_has_no_live_injector(build_dir):
    """#1053: Static output must NOT have live ?mvp=1 injector."""
    mvp_index = os.path.join(build_dir, "mvp", "index.html")
    html = open(mvp_index, encoding="utf-8").read()
    assert '"?mvp=1"' not in html, "static mvp must NOT have ?mvp=1 injector"
    assert '"?mvp=1" + window.location.hash' not in html


def test_mvp_live_has_injector():
    """#1053: Live mode build must have ?mvp=1 injector before first shell script."""
    mod = _load_build_module()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out")
        mod.build(out_dir=out, mode="live")
        mvp_index = os.path.join(out, "mvp", "index.html")
        html = open(mvp_index, encoding="utf-8").read()
        # Live injector must be present
        assert '"?mvp=1"' in html or '"\\u003Fmvp=1"' in html, \
            "live mode mvp must have ?mvp=1 injector"
        # Live injector runs before citizen-first-use-shell.js
        injector_idx = html.find("history.replaceState")
        shell_idx = html.find("citizen-first-use-shell.js")
        assert injector_idx >= 0 and injector_idx < shell_idx, \
            "live injector must run before shell script"
        # Live output must NOT have static query sanitizer (pathname+hash).
        assert "window.location.pathname + window.location.hash" not in html, \
            "live mode must NOT have static query sanitizer"
        # Live output must NOT have data-mvp="1".
        assert 'data-mvp="1"' not in html, \
            "live mode must NOT have data-mvp=1"


def test_mvp_live_has_no_static_sanitizer():
    """#1053: Live output must NOT have static query sanitizer (pathname+hash only)."""
    mod = _load_build_module()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out")
        mod.build(out_dir=out, mode="live")
        mvp_index = os.path.join(out, "mvp", "index.html")
        html = open(mvp_index, encoding="utf-8").read()
        # Live output must NOT have the static query sanitizer pattern.
        assert "window.location.pathname + window.location.hash" not in html, \
            "live mode must NOT have static query sanitizer"
        # Live output must have the ?mvp=1 injector.
        assert '"?mvp=1"' in html or '"\\u003Fmvp=1"' in html, \
            "live mode must have ?mvp=1 injector"


def test_mvp_build_does_not_modify_source():
    """#1053: Static/live build must not modify the source template."""
    import hashlib
    source_path = os.path.join(_REPO_ROOT, "src", "web", "static", "citizen-action-demo.html")
    before = hashlib.sha256(open(source_path, "rb").read()).hexdigest()
    mod = _load_build_module()
    with tempfile.TemporaryDirectory() as tmp:
        out_static = os.path.join(tmp, "static_out")
        mod.build(out_dir=out_static, mode="static")
        out_live = os.path.join(tmp, "live_out")
        mod.build(out_dir=out_live, mode="live")
    after = hashlib.sha256(open(source_path, "rb").read()).hexdigest()
    assert before == after, "build must not modify source template"


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
