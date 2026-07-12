// tests/browser/verify_first_use_responsive.mjs
//
// Deterministic real-browser responsive + entry-panel contract for #1066.
//
// Hardens the responsive browser contract:
//   1. A browser launch failure must FAIL (never silently skip).
//   2. Real keyboard focus-visible state of input and send is verified
//      independently.
//   3. The fixed port 4173 collision / wrong-server problem is removed by
//      serving the built static site from an OS-assigned ephemeral port.
//   4. The #1066 first-use entry panel (prioritized resident tasks) is
//      verified across 320/390/768/1440 with secondary disclosure, canonical
//      submission capture, and composer-geometry stability.
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

const PRIMARY = [
  "불법 주정차 신고는 어디서 하나요?",
  "공동주택 관련 문의는 어느 부서에 해야 하나요?",
  "매트리스 폐기 신청은 어디서 하나요?",
];
const SECONDARY = [
  "여권 발급은 어디서 하나요?",
  "무인민원발급기 어디 있어요?",
  "가로등이 고장났어요. 신고할게요",
  "쓰레기 무단투기 신고할래 (AI 도움)",
];

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
      focusVisible: el.matches(":focus-visible"),
      focused: el.matches(":focus"),
      outlineStyle: cs.outlineStyle,
      outlineWidth,
      outlineColor: cs.outlineColor,
      outlineOffset,
      box,
      clips,
      layoutClipping,
    };
  }, selector);

  assert.ok(info.exists, `${selector} does not exist [${ctx}]`);
  const activeLabel = info.activeElementMatches
    ? `${info.selector}`
    : "(mismatch)";
  assert.ok(info.activeElementMatches, `${selector} not activeElement (${activeLabel}) [${ctx}]`);
  assert.ok(info.focused, `${selector} is not :focus [${ctx}]`);
  assert.ok(info.focusVisible, `${selector} is not :focus-visible [${ctx}]`);
  assert.ok(info.outlineStyle !== "none", `${selector} outline-style none [${ctx}]`);
  assert.ok(info.outlineWidth >= 1, `${selector} outline width < 1px [${ctx}]`);
  assert.ok(
    info.outlineColor !== "transparent" && info.outlineColor !== "rgba(0, 0, 0, 0)",
    `${selector} outline transparent [${ctx}]`,
  );
  assert.ok(info.outlineOffset >= 0, `${selector} outline offset < 0 [${ctx}]`);

  assert.ok(info.clips.length > 0, `${selector} found no clipping ancestors [${ctx}]`);
  if (info.layoutClipping) {
    assert.ok(
      info.clips.some((c) => String(c.cls).split(/\s+/).includes("first-use-layout")),
      `${selector} did not detect .first-use-layout as clipping [${ctx}]`,
    );
  }

  const vw = await page.evaluate(() => window.innerWidth);
  const vh = await page.evaluate(() => window.innerHeight);
  assert.ok(
    info.box.left >= -TOL && info.box.right <= vw + TOL,
    `${selector} outline clipped horizontally [${ctx}]`,
  );
  assert.ok(
    info.box.top >= -TOL && info.box.bottom <= vh + TOL,
    `${selector} outline clipped vertically [${ctx}]`,
  );

  for (const c of info.clips) {
    if (c.clipsX) {
      assert.ok(info.box.left >= c.rect.left - TOL, `${selector} left clipped [${ctx}]`);
      assert.ok(info.box.right <= c.rect.right + TOL, `${selector} right clipped [${ctx}]`);
    }
    if (c.clipsY) {
      assert.ok(info.box.top >= c.rect.top - TOL, `${selector} top clipped [${ctx}]`);
      assert.ok(info.box.bottom <= c.rect.bottom + TOL, `${selector} bottom clipped [${ctx}]`);
    }
  }
  return info;
}

