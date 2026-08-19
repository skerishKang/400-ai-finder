// tools/resident-evidence/src/manifest.mjs
//
// Evidence manifest writer — SHA256 + machine-readable metadata.
// Validates PNG bytes after write. Manifest SHA256 must match actual file bytes.
//
// Never serializes secrets, cookies, auth tokens, or PII.

import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, existsSync, statSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { collectSnapshot } from "./runtime-observer.mjs";

export const MANIFEST_SCHEMA_VERSION = "1.0.0";

/**
 * Compute SHA256 of file bytes.
 * @param {string} filePath
 * @returns {string} hex digest
 */
export function computeFileSha256(filePath) {
  const bytes = readFileSync(filePath);
  return createHash("sha256").update(bytes).digest("hex");
}

/**
 * Validate that a file is a well-formed PNG by checking the signature and
 * reading width/height from the IHDR chunk using only Node core.
 * PNG signature: 89 50 4E 47 0D 0A 1A 0A
 * IHDR starts at byte 8, is 13 bytes of data: width(4) + height(4) + ...
 * @param {string} filePath
 * @returns {{valid: boolean, bytes: number, width: number, height: number, sha256: string, reason?: string}}
 */
export function validatePngFile(filePath) {
  if (!existsSync(filePath)) {
    return { valid: false, bytes: 0, width: 0, height: 0, sha256: "", reason: "file does not exist" };
  }

  const buf = readFileSync(filePath);
  const stats = statSync(filePath);
  const sha256 = createHash("sha256").update(buf).digest("hex");

  if (buf.length < 24) {
    return { valid: false, bytes: stats.size, width: 0, height: 0, sha256, reason: "file too small to be a valid PNG" };
  }

  // PNG signature
  const PNG_SIG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  if (buf.compare(PNG_SIG, 0, 8, 0, 8) !== 0) {
    return { valid: false, bytes: stats.size, width: 0, height: 0, sha256, reason: "invalid PNG signature" };
  }

  // IHDR chunk: starts at offset 8
  // Length (4 bytes big-endian) = 13 for IHDR
  // Type (4 bytes) = "IHDR"
  // Width (4 bytes big-endian)
  // Height (4 bytes big-endian)
  const chunkLength = buf.readUInt32BE(8);
  const chunkType = buf.toString("ascii", 12, 16);
  if (chunkType !== "IHDR" || chunkLength < 13) {
    return { valid: false, bytes: stats.size, width: 0, height: 0, sha256, reason: "missing or invalid IHDR chunk" };
  }

  const width = buf.readUInt32BE(16);
  const height = buf.readUInt32BE(20);

  return { valid: true, bytes: stats.size, width, height, sha256 };
}

/**
 * Build a manifest entry for an accepted capture.
 *
 * @param {Object} params
 * @param {string} params.scenarioId
 * @param {string} params.semanticState
 * @param {string} [params.equivalentState]
 * @param {string} params.product
 * @param {{width: number, height: number}} params.viewport
 * @param {string} params.url
 * @param {string} params.filename
 * @param {string} params.filePath
 * @param {Object} params.runtimeSnapshot
 * @param {Array} params.requiredResults
 * @param {Array} params.forbiddenResults
 * @param {Object} params.safetyCounts
 * @param {string} params.captureStatus
 * @returns {Object} manifest entry
 */
export function buildManifestEntry(params) {
  const png = validatePngFile(params.filePath);
  const { scenarioId, semanticState, equivalentState, product, viewport, url, filename, runtimeSnapshot, requiredResults, forbiddenResults, safetyCounts, captureStatus } = params;

  const requiredPassed = requiredResults.filter((r) => r.passed).length;
  const forbiddenAbsent = forbiddenResults.filter((r) => r.passed).length;

  return {
    schema_version: MANIFEST_SCHEMA_VERSION,
    scenario_id: scenarioId,
    semantic_state: semanticState,
    equivalent_state: equivalentState || null,
    product,
    viewport,
    url,
    timestamp: new Date().toISOString(),
    filename,
    bytes: png.bytes,
    sha256: png.sha256,
    width: png.width,
    height: png.height,
    png_valid: png.valid,
    first_use_state: runtimeSnapshot.attributes.firstUseState,
    journey_state: runtimeSnapshot.attributes.journeyState,
    choreography_state: runtimeSnapshot.attributes.choreographyState,
    active_surface: runtimeSnapshot.attributes.mobileSurface,
    visible_route: null,
    quest_id: runtimeSnapshot.attributes.questId,
    required_predicates_passed: requiredPassed,
    forbidden_predicates_absent: forbiddenAbsent,
    external_origin_request_count: safetyCounts.externalOriginRequests,
    failed_request_count: safetyCounts.failedRequests,
    console_error_count: safetyCounts.consoleErrors,
    page_error_count: safetyCounts.pageErrors,
    capture_status: captureStatus,
  };
}

/**
 * Build a manifest entry for a rejected/diagnostic capture.
 * Does NOT include a valid PNG entry in the accepted set.
 *
 * @param {Object} params
 * @returns {Object} diagnostic manifest entry
 */
export function buildDiagnosticEntry(params) {
  const { scenarioId, semanticState, requestedState, product, viewport, url, runtimeSnapshot, requiredResults, forbiddenResults, stabilityResult, safetyCounts, captureStatus, reason } = params;

  return {
    schema_version: MANIFEST_SCHEMA_VERSION,
    scenario_id: scenarioId,
    requested_state: requestedState || semanticState,
    actual_choreography_state: runtimeSnapshot.attributes.choreographyState,
    actual_mobile_surface: runtimeSnapshot.attributes.mobileSurface,
    product,
    viewport,
    url,
    timestamp: new Date().toISOString(),
    classification: captureStatus,
    reason,
    first_use_state: runtimeSnapshot.attributes.firstUseState,
    journey_state: runtimeSnapshot.attributes.journeyState,
    choreography_state: runtimeSnapshot.attributes.choreographyState,
    active_surface: runtimeSnapshot.attributes.mobileSurface,
    quest_id: runtimeSnapshot.attributes.questId,
    required_predicates_passed: requiredResults ? requiredResults.filter((r) => r.passed).length : 0,
    forbidden_predicates_absent: forbiddenResults ? forbiddenResults.filter((r) => r.passed).length : 0,
    stability_classification: stabilityResult ? stabilityResult.classification : null,
    external_origin_request_count: safetyCounts.externalOriginRequests,
    failed_request_count: safetyCounts.failedRequests,
    console_error_count: safetyCounts.consoleErrors,
    page_error_count: safetyCounts.pageErrors,
    capture_status: captureStatus,
  };
}

/**
 * Write the evidence manifest to disk.
 *
 * @param {string} manifestDir — directory for manifest
 * @param {string} runId — unique run identifier
 * @param {Array} entries — accepted + diagnostic entries
 */
export function writeManifest(manifestDir, runId, entries) {
  mkdirSync(manifestDir, { recursive: true });
  const manifestPath = join(manifestDir, "evidence-manifest.json");
  const manifest = {
    schema_version: MANIFEST_SCHEMA_VERSION,
    run_id: runId,
    generated_at: new Date().toISOString(),
    entry_count: entries.length,
    accepted_count: entries.filter((e) => e.capture_status === "ACCEPTED").length,
    rejected_count: entries.filter((e) => e.capture_status !== "ACCEPTED").length,
    entries,
  };
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n", "utf8");
  return manifestPath;
}
