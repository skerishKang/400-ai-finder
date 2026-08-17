import assert from 'node:assert/strict';

const ORIGINAL_FETCH = globalThis.fetch;
const GENERAL_PATH = new URL('../../functions/api/mvp/general.js', import.meta.url).pathname;
const ASK_PATH = new URL('../../functions/api/mvp/ask.js', import.meta.url).pathname;

const generalModule = await import(`file://${GENERAL_PATH}`);
const askModule = await import(`file://${ASK_PATH}`);
const { onRequest: onGeneral, buildGeneralModelPrompt } = generalModule;
const { onRequest: onAsk } = askModule;

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
    failures.push(`${name}: ${error && error.message ? error.message : error}`);
    console.log(`  FAIL ${name}: ${error && error.message ? error.message : error}`);
  }
}

function env(overrides = {}) {
  return {
    GEMINI_API_KEY: '',
    KILOCODE_API_KEY: '',
    MVP_RUNTIME_LOGS: '0',
    ...overrides,
  };
}

function request(body, url = 'http://localhost/api/mvp/general') {
  return new Request(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function callGeneral(body, overrides = {}, url = 'http://localhost/api/mvp/general') {
  const response = await onGeneral({ request: request(body, url), env: env(overrides) });
  return { response, data: JSON.parse(await response.text()) };
}

async function callAsk(body, overrides = {}, url = 'http://localhost/api/mvp/ask') {
  const response = await onAsk({ request: request(body, url), env: env(overrides) });
  return { response, data: JSON.parse(await response.text()) };
}

function successChatResponse(answer) {
  return new Response(JSON.stringify({
    choices: [{
      message: {
        content: JSON.stringify({ answer, action: 'housing_department', confidence: 0.81 }),
      },
    }],
    usage: { prompt_tokens: 30, completion_tokens: 20, total_tokens: 50 },
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

function successInteractionResponse(answer) {
  return new Response(JSON.stringify({
    steps: [{
      type: 'model_output',
      content: [{
        type: 'text',
        text: JSON.stringify({ answer, action: 'illegal_parking', confidence: 0.73 }),
        annotations: [{
          type: 'url_citation',
          title: 'Must not become provenance',
          url: 'https://example.com/not-official-evidence',
        }],
      }],
    }],
    usage: { total_input_tokens: 25, total_output_tokens: 15 },
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

function assertGeneralProvenance(data) {
  assert.equal(data.grounded, false);
  assert.equal(data.source_kind, 'general_model');
  assert.equal(data.evidence_kind, 'none');
  assert.equal(data.answer_scope, 'general_model');
  assert.equal(data.freshness_state, 'model_only');
  assert.equal(data.action, 'none');
  assert.equal(data.source_url, '');
  assert.deepEqual(data.sources, []);
  assert.deepEqual(data.search_queries, []);
  assert.equal(data.fallback_to_bukgu, false);
}

try {
  globalThis.fetch = async () => {
    throw new Error('NETWORK_BLOCKED: unexpected upstream call');
  };

  await check('legacy /api/mvp/ask Seo-gu request remains site_unconfigured and provider-free', async () => {
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      throw new Error('unexpected provider call');
    };
    const { data } = await callAsk({
      question: '회의록을 깔끔하게 정리하는 방법을 알려줘',
      locale: 'ko',
      site_id: 'seogu_gwangju',
    }, { GEMINI_API_KEY: 'test-key' });
    assert.equal(data.ok, false);
    assert.equal(data.failure_code, 'site_unconfigured_for_slice');
    assert.equal(data.site_id, 'seogu_gwangju');
    assert.equal(calls, 0);
  });

  await check('unknown site never receives a general-model provider call', async () => {
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      throw new Error('unexpected provider call');
    };
    const { data } = await callGeneral({
      question: '회의록을 정리하는 방법을 알려줘',
      locale: 'ko',
      site_id: 'atlantis_gov',
    }, { GEMINI_API_KEY: 'test-key' });
    assert.equal(data.ok, false);
    assert.equal(data.failure_code, 'unknown_site');
    assert.equal(data.site_id, 'atlantis_gov');
    assert.equal(calls, 0);
    assertGeneralProvenance(data);
  });

  await check('request shape/type validation remains fail-closed before provider call', async () => {
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      throw new Error('unexpected provider call');
    };
    const { data } = await callGeneral({
      question: '회의록을 정리하는 방법을 알려줘',
      locale: 'ko',
      site_id: 123,
    }, { GEMINI_API_KEY: 'test-key' });
    assert.equal(data.ok, false);
    assert.equal(data.failure_code, 'invalid_input');
    assert.equal(calls, 0);
  });

  await check('resident-ID-like input is rejected before provider call', async () => {
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      throw new Error('unexpected provider call');
    };
    const { data } = await callGeneral({
      question: '제 주민번호는 900101-1234567인데 회의록 정리법 알려줘',
      locale: 'ko',
      site_id: 'seogu_gwangju',
    }, { GEMINI_API_KEY: 'test-key' });
    assert.equal(data.ok, false);
    assert.equal(data.failure_code, 'sensitive_input_rejected');
    assert.equal(calls, 0);
    assertGeneralProvenance(data);
  });

  await check('known Seo-gu with no configured provider fails honestly', async () => {
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      throw new Error('unexpected provider call');
    };
    const { data } = await callGeneral({
      question: '회의록을 깔끔하게 정리하는 방법을 알려줘',
      locale: 'ko',
      site_id: 'seogu_gwangju',
    });
    assert.equal(data.ok, false);
    assert.equal(data.failure_code, 'config_error');
    assert.equal(calls, 0);
    assertGeneralProvenance(data);
  });

  await check('general prompt is institution-neutral and explicitly model-only', async () => {
    const prompt = buildGeneralModelPrompt('2026. 08. 17. 19:00:00', 'ko');
    assert.ok(prompt.includes('general model knowledge only'));
    assert.ok(prompt.includes('NOT based on an institution website'));
    assert.ok(!prompt.includes('Buk-gu Helper'));
    assert.ok(!prompt.includes('<official_reference>'));
    assert.ok(!prompt.includes('bukgu.gwangju.kr'));
    assert.ok(!prompt.includes('google_search'));
  });

  await check('OpenAI-compatible general success has exact non-clone provenance and forced action none', async () => {
    const calls = [];
    globalThis.fetch = async (url, init) => {
      calls.push({ url: String(url), init, body: JSON.parse(init.body) });
      return successChatResponse('회의록은 목적, 결정사항, 담당자, 기한 순서로 정리하면 읽기 쉽습니다. 항목마다 한 문장으로 요약하고 후속 조치를 별도로 표시하세요.');
    };
    const { data } = await callGeneral({
      question: '회의록을 깔끔하게 정리하는 방법을 알려줘',
      locale: 'ko',
      site_id: 'seogu_gwangju',
    }, {
      GEMINI_API_KEY: 'test-key',
      MVP_ALLOW_LOCAL_PROVIDER_ENDPOINT: '1',
      GEMINI_API_ENDPOINT: 'http://127.0.0.1:9911/chat',
      GEMINI_API_STYLE: 'openai',
    });
    assert.equal(data.ok, true);
    assert.equal(data.site_id, 'seogu_gwangju');
    assert.equal(data.site_status, 'recognized_unconfigured');
    assert.equal(calls.length, 1);
    assertGeneralProvenance(data);
    const system = calls[0].body.messages[0].content;
    assert.ok(system.includes('general model knowledge only'));
    assert.ok(!system.includes('Buk-gu Helper'));
    assert.ok(!system.includes('<official_reference>'));
    assert.ok(!system.includes('bukgu.gwangju.kr'));
    assert.ok(!system.includes('google_search'));
  });

  await check('Gemini Interactions general mode sends no tools and discards citations/search provenance', async () => {
    const calls = [];
    globalThis.fetch = async (url, init) => {
      const body = JSON.parse(init.body);
      calls.push({ url: String(url), init, body });
      return successInteractionResponse('회의록은 안건별로 결정사항과 담당자, 완료 기한을 분리해 적으면 좋습니다. 마지막에는 다음 회의 전 확인할 후속 조치를 모아 두세요.');
    };
    const { data } = await callGeneral({
      question: '회의록을 깔끔하게 정리하는 방법을 알려줘',
      locale: 'ko',
      site_id: 'seogu_gwangju',
    }, {
      GEMINI_API_KEY: 'test-key',
      MVP_ALLOW_LOCAL_PROVIDER_ENDPOINT: '1',
      GEMINI_API_ENDPOINT: 'http://127.0.0.1:9912/interactions',
      GEMINI_API_STYLE: 'interactions',
    });
    assert.equal(data.ok, true);
    assert.equal(calls.length, 1);
    assert.ok(!Object.prototype.hasOwnProperty.call(calls[0].body, 'tools'));
    assert.ok(!calls[0].body.input.includes('google_search'));
    assertGeneralProvenance(data);
  });

  await check('general model may also run for configured Buk-gu without changing provenance', async () => {
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      return successChatResponse('회의록은 핵심 결정과 후속 조치를 중심으로 간결하게 정리하면 좋습니다. 담당자와 기한을 함께 적으면 실행 여부를 확인하기 쉽습니다.');
    };
    const { data } = await callGeneral({
      question: '회의록을 깔끔하게 정리하는 방법을 알려줘',
      locale: 'ko',
      site_id: 'bukgu_gwangju',
    }, {
      GEMINI_API_KEY: 'test-key',
      MVP_ALLOW_LOCAL_PROVIDER_ENDPOINT: '1',
      GEMINI_API_ENDPOINT: 'http://127.0.0.1:9913/chat',
    });
    assert.equal(data.ok, true);
    assert.equal(data.site_id, 'bukgu_gwangju');
    assert.equal(data.site_status, 'configured');
    assert.equal(calls, 1);
    assertGeneralProvenance(data);
  });
} finally {
  globalThis.fetch = ORIGINAL_FETCH;
}

console.log(`\nGeneral-model fallback contract: ${passed} passed, ${failed} failed`);
if (failed) {
  for (const failure of failures) console.error(`  - ${failure}`);
  process.exit(1);
}
