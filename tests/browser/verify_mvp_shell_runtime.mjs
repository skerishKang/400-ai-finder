// tests/browser/verify_mvp_shell_runtime.mjs
//
// Executable runtime verification for the #925/#927 MVP first-use shell.
//
// Constraints (per task):
//   - no Playwright, no external network, no real fetch
//   - uses only node:assert, node:fs, node:vm
//   - reads src/web/static/citizen-first-use-shell.js and executes its IIFE
//     inside a minimal fake DOM/window with injected test doubles
//     (window.CitizenMvpBridge, window.CitizenFirstChoreography).

import { readFileSync } from "node:fs";
import assert from "node:assert";
import vm from "node:vm";

const SHELL_PATH = new URL(
  "../../src/web/static/citizen-first-use-shell.js",
  import.meta.url,
);
const shellCode = readFileSync(SHELL_PATH, "utf8");

// ── Fake DOM ────────────────────────────────────────────────────────────

function makeEl(tag) {
  const el = {
    tagName: tag || "div",
    id: "",
    className: "",
    style: {},
    disabled: false,
    hidden: false,
    value: "",
    _textContent: "",
    _attrs: {},
    _children: [],
    _listeners: {},
    scrollTop: 0,
    scrollHeight: 0,
    setAttribute(k, v) {
      this._attrs[k] = String(v);
    },
    getAttribute(k) {
      return Object.prototype.hasOwnProperty.call(this._attrs, k)
        ? this._attrs[k]
        : null;
    },
    hasAttribute(k) {
      return Object.prototype.hasOwnProperty.call(this._attrs, k);
    },
    removeAttribute(k) {
      delete this._attrs[k];
    },
    appendChild(c) {
      this._children.push(c);
      return c;
    },
    removeChild(c) {
      const i = this._children.indexOf(c);
      if (i >= 0) this._children.splice(i, 1);
    },
    addEventListener(type, fn) {
      (this._listeners[type] = this._listeners[type] || []).push(fn);
    },
    removeEventListener() {},
    dispatchEvent() {},
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
    focus() {},
    scrollIntoView() {},
  };
  el.classList = {
    _s: new Set(),
    add(c) {
      this._s.add(c);
    },
    remove(c) {
      this._s.delete(c);
    },
    contains(c) {
      return this._s.has(c);
    },
    toggle(c) {
      if (this._s.has(c)) this._s.delete(c);
      else this._s.add(c);
    },
  };
  Object.defineProperty(el, "innerHTML", {
    get() {
      return this._html || "";
    },
    set(v) {
      this._html = v;
      if (v === "") this._children = [];
    },
  });
  // textContent aggregates real-DOM-like: leaf text plus recursion over
  // children, so a body that contains the chat-thread subtree will surface
  // the actual rendered chat bubble text.
  Object.defineProperty(el, "textContent", {
    configurable: true,
    get() {
      if (this._children && this._children.length) {
        let out = "";
        for (const c of this._children) {
          out += c.textContent || "";
        }
        return out;
      }
      return this._textContent || "";
    },
    set(v) {
      this._textContent = String(v);
      this._children = [];
    },
  });
  return el;
}

function buildDoc() {
  const ids = {};
  const body = makeEl("body");
  const head = makeEl("head");
  const ensure = (id) => {
    if (!ids[id]) {
      ids[id] = makeEl("div");
      ids[id].id = id;
      body.appendChild(ids[id]);
    }
    return ids[id];
  };
  return {
    _ids: ids,
    body,
    head,
    getElementById(id) {
      return ensure(id);
    },
    createElement(tag) {
      return makeEl(tag);
    },
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
    addEventListener() {},
  };
}

function buildWindow({ search, reducedMotion, bridge, choreo }) {
  return {
    location: {
      search: search || "",
      href: "http://localhost/" + (search || ""),
      pathname: "/",
    },
    matchMedia(q) {
      return {
        matches: !!reducedMotion,
        media: q,
        addListener() {},
        removeListener() {},
        addEventListener() {},
        removeEventListener() {},
      };
    },
    requestAnimationFrame(cb) {
      cb(0);
      return 1;
    },
    cancelAnimationFrame() {},
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    CitizenMvpBridge: bridge,
    CitizenFirstChoreography: choreo,
  };
}

// ── Test doubles ───────────────────────────────────────────────────────────

function makeResolvingBridge(result) {
  return {
    askCalled: 0,
    cancelCalled: 0,
    ask(q) {
      this.askCalled++;
      return Promise.resolve(result);
    },
    cancel() {
      this.cancelCalled++;
    },
  };
}

function makeRejectingBridge(error) {
  return {
    askCalled: 0,
    cancelCalled: 0,
    ask() {
      this.askCalled++;
      return Promise.reject(error);
    },
    cancel() {
      this.cancelCalled++;
    },
  };
}

