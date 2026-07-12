// scripts/merge_comparison_evidence.mjs
//
// Merges partial evidence JSON files (from --attempt-range shards) into one
// combined evidence file with correctly recalculated aggregate.
//
// Usage:
//   node scripts/merge_comparison_evidence.mjs \\
//     --inputs /tmp/ev-attempt-1.json,/tmp/ev-attempt-2.json,/tmp/ev-attempt-3.json \\
//     --output docs/artifacts/1109-stage3-comparison/comparison-evidence.json

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname } from "node:path";

function loadJson(path) {
  return JSON.parse(readFileSync(path, "utf-8"));
}

function median(arr) {
  if (!arr.length) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  const m = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[m] : (sorted[m - 1] + sorted[m]) / 2;
}

function parseArgs() {
  const args = {};
  for (let i = 2; i < process.argv.length; i++) {
    const arg = process.argv[i];
    if (arg === "--inputs" && i + 1 < process.argv.length) {
      args.inputs = process.argv[++i].split(",").map(s => s.trim()).filter(Boolean);
    } else if (arg === "--output" && i + 1 < process.argv.length) {
      args.output = process.argv[++i];
    }
  }
  if (!args.inputs || args.inputs.length < 2) {
    throw new Error("--inputs requires at least 2 comma-separated file paths");
  }
  if (!args.output) throw new Error("--output is required");
  return args;
}

function main() {
  const args = parseArgs();

  console.log(`Merging ${args.inputs.length} evidence files...`);

  // Load all partial evidence files
  const parts = args.inputs.map((p, i) => {
    const data = loadJson(p);
    console.log(`  [${i + 1}] ${p}: ${data.primary_runs.length} primary runs, ${data.boundary_probes.length} boundary probes`);
    return data;
  });

  // Validate all inputs share the same schema_version
  const versions = parts.map(p => p.schema_version).filter(Boolean);
  const uniqueVersions = new Set(versions);
  if (uniqueVersions.size > 1) {
    throw new Error(`Schema version mismatch: ${[...uniqueVersions].join(", ")}`);
  }

  // Use the first file's metadata as the base
  const base = { ...parts[0] };

  // Merge primary_runs (all shards combined)
  base.primary_runs = [];
  for (const p of parts) {
    base.primary_runs.push(...p.primary_runs);
  }

  // Use boundary_probes from the first shard only (all shards run the same probes)
  base.boundary_probes = parts[0].boundary_probes || [];

  // Update methodology
  base.generated_at = new Date().toISOString();
  if (base.methodology) {
    base.methodology = {
      ...base.methodology,
      total_primary_runs: base.primary_runs.length,
      merge_info: {
        input_files: args.inputs,
        shard_count: args.inputs.length,
        merged_at: base.generated_at,
      },
    };
  }

  // Recalculate aggregate from all merged runs
  const allRecords = base.primary_runs;
  const successRuns = allRecords.filter(r => r.success);
  const failRuns = allRecords.filter(r => !r.success);
  const detRuns = allRecords.filter(r => r.mode === "deterministic");
  const paRuns = allRecords.filter(r => r.mode === "page_agent");

  const elapsedDet = detRuns.filter(r => r.success).map(r => r.elapsed_ms).sort((a, b) => a - b);
  const elapsedPa = paRuns.filter(r => r.success).map(r => r.elapsed_ms).sort((a, b) => a - b);

  // Reproducibility: group by (scenario_id, mode)
  const groups = {};
  for (const r of allRecords) {
    const key = `${r.scenario_id}|${r.mode}`;
    if (!groups[key]) groups[key] = [];
    groups[key].push(r);
  }
  const reproducibilityDetails = Object.values(groups).map(grouped => {
    const sigs = grouped.map(r => r.reproducibility_signature);
    const unique = new Set(sigs);
    return {
      scenario_id: grouped[0].scenario_id,
      mode: grouped[0].mode,
      run_count: grouped.length,
      unique_signatures: unique.size,
      reproducible: unique.size === 1,
      signatures: [...unique],
    };
  });

  base.aggregate = {
    total_runs: allRecords.length,
    successful: successRuns.length,
    failed: failRuns.length,
    success_rate: allRecords.length > 0 ? (successRuns.length / allRecords.length) : 0,
    by_mode: {
      deterministic: {
        total: detRuns.length,
        successful: detRuns.filter(r => r.success).length,
        failed: detRuns.filter(r => !r.success).length,
        median_elapsed_ms: median(elapsedDet),
        min_elapsed_ms: elapsedDet.length > 0 ? elapsedDet[0] : 0,
        max_elapsed_ms: elapsedDet.length > 0 ? elapsedDet[elapsedDet.length - 1] : 0,
        median_action_step_count: median(detRuns.filter(r => r.success).map(r => r.action_step_count)),
        total_wrong_route_actions: detRuns.reduce((s, r) => s + r.wrong_route_action_count, 0),
      },
      page_agent: {
        total: paRuns.length,
        successful: paRuns.filter(r => r.success).length,
        failed: paRuns.filter(r => !r.success).length,
        median_elapsed_ms: median(elapsedPa),
        min_elapsed_ms: elapsedPa.length > 0 ? elapsedPa[0] : 0,
        max_elapsed_ms: elapsedPa.length > 0 ? elapsedPa[elapsedPa.length - 1] : 0,
        median_action_step_count: median(paRuns.filter(r => r.success).map(r => r.action_step_count)),
        total_wrong_route_actions: paRuns.reduce((s, r) => s + r.wrong_route_action_count, 0),
      },
    },
    reproducibility: reproducibilityDetails.every(d => d.reproducible),
    reproducibility_details: reproducibilityDetails,
  };

  // Ensure output directory exists
  const outputDir = dirname(args.output);
  if (!existsSync(outputDir)) mkdirSync(outputDir, { recursive: true });

  // Write merged evidence
  writeFileSync(args.output, JSON.stringify(base, null, 2), "utf-8");
  console.log(`\n  ✓ Merged evidence written: ${args.output}`);
  console.log(`  Total primary runs: ${base.primary_runs.length}`);
  console.log(`  Successful: ${successRuns.length}, Failed: ${failRuns.length}`);
  console.log(`  Success rate: ${(base.aggregate.success_rate * 100).toFixed(1)}%`);
}

main();
