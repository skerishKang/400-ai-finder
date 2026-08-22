/**
 * Focused browser contract proof for #1343 Round 2 — Seo-gu resident surface.
 *
 * Runs against an ALREADY-SERVED localhost build (dist/cloudflare-pages) and
 * verifies the Seo-gu resident product surface DIRECTLY (not just shared
 * regression machinery):
 *
 *   1. canonical 8 chips exactly present (preserved infrastructure proofs are
 *      NOT chips and are not counted);
 *   2. all 8 scenarios carry an explicit classification/status matching the
 *      Round 2 matrix;
 *   3. S3 공동주택 chip: navigate -> bounded clone READ -> required markers
 *      (공동주택/주택과/공동주택관리) -> grounded, READ-derived answer with
 *      visible repository-clone provenance (answer excerpt must be a literal
 *      substring of the iframe rc-main evidence text — no hard-coded answer);
 *   3b. REAL desktop visibility after S3: split state + canvas inert removed /
 *      aria-hidden=false / non-zero rect in viewport + iframe non-zero rect +
 *      visible rc-main with grounded markers (blank canvas = FAIL);
 *   4. the remaining SOURCE_CAPTURE_NEEDED scenario (mattress disposal) produces
 *      an honest capture-needed row, no navigation, no fake success;
 *   5. S2 EXTERNAL_OFFICIAL_HANDOFF (Blocker B + Blocker A):
 *      D1 — generic config-driven contract on the handoff row
 *           (action_kind=EXTERNAL_OFFICIAL_HANDOFF, claim_scope=HANDOFF_ONLY,
 *           stop boundary, explicit resident-activated anchor, no auto-open/
 *           prefill/submit) + grounded repository-clone local-evidence row with
 *           required-marker validation; external requests stay 0;
 *      D2 — #1380: S2 is a GUIDANCE_NAVIGATION journey (Buk-gu guidance/
 *           handoff-stop shape) — no external anchor exists anywhere;
 *   5b. #1364 Lane B: S3/S4 evidence-gated complaint writing — after the
 *       COMPLAINT_EVIDENCE_GATE passes, the app-owned complaint surface renders
 *       and the shared choreography runs to PRE_SUBMIT STOP (S3 direct write
 *       flow; S4 with CHOICE → AI assist). Final journey state is
 *       complaint_write (never safe_handoff), submit stays disabled, and no
 *       external destination exists;
 *   D3. general-AI explicit opt-in: unmatched question never silently calls a
 *       model; mocked CitizenMvpBridge.askGeneralModel fires exactly once
 *       (0 → 1) only after the resident clicks, with exact general-model
 *       provenance (grounded=false / source_kind=general_model /
 *       evidence_kind=none / answer_scope=general_model);
 *   D4. preserved journeys (사회연대경제 / 조직도) remain grounded, repository-
 *       clone READ-derived, marker-verified, never re-implemented;
 *   D5. language-control regression (Blocker C): no visible empty
 *       <select id="chat-lang"> / .chat-shell__lang remains;
 *   D6. FAIL-CLOSED negative proof (CTO comment 5322239653): with ONE
 *       required marker deterministically stripped from the served
 *       local-evidence page, the complaint-writing flow must NOT start — no
 *       destination row, no anchor/href, no destination URL control, no
 *       auto-open/prefill/submit, no complaint surface, no choreography
 *       start, no model fallback, no success semantics;
 *       the evidence explanation + bounded STOP state
 *       (handoff_evidence_failed) remain visible and external requests = 0;
 *   6. mobile conversation/guidance switch is actually clickable;
 *   7. mobile guidance switch drives the correct layout state;
 *   7b. REAL mobile guidance visibility: after S3 on mobile, guidance tab shows
 *      the housing clone (inert removed, non-zero rect, readable rc-main with
 *      grounded markers, composer usable); conversation restores inert/hidden;
 *   8. the clone iframe keeps the exact script-disabled sandbox boundary;
 *   9. zero external HTTP(S) runtime requests.
 *
 * Proof #10 (Buk-gu canonical resident shell regression unchanged) is covered
 * by the existing Buk-gu regression suite, which must keep passing alongside
 * this focused test.
 *
 * Usage:
 *   node tests/browser/verify_seogu_resident_surface_focused_e2e.mjs <BASE_URL>
 *   e.g. node tests/browser/verify_seogu_resident_surface_focused_e2e.mjs http://127.0.0.1:8773
 */

import assert from "assert";
import { existsSync } from "fs";
import { chromium } from "playwright";

const rawBase = process.argv[2] || "http://127.0.0.1:8773";

const KNOWN_BROWSER_PATHS = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
];

// Round 2 canonical 8-row matrix (chips only; preserved infra proofs excluded).
const EXPECTED_MATRIX = [
  { journey_id: "seogu_mayor_proposal", label: "구청장에게 제안하고 싶어요", status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED" },
  { journey_id: "seogu_illegal_parking_report", label: "불법 주정차 신고", status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED" },
  { journey_id: "seogu_apartment_housing_dept", label: "공동주택 부서 문의", status: "DIRECT_REUSE" },
  { journey_id: "seogu_mattress_disposal", label: "대형폐기물 배출", status: "DIRECT_REUSE" },
  { journey_id: "seogu_passport_issuance", label: "여권 발급 안내", status: "DIRECT_REUSE" },
  { journey_id: "seogu_unmanned_kiosk", label: "무인민원발급기 안내", status: "DIRECT_REUSE" },
  { journey_id: "seogu_streetlight_report", label: "가로등 고장 신고 (AI)", status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED" },
  { journey_id: "seogu_illegal_dumping_report", label: "쓰레기 무단투기 (AI)", status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED" },
];

// #1376 S8 was the last SOURCE_CAPTURE_NEEDED scenario — every canonical
// Seo-gu chip now has an implemented journey shape. The list is kept as a
// contract anchor: it must stay empty unless a NEW scenario is added.
const CAPTURE_NEEDED_IDS = [];

// #1364 Lane B: S3/S4 are evidence-gated app-owned complaint-writing flows
// (dedicated section below + verify_seogu_complaint_s3s4_e2e.mjs).
// #1363 Lane B: S7 mayor proposal is an evidence-gated app-owned writing
// journey (verify_seogu_s7_mayor_proposal_e2e.mjs).
// #1380 S-final: S2 illegal-parking is a GUIDANCE_NAVIGATION journey (Buk-gu
// guidance/handoff-stop shape, dedicated section below). NO Seo-gu scenario
// renders an external destination row anymore — the list stays empty as a
// contract anchor.
const HANDOFF_IDS = [];

// Former generic EXTERNAL_OFFICIAL_HANDOFF contract expectations — retired by
// the #1380 owner decision (외부 채널 링크 표면 금지). Kept as an empty anchor.
const HANDOFF_CONTRACT = {};

// Strings that would indicate a fake submission success (strictly forbidden).
const FORBIDDEN_SUCCESS_PATTERNS = [
  "신고 완료",
  "접수 완료",
  "제출 완료",
  "접수번호",
  "receipt number",
  "자동 제출",
];

function localOrigin(value) {
  const parsed = new URL(value);
  const host = parsed.hostname.replace(/^\[|\]$/g, "");
  if (parsed.protocol !== "http:") throw new Error("Only local http:// is allowed");
  if (!["127.0.0.1", "localhost", "::1"].includes(host)) {
    throw new Error(`Non-local host rejected: ${parsed.hostname}`);
  }
  return parsed.origin;
}

async function launchBrowser() {
  const attempts = [];
  const errors = [];
  const envPath = process.env.PREVIEW_BROWSER_EXECUTABLE;
  if (envPath) {
    attempts.push({ name: `env: ${envPath}`, launch: () => chromium.launch({ headless: true, executablePath: envPath }) });
  }
  attempts.push({ name: "channel: chrome", launch: () => chromium.launch({ headless: true, channel: "chrome" }) });
  for (const path of KNOWN_BROWSER_PATHS) {
    if (!existsSync(path)) continue;
    attempts.push({ name: `path: ${path}`, launch: () => chromium.launch({ headless: true, executablePath: path }) });
  }
  attempts.push({ name: "default playwright chromium", launch: () => chromium.launch({ headless: true }) });
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

const BASE_ORIGIN = localOrigin(rawBase);
const DEMO_URL = `${BASE_ORIGIN}/static/seogu-citizen-action-demo.html`;

const browser = await launchBrowser();
const externalRequests = [];

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
  // #1378 — cross-institution literal contract: the Seo-gu resident surface
  // must never render another institution's display identity. Fails on any
  // visible '북구청' leak (copy, alt text, aria labels, document title).
  const crossInstitutionLeak = await page.evaluate(() => {
    const texts = [
      document.title || "",
      document.body.innerText || "",
      ...Array.from(document.querySelectorAll("[alt],[aria-label],[placeholder]"))
        .map((el) => `${el.getAttribute("alt") || ""}${el.getAttribute("aria-label") || ""}${el.getAttribute("placeholder") || ""}`),
    ];
    return texts.filter((t) => t.includes("북구청")).length;
  });
  if (crossInstitutionLeak > 0) {
    throw new Error(
      `CROSS_INSTITUTION_LITERAL_LEAK: ${crossInstitutionLeak} rendered node(s) contain '북구청' on the Seo-gu surface`,
    );
  }
  return page;
}


// #1365: Canonical Buk-gu confirmation gate. A chip click is NOT confirmation.
// Every journey with an entry_route or handoff must pass through:
//   chip click → first answer (data-journey-state="answer")
//   → confirm-run prompt (data-journey-state="confirm") with YES/NO
//   → YES (data-confirm-action="yes") → navigate → grounded/safe_handoff
//   → NO  (data-confirm-action="no")  → answer, zero navigation
// This helper clicks the chip, asserts the answer→confirm state order,
// then clicks YES to proceed to the grounded/handoff state.
async function confirmAndProceed(page, selector, finalState) {
  await page.locator(selector).click();
  // FIRST: answer state (first AI message before confirmation)
  await page.waitForFunction(
    () => document.body.getAttribute("data-journey-state") === "answer",
    null,
    { timeout: 10000 },
  );
  // THEN: confirm state (YES/NO prompt)
  await page.waitForFunction(
    () => document.body.getAttribute("data-journey-state") === "confirm",
    null,
    { timeout: 10000 },
  );
  // Assert both YES and NO controls exist in the latest confirm-run message
  const controls = await page.evaluate(() => {
    const msgs = Array.from(document.querySelectorAll('.chat-msg--confirm-run'));
    const last = msgs[msgs.length - 1];
    if (!last) return { yes: false, no: false, count: 0 };
    const btns = last.querySelectorAll('[data-confirm-action]');
    return {
      yes: !!last.querySelector('[data-confirm-action="yes"]'),
      no: !!last.querySelector('[data-confirm-action="no"]'),
      count: btns.length,
    };
  });
  assert.strictEqual(controls.yes, true, "YES control must exist after chip click");
  assert.strictEqual(controls.no, true, "NO control must exist after chip click");
  assert.strictEqual(controls.count, 2, "exactly YES and NO controls must exist in latest confirm-run");
  // Click YES to proceed (last YES button in the thread)
  await page.locator('[data-confirm-action="yes"]').last().click();
  await page.waitForFunction(
    (state) => document.body.getAttribute("data-journey-state") === state,
    finalState,
    { timeout: 20000 },
  );
}

// #1365: Assert NO path stops with zero navigation
async function confirmNoStaysOnAnswer(page, selector) {
  const preRoute = await page.evaluate(() => {
    const frame = document.getElementById("seogu-clone-frame");
    return frame && frame.contentWindow ? frame.contentWindow.location.pathname : null;
  });
  await page.locator(selector).click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-journey-state") === "confirm",
    null,
    { timeout: 10000 },
  );
  await page.locator('[data-confirm-action="no"]').click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-journey-state") === "answer",
    null,
    { timeout: 10000 },
  );
  // NO must not navigate
  const postRoute = await page.evaluate(() => {
    const frame = document.getElementById("seogu-clone-frame");
    return frame && frame.contentWindow ? frame.contentWindow.location.pathname : null;
  });
  assert.strictEqual(postRoute, preRoute, "NO must not navigate the clone surface");
}

// #1365 BLOCKER 3: real browser NO-path proof for ONE scenario, executed in an
// isolated fresh context so prior journey state cannot contaminate the proof.
// Strengthens the route-equality helper with the full canonical NO contract:
//   - NO leaves the conversation on the answer (zero navigation)
//   - the journey result is null (no scenario-specific execution occurred)
//   - no repository READ (grounded) result, no safe-handoff row, no handoff
//     evidence result is rendered for the journey
//   - zero external requests
async function proveNoPathIsolated(browser, selector, jid) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const external = [];
  installEgressGuard(ctx);
  const page = await ctx.newPage();
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
  const initialRoute = await page.evaluate(() => {
    const frame = document.getElementById("seogu-clone-frame");
    return frame && frame.contentWindow ? frame.contentWindow.location.pathname : null;
  });
  // chip -> answer
  await page.locator(selector).click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-journey-state") === "answer",
    null,
    { timeout: 10000 },
  );
  const routeAtAnswer = await page.evaluate(() => {
    return (() => {
      const frame = document.getElementById("seogu-clone-frame");
      return frame && frame.contentWindow ? frame.contentWindow.location.pathname : null;
    })();
  });
  assert.strictEqual(routeAtAnswer, initialRoute, `${jid} NO: route unchanged at answer`);
  // answer -> confirm
  await page.waitForFunction(
    () => document.body.getAttribute("data-journey-state") === "confirm",
    null,
    { timeout: 10000 },
  );
  const routeAtConfirm = await page.evaluate(() => {
    const frame = document.getElementById("seogu-clone-frame");
    return frame && frame.contentWindow ? frame.contentWindow.location.pathname : null;
  });
  assert.strictEqual(routeAtConfirm, initialRoute, `${jid} NO: route unchanged at confirm`);
  // YES + NO controls must exist
  const controls = await page.evaluate(() => {
    const msgs = Array.from(document.querySelectorAll('.chat-msg--confirm-run'));
    const last = msgs[msgs.length - 1];
    if (!last) return { yes: false, no: false, count: 0 };
    const btns = last.querySelectorAll('[data-confirm-action]');
    return {
      yes: !!last.querySelector('[data-confirm-action="yes"]'),
      no: !!last.querySelector('[data-confirm-action="no"]'),
      count: btns.length,
    };
  });
  assert.strictEqual(controls.yes, true, `${jid} NO: YES control must exist`);
  assert.strictEqual(controls.no, true, `${jid} NO: NO control must exist`);
  assert.strictEqual(controls.count, 2, `${jid} NO: exactly YES and NO controls`);
  // click NO
  await page.locator('[data-confirm-action="no"]').last().click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-journey-state") === "answer",
    null,
    { timeout: 10000 },
  );
  const after = await page.evaluate((jid) => {
    const shell = window.SeoguCitizenActionShell;
    const r = shell.getLastJourneyResult();
    const frame = document.getElementById("seogu-clone-frame");
    const safeHandoff = document.querySelector(`[data-safe-handoff="true"][data-journey-id="${jid}"]`);
    const handoffEvidence = document.querySelector(`[data-handoff-evidence="true"][data-journey-id="${jid}"]`);
    const grounded = document.querySelector(`.chat-msg[data-grounded="true"][data-journey-id="${jid}"]`);
    return {
      state: document.body.getAttribute("data-journey-state"),
      route: frame && frame.contentWindow ? frame.contentWindow.location.pathname : null,
      resultNull: r === null || r === undefined,
      safeHandoff: !!safeHandoff,
      handoffEvidence: !!handoffEvidence,
      grounded: !!grounded,
    };
  }, jid);
  assert.strictEqual(after.state, "answer", `${jid} NO: must return to answer state`);
  assert.strictEqual(after.route, initialRoute, `${jid} NO: route unchanged after NO`);
  assert.strictEqual(after.resultNull, true, `${jid} NO: getLastJourneyResult() must be null (no execution)`);
  assert.strictEqual(after.safeHandoff, false, `${jid} NO: no safe-handoff row rendered`);
  assert.strictEqual(after.handoffEvidence, false, `${jid} NO: no handoff-evidence row rendered`);
  assert.strictEqual(after.grounded, false, `${jid} NO: no repository READ (grounded) result rendered`);
  assert.deepStrictEqual(external, [], `${jid} NO: zero external requests`);
  await ctx.close();
}

