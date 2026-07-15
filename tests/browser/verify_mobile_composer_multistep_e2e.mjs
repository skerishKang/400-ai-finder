/**
 * #1174 — mobile multi-step composer preservation (fail-closed).
 *
 * Root cause under test:
 *   After 예 starts repository-controlled multi-step guidance, mobile used to
 *   set data-mobile-surface=guidance which hid the entire #chat-shell
 *   (display:none + inert), collapsing the composer to 0×0.
 *
 * Contract:
 *   - 390×844 only (primary)
 *   - supported question → assistant → 예 → multi-step guidance
 *   - same #chat-composer-form / input / send remain connected, non-zero,
 *     viewport-visible, enabled, and able to send a follow-up EN question
 *   - no second composer DOM; guidance canvas still shown
 *   - no live network / 북구청 / provider calls
 *
 * Usage:
 *   node tests/browser/verify_mobile_composer_multistep_e2e.mjs
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
const VIEWPORT = { width: 390, height: 844, label: "390x844" };
const HOUSING_Q = "공동주택 관련 문의는 어느 부서에 해야 하나요?";
const FOLLOWUP_EN = "Can I ask another question about district services?";
const MARKER_HOUSING = "[[1174-HOUSING-ANSWER]]";
const MARKER_FOLLOWUP = "[[1174-FOLLOWUP-EN]]";

function buildAndServe() {
  const tmpDir = mkdtempSync(join(tmpdir(), "1174-mobile-composer-"));
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
    throw new Error("Build failed for #1174 mobile composer verifier");
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
      const port = server.address().port;
      resolve({
        origin: `http://127.0.0.1:${port}`,
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
    const isFollow = question === FOLLOWUP_EN;
    const marker = isFollow ? MARKER_FOLLOWUP : MARKER_HOUSING;
    const payload = {
      ok: true,
      question,
      answer: isFollow
        ? `${marker} Yes — you can ask another district service question anytime. ` +
          "This is a local fixture answer with no live network."
        : `${marker} 공동주택 관련 문의는 공동주택과에서 담당합니다. ` +
          "부서 대표전화와 담당 업무를 왼쪽 안내 화면에서 확인할 수 있습니다. " +
          "이 답변은 로컬 정적 픽스처입니다.",
      action: isFollow ? "none" : "housing_department",
      confidence: 1,
      failure_code: "",
      provider: "1174-fixture",
      model: "none",
      freshness_state: "official_snapshot",
      sources: [{ title: "공동주택과", url: "/mvp/", official: true }],
    };
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(payload),
    });
  });
}

async function measureComposer(page, label) {
  const m = await page.evaluate((checkpoint) => {
    const form = document.getElementById("chat-composer-form");
    const input = document.getElementById("chat-composer-input");
    const send = document.getElementById("chat-composer-send");
    const shell = document.getElementById("chat-shell");
    const canvas = document.getElementById("demo-canvas");
    const rect = (el) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return {
        width: r.width,
        height: r.height,
        top: r.top,
        bottom: r.bottom,
        left: r.left,
        right: r.right,
      };
    };
    const fr = rect(form);
    const ir = rect(input);
    const sr = rect(send);
    const vh = window.innerHeight;
    const vw = window.innerWidth;
    const inVp = (r) =>
      !!(
        r &&
        r.width > 0 &&
        r.height > 0 &&
        r.top >= -2 &&
        r.bottom <= vh + 2 &&
        r.left >= -2 &&
        r.right <= vw + 2
      );
    return {
      label: checkpoint,
      firstUse: document.body.getAttribute("data-first-use-state") || "",
      mobileSurface: document.body.getAttribute("data-mobile-surface") || "",
      journey: document.body.getAttribute("data-journey-state") || "",
      choreography: document.body.getAttribute("data-choreography-state") || "",
      formConnected: !!(form && form.isConnected),
      inputConnected: !!(input && input.isConnected),
      sendConnected: !!(send && send.isConnected),
      form: fr,
      input: ir,
      send: sr,
      formInVp: inVp(fr),
      inputInVp: inVp(ir),
      sendInVp: inVp(sr),
      inputDisabled: !!(input && input.disabled),
      inputReadOnly: !!(input && input.readOnly),
      sendDisabled: !!(send && send.disabled),
      shellDisplay: shell ? getComputedStyle(shell).display : "missing",
      shellInert: !!(shell && shell.hasAttribute("inert")),
      shellAriaHidden: shell ? shell.getAttribute("aria-hidden") : null,
      canvasDisplay: canvas ? getComputedStyle(canvas).display : "missing",
      canvasInert: !!(canvas && canvas.hasAttribute("inert")),
      composerCount: document.querySelectorAll("#chat-composer-form").length,
      inputCount: document.querySelectorAll("#chat-composer-input").length,
    };
  }, label);

  assert.strictEqual(m.composerCount, 1, `[${label}] must keep single composer form`);
  assert.strictEqual(m.inputCount, 1, `[${label}] must keep single composer input`);
  assert.ok(m.formConnected, `[${label}] form not connected`);
  assert.ok(m.inputConnected, `[${label}] input not connected`);
  assert.ok(m.sendConnected, `[${label}] send not connected`);
  assert.ok(m.form && m.form.width > 40 && m.form.height > 20, `[${label}] form box: ${JSON.stringify(m.form)}`);
  assert.ok(m.input && m.input.width > 40 && m.input.height > 20, `[${label}] input box: ${JSON.stringify(m.input)}`);
  assert.ok(m.send && m.send.width > 20 && m.send.height > 20, `[${label}] send box: ${JSON.stringify(m.send)}`);
  assert.ok(m.formInVp, `[${label}] form not in viewport: ${JSON.stringify(m.form)}`);
  assert.ok(m.inputInVp, `[${label}] input not in viewport`);
  assert.ok(m.sendInVp, `[${label}] send not in viewport`);
  assert.ok(!m.inputDisabled, `[${label}] input disabled`);
  assert.ok(!m.inputReadOnly, `[${label}] input readOnly`);
  assert.ok(!m.sendDisabled, `[${label}] send disabled`);
  assert.ok(!m.shellInert, `[${label}] chat-shell must not be inert (composer dock)`);
  assert.notStrictEqual(
    m.shellDisplay,
    "none",
    `[${label}] chat-shell display:none collapses composer`,
  );
  console.log(
    `  [${label}] surface=${m.mobileSurface} journey=${m.journey} choreo=${m.choreography} ` +
      `form=${Math.round(m.form.width)}x${Math.round(m.form.height)} ` +
      `input=${Math.round(m.input.width)}x${Math.round(m.input.height)} ` +
      `shellDisplay=${m.shellDisplay} canvasDisplay=${m.canvasDisplay}`,
  );
  return m;
}

async function focusInput(page, ctx) {
  const input = page.locator("#chat-composer-input");
  await input.click({ force: true });
  const focused = await page.evaluate(
    () => document.activeElement && document.activeElement.id === "chat-composer-input",
  );
  assert.ok(focused, `[${ctx}] could not focus #chat-composer-input`);
}

async function main() {
  console.log("#1174 mobile multi-step composer preservation E2E");
  console.log(`viewport ${VIEWPORT.width}x${VIEWPORT.height}`);
  console.log(`question: ${HOUSING_Q}`);
  console.log(`follow-up: ${FOLLOWUP_EN}`);

  const { origin, cleanup } = await buildAndServe();
  const { browser, source } = await launchBrowser();
  console.log(`Browser: ${source}`);
  console.log(`Origin: ${origin}`);
  const safety = createSafety(origin);

  try {
    const context = await browser.newContext({
      viewport: VIEWPORT,
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
    await measureComposer(page, "entry");

    // 1) Supported housing question
    await page.fill("#chat-composer-input", HOUSING_Q);
    const ask1 = page.waitForResponse(
      (r) => r.url().includes("/api/mvp/ask") && r.request().method() === "POST",
      { timeout: 15000 },
    );
    await page.click("#chat-composer-send");
    const res1 = await ask1;
    assert.strictEqual(res1.status(), 200, "housing ask status");
    const body1 = await res1.json();
    assert.ok(body1.ok && String(body1.answer || "").includes(MARKER_HOUSING));

    await page.waitForFunction(
      (marker) =>
        Array.from(document.querySelectorAll(".chat-msg--ai")).some((el) =>
          (el.textContent || "").includes(marker),
        ),
      MARKER_HOUSING,
      { timeout: 15000 },
    );
    await measureComposer(page, "after-answer");

    // 2) Confirm bubble → 예
    await page.waitForSelector(".chat-msg--confirm-run button", { timeout: 15000 });
    const yes = page.getByRole("button", { name: /예,?\s*안내해\s*주세요/i });
    assert.ok((await yes.count()) > 0, "yes button missing");
    await measureComposer(page, "before-yes");
    await yes.first().click();

    // 3) Guidance surface + multi-step running
    await page.waitForFunction(
      () => document.body.getAttribute("data-mobile-surface") === "guidance",
      null,
      { timeout: 10000 },
    );
    await measureComposer(page, "after-yes-guidance");

    // Wait for choreography progress (best-effort: state transitions or canvas content)
    await page
      .waitForFunction(
        () => {
          const ch = document.body.getAttribute("data-choreography-state");
          const j = document.body.getAttribute("data-journey-state");
          const canvas = document.getElementById("demo-canvas");
          const text = canvas ? canvas.innerText || "" : "";
          return (
            ch === "running" ||
            ch === "done" ||
            j === "navigate" ||
            j === "result" ||
            text.length > 40
          );
        },
        null,
        { timeout: 20000 },
      )
      .catch(() => {
        /* continue measuring even if choreography is short */
      });

    // Sample mid-flow points
    for (const delay of [400, 1200, 2500]) {
      await page.waitForTimeout(delay);
      const snap = await measureComposer(page, `mid-flow-${delay}ms`);
      assert.ok(
        snap.canvasDisplay !== "none",
        `guidance canvas should show mid-flow (${snap.canvasDisplay})`,
      );
    }

    // Prefer wait for done, but do not hang forever
    await page
      .waitForFunction(
        () => {
          const ch = document.body.getAttribute("data-choreography-state");
          return ch === "done" || ch === "idle" || ch === null || ch === "";
        },
        null,
        { timeout: 45000 },
      )
      .catch(() => {});

    const afterGuide = await measureComposer(page, "after-multistep");
    assert.strictEqual(
      afterGuide.mobileSurface,
      "guidance",
      "expected to remain on guidance after multi-step unless user switches",
    );

    // 4) Focus + English follow-up without reload
    await focusInput(page, "follow-up-focus");
    await page.fill("#chat-composer-input", FOLLOWUP_EN);
    const ask2 = page.waitForResponse(
      (r) => r.url().includes("/api/mvp/ask") && r.request().method() === "POST",
      { timeout: 15000 },
    );
    await page.click("#chat-composer-send");
    const res2 = await ask2;
    assert.strictEqual(res2.status(), 200, "follow-up ask status");
    const body2 = await res2.json();
    assert.ok(body2.ok && String(body2.answer || "").includes(MARKER_FOLLOWUP));

    // Switch to conversation if needed to see the answer bubble, but composer
    // must already have been usable for the send above.
    await measureComposer(page, "after-followup-send");

    // Ensure marker eventually lands in DOM (may be on conversation surface)
    const tabConv = page.locator("#tab-conversation");
    if ((await tabConv.count()) > 0 && (await tabConv.isVisible())) {
      await tabConv.click({ force: true });
      await page.waitForFunction(
        () => document.body.getAttribute("data-mobile-surface") === "conversation",
        null,
        { timeout: 5000 },
      );
    }
    await page.waitForFunction(
      (marker) =>
        Array.from(document.querySelectorAll(".chat-msg--ai")).some((el) =>
          (el.textContent || "").includes(marker),
        ),
      MARKER_FOLLOWUP,
      { timeout: 15000 },
    );
    await measureComposer(page, "after-followup-visible");

    assert.deepStrictEqual(safety.state.consoleErrors, [], safety.state.consoleErrors.join(" | "));
    assert.deepStrictEqual(safety.state.pageErrors, [], safety.state.pageErrors.join(" | "));
    assert.deepStrictEqual(safety.state.failedResources, [], safety.state.failedResources.join(" | "));
    assert.deepStrictEqual(safety.state.externalRequests, [], safety.state.externalRequests.join(" | "));
    assert.deepStrictEqual(safety.state.externalNavigations, [], safety.state.externalNavigations.join(" | "));
    assert.strictEqual(safety.state.popups, 0);
    assert.strictEqual(safety.state.liveApiHits, 0);

    await context.close();
    console.log("#1174 PASS");
  } finally {
    await browser.close();
    cleanup();
  }
}

main().catch((err) => {
  console.error("#1174 FAIL:", err);
  process.exitCode = 1;
});
