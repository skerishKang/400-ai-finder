// tests/browser/verify_first_use_responsive.mjs
//
// Deterministic real-browser responsive contract for #1076.
//
// Hardens the responsive browser contract added in #1075 along three axes:
//   1. A browser launch failure must FAIL (never silently skip).
//   2. Real keyboard focus-visible state of input and send is verified
//      independently.
//   3. The fixed port 4173 collision / wrong-server problem is removed by
//      serving the built static site from an OS-assigned ephemeral port.
//
// The static site is built locally and served from 127.0.0.1 only. All
// external (non-loopback-origin) requests are aborted so this never performs
// real network / provider / API / Cloudflare calls.
//
// Uses only Playwright (no other runtime deps). Browser binaries are NOT
// downloaded; system Google Chrome, channel:"chrome", or an already-installed
// bundled Chromium are used.

import assert from "node:assert";
import { spawn } from "node:child_process";
import http from "node:http";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import { chromium } from "playwright";

const REPO = path.resolve(fileURLToPath(import.meta.url), "../../..");
const DIST_DIR = path.join(REPO, "dist", "cloudflare-pages");

const VIEWPORTS = [
  { width: 320, height: 568 },
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
];

const STATES = ["entry", "split"];

const TOL = 1.5; // sub-pixel rounding tolerance (px)

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
};

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

// Launch a browser using every available source. Throws (never skips) if all
// sources fail. Returns { browser, source, version }.
async function launchBrowser() {
  const attempts = [];

  // 1) system Google Chrome via Playwright channel:"chrome"
  try {
    const browser = await chromium.launch({ headless: true, channel: "chrome" });
    const version = browser.version();
    return { browser, source: "channel=chrome", version };
  } catch (e) {
    attempts.push(`channel=chrome -> ${String(e.message).split("\n")[0]}`);
  }

  // 2) system Chrome at a known path
  try {
    const browser = await chromium.launch({
      headless: true,
      executablePath: "/usr/bin/google-chrome",
    });
    const version = browser.version();
    return { browser, source: "executablePath=/usr/bin/google-chrome", version };
  } catch (e) {
    attempts.push(`/usr/bin/google-chrome -> ${String(e.message).split("\n")[0]}`);
  }

  // 3) already-installed bundled Chromium (no download)
  try {
    const browser = await chromium.launch({ headless: true });
    const version = browser.version();
    return { browser, source: "bundled-chromium", version };
  } catch (e) {
    attempts.push(`bundled chromium -> ${String(e.message).split("\n")[0]}`);
  }

  const err = new Error(
    "No browser available to run responsive geometry checks. " +
      "Install Google Chrome (system) or use an already-installed Playwright " +
      "browser. Browser binary downloads are intentionally disabled.\n  " +
      attempts.join("\n  "),
  );
  err.attempts = attempts;
  throw err;
}

// In-process static file server backed by dist/cloudflare-pages.
// Listens on an OS-assigned port (0) so no fixed-port collision is possible.
async function startServer() {
  assert.ok(fs.existsSync(DIST_DIR), `dist build missing: ${DIST_DIR}`);

  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      try {
        const url = new URL(req.url, "http://127.0.0.1");
        let pathname = decodeURIComponent(url.pathname);

        // Block path traversal.
        const safePath = path
          .normalize(pathname)
          .replace(/^(\.\.[/\\])+/, "")
          .replace(/^[/\\]+/, "");
        if (safePath.includes("..")) {
          res.writeHead(400, { "Content-Type": "text/plain" });
          res.end("bad request");
          return;
        }

        // Default /mvp/ -> mvp/index.html
        let rel = safePath;
        if (rel === "/" || rel === "") rel = "mvp/index.html";
        if (rel.endsWith("/")) rel += "index.html";
        if (rel === "mvp" || rel === "/mvp") rel = "mvp/index.html";

        const filePath = path.join(DIST_DIR, rel);
        // Reject anything escaping DIST_DIR.
        if (!filePath.startsWith(DIST_DIR)) {
          res.writeHead(403, { "Content-Type": "text/plain" });
          res.end("forbidden");
          return;
        }

        fs.readFile(filePath, (err, data) => {
          if (err) {
            res.writeHead(404, { "Content-Type": "text/html; charset=utf-8" });
            res.end(
              "<!doctype html><html><head><title>404</title></head>" +
                "<body><h1>404 Not Found</h1></body></html>",
            );
            return;
          }
          const ext = path.extname(filePath).toLowerCase();
          const type = MIME[ext] || "application/octet-stream";
          res.writeHead(200, { "Content-Type": type });
          res.end(data);
        });
      } catch (e) {
        res.writeHead(500, { "Content-Type": "text/plain" });
        res.end("server error");
      }
    });

    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address();
      const port = addr.port;
      const base = `http://127.0.0.1:${port}/mvp/`;
      resolve({ server, port, base });
    });
  });
}

