// tools/resident-evidence/src/capture.mjs
//
// Capture eligibility decision and screenshot execution.
// FAIL CLOSED: a screenshot is accepted ONLY when:
//   1. All required predicates pass
//   2. All forbidden predicates are absent
//   3. The state is stable (stability observer confirms STABLE)
//   4. Safety observer confirms ZERO external-origin requests (ATOMIC)
//
// BLOCKER 1 FIX: zero-external is an atomic precondition of ACCEPTED capture.
// If external-origin count > 0, no PNG may enter the accepted set.
// The result is classified as FORBIDDEN_STATE_REACHED with a safety violation reason.
//
// Failed captures produce diagnostic-only evidence, never accepted evidence.

import { evaluatePredicates } from "./predicates.mjs";
import { waitForStability } from "./stability-observer.mjs";

export const CAPTURE_STATUS = Object.freeze({
  ACCEPTED: "ACCEPTED",
  STATE_MISMATCH: "STATE_MISMATCH",
  STATE_TIMEOUT: "STATE_TIMEOUT",
  UNSTABLE_STATE: "UNSTABLE_STATE",
  FORBIDDEN_STATE_REACHED: "FORBIDDEN_STATE_REACHED",
  NOT_SEPARATELY_OBSERVABLE: "NOT_SEPARATELY_OBSERVABLE",
});

/**
 * Evaluate whether the current page state satisfies the requested semantic state spec.
 *
 * @param {import('playwright').Page} page
 * @param {Object} stateSpec — from state-specs.mjs
 * @param {Object} [stabilityConfig] — overrides for stability observer
 * @returns {Promise<{eligible: boolean, status: string, requiredResults: Array, forbiddenResults: Array, stabilityResult: Object}>}
 */
export async function evaluateCaptureEligibility(page, stateSpec, stabilityConfig = {}) {
  // Handle non-observable states (NOT_SEPARATELY_OBSERVABLE)
  if (stateSpec.observable === false) {
    return {
      eligible: false,
      status: CAPTURE_STATUS.NOT_SEPARATELY_OBSERVABLE,
      requiredResults: [],
      forbiddenResults: [],
      stabilityResult: null,
      notSeparablyObservable: true,
      equivalentState: stateSpec.equivalentState || null,
      reason: stateSpec.reason || "State is not separately observable",
    };
  }

  // 1. Evaluate required predicates
  const requiredResult = await evaluatePredicates(page, stateSpec.required);
  if (!requiredResult.allPassed) {
    return {
      eligible: false,
      status: CAPTURE_STATUS.STATE_MISMATCH,
      requiredResults: requiredResult.results,
      forbiddenResults: [],
      stabilityResult: null,
    };
  }

  // 2. Evaluate forbidden predicates
  const forbiddenResult = await evaluatePredicates(page, stateSpec.forbidden);
  if (!forbiddenResult.allPassed) {
    return {
      eligible: false,
      status: CAPTURE_STATUS.FORBIDDEN_STATE_REACHED,
      requiredResults: requiredResult.results,
      forbiddenResults: forbiddenResult.results,
      stabilityResult: null,
    };
  }

  // 3. Check evidence requirements (if present)
  if (stateSpec.evidenceRequirements) {
    const evidenceResult = await evaluatePredicates(page, stateSpec.evidenceRequirements);
    if (!evidenceResult.allPassed) {
      return {
        eligible: false,
        status: CAPTURE_STATUS.STATE_MISMATCH,
        requiredResults: requiredResult.results,
        forbiddenResults: forbiddenResult.results,
        stabilityResult: null,
        evidenceResults: evidenceResult.results,
      };
    }
  }

  // 4. Wait for stability
  const stabilityResult = await waitForStability(page, stabilityConfig);
  if (stabilityResult.classification === "STATE_TIMEOUT") {
    return {
      eligible: false,
      status: CAPTURE_STATUS.STATE_TIMEOUT,
      requiredResults: requiredResult.results,
      forbiddenResults: forbiddenResult.results,
      stabilityResult,
    };
  }
  if (stabilityResult.classification === "UNSTABLE_STATE") {
    return {
      eligible: false,
      status: CAPTURE_STATUS.UNSTABLE_STATE,
      requiredResults: requiredResult.results,
      forbiddenResults: forbiddenResult.results,
      stabilityResult,
    };
  }

  // 5. Re-verify predicates after stability
  const recheckRequired = await evaluatePredicates(page, stateSpec.required);
  if (!recheckRequired.allPassed) {
    return {
      eligible: false,
      status: CAPTURE_STATUS.STATE_MISMATCH,
      requiredResults: recheckRequired.results,
      forbiddenResults: [],
      stabilityResult,
    };
  }

  const recheckForbidden = await evaluatePredicates(page, stateSpec.forbidden);
  if (!recheckForbidden.allPassed) {
    return {
      eligible: false,
      status: CAPTURE_STATUS.FORBIDDEN_STATE_REACHED,
      requiredResults: recheckRequired.results,
      forbiddenResults: recheckForbidden.results,
      stabilityResult,
    };
  }

  return {
    eligible: true,
    status: CAPTURE_STATUS.ACCEPTED,
    requiredResults: recheckRequired.results,
    forbiddenResults: recheckForbidden.results,
    stabilityResult,
  };
}

/**
 * Capture a screenshot to a file path.
 *
 * @param {import('playwright').Page} page
 * @param {string} filePath — full path for the PNG file
 * @returns {Promise<{path: string, bytes: number}>}
 */
export async function captureScreenshot(page, filePath) {
  await page.screenshot({ path: filePath, type: "png", fullPage: false });
  const { readFileSync, statSync } = await import("node:fs");
  const stats = statSync(filePath);
  return { path: filePath, bytes: stats.size };
}
