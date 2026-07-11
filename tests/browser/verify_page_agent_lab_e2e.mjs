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

const EXPECTED_UNSUPPORTED_TEXT =
  "I can only help with the following topics on this page";

// ── Known browser executable paths for fallback ──────────────────────────

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

// ── Panel selectors (built-in PageAgent Panel DOM) ───────────────────────
// These are the actual DOM selectors observed from the vendored IIFE bundle.
// The Panel renders a <div class="panel-container"> root with nested
// structure containing textarea, message list, and status elements.

const PANEL_INPUT_SELECTORS = [
  "div.panel-container textarea",
  "textarea.page-agent-panel-input",
  "#pageAgentPanel textarea",
  "div[class*='page-agent'] textarea[placeholder]",
  "div[class*='panel'] textarea",
];

const PANEL_ROOT_SELECTORS = [
  "div.panel-container",
  "#pageAgentPanel",
  "div[class*='page-agent-panel']",
  "div[class*='panel-container']",
];

const PANEL_MESSAGE_SELECTORS = [
  "div.panel-container div[class*='message']",
  "div.panel-container div[class*='chat-item']",
  "div.panel-container div[class*='history-item']",
];

const PANEL_STATUS_SELECTORS = [
  "div.panel-container div[class*='status']",
  "div.panel-container div[class*='loading']",
  "div.panel-container div[aria-live]",
];

// ── Helpers ──────────────────────────────────────────────────────────────

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

// ── Browser launch with progressive fallback (no Firefox) ────────────────

async function findChromeExecutable() {
  // Check PAGE_AGENT_BROWSER_EXECUTABLE env var first
  const envPath = process.env.PAGE_AGENT_BROWSER_EXECUTABLE;
  if (envPath) {
    try {
      readFileSync(envPath);
      return { source: "env", executable: envPath };
    } catch (_) {
      // env path invalid, continue
    }
  }

  // Check known system paths
  for (const p of KNOWN_BROWSER_PATHS) {
    try {
      readFileSync(p);
      return { source: "known-path", executable: p };
    } catch (_) {
      // not found, continue
    }
  }

  return null;
}

async function launchBrowser() {
  const launchAttempts = [];
  const errors = [];

  // Strategy 1: env variable
  const envPath = process.env.PAGE_AGENT_BROWSER_EXECUTABLE;
  if (envPath) {
    launchAttempts.push({
      name: `env: ${envPath}`,
      launch: () => chromium.launch({ headless: true, executablePath: envPath }),
    });
  }

  // Strategy 2: chrome channel (system Chrome via Playwright)
  launchAttempts.push({
    name: "channel: chrome",
    launch: () => chromium.launch({ headless: true, channel: "chrome" }),
  });

  // Strategy 3: known system paths
  for (const p of KNOWN_BROWSER_PATHS) {
    let exists = false;
    try {
      readFileSync(p);
      exists = true;
    } catch (_) {}
    if (exists) {
      launchAttempts.push({
        name: `path: ${p}`,
        launch: () => chromium.launch({ headless: true, executablePath: p }),
      });
    }
  }

  // Strategy 4: default Playwright Chromium (bundled)
  launchAttempts.push({
    name: "default playwright chromium",
    launch: () => chromium.launch({ headless: true }),
  });

  for (const attempt of launchAttempts) {
    try {
      const browser = await attempt.launch();
      const version =
        browser.version && typeof browser.version === "function"
          ? await browser.version().catch(() => "unknown")
          : "unknown";
      console.log(`  Browser launched (${attempt.name}, v${version}) ✓`);
      return { browser, launchInfo: { source: attempt.name, version } };
    } catch (e) {
      errors.push(`  [${attempt.name}] ${e.message}`);
    }
  }

  throw new Error(
    `Cannot launch any browser. Attempts:\n${errors.join("\n")}`
  );
}

// ── Task constants ──────────────────────────────────────────────────────

