/**
 * #1380 S-final — Seo-gu illegal-parking GUIDANCE_NAVIGATION PNG evidence
 * chain (Buk-gu guidance/handoff-stop shape).
 *
 * States captured per viewport (desktop 1920x1080, mobile 390x844):
 *   0 entry (chips)                1 ANSWER
 *   2 CONFIRM                      3 grounded answer + trafficminwon clone READ
 *   4 guidance surface (지도단속 card, choreography parked at final line)
 *   5 handoff-stop terminal after resident card selection
 *
 * Usage: node tests/browser/capture_s2_png_evidence.mjs <BASE_URL> <OUT_DIR>
 */
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const BASE = process.argv[2];
const OUT = process.argv[3] || "artifacts/s2_evidence";
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

  await page.locator('.chat-chip[data-journey-id="seogu_illegal_parking_report"]').click();
  await page.waitForFunction(() => document.body.getAttribute("data-journey-state") === "answer");
  await page.screenshot({ path: `${OUT}/${label}_1_answer.png` });

  await page.waitForFunction(() => document.body.getAttribute("data-journey-state") === "confirm");
  await page.screenshot({ path: `${OUT}/${label}_2_confirm.png` });

  await page.locator('[data-confirm-action="yes"]').last().click();
  await page.waitForFunction(() => document.body.getAttribute("data-journey-state") === "grounded", null, { timeout: 30000 });
  await page.screenshot({ path: `${OUT}/${label}_3_grounded_answer_and_clone.png` });

  // Guidance surface + choreography terminal line.
  await page.waitForFunction(() =>
    document.querySelector('[data-complaint-route="complaint-illegal-parking"]') !== null,
  null, { timeout: 30000 });
  await page.waitForFunction(() =>
    document.getElementById("chat-thread").innerText.includes(
      "실제 신고는 안전신문고(safetyreport.go.kr)에서 가능합니다"),
  null, { timeout: 30000 });
  await page.screenshot({ path: `${OUT}/${label}_4_guidance_surface_card.png` });

  // Resident card selection → app-owned handoff-stop terminal.
  await page.locator(".bg-illegal-parking-card").click();
  await page.waitForFunction(() =>
    document.querySelector('[data-stop-route="handoff-stop"]') !== null,
  null, { timeout: 15000 });
  await page.screenshot({ path: `${OUT}/${label}_5_handoff_stop_terminal.png` });

  const summary = await page.evaluate(() => {
    const canvasText = document.getElementById("demo-canvas").innerText;
    return {
      finalState: document.body.getAttribute("data-journey-state"),
      stopRoute: document.querySelector('[data-stop-route="handoff-stop"]') !== null,
      truthfulLine: canvasText.includes("실제 민원 신청은 서구청 공식 채널을 이용하시기 바랍니다"),
      notSubmitted: canvasText.includes("미제출"),
      noExternalAnchor: !((document.getElementById("chat-thread").innerHTML +
        document.getElementById("demo-canvas").innerHTML).includes('href="https://www.safetyreport')),
      systemScopeText: canvasText.includes("과태료 조회") && canvasText.includes("의견진술"),
    };
  });
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
console.log("S2_PNG_EVIDENCE_DONE");
