/**
 * Architecture regression proof for #1365/#1366: ONE GOLDEN ENGINE for the resident
 * confirmation gate and informational resident controller.
 *
 * Purpose: prove that a future developer cannot silently reintroduce
 *   - a Seo-gu-local canonical confirm-run state machine,
 *   - a Seo-gu-local handoff state machine (_runExternalOfficialHandoff),
 *   - a Seo-gu-local top-level progress owner (_answerQuestion),
 *   - a duplicated confirmation owner, or
 *   - site-local RESULT/STOP progression.
 *
 * Browserless node:vm + fs proof (no browser, no network), matching the
 * tests/functions/* convention so routine CI can run it directly:
 *
 *   node --test tests/functions/test_golden_confirm_gate_architecture.mjs
 *
 * Not a whole-file snapshot — asserts the intended shared ownership seam and the
 * canonical lifecycle behavior.
 */

import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const STATIC_DIR = path.dirname(fileURLToPath(new URL('../../src/web/static/municipal-resident-confirm-gate.js', import.meta.url)));

const GATE_SOURCE = fs.readFileSync(path.join(STATIC_DIR, 'municipal-resident-confirm-gate.js'), 'utf8');
const CONTROLLER_SOURCE = fs.readFileSync(path.join(STATIC_DIR, 'municipal-resident-informational-controller.js'), 'utf8');
const SEOGU_SHELL_SOURCE = fs.readFileSync(path.join(STATIC_DIR, 'seogu-citizen-action-shell.js'), 'utf8');
const BUKGU_SHELL_SOURCE = fs.readFileSync(path.join(STATIC_DIR, 'citizen-first-use-shell.js'), 'utf8');
const SEOGU_HTML = fs.readFileSync(path.join(STATIC_DIR, 'seogu-citizen-action-demo.html'), 'utf8');
const BUKGU_HTML = fs.readFileSync(path.join(STATIC_DIR, 'citizen-action-demo.html'), 'utf8');

function has(haystack, needle) { return haystack.includes(needle); }

// ── DOM shim sufficient for the confirm gate & controller (no jsdom needed) ──
function makeElement(tag) {
  let textContent = '';
  const children = [];
  const attrs = {};
  const listeners = {};
  const style = {};
  const node = {
    _tag: tag,
    className: '',
    style,
    get textContent() { return textContent; },
    set textContent(v) { textContent = String(v == null ? '' : v); },
    setAttribute(k, v) { attrs[k] = String(v); },
    removeAttribute(k) { delete attrs[k]; },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(attrs, k) ? attrs[k] : null; },
    appendChild(c) { children.push(c); return c; },
    addEventListener(type, fn) {
      (listeners[type] = listeners[type] || []).push(fn);
    },
    set disabled(v) { attrs.disabled = v ? 'true' : ''; },
    get disabled() { return attrs.disabled === 'true'; },
    focus() {},
    _children: children,
    _descendants(filter) {
      const out = [];
      const stack = [...children];
      while (stack.length) {
        const n = stack.pop();
        out.push(n);
        if (Array.isArray(n._children)) stack.push(...n._children);
      }
      return out.filter(filter);
    },
    querySelectorAll(sel) {
      if (sel === 'button') return node._descendants((c) => c._tag === 'button');
      return [];
    },
    _click() {
      const ev = { target: node };
      (listeners.click || []).forEach((fn) => fn(ev));
    },
  };
  return node;
}

function createTestSandbox() {
  const win = {
    addEventListener() {},
    matchMedia() { return { matches: false }; },
  };
  const doc = {
    createElement: makeElement,
    body: makeElement('body'),
  };
  const sandbox = {
    window: win,
    document: doc,
    matchMedia: win.matchMedia,
    setTimeout: (fn, ms) => setTimeout(fn, ms != null ? Math.min(ms, 1) : 0),
    clearTimeout: (id) => clearTimeout(id),
    Date,
    Promise,
    console,
    Object,
    Array,
    String,
    Number,
    Boolean,
    Set,
    Symbol,
  };
  vm.createContext(sandbox);
  vm.runInContext(GATE_SOURCE, sandbox, { filename: 'municipal-resident-confirm-gate.js' });
  vm.runInContext(CONTROLLER_SOURCE, sandbox, { filename: 'municipal-resident-informational-controller.js' });
  return sandbox;
}