const SUPPORTED_TASKS = [
  { id: "quick-start", prompt: "Show the Quick Start section.", sectionId: "quick-start" },
  { id: "vs-browser-use", prompt: "Compare page-agent with browser-use.", sectionId: "vs-browser-use" },
  { id: "license", prompt: "Show the MIT license section.", sectionId: "license" },
  { id: "architecture", prompt: "Find the custom UI architecture.", sectionId: "architecture" },
];

const UNKNOWN_TASK = { id: "unknown", prompt: "What is the weather today?" };

// ── DOM interaction helpers ─────────────────────────────────────────────

async function getPanelInputHandle(page) {
  for (const sel of PANEL_INPUT_SELECTORS) {
    const el = await page.$(sel);
    if (el) return el;
  }
  return null;
}

async function getPanelRoot(page) {
  for (const sel of PANEL_ROOT_SELECTORS) {
    const el = await page.$(sel);
    if (el) return el;
  }
  return null;
}

async function getPanelMessageElements(page) {
  for (const sel of PANEL_MESSAGE_SELECTORS) {
    const els = await page.$$(sel);
    if (els && els.length > 0) return els;
  }
  return [];
}

async function getPanelStatusElements(page) {
  for (const sel of PANEL_STATUS_SELECTORS) {
    const els = await page.$$(sel);
    if (els && els.length > 0) return els;
  }
  return [];
}

async function getPanelRootText(page) {
  return page.evaluate(() => {
    const roots = [
      document.querySelector("div.panel-container"),
      document.querySelector("#pageAgentPanel"),
      document.querySelector("[class*='page-agent-panel']"),
      document.querySelector("[class*='panel-container']"),
    ];
    for (const r of roots) {
      if (r && r.textContent) return r.textContent;
    }
    return "";
  });
}

async function submitTaskViaPanel(page, prompt) {
  const input = await getPanelInputHandle(page);
  assert.ok(
    input,
    `Panel textarea not found in DOM — cannot submit task: "${prompt}". PageAgent Panel may not be rendered.`
  );
  await input.click();
  await input.fill(prompt);
  await page.evaluate((el) => {
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }, input);
  await page.waitForTimeout(300);
  await input.press("Enter");
}

// ── Diagnostics helpers ─────────────────────────────────────────────────

async function getDiagnostics(page) {
  return page.evaluate(() => {
    const m = window.PageAgentLabMockModel || window.PageAgentMockModel;
    if (!m || !m.getDiagnostics) return null;
    return m.getDiagnostics();
  });
}

async function resetDiagnostics(page) {
  await page.evaluate(() => {
    const m = window.PageAgentLabMockModel || window.PageAgentMockModel;
    if (m && m.resetDiagnostics) m.resetDiagnostics();
    else if (window.__pageAgentLabResetDiagnostics)
      window.__pageAgentLabResetDiagnostics();
  });
}

// ── Polling helpers ─────────────────────────────────────────────────────

const POLL_TIMEOUT_MS = 20000;
const POLL_INTERVAL_MS = 200;

async function waitForSupportedCompletion(page, taskId) {
  await page.waitForFunction(
    (tId) => {
      const m = window.PageAgentLabMockModel || window.PageAgentMockModel;
      if (!m || !m.getDiagnostics) return false;
      const d = m.getDiagnostics();
      return (
        d.callCount === 2 &&
        d.actionNames.length === 2 &&
        d.actionNames[0] === "execute_javascript" &&
        d.actionNames[1] === "done" &&
        d.taskIds[0] === tId
      );
    },
    taskId,
    { timeout: POLL_TIMEOUT_MS, polling: POLL_INTERVAL_MS }
  );
}

async function waitForUnknownCompletion(page) {
  await page.waitForFunction(
    () => {
      const m = window.PageAgentLabMockModel || window.PageAgentMockModel;
      if (!m || !m.getDiagnostics) return false;
      const d = m.getDiagnostics();
      return (
        d.callCount === 1 &&
        d.actionNames.length === 1 &&
        d.actionNames[0] === "done" &&
        d.taskIds[0] === null
      );
    },
    { timeout: POLL_TIMEOUT_MS, polling: POLL_INTERVAL_MS }
  );
}

// ── Scroll / marker verification ───────────────────────────────────────