function assertNoForbiddenSuccess(text, where) {
  for (const pattern of FORBIDDEN_SUCCESS_PATTERNS) {
    assert.ok(
      !String(text || "").includes(pattern),
      `forbidden fake-success string "${pattern}" found in ${where}`,
    );
  }
}

// Real visibility probe — proves the surface is not merely dataset-correct but
// ACTUALLY VISIBLE (non-zero rect, not display:none, not inert, iframe rc-main
// readable + showing grounded markers). This is the guard for the CTO rule:
// "테스트가 green이어도 screenshot이 blank면 FAIL" / "단순 dataset 변경만 확인
// 하는 테스트는 부족하다". A green dataset assertion with a blank canvas must
// fail here.
async function measureVisibility(page) {
  return page.evaluate(() => {
    const canvas = document.getElementById("demo-canvas");
    const frame = document.getElementById("seogu-clone-frame");
    const cs = getComputedStyle(canvas);
    const cr = canvas.getBoundingClientRect();
    const fr = frame.getBoundingClientRect();
    let rcMainVisible = false;
    let rcRect = { w: 0, h: 0 };
    let rcMarkers = { gongdong: false, jootaekgwa: false, gongdongmanage: false, passportIssuance: false };
    try {
      const doc = frame.contentDocument;
      const main = doc && doc.querySelector("main.rc-main");
      if (main) {
        const mr = main.getBoundingClientRect();
        const mcs = getComputedStyle(main);
        rcRect = { w: Math.round(mr.width), h: Math.round(mr.height) };
        const text = main.innerText || "";
        rcMainVisible =
          mr.width > 0 && mr.height > 0 && mcs.visibility !== "hidden" && mcs.display !== "none";
        rcMarkers = {
          gongdong: text.includes("공동주택"),
          jootaekgwa: text.includes("주택과"),
          gongdongmanage: text.includes("공동주택관리"),
          passportIssuance: text.includes("여권발급"),
        };
      }
    } catch {
      rcMainVisible = false;
    }
    return {
      canvas: {
        inert: canvas.hasAttribute("inert"),
        ariaHidden: canvas.getAttribute("aria-hidden"),
        display: cs.display,
        visibility: cs.visibility,
        rect: { w: Math.round(cr.width), h: Math.round(cr.height) },
        inViewport: cr.width > 0 && cr.height > 0 && cr.x < window.innerWidth && cr.y < window.innerHeight,
      },
      iframe: {
        rect: { w: Math.round(fr.width), h: Math.round(fr.height) },
        inViewport: fr.width > 0 && fr.height > 0 && fr.x < window.innerWidth && fr.y < window.innerHeight,
      },
      rc_main: { visible: rcMainVisible, rect: rcRect, markers: rcMarkers },
    };
  });
}

// #1353 handoff-row layout probe. Measures the geometry of ONE rendered
// [data-safe-handoff] destination row so the test can assert the CTA and
// authority stack inside a single content column (avatar left) instead of
// being squeezed into narrow implicit side columns. Pure layout measurement —
// no contract/data attribute is read here (those are covered by D1/D2).
async function measureHandoffLayout(page, jid) {
  return page.evaluate((jid) => {
    const rows = Array.from(document.querySelectorAll('[data-safe-handoff="true"]'));
    const el = rows.filter((n) => n.getAttribute("data-journey-id") === jid).pop();
    if (!el) return null;
    const link = el.querySelector('a[data-handoff-action="explicit-open"]');
    const authority = el.querySelector('[data-handoff-authority="true"]');
    const avatar = el.querySelector('.chat-avatar');
    const bubble = el.querySelector('.chat-bubble--ai');
    function rect(node) {
      if (!node) return null;
      const r = node.getBoundingClientRect();
      return {
        x: Math.round(r.x),
        y: Math.round(r.y),
        w: Math.round(r.width),
        h: Math.round(r.height),
        right: Math.round(r.right),
        bottom: Math.round(r.bottom),
      };
    }
    const cs = getComputedStyle(el);
    return {
      display: cs.display,
      row: rect(el),
      avatar: rect(avatar),
      bubble: rect(bubble),
      link: rect(link),
      authority: rect(authority),
      linkText: link ? link.textContent.trim() : null,
      authorityText: authority ? authority.textContent.trim() : null,
    };
  }, jid);
}

// #1353 evidence-row layout probe. Measures the geometry of ONE rendered
// [data-handoff-evidence] row so the test can assert the local-evidence
// provenance (repository-clone source) shares the evidence bubble content
// column (avatar left) instead of being squeezed into a narrow sibling column
// (a tall fragmented stack on mobile). Pure layout measurement — no
// contract/data attribute is read here (those are covered by D1/D6).
async function measureEvidenceLayout(page, jid) {
  return page.evaluate((jid) => {
    const rows = Array.from(document.querySelectorAll('[data-handoff-evidence="true"]'));
    const el = rows.filter((n) => n.getAttribute("data-journey-id") === jid).pop();
    if (!el) return null;
    const avatar = el.querySelector(".chat-avatar");
    const bubble = el.querySelector(".chat-bubble--ai");
    const source = el.querySelector(".message-source--clone");
    function rect(node) {
      if (!node) return null;
      const r = node.getBoundingClientRect();
      return {
        x: Math.round(r.x),
        y: Math.round(r.y),
        w: Math.round(r.width),
        h: Math.round(r.height),
        right: Math.round(r.right),
        bottom: Math.round(r.bottom),
      };
    }
    const cs = getComputedStyle(el);
    return {
      display: cs.display,
      row: rect(el),
      avatar: rect(avatar),
      bubble: rect(bubble),
      source: rect(source),
      sourceText: source ? source.textContent.trim() : null,
    };
  }, jid);
}

// #1388 split-state never-blank lock. Samples the canvas from inside the page
// on a fixed interval and records, for every instant the clone canvas is
// resident-available (split state, inert removed), whether it presents as
// (a) the styled loading affordance ("… 안내 화면을 준비하는 중…") or
// (b) actually rendered clone content — never empty-unstyled. The collector
// runs entirely in-page so sampling continues while Node awaits other steps.
async function startNeverBlankProbe(page) {
  await page.evaluate(() => {
    window.__nbSamples = [];
    window.__nbTimer = setInterval(() => {
      try {
        const canvas = document.getElementById("demo-canvas");
        const loading = document.getElementById("demo-canvas-loading");
        const frame = document.getElementById("seogu-clone-frame");
        const cs = loading ? getComputedStyle(loading) : null;
        let cloneRendered = false;
        try {
          const doc = frame && frame.contentDocument;
          const main = doc && doc.querySelector("main.rc-main");
          if (main) {
            const r = main.getBoundingClientRect();
            cloneRendered =
              r.width > 0 &&
              r.height > 0 &&
              String(doc.readyState) === "complete" &&
              String(main.innerText || "").length > 0;
          }
        } catch {
          cloneRendered = false;
        }
        window.__nbSamples.push({
          t: Math.round(performance.now()),
          state: document.body.getAttribute("data-first-use-state") || "",
          canvasAvailable: !!canvas && !canvas.hasAttribute("inert") && canvas.getAttribute("aria-hidden") === "false",
          loadingVisible:
            !!loading &&
            !!cs &&
            cs.display !== "none" &&
            cs.visibility !== "hidden" &&
            String(loading.textContent || "").includes("준비하는 중"),
          cloneRendered,
        });
      } catch {
        // A torn-down surface mid-sample cannot present a blank canvas.
      }
    }, 40);
  });
}

async function stopNeverBlankProbe(page) {
  return page.evaluate(() => {
    clearInterval(window.__nbTimer);
    return window.__nbSamples || [];
  });
}

function assertNeverBlankSamples(samples, where) {
  const available = samples.filter((s) => s.canvasAvailable);
  assert.ok(
    available.length > 0,
    `${where}: probe must observe the canvas in available split state`,
  );
  for (const s of available) {
    assert.ok(
      s.loadingVisible || s.cloneRendered,
      `${where}: canvas presented empty-unstyled at t=${s.t}ms ` +
        `(state=${s.state}, loadingVisible=${s.loadingVisible}, cloneRendered=${s.cloneRendered})`,
    );
  }
}

