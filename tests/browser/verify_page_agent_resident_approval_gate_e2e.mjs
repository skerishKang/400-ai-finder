// tests/browser/verify_page_agent_resident_approval_gate_e2e.mjs
//
// #1198 follow-up: Page Agent resident entry must load approval registry/gate
// and ordinary home must select the approved designed renderer (fail-closed).
// Offline local only — no official-site/network/provider access.

import { chromium } from "playwright";
import assert from "node:assert";
import { createServer } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");
const LOCAL = new Set(["127.0.0.1", "localhost", "::1"]);
const APPROVED_ID = "bukgu_gwangju.home.designed.approved";
const FIXTURE_ID = "bukgu_gwangju.home.fixture.candidate";
const EXPECTED_FIXTURE_SHA =
  "81b27b98fadc091ca852079f89ea93da45b93f250372835b8b352726b2faeaed";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".json": "application/json",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

const KNOWN_BROWSER_PATHS = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
];

function buildDist() {
  const out = join(ROOT, "dist", "cloudflare-pages-1198-resident-gate");
  const r = spawnSync(
    "python",
    ["scripts/build_cloudflare_pages.py", "--out-dir", out],
    { cwd: ROOT, encoding: "utf-8", env: { ...process.env, PYTHONPATH: "." } }
  );
  if (r.status !== 0) {
    throw new Error((r.stdout || "") + (r.stderr || ""));
  }
  return out;
}

function startServer(rootDir) {
  const server = createServer((req, res) => {
    try {
      const url = new URL(req.url || "/", "http://127.0.0.1");
      let p = decodeURIComponent(url.pathname);
      if (p.endsWith("/")) p = p + "index.html";
      const fp = join(rootDir, p.replace(/^\/+/, ""));
      if (!fp.startsWith(rootDir) || !existsSync(fp) || !statSync(fp).isFile()) {
        res.writeHead(404);
        res.end("not found");
        return;
      }
      res.writeHead(200, {
        "Content-Type": MIME[extname(fp)] || "application/octet-stream",
      });
      res.end(readFileSync(fp));
    } catch (e) {
      res.writeHead(500);
      res.end(String(e));
    }
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      resolve({
        server,
        baseUrl: `http://127.0.0.1:${server.address().port}`,
      });
    });
  });
}

async function launchBrowser() {
  const attempts = [];
  const errors = [];
  if (process.env.PAGE_AGENT_BROWSER_EXECUTABLE) {
    attempts.push({
      name: "env",
      launch: () =>
        chromium.launch({
          headless: true,
          executablePath: process.env.PAGE_AGENT_BROWSER_EXECUTABLE,
        }),
    });
  }
  attempts.push({
    name: "channel:chrome",
    launch: () => chromium.launch({ headless: true, channel: "chrome" }),
  });
  for (const p of KNOWN_BROWSER_PATHS) {
    if (existsSync(p)) {
      attempts.push({
        name: p,
        launch: () => chromium.launch({ headless: true, executablePath: p }),
      });
    }
  }
  attempts.push({
    name: "default",
    launch: () => chromium.launch({ headless: true }),
  });
  for (const a of attempts) {
    try {
      const browser = await a.launch();
      console.log(`  Browser launched (${a.name})`);
      return browser;
    } catch (e) {
      errors.push(`${a.name}: ${e.message}`);
    }
  }
  throw new Error(`Cannot launch browser:\n${errors.join("\n")}`);
}

function attachSafety(page, baseUrl) {
  const c = {
    consoleErrors: 0,
    pageErrors: 0,
    external: 0,
    failed: 0,
    texts: [],
  };
  const origin = new URL(baseUrl).origin;
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      c.consoleErrors += 1;
      c.texts.push(msg.text());
    }
  });
  page.on("pageerror", (err) => {
    c.pageErrors += 1;
    c.texts.push(String(err));
  });
  page.on("requestfailed", () => {
    c.failed += 1;
  });
  page.route("**/*", async (route) => {
    const u = route.request().url();
    if (u.startsWith(origin) || u.startsWith("data:") || u.startsWith("blob:")) {
      return route.continue();
    }
    try {
      const h = new URL(u).hostname;
      if (!LOCAL.has(h) && u.startsWith("http")) c.external += 1;
    } catch (_) {}
    return route.abort();
  });
  return c;
}

async function openResident(page, baseUrl, query = "") {
  const path = `/examples/page-agent/resident/index.html${query}`;
  await page.goto(`${baseUrl}${path}`, {
    waitUntil: "domcontentloaded",
    timeout: 30000,
  });
  await page.waitForFunction(
    () =>
      window.CitizenActionDemoCanvas &&
      typeof window.CitizenActionDemoCanvas.navigateToRoute === "function",
    null,
    { timeout: 15000 }
  );
  await page.evaluate(() => {
    window.CitizenActionDemoCanvas.navigateToRoute("home");
  });
}

