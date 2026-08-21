/**
 * #1364 Lane B — Seo-gu S3/S4 complaint-writing safety contract (browser E2E).
 *
 * Runs against an ALREADY-SERVED localhost build (dist/cloudflare-pages) and
 * proves the SAFETY half of the evidence-gated complaint-writing flows that
 * verify_seogu_resident_surface_focused_e2e.mjs covers for the happy path:
 *
 *   For BOTH S3 (seogu_streetlight_report / COMPLAINT_BOARD_WRITE) and
 *   S4 (seogu_illegal_dumping_report / COMPLAINT_AI_ASSIST):
 *
 *   A. NO path stops: chip → ANSWER → CONFIRM → NO returns to answer with
 *      zero navigation, no complaint surface, no choreography start, null
 *      journey result, zero external requests.
 *   B. Evidence failure stops: with ONE required gate marker deterministically
 *      stripped from the served clone page, YES ends fail-closed at
 *      handoff_evidence_failed — blocked STOP row carries the configured
 *      COMPLAINT_EVIDENCE_GATE boundary, and NO complaint surface, NO
 *      choreography start, no destination control, no model fallback.
 *   C. PRE_SUBMIT STOP: on the happy path the choreography parks at a waiting
 *      state with #btn-board-submit disabled (attribute AND behaviour: a
 *      forced click must not navigate, submit, or mutate the draft), the form
 *      panel keeps data-pre-submit=true, and the whole thread stays free of
 *      fake receipt/success semantics.
 *   D. No duplicate activation: while the choreography owns the flow, a second
 *      full CONFIRM → YES activation is refused ("이미 민원 작성 안내가
 *      진행 중입니다."), the draft is preserved, exactly one complaint view
 *      host exists, and the submit button remains disabled.
 *   E. Zero external HTTP(S) runtime requests across every scenario.
 *
 * Usage: node verify_seogu_complaint_s3s4_e2e.mjs <LOCAL_BASE_URL>
 */
import assert from "assert";
import { chromium } from "playwright";

const BASE_ORIGIN = localOrigin(process.argv[2]);
const DEMO_URL = `${BASE_ORIGIN}/static/seogu-citizen-action-demo.html`;

const FLOWS = Object.freeze([
  {
    id: "S3",
    jid: "seogu_streetlight_report",
    selector: '[data-journey-id="seogu_streetlight_report"]',
    gate_route: "streetlight-report-handoff",
    missing_marker: "재난신고센터",
    control_marker: "재난신고",
    has_choice: false,
  },
  {
    id: "S4",
    jid: "seogu_illegal_dumping_report",
    selector: '[data-journey-id="seogu_illegal_dumping_report"]',
    gate_route: "litter-report-handoff",
    missing_marker: "대형폐기물 신고",
    control_marker: "생활폐기물",
    has_choice: true,
  },
]);

// Strings that would indicate a fake submission success (strictly forbidden).
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
    throw new Error("usage: node verify_seogu_complaint_s3s4_e2e.mjs <BASE_URL>");
  }
  const url = new URL(raw);
  if (!["127.0.0.1", "localhost", "::1"].includes(url.hostname)) {
    throw new Error(`complaint gate requires localhost base, got ${url.hostname}`);
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
async function proveNoPathStops(browser, flow) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  installEgressGuard(context);
  const page = await openDemo(context);

  await page.locator(`.chat-chip${flow.selector}`).click();
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
    complaintViewHosts: document.querySelectorAll("[data-seogu-complaint-view]").length,
    boardRendered: document.querySelector('[data-complaint-route="complaint-board"]') !== null,
    writeRendered: document.querySelector('[data-complaint-route="complaint-write"]') !== null,
    safeHandoffRows: document.querySelectorAll('[data-safe-handoff="true"]').length,
    handoffEvidenceRows: document.querySelectorAll('[data-handoff-evidence="true"]').length,
    choreoState: window.CitizenFirstChoreography ? window.CitizenFirstChoreography.getState() : null,
    threadText: document.getElementById("chat-thread").innerText,
  }));

  assert.strictEqual(after.state, "answer", `${flow.id} NO: must stop at answer`);
  assert.strictEqual(after.resultNull, true, `${flow.id} NO: journey result must stay null`);
  assert.strictEqual(after.complaintViewHosts, 0, `${flow.id} NO: complaint surface must not render`);
  assert.strictEqual(after.boardRendered, false, `${flow.id} NO: complaint board must not render`);
  assert.strictEqual(after.writeRendered, false, `${flow.id} NO: complaint write must not render`);
  assert.strictEqual(after.safeHandoffRows, 0, `${flow.id} NO: no destination row may exist`);
  assert.strictEqual(after.handoffEvidenceRows, 0, `${flow.id} NO: evidence gate must not run`);
  assert.strictEqual(after.choreoState, "idle", `${flow.id} NO: choreography must never start`);
  assertNoForbiddenSuccess(after.threadText, `${flow.id} NO thread`);

  await context.close();
  return true;
}

