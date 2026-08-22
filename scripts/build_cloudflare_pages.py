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
        index.html            # canonical citizen assistant + official canvas (#1068)
        mvp/index.html        # compatibility alias of the same citizen entry
        internal/index.html   # secondary operator/developer artifact index
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
from pathlib import Path

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, ".."))
_SYS_PATH_SET = False

# Characters safe to inline verbatim into both HTML text nodes and a JS
# single-quoted string (no quotes/angle-brackets/backslashes/ampersands).
_SAFE_STATIC_RE = re.compile(r"^[가-힣A-Za-z0-9\s\-_,.()/:·]*$")


def _ensure_repo_on_path() -> None:
    """Put this repo first and drop foreign PYTHONPATH ``src`` packages."""
    global _SYS_PATH_SET
    cleaned: list[str] = [_REPO_ROOT]
    for entry in sys.path:
        if not entry or entry == _REPO_ROOT:
            continue
        path = Path(entry)
        try:
            if (path / "src" / "__init__.py").is_file():
                continue
            if path.name == "src" and (path / "__init__.py").is_file():
                continue
        except OSError:
            pass
        cleaned.append(entry)
    sys.path[:] = cleaned
    for key in list(sys.modules):
        if key == "src" or key.startswith("src."):
            mod = sys.modules[key]
            file_hint = getattr(mod, "__file__", "") or ""
            if file_hint and not file_hint.startswith(_REPO_ROOT):
                del sys.modules[key]
            elif key == "src":
                paths = list(getattr(mod, "__path__", []) or [])
                if paths and not any(p.startswith(_REPO_ROOT) for p in paths):
                    del sys.modules[key]
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
# only. Strip the live-bridge flag (?mvp=1) with replaceState BEFORE
# citizen-first-use-shell.js runs, so the shell never enters live bridge/API
# mode. Preserve other params (notably `lang` for #1143, plus journey state).
# No network/redirect/provider call is made.
MVP_QUERY_SANITIZER = (
    '<script>\n'
    '(function () {\n'
    '  "use strict";\n'
    "  if (!window.location.search || !window.history || !window.history.replaceState) return;\n"
    "  var u = new URL(window.location.href);\n"
    "  if (!u.searchParams.has(\"mvp\")) return;\n"
    "  u.searchParams.delete(\"mvp\");\n"
    "  window.history.replaceState(null, \"\", u.pathname + u.search + u.hash);\n"
    "})();\n"
    "</script>"
)

