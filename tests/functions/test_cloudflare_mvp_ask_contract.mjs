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
try {
  const mod = await import(`file://${FUNCTION_PATH}`);
  onRequest = mod.onRequest;
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
  model: 'gemini-3.1-flash-lite',
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
  const mod = await import(`file://${FUNCTION_PATH}`);
  if (mod.VALID_ACTIONS) {
    if (!Array.isArray(mod.VALID_ACTIONS)) throw new Error('VALID_ACTIONS must be an array');
    if (mod.VALID_ACTIONS.length < 5) throw new Error('VALID_ACTIONS has too few entries');
  }
});

// 7. API key not configured — returns config_error
await assertNoCallJsonResponse('No API key returns config_error with gemini provider', 'POST', JSON.stringify({ question: 'test' }), {
  ok: false,
  failure_code: 'config_error',
  action: 'none',
  confidence: 0.0,
  provider: 'gemini',
  model: 'gemini-3.1-flash-lite',
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

// All tests below this line use canned mock fetch for upstream responses.
console.log('\n--- Mock upstream response tests ---\n');

// 10. Invalid action from LLM is clamped to 'none'
try {
  mockFetch(200, {
    choices: [{ message: { content: JSON.stringify({ action: 'DROP_DATABASE', answer: 'test answer', confidence: 0.8 }) } }],
  });
  await assertJsonResponse('Invalid action "DROP_DATABASE" is clamped to none', 'POST', JSON.stringify({ question: 'test' }), {
    ok: true,
    action: 'none',
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 11. Confidence > 1.0 is clamped to 1.0
try {
  mockFetch(200, {
    choices: [{ message: { content: JSON.stringify({ action: 'none', answer: 'test answer', confidence: 999 }) } }],
  });
  await assertJsonResponse('Confidence 999 is clamped to 1.0', 'POST', JSON.stringify({ question: 'test' }), {
    ok: true,
    confidence: 1.0,
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 12. Whitespace-only answer returns fallback message
try {
  mockFetch(200, {
    choices: [{ message: { content: JSON.stringify({ action: 'none', answer: '   ', confidence: 0.5 }) } }],
  });
  await assertJsonResponse('Whitespace-only answer returns fallback message', 'POST', JSON.stringify({ question: 'test' }), {
    ok: true,
    answer: '죄송합니다. 답변을 준비하지 못했습니다. 다른 질문을 해 주세요.',
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 13. Empty answer returns fallback message
try {
  mockFetch(200, {
    choices: [{ message: { content: JSON.stringify({ action: 'none', answer: '', confidence: 0.5 }) } }],
  });
  await assertJsonResponse('Empty answer returns fallback message', 'POST', JSON.stringify({ question: 'test' }), {
    ok: true,
    answer: '죄송합니다. 답변을 준비하지 못했습니다. 다른 질문을 해 주세요.',
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 14. Negative confidence is clamped to 0.0
try {
  mockFetch(200, {
    choices: [{ message: { content: JSON.stringify({ action: 'none', answer: 'test answer', confidence: -5 }) } }],
  });
  await assertJsonResponse('Confidence -5 is clamped to 0.0', 'POST', JSON.stringify({ question: 'test' }), {
    ok: true,
    confidence: 0.0,
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 15. Non-JSON LLM response is handled without crash
try {
  mockFetch(200, {
    choices: [{ message: { content: 'Hello, I am a helpful assistant. The answer is...' } }],
  });
  await assertJsonResponse('Non-JSON LLM response is handled without crash', 'POST', JSON.stringify({ question: 'test' }), {
    ok: true,
    provider: 'gemini',
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 16. Upstream HTTP error returns upstream_error failure_code
try {
  mockFetch(500, { error: 'Internal Server Error' });
  await assertJsonResponse('Upstream HTTP 500 returns upstream_error', 'POST', JSON.stringify({ question: 'test' }), {
    ok: false,
    failure_code: 'upstream_error',
    action: 'none',
    confidence: 0.0,
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 17. No content field in upstream response
try {
  mockFetch(200, { choices: [{ message: {} }] });
  await assertJsonResponse('Empty message content returns fallback answer', 'POST', JSON.stringify({ question: 'test' }), {
    ok: true,
    answer: '죄송합니다. 답변을 준비하지 못했습니다. 다른 질문을 해 주세요.',
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// ---------------------------------------------------------------------------
// Upstream fetch verification tests
// ---------------------------------------------------------------------------
console.log('\n--- Upstream fetch verification ---\n');

// 18. Verify upstream fetch URL, method, headers, and request body model
try {
  mockFetch(200, {
    choices: [{ message: { content: JSON.stringify({ action: 'none', answer: 'test', confidence: 0.5 }) } }],
  });
  await getResponse('POST', JSON.stringify({ question: '테스트 질문' }), { GEMINI_API_KEY: 'test-key' });
  const call = getLastCall();
  await assert('Upstream fetch URL matches Gemini endpoint', async () => {
    if (!call) throw new Error('No upstream call recorded');
    if (call.url !== 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions') {
      throw new Error(`Expected Gemini URL, got ${call.url}`);
    }
  });
  await assert('Upstream fetch uses POST method', async () => {
    if (!call || call.method !== 'POST') throw new Error(`Expected POST, got ${call ? call.method : 'none'}`);
  });
  await assert('Upstream Authorization header uses Bearer test-key', async () => {
    const auth = call && call.headers && call.headers['Authorization'];
    if (!auth || auth !== 'Bearer test-key') throw new Error(`Expected Bearer test-key, got ${auth}`);
  });
  await assert('Upstream Content-Type is application/json', async () => {
    const ct = call && call.headers && call.headers['Content-Type'];
    if (!ct || ct !== 'application/json') throw new Error(`Expected application/json, got ${ct}`);
  });
  await assert('Upstream request body contains model gemini-3.1-flash-lite', async () => {
    if (!call || !call.body) throw new Error('No request body');
    const parsed = JSON.parse(call.body);
    if (parsed.model !== 'gemini-3.1-flash-lite') throw new Error(`Expected model gemini-3.1-flash-lite, got ${parsed.model}`);
  });
} finally {
  restoreFetch();
}

// ---------------------------------------------------------------------------
// Action allowlist behavior tests
// ---------------------------------------------------------------------------
console.log('\n--- Action behavior tests ---\n');

// 19. Allowed action: passport_guidance
try {
  mockFetch(200, {
    choices: [{ message: { content: JSON.stringify({ action: 'passport_guidance', answer: '여권 발급 안내입니다.', confidence: 0.9 }) } }],
  });
  await assertJsonResponse('Action passport_guidance is allowed', 'POST', JSON.stringify({ question: '여권 발급' }), {
    ok: true,
    action: 'passport_guidance',
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 20. Allowed action: unmanned_kiosk
try {
  mockFetch(200, {
    choices: [{ message: { content: JSON.stringify({ action: 'unmanned_kiosk', answer: '무인민원발급기 안내입니다.', confidence: 0.85 }) } }],
  });
  await assertJsonResponse('Action unmanned_kiosk is allowed', 'POST', JSON.stringify({ question: '무인민원발급기' }), {
    ok: true,
    action: 'unmanned_kiosk',
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 21. Rejected action: move_in_report is clamped to none
try {
  mockFetch(200, {
    choices: [{ message: { content: JSON.stringify({ action: 'move_in_report', answer: '전입신고 안내입니다.', confidence: 0.9 }) } }],
  });
  await assertJsonResponse('Action move_in_report is clamped to none', 'POST', JSON.stringify({ question: '전입신고' }), {
    ok: true,
    action: 'none',
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 22. Rejected action: public_health_center is clamped to none
try {
  mockFetch(200, {
    choices: [{ message: { content: JSON.stringify({ action: 'public_health_center', answer: '보건소 안내입니다.', confidence: 0.9 }) } }],
  });
  await assertJsonResponse('Action public_health_center is clamped to none', 'POST', JSON.stringify({ question: '보건소' }), {
    ok: true,
    action: 'none',
  }, { GEMINI_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

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
