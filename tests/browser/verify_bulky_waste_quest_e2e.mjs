/**
 * Browser E2E verifier for #984 bulky_waste_disposal_guidance real-page fidelity.
 *
 * Usage:
 *   node tests/browser/verify_bulky_waste_quest_e2e.mjs http://127.0.0.1:<port>
 *
 * Screenshots:
 *   /tmp/400-ai-finder-984/bulky-waste-quest-e2e.png
 */

import assert from "assert";
import { mkdirSync } from "fs";
import { join } from "path";
import { chromium } from "playwright";

const requestedBase = process.argv[2] || "http://127.0.0.1:8080";
const SCREENSHOT_DIR = "/tmp/400-ai-finder-984";
mkdirSync(SCREENSHOT_DIR, { recursive: true });

function validateOrigin(raw) {
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(`Invalid URL: ${raw}`);
  }
  const hostname = parsed.hostname.replace(/^\[|\]$/g, "");
  const allowedHosts = new Set(["127.0.0.1", "localhost", "::1"]);
  if (parsed.protocol !== "http:") throw new Error("Only local http:// is allowed.");
  if (!allowedHosts.has(hostname)) throw new Error(`Non-local host rejected: ${parsed.hostname}`);
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error("Credentials, query, and hash are not allowed in baseUrl.");
  }
  return parsed.origin;
}

const BASE_ORIGIN = validateOrigin(requestedBase);
const MVP_URL = `${BASE_ORIGIN}/mvp`;

function isLocalRequest(url) {
  if (url.startsWith("data:")) return true;
  try {
    return new URL(url).origin === BASE_ORIGIN;
  } catch {
    return false;
  }
}

async function waitForText(page, selector, text, timeout = 10000) {
  await page.waitForFunction(
    ({ selector, text }) => {
      const el = document.querySelector(selector);
      return el && el.textContent && el.textContent.includes(text);
    },
    { selector, text },
    { timeout },
  );
}

async function main() {
  const requests = [];
  const errors = [];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1366, height: 900 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  page.on("request", (request) => requests.push(request.url()));
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  await page.goto(MVP_URL, { waitUntil: "networkidle", timeout: 15000 });
  assert.strictEqual(await page.getAttribute("body", "data-first-use-state"), "entry");

  await page.fill("#chat-composer-input", "침대 매트리스 버리고 싶어요");
  await page.click("#chat-composer-send");

  await page.waitForFunction(
    () => document.body.getAttribute("data-quest-id") === "bulky_waste_disposal_guidance",
    null,
    { timeout: 10000 },
  );
  assert.strictEqual(await page.getAttribute("body", "data-quest-match-status"), "matched");
  assert.strictEqual(await page.getAttribute("body", "data-quest-stop-condition"), "STOP_FOR_USER_CONFIRMATION");
  assert.strictEqual(await page.getAttribute("body", "data-quest-source-mode"), "local_static");

  await page.waitForFunction(
    () => document.body.getAttribute("data-first-use-state") === "split",
    null,
    { timeout: 10000 },
  );
  await page.waitForFunction(
    () => document.body.getAttribute("data-choreography-state") === "done",
    null,
    { timeout: 12000 },
  );

  await waitForText(page, "#demo-canvas", "대형폐기물 배출방법");
  await waitForText(page, "#demo-canvas", "재활용");
  await waitForText(page, "#demo-canvas", "수탁업체(녹색환경)");
  await waitForText(page, "#demo-canvas", "062-572-1336, 1337");
  await waitForText(page, "#demo-canvas", "여기로");
  await waitForText(page, "#demo-canvas", "인터넷 배출하기");
  await waitForText(page, "#demo-canvas", "수수료 납부 방법");
  await waitForText(page, "#demo-canvas", "배출변경");
  await waitForText(page, "#demo-canvas", "폐가전");
  await waitForText(page, "#chat-thread", "대형폐기물 배출방법 안내");
  await waitForText(page, "#chat-thread", "bulky_waste_disposal_guidance");
  await waitForText(page, "#chat-thread", "북구청 홈 > 분야별정보 > 환경재활용 > 대형폐기물 배출방법");
  await waitForText(page, "#chat-thread", "대형폐기물 배출방법 안내 / 대형폐기물 배출방법 안내");
  await waitForText(page, "#chat-thread", "STOP_FOR_USER_CONFIRMATION");
  await waitForText(page, "#chat-thread", "local_static");
  await waitForText(page, "#chat-thread", "품목 선택");
  await waitForText(page, "#chat-thread", "수수료 결제");
  await waitForText(page, "#chat-thread", "배출번호 발급");

  const evidence = await page.evaluate(() => {
    const card = document.querySelector("#chat-thread .chat-quest-card");
    const routeId = window.CitizenActionDemoCanvas
      ? window.CitizenActionDemoCanvas.getCurrentRouteId()
      : "";
    const target = window.CitizenActionDemoCanvas
      ? window.CitizenActionDemoCanvas.getTargetElement("bulky-waste-guidance-card")
      : null;
    return {
      routeId,
      targetVisible: Boolean(target),
      canvasText: document.querySelector("#demo-canvas")?.textContent || "",
      card: card ? {
        questCardType: card.getAttribute("data-quest-card"),
        questId: card.getAttribute("data-quest-id"),
        sourceMode: card.getAttribute("data-source-mode"),
        actionLabels: Array.from(card.querySelectorAll(".chat-quest-card__action")).map((node) => node.textContent.trim()),
        text: card.textContent,
      } : null,
    };
  });
  assert.strictEqual(evidence.routeId, "bulky-waste-disposal");
  assert.strictEqual(evidence.targetVisible, true);
  assert.ok(!evidence.canvasText.includes("청원24"), "bulky waste route must not render Cheongwon24");
  assert.ok(evidence.card, "quest card must exist in the right panel");
  assert.strictEqual(evidence.card.questCardType, "action_plan");
  assert.strictEqual(evidence.card.questId, "bulky_waste_disposal_guidance");
  assert.strictEqual(evidence.card.sourceMode, "local_static");
  assert.ok(evidence.card.actionLabels.length >= 2, `expected at least 2 action labels, got ${evidence.card.actionLabels.length}`);
  assert.ok(evidence.card.actionLabels.includes("대형폐기물 배출방법 화면 이동"));
  assert.ok(evidence.card.actionLabels.includes("대형폐기물 배출방법 안내 확인"));
  assert.ok(evidence.card.text.includes("STOP_FOR_USER_CONFIRMATION"));

  const nonLocal = requests.filter((url) => !isLocalRequest(url));
  assert.deepStrictEqual(nonLocal, [], `non-local requests: ${nonLocal.join(", ")}`);
  assert.deepStrictEqual(errors, [], `browser errors: ${errors.join("\n")}`);

  const screenshotPath = join(SCREENSHOT_DIR, "bulky-waste-quest-e2e.png");
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await browser.close();

  console.log("Bulky waste quest E2E passed.");
  console.log(`Screenshot: ${screenshotPath}`);
}

main().catch((error) => {
  console.error("Bulky waste quest E2E FAILED:");
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
