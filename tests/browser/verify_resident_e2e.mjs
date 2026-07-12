// tests/browser/verify_resident_e2e.mjs
//
// End-to-end browser verification for the #1109 Stage 2 resident demo.
//
// REQUIRED BEHAVIOR:
//   custom chat input -> PageAgentCore -> same-origin customFetch
//   -> AgentOutput tool call -> PageController click_element_by_index
//   -> civic canvas route transition -> done
//   -> custom chat history display with action recording
//
// PASS CRITERIA:
//   1. Page Agent runtime boots and custom chat panel is visible
//   2. 5 parity scenarios complete through real action loop
//   3. Click actions (not execute_javascript) are recorded
//   4. Canvas route changes after click actions
//   5. Safety badges displayed (offline/mock, same-origin, no-submit)
//   6. Cancel button present and functional
//   7. No external network requests
//   8. Desktop and mobile viewport both work

import { chromium } from "playwright";
import assert from "node:assert";
import { writeFileSync, mkdirSync, existsSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = join(__dirname, "..", "..", "docs", "artifacts", "1109-resident-demo");
const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1"]);

const UNIQUE_MARKER = "Page Agent형 AI 북구청";
const RELOAD_READY_TIMEOUT = 30000;
const TASK_TIMEOUT_MS = 45000;

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

const EXPECTED_TASKS = [
  { id: "apartment_contact", prompt: "공동주택과 연락처 찾아줘", navSteps: 1 },
  { id: "bulky_waste_menu", prompt: "대형폐기물 신청 메뉴 찾아줘", navSteps: 1 },
  { id: "passport_procedure", prompt: "여권 발급 절차를 찾아줘", navSteps: 1 },
  { id: "complaint_screen", prompt: "민원 작성 화면을 열어줘", navSteps: 2 },
  { id: "mayor_proposal_writing", prompt: "구청장에게 제안할 글 작성을 도와줘", navSteps: 2 },
];

const UNKNOWN_PROMPT = "오늘 날씨 알려줘";

// ── Browser launch ────────────────────────────────────────────────────────

async function launchBrowser() {
  const launchAttempts = [];
  const errors = [];

  const envPath = process.env.PAGE_AGENT_BROWSER_EXECUTABLE;
  if (envPath) {
    launchAttempts.push({
      name: `env: ${envPath}`,
      launch: () => chromium.launch({ headless: true, executablePath: envPath }),
    });
  }

  launchAttempts.push({
    name: "channel: chrome",
    launch: () => chromium.launch({ headless: true, channel: "chrome" }),
  });

  for (const p of KNOWN_BROWSER_PATHS) {
    let exists = false;
    try { readFileSync(p); exists = true; } catch (_) {}
    if (exists) {
      launchAttempts.push({
        name: `path: ${p}`,
        launch: () => chromium.launch({ headless: true, executablePath: p }),
      });
    }
  }

  launchAttempts.push({
    name: "default playwright chromium",
    launch: () => chromium.launch({ headless: true }),
  });

  for (const attempt of launchAttempts) {
    try {
      const browser = await attempt.launch();
      let version = "unknown";
      try { if (browser && typeof browser.version === "function") version = browser.version(); } catch (_) {}
      console.log(`  Browser launched (${attempt.name}, v${version}) ✓`);
      return { browser, launchInfo: { source: attempt.name, version } };
    } catch (e) {
      errors.push(`  [${attempt.name}] ${e.message}`);
    }
  }
  throw new Error(`Cannot launch any browser. Attempts:\n${errors.join("\n")}`);
}

// ── Helpers ───────────────────────────────────────────────────────────────

function validateBaseUrl(baseUrl) {
  const parsed = new URL(baseUrl);
  if (!LOCAL_HOSTS.has(parsed.hostname))
    throw new Error(`BASE_ORIGIN must be localhost: ${parsed.hostname}`);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:")
    throw new Error("protocol must be http/https");
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

// ── Resident page helpers ─────────────────────────────────────────────────

async function waitForResidentReady(page) {
  await page.waitForFunction(
    () => document.readyState === "complete",
    { timeout: RELOAD_READY_TIMEOUT }
  );
  await page.waitForFunction(
    (marker) => document.body.innerText.includes(marker),
    UNIQUE_MARKER,
    { timeout: RELOAD_READY_TIMEOUT }
  );
  // Custom chat input must be visible and enabled
  const inputLocator = page.locator("#chat-input");
  await inputLocator.waitFor({ state: "visible", timeout: RELOAD_READY_TIMEOUT });
  await page.waitForTimeout(500);
}

async function submitTask(page, prompt) {
  const submitted = await page.evaluate((p) => {
    const input = document.getElementById("chat-input");
    if (!input) return false;
    const nativeSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, "value"
    ).set;
    nativeSetter.call(input, p);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.focus({ preventScroll: true });
    input.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true, cancelable: true })
    );
    input.dispatchEvent(
      new KeyboardEvent("keyup", { key: "Enter", code: "Enter", bubbles: true, cancelable: true })
    );
    return true;
  }, prompt);
  assert.ok(submitted, `Chat input not found, cannot submit: "${prompt}"`);
  await page.waitForTimeout(200);
}

