// tools/resident-evidence/src/orchestrator.mjs
//
// Scenario orchestrator — drives the resident journey to a target state,
// evaluates the semantic state spec, and coordinates capture.
//
// The orchestrator is GENERIC: it evaluates state specs from state-specs.mjs
// and drives scenario steps from scenario spec files. No Streetlight/Litter
// hard-coded logic lives here.

import { evaluateCaptureEligibility, captureScreenshot, CAPTURE_STATUS } from "./capture.mjs";
import { collectSnapshot } from "./runtime-observer.mjs";
import { attachSafetyObserver, assertZeroExternalRequests } from "./safety-observer.mjs";
import { buildManifestEntry, buildDiagnosticEntry, writeManifest } from "./manifest.mjs";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

/**
 * Poll until a predicate function returns true or timeout.
 * @param {import('playwright').Page} page
 * @param {() => Promise<boolean>} fn
 * @param {{timeoutMs?: number, label?: string}} opts
 */
export async function pollUntil(page, fn, opts = {}) {
  const { timeoutMs = 20000, label = "unnamed" } = opts;
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const result = await fn();
    if (result) return result;
    await page.waitForTimeout(50);
  }
  throw new Error(`pollUntil timeout: ${label} (${timeoutMs}ms)`);
}

/**
 * Build a deterministic mock API response for a question.
 * This is the test-tool-side mock, not a production change.
 * @param {string} question
 * @param {Object} config — scenario config with question-to-action mapping
 */
export function buildMockResponse(question, config) {
  const action = config.action || "none";
  const journeyId = config.journeyId || action;
  return {
    ok: true,
    question,
    answer: config.answer || "안내해 드립니다.",
    action,
    confidence: 1,
    provider: "canonical_e2e_fixture",
    model: "none",
    failure_code: "",
    journey_id: journeyId,
    quest: {
      quest_id: journeyId,
      quest_name: config.question,
      official_path: "민원게시판 > 글쓰기",
      browser_actions: [],
      result: { stop: "사용자 확인 후 공식 채널에서 직접 진행" },
      source_mode: "local_static",
      stop_condition: "STOP_FOR_USER_CONFIRMATION",
      final_warning: "실제 제출은 북구청 공식 채널에서 직접 진행해 주세요.",
      client_action: action,
    },
    action_plan: { client_action: action },
    fallback_used: false,
  };
}

/**
 * Switch the mobile surface to conversation.
 * @param {import('playwright').Page} page
 */
export async function switchToConversation(page) {
  const surface = await page.getAttribute("body", "data-mobile-surface");
  if (surface === "guidance") {
    await page.evaluate(() => {
      const tab = document.getElementById("tab-conversation");
      if (tab) tab.click();
    });
    await pollUntil(page, async () => {
      return (await page.getAttribute("body", "data-mobile-surface")) === "conversation";
    }, { label: "switch to conversation", timeoutMs: 5000 });
  }
}

/**
 * Switch the mobile surface to guidance.
 * @param {import('playwright').Page} page
 */
export async function switchToGuidance(page) {
  const surface = await page.getAttribute("body", "data-mobile-surface");
  if (surface !== "guidance") {
    await page.evaluate(() => {
      const tab = document.getElementById("tab-guidance");
      if (tab) tab.click();
    });
    await pollUntil(page, async () => {
      return (await page.getAttribute("body", "data-mobile-surface")) === "guidance";
    }, { label: "switch to guidance", timeoutMs: 5000 });
  }
}

/**
 * Drive a scenario to a target state and attempt evidence capture.
 *
 * @param {Object} params
 * @param {import('playwright').Page} params.page
 * @param {Object} params.scenarioSpec — from scenario file
 * @param {string} params.targetState — semantic state name
 * @param {Object} params.stateSpec — from state-specs.mjs
 * @param {Object} params.safetyObserver
 * @param {string} params.acceptedDir
 * @param {string} params.diagnosticDir
 * @param {Object} [params.stabilityConfig]
 * @returns {Promise<Object>} capture result
 */
