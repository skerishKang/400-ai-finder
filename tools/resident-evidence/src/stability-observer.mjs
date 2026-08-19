// tools/resident-evidence/src/stability-observer.mjs
//
// Bounded deterministic stability observer.
// Does NOT use arbitrary fixed sleep as the truth oracle.
// Does NOT use .executor-typing or .executor-highlight as stability signals
// (proven unreliable — they persist after typing completes).
//
// A state is accepted as stable only after N consecutive samples prove:
//   - semantic state attributes unchanged
//   - required predicates remain true
//   - relevant element visibility unchanged
//   - relevant text/value unchanged
//   - relevant geometry stable within tolerance
//
// Classifications remain distinct:
//   STABLE — state is stable and ready for capture
//   UNSTABLE_STATE — state changed between samples within the window
//   STATE_TIMEOUT — could not reach stability within maxWaitMs

import { collectStabilitySignature } from "./runtime-observer.mjs";

/**
 * Default stability configuration.
 */
export const DEFAULT_STABILITY_CONFIG = Object.freeze({
  sampleCount: 3, // minimum consecutive identical samples
  intervalMs: 100, // polling interval between samples
  maxWaitMs: 20000, // maximum time to wait for stability
  geometryTolerance: 2, // pixels of tolerance for bounding box comparison
});

/**
 * Compare two stability signatures for equality.
 * Geometry is compared within a tolerance.
 * @param {Object} a — first signature
 * @param {Object} b — second signature
 * @param {number} tolerance — pixel tolerance for bounding boxes
 * @returns {{equal: boolean, diff: string[]}}
 */
export function signaturesEqual(a, b, tolerance = 2) {
  const diffs = [];
  const scalarKeys = ["choreo", "journey", "firstUse", "mobileSurface", "questId", "titleValue", "contentValue", "titleVisible", "contentVisible", "decisionPrimaryText", "decisionPrimaryVisible", "chatThreadVisible"];

  for (const key of scalarKeys) {
    if (a[key] !== b[key]) {
      diffs.push(`${key}: ${JSON.stringify(a[key])} → ${JSON.stringify(b[key])}`);
    }
  }

  // Bounding box comparison with tolerance
  for (const bboxKey of ["titleBbox", "contentBbox"]) {
    const av = a[bboxKey];
    const bv = b[bboxKey];
    if (av === null && bv === null) continue;
    if (av === null || bv === null) {
      diffs.push(`${bboxKey}: ${JSON.stringify(av)} → ${JSON.stringify(bv)}`);
      continue;
    }
    const [ax, ay, aw, ah] = av.split(",").map(Number);
    const [bx, by, bw, bh] = bv.split(",").map(Number);
    if (Math.abs(ax - bx) > tolerance || Math.abs(ay - by) > tolerance || Math.abs(aw - bw) > tolerance || Math.abs(ah - bh) > tolerance) {
      diffs.push(`${bboxKey}: ${av} → ${bv}`);
    }
  }

  return { equal: diffs.length === 0, diff: diffs };
}

/**
 * Wait for stability using bounded polling.
 * Takes at least `sampleCount` consecutive identical signatures.
 *
 * @param {import('playwright').Page} page
 * @param {Object} [config] — stability configuration overrides
 * @returns {Promise<{classification: string, samples: Object[], durationMs: number, lastDiff: string[]}>}
 */
export async function waitForStability(page, config = {}) {
  const cfg = { ...DEFAULT_STABILITY_CONFIG, ...config };
  const startTime = Date.now();
  const samples = [];
  let consecutiveEqual = 0;
  let lastDiff = [];

  while (Date.now() - startTime < cfg.maxWaitMs) {
    const sig = await collectStabilitySignature(page);
    samples.push(sig);

    if (samples.length >= 2) {
      const prev = samples[samples.length - 2];
      const cmp = signaturesEqual(prev, sig, cfg.geometryTolerance);
      if (cmp.equal) {
        consecutiveEqual++;
        lastDiff = [];
      } else {
        consecutiveEqual = 0;
        lastDiff = cmp.diff;
      }
    } else {
      // First sample — count it
      consecutiveEqual++;
    }

    if (consecutiveEqual >= cfg.sampleCount) {
      return {
        classification: "STABLE",
        samples,
        durationMs: Date.now() - startTime,
        lastDiff: [],
      };
    }

    await page.waitForTimeout(cfg.intervalMs);
  }

  return {
    classification: consecutiveEqual > 0 ? "UNSTABLE_STATE" : "STATE_TIMEOUT",
    samples,
    durationMs: Date.now() - startTime,
    lastDiff,
  };
}