async function moveTargetOutsideViewport(page, sectionId, viewportHeight) {
  // Check if target is currently in viewport; if so, scroll to the opposite extreme
  const state = await page.evaluate(
    ({ sid }) => {
      const el = document.getElementById(sid);
      if (!el) return { inViewport: true, rectTop: 0 };
      const r = el.getBoundingClientRect();
      return {
        inViewport: r.top < window.innerHeight && r.bottom > 0,
        rectTop: r.top,
        docHeight: document.body.scrollHeight,
      };
    },
    { sid: sectionId }
  );

  if (state.inViewport) {
    // Scroll to opposite extreme based on section's position
    if (state.rectTop < viewportHeight / 2) {
      // Section is in upper half — scroll to bottom
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    } else {
      // Section is in lower half — scroll to top
      await page.evaluate(() => window.scrollTo(0, 0));
    }
    // Wait for scroll to settle
    await page.waitForTimeout(300);
  }
}

async function getSectionState(page, sectionId) {
  return page.evaluate(
    ({ sid }) => {
      const el = document.getElementById(sid);
      if (!el)
        return {
          scrollY: window.scrollY,
          rectTop: null,
          rectBottom: null,
          inViewport: false,
          exists: false,
        };
      const r = el.getBoundingClientRect();
      const inVp = r.top < window.innerHeight && r.bottom > 0;
      return {
        scrollY: window.scrollY,
        rectTop: r.top,
        rectBottom: r.bottom,
        inViewport: inVp,
        exists: true,
      };
    },
    { sid: sectionId }
  );
}

async function getMarkerState(page, sectionId) {
  return page.evaluate(
    ({ sid }) => {
      const el = document.getElementById(sid);
      if (!el)
        return {
          hasClass: false,
          hasAttribute: false,
          dataPageAgentTarget: null,
        };
      return {
        hasClass: el.classList.contains("page-agent-target-active"),
        hasAttribute: el.getAttribute("data-page-agent-target") === "active",
        dataPageAgentTarget: el.getAttribute("data-page-agent-target"),
      };
    },
    { sid: sectionId }
  );
}

// ── Panel verification ─────────────────────────────────────────────────

async function verifyPanelAfterSupportedTask(page, prompt, completionText) {
  // 1. Verify exact prompt appears in Panel root
  const panelText = await getPanelRootText(page);
  assert.ok(
    panelText.includes(prompt),
    `Panel root must contain the exact submitted prompt. Expected to include: "${prompt}"`
  );

  // 2. Verify history/message count increased
  const msgs = await getPanelMessageElements(page);
  assert.ok(
    msgs.length > 0,
    `Panel must have at least 1 message element after task submission (got ${msgs.length})`
  );

  // 3. Verify completion text appears in Panel root
  if (completionText) {
    assert.ok(
      panelText.includes(completionText),
      `Panel root must contain completion text. Expected to include: "${completionText.substring(0, 50)}..."`
    );
  }

  // 4. Verify no error status in panel
  const statusEls = await getPanelStatusElements(page);
  for (const el of statusEls) {
    const text = await el.textContent();
    assert.ok(
      !text.toLowerCase().includes("error"),
      `Panel must not contain error status: "${text}"`
    );
  }
}

async function verifyPanelAfterUnknownTask(page, prompt, unsupportedText) {
  // 1. Verify exact unknown prompt appears in Panel root
  const panelText = await getPanelRootText(page);
  assert.ok(
    panelText.includes(prompt),
    `Panel root must contain the exact unknown prompt. Expected to include: "${prompt}"`
  );

  // 2. Verify unsupported bounded text in Panel root
  assert.ok(
    panelText.includes(unsupportedText),
    `Panel root must contain unsupported bounded text. Expected to include: "${unsupportedText}"`
  );
}

// ── Run supported task ─────────────────────────────────────────────────