function makePendingBridge() {
  return {
    askCalled: 0,
    cancelCalled: 0,
    _resolve: null,
    ask(q) {
      this.askCalled++;
      return new Promise((res) => {
        this._resolve = res;
      });
    },
    cancel() {
      this.cancelCalled++;
    },
  };
}

function makeChoreo() {
  return {
    startCalls: [],
    cancelCalls: 0,
    start(action) {
      this.startCalls.push(action);
    },
    cancel() {
      this.cancelCalls++;
    },
    getState() {
      return "idle";
    },
  };
}

// ── Scenario runner ───────────────────────────────────────────────────────

function runScenario({ search, reducedMotion, bridge, choreo }) {
  const doc = buildDoc();
  const win = buildWindow({ search, reducedMotion, bridge, choreo });
  const context = {
    window: win,
    document: doc,
    console,
    URLSearchParams,
    Promise,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    Math,
    Object,
    String,
    Boolean,
    Array,
    JSON,
    Number,
    Date,
    requestAnimationFrame: win.requestAnimationFrame,
  };
  context.globalThis = context;
  vm.createContext(context);
  vm.runInContext(shellCode, context);
  return { ctx: context, win, doc, bridge, choreo };
}

function submit(scenario, question) {
  const form = scenario.doc.getElementById("chat-composer-form");
  scenario.doc.getElementById("chat-composer-input").value = question;
  const handlers = form._listeners.submit || [];
  for (const h of handlers) h({ preventDefault() {} });
}

function aiBubbleTexts(scenario) {
  const thread = scenario.doc.getElementById("chat-thread");
  const out = [];
  for (const msg of thread._children) {
    if (!((msg.className || "").includes("chat-msg--ai"))) continue;
    for (const child of msg._children) {
      if ((child.className || "").includes("chat-bubble")) {
        out.push(child.textContent);
      }
    }
  }
  return out;
}

function canvasAriaHidden(scenario) {
  return scenario.doc.getElementById("demo-canvas").getAttribute("aria-hidden");
}

function canvasInert(scenario) {
  return scenario.doc.getElementById("demo-canvas").hasAttribute("inert");
}

function assertSplitCloneVisible(scenario, label) {
  assert.strictEqual(
    scenario.win.CitizenFirstUseShell.getState(),
    "split",
    `${label}: shell must transition to split`,
  );
  assert.strictEqual(
    canvasAriaHidden(scenario),
    "false",
    `${label}: left clone must be exposed to the accessibility tree`,
  );
  assert.strictEqual(
    canvasInert(scenario),
    false,
    `${label}: left clone must not remain inert after split`,
  );
}

function assertComposerRecovered(scenario, label) {
  const input = scenario.doc.getElementById("chat-composer-input");
  const send = scenario.doc.getElementById("chat-composer-send");
  assert.strictEqual(
    input.disabled,
    false,
    `${label}: composer input must be re-enabled after resolution`,
  );
  assert.strictEqual(
    send.disabled,
    false,
    `${label}: composer send must be re-enabled after resolution`,
  );
}

const flush = () => new Promise((r) => setTimeout(r, 0));

// ── Scenarios ─────────────────────────────────────────────────────────────

async function scenarioIllegalParking() {
  const bridge = makeResolvingBridge({
    ok: true,
    answer: "불법 주정차 신고는 종합민원에서 안내합니다.",
    action: "illegal_parking",
    confidence: 0.9,
    quest: {
      quest_id: "illegal_parking_report_guidance",
      quest_name: "불법 주정차 신고 안내",
      source_mode: "local_static",
      match_status: "matched",
    },
    action_plan: {
      quest_id: "illegal_parking_report_guidance",
      quest_name: "불법 주정차 신고 안내",
      official_path: ["종합민원", "민원신고", "불법 주정차 신고"],
      source_mode: "local_static",
      stop_condition: "STOP_FOR_USER_CONFIRMATION",
      result: {
        service: "불법 주정차 신고",
        surface: "불법 주정차 신고 카드",
      },
      browser_actions: [
        { label: "종합민원 메뉴 확인" },
        { label: "불법 주정차 신고 화면 이동" },
        { label: "불법 주정차 신고 카드 확인" },
      ],
      final_warning: {
        warning_text: "실제 신고 제출과 본인인증은 사용자가 직접 확인해야 합니다.",
        requires_user_confirmation: true,
      },
    },
  });
  const choreo = makeChoreo();
  const s = runScenario({
    search: "?mvp=1",
    reducedMotion: true,
    bridge,
    choreo,
  });
  submit(s, "불법 주정차 신고는 어디서 하나요?");
  await flush();

  const bubbles = aiBubbleTexts(s);
  assert.ok(
    bubbles.includes("불법 주정차 신고는 종합민원에서 안내합니다."),
    "illegal_parking: server answer must be shown in assistant bubble",
  );
  assert.strictEqual(
    s.win.CitizenFirstUseShell.getState(),
    "split",
    "illegal_parking: shell must transition to split (reduced motion)",
  );
  assertSplitCloneVisible(s, "illegal_parking");
  assert.deepStrictEqual(
    choreo.startCalls,
    ["illegal_parking"],
    "illegal_parking: choreography.start('illegal_parking') called exactly once",
  );
  const card = s.doc.getElementById("chat-thread")._children.find((node) => {
    return (node.className || "").includes("chat-quest-card");
  });
  assert.ok(card, "illegal_parking: quest card must be appended from metadata");
  assert.strictEqual(card.getAttribute("data-quest-card"), "action_plan");
  assert.strictEqual(card.getAttribute("data-quest-id"), "illegal_parking_report_guidance");
  const cardText = card.textContent;
  assert.ok(cardText.includes("불법 주정차 신고 안내"));
  assert.ok(cardText.includes("종합민원 > 민원신고 > 불법 주정차 신고"));
  assert.ok(cardText.includes("불법 주정차 신고 / 불법 주정차 신고 카드"));
  assert.ok(cardText.includes("STOP_FOR_USER_CONFIRMATION"));
  assert.ok(cardText.includes("local_static"));
  assert.ok(cardText.includes("불법 주정차 신고 화면 이동"));
  assert.ok(cardText.includes("실제 신고 제출과 본인인증"));
  console.log("  [1] illegal_parking: OK");
}

