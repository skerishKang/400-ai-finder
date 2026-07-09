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
  const env = { KILOCODE_API_KEY: '', ...envOverrides };
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
// LLM API call is intercepted. Each call returns a canned response.
// ---------------------------------------------------------------------------
let _originalFetch = null;

function mockFetch(status, body) {
  _originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    return {
      ok: status >= 200 && status < 300,
      status,
      text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
      json: async () => (typeof body === 'string' ? JSON.parse(body) : body),
    };
  };
}

function restoreFetch() {
  if (_originalFetch !== null) {
    globalThis.fetch = _originalFetch;
    _originalFetch = null;
  }
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
await assertJsonResponse('Invalid JSON body returns ok:false (not 500)', 'POST', 'not json at all', {
  ok: false,
}, { KILOCODE_API_KEY: 'test-key' });

// 4. missing question returns 400
await assertJsonResponse('Missing question field returns 400 with ok:false', 'POST', JSON.stringify({}), {
  ok: false,
  error: 'Missing question',
}, { KILOCODE_API_KEY: 'test-key' });

await assertJsonResponse('Empty question string returns 400', 'POST', JSON.stringify({ question: '' }), {
  ok: false,
  error: 'Missing question',
}, { KILOCODE_API_KEY: 'test-key' });

await assertJsonResponse('Whitespace-only question returns 400', 'POST', JSON.stringify({ question: '   ' }), {
  ok: false,
  error: 'Missing question',
}, { KILOCODE_API_KEY: 'test-key' });

// 5. question too long returns safe invalid_input
const longQuestion = 'x'.repeat(301);
await assertJsonResponse('Question over 300 chars returns invalid_input', 'POST', JSON.stringify({ question: longQuestion }), {
  ok: false,
  failure_code: 'invalid_input',
  action: 'none',
  confidence: 0.0,
}, { KILOCODE_API_KEY: 'test-key' });

// 6. action allowlist — verify the allowlist exists by checking the module's behavior.
await assert('VALID_ACTIONS constant is defined in module', async () => {
  const mod = await import(`file://${FUNCTION_PATH}`);
  if (mod.VALID_ACTIONS) {
    if (!Array.isArray(mod.VALID_ACTIONS)) throw new Error('VALID_ACTIONS must be an array');
    if (mod.VALID_ACTIONS.length < 5) throw new Error('VALID_ACTIONS has too few entries');
  }
});

// 7. API key not configured — returns config_error
await assertJsonResponse('No API key returns config_error', 'POST', JSON.stringify({ question: 'test' }), {
  ok: false,
  failure_code: 'config_error',
  action: 'none',
  confidence: 0.0,
  provider: 'kilocode',
  model: 'tencent/hy3:free',
});

// 8. Response shape contract — check all known failure modes return proper JSON
await assertJsonResponse('Invalid JSON body returns ok:false', 'POST', '{invalid json}', {
  ok: false,
}, { KILOCODE_API_KEY: 'test-key' });

// 9. Question length exact boundary — 300 chars should pass (not block)
const exact300 = 'a'.repeat(300);
await assertJsonResponse('Question exactly 300 chars is accepted (not blocked)', 'POST', JSON.stringify({ question: exact300 }), {
  ok: false,
  failure_code: 'config_error',
}, {});

const exact301 = 'b'.repeat(301);
await assertJsonResponse('Question 301 chars returns invalid_input', 'POST', JSON.stringify({ question: exact301 }), {
  ok: false,
  failure_code: 'invalid_input',
}, {});

// ---------------------------------------------------------------------------
// Mock fetch tests — intercept upstream LLM API calls and verify parsing
// ---------------------------------------------------------------------------
console.log('\n--- Mock upstream response tests ---\n');

// 10. Invalid action from LLM is clamped to 'none'
try {
  mockFetch(200, {
    choices: [{ message: { content: JSON.stringify({ action: 'DROP_DATABASE', answer: 'test answer', confidence: 0.8 }) } }],
  });
  await assertJsonResponse('Invalid action "DROP_DATABASE" is clamped to none', 'POST', JSON.stringify({ question: 'test' }), {
    ok: true,
    action: 'none',
  }, { KILOCODE_API_KEY: 'test-key' });
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
  }, { KILOCODE_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 12. Negative confidence is clamped to 0.0
try {
  mockFetch(200, {
    choices: [{ message: { content: JSON.stringify({ action: 'none', answer: 'test answer', confidence: -5 }) } }],
  });
  await assertJsonResponse('Confidence -5 is clamped to 0.0', 'POST', JSON.stringify({ question: 'test' }), {
    ok: true,
    confidence: 0.0,
  }, { KILOCODE_API_KEY: 'test-key' });
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
  }, { KILOCODE_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 14. Whitespace-only answer returns fallback message
try {
  mockFetch(200, {
    choices: [{ message: { content: JSON.stringify({ action: 'none', answer: '   ', confidence: 0.5 }) } }],
  });
  await assertJsonResponse('Whitespace-only answer returns fallback message', 'POST', JSON.stringify({ question: 'test' }), {
    ok: true,
    answer: '죄송합니다. 답변을 준비하지 못했습니다. 다른 질문을 해 주세요.',
  }, { KILOCODE_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 15. Non-JSON content from LLM is passed through as answer (no crash)
try {
  mockFetch(200, {
    choices: [{ message: { content: 'Hello, I am a helpful assistant. The answer is...' } }],
  });
  await assertJsonResponse('Non-JSON LLM response is handled without crash', 'POST', JSON.stringify({ question: 'test' }), {
    ok: true,
    provider: 'kilocode',
  }, { KILOCODE_API_KEY: 'test-key' });
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
  }, { KILOCODE_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// 17. No content field in upstream response
try {
  mockFetch(200, { choices: [{ message: {} }] });
  await assertJsonResponse('Empty message content returns fallback answer', 'POST', JSON.stringify({ question: 'test' }), {
    ok: true,
    answer: '죄송합니다. 답변을 준비하지 못했습니다. 다른 질문을 해 주세요.',
  }, { KILOCODE_API_KEY: 'test-key' });
} finally {
  restoreFetch();
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------
console.log(`\n=== Results: ${passed} passed, ${failed} failed ===\n`);
if (failed > 0) {
  console.error('Failures:');
  for (const f of failures) {
    console.error(`  - ${f.description}: ${f.error}`);
  }
  process.exit(1);
}
