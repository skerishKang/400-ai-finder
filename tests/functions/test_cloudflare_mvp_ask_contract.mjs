/**
 * Contract tests for the Cloudflare Pages `/api/mvp/ask` function.
 * All upstream calls are mocked; no provider network is used.
 */

const RUN_CONTRACTS = process.env.RUN_CLOUDFLARE_FUNCTION_CONTRACTS === '1';

if (!RUN_CONTRACTS) {
  console.log('[SKIP] RUN_CLOUDFLARE_FUNCTION_CONTRACTS not set');
  process.exit(0);
}

const ORIGINAL_FETCH = globalThis.fetch;

function noNetworkStub() {
  throw new Error('NETWORK_BLOCKED: unexpected upstream call');
}

globalThis.fetch = noNetworkStub;

function createMockContext(method, body, envOverrides = {}) {
  const request = {
    method,
    headers: new Map([['Content-Type', 'application/json']]),
    json: async () => (body ? JSON.parse(body) : {}),
    text: async () => (body ? String(body) : ''),
  };
  const env = {
    GEMINI_API_KEY: '',
    KILOCODE_API_KEY: '',
    ...envOverrides,
  };
  return { request, env };
}

const FUNCTION_PATH = new URL('../../functions/api/mvp/ask.js', import.meta.url).pathname;
let functionModule;
try {
  functionModule = await import(`file://${FUNCTION_PATH}`);
} catch (error) {
  console.error('[FAIL] Could not import Cloudflare Function:', error.message);
  process.exit(1);
}

const { onRequest } = functionModule;
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

async function requestJson(method, body, envOverrides) {
  const response = await onRequest(createMockContext(method, body, envOverrides));
  const text = await response.text();
  return { response, data: text ? JSON.parse(text) : null };
}

function expectEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function expectIsoDate(value, label) {
  if (typeof value !== 'string' || Number.isNaN(Date.parse(value))) {
    throw new Error(`${label}: invalid ISO date ${JSON.stringify(value)}`);
  }
}

let fetchCalls = [];

function mockFetchSequence(responses) {
  fetchCalls = [];
  let index = 0;
  globalThis.fetch = async (url, options = {}) => {
    fetchCalls.push({
      url: typeof url === 'string' ? url : url.toString(),
      method: options.method || 'GET',
      headers: options.headers || {},
      body: options.body || '',
    });
    const response = responses[Math.min(index, responses.length - 1)];
    index += 1;
    if (response.throw) throw response.throw;
    const status = response.status ?? 200;
    const payload = response.body ?? {};
    return {
      ok: status >= 200 && status < 300,
      status,
      text: async () => (typeof payload === 'string' ? payload : JSON.stringify(payload)),
      json: async () => (typeof payload === 'string' ? JSON.parse(payload) : payload),
    };
  };
}

function restoreFetch() {
  globalThis.fetch = noNetworkStub;
  fetchCalls = [];
}

function chatResponse(answer, action = 'none', confidence = 0.8) {
  return {
    choices: [{
      message: {
        content: JSON.stringify({ answer, action, confidence }),
      },
    }],
  };
}

function groundedInteraction(answer, annotations = []) {
  return {
    steps: [
      { type: 'google_search_call', arguments: { queries: ['site:bukgu.gwangju.kr 북구청 공지'] } },
      {
        type: 'model_output',
        content: [{
          type: 'text',
          text: JSON.stringify({ answer, action: 'none', confidence: 0.9 }),
          annotations,
        }],
      },
    ],
  };
}

console.log('\n=== Cloudflare MVP provider failover contract ===\n');

await assert('OPTIONS returns restricted CORS response', async () => {
  const { response } = await requestJson('OPTIONS', null);
  expectEqual(response.status, 200, 'status');
  expectEqual(response.headers.get('Access-Control-Allow-Origin'), 'https://cgbukku.pages.dev', 'origin');
  expectEqual(response.headers.get('Cache-Control'), 'no-store', 'cache control');
});

