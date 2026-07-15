/**
 * #1174 — mobile multi-step composer preservation (fail-closed continuous probe).
 *
 * Root cause (pre-fix):
 *   예 → setMobileSurface("guidance") hid #chat-shell via display:none + inert,
 *   collapsing the nested #chat-composer-form to 0×0 for the whole multi-step run.
 *
 * Product fix (already on branch):
 *   guidance keeps the same #chat-shell as a fixed bottom composer dock
 *   (non-inert); header/thread/chips hide via CSS only; #demo-canvas stays primary.
 *
 * This verifier continuously probes composer geometry/a11y from 예 through
 * multi-step, asserts same DOM node identity, and runs independent sequences:
 *   A) KO → 예 → multi-step → EN follow-up
 *   B) EN housing action → 예 → multi-step → KO follow-up
 *   C) unsupported → supported housing → 예 → multi-step → follow-up
 * Viewports: 390×844, 390×640; desktop regression: 1440×1000.
 *
 * Usage:
 *   node tests/browser/verify_mobile_multistep_composer_e2e.mjs
 */

import assert from "node:assert";
import { spawnSync } from "node:child_process";
import {
  mkdtempSync,
  rmSync,
  statSync,
  readFileSync,
  existsSync,
} from "node:fs";
import { join, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import http from "node:http";
import { chromium } from "playwright";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

const MOBILE_VIEWPORTS = [
  { width: 390, height: 844, label: "390x844" },
  { width: 390, height: 640, label: "390x640" },
];
const DESKTOP_VIEWPORT = { width: 1440, height: 1000, label: "1440x1000" };

const HOUSING_KO = "공동주택 관련 문의는 어느 부서에 해야 하나요?";
const HOUSING_EN = "Where should I inquire about apartment housing affairs?";
const UNSUPPORTED_KO = "내일 날씨가 어때?";
const FOLLOW_EN = "Can I ask another question about district services?";
const FOLLOW_KO = "다른 민원 안내도 물어볼 수 있나요?";

const M = {
  housingKo: "[[1174-SEQ-A-HOUSING-KO]]",
  followEn: "[[1174-SEQ-A-FOLLOW-EN]]",
  housingEn: "[[1174-SEQ-B-HOUSING-EN]]",
  followKo: "[[1174-SEQ-B-FOLLOW-KO]]",
  unsupported: "[[1174-SEQ-C-UNSUPPORTED]]",
  housingFromC: "[[1174-SEQ-C-HOUSING]]",
  followFromC: "[[1174-SEQ-C-FOLLOW]]",
  desktopHousing: "[[1174-DESKTOP-HOUSING]]",
};

function buildAndServe() {
  const tmpDir = mkdtempSync(join(tmpdir(), "1174-multistep-composer-"));
  console.log("Building to tmp dir:", tmpDir);
  const res = spawnSync(
    "python",
    ["scripts/build_cloudflare_pages.py", "--mode", "live", "--out-dir", tmpDir],
    {
      stdio: "inherit",
      cwd: REPO_ROOT,
      env: { ...process.env, PYTHONPATH: REPO_ROOT },
    },
  );
  if (res.error || res.status !== 0) {
    throw new Error("Build failed for #1174 multistep composer verifier");
  }
  const server = http.createServer((req, res) => {
    try {
      const urlPath = new URL(req.url, "http://127.0.0.1").pathname;
      let filePath = join(tmpDir, urlPath === "/" ? "index.html" : urlPath);
      let stat;
      try {
        stat = statSync(filePath);
      } catch {
        try {
          stat = statSync(filePath + ".html");
          filePath = filePath + ".html";
        } catch {
          try {
            stat = statSync(join(filePath, "index.html"));
            filePath = join(filePath, "index.html");
          } catch {
            res.writeHead(404);
            res.end("Not found");
            return;
          }
        }
      }
      if (stat.isDirectory()) filePath = join(filePath, "index.html");
      const content = readFileSync(filePath);
      const ext = extname(filePath);
      const mime =
        ext === ".js"
          ? "application/javascript; charset=utf-8"
          : ext === ".css"
            ? "text/css; charset=utf-8"
            : ext === ".png"
              ? "image/png"
              : ext === ".svg"
                ? "image/svg+xml"
                : ext === ".json"
                  ? "application/json; charset=utf-8"
                  : "text/html; charset=utf-8";
      res.writeHead(200, { "Content-Type": mime });
      res.end(content);
    } catch (e) {
      res.writeHead(500);
      res.end(String(e));
    }
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      resolve({
        origin: `http://127.0.0.1:${server.address().port}`,
        cleanup: () => {
          server.close();
          rmSync(tmpDir, { recursive: true, force: true });
        },
      });
    });
  });
}

