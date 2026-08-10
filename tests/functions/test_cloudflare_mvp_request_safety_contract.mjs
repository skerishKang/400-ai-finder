const ORIGINAL_FETCH = globalThis.fetch;

globalThis.fetch = async () => {
  throw new Error('NETWORK_BLOCKED: unexpected provider call');
};

const safety = await import('../../functions/api/mvp/request-safety.js');
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

function makeRequest(body, headers = {}, method = 'POST') {
  const requestHeaders = new Headers({ 'Content-Type': 'application/json', ...headers });
  return {
    method,
    url: 'http://localhost:8788/api/mvp/ask',
    headers: requestHeaders,
    text: async () => String(body ?? ''),
  };
}

async function invoke(body, env = {}, headers = {}) {
  const request = makeRequest(body, headers);
  const response = await askModule.onRequest({
    request,
    env: {
      GEMINI_API_KEY: '',
      KILOCODE_API_KEY: '',
      MVP_RUNTIME_LOGS: '0',
      MVP_TURNSTILE_MODE: 'disabled',
      ...env,
    },
  });
  const text = await response.text();
  return { response, data: text ? JSON.parse(text) : null };
}

function providerSuccess(answer = '북구청 안내를 확인해 드립니다.') {
  return {
    ok: true,
    status: 200,
    json: async () => ({
      choices: [{ message: { content: JSON.stringify({ answer, action: 'none', confidence: 0.9 }) } }],
    }),
    text: async () => '',
  };
}

console.log('\n=== Cloudflare MVP request/privacy safety contract ===\n');

await check('body byte limit defaults to 8192', async () => {
  equal(safety.resolveMaxBodyBytes({}), 8192, 'default');
  equal(safety.resolveMaxBodyBytes({ MVP_MAX_BODY_BYTES: '8192' }), 8192, 'explicit');
});

await check('invalid or out-of-range body byte limit fails to default', async () => {
  for (const value of ['x', '0', '1023', '32769', '-1', '999999999999999999999']) {
    equal(safety.resolveMaxBodyBytes({ MVP_MAX_BODY_BYTES: value }), 8192, value);
  }
});

await check('valid body byte limit override is accepted', async () => {
  equal(safety.resolveMaxBodyBytes({ MVP_MAX_BODY_BYTES: '1024' }), 1024, 'min');
  equal(safety.resolveMaxBodyBytes({ MVP_MAX_BODY_BYTES: '32768' }), 32768, 'max');
});

await check('unsupported media type is rejected before parse', async () => {
  const request = makeRequest('{}', { 'Content-Type': 'text/plain' });
  const result = await safety.readBoundedJsonBody(request, {});
  equal(result.ok, false, 'ok');
  equal(result.status, 415, 'status');
  equal(result.failureCode, 'unsupported_media_type', 'failure');
});

await check('declared Content-Length over cap is rejected', async () => {
  const request = makeRequest('{}', { 'Content-Length': '9000' });
  const result = await safety.readBoundedJsonBody(request, {});
  equal(result.status, 413, 'status');
  equal(result.failureCode, 'payload_too_large', 'failure');
});

await check('actual UTF-8 bytes over cap are rejected', async () => {
  const body = JSON.stringify({ question: '가'.repeat(400), locale: 'ko' });
  const result = await safety.readBoundedJsonBody(makeRequest(body), { MVP_MAX_BODY_BYTES: '1024' });
  equal(result.status, 413, 'status');
});

await check('streamed body stops reading and cancels after byte cap', async () => {
  const chunks = [new Uint8Array(700), new Uint8Array(700), new Uint8Array(700)];
  let index = 0;
  let cancelled = false;
  const request = {
    headers: new Headers({ 'Content-Type': 'application/json' }),
    body: {
      getReader() {
        return {
          async read() {
            if (index >= chunks.length) return { done: true, value: undefined };
            return { done: false, value: chunks[index++] };
          },
          async cancel() { cancelled = true; },
        };
      },
    },
    text: async () => { throw new Error('stream path should not call text()'); },
  };
  const result = await safety.readBoundedJsonBody(request, { MVP_MAX_BODY_BYTES: '1024' });
  equal(result.status, 413, 'status');
  equal(result.failureCode, 'payload_too_large', 'failure');
  equal(cancelled, true, 'reader cancelled');
  equal(index, 2, 'chunks read before rejection');
});