function measure(page) {
  return page.evaluate(() => {
    const html = document.documentElement;
    const body = document.body;
    const q = (sel) => document.querySelector(sel);
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
      if (cs.visibility === "hidden") return false;
      // getComputedStyle returns a child's own display even inside a
      // display:none ancestor, so use getClientRects to detect real rendering.
      return el.getClientRects().length > 0;
    };
    const chat = q(".chat-shell");
    const entry = q("#chat-entry-panel");
    const thread = q("#chat-thread");
    const composer = q(".chat-composer");
    const input = q(".chat-composer__input");
    const send = q(".chat-composer__send");
    const toggle = q("#chat-more-tasks");
    const primaryGroup = q("#chat-primary-tasks");
    const secondaryGroup = q("#chat-secondary-tasks");
    const primaryEls = primaryGroup
      ? Array.from(primaryGroup.querySelectorAll("[data-chip-question]"))
      : [];
    const secondaryEls = secondaryGroup
      ? Array.from(secondaryGroup.querySelectorAll("[data-chip-question]"))
      : [];
    const visCount = (els) => els.filter((el) => vis(el)).length;
    const labelClips = primaryEls
      .map((el) => {
        const label = el.querySelector(".chat-task__label");
        if (!label) return null;
        return { scrollWidth: label.scrollWidth, clientWidth: label.clientWidth };
      })
      .filter(Boolean);
    return {
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      state: body.getAttribute("data-first-use-state"),
      htmlScrollWidth: html.scrollWidth,
      bodyScrollWidth: body.scrollWidth,
      htmlClientWidth: html.clientWidth,
      present: {
        chat: !!(chat && vis(chat)),
        header: !!q(".chat-shell__header") && vis(q(".chat-shell__header")),
        entry: !!(entry && vis(entry)),
        thread: !!(thread && vis(thread)),
        composer: !!(composer && vis(composer)),
        input: !!(input && vis(input)),
        send: !!(send && vis(send)),
        toggle: !!(toggle && vis(toggle)),
      },
      visPrimary: visCount(primaryEls),
      visSecondary: visCount(secondaryEls),
      chat: rect(chat),
      header: rect(q(".chat-shell__header")),
      entry: rect(entry),
      thread: rect(thread),
      composer: rect(composer),
      input: rect(input),
      send: rect(send),
      toggle: rect(toggle),
      taskRegion: entry && vis(entry) ? rect(entry) : rect(thread),
      labelClips,
      toggleExpanded: toggle ? toggle.getAttribute("aria-expanded") : null,
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
    `${label}: html.scrollWidth (${m.htmlScrollWidth}) must not exceed clientWidth (${m.htmlClientWidth}) [${ctx}]`,
  );
  assert.ok(
    m.bodyScrollWidth <= m.viewportWidth + TOL,
    `${label}: body.scrollWidth (${m.bodyScrollWidth}) must not exceed viewport (${m.viewportWidth}) [${ctx}]`,
  );
}

function assertInsideChat(childRect, chatRect, name, ctx) {
  assert.ok(childRect && chatRect, `${name} missing rect [${ctx}]`);
  assert.ok(
    childRect.left >= chatRect.left - TOL,
    `${name} left (${childRect.left}) >= chat left (${chatRect.left}) [${ctx}]`,
  );
  assert.ok(
    childRect.right <= chatRect.right + TOL,
    `${name} right (${childRect.right}) <= chat right (${chatRect.right}) [${ctx}]`,
  );
}

function assertInsideViewport(rect, name, ctx, vw, vh) {
  assert.ok(rect, `${name} missing rect [${ctx}]`);
  assert.ok(rect.left >= -TOL, `${name} left (${rect.left}) >= 0 [${ctx}]`);
  assert.ok(
    rect.right <= vw + TOL,
    `${name} right (${rect.right}) <= viewportWidth (${vw}) [${ctx}]`,
  );
  assert.ok(rect.top >= -TOL, `${name} top (${rect.top}) >= 0 [${ctx}]`);
  assert.ok(
    rect.bottom <= vh + TOL,
    `${name} bottom (${rect.bottom}) <= viewportHeight (${vh}) [${ctx}]`,
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
    const t = document.getElementById("chat-thread");
    if (t) t.hidden = false;
    const e = document.getElementById("chat-entry-panel");
    if (e) e.hidden = true;
  });
}

