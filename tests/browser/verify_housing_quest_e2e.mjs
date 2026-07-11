/**
 * Browser E2E verifier for #1062 apartment-dept canonical snapshot fidelity.
 *
 * Usage:
 *   node tests/browser/verify_housing_quest_e2e.mjs http://127.0.0.1:<port>
 *
 * Screenshots:
 *   <system-temp>/400-ai-finder-1062/housing-quest-e2e.png
 */

import assert from "assert";
import { mkdirSync, readFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { chromium } from "playwright";

const requestedBase = process.argv[2] || "http://127.0.0.1:8080";
const SCREENSHOT_DIR = join(tmpdir(), "400-ai-finder-1062");
mkdirSync(SCREENSHOT_DIR, { recursive: true });

const SNAPSHOT = JSON.parse(readFileSync(
  new URL("../../data/official_snapshots/bukgu_gwangju/apartment-dept.json", import.meta.url),
  "utf8",
));
const QUEST = JSON.parse(readFileSync(
  new URL("../../data/quests/bukgu_gwangju_quests.json", import.meta.url),
  "utf8",
)).quests.find((item) => item.quest_id === "housing_department_lookup");
assert.ok(QUEST, "housing_department_lookup quest fixture must exist");

function buildQuestResult() {
  return {
    service: `${SNAPSHOT.representative_contact.department} 조직 및 업무안내`,
    surface: `전체 ${SNAPSHOT.page.row_count}명 공식 업무 및 연락처`,
    stop: "사용자 확인 후 공식 채널에서 직접 진행",
    snapshot_id: SNAPSHOT.snapshot_id,
    source_url: SNAPSHOT.source.url,
    source_updated_at: SNAPSHOT.source.source_updated_at,
  };
}

function buildMvpResponse(question) {
  const result = buildQuestResult();
  const quest = {
    ...QUEST,
    answer: `공동주택 관련 문의는 ${SNAPSHOT.representative_contact.department}에서 담당합니다. ` +
      `부서 대표전화는 ${SNAPSHOT.representative_contact.phone}, FAX는 ${SNAPSHOT.representative_contact.fax}입니다. ` +
      `왼쪽 조직 및 업무안내에서 전체 ${SNAPSHOT.page.row_count}명의 담당 업무와 전화번호를 공식 표 그대로 확인할 수 있습니다.`,
    result,
    match_status: "matched",
    match_mode: "exact_phrase",
  };
  return {
    ok: true,
    question,
    answer: quest.answer,
    action: QUEST.client_action,
    confidence: 1,
    provider: "canonical_e2e_fixture",
    model: "none",
    failure_code: "",
    retrieved_at: SNAPSHOT.source.verified_at,
    freshness_state: "official_snapshot",
    source_url: SNAPSHOT.source.url,
    sources: [{ title: SNAPSHOT.source.title, url: SNAPSHOT.source.url, official: true }],
    captured_at: SNAPSHOT.source.captured_at,
    verified_at: SNAPSHOT.source.verified_at,
    official_route_id: SNAPSHOT.route_id,
    official_page_id: SNAPSHOT.page_id,
    snapshot_id: SNAPSHOT.snapshot_id,
    quest,
    action_plan: {
      quest_id: QUEST.quest_id,
      quest_name: QUEST.quest_name,
      official_path: QUEST.official_path,
      browser_actions: QUEST.browser_actions,
      result,
      source_mode: QUEST.source_mode,
      stop_condition: QUEST.stop_condition,
      final_warning: QUEST.final_warning,
      client_action: QUEST.client_action,
    },
    fallback_used: false,
  };
}

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

async function launchLocalBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch {
    return chromium.launch({ headless: true, channel: "chrome" });
  }
}

async function main() {
  const requests = [];
  const errors = [];
  const browser = await launchLocalBrowser();
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
  await page.route("**/api/mvp/ask", async (route) => {
    const payload = JSON.parse(route.request().postData() || "{}");
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(buildMvpResponse(payload.question || "")),
    });
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

  await waitForText(page, "#chat-thread", "공동주택과 안내");
  await waitForText(page, "#chat-thread", "홈 > 북구소개 > 구청안내 > 행정조직 > 공동주택과 > 조직 및 업무안내");
  await waitForText(page, "#chat-thread", "공동주택과 조직 및 업무안내 / 전체 19명 공식 업무 및 연락처");

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
  assert.ok(card, "quest card must exist before the resident confirms the walkthrough");
  assert.strictEqual(card.questCardType, "action_plan");
  assert.strictEqual(card.questId, "housing_department_lookup");
  assert.strictEqual(card.sourceMode, "local_static");
  assert.ok(card.actionLabels.includes("공동주택과 안내 화면 이동"));
  assert.ok(card.actionLabels.includes("공동주택과 업무 및 연락처 확인"));
  assert.ok(card.actionLabels.includes("사용자 확인 대기"));
  assert.ok(!card.text.includes("분야별정보 > 건축 > 아파트정보 > 아파트현황"));

  await page.getByRole("button", { name: "예, 안내해 주세요", exact: true }).click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-choreography-state") === "done",
    null,
    { timeout: 30000 },
  );

  for (const text of [
    "행정조직",
    "조직 및 업무안내",
    "조직 및 업무",
    "총 19명",
    "부서명",
    "팀명",
    "직책",
    "전화번호",
    "담당업무",
    "062-410-6033",
    "062-410-6841",
    "062-410-6828",
    "공동주택어린이놀이시설관리 등",
    "최근업데이트 2026/06/01",
  ]) {
    await waitForText(page, "#demo-canvas", text);
  }
  await waitForText(page, "#chat-thread", "부서 대표전화는 062-410-6841, FAX는 062-510-1486");
  await waitForText(page, "#chat-thread", "전체 19명의 업무별 연락처");

  const evidence = await page.evaluate(() => {
    const root = document.querySelector('[data-official-route-id="apartment-dept"]');
    const rows = Array.from(document.querySelectorAll("[data-official-row]"));
    const representative = document.querySelector('[data-representative-contact="true"]');
    const rowText = (row) => row
      ? Array.from(row.querySelectorAll("td")).map((cell) => cell.textContent.trim()).join(" | ")
      : "";
    return {
      snapshotId: root ? root.getAttribute("data-official-snapshot-id") : "",
      canonicalSha256: root ? root.getAttribute("data-canonical-sha256") : "",
      rowCount: rows.length,
      firstRow: rowText(rows[0]),
      lastRow: rowText(rows.at(-1)),
      representative: rowText(representative),
    };
  });
  assert.strictEqual(evidence.snapshotId, "bukgu_gwangju.apartment-dept.2026-07-11");
  assert.strictEqual(evidence.canonicalSha256.length, 64);
  assert.strictEqual(evidence.rowCount, 19);
  assert.strictEqual(
    evidence.firstRow,
    "공동주택과 |  | 과장 | 062-410-6033 | 공동주택과 업무전반",
  );
  assert.ok(evidence.lastRow.includes("062-410-6828"));
  assert.strictEqual(
    evidence.representative,
    "공동주택과 | 공동주택정책 | 직원 | 062-410-6841 | 서무",
  );

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
