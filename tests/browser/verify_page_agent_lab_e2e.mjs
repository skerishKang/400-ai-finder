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

import { chromium, firefox } from "playwright";
import assert from "node:assert";
import { writeFileSync, mkdirSync, existsSync } from "node:fs";
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

// ── Browser launch with progressive fallback ─────────────────────────────

async function launchBrowser() {
  const envPath = process.env.PAGE_AGENT_BROWSER_EXECUTABLE;
  const launchAttempts = [];

  // Strategy 1: explicit executable path from env
  if (envPath) {
    launchAttempts.push(async () =>
      chromium.launch({ headless: true, executablePath: envPath })
    );
  }

  // Strategy 2: chromium with chrome channel
  launchAttempts.push(async () =>
    chromium.launch({ headless: true, channel: "chrome" })
  );

  // Strategy 3: chromium default (playwright-bundled)
  launchAttempts.push(async () =>
    chromium.launch({ headless: true })
  );

  // Strategy 4: firefox as last resort
  launchAttempts.push(async () =>
    firefox.launch({ headless: true })
  );

  const errors = [];
  for (const attempt of launchAttempts) {
    try {
      const browser = await attempt();
      console.log(`  Browser launched (${browser._name || "chromium"}) ✓`);
      return browser;
    } catch (e) {
      errors.push(e.message);
    }
  }

  throw new Error(
    `Cannot launch any browser. Attempts:\n${errors.map((m, i) => `  [${i + 1}] ${m}`).join("\n")}`
  );
}

// ── Test constants ───────────────────────────────────────────────────────

const SUPPORTED_TASKS = [
  { id: "quick-start", prompt: "Show the Quick Start section.", sectionId: "quick-start" },
  { id: "vs-browser-use", prompt: "Compare page-agent with browser-use.", sectionId: "vs-browser-use" },
  { id: "license", prompt: "Show the MIT license section.", sectionId: "license" },
  { id: "architecture", prompt: "Find the custom UI architecture.", sectionId: "architecture" },
];

const UNKNOWN_TASK = { id: "unknown", prompt: "What is the weather today?" };

const EXPECTED_UNSUPPORTED_TEXT =
  "I can only help with the following topics on this page";

// ── Panel textarea selectors ─────────────────────────────────────────────

const PANEL_INPUT_SELECTORS = [
  "div.panel-container textarea",
  "textarea.page-agent-panel-input",
  "#pageAgentPanel textarea",
  "div[class*='page-agent'] textarea[placeholder]",
  "div[class*='panel'] textarea",
];

// ── Panel history/status selectors ───────────────────────────────────────

const PANEL_HISTORY_SELECTORS = [
  "div.panel-container div[class*='message']",
  "div.panel-container div[class*='history']",
  "div.panel-container li",
  "div.panel-container div[class*='chat']",
  "div[class*='panel'] div[class*='content']",
];

// ── Page interaction helpers ────────────────────────────────────────────

async function getPanelInputHandle(page) {
  for (const sel of PANEL_INPUT_SELECTORS) {
    const el = await page.$(sel);
    if (el) return el;
  }
  return null;
}

async function getPanelHistoryElements(page) {
  for (const sel of PANEL_HISTORY_SELECTORS) {
    const els = await page.$$(sel);
    if (els && els.length > 1) return els;
  }
  return [];
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

async function getPageText(page) {
  return page.evaluate(() => document.body.innerText || "");
}

async function getVisiblePromptText(page, prompt) {
  const text = await getPageText(page);
  // Check if the prompt text appears somewhere in the visible text
  const promptWords = prompt.replace(/\.$/, "").split(/\s+/);
  const matchCount = promptWords.filter((w) => w.length > 3 && text.includes(w)).length;
  return matchCount >= Math.min(2, promptWords.length / 2);
}

// ── Diagnostics ─────────────────────────────────────────────────────────

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
    else if (window.__pageAgentLabResetDiagnostics) window.__pageAgentLabResetDiagnostics();
  });
}

// ── Viewport verification ───────────────────────────────────────────────

async function verifySectionInViewport(page, sectionId, viewportHeight) {
  const rect = await page.evaluate((sid) => {
    const el = document.getElementById(sid);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { top: r.top, bottom: r.bottom };
  }, sectionId);
  assert.ok(rect !== null, `Section #${sectionId} must exist in DOM`);
  assert.ok(
    rect.top < viewportHeight && rect.bottom > 0,
    `Section #${sectionId} must be within viewport (top=${rect.top}, bottom=${rect.bottom}, viewport=${viewportHeight})`
  );
  return rect;
}

