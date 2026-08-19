// tools/resident-evidence/src/orchestrator.mjs
//
// Scenario orchestrator — drives the resident journey through checkpoints,
// evaluating the semantic state spec and capturing evidence AT THE ACTUAL
// STATE TIME, not after all scenario steps finish.
//
// BLOCKER 1 FIX: zero-external is an atomic precondition of ACCEPTED capture.
// If external-origin count > 0, no PNG may enter the accepted set.
// BLOCKER 2 FIX: scenario spec defines checkpoints (step + capture interleaved).
// BLOCKER 3 FIX: runScenario returns expected vs actual disposition for each
// checkpoint. CLI enforces required positive states must be ACCEPTED.

import { evaluateCaptureEligibility, captureScreenshot, CAPTURE_STATUS } from "./capture.mjs";
import { collectSnapshot } from "./runtime-observer.mjs";
import { attachSafetyObserver } from "./safety-observer.mjs";
import { buildManifestEntry, buildDiagnosticEntry, writeManifest } from "./manifest.mjs";
import { isObservable, getEquivalentState } from "./state-specs.mjs";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

/**
 * Poll until a predicate function returns true or timeout.
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
 * BLOCKER 1 FIX: zero-external is checked ATOMICALLY before any accepted
 * screenshot write. If external-origin count > 0, the capture is classified
 * as FORBIDDEN_STATE_REACHED and routed to diagnostics only.
 *
 * @param {Object} params
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

  // BLOCKER 1: ATOMIC zero-external precondition for ACCEPTED capture.
  // If external-origin count > 0, no PNG may enter the accepted set,
  // EVEN IF all other predicates passed. Route to diagnostic/fail-closed.
  if (eligibility.eligible && safetyCounts.externalOriginRequests > 0) {
    // Write diagnostic only (never to accepted)
    const diagPath = join(diagnosticDir, filename);
    let diagResult = null;
    try {
      diagResult = await captureScreenshot(page, diagPath);
    } catch {
      // best-effort
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
      captureStatus: CAPTURE_STATUS.FORBIDDEN_STATE_REACHED,
      reason: `SAFETY VIOLATION: external-origin requests=${safetyCounts.externalOriginRequests}. Accepted set unchanged.`,
    });
    return { accepted: false, entry: diagEntry, eligibility: { ...eligibility, eligible: false, status: CAPTURE_STATUS.FORBIDDEN_STATE_REACHED }, snapshot, safetyViolation: true };
  }

  // Handle NOT_SEPARATELY_OBSERVABLE states
  if (eligibility.notSeparablyObservable) {
    const diagEntry = buildDiagnosticEntry({
      scenarioId: scenarioSpec.id,
      semanticState: targetState,
      requestedState: targetState,
      product: scenarioSpec.product,
      viewport: scenarioSpec.viewport,
      url: snapshot.url,
      runtimeSnapshot: snapshot,
      requiredResults: [],
      forbiddenResults: [],
      stabilityResult: null,
      safetyCounts,
      captureStatus: CAPTURE_STATUS.NOT_SEPARATELY_OBSERVABLE,
      reason: eligibility.reason || `State ${targetState} is not separately observable. Equivalent: ${eligibility.equivalentState}`,
    });
    return { accepted: false, entry: diagEntry, eligibility, snapshot, notSeparablyObservable: true, equivalentState: eligibility.equivalentState };
  }

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

  let diagResult = null;
  try {
    diagResult = await captureScreenshot(page, diagPath);
  } catch {
    // best-effort
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
 * Run a full scenario with checkpoint-based capture.
 *
 * BLOCKER 2 FIX: scenario spec defines `checkpoints` — an array of
 * { state, afterStep } where `afterStep` is the index of the step
 * after which this state should be captured. The orchestrator executes
 * steps and captures at each checkpoint BETWEEN steps, not after all.
 *
 * @param {Object} params
 * @returns {Promise<Object>} full run result
 */
