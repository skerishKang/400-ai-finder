export async function onRequest(context) {
  const url = context.request.url;
  const target = new URL(url).searchParams.get('t') || 'https://bukgu.gwangju.kr/';
  try {
    const r = await fetch(target, { method: 'GET', headers: { Accept: 'text/html' }, redirect: 'follow' });
    const txt = await r.text();
    return new Response(JSON.stringify({ ok: true, status: r.status, len: txt.length, head: txt.slice(0, 200) }), { status: 200, headers: { 'content-type': 'application/json' } });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: String(e && e.message || e), name: e && e.name }), { status: 200, headers: { 'content-type': 'application/json' } });
  }
}