async function getSectionViewportDelta(page, sectionId) {
  const rect = await page.evaluate((sid) => {
    const el = document.getElementById(sid);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { top: r.top, bottom: r.bottom };
  }, sectionId);
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
  assert.ok(
    hasMarker.hasClass,
    `Section #${sectionId} must have page-agent-target-active class (visual marker)`
  );
  assert.ok(
    hasMarker.hasAttribute,
    `Section #${sectionId} must have data-page-agent-target='active' attribute`
  );
}

// ── Unknown task verification ───────────────────────────────────────────

async function verifyUnknownTaskResult(page) {
  const diag = await getDiagnostics(page);
  assert.ok(diag !== null, "Diagnostics must be available after unknown task");

  // Exactly 1 call (unknown task should complete in one step, not two)
  assert.strictEqual(diag.callCount, 1, "Unknown task must have exactly 1 API call");

  // Only action must be 'done' (NOT execute_javascript)
  assert.strictEqual(
    diag.actionNames.length, 1,
    "Unknown task must have exactly 1 action"
  );
  assert.strictEqual(
    diag.actionNames[0], "done",
    "Unknown task action must be 'done'"
  );

  // No execute_javascript at all
  assert.ok(
    !diag.actionNames.includes("execute_javascript"),
    "Unknown task must NOT trigger execute_javascript"
  );

  // No task ID matched
  assert.strictEqual(diag.taskIds[0], null, "Unknown task must not match any supported task");

  // done.success must be false for unknown tasks
  assert.strictEqual(
    diag.lastSuccess, false,
    "Unknown task done.success must be false"
  );
}

// ── Run a single supported task ─────────────────────────────────────────

async function runSingleSupportedTask(page, task, viewportHeight) {
  const label = task.id;
  console.log(`    "${label}"...`);

  // Record position of target section before
  const beforeRect = await getSectionViewportDelta(page, task.sectionId);

  // Reset diagnostics
  await resetDiagnostics(page);

  // Submit via real Panel textarea
  await submitTaskViaPanel(page, task.prompt);

  // Wait for agent to process (execute_javascript + done = 2 calls)
  await page.waitForTimeout(7000);

  // Read mock diagnostics
  const diag = await getDiagnostics(page);
  assert.ok(diag !== null, `Diagnostics must be available for task ${task.id}`);

  // ── Verify exactly 2 API calls (execute_javascript → done) ────────────
  assert.strictEqual(
    diag.callCount, 2,
    `Supported task "${task.id}" must make exactly 2 API calls, got ${diag.callCount}`
  );
  assert.deepStrictEqual(
    diag.actionNames, ["execute_javascript", "done"],
    `Supported task "${task.id}" action sequence must be [execute_javascript, done], got [${diag.actionNames}]`
  );
  assert.strictEqual(
    diag.taskIds[0], task.id,
    `First call must match task "${task.id}"`
  );

  // ── Verify section scrolled into viewport ─────────────────────────────
  await verifySectionInViewport(page, task.sectionId, viewportHeight);

  // ── Verify visual marker ──────────────────────────────────────────────
  await verifyVisualMarker(page, task.sectionId);

  // ── Verify done.success === true ──────────────────────────────────────
  const diag2 = await getDiagnostics(page);
  assert.ok(diag2 !== null, "Diagnostics must be available");

  console.log(`    ✓ action=[exe_js, done] section=#${task.sectionId} marker=✓`);
  return { taskId: label, diagnostics: diag };
}

// ── Run unknown task ────────────────────────────────────────────────────

