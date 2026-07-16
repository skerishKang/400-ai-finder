/**
 * #1190 entry chat space reclaim + recommendations utility toggle contract.
 *
 * Asserts:
 * - single .chat-recommendations-toggle mounted in composer utility (not before chips)
 * - ARIA expanded/controls + click hide/show + first-question auto-collapse
 * - no large artificial gap between last chip and composer utility
 * - chat-thread absorbs reclaimed height
 * - composer fully in viewport; horizontal overflow 0
 * - safety counters: console/page/external = 0
 *
 * Local static build only. No live network/provider.
 *
 * Usage:
 *   node tests/browser/verify_entry_chat_space_e2e.mjs
 */

import assert from "node:assert";
import { spawn } from "node:child_process";
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../..");

/**
 * Max allowed *artificial* empty space under chips:
 * - inside chips rail below last chip (beyond CSS padding-bottom)
 * - between chips box bottom and composer top
 * Does NOT include the composer input row (utility lives under the input).
 */
const GAP_BUDGET_PX = 24;
const TOL = 2;

const VIEWPORTS = [
  { name: "desktop-1440x900", width: 1440, height: 900 },
  { name: "desktop-short-1440x760", width: 1440, height: 760, shortHeight: true },
  { name: "tablet-768x1024", width: 768, height: 1024 },
  { name: "mobile-390x844", width: 390, height: 844 },
];

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true, channel: "chrome" });
  } catch {
    return chromium.launch({ headless: true });
  }
}

function buildStatic() {
  const out = fs.mkdtempSync(path.join(os.tmpdir(), "1190-entry-space-"));
  const env = { ...process.env, PYTHONPATH: REPO_ROOT };
  const child = spawn(
    process.platform === "win32" ? "python" : "python3",
    ["scripts/build_cloudflare_pages.py", "--mode", "static", "--out-dir", out],
    { cwd: REPO_ROOT, env, stdio: ["ignore", "pipe", "pipe"] },
  );
  return new Promise((resolve, reject) => {
    let err = "";
    child.stderr.on("data", (c) => {
      err += c.toString();
    });
    child.on("close", (code) => {
      if (code !== 0) reject(new Error(`build failed: ${err}`));
      else resolve(out);
    });
  });
}

function rmTempDir(dir) {
  try {
    fs.rmSync(dir, { recursive: true, force: true });
  } catch {
    /* best-effort */
  }
}

function startServer(dir) {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const urlPath = decodeURIComponent((req.url || "/").split("?")[0]);
      let filePath = path.join(dir, urlPath === "/" ? "index.html" : urlPath);
      if (
        filePath.endsWith(path.sep) ||
        (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory())
      ) {
        filePath = path.join(filePath, "index.html");
      }
      if (!filePath.startsWith(dir) || !fs.existsSync(filePath)) {
        res.writeHead(404);
        res.end("not found");
        return;
      }
      const ext = path.extname(filePath).toLowerCase();
      const types = {
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".png": "image/png",
        ".svg": "image/svg+xml",
      };
      res.writeHead(200, {
        "Content-Type": types[ext] || "application/octet-stream",
      });
      fs.createReadStream(filePath).pipe(res);
    });
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({ server, baseUrl: `http://127.0.0.1:${port}` });
    });
    server.on("error", reject);
  });
}

/**
 * Safety counters for this harness.
 * External request blocking is owned only by installExternalRouteGuard (route.abort).
 * Do not call Request.abort() — Playwright Request is not the abort owner.
 */
function setupSafety(page) {
  const t = { external: 0, console: 0, page: 0, texts: [] };
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      t.console += 1;
      t.texts.push(`console:${msg.text()}`);
    }
  });
  page.on("pageerror", (err) => {
    t.page += 1;
    t.texts.push(`page:${err.message}`);
  });
  return t;
}

/** Sole owner of external request deny + single-count external counter. */
async function installExternalRouteGuard(page, baseUrl, safety) {
  const origin = new URL(baseUrl).origin;
  await page.route("**/*", async (route) => {
    const u = route.request().url();
    if (
      u.startsWith(origin) ||
      u.startsWith("http://127.0.0.1") ||
      u.startsWith("http://localhost") ||
      u.startsWith("data:") ||
      u.startsWith("blob:")
    ) {
      return route.continue();
    }
    safety.external += 1;
    safety.texts.push(`external:${u}`);
    return route.abort();
  });
}

function assertSafety(t, ctx) {
  assert.equal(t.external, 0, `external requests must be 0 [${ctx}] ${t.texts.join(" | ")}`);
  assert.equal(t.console, 0, `console errors must be 0 [${ctx}] ${t.texts.join(" | ")}`);
  assert.equal(t.page, 0, `page errors must be 0 [${ctx}] ${t.texts.join(" | ")}`);
}

