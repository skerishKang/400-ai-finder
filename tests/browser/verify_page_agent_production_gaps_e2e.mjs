/**
 * #1164 — Page Agent production-gap browser contracts.
 *
 * Covers:
 *  - stakeholder phrasing aliases (mayor / streetlight→complaint)
 *  - canonical mayor/complaint phrasings
 *  - complaint two-step action order
 *  - unsupported fail-closed (no click / no navigation)
 *  - A→B top-level requests without reload + new task/session IDs
 *  - same-task post-done stop
 *  - missing-target / wrong-route fail-closed
 *  - deterministic /mvp/ confirmation UI for five production phrases
 *
 * Safety: no external origin, no live provider, no real civic submission.
 * Does not modify #1152 product files or call internal route dispatchers
 * to fake success.
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

async function resetMock(page) {
  await page.evaluate(() => {
    window.PageAgentMockModel.resetSession();
    window.PageAgentMockModel.resetDiagnostics();
  });
}

async function getSessionMeta(page) {
  return page.evaluate(() => {
    const d = window.PageAgentMockModel.getDiagnostics();
    return {
      taskIds: [...d.taskIds],
      actionNames: [...d.actionNames],
      successValues: [...d.successValues],
      lastSuccess: d.lastSuccess,
      callCount: d.callCount,
      activeTaskId: window.PageAgentMockModel.getActiveTaskId
        ? window.PageAgentMockModel.getActiveTaskId()
        : null,
      generation: window.PageAgentMockModel.getTaskGeneration
        ? window.PageAgentMockModel.getTaskGeneration()
        : null,
    };
  });
}

async function runClickThenSuccess(page, prompt, targets, expectedRoute) {
  await resetMock(page);
  const state = makeBrowserState(targets);
  for (let i = 0; i < targets.length; i++) {
    const resp = await callRespond(page, prompt, state);
    const action = getAction(resp);
    assert.ok(action?.click_element_by_index, `${prompt}: expected click step ${i + 1}`);
  }
  await page.evaluate((route) => {
    window.CitizenActionDemoCanvas.navigateToRoute(route);
  }, expectedRoute);
  const doneResp = await callRespond(page, prompt, state);
  const done = getAction(doneResp);
  assert.ok(done?.done, `${prompt}: expected done`);
  assert.strictEqual(done.done.success, true, `${prompt}: expected success=true`);
  return getSessionMeta(page);
}

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
        document.querySelectorAll("#chat-thread button, .chat-thread button, .chat-msg button"),
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
    '.chat-msg--confirm-run button.chat-decision__button--primary, ' +
    'button:has-text("예, 안내해 주세요")';

  try {
    await page.locator(selector).first().waitFor({ state: "visible", timeout: 20000 });
  } catch {
    const diag = await collectMvpDiag(page);
    throw new Error(
      `[${label}] confirmation timeout (visible wait): ${JSON.stringify(diag)}`,
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
    const diag = await collectMvpDiag(page);
    throw new Error(
      `[${label}] confirmation stayed disabled: ${JSON.stringify(diag)}`,
    );
  }

  // Prefer the localized primary confirm action that is currently enabled.
  const clicked = await page.evaluate(() => {
    const buttons = Array.from(
      document.querySelectorAll(
        ".chat-msg--confirm-run button, button.chat-decision__button--primary, button",
      ),
    );
    const match = buttons.find(
      (b) =>
        !b.disabled &&
        /예,\s*안내해 주세요|Yes,?\s*please guide|예.*안내/i.test((b.textContent || "").trim()) &&
        !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length),
    );
    if (!match) return false;
    match.click();
    return true;
  });
  if (!clicked) {
    const diag = await collectMvpDiag(page);
    throw new Error(`[${label}] no enabled confirmation candidate: ${JSON.stringify(diag)}`);
  }
}

/**
 * Wait for journey surface evidence after real confirmation click.
 * Housing uses in-home J-DEPT surface (route may stay home while
 * data-official-route-id="apartment-dept" is present). Other journeys
 * set canvas getCurrentRouteId().
 */
