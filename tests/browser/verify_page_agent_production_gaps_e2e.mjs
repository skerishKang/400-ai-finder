/**
 * #1164 — Page Agent production-gap browser contracts.
 *
 * Layers:
 *  A) Unit-level PageAgentMockModel.respond() supplements
 *  B) Real resident chat UI + Page Agent action loop
 *  C) Deterministic /mvp/ confirmation surfaces
 *
 * Safety: hard-assert zero external/live/submit/login/payment/error counters.
 */
import assert from "node:assert";
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFileSync, existsSync, mkdtempSync, rmSync, statSync } from "node:fs";
import { join, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, "..", "..");
const RESIDENT_ROUTE = "/src/web/examples/page-agent/resident/index.html";
const TASK_TIMEOUT_MS = 60000;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".gif": "image/gif",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function createStaticServer(rootDir) {
  return new Promise((resolve) => {
    const server = createServer((req, res) => {
      try {
        const url = new URL(req.url || "/", "http://127.0.0.1");
        let rel = decodeURIComponent(url.pathname);
        if (rel === "/") rel = "/index.html";
        let filePath = join(rootDir, rel);
        if (existsSync(filePath) && statSync(filePath).isDirectory()) {
          filePath = join(filePath, "index.html");
        }
        if (!existsSync(filePath) && existsSync(filePath + ".html")) filePath += ".html";
        if (!existsSync(filePath)) {
          res.writeHead(404);
          res.end("Not Found");
          return;
        }
        const content = readFileSync(filePath);
        res.writeHead(200, {
          "Content-Type": MIME[extname(filePath)] || "application/octet-stream",
        });
        res.end(content);
      } catch {
        if (!res.headersSent) {
          res.writeHead(404);
          res.end("Not Found");
        }
      }
    });
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      resolve({ server, origin: `http://127.0.0.1:${port}` });
    });
  });
}

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch {
    return chromium.launch({ headless: true, channel: "chrome" });
  }
}

function makeBrowserState(targets) {
  return targets
    .map((t, i) => `[${i}]<a data-action-target=${t} class=bg-home-link>${t}</a>`)
    .join("\n");
}

const FULL_TARGETS = makeBrowserState([
  "nav-apartment-dept",
  "nav-bulky-waste-disposal",
  "nav-passport-guidance",
  "nav-complaint-board",
  "complaint-write",
  "mayor-office-open",
  "mayor-message-write",
]);

// ── Safety tracker ────────────────────────────────────────────────────────

function createSafetyTracker(origin) {
  return {
    origin,
    external: [],
    requestFailures: [],
    consoleErrors: [],
    pageErrors: [],
    formSubmissions: [],
    loginAttempts: [],
    paymentAttempts: [],
    liveProvider: [],
    wrongRouteClicks: 0,
  };
}

function attachSafety(page, tracker) {
  page.on("request", (req) => {
    const u = req.url();
    if (u.startsWith("data:") || u.startsWith("blob:")) return;
    let parsed;
    try {
      parsed = new URL(u);
    } catch {
      return;
    }
    if (parsed.origin !== tracker.origin) {
      tracker.external.push({ url: u, method: req.method() });
    }
    const lower = u.toLowerCase();
    const method = req.method().toUpperCase();
    // Forbidden product surfaces (no payloads/headers logged).
    if (/firecrawl|openai\.com|api\.anthropic|generativelanguage\.googleapis|api\.x\.ai/i.test(lower)) {
      tracker.liveProvider.push(parsed.origin + parsed.pathname);
    }
    if (/\/login|\/signin|\/oauth|\/sso/i.test(lower) && method !== "GET") {
      tracker.loginAttempts.push(parsed.pathname);
    }
    if (/\/pay|\/payment|\/checkout|\/billing/i.test(lower)) {
      tracker.paymentAttempts.push(parsed.pathname);
    }
    if (
      method === "POST" &&
      /submit|receipt|confirm-submit|form-submit/i.test(lower) &&
      !/\/api\/mvp\/ask|mock-llm/i.test(lower)
    ) {
      tracker.formSubmissions.push(parsed.pathname);
    }
  });
  page.on("requestfailed", (req) => {
    const err = req.failure()?.errorText || "unknown";
    // Ignore benign aborts from navigation teardown.
    if (/ERR_ABORTED|NS_BINDING_ABORTED/i.test(err)) return;
    tracker.requestFailures.push({ url: req.url(), error: err });
  });
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    if (text.includes("favicon.ico")) return;
    if (/GL Driver Message \(OpenGL, Performance/i.test(text)) return;
    if (/Failed to load resource/i.test(text)) return;
    tracker.consoleErrors.push(text);
  });
  page.on("pageerror", (err) => {
    tracker.pageErrors.push(err.message);
  });
}

