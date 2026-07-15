/** Browser E2E for the separate #1099 mayor-message proposal journey. */

import assert from "assert";
import { chromium } from "playwright";

const requestedBase = process.argv[2] || "http://127.0.0.1:8080";

function validateOrigin(raw) {
  const parsed = new URL(raw);
  const hostname = parsed.hostname.replace(/^\[|\]$/g, "");
  if (parsed.protocol !== "http:" || !new Set(["127.0.0.1", "localhost", "::1"]).has(hostname)) {
    throw new Error("Mayor E2E accepts only a local http origin.");
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error("Credentials, query, and hash are not allowed in baseUrl.");
  }
  return parsed.origin;
}

function isMobileViewport(viewport) {
  return viewport.width <= 767;
}

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch {
    return chromium.launch({ headless: true, channel: "chrome" });
  }
}

const BASE_ORIGIN = validateOrigin(requestedBase);

async function readSurfaceState(page) {
  return page.evaluate(() => {
    const body = document.body;
    const chat = document.getElementById("chat-shell");
    const canvas = document.getElementById("demo-canvas");
    const conversation = document.getElementById("tab-conversation");
    const guidance = document.getElementById("tab-guidance");
    const switcher = document.getElementById("mobile-surface-switch");

    return {
      firstUseState: body.getAttribute("data-first-use-state"),
      surface: body.getAttribute("data-mobile-surface"),
      switchHidden: switcher ? switcher.hasAttribute("hidden") : null,

      conversationPressed:
        conversation && conversation.getAttribute("aria-pressed"),
      guidancePressed: guidance && guidance.getAttribute("aria-pressed"),

      chatAriaHidden: chat && chat.getAttribute("aria-hidden"),
      chatInert: chat ? chat.hasAttribute("inert") : null,

      canvasAriaHidden: canvas && canvas.getAttribute("aria-hidden"),
      canvasInert: canvas ? canvas.hasAttribute("inert") : null,
    };
  });
}

async function selectMobileSurface(page, viewport, surface, label) {
  if (!isMobileViewport(viewport)) {
    return;
  }

  const accessibleName = surface === "guidance" ? "안내 화면" : "대화";

  const button = page.getByRole("button", {
    name: accessibleName,
    exact: true,
  });

  await button.waitFor({ state: "visible", timeout: 5000 });
  await button.click();

  await page.waitForFunction(
    (expectedSurface) =>
      document.body.getAttribute("data-mobile-surface") === expectedSurface,
    surface,
    { timeout: 5000 },
  );

  const state = await readSurfaceState(page);

  assert.strictEqual(
    state.firstUseState,
    "split",
    `${label}: shell must remain split`,
  );

  assert.strictEqual(
    state.surface,
    surface,
    `${label}: active mobile surface must be ${surface}`,
  );

  assert.strictEqual(
    state.switchHidden,
    false,
    `${label}: mobile switch must remain visible`,
  );

  if (surface === "guidance") {
    assert.strictEqual(
      state.conversationPressed,
      "false",
      `${label}: conversation aria-pressed=false`,
    );
    assert.strictEqual(
      state.guidancePressed,
      "true",
      `${label}: guidance aria-pressed=true`,
    );
    assert.strictEqual(
      state.chatAriaHidden,
      "true",
      `${label}: chat aria-hidden=true`,
    );
    assert.strictEqual(state.chatInert, true, `${label}: chat inert`);
    assert.strictEqual(
      state.canvasAriaHidden,
      "false",
      `${label}: canvas aria-hidden=false`,
    );
    assert.strictEqual(state.canvasInert, false, `${label}: canvas not inert`);
  } else {
    assert.strictEqual(
      state.conversationPressed,
      "true",
      `${label}: conversation aria-pressed=true`,
    );
    assert.strictEqual(
      state.guidancePressed,
      "false",
      `${label}: guidance aria-pressed=false`,
    );
    assert.strictEqual(
      state.chatAriaHidden,
      "false",
      `${label}: chat aria-hidden=false`,
    );
    assert.strictEqual(state.chatInert, false, `${label}: chat not inert`);
    assert.strictEqual(
      state.canvasAriaHidden,
      "true",
      `${label}: canvas aria-hidden=true`,
    );
    assert.strictEqual(state.canvasInert, true, `${label}: canvas inert`);
  }
}

async function assertSplitSurfaceContract(page, viewport, viewportLabel) {
  const state = await readSurfaceState(page);

  assert.strictEqual(
    state.firstUseState,
    "split",
    `[${viewportLabel}] split: data-first-use-state=split`,
  );

  if (isMobileViewport(viewport)) {
    assert.strictEqual(
      state.surface,
      "conversation",
      `[${viewportLabel}] split: default mobile surface=conversation`,
    );
    assert.strictEqual(
      state.switchHidden,
      false,
      `[${viewportLabel}] split: mobile switch visible`,
    );
    assert.strictEqual(
      state.conversationPressed,
      "true",
      `[${viewportLabel}] split: conversation pressed`,
    );
    assert.strictEqual(
      state.guidancePressed,
      "false",
      `[${viewportLabel}] split: guidance not pressed`,
    );
    assert.strictEqual(
      state.chatAriaHidden,
      "false",
      `[${viewportLabel}] split: chat aria-hidden=false`,
    );
    assert.strictEqual(
      state.chatInert,
      false,
      `[${viewportLabel}] split: chat not inert`,
    );
    assert.strictEqual(
      state.canvasAriaHidden,
      "true",
      `[${viewportLabel}] split: canvas aria-hidden=true`,
    );
    assert.strictEqual(
      state.canvasInert,
      true,
      `[${viewportLabel}] split: canvas inert`,
    );
  } else {
    assert.strictEqual(
      state.surface,
      null,
      `[${viewportLabel}] split: no data-mobile-surface on desktop`,
    );
    assert.ok(
      state.switchHidden === true || state.switchHidden === null,
      `[${viewportLabel}] split: mobile switch hidden on desktop`,
    );
    assert.ok(
      state.chatAriaHidden === null || state.chatAriaHidden === "false",
      `[${viewportLabel}] split: chat aria-hidden cleared on desktop`,
    );
    assert.strictEqual(
      state.chatInert,
      false,
      `[${viewportLabel}] split: chat not inert on desktop`,
    );
    assert.ok(
      state.canvasAriaHidden === null || state.canvasAriaHidden === "false",
      `[${viewportLabel}] split: canvas aria-hidden cleared on desktop`,
    );
    assert.strictEqual(
      state.canvasInert,
      false,
      `[${viewportLabel}] split: canvas not inert on desktop`,
    );
  }
}

