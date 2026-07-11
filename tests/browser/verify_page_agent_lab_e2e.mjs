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
// FAILS IMMEDIATELY if the Panel input is not found (no fallback).

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

const UNIQUE_MARKER = "Local interoperability experiment";
const RELOAD_READY_TIMEOUT = 20000;

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

// ── Panel DOM helpers ────────────────────────────────────────────────────
// The vendored IIFE bundle uses CSS-module hashed class names (e.g.
// _taskInput_1tu05_573).  Built-in Panel root: #page-agent-runtime_agent-panel.
// Input element is <input type="text"> (NOT a textarea) — so we target it
// via attribute selector which works regardless of CSS module hashing.

const PANEL_ROOT_SELECTOR = "#page-agent-runtime_agent-panel";

async function getPanelInputHandle(page) {
  return page.locator(`${PANEL_ROOT_SELECTOR} input[type="text"]`).first();
}

async function getPanelRootText(page) {
  return page.evaluate(() => {
    const panelRoot = document.querySelector("#page-agent-runtime_agent-panel");
    if (panelRoot && panelRoot.textContent) return panelRoot.textContent;
    for (const el of document.querySelectorAll("[class*='panel']")) {
      if (el.textContent && el.textContent.includes("Page Agent")) return el.textContent;
    }
    return "";
  });
}

async function getPanelMessageElementCount(page) {
  return page.evaluate(() => {
    const root = document.querySelector("#page-agent-runtime_agent-panel");
    if (!root) return 0;
    let count = 0;
    const all = root.querySelectorAll("*");
    for (const el of all) {
      if (el.className && typeof el.className === "string") {
        const cn = el.className.toLowerCase();
        if (cn.includes("history") || cn.includes("message") || cn.includes("chat") || cn.includes("item")) {
          count++;
        }
      }
    }
    return count;
  });
}

async function getPanelStatusTexts(page) {
  return page.evaluate(() => {
    const root = document.querySelector("#page-agent-runtime_agent-panel");
    if (!root) return [];
    const texts = [];
    const all = root.querySelectorAll("*");
    for (const el of all) {
      if (el.className && typeof el.className === "string") {
        const cn = el.className.toLowerCase();
        if (cn.includes("status") || cn.includes("indicator") || cn.includes("loading") || cn.includes("thinking")) {
          if (el.textContent && el.textContent.trim()) {
            texts.push(el.textContent.trim());
          }
        }
      }
    }
    return texts;
  });
}

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
      try {
        if (browser && typeof browser.version === "function") {
          version = browser.version();
        }
      } catch (_) {
        version = "unknown";
      }
      console.log(`  Browser launched (${attempt.name}, v${version}) ✓`);
      return { browser, launchInfo: { source: attempt.name, version } };
    } catch (e) {
      errors.push(`  [${attempt.name}] ${e.message}`);
    }
  }

  throw new Error(`Cannot launch any browser. Attempts:\n${errors.join("\n")}`);
}

// ── Task constants ──────────────────────────────────────────────────────

const SUPPORTED_TASKS = [
  { id: "quick-start", prompt: "Show the Quick Start section.", sectionId: "quick-start" },
  { id: "vs-browser-use", prompt: "Compare page-agent with browser-use.", sectionId: "vs-browser-use" },
  { id: "license", prompt: "Show the MIT license section.", sectionId: "license" },
  { id: "architecture", prompt: "Find the custom UI architecture.", sectionId: "architecture" },
];

const UNKNOWN_TASK = { id: "unknown", prompt: "What is the weather today?" };

async function submitTaskViaPanel(page, prompt) {
  // Use page.evaluate to ensure the browser-native events fire correctly.
  // Playwright's locator.fill() + press("Enter") may not trigger custom
  // React/VanillaJS event handlers that the PageAgent Panel uses.
  const submitted = await page.evaluate((p) => {
    const root = document.querySelector("#page-agent-runtime_agent-panel");
    if (!root) return false;
    const input = root.querySelector('input[type="text"]');
    if (!input) return false;
    // Set the value directly
    const nativeSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, "value"
    ).set;
    nativeSetter.call(input, p);
    // Dispatch input event
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    // Focus and press Enter. preventScroll avoids the browser auto-scrolling
    // the document to reveal the Panel input (a test artifact, not agent
    // behavior) which would otherwise break the unknown-task "no movement"
    // assertion.
    input.focus({ preventScroll: true });
    input.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true, cancelable: true })
    );
    input.dispatchEvent(
      new KeyboardEvent("keyup", { key: "Enter", code: "Enter", bubbles: true, cancelable: true })
    );
    return true;
  }, prompt);
  assert.ok(submitted, `Panel input not found, cannot submit: "${prompt}"`);
  await page.waitForTimeout(100);
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

