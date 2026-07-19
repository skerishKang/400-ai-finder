/**
 * Static contract for English MVP "Continue reading" pill.
 * Node-only — no browser, no network, no live provider.
 *
 * Usage:
 *   node tests/test_continue_reading_en.mjs
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const JS = readFileSync(
  join(ROOT, "src/web/static/citizen-first-use-shell.js"),
  "utf8",
);
const CSS = readFileSync(
  join(ROOT, "src/web/static/citizen-first-use-shell.css"),
  "utf8",
);

function ok(name) {
  console.log(`PASS ${name}`);
}

// ── State / API surface ──────────────────────────────────────────
assert.match(JS, /var _continueReadingArmed = false/);
assert.match(JS, /var _continueReadButton = null/);
assert.match(JS, /var _continueReadResizeObserver = null/);
assert.match(JS, /function ensureContinueButton\s*\(/);
assert.match(JS, /function updateContinueButton\s*\(/);
assert.match(JS, /function removeContinueButton\s*\(/);
assert.match(JS, /function positionContinueButton\s*\(/);
assert.match(JS, /function armContinueReadingAfterMvpAnswer\s*\(/);
ok("state + helpers defined");

// ── Forbidden targeting patterns ─────────────────────────────────
assert.doesNotMatch(JS, /querySelectorAll\s*\(\s*["']\.chat-msg--ai["']\s*\)/);
assert.doesNotMatch(JS, /\b_continueTargetMsg\b/);
assert.doesNotMatch(JS, /\b_markLatestAssistantResponse\b/);
// Must not invent a generic "last AI message" fallback.
assert.doesNotMatch(
  JS,
  /querySelector\s*\(\s*["']\.chat-msg--ai:last-child["']\s*\)/,
);
ok("forbidden DOM targeting patterns absent");

// ── Arm only after MVP answerMessage path ────────────────────────
const armCall = "armContinueReadingAfterMvpAnswer(answerMessage, answer, result);";
const armIdx = JS.indexOf(armCall);
assert.ok(armIdx > 0, "arm call present");
// Function definition must appear before the call site.
const armDefIdx = JS.indexOf("function armContinueReadingAfterMvpAnswer");
assert.ok(armDefIdx > 0 && armDefIdx < armIdx, "helper defined before call");
const answerMsgIdx = JS.lastIndexOf(
  'var answerMessage = appendChatMessage("ai", answer)',
  armIdx,
);
assert.ok(answerMsgIdx > 0 && answerMsgIdx < armIdx, "arm after answerMessage");
const armWindow = JS.slice(answerMsgIdx, armIdx + armCall.length);
assert.match(armWindow, /if \(hasUsableMvpResult\)/);
assert.match(
  armWindow,
  /armContinueReadingAfterMvpAnswer\(answerMessage, answer, result\)/,
);
// appendChatMessage itself must not create the button
const appendStart = JS.indexOf("function appendChatMessage");
assert.ok(appendStart > 0, "appendChatMessage found");
const appendEnd = JS.indexOf("\n  function ", appendStart + 10);
const appendFn = JS.slice(appendStart, appendEnd > 0 ? appendEnd : appendStart + 800);
assert.doesNotMatch(appendFn, /chat-continue-read|ensureContinueButton|armContinue/);
ok("arm only at MVP success path; appendChatMessage untouched");

// ── handleMvpSubmission entry must disarm prior Continue reading ──
const mvpStart = JS.indexOf("function handleMvpSubmission");
assert.ok(mvpStart > 0, "handleMvpSubmission found");
const mvpHead = JS.slice(mvpStart, mvpStart + 500);
// Disarm must run at function entry before user echo / bridge ask.
const disarmArmed = mvpHead.indexOf("_continueReadingArmed = false");
const disarmRemove = mvpHead.indexOf("removeContinueButton()");
const echoIdx = mvpHead.indexOf("appendChatMessage(\"user\"");
assert.ok(disarmArmed > 0, "entry sets _continueReadingArmed = false");
assert.ok(disarmRemove > 0, "entry calls removeContinueButton()");
assert.ok(
  disarmArmed < echoIdx && disarmRemove < echoIdx,
  "disarm before user-message echo",
);
ok("handleMvpSubmission entry disarms continue-reading");

// ── Accessibility + click behavior ───────────────────────────────
assert.match(JS, /btn\.type\s*=\s*["']button["']/);
assert.match(JS, /btn\.className\s*=\s*["']chat-continue-read["']/);
assert.match(JS, /btn\.textContent\s*=\s*["']↓ Continue reading["']/);
assert.match(JS, /setAttribute\s*\(\s*["']aria-label["']\s*,\s*["']Continue reading["']\s*\)/);
assert.match(JS, /clientHeight\s*\*\s*0\.8/);
assert.match(JS, /reducedMotion\s*\?\s*["']auto["']\s*:\s*["']smooth["']/);
ok("a11y attributes + scroll-by 80% + reducedMotion");

// ── Locale gate + non-English removal ────────────────────────────
assert.match(JS, /CitizenI18n\.getLocale\(\)\s*===\s*["']en["']/);
assert.match(JS, /function updateContinueButton[\s\S]*?removeContinueButton\(\)/);
assert.match(JS, /function resetToEntry[\s\S]*?_continueReadingArmed = false/);
assert.match(JS, /function resetToEntry[\s\S]*?removeContinueButton\(\)/);
ok("locale gate + reset/Start over clears button");

// ── Visibility gate: remaining scroll > 8 ────────────────────────
assert.match(
  JS,
  /scrollHeight\s*-\s*chatThread\.scrollTop\s*-\s*chatThread\.clientHeight/,
);
assert.match(JS, /remaining\s*>\s*8|remainingScroll\s*>\s*8/);
ok("remainingScroll > 8 visibility gate");

// ── Position uses thread/shell rects, not bottom:8px CSS ──────────
assert.match(JS, /threadRect\.bottom\s*-\s*shellRect\.top/);
assert.match(JS, /ResizeObserver/);
// Continue-reading helpers must not poll; existing file may use timers elsewhere.
const contBlockStart = JS.indexOf("// ── English MVP Continue reading helpers");
const contBlockEnd = JS.indexOf("function handleMvpSubmission");
assert.ok(contBlockStart > 0 && contBlockEnd > contBlockStart);
const contBlock = JS.slice(contBlockStart, contBlockEnd);
assert.doesNotMatch(contBlock, /setInterval\s*\(/);
ok("JS position against chat-thread bottom; ResizeObserver; no polling");

// ── CSS design contract ──────────────────────────────────────────
assert.match(CSS, /\.chat-continue-read\s*\{/);
assert.match(CSS, /\.first-use-layout\s+\.chat-shell\s*\{[\s\S]*?position:\s*relative/);
const rule = CSS.match(/\.chat-continue-read\s*\{([^}]+)\}/);
assert.ok(rule, "pill rule present");
const body = rule[1];
assert.match(body, /display:\s*none/);
assert.match(body, /position:\s*absolute/);
assert.match(body, /background:\s*#fff/);
assert.match(body, /color:\s*var\(--first-use-teal\)/);
assert.match(body, /border:\s*1px\s+solid\s+var\(--first-use-teal\)/);
assert.match(body, /border-radius:\s*999px/);
assert.doesNotMatch(body, /bottom:\s*8px/);
assert.doesNotMatch(body, /background:\s*#008080|background:\s*var\(--first-use-teal\)/);
assert.doesNotMatch(body, /color:\s*#fff/);
assert.doesNotMatch(body, /coral|orange|#ff7654/i);
ok("CSS white pill + teal border/text; no bottom:8px; no teal fill");

// ── Forbidden files untouched (spot-check markers still present) ──
const choreo = readFileSync(
  join(ROOT, "src/web/static/citizen-first-choreography.js"),
  "utf8",
);
const i18n = readFileSync(join(ROOT, "src/web/static/citizen-i18n.js"), "utf8");
const bridge = readFileSync(
  join(ROOT, "src/web/static/citizen-mvp-bridge.js"),
  "utf8",
);
assert.doesNotMatch(choreo, /chat-continue-read|_continueReadingArmed/);
assert.doesNotMatch(i18n, /chat-continue-read|_continueReadingArmed/);
assert.doesNotMatch(bridge, /chat-continue-read|_continueReadingArmed/);
ok("choreography / i18n / bridge free of continue-reading hooks");

console.log("\nAll continue-reading static contracts passed.");