function loadGate(adapterOverrides) {
  const sandbox = createTestSandbox();
  const thread = {
    _children: [],
    appendChild(c) { this._children.push(c); },
    scrollTop: 0,
    scrollHeight: 0,
  };
  const states = [];
  let yesCalls = 0;
  let noCalls = 0;
  let surfacePrepared = 0;

  const api = sandbox.window.MunicipalResidentConfirmGate;
  const overrides = adapterOverrides || {};
  const gate = api.createConfirmGate(Object.assign({
    getThread: () => thread,
    getInput: () => null,
    displayName: (q) => (q === 'chip/housing' ? '공동주택 부서 문의' : q),
    setJourneyState: (s) => states.push(s),
    isMobileSurfaceMode: () => false,
    scrollToLatest: (node) => { thread.appendChild(node); },
    onYesSurfacePrepare: () => { surfacePrepared += 1; },
    onYes: () => { yesCalls += 1; },
    onNo: () => { noCalls += 1; },
  }, overrides));

  return { gate, thread, states, yesCalls: () => yesCalls, noCalls: () => noCalls,
    surfacePrepared: () => surfacePrepared, api };
}

function loadController(adapterOverrides) {
  const sandbox = createTestSandbox();
  const thread = {
    _children: [],
    appendChild(c) { this._children.push(c); },
    scrollTop: 0,
    scrollHeight: 0,
  };
  const states = [];
  const renderedEvidence = [];
  const renderedDestinations = [];
  const renderedBlocked = [];
  const renderedGrounded = [];
  const renderedFailures = [];
  const inputNode = makeElement('input');
  const sendNode = makeElement('button');

  const api = sandbox.window.MunicipalResidentInformationalController;
  const overrides = adapterOverrides || {};

  const controller = api.createInformationalController(Object.assign({
    getThread: () => thread,
    getInput: () => inputNode,
    getSend: () => sendNode,
    displayName: (q) => (q === 'chip/housing' ? '공동주택 부서 문의' : q),
    setJourneyState: (s) => {
      states.push(s);
      sandbox.document.body.setAttribute('data-journey-state', s);
    },
    isMobileSurfaceMode: () => false,
    scrollToLatest: (node) => { thread.appendChild(node); },
    renderHandoffEvidence: (j, h, ev, missing) => {
      renderedEvidence.push({ journey: j, handoff: h, evidence: ev, missing });
    },
    renderHandoffDestination: (j, h) => {
      renderedDestinations.push({ journey: j, handoff: h });
    },
    renderHandoffBlocked: (j, h) => {
      renderedBlocked.push({ journey: j, handoff: h });
    },
    renderGroundedResult: (res, j) => {
      renderedGrounded.push({ result: res, journey: j });
    },
    renderGroundedFailure: (res, j) => {
      renderedFailures.push({ result: res, journey: j });
    },
  }, overrides));

  return {
    controller,
    thread,
    states,
    inputNode,
    sendNode,
    renderedEvidence,
    renderedDestinations,
    renderedBlocked,
    renderedGrounded,
    renderedFailures,
    sandbox,
  };
}

function lastConfirmBubble(thread) {
  return thread._children.filter((n) => n.className && n.className.includes('chat-msg--confirm-run'))[0];
}

// ── Static: single shared canonical owners ─────────────────────────────────
test('shared gate module exists and exposes createConfirmGate', () => {
  assert.ok(has(GATE_SOURCE, 'createConfirmGate'), 'createConfirmGate missing');
  assert.ok(has(GATE_SOURCE, 'MunicipalResidentConfirmGate'), 'export missing');
});

test('shared gate owns the canonical YES/NO decision seam', () => {
  assert.ok(has(GATE_SOURCE, 'data-confirm-action'), 'data-confirm-action seam not owned by gate');
  assert.ok(has(GATE_SOURCE, '"data-confirm-action", "yes"'), 'YES control not owned by gate');
  assert.ok(has(GATE_SOURCE, '"data-confirm-action", "no"'), 'NO control not owned by gate');
});

test('shared gate owns the stale-confirm generation guard', () => {
  assert.ok(has(GATE_SOURCE, 'invalidate'), 'invalidate() not exposed');
  assert.ok(has(GATE_SOURCE, 'generation'), 'generation guard not owned by gate');
});

