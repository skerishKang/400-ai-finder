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

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch {
    return chromium.launch({ headless: true, channel: "chrome" });
  }
}

const BASE_ORIGIN = validateOrigin(requestedBase);

async function runViewport(browser, viewport) {
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
    if (!url.startsWith("data:") && new URL(url).origin !== BASE_ORIGIN) externalRequests.push(url);
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

  await page.goto(`${BASE_ORIGIN}/mvp/`, { waitUntil: "networkidle", timeout: 15000 });
  await page.getByRole("button", { name: "불법 주정차 신고", exact: true }).click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-first-use-state") === "split",
    null,
    { timeout: 10000 },
  );

  for (const expected of [
    { routeId: "bulky-waste-disposal", minimumRows: 160 },
    { routeId: "passport-guidance", minimumRows: 10 },
    { routeId: "unmanned-kiosk-guidance", minimumRows: 50 },
  ]) {
    await page.evaluate((routeId) => window.CitizenActionDemoCanvas.navigateToRoute(routeId), expected.routeId);
    const officialRoot = page.locator(`[data-official-route-id="${expected.routeId}"]`);
    await officialRoot.waitFor({ state: "visible", timeout: 5000 });
    assert.strictEqual((await officialRoot.getAttribute("data-canonical-sha256")).length, 64);
    assert.ok(await officialRoot.locator("table tr").count() >= expected.minimumRows);
  }
  await page.evaluate(() => window.CitizenActionDemoCanvas.navigateToRoute("home"));

  const mayorEntry = page.locator("#btn-open-mayor-office");
  await mayorEntry.waitFor({ state: "visible", timeout: 5000 });
  await mayorEntry.click();
  await page.locator(".bg-page--mayor").waitFor({ state: "visible", timeout: 5000 });
  assert.strictEqual(await page.locator('.bg-page--mayor [target="_blank"]').count(), 0);

  await page.locator('[data-action-target="mayor-message-write"]').click();
  await page.locator(".bg-page--mayor-writing").waitFor({ state: "visible", timeout: 5000 });
  await page.waitForFunction(
    () => document.body.getAttribute("data-choreography-state") === "waiting_confirmation",
    null,
    { timeout: 20000 },
  );

  assert.ok((await page.locator("#mayor-write-title").inputValue()).includes("통학로"));
  assert.ok((await page.locator("#mayor-write-content").inputValue()).length > 250);

  const confirm = page.locator(".chat-decision__button--primary");
  assert.strictEqual(await confirm.count(), 1);
  const baseShadow = await confirm.evaluate((element) => getComputedStyle(element).boxShadow);
  await confirm.hover();
  const hoverShadow = await confirm.evaluate((element) => getComputedStyle(element).boxShadow);
  assert.notStrictEqual(hoverShadow, baseShadow, "confirmation button must visibly respond to hover");
  await confirm.focus();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Shift+Tab");
  const focusOutline = await confirm.evaluate((element) => getComputedStyle(element).outlineStyle);
  assert.notStrictEqual(focusOutline, "none", "confirmation button must expose keyboard focus");

  await confirm.click();
  await page.locator(".bg-page--mayor-receipt").waitFor({ state: "visible", timeout: 5000 });
  assert.strictEqual(await page.locator('[target="_blank"]').count(), 0);
  assert.strictEqual(popups.length, 0);
  assert.deepStrictEqual(externalRequests, []);
  assert.deepStrictEqual(errors, []);

  const geometry = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  assert.ok(geometry.scrollWidth <= geometry.clientWidth, `horizontal overflow at ${viewport.width}px`);
  await context.close();
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