// ── Session isolation via page.reload() ────────────────────────────────
// Each task runs as an independent Page Agent session by reloading the
// same page and re-acquiring every Locator / handle afterwards.  The
// vendored Page Agent runtime keeps ALL conversation + diagnostic state
// in memory only (no localStorage / sessionStorage usage in the IIFE
// bundle), so a full reload resets it completely — preventing a previous
// task's ID from leaking into the next task's diagnostics.

async function waitForLabReady(page) {
  // 1. document.readyState === "complete"
  await page.waitForFunction(
    () => document.readyState === "complete",
    { timeout: RELOAD_READY_TIMEOUT }
  );

  // 2. Page Agent unique marker ("Local interoperability experiment")
  await page.waitForFunction(
    (marker) => document.body.innerText.includes(marker),
    UNIQUE_MARKER,
    { timeout: RELOAD_READY_TIMEOUT }
  );

  // 3. built-in Panel root exists
  await page.waitForSelector(PANEL_ROOT_SELECTOR, {
    state: "attached",
    timeout: RELOAD_READY_TIMEOUT,
  });

  // 4. Panel input visible + enabled
  const inputLocator = page
    .locator(`${PANEL_ROOT_SELECTOR} input[type="text"]`)
    .first();
  await inputLocator.waitFor({ state: "visible", timeout: RELOAD_READY_TIMEOUT });

  // 5. Verify lab initialization (actual PageAgent + built-in Panel)
  const labState = await page.evaluate(() => {
    const lab = window.__PAGE_AGENT_LAB__;
    return lab
      ? { ok: true, integration: lab.integration, panel: lab.panel }
      : { ok: false };
  });
  if (!labState.ok)
    throw new Error("window.__PAGE_AGENT_LAB__ must be defined");
  if (labState.integration !== "actual-page-agent")
    throw new Error("must be actual PageAgent runtime");
  if (labState.panel !== "built-in")
    throw new Error("must use built-in Panel");

  // 6. mock diagnostics API exists
  const hasDiag = await page.evaluate(() => {
    const m = window.PageAgentLabMockModel || window.PageAgentMockModel;
    return !!(m && m.getDiagnostics && m.resetDiagnostics);
  });
  if (!hasDiag)
    throw new Error("mock diagnostics API must exist");

  // 7. reset diagnostics + verify empty
  await page.evaluate(() => {
    const m = window.PageAgentLabMockModel || window.PageAgentMockModel;
    if (m && m.resetDiagnostics) m.resetDiagnostics();
  });
  const diagAfterReset = await page.evaluate(() => {
    const m = window.PageAgentLabMockModel || window.PageAgentMockModel;
    if (!m || !m.getDiagnostics) return null;
    return m.getDiagnostics();
  });
  if (diagAfterReset && diagAfterReset.callCount !== 0)
    throw new Error(
      `diagnostics must be empty, got callCount=${diagAfterReset.callCount}`
    );

  // Force a deterministic scroll baseline.  page.reload() restores the
  // previous scroll position (scroll restoration), which makes the
  // unknown-task "no movement" check flaky.  Reset to top with instant
  // behavior so every task session starts from a known position.
  await page.evaluate(() => {
    try { history.scrollRestoration = "manual"; } catch (_) {}
    const root = document.documentElement;
    const prev = root.style.scrollBehavior;
    root.style.scrollBehavior = "auto";
    window.scrollTo(0, 0);
    root.style.scrollBehavior = prev;
  });
}

// Create ONE page (one session) for a viewport.  Error listeners are
// registered exactly once per page via setupErrorTracking — reload does
// NOT re-register them.
async function createLabPage(browser, labUrl, viewport, tracker) {
  const ctx = await browser.newContext({
    viewport: { width: viewport.w, height: viewport.h },
  });
  const page = await ctx.newPage();
  setupErrorTracking(page, tracker);

  await page.goto(labUrl, {
    waitUntil: "networkidle",
    timeout: RELOAD_READY_TIMEOUT,
  });
  await waitForLabReady(page);
  return { ctx, page };
}