async function scenarioHousingDepartment() {
  const bridge = makeResolvingBridge({
    ok: true,
    answer: "공동주택 관련 문의는 공동주택과(062-410-6033)에서 담당합니다.",
    action: "housing_department",
    confidence: 0.9,
    quest: {
      quest_id: "housing_department_lookup",
      quest_name: "공동주택 담당부서 찾기",
      official_path: ["북구소개", "구청안내", "업무 및 전화번호 안내", "공동주택과"],
      result: { department: "공동주택과", phone: "062-410-6033" },
      source_mode: "local_static",
    },
    action_plan: {
      official_path: ["북구소개", "구청안내", "업무 및 전화번호 안내", "공동주택과"],
      browser_actions: [
        { label: "업무 및 전화번호 안내 이동" },
        { label: "공동주택 검색" },
      ],
      result: { department: "공동주택과", phone: "062-410-6033" },
      source_mode: "local_static",
      stop_condition: "STOP_AFTER_RESULT",
      final_warning: null,
    },
  });
  const choreo = makeChoreo();
  const s = runScenario({
    search: "?mvp=1",
    reducedMotion: true,
    bridge,
    choreo,
  });
  submit(s, "공동주택과 전화번호 알려줘");
  await flush();

  const bubbles = aiBubbleTexts(s);
  assert.ok(
    bubbles.includes(
      "공동주택 관련 문의는 공동주택과(062-410-6033)에서 담당합니다.",
    ),
    "housing_department: server answer must be shown",
  );
  assertSplitCloneVisible(s, "housing_department");
  assert.deepStrictEqual(
    choreo.startCalls,
    ["housing_department"],
    "housing_department: choreography.start('housing_department') once",
  );
  const card = s.win.CitizenFirstUseShell.renderQuestProgressCard();
  assert.ok(card, "housing_department: quest card must render from stored metadata");
  assert.strictEqual(card.getAttribute("data-quest-card"), "action_plan");
  const cardText = card.textContent;
  assert.ok(cardText.includes("공동주택 담당부서 찾기"));
  assert.ok(cardText.includes("housing_department_lookup"));
  assert.ok(cardText.includes("북구소개 > 구청안내 > 업무 및 전화번호 안내 > 공동주택과"));
  assert.ok(cardText.includes("공동주택과 / 062-410-6033"));
  assert.ok(cardText.includes("업무 및 전화번호 안내 이동"));
  assert.ok(cardText.includes("공동주택 검색"));
  assert.ok(cardText.includes("local_static"));
  assert.ok(cardText.includes("STOP_AFTER_RESULT"));
  console.log("  [2] housing_department: OK");
}