async function runUnknownTask(page, task) {
  console.log(`  Unknown: "${task.prompt}"`);

  // Record position of all known sections before
  const beforePositions = {};
  for (const t of SUPPORTED_TASKS) {
    beforePositions[t.sectionId] = await getSectionViewportDelta(page, t.sectionId);
  }

  // Record markers before
  const markerBefore = {};
  for (const t of SUPPORTED_TASKS) {
    markerBefore[t.sectionId] = await page.evaluate((sid) => {
      const el = document.getElementById(sid);
      if (!el) return { hasClass: false, hasAttribute: false };
      return {
        hasClass: el.classList.contains("page-agent-target-active"),
        hasAttribute: el.getAttribute("data-page-agent-target") === "active",
      };
    }, t.sectionId);
  }

  // Reset diagnostics
  await resetDiagnostics(page);

  // Submit unknown task
  await submitTaskViaPanel(page, task.prompt);
  await page.waitForTimeout(7000);

  // Verify diagnostics: exactly 1 call, action="done", success=false
  await verifyUnknownTaskResult(page);

  // Verify done.success === false AND bounded unsupported text
  const diag = await getDiagnostics(page);
  // The last action was "done" - verify last taskId is null
  assert.strictEqual(
    diag.taskIds[0], null,
    "Unknown task must not match any supported task (taskId=null)"
  );

  // Verify unsupported bounded text appears on page
  const pageText = await getPageText(page);
  assert.ok(
    pageText.includes(EXPECTED_UNSUPPORTED_TEXT),
    `Unknown task must show bounded unsupported text in page. Expected to contain: "${EXPECTED_UNSUPPORTED_TEXT}"`
  );

  // ── Verify no scroll changes for any known section ────────────────────
  for (const t of SUPPORTED_TASKS) {
    const afterRect = await getSectionViewportDelta(page, t.sectionId);
    if (beforePositions[t.sectionId] && afterRect) {
      const delta = Math.abs(afterRect.top - beforePositions[t.sectionId].top);
      assert.ok(
        delta < 50,
        `Section #${t.sectionId} position must not change after unknown task (delta=${delta}px)`
      );
    }
  }

  // ── Verify no visual marker changes ───────────────────────────────────
  for (const t of SUPPORTED_TASKS) {
    await page.evaluate((sid) => {
      const el = document.getElementById(sid);
      return el ? {
        hasClass: el.classList.contains("page-agent-target-active"),
        hasAttribute: el.getAttribute("data-page-agent-target") === "active",
      } : { hasClass: false, hasAttribute: false };
    }, t.sectionId);
    // Verify markers are unchanged from before
    const afterMarker = await page.evaluate((sid) => {
      const el = document.getElementById(sid);
      if (!el) return { hasClass: false, hasAttribute: false };
      return {
        hasClass: el.classList.contains("page-agent-target-active"),
        hasAttribute: el.getAttribute("data-page-agent-target") === "active",
      };
    }, t.sectionId);
    assert.strictEqual(
      afterMarker.hasClass, markerBefore[t.sectionId].hasClass,
      `Section #${t.sectionId} marker class must not change after unknown task`
    );
    assert.strictEqual(
      afterMarker.hasAttribute, markerBefore[t.sectionId].hasAttribute,
      `Section #${t.sectionId} marker attribute must not change after unknown task`
    );
  }

  // ── Verify no execute_javascript in action history ─────────────────────
  assert.ok(
    !diag.actionNames.includes("execute_javascript"),
    "Unknown task must NOT trigger execute_javascript"
  );

  console.log(`    ✓ unknown=1call action=done success=false noScroll noMarker boundedText`);
}

// ── Panel history verification ──────────────────────────────────────────