// Collect the keyboard focus order starting from body focus until the send
// button is reached. Returns a list of descriptors: 'q:<canonical>' for task
// buttons, '#<id>' for id'd controls, or the tag name.
async function collectFocusOrder(page, maxTabs = 40) {
  await page.evaluate(() => {
    if (document.activeElement && document.activeElement !== document.body) {
      document.activeElement.blur();
    }
  });
  const order = [];
  for (let i = 0; i < maxTabs; i++) {
    const info = await page.evaluate(() => {
      const ae = document.activeElement;
      if (!ae || ae === document.body) return { d: "body", isSend: false };
      let d;
      if (ae.hasAttribute("data-chip-question")) d = "q:" + ae.getAttribute("data-chip-question");
      else if (ae.id) d = "#" + ae.id;
      else d = ae.tagName.toLowerCase();
      return { d, isSend: ae.id === "chat-composer-send" };
    });
    order.push(info.d);
    if (info.isSend) break;
    await page.keyboard.press("Tab");
  }
  return order;
}

// Capture the canonical question delivered to the submission path when a task
// button is clicked. A capture-phase submit listener records chatInput.value
// and stops propagation so the real transition never runs (offline-safe).
async function captureSubmission(page, question) {
  await page.evaluate(() => {
    const form = document.getElementById("chat-composer-form");
    window.__captured = "__none__";
    form.addEventListener(
      "submit",
      function (e) {
        window.__captured = document.getElementById("chat-composer-input").value;
        e.stopImmediatePropagation();
        e.preventDefault();
      },
      true,
    );
  });
  await page.evaluate((q) => {
    const btn = document.querySelector('[data-chip-question="' + q + '"]');
    btn.click();
  }, question);
  return page.evaluate(() => window.__captured);
}

async function freshEntry(page, base, viewport) {
  await page.setViewportSize({ width: viewport.width, height: viewport.height });
  await page.goto(base, { waitUntil: "domcontentloaded" });
  await page.addStyleTag({ content: "*{animation:none !important;transition:none !important;}" });
}

async function verifyEntryState(page, viewport, base) {
  const ctx = `viewport=${viewport.width}x${viewport.height} state=entry`;
  await freshEntry(page, base, viewport);
  const m = await measure(page);

  assert.equal(m.state, "entry", `${ctx}: state`);
  assert.ok(m.present.entry, `entry panel hidden [${ctx}]`);
  assert.ok(m.present.toggle, `toggle hidden [${ctx}]`);
  assert.strictEqual(m.visPrimary, 3, `primary visible count != 3 [${ctx}]`);
  assert.strictEqual(m.visSecondary, 0, `secondary should be hidden [${ctx}]`);
  assert.equal(m.toggleExpanded, "false", `toggle expanded [${ctx}]`);
  assert.ok(
    m.present.composer && m.present.input && m.present.send,
    `composer missing [${ctx}]`,
  );
  assertRect(".chat-shell", m.chat, ctx);
  assertRect(".chat-shell__header", m.header, ctx);
  assertRect("#chat-entry-panel", m.entry, ctx);
  assertRect(".chat-composer", m.composer, ctx);
  assertRect(".chat-composer__input", m.input, ctx);
  assertRect(".chat-composer__send", m.send, ctx);

  assertNoHorizontalOverflow(m, ctx);
  assertInsideChat(m.entry, m.chat, "entry", ctx);
  assertInsideChat(m.composer, m.chat, "composer", ctx);
  assertInsideChat(m.input, m.chat, "input", ctx);
  assertInsideChat(m.send, m.chat, "send", ctx);
  assert.ok(
    m.composer.top >= m.entry.bottom - TOL,
    `composer overlaps entry region [${ctx}]`,
  );

  assertInsideViewport(m.composer, "composer", ctx, viewport.width, viewport.height);
  assertInsideViewport(m.send, "send", ctx, viewport.width, viewport.height);
  assertInsideViewport(m.input, "input", ctx, viewport.width, viewport.height);

  // Primary labels must not be clipped/truncated.
  assert.ok(m.labelClips.length === 3, `expected 3 primary labels [${ctx}]`);
  for (const lc of m.labelClips) {
    assert.ok(lc.scrollWidth <= lc.clientWidth + 1, `primary label clipped [${ctx}]`);
  }

  // Keyboard order: primary1-3 -> toggle -> composer input -> send.
  const order = await collectFocusOrder(page);
  const seq = order.filter((x) => x && x !== "body");
  const expectedPrimary = PRIMARY.map((q) => "q:" + q);
  assert.deepStrictEqual(seq.slice(0, 3), expectedPrimary, `primary order [${ctx}]`);
  assert.strictEqual(seq[3], "#chat-more-tasks", `toggle position [${ctx}]`);
  const secSet = SECONDARY.map((q) => "q:" + q);
  assert.strictEqual(
    seq.filter((x) => secSet.includes(x)).length,
    0,
    `secondary in collapsed tab order [${ctx}]`,
  );
  assert.ok(seq.includes("#chat-composer-input"), `input missing in order [${ctx}]`);
  assert.ok(seq.includes("#chat-composer-send"), `send missing in order [${ctx}]`);
  assert.ok(
    seq.indexOf("#chat-composer-input") > seq.indexOf("#chat-more-tasks"),
    `input before toggle [${ctx}]`,
  );

  // Independent focus-visible checks.
  await freshEntry(page, base, viewport);
  assert.ok(await focusByKeyboard(page, ".chat-composer__input"), `to input [${ctx}]`);
  await verifyFocusVisible(page, ".chat-composer__input", ctx);

  await freshEntry(page, base, viewport);
  assert.ok(await focusByKeyboard(page, ".chat-composer__send"), `to send [${ctx}]`);
  await verifyFocusVisible(page, ".chat-composer__send", ctx);

  console.log(`[${viewport.width}x${viewport.height} entry] PASS`);
}