async function measureEntryLayout(page) {
  return page.evaluate((gapBudget) => {
    const body = document.body;
    const html = document.documentElement;
    const thread = document.getElementById("chat-thread");
    const chips = document.getElementById("chat-chips");
    const composer = document.getElementById("chat-composer-form");
    const utility = document.querySelector(".chat-composer__utility");
    const mount = document.getElementById("chat-recommendations-toggle-mount");
    const toggles = Array.from(
      document.querySelectorAll(".chat-recommendations-toggle"),
    );
    const shell = document.getElementById("chat-shell");
    const chipEls = chips
      ? Array.from(chips.querySelectorAll(".chat-chip")).filter((el) => {
          const r = el.getBoundingClientRect();
          const cs = getComputedStyle(el);
          return (
            r.height > 0 &&
            r.width > 0 &&
            cs.display !== "none" &&
            cs.visibility !== "hidden"
          );
        })
      : [];
    let lastChipBottom = null;
    if (chipEls.length) {
      lastChipBottom = Math.max(
        ...chipEls.map((el) => el.getBoundingClientRect().bottom),
      );
    }
    const chipsRect = chips ? chips.getBoundingClientRect() : null;
    const utilityRect = utility ? utility.getBoundingClientRect() : null;
    const composerRect = composer ? composer.getBoundingClientRect() : null;
    const threadRect = thread ? thread.getBoundingClientRect() : null;
    const shellRect = shell ? shell.getBoundingClientRect() : null;
    const toggle = toggles[0] || null;
    const chipsCs = chips ? getComputedStyle(chips) : null;
    const threadCs = thread ? getComputedStyle(thread) : null;
    const prev = chips ? chips.previousElementSibling : null;
    const padBottom = chipsCs ? parseFloat(chipsCs.paddingBottom) || 0 : 0;
    // Artificial empty space under last chip *inside* the chips rail (beyond padding).
    const internalEmpty =
      lastChipBottom != null && chipsRect
        ? chipsRect.bottom - lastChipBottom - padBottom
        : null;
    // Space between chips box and composer form (should be ~0).
    const chipsToComposer =
      chipsRect && composerRect ? composerRect.top - chipsRect.bottom : null;
    const gap =
      internalEmpty != null && chipsToComposer != null
        ? Math.max(0, internalEmpty) + Math.max(0, chipsToComposer)
        : null;
    const chipContainment = chipEls.map((el, i) => {
      const r = el.getBoundingClientRect();
      const fully =
        !!chipsRect &&
        r.left >= chipsRect.left - 1 &&
        r.right <= chipsRect.right + 1 &&
        r.top >= chipsRect.top - 1 &&
        r.bottom <= chipsRect.bottom + 1;
      return {
        i,
        fully,
        top: r.top,
        bottom: r.bottom,
        height: r.height,
        visible: r.height > 0 && r.width > 0,
      };
    });
    const maxHeightRaw = chipsCs ? chipsCs.maxHeight : "none";
    return {
      state: body.getAttribute("data-first-use-state"),
      recExpanded: body.getAttribute("data-recommendations-expanded"),
      toggleCount: toggles.length,
      toggleInMount: !!(toggle && mount && mount.contains(toggle)),
      toggleInUtility: !!(toggle && utility && utility.contains(toggle)),
      toggleBeforeChips: !!(
        prev &&
        prev.classList &&
        prev.classList.contains("chat-recommendations-toggle")
      ),
      ariaControls: toggle ? toggle.getAttribute("aria-controls") : null,
      ariaExpanded: toggle ? toggle.getAttribute("aria-expanded") : null,
      chipsDisplay: chipsCs ? chipsCs.display : null,
      chipsFlexGrow: chipsCs ? chipsCs.flexGrow : null,
      chipsFlexShrink: chipsCs ? chipsCs.flexShrink : null,
      chipsFlex: chipsCs ? chipsCs.flex : null,
      chipsMaxHeight: maxHeightRaw,
      chipsOverflowY: chipsCs ? chipsCs.overflowY : null,
      shortHeightFallback:
        !!chipsCs &&
        chipsCs.maxHeight !== "none" &&
        parseFloat(chipsCs.maxHeight) > 0,
      chipsClientHeight: chips ? chips.clientHeight : 0,
      chipsScrollHeight: chips ? chips.scrollHeight : 0,
      threadFlexGrow: threadCs ? threadCs.flexGrow : null,
      threadMinHeight: threadCs ? threadCs.minHeight : null,
      threadOverflowY: threadCs ? threadCs.overflowY : null,
      lastChipBottom,
      chipCount: chipEls.length,
      chipContainment,
      chip6: chipContainment[6] || null,
      internalEmpty,
      chipsToComposer,
      gap,
      gapBudget,
      chipsHeight: chipsRect ? chipsRect.height : 0,
      chipsBottom: chipsRect ? chipsRect.bottom : null,
      threadHeight: threadRect ? threadRect.height : 0,
      composerFullyInViewport: composerRect
        ? composerRect.top >= -1 &&
          composerRect.bottom <= window.innerHeight + 1 &&
          composerRect.left >= -1 &&
          composerRect.right <= window.innerWidth + 1
        : false,
      utilityWrap: utility
        ? getComputedStyle(utility).flexWrap === "wrap"
        : false,
      horizontalOverflow:
        html.scrollWidth > html.clientWidth + 1 ||
        body.scrollWidth > window.innerWidth + 1,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
      shellHeight: shellRect ? shellRect.height : 0,
    };
  }, GAP_BUDGET_PX);
}