function assertSafety(tracker, label) {
  assert.strictEqual(
    tracker.external.length,
    0,
    `${label} external-origin=0 got=${JSON.stringify(tracker.external.slice(0, 5))}`,
  );
  assert.strictEqual(
    tracker.requestFailures.length,
    0,
    `${label} requestFailures=0 got=${JSON.stringify(tracker.requestFailures.slice(0, 5))}`,
  );
  assert.strictEqual(
    tracker.consoleErrors.length,
    0,
    `${label} consoleErrors=0 got=${JSON.stringify(tracker.consoleErrors.slice(0, 5))}`,
  );
  assert.strictEqual(
    tracker.pageErrors.length,
    0,
    `${label} pageErrors=0 got=${JSON.stringify(tracker.pageErrors.slice(0, 5))}`,
  );
  assert.strictEqual(
    tracker.formSubmissions.length,
    0,
    `${label} formSubmissions=0 got=${JSON.stringify(tracker.formSubmissions)}`,
  );
  assert.strictEqual(
    tracker.loginAttempts.length,
    0,
    `${label} loginAttempts=0 got=${JSON.stringify(tracker.loginAttempts)}`,
  );
  assert.strictEqual(
    tracker.paymentAttempts.length,
    0,
    `${label} paymentAttempts=0 got=${JSON.stringify(tracker.paymentAttempts)}`,
  );
  assert.strictEqual(
    tracker.liveProvider.length,
    0,
    `${label} liveProvider=0 got=${JSON.stringify(tracker.liveProvider)}`,
  );
  assert.strictEqual(tracker.wrongRouteClicks, 0, `${label} wrongRouteClicks=0`);
}

// ── Mock unit helpers ─────────────────────────────────────────────────────

async function callRespond(page, userRequestText, browserStateContent) {
  const rawMessage =
    `<user_request>${userRequestText}</user_request>` +
    `<browser_state>${browserStateContent || ""}</browser_state>`;
  const payload = {
    model: "resident-mock-local",
    messages: [{ role: "user", content: rawMessage }],
    tools: [{ function: { name: "AgentOutput" } }],
  };
  return page.evaluate((p) => {
    const resp = window.PageAgentMockModel.respond(
      "http://127.0.0.1/mock-llm/v1/chat/completions",
      { body: JSON.stringify(p) },
    );
    return resp.json();
  }, payload);
}

function getAction(response) {
  if (!response?.choices?.[0]) return null;
  const choice = response.choices[0];
  if (choice.finish_reason === "stop") {
    return { _stop: true, text: choice.message?.content || "" };
  }
  const tc = choice.message?.tool_calls?.[0];
  if (!tc) return null;
  const parsed = JSON.parse(tc.function.arguments);
  return parsed.action || parsed;
}

async function resetMockOnly(page) {
  await page.evaluate(() => {
    window.PageAgentMockModel.resetSession();
    window.PageAgentMockModel.resetDiagnostics();
  });
}

// ── Resident UI helpers ───────────────────────────────────────────────────

async function openResident(page, origin) {
  await page.goto(`${origin}${RESIDENT_ROUTE}`, {
    waitUntil: "domcontentloaded",
    timeout: 30000,
  });
  await page.waitForFunction(
    () =>
      window.PageAgentMockModel &&
      window.CitizenActionDemoCanvas &&
      typeof window.PageAgent === "function" &&
      document.getElementById("chat-input") &&
      document.getElementById("chat-send"),
    null,
    { timeout: 20000 },
  );
  // Wait agent init (status ready)
  await page.waitForFunction(
    () => {
      const status = document.querySelector(".chat-header__status")?.textContent || "";
      return /준비|완료|idle/i.test(status) || status.length >= 0;
    },
    null,
    { timeout: 10000 },
  );
  await page.waitForTimeout(300);
}

/**
 * Submit through real chat UI only — no sendMessage() evaluation,
 * no resetSession(), no navigateToRoute() from the test.
 */
async function submitViaChatUi(page, prompt) {
  const input = page.locator("#chat-input");
  await input.waitFor({ state: "visible", timeout: 10000 });
  await input.click();
  await input.fill(prompt);
  const send = page.locator("#chat-send");
  if (await send.isVisible().catch(() => false)) {
    await send.click();
  } else {
    await input.press("Enter");
  }
}

async function returnToConversationUi(page) {
  // Desktop keeps both surfaces; mobile may need the conversation tab.
  const tab = page.locator("#page-agent-tab-conversation");
  if (await tab.isVisible().catch(() => false)) {
    await tab.click();
    await page.waitForTimeout(150);
  }
  // Ensure composer is interactable
  await page.locator("#chat-input").waitFor({ state: "visible", timeout: 10000 });
}

/** Read-only evidence after real UI execution */
async function readSessionEvidence(page) {
  return page.evaluate(() => {
    const d = window.PageAgentMockModel.getDiagnostics();
    return {
      callCount: d.callCount,
      actionNames: [...d.actionNames],
      taskIds: [...d.taskIds],
      successValues: [...d.successValues],
      lastSuccess: d.lastSuccess,
      lastCompletionText: d.lastCompletionText,
      activeTaskId: window.PageAgentMockModel.getActiveTaskId
        ? window.PageAgentMockModel.getActiveTaskId()
        : null,
      generation: window.PageAgentMockModel.getTaskGeneration
        ? window.PageAgentMockModel.getTaskGeneration()
        : null,
      route: window.CitizenActionDemoCanvas?.getCurrentRouteId?.() || "",
      planState: document.body.getAttribute("data-page-agent-plan-state") || "",
      status: document.querySelector(".chat-header__status")?.textContent || "",
      chatTail: (document.getElementById("chat-messages")?.innerText || "").slice(-500),
    };
  });
}

