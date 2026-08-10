import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  TURNSTILE_MAX_TOKEN_CHARS,
  TURNSTILE_SITEVERIFY_URL,
  buildTurnstileClientConfig,
  resolveTurnstileMode,
  validateTurnstileToken,
  verifyTurnstileRequest,
} from '../../functions/api/mvp/turnstile.js';
import * as configEndpoint from '../../functions/api/mvp/turnstile-config.js';

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

function responseJson(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  };
}

function baseEnv(overrides = {}) {
  return {
    MVP_TURNSTILE_MODE: 'required',
    MVP_TURNSTILE_SECRET_KEY: 'test-secret-do-not-log',
    MVP_TURNSTILE_SITE_KEY: 'test-public-site-key',
    MVP_TURNSTILE_EXPECTED_ACTION: 'mvp_ask',
    MVP_TURNSTILE_ALLOWED_HOSTNAMES: 'cgbukku.pages.dev',
    MVP_TURNSTILE_TIMEOUT_MS: '1000',
    ...overrides,
  };
}

async function verify({ env = baseEnv(), token = 'valid-test-token-123456', data, fetchError, hostname = 'cgbukku.pages.dev' } = {}) {
  let calls = 0;
  let captured = null;
  const result = await verifyTurnstileRequest({
    env,
    requestHostname: hostname,
    token,
    remainingRequestBudgetMs: 5000,
    fetchWithDeadline: async (url, init, timeoutMs) => {
      calls += 1;
      captured = { url, init, timeoutMs };
      if (fetchError) throw fetchError;
      return responseJson(data || {
        success: true,
        action: 'mvp_ask',
        hostname: 'cgbukku.pages.dev',
      });
    },
  });
  return { result, calls, captured };
}

console.log('\n=== Cloudflare MVP Turnstile contract ===\n');

await check('Turnstile token max length matches Cloudflare contract', async () => {
  equal(TURNSTILE_MAX_TOKEN_CHARS, 2048, 'max token chars');
  equal(validateTurnstileToken('x'.repeat(2048)).ok, true, '2048 accepted');
  equal(validateTurnstileToken('x'.repeat(2049)).ok, false, '2049 rejected');
});

await check('missing and malformed tokens fail before Siteverify', async () => {
  for (const token of ['', 'bad token with spaces', 'x'.repeat(2049)]) {
    const { result, calls } = await verify({ token });
    equal(result.ok, false, `ok ${token.length}`);
    equal(result.failureCode, 'bot_verification_required', `failure ${token.length}`);
    equal(result.status, 403, `status ${token.length}`);
    equal(calls, 0, `siteverify calls ${token.length}`);
  }
});

await check('Siteverify success is accepted and secret stays only in outbound body', async () => {
  const { result, calls, captured } = await verify();
  equal(result.ok, true, 'ok');
  equal(result.verified, true, 'verified');
  equal(calls, 1, 'siteverify calls');
  equal(captured.url, TURNSTILE_SITEVERIFY_URL, 'endpoint');
  const outbound = JSON.parse(captured.init.body);
  equal(outbound.secret, 'test-secret-do-not-log', 'secret outbound');
  equal(outbound.response, 'valid-test-token-123456', 'token outbound');
  if ('question' in outbound || 'session_id' in outbound || 'remoteip' in outbound) {
    throw new Error('Siteverify body leaked unrelated resident/network data');
  }
  if (JSON.stringify(result).includes('test-secret-do-not-log') || JSON.stringify(result).includes('valid-test-token-123456')) {
    throw new Error('result leaked secret/token');
  }
});

await check('expired or duplicate token fails closed', async () => {
  const { result } = await verify({
    data: { success: false, 'error-codes': ['timeout-or-duplicate'] },
  });
  equal(result.ok, false, 'ok');
  equal(result.failureCode, 'bot_verification_failed', 'failure');
  equal(result.reason, 'expired_or_duplicate', 'reason');
  equal(result.status, 403, 'status');
});

await check('generic Siteverify rejection fails closed', async () => {
  const { result } = await verify({
    data: { success: false, 'error-codes': ['invalid-input-response'] },
  });
  equal(result.failureCode, 'bot_verification_failed', 'failure');
  equal(result.reason, 'siteverify_rejected', 'reason');
});

await check('action mismatch fails closed', async () => {
  const { result } = await verify({
    data: { success: true, action: 'other_action', hostname: 'cgbukku.pages.dev' },
  });
  equal(result.failureCode, 'bot_verification_failed', 'failure');
  equal(result.reason, 'action_mismatch', 'reason');
});

await check('configured hostname mismatch fails closed', async () => {
  const { result } = await verify({
    data: { success: true, action: 'mvp_ask', hostname: 'attacker.example' },
  });
  equal(result.failureCode, 'bot_verification_failed', 'failure');
  equal(result.reason, 'hostname_mismatch', 'reason');
});

await check('Siteverify timeout and network errors are unavailable', async () => {
  const timeout = new Error('UPSTREAM_TIMEOUT');
  timeout.code = 'upstream_timeout';
  for (const error of [timeout, new Error('network down')]) {
    const { result } = await verify({ fetchError: error });
    equal(result.failureCode, 'bot_verification_unavailable', 'failure');
    equal(result.status, 503, 'status');
  }
});

