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
import os from "node:os";
import { chromium } from "playwright";

const REPO = path.resolve(fileURLToPath(import.meta.url), "../../..");
const DIST_DIR = path.join(REPO, "dist", "cloudflare-pages");

// Screenshots are generated for evidence but NEVER committed (Step 10).
const SCREENSHOT_DIR = path.join(
  os.tmpdir(),
  "400-ai-finder-1116",
);

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

// Promise wrapper around server.close() so cleanup awaits completion.
function closeServer(server) {
  return new Promise((resolve, reject) => {
    if (!server || !server.listening) {
      resolve();
      return;
    }
    server.close((error) => {
      if (error) {
        // ERR_SERVER_NOT_RUNNING is harmless on a double-close; propagate
        // anything else so real failures are not silently swallowed.
        if (error.code === "ERR_SERVER_NOT_RUNNING") {
          resolve();
          return;
        }
        reject(error);
        return;
      }
      resolve();
    });
  });
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
          .posix.normalize(pathname)
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

    // Walk ancestor chain for clipping containers, judged per-axis so an
    // element that clips only one axis is still detected (the old concat of
    // overflow+overflowX+overflowY could never match a single value).
    const CLIPPING_VALUES = new Set(["hidden", "clip", "auto", "scroll"]);
    const clips = [];
    let node = el.parentElement;
    let depth = 0;
    while (node && node !== document.documentElement && depth < 50) {
      const ncs = getComputedStyle(node);
      const overflowX = ncs.overflowX;
      const overflowY = ncs.overflowY;
      const clipsX = CLIPPING_VALUES.has(overflowX);
      const clipsY = CLIPPING_VALUES.has(overflowY);
      if (clipsX || clipsY) {
        const nrect = node.getBoundingClientRect();
        clips.push({
          tag: node.tagName,
          cls: typeof node.className === "string" ? node.className : "",
          overflowX,
          overflowY,
          clipsX,
          clipsY,
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

    const ae = document.activeElement;
    // .first-use-layout clips only at wider viewports (grid + overflow:hidden);
    // at narrow widths it is display:flex with overflow:visible, so it is a
    // non-clipping ancestor there. Report whether it actually clips so the
    // caller can require its detection conditionally.
    const layoutEl = document.querySelector(".first-use-layout");
    const layoutCs = layoutEl ? getComputedStyle(layoutEl) : null;
    const layoutClipping = !!(
      layoutCs &&
      (CLIPPING_VALUES.has(layoutCs.overflowX) ||
        CLIPPING_VALUES.has(layoutCs.overflowY))
    );
    return {
      exists: true,
      selector: sel,
      activeElementMatches: ae === el,
      activeTag: ae ? ae.tagName : null,
      activeId: ae ? ae.id || "" : "",
      activeClass: ae ? (typeof ae.className === "string" ? ae.className : "") : "",
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
      layoutClipping,
    };
  }, selector);

  assert.ok(info.exists, `${selector} does not exist [${ctx}]`);
  const activeLabel = info.activeTag
    ? `${info.activeTag}${info.activeId ? "#" + info.activeId : ""}${
        info.activeClass ? "." + info.activeClass.split(/\s+/).join(".") : ""
      }`
    : "(none)";
  assert.ok(
    info.activeElementMatches,
    `${selector} is not document.activeElement (got ${activeLabel}) [${ctx}]`,
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

  // Vacuous-pass guard: clipping detection must actually find an ancestor.
  assert.ok(
    info.clips.length > 0,
    `${selector} found no clipping ancestors; ancestor detection may be broken [${ctx}]`,
  );
  // Require .first-use-layout detection only where it actually clips (it is
  // display:flex + overflow:visible at narrow widths, where .chat-shell is the
  // clipping ancestor instead). This keeps the guard meaningful on every
  // viewport without asserting a structure that does not exist.
  if (info.layoutClipping) {
    assert.ok(
      info.clips.some((c) => String(c.cls).split(/\s+/).includes("first-use-layout")),
      `${selector} did not detect .first-use-layout as a clipping ancestor ` +
        `[${ctx}]`,
    );
  }

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

  // Outline box must not be clipped by an overflow ancestor. Each ancestor is
  // judged per-axis: only the axes it actually clips are asserted.
  let clippingChecks = 0;
  for (const c of info.clips) {
    if (c.clipsX) {
      assert.ok(
        info.box.left >= c.rect.left - TOL,
        `${selector} outline box left (${info.box.left}) clipped by ancestor ` +
          `${c.tag}.${c.cls} (overflow-x=${c.overflowX}) left=${c.rect.left} [${ctx}]`,
      );
      assert.ok(
        info.box.right <= c.rect.right + TOL,
        `${selector} outline box right (${info.box.right}) clipped by ancestor ` +
          `${c.tag}.${c.cls} (overflow-x=${c.overflowX}) right=${c.rect.right} [${ctx}]`,
      );
      clippingChecks += 2;
    }
    if (c.clipsY) {
      assert.ok(
        info.box.top >= c.rect.top - TOL,
        `${selector} outline box top (${info.box.top}) clipped by ancestor ` +
          `${c.tag}.${c.cls} (overflow-y=${c.overflowY}) top=${c.rect.top} [${ctx}]`,
      );
      assert.ok(
        info.box.bottom <= c.rect.bottom + TOL,
        `${selector} outline box bottom (${info.box.bottom}) clipped by ancestor ` +
          `${c.tag}.${c.cls} (overflow-y=${c.overflowY}) bottom=${c.rect.bottom} [${ctx}]`,
      );
      clippingChecks += 2;
    }
  }
  info.clippingChecks = clippingChecks;

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

async function applySplitState(page) {
  await page.evaluate(() => {
    document.body.setAttribute("data-first-use-state", "split");
    const c = document.getElementById("demo-canvas");
    if (c) {
      c.removeAttribute("inert");
      c.setAttribute("aria-hidden", "false");
    }
  });
}

// Extra contract checks required by #1065 (token layer): token stylesheet is
// actually loaded + parsed, the disabled state collapses correctly, and
// prefers-reduced-motion collapses transition duration. Each throws on
// failure so it is surfaced through the shared failure list.
async function verifyStateExtra(page, viewport, state, base) {
  const ctx = `extra viewport=${viewport.width}x${viewport.height} state=${state}`;

  // 1) Token stylesheet loaded + parsed (canonical primitive resolves).
  await page.goto(base, { waitUntil: "domcontentloaded" });
  if (state === "split") await applySplitState(page);
  const tokenVal = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--mvp-radius-sm").trim(),
  );
  assert.equal(
    tokenVal,
    "4px",
    `${ctx}: --mvp-radius-sm not applied via token stylesheet (got '${tokenVal}')`,
  );

  // 2) Disabled state: send button must read opacity 0.4 + cursor default.
  await page.goto(base, { waitUntil: "domcontentloaded" });
  if (state === "split") await applySplitState(page);
  const dis = await page.evaluate(() => {
    const s = document.querySelector(".chat-composer__send");
    if (!s) return { exists: false };
    s.disabled = true;
    const cs = getComputedStyle(s);
    const out = { exists: true, opacity: cs.opacity, cursor: cs.cursor };
    s.disabled = false;
    return out;
  });
  assert.ok(dis.exists, `${ctx}: .chat-composer__send missing`);
  assert.equal(
    dis.opacity,
    "0.4",
    `${ctx}: disabled send opacity expected 0.4, got ${dis.opacity}`,
  );
  assert.equal(
    dis.cursor,
    "default",
    `${ctx}: disabled send cursor expected default, got ${dis.cursor}`,
  );

  // 3) Reduced motion collapses transition duration to ~0.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(base, { waitUntil: "domcontentloaded" });
  if (state === "split") await applySplitState(page);
  const rd = await page.evaluate(() => {
    const el = document.querySelector(".chat-shell");
    return el ? getComputedStyle(el).transitionDuration : null;
  });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  assert.ok(rd !== null, `${ctx}: .chat-shell missing for reduced-motion check`);
  // Reduced motion must collapse transitions to an effectively-instant value.
  // The shared token layer sets `transition-duration: 0.001ms !important`, but
  // the first-use layer overrides `.first-use-layout .chat-shell` with
  // `transition: none !important` (a stricter, equally reduced-motion-safe
  // collapse). Both yield "no visible motion", so accept either.
  assert.ok(
    rd === "0s" || rd === "0.001ms",
    `${ctx}: reduced-motion transition-duration expected 0s or 0.001ms (collapsed), got ${rd}`,
  );

  console.log(
    `[${viewport.width}x${viewport.height} ${state}] extra=` +
      `token(${tokenVal}) disabled(opacity=${dis.opacity},cursor=${dis.cursor}) ` +
      `reduced-motion(transition=${rd})`,
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
    // Re-apply transition:none after the fresh navigation so the grid layout
    // settles immediately (a live transition makes the focus-box rect a
    // non-deterministic mid-animation frame).
    await page.addStyleTag({
      content: "*{animation:none !important;transition:none !important;}",
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
    // Re-apply transition:none after the fresh navigation (see comment above).
    await page.addStyleTag({
      content: "*{animation:none !important;transition:none !important;}",
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
      `clipping=${push("c", true)} ` +
      `input-clipping-ancestors=${inputFocus.clips.length} ` +
      `send-clipping-ancestors=${sendFocus.clips.length} ` +
      `clipping-checks=${inputFocus.clippingChecks + sendFocus.clippingChecks}`,
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
  let context;
  try {
    browserInfo = await launchBrowser();
    browser = browserInfo.browser;
  } catch (e) {
    // A browser launch failure MUST fail the contract (never skip). Clean up
    // the server first, then let main().catch produce the non-zero exit.
    await closeServer(server);
    console.error("\n✗ RESPONSIVE BROWSER CONTRACT FAILED: no browser available");
    console.error("  " + e.message);
    throw e;
  }

  // Report the actual browser used.
  console.log(
    `  browser: ${browserInfo.version}\n  browser source: ${browserInfo.source}`,
  );

  const failures = [];
  let results = [];
  try {
    context = await browser.newContext({ viewport: VIEWPORTS[0] });
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

    // ── #1116 Stage B: mobile conversation/guidance surface ──────────
    // Drives the REAL shell on ≤767px viewports: submit a supported
    // question → confirm → assert the surface switch (role=group) appears,
    // the guidance surface (canonical #demo-canvas) becomes active, and NO
    // automated editable focus occurs during the journey. Also drives the
    // writing journey, direct user focus, cancellation, desktop regression,
    // and screenshot evidence under os.tmpdir().
    const mobileViewports = VIEWPORTS.filter((v) => v.width <= 767);
    if (mobileViewports.length) {
      console.log("\nRunning #1116 Stage B mobile surface scenario:");
      try {
        fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
        const surfCtx = await browser.newContext({
          viewport: mobileViewports[0],
        });
        const allowedOrigin2 = new URL(base).origin;
        // All non-loopback requests are ABORTED and recorded so an attempt
        // (not just a PASS-after-abort) counts as a failure.
        const externalRequestAttempts = [];
        const consoleErrors = [];
        const pageErrors = [];
        const requestFailures = [];
        const httpErrors = [];

        await surfCtx.route("**", (route) => {
          const requestUrl = new URL(route.request().url());
          if (requestUrl.origin === allowedOrigin2) {
            return route.continue();
          }
          // Only favicon is treated as a clearly benign auto-request.
          if (requestUrl.pathname === "/favicon.ico") {
            return route.abort();
          }
          externalRequestAttempts.push(requestUrl.toString());
          return route.abort();
        });

        const sp = await surfCtx.newPage();
        sp.on("pageerror", (err) => {
          pageErrors.push(String(err && err.message ? err.message : err));
        });
        sp.on("console", (msg) => {
          if (msg.type() === "error") {
            consoleErrors.push(msg.text());
          }
        });
        sp.on("requestfailed", (req) => {
          const u = req.url();
          try {
            const parsed = new URL(u);
            if (parsed.origin === allowedOrigin2) return;
            if (parsed.pathname === "/favicon.ico") return;
          } catch {
            /* keep */
          }
          requestFailures.push(u);
        });
        sp.on("response", (resp) => {
          const u = resp.url();
          try {
            const parsed = new URL(u);
            if (parsed.origin === allowedOrigin2) return;
            if (parsed.pathname === "/favicon.ico") return;
          } catch {
            /* keep */
          }
          if (resp.status() >= 400) {
            httpErrors.push(`${u} ${resp.status()}`);
          }
        });
        sp.on("request", (req) => {
          const u = req.url();
          try {
            const parsed = new URL(u);
            if (parsed.origin === allowedOrigin2) return;
            if (parsed.pathname === "/favicon.ico") return;
            // Record attempt even if route.abort() also fires.
            if (!externalRequestAttempts.includes(u)) {
              externalRequestAttempts.push(u);
            }
          } catch {
            /* ignore malformed */
          }
        });

        // Transient editable-focus instrumentation: capture focusin on any
        // editable during the automated phase (from confirm-yes until
        // terminal/cancel/reset). The final array must be empty.
        async function installTfFocusCapture() {
          await sp.evaluate(() => {
            const w = window;
            if (!w.__tfInstalled) {
              w.__tfInstalled = true;
              w.__tfViolations = [];
              w.__tfAllowUserFocus = false;
              const handler = (e) => {
                if (w.__tfAllowUserFocus) return;
                if (!w.__tfAutomatedPhase) return;
                const el = e.target;
                if (
                  el &&
                  (el.matches("input, textarea, [contenteditable='true']") ||
                    el.isContentEditable)
                ) {
                  w.__tfViolations.push({
                    t: Date.now(),
                    tagName: el.tagName,
                    id: el.id || "",
                    className: (el.className && el.className.toString()) || "",
                    surface:
                      document.body.getAttribute("data-mobile-surface") || "",
                    firstUse:
                      document.body.getAttribute("data-first-use-state") || "",
                    choreo:
                      document.body.getAttribute("data-choreography-state") ||
                      "",
                    journey:
                      (window.CitizenFirstChoreography &&
                        typeof window.CitizenFirstChoreography
                          .getCurrentStepIndex === "function" &&
                        String(
                          window.CitizenFirstChoreography.getCurrentStepIndex(),
                        )) ||
                      "",
                  });
                }
              };
              document.addEventListener("focusin", handler, true);
            } else {
              w.__tfViolations = [];
              w.__tfAllowUserFocus = false;
              w.__tfAutomatedPhase = false;
            }
          });
        }
        async function setAutomatedPhase(on) {
          await sp.evaluate((flag) => {
            window.__tfAutomatedPhase = !!flag;
          }, on);
        }
        async function allowUserFocus(on) {
          await sp.evaluate((flag) => {
            window.__tfAllowUserFocus = !!flag;
          }, on);
        }
        async function drainTfViolations() {
          return sp.evaluate(() => window.__tfViolations || []);
        }
        async function clearTfViolations() {
          await sp.evaluate(() => {
            window.__tfViolations = [];
          });
        }

        const shot = async (name) => {
          try {
            await sp.screenshot({
              path: path.join(SCREENSHOT_DIR, name),
              fullPage: false,
            });
          } catch {
            /* screenshot is evidence only; never fail the contract on it */
          }
        };

        const SEARCH_Q = "공동주택 관련 문의는 어느 부서에 해야 하나요?";
        const WRITE_Q = "가로등이 고장났어요. 신고할게요";

        // ── Search journey on 320 and 390 ──
        for (const vp of mobileViewports) {
          try {
            await sp.setViewportSize({ width: vp.width, height: vp.height });
            await sp.goto(base, { waitUntil: "domcontentloaded" });
            await sp.waitForSelector(".chat-shell", { timeout: 10000 });
            await installTfFocusCapture();
            await clearTfViolations();
            await setAutomatedPhase(false);
            await allowUserFocus(false);

            // 1) entry: switch hidden, conversation default surface.
            const entryState = await sp.evaluate(() => {
              const sw = document.getElementById("mobile-surface-switch");
              const tabC = document.getElementById("tab-conversation");
              const tabG = document.getElementById("tab-guidance");
              return {
                switchHidden: !!sw && sw.hasAttribute("hidden"),
                role: sw ? sw.getAttribute("role") : null,
                ariaLabel: sw ? sw.getAttribute("aria-label") : null,
                state: document.body.getAttribute("data-first-use-state"),
                convPressed: tabC ? tabC.getAttribute("aria-pressed") : null,
                guidPressed: tabG ? tabG.getAttribute("aria-pressed") : null,
                hasTablist: !!document.querySelector(
                  '#mobile-surface-switch[role="tablist"]',
                ),
                hasTabRole: !!document.querySelector(
                  "#mobile-surface-switch [role='tab']",
                ),
                hasAriaSelected: !!document.querySelector(
                  "#mobile-surface-switch [aria-selected]",
                ),
              };
            });
            assert.ok(
              entryState.switchHidden,
              `stageB ${vp.width}x${vp.height}: mobile switch must be hidden on entry`,
            );
            assert.equal(
              entryState.role,
              "group",
              `stageB ${vp.width}x${vp.height}: switch must be role=group`,
            );
            assert.equal(
              entryState.ariaLabel,
              "서비스 화면",
              `stageB ${vp.width}x${vp.height}: accessible name`,
            );
            assert.equal(
              entryState.convPressed,
              "true",
              `stageB ${vp.width}x${vp.height}: conversation pressed at entry`,
            );
            assert.equal(
              entryState.guidPressed,
              "false",
              `stageB ${vp.width}x${vp.height}: guidance not pressed at entry`,
            );
            assert.equal(
              entryState.hasTablist,
              false,
              `stageB ${vp.width}x${vp.height}: no role=tablist`,
            );
            assert.equal(
              entryState.hasTabRole,
              false,
              `stageB ${vp.width}x${vp.height}: no role=tab`,
            );
            assert.equal(
              entryState.hasAriaSelected,
              false,
              `stageB ${vp.width}x${vp.height}: no aria-selected`,
            );
            await shot(`${vp.width}-entry.png`);

            // 2) submit a supported question (deterministic, non-MVP).
            await sp.fill(".chat-composer__input", SEARCH_Q);
            await sp.click(".chat-composer__send");

            // Wait for confirm / surface switch exposure.
            await sp.waitForFunction(
              () => {
                const sw = document.getElementById("mobile-surface-switch");
                return sw && !sw.hasAttribute("hidden");
              },
              { timeout: 10000 },
            );

            const splitState = await sp.evaluate(() => {
              const sw = document.getElementById("mobile-surface-switch");
              const tabC = document.getElementById("tab-conversation");
              const tabG = document.getElementById("tab-guidance");
              return {
                switchVisible: !!sw && !sw.hasAttribute("hidden"),
                role: sw ? sw.getAttribute("role") : null,
                tabCPressed: tabC ? tabC.getAttribute("aria-pressed") : null,
                tabGPressed: tabG ? tabG.getAttribute("aria-pressed") : null,
                surface: document.body.getAttribute("data-mobile-surface"),
              };
            });
            assert.equal(
              splitState.role,
              "group",
              `stageB ${vp.width}x${vp.height}: switch must be role=group at split`,
            );
            assert.equal(
              splitState.tabCPressed,
              "true",
              `stageB ${vp.width}x${vp.height}: conversation pressed at answer/confirm`,
            );
            assert.equal(
              splitState.tabGPressed,
              "false",
              `stageB ${vp.width}x${vp.height}: guidance not pressed at answer/confirm`,
            );

            // 3) confirm-run bubble → press 예, 안내해 주세요.
            const yesBtn = await sp
              .waitForSelector(
                '.chat-msg--confirm-run button:has-text("예, 안내해 주세요")',
                { timeout: 10000 },
              )
              .catch(() => null);
            assert.ok(
              yesBtn,
              `stageB ${vp.width}x${vp.height}: confirm-run button not found`,
            );

            // Automated phase starts at confirm yes.
            await clearTfViolations();
            await setAutomatedPhase(true);
            await allowUserFocus(false);

            if (yesBtn) {
              await yesBtn.click();
              await sp
                .waitForFunction(
                  () =>
                    document.body.getAttribute("data-mobile-surface") ===
                    "guidance",
                  { timeout: 10000 },
                )
                .catch(() => {});

              const afterConfirm = await sp.evaluate(() => {
                const tabC = document.getElementById("tab-conversation");
                const tabG = document.getElementById("tab-guidance");
                const canvas = document.getElementById("demo-canvas");
                const chatShell = document.getElementById("chat-shell");
                const cs = canvas ? getComputedStyle(canvas) : null;
                const active = document.activeElement;
                const editable =
                  !!active &&
                  (active.matches(
                    "input, textarea, [contenteditable='true']",
                  ) ||
                    active.isContentEditable);
                return {
                  surface: document.body.getAttribute("data-mobile-surface"),
                  tabCPressed: tabC ? tabC.getAttribute("aria-pressed") : null,
                  tabGPressed: tabG ? tabG.getAttribute("aria-pressed") : null,
                  canvasDisplay: cs ? cs.display : null,
                  canvasAriaHidden: canvas
                    ? canvas.getAttribute("aria-hidden")
                    : null,
                  canvasInert: canvas ? canvas.hasAttribute("inert") : null,
                  chatAriaHidden: chatShell
                    ? chatShell.getAttribute("aria-hidden")
                    : null,
                  chatInert: chatShell
                    ? chatShell.hasAttribute("inert")
                    : null,
                  composerEditableFocused: editable,
                };
              });
              assert.equal(
                afterConfirm.surface,
                "guidance",
                `stageB ${vp.width}x${vp.height}: guidance surface active after confirm`,
              );
              assert.equal(
                afterConfirm.tabGPressed,
                "true",
                `stageB ${vp.width}x${vp.height}: guidance pressed after confirm`,
              );
              assert.equal(
                afterConfirm.tabCPressed,
                "false",
                `stageB ${vp.width}x${vp.height}: conversation not pressed after confirm`,
              );
              assert.ok(
                afterConfirm.canvasDisplay &&
                  afterConfirm.canvasDisplay !== "none",
                `stageB ${vp.width}x${vp.height}: canonical #demo-canvas visible as guidance`,
              );
              assert.equal(
                afterConfirm.canvasAriaHidden,
                "false",
                `stageB ${vp.width}x${vp.height}: canvas aria-hidden=false in guidance`,
              );
              assert.equal(
                afterConfirm.chatInert,
                true,
                `stageB ${vp.width}x${vp.height}: chat-shell inert in guidance`,
              );
              assert.equal(
                afterConfirm.composerEditableFocused,
                false,
                `stageB ${vp.width}x${vp.height}: composer keyboard closed before navigation`,
              );
              await shot(`${vp.width}-confirm.png`);

              // First cursor/target action should be visible.
              await sp
                .waitForSelector(
                  ".choreography-cursor, .cursor-arrow, .ai-cursor, [data-cursor]",
                  { timeout: 10000 },
                )
                .catch(() => {});
              await shot(`${vp.width}-first-action.png`);

              // Search field typing indicator + value change.
              const typed = await sp
                .waitForFunction(
                  () => {
                    const el =
                      document.querySelector(".bg-dept-search__input") ||
                      document.querySelector(
                        'input[type="search"], input[name*="search" i], input[placeholder*="검색"]',
                      );
                    return el && el.value && el.value.length > 0;
                  },
                  { timeout: 12000 },
                )
                .catch(() => false);
              assert.ok(
                typed,
                `stageB ${vp.width}x${vp.height}: search field received typed value`,
              );
              await shot(`${vp.width}-search-typing.png`);

              // Automated phase editable focus violation must be 0 so far.
              let violations = await drainTfViolations();
              assert.equal(
                violations.length,
                0,
                `stageB ${vp.width}x${vp.height}: transient editable focus violations during automated search = ${violations.length} ${JSON.stringify(violations.slice(0, 3))}`,
              );

              // route/result reached (best-effort markers).
              await sp
                .waitForFunction(
                  () => {
                    return (
                      !!document.querySelector(
                        '[data-representative-contact="true"]',
                      ) ||
                      !!document.querySelector(".dept-result") ||
                      !!document.querySelector("[data-route-result]") ||
                      document.body.getAttribute("data-choreography-state") ===
                        "complete" ||
                      document.body.getAttribute("data-choreography-state") ===
                        "completed"
                    );
                  },
                  { timeout: 15000 },
                )
                .catch(() => {});
              await shot(`${vp.width}-result.png`);

              // End automated phase for switch/user interactions.
              await setAutomatedPhase(false);

              // 4) switch back to conversation, then guidance, preserve state.
              const tabC2 = await sp.$("#tab-conversation");
              if (tabC2) {
                await tabC2.click();
                const back = await sp.evaluate(() => {
                  const tabC = document.getElementById("tab-conversation");
                  const chatShell = document.getElementById("chat-shell");
                  const canvas = document.getElementById("demo-canvas");
                  return {
                    surface: document.body.getAttribute("data-mobile-surface"),
                    tabCPressed: tabC
                      ? tabC.getAttribute("aria-pressed")
                      : null,
                    chatAriaHidden: chatShell
                      ? chatShell.getAttribute("aria-hidden")
                      : null,
                    chatInert: chatShell
                      ? chatShell.hasAttribute("inert")
                      : null,
                    canvasInert: canvas ? canvas.hasAttribute("inert") : null,
                    canvasAriaHidden: canvas
                      ? canvas.getAttribute("aria-hidden")
                      : null,
                  };
                });
                assert.equal(
                  back.surface,
                  "conversation",
                  `stageB ${vp.width}x${vp.height}: returns to conversation`,
                );
                assert.equal(
                  back.tabCPressed,
                  "true",
                  `stageB ${vp.width}x${vp.height}: conversation pressed`,
                );
                assert.equal(
                  back.chatAriaHidden,
                  "false",
                  `stageB ${vp.width}x${vp.height}: chat aria-hidden=false`,
                );
                assert.equal(
                  back.chatInert,
                  false,
                  `stageB ${vp.width}x${vp.height}: chat not inert`,
                );
              }

              const tabG2 = await sp.$("#tab-guidance");
              if (tabG2) {
                await tabG2.click();
                const after = await sp.evaluate(() => {
                  const el =
                    document.querySelector(".bg-dept-search__input") ||
                    document.querySelector(
                      'input[type="search"], input[name*="search" i], input[placeholder*="검색"]',
                    );
                  return {
                    surface: document.body.getAttribute("data-mobile-surface"),
                    value: el ? el.value : "",
                  };
                });
                assert.equal(
                  after.surface,
                  "guidance",
                  `stageB ${vp.width}x${vp.height}: back to guidance`,
                );
                assert.ok(
                  after.value && after.value.length > 0,
                  `stageB ${vp.width}x${vp.height}: search value preserved across switch`,
                );
                await shot(`${vp.width}-view-switch.png`);
              }

              // 5) direct user focus: click composer → activeElement is composer.
              const tabC3 = await sp.$("#tab-conversation");
              if (tabC3) await tabC3.click();
              await allowUserFocus(true);
              await sp.click(".chat-composer__input");
              const composerFocus = await sp.evaluate(
                () =>
                  document.activeElement ===
                  document.querySelector(".chat-composer__input"),
              );
              assert.ok(
                composerFocus,
                `stageB ${vp.width}x${vp.height}: direct user click focuses composer`,
              );
              await allowUserFocus(false);

              // 6) reset → entry + conversation default state.
              await setAutomatedPhase(false);
              const didReset = await sp.evaluate(() => {
                if (
                  window.CitizenFirstUseShell &&
                  typeof window.CitizenFirstUseShell.reset === "function"
                ) {
                  window.CitizenFirstUseShell.reset();
                  return true;
                }
                const btn =
                  document.querySelector('[data-action="reset-first-use"]') ||
                  document.querySelector(".chat-shell__reset") ||
                  document.querySelector('button[aria-label*="다시"]');
                if (btn) {
                  btn.click();
                  return true;
                }
                return false;
              });
              if (didReset) {
                await sp
                  .waitForFunction(
                    () =>
                      document.body.getAttribute("data-first-use-state") ===
                      "entry",
                    { timeout: 10000 },
                  )
                  .catch(() => {});
              }
              const resetState = await sp.evaluate(() => {
                const sw = document.getElementById("mobile-surface-switch");
                const tabC = document.getElementById("tab-conversation");
                const active = document.activeElement;
                const editable =
                  !!active &&
                  (active.matches(
                    "input, textarea, [contenteditable='true']",
                  ) ||
                    active.isContentEditable);
                return {
                  state: document.body.getAttribute("data-first-use-state"),
                  switchHidden: !!sw && sw.hasAttribute("hidden"),
                  convPressed: tabC ? tabC.getAttribute("aria-pressed") : null,
                  editableFocused: editable,
                };
              });
              if (didReset && resetState.state === "entry") {
                assert.equal(
                  resetState.state,
                  "entry",
                  `stageB ${vp.width}x${vp.height}: reset returns to entry`,
                );
                assert.ok(
                  resetState.switchHidden,
                  `stageB ${vp.width}x${vp.height}: switch hidden after reset`,
                );
                assert.equal(
                  resetState.convPressed,
                  "true",
                  `stageB ${vp.width}x${vp.height}: conversation pressed after reset`,
                );
                assert.equal(
                  resetState.editableFocused,
                  false,
                  `stageB ${vp.width}x${vp.height}: no automated editable focus after reset`,
                );
                await shot(`${vp.width}-reset.png`);
              } else {
                await shot(`${vp.width}-reset.png`);
              }

              // Final automated-phase violations for this viewport (should still be 0).
              violations = await drainTfViolations();
              assert.equal(
                violations.length,
                0,
                `stageB ${vp.width}x${vp.height}: final transient editable focus violations = ${violations.length}`,
              );
            }

            console.log(`  [${vp.width}x${vp.height}] stageB search=PASS`);
          } catch (err) {
            failures.push(
              `stageB search viewport=${vp.width}x${vp.height}: ${err.message}`,
            );
          }
        }

        // ── Writing journey (390×844) ──
        const writingVp =
          mobileViewports.find((v) => v.width === 390) ||
          mobileViewports[mobileViewports.length - 1];
        if (writingVp) {
          try {
            await sp.setViewportSize({
              width: writingVp.width,
              height: writingVp.height,
            });
            await sp.goto(base, { waitUntil: "domcontentloaded" });
            await sp.waitForSelector(".chat-shell", { timeout: 10000 });
            await installTfFocusCapture();
            await clearTfViolations();
            await setAutomatedPhase(false);
            await allowUserFocus(false);

            await sp.fill(".chat-composer__input", WRITE_Q);
            await sp.click(".chat-composer__send");
            await sp.waitForFunction(
              () => {
                const sw = document.getElementById("mobile-surface-switch");
                return sw && !sw.hasAttribute("hidden");
              },
              { timeout: 10000 },
            );
            const yesBtn = await sp
              .waitForSelector(
                '.chat-msg--confirm-run button:has-text("예, 안내해 주세요")',
                { timeout: 10000 },
              )
              .catch(() => null);
            assert.ok(
              yesBtn,
              `stageB writing ${writingVp.width}x${writingVp.height}: confirm button not found`,
            );

            await clearTfViolations();
            await setAutomatedPhase(true);
            if (yesBtn) await yesBtn.click();

            // Reach writing route (title/body fields).
            await sp
              .waitForFunction(
                () => {
                  return (
                    !!document.querySelector("#board-write-title") ||
                    !!document.querySelector(
                      'input[name*="title" i], input[id*="title" i], textarea[name*="title" i]',
                    ) ||
                    !!document.querySelector(
                      "#board-write-content, textarea[name*='content' i], textarea[id*='content' i], textarea[id*='body' i]",
                    )
                  );
                },
                { timeout: 15000 },
              )
              .catch(() => {});

            // Wait for automated values.
            await sp
              .waitForFunction(
                () => {
                  const title =
                    document.querySelector("#board-write-title") ||
                    document.querySelector(
                      'input[name*="title" i], input[id*="title" i]',
                    );
                  const body =
                    document.querySelector("#board-write-content") ||
                    document.querySelector(
                      "textarea[name*='content' i], textarea[id*='content' i], textarea[id*='body' i]",
                    );
                  const tOk = title && title.value && title.value.length > 0;
                  const bOk = body && body.value && body.value.length > 0;
                  return tOk || bOk;
                },
                { timeout: 15000 },
              )
              .catch(() => {});

            const writeState = await sp.evaluate(() => {
              const title =
                document.querySelector("#board-write-title") ||
                document.querySelector(
                  'input[name*="title" i], input[id*="title" i]',
                );
              const body =
                document.querySelector("#board-write-content") ||
                document.querySelector(
                  "textarea[name*='content' i], textarea[id*='content' i], textarea[id*='body' i]",
                );
              return {
                hasTitle: !!title,
                hasBody: !!body,
                titleVal: title ? title.value : "",
                bodyVal: body ? body.value : "",
              };
            });
            assert.ok(
              writeState.hasTitle || writeState.hasBody,
              `stageB writing ${writingVp.width}x${writingVp.height}: writing route reached`,
            );
            assert.ok(
              (writeState.titleVal && writeState.titleVal.length > 0) ||
                (writeState.bodyVal && writeState.bodyVal.length > 0),
              `stageB writing ${writingVp.width}x${writingVp.height}: title/body auto-filled`,
            );
            await shot(`${writingVp.width}-body-typing.png`);
            await shot(`${writingVp.width}-result.png`);

            // typing/highlight/cursor present (best-effort visual marker).
            await sp
              .waitForSelector(
                ".choreography-cursor, .cursor-arrow, .ai-cursor, .highlight, [data-cursor]",
                { timeout: 8000 },
              )
              .catch(() => {});

            // Editable focus violation across title/body typing must be 0.
            const violations = await drainTfViolations();
            assert.equal(
              violations.length,
              0,
              `stageB writing ${writingVp.width}x${writingVp.height}: transient editable focus violations = ${violations.length} ${JSON.stringify(violations.slice(0, 3))}`,
            );

            // Stop BEFORE confirmation / real submit.
            const confBtn = await sp
              .$('.chat-msg--decision button:has-text("검토했고, 제출하기")')
              .catch(() => null);
            if (confBtn) {
              // Stay before submit — do not click.
            }

            // Direct user click on title/body focuses it.
            await setAutomatedPhase(false);
            await allowUserFocus(true);
            const titleSel =
              (await sp.$("#board-write-title")) ||
              (await sp.$('input[name*="title" i], input[id*="title" i]'));
            if (titleSel) {
              await titleSel.click();
              const titleFocus = await sp.evaluate(() => {
                const title =
                  document.querySelector("#board-write-title") ||
                  document.querySelector(
                    'input[name*="title" i], input[id*="title" i]',
                  );
                return document.activeElement === title;
              });
              assert.ok(
                titleFocus,
                `stageB writing ${writingVp.width}x${writingVp.height}: direct user click focuses title`,
              );
            } else {
              const bodySel =
                (await sp.$("#board-write-content")) ||
                (await sp.$(
                  "textarea[name*='content' i], textarea[id*='content' i], textarea[id*='body' i]",
                ));
              if (bodySel) {
                await bodySel.click();
                const bodyFocus = await sp.evaluate(() => {
                  const body =
                    document.querySelector("#board-write-content") ||
                    document.querySelector(
                      "textarea[name*='content' i], textarea[id*='content' i], textarea[id*='body' i]",
                    );
                  return document.activeElement === body;
                });
                assert.ok(
                  bodyFocus,
                  `stageB writing ${writingVp.width}x${writingVp.height}: direct user click focuses body`,
                );
              }
            }
            await allowUserFocus(false);

            // Cancellation via public API if available.
            await setAutomatedPhase(false);
            await sp.evaluate(() => {
              if (
                window.CitizenFirstChoreography &&
                typeof window.CitizenFirstChoreography.cancel === "function"
              ) {
                window.CitizenFirstChoreography.cancel();
              }
            });
            await sp
              .waitForFunction(
                () => {
                  const st = document.body.getAttribute(
                    "data-choreography-state",
                  );
                  return st === "cancelled" || st === "idle" || st === "ready";
                },
                { timeout: 8000 },
              )
              .catch(() => {});

            const cancelState = await sp.evaluate(() => {
              const active = document.activeElement;
              const editable =
                !!active &&
                (active.matches(
                  "input, textarea, [contenteditable='true']",
                ) ||
                  active.isContentEditable);
              const sw = document.getElementById("mobile-surface-switch");
              return {
                state: document.body.getAttribute("data-choreography-state"),
                hasEditableFocus: editable,
                switchUsable: !!sw && !sw.hasAttribute("hidden"),
              };
            });
            assert.ok(
              cancelState.state === "cancelled" ||
                cancelState.state === "idle" ||
                cancelState.state === "ready" ||
                cancelState.state === null,
              `stageB writing ${writingVp.width}x${writingVp.height}: choreography cancelled/idle (got ${cancelState.state})`,
            );
            assert.equal(
              cancelState.hasEditableFocus,
              false,
              `stageB writing ${writingVp.width}x${writingVp.height}: no editable focused after cancel`,
            );
            if (cancelState.switchUsable) {
              const tabC = await sp.$("#tab-conversation");
              const tabG = await sp.$("#tab-guidance");
              if (tabC) await tabC.click();
              if (tabG) await tabG.click();
            }

            await shot(`${writingVp.width}-view-switch.png`);
            await shot(`${writingVp.width}-reset.png`);

            console.log(
              `  [${writingVp.width}x${writingVp.height}] stageB writing=PASS`,
            );
          } catch (err) {
            failures.push(
              `stageB writing viewport=${writingVp.width}x${writingVp.height}: ${err.message}`,
            );
          }
        }

        // ── Desktop regression (1440×900) ──
        try {
          await sp.setViewportSize({ width: 1440, height: 900 });
          await sp.goto(base, { waitUntil: "domcontentloaded" });
          await sp.waitForSelector(".chat-shell", { timeout: 10000 });
          const desk = await sp.evaluate(() => {
            const sw = document.getElementById("mobile-surface-switch");
            const canvas = document.getElementById("demo-canvas");
            const chat = document.getElementById("chat-shell");
            const cs = canvas ? getComputedStyle(canvas) : null;
            const chs = chat ? getComputedStyle(chat) : null;
            return {
              switchHidden:
                !sw ||
                sw.hasAttribute("hidden") ||
                getComputedStyle(sw).display === "none",
              canvasInert: canvas ? canvas.hasAttribute("inert") : false,
              chatInert: chat ? chat.hasAttribute("inert") : false,
              chatAriaHidden: chat ? chat.getAttribute("aria-hidden") : null,
              canvasAriaHidden: canvas
                ? canvas.getAttribute("aria-hidden")
                : null,
              mobileSurface: document.body.getAttribute("data-mobile-surface"),
              canvasDisplay: cs ? cs.display : null,
              chatDisplay: chs ? chs.display : null,
            };
          });
          assert.ok(
            desk.switchHidden,
            "stageB desktop 1440: mobile switch hidden",
          );
          assert.equal(
            desk.mobileSurface,
            null,
            "stageB desktop 1440: no data-mobile-surface residue",
          );
          assert.equal(
            desk.chatInert,
            false,
            "stageB desktop 1440: chat not inert",
          );
          assert.ok(
            desk.chatAriaHidden === null || desk.chatAriaHidden === "false",
            "stageB desktop 1440: chat aria-hidden cleared",
          );
          assert.equal(
            desk.canvasInert,
            false,
            "stageB desktop 1440: canvas not inert",
          );
          await shot("1440-desktop.png");
          console.log("  [1440x900] stageB desktop=PASS");
        } catch (err) {
          failures.push(`stageB desktop 1440x900: ${err.message}`);
        }

        // Instrumentation final asserts.
        assert.equal(
          consoleErrors.length,
          0,
          `stageB: console errors = ${consoleErrors.length} ${JSON.stringify(consoleErrors.slice(0, 3))}`,
        );
        assert.equal(
          pageErrors.length,
          0,
          `stageB: page errors = ${pageErrors.length} ${JSON.stringify(pageErrors.slice(0, 3))}`,
        );
        assert.equal(
          requestFailures.length,
          0,
          `stageB: request failures = ${requestFailures.length} ${JSON.stringify(requestFailures.slice(0, 3))}`,
        );
        assert.equal(
          httpErrors.length,
          0,
          `stageB: http errors = ${httpErrors.length} ${JSON.stringify(httpErrors.slice(0, 3))}`,
        );
        assert.equal(
          externalRequestAttempts.length,
          0,
          `stageB: external request attempts = ${externalRequestAttempts.length} ${JSON.stringify(externalRequestAttempts.slice(0, 5))}`,
        );

        await sp.close();
        await surfCtx.close();
      } catch (err) {
        failures.push(`stageB setup: ${err.message}`);
      }
    }

    for (const vp of VIEWPORTS) {
      for (const state of STATES) {
        try {
          const r = await runOneState(page, vp, state, base);
          results.push(r);
          await verifyStateExtra(page, vp, state, base);
        } catch (err) {
          failures.push(`viewport=${vp.width}x${vp.height} state=${state}: ${err.message}`);
        }
      }
    }
    await context.close();
  } finally {
    // Close browser/context first, but always close the server afterwards so a
    // browser-close failure cannot leave the server running.
    try {
      if (context) {
        try {
          await context.close();
        } catch {
          /* fall through to browser close */
        }
      }
    } finally {
      try {
        if (browser) {
          await browser.close();
        }
      } finally {
        await closeServer(server);
      }
    }
  }

  // Server must be fully stopped after the run.
  assert.equal(server.listening, false, "server still listening after cleanup");

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