for (const method of ['GET', 'PUT', 'DELETE']) {
  await assert(`${method} returns 405`, async () => {
    const { response } = await requestJson(method, null);
    expectEqual(response.status, 405, 'status');
  });
}

await assert('invalid JSON fails closed without provider call', async () => {
  const { data } = await requestJson('POST', 'not-json', { GEMINI_API_KEY: 'test-gemini' });
  expectEqual(data.ok, false, 'ok');
  expectEqual(data.failure_code, 'invalid_input', 'failure_code');
  expectEqual(fetchCalls.length, 0, 'fetch call count');
});

await assert('missing question returns 400', async () => {
  const { response, data } = await requestJson('POST', JSON.stringify({}), { GEMINI_API_KEY: 'test-gemini' });
  expectEqual(response.status, 400, 'status');
  expectEqual(data.error, 'Missing question', 'error');
});

for (const question of [null, 123, [], {}, true, false]) {
  await assert(`non-string question ${JSON.stringify(question)} is invalid`, async () => {
    const { data } = await requestJson('POST', JSON.stringify({ question }), { GEMINI_API_KEY: 'test-gemini' });
    expectEqual(data.failure_code, 'invalid_input', 'failure_code');
    expectEqual(fetchCalls.length, 0, 'fetch call count');
  });
}

await assert('empty question returns 400', async () => {
  const { response } = await requestJson('POST', JSON.stringify({ question: '   ' }));
  expectEqual(response.status, 400, 'status');
});

await assert('question over 300 characters is rejected', async () => {
  const { data } = await requestJson('POST', JSON.stringify({ question: 'x'.repeat(301) }));
  expectEqual(data.failure_code, 'invalid_input', 'failure_code');
});

await assert('visible action allowlist contains seven journeys plus none', async () => {
  expectEqual(functionModule.VALID_ACTIONS.length, 8, 'action count');
  for (const action of ['passport_guidance', 'streetlight_report', 'litter_ai_assist', 'none']) {
    if (!functionModule.VALID_ACTIONS.includes(action)) throw new Error(`missing ${action}`);
  }
});

await assert('provider order defaults to Gemini then HY3', async () => {
  expectEqual(functionModule.normalizeProviderOrder().join(','), 'gemini,hy3', 'default order');
  expectEqual(functionModule.normalizeProviderOrder('hy3,gemini').join(','), 'hy3,gemini', 'custom order');
  expectEqual(functionModule.normalizeProviderOrder('bad,bad').join(','), 'gemini,hy3', 'invalid order fallback');
  expectEqual(functionModule.normalizeProviderOrder('gemini,gemini,hy3').join(','), 'gemini,hy3', 'deduped order');
});

await assert('no configured keys returns config_error for primary provider', async () => {
  const { data } = await requestJson('POST', JSON.stringify({ question: '안녕하세요' }));
  expectEqual(data.ok, false, 'ok');
  expectEqual(data.failure_code, 'config_error', 'failure_code');
  expectEqual(data.provider, 'gemini', 'provider');
  expectEqual(data.model, 'gemini-3.1-flash-lite', 'model');
  expectEqual(fetchCalls.length, 0, 'fetch call count');
});

