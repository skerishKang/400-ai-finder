/**
 * Contract tests for the Stage 4 Page Agent server-side model adapter.
 *
 *   functions/api/page-agent/v1/chat/completions.js
 *
 * All upstream provider calls are mocked; no network / secret is used.
 * The adapter is imported directly from the Functions source so the policy
 * + validation gateway is exercised in isolation.
 *
 * Gated behind RUN_CLOUDFLARE_FUNCTION_CONTRACTS=1 (matches the
 * existing MVP function contract harness).
 */

const RUN_CONTRACTS = process.env.RUN_CLOUDFLARE_FUNCTION_CONTRACTS === '1';

if (!RUN_CONTRACTS) {
  console.log('[SKIP] RUN_CLOUDFLARE_FUNCTION_CONTRACTS not set');
  process.exit(0);
}

const REAL_FETCH = globalThis.fetch;
let fetchCalls = 0;
let lastFetch = null;

function installFetch(handler) {
  fetchCalls = 0;
  lastFetch = null;
  globalThis.fetch = async (url, init) => {
    fetchCalls += 1;
    lastFetch = { url: url, init: init };
    return handler(url, init, fetchCalls);
  };
}

function restoreFetch() {
  globalThis.fetch = REAL_FETCH;
}

function makeRequest(opts) {
  opts = opts || {};
  const method = opts.method || 'POST';
  const origin = opts.origin === undefined ? 'http://localhost:8766' : opts.origin;
  const contentType = opts.contentType || 'application/json';
  const body = opts.body === undefined ? {} : opts.body;
  const rawText = opts.rawText !== undefined ? opts.rawText : JSON.stringify(body);
  const headers = new Map();
  headers.set('Content-Type', contentType);
  if (origin) headers.set('Origin', origin);
  if (opts.auth) headers.set('Authorization', opts.auth);
  return {
    method: method,
    url: 'http://localhost:8766/api/page-agent/v1/chat/completions',
    headers: headers,
    text: async () => rawText,
    json: async () => (rawText ? JSON.parse(rawText) : {}),
  };
}

// ---- sample PageAgent runtime payload helpers ----

function toolCallsMessages(userRequest, browserState, extra) {
  const userText =
    '<agent_state>\n' +
    '<user_request>' + userRequest + '</user_request>\n' +
    '<browser_state>\n' + browserState + '\n</browser_state>\n' +
    (extra || '') +
    '</agent_state>';
  return [
    { role: 'system', content: 'plan only' },
    { role: 'user', content: userText },
  ];
}

function bodyWith(messages, macroName) {
  macroName = macroName || 'AgentOutput';
  return {
    model: 'ignored-browser-model',
    messages: messages,
    tools: [{ type: 'function', function: { name: macroName, description: 'x', parameters: {} } }],
    tool_choice: { type: 'function', function: { name: macroName } },
  };
}

const SAFE_BROWSER_STATE =
  '[0]<a href="#" data-action-target="nav-civil-service">종합민원</a>\n' +
  '[1]<button data-action-target="confirm-draft-prefill" type="button">제출하기</button>\n' +
  '[2]<div data-action-target="apartment-guidance-card" tabindex="0">공동주택과</div>\n' +
  '[3]<a href="#" data-action-target="mayor-office-open">열린구청장실</a>\n' +
  '[5]<a href="https://evil.example.com" data-action-target="nav-civil-service">외부</a>\n' +
  '[7]<button data-action-target="login-button">로그인</button>';

function agentOutputArgs(actionObj) {
  return JSON.stringify({ action: actionObj });
}

// ---- provider stubs (no manual bracket towers) ----

