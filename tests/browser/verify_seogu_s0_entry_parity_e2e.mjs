/**
 * #1349/#1350 — Seo-gu S0 cold-entry visual/containment contract.
 * Local build only; every non-loopback request is blocked.
 */
import assert from "assert";
import { existsSync } from "fs";
import { chromium } from "playwright";

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

async function launchBrowser() {
  const attempts = [];
  const errors = [];
  const envPath = process.env.PREVIEW_BROWSER_EXECUTABLE;
  if (envPath) attempts.push({ name: `env: ${envPath}`, launch: () => chromium.launch({ headless: true, executablePath: envPath }) });
  attempts.push({ name: "channel: chrome", launch: () => chromium.launch({ headless: true, channel: "chrome" }) });
  for (const path of KNOWN_BROWSER_PATHS) {
    if (!existsSync(path)) continue;
    attempts.push({ name: `path: ${path}`, launch: () => chromium.launch({ headless: true, executablePath: path }) });
  }
  attempts.push({ name: "default playwright chromium", launch: () => chromium.launch({ headless: true }) });
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

const rawBase = process.argv[2] || "http://127.0.0.1:8772";
const parsedBase = new URL(rawBase);
if (parsedBase.protocol !== "http:" || !["127.0.0.1", "localhost", "::1"].includes(parsedBase.hostname)) {
  throw new Error(`local http origin required, got ${rawBase}`);
}
const BASE_ORIGIN = parsedBase.origin;
const DEMO_URL = `${BASE_ORIGIN}/static/seogu-citizen-action-demo.html`;
const browser = await launchBrowser();
const externalRequests = [];

async function installGuard(context) {
  await context.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.startsWith("data:")) return route.continue();
    let parsed;
    try { parsed = new URL(url); } catch {
      externalRequests.push(url);
      return route.abort();
    }
    if (parsed.origin !== BASE_ORIGIN) {
      externalRequests.push(url);
      return route.abort();
    }
    return route.continue();
  });
}

async function openEntry(context) {
  const page = await context.newPage();
  await page.goto(DEMO_URL, { waitUntil: "networkidle", timeout: 20000 });
  await page.waitForFunction(() => document.querySelectorAll("#chat-chips .chat-chip").length === 8, null, { timeout: 15000 });
  await page.waitForFunction(() => {
    const chat = document.getElementById("chat-shell");
    if (!chat || typeof chat.getAnimations !== "function") return false;
    return chat.getAnimations().every((animation) => animation.playState === "finished");
  }, null, { timeout: 4000 });
  return page;
}

function requirePositiveRect(value, label) {
  assert.ok(value && value.w > 0 && value.h > 0, `${label} must have a positive visible rect: ${JSON.stringify(value)}`);
}

