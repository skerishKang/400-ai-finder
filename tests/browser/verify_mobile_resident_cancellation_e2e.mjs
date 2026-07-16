/**
 * #1183 Mobile Page Agent cancellation contract (fail-closed).
 *
 * Locks real Playwright pointer cancellation on mobile while preserving desktop.
 * Does not use force-click or JS evaluate cancel — only real pointer clicks.
 *
 * Usage:
 *   node tests/browser/verify_mobile_resident_cancellation_e2e.mjs [baseUrl]
 * Default baseUrl: http://127.0.0.1:8783 (build served by this script if omitted).
 */

import assert from "assert";
import { spawn } from "child_process";
import fs from "fs";
import http from "http";
import os from "os";
import path from "path";
import { fileURLToPath } from "url";
import { chromium } from "playwright";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../..");
const PROMPT = "민원 작성 화면을 열어줘";
const TIMINGS_MS = [250, 1000, 2500];
const REPS = 2;
const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };

const requestedBase = process.argv[2] || null;

function validateOrigin(raw) {
  const parsed = new URL(raw);
  const hostname = parsed.hostname.replace(/^\[|\]$/g, "");
  if (parsed.protocol !== "http:" || !new Set(["127.0.0.1", "localhost", "::1"]).has(hostname)) {
    throw new Error("Cancellation E2E accepts only a local http origin.");
  }
  return parsed.origin;
}

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true, channel: "chrome" });
  } catch {
    return chromium.launch({ headless: true });
  }
}

function buildStaticDist() {
  const out = fs.mkdtempSync(path.join(os.tmpdir(), "1183-cancel-"));
  const env = { ...process.env, PYTHONPATH: REPO_ROOT };
  const result = spawn(
    process.platform === "win32" ? "python" : "python3",
    ["scripts/build_cloudflare_pages.py", "--mode", "static", "--out-dir", out],
    { cwd: REPO_ROOT, env, stdio: ["ignore", "pipe", "pipe"] },
  );
  return new Promise((resolve, reject) => {
    let err = "";
    result.stderr.on("data", (c) => {
      err += c.toString();
    });
    result.on("close", (code) => {
      if (code !== 0) reject(new Error(`build failed (${code}): ${err}`));
      else resolve(out);
    });
  });
}

function startServer(dir) {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const urlPath = decodeURIComponent((req.url || "/").split("?")[0]);
      let filePath = path.join(dir, urlPath === "/" ? "index.html" : urlPath);
      if (filePath.endsWith(path.sep) || fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
        filePath = path.join(filePath, "index.html");
      }
      if (!filePath.startsWith(dir) || !fs.existsSync(filePath)) {
        res.writeHead(404);
        res.end("not found");
        return;
      }
      const ext = path.extname(filePath).toLowerCase();
      const types = {
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json",
        ".png": "image/png",
        ".svg": "image/svg+xml",
      };
      res.writeHead(200, { "Content-Type": types[ext] || "application/octet-stream" });
      fs.createReadStream(filePath).pipe(res);
    });
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({ server, baseUrl: `http://127.0.0.1:${port}` });
    });
    server.on("error", reject);
  });
}

function setupSafety(page, baseUrl) {
  const tracker = {
    external: 0,
    consoleErrors: 0,
    pageErrors: 0,
    requestFailures: 0,
    formSubmissions: 0,
    texts: [],
  };
  page.on("request", (req) => {
    const u = req.url();
    if (!u.startsWith(baseUrl) && !u.startsWith("data:") && !u.startsWith("blob:")) {
      tracker.external += 1;
    }
    if (req.method() === "POST" && /submit|login|payment/i.test(u)) {
      tracker.formSubmissions += 1;
    }
  });
  page.on("requestfailed", (req) => {
    if (!/favicon/i.test(req.url())) tracker.requestFailures += 1;
  });
  page.on("pageerror", (err) => {
    tracker.pageErrors += 1;
    tracker.texts.push(String(err.message || err));
  });
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const t = msg.text();
    if (/favicon|404|Failed to load resource/i.test(t)) return;
    tracker.consoleErrors += 1;
    tracker.texts.push(t);
  });
  return tracker;
}

