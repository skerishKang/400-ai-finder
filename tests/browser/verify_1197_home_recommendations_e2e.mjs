/**
 * #1197: approved default home + recommendations defaults + AI chip single-line.
 * Offline static only.
 */
import assert from "node:assert";
import { spawnSync } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");
const LOCAL = new Set(["127.0.0.1", "localhost", "::1"]);
const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".json": "application/json",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function buildDist() {
  const out = join(ROOT, "dist", "cloudflare-pages-1197");
  const r = spawnSync("python", ["scripts/build_cloudflare_pages.py", "--out-dir", out], {
    cwd: ROOT,
    encoding: "utf-8",
  });
  if (r.status !== 0) throw new Error(r.stdout + r.stderr);
  return out;
}

function startServer(rootDir) {
  const server = createServer((req, res) => {
    try {
      const url = new URL(req.url || "/", "http://127.0.0.1");
      let p = decodeURIComponent(url.pathname);
      if (p === "/" || p === "/mvp" || p === "/mvp/") p = "/static/citizen-action-demo.html";
      if (p.startsWith("/mvp/")) p = p.slice(4);
      const fp = join(rootDir, p.replace(/^\/+/, ""));
      if (!fp.startsWith(rootDir) || !existsSync(fp) || !statSync(fp).isFile()) {
        res.writeHead(404);
        res.end("not found");
        return;
      }
      res.writeHead(200, { "Content-Type": MIME[extname(fp)] || "application/octet-stream" });
      res.end(readFileSync(fp));
    } catch (e) {
      res.writeHead(500);
      res.end(String(e));
    }
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      resolve({ server, baseUrl: `http://127.0.0.1:${server.address().port}` });
    });
  });
}