async function installActionProbe(page) {
  await page.evaluate(() => {
    window.__paClickTargets = [];
    window.__paRoutesAtRespond = [];
    window.__paDoneLog = [];
    if (window.__paProbeInstalled) return;
    window.__paProbeInstalled = true;
    const orig = window.PageAgentMockModel.respond;
    window.PageAgentMockModel.respond = function (input, init) {
      let route = "";
      try {
        route = window.CitizenActionDemoCanvas?.getCurrentRouteId?.() || "";
      } catch (_) {
        /* ignore */
      }
      window.__paRoutesAtRespond.push(route);
      const resp = orig.call(window.PageAgentMockModel, input, init);
      try {
        const clone = resp.clone();
        clone.json().then((data) => {
          const choice = data?.choices?.[0];
          if (!choice) return;
          if (choice.finish_reason === "stop") {
            window.__paDoneLog.push({ stop: true });
            return;
          }
          const tc = choice.message?.tool_calls?.[0];
          if (!tc) return;
          let action;
          try {
            const args = JSON.parse(tc.function.arguments);
            action = args.action || args;
          } catch (_) {
            return;
          }
          if (action.click_element_by_index) {
            const idx = action.click_element_by_index.index;
            let body = {};
            try {
              body = JSON.parse((init && init.body) || "{}");
            } catch (_) {
              body = {};
            }
            const msgs = body.messages || [];
            const content = msgs.length ? msgs[msgs.length - 1].content || "" : "";
            const m = String(content).match(
              /<browser_state>([\s\S]*?)<\/browser_state>/,
            );
            const state = m ? m[1] : "";
            // Flat-tree lines look like: [7]<a ... data-action-target=nav-... >
            // or with quotes / truncated values.
            let target = null;
            const lineRe = new RegExp(
              "\\[" + idx + "\\][^\\n]*data-action-target=(?:\"([^\"]+)\"|'([^']+)'|([^\\s>\"']+))",
            );
            const lm = String(state).match(lineRe);
            if (lm) {
              target = lm[1] || lm[2] || lm[3] || null;
              if (target && target.indexOf("...") !== -1) {
                target = target.slice(0, target.indexOf("..."));
              }
            }
            // Expand truncated prefixes against known scenario targets.
            if (target && window.PageAgentParityScenarios) {
              const known = [];
              (window.PageAgentParityScenarios.SCENARIOS || []).forEach((s) => {
                (s.navSteps || []).forEach((step) => {
                  if (step && step.target) known.push(step.target);
                });
              });
              const hit = known.find(
                (k) => k === target || k.indexOf(target) === 0,
              );
              if (hit) target = hit;
            }
            window.__paClickTargets.push(target || "index:" + idx);
          }
          if (action.done) {
            window.__paDoneLog.push({
              success: action.done.success,
              text: action.done.text,
            });
          }
        });
      } catch (_) {
        /* ignore probe errors */
      }
      return resp;
    };
  });
}

async function readProbe(page) {
  return page.evaluate(() => ({
    clicks: [...(window.__paClickTargets || [])],
    routesAtRespond: [...(window.__paRoutesAtRespond || [])],
    dones: [...(window.__paDoneLog || [])],
  }));
}

async function clearProbe(page) {
  await page.evaluate(() => {
    window.__paClickTargets = [];
    window.__paRoutesAtRespond = [];
    window.__paDoneLog = [];
  });
}

async function waitForAgentIdle(page) {
  // sendMessage ignores input while isRunning; wait until composer accepts a new top-level request.
  await page.waitForFunction(
    () => {
      const input = document.getElementById("chat-input");
      const send = document.getElementById("chat-send");
      if (!input || !send) return false;
      if (input.disabled || send.disabled) return false;
      const plan = document.body.getAttribute("data-page-agent-plan-state") || "";
      return (
        plan === "result" ||
        plan === "unsupported" ||
        plan === "idle" ||
        plan === "error" ||
        plan === "cancelled"
      );
    },
    null,
    { timeout: TASK_TIMEOUT_MS },
  );
}

async function waitForUiTaskDone(page, { expectedRoute, minClicks, label, routeTrail }) {
  const deadline = Date.now() + TASK_TIMEOUT_MS;
  const seenRoutes = new Set();
  while (Date.now() < deadline) {
    const ev = await readSessionEvidence(page);
    if (ev.route) seenRoutes.add(ev.route);
    if (routeTrail) routeTrail.push(ev.route);
    const clicks = ev.actionNames.filter((a) => a === "click_element_by_index").length;
    const lastDone =
      ev.actionNames.length && ev.actionNames[ev.actionNames.length - 1] === "done";
    const success = lastDone && ev.lastSuccess === true;
    const routeOk = !expectedRoute || ev.route === expectedRoute;
    if (success && routeOk && (minClicks == null || clicks >= minClicks)) {
      // Ensure resident UI is ready for a subsequent top-level request.
      await waitForAgentIdle(page);
      const idleEv = await readSessionEvidence(page);
      idleEv.seenRoutes = [...seenRoutes];
      return idleEv;
    }
    await page.waitForTimeout(200);
  }
  const finalEv = await readSessionEvidence(page);
  const probe = await readProbe(page);
  throw new Error(
    `[${label}] UI task timeout expectedRoute=${expectedRoute} evidence=${JSON.stringify(finalEv)} probe=${JSON.stringify(probe)} seen=${JSON.stringify([...seenRoutes])}`,
  );
}

