const testQ = document.getElementById('testQuestion');
testQ.addEventListener('keydown', e => { if(e.key==='Enter') runTest(); });

async function init(){
  try {
    const res = await fetch('/api/info');
    const d = await res.json();

    const s = d.summary || {};
    document.getElementById('summaryInfo').innerHTML = kvRows({
      '서비스명': s.service_name || '-',
      '사이트 ID': s.site_id || '-',
      '기관명': s.site_name || '-',
      'Provider': s.provider || '-',
      'Fetch Provider': s.fetch_provider || '-',
      'Snapshot': s.snapshot_path ? '사용 중' : '없음',
    });

    const p = d.profile || {};
    document.getElementById('profileInfo').innerHTML = kvRows({
      '기관명': p.name || '-',
      'Base URL': p.base_url ? '<a href="' + esc(p.base_url) + '" target="_blank">' + esc(p.base_url) + '</a>' : '-',
      '분류': p.classification || '-',
      'Fetch Provider': p.preferred_fetch_provider || '-',
      '중요 키워드': (p.important_keywords||[]).join(', ') || '-',
      'Fallback 전략': p.fallback_strategy || '-',
    });

    const sn = d.snapshot || {};
    document.getElementById('snapshotInfo').innerHTML = kvRows({
      '상태': sn.loaded ? '<span class="tag green">로드 성공</span>' : '<span class="tag red">없음/실패</span>',
      '경로': sn.path || '-',
      '수집 시각': sn.fetched_at || '-',
      'Navigation 링크': sn.nav_link_count != null ? sn.nav_link_count + '개' : '-',
      'Source 개수': sn.source_count != null ? sn.source_count + '개' : '-',
      '질문': sn.question || '-',
    });

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

    const srcCount = (d.sources||[]).length;
    document.getElementById('resultStats').innerHTML =
      statBox(d.answer_ok !== false ? '✓' : '✗', '답변') +
      statBox(srcCount, '출처') +
      statBox(d.fallback_used ? '사용' : '없음', 'Fallback') +
      statBox((d.warnings||[]).length, '경고');

    document.getElementById('resultAnswer').textContent = d.answer || '(답변 없음)';

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