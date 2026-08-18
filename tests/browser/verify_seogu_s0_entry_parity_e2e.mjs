/**
 * #1349 — Seo-gu S0 cold-entry visual/containment contract.
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
    const card = document.querySelector(".seogu-entry-profile-card");
    return {
      firstUseState: document.body.getAttribute("data-first-use-state"),
      cardText: card ? card.textContent.replace(/\s+/g, " ").trim() : "",
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
  assert.ok(desktopState.card && desktopState.card.w >= 300 && desktopState.card.h >= 240, `desktop profile card geometry: ${JSON.stringify(desktopState.card)}`);
  assert.notStrictEqual(desktopState.card.display, "none");
  assert.notStrictEqual(desktopState.card.visibility, "hidden");
  for (const marker of ["#착한도시 서구", "김이강", "내곁에 구청장실", "매니페스토 (공약)"]) {
    assert.ok(desktopState.cardText.includes(marker), `missing source-grounded S0 marker: ${marker}`);
  }
  assert.ok(desktopState.brand && desktopState.brand.w > 100, `Seo-gu identity lockup: ${JSON.stringify(desktopState.brand)}`);
  assert.ok(desktopState.chat && desktopState.chat.w >= 560 && desktopState.chat.w <= 680, `desktop chat width: ${JSON.stringify(desktopState.chat)}`);
  assert.ok(desktopState.chat && desktopState.chat.h >= 410 && desktopState.chat.h <= 540, `desktop chat height: ${JSON.stringify(desktopState.chat)}`);
  requirePositiveRect(desktopState.composer, "desktop composer");
  requirePositiveRect(desktopState.send, "desktop send");
  assert.ok(desktopState.horizontalOverflow <= 1, `desktop horizontal overflow=${desktopState.horizontalOverflow}`);
  await desktop.close();

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
    const style = (node) => {
      if (!node) return null;
      const s = getComputedStyle(node);
      return {
        height: s.height,
        minHeight: s.minHeight,
        maxHeight: s.maxHeight,
        marginTop: s.marginTop,
        marginBottom: s.marginBottom,
        paddingTop: s.paddingTop,
        paddingBottom: s.paddingBottom,
        gap: s.gap,
        overflowY: s.overflowY,
        transform: s.transform,
        flex: s.flex,
        flexShrink: s.flexShrink,
      };
    };
    const chat = document.getElementById("chat-shell");
    const header = document.querySelector(".chat-shell__header");
    const thread = document.getElementById("chat-thread");
    const chipsRoot = document.getElementById("chat-chips");
    const firstChip = chipsRoot && chipsRoot.querySelector(".chat-chip");
    const composer = document.getElementById("chat-composer-form");
    const disclosure = document.getElementById("shell-disclosure");
    return {
      firstUseState: document.body.getAttribute("data-first-use-state"),
      siteId: document.body.getAttribute("data-site-id"),
      chat: rect(chat),
      header: rect(header),
      thread: rect(thread),
      chips: rect(chipsRoot),
      firstChip: rect(firstChip),
      composer: rect(composer),
      disclosure: rect(disclosure),
      send: rect(document.getElementById("chat-composer-send")),
      chatStyle: style(chat),
      chipsStyle: style(chipsRoot),
      firstChipStyle: style(firstChip),
      composerStyle: style(composer),
      disclosureStyle: style(disclosure),
      chipCount: document.querySelectorAll("#chat-chips .chat-chip").length,
      horizontalOverflow: document.documentElement.scrollWidth - window.innerWidth,
      viewportHeight: window.innerHeight,
      documentScrollHeight: document.documentElement.scrollHeight,
      bodyScrollHeight: document.body.scrollHeight,
    };
  });

  console.log("SEOGU_S0_MOBILE_GEOMETRY " + JSON.stringify(mobileState));
  assert.strictEqual(mobileState.firstUseState, "entry");
  assert.strictEqual(mobileState.siteId, "seogu_gwangju");
  assert.strictEqual(mobileState.chipCount, 8);
  requirePositiveRect(mobileState.chat, "mobile chat");
  requirePositiveRect(mobileState.composer, "mobile composer");
  requirePositiveRect(mobileState.send, "mobile send");
  assert.ok(
    mobileState.composer.bottom <= mobileState.viewportHeight + 2,
    `mobile composer clipped below viewport: ${JSON.stringify(mobileState)}`,
  );
  assert.ok(mobileState.horizontalOverflow <= 1, `mobile horizontal overflow=${mobileState.horizontalOverflow}`);
  await mobile.close();

  assert.deepStrictEqual(externalRequests, [], `external runtime requests are forbidden:\n${externalRequests.join("\n")}`);
  console.log("Seo-gu S0 cold-entry visual/containment contract PASS");
} finally {
  await browser.close();
}
