/**
 * verify_citizen_first_use_pages.mjs
 * #921 — Static Pages emitted artifact acceptance verifier.
 *
 * Runs against a localhost server serving the built Pages artifact.
 * No external URLs, no deploy, no live site access.
 *
 * Usage:
 *   node tests/browser/verify_citizen_first_use_pages.mjs [baseUrl]
 *
 * Default baseUrl: http://127.0.0.1:8765
 *
 * Screenshots: /tmp/400-ai-finder-stage921/
 * Exit code: 0 (all pass) or 1 (any fail)
 */

import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "fs";
import { join } from "path";

const BASE_URL = (process.argv[2] || "http://127.0.0.1:8765").replace(/\/+$/, "");
const STATIC_URL = `${BASE_URL}/static/citizen-action-demo.html`;
const SCREENSHOT_DIR = "/tmp/400-ai-finder-stage921";
mkdirSync(SCREENSHOT_DIR, { recursive: true });

// ── Results aggregator ─────────────────────────────────────────────
const results = [];
const allRequests = [];
const allErrors = [];

function record(name, passed, detail) {
  results.push({ name, passed, detail });
  const tag = passed ? "PASS" : "FAIL";
  console.log(`  [${tag}] ${name}${detail ? ` — ${detail}` : ""}`);
}

// ── Page helpers ────────────────────────────────────────────────────
function onRequest(page) {
  page.on("request", (r) => allRequests.push(r.url()));
}
function onError(page) {
  page.on("pageerror", (e) => allErrors.push({ type: "pageerror", msg: e.message }));
  page.on("console", (msg) => {
    if (msg.type() === "error") allErrors.push({ type: "console-error", msg: msg.text() });
  });
}

async function gotoStatic(page) {
  await page.goto(STATIC_URL, { waitUntil: "networkidle", timeout: 15000 });
}

async function getChoreo(page) {
  return page.evaluate(() =>
    window.CitizenFirstChoreography ? window.CitizenFirstChoreography.getState() : "NO-API"
  );
}

async function getFirstUse(page) {
  return page.evaluate(() => document.body.getAttribute("data-first-use-state"));
}

async function getRoute(page) {
  return page.evaluate(() =>
    window.CitizenActionDemoCanvas ? window.CitizenActionDemoCanvas.getCurrentRouteId() : "NO-API"
  );
}

async function hasHighlight(page, targetId) {
  return page.evaluate(
    (tid) =>
      window.CitizenActionDemoCanvas && window.CitizenActionDemoCanvas.getTargetElement(tid)
        ? window.CitizenActionDemoCanvas.getTargetElement(tid).classList.contains(
            "executor-highlight"
          )
        : "NO-ELEMENT",
    targetId
  );
}

/** Poll for a condition up to `timeoutMs`, checking every `intervalMs`. */
async function poll(page, label, predicate, timeoutMs = 8000, intervalMs = 200) {
  const deadline = Date.now() + timeoutMs;
  let last = null;
  while (Date.now() < deadline) {
    last = await predicate(page);
    if (last) return last;
    await page.waitForTimeout(intervalMs);
  }
  return last;
}

function chatText(page) {
  return page.evaluate(() =>
    Array.from(document.querySelectorAll(".chat-bubble")).map((b) => b.textContent)
  );
}

