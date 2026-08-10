const ORIGINAL_FETCH = globalThis.fetch;
const askModule = await import('../../functions/api/mvp/ask.js');

let passed = 0;
let failed = 0;
const failures = [];

async function check(name, fn) {
  try {
    await fn();
    passed += 1;
    console.log(`  PASS ${name}`);
  } catch (error) {
    failed += 1;
    failures.push(`${name}: ${error.message}`);
    console.log(`  FAIL ${name}: ${error.message}`);
  }
}

function equal(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function baseEnv(overrides = {}) {
  return {
    GEMINI_API_KEY: 'test-gemini-key',
    KILOCODE_API_KEY: '',
    MVP_RUNTIME_LOGS: '0',
    MVP_TURNSTILE_MODE: 'required',
    MVP_TURNSTILE_SECRET_KEY: 'test-turnstile-secret',
    MVP_TURNSTILE_EXPECTED_ACTION: 'mvp_ask',
    MVP_TURNSTILE_ALLOWED_HOSTNAMES: 'cgbukku.pages.dev',
    MVP_TURNSTILE_TIMEOUT_MS: '1000',
    ...overrides,
  };
}

function requestBody(question, token) {
  const body = {
    question,
    locale: 'ko',
    session_id: 'mvp_session_0123456789abcdef',
  };
  if (token !== undefined) body.turnstile_token = token;
  return body;
}

async function invoke(body, env = baseEnv()) {
  const response = await askModule.onRequest({
    request: new Request('https://cgbukku.pages.dev/api/mvp/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
    env,
  });
  return { response, data: JSON.parse(await response.text()) };
}

function siteverifyResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  };
}

function providerResponse(answer = '북구청 여권 안내입니다.') {
  return {
    ok: true,
    status: 200,
    json: async () => ({
      choices: [{ message: { content: JSON.stringify({ answer, action: 'passport_guidance', confidence: 0.9 }) } }],
    }),
    text: async () => '',
  };
}

console.log('\n=== Cloudflare MVP Turnstile integration contract ===\n');

await check('missing Turnstile token blocks Siteverify and provider', async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    throw new Error('fetch must not run');
  };
  const { response, data } = await invoke(requestBody('여권 안내해줘'));
  equal(response.status, 403, 'status');
  equal(data.ok, false, 'ok');
  equal(data.failure_code, 'bot_verification_required', 'failure');
  equal(data.error.retryable, false, 'retryable');
  equal(calls, 0, 'fetch calls');
});

await check('rejected Turnstile token reaches Siteverify once and provider zero times', async () => {
  let siteverifyCalls = 0;
  let providerCalls = 0;
  globalThis.fetch = async (url) => {
    if (String(url).includes('/turnstile/v0/siteverify')) {
      siteverifyCalls += 1;
      return siteverifyResponse({ success: false, 'error-codes': ['invalid-input-response'] });
    }
    providerCalls += 1;
    return providerResponse();
  };
  const { response, data } = await invoke(requestBody('여권 안내해줘', 'invalid-token-123456'));
  equal(response.status, 403, 'status');
  equal(data.failure_code, 'bot_verification_failed', 'failure');
  equal(siteverifyCalls, 1, 'siteverify calls');
  equal(providerCalls, 0, 'provider calls');
});

await check('valid Turnstile token gates provider call and is never forwarded to provider', async () => {
  let siteverifyCalls = 0;
  let providerCalls = 0;
  let siteverifyBody = '';
  let providerBody = '';
  globalThis.fetch = async (url, options = {}) => {
    if (String(url).includes('/turnstile/v0/siteverify')) {
      siteverifyCalls += 1;
      siteverifyBody = String(options.body || '');
      return siteverifyResponse({
        success: true,
        action: 'mvp_ask',
        hostname: 'cgbukku.pages.dev',
        'error-codes': [],
      });
    }
    providerCalls += 1;
    providerBody = String(options.body || '');
    return providerResponse();
  };
  const token = 'valid-token-abcdefghijklmnopqrstuvwxyz';
  const { response, data } = await invoke(requestBody('여권 안내해줘', token));
  equal(response.status, 200, 'status');
  equal(data.ok, true, 'ok');
  equal(siteverifyCalls, 1, 'siteverify calls');
  equal(providerCalls, 1, 'provider calls');
  equal(data.meta.bot_defense.verified, true, 'verified metadata');
  if (!siteverifyBody.includes(token)) throw new Error('Siteverify did not receive token');
  if (providerBody.includes(token)) throw new Error('provider received Turnstile token');
  if (providerBody.includes('test-turnstile-secret')) throw new Error('provider received Turnstile secret');
});

await check('resident-ID-like input is rejected before any Siteverify call', async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    throw new Error('external fetch must not run for high-risk PII');
  };
  const { response, data } = await invoke(requestBody('주민번호 900101-1234567 로 확인해줘'));
  equal(response.status, 200, 'status');
  equal(data.failure_code, 'sensitive_input_rejected', 'failure');
  equal(calls, 0, 'external fetch calls');
});

await check('snapshot-only emergency mode does not require Turnstile or provider', async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    throw new Error('snapshot-only must remain network free');
  };
  const { response, data } = await invoke(
    requestBody('공동주택 관련 문의는 어느 부서에 해야 하나요?'),
    baseEnv({ MVP_AI_MODE: 'snapshot_only', GEMINI_API_KEY: '' }),
  );
  equal(response.status, 200, 'status');
  equal(data.failure_code, 'snapshot_only', 'failure');
  equal(data.meta.bot_defense.mode, 'not_applicable', 'bot defense mode');
  equal(calls, 0, 'external fetch calls');
});

globalThis.fetch = ORIGINAL_FETCH;

if (failed) {
  throw new Error(`Turnstile integration contracts failed: ${failed}/${passed + failed}\n${failures.join('\n')}`);
}

console.log(`\nTurnstile integration contracts: ${passed}/${passed + failed} PASS`);