function provOk(actionObj, name) {
  return async () => {
    const result = {
      choices: [
        {
          message: {
            tool_calls: [
              {
                function: {
                  name: name || 'AgentOutput',
                  arguments: agentOutputArgs(actionObj),
                },
              },
            ],
          },
        },
      ],
    };
    return { ok: true, status: 200, json: async () => result };
  };
}
function provFail(status) {
  return async () => ({ ok: false, status: status || 500, json: async () => ({}) });
}
function provJsonThrow() {
  return async () => ({ ok: true, status: 200, json: async () => { throw new Error('bad'); } });
}
function provEmptyChoices() {
  return async () => ({ ok: true, status: 200, json: async () => ({ choices: [] }) });
}
function provNoTool() {
  return async () => ({ ok: true, status: 200, json: async () => ({ choices: [{ message: { tool_calls: [] } }] }) });
}
function provTwoTools(textA, textB) {
  return async () => {
    const result = {
      choices: [
        {
          message: {
            tool_calls: [
              {
                function: {
                  name: 'AgentOutput',
                  arguments: agentOutputArgs({ done: { text: textA, success: true } }),
                },
              },
              {
                function: {
                  name: 'AgentOutput',
                  arguments: agentOutputArgs({ done: { text: textB, success: true } }),
                },
              },
            ],
          },
        },
      ],
    };
    return { ok: true, status: 200, json: async () => result };
  };
}
function provWrongName() {
  return async () => {
    const result = {
      choices: [
        {
          message: {
            tool_calls: [
              {
                function: {
                  name: 'OtherTool',
                  arguments: agentOutputArgs({ done: { text: 'a', success: true } }),
                },
              },
            ],
          },
        },
      ],
    };
    return { ok: true, status: 200, json: async () => result };
  };
}
function provBadArgs() {
  return async () => {
    const result = {
      choices: [
        {
          message: {
            tool_calls: [
              {
                function: {
                  name: 'AgentOutput',
                  arguments: 'not-json',
                },
              },
            ],
          },
        },
      ],
    };
    return { ok: true, status: 200, json: async () => result };
  };
}

// ---- test harness ----

const mod = await import(new URL('../../functions/api/page-agent/_adapter.js', import.meta.url).pathname);
const P = await import(new URL('../../functions/api/page-agent/_policy.js', import.meta.url).pathname);
const onRequest = mod.onRequest;
const resolveConfig = mod.resolveConfig;
const validateAction = mod.validateAction;
const validateProviderResponse = mod.validateProviderResponse;
const buildSafeDone = mod.buildSafeDone;
const sanitizeUserRequest = mod.sanitizeUserRequest;
const redactBrowserState = mod.redactBrowserState;
const extractUserRequest = mod.extractUserRequest;
const countSteps = mod.countSteps;
const extractUsedClickIndices = mod.extractUsedClickIndices;
const parseBrowserStateElements = mod.parseBrowserStateElements;

let passed = 0;
let failed = 0;
const failures = [];

async function assert(desc, fn) {
  try {
    await fn();
    passed += 1;
    console.log('  PASS ' + desc);
  } catch (err) {
    failed += 1;
    failures.push({ desc: desc, error: err.message });
    console.log('  FAIL ' + desc + ': ' + err.message);
  }
}

function eq(actual, expected, msg) {
  if (actual !== expected) {
    throw new Error(msg + ' (expected ' + JSON.stringify(expected) + ', got ' + JSON.stringify(actual) + ')');
  }
}
function ok(cond, msg) {
  if (!cond) throw new Error(msg);
}

async function callOn(body, env, opts) {
  const request = makeRequest(Object.assign({ body: body }, opts || {}));
  const res = await onRequest({ request: request, env: env || {} });
  const data = await res.json();
  return { res: res, data: data };
}

// ---- 1. disabled / config ----

await assert('default disabled (no env) -> safe done, 0 upstream', async () => {
  installFetch(async () => { throw new Error('should not be called'); });
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), {});
  eq(fetchCalls, 0, 'upstream calls');
  eq(r.res.status, 200, 'status');
  const tc = r.data.choices[0].message.tool_calls[0];
  eq(tc.function.name, 'AgentOutput', 'macro');
  eq(JSON.parse(tc.function.arguments).action.done.success, false, 'done success');
  restoreFetch();
});

await assert('enabled but missing provider key -> 0 upstream', async () => {
  installFetch(async () => { throw new Error('no'); });
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(fetchCalls, 0, 'upstream calls');
  eq(r.res.status, 200, 'status');
  restoreFetch();
});

await assert('unknown provider -> 0 upstream', async () => {
  installFetch(async () => { throw new Error('no'); });
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'openai', GEMINI_API_KEY: 'k' };
  await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(fetchCalls, 0, 'upstream calls');
  restoreFetch();
});

await assert('resolveConfig disabled when not enabled', () => {
  const c = resolveConfig({});
  eq(c.usable, false, 'usable');
  eq(c.provider, '', 'provider');
});

await assert('resolveConfig usable with gemini + secret', () => {
  const c = resolveConfig({ PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'sec' });
  eq(c.usable, true, 'usable');
  eq(c.provider, 'gemini', 'provider');
  ok(c.endpoint.indexOf('generativelanguage.googleapis.com') > 0, 'endpoint');
});

await assert('endpoint override only via allowlisted https host', () => {
  const bad = resolveConfig({ PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 's', PAGE_AGENT_GEMINI_ENDPOINT: 'http://evil.test/x' });
  ok(bad.endpoint.indexOf('generativelanguage.googleapis.com') > 0, 'bad override ignored');
  const good = resolveConfig({ PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 's', PAGE_AGENT_GEMINI_ENDPOINT: 'https://generativelanguage.googleapis.com/v1/x' });
  ok(good.endpoint.indexOf('https://generativelanguage.googleapis.com/v1/x') === 0, 'good override honoured');
});

