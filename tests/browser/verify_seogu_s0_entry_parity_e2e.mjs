/**
 * #1349 — Seo-gu S0 cold-entry visual/containment contract.
 *
 * Local build only. No external site/provider requests are allowed.
 * Proves the fresh Seo-gu first screen is no longer a blank hero shell while
 * preserving the Buk-gu-family chat geometry and mobile containment.
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
  if (envPath) {
    attempts.push({ name: `env: ${envPath}`, launch: () => chromium.launch({ headless: true, executablePath: envPath }) });
  }
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
}

async function openEntry(context) {
  const page = await context.newPage();
  await page.goto(DEMO_URL, { waitUntil: "networkidle", timeout: 20000 });
  await page.waitForFunction(
    () => document.querySelectorAll("#chat-chips .chat-chip").length === 8,
    null,
    { timeout: 15000 },
  );
  // The canonical Buk-gu-family cold entry intentionally animates the chat card
  // into place for 900ms. Geometry acceptance must measure the stable S0 state,
  // not an in-flight translateY frame that can temporarily cross the viewport.
  await page.waitForFunction(
    () => {
      const chat = document.getElementById("chat-shell");
      if (!chat || typeof chat.getAnimations !== "function") return false;
      return chat.getAnimations().every((animation) => animation.playState === "finished");
    },
    null,
    { timeout: 4000 },
  );
  return page;
}

try {
  const desktop = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  await installGuard(desktop);
  const page = await openEntry(desktop);

  const desktopState = await page.evaluate(() => {
    const card = document.querySelector(".seogu-entry-profile-card");
    const brand = document.querySelector(".entry-stage__brand--seogu");
    const chat = document.getElementById("chat-shell");
    const composer = document.getElementById("chat-composer-form");
    const send = document.getElementById("chat-composer-send");
    const chips = document.querySelectorAll("#chat-chips .chat-chip");

    const rect = (node) => {
      if (!node) return null;
      const r = node.getBoundingClientRect();
      const s = getComputedStyle(node);
      return {
        x: Math.round(r.x),
        y: Math.round(r.y),
        w: Math.round(r.width),
        h: Math.round(r.height),
        display: s.display,
        visibility: s.visibility,
      };
    };

    return {
      firstUseState: document.body.getAttribute("data-first-use-state"),
      cardText: card ? card.textContent.replace(/\s+/g, " ").trim() : "",
      card: rect(card),
      brand: rect(brand),
      chat: rect(chat),
      composer: rect(composer),
      send: rect(send),
      chipCount: chips.length,
      horizontalOverflow: document.documentElement.scrollWidth - window.innerWidth,
    };
  });

  assert.strictEqual(desktopState.firstUseState, "entry", "desktop must boot in cold-entry state");
  assert.strictEqual(desktopState.chipCount, 8, "desktop must expose all eight canonical resident chips");
  assert.ok(desktopState.card, "Seo-gu civic profile card must exist");
  assert.ok(desktopState.card.w >= 300, `profile card too narrow: ${desktopState.card.w}`);
  assert.ok(desktopState.card.h >= 240, `profile card too short: ${desktopState.card.h}`);
  assert.notStrictEqual(desktopState.card.display, "none", "profile card must be displayed");
  assert.notStrictEqual(desktopState.card.visibility, "hidden", "profile card must be visible");
  for (const marker of ["#착한도시 서구", "김이강", "내곁에 구청장실", "매니페스토 (공약)"]) {
    assert.ok(desktopState.cardText.includes(marker), `missing source-grounded S0 marker: ${marker}`);
  }
  assert.ok(desktopState.brand && desktopState.brand.w > 100, "Seo-gu identity lockup must be populated");
  assert.ok(desktopState.chat && desktopState.chat.w >= 560 && desktopState.chat.w <= 680,
    `desktop entry chat width outside Buk-gu-family bounds: ${desktopState.chat && desktopState.chat.w}`);
  assert.ok(desktopState.chat && desktopState.chat.h >= 410 && desktopState.chat.h <= 540,
    `desktop entry chat height outside Buk-gu-family bounds: ${desktopState.chat && desktopState.chat.h}`);
  assert.ok(desktopState.composer && desktopState.composer.w > 0 && desktopState.composer.h > 0,
    "desktop composer must remain visible");
  assert.ok(desktopState.send && desktopState.send.w > 0 && desktopState.send.h > 0,
    "desktop send control must remain visible");
  assert.ok(desktopState.horizontalOverflow <= 1,
    `desktop horizontal overflow detected: ${desktopState.horizontalOverflow}px`);

  await desktop.close();

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await installGuard(mobile);
  const mpage = await openEntry(mobile);

  const mobileState = await mpage.evaluate(() => {
    const chat = document.getElementById("chat-shell");
    const composer = document.getElementById("chat-composer-form");
    const send = document.getElementById("chat-composer-send");
    const chips = document.querySelectorAll("#chat-chips .chat-chip");

    const rect = (node) => {
      if (!node) return null;
      const r = node.getBoundingClientRect();
      const s = getComputedStyle(node);
      return {
        x: Math.round(r.x),
        y: Math.round(r.y),
        w: Math.round(r.width),
        h: Math.round(r.height),
        bottom: Math.round(r.bottom),
        display: s.display,
        visibility: s.visibility,
      };
    };

    return {
      firstUseState: document.body.getAttribute("data-first-use-state"),
      chat: rect(chat),
      composer: rect(composer),
      send: rect(send),
      chipCount: chips.length,
      horizontalOverflow: document.documentElement.scrollWidth - window.innerWidth,
      viewportHeight: window.innerHeight,
    };
  });

  assert.strictEqual(mobileState.firstUseState, "entry", "mobile must boot in cold-entry state");
  assert.strictEqual(mobileState.chipCount, 8, "mobile must expose all eight canonical resident chips");
  assert.ok(mobileState.chat && mobileState.chat.w > 0 && mobileState.chat.h > 0, "mobile chat must be visible");
  assert.ok(mobileState.composer && mobileState.composer.w > 0 && mobileState.composer.h > 0,
    "mobile composer must remain usable");
  assert.ok(mobileState.composer.bottom <= mobileState.viewportHeight + 2,
    `mobile composer clipped below viewport: bottom=${mobileState.composer.bottom}, viewport=${mobileState.viewportHeight}`);
  assert.ok(mobileState.send && mobileState.send.w > 0 && mobileState.send.h > 0,
    "mobile send control must remain visible");
  assert.ok(mobileState.horizontalOverflow <= 1,
    `mobile horizontal overflow detected: ${mobileState.horizontalOverflow}px`);

  await mobile.close();

  assert.deepStrictEqual(
    externalRequests,
    [],
    `external runtime requests are forbidden in #1349 S0 contract:\n${externalRequests.join("\n")}`,
  );

  console.log("Seo-gu S0 cold-entry visual/containment contract PASS");
} finally {
  await browser.close();
}
