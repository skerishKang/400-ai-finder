import assert from "assert";
import { existsSync } from "fs";
import { chromium } from "playwright";

/**
 * Focused browser proof for #1343.
 *
 * The municipal AI shell intentionally keeps clone scripts disabled with
 * sandbox="allow-same-origin". The parent MunicipalCloneSurface adapter must
 * therefore restore the repository clone's bounded GNB toggle interaction
 * without adding allow-scripts or making any external request.
 */

const rawBase = process.argv[2] || "http://127.0.0.1:8772";
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

function localOrigin(value) {
  const parsed = new URL(value);
  const host = parsed.hostname.replace(/^\[|\]$/g, "");
  if (parsed.protocol !== "http:") throw new Error("Only local http:// is allowed");
  if (!["127.0.0.1", "localhost", "::1"].includes(host)) {
    throw new Error(`Non-local host rejected: ${parsed.hostname}`);
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error("Credentials, query, and hash are not allowed in base URL");
  }
  return parsed.origin;
}

async function launchBrowser() {
  const attempts = [];
  const errors = [];
  const envPath = process.env.PREVIEW_BROWSER_EXECUTABLE;
  if (envPath) {
    attempts.push({
      name: `env: ${envPath}`,
      launch: () => chromium.launch({ headless: true, executablePath: envPath }),
    });
  }
  attempts.push({
    name: "channel: chrome",
    launch: () => chromium.launch({ headless: true, channel: "chrome" }),
  });
  for (const path of KNOWN_BROWSER_PATHS) {
    if (!existsSync(path)) continue;
    attempts.push({
      name: `path: ${path}`,
      launch: () => chromium.launch({ headless: true, executablePath: path }),
    });
  }
  attempts.push({
    name: "default playwright chromium",
    launch: () => chromium.launch({ headless: true }),
  });
  for (const attempt of attempts) {
    try {
      const browser = await attempt.launch();
      console.log(`Browser launched (${attempt.name})`);
      return browser;
    } catch (error) {
      errors.push(`[${attempt.name}] ${error.message}`);
    }
  }
  throw new Error(`Cannot launch any browser. Attempts:\n${errors.join("\n")}`);
}

const BASE_ORIGIN = localOrigin(rawBase);
const SHELL_URL = `${BASE_ORIGIN}/static/municipal-ai-shell.html?site_id=seogu_gwangju`;

const browser = await launchBrowser();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
const externalRequests = [];

await context.route("**/*", async (route) => {
  const url = route.request().url();
  if (url.startsWith("data:")) {
    await route.continue();
    return;
  }
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    externalRequests.push(url);
    await route.abort();
    return;
  }
  if (parsed.origin !== BASE_ORIGIN) {
    externalRequests.push(url);
    await route.abort();
    return;
  }
  await route.continue();
});

try {
  await page.goto(SHELL_URL, { waitUntil: "networkidle", timeout: 15000 });

  const iframe = page.locator("#municipal-clone-frame");
  await iframe.waitFor({ state: "attached", timeout: 5000 });
  const sandbox = await iframe.getAttribute("sandbox");
  assert.strictEqual(
    sandbox,
    "allow-same-origin",
    "shell must preserve the exact script-disabled sandbox boundary",
  );
  assert.ok(!sandbox.split(/\s+/).includes("allow-scripts"), "allow-scripts must remain absent");

  const frameHandle = await page.$("#municipal-clone-frame");
  assert.ok(frameHandle, "clone iframe must exist");
  const cloneFrame = await frameHandle.contentFrame();
  assert.ok(cloneFrame, "clone iframe must remain same-origin and readable");

  const toggle = cloneFrame.locator("#rc-gnb-toggle");
  const panel = cloneFrame.locator("#rc-mega-menu");
  await toggle.waitFor({ state: "visible", timeout: 10000 });
  assert.strictEqual(await toggle.getAttribute("type"), "button");
  assert.strictEqual(await toggle.getAttribute("aria-controls"), "rc-mega-menu");
  assert.strictEqual(await toggle.getAttribute("aria-expanded"), "false");
  assert.strictEqual(await panel.getAttribute("hidden"), "", "GNB panel must start hidden");

  await toggle.click();
  assert.strictEqual(await toggle.getAttribute("aria-expanded"), "true");
  assert.strictEqual(await panel.getAttribute("hidden"), null, "resident click must open GNB panel");

  await toggle.click();
  assert.strictEqual(await toggle.getAttribute("aria-expanded"), "false");
  assert.strictEqual(await panel.getAttribute("hidden"), "", "second resident click must close GNB panel");

  await toggle.click();
  assert.strictEqual(await toggle.getAttribute("aria-expanded"), "true");
  await toggle.press("Escape");
  assert.strictEqual(await toggle.getAttribute("aria-expanded"), "false");
  assert.strictEqual(await panel.getAttribute("hidden"), "", "Escape must close GNB panel");
  assert.strictEqual(
    await cloneFrame.evaluate(() => document.activeElement && document.activeElement.id),
    "rc-gnb-toggle",
    "Escape must return focus to the GNB toggle",
  );

  const evidence = await page.evaluate(() => (
    window.MunicipalAiShell && window.MunicipalAiShell.getEvidence
      ? window.MunicipalAiShell.getEvidence()
      : null
  ));
  assert.ok(evidence && evidence.ok, "bounded clone READ must remain available after GNB interaction");
  assert.strictEqual(evidence.site_id, "seogu_gwangju");
  assert.strictEqual(evidence.source_kind, "repository_clone");
  assert.strictEqual(evidence.evidence_kind, "clone_dom");
  assert.deepStrictEqual(externalRequests, [], "focused shell interaction proof must make zero external requests");

  console.log("SEOGU_SHELL_GNB_INTERACTION_PASS");
} finally {
  await context.close();
  await browser.close();
}
