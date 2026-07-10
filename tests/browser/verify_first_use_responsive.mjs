// tests/browser/verify_first_use_responsive.mjs
//
// Deterministic real-browser responsive contract for #1064.
//
// Verifies that the citizen first-use shell has NO horizontal document
// overflow and that entry/split chat + canvas surfaces, header, thread,
// chips, composer, input and send button all stay inside the viewport at
// 320 / 390 / 768 / 1440 px. All external (non-localhost) requests are
// aborted so this never performs real network / provider / API / Cloudflare
// calls.
//
// Uses only Playwright (no other runtime deps). The static site is built
// locally and served from 127.0.0.1 only.

import assert from "node:assert";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { chromium } from "playwright";

const REPO = path.resolve(fileURLToPath(import.meta.url), "../../..");
const DIST_DIR = path.join(REPO, "dist", "cloudflare-pages");
const PORT = 4173;
const BASE = `http://127.0.0.1:${PORT}/mvp/`;

const VIEWPORTS = [
  { width: 320, height: 568 },
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
];

const TOL = 1.5; // sub-pixel rounding tolerance (px)

function run(cmd, args, opts = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { cwd: REPO, ...opts });
    let stdout = "";
    let stderr = "";
    child.stdout && child.stdout.on("data", (d) => (stdout += d));
    child.stderr && child.stderr.on("data", (d) => (stderr += d));
    child.on("error", reject);
    child.on("close", (code) =>
      code === 0
        ? resolve({ stdout, stderr, code })
        : reject(new Error(`${cmd} ${args.join(" ")} exited ${code}\n${stderr}`)),
    );
  });
}

async function pickPython() {
  for (const exe of ["python3", "python"]) {
    try {
      await run(exe, ["--version"]);
      return exe;
    } catch {
      /* try next */
    }
  }
  throw new Error("python3/python not found");
}

async function launchBrowser() {
  const attempts = [];
  try {
    return await chromium.launch({ headless: true, channel: "chrome" });
  } catch (e) {
    attempts.push(`channel=chrome -> ${e.message.split("\n")[0]}`);
  }
  try {
    return await chromium.launch({ headless: true });
  } catch (e) {
    attempts.push(`bundled chromium -> ${e.message.split("\n")[0]}`);
  }
  const err = new Error(
    "No browser available to run responsive geometry checks. " +
      "Install Google Chrome (system) or `npx playwright install chromium`.\n  " +
      attempts.join("\n  "),
  );
  err.attempts = attempts;
  throw err;
}

function measure(page) {
  return page.evaluate(() => {
    const html = document.documentElement;
    const body = document.body;
    const q = (sel) => document.querySelector(sel);
    const rect = (el) =>
      el ? el.getBoundingClientRect() : { left: 0, right: 0, top: 0, bottom: 0, width: 0, height: 0 };
    const chat = q(".chat-shell");
    const header = q(".chat-shell__header");
    const thread = q(".chat-thread");
    const chips = q(".chat-chips");
    const composer = q(".chat-composer");
    const input = q(".chat-composer__input");
    const send = q(".chat-composer__send");
    const canvas = q(".demo-canvas");
    const chipsEls = chips ? Array.from(chips.querySelectorAll(".chat-chip")) : [];
    return {
      viewportWidth: window.innerWidth,
      state: body.getAttribute("data-first-use-state"),
      htmlScrollWidth: html.scrollWidth,
      bodyScrollWidth: body.scrollWidth,
      htmlClientWidth: html.clientWidth,
      chat: rect(chat),
      header: rect(header),
      thread: rect(thread),
      chips: rect(chips),
      composer: rect(composer),
      input: rect(input),
      send: rect(send),
      canvas: rect(canvas),
      chipsBox: rect(chips),
      chipRects: chipsEls.map((c) => ({
        left: c.getBoundingClientRect().left,
        right: c.getBoundingClientRect().right,
        width: c.getBoundingClientRect().width,
      })),
    };
  });
}

function assertNoHorizontalOverflow(m, ctx) {
  const label = `viewport=${m.viewportWidth} state=${m.state}`;
  assert.ok(
    m.htmlScrollWidth <= m.htmlClientWidth + TOL,
    `${label}: document.documentElement.scrollWidth (${m.htmlScrollWidth}) must not exceed clientWidth (${m.htmlClientWidth}) [${ctx}]`,
  );
  assert.ok(
    m.bodyScrollWidth <= m.viewportWidth + TOL,
    `${label}: document.body.scrollWidth (${m.bodyScrollWidth}) must not exceed viewportWidth (${m.viewportWidth}) [${ctx}]`,
  );
}

function assertInsideChat(childRect, chatRect, name, ctx) {
  // Allow a tiny tolerance; elements must not spill outside the chat shell.
  assert.ok(
    childRect.left >= chatRect.left - TOL,
    `${name} left (${childRect.left}) must be >= chat left (${chatRect.left}) [${ctx}]`,
  );
  assert.ok(
    childRect.right <= chatRect.right + TOL,
    `${name} right (${childRect.right}) must be <= chat right (${chatRect.right}) [${ctx}]`,
  );
}

function assertInsideViewport(rect, name, ctx, vw) {
  assert.ok(
    rect.left >= -TOL,
    `${name} left (${rect.left}) must be >= 0 [${ctx}]`,
  );
  assert.ok(
    rect.right <= vw + TOL,
    `${name} right (${rect.right}) must be <= viewportWidth (${vw}) [${ctx}]`,
  );
}