async function scenarioBulkyWaste() {
  const bridge = makeResolvingBridge({
    ok: true,
    answer: "대형폐기물 배출 신청 경로를 안내해 드립니다.",
    action: "bulky_waste",
    confidence: 0.92,
    quest: {
      quest_id: "bulky_waste_disposal_guidance",
      quest_name: "대형폐기물 배출 안내",
      source_mode: "local_static",
      match_status: "matched",
    },
    action_plan: {
      quest_id: "bulky_waste_disposal_guidance",
      quest_name: "대형폐기물 배출 안내",
      official_path: ["종합민원", "분야별정보", "대형폐기물 처리"],
      source_mode: "local_static",
      stop_condition: "STOP_FOR_USER_CONFIRMATION",
      result: {
        service: "대형폐기물 배출 안내",
        surface: "대형폐기물 신청 안내 카드",
      },
      browser_actions: [
        { label: "종합민원 메뉴 확인" },
        { label: "대형폐기물 배출 안내 화면 이동" },
        { label: "대형폐기물 배출/신청 안내 확인" },
        { label: "사용자 확인 대기" },
      ],
      final_warning: {
        warning_text: "실제 대형폐기물 신청, 품목·주소·연락처 입력, 수수료 결제, 스티커 출력 또는 배출신고 제출은 사용자가 공식 페이지에서 직접 확인해야 합니다.",
        requires_user_confirmation: true,
      },
    },
  });
  const choreo = makeChoreo();
  const s = runScenario({
    search: "?mvp=1",
    reducedMotion: true,
    bridge,
    choreo,
  });
  submit(s, "침대 매트리스 버리고 싶어요");
  await flush();

  const bubbles = aiBubbleTexts(s);
  assert.ok(
    bubbles.includes("대형폐기물 배출 신청 경로를 안내해 드립니다."),
    "bulky_waste: server answer must be shown",
  );
  assertSplitCloneVisible(s, "bulky_waste");
  assert.deepStrictEqual(
    choreo.startCalls,
    ["bulky_waste"],
    "bulky_waste: choreography.start('bulky_waste') once",
  );
  const card = s.doc.getElementById("chat-thread")._children.find((node) => {
    return (node.className || "").includes("chat-quest-card");
  });
  assert.ok(card, "bulky_waste: quest card must be appended from metadata");
  assert.strictEqual(card.getAttribute("data-quest-card"), "action_plan");
  assert.strictEqual(card.getAttribute("data-quest-id"), "bulky_waste_disposal_guidance");
  const cardText = card.textContent;
  assert.ok(cardText.includes("대형폐기물 배출 안내"));
  assert.ok(cardText.includes("종합민원 > 분야별정보 > 대형폐기물 처리"));
  assert.ok(cardText.includes("대형폐기물 배출 안내 / 대형폐기물 신청 안내 카드"));
  assert.ok(cardText.includes("STOP_FOR_USER_CONFIRMATION"));
  assert.ok(cardText.includes("local_static"));
  assert.ok(cardText.includes("대형폐기물 배출 안내 화면 이동"));
  assert.ok(cardText.includes("수수료 결제"));
  assert.ok(cardText.includes("스티커 출력"));
  console.log("  [2.5] bulky_waste: OK");
}

async function scenarioMoveInReport() {
  const bridge = makeResolvingBridge({
    ok: true,
    answer: "전입신고 경로를 안내해 드립니다.",
    action: "move_in_report",
    confidence: 0.92,
    quest: {
      quest_id: "move_in_report_guidance",
      quest_name: "전입신고 안내",
      source_mode: "local_static",
      match_status: "matched",
    },
    action_plan: {
      quest_id: "move_in_report_guidance",
      quest_name: "전입신고 안내",
      official_path: ["종합민원", "전자민원창구", "정부24", "전입신고 안내"],
      source_mode: "local_static",
      stop_condition: "STOP_FOR_USER_CONFIRMATION",
      result: {
        service: "전입신고 안내",
        surface: "전입신고 안내 카드",
      },
      browser_actions: [
        { label: "종합민원 메뉴 확인" },
        { label: "전입신고 안내 화면 이동" },
        { label: "전입신고 안내 카드 확인" },
        { label: "사용자 확인 대기" },
      ],
      final_warning: {
        warning_text: "실제 전입신고, 본인인증, 세대주·주소·가족관계 등 개인정보 입력, 정부24 또는 주민센터 민원 제출은 사용자가 공식 채널에서 직접 확인해야 합니다.",
        requires_user_confirmation: true,
      },
    },
  });
  const choreo = makeChoreo();
  const s = runScenario({
    search: "?mvp=1",
    reducedMotion: true,
    bridge,
    choreo,
  });
  submit(s, "이사 왔는데 전입신고는 어떻게 해요?");
  await flush();

  const bubbles = aiBubbleTexts(s);
  assert.ok(
    bubbles.includes("전입신고 경로를 안내해 드립니다."),
    "move_in_report: server answer must be shown",
  );
  assertSplitCloneVisible(s, "move_in_report");
  assert.deepStrictEqual(
    choreo.startCalls,
    ["move_in_report"],
    "move_in_report: choreography.start('move_in_report') once",
  );
  const card = s.doc.getElementById("chat-thread")._children.find((node) => {
    return (node.className || "").includes("chat-quest-card");
  });
  assert.ok(card, "move_in_report: quest card must be appended from metadata");
  assert.strictEqual(card.getAttribute("data-quest-card"), "action_plan");
  assert.strictEqual(card.getAttribute("data-quest-id"), "move_in_report_guidance");
  const cardText = card.textContent;
  assert.ok(cardText.includes("전입신고 안내"));
  assert.ok(cardText.includes("종합민원 > 전자민원창구 > 정부24 > 전입신고 안내"));
  assert.ok(cardText.includes("전입신고 안내 / 전입신고 안내 카드"));
  assert.ok(cardText.includes("STOP_FOR_USER_CONFIRMATION"));
  assert.ok(cardText.includes("local_static"));
  assert.ok(cardText.includes("전입신고 안내 화면 이동"));
  assert.ok(cardText.includes("본인인증"));
  assert.ok(cardText.includes("세대주"));
  assert.ok(cardText.includes("가족관계"));
  console.log("  [2.75] move_in_report: OK");
}