await check('missing secret is config error before Siteverify', async () => {
  const { result, calls } = await verify({ env: baseEnv({ MVP_TURNSTILE_SECRET_KEY: '' }) });
  equal(result.failureCode, 'bot_verification_config_error', 'failure');
  equal(result.status, 503, 'status');
  equal(calls, 0, 'calls');
});

await check('production disabled bypass is rejected while loopback bypass is explicit', async () => {
  const prod = resolveTurnstileMode({ MVP_TURNSTILE_MODE: 'disabled' }, 'cgbukku.pages.dev');
  equal(prod.mode, 'required', 'production mode');
  equal(prod.reason, 'insecure_bypass_rejected', 'production reason');

  const local = resolveTurnstileMode({ MVP_TURNSTILE_MODE: 'disabled' }, 'localhost');
  equal(local.mode, 'disabled', 'local mode');
  equal(local.reason, 'explicit_loopback_bypass', 'local reason');

  const localVerify = await verify({
    env: baseEnv({ MVP_TURNSTILE_MODE: 'disabled', MVP_TURNSTILE_SECRET_KEY: '' }),
    hostname: 'localhost',
  });
  equal(localVerify.result.ok, true, 'local bypass ok');
  equal(localVerify.result.bypassed, true, 'local bypassed');
  equal(localVerify.calls, 0, 'local Siteverify calls');
});

await check('missing or invalid mode fails closed to required', async () => {
  equal(resolveTurnstileMode({}, 'localhost').mode, 'required', 'missing mode');
  equal(resolveTurnstileMode({ MVP_TURNSTILE_MODE: 'maybe' }, 'localhost').mode, 'required', 'invalid mode');
});

await check('client config exposes site key and never secret', async () => {
  const config = buildTurnstileClientConfig(baseEnv(), 'cgbukku.pages.dev');
  equal(config.ok, true, 'config ok');
  equal(config.enabled, true, 'enabled');
  equal(config.site_key, 'test-public-site-key', 'site key');
  const serialized = JSON.stringify(config);
  if (serialized.includes('test-secret-do-not-log')) throw new Error('client config leaked secret');
});

await check('config endpoint fails closed when required site key is missing', async () => {
  const request = new Request('https://cgbukku.pages.dev/api/mvp/turnstile-config', { method: 'GET' });
  const response = await configEndpoint.onRequest({
    request,
    env: baseEnv({ MVP_TURNSTILE_SITE_KEY: '' }),
  });
  equal(response.status, 503, 'status');
  const data = await response.json();
  equal(data.failure_code, 'bot_verification_config_error', 'failure');
  if (JSON.stringify(data).includes('test-secret-do-not-log')) throw new Error('endpoint leaked secret');
});

await check('live Pages build publishes Turnstile assets without inventing CSP headers', async () => {
  const repoRoot = fileURLToPath(new URL('../../', import.meta.url));
  const outDir = mkdtempSync(join(tmpdir(), 'mvp-turnstile-build-'));
  try {
    const build = spawnSync(
      'python',
      ['scripts/build_cloudflare_pages.py', '--mode', 'live', '--out-dir', outDir],
      { cwd: repoRoot, encoding: 'utf-8' },
    );
    if (build.status !== 0) {
      throw new Error(`live build failed: ${build.stdout}\n${build.stderr}`);
    }

    for (const filename of ['citizen-mvp-bridge.js', 'citizen-turnstile.js']) {
      const source = join(repoRoot, 'src', 'web', 'static', filename);
      const built = join(outDir, 'static', filename);
      if (!existsSync(source) || !existsSync(built)) {
        throw new Error(`missing live build asset: ${filename}`);
      }
      if (!readFileSync(source).equals(readFileSync(built))) {
        throw new Error(`live build changed static asset bytes: ${filename}`);
      }
    }

    const bridge = readFileSync(join(outDir, 'static', 'citizen-mvp-bridge.js'), 'utf-8');
    if (!bridge.includes('var TURNSTILE_CLIENT_SRC = "/static/citizen-turnstile.js";')) {
      throw new Error('built bridge does not point to citizen-turnstile.js');
    }
    const shell = readFileSync(join(outDir, 'static', 'citizen-first-use-shell.js'), 'utf-8');
    if (!shell.includes('citizen-mvp-bridge.js')) {
      throw new Error('built shell does not load citizen-mvp-bridge.js');
    }
    const mvpHtml = readFileSync(join(outDir, 'mvp', 'index.html'), 'utf-8');
    if (!mvpHtml.includes('searchParams.set("mvp", "1")')) {
      throw new Error('live /mvp/ entry does not activate the MVP bridge');
    }
    if (existsSync(join(outDir, '_headers'))) {
      throw new Error('live build invented an unreviewed Cloudflare _headers policy');
    }
  } finally {
    rmSync(outDir, { recursive: true, force: true });
  }
});

if (failed) {
  throw new Error(`Turnstile contracts failed: ${failed}/${passed + failed}\n${failures.join('\n')}`);
}

console.log(`\nTurnstile contracts: ${passed}/${passed + failed} PASS`);
