"""Build a Cloudflare Pages deployment from the existing Buk-gu MVP.

Two modes (``--mode``):

**static** (explicit fallback via ``--mode static``)
    Produces ``dist/cloudflare-pages/`` containing a fully static, backend-free
    demo that mirrors the live Python ``src/web`` demos. It is the *only*
    producer of that directory — originals under ``src/web`` are copied verbatim
    and never moved, deleted, or restructured.

    Deterministic by design: the demo answers are baked from the committed
    Buk-gu snapshot fixture at build time. No network, no LLM, no Firecrawl,
    no requests fetch, no live site call.

    Output layout (all under ``dist/cloudflare-pages/``):
        index.html            # static landing page linking to the two demos
        admin.html            # admin_demo.html (template copied + shim injected)
        mobile.html           # mobile_demo.html (template copied + shim injected)
        static/               # verbatim copy of src/web/static/
        snapshot-data.js      # baked snapshot used by the shim
        static-api-shim.js    # deterministic client-side replacement for /api/*

    Usage::

        python3 scripts/build_cloudflare_pages.py --mode static

**live** (deployment CLI default)
    Produces ``dist/cloudflare-pages/`` optimised for deployment behind
    Cloudflare Pages Functions (``functions/api/mvp/ask.js``). All chat
    interfaces use the live ``POST /api/mvp/ask`` endpoint instead of the
    static shim:

      * No ``snapshot-data.js`` or ``static-api-shim.js`` are generated.
      * The ``?mvp=1`` query string is preserved in the MVP entry so that
        ``citizen-first-use-shell.js`` loads the MVP bridge.
      * Mobile chat uses ``/api/mvp/ask`` as its API endpoint.
      * Neither mobile nor admin pages inject the static shim scripts.

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
EXAMPLES_DIR = os.path.join(WEB_DIR, "examples")
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

# Live mode MVP entry injects ?mvp=1 via replaceState so that
# citizen-first-use-shell.js loads the MVP bridge even when the user
# arrives without the query string.
MVP_MODE_INJECTOR = (
    '<script>\n'
    '(function () {\n'
    '  "use strict";\n'
    "  if (window.history && window.history.replaceState) {\n"
    "    window.history.replaceState(\n"
    "      null,\n"
    '      "",\n'
    "      window.location.pathname + \"?mvp=1\" + window.location.hash\n"
    "    );\n"
    "  }\n"
    "})();\n"
    "</script>\n"
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
        "      llm_label: '정적 안내',\n"
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
        "      answer: '현재 북구청 안내 정보를 바탕으로 답변드립니다. 준비된 질문으로 다시 확인해 주세요.',\n"
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
        "      llm_label: '정적 안내',\n"
        "      warnings: ['준비된 질문 외에는 답변이 어렵습니다. 준비된 질문으로 다시 확인해 주세요.'],\n"
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
        "        llm_label: '정적 데이터',\n"
        "        fetch_provider: PROFILE ? (PROFILE.preferred_fetch_provider || '-') : '-',\n"
        "        demo_fixed: true,\n"
        "        demo_note: '북구청 단일 안내 데이터 고정',\n"
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


def build_index_html(profiles: list[dict], is_live: bool = False) -> str:
    """Build a static landing page linking to the two demos.

    If *is_live* is True, the MVP card link includes ``?mvp=1`` so that
    the shell loads the live MVP bridge instead of the query-sanitized
    static entry.
    """
    mvp_href = "mvp/?mvp=1" if is_live else "mvp/"
    profile_items = "".join(
        f"<li><code>{p.get('site_id', '-')}</code> — {p.get('name', '-')}</li>"
        for p in profiles
    ) or "<li>북구청 (bukgu_gwangju)</li>"
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>400 AI 파인더</title>
<style>
  :root {{ --bg:#fff; --card:#fafafb; --fg:#0d0d0f; --muted:#9b9ba5; --line:#e6e6ea; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans KR","Apple SD Gothic Neo",sans-serif; background:var(--bg); color:var(--fg); -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width: 680px; margin: 0 auto; padding: 60px 20px; }}
  h1 {{ font-size: 1.6rem; font-weight: 600; letter-spacing:-.02em; margin: 0 0 6px; }}
  .sub {{ color: var(--muted); margin-bottom: 36px; font-size:.92rem; }}
  .cards {{ display: grid; gap: 12px; }}
  .card {{ display:block; background:var(--card); border:1px solid var(--line); border-radius:14px; padding:20px 22px; text-decoration:none; color:var(--fg); transition:background .15s,border-color .15s; }}
  .card:hover {{ background:#f5f5f7; border-color:#d0d0d5; }}
  .card h2 {{ margin: 0 0 4px; font-size:1.05rem; font-weight:600; }}
  .card p {{ margin:0; color: var(--muted); font-size:.88rem; line-height:1.45; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>400 AI 파인더</h1>
  <div class="sub">북구청 AI 안내 서비스</div>
  <div class="cards">
    <a class="card" href="{mvp_href}">
      <h2>시민 행정 도우미</h2>
      <p>정밀 구현형 AI 북구청 — 질문하면 북구청 안내 화면을 함께 열어 경로를 안내합니다.</p>
    </a>
    <a class="card" href="examples/page-agent/resident/">
      <h2>Page Agent형 AI 북구청</h2>
      <p>자연어 요청을 해석하고, Page Agent가 보이는 동작(클릭·입력·선택·스크롤·같은 출처 이동)으로 북구청 화면을 안내합니다. 주민용 비교 데모입니다.</p>
    </a>
    <a class="card" href="mobile.html">
      <h2>모바일 챗 안내</h2>
      <p>자연어 질문으로 관련 메뉴를 찾습니다.</p>
    </a>
    <a class="card" href="admin.html">
      <h2>운영자 화면</h2>
      <p>사이트 프로필 · 질문 테스트 · 상태 확인</p>
    </a>
    <a class="card" href="examples/page-agent/">
      <h2>Page Agent 개발자 실험실</h2>
      <p>브라우저 안에서 페이지 요소를 조작하는 독립 오프라인 기술 실험(영어 문서)입니다. 북구청 주민 데모가 아닙니다.</p>
    </a>
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
  :root {{ --bg:#fff; --fg:#0d0d0f; --muted:#9b9ba5; --line:#e6e6ea; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans KR","Apple SD Gothic Neo",sans-serif; background:var(--bg); color:var(--fg); -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width: 480px; margin: 0 auto; padding: 100px 20px; text-align:center; }}
  h1 {{ font-size: 3.6rem; margin: 0 0 8px; font-weight:600; color:var(--muted); }}
  p {{ color: var(--muted); }}
  .btns {{ display:flex; gap:10px; justify-content:center; flex-wrap:wrap; margin-top:24px; }}
  .btn {{ display:inline-block; padding:10px 18px; border-radius:18px; text-decoration:none; color:var(--fg); background:var(--bg); border:1px solid var(--line); font-size:.9rem; }}
  .btn:hover {{ background:#f5f5f7; border-color:#d0d0d5; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>404</h1>
  <p>요청하신 페이지를 찾을 수 없습니다.</p>
  <div class="btns">
    <a class="btn" href="index.html">홈으로</a>
    <a class="btn" href="mobile.html">모바일</a>
    <a class="btn" href="admin.html">운영자</a>
  </div>
</div>
</body>
</html>
"""