async function scenarioSupportedQuestionActionNoneFallback() {
  const bridge = makeResolvingBridge({
    ok: true,
    answer: "불법 주정차 신고 경로를 안내하겠습니다.",
    action: "none",
    confidence: 0.75,
  });
  const choreo = makeChoreo();
  const s = runScenario({
    search: "?mvp=1",
    reducedMotion: true,
    bridge,
    choreo,
  });
  submit(s, "불법 주정차 신고는 어디서 하나요?");
  await flush();

  const bubbles = aiBubbleTexts(s);
  assert.ok(
    bubbles.includes("불법 주정차 신고 경로를 안내하겠습니다."),
    "supported none fallback: server answer must still be shown",
  );
  assertSplitCloneVisible(s, "supported none fallback");
  assert.deepStrictEqual(
    choreo.startCalls,
    ["illegal_parking"],
    "supported none fallback: exact supported question opens existing illegal_parking clone journey",
  );
  console.log("  [3] supported question action=none fallback: OK");
}

async function scenarioNone() {
  const bridge = makeResolvingBridge({
    ok: true,
    answer: "북구청 민원·부서 등을 안내할 수 있습니다.",
    action: "none",
    confidence: 0.8,
  });
  const choreo = makeChoreo();
  const s = runScenario({
    search: "?mvp=1",
    reducedMotion: true,
    bridge,
    choreo,
  });
  submit(s, "오늘 날씨 어떠세요?");
  await flush();

  const bubbles = aiBubbleTexts(s);
  assert.ok(
    bubbles.includes("북구청 민원·부서 등을 안내할 수 있습니다."),
    "none: server answer must be shown",
  );
  assert.strictEqual(
    s.win.CitizenFirstUseShell.getState(),
    "entry",
    "none: shell must stay in entry (no split)",
  );
  assert.strictEqual(
    choreo.startCalls.length,
    0,
    "none: choreography must NOT start",
  );
  assert.strictEqual(
    canvasAriaHidden(s),
    "true",
    "none: left clone must remain hidden/inert",
  );
  assert.strictEqual(
    canvasInert(s),
    true,
    "none: left clone must remain inert",
  );
  console.log("  [4] none: OK");
}

async function scenarioPendingThenReset() {
  const bridge = makePendingBridge();
  const choreo = makeChoreo();
  const s = runScenario({
    search: "?mvp=1",
    reducedMotion: true,
    bridge,
    choreo,
  });
  submit(s, "불법 주정차 신고는 어디서 하나요?");
  assert.strictEqual(bridge.askCalled, 1, "pending: ask() called once");

  // Reset while the request is still pending.
  s.win.CitizenFirstUseShell.reset();
  assert.strictEqual(bridge.cancelCalled, 1, "pending: bridge.cancel() called on reset");

  // Late response arrives after reset.
  bridge._resolve({
    ok: true,
    answer: "늦은 응답",
    action: "illegal_parking",
    confidence: 0.9,
  });
  await flush();

  assert.strictEqual(
    s.win.CitizenFirstUseShell.getState(),
    "entry",
    "pending: late response must not move shell to split",
  );
  assert.strictEqual(
    choreo.startCalls.length,
    0,
    "pending: late response must not start choreography",
  );
  const input = s.doc.getElementById("chat-composer-input");
  const send = s.doc.getElementById("chat-composer-send");
  assert.strictEqual(input.disabled, false, "pending: composer input enabled");
  assert.strictEqual(send.disabled, false, "pending: composer send enabled");
  console.log("  [5] pending + reset: OK");
}