async function verifySplitState(page, viewport, base) {
  const ctx = `viewport=${viewport.width}x${viewport.height} state=split`;
  await page.setViewportSize({ width: viewport.width, height: viewport.height });
  await page.goto(base, { waitUntil: "domcontentloaded" });
  await page.addStyleTag({ content: "*{animation:none !important;transition:none !important;}" });
  await applySplitState(page);
  await page.waitForSelector(".demo-canvas", { state: "visible", timeout: 10000 });
  const m = await measure(page);

  assert.equal(m.state, "split", `${ctx}: state`);
  assert.ok(m.present.thread, `thread hidden [${ctx}]`);
  assert.ok(!m.present.entry, `entry panel should be hidden [${ctx}]`);
  assert.ok(
    m.present.composer && m.present.input && m.present.send,
    `composer missing [${ctx}]`,
  );
  assertRect(".chat-thread", m.thread, ctx);
  assertRect(".chat-composer", m.composer, ctx);
  assertRect(".chat-composer__input", m.input, ctx);
  assertRect(".chat-composer__send", m.send, ctx);

  assertNoHorizontalOverflow(m, ctx);
  assertInsideViewport(m.composer, "composer", ctx, viewport.width, viewport.height);
  assertInsideViewport(m.send, "send", ctx, viewport.width, viewport.height);
  assert.ok(
    m.composer.top >= m.thread.bottom - TOL,
    `composer overlaps thread [${ctx}]`,
  );

  assert.ok(await focusByKeyboard(page, ".chat-composer__input"), `to input [${ctx}]`);
  await verifyFocusVisible(page, ".chat-composer__input", ctx);

  console.log(`[${viewport.width}x${viewport.height} split] PASS`);
}

async function verifySecondaryExpand(page, viewport, base) {
  const ctx = `viewport=${viewport.width}x${viewport.height} secondary-expand`;
  await freshEntry(page, base, viewport);

  // Expand via keyboard.
  await page.focus("#chat-more-tasks");
  await page.keyboard.press("Enter");
  let m = await measure(page);
  assert.equal(m.toggleExpanded, "true", `toggle not expanded [${ctx}]`);
  assert.strictEqual(m.visSecondary, 4, `secondary visible count != 4 [${ctx}]`);
  assertInsideViewport(m.composer, "composer", ctx, viewport.width, viewport.height);
  assertInsideViewport(m.send, "send", ctx, viewport.width, viewport.height);

  // Secondary tasks enter the tab order between toggle and composer input.
  const order = await collectFocusOrder(page);
  const seq = order.filter((x) => x && x !== "body");
  const secSet = SECONDARY.map((q) => "q:" + q);
  const seenSec = seq.filter((x) => secSet.includes(x));
  assert.strictEqual(seenSec.length, 4, `secondary not in tab order [${ctx}]`);
  assert.ok(
    seq.indexOf(seenSec[0]) > seq.indexOf("#chat-more-tasks"),
    `secondary before toggle [${ctx}]`,
  );
  assert.ok(
    seq.indexOf("#chat-composer-input") > seq.indexOf(seenSec[seenSec.length - 1]),
    `secondary after input [${ctx}]`,
  );

  // Collapse via keyboard.
  await page.focus("#chat-more-tasks");
  await page.keyboard.press("Enter");
  m = await measure(page);
  assert.equal(m.toggleExpanded, "false", `toggle not collapsed [${ctx}]`);
  assert.strictEqual(m.visSecondary, 0, `secondary still visible [${ctx}]`);
  const order2 = await collectFocusOrder(page);
  const seq2 = order2.filter((x) => x && x !== "body");
  assert.strictEqual(
    seq2.filter((x) => secSet.includes(x)).length,
    0,
    `secondary in tab order after collapse [${ctx}]`,
  );

  console.log(`[${viewport.width}x${viewport.height} secondary-expand] PASS`);
}

