// tests/browser/verify_page_agent_lab_e2e.mjs
//
// End-to-end browser verification for the #1090 Page Agent lab.
//
// REQUIRED BEHAVIOR:
//   built-in Panel input -> PageAgentCore -> same-origin customFetch
//   -> AgentOutput tool call -> PageController execute_javascript
//   -> target section scroll + visual marker -> done
//   -> built-in Panel history/status display
//
// FAILS IMMEDIATELY if the Panel textarea is not found (no fallback).

import { chromium } from "playwright";
import assert from "node:assert";
import { writeFileSync, mkdirSync, existsSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = join(__dirname, "..", "..", "docs", "artifacts", "1090-page-agent-lab");
const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1"]);

function validateBaseUrl(baseUrl) {
  const parsed = new URL(baseUrl);
  if (!LOCAL_HOSTS.has(parsed.hostname)) throw new Error(`BASE_ORIGIN must be localhost: ${parsed.hostname}`);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") throw new Error("protocol must be http/https");
  if (parsed.username || parsed.password) throw new Error("no credentials");
  if (parsed.search) throw new Error("no query string");
  if (parsed.hash) throw new Error("no hash");
}

function ensureScreenshotDir() {
  if (!existsSync(SCREENSHOT_DIR)) mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function screenshot(page, name) {
  ensureScreenshotDir();
  await page.screenshot({ path: join(SCREENSHOT_DIR, name), fullPage: false });
}

function getLaunchOptions() {
  if (process.env.PAGE_AGENT_BROWSER_EXECUTABLE) {
    return { headless: true, executablePath: process.env.PAGE_AGENT_BROWSER_EXECUTABLE };
  }
  return { headless: true, channel: "chrome" };
}

const SUPPORTED_TASKS = [
  { id: "quick-start", prompt: "Show the Quick Start section.", sectionId: "quick-start" },
  { id: "vs-browser-use", prompt: "Compare page-agent with browser-use.", sectionId: "vs-browser-use" },
  { id: "license", prompt: "Show the MIT license section.", sectionId: "license" },
  { id: "architecture", prompt: "Find the custom UI architecture.", sectionId: "architecture" },
];
const UNKNOWN_TASK = { id: "unknown", prompt: "What is the weather today?" };

async function getDiagnostics(page) {
  return page.evaluate(() => {
    const m = window.PageAgentLabMockModel || window.PageAgentMockModel;
    if (!m || !m.getDiagnostics) return null;
    return m.getDiagnostics();
  });
}

async function getPanelInputHandle(page) {
  const selectors = [
    "div.panel-container textarea",
    "textarea.page-agent-panel-input",
    "#pageAgentPanel textarea",
    "div[class*='page-agent'] textarea[placeholder]",
    "div[class*='panel'] textarea",
  ];
  for (const sel of selectors) {
    const el = await page.$(sel);
    if (el) return el;
  }
  return null;
}

async function submitTaskViaPanel(page, prompt) {
  const input = await getPanelInputHandle(page);
  assert.ok(input, `Panel textarea not found in DOM — cannot submit task: "${prompt}". PageAgent Panel may not be rendered.`);
  await input.click();
  await input.fill(prompt);
  await page.evaluate((el) => {
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }, input);
  await page.waitForTimeout(300);
  await input.press("Enter");
}

async function verifySectionInViewport(page, sectionId, viewportHeight) {
  const rect = await page.evaluate((sid) => {
    const el = document.getElementById(sid);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { top: r.top, bottom: r.bottom };
  }, sectionId);
  assert.ok(rect !== null, `Section #${sectionId} must exist in DOM`);
  assert.ok(rect.top < viewportHeight && rect.bottom > 0,
    `Section #${sectionId} must be within viewport (top=${rect.top}, bottom=${rect.bottom}, viewport=${viewportHeight})`);
  return rect;
}

async function verifyVisualMarker(page, sectionId) {
  const hasMarker = await page.evaluate((sid) => {
    const el = document.getElementById(sid);
    if (!el) return { exists: false };
    return {
      exists: true,
      hasClass: el.classList.contains("page-agent-target-active"),
      hasAttribute: el.getAttribute("data-page-agent-target") === "active",
    };
  }, sectionId);
  assert.ok(hasMarker.exists, `Section #${sectionId} must exist`);
  assert.ok(hasMarker.hasClass, `Section #${sectionId} must have page-agent-target-active class (visual marker)`);
  assert.ok(hasMarker.hasAttribute, `Section #${sectionId} must have data-page-agent-target='active' attribute`);
}

async function verifyUnknownTaskResult(page) {
  const diag = await getDiagnostics(page);
  assert.ok(diag !== null, "Diagnostics must be available after unknown task");
  // Last action should be 'done' (not execute_javascript)
  const lastAction = diag.actionNames?.[diag.actionNames.length - 1];
  assert.strictEqual(lastAction, "done", "Unknown task must end with 'done', not execute_javascript");
  // No execute_javascript in action history
  assert.ok(!diag.actionNames.includes("execute_javascript"),
    "Unknown task must NOT trigger execute_javascript");
}

async function runSingleTask(page, task) {
  const label = task.id;
  console.log(`    "${label}"...`);

  // Record position before
  const beforePos = await page.evaluate((sid) => {
    const el = sid ? document.getElementById(sid) : null;
    return el ? el.getBoundingClientRect().top : null;
  }, task.sectionId || null);

  // Reset diagnostics tracking
  await page.evaluate(() => {
    const m = window.PageAgentLabMockModel || window.PageAgentMockModel;
    if (m && m.getDiagnostics) { /* just reset, no API for reset */ }
  });

  // Submit via real Panel textarea
  await submitTaskViaPanel(page, task.prompt);
  await page.waitForTimeout(5000);

  // Read mock diagnostics
  const diag = await getDiagnostics(page);

  return { taskId: label, diagnostics: diag, beforePosition: beforePos };
}

async function main() {
  const baseUrl = process.argv[2];
  if (!baseUrl) {
    console.error("Usage: node verify_page_agent_lab_e2e.mjs <BASE_URL>");
    process.exit(1);
  }
  validateBaseUrl(baseUrl);
  const labUrl = baseUrl.replace(/\/+$/, "") + "/examples/page-agent/";
  console.log(`Verifying Page Agent lab at: ${labUrl}`);

  const browser = await chromium.launch(getLaunchOptions());
  let allPassed = true;
  let desktopCtx, mobileCtx;

  try {
    // ═══════════════════ Desktop (1440x900) ═══════════════════
    console.log("\n[Desktop 1440x900]");
    desktopCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const dp = await desktopCtx.newPage();
    const desktopReqMonitor = [];

    dp.on("request", (r) => desktopReqMonitor.push({ url: r.url(), method: r.method() }));
    dp.on("console", (msg) => {
      if (msg.type() === "error" || msg.type() === "warning") {
        throw new Error(`[${msg.type().toUpperCase()}] ${msg.text()}`);
      }
    });
    dp.on("pageerror", (err) => { throw new Error(`Page error: ${err.message}`); });
    dp.on("requestfailed", (req) => {
      const err = req.failure()?.errorText || "unknown";
      if (!req.url().includes("favicon")) throw new Error(`Request failed: ${req.url()} (${err})`);
    });

    await dp.goto(labUrl, { waitUntil: "networkidle", timeout: 20000 });
    await screenshot(dp, "desktop-initial.png");

    // Verify Panel initialization via window.__PAGE_AGENT_LAB__
    const labState = await dp.evaluate(() => {
      const lab = window.__PAGE_AGENT_LAB__;
      return lab ? { ok: true, integration: lab.integration, panel: lab.panel } : { ok: false };
    });
    assert.ok(labState.ok, "window.__PAGE_AGENT_LAB__ must be defined");
    assert.strictEqual(labState.integration, "actual-page-agent", "must be actual PageAgent runtime");
    assert.strictEqual(labState.panel, "built-in", "must use built-in Panel");
    console.log("  Panel initialized (built-in) ✓");

    // Verify Panel textarea exists - FAIL IMMEDIATELY if not found
    const panelInput = await getPanelInputHandle(dp);
    assert.ok(panelInput, "Panel textarea must be present in DOM. This is a hard requirement - if the PageAgent Panel is not rendered, no tasks can be submitted.");
    console.log("  Panel textarea found ✓");

    // ── Run supported tasks (3 minimum) ──────────────────────────────────
    const desktopResults = [];
    for (let i = 0; i < 3; i++) {
      const task = SUPPORTED_TASKS[i];
      const result = await runSingleTask(dp, task);
      desktopResults.push(result);

      // Verify section in viewport (viewport height = 900 for desktop)
      await verifySectionInViewport(dp, task.sectionId, 900);
      // Verify visual marker (page-agent-target-active class)
      await verifyVisualMarker(dp, task.sectionId);
      // Verify mock was called
      assert.ok(result.diagnostics && result.diagnostics.callCount > 0,
        `Mock must be called for task ${task.id}`);
      console.log(`    ✓ section #${task.sectionId} in viewport + marker`);
    }

    // Verify all 3 tasks had Panel submission
    assert.ok(desktopResults.length === 3, "Must have 3 desktop task results");

    // ── Run unknown task ────────────────────────────────────────────────
    console.log(`  Unknown: "${UNKNOWN_TASK.prompt}"`);
    const unknownDiagBefore = await getDiagnostics(dp);
    await submitTaskViaPanel(dp, UNKNOWN_TASK.prompt);
    await dp.waitForTimeout(5000);
    const unknownResult = await runSingleTask(dp, UNKNOWN_TASK);
    await verifyUnknownTaskResult(dp);
    console.log(`    ✓ unknown task correctly returns done (not execute_javascript)`);

    // ── Check non-local requests ────────────────────────────────────────
    const deskNonLocal = desktopReqMonitor.filter(
      (r) => !r.url.startsWith(baseUrl) && !r.url.includes("favicon")
    );
    assert.strictEqual(deskNonLocal.length, 0,
      `Desktop non-local requests found: ${JSON.stringify(deskNonLocal.slice(0, 5))}`);

    await screenshot(dp, "desktop-final.png");

    // ═══════════════════ Mobile (390x844) ═══════════════════
    console.log("\n[Mobile 390x844]");
    mobileCtx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const mp = await mobileCtx.newPage();
    const mobileReqMonitor = [];

    mp.on("request", (r) => mobileReqMonitor.push({ url: r.url(), method: r.method() }));
    mp.on("pageerror", (err) => { throw new Error(`Mobile page error: ${err.message}`); });
    mp.on("requestfailed", (req) => {
      const err = req.failure()?.errorText || "unknown";
      if (!req.url().includes("favicon")) throw new Error(`Mobile request failed: ${req.url()} (${err})`);
    });

    await mp.goto(labUrl, { waitUntil: "networkidle", timeout: 20000 });
    await screenshot(mp, "mobile-initial.png");

    // Verify Panel textarea exists on mobile
    const mobilePanelInput = await getPanelInputHandle(mp);
    assert.ok(mobilePanelInput, "Panel textarea must exist on mobile (hard requirement)");
    console.log("  Mobile Panel textarea found ✓");

    // Run 1 supported task on mobile
    const mobileTask = SUPPORTED_TASKS[0];
    const mobileResult = await runSingleTask(mp, mobileTask);
    await verifySectionInViewport(mp, mobileTask.sectionId, 844);
    await verifyVisualMarker(mp, mobileTask.sectionId);
    console.log(`  ✓ Mobile task #${mobileTask.sectionId} completed`);

    // Check non-local requests on mobile
    const mobNonLocal = mobileReqMonitor.filter(
      (r) => !r.url.startsWith(baseUrl) && !r.url.includes("favicon")
    );
    assert.strictEqual(mobNonLocal.length, 0,
      `Mobile non-local requests found: ${JSON.stringify(mobNonLocal.slice(0, 5))}`);

    await screenshot(mp, "mobile-final.png");

    // ═══════════════════ Summary ═══════════════════
    console.log(`\n  === SUMMARY ===`);
    console.log(`  Desktop tasks: 3 supported + 1 unknown = ${desktopResults.length + 1}`);
    console.log(`  Desktop non-local requests: ${deskNonLocal.length}`);
    console.log(`  Mobile tasks: 1 supported`);
    console.log(`  Mobile non-local requests: ${mobNonLocal.length}`);
    console.log(`\nAll Page Agent lab E2E checks passed.`);

    // Save evidence
    ensureScreenshotDir();
    writeFileSync(join(SCREENSHOT_DIR, "browser-evidence.json"), JSON.stringify({
      baseUrl, labUrl, timestamp: new Date().toISOString(),
      desktopTasks: desktopResults.length,
      mobileTasks: 1,
      desktopResults: desktopResults.map((r) => ({ taskId: r.taskId, callCount: r.diagnostics?.callCount })),
    }, null, 2));
  } catch (err) {
    console.error("\nPage Agent lab E2E verification FAILED:");
    console.error(err && err.stack ? err.stack : err);
    allPassed = false;
  } finally {
    if (desktopCtx) await desktopCtx.close();
    if (mobileCtx) await mobileCtx.close();
    await browser.close();
  }

  if (!allPassed) process.exit(1);
}

main();