async function launchBrowser() {
  try {
    return {
      browser: await chromium.launch({ headless: true, channel: "chrome" }),
      source: "channel=chrome",
    };
  } catch {
    return {
      browser: await chromium.launch({ headless: true }),
      source: "bundled",
    };
  }
}

function createSafety(origin) {
  const state = {
    consoleErrors: [],
    pageErrors: [],
    failedResources: [],
    externalRequests: [],
    externalNavigations: [],
    popups: 0,
    liveApiHits: 0,
  };
  function attach(page) {
    page.on("pageerror", (e) => state.pageErrors.push(String(e.message || e)));
    page.on("console", (m) => {
      if (m.type() === "error") state.consoleErrors.push(m.text());
    });
    page.on("requestfailed", (req) => {
      const u = req.url();
      if (/favicon\.ico$/i.test(u)) return;
      if (req.failure() && /ERR_ABORTED/i.test(req.failure().errorText || "")) return;
      state.failedResources.push(u);
    });
    page.on("request", (req) => {
      const u = req.url();
      if (u.startsWith("data:") || u.startsWith("blob:")) return;
      try {
        const p = new URL(u);
        if (p.origin !== origin) state.externalRequests.push(u);
        if (/firecrawl|openai|anthropic|googleapis|bukgu\.gwangju/i.test(u)) {
          state.liveApiHits += 1;
        }
      } catch {
        /* ignore */
      }
    });
    page.on("framenavigated", (frame) => {
      if (frame !== page.mainFrame()) return;
      try {
        const u = new URL(frame.url());
        if (u.origin !== origin && u.protocol !== "about:") {
          state.externalNavigations.push(frame.url());
        }
      } catch {
        /* ignore */
      }
    });
    page.on("popup", () => {
      state.popups += 1;
    });
  }
  return { state, attach };
}

function assertSafety(state, label) {
  assert.deepStrictEqual(state.consoleErrors, [], `[${label}] console: ${state.consoleErrors.join(" | ")}`);
  assert.deepStrictEqual(state.pageErrors, [], `[${label}] page: ${state.pageErrors.join(" | ")}`);
  assert.deepStrictEqual(state.failedResources, [], `[${label}] failed: ${state.failedResources.join(" | ")}`);
  assert.deepStrictEqual(state.externalRequests, [], `[${label}] external: ${state.externalRequests.join(" | ")}`);
  assert.deepStrictEqual(state.externalNavigations, [], `[${label}] nav: ${state.externalNavigations.join(" | ")}`);
  assert.strictEqual(state.popups, 0, `[${label}] popups`);
  assert.strictEqual(state.liveApiHits, 0, `[${label}] live`);
}

/** Pending ask configuration for the mock route. */
let pendingAsk = { marker: "[[1174-UNSET]]", action: "none" };