async function verifyCanonicalSubmission(page, viewport, base) {
  const ctx = `viewport=${viewport.width}x${viewport.height} submission`;

  await freshEntry(page, base, viewport);
  const pCap = await captureSubmission(page, PRIMARY[0]);
  assert.strictEqual(pCap, PRIMARY[0], `primary submission value [${ctx}]`);

  await freshEntry(page, base, viewport);
  await page.focus("#chat-more-tasks");
  await page.keyboard.press("Enter");
  const sCap = await captureSubmission(page, SECONDARY[3]);
  assert.strictEqual(sCap, SECONDARY[3], `secondary submission value [${ctx}]`);

  console.log(`[${viewport.width}x${viewport.height} submission] PASS`);
}

async function verifyComposerStable(page, viewport, base) {
  const ctx = `viewport=${viewport.width}x${viewport.height} composer-stable`;
  // Stability is measured WITHIN a layout: the composer must not disappear or
  // move when busy/error content changes its sibling region. The entry
  // (floating) and split (docked) shells legitimately occupy different
  // viewport positions, so we compare within each layout, not across them.
  await freshEntry(page, base, viewport);
  const c0 = (await measure(page)).composer;

  // entry busy
  await page.evaluate(() =>
    document.getElementById("chat-shell").setAttribute("data-chat-busy", "true"),
  );
  const c1 = (await measure(page)).composer;
  await page.evaluate(() =>
    document.getElementById("chat-shell").removeAttribute("data-chat-busy"),
  );

  // split normal
  await applySplitState(page);
  await page.waitForSelector(".demo-canvas", { state: "visible", timeout: 10000 });
  const c2 = (await measure(page)).composer;

  // split busy
  await page.evaluate(() =>
    document.getElementById("chat-shell").setAttribute("data-chat-busy", "true"),
  );
  const c3 = (await measure(page)).composer;
  await page.evaluate(() =>
    document.getElementById("chat-shell").removeAttribute("data-chat-busy"),
  );

  // split error bubble (added to the scrollable thread, not the composer)
  await page.evaluate(() => {
    const t = document.getElementById("chat-thread");
    const d = document.createElement("div");
    d.className = "chat-msg chat-msg--ai";
    d.innerHTML =
      '<div class="chat-bubble chat-bubble--ai">잠시 후 다시 시도해 주세요.</div>';
    t.appendChild(d);
  });
  const c4 = (await measure(page)).composer;

  assert.ok(Math.abs(c1.top - c0.top) <= TOL, `entry busy moved composer [${ctx}]`);
  assert.ok(Math.abs(c1.left - c0.left) <= TOL, `entry busy moved composer x [${ctx}]`);
  assert.ok(Math.abs(c1.width - c0.width) <= TOL, `entry busy resized composer [${ctx}]`);
  assert.ok(Math.abs(c1.height - c0.height) <= TOL, `entry busy resized composer [${ctx}]`);

  for (const c of [c3, c4]) {
    assert.ok(Math.abs(c.top - c2.top) <= TOL, `split composer top moved [${ctx}]`);
    assert.ok(Math.abs(c.left - c2.left) <= TOL, `split composer left moved [${ctx}]`);
    assert.ok(Math.abs(c.width - c2.width) <= TOL, `split composer width moved [${ctx}]`);
    assert.ok(Math.abs(c.height - c2.height) <= TOL, `split composer height moved [${ctx}]`);
  }

  console.log(`[${viewport.width}x${viewport.height} composer-stable] PASS`);
}

