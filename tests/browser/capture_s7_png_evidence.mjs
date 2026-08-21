/**
 * #1363 Lane B — Seo-gu S7 mayor-proposal WRITE-FLOW PNG evidence chain.
 * (CTO rework 2026-08-21: journey shape = Buk-gu mayor-complaint-write/receipt.)
 *
 * Walks the canonical YES path and captures a PNG at every observable
 * canonical state for desktop 1920x1080 and mobile 390x844, per the #1348
 * state-by-state documentation requirement:
 *
 *   0 entry (chips)            1 ANSWER
 *   2 CONFIRM                  3 evidence gate passed → mayor-office-entry
 *   4 mayor-office             5 mayor-complaint-write PRE_SUBMIT STOP
 *   6 mayor-complaint-receipt (공식 제출 전)
 *
 * Usage: node tests/browser/capture_s7_png_evidence.mjs <BASE_URL> <OUT_DIR>
 */
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const BASE = process.argv[2];
const OUT = process.argv[3] || "artifacts/s7_evidence";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ headless: true, channel: "chrome" });

async function walk(viewport, label) {
  const ctx = await browser.newContext({ viewport });
  await ctx.route("**/*", async (r) => {
    const u = r.request().url();
    if (u.startsWith(BASE)) return r.continue();
    return r.abort();
  });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/static/seogu-citizen-action-demo.html`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.querySelectorAll("#chat-chips .chat-chip").length > 0);
  await page.screenshot({ path: `${OUT}/${label}_0_entry.png` });

  await page.locator('.chat-chip[data-journey-id="seogu_mayor_proposal"]').click();
  await page.waitForFunction(() => document.body.getAttribute("data-journey-state") === "answer");
  await page.screenshot({ path: `${OUT}/${label}_1_answer.png` });

  await page.waitForFunction(() => document.body.getAttribute("data-journey-state") === "confirm");
  await page.screenshot({ path: `${OUT}/${label}_2_confirm.png` });

  await page.locator('[data-confirm-action="yes"]').last().click();
  await page.waitForFunction(
    () => document.querySelector('[data-complaint-route="mayor-office-entry"]') !== null,
    null,
    { timeout: 30000 },
  );
  await page.screenshot({ path: `${OUT}/${label}_3_gate_passed_office_entry.png` });

  await page.waitForFunction(() =>
    document.querySelector('[data-complaint-route="mayor-office"]') !== null,
  null, { timeout: 30000 });
  await page.screenshot({ path: `${OUT}/${label}_4_mayor_office.png` });

  await page.waitForFunction(() =>
    document.querySelector('[data-complaint-route="mayor-complaint-write"]') !== null,
  null, { timeout: 30000 });
  await page.waitForFunction(() => {
    const btns = Array.from(document.querySelectorAll(".chat-decision__button--primary"));
    const t = document.getElementById("mayor-write-content");
    return btns.some((b) => String(b.textContent || "").includes("제출하기")) &&
      t && t.value && t.value.length > 50;
  }, null, { timeout: 90000 });
  await page.screenshot({ path: `${OUT}/${label}_5_pre_submit_stop.png` });

  // Resident confirms at the pre-submit boundary → truthful receipt.
  // On mobile the split state shows the canvas ("guidance"); the chat with
  // the confirmation button lives behind the "conversation" tab.
  const isMobile = viewport.width < 768;
  if (isMobile) {
    const convTab = page.locator('[data-mobile-surface-tab="conversation"]');
    if (await convTab.count()) {
      await convTab.first().click();
      await page.waitForFunction(() =>
        document.body.getAttribute("data-mobile-surface") === "conversation",
      null, { timeout: 10000 });
    }
  }
  await page
    .locator(".chat-decision__button--primary")
    .filter({ hasText: "제출하기" })
    .first()
    .click();
  await page.waitForFunction(() =>
    document.querySelector('[data-receipt-route="mayor-complaint-receipt"]') !== null,
  null, { timeout: 30000 });
  if (isMobile) {
    // The receipt visual lives on the canvas surface — switch back.
    const guidTab = page.locator('[data-mobile-surface-tab="guidance"]');
    if (await guidTab.count()) {
      await guidTab.first().click();
      await page.waitForFunction(() =>
        document.body.getAttribute("data-mobile-surface") === "guidance",
      null, { timeout: 10000 });
    }
  }
  await page.screenshot({ path: `${OUT}/${label}_6_receipt_official_channel_pending.png` });

  const summary = await page.evaluate(() => ({
    finalState: document.body.getAttribute("data-journey-state"),
    receiptRoute: document.querySelector('[data-receipt-route="mayor-complaint-receipt"]') !== null,
    officialPending: (document.getElementById("demo-canvas").innerText || "").includes("공식 제출 전"),
    truthfulLine: (document.getElementById("demo-canvas").innerText || "").includes(
      "서구청 공식 채널에서 시민이 직접 확인하고 진행합니다"),
    noExternalChannel: !(document.getElementById("chat-thread").innerText +
      document.getElementById("demo-canvas").innerText).includes("epeople"),
  }));
  console.log(label, JSON.stringify(summary));
  await ctx.close();
}

let desktopDone = false;
for (let attempt = 1; attempt <= 3 && !desktopDone; attempt++) {
  try {
    await walk({ width: 1920, height: 1080 }, "desktop_1920x1080");
    desktopDone = true;
  } catch (e) {
    console.error(`desktop attempt ${attempt} failed: ${e.message.split("\n")[0]}`);
  }
}
if (!desktopDone) throw new Error("desktop evidence chain failed after 3 attempts");

let mobileDone = false;
for (let attempt = 1; attempt <= 3 && !mobileDone; attempt++) {
  try {
    await walk({ width: 390, height: 844 }, "mobile_390x844");
    mobileDone = true;
  } catch (e) {
    console.error(`mobile attempt ${attempt} failed: ${e.message.split("\n")[0]}`);
  }
}
if (!mobileDone) throw new Error("mobile evidence chain failed after 3 attempts");
await browser.close();
console.log("S7_PNG_EVIDENCE_DONE");
