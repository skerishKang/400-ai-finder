"""Build a static Cloudflare Pages demo from the existing Buk-gu MVP.

This script produces ``dist/cloudflare-pages/`` containing a fully static,
backend-free demo that mirrors the live Python ``src/web`` demos. It is the
*only* producer of that directory — originals under ``src/web`` are copied
verbatim and never moved, deleted, or restructured.

Deterministic by design: the demo answers are baked from the committed Buk-gu
snapshot fixture (``tests/fixtures/bukgu_gwangju_demo_snapshot.json``) at build
time. No network, no LLM, no Firecrawl, no requests fetch, no live site call.

Output layout (all under ``dist/cloudflare-pages/``):
    index.html            # static landing page linking to the two demos
    admin.html            # admin_demo.html (template copied + shim injected)
    mobile.html           # mobile_demo.html (template copied + shim injected)
    static/               # verbatim copy of src/web/static/
    snapshot-data.js      # baked snapshot used by the shim
    static-api-shim.js    # deterministic client-side replacement for /api/*

The shim re-declares ``fetch`` so the existing UI code keeps calling
``/api/ask`` / ``/api/info`` / ``/api/test`` unchanged, but responses come from
the inlined snapshot. Because the shim is injected immediately after the
``<body>`` open tag (before the page's own <script> tags), the override is in
place before any module calls ``fetch``.

Usage::

    python3 scripts/build_cloudflare_pages.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, ".."))
_SYS_PATH_SET = False

# Characters safe to inline verbatim into both HTML text nodes and a JS
# single-quoted string (no quotes/angle-brackets/backslashes/ampersands).
_SAFE_STATIC_RE = re.compile(r"^[가-힣A-Za-z0-9\s\-_,.()/:·]*$")


def _ensure_repo_on_path() -> None:
    global _SYS_PATH_SET
    if not _SYS_PATH_SET:
        sys.path.insert(0, _REPO_ROOT)
        _SYS_PATH_SET = True


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WEB_DIR = os.path.join(_REPO_ROOT, "src", "web")
TEMPLATES_DIR = os.path.join(WEB_DIR, "templates")
STATIC_DIR = os.path.join(WEB_DIR, "static")
SNAPSHOT_FIXTURE = os.path.join(
    _REPO_ROOT, "tests", "fixtures", "bukgu_gwangju_demo_snapshot.json"
)
DIST_ROOT = os.path.join(_REPO_ROOT, "dist", "cloudflare-pages")


# ---------------------------------------------------------------------------
# Snapshot / profile resolution (offline, deterministic)
# ---------------------------------------------------------------------------
def load_snapshot() -> dict:
    """Load the committed Buk-gu snapshot fixture verbatim."""
    with open(SNAPSHOT_FIXTURE, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_site_profile(site_id: str) -> dict | None:
    """Load the site profile offline; return None on any failure."""
    _ensure_repo_on_path()
    try:
        from src.site_profiles import load_profile

        p = load_profile(site_id)
        return {
            "name": p.name,
            "base_url": p.base_url,
            "classification": getattr(p, "classification", None),
            "preferred_fetch_provider": getattr(p, "preferred_fetch_provider", None),
            "important_keywords": list(getattr(p, "important_keywords", []) or []),
            "fallback_strategy": getattr(p, "fallback_strategy", None),
        }
    except Exception:
        return None


def list_all_profiles() -> list[dict]:
    """List all site profiles offline; return [] on any failure."""
    _ensure_repo_on_path()
    try:
        from src.site_profiles import list_profiles

        return list_profiles()
    except Exception:
        return []


# ---------------------------------------------------------------------------
# HTML injection helpers
# ---------------------------------------------------------------------------
BODY_OPEN = "<body>"

# Public first-use MVP entry (/mvp/) boots into the deterministic default flow
# only. If anyone opens it with a query string (e.g. ?mvp=1), strip the query
# with replaceState BEFORE citizen-first-use-shell.js runs, so the shell never
# enters live bridge/API mode. No network/redirect/provider call is made.
MVP_QUERY_SANITIZER = (
    '<script>\n'
    '(function () {\n'
    '  "use strict";\n'
    "  if (window.location.search && window.history && window.history.replaceState) {\n"
    "    window.history.replaceState(\n"
    "      null,\n"
    '      "",\n'
    "      window.location.pathname + window.location.hash\n"
    "    );\n"
    "  }\n"
    "})();\n"
    "</script>"
)


def _inject_after_body_open(html: str, snippet: str) -> str:
    """Insert *snippet* immediately after the first ``<body ...>`` tag.

    Inserting before any page <script> lets the shim's fetch override take
    effect before the UI code runs.
    """
    import re

    # Match <body> with any attributes, non-greedy, first occurrence.
    return re.sub(
        r"(<body[^>]*>)",
        lambda m: m.group(1) + "\n" + snippet,
        html,
        count=1,
    )


def _safe_static_text(value: str) -> str:
    """Return *value* if it is safe to inline into HTML/JS without escaping.

    The static demo substitutes ``{{site_name}}`` directly into both HTML text
    and a JS single-quoted string, so the value must not contain quotes, angle
    brackets, backslashes, or ampersands. Raises ``ValueError`` otherwise.
    """
    if not isinstance(value, str) or value == "":
        raise ValueError("site name must be a non-empty string")
    if "<" in value or ">" in value or "\\" in value or "&" in value:
        raise ValueError(f"site name contains unsafe markup characters: {value!r}")
    if not _SAFE_STATIC_RE.match(value):
        raise ValueError(f"site name contains characters unsafe for static substitution: {value!r}")
    return value


def build_snapshot_data_js(snapshot: dict, profile: dict | None, profiles: list[dict], site_name: str) -> str:
    """Serialize the baked snapshot + profile into a JS data module."""
    payload = {
        "snapshot": snapshot,
        "profile": profile,
        "profiles": profiles,
        "site_name": site_name,
    }
    return (
        "// AUTO-GENERATED by scripts/build_cloudflare_pages.py — do not edit.\n"
        "// Deterministic, build-time snapshot of the Buk-gu demo. No network.\n"
        "window.__BUKGU_SNAPSHOT__ = "
        + json.dumps(payload, ensure_ascii=False)
        + ";\n"
    )


def build_static_api_shim(snapshot: dict, profile: dict | None, profiles: list[dict], site_name: str) -> str:
    """Return a client-side shim that replaces the live /api/* endpoints.

    The shim re-declares a deterministic ``fetch`` that answers the three
    endpoints the original UI calls (/api/ask, /api/info, /api/test) from the
    inlined snapshot. This keeps the original template/JS unchanged while
    making the demo fully static and offline.

    Hardening (per Issue #906):
      * Only /api/ask, /api/test, /api/info are intercepted.
      * Every other fetch is immediately rejected — there is NO native fetch
        fallback, so the "no network" claim is truthful.
      * The /api/ask and /api/test answers are only served for the baked
        snapshot question (or an approved synonym). Out-of-scope questions get
        a bounded, honest "demo only" response with empty sources.
    """
    # Bake the approved (supported) normalized questions into the shim so the
    # boundary is deterministic and verifiable. Only the snapshot question is
    # supported by default; everything else is out of demo scope.
    approved = []
    snap_q = (snapshot or {}).get("question") or ""
    if snap_q:
        approved.append(snap_q)
    approved_json = json.dumps(approved, ensure_ascii=False)

    # Demo profiles baked in (single Buk-gu static demo).
    profiles_json = json.dumps(profiles or [], ensure_ascii=False)
    site_name_json = json.dumps(site_name, ensure_ascii=False)

    return (
        "// AUTO-GENERATED by scripts/build_cloudflare_pages.py — do not edit.\n"
        "// Deterministic, offline replacement for the Python /api/* endpoints.\n"
        "// Reads window.__BUKGU_SNAPSHOT__ baked at build time. No network calls.\n"
        "(function () {\n"
        '  "use strict";\n'
        "  var DATA = window.__BUKGU_SNAPSHOT__ || { snapshot: null, profile: null, profiles: [], site_name: null };\n"
        "  var SNAP = DATA.snapshot || {};\n"
        "  var PROFILE = DATA.profile || null;\n"
        "  var SITE_NAME = DATA.site_name || (SNAP.site_name) || (PROFILE ? PROFILE.name : null) || "
        + json.dumps(site_name, ensure_ascii=False)
        + ";\n"
        "  var APPROVED_QUESTIONS = " + approved_json + ";\n"
        "  var DEMO_PROFILES = " + profiles_json + ";\n"
        "\n"
        "  function delay() { return new Promise(function (r) { setTimeout(r, 120); }); }\n"
        "\n"
        "  function okJson(obj) {\n"
        "    return new Promise(function (resolve) {\n"
        "      resolve({ ok: true, status: 200, json: function () { return Promise.resolve(obj); } });\n"
        "    });\n"
        "  }\n"
        "\n"
        "  function normalize(q) {\n"
        "    if (typeof q !== 'string') return '';\n"
        "    q = q.toLowerCase();\n"
        "    // strip emoji / surrogate pairs\n"
        "    q = q.replace(/[\\uD800-\\uDBFF][\\uDC00-\\uDFFF]/g, '');\n"
        "    // keep only korean / latin / digits / whitespace\n"
        "    q = q.replace(/[^가-힣a-z0-9\\s]/g, ' ');\n"
        "    q = q.replace(/\\s+/g, ' ').trim();\n"
        "    return q;\n"
        "  }\n"
        "\n"
        "  function isSupported(question) {\n"
        "    var n = normalize(question);\n"
        "    if (!n) return false;\n"
        "    for (var i = 0; i < APPROVED_QUESTIONS.length; i++) {\n"
        "      if (normalize(APPROVED_QUESTIONS[i]) === n) return true;\n"
        "    }\n"
        "    return false;\n"
        "  }\n"
        "\n"
        "  function buildAnswerResponse(question) {\n"
        "    return {\n"
        "      site_id: SNAP.site_id,\n"
        "      site_name: SITE_NAME,\n"
        "      question: question,\n"
        "      answer: SNAP.answer || '',\n"
        "      sources: SNAP.sources || [],\n"
        "      search_results: SNAP.search_results || [],\n"
        "      ok: SNAP.ok !== false,\n"
        "      answer_ok: SNAP.answer_ok !== false,\n"
        "      answer_status: SNAP.answer_ok !== false ? 'answered' : 'error',\n"
        "      provider: SNAP.provider || 'mock',\n"
        "      model: SNAP.model || '',\n"
        "      snapshot_mode: true,\n"
        "      fallback_used: false,\n"
        "      llm_live: false,\n"
        "      llm_status: 'snapshot',\n"
        "      llm_label: 'Snapshot 데모',\n"
        "      warnings: [],\n"
        "      route: 'site_search',\n"
        "      should_search_site: true,\n"
        "      route_confidence: 1.0,\n"
        "      route_reason: 'static snapshot',\n"
        "      search_query: question,\n"
        "      answer_mode: 'retrieval_answer',\n"
        "      source_weak: false,\n"
        "      fetch_diagnostic: null\n"
        "    };\n"
        "  }\n"
        "\n"
        "  function buildBoundedResponse(question) {\n"
        "    return {\n"
        "      site_id: SNAP.site_id,\n"
        "      site_name: SITE_NAME,\n"
        "      question: question,\n"
        "      answer: '현재 Cloudflare Pages 정적 시연본은 북구청 스냅샷 기반의 제한된 안내 흐름입니다. 시연 데이터에 포함된 질문으로 다시 확인해 주세요.',\n"
        "      sources: [],\n"
        "      search_results: [],\n"
        "      ok: false,\n"
        "      answer_ok: false,\n"
        "      answer_status: 'demo_out_of_scope',\n"
        "      provider: 'mock',\n"
        "      model: '',\n"
        "      snapshot_mode: true,\n"
        "      fallback_used: false,\n"
        "      llm_live: false,\n"
        "      llm_status: 'snapshot',\n"
        "      llm_label: 'Snapshot 데모',\n"
        "      warnings: ['정적 시연 범위 외 질문입니다. (데모 데이터에 포함된 질문만 응답)'],\n"
        "      route: 'bounded_demo',\n"
        "      should_search_site: false,\n"
        "      route_confidence: 0.0,\n"
        "      route_reason: 'out of demo scope',\n"
        "      search_query: question,\n"
        "      answer_mode: 'bounded_demo',\n"
        "      source_weak: true,\n"
        "      fetch_diagnostic: null\n"
        "    };\n"
        "  }\n"
        "\n"
        "  function buildInfoResponse() {\n"
        "    var snap = SNAP || {};\n"
        "    var homepage = (snap.homepage_map || {}).homepage || {};\n"
        "    var navLinks = homepage.navigation_links || [];\n"
        "    return {\n"
        "      summary: {\n"
        "        service_name: 'AI 홈페이지 파인더',\n"
        "        site_id: snap.site_id || 'bukgu_gwangju',\n"
        "        site_name: SITE_NAME,\n"
        "        provider: snap.provider || 'mock',\n"
        "        model: snap.model || '',\n"
        "        preset: '-',\n"
        "        recommended_order: '-',\n"
        "        llm_live: false,\n"
        "        llm_status: 'snapshot',\n"
        "        llm_label: 'Snapshot 데모',\n"
        "        fetch_provider: PROFILE ? (PROFILE.preferred_fetch_provider || '-') : '-',\n"
        "        demo_fixed: true,\n"
        "        demo_note: '북구청 단일 정적 시연본 (모델 전환 없음)',\n"
        "        snapshot_path: 'tests/fixtures/bukgu_gwangju_demo_snapshot.json'\n"
        "      },\n"
        "      profile: PROFILE || {},\n"
        "      snapshot: {\n"
        "        loaded: true,\n"
        "        path: 'tests/fixtures/bukgu_gwangju_demo_snapshot.json',\n"
        "        fetched_at: snap.fetched_at || '-',\n"
        "        nav_link_count: navLinks.length,\n"
        "        source_count: (snap.sources || []).length,\n"
        "        question: snap.question || '-'\n"
        "      },\n"
        "      status: { snapshot_mode: true, fallback_used: false },\n"
        "      profiles: DEMO_PROFILES\n"
        "    };\n"
        "  }\n"
        "\n"
        "  function buildTestResponse(question) {\n"
        "    if (isSupported(question)) return buildAnswerResponse(question);\n"
        "    return buildBoundedResponse(question);\n"
        "  }\n"
        "\n"
        "  // Expose the deterministic info used by admin_demo.js (loaded via /api/info).\n"
        "  window.__BUKGU_PROFILES__ = DEMO_PROFILES;\n"
        "\n"
        "  // Override fetch BEFORE the UI scripts run (this shim is injected in <body>).\n"
        "  window.fetch = function (input, init) {\n"
        "    var url = (input && input.url) ? input.url : String(input);\n"
        "    var body = (init && init.body) || (input && input.body) || '{}';\n"
        "    function postPayload() { try { return JSON.parse(body) || {}; } catch (e) { return {}; } }\n"
        "\n"
        "    if (url.indexOf('/api/ask') !== -1) {\n"
        "      var qAsk = postPayload().question || '';\n"
        "      return delay().then(function () {\n"
        "        return okJson(isSupported(qAsk) ? buildAnswerResponse(qAsk) : buildBoundedResponse(qAsk));\n"
        "      });\n"
        "    }\n"
        "    if (url.indexOf('/api/test') !== -1) {\n"
        "      var qTest = postPayload().question || '';\n"
        "      return delay().then(function () {\n"
        "        return okJson(buildTestResponse(qTest));\n"
        "      });\n"
        "    }\n"
        "    if (url.indexOf('/api/info') !== -1) {\n"
        "      return delay().then(function () { return okJson(buildInfoResponse()); });\n"
        "    }\n"
        "    // Hard block: this is a static, network-disabled demo. Any other fetch\n"
        "    // (external API, live site, Firecrawl, etc.) is rejected outright.\n"
        "    return Promise.reject(new Error('Static demo: network disabled'));\n"
        "  };\n"
        "})();\n"
    )


def build_index_html(profiles: list[dict]) -> str:
    """Build a static landing page linking to the two demos."""
    profile_items = "".join(
        f"<li><code>{p.get('site_id', '-')}</code> — {p.get('name', '-')}</li>"
        for p in profiles
    ) or "<li>북구청 (bukgu_gwangju)</li>"
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>400 AI 파인더 — 정적 시연 (Cloudflare Pages)</title>
<style>
  :root {{ --bg:#0f172a; --card:#1e293b; --fg:#e2e8f0; --muted:#94a3b8; --accent:#38bdf8; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background:var(--bg); color:var(--fg); }}
  .wrap {{ max-width: 760px; margin: 0 auto; padding: 48px 20px; }}
  h1 {{ font-size: 1.8rem; margin: 0 0 8px; }}
  .sub {{ color: var(--muted); margin-bottom: 32px; }}
  .cards {{ display: grid; gap: 16px; grid-template-columns: 1fr 1fr; }}
  .card {{ display:block; background:var(--card); border-radius:14px; padding:22px; text-decoration:none; color:var(--fg); border:1px solid #334155; transition: transform .15s, border-color .15s; }}
  .card:hover {{ transform: translateY(-3px); border-color: var(--accent); }}
  .card h2 {{ margin: 0 0 6px; font-size:1.15rem; }}
  .card p {{ margin:0; color: var(--muted); font-size:.9rem; }}
  .note {{ margin-top: 32px; padding: 16px; background: var(--card); border-radius:12px; font-size:.85rem; color: var(--muted); }}
  ul {{ margin: 8px 0 0; padding-left: 18px; }}
  code {{ color: var(--accent); }}
</style>
</head>
<body>
<div class="wrap">
  <h1>🏛️ 400 AI 파인더 — 정적 시연</h1>
  <div class="sub">북구청 MVP 정적 배포본 · 빌드 시점 스냅샷 기반 · 네트워크 호출 없음</div>
  <div class="cards">
    <a class="card" href="mobile.html">
      <h2>📱 모바일 챗 데모</h2>
      <p>자연어 질문 → 관련 메뉴 안내</p>
    </a>
    <a class="card" href="admin.html">
      <h2>🖥️ 운영자 화면</h2>
      <p>사이트 프로필 · 스냅샷 상태 · 질문 테스트</p>
    </a>
  </div>
  <div class="note">
    이 데모는 빌드 시점에 고정된 북구청 스냅샷(<code>bukgu_gwangju_demo_snapshot.json</code>)에서 생성된
    결정형 정적 시연입니다. 실제 북구청 사이트·LLM·외부 API 호출은 발생하지 않습니다.
    <ul>{profile_items}</ul>
  </div>
</div>
</body>
</html>
"""


def substitute_site_name(html: str, site_name: str) -> str:
    """Replace every ``{{site_name}}`` token with the build-time *site_name*.

    *site_name* is validated by ``_safe_static_text`` so it is safe to inline
    into both HTML text nodes and the JS single-quoted ``SITE_NAME`` string.
    After substitution the output must contain no ``{{site_name}}`` token.
    """
    safe = _safe_static_text(site_name)
    return html.replace("{{site_name}}", safe)


def build_404_html(site_name: str) -> str:
    """Build a simple, fully static 404 page with no external calls."""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 — 페이지를 찾을 수 없습니다</title>
<style>
  :root {{ --bg:#0f172a; --card:#1e293b; --fg:#e2e8f0; --muted:#94a3b8; --accent:#38bdf8; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background:var(--bg); color:var(--fg); }}
  .wrap {{ max-width: 560px; margin: 0 auto; padding: 80px 20px; text-align:center; }}
  h1 {{ font-size: 4rem; margin: 0 0 8px; color: var(--accent); }}
  p {{ color: var(--muted); }}
  .note {{ margin: 16px 0 32px; font-size:.9rem; }}
  .btns {{ display:flex; gap:12px; justify-content:center; flex-wrap:wrap; }}
  .btn {{ display:inline-block; padding:12px 18px; border-radius:10px; text-decoration:none; color:var(--fg); background:var(--card); border:1px solid #334155; }}
  .btn:hover {{ border-color: var(--accent); }}
</style>
</head>
<body>
<div class="wrap">
  <h1>404</h1>
  <p>요청하신 페이지를 찾을 수 없습니다.</p>
  <p class="note">이 페이지는 빌드 시점에 고정된 {site_name} 정적 시연본입니다. 외부 API 호출은 발생하지 않습니다.</p>
  <div class="btns">
    <a class="btn" href="index.html">시연 홈으로</a>
    <a class="btn" href="mobile.html">모바일 데모</a>
    <a class="btn" href="admin.html">운영자 화면</a>
  </div>
</div>
</body>
</html>
"""


def build_mvp_entry_html() -> str:
    """Build the public first-use MVP entry at ``/mvp/``.

    This is the existing ``citizen-action-demo.html`` first-use demo, copied
    into the build output verbatim except for a query sanitizer injected
    immediately after ``<body>`` open (before the shell scripts run). The
    source template is never modified.

    The sanitizer strips any query string (e.g. ``?mvp=1``) via
    ``history.replaceState`` so the shell can never enter live bridge/API mode
    from the public entry. The copied ``/static/...`` asset paths and the
    existing choreography assets are preserved, and no ``citizen-mvp-bridge.js``
    tag is added.
    """
    source = _read_file(os.path.join(STATIC_DIR, "citizen-action-demo.html"))
    return _inject_after_body_open(source, MVP_QUERY_SANITIZER)


def _disable_model_preset_select(html: str) -> str:
    """Replace the model preset <select> with a disabled, honest demo label.

    The static demo never switches models, so the select is disabled and
    relabeled to make that explicit. The original options are dropped.
    """
    pattern = re.compile(
        r"<select\s+id=\"modelPresetSelect\"[^>]*>.*?</select>",
        re.DOTALL,
    )
    replacement = (
        '<select id="modelPresetSelect" disabled '
        'style="width: 100%; padding: 8px 10px; border: 1.5px solid var(--border); '
        'border-radius: 8px; font-size: .85rem; outline: none; background: #f1f5f9; color: #475569;">'
        '<option value="snapshot-demo" selected>Snapshot 데모 · 모델 전환 없음</option>'
        "</select>"
    )
    return pattern.sub(replacement, html)


# ---------------------------------------------------------------------------
# Copy helpers
# ---------------------------------------------------------------------------
def _copy_tree(src: str, dst: str) -> None:
    """Recursively copy *src* into *dst*, ignoring __pycache__."""
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for entry in os.listdir(src):
            if entry == "__pycache__":
                continue
            _copy_tree(os.path.join(src, entry), os.path.join(dst, entry))
    else:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------
def build(out_dir: str | None = None) -> None:
    # 1. Refresh dist/cloudflare-pages (build-time only output).
    dist_root = out_dir if out_dir else DIST_ROOT
    if os.path.isdir(dist_root):
        shutil.rmtree(dist_root)
    os.makedirs(dist_root, exist_ok=True)

    # 2. Copy static assets verbatim (originals never touched).
    _copy_tree(STATIC_DIR, os.path.join(dist_root, "static"))
    print("[build] copied static assets")

    # 3. Resolve deterministic demo data (offline).
    snapshot = load_snapshot()
    site_id = snapshot.get("site_id", "bukgu_gwangju")
    profile = resolve_site_profile(site_id)
    all_profiles = list_all_profiles()

    # The static demo is fixed to the single Buk-gu snapshot site. Restrict the
    # available profiles to that site so the admin UI cannot imply switching to
    # other (unbaked) sites. Always guarantee the Buk-gu profile is present.
    demo_profiles = [p for p in all_profiles if p.get("site_id") == site_id]
    if not demo_profiles and profile:
        demo_profiles = [profile]
    if not demo_profiles:
        demo_profiles = [{
            "site_id": site_id,
            "name": snapshot.get("site_name") or "북구청",
            "base_url": (profile or {}).get("base_url") or "https://bukgu.gwangju.kr",
            "classification": (profile or {}).get("classification") or "municipal",
        }]

    # Resolved site name used for {{site_name}} substitution (honest, static).
    site_name = (
        (profile or {}).get("name")
        or snapshot.get("site_name")
        or demo_profiles[0].get("name")
        or "북구청"
    )
    site_name = _safe_static_text(site_name)
    print(f"[build] snapshot site_id={site_id}, profile={'loaded' if profile else 'missing'}, site_name={site_name}")

    # 4. Bake snapshot data + shim.
    snapshot_js = build_snapshot_data_js(snapshot, profile, demo_profiles, site_name)
    shim_js = build_static_api_shim(snapshot, profile, demo_profiles, site_name)
    _write_file(os.path.join(dist_root, "snapshot-data.js"), snapshot_js)
    _write_file(os.path.join(dist_root, "static-api-shim.js"), shim_js)
    print("[build] wrote snapshot-data.js + static-api-shim.js")

    # 5. Emit the landing page.
    index_html = build_index_html(demo_profiles)
    _write_file(os.path.join(dist_root, "index.html"), index_html)
    print("[build] wrote index.html")

    # 6. Emit a static 404 page (no external calls).
    _write_file(os.path.join(dist_root, "404.html"), build_404_html(site_name))
    print("[build] wrote 404.html")

    # 7. Copy + adapt the two demo templates (inject shim, keep originals intact).
    mobile_html = _read_file(os.path.join(TEMPLATES_DIR, "mobile_demo.html"))
    admin_html = _read_file(os.path.join(TEMPLATES_DIR, "admin_demo.html"))

    mobile_snippet = (
        '<script src="snapshot-data.js"></script>\n'
        '<script src="static-api-shim.js"></script>'
    )
    admin_snippet = (
        '<script src="snapshot-data.js"></script>\n'
        '<script src="static-api-shim.js"></script>'
    )

    # Honesty fix: statically substitute the Jinja {{site_name}} token so the
    # published mobile page shows the real site name, not the literal token.
    mobile_out = substitute_site_name(mobile_html, site_name)
    mobile_out = _inject_after_body_open(mobile_out, mobile_snippet)

    # Honesty fix: the admin demo is fixed to a single Buk-gu snapshot. Disable
    # the model-preset select and relabel it (no model switching in static demo).
    admin_out = _disable_model_preset_select(admin_html)
    admin_out = _inject_after_body_open(admin_out, admin_snippet)

    _write_file(os.path.join(dist_root, "mobile.html"), mobile_out)
    _write_file(os.path.join(dist_root, "admin.html"), admin_out)
    print("[build] wrote mobile.html + admin.html (templates copied, shim injected)")

    # 8. Emit a public first-use MVP entry at /mvp/ (backend-free, query-sanitized).
    mvp_index = os.path.join(dist_root, "mvp", "index.html")
    _write_file(mvp_index, build_mvp_entry_html())
    print(f"[build] wrote mvp/index.html (public first-use entry)")

    print(f"[build] done -> {dist_root}")


if __name__ == "__main__":
    build()