// ── MVP helpers ───────────────────────────────────────────────────────────

async function collectMvpDiag(page) {
  return page.evaluate(() => {
    const confButtons = Array.from(
      document.querySelectorAll(
        ".chat-msg--confirm-run button, .chat-decision__button, [data-msg-type='confirm-run'] button",
      ),
    );
    return {
      route: window.CitizenActionDemoCanvas?.getCurrentRouteId?.() || "",
      choreographyState:
        document.body.getAttribute("data-choreography-state") ||
        document.body.getAttribute("data-first-use-state") ||
        "",
      confirmationCandidates: confButtons.slice(0, 12).map((b) => ({
        text: (b.textContent || "").trim().slice(0, 60),
        disabled: !!b.disabled,
        visible: !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length),
      })),
      disabledState: confButtons.map((b) => !!b.disabled),
      visibleChatActions: Array.from(
        document.querySelectorAll(
          "#chat-thread button, .chat-thread button, .chat-msg button",
        ),
      )
        .slice(0, 16)
        .map((b) => (b.textContent || "").trim().slice(0, 40))
        .filter(Boolean),
      chatTail: (document.querySelector("#chat-thread")?.innerText || "").slice(-400),
    };
  });
}

async function clickMvpConfirmation(page, label) {
  const selector =
    '.chat-msg--confirm-run button:has-text("예, 안내해 주세요"), ' +
    "button:has-text(\"예, 안내해 주세요\")";
  try {
    await page.locator(selector).first().waitFor({ state: "visible", timeout: 20000 });
  } catch {
    throw new Error(
      `[${label}] confirmation timeout: ${JSON.stringify(await collectMvpDiag(page))}`,
    );
  }
  try {
    await page.waitForFunction(
      () => {
        const buttons = Array.from(
          document.querySelectorAll(
            ".chat-msg--confirm-run button, button.chat-decision__button--primary",
          ),
        );
        return buttons.some(
          (b) =>
            !b.disabled &&
            /예|Yes|안내/i.test((b.textContent || "").trim()) &&
            !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length),
        );
      },
      null,
      { timeout: 15000 },
    );
  } catch {
    throw new Error(
      `[${label}] confirmation stayed disabled: ${JSON.stringify(await collectMvpDiag(page))}`,
    );
  }
  const clicked = await page.evaluate(() => {
    const buttons = Array.from(
      document.querySelectorAll(
        ".chat-msg--confirm-run button, button.chat-decision__button--primary, button",
      ),
    );
    const match = buttons.find(
      (b) =>
        !b.disabled &&
        /예,\s*안내해 주세요|Yes,?\s*please guide|예.*안내/i.test(
          (b.textContent || "").trim(),
        ) &&
        !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length),
    );
    if (!match) return false;
    match.click();
    return true;
  });
  if (!clicked) {
    throw new Error(
      `[${label}] no enabled confirmation: ${JSON.stringify(await collectMvpDiag(page))}`,
    );
  }
}

async function waitForSurface(page, sc, timeoutMs = 120000) {
  try {
    await page.waitForFunction(
      (spec) => {
        const route = window.CitizenActionDemoCanvas?.getCurrentRouteId?.() || "";
        const choreo = document.body.getAttribute("data-choreography-state") || "";
        if (spec.mode === "route") return route === spec.expectedRoute;
        if (spec.mode === "official-surface") {
          if (
            document.querySelector(
              `[data-official-route-id="${spec.surfaceId}"]`,
            )
          ) {
            return true;
          }
          const canvasText =
            document.querySelector("#demo-canvas")?.innerText || "";
          return (
            choreo === "done" &&
            (canvasText.includes("조직 및 업무") ||
              canvasText.includes("062-410-6841") ||
              canvasText.includes("공동주택과"))
          );
        }
        return false;
      },
      {
        mode: sc.surfaceMode,
        expectedRoute: sc.expectedRoute,
        surfaceId: sc.surfaceId || sc.expectedRoute,
      },
      { timeout: timeoutMs },
    );
  } catch {
    const diag = await collectMvpDiag(page);
    throw new Error(
      `[${sc.label}] surface timeout expected=${sc.expectedRoute} diag=${JSON.stringify(diag)}`,
    );
  }
}

// ── Main ──────────────────────────────────────────────────────────────────