async function runSingleSupportedTask(page, task, viewportHeight) {
  const label = task.id;
  console.log(`    "${label}"...`);

  // ── Precondition: move target outside viewport ─────────────────────────
  const beforeState = await getSectionState(page, task.sectionId);
  if (beforeState.inViewport) {
    await moveTargetOutsideViewport(page, task.sectionId, viewportHeight);
  }
  const preconditionState = await getSectionState(page, task.sectionId);
  assert.ok(
    !preconditionState.inViewport,
    `Precondition: #${task.sectionId} must be outside viewport before task submission (top=${preconditionState.rectTop}, viewport=${viewportHeight})`
  );

  const beforeMarkers = await getMarkerState(page, task.sectionId);

  // Reset diagnostics
  await resetDiagnostics(page);

  // Record initial Panel message count
  const msgBefore = (await getPanelMessageElements(page)).length;

  // Submit via real Panel textarea
  await submitTaskViaPanel(page, task.prompt);

  // Wait for completion via polling
  await waitForSupportedCompletion(page, task.id);

  // ── Read diagnostics ──────────────────────────────────────────────────
  const diag = await getDiagnostics(page);
  assert.ok(diag !== null, `Diagnostics must be available for task ${task.id}`);

  // ── Verify exactly 2 calls with correct sequence ──────────────────────
  assert.strictEqual(
    diag.callCount, 2,
    `callCount must be 2 for "${task.id}", got ${diag.callCount}`
  );
  assert.deepStrictEqual(
    diag.actionNames, ["execute_javascript", "done"],
    `action sequence must be [execute_javascript, done], got [${diag.actionNames}]`
  );
  assert.deepStrictEqual(
    diag.taskIds, [task.id, task.id],
    `taskIds must be [${task.id}, ${task.id}], got [${diag.taskIds}]`
  );
  assert.deepStrictEqual(
    diag.successValues, [null, true],
    `successValues must be [null, true] for "${task.id}", got [${diag.successValues}]`
  );
  assert.strictEqual(
    diag.lastSuccess, true,
    `lastSuccess must be true for "${task.id}"`
  );

  // ── Verify completion text ────────────────────────────────────────────
  const taskDef = SUPPORTED_TASKS.find((t) => t.id === task.id);
  const taskObj =
    diag.completionTexts && diag.completionTexts.length === 2
      ? diag.completionTexts[1]
      : "";
  assert.ok(
    typeof taskObj === "string" && taskObj.length > 0,
    `completionTexts[1] must be a non-empty string for "${task.id}"`
  );

  // ── Verify scroll change (viewport + scrollY) ─────────────────────────
  const afterState = await getSectionState(page, task.sectionId);
  const afterMarkers = await getMarkerState(page, task.sectionId);

  assert.ok(
    afterState.inViewport,
    `After task, #${task.sectionId} must be within viewport (top=${afterState.rectTop}, bottom=${afterState.rectBottom}, viewport=${viewportHeight})`
  );
  assert.ok(
    Math.abs(afterState.rectTop - preconditionState.rectTop) > 5 ||
      Math.abs(afterState.scrollY - preconditionState.scrollY) > 5,
    `PageController must have scrolled. scrollY delta=${Math.abs(afterState.scrollY - preconditionState.scrollY)}, rectTop delta=${Math.abs(afterState.rectTop - preconditionState.rectTop)}`
  );

  // ── Verify visual marker ──────────────────────────────────────────────
  assert.ok(
    afterMarkers.hasClass,
    `#${task.sectionId} must have page-agent-target-active class after task`
  );
  assert.ok(
    afterMarkers.hasAttribute,
    `#${task.sectionId} must have data-page-agent-target='active' after task`
  );

  // ── Verify Panel history ──────────────────────────────────────────────
  const taskDefObj = SUPPORTED_TASKS.find((t) => t.id === task.id);
  const taskResponse = taskDefObj
    ? diag.completionTexts[1] || ""
    : "";
  await verifyPanelAfterSupportedTask(page, task.prompt, taskResponse);

  console.log(
    `    ✓ callCount=2 action=[exe_js, done] success=[null,true] ` +
      `scroll=✓ marker=✓ panel=✓ msgDelta=${(await getPanelMessageElements(page)).length - msgBefore}`
  );
  return { taskId: label, diagnostics: diag, beforeState: preconditionState, afterState };
}

