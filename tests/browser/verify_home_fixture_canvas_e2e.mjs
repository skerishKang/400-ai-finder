// tests/browser/verify_home_fixture_canvas_e2e.mjs
//
// #1170 focused browser contract for canonical home fixture canvas renderer.
// Offline static MVP only — no official-site/network/provider access.

import { chromium } from "playwright";
import assert from "node:assert";
import { createServer } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");
const EXPECTED_FIXTURE_SHA =
  "81b27b98fadc091ca852079f89ea93da45b93f250372835b8b352726b2faeaed";
const REGION_ORDER = [
  "utility_navigation",
  "main_banner",
  "resident_service_shortcuts",
  "notice_news",
  "related_site_controls",
  "footer_identity_contact",
];
const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1"]);

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
      console.log(`  Browser launched (${a.name}) ✓`);
      return browser;
    } catch (e) {
      errors.push(`${a.name}: ${e.message}`);
    }
  }
  throw new Error(`Cannot launch browser:\n${errors.join("\n")}`);
}

function buildStaticDist() {
  const out = join(ROOT, "dist", "cloudflare-pages-1170-home");
  const result = spawnSync(
    "python",
    ["scripts/build_cloudflare_pages.py", "--out-dir", out],
    { cwd: ROOT, encoding: "utf-8" }
  );
  if (result.status !== 0) {
    throw new Error(`static build failed: ${result.stdout}\n${result.stderr}`);
  }
  return out;
}

function startStaticServer(rootDir) {
  const server = createServer((req, res) => {
    try {
      const url = new URL(req.url || "/", "http://127.0.0.1");
      let pathname = decodeURIComponent(url.pathname);
      if (pathname === "/" || pathname === "/mvp" || pathname === "/mvp/") {
        pathname = "/static/citizen-action-demo.html";
      }
      if (pathname.startsWith("/mvp/")) {
        pathname = pathname.slice(4);
      }
      const filePath = join(rootDir, pathname.replace(/^\/+/, ""));
      if (!filePath.startsWith(rootDir) || !existsSync(filePath) || !statSync(filePath).isFile()) {
        res.writeHead(404);
        res.end("not found");
        return;
      }
      const ext = extname(filePath).toLowerCase();
      res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
      res.end(readFileSync(filePath));
    } catch (e) {
      res.writeHead(500);
      res.end(String(e));
    }
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({ server, baseUrl: `http://127.0.0.1:${port}` });
    });
  });
}

async function probeHome(page, viewport) {
  const counters = {
    externalRequests: 0,
    externalNavigations: 0,
    consoleErrors: 0,
    pageErrors: 0,
    requestFailures: 0,
    formSubmissions: 0,
    loginAttempts: 0,
    paymentAttempts: 0,
    piiTransmissions: 0,
    consoleErrorTexts: [],
    pageErrorTexts: [],
    failedRequests: [],
  };

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      const loc = msg.location && msg.location();
      const locUrl = (loc && loc.url) || "";
      // Ignore benign browser chrome 404 noise (favicon etc.)
      if (/favicon\.ico/i.test(text) || /favicon\.ico/i.test(locUrl)) return;
      // Static harness serves only /static/**; root favicon/manifest probes are noise.
      if (/Failed to load resource/i.test(text) && /status of 404/i.test(text)) {
        counters.consoleErrorTexts.push(`soft404:${locUrl || text}`);
        return;
      }
      counters.consoleErrors += 1;
      counters.consoleErrorTexts.push(text + (locUrl ? ` @ ${locUrl}` : ""));
    }
  });
  page.on("pageerror", (err) => {
    counters.pageErrors += 1;
    counters.pageErrorTexts.push(String(err && err.message ? err.message : err));
  });
  page.on("requestfailed", (req) => {
    const u = req.url();
    if (/favicon\.ico/i.test(u)) return;
    counters.requestFailures += 1;
    counters.failedRequests.push(u + " " + (req.failure() && req.failure().errorText));
  });
  page.on("response", (res) => {
    const u = res.url();
    if (/favicon\.ico/i.test(u)) return;
    if (res.status() >= 400) {
      counters.requestFailures += 1;
      counters.failedRequests.push(u + " status=" + res.status());
    }
  });
  page.on("request", (req) => {
    const u = req.url();
    try {
      const parsed = new URL(u);
      if (!LOCAL_HOSTS.has(parsed.hostname) && parsed.protocol.startsWith("http")) {
        counters.externalRequests += 1;
      }
    } catch (_) {}
    if (req.method() === "POST") counters.formSubmissions += 1;
    if (/login|signin|password/i.test(u)) counters.loginAttempts += 1;
    if (/pay|checkout|billing/i.test(u)) counters.paymentAttempts += 1;
    if (/resident|ssn|jumin|phone|email/i.test(u) && req.method() !== "GET") {
      counters.piiTransmissions += 1;
    }
  });
  page.on("framenavigated", (frame) => {
    if (frame !== page.mainFrame()) return;
    try {
      const parsed = new URL(frame.url());
      if (!LOCAL_HOSTS.has(parsed.hostname)) counters.externalNavigations += 1;
    } catch (_) {}
  });

  await page.setViewportSize(viewport);
  await page.goto(`${page._homeBase}/static/citizen-action-demo.html`, {
    waitUntil: "domcontentloaded",
    timeout: 30000,
  });

  // Ensure home route is active
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
  await page.waitForSelector('[data-home-fixture-sha256]', { timeout: 10000 });

  const result = await page.evaluate(
    ({ expectedSha, regionOrder }) => {
      const root =
        document.querySelector("[data-home-fixture-sha256]") ||
        document.querySelector(".bg-page--home");
      const regions = [...document.querySelectorAll("[data-home-region-id]")].map((el) =>
        el.getAttribute("data-home-region-id")
      );
      const util = document.querySelector('[data-home-region-id="utility_navigation"]');
      const hiddenLang = util
        ? [...util.querySelectorAll('[data-home-effective-variant="hidden"]')].filter((el) => {
            const t = (el.textContent || "").replace(/\s+/g, " ").trim();
            return t === "ENG" || t === "CHN" || t === "JPN";
          })
        : [];
      const hiddenVisible = hiddenLang.filter((el) => {
        const cs = getComputedStyle(el);
        if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0) {
          return false;
        }
        // offsetParent null also means not shown for non-fixed elements
        return el.offsetParent !== null || cs.position === "fixed";
      });
      const overflowX = document.documentElement.scrollWidth > document.documentElement.clientWidth + 1;
      const bodyOverflow =
        document.querySelector(".bg-page--home") &&
        document.querySelector(".bg-page--home").scrollWidth >
          document.querySelector(".bg-page--home").clientWidth + 2;
      const crossOriginActions = [
        ...document.querySelectorAll('[data-same-origin="false"][data-action-target]'),
      ].length;
      const remoteImgs = [...document.querySelectorAll("img[src]")].filter((img) =>
        /^https?:/i.test(img.getAttribute("src") || "")
      ).length;
      const targets = [
        "nav-civil-service",
        "nav-complaint-board",
        "nav-apartment-dept",
        "nav-passport-guidance",
        "nav-bulky-waste-disposal",
        "mayor-office-open",
      ].map((t) => ({
        t,
        present: !!document.querySelector(`[data-action-target="${t}"]`),
      }));
      return {
        sha: root ? root.getAttribute("data-home-fixture-sha256") : null,
        cloneStatus: root ? root.getAttribute("data-home-clone-status") : null,
        exact: root ? root.getAttribute("data-home-exact-clone") : null,
        regions,
        regionOrderMatch: JSON.stringify(regions) === JSON.stringify(regionOrder),
        hiddenLangCount: hiddenLang.length,
        hiddenVisibleCount: hiddenVisible.length,
        overflowX: overflowX || bodyOverflow,
        crossOriginActions,
        remoteImgs,
        targets,
        expectedShaOk: root && root.getAttribute("data-home-fixture-sha256") === expectedSha,
      };
    },
    { expectedSha: EXPECTED_FIXTURE_SHA, regionOrder: REGION_ORDER }
  );

  return { result, counters };
}