// ── B. Evidence failure stops ───────────────────────────────────────────────
async function proveEvidenceFailureStops(browser, flow) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  installEgressGuard(context);

  // Fetch the ORIGINAL gate page BEFORE registering interception, then strip
  // ONE required marker from every occurrence so the READ region provably
  // lacks it while the page demonstrably loaded (control marker present).
  const original = await context.request.get(`${BASE_ORIGIN}/seogu/${flow.gate_route}/`);
  assert.strictEqual(original.status(), 200, `${flow.id} gate page must be served`);
  const strippedBody = (await original.text())
    .split(flow.missing_marker)
    .join("_STRIPPED_BY_TEST_");

  const page = await openDemo(context);
  const interceptUrl = `${BASE_ORIGIN}/seogu/${flow.gate_route}/`;
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

  await page.locator(`.chat-chip${flow.selector}`).click();
  await waitForState(page, "answer");
  await waitForState(page, "confirm");
  await clickYes(page);
  await waitForState(page, "handoff_evidence_failed");

  // Deterministic precondition: stripped marker absent, control marker present.
  const pre = await page.evaluate(() => {
    const frame = document.getElementById("seogu-clone-frame");
    const doc = frame.contentDocument;
    const main = doc && doc.querySelector("main.rc-main");
    return main ? main.innerText : "";
  });
  assert.ok(pre.includes(flow.control_marker), `${flow.id} gate page must have loaded (control marker present)`);
  assert.ok(!pre.includes(flow.missing_marker), `${flow.id} forced marker must be absent from the READ region`);

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
        text: el.textContent,
      } : null,
      safeHandoffRows: document.querySelectorAll('[data-safe-handoff="true"]').length,
      explicitOpenAnchors: document.querySelectorAll('[data-handoff-action="explicit-open"]').length,
      destinationAttrs: document.querySelectorAll("[data-handoff-destination-url]").length,
      complaintViewHosts: document.querySelectorAll("[data-seogu-complaint-view]").length,
      boardRendered: document.querySelector('[data-complaint-route="complaint-board"]') !== null,
      writeRendered: document.querySelector('[data-complaint-route="complaint-write"]') !== null,
      choreoState: window.CitizenFirstChoreography ? window.CitizenFirstChoreography.getState() : null,
      generalFallbackOffers: document.querySelectorAll('[data-general-fallback-offer="true"]').length,
      threadText: document.getElementById("chat-thread").innerText,
    };
  }, flow.jid);

  assert.strictEqual(after.state, "handoff_evidence_failed", `${flow.id} failed gate must expose the fail-closed state`);
  assert.ok(after.blocked, `${flow.id} failed gate must render the bounded STOP row`);
  assert.strictEqual(after.blocked.action_kind, "COMPLAINT_EVIDENCE_GATE", `${flow.id} STOP row must keep the gate action_kind`);
  assert.strictEqual(after.blocked.claim_scope, "EVIDENCE_GATE_ONLY", `${flow.id} STOP row must keep EVIDENCE_GATE_ONLY scope`);
  assert.strictEqual(after.blocked.stop_boundary, "COMPLAINT_EVIDENCE_FAILED_STOP", `${flow.id} STOP row must carry the configured boundary code`);
  assert.strictEqual(after.blocked.hasAnchor, false, `${flow.id} STOP row must contain no anchor`);
  assert.strictEqual(after.blocked.hasFormControl, false, `${flow.id} STOP row must contain no form control`);
  assert.strictEqual(after.safeHandoffRows, 0, `${flow.id} failed gate must render no destination row`);
  assert.strictEqual(after.explicitOpenAnchors, 0, `${flow.id} failed gate must render no explicit-open anchor`);
  assert.strictEqual(after.destinationAttrs, 0, `${flow.id} failed gate must render no destination URL attribute`);
  assert.strictEqual(after.complaintViewHosts, 0, `${flow.id} failed gate must not open the complaint surface`);
  assert.strictEqual(after.boardRendered, false, `${flow.id} failed gate must not render the complaint board`);
  assert.strictEqual(after.writeRendered, false, `${flow.id} failed gate must not render the write form`);
  assert.strictEqual(after.choreoState, "idle", `${flow.id} failed gate must not start the choreography`);
  assert.strictEqual(after.generalFallbackOffers, 0, `${flow.id} failed gate must not offer the general-model fallback`);
  assertNoForbiddenSuccess(after.blocked.text, `${flow.id} STOP row`);
  assertNoForbiddenSuccess(after.threadText, `${flow.id} failed-gate thread`);

  await context.close();
  return true;
}

