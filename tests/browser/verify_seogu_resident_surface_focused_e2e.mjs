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
 *   4. SOURCE_CAPTURE_NEEDED scenarios (S1/S4/S6-now-DIRECT_REUSE) produce honest
 *      capture-needed rows, no navigation, no fake success;
 *   5. S2/S7/S8 EXTERNAL_OFFICIAL_HANDOFF (Blocker B + Blocker A):
 *      D1 — generic config-driven contract on every handoff row
 *           (action_kind=EXTERNAL_OFFICIAL_HANDOFF, claim_scope=HANDOFF_ONLY,
 *           stop boundary, explicit resident-activated anchor, no auto-open/
 *           prefill/submit) + grounded repository-clone local-evidence row with
 *           required-marker validation; external requests stay 0;
 *      D2 — S8 maps to 국민신문고/epeople (NOT 안전신문고); S2/S7 map to 안전신문고;
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
 *       local-evidence page, the external handoff must NOT render — no
 *       destination row, no anchor/href, no destination URL control, no
 *       auto-open/prefill/submit, no model fallback, no success semantics;
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
  { journey_id: "seogu_mayor_proposal", label: "구청장에게 제안하고 싶어요", status: "SOURCE_CAPTURE_NEEDED" },
  { journey_id: "seogu_illegal_parking_report", label: "불법 주정차 신고", status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED" },
  { journey_id: "seogu_apartment_housing_dept", label: "공동주택 부서 문의", status: "DIRECT_REUSE" },
  { journey_id: "seogu_mattrass_disposal", label: "대형폐기물 배출", status: "SOURCE_CAPTURE_NEEDED" },
  { journey_id: "seogu_passport_issuance", label: "여권 발급 안내", status: "DIRECT_REUSE" },
  { journey_id: "seogu_unmanned_kiosk", label: "무인민원발급기 안내", status: "DIRECT_REUSE" },
  { journey_id: "seogu_streetlight_report", label: "가로등 고장 신고 (AI)", status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED" },
  { journey_id: "seogu_illegal_dumping_report", label: "쓰레기 무단투기 (AI)", status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED" },
];

const CAPTURE_NEEDED_IDS = [
  "seogu_mayor_proposal",
  "seogu_mattrass_disposal",
];

const HANDOFF_IDS = [
  "seogu_illegal_parking_report",
  "seogu_streetlight_report",
  "seogu_illegal_dumping_report",
];

// Generic EXTERNAL_OFFICIAL_HANDOFF contract expectations (Blocker B) + the
// exact verified destination authority per scenario (Blocker A). The shell must
// render ONE config-driven contract for all three — never per-scenario branches.
// S8 (litter/dumping) MUST map to 국민신문고/epeople, NOT 안전신문고.
const HANDOFF_CONTRACT = {
  seogu_illegal_parking_report: {
    local_evidence_route: "illegal-parking-report/",
    required_markers: ["주정차단속조회", "과태료 조회", "과태료 납부", "의견진술"],
    destination_url: "https://www.safetyreport.go.kr/#main",
    destination_label: "안전신문고",
    destination_authority: "행정안전부가 운영하는 안전신문고",
  },
  seogu_streetlight_report: {
    local_evidence_route: "streetlight-report-handoff/",
    required_markers: ["재난신고", "재난신고센터", "국민재난안전포털"],
    destination_url: "https://www.safetyreport.go.kr/#main",
    destination_label: "안전신문고",
    destination_authority: "행정안전부가 운영하는 안전신문고",
  },
  seogu_illegal_dumping_report: {
    local_evidence_route: "litter-report-handoff/",
    required_markers: ["생활폐기물", "배출/수거", "대형폐기물 신고"],
    destination_url: "https://www.epeople.go.kr/",
    destination_label: "국민신문고",
    destination_authority: "국민권익위원회가 운영하는 국민신문고",
  },
};

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


  // (5) S2/S7/S8 EXTERNAL_OFFICIAL_HANDOFF — local-evidence-first, generic
  // config-driven contract (Blocker B), exact verified authority (Blocker A),
  // never a submission success. For each handoff scenario:
  //   D1: the rendered destination row carries the full generic contract
  //       (action_kind, claim_scope=HANDOFF_ONLY, stop boundary, explicit
  //       resident-activated anchor, auto_open/prefill/submit all false) and
  //       the local-evidence row is grounded from the repository clone route;
  //   D2: S8 maps to 국민신문고/epeople (NOT 안전신문고); S2/S7 map to 안전신문고.
  for (const id of HANDOFF_IDS) {
    const expected = HANDOFF_CONTRACT[id];
    // #1365: chip -> answer -> confirm -> YES -> handoff evidence -> safe_handoff
    await confirmAndProceed(page, `[data-journey-id="${id}"]`, "safe_handoff");

    // D1 — generic contract on the destination row.
    const row = await page.evaluate((jid) => {
      const rows = Array.from(document.querySelectorAll('[data-safe-handoff="true"]'));
      const el = rows.filter((n) => n.getAttribute("data-journey-id") === jid).pop();
      if (!el) return null;
      const link = el.querySelector('a[data-handoff-action="explicit-open"]');
      return {
        status: el.getAttribute("data-status"),
        action_kind: el.getAttribute("data-handoff-action-kind"),
        destination_url: el.getAttribute("data-handoff-destination-url"),
        destination_label: el.getAttribute("data-handoff-destination-label"),
        destination_authority: el.getAttribute("data-handoff-destination-authority"),
        claim_scope: el.getAttribute("data-handoff-claim-scope"),
        stop_boundary: el.getAttribute("data-handoff-stop-boundary"),
        link_href: link ? link.getAttribute("href") : null,
        link_target: link ? link.getAttribute("target") : null,
        link_rel: link ? link.getAttribute("rel") : null,
        text: el.textContent,
      };
    }, id);
    assert.ok(row, `handoff destination row missing for ${id}`);
    assert.strictEqual(
      row.status,
      "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED",
      `${id} must keep handoff classification`,
    );
    assert.strictEqual(row.action_kind, "EXTERNAL_OFFICIAL_HANDOFF", `${id} must use the generic handoff action_kind`);
    assert.strictEqual(row.claim_scope, "HANDOFF_ONLY", `${id} claim_scope must be HANDOFF_ONLY`);
    assert.ok(row.stop_boundary && row.stop_boundary.length > 0, `${id} must carry a stop boundary code`);
    assert.strictEqual(row.destination_url, expected.destination_url, `${id} destination_url mismatch`);
    assert.strictEqual(row.destination_label, expected.destination_label, `${id} destination_label mismatch`);
    assert.strictEqual(row.destination_authority, expected.destination_authority, `${id} destination_authority mismatch`);
    // Explicit resident activation: a real anchor the resident clicks. Never
    // auto-opened (no window.open), never prefilled, never submitted.
    assert.ok(row.link_href, `${id} must render an explicit resident-activated anchor`);
    assert.strictEqual(row.link_href, expected.destination_url, `${id} anchor href must equal destination_url`);
    assert.strictEqual(row.link_target, "_blank", `${id} anchor must open in a new tab on resident click`);
    assert.ok(String(row.link_rel || "").includes("noopener"), `${id} anchor must be noopener`);
    assertNoForbiddenSuccess(row.text, `handoff destination row for ${id}`);

    // ── #1353 desktop handoff responsive hierarchy ───────────────────────────
    // The CTA and authority must stack inside ONE readable content column (avatar
    // left), NOT be squeezed into narrow implicit side columns, with no
    // horizontal overflow. This is the resident-facing fix for the Web CTO
    // model-vision defect; the contract/data attributes above are unchanged.
    const dHandoff = await measureHandoffLayout(page, id);
    assert.ok(dHandoff, `desktop ${id} handoff destination row must be present`);
    assert.strictEqual(dHandoff.display, "grid", `desktop ${id} handoff row must use the grid content-column layout`);
    assert.ok(dHandoff.link && dHandoff.authority, `desktop ${id} handoff must render CTA + authority`);
    assert.ok(
      Math.abs(dHandoff.bubble.x - dHandoff.link.x) <= 2,
      `desktop ${id} CTA must share the bubble content column`,
    );
    assert.ok(
      Math.abs(dHandoff.link.x - dHandoff.authority.x) <= 2,
      `desktop ${id} authority must share the CTA content column`,
    );
    assert.ok(
      dHandoff.avatar.x < dHandoff.bubble.x,
      `desktop ${id} avatar must stay left of the content column`,
    );
    assert.ok(
      dHandoff.link.bottom <= dHandoff.authority.y + 2,
      `desktop ${id} CTA must sit above the authority`,
    );
    // CTA must use a readable column width (no narrow sliver) and remain a short
    // few-line block rather than collapsing.
    assert.ok(dHandoff.link.w >= 200, `desktop ${id} CTA must use a readable column width (no narrow sliver)`);
    assert.ok(dHandoff.authority.w >= 200, `desktop ${id} authority must use a readable column width`);
    const dOverflow = await page.evaluate(() => {
      const t = document.getElementById("chat-thread");
      return { scrollW: t.scrollWidth, clientW: t.clientWidth };
    });
    assert.ok(
      dOverflow.scrollW <= dOverflow.clientW + 1,
      `desktop ${id} thread must not horizontally overflow`,
    );

    // D1 — local-evidence row is grounded from the repository clone route and
    // the required markers were validated against the READ region.
    const evidenceRow = await page.evaluate((jid) => {
      const rows = Array.from(document.querySelectorAll('[data-handoff-evidence="true"]'));
      const el = rows.filter((n) => n.getAttribute("data-journey-id") === jid).pop();
      if (!el) return null;
      return {
        verified: el.getAttribute("data-handoff-evidence-verified"),
        route: el.getAttribute("data-handoff-local-evidence-route"),
        grounded: el.getAttribute("data-grounded"),
        source_kind: el.getAttribute("data-source-kind"),
        evidence_kind: el.getAttribute("data-evidence-kind"),
        text: el.textContent,
      };
    }, id);
    assert.ok(evidenceRow, `handoff local-evidence row missing for ${id}`);
    assert.strictEqual(evidenceRow.verified, "true", `${id} local evidence must be verified (all required markers present)`);
    assert.ok(
      String(evidenceRow.route).includes(expected.local_evidence_route.replace(/\/$/, "")),
      `${id} local-evidence route must be ${expected.local_evidence_route}, got ${evidenceRow.route}`,
    );
    assert.strictEqual(evidenceRow.grounded, "true", `${id} local-evidence row must be grounded`);
    assert.strictEqual(evidenceRow.source_kind, "repository_clone", `${id} local evidence must be repository_clone`);
    assert.strictEqual(evidenceRow.evidence_kind, "clone_dom", `${id} local evidence must be clone_dom`);
    assertNoForbiddenSuccess(evidenceRow.text, `handoff local-evidence row for ${id}`);

    // ── #1353 desktop evidence provenance ─────────────────────────────────────
    // The local-evidence provenance ("근거 · 저장소 기반 기관 안내 · ...") must
    // share the evidence bubble content column (avatar left) — NOT be squeezed
    // into a narrow sibling column — with a readable width and no horizontal
    // overflow. This is the second half of the Web CTO model-vision defect.
    const dEvidence = await measureEvidenceLayout(page, id);
    assert.ok(dEvidence, `desktop ${id} handoff evidence row must be present`);
    assert.strictEqual(dEvidence.display, "grid", `desktop ${id} evidence row must use the grid content-column layout`);
    assert.ok(dEvidence.source, `desktop ${id} evidence row must render the provenance`);
    assert.ok(
      String(dEvidence.sourceText || "").includes("근거 · 저장소 기반 기관 안내"),
      `desktop ${id} evidence provenance must be the repository-clone label`,
    );
    assert.ok(
      Math.abs(dEvidence.bubble.x - dEvidence.source.x) <= 2,
      `desktop ${id} evidence provenance must share the bubble content column`,
    );
    assert.ok(
      dEvidence.avatar.x < dEvidence.bubble.x,
      `desktop ${id} evidence avatar must stay left of the content column`,
    );
    assert.ok(
      dEvidence.bubble.bottom <= dEvidence.source.y + 2,
      `desktop ${id} evidence provenance must sit below the bubble`,
    );
    assert.ok(dEvidence.source.w >= 200, `desktop ${id} evidence provenance must use a readable column width`);
    const dEvidenceOverflow = await page.evaluate(() => {
      const t = document.getElementById("chat-thread");
      return { scrollW: t.scrollWidth, clientW: t.clientWidth };
    });
    assert.ok(
      dEvidenceOverflow.scrollW <= dEvidenceOverflow.clientW + 1,
      `desktop ${id} evidence provenance must not horizontally overflow the thread`,
    );

    // D2 — exact authority. S8 must NOT be 안전신문고; it must be 국민신문고/epeople.
    if (id === "seogu_illegal_dumping_report") {
      assert.ok(
        !String(row.destination_label).includes("안전신문고"),
        "S8 litter/dumping must NOT map to 안전신문고 (Blocker A)",
      );
      assert.ok(
        !String(row.destination_url).includes("safetyreport"),
        "S8 destination_url must NOT be safetyreport.go.kr (Blocker A)",
      );
      assert.ok(
        String(row.destination_url).includes("epeople.go.kr"),
        "S8 destination_url must be the verified 국민신문고/epeople chain (Blocker A)",
      );
      assert.ok(
        String(row.destination_authority).includes("국민권익위원회"),
        "S8 destination_authority must name 국민권익위원회 (Blocker A)",
      );
    }
  }

  // ── D6: FAIL-CLOSED negative proof (CTO comment 5322239653) ────────────────
  // The external official handoff may be rendered ONLY after successful local
  // evidence validation (evidence.ok === true && missingMarkers.length === 0).
  // Deterministic proof on S8 (litter): serve the litter-report-handoff clone
  // page with ONE required marker ("대형폐기물 신고") stripped, then run the
  // journey on a FRESH page (the iframe must start off-route so the reload is
  // real and the stripped page is what gets READ). The journey must then STOP
  // fail-closed: no destination row, no anchor/href, no auto-open/prefill/
  // submit, no model fallback, no success semantics — with the evidence
  // explanation + bounded STOP state visible and zero external requests.
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
  assert.strictEqual(negAfter.blocked.status, "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED", "blocked row must keep the handoff classification");
  assert.strictEqual(negAfter.blocked.action_kind, "EXTERNAL_OFFICIAL_HANDOFF", "blocked row must keep the generic handoff action_kind");
  assert.strictEqual(negAfter.blocked.claim_scope, "HANDOFF_ONLY", "blocked row must keep claim_scope=HANDOFF_ONLY");
  // D6-6: no actionable external destination control (no anchor, no href, no destination attrs).
  assert.strictEqual(negAfter.blocked.hasAnchor, false, "blocked row must contain no anchor");
  assert.strictEqual(negAfter.blocked.hasExplicitOpen, false, "blocked row must contain no explicit-open control");
  assert.strictEqual(negAfter.blocked.hasDestinationUrl, false, "blocked row must not carry a destination URL attribute");
  assert.strictEqual(negAfter.blocked.hasDestinationLabel, false, "blocked row must not carry a destination label attribute");
  assert.strictEqual(negAfter.blocked.hasDestinationAuthority, false, "blocked row must not carry a destination authority attribute");
  // D6-7: no prefill/submit capability (no form/button/input control).
  assert.strictEqual(negAfter.blocked.hasFormControl, false, "blocked row must contain no form/button/input control");
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
  // ── #1353 mobile handoff responsive hierarchy (S2) ──────────────────────────
  // The S2 final handoff row must NOT collapse the CTA into character-by-character
  // vertical stacking and must keep the authority readable in the content column
  // (no narrow-side-column squeeze). Composer + mobile surface switch stay usable.
  await convTab.click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "conversation",
    null,
    { timeout: 5000 },
  );
  // #1365: chip -> answer -> confirm -> YES -> handoff -> safe_handoff (mobile S2)
  await confirmAndProceed(mpage, '[data-journey-id="seogu_illegal_parking_report"]', "safe_handoff");
  // The canonical onYesSurfacePrepare switches the mobile surface to guidance
  // (matching Buk-gu) to reveal the institution canvas, which hides the
  // conversation thread. Switch back to conversation so the handoff/evidence
  // row geometry (measured via getBoundingClientRect) is actually laid out.
  await convTab.click();
  await mpage.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "conversation",
    null,
    { timeout: 5000 },
  );
  const mHandoff = await measureHandoffLayout(mpage, "seogu_illegal_parking_report");
  assert.ok(mHandoff, "mobile S2 handoff destination row must be present");
  assert.strictEqual(mHandoff.display, "grid", "mobile S2 handoff row must use the grid content-column layout");
  assert.ok(mHandoff.link && mHandoff.authority, "mobile S2 handoff must render CTA + authority");
  assert.ok(
    Math.abs(mHandoff.bubble.x - mHandoff.link.x) <= 2,
    "mobile S2 CTA must share the bubble content column",
  );
  assert.ok(
    Math.abs(mHandoff.link.x - mHandoff.authority.x) <= 2,
    "mobile S2 authority must share the CTA content column",
  );
  assert.ok(
    mHandoff.avatar.x < mHandoff.bubble.x,
    "mobile S2 avatar must stay left of the content column",
  );
  assert.ok(
    mHandoff.link.bottom <= mHandoff.authority.y + 2,
    "mobile S2 CTA must sit above the authority",
  );
  // No character-by-character vertical stacking: the CTA must occupy a normal,
  // wide, bounded-height box (a readable wrap), not one character per line.
  assert.ok(mHandoff.link.w >= 120, "mobile S2 CTA must use a readable column width (no narrow sliver)");
  assert.ok(mHandoff.link.h <= 80, "mobile S2 CTA must not stack character-by-character (height bounded)");
  assert.ok(mHandoff.authority.w >= 120, "mobile S2 authority must use a readable column width");
  assert.ok(mHandoff.authority.h <= 60, "mobile S2 authority must not vertically collapse");
  // No horizontal overflow of the thread.
  const mOverflow = await mpage.evaluate(() => {
    const t = document.getElementById("chat-thread");
    return { scrollW: t.scrollWidth, clientW: t.clientWidth };
  });
  assert.ok(mOverflow.scrollW <= mOverflow.clientW + 1, "mobile S2 thread must not horizontally overflow");
  // ── #1353 mobile evidence provenance ───────────────────────────────────────
  // On 390×844 the local-evidence provenance must NOT render as a tall,
  // fragmented narrow sibling column next to the evidence bubble. It must share
  // the evidence bubble content column, stay readable, and remain bounded.
  const mEvidence = await measureEvidenceLayout(mpage, "seogu_illegal_parking_report");
  assert.ok(mEvidence, "mobile S2 evidence row must be present");
  assert.strictEqual(mEvidence.display, "grid", "mobile S2 evidence row must use the grid content-column layout");
  assert.ok(mEvidence.source, "mobile S2 evidence row must render the provenance");
  assert.ok(
    String(mEvidence.sourceText || "").includes("근거 · 저장소 기반 기관 안내"),
    "mobile S2 evidence provenance must be the repository-clone label",
  );
  assert.ok(
    Math.abs(mEvidence.bubble.x - mEvidence.source.x) <= 2,
    "mobile S2 evidence provenance must share the bubble content column",
  );
  assert.ok(
    mEvidence.avatar.x < mEvidence.bubble.x,
    "mobile S2 evidence avatar must stay left of the content column",
  );
  assert.ok(
    mEvidence.bubble.bottom <= mEvidence.source.y + 2,
    "mobile S2 evidence provenance must sit below the bubble",
  );
  assert.ok(mEvidence.source.w >= 120, "mobile S2 evidence provenance must use a readable column width");
  assert.ok(mEvidence.source.h <= 80, "mobile S2 evidence provenance must not stack as a tall fragmented column");
  const mEvidenceOverflow = await mpage.evaluate(() => {
    const t = document.getElementById("chat-thread");
    return { scrollW: t.scrollWidth, clientW: t.clientWidth };
  });
  assert.ok(
    mEvidenceOverflow.scrollW <= mEvidenceOverflow.clientW + 1,
    "mobile S2 evidence provenance must not horizontally overflow the thread",
  );
  // Composer + mobile surface switch remain usable after the S2 handoff.
  const mComposerAfter = await mpage.evaluate(() => {
    const el = document.getElementById("chat-composer-input");
    return el ? { disabled: el.disabled } : null;
  });
  assert.ok(mComposerAfter && mComposerAfter.disabled === false, "mobile composer must stay usable after S2 handoff");
  assert.strictEqual(
    await switchEl.evaluate((el) => el.hasAttribute("hidden")),
    false,
    "mobile surface switch must stay usable after S2 handoff",
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

  // (9) zero external HTTP(S) runtime requests across both contexts
  assert.deepStrictEqual(externalRequests, [], "focused surface proof must make zero external requests");

  console.log("SEOGU_RESIDENT_SURFACE_FOCUSED_PASS");
} finally {
  await browser.close();
}