// Extra contract checks required by #1065 (token layer): token stylesheet is
// actually loaded + parsed, the disabled state collapses correctly, and
// prefers-reduced-motion collapses transition duration.
async function verifyStateExtra(page, viewport, state, base) {
  const ctx = `extra viewport=${viewport.width}x${viewport.height} state=${state}`;

  await page.goto(base, { waitUntil: "domcontentloaded" });
  if (state === "split") await applySplitState(page);
  const tokenVal = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--mvp-radius-sm").trim(),
  );
  assert.equal(tokenVal, "4px", `${ctx}: --mvp-radius-sm not applied (got '${tokenVal}')`);

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
  assert.equal(dis.opacity, "0.4", `${ctx}: disabled send opacity [${ctx}]`);
  assert.equal(dis.cursor, "default", `${ctx}: disabled send cursor [${ctx}]`);

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(base, { waitUntil: "domcontentloaded" });
  if (state === "split") await applySplitState(page);
  const rd = await page.evaluate(() => {
    const el = document.querySelector(".chat-shell");
    return el ? getComputedStyle(el).transitionDuration : null;
  });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  assert.ok(rd !== null, `${ctx}: .chat-shell missing for reduced-motion`);
  assert.ok(
    rd === "0s" || rd === "0.001ms",
    `${ctx}: reduced-motion transition-duration (got ${rd})`,
  );

  console.log(
    `[${viewport.width}x${viewport.height} ${state}] extra=` +
      `token(${tokenVal}) disabled(opacity=${dis.opacity},cursor=${dis.cursor}) ` +
      `reduced-motion(transition=${rd})`,
  );
}

async function main() {
  console.log("Running first-use responsive + entry-panel browser contract (no network):");

  const python = await pickPython();
  console.log("  building static site with", python);
  await run(python, ["scripts/build_cloudflare_pages.py"]);
  assert.ok(
    fs.existsSync(path.join(DIST_DIR, "mvp", "index.html")),
    "dist build missing mvp/index.html",
  );
  assert.ok(fs.existsSync(path.join(DIST_DIR, "index.html")), "dist build missing index.html");

  const { server, port, base } = await startServer();
  console.log(`  serving dist from ${base} (ephemeral port ${port})`);

  let browser;
  let browserInfo;
  let context;
  try {
    browserInfo = await launchBrowser();
    browser = browserInfo.browser;
  } catch (e) {
    await closeServer(server);
    console.error("\n✗ RESPONSIVE BROWSER CONTRACT FAILED: no browser available");
    console.error("  " + e.message);
    throw e;
  }

  console.log(
    `  browser: ${browserInfo.version}\n  browser source: ${browserInfo.source}`,
  );

  const failures = [];
  try {
    context = await browser.newContext({ viewport: VIEWPORTS[0] });
    const allowedOrigin = new URL(base).origin;
    await context.route("**", (route) => {
      const requestUrl = new URL(route.request().url());
      if (requestUrl.origin === allowedOrigin) return route.continue();
      return route.abort();
    });
    const page = await context.newPage();
    page.on("pageerror", (err) => failures.push("pageerror: " + err.message));

    for (const vp of VIEWPORTS) {
      for (const fn of [
        verifyEntryState,
        verifySplitState,
        verifySecondaryExpand,
        verifyCanonicalSubmission,
        verifyComposerStable,
      ]) {
        try {
          await fn(page, vp, base);
        } catch (err) {
          failures.push(`viewport=${vp.width}x${vp.height} ${fn.name}: ${err.message}`);
        }
      }
      for (const state of ["entry", "split"]) {
        try {
          await verifyStateExtra(page, vp, state, base);
        } catch (err) {
          failures.push(`viewport=${vp.width}x${vp.height} extra ${state}: ${err.message}`);
        }
      }
    }
    await context.close();
  } finally {
    try {
      if (context) {
        try {
          await context.close();
        } catch {
          /* fall through */
        }
      }
    } finally {
      try {
        if (browser) await browser.close();
      } finally {
        await closeServer(server);
      }
    }
  }

  assert.equal(server.listening, false, "server still listening after cleanup");

  if (failures.length) {
    console.error("\nRESPONSIVE CONTRACT FAILED:");
    for (const f of failures) console.error("  - " + f);
    process.exit(1);
  }
  console.log("\nAll first-use responsive + entry-panel geometry checks passed.");
}

main().catch((err) => {
  console.error("Responsive browser contract error:");
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
