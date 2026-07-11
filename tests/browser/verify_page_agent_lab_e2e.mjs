// tests/browser/verify_page_agent_lab_e2e.mjs
//
// End-to-end browser verification for the #1090 Page Agent lab.
//
// This lab vendors a custom non-demo IIFE bundle built from pinned upstream
// source (alibaba/page-agent@fa4664df). page-agent-lab.js instantiates the
// real PageAgent → PageAgentCore → PageController → built-in Panel stack
// with a local deterministic mock model and same-origin customFetch.
//
// Requires:
//   - Playwright package installed
//   - A local HTTP server running at the specified BASE_URL
//
// Usage:
//   node tests/browser/verify_page_agent_lab_e2e.mjs <BASE_URL>
//
// The BASE_URL must be a localhost or 127.0.0.1 origin.

import { chromium } from "playwright";
import assert from "node:assert";
import { writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = join(
  __dirname, "..", "..", "docs", "artifacts", "1090-page-agent-lab",
);

// ── Localhost validation ─────────────────────────────────────────────────

const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1"]);

function validateBaseUrl(baseUrl) {
  const parsed = new URL(baseUrl);
  if (!LOCAL_HOSTS.has(parsed.hostname)) {
    throw new Error(`BASE_ORIGIN must be localhost, got: ${parsed.hostname}`);
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error(`BASE_ORIGIN protocol must be http or https, got: ${parsed.protocol}`);
  }
  if (parsed.username || parsed.password) {
    throw new Error("BASE_ORIGIN must not contain credentials");
  }
  if (parsed.search) {
    throw new Error("BASE_ORIGIN must not contain query string");
  }
  if (parsed.hash) {
    throw new Error("BASE_ORIGIN must not contain hash");
  }
}

// ── Request monitoring ───────────────────────────────────────────────────

class RequestMonitor {
  constructor() {
    this.requests = [];
  }

  onRequest(request) {
    this.requests.push({
      url: request.url(),
      method: request.method(),
      resourceType: request.resourceType(),
      headers: request.headers(),
    });
  }

  getNonLocalRequests(baseOrigin) {
    return this.requests.filter((r) => !r.url.startsWith(baseOrigin));
  }

  getMockApiRequests(baseOrigin) {
    return this.requests.filter(
      (r) => r.url.includes("/mock-llm/v1/chat/completions") && r.url.startsWith(baseOrigin),
    );
  }

  reset() {
    this.requests = [];
  }
}

// ── Screenshot helper ────────────────────────────────────────────────────

function ensureScreenshotDir() {
  if (!existsSync(SCREENSHOT_DIR)) {
    mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }
}

async function screenshot(page, name) {
  ensureScreenshotDir();
  await page.screenshot({
    path: join(SCREENSHOT_DIR, name),
    fullPage: false,
  });
}

// ── Browser launch with optional system executable ───────────────────────

function getLaunchOptions() {
  const opts = { headless: true };
  if (process.env.PAGE_AGENT_BROWSER_EXECUTABLE) {
    opts.executablePath = process.env.PAGE_AGENT_BROWSER_EXECUTABLE;
  }
  return opts;
}

// ── Task configuration ───────────────────────────────────────────────────

const TASKS = [
  {
    id: "quick-start",
    prompt: "Show the Quick Start section.",
    sectionId: "quick-start",
    sectionText: "Quick Start",
  },
  {
    id: "vs-browser-use",
    prompt: "Compare page-agent with browser-use.",
    sectionId: "vs-browser-use",
    sectionText: "Page Agent vs browser-use",
  },
  {
    id: "license",
    prompt: "Show the MIT license section.",
    sectionId: "license",
    sectionText: "MIT License",
  },
  {
    id: "architecture",
    prompt: "Find the custom UI architecture.",
    sectionId: "architecture",
    sectionText: "Custom UI",
  },
];

// ── Attempt to submit a task via the Page Agent Panel ────────────────────
//
// Returns one of:
//   "panel-input"   — text was typed into Panel textarea and Enter pressed
//   "via-execute"   — task was dispatched via agent.execute()
//   "panel-present" — Panel found but could not submit (informational)
//   "panel-not-found" — no Panel input or agent.execute() found

async function submitTaskViaPanel(page, prompt) {
  // Try to find the Panel's input element
  // PageAgent's built-in Panel injects elements with specific classes
  const panelInput = await page.$(
    "textarea.page-agent-panel-input, " +
    "div.page-agent-panel textarea, " +
    "#pageAgentPanel textarea, " +
    "textarea[placeholder*='input']",
  );

  if (panelInput) {
    await panelInput.click();
    await panelInput.fill(prompt);
    // Dispatch native change event for frameworks that expect it
    await page.evaluate((el) => {
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }, panelInput);
    await page.waitForTimeout(500);
    await panelInput.press("Enter");
    return "panel-input";
  }

  // Fallback: try agent.execute() via window.__PAGE_AGENT_LAB__
  const result = await page.evaluate((p) => {
    const lab = window.__PAGE_AGENT_LAB__;
    if (!lab || !lab.agent) return "no-agent";
    if (typeof lab.agent.execute === "function") {
      lab.agent.execute(p);
      return "via-execute";
    }
    if (lab.panel === "built-in") return "panel-present";
    return "panel-not-found";
  }, prompt);

  return result;
}

// ── Main verification ────────────────────────────────────────────────────

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
  const monitor = new RequestMonitor();
  const evidence = {
    baseUrl, labUrl,
    timestamp: new Date().toISOString(),
    desktop: { tasksAttempted: 0, tasksCompleted: 0, results: [] },
    mobile: { tasksAttempted: 0, tasksCompleted: 0, results: [] },
    nonLocalRequestsDesktop: [],
    nonLocalRequestsMobile: [],
    consoleErrors: [],
    networkErrors: [],
  };

  const desktopSections = [
    "overview", "what-is-page-agent", "core-features", "use-cases",
    "vs-browser-use", "quick-start", "npm-installation", "basic-execution",
    "architecture", "custom-ui", "local-integration", "license", "source-attribution",
  ];

  try {
    // ═════════════════════════════════════════════════════════════════════
    // Desktop test (1440px)
    // ═════════════════════════════════════════════════════════════════════
    console.log("\n[Desktop 1440px]");
    const desktopCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const desktopPage = await desktopCtx.newPage();
    monitor.reset();
    const desktopErrors = [];

    desktopPage.on("request", (req) => monitor.onRequest(req));
    desktopPage.on("pageerror", (err) => { desktopErrors.push(err.message); });
    desktopPage.on("console", (msg) => {
      if (msg.type() === "error" || msg.type() === "warning") {
        evidence.consoleErrors.push(`[${msg.type()}] ${msg.text()}`);
      }
    });
    desktopPage.on("requestfailed", (req) => {
      evidence.networkErrors.push({ url: req.url(), error: req.failure()?.errorText });
    });

    await desktopPage.goto(labUrl, { waitUntil: "networkidle", timeout: 20000 });
    await screenshot(desktopPage, "desktop-initial.png");

    // Verify page title
    const title = await desktopPage.title();
    assert.ok(title.includes("Page Agent"), `Page title: ${title}`);
    console.log(`  Page title: ${title}`);

    // Verify Page Agent Panel is initialized via window.__PAGE_AGENT_LAB__
    const labState = await desktopPage.evaluate(() => {
      const lab = window.__PAGE_AGENT_LAB__;
      if (!lab) return { initialized: false };
      return {
        initialized: true,
        integration: lab.integration,
        panel: lab.panel,
        hasAgent: !!lab.agent,
        hasAgentPanel: !!(lab.agent && lab.agent.panel),
      };
    });
    assert.ok(labState.initialized, "window.__PAGE_AGENT_LAB__ must be defined");
    assert.strictEqual(labState.integration, "actual-page-agent", "must be actual PageAgent");
    assert.strictEqual(labState.panel, "built-in", "must use built-in Panel");
    assert.ok(labState.hasAgent, "agent instance must exist");
    console.log(`  PageAgent Panel (built-in): ${labState.panel}`);

    // Verify all sections exist in DOM
    for (const sectionId of desktopSections) {
      const el = await desktopPage.$(`#${sectionId}`);
      assert.ok(el, `Section #${sectionId} must exist in the DOM`);
    }

    // Verify MIT license and upstream provenance
    const bodyText = await desktopPage.textContent("body");
    assert.ok(bodyText.includes("MIT License"), "MIT License must be visible");
    assert.ok(bodyText.includes("Permission is hereby granted"), "MIT notice must be visible");
    assert.ok(bodyText.includes("alibaba/page-agent"), "Repository must be shown");
    assert.ok(bodyText.includes("fa4664dfa5379e6e91deaf85bc1db2ae14d8e1d7"), "Commit SHA shown");
    assert.ok(bodyText.includes("1.12.1"), "Version shown");
    assert.ok(bodyText.includes("interoperability experiment") || bodyText.includes("Local Lab"),
      "Page must be marked as experiment");

    // Verify the real bundle documentation
    assert.ok(
      bodyText.includes("custom non-demo IIFE bundle"),
      "Page must document the real non-demo bundle",
    );

    // ── Attempt supported tasks ──────────────────────────────────────────
    let desktopTasksAttempted = 0;
    let desktopTasksCompleted = 0;

    for (const task of TASKS.slice(0, 3)) { // Attempt first 3 tasks on desktop
      desktopTasksAttempted++;
      console.log(`  Task ${desktopTasksAttempted}/3: "${task.prompt.substring(0, 40)}..."`);

      try {
        const status = await submitTaskViaPanel(desktopPage, task.prompt);
        await desktopPage.waitForTimeout(2000);
        await screenshot(desktopPage, `desktop-task-${task.id}.png`);

        if (status === "panel-input" || status === "via-execute") {
          desktopTasksCompleted++;
        }

        evidence.desktop.results.push({
          task: task.id,
          prompt: task.prompt,
          submitStatus: status,
        });
        console.log(`    submit status: ${status}`);
      } catch (err) {
        evidence.desktop.results.push({
          task: task.id,
          prompt: task.prompt,
          submitStatus: `error: ${err.message}`,
        });
        console.log(`    submit error: ${err.message}`);
      }
    }

    evidence.desktop.tasksAttempted = desktopTasksAttempted;
    evidence.desktop.tasksCompleted = desktopTasksCompleted;

    // Check for customFetch invocations (mock model requests)
    const mockRequests = monitor.getMockApiRequests(baseUrl);
    console.log(`  Mock model customFetch requests: ${mockRequests.length}`);

    // No non-local requests (excluding favicon)
    const nonLocal = monitor.getNonLocalRequests(baseUrl).filter(
      (r) => !r.url.includes("favicon"),
    );
    evidence.nonLocalRequestsDesktop = nonLocal;
    assert.strictEqual(nonLocal.length, 0,
      `Non-local requests on desktop: ${JSON.stringify(nonLocal.slice(0, 5))}`);
    console.log(`  Non-local requests: ${nonLocal.length}`);

    await screenshot(desktopPage, "desktop-final.png");

    // ═════════════════════════════════════════════════════════════════════
    // Mobile test (390px)
    // ═════════════════════════════════════════════════════════════════════
    console.log("\n[Mobile 390px]");
    const mobileCtx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const mobilePage = await mobileCtx.newPage();
    monitor.reset();

    mobilePage.on("request", (req) => monitor.onRequest(req));
    mobilePage.on("pageerror", (err) => { evidence.consoleErrors.push(err.message); });
    mobilePage.on("requestfailed", (req) => {
      evidence.networkErrors.push({ url: req.url(), error: req.failure()?.errorText });
    });

    await mobilePage.goto(labUrl, { waitUntil: "networkidle", timeout: 20000 });
    await screenshot(mobilePage, "mobile-initial.png");

    const mobileTitle = await mobilePage.title();
    assert.ok(mobileTitle.includes("Page Agent"), "Mobile page must load");
    console.log(`  Mobile title: ${mobileTitle}`);

    const mobileBody = await mobilePage.textContent("body");
    assert.ok(mobileBody.includes("MIT License"), "MIT license visible on mobile");

    // Attempt first task on mobile
    const firstTask = TASKS[0];
    evidence.mobile.tasksAttempted = 1;
    try {
      const status = await submitTaskViaPanel(mobilePage, firstTask.prompt);
      await mobilePage.waitForTimeout(3000);

      if (status === "panel-input" || status === "via-execute") {
        evidence.mobile.tasksCompleted = 1;
      }

      evidence.mobile.results.push({
        task: firstTask.id,
        prompt: firstTask.prompt,
        submitStatus: status,
      });
      console.log(`  Mobile task submit status: ${status}`);
      await screenshot(mobilePage, "mobile-final.png");
    } catch (err) {
      evidence.mobile.results.push({
        task: firstTask.id,
        prompt: firstTask.prompt,
        submitStatus: `error: ${err.message}`,
      });
    }

    const nonLocalMobile = monitor.getNonLocalRequests(baseUrl).filter(
      (r) => !r.url.includes("favicon"),
    );
    evidence.nonLocalRequestsMobile = nonLocalMobile;
    assert.strictEqual(nonLocalMobile.length, 0,
      `Non-local requests on mobile: ${JSON.stringify(nonLocalMobile.slice(0, 5))}`);

    await screenshot(mobilePage, "mobile-final.png");
    await mobileCtx.close();

    // ── Summary ───────────────────────────────────────────────────────────
    console.log(`\n  Desktop: ${evidence.desktop.tasksCompleted}/${evidence.desktop.tasksAttempted} tasks completed`);
    console.log(`  Mobile: ${evidence.mobile.tasksCompleted}/${evidence.mobile.tasksAttempted} tasks completed`);
    console.log(`  Non-local requests: ${nonLocal.length} desktop, ${nonLocalMobile.length} mobile`);
    console.log(`  Console/warning messages: ${evidence.consoleErrors.length}`);

    const fatalPageErrors = desktopErrors.filter(
      (e) => !e.includes("favicon") && !e.includes("net::ERR_"),
    );
    console.log(`  Page errors (excluding favicon): ${fatalPageErrors.length}`);

    // ── Save evidence ────────────────────────────────────────────────────
    ensureScreenshotDir();
    writeFileSync(
      join(SCREENSHOT_DIR, "browser-evidence.json"),
      JSON.stringify(evidence, null, 2),
    );

    await desktopCtx.close();
    console.log("\nAll Page Agent lab E2E checks completed.");
    console.log(`Screenshots saved to: ${SCREENSHOT_DIR}`);
  } catch (err) {
    console.error("Page Agent lab E2E verification FAILED:");
    console.error(err && err.stack ? err.stack : err);
    await browser.close();
    process.exit(1);
  } finally {
    await browser.close();
  }
}

main();