// Move keyboard focus (Tab) until selector matches document.activeElement,
// within maxTabs attempts. Fails if not reached.
async function focusByKeyboard(page, selector, maxTabs = 30) {
  const matched = await page.evaluate((sel) => {
    return document.activeElement && document.activeElement.matches(sel);
  }, selector);
  if (matched) return true;

  for (let i = 0; i < maxTabs; i++) {
    await page.keyboard.press("Tab");
    const isMatch = await page.evaluate((sel) => {
      const ae = document.activeElement;
      return !!(ae && ae.matches(sel));
    }, selector);
    if (isMatch) return true;
  }
  return false;
}

// Verify a focused element shows a real, visible focus outline and that the
// outline box is not clipped by an overflow ancestor.
async function verifyFocusVisible(page, selector, ctx) {
  const info = await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return { exists: false };
    const cs = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    const outlineWidth = parseFloat(cs.outlineWidth) || 0;
    const outlineOffset = parseFloat(cs.outlineOffset) || 0;
    const focusExtent = outlineWidth + Math.max(outlineOffset, 0);

    const box = {
      left: rect.left - focusExtent,
      right: rect.right + focusExtent,
      top: rect.top - focusExtent,
      bottom: rect.bottom + focusExtent,
    };

    // Walk ancestor chain for clipping containers.
    const clips = [];
    let node = el.parentElement;
    let depth = 0;
    while (node && node !== document.documentElement && depth < 50) {
      const ncs = getComputedStyle(node);
      const clip = ["hidden", "clip", "auto", "scroll"].includes(
        ncs.overflow + ncs.overflowX + ncs.overflowY,
      )
        ? ["hidden", "clip", "auto", "scroll"].filter((v) =>
            [ncs.overflow, ncs.overflowX, ncs.overflowY].includes(v),
          )
        : [];
      if (clip.length) {
        const nrect = node.getBoundingClientRect();
        clips.push({
          tag: node.tagName,
          cls: node.className,
          clip,
          rect: {
            left: nrect.left,
            right: nrect.right,
            top: nrect.top,
            bottom: nrect.bottom,
          },
        });
      }
      node = node.parentElement;
      depth++;
    }

    return {
      exists: true,
      selector: sel,
      activeElementMatches: document.activeElement === el,
      focusVisible: el.matches(":focus-visible"),
      focused: el.matches(":focus"),
      outlineStyle: cs.outlineStyle,
      outlineWidth,
      outlineColor: cs.outlineColor,
      outlineOffset,
      rect: {
        left: rect.left,
        right: rect.right,
        top: rect.top,
        bottom: rect.bottom,
      },
      focusExtent,
      box,
      clips,
    };
  }, selector);

  assert.ok(info.exists, `${selector} does not exist [${ctx}]`);
  assert.ok(
    info.activeElementMatches,
    `${selector} is not document.activeElement (got ${"tag"}:${info.activeElementMatches}) [${ctx}]`,
  );
  assert.ok(info.focused, `${selector} is not :focus [${ctx}]`);
  assert.ok(info.focusVisible, `${selector} is not :focus-visible [${ctx}]`);
  assert.ok(
    info.outlineStyle !== "none",
    `${selector} computed outline-style is none [${ctx}]`,
  );
  assert.ok(
    info.outlineWidth >= 1,
    `${selector} outline width (${info.outlineWidth}px) < 1px [${ctx}]`,
  );
  assert.ok(
    info.outlineColor !== "transparent" && info.outlineColor !== "rgba(0, 0, 0, 0)",
    `${selector} outline color is transparent [${ctx}]`,
  );
  assert.ok(
    info.outlineOffset >= 0,
    `${selector} outline offset (${info.outlineOffset}px) < 0 [${ctx}]`,
  );

  // Outline box must stay inside the viewport.
  const vw = await page.evaluate(() => window.innerWidth);
  const vh = await page.evaluate(() => window.innerHeight);
  assert.ok(
    info.box.left >= -TOL && info.box.right <= vw + TOL,
    `${selector} outline box horizontally clipped by viewport ` +
      `[left=${info.box.left} right=${info.box.right} vw=${vw}] [${ctx}]`,
  );
  assert.ok(
    info.box.top >= -TOL && info.box.bottom <= vh + TOL,
    `${selector} outline box vertically clipped by viewport ` +
      `[top=${info.box.top} bottom=${info.box.bottom} vh=${vh}] [${ctx}]`,
  );

  // Outline box must not be clipped by an overflow ancestor.
  for (const c of info.clips) {
    assert.ok(
      info.box.left >= c.rect.left - TOL,
      `${selector} outline box left (${info.box.left}) clipped by ancestor ` +
        `${c.tag}.${c.cls} (${c.clip.join("/")}) left=${c.rect.left} [${ctx}]`,
    );
    assert.ok(
      info.box.right <= c.rect.right + TOL,
      `${selector} outline box right (${info.box.right}) clipped by ancestor ` +
        `${c.tag}.${c.cls} (${c.clip.join("/")}) right=${c.rect.right} [${ctx}]`,
    );
    assert.ok(
      info.box.top >= c.rect.top - TOL,
      `${selector} outline box top (${info.box.top}) clipped by ancestor ` +
        `${c.tag}.${c.cls} (${c.clip.join("/")}) top=${c.rect.top} [${ctx}]`,
    );
    assert.ok(
      info.box.bottom <= c.rect.bottom + TOL,
      `${selector} outline box bottom (${info.box.bottom}) clipped by ancestor ` +
        `${c.tag}.${c.cls} (${c.clip.join("/")}) bottom=${c.rect.bottom} [${ctx}]`,
    );
  }

  return info;
}

