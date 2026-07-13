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
  const mayorEntry = page.locator("#btn-open-mayor-office");
  await mayorEntry.waitFor({ state: "visible", timeout: 5000 });
  await mayorEntry.click();
  await page.locator(".bg-page--mayor").waitFor({ state: "visible", timeout: 5000 });
  assert.strictEqual(
    await page.locator('.bg-page--mayor [target="_blank"]').count(),
    0,
    `[${viewportLabel}] mayor page must not open target=_blank`,
  );

  await page.locator('[data-action-target="mayor-message-write"]').click();
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
  assert.ok(
    (await page.locator("#mayor-write-content").inputValue()).length > 250,
    `[${viewportLabel}] mayor body length > 250`,
  );

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

async function main() {
  const browser = await launchBrowser();
  try {
    await runViewport(browser, { width: 1440, height: 900 });
    await runViewport(browser, { width: 390, height: 844 });
  } finally {
    await browser.close();
  }
  console.log("Mayor writing E2E passed at 1440x900 and 390x844.");
}

main().catch((error) => {
  console.error("Mayor writing E2E FAILED:");
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