// ── Run unknown task ───────────────────────────────────────────────────

async function runUnknownTask(page, task) {
  console.log(`  Unknown: "${task.prompt}"`);

  // ── Record before state ───────────────────────────────────────────────
  const beforeState = {
    scrollY: await page.evaluate(() => window.scrollY),
    sections: {},
    markers: {},
  };

  for (const t of SUPPORTED_TASKS) {
    beforeState.sections[t.sectionId] = await getSectionState(page, t.sectionId);
    beforeState.markers[t.sectionId] = await getMarkerState(page, t.sectionId);
  }

  // Record initial Panel message count
  const msgBefore = (await getPanelMessageElements(page)).length;

  // Reset diagnostics
  await resetDiagnostics(page);

  // Submit unknown task (exactly once)
  await submitTaskViaPanel(page, task.prompt);

  // Wait for completion via polling
  await waitForUnknownCompletion(page);

  // ── Verify diagnostics ────────────────────────────────────────────────
  const diag = await getDiagnostics(page);
  assert.ok(diag !== null, "Diagnostics must be available after unknown task");

  assert.strictEqual(diag.callCount, 1, "Unknown task must have exactly 1 API call");
  assert.deepStrictEqual(
    diag.actionNames, ["done"],
    `Unknown task actions must be ["done"], got [${diag.actionNames}]`
  );
  assert.deepStrictEqual(
    diag.taskIds, [null],
    `Unknown taskIds must be [null], got [${diag.taskIds}]`
  );
  assert.deepStrictEqual(
    diag.successValues, [false],
    `Unknown task successValues must be [false], got [${diag.successValues}]`
  );
  assert.strictEqual(diag.lastSuccess, false, "Unknown task lastSuccess must be false");

  // ── Verify completion text ────────────────────────────────────────────
  assert.ok(
    typeof diag.lastCompletionText === "string" && diag.lastCompletionText.length > 0,
    "lastCompletionText must be a non-empty string"
  );
  assert.ok(
    diag.lastCompletionText.includes(EXPECTED_UNSUPPORTED_TEXT),
    `lastCompletionText must contain unsupported text. Got: "${diag.lastCompletionText}"`
  );

  // ── Verify no scroll change (delta <= 3px) ────────────────────────────
  const afterScrollY = await page.evaluate(() => window.scrollY);
  const scrollDelta = Math.abs(afterScrollY - beforeState.scrollY);
  assert.ok(
    scrollDelta <= 3,
    `scrollY must not change after unknown task (delta=${scrollDelta}px, threshold=3px)`
  );

  // ── Verify no section movement (delta <= 3px) ─────────────────────────
  for (const t of SUPPORTED_TASKS) {
    const afterSection = await getSectionState(page, t.sectionId);
    if (beforeState.sections[t.sectionId] && beforeState.sections[t.sectionId].exists) {
      const beforeTop = beforeState.sections[t.sectionId].rectTop;
      const afterTop = afterSection.rectTop;
      if (beforeTop !== null && afterTop !== null) {
        const delta = Math.abs(afterTop - beforeTop);
        assert.ok(
          delta <= 3,
          `Section #${t.sectionId} top must not change (delta=${delta}px, threshold=3px)`
        );
      }
    }
  }

  // ── Verify markers unchanged ──────────────────────────────────────────
  for (const t of SUPPORTED_TASKS) {
    const afterMarker = await getMarkerState(page, t.sectionId);
    assert.strictEqual(
      afterMarker.hasClass,
      beforeState.markers[t.sectionId].hasClass,
      `#${t.sectionId} marker class must not change after unknown task`
    );
    assert.strictEqual(
      afterMarker.dataPageAgentTarget,
      beforeState.markers[t.sectionId].dataPageAgentTarget,
      `#${t.sectionId} data-page-agent-target must not change after unknown task`
    );
  }

  // ── Verify no execute_javascript ──────────────────────────────────────
  assert.ok(
    !diag.actionNames.includes("execute_javascript"),
    "Unknown task must NOT trigger execute_javascript"
  );

  // ── Verify Panel shows unknown prompt + unsupported text ───────────────
  await verifyPanelAfterUnknownTask(page, task.prompt, EXPECTED_UNSUPPORTED_TEXT);

  console.log(
    `    ✓ callCount=1 action=[done] success=[false] scroll=0 panel=✓ ` +
      `msgDelta=${(await getPanelMessageElements(page)).length - msgBefore}`
  );
}