await check('malformed JSON is invalid_input', async () => {
  const result = await safety.readBoundedJsonBody(makeRequest('{bad'), {});
  equal(result.ok, false, 'ok');
  equal(result.failureCode, 'invalid_input', 'failure');
});

await check('strict request shape rejects non-object bodies', async () => {
  for (const body of [null, [], 'x', 1, true]) {
    equal(safety.validateRequestShape(body).ok, false, JSON.stringify(body));
  }
});

await check('strict request shape rejects unknown top-level fields', async () => {
  const result = safety.validateRequestShape({ question: 'hello', extra: true });
  equal(result.ok, false, 'ok');
  equal(result.reason, 'unknown_field', 'reason');
});

await check('strict request shape accepts question locale and valid session_id only', async () => {
  const result = safety.validateRequestShape({
    question: '안내해 주세요',
    locale: 'ko',
    session_id: 'mvp_session_0123456789abcdef',
  });
  equal(result.ok, true, 'ok');
});

await check('malformed and oversized session IDs are rejected', async () => {
  for (const id of ['short', 'bad session id 123456789', 'x'.repeat(129)]) {
    equal(safety.validateRequestShape({ question: '안내', session_id: id }).ok, false, id.slice(0, 20));
  }
});

await check('resident-id-like input is fail-closed', async () => {
  const result = safety.assessQuestionPrivacy('제 주민번호는 900101-1234567 입니다');
  equal(result.ok, false, 'ok');
  equal(result.failureCode, 'sensitive_input_rejected', 'failure');
  if (!result.categories.includes('resident_id_like')) throw new Error('resident category missing');
  equal(result.question, '', 'question');
});

await check('phone email and precise address are redacted without raw spans', async () => {
  const raw = '연락처 010-1234-5678, a.person@example.com, 광주 북구 우치로 77 관련 안내';
  const result = safety.assessQuestionPrivacy(raw);
  equal(result.ok, true, 'ok');
  for (const secret of ['010-1234-5678', 'a.person@example.com', '광주 북구 우치로 77']) {
    if (result.question.includes(secret)) throw new Error(`raw sensitive span leaked: ${secret}`);
  }
  for (const category of ['phone_like', 'email_like', 'precise_address_like']) {
    if (!result.categories.includes(category)) throw new Error(`category missing: ${category}`);
  }
});

await check('resident-id-like ingress reaches zero provider fetches', async () => {
  let calls = 0;
  globalThis.fetch = async () => { calls += 1; return providerSuccess(); };
  const { data } = await invoke(JSON.stringify({ question: '주민번호 900101-1234567 로 확인해줘', locale: 'ko' }), {
    GEMINI_API_KEY: 'test-key',
  });
  equal(data.ok, false, 'ok');
  equal(data.failure_code, 'sensitive_input_rejected', 'failure_code');
  equal(calls, 0, 'provider fetch count');
});

await check('oversized ingress reaches zero provider fetches', async () => {
  let calls = 0;
  globalThis.fetch = async () => { calls += 1; return providerSuccess(); };
  const body = JSON.stringify({ question: '가'.repeat(400), locale: 'ko' });
  const { response, data } = await invoke(body, { GEMINI_API_KEY: 'test-key', MVP_MAX_BODY_BYTES: '1024' });
  equal(response.status, 413, 'status');
  equal(data.failure_code, 'payload_too_large', 'failure_code');
  equal(calls, 0, 'provider fetch count');
});