async function assertToggleBasics(page, ctx, { expanded }) {
  const m = await measureEntryLayout(page);
  assert.equal(m.toggleCount, 1, `exactly one toggle [${ctx}]`);
  assert.equal(m.toggleInMount, true, `toggle in mount [${ctx}]`);
  assert.equal(m.toggleInUtility, true, `toggle in utility [${ctx}]`);
  assert.equal(m.toggleBeforeChips, false, `toggle must not precede chips [${ctx}]`);
  assert.equal(m.ariaControls, "chat-chips", `aria-controls chat-chips [${ctx}]`);
  assert.equal(
    m.ariaExpanded,
    expanded ? "true" : "false",
    `aria-expanded=${expanded} [${ctx}] got ${m.ariaExpanded}`,
  );
  if (expanded) {
    assert.ok(
      m.recExpanded === null || m.recExpanded === "true",
      `expanded attr [${ctx}] got ${m.recExpanded}`,
    );
  } else {
    assert.equal(m.recExpanded, "false", `collapsed data attr [${ctx}]`);
  }
  return m;
}

async function assertExpandedLayout(page, ctx, vp = {}) {
  const m = await measureEntryLayout(page);
  const isShortHeight = Boolean(vp.shortHeight || m.shortHeightFallback);
  assert.equal(m.state, "entry", `entry state [${ctx}]`);
  assert.ok(
    Number(m.chipsFlexGrow) === 0,
    `chips flex-grow must be 0 (not fill leftover) got ${m.chipsFlexGrow} [${ctx}]`,
  );
  // Normal heights: flex-shrink must stay 0 so wrapped chips never clip
  // (#1114 768×1024). Short heights may bound via max-height + overflow-y.
  assert.ok(
    Number(m.chipsFlexShrink) === 0,
    `chips flex-shrink must be 0 got ${m.chipsFlexShrink} flex=${m.chipsFlex} [${ctx}]`,
  );
  assert.ok(
    Number(m.threadFlexGrow) >= 1,
    `thread flex-grow must absorb leftover got ${m.threadFlexGrow} [${ctx}]`,
  );
  assert.ok(
    m.threadMinHeight === "0px" || m.threadMinHeight === "0",
    `thread min-height 0 got ${m.threadMinHeight} [${ctx}]`,
  );
  assert.ok(
    m.threadOverflowY === "auto" || m.threadOverflowY === "scroll",
    `thread overflow-y auto/scroll got ${m.threadOverflowY} [${ctx}]`,
  );
  assert.ok(m.gap != null, `gap measurable [${ctx}]`);
  assert.ok(
    m.gap <= GAP_BUDGET_PX + TOL,
    `artificial chip empty space ${m.gap}px (internal=${m.internalEmpty}, toComposer=${m.chipsToComposer}) exceeds budget ${GAP_BUDGET_PX}px [${ctx}]`,
  );
  assert.ok(
    m.chipsToComposer == null || m.chipsToComposer <= TOL + 4,
    `chips must sit against composer (toComposer=${m.chipsToComposer}) [${ctx}]`,
  );
  assert.ok(
    m.internalEmpty == null || m.internalEmpty <= GAP_BUDGET_PX + TOL,
    `chips internal empty under last chip ${m.internalEmpty}px [${ctx}]`,
  );

  // Chip containment: all visible chips inside #chat-chips client box.
  assert.ok(m.chipCount >= 8, `expected 8 chips got ${m.chipCount} [${ctx}]`);
  for (const c of m.chipContainment || []) {
    assert.ok(c.visible, `chip[${c.i}] not visible [${ctx}]`);
    assert.ok(
      c.fully,
      `chip[${c.i}] not inside #chat-chips box [${ctx}] top=${c.top} bottom=${c.bottom}`,
    );
  }
  if (m.lastChipBottom != null && m.chipsBottom != null) {
    assert.ok(
      m.lastChipBottom <= m.chipsBottom + TOL,
      `last chip bottom ${m.lastChipBottom} > chips bottom ${m.chipsBottom} [${ctx}]`,
    );
  }
  // Normal heights must not rely on vertical scroll-clip of chips.
  // Short-height fallback (max-height: 760px media) may allow scrollHeight > clientHeight.
  if (!isShortHeight) {
    assert.equal(
      m.shortHeightFallback,
      false,
      `short-height overflow fallback must not apply [${ctx}] maxHeight=${m.chipsMaxHeight}`,
    );
    assert.ok(
      m.chipsScrollHeight <= m.chipsClientHeight + TOL,
      `chips scrollHeight ${m.chipsScrollHeight} > clientHeight ${m.chipsClientHeight} [${ctx}]`,
    );
  }
  if (m.chip6) {
    assert.ok(m.chip6.visible, `chip[6] visible [${ctx}]`);
    assert.ok(m.chip6.fully, `chip[6] fully inside chips box [${ctx}]`);
  }

  assert.ok(m.composerFullyInViewport, `composer fully in viewport [${ctx}]`);
  assert.equal(m.horizontalOverflow, false, `no horizontal overflow [${ctx}]`);
  assert.ok(m.utilityWrap, `utility flex-wrap wrap [${ctx}]`);
  assert.ok(m.threadHeight > 40, `thread has usable height ${m.threadHeight} [${ctx}]`);
  return m;
}

