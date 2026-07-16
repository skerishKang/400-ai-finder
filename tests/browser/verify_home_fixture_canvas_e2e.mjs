// tests/browser/verify_home_fixture_canvas_e2e.mjs
//
// #1170 / #1192 home fixture canvas browser contract.
// Offline static MVP only — no official-site/network/provider access.
//
// States:
//  1) 1440×900 full-width entry home
//  2) 1440×900 desktop split after first question
//  3) 1440×760 desktop split after first question
//  4) 390×844 mobile guidance after first question

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
const DESKTOP_MIN_CARD = 160;
const MOBILE_MIN_CARD = 140;
const TEXT_MIN_W = 40;

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

function attachSafety(page, baseUrl) {
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
    remoteVisualRequests: 0,
  };
  const origin = new URL(baseUrl).origin;

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      const loc = msg.location && msg.location();
      const locUrl = (loc && loc.url) || "";
      if (/favicon\.ico/i.test(text) || /favicon\.ico/i.test(locUrl)) return;
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
    if (/\/upload\/visual\//i.test(u) || /bukgu\.gwangju\.kr\/upload\/visual/i.test(u)) {
      counters.remoteVisualRequests += 1;
    }
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

  // Abort non-local HTTP(S) — safety owner for external requests.
  page.route("**/*", async (route) => {
    const u = route.request().url();
    if (
      u.startsWith(origin) ||
      u.startsWith("data:") ||
      u.startsWith("blob:") ||
      /^https?:\/\/(127\.0\.0\.1|localhost|\[::1\])(?::\d+)?\//i.test(u)
    ) {
      return route.continue();
    }
    counters.externalRequests += 1;
    return route.abort();
  });

  return counters;
}