async function installRoutes(page, origin) {
  await page.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.startsWith("data:") || url.startsWith("blob:")) return route.continue();
    let parsed;
    try {
      parsed = new URL(url);
    } catch {
      return route.abort();
    }
    if (parsed.origin !== origin) return route.abort();
    return route.continue();
  });

  await page.route("**/api/mvp/ask", async (route) => {
    let question = "";
    try {
      question = JSON.parse(route.request().postData() || "{}").question || "";
    } catch {
      question = "";
    }
    const { marker, action } = pendingAsk;
    const housing = action === "housing_department";
    const payload = {
      ok: true,
      question,
      answer: housing
        ? `${marker} 공동주택 관련 문의는 공동주택과에서 담당합니다. 로컬 픽스처 안내입니다.`
        : `${marker} 안내 범위 밖이거나 일반 후속 답변입니다. 로컬 픽스처입니다.`,
      action,
      confidence: housing ? 1 : 0.2,
      failure_code: "",
      provider: "1174-fixture",
      model: "none",
      freshness_state: housing ? "official_snapshot" : "model_only",
      sources: housing
        ? [{ title: "공동주택과", url: "/mvp/", official: true }]
        : [],
    };
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(payload),
    });
  });
}

async function startProbe(page) {
  await page.evaluate(() => {
    function hasAncestorAttr(el, attr) {
      let n = el;
      while (n) {
        if (attr === "inert" && n.hasAttribute && n.hasAttribute("inert")) return true;
        if (attr === "aria-hidden") {
          const v = n.getAttribute && n.getAttribute("aria-hidden");
          if (v === "true") return true;
        }
        n = n.parentElement;
      }
      return false;
    }
    function sample() {
      const form = document.getElementById("chat-composer-form");
      const input = document.getElementById("chat-composer-input");
      const send = document.getElementById("chat-composer-send");
      const shell = document.getElementById("chat-shell");
      const canvas = document.getElementById("demo-canvas");
      const rect = (el) => {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { w: r.width, h: r.height, t: r.top, b: r.bottom, l: r.left, rgt: r.right };
      };
      const fr = rect(form);
      const ir = rect(input);
      const sr = rect(send);
      const vh = window.innerHeight;
      const vw = window.innerWidth;
      const collapse = [];
      if (!form || !form.isConnected) collapse.push("form-disconnected");
      if (!input || !input.isConnected) collapse.push("input-disconnected");
      if (!send || !send.isConnected) collapse.push("send-disconnected");
      if (fr && (fr.w <= 1 || fr.h <= 1)) collapse.push("form-zero");
      if (ir && (ir.w <= 1 || ir.h <= 1)) collapse.push("input-zero");
      if (sr && (sr.w <= 1 || sr.h <= 1)) collapse.push("send-zero");
      if (form && getComputedStyle(form).display === "none") collapse.push("form-display-none");
      if (form && getComputedStyle(form).visibility === "hidden") collapse.push("form-visibility-hidden");
      if (input) {
        const pos = shell ? getComputedStyle(shell).position : "";
        if (input.offsetParent === null && pos !== "fixed" && pos !== "sticky") {
          collapse.push("input-offsetParent-null");
        }
      }
      if (form && hasAncestorAttr(form, "inert")) collapse.push("inert-ancestor");
      if (form && hasAncestorAttr(form, "aria-hidden")) collapse.push("aria-hidden-ancestor");
      if (fr && (fr.b < -1 || fr.t > vh + 1 || fr.rgt < -1 || fr.l > vw + 1)) {
        collapse.push("form-outside-viewport");
      }
      if (document.querySelectorAll("#chat-composer-form").length !== 1) {
        collapse.push("composer-count-not-1");
      }
      return {
        t: performance.now(),
        firstUse: document.body.getAttribute("data-first-use-state") || "",
        mobileSurface: document.body.getAttribute("data-mobile-surface") || "",
        journey: document.body.getAttribute("data-journey-state") || "",
        choreography: document.body.getAttribute("data-choreography-state") || "",
        form: fr,
        input: ir,
        send: sr,
        inputDisabled: !!(input && input.disabled),
        shellDisplay: shell ? getComputedStyle(shell).display : "missing",
        shellPosition: shell ? getComputedStyle(shell).position : "",
        shellInert: !!(shell && shell.hasAttribute("inert")),
        canvasDisplay: canvas ? getComputedStyle(canvas).display : "missing",
        canvas: rect(canvas),
        collapse,
        docSW: document.documentElement.scrollWidth,
        vw,
        vh,
      };
    }
    window.__1174Probe = { samples: [], violations: [], firstCollapse: null };
    const tick = () => {
      const s = sample();
      window.__1174Probe.samples.push(s);
      if (s.collapse.length && !window.__1174Probe.firstCollapse) {
        window.__1174Probe.firstCollapse = s;
      }
      if (s.collapse.length) window.__1174Probe.violations.push(s);
      window.__1174Raf = requestAnimationFrame(tick);
    };
    window.__1174Raf = requestAnimationFrame(tick);
  });
}

