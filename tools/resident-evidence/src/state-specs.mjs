// tools/resident-evidence/src/state-specs.mjs
//
// Declarative semantic state predicate bundles for Resident Journey Evidence Harness V1.
// Based on proven runtime predicate probe observations.
//
// Each state spec is a frozen object with:
//   semanticState: string
//   required: Array<{name, check}> — predicate combinators
//   forbidden: Array<{name, check}> — predicate combinators (must all fail-to-find)
//   surface: "conversation" | "guidance" | "any" — mobile surface requirement
//   stabilityNotes: string — proven stability characteristics
//
// State identity is NEVER inferred from the filename alone.
// All predicates are evaluated against actual DOM/runtime truth.

import {
  bodyAttrIs,
  bodyAttrIsNot,
  selectorExists,
  selectorAbsent,
  selectorVisible,
  selectorNotVisible,
  inputValueNonEmpty,
  elementDisabled,
  visibleTextAbsent,
  visibleTextContains,
  elementTextContains,
  ariaIs,
} from "./predicates.mjs";

// ── Success/receipt forbidden text patterns ─────────────────────────────
// These are proven absent at all pre-submit states by the runtime probe.
export const FORBIDDEN_SUCCESS_PATTERNS = [
  "접수되었습니다",
  "접수번호",
  "민원 접수가 완료",
  "제출이 완료",
  "처리결과",
  "등록되었습니다",
];

/**
 * Build forbidden success semantics predicates from the shared pattern list.
 */
function forbiddenSuccessPredicates() {
  return FORBIDDEN_SUCCESS_PATTERNS.map((text) => ({
    name: `forbidden-text:${text}`,
    check: visibleTextAbsent(text),
  }));
}

/**
 * Build the standard forbidden predicates for all pre-submit states:
 * - no success/receipt text
 * - #btn-board-submit must be disabled
 */
function standardPreSubmitForbidden() {
  return [
    ...forbiddenSuccessPredicates(),
    {
      name: "btn-board-submit-disabled",
      check: elementDisabled("#btn-board-submit"),
    },
  ];
}

// ── Semantic state definitions ──────────────────────────────────────────