// ── Error tracking ─────────────────────────────────────────────────────

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
    if (msg.type() === "error") tracker.consoleErrors.push(text);
    else if (msg.type() === "warning") tracker.warnings.push(text);
  });
  page.on("pageerror", (err) => tracker.pageErrors.push(err.message));
  page.on("requestfailed", (req) => {
    const err = req.failure()?.errorText || "unknown";
    if (!req.url().includes("favicon"))
      tracker.requestFailures.push({ url: req.url(), error: err });
  });
}

function assertZeroErrors(tracker, label) {
  assert.strictEqual(
    tracker.nonLocal.length, 0,
    `${label} non-local requests: ${JSON.stringify(tracker.nonLocal.slice(0, 5))}`
  );
  assert.strictEqual(
    tracker.consoleErrors.length, 0,
    `${label} console errors: ${JSON.stringify(tracker.consoleErrors.slice(0, 5))}`
  );
  assert.strictEqual(
    tracker.warnings.length, 0,
    `${label} warnings: ${JSON.stringify(tracker.warnings.slice(0, 5))}`
  );
  assert.strictEqual(
    tracker.pageErrors.length, 0,
    `${label} page errors: ${JSON.stringify(tracker.pageErrors.slice(0, 5))}`
  );
  assert.strictEqual(
    tracker.requestFailures.length, 0,
    `${label} request failures: ${JSON.stringify(tracker.requestFailures.slice(0, 5))}`
  );
}

// ── Main ────────────────────────────────────────────────────────────────

