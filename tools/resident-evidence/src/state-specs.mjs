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
//   equivalentState: string|null — when NOT_SEPARATELY_OBSERVABLE, the canonical alias
//   nonSeparableOn: string|null — viewport where this state is not separately observable
//   observable: boolean — false for states that have no unique runtime predicate
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
export const FORBIDDEN_SUCCESS_PATTERNS = [
  "접수되었습니다",
  "접수번호",
  "민원 접수가 완료",
  "제출이 완료",
  "처리결과",
  "등록되었습니다",
];

function forbiddenSuccessPredicates() {
  return FORBIDDEN_SUCCESS_PATTERNS.map((text) => ({
    name: `forbidden-text:${text}`,
    check: visibleTextAbsent(text),
  }));
}

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
    evidenceRequirements: Object.freeze([
      { name: "surface-conversation-or-desktop", check: bodyAttrIs("mobile-surface", "conversation") },
      { name: "ai-help-button-visible", check: selectorVisible(".chat-decision__button--primary") },
      { name: "write-self-button-visible", check: selectorVisible(".chat-decision__button--secondary") },
    ]),
    stabilityNotes: "choreography=waiting_choice — stable across 3 samples; typing/highlight absent",
  }),

  // ── TRANSITION ─────────────────────────────────────────────────────────
  // Probe proven: first-use-state="transitioning" is a transient cinematic
  // animation immediately replaced by "split". No stable observation window
  // exists. NOT_SEPARATELY_OBSERVABLE for accepted evidence.
  TRANSITION: Object.freeze({
    semanticState: "TRANSITION",
    surface: "any",
    observable: false,
    equivalentState: "CONFIRMATION",
    reason: "first-use-state=transitioning is a transient cinematic animation with no stable observation window. Replaced immediately by split. NOT_SEPARATELY_OBSERVABLE.",
    required: [],
    forbidden: [],
    stabilityNotes: "transient — no stable observation window",
  }),

  // ── SPLIT_READY ────────────────────────────────────────────────────────
  // Probe proven: SPLIT_READY has no unique stable predicate distinct from
  // CONFIRMATION. data-first-use-state="split" + confirm-run visible is the
  // same observable state as CONFIRMATION. NOT_SEPARATELY_OBSERVABLE.
  SPLIT_READY: Object.freeze({
    semanticState: "SPLIT_READY",
    surface: "any",
    observable: false,
    equivalentState: "CONFIRMATION",
    reason: "data-first-use-state=split + confirm-run visible is the same observable state as CONFIRMATION. No unique stable predicate exists. NOT_SEPARATELY_OBSERVABLE.",
    required: [],
    forbidden: [],
    stabilityNotes: "same as CONFIRMATION — NOT_SEPARATELY_OBSERVABLE",
  }),

  // ── TARGET_ROUTE_READY ─────────────────────────────────────────────────
  // Probe proven: canvas[data-canvas-route] is null at all observed states.
  // The route is rendered in canvas content, not a stable attribute. No
  // unique runtime predicate for "route ready" distinct from the choreography
  // step that follows. NOT_SEPARATELY_OBSERVABLE from the subsequent state.
  TARGET_ROUTE_READY: Object.freeze({
    semanticState: "TARGET_ROUTE_READY",
    surface: "any",
    observable: false,
    equivalentState: "CHOICE",
    reason: "canvas[data-canvas-route] is null at all observed states. Route is rendered in canvas content, not a stable attribute. No unique predicate distinct from the subsequent choreography state. NOT_SEPARATELY_OBSERVABLE.",
    required: [],
    forbidden: [],
    stabilityNotes: "no unique stable predicate — NOT_SEPARATELY_OBSERVABLE",
  }),

  // ── AI_ANSWER ──────────────────────────────────────────────────────────
  // The AI answer bubble is displayed in #chat-thread after the bridge
  // response. This is transient between split and confirm-run. In the Buk-gu
  // MVP resident journey, the answer is immediately followed by the
  // confirm-run gate. No stable observation window between answer and confirm.
  // NOT_SEPARATELY_OBSERVABLE from CONFIRMATION.
  AI_ANSWER: Object.freeze({
    semanticState: "AI_ANSWER",
    surface: "any",
    observable: false,
    equivalentState: "CONFIRMATION",
    reason: "AI answer bubble is transient between split and confirm-run. No stable observation window between answer and confirm in the Buk-gu MVP resident journey. NOT_SEPARATELY_OBSERVABLE.",
    required: [],
    forbidden: [],
    stabilityNotes: "transient — NOT_SEPARATELY_OBSERVABLE from CONFIRMATION",
  }),

  // ── GROUNDING_EVIDENCE ─────────────────────────────────────────────────
  // In the Buk-gu MVP resident journey, grounding evidence (the quest card
  // with official_path/source_mode) appears simultaneously with the
  // confirm-run gate. No separate stable state. NOT_SEPARATELY_OBSERVABLE
  // from CONFIRMATION.
  GROUNDING_EVIDENCE: Object.freeze({
    semanticState: "GROUNDING_EVIDENCE",
    surface: "any",
    observable: false,
    equivalentState: "CONFIRMATION",
    reason: "Quest card with official_path/source_mode appears simultaneously with confirm-run gate. No separate stable state. NOT_SEPARATELY_OBSERVABLE from CONFIRMATION.",
    required: [],
    forbidden: [],
    stabilityNotes: "simultaneous with CONFIRMATION — NOT_SEPARATELY_OBSERVABLE",
  }),

  // ── EXTERNAL_HANDOFF ───────────────────────────────────────────────────
  // In the Buk-gu MVP resident journey, there is no external handoff step
  // (the journey stops at pre-submit). This state is not applicable to the
  // V1 proof scenarios. It exists in the vocabulary for completeness but is
  // NOT_SEPARATELY_OBSERVABLE from PRE_SUBMIT_CONVERSATION in the Buk-gu
  // resident journey (the STOP boundary is the pre-submit confirmation).
  EXTERNAL_HANDOFF: Object.freeze({
    semanticState: "EXTERNAL_HANDOFF",
    surface: "any",
    observable: false,
    equivalentState: "PRE_SUBMIT_CONVERSATION",
    reason: "Buk-gu MVP resident journey has no external handoff step. The STOP boundary is the pre-submit confirmation. NOT_SEPARATELY_OBSERVABLE from PRE_SUBMIT_CONVERSATION.",
    required: [],
    forbidden: [],
    stabilityNotes: "not applicable to V1 Buk-gu proof scenarios — NOT_SEPARATELY_OBSERVABLE",
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

  // ── FINAL_STABLE_STATE ─────────────────────────────────────────────────
  // V1 must NEVER reach data-choreography-state="done" (requires clicking
  // "검토했고, 제출하기" which is forbidden). FINAL_STABLE_STATE aliases the
  // last safely observable pre-submit state. No unique predicate exists
  // beyond PRE_SUBMIT_CONVERSATION. NOT_SEPARATELY_OBSERVABLE.
  FINAL_STABLE_STATE: Object.freeze({
    semanticState: "FINAL_STABLE_STATE",
    surface: "any",
    observable: false,
    equivalentState: "PRE_SUBMIT_CONVERSATION",
    reason: "Reaching choreography=done requires clicking the final confirmation button (검토했고, 제출하기), which is forbidden by #1355 hard boundary. No unique predicate exists beyond PRE_SUBMIT_CONVERSATION. NOT_SEPARATELY_OBSERVABLE — aliases the last safe pre-submit state.",
    required: [],
    forbidden: [],
    stabilityNotes: "not independently observable — aliases PRE_SUBMIT_CONVERSATION",
  }),
});