// ── C + D. PRE_SUBMIT STOP, disabled submit, duplicate activation refused ───
async function provePreSubmitStopAndDuplicateRefused(browser, flow) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  installEgressGuard(context);
  const page = await openDemo(context);

  // Happy path to PRE_SUBMIT.
  await page.locator(`.chat-chip${flow.selector}`).click();
  await waitForState(page, "answer");
  await waitForState(page, "confirm");
  await clickYes(page);
  await waitForState(page, "complaint_write", 30000);

  if (flow.has_choice) {
    // Scope by prompt text: the confirm-gate YES shares
    // .chat-decision__button--primary but is disabled after its own click.
    await page
      .locator(".chat-decision__button--primary")
      .filter({ hasText: "AI 도움" })
      .first()
      .click();
  }
  await page.waitForFunction(() => {
    const btns = Array.from(document.querySelectorAll(".chat-decision__button--primary"));
    return btns.some((b) => String(b.textContent || "").includes("제출하기"));
  }, null, { timeout: 90000 });

  const preSubmit = await page.evaluate(() => ({
    state: document.body.getAttribute("data-journey-state"),
    choreoState: document.body.getAttribute("data-choreography-state"),
    title: document.getElementById("board-write-title")?.value ?? null,
    content: document.getElementById("board-write-content")?.value ?? null,
    submit: (() => {
      const b = document.getElementById("btn-board-submit");
      return b ? { disabled: b.disabled, aria: b.getAttribute("aria-disabled") } : null;
    })(),
    preSubmitPanel: document.querySelector('[data-pre-submit="true"]') !== null,
    viewHosts: document.querySelectorAll("[data-seogu-complaint-view]").length,
  }));
  assert.strictEqual(preSubmit.state, "complaint_write", `${flow.id} PRE_SUBMIT: journey state must be complaint_write`);
  assert.ok(
    String(preSubmit.choreoState || "").startsWith("waiting"),
    `${flow.id} PRE_SUBMIT: choreography must park at a waiting state, got ${preSubmit.choreoState}`,
  );
  assert.ok(preSubmit.title && preSubmit.title.length > 0, `${flow.id} PRE_SUBMIT: draft title must be written`);
  assert.ok(preSubmit.content && preSubmit.content.length > 0, `${flow.id} PRE_SUBMIT: draft body must be written`);
  assert.ok(preSubmit.submit, `${flow.id} PRE_SUBMIT: submit button must exist`);
  assert.strictEqual(preSubmit.submit.disabled, true, `${flow.id} PRE_SUBMIT: submit button must be disabled`);
  assert.strictEqual(preSubmit.submit.aria, "true", `${flow.id} PRE_SUBMIT: submit must keep aria-disabled=true`);
  assert.ok(preSubmit.preSubmitPanel, `${flow.id} PRE_SUBMIT: form panel must carry data-pre-submit=true`);
  assert.strictEqual(preSubmit.viewHosts, 1, `${flow.id} PRE_SUBMIT: exactly one complaint view host`);

  // Submit must be inert even under a forced programmatic click: no navigation,
  // no draft mutation, no success semantics, still parked at PRE_SUBMIT.
  await page.evaluate(() => document.getElementById("btn-board-submit").click());
  await page.waitForTimeout(500);
  const afterForcedClick = await page.evaluate(() => ({
    state: document.body.getAttribute("data-journey-state"),
    title: document.getElementById("board-write-title")?.value ?? null,
    content: document.getElementById("board-write-content")?.value ?? null,
    choreoState: window.CitizenFirstChoreography.getState(),
    threadText: document.getElementById("chat-thread").innerText,
  }));
  assert.strictEqual(afterForcedClick.state, "complaint_write", `${flow.id} forced submit click must not change the journey state`);
  assert.strictEqual(afterForcedClick.title, preSubmit.title, `${flow.id} forced submit click must not mutate the draft title`);
  assert.strictEqual(afterForcedClick.content, preSubmit.content, `${flow.id} forced submit click must not mutate the draft body`);
  assert.ok(
    String(afterForcedClick.choreoState || "").startsWith("waiting"),
    `${flow.id} forced submit click must not advance the choreography`,
  );
  assertNoForbiddenSuccess(afterForcedClick.threadText, `${flow.id} post-forced-click thread`);

  // Duplicate activation while the choreography owns the flow must be refused:
  // full CONFIRM → YES again → "이미 민원 작성 안내가 진행 중입니다." and the
  // draft/surface/state stay untouched.
  await page.locator(`.chat-chip${flow.selector}`).click();
  await waitForState(page, "answer");
  await waitForState(page, "confirm");
  await clickYes(page);
  await page.waitForFunction(() =>
    document.getElementById("chat-thread").innerText.includes("이미 민원 작성 안내가 진행 중입니다."),
  null, { timeout: 30000 });

  const afterDuplicate = await page.evaluate(() => ({
    state: document.body.getAttribute("data-journey-state"),
    title: document.getElementById("board-write-title")?.value ?? null,
    content: document.getElementById("board-write-content")?.value ?? null,
    submitDisabled: document.getElementById("btn-board-submit")?.disabled ?? null,
    viewHosts: document.querySelectorAll("[data-seogu-complaint-view]").length,
    choreoState: window.CitizenFirstChoreography.getState(),
    threadText: document.getElementById("chat-thread").innerText,
  }));
  assert.strictEqual(afterDuplicate.state, "complaint_write", `${flow.id} duplicate activation must stay on the complaint axis`);
  assert.strictEqual(afterDuplicate.title, preSubmit.title, `${flow.id} duplicate activation must preserve the draft title`);
  assert.strictEqual(afterDuplicate.content, preSubmit.content, `${flow.id} duplicate activation must preserve the draft body`);
  assert.strictEqual(afterDuplicate.submitDisabled, true, `${flow.id} duplicate activation must keep submit disabled`);
  assert.strictEqual(afterDuplicate.viewHosts, 1, `${flow.id} duplicate activation must not create a second complaint surface`);
  assert.strictEqual(afterDuplicate.choreoState, preSubmit.choreoState, `${flow.id} duplicate activation must not restart the choreography`);
  assertNoForbiddenSuccess(afterDuplicate.threadText, `${flow.id} post-duplicate thread`);

  await context.close();
  return true;
}

try {
  const browser = await launchBrowser();
  const results = {};

  for (const flow of FLOWS) {
    await proveNoPathStops(browser, flow);
    results[`${flow.id}_NO_STOP`] = "PASS";
    await proveEvidenceFailureStops(browser, flow);
    results[`${flow.id}_EVIDENCE_FAILURE_STOP`] = "PASS";
    await provePreSubmitStopAndDuplicateRefused(browser, flow);
    results[`${flow.id}_PRE_SUBMIT_AND_DUPLICATE_REFUSED`] = "PASS";
  }

  await browser.close();

  assert.deepStrictEqual(externalRequests, [], "S3/S4 complaint proof must make zero external requests");
  results.EXTERNAL_REQUESTS = externalRequests.length;

  console.log("SEOGU_COMPLAINT_S3S4_E2E PASS");
  console.log(JSON.stringify(results, null, 2));
} catch (err) {
  console.error("SEOGU_COMPLAINT_S3S4_E2E FAIL");
  console.error(err.stack || err.message);
  process.exit(1);
}