async function scenarioDefaultModeRegression() {
  // MVP bridge present but default mode (no ?mvp=1) must not use it.
  const bridge = makeResolvingBridge({
    ok: true,
    answer: "x",
    action: "none",
    confidence: 0.5,
  });
  const choreo = makeChoreo();
  const s = runScenario({
    search: "",
    reducedMotion: true,
    bridge,
    choreo,
  });
  submit(s, "불법 주정차 신고는 어디서 하나요?");
  await flush();

  assert.strictEqual(
    bridge.askCalled,
    0,
    "default mode: bridge.ask() must NOT be called",
  );
  assert.strictEqual(
    choreo.startCalls.length,
    0,
    "default mode: choreography must wait for user confirm before starting",
  );
  assertSplitCloneVisible(s, "default mode");
  // Confirm-run message must be present in the chat thread
  var thread = s.doc.getElementById("chat-thread");
  var hasConfirmRun = false;
  for (var ci = 0; ci < (thread._children || []).length; ci++) {
    if ((thread._children[ci].getAttribute("data-msg-type") || "") === "confirm-run") {
      hasConfirmRun = true;
      break;
    }
  }
  assert.ok(hasConfirmRun, "default mode: confirm-run UI must be shown after split");
  console.log("  [6] default static mode regression: OK");
}

// ── Scenario: failure diagnostics must stay hidden from citizen shell ────
// This scenario validates that when the MVP bridge returns a failure response
// (ok=false) with additional diagnostic fields (failure_code, error, URL,
// authorization), the citizen shell must:
//   - show only the generic Korean failure answer (no diagnostic text)
//   - NOT start choreography (choreo.startCalls.length === 0)
//   - NOT split the shell (stay in entry state)
//   - keep the canvas hidden/inert

const FAILURE_DIAGNOSTIC_CANARIES = [
  "timeout",
  "CANARY_SECRET_MUST_NOT_RENDER",
  "https://private.invalid/forbidden",
  "Authorization: Bearer",
  "CANARY_TOKEN_MUST_NOT_RENDER",
];

// Untrusted answer text that a malicious/failure response might try to inject
// into the citizen chat DOM despite ok:false.
const FAILURE_ANSWER_CANARIES = [
  "CANARY_FAILURE_ANSWER_MUST_NOT_RENDER",
  "https://private.invalid/failure",
  "CANARY_FAILURE_TOKEN",
];

// Shared assertion: the rendered shell must show the generic Korean failure
// message and must NOT expose any of the supplied forbidden strings, checked
// both against the whole rendered body aggregate and the aggregated AI bubble
// text (the actual chat bubble path the shell produces).
function assertFailureHidden(visibleText, aiText, forbidden, label) {
  assert.ok(
    visibleText.includes("현재 AI 안내를 연결하지 못했습니다."),
    `${label}: generic Korean failure must be visible in rendered body`,
  );
  assert.ok(
    aiText.includes("현재 AI 안내를 연결하지 못했습니다."),
    `${label}: generic Korean failure must be in AI bubble text`,
  );
  for (const canary of forbidden) {
    assert.ok(
      !visibleText.includes(canary),
      `${label}: forbidden string '${canary}' must NOT appear in body text`,
    );
    assert.ok(
      !aiText.includes(canary),
      `${label}: forbidden string '${canary}' must NOT appear in AI bubble text`,
    );
  }
}

async function scenarioFailureDiagnosticHidden(failureCode) {
  const bridge = makeResolvingBridge({
    ok: false,
    question: "테스트 질문",
    answer: "현재 AI 안내를 연결하지 못했습니다.",
    action: "none",
    confidence: 0.0,
    failure_code: failureCode,
    error: "CANARY_SECRET_MUST_NOT_RENDER",
    upstream_url: "https://private.invalid/forbidden",
    authorization: "Authorization: Bearer CANARY_TOKEN_MUST_NOT_RENDER",
  });
  const choreo = makeChoreo();
  const s = runScenario({
    search: "?mvp=1",
    reducedMotion: true,
    bridge,
    choreo,
  });
  submit(s, "불법 주정차 신고는 어디서 하나요?");
  await flush();

  const visibleText = s.doc.body.textContent;
  const aiText = aiBubbleTexts(s).join("");
  const forbiddenDiagnostics = [failureCode, ...FAILURE_DIAGNOSTIC_CANARIES];
  assertFailureHidden(visibleText, aiText, forbiddenDiagnostics, `failure(${failureCode})`);

  // action="none" failure must not start choreography.
  assert.strictEqual(
    choreo.startCalls.length,
    0,
    `failure(${failureCode}): choreography must NOT start on failure`,
  );

  // Shell must stay in entry state (not split).
  assert.strictEqual(
    s.win.CitizenFirstUseShell.getState(),
    "entry",
    `failure(${failureCode}): shell must stay in entry (no split)`,
  );

  // Left canvas must remain hidden/inert.
  assert.strictEqual(
    canvasAriaHidden(s),
    "true",
    `failure(${failureCode}): left clone must remain hidden/inert`,
  );
  assert.strictEqual(
    canvasInert(s),
    true,
    `failure(${failureCode}): left clone must remain inert`,
  );

  console.log(`  [7] failure diagnostics hidden (${failureCode}): OK`);
}

