/**
 * Architecture regression proof for #1365: ONE GOLDEN ENGINE for the resident
 * confirmation gate.
 *
 * Purpose: prove that a future developer cannot silently reintroduce
 *   - a Seo-gu-local canonical confirm-run state machine, or
 *   - a duplicated confirmation owner.
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
import { fileURLToPath } from 'node:url';

const STATIC_DIR = path.dirname(fileURLToPath(new URL('../../src/web/static/municipal-resident-confirm-gate.js', import.meta.url)));
const REPO_ROOT = path.dirname(fileURLToPath(new URL('../../', import.meta.url)));

const GATE_SOURCE = fs.readFileSync(path.join(STATIC_DIR, 'municipal-resident-confirm-gate.js'), 'utf8');
const SEOGU_SHELL_SOURCE = fs.readFileSync(path.join(STATIC_DIR, 'seogu-citizen-action-shell.js'), 'utf8');
const BUKGU_SHELL_SOURCE = fs.readFileSync(path.join(STATIC_DIR, 'citizen-first-use-shell.js'), 'utf8');
const SEOGU_HTML = fs.readFileSync(path.join(STATIC_DIR, 'seogu-citizen-action-demo.html'), 'utf8');
const BUKGU_HTML = fs.readFileSync(path.join(STATIC_DIR, 'citizen-action-demo.html'), 'utf8');

let passed = 0;
let failed = 0;
const failures = [];

async function check(name, fn) {
  try {
    await fn();
    passed += 1;
    console.log(`  PASS ${name}`);
  } catch (error) {
    failed += 1;
    failures.push(`${name}: ${error.message}`);
    console.log(`  FAIL ${name}: ${error.message}`);
  }
}

function has(haystack, needle) { return haystack.includes(needle); }

// ── DOM shim sufficient for the confirm gate (no jsdom needed) ──────────────
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

function loadGate(adapterOverrides) {
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

  const win = { addEventListener() {}, matchMedia() { return { matches: false }; } };
  const sandbox = {
    window: win,
    document: { createElement: makeElement },
    matchMedia: win.matchMedia,
    setTimeout: (fn) => fn(),
    clearTimeout: () => {},
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

  const api = win.MunicipalResidentConfirmGate;
  const overrides = adapterOverrides || {};
  const gate = api.createConfirmGate(Object.assign({
    getThread: () => thread,
    getInput: () => null,
    displayName: (q) => (q === 'chip/housing' ? '공동주택 부서 문의' : q),
    setJourneyState: (s) => states.push(s),
    isMobileSurfaceMode: () => false,
    scrollToLatest: (node) => { thread.appendChild(node); },
    onYesSurfacePrepare: () => { surfacePrepared += 1; },
    onYes: (q) => { yesCalls += 1; },
    onNo: () => { noCalls += 1; },
  }, overrides));

  return { gate, thread, states, yesCalls: () => yesCalls, noCalls: () => noCalls,
    surfacePrepared: () => surfacePrepared, api };
}

function lastConfirmBubble(thread) {
  return thread._children.filter((n) => n.className.includes('chat-msg--confirm-run'))[0];
}

console.log('\n=== Golden confirm-gate architecture (static + runtime) ===\n');

// ── Static: single shared canonical owner ──────────────────────────────────
check('shared gate module exists and exposes createConfirmGate', () => {
  if (!has(GATE_SOURCE, 'createConfirmGate')) throw new Error('createConfirmGate missing');
  if (!has(GATE_SOURCE, 'MunicipalResidentConfirmGate')) throw new Error('export missing');
});

check('shared gate owns the canonical YES/NO decision seam', () => {
  if (!has(GATE_SOURCE, 'data-confirm-action')) throw new Error('data-confirm-action seam not owned by gate');
  if (!has(GATE_SOURCE, '"data-confirm-action", "yes"')) throw new Error('YES control not owned by gate');
  if (!has(GATE_SOURCE, '"data-confirm-action", "no"')) throw new Error('NO control not owned by gate');
});

check('shared gate owns the stale-confirm generation guard', () => {
  if (!has(GATE_SOURCE, 'invalidate')) throw new Error('invalidate() not exposed');
  if (!has(GATE_SOURCE, 'generation')) throw new Error('generation guard not owned by gate');
});

check('Seo-gu shell delegates to the golden engine (no local confirm state machine)', () => {
  if (has(SEOGU_SHELL_SOURCE, 'function _showConfirmRun')) throw new Error('Seo-gu still declares local _showConfirmRun');
  if (has(SEOGU_SHELL_SOURCE, 'function _runConfirmedJourney')) throw new Error('Seo-gu still declares local _runConfirmedJourney');
  if (/_confirmGeneration/.test(SEOGU_SHELL_SOURCE)) throw new Error('Seo-gu still declares _confirmGeneration');
  if (!has(SEOGU_SHELL_SOURCE, 'MunicipalResidentInformationalController')) throw new Error('Seo-gu does not reference the shared informational controller');
});

check('Buk-gu shell delegates to the golden engine (no duplicated owner)', () => {
  if (/var _confirmGeneration/.test(BUKGU_SHELL_SOURCE)) throw new Error('Buk-gu still declares _confirmGeneration');
  if (!has(BUKGU_HTML, 'municipal-resident-confirm-gate.js')) throw new Error('Buk-gu demo HTML does not load the golden gate');
  if (!has(BUKGU_SHELL_SOURCE, 'MunicipalResidentInformationalController')) throw new Error('Buk-gu does not reference the shared informational controller');
});

check('Buk-gu confirm wrappers delegate to the shared controller (behavior-preserving)', () => {
  if (!has(BUKGU_SHELL_SOURCE, 'bukguInfoController.showConfirmRun')) throw new Error('Buk-gu showConfirmRun does not delegate');
  if (!has(BUKGU_SHELL_SOURCE, 'bukguInfoController.invalidate')) throw new Error('Buk-gu reset does not invalidate');
});

check('one shared informational controller exists and composes the confirm gate', () => {
  const ctrlSrc = fs.readFileSync(path.join(STATIC_DIR, 'municipal-resident-informational-controller.js'), 'utf8');
  if (!has(ctrlSrc, 'createInformationalController')) throw new Error('controller missing createInformationalController');
  if (!has(ctrlSrc, 'MunicipalResidentConfirmGate')) throw new Error('controller does not compose the confirm gate');
  if (!has(ctrlSrc, 'showConfirmRun')) throw new Error('controller does not delegate showConfirmRun to the gate');
  if (!has(ctrlSrc, 'startConfirmFlow')) throw new Error('controller missing startConfirmFlow');
});

check('both shells use the shared informational controller (no duplicate scheduling)', () => {
  if (!has(SEOGU_SHELL_SOURCE, 'seoguInfoController.startConfirmFlow')) throw new Error('Seo-gu does not use controller.startConfirmFlow');
  if (!has(BUKGU_SHELL_SOURCE, 'bukguInfoController.showConfirmRun')) throw new Error('Buk-gu does not use controller.showConfirmRun');
  // Seo-gu must not contain inline setTimeout + showConfirmRun (the controller owns that).
  if (/setTimeout.*seoguConfirmGate\.showConfirmRun|setTimeout.*seoguInfoController\.showConfirmRun/.test(SEOGU_SHELL_SOURCE)) {
    throw new Error('Seo-gu still has inline setTimeout showConfirmRun (controller should own it)');
  }
});

check('both demo HTML files load the shared informational controller before their shell', () => {
  if (!has(SEOGU_HTML, 'municipal-resident-informational-controller.js')) throw new Error('Seo-gu HTML missing informational controller');
  if (!has(BUKGU_HTML, 'municipal-resident-informational-controller.js')) throw new Error('Buk-gu HTML missing informational controller');
  if (SEOGU_HTML.indexOf('municipal-resident-informational-controller.js') > SEOGU_HTML.indexOf('seogu-citizen-action-shell.js')) {
    throw new Error('informational controller must load before Seo-gu shell');
  }
  if (BUKGU_HTML.indexOf('municipal-resident-informational-controller.js') > BUKGU_HTML.indexOf('citizen-first-use-shell.js')) {
    throw new Error('informational controller must load before Buk-gu shell');
  }
});

check('exactly one production file renders the confirm-run controls', () => {
  let owners = 0;
  const files = fs.readdirSync(STATIC_DIR);
  for (const f of files) {
    if (!f.endsWith('.js')) continue;
    const src = fs.readFileSync(path.join(STATIC_DIR, f), 'utf8');
    if (src.includes('data-confirm-action')) owners += 1;
  }
  if (owners !== 1) throw new Error(`expected exactly 1 owner of data-confirm-action, got ${owners}`);
});

check('both demo HTML files load the golden confirm gate before their shell', () => {
  if (!has(SEOGU_HTML, 'municipal-resident-confirm-gate.js')) throw new Error('Seo-gu HTML missing golden gate');
  if (!has(BUKGU_HTML, 'municipal-resident-confirm-gate.js')) throw new Error('Buk-gu HTML missing golden gate');
  if (SEOGU_HTML.indexOf('municipal-resident-confirm-gate.js') > SEOGU_HTML.indexOf('seogu-citizen-action-shell.js')) {
    throw new Error('golden gate must load before Seo-gu shell');
  }
  if (BUKGU_HTML.indexOf('municipal-resident-confirm-gate.js') > BUKGU_HTML.indexOf('citizen-first-use-shell.js')) {
    throw new Error('golden gate must load before Buk-gu shell');
  }
});

// ── Runtime: canonical lifecycle behavior ──────────────────────────────────
check('showConfirmRun renders a single canonical confirm-run bubble with YES + NO', () => {
  const { gate, thread } = loadGate();
  gate.showConfirmRun({ question: 'chip/housing' });
  const bubbles = thread._children.filter((n) => n.className.includes('chat-msg--confirm-run'));
  if (bubbles.length !== 1) throw new Error(`expected 1 confirm-run bubble, got ${bubbles.length}`);
  const b = bubbles[0];
  if (b.getAttribute('data-msg-type') !== 'confirm-run') throw new Error('missing data-msg-type');
  const btns = b.querySelectorAll('button');
  if (btns.length !== 2) throw new Error(`expected 2 controls, got ${btns.length}`);
  const act = btns.map((x) => x.getAttribute('data-confirm-action'));
  if (!act.includes('yes') || !act.includes('no')) throw new Error('YES/NO controls missing');
  const prompt = b._descendants((n) => n._tag === 'p')[0];
  if (!prompt || !String(prompt.textContent).includes('공동주택 부서 문의')) {
    throw new Error('display name not rendered in confirm prompt');
  }
});

check('YES is the only allowed transition trigger and fires onYes', () => {
  const { gate, thread, yesCalls } = loadGate();
  gate.showConfirmRun({ question: 'chip/housing' });
  const b = lastConfirmBubble(thread);
  const yes = b.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'yes');
  if (!yes) throw new Error('yes button not found');
  yes._click();
  if (yesCalls() !== 1) throw new Error(`YES did not fire onYes exactly once, got ${yesCalls()}`);
});

check('NO stops on the answer with zero navigation (onNo fires)', () => {
  const { gate, thread, states, noCalls } = loadGate();
  gate.showConfirmRun({ question: 'chip/housing' });
  const b = lastConfirmBubble(thread);
  const no = b.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'no');
  if (!no) throw new Error('no button not found');
  no._click();
  if (!states.includes('confirm')) throw new Error('confirm state was not asserted before NO');
  if (!states.includes('answer')) throw new Error('NO did not transition to answer state');
  if (noCalls() !== 1) throw new Error(`NO did not fire onNo, got ${noCalls()}`);
});

check('stale-confirm guard: invalidate() deactivates prior YES/NO controls', () => {
  const { gate, thread, yesCalls, noCalls } = loadGate();
  gate.showConfirmRun({ question: 'chip/housing' });
  gate.invalidate();
  const b = lastConfirmBubble(thread);
  const yes = b.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'yes');
  const no = b.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'no');
  yes._click();
  no._click();
  if (yesCalls() !== 0) throw new Error('stale YES fired after invalidate');
  if (noCalls() !== 0) throw new Error('stale NO fired after invalidate');
});

check('double-action protection: controls are disabled after a decision', () => {
  const { gate, thread } = loadGate();
  gate.showConfirmRun({ question: 'chip/housing' });
  const b = lastConfirmBubble(thread);
  const yes = b.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'yes');
  yes._click();
  const btns = b.querySelectorAll('button');
  if (!btns.every((x) => x.disabled)) throw new Error('buttons not disabled after click');
});

check('a second showConfirmRun after invalidate is live (fresh generation)', () => {
  const { gate, thread, yesCalls } = loadGate();
  gate.showConfirmRun({ question: 'chip/housing' });
  gate.invalidate();
  gate.showConfirmRun({ question: 'chip/housing' });
  const bubbles = thread._children.filter((n) => n.className.includes('chat-msg--confirm-run'));
  if (bubbles.length !== 2) throw new Error(`expected 2 bubbles, got ${bubbles.length}`);
  const fresh = bubbles[bubbles.length - 1];
  const yes = fresh.querySelectorAll('button').find((x) => x.getAttribute('data-confirm-action') === 'yes');
  yes._click();
  if (yesCalls() !== 1) throw new Error('fresh YES did not fire after re-show, got ' + yesCalls());
});

if (failed) {
  throw new Error(`golden confirm-gate architecture failed: ${failed}/${passed + failed}\n${failures.join('\n')}`);
}

console.log(`\nGolden confirm-gate architecture: ${passed}/${passed + failed} PASS`);
