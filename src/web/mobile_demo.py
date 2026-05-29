"""Mobile-first web demo for AI Homepage Finder.

Serves a responsive mobile UI at http://localhost:8080 with a
POST /api/ask endpoint that returns demo results from SiteDemoRunner.

Usage::

    from src.web.mobile_demo import create_app
    app = create_app(site_id="bukgu_gwangju", snapshot="/tmp/snap.json")
    app.serve_forever()
"""

from __future__ import annotations

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any
from urllib.parse import urlparse, parse_qs


MOBILE_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>AI 홈페이지 도우미 — {{site_name}}</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#f5f6f8;--card:#fff;--primary:#1a56db;--primary-light:#e8eefb;--text:#1f2937;--text2:#6b7280;--border:#e5e7eb;--success:#059669;--warn:#d97706;--radius:12px}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif;background:var(--bg);color:var(--text);line-height:1.6;min-height:100vh;display:flex;justify-content:center}
.container{max-width:480px;width:100%;margin:0 auto;padding:16px}
header{text-align:center;padding:24px 0 16px}
header h1{font-size:1.3rem;font-weight:700;color:var(--text)}
header .badge{display:inline-block;background:var(--primary-light);color:var(--primary);font-size:.75rem;padding:2px 10px;border-radius:20px;margin-top:6px}
.search-box{background:var(--card);border-radius:var(--radius);padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:12px}
.search-box input{width:100%;padding:14px 16px;border:2px solid var(--border);border-radius:10px;font-size:1rem;outline:none;transition:border .2s}
.search-box input:focus{border-color:var(--primary)}
.search-box button{width:100%;margin-top:10px;padding:14px;background:var(--primary);color:#fff;border:none;border-radius:10px;font-size:1rem;font-weight:600;cursor:pointer;transition:opacity .2s}
.search-box button:active{opacity:.85}
.search-box button:disabled{opacity:.5;cursor:not-allowed}
.quick-questions{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.quick-questions button{flex:1 1 calc(50% - 4px);padding:12px 10px;background:var(--card);border:1.5px solid var(--border);border-radius:10px;font-size:.85rem;color:var(--text);cursor:pointer;transition:all .2s;text-align:left;min-width:0}
.quick-questions button:active{background:var(--primary-light);border-color:var(--primary)}
.status{padding:10px 16px;border-radius:10px;margin-bottom:12px;font-size:.85rem;display:none}
.status.loading{display:block;background:#fef3c7;color:var(--warn)}
.status.error{display:block;background:#fee2e2;color:#dc2626}
.status.info{display:block;background:#ecfdf5;color:var(--success)}
.result{display:none}
.result.show{display:block}
.question-echo{background:var(--primary-light);border-radius:10px;padding:12px 16px;margin-bottom:12px;font-size:.9rem;color:var(--primary);font-weight:500}
.question-echo::before{content:"💬 ";font-size:1rem}
.answer-card{background:var(--card);border-radius:var(--radius);padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:12px}
.answer-card h3{font-size:.9rem;color:var(--text2);margin-bottom:8px}
.answer-card .answer-text{font-size:.95rem;line-height:1.8;white-space:pre-wrap}
.answer-card .answer-text h2{font-size:1.05rem;margin:12px 0 6px;color:var(--text)}
.answer-card .answer-text ul{padding-left:1.2em;margin:6px 0}
.sources-section h3{font-size:.9rem;color:var(--text2);margin-bottom:8px;padding:0 4px}
.source-card{display:block;background:var(--card);border-radius:var(--radius);padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:8px;text-decoration:none;color:inherit;transition:transform .1s,box-shadow .1s}
.source-card:active{transform:scale(.99);box-shadow:0 2px 6px rgba(0,0,0,.12)}
.source-card .source-title{font-size:.95rem;font-weight:600;color:var(--primary);margin-bottom:4px}
.source-card .source-url{font-size:.75rem;color:var(--text2);word-break:break-all;margin-bottom:6px}
.source-card .source-meta{display:flex;gap:6px;flex-wrap:wrap}
.source-card .tag{font-size:.7rem;padding:2px 8px;border-radius:12px;background:var(--primary-light);color:var(--primary)}
.source-card .go-arrow{float:right;font-size:.85rem;color:var(--primary);margin-top:2px}
.guide-note{text-align:center;padding:10px;font-size:.78rem;color:var(--text2);margin-bottom:12px}
footer{text-align:center;padding:24px 0;font-size:.75rem;color:var(--text2)}
@media(min-width:768px){.container{padding:32px 24px;max-width:520px}header h1{font-size:1.6rem}}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🏛️ {{site_name}}</h1>
    <div class="badge">AI 홈페이지 도우미</div>
  </header>

  <div class="search-box">
    <input type="text" id="question" placeholder="예: 민원서식 어디서 받아?" autocomplete="off">
    <button id="askBtn" onclick="ask()">질문하기</button>
  </div>

  <div class="quick-questions" id="quickQ">
    <button onclick="quickAsk(this)">민원서식 어디서 받아?</button>
    <button onclick="quickAsk(this)">교육접수는 어디서 해?</button>
    <button onclick="quickAsk(this)">정보공개는 어디서 볼 수 있어?</button>
    <button onclick="quickAsk(this)">고시공고는 어디서 확인해?</button>
  </div>

  <div class="status" id="status"></div>

  <div class="result" id="result">
    <div class="question-echo" id="questionEcho"></div>
    <div class="answer-card">
      <h3>안내</h3>
      <div class="answer-text" id="answerText"></div>
    </div>
    <div class="sources-section">
      <h3 id="sourcesTitle">관련 홈페이지 바로가기</h3>
      <div id="sourcesList"></div>
    </div>
    <div class="guide-note" id="guideNote"></div>
  </div>

  <footer>
    AI 홈페이지 파인더 · {{site_name}} 안내 서비스
  </footer>
</div>

<script>
const q = document.getElementById('question');
const btn = document.getElementById('askBtn');
const statusEl = document.getElementById('status');
const resultEl = document.getElementById('result');
const answerEl = document.getElementById('answerText');
const sourcesEl = document.getElementById('sourcesList');
const sourcesTitle = document.getElementById('sourcesTitle');
const questionEcho = document.getElementById('questionEcho');
const guideNote = document.getElementById('guideNote');

q.addEventListener('keydown', e => { if(e.key==='Enter') ask(); });

function quickAsk(el){ q.value = el.textContent; ask(); }

function showStatus(msg, cls){
  statusEl.textContent = msg;
  statusEl.className = 'status ' + cls;
}
function hideStatus(){ statusEl.className = 'status'; }

async function ask(){
  const question = q.value.trim();
  if(!question){ showStatus('질문을 입력해 주세요.','error'); return; }

  btn.disabled = true;
  btn.textContent = '확인 중…';
  showStatus('질문을 확인하고 관련 메뉴를 찾고 있어요…','loading');
  resultEl.classList.remove('show');

  try {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({question})
    });
    const data = await res.json();

    if(data.error){ showStatus('❌ ' + data.error, 'error'); return; }

    // Status — user-friendly
    hideStatus();

    // Question echo
    questionEcho.textContent = data.question || question;

    // Answer
    answerEl.innerHTML = renderMarkdown(data.answer || '답변을 생성하지 못했습니다.');

    // Sources — "관련 홈페이지 바로가기"
    const srcCount = (data.sources||[]).length;
    sourcesTitle.textContent = '관련 홈페이지 바로가기' + (srcCount > 0 ? ' (' + srcCount + '건)' : '');
    sourcesEl.innerHTML = '';
    (data.sources||[]).forEach(s => {
      const card = document.createElement('a');
      card.className = 'source-card';
      card.href = s.url || '#';
      card.target = '_blank';
      card.rel = 'noopener';
      card.innerHTML =
        '<span class="go-arrow">이동 ›</span>' +
        '<div class="source-title">' + esc(s.title||'바로가기') + '</div>' +
        '<div class="source-url">' + esc(s.url||'') + '</div>' +
        '<div class="source-meta">' +
          '<span class="tag">' + esc(s.source_type||'web') + '</span>' +
        '</div>';
      sourcesEl.appendChild(card);
    });

    // Guide note
    guideNote.textContent = '홈페이지 메뉴와 저장된 데모 자료를 기준으로 안내합니다.';

    resultEl.classList.add('show');
  } catch(e) {
    showStatus('❌ 오류가 발생했습니다. 다시 시도해 주세요.', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '질문하기';
  }
}

function esc(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function renderMarkdown(md){
  return md
    .replace(/^## (.+)$/gm,'<h2>$1</h2>')
    .replace(/^- (.+)$/gm,'<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs,'<ul>$1</ul>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\n/g,'<br>');
}
</script>
</body>
</html>"""


class MobileDemoHandler(BaseHTTPRequestHandler):
    """HTTP handler for the mobile demo."""

    # These are set by create_app()
    site_id: str = "bukgu_gwangju"
    provider: str = "mock"
    snapshot_path: str | None = None
    _runner: Any = None
    _site_name: str = ""

    def log_message(self, format, *args):
        """Suppress default stderr logging."""
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "":
            self._serve_html()
        elif parsed.path == "/health":
            self._json_response({"ok": True, "site_id": self.site_id})
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/ask":
            self._handle_ask()
        else:
            self.send_error(404)

    def _serve_html(self):
        html = MOBILE_HTML.replace("{{site_name}}", self._site_name or self.site_id)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_ask(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(content_len)
            data = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, ValueError):
            self._json_response({"error": "Invalid JSON"}, 400)
            return

        question = (data.get("question") or "").strip()
        if not question:
            self._json_response({"error": "질문을 입력해 주세요."}, 400)
            return

        try:
            if self._runner is None:
                from src.demo import SiteDemoRunner
                self.__class__._runner = SiteDemoRunner(
                    site_id=self.site_id,
                    provider=self.provider,
                )

            runner = self._runner

            if self.snapshot_path:
                result = runner.answer_from_snapshot(self.snapshot_path, question=question)
            else:
                result = runner.answer(question)

            # Trim response for mobile
            response = {
                "site_id": result.get("site_id"),
                "site_name": result.get("site_name"),
                "question": result.get("question"),
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "ok": result.get("ok", False),
                "snapshot_mode": result.get("snapshot_mode", False),
                "fallback_used": result.get("fallback_used", False),
                "warnings": result.get("warnings", []),
            }
            self._json_response(response)

        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_app(
    site_id: str = "bukgu_gwangju",
    provider: str = "mock",
    snapshot: str | None = None,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> HTTPServer:
    """Create and return an HTTPServer for the mobile demo.

    Args:
        site_id: Site profile ID.
        provider: LLM provider name.
        snapshot: Path to snapshot file for stable demos.
        host: Bind host.
        port: Bind port.

    Returns:
        An HTTPServer instance. Call ``.serve_forever()`` to start.
    """
    # Resolve site name
    try:
        from src.site_profiles import load_profile
        profile = load_profile(site_id)
        site_name = profile.name
    except Exception:
        site_name = site_id

    # Set handler class attributes
    handler = type("Handler", (MobileDemoHandler,), {
        "site_id": site_id,
        "provider": provider,
        "snapshot_path": snapshot,
        "_runner": None,
        "_site_name": site_name,
    })

    server = HTTPServer((host, port), handler)
    return server
