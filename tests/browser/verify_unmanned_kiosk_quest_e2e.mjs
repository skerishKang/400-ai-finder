/**
 * Browser E2E verifier for #1079 unmanned_kiosk_guidance.
 *
 * Usage:
 *   node tests/browser/verify_unmanned_kiosk_quest_e2e.mjs http://127.0.0.1:<port>
 *
 * Screenshots:
 *   /tmp/400-ai-finder-1079/unmanned-kiosk-quest-e2e.png
 */

import assert from "assert";
import { mkdirSync } from "fs";
import { join } from "path";
import { chromium } from "playwright";

const requestedBase = process.argv[2] || "http://127.0.0.1:8080";
const SCREENSHOT_DIR = "/tmp/400-ai-finder-1079";
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

  await page.fill("#chat-composer-input", "무인민원발급기 어디 있어요?");
  await page.click("#chat-composer-send");

  await page.waitForFunction(
    () => document.body.getAttribute("data-quest-id") === "unmanned_kiosk_guidance",
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

  await waitForText(page, "#demo-canvas", "종합민원");
  await waitForText(page, "#demo-canvas", "무인민원발급기");
  await waitForText(page, "#chat-thread", "무인민원발급기 안내");
  await waitForText(page, "#chat-thread", "unmanned_kiosk_guidance");
  await waitForText(page, "#chat-thread", "북구청 홈 > 종합민원 > 무인민원발급기");
  await waitForText(page, "#chat-thread", "STOP_FOR_USER_CONFIRMATION");
  await waitForText(page, "#chat-thread", "local_static");
  await waitForText(page, "#chat-thread", "실제 서류 발급");
  await waitForText(page, "#chat-thread", "사용자가");
  await waitForText(page, "#chat-thread", "직접 진행");
  await waitForText(page, "#chat-thread", "본인인증");
  await waitForText(page, "#chat-thread", "무인민원발급기");

  const evidence = await page.evaluate(() => {
    const card = document.querySelector("#chat-thread .chat-quest-card");
    const routeId = window.CitizenActionDemoCanvas
      ? window.CitizenActionDemoCanvas.getCurrentRouteId()
      : "";
    const target = window.CitizenActionDemoCanvas
      ? window.CitizenActionDemoCanvas.getTargetElement("unmanned-kiosk-card")
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
  assert.strictEqual(evidence.routeId, "unmanned-kiosk-guidance");
  assert.strictEqual(evidence.targetVisible, true);
  assert.ok(evidence.card, "quest card must exist in the right panel");
  assert.strictEqual(evidence.card.questCardType, "action_plan");
  assert.strictEqual(evidence.card.questId, "unmanned_kiosk_guidance");
  assert.strictEqual(evidence.card.sourceMode, "local_static");
  assert.strictEqual(evidence.card.actionLabels.length, 4, `expected exactly 4 action labels, got ${evidence.card.actionLabels.length}`);
  assert.strictEqual(evidence.card.actionLabels[0], "종합민원 메뉴 확인");
  assert.strictEqual(evidence.card.actionLabels[1], "무인민원발급기 안내 화면 이동");
  assert.strictEqual(evidence.card.actionLabels[2], "무인민원발급기 안내 카드 확인");
  assert.strictEqual(evidence.card.actionLabels[3], "사용자 확인 대기");
  assert.ok(evidence.card.text.includes("STOP_FOR_USER_CONFIRMATION"));

  // Verify no forbidden completion wording in the quest card or chat thread
  const fullChatText = String(await page.evaluate(() => {
    const el = document.querySelector("#chat-thread");
    return el ? el.textContent : "";
  }));
  assert.ok(!fullChatText.includes("서류가 발급되었습니다"), "must not claim document issued");
  assert.ok(!fullChatText.includes("발급 완료"), "must not claim issuance completed");
  assert.ok(!fullChatText.includes("본인인증을 완료"), "must not claim auth completed");

  const nonLocal = requests.filter((url) => !isLocalRequest(url));
  assert.deepStrictEqual(nonLocal, [], `non-local requests: ${nonLocal.join(", ")}`);
  assert.deepStrictEqual(errors, [], `browser errors: ${errors.join("\n")}`);

  const screenshotPath = join(SCREENSHOT_DIR, "unmanned-kiosk-quest-e2e.png");
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await browser.close();

  console.log("Unmanned kiosk quest E2E passed.");
  console.log(`Screenshot: ${screenshotPath}`);
}

main().catch((error) => {
  console.error("Unmanned kiosk quest E2E FAILED:");
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
