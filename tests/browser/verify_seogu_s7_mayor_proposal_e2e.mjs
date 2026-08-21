/**
 * #1363 Lane B (CTO rework 2026-08-21) — Seo-gu S7 mayor-proposal writing
 * journey safety contract (browser E2E).
 *
 * S7 mirrors the Buk-gu 구청장에게 제안하고 싶어요 mayor-complaint-write/receipt
 * golden journey via the #1375 complaint-writing pattern:
 *
 *   ANSWER → CONFIRM → YES → COMPLAINT_EVIDENCE_GATE (bounded 주민제안 capture)
 *   → grounded guidance → app-owned surface: mayor-office-entry → mayor-office
 *   → mayor-complaint-write (AI draft) → PRE_SUBMIT STOP (submit disabled)
 *   → resident confirms → mayor-complaint-receipt (truthful 서구청 line,
 *   공식 제출 전).
 *
 * Proves:
 *   A. NO path stops (no surface, no choreography, zero external requests)
 *   B. Evidence failure stops fail-closed (no surface, no choreography)
 *   C. Happy path drives the full write flow to the receipt with the
 *      pre-submit STOP invariant enforced before resident confirmation
 *   D. Duplicate activation refused while the choreography owns the flow
 *   E. No epeople/external anchor anywhere; no safe_handoff row; zero
 *      external HTTP(S) requests; no fake submission-success semantics
 *
 * Usage: node verify_seogu_s7_mayor_proposal_e2e.mjs <LOCAL_BASE_URL>
 */
import assert from "assert";
import { chromium } from "playwright";

const BASE_ORIGIN = localOrigin(process.argv[2]);
const DEMO_URL = `${BASE_ORIGIN}/static/seogu-citizen-action-demo.html`;

const JID = "seogu_mayor_proposal";
const CHIP = `.chat-chip[data-journey-id="${JID}"]`;
const GATE_ROUTE = "mayor-proposal-guidance";
const MISSING_MARKER = "참여방법";
const CONTROL_MARKER = "주민제안";

// Strings that would indicate a fake submission success (strictly forbidden).
// The truthful receipt line ("공식 제출 전" / "공식 채널에서 직접 확인") is the
// Buk-gu-native safety boundary and must stay present.
const FORBIDDEN_SUCCESS_PATTERNS = [
  "신고 완료",
  "접수 완료",
  "제출 완료",
  "접수번호",
  "receipt number",
  "자동 제출",
];

function localOrigin(raw) {
  if (!raw || raw === "undefined") {
    throw new Error("usage: node verify_seogu_s7_mayor_proposal_e2e.mjs <BASE_URL>");
  }
  const url = new URL(raw);
  if (!["127.0.0.1", "localhost", "::1"].includes(url.hostname)) {
    throw new Error(`S7 gate requires localhost base, got ${url.hostname}`);
  }
  return url.origin;
}

async function launchBrowser() {
  const attempts = [];
  const errors = [];
  const envPath = process.env.PREVIEW_BROWSER_EXECUTABLE;
  if (envPath) {
    attempts.push({
      name: `env: ${envPath}`,
      launch: () => chromium.launch({ headless: true, executablePath: envPath }),
    });
  }
  attempts.push({
    name: "channel: chrome",
    launch: () => chromium.launch({ headless: true, channel: "chrome" }),
  });
  attempts.push({
    name: "default playwright chromium",
    launch: () => chromium.launch({ headless: true }),
  });
  for (const attempt of attempts) {
    try {
      const browser = await attempt.launch();
      console.log(`Browser launched (${attempt.name})`);
      return browser;
    } catch (error) {
      errors.push(`[${attempt.name}] ${error.message}`);
    }
  }
  throw new Error(`Cannot launch any browser. Attempts:\n${errors.join("\n")}`);
}

function installEgressGuard(context) {
  return context.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.startsWith("data:")) {
      await route.continue();
      return;
    }
    let parsed;
    try {
      parsed = new URL(url);
    } catch {
      externalRequests.push(url);
      await route.abort();
      return;
    }
    if (parsed.origin !== BASE_ORIGIN) {
      externalRequests.push(url);
      await route.abort();
      return;
    }
    await route.continue();
  });
}

const externalRequests = [];

async function openDemo(context) {
  const page = await context.newPage();
  await page.goto(DEMO_URL, { waitUntil: "networkidle", timeout: 20000 });
  await page.waitForFunction(
    () => document.querySelectorAll("#chat-chips .chat-chip").length > 0,
    null,
    { timeout: 15000 },
  );
  await page.waitForFunction(
    () => document.body.getAttribute("data-surface-state") === "ready",
    null,
    { timeout: 15000 },
  );
  return page;
}