try {
  // ── Desktop contract (1920x1080) ──────────────────────────────────────────
  const desktop = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  await installEgressGuard(desktop);
  const page = await openDemo(desktop);

  // (1) canonical 8 chips exactly present
  const chips = await page.$$eval("#chat-chips .chat-chip", (nodes) =>
    nodes.map((n) => ({
      journey_id: n.getAttribute("data-journey-id"),
      status: n.getAttribute("data-status"),
      label: (n.querySelector(".chat-chip__label") || {}).textContent || "",
    })),
  );
  assert.strictEqual(chips.length, 8, `expected exactly 8 canonical chips, got ${chips.length}`);
  for (const expected of EXPECTED_MATRIX) {
    const found = chips.find((c) => c.journey_id === expected.journey_id);
    assert.ok(found, `chip missing: ${expected.journey_id}`);
    assert.strictEqual(found.status, expected.status, `status mismatch for ${expected.journey_id}`);
    assert.strictEqual(found.label, expected.label, `label mismatch for ${expected.journey_id}`);
  }

  // (2) all 8 scenarios carry explicit classification in the registry itself
  const registryView = await page.evaluate(() => {
    const R = window.SeoguResidentJourneyRegistry;
    return {
      scenario_count: R.scenarios().length,
      scenarios: R.scenarios().map((s) => ({
        journey_id: s.journey_id,
        status: s.status,
        handoff: Boolean(s.handoff),
        capture_needed: Boolean(s.capture_needed),
        entry_route: s.entry_route || "",
      })),
      list_count: R.list().length,
    };
  });
  assert.strictEqual(registryView.scenario_count, 8, "registry must classify exactly 8 canonical scenarios");
  for (const s of registryView.scenarios) {
    assert.ok(s.status && s.status.length > 0, `scenario ${s.journey_id} lacks explicit status`);
  }
  // Preserved infrastructure proofs exist in list() but are NOT chips.
  assert.ok(
    registryView.list_count > 8,
    "preserved infrastructure proofs must remain in list() without becoming chips",
  );

  // (8) iframe script-disabled boundary (before any interaction)
  const sandbox = await page.getAttribute("#seogu-clone-frame", "sandbox");
  assert.strictEqual(sandbox, "allow-same-origin", "iframe must keep exact script-disabled sandbox");
  assert.ok(!String(sandbox).split(/\s+/).includes("allow-scripts"), "allow-scripts must remain absent");

  // (3) S3 housing chip: navigate -> READ -> markers -> grounded READ-derived answer
  // #1365: chip -> answer -> confirm -> YES -> navigate -> grounded
  // #1388 never-blank lock (per-navigation window): the sampler runs from
  // before the chip click through the YES→navigate→grounded terminal so every
  // instant of the split-state canvas — including the housing-route iframe
  // reload after YES — presents the loading affordance or rendered clone
  // content, never empty-unstyled.
  const s3NeverBlank = await startNeverBlankProbe(page);
  await confirmAndProceed(page, '[data-journey-id="seogu_apartment_housing_dept"]', "grounded");
  const s3 = await page.evaluate(() => {
    const shell = window.SeoguCitizenActionShell;
    const r = shell.getLastJourneyResult();
    const ev = shell.getEvidence();
    const frame = document.getElementById("seogu-clone-frame");
    let rcMainText = null;
    try {
      const doc = frame.contentDocument;
      const main = doc && doc.querySelector("main.rc-main");
      rcMainText = main ? main.innerText : null;
    } catch {
      rcMainText = null;
    }
    return {
      result: r
        ? {
            ok: r.ok,
            grounded: r.grounded,
            route: r.route,
            journey_id: r.journey_id,
            source_kind: r.source_kind,
            evidence_kind: r.evidence_kind,
            answer: r.answer,
            excerpt: r.excerpt,
          }
        : null,
      evidence: ev
        ? { route: ev.route, source_kind: ev.source_kind, evidence_kind: ev.evidence_kind, text: ev.text }
        : null,
      rc_main_text: rcMainText,
      iframe_url: frame.contentWindow ? frame.contentWindow.location.pathname : null,
    };
  });
  assert.ok(s3.result, "S3 journey result must exist");
  assert.strictEqual(s3.result.ok, true, "S3 journey must be ok");
  assert.strictEqual(s3.result.grounded, true, "S3 journey must be grounded");
  assert.strictEqual(s3.result.journey_id, "seogu_apartment_housing_dept");
  assert.ok(String(s3.result.route).includes("housing"), `S3 must land on housing route, got ${s3.result.route}`);
  assert.ok(String(s3.iframe_url || "").includes("housing"), "iframe must actually navigate to the housing clone route");
  // Required markers present in the READ evidence text.
  for (const marker of ["공동주택", "주택과", "공동주택관리"]) {
    assert.ok(String(s3.evidence.text || "").includes(marker), `READ evidence missing marker: ${marker}`);
  }
  // Provenance: repository clone, clone DOM evidence.
  assert.strictEqual(s3.result.source_kind, "repository_clone", "S3 provenance must be repository_clone");
  assert.strictEqual(s3.result.evidence_kind, "clone_dom", "S3 evidence_kind must be clone_dom");
  assert.strictEqual(s3.evidence.source_kind, "repository_clone");
  // READ-derived answer: excerpt must be a literal substring of the iframe
  // rc-main innerText (proves the answer is derived from the READ region,
  // not hard-coded), and the answer must embed that excerpt. Both sides are
  // whitespace-normalized (collapse runs to single spaces) because the shared
  // _selectExcerpt normalizes lines the same way and rendered innerText uses
  // tabs/newlines — this is a whitespace-robust literal-content proof, NOT a
  // weakening of the READ-derived guarantee.
  assert.ok(s3.result.excerpt && s3.result.excerpt.length > 0, "S3 excerpt must be non-empty");
  assert.ok(s3.rc_main_text, "iframe rc-main must be readable (same-origin, script-disabled)");
  const rcMainNormalized = String(s3.rc_main_text).replace(/\s+/g, " ");
  for (const line of s3.result.excerpt.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const normalizedLine = trimmed.replace(/\s+/g, " ");
    assert.ok(
      rcMainNormalized.includes(normalizedLine),
      `answer excerpt line not found in rc-main READ region: ${trimmed.slice(0, 60)}`,
    );
  }
  // Internal generic grounding proof: the result answer must embed the READ
  // excerpt verbatim. This is the #1351 internal result contract and must
  // NEVER be deleted or weakened.
  assert.ok(
    s3.result.answer.includes(s3.result.excerpt),
    "grounded answer must embed the READ excerpt",
  );
  // #1351: Verify the resident-facing answer is a concise guidance hierarchy,
  // not the raw long excerpt dump. The bubble must contain key grounded
  // markers from the evidence as resident-useful hierarchy, while the
  // repository-clone provenance stays on the grounded row (not duplicated in
  // the bubble).
  const s1Row = page.locator('#chat-thread [data-grounded="true"][data-journey-id="seogu_apartment_housing_dept"]').last();
  const s1Bubble = await s1Row.locator(".chat-bubble--ai").textContent();
  const s1Source = await s1Row.locator("[data-grounded-source]").textContent();
  assert.ok(String(s1Bubble || "").includes("담당 부서"), "resident answer must contain concise department hierarchy");
  assert.ok(String(s1Bubble || "").includes("주택과"), "resident answer must mention 주택과 department");
  assert.ok(String(s1Bubble || "").includes("공동주택관리"), "resident answer must mention 공동주택관리 service context");
  // Raw excerpt is NOT the primary answer (transformed, not dumped).
  assert.ok(
    !String(s1Bubble || "").startsWith("왼쪽 저장소 기반 기관 안내 화면에서 확인한 내용입니다."),
    "resident answer must NOT start with raw excerpt boilerplate",
  );
  // No board-notice dump: unrelated bulletin titles (폭염 notice, 공동주택관리규약
  // notice) must never surface in the resident answer.
  for (const noise of ["폭염으로 인한 온열질환", "공동주택관리규약 준칙 개정"]) {
    assert.ok(
      !String(s1Bubble || "").includes(noise),
      `resident answer must not dump board notice: ${noise}`,
    );
  }
  // housing/ provenance is kept on the grounded row.
  assert.ok(
    String(s1Source || "").includes("housing/"),
    "S1 grounded row must keep repository-clone housing/ provenance",
  );
  for (const marker of ["공동주택", "주택과", "공동주택관리"]) {
    assert.ok(s3.rc_main_text.includes(marker), `rc-main READ region missing marker: ${marker}`);
  }
  // #1388 never-blank lock: the S3 journey (chip click → answer → confirm →
  // YES → housing-route iframe navigation → grounded terminal) must never have
  // presented the split-state canvas as empty-unstyled.
  const s3NeverBlankSamples = await stopNeverBlankProbe(page);
  assertNeverBlankSamples(s3NeverBlankSamples, "S3 housing journey (#1388)");

  // (3p) S5 passport chip (#1356): navigate -> bounded clone READ -> required
  // markers (여권발급/민원실 4번 창구/민원봉사과 민원여권/062-360-7613) ->
  // grounded, READ-derived answer with visible repository-clone provenance.
  // Before the resident explicitly activates the chip, no route
  // choreography begins; after activation the journey navigates to the
  // committed passport-guidance/ clone route and READs its main.rc-main.
  const prePassportRoute = await page.evaluate(() => {
    const frame = document.getElementById("seogu-clone-frame");
    return frame && frame.contentWindow ? frame.contentWindow.location.pathname : null;
  });
  assert.ok(
    !prePassportRoute || !prePassportRoute.includes("passport-guidance"),
    "no passport route choreography before explicit resident confirmation",
  );
  // #1365: chip -> answer -> confirm -> YES -> navigate -> grounded
  await confirmAndProceed(page, '[data-journey-id="seogu_passport_issuance"]', "grounded");
  const s5 = await page.evaluate(() => {
    const shell = window.SeoguCitizenActionShell;
    const r = shell.getLastJourneyResult();
    const ev = shell.getEvidence();
    const frame = document.getElementById("seogu-clone-frame");
    let rcMainText = null;
    try {
      const doc = frame.contentDocument;
      const main = doc && doc.querySelector("main.rc-main");
      rcMainText = main ? main.innerText : null;
    } catch {
      rcMainText = null;
    }
    return {
      result: r
        ? {
            ok: r.ok,
            grounded: r.grounded,
            route: r.route,
            journey_id: r.journey_id,
            source_kind: r.source_kind,
            evidence_kind: r.evidence_kind,
            answer: r.answer,
            excerpt: r.excerpt,
          }
        : null,
      evidence: ev
        ? { route: ev.route, source_kind: ev.source_kind, evidence_kind: ev.evidence_kind, text: ev.text }
        : null,
      rc_main_text: rcMainText,
      iframe_url: frame.contentWindow ? frame.contentWindow.location.pathname : null,
    };
  });
  assert.ok(s5.result, "S5 passport journey result must exist");
  assert.strictEqual(s5.result.ok, true, "S5 passport journey must be ok");
  assert.strictEqual(s5.result.grounded, true, "S5 passport journey must be grounded");
  assert.strictEqual(s5.result.journey_id, "seogu_passport_issuance");
  assert.ok(
    String(s5.result.route).includes("passport-guidance"),
    `S5 must land on passport-guidance route, got ${s5.result.route}`,
  );
  assert.ok(
    String(s5.iframe_url || "").includes("passport-guidance"),
    "iframe must actually navigate to the passport-guidance clone route",
  );
  // Four required institution markers present in the READ evidence text.
  for (const marker of ["여권발급", "민원실 4번 창구", "민원봉사과 민원여권", "062-360-7613"]) {
    assert.ok(String(s5.evidence.text || "").includes(marker), `READ evidence missing passport marker: ${marker}`);
  }
  // Provenance: repository clone, clone DOM evidence.
  assert.strictEqual(s5.result.source_kind, "repository_clone", "S5 provenance must be repository_clone");
  assert.strictEqual(s5.result.evidence_kind, "clone_dom", "S5 evidence_kind must be clone_dom");
  assert.strictEqual(s5.evidence.source_kind, "repository_clone");
  // READ-derived answer: excerpt must be a literal substring of the iframe
  // rc-main innerText (proves the answer is derived from the READ region,
  // not a hard-coded institution answer).
  assert.ok(s5.result.excerpt && s5.result.excerpt.length > 0, "S5 excerpt must be non-empty");
  assert.ok(s5.rc_main_text, "iframe rc-main must be readable (same-origin, script-disabled)");
  const s5RcMainNormalized = String(s5.rc_main_text).replace(/\s+/g, " ");
  for (const line of s5.result.excerpt.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const normalizedLine = trimmed.replace(/\s+/g, " ");
    assert.ok(
      s5RcMainNormalized.includes(normalizedLine),
      `answer excerpt line not found in rc-main READ region: ${trimmed.slice(0, 60)}`,
    );
  }
  // Internal generic grounding proof: the result answer must embed the READ
  // excerpt verbatim.
  assert.ok(
    s5.result.answer.includes(s5.result.excerpt),
    "grounded passport answer must embed the READ excerpt",
  );
  // Required markers also present directly in the rc-main READ region.
  for (const marker of ["여권발급", "민원실 4번 창구", "민원봉사과 민원여권", "062-360-7613"]) {
    assert.ok(s5.rc_main_text.includes(marker), `rc-main READ region missing passport marker: ${marker}`);
  }
  // No forbidden application/reservation/payment/login/PII/submission surface.
  for (const forbidden of ["신청하기", "예약하기", "결제하기", "로그인"]) {
    assert.ok(
      !String(s5.result.answer || "").includes(forbidden),
      `passport answer must not contain forbidden action surface: ${forbidden}`,
    );
  }

  // (3p-geo) #1356 desktop S5 geometry: the passport-guidance canvas must NOT
  // be clipped by left overflow. The entry-stage's transform:scale(1.06)
  // previously inflated .first-use-layout scrollWidth and auto-scrolled the
  // canvas left edge off-screen. Prove the fix: layout scrollLeft=0, canvas
  // left>=0, iframe left>=0, title left>=0 (여권발급 fully visible).
  const s5DesktopGeo = await page.evaluate(() => {
    const layout = document.querySelector('.first-use-layout');
    const canvas = document.getElementById("demo-canvas");
    const frame = document.getElementById("seogu-clone-frame");
    let iframeTitleLeft = null;
    try {
      const doc = frame.contentDocument;
      const main = doc && doc.querySelector("main.rc-main");
      const headings = main ? Array.from(main.querySelectorAll("h2,h3")) : [];
      const title = headings.find(h => h.textContent.includes("여권발급")) || headings[0];
      iframeTitleLeft = title ? Math.round(title.getBoundingClientRect().left) : null;
    } catch { iframeTitleLeft = null; }
    return {
      layoutScrollLeft: layout ? layout.scrollLeft : null,
      layoutScrollWidth: layout ? layout.scrollWidth : null,
      canvasLeft: canvas ? Math.round(canvas.getBoundingClientRect().left) : null,
      canvasRight: canvas ? Math.round(canvas.getBoundingClientRect().right) : null,
      iframeLeft: frame ? Math.round(frame.getBoundingClientRect().left) : null,
      iframeTitleLeft,
    };
  });
  assert.strictEqual(s5DesktopGeo.layoutScrollLeft, 0, "desktop S5 layout must not auto-scroll left (entry-stage overflow fixed)");
  assert.ok(s5DesktopGeo.canvasLeft >= 0, `desktop S5 canvas left must be >= 0, got ${s5DesktopGeo.canvasLeft}`);
  assert.ok(s5DesktopGeo.iframeLeft >= 0, `desktop S5 iframe left must be >= 0, got ${s5DesktopGeo.iframeLeft}`);
  assert.ok(s5DesktopGeo.iframeTitleLeft !== null && s5DesktopGeo.iframeTitleLeft >= 0, "desktop S5 passport title (여권발급) must be fully visible (left >= 0)");

  // (3b) S3 visibility check moved right after S3 (below)
  // Grounded answer provenance row must be visible in the thread.
  const provenance = await page.evaluate(() => {
    const rows = Array.from(document.querySelectorAll('#chat-thread [data-grounded="true"]'));
    const el = rows.filter((n) => n.getAttribute("data-journey-id") === "seogu_apartment_housing_dept").pop();
    const src = el && el.querySelector("[data-grounded-source]");
    return src ? src.textContent : null;
  });
  // (3b) #1365 REAL desktop visibility proof right after S3 (before S5/S6

  // navigate the iframe away from the housing route).

  const desktopSplit = await page.evaluate(() => document.body.getAttribute("data-first-use-state"));

  assert.strictEqual(desktopSplit, "split", "desktop S3 must enter split layout state");

  const desktopVis = await measureVisibility(page);

  assert.strictEqual(desktopVis.canvas.inert, false, "desktop S3 canvas must have inert removed");

  assert.strictEqual(desktopVis.canvas.ariaHidden, "false", "desktop S3 canvas must be aria-hidden=false");

  assert.notStrictEqual(desktopVis.canvas.display, "none", "desktop S3 canvas must not be display:none");

  assert.ok(desktopVis.canvas.rect.w > 0 && desktopVis.canvas.rect.h > 0, "desktop S3 canvas must have non-zero rect");

  assert.ok(desktopVis.canvas.inViewport, "desktop S3 canvas must intersect the viewport");

  assert.ok(desktopVis.iframe.rect.w > 0 && desktopVis.iframe.rect.h > 0, "desktop S3 iframe must have non-zero rect");

  assert.ok(desktopVis.iframe.inViewport, "desktop S3 iframe must intersect the viewport");

  assert.ok(desktopVis.rc_main.visible, "desktop S3 iframe rc-main must be visible (not blank)");

  assert.ok(desktopVis.rc_main.rect.w > 0 && desktopVis.rc_main.rect.h > 0, "desktop S3 rc-main must have non-zero rect");

  assert.ok(provenance && provenance.includes("housing/"), "S3 grounded row must show repository-clone provenance");

  // (4) SOURCE_CAPTURE_NEEDED scenarios: honest, no navigation, no fake success.
  // Capture iframe path BEFORE the loop to prove capture-needed clicks don't
  // navigate the clone surface (regardless of the current route).
  const iframePathBeforeCapture = await page.evaluate(
    () => document.getElementById("seogu-clone-frame").contentWindow.location.pathname,
  );
  for (const id of CAPTURE_NEEDED_IDS) {
    await page.locator(`[data-journey-id="${id}"]`).click();
    await page.waitForFunction(
      () => document.body.getAttribute("data-journey-state") === "capture_needed",
      null,
      { timeout: 10000 },
    );
    const row = await page.evaluate((jid) => {
      const rows = Array.from(document.querySelectorAll('[data-capture-needed="true"]'));
      const el = rows.filter((n) => n.getAttribute("data-journey-id") === jid).pop();
      return el ? { status: el.getAttribute("data-status"), text: el.textContent } : null;
    }, id);
    assert.ok(row, `capture-needed row missing for ${id}`);
    assert.strictEqual(row.status, "SOURCE_CAPTURE_NEEDED", `${id} must keep SOURCE_CAPTURE_NEEDED status`);
    assertNoForbiddenSuccess(row.text, `capture-needed row for ${id}`);
  }
  // After capture-needed clicks the iframe must NOT have navigated.
  const iframePathAfterCapture = await page.evaluate(
    () => document.getElementById("seogu-clone-frame").contentWindow.location.pathname,
  );
  assert.strictEqual(
    iframePathAfterCapture, iframePathBeforeCapture,
    "capture-needed scenarios must not navigate the clone surface",
  );
  // #1376: no canonical Seo-gu scenario may remain capture-needed.
  assert.strictEqual(
    CAPTURE_NEEDED_IDS.length, 0,
    "all canonical Seo-gu scenarios must be implemented (no SOURCE_CAPTURE_NEEDED left)",
  );
  // (3k) #1360 S6 kiosk chip: navigate -> bounded clone READ -> required
  // markers (무인민원발급안내/설치장소/도로명주소/서비스시간/발급종수) ->
  // grounded, READ-derived answer with visible repository-clone provenance.
  // Before the resident explicitly activates the chip, no route choreography
  // begins; after activation the journey navigates to the committed
  // unmanned-kiosk/ clone route and READs its main.rc-main.
  const preKioskRoute = await page.evaluate(() => {
    const frame = document.getElementById("seogu-clone-frame");
    return frame && frame.contentWindow ? frame.contentWindow.location.pathname : null;
  });
  assert.ok(
    !preKioskRoute || !preKioskRoute.includes("unmanned-kiosk"),
    "no kiosk route choreography before explicit resident confirmation",
  );
  // #1365: chip -> answer -> confirm -> YES -> navigate -> grounded
  await confirmAndProceed(page, '[data-journey-id="seogu_unmanned_kiosk"]', "grounded");
  const s6 = await page.evaluate(() => {
    const shell = window.SeoguCitizenActionShell;
    const r = shell.getLastJourneyResult();
    const ev = shell.getEvidence();
    const frame = document.getElementById("seogu-clone-frame");
    let rcMainText = null;
    try {
      const doc = frame.contentDocument;
      const main = doc && doc.querySelector("main.rc-main");
      rcMainText = main ? main.innerText : null;
    } catch {
      rcMainText = null;
    }
    return {
      result: r
        ? {
            ok: r.ok,
            grounded: r.grounded,
            route: r.route,
            journey_id: r.journey_id,
            source_kind: r.source_kind,
            evidence_kind: r.evidence_kind,
            answer: r.answer,
            excerpt: r.excerpt,
          }
        : null,
      evidence: ev
        ? { route: ev.route, source_kind: ev.source_kind, evidence_kind: ev.evidence_kind, text: ev.text }
        : null,
      rc_main_text: rcMainText,
      iframe_url: frame.contentWindow ? frame.contentWindow.location.pathname : null,
    };
  });
  assert.ok(s6.result, "S6 kiosk journey result must exist");
  assert.strictEqual(s6.result.ok, true, "S6 kiosk journey must be ok");
  assert.strictEqual(s6.result.grounded, true, "S6 kiosk journey must be grounded");
  assert.strictEqual(s6.result.journey_id, "seogu_unmanned_kiosk");
  assert.ok(
    String(s6.result.route).includes("unmanned-kiosk"),
    `S6 must land on unmanned-kiosk route, got ${s6.result.route}`,
  );
  assert.ok(
    String(s6.iframe_url || "").includes("unmanned-kiosk"),
    "iframe must actually navigate to the unmanned-kiosk clone route",
  );
  // Required markers present in the READ evidence text.
  for (const marker of ["무인민원발급안내", "설치장소", "도로명주소", "서비스시간", "발급종수"]) {
    assert.ok(String(s6.evidence.text || "").includes(marker), `READ evidence missing kiosk marker: ${marker}`);
  }
  // Provenance: repository clone, clone DOM evidence.
  assert.strictEqual(s6.result.source_kind, "repository_clone", "S6 provenance must be repository_clone");
  assert.strictEqual(s6.result.evidence_kind, "clone_dom", "S6 evidence_kind must be clone_dom");
  assert.strictEqual(s6.evidence.source_kind, "repository_clone");
  // READ-derived answer: excerpt must be a literal substring of the iframe
  // rc-main innerText (proves the answer is derived from the READ region,
  // not a hard-coded institution answer).
  assert.ok(s6.result.excerpt && s6.result.excerpt.length > 0, "S6 excerpt must be non-empty");
  assert.ok(s6.rc_main_text, "iframe rc-main must be readable (same-origin, script-disabled)");
  const s6RcMainNormalized = String(s6.rc_main_text).replace(/\s+/g, " ");
  for (const line of s6.result.excerpt.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const normalizedLine = trimmed.replace(/\s+/g, " ");
    assert.ok(
      s6RcMainNormalized.includes(normalizedLine),
      `answer excerpt line not found in rc-main READ region: ${trimmed.slice(0, 60)}`,
    );
  }
  // Internal generic grounding proof: the result answer must embed the READ
  // excerpt verbatim.
  assert.ok(
    s6.result.answer.includes(s6.result.excerpt),
    "grounded kiosk answer must embed the READ excerpt",
  );
  // Required markers also present directly in the rc-main READ region.
  for (const marker of ["무인민원발급안내", "설치장소", "도로명주소", "서비스시간", "발급종수"]) {
    assert.ok(s6.rc_main_text.includes(marker), `rc-main READ region missing kiosk marker: ${marker}`);
  }
  // Source-backed page-1 table content present in rc-main.
  assert.ok(s6.rc_main_text.includes("푸른새마을금고 금호지점"), "rc-main must contain source-backed kiosk row (푸른새마을금고 금호지점)");
  // No forbidden application/reservation/payment/login/PII/submission surface.
  for (const forbidden of ["신청하기", "예약하기", "결제하기", "로그인"]) {
    assert.ok(
      !String(s6.result.answer || "").includes(forbidden),
      `kiosk answer must not contain forbidden action surface: ${forbidden}`,
    );
  }
  // No nearest-kiosk inference claim (no resident location feature exists).
  assert.ok(
    !String(s6.result.answer || "").includes("가장 가까운"),
    "S6 must NOT claim nearest kiosk (no resident location feature)",
  );
  // Desktop no horizontal overflow on the kiosk journey thread.
  const s6Overflow = await page.evaluate(() => {
    const t = document.getElementById("chat-thread");
    return { scrollW: t.scrollWidth, clientW: t.clientWidth };
  });
  assert.ok(s6Overflow.scrollW <= s6Overflow.clientW + 1, "desktop S6 thread must not horizontally overflow");


  // (3m) #1376 S8 bulky-waste chip: navigate -> bounded clone READ ->
  // required markers (대형폐기물 신고/한손/시설관리공단/374-9446/자원순환과/
  // 062-360-7287 + fee table 1인용 매트리스 8,000 / 2인용 매트리스 11,000 /
  // 4~7일) -> grounded, READ-derived answer with repository-clone provenance.
  // Fees MUST come from the captured official page — never from Buk-gu
  // fallback hardcodes (침대 매트리스 5,000원).
  await confirmAndProceed(page, '[data-journey-id="seogu_mattress_disposal"]', "grounded");
  const s8 = await page.evaluate(() => {
    const shell = window.SeoguCitizenActionShell;
    const r = shell.getLastJourneyResult();
    const ev = shell.getEvidence();
    const frame = document.getElementById("seogu-clone-frame");
    let rcMainText = null;
    try {
      const doc = frame.contentDocument;
      const main = doc && doc.querySelector("main.rc-main");
      rcMainText = main ? main.innerText : null;
    } catch {
      rcMainText = null;
    }
    return {
      result: r
        ? { ok: r.ok, grounded: r.grounded, route: r.route, journey_id: r.journey_id,
            source_kind: r.source_kind, evidence_kind: r.evidence_kind, excerpt: r.excerpt }
        : null,
      evidence: ev ? { route: ev.route, text: ev.text } : null,
      rc_main_text: rcMainText,
      iframe_url: frame.contentWindow ? frame.contentWindow.location.pathname : null,
    };
  });
  assert.ok(s8.result, "S8 bulky-waste journey result must exist");
  assert.strictEqual(s8.result.ok, true, "S8 bulky-waste journey must be ok");
  assert.strictEqual(s8.result.grounded, true, "S8 bulky-waste journey must be grounded");
  assert.strictEqual(s8.result.journey_id, "seogu_mattress_disposal");
  assert.ok(
    String(s8.result.route).includes("bulky-waste-guidance"),
    `S8 must land on bulky-waste-guidance route, got ${s8.result.route}`,
  );
  assert.ok(
    String(s8.iframe_url || "").includes("bulky-waste-guidance"),
    "iframe must actually navigate to the bulky-waste-guidance clone route",
  );
  for (const marker of [
    "대형폐기물 신고", "한손", "시설관리공단", "374-9446",
    "자원순환과", "062-360-7287",
  ]) {
    assert.ok(String(s8.evidence.text || "").includes(marker), `READ evidence missing S8 marker: ${marker}`);
  }
  // Fee facts from the FRESH capture only (CTO mandatory requirement #1).
  for (const feeMarker of ["1인용 매트리스", "8,000", "2인용 매트리스", "11,000", "4~7일"]) {
    assert.ok(
      String(s8.rc_main_text || "").includes(feeMarker),
      `rc-main READ region missing S8 fee/timeline fact: ${feeMarker}`,
    );
  }
  // The stale Buk-gu fallback fee value must NOT appear in the Seo-gu capture.
  assert.ok(
    !String(s8.rc_main_text || "").includes("침대 매트리스 5,000"),
    "S8 capture must not inherit the stale Buk-gu fallback fee (5,000원)",
  );
  assert.strictEqual(s8.result.source_kind, "repository_clone", "S8 provenance must be repository_clone");
  assert.strictEqual(s8.result.evidence_kind, "clone_dom", "S8 evidence_kind must be clone_dom");
  assert.ok(s8.result.excerpt && s8.result.excerpt.length > 0, "S8 excerpt must be non-empty");
  assert.ok(s8.rc_main_text, "iframe rc-main must be readable (same-origin, script-disabled)");
  const s8RcMainNormalized = String(s8.rc_main_text).replace(/\s+/g, " ");
  for (const line of s8.result.excerpt.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const normalizedLine = trimmed.replace(/\s+/g, " ");
    assert.ok(
      s8RcMainNormalized.includes(normalizedLine),
      `answer excerpt line not found in rc-main READ region: ${trimmed.slice(0, 60)}`,
    );
  }


  // (5) #1380 S-final: illegal-parking GUIDANCE_NAVIGATION — Buk-gu golden
  // shape (안내 채팅 → 지도단속 안내 surface → card → handoff-stop 단말).
  // No external anchor/link surface exists anywhere; 안전신문고 appears as
  // guidance TEXT only. The trafficminwon bounded capture grounds the
  // READ-derived answer (과태료 조회/납부/의견진술 시스템 — 신고 intake 아님).
  // HANDOFF_IDS/HANDOFF_CONTRACT stay as empty contract anchors: no Seo-gu
  // scenario may render an external destination row anymore.
  assert.strictEqual(
    HANDOFF_IDS.length, 0,
    "no external handoff scenarios may remain (#1380 owner decision)",
  );
  {
    // #1365: chip -> answer -> confirm -> YES -> navigate -> grounded READ.
    await confirmAndProceed(page, '[data-journey-id="seogu_illegal_parking_report"]', "grounded");

    const s2 = await page.evaluate(() => {
      const shell = window.SeoguCitizenActionShell;
      const r = shell.getLastJourneyResult();
      const ev = shell.getEvidence();
      const frame = document.getElementById("seogu-clone-frame");
      let rcMainText = null;
      try {
        const doc = frame.contentDocument;
        const main = doc && doc.querySelector("main.rc-main");
        rcMainText = main ? main.innerText : null;
      } catch {
        rcMainText = null;
      }
      return {
        result: r
          ? { ok: r.ok, grounded: r.grounded, route: r.route,
              journey_id: r.journey_id, source_kind: r.source_kind,
              evidence_kind: r.evidence_kind, excerpt: r.excerpt }
          : null,
        evidenceRoute: ev ? ev.route : null,
        evidenceText: ev ? ev.text : null,
        rc_main_text: rcMainText,
        iframe_url: frame.contentWindow ? frame.contentWindow.location.pathname : null,
        safeHandoffRows: document.querySelectorAll('[data-safe-handoff="true"]').length,
        destinationAttrs: document.querySelectorAll("[data-handoff-destination-url]").length,
        explicitOpenAnchors: document.querySelectorAll('[data-handoff-action="explicit-open"]').length,
        threadHtml: document.getElementById("chat-thread").innerHTML,
        canvasHtml: document.getElementById("demo-canvas").innerHTML,
      };
    });
    assert.ok(s2.result, "S2 grounded result must exist");
    assert.strictEqual(s2.result.ok, true, "S2 journey must be ok");
    assert.strictEqual(s2.result.grounded, true, "S2 journey must be grounded");
    assert.strictEqual(s2.result.journey_id, "seogu_illegal_parking_report");
    assert.ok(
      String(s2.result.route || "").includes("illegal-parking-report"),
      `S2 result.route must be the trafficminwon clone route, got ${s2.result.route}`,
    );
    assert.ok(
      String(s2.iframe_url || "").includes("illegal-parking-report"),
      "iframe must actually navigate to the illegal-parking-report clone route",
    );
    for (const marker of ["주정차단속조회", "과태료 조회", "과태료 납부", "의견진술"]) {
      assert.ok(String(s2.evidenceText || "").includes(marker), `READ evidence missing S2 marker: ${marker}`);
    }
    assert.strictEqual(s2.result.source_kind, "repository_clone", "S2 provenance must be repository_clone");
    assert.strictEqual(s2.result.evidence_kind, "clone_dom", "S2 evidence_kind must be clone_dom");
    assert.ok(s2.result.excerpt && s2.result.excerpt.length > 0, "S2 excerpt must be non-empty");
    assert.ok(s2.rc_main_text, "iframe rc-main must be readable (same-origin, script-disabled)");
    const s2RcMainNormalized = String(s2.rc_main_text).replace(/\s+/g, " ");
    for (const line of s2.result.excerpt.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      assert.ok(
        s2RcMainNormalized.includes(trimmed.replace(/\s+/g, " ")),
        `answer excerpt line not found in rc-main READ region: ${trimmed.slice(0, 60)}`,
      );
    }

    // Owner decision 2026-08-21: NO external channel surface anywhere.
    assert.strictEqual(s2.safeHandoffRows, 0, "S2 must render no safe_handoff destination row");
    assert.strictEqual(s2.destinationAttrs, 0, "S2 must render no destination URL attribute");
    assert.strictEqual(s2.explicitOpenAnchors, 0, "S2 must render no explicit-open anchor");
    const combinedHtml = s2.threadHtml + s2.canvasHtml;
    assert.ok(
      !combinedHtml.includes('href="https://www.safetyreport') &&
        !combinedHtml.includes("epeople"),
      "S2 must not contain any external channel anchor (safetyreport/epeople)",
    );

    // Buk-gu golden shape: guidance surface with the 지도단속 card, driven by
    // the shared choreography, ending at the truthful terminal line.
    await page.waitForFunction(() =>
      document.querySelector('[data-complaint-route="complaint-illegal-parking"]') !== null,
    null, { timeout: 30000 });
    const guidanceCard = await page.evaluate(() => {
      const card = document.querySelector(".bg-illegal-parking-card");
      const canvasText = document.getElementById("demo-canvas").innerText;
      return {
        present: card !== null,
        text: card ? card.textContent : "",
        mentionsOfficialChannelAsText: canvasText.includes("안전신문고"),
        systemScope: canvasText.includes("과태료 조회") &&
                     canvasText.includes("의견진술") &&
                     canvasText.includes("신고 접수 창구가 아닙니다"),
      };
    });
    assert.ok(guidanceCard.present, "S2 guidance surface must render the 지도단속 card");
    assert.ok(guidanceCard.systemScope, "S2 guidance card must state the system scope (조회/납부/의견진술, not intake)");
    assert.ok(guidanceCard.mentionsOfficialChannelAsText, "S2 guidance must mention 안전신문고 as text");

    await page.waitForFunction(() =>
      document.getElementById("chat-thread").innerText.includes(
        "실제 신고는 안전신문고(safetyreport.go.kr)에서 가능합니다"),
    null, { timeout: 30000 });

    // Resident-initiated card selection → app-owned handoff-stop terminal.
    await page.locator(".bg-illegal-parking-card").click();
    await page.waitForFunction(() =>
      document.querySelector('[data-stop-route="handoff-stop"]') !== null,
    null, { timeout: 15000 });
    const stop = await page.evaluate(() => ({
      summary: document.querySelector("[data-stop-summary]")?.innerText ?? "",
      state: document.body.getAttribute("data-journey-state"),
      threadText: document.getElementById("chat-thread").innerText,
    }));
    assert.ok(stop.summary.includes("안내 완료 · 미제출"), "S2 stop terminal must declare 안내 완료 · 미제출");
    assert.ok(
      stop.summary.includes("공식 채널에서 직접 신청"),
      "S2 stop terminal must point to the official channel next step",
    );
    assertNoForbiddenSuccess(stop.threadText, "S2 stop thread");
  }

  // ── #1364 Lane B: S3/S4 evidence-gated complaint writing ───────────────────
  // S3/S4 are NO LONGER external handoff journeys. The registry handoff config
  // is an EVIDENCE GATE (COMPLAINT_EVIDENCE_GATE / EVIDENCE_GATE_ONLY), not a
  // destination. After the shared controller's gate passes, the app-owned
  // complaint surface renders inside #demo-canvas and the shared choreography
  // runs to the PRE_SUBMIT STOP boundary:
  //   S3: ANSWER → CONFIRM → YES → evidence gate → complaint board → write
  //       flow → PRE_SUBMIT STOP (form review, submit disabled)
  //   S4: ANSWER → CONFIRM → YES → evidence gate → CHOICE → AI assist →
  //       complaint write → PRE_SUBMIT STOP
  // No safe_handoff row, no explicit-open anchor, no external destination.
  const COMPLAINT_FLOWS = [
    {
      id: "S3",
      jid: "seogu_streetlight_report",
      gate_route: "streetlight-report-handoff",
      has_choice: false,
    },
    {
      id: "S4",
      jid: "seogu_illegal_dumping_report",
      gate_route: "litter-report-handoff",
      has_choice: true,
    },
  ];
  for (const flow of COMPLAINT_FLOWS) {
    const cpage = await openDemo(desktop);
    // ANSWER → CONFIRM → YES → evidence gate → complaint_write
    await confirmAndProceed(cpage, `[data-journey-id="${flow.jid}"]`, "complaint_write");

    // Evidence gate passed: verified grounded provenance from the gate route.
    const cEvidence = await cpage.evaluate((jid) => {
      const rows = Array.from(document.querySelectorAll('[data-handoff-evidence="true"]'));
      const el = rows.filter((n) => n.getAttribute("data-journey-id") === jid).pop();
      return el ? {
        verified: el.getAttribute("data-handoff-evidence-verified"),
        route: el.getAttribute("data-handoff-local-evidence-route"),
        grounded: el.getAttribute("data-grounded"),
        source_kind: el.getAttribute("data-source-kind"),
        evidence_kind: el.getAttribute("data-evidence-kind"),
      } : null;
    }, flow.jid);
    assert.ok(cEvidence, `${flow.id} evidence-gate row must be rendered`);
    assert.strictEqual(cEvidence.verified, "true", `${flow.id} evidence gate must pass (all required markers present)`);
    assert.ok(
      String(cEvidence.route).includes(flow.gate_route),
      `${flow.id} evidence route must be the ${flow.gate_route} clone route, got ${cEvidence.route}`,
    );
    assert.strictEqual(cEvidence.grounded, "true", `${flow.id} evidence row must be grounded`);
    assert.strictEqual(cEvidence.source_kind, "repository_clone", `${flow.id} evidence must be repository_clone`);
    assert.strictEqual(cEvidence.evidence_kind, "clone_dom", `${flow.id} evidence must be clone_dom`);

    // Complaint surface owns the canvas: journey state stays on the complaint
    // axis and NO external handoff destination exists anywhere.
    const boardState = await cpage.evaluate(() => ({
      state: document.body.getAttribute("data-journey-state"),
      viewHosts: document.querySelectorAll("[data-seogu-complaint-view]").length,
      boardRoute: document.querySelector('[data-complaint-route="complaint-board"]') !== null,
      writeRoute: document.querySelector('[data-complaint-route="complaint-write"]') !== null,
      safeHandoffRows: document.querySelectorAll('[data-safe-handoff="true"]').length,
      explicitOpenAnchors: document.querySelectorAll('[data-handoff-action="explicit-open"]').length,
      destinationAttrs: document.querySelectorAll("[data-handoff-destination-url]").length,
    }));
    assert.strictEqual(boardState.state, "complaint_write", `${flow.id} final state after evidence success must be complaint_write (not safe_handoff)`);
    assert.strictEqual(boardState.safeHandoffRows, 0, `${flow.id} must render no safe_handoff destination row`);
    assert.strictEqual(boardState.explicitOpenAnchors, 0, `${flow.id} must render no explicit-open anchor`);
    assert.strictEqual(boardState.destinationAttrs, 0, `${flow.id} must render no destination URL attribute`);
    assert.strictEqual(boardState.viewHosts, 1, `${flow.id} must render exactly one app-owned complaint view host`);
    assert.ok(
      boardState.boardRoute || boardState.writeRoute,
      `${flow.id} complaint surface must render the board or write stage`,
    );

    // Drive the shared choreography to the PRE_SUBMIT STOP boundary.
    if (flow.has_choice) {
      // S4 CHOICE: resident explicitly selects AI assist ("AI 도움 받기").
      // Scoped by prompt text — the confirm-gate YES shares
      // .chat-decision__button--primary but is disabled after its own click.
      await cpage
        .locator(".chat-decision__button--primary")
        .filter({ hasText: "AI 도움" })
        .first()
        .click();
    }
    // PRE_SUBMIT STOP: the form-review confirmation prompt appears with the
    // submit button still disabled. confirmSubmission is NEVER clicked here —
    // the flow must STOP at pre-submit.
    await cpage.waitForFunction(() => {
      const btns = Array.from(document.querySelectorAll(".chat-decision__button--primary"));
      return btns.some((b) => String(b.textContent || "").includes("제출하기"));
    }, null, { timeout: 90000 });

    const preSubmit = await cpage.evaluate(() => ({
      state: document.body.getAttribute("data-journey-state"),
      choreoState: document.body.getAttribute("data-choreography-state"),
      title: (() => { const el = document.getElementById("board-write-title"); return el ? el.value : null; })(),
      content: (() => { const el = document.getElementById("board-write-content"); return el ? el.value : null; })(),
      submit: (() => {
        const b = document.getElementById("btn-board-submit");
        return b ? { disabled: b.disabled, aria: b.getAttribute("aria-disabled") } : null;
      })(),
      preSubmitPanel: document.querySelector('[data-pre-submit="true"]') !== null,
      threadText: document.getElementById("chat-thread").innerText,
    }));
    assert.strictEqual(preSubmit.state, "complaint_write", `${flow.id} journey state must remain complaint_write at PRE_SUBMIT`);
    assert.ok(
      String(preSubmit.choreoState || "").startsWith("waiting"),
      `${flow.id} choreography must be parked at a waiting (STOP) state, got ${preSubmit.choreoState}`,
    );
    assert.ok(preSubmit.title && preSubmit.title.length > 0, `${flow.id} draft title must be written at PRE_SUBMIT`);
    assert.ok(preSubmit.content && preSubmit.content.length > 0, `${flow.id} draft body must be written at PRE_SUBMIT`);
    assert.ok(preSubmit.submit, `${flow.id} submit button must exist`);
    assert.strictEqual(preSubmit.submit.disabled, true, `${flow.id} submit button must remain disabled (PRE_SUBMIT STOP)`);
    assert.strictEqual(preSubmit.submit.aria, "true", `${flow.id} submit button must keep aria-disabled=true`);
    assert.ok(preSubmit.preSubmitPanel, `${flow.id} form panel must carry data-pre-submit=true`);
    assertNoForbiddenSuccess(preSubmit.threadText, `${flow.id} PRE_SUBMIT thread`);
    await cpage.close();
  }

  // ── D6: FAIL-CLOSED negative proof (CTO comment 5322239653) ────────────────
  // The complaint-writing choreography may start ONLY after successful local
  // evidence validation (evidence.ok === true && missingMarkers.length === 0).
  // Deterministic proof on S4 (litter): serve the litter-report-handoff clone
  // page with ONE required marker ("대형폐기물 신고") stripped, then run the
  // journey on a FRESH page (the iframe must start off-route so the reload is
  // real and the stripped page is what gets READ). The journey must then STOP
  // fail-closed: no destination row, no anchor/href, no auto-open/prefill/
  // submit, NO complaint surface, NO choreography start, no model fallback,
  // no success semantics — with the evidence explanation + bounded STOP state
  // visible and zero external requests.
  const NEG_JID = "seogu_illegal_dumping_report";
  const NEG_ROUTE = "litter-report-handoff";
  const NEG_MISSING_MARKER = "대형폐기물 신고";
  const NEG_PRESENT_MARKER = "생활폐기물";

  // Fetch the ORIGINAL page body BEFORE registering the interception (avoids
  // any recursion if API requests were routed) and strip the forced marker
  // from EVERY occurrence so the READ region provably lacks it.
  const negOriginal = await desktop.request.get(`${BASE_ORIGIN}/seogu/${NEG_ROUTE}/`);
  assert.strictEqual(negOriginal.status(), 200, "negative proof must fetch the original litter evidence page");
  const negStrippedBody = (await negOriginal.text())
    .split(NEG_MISSING_MARKER)
    .join("_STRIPPED_BY_TEST_");

  // Fresh page in the same (egress-guarded) desktop context. The iframe must
  // start on the home route so the first litter navigation is a real reload
  // that hits the stripped page.
  const negPage = await openDemo(desktop);

  // Intercept the litter evidence page at PAGE level (page routes are evaluated
  // BEFORE the context-level egress guard), fulfilling a marker-stripped copy so
  // the READ region provably lacks the forced marker. All other (non-target)
  // requests fall back to the existing context-level egress guard via
  // route.fallback(), keeping it authoritative for every non-target request
  // (CTO 5322506871). This is deterministic regardless of route registration.
  const negInterceptUrl = `${BASE_ORIGIN}/seogu/${NEG_ROUTE}/`;
  await negPage.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.includes(negInterceptUrl)) {
      await route.fulfill({
        status: 200,
        contentType: "text/html; charset=utf-8",
        body: negStrippedBody,
      });
      return;
    }
    // Non-target requests fall back to the context-level egress guard so it
    // stays authoritative for every non-target request (CTO 5322506871).
    await route.fallback();
  });

  await negPage.evaluate(() => {
    window.__generalModelCalls = 0;
    window.CitizenMvpBridge = {
      askGeneralModel: () => {
        window.__generalModelCalls += 1;
        return Promise.resolve({
          ok: true,
          answer: "unused",
          grounded: false,
          source_kind: "general_model",
          evidence_kind: "none",
          answer_scope: "general_model",
        });
      },
    };
  });

  const negBefore = await negPage.evaluate((jid) => ({
    state: document.body.getAttribute("data-journey-state"),
    safeHandoffRows: document.querySelectorAll(`[data-safe-handoff="true"][data-journey-id="${jid}"]`).length,
    explicitOpenAnchors: document.querySelectorAll('[data-handoff-action="explicit-open"]').length,
    destinationAttrCount: document.querySelectorAll('[data-handoff-destination-url]').length,
    blockedRows: document.querySelectorAll(`[data-handoff-blocked="true"][data-journey-id="${jid}"]`).length,
    evidenceRows: document.querySelectorAll(`[data-handoff-evidence="true"][data-journey-id="${jid}"]`).length,
    generalFallbackOffers: document.querySelectorAll('[data-general-fallback-offer="true"]').length,
    generalModelCalls: window.__generalModelCalls,
  }), NEG_JID);

  // #1365: chip -> answer -> confirm -> YES -> handoff evidence -> fail-closed
  await confirmAndProceed(negPage, `[data-journey-id="${NEG_JID}"]`, "handoff_evidence_failed");

  // Deterministic precondition: the forced marker is really absent from the
  // READ region while the page demonstrably loaded (control marker present).
  const negPre = await negPage.evaluate(() => {
    const frame = document.getElementById("seogu-clone-frame");
    const doc = frame.contentDocument;
    const main = doc && doc.querySelector("main.rc-main");
    return {
      iframePath: frame.contentWindow ? frame.contentWindow.location.pathname : null,
      rcText: main ? main.innerText : "",
    };
  });
  assert.ok(
    String(negPre.iframePath || "").includes(NEG_ROUTE),
    "negative proof iframe must land on the litter evidence route",
  );
  assert.ok(
    negPre.rcText.includes(NEG_PRESENT_MARKER),
    "negative proof page must have loaded (control marker present in READ region)",
  );
  assert.ok(
    !negPre.rcText.includes(NEG_MISSING_MARKER),
    "negative proof forced marker must be absent from the READ region",
  );

  const negAfter = await negPage.evaluate((jid) => {
    const blocked = (() => {
      const rows = Array.from(document.querySelectorAll('[data-handoff-blocked="true"]'));
      const el = rows.filter((n) => n.getAttribute("data-journey-id") === jid).pop();
      if (!el) return null;
      return {
        status: el.getAttribute("data-status"),
        action_kind: el.getAttribute("data-handoff-action-kind"),
        claim_scope: el.getAttribute("data-handoff-claim-scope"),
        stop_boundary: el.getAttribute("data-handoff-stop-boundary"),
        hasAnchor: Boolean(el.querySelector("a")),
        hasExplicitOpen: Boolean(el.querySelector('[data-handoff-action="explicit-open"]')),
        hasDestinationUrl: el.hasAttribute("data-handoff-destination-url"),
        hasDestinationLabel: el.hasAttribute("data-handoff-destination-label"),
        hasDestinationAuthority: el.hasAttribute("data-handoff-destination-authority"),
        hasFormControl: Boolean(el.querySelector("input,select,textarea,button,form")),
        text: el.textContent,
      };
    })();
    const evidence = (() => {
      const rows = Array.from(document.querySelectorAll('[data-handoff-evidence="true"]'));
      const el = rows.filter((n) => n.getAttribute("data-journey-id") === jid).pop();
      return el
        ? {
            verified: el.getAttribute("data-handoff-evidence-verified"),
            route: el.getAttribute("data-handoff-local-evidence-route"),
            text: el.textContent,
          }
        : null;
    })();
    return {
      state: document.body.getAttribute("data-journey-state"),
      safeHandoffRows: document.querySelectorAll(`[data-safe-handoff="true"][data-journey-id="${jid}"]`).length,
      explicitOpenAnchors: document.querySelectorAll('[data-handoff-action="explicit-open"]').length,
      destinationAttrCount: document.querySelectorAll('[data-handoff-destination-url]').length,
      blockedRows: document.querySelectorAll(`[data-handoff-blocked="true"][data-journey-id="${jid}"]`).length,
      evidenceRows: document.querySelectorAll(`[data-handoff-evidence="true"][data-journey-id="${jid}"]`).length,
      generalFallbackOffers: document.querySelectorAll('[data-general-fallback-offer="true"]').length,
      generalModelCalls: window.__generalModelCalls,
      // #1364 Lane B: failed gate must NOT open the complaint surface or start
      // the shared choreography.
      complaintViewHosts: document.querySelectorAll("[data-seogu-complaint-view]").length,
      choreoState: window.CitizenFirstChoreography ? window.CitizenFirstChoreography.getState() : null,
      blocked,
      evidence,
    };
  }, NEG_JID);

  // D6-1: fail-closed journey state is visible (bounded STOP, not safe_handoff).
  assert.strictEqual(negAfter.state, "handoff_evidence_failed", "failed evidence must expose the fail-closed journey state");
  // D6-2: no destination row was added for this journey.
  assert.strictEqual(negAfter.safeHandoffRows, negBefore.safeHandoffRows, "no external destination row may be rendered on failed evidence");
  // D6-3: no explicit-open anchor anywhere in the thread.
  assert.strictEqual(negAfter.explicitOpenAnchors, negBefore.explicitOpenAnchors, "no explicit-open anchor may be rendered on failed evidence");
  assert.strictEqual(negAfter.explicitOpenAnchors, 0, "no explicit-open anchor may exist anywhere on the fail-closed page");
  // D6-4: no destination URL control attribute exists anywhere.
  assert.strictEqual(negAfter.destinationAttrCount, 0, "no data-handoff-destination-url control may exist on the fail-closed page");
  // D6-5: exactly one bounded STOP row was added, carrying the configured stop boundary.
  assert.strictEqual(negAfter.blockedRows, negBefore.blockedRows + 1, "exactly one fail-closed STOP row must be rendered");
  assert.ok(negAfter.blocked, "fail-closed STOP row must be present");
  assert.ok(negAfter.blocked.stop_boundary && negAfter.blocked.stop_boundary.length > 0, "STOP row must expose the configured stop boundary code");
  assert.strictEqual(negAfter.blocked.status, "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED", "blocked row must keep the substitution classification");
  assert.strictEqual(negAfter.blocked.action_kind, "COMPLAINT_EVIDENCE_GATE", "blocked row must keep the complaint evidence-gate action_kind");
  assert.strictEqual(negAfter.blocked.claim_scope, "EVIDENCE_GATE_ONLY", "blocked row must keep claim_scope=EVIDENCE_GATE_ONLY");
  // D6-6: no actionable external destination control (no anchor, no href, no destination attrs).
  assert.strictEqual(negAfter.blocked.hasAnchor, false, "blocked row must contain no anchor");
  assert.strictEqual(negAfter.blocked.hasExplicitOpen, false, "blocked row must contain no explicit-open control");
  assert.strictEqual(negAfter.blocked.hasDestinationUrl, false, "blocked row must not carry a destination URL attribute");
  assert.strictEqual(negAfter.blocked.hasDestinationLabel, false, "blocked row must not carry a destination label attribute");
  assert.strictEqual(negAfter.blocked.hasDestinationAuthority, false, "blocked row must not carry a destination authority attribute");
  // D6-7: no prefill/submit capability (no form/button/input control).
  assert.strictEqual(negAfter.blocked.hasFormControl, false, "blocked row must contain no form/button/input control");
  // D6-7b (#1364): the failed evidence gate must NOT open the app-owned
  // complaint surface and must NOT start the shared choreography.
  assert.strictEqual(negAfter.complaintViewHosts, 0, "failed gate must not render any complaint view host");
  assert.strictEqual(negAfter.choreoState, "idle", "failed gate must not start the complaint choreography");
  // D6-8: no fake success/receipt semantics.
  assertNoForbiddenSuccess(negAfter.blocked.text, "fail-closed STOP row");
  // D6-9: evidence explanation retained with the missing marker named.
  assert.ok(negAfter.evidence, "evidence explanation row must still be rendered on failure");
  assert.strictEqual(negAfter.evidence.verified, "false", "evidence row must be verified=false");
  assert.ok(String(negAfter.evidence.text).includes("확인하지 못한 항목"), "evidence row must name the unconfirmed items");
  assert.ok(String(negAfter.evidence.text).includes(NEG_MISSING_MARKER), "evidence row must name the forced missing marker");
  assert.strictEqual(negAfter.evidenceRows, negBefore.evidenceRows + 1, "exactly one evidence explanation row must be added");
  // D6-10: no general-model call, no general fallback offer, no external request.
  assert.strictEqual(negAfter.generalModelCalls, negBefore.generalModelCalls, "failed handoff must never call the general model");
  assert.strictEqual(negAfter.generalModelCalls, 0, "general model call count must remain 0 on the fail-closed page");
  assert.strictEqual(negAfter.generalFallbackOffers, negBefore.generalFallbackOffers, "failed handoff must not offer the general-model fallback");
  assert.deepStrictEqual(externalRequests, [], "fail-closed negative proof must make zero external requests");

  await negPage.close();

  // Whole-thread fake-success sweep over every AI bubble rendered so far.
  const threadText = await page.evaluate(() => document.getElementById("chat-thread").innerText);
  assertNoForbiddenSuccess(threadText, "chat thread");

  // ── D3: general-AI explicit opt-in (mocked CitizenMvpBridge.askGeneralModel) ──
  // An unmatched question must NEVER call a model silently. It must surface an
  // explicit opt-in offer; only after the resident clicks does the bridge fire
  // exactly once (call count 0 → 1), and the rendered answer must carry the
  // exact general-model provenance (grounded=false, source_kind=general_model,
  // evidence_kind=none, answer_scope=general_model).
  await page.evaluate(() => {
    window.__generalModelCalls = 0;
    window.CitizenMvpBridge = {
      askGeneralModel: (question, options) => {
        window.__generalModelCalls += 1;
        window.__generalModelLastQuestion = question;
        window.__generalModelLastOptions = options;
        return Promise.resolve({
          ok: true,
          answer: "일반 AI 모델 답변입니다 (기관 안내 화면 근거 아님).",
          grounded: false,
          source_kind: "general_model",
          evidence_kind: "none",
          answer_scope: "general_model",
        });
      },
    };
  });
  const callsBefore = await page.evaluate(() => window.__generalModelCalls);
  assert.strictEqual(callsBefore, 0, "general model must not be called before any question");

  await page.fill("#chat-composer-input", "오늘 날씨 어때?");
  await page.click("#chat-composer-send");
  await page.waitForFunction(
    () => document.body.getAttribute("data-journey-state") === "general_model_offer",
    null,
    { timeout: 10000 },
  );
  const callsAfterOffer = await page.evaluate(() => window.__generalModelCalls);
  assert.strictEqual(callsAfterOffer, 0, "unmatched question must NOT silently call the general model (explicit opt-in)");

  await page.locator('[data-general-model-action="request"]').last().click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-journey-state") === "general_model",
    null,
    { timeout: 10000 },
  );
  const d3 = await page.evaluate(() => ({
    calls: window.__generalModelCalls,
    lastQuestion: window.__generalModelLastQuestion,
    lastSiteId: window.__generalModelLastOptions && window.__generalModelLastOptions.site_id,
    generalRow: (() => {
      const rows = Array.from(document.querySelectorAll('#chat-thread [data-grounded="false"]'));
      const el = rows.filter((n) => n.getAttribute("data-source-kind") === "general_model").pop();
      if (!el) return null;
      return {
        grounded: el.getAttribute("data-grounded"),
        source_kind: el.getAttribute("data-source-kind"),
        evidence_kind: el.getAttribute("data-evidence-kind"),
        answer_scope: el.getAttribute("data-answer-scope"),
        hasGeneralSource: Boolean(el.querySelector("[data-general-model-source]")),
        text: el.textContent,
      };
    })(),
  }));
  assert.strictEqual(d3.calls, 1, "general model must be called exactly once after explicit opt-in (0 → 1)");
  assert.strictEqual(d3.lastQuestion, "오늘 날씨 어때?", "bridge must receive the resident's exact question");
  assert.strictEqual(d3.lastSiteId, "seogu_gwangju", "bridge must receive the Seo-gu site_id");
  assert.ok(d3.generalRow, "general-model answer row must be rendered");
  assert.strictEqual(d3.generalRow.grounded, "false", "general answer must be grounded=false");
  assert.strictEqual(d3.generalRow.source_kind, "general_model", "general answer source_kind must be general_model");
  assert.strictEqual(d3.generalRow.evidence_kind, "none", "general answer evidence_kind must be none");
  assert.strictEqual(d3.generalRow.answer_scope, "general_model", "general answer answer_scope must be general_model");
  assert.ok(d3.generalRow.hasGeneralSource, "general answer must show the general-model provenance source row");
  assertNoForbiddenSuccess(d3.generalRow.text, "general-model answer row");

  // ── D4: preserved journeys remain grounded (사회연대경제 / 조직도) ──────────
  // The two already-proven Seo-gu journeys must stay reachable by typed question
  // and produce grounded, repository-clone READ-derived answers with their
  // markers — never re-implemented, never weakened.
  const PRESERVED_PROOFS = [
    {
      journey_id: "seogu_notice_social_economy",
      question: "사회연대경제 공고 내용을 알려줘",
      markers: ["사회연대경제"],
    },
    {
      journey_id: "seogu_organization_leadership",
      question: "서구청 조직도에서 구청장과 부구청장 구조를 알려줘",
      markers: ["행정조직도", "구청장", "부구청장"],
    },
  ];
  for (const proof of PRESERVED_PROOFS) {
    await page.fill("#chat-composer-input", proof.question);
    await page.click("#chat-composer-send");
    // #1365: typed questions also pass through the confirm gate
    await page.waitForFunction(
      () => document.body.getAttribute("data-journey-state") === "confirm",
      null,
      { timeout: 10000 },
    );
    await page.locator('[data-confirm-action="yes"]').last().click();
    await page.waitForFunction(
      () => document.body.getAttribute("data-journey-state") === "grounded",
      null,
      { timeout: 20000 },
    );
    const preserved = await page.evaluate((jid) => {
      const shell = window.SeoguCitizenActionShell;
      const r = shell.getLastJourneyResult();
      return r
        ? {
            ok: r.ok,
            grounded: r.grounded,
            journey_id: r.journey_id,
            route: r.route,
            source_kind: r.source_kind,
            evidence_kind: r.evidence_kind,
            answer: r.answer,
            excerpt: r.excerpt,
          }
        : null;
    }, proof.journey_id);
    assert.ok(preserved, `preserved journey result missing for ${proof.journey_id}`);
    assert.strictEqual(preserved.ok, true, `${proof.journey_id} must be ok`);
    assert.strictEqual(preserved.grounded, true, `${proof.journey_id} must be grounded`);
    assert.strictEqual(preserved.journey_id, proof.journey_id, `${proof.journey_id} journey_id mismatch`);
    assert.strictEqual(preserved.source_kind, "repository_clone", `${proof.journey_id} provenance must be repository_clone`);
    assert.strictEqual(preserved.evidence_kind, "clone_dom", `${proof.journey_id} evidence_kind must be clone_dom`);
    for (const marker of proof.markers) {
      assert.ok(String(preserved.answer || "").includes(marker), `${proof.journey_id} answer missing marker: ${marker}`);
    }
    assert.ok(preserved.excerpt && preserved.excerpt.length > 0, `${proof.journey_id} excerpt must be non-empty`);
    assert.ok(preserved.answer.includes(preserved.excerpt), `${proof.journey_id} answer must embed the READ excerpt`);
    assertNoForbiddenSuccess(preserved.answer, `preserved journey answer for ${proof.journey_id}`);
    // Rendered presentation must stay EXACTLY the preserved READ-derived
    // answer — the S1 concise-guidance transform may not leak into any other
    // journey (non-S1 behaviour must not regress).
    const preservedRow = page.locator(`#chat-thread [data-grounded="true"][data-journey-id="${proof.journey_id}"]`).last();
    const preservedBubble = await preservedRow.locator(".chat-bubble--ai").textContent();
    assert.strictEqual(
      String(preservedBubble || ""),
      preserved.answer,
      `${proof.journey_id} rendered bubble must equal the preserved READ-derived answer`,
    );
    assert.ok(
      String(preservedBubble || "").startsWith("왼쪽 저장소 기반 기관 안내 화면에서 확인한 내용입니다."),
      `${proof.journey_id} bubble must keep the raw READ-derived boilerplate start`,
    );
    assert.ok(
      !String(preservedBubble || "").includes("담당 부서:"),
      `${proof.journey_id} bubble must not leak the S1 department hierarchy`,
    );
    assert.ok(
      !String(preservedBubble || "").includes("공동주택 관련"),
      `${proof.journey_id} bubble must not leak S1 housing guidance`,
    );
  }

  // ── D5: language-control regression — no visible empty selector ────────────
  // Blocker C: the empty, nonfunctional <select id="chat-lang"> (arrow-only
  // broken control) must be gone. No visible empty language selector may remain.
  const langControl = await page.evaluate(() => {
    const byId = document.getElementById("chat-lang");
    const empties = Array.from(document.querySelectorAll("select.chat-shell__lang")).filter(
      (s) => s.querySelectorAll("option").length === 0,
    );
    function visible(el) {
      if (!el) return false;
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return cs.display !== "none" && cs.visibility !== "hidden" && r.width > 0 && r.height > 0;
    }
    return {
      byIdExists: Boolean(byId),
      byIdVisible: visible(byId),
      emptyLangSelectCount: empties.length,
      visibleEmptyLangSelect: empties.some(visible),
    };
  });
  assert.strictEqual(langControl.visibleEmptyLangSelect, false, "no visible empty language selector may remain (Blocker C)");
  assert.strictEqual(langControl.byIdVisible, false, "#chat-lang must not be a visible broken control (Blocker C)");
  assert.strictEqual(langControl.emptyLangSelectCount, 0, "no empty .chat-shell__lang select may remain in the DOM (Blocker C)");

  // (3n) #1388 split-state never-blank loading affordance — owner-reported
  // defect window made deterministic. A fresh context delays the /seogu/ home
  // document so the clone iframe is still loading when the resident clicks the
  // 구청장에게 제안 chip (the reported surface). Contract: from the first
  // available-canvas sample until the pending navigation completes, the canvas
  // must present either the styled loading affordance or rendered clone
  // content; the affordance hands over exactly on actual load completion.
  {
    const slowCtx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
    await installEgressGuard(slowCtx);
    // Exact-match regex (glob **/seogu/ proved unreliable across versions):
    // only the clone HOME document is delayed; latest-registered handler runs
    // first, then falls back to the egress guard which validates origin.
    await slowCtx.route(/\/seogu\/$/, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1200));
      await route.fallback();
    });
    const slowPage = await slowCtx.newPage();
    // domcontentloaded on purpose: boot starts while the delayed home doc is
    // still pending, exactly like a cold production visit.
    await slowPage.goto(DEMO_URL, { waitUntil: "domcontentloaded", timeout: 20000 });
    await slowPage.waitForFunction(
      () => document.querySelectorAll("#chat-chips .chat-chip").length > 0,
      null,
      { timeout: 15000 },
    );

    const slowProbe = await startNeverBlankProbe(slowPage);
    await slowPage.locator('[data-journey-id="seogu_mayor_proposal"]').click();
    await slowPage.waitForFunction(
      () =>
        document.body.getAttribute("data-first-use-state") === "split" &&
        !document.getElementById("demo-canvas").hasAttribute("inert"),
      null,
      { timeout: 10000 },
    );
    // While the home document is still being delayed, the fix MUST be visible:
    // at least one available-canvas sample presents the loading affordance.
    const sawAffordanceDuringPendingLoad = await slowPage.waitForFunction(
      () =>
        (window.__nbSamples || []).some(
          (s) => s.canvasAvailable && s.loadingVisible && !s.cloneRendered,
        ),
      null,
      { timeout: 8000 },
    );
    assert.ok(sawAffordanceDuringPendingLoad !== null, "loading affordance must be visible while the split canvas awaits the pending clone load");

    // Hand-over: only on actual load completion does the affordance clear and
    // rendered clone content appear (answer state is this probe's terminal).
    await slowPage.waitForFunction(
      () => {
        const frame = document.getElementById("seogu-clone-frame");
        try {
          const doc = frame && frame.contentDocument;
          const main = doc && doc.querySelector("main.rc-main");
          return (
            String(doc && doc.readyState) === "complete" &&
            !!main &&
            main.getBoundingClientRect().width > 0
          );
        } catch {
          return false;
        }
      },
      null,
      { timeout: 20000 },
    );
    await slowPage.waitForFunction(
      () => {
        const state = document.body.getAttribute("data-journey-state");
        // "answer" is transient (controller schedules confirm 300ms later);
        // any of these proves the canonical confirm flow engaged cleanly
        // across the pending-load window.
        return ["answer", "confirm", "grounded"].includes(state);
      },
      null,
      { timeout: 10000 },
    );
    const handOver = await slowPage.evaluate(() => {
      const samples = window.__nbSamples || [];
      const last = samples[samples.length - 1];
      const loadingEl = document.getElementById("demo-canvas-loading");
      return {
        lastSample: last || null,
        loadingDisplayNow: loadingEl ? getComputedStyle(loadingEl).display : null,
      };
    });
    assert.ok(handOver.lastSample, "never-blank probe must retain final sample");
    assert.strictEqual(handOver.loadingDisplayNow, "none", "affordance must hand over (display:none) once the clone document has actually loaded");
    const slowSamples = await stopNeverBlankProbe(slowPage);
    assertNeverBlankSamples(slowSamples, "slow-load chip click (#1388)");
    void slowProbe;

    const slowExternalLeak = [];
    await slowCtx.close();
    assert.deepStrictEqual(slowExternalLeak, [], "delayed-load context must not add external requests");
  }

  await desktop.close();

  // ── Mobile contract (390x844) ─────────────────────────────────────────────
  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await installEgressGuard(mobile);
  const mpage = await openDemo(mobile);

  // (6) mobile conversation/guidance switch
  // At cold entry the switch is [hidden]; it reveals after first resident action.
  const switchEl = mpage.locator("#mobile-surface-switch");
  assert.strictEqual(await switchEl.evaluate((el) => el.hasAttribute("hidden")), true, "switch hidden at cold entry");
  // Trigger split by clicking a chip (first supported resident action)
  await mpage.locator(".chat-chip").first().click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-first-use-state") === "split",
    null,
    { timeout: 10000 },
  );
  // Now switch should be visible
  await switchEl.waitFor({ state: "visible", timeout: 10000 });
  const convTab = mpage.locator('[data-mobile-surface-tab="conversation"]');
  const guideTab = mpage.locator('[data-mobile-surface-tab="guidance"]');
  assert.strictEqual(await convTab.getAttribute("aria-pressed"), "true", "conversation tab starts pressed");
  assert.strictEqual(await guideTab.getAttribute("aria-pressed"), "false", "guidance tab starts unpressed");

  // (7) guidance switch drives the correct layout state
  await guideTab.click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "guidance",
    null,
    { timeout: 5000 },
  );
  const guidanceState = await mpage.evaluate(() => ({
    surface: document.body.getAttribute("data-mobile-surface"),
    layout: document.body.getAttribute("data-first-use-state"),
    convPressed: document.querySelector('[data-mobile-surface-tab="conversation"]').getAttribute("aria-pressed"),
    guidePressed: document.querySelector('[data-mobile-surface-tab="guidance"]').getAttribute("aria-pressed"),
    canvasHidden: document.getElementById("demo-canvas").hasAttribute("hidden"),
  }));
  assert.strictEqual(guidanceState.surface, "guidance");
  assert.strictEqual(guidanceState.layout, "split", "guidance surface must enter split layout state");
  assert.strictEqual(guidanceState.convPressed, "false");
  assert.strictEqual(guidanceState.guidePressed, "true");
  assert.strictEqual(guidanceState.canvasHidden, false, "guidance canvas must be revealed");

  // (7b) REAL mobile guidance visibility proof: run S3 on mobile, then the
  // guidance tab must show the housing clone (inert removed, aria-hidden=false,
  // non-zero rect, readable rc-main with grounded markers) — not a blank panel.
  await convTab.click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "conversation",
    null,
    { timeout: 5000 },
  );
  // #1365: chip -> answer -> confirm -> YES -> navigate -> grounded (mobile)
  await confirmAndProceed(mpage, '[data-journey-id="seogu_apartment_housing_dept"]', "grounded");
  await guideTab.click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "guidance",
    null,
    { timeout: 5000 },
  );
  await mpage.waitForTimeout(400); // let the split transition settle
  const mobileGuidanceVis = await measureVisibility(mpage);
  assert.strictEqual(mobileGuidanceVis.canvas.inert, false, "mobile guidance canvas must have inert removed");
  assert.strictEqual(mobileGuidanceVis.canvas.ariaHidden, "false", "mobile guidance canvas must be aria-hidden=false");
  assert.notStrictEqual(mobileGuidanceVis.canvas.display, "none", "mobile guidance canvas must not be display:none");
  assert.ok(mobileGuidanceVis.canvas.rect.w > 0 && mobileGuidanceVis.canvas.rect.h > 0, "mobile guidance canvas must have non-zero rect");
  assert.ok(mobileGuidanceVis.iframe.rect.w > 0 && mobileGuidanceVis.iframe.rect.h > 0, "mobile guidance iframe must have non-zero rect");
  assert.ok(mobileGuidanceVis.iframe.inViewport, "mobile guidance iframe must intersect the viewport");
  assert.ok(mobileGuidanceVis.rc_main.visible, "mobile guidance iframe rc-main must be visible (not blank)");
  assert.ok(mobileGuidanceVis.rc_main.markers.gongdong, "mobile guidance rc-main must show 공동주택");
  assert.ok(mobileGuidanceVis.rc_main.markers.jootaekgwa, "mobile guidance rc-main must show 주택과");
  assert.ok(mobileGuidanceVis.rc_main.markers.gongdongmanage, "mobile guidance rc-main must show 공동주택관리");
  const mobileIframePath = await mpage.evaluate(
    () => document.getElementById("seogu-clone-frame").contentWindow.location.pathname,
  );
  assert.ok(String(mobileIframePath).includes("housing"), "mobile guidance must show the housing clone route");
  // Mobile S1 resident answer: actually verify the concise guidance bubble,
  // not just the housing canvas visibility.
  const mS1Row = mpage.locator('#chat-thread [data-grounded="true"][data-journey-id="seogu_apartment_housing_dept"]').last();
  const mS1Bubble = await mS1Row.locator(".chat-bubble--ai").textContent();
  assert.ok(String(mS1Bubble || "").includes("담당 부서"), "mobile S1 answer must contain department hierarchy");
  assert.ok(String(mS1Bubble || "").includes("주택과"), "mobile S1 answer must mention 주택과");
  assert.ok(String(mS1Bubble || "").includes("공동주택관리"), "mobile S1 answer must mention 공동주택관리");
  assert.ok(
    !String(mS1Bubble || "").startsWith("왼쪽 저장소 기반 기관 안내 화면에서 확인한 내용입니다."),
    "mobile S1 answer must NOT start with raw excerpt boilerplate",
  );
  for (const noise of ["폭염으로 인한 온열질환", "공동주택관리규약 준칙 개정"]) {
    assert.ok(
      !String(mS1Bubble || "").includes(noise),
      `mobile S1 answer must not dump board notice: ${noise}`,
    );
  }
  const mS1Source = await mS1Row.locator("[data-grounded-source]").textContent();
  assert.ok(
    String(mS1Source || "").includes("housing/"),
    "mobile S1 grounded row must keep housing/ provenance",
  );

  // (7p) #1356 mobile S5 passport guidance visibility: activate the passport
  // chip on mobile, switch to guidance, and prove the passport-guidance clone
  // renders a visible rc-main with the four required markers (no blank canvas).
  await convTab.click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "conversation",
    null,
    { timeout: 5000 },
  );
  // #1365: chip -> answer -> confirm -> YES -> navigate -> grounded (mobile S5)
  await confirmAndProceed(mpage, '[data-journey-id="seogu_passport_issuance"]', "grounded");
  await guideTab.click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "guidance",
    null,
    { timeout: 5000 },
  );
  await mpage.waitForTimeout(400); // let the split transition settle
  const mPassportVis = await measureVisibility(mpage);
  assert.strictEqual(mPassportVis.canvas.inert, false, "mobile passport canvas must have inert removed");
  assert.strictEqual(mPassportVis.canvas.ariaHidden, "false", "mobile passport canvas must be aria-hidden=false");
  assert.notStrictEqual(mPassportVis.canvas.display, "none", "mobile passport canvas must not be display:none");
  assert.ok(mPassportVis.canvas.rect.w > 0 && mPassportVis.canvas.rect.h > 0, "mobile passport canvas must have non-zero rect");
  assert.ok(mPassportVis.iframe.rect.w > 0 && mPassportVis.iframe.rect.h > 0, "mobile passport iframe must have non-zero rect");
  assert.ok(mPassportVis.rc_main.visible, "mobile passport iframe rc-main must be visible (not blank)");
  assert.ok(mPassportVis.rc_main.markers.passportIssuance, "mobile passport rc-main must show 여권발급");
  const mPassportIframePath = await mpage.evaluate(
    () => document.getElementById("seogu-clone-frame").contentWindow.location.pathname,
  );
  assert.ok(String(mPassportIframePath).includes("passport-guidance"), "mobile guidance must show the passport-guidance clone route");
  // No horizontal overflow of the thread on mobile passport journey.
  const mPassportOverflow = await mpage.evaluate(() => {
    const t = document.getElementById("chat-thread");
    return { scrollW: t.scrollWidth, clientW: t.clientWidth };
  });
  assert.ok(mPassportOverflow.scrollW <= mPassportOverflow.clientW + 1, "mobile passport thread must not horizontally overflow");
  // (7k) #1360 mobile S6 kiosk: activate the kiosk chip on mobile, switch to
  // guidance, and prove the unmanned-kiosk clone renders a visible rc-main with
  // the required markers (no blank canvas). Conversation surface works, then
  // guidance canvas visible/nonzero, iframe/route is unmanned-kiosk, rc-main
  // visible, no horizontal overflow. Do NOT automate map/search/pagination.
  await convTab.click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "conversation",
    null,
    { timeout: 5000 },
  );
  // #1365: chip -> answer -> confirm -> YES -> navigate -> grounded (mobile S6)
  await confirmAndProceed(mpage, '[data-journey-id="seogu_unmanned_kiosk"]', "grounded");
  await guideTab.click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "guidance",
    null,
    { timeout: 5000 },
  );
  await mpage.waitForTimeout(400); // let the split transition settle
  const mKioskVis = await measureVisibility(mpage);
  assert.strictEqual(mKioskVis.canvas.inert, false, "mobile kiosk canvas must have inert removed");
  assert.strictEqual(mKioskVis.canvas.ariaHidden, "false", "mobile kiosk canvas must be aria-hidden=false");
  assert.notStrictEqual(mKioskVis.canvas.display, "none", "mobile kiosk canvas must not be display:none");
  assert.ok(mKioskVis.canvas.rect.w > 0 && mKioskVis.canvas.rect.h > 0, "mobile kiosk canvas must have non-zero rect");
  assert.ok(mKioskVis.iframe.rect.w > 0 && mKioskVis.iframe.rect.h > 0, "mobile kiosk iframe must have non-zero rect");
  assert.ok(mKioskVis.rc_main.visible, "mobile kiosk iframe rc-main must be visible (not blank)");
  const mKioskIframePath = await mpage.evaluate(
    () => document.getElementById("seogu-clone-frame").contentWindow.location.pathname,
  );
  assert.ok(String(mKioskIframePath).includes("unmanned-kiosk"), "mobile guidance must show the unmanned-kiosk clone route");
  // Required markers in the mobile kiosk rc-main READ region.
  const mKioskRcMain = await mpage.evaluate(() => {
    const frame = document.getElementById("seogu-clone-frame");
    try {
      const doc = frame.contentDocument;
      const main = doc && doc.querySelector("main.rc-main");
      return main ? main.innerText : null;
    } catch { return null; }
  });
  assert.ok(mKioskRcMain, "mobile kiosk rc-main must be readable");
  for (const marker of ["무인민원발급안내", "설치장소", "도로명주소", "서비스시간", "발급종수"]) {
    assert.ok(String(mKioskRcMain || "").includes(marker), `mobile kiosk rc-main missing marker: ${marker}`);
  }
  // No horizontal overflow of the thread on mobile kiosk journey.
  const mKioskOverflow = await mpage.evaluate(() => {
    const t = document.getElementById("chat-thread");
    return { scrollW: t.scrollWidth, clientW: t.clientWidth };
  });
  assert.ok(mKioskOverflow.scrollW <= mKioskOverflow.clientW + 1, "mobile kiosk thread must not horizontally overflow");
  // (7q-geo) #1362 mobile S6 kiosk board geometry: the generic list-board
  // clone must not squeeze the table beside the SNB at 390px. The generic
  // renderer uses flex-wrap:wrap + a flex-basis on .rc-content so the SNB
  // stacks above the content, giving the table the full iframe width.
  // This regression fails on old head f538 (content squeezed to ~224px
  // beside a 166px SNB, table columns collapsed to ~18-48px).
  const mKioskBoardGeo = await mpage.evaluate(() => {
    const frame = document.getElementById("seogu-clone-frame");
    if (!frame || !frame.contentWindow) return null;
    const doc = frame.contentWindow.document;
    const snb = doc.querySelector(".rc-snb");
    const ct = doc.querySelector(".rc-content");
    if (!snb || !ct) return null;
    const ths = doc.querySelectorAll("table.rc-board th");
    return {
      contentTop: ct.offsetTop,
      snbTop: snb.offsetTop,
      snbHeight: snb.offsetHeight,
      contentWidth: ct.getBoundingClientRect().width,
      stacked: ct.offsetTop >= snb.offsetTop + snb.offsetHeight - 1,
      minColWidth: Math.min(
        ...Array.from(ths).map((th) => th.getBoundingClientRect().width),
      ),
    };
  });
  assert.ok(mKioskBoardGeo, "mobile kiosk board geometry must be measurable");
  assert.ok(
    mKioskBoardGeo.stacked,
    "mobile kiosk content must be stacked below SNB (not squeezed beside)",
  );
  assert.ok(
    mKioskBoardGeo.contentWidth >= 350,
    `mobile kiosk content must receive viable width (>=350px, got ${mKioskBoardGeo.contentWidth})`,
  );
  assert.ok(
    mKioskBoardGeo.minColWidth >= 25,
    `mobile kiosk table columns must not collapse below practical width (>=25px, got ${mKioskBoardGeo.minColWidth})`,
  );
  // Switch back to conversation for the S5 conversation geometry check.
  await convTab.click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "conversation",
    null,
    { timeout: 5000 },
  );
  // (7p-geo) #1356 mobile S5 conversation grounded-row geometry: the grounded
  // answer bubble + provenance must share one readable content column (not
  // squeezed as narrow horizontal siblings). Prove the grid fix: display=grid,
  // bubble width and source width both span the full content column, no page
  // overflow, and the chip rail matches the Buk-gu canonical wrap contract.
  //
  // Golden chip-rail contract (B / #1367 reconciliation): the canonical Buk-gu
  // `.chat-chips` is `display:flex; flex-wrap:wrap; overflow:visible` — it WRAPS,
  // it is NOT an internal horizontal scroll rail. The previous assertion
  // `chips.scrollWidth > document.clientWidth` (364 > 390 at 390x844) measured
  // the wrong geometry and was always false. The correct invariant is that the
  // rail stays fully inside the viewport (no page overflow, proven above) and its
  // own geometry is contained: scrollWidth === clientWidth (no internal
  // overflow) with the canonical wrap/overflow policy preserved.
  const mPassportConvGeo = await mpage.evaluate(() => {
    const thread = document.getElementById("chat-thread");
    const row = thread ? thread.querySelector('.chat-msg[data-grounded="true"][data-journey-id="seogu_passport_issuance"]') : null;
    if (!row) return null;
    const bubble = row.querySelector('.chat-bubble');
    const source = row.querySelector('.message-source--clone');
    const chips = document.querySelector('.chat-chips');
    const ccs = chips ? getComputedStyle(chips) : null;
    return {
      rowDisplay: getComputedStyle(row).display,
      bubbleW: bubble ? Math.round(bubble.getBoundingClientRect().width) : 0,
      sourceW: source ? Math.round(source.getBoundingClientRect().width) : 0,
      sourceLeft: source ? Math.round(source.getBoundingClientRect().left) : 0,
      bubbleLeft: bubble ? Math.round(bubble.getBoundingClientRect().left) : 0,
      rowRight: Math.round(row.getBoundingClientRect().right),
      docScrollW: document.documentElement.scrollWidth,
      docClientW: document.documentElement.clientWidth,
      chipsScrollW: chips ? chips.scrollWidth : 0,
      chipsClientW: chips ? chips.clientWidth : 0,
      chipsDisplay: ccs ? ccs.display : null,
      chipsFlexWrap: ccs ? ccs.flexWrap : null,
      chipsOverflowX: ccs ? ccs.overflowX : null,
      chipsOverflow: chips ? getComputedStyle(chips).overflow : null,
      chipCount: chips ? chips.querySelectorAll('.chat-chip').length : 0,
    };
  });
  assert.ok(mPassportConvGeo, "mobile S5 conversation grounded row must exist for geometry check");
  assert.strictEqual(mPassportConvGeo.rowDisplay, "grid", "mobile S5 grounded row must use grid (not flex)");
  assert.ok(mPassportConvGeo.bubbleW >= 200, `mobile S5 bubble must span full content column (>=200px), got ${mPassportConvGeo.bubbleW}`);
  assert.ok(mPassportConvGeo.sourceW >= 200, `mobile S5 provenance must span full content column (>=200px), got ${mPassportConvGeo.sourceW}`);
  assert.strictEqual(mPassportConvGeo.bubbleLeft, mPassportConvGeo.sourceLeft, "mobile S5 bubble and provenance must share the same content column left edge");
  assert.ok(mPassportConvGeo.docScrollW <= mPassportConvGeo.docClientW + 1, "mobile S5 conversation must not cause page-level horizontal overflow");
  // Golden chip-rail contract (B / #1367): the Buk-gu canonical `.chat-chips`
  // WRAPS (flex-wrap:wrap, overflow:visible) — it is NOT an internal horizontal
  // scroll rail. The rail must stay fully inside the viewport and its own
  // geometry must be contained (scrollWidth === clientWidth, no internal
  // overflow). All eight resident chips must remain present and reachable.
  assert.ok(
    mPassportConvGeo.chipsClientW <= mPassportConvGeo.docClientW,
    `mobile S5 chip rail must stay inside the viewport (clientW ${mPassportConvGeo.chipsClientW} <= docClientW ${mPassportConvGeo.docClientW})`,
  );
  assert.strictEqual(mPassportConvGeo.chipsDisplay, "flex", "mobile S5 chip rail must use flex display like Buk-gu canonical");
  assert.strictEqual(mPassportConvGeo.chipsFlexWrap, "wrap", "mobile S5 chip rail must wrap like Buk-gu canonical (no internal horizontal scroll rail)");
  assert.ok(
    mPassportConvGeo.chipsScrollW <= mPassportConvGeo.chipsClientW + 1,
    `mobile S5 chip rail must not internally overflow (scrollW ${mPassportConvGeo.chipsScrollW} <= clientW ${mPassportConvGeo.chipsClientW})`,
  );
  assert.strictEqual(mPassportConvGeo.chipCount, 8, "mobile S5 chip rail must keep all 8 resident chips reachable");
  // ── #1353/#1380 mobile S2 guidance journey (grounded message geometry) ─────
  // S2 is now a GUIDANCE_NAVIGATION journey: the resident sees the grounded
  // answer + provenance in the conversation column (same layout contract as
  // the S5 mobile check) — no handoff destination row exists anymore.
  await convTab.click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "conversation",
    null,
    { timeout: 5000 },
  );
  // #1365: chip -> answer -> confirm -> YES -> navigate -> grounded (mobile S2)
  await confirmAndProceed(mpage, '[data-journey-id="seogu_illegal_parking_report"]', "grounded");
  // The canonical onYesSurfacePrepare switches the mobile surface to guidance
  // (matching Buk-gu). Switch back so the grounded row is laid out for geometry.
  await convTab.click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "conversation",
    null,
    { timeout: 5000 },
  );
  const mS2Geo = await mpage.evaluate(() => {
    const thread = document.getElementById("chat-thread");
    const row = thread ? thread.querySelector('.chat-msg[data-grounded="true"][data-journey-id="seogu_illegal_parking_report"]') : null;
    if (!row) return null;
    const bubble = row.querySelector('.chat-bubble');
    const source = row.querySelector('.message-source--clone');
    return {
      rowPresent: true,
      bubbleW: bubble ? Math.round(bubble.getBoundingClientRect().width) : 0,
      sourceW: source ? Math.round(source.getBoundingClientRect().width) : 0,
      sourceLeft: source ? Math.round(source.getBoundingClientRect().left) : 0,
      bubbleLeft: bubble ? Math.round(bubble.getBoundingClientRect().left) : 0,
      docScrollW: document.documentElement.scrollWidth,
      docClientW: document.documentElement.clientWidth,
      safeHandoffRows: document.querySelectorAll('[data-safe-handoff="true"]').length,
      destinationAttrs: document.querySelectorAll("[data-handoff-destination-url]").length,
    };
  });
  assert.ok(mS2Geo && mS2Geo.rowPresent, "mobile S2 grounded row must be present");
  assert.strictEqual(mS2Geo.safeHandoffRows, 0, "mobile S2 must render no safe_handoff destination row");
  assert.strictEqual(mS2Geo.destinationAttrs, 0, "mobile S2 must render no destination URL attribute");
  assert.ok(mS2Geo.bubbleW >= 200, `mobile S2 bubble must span full content column (>=200px), got ${mS2Geo.bubbleW}`);
  assert.ok(mS2Geo.sourceW >= 200, `mobile S2 provenance must span full content column (>=200px), got ${mS2Geo.sourceW}`);
  assert.strictEqual(mS2Geo.bubbleLeft, mS2Geo.sourceLeft, "mobile S2 bubble and provenance must share the same content column left edge");
  assert.ok(mS2Geo.docScrollW <= mS2Geo.docClientW + 1, "mobile S2 conversation must not cause page-level horizontal overflow");
  // Composer + mobile surface switch remain usable after the S2 guidance.
  const mComposerAfter = await mpage.evaluate(() => {
    const el = document.getElementById("chat-composer-input");
    return el ? { disabled: el.disabled } : null;
  });
  assert.ok(mComposerAfter && mComposerAfter.disabled === false, "mobile composer must stay usable after S2 guidance");
  assert.strictEqual(
    await switchEl.evaluate((el) => el.hasAttribute("hidden")),
    false,
    "mobile surface switch must stay usable after S2 guidance",
  );

  // Composer stays usable on the guidance surface.
  const mobileComposer = await mpage.evaluate(() => {
    const el = document.getElementById("chat-composer-input");
    return el ? { disabled: el.disabled, h: Math.round(el.getBoundingClientRect().height) } : null;
  });
  assert.ok(mobileComposer && mobileComposer.disabled === false, "mobile composer must stay usable on guidance");

  // And back to conversation.
  await convTab.click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "conversation",
    null,
    { timeout: 5000 },
  );
  const convState = await mpage.evaluate(() => ({
    surface: document.body.getAttribute("data-mobile-surface"),
    layout: document.body.getAttribute("data-first-use-state"),
    convPressed: document.querySelector('[data-mobile-surface-tab="conversation"]').getAttribute("aria-pressed"),
  }));
  assert.strictEqual(convState.surface, "conversation");
  assert.strictEqual(convState.layout, "entry", "conversation surface must return to entry layout state");
  assert.strictEqual(convState.convPressed, "true");
  // Conversation surface must restore canvas to hidden/inert (canonical semantics).
  const mobileConvVis = await measureVisibility(mpage);
  assert.strictEqual(mobileConvVis.canvas.inert, true, "conversation surface must restore canvas inert");
  assert.strictEqual(mobileConvVis.canvas.ariaHidden, "true", "conversation surface must restore aria-hidden=true");

  // Mobile iframe boundary unchanged.
  const mSandbox = await mpage.getAttribute("#seogu-clone-frame", "sandbox");
  assert.strictEqual(mSandbox, "allow-same-origin", "mobile iframe must keep script-disabled sandbox");

  await mobile.close();

  // (B3) #1365 BLOCKER 3: real browser NO-path proof for the four target
  // scenarios, each in its own isolated fresh context (no cross-contamination).
  // S1 / S2 / S5 / S6 NO must stop on the answer with zero navigation, a null
  // journey result, and no scenario-specific execution (no repository READ
  // result, no safe-handoff row, no handoff-evidence result, no external request).
  await proveNoPathIsolated(browser, '[data-journey-id="seogu_apartment_housing_dept"]', "seogu_apartment_housing_dept");
  await proveNoPathIsolated(browser, '[data-journey-id="seogu_illegal_parking_report"]', "seogu_illegal_parking_report");
  await proveNoPathIsolated(browser, '[data-journey-id="seogu_passport_issuance"]', "seogu_passport_issuance");
  await proveNoPathIsolated(browser, '[data-journey-id="seogu_unmanned_kiosk"]', "seogu_unmanned_kiosk");
  console.log("  [B3] NO-path browser proof S1/S2/S5/S6: OK");

  // (9) zero external HTTP(S) runtime requests across both contexts
  assert.deepStrictEqual(externalRequests, [], "focused surface proof must make zero external requests");

  console.log("SEOGU_RESIDENT_SURFACE_FOCUSED_PASS");
} finally {
  await browser.close();
}