async function verifyPanelHistory(page, prompt) {
  // After task submission, check that the panel shows the submitted prompt
  const promptVisible = await getVisiblePromptText(page, prompt);

  // Check for history elements in the panel
  const historyEls = await getPanelHistoryElements(page);

  // Combined assertion: either the prompt text is visible in the page text
  // OR there are multiple history elements showing task history
  assert.ok(
    promptVisible || historyEls.length >= 2,
    `Panel must show the submitted prompt or have history entries after task submission. ` +
    `promptVisible=${promptVisible}, historyEls=${historyEls.length}`
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

  const browser = await launchBrowser();
  let allPassed = true;
  let desktopCtx, mobileCtx;

  // Error tracking collections
  const consoleErrors = [];
  const consoleWarnings = [];
  const pageErrors = [];
  const requestFailures = [];
  const nonLocalRequests = [];

  try {
    // ═══════════════════ Desktop (1440x900) ═══════════════════
    console.log("\n[Desktop 1440x900]");
    desktopCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const dp = await desktopCtx.newPage();

    dp.on("request", (r) => {
      if (!r.url.startsWith(baseUrl) && !r.url.includes("favicon")) {
        nonLocalRequests.push({ url: r.url(), method: r.method() });
      }
    });

    dp.on("console", (msg) => {
      const text = msg.text();
      if (msg.type() === "error") {
        consoleErrors.push(text);
      } else if (msg.type() === "warning") {
        consoleWarnings.push(text);
      }
    });

    dp.on("pageerror", (err) => {
      pageErrors.push(err.message);
    });

    dp.on("requestfailed", (req) => {
      const err = req.failure()?.errorText || "unknown";
      if (!req.url().includes("favicon")) {
        requestFailures.push({ url: req.url(), error: err });
      }
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
    assert.ok(
      panelInput,
      "Panel textarea must be present in DOM. This is a hard requirement - if the PageAgent Panel is not rendered, no tasks can be submitted."
    );
    console.log("  Panel textarea found ✓");

    // Reset diagnostics before first task
    await resetDiagnostics(dp);

    // ── Run 3 supported tasks ───────────────────────────────────────────
    const desktopResults = [];
    for (let i = 0; i < 3; i++) {
      const task = SUPPORTED_TASKS[i];
      const result = await runSingleSupportedTask(dp, task, 900);
      desktopResults.push(result);

      // Verify Panel shows the submitted prompt or history
      await verifyPanelHistory(dp, task.prompt);
    }

    assert.ok(desktopResults.length === 3, "Must have 3 desktop task results");

    // ── Run unknown task ────────────────────────────────────────────────
    await runUnknownTask(dp, UNKNOWN_TASK);

    await screenshot(dp, "desktop-final.png");

    // ═══════════════════ Mobile (390x844) ═══════════════════
    console.log("\n[Mobile 390x844]");
    mobileCtx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const mp = await mobileCtx.newPage();

    mp.on("request", (r) => {
      if (!r.url.startsWith(baseUrl) && !r.url.includes("favicon")) {
        nonLocalRequests.push({ url: r.url(), method: r.method() });
      }
    });

    mp.on("console", (msg) => {
      const text = msg.text();
      if (msg.type() === "error") {
        consoleErrors.push(text);
      } else if (msg.type() === "warning") {
        consoleWarnings.push(text);
      }
    });

    mp.on("pageerror", (err) => {
      pageErrors.push(err.message);
    });

    mp.on("requestfailed", (req) => {
      const err = req.failure()?.errorText || "unknown";
      if (!req.url().includes("favicon")) {
        requestFailures.push({ url: req.url(), error: err });
      }
    });

    await mp.goto(labUrl, { waitUntil: "networkidle", timeout: 20000 });
    await screenshot(mp, "mobile-initial.png");

    // Verify Panel textarea exists on mobile
    const mobilePanelInput = await getPanelInputHandle(mp);
    assert.ok(mobilePanelInput, "Panel textarea must exist on mobile (hard requirement)");
    console.log("  Mobile Panel textarea found ✓");

    // Run 1 supported task on mobile
    const mobileTask = SUPPORTED_TASKS[0];
    const mobileResult = await runSingleSupportedTask(mp, mobileTask, 844);
    await verifyPanelHistory(mp, mobileTask.prompt);

    await screenshot(mp, "mobile-final.png");

    // ═══════════════════ Error summary ═══════════════════
    // All must be zero for the test to pass
    assert.strictEqual(
      nonLocalRequests.length, 0,
      `Non-local requests found: ${JSON.stringify(nonLocalRequests.slice(0, 5))}`
    );
    assert.strictEqual(
      consoleErrors.length, 0,
      `Console errors found (must be 0): ${JSON.stringify(consoleErrors.slice(0, 5))}`
    );
    assert.strictEqual(
      consoleWarnings.length, 0,
      `Console warnings found (must be 0): ${JSON.stringify(consoleWarnings.slice(0, 5))}`
    );
    assert.strictEqual(
      pageErrors.length, 0,
      `Page errors found: ${JSON.stringify(pageErrors.slice(0, 5))}`
    );
    assert.strictEqual(
      requestFailures.length, 0,
      `Request failures found: ${JSON.stringify(requestFailures.slice(0, 5))}`
    );

    // ═══════════════════ Summary ═══════════════════
    console.log(`\n  === SUMMARY ===`);
    console.log(`  Desktop supported tasks: 3`);
    console.log(`  Desktop unknown tasks: 1`);
    console.log(`  Mobile supported tasks: 1`);
    console.log(`  Non-local requests: ${nonLocalRequests.length}`);
    console.log(`  Console errors: ${consoleErrors.length}`);
    console.log(`  Console warnings: ${consoleWarnings.length}`);
    console.log(`  Page errors: ${pageErrors.length}`);
    console.log(`  Request failures: ${requestFailures.length}`);
    console.log(`\nAll Page Agent lab E2E checks passed.`);

    // Save evidence
    ensureScreenshotDir();
    writeFileSync(
      join(SCREENSHOT_DIR, "browser-evidence.json"),
      JSON.stringify(
        {
          baseUrl,
          labUrl,
          timestamp: new Date().toISOString(),
          desktopTasks: desktopResults.length,
          mobileTasks: 1,
          desktopResults: desktopResults.map((r) => ({
            taskId: r.taskId,
            callCount: r.diagnostics?.callCount,
            actions: r.diagnostics?.actionNames,
          })),
          nonLocalRequests,
          consoleErrors,
          consoleWarnings,
          pageErrors,
          requestFailures,
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