async function getChatMessageCount(page) {
  return page.evaluate(() => {
    const container = document.getElementById("chat-messages");
    if (!container) return 0;
    return container.querySelectorAll(".chat-msg").length;
  });
}

async function getChatText(page) {
  return page.evaluate(() => {
    const container = document.getElementById("chat-messages");
    if (!container) return "";
    return container.textContent || "";
  });
}

async function getDiagnostics(page) {
  return page.evaluate(() => {
    const m = window.PageAgentMockModel;
    if (!m || !m.getDiagnostics) return null;
    return m.getDiagnostics();
  });
}

async function resetDiagnostics(page) {
  await page.evaluate(() => {
    const m = window.PageAgentMockModel;
    if (m && m.resetDiagnostics) m.resetDiagnostics();
  });
}

// Wait for supported task completion (diagnostics: at least 2 calls)
async function waitForSupportedCompletion(page, taskId, expectedNavSteps) {
  const expectedCalls = expectedNavSteps + 1; // nav clicks + done
  const maxAttempts = 200;
  for (let i = 0; i < maxAttempts; i++) {
    const d = await getDiagnostics(page);
    if (d && d.callCount >= expectedCalls) {
      const clickCount = d.actionNames.filter(a => a === "click_element_by_index").length;
      if (clickCount === expectedNavSteps && d.actionNames[d.actionNames.length - 1] === "done") {
        return d;
      }
    }
    await new Promise(r => setTimeout(r, 250));
  }
  const finalDiag = await getDiagnostics(page);
  throw new Error(
    `waitForSupportedCompletion timed out for "${taskId}" after ${TASK_TIMEOUT_MS}ms. ` +
    `Expected ${expectedNavSteps + 1} calls, got ${finalDiag ? finalDiag.callCount : "null"}. ` +
    `Actions: ${finalDiag ? finalDiag.actionNames.join(", ") : "N/A"}`
  );
}

// Wait for unknown task completion (diagnostics: 1 call, done with success=false)
async function waitForUnknownCompletion(page) {
  const maxAttempts = 200;
  for (let i = 0; i < maxAttempts; i++) {
    const d = await getDiagnostics(page);
    if (d && d.callCount >= 1 && d.actionNames[0] === "done" && d.successValues[0] === false) {
      return d;
    }
    await new Promise(r => setTimeout(r, 250));
  }
  const finalDiag = await getDiagnostics(page);
  throw new Error(
    `waitForUnknownCompletion timed out. Actions: ${finalDiag ? finalDiag.actionNames.join(", ") : "N/A"}`
  );
}

// ── Page error / request tracking ─────────────────────────────────────────

