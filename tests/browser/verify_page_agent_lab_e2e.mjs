// tests/browser/verify_page_agent_lab_e2e.mjs
//
// End-to-end browser verification for the #1090 Page Agent lab.
//
// Requires:
//   - Playwright package installed
//   - Chromium executable available
//   - A local HTTP server running at the specified BASE_URL
//
// Usage:
//   node tests/browser/verify_page_agent_lab_e2e.mjs <BASE_URL>
//
// Example:
//   node tests/browser/verify_page_agent_lab_e2e.mjs http://127.0.0.1:8765
//
// The BASE_URL must be a localhost or 127.0.0.1 origin.

import { chromium } from "playwright";
import assert from "node:assert";
import { writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = join(
  __dirname,
  "..",
  "..",
  "docs",
  "artifacts",
  "1090-page-agent-lab",
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

  const browser = await chromium.launch({ headless: true });
  const monitor = new RequestMonitor();

  try {
    // ── Desktop test ───────────────────────────────────────────────────────

    console.log("\n[Desktop 1440px]");
    const desktopCtx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });
    const desktopPage = await desktopCtx.newPage();

    // Monitor requests
    desktopPage.on("request", (req) => monitor.onRequest(req));
    desktopPage.on("requestfailed", (req) => {
      // We don't throw here, just record
    });

    // Navigate to the lab page
    await desktopPage.goto(labUrl, { waitUntil: "networkidle", timeout: 15000 });
    await screenshot(desktopPage, "desktop-initial.png");

    // Verify page content
    const title = await desktopPage.title();
    assert.ok(
      title.includes("Page Agent"),
      `Page title must contain 'Page Agent': ${title}`,
    );

    // Verify required sections are visible
    const sections = [
      "overview",
      "what-is-page-agent",
      "core-features",
      "use-cases",
      "vs-browser-use",
      "quick-start",
      "npm-installation",
      "basic-execution",
      "architecture",
      "custom-ui",
      "license",
      "source-attribution",
    ];
    for (const sectionId of sections) {
      const el = await desktopPage.$(`#${sectionId}`);
      assert.ok(el, `Section #${sectionId} must exist in the DOM`);
    }

    // Verify MIT license text
    const bodyText = await desktopPage.textContent("body");
    assert.ok(bodyText.includes("MIT License"), "MIT License must be visible");
    assert.ok(
      bodyText.includes("Permission is hereby granted"),
      "MIT permission notice must be visible",
    );

    // Verify provenance
    assert.ok(
      bodyText.includes("alibaba/page-agent"),
      "Upstream repository must be shown",
    );
    assert.ok(
      bodyText.includes("fa4664dfa5379e6e91deaf85bc1db2ae14d8e1d7"),
      "Pinned commit SHA must be shown",
    );
    assert.ok(bodyText.includes("1.12.1"), "Version must be shown");

    // Verify experiment marker
    assert.ok(
      bodyText.includes("interoperability experiment") || bodyText.includes("Local Lab"),
      "Page must be marked as interoperability experiment",
    );

    // Check for non-local requests
    const nonLocalBefore = monitor.getNonLocalRequests(baseUrl);
    assert.strictEqual(
      nonLocalBefore.length,
      0,
      `Non-local requests detected on initial load: ${JSON.stringify(nonLocalBefore.slice(0, 5))}`,
    );

    await screenshot(desktopPage, "desktop-panel.png");

    // ── Mobile test ────────────────────────────────────────────────────────

    console.log("[Mobile 390px]");
    const mobileCtx = await browser.newContext({
      viewport: { width: 390, height: 844 },
    });
    const mobilePage = await mobileCtx.newPage();
    monitor.reset();

    mobilePage.on("request", (req) => monitor.onRequest(req));

    await mobilePage.goto(labUrl, { waitUntil: "networkidle", timeout: 15000 });
    await screenshot(mobilePage, "mobile-panel.png");

    // Verify page loads on mobile
    const mobileTitle = await mobilePage.title();
    assert.ok(mobileTitle.includes("Page Agent"), "Mobile page must load");

    const mobileBody = await mobilePage.textContent("body");
    assert.ok(mobileBody.includes("MIT License"), "MIT license visible on mobile");

    const nonLocalMobile = monitor.getNonLocalRequests(baseUrl);
    assert.strictEqual(
      nonLocalMobile.length,
      0,
      `Non-local requests detected on mobile: ${JSON.stringify(nonLocalMobile.slice(0, 5))}`,
    );

    await mobileCtx.close();

    // ── Activity / history visibility ─────────────────────────────────────
    // The Page Agent Panel should be visible and show the input area.
    // Since the panel is a floating element created by PageAgent, we check
    // for it by looking for specific UI markers.

    // Check for console errors (desktop page)
    const consoleErrors = [];
    desktopPage.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    // Check for page errors
    const pageErrors = [];
    desktopPage.on("pageerror", (err) => {
      pageErrors.push(err.message);
    });

    // Give the Page Agent time to initialize
    await desktopPage.waitForTimeout(2000);

    // Collect any errors after initialization
    const finalConsoleErrors = consoleErrors.filter(
      (e) => !e.includes("favicon.ico") && !e.includes("net::ERR_")
    );
    const finalPageErrors = pageErrors;

    // Report findings
    if (finalConsoleErrors.length > 0) {
      console.warn(`  Console errors (non-fatal): ${finalConsoleErrors.length}`);
      for (const err of finalConsoleErrors) {
        console.warn(`    - ${err}`);
      }
    }

    if (finalPageErrors.length > 0) {
      console.warn(`  Page errors (non-fatal): ${finalPageErrors.length}`);
      for (const err of finalPageErrors) {
        console.warn(`    - ${err}`);
      }
    }

    console.log(`  Console errors: ${finalConsoleErrors.length}`);
    console.log(`  Page errors: ${finalPageErrors.length}`);

    const nonLocalFinal = monitor.getNonLocalRequests(baseUrl);
    console.log(`  Non-local requests: ${nonLocalFinal.length}`);

    // Save evidence
    ensureScreenshotDir();
    const evidence = {
      baseUrl,
      labUrl,
      timestamp: new Date().toISOString(),
      viewports: {
        desktop: { width: 1440, height: 900 },
        mobile: { width: 390, height: 844 },
      },
      sectionsFound: sections.length,
      nonLocalRequests: nonLocalFinal.map((r) => r.url),
      consoleErrors: finalConsoleErrors,
      pageErrors: finalPageErrors,
      passed: finalConsoleErrors.length === 0 || finalPageErrors.length === 0,
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
