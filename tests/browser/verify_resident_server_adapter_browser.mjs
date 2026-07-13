// tests/browser/verify_resident_server_adapter_browser.mjs
//
// Focused browser verification for the Stage 4 Page Agent resident demo.
//   - default MOCK path (no query param) must initialise and respond locally
//   - SERVER path (?page_agent_adapter=server) with a disabled adapter must
//     handle the safe `done(success:false)` gracefully, and the browser-side
//     serverCustomFetch must never send an `Authorization` header upstream.
//
// Uses the locally-installed Playwright Chromium (no download).
// Screenshots are captured at 390x844 (mobile) and 1440x900 (desktop).

import { chromium } from 'playwright';
import http from 'node:http';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { join, extname, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, '..', '..');
const RESIDENT_URL = '/src/web/examples/page-agent/resident/index.html';
const ADAPTER_PATH = '/api/page-agent/v1/chat/completions';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.ico': 'image/x-icon',
};

// Observed adapter request metadata (set by the static server's adapter handler).
const adapterSeen = { count: 0, hadAuth: false, origin: '', path: '', method: '' };

let server;
let serverPort;

function startServer() {
  return new Promise((resolve) => {
    server = http.createServer((req, res) => {
      try {
        let urlPath = decodeURIComponent(req.url.split('?')[0]);
        if (urlPath.endsWith('/')) urlPath += 'index.html';

        // Simulated disabled server adapter endpoint.
        if (req.method === 'POST' && urlPath === ADAPTER_PATH) {
          const chunks = [];
          req.on('data', (c) => chunks.push(c));
          req.on('end', () => {
            adapterSeen.count += 1;
            adapterSeen.method = req.method;
            adapterSeen.path = urlPath;
            adapterSeen.origin = req.headers['origin'] || '';
            adapterSeen.hadAuth = Object.keys(req.headers).some(
              (k) => k.toLowerCase() === 'authorization'
            );
            const body = JSON.stringify({
              id: 'chatcmpl-page-agent-test',
              object: 'chat.completion',
              created: 1,
              model: 'page-agent-server-adapter',
              choices: [
                {
                  index: 0,
                  message: {
                    role: 'assistant',
                    content: null,
                    tool_calls: [
                      {
                        id: 'call_test',
                        type: 'function',
                        function: {
                          name: 'AgentOutput',
                          arguments: JSON.stringify({
                            action: { done: { text: '서버 모델이 비활성 상태입니다.', success: false } },
                          }),
                        },
                      },
                    ],
                  },
                  finish_reason: 'tool_calls',
                },
              ],
              usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
            });
            res.writeHead(200, {
              'Content-Type': 'application/json; charset=utf-8',
              'Access-Control-Allow-Origin': req.headers['origin'] || '*',
            });
            res.end(body);
          });
          return;
        }

        const filePath = normalize(join(REPO_ROOT, urlPath));
        if (!filePath.startsWith(REPO_ROOT)) {
          res.writeHead(403);
          res.end('forbidden');
          return;
        }
        if (!existsSync(filePath) || !statSync(filePath).isFile()) {
          res.writeHead(404);
          res.end('not found: ' + urlPath);
          return;
        }
        const fileBody = readFileSync(filePath);
        res.writeHead(200, {
          'Content-Type': MIME[extname(filePath)] || 'application/octet-stream',
          'Access-Control-Allow-Origin': '*',
        });
        res.end(fileBody);
      } catch (e) {
        res.writeHead(500);
        res.end('error: ' + e.message);
      }
    });
    server.listen(0, '127.0.0.1', () => {
      serverPort = server.address().port;
      resolve(serverPort);
    });
  });
}

function base() {
  return `http://127.0.0.1:${serverPort}`;
}

let failures = 0;
const jsErrors = [];

function assert(cond, msg) {
  if (cond) {
    console.log('  PASS ' + msg);
  } else {
    failures += 1;
    console.log('  FAIL ' + msg);
  }
}