async function main() {
  console.log("=== #1170 home fixture canvas browser E2E ===");
  const dist = buildStaticDist();
  console.log(`  static build: ${dist}`);
  const { server, baseUrl } = await startStaticServer(dist);
  console.log(`  server: ${baseUrl}`);
  const browser = await launchBrowser();
  const summary = { desktop: null, mobile: null };

  try {
    for (const [name, viewport] of [
      ["desktop", { width: 1440, height: 1000 }],
      ["mobile", { width: 390, height: 844 }],
    ]) {
      const page = await browser.newPage();
      page._homeBase = baseUrl;
      const { result, counters } = await probeHome(page, viewport);
      summary[name] = { result, counters };
      console.log(`  [${name}] sha=${result.sha} regions=${result.regions.length} overflow=${result.overflowX}`);
      assert.ok(result.expectedShaOk, `${name}: fixture sha mismatch`);
      assert.strictEqual(result.cloneStatus, "capture_required");
      assert.strictEqual(result.exact, "false");
      assert.ok(result.regionOrderMatch, `${name}: region order mismatch ${result.regions}`);
      assert.strictEqual(result.hiddenLangCount, 3, `${name}: expected 3 hidden language items`);
      assert.strictEqual(result.hiddenVisibleCount, 0, `${name}: language items must not be visible`);
      if (name === "mobile") {
        assert.strictEqual(result.overflowX, false, "mobile horizontal overflow");
      }
      assert.strictEqual(result.crossOriginActions, 0);
      assert.strictEqual(result.remoteImgs, 0);
      for (const t of result.targets) {
        assert.ok(t.present, `${name}: missing target ${t.t}`);
      }
      assert.strictEqual(counters.externalRequests, 0, `${name}: external requests`);
      assert.strictEqual(counters.externalNavigations, 0, `${name}: external navigations`);
      assert.strictEqual(
        counters.consoleErrors,
        0,
        `${name}: console errors ${JSON.stringify(counters.consoleErrorTexts)} failed=${JSON.stringify(counters.failedRequests)}`
      );
      assert.strictEqual(
        counters.pageErrors,
        0,
        `${name}: page errors ${JSON.stringify(counters.pageErrorTexts)}`
      );
      assert.strictEqual(counters.formSubmissions, 0);
      assert.strictEqual(counters.loginAttempts, 0);
      assert.strictEqual(counters.paymentAttempts, 0);
      assert.strictEqual(counters.piiTransmissions, 0);
      await page.close();
    }
    console.log("PASS #1170 home fixture canvas browser E2E");
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