async function runViewport(browser, viewport) {
  const viewportLabel = `${viewport.width}x${viewport.height}`;
  console.log(`[${viewportLabel}] mayor E2E start`);

  const context = await browser.newContext({ viewport, reducedMotion: "reduce" });
  const page = await context.newPage();
  const errors = [];
  const popups = [];
  const externalRequests = [];

  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("popup", (popup) => popups.push(popup.url()));
  page.on("request", (request) => {
    const url = request.url();
    if (!url.startsWith("data:") && new URL(url).origin !== BASE_ORIGIN) {
      externalRequests.push(url);
    }
  });
  await page.route("**/api/mvp/ask", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        ok: true,
        answer: "불법 주정차 신고 경로를 안내합니다.",
        action: "illegal_parking",
        confidence: 1,
        failure_code: "",
      }),
    });
  });

  await page.goto(`${BASE_ORIGIN}/mvp/`, {
    waitUntil: "networkidle",
    timeout: 15000,
  });
  await page.getByRole("button", { name: "불법 주정차 신고", exact: true }).click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-first-use-state") === "split",
    null,
    { timeout: 10000 },
  );

  console.log(`[${viewportLabel}] split`);
  await assertSplitSurfaceContract(page, viewport, viewportLabel);

  // Official routes live on the canonical canvas. Mobile must select guidance
  // first so route roots are visible (not only attached while conversation is active).
  await selectMobileSurface(
    page,
    viewport,
    "guidance",
    `[${viewportLabel}] official-route setup`,
  );
  console.log(`[${viewportLabel}] official routes`);

  for (const expected of [
    { routeId: "bulky-waste-disposal", minimumRows: 160 },
    { routeId: "passport-guidance", minimumRows: 10 },
    { routeId: "unmanned-kiosk-guidance", minimumRows: 50 },
  ]) {
    await page.evaluate(
      (routeId) => window.CitizenActionDemoCanvas.navigateToRoute(routeId),
      expected.routeId,
    );
    const officialRoot = page.locator(
      `[data-official-route-id="${expected.routeId}"]`,
    );
    await officialRoot.waitFor({ state: "visible", timeout: 5000 });
    assert.strictEqual(
      (await officialRoot.getAttribute("data-canonical-sha256")).length,
      64,
      `[${viewportLabel}] ${expected.routeId}: canonical sha256 length`,
    );
    assert.ok(
      (await officialRoot.locator("table tr").count()) >= expected.minimumRows,
      `[${viewportLabel}] ${expected.routeId}: minimum table rows`,
    );
  }

  await page.evaluate(() => window.CitizenActionDemoCanvas.navigateToRoute("home"));

  console.log(`[${viewportLabel}] mayor writing`);
  // Ensure guidance surface is active on mobile so the home control is live,
  // then bring the control into the canvas viewport without route injection.
  if (isMobileViewport(viewport)) {
    await selectMobileSurface(
      page,
      viewport,
      "guidance",
      `[${viewportLabel}] mayor entry guidance`,
    );
  }
  const mayorEntry = page.locator("#btn-open-mayor-office");
  await mayorEntry.waitFor({ state: "attached", timeout: 5000 });
  await page.evaluate(() => {
    const canvas = document.getElementById("demo-canvas");
    const btn = document.getElementById("btn-open-mayor-office");
    if (btn && typeof btn.scrollIntoView === "function") {
      btn.scrollIntoView({ block: "center", inline: "nearest" });
    }
    if (canvas && btn) {
      const c = canvas.getBoundingClientRect();
      const t = btn.getBoundingClientRect();
      if (t.bottom > c.bottom || t.top < c.top) {
        canvas.scrollTop += t.top - c.top - c.height / 3;
      }
    }
  });
  await mayorEntry.waitFor({ state: "visible", timeout: 5000 });
  // Click only if the control is actually inside the viewport.
  const mayorClickable = await page.evaluate(() => {
    const btn = document.getElementById("btn-open-mayor-office");
    if (!btn) return false;
    const r = btn.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    return r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0 && r.top < vh && r.left < vw;
  });
  assert.ok(mayorClickable, `[${viewportLabel}] #btn-open-mayor-office clickable in viewport`);
  await mayorEntry.click({ force: false });
  await page.locator(".bg-page--mayor").waitFor({ state: "visible", timeout: 5000 });
  assert.strictEqual(
    await page.locator('.bg-page--mayor [target="_blank"]').count(),
    0,
    `[${viewportLabel}] mayor page must not open target=_blank`,
  );

  const mayorMessage = page.locator('[data-action-target="mayor-message-write"], #btn-mayor-message');
  await mayorMessage.first().waitFor({ state: "visible", timeout: 5000 });
  await page.evaluate(() => {
    const btn =
      document.getElementById("btn-mayor-message") ||
      document.querySelector('[data-action-target="mayor-message-write"]');
    if (btn && typeof btn.scrollIntoView === "function") {
      btn.scrollIntoView({ block: "center", inline: "nearest" });
    }
  });
  await mayorMessage.first().click({ force: false });
  await page.locator(".bg-page--mayor-writing").waitFor({ state: "visible", timeout: 5000 });

  if (isMobileViewport(viewport)) {
    const writingSurface = await readSurfaceState(page);
    assert.strictEqual(
      writingSurface.surface,
      "guidance",
      `[${viewportLabel}] mayor writing: surface=guidance`,
    );
    assert.strictEqual(
      writingSurface.canvasAriaHidden,
      "false",
      `[${viewportLabel}] mayor writing: canvas aria-hidden=false`,
    );
    assert.strictEqual(
      writingSurface.canvasInert,
      false,
      `[${viewportLabel}] mayor writing: canvas not inert`,
    );
    assert.strictEqual(
      writingSurface.chatAriaHidden,
      "true",
      `[${viewportLabel}] mayor writing: chat aria-hidden=true`,
    );
    assert.strictEqual(
      writingSurface.chatInert,
      true,
      `[${viewportLabel}] mayor writing: chat inert`,
    );
  }

  await page.waitForFunction(
    () =>
      document.body.getAttribute("data-choreography-state") ===
      "waiting_confirmation",
    null,
    { timeout: 20000 },
  );
  console.log(`[${viewportLabel}] confirmation`);

  // Title/body live on canvas; verify while guidance is still active on mobile.
  assert.ok(
    (await page.locator("#mayor-write-title").inputValue()).includes("통학로"),
    `[${viewportLabel}] mayor title must include 통학로`,
  );
  const bodyValue = await page.locator("#mayor-write-content").inputValue();
  assert.ok(bodyValue.length > 250, `[${viewportLabel}] mayor body length > 250`);
  const lastSentenceMarker = "제출 전에 추가하겠습니다";
  assert.ok(
    bodyValue.includes(lastSentenceMarker),
    `[${viewportLabel}] last body sentence present in value`,
  );
  const bodyScroll = await page.evaluate(() => {
    const el = document.getElementById("mayor-write-content");
    if (!el) return null;
    return {
      scrollTop: el.scrollTop,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
      atBottom: el.scrollTop + el.clientHeight >= el.scrollHeight - 4,
    };
  });
  assert.ok(bodyScroll, `[${viewportLabel}] mayor textarea exists`);
  if (bodyScroll.scrollHeight > bodyScroll.clientHeight + 2) {
    assert.ok(
      bodyScroll.atBottom,
      `[${viewportLabel}] textarea scrolled to bottom after typing: ${JSON.stringify(bodyScroll)}`,
    );
  }

  // Confirmation controls live in chat; mobile must switch to conversation.
  await selectMobileSurface(
    page,
    viewport,
    "conversation",
    `[${viewportLabel}] confirmation review`,
  );

  const confirm = page.locator(".chat-decision__button--primary");
  assert.strictEqual(
    await confirm.count(),
    1,
    `[${viewportLabel}] confirmation primary button count`,
  );
  const baseShadow = await confirm.evaluate(
    (element) => getComputedStyle(element).boxShadow,
  );
  await confirm.hover();
  const hoverShadow = await confirm.evaluate(
    (element) => getComputedStyle(element).boxShadow,
  );
  assert.notStrictEqual(
    hoverShadow,
    baseShadow,
    `[${viewportLabel}] confirmation button must visibly respond to hover`,
  );
  await confirm.focus();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Shift+Tab");
  const focusOutline = await confirm.evaluate(
    (element) => getComputedStyle(element).outlineStyle,
  );
  assert.notStrictEqual(
    focusOutline,
    "none",
    `[${viewportLabel}] confirmation button must expose keyboard focus`,
  );

  await confirm.click();
  // Receipt is rendered on the canvas by product choreography after confirmation.
  await selectMobileSurface(
    page,
    viewport,
    "guidance",
    `[${viewportLabel}] receipt`,
  );
  console.log(`[${viewportLabel}] receipt`);
  await page
    .locator(".bg-page--mayor-receipt")
    .waitFor({ state: "visible", timeout: 5000 });

  // #1139: truthful pre-submit completion (no fake receipt / demo copy)
  const receiptText = await page.locator(".bg-page--mayor-receipt").innerText();
  assert.ok(receiptText.includes("구정 제안서가 작성되었습니다"), `[${viewportLabel}] receipt title`);
  assert.ok(receiptText.includes("공식 제출 전"), `[${viewportLabel}] pre-submit status`);
  assert.ok(receiptText.includes("공식 채널에서 확인 및 제출"), `[${viewportLabel}] official handoff`);
  for (const banned of ["시연용", "DEMO-", "PoC", "접수 완료"]) {
    assert.ok(!receiptText.includes(banned), `[${viewportLabel}] banned copy: ${banned}`);
  }

  if (isMobileViewport(viewport)) {
    const receiptSurface = await readSurfaceState(page);
    assert.strictEqual(
      receiptSurface.surface,
      "guidance",
      `[${viewportLabel}] receipt: surface=guidance`,
    );
    assert.strictEqual(
      receiptSurface.canvasAriaHidden,
      "false",
      `[${viewportLabel}] receipt: canvas aria-hidden=false`,
    );
    assert.strictEqual(
      receiptSurface.canvasInert,
      false,
      `[${viewportLabel}] receipt: canvas not inert`,
    );
    assert.strictEqual(
      receiptSurface.chatAriaHidden,
      "true",
      `[${viewportLabel}] receipt: chat aria-hidden=true`,
    );
    assert.strictEqual(
      receiptSurface.chatInert,
      true,
      `[${viewportLabel}] receipt: chat inert`,
    );
  }

  assert.strictEqual(
    await page.locator('[target="_blank"]').count(),
    0,
    `[${viewportLabel}] no target=_blank after receipt`,
  );
  assert.strictEqual(popups.length, 0, `[${viewportLabel}] popups must be 0`);
  assert.deepStrictEqual(
    externalRequests,
    [],
    `[${viewportLabel}] external requests must be empty`,
  );
  assert.deepStrictEqual(errors, [], `[${viewportLabel}] console/page errors must be empty`);

  const geometry = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  assert.ok(
    geometry.scrollWidth <= geometry.clientWidth,
    `horizontal overflow at ${viewport.width}px`,
  );
  await context.close();
  console.log(`[${viewportLabel}] mayor E2E PASS`);
}

