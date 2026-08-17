/**
 * #1331 Slice A — Cloudflare site-aware MVP runtime identity contract.
 *
 * Deterministic / offline. No provider, no network, no official-site / Firecrawl
 * calls. Covers:
 *   1. site_runtime.js resolver parity (the vocabulary MUST match the Python
 *      mirror src/llm/site_aware_mvp_dispatch.py 1:1).
 *   2. ask.js fail-closed early-return seam: a non-CONFIGURED site never reaches
 *      the Buk-gu router/quest; omitted/empty site_id preserves the Buk-gu default.
 *   3. request-visible non-string site_id is rejected before dispatch.
 *
 * Run with: node tests/functions/test_site_runtime_contract.mjs
 */

// Block any accidental upstream call (fail-safe).
globalThis.fetch = () => {
  throw new Error('NETWORK_BLOCKED: unexpected upstream call');
};

const SITE_RUNTIME_PATH = new URL(
  '../../functions/api/mvp/site_runtime.js',
  import.meta.url,
).pathname;
const ASK_PATH = new URL('../../functions/api/mvp/ask.js', import.meta.url).pathname;

const siteRuntime = await import(`file://${SITE_RUNTIME_PATH}`);
const { onRequest } = await import(`file://${ASK_PATH}`);

let passed = 0;
let failed = 0;
const failures = [];

async function assert(description, fn) {
  try {
    await fn();
    passed += 1;
    console.log(`  PASS ${description}`);
  } catch (error) {
    failed += 1;
    failures.push({ description, error: error.message });
    console.log(`  FAIL ${description}: ${error.message}`);
  }
}

function expectEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function expectTrue(value, label) {
  if (value !== true) throw new Error(`${label}: expected true, got ${JSON.stringify(value)}`);
}

function createMockContext(method, body, envOverrides = {}, requestUrl = '') {
  const request = {
    method,
    url: requestUrl,
    headers: new Map([['Content-Type', 'application/json']]),
    json: async () => (body ? JSON.parse(body) : {}),
    text: async () => (body ? String(body) : ''),
  };
  const env = {
    GEMINI_API_KEY: '',
    KILOCODE_API_KEY: '',
    MVP_RUNTIME_LOGS: '0',
    ...envOverrides,
  };
  return { request, env };
}

async function requestJson(method, body, envOverrides, requestUrl = '') {
  const response = await onRequest(createMockContext(method, body, envOverrides, requestUrl));
  const text = await response.text();
  return { response, data: text ? JSON.parse(text) : null };
}

// --------------------------------------------------------------------------- //
// 1. Resolver vocabulary parity (MUST match Python mirror exactly)            //
// --------------------------------------------------------------------------- //
console.log('#1331 Slice A: site_runtime resolver parity');

await assert('status vocabulary strings are canonical', () => {
  expectEqual(siteRuntime.SITE_RUNTIME_CONFIGURED, 'configured');
  expectEqual(siteRuntime.SITE_RUNTIME_RECOGNIZED_UNCONFIGURED, 'recognized_unconfigured');
  expectEqual(siteRuntime.SITE_RUNTIME_UNKNOWN, 'unknown');
  expectEqual(siteRuntime.SITE_FAILURE_UNKNOWN, 'unknown_site');
  expectEqual(siteRuntime.SITE_FAILURE_UNCONFIGURED, 'site_unconfigured_for_slice');
  expectEqual(siteRuntime.DEFAULT_SITE_ID, 'bukgu_gwangju');
});

await assert('supported registry has exactly the two known sites', () => {
  const keys = Object.keys(siteRuntime.SUPPORTED_SITE_RUNTIMES);
  expectEqual(keys.length, 2);
  expectEqual(siteRuntime.SUPPORTED_SITE_RUNTIMES.bukgu_gwangju, 'configured');
  expectEqual(siteRuntime.SUPPORTED_SITE_RUNTIMES.seogu_gwangju, 'recognized_unconfigured');
});

await assert('omitted site_id defaults to Buk-gu (configured)', () => {
  const r = siteRuntime.resolveSiteRuntime(undefined);
  expectEqual(r.siteId, 'bukgu_gwangju');
  expectEqual(r.status, 'configured');
});

await assert('null site_id defaults to Buk-gu', () => {
  const r = siteRuntime.resolveSiteRuntime(null);
  expectEqual(r.status, 'configured');
});

await assert('empty string site_id defaults to Buk-gu', () => {
  const r = siteRuntime.resolveSiteRuntime('');
  expectEqual(r.status, 'configured');
});

await assert('whitespace-only site_id defaults to Buk-gu', () => {
  const r = siteRuntime.resolveSiteRuntime('   ');
  expectEqual(r.status, 'configured');
});

await assert('non-string resolver input defaults to Buk-gu (internal parity path)', () => {
  const r = siteRuntime.resolveSiteRuntime(12345);
  expectEqual(r.status, 'configured');
});

await assert('explicit bukgu_gwangju is configured', () => {
  const r = siteRuntime.resolveSiteRuntime('bukgu_gwangju');
  expectEqual(r.status, 'configured');
});