// ── Scenario: untrusted failure answer must never reach the citizen DOM ──
// A failure response (ok:false) that also carries a non-empty `answer` must
// still fail closed to the generic Korean message. The attacker-controlled
// answer text, raw URL, and token canaries must not appear in the rendered
// shell nor in the AI chat bubble.

async function scenarioFailureUntrustedAnswer() {
  const failureCode = "unknown";
  const bridge = makeResolvingBridge({
    ok: false,
    question: "테스트 질문",
    answer:
      "CANARY_FAILURE_ANSWER_MUST_NOT_RENDER https://private.invalid/failure Authorization: Bearer CANARY_FAILURE_TOKEN",
    action: "none",
    confidence: 0.0,
    failure_code: failureCode,
    error: "CANARY_SECRET_MUST_NOT_RENDER",
    upstream_url: "https://private.invalid/forbidden",
    authorization: "Authorization: Bearer CANARY_TOKEN_MUST_NOT_RENDER",
  });
  const choreo = makeChoreo();
  const s = runScenario({
    search: "?mvp=1",
    reducedMotion: true,
    bridge,
    choreo,
  });
  submit(s, "불법 주정차 신고는 어디서 하나요?");
  await flush();

  const visibleText = s.doc.body.textContent;
  const aiText = aiBubbleTexts(s).join("");
  const forbidden = [
    failureCode,
    ...FAILURE_DIAGNOSTIC_CANARIES,
    ...FAILURE_ANSWER_CANARIES,
  ];
  assertFailureHidden(visibleText, aiText, forbidden, "failure(untrusted answer)");

  // action="none" failure must not start choreography.
  assert.strictEqual(
    choreo.startCalls.length,
    0,
    "failure(untrusted answer): choreography must NOT start on failure",
  );

  // Shell must stay in entry state (not split).
  assert.strictEqual(
    s.win.CitizenFirstUseShell.getState(),
    "entry",
    "failure(untrusted answer): shell must stay in entry (no split)",
  );

  // Left canvas must remain hidden/inert.
  assert.strictEqual(
    canvasAriaHidden(s),
    "true",
    "failure(untrusted answer): left clone must remain hidden/inert",
  );
  assert.strictEqual(
    canvasInert(s),
    true,
    "failure(untrusted answer): left clone must remain inert",
  );

  console.log("  [8] failure untrusted answer hidden: OK");
}

// ── Scenario: explicit success but blank answer must fail closed ──
// An ok:true result with a blank/whitespace-only answer must NOT show the
// empty answer; it must fall back to the generic Korean failure message.

async function scenarioSuccessBlankAnswer() {
  const bridge = makeResolvingBridge({
    ok: true,
    question: "테스트 질문",
    answer: "   ",
    action: "illegal_parking",
    confidence: 0.5,
  });
  const choreo = makeChoreo();
  const s = runScenario({
    search: "?mvp=1",
    reducedMotion: true,
    bridge,
    choreo,
  });
  submit(s, "오늘 날씨 어떠세요?");
  await flush();

  const visibleText = s.doc.body.textContent;
  const aiText = aiBubbleTexts(s).join("");
  assertFailureHidden(visibleText, aiText, [], "success(blank answer)");

  // Blank-answer success (action=none) must not start choreography.
  assert.strictEqual(
    choreo.startCalls.length,
    0,
    "success(blank answer): choreography must NOT start",
  );

  // Shell must stay in entry state (not split).
  assert.strictEqual(
    s.win.CitizenFirstUseShell.getState(),
    "entry",
    "success(blank answer): shell must stay in entry (no split)",
  );

  // Left canvas must remain hidden/inert.
  assert.strictEqual(
    canvasAriaHidden(s),
    "true",
    "success(blank answer): left clone must remain hidden/inert",
  );
  assert.strictEqual(
    canvasInert(s),
    true,
    "success(blank answer): left clone must remain inert",
  );

  console.log("  [9] success blank answer fails closed: OK");
}

// ── Scenario A: missing result must fail closed ──
// The bridge resolves with `undefined`. The shell must never render anything
// from a missing result; it must show the generic Korean failure message and
// keep the shell in entry with the canvas inert, and recover the composer.

async function scenarioMissingResult() {
  const bridge = makeResolvingBridge(undefined);
  const choreo = makeChoreo();
  const s = runScenario({
    search: "?mvp=1",
    reducedMotion: true,
    bridge,
    choreo,
  });
  submit(s, "불법 주정차 신고는 어디서 하나요?");
  await flush();

  const visibleText = s.doc.body.textContent;
  const aiText = aiBubbleTexts(s).join("");
  assertFailureHidden(visibleText, aiText, [], "missing result");

  assert.strictEqual(
    choreo.startCalls.length,
    0,
    "missing result: choreography must NOT start",
  );
  assert.strictEqual(
    s.win.CitizenFirstUseShell.getState(),
    "entry",
    "missing result: shell must stay in entry (no split)",
  );
  assert.strictEqual(
    canvasAriaHidden(s),
    "true",
    "missing result: left clone must remain hidden/inert",
  );
  assert.strictEqual(
    canvasInert(s),
    true,
    "missing result: left clone must remain inert",
  );
  assertComposerRecovered(s, "missing result");

  console.log("  [10] missing result fails closed: OK");
}

