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
 * This verifier continuously probes composer geometry/a11y/operability from 예
 * through multi-step (fail-closed):
 *   - start: data-choreography-state=running | data-journey-state=navigate
 *   - J-DEPT-01 dept-state coverage: menu → directory → result
 *   - terminal: data-choreography-state=done only (not !ch/idle/cancelled)
 *   - continuous input.disabled / readOnly / send.disabled = violation
 *   - mid-flow focus+typing at directory (text not sent)
 *   - each ask: assistant exact +1 and latest AI has marker
 * Sequences (independent browser contexts):
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
    function readUrlState() {
      const params = new URLSearchParams(window.location.search);
      return {
        urlJourney: params.get("journey") || "",
        urlDeptState: params.get("dept-state") || "",
      };
    }
    function readRouteId() {
      try {
        const api = window.CitizenActionDemoCanvas;
        if (api && typeof api.getCurrentRouteId === "function") {
          return String(api.getCurrentRouteId() || "");
        }
      } catch {
        /* ignore */
      }
      return "";
    }
    function tryOperabilityAtDirectory() {
      if (window.__1174Probe.operability) return;
      const url = readUrlState();
      if (url.urlJourney !== "J-DEPT-01" || url.urlDeptState !== "directory") return;
      const input = document.getElementById("chat-composer-input");
      const send = document.getElementById("chat-composer-send");
      if (!input || !send) return;
      const PROBE = "[[1174-OPERABILITY-PROBE]]";
      let focusOk = false;
      let typeOk = false;
      let clearOk = false;
      let sendOk = false;
      try {
        input.focus();
        focusOk = document.activeElement === input && !input.disabled && !input.readOnly;
        if (focusOk) {
          input.value = PROBE;
          input.dispatchEvent(new Event("input", { bubbles: true }));
          typeOk = input.value === PROBE;
          input.value = "";
          input.dispatchEvent(new Event("input", { bubbles: true }));
          clearOk = input.value === "";
        }
        sendOk = !send.disabled;
      } catch {
        focusOk = false;
      }
      window.__1174Probe.operability = {
        atDeptState: "directory",
        focus: focusOk,
        typing: typeOk,
        cleared: clearOk,
        sendEnabled: sendOk,
        t: performance.now(),
      };
    }
    function recordStateTrace(source) {
      const url = readUrlState();
      const entry = {
        source,
        t: performance.now(),
        firstUse: document.body.getAttribute("data-first-use-state") || "",
        mobileSurface: document.body.getAttribute("data-mobile-surface") || "",
        journey: document.body.getAttribute("data-journey-state") || "",
        choreography: document.body.getAttribute("data-choreography-state") || "",
        routeId: readRouteId(),
        urlJourney: url.urlJourney,
        urlDeptState: url.urlDeptState,
        canvasVisible: (() => {
          const canvas = document.getElementById("demo-canvas");
          if (!canvas) return false;
          const st = getComputedStyle(canvas);
          const r = canvas.getBoundingClientRect();
          return st.display !== "none" && st.visibility !== "hidden" && r.width > 0 && r.height > 0;
        })(),
      };
      window.__1174Probe.stateTrace.push(entry);
      tryOperabilityAtDirectory();
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
      const cr = rect(canvas);
      const vh = window.innerHeight;
      const vw = window.innerWidth;
      const url = readUrlState();
      const journeyState = document.body.getAttribute("data-journey-state") || "";
      const choreography = document.body.getAttribute("data-choreography-state") || "";
      const mobileSurface = document.body.getAttribute("data-mobile-surface") || "";
      const canvasDisplay = canvas ? getComputedStyle(canvas).display : "missing";
      const canvasVisible =
        !!canvas &&
        canvasDisplay !== "none" &&
        getComputedStyle(canvas).visibility !== "hidden" &&
        !!cr &&
        cr.w > 0 &&
        cr.h > 0;
      const inputDisabled = !!(input && input.disabled);
      const inputReadOnly = !!(input && input.readOnly);
      const sendDisabled = !!(send && send.disabled);
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
      if (document.querySelectorAll("#chat-shell").length !== 1) collapse.push("shell-count-not-1");
      if (document.querySelectorAll("#chat-thread").length !== 1) collapse.push("thread-count-not-1");
      if (document.querySelectorAll("#chat-composer-input").length !== 1) {
        collapse.push("input-count-not-1");
      }
      if (document.querySelectorAll("#chat-composer-send").length !== 1) {
        collapse.push("send-count-not-1");
      }
      if (document.querySelectorAll("#demo-canvas").length !== 1) collapse.push("canvas-count-not-1");
      // Guidance multi-step probe starts after housing answer (no ask lock).
      // Composer must stay operable for the entire multi-step window.
      if (inputDisabled) collapse.push("input-disabled");
      if (inputReadOnly) collapse.push("input-readonly");
      if (sendDisabled) collapse.push("send-disabled");

      if (
        window.__1174Probe.operability &&
        window.__1174Probe.operability.atDeptState === "directory"
      ) {
        const op = window.__1174Probe.operability;
        if (!op.focus) collapse.push("operability-focus-fail");
        if (!op.typing) collapse.push("operability-typing-fail");
        if (!op.cleared) collapse.push("operability-clear-fail");
        if (!op.sendEnabled) collapse.push("operability-send-disabled");
      }

      return {
        t: performance.now(),
        firstUse: document.body.getAttribute("data-first-use-state") || "",
        mobileSurface,
        journey: journeyState,
        choreography,
        routeId: readRouteId(),
        urlJourney: url.urlJourney,
        urlDeptState: url.urlDeptState,
        form: fr,
        input: ir,
        send: sr,
        inputDisabled,
        inputReadOnly,
        sendDisabled,
        shellDisplay: shell ? getComputedStyle(shell).display : "missing",
        shellPosition: shell ? getComputedStyle(shell).position : "",
        shellInert: !!(shell && shell.hasAttribute("inert")),
        canvasDisplay,
        canvasVisible,
        canvas: cr,
        collapse,
        docSW: document.documentElement.scrollWidth,
        vw,
        vh,
      };
    }
    window.__1174Probe = {
      samples: [],
      violations: [],
      firstCollapse: null,
      inputDisabledViolations: 0,
      inputReadOnlyViolations: 0,
      sendDisabledViolations: 0,
      operability: null,
      stateTrace: [],
    };

    // Event/history trace: reduced-motion dept-state can last <1 rAF frame.
    // Capture every canonical history write + body/choreography transition.
    if (!window.__1174HistoryPatched) {
      window.__1174HistoryPatched = true;
      const push = history.pushState.bind(history);
      history.pushState = function patchedPushState() {
        const ret = push.apply(history, arguments);
        try {
          recordStateTrace("history.pushState");
        } catch {
          /* probe may not exist yet */
        }
        return ret;
      };
      const replace = history.replaceState.bind(history);
      history.replaceState = function patchedReplaceState() {
        const ret = replace.apply(history, arguments);
        try {
          recordStateTrace("history.replaceState");
        } catch {
          /* ignore */
        }
        return ret;
      };
    }
    window.addEventListener("citizen:choreography-statechange", () => {
      recordStateTrace("citizen:choreography-statechange");
    });
    window.addEventListener("citizen:history-commit-request", () => {
      // Commit request is pre-URL; still useful for start timing.
      recordStateTrace("citizen:history-commit-request");
    });
    const bodyMo = new MutationObserver(() => {
      recordStateTrace("body-attr");
    });
    bodyMo.observe(document.body, {
      attributes: true,
      attributeFilter: [
        "data-choreography-state",
        "data-journey-state",
        "data-mobile-surface",
        "data-first-use-state",
      ],
    });
    window.__1174BodyMo = bodyMo;
    recordStateTrace("probe-start");

    const tick = () => {
      const s = sample();
      window.__1174Probe.samples.push(s);
      if (s.inputDisabled) window.__1174Probe.inputDisabledViolations += 1;
      if (s.inputReadOnly) window.__1174Probe.inputReadOnlyViolations += 1;
      if (s.sendDisabled) window.__1174Probe.sendDisabledViolations += 1;
      if (s.collapse.length && !window.__1174Probe.firstCollapse) {
        window.__1174Probe.firstCollapse = s;
      }
      if (s.collapse.length) window.__1174Probe.violations.push(s);
      window.__1174Raf = requestAnimationFrame(tick);
    };
    window.__1174Raf = requestAnimationFrame(tick);
  });
}

