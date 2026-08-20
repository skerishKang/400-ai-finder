/**
 * Pure deterministic Golden state-graph trace validator for #1368.
 *
 * This module defines the canonical Golden resident journey state graph and a
 * deterministic validator that accepts ONLY legal traces and rejects every
 * illegal shortcut. It contains ZERO browser code and ZERO product source —
 * it is a pure semantic contract used by both the unit-level self-contract
 * test and the browser E2E gate.
 *
 * Canonical YES path:
 *
 *   ENTRY → ANSWER → CONFIRM → NAVIGATE → RESULT → STOP
 *
 * Canonical NO path:
 *
 *   ENTRY → ANSWER → CONFIRM → DECISION_NO → STOP
 *
 * Rules (all enforced by validateGoldenTrace):
 *
 *   ENTRY → ANSWER only (never ENTRY → NAVIGATE)
 *   ANSWER → CONFIRM only
 *   CONFIRM → NAVIGATE | DECISION_NO only
 *   DECISION_NO → STOP only
 *   NAVIGATE → RESULT only
 *   RESULT → STOP only (RESULT is never a terminal state)
 *   STOP is the ONLY permitted terminal state
 *   nothing may follow STOP
 *   RESULT without STOP is rejected
 *   duplicate NAVIGATE is rejected
 *   duplicate RESULT is rejected
 *
 * If expectedResult is supplied, RESULT metadata must exist and its value must
 * equal expectedResult. Missing or mismatched metadata fails.
 *
 * Usage:
 *   import { GOLDEN_STATES, validateGoldenTrace, GOLDEN_TRANSITIONS } from
 *     "./golden_state_graph_contract.mjs";
 */

export const GOLDEN_STATES = Object.freeze([
  "ENTRY",
  "ANSWER",
  "CONFIRM",
  "DECISION_NO",
  "NAVIGATE",
  "RESULT",
  "STOP",
]);

// Canonical adjacency: the ONLY legal successor for each state.
export const GOLDEN_TRANSITIONS = Object.freeze({
  ENTRY: ["ANSWER"],
  ANSWER: ["CONFIRM"],
  CONFIRM: ["DECISION_NO", "NAVIGATE"],
  DECISION_NO: ["STOP"],
  NAVIGATE: ["RESULT"],
  RESULT: ["STOP"],
  STOP: [], // terminal — nothing follows
});

/**
 * Validate a single Golden journey trace.
 *
 * @param {Array<{state: string, metadata?: object}>} events - ordered trace.
 * @param {{expectedResult?: string}} [options] - optional expected result.
 * @returns {{valid: boolean, errors: string[], states: string[]}}
 */
export function validateGoldenTrace(events, options) {
  const errors = [];
  const states = [];

  if (!Array.isArray(events)) {
    return { valid: false, errors: ["trace must be an array"], states: [] };
  }

  if (events.length === 0) {
    return { valid: false, errors: ["trace is empty"], states: [] };
  }

  const seenNav = [];
  const seenResult = [];
  let stopped = false;

  for (let i = 0; i < events.length; i++) {
    const ev = events[i];
    const state = ev && ev.state;

    if (stopped) {
      errors.push(`event ${i}: state "${state}" appears after STOP`);
      states.push(state || "(missing)");
      continue;
    }

    if (!GOLDEN_STATES.includes(state)) {
      errors.push(`event ${i}: unknown state "${state}"`);
      states.push(state || "(missing)");
      continue;
    }

    states.push(state);

    // Track duplicate NAVIGATE.
    if (state === "NAVIGATE") {
      seenNav.push(i);
      if (seenNav.length > 1) {
        errors.push(
          `event ${i}: duplicate NAVIGATE (first at event ${seenNav[0]})`,
        );
      }
    }

    // Track duplicate RESULT.
    if (state === "RESULT") {
      seenResult.push(i);
      if (seenResult.length > 1) {
        errors.push(
          `event ${i}: duplicate RESULT (first at event ${seenResult[0]})`,
        );
      }
    }

    // First state must be ENTRY.
    if (i === 0 && state !== "ENTRY") {
      errors.push(`event 0: first state must be ENTRY, got "${state}"`);
    }

    // Check transition legality against the predecessor (if any).
    if (i > 0) {
      const prev = states[i - 1];
      const allowed = GOLDEN_TRANSITIONS[prev] || [];
      if (!allowed.includes(state)) {
        errors.push(
          `event ${i}: illegal transition ${prev} → ${state} (allowed: ${allowed.join(", ") || "none"})`,
        );
      }
    }

    // RESULT metadata check when expectedResult is supplied.
    if (state === "RESULT") {
      const meta = ev && ev.metadata;
      const expectedResult = options && options.expectedResult;
      if (expectedResult !== undefined) {
        if (!meta || typeof meta !== "object") {
          errors.push(
            `event ${i}: RESULT metadata missing but expectedResult supplied`,
          );
        } else if (meta.result !== expectedResult) {
          errors.push(
            `event ${i}: RESULT metadata.result="${meta.result}" != expectedResult="${expectedResult}"`,
          );
        }
      }
    }

    if (state === "STOP") {
      stopped = true;
    }
  }

  // Terminal state must be STOP.
  const lastState = states[states.length - 1];
  if (lastState !== "STOP") {
    errors.push(`terminal state must be STOP, got "${lastState}"`);
  }

  const expectedResult = options && options.expectedResult;

  // RESULT without STOP (if RESULT exists but trace did not reach STOP).
  if (seenResult.length > 0 && !stopped) {
    errors.push("RESULT present but STOP never reached (RESULT without STOP)");
  }

  if (expectedResult !== undefined && seenResult.length === 0) {
    errors.push("expectedResult supplied but trace contains no RESULT event");
  }

  return { valid: errors.length === 0, errors, states };
}