async function launch() {
  try {
    return await chromium.launch({ headless: true, channel: "chrome" });
  } catch (_) {
    return chromium.launch({ headless: true });
  }
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

async function measure(page) {
  return page.evaluate(() => {
    const title = document.querySelector(".chat-shell__title");
    const home = document.querySelector(".bg-page--home");
    const fixtureRoot = document.querySelector(".bg-home-fixture-root");
    const visualCards = document.querySelectorAll(
      '[data-home-presentation="visual-card"]'
    );
    const mayor = document.querySelector('img[src*="home-mayor-card"]');
    const quick = document.querySelectorAll(".bg-home-quick-link");
    const banner = document.querySelector(
      'img[src*="home-alert-banner"], .bg-home-alert, .bg-home-banner'
    );
    const streetBtn = [...document.querySelectorAll(".chat-chip")].find((el) =>
      (el.textContent || "").includes("가로등")
    );
    const litterBtn = [...document.querySelectorAll(".chat-chip")].find((el) =>
      (el.textContent || "").includes("쓰레기")
    );
    const street = streetBtn?.querySelector(".chat-chip__label") || streetBtn;
    const litter = litterBtn?.querySelector(".chat-chip__label") || litterBtn;
    function lineCount(el) {
      if (!el) return null;
      const cs = getComputedStyle(el);
      const lh = parseFloat(cs.lineHeight);
      const h = el.getBoundingClientRect().height;
      const range = document.createRange();
      range.selectNodeContents(el);
      const rects = [...range.getClientRects()];
      const lineBoxes = rects.length || Math.max(1, Math.round(h / (lh || 20)));
      return {
        h,
        lh: lh || null,
        lines: lineBoxes,
        w: el.getBoundingClientRect().width,
        text: (el.textContent || "").trim(),
        whiteSpace: cs.whiteSpace,
        hasCompact: !!(streetBtn || litterBtn)?.classList?.contains("chat-chip--ai-compact"),
      };
    }
    return {
      title: title ? title.textContent.trim() : null,
      hasHome: !!home,
      hasFixtureRoot: !!fixtureRoot,
      visualCardCount: visualCards.length,
      hasMayor: !!mayor,
      quickCount: quick.length,
      hasBanner: !!banner,
      targets: {
        civil: !!document.querySelector('[data-action-target="nav-civil-service"]'),
        complaint: !!document.querySelector('[data-action-target="nav-complaint-board"]'),
        mayor: !!document.querySelector('[data-action-target="mayor-office-open"]'),
      },
      recExpanded: document.body.getAttribute("data-recommendations-expanded"),
      state: document.body.getAttribute("data-first-use-state"),
      street: lineCount(street),
      litter: lineCount(litter),
      overflow:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth + 1,
    };
  });
}

async function runViewport(browser, baseUrl, name, viewport, afterFirstQuestion) {
  const ctx = await browser.newContext({ viewport, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  const safety = attachSafety(page, baseUrl);
  await page.goto(`${baseUrl}/static/citizen-action-demo.html`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForFunction(
    () => window.CitizenActionDemoCanvas?.navigateToRoute,
    null,
    { timeout: 15000 }
  );
  await page.evaluate(() => window.CitizenActionDemoCanvas.navigateToRoute("home"));
  await page.waitForSelector(".bg-page--home", { timeout: 10000 });

  if (afterFirstQuestion) {
    await page.fill("#chat-composer-input", "불법 주정차 신고는 어디서 하나요?");
    await page.click("#chat-composer-send");
    await page.waitForFunction(
      () => document.body.getAttribute("data-first-use-state") === "split",
      null,
      { timeout: 20000 }
    );
    if (viewport.width <= 430) {
      const tab = await page.$("#tab-guidance");
      if (tab) await tab.click();
      await page.waitForTimeout(400);
    }
    await page.evaluate(() => window.CitizenActionDemoCanvas.navigateToRoute("home"));
    await page.waitForTimeout(300);
  }

  const m = await measure(page);
  assert.strictEqual(m.title, "네비게이터", `${name}: title`);
  assert.ok(m.hasHome, `${name}: home`);
  assert.strictEqual(m.hasFixtureRoot, false, `${name}: no fixture root`);
  assert.strictEqual(m.visualCardCount, 0, `${name}: no visual-card rail`);
  assert.ok(m.hasMayor, `${name}: mayor card`);
  assert.ok(m.quickCount >= 4, `${name}: quick services`);
  assert.ok(m.targets.civil && m.targets.complaint, `${name}: action targets`);
  if (afterFirstQuestion) {
    assert.notStrictEqual(m.recExpanded, "false", `${name}: recommendations expanded`);
  }
  if (m.street) {
    assert.ok(m.street.lines < 1.6, `${name}: streetlight one line ${JSON.stringify(m.street)}`);
    assert.ok(m.street.text.includes("(AI)"), `${name}: streetlight label`);
  }
  if (m.litter) {
    assert.ok(m.litter.lines < 1.6, `${name}: litter one line ${JSON.stringify(m.litter)}`);
    assert.ok(m.litter.text.includes("(AI)"), `${name}: litter label`);
  }
  assert.strictEqual(m.overflow, false, `${name}: overflow`);
  assert.strictEqual(safety.consoleErrors, 0, `${name}: console ${safety.texts}`);
  assert.strictEqual(safety.pageErrors, 0, `${name}: page`);
  assert.strictEqual(safety.external, 0, `${name}: external`);
  console.log(
    `  [${name}] title=${m.title} mayor=${m.hasMayor} quick=${m.quickCount} ` +
      `fixtureRoot=${m.hasFixtureRoot} cards=${m.visualCardCount} rec=${m.recExpanded} ` +
      `streetLines=${m.street?.lines?.toFixed?.(2)} litterLines=${m.litter?.lines?.toFixed?.(2)} ` +
      `overflow=${m.overflow}`
  );
  await ctx.close();
  return m;
}

async function main() {
  console.log("=== #1197 home + recommendations browser contract ===");
  const dist = buildDist();
  const { server, baseUrl } = await startServer(dist);
  const browser = await launch();
  try {
    await runViewport(browser, baseUrl, "entry-1440x900", { width: 1440, height: 900 }, false);
    await runViewport(browser, baseUrl, "split-1440x900", { width: 1440, height: 900 }, true);
    await runViewport(browser, baseUrl, "split-1440x760", { width: 1440, height: 760 }, true);
    await runViewport(browser, baseUrl, "mobile-390x844", { width: 390, height: 844 }, true);
    console.log("PASS #1197 home + recommendations browser contract");
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch((e) => {
  console.error("FAIL", e);
  process.exit(1);
});