function deriveCoverageFromSamples(samples, stateTrace) {
  const merged = [];
  for (const s of samples || []) {
    merged.push({
      choreography: s.choreography || "",
      journey: s.journey || "",
      urlJourney: s.urlJourney || "",
      urlDeptState: s.urlDeptState || "",
      routeId: s.routeId || "",
      mobileSurface: s.mobileSurface || "",
      canvasVisible: !!s.canvasVisible,
      source: "raf",
    });
  }
  for (const s of stateTrace || []) {
    merged.push({
      choreography: s.choreography || "",
      journey: s.journey || "",
      urlJourney: s.urlJourney || "",
      urlDeptState: s.urlDeptState || "",
      routeId: s.routeId || "",
      mobileSurface: s.mobileSurface || "",
      canvasVisible: !!s.canvasVisible,
      source: s.source || "trace",
    });
  }
  const stateSequence = [];
  let lastKey = "";
  let seenStart = false;
  let seenMenu = false;
  let seenDirectory = false;
  let seenResult = false;
  let seenTerminalDone = false;
  let seenTerminalJourneyResult = false;
  let sawAnyChoreographyAttr = false;
  for (const s of merged) {
    if (s.choreography) sawAnyChoreographyAttr = true;
    if (s.choreography === "running" || s.journey === "navigate") seenStart = true;
    if (s.urlJourney === "J-DEPT-01" && s.urlDeptState === "menu") seenMenu = true;
    if (s.urlJourney === "J-DEPT-01" && s.urlDeptState === "directory") seenDirectory = true;
    if (s.urlJourney === "J-DEPT-01" && s.urlDeptState === "result") seenResult = true;
    if (s.choreography === "done") seenTerminalDone = true;
    if (s.journey === "result") seenTerminalJourneyResult = true;
    const key = [
      s.choreography || "-",
      s.journey || "-",
      s.urlJourney || "-",
      s.urlDeptState || "-",
      s.routeId || "-",
    ].join("|");
    if (key !== lastKey) {
      stateSequence.push({
        choreography: s.choreography || "",
        journey: s.journey || "",
        urlJourney: s.urlJourney || "",
        urlDeptState: s.urlDeptState || "",
        routeId: s.routeId || "",
        mobileSurface: s.mobileSurface || "",
        canvasVisible: !!s.canvasVisible,
        source: s.source || "",
      });
      lastKey = key;
    }
  }
  return {
    stateSequence,
    seenStart,
    seenMenu,
    seenDirectory,
    seenResult,
    seenTerminalDone,
    seenTerminalJourneyResult,
    sawAnyChoreographyAttr,
    explicitStart: seenStart,
    explicitTerminal: seenTerminalDone || seenTerminalJourneyResult,
  };
}