export async function captureEvidence(params) {
  const { page, scenarioSpec, targetState, stateSpec, safetyObserver, acceptedDir, diagnosticDir, stabilityConfig } = params;

  mkdirSync(acceptedDir, { recursive: true });
  mkdirSync(diagnosticDir, { recursive: true });

  const eligibility = await evaluateCaptureEligibility(page, stateSpec, stabilityConfig);
  const snapshot = await collectSnapshot(page);
  const safetyCounts = safetyObserver.getCounts();
  const filename = `${scenarioSpec.id}_${targetState}.png`;

  if (eligibility.eligible) {
    // ACCEPTED: write to accepted dir
    const filePath = join(acceptedDir, filename);
    const screenshotResult = await captureScreenshot(page, filePath);
    const entry = buildManifestEntry({
      scenarioId: scenarioSpec.id,
      semanticState: targetState,
      equivalentState: stateSpec.equivalentState,
      product: scenarioSpec.product,
      viewport: scenarioSpec.viewport,
      url: snapshot.url,
      filename,
      filePath,
      runtimeSnapshot: snapshot,
      requiredResults: eligibility.requiredResults,
      forbiddenResults: eligibility.forbiddenResults,
      safetyCounts,
      captureStatus: CAPTURE_STATUS.ACCEPTED,
    });
    return { accepted: true, entry, screenshotResult, eligibility, snapshot };
  }

  // REJECTED: write diagnostic only (never to accepted)
  const diagPath = join(diagnosticDir, filename);
  const failedReasons = [
    ...eligibility.requiredResults.filter((r) => !r.passed).map((r) => `FAIL:${r.name}:${r.detail}`),
    ...eligibility.forbiddenResults.filter((r) => !r.passed).map((r) => `FORBIDDEN:${r.name}:${r.detail}`),
  ].join("; ");

  // Diagnostic screenshot (optional, clearly separated)
  let diagResult = null;
  try {
    diagResult = await captureScreenshot(page, diagPath);
  } catch {
    // Diagnostic screenshot is best-effort
  }

  const diagEntry = buildDiagnosticEntry({
    scenarioId: scenarioSpec.id,
    semanticState: targetState,
    requestedState: targetState,
    product: scenarioSpec.product,
    viewport: scenarioSpec.viewport,
    url: snapshot.url,
    runtimeSnapshot: snapshot,
    requiredResults: eligibility.requiredResults,
    forbiddenResults: eligibility.forbiddenResults,
    stabilityResult: eligibility.stabilityResult,
    safetyCounts,
    captureStatus: eligibility.status,
    reason: failedReasons || eligibility.status,
  });

  return { accepted: false, entry: diagEntry, eligibility, snapshot };
}

/**
 * Run a full scenario with multiple state captures.
 *
 * @param {Object} params
 * @param {import('playwright').Browser} params.browser
 * @param {Object} params.scenarioSpec — scenario definition with steps
 * @param {Object} params.stateSpecs — map of state name to spec
 * @param {string} params.baseUrl
 * @param {string} params.artifactsRoot
 * @param {string} params.runId
 * @param {Object} [params.stabilityConfig]
 * @returns {Promise<Object>} full run result with all manifest entries
 */
export async function runScenario(params) {
  const { browser, scenarioSpec, stateSpecs, baseUrl, artifactsRoot, runId, stabilityConfig } = params;

  const runDir = join(artifactsRoot, runId, scenarioSpec.id);
  const acceptedDir = join(runDir, "screenshots");
  const diagnosticDir = join(runDir, "diagnostics");
  const manifestDir = join(runDir);
  mkdirSync(runDir, { recursive: true });

  const context = await browser.newContext({
    viewport: scenarioSpec.viewport,
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const safetyObserver = attachSafetyObserver(page);

  // Set up deterministic API mock
  await page.route("**/api/mvp/ask", async (route) => {
    const payload = JSON.parse(route.request().postData() || "{}");
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(buildMockResponse(payload.question || "", scenarioSpec)),
    });
  });

  const entries = [];

  try {
    // Navigate to MVP entry
    await page.goto(`${baseUrl}/mvp/index.html`, { waitUntil: "networkidle", timeout: 15000 });
    await pollUntil(
      page,
      async () => (await page.getAttribute("body", "data-first-use-state")) === "entry",
      { label: "entry state", timeoutMs: 8000 },
    );

    // Execute scenario steps
    for (const step of scenarioSpec.steps) {
      await step(page);
    }

    // Attempt capture for each requested state
    for (const targetState of scenarioSpec.captureStates) {
      const stateSpec = stateSpecs[targetState];
      if (!stateSpec) {
        entries.push({
          schema_version: "1.0.0",
          scenario_id: scenarioSpec.id,
          requested_state: targetState,
          capture_status: "UNKNOWN_STATE",
          reason: `No state spec defined for ${targetState}`,
        });
        continue;
      }

      const result = await captureEvidence({
        page,
        scenarioSpec,
        targetState,
        stateSpec,
        safetyObserver,
        acceptedDir,
        diagnosticDir,
        stabilityConfig,
      });
      entries.push(result.entry);
    }
  } finally {
    safetyObserver.detach();
    await context.close();
  }

  const manifestPath = writeManifest(manifestDir, runId, entries);
  const safetyCounts = safetyObserver.getCounts();

  return {
    scenarioId: scenarioSpec.id,
    entries,
    manifestPath,
    safetyCounts,
  };
}