def build_mvp_entry_html(is_live: bool = False) -> str:
    """Build the public first-use MVP entry at ``/mvp/``.

    In **static** mode (default): injects a query sanitizer that strips any
    query string (e.g. ``?mvp=1``) via ``history.replaceState`` so the shell
    can never enter live bridge/API mode from the public entry.

    In **live** mode: injects a script that forces ``?mvp=1`` in the URL via
    ``history.replaceState`` so that ``citizen-first-use-shell.js`` loads the
    MVP bridge even when the user arrives without the query string.

    The source template is never modified.
    """
    source = _read_file(os.path.join(STATIC_DIR, "citizen-action-demo.html"))
    if is_live:
        return _inject_after_body_open(source, MVP_MODE_INJECTOR)
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
        '<option value="snapshot-demo" selected>정적 안내 · 데이터 고정</option>'
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
def build(out_dir: str | None = None, mode: str = "static") -> None:
    _ensure_repo_on_path()
    from scripts.generate_bukgu_official_snapshots import check_generated_artifacts

    stale_snapshot_artifacts = check_generated_artifacts()
    if stale_snapshot_artifacts:
        stale = ", ".join(str(path.relative_to(_REPO_ROOT)) for path in stale_snapshot_artifacts)
        raise RuntimeError(
            "generated official snapshot artifacts are stale; run "
            f"python scripts/generate_bukgu_official_snapshots.py ({stale})"
        )

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

    # 4. Bake snapshot data + shim (only in static mode).
    if mode == "static":
        snapshot_js = build_snapshot_data_js(snapshot, profile, demo_profiles, site_name)
        shim_js = build_static_api_shim(snapshot, profile, demo_profiles, site_name)
        _write_file(os.path.join(dist_root, "snapshot-data.js"), snapshot_js)
        _write_file(os.path.join(dist_root, "static-api-shim.js"), shim_js)
        print("[build] wrote snapshot-data.js + static-api-shim.js")
    else:
        print("[build] live mode: skipping snapshot-data.js + static-api-shim.js")

    # 5. Emit the landing page.
    index_html = build_index_html(demo_profiles, is_live=(mode == "live"))
    _write_file(os.path.join(dist_root, "index.html"), index_html)
    print("[build] wrote index.html")

    # 6. Emit a static 404 page (no external calls).
    _write_file(os.path.join(dist_root, "404.html"), build_404_html(site_name))
    print("[build] wrote 404.html")

    # 7. Copy + adapt the two demo templates (inject shim in static mode, or
    #    adapt for live API in live mode; keep originals intact).
    mobile_html = _read_file(os.path.join(TEMPLATES_DIR, "mobile_demo.html"))
    admin_html = _read_file(os.path.join(TEMPLATES_DIR, "admin_demo.html"))

    if mode == "static":
        # Static mode: inject the shim scripts after <body> open.
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

        # The admin demo keeps the model-preset select enabled for testing.
        admin_out = _inject_after_body_open(admin_html, admin_snippet)
    else:
        # Live mode: no shim, use live /api/mvp/ask endpoint.
        # Substitute {{site_name}} in mobile template.
        mobile_out = substitute_site_name(mobile_html, site_name)
        # Change API_ENDPOINT from /api/ask to /api/mvp/ask.
        mobile_out = mobile_out.replace(
            "var API_ENDPOINT = '/api/ask';",
            "var API_ENDPOINT = '/api/mvp/ask';",
        )
        # Admin: substitute {{site_name}} and keep model select enabled for live use.
        admin_out = substitute_site_name(admin_html, site_name)
        # No shim injection. Admin fetches /api/info and /api/test will fail on
        # Cloudflare Pages (only /api/mvp/ask is proxied), but that is acceptable
        # for a developer tool in live mode.

    _write_file(os.path.join(dist_root, "mobile.html"), mobile_out)
    _write_file(os.path.join(dist_root, "admin.html"), admin_out)
    print("[build] wrote mobile.html + admin.html (templates copied, shim injected)")

    # 8. Emit a public first-use MVP entry at /mvp/.
    #    In static mode: backend-free, query-sanitized (strips ?mvp=1).
    #    In live mode: forces ?mvp=1 so the shell loads the MVP bridge
    #    even when the user arrives without the query string.
    mvp_index = os.path.join(dist_root, "mvp", "index.html")
    _write_file(mvp_index, build_mvp_entry_html(mode == "live"))
    print(
        f"[build] wrote mvp/index.html "
        f"({'live, ?mvp=1 forced' if mode == 'live' else 'public entry, query-sanitized'})"
    )

    # 9. Copy examples (Page Agent lab) verbatim - isolated, no build-time
    #    processing. The lab is an independent experiment not connected to
    #    the Buk-gu MVP or its live bridge.
    examples_src = os.path.join(EXAMPLES_DIR, "page-agent")
    if os.path.isdir(examples_src):
        _copy_tree(examples_src, os.path.join(dist_root, "examples", "page-agent"))
        print("[build] copied examples/page-agent")

    print(f"[build] done -> {dist_root}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build Cloudflare Pages deployment from Buk-gu MVP."
    )
    parser.add_argument(
        "--mode",
        choices=["static", "live"],
        default="live",
        help="Build mode: live (LLM-backed, deployment default) or static (offline fallback)",
    )
    args = parser.parse_args()
    build(mode=args.mode)