test('one shared informational controller exists and composes the confirm gate', () => {
  assert.ok(has(CONTROLLER_SOURCE, 'createInformationalController'), 'controller missing createInformationalController');
  assert.ok(has(CONTROLLER_SOURCE, 'MunicipalResidentConfirmGate'), 'controller does not compose the confirm gate');
  assert.ok(has(CONTROLLER_SOURCE, 'showConfirmRun'), 'controller does not delegate showConfirmRun to the gate');
  assert.ok(has(CONTROLLER_SOURCE, 'startConfirmFlow'), 'controller missing startConfirmFlow');
  assert.ok(has(CONTROLLER_SOURCE, 'runHandoff'), 'controller missing runHandoff');
  assert.ok(has(CONTROLLER_SOURCE, 'runGroundedJourney'), 'controller missing runGroundedJourney');
  assert.ok(has(CONTROLLER_SOURCE, 'executeYesContinuation'), 'controller missing executeYesContinuation');
});

test('Seo-gu shell is a thin bootstrap (no local confirm, handoff, or progress state machines)', () => {
  assert.ok(!has(SEOGU_SHELL_SOURCE, 'function _showConfirmRun'), 'Seo-gu still declares local _showConfirmRun');
  assert.ok(!has(SEOGU_SHELL_SOURCE, 'function _runConfirmedJourney'), 'Seo-gu still declares local _runConfirmedJourney');
  assert.ok(!has(SEOGU_SHELL_SOURCE, 'function _runExternalOfficialHandoff'), 'Seo-gu still declares local _runExternalOfficialHandoff');
  assert.ok(!has(SEOGU_SHELL_SOURCE, 'function _answerQuestion'), 'Seo-gu still declares local _answerQuestion');
  assert.ok(!/_confirmGeneration/.test(SEOGU_SHELL_SOURCE), 'Seo-gu still declares _confirmGeneration');
  assert.ok(has(SEOGU_SHELL_SOURCE, 'MunicipalResidentInformationalController'), 'Seo-gu does not reference the shared informational controller');
  // Seo-gu must not directly own top-level progress states like "navigate" or "handoff_evidence_running"
  assert.ok(!has(SEOGU_SHELL_SOURCE, '"data-journey-state", "navigate"'), 'Seo-gu directly assigns data-journey-state="navigate" (controller must own it)');
  assert.ok(!has(SEOGU_SHELL_SOURCE, '"data-journey-state", "handoff_evidence_running"'), 'Seo-gu directly assigns data-journey-state="handoff_evidence_running" (controller must own it)');
  assert.ok(!has(SEOGU_SHELL_SOURCE, '"data-journey-state", "safe_handoff"'), 'Seo-gu directly assigns data-journey-state="safe_handoff" (controller must own it)');
});

test('Buk-gu shell delegates to the golden engine (no duplicated owner)', () => {
  assert.ok(!/var _confirmGeneration/.test(BUKGU_SHELL_SOURCE), 'Buk-gu still declares _confirmGeneration');
  assert.ok(has(BUKGU_HTML, 'municipal-resident-confirm-gate.js'), 'Buk-gu demo HTML does not load the golden gate');
  assert.ok(has(BUKGU_SHELL_SOURCE, 'MunicipalResidentInformationalController'), 'Buk-gu does not reference the shared informational controller');
});

test('Buk-gu confirm wrappers delegate to the shared controller (behavior-preserving)', () => {
  assert.ok(has(BUKGU_SHELL_SOURCE, 'bukguInfoController.showConfirmRun'), 'Buk-gu showConfirmRun does not delegate');
  assert.ok(has(BUKGU_SHELL_SOURCE, 'bukguInfoController.invalidate'), 'Buk-gu reset does not invalidate');
});

test('both shells use the shared informational controller (no duplicate scheduling)', () => {
  assert.ok(has(SEOGU_SHELL_SOURCE, 'seoguInfoController.startConfirmFlow'), 'Seo-gu does not use controller.startConfirmFlow');
  assert.ok(has(BUKGU_SHELL_SOURCE, 'bukguInfoController.showConfirmRun'), 'Buk-gu does not use controller.showConfirmRun');
  assert.ok(
    !/setTimeout.*seoguConfirmGate\.showConfirmRun|setTimeout.*seoguInfoController\.showConfirmRun/.test(SEOGU_SHELL_SOURCE),
    'Seo-gu still has inline setTimeout showConfirmRun (controller should own it)'
  );
});