// Reload to start a fresh, isolated Page Agent session for the next task.
// All Locators / handles must be re-acquired after this (our helpers
// re-query the DOM via page.evaluate, so they are inherently reload-safe).
async function reloadLabPage(page, labUrl) {
  await page.reload({ waitUntil: "networkidle", timeout: RELOAD_READY_TIMEOUT });
  await waitForLabReady(page);
}

// ── Polling helpers (manual loop for verbose diagnostics) ──────────────

const POLL_TIMEOUT_MS = 30000;
const POLL_INTERVAL_MS = 200;

async function waitForSupportedCompletion(page, taskId) {
  let pollAttempts = 0;
  const maxAttempts = Math.ceil(POLL_TIMEOUT_MS / POLL_INTERVAL_MS);
  while (pollAttempts < maxAttempts) {
    const d = await page.evaluate(() => {
      const m = window.PageAgentLabMockModel || window.PageAgentMockModel;
      if (!m || !m.getDiagnostics) return null;
      return m.getDiagnostics();
    });
    if (d && d.callCount >= 2) {
      if (
        d.actionNames.length >= 2 &&
        d.actionNames[0] === "execute_javascript" &&
        d.actionNames[1] === "done" &&
        d.taskIds[0] === taskId
      ) {
        return;
      }
      console.log(`    waitForSupported: callCount=${d.callCount} actions=[${d.actionNames}] taskIds=[${d.taskIds}]`);
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
      pollAttempts++;
      continue;
    }
    if (pollAttempts > 0 && pollAttempts % 25 === 0) {
      const snap = d || { callCount: 0, actionNames: [], taskIds: [] };
      console.log(`    waitForSupported: [${pollAttempts}/${maxAttempts}] callCount=${snap.callCount} actions=[${snap.actionNames}]`);
    }
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    pollAttempts++;
  }
  const final = await page.evaluate(() => {
    const m = window.PageAgentLabMockModel || window.PageAgentMockModel;
    if (!m || !m.getDiagnostics) return null;
    return m.getDiagnostics();
  });
  throw new Error(
    `waitForSupportedCompletion timed out for "${taskId}" after ${POLL_TIMEOUT_MS}ms. ` +
    `Final diagnostics: ${JSON.stringify(final)}`
  );
}

async function waitForUnknownCompletion(page) {
  let pollAttempts = 0;
  const maxAttempts = Math.ceil(POLL_TIMEOUT_MS / POLL_INTERVAL_MS);
  while (pollAttempts < maxAttempts) {
    const d = await page.evaluate(() => {
      const m = window.PageAgentLabMockModel || window.PageAgentMockModel;
      if (!m || !m.getDiagnostics) return null;
      return m.getDiagnostics();
    });
    if (d && d.callCount >= 1) {
      if (
        d.actionNames.length >= 1 &&
        d.actionNames[0] === "done" &&
        d.taskIds[0] === null
      ) {
        return;
      }
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
      pollAttempts++;
      continue;
    }
    if (pollAttempts > 0 && pollAttempts % 25 === 0) {
      const snap = d || { callCount: 0, actionNames: [], taskIds: [] };
      console.log(`    waitForUnknown: [${pollAttempts}/${maxAttempts}] callCount=${snap.callCount} actions=[${snap.actionNames}]`);
    }
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    pollAttempts++;
  }
  const final = await page.evaluate(() => {
    const m = window.PageAgentLabMockModel || window.PageAgentMockModel;
    if (!m || !m.getDiagnostics) return null;
    return m.getDiagnostics();
  });
  throw new Error(
    `waitForUnknownCompletion timed out after ${POLL_TIMEOUT_MS}ms. Final diagnostics: ${JSON.stringify(final)}`
  );
}

// ── Scroll / marker verification ───────────────────────────────────────