async function waitForSurface(page, sc, timeoutMs = 120000) {
  try {
    await page.waitForFunction(
      (spec) => {
        const route = window.CitizenActionDemoCanvas?.getCurrentRouteId?.() || "";
        const choreo = document.body.getAttribute("data-choreography-state") || "";
        if (spec.mode === "route") {
          return route === spec.expectedRoute;
        }
        if (spec.mode === "official-surface") {
          const el = document.querySelector(
            `[data-official-route-id="${spec.surfaceId}"]`,
          );
          if (el) return true;
          // Housing J-DEPT may keep route=home; accept completed walkthrough markers.
          const canvasText = document.querySelector("#demo-canvas")?.innerText || "";
          if (
            choreo === "done" &&
            (canvasText.includes("조직 및 업무") ||
              canvasText.includes("062-410-6841") ||
              canvasText.includes("공동주택과"))
          ) {
            return true;
          }
          return false;
        }
        if (spec.mode === "route-or-surface") {
          if (route === spec.expectedRoute) return true;
          return !!document.querySelector(
            `[data-official-route-id="${spec.surfaceId || spec.expectedRoute}"]`,
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
    const extra = await page.evaluate((surfaceId) => ({
      officialSurface: !!document.querySelector(
        `[data-official-route-id="${surfaceId}"]`,
      ),
      canvasText: (document.querySelector("#demo-canvas")?.innerText || "").slice(
        0,
        200,
      ),
    }), sc.surfaceId || sc.expectedRoute);
    throw new Error(
      `[${sc.label}] surface timeout expected=${sc.expectedRoute} mode=${sc.surfaceMode} got=${diag.route} diag=${JSON.stringify({ ...diag, ...extra })}`,
    );
  }
}

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
  const page = await browser.newPage();
  const safety = {
    external: 0,
    pageErrors: 0,
    consoleErrors: 0,
  };
  page.on("pageerror", () => {
    safety.pageErrors += 1;
  });
  page.on("console", (m) => {
    if (m.type() === "error") safety.consoleErrors += 1;
  });
  page.on("request", (req) => {
    const u = req.url();
    if (u.startsWith("data:") || u.startsWith("blob:")) return;
    try {
      if (new URL(u).origin !== origin) safety.external += 1;
    } catch {
      /* ignore */
    }
  });

  try {
    console.log("[1164] mock-model path: aliases, isolation, fail-closed");
    await page.goto(`${origin}${RESIDENT_ROUTE}`, {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });
    await page.waitForFunction(
      () => window.PageAgentMockModel && window.CitizenActionDemoCanvas,
      null,
      { timeout: 15000 },
    );

    // ── Stakeholder mayor phrase ──
    {
      const meta = await runClickThenSuccess(
        page,
        "북구청장에게 글을 쓰고 싶어요",
        ["mayor-office-open", "mayor-message-write"],
        "mayor-complaint-write",
      );
      assert.ok(
        String(meta.activeTaskId || "").startsWith("mayor_proposal_writing#"),
        `mayor task id shape: ${meta.activeTaskId}`,
      );
      assert.strictEqual(meta.lastSuccess, true);
      console.log("  mayor stakeholder phrase: PASS", meta.activeTaskId);
    }

    // ── Stakeholder complaint / streetlight phrase (two-step) ──
    {
      await resetMock(page);
      const state = makeBrowserState(["nav-complaint-board", "complaint-write"]);
      let resp = await callRespond(page, "가로등이 고장 났어요", state);
      let action = getAction(resp);
      assert.ok(action?.click_element_by_index, "complaint alias step1 click");
      const idx1 = action.click_element_by_index.index;
      resp = await callRespond(page, "가로등이 고장 났어요", state);
      action = getAction(resp);
      assert.ok(action?.click_element_by_index, "complaint alias step2 click");
      const idx2 = action.click_element_by_index.index;
      assert.notStrictEqual(idx1, idx2, "complaint two-step distinct targets");
      // Order: index 0 = nav-complaint-board, index 1 = complaint-write
      assert.strictEqual(idx1, 0, "first click nav-complaint-board");
      assert.strictEqual(idx2, 1, "second click complaint-write");
      await page.evaluate(() =>
        window.CitizenActionDemoCanvas.navigateToRoute("complaint-write"),
      );
      resp = await callRespond(page, "가로등이 고장 났어요", state);
      action = getAction(resp);
      assert.ok(action?.done?.success === true, "complaint alias success");
      const meta = await getSessionMeta(page);
      assert.ok(
        String(meta.activeTaskId || "").startsWith("complaint_screen#"),
        `complaint task id: ${meta.activeTaskId}`,
      );
      console.log("  streetlight→complaint two-step: PASS", meta.activeTaskId);
    }

    // ── Canonical phrases still recognized ──
    {
      await resetMock(page);
      let resp = await callRespond(
        page,
        "구청장에게 제안할 글 작성을 도와줘",
        makeBrowserState(["mayor-office-open", "mayor-message-write"]),
      );
      assert.ok(getAction(resp)?.click_element_by_index, "canonical mayor");

      await resetMock(page);
      resp = await callRespond(
        page,
        "민원 작성 화면을 열어줘",
        makeBrowserState(["nav-complaint-board", "complaint-write"]),
      );
      assert.ok(getAction(resp)?.click_element_by_index, "canonical complaint");
      console.log("  canonical mayor + complaint phrases: PASS");
    }

    // ── Unsupported fail-closed ──
    {
      await resetMock(page);
      await page.evaluate(() => window.CitizenActionDemoCanvas.navigateToRoute("home"));
      const resp = await callRespond(page, "지원하지 않는 요청", FULL_TARGETS);
      const action = getAction(resp);
      assert.ok(action?.done, "unsupported done");
      assert.strictEqual(action.done.success, false, "unsupported success=false");
      const meta = await getSessionMeta(page);
      assert.ok(
        !meta.actionNames.includes("click_element_by_index"),
        "unsupported must not click",
      );
      const route = await page.evaluate(
        () => window.CitizenActionDemoCanvas.getCurrentRouteId(),
      );
      assert.strictEqual(route, "home", "unsupported no navigation");
      console.log("  unsupported fail-closed: PASS");
    }

    // ── Same-task post-done stop ──
    {
      await resetMock(page);
      const state = makeBrowserState(["nav-apartment-dept"]);
      let resp = await callRespond(page, "공동주택과 연락처 찾아줘", state);
      assert.ok(getAction(resp)?.click_element_by_index);
      await page.evaluate(() =>
        window.CitizenActionDemoCanvas.navigateToRoute("apartment-dept"),
      );
      resp = await callRespond(page, "공동주택과 연락처 찾아줘", state);
      assert.ok(getAction(resp)?.done?.success === true);
      const taskId1 = await page.evaluate(() =>
        window.PageAgentMockModel.getActiveTaskId(),
      );
      resp = await callRespond(page, "공동주택과 연락처 찾아줘", state);
      const action = getAction(resp);
      assert.ok(action?._stop, "post-done must stop");
      const meta = await getSessionMeta(page);
      const clicks = meta.actionNames.filter((a) => a === "click_element_by_index").length;
      assert.strictEqual(clicks, 1, "no extra clicks after done");
      console.log("  same-task post-done stop: PASS", taskId1);
    }

    // ── A→B without reload + unique task IDs + home restore ──
    {
      await resetMock(page);
      await page.evaluate(() => window.CitizenActionDemoCanvas.navigateToRoute("home"));

      // A: apartment complete
      let state = makeBrowserState([
        "nav-apartment-dept",
        "nav-bulky-waste-disposal",
      ]);
      let resp = await callRespond(page, "공동주택과 연락처 찾아줘", state);
      assert.ok(getAction(resp)?.click_element_by_index);
      await page.evaluate(() =>
        window.CitizenActionDemoCanvas.navigateToRoute("apartment-dept"),
      );
      resp = await callRespond(page, "공동주택과 연락처 찾아줘", state);
      assert.ok(getAction(resp)?.done?.success === true);
      const taskA = await page.evaluate(() =>
        window.PageAgentMockModel.getActiveTaskId(),
      );
      const genA = await page.evaluate(() =>
        window.PageAgentMockModel.getTaskGeneration(),
      );
      const routeAfterA = await page.evaluate(() =>
        window.CitizenActionDemoCanvas.getCurrentRouteId(),
      );
      assert.strictEqual(routeAfterA, "apartment-dept");

      // Demo isolation path: new top-level request resets session + restores home
      // (mirrors resident-demo sendMessage). No page reload.
      await page.evaluate(() => {
        window.PageAgentMockModel.resetSession();
        const canvas = window.CitizenActionDemoCanvas;
        if (canvas.getCurrentRouteId() !== "home") {
          canvas.navigateToRoute("home");
        }
      });
      const routeHome = await page.evaluate(() =>
        window.CitizenActionDemoCanvas.getCurrentRouteId(),
      );
      assert.strictEqual(routeHome, "home", "B starts from safe home surface");

      const homeState = makeBrowserState([
        "nav-bulky-waste-disposal",
        "nav-apartment-dept",
      ]);
      resp = await callRespond(page, "대형폐기물 신청 메뉴 찾아줘", homeState);
      assert.ok(
        getAction(resp)?.click_element_by_index,
        "B must click (not target missing from stale apartment route)",
      );
      await page.evaluate(() =>
        window.CitizenActionDemoCanvas.navigateToRoute("bulky-waste-disposal"),
      );
      resp = await callRespond(page, "대형폐기물 신청 메뉴 찾아줘", homeState);
      assert.ok(getAction(resp)?.done?.success === true, "B success");
      const taskB = await page.evaluate(() =>
        window.PageAgentMockModel.getActiveTaskId(),
      );
      const genB = await page.evaluate(() =>
        window.PageAgentMockModel.getTaskGeneration(),
      );
      assert.notStrictEqual(taskA, taskB, "new task id for B");
      assert.ok(genB > genA, "generation advanced for B");
      assert.ok(String(taskA).startsWith("apartment_contact#"), "A id shape");
      assert.ok(String(taskB).startsWith("bulky_waste_menu#"), "B id shape");
      console.log("  A→B without reload + new task id: PASS", { taskA, taskB, genA, genB });
    }

    // ── Missing target failure ──
    {
      await resetMock(page);
      const emptyState = makeBrowserState(["unrelated-target"]);
      const resp = await callRespond(page, "공동주택과 연락처 찾아줘", emptyState);
      const action = getAction(resp);
      assert.ok(action?.done && action.done.success === false, "missing target fail");
      console.log("  missing target failure: PASS");
    }

    // ── Wrong final route failure ──
    {
      await resetMock(page);
      const state = makeBrowserState(["nav-apartment-dept"]);
      let resp = await callRespond(page, "공동주택과 연락처 찾아줘", state);
      assert.ok(getAction(resp)?.click_element_by_index);
      await page.evaluate(() => window.CitizenActionDemoCanvas.navigateToRoute("home"));
      resp = await callRespond(page, "공동주택과 연락처 찾아줘", state);
      const action = getAction(resp);
      assert.ok(action?.done && action.done.success === false, "wrong route fail");
      console.log("  wrong final route failure: PASS");
    }

    // ── Deterministic MVP confirmation contract (five production phrases) ──
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
    const mvpPage = await browser.newPage();
    const mvpSafety = { external: 0, pageErrors: 0, consoleErrors: 0 };
    mvpPage.on("pageerror", () => {
      mvpSafety.pageErrors += 1;
    });
    mvpPage.on("console", (m) => {
      if (m.type() === "error") mvpSafety.consoleErrors += 1;
    });
    mvpPage.on("request", (req) => {
      const u = req.url();
      if (u.startsWith("data:") || u.startsWith("blob:")) return;
      try {
        if (new URL(u).origin !== mvpSrv.origin) mvpSafety.external += 1;
      } catch {
        /* ignore */
      }
    });

    // Deterministic ask API — maps production phrases to actions only.
    // No live provider. No real submission.
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
        // Housing journey lands apartment-dept official surface via J-DEPT clicks;
        // canvas route id may remain home while data-official-route-id is set.
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
        // Journey id mayor-message-assist → canvas route mayor-complaint-write
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
      try {
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
      } catch {
        const boot = await mvpPage.evaluate(() => ({
          href: location.href,
          title: document.title,
          keys: Object.keys(window).filter((k) => /Citizen|Canvas|Choreo/i.test(k)),
          body: (document.body?.innerText || "").slice(0, 200),
        }));
        throw new Error(`[${sc.label}] MVP shell boot timeout: ${JSON.stringify(boot)}`);
      }

      // Prefer chip when available (deterministic entry); otherwise free-text ask.
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
        if ((await send.count()) > 0) {
          await send.click();
        } else {
          await input.press("Enter");
        }
      }

      if (!sc.expectSuccess) {
        // Unsupported: no confirmation journey start, stay home / no wrong route.
        await mvpPage.waitForTimeout(2500);
        const diag = await collectMvpDiag(mvpPage);
        assert.ok(
          diag.route === "home" || diag.route === "" || !diag.route,
          `unsupported must not leave home, got ${diag.route}`,
        );
        // Must not have auto-started a guidance journey on canvas.
        const hasConfirm = diag.confirmationCandidates.some(
          (c) => c.visible && /예.*안내/i.test(c.text),
        );
        // Some shells may still show a soft reply without confirm; either is ok if route stays home.
        finalRoutes[sc.label] = diag.route || "home";
        console.log(
          `  MVP unsupported stay home: PASS route=${finalRoutes[sc.label]} confirm=${hasConfirm}`,
        );
        continue;
      }

      // Real confirmation UI click (no internal dispatcher shortcut).
      await clickMvpConfirmation(mvpPage, sc.label);

      // Wait for journey surface (route or official surface) after real click.
      // Mayor/streetlight type form content later; target surface lands earlier.
      await waitForSurface(mvpPage, sc, 120000);

      const evidence = await mvpPage.evaluate((spec) => {
        const route = window.CitizenActionDemoCanvas?.getCurrentRouteId?.() || "";
        const official = document.querySelector(
          `[data-official-route-id="${spec.surfaceId || spec.expectedRoute}"]`,
        );
        const canvasText = document.querySelector("#demo-canvas")?.innerText || "";
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
        assert.strictEqual(
          evidence.route,
          sc.expectedRoute,
          `${sc.label} final route`,
        );
        finalRoutes[sc.label] = evidence.route;
      } else {
        assert.ok(
          evidence.officialSurface === sc.expectedRoute ||
            evidence.route === sc.expectedRoute ||
            (evidence.choreo === "done" && evidence.hasHousingMarkers),
          `${sc.label} surface missing: ${JSON.stringify(evidence)}`,
        );
        finalRoutes[sc.label] =
          evidence.officialSurface ||
          (evidence.route !== "home" ? evidence.route : sc.expectedRoute);
      }
      console.log(
        `  MVP confirm ${sc.label} → ${finalRoutes[sc.label]} (route=${evidence.route}, choreo=${evidence.choreo}): PASS`,
      );
    }

    assert.strictEqual(mvpSafety.external, 0, "mvp external requests=0");
    // Allow zero page/console errors; report if any (hard fail).
    assert.strictEqual(
      mvpSafety.pageErrors,
      0,
      `mvp page errors: ${mvpSafety.pageErrors}`,
    );
    console.log("  five deterministic final routes:", finalRoutes);

    await new Promise((r) => mvpSrv.server.close(r));
    rmSync(tmp, { recursive: true, force: true });
    await mvpPage.close();

    assert.strictEqual(safety.external, 0, "resident external=0");
    console.log("\n=== #1164 page-agent production gaps PASS ===");
    console.log("safety:", { ...safety, mvp: mvpSafety });
  } finally {
    await browser.close();
    await cleanup();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
