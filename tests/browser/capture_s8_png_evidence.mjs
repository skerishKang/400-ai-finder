/**
 * #1376 Lane B — Seo-gu S8 bulky-waste DIRECT_REUSE PNG evidence chain.
 *
 * Walks the canonical YES path and captures a PNG at every observable
 * canonical state for desktop 1920x1080 and mobile 390x844 (#1348
 * state-by-state documentation):
 *
 *   0 entry (chips)   1 ANSWER   2 CONFIRM
 *   3 grounded result + bulky-waste-guidance clone page (fee table visible)
 *
 * Usage: node tests/browser/capture_s8_png_evidence.mjs <BASE_URL> <OUT_DIR>
 */
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const BASE = process.argv[2];
const OUT = process.argv[3] || "artifacts/s8_evidence";
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

  await page.locator('.chat-chip[data-journey-id="seogu_mattress_disposal"]').click();
  await page.waitForFunction(() => document.body.getAttribute("data-journey-state") === "answer");
  await page.screenshot({ path: `${OUT}/${label}_1_answer.png` });

  await page.waitForFunction(() => document.body.getAttribute("data-journey-state") === "confirm");
  await page.screenshot({ path: `${OUT}/${label}_2_confirm.png` });

  await page.locator('[data-confirm-action="yes"]').last().click();
  await page.waitForFunction(() => document.body.getAttribute("data-journey-state") === "grounded", null, { timeout: 30000 });
  // Give the clone iframe READ + answer render a beat to settle.
  await page.waitForFunction(() => {
    const frame = document.getElementById("seogu-clone-frame");
    try {
      const main = frame.contentDocument && frame.contentDocument.querySelector("main.rc-main");
      return main && main.innerText.includes("대형폐기물 신고");
    } catch {
      return false;
    }
  }, null, { timeout: 15000 });
  await page.screenshot({ path: `${OUT}/${label}_3_grounded_result_and_clone.png` });

  const summary = await page.evaluate(() => {
    const frame = document.getElementById("seogu-clone-frame");
    let rcMain = "";
    try {
      const main = frame.contentDocument && frame.contentDocument.querySelector("main.rc-main");
      rcMain = main ? main.innerText : "";
    } catch {}
    return {
      finalState: document.body.getAttribute("data-journey-state"),
      iframePath: frame.contentWindow ? frame.contentWindow.location.pathname : null,
      feeFacts: ["1인용 매트리스", "8,000", "2인용 매트리스", "11,000", "4~7일"]
        .map((k) => `${k}:${rcMain.includes(k) ? "Y" : "N"}`).join(" "),
      noStaleFallbackFee: !rcMain.includes("침대 매트리스 5,000"),
      threadGrounded: (document.getElementById("chat-thread").innerText || "").includes("서구"),
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
console.log("S8_PNG_EVIDENCE_DONE");