export async function runScenario(params) {
  const { browser, scenarioSpec, stateSpecs, baseUrl, artifactsRoot, runId, stabilityConfig } = params;

  const runDir = join(artifactsRoot, runId, scenarioSpec.id);
  const acceptedDir = join(runDir, "screenshots");
  const diagnosticDir = join(runDir, "diagnostics");
  const manifestDir = runDir;
  mkdirSync(runDir, { recursive: true });

  const context = await browser.newContext({
    viewport: scenarioSpec.viewport,
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const safetyObserver = attachSafetyObserver(page);

  await page.route("**/api/mvp/ask", async (route) => {
    const payload = JSON.parse(route.request().postData() || "{}");
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(buildMockResponse(payload.question || "", scenarioSpec)),
    });
  });

  const entries = [];
  const checkpointResults = [];

  try {
    // Navigate to MVP entry
    await page.goto(`${baseUrl}/mvp/index.html`, { waitUntil: "networkidle", timeout: 15000 });
    await pollUntil(
      page,
      async () => (await page.getAttribute("body", "data-first-use-state")) === "entry",
      { label: "entry state", timeoutMs: 8000 },
    );

    // Determine checkpoint plan
    const checkpoints = scenarioSpec.checkpoints || [];

    // If no checkpoints defined, fall back to old behavior (all captures after all steps)
    if (checkpoints.length === 0 && scenarioSpec.captureStates) {
      // Execute all steps
      for (const step of scenarioSpec.steps) {
        await step(page);
      }
      // Capture all states
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
          checkpointResults.push({ state: targetState, expected: "ACCEPTED", actual: "UNKNOWN_STATE", accepted: false });
          continue;
        }
        const result = await captureEvidence({
          page, scenarioSpec, targetState, stateSpec, safetyObserver, acceptedDir, diagnosticDir, stabilityConfig,
        });
        entries.push(result.entry);
        checkpointResults.push({
          state: targetState,
          expected: isObservable(targetState) ? "ACCEPTED" : "NOT_SEPARATELY_OBSERVABLE",
          actual: result.entry.capture_status,
          accepted: result.accepted,
        });
      }
    } else {
      // BLOCKER 2 FIX: checkpoint-based execution
      // Execute steps in order, capturing at each checkpoint.
      // Track the current step index so steps are NOT re-executed.
      let currentStepIndex = 0;

      for (const checkpoint of checkpoints) {
        // Determine which steps to execute for this checkpoint
        const targetStepIndex = checkpoint.afterStep !== undefined
          ? checkpoint.afterStep + 1
          : (checkpoint.beforeStep !== undefined ? checkpoint.beforeStep : 0);

        // Execute any steps that haven't been run yet up to the target
        while (currentStepIndex < targetStepIndex && currentStepIndex < scenarioSpec.steps.length) {
          await scenarioSpec.steps[currentStepIndex](page);
          currentStepIndex++;
        }

        // Capture at this checkpoint
        const targetState = checkpoint.state;
        const stateSpec = stateSpecs[targetState];
        if (!stateSpec) {
          entries.push({
            schema_version: "1.0.0",
            scenario_id: scenarioSpec.id,
            requested_state: targetState,
            capture_status: "UNKNOWN_STATE",
            reason: `No state spec defined for ${targetState}`,
          });
          checkpointResults.push({ state: targetState, expected: checkpoint.expected || "ACCEPTED", actual: "UNKNOWN_STATE", accepted: false });
          continue;
        }

        const result = await captureEvidence({
          page, scenarioSpec, targetState, stateSpec, safetyObserver, acceptedDir, diagnosticDir, stabilityConfig,
        });
        entries.push(result.entry);
        checkpointResults.push({
          state: targetState,
          expected: checkpoint.expected || (isObservable(targetState) ? "ACCEPTED" : "NOT_SEPARATELY_OBSERVABLE"),
          actual: result.entry.capture_status,
          accepted: result.accepted,
          equivalentState: result.equivalentState || getEquivalentState(targetState),
        });
      }
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
    checkpointResults,
    manifestPath,
    safetyCounts,
  };
}
