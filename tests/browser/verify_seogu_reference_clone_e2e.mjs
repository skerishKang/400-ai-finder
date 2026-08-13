/**
 * Browser E2E verifier for #1303 G2-B Seo-gu faithful clone candidate QA.
 *
 * Pure offline harness. It connects to an ALREADY-SERVED localhost clone
 * directory (the Seo-gu subtree) provided as the single CLI argument:
 *
 *   node tests/browser/verify_seogu_reference_clone_e2e.mjs <LOCAL_BASE_URL>
 *
 * e.g. the CI step builds the subtree and serves it on 127.0.0.1, then passes
 * its base URL. The verifier then:
 *   1. enforces a localhost-only origin boundary (aborts any non-loopback request);
 *   2. verifies route / content / GNB interaction / list->detail navigation;
 *   3. verifies attachment affordances are visible but NOT remotely downloaded;
 *   4. verifies organization/staff reachability;
 *   5. verifies Desktop 1440x900 and Mobile 390x844 have no material horizontal
 *      overflow;
 *   6. verifies basic keyboard/focus accessibility;
 *   7. proves zero external HTTP(S) requests (incl. none to seogu.gwangju.kr).
 *
 * It reuses only the existing Playwright 1.61.1 dependency. No new dependency.
 */

import assert from "assert";
import { spawn } from "child_process";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __filename = fileURLToPath(import.meta.url);
const REPO_ROOT = join(dirname(__filename), "..", "..");
const PYTHON = process.env.PYTHON_BIN || "python";

// Known browser executable paths for fallback (no browser download).
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

if (process.argv.length < 3) {
  console.error("usage: node verify_seogu_reference_clone_e2e.mjs <LOCAL_BASE_URL>");
  process.exit(2);
}
let BASE = process.argv[2];
if (!BASE.endsWith("/")) BASE += "/";

function isLocal(url) {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/^\[|\]$/g, "");
    return (
      (parsed.protocol === "http:" || parsed.protocol === "https:") &&
      (host === "127.0.0.1" || host === "localhost" || host === "::1")
    );
  } catch {
    return false;
  }
}

import { chromium } from "playwright";

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
  for (const p of KNOWN_BROWSER_PATHS) {
    let exists = false;
    try {
      readFileSync(p);
      exists = true;
    } catch (_) {}
    if (exists) {
      attempts.push({
        name: `path: ${p}`,
        launch: () => chromium.launch({ headless: true, executablePath: p }),
      });
    }
  }
  attempts.push({
    name: "default playwright chromium",
    launch: () => chromium.launch({ headless: true }),
  });
  for (const attempt of attempts) {
    try {
      const browser = await attempt.launch();
      console.log(`  Browser launched (${attempt.name}) ✓`);
      return browser;
    } catch (e) {
      errors.push(`  [${attempt.name}] ${e.message}`);
    }
  }
  throw new Error(`Cannot launch any browser. Attempts:\n${errors.join("\n")}`);
}

const REQUIRED_ROUTES = [
  "", // root = /seogu/ home
  "notice/",
  "notice/detail/",
  "gosi/",
  "gosi/detail/",
  "civil-form/",
  "civil-form/detail/",
  "organization/",
  "staff/",
  "home/gnb-open/",
  "home/mobile/",
];

const FAMILIES = [
  { list: "notice/", detail: "notice/detail/", marker: "143106" },
  { list: "gosi/", detail: "gosi/detail/", marker: "고시/공고" },
  { list: "civil-form/", detail: "civil-form/detail/", marker: "143010" },
];

async function waitForServer(base, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(base + "/");
      if (res.ok) return;
    } catch (_) {
      /* not ready */
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("Seo-gu clone server did not become ready");
}

