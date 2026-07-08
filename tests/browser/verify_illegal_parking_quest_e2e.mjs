/**
 * Browser E2E verifier for #974 illegal_parking_report_guidance.
 *
 * Usage:
 *   node tests/browser/verify_illegal_parking_quest_e2e.mjs http://127.0.0.1:<port>
 *
 * Screenshots:
 *   /tmp/400-ai-finder-974/illegal-parking-quest-e2e.png
 */

import assert from "assert";
import { mkdirSync } from "fs";
import { join } from "path";
import { chromium } from "playwright";

const requestedBase = process.argv[2] || "http://127.0.0.1:8080";
const SCREENSHOT_DIR = "/tmp/400-ai-finder-974";
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

  await page.fill("#chat-composer-input", "불법 주정차 신고는 어디서 하나요?");
  await page.click("#chat-composer-send");

  await page.waitForFunction(
    () => document.body.getAttribute("data-quest-id") === "illegal_parking_report_guidance",
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

  await waitForText(page, "#demo-canvas", "불법 주정차 신고");
  await waitForText(page, "#demo-canvas", "민원신고 > 불법 주정차 신고");
  await waitForText(page, "#demo-canvas", "북구청 민원신고 (교통과)");
  await waitForText(page, "#chat-thread", "불법 주정차 신고 안내");
  await waitForText(page, "#chat-thread", "illegal_parking_report_guidance");
  await waitForText(page, "#chat-thread", "종합민원 > 민원신고 > 불법 주정차 신고");
  await waitForText(page, "#chat-thread", "불법 주정차 신고 / 불법 주정차 신고 카드");
  await waitForText(page, "#chat-thread", "STOP_FOR_USER_CONFIRMATION");
  await waitForText(page, "#chat-thread", "local_static");
  await waitForText(page, "#chat-thread", "본인인증");
  await waitForText(page, "#chat-thread", "차량번호");
  await waitForText(page, "#chat-thread", "위치정보");
  await waitForText(page, "#chat-thread", "첨부파일");

  const evidence = await page.evaluate(() => {
    const card = document.querySelector("#chat-thread .chat-quest-card");
    const routeId = window.CitizenActionDemoCanvas
      ? window.CitizenActionDemoCanvas.getCurrentRouteId()
      : "";
    const target = window.CitizenActionDemoCanvas
      ? window.CitizenActionDemoCanvas.getTargetElement("complaint-illegal-parking-report")
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
  assert.strictEqual(evidence.routeId, "complaint-illegal-parking");
  assert.strictEqual(evidence.targetVisible, true);
  assert.ok(!evidence.canvasText.includes("청원24"), "illegal parking route must not render Cheongwon24");
  assert.ok(evidence.card, "quest card must exist in the right panel");
  assert.strictEqual(evidence.card.questCardType, "action_plan");
  assert.strictEqual(evidence.card.questId, "illegal_parking_report_guidance");
  assert.strictEqual(evidence.card.sourceMode, "local_static");
  assert.ok(evidence.card.actionLabels.length >= 2, `expected at least 2 action labels, got ${evidence.card.actionLabels.length}`);
  assert.ok(evidence.card.actionLabels.includes("불법 주정차 신고 화면 이동"));
  assert.ok(evidence.card.actionLabels.includes("불법 주정차 신고 카드 확인"));
  assert.ok(evidence.card.text.includes("STOP_FOR_USER_CONFIRMATION"));

  const nonLocal = requests.filter((url) => !isLocalRequest(url));
  assert.deepStrictEqual(nonLocal, [], `non-local requests: ${nonLocal.join(", ")}`);
  assert.deepStrictEqual(errors, [], `browser errors: ${errors.join("\n")}`);

  const screenshotPath = join(SCREENSHOT_DIR, "illegal-parking-quest-e2e.png");
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await browser.close();

  console.log("Illegal parking quest E2E passed.");
  console.log(`Screenshot: ${screenshotPath}`);
}

main().catch((error) => {
  console.error("Illegal parking quest E2E FAILED:");
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