// ---- 2. HTTP / origin ----

await assert('OPTIONS preflight -> 200, 0 upstream', async () => {
  installFetch(async () => { throw new Error('no'); });
  const request = makeRequest({ method: 'OPTIONS' });
  const res = await onRequest({ request: request, env: {} });
  eq(res.status, 200, 'status');
  eq(fetchCalls, 0, 'upstream');
  restoreFetch();
});

await assert('GET -> 405', async () => {
  const request = makeRequest({ method: 'GET' });
  const res = await onRequest({ request: request, env: {} });
  eq(res.status, 405, 'status');
});

await assert('invalid origin -> 403', async () => {
  const request = makeRequest({ origin: 'https://evil.example.com' });
  const res = await onRequest({ request: request, env: {} });
  eq(res.status, 403, 'status');
});

await assert('malformed origin -> 403', async () => {
  const request = makeRequest({ origin: 'not a url ::' });
  const res = await onRequest({ request: request, env: {} });
  eq(res.status, 403, 'status');
});

await assert('invalid content type -> 415', async () => {
  const request = makeRequest({ contentType: 'text/plain' });
  const res = await onRequest({ request: request, env: {} });
  eq(res.status, 415, 'status');
});

await assert('invalid JSON -> 400', async () => {
  const request = makeRequest({ rawText: '{not json' });
  const res = await onRequest({ request: request, env: {} });
  eq(res.status, 400, 'status');
});

await assert('oversized body -> 413', async () => {
  const big = 'x'.repeat(100000);
  const body = bodyWith(toolCallsMessages(big, SAFE_BROWSER_STATE));
  const request = makeRequest({ body: body, rawText: JSON.stringify(body) });
  const res = await onRequest({ request: request, env: {} });
  eq(res.status, 413, 'status');
});

await assert('missing messages -> 400', async () => {
  const request = makeRequest({ body: { tools: [] } });
  const res = await onRequest({ request: request, env: {} });
  eq(res.status, 400, 'status');
});

await assert('wrong macro name -> 400', async () => {
  const body = bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE), 'OtherTool');
  const request = makeRequest({ body: body });
  const res = await onRequest({ request: request, env: {} });
  eq(res.status, 400, 'status');
});

// ---- 3. sanitization ----

await assert('inbound Authorization never forwarded; provider key used', async () => {
  installFetch(async (url, init) => {
    ok(init.headers.Authorization === 'Bearer srv-secret', 'provider auth');
    ok(init.headers.Authorization !== 'Bearer inbound-fake', 'inbound ignored');
    return provOk({ click_element_by_index: { index: 2 } })();
  });
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'srv-secret' };
  const request = makeRequest({ body: bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), auth: 'Bearer inbound-fake' });
  await onRequest({ request: request, env: env });
  ok(lastFetch.init.body.indexOf('ignored-browser-model') === -1, 'browser model not proxied');
  ok(lastFetch.init.body.indexOf('AgentOutput') !== -1, 'fresh provider tool sent');
  restoreFetch();
});

await assert('browser-provided model ignored (env model used)', async () => {
  installFetch(async (url, init) => {
    const sent = JSON.parse(init.body);
    eq(sent.model, 'gemini-2.0-flash', 'model from env default');
    return provOk({ done: { text: 'ok', success: true } })();
  });
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  restoreFetch();
});

await assert('PII user request -> rejected, 0 upstream', async () => {
  installFetch(async () => { throw new Error('no'); });
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('내 계좌 123-456-789012 확인해줘', SAFE_BROWSER_STATE)), env);
  eq(fetchCalls, 0, 'upstream');
  eq(r.res.status, 200, 'status');
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('input value redacted from provider payload', async () => {
  const stateWithValue = '[2]<div data-action-target="apartment-guidance-card">공동주택과</div>\n[9]<input data-action-target="complaint-body" value="비밀주민내용">글</input>';
  installFetch(async (url, init) => {
    ok(init.body.indexOf('비밀주민내용') === -1, 'value redacted');
    return provOk({ done: { text: 'ok', success: true } })();
  });
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  await callOn(bodyWith(toolCallsMessages('공동주택과', stateWithValue)), env);
  restoreFetch();
});

await assert('control characters stripped from user request', () => {
  const cleaned = sanitizeUserRequest('공동\u0000주택\u0007과');
  eq(cleaned, '공동주택과', 'control chars removed');
});