function isDefaultBrowserLinkBlue(color) {
  return color === "rgb(0, 0, 238)" || color === "#0000ee" || color === "blue";
}

async function assertActionVisibleInChat(page, label) {
  const action = page.locator(".chat-decision__button--primary").first();
  await action.waitFor({ state: "visible", timeout: 15000 });
  const visible = await action.evaluate((el) => {
    const thread = document.getElementById("chat-thread");
    if (!thread) return { ok: false, reason: "no-thread" };
    const t = thread.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    const inBounds =
      r.top >= t.top - 2 &&
      r.bottom <= t.bottom + 2 &&
      r.left >= t.left - 2 &&
      r.right <= t.right + 2;
    return {
      ok:
        inBounds &&
        style.visibility !== "hidden" &&
        style.display !== "none" &&
        r.height > 0 &&
        r.width > 0,
      top: r.top,
      bottom: r.bottom,
      threadTop: t.top,
      threadBottom: t.bottom,
    };
  });
  assert.ok(visible.ok, `${label}: confirmation action must be fully inside chat-thread ${JSON.stringify(visible)}`);
}

async function runNormalMotionMayorChipFlow(browser) {
  const viewport = { width: 1440, height: 900 };
  const label = "normal-motion-mayor-chip";
  console.log(`[${label}] start`);
  const context = await browser.newContext({
    viewport,
    reducedMotion: "no-preference",
  });
  const page = await context.newPage();
  const errors = [];
  const externalRequests = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("request", (request) => {
    const url = request.url();
    if (!url.startsWith("data:") && new URL(url).origin !== BASE_ORIGIN) {
      externalRequests.push(url);
    }
  });
  await page.route("**/api/mvp/ask", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        ok: true,
        answer: "구청장 제안 작성을 안내합니다.",
        action: "mayor_message_assist",
        confidence: 1,
        failure_code: "",
      }),
    });
  });

  await page.goto(`${BASE_ORIGIN}/mvp/`, { waitUntil: "networkidle", timeout: 20000 });

  // Hover control contract on entry
  const mayorControl = page.locator("#mayor-open-office-control");
  await mayorControl.waitFor({ state: "attached", timeout: 5000 });
  const controlMeta = await mayorControl.evaluate((el) => {
    const cs = getComputedStyle(el);
    return {
      text: (el.textContent || "").trim(),
      aria: el.getAttribute("aria-label") || "",
      title: el.getAttribute("title"),
      bg: cs.backgroundColor,
      cursor: cs.cursor,
    };
  });
  assert.strictEqual(controlMeta.text, "", `[${label}] hover control has no visible text`);
  assert.ok(controlMeta.aria.includes("열린구청장실"), `[${label}] aria-label present`);
  assert.ok(!controlMeta.title, `[${label}] no title tooltip`);
  assert.ok(
    controlMeta.bg === "rgba(0, 0, 0, 0)" || controlMeta.bg === "transparent",
    `[${label}] no filled hover background by default`,
  );

  // Start from chip — do not click left hero or force navigate.
  const mayorChip = page.locator(".chat-chip--mayor-primary").first();
  await mayorChip.click();
  await page.getByRole("button", { name: "예, 안내해 주세요" }).click();

  const routes = [];
  await page.exposeFunction("__recordRoute", (id) => {
    routes.push(id);
  });
  await page.evaluate(() => {
    const api = window.CitizenActionDemoCanvas;
    if (!api || !api.navigateToRoute || api.__routeProbeWrapped) return;
    const original = api.navigateToRoute.bind(api);
    // wrap via redefine if frozen object methods still callable
    const wrapped = function (routeId) {
      try {
        window.__recordRoute(String(routeId || ""));
      } catch (_) {}
      return original(routeId);
    };
    try {
      Object.defineProperty(api, "navigateToRoute", { value: wrapped });
      api.__routeProbeWrapped = true;
    } catch (_) {
      /* frozen API — fall back to polling getCurrentRouteId */
    }
  });

  // Poll route order while AI choreography drives the left surface.
  const seen = new Set();
  const order = [];
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    const routeId = await page.evaluate(() =>
      window.CitizenActionDemoCanvas && window.CitizenActionDemoCanvas.getCurrentRouteId
        ? window.CitizenActionDemoCanvas.getCurrentRouteId()
        : "",
    );
    if (routeId && !seen.has(routeId)) {
      seen.add(routeId);
      order.push(routeId);
      console.log(`[${label}] route`, routeId);
    }
    // Intermediate DOM presence
    if (routeId === "mayor-office") {
      await page.locator(".bg-page--mayor").first().waitFor({ state: "attached", timeout: 3000 }).catch(() => {});
      const heading = await page.locator(".bg-mayor-hero h1").innerText().catch(() => "");
      assert.ok(heading.includes("참여로 실현하는"), `[${label}] heading phrase 1`);
      assert.ok(heading.includes("주민주권 도시"), `[${label}] heading phrase 2`);
      assert.ok(!/^\s*는\s*$/m.test(heading), `[${label}] no isolated 는 line`);
      const spans = await page.locator(".bg-mayor-hero h1 > span").count();
      assert.ok(spans >= 2, `[${label}] heading uses phrase spans`);
    }
    if (routeId === "mayor-complaint-write") {
      await page.locator(".bg-page--mayor-writing, #mayor-write-title").first().waitFor({
        state: "attached",
        timeout: 3000,
      }).catch(() => {});
    }
    const waiting = await page.evaluate(
      () => document.body.getAttribute("data-choreography-state") === "waiting_confirmation",
    );
    if (waiting) break;
    await page.waitForTimeout(400);
  }

  assert.ok(order.includes("mayor-office"), `[${label}] visited mayor-office: ${order.join(">")}`);
  assert.ok(
    order.includes("mayor-complaint-write"),
    `[${label}] visited mayor-complaint-write: ${order.join(">")}`,
  );

  // Do not hide clipping with test scrollIntoView.
  await assertActionVisibleInChat(page, label);

  // Left confirmation section must already be revealed by product after typing.
  const leftConfirmVisible = await page.evaluate(() => {
    const canvas = document.getElementById("demo-canvas");
    const target =
      (canvas && canvas.querySelector(".bg-writing-consent")) ||
      (canvas && canvas.querySelector(".bg-writing-actions"));
    if (!canvas || !target) return false;
    const c = canvas.getBoundingClientRect();
    const t = target.getBoundingClientRect();
    return t.top < c.bottom && t.bottom > c.top;
  });
  assert.ok(leftConfirmVisible, `[${label}] left writing confirmation section visible without test scroll`);

  await page.locator(".chat-decision__button--primary").first().click();
  await page.locator(".bg-page--mayor-receipt").waitFor({ state: "visible", timeout: 20000 });
  const receiptRoute = await page.evaluate(() =>
    window.CitizenActionDemoCanvas.getCurrentRouteId(),
  );
  assert.strictEqual(receiptRoute, "mayor-complaint-receipt", `[${label}] receipt route`);

  const chatText = await page.locator("#chat-thread").innerText();
  for (const banned of ["시연용", "PoC", "DEMO-", "접수 완료", "접수되었습니다"]) {
    assert.ok(!chatText.includes(banned), `[${label}] chat banned: ${banned}`);
  }
  const receiptText = await page.locator(".bg-page--mayor-receipt").innerText();
  assert.ok(receiptText.includes("구정 제안서가 작성되었습니다"), `[${label}] receipt title`);
  assert.ok(receiptText.includes("공식 제출 전"), `[${label}] pre-submit`);
  assert.ok(receiptText.includes("공식 채널에서 확인 및 제출"), `[${label}] official handoff`);

  const geometry = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  assert.ok(geometry.scrollWidth <= geometry.clientWidth + 1, `[${label}] no horizontal overflow`);
  assert.deepStrictEqual(externalRequests, [], `[${label}] no external requests`);
  assert.deepStrictEqual(errors, [], `[${label}] no browser errors: ${errors.join(" | ")}`);

  await context.close();
  console.log(`[${label}] PASS`);
}