async function stopProbe(page) {
  return page.evaluate(() => {
    if (window.__1174Raf) cancelAnimationFrame(window.__1174Raf);
    const p = window.__1174Probe || { samples: [], violations: [], firstCollapse: null };
    return {
      sampleCount: p.samples.length,
      violationCount: p.violations.length,
      firstCollapse: p.firstCollapse,
      last: p.samples[p.samples.length - 1] || null,
      minFormW: Math.min(...p.samples.map((s) => (s.form ? s.form.w : 0))),
      minFormH: Math.min(...p.samples.map((s) => (s.form ? s.form.h : 0))),
      minInputW: Math.min(...p.samples.map((s) => (s.input ? s.input.w : 0))),
      minInputH: Math.min(...p.samples.map((s) => (s.input ? s.input.h : 0))),
    };
  });
}

async function assertProbeClean(summary, label) {
  assert.ok(summary.sampleCount > 5, `[${label}] probe collected too few samples: ${summary.sampleCount}`);
  assert.strictEqual(
    summary.violationCount,
    0,
    `[${label}] continuous probe violations=${summary.violationCount} first=${JSON.stringify(summary.firstCollapse)}`,
  );
  assert.ok(summary.minFormW > 40, `[${label}] min form width ${summary.minFormW}`);
  assert.ok(summary.minFormH > 20, `[${label}] min form height ${summary.minFormH}`);
  assert.ok(summary.minInputW > 40, `[${label}] min input width ${summary.minInputW}`);
  assert.ok(summary.minInputH > 20, `[${label}] min input height ${summary.minInputH}`);
}

async function pinNodes(page) {
  await page.evaluate(() => {
    window.__1174Nodes = {
      form: document.getElementById("chat-composer-form"),
      input: document.getElementById("chat-composer-input"),
      send: document.getElementById("chat-composer-send"),
      shell: document.getElementById("chat-shell"),
      thread: document.getElementById("chat-thread"),
      canvas: document.getElementById("demo-canvas"),
    };
  });
}

async function assertSameNodes(page, label) {
  const same = await page.evaluate(() => {
    const n = window.__1174Nodes || {};
    return {
      form: n.form === document.getElementById("chat-composer-form"),
      input: n.input === document.getElementById("chat-composer-input"),
      send: n.send === document.getElementById("chat-composer-send"),
      shell: n.shell === document.getElementById("chat-shell"),
      thread: n.thread === document.getElementById("chat-thread"),
      canvas: n.canvas === document.getElementById("demo-canvas"),
      formCount: document.querySelectorAll("#chat-composer-form").length,
      shellCount: document.querySelectorAll("#chat-shell").length,
      threadCount: document.querySelectorAll("#chat-thread").length,
      canvasCount: document.querySelectorAll("#demo-canvas").length,
    };
  });
  assert.ok(same.form, `[${label}] form node identity changed`);
  assert.ok(same.input, `[${label}] input node identity changed`);
  assert.ok(same.send, `[${label}] send node identity changed`);
  assert.ok(same.shell, `[${label}] chat-shell identity changed`);
  assert.ok(same.thread, `[${label}] chat-thread identity changed`);
  assert.ok(same.canvas, `[${label}] demo-canvas identity changed`);
  assert.strictEqual(same.formCount, 1, `[${label}] form count`);
  assert.strictEqual(same.shellCount, 1, `[${label}] shell count`);
  assert.strictEqual(same.threadCount, 1, `[${label}] thread count`);
  assert.strictEqual(same.canvasCount, 1, `[${label}] canvas count`);
  return same;
}