// ---- 4. provider behaviour ----

await assert('exactly 1 fetch, no retry', async () => {
  installFetch(provOk({ click_element_by_index: { index: 2 } }));
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(fetchCalls, 1, 'fetch count');
  restoreFetch();
});

await assert('provider timeout -> safe done', async () => {
  installFetch(async () => { throw new Error('aborted'); });
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(fetchCalls, 1, 'fetch count');
  eq(r.res.status, 200, 'status');
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('provider non-2xx -> safe done', async () => {
  installFetch(provFail(500));
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'hy3', KILOCODE_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('provider malformed JSON -> safe done', async () => {
  installFetch(provJsonThrow());
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('empty choices -> malformed -> safe done', async () => {
  installFetch(provEmptyChoices());
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('missing tool call -> safe done', async () => {
  installFetch(provNoTool());
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('multiple tool calls -> safe done', async () => {
  installFetch(provTwoTools('a', 'b'));
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('incorrect function name -> safe done', async () => {
  installFetch(provWrongName());
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('malformed arguments -> safe done', async () => {
  installFetch(provBadArgs());
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('oversized done text -> clamped to limit', () => {
  const big = '결과입니다. '.repeat(400);
  const r = validateAction({ done: { text: big, success: true } }, new Map(), {});
  ok(r.ok, 'validated');
  eq(r.value.done.text.length, P.MAX_DONE_TEXT_CHARS, 'clamped');
});

// ---- 5. action policy ----

await assert('allowed click on safe target -> returned', async () => {
  installFetch(provOk({ click_element_by_index: { index: 2 } }));
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  const action = JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action;
  eq(action.click_element_by_index.index, 2, 'click index 2');
  restoreFetch();
});

await assert('click on nonexistent index -> unsafe_target', async () => {
  installFetch(provOk({ click_element_by_index: { index: 99 } }));
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('out-of-range (negative) index -> invalid_action', () => {
  const r = validateAction({ click_element_by_index: { index: -1 } }, new Map(), {});
  eq(r.ok, false, 'not ok');
  eq(r.failureCode, 'invalid_action', 'code');
});

await assert('click submit button -> unsafe_target', async () => {
  installFetch(provOk({ click_element_by_index: { index: 1 } }));
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('click external href -> unsafe_target', async () => {
  installFetch(provOk({ click_element_by_index: { index: 5 } }));
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('click login button -> unsafe_target', async () => {
  installFetch(provOk({ click_element_by_index: { index: 7 } }));
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('execute_javascript (unknown) -> unknown_action', () => {
  const r = validateAction({ execute_javascript: { script: 'x' } }, new Map(), {});
  eq(r.ok, false, 'not ok');
  eq(r.failureCode, 'unknown_action', 'code');
});

await assert('unknown action -> unknown_action', () => {
  const r = validateAction({ go_to: { url: 'x' } }, new Map(), {});
  eq(r.failureCode, 'unknown_action', 'code');
});

await assert('multiple action keys -> invalid_action', () => {
  const r = validateAction({ done: { text: 'a', success: true }, scroll: {} }, new Map(), {});
  eq(r.failureCode, 'invalid_action', 'code');
});

await assert('deceptive submit-complete done text -> rejected', () => {
  const r = validateAction({ done: { text: '민원이 정상적으로 접수되었습니다.', success: true } }, new Map(), {});
  eq(r.ok, false, 'not ok');
  eq(r.failureCode, 'invalid_action', 'code');
});

await assert('scroll out-of-bounds -> clamped', () => {
  const r = validateAction({ scroll: { num_pages: 999 } }, new Map(), {});
  ok(r.ok, 'ok');
  eq(r.value.scroll.num_pages, P.SCROLL_MAX_PAGES, 'clamped');
});

await assert('safe done success preserved', async () => {
  installFetch(provOk({ done: { text: '공동주택과 안내입니다.', success: true } }));
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  const action = JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action;
  eq(action.done.success, true, 'success preserved');
  restoreFetch();
});

// ---- 6. step safety ----

await assert('max step -> safe done, 0 upstream', async () => {
  installFetch(async () => { throw new Error('no'); });
  const history = '<step_1>Action Results: {"click_element_by_index":{"index":2}}</step_1>\n<step_2>Action Results: {"click_element_by_index":{"index":3}}</step_2>';
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k', PAGE_AGENT_LLM_MAX_STEPS: '2' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE, history)), env);
  eq(fetchCalls, 0, 'upstream');
  eq(r.res.status, 200, 'status');
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('repeated click -> safe done after 1 call', async () => {
  installFetch(provOk({ click_element_by_index: { index: 2 } }));
  const history = '<step_1>Action Results: {"click_element_by_index":{"index":2}}</step_1>';
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE, history)), env);
  eq(fetchCalls, 1, 'one upstream call');
  eq(JSON.parse(r.data.choices[0].message.tool_calls[0].function.arguments).action.done.success, false, 'safe done');
  restoreFetch();
});

await assert('malformed history does not crash', () => {
  eq(countSteps('garbage no steps here'), 0, 'zero steps');
  const set = extractUsedClickIndices('no clicks');
  eq(set.size, 0, 'empty set');
});

// ---- 7. response hygiene ----

await assert('response is OpenAI-compatible safe structure', async () => {
  installFetch(provOk({ done: { text: 'ok', success: false } }));
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'hy3', KILOCODE_API_KEY: 'k' };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과', SAFE_BROWSER_STATE)), env);
  eq(r.res.status, 200, 'status');
  eq(r.data.object, 'chat.completion', 'object');
  eq(r.data.choices.length, 1, 'one choice');
  eq(r.data.choices[0].message.tool_calls.length, 1, 'one tool call');
  eq(r.data.choices[0].message.content, null, 'no content');
  eq(r.res.headers.get('Cache-Control'), 'no-store', 'no-store');
  restoreFetch();
});

await assert('no secret / raw DOM / prompt / stack in response or log', async () => {
  installFetch(provOk({ done: { text: 'ok', success: false } }));
  const env = { PAGE_AGENT_LLM_ENABLED: 'true', PAGE_AGENT_LLM_PROVIDER: 'gemini', GEMINI_API_KEY: 'SUPER_SECRET_KEY', PAGE_AGENT_LLM_DEBUG: '1' };
  const captured = [];
  const origLog = console.log;
  console.log = function () { captured.push(Array.prototype.join.call(arguments, ' ')); };
  const r = await callOn(bodyWith(toolCallsMessages('공동주택과 연락처', SAFE_BROWSER_STATE)), env);
  console.log = origLog;
  const dump = JSON.stringify(r.data) + ' ' + captured.join(' ');
  ok(dump.indexOf('SUPER_SECRET_KEY') === -1, 'no secret');
  ok(dump.indexOf('data-action-target') === -1, 'no raw DOM');
  ok(dump.indexOf('공동주택과 연락처') === -1, 'no raw prompt');
  ok(dump.indexOf('.stack') === -1 && dump.indexOf(' at ') === -1, 'no stack trace');
  restoreFetch();
});

// ---- 8. pure helper contracts ----

await assert('isAllowedOrigin accepts pages + localhost, rejects others', () => {
  ok(P.isAllowedOrigin('https://cgbukku.pages.dev'), 'prod');
  ok(P.isAllowedOrigin('https://preview.cgbukku.pages.dev'), 'preview');
  ok(P.isAllowedOrigin('http://localhost:8766'), 'localhost');
  ok(!P.isAllowedOrigin('https://evil.example.com'), 'evil');
  ok(!P.isAllowedOrigin('not a url'), 'malformed');
});

await assert('isSafeTarget allowlist + forbidden', () => {
  ok(P.isSafeTarget('nav-civil-service'), 'nav');
  ok(P.isSafeTarget('apartment-guidance-card'), 'card');
  ok(!P.isSafeTarget('confirm-draft-prefill'), 'submit');
  ok(!P.isSafeTarget('login-button'), 'login');
});

await assert('detectUserRequestPii catches RRN / card / phone / email', () => {
  ok(P.detectUserRequestPii('주민번호 123456-1234567 알려줘'), 'rrn');
  ok(P.detectUserRequestPii('카드 1234 5678 9012 3456'), 'card');
  ok(P.detectUserRequestPii('내 번호 010-1234-5678'), 'phone');
  ok(P.detectUserRequestPii('me@test.com 문의'), 'email');
  eq(P.detectUserRequestPii('공동주택과 연락처 찾아줘'), null, 'clean');
});

await assert('parseBrowserStateElements extracts index/target', () => {
  const map = parseBrowserStateElements(SAFE_BROWSER_STATE);
  ok(map.has(2), 'index 2 present');
  eq(map.get(2).target, 'apartment-guidance-card', 'target');
  eq(map.get(0).href, '#', 'href');
});

// ---- summary ----

console.log('\n[PageAgent server adapter] passed=' + passed + ' failed=' + failed);
if (failed > 0) {
  console.log('FAILURES:');
  for (const f of failures) console.log('  - ' + f.desc + ': ' + f.error);
  process.exit(1);
}
console.log('All Page Agent server adapter contract tests passed.');
