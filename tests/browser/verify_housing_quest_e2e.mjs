/**
 * Browser E2E verifier for #988 apartment quest real-page fidelity.
 *
 * Usage:
 *   node tests/browser/verify_housing_quest_e2e.mjs http://127.0.0.1:<port>
 *
 * Screenshots:
 *   /tmp/400-ai-finder-988/housing-quest-e2e.png
 */

import assert from "assert";
import { mkdirSync } from "fs";
import { join } from "path";
import { chromium } from "playwright";

const requestedBase = process.argv[2] || "http://127.0.0.1:8080";
const SCREENSHOT_DIR = "/tmp/400-ai-finder-988";
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

  await page.fill("#chat-composer-input", "공동주택 문의는 어디로 해요?");
  await page.click("#chat-composer-send");

  await page.waitForFunction(
    () => document.body.getAttribute("data-quest-id") === "housing_department_lookup",
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

  await waitForText(page, "#demo-canvas", "분야별정보");
  await waitForText(page, "#demo-canvas", "건축");
  await waitForText(page, "#demo-canvas", "아파트정보");
  await waitForText(page, "#demo-canvas", "아파트명");
  await waitForText(page, "#demo-canvas", "새주소명");
  await waitForText(page, "#demo-canvas", "사용검사");
  await waitForText(page, "#demo-canvas", "세대수");
  await waitForText(page, "#demo-canvas", "관리사무소");
  await waitForText(page, "#demo-canvas", "전체 428 건");
  await waitForText(page, "#demo-canvas", "아파트생활정보");
  await waitForText(page, "#demo-canvas", "하자발생");
  await waitForText(page, "#demo-canvas", "생활요령");
  await waitForText(page, "#demo-canvas", "생활수칙");
  await waitForText(page, "#demo-canvas", "관리비");
  await waitForText(page, "#chat-thread", "아파트 정보 안내");
  await waitForText(page, "#chat-thread", "북구청 홈 > 분야별정보 > 건축 > 아파트정보 > 아파트현황");
  await waitForText(page, "#chat-thread", "STOP_FOR_USER_CONFIRMATION");
  await waitForText(page, "#chat-thread", "local_static");

  const card = await page.evaluate(() => {
    const el = document.querySelector("#chat-thread .chat-quest-card");
    if (!el) return null;
    return {
      questCardType: el.getAttribute("data-quest-card"),
      questId: el.getAttribute("data-quest-id"),
      sourceMode: el.getAttribute("data-source-mode"),
      actionLabels: Array.from(el.querySelectorAll(".chat-quest-card__action")).map((node) => node.textContent.trim()),
      text: el.textContent,
    };
  });
  assert.ok(card, "quest card must exist in the right panel");
  assert.strictEqual(card.questCardType, "action_plan");
  assert.strictEqual(card.questId, "housing_department_lookup");
  assert.strictEqual(card.sourceMode, "local_static");
  assert.ok(card.actionLabels.length >= 2, `expected at least 2 action labels, got ${card.actionLabels.length}`);
  assert.ok(card.actionLabels.includes("아파트정보 화면 이동"));
  assert.ok(card.actionLabels.includes("아파트생활정보 관련 안내 확인"));

  const nonLocal = requests.filter((url) => !isLocalRequest(url));
  assert.deepStrictEqual(nonLocal, [], `non-local requests: ${nonLocal.join(", ")}`);
  assert.deepStrictEqual(errors, [], `browser errors: ${errors.join("\n")}`);

  const screenshotPath = join(SCREENSHOT_DIR, "housing-quest-e2e.png");
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await browser.close();

  console.log("Housing quest E2E passed.");
  console.log(`Screenshot: ${screenshotPath}`);
}

main().catch((error) => {
  console.error("Housing quest E2E FAILED:");
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