test('both demo HTML files load the shared informational controller before their shell', () => {
  assert.ok(has(SEOGU_HTML, 'municipal-resident-informational-controller.js'), 'Seo-gu HTML missing informational controller');
  assert.ok(has(BUKGU_HTML, 'municipal-resident-informational-controller.js'), 'Buk-gu HTML missing informational controller');
  assert.ok(
    SEOGU_HTML.indexOf('municipal-resident-informational-controller.js') < SEOGU_HTML.indexOf('seogu-citizen-action-shell.js'),
    'informational controller must load before Seo-gu shell'
  );
  assert.ok(
    BUKGU_HTML.indexOf('municipal-resident-informational-controller.js') < BUKGU_HTML.indexOf('citizen-first-use-shell.js'),
    'informational controller must load before Buk-gu shell'
  );
});

test('exactly one production file renders the confirm-run controls', () => {
  let owners = 0;
  const files = fs.readdirSync(STATIC_DIR);
  for (const f of files) {
    if (!f.endsWith('.js')) continue;
    const src = fs.readFileSync(path.join(STATIC_DIR, f), 'utf8');
    if (src.includes('data-confirm-action')) owners += 1;
  }
  assert.strictEqual(owners, 1, `expected exactly 1 owner of data-confirm-action, got ${owners}`);
});

test('both demo HTML files load the golden confirm gate before their shell', () => {
  assert.ok(has(SEOGU_HTML, 'municipal-resident-confirm-gate.js'), 'Seo-gu HTML missing golden gate');
  assert.ok(has(BUKGU_HTML, 'municipal-resident-confirm-gate.js'), 'Buk-gu HTML missing golden gate');
  assert.ok(
    SEOGU_HTML.indexOf('municipal-resident-confirm-gate.js') < SEOGU_HTML.indexOf('seogu-citizen-action-shell.js'),
    'golden gate must load before Seo-gu shell'
  );
  assert.ok(
    BUKGU_HTML.indexOf('municipal-resident-confirm-gate.js') < BUKGU_HTML.indexOf('citizen-first-use-shell.js'),
    'golden gate must load before Buk-gu shell'
  );
});

// ── Runtime: canonical gate lifecycle behavior ────────────────────────────
test('showConfirmRun renders a single canonical confirm-run bubble with YES + NO', () => {
  const { gate, thread } = loadGate();
  gate.showConfirmRun({ question: 'chip/housing' });
  const bubbles = thread._children.filter((n) => n.className && n.className.includes('chat-msg--confirm-run'));
  assert.strictEqual(bubbles.length, 1, `expected 1 confirm-run bubble, got ${bubbles.length}`);
  const b = bubbles[0];
  assert.strictEqual(b.getAttribute('data-msg-type'), 'confirm-run', 'missing data-msg-type');
  const btns = b.querySelectorAll('button');
  assert.strictEqual(btns.length, 2, `expected 2 controls, got ${btns.length}`);
  const act = btns.map((x) => x.getAttribute('data-confirm-action'));
  assert.ok(act.includes('yes') && act.includes('no'), 'YES/NO controls missing');
  const prompt = b._descendants((n) => n._tag === 'p')[0];
  assert.ok(prompt && String(prompt.textContent).includes('공동주택 부서 문의'), 'display name not rendered in confirm prompt');
});

test('YES is the only allowed transition trigger and fires onYes', () => {
  const { gate, thread, yesCalls } = loadGate();
  gate.showConfirmRun({ question: 'chip/housing' });
  const b = lastConfirmBubble(thread);
  const yes = b.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'yes');
  assert.ok(yes, 'yes button not found');
  yes._click();
  assert.strictEqual(yesCalls(), 1, `YES did not fire onYes exactly once, got ${yesCalls()}`);
});

test('NO stops on the answer with zero navigation (onNo fires)', () => {
  const { gate, thread, states, noCalls } = loadGate();
  gate.showConfirmRun({ question: 'chip/housing' });
  const b = lastConfirmBubble(thread);
  const no = b.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'no');
  assert.ok(no, 'no button not found');
  no._click();
  assert.ok(states.includes('confirm'), 'confirm state was not asserted before NO');
  assert.ok(states.includes('answer'), 'NO did not transition to answer state');
  assert.strictEqual(noCalls(), 1, `NO did not fire onNo, got ${noCalls()}`);
});

