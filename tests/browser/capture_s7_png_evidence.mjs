/**
 * #1363 S7 mayor-proposal PNG evidence chain.
 * Walks the canonical YES path and captures a PNG at every observable
 * canonical state (entry/answer/confirm/evidence-gate/handoff-STOP) for
 * desktop 1920x1080 and mobile 390x844, per the #1348 state-by-state
 * documentation requirement.
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
  await page.screenshot({ path: `${OUT}/${label}_0_entry.png`, fullPage: false });

  await page.locator('.chat-chip[data-journey-id="seogu_mayor_proposal"]').click();
  await page.waitForFunction(() => document.body.getAttribute("data-journey-state") === "answer");
  await page.screenshot({ path: `${OUT}/${label}_1_answer.png` });

  await page.waitForFunction(() => document.body.getAttribute("data-journey-state") === "confirm");
  await page.screenshot({ path: `${OUT}/${label}_2_confirm.png` });

  await page.locator('[data-confirm-action="yes"]').last().click();
  await page.waitForFunction(() => document.body.getAttribute("data-journey-state") === "safe_handoff", null, { timeout: 30000 });
  await page.screenshot({ path: `${OUT}/${label}_3_evidence_gate_and_handoff_stop.png` });

  const summary = await page.evaluate(() => ({
    finalState: document.body.getAttribute("data-journey-state"),
    evidenceVerified: [...document.querySelectorAll('[data-handoff-evidence="true"]')]
      .some((n) => n.getAttribute("data-journey-id") === "seogu_mayor_proposal" &&
                    n.getAttribute("data-handoff-evidence-verified") === "true"),
    handoffRow: (() => {
      const n = [...document.querySelectorAll('[data-safe-handoff="true"]')]
        .find((n) => n.getAttribute("data-journey-id") === "seogu_mayor_proposal");
      return n ? {
        url: n.getAttribute("data-handoff-destination-url"),
        label: n.getAttribute("data-handoff-destination-label"),
        scope: n.getAttribute("data-handoff-claim-scope"),
        stop: n.getAttribute("data-handoff-stop-boundary"),
        anchorTarget: n.querySelector("a")?.getAttribute("target"),
      } : null;
    })(),
    iframePath: (() => { try { return document.getElementById("seogu-clone-frame").contentWindow.location.pathname; } catch { return null; } })(),
  }));
  console.log(label, JSON.stringify(summary));
  await ctx.close();
}

await walk({ width: 1920, height: 1080 }, "desktop_1920x1080");
await walk({ width: 390, height: 844 }, "mobile_390x844");
await browser.close();
console.log("S7_PNG_EVIDENCE_DONE");