async function runViewport(browser, baseUrl, vp) {
  const ctxName = vp.name;
  const context = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
  });
  const page = await context.newPage();
  const safety = setupSafety(page);
  await installExternalRouteGuard(page, baseUrl, safety);

  const response = await page.goto(`${baseUrl}/`, {
    waitUntil: "domcontentloaded",
  });
  assert.ok(response, `response [${ctxName}]`);
  assert.equal(response.status(), 200, `HTTP [${ctxName}]`);
  await page.waitForSelector("#chat-thread", { timeout: 10000 });
  await page.waitForSelector("#chat-chips", { timeout: 10000 });
  await page.waitForSelector(".chat-recommendations-toggle", { timeout: 10000 });
  await page.waitForSelector(".chat-composer__utility", { timeout: 10000 });

  // Desktop/mobile/tablet entry expanded
  await assertToggleBasics(page, `${ctxName}/expanded`, { expanded: true });
  const expanded = await assertExpandedLayout(
    page,
    `${ctxName}/expanded-layout`,
    vp,
  );

  // Manual collapse
  await page.click(".chat-recommendations-toggle");
  await page.waitForFunction(
    () =>
      document.body.getAttribute("data-recommendations-expanded") === "false",
    null,
    { timeout: 3000 },
  );
  await assertToggleBasics(page, `${ctxName}/manual-collapsed`, { expanded: false });
  const chipsHidden = await page.evaluate(() => {
    const chips = document.getElementById("chat-chips");
    if (!chips) return true;
    const cs = getComputedStyle(chips);
    return cs.display === "none" || chips.offsetParent === null;
  });
  assert.ok(chipsHidden, `chips hidden when collapsed [${ctxName}]`);

  // Manual re-expand
  await page.click(".chat-recommendations-toggle");
  await page.waitForFunction(
    () => document.body.getAttribute("data-recommendations-expanded") !== "false",
    null,
    { timeout: 3000 },
  );
  await assertToggleBasics(page, `${ctxName}/re-expanded`, { expanded: true });

  // First question auto-collapse (type + submit without relying on network MVP answer)
  // Use a short local path: press chip after re-expand, or submit empty-safe question.
  // Prefer typing into composer and submitting — shell collapses recommendations on entry submit.
  await page.fill("#chat-composer-input", "불법 주정차 신고는 어디서 하나요?");
  await page.click("#chat-composer-send");
  await page.waitForFunction(
    () =>
      document.body.getAttribute("data-recommendations-expanded") === "false" ||
      document.body.getAttribute("data-first-use-state") !== "entry",
    null,
    { timeout: 8000 },
  );
  const afterAsk = await measureEntryLayout(page);
  assert.equal(
    afterAsk.ariaExpanded,
    "false",
    `auto-collapse after first question aria-expanded [${ctxName}]`,
  );
  assert.equal(
    afterAsk.recExpanded,
    "false",
    `auto-collapse data-recommendations-expanded [${ctxName}]`,
  );

  // Wait briefly for split/transition if it arrives (static/mvp may differ).
  await page.waitForTimeout(600);
  const post = await measureEntryLayout(page);
  assert.equal(post.toggleCount, 1, `still one toggle after ask [${ctxName}]`);
  assert.equal(post.toggleInUtility, true, `toggle stays in utility [${ctxName}]`);
  assert.equal(post.horizontalOverflow, false, `no overflow after ask [${ctxName}]`);
  assert.ok(post.composerFullyInViewport, `composer in viewport after ask [${ctxName}]`);

  // Mobile guidance surface: utility should hide (no overflow / no focus trap requirement).
  if (vp.width <= 767) {
    const hasTabs = await page.$("#tab-guidance");
    if (hasTabs) {
      await page.click("#tab-guidance");
      await page.waitForTimeout(200);
      const guidance = await page.evaluate(() => {
        const util = document.querySelector(".chat-composer__utility");
        const cs = util ? getComputedStyle(util) : null;
        return {
          utilDisplay: cs ? cs.display : "missing",
          overflow:
            document.documentElement.scrollWidth >
            document.documentElement.clientWidth + 1,
        };
      });
      assert.equal(
        guidance.utilDisplay,
        "none",
        `utility hidden on mobile guidance [${ctxName}]`,
      );
      assert.equal(guidance.overflow, false, `no overflow guidance [${ctxName}]`);
      await page.click("#tab-conversation");
      await page.waitForTimeout(200);
    }
  }

  // Tab order: focusable toggle not preceding chips when expanded after reset.
  // Reset if available.
  const reset = await page.$("#chat-reset");
  if (reset) {
    const visible = await reset.isVisible().catch(() => false);
    if (visible) {
      await reset.click();
      await page.waitForFunction(
        () => document.body.getAttribute("data-first-use-state") === "entry",
        null,
        { timeout: 5000 },
      );
      await page.waitForTimeout(200);
    }
  }

  // Focus sample: composer input then Tab should not enter hidden chips when collapsed.
  await page.click(".chat-recommendations-toggle").catch(() => {});
  // Ensure collapsed for focus isolation check when possible
  const expandedNow = await page.evaluate(
    () =>
      document
        .querySelector(".chat-recommendations-toggle")
        ?.getAttribute("aria-expanded") === "true",
  );
  if (expandedNow) {
    await page.click(".chat-recommendations-toggle");
  }
  await page.focus("#chat-composer-input");
  await page.keyboard.press("Tab");
  const focusAfter = await page.evaluate(() => {
    const ae = document.activeElement;
    if (!ae) return { tag: null, inHiddenChip: false };
    const chips = document.getElementById("chat-chips");
    const inHiddenChip =
      chips &&
      chips.contains(ae) &&
      (getComputedStyle(chips).display === "none" ||
        document.body.getAttribute("data-recommendations-expanded") === "false");
    return {
      tag: ae.tagName,
      id: ae.id,
      className: ae.className,
      inHiddenChip: !!inHiddenChip,
    };
  });
  assert.equal(
    focusAfter.inHiddenChip,
    false,
    `focus must not enter hidden chips [${ctxName}] ${JSON.stringify(focusAfter)}`,
  );

  assertSafety(safety, ctxName);
  await context.close();

  return {
    viewport: ctxName,
    expandedGap: expanded.gap,
    expandedThreadHeight: expanded.threadHeight,
    chipsFlexGrow: expanded.chipsFlexGrow,
    chipsFlexShrink: expanded.chipsFlexShrink,
    chipsClientHeight: expanded.chipsClientHeight,
    chipsScrollHeight: expanded.chipsScrollHeight,
    shortHeightFallback: expanded.shortHeightFallback,
    chip6: expanded.chip6,
  };
}

async function main() {
  let outDir;
  let server;
  let browser;
  const results = [];
  try {
    outDir = await buildStatic();
    const srv = await startServer(outDir);
    server = srv.server;
    browser = await launchBrowser();
    for (const vp of VIEWPORTS) {
      results.push(await runViewport(browser, srv.baseUrl, vp));
    }
    console.log(JSON.stringify({ ok: true, results }, null, 2));
    console.log("#1190 PASS");
  } finally {
    if (browser) await browser.close().catch(() => {});
    if (server) await new Promise((r) => server.close(r));
    if (outDir) rmTempDir(outDir);
  }
}

main().catch((err) => {
  console.error("#1190 FAIL", err);
  process.exit(1);
});
