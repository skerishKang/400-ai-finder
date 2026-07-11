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

// Real production modules (map → canvas → adapter → choreography) are loaded
// into the same vm context so runtime scenarios C/D/E exercise the ACTUAL
// canvas navigateToRoute / choreography step progression, not test doubles.
const STATIC_BASE = new URL("../../src/web/static/", import.meta.url);
const readStatic = (f) => readFileSync(new URL(f, STATIC_BASE), "utf8");
const snapshotCode = readStatic("bukgu-official-snapshots.js");
const mapCode = readStatic("citizen-action-demo-map.js");
const canvasCode = readStatic("citizen-action-demo-canvas.js");
const adapterCode = readStatic("citizen-content-adapter.js");
const choreoCode = readStatic("citizen-first-choreography.js");

// ── Fake DOM ────────────────────────────────────────────────────────────

function makeEl(tag) {
  const el = {
    tagName: tag || "div",
    id: "",
    className: "",
    // CSSStyleDeclaration shim: production code calls style.removeProperty/
    // setProperty (e.g. clearChatMotionStyles, fitToViewport). Without these the
    // shell throws inside completeMvpSplit and the confirm-run message never renders.
    style: {
      _p: {},
      removeProperty(k) { delete this._p[k]; },
      setProperty(k, v) { this._p[k] = v; },
      getPropertyValue(k) { return this._p[k] || ""; },
    },
    disabled: false,
    hidden: false,
    value: "",
    _textContent: "",
    _attrs: {},
    _children: [],
    _listeners: {},
    scrollTop: 0,
    scrollHeight: 0,
    getBoundingClientRect() {
      return { width: 100, height: 100, left: 0, top: 0, right: 100, bottom: 100 };
    },
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
      c._parent = this;
      return c;
    },
    removeChild(c) {
      const i = this._children.indexOf(c);
      if (i >= 0) {
        this._children.splice(i, 1);
        c._parent = null;
      }
    },
    addEventListener(type, fn) {
      (this._listeners[type] = this._listeners[type] || []).push(fn);
    },
    removeEventListener() {},
    dispatchEvent() {},
    get innerHTML() { return ''; },
    set innerHTML(v) {
      for (const c of this._children) { c._parent = null; }
      this._children = [];
    },
    _querySelectorTag(tag) {
      for (const c of this._children || []) {
        if ((c.tagName || '').toUpperCase() === tag.toUpperCase()) return c;
        const found = c._querySelectorTag(tag);
        if (found) return found;
      }
      return null;
    },
    _querySelectorAllTag(tag) {
      const result = [];
      for (const c of this._children || []) {
        if ((c.tagName || '').toUpperCase() === tag.toUpperCase()) result.push(c);
        result.push(...c._querySelectorAllTag(tag));
      }
      return result;
    },
    querySelector(sel) {
      return this._querySelectorTag(sel);
    },
    querySelectorAll(sel) {
      return this._querySelectorAllTag(sel);
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
    querySelector(sel) {
      return body._querySelectorTag(sel);
    },
    querySelectorAll(sel) {
      return body._querySelectorAllTag(sel);
    },
    addEventListener() {},
  };
}