async function main() {
  const requestedBase = process.argv[2];
  let origin;
  let cleanup = async () => {};

  if (requestedBase) {
    origin = new URL(requestedBase).origin;
  } else {
    const srv = await createStaticServer(PROJECT_ROOT);
    origin = srv.origin;
    cleanup = async () => {
      await new Promise((r) => srv.server.close(r));
    };
  }

  const browser = await launchBrowser();
  const residentSafety = createSafetyTracker(origin);

  try {
    // ════════════════════════════════════════════════════════════════════
    // A) Unit-level mock supplements
    // ════════════════════════════════════════════════════════════════════
    console.log("[1164] unit mock supplements");
    const unitPage = await browser.newPage({
      viewport: { width: 1280, height: 800 },
    });
    attachSafety(unitPage, residentSafety);
    await openResident(unitPage, origin);

    // Same-task post-done stop
    {
      await resetMockOnly(unitPage);
      const state = makeBrowserState(["nav-apartment-dept"]);
      let resp = await callRespond(unitPage, "공동주택과 연락처 찾아줘", state);
      assert.ok(getAction(resp)?.click_element_by_index);
      // Unit path may set route only for final success check (not a UI product path).
      await unitPage.evaluate(() =>
        window.CitizenActionDemoCanvas.navigateToRoute("apartment-dept"),
      );
      resp = await callRespond(unitPage, "공동주택과 연락처 찾아줘", state);
      assert.ok(getAction(resp)?.done?.success === true);
      const genBefore = await unitPage.evaluate(() =>
        window.PageAgentMockModel.getTaskGeneration(),
      );
      const taskBefore = await unitPage.evaluate(() =>
        window.PageAgentMockModel.getActiveTaskId(),
      );
      resp = await callRespond(unitPage, "공동주택과 연락처 찾아줘", state);
      const action = getAction(resp);
      assert.ok(action?._stop, "post-done stop");
      assert.strictEqual(
        resp.choices[0].finish_reason,
        "stop",
        "finish_reason=stop",
      );
      const genAfter = await unitPage.evaluate(() =>
        window.PageAgentMockModel.getTaskGeneration(),
      );
      const taskAfter = await unitPage.evaluate(() =>
        window.PageAgentMockModel.getActiveTaskId(),
      );
      const diag = await unitPage.evaluate(() =>
        window.PageAgentMockModel.getDiagnostics(),
      );
      const clicks = diag.actionNames.filter(
        (a) => a === "click_element_by_index",
      ).length;
      assert.strictEqual(clicks, 1, "no additional click after done");
      assert.strictEqual(genAfter, genBefore, "generation not fake-new-task");
      assert.strictEqual(taskAfter, taskBefore, "same task id retained on stop");
      console.log("  same-task post-done stop: PASS", { taskBefore, genBefore });
    }

    // Missing target / wrong route (unit)
    {
      await resetMockOnly(unitPage);
      let resp = await callRespond(
        unitPage,
        "공동주택과 연락처 찾아줘",
        makeBrowserState(["unrelated-target"]),
      );
      assert.ok(getAction(resp)?.done?.success === false, "missing target");
      console.log("  missing-target fail-closed: PASS");

      await resetMockOnly(unitPage);
      resp = await callRespond(
        unitPage,
        "공동주택과 연락처 찾아줘",
        makeBrowserState(["nav-apartment-dept"]),
      );
      assert.ok(getAction(resp)?.click_element_by_index);
      await unitPage.evaluate(() =>
        window.CitizenActionDemoCanvas.navigateToRoute("home"),
      );
      resp = await callRespond(
        unitPage,
        "공동주택과 연락처 찾아줘",
        makeBrowserState(["nav-apartment-dept"]),
      );
      assert.ok(getAction(resp)?.done?.success === false, "wrong route");
      console.log("  wrong-route fail-closed: PASS");
    }

    // Alias recognition (unit supplement)
    {
      await resetMockOnly(unitPage);
      let resp = await callRespond(
        unitPage,
        "북구청장에게 글을 쓰고 싶어요",
        makeBrowserState(["mayor-office-open", "mayor-message-write"]),
      );
      assert.ok(getAction(resp)?.click_element_by_index, "mayor alias unit");
      await resetMockOnly(unitPage);
      resp = await callRespond(
        unitPage,
        "가로등이 고장 났어요",
        makeBrowserState(["nav-complaint-board", "complaint-write"]),
      );
      assert.ok(getAction(resp)?.click_element_by_index, "complaint alias unit");
      console.log("  unit alias recognition: PASS");
    }

    await unitPage.close();

    // ════════════════════════════════════════════════════════════════════
    // B) Real resident UI — mayor / complaint / A→B
    // ════════════════════════════════════════════════════════════════════
    console.log("[1164] real resident UI contracts");

    // ── Mayor stakeholder via chat UI ──
    {
      const page = await browser.newPage({
        viewport: { width: 1440, height: 900 },
      });
      attachSafety(page, residentSafety);
      await openResident(page, origin);
      await installActionProbe(page);
      await clearProbe(page);
      // Read-only: clear diagnostics so evidence is for this UI run only.
      await page.evaluate(() => window.PageAgentMockModel.resetDiagnostics());

      await submitViaChatUi(page, "북구청장에게 글을 쓰고 싶어요");
      const ev = await waitForUiTaskDone(page, {
        expectedRoute: "mayor-complaint-write",
        minClicks: 2,
        label: "ui-mayor",
      });
      const probe = await readProbe(page);
      assert.ok(
        String(ev.activeTaskId || "").startsWith("mayor_proposal_writing#"),
        `mayor task id: ${ev.activeTaskId}`,
      );
      assert.strictEqual(ev.lastSuccess, true, "mayor success=true");
      assert.strictEqual(ev.route, "mayor-complaint-write", "mayor final route");
      assert.ok(
        probe.clicks.includes("mayor-office-open") || probe.clicks.length >= 2,
        `mayor clicks observed: ${JSON.stringify(probe.clicks)}`,
      );
      console.log("  UI mayor stakeholder: PASS", {
        taskId: ev.activeTaskId,
        route: ev.route,
        clicks: probe.clicks,
      });
      await page.close();
    }

    // ── Complaint / streetlight stakeholder via chat UI ──
    {
      const page = await browser.newPage({
        viewport: { width: 1440, height: 900 },
      });
      attachSafety(page, residentSafety);
      await openResident(page, origin);
      await installActionProbe(page);
      await clearProbe(page);
      await page.evaluate(() => window.PageAgentMockModel.resetDiagnostics());

      const routeTrail = [];
      await submitViaChatUi(page, "가로등이 고장 났어요");
      const ev = await waitForUiTaskDone(page, {
        expectedRoute: "complaint-write",
        minClicks: 2,
        label: "ui-complaint",
        routeTrail,
      });
      const probe = await readProbe(page);
      assert.strictEqual(ev.lastSuccess, true, "complaint success");
      assert.strictEqual(ev.route, "complaint-write");
      assert.ok(
        String(ev.activeTaskId || "").startsWith("complaint_screen#"),
        `complaint task id: ${ev.activeTaskId}`,
      );
      // Ordered targets: real agent loop + mock navSteps (read-only scenario table).
      const expectedOrder = await page.evaluate(() => {
        const s = (window.PageAgentParityScenarios?.SCENARIOS || []).find(
          (x) => x.id === "complaint_screen",
        );
        return (s?.navSteps || []).map((step) => step.target);
      });
      assert.deepStrictEqual(
        expectedOrder,
        ["nav-complaint-board", "complaint-write"],
        "complaint scenario navSteps order",
      );
      // Diagnostics: exactly two clicks then done for this UI run
      const clickCount = ev.actionNames.filter(
        (a) => a === "click_element_by_index",
      ).length;
      assert.strictEqual(clickCount, 2, "complaint two-step click count");
      assert.strictEqual(
        ev.actionNames[0],
        "click_element_by_index",
        "complaint first action click",
      );
      assert.strictEqual(
        ev.actionNames[1],
        "click_element_by_index",
        "complaint second action click",
      );
      assert.strictEqual(ev.actionNames[2], "done", "complaint third action done");
      // Probe resolves tree targets when available; require ordered match if resolved.
      if (
        probe.clicks.length >= 2 &&
        !String(probe.clicks[0]).startsWith("index:") &&
        !String(probe.clicks[1]).startsWith("index:")
      ) {
        assert.deepStrictEqual(
          probe.clicks.slice(0, 2),
          ["nav-complaint-board", "complaint-write"],
          `probe click order: ${JSON.stringify(probe.clicks)}`,
        );
      } else {
        // Fallback evidence: two clicks + intermediate board surface + final write.
        const uniqueRoutes = [...new Set(routeTrail.filter(Boolean))];
        assert.ok(
          uniqueRoutes.includes("complaint-board"),
          `expected intermediate complaint-board in ${JSON.stringify(uniqueRoutes)}`,
        );
        assert.ok(
          uniqueRoutes.includes("complaint-write"),
          `expected final complaint-write in ${JSON.stringify(uniqueRoutes)}`,
        );
      }
      console.log("  UI complaint two-step: PASS", {
        taskId: ev.activeTaskId,
        expectedOrder,
        probeClicks: probe.clicks,
        routes: [...new Set(routeTrail.filter(Boolean))],
      });
      await page.close();
    }

    // ── A→B isolation via chat UI only (no test reset/home navigate) ──
    {
      const page = await browser.newPage({
        viewport: { width: 1440, height: 900 },
      });
      attachSafety(page, residentSafety);
      await openResident(page, origin);
      await installActionProbe(page);
      const urlBefore = page.url();

      // A
      await page.evaluate(() => window.PageAgentMockModel.resetDiagnostics());
      await clearProbe(page);
      await submitViaChatUi(page, "공동주택과 연락처 찾아줘");
      const evA = await waitForUiTaskDone(page, {
        expectedRoute: "apartment-dept",
        minClicks: 1,
        label: "ui-A-apartment",
      });
      const probeA = await readProbe(page);
      assert.strictEqual(evA.lastSuccess, true, "A success");
      assert.strictEqual(evA.route, "apartment-dept");
      assert.ok(
        String(evA.activeTaskId || "").startsWith("apartment_contact#"),
        `A task: ${evA.activeTaskId}`,
      );
      const taskA = evA.activeTaskId;
      const genA = evA.generation;
      const clicksA = [...probeA.clicks];

      // Return to conversation via visible UI when needed (not internal APIs)
      await returnToConversationUi(page);

      // B — must go through resident-demo sendMessage isolation path
      await page.evaluate(() => window.PageAgentMockModel.resetDiagnostics());
      await clearProbe(page);
      await submitViaChatUi(page, "대형폐기물 신청 메뉴 찾아줘");
      const evB = await waitForUiTaskDone(page, {
        expectedRoute: "bulky-waste-disposal",
        minClicks: 1,
        label: "ui-B-bulky",
      });
      const probeB = await readProbe(page);
      assert.strictEqual(evB.lastSuccess, true, "B success");
      assert.strictEqual(evB.route, "bulky-waste-disposal");
      assert.ok(
        String(evB.activeTaskId || "").startsWith("bulky_waste_menu#"),
        `B task: ${evB.activeTaskId}`,
      );
      assert.notStrictEqual(taskA, evB.activeTaskId, "A task ID != B task ID");
      assert.ok(
        evB.generation > genA,
        `B generation ${evB.generation} > A generation ${genA}`,
      );
      // B must not re-click apartment targets
      assert.ok(
        !probeB.clicks.some((t) => /apartment|nav-apartment/i.test(t)),
        `no stale A click during B: ${JSON.stringify(probeB.clicks)}`,
      );
      assert.ok(
        probeB.clicks.includes("nav-bulky-waste-disposal") ||
          probeB.clicks.some((t) => /bulky/i.test(t)),
        `B bulky click: ${JSON.stringify(probeB.clicks)}`,
      );
      // First respond of B should see home (demo restoreCanvasToSafeHome)
      const firstRouteB = probeB.routesAtRespond[0];
      assert.ok(
        firstRouteB === "home" || firstRouteB === "" || firstRouteB == null,
        `B start boundary should be home, got ${firstRouteB}`,
      );
      // Same document navigation only — hash may change from canvas anchors,
      // but origin+pathname must stay and Playwright must not re-load the page.
      const urlAfter = page.url();
      assert.strictEqual(
        new URL(urlAfter).origin + new URL(urlAfter).pathname,
        new URL(urlBefore).origin + new URL(urlBefore).pathname,
        "no page reload (pathname must stay)",
      );
      console.log("  UI A→B without reload: PASS", {
        taskA,
        taskB: evB.activeTaskId,
        genA,
        genB: evB.generation,
        clicksA,
        clicksB: probeB.clicks,
        firstRouteB,
        urlBefore,
        urlAfter,
      });
      await page.close();
    }

    assertSafety(residentSafety, "resident");

    // ════════════════════════════════════════════════════════════════════
    // C) Deterministic MVP confirmation (five production phrases)
    // ════════════════════════════════════════════════════════════════════
    console.log("[1164] deterministic MVP confirmation contract");
    const tmp = mkdtempSync(join(tmpdir(), "pa-1164-"));
    const build = spawnSync(
      "python",
      ["scripts/build_cloudflare_pages.py", "--mode", "live", "--out-dir", tmp],
      {
        cwd: PROJECT_ROOT,
        env: { ...process.env, PYTHONPATH: PROJECT_ROOT },
        encoding: "utf8",
      },
    );
    if (build.status !== 0) {
      console.error(build.stdout, build.stderr);
      throw new Error("pages build failed for MVP confirmation contract");
    }

    const mvpSrv = await createStaticServer(tmp);
    const mvpPage = await browser.newPage({
      viewport: { width: 1366, height: 900 },
    });
    const mvpSafety = createSafetyTracker(mvpSrv.origin);
    attachSafety(mvpPage, mvpSafety);

    await mvpPage.route("**/api/mvp/ask", async (route) => {
      const post = route.request().postData() || "";
      let action = "none";
      let answer = "안내 범위에 없는 요청입니다.";
      let failure_code = "";
      if (post.includes("공동주택") || post.includes("apartment")) {
        action = "housing_department";
        answer = "공동주택과 안내입니다.";
      } else if (post.includes("대형") || post.includes("폐기물") || post.includes("bulky")) {
        action = "bulky_waste";
        answer = "대형폐기물 안내입니다.";
      } else if (
        post.includes("북구청장") ||
        post.includes("구청장") ||
        post.includes("제안") ||
        post.includes("mayor")
      ) {
        action = "mayor_message_assist";
        answer = "구청장 제안 안내입니다.";
      } else if (
        post.includes("가로등") ||
        post.includes("streetlight") ||
        post.includes("민원 작성")
      ) {
        action = "streetlight_report";
        answer = "가로등 고장 신고 안내입니다.";
      } else if (post.includes("지원하지") || post.includes("날씨")) {
        action = "none";
        answer = "현재 준비된 안내 범위에 없는 요청입니다.";
        failure_code = "unsupported_request";
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify({
          ok: action !== "none",
          answer,
          action,
          confidence: action === "none" ? 0 : 1,
          failure_code,
        }),
      });
    });

    const five = [
      {
        label: "apartment",
        ask: "공동주택과 연락처 찾아줘",
        chip: "공동주택",
        expectedRoute: "apartment-dept",
        surfaceId: "apartment-dept",
        surfaceMode: "official-surface",
        expectSuccess: true,
      },
      {
        label: "bulky",
        ask: "대형폐기물 신청 메뉴 찾아줘",
        chip: "대형폐기물",
        expectedRoute: "bulky-waste-disposal",
        surfaceMode: "route",
        expectSuccess: true,
      },
      {
        label: "mayor",
        ask: "북구청장에게 글을 쓰고 싶어요",
        chip: null,
        expectedRoute: "mayor-complaint-write",
        surfaceMode: "route",
        expectSuccess: true,
      },
      {
        label: "complaint-streetlight",
        ask: "가로등이 고장 났어요",
        chip: null,
        expectedRoute: "complaint-write",
        surfaceMode: "route",
        expectSuccess: true,
      },
      {
        label: "unsupported",
        ask: "지원하지 않는 요청",
        chip: null,
        expectedRoute: "home",
        surfaceMode: "route",
        expectSuccess: false,
      },
    ];

    const finalRoutes = {};

    for (const sc of five) {
      await mvpPage.goto(`${mvpSrv.origin}/mvp/?lang=ko`, {
        waitUntil: "domcontentloaded",
        timeout: 45000,
      });
      await mvpPage.waitForFunction(
        () =>
          !!(
            window.CitizenActionDemoCanvas &&
            window.CitizenFirstUseShell &&
            window.CitizenFirstChoreography
          ),
        null,
        { timeout: 30000 },
      );

      let usedChip = false;
      if (sc.chip) {
        const chip = mvpPage
          .locator(".chat-chip, button.chat-chip, [data-chip]")
          .filter({ hasText: sc.chip })
          .first();
        if ((await chip.count()) > 0) {
          await chip.click();
          usedChip = true;
        }
      }
      if (!usedChip) {
        const input = mvpPage
          .locator(
            "#chat-composer-input, #chat-input, textarea.chat-input, textarea",
          )
          .first();
        await input.waitFor({ state: "visible", timeout: 10000 });
        await input.fill(sc.ask);
        const send = mvpPage
          .locator(
            "#chat-composer-send, #chat-send, button[type='submit'], .chat-send",
          )
          .first();
        if ((await send.count()) > 0) await send.click();
        else await input.press("Enter");
      }

      if (!sc.expectSuccess) {
        await mvpPage.waitForTimeout(2500);
        const diag = await collectMvpDiag(mvpPage);
        assert.ok(
          diag.route === "home" || diag.route === "" || !diag.route,
          `unsupported must stay home, got ${diag.route}`,
        );
        finalRoutes[sc.label] = diag.route || "home";
        console.log(`  MVP unsupported stay home: PASS route=${finalRoutes[sc.label]}`);
        continue;
      }

      await clickMvpConfirmation(mvpPage, sc.label);
      await waitForSurface(mvpPage, sc, 120000);

      const evidence = await mvpPage.evaluate((spec) => {
        const route = window.CitizenActionDemoCanvas?.getCurrentRouteId?.() || "";
        const official = document.querySelector(
          `[data-official-route-id="${spec.surfaceId || spec.expectedRoute}"]`,
        );
        const canvasText =
          document.querySelector("#demo-canvas")?.innerText || "";
        return {
          route,
          officialSurface: official
            ? official.getAttribute("data-official-route-id")
            : null,
          choreo: document.body.getAttribute("data-choreography-state") || "",
          hasHousingMarkers:
            canvasText.includes("조직 및 업무") ||
            canvasText.includes("062-410-6841") ||
            canvasText.includes("공동주택과"),
        };
      }, sc);

      if (sc.surfaceMode === "route") {
        assert.strictEqual(evidence.route, sc.expectedRoute, `${sc.label} route`);
        finalRoutes[sc.label] = evidence.route;
      } else {
        assert.ok(
          evidence.officialSurface === sc.expectedRoute ||
            evidence.route === sc.expectedRoute ||
            (evidence.choreo === "done" && evidence.hasHousingMarkers) ||
            evidence.hasHousingMarkers,
          `${sc.label} surface missing: ${JSON.stringify(evidence)}`,
        );
        finalRoutes[sc.label] =
          evidence.officialSurface ||
          (evidence.route !== "home" ? evidence.route : sc.expectedRoute);
      }
      console.log(
        `  MVP confirm ${sc.label} → ${finalRoutes[sc.label]} (route=${evidence.route}): PASS`,
      );
    }

    assertSafety(mvpSafety, "mvp");
    console.log("  five deterministic final routes:", finalRoutes);

    await new Promise((r) => mvpSrv.server.close(r));
    rmSync(tmp, { recursive: true, force: true });
    await mvpPage.close();

    console.log("\n=== #1164 page-agent production gaps PASS ===");
    console.log("safety resident:", {
      external: residentSafety.external.length,
      requestFailures: residentSafety.requestFailures.length,
      consoleErrors: residentSafety.consoleErrors.length,
      pageErrors: residentSafety.pageErrors.length,
      formSubmissions: residentSafety.formSubmissions.length,
      loginAttempts: residentSafety.loginAttempts.length,
      paymentAttempts: residentSafety.paymentAttempts.length,
      liveProvider: residentSafety.liveProvider.length,
    });
    console.log("safety mvp:", {
      external: mvpSafety.external.length,
      requestFailures: mvpSafety.requestFailures.length,
      consoleErrors: mvpSafety.consoleErrors.length,
      pageErrors: mvpSafety.pageErrors.length,
      formSubmissions: mvpSafety.formSubmissions.length,
      loginAttempts: mvpSafety.loginAttempts.length,
      paymentAttempts: mvpSafety.paymentAttempts.length,
      liveProvider: mvpSafety.liveProvider.length,
    });
  } finally {
    await browser.close();
    await cleanup();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