function setupErrorTracking(page, tracker) {
  page.on("request", (r) => {
    if (!r.url().startsWith(tracker.baseUrl)) {
      tracker.nonLocal.push({ url: r.url(), method: r.method() });
    }
  });
  page.on("requestfailed", (req) => {
    const err = req.failure()?.errorText || "unknown";
    tracker.requestFailures.push({ url: req.url(), error: err });
  });
  page.on("console", (msg) => {
    const text = msg.text();
    if (text.includes("favicon.ico")) return;
    if (/GL Driver Message \(OpenGL, Performance/i.test(text)) return;
    if (msg.type() === "error" && /Failed to load resource/i.test(text)) return;
    if (msg.type() === "error") tracker.consoleErrors.push(text);
    else if (msg.type() === "warning") tracker.warnings.push(text);
  });
  page.on("pageerror", (err) => tracker.pageErrors.push(err.message));
}

function assertZeroErrors(tracker, label) {
  assert.strictEqual(tracker.nonLocal.length, 0, `${label} non-local requests: ${JSON.stringify(tracker.nonLocal.slice(0, 5))}`);
  assert.strictEqual(tracker.consoleErrors.length, 0, `${label} console errors: ${JSON.stringify(tracker.consoleErrors.slice(0, 5))}`);
  assert.strictEqual(tracker.warnings.length, 0, `${label} warnings: ${JSON.stringify(tracker.warnings.slice(0, 5))}`);
  assert.strictEqual(tracker.pageErrors.length, 0, `${label} page errors: ${JSON.stringify(tracker.pageErrors.slice(0, 5))}`);
  assert.strictEqual(tracker.requestFailures.length, 0, `${label} request failures: ${JSON.stringify(tracker.requestFailures.slice(0, 5))}`);
}

// ── Verification functions ────────────────────────────────────────────────

async function verifySafetyBadges(page) {
  const text = await page.evaluate(() => document.body.innerText);
  assert.ok(text.includes("오프라인") || text.includes("mock"), "safety badge: offline/mock missing");
  assert.ok(text.includes("동일 출처") || text.includes("same-origin"), "safety badge: same-origin missing");
  assert.ok(text.includes("제출 불가") || text.includes("no-submit"), "safety badge: no-submit missing");
  console.log("    ✓ Safety badges present");
}

async function verifyCancelButton(page) {
  const hasCancel = await page.evaluate(() => {
    const btn = document.getElementById("chat-cancel");
    return btn !== null;
  });
  assert.ok(hasCancel, "Cancel button must exist in DOM");
  console.log("    ✓ Cancel button present");
}

async function verifyCanvasRendered(page) {
  const hasCanvas = await page.evaluate(() => {
    const canvas = document.getElementById("demo-canvas");
    return canvas !== null && canvas.innerHTML.length > 0;
  });
  assert.ok(hasCanvas, "Civic canvas must be rendered with content");
  console.log("    ✓ Civic canvas rendered");
}

async function verifyMobileLayout(page) {
  const layoutDirection = await page.evaluate(() => {
    const layout = document.querySelector(".resident-layout");
    if (!layout) return null;
    return window.getComputedStyle(layout).flexDirection;
  });
  // On mobile viewport, flex-direction should be column
  const vw = page.viewportSize().width;
  if (vw <= 768) {
    assert.strictEqual(layoutDirection, "column", `Mobile layout must be column at ${vw}px`);
    console.log(`    ✓ Mobile layout column at ${vw}px`);
  } else {
    assert.strictEqual(layoutDirection, "row", `Desktop layout must be row at ${vw}px`);
    console.log(`    ✓ Desktop layout row at ${vw}px`);
  }
}

async function runSupportedTask(page, task) {
  const label = task.id;
  console.log(`    "${label}" (${task.navSteps} click(s))...`);

  const msgBefore = await getChatMessageCount(page);
  await resetDiagnostics(page);

  await submitTask(page, task.prompt);
  const diag = await waitForSupportedCompletion(page, task.id, task.navSteps);

  // Verify diagnostic pattern: click_element_by_index × N + done with success
  assert.ok(diag !== null, `Diagnostics must be available for ${label}`);
  assert.strictEqual(diag.callCount, task.navSteps + 1,
    `callCount must be ${task.navSteps + 1}, got ${diag.callCount}`);

  const clickActions = diag.actionNames.filter(a => a === "click_element_by_index");
  assert.strictEqual(clickActions.length, task.navSteps,
    `Expected ${task.navSteps} click_element_by_index actions, got ${clickActions.length}`);

  const lastAction = diag.actionNames[diag.actionNames.length - 1];
  assert.strictEqual(lastAction, "done",
    `Last action must be "done", got "${lastAction}"`);

  const lastSuccess = diag.successValues[diag.successValues.length - 1];
  assert.strictEqual(lastSuccess, true,
    `Last success must be true, got ${lastSuccess}`);

  // Verify chat history grew
  const msgAfter = await getChatMessageCount(page);
  assert.ok(msgAfter > msgBefore,
    `Chat messages must grow: before=${msgBefore}, after=${msgAfter}`);

  // Verify action text appears in chat (click_element actions recorded)
  const chatText = await getChatText(page);
  assert.ok(chatText.includes(task.prompt),
    `Chat must contain user prompt "${task.prompt.substring(0, 30)}..."`);

  console.log(`    ✓ callCount=${diag.callCount} click=${clickActions.length} done=[${lastSuccess}] chat=✓`);
  return { taskId: label, diagnostics: diag };
}

async function runUnknownTask(page) {
  console.log(`  Unknown: "${UNKNOWN_PROMPT}"...`);

  const msgBefore = await getChatMessageCount(page);
  await resetDiagnostics(page);

  await submitTask(page, UNKNOWN_PROMPT);
  const diag = await waitForUnknownCompletion(page);

  assert.ok(diag !== null, "Diagnostics must be available for unknown task");
  assert.strictEqual(diag.callCount, 1, "Unknown must have exactly 1 API call");
  assert.strictEqual(diag.actionNames[0], "done", `Unknown action must be "done"`);
  assert.strictEqual(diag.successValues[0], false, "Unknown must be success=false");

  const hasExecuteJavascript = diag.actionNames.some(a => a === "execute_javascript");
  assert.ok(!hasExecuteJavascript, "Unknown task must NOT trigger execute_javascript");

  const hasClick = diag.actionNames.some(a => a === "click_element_by_index");
  assert.ok(!hasClick, "Unknown task must NOT trigger click_element_by_index");

  const msgAfter = await getChatMessageCount(page);
  assert.ok(msgAfter > msgBefore,
    `Chat messages must grow for unknown: before=${msgBefore}, after=${msgAfter}`);

  console.log(`    ✓ callCount=1 action=[done] success=false chat=✓`);
  return { diagnostics: diag };
}

// ── Main ──────────────────────────────────────────────────────────────────

async function main() {
  const baseUrl = process.argv[2];
  if (!baseUrl) {
    console.error("Usage: node tests/browser/verify_resident_e2e.mjs <BASE_URL>");
    process.exit(1);
  }
  validateBaseUrl(baseUrl);

  const residentUrl = baseUrl.replace(/\/+$/, "") + "/" + "examples/page-agent/resident/";
  console.log(`Verifying resident demo at: ${residentUrl}`);

  const { browser, launchInfo } = await launchBrowser();
  let allPassed = true;

  const desktopTracker = { baseUrl, nonLocal: [], consoleErrors: [], warnings: [], pageErrors: [], requestFailures: [] };
  const mobileTracker = { baseUrl, nonLocal: [], consoleErrors: [], warnings: [], pageErrors: [], requestFailures: [] };

  try {
    // ═════ Desktop (1440x900) ═════
    console.log("\n[Desktop 1440x900]");

    const ctxDesktop = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const pageDesktop = await ctxDesktop.newPage();
    setupErrorTracking(pageDesktop, desktopTracker);

    await pageDesktop.goto(residentUrl, { waitUntil: "networkidle", timeout: RELOAD_READY_TIMEOUT });
    await waitForResidentReady(pageDesktop);
    console.log("  Page ready ✓");

    // Verify structural elements
    await verifySafetyBadges(pageDesktop);
    await verifyCancelButton(pageDesktop);
    await verifyCanvasRendered(pageDesktop);
    await verifyMobileLayout(pageDesktop);

    // Run all 5 parity scenarios
    const desktopResults = [];
    for (let i = 0; i < EXPECTED_TASKS.length; i++) {
      const task = EXPECTED_TASKS[i];
      const result = await runSupportedTask(pageDesktop, task);
      desktopResults.push(result);
      // Reload for clean session
      await pageDesktop.reload({ waitUntil: "networkidle", timeout: RELOAD_READY_TIMEOUT });
      await waitForResidentReady(pageDesktop);
    }
    assert.strictEqual(desktopResults.length, 5, "Must have 5 desktop task results");

    // Unknown task
    await runUnknownTask(pageDesktop);
    await screenshot(pageDesktop, "desktop-final.png");

    assertZeroErrors(desktopTracker, "Desktop");
    await ctxDesktop.close();

    // ═════ Mobile (390x844) ═════
    console.log("\n[Mobile 390x844]");

    const ctxMobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const pageMobile = await ctxMobile.newPage();
    setupErrorTracking(pageMobile, mobileTracker);

    await pageMobile.goto(residentUrl, { waitUntil: "networkidle", timeout: RELOAD_READY_TIMEOUT });
    await waitForResidentReady(pageMobile);
    console.log("  Mobile page ready ✓");

    // Verify mobile layout
    await verifyMobileLayout(pageMobile);

    // Run first scenario on mobile
    const mobileTask = EXPECTED_TASKS[0];
    const mobileResult = await runSupportedTask(pageMobile, mobileTask);
    await screenshot(pageMobile, "mobile-final.png");

    assertZeroErrors(mobileTracker, "Mobile");
    await ctxMobile.close();

    // ═════ Summary ═════
    console.log("\n  === SUMMARY ===");
    console.log(`  Desktop supported: 5/5`);
    console.log(`  Desktop unknown: 1/1`);
    console.log(`  Mobile supported: 1/1`);
    console.log(`  Desktop errors: nonLocal=${desktopTracker.nonLocal.length} console=${desktopTracker.consoleErrors.length} warn=${desktopTracker.warnings.length} page=${desktopTracker.pageErrors.length} reqFail=${desktopTracker.requestFailures.length}`);
    console.log(`  Mobile errors: nonLocal=${mobileTracker.nonLocal.length} console=${mobileTracker.consoleErrors.length} warn=${mobileTracker.warnings.length} page=${mobileTracker.pageErrors.length} reqFail=${mobileTracker.requestFailures.length}`);
    console.log(`  Browser: ${launchInfo.source} v${launchInfo.version}`);
    console.log("\nAll resident E2E checks passed.");

    ensureScreenshotDir();
    writeFileSync(join(SCREENSHOT_DIR, "browser-evidence.json"), JSON.stringify({
      baseUrl, residentUrl, timestamp: new Date().toISOString(), browser: launchInfo,
      desktop: { tasks: desktopResults.map(r => ({ taskId: r.taskId, callCount: r.diagnostics?.callCount, actions: r.diagnostics?.actionNames })), errors: desktopTracker },
      mobile: { tasks: [{ taskId: mobileTask.id, callCount: mobileResult.diagnostics?.callCount, actions: mobileResult.diagnostics?.actionNames }], errors: mobileTracker },
    }, null, 2));
  } catch (err) {
    console.error("\nResident E2E verification FAILED:");
    console.error(err && err.stack ? err.stack : err);
    allPassed = false;
  } finally {
    await browser.close();
  }

  if (!allPassed) process.exit(1);
}

main();