async function main() {
  console.log("=== #1198 Page Agent resident approval gate browser E2E ===");
  const dist = buildDist();
  console.log(`  build: ${dist}`);
  const { server, baseUrl } = await startServer(dist);
  console.log(`  server: ${baseUrl}`);
  const browser = await launchBrowser();
  const summary = {};

  try {
    // Ordinary home
    {
      console.log("  [ordinary] Page Agent resident home");
      const context = await browser.newContext({
        viewport: { width: 1440, height: 900 },
      });
      const page = await context.newPage();
      const counters = attachSafety(page, baseUrl);
      await openResident(page, baseUrl, "");
      await page.waitForSelector(
        `[data-renderer-id="${APPROVED_ID}"]`,
        { timeout: 10000 }
      );
      const ordinary = await page.evaluate((approvedId) => {
        const root = document.querySelector(".bg-page--home");
        return {
          hasRegistry: !!window.__CLONE_RENDERER_APPROVAL_REGISTRY__,
          hasGate: !!(
            window.CloneRendererApprovalGate &&
            typeof window.CloneRendererApprovalGate.resolveHomeSelection ===
              "function"
          ),
          rendererId: root && root.getAttribute("data-renderer-id"),
          residentDefault:
            root && root.getAttribute("data-resident-default-approved"),
          visualReview: root && root.getAttribute("data-visual-review-state"),
          unavailable: !!document.querySelector(
            ".bg-page--home-approval-unavailable"
          ),
          fixtureRoot: !!document.querySelector(".bg-home-fixture-root"),
          mayor: !!document.querySelector('img[src*="home-mayor-card"]'),
          chatInput: !!document.querySelector("#chat-input"),
          chatSend: !!document.querySelector("#chat-send"),
          demoCanvas: !!document.querySelector("#demo-canvas"),
          planStatus: !!document.querySelector("#page-agent-plan-status"),
          approvedId,
        };
      }, APPROVED_ID);
      assert.strictEqual(ordinary.hasRegistry, true, "registry missing");
      assert.strictEqual(ordinary.hasGate, true, "gate missing");
      assert.strictEqual(ordinary.rendererId, APPROVED_ID);
      assert.strictEqual(ordinary.residentDefault, "true");
      assert.strictEqual(ordinary.visualReview, "visual_review_approved");
      assert.strictEqual(ordinary.unavailable, false);
      assert.strictEqual(ordinary.fixtureRoot, false);
      assert.ok(ordinary.mayor, "mayor card missing");
      assert.ok(ordinary.chatInput, "Page Agent chat input missing");
      assert.ok(ordinary.chatSend, "Page Agent chat send missing");
      assert.ok(ordinary.demoCanvas, "demo canvas missing");
      assert.ok(ordinary.planStatus, "plan status missing");
      assert.strictEqual(counters.consoleErrors, 0, counters.texts.join(" | "));
      assert.strictEqual(counters.pageErrors, 0, counters.texts.join(" | "));
      assert.strictEqual(counters.external, 0);
      summary.ordinary = { ordinary, counters };
      await context.close();
      console.log("  [ordinary] PASS");
    }

    // Fixture preview
    {
      console.log("  [fixture-preview] Page Agent resident home-fixture=1");
      const context = await browser.newContext({
        viewport: { width: 1440, height: 900 },
      });
      const page = await context.newPage();
      const counters = attachSafety(page, baseUrl);
      await openResident(page, baseUrl, "?home-fixture=1");
      await page.waitForSelector(".bg-home-fixture-root", { timeout: 10000 });
      const preview = await page.evaluate(
        ({ fixtureId, expectedSha }) => {
          const root = document.querySelector(".bg-home-fixture-root");
          return {
            rendererId: root && root.getAttribute("data-renderer-id"),
            visualReview:
              root && root.getAttribute("data-visual-review-state"),
            residentDefault:
              root && root.getAttribute("data-resident-default-approved"),
            previewOnly: root && root.getAttribute("data-preview-only"),
            sha: root && root.getAttribute("data-home-fixture-sha256"),
            approvedMarker: !!document.querySelector(
              '[data-renderer-id="bukgu_gwangju.home.designed.approved"]'
            ),
            fixtureId,
            expectedShaOk:
              root &&
              root.getAttribute("data-home-fixture-sha256") === expectedSha,
          };
        },
        { fixtureId: FIXTURE_ID, expectedSha: EXPECTED_FIXTURE_SHA }
      );
      assert.strictEqual(preview.rendererId, FIXTURE_ID);
      assert.strictEqual(preview.visualReview, "visual_review_pending");
      assert.strictEqual(preview.residentDefault, "false");
      assert.strictEqual(preview.previewOnly, "true");
      assert.strictEqual(preview.approvedMarker, false);
      assert.ok(preview.expectedShaOk, "fixture sha mismatch");
      assert.strictEqual(counters.external, 0);
      summary.fixture_preview = { preview, counters };
      await context.close();
      console.log("  [fixture-preview] PASS");
    }

    console.log("PASS #1198 Page Agent resident approval gate browser E2E");
    console.log(JSON.stringify(summary, null, 2));
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch((err) => {
  console.error("FAIL", err);
  process.exit(1);
});