// ── Non-separable state pairs ─────────────────────────────────────────────
export const NON_SEPARABLE_PAIRS = Object.freeze([
  {
    stateA: "DRAFT_POPULATED",
    stateB: "PRE_SUBMIT_CONVERSATION",
    viewport: "desktop",
    reason: "Same choreography state (waiting_confirmation), same form field values, same button set, same surface (null on desktop). No stable interval between them.",
  },
  {
    stateA: "TRANSITION",
    stateB: "CONFIRMATION",
    viewport: "any",
    reason: "first-use-state=transitioning is a transient cinematic animation with no stable observation window.",
  },
  {
    stateA: "SPLIT_READY",
    stateB: "CONFIRMATION",
    viewport: "any",
    reason: "data-first-use-state=split + confirm-run visible is the same observable state as CONFIRMATION.",
  },
  {
    stateA: "TARGET_ROUTE_READY",
    stateB: "CHOICE",
    viewport: "any",
    reason: "canvas[data-canvas-route] is null at all observed states. No unique predicate distinct from the subsequent choreography state.",
  },
  {
    stateA: "AI_ANSWER",
    stateB: "CONFIRMATION",
    viewport: "any",
    reason: "AI answer bubble is transient between split and confirm-run. No stable observation window.",
  },
  {
    stateA: "GROUNDING_EVIDENCE",
    stateB: "CONFIRMATION",
    viewport: "any",
    reason: "Quest card appears simultaneously with confirm-run gate. No separate stable state.",
  },
  {
    stateA: "EXTERNAL_HANDOFF",
    stateB: "PRE_SUBMIT_CONVERSATION",
    viewport: "any",
    reason: "Buk-gu MVP resident journey has no external handoff step. STOP boundary is pre-submit confirmation.",
  },
  {
    stateA: "FINAL_STABLE_STATE",
    stateB: "PRE_SUBMIT_CONVERSATION",
    viewport: "any",
    reason: "Reaching choreography=done requires forbidden final-confirmation click. No unique predicate beyond PRE_SUBMIT_CONVERSATION.",
  },
]);