async function runOneState(page, viewport, state) {
  const ctx = `viewport=${viewport.width} state=${state}`;
  await page.setViewportSize({ width: viewport.width, height: viewport.height });
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".chat-shell", { timeout: 10000 });
  // Disable transitions/animations so geometry is final and deterministic
  // (the shell has a 1100ms width/transform transition that would otherwise
  // leave measurements mid-flight). This only affects the test harness.
  await page.addStyleTag({ content: "*{animation:none !important;transition:none !important;}" });
  if (state === "split") {
    // Force the split layout without any network/bridge (static, offline).
    await page.evaluate(() => {
      document.body.setAttribute("data-first-use-state", "split");
    });
    await page.waitForTimeout(120);
  }

  const m = await measure(page);
  assertNoHorizontalOverflow(m, ctx);
  assertInsideViewport(m.chat, "chat-shell", ctx, viewport.width);

  if (state === "entry") {
    assertInsideChat(m.header, m.chat, "header", ctx);
    assertInsideChat(m.thread, m.chat, "thread", ctx);
    assertInsideChat(m.chips, m.chat, "chips", ctx);
    assertInsideChat(m.composer, m.chat, "composer", ctx);
    assertInsideChat(m.input, m.chat, "input", ctx);
    assertInsideChat(m.send, m.chat, "send", ctx);
    // Each chip must stay within the chips container (no intrinsic-width overflow).
    for (let i = 0; i < m.chipRects.length; i++) {
      const c = m.chipRects[i];
      assert.ok(
        c.left >= m.chipsBox.left - TOL,
        `chip[${i}] left (${c.left}) must be >= chips.left (${m.chipsBox.left}) [${ctx}]`,
      );
      assert.ok(
        c.right <= m.chipsBox.right + TOL,
        `chip[${i}] right (${c.right}) must be <= chips.right (${m.chipsBox.right}) [${ctx}]`,
      );
      assert.ok(
        c.width <= m.chipsBox.width + TOL,
        `chip[${i}] width (${c.width}) must not exceed chips width (${m.chipsBox.width}) [${ctx}]`,
      );
    }
  } else {
    // split: chat + canvas must both remain inside the viewport.
    assertInsideViewport(m.canvas, "demo-canvas", ctx, viewport.width);
    assertInsideViewport(m.composer, "composer", ctx, viewport.width);
    assertInsideViewport(m.input, "input", ctx, viewport.width);
    assertInsideViewport(m.send, "send", ctx, viewport.width);
  }

  // Focus visibility: focusing input/send must keep them inside chat + viewport.
  await page.locator(".chat-composer__input").focus();
  await page.locator(".chat-composer__send").focus();
  const afterFocus = await measure(page);
  assertInsideChat(afterFocus.input, afterFocus.chat, "input(after focus)", ctx);
  assertInsideChat(afterFocus.send, afterFocus.chat, "send(after focus)", ctx);
  assertInsideViewport(afterFocus.input, "input(after focus)", ctx, viewport.width);
  assertInsideViewport(afterFocus.send, "send(after focus)", ctx, viewport.width);

  console.log(
    `  [${viewport.width}px ${state}] htmlSW=${m.htmlScrollWidth} bodySW=${m.bodyScrollWidth} ` +
      `chat=[${Math.round(m.chat.left)},${Math.round(m.chat.right)}] chips=${m.chipRects.length} -> OK`,
  );
}

async function main() {
  console.log("Running first-use responsive browser contract (no network):");

  const python = await pickPython();
  console.log("  building static site with", python);
  await run(python, ["scripts/build_cloudflare_pages.py"]);
  assert.ok(fs.existsSync(path.join(DIST_DIR, "mvp", "index.html")), "dist build missing mvp/index.html");

  const server = spawn(
    python,
    ["-m", "http.server", String(PORT), "--bind", "127.0.0.1", "--directory", DIST_DIR],
    { cwd: REPO, stdio: "ignore" },
  );

  let browser;
  try {
    browser = await launchBrowser();
  } catch (e) {
    server.kill("SIGTERM");
    console.warn("\n⚠ RESPONSIVE BROWSER TEST SKIPPED:\n  " + e.message + "\n");
    process.exit(0); // smallest stable CI path: skip when no browser is installed
  }

  const failures = [];
  try {
    const context = await browser.newContext({ viewport: VIEWPORTS[0] });
    // Block all non-localhost requests so no real network/provider/API happens.
    await context.route("**", (route) => {
      const url = route.request().url();
      if (url.startsWith(`http://127.0.0.1:${PORT}`) || url.startsWith(`http://localhost:${PORT}`)) {
        return route.continue();
      }
      return route.abort();
    });
    const page = await context.newPage();
    page.on("pageerror", (err) => failures.push("pageerror: " + err.message));

    for (const vp of VIEWPORTS) {
      for (const state of ["entry", "split"]) {
        try {
          await runOneState(page, vp, state);
        } catch (err) {
          failures.push(`viewport=${vp.width} state=${state}: ${err.message}`);
        }
      }
    }
    await context.close();
  } finally {
    await browser.close();
    server.kill("SIGTERM");
  }

  if (failures.length) {
    console.error("\nRESPONSIVE CONTRACT FAILED:");
    for (const f of failures) console.error("  - " + f);
    process.exit(1);
  }
  console.log("All first-use responsive geometry checks passed.");
}

main().catch((err) => {
  console.error("Responsive browser contract error:");
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