async function waitForState(page, state, timeout = 20000) {
  await page.waitForFunction(
    (s) => document.body.getAttribute("data-journey-state") === s,
    state,
    { timeout },
  );
}

async function clickYes(page) {
  await page.locator('[data-confirm-action="yes"]').last().click();
}

async function clickNo(page) {
  await page.locator('[data-confirm-action="no"]').last().click();
}

function assertNoForbiddenSuccess(text, where) {
  for (const pattern of FORBIDDEN_SUCCESS_PATTERNS) {
    assert.ok(
      !String(text || "").includes(pattern),
      `forbidden fake-success string "${pattern}" found in ${where}`,
    );
  }
}

// ── A. NO path stops ────────────────────────────────────────────────────────
async function proveNoPathStops(browser) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  installEgressGuard(context);
  const page = await openDemo(context);

  await page.locator(CHIP).click();
  await waitForState(page, "answer");
  await waitForState(page, "confirm");
  await clickNo(page);
  await waitForState(page, "answer");

  const after = await page.evaluate(() => ({
    state: document.body.getAttribute("data-journey-state"),
    resultNull: (() => {
      const shell = window.SeoguCitizenActionShell;
      const r = shell ? shell.getLastJourneyResult() : null;
      return r === null || r === undefined;
    })(),
    viewHosts: document.querySelectorAll("[data-seogu-complaint-view]").length,
    mayorRoutes: document.querySelectorAll("[data-complaint-route]").length,
    choreoState: window.CitizenFirstChoreography ? window.CitizenFirstChoreography.getState() : null,
    safeHandoffRows: document.querySelectorAll('[data-safe-handoff="true"]').length,
    threadText: document.getElementById("chat-thread").innerText,
  }));

  assert.strictEqual(after.state, "answer", "S7 NO: must stop at answer");
  assert.strictEqual(after.resultNull, true, "S7 NO: journey result must stay null");
  assert.strictEqual(after.viewHosts, 0, "S7 NO: proposal surface must not render");
  assert.strictEqual(after.mayorRoutes, 0, "S7 NO: no mayor route may render");
  assert.strictEqual(after.choreoState, "idle", "S7 NO: choreography must never start");
  assert.strictEqual(after.safeHandoffRows, 0, "S7 NO: no safe_handoff row may exist");
  assertNoForbiddenSuccess(after.threadText, "S7 NO thread");

  await context.close();
}

// ── B. Evidence failure stops ───────────────────────────────────────────────
async function proveEvidenceFailureStops(browser) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  installEgressGuard(context);

  const original = await context.request.get(`${BASE_ORIGIN}/seogu/${GATE_ROUTE}/`);
  assert.strictEqual(original.status(), 200, "S7 gate page must be served");
  const strippedBody = (await original.text())
    .split(MISSING_MARKER)
    .join("_STRIPPED_BY_TEST_");

  const page = await openDemo(context);
  const interceptUrl = `${BASE_ORIGIN}/seogu/${GATE_ROUTE}/`;
  await page.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.includes(interceptUrl)) {
      await route.fulfill({
        status: 200,
        contentType: "text/html; charset=utf-8",
        body: strippedBody,
      });
      return;
    }
    await route.fallback();
  });

  await page.locator(CHIP).click();
  await waitForState(page, "answer");
  await waitForState(page, "confirm");
  await clickYes(page);
  await waitForState(page, "handoff_evidence_failed");

  const after = await page.evaluate((jid) => {
    const rows = Array.from(document.querySelectorAll('[data-handoff-blocked="true"]'));
    const el = rows.filter((n) => n.getAttribute("data-journey-id") === jid).pop();
    return {
      state: document.body.getAttribute("data-journey-state"),
      blocked: el ? {
        action_kind: el.getAttribute("data-handoff-action-kind"),
        claim_scope: el.getAttribute("data-handoff-claim-scope"),
        stop_boundary: el.getAttribute("data-handoff-stop-boundary"),
        hasAnchor: Boolean(el.querySelector("a")),
        hasFormControl: Boolean(el.querySelector("input,select,textarea,button,form")),
      } : null,
      viewHosts: document.querySelectorAll("[data-seogu-complaint-view]").length,
      mayorRoutes: document.querySelectorAll("[data-complaint-route]").length,
      safeHandoffRows: document.querySelectorAll('[data-safe-handoff="true"]').length,
      choreoState: window.CitizenFirstChoreography ? window.CitizenFirstChoreography.getState() : null,
      generalFallbackOffers: document.querySelectorAll('[data-general-fallback-offer="true"]').length,
      threadText: document.getElementById("chat-thread").innerText,
    };
  }, JID);

  assert.strictEqual(after.state, "handoff_evidence_failed", "S7 failed gate must expose the fail-closed state");
  assert.ok(after.blocked, "S7 failed gate must render the bounded STOP row");
  assert.strictEqual(after.blocked.action_kind, "COMPLAINT_EVIDENCE_GATE", "S7 STOP row must keep the gate action_kind");
  assert.strictEqual(after.blocked.claim_scope, "EVIDENCE_GATE_ONLY", "S7 STOP row must keep EVIDENCE_GATE_ONLY scope");
  assert.strictEqual(after.blocked.stop_boundary, "COMPLAINT_EVIDENCE_FAILED_STOP", "S7 STOP row must carry the configured boundary code");
  assert.strictEqual(after.blocked.hasAnchor, false, "S7 STOP row must contain no anchor");
  assert.strictEqual(after.blocked.hasFormControl, false, "S7 STOP row must contain no form control");
  assert.strictEqual(after.viewHosts, 0, "S7 failed gate must not open the proposal surface");
  assert.strictEqual(after.mayorRoutes, 0, "S7 failed gate must not render any mayor route");
  assert.strictEqual(after.safeHandoffRows, 0, "S7 failed gate must render no destination row");
  assert.strictEqual(after.choreoState, "idle", "S7 failed gate must not start the choreography");
  assert.strictEqual(after.generalFallbackOffers, 0, "S7 failed gate must not offer the general-model fallback");

  await context.close();
}