// ── FINAL_STABLE_STATE policy ────────────────────────────────────────────
export const FINAL_STABLE_STATE_POLICY = Object.freeze({
  forbiddenClick: "검토했고, 제출하기",
  forbiddenChoreographyState: "done",
  alias: "PRE_SUBMIT_CONVERSATION",
  reason: "Reaching choreography=done requires clicking the final confirmation button, which is forbidden by #1355 hard boundary. V1 aliases FINAL_STABLE_STATE to the last safe pre-submit state.",
});

/**
 * Check if a state is observable (has unique runtime predicates).
 * Returns false for NOT_SEPARATELY_OBSERVABLE states.
 */
export function isObservable(semanticState) {
  const spec = STATES[semanticState];
  if (!spec) return false;
  return spec.observable !== false;
}

/**
 * Get the equivalent/canonical state for a non-observable state.
 * Returns null for observable states.
 */
export function getEquivalentState(semanticState) {
  const spec = STATES[semanticState];
  if (!spec) return null;
  if (spec.observable === false) return spec.equivalentState || null;
  return null;
}

export function getStateSpec(semanticState) {
  return STATES[semanticState] || null;
}

export function getAllStateNames() {
  return Object.keys(STATES);
}

// ── Required V1 semantic vocabulary ─────────────────────────────────────
export const REQUIRED_VOCABULARY = Object.freeze([
  "ENTRY",
  "BEFORE_CLICK",
  "CONFIRMATION",
  "CHOICE",
  "TRANSITION",
  "SPLIT_READY",
  "TARGET_ROUTE_READY",
  "AI_ANSWER",
  "GROUNDING_EVIDENCE",
  "EXTERNAL_HANDOFF",
  "DRAFT_POPULATED",
  "PRE_SUBMIT_CONVERSATION",
  "PRE_SUBMIT_GUIDANCE",
  "FINAL_STABLE_STATE",
  // classifications
  "NOT_SEPARATELY_OBSERVABLE",
  "STATE_MISMATCH",
  "STATE_TIMEOUT",
  "UNSTABLE_STATE",
  "FORBIDDEN_STATE_REACHED",
]);
