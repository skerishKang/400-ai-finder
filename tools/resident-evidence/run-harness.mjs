#!/usr/bin/env node
// tools/resident-evidence/run-harness.mjs
//
// CLI entrypoint for the Resident Journey Evidence Harness V1.
//
// BLOCKER 3 FIX: CLI fails nonzero if an expected positive state is
// unexpectedly rejected. NOT_SEPARATELY_OBSERVABLE is allowed only where
// explicitly declared by the scenario checkpoint `expected` field.
// UNKNOWN_STATE / STATE_MISMATCH for required positive evidence = failure.
//
// Usage:
//   node tools/resident-evidence/run-harness.mjs --base-url http://127.0.0.1:8780

import { chromium } from "playwright";
import { mkdirSync, existsSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { runScenario } from "./src/orchestrator.mjs";
import { STATES, REQUIRED_VOCABULARY } from "./src/state-specs.mjs";
import { streetlightScenario } from "./scenarios/bukgu-streetlight.mjs";
import { litterScenario } from "./scenarios/bukgu-litter.mjs";

const ARTIFACTS_ROOT = resolve("artifacts/resident-evidence");

function parseArgs() {
  const args = process.argv.slice(2);
  let baseUrl = "http://127.0.0.1:8780";
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--base-url" && args[i + 1]) {
      baseUrl = args[i + 1];
      i++;
    }
  }
  return { baseUrl };
}

/**
 * Validate that all required semantic vocabulary entries resolve.
 * BLOCKER 4: required vocabulary must be resolvable, not UNKNOWN_STATE.
 */
function validateVocabulary() {
  const missing = [];
  for (const name of REQUIRED_VOCABULARY) {
    // Classifications are in CAPTURE_STATUS, not STATES
    if (["NOT_SEPARATELY_OBSERVABLE", "STATE_MISMATCH", "STATE_TIMEOUT", "UNSTABLE_STATE", "FORBIDDEN_STATE_REACHED"].includes(name)) {
      continue;
    }
    if (!STATES[name]) {
      missing.push(name);
    }
  }
  return missing;
}

/**
 * Check checkpoint results against expected dispositions.
 * Returns array of violations (empty if all pass).
 */
function checkCheckpointResults(checkpointResults) {
  const violations = [];
  for (const cp of checkpointResults) {
    if (cp.actual === "UNKNOWN_STATE") {
      violations.push({
        state: cp.state,
        expected: cp.expected,
        actual: cp.actual,
        reason: "UNKNOWN_STATE — required state spec is missing",
      });
      continue;
    }
    if (cp.expected === "ACCEPTED" && !cp.accepted) {
      violations.push({
        state: cp.state,
        expected: "ACCEPTED",
        actual: cp.actual,
        reason: `Required positive state was not ACCEPTED (got ${cp.actual})`,
      });
      continue;
    }
    if (cp.expected === "NOT_SEPARATELY_OBSERVABLE" && cp.actual !== "NOT_SEPARATELY_OBSERVABLE") {
      violations.push({
        state: cp.state,
        expected: "NOT_SEPARATELY_OBSERVABLE",
        actual: cp.actual,
        reason: `Expected NOT_SEPARATELY_OBSERVABLE but got ${cp.actual}`,
      });
      continue;
    }
  }
  return violations;
}

/**
 * Exported top-level harness runner — exercises the REAL CLI logic.
 * Returns { hasFailure, results } so tests can verify exit disposition.
 * The CLI main() calls this and exits nonzero on hasFailure.
 *
 * @param {Object} options
 * @param {string} options.baseUrl
 * @param {Array} [options.scenarios] — override scenario list
 * @param {string} [options.artifactsRoot] — override artifacts root
 * @returns {Promise<{hasFailure: boolean, results: Array}>}
 */
