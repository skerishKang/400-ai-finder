#!/usr/bin/env node
// tools/resident-evidence/run-harness.mjs
//
// CLI entrypoint for the Resident Journey Evidence Harness V1.
//
// Usage:
//   node tools/resident-evidence/run-harness.mjs --base-url http://127.0.0.1:8780
//
// Requires a local server serving dist/cloudflare-pages (live build).

import { chromium } from "playwright";
import { mkdirSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { runScenario } from "./src/orchestrator.mjs";
import { STATES } from "./src/state-specs.mjs";
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

async function main() {
  const { baseUrl } = parseArgs();
  const runId = `run-${Date.now()}`;
  mkdirSync(ARTIFACTS_ROOT, { recursive: true });

  console.log("=== Resident Journey Evidence Harness V1 ===");
  console.log(`Base URL: ${baseUrl}`);
  console.log(`Run ID: ${runId}`);
  console.log(`Artifacts root: ${ARTIFACTS_ROOT}`);
  console.log();

  const browser = await chromium.launch({ headless: true });

  const scenarios = [streetlightScenario, litterScenario];
  const allResults = [];

  for (const scenario of scenarios) {
    console.log(`\n--- Scenario: ${scenario.id} ---`);
    try {
      const result = await runScenario({
        browser,
        scenarioSpec: scenario,
        stateSpecs: STATES,
        baseUrl,
        artifactsRoot: ARTIFACTS_ROOT,
        runId,
      });
      allResults.push(result);

      console.log(`Manifest: ${result.manifestPath}`);
      console.log(`Entries: ${result.entries.length}`);
      const accepted = result.entries.filter((e) => e.capture_status === "ACCEPTED");
      const rejected = result.entries.filter((e) => e.capture_status !== "ACCEPTED");
      console.log(`Accepted: ${accepted.length}, Rejected: ${rejected.length}`);
      if (result.safetyCounts.externalOriginRequests > 0) {
        console.error(`SAFETY VIOLATION: ${result.safetyCounts.externalOriginRequests} external requests detected!`);
      }
    } catch (err) {
      console.error(`Scenario ${scenario.id} failed: ${err.message}`);
      allResults.push({ scenarioId: scenario.id, error: err.message });
    }
  }

  await browser.close();

  console.log("\n=== Harness Run Complete ===");
  console.log(`Scenarios: ${allResults.length}`);
  const totalAccepted = allResults.reduce((sum, r) => sum + (r.entries ? r.entries.filter((e) => e.capture_status === "ACCEPTED").length : 0), 0);
  const totalRejected = allResults.reduce((sum, r) => sum + (r.entries ? r.entries.filter((e) => e.capture_status !== "ACCEPTED").length : 0), 0);
  console.log(`Total accepted: ${totalAccepted}`);
  console.log(`Total rejected: ${totalRejected}`);

  // Safety check
  const totalExternal = allResults.reduce((sum, r) => sum + (r.safetyCounts ? r.safetyCounts.externalOriginRequests : 0), 0);
  if (totalExternal > 0) {
    console.error(`FATAL: ${totalExternal} external-origin requests detected across all scenarios`);
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