test('stale-confirm guard: invalidate() deactivates prior YES/NO controls', () => {
  const { gate, thread, yesCalls, noCalls } = loadGate();
  gate.showConfirmRun({ question: 'chip/housing' });
  gate.invalidate();
  const b = lastConfirmBubble(thread);
  const yes = b.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'yes');
  const no = b.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'no');
  yes._click();
  no._click();
  assert.strictEqual(yesCalls(), 0, 'stale YES fired after invalidate');
  assert.strictEqual(noCalls(), 0, 'stale NO fired after invalidate');
});

test('double-action protection: controls are disabled after a decision', () => {
  const { gate, thread } = loadGate();
  gate.showConfirmRun({ question: 'chip/housing' });
  const b = lastConfirmBubble(thread);
  const yes = b.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'yes');
  yes._click();
  const btns = b.querySelectorAll('button');
  assert.ok(btns.every((x) => x.disabled), 'buttons not disabled after click');
});

test('a second showConfirmRun after invalidate is live (fresh generation)', () => {
  const { gate, thread, yesCalls } = loadGate();
  gate.showConfirmRun({ question: 'chip/housing' });
  gate.invalidate();
  gate.showConfirmRun({ question: 'chip/housing' });
  const bubbles = thread._children.filter((n) => n.className && n.className.includes('chat-msg--confirm-run'));
  assert.strictEqual(bubbles.length, 2, `expected 2 bubbles, got ${bubbles.length}`);
  const fresh = bubbles[bubbles.length - 1];
  const yes = fresh.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'yes');
  yes._click();
  assert.strictEqual(yesCalls(), 1, 'fresh YES did not fire after re-show');
});

// ── Runtime: Informational Controller behavior & handoff state machine ─────
test('shared controller owns answer -> confirm -> NO sequence', async () => {
  const { controller, states, thread } = loadController();
  let answerRendered = false;
  let noCalled = false;

  controller.startConfirmFlow({
    question: 'chip/housing',
    delay: 0,
    renderAnswer: () => { answerRendered = true; },
    onNo: () => { noCalled = true; },
  });

  assert.ok(answerRendered, 'renderAnswer was not called');
  assert.ok(states.includes('answer'), 'controller did not assert answer state');

  await new Promise((r) => setTimeout(r, 10));

  assert.ok(states.includes('confirm'), 'controller did not assert confirm state');
  const bubble = lastConfirmBubble(thread);
  assert.ok(bubble, 'confirm-run bubble not found');

  const noBtn = bubble.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'no');
  assert.ok(noBtn, 'no button not found');
  noBtn._click();

  assert.ok(noCalled, 'onNo was not called on NO click');
  assert.strictEqual(states[states.length - 1], 'answer', 'final state after NO must be answer');
});

test('shared controller owns external official handoff flow with verified markers (safe_handoff)', async () => {
  const surface = {
    navigate: (route) => route === 'parking-evidence/',
    readEvidence: () => ({
      ok: true,
      route: 'parking-evidence/',
      text: '주정차단속조회 과태료 조회 과태료 납부 의견진술',
    }),
  };

  const { controller, states, renderedEvidence, renderedDestinations, renderedBlocked } = loadController();

  const journey = {
    journey_id: 'seogu_illegal_parking_report',
    handoff: {
      local_evidence_route: 'parking-evidence/',
      required_markers: ['주정차단속조회', '과태료 조회', '과태료 납부', '의견진술'],
      destination_url: 'https://www.safetyreport.go.kr/#main',
      destination_label: '안전신문고',
    },
  };

  await controller.runHandoff({ journey, surface, timeoutMs: 100 });

  assert.ok(states.includes('handoff_evidence_running'), 'controller did not transition through handoff_evidence_running');
  assert.ok(states.includes('safe_handoff'), 'controller did not transition to safe_handoff');
  assert.strictEqual(renderedEvidence.length, 1, 'renderHandoffEvidence was not called exactly once');
  assert.strictEqual(renderedDestinations.length, 1, 'renderHandoffDestination was not called exactly once');
  assert.strictEqual(renderedBlocked.length, 0, 'renderHandoffBlocked should not be called when verified');
});