export async function runHarness(options = {}) {
  const baseUrl = options.baseUrl || "http://127.0.0.1:8780";
  const scenarios = options.scenarios || [streetlightScenario, litterScenario];
  const artifactsRoot = options.artifactsRoot || ARTIFACTS_ROOT;
  const runId = `run-${Date.now()}`;
  mkdirSync(artifactsRoot, { recursive: true });

  console.log("=== Resident Journey Evidence Harness V1 ===");
  console.log(`Base URL: ${baseUrl}`);
  console.log(`Run ID: ${runId}`);
  console.log(`Artifacts root: ${artifactsRoot}`);

  const missingVocab = validateVocabulary();
  if (missingVocab.length > 0) {
    console.error(`FATAL: Missing required semantic vocabulary: ${missingVocab.join(", ")}`);
    return { hasFailure: true, results: [] };
  }
  console.log(`Vocabulary: ${REQUIRED_VOCABULARY.length} states defined (${Object.keys(STATES).length} in STATES + 5 classifications)`);

  const browser = await chromium.launch({ headless: true });
  const allResults = [];
  let hasFailure = false;

  for (const scenario of scenarios) {
    console.log(`\n--- Scenario: ${scenario.id} ---`);
    try {
      const result = await runScenario({
        browser, scenarioSpec: scenario, stateSpecs: STATES,
        baseUrl, artifactsRoot, runId,
      });
      allResults.push(result);

      console.log(`Manifest: ${result.manifestPath}`);
      console.log(`Entries: ${result.entries.length}`);
      const accepted = result.entries.filter((e) => e.capture_status === "ACCEPTED");
      const rejected = result.entries.filter((e) => e.capture_status !== "ACCEPTED");
      console.log(`Accepted: ${accepted.length}, Rejected: ${rejected.length}`);

      console.log(`Checkpoints:`);
      for (const cp of result.checkpointResults) {
        const status = cp.accepted ? "ACCEPTED" : cp.actual;
        const ok = cp.expected === status || (cp.expected === "NOT_SEPARATELY_OBSERVABLE" && cp.actual === "NOT_SEPARATELY_OBSERVABLE");
        console.log(`  ${ok ? "✓" : "✗"} ${cp.state}: expected=${cp.expected}, actual=${cp.actual}`);
      }

      const violations = checkCheckpointResults(result.checkpointResults);
      if (violations.length > 0) {
        hasFailure = true;
        console.error(`CHECKPOINT VIOLATIONS in ${scenario.id}:`);
        for (const v of violations) { console.error(`  ${v.state}: ${v.reason}`); }
      }

      if (result.safetyCounts.externalOriginRequests > 0) {
        hasFailure = true;
        console.error(`SAFETY VIOLATION: ${result.safetyCounts.externalOriginRequests} external-origin requests detected!`);
      }
    } catch (err) {
      hasFailure = true;
      console.error(`Scenario ${scenario.id} failed: ${err.message}`);
      allResults.push({ scenarioId: scenario.id, error: err.message });
    }
  }

  await browser.close();

  console.log("\n=== Harness Run Complete ===");
  const totalAccepted = allResults.reduce((sum, r) => sum + (r.entries ? r.entries.filter((e) => e.capture_status === "ACCEPTED").length : 0), 0);
  const totalRejected = allResults.reduce((sum, r) => sum + (r.entries ? r.entries.filter((e) => e.capture_status !== "ACCEPTED").length : 0), 0);
  console.log(`Total accepted: ${totalAccepted}, Total rejected: ${totalRejected}`);

  const totalExternal = allResults.reduce((sum, r) => sum + (r.safetyCounts ? r.safetyCounts.externalOriginRequests : 0), 0);
  if (totalExternal > 0) {
    hasFailure = true;
    console.error(`FATAL: ${totalExternal} external-origin requests detected across all scenarios`);
  }

  if (hasFailure) {
    console.error("\nHARNESS FAILED — see violations above");
  } else {
    console.log("\nHARNESS PASSED — all checkpoints met expected dispositions");
  }

  return { hasFailure, results: allResults };
}

async function main() {
  const { baseUrl } = parseArgs();
  const { hasFailure } = await runHarness({ baseUrl });
  if (hasFailure) process.exit(1);
}

main().catch((err) => { console.error(err); process.exit(1); });