// ── Main ────────────────────────────────────────────────────────────
async function main() {
  // ═════════════════════════════════════════════════════════════════
  // A. Fresh entry
  // ═════════════════════════════════════════════════════════════════
  console.log("\n=== A. Fresh entry ===");
  const browserA = await chromium.launch({ headless: true });
  const ctxA = await browserA.newContext({ viewport: { width: 1280, height: 900 } });
  const pageA = await ctxA.newPage();
  onRequest(pageA);
  onError(pageA);

  await gotoStatic(pageA);

  const entryState = await getFirstUse(pageA);
  record("A1. body state entry", entryState === "entry", `got "${entryState}"`);

  const canInert = await pageA.evaluate(() => {
    const el = document.getElementById("demo-canvas");
    return el ? el.hasAttribute("inert") : "NO-ELEMENT";
  });
  record("A2. canvas inert", canInert === true, `inert=${canInert}`);

  const canHidden = await pageA.evaluate(() => {
    const el = document.getElementById("demo-canvas");
    return el ? el.getAttribute("aria-hidden") : "NO-ELEMENT";
  });
  record("A3. canvas aria-hidden", canHidden === "true", `got "${canHidden}"`);

  const choreo = await getChoreo(pageA);
  record("A4. choreography not running", choreo !== "running" && choreo !== "NO-API", `state="${choreo}"`);

  const inputEnabled = await pageA.evaluate(() => {
    const inp = document.getElementById("chat-composer-input");
    return inp ? !inp.disabled : "NO-ELEMENT";
  });
  record("A5. composer input enabled", inputEnabled === true, `${inputEnabled}`);

  const inputTypeable = await pageA.evaluate(() => {
    const inp = document.getElementById("chat-composer-input");
    if (!inp) return false;
    inp.focus();
    return document.activeElement === inp;
  });
  record("A6. composer input focusable", inputTypeable, "");

  // ═════════════════════════════════════════════════════════════════
  // B. Full first-use flow
  // ═════════════════════════════════════════════════════════════════
  console.log("\n=== B. Full first-use flow ===");

  // Type the question
  await pageA.fill("#chat-composer-input", "불법 주정차 신고는 어디서 하나요?");
  await pageA.click("#chat-composer-send");

  // B1-B2: transitioning → split
  const splitState = await poll(pageA, "split", async (p) => {
    const s = await getFirstUse(p);
    return s === "split" ? s : null;
  }, 2000);
  record("B1. state → split", splitState === "split", `got "${splitState}"`);

  const runningChoreo = await getChoreo(pageA);
  record("B2. choreography running", runningChoreo === "running", `state="${runningChoreo}"`);

  // B3: nav-civil-service highlight
  const hlNavCivil = await poll(
    pageA,
    "nav-civil-service highlight",
    async (p) => (await hasHighlight(p, "nav-civil-service")) === true || null,
    3000
  );
  record("B3. nav-civil-service highlight", hlNavCivil === true, `${hlNavCivil}`);

  // B4: civil-service route
  const routeCivil = await poll(
    pageA,
    "civil-service route",
    async (p) => {
      const r = await getRoute(p);
      return r === "civil-service" ? r : null;
    },
    4000
  );
  record("B4. route → civil-service", routeCivil === "civil-service", `got "${routeCivil}"`);

  // Check chat messages preserved after civil-service transition
  const chatAfterCivil = await chatText(pageA);
  const hasCivilMsg = chatAfterCivil.some((t) => t.includes("종합민원 페이지로 이동합니다"));
  record("B4a. chat retained after civil-service", hasCivilMsg, "");

  // B5: nav-complaint-category highlight
  const hlNavCategory = await poll(
    pageA,
    "nav-complaint-category highlight",
    async (p) => (await hasHighlight(p, "nav-complaint-category")) === true || null,
    4000
  );
  record("B5. nav-complaint-category highlight", hlNavCategory === true, `${hlNavCategory}`);

  // B6: complaint-category route
  const routeCategory = await poll(
    pageA,
    "complaint-category route",
    async (p) => {
      const r = await getRoute(p);
      return r === "complaint-category" ? r : null;
    },
    4000
  );
  record("B6. route → complaint-category", routeCategory === "complaint-category", `got "${routeCategory}"`);

  // Check chat messages preserved after second route transition
  const chatAfterCategory = await chatText(pageA);
  const hasRouteMsg = chatAfterCategory.some((t) => t.includes("민원 유형 선택 페이지로 이동합니다"));
  record("B6a. chat retained after complaint-category", hasRouteMsg, "");

  // B7: complaint-category-illegal-parking highlight
  const hlIllegal = await poll(
    pageA,
    "illegal-parking highlight",
    async (p) => (await hasHighlight(p, "complaint-category-illegal-parking")) === true || null,
    4000
  );
  record("B7. illegal-parking highlight", hlIllegal === true, `${hlIllegal}`);

  await pageA.screenshot({ path: join(SCREENSHOT_DIR, "final-highlight.png") });
  console.log(`  [SCREENSHOT] ${join(SCREENSHOT_DIR, "final-highlight.png")}`);

  // B8: done state
  const doneState = await poll(
    pageA,
    "choreography done",
    async (p) => {
      const s = await getChoreo(p);
      return s === "done" ? s : null;
    },
    4000
  );
  record("B8. choreography done", doneState === "done", `state="${doneState}"`);

  const chatAfterDone = await chatText(pageA);
  const hasDoneMsg = chatAfterDone.some((t) => t.includes("안내가 완료되었습니다"));
  record("B8a. completion message shown", hasDoneMsg, "");

  // B9: final highlight preserved after completion
  const hlAfterDone = await hasHighlight(pageA, "complaint-category-illegal-parking");
  record("B9. final highlight preserved in done", hlAfterDone === true, `${hlAfterDone}`);

  // Count choreography messages in thread
  const choreoMsgCount = chatAfterDone.filter(
    (t) =>
      t.includes("안내해 드리겠습니다") ||
      t.includes("확인합니다") ||
      t.includes("이동합니다") ||
      t.includes("안내합니다") ||
      t.includes("완료되었습니다") ||
      t.includes("항목을 확인합니다")
  ).length;
  record("B10. choreography messages retained after route transitions", choreoMsgCount >= 6, `count=${choreoMsgCount}`);

  await pageA.screenshot({ path: join(SCREENSHOT_DIR, "completion.png") });
  console.log(`  [SCREENSHOT] ${join(SCREENSHOT_DIR, "completion.png")}`);

  await browserA.close();

  // ═════════════════════════════════════════════════════════════════
  // C. Reset / cancel
  // ═════════════════════════════════════════════════════════════════
  console.log("\n=== C. Reset / cancel ===");
  const browserC = await chromium.launch({ headless: true });
  const ctxC = await browserC.newContext({ viewport: { width: 1280, height: 900 } });
  const pageC = await ctxC.newPage();
  onRequest(pageC);
  onError(pageC);

  await gotoStatic(pageC);
  await pageC.fill("#chat-composer-input", "불법 주정차 신고는 어디서 하나요?");
  await pageC.click("#chat-composer-send");
  // Wait until choreography has progressed a bit (nav-civil-service highlight)
  await poll(pageC, "running", async (p) => {
    const s = await getChoreo(p);
    return s === "running" ? s : null;
  }, 2000);
  await pageC.waitForTimeout(600);
  record("C1. choreography running pre-reset", (await getChoreo(pageC)) === "running", "");

  // Click reset
  await pageC.click("#chat-reset");
  await pageC.waitForTimeout(300);

  const resetState = await getFirstUse(pageC);
  record("C2. state → entry", resetState === "entry", `got "${resetState}"`);

  const resetInert = await pageC.evaluate(() => {
    const el = document.getElementById("demo-canvas");
    return el ? el.hasAttribute("inert") : "NO-ELEMENT";
  });
  record("C3. canvas inert", resetInert === true, `inert=${resetInert}`);

  const resetChoreo = await getChoreo(pageC);
  record("C4. choreography cancelled", resetChoreo === "cancelled", `state="${resetChoreo}"`);

  const resetHLCount = await pageC.evaluate(
    () => document.querySelectorAll(".executor-highlight").length
  );
  record("C5. zero highlights", resetHLCount === 0, `count=${resetHLCount}`);

  const resetMsgCount = await pageC.evaluate(() => document.querySelectorAll(".chat-msg").length);
  record("C6. chat thread → 1 message", resetMsgCount === 1, `count=${resetMsgCount}`);

  const hasFocus = await pageC.evaluate(() => {
    const inp = document.getElementById("chat-composer-input");
    return document.activeElement === inp;
  });
  record("C7. composer re-focused", hasFocus, "");

  // 10s quiet check
  const preQuietMsgs = resetMsgCount;
  const preQuietHL = resetHLCount;
  const preQuietRoute = await getRoute(pageC);
  await pageC.waitForTimeout(10500);
  const postMsgs = await pageC.evaluate(() => document.querySelectorAll(".chat-msg").length);
  record("C8. no new messages in 10s", postMsgs === preQuietMsgs, `${preQuietMsgs} → ${postMsgs}`);
  const postHL = await pageC.evaluate(() => document.querySelectorAll(".executor-highlight").length);
  record("C9. no highlights in 10s", postHL === preQuietHL, `${preQuietHL} → ${postHL}`);
  const postRoute = await getRoute(pageC);
  record("C10. route unchanged in 10s", postRoute === preQuietRoute, `${preQuietRoute} → ${postRoute}`);

  await browserC.close();

  // ═════════════════════════════════════════════════════════════════
  // D. Unsupported question
  // ═════════════════════════════════════════════════════════════════
  console.log("\n=== D. Unsupported question ===");
  const browserD = await chromium.launch({ headless: true });
  const ctxD = await browserD.newContext({ viewport: { width: 1280, height: 900 } });
  const pageD = await ctxD.newPage();
  onRequest(pageD);
  onError(pageD);

  await gotoStatic(pageD);
  await pageD.fill("#chat-composer-input", "이 근처 맛집 추천해줘");
  await pageD.click("#chat-composer-send");
  await pageD.waitForTimeout(300);

  record("D1. state stays entry", (await getFirstUse(pageD)) === "entry", "");
  record("D2. choreography not running", (await getChoreo(pageD)) !== "running", "");

  const dInert = await pageD.evaluate(() => {
    const el = document.getElementById("demo-canvas");
    return el ? el.hasAttribute("inert") : "NO-ELEMENT";
  });
  record("D3. canvas inert", dInert === true, "");

  const dUnsupMsg = await pageD.evaluate(() =>
    document.body.textContent.includes("지원 범위의 질문으로 다시 입력해 주세요")
  );
  record("D4. unsupported guidance shown", dUnsupMsg, "");

  await browserD.close();

  // ═════════════════════════════════════════════════════════════════
  // E. Reduced motion
  // ═════════════════════════════════════════════════════════════════
  console.log("\n=== E. Reduced motion ===");
  const browserE = await chromium.launch({ headless: true });
  const ctxE = await browserE.newContext({
    viewport: { width: 1280, height: 900 },
    reducedMotion: "reduce",
  });
  const pageE = await ctxE.newPage();
  onRequest(pageE);
  onError(pageE);

  await gotoStatic(pageE);
  await pageE.fill("#chat-composer-input", "불법 주정차 신고는 어디서 하나요?");
  await pageE.click("#chat-composer-send");
  await pageE.waitForTimeout(200);

  // Should be split immediately (no animation delay)
  const rmSplit = await getFirstUse(pageE);
  record("E1. reduced-motion → split", rmSplit === "split", `got "${rmSplit}"`);

  // choreography should start and progress
  const rmRunning = await getChoreo(pageE);
  record("E2. reduced-motion choreography running or done", rmRunning === "running" || rmRunning === "done", `state="${rmRunning}"`);

  // Wait for the navigation sequence to complete
  const rmDone = await poll(pageE, "reduced-motion done", async (p) => {
    const s = await getChoreo(p);
    return s === "done" ? s : null;
  }, 12000);
  record("E3. reduced-motion reaches done", rmDone === "done", `state="${rmDone}"`);

  const rmHighlight = await hasHighlight(pageE, "complaint-category-illegal-parking");
  record("E4. reduced-motion final highlight preserved", rmHighlight === true, `${rmHighlight}`);

  await browserE.close();

  // ═════════════════════════════════════════════════════════════════
  // F. Legacy direct-load regression
  // ═════════════════════════════════════════════════════════════════
  console.log("\n=== F. Legacy direct-load regression ===");
  for (const journey of ["J-DEPT-01", "J-PARK-01", "J-KIOSK-01"]) {
    const bLeg = await chromium.launch({ headless: true });
    const ctxLeg = await bLeg.newContext({ viewport: { width: 1280, height: 900 } });
    const pLeg = await ctxLeg.newPage();
    const legErrors = [];
    pLeg.on("pageerror", (e) => legErrors.push(e.message));
    pLeg.on("console", (msg) => {
      if (msg.type() === "error") legErrors.push(msg.text());
    });

    await pLeg.goto(`${BASE_URL}/static/citizen-action-demo.html?journey=${journey}`, {
      waitUntil: "networkidle",
      timeout: 15000,
    });
    await pLeg.waitForTimeout(500);

    const legSplit = await pLeg.evaluate(() => document.body.getAttribute("data-first-use-state"));
    record(`F1. ${journey} state split`, legSplit === "split", `got "${legSplit}"`);

    const legChoreo = await pLeg.evaluate(() => {
      const c = window.CitizenFirstChoreography;
      return c ? c.getState() : "NO-API";
    });
    record(`F2. ${journey} choreography idle`, legChoreo === "idle", `state="${legChoreo}"`);

    const legHL = await pLeg.evaluate(() => document.querySelectorAll(".executor-highlight").length);
    record(`F3. ${journey} no auto-highlight`, legHL === 0, `count=${legHL}`);

    if (legErrors.length > 0) {
      record(`F4. ${journey} no errors`, false, legErrors.join("; "));
    } else {
      record(`F4. ${journey} no errors`, true, "");
    }

    await bLeg.close();
  }

  // ═════════════════════════════════════════════════════════════════
  // G. Safety boundary (aggregated across all runs)
  // ═════════════════════════════════════════════════════════════════
  console.log("\n=== G. Safety boundary ===");

  const nonLocal = allRequests.filter(
    (u) => !u.startsWith("http://127.0.0.1:8765") && !u.startsWith("data:")
  );
  record("G1. all requests from localhost", nonLocal.length === 0, nonLocal.join(", ") || "0 external");

  const pageErrs = allErrors.filter((e) => e.type === "pageerror");
  const consoleErrs = allErrors.filter((e) => e.type === "console-error");
  record("G2. pageerrors 0", pageErrs.length === 0, pageErrs.map((e) => e.msg).join(" | ") || "0");
  record("G3. console errors 0", consoleErrs.length === 0, consoleErrs.map((e) => e.msg).join(" | ") || "0");

  // Check storage/cookie on the last open page (pageD — unsupported context)
  // But pageD is closed. Let's open a fresh one for safety check.
  const browserG = await chromium.launch({ headless: true });
  const ctxG = await browserG.newContext({ viewport: { width: 1280, height: 900 } });
  const pageG = await ctxG.newPage();
  await gotoStatic(pageG);

  const cookieEmpty = await pageG.evaluate(() => document.cookie === "");
  record("G4. document.cookie empty", cookieEmpty, `got "${await pageG.evaluate(() => document.cookie)}"`);

  const lsEmpty = await pageG.evaluate(() => localStorage.length === 0);
  record("G5. localStorage empty", lsEmpty, `length=${await pageG.evaluate(() => localStorage.length)}`);

  const ssEmpty = await pageG.evaluate(() => sessionStorage.length === 0);
  record("G6. sessionStorage empty", ssEmpty, `length=${await pageG.evaluate(() => sessionStorage.length)}`);

  await browserG.close();

  // ═════════════════════════════════════════════════════════════════
  // Summary
  // ═════════════════════════════════════════════════════════════════
  console.log("\n══════════════════════════════════════════");
  console.log("           VERIFICATION SUMMARY");
  console.log("══════════════════════════════════════════");
  const passed = results.filter((r) => r.passed).length;
  const failed = results.filter((r) => !r.passed).length;
  console.log(`  Total: ${results.length}  |  PASS: ${passed}  |  FAIL: ${failed}`);
  if (failed > 0) {
    console.log("\n  FAILED ITEMS:");
    for (const r of results) {
      if (!r.passed) console.log(`    ✗ ${r.name}: ${r.detail}`);
    }
  }
  console.log(`\n  Screenshots: ${SCREENSHOT_DIR}/`);
  console.log("──────────────────────────────────────────\n");

  process.exit(failed > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error("FATAL:", err);
  process.exit(1);
});
