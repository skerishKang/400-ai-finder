import fs from 'node:fs';
import vm from 'node:vm';

const TURNSTILE_PATH = new URL('../../src/web/static/citizen-turnstile.js', import.meta.url);
const BRIDGE_PATH = new URL('../../src/web/static/citizen-mvp-bridge.js', import.meta.url);
const TURNSTILE_SOURCE = fs.readFileSync(TURNSTILE_PATH, 'utf8');
const BRIDGE_SOURCE = fs.readFileSync(BRIDGE_PATH, 'utf8');
const OFFICIAL_SCRIPT = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

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

function makeResponse(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => '' },
    json: async () => data,
  };
}

function createHarness({
  configStatus = 200,
  configData = {
    ok: true,
    enabled: true,
    configured: true,
    mode: 'required',
    action: 'mvp_ask',
    site_key: 'test-public-site-key',
  },
  challengeMode = 'success',
  turnstilePreloaded = true,
} = {}) {
  const requests = [];
  const appendedScripts = [];
  const storage = new Map();
  let localStorageTouches = 0;
  let executeCount = 0;
  let resetCount = 0;
  let renderOptions = null;
  let pendingRenderOptions = null;

  const formParent = {
    insertBefore(node) {
      node.parentNode = formParent;
    },
  };
  const form = { parentNode: formParent };
  const body = {
    appendChild(node) {
      node.parentNode = body;
    },
  };
  const nodesById = new Map();
  const scripts = [];

  function makeTurnstileApi() {
    return {
      render(container, options) {
        renderOptions = options;
        pendingRenderOptions = options;
        if (container && container.id) nodesById.set(container.id, container);
        return 'widget-1';
      },
      execute(widgetId) {
        equal(widgetId, 'widget-1', 'widget id');
        executeCount += 1;
        const options = pendingRenderOptions;
        if (challengeMode === 'pending') return;
        if (challengeMode === 'error') {
          options['error-callback']('110200');
          return;
        }
        if (challengeMode === 'expired') {
          options['expired-callback']();
          return;
        }
        options.callback(`token-${executeCount}-abcdefghijklmnopqrstuvwxyz`);
      },
      reset(widgetId) {
        equal(widgetId, 'widget-1', 'reset widget id');
        resetCount += 1;
      },
    };
  }

  const document = {
    head: {
      appendChild(script) {
        script.parentNode = document.head;
        scripts.push(script);
        appendedScripts.push(script.src || '');
        if (script.src === OFFICIAL_SCRIPT) {
          window.turnstile = makeTurnstileApi();
          queueMicrotask(() => script.onload && script.onload());
        }
      },
    },
    body,
    createElement(tag) {
      const attrs = new Map();
      return {
        tagName: String(tag || '').toUpperCase(),
        id: '',
        className: '',
        src: '',
        async: false,
        defer: false,
        parentNode: null,
        setAttribute(name, value) { attrs.set(name, String(value)); },
        getAttribute(name) { return attrs.get(name) || null; },
        addEventListener() {},
      };
    },
    getElementById(id) {
      if (id === 'chat-composer-form') return form;
      return nodesById.get(id) || null;
    },
    querySelector(selector) {
      if (selector === 'script[data-citizen-turnstile-api="1"]') {
        return scripts.find((script) => script.getAttribute('data-citizen-turnstile-api') === '1') || null;
      }
      return null;
    },
  };

  const sessionStorage = {
    getItem(key) { return storage.has(key) ? storage.get(key) : null; },
    setItem(key, value) { storage.set(key, String(value)); },
  };

  const window = {
    CitizenI18n: {
      getLocale: () => 'ko',
      normalizeLocale: (value) => value || 'ko',
      t: () => '현재 AI 안내를 연결하지 못했습니다.',
    },
    AbortController,
    setTimeout,
    clearTimeout,
    crypto: {
      randomUUID: () => '123e4567-e89b-12d3-a456-426614174000',
    },
    sessionStorage,
  };
  if (turnstilePreloaded) window.turnstile = makeTurnstileApi();

  Object.defineProperty(window, 'localStorage', {
    get() {
      localStorageTouches += 1;
      throw new Error('localStorage must not be touched');
    },
  });

  async function fetch(url, options = {}) {
    requests.push({ url, options });
    if (url === '/api/mvp/turnstile-config') {
      return makeResponse(configData, configStatus);
    }
    if (url === '/api/mvp/ask') {
      return makeResponse({
        ok: true,
        answer: '북구청 안내입니다.',
        action: 'none',
        confidence: 0.9,
        request_id: '',
        schema_version: '1.0',
      });
    }
    throw new Error(`unexpected fetch ${url}`);
  }

  const context = {
    window,
    document,
    fetch,
    AbortController,
    Uint8Array,
    Promise,
    console,
    setTimeout,
    clearTimeout,
    queueMicrotask,
  };
  vm.runInNewContext(TURNSTILE_SOURCE, context, { filename: 'citizen-turnstile.js' });
  vm.runInNewContext(BRIDGE_SOURCE, context, { filename: 'citizen-mvp-bridge.js' });

  return {
    window,
    bridge: window.CitizenMvpBridge,
    client: window.CitizenTurnstile,
    requests,
    appendedScripts,
    executeCount: () => executeCount,
    resetCount: () => resetCount,
    renderOptions: () => renderOptions,
    localStorageTouches: () => localStorageTouches,
  };
}