// ── Scenario B: malformed result must fail closed ──
// A result that is missing `ok` or has a non-boolean `ok`, plus a subverted
// `answer`/`action`/`error`, must not leak any diagnostic or approved-action
// text into the citizen DOM.

async function scenarioMalformedResult() {
  const malformed = [
    {},
    {
      ok: "true",
      answer: "CANARY_MALFORMED_ANSWER_MUST_NOT_RENDER",
      action: "illegal_parking",
      error: "CANARY_MALFORMED_ERROR_MUST_NOT_RENDER",
    },
  ];
  const forbidden = [
    "CANARY_MALFORMED_ANSWER_MUST_NOT_RENDER",
    "CANARY_MALFORMED_ERROR_MUST_NOT_RENDER",
    "illegal_parking",
  ];
  let idx = 0;
  for (const result of malformed) {
    const label = `malformed result [${idx++}]`;
    const bridge = makeResolvingBridge(result);
    const choreo = makeChoreo();
    const s = runScenario({
      search: "?mvp=1",
      reducedMotion: true,
      bridge,
      choreo,
    });
    submit(s, "불법 주정차 신고는 어디서 하나요?");
    await flush();

    const visibleText = s.doc.body.textContent;
    const aiText = aiBubbleTexts(s).join("");
    assertFailureHidden(visibleText, aiText, forbidden, label);

    assert.strictEqual(
      choreo.startCalls.length,
      0,
      `${label}: choreography must NOT start`,
    );
    assert.strictEqual(
      s.win.CitizenFirstUseShell.getState(),
      "entry",
      `${label}: shell must stay in entry (no split)`,
    );
    assert.strictEqual(
      canvasAriaHidden(s),
      "true",
      `${label}: left clone must remain hidden/inert`,
    );
    assert.strictEqual(
      canvasInert(s),
      true,
      `${label}: left clone must remain inert`,
    );
    assertComposerRecovered(s, label);
  }

  console.log("  [11] malformed result fails closed: OK");
}

// ── Scenario C: rejected bridge request must fail closed ──
// The bridge rejects its promise. The shell's catch handler must show the
// generic Korean failure message (not the rejection error) and recover the
// composer without touching the clone.

async function scenarioRejectedBridge() {
  const bridge = makeRejectingBridge(
    new Error("CANARY_REJECTED_BRIDGE_ERROR_MUST_NOT_RENDER"),
  );
  const choreo = makeChoreo();
  const s = runScenario({
    search: "?mvp=1",
    reducedMotion: true,
    bridge,
    choreo,
  });
  submit(s, "불법 주정차 신고는 어디서 하나요?");
  await flush();

  const visibleText = s.doc.body.textContent;
  const aiText = aiBubbleTexts(s).join("");
  assertFailureHidden(
    visibleText,
    aiText,
    ["CANARY_REJECTED_BRIDGE_ERROR_MUST_NOT_RENDER"],
    "rejected bridge",
  );

  assert.strictEqual(
    choreo.startCalls.length,
    0,
    "rejected bridge: choreography must NOT start",
  );
  assert.strictEqual(
    s.win.CitizenFirstUseShell.getState(),
    "entry",
    "rejected bridge: shell must stay in entry (no split)",
  );
  assert.strictEqual(
    canvasAriaHidden(s),
    "true",
    "rejected bridge: left clone must remain hidden/inert",
  );
  assert.strictEqual(
    canvasInert(s),
    true,
    "rejected bridge: left clone must remain inert",
  );
  assertComposerRecovered(s, "rejected bridge");

  console.log("  [12] rejected bridge request fails closed: OK");
}

async function main() {
  console.log("Running MVP shell runtime scenarios (no network, no fetch):");
  await scenarioIllegalParking();
  await scenarioHousingDepartment();
  await scenarioBulkyWaste();
  await scenarioMoveInReport();
  await scenarioSupportedQuestionActionNoneFallback();
  await scenarioNone();
  await scenarioPendingThenReset();
  await scenarioDefaultModeRegression();
  await scenarioFailureDiagnosticHidden("timeout");
  await scenarioFailureDiagnosticHidden("unknown");
  await scenarioFailureUntrustedAnswer();
  await scenarioSuccessBlankAnswer();
  await scenarioMissingResult();
  await scenarioMalformedResult();
  await scenarioRejectedBridge();
  console.log("All MVP shell runtime scenarios passed.");
}

main().catch((err) => {
  console.error("MVP shell runtime verification FAILED:");
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