async function stopProbe(page) {
  return page.evaluate(() => {
    if (window.__1174Raf) cancelAnimationFrame(window.__1174Raf);
    if (window.__1174BodyMo) {
      try {
        window.__1174BodyMo.disconnect();
      } catch {
        /* ignore */
      }
      window.__1174BodyMo = null;
    }
    const p = window.__1174Probe || {
      samples: [],
      violations: [],
      firstCollapse: null,
      inputDisabledViolations: 0,
      inputReadOnlyViolations: 0,
      sendDisabledViolations: 0,
      operability: null,
      stateTrace: [],
    };
    const samples = p.samples || [];
    return {
      sampleCount: samples.length,
      violationCount: (p.violations || []).length,
      firstCollapse: p.firstCollapse,
      last: samples[samples.length - 1] || null,
      samples,
      stateTrace: p.stateTrace || [],
      minFormW: samples.length ? Math.min(...samples.map((s) => (s.form ? s.form.w : 0))) : 0,
      minFormH: samples.length ? Math.min(...samples.map((s) => (s.form ? s.form.h : 0))) : 0,
      minInputW: samples.length ? Math.min(...samples.map((s) => (s.input ? s.input.w : 0))) : 0,
      minInputH: samples.length ? Math.min(...samples.map((s) => (s.input ? s.input.h : 0))) : 0,
      inputDisabledViolations: p.inputDisabledViolations || 0,
      inputReadOnlyViolations: p.inputReadOnlyViolations || 0,
      sendDisabledViolations: p.sendDisabledViolations || 0,
      operability: p.operability || null,
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
  assert.strictEqual(
    summary.inputDisabledViolations,
    0,
    `[${label}] input-disabled violations=${summary.inputDisabledViolations}`,
  );
  assert.strictEqual(
    summary.inputReadOnlyViolations,
    0,
    `[${label}] input-readonly violations=${summary.inputReadOnlyViolations}`,
  );
  assert.strictEqual(
    summary.sendDisabledViolations,
    0,
    `[${label}] send-disabled violations=${summary.sendDisabledViolations}`,
  );
  assert.ok(summary.minFormW > 40, `[${label}] min form width ${summary.minFormW}`);
  assert.ok(summary.minFormH > 20, `[${label}] min form height ${summary.minFormH}`);
  assert.ok(summary.minInputW > 40, `[${label}] min input width ${summary.minInputW}`);
  assert.ok(summary.minInputH > 20, `[${label}] min input height ${summary.minInputH}`);
}

function assertMultistepCoverage(coverage, label) {
  assert.ok(coverage.sawAnyChoreographyAttr, `[${label}] choreography attribute never appeared`);
  assert.ok(coverage.seenStart, `[${label}] explicit start not observed (running|navigate)`);
  assert.ok(coverage.seenMenu, `[${label}] expected dept-state=menu not observed`);
  assert.ok(coverage.seenDirectory, `[${label}] expected dept-state=directory not observed`);
  assert.ok(coverage.seenResult, `[${label}] expected dept-state=result not observed`);
  assert.ok(
    coverage.seenTerminalDone,
    `[${label}] explicit terminal data-choreography-state=done not observed`,
  );
  // Fail-closed: unknown/missing/idle/cancelled are not success terminals.
  assert.ok(
    coverage.explicitTerminal,
    `[${label}] explicit terminal missing: ${JSON.stringify(coverage.stateSequence.slice(-3))}`,
  );
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
      const shell = document.getElementById("chat-shell");
      if (!input || input.disabled) return false;
      if (input.offsetParent !== null) return true;
      const pos = shell ? getComputedStyle(shell).position : "";
      return pos === "fixed" || pos === "sticky";
    },
    null,
    { timeout: 15000 },
  );

  // Mutation trace: capture exact assistant +1 landing even if split ack races next task.
  await page.evaluate(
    ({ m, prevUser, prevAi }) => {
      const thread = document.getElementById("chat-thread");
      if (window.__1174AskObs) {
        try {
          window.__1174AskObs.disconnect();
        } catch {
          /* ignore */
        }
      }
      window.__1174AskTrace = {
        marker: m,
        prevUser,
        prevAi,
        events: [],
        landed: null,
      };
      const snap = () => {
        const ais = Array.from(document.querySelectorAll(".chat-msg--ai"));
        const users = document.querySelectorAll(".chat-msg--user").length;
        const last = ais.length ? ais[ais.length - 1] : null;
        const lastText = last ? last.textContent || "" : "";
        const markerCount = ais.filter((el) => (el.textContent || "").includes(m)).length;
        const event = {
          t: performance.now(),
          user: users,
          ai: ais.length,
          lastHasMarker: lastText.includes(m),
          markerCount,
        };
        window.__1174AskTrace.events.push(event);
        if (
          !window.__1174AskTrace.landed &&
          event.user === prevUser + 1 &&
          event.ai === prevAi + 1 &&
          event.lastHasMarker &&
          event.markerCount === 1
        ) {
          // Exact response landing: latest assistant IS the current marker response.
          window.__1174AskTrace.landed = event;
        }
      };
      const obs = new MutationObserver(snap);
      if (thread) obs.observe(thread, { childList: true, subtree: true });
      window.__1174AskObs = obs;
      snap();
    },
    { m: marker, prevUser: before.user, prevAi: before.ai },
  );

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

  // Fail-closed: MutationObserver must have seen exact user+1 / ai+1 / latest marker.
  await page.waitForFunction(
    () => !!(window.__1174AskTrace && window.__1174AskTrace.landed),
    null,
    { timeout: 15000 },
  );

  const landing = await page.evaluate(() => {
    if (window.__1174AskObs) {
      try {
        window.__1174AskObs.disconnect();
      } catch {
        /* ignore */
      }
      window.__1174AskObs = null;
    }
    const ais = Array.from(document.querySelectorAll(".chat-msg--ai"));
    const m = (window.__1174AskTrace && window.__1174AskTrace.marker) || "";
    const markerCount = ais.filter((el) => (el.textContent || "").includes(m)).length;
    return {
      user: document.querySelectorAll(".chat-msg--user").length,
      ai: ais.length,
      markerCount,
      landed: (window.__1174AskTrace && window.__1174AskTrace.landed) || null,
    };
  });

  assert.ok(landing.landed, `[${ctx}] missing exact assistant +1 landing trace`);
  assert.strictEqual(landing.landed.user, before.user + 1, `[${ctx}] landing user +1`);
  assert.strictEqual(landing.landed.ai, before.ai + 1, `[${ctx}] landing assistant exact +1`);
  assert.ok(landing.landed.lastHasMarker, `[${ctx}] landing latest assistant must contain marker`);
  assert.strictEqual(landing.landed.markerCount, 1, `[${ctx}] landing marker count`);
  assert.strictEqual(landing.user, before.user + 1, `[${ctx}] user +1 stable`);
  assert.strictEqual(landing.markerCount, 1, `[${ctx}] marker should appear once, got ${landing.markerCount}`);

  // Allow follow-on split/confirm AI bubbles after the exact response landing.
  if (action === "housing_department") {
    await page.waitForSelector(".chat-msg--confirm-run button", { timeout: 20000 });
  }

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
  assert.strictEqual(after.user, before.user + 1, `[${ctx}] user +1 after settle`);
  assert.strictEqual(markerCount, 1, `[${ctx}] marker still once after settle, got ${markerCount}`);
  return {
    before,
    after,
    landing,
    assistantExactPlusOne: true,
    latestAssistantHasMarker: true,
  };
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

/**
 * Fail-closed multi-step wait aligned with housing quest + J-DEPT-01 contracts.
 *
 * Under reduced-motion, menu/directory may last only a few rAF frames, so
 * intermediate coverage is proven from the continuous probe samples — not from
 * sequential waitForFunction on each dept-state (that race is fail-open for
 * "already past" and fail-flaky for "too short").
 *
 * Start: data-choreography-state=running OR data-journey-state=navigate
 * Steps: journey=J-DEPT-01 + dept-state menu → directory → result (via samples)
 * Terminal: data-choreography-state=done (same as verify_housing_quest_e2e.mjs)
 * Forbidden: text.length heuristics, !ch / idle / cancelled as success.
 */
async function waitMultistepWithCoverage(page, label) {
  // Explicit start — must not use canvas text length.
  // Also accept done if the whole reduced-motion run finished before the poll
  // (coverage is still enforced from rAF samples afterward).
  await page.waitForFunction(
    () => {
      const ch = document.body.getAttribute("data-choreography-state");
      const j = document.body.getAttribute("data-journey-state");
      return ch === "running" || j === "navigate" || ch === "done";
    },
    null,
    { timeout: 25000 },
  );
  console.log(`  [${label}] multi-step progress signal observed (running|navigate|done)`);

  // Terminal: canonical housing verifier contract — choreography done only.
  await page.waitForFunction(
    () => document.body.getAttribute("data-choreography-state") === "done",
    null,
    { timeout: 60000 },
  );
  console.log(`  [${label}] explicit terminal data-choreography-state=done`);

  const snapshot = await page.evaluate(() => {
    const params = new URLSearchParams(window.location.search);
    let routeId = "";
    try {
      routeId =
        (window.CitizenActionDemoCanvas &&
          typeof window.CitizenActionDemoCanvas.getCurrentRouteId === "function" &&
          window.CitizenActionDemoCanvas.getCurrentRouteId()) ||
        "";
    } catch {
      routeId = "";
    }
    return {
      choreography: document.body.getAttribute("data-choreography-state") || "",
      journey: document.body.getAttribute("data-journey-state") || "",
      urlJourney: params.get("journey") || "",
      urlDeptState: params.get("dept-state") || "",
      routeId: String(routeId || ""),
    };
  });
  assert.strictEqual(snapshot.choreography, "done", `[${label}] terminal choreography`);
  // Terminal must be real completion — journey result and/or final dept-state.
  assert.ok(
    snapshot.journey === "result" || snapshot.urlDeptState === "result",
    `[${label}] terminal journey/result missing: ${JSON.stringify(snapshot)}`,
  );
  if (snapshot.urlJourney) {
    assert.strictEqual(snapshot.urlJourney, "J-DEPT-01", `[${label}] terminal journey URL`);
  }
  if (snapshot.urlDeptState) {
    assert.strictEqual(snapshot.urlDeptState, "result", `[${label}] terminal dept-state`);
  }

  return {
    explicitStart: "running|navigate",
    observedSteps: ["menu", "directory", "result"],
    explicitTerminal: "done",
    snapshot,
  };
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

  // Probe starts after housing answer, immediately before 예 (no ask lock window).
  await startProbe(page);
  await clickYes(page, `${label}-yes`);
  await measureNow(page, `${label}-after-yes`);
  const multistep = await waitMultistepWithCoverage(page, label);
  const probe = await stopProbe(page);
  await assertProbeClean(probe, label);

  const coverage = deriveCoverageFromSamples(probe.samples, probe.stateTrace);
  assertMultistepCoverage(coverage, label);
  // In-page mid-flow operability at first directory observation (rAF probe).
  assert.ok(probe.operability, `[${label}] mid-flow operability never ran at directory`);
  assert.ok(probe.operability.focus, `[${label}] operability focus`);
  assert.ok(probe.operability.typing, `[${label}] operability typing`);
  assert.ok(probe.operability.cleared, `[${label}] operability clear`);
  assert.ok(probe.operability.sendEnabled, `[${label}] operability send enabled`);
  console.log(
    `  [${label}] state coverage: start/menu/directory/result/done + mid-flow operability PASS`,
  );
  console.log(
    `  [${label}] stateSequence=${JSON.stringify(
      coverage.stateSequence.map((s) => `${s.choreography}/${s.journey}/${s.urlDeptState || "-"}`),
    )}`,
  );

  await measureNow(page, `${label}-after-multistep`);
  await assertSameNodes(page, `${label}-post-multistep`);

  // Canvas must have been visible during guidance multi-step samples.
  const anyCanvasVisible = (probe.samples || []).some((s) => s.canvasVisible);
  assert.ok(anyCanvasVisible, `[${label}] guidance canvas never visible during multi-step`);

  await toggleSurfaces(page, label);
  // Back to guidance if needed for follow-up from dock (composer works on either)
  await measureNow(page, `${label}-pre-followup`);
  const follow = await sendAsk(
    page,
    sequence.follow.q,
    sequence.follow.marker,
    "none",
    `${label}-followup`,
  );
  assert.ok(follow.assistantExactPlusOne, `[${label}] follow-up assistant exact +1`);
  assert.ok(follow.latestAssistantHasMarker, `[${label}] follow-up latest assistant marker`);
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

  // No stale busy/inert/loading on composer after multi-step.
  const stale = await page.evaluate(() => {
    const form = document.getElementById("chat-composer-form");
    const input = document.getElementById("chat-composer-input");
    const send = document.getElementById("chat-composer-send");
    const shell = document.getElementById("chat-shell");
    function hasInert(el) {
      let n = el;
      while (n) {
        if (n.hasAttribute && n.hasAttribute("inert")) return true;
        n = n.parentElement;
      }
      return false;
    }
    return {
      inputDisabled: !!(input && input.disabled),
      inputReadOnly: !!(input && input.readOnly),
      sendDisabled: !!(send && send.disabled),
      shellBusy: !!(shell && shell.getAttribute("aria-busy") === "true"),
      chatBusy: !!(shell && shell.getAttribute("data-chat-busy") === "true"),
      inert: form ? hasInert(form) : true,
    };
  });
  assert.ok(!stale.inputDisabled, `[${label}] stale input disabled`);
  assert.ok(!stale.inputReadOnly, `[${label}] stale input readOnly`);
  assert.ok(!stale.sendDisabled, `[${label}] stale send disabled`);
  assert.ok(!stale.chatBusy, `[${label}] stale data-chat-busy`);
  assert.ok(!stale.inert, `[${label}] stale inert on composer`);

  await context.close();
  return {
    label,
    minFormW: probe.minFormW,
    minFormH: probe.minFormH,
    minInputW: probe.minInputW,
    minInputH: probe.minInputH,
    probeSamples: probe.sampleCount,
    firstCollapse: probe.firstCollapse,
    inputDisabledViolations: probe.inputDisabledViolations,
    inputReadOnlyViolations: probe.inputReadOnlyViolations,
    sendDisabledViolations: probe.sendDisabledViolations,
    stateSequence: coverage.stateSequence,
    explicitStart: multistep.explicitStart,
    explicitTerminal: multistep.explicitTerminal,
    observedSteps: multistep.observedSteps,
    coverage: {
      seenStart: coverage.seenStart,
      seenMenu: coverage.seenMenu,
      seenDirectory: coverage.seenDirectory,
      seenResult: coverage.seenResult,
      seenTerminalDone: coverage.seenTerminalDone,
      sawAnyChoreographyAttr: coverage.sawAnyChoreographyAttr,
    },
    operability: probe.operability,
    followUpAssistantExactPlusOne: follow.assistantExactPlusOne,
    terminalSnapshot: multistep.snapshot,
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
  console.log("#1174 mobile multistep composer E2E (fail-closed state coverage + continuous probe)");
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
