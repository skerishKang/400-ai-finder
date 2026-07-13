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

        // Browser auto-requests /favicon.ico. The offline static tree does not
        // ship one; answer 204 so instrumentation does not treat the browser's
        // benign auto-request as a product asset failure.
        if (safePath === "favicon.ico") {
          res.writeHead(204);
          res.end();
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
  // Offline browser contract must use the static (query-sanitized, no live
  // ?mvp=1 injector) build. Live mode forces /api/mvp/ask which 404s on the
  // local static server and is outside this no-network contract.
  console.log("  building static site with", python, "--mode static");
  await run(python, ["scripts/build_cloudflare_pages.py", "--mode", "static"]);
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
    //
    // Stage B acceptance is fail-closed: no catch-swallow on required waits,
    // required selectors, screenshots, network errors, or state contracts.
    const mobileViewports = VIEWPORTS.filter((v) => v.width <= 767);
    if (mobileViewports.length) {
      console.log("\nRunning #1116 Stage B mobile surface scenario:");
      try {
        fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

        // Canonical selectors taken from real renderer/choreography sources
        // (citizen-action-demo-canvas.js / citizen-first-choreography.js).
        const CANONICAL_CURSOR_SELECTOR = '[data-agent-cursor="true"]';
        const CANONICAL_RESULT_SELECTOR = '[data-representative-contact="true"]';
        const CANONICAL_SEARCH_INPUT = ".bg-dept-search__input";
        const BOARD_WRITE_TITLE = "#board-write-title";
        const BOARD_WRITE_BODY = "#board-write-content";
        const TYPING_MARKER_SELECTOR =
          '[data-agent-typing="true"], .executor-typing';
        const HIGHLIGHT_MARKER_SELECTOR = ".executor-highlight";
        const CONFIRM_SUBMIT_SELECTOR =
          '.chat-msg--decision .chat-decision__button--primary:has-text("검토했고, 제출하기")';
        const CONFIRM_YES_SELECTOR =
          '.chat-msg--confirm-run button:has-text("예, 안내해 주세요")';

        const SEARCH_Q = "공동주택 관련 문의는 어느 부서에 해야 하나요?";
        const WRITE_Q = "가로등이 고장났어요. 신고할게요";

        // Exact expected screenshot set (repo-external under os.tmpdir()).
        // Writing flow uses distinct names so it never overwrites search evidence.
        const expectedScreenshots = [
          "320-entry.png",
          "320-confirm.png",
          "320-first-action.png",
          "320-search-typing.png",
          "320-result.png",
          "320-view-switch.png",
          "320-reset.png",
          "390-entry.png",
          "390-confirm.png",
          "390-first-action.png",
          "390-search-typing.png",
          "390-result.png",
          "390-view-switch.png",
          "390-reset.png",
          "390-writing-route.png",
          "390-writing-typing.png",
          "390-writing-cancelled.png",
          "1440-desktop.png",
        ];

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
            const loc = typeof msg.location === "function" ? msg.location() : null;
            consoleErrors.push({
              text: msg.text(),
              url: loc && loc.url ? loc.url : "",
              line: loc && typeof loc.lineNumber === "number" ? loc.lineNumber : null,
            });
          }
        });
        // Favicon excluded only. Same-origin failures are recorded.
        sp.on("requestfailed", (req) => {
          const url = req.url();
          try {
            const parsed = new URL(url);
            if (parsed.pathname === "/favicon.ico") return;
          } catch {
            // malformed URL also counts as failure
          }
          requestFailures.push({
            url,
            failure: (req.failure() && req.failure().errorText) || "unknown",
          });
        });
        // Favicon excluded only. Same-origin HTTP 4xx/5xx are recorded.
        sp.on("response", (resp) => {
          const url = resp.url();
          try {
            const parsed = new URL(url);
            if (parsed.pathname === "/favicon.ico") return;
          } catch {
            // malformed URL also inspected
          }
          if (resp.status() >= 400) {
            httpErrors.push({
              url,
              status: resp.status(),
            });
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

        // Screenshots are required Stage B evidence — failures must fail.
        const shot = async (name) => {
          const outputPath = path.join(SCREENSHOT_DIR, name);
          await sp.screenshot({
            path: outputPath,
            fullPage: false,
          });
          return outputPath;
        };

        async function assertNoEditableFocus(ctx) {
          const editable = await sp.evaluate(() => {
            const active = document.activeElement;
            return (
              !!active &&
              (active.matches("input, textarea, [contenteditable='true']") ||
                active.isContentEditable)
            );
          });
          assert.equal(
            editable,
            false,
            `${ctx}: editable activeElement must be none`,
          );
        }

        async function readSearchValue() {
          return sp.evaluate((sel) => {
            const input = document.querySelector(sel);
            return input ? String(input.value || "") : "";
          }, CANONICAL_SEARCH_INPUT);
        }

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
            const yesBtn = await sp.waitForSelector(CONFIRM_YES_SELECTOR, {
              timeout: 10000,
            });
            assert.ok(
              yesBtn,
              `stageB ${vp.width}x${vp.height}: confirm-run button not found`,
            );

            // Automated phase starts at confirm yes.
            await clearTfViolations();
            await setAutomatedPhase(true);
            await allowUserFocus(false);

            await yesBtn.click();
            await sp.waitForFunction(
              () =>
                document.body.getAttribute("data-mobile-surface") ===
                "guidance",
              { timeout: 10000 },
            );

            const afterConfirm = await sp.evaluate(() => {
              const tabC = document.getElementById("tab-conversation");
              const tabG = document.getElementById("tab-guidance");
              const canvas = document.getElementById("demo-canvas");
              const chatShell = document.getElementById("chat-shell");
              const cs = canvas ? getComputedStyle(canvas) : null;
              const active = document.activeElement;
              const editable =
                !!active &&
                (active.matches("input, textarea, [contenteditable='true']") ||
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
                chatInert: chatShell ? chatShell.hasAttribute("inert") : null,
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
              afterConfirm.canvasInert,
              false,
              `stageB ${vp.width}x${vp.height}: canvas must not be inert in guidance`,
            );
            assert.equal(
              afterConfirm.chatAriaHidden,
              "true",
              `stageB ${vp.width}x${vp.height}: chat aria-hidden=true in guidance`,
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

            // First cursor action: real AI cursor from CitizenActionDemoCanvas.
            await sp.waitForSelector(CANONICAL_CURSOR_SELECTOR, {
              state: "visible",
              timeout: 10000,
            });
            await shot(`${vp.width}-first-action.png`);

            // Search field typing — exact selector only, no generic fallback.
            await sp.waitForFunction(
              (sel) => {
                const input = document.querySelector(sel);
                return Boolean(input && input.value && input.value.trim());
              },
              CANONICAL_SEARCH_INPUT,
              { timeout: 15000 },
            );
            const searchValue = await readSearchValue();
            assert.ok(
              searchValue.trim().length > 0,
              `stageB ${vp.width}x${vp.height}: search field non-empty (got ${JSON.stringify(searchValue)})`,
            );
            await shot(`${vp.width}-search-typing.png`);

            // Automated phase editable focus violation must be 0 so far.
            let violations = await drainTfViolations();
            assert.equal(
              violations.length,
              0,
              `stageB ${vp.width}x${vp.height}: transient editable focus violations during automated search = ${violations.length} ${JSON.stringify(violations.slice(0, 3))}`,
            );

            // Apartment result: canonical representative-contact marker only.
            await sp.waitForSelector(CANONICAL_RESULT_SELECTOR, {
              state: "visible",
              timeout: 20000,
            });
            await shot(`${vp.width}-result.png`);

            violations = await drainTfViolations();
            assert.equal(
              violations.length,
              0,
              `stageB ${vp.width}x${vp.height}: transient editable focus violations confirm→result = ${violations.length} ${JSON.stringify(violations.slice(0, 3))}`,
            );

            // End automated phase for switch/user interactions.
            await setAutomatedPhase(false);

            // 4) Surface switch must preserve the current route/DOM snapshot.
            // Non-empty search typing is already hard-asserted above; after
            // submit/result the product may keep or clear the input. Surface
            // switching only requires before === after identity, not non-empty.
            const beforeSurfaceSwitch = await sp.evaluate(() => {
              const searchInput = document.querySelector(
                ".bg-dept-search__input",
              );
              const resultMarker = document.querySelector(
                '[data-representative-contact="true"]',
              );
              return {
                searchInputPresent: Boolean(searchInput),
                searchValue: searchInput ? searchInput.value : null,
                resultPresent: Boolean(resultMarker),
                firstUseState: document.body.getAttribute(
                  "data-first-use-state",
                ),
                choreographyState: document.body.getAttribute(
                  "data-choreography-state",
                ),
              };
            });
            assert.equal(
              beforeSurfaceSwitch.resultPresent,
              true,
              `stageB ${vp.width}x${vp.height}: result marker present before surface switch`,
            );

            const tabC2 = await sp.waitForSelector("#tab-conversation", {
              state: "visible",
              timeout: 5000,
            });
            await tabC2.click();
            const back = await sp.evaluate(() => {
              const tabC = document.getElementById("tab-conversation");
              const tabG = document.getElementById("tab-guidance");
              const chatShell = document.getElementById("chat-shell");
              const canvas = document.getElementById("demo-canvas");
              return {
                surface: document.body.getAttribute("data-mobile-surface"),
                tabCPressed: tabC ? tabC.getAttribute("aria-pressed") : null,
                tabGPressed: tabG ? tabG.getAttribute("aria-pressed") : null,
                chatAriaHidden: chatShell
                  ? chatShell.getAttribute("aria-hidden")
                  : null,
                chatInert: chatShell ? chatShell.hasAttribute("inert") : null,
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
              back.tabGPressed,
              "false",
              `stageB ${vp.width}x${vp.height}: guidance not pressed in conversation`,
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
            assert.equal(
              back.canvasInert,
              true,
              `stageB ${vp.width}x${vp.height}: canvas inert in conversation`,
            );
            assert.equal(
              back.canvasAriaHidden,
              "true",
              `stageB ${vp.width}x${vp.height}: canvas aria-hidden=true in conversation`,
            );

            const tabG2 = await sp.waitForSelector("#tab-guidance", {
              state: "visible",
              timeout: 5000,
            });
            await tabG2.click();
            const afterSurface = await sp.evaluate(() => {
              const tabC = document.getElementById("tab-conversation");
              const tabG = document.getElementById("tab-guidance");
              const chatShell = document.getElementById("chat-shell");
              const canvas = document.getElementById("demo-canvas");
              return {
                surface: document.body.getAttribute("data-mobile-surface"),
                tabCPressed: tabC ? tabC.getAttribute("aria-pressed") : null,
                tabGPressed: tabG ? tabG.getAttribute("aria-pressed") : null,
                chatAriaHidden: chatShell
                  ? chatShell.getAttribute("aria-hidden")
                  : null,
                chatInert: chatShell ? chatShell.hasAttribute("inert") : null,
                canvasInert: canvas ? canvas.hasAttribute("inert") : null,
                canvasAriaHidden: canvas
                  ? canvas.getAttribute("aria-hidden")
                  : null,
              };
            });
            assert.equal(
              afterSurface.surface,
              "guidance",
              `stageB ${vp.width}x${vp.height}: back to guidance`,
            );
            assert.equal(
              afterSurface.tabCPressed,
              "false",
              `stageB ${vp.width}x${vp.height}: conversation not pressed after guidance return`,
            );
            assert.equal(
              afterSurface.tabGPressed,
              "true",
              `stageB ${vp.width}x${vp.height}: guidance pressed after return`,
            );
            assert.equal(
              afterSurface.chatAriaHidden,
              "true",
              `stageB ${vp.width}x${vp.height}: chat aria-hidden=true after guidance return`,
            );
            assert.equal(
              afterSurface.chatInert,
              true,
              `stageB ${vp.width}x${vp.height}: chat inert after guidance return`,
            );
            assert.equal(
              afterSurface.canvasInert,
              false,
              `stageB ${vp.width}x${vp.height}: canvas active (not inert) after guidance return`,
            );
            assert.equal(
              afterSurface.canvasAriaHidden,
              "false",
              `stageB ${vp.width}x${vp.height}: canvas aria-hidden=false after guidance return`,
            );

            const afterSurfaceSwitch = await sp.evaluate(() => {
              const searchInput = document.querySelector(
                ".bg-dept-search__input",
              );
              const resultMarker = document.querySelector(
                '[data-representative-contact="true"]',
              );
              return {
                searchInputPresent: Boolean(searchInput),
                searchValue: searchInput ? searchInput.value : null,
                resultPresent: Boolean(resultMarker),
                firstUseState: document.body.getAttribute(
                  "data-first-use-state",
                ),
                choreographyState: document.body.getAttribute(
                  "data-choreography-state",
                ),
              };
            });
            assert.equal(
              afterSurfaceSwitch.searchInputPresent,
              beforeSurfaceSwitch.searchInputPresent,
              `stageB ${vp.width}x${vp.height}: surface switch must preserve search-input presence`,
            );
            assert.equal(
              afterSurfaceSwitch.searchValue,
              beforeSurfaceSwitch.searchValue,
              `stageB ${vp.width}x${vp.height}: surface switch must preserve the exact current search value (before=${JSON.stringify(beforeSurfaceSwitch.searchValue)} after=${JSON.stringify(afterSurfaceSwitch.searchValue)})`,
            );
            assert.equal(
              afterSurfaceSwitch.resultPresent,
              beforeSurfaceSwitch.resultPresent,
              `stageB ${vp.width}x${vp.height}: surface switch must preserve the apartment result marker`,
            );
            assert.equal(
              afterSurfaceSwitch.firstUseState,
              beforeSurfaceSwitch.firstUseState,
              `stageB ${vp.width}x${vp.height}: surface switch must preserve first-use state`,
            );
            assert.equal(
              afterSurfaceSwitch.choreographyState,
              beforeSurfaceSwitch.choreographyState,
              `stageB ${vp.width}x${vp.height}: surface switch must preserve choreography state`,
            );
            await shot(`${vp.width}-view-switch.png`);

            // 5) direct user focus: click composer → activeElement is composer.
            const tabC3 = await sp.waitForSelector("#tab-conversation", {
              state: "visible",
              timeout: 5000,
            });
            await tabC3.click();
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

            // 6) reset → entry + conversation default state (required).
            // Clear residual focus from the explicit composer click above so the
            // post-reset check measures product auto-focus policy only. On mobile,
            // focusComposerIfAllowed() must NOT re-focus the composer after reset.
            await setAutomatedPhase(false);
            await sp.evaluate(() => {
              const active = document.activeElement;
              if (active && typeof active.blur === "function") active.blur();
            });
            const resetApi = await sp.evaluate(() => {
              return Boolean(
                window.CitizenFirstUseShell &&
                  typeof window.CitizenFirstUseShell.reset === "function",
              );
            });
            assert.ok(
              resetApi,
              `stageB ${vp.width}x${vp.height}: CitizenFirstUseShell.reset public API must exist`,
            );
            await sp.evaluate(() => {
              window.CitizenFirstUseShell.reset();
            });
            await sp.waitForFunction(
              () =>
                document.body.getAttribute("data-first-use-state") === "entry",
              { timeout: 10000 },
            );
            const resetState = await sp.evaluate(() => {
              const sw = document.getElementById("mobile-surface-switch");
              const tabC = document.getElementById("tab-conversation");
              const tabG = document.getElementById("tab-guidance");
              const active = document.activeElement;
              const editable =
                !!active &&
                (active.matches("input, textarea, [contenteditable='true']") ||
                  active.isContentEditable);
              return {
                state: document.body.getAttribute("data-first-use-state"),
                switchHidden: !!sw && sw.hasAttribute("hidden"),
                convPressed: tabC ? tabC.getAttribute("aria-pressed") : null,
                guidPressed: tabG ? tabG.getAttribute("aria-pressed") : null,
                mobileSurface:
                  document.body.getAttribute("data-mobile-surface"),
                editableFocused: editable,
                activeId: active && active.id ? active.id : "",
                activeClass:
                  active && active.className
                    ? String(active.className)
                    : "",
              };
            });
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
              resetState.guidPressed,
              "false",
              `stageB ${vp.width}x${vp.height}: guidance not pressed after reset`,
            );
            assert.ok(
              resetState.mobileSurface === null ||
                resetState.mobileSurface === "" ||
                resetState.mobileSurface === "conversation",
              `stageB ${vp.width}x${vp.height}: data-mobile-surface cleared or coherent entry (got ${resetState.mobileSurface})`,
            );
            assert.equal(
              resetState.editableFocused,
              false,
              `stageB ${vp.width}x${vp.height}: no automated editable focus after reset (active=${resetState.activeId || resetState.activeClass || "none"})`,
            );
            await shot(`${vp.width}-reset.png`);

            // Final automated-phase violations for this viewport (should still be 0).
            violations = await drainTfViolations();
            assert.equal(
              violations.length,
              0,
              `stageB ${vp.width}x${vp.height}: final transient editable focus violations = ${violations.length}`,
            );

            console.log(`  [${vp.width}x${vp.height}] stageB search=PASS`);
          } catch (err) {
            failures.push(
              `stageB search viewport=${vp.width}x${vp.height}: ${err.message}`,
            );
          }
        }

        // ── Writing journey (390×844): title + body auto-fill + no-submit ──
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
            const yesBtn = await sp.waitForSelector(CONFIRM_YES_SELECTOR, {
              timeout: 10000,
            });
            assert.ok(
              yesBtn,
              `stageB writing ${writingVp.width}x${writingVp.height}: confirm button not found`,
            );

            await clearTfViolations();
            await setAutomatedPhase(true);
            await yesBtn.click();

            await sp.waitForFunction(
              () =>
                document.body.getAttribute("data-mobile-surface") ===
                "guidance",
              { timeout: 10000 },
            );

            // First AI cursor action must appear.
            await sp.waitForSelector(CANONICAL_CURSOR_SELECTOR, {
              state: "visible",
              timeout: 10000,
            });

            // Writing route: exact board fields, no fallback selectors.
            await sp.waitForSelector(BOARD_WRITE_TITLE, {
              state: "visible",
              timeout: 15000,
            });
            await sp.waitForSelector(BOARD_WRITE_BODY, {
              state: "visible",
              timeout: 15000,
            });
            await shot("390-writing-route.png");

            // Visual markers while automated typing is active.
            await sp.waitForSelector(TYPING_MARKER_SELECTOR, {
              timeout: 20000,
            });
            await sp.waitForSelector(HIGHLIGHT_MARKER_SELECTOR, {
              timeout: 20000,
            });
            await sp.waitForSelector(CANONICAL_CURSOR_SELECTOR, {
              state: "visible",
              timeout: 10000,
            });

            // Both title and body must be auto-filled (not OR).
            await sp.waitForFunction(
              () => {
                const title = document.querySelector("#board-write-title");
                const body = document.querySelector("#board-write-content");
                return Boolean(
                  title &&
                    body &&
                    title.value &&
                    title.value.trim() &&
                    body.value &&
                    body.value.trim(),
                );
              },
              { timeout: 30000 },
            );

            const writeState = await sp.evaluate(() => {
              const title = document.querySelector("#board-write-title");
              const body = document.querySelector("#board-write-content");
              return {
                titleVal: title ? String(title.value || "") : "",
                bodyVal: body ? String(body.value || "") : "",
              };
            });
            assert.ok(
              writeState.titleVal.trim().length > 0,
              `stageB writing ${writingVp.width}x${writingVp.height}: title auto-filled non-empty (got ${JSON.stringify(writeState.titleVal)})`,
            );
            assert.ok(
              writeState.bodyVal.trim().length > 0,
              `stageB writing ${writingVp.width}x${writingVp.height}: body auto-filled non-empty (got ${JSON.stringify(writeState.bodyVal.slice(0, 40))})`,
            );
            await shot("390-writing-typing.png");

            // Editable focus violation across title/body typing must be 0.
            const violations = await drainTfViolations();
            assert.equal(
              violations.length,
              0,
              `stageB writing ${writingVp.width}x${writingVp.height}: transient editable focus violations = ${violations.length} ${JSON.stringify(violations.slice(0, 3))}`,
            );

            // No-submit boundary: exact waiting_confirmation state, then
            // surface-switch to conversation so the confirmation control is
            // visible (chat is display:none while guidance is active).
            // Do NOT click the submit confirmation control.
            await sp.waitForFunction(
              () =>
                document.body.getAttribute("data-choreography-state") ===
                "waiting_confirmation",
              { timeout: 20000 },
            );
            await setAutomatedPhase(false);
            const tabCForConfirm = await sp.waitForSelector(
              "#tab-conversation",
              { state: "visible", timeout: 5000 },
            );
            await tabCForConfirm.click();
            await sp.waitForSelector(CONFIRM_SUBMIT_SELECTOR, {
              state: "visible",
              timeout: 10000,
            });
            const noSubmit = await sp.evaluate(() => {
              const submit = document.querySelector("#btn-board-submit");
              const conf = document.querySelector(
                ".chat-msg--decision .chat-decision__button--primary",
              );
              return {
                state: document.body.getAttribute("data-choreography-state"),
                confText: conf ? String(conf.textContent || "").trim() : "",
                submitText: submit ? String(submit.textContent || "") : "",
                hasReceipt:
                  !!document.querySelector(
                    '[data-route-id="complaint-review"]',
                  ) || !!document.body.innerText.match(/성공적으로 접수/),
              };
            });
            assert.equal(
              noSubmit.state,
              "waiting_confirmation",
              `stageB writing ${writingVp.width}x${writingVp.height}: must stop at waiting_confirmation`,
            );
            assert.equal(
              noSubmit.confText,
              "검토했고, 제출하기",
              `stageB writing ${writingVp.width}x${writingVp.height}: confirmation control must be present`,
            );
            assert.ok(
              !noSubmit.submitText.includes("제출하는 중"),
              `stageB writing ${writingVp.width}x${writingVp.height}: submit must not have been triggered`,
            );
            assert.equal(
              noSubmit.hasReceipt,
              false,
              `stageB writing ${writingVp.width}x${writingVp.height}: no submission receipt`,
            );

            // Direct user click on title/body focuses them (Playwright click).
            await allowUserFocus(true);
            const tabGWrite = await sp.waitForSelector("#tab-guidance", {
              state: "visible",
              timeout: 5000,
            });
            await tabGWrite.click();
            await sp.waitForFunction(
              () =>
                document.body.getAttribute("data-mobile-surface") ===
                "guidance",
              { timeout: 5000 },
            );
            await sp.click(BOARD_WRITE_TITLE);
            const titleFocus = await sp.evaluate(() => {
              const title = document.querySelector("#board-write-title");
              return document.activeElement === title;
            });
            assert.ok(
              titleFocus,
              `stageB writing ${writingVp.width}x${writingVp.height}: direct user click focuses title`,
            );
            await sp.click(BOARD_WRITE_BODY);
            const bodyFocus = await sp.evaluate(() => {
              const body = document.querySelector("#board-write-content");
              return document.activeElement === body;
            });
            assert.ok(
              bodyFocus,
              `stageB writing ${writingVp.width}x${writingVp.height}: direct user click focuses body`,
            );
            await allowUserFocus(false);

            console.log(
              `  [${writingVp.width}x${writingVp.height}] stageB writing=PASS`,
            );
          } catch (err) {
            failures.push(
              `stageB writing viewport=${writingVp.width}x${writingVp.height}: ${err.message}`,
            );
          }
        }

        // ── Cancellation: cancel while actually running (fresh journey) ──
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
            const yesBtn = await sp.waitForSelector(CONFIRM_YES_SELECTOR, {
              timeout: 10000,
            });
            await clearTfViolations();
            await setAutomatedPhase(true);
            await yesBtn.click();

            // Hard-assert running before cancel.
            await sp.waitForFunction(
              () =>
                document.body.getAttribute("data-choreography-state") ===
                "running",
              { timeout: 10000 },
            );
            const runningBefore = await sp.evaluate(
              () => document.body.getAttribute("data-choreography-state"),
            );
            assert.equal(
              runningBefore,
              "running",
              `stageB cancel ${writingVp.width}x${writingVp.height}: must be running before cancel`,
            );

            const cancelApi = await sp.evaluate(() => {
              return Boolean(
                window.CitizenFirstChoreography &&
                  typeof window.CitizenFirstChoreography.cancel === "function",
              );
            });
            assert.ok(
              cancelApi,
              `stageB cancel ${writingVp.width}x${writingVp.height}: CitizenFirstChoreography.cancel must exist`,
            );
            await sp.evaluate(() => {
              window.CitizenFirstChoreography.cancel();
            });

            // Only "cancelled" is accepted — not idle/ready/done/complete/null.
            await sp.waitForFunction(
              () =>
                document.body.getAttribute("data-choreography-state") ===
                "cancelled",
              { timeout: 8000 },
            );
            const cancelState = await sp.evaluate(() => {
              const active = document.activeElement;
              const editable =
                !!active &&
                (active.matches("input, textarea, [contenteditable='true']") ||
                  active.isContentEditable);
              const sw = document.getElementById("mobile-surface-switch");
              const tabC = document.getElementById("tab-conversation");
              const tabG = document.getElementById("tab-guidance");
              return {
                state: document.body.getAttribute("data-choreography-state"),
                hasEditableFocus: editable,
                switchUsable: !!sw && !sw.hasAttribute("hidden"),
                hasTabC: !!tabC,
                hasTabG: !!tabG,
                hasReceipt: !!document.body.innerText.match(/성공적으로 접수/),
              };
            });
            assert.equal(
              cancelState.state,
              "cancelled",
              `stageB cancel ${writingVp.width}x${writingVp.height}: exact state must be cancelled (got ${cancelState.state})`,
            );
            assert.equal(
              cancelState.hasEditableFocus,
              false,
              `stageB cancel ${writingVp.width}x${writingVp.height}: no editable focused after cancel`,
            );
            assert.ok(
              cancelState.switchUsable,
              `stageB cancel ${writingVp.width}x${writingVp.height}: surface switch must remain usable`,
            );
            assert.ok(
              cancelState.hasTabC && cancelState.hasTabG,
              `stageB cancel ${writingVp.width}x${writingVp.height}: conversation and guidance buttons present`,
            );
            assert.equal(
              cancelState.hasReceipt,
              false,
              `stageB cancel ${writingVp.width}x${writingVp.height}: actual submit count must be 0`,
            );

            // Switch usability: both surfaces operable after cancel.
            await setAutomatedPhase(false);
            const tabC = await sp.waitForSelector("#tab-conversation", {
              state: "visible",
              timeout: 5000,
            });
            await tabC.click();
            const afterConv = await sp.evaluate(
              () => document.body.getAttribute("data-mobile-surface"),
            );
            assert.equal(
              afterConv,
              "conversation",
              `stageB cancel ${writingVp.width}x${writingVp.height}: conversation switch works after cancel`,
            );
            const tabG = await sp.waitForSelector("#tab-guidance", {
              state: "visible",
              timeout: 5000,
            });
            await tabG.click();
            const afterGuid = await sp.evaluate(
              () => document.body.getAttribute("data-mobile-surface"),
            );
            assert.equal(
              afterGuid,
              "guidance",
              `stageB cancel ${writingVp.width}x${writingVp.height}: guidance switch works after cancel`,
            );

            await assertNoEditableFocus(
              `stageB cancel ${writingVp.width}x${writingVp.height}`,
            );
            await shot("390-writing-cancelled.png");

            console.log(
              `  [${writingVp.width}x${writingVp.height}] stageB cancel=PASS`,
            );
          } catch (err) {
            failures.push(
              `stageB cancel viewport=${writingVp.width}x${writingVp.height}: ${err.message}`,
            );
          }
        }

        // ── Desktop regression (1440×900) ──
        // Entry and split have different canvas availability contracts:
        //   entry → canvas unavailable (inert + aria-hidden)
        //   split/transitioning → canvas available (not inert)
        try {
          await sp.setViewportSize({ width: 1440, height: 900 });
          await sp.goto(base, { waitUntil: "domcontentloaded" });
          await sp.waitForSelector(".chat-shell", { timeout: 10000 });
          const deskEntry = await sp.evaluate(() => {
            const sw = document.getElementById("mobile-surface-switch");
            const canvas = document.getElementById("demo-canvas");
            const chat = document.getElementById("chat-shell");
            const chs = chat ? getComputedStyle(chat) : null;
            return {
              firstUse: document.body.getAttribute("data-first-use-state"),
              switchHidden:
                !sw ||
                sw.hasAttribute("hidden") ||
                getComputedStyle(sw).display === "none",
              canvasPresent: !!canvas,
              canvasInert: canvas ? canvas.hasAttribute("inert") : false,
              canvasAriaHidden: canvas
                ? canvas.getAttribute("aria-hidden")
                : null,
              chatInert: chat ? chat.hasAttribute("inert") : false,
              chatAriaHidden: chat ? chat.getAttribute("aria-hidden") : null,
              mobileSurface: document.body.getAttribute("data-mobile-surface"),
              chatDisplay: chs ? chs.display : null,
            };
          });
          assert.equal(
            deskEntry.firstUse,
            "entry",
            "stageB desktop 1440 entry: data-first-use-state=entry",
          );
          assert.ok(
            deskEntry.switchHidden,
            "stageB desktop 1440 entry: mobile switch hidden",
          );
          assert.equal(
            deskEntry.mobileSurface,
            null,
            "stageB desktop 1440 entry: no data-mobile-surface",
          );
          assert.ok(
            deskEntry.chatDisplay && deskEntry.chatDisplay !== "none",
            "stageB desktop 1440 entry: chat visible",
          );
          assert.equal(
            deskEntry.chatInert,
            false,
            "stageB desktop 1440 entry: chat not inert",
          );
          assert.ok(
            deskEntry.chatAriaHidden === null ||
              deskEntry.chatAriaHidden === "false",
            "stageB desktop 1440 entry: chat aria-hidden cleared",
          );
          assert.ok(
            deskEntry.canvasPresent,
            "stageB desktop 1440 entry: canvas DOM present",
          );
          // Product setCanvasAvailability(false) on entry.
          assert.equal(
            deskEntry.canvasInert,
            true,
            "stageB desktop 1440 entry: canvas inert while unavailable",
          );
          assert.equal(
            deskEntry.canvasAriaHidden,
            "true",
            "stageB desktop 1440 entry: canvas aria-hidden=true while unavailable",
          );

          // Desktop composer remains operable on entry.
          await sp.click(".chat-composer__input");
          const deskComposerFocus = await sp.evaluate(
            () =>
              document.activeElement ===
              document.querySelector(".chat-composer__input"),
          );
          assert.ok(
            deskComposerFocus,
            "stageB desktop 1440 entry: composer click focuses input",
          );

          // Deterministic search journey → split, with desktop automated focus.
          await sp.fill(".chat-composer__input", SEARCH_Q);
          await sp.click(".chat-composer__send");
          const deskYes = await sp.waitForSelector(CONFIRM_YES_SELECTOR, {
            timeout: 10000,
          });
          await deskYes.click();

          // Split/transitioning makes canvas available on desktop.
          await sp.waitForFunction(
            () => {
              const st = document.body.getAttribute("data-first-use-state");
              return st === "split" || st === "transitioning";
            },
            { timeout: 10000 },
          );

          // Capture desktop automated search focus during the typing step
          // (not after later result focus drift).
          await sp.waitForFunction(
            (sel) => {
              const input = document.querySelector(sel);
              return Boolean(
                input &&
                  document.activeElement === input &&
                  input.value &&
                  input.value.trim().length > 0,
              );
            },
            CANONICAL_SEARCH_INPUT,
            { timeout: 20000 },
          );
          const deskSearch = await sp.evaluate((sel) => {
            const input = document.querySelector(sel);
            return {
              value: input ? String(input.value || "") : "",
              focusedOnSearch: document.activeElement === input,
            };
          }, CANONICAL_SEARCH_INPUT);
          assert.ok(
            deskSearch.value.trim().length > 0,
            `stageB desktop 1440 split: search auto-typed (got ${JSON.stringify(deskSearch.value)})`,
          );
          assert.ok(
            deskSearch.focusedOnSearch,
            "stageB desktop 1440 split: activeElement === .bg-dept-search__input during automated typing",
          );

          await sp.waitForSelector(CANONICAL_RESULT_SELECTOR, {
            state: "visible",
            timeout: 20000,
          });

          // Wait until product settles on split (not still transitioning).
          await sp.waitForFunction(
            () =>
              document.body.getAttribute("data-first-use-state") === "split",
            { timeout: 15000 },
          );

          const deskSplit = await sp.evaluate(() => {
            const sw = document.getElementById("mobile-surface-switch");
            const chat = document.getElementById("chat-shell");
            const canvas = document.getElementById("demo-canvas");
            return {
              firstUse: document.body.getAttribute("data-first-use-state"),
              mobileSurface: document.body.getAttribute("data-mobile-surface"),
              switchHidden:
                !sw ||
                sw.hasAttribute("hidden") ||
                getComputedStyle(sw).display === "none",
              chatInert: chat ? chat.hasAttribute("inert") : false,
              canvasInert: canvas ? canvas.hasAttribute("inert") : false,
              chatAriaHidden: chat ? chat.getAttribute("aria-hidden") : null,
              canvasAriaHidden: canvas
                ? canvas.getAttribute("aria-hidden")
                : null,
              chatDisplay: chat ? getComputedStyle(chat).display : null,
              canvasDisplay: canvas ? getComputedStyle(canvas).display : null,
            };
          });
          assert.equal(
            deskSplit.firstUse,
            "split",
            "stageB desktop 1440 split: data-first-use-state=split",
          );
          assert.ok(
            deskSplit.switchHidden,
            "stageB desktop 1440 split: mobile switch hidden",
          );
          assert.equal(
            deskSplit.mobileSurface,
            null,
            "stageB desktop 1440 split: no data-mobile-surface",
          );
          assert.equal(
            deskSplit.chatInert,
            false,
            "stageB desktop 1440 split: chat not inert",
          );
          assert.equal(
            deskSplit.canvasInert,
            false,
            "stageB desktop 1440 split: canvas not inert",
          );
          assert.ok(
            deskSplit.chatAriaHidden === null ||
              deskSplit.chatAriaHidden === "false",
            "stageB desktop 1440 split: chat aria-hidden is not true",
          );
          assert.equal(
            deskSplit.canvasAriaHidden,
            "false",
            "stageB desktop 1440 split: canvas aria-hidden=false",
          );
          assert.ok(
            deskSplit.chatDisplay && deskSplit.chatDisplay !== "none",
            "stageB desktop 1440 split: chat visible",
          );
          assert.ok(
            deskSplit.canvasDisplay && deskSplit.canvasDisplay !== "none",
            "stageB desktop 1440 split: canvas visible",
          );

          // Evidence of active desktop split, not entry.
          await shot("1440-desktop.png");
          console.log("  [1440x900] stageB desktop=PASS");
        } catch (err) {
          failures.push(`stageB desktop 1440x900: ${err.message}`);
        }

        // Exact screenshot evidence set (required, non-empty files).
        for (const name of expectedScreenshots) {
          const outputPath = path.join(SCREENSHOT_DIR, name);
          assert.ok(
            fs.existsSync(outputPath),
            `missing screenshot: ${outputPath}`,
          );
          assert.ok(
            fs.statSync(outputPath).size > 0,
            `empty screenshot: ${outputPath}`,
          );
        }
        const shotListing = expectedScreenshots
          .map((name) => {
            const outputPath = path.join(SCREENSHOT_DIR, name);
            const size = fs.statSync(outputPath).size;
            return `    ${name} (${size} bytes)`;
          })
          .join("\n");
        console.log(`  screenshot directory: ${SCREENSHOT_DIR}`);
        console.log(`  screenshots:\n${shotListing}`);

        // Instrumentation final hard asserts.
        // Report every bucket together so a first failing deepEqual cannot hide
        // the actual 404 URLs captured by the response listener.
        const instrumentationSummary = {
          consoleErrors,
          pageErrors,
          requestFailures,
          httpErrors,
          externalRequestAttempts,
        };
        assert.deepEqual(
          consoleErrors,
          [],
          `console errors: ${JSON.stringify(instrumentationSummary)}`,
        );
        assert.deepEqual(
          pageErrors,
          [],
          `page errors: ${JSON.stringify(instrumentationSummary)}`,
        );
        assert.deepEqual(
          requestFailures,
          [],
          `request failures: ${JSON.stringify(instrumentationSummary)}`,
        );
        assert.deepEqual(
          httpErrors,
          [],
          `HTTP errors: ${JSON.stringify(instrumentationSummary)}`,
        );
        assert.deepEqual(
          externalRequestAttempts,
          [],
          `external request attempts: ${JSON.stringify(instrumentationSummary)}`,
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