export const STATES = Object.freeze({
  // ── ENTRY ──────────────────────────────────────────────────────────────
  ENTRY: Object.freeze({
    semanticState: "ENTRY",
    surface: "any",
    required: [
      { name: "first-use-state=entry", check: bodyAttrIs("first-use-state", "entry") },
      { name: "journey-state=entry", check: bodyAttrIs("journey-state", "entry") },
      { name: "composer-visible", check: selectorVisible("#chat-composer-input") },
      { name: "choreography-absent", check: bodyAttrIs("choreography-state", null) },
    ],
    forbidden: [
      { name: "no-confirm-run", check: selectorAbsent('[data-msg-type="confirm-run"]') },
      { name: "no-decision-buttons", check: selectorAbsent(".chat-decision__button") },
      { name: "no-success-text", check: visibleTextAbsent("접수되었습니다") },
    ],
    stabilityNotes: "choreography=null, journey=entry, firstUse=entry — stable across 3 samples",
  }),

  // ── BEFORE_CLICK ───────────────────────────────────────────────────────
  // NOTE: ENTRY and BEFORE_CLICK share body attributes. The differentiator
  // is the composer input value. This is a user-action state.
  BEFORE_CLICK: Object.freeze({
    semanticState: "BEFORE_CLICK",
    surface: "any",
    required: [
      { name: "first-use-state=entry", check: bodyAttrIs("first-use-state", "entry") },
      { name: "journey-state=entry", check: bodyAttrIs("journey-state", "entry") },
      { name: "composer-value-non-empty", check: inputValueNonEmpty("#chat-composer-input") },
      { name: "send-button-visible", check: selectorVisible("#chat-composer-send") },
    ],
    forbidden: [
      { name: "not-split", check: bodyAttrIsNot("first-use-state", "split") },
      { name: "no-success-text", check: visibleTextAbsent("접수되었습니다") },
    ],
    stabilityNotes: "same as ENTRY but composer input value is non-empty — user-action state",
  }),

  // ── CONFIRMATION ───────────────────────────────────────────────────────
  CONFIRMATION: Object.freeze({
    semanticState: "CONFIRMATION",
    surface: "any",
    required: [
      { name: "first-use-state=split", check: bodyAttrIs("first-use-state", "split") },
      { name: "journey-state=confirm", check: bodyAttrIs("journey-state", "confirm") },
      { name: "confirm-run-visible", check: selectorVisible('[data-msg-type="confirm-run"]') },
      { name: "yes-button-visible", check: elementTextContains(".chat-msg--confirm-run", "예, 안내해 주세요") },
      { name: "no-button-visible", check: elementTextContains(".chat-msg--confirm-run", "아니요") },
    ],
    forbidden: [
      { name: "no-decision-buttons", check: selectorAbsent(".chat-decision__button") },
      { name: "no-board-write-title", check: selectorAbsent("#board-write-title") },
      { name: "choreography-not-running", check: bodyAttrIsNot("choreography-state", "running") },
      { name: "not-waiting-choice", check: bodyAttrIsNot("choreography-state", "waiting_choice") },
      { name: "not-waiting-confirmation", check: bodyAttrIsNot("choreography-state", "waiting_confirmation") },
    ],
    stabilityNotes: "choreography=null, journey=confirm, firstUse=split — stable across 3 samples",
  }),

  // ── CHOICE ─────────────────────────────────────────────────────────────
  CHOICE: Object.freeze({
    semanticState: "CHOICE",
    surface: "conversation",
    required: [
      { name: "choreography=waiting_choice", check: bodyAttrIs("choreography-state", "waiting_choice") },
      { name: "ai-help-button-exists", check: selectorExists(".chat-decision__button--primary") },
      { name: "write-self-button-exists", check: selectorExists(".chat-decision__button--secondary") },
      { name: "decision-message-exists", check: selectorExists(".chat-msg--decision") },
      { name: "ai-help-text", check: elementTextContains(".chat-decision__button--primary", "AI 도움 받기") },
      { name: "write-self-text", check: elementTextContains(".chat-decision__button--secondary", "직접 작성") },
    ],
    forbidden: [
      { name: "not-waiting-confirmation", check: bodyAttrIsNot("choreography-state", "waiting_confirmation") },
      { name: "no-title-populated", check: selectorAbsent("#board-write-title") },
      ...forbiddenSuccessPredicates(),
    ],
    // For accepted mobile CHOICE evidence, both buttons must be VISIBLE
    // on the conversation surface. The harness must switch to conversation
    // before accepting CHOICE evidence.
    evidenceRequirements: Object.freeze([
      { name: "surface-conversation-or-desktop", check: bodyAttrIs("mobile-surface", "conversation") },
      { name: "ai-help-button-visible", check: selectorVisible(".chat-decision__button--primary") },
      { name: "write-self-button-visible", check: selectorVisible(".chat-decision__button--secondary") },
    ]),
    stabilityNotes: "choreography=waiting_choice — stable across 3 samples; typing/highlight absent",
  }),

  // ── DRAFT_POPULATED ────────────────────────────────────────────────────
  DRAFT_POPULATED: Object.freeze({
    semanticState: "DRAFT_POPULATED",
    surface: "any",
    required: [
      { name: "choreography=waiting_confirmation", check: bodyAttrIs("choreography-state", "waiting_confirmation") },
      { name: "title-exists-non-empty", check: inputValueNonEmpty("#board-write-title") },
      { name: "content-exists-non-empty", check: inputValueNonEmpty("#board-write-content") },
      { name: "submit-decision-exists", check: selectorExists(".chat-decision__button--primary") },
      { name: "edit-decision-exists", check: selectorExists(".chat-decision__button--secondary") },
      { name: "submit-decision-text", check: visibleTextContains("검토했고, 제출하기", "#chat-thread") },
      { name: "edit-decision-text", check: visibleTextContains("수정할게요", "#chat-thread") },
    ],
    forbidden: standardPreSubmitForbidden(),
    stabilityNotes: "choreography=waiting_confirmation, title/content values stable — stable across 3 samples",
    // On desktop, DRAFT_POPULATED == PRE_SUBMIT_CONVERSATION (NOT_SEPARATELY_OBSERVABLE)
    equivalentState: "PRE_SUBMIT_CONVERSATION",
    nonSeparableOn: "desktop",
  }),

  // ── PRE_SUBMIT_CONVERSATION ────────────────────────────────────────────
  PRE_SUBMIT_CONVERSATION: Object.freeze({
    semanticState: "PRE_SUBMIT_CONVERSATION",
    surface: "conversation",
    required: [
      { name: "choreography=waiting_confirmation", check: bodyAttrIs("choreography-state", "waiting_confirmation") },
      { name: "surface-conversation-or-desktop", check: bodyAttrIs("mobile-surface", "conversation") },
      { name: "chat-thread-visible", check: selectorVisible("#chat-thread") },
      { name: "submit-decision-visible", check: selectorVisible(".chat-decision__button--primary") },
      { name: "edit-decision-visible", check: selectorVisible(".chat-decision__button--secondary") },
      { name: "submit-decision-text", check: visibleTextContains("검토했고, 제출하기", "#chat-thread") },
      { name: "edit-decision-text", check: visibleTextContains("수정할게요", "#chat-thread") },
    ],
    forbidden: [
      ...standardPreSubmitForbidden(),
      { name: "not-guidance-surface", check: bodyAttrIsNot("mobile-surface", "guidance") },
    ],
    stabilityNotes: "choreography=waiting_confirmation, surface=conversation — stable across 3 samples",
  }),

  // ── PRE_SUBMIT_GUIDANCE ────────────────────────────────────────────────
  PRE_SUBMIT_GUIDANCE: Object.freeze({
    semanticState: "PRE_SUBMIT_GUIDANCE",
    surface: "guidance",
    required: [
      { name: "choreography=waiting_confirmation", check: bodyAttrIs("choreography-state", "waiting_confirmation") },
      { name: "mobile-surface=guidance", check: bodyAttrIs("mobile-surface", "guidance") },
      { name: "title-visible-non-empty", check: inputValueNonEmpty("#board-write-title") },
      { name: "content-visible-non-empty", check: inputValueNonEmpty("#board-write-content") },
      { name: "title-visible", check: selectorVisible("#board-write-title") },
      { name: "content-visible", check: selectorVisible("#board-write-content") },
      { name: "demo-canvas-visible", check: selectorVisible("#demo-canvas") },
      { name: "guidance-tab-pressed", check: ariaIs("#tab-guidance", "aria-pressed", "true") },
    ],
    forbidden: [
      ...standardPreSubmitForbidden(),
      { name: "chat-thread-not-visible", check: selectorNotVisible("#chat-thread") },
      { name: "not-conversation-surface", check: bodyAttrIsNot("mobile-surface", "conversation") },
    ],
    stabilityNotes: "choreography=waiting_confirmation, surface=guidance, title/content visible — stable across 3 samples",
  }),
});