function measure(page) {
  return page.evaluate(() => {
    const html = document.documentElement;
    const body = document.body;
    const q = (sel) => document.querySelector(sel);
    // No zero-rect fallback for required elements: missing element -> null.
    const rect = (el) =>
      el
        ? {
            left: el.getBoundingClientRect().left,
            right: el.getBoundingClientRect().right,
            top: el.getBoundingClientRect().top,
            bottom: el.getBoundingClientRect().bottom,
            width: el.getBoundingClientRect().width,
            height: el.getBoundingClientRect().height,
          }
        : null;
    const vis = (el) => {
      if (!el) return false;
      const cs = getComputedStyle(el);
      return cs.display !== "none" && cs.visibility !== "hidden";
    };
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
      viewportHeight: window.innerHeight,
      state: body.getAttribute("data-first-use-state"),
      htmlScrollWidth: html.scrollWidth,
      bodyScrollWidth: body.scrollWidth,
      htmlClientWidth: html.clientWidth,
      present: {
        chat: !!(chat && vis(chat)),
        header: !!(header && vis(header)),
        thread: !!(thread && vis(thread)),
        chips: !!(chips && vis(chips)),
        composer: !!(composer && vis(composer)),
        input: !!(input && vis(input)),
        send: !!(send && vis(send)),
        canvas: !!(canvas && vis(canvas)),
      },
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

function assertRect(name, r, ctx) {
  assert.ok(r, `${name} is missing (null rect) [${ctx}]`);
  assert.ok(r.width > 0, `${name} has width 0 [${ctx}]`);
  assert.ok(r.height > 0, `${name} has height 0 [${ctx}]`);
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

async function runOneState(page, viewport, state, base) {
  const ctx = `viewport=${viewport.width}x${viewport.height} state=${state}`;
  await page.setViewportSize({ width: viewport.width, height: viewport.height });
  const response = await page.goto(base, { waitUntil: "domcontentloaded" });

  assert.ok(response, `navigation returned no response [${ctx}]`);
  assert.equal(response.status(), 200, `navigation status ${response.status()} [${ctx}]`);

  const finalUrl = page.url();
  const finalOrigin = new URL(finalUrl).origin;
  const baseOrigin = new URL(base).origin;
  assert.equal(
    finalOrigin,
    baseOrigin,
    `final URL origin (${finalOrigin}) differs from test server origin (${baseOrigin}) [${ctx}]`,
  );

  // Required DOM must exist before any assertion.
  const dom = await page.evaluate(() => {
    const need = [
      ".chat-shell",
      ".chat-composer",
      ".chat-composer__input",
      ".chat-composer__send",
    ];
    const missing = need.filter((s) => !document.querySelector(s));
    const fullText = document.body ? document.body.innerText : "";
    return {
      missing,
      title: document.title,
      bodyLen: fullText.length,
      bodyText: fullText.slice(0, 200),
    };
  });
  if (dom.missing.length) {
    throw new Error(
      `required DOM missing ${JSON.stringify(dom.missing)} url=${finalUrl} ` +
        `status=${response.status()} title="${dom.title}" body="${dom.bodyText}" [${ctx}]`,
    );
  }
  assert.ok(
    dom.bodyLen > 200,
    `document looks like a short 404 page (bodyLen=${dom.bodyLen}) url=${finalUrl} [${ctx}]`,
  );

  await page.waitForSelector(".chat-shell", { timeout: 10000 });
  await page.addStyleTag({
    content: "*{animation:none !important;transition:none !important;}",
  });
  if (state === "split") {
    // Force the split layout without any network/bridge (static, offline).
    // Mirror what the shell's setCanvasAvailability(true) does so the demo
    // canvas is actually visible (the CSS hides #demo-canvas[inert]).
    await page.evaluate(() => {
      document.body.setAttribute("data-first-use-state", "split");
      const c = document.getElementById("demo-canvas");
      if (c) {
        c.removeAttribute("inert");
        c.setAttribute("aria-hidden", "false");
      }
    });
    // Wait until the demo canvas is actually visible (its display/visibility
    // transition has settled) so the required-element check measures a
    // final, non-clipped layout rather than a mid-transition state.
    await page.waitForSelector(".demo-canvas", { state: "visible", timeout: 10000 });
  }

  const m = await measure(page);

  // Required elements present and visible with positive rects (no zero fallback).
  assert.ok(m.present.chat, `.chat-shell missing/hidden [${ctx}]`);
  assert.ok(m.present.header, `.chat-shell__header missing/hidden [${ctx}]`);
  assert.ok(m.present.thread, `.chat-thread missing/hidden [${ctx}]`);
  assert.ok(m.present.chips, `.chat-chips missing/hidden [${ctx}]`);
  assert.ok(m.present.composer, `.chat-composer missing/hidden [${ctx}]`);
  assert.ok(m.present.input, `.chat-composer__input missing/hidden [${ctx}]`);
  assert.ok(m.present.send, `.chat-composer__send missing/hidden [${ctx}]`);
  if (state === "split") {
    assert.ok(m.present.canvas, `.demo-canvas missing/hidden (split) [${ctx}]`);
  }

  assertRect(".chat-shell", m.chat, ctx);
  assertRect(".chat-shell__header", m.header, ctx);
  assertRect(".chat-thread", m.thread, ctx);
  assertRect(".chat-chips", m.chips, ctx);
  assertRect(".chat-composer", m.composer, ctx);
  assertRect(".chat-composer__input", m.input, ctx);
  assertRect(".chat-composer__send", m.send, ctx);
  if (state === "split") assertRect(".demo-canvas", m.canvas, ctx);

  assertNoHorizontalOverflow(m, ctx);
  assertInsideViewport(m.chat, "chat-shell", ctx, viewport.width);

  if (state === "entry") {
    assertInsideChat(m.header, m.chat, "header", ctx);
    assertInsideChat(m.thread, m.chat, "thread", ctx);
    assertInsideChat(m.chips, m.chat, "chips", ctx);
    assertInsideChat(m.composer, m.chat, "composer", ctx);
    assertInsideChat(m.input, m.chat, "input", ctx);
    assertInsideChat(m.send, m.chat, "send", ctx);
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
    assertInsideViewport(m.canvas, "demo-canvas", ctx, viewport.width);
    assertInsideViewport(m.composer, "composer", ctx, viewport.width);
    assertInsideViewport(m.input, "input", ctx, viewport.width);
    assertInsideViewport(m.send, "send", ctx, viewport.width);
  }

  // Independent keyboard focus verification for input and send, each from a
  // fresh navigation so the focus order is reset.
  await page.goto(base, { waitUntil: "domcontentloaded" });
  if (state === "split") {
    // Force the split layout without any network/bridge (static, offline).
    // Mirror what the shell's setCanvasAvailability(true) does so the demo
    // canvas is actually visible (the CSS hides #demo-canvas[inert]).
    await page.evaluate(() => {
      document.body.setAttribute("data-first-use-state", "split");
      const c = document.getElementById("demo-canvas");
      if (c) {
        c.removeAttribute("inert");
        c.setAttribute("aria-hidden", "false");
      }
    });
    // Wait until the demo canvas is actually visible (its display/visibility
    // transition has settled) so the required-element check measures a
    // final, non-clipped layout rather than a mid-transition state.
    await page.waitForSelector(".demo-canvas", { state: "visible", timeout: 10000 });
  }
  const reachedInput = await focusByKeyboard(page, ".chat-composer__input");
  assert.ok(reachedInput, `keyboard Tab could not reach .chat-composer__input [${ctx}]`);
  const inputFocus = await verifyFocusVisible(page, ".chat-composer__input", ctx);

  // Fresh navigation for an independent keyboard focus pass on send.
  await page.goto(base, { waitUntil: "domcontentloaded" });
  if (state === "split") {
    // Force the split layout without any network/bridge (static, offline).
    // Mirror what the shell's setCanvasAvailability(true) does so the demo
    // canvas is actually visible (the CSS hides #demo-canvas[inert]).
    await page.evaluate(() => {
      document.body.setAttribute("data-first-use-state", "split");
      const c = document.getElementById("demo-canvas");
      if (c) {
        c.removeAttribute("inert");
        c.setAttribute("aria-hidden", "false");
      }
    });
    // Wait until the demo canvas is actually visible (its display/visibility
    // transition has settled) so the required-element check measures a
    // final, non-clipped layout rather than a mid-transition state.
    await page.waitForSelector(".demo-canvas", { state: "visible", timeout: 10000 });
  }
  const reachedSend = await focusByKeyboard(page, ".chat-composer__send");
  assert.ok(reachedSend, `keyboard Tab could not reach .chat-composer__send [${ctx}]`);
  const sendFocus = await verifyFocusVisible(page, ".chat-composer__send", ctx);

  const push = (label, ok) => (ok ? "PASS" : "FAIL");
  console.log(
    `[${viewport.width}x${viewport.height} ${state}] ` +
      `geometry=${push("g", true)} ` +
      `overflow(htmlSW=${m.htmlScrollWidth}/${m.htmlClientWidth},bodySW=${m.bodyScrollWidth}/${m.viewportWidth}) ` +
      `input-focus(active=${inputFocus.activeElementMatches}, :focus-visible=${inputFocus.focusVisible}, outline=${inputFocus.outlineStyle} ${inputFocus.outlineWidth}px) ` +
      `send-focus(active=${sendFocus.activeElementMatches}, :focus-visible=${sendFocus.focusVisible}, outline=${sendFocus.outlineStyle} ${sendFocus.outlineWidth}px) ` +
      `clipping=${push("c", true)}`,
  );

  return { viewport, state, geometry: "PASS", inputFocus: "PASS", sendFocus: "PASS" };
}

async function main() {
  console.log("Running first-use responsive browser contract (no network):");

  const python = await pickPython();
  console.log("  building static site with", python);
  await run(python, ["scripts/build_cloudflare_pages.py"]);
  assert.ok(
    fs.existsSync(path.join(DIST_DIR, "mvp", "index.html")),
    "dist build missing mvp/index.html",
  );
  assert.ok(
    fs.existsSync(path.join(DIST_DIR, "index.html")),
    "dist build missing index.html",
  );

  // OS-assigned ephemeral port. No fixed 4173; no stale-server collision.
  const { server, port, base } = await startServer();
  console.log(`  serving dist from ${base} (ephemeral port ${port})`);

  let browser;
  let browserInfo;
  try {
    browserInfo = await launchBrowser();
    browser = browserInfo.browser;
  } catch (e) {
    server.close();
    // A browser launch failure MUST fail the contract (never skip).
    console.error("\n✗ RESPONSIVE BROWSER CONTRACT FAILED: no browser available");
    console.error("  " + e.message);
    process.exit(1);
  }

  // Report the actual browser used.
  console.log(
    `  browser: ${browserInfo.version}\n  browser source: ${browserInfo.source}`,
  );

  const failures = [];
  let results = [];
  try {
    const context = await browser.newContext({ viewport: VIEWPORTS[0] });
    const allowedOrigin = new URL(base).origin;
    // Block every request that is not to the test's own loopback origin.
    await context.route("**", (route) => {
      const requestUrl = new URL(route.request().url());
      if (requestUrl.origin === allowedOrigin) {
        return route.continue();
      }
      return route.abort();
    });
    const page = await context.newPage();
    page.on("pageerror", (err) => failures.push("pageerror: " + err.message));

    for (const vp of VIEWPORTS) {
      for (const state of STATES) {
        try {
          const r = await runOneState(page, vp, state, base);
          results.push(r);
        } catch (err) {
          failures.push(`viewport=${vp.width}x${vp.height} state=${state}: ${err.message}`);
        }
      }
    }
    await context.close();
  } finally {
    await browser.close();
    server.close();
  }

  console.log("\n=== viewport matrix ===");
  for (const r of results) {
    console.log(
      `[${r.viewport.width}x${r.viewport.height} ${r.state}] ` +
        `geometry=${r.geometry} input-focus=${r.inputFocus} send-focus=${r.sendFocus}`,
    );
  }

  if (failures.length) {
    console.error("\nRESPONSIVE CONTRACT FAILED:");
    for (const f of failures) console.error("  - " + f);
    process.exit(1);
  }
  console.log("\nAll first-use responsive geometry + focus-visible checks passed.");
}

main().catch((err) => {
  console.error("Responsive browser contract error:");
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