// ── C + D. Write flow to PRE_SUBMIT STOP → receipt; duplicate refused ───────
async function proveWriteFlowAndDuplicateRefused(browser) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  installEgressGuard(context);
  const page = await openDemo(context);

  // Gate → grounded guidance → proposal-writing surface.
  await page.locator(CHIP).click();
  await waitForState(page, "answer");
  await waitForState(page, "confirm");
  await clickYes(page);
  await waitForState(page, "complaint_write", 30000);

  const entered = await page.evaluate(() => ({
    state: document.body.getAttribute("data-journey-state"),
    entryRoute: document.querySelector('[data-complaint-route="mayor-office-entry"]') !== null,
    openOfficeBtn: document.getElementById("btn-open-mayor-office") !== null,
    groundedMsg: document.getElementById("chat-thread").innerText.includes(
      "서구청 공식 안내 화면에서 주민 제안 관련 정보를 확인했습니다"),
    safeHandoffRows: document.querySelectorAll('[data-safe-handoff="true"]').length,
    epeopleRefs: document.getElementById("chat-thread").innerText.includes("epeople") ||
                 document.querySelector("#demo-canvas").innerText.includes("epeople"),
  }));
  assert.strictEqual(entered.state, "complaint_write", "S7 journey state must be complaint_write after the gate");
  assert.ok(entered.entryRoute, "S7 must land on the mayor-office-entry route");
  assert.ok(entered.openOfficeBtn, "S7 entry must expose #btn-open-mayor-office");
  assert.ok(entered.groundedMsg, "S7 must show the grounded guidance message from the capture");
  assert.strictEqual(entered.safeHandoffRows, 0, "S7 must render no safe_handoff destination row");
  assert.strictEqual(entered.epeopleRefs, false, "S7 must not reference any external channel (epeople)");

  // Choreography: office entry → office → write form.
  await page.waitForFunction(() =>
    document.querySelector('[data-complaint-route="mayor-office"]') !== null,
  null, { timeout: 30000 });
  await page.waitForFunction(() =>
    document.querySelector('[data-complaint-route="mayor-complaint-write"]') !== null,
  null, { timeout: 30000 });

  // PRE_SUBMIT STOP: confirmation prompt with submit still disabled.
  await page.waitForFunction(() => {
    const btns = Array.from(document.querySelectorAll(".chat-decision__button--primary"));
    return btns.some((b) => String(b.textContent || "").includes("제출하기"));
  }, null, { timeout: 90000 });

  const preSubmit = await page.evaluate(() => ({
    state: document.body.getAttribute("data-journey-state"),
    choreoState: document.body.getAttribute("data-choreography-state"),
    title: document.getElementById("mayor-write-title")?.value ?? null,
    content: document.getElementById("mayor-write-content")?.value ?? null,
    submit: (() => {
      const b = document.getElementById("btn-mayor-submit");
      return b ? { disabled: b.disabled, aria: b.getAttribute("aria-disabled") } : null;
    })(),
    preSubmitPanel: document.querySelector('[data-pre-submit="true"]') !== null,
    receiptVisible: document.querySelector('[data-receipt-route="mayor-complaint-receipt"]') !== null,
  }));
  assert.strictEqual(preSubmit.state, "complaint_write", "S7 PRE_SUBMIT: journey state must remain complaint_write");
  assert.ok(
    String(preSubmit.choreoState || "").startsWith("waiting"),
    `S7 PRE_SUBMIT: choreography must park at a waiting state, got ${preSubmit.choreoState}`,
  );
  assert.ok(preSubmit.title && preSubmit.title.length > 0, "S7 PRE_SUBMIT: proposal title must be written");
  assert.ok(preSubmit.content && preSubmit.content.length > 0, "S7 PRE_SUBMIT: proposal body must be written");
  assert.ok(preSubmit.submit, "S7 PRE_SUBMIT: submit button must exist");
  assert.strictEqual(preSubmit.submit.disabled, true, "S7 PRE_SUBMIT: submit button must be disabled");
  assert.strictEqual(preSubmit.submit.aria, "true", "S7 PRE_SUBMIT: submit must keep aria-disabled=true");
  assert.ok(preSubmit.preSubmitPanel, "S7 PRE_SUBMIT: form panel must carry data-pre-submit=true");
  assert.strictEqual(preSubmit.receiptVisible, false, "S7 PRE_SUBMIT: receipt must not render before resident confirmation");

  // Duplicate activation while the choreography owns the flow is refused.
  await page.locator(CHIP).click();
  await waitForState(page, "answer");
  await waitForState(page, "confirm");
  await clickYes(page);
  await page.waitForFunction(() =>
    document.getElementById("chat-thread").innerText.includes("이미 민원 작성 안내가 진행 중입니다."),
  null, { timeout: 30000 });

  const afterDuplicate = await page.evaluate(() => ({
    state: document.body.getAttribute("data-journey-state"),
    title: document.getElementById("mayor-write-title")?.value ?? null,
    submitDisabled: document.getElementById("btn-mayor-submit")?.disabled ?? null,
    choreoState: window.CitizenFirstChoreography.getState(),
  }));
  assert.strictEqual(afterDuplicate.state, "complaint_write", "S7 duplicate activation must stay on the writing axis");
  assert.strictEqual(afterDuplicate.title, preSubmit.title, "S7 duplicate activation must preserve the draft title");
  assert.strictEqual(afterDuplicate.submitDisabled, true, "S7 duplicate activation must keep submit disabled");
  assert.strictEqual(afterDuplicate.choreoState, preSubmit.choreoState, "S7 duplicate activation must not restart the choreography");

  // Resident confirms at PRE_SUBMIT → engine commits visually → receipt.
  await page
    .locator(".chat-decision__button--primary")
    .filter({ hasText: "제출하기" })
    .first()
    .click();

  await page.waitForFunction(() =>
    document.querySelector('[data-receipt-route="mayor-complaint-receipt"]') !== null,
  null, { timeout: 30000 });

  const receipt = await page.evaluate(() => ({
    state: document.body.getAttribute("data-journey-state"),
    summary: document.querySelector("[data-receipt-summary]")?.innerText ?? "",
    threadText: document.getElementById("chat-thread").innerText,
    canvasText: document.getElementById("demo-canvas").innerText,
    epeopleAnywhere: (document.getElementById("chat-thread").innerText +
      document.getElementById("demo-canvas").innerText).includes("epeople"),
  }));
  assert.ok(receipt.summary.includes("공식 제출 전"), "S7 receipt must declare 공식 제출 전");
  assert.ok(receipt.summary.includes("공식 채널에서 확인 및 제출"), "S7 receipt must point to the official channel next step");
  assert.ok(
    receipt.canvasText.includes("서구청 공식 채널에서 시민이 직접 확인하고 진행합니다"),
    "S7 receipt must carry the truthful 서구청 official-channel boundary line",
  );
  assert.strictEqual(receipt.epeopleAnywhere, false, "S7 must not surface any external-channel reference");
  assertNoForbiddenSuccess(receipt.threadText, "S7 receipt thread");
  assertNoForbiddenSuccess(receipt.canvasText, "S7 receipt surface");

  await context.close();
}

try {
  const browser = await launchBrowser();
  const results = {};

  await proveNoPathStops(browser);
  results.S7_NO_STOP = "PASS";
  await proveEvidenceFailureStops(browser);
  results.S7_EVIDENCE_FAILURE_STOP = "PASS";
  await proveWriteFlowAndDuplicateRefused(browser);
  results.S7_WRITE_FLOW_PRE_SUBMIT_RECEIPT = "PASS";

  await browser.close();

  assert.deepStrictEqual(externalRequests, [], "S7 proof must make zero external requests");
  results.EXTERNAL_REQUESTS = externalRequests.length;

  console.log("SEOGU_S7_MAYOR_PROPOSAL_E2E PASS");
  console.log(JSON.stringify(results, null, 2));
} catch (err) {
  console.error("SEOGU_S7_MAYOR_PROPOSAL_E2E FAIL");
  console.error(err.stack || err.message);
  process.exit(1);
}