async function measureNow(page, label) {
  const m = await page.evaluate(() => {
    const form = document.getElementById("chat-composer-form");
    const input = document.getElementById("chat-composer-input");
    const send = document.getElementById("chat-composer-send");
    const shell = document.getElementById("chat-shell");
    const canvas = document.getElementById("demo-canvas");
    const r = (el) => {
      if (!el) return null;
      const b = el.getBoundingClientRect();
      return { w: b.width, h: b.height, t: b.top, btm: b.bottom, l: b.left, r: b.right };
    };
    const fr = r(form);
    const ir = r(input);
    const sr = r(send);
    const vh = window.innerHeight;
    const vw = window.innerWidth;
    const inVp = (x) =>
      !!(x && x.w > 0 && x.h > 0 && x.t >= -2 && x.btm <= vh + 2 && x.l >= -2 && x.r <= vw + 2);
    function hasInert(el) {
      let n = el;
      while (n) {
        if (n.hasAttribute && n.hasAttribute("inert")) return true;
        n = n.parentElement;
      }
      return false;
    }
    function hasAriaHidden(el) {
      let n = el;
      while (n) {
        if (n.getAttribute && n.getAttribute("aria-hidden") === "true") return true;
        n = n.parentElement;
      }
      return false;
    }
    return {
      firstUse: document.body.getAttribute("data-first-use-state") || "",
      mobileSurface: document.body.getAttribute("data-mobile-surface") || "",
      journey: document.body.getAttribute("data-journey-state") || "",
      choreography: document.body.getAttribute("data-choreography-state") || "",
      form: fr,
      input: ir,
      send: sr,
      formInVp: inVp(fr),
      inputInVp: inVp(ir),
      sendInVp: inVp(sr),
      inputDisabled: !!(input && input.disabled),
      inputReadOnly: !!(input && input.readOnly),
      inertAncestor: form ? hasInert(form) : true,
      ariaHiddenAncestor: form ? hasAriaHidden(form) : true,
      shellDisplay: shell ? getComputedStyle(shell).display : "missing",
      shellPosition: shell ? getComputedStyle(shell).position : "",
      canvasDisplay: canvas ? getComputedStyle(canvas).display : "missing",
      canvas: r(canvas),
      docSW: document.documentElement.scrollWidth,
      vw,
      vh,
      user: document.querySelectorAll(".chat-msg--user").length,
      ai: document.querySelectorAll(".chat-msg--ai").length,
    };
  });
  assert.ok(m.form && m.form.w > 40 && m.form.h > 20, `[${label}] form box ${JSON.stringify(m.form)}`);
  assert.ok(m.input && m.input.w > 40 && m.input.h > 20, `[${label}] input box`);
  assert.ok(m.send && m.send.w > 20 && m.send.h > 20, `[${label}] send box`);
  assert.ok(m.formInVp, `[${label}] form not in viewport ${JSON.stringify(m.form)} vh=${m.vh}`);
  assert.ok(m.inputInVp, `[${label}] input not in viewport`);
  assert.ok(m.sendInVp, `[${label}] send not in viewport`);
  assert.ok(!m.inertAncestor, `[${label}] inert ancestor on composer`);
  assert.ok(!m.ariaHiddenAncestor, `[${label}] aria-hidden ancestor on composer`);
  assert.ok(!m.inputReadOnly, `[${label}] input readOnly`);
  assert.ok(m.docSW <= m.vw + 2, `[${label}] horizontal overflow sw=${m.docSW} vw=${m.vw}`);
  console.log(
    `  [${label}] surface=${m.mobileSurface} journey=${m.journey} choreo=${m.choreography} ` +
      `form=${Math.round(m.form.w)}x${Math.round(m.form.h)} ` +
      `shell=${m.shellDisplay}/${m.shellPosition} canvas=${m.canvasDisplay}`,
  );
  return m;
}