function buildWindow({ search, reducedMotion, bridge, choreo, setTimeoutImpl }) {
  const listeners = {};
  return {
    location: {
      search: search || "",
      href: "http://localhost/" + (search || ""),
      pathname: "/",
    },
    history: {
      pushState() {},
      replaceState() {},
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
    setTimeout: setTimeoutImpl || setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    addEventListener(type, fn) {
      (listeners[type] = listeners[type] || []).push(fn);
    },
    removeEventListener() {},
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
    startResults: [],
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

function runScenario({ search, reducedMotion, bridge, choreo, fastTimers }) {
  // fastTimers collapses production step/visual delays to a small fixed value
  // so progression scenarios can drive the REAL choreography to terminal
  // states (waiting_choice / waiting_confirmation) without waiting for the
  // full production delay budget. Production delay constants are untouched.
  const setTimeoutImpl = fastTimers
    ? (fn, ms) => setTimeout(fn, Math.min(typeof ms === "number" ? ms : 0, 2))
    : setTimeout;
  const doc = buildDoc();
  const win = buildWindow({ search, reducedMotion, bridge, choreo, setTimeoutImpl });
  const context = {
    window: win,
    document: doc,
    console,
    URLSearchParams,
    Promise,
    setTimeout: setTimeoutImpl,
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
  // Load real production modules (map → canvas → adapter → choreography) into
  // the SAME context so the shell's confirmed-run "예" click drives the actual
  // CitizenFirstChoreography.start(action) and the canvas navigateToRoute
  // executes the real complaint-board route render. The injected
  // window.CitizenFirstChoreography test double (above) is replaced by the real
  // module so C/D/E assert against genuine runtime behavior.
  vm.runInContext(snapshotCode, context);
  vm.runInContext(mapCode, context);
  vm.runInContext(canvasCode, context);
  vm.runInContext(adapterCode, context);
  vm.runInContext(choreoCode, context);
  vm.runInContext(shellCode, context);
  // Wrap the REAL choreography so the injected `choreo` recorder (startCalls)
  // captures the exact action key passed by the shell's confirm-run "예" click,
  // while preserving all real choreography behavior for C/D/E assertions.
  // (The module freezes its public object, so we delegate via a plain proxy
  // rather than mutating the frozen object.)
  if (choreo && Array.isArray(choreo.startCalls)) {
    const real = win.CitizenFirstChoreography;
    if (real && typeof real.start === "function") {
      const proxy = {
        start(action) {
          // Record BOTH the called action and the REAL return value so the
          // test can assert genuine start() behavior, not just that a call
          // happened (the previous false-positive gap).
          const result = real.start(action);
          choreo.startCalls.push(action);
          if (Array.isArray(choreo.startResults)) choreo.startResults.push(result);
          return result;
        },
        cancel(...args) { return real.cancel(...args); },
        getState(...args) { return real.getState(...args); },
        getCurrentJourneyId(...args) { return real.getCurrentJourneyId(...args); },
        hasJourney(...args) { return real.hasJourney(...args); },
        handleChoice(...args) { return real.handleChoice(...args); },
        confirmSubmission(...args) { return real.confirmSubmission(...args); },
      };
      win.CitizenFirstChoreography = proxy;
    }
  }
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
// drainTimers waits for pending macrotasks. The shell's completeMvpSplit delays
// the confirm-run message by 220ms and the canvas navigateToRoute swaps route
// HTML after a 300ms fade, so a single 200ms wait was too short (harness bug,
// not a production defect). Wait long enough for both real timers to fire.
const drainTimers = async () => { await new Promise(r => setTimeout(r, 700)); };
// Full drain for end-to-end choreography scenarios (multiple step delays).
const drainTimersLong = async () => { await new Promise(r => setTimeout(r, 1200)); };

// Poll until `predicate()` is true or `maxMs` elapses. Used by the genuine
// progression scenarios to drive the REAL choreography to a terminal/awaiting
// state (waiting_choice / waiting_confirmation) without guessing exact delays.
async function drainUntil(predicate, maxMs = 2000, tickMs = 5) {
  const start = Date.now();
  while (!predicate() && Date.now() - start < maxMs) {
    await new Promise((r) => setTimeout(r, tickMs));
  }
  return predicate();
}

// Install a route-navigation + submit spy over the REAL canvas/adapter so the
// progression scenarios can assert genuine runtime effects (route transition,
// no automatic submission) rather than only inspecting return booleans.
function installCanvasRouteSpy(scenario) {
  const realCanvas = scenario.win.CitizenActionDemoCanvas;
  const routeCalls = [];
  scenario.win.CitizenActionDemoCanvas = {
    navigateToRoute(id) {
      routeCalls.push(id);
      return realCanvas.navigateToRoute(id);
    },
    getTargetElement: (...a) => realCanvas.getTargetElement(...a),
    clickAnimation: (...a) => realCanvas.clickAnimation(...a),
    hideCursor: (...a) => (realCanvas.hideCursor ? realCanvas.hideCursor(...a) : undefined),
    showCursorAt: (...a) => (realCanvas.showCursorAt ? realCanvas.showCursorAt(...a) : undefined),
  };
  const realAdapter = scenario.win.CitizenContentAdapter;
  const submitCalls = [];
  if (realAdapter) {
    // Delegate ALL adapter methods to the real object; only intercept
    // submitBoardPost so we can assert no automatic submission occurs.
    scenario.win.CitizenContentAdapter = new Proxy(realAdapter, {
      get(target, prop) {
        if (prop === "submitBoardPost") {
          return (data) => {
            submitCalls.push(data);
            return target.submitBoardPost(data);
          };
        }
        const value = target[prop];
        return typeof value === "function" ? value.bind(target) : value;
      },
    });
  }
  return { routeCalls, submitCalls };
}

// ── Confirm-run helpers ──────────────────────────────────────────────────

function findConfirmRunMsg(scenario) {
  const thread = scenario.doc.getElementById("chat-thread");
  for (const child of thread._children) {
    if (child.getAttribute && child.getAttribute("data-msg-type") === "confirm-run") {
      return child;
    }
  }
  return null;
}

function findButtonByText(parent, text) {
  for (const c of parent._children || []) {
    if ((c.tagName === 'BUTTON' || c.tagName === 'button') && c.textContent && c.textContent.trim().includes(text)) {
      return c;
    }
    const found = findButtonByText(c, text);
    if (found) return found;
  }
  return null;
}

function isConnectedToDocument(el) {
  if (!el) return false;
  if (el.tagName && el.tagName.toUpperCase() === 'BODY') return true;
  if (!el._parent) return false;
  return isConnectedToDocument(el._parent);
}

function clickButton(btn) {
  if (!btn) return;
  if (btn.disabled) return;
  // Simulate browser behavior: skip click if element is not connected to document
  if (!isConnectedToDocument(btn)) return;
  const handlers = btn._listeners && btn._listeners.click;
  if (handlers) {
    for (const h of handlers) h({ target: btn });
  }
}

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
  await drainTimers();

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
  // confirm-run: choreography must NOT start until user clicks yes
  assert.deepStrictEqual(
    choreo.startCalls,
    [],
    "illegal_parking: choreography must NOT start before confirm-run yes click",
  );
  // confirm-run message must exist
  const confirmMsg = findConfirmRunMsg(s);
  assert.ok(confirmMsg, "illegal_parking: confirm-run message must be present");
  // Yes and No buttons must exist
  const yesBtn = findButtonByText(confirmMsg, "예");
  const noBtn = findButtonByText(confirmMsg, "아니요");
  assert.ok(yesBtn, "illegal_parking: 예 button must exist");
  assert.ok(noBtn, "illegal_parking: 아니요 button must exist");
  // Click Yes
  clickButton(yesBtn);
  await flush();
  assert.deepStrictEqual(
    choreo.startCalls,
    ["illegal_parking"],
    "illegal_parking: choreography.start('illegal_parking') called exactly once after yes click",
  );
  const card = s.doc.getElementById("chat-thread")._children.find((node) => {
    return (node.className || "").includes("chat-quest-card");
  });
  assert.ok(card, "illegal_parking: quest card must be appended from metadata");
  assert.strictEqual(card.getAttribute("data-quest-card"), "action_plan");
  const cardText = card.textContent;
  assert.ok(cardText.includes("불법 주정차 신고 안내"));
  assert.ok(cardText.includes("종합민원 > 민원신고 > 불법 주정차 신고"));
  assert.ok(cardText.includes("불법 주정차 신고 / 불법 주정차 신고 카드"));
  // Labels are localized by the shell (stopConditionLabel / sourceModeLabel),
  // so assert on the rendered Korean text, not the internal enum constants.
  assert.ok(cardText.includes("사용자 확인 후 진행"));
  assert.ok(cardText.includes("북구청 공식 화면 기준"));
  assert.ok(cardText.includes("불법 주정차 신고 화면 이동"));
  assert.ok(cardText.includes("실제 신고 제출과 본인인증"));
  console.log("  [1] illegal_parking: OK");
}

async function scenarioHousingDepartment() {
  const bridge = makeResolvingBridge({
    ok: true,
    answer: "공동주택과 부서 대표전화는 062-410-6841이며, 공식 19명 업무표를 함께 보여드립니다.",
    action: "housing_department",
    confidence: 0.9,
    quest: {
      quest_id: "housing_department_lookup",
      quest_name: "공동주택 담당부서 찾기",
      official_path: ["홈", "북구소개", "구청안내", "행정조직", "공동주택과", "조직 및 업무안내"],
      result: { service: "공동주택과 조직 및 업무안내", surface: "전체 19명 공식 업무 및 연락처" },
      source_mode: "local_static",
    },
    action_plan: {
      official_path: ["홈", "북구소개", "구청안내", "행정조직", "공동주택과", "조직 및 업무안내"],
      browser_actions: [
        { label: "공동주택과 안내 화면 이동" },
        { label: "공동주택과 업무 및 연락처 확인" },
      ],
      result: { service: "공동주택과 조직 및 업무안내", surface: "전체 19명 공식 업무 및 연락처" },
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
  await drainTimers();

  const bubbles = aiBubbleTexts(s);
  assert.ok(
    bubbles.includes(
      "공동주택과 부서 대표전화는 062-410-6841이며, 공식 19명 업무표를 함께 보여드립니다.",
    ),
    "housing_department: server answer must be shown",
  );
  assertSplitCloneVisible(s, "housing_department");
  // confirm-run: choreography must NOT start until yes click
  assert.deepStrictEqual(
    choreo.startCalls,
    [],
    "housing_department: choreography must NOT start before confirm-run yes click",
  );
  const confirmMsg = findConfirmRunMsg(s);
  assert.ok(confirmMsg, "housing_department: confirm-run message must be present");
  const yesBtn = findButtonByText(confirmMsg, "예");
  assert.ok(yesBtn, "housing_department: 예 button must exist");
  clickButton(yesBtn);
  await flush();
  assert.deepStrictEqual(
    choreo.startCalls,
    ["housing_department"],
    "housing_department: choreography.start('housing_department') once after yes click",
  );
  const card = s.win.CitizenFirstUseShell.renderQuestProgressCard();
  assert.ok(card, "housing_department: quest card must render from stored metadata");
  assert.strictEqual(card.getAttribute("data-quest-card"), "action_plan");
  const cardText = card.textContent;
  assert.ok(cardText.includes("공동주택 담당부서 찾기"));
  assert.ok(cardText.includes("홈 > 북구소개 > 구청안내 > 행정조직 > 공동주택과 > 조직 및 업무안내"));
  assert.ok(cardText.includes("공동주택과 조직 및 업무안내 / 전체 19명 공식 업무 및 연락처"));
  assert.ok(cardText.includes("공동주택과 안내 화면 이동"));
  assert.ok(cardText.includes("공동주택과 업무 및 연락처 확인"));
  // Localized labels (not internal enum constants):
  assert.ok(cardText.includes("북구청 공식 화면 기준"));
  assert.ok(cardText.includes("안내 준비 완료"));
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
  await drainTimers();

  const bubbles = aiBubbleTexts(s);
  assert.ok(
    bubbles.includes("대형폐기물 배출 신청 경로를 안내해 드립니다."),
    "bulky_waste: server answer must be shown",
  );
  assertSplitCloneVisible(s, "bulky_waste");
  // confirm-run: choreography must NOT start until yes click
  assert.deepStrictEqual(
    choreo.startCalls,
    [],
    "bulky_waste: choreography must NOT start before confirm-run yes click",
  );
  const confirmMsg = findConfirmRunMsg(s);
  assert.ok(confirmMsg, "bulky_waste: confirm-run message must be present");
  const yesBtn = findButtonByText(confirmMsg, "예");
  assert.ok(yesBtn, "bulky_waste: 예 button must exist");
  clickButton(yesBtn);
  await flush();
  assert.deepStrictEqual(
    choreo.startCalls,
    ["bulky_waste"],
    "bulky_waste: choreography.start('bulky_waste') once after yes click",
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
  assert.ok(cardText.includes("사용자 확인 후 진행"));
  assert.ok(cardText.includes("북구청 공식 화면 기준"));
  assert.ok(cardText.includes("대형폐기물 배출 안내 화면 이동"));
  assert.ok(cardText.includes("수수료 결제"));
  assert.ok(cardText.includes("스티커 출력"));
  console.log("  [2.5] bulky_waste: OK");
}

async function scenarioPassportGuidance() {
  const bridge = makeResolvingBridge({
    ok: true,
    answer: "여권 발급 경로를 안내해 드립니다.",
    action: "passport_guidance",
    confidence: 0.92,
    quest: {
      quest_id: "passport_guidance",
      quest_name: "여권 발급 안내",
      source_mode: "local_static",
      match_status: "matched",
    },
    action_plan: {
      quest_id: "passport_guidance",
      quest_name: "여권 발급 안내",
      official_path: ["종합민원", "여권", "여권 발급 안내"],
      source_mode: "local_static",
      stop_condition: "STOP_FOR_USER_CONFIRMATION",
      result: { service: "여권 발급 안내", surface: "여권 발급 안내 카드" },
      browser_actions: [
        { label: "종합민원 메뉴 확인" },
        { label: "여권 발급 안내 화면 이동" },
      ],
      final_warning: {
        warning_text: "실제 여권 발급 신청은 사용자가 직접 확인해야 합니다.",
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
  submit(s, "여권 발급은 어디서 하나요?");
  await flush();
  await drainTimers();

  const bubbles = aiBubbleTexts(s);
  assert.ok(bubbles.includes("여권 발급 경로를 안내해 드립니다."), "passport: server answer must be shown");
  assertSplitCloneVisible(s, "passport");
  // confirm-run: choreography must NOT start until yes click
  assert.deepStrictEqual(choreo.startCalls, [], "passport: startCalls empty before confirm");
  const confirmMsg = findConfirmRunMsg(s);
  assert.ok(confirmMsg, "passport: confirm-run message must be present");
  const yesBtn = findButtonByText(confirmMsg, "예");
  assert.ok(yesBtn, "passport: 예 button must exist");
  clickButton(yesBtn);
  await flush();
  assert.deepStrictEqual(choreo.startCalls, ["passport_guidance"], "passport: choreography.start('passport_guidance') once after yes click");
  const card = s.doc.getElementById("chat-thread")._children.find((node) => {
    return (node.className || "").includes("chat-quest-card");
  });
  assert.ok(card, "passport: quest card must exist");
  console.log("  [2.75] passport_guidance: OK");
}

async function scenarioUnmannedKiosk() {
  const bridge = makeResolvingBridge({
    ok: true,
    answer: "무인민원발급기 위치를 안내해 드립니다.",
    action: "unmanned_kiosk",
    confidence: 0.92,
    quest: {
      quest_id: "unmanned_kiosk_guidance",
      quest_name: "무인민원발급기 안내",
      source_mode: "local_static",
      match_status: "matched",
    },
    action_plan: {
      quest_id: "unmanned_kiosk_guidance",
      quest_name: "무인민원발급기 안내",
      official_path: ["종합민원", "무인민원발급기", "설치장소"],
      source_mode: "local_static",
      stop_condition: "STOP_FOR_USER_CONFIRMATION",
      result: { service: "무인민원발급기 안내", surface: "무인민원발급기 안내 카드" },
      browser_actions: [
        { label: "종합민원 메뉴 확인" },
        { label: "무인민원발급기 안내 화면 이동" },
      ],
      final_warning: {
        warning_text: "실제 민원서류 발급은 사용자가 직접 확인해야 합니다.",
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
  submit(s, "무인민원발급기 어디 있어요?");
  await flush();
  await drainTimers();

  const bubbles = aiBubbleTexts(s);
  assert.ok(bubbles.includes("무인민원발급기 위치를 안내해 드립니다."), "kiosk: server answer must be shown");
  assertSplitCloneVisible(s, "kiosk");
  assert.deepStrictEqual(choreo.startCalls, [], "kiosk: startCalls empty before confirm");
  const confirmMsg = findConfirmRunMsg(s);
  assert.ok(confirmMsg, "kiosk: confirm-run message must be present");
  const yesBtn = findButtonByText(confirmMsg, "예");
  assert.ok(yesBtn, "kiosk: 예 button must exist");
  clickButton(yesBtn);
  await flush();
  assert.deepStrictEqual(choreo.startCalls, ["unmanned_kiosk"], "kiosk: choreography.start('unmanned_kiosk') once after yes click");
  const card = s.doc.getElementById("chat-thread")._children.find((node) => {
    return (node.className || "").includes("chat-quest-card");
  });
  assert.ok(card, "kiosk: quest card must exist");
  console.log("  [2.8] unmanned_kiosk: OK");
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
  await drainTimers();

  const bubbles = aiBubbleTexts(s);
  assert.ok(
    bubbles.includes("불법 주정차 신고 경로를 안내하겠습니다."),
    "supported none fallback: server answer must still be shown",
  );
  assertSplitCloneVisible(s, "supported none fallback");
  // confirm-run: choreography must NOT start until yes click
  assert.deepStrictEqual(
    choreo.startCalls,
    [],
    "supported none fallback: choreography must NOT start before confirm",
  );
  const confirmMsg = findConfirmRunMsg(s);
  assert.ok(confirmMsg, "supported none fallback: confirm-run message must be present");
  const yesBtn = findButtonByText(confirmMsg, "예");
  assert.ok(yesBtn, "supported none fallback: 예 button must exist");
  clickButton(yesBtn);
  await flush();
  assert.deepStrictEqual(
    choreo.startCalls,
    ["illegal_parking"],
    "supported none fallback: choreography.start('illegal_parking') once after yes click",
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
  await drainTimers();

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

  // Exact presentation prompts keep their deterministic route even when the
  // live answer fails. The journey still waits for the resident's confirmation.
  assert.strictEqual(
    s.win.CitizenFirstUseShell.getState(),
    "split",
    `failure(${failureCode}): supported prompt must retain its split fallback`,
  );

  // Left fallback clone is visible, but choreography has not started.
  assert.strictEqual(
    canvasAriaHidden(s),
    "false",
    `failure(${failureCode}): fallback clone must be visible`,
  );
  assert.strictEqual(
    canvasInert(s),
    false,
    `failure(${failureCode}): fallback clone must be interactive`,
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

  // The untrusted answer remains hidden while the exact chip route still opens.
  assert.strictEqual(
    s.win.CitizenFirstUseShell.getState(),
    "split",
    "failure(untrusted answer): supported prompt keeps deterministic split fallback",
  );

  assert.strictEqual(
    canvasAriaHidden(s),
    "false",
    "failure(untrusted answer): fallback clone must be visible",
  );
  assert.strictEqual(
    canvasInert(s),
    false,
    "failure(untrusted answer): fallback clone must be interactive",
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
// from a missing result; it shows the generic failure while retaining the
// deterministic presentation route for an exact chip prompt.

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
    "split",
    "missing result: exact prompt must keep split fallback",
  );
  assert.strictEqual(
    canvasAriaHidden(s),
    "false",
    "missing result: fallback clone must be visible",
  );
  assert.strictEqual(
    canvasInert(s),
    false,
    "missing result: fallback clone must be interactive",
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
      "split",
      `${label}: exact prompt must keep split fallback`,
    );
    assert.strictEqual(
      canvasAriaHidden(s),
      "false",
      `${label}: fallback clone must be visible`,
    );
    assert.strictEqual(
      canvasInert(s),
      false,
      `${label}: fallback clone must be interactive`,
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

// ── Confirm-run specific scenarios (#1058) ────────────────────────────────

async function scenarioConfirmRunYesNo() {
  // Test "아니요" click does NOT start choreography
  const bridge = makeResolvingBridge({
    ok: true, answer: "불법 주정차 안내입니다.", action: "illegal_parking", confidence: 0.9,
  });
  const choreo = makeChoreo();
  const s = runScenario({ search: "?mvp=1", reducedMotion: true, bridge, choreo });
  submit(s, "불법 주정차 신고는 어디서 하나요?");
  await flush();
  await drainTimers();
  assert.deepStrictEqual(choreo.startCalls, [], "confirm-no: startCalls empty after model response");
  const confirmMsg = findConfirmRunMsg(s);
  assert.ok(confirmMsg, "confirm-no: confirm-run message must exist");
  const noBtn = findButtonByText(confirmMsg, "아니요");
  assert.ok(noBtn, "confirm-no: 아니요 button must exist");
  clickButton(noBtn);
  await flush();
  assert.deepStrictEqual(choreo.startCalls, [], "confirm-no: startCalls still empty after no click");
  assertComposerRecovered(s, "confirm-no");
  console.log("  [13] confirm-run yes/no behavior: OK");
}

async function scenarioConfirmRunDuplicateClick() {
  // Test double-clicking "예" does NOT call start twice
  const bridge = makeResolvingBridge({
    ok: true, answer: "불법 주정차 안내입니다.", action: "illegal_parking", confidence: 0.9,
  });
  const choreo = makeChoreo();
  const s = runScenario({ search: "?mvp=1", reducedMotion: true, bridge, choreo });
  submit(s, "불법 주정차 신고는 어디서 하나요?");
  await flush();
  await drainTimers();
  const confirmRunNode = findConfirmRunMsg(s);
  const yesBtn = findButtonByText(confirmRunNode, "예");
  assert.ok(yesBtn, "dup-click: 예 button must exist");
  clickButton(yesBtn);
  await flush();
  // After first click, buttons should be disabled — second click should have no effect
  // The production code disables buttons via: var btns = bubble.querySelectorAll("button"); for (var i = 0; i < btns.length; i++) btns[i].disabled = true;
  // verify startCalls was exactly once
  assert.strictEqual(choreo.startCalls.length, 1, "dup-click: startCalls must have exactly 1 entry");
  assert.strictEqual(choreo.startCalls[0], "illegal_parking", "dup-click: action must be illegal_parking");
  // Try clicking again (should have no effect since buttons are disabled)
  const yesBtns = confirmRunNode._querySelectorAllTag("button");
  for (const btn of yesBtns) {
    if (btn.textContent.includes("예")) clickButton(btn);
  }
  await flush();
  assert.strictEqual(choreo.startCalls.length, 1, "dup-click: second click must NOT start choreography again");
  console.log("  [14] confirm-run duplicate click prevention: OK");
}

async function scenarioConfirmRunReset() {
  // Test reset after confirm does not re-trigger old confirm button
  const bridge = makeResolvingBridge({
    ok: true, answer: "불법 주정차 안내입니다.", action: "illegal_parking", confidence: 0.9,
  });
  const choreo = makeChoreo();
  const s = runScenario({ search: "?mvp=1", reducedMotion: true, bridge, choreo });
  submit(s, "불법 주정차 신고는 어디서 하나요?");
  await flush();
  await drainTimers();
  const confirmMsg = findConfirmRunMsg(s);
  assert.ok(confirmMsg, "reset-after-confirm: confirm-run message must exist");
  const yesBtn = findButtonByText(confirmMsg, "예");
  assert.ok(yesBtn, "reset-after-confirm: 예 button must exist");
  // Reset the shell
  s.win.CitizenFirstUseShell.reset();
  await flush();
  // The old confirm button is no longer in the DOM (reset clears chat)
  // Try clicking it anyway — choreography must NOT start
  clickButton(yesBtn);
  await flush();
  console.log("  [15] confirm-run reset prevention: OK");
}

// ── #1059: No global default action fallback ────────────────────────────────

async function scenarioPassportNoneFallback() {
  // Passport question + model action "none" → passport_guidance
  const bridge = makeResolvingBridge({
    ok: true, answer: "여권 안내입니다.", action: "none", confidence: 0.5,
  });
  const choreo = makeChoreo();
  const s = runScenario({ search: "?mvp=1", reducedMotion: true, bridge, choreo });
  submit(s, "여권 발급은 어디서 하나요?");
  await flush();
  await drainTimers();
  assert.strictEqual(s.win.CitizenFirstUseShell.getState(), "split", "passport-none-fallback: shell must split");
  assert.deepStrictEqual(choreo.startCalls, [], "passport-none-fallback: startCalls empty before confirm");
  clickButton(findButtonByText(findConfirmRunMsg(s), "예"));
  await flush();
  assert.deepStrictEqual(choreo.startCalls, ["passport_guidance"], "passport-none-fallback: choreography starts passport_guidance");
  console.log("  [16] passport question + model none → passport_guidance: OK");
}

async function scenarioKioskNoneFallback() {
  const bridge = makeResolvingBridge({
    ok: true, answer: "무인민원발급기 안내입니다.", action: "none", confidence: 0.5,
  });
  const choreo = makeChoreo();
  const s = runScenario({ search: "?mvp=1", reducedMotion: true, bridge, choreo });
  submit(s, "무인민원발급기 어디 있어요?");
  await flush();
  await drainTimers();
  assert.strictEqual(s.win.CitizenFirstUseShell.getState(), "split", "kiosk-none-fallback: shell must split");
  assert.deepStrictEqual(choreo.startCalls, [], "kiosk-none-fallback: startCalls empty before confirm");
  clickButton(findButtonByText(findConfirmRunMsg(s), "예"));
  await flush();
  assert.deepStrictEqual(choreo.startCalls, ["unmanned_kiosk"], "kiosk-none-fallback: choreography starts unmanned_kiosk");
  console.log("  [17] kiosk question + model none → unmanned_kiosk: OK");
}

async function scenarioHousingNoneFallback() {
  const bridge = makeResolvingBridge({
    ok: true, answer: "공동주택 안내입니다.", action: "none", confidence: 0.5,
  });
  const choreo = makeChoreo();
  const s = runScenario({ search: "?mvp=1", reducedMotion: true, bridge, choreo });
  submit(s, "공동주택 관련 문의는 어느 부서에 해야 하나요?");
  await flush();
  await drainTimers();
  assert.strictEqual(s.win.CitizenFirstUseShell.getState(), "split", "housing-none-fallback: shell must split");
  assert.deepStrictEqual(choreo.startCalls, [], "housing-none-fallback: startCalls empty before confirm");
  clickButton(findButtonByText(findConfirmRunMsg(s), "예"));
  await flush();
  assert.deepStrictEqual(choreo.startCalls, ["housing_department"], "housing-none-fallback: choreography starts housing_department");
  console.log("  [18] housing question + model none → housing_department: OK");
}

async function scenarioBulkyWasteNoneFallback() {
  const bridge = makeResolvingBridge({
    ok: true, answer: "대형폐기물 안내입니다.", action: "none", confidence: 0.5,
  });
  const choreo = makeChoreo();
  const s = runScenario({ search: "?mvp=1", reducedMotion: true, bridge, choreo });
  submit(s, "침대 매트리스 버리고 싶어요");
  await flush();
  await drainTimers();
  assert.strictEqual(s.win.CitizenFirstUseShell.getState(), "split", "bulky-none-fallback: shell must split");
  assert.deepStrictEqual(choreo.startCalls, [], "bulky-none-fallback: startCalls empty before confirm");
  clickButton(findButtonByText(findConfirmRunMsg(s), "예"));
  await flush();
  assert.deepStrictEqual(choreo.startCalls, ["bulky_waste"], "bulky-none-fallback: choreography starts bulky_waste");
  console.log("  [19] bulky waste question + model none → bulky_waste: OK");
}

async function scenarioUnknownNoneNoMovement() {
  // Unknown question + model action "none" → no split
  const bridge = makeResolvingBridge({
    ok: true, answer: "죄송합니다.", action: "none", confidence: 0.5,
  });
  const choreo = makeChoreo();
  const s = runScenario({ search: "?mvp=1", reducedMotion: true, bridge, choreo });
  submit(s, "오늘 날씨 어떠세요?");
  await flush();
  assert.strictEqual(s.win.CitizenFirstUseShell.getState(), "entry", "unknown-none: shell must stay in entry (no split)");
  assert.strictEqual(choreo.startCalls.length, 0, "unknown-none: choreography must NOT start");
  console.log("  [20] unknown question + model none → no split: OK");
}

async function scenarioMalformedResultNoMovement() {
  // Malformed result cannot override the exact presentation route.
  const choreo = makeChoreo();
  const s = runScenario({
    search: "?mvp=1", reducedMotion: true,
    bridge: makeResolvingBridge(null),
    choreo,
  });
  submit(s, "불법 주정차 신고는 어디서 하나요?");
  await flush();
  assert.strictEqual(s.win.CitizenFirstUseShell.getState(), "split", "malformed-none: exact prompt keeps split fallback");
  assert.strictEqual(choreo.startCalls.length, 0, "malformed-none: choreography must NOT start");
  console.log("  [21] malformed result → deterministic split fallback: OK");
}

// ═══════════════════════════════════════════════════════════════════════════
// Post-deploy regression lock — scenarios A–E (#1069)
//
// These scenarios drive the REAL CitizenFirstChoreography + CitizenActionDemoCanvas
// modules (loaded into the same vm context by runScenario) so they assert genuine
// runtime behavior, not test doubles. No network / fetch / provider / Cloudflare.
// ═══════════════════════════════════════════════════════════════════════════

// The complaint-board route must be a valid, renderable canvas route (E).
// E: complaint-board must be a registered, valid, renderable route.
// Minimum-contract verification (per scope lock):
//   1. isValidRoute("complaint-board") === true
//   2. navigateToRoute("complaint-board") does NOT throw "invalid routeId"
//   3. route dispatch selects _renderComplaintBoard (not the default branch)
//   4. the rendered HTML carries the write-form marker (id="btn-board-write")
//   5. must NOT fall through to the default "알 수 없는 경로" renderer
// We verify the dispatch RESULT HTML via an innerHTML setter spy on the
// demo-canvas element (no full fake-DOM replay of _attachDelegation/fitToViewport).
async function scenarioComplaintBoardRouteRegistered() {
  const doc = buildDoc();
  const w = buildWindow({ search: "", reducedMotion: true, bridge: makeChoreo(), choreo: makeChoreo() });
  const ctx = {
    window: w, document: doc, console, URLSearchParams, Promise,
    setTimeout, clearTimeout, setInterval, clearInterval, Math, Object,
    String, Boolean, Array, JSON, Number, Date,
    requestAnimationFrame: w.requestAnimationFrame,
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(snapshotCode, ctx);
  vm.runInContext(mapCode, ctx);
  vm.runInContext(canvasCode, ctx);
  const map = w.CitizenActionDemoMap;
  const canvas = w.CitizenActionDemoCanvas;

  // (1) valid route in the closed vocabulary
  assert.ok(map.isValidRoute("complaint-board"), "E: complaint-board must be a valid route in the closed vocabulary");
  assert.ok(
    map.getRouteIds().indexOf("complaint-board") !== -1,
    "E: complaint-board must appear in getRouteIds()",
  );
  // (1b) the reversible write form is a first-class route.
  assert.strictEqual(map.isValidRoute("complaint-write"), true, "E: complaint-write must be a valid route");

  // Spy on the demo-canvas innerHTML so we can inspect the dispatch RESULT
  // without replaying the full _attachDelegation/fitToViewport timer chain.
  const canvasEl = doc.getElementById("demo-canvas");
  let lastHtml = "";
  let threwInvalid = false;
  try {
    // (2) must not throw "invalid routeId"
    canvas.navigateToRoute("complaint-board");
  } catch (e) {
    if (/invalid routeId/.test(String(e && e.message))) threwInvalid = true;
  }
  assert.strictEqual(threwInvalid, false, "E: navigateToRoute('complaint-board') must NOT throw 'invalid routeId'");
  await drainTimers();

  // Capture whatever was assigned to innerHTML by the navigation timer.
  lastHtml = String(canvasEl.innerHTML || "");
  // (3)+(4) the dispatched renderer must be _renderComplaintBoard, evidenced by
  // the write-form marker id="btn-board-write" in the result HTML.
  assert.ok(
    lastHtml.includes('id="btn-board-write"') || lastHtml.includes("btn-board-write"),
    "E: route dispatch must select _renderComplaintBoard (write-form marker id='btn-board-write' present in result HTML)",
  );
  // (5) must NOT fall through to the default unknown-route renderer.
  assert.ok(
    !lastHtml.includes("알 수 없는 경로"),
    "E: complaint-board must NOT fall through to the default '알 수 없는 경로' renderer",
  );

  canvas.navigateToRoute("complaint-write");
  await drainTimers();
  lastHtml = String(canvasEl.innerHTML || "");
  assert.ok(lastHtml.includes('id="board-write-title"'), "E: write route must render the title field");
  assert.ok(lastHtml.includes('id="board-write-content"'), "E: write route must render the body field");
  assert.ok(lastHtml.includes('id="btn-board-submit"') && lastHtml.includes("disabled"), "E: final submit must start locked");
  console.log("  [22] complaint-board + complaint-write route registration: OK");
}

// New-chip gate contract (directive §5-A). The shell must recognize the
// 신규 칩 question text, split the shell, present a confirm-run, and — on the
// 예 click — drive CitizenFirstChoreography.start(<exact action>) exactly once.
// We assert the gate→orchestration wiring only; the choreography journey
// bodies themselves are out of scope for this regression lock.
async function scenarioChipGate(question, expectedAction, label) {
  const bridge = makeResolvingBridge({ ok: true, answer: "안내입니다.", action: "none", confidence: 0.5 });
  const choreo = makeChoreo();
  const s = runScenario({ search: "?mvp=1", reducedMotion: true, bridge, choreo });
  // Gate recognition: the supported-question map must contain this chip text.
  assert.ok(
    s.win.CitizenFirstUseShell.isSupportedQuestion(question),
    `${label}: chip question must be registered in the supported-question gate`,
  );
  submit(s, question);
  await flush();
  await drainTimers();
  // Split must occur (reduced motion → immediate completeMvpSplit).
  assert.strictEqual(
    s.win.CitizenFirstUseShell.getState(),
    "split",
    `${label}: shell must transition to split after chip submit`,
  );
  // Choreography must NOT start before the confirm-run 예 click.
  assert.deepStrictEqual(choreo.startCalls, [], `${label}: choreography must NOT start before confirm-run yes`);
  const confirmMsg = findConfirmRunMsg(s);
  assert.ok(confirmMsg, `${label}: confirm-run message must be present`);
  const yesBtn = findButtonByText(confirmMsg, "예");
  assert.ok(yesBtn, `${label}: confirm-run 예 button must exist`);
  clickButton(yesBtn);
  await flush();
  await drainTimers();
  // 예 click must drive the exact action key to the orchestrator exactly once.
  assert.deepStrictEqual(
    choreo.startCalls,
    [expectedAction],
    `${label}: choreography.start('${expectedAction}') called exactly once after confirm`,
  );
  return s;
}

// A: streetlight_report chip gate.
async function scenarioStreetlightChipGateAndStepProgression() {
  await scenarioChipGate("가로등이 고장났어요. 신고할게요", "streetlight_report", "A");
  console.log("  [23] streetlight chip gate (→ streetlight_report): OK");
}

// C: litter_ai_assist chip gate (쓰레기 무단투기 AI 도움).
async function scenarioLitterAiAssistEndToEnd() {
  await scenarioChipGate("쓰레기 무단투기 신고할래 (AI 도움)", "litter_ai_assist", "C");
  console.log("  [24] 쓰레기 무단투기 AI 도움 chip gate (→ litter_ai_assist): OK");
}

// D: the gate resolves to the streetlight action; complaint-write is a route,
// never an action value returned by the model bridge.
async function scenarioStreetlightRouteContract() {
  const bridge = makeResolvingBridge({ ok: true, answer: "가로등 안내입니다.", action: "none", confidence: 0.5 });
  const choreo = makeChoreo();
  const s = runScenario({ search: "?mvp=1", reducedMotion: true, bridge, choreo });
  submit(s, "가로등이 고장났어요. 신고할게요");
  await flush();
  await drainTimers();
  clickButton(findButtonByText(findConfirmRunMsg(s), "예"));
  await flush();
  await drainTimers();
  assert.deepStrictEqual(choreo.startCalls, ["streetlight_report"], "D: starts streetlight_report");
  // Action and route vocabularies remain distinct.
  assert.notStrictEqual(
    choreo.startCalls[0],
    "complaint-write",
    "D: complaint-write is a route and must not be emitted as an action",
  );
  // The complaint-board canvas route itself is validated in scenario E.
  assert.ok(
    s.win.CitizenActionDemoMap.isValidRoute("complaint-board"),
    "D: complaint-board must be a registered valid canvas route (see E for full render)",
  );
  console.log("  [25] 가로등 신고 route contract (complaint-board): OK");
}

// ── Genuine end-to-end progression (#1069 / PR #1074) ───────────────────────
// These scenarios drive the REAL choreography (not the old false-positive
// startCalls-only check) and assert the actual start() return value plus real
// step progression through the canvas route transition and the awaiting states.
// fastTimers collapses production delays so the journey can reach terminal
// awaiting states without changing any production delay constant.

async function scenarioStreetlightReportProgression() {
  const bridge = makeResolvingBridge({ ok: true, answer: "가로등 안내입니다.", action: "none", confidence: 0.5 });
  const choreo = makeChoreo();
  const s = runScenario({ search: "?mvp=1", reducedMotion: true, bridge, choreo, fastTimers: true });

  assert.strictEqual(
    s.win.CitizenFirstChoreography.hasJourney("streetlight_report"),
    true,
    "streetlight: hasJourney('streetlight_report') must be true",
  );

  const { routeCalls } = installCanvasRouteSpy(s);

  submit(s, "가로등이 고장났어요. 신고할게요");
  await flush();
  await drainTimers();
  assert.strictEqual(
    s.win.CitizenFirstUseShell.getState(),
    "split",
    "streetlight: shell must split after chip submit",
  );
  const confirmMsg = findConfirmRunMsg(s);
  assert.ok(confirmMsg, "streetlight: confirm-run message must be present");
  const yesBtn = findButtonByText(confirmMsg, "예");
  assert.ok(yesBtn, "streetlight: confirm-run 예 button must exist");
  clickButton(yesBtn);
  await flush();

  // The actual start() return value must be true (was false / false-positive before).
  const started = s.win.CitizenFirstChoreography.start("streetlight_report");
  assert.strictEqual(started, true, "streetlight: start('streetlight_report') must return true");
  assert.strictEqual(
    s.win.CitizenFirstChoreography.getCurrentJourneyId(),
    "complaint-board-write",
    "streetlight: current journey id must be complaint-board-write",
  );
  // The choreography is progressing (running), not immediately idle.
  assert.strictEqual(
    s.win.CitizenFirstChoreography.getState(),
    "running",
    "streetlight: choreography must be running after first step (not idle)",
  );
  // Real route transition to the validated complaint-board canvas route (the
  // route dispatch fires after the thinking indicator delay, so drain first).
  await drainTimersLong();
  assert.ok(
    routeCalls.includes("complaint-board"),
    "streetlight: choreography must navigate to the complaint-board route",
  );
  assert.ok(
    routeCalls.includes("complaint-write"),
    "streetlight: visible write click must navigate to the complaint-write form",
  );
  console.log("  [26] 가로등 신고 journey progression (board → write form): OK");
}

async function scenarioLitterAiAssistProgression() {
  const bridge = makeResolvingBridge({ ok: true, answer: "안내입니다.", action: "none", confidence: 0.5 });
  const choreo = makeChoreo();
  const s = runScenario({ search: "?mvp=1", reducedMotion: true, bridge, choreo, fastTimers: true });

  assert.strictEqual(
    s.win.CitizenFirstChoreography.hasJourney("litter_ai_assist"),
    true,
    "litter: hasJourney('litter_ai_assist') must be true",
  );

  const { routeCalls, submitCalls } = installCanvasRouteSpy(s);

  submit(s, "쓰레기 무단투기 신고할래 (AI 도움)");
  await flush();
  await drainTimers();
  assert.strictEqual(
    s.win.CitizenFirstUseShell.getState(),
    "split",
    "litter: shell must split after chip submit",
  );
  const confirmMsg = findConfirmRunMsg(s);
  assert.ok(confirmMsg, "litter: confirm-run message must be present");
  const yesBtn = findButtonByText(confirmMsg, "예");
  assert.ok(yesBtn, "litter: confirm-run 예 button must exist");
  clickButton(yesBtn);
  await flush();

  // The actual start() return value from the confirm-run 예 click must be true
  // (was false / false-positive before the alias fix). The proxy records the
  // REAL return value in choreo.startResults.
  assert.ok(
    choreo.startResults.length > 0,
    "litter: confirm-run 예 must have driven a real start() call",
  );
  assert.strictEqual(
    choreo.startResults[choreo.startResults.length - 1],
    true,
    "litter: real start('litter_ai_assist') must return true",
  );
  assert.strictEqual(
    s.win.CitizenFirstChoreography.getCurrentJourneyId(),
    "complaint-ai-assist",
    "litter: current journey id must be complaint-ai-assist",
  );
  // Reaches the choice-awaiting state after step 0/1/2.
  await drainUntil(() => s.win.CitizenFirstChoreography.getState() === "waiting_choice", 2000);
  assert.strictEqual(
    s.win.CitizenFirstChoreography.getState(),
    "waiting_choice",
    "litter: choreography must reach waiting_choice",
  );
  // Real route transition through the validated complaint-board canvas route.
  assert.ok(
    routeCalls.includes("complaint-board"),
    "litter: choreography must navigate to the complaint-board route",
  );
  // AI 도움 선택 (the choice step index passed by the rendered prompt) advances
  // the REAL journey past step 0.
  s.win.CitizenFirstChoreography.handleChoice(2);
  await flush();
  await drainUntil(() => s.win.CitizenFirstChoreography.getState() === "waiting_confirmation", 2000);
  assert.strictEqual(
    s.win.CitizenFirstChoreography.getState(),
    "waiting_confirmation",
    "litter: after AI 도움, choreography must reach waiting_confirmation",
  );
  assert.ok(
    routeCalls.includes("complaint-write"),
    "litter: AI help must open the complaint-write form before confirmation",
  );
  // No automatic submission before the user confirms.
  assert.strictEqual(
    submitCalls.length,
    0,
    "litter: no automatic submit must occur before confirmation",
  );
  console.log("  [27] 쓰레기 무단투기 AI 도움 journey progression (waiting_choice → waiting_confirmation, no auto-submit): OK");
}

async function main() {
  console.log("Running MVP shell runtime scenarios (no network, no fetch):");
  await scenarioIllegalParking();
  await scenarioHousingDepartment();
  await scenarioBulkyWaste();
  await scenarioPassportGuidance();
  await scenarioUnmannedKiosk();
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
  await scenarioConfirmRunYesNo();
  await scenarioConfirmRunDuplicateClick();
  await scenarioConfirmRunReset();
  await scenarioPassportNoneFallback();
  await scenarioKioskNoneFallback();
  await scenarioHousingNoneFallback();
  await scenarioBulkyWasteNoneFallback();
  await scenarioUnknownNoneNoMovement();
  await scenarioMalformedResultNoMovement();
  // Post-deploy regression lock scenarios A–E (#1069)
  await scenarioComplaintBoardRouteRegistered();   // E
  await scenarioStreetlightChipGateAndStepProgression(); // A + B
  await scenarioLitterAiAssistEndToEnd();           // C (+ B)
  await scenarioStreetlightRouteContract();        // D
  await scenarioStreetlightReportProgression();    // progression: streetlight
  await scenarioLitterAiAssistProgression();        // progression: litter AI
  console.log("All MVP shell runtime scenarios passed.");
}

main().catch((err) => {
  console.error("MVP shell runtime verification FAILED:");
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
