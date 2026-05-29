"""Desktop admin/operator dashboard for AI Homepage Finder.

Serves a desktop-focused admin UI at http://localhost:8090 with
site profile, snapshot status, and demo question testing.

Usage::

    from src.web.admin_demo import create_admin_app
    app = create_admin_app(site_id="bukgu_gwangju", snapshot="/tmp/snap.json")
    app.serve_forever()
"""

from __future__ import annotations

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any
from urllib.parse import urlparse


ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>운영자 화면 — AI 홈페이지 파인더</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#f0f2f5;--card:#fff;--primary:#1a56db;--primary-light:#e8eefb;--text:#1f2937;--text2:#6b7280;--border:#e5e7eb;--success:#059669;--warn:#d97706;--error:#dc2626;--radius:10px}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif;background:var(--bg);color:var(--text);line-height:1.6}
.topbar{background:#1e293b;color:#fff;padding:12px 24px;display:flex;align-items:center;justify-content:space-between}
.topbar h1{font-size:1rem;font-weight:600}
.topbar .badge{background:#3b82f6;font-size:.7rem;padding:2px 8px;border-radius:12px}
.layout{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px 24px;max-width:1200px;margin:0 auto}
.card{background:var(--card);border-radius:var(--radius);padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.card h2{font-size:.85rem;color:var(--text2);margin-bottom:10px;text-transform:uppercase;letter-spacing:.03em;border-bottom:1px solid var(--border);padding-bottom:8px}
.card.full{grid-column:1/-1}
.kv{display:flex;justify-content:space-between;padding:4px 0;font-size:.85rem;border-bottom:1px solid #f3f4f6}
.kv:last-child{border-bottom:none}
.kv .k{color:var(--text2);min-width:140px}
.kv .v{font-weight:500;text-align:right;word-break:break-all}
.tag{display:inline-block;font-size:.7rem;padding:2px 8px;border-radius:12px;margin:2px}
.tag.blue{background:var(--primary-light);color:var(--primary)}
.tag.green{background:#ecfdf5;color:var(--success)}
.tag.yellow{background:#fef3c7;color:var(--warn)}
.tag.red{background:#fee2e2;color:var(--error)}
.test-panel{display:flex;gap:8px;margin-bottom:12px}
.test-panel input{flex:1;padding:10px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:.9rem;outline:none}
.test-panel input:focus{border-color:var(--primary)}
.test-panel button{padding:10px 20px;background:var(--primary);color:#fff;border:none;border-radius:8px;font-size:.9rem;font-weight:600;cursor:pointer;white-space:nowrap}
.test-panel button:disabled{opacity:.5}
.quick-btns{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.quick-btns button{padding:6px 14px;background:var(--card);border:1.5px solid var(--border);border-radius:8px;font-size:.8rem;cursor:pointer}
.quick-btns button:hover{border-color:var(--primary);background:var(--primary-light)}
.result-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px}
.stat-box{background:#f9fafb;border-radius:8px;padding:10px;text-align:center}
.stat-box .num{font-size:1.4rem;font-weight:700;color:var(--primary)}
.stat-box .label{font-size:.7rem;color:var(--text2)}
table{width:100%;border-collapse:collapse;font-size:.82rem}
th{background:#f9fafb;text-align:left;padding:8px 10px;font-weight:600;color:var(--text2);border-bottom:2px solid var(--border)}
td{padding:8px 10px;border-bottom:1px solid #f3f4f6;vertical-align:top}
td a{color:var(--primary);text-decoration:none}
td a:hover{text-decoration:underline}
.warnings{margin-top:8px}
.warnings .w{padding:6px 10px;background:#fef3c7;border-radius:6px;font-size:.8rem;color:var(--warn);margin-bottom:4px}
.answer-box{background:#f9fafb;border-radius:8px;padding:14px;font-size:.9rem;line-height:1.7;white-space:pre-wrap;margin-bottom:8px;max-height:200px;overflow-y:auto}
@media(max-width:768px){.layout{grid-template-columns:1fr}.result-summary{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<div class="topbar">
  <h1>🏛️ AI 홈페이지 파인더 — 운영자 화면</h1>
  <span class="badge">ADMIN</span>
</div>

<div class="layout">
  <!-- Summary -->
  <div class="card">
    <h2>서비스 정보</h2>
    <div id="summaryInfo"></div>
  </div>

  <!-- Site Profile -->
  <div class="card">
    <h2>사이트 프로필</h2>
    <div id="profileInfo"></div>
  </div>

  <!-- Snapshot Status -->
  <div class="card">
    <h2>snapshot 상태</h2>
    <div id="snapshotInfo"></div>
  </div>

  <!-- Status/Warnings -->
  <div class="card">
    <h2>상태 / 경고</h2>
    <div id="statusInfo"></div>
  </div>

  <!-- Demo Test Panel -->
  <div class="card full">
    <h2>데모 질문 테스트</h2>
    <div class="test-panel">
      <input type="text" id="testQuestion" placeholder="질문을 입력하세요" autocomplete="off">
      <button id="testBtn" onclick="runTest()">실행</button>
    </div>
    <div class="quick-btns">
      <button onclick="quickTest('민원서식 어디서 받아?')">민원서식</button>
      <button onclick="quickTest('교육접수는 어디서 해?')">교육접수</button>
      <button onclick="quickTest('정보공개는 어디서 볼 수 있어?')">정보공개</button>
      <button onclick="quickTest('고시공고는 어디서 확인해?')">고시공고</button>
    </div>
    <div id="testResult" style="display:none">
      <div class="result-summary" id="resultStats"></div>
      <div class="answer-box" id="resultAnswer"></div>
      <h3 style="font-size:.85rem;color:var(--text2);margin:10px 0 6px">출처 / 검색 결과</h3>
      <table>
        <thead><tr><th>제목</th><th>URL</th><th>유형</th><th>점수</th></tr></thead>
        <tbody id="resultTable"></tbody>
      </table>
      <div class="warnings" id="resultWarnings"></div>
    </div>
  </div>
</div>

<script>
const testQ = document.getElementById('testQuestion');
testQ.addEventListener('keydown', e => { if(e.key==='Enter') runTest(); });

async function init(){
  try {
    const res = await fetch('/api/info');
    const d = await res.json();

    // Summary
    const s = d.summary || {};
    document.getElementById('summaryInfo').innerHTML = kvRows({
      '서비스명': s.service_name || '-',
      '사이트 ID': s.site_id || '-',
      '기관명': s.site_name || '-',
      'Provider': s.provider || '-',
      'Fetch Provider': s.fetch_provider || '-',
      'Snapshot': s.snapshot_path ? '사용 중' : '없음',
    });

    // Profile
    const p = d.profile || {};
    document.getElementById('profileInfo').innerHTML = kvRows({
      '기관명': p.name || '-',
      'Base URL': p.base_url ? '<a href="' + esc(p.base_url) + '" target="_blank">' + esc(p.base_url) + '</a>' : '-',
      '분류': p.classification || '-',
      'Fetch Provider': p.preferred_fetch_provider || '-',
      '중요 키워드': (p.important_keywords||[]).join(', ') || '-',
      'Fallback 전략': p.fallback_strategy || '-',
    });

    // Snapshot
    const sn = d.snapshot || {};
    document.getElementById('snapshotInfo').innerHTML = kvRows({
      '상태': sn.loaded ? '<span class="tag green">로드 성공</span>' : '<span class="tag red">없음/실패</span>',
      '경로': sn.path || '-',
      '수집 시각': sn.fetched_at || '-',
      'Navigation 링크': sn.nav_link_count != null ? sn.nav_link_count + '개' : '-',
      'Source 개수': sn.source_count != null ? sn.source_count + '개' : '-',
      '질문': sn.question || '-',
    });

    // Status
    const st = d.status || {};
    let statusHtml = '';
    if(st.snapshot_mode) statusHtml += '<span class="tag blue">Snapshot 모드</span> ';
    if(st.fallback_used) statusHtml += '<span class="tag yellow">Fallback 사용</span> ';
    if(!st.snapshot_mode && !st.fallback_used) statusHtml += '<span class="tag green">정상</span>';
    document.getElementById('statusInfo').innerHTML = statusHtml || '<span class="tag green">정상</span>';

  } catch(e) {
    document.getElementById('summaryInfo').innerHTML = '<p style="color:var(--error)">정보 로드 실패: ' + esc(e.message) + '</p>';
  }
}

function kvRows(obj){
  return Object.entries(obj).map(([k,v]) =>
    '<div class="kv"><span class="k">' + k + '</span><span class="v">' + v + '</span></div>'
  ).join('');
}

function quickTest(q){ document.getElementById('testQuestion').value = q; runTest(); }

async function runTest(){
  const q = testQ.value.trim();
  if(!q) return;

  const btn = document.getElementById('testBtn');
  btn.disabled = true;
  btn.textContent = '실행 중…';

  try {
    const res = await fetch('/api/test', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({question: q})
    });
    const d = await res.json();

    if(d.error){
      alert('오류: ' + d.error);
      return;
    }

    // Stats
    const srcCount = (d.sources||[]).length;
    document.getElementById('resultStats').innerHTML =
      statBox(d.answer_ok !== false ? '✓' : '✗', '답변') +
      statBox(srcCount, '출처') +
      statBox(d.fallback_used ? '사용' : '없음', 'Fallback') +
      statBox((d.warnings||[]).length, '경고');

    // Answer
    document.getElementById('resultAnswer').textContent = d.answer || '(답변 없음)';

    // Table
    const tbody = document.getElementById('resultTable');
    tbody.innerHTML = '';
    (d.search_results||d.sources||[]).forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + esc(r.title||'-') + '</td>' +
        '<td><a href="' + esc(r.url||'#') + '" target="_blank">' + esc((r.url||'').substring(0,50)) + '</a></td>' +
        '<td><span class="tag blue">' + esc(r.category||r.source_type||'-') + '</span></td>' +
        '<td>' + (r.score != null ? r.score.toFixed(1) : '-') + '</td>';
      tbody.appendChild(tr);
    });

    // Warnings
    const wEl = document.getElementById('resultWarnings');
    wEl.innerHTML = '';
    (d.warnings||[]).forEach(w => {
      const div = document.createElement('div');
      div.className = 'w';
      div.textContent = w;
      wEl.appendChild(div);
    });

    document.getElementById('testResult').style.display = 'block';
  } catch(e) {
    alert('오류: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '실행';
  }
}

function statBox(num, label){
  return '<div class="stat-box"><div class="num">' + num + '</div><div class="label">' + label + '</div></div>';
}

function esc(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }

init();
</script>
</body>
</html>"""


class AdminDemoHandler(BaseHTTPRequestHandler):
    """HTTP handler for the admin dashboard."""

    site_id: str = "bukgu_gwangju"
    provider: str = "mock"
    snapshot_path: str | None = None
    _runner: Any = None
    _site_name: str = ""
    _profile_data: dict[str, Any] | None = None
    _snapshot_data: dict[str, Any] | None = None

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", ""):
            self._serve_html()
        elif parsed.path == "/api/info":
            self._handle_info()
        elif parsed.path == "/health":
            self._json_response({"ok": True, "site_id": self.site_id})
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/test":
            self._handle_test()
        else:
            self.send_error(404)

    def _serve_html(self):
        body = ADMIN_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_info(self):
        """Return site info, profile, and snapshot status."""
        info: dict[str, Any] = {"summary": {}, "profile": {}, "snapshot": {}, "status": {}}

        # Summary
        info["summary"] = {
            "service_name": "AI 홈페이지 파인더",
            "site_id": self.site_id,
            "site_name": self._site_name,
            "provider": self.provider,
            "fetch_provider": "-",
            "snapshot_path": self.snapshot_path or "",
        }

        # Profile
        profile = self._get_profile_data()
        if profile:
            info["profile"] = profile
            info["summary"]["fetch_provider"] = profile.get("preferred_fetch_provider", "-")

        # Snapshot
        snap = self._get_snapshot_data()
        if snap:
            nav_count = len(
                snap.get("homepage_map", {})
                .get("homepage", {})
                .get("navigation_links", [])
            )
            info["snapshot"] = {
                "loaded": True,
                "path": self.snapshot_path,
                "fetched_at": snap.get("fetched_at", "-"),
                "nav_link_count": nav_count,
                "source_count": len(snap.get("sources", [])),
                "question": snap.get("question", "-"),
            }
            info["status"]["snapshot_mode"] = snap.get("snapshot_mode", False)
        else:
            info["snapshot"] = {"loaded": False, "path": self.snapshot_path or ""}

        self._json_response(info)

    def _handle_test(self):
        """Run a demo question and return the result."""
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

            response = {
                "site_id": result.get("site_id"),
                "site_name": result.get("site_name"),
                "question": result.get("question"),
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "search_results": result.get("search_results", []),
                "ok": result.get("ok", False),
                "answer_ok": result.get("answer_ok", False),
                "snapshot_mode": result.get("snapshot_mode", False),
                "fallback_used": result.get("fallback_used", False),
                "warnings": result.get("warnings", []),
            }
            self._json_response(response)

        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _get_profile_data(self) -> dict[str, Any] | None:
        """Load site profile data."""
        if self._profile_data is not None:
            return self._profile_data
        try:
            from src.site_profiles import load_profile
            profile = load_profile(self.site_id)
            self.__class__._profile_data = {
                "name": profile.name,
                "base_url": profile.base_url,
                "classification": profile.classification,
                "preferred_fetch_provider": profile.preferred_fetch_provider,
                "important_keywords": profile.important_keywords,
                "fallback_strategy": profile.fallback_strategy,
            }
            return self._profile_data
        except Exception:
            return None

    def _get_snapshot_data(self) -> dict[str, Any] | None:
        """Load snapshot data."""
        if self._snapshot_data is not None:
            return self._snapshot_data
        if not self.snapshot_path:
            return None
        try:
            from src.demo import SiteDemoRunner
            self.__class__._snapshot_data = SiteDemoRunner.load_snapshot(self.snapshot_path)
            return self._snapshot_data
        except Exception:
            return None

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_admin_app(
    site_id: str = "bukgu_gwangju",
    provider: str = "mock",
    snapshot: str | None = None,
    host: str = "0.0.0.0",
    port: int = 8090,
) -> HTTPServer:
    """Create and return an HTTPServer for the admin dashboard."""
    try:
        from src.site_profiles import load_profile
        profile = load_profile(site_id)
        site_name = profile.name
    except Exception:
        site_name = site_id

    handler = type("AdminHandler", (AdminDemoHandler,), {
        "site_id": site_id,
        "provider": provider,
        "snapshot_path": snapshot,
        "_runner": None,
        "_site_name": site_name,
        "_profile_data": None,
        "_snapshot_data": None,
    })

    return HTTPServer((host, port), handler)