async function sendAsk(page, question, marker, action, ctx) {
  pendingAsk = { marker, action };
  const before = await page.evaluate(() => ({
    user: document.querySelectorAll(".chat-msg--user").length,
    ai: document.querySelectorAll(".chat-msg--ai").length,
  }));
  await page.waitForFunction(
    () => {
      const input = document.getElementById("chat-composer-input");
      return input && !input.disabled && input.offsetParent !== null ||
        (input && !input.disabled && getComputedStyle(document.getElementById("chat-shell") || document.body).position === "fixed");
    },
    null,
    { timeout: 15000 },
  );
  // Prefer visible input; force fill if fixed dock
  const input = page.locator("#chat-composer-input");
  await input.fill(question);
  const respP = page.waitForResponse(
    (r) => r.url().includes("/api/mvp/ask") && r.request().method() === "POST",
    { timeout: 15000 },
  );
  await page.locator("#chat-composer-send").click({ force: true });
  const resp = await respP;
  assert.strictEqual(resp.status(), 200, `[${ctx}] ask status`);
  const body = await resp.json();
  assert.strictEqual(body.ok, true, `[${ctx}] ok`);
  assert.ok(String(body.answer || "").includes(marker), `[${ctx}] body marker`);
  if (action === "none") {
    assert.ok(
      !body.action || body.action === "none",
      `[${ctx}] expected action none got ${body.action}`,
    );
  } else {
    assert.strictEqual(body.action, action, `[${ctx}] action`);
  }

  await page.waitForFunction(
    ({ prevUser, marker }) => {
      const user = document.querySelectorAll(".chat-msg--user").length;
      if (user !== prevUser + 1) return false;
      return Array.from(document.querySelectorAll(".chat-msg--ai")).some((el) =>
        (el.textContent || "").includes(marker),
      );
    },
    { prevUser: before.user, marker },
    { timeout: 15000 },
  );

  const after = await page.evaluate(() => ({
    user: document.querySelectorAll(".chat-msg--user").length,
    ai: document.querySelectorAll(".chat-msg--ai").length,
  }));
  const markerCount = await page.evaluate(
    (m) =>
      Array.from(document.querySelectorAll(".chat-msg--ai")).filter((el) =>
        (el.textContent || "").includes(m),
      ).length,
    marker,
  );
  assert.strictEqual(after.user, before.user + 1, `[${ctx}] user +1`);
  assert.strictEqual(markerCount, 1, `[${ctx}] marker should appear once, got ${markerCount}`);
  return { before, after };
}

async function clickYes(page, ctx) {
  await page.waitForSelector(".chat-msg--confirm-run button", { timeout: 20000 });
  const yes = page.getByRole("button", { name: /예,?\s*안내해\s*주세요|Yes,?\s*please\s*guide/i });
  assert.ok((await yes.count()) > 0, `[${ctx}] yes button missing`);
  await yes.first().click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "guidance",
    null,
    { timeout: 10000 },
  );
}

async function waitMultistepProgress(page) {
  await page.waitForFunction(
    () => {
      const ch = document.body.getAttribute("data-choreography-state");
      const j = document.body.getAttribute("data-journey-state");
      const canvas = document.getElementById("demo-canvas");
      const text = canvas ? canvas.innerText || "" : "";
      const disp = canvas ? getComputedStyle(canvas).display : "none";
      return (
        disp !== "none" &&
        (ch === "running" ||
          ch === "done" ||
          j === "navigate" ||
          j === "result" ||
          text.length > 30)
      );
    },
    null,
    { timeout: 25000 },
  );
  // Sample a few moments during flow without swallowing failures on measure
  for (const ms of [300, 900, 1800]) {
    await page.waitForTimeout(ms);
  }
  await page.waitForFunction(
    () => {
      const ch = document.body.getAttribute("data-choreography-state");
      return !ch || ch === "done" || ch === "idle" || ch === "cancelled";
    },
    null,
    { timeout: 60000 },
  );
}