test('shared controller owns external official handoff FAIL-CLOSED decision when markers missing', async () => {
  const surface = {
    navigate: (route) => route === 'parking-evidence/',
    readEvidence: () => ({
      ok: true,
      route: 'parking-evidence/',
      text: '주정차단속조회 과태료 조회', // missing '과태료 납부', '의견진술'
    }),
  };

  const { controller, states, renderedEvidence, renderedDestinations, renderedBlocked } = loadController();

  const journey = {
    journey_id: 'seogu_illegal_parking_report',
    handoff: {
      local_evidence_route: 'parking-evidence/',
      required_markers: ['주정차단속조회', '과태료 조회', '과태료 납부', '의견진술'],
      destination_url: 'https://www.safetyreport.go.kr/#main',
    },
  };

  await controller.runHandoff({ journey, surface, timeoutMs: 100 });

  assert.ok(states.includes('handoff_evidence_running'), 'controller did not transition through handoff_evidence_running');
  assert.ok(states.includes('handoff_evidence_failed'), 'controller did not transition to handoff_evidence_failed on marker mismatch');
  assert.ok(!states.includes('safe_handoff'), 'controller must not transition to safe_handoff on failure');
  assert.strictEqual(renderedDestinations.length, 0, 'renderHandoffDestination must not be called on failure');
  assert.strictEqual(renderedBlocked.length, 1, 'renderHandoffBlocked must be called exactly once on failure');
});

test('shared controller owns complete answer -> confirm -> YES -> handoff lifecycle', async () => {
  const surface = {
    navigate: (route) => route === 'parking-evidence/',
    readEvidence: () => ({
      ok: true,
      route: 'parking-evidence/',
      text: '주정차단속조회 과태료 조회 과태료 납부 의견진술',
    }),
  };

  const { controller, states, thread, renderedDestinations, inputNode, sendNode } = loadController();

  const journey = {
    journey_id: 'seogu_illegal_parking_report',
    handoff: {
      local_evidence_route: 'parking-evidence/',
      required_markers: ['주정차단속조회', '과태료 조회', '과태료 납부', '의견진술'],
      destination_url: 'https://www.safetyreport.go.kr/#main',
    },
  };

  controller.startConfirmFlow({
    question: '불법 주정차 신고',
    journey,
    surface,
    delay: 0,
    renderAnswer: () => {},
  });

  await new Promise((r) => setTimeout(r, 10));

  const bubble = lastConfirmBubble(thread);
  const yesBtn = bubble.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'yes');
  yesBtn._click();

  await new Promise((r) => setTimeout(r, 50));

  assert.ok(states.includes('answer'), 'missing answer state');
  assert.ok(states.includes('confirm'), 'missing confirm state');
  assert.ok(states.includes('navigate'), 'missing navigate state');
  assert.ok(states.includes('handoff_evidence_running'), 'missing handoff_evidence_running state');
  assert.ok(states.includes('safe_handoff'), 'missing safe_handoff state');
  assert.strictEqual(renderedDestinations.length, 1, 'destination not rendered after full flow');
  assert.ok(!inputNode.disabled, 'input must be re-enabled after flow completes');
  assert.ok(!sendNode.disabled, 'send must be re-enabled after flow completes');
});

test('shared controller owns grounded clone journey flow', async () => {
  const mockResult = {
    ok: true,
    grounded: true,
    answer: '공동주택 관련 안내입니다.',
    excerpt: '주택과 공동주택관리',
  };

  const { controller, states, renderedGrounded, sandbox } = loadController();
  sandbox.window.MunicipalResidentJourney = {
    run: async () => mockResult,
  };

  const journey = {
    journey_id: 'seogu_apartment_housing_dept',
    entry_route: 'housing/',
  };

  const surface = {
    navigate: () => true,
    readEvidence: () => ({ ok: true, route: 'housing/' }),
  };

  await controller.runGroundedJourney({ journey, surface });

  assert.ok(states.includes('running'), 'missing running state');
  assert.ok(states.includes('grounded'), 'missing grounded state');
  assert.strictEqual(renderedGrounded.length, 1, 'renderGroundedResult not called');
  assert.strictEqual(renderedGrounded[0].result, mockResult, 'result mismatch');
});
