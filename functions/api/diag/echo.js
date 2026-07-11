export async function onRequest(context) {
  const target = 'https://bukgu.gwangju.kr/';
  const variants = {};
  try {
    const r1 = await fetch(target, { headers: { 'User-Agent': 'Mozilla/5.0', Accept: 'text/html' } });
    variants.plainUA = { status: r1.status, len: (await r1.text()).length };
  } catch (e) { variants.plainUA = { error: String(e.message||e) }; }
  return new Response(JSON.stringify(variants), { status: 200, headers: { 'content-type': 'application/json' } });
}