async function openHome(page, baseUrl) {
  // #1197: fixture visual-card rail is opt-in only (?home-fixture=1).
  await page.goto(`${baseUrl}/static/citizen-action-demo.html?home-fixture=1`, {
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
  await page.waitForSelector("[data-home-fixture-sha256]", { timeout: 10000 });
}

async function enterSplitViaFirstQuestion(page) {
  await page.waitForSelector("#chat-composer-input", { timeout: 10000 });
  await page.fill("#chat-composer-input", "불법 주정차 신고는 어디서 하나요?");
  await page.click("#chat-composer-send");
  // Fail-closed: real first-question flow must reach split (no swallowed timeout).
  await page.waitForFunction(
    () => {
      const s = document.body.getAttribute("data-first-use-state");
      return s === "split" || s === "transitioning";
    },
    null,
    { timeout: 15000 }
  );
  await page.waitForFunction(
    () => document.body.getAttribute("data-first-use-state") === "split",
    null,
    { timeout: 15000 }
  );
  const state = await page.evaluate(() =>
    document.body.getAttribute("data-first-use-state")
  );
  assert.strictEqual(state, "split", `enterSplitViaFirstQuestion: expected split, got ${state}`);
  await page.waitForTimeout(600);
  await page.evaluate(() => {
    if (
      window.CitizenActionDemoCanvas &&
      typeof window.CitizenActionDemoCanvas.navigateToRoute === "function"
    ) {
      // Prefer home for banner geometry; illegal-parking guidance is OK too if
      // fixture home is still in DOM under the canvas shell.
      const route =
        typeof window.CitizenActionDemoCanvas.getCurrentRouteId === "function"
          ? window.CitizenActionDemoCanvas.getCurrentRouteId()
          : null;
      if (route !== "home") {
        window.CitizenActionDemoCanvas.navigateToRoute("home");
      }
    }
  });
  // Do not require main_banner *visible* here — mobile conversation surface
  // may hide the canvas until the guidance tab is selected.
  await page.waitForSelector('[data-home-region-id="main_banner"]', {
    state: "attached",
    timeout: 10000,
  });
}

async function measureMainBanner(page, expectedSha, regionOrder) {
  return page.evaluate(
    ({ expectedSha, regionOrder }) => {
      const root =
        document.querySelector("[data-home-fixture-sha256]") ||
        document.querySelector(".bg-page--home");
      const regions = [...document.querySelectorAll("[data-home-region-id]")].map((el) =>
        el.getAttribute("data-home-region-id")
      );
      const region = document.querySelector('[data-home-region-id="main_banner"]');
      const itemsBox = region
        ? region.querySelector(".bg-home-fixture-items")
        : null;
      const allItems = region
        ? [...region.querySelectorAll("[data-home-item-id]")]
        : [];
      const metadataOnly = allItems.filter(
        (el) => el.getAttribute("data-home-presentation") === "metadata-only"
      );
      const visualCards = allItems.filter(
        (el) => el.getAttribute("data-home-presentation") === "visual-card"
      );
      const controls = allItems.filter(
        (el) => el.getAttribute("data-home-presentation") === "control"
      );
      const orders = allItems.map((el) =>
        Number(el.getAttribute("data-home-item-order") || "0")
      );
      let orderNonDecreasing = true;
      for (let i = 1; i < orders.length; i++) {
        if (orders[i] < orders[i - 1]) orderNonDecreasing = false;
      }
      const metaFocusable = metadataOnly.filter((el) => {
        if (el.matches("a[href],button,input,select,textarea,[tabindex]")) {
          const ti = el.getAttribute("tabindex");
          if (ti === "-1") return false;
          const cs = getComputedStyle(el);
          return cs.display !== "none" && cs.visibility !== "hidden";
        }
        return false;
      }).length;

      const visibleVisual = visualCards.filter((el) => {
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        return (
          cs.display !== "none" &&
          cs.visibility !== "hidden" &&
          r.width > 0 &&
          r.height > 0
        );
      });
      // Layout (offset*) vs visual (getBoundingClientRect) — pass criteria use visual only.
      const layoutCardW = visibleVisual
        .map((el) => el.offsetWidth)
        .filter((w) => w > 0)
        .sort((a, b) => a - b);
      const visualCardW = visibleVisual
        .map((el) => el.getBoundingClientRect().width)
        .filter((w) => w > 0)
        .sort((a, b) => a - b);
      const texts = visibleVisual
        .map((el) => el.querySelector(".bg-home-fixture-item__text"))
        .filter(Boolean)
        .filter((t) => (t.textContent || "").replace(/\s+/g, "").length > 0);
      const layoutTextW = texts
        .map((el) => el.offsetWidth)
        .filter((w) => w > 0)
        .sort((a, b) => a - b);
      const visualTextW = texts
        .map((el) => el.getBoundingClientRect().width)
        .filter((w) => w > 0)
        .sort((a, b) => a - b);
      const visualFallbackW = visibleVisual
        .map((el) => {
          const fb = el.querySelector(
            '.bg-home-fixture-asset[data-asset-state="unresolved"]'
          );
          return fb ? fb.getBoundingClientRect().width : null;
        })
        .filter((w) => w != null && w > 0)
        .sort((a, b) => a - b);
      const median = (arr) =>
        arr.length ? arr[Math.floor(arr.length / 2)] : null;
      // Visual geometry only for wrap suspects (after canvas transform).
      let verticalCharWrapSuspect = 0;
      for (const t of texts) {
        const r = t.getBoundingClientRect();
        const w = r.width;
        const h = r.height;
        if (w > 0 && w < 40 && h > 40) verticalCharWrapSuspect += 1;
      }
      const sampleCard = visibleVisual[0] || null;
      const sampleLayoutW = sampleCard ? sampleCard.offsetWidth : null;
      const sampleVisualW = sampleCard
        ? sampleCard.getBoundingClientRect().width
        : null;
      const visualTransformRatio =
        sampleLayoutW && sampleLayoutW > 0 && sampleVisualW != null
          ? sampleVisualW / sampleLayoutW
          : null;
      const canvasInner = document.querySelector(".demo-canvas__inner");
      const canvasTransform = canvasInner
        ? getComputedStyle(canvasInner).transform
        : null;
      const rootEl = document.querySelector(".bg-home-fixture-root");
      const rootR = rootEl ? rootEl.getBoundingClientRect() : null;
      const regionR = region ? region.getBoundingClientRect() : null;
      let cardsOutsideRoot = 0;
      let fallbackOutsideCard = 0;
      for (const el of visibleVisual) {
        const r = el.getBoundingClientRect();
        // Horizontal rail intentionally places cards past the visible root edge
        // (scrollWidth > clientWidth). That is allowed and must not fail.
        // Fail only if a card is completely to the left of the root, or escapes
        // the banner region vertically.
        if (rootR && r.right < rootR.left - 2) {
          cardsOutsideRoot += 1;
        }
        if (regionR && (r.bottom > regionR.bottom + 12 || r.top < regionR.top - 12)) {
          cardsOutsideRoot += 1;
        }
        const fb = el.querySelector(
          '.bg-home-fixture-asset[data-asset-state="unresolved"]'
        );
        if (fb) {
          const fr = fb.getBoundingClientRect();
          // Media panel must stay within the card box (allow 2px subpixel).
          if (fr.right > r.right + 2 || fr.bottom > r.bottom + 2 || fr.left < r.left - 2) {
            fallbackOutsideCard += 1;
          }
        }
      }
      const unresolvedFallbacks = region
        ? region.querySelectorAll(
            '.bg-home-fixture-asset[data-asset-state="unresolved"]'
          ).length
        : 0;
      const remoteOfficialImgs = region
        ? [...region.querySelectorAll("img[src]")].filter((img) => {
            const s = img.getAttribute("src") || "";
            return (
              /^https?:\/\/bukgu\.gwangju\.kr/i.test(s) ||
              /\/upload\/visual\//i.test(s)
            );
          }).length
        : 0;
      const brokenImgs = region
        ? [...region.querySelectorAll("img")].filter(
            (img) => img.complete && img.naturalWidth === 0
          ).length
        : 0;
      const dashedLegacy = region
        ? [...region.querySelectorAll(".bg-home-fixture-asset")].filter((el) => {
            if (el.getAttribute("data-asset-state") === "unresolved") return false;
            const cs = getComputedStyle(el);
            return /dashed/i.test(cs.borderStyle || "") || /repeating-linear-gradient/i.test(cs.backgroundImage || "");
          }).length
        : 0;
      const util = document.querySelector('[data-home-region-id="utility_navigation"]');
      const hiddenLang = util
        ? [...util.querySelectorAll('[data-home-effective-variant="hidden"]')].filter(
            (el) => {
              const t = (el.textContent || "").replace(/\s+/g, " ").trim();
              return t === "ENG" || t === "CHN" || t === "JPN";
            }
          )
        : [];
      const hiddenVisible = hiddenLang.filter((el) => {
        const cs = getComputedStyle(el);
        if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0) {
          return false;
        }
        return el.offsetParent !== null || cs.position === "fixed";
      });
      // 비주얼 모아보기: visible control, not metadata-only, non-zero box.
      let collectControl = null;
      for (const el of allItems) {
        const t = (el.textContent || "").replace(/\s+/g, " ").trim();
        if (/비주얼\s*모아보기/.test(t) || t === "비주얼 모아보기") {
          collectControl = el;
          break;
        }
      }
      if (!collectControl) {
        collectControl = document.querySelector(
          '[data-home-region-id="main_banner"] [data-home-presentation="control"]'
        );
      }
      const collectCs = collectControl ? getComputedStyle(collectControl) : null;
      const collectR = collectControl
        ? collectControl.getBoundingClientRect()
        : null;
      const collectPresentation = collectControl
        ? collectControl.getAttribute("data-home-presentation")
        : null;
      const collectText = collectControl
        ? (collectControl.textContent || "").replace(/\s+/g, " ").trim()
        : "";
      const collectVisible =
        !!collectControl &&
        collectPresentation !== "metadata-only" &&
        collectCs &&
        collectCs.display !== "none" &&
        collectCs.visibility !== "hidden" &&
        collectR &&
        collectR.width > 0 &&
        collectR.height > 0;
      // Document/page overflow: viewport-level HTML/body only (not scaled canvas scrollWidth).
      const html = document.documentElement;
      const body = document.body;
      const pageLevelOverflow =
        html.scrollWidth > html.clientWidth + 1 ||
        body.scrollWidth > body.clientWidth + 1;
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
        expectedShaOk:
          root && root.getAttribute("data-home-fixture-sha256") === expectedSha,
        regions,
        regionOrderMatch: JSON.stringify(regions) === JSON.stringify(regionOrder),
        itemDomCount: allItems.length,
        metadataOnlyCount: metadataOnly.length,
        visualCardCount: visualCards.length,
        controlCount: controls.length,
        orderNonDecreasing,
        metaFocusable,
        collectTextHasVisual: /비주얼|모아보기/.test(collectText),
        collectVisible,
        collectPresentation,
        collectVisualW: collectR ? collectR.width : null,
        collectVisualH: collectR ? collectR.height : null,
        fixtureRootW: rootEl ? rootEl.getBoundingClientRect().width : null,
        regionW: region ? region.getBoundingClientRect().width : null,
        railClientW: itemsBox ? itemsBox.clientWidth : null,
        railScrollW: itemsBox ? itemsBox.scrollWidth : null,
        railVisualW: itemsBox ? itemsBox.getBoundingClientRect().width : null,
        visibleVisualCount: visibleVisual.length,
        // Layout diagnostics (offsetWidth) — not pass criteria.
        layoutCardWMin: layoutCardW[0] ?? null,
        layoutCardWMed: median(layoutCardW),
        layoutCardWMax: layoutCardW[layoutCardW.length - 1] ?? null,
        layoutTextWMin: layoutTextW[0] ?? null,
        layoutTextWMed: median(layoutTextW),
        // Visual pass criteria (getBoundingClientRect).
        cardWMin: visualCardW[0] ?? null,
        cardWMed: median(visualCardW),
        cardWMax: visualCardW[visualCardW.length - 1] ?? null,
        textWMin: visualTextW[0] ?? null,
        textWMed: median(visualTextW),
        textWLt40: visualTextW.filter((w) => w < 40).length,
        visualFallbackWMin: visualFallbackW[0] ?? null,
        visualFallbackWMed: median(visualFallbackW),
        visualTransformRatio,
        canvasTransform,
        verticalCharWrapSuspect,
        cardsOutsideRoot,
        fallbackOutsideCard,
        unresolvedFallbacks,
        remoteOfficialImgs,
        brokenImgs,
        dashedLegacy,
        overflowX: pageLevelOverflow,
        docScrollW: document.documentElement.scrollWidth,
        docClientW: document.documentElement.clientWidth,
        state: document.body.getAttribute("data-first-use-state"),
        mobileSurface: document.body.getAttribute("data-mobile-surface"),
        hiddenLangCount: hiddenLang.length,
        hiddenVisibleCount: hiddenVisible.length,
        targets,
        viewport: `${window.innerWidth}x${window.innerHeight}`,
      };
    },
    { expectedSha, regionOrder }
  );
}