// ── Non-separable state pairs ─────────────────────────────────────────────
// These pairs are proven NOT_SEPARATELY_OBSERVABLE on specific viewports.
export const NON_SEPARABLE_PAIRS = Object.freeze([
  {
    stateA: "DRAFT_POPULATED",
    stateB: "PRE_SUBMIT_CONVERSATION",
    viewport: "desktop",
    reason: "Same choreography state (waiting_confirmation), same form field values, same button set, same surface (null on desktop). No stable interval between them.",
  },
]);

// ── FINAL_STABLE_STATE policy ────────────────────────────────────────────
// V1 must NEVER reach data-choreography-state="done" if it requires clicking
// "검토했고, 제출하기". FINAL_STABLE_STATE aliases the last safely observable
// pre-submit state. If no unique predicate exists beyond PRE_SUBMIT, it is
// classified as NOT_SEPARATELY_OBSERVABLE.
export const FINAL_STABLE_STATE_POLICY = Object.freeze({
  forbiddenClick: "검토했고, 제출하기",
  forbiddenChoreographyState: "done",
  alias: "PRE_SUBMIT_CONVERSATION",
  reason: "Reaching choreography=done requires clicking the final confirmation button, which is forbidden by #1355 hard boundary. V1 aliases FINAL_STABLE_STATE to the last safe pre-submit state.",
});

/**
 * Get a state spec by semantic state name.
 * @param {string} semanticState
 * @returns {Object|null}
 */
export function getStateSpec(semanticState) {
  return STATES[semanticState] || null;
}

/**
 * Get all semantic state names.
 * @returns {string[]}
 */
export function getAllStateNames() {
  return Object.keys(STATES);
}