function askRequests(harness) {
  return harness.requests.filter((request) => request.url === '/api/mvp/ask');
}

function configRequests(harness) {
  return harness.requests.filter((request) => request.url === '/api/mvp/turnstile-config');
}

console.log('\n=== Citizen MVP Turnstile client contract ===\n');

await check('protected ask obtains token and sends it only in request body', async () => {
  const harness = createHarness();
  const result = await harness.bridge.ask('여권 안내해줘');
  equal(result.ok, true, 'result ok');
  equal(configRequests(harness).length, 1, 'config calls');
  equal(askRequests(harness).length, 1, 'ask calls');
  const body = JSON.parse(askRequests(harness)[0].options.body);
  equal(body.turnstile_token, 'token-1-abcdefghijklmnopqrstuvwxyz', 'token');
  equal(body.question, '여권 안내해줘', 'question');
  if (JSON.stringify(harness.requests).includes('secret')) throw new Error('browser request leaked secret material');
});

await check('two asks use fresh single-use tokens and reset the widget', async () => {
  const harness = createHarness();
  await harness.bridge.ask('첫 질문');
  await harness.bridge.ask('둘째 질문');
  const asks = askRequests(harness);
  equal(asks.length, 2, 'ask calls');
  const first = JSON.parse(asks[0].options.body).turnstile_token;
  const second = JSON.parse(asks[1].options.body).turnstile_token;
  if (first === second) throw new Error('Turnstile token was reused');
  equal(configRequests(harness).length, 1, 'config cached for page lifetime');
  equal(harness.executeCount(), 2, 'challenge executions');
  if (harness.resetCount() < 2) throw new Error(`expected reset after asks, got ${harness.resetCount()}`);
});

await check('explicit widget uses execute and interaction-only modes', async () => {
  const harness = createHarness();
  await harness.bridge.ask('안내');
  const options = harness.renderOptions();
  equal(options.sitekey, 'test-public-site-key', 'site key');
  equal(options.action, 'mvp_ask', 'action');
  equal(options.execution, 'execute', 'execution');
  equal(options.appearance, 'interaction-only', 'appearance');
});

await check('config failure fails closed before protected ask', async () => {
  const harness = createHarness({
    configStatus: 503,
    configData: { ok: false, failure_code: 'bot_verification_config_error' },
  });
  const result = await harness.bridge.ask('안내');
  equal(result.ok, false, 'result ok');
  equal(askRequests(harness).length, 0, 'ask calls');
});

await check('challenge error fails closed before protected ask', async () => {
  const harness = createHarness({ challengeMode: 'error' });
  const result = await harness.bridge.ask('안내');
  equal(result.ok, false, 'result ok');
  equal(askRequests(harness).length, 0, 'ask calls');
});

await check('expired challenge fails closed before protected ask', async () => {
  const harness = createHarness({ challengeMode: 'expired' });
  const result = await harness.bridge.ask('안내');
  equal(result.ok, false, 'result ok');
  equal(askRequests(harness).length, 0, 'ask calls');
});

await check('cancel aborts a pending challenge and never calls protected ask', async () => {
  const harness = createHarness({ challengeMode: 'pending' });
  const promise = harness.bridge.ask('안내');
  await Promise.resolve();
  await Promise.resolve();
  harness.bridge.cancel();
  const result = await promise;
  equal(result.ok, false, 'result ok');
  equal(askRequests(harness).length, 0, 'ask calls');
});

await check('client loads only the canonical Cloudflare explicit-render script', async () => {
  const harness = createHarness({ turnstilePreloaded: false });
  const result = await harness.bridge.ask('안내');
  equal(result.ok, true, 'result ok');
  equal(harness.appendedScripts.length, 1, 'script count');
  equal(harness.appendedScripts[0], OFFICIAL_SCRIPT, 'script URL');
});

await check('disabled client config omits token and skips Cloudflare script', async () => {
  const harness = createHarness({
    turnstilePreloaded: false,
    configData: {
      ok: true,
      enabled: false,
      configured: true,
      mode: 'disabled',
      action: 'mvp_ask',
      site_key: '',
    },
  });
  const result = await harness.bridge.ask('로컬 안내');
  equal(result.ok, true, 'result ok');
  equal(harness.appendedScripts.length, 0, 'script count');
  const body = JSON.parse(askRequests(harness)[0].options.body);
  if ('turnstile_token' in body) throw new Error('disabled mode emitted token field');
});

await check('Turnstile client never uses localStorage', async () => {
  const harness = createHarness();
  await harness.bridge.ask('안내');
  equal(harness.localStorageTouches(), 0, 'localStorage touches');
});

if (failed) {
  throw new Error(`Turnstile client contracts failed: ${failed}/${passed + failed}\n${failures.join('\n')}`);
}

console.log(`\nTurnstile client contracts: ${passed}/${passed + failed} PASS`);