async function readState(page) {
  return page.evaluate(() => {
    const d =
      window.PageAgentMockModel && window.PageAgentMockModel.getDiagnostics
        ? window.PageAgentMockModel.getDiagnostics()
        : null;
    const input = document.getElementById("chat-input");
    const send = document.getElementById("chat-send");
    const mc = document.getElementById("page-agent-mobile-cancel");
    const cc = document.getElementById("chat-cancel");
    const planStatus = document.getElementById("page-agent-plan-status");
    return {
      plan: document.body.getAttribute("data-page-agent-plan-state"),
      surface: document.body.getAttribute("data-page-agent-mobile-surface"),
      status: document.getElementById("chat-status")
        ? document.getElementById("chat-status").textContent
        : "",
      planStatus: planStatus ? planStatus.textContent : "",
      planDataState: planStatus ? planStatus.getAttribute("data-state") : "",
      route:
        window.CitizenActionDemoCanvas &&
        window.CitizenActionDemoCanvas.getCurrentRouteId
          ? window.CitizenActionDemoCanvas.getCurrentRouteId()
          : null,
      inputDisabled: input ? input.disabled : null,
      sendDisabled: send ? send.disabled : null,
      callCount: d ? d.callCount : null,
      actions: d ? d.actionNames.slice() : [],
      lastSuccess: d ? d.lastSuccess : null,
      mobileCancelHidden: mc ? mc.hidden : null,
      chatCancelDisplay: cc ? getComputedStyle(cc).display : null,
    };
  });
}

async function controlSnapshot(page, selector) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      hidden: el.hidden,
      disabled: !!el.disabled,
      display: cs.display,
      visibility: cs.visibility,
      pointerEvents: cs.pointerEvents,
      w: r.width,
      h: r.height,
      x: r.x,
      y: r.y,
      inertAnc: !!el.closest("[inert]"),
      hiddenAnc: !!el.closest("[hidden]"),
    };
  }, selector);
}

async function realClick(page, selector) {
  const loc = page.locator(selector);
  await loc.waitFor({ state: "visible", timeout: 5000 });
  const box = await loc.boundingBox();
  assert.ok(box && box.width > 0 && box.height > 0, `${selector} must have non-zero box`);
  // Real pointer path (no force, no evaluate click).
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  return box;
}