function assertSafety(counters, label) {
  assert.strictEqual(counters.externalRequests, 0, `${label}: external requests`);
  assert.strictEqual(counters.externalNavigations, 0, `${label}: external navigations`);
  assert.strictEqual(
    counters.consoleErrors,
    0,
    `${label}: console errors ${JSON.stringify(counters.consoleErrorTexts)}`
  );
  assert.strictEqual(
    counters.pageErrors,
    0,
    `${label}: page errors ${JSON.stringify(counters.pageErrorTexts)}`
  );
  assert.strictEqual(
    counters.requestFailures,
    0,
    `${label}: failed requests ${JSON.stringify(counters.failedRequests)}`
  );
  assert.strictEqual(counters.formSubmissions, 0, `${label}: form submissions`);
  assert.strictEqual(counters.loginAttempts, 0, `${label}: login`);
  assert.strictEqual(counters.paymentAttempts, 0, `${label}: payment`);
  assert.strictEqual(counters.piiTransmissions, 0, `${label}: pii`);
  assert.strictEqual(
    counters.remoteVisualRequests,
    0,
    `${label}: remote /upload/visual requests`
  );
}

function assertCoreHome(result, label) {
  assert.ok(result.expectedShaOk, `${label}: fixture sha mismatch ${result.sha}`);
  assert.strictEqual(result.cloneStatus, "capture_required", `${label}: clone_status`);
  assert.strictEqual(result.exact, "false", `${label}: exact_clone_claimed`);
  assert.ok(
    result.regionOrderMatch,
    `${label}: region order mismatch ${JSON.stringify(result.regions)}`
  );
  assert.strictEqual(result.itemDomCount, 31, `${label}: canonical DOM item count`);
  assert.strictEqual(result.metadataOnlyCount, 15, `${label}: metadata-only count`);
  assert.strictEqual(result.visualCardCount, 15, `${label}: visual-card count`);
  assert.ok(result.orderNonDecreasing, `${label}: item order non-decreasing`);
  assert.strictEqual(result.metaFocusable, 0, `${label}: metadata-only focusable`);
  assert.ok(result.collectTextHasVisual, `${label}: 비주얼 모아보기 text present`);
  assert.ok(
    result.collectVisible,
    `${label}: 비주얼 모아보기 not visually visible (presentation=${result.collectPresentation}, w=${result.collectVisualW}, h=${result.collectVisualH})`
  );
  assert.notStrictEqual(
    result.collectPresentation,
    "metadata-only",
    `${label}: 비주얼 모아보기 must not be metadata-only`
  );
  assert.strictEqual(result.unresolvedFallbacks, 15, `${label}: unresolved fallbacks`);
  assert.strictEqual(result.remoteOfficialImgs, 0, `${label}: remote official imgs`);
  assert.strictEqual(result.brokenImgs, 0, `${label}: broken imgs`);
  assert.strictEqual(result.dashedLegacy, 0, `${label}: dashed legacy placeholders`);
  // Visual geometry pass criteria only (not offsetWidth/layout).
  assert.strictEqual(result.textWLt40, 0, `${label}: visual text width <40 count`);
  assert.strictEqual(
    result.verticalCharWrapSuspect,
    0,
    `${label}: visual vertical char wrap suspect`
  );
  assert.strictEqual(result.cardsOutsideRoot, 0, `${label}: cards outside root`);
  assert.strictEqual(result.fallbackOutsideCard, 0, `${label}: fallback outside card`);
  assert.strictEqual(result.overflowX, false, `${label}: page overflow`);
  assert.ok(
    result.railScrollW == null ||
      result.railClientW == null ||
      result.railScrollW >= result.railClientW - 1,
    `${label}: rail metrics`
  );
  for (const t of result.targets) {
    assert.ok(t.present, `${label}: missing target ${t.t}`);
  }
}