async function main() {
  await waitForServer(BASE);

  const browser = await launchBrowser();
  const externalRequests = [];
  const interceptedRequests = [];
  const pageErrors = [];

  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      reducedMotion: "reduce",
    });

    // Context-wide interception: abort any non-loopback request.
    await context.route("**/*", (route) => {
      const url = route.request().url();
      interceptedRequests.push(url);
      if (isLocal(url)) route.continue();
      else {
        externalRequests.push(url);
        route.abort();
      }
    });
    context.on("weberror", (e) => pageErrors.push("weberror: " + e.error().message));
    context.on("console", (msg) => {
      if (msg.type() === "error") pageErrors.push("console: " + msg.text());
    });

    const page = await context.newPage();

    // ── ROUTE availability (all modeled routes serve 200 + html) ──────────
    for (const route of REQUIRED_ROUTES) {
      const res = await fetch(BASE + route);
      assert.strictEqual(
        res.status,
        200,
        `route not served 200: ${route} (${res.status})`,
      );
      assert.ok(
        (res.headers.get("content-type") || "").includes("text/html"),
        `route not html: ${route}`,
      );
    }
    console.log(`  routes: ${REQUIRED_ROUTES.length} modeled routes served 200`);

    // ── ROOT content (recognizable Seo-gu captured title) ────────────────
    await page.goto(BASE, { waitUntil: "networkidle", timeout: 15000 });
    const rootTitle = await page.title();
    assert.ok(rootTitle.includes("서구청"), "root must show captured Seo-gu title");
    assert.ok(rootTitle.includes("착한도시 서구"), "root must show captured site tag");
    const rootHtml = await page.content();
    assert.ok(
      rootHtml.includes('id="rc-lifecycle"'),
      "lifecycle markers must be embedded",
    );
    assert.ok(
      rootHtml.includes('"faithful_clone_candidate": true'),
      "lifecycle faithful_clone_candidate must be true",
    );
    assert.ok(
      rootHtml.includes('"asset_byte_fidelity_complete": false'),
      "lifecycle asset_byte_fidelity_complete must be false",
    );

    // ── GNB open/close interaction ────────────────────────────────────────
    const toggle = await page.$("#rc-gnb-toggle");
    assert.ok(toggle, "GNB toggle button must exist on root");
    let expanded = await page.getAttribute("#rc-gnb-toggle", "aria-expanded");
    assert.strictEqual(expanded, "false", "GNB starts collapsed on root");
    await page.click("#rc-gnb-toggle");
    expanded = await page.getAttribute("#rc-gnb-toggle", "aria-expanded");
    assert.strictEqual(expanded, "true", "GNB opens on click");
    const panelVisible = await page.isVisible("#rc-mega-menu");
    assert.ok(panelVisible, "mega-menu panel must be visible when open");
    await page.keyboard.press("Escape");
    expanded = await page.getAttribute("#rc-gnb-toggle", "aria-expanded");
    assert.strictEqual(expanded, "false", "Escape closes GNB");
    console.log("  GNB open/close interaction OK");

    // ── list -> detail local navigation (all three families) ─────────────
    for (const fam of FAMILIES) {
      await page.goto(BASE + fam.list, { waitUntil: "networkidle", timeout: 15000 });
      const link = await page.$("a.rc-list-link[data-detail='1']");
      assert.ok(link, `list->detail link missing for ${fam.list}`);
      await Promise.all([
        page.waitForNavigation({ waitUntil: "networkidle", timeout: 15000 }),
        link.click(),
      ]);
      const url = page.url();
      assert.ok(
        url.endsWith(fam.detail),
        `expected to land on ${fam.detail}, got ${url}`,
      );
      const detailHtml = await page.content();
      assert.ok(
        detailHtml.includes(fam.marker),
        `detail for ${fam.list} missing captured marker ${fam.marker}`,
      );
      // attachment affordance visible but inert.
      const attachCount = await page.$$eval("button.rc-attach", (els) => els.length);
      assert.ok(attachCount >= 1, `detail for ${fam.list} missing attachment affordance`);
      const allDisabled = await page.$$eval("button.rc-attach", (els) =>
        els.every((e) => e.hasAttribute("disabled") || e.getAttribute("aria-disabled") === "true"),
      );
      assert.ok(allDisabled, `detail for ${fam.list} attachment must be inert`);
      console.log(`  ${fam.list} -> ${fam.detail} navigation OK (marker ${fam.marker})`);
    }

    // ── organization / staff reachable ───────────────────────────────────
    for (const route of ["organization/", "staff/"]) {
      const res = await fetch(BASE + route);
      assert.strictEqual(res.status, 200, `${route} not reachable`);
      await page.goto(BASE + route, { waitUntil: "networkidle", timeout: 15000 });
      const html = await page.content();
      assert.ok(html.includes("서구소개") || html.includes("청사안내"), `${route} content missing`);
    }
    console.log("  organization/staff reachable OK");

    // ── attachment affordance on notice detail (explicit) ────────────────
    await page.goto(BASE + "notice/detail/", { waitUntil: "networkidle", timeout: 15000 });
    const hwpx = await page.$$eval("button.rc-attach", (els) =>
      els.some((e) => (e.getAttribute("data-attachment-ext") || "").includes("hwpx")),
    );
    assert.ok(hwpx, "notice detail must surface the .hwpx attachment affordance");

    // ── Responsive: no material horizontal overflow ──────────────────────
    for (const vp of [
      { width: 1440, height: 900 },
      { width: 390, height: 844 },
    ]) {
      await page.setViewportSize(vp);
      await page.goto(BASE, { waitUntil: "networkidle", timeout: 15000 });
      const overflow = await page.evaluate(() => {
        const de = document.documentElement;
        return de.scrollWidth - window.innerWidth;
      });
      assert.ok(
        overflow <= 1,
        `horizontal overflow at ${vp.width}x${vp.height}: ${overflow}px`,
      );
    }
    console.log("  responsive overflow check OK (1440x900, 390x844)");

    // ── Basic keyboard/focus accessibility ───────────────────────────────
    await page.goto(BASE, { waitUntil: "networkidle", timeout: 15000 });
    await page.focus("#rc-gnb-toggle");
    const focusedId = await page.evaluate(
      () => document.activeElement && document.activeElement.id,
    );
    assert.strictEqual(focusedId, "rc-gnb-toggle", "GNB toggle must be keyboard-focusable");
    console.log("  keyboard/focus accessibility OK");

    // ── NETWORK: zero external requests ─────────────────────────────────
    assert.deepStrictEqual(
      externalRequests,
      [],
      `external requests: ${externalRequests.join(", ")}`,
    );
    assert.strictEqual(externalRequests.length, 0, "external request count must be 0");
    for (const url of interceptedRequests) {
      assert.ok(isLocal(url), `non-loopback request slipped through: ${url}`);
      assert.ok(
        !url.includes("seogu.gwangju.kr"),
        `request to actual seogu host: ${url}`,
      );
    }
    assert.deepStrictEqual(pageErrors, [], `page errors: ${pageErrors.join("\n")}`);
    console.log(
      `  network: ${interceptedRequests.length} intercepted (all loopback), ` +
        `${externalRequests.length} external`,
    );

    await browser.close();
    console.log("Seo-gu G2-B faithful clone browser QA passed.");
  } finally {
    try {
      await browser.close();
    } catch (_) {}
  }
}

main().catch((error) => {
  console.error("Seo-gu G2-B faithful clone browser QA FAILED:");
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