try {
  /* ═══════════════════════════ DESKTOP 1920×1080 ═══════════════════════════ */
  const desktop = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  await installGuard(desktop);
  const page = await openEntry(desktop);
  const desktopState = await page.evaluate(() => {
    const rect = (node) => {
      if (!node) return null;
      const r = node.getBoundingClientRect();
      const s = getComputedStyle(node);
      return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), bottom: Math.round(r.bottom), display: s.display, visibility: s.visibility };
    };
    const logo = document.querySelector(".entry-stage__brand-mark");
    const mayor = document.querySelector(".seogu-mayor-image");
    const keyVisual = document.querySelector(".seogu-key-visual");
    const card = document.querySelector(".seogu-entry-profile-card");
    const logoRect = logo ? (() => {
      const r = logo.getBoundingClientRect();
      const s = getComputedStyle(logo);
      return {
        x: Math.round(r.x), y: Math.round(r.y),
        w: Math.round(r.width), h: Math.round(r.height),
        display: s.display, visibility: s.visibility,
        naturalW: logo.naturalWidth, naturalH: logo.naturalHeight,
      };
    })() : null;
    return {
      firstUseState: document.body.getAttribute("data-first-use-state"),
      logoSrc: logo ? logo.getAttribute("src") : "",
      logoLoaded: logo ? logo.complete && logo.naturalWidth > 0 : false,
      logoRect,
      mayorSrc: mayor ? mayor.getAttribute("src") : "",
      mayorLoaded: mayor ? mayor.complete && mayor.naturalWidth > 0 : false,
      keyVisualSrc: keyVisual ? keyVisual.getAttribute("src") : "",
      keyVisualLoaded: keyVisual ? keyVisual.complete && keyVisual.naturalWidth > 0 : false,
      card: rect(card),
      brand: rect(document.querySelector(".entry-stage__brand--seogu")),
      chat: rect(document.getElementById("chat-shell")),
      composer: rect(document.getElementById("chat-composer-form")),
      send: rect(document.getElementById("chat-composer-send")),
      chipCount: document.querySelectorAll("#chat-chips .chat-chip").length,
      horizontalOverflow: document.documentElement.scrollWidth - window.innerWidth,
    };
  });

  assert.strictEqual(desktopState.firstUseState, "entry");
  assert.strictEqual(desktopState.chipCount, 8);
  assert.ok(desktopState.card && desktopState.card.w >= 300 && desktopState.card.h >= 100, `desktop profile card geometry: ${JSON.stringify(desktopState.card)}`);
  assert.notStrictEqual(desktopState.card.display, "none");
  assert.notStrictEqual(desktopState.card.visibility, "hidden");

  // Verify official Seo-gu images loaded
  assert.ok(desktopState.logoLoaded, `official logo not loaded: src=${desktopState.logoSrc}`);
  assert.ok(desktopState.mayorLoaded, `official mayor image not loaded: src=${desktopState.mayorSrc}`);
  assert.ok(desktopState.keyVisualLoaded, `official key visual not loaded: src=${desktopState.keyVisualSrc}`);

  // Logo visual scale verification (#1350 logo scale fix)
  const lr = desktopState.logoRect;
  assert.ok(lr, "logo element must exist");
  assert.ok(lr.w > 0 && lr.h > 0, `logo must have positive rendered size: ${JSON.stringify(lr)}`);
  assert.notStrictEqual(lr.display, "none", "logo must not be display:none");
  assert.notStrictEqual(lr.visibility, "hidden", "logo must not be visibility:hidden");
  assert.ok(lr.w >= 60, `logo rendered width too small for legibility: ${JSON.stringify(lr)}`);
  assert.ok(lr.h >= 20, `logo rendered height too small for legibility: ${JSON.stringify(lr)}`);
  assert.ok(lr.x >= 0 && lr.x < 1920, `logo must be inside viewport horizontally: ${JSON.stringify(lr)}`);
  assert.ok(lr.y >= 0 && lr.y < 1080, `logo must be inside viewport vertically: ${JSON.stringify(lr)}`);
  // Aspect ratio check: logo is a wide horizontal mark, not square
  assert.ok(lr.w > lr.h, `logo should be wider than tall (horizontal mark): ${JSON.stringify(lr)}`);

  assert.ok(desktopState.brand && desktopState.brand.w > 100, `Seo-gu identity lockup: ${JSON.stringify(desktopState.brand)}`);
  assert.ok(desktopState.chat && desktopState.chat.w >= 560 && desktopState.chat.w <= 680, `desktop chat width: ${JSON.stringify(desktopState.chat)}`);
  assert.ok(desktopState.chat && desktopState.chat.h >= 410 && desktopState.chat.h <= 540, `desktop chat height: ${JSON.stringify(desktopState.chat)}`);
  requirePositiveRect(desktopState.composer, "desktop composer");
  requirePositiveRect(desktopState.send, "desktop send");
  assert.ok(desktopState.horizontalOverflow <= 1, `desktop horizontal overflow=${desktopState.horizontalOverflow}`);
  await desktop.close();

  /* ═══════════════════════════ MOBILE 390×844 ═════════════════════════════ */
  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await installGuard(mobile);
  const mpage = await openEntry(mobile);
  const mobileState = await mpage.evaluate(() => {
    const rect = (node) => {
      if (!node) return null;
      const r = node.getBoundingClientRect();
      const s = getComputedStyle(node);
      return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), bottom: Math.round(r.bottom), display: s.display, visibility: s.visibility };
    };
    const switchEl = document.getElementById("mobile-surface-switch");
    const chat = document.getElementById("chat-shell");
    return {
      firstUseState: document.body.getAttribute("data-first-use-state"),
      siteId: document.body.getAttribute("data-site-id"),
      switchHidden: switchEl ? switchEl.hasAttribute("hidden") : true,
      chat: rect(chat),
      composer: rect(document.getElementById("chat-composer-form")),
      disclosure: rect(document.getElementById("shell-disclosure")),
      send: rect(document.getElementById("chat-composer-send")),
      chipCount: document.querySelectorAll("#chat-chips .chat-chip").length,
      horizontalOverflow: document.documentElement.scrollWidth - window.innerWidth,
      viewportHeight: window.innerHeight,
    };
  });

  console.log("SEOGU_S0_MOBILE_GEOMETRY " + JSON.stringify(mobileState));
  assert.strictEqual(mobileState.firstUseState, "entry");
  assert.strictEqual(mobileState.siteId, "seogu_gwangju");
  assert.strictEqual(mobileState.chipCount, 8);
  // #1350: surface switch must remain hidden at cold entry
  assert.strictEqual(mobileState.switchHidden, true, "mobile surface switch must be hidden at cold entry");
  requirePositiveRect(mobileState.chat, "mobile chat");
  requirePositiveRect(mobileState.composer, "mobile composer");
  requirePositiveRect(mobileState.send, "mobile send");
  requirePositiveRect(mobileState.disclosure, "mobile disclosure");
  assert.ok(
    mobileState.composer.bottom <= mobileState.viewportHeight + 2,
    `mobile composer clipped below viewport: ${JSON.stringify(mobileState)}`,
  );
  assert.ok(
    mobileState.disclosure.bottom <= mobileState.viewportHeight + 5,
    `mobile disclosure clipped below viewport: ${JSON.stringify(mobileState)}`,
  );
  assert.ok(mobileState.horizontalOverflow <= 1, `mobile horizontal overflow=${mobileState.horizontalOverflow}`);
  await mobile.close();

  /* ═══════════════════════════ FINAL ═══════════════════════════════════════ */
  assert.deepStrictEqual(externalRequests, [], `external runtime requests are forbidden:\n${externalRequests.join("\n")}`);
  console.log("Seo-gu S0 cold-entry visual/containment contract PASS");
} finally {
  await browser.close();
}