async function runScenario(browser, baseUrl, name, viewport, prepare, expectations) {
  const context = await browser.newContext({
    viewport,
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const counters = attachSafety(page, baseUrl);
  await openHome(page, baseUrl);
  if (prepare) await prepare(page);
  const result = await measureMainBanner(page, EXPECTED_FIXTURE_SHA, REGION_ORDER);
  assertCoreHome(result, name);
  if (expectations) {
    if (expectations.state != null) {
      assert.strictEqual(
        result.state,
        expectations.state,
        `${name}: expected state ${expectations.state}, got ${result.state}`
      );
    }
    if (expectations.mobileSurface != null) {
      assert.strictEqual(
        result.mobileSurface,
        expectations.mobileSurface,
        `${name}: expected mobile surface ${expectations.mobileSurface}, got ${result.mobileSurface}`
      );
    }
  }
  const minCard = viewport.width <= 430 ? MOBILE_MIN_CARD : DESKTOP_MIN_CARD;
  // Pass criterion: visual (getBoundingClientRect) only — never offsetWidth.
  assert.ok(
    result.cardWMin != null && result.cardWMin + 0.5 >= minCard,
    `${name}: visual card min width ${result.cardWMin} < ${minCard} ` +
      `(layoutMin=${result.layoutCardWMin}, ratio=${result.visualTransformRatio})`
  );
  assert.ok(
    result.textWMin == null || result.textWMin + 0.5 >= TEXT_MIN_W,
    `${name}: visual text min width ${result.textWMin} < ${TEXT_MIN_W} ` +
      `(layoutMin=${result.layoutTextWMin}, ratio=${result.visualTransformRatio})`
  );
  assertSafety(counters, name);
  console.log(
    `  [${name}] state=${result.state} surface=${result.mobileSurface} ` +
      `visCardMin=${result.cardWMin?.toFixed?.(1) ?? result.cardWMin} ` +
      `layCardMin=${result.layoutCardWMin?.toFixed?.(1) ?? result.layoutCardWMin} ` +
      `visTextMin=${result.textWMin?.toFixed?.(1) ?? result.textWMin} ` +
      `layTextMin=${result.layoutTextWMin?.toFixed?.(1) ?? result.layoutTextWMin} ` +
      `ratio=${result.visualTransformRatio?.toFixed?.(3) ?? result.visualTransformRatio} ` +
      `rail=${result.railClientW}/${result.railScrollW} overflow=${result.overflowX} ` +
      `reqFail=${counters.requestFailures}`
  );
  await context.close();
  return { result, counters };
}

async function main() {
  console.log("=== #1170/#1192 home fixture canvas browser E2E ===");
  const dist = buildStaticDist();
  console.log(`  static build: ${dist}`);
  const { server, baseUrl } = await startStaticServer(dist);
  console.log(`  server: ${baseUrl}`);
  const browser = await launchBrowser();
  const summary = {};

  try {
    summary.entry_1440x900 = await runScenario(
      browser,
      baseUrl,
      "entry-1440x900",
      { width: 1440, height: 900 },
      null,
      { state: "entry" }
    );
    summary.split_1440x900 = await runScenario(
      browser,
      baseUrl,
      "split-1440x900",
      { width: 1440, height: 900 },
      enterSplitViaFirstQuestion,
      { state: "split" }
    );
    summary.split_1440x760 = await runScenario(
      browser,
      baseUrl,
      "split-1440x760",
      { width: 1440, height: 760 },
      enterSplitViaFirstQuestion,
      { state: "split" }
    );
    summary.mobile_guidance_390x844 = await runScenario(
      browser,
      baseUrl,
      "mobile-guidance-390x844",
      { width: 390, height: 844 },
      async (page) => {
        await enterSplitViaFirstQuestion(page);
        const tab = await page.$("#tab-guidance");
        assert.ok(tab, "mobile-guidance: #tab-guidance missing");
        await tab.click();
        await page.waitForFunction(
          () => document.body.getAttribute("data-mobile-surface") === "guidance",
          null,
          { timeout: 10000 }
        );
        await page.waitForSelector('[data-home-region-id="main_banner"]', {
          state: "visible",
          timeout: 10000,
        });
        // Ensure home route content (not parking-only) for banner geometry.
        await page.evaluate(() => {
          if (
            window.CitizenActionDemoCanvas &&
            typeof window.CitizenActionDemoCanvas.navigateToRoute === "function"
          ) {
            window.CitizenActionDemoCanvas.navigateToRoute("home");
          }
        });
        await page.waitForTimeout(300);
        // Re-assert guidance surface after home navigation (still split shell).
        await page.waitForFunction(
          () => {
            const state = document.body.getAttribute("data-first-use-state");
            const surface = document.body.getAttribute("data-mobile-surface");
            return state === "split" && surface === "guidance";
          },
          null,
          { timeout: 10000 }
        );
      },
      { state: "split", mobileSurface: "guidance" }
    );

    console.log("PASS #1170/#1192 home fixture canvas browser E2E");
    console.log(
      JSON.stringify(
        Object.fromEntries(
          Object.entries(summary).map(([k, v]) => [
            k,
            {
              viewport: v.result.viewport,
              state: v.result.state,
              mobileSurface: v.result.mobileSurface,
              metadataOnly: v.result.metadataOnlyCount,
              visualCards: v.result.visualCardCount,
              layoutCardWMin: v.result.layoutCardWMin,
              layoutCardWMed: v.result.layoutCardWMed,
              layoutCardWMax: v.result.layoutCardWMax,
              visualCardWMin: v.result.cardWMin,
              visualCardWMed: v.result.cardWMed,
              visualCardWMax: v.result.cardWMax,
              layoutTextWMin: v.result.layoutTextWMin,
              layoutTextWMed: v.result.layoutTextWMed,
              visualTextWMin: v.result.textWMin,
              visualTextWMed: v.result.textWMed,
              textWLt40: v.result.textWLt40,
              wrapSuspect: v.result.verticalCharWrapSuspect,
              visualTransformRatio: v.result.visualTransformRatio,
              visualFallbackWMin: v.result.visualFallbackWMin,
              collectVisible: v.result.collectVisible,
              fallbacks: v.result.unresolvedFallbacks,
              remoteOfficial: v.result.remoteOfficialImgs,
              overflow: v.result.overflowX,
              rail: `${v.result.railClientW}/${v.result.railScrollW}`,
              safety: {
                console: v.counters.consoleErrors,
                page: v.counters.pageErrors,
                external: v.counters.externalRequests,
                requestFailures: v.counters.requestFailures,
                remoteVisual: v.counters.remoteVisualRequests,
              },
            },
          ])
        ),
        null,
        2
      )
    );
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch((err) => {
  console.error("FAIL", err);
  process.exit(1);
});
