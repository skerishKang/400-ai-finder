import fs from 'node:fs';
import vm from 'node:vm';

const BRIDGE_PATH = new URL('../../src/web/static/citizen-mvp-bridge.js', import.meta.url);
const BRIDGE_SOURCE = fs.readFileSync(BRIDGE_PATH, 'utf8');
const SESSION_ID_RE = /^[A-Za-z0-9_-]{16,128}$/;

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

function createBridgeHarness({ storageThrows = false } = {}) {
  const requests = [];
  const stored = new Map();
  let uuidCounter = 0;
  let localStorageTouches = 0;

  const sessionStorage = {
    getItem(key) {
      if (storageThrows) throw new Error('session storage unavailable');
      return stored.has(key) ? stored.get(key) : null;
    },
    setItem(key, value) {
      if (storageThrows) throw new Error('session storage unavailable');
      stored.set(key, String(value));
    },
  };

  const window = {
    CitizenI18n: {
      getLocale: () => 'ko',
      normalizeLocale: (value) => value || 'ko',
      t: () => '현재 AI 안내를 연결하지 못했습니다.',
    },
    // This suite isolates anonymous-session identity. Turnstile lifecycle has
    // its own contract suite; an explicit disabled-mode client returns no token.
    CitizenTurnstile: {
      acquireToken: async () => '',
      reset: () => {},
      cancel: () => {},
    },
    AbortController,
    crypto: {
      randomUUID() {
        uuidCounter += 1;
        return uuidCounter === 1
          ? '123e4567-e89b-12d3-a456-426614174000'
          : '123e4567-e89b-12d3-a456-426614174001';
      },
    },
    sessionStorage,
  };

  Object.defineProperty(window, 'localStorage', {
    get() {
      localStorageTouches += 1;
      throw new Error('localStorage must not be used');
    },
  });

  async function fetch(url, options = {}) {
    requests.push({ url, options });
    return {
      ok: true,
      headers: { get: () => '' },
      json: async () => ({
        ok: true,
        answer: '북구청 안내입니다.',
        action: 'none',
        confidence: 0.9,
        request_id: '',
        schema_version: '1.0',
      }),
    };
  }

  const context = {
    window,
    fetch,
    AbortController,
    console,
    setTimeout,
    clearTimeout,
  };
  vm.runInNewContext(BRIDGE_SOURCE, context, { filename: 'citizen-mvp-bridge.js' });
  return {
    bridge: window.CitizenMvpBridge,
    requests,
    stored,
    localStorageTouches: () => localStorageTouches,
  };
}

console.log('\n=== Citizen MVP anonymous session contract ===\n');

await check('browser request includes a random closed-format session_id', async () => {
  const harness = createBridgeHarness();
  await harness.bridge.ask('여권 안내해줘');
  equal(harness.requests.length, 1, 'request count');
  const body = JSON.parse(harness.requests[0].options.body);
  if (!SESSION_ID_RE.test(body.session_id)) throw new Error(`invalid session_id ${body.session_id}`);
  equal(body.session_id, '123e4567-e89b-12d3-a456-426614174000', 'uuid');
  if (body.session_id.includes('여권')) throw new Error('session_id derived from question');
  if ('turnstile_token' in body) throw new Error('disabled Turnstile must not emit empty token field');
});

await check('session_id is reused within sessionStorage', async () => {
  const harness = createBridgeHarness();
  await harness.bridge.ask('첫 질문');
  await harness.bridge.ask('둘째 질문');
  const first = JSON.parse(harness.requests[0].options.body).session_id;
  const second = JSON.parse(harness.requests[1].options.body).session_id;
  equal(second, first, 'stable session ID');
  if (![...harness.stored.values()].includes(first)) throw new Error('session ID not persisted in sessionStorage');
});

await check('sessionStorage failure falls back to page-lifetime memory', async () => {
  const harness = createBridgeHarness({ storageThrows: true });
  await harness.bridge.ask('첫 질문');
  await harness.bridge.ask('둘째 질문');
  const first = JSON.parse(harness.requests[0].options.body).session_id;
  const second = JSON.parse(harness.requests[1].options.body).session_id;
  equal(second, first, 'memory fallback ID');
  if (!SESSION_ID_RE.test(first)) throw new Error(`invalid memory session_id ${first}`);
});

await check('bridge never touches localStorage for anonymous session identity', async () => {
  const harness = createBridgeHarness();
  await harness.bridge.ask('안내');
  equal(harness.localStorageTouches(), 0, 'localStorage touches');
});

if (failed) {
  throw new Error(`browser session contracts failed: ${failed}/${passed + failed}\n${failures.join('\n')}`);
}

console.log(`\nBrowser session contracts: ${passed}/${passed + failed} PASS`);