async function main() {
  const baseUrl = process.argv[2];
  if (!baseUrl) {
    console.error("Usage: node verify_page_agent_lab_e2e.mjs <BASE_URL>");
    process.exit(1);
  }
  validateBaseUrl(baseUrl);

  const labUrl = baseUrl.replace(/\/+$/, "") + "/examples/page-agent/";
  console.log(`Verifying Page Agent lab at: ${labUrl}`);

  const { browser, launchInfo } = await launchBrowser();
  let allPassed = true;
  let desktopCtx, mobileCtx;

  // Separate error trackers per viewport
  const desktopTracker = {
    baseUrl,
    nonLocal: [],
    consoleErrors: [],
    warnings: [],
    pageErrors: [],
    requestFailures: [],
  };

  const mobileTracker = {
    baseUrl,
    nonLocal: [],
    consoleErrors: [],
    warnings: [],
    pageErrors: [],
    requestFailures: [],
  };

  const browserEvidence = {
    browser: launchInfo,
    desktop: { tasks: [] },
    mobile: { tasks: [] },
  };

  try {
    // ═══════════════════ Desktop (1440x900) ═══════════════════
    console.log("\n[Desktop 1440x900]");
    desktopCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const dp = await desktopCtx.newPage();
    setupErrorTracking(dp, desktopTracker);

    await dp.goto(labUrl, { waitUntil: "networkidle", timeout: 20000 });
    await screenshot(dp, "desktop-initial.png");

    // Verify Panel initialization
    const labState = await dp.evaluate(() => {
      const lab = window.__PAGE_AGENT_LAB__;
      return lab
        ? { ok: true, integration: lab.integration, panel: lab.panel }
        : { ok: false };
    });
    assert.ok(labState.ok, "window.__PAGE_AGENT_LAB__ must be defined");
    assert.strictEqual(
      labState.integration, "actual-page-agent",
      "must be actual PageAgent runtime"
    );
    assert.strictEqual(labState.panel, "built-in", "must use built-in Panel");
    console.log("  Panel initialized (built-in) ✓");

    // Verify Panel textarea exists
    const panelInput = await getPanelInputHandle(dp);
    assert.ok(
      panelInput,
      "Panel textarea must be present in DOM. Hard requirement."
    );
    console.log("  Panel textarea found ✓");

    // ── Run 3 supported tasks ──────────────────────────────────────────
    const desktopResults = [];
    for (let i = 0; i < 3; i++) {
      const task = SUPPORTED_TASKS[i];
      const result = await runSingleSupportedTask(dp, task, 900);
      desktopResults.push(result);
      browserEvidence.desktop.tasks.push({
        taskId: task.id,
        callCount: result.diagnostics?.callCount,
        actions: result.diagnostics?.actionNames,
        successValues: result.diagnostics?.successValues,
        lastSuccess: result.diagnostics?.lastSuccess,
      });
    }

    assert.strictEqual(
      desktopResults.length, 3,
      "Must have 3 desktop task results"
    );

    // ── Run unknown task ───────────────────────────────────────────────
    await runUnknownTask(dp, UNKNOWN_TASK);

    await screenshot(dp, "desktop-final.png");

    // ── Desktop errors must be zero ────────────────────────────────────
    assertZeroErrors(desktopTracker, "Desktop");

    // ═══════════════════ Mobile (390x844) ═══════════════════
    console.log("\n[Mobile 390x844]");
    mobileCtx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const mp = await mobileCtx.newPage();
    setupErrorTracking(mp, mobileTracker);

    await mp.goto(labUrl, { waitUntil: "networkidle", timeout: 20000 });
    await screenshot(mp, "mobile-initial.png");

    // Verify Panel textarea exists on mobile
    const mobilePanelInput = await getPanelInputHandle(mp);
    assert.ok(
      mobilePanelInput,
      "Panel textarea must exist on mobile (hard requirement)"
    );
    console.log("  Mobile Panel textarea found ✓");

    // Run 1 supported task on mobile
    const mobileTask = SUPPORTED_TASKS[0];
    const mobileResult = await runSingleSupportedTask(mp, mobileTask, 844);
    browserEvidence.mobile.tasks.push({
      taskId: mobileTask.id,
      callCount: mobileResult.diagnostics?.callCount,
      actions: mobileResult.diagnostics?.actionNames,
      successValues: mobileResult.diagnostics?.successValues,
      lastSuccess: mobileResult.diagnostics?.lastSuccess,
    });

    await screenshot(mp, "mobile-final.png");

    // ── Mobile errors must be zero ─────────────────────────────────────
    assertZeroErrors(mobileTracker, "Mobile");

    // ═══════════════════ Summary ═══════════════════
    console.log("\n  === SUMMARY ===");
    console.log(`  Desktop supported: 3/3`);
    console.log(`  Desktop unknown: 1/1`);
    console.log(`  Mobile supported: 1/1`);
    console.log(
      `  Desktop errors: nonLocal=${desktopTracker.nonLocal.length} ` +
        `console=${desktopTracker.consoleErrors.length} ` +
        `warn=${desktopTracker.warnings.length} ` +
        `page=${desktopTracker.pageErrors.length} ` +
        `reqFail=${desktopTracker.requestFailures.length}`
    );
    console.log(
      `  Mobile errors: nonLocal=${mobileTracker.nonLocal.length} ` +
        `console=${mobileTracker.consoleErrors.length} ` +
        `warn=${mobileTracker.warnings.length} ` +
        `page=${mobileTracker.pageErrors.length} ` +
        `reqFail=${mobileTracker.requestFailures.length}`
    );
    console.log(`  Browser: ${launchInfo.source} v${launchInfo.version}`);
    console.log("\nAll Page Agent lab E2E checks passed.");

    // Save evidence
    ensureScreenshotDir();
    writeFileSync(
      join(SCREENSHOT_DIR, "browser-evidence.json"),
      JSON.stringify(
        {
          baseUrl,
          labUrl,
          timestamp: new Date().toISOString(),
          browser: launchInfo,
          desktop: {
            tasks: browserEvidence.desktop.tasks,
            errors: desktopTracker,
          },
          mobile: {
            tasks: browserEvidence.mobile.tasks,
            errors: mobileTracker,
          },
        },
        null,
        2
      )
    );
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