await assert('seogu_gwangju is recognized_unconfigured', () => {
  const r = siteRuntime.resolveSiteRuntime('seogu_gwangju');
  expectEqual(r.status, 'recognized_unconfigured');
});

await assert('well-formed unrecognized site fails closed (unknown)', () => {
  const r = siteRuntime.resolveSiteRuntime('atlantis_gov');
  expectEqual(r.status, 'unknown');
});

await assert('malformed uppercase site fails closed', () => {
  const r = siteRuntime.resolveSiteRuntime('Bukgu');
  expectEqual(r.status, 'unknown');
});

await assert('malformed dash site fails closed', () => {
  const r = siteRuntime.resolveSiteRuntime('buk-gu');
  expectEqual(r.status, 'unknown');
});

await assert('malformed too-short site fails closed', () => {
  const r = siteRuntime.resolveSiteRuntime('ab');
  expectEqual(r.status, 'unknown');
});

await assert('malformed too-long site fails closed', () => {
  const r = siteRuntime.resolveSiteRuntime('a'.repeat(65));
  expectEqual(r.status, 'unknown');
});

await assert('format checker accepts valid ids and rejects malformed', () => {
  expectTrue(siteRuntime.is_valid_site_id_format('seogu_gwangju'));
  expectTrue(!siteRuntime.is_valid_site_id_format('Bukgu'));
  expectTrue(!siteRuntime.is_valid_site_id_format('buk-gu'));
  expectTrue(!siteRuntime.is_valid_site_id_format('ab'));
  expectTrue(!siteRuntime.is_valid_site_id_format('a'.repeat(65)));
});

// --------------------------------------------------------------------------- //
// 2. ask.js fail-closed dispatch seam                                          //
// --------------------------------------------------------------------------- //
console.log('#1331 Slice A: ask.js site dispatch seam');

await assert('seogu_gwangju never executes Buk-gu (recognized_unconfigured)', async () => {
  const { data } = await requestJson('POST', JSON.stringify({ question: '공동주택 문의는 어디로 해요?', site_id: 'seogu_gwangju' }));
  expectEqual(data.ok, false);
  expectEqual(data.action, 'none');
  expectEqual(data.provider, 'site_dispatch');
  expectEqual(data.failure_code, 'site_unconfigured_for_slice');
  expectEqual(data.site_status, 'recognized_unconfigured');
  expectEqual(data.site_id, 'seogu_gwangju');
  expectEqual(data.fallback_to_bukgu, false);
  expectTrue(!('quest' in data));
});

await assert('unknown well-formed site fails closed', async () => {
  const { data } = await requestJson('POST', JSON.stringify({ question: '안녕하세요', site_id: 'atlantis_gov' }));
  expectEqual(data.ok, false);
  expectEqual(data.provider, 'site_dispatch');
  expectEqual(data.failure_code, 'unknown_site');
  expectEqual(data.site_status, 'unknown');
  expectEqual(data.fallback_to_bukgu, false);
});

await assert('malformed string site_id fails closed', async () => {
  const { data } = await requestJson('POST', JSON.stringify({ question: '안녕하세요', site_id: 'Bukgu' }));
  expectEqual(data.ok, false);
  expectEqual(data.provider, 'site_dispatch');
  expectEqual(data.failure_code, 'unknown_site');
  expectEqual(data.site_status, 'unknown');
  expectEqual(data.fallback_to_bukgu, false);
});

await assert('request-visible non-string site_id is rejected before dispatch', async () => {
  for (const siteId of [12345, null, { id: 'bukgu_gwangju' }, ['bukgu_gwangju']]) {
    const { data } = await requestJson(
      'POST',
      JSON.stringify({ question: '안녕하세요', site_id: siteId }),
    );
    expectEqual(data.ok, false);
    expectEqual(data.failure_code, 'invalid_input');
    expectTrue(!('site_status' in data));
    expectTrue(!('fallback_to_bukgu' in data));
  }
});

await assert('explicit bukgu_gwangju is NOT intercepted by the site guard', async () => {
  const { data } = await requestJson(
    'POST',
    JSON.stringify({ question: '안녕하세요', site_id: 'bukgu_gwangju' }),
    { MVP_AI_MODE: 'disabled' },
  );
  // Disabled mode returns a service_disabled envelope, but crucially the
  // site guard must NOT have intercepted it as a site_dispatch failure.
  expectTrue(data.provider !== 'site_dispatch');
  expectTrue(!('site_status' in data) || data.site_status === undefined);
  expectEqual(data.ok, false);
});

await assert('omitted site_id preserves Buk-gu default (backward compatible)', async () => {
  const { data } = await requestJson(
    'POST',
    JSON.stringify({ question: '안녕하세요' }),
    { MVP_AI_MODE: 'disabled' },
  );
  expectTrue(data.provider !== 'site_dispatch');
  expectEqual(data.ok, false);
});

console.log(`\n#1331 Slice A site_runtime contract: ${passed} passed, ${failed} failed`);
if (failed > 0) {
  console.error('Failures:');
  for (const f of failures) console.error(`  - ${f.description}: ${f.error}`);
  process.exit(1);
}
process.exit(0);