async function runStreetlightWriteHeaderFlow(browser) {
  const label = "streetlight-write-header";
  console.log(`[${label}] start`);
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const errors = [];
  const externalRequests = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("request", (request) => {
    const url = request.url();
    if (!url.startsWith("data:") && new URL(url).origin !== BASE_ORIGIN) {
      externalRequests.push(url);
    }
  });
  await page.route("**/api/mvp/ask", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        ok: true,
        answer: "가로등 고장 신고 경로를 안내합니다.",
        action: "streetlight_report",
        confidence: 1,
        failure_code: "",
      }),
    });
  });

  await page.goto(`${BASE_ORIGIN}/mvp/`, { waitUntil: "networkidle", timeout: 20000 });
  await page.getByRole("button", { name: "가로등 고장 신고 (AI 도움)", exact: true }).click();
  await page.getByRole("button", { name: "예, 안내해 주세요" }).click();

  await page.waitForFunction(
    () =>
      window.CitizenActionDemoCanvas &&
      window.CitizenActionDemoCanvas.getCurrentRouteId &&
      window.CitizenActionDemoCanvas.getCurrentRouteId() === "complaint-write",
    null,
    { timeout: 25000 },
  );

  const headerProbe = await page.evaluate(() => {
    const pageRoot = document.querySelector(".bg-page--product.bg-page--writing, .bg-page--writing, .bg-page--product");
    const utility = document.querySelector(".bg-home-utility");
    const header = document.querySelector(".bg-home-header");
    const gnb = document.querySelector(".bg-home-gnb");
    const footer = document.querySelector(".bg-home-footer");
    const consent = document.querySelector(".bg-writing-consent");
    const links = gnb ? [...gnb.querySelectorAll("a")] : [];
    function style(el) {
      if (!el) return null;
      const cs = getComputedStyle(el);
      return {
        display: cs.display,
        color: cs.color,
        background: cs.backgroundColor,
        textDecoration: cs.textDecorationLine || cs.textDecoration,
        height: cs.height,
        justifyContent: cs.justifyContent,
      };
    }
    const linkBoxes = links.map((a) => {
      const r = a.getBoundingClientRect();
      const cs = getComputedStyle(a);
      return {
        text: (a.textContent || "").trim(),
        w: r.width,
        h: r.height,
        x: r.x,
        color: cs.color,
        decoration: cs.textDecorationLine || cs.textDecoration,
        display: cs.display,
      };
    });
    return {
      hasProduct: !!(pageRoot && pageRoot.classList.contains("bg-page--product")),
      utility: style(utility),
      header: style(header),
      gnb: style(gnb),
      linkBoxes,
      footer: style(footer),
      consentPresent: !!consent,
    };
  });

  assert.ok(headerProbe.hasProduct, `[${label}] writing page uses product class`);
  assert.ok(headerProbe.utility && headerProbe.utility.display !== "none", `[${label}] utility styled present`);
  assert.ok(headerProbe.header && headerProbe.header.background !== "rgba(0, 0, 0, 0)", `[${label}] header has surface`);
  assert.ok(headerProbe.gnb && headerProbe.gnb.display === "flex", `[${label}] gnb is flex layout`);
  assert.ok(headerProbe.linkBoxes.length >= 4, `[${label}] gnb has multiple links`);
  // Styled nav: each item is a laid-out box with non-default link chrome.
  for (const link of headerProbe.linkBoxes) {
    assert.ok(link.w > 20 && link.h > 10, `[${label}] gnb link has box: ${link.text}`);
    assert.ok(
      !String(link.decoration).includes("underline"),
      `[${label}] gnb link not underlined: ${link.text}`,
    );
    assert.ok(
      !isDefaultBrowserLinkBlue(link.color),
      `[${label}] gnb link not default blue: ${link.text} (${link.color})`,
    );
  }
  // Links are horizontally spaced (not one collapsed inline blob).
  if (headerProbe.linkBoxes.length >= 2) {
    const xs = headerProbe.linkBoxes.map((l) => l.x).sort((a, b) => a - b);
    let spaced = 0;
    for (let i = 1; i < xs.length; i++) {
      if (xs[i] - xs[i - 1] > 8) spaced += 1;
    }
    assert.ok(spaced >= 2, `[${label}] gnb links spatially separated`);
  }
  assert.ok(headerProbe.footer && headerProbe.footer.display !== "none", `[${label}] footer present`);

  // Wait for confirmation / typing complete at reduced motion (fast).
  await page.waitForFunction(
    () => document.body.getAttribute("data-choreography-state") === "waiting_confirmation",
    null,
    { timeout: 20000 },
  );
  const confirmVisible = await page.evaluate(() => {
    const canvas = document.getElementById("demo-canvas");
    const target =
      (canvas && canvas.querySelector(".bg-writing-consent")) ||
      (canvas && canvas.querySelector(".bg-writing-actions"));
    if (!canvas || !target) return false;
    const c = canvas.getBoundingClientRect();
    const t = target.getBoundingClientRect();
    return t.top < c.bottom && t.bottom > c.top && t.height > 0;
  });
  assert.ok(confirmVisible, `[${label}] left confirmation visible without test scroll`);

  const geometry = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  assert.ok(geometry.scrollWidth <= geometry.clientWidth + 1, `[${label}] no horizontal overflow`);
  assert.deepStrictEqual(externalRequests, [], `[${label}] no external requests`);
  assert.deepStrictEqual(errors, [], `[${label}] no browser errors`);

  await context.close();
  console.log(`[${label}] PASS`);
}