await assert('Gemini OpenAI-compatible endpoint is primary', async () => {
  try {
    mockFetchSequence([{ body: chatResponse('여권 발급 안내입니다.', 'passport_guidance', 0.95) }]);
    const { data } = await requestJson('POST', JSON.stringify({ question: '여권 발급 알려줘' }), {
      GEMINI_API_KEY: 'test-gemini',
      KILOCODE_API_KEY: 'test-hy3',
    });
    expectEqual(data.ok, true, 'ok');
    expectEqual(data.provider, 'gemini', 'provider');
    expectEqual(data.model, 'gemini-3.1-flash-lite', 'model');
    expectEqual(data.action, 'passport_guidance', 'action');
    expectEqual(data.fallback_used, false, 'fallback_used');
    expectEqual(data.freshness_state, 'model_only', 'freshness_state');
    expectIsoDate(data.retrieved_at, 'retrieved_at');
    expectEqual(fetchCalls.length, 1, 'fetch call count');
    expectEqual(fetchCalls[0].url, 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions', 'Gemini URL');
    expectEqual(fetchCalls[0].headers.Authorization, 'Bearer test-gemini', 'Gemini auth');
    const payload = JSON.parse(fetchCalls[0].body);
    expectEqual(payload.model, 'gemini-3.1-flash-lite', 'Gemini model');
    if (!payload.messages[0].content.includes('현재 대한민국 표준시각')) throw new Error('current time missing');
  } finally {
    restoreFetch();
  }
});

await assert('Gemini model and endpoint are operator-configurable', async () => {
  try {
    mockFetchSequence([{ body: chatResponse('설정 반영') }]);
    await requestJson('POST', JSON.stringify({ question: '테스트' }), {
      GEMINI_API_KEY: 'test-gemini',
      GEMINI_MODEL: 'custom-gemini',
      GEMINI_API_ENDPOINT: 'https://gemini.example.test/chat/completions',
    });
    expectEqual(fetchCalls[0].url, 'https://gemini.example.test/chat/completions', 'custom endpoint');
    expectEqual(JSON.parse(fetchCalls[0].body).model, 'custom-gemini', 'custom model');
  } finally {
    restoreFetch();
  }
});

await assert('Gemini HTTP failure falls back to HY3', async () => {
  try {
    mockFetchSequence([
      { status: 503, body: { error: 'unavailable' } },
      { body: chatResponse('HY3 폴백 답변입니다.') },
    ]);
    const { data } = await requestJson('POST', JSON.stringify({ question: '일반 민원 질문' }), {
      GEMINI_API_KEY: 'test-gemini',
      KILOCODE_API_KEY: 'test-hy3',
    });
    expectEqual(data.ok, true, 'ok');
    expectEqual(data.provider, 'hy3', 'provider');
    expectEqual(data.model, 'tencent/hy3:free', 'model');
    expectEqual(data.fallback_used, true, 'fallback_used');
    expectEqual(fetchCalls.length, 2, 'fetch call count');
    expectEqual(fetchCalls[1].url, 'https://api.kilo.ai/api/gateway/v1/chat/completions', 'HY3 URL');
    expectEqual(fetchCalls[1].headers.Authorization, 'Bearer test-hy3', 'HY3 auth');
  } finally {
    restoreFetch();
  }
});

await assert('missing Gemini key skips directly to HY3', async () => {
  try {
    mockFetchSequence([{ body: chatResponse('HY3 직접 응답') }]);
    const { data } = await requestJson('POST', JSON.stringify({ question: '질문' }), {
      KILOCODE_API_KEY: 'test-hy3',
    });
    expectEqual(data.provider, 'hy3', 'provider');
    expectEqual(data.fallback_used, true, 'fallback_used');
    expectEqual(fetchCalls.length, 1, 'fetch call count');
  } finally {
    restoreFetch();
  }
});

await assert('HY3 reasoning-only response supplies the final answer', async () => {
  try {
    mockFetchSequence([{ body: {
      choices: [{ message: {
        content: '',
        reasoning: '<think>internal notes</think>\n```json\n{"answer":"reasoning 폴백 답변","action":"none","confidence":0.7}\n```',
      } }],
    } }]);
    const { data } = await requestJson('POST', JSON.stringify({ question: '질문' }), {
      MVP_LLM_ORDER: 'hy3',
      KILOCODE_API_KEY: 'test-hy3',
    });
    expectEqual(data.ok, true, 'ok');
    expectEqual(data.answer, 'reasoning 폴백 답변', 'answer');
    if (data.answer.includes('internal notes')) throw new Error('reasoning leaked');
  } finally {
    restoreFetch();
  }
});

await assert('operator can make HY3 the primary provider', async () => {
  try {
    mockFetchSequence([{ body: chatResponse('HY3 우선 응답') }]);
    const { data } = await requestJson('POST', JSON.stringify({ question: '질문' }), {
      MVP_LLM_ORDER: 'hy3,gemini',
      GEMINI_API_KEY: 'test-gemini',
      KILOCODE_API_KEY: 'test-hy3',
    });
    expectEqual(data.provider, 'hy3', 'provider');
    expectEqual(data.fallback_used, false, 'fallback_used');
    expectEqual(fetchCalls.length, 1, 'fetch call count');
  } finally {
    restoreFetch();
  }
});

await assert('empty Gemini response falls back to HY3', async () => {
  try {
    mockFetchSequence([
      { body: { choices: [{ message: { content: '   ' } }] } },
      { body: chatResponse('빈 응답 뒤 HY3') },
    ]);
    const { data } = await requestJson('POST', JSON.stringify({ question: '질문' }), {
      GEMINI_API_KEY: 'test-gemini',
      KILOCODE_API_KEY: 'test-hy3',
    });
    expectEqual(data.provider, 'hy3', 'provider');
    expectEqual(fetchCalls.length, 2, 'fetch call count');
  } finally {
    restoreFetch();
  }
});

await assert('all configured providers failing returns sanitized upstream_error', async () => {
  try {
    mockFetchSequence([
      { status: 500, body: { secret: 'do-not-expose' } },
      { status: 429, body: { secret: 'do-not-expose' } },
    ]);
    const { data } = await requestJson('POST', JSON.stringify({ question: '질문' }), {
      GEMINI_API_KEY: 'test-gemini',
      KILOCODE_API_KEY: 'test-hy3',
    });
    expectEqual(data.ok, false, 'ok');
    expectEqual(data.failure_code, 'upstream_error', 'failure_code');
    if (JSON.stringify(data).includes('do-not-expose')) throw new Error('raw upstream body leaked');
  } finally {
    restoreFetch();
  }
});

await assert('optional Gemini Interactions mode keeps search grounding', async () => {
  const officialCitation = {
    type: 'url_citation',
    title: '광주 북구청',
    url: 'https://bukgu.gwangju.kr/board.es?mid=a10201010000',
  };
  try {
    mockFetchSequence([{ body: groundedInteraction('공식 공지를 확인했습니다.', [officialCitation]) }]);
    const { data } = await requestJson('POST', JSON.stringify({ question: '최신 공지 알려줘' }), {
      GEMINI_API_KEY: 'test-gemini',
      GEMINI_API_STYLE: 'interactions',
      GEMINI_MODEL: 'gemini-3.5-flash',
      GEMINI_API_ENDPOINT: 'https://generativelanguage.googleapis.com/v1beta/interactions',
    });
    expectEqual(data.provider, 'gemini', 'provider');
    expectEqual(data.freshness_state, 'live_official', 'freshness_state');
    expectEqual(data.source_url, officialCitation.url, 'source_url');
    expectEqual(fetchCalls[0].headers['x-goog-api-key'], 'test-gemini', 'Interactions auth');
    const payload = JSON.parse(fetchCalls[0].body);
    expectEqual(payload.store, false, 'store');
    expectEqual(payload.tools[0].type, 'google_search', 'tool');
  } finally {
    restoreFetch();
  }
});

await assert('all seven visible prompts classify deterministically', async () => {
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
    expectEqual(functionModule.classifyAction(question), expected, question);
  }
  expectEqual(functionModule.classifyAction('안녕하세요'), 'none', 'unknown action');
});

console.log(`\n=== Results: ${passed} passed, ${failed} failed ===\n`);
globalThis.fetch = ORIGINAL_FETCH;

if (failed > 0) {
  for (const failure of failures) {
    console.error(`- ${failure.description}: ${failure.error}`);
  }
  process.exit(1);
}
