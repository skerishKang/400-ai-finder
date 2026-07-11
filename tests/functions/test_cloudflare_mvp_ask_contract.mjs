/**
 * test_cloudflare_mvp_ask_contract.mjs
 *
 * Cloudflare Pages Function `/api/mvp/ask` contract test.
 *
 * Tests the function's contract (input validation, output shape, error modes)
 * WITHOUT deploying or running Miniflare — validates contract expectations
 * by directly testing the exported `onRequest` handler in a simulated
 * Cloudflare Workers environment via a lightweight mock.
 *
 * Run:
 *   RUN_CLOUDFLARE_FUNCTION_CONTRACTS=1 node tests/functions/test_cloudflare_mvp_ask_contract.mjs
 *
 * Without the env gate, tests are skipped silently (CI sets the flag).
 */

const RUN_LIVE = process.env.RUN_CLOUDFLARE_FUNCTION_CONTRACTS === '1';

if (!RUN_LIVE) {
  console.log('[SKIP] RUN_CLOUDFLARE_FUNCTION_CONTRACTS not set — skipping Cloudflare Function contract test');
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Fail-fast no-network stub — any unexpected fetch call throws immediately.
// ---------------------------------------------------------------------------
const _ORIGINAL_FETCH = globalThis.fetch;

function noNetworkStub() {
  throw new Error('NETWORK_BLOCKED: unexpected upstream call in contract test');
}

// Replace with no-network stub upfront.
globalThis.fetch = noNetworkStub;

// ---------------------------------------------------------------------------
// Lightweight Cloudflare Workers environment mock
// ---------------------------------------------------------------------------
function createMockContext(method, body, envOverrides) {
  const headers = {
    'Content-Type': 'application/json',
  };
  const request = {
    method,
    headers: new Map(Object.entries(headers)),
    json: async () => (body ? JSON.parse(body) : {}),
    text: async () => (body ? String(body) : ''),
  };
  const env = { GEMINI_API_KEY: '', ...envOverrides };
  return { request, env };
}

// ---------------------------------------------------------------------------
// Dynamically import the module — must be runnable from repo root
// ---------------------------------------------------------------------------
const FUNCTION_PATH = new URL('../../functions/api/mvp/ask.js', import.meta.url).pathname;

let onRequest;
let functionModule;
try {
  functionModule = await import(`file://${FUNCTION_PATH}`);
  onRequest = functionModule.onRequest;
} catch (err) {
  console.error('[FAIL] Could not import Cloudflare Function module:', err.message);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
let passed = 0;
let failed = 0;
const failures = [];

async function assert(description, fn) {
  try {
    await fn();
    passed++;
    console.log(`  ✅ ${description}`);
  } catch (err) {
    failed++;
    failures.push({ description, error: err.message });
    console.log(`  ❌ ${description}`);
    console.log(`       ${err.message}`);
  }
}

async function getResponse(method, body, envOverrides) {
  const ctx = createMockContext(method, body, envOverrides);
  return await onRequest(ctx);
}

async function assertStatus(description, method, body, expectedStatus, envOverrides) {
  await assert(description, async () => {
    const res = await getResponse(method, body, envOverrides);
    if (res.status !== expectedStatus) {
      throw new Error(`Expected status ${expectedStatus}, got ${res.status}`);
    }
  });
}

async function assertJsonResponse(description, method, body, expectedChecks, envOverrides) {
  await assert(description, async () => {
    const res = await getResponse(method, body, envOverrides);
    const data = JSON.parse(await res.text());
    for (const [key, checker] of Object.entries(expectedChecks)) {
      if (typeof checker === 'function') {
        checker(data[key], key, data);
      } else if (data[key] !== checker) {
        throw new Error(`Expected ${key}=${JSON.stringify(checker)}, got ${JSON.stringify(data[key])}`);
      }
    }
  });
}

// ---------------------------------------------------------------------------
// Mock fetch helper — replaces globalThis.fetch so the function's upstream
// LLM API call is intercepted. Each call returns a canned response and
// records the last call info (url, method, headers, body) for assertion.
// ---------------------------------------------------------------------------
let _lastCall = null;

function getLastCall() {
  return _lastCall;
}

function mockFetch(status, body) {
  _lastCall = null;
  globalThis.fetch = async (url, options) => {
    const reqBody = options && options.body ? options.body : '';
    _lastCall = {
      url: typeof url === 'string' ? url : url.toString(),
      method: (options && options.method) || 'GET',
      headers: (options && options.headers) || {},
      body: reqBody,
    };
    return {
      ok: status >= 200 && status < 300,
      status,
      text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
      json: async () => (typeof body === 'string' ? JSON.parse(body) : body),
    };
  };
}

function restoreFetch() {
  globalThis.fetch = noNetworkStub;
  _lastCall = null;
}

// Helper: assert that no upstream call was made.
async function assertNoUpstreamCall(description, fn) {
  const prior = _lastCall;
  try {
    await fn();
  } finally {
    const callCount = _lastCall !== prior ? 1 : 0;
    if (callCount > 0) {
      throw new Error(`${description}: unexpected upstream call: count=1, url=${_lastCall.url}`);
    }
  }
}

// Wrapper around assertJsonResponse that also verifies zero upstream calls.
async function assertNoCallJsonResponse(description, method, body, expectedChecks, envOverrides) {
  await assertNoUpstreamCall(description, async () => {
    await assertJsonResponse(description, method, body, expectedChecks, envOverrides);
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
console.log('\n=== Cloudflare Pages Function /api/mvp/ask Contract Test ===\n');

// 1. OPTIONS preflight returns expected CORS headers
await assert('OPTIONS preflight returns 200 with CORS headers', async () => {
  const res = await getResponse('OPTIONS', null);
  if (res.status !== 200) throw new Error(`Expected 200, got ${res.status}`);
  const cors = res.headers.get('Access-Control-Allow-Origin');
  // CORS is now restricted — no Origin header in mock means the fallback is used
  if (!cors || cors === '*') throw new Error(`Expected restricted CORS, got ${cors}`);
  if (cors !== 'https://cgbukku.pages.dev') throw new Error(`Expected https://cgbukku.pages.dev, got ${cors}`);
  const methods = res.headers.get('Access-Control-Allow-Methods');
  if (!methods || !methods.includes('POST')) throw new Error(`Missing POST in Allow-Methods: ${methods}`);
});

// 2. non-POST returns 405
await assertStatus('GET request returns 405', 'GET', null, 405);
await assertStatus('PUT request returns 405', 'PUT', null, 405);
await assertStatus('DELETE request returns 405', 'DELETE', null, 405);

// 3. invalid JSON does not 500
await assertNoCallJsonResponse('Invalid JSON body returns ok:false (not 500)', 'POST', 'not json at all', {
  ok: false,
}, { GEMINI_API_KEY: 'test-key' });

// 4. missing question returns 400
await assertNoCallJsonResponse('Missing question field returns 400 with ok:false', 'POST', JSON.stringify({}), {
  ok: false,
  error: 'Missing question',
}, { GEMINI_API_KEY: 'test-key' });

await assertNoCallJsonResponse('Empty question string returns 400', 'POST', JSON.stringify({ question: '' }), {
  ok: false,
  error: 'Missing question',
}, { GEMINI_API_KEY: 'test-key' });

await assertNoCallJsonResponse('Whitespace-only question returns 400', 'POST', JSON.stringify({ question: '   ' }), {
  ok: false,
  error: 'Missing question',
}, { GEMINI_API_KEY: 'test-key' });

// 4a. Non-string question type validation
await assertNoCallJsonResponse('Question null returns invalid_input (not internal_error)', 'POST', JSON.stringify({ question: null }), {
  ok: false,
  answer: '잘못된 요청 형식입니다.',
  action: 'none',
  confidence: 0.0,
  failure_code: 'invalid_input',
  provider: 'gemini',
  model: 'gemini-3.5-flash',
}, { GEMINI_API_KEY: 'test-key' });

await assertNoCallJsonResponse('Question number returns invalid_input', 'POST', JSON.stringify({ question: 123 }), {
  ok: false,
  answer: '잘못된 요청 형식입니다.',
  action: 'none',
  confidence: 0.0,
  failure_code: 'invalid_input',
}, { GEMINI_API_KEY: 'test-key' });

await assertNoCallJsonResponse('Question array returns invalid_input', 'POST', JSON.stringify({ question: [] }), {
  ok: false,
  answer: '잘못된 요청 형식입니다.',
  action: 'none',
  confidence: 0.0,
  failure_code: 'invalid_input',
}, { GEMINI_API_KEY: 'test-key' });

await assertNoCallJsonResponse('Question object returns invalid_input', 'POST', JSON.stringify({ question: {} }), {
  ok: false,
  answer: '잘못된 요청 형식입니다.',
  action: 'none',
  confidence: 0.0,
  failure_code: 'invalid_input',
}, { GEMINI_API_KEY: 'test-key' });

await assertNoCallJsonResponse('Question boolean true returns invalid_input', 'POST', JSON.stringify({ question: true }), {
  ok: false,
  answer: '잘못된 요청 형식입니다.',
  action: 'none',
  confidence: 0.0,
  failure_code: 'invalid_input',
}, { GEMINI_API_KEY: 'test-key' });

await assertNoCallJsonResponse('Question boolean false returns invalid_input', 'POST', JSON.stringify({ question: false }), {
  ok: false,
  answer: '잘못된 요청 형식입니다.',
  action: 'none',
  confidence: 0.0,
  failure_code: 'invalid_input',
}, { GEMINI_API_KEY: 'test-key' });

// 5. question too long returns safe invalid_input
const longQuestion = 'x'.repeat(301);
await assertNoCallJsonResponse('Question over 300 chars returns invalid_input', 'POST', JSON.stringify({ question: longQuestion }), {
  ok: false,
  failure_code: 'invalid_input',
  action: 'none',
  confidence: 0.0,
}, { GEMINI_API_KEY: 'test-key' });

// 6. action allowlist — verify the allowlist exists by checking the module's behavior.
await assert('VALID_ACTIONS constant is defined in module', async () => {
  if (!Array.isArray(functionModule.VALID_ACTIONS)) throw new Error('VALID_ACTIONS must be an array');
  if (functionModule.VALID_ACTIONS.length !== 8) throw new Error('VALID_ACTIONS must contain seven journeys plus none');
  for (const action of ['streetlight_report', 'litter_ai_assist', 'none']) {
    if (!functionModule.VALID_ACTIONS.includes(action)) throw new Error(`Missing action ${action}`);
  }
});

// 7. API key not configured — returns config_error
await assertNoCallJsonResponse('No API key returns config_error with gemini provider', 'POST', JSON.stringify({ question: 'test' }), {
  ok: false,
  failure_code: 'config_error',
  action: 'none',
  confidence: 0.0,
  provider: 'gemini',
  model: 'gemini-3.5-flash',
});

// 8. Response shape contract — check all known failure modes return proper JSON
await assertNoCallJsonResponse('Invalid JSON body returns ok:false', 'POST', '{invalid json}', {
  ok: false,
}, { GEMINI_API_KEY: 'test-key' });

// 9. Question length exact boundary — 300 chars should pass (not block)
const exact300 = 'a'.repeat(300);
await assertNoCallJsonResponse('Question exactly 300 chars is accepted (not blocked)', 'POST', JSON.stringify({ question: exact300 }), {
  ok: false,
  failure_code: 'config_error',
}, {});

const exact301 = 'b'.repeat(301);
await assertNoCallJsonResponse('Question 301 chars returns invalid_input', 'POST', JSON.stringify({ question: exact301 }), {
  ok: false,
  failure_code: 'invalid_input',
}, {});

// All tests below this line use canned Gemini Interactions API responses.
console.log('\n--- Grounded interaction response tests ---\n');

function groundedInteraction(answer, annotations = [], queries = ['site:bukgu.gwangju.kr 북구청 공지']) {
  return {
    steps: [
      { type: 'google_search_call', arguments: { queries } },
      { type: 'model_output', content: [{ type: 'text', text: answer, annotations }] },
    ],
  };
}

const officialCitation = {
  type: 'url_citation',
  title: '광주 북구청',
  url: 'https://bukgu.gwangju.kr/board.es?mid=a10201010000',
  start_index: 0,
  end_index: 8,
};

try {
  mockFetch(200, groundedInteraction('현재 북구청 공지사항을 확인했습니다.', [officialCitation]));
  await assertJsonResponse('Official grounded answer exposes freshness metadata', 'POST', JSON.stringify({ question: '이번 주 북구청 공지 알려줘' }), {
    ok: true,
    answer: '현재 북구청 공지사항을 확인했습니다.',
    action: 'none',
    provider: 'gemini',
    model: 'gemini-3.5-flash',
    freshness_state: 'live_official',
    source_url: officialCitation.url,
    retrieved_at: (value) => {
      if (typeof value !== 'string' || Number.isNaN(Date.parse(value))) throw new Error(`Invalid retrieved_at: ${value}`);
    },
    sources: (value) => {
      if (!Array.isArray(value) || value.length !== 1 || value[0].official !== true) {
        throw new Error(`Expected one official source, got ${JSON.stringify(value)}`);
      }
    },
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

try {
  mockFetch(200, groundedInteraction('참고 자료를 확인했습니다.', [{
    type: 'url_citation', title: '참고', url: 'https://example.com/info', start_index: 0, end_index: 4,
  }]));
  await assertJsonResponse('Non-official citation is marked live_web', 'POST', JSON.stringify({ question: '일반 질문' }), {
    ok: true,
    freshness_state: 'live_web',
    source_url: 'https://example.com/info',
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

try {
  mockFetch(200, groundedInteraction('   ', []));
  await assertJsonResponse('Blank grounded output fails closed', 'POST', JSON.stringify({ question: 'test' }), {
    ok: false,
    failure_code: 'empty_response',
    freshness_state: 'unavailable',
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

try {
  mockFetch(500, { error: 'Internal Server Error' });
  await assertJsonResponse('Upstream HTTP 500 returns upstream_error', 'POST', JSON.stringify({ question: 'test' }), {
    ok: false,
    failure_code: 'upstream_error',
    action: 'none',
    freshness_state: 'unavailable',
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

console.log('\n--- Upstream request and action routing ---\n');

try {
  mockFetch(200, groundedInteraction('테스트 답변', [officialCitation]));
  await getResponse('POST', JSON.stringify({ question: '테스트 질문' }), { GEMINI_API_KEY: 'test-key' });
  const call = getLastCall();
  await assert('Upstream uses Gemini Interactions endpoint', async () => {
    if (!call || call.url !== 'https://generativelanguage.googleapis.com/v1beta/interactions') {
      throw new Error(`Unexpected URL: ${call && call.url}`);
    }
  });
  await assert('Upstream uses x-goog-api-key and POST', async () => {
    if (call.method !== 'POST') throw new Error(`Expected POST, got ${call.method}`);
    if (call.headers['x-goog-api-key'] !== 'test-key') throw new Error('Missing x-goog-api-key');
  });
  await assert('Request enables Google Search and current-time official prompt', async () => {
    const payload = JSON.parse(call.body);
    if (payload.model !== 'gemini-3.5-flash') throw new Error(`Unexpected model ${payload.model}`);
    if (payload.tools?.[0]?.type !== 'google_search') throw new Error('google_search tool missing');
    if (payload.store !== false) throw new Error('Interactions request must be stateless');
    if (!payload.input.includes('현재 대한민국 표준시각')) throw new Error('Current time missing from prompt');
    if (!payload.input.includes('site:bukgu.gwangju.kr')) throw new Error('Official-domain search guidance missing');
  });
} finally {
  restoreFetch();
}

await assert('All seven visible prompts classify deterministically', async () => {
  const cases = [
    ['불법 주정차 신고는 어디서 하나요?', 'illegal_parking'],
    ['공동주택 관련 문의는 어느 부서에 해야 하나요?', 'housing_department'],
    ['매트리스 폐기 신청은 어디서 하나요?', 'bulky_waste'],
    ['여권 발급은 어디서 하나요?', 'passport_guidance'],
    ['무인민원발급기 어디 있어요?', 'unmanned_kiosk'],
    ['가로등이 고장났어요. 신고할게요', 'streetlight_report'],
    ['쓰레기 무단투기 신고할래', 'litter_ai_assist'],
  ];
  for (const [question, expected] of cases) {
    const actual = functionModule.classifyAction(question);
    if (actual !== expected) throw new Error(`${question}: expected ${expected}, got ${actual}`);
  }
});

await assert('Unknown question remains chat-only action none', async () => {
  if (functionModule.classifyAction('안녕하세요') !== 'none') throw new Error('Unknown question must be none');
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------
console.log(`\n=== Results: ${passed} passed, ${failed} failed ===\n`);

// Restore original fetch so process exit doesn't leave a stub behind.
globalThis.fetch = _ORIGINAL_FETCH;

if (failed > 0) {
  console.error('Failures:');
  for (const f of failures) {
    console.error(`  - ${f.description}: ${f.error}`);
  }
  process.exit(1);
}