await check('wrong content type reaches zero provider fetches', async () => {
  let calls = 0;
  globalThis.fetch = async () => { calls += 1; return providerSuccess(); };
  const request = makeRequest(JSON.stringify({ question: '안내', locale: 'ko' }), { 'Content-Type': 'text/plain' });
  const response = await askModule.onRequest({ request, env: { GEMINI_API_KEY: 'test-key', MVP_RUNTIME_LOGS: '0' } });
  const data = JSON.parse(await response.text());
  equal(response.status, 415, 'status');
  equal(data.failure_code, 'unsupported_media_type', 'failure_code');
  equal(calls, 0, 'provider fetch count');
});

await check('redacted sensitive spans are never sent to provider', async () => {
  let providerBody = '';
  globalThis.fetch = async (url, options = {}) => {
    providerBody = String(options.body || '');
    return providerSuccess();
  };
  const rawPhone = '010-1234-5678';
  const rawEmail = 'a.person@example.com';
  const rawAddress = '광주 북구 우치로 77';
  const question = `제 연락처 ${rawPhone}, ${rawEmail}, 주소 ${rawAddress}인데 여권 안내해줘`;
  const { data } = await invoke(JSON.stringify({ question, locale: 'ko' }), { GEMINI_API_KEY: 'test-key' });
  equal(data.ok, true, 'ok');
  for (const secret of [rawPhone, rawEmail, rawAddress]) {
    if (providerBody.includes(secret)) throw new Error(`provider body leaked ${secret}`);
    if (String(data.question || '').includes(secret)) throw new Error(`response question leaked ${secret}`);
  }
});

await check('too-long input never echoes raw sensitive text', async () => {
  const rawPhone = '010-1234-5678';
  const question = rawPhone + ' ' + 'x'.repeat(301);
  const { data } = await invoke(JSON.stringify({ question, locale: 'ko' }));
  equal(data.ok, false, 'ok');
  equal(data.failure_code, 'invalid_input', 'failure_code');
  if (String(data.question || '').includes(rawPhone)) throw new Error('raw phone echoed in too-long failure');
});

await check('new ingress/privacy failures are explicitly non-retryable', async () => {
  const wrongTypeRequest = makeRequest(JSON.stringify({ question: '안내' }), { 'Content-Type': 'text/plain' });
  const wrongTypeResponse = await askModule.onRequest({ request: wrongTypeRequest, env: { MVP_RUNTIME_LOGS: '0' } });
  const wrongType = JSON.parse(await wrongTypeResponse.text());
  equal(wrongType.error.retryable, false, 'unsupported media retryable');

  const largeBody = JSON.stringify({ question: '가'.repeat(400) });
  const large = await invoke(largeBody, { MVP_MAX_BODY_BYTES: '1024' });
  equal(large.data.error.retryable, false, 'payload too large retryable');

  const sensitive = await invoke(JSON.stringify({ question: '주민번호 900101-1234567', locale: 'ko' }));
  equal(sensitive.data.error.retryable, false, 'sensitive input retryable');
});

await check('sanitized runtime log allowlists privacy categories and excludes raw sensitive data', async () => {
  const rawEmail = 'secret.person@example.com';
  const log = askModule.buildSanitizedRuntimeLog({
    ok: false,
    question: rawEmail,
    answer: rawEmail,
    failure_code: 'sensitive_input_rejected',
    meta: {
      privacy: {
        sensitive_input_detected: true,
        categories: ['email_like', rawEmail],
        redacted: true,
        session_id_present: true,
      },
    },
  });
  const serialized = JSON.stringify(log);
  if (serialized.includes(rawEmail)) throw new Error('raw sensitive value leaked into runtime log');
  equal(log.privacy.categories.length, 1, 'privacy category count');
  equal(log.privacy.categories[0], 'email_like', 'privacy category');
});

globalThis.fetch = ORIGINAL_FETCH;

if (failed) {
  throw new Error(`request/privacy safety contracts failed: ${failed}/${passed + failed}\n${failures.join('\n')}`);
}

console.log(`\nRequest/privacy safety contracts: ${passed}/${passed + failed} PASS`);