async function toggleSurfaces(page, label) {
  const guide = page.locator("#tab-guidance");
  const conv = page.locator("#tab-conversation");
  if ((await guide.count()) === 0 || !(await guide.isVisible())) return;
  await guide.click({ force: true });
  await page.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "guidance",
    null,
    { timeout: 5000 },
  );
  await measureSnapshot(page, `${label}-guidance-tab`);
  await conv.click({ force: true });
  await page.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "conversation",
    null,
    { timeout: 5000 },
  );
  await measureSnapshot(page, `${label}-conversation-tab`);
}

async function measureSnapshot(page, label) {
  return measureNow(page, label);
}

async function runMobileSequence(browser, origin, safety, viewport, sequence) {
  const label = `${sequence.name}@${viewport.label}`;
  console.log(`\n=== ${label} ===`);
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    reducedMotion: "reduce",
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  safety.attach(page);
  await installRoutes(page, origin);

  await page.goto(`${origin}/mvp/?lang=ko`, {
    waitUntil: "domcontentloaded",
    timeout: 20000,
  });
  await page.waitForSelector("#chat-composer-input", { timeout: 10000 });
  await pinNodes(page);
  await measureNow(page, `${label}-entry`);

  // Sequence steps
  for (const step of sequence.preSteps || []) {
    await sendAsk(page, step.q, step.marker, step.action, `${label}-${step.name}`);
    await measureNow(page, `${label}-after-${step.name}`);
  }

  await sendAsk(
    page,
    sequence.housing.q,
    sequence.housing.marker,
    "housing_department",
    `${label}-housing`,
  );
  await measureNow(page, `${label}-after-housing-answer`);

  await startProbe(page);
  await clickYes(page, `${label}-yes`);
  await measureNow(page, `${label}-after-yes`);
  await waitMultistepProgress(page);
  const probe = await stopProbe(page);
  await assertProbeClean(probe, label);
  await measureNow(page, `${label}-after-multistep`);
  await assertSameNodes(page, `${label}-post-multistep`);

  // Ensure canvas was guidance during flow (last probe sample)
  assert.ok(
    probe.last &&
      (probe.last.canvasDisplay === "flex" ||
        probe.last.canvasDisplay === "block" ||
        (probe.last.canvas && probe.last.canvas.w > 0)),
    `[${label}] guidance canvas not shown during multi-step`,
  );

  await toggleSurfaces(page, label);
  // Back to guidance if needed for follow-up from dock (composer works on either)
  await measureNow(page, `${label}-pre-followup`);
  await sendAsk(
    page,
    sequence.follow.q,
    sequence.follow.marker,
    "none",
    `${label}-followup`,
  );
  await measureNow(page, `${label}-after-followup`);
  await assertSameNodes(page, `${label}-final`);

  // No duplicate housing marker spam
  const housingMarkers = await page.evaluate(
    (m) =>
      Array.from(document.querySelectorAll(".chat-msg--ai")).filter((el) =>
        (el.textContent || "").includes(m),
      ).length,
    sequence.housing.marker,
  );
  assert.strictEqual(housingMarkers, 1, `[${label}] housing marker count`);

  await context.close();
  return {
    label,
    minFormW: probe.minFormW,
    minFormH: probe.minFormH,
    minInputW: probe.minInputW,
    minInputH: probe.minInputH,
    probeSamples: probe.sampleCount,
    firstCollapse: probe.firstCollapse,
  };
}