async function runCancelCase(browser, baseUrl, viewport, delayMs, rep) {
  const label = `${viewport.width}x${viewport.height}@${delayMs}ms#${rep}`;
  const context = await browser.newContext({
    viewport,
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const safety = setupSafety(page, baseUrl);
  const residentUrl = `${baseUrl}/examples/page-agent/resident/`;

  await page.goto(residentUrl, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForSelector("#chat-input", { timeout: 10000 });
  await page.waitForTimeout(400);

  await page.fill("#chat-input", PROMPT);
  await page.click("#chat-send");
  await page.waitForTimeout(delayMs);

  const isMobile = viewport.width <= 768;
  const cancelSel = isMobile ? "#page-agent-mobile-cancel" : "#chat-cancel";
  const pre = await controlSnapshot(page, cancelSel);
  assert.ok(pre, `${label}: cancel control missing (${cancelSel})`);
  assert.notStrictEqual(pre.display, "none", `${label}: cancel display none`);
  assert.notStrictEqual(pre.visibility, "hidden", `${label}: cancel visibility hidden`);
  assert.ok(pre.w > 0 && pre.h > 0, `${label}: cancel zero box ${JSON.stringify(pre)}`);
  assert.strictEqual(pre.disabled, false, `${label}: cancel disabled`);
  assert.strictEqual(pre.inertAnc, false, `${label}: cancel under inert ancestor`);
  assert.strictEqual(pre.hiddenAnc, false, `${label}: cancel under hidden ancestor`);
  assert.notStrictEqual(pre.pointerEvents, "none", `${label}: pointer-events none`);

  if (isMobile) {
    assert.strictEqual(pre.hidden, false, `${label}: mobile cancel hidden attr`);
  }

  const actionsBefore = (await readState(page)).actions.length;
  await realClick(page, cancelSel);

  // Allow in-flight agent loops to settle; cancel must stay terminal.
  await page.waitForTimeout(6000);
  const after = await readState(page);
  const actionsAfterCancel = after.actions.length - actionsBefore;

  assert.strictEqual(
    after.plan,
    "cancelled",
    `${label}: plan must be cancelled (got ${after.plan})`,
  );
  assert.ok(
    after.planDataState === "cancelled" || /취소/.test(after.planStatus || ""),
    `${label}: cancelled UI missing (${after.planStatus})`,
  );
  assert.ok(
    /취소/.test(after.status || "") || after.plan === "cancelled",
    `${label}: status not cancelled (${after.status})`,
  );
  assert.notStrictEqual(
    after.lastSuccess,
    true,
    `${label}: lastSuccess must not be true after cancel`,
  );
  assert.ok(
    actionsAfterCancel <= 0,
    `${label}: actions after cancel must be 0 (delta=${actionsAfterCancel}, actions=${JSON.stringify(after.actions)})`,
  );

  // Early cancel (before multi-step finish): must not land on complaint-write.
  // At 250ms the mock usually has not navigated yet; at 2500ms prior clicks may
  // already have reached intermediate/final routes — still require cancelled terminal.
  if (delayMs <= 250) {
    assert.notStrictEqual(
      after.route,
      "complaint-write",
      `${label}: early cancel must not reach complaint-write (route=${after.route})`,
    );
  }

  // Composer / restart operability after cancel.
  assert.strictEqual(after.inputDisabled, false, `${label}: composer disabled after cancel`);
  assert.strictEqual(after.sendDisabled, false, `${label}: send disabled after cancel`);
  await page.fill("#chat-input", "취소 후 재입력");
  const typed = await page.inputValue("#chat-input");
  assert.strictEqual(typed, "취소 후 재입력", `${label}: composer not operable`);

  assert.strictEqual(safety.external, 0, `${label}: external requests ${safety.external}`);
  assert.strictEqual(safety.formSubmissions, 0, `${label}: form submissions`);
  assert.strictEqual(
    safety.consoleErrors,
    0,
    `${label}: console errors ${JSON.stringify(safety.texts)}`,
  );
  assert.strictEqual(
    safety.pageErrors,
    0,
    `${label}: page errors ${JSON.stringify(safety.texts)}`,
  );

  await context.close();
  return {
    label,
    cancelSel,
    delayMs,
    route: after.route,
    plan: after.plan,
    lastSuccess: after.lastSuccess,
    actions: after.actions,
    actionsAfterCancel,
    safety,
  };
}

async function main() {
  console.log("#1183 mobile/desktop resident cancellation E2E");
  let baseUrl;
  let server = null;
  let dist = null;
  if (requestedBase) {
    baseUrl = validateOrigin(requestedBase);
    console.log(`  baseUrl (provided): ${baseUrl}`);
  } else {
    dist = await buildStaticDist();
    const started = await startServer(dist);
    server = started.server;
    baseUrl = started.baseUrl;
    console.log(`  static build + server: ${baseUrl}`);
  }

  const browser = await launchBrowser();
  const results = [];
  try {
    for (const viewport of [DESKTOP, MOBILE]) {
      for (const delay of TIMINGS_MS) {
        for (let rep = 1; rep <= REPS; rep++) {
          const r = await runCancelCase(browser, baseUrl, viewport, delay, rep);
          results.push(r);
          console.log(
            `  PASS ${r.label} cancel=${r.cancelSel} route=${r.route} actionsAfter=${r.actionsAfterCancel} lastSuccess=${r.lastSuccess}`,
          );
        }
      }
    }
  } finally {
    await browser.close();
    if (server) {
      await new Promise((res) => server.close(res));
    }
  }

  console.log("\n=== SUMMARY ===");
  console.log(`cases: ${results.length}`);
  console.log(
    JSON.stringify(
      results.map((r) => ({
        label: r.label,
        route: r.route,
        plan: r.plan,
        lastSuccess: r.lastSuccess,
        actionsAfterCancel: r.actionsAfterCancel,
      })),
      null,
      2,
    ),
  );
  console.log("#1183 PASS");
}

main().catch((err) => {
  console.error("#1183 cancellation E2E FAILED:");
  console.error(err);
  process.exit(1);
});