async function main() {
  await startServer();
  const browser = await chromium.launch();
  try {
    // ── 1. DEFAULT MOCK PATH ────────────────────────────────────────────────
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      page.on('pageerror', (e) => jsErrors.push('mock: ' + e.message));

      await page.goto(base() + RESIDENT_URL, { waitUntil: 'load' });
      await page.waitForSelector('#chat-suggestions .chat-suggestion', { timeout: 10000 });
      const suggCount = await page.locator('#chat-suggestions .chat-suggestion').count();
      assert(suggCount >= 1, `mock: suggestion buttons rendered (${suggCount})`);

      const badge = await page.locator('#badge-mode').textContent();
      assert(/mock|오프라인/i.test(badge), `mock: offline/mock badge present ("${badge}")`);

      await page.locator('#chat-suggestions .chat-suggestion').first().click();
      let responded = false;
      try {
        await page.waitForFunction(
          () => {
            const msgs = document.querySelectorAll('#chat-messages .chat-msg--agent');
            return msgs.length >= 2 || document.querySelector('.chat-msg--action');
          },
          { timeout: 20000 }
        );
        responded = true;
      } catch (_) {
        responded = false;
      }
      assert(responded, 'mock: local mock produced an agent response / action');
      assert(adapterSeen.count === 0, 'mock: no upstream adapter request in mock mode');

      await page.screenshot({ path: join(REPO_ROOT, 'tests', 'browser', 'shot_mock_desktop.png') });
      await page.setViewportSize({ width: 390, height: 844 });
      await page.screenshot({ path: join(REPO_ROOT, 'tests', 'browser', 'shot_mock_mobile.png') });
      await ctx.close();
    }

    // ── 2. SERVER PATH (disabled adapter) + Authorization stripping ──────────
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      page.on('pageerror', (e) => jsErrors.push('server: ' + e.message));

      await page.goto(base() + RESIDENT_URL + '?page_agent_adapter=server', { waitUntil: 'load' });
      await page.waitForSelector('#chat-suggestions .chat-suggestion', { timeout: 10000 });
      // Click the first suggestion; retry until the adapter request is actually
      // issued (the demo's agent may need a moment after init).
      let requestSeen = false;
      for (let attempt = 1; attempt <= 3 && !requestSeen; attempt++) {
        await page.locator('#chat-suggestions .chat-suggestion').first().click();
        try {
          await page.waitForRequest((r) => r.url().includes('api/page-agent'), { timeout: 12000 });
          requestSeen = true;
        } catch (_) {
          requestSeen = false;
        }
      }

      let disabledHandled = false;
      try {
        await page.waitForFunction(
          () => {
            const badge = document.getElementById('badge-mode');
            if (badge && /비활성/.test(badge.textContent)) return true;
            const msgs = document.querySelectorAll('#chat-messages .chat-msg--agent');
            return msgs.length >= 2;
          },
          { timeout: 15000 }
        );
        disabledHandled = true;
      } catch (_) {
        disabledHandled = false;
      }

      assert(requestSeen, 'server: adapter request issued via serverCustomFetch');
      assert(adapterSeen.count >= 1, 'server: adapter request reached the disabled adapter');
      assert(
        adapterSeen.path === ADAPTER_PATH,
        `server: adapter request hits ${ADAPTER_PATH} (got "${adapterSeen.path}")`
      );
      assert(!!adapterSeen.origin, `server: adapter request carries Origin ("${adapterSeen.origin}")`);
      assert(!adapterSeen.hadAuth, 'server: serverCustomFetch stripped Authorization (no auth header sent)');
      assert(disabledHandled, 'server: disabled-adapter safe done handled gracefully');

      await page.screenshot({ path: join(REPO_ROOT, 'tests', 'browser', 'shot_server_disabled_desktop.png') });
      await page.setViewportSize({ width: 390, height: 844 });
      await page.screenshot({ path: join(REPO_ROOT, 'tests', 'browser', 'shot_server_disabled_mobile.png') });
      await ctx.close();
    }

    // ── 3. No uncaught JS errors ─────────────────────────────────────────────
    assert(jsErrors.length === 0, 'no uncaught page JS errors (' + jsErrors.length + ')');
    for (const e of jsErrors.slice(0, 10)) console.log('     ! ' + e);
  } finally {
    await browser.close();
    server.close();
  }

  console.log('\n[resident server-adapter browser verification] failures=' + failures);
  if (failures > 0) process.exit(1);
  console.log('All resident server-adapter browser checks passed.');
}

main().catch((err) => {
  console.error('Browser verification FAILED:');
  console.error(err && err.stack ? err.stack : err);
  if (server) server.close();
  process.exit(1);
});