async function runVietnameseMayorChipFlow(browser) {
  const label = "vietnamese-mayor-chip";
  console.log(`[${label}] start`);
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    reducedMotion: "no-preference",
  });
  const page = await context.newPage();
  const errors = [];
  const externalRequests = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("request", (request) => {
    const url = request.url();
    if (!url.startsWith("data:") && new URL(url).origin !== BASE_ORIGIN) {
      externalRequests.push(url);
    }
  });
  await page.route("**/api/mvp/ask", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        ok: true,
        answer: "구청장 제안 작성을 안내합니다.",
        action: "mayor_message_assist",
        confidence: 1,
        failure_code: "",
      }),
    });
  });

  await page.goto(`${BASE_ORIGIN}/mvp/?lang=vi`, {
    waitUntil: "networkidle",
    timeout: 20000,
  });

  // Shell language contract
  const shellTitle = page.locator(".chat-shell__title");
  await shellTitle.waitFor({ state: "visible", timeout: 5000 });
  assert.strictEqual(await shellTitle.innerText(), "BUKGU AI CIVIC NAVIGATOR", `[${label}] shell title`);

  const langSelect = page.locator("#chat-lang");
  assert.strictEqual(await langSelect.inputValue(), "vi", `[${label}] lang selector value`);

  // Chip shows Vietnamese text
  const viMayorChip = page.locator(".chat-chip--mayor-primary").first();
  await viMayorChip.waitFor({ state: "visible", timeout: 5000 });
  const chipText = await viMayorChip.innerText();
  assert.ok(chipText.includes("gửi đề xuất"), `[${label}] chip text Vietnamese: ${chipText}`);

  // Start journey from chip
  await viMayorChip.click();
  await page.getByRole("button", { name: "Vâng, hãy hướng dẫn tôi", exact: true }).click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-first-use-state") === "split",
    null,
    { timeout: 10000 },
  );

  // Verify welcome message in Vietnamese
  const chatThread = page.locator("#chat-thread");
  const threadText = await chatThread.innerText();
  assert.ok(threadText.includes("Xin chào"), `[${label}] thread contains Vietnamese AI greeting: ${threadText.substring(0, 100)}`);

  // #1152: poll through Stage 1 (resident draft) before form population.
  const order = [];
  const seen = new Set();
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    const routeId = await page.evaluate(() =>
      window.CitizenActionDemoCanvas && window.CitizenActionDemoCanvas.getCurrentRouteId
        ? window.CitizenActionDemoCanvas.getCurrentRouteId()
        : "",
    );
    if (routeId && !seen.has(routeId)) {
      seen.add(routeId);
      order.push(routeId);
      console.log(`[${label}] route`, routeId);
    }
    const waitingResident = await page.evaluate(
      () =>
        document.body.getAttribute("data-choreography-state") === "waiting_resident_draft" ||
        document.body.getAttribute("data-draft-stage") === "resident_draft_review",
    );
    if (waitingResident) break;
    await page.waitForTimeout(400);
  }

  assert.ok(order.includes("mayor-office"), `[${label}] visited mayor-office: ${order.join(">")}`);
  assert.ok(
    order.includes("mayor-complaint-write"),
    `[${label}] visited mayor-complaint-write: ${order.join(">")}`,
  );

  // Stage 1: form still empty; Korean draft absent (DOM + internal state).
  const stage1 = await page.evaluate(() => {
    const title = document.getElementById("mayor-write-title");
    const body = document.getElementById("mayor-write-content");
    const draft =
      window.CitizenFirstChoreography &&
      window.CitizenFirstChoreography.getDraftStageState
        ? window.CitizenFirstChoreography.getDraftStageState()
        : null;
    return {
      draftStage: document.body.getAttribute("data-draft-stage"),
      choreo: document.body.getAttribute("data-choreography-state"),
      title: title ? title.value : "",
      body: body ? body.value : "",
      koreanCard: !!document.querySelector(
        '[data-bilingual-draft-card="stage2"], [data-draft-role="korean-administrative-draft"]',
      ),
      residentCard: !!document.querySelector(
        '[data-bilingual-draft-card="stage1"], [data-draft-field="resident-title"]',
      ),
      koreanTitle: draft ? draft.koreanTitle : null,
      koreanBody: draft ? draft.koreanBody : null,
    };
  });
  assert.strictEqual(stage1.draftStage, "resident_draft_review", `[${label}] Stage 1 draft stage`);
  assert.strictEqual(stage1.title, "", `[${label}] Stage 1 form title empty`);
  assert.strictEqual(stage1.body, "", `[${label}] Stage 1 form body empty`);
  assert.equal(stage1.koreanCard, false, `[${label}] Stage 1 Korean draft absent`);
  assert.ok(stage1.residentCard, `[${label}] Stage 1 resident draft card visible`);
  assert.strictEqual(stage1.koreanTitle, "", `[${label}] Stage 1 internal koreanTitle empty`);
  assert.strictEqual(stage1.koreanBody, "", `[${label}] Stage 1 internal koreanBody empty`);

  // Confirm the reviewed Vietnamese sample (not free-form) → Stage 2.
  const stage1Confirm = page.locator('[data-draft-action="confirm-content"]');
  await stage1Confirm.waitFor({ state: "visible", timeout: 5000 });
  const stage1BtnText = await stage1Confirm.innerText();
  assert.ok(
    stage1BtnText.includes("ý nghĩa") || stage1BtnText.includes("đúng"),
    `[${label}] Stage 1 confirm Vietnamese: ${stage1BtnText}`,
  );
  await stage1Confirm.click();

  await page.waitForFunction(
    () =>
      document.body.getAttribute("data-draft-stage") === "korean_draft_review" ||
      document.body.getAttribute("data-choreography-state") === "waiting_korean_draft",
    null,
    { timeout: 10000 },
  );

  // Stage 2: both drafts visible; form still empty.
  const stage2 = await page.evaluate(() => {
    const i18n = window.CitizenI18n;
    const originalExpected = i18n.t("draft.originalResidentMessage");
    const koreanExpected = i18n.t("draft.koreanAdministrativeDraft");
    const originalNode = document.querySelector(
      '[data-draft-role="original-resident"] [data-draft-label], [data-draft-role="original-resident"] .chat-draft-label',
    );
    const koreanNode = document.querySelector(
      '[data-draft-role="korean-administrative-draft"] [data-draft-label], [data-draft-role="korean-administrative-draft"] .chat-draft-label',
    );
    const originalText = document.querySelector(
      '[data-draft-role="original-resident"] [data-draft-original-text], [data-draft-role="original-resident"] .chat-draft-body',
    );
    const koreanBody = document.querySelector(
      '[data-draft-role="korean-administrative-draft"] [data-draft-korean-body], [data-draft-role="korean-administrative-draft"] .chat-draft-body',
    );
    const title = document.getElementById("mayor-write-title");
    const body = document.getElementById("mayor-write-content");
    return {
      originalExpected,
      koreanExpected,
      originalLabelText: originalNode ? originalNode.textContent.trim() : "",
      koreanLabelText: koreanNode ? koreanNode.textContent.trim() : "",
      originalBody: originalText ? originalText.textContent.trim() : "",
      koreanDraftBody: koreanBody ? koreanBody.textContent.trim() : "",
      title: title ? title.value : "",
      body: body ? body.value : "",
      draftStage: document.body.getAttribute("data-draft-stage"),
    };
  });
  assert.strictEqual(stage2.draftStage, "korean_draft_review", `[${label}] Stage 2 draft stage`);
  assert.strictEqual(stage2.title, "", `[${label}] Stage 2 form title still empty`);
  assert.strictEqual(stage2.body, "", `[${label}] Stage 2 form body still empty`);
  assert.ok(stage2.originalExpected, `[${label}] registry original label exists`);
  assert.ok(stage2.koreanExpected, `[${label}] registry korean draft label exists`);
  assert.strictEqual(
    stage2.originalLabelText,
    stage2.originalExpected,
    `[${label}] original-language label visible from registry`,
  );
  assert.strictEqual(
    stage2.koreanLabelText,
    stage2.koreanExpected,
    `[${label}] Korean administrative draft label visible from registry`,
  );
  assert.ok(stage2.originalBody.length > 10, `[${label}] original resident text visible`);
  assert.ok(
    stage2.koreanDraftBody.includes("제출 전에 추가하겠습니다") ||
      stage2.koreanDraftBody.includes("통학"),
    `[${label}] matching Korean draft body for reviewed fixture`,
  );

  const insertBtn = page.locator('[data-draft-action="confirm-insert"]');
  await insertBtn.waitFor({ state: "visible", timeout: 5000 });
  await insertBtn.click();

  // After second confirmation: form receives Korean title/body; terminal pre-submit.
  await page.waitForFunction(
    () => {
      const title = document.getElementById("mayor-write-title");
      const body = document.getElementById("mayor-write-content");
      const choreo = document.body.getAttribute("data-choreography-state");
      return (
        title &&
        body &&
        title.value.includes("통학로") &&
        body.value.length > 20 &&
        choreo === "waiting_form_review"
      );
    },
    null,
    { timeout: 10000 },
  );
  await page.waitForTimeout(600);

  const afterInsert = await page.evaluate(() => {
    const title = document.getElementById("mayor-write-title");
    const body = document.getElementById("mayor-write-content");
    const submit = document.getElementById("btn-mayor-submit");
    const submitConfirms = Array.from(
      document.querySelectorAll(".chat-msg--decision .chat-decision__button--primary"),
    ).filter((btn) => /Đã xem xét|Reviewed, submit|검토했고/.test((btn.textContent || "").trim()));
    return {
      draftStage: document.body.getAttribute("data-draft-stage"),
      choreo: document.body.getAttribute("data-choreography-state"),
      title: title ? title.value : "",
      body: body ? body.value : "",
      titleEditable: title ? !title.disabled && !title.readOnly : false,
      bodyEditable: body ? !body.disabled && !body.readOnly : false,
      submitDisabled: submit ? submit.disabled : null,
      hasReceipt: !!document.querySelector(".bg-page--mayor-receipt"),
      submitConfirmCount: submitConfirms.length,
      route:
        window.CitizenActionDemoCanvas && window.CitizenActionDemoCanvas.getCurrentRouteId
          ? window.CitizenActionDemoCanvas.getCurrentRouteId()
          : "",
    };
  });
  assert.strictEqual(afterInsert.draftStage, "form_populated", `[${label}] form_populated`);
  assert.strictEqual(afterInsert.choreo, "waiting_form_review", `[${label}] waiting_form_review`);
  assert.ok(
    afterInsert.title.includes("통학로") || afterInsert.title.length > 5,
    `[${label}] Korean title populated after second confirm`,
  );
  assert.ok(afterInsert.body.length > 20, `[${label}] Korean body populated after second confirm`);
  assert.ok(afterInsert.titleEditable, `[${label}] title remains editable`);
  assert.ok(afterInsert.bodyEditable, `[${label}] body remains editable`);
  assert.equal(afterInsert.hasReceipt, false, `[${label}] no receipt on form insert`);
  assert.ok(afterInsert.submitDisabled === true, `[${label}] submit remains disabled after insert`);
  assert.strictEqual(afterInsert.submitConfirmCount, 0, `[${label}] no legacy submit confirmation`);
  assert.notEqual(afterInsert.route, "mayor-complaint-receipt", `[${label}] not on receipt route`);

  const bannedTranslationClaims = ["공식 번역", "공인 통역", "official translation", "certified interpreter"];
  const pageText = await page.locator("body").innerText();
  for (const banned of bannedTranslationClaims) {
    assert.ok(!pageText.includes(banned), `[${label}] banned claim: ${banned}`);
  }
  assert.ok(!pageText.includes("Đã xem xét, gửi đi"), `[${label}] no Vietnamese submit CTA`);

  // No banned completed-submission claims in chat
  const finalChatText = await chatThread.innerText();
  for (const banned of ["시연용", "PoC", "DEMO-", "접수 완료", "접수되었습니다"]) {
    assert.ok(!finalChatText.includes(banned), `[${label}] chat banned: ${banned}`);
  }

  assert.deepStrictEqual(externalRequests, [], `[${label}] no external requests`);
  assert.deepStrictEqual(errors, [], `[${label}] no browser errors: ${errors.join(" | ")}`);

  await context.close();
  console.log(`[${label}] PASS`);
}

async function main() {
  const browser = await launchBrowser();
  try {
    // Desktop + both mobile contracts: product target 390×844 and the
    // existing locked 375×812 reduced-motion suite.
    await runViewport(browser, { width: 1440, height: 900 });
    await runViewport(browser, { width: 390, height: 844 });
    await runViewport(browser, { width: 375, height: 812 });
    await runNormalMotionMayorChipFlow(browser);
    await runStreetlightWriteHeaderFlow(browser);
    // #1143: Vietnamese mayor flow (i18n).
    await runVietnameseMayorChipFlow(browser);
  } finally {
    await browser.close();
  }
  console.log(
    "Mayor writing E2E passed (1440 + 390 + 375 + normal-motion + streetlight write + Vietnamese).",
  );
}

main().catch((error) => {
  console.error("Mayor writing E2E FAILED:");
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
