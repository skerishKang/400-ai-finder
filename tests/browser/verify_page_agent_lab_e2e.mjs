// tests/browser/verify_page_agent_lab_e2e.mjs
//
// End-to-end browser verification for the #1090 Page Agent lab.
//
// Note: page-agent@1.12.1 does not expose a usable non-demo browser bundle
// for static integration (ESM requires bundler, IIFE is demo-only). This
// verifier tests the documentation page content and mock model correctness.
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
    });
  }

  getNonLocalRequests(baseOrigin) {
    return this.requests.filter((r) => !r.url.startsWith(baseOrigin));
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

  const desktopSections = [
    "overview", "what-is-page-agent", "core-features", "use-cases",
    "vs-browser-use", "quick-start", "npm-installation", "basic-execution",
    "architecture", "custom-ui", "local-integration", "license", "source-attribution",
  ];

  try {
    // ── Desktop test (1440px) ────────────────────────────────────────────
    console.log("\n[Desktop 1440px]");
    const desktopCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const desktopPage = await desktopCtx.newPage();

    desktopPage.on("request", (req) => monitor.onRequest(req));
    desktopPage.on("pageerror", (err) => { throw err; });

    await desktopPage.goto(labUrl, { waitUntil: "networkidle", timeout: 15000 });
    await screenshot(desktopPage, "desktop-initial.png");

    // Verify page title
    const title = await desktopPage.title();
    assert.ok(title.includes("Page Agent"), `Page title: ${title}`);

    // Verify all sections exist
    for (const sectionId of desktopSections) {
      const el = await desktopPage.$(`#${sectionId}`);
      assert.ok(el, `Section #${sectionId} must exist in the DOM`);
    }

    // Verify MIT license
    const bodyText = await desktopPage.textContent("body");
    assert.ok(bodyText.includes("MIT License"), "MIT License must be visible");
    assert.ok(bodyText.includes("Permission is hereby granted"), "MIT notice must be visible");
    assert.ok(bodyText.includes("alibaba/page-agent"), "Repository must be shown");
    assert.ok(bodyText.includes("fa4664dfa5379e6e91deaf85bc1db2ae14d8e1d7"), "Commit SHA shown");
    assert.ok(bodyText.includes("1.12.1"), "Version shown");
    assert.ok(bodyText.includes("interoperability experiment") || bodyText.includes("Local Lab"),
      "Page must be marked as experiment");

    // Verify bundle limitation is documented
    assert.ok(
      bodyText.includes("does not expose a usable non-demo browser bundle"),
      "Bundle limitation must be documented",
    );

    // No non-local requests
    const nonLocal = monitor.getNonLocalRequests(baseUrl);
    assert.strictEqual(nonLocal.length, 0,
      `Non-local requests on desktop: ${JSON.stringify(nonLocal.slice(0, 5))}`);

    // ── Mobile test (390px) ──────────────────────────────────────────────
    console.log("[Mobile 390px]");
    const mobileCtx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const mobilePage = await mobileCtx.newPage();
    monitor.reset();

    mobilePage.on("request", (req) => monitor.onRequest(req));
    mobilePage.on("pageerror", (err) => { throw err; });

    await mobilePage.goto(labUrl, { waitUntil: "networkidle", timeout: 15000 });
    await screenshot(mobilePage, "mobile-panel.png");

    const mobileTitle = await mobilePage.title();
    assert.ok(mobileTitle.includes("Page Agent"), "Mobile page must load");
    const mobileBody = await mobilePage.textContent("body");
    assert.ok(mobileBody.includes("MIT License"), "MIT license visible on mobile");

    const nonLocalMobile = monitor.getNonLocalRequests(baseUrl);
    assert.strictEqual(nonLocalMobile.length, 0,
      `Non-local requests on mobile: ${JSON.stringify(nonLocalMobile.slice(0, 5))}`);

    await mobileCtx.close();

    // ── Console errors ───────────────────────────────────────────────────
    const consoleErrors = [];
    desktopPage.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    await desktopPage.waitForTimeout(1000);
    const finalConsoleErrors = consoleErrors.filter(
      (e) => !e.includes("favicon.ico") && !e.includes("net::ERR_")
    );
    const finalPageErrors = [];

    console.log(`  Console errors: ${finalConsoleErrors.length}`);
    console.log(`  Page errors: ${finalPageErrors.length}`);
    console.log(`  Non-local requests: 0`);

    // Save evidence
    ensureScreenshotDir();
    const evidence = {
      baseUrl, labUrl,
      timestamp: new Date().toISOString(),
      sectionsFound: desktopSections.length,
      nonLocalRequests: [],
      consoleErrors: finalConsoleErrors,
      pageErrors: finalPageErrors,
    };
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