# Live mode MVP entry injects ?mvp=1 via replaceState so that
# citizen-first-use-shell.js loads the MVP bridge even when the user
# arrives without the query string. Other params (e.g. lang) are preserved.
MVP_MODE_INJECTOR = (
    '<script>\n'
    '(function () {\n'
    '  "use strict";\n'
    "  if (window.history && window.history.replaceState) {\n"
    "    var u = new URL(window.location.href);\n"
    "    u.searchParams.set(\"mvp\", \"1\");\n"
    "    window.history.replaceState(null, \"\", u.pathname + u.search + u.hash);\n"
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


def build_internal_artifacts_html(profiles: list[dict], is_live: bool = False) -> str:
    """Build a secondary internal artifact index (#1068).

    This is **not** the resident root. Operator / developer surfaces live
    here so ``/`` can open the citizen assistant without an equal-choice
    artifact chooser. Direct URLs (``/mvp/``, ``/mobile.html``, …) stay valid.

    If *is_live* is True, the MVP card link includes ``?mvp=1`` so that the
    shell loads the live MVP bridge from the internal index link as well.
    """
    mvp_href = "../mvp/?mvp=1" if is_live else "../mvp/"
    _ = profiles  # reserved for future operator profile listing
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>내부 도구 · 400 AI 파인더</title>
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
  .note {{ margin-top: 28px; font-size:.82rem; color:var(--muted); line-height:1.45; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>내부 도구</h1>
  <div class="sub">운영·개발용 경로입니다. 주민용 안내는 사이트 루트에서 바로 이용합니다.</div>
  <div class="cards">
    <a class="card" href="{mvp_href}">
      <h2>시민 AI 안내 (호환 경로)</h2>
      <p>루트와 동일한 북구청 시민 AI 안내 화면 — /mvp/ 호환 진입.</p>
    </a>
    <a class="card" href="../examples/page-agent/resident/">
      <h2>Page Agent형 AI 북구청</h2>
      <p>주민용 비교 경로 — 실제 Page Agent 조작은 Stage 2에서 제공됩니다.</p>
    </a>
    <a class="card" href="../mobile.html">
      <h2>모바일 챗 안내</h2>
      <p>자연어 질문으로 관련 메뉴를 찾는 별도 챗 화면.</p>
    </a>
    <a class="card" href="../admin.html">
      <h2>운영자 화면</h2>
      <p>사이트 프로필 · 질문 테스트 · 상태 확인</p>
    </a>
  </div>
  <div class="note">
    <a href="../examples/page-agent/" style="color:inherit;text-decoration:underline;">Page Agent 개발자 실험실</a>
    — 브라우저 안에서 페이지 요소를 조작하는 독립 오프라인 기술 실험
  </div>
</div>
</body>
</html>
"""


def build_index_html(profiles: list[dict], is_live: bool = False) -> str:
    """Deprecated name kept for imports: builds the *internal* artifact index.

    #1068 moved the equal-choice artifact cards off the resident root. Call
    ``build_mvp_entry_html`` for the citizen entry written to ``index.html``.
    """
    return build_internal_artifacts_html(profiles, is_live=is_live)


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
    """Build the citizen first-use assistant entry (#1068 root + ``/mvp/``).

    The same HTML is written to both ``/`` (canonical resident entry) and
    ``/mvp/`` (compatibility path). No duplicate template is maintained.

    In **static** mode (default): injects a query sanitizer that removes only
    the live-bridge flag (``mvp``) via ``history.replaceState`` so the shell
    can never enter live bridge/API mode from the public entry, while
    preserving other params such as ``lang`` (#1143).

    In **live** mode: injects a script that forces ``?mvp=1`` in the URL via
    ``history.replaceState`` (preserving other params) so that
    ``citizen-first-use-shell.js`` loads the MVP bridge even when the user
    arrives without the query string.

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
def build_seogu_reference_clone(dist_root: str) -> None:
    """Emit the #1303 G2-B faithful-clone candidate under dist/seogu.

    Reads the committed G2-A ``clone-model.json`` and G2-B
    ``visual-contract.json``, VALIDATES the visual contract against the model,
    then renders the generic local clone structure via
    ``src/official_clone/reference_clone_renderer.py``. Fully offline; does not
    touch the Buk-gu root or any G0 artifact.

    Fail-closed: raises RuntimeError if the model or the visual contract is
    missing, or if the visual contract fails identity/checksum/schema/
    provenance validation against the model.
    """
    import importlib

    # Ensure the official_clone package is importable.
    _src = os.path.join(_REPO_ROOT, "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

    renderer = importlib.import_module("official_clone.reference_clone_renderer")
    validator = importlib.import_module("official_clone.visual_contract")

    model_path = os.path.join(
        _REPO_ROOT,
        "data",
        "official_clone_fixtures",
        "seogu_gwangju",
        "g1",
        "20260812T231018-0900",
        "clone-model.json",
    )
    vc_path = os.path.join(
        _REPO_ROOT,
        "data",
        "official_clone_visual_inputs",
        "seogu_gwangju",
        "g1",
        "20260812T231018-0900",
        "visual-contract.json",
    )
    if not os.path.isfile(model_path):
        raise RuntimeError(f"G2-B fail-closed: model not found: {model_path}")
    if not os.path.isfile(vc_path):
        raise RuntimeError(f"G2-B fail-closed: visual contract not found: {vc_path}")
    model = renderer.load_model(model_path)
    contract = json.loads(Path(vc_path).read_text(encoding="utf-8"))
    validated = validator.validate_visual_contract(contract, model)
    written = renderer.write_site(
        model,
        os.path.join(dist_root, "seogu"),
        route_prefix="/seogu/",
        visual_contract=validated,
    )
    print(f"[build] wrote {len(written)} G2-B clone routes -> seogu/")
    print(f"[build] G2-B faithful_ready={validator.faithful_ready(validated)}")


def enrich_seogu_home_assets(dist_root: str) -> None:
    """#1389 — bind owner-authorized verified official-site assets into the
    Seo-gu home clone surface.

    The G2-B renderer deliberately emits flat placeholder blocks for imagery
    (pending-asset lifecycle). This step replaces those placeholders on the
    HOME surface only (``seogu/index.html``) with the committed, hash-verified
    local assets under ``/static/seogu-assets/`` and enables the captured
    official webfonts (Gmarket Sans / Noto Sans CJK KR — the families the
    clone already declares).

    Owner authorization: 2026-08-22 (#1389). Asset provenance:
    ``data/official_captures/seogu_gwangju/g2_home_assets/20260822/manifest.json``
    (every body sha256-verified against the g1 20260812 manifest; all 100/100
    matched at re-capture time). Deterministic + offline: assets are
    committed, no runtime external fetch. Other routes and the Buk-gu root
    are untouched.

    #1383 R2 fidelity repairs (owner defect directive 2026-08-22): rebind the
    brand calligraphy slot to its real artwork, restructure the mayor hero
    into the captured two-column composition (calligraphy / name / CTA pair /
    SMS badge), convert utility SNS entries to their official icon marks,
    reshape the brand search control, and rebuild the key-visual overlay
    (rounded banner, info chips, dark pager pill). Crop provenance:
    ``data/official_captures/seogu_gwangju/g3_home_fidelity_crops/20260822/provenance.json``.
    """
    index_path = os.path.join(dist_root, "seogu", "index.html")
    if not os.path.isfile(index_path):
        raise RuntimeError(f"#1389 fail-closed: home route missing: {index_path}")
    html = open(index_path, encoding="utf-8").read()

    IMG = "/static/seogu-assets/img/"
    inline_map = [
        ("rc-key-visual-placeholder", ["keyvisual.jpg"]),
        ("rc-story-image-placeholder", ["story_1.jpg", "story_2.jpg"]),
        ("rc-lower-placeholder", ["sns_card1.png", "news_banner.jpg"]),
    ]
    for cls, files in inline_map:
        pattern = re.compile(r'(class="[^"]*' + cls + r'[^"]*")')
        matches = list(pattern.finditer(html))
        if len(matches) != len(files):
            raise RuntimeError(
                f"#1389 fail-closed: expected {len(files)} '{cls}' in home route, "
                f"found {len(matches)}"
            )
        out, last = [], 0
        for m, fname in zip(matches, files):
            out.append(html[last:m.end()])
            out.append(f' style="background:url({IMG}{fname}) center/cover no-repeat;"')
            last = m.end()
        out.append(html[last:])
        html = "".join(out)

    # --- #1383 R2: DOM surgeries on the home surface ---
    hero_old = '<div class="rc-hero">#착한도시 서구 김이강 서구청장 입니다.</div>'
    hero_new = (
        '<div class="rc-hero">'
        + f'<img class="rc-hero-cal" src="{IMG}hero-calligraphy.png" alt="#착한도시 서구">'
        + '<span class="rc-hero-name"><em>김이강</em>서구청장 입니다.</span></div>'
    )
    if html.count(hero_old) != 1:
        raise RuntimeError(
            f"#1383 fail-closed: expected 1 mayor hero block, found {html.count(hero_old)}"
        )
    html = html.replace(hero_old, hero_new, 1)

    kv_old = (
        f'style="background:url({IMG}keyvisual.jpg) center/cover no-repeat;"'
    )
    kv_new = (
        f'style="background:url({IMG}keyvisual.jpg) center/100% 100% no-repeat;"'
    )
    if html.count(kv_old) != 1:
        raise RuntimeError(
            f"#1383 fail-closed: expected 1 key-visual inline style, found {html.count(kv_old)}"
        )
    html = html.replace(kv_old, kv_new, 1)

    chips = (
        '<div class="rc-kv-chip rc-kv-chip-l" aria-hidden="true">시민 누구나 이용 가능</div>'
        '<div class="rc-kv-chip rc-kv-chip-r" aria-hidden="true">관내 주요 건널목 20개소<br>장소 확인하기</div>'
    )
    ctrl_open = '<div class="rc-primary-slider-controls">'
    if html.count(ctrl_open) != 1:
        raise RuntimeError(
            f"#1383 fail-closed: expected 1 primary slider controls, found {html.count(ctrl_open)}"
        )
    ctrl_pat = re.compile(re.escape(ctrl_open) + r".*?</div>", re.S)
    controls = ctrl_pat.search(html)
    if not controls:
        raise RuntimeError("#1383 fail-closed: slider controls block not found")
    block = (
        ctrl_open
        + '<span class="rc-pager-count" aria-hidden="true">1/4</span>'
        + controls.group(0)[len(ctrl_open):]
    )
    html = html[: controls.start()] + html[controls.end():]
    ph_pat = re.compile(r'(<div class="rc-key-visual-placeholder"[^>]*>)(\s*</div>)')
    if not ph_pat.search(html):
        raise RuntimeError("#1383 fail-closed: key-visual placeholder body not found")
    html = ph_pat.subn(lambda m: m.group(1) + chips + block + m.group(2), html, count=1)[0]

    search_pat = re.compile(r'(<span class="[^"]*rc-search-part"[^>]*>)검색(</span>)')
    if len(search_pat.findall(html)) != 2:
        raise RuntimeError(
            f"#1383 fail-closed: expected 2 search parts, found {len(search_pat.findall(html))}"
        )
    html = search_pat.sub(
        lambda m: m.group(1) + "검색어를 입력해 주세요" + m.group(2), html, count=1
    )

    # Quick cards carry their icon on a ::before block; assign per-card via
    # nth-of-type so the DOM stays untouched.
    quick_rules = [
        f".rc-quick-card:nth-of-type({i}):before{{background:url({IMG}quick_{i:02d}.png) center/contain no-repeat;}}"
        for i in range(1, 16)
    ]
    font_faces = (
        "@font-face{font-family:'Gmarket Sans';font-weight:300;font-display:swap;"
        "src:url('/static/seogu-assets/fonts/font_1.woff2') format('woff2');}"
        "@font-face{font-family:'Gmarket Sans';font-weight:500;font-display:swap;"
        "src:url('/static/seogu-assets/fonts/font_2.woff2') format('woff2');}"
        "@font-face{font-family:'Gmarket Sans';font-weight:700;font-display:swap;"
        "src:url('/static/seogu-assets/fonts/font_3.woff2') format('woff2');}"
        "@font-face{font-family:'Noto Sans CJK KR';font-weight:350;font-display:swap;"
        "src:url('/static/seogu-assets/fonts/font_4.woff2') format('woff2');}"
        "@font-face{font-family:'Noto Sans CJK KR';font-weight:500;font-display:swap;"
        "src:url('/static/seogu-assets/fonts/font_5.woff2') format('woff2');}"
        "@font-face{font-family:'Noto Sans CJK KR';font-weight:700;font-display:swap;"
        "src:url('/static/seogu-assets/fonts/font_6.woff2') format('woff2');}"
    )
    style_block = (
        '<style id="seogu-home-assets">#1389-official-asset-bind{}'
        + font_faces
        + ".rc-site-emblem{background:#1663b6 url(" + IMG + "emblem.png) center/contain no-repeat;}"
        + ".rc-brand-slogan{background:url(" + IMG + "slogan.png) left center/auto 100% no-repeat;color:transparent;font-size:1px;line-height:0;min-width:220px;}"
        + ".rc-section01{grid-template-columns:minmax(0,40%) minmax(0,60%);}"
        + ".rc-mayor-panel{background:#f0f0ff url(" + IMG + "mayor_section.png) left bottom/auto 88% no-repeat;padding-left:14px;}"
        + ".rc-hero{font-size:23px;white-space:normal;max-width:none;text-shadow:0 1px 3px rgba(240,240,255,.9);}"
        + "body,.rc-header-inner,.rc-main{font-family:'Gmarket Sans','Noto Sans CJK KR',"
        + "'Apple SD Gothic Neo','Malgun Gothic',ui-sans-serif,system-ui,sans-serif;}"
        + "".join(quick_rules)
        + "</style>"
    )
    r2_rules = [
        # D1 utility bar: compact left list with separators, icon SNS marks.
        ".rc-utility-inner{max-width:1400px;margin:0 auto;padding-left:20px;padding-right:20px;}",
        ".rc-utility-left{gap:0;color:#555555;}",
        ".rc-utility-left .rc-utility-item{font-size:13px;}",
        ".rc-utility-left .rc-utility-item+.rc-utility-item{margin-left:12px;padding-left:13px;border-left:1px solid #dddddd;}",
        ".rc-utility-right{gap:9px;}",
        ".rc-utility-right>.btn.rc-utility-item{width:auto;height:auto;border-radius:0;background:none;margin-right:16px;font-size:13px;color:#555555;}",
        ".rc-utility-right>.btn.rc-utility-item:after{content:'\\2304';margin-left:4px;font-size:11px;}",
        ".rc-utility-right>.rc-utility-item{width:24px;height:24px;padding:0;justify-content:center;font-size:0;border-radius:50%;background-position:center;background-size:contain;background-repeat:no-repeat;}",
        ".rc-gnb .rc-stub{color:#111111;font-weight:700;font-size:16px;}",
        f".rc-utility-right>.facebook{{background-image:url({IMG}sns-facebook.png);}}",
        f".rc-utility-right>.kakaoch{{background-image:url({IMG}sns-kakaoch.png);}}",
        f".rc-utility-right>.kakaostory{{background-image:url({IMG}sns-kakaostory.png);}}",
        f".rc-utility-right>.band{{background-image:url({IMG}sns-band.png);}}",
        f".rc-utility-right>.naver{{background-image:url({IMG}sns-naver.png);}}",
        f".rc-utility-right>.instagram{{background-image:url({IMG}sns-instagram.png);}}",
        f".rc-utility-right>.youtube{{background-image:url({IMG}sns-youtube.png);}}",
        # D1 brand search: pill input + rounded-square magnifier button.
        ".rc-brand-search{width:360px;max-width:none;height:52px;border-radius:26px;border:1px solid #1663b6;}",
        ".rc-brand-search .rc-search-part:first-child{padding:0 22px;font-size:15px;}",
        ".rc-brand-search .rc-search-part:last-child{width:56px;flex:0 0 56px;border-radius:12px;margin-right:4px;position:relative;font-size:0;}",
        ".rc-brand-search .rc-search-part:last-child:before{content:'';position:absolute;left:17px;top:15px;width:15px;height:15px;border:3px solid #ffffff;border-radius:50%;}",
        ".rc-brand-search .rc-search-part:last-child:after{content:'';position:absolute;left:32px;top:30px;width:9px;height:3px;background:#ffffff;transform:rotate(45deg);border-radius:2px;}",
        # D3 brand calligraphy logo (real artwork, fixed-height slot).
        f".rc-brand-slogan{{background:url({IMG}brand-calligraphy.png) left center/auto 100% no-repeat;color:transparent;font-size:1px;line-height:0;width:254px;min-width:254px;height:52px;}}",
        # D2 mayor hero: captured two-column composition.
        ".rc-section01{grid-template-columns:minmax(0,calc(100% - 820px)) minmax(0,820px);}",
        ".rc-mayor-panel{display:block;padding:44px 22px 0 300px;background:#f0f0ff url(" + IMG + "mayor_section.png) left 10px bottom 12px/auto 86% no-repeat;}",
        ".rc-hero{display:flex;flex-direction:column;gap:12px;font-size:32px;line-height:1.28;font-weight:700;color:#111111;text-shadow:none;max-width:none;white-space:normal;}",
        ".rc-hero-cal{display:block;width:222px;height:auto;}",
        ".rc-hero-name em{font-style:normal;display:block;color:#1663b6;font-size:27px;margin-bottom:4px;}",
        ".rc-mayor-actions{flex-wrap:wrap;gap:2px;margin-top:14px;}",
        ".rc-mayor-action:nth-child(-n+2){border-radius:4px;min-height:72px;max-width:128px;padding:8px 10px;font-size:14px;font-weight:600;line-height:1.35;white-space:normal;word-break:keep-all;}",
        ".rc-mayor-action:nth-child(1){background:#2a9757;}",
        ".rc-mayor-action:nth-child(-n+2):after{content:'>';margin-left:8px;font-weight:400;}",
        ".rc-mayor-action:nth-child(3){flex:0 0 auto;margin-top:10px;width:260px;min-height:115px;height:115px;padding:0;font-size:0;font-weight:400;background:url(" + IMG + "sms-badge.png) left center/contain no-repeat;justify-content:flex-start;}",
        ".rc-banner{margin-top:12px;}",
        ".hns_bn{font-size:15px;font-weight:500;color:#1663b6;}",
        # D4 key visual: rounded banner, flat navy overlay strip with info
        # chips and a dark pager pill (all live DOM, no baked text).
        ".rc-key-visual-placeholder{position:relative;height:375px;border-radius:16px;overflow:hidden;}",
        ".rc-key-visual-placeholder:after{content:'';position:absolute;left:0;right:0;bottom:0;height:72px;background:#083d7f;}",
        ".rc-kv-chip{position:absolute;display:flex;align-items:center;gap:10px;color:#ffffff;font-size:15px;line-height:1.3;z-index:2;}",
        ".rc-kv-chip:before{content:'';width:38px;height:38px;border-radius:50%;background-position:center;background-size:contain;background-repeat:no-repeat;flex:0 0 auto;}",
        ".rc-kv-chip-l{left:14px;bottom:17px;}",
        f".rc-kv-chip-l:before{{background-image:url({IMG}kv-chip-people.png);}}",
        ".rc-kv-chip-r{right:18px;bottom:11px;max-width:250px;text-align:left;align-items:flex-start;}",
        f".rc-kv-chip-r:before{{background-image:url({IMG}kv-chip-pin.png);}}",
        ".rc-primary-slider-controls{left:50%;bottom:18px;transform:translateX(-50%);background:#091f4b;border-radius:19px;height:38px;padding:0 24px;gap:16px;font-size:0;z-index:3;}",
        ".rc-pager-count{font-size:13px;color:#ffffff;font-weight:700;letter-spacing:.5px;}",
        ".prev,.pause,.next{color:#ffffff;font-size:0;width:auto;height:auto;}",
        ".prev:before,.next:before{font-size:15px;}",
        ".prev:before{content:'\\2190';}",
        ".next:before{content:'\\2192';}",
        ".pause{position:relative;width:12px;height:14px;font-size:0;}",
        ".pause:before,.pause:after{content:'';position:absolute;top:0;width:3px;height:12px;background:#ffffff;}",
        ".pause:before{left:1px;}",
        ".pause:after{right:1px;}",
    ]
    r2_style = (
        '<style id="seogu-home-fidelity-r2">#1383-home-fidelity-r2{}'
        + "".join(r2_rules)
        + "</style>"
    )

    if "</head>" not in html:
        raise RuntimeError("#1389 fail-closed: </head> not found in home route")
    html = html.replace("</head>", style_block + r2_style + "</head>", 1)

    open(index_path, "w", encoding="utf-8").write(html)
    print("[build] #1389 enriched Seo-gu home surface with verified official assets")


def build_seogu_housing_addon(dist_root: str) -> None:
    """Emit the additive #1343 S3 housing route under dist/seogu/housing/.

    The committed 11-state G2-B baseline (capture-id ``20260812T231018-0900``)
    is immutable: its visual contract is checksum-pinned to that model, so a
    full re-capture would break the fail-closed visual-contract gates and the
    regression tests. Round 2 therefore authorizes a SEPARATE, additive
    bounded capture for the S3 공동주택 canonical scenario (capture-id
    ``20260818T060400-0900``), which renders exactly one route
    (``/seogu/housing/``) and never clobbers the baseline routes.

    Fully offline; reads only the committed additive clone-model.json.
    ``write_site`` writes only the routes present in the model, so the baseline
    subtree is untouched. Rendered with ``visual_contract=None`` because the
    additive capture has its own provenance chain and is not covered by the
    pinned baseline visual contract.
    """
    import importlib

    _src = os.path.join(_REPO_ROOT, "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

    renderer = importlib.import_module("official_clone.reference_clone_renderer")

    model_path = os.path.join(
        _REPO_ROOT,
        "data",
        "official_clone_fixtures",
        "seogu_gwangju",
        "g1",
        "20260818T060400-0900",
        "clone-model.json",
    )
    if not os.path.isfile(model_path):
        raise RuntimeError(f"S3 housing fail-closed: additive model not found: {model_path}")
    model = renderer.load_model(model_path)
    written = renderer.write_site(
        model,
        os.path.join(dist_root, "seogu"),
        route_prefix="/seogu/",
        visual_contract=None,
    )
    routes = sorted(
        (str(w.relative_to(Path(dist_root))) if hasattr(w, "relative_to") else str(w))
        for w in written
    )
    print(f"[build] wrote {len(written)} additive S3 housing route(s) -> seogu/housing/ : {routes}")


def build_seogu_handoff_addon(dist_root: str) -> None:
    """Emit the additive #1343 S2/S7/S8 handoff evidence routes under /seogu/.

    Final-addendum bounded capture (capture-id ``20260818T080808-0900``) for
    the generic ``EXTERNAL_OFFICIAL_HANDOFF`` local-evidence routes:

    * ``/seogu/illegal-parking-report/``      (S2 trafficminwon negative evidence)
    * ``/seogu/streetlight-report-handoff/``  (S7 disaster-report center)
    * ``/seogu/litter-report-handoff/``       (S8 household-waste guidance)

    Additive only: ``write_site`` writes only the routes present in this model,
    so the pinned 11-state baseline and the S3 housing route are untouched.
    Fully offline; reads only the committed additive clone-model.json.
    """
    import importlib

    _src = os.path.join(_REPO_ROOT, "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

    renderer = importlib.import_module("official_clone.reference_clone_renderer")

    model_path = os.path.join(
        _REPO_ROOT,
        "data",
        "official_clone_fixtures",
        "seogu_gwangju",
        "g1",
        "20260818T080808-0900",
        "clone-model.json",
    )
    if not os.path.isfile(model_path):
        raise RuntimeError(f"S2/S7/S8 handoff fail-closed: additive model not found: {model_path}")
    model = renderer.load_model(model_path)
    written = renderer.write_site(
        model,
        os.path.join(dist_root, "seogu"),
        route_prefix="/seogu/",
        visual_contract=None,
    )
    routes = sorted(
        (str(w.relative_to(Path(dist_root))) if hasattr(w, "relative_to") else str(w))
        for w in written
    )
    print(f"[build] wrote {len(written)} additive S2/S7/S8 handoff evidence route(s) -> seogu/ : {routes}")


def build_seogu_passport_addon(dist_root: str) -> None:
    """Emit the additive #1356 S5 passport-guidance route under /seogu/.

    Bounded one-page official Seo-gu passport guidance capture (capture-id
    ``20260820T011047-0900``) for the informational-only S5 scenario. Renders
    exactly one route (``/seogu/passport-guidance/``) through the generic
    ``content_page`` model (#1357) so the required markers become
    clone-DOM-verifiable without a bespoke passport renderer.

    Additive only: ``write_site`` writes only the routes present in this
    model, so the pinned 11-state baseline, the S3 housing route, and the
    S2/S7/S8 handoff-evidence routes are untouched. Fully offline; reads only
    the committed additive clone-model.json. Rendered with
    ``visual_contract=None`` because the additive capture has its own
    provenance chain and is not covered by the pinned baseline visual
    contract.
    """
    import importlib

    _src = os.path.join(_REPO_ROOT, "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

    renderer = importlib.import_module("official_clone.reference_clone_renderer")

    model_path = os.path.join(
        _REPO_ROOT,
        "data",
        "official_clone_fixtures",
        "seogu_gwangju",
        "g1",
        "20260820T011047-0900",
        "clone-model.json",
    )
    if not os.path.isfile(model_path):
        raise RuntimeError(f"S5 passport fail-closed: additive model not found: {model_path}")
    model = renderer.load_model(model_path)
    written = renderer.write_site(
        model,
        os.path.join(dist_root, "seogu"),
        route_prefix="/seogu/",
        visual_contract=None,
    )
    routes = sorted(
        (str(w.relative_to(Path(dist_root))) if hasattr(w, "relative_to") else str(w))
        for w in written
    )
    print(f"[build] wrote {len(written)} additive S5 passport-guidance route(s) -> seogu/passport-guidance/ : {routes}")


def build_seogu_unmanned_kiosk_addon(dist_root: str) -> None:
    """Emit the additive #1360 S6 unmanned-kiosk route under /seogu/.

    Bounded one-page official Seo-gu unmanned civil-document kiosk catalog
    capture (capture-id ``20260820T083013-0900``) for the informational-only
    S6 scenario. The page-1 ``list`` board is modelled generically by the
    existing reference-clone model (``kind=list`` with the six source table
    columns), so the required markers become clone-DOM-verifiable through the
    generic renderer with no bespoke kiosk renderer.

    Additive only: ``write_site`` writes only the routes present in this
    model, so the pinned 11-state baseline, the S3 housing route, the
    S2/S7/S8 handoff-evidence routes, and the S5 passport-guidance route are
    untouched. Fully offline; reads only the committed additive
    clone-model.json. Rendered with ``visual_contract=None`` because the
    additive capture has its own provenance chain and is not covered by the
    pinned baseline visual contract.
    """
    import importlib

    _src = os.path.join(_REPO_ROOT, "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

    renderer = importlib.import_module("official_clone.reference_clone_renderer")

    model_path = os.path.join(
        _REPO_ROOT,
        "data",
        "official_clone_fixtures",
        "seogu_gwangju",
        "g1",
        "20260820T083013-0900",
        "clone-model.json",
    )
    if not os.path.isfile(model_path):
        raise RuntimeError(f"S6 kiosk fail-closed: additive model not found: {model_path}")
    model = renderer.load_model(model_path)
    written = renderer.write_site(
        model,
        os.path.join(dist_root, "seogu"),
        route_prefix="/seogu/",
        visual_contract=None,
    )
    routes = sorted(
        (str(w.relative_to(Path(dist_root))) if hasattr(w, "relative_to") else str(w))
        for w in written
    )
    print(f"[build] wrote {len(written)} additive S6 unmanned-kiosk route(s) -> seogu/unmanned-kiosk/ : {routes}")


def build_seogu_mayor_proposal_addon(dist_root: str) -> None:
    """Emit the additive #1363 S7 mayor-proposal guidance route under /seogu/.

    Bounded one-page official Seo-gu resident-proposal (주민제안) guidance
    capture (capture-id ``20260821T111106-0900``) for the
    INFORMATIONAL_PLUS_EXTERNAL_OFFICIAL_HANDOFF scenario. The informational
    participation-method page is modelled generically by the existing
    reference-clone model (``content_page``), so the required markers become
    clone-DOM-verifiable through the generic renderer with no bespoke
    mayor-proposal renderer branch.

    Additive only: ``write_site`` writes only the routes present in this
    model, so the pinned 11-state baseline and all prior additive routes are
    untouched. Fully offline; reads only the committed additive
    clone-model.json. Rendered with ``visual_contract=None`` because the
    additive capture has its own provenance chain and is not covered by the
    pinned baseline visual contract.
    """
    import importlib

    _src = os.path.join(_REPO_ROOT, "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

    renderer = importlib.import_module("official_clone.reference_clone_renderer")

    model_path = os.path.join(
        _REPO_ROOT,
        "data",
        "official_clone_fixtures",
        "seogu_gwangju",
        "g1",
        "20260821T111106-0900",
        "clone-model.json",
    )
    if not os.path.isfile(model_path):
        raise RuntimeError(f"S7 mayor-proposal fail-closed: additive model not found: {model_path}")
    model = renderer.load_model(model_path)
    written = renderer.write_site(
        model,
        os.path.join(dist_root, "seogu"),
        route_prefix="/seogu/",
        visual_contract=None,
    )
    routes = sorted(
        (str(w.relative_to(Path(dist_root))) if hasattr(w, "relative_to") else str(w))
        for w in written
    )
    print(f"[build] wrote {len(written)} additive S7 mayor-proposal route(s) -> seogu/mayor-proposal-guidance/ : {routes}")


def build_seogu_bulky_waste_addon(dist_root: str) -> None:
    """Emit the additive #1376 S8 bulky-waste guidance route under /seogu/.

    Bounded one-page official Seo-gu 대형폐기물 신고 guidance capture
    (capture-id ``20260821T143931-0900``) for the DIRECT_REUSE scenario
    (Phase-A classification A. INFORMATIONAL_DIRECT_REUSE_CANDIDATE). The
    page is modelled generically by the existing reference-clone model
    (``content_page``), so the required markers become clone-DOM-verifiable
    through the generic renderer with no bespoke bulky-waste renderer branch.

    Additive only: ``write_site`` writes only the routes present in this
    model, so the pinned 11-state baseline and all prior additive routes are
    untouched. Fully offline; reads only the committed additive
    clone-model.json. Rendered with ``visual_contract=None`` because the
    additive capture has its own provenance chain and is not covered by the
    pinned baseline visual contract.
    """
    import importlib

    _src = os.path.join(_REPO_ROOT, "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

    renderer = importlib.import_module("official_clone.reference_clone_renderer")

    model_path = os.path.join(
        _REPO_ROOT,
        "data",
        "official_clone_fixtures",
        "seogu_gwangju",
        "g1",
        "20260821T143931-0900",
        "clone-model.json",
    )
    if not os.path.isfile(model_path):
        raise RuntimeError(f"S8 bulky-waste fail-closed: additive model not found: {model_path}")
    model = renderer.load_model(model_path)
    written = renderer.write_site(
        model,
        os.path.join(dist_root, "seogu"),
        route_prefix="/seogu/",
        visual_contract=None,
    )
    routes = sorted(
        (str(w.relative_to(Path(dist_root))) if hasattr(w, "relative_to") else str(w))
        for w in written
    )
    print(f"[build] wrote {len(written)} additive S8 bulky-waste route(s) -> seogu/bulky-waste-guidance/ : {routes}")


def build(out_dir: str | None = None, mode: str = "static") -> None:
    _ensure_repo_on_path()
    from scripts.generate_bukgu_official_snapshots import check_generated_artifacts
    from scripts.generate_bukgu_home_clone_fixture import (
        check_generated_artifacts as check_home_clone_fixture_artifacts,
    )

    stale_snapshot_artifacts = check_generated_artifacts()
    if stale_snapshot_artifacts:
        stale = ", ".join(str(path.relative_to(_REPO_ROOT)) for path in stale_snapshot_artifacts)
        raise RuntimeError(
            "generated official snapshot artifacts are stale; run "
            f"python scripts/generate_bukgu_official_snapshots.py ({stale})"
        )

    stale_home_fixture_artifacts = check_home_clone_fixture_artifacts()
    if stale_home_fixture_artifacts:
        stale = ", ".join(
            str(path.relative_to(_REPO_ROOT)) for path in stale_home_fixture_artifacts
        )
        raise RuntimeError(
            "generated home clone fixture artifacts are stale; run "
            f"python scripts/generate_bukgu_home_clone_fixture.py ({stale})"
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

    # 5. Emit the canonical resident entry at / and the /mvp/ compatibility
    #    path from the same HTML (#1068). No redirect, no duplicate template.
    #    static: backend-free + query sanitizer (strips ?mvp=1).
    #    live: forces ?mvp=1 so the shell loads the MVP bridge.
    citizen_entry = build_mvp_entry_html(mode == "live")
    _write_file(os.path.join(dist_root, "index.html"), citizen_entry)
    mvp_index = os.path.join(dist_root, "mvp", "index.html")
    _write_file(mvp_index, citizen_entry)
    mode_label = "live, ?mvp=1 forced" if mode == "live" else "public entry, query-sanitized"
    print(f"[build] wrote index.html (citizen root, {mode_label})")
    print(f"[build] wrote mvp/index.html (compatibility, {mode_label})")

    # 5b. Secondary internal artifact index — not the resident root.
    internal_html = build_internal_artifacts_html(
        demo_profiles, is_live=(mode == "live")
    )
    _write_file(os.path.join(dist_root, "internal", "index.html"), internal_html)
    print("[build] wrote internal/index.html (operator artifacts)")

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

    # 9. Copy examples (Page Agent lab) verbatim - isolated, no build-time
    #    processing. The lab is an independent experiment not connected to
    #    the Buk-gu MVP or its live bridge.
    examples_src = os.path.join(EXAMPLES_DIR, "page-agent")
    if os.path.isdir(examples_src):
        examples_dst = os.path.join(dist_root, "examples", "page-agent")
        _copy_tree(examples_src, examples_dst)
        # #1170 / #1198: resident embeds civic canvas; fixture + approval gate
        # must load before map/canvas even if a stale examples tree is copied.
        resident_index = os.path.join(examples_dst, "resident", "index.html")
        if os.path.isfile(resident_index):
            with open(resident_index, encoding="utf-8") as handle:
                resident_html = handle.read()
            fixture_tag = (
                '<script src="../../../static/bukgu-home-clone-fixture.js"></script>'
            )
            registry_tag = (
                '<script src="../../../static/clone-renderer-approval-registry.js">'
                "</script>"
            )
            gate_tag = (
                '<script src="../../../static/clone-renderer-approval-gate.js">'
                "</script>"
            )
            map_tag = (
                '<script src="../../../static/citizen-action-demo-map.js"></script>'
            )
            canvas_tag = (
                '<script src="../../../static/citizen-action-demo-canvas.js">'
                "</script>"
            )
            changed = False
            if "bukgu-home-clone-fixture.js" not in resident_html:
                if "bukgu-official-snapshots.js" in resident_html:
                    resident_html = resident_html.replace(
                        '<script src="../../../static/bukgu-official-snapshots.js"></script>',
                        '<script src="../../../static/bukgu-official-snapshots.js"></script>\n'
                        + fixture_tag,
                        1,
                    )
                else:
                    resident_html = resident_html.replace(
                        canvas_tag,
                        fixture_tag + "\n" + canvas_tag,
                        1,
                    )
                changed = True
            if "clone-renderer-approval-registry.js" not in resident_html:
                if "bukgu-home-clone-fixture.js" in resident_html:
                    resident_html = resident_html.replace(
                        fixture_tag,
                        fixture_tag + "\n" + registry_tag,
                        1,
                    )
                else:
                    resident_html = resident_html.replace(
                        map_tag, registry_tag + "\n" + map_tag, 1
                    )
                changed = True
            if "clone-renderer-approval-gate.js" not in resident_html:
                if "clone-renderer-approval-registry.js" in resident_html:
                    resident_html = resident_html.replace(
                        registry_tag,
                        registry_tag + "\n" + gate_tag,
                        1,
                    )
                else:
                    resident_html = resident_html.replace(
                        map_tag, gate_tag + "\n" + map_tag, 1
                    )
                changed = True
            if changed:
                _write_file(resident_index, resident_html)
        print("[build] copied examples/page-agent")

    # 9b. Copy compare (stakeholder comparison gateway) — static page only.
    compare_src = os.path.join(WEB_DIR, "compare")
    if os.path.isdir(compare_src):
        _copy_tree(compare_src, os.path.join(dist_root, "compare"))
        print("[build] copied compare")

    # 9c. Emit the #1303 G2-B Seo-gu faithful-clone candidate under /seogu/.
    #     Generic, model-driven, offline; the Buk-gu root is untouched.
    build_seogu_reference_clone(dist_root)

    # 9c-2. #1389 — bind owner-authorized verified official-site assets
    #     (home imagery + webfonts) into the Seo-gu home clone surface.
    enrich_seogu_home_assets(dist_root)

    # 9d. Emit the additive #1343 S3 housing route under /seogu/housing/.
    #     Separate bounded capture; never clobbers the pinned 11-state baseline.
    build_seogu_housing_addon(dist_root)

    # 9e. Emit the additive #1343 final-addendum S2/S7/S8 handoff evidence
    #     routes under /seogu/. Separate bounded capture; additive only.
    build_seogu_handoff_addon(dist_root)

    # 9f. Emit the additive #1356 S5 passport-guidance route under
    #     /seogu/passport-guidance/. Separate bounded one-page capture;
    #     additive only; never clobbers baseline/housing/handoff routes.
    build_seogu_passport_addon(dist_root)

    # 9g. Emit the additive #1360 S6 unmanned-kiosk route under
    #     /seogu/unmanned-kiosk/. Separate bounded one-page capture;
    #     additive only; never clobbers baseline/housing/handoff/passport routes.
    build_seogu_unmanned_kiosk_addon(dist_root)

    # 9h. Emit the additive #1363 S7 mayor-proposal guidance route under
    #     /seogu/mayor-proposal-guidance/. Separate bounded one-page capture;
    #     additive only; never clobbers baseline/housing/handoff/passport/kiosk
    #     routes.
    build_seogu_mayor_proposal_addon(dist_root)

    # 9i. Emit the additive #1376 S8 bulky-waste guidance route under
    #     /seogu/bulky-waste-guidance/. Separate bounded one-page capture;
    #     additive only; never clobbers baseline or prior additive routes.
    build_seogu_bulky_waste_addon(dist_root)

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
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Optional output directory (default: dist/cloudflare-pages)",
    )
    args = parser.parse_args()
    build(out_dir=args.out_dir, mode=args.mode)