async function moveTargetOutsideViewport(page, sectionId, viewportHeight) {
  const state = await page.evaluate(
    ({ sid }) => {
      const el = document.getElementById(sid);
      if (!el) return { inViewport: true, rectTop: 0 };
      const r = el.getBoundingClientRect();
      return { inViewport: r.top < window.innerHeight && r.bottom > 0, rectTop: r.top, docHeight: document.body.scrollHeight };
    },
    { sid: sectionId }
  );
  if (state.inViewport) {
    if (state.rectTop < viewportHeight / 2) {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    } else {
      await page.evaluate(() => window.scrollTo(0, 0));
    }
    await page.waitForTimeout(300);
  }
}

async function getSectionState(page, sectionId) {
  return page.evaluate(
    ({ sid }) => {
      const el = document.getElementById(sid);
      if (!el) return { scrollY: window.scrollY, rectTop: null, rectBottom: null, inViewport: false, exists: false };
      const r = el.getBoundingClientRect();
      return { scrollY: window.scrollY, rectTop: r.top, rectBottom: r.bottom, inViewport: r.top < window.innerHeight && r.bottom > 0, exists: true };
    },
    { sid: sectionId }
  );
}

async function getMarkerState(page, sectionId) {
  return page.evaluate(
    ({ sid }) => {
      const el = document.getElementById(sid);
      if (!el) return { hasClass: false, hasAttribute: false, dataPageAgentTarget: null };
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
  const panelText = await getPanelRootText(page);
  assert.ok(panelText.includes(prompt), `Panel root must contain the exact submitted prompt. Expected to include: "${prompt}"`);
  const msgCount = await getPanelMessageElementCount(page);
  assert.ok(msgCount > 0, `Panel must have at least 1 message element after task submission (got ${msgCount})`);
  if (completionText) {
    assert.ok(panelText.includes(completionText), `Panel root must contain completion text. Expected to include: "${completionText.substring(0, 50)}..."`);
  }
  const statusTexts = await getPanelStatusTexts(page);
  const forbiddenStates = ["error", "failed", "loading", "running", "processing", "thinking"];
  for (const st of statusTexts) {
    const lower = st.toLowerCase();
    for (const fs of forbiddenStates) {
      assert.ok(!lower.includes(fs), `Panel must not contain '${fs}' status: "${st}"`);
    }
  }
}

async function verifyPanelAfterUnknownTask(page, prompt, unsupportedText) {
  const panelText = await getPanelRootText(page);
  assert.ok(panelText.includes(prompt), `Panel root must contain the exact unknown prompt. Expected to include: "${prompt}"`);
  assert.ok(panelText.includes(unsupportedText), `Panel root must contain unsupported bounded text. Expected to include: "${unsupportedText}"`);
}

// ── Run supported task ─────────────────────────────────────────────────

async function runSingleSupportedTask(page, task, viewportHeight) {
  const label = task.id;
  console.log(`    "${label}"...`);

  const beforeState = await getSectionState(page, task.sectionId);
  if (beforeState.inViewport) {
    await moveTargetOutsideViewport(page, task.sectionId, viewportHeight);
  }
  const preconditionState = await getSectionState(page, task.sectionId);
  assert.ok(!preconditionState.inViewport, `Precondition: #${task.sectionId} must be outside viewport before task submission (top=${preconditionState.rectTop}, viewport=${viewportHeight})`);

  const beforeMarkers = await getMarkerState(page, task.sectionId);

  await resetDiagnostics(page);
  const msgBefore = await getPanelMessageElementCount(page);

  await submitTaskViaPanel(page, task.prompt);

  await waitForSupportedCompletion(page, task.id);

  const diag = await getDiagnostics(page);
  assert.ok(diag !== null, `Diagnostics must be available for task ${task.id}`);

  assert.strictEqual(diag.callCount, 2, `callCount must be 2 for "${task.id}", got ${diag.callCount}`);
  assert.strictEqual(diag.actionNames.length, 2, `action sequence must have length 2, got ${diag.actionNames.length}`);
  assert.strictEqual(diag.actionNames[0], "execute_javascript", `actionNames[0] must be "execute_javascript", got "${diag.actionNames[0]}"`);
  assert.strictEqual(diag.actionNames[1], "done", `actionNames[1] must be "done", got "${diag.actionNames[1]}"`);
  assert.strictEqual(diag.taskIds.length, 2, `taskIds must have length 2, got ${diag.taskIds.length}`);
  assert.strictEqual(diag.taskIds[0], task.id, `taskIds[0] must be "${task.id}", got "${diag.taskIds[0]}"`);
  assert.strictEqual(diag.taskIds[1], task.id, `taskIds[1] must be "${task.id}", got "${diag.taskIds[1]}"`);
  assert.strictEqual(diag.successValues.length, 2, `successValues must have length 2, got ${diag.successValues.length}`);
  assert.strictEqual(diag.successValues[0], null, `successValues[0] must be null, got ${diag.successValues[0]}`);
  assert.strictEqual(diag.successValues[1], true, `successValues[1] must be true, got ${diag.successValues[1]}`);
  assert.strictEqual(diag.lastSuccess, true, `lastSuccess must be true for "${task.id}"`);

  const taskObj = diag.completionTexts && diag.completionTexts.length === 2 ? diag.completionTexts[1] : "";
  assert.ok(typeof taskObj === "string" && taskObj.length > 0, `completionTexts[1] must be a non-empty string for "${task.id}"`);

  // Wait for smooth-scroll animation to complete (CSS scroll-behavior: smooth)
  await page.waitForTimeout(500);

  const afterState = await getSectionState(page, task.sectionId);
  const afterMarkers = await getMarkerState(page, task.sectionId);

  assert.ok(afterState.inViewport, `After task, #${task.sectionId} must be within viewport (top=${afterState.rectTop}, bottom=${afterState.rectBottom}, viewport=${viewportHeight})`);
  assert.ok(Math.abs(afterState.rectTop - preconditionState.rectTop) > 5 || Math.abs(afterState.scrollY - preconditionState.scrollY) > 5, `PageController must have scrolled. scrollY delta=${Math.abs(afterState.scrollY - preconditionState.scrollY)}, rectTop delta=${Math.abs(afterState.rectTop - preconditionState.rectTop)}`);
  assert.ok(afterMarkers.hasClass, `#${task.sectionId} must have page-agent-target-active class after task`);
  assert.ok(afterMarkers.hasAttribute, `#${task.sectionId} must have data-page-agent-target='active' after task`);

  const taskResponse = diag.completionTexts[1] || "";
  await verifyPanelAfterSupportedTask(page, task.prompt, taskResponse);

  const msgAfter = await getPanelMessageElementCount(page);
  assert.ok(msgAfter > msgBefore, `Panel history must grow for "${task.id}": before=${msgBefore}, after=${msgAfter}`);

  console.log(`    ✓ callCount=2 action=[exe_js, done] success=[null,true] scroll=✓ marker=✓ panel=✓ msgDelta=${msgAfter - msgBefore}`);
  return { taskId: label, diagnostics: diag, beforeState: preconditionState, afterState };
}

// ── Run unknown task ───────────────────────────────────────────────────

async function runUnknownTask(page, task) {
  console.log(`  Unknown: "${task.prompt}"`);

  const beforeState = { scrollY: await page.evaluate(() => window.scrollY), sections: {}, markers: {} };
  for (const t of SUPPORTED_TASKS) {
    beforeState.sections[t.sectionId] = await getSectionState(page, t.sectionId);
    beforeState.markers[t.sectionId] = await getMarkerState(page, t.sectionId);
  }

  const msgBefore = await getPanelMessageElementCount(page);
  await resetDiagnostics(page);
  await submitTaskViaPanel(page, task.prompt);
  await waitForUnknownCompletion(page);

  const diag = await getDiagnostics(page);
  assert.ok(diag !== null, "Diagnostics must be available after unknown task");
  assert.strictEqual(diag.callCount, 1, "Unknown task must have exactly 1 API call");
  assert.strictEqual(diag.actionNames.length, 1, "Unknown task must have exactly 1 action");
  assert.strictEqual(diag.actionNames[0], "done", `Unknown task action must be "done", got "${diag.actionNames[0]}"`);
  assert.strictEqual(diag.taskIds.length, 1, "Unknown task must have exactly 1 taskId");
  assert.strictEqual(diag.taskIds[0], null, `Unknown taskIds[0] must be null, got ${diag.taskIds[0]}`);
  assert.strictEqual(diag.successValues.length, 1, "Unknown task must have exactly 1 successValue");
  assert.strictEqual(diag.successValues[0], false, `Unknown task successValues[0] must be false, got ${diag.successValues[0]}`);
  assert.strictEqual(diag.lastSuccess, false, "Unknown task lastSuccess must be false");
  assert.ok(typeof diag.lastCompletionText === "string" && diag.lastCompletionText.length > 0, "lastCompletionText must be a non-empty string");
  assert.ok(diag.lastCompletionText.includes(EXPECTED_UNSUPPORTED_TEXT), `lastCompletionText must contain unsupported text. Got: "${diag.lastCompletionText}"`);

  const afterScrollY = await page.evaluate(() => window.scrollY);
  assert.ok(Math.abs(afterScrollY - beforeState.scrollY) <= 3, `scrollY must not change after unknown task (delta=${Math.abs(afterScrollY - beforeState.scrollY)}px, threshold=3px)`);

  for (const t of SUPPORTED_TASKS) {
    const afterSection = await getSectionState(page, t.sectionId);
    if (beforeState.sections[t.sectionId] && beforeState.sections[t.sectionId].exists) {
      const beforeTop = beforeState.sections[t.sectionId].rectTop;
      const afterTop = afterSection.rectTop;
      if (beforeTop !== null && afterTop !== null) {
        assert.ok(Math.abs(afterTop - beforeTop) <= 3, `Section #${t.sectionId} top must not change (delta=${Math.abs(afterTop - beforeTop)}px, threshold=3px)`);
      }
    }
  }

  for (const t of SUPPORTED_TASKS) {
    const afterMarker = await getMarkerState(page, t.sectionId);
    assert.strictEqual(afterMarker.hasClass, beforeState.markers[t.sectionId].hasClass, `#${t.sectionId} marker class must not change after unknown task`);
    assert.strictEqual(afterMarker.dataPageAgentTarget, beforeState.markers[t.sectionId].dataPageAgentTarget, `#${t.sectionId} data-page-agent-target must not change after unknown task`);
  }

  assert.ok(!diag.actionNames.includes("execute_javascript"), "Unknown task must NOT trigger execute_javascript");
  await verifyPanelAfterUnknownTask(page, task.prompt, EXPECTED_UNSUPPORTED_TEXT);

  const msgAfterUnknown = await getPanelMessageElementCount(page);
  assert.ok(msgAfterUnknown > msgBefore, `Panel history must grow for unknown task: before=${msgBefore}, after=${msgAfterUnknown}`);

  console.log(`    ✓ callCount=1 action=[done] success=[false] scroll=0 panel=✓ msgDelta=${msgAfterUnknown - msgBefore}`);
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
    // Skip harmless favicon 404 (browser default request, not from PageAgent)
    if (text.includes("favicon.ico")) return;
    // Chromium's GPU process emits WebGL GL driver performance diagnostics
    // (e.g. "[.WebGL-...]GL Driver Message (OpenGL, Performance, GL_CLOSE_PATH_NV,
    // High): GPU stall due to ReadPixels") as console warnings. These are
    // browser-generated, driver/GPU specific, and unrelated to the Page Agent,
    // so they must not fail the warning gate. Only the GL driver message
    // signature is excluded — genuine Page Agent/application warnings remain.
    if (/GL Driver Message \(OpenGL, Performance/i.test(text)) return;
    // The browser also logs a generic "Failed to load resource" message for
    // network 404s (e.g. the automatic favicon request). This is not a
    // PageAgent error, so exclude resource-load failures from the count.
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

// ── Main ────────────────────────────────────────────────────────────────

async function main() {
  const baseUrl = process.argv[2];
  if (!baseUrl) { console.error("Usage: node verify_page_agent_lab_e2e.mjs <BASE_URL>"); process.exit(1); }
  validateBaseUrl(baseUrl);

  const labUrl = baseUrl.replace(/\/+$/, "") + "/examples/page-agent/";
  console.log(`Verifying Page Agent lab at: ${labUrl}`);

  const { browser, launchInfo } = await launchBrowser();
  let allPassed = true;

  const desktopTracker = { baseUrl, nonLocal: [], consoleErrors: [], warnings: [], pageErrors: [], requestFailures: [] };
  const mobileTracker = { baseUrl, nonLocal: [], consoleErrors: [], warnings: [], pageErrors: [], requestFailures: [] };
  const browserEvidence = { browser: launchInfo, desktop: { tasks: [] }, mobile: { tasks: [] } };

  try {
    // ═════ Desktop (1440x900) ═════
    console.log("\n[Desktop 1440x900]");

    // ── Desktop supported tasks (each in a reloaded, isolated session) ──
    const { ctx: desktopCtx, page: desktopPage } = await createLabPage(
      browser, labUrl, { w: 1440, h: 900 }, desktopTracker
    );
    console.log(`  Desktop page ready ✓`);

    const desktopResults = [];
    for (let i = 0; i < 3; i++) {
      const task = SUPPORTED_TASKS[i];
      // Reload to start a brand-new Page Agent session so no prior
      // conversation / task ID can leak into this task's diagnostics.
      await reloadLabPage(desktopPage, labUrl);
      console.log(`  Task ${i + 1}: "${task.id}" — session reloaded ✓`);

      const result = await runSingleSupportedTask(desktopPage, task, 900);
      desktopResults.push(result);
      browserEvidence.desktop.tasks.push({
        taskId: task.id, callCount: result.diagnostics?.callCount,
        actions: result.diagnostics?.actionNames, successValues: result.diagnostics?.successValues, lastSuccess: result.diagnostics?.lastSuccess,
      });
    }
    assert.strictEqual(desktopResults.length, 3, "Must have 3 desktop task results");

    // ── Desktop unknown task (separate reload cycle) ──
    await reloadLabPage(desktopPage, labUrl);
    console.log(`  Unknown task — session reloaded ✓`);
    await runUnknownTask(desktopPage, UNKNOWN_TASK);
    await screenshot(desktopPage, "desktop-final.png");
    assertZeroErrors(desktopTracker, "Desktop");
    await desktopCtx.close();

    // ═════ Mobile (390x844) ═════
    console.log("\n[Mobile 390x844]");
    const { ctx: mobileCtxObj, page: mobilePage } = await createLabPage(
      browser, labUrl, { w: 390, h: 844 }, mobileTracker
    );
    console.log(`  Mobile page ready ✓`);
    await reloadLabPage(mobilePage, labUrl);
    console.log(`  Mobile — session reloaded ✓`);

    const mobileTask = SUPPORTED_TASKS[0];
    const mobileResult = await runSingleSupportedTask(mobilePage, mobileTask, 844);
    browserEvidence.mobile.tasks.push({
      taskId: mobileTask.id, callCount: mobileResult.diagnostics?.callCount,
      actions: mobileResult.diagnostics?.actionNames, successValues: mobileResult.diagnostics?.successValues, lastSuccess: mobileResult.diagnostics?.lastSuccess,
    });

    await screenshot(mobilePage, "mobile-final.png");
    await mobileCtxObj.close();
    assertZeroErrors(mobileTracker, "Mobile");

    // ═════ Summary ═════
    console.log("\n  === SUMMARY ===");
    console.log(`  Desktop supported: 3/3`);
    console.log(`  Desktop unknown: 1/1`);
    console.log(`  Mobile supported: 1/1`);
    console.log(`  Desktop errors: nonLocal=${desktopTracker.nonLocal.length} console=${desktopTracker.consoleErrors.length} warn=${desktopTracker.warnings.length} page=${desktopTracker.pageErrors.length} reqFail=${desktopTracker.requestFailures.length}`);
    console.log(`  Mobile errors: nonLocal=${mobileTracker.nonLocal.length} console=${mobileTracker.consoleErrors.length} warn=${mobileTracker.warnings.length} page=${mobileTracker.pageErrors.length} reqFail=${mobileTracker.requestFailures.length}`);
    console.log(`  Browser: ${launchInfo.source} v${launchInfo.version}`);
    console.log("\nAll Page Agent lab E2E checks passed.");

    ensureScreenshotDir();
    writeFileSync(join(SCREENSHOT_DIR, "browser-evidence.json"), JSON.stringify({
      baseUrl, labUrl, timestamp: new Date().toISOString(), browser: launchInfo,
      desktop: { tasks: browserEvidence.desktop.tasks, errors: desktopTracker },
      mobile: { tasks: browserEvidence.mobile.tasks, errors: mobileTracker },
    }, null, 2));
  } catch (err) {
    console.error("\nPage Agent lab E2E verification FAILED:");
    console.error(err && err.stack ? err.stack : err);
    allPassed = false;
  } finally {
    // Each task's context is closed individually; only close the browser here
    await browser.close();
  }

  if (!allPassed) process.exit(1);
}

main();