async function runDesktopRegression(browser, origin, safety) {
  const label = `desktop@${DESKTOP_VIEWPORT.label}`;
  console.log(`\n=== ${label} ===`);
  const context = await browser.newContext({
    viewport: DESKTOP_VIEWPORT,
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  safety.attach(page);
  await installRoutes(page, origin);
  await page.goto(`${origin}/mvp/?lang=ko`, {
    waitUntil: "domcontentloaded",
    timeout: 20000,
  });
  await page.waitForSelector("#chat-composer-input", { timeout: 10000 });
  await pinNodes(page);

  const before = await measureNow(page, `${label}-entry`);
  assert.ok(
    before.shellPosition !== "fixed" || before.mobileSurface === "",
    "desktop must not use mobile fixed composer dock at entry",
  );

  await sendAsk(
    page,
    HOUSING_KO,
    M.desktopHousing,
    "housing_department",
    `${label}-housing`,
  );
  await page.waitForFunction(
    () => document.body.getAttribute("data-first-use-state") === "split",
    null,
    { timeout: 15000 },
  );
  const mid = await measureNow(page, `${label}-split`);
  assert.strictEqual(mid.mobileSurface, "", `${label}: no data-mobile-surface on desktop`);
  assert.notStrictEqual(mid.shellPosition, "fixed", `${label}: mobile fixed dock must not apply on desktop`);

  // Decline multi-step to avoid long run; composer still checked
  const no = page.getByRole("button", { name: /^(아니요|No)$/i });
  if ((await no.count()) > 0) {
    await no.first().click();
  }
  await measureNow(page, `${label}-after-no`);
  await assertSameNodes(page, label);

  // Internal overflow possible after long answers
  const thread = await page.evaluate(() => {
    const t = document.getElementById("chat-thread");
    return {
      c: t ? t.clientHeight : 0,
      s: t ? t.scrollHeight : 0,
      doc: document.documentElement.scrollHeight,
      vh: window.innerHeight,
    };
  });
  assert.ok(thread.doc <= thread.vh + 80, `${label} document containment`);

  await context.close();
  return { label, shellPosition: mid.shellPosition, doc: thread.doc, vh: thread.vh };
}

async function main() {
  console.log("#1174 mobile multistep composer E2E (continuous probe)");
  const { origin, cleanup } = await buildAndServe();
  const { browser, source } = await launchBrowser();
  console.log(`Browser: ${source}`);
  console.log(`Origin: ${origin}`);

  const sequences = [
    {
      name: "A-ko-en",
      preSteps: [],
      housing: { q: HOUSING_KO, marker: M.housingKo },
      follow: { q: FOLLOW_EN, marker: M.followEn },
    },
    {
      name: "B-en-ko",
      preSteps: [],
      housing: { q: HOUSING_EN, marker: M.housingEn },
      follow: { q: FOLLOW_KO, marker: M.followKo },
    },
    {
      name: "C-unsupported-then-housing",
      preSteps: [
        {
          name: "unsupported",
          q: UNSUPPORTED_KO,
          marker: M.unsupported,
          action: "none",
        },
      ],
      housing: { q: HOUSING_KO, marker: M.housingFromC },
      follow: { q: FOLLOW_EN, marker: M.followFromC },
    },
  ];

  const results = { mobile: [], desktop: null };
  try {
    for (const vp of MOBILE_VIEWPORTS) {
      for (const seq of sequences) {
        const safety = createSafety(origin);
        const r = await runMobileSequence(browser, origin, safety, vp, seq);
        assertSafety(safety.state, r.label);
        results.mobile.push(r);
      }
    }
    const deskSafety = createSafety(origin);
    results.desktop = await runDesktopRegression(browser, origin, deskSafety);
    assertSafety(deskSafety.state, "desktop");
  } finally {
    await browser.close();
    cleanup();
  }

  console.log("\n=== SUMMARY ===");
  console.log(JSON.stringify(results, null, 2));
  console.log("#1174 PASS");
}

main().catch((err) => {
  console.error("#1174 FAIL:", err);
  process.exitCode = 1;
});
