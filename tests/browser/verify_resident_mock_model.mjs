// tests/browser/verify_resident_mock_model.mjs
//
// Unit-level verification of resident-mock-model.js behavioral fixes:
//
//   1. resetSession exported on PageAgentMockModel
//   2. resetSession() API clears stale state
//   3. Automatic session-key isolation (internal _sessionTask reset)
//   4. Same-request restart after resetSession()
//   5. Request dedup returns stop for same completed session
//   6. Missing target fail-closed: unknown element returns done(success=false)
//   7. Route validation: correct/wrong final route before reporting success
//   8. All 5 scenarios sequential without page reload
//   9. Complaint 2-step: nav-complaint-board -> complaint-write
//  10. Diagnostics integrity across all operations
//
// This is a mock-model unit test (no canvas DOM). It calls
// PageAgentMockModel.respond() directly, not the vendored Page Agent runtime.
//
// PASS: all assertions pass, exit code 0
// FAIL: any assertion fails, exit code 1

import { chromium } from "playwright";
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { createServer } from "node:http";
import { join, extname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const PROJECT_ROOT = join(__dirname, "..", "..");
const RESIDENT_ROUTE = "/src/web/examples/page-agent/resident/index.html";

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

// ── Inline static server ──────────────────────────────────────────────────

function createStaticServer() {
  return new Promise((resolve) => {
    const server = createServer((req, res) => {
      const url = new URL(req.url, "http://localhost");
      let filePath = join(PROJECT_ROOT, url.pathname);
      const ext = extname(filePath);

      try {
        const content = readFileSync(filePath);
        res.writeHead(200, { "Content-Type": MIME_TYPES[ext] || "application/octet-stream" });
        res.end(content);
      } catch {
        res.writeHead(404);
        res.end("Not Found");
      }
    });

    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      resolve({ server, baseUrl: `http://127.0.0.1:${port}/` });
    });
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────

/**
 * Launch Chromium when available; fall back to system Google Chrome.
 * Used so CI (npm ci without playwright install) and local dev both work.
 * Only catches browser-process launch failures — not test assertions.
 */
async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch (error) {
    return chromium.launch({
      headless: true,
      channel: "chrome",
    });
  }
}

function callRespond(page, userRequestText, browserStateContent) {
  const rawMessage =
    `<user_request>${userRequestText}</user_request>` +
    `<browser_state>${browserStateContent || ""}</browser_state>`;

  const payload = {
    model: "resident-mock-local",
    messages: [{ role: "user", content: rawMessage }],
    tools: [{ function: { name: "AgentOutput" } }],
  };

  return page.evaluate((p) => {
    const resp = window.PageAgentMockModel.respond(
      "http://127.0.0.1/mock-llm/v1/chat/completions",
      { body: JSON.stringify(p) }
    );
    return resp.json();
  }, payload);
}

function isToolCall(response) {
  return (
    response.choices &&
    response.choices[0] &&
    response.choices[0].finish_reason === "tool_calls"
  );
}

function isStop(response) {
  return (
    response.choices &&
    response.choices[0] &&
    response.choices[0].finish_reason === "stop"
  );
}

function getToolAction(response) {
  if (!isToolCall(response)) return null;
  const fn = response.choices[0].message.tool_calls[0].function;
  const parsed = JSON.parse(fn.arguments);
  return parsed.action || parsed;
}

function assertClickAction(action, label) {
  assert.ok(action, `${label}: expected action object`);
  assert.ok(
    action.click_element_by_index,
    `${label}: expected click_element_by_index action`
  );
  assert.ok(
    Number.isInteger(action.click_element_by_index.index),
    `${label}: click index must be integer`
  );
}

function assertDoneAction(action, expectedSuccess, label) {
  assert.ok(action, `${label}: expected action object`);
  assert.ok(action.done, `${label}: expected done action`);
  assert.strictEqual(
    action.done.success,
    expectedSuccess,
    `${label}: expected done(success=${expectedSuccess})`
  );
}

// Elements for click simulation — uses same flatTreeToString format as Page Agent:
//   [index]<tagName attr1=value1 attr2=attr2>text</tagName>
function makeBrowserState(targets) {
  const lines = [];
  for (let i = 0; i < targets.length; i++) {
    lines.push(
      `[${i}]<a data-action-target=${targets[i]} class=bg-home-link>${targets[i]}</a>`
    );
  }
  return lines.join("\n");
}

function browserStateWithTargets() {
  return makeBrowserState([
    "nav-apartment-dept",
    "nav-bulky-waste-disposal",
    "nav-passport-guidance",
    "nav-complaint-board",
    "complaint-write",
    "mayor-office-open",
    "mayor-message-write",
  ]);
}

async function getDiagnostics(page) {
  return page.evaluate(() => {
    const m = window.PageAgentMockModel;
    if (!m || !m.getDiagnostics) return null;
    const d = m.getDiagnostics();
    return {
      callCount: d.callCount,
      toolNames: d.toolNames ? [...d.toolNames] : [],
      actionNames: d.actionNames ? [...d.actionNames] : [],
      taskIds: d.taskIds ? [...d.taskIds] : [],
      successValues: d.successValues ? [...d.successValues] : [],
      completionTexts: d.completionTexts ? [...d.completionTexts] : [],
      lastSuccess: d.lastSuccess,
      lastCompletionText: d.lastCompletionText,
      lastActionName: d.lastActionName,
    };
  });
}

function assertDiagnosticsMatch(diag, callIdx, expected) {
  if (expected.lastActionName !== undefined) {
    assert.strictEqual(
      diag.actionNames[callIdx],
      expected.lastActionName,
      `diag[${callIdx}].actionName`
    );
  }
  if (expected.lastSuccess !== undefined) {
    assert.strictEqual(
      diag.successValues[callIdx],
      expected.lastSuccess,
      `diag[${callIdx}].successValue`
    );
  }
}

function resetDiag(page) {
  return page.evaluate(() => {
    const m = window.PageAgentMockModel;
    if (m && m.resetDiagnostics) m.resetDiagnostics();
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────

async function testResetSessionExport(page) {
  console.log("  0. resetSession exported on PageAgentMockModel...");

  const hasReset = await page.evaluate(() => {
    const m = window.PageAgentMockModel;
    return m && typeof m.resetSession === "function";
  });
  assert.ok(hasReset, "resetSession must be exported");

  console.log("    resetSession exported: PASS");
}

async function testSessionIsolation(page) {
  console.log("  1. Session isolation (explicit resetSession API)...");

  await page.evaluate(() => window.PageAgentMockModel.resetSession());
  await resetDiag(page);

  const browserState = browserStateWithTargets();

  // Scenario A: apartment_contact
  const result1 = await callRespond(page, "공동주택과 연락처 찾아줘", browserState);
  assert.ok(isToolCall(result1), "Scenario A: expected tool_call");
  const action1 = getToolAction(result1);
  assertClickAction(action1, "Scenario A");
  const idxA = action1.click_element_by_index.index;
  console.log(`    Scenario A: target index ${idxA}`);

  // Explicit reset before scenario B
  await page.evaluate(() => window.PageAgentMockModel.resetSession());

  // Scenario B: bulky_waste_menu
  const result2 = await callRespond(page, "대형폐기물 신청 메뉴 찾아줘", browserState);
  assert.ok(isToolCall(result2), "Scenario B: expected tool_call");
  const action2 = getToolAction(result2);
  assertClickAction(action2, "Scenario B");
  const idxB = action2.click_element_by_index.index;
  console.log(`    Scenario B: target index ${idxB}`);

  // Different targets
  assert.notStrictEqual(idxA, idxB, "Scenarios should select different targets");

  console.log("    Session isolation (explicit reset): PASS");
}

async function testAutomaticSessionIsolation(page) {
  console.log("  2. Automatic session-key isolation (no resetSession)...");

  await page.evaluate(() => window.PageAgentMockModel.resetSession());
  await resetDiag(page);

  const browserState = browserStateWithTargets();

  // Scenario A
  const result1 = await callRespond(page, "공동주택과 연락처 찾아줘", browserState);
  assert.ok(isToolCall(result1), "Scenario A: expected tool_call");
  const action1 = getToolAction(result1);
  assertClickAction(action1, "Scenario A");
  const idxA = action1.click_element_by_index.index;
  console.log(`    Scenario A: target index ${idxA}`);

  // DO NOT call resetSession() here.
  // With a different sessionKey, the internal protection must fire:
  //   if (sessionKey !== _lastSessionKey) { _sessionTask = null; }
  // so scenario B starts fresh and selects its own first target.

  // Scenario B: different sessionKey
  const result2 = await callRespond(page, "대형폐기물 신청 메뉴 찾아줘", browserState);
  assert.ok(isToolCall(result2), "Scenario B (auto-isolate): expected tool_call");
  const action2 = getToolAction(result2);
  assertClickAction(action2, "Scenario B (auto-isolate)");
  const idxB = action2.click_element_by_index.index;
  console.log(`    Scenario B (auto-isolate): target index ${idxB}`);

  // Must select a different target (stale _sessionTask was reset)
  assert.notStrictEqual(idxA, idxB, "Auto-isolation should select different target");

  console.log("    Automatic session-key isolation: PASS");
}

async function testSameRequestRestart(page) {
  console.log("  3. Same-request restart after resetSession()...");

  await page.evaluate(() => window.PageAgentMockModel.resetSession());
  await resetDiag(page);

  const browserState = browserStateWithTargets();
  const requestText = "공동주택과 연락처 찾아줘";

  // Run scenario A to completion
  const resp1 = await callRespond(page, requestText, browserState);
  assert.ok(isToolCall(resp1), "First run: expected tool_call (click)");
  const action1 = getToolAction(resp1);
  assertClickAction(action1, "First run");
  const idxFirst = action1.click_element_by_index.index;
  console.log(`    First run: click index ${idxFirst}`);

  // Complete: empty browser state signals nav complete
  const respDone = await callRespond(page, requestText, "");
  assert.ok(isToolCall(respDone), "Completion: expected tool_call");
  const actionDone = getToolAction(respDone);
  assertDoneAction(actionDone, false, "Completion (no canvas, route mismatch)");
  console.log("    Completion (route mismatch, success=false)");

  // Now resetSession to clear stale state
  await page.evaluate(() => window.PageAgentMockModel.resetSession());
  await resetDiag(page);

  // Submit SAME request again — must restart from nav step 0, not dedup to stop
  const respRestart = await callRespond(page, requestText, browserState);
  assert.ok(isToolCall(respRestart), "Restart: expected tool_call (not stop)");
  const actionRestart = getToolAction(respRestart);
  assertClickAction(actionRestart, "Restart");
  const idxRestart = actionRestart.click_element_by_index.index;

  // Must select the same first target (same scenario step 0)
  assert.strictEqual(
    idxRestart,
    idxFirst,
    "After resetSession(), same request must select the same first target"
  );
  console.log(`    Restart: click index ${idxRestart} (same as first run)`);

  // Verify finish_reason is tool_calls, not stop
  assert.strictEqual(
    respRestart.choices[0].finish_reason,
    "tool_calls",
    "Restart must not return stop"
  );

  console.log("    Same-request restart: PASS");
}

async function testRequestDedup(page) {
  console.log("  4. Request dedup returns stop for completed session...");

  await page.evaluate(() => window.PageAgentMockModel.resetSession());
  await resetDiag(page);

  const browserState = browserStateWithTargets();
  const requestText = "공동주택과 연락처 찾아줘";

  // First call: click
  let resp = await callRespond(page, requestText, browserState);
  assert.ok(isToolCall(resp), "Call 1: expected tool_call (click)");
  assertClickAction(getToolAction(resp), "Call 1");

  // Second call: same sessionKey, empty browser state → nav complete → done
  resp = await callRespond(page, requestText, "");
  assert.ok(isToolCall(resp), "Call 2: expected tool_call (done)");
  const action2 = getToolAction(resp);
  assertDoneAction(action2, false, "Call 2 (no canvas, route mismatch)");

  // Verify diagnostics after done
  let diag = await getDiagnostics(page);
  assert.strictEqual(diag.callCount, 2, "Diag: expected 2 calls");
  assert.strictEqual(diag.actionNames[1], "done", "Diag: second action is done");
  assert.strictEqual(diag.lastActionName, "done", "Diag: lastActionName is done");
  assert.strictEqual(diag.lastSuccess, false, "Diag: lastSuccess is false (no canvas)");

  // Third call: same sessionKey again → dedup → stop
  resp = await callRespond(page, requestText, "");
  assert.ok(isStop(resp), "Call 3 (dedup): expected finish_reason=stop");
  assert.strictEqual(
    resp.choices[0].finish_reason,
    "stop",
    "Dedup: finish_reason must be stop"
  );

  // Diagnostics should NOT have been updated by dedup (mock returns stop directly)
  diag = await getDiagnostics(page);
  assert.strictEqual(diag.callCount, 2, "Diag: dedup must not increment callCount");

  console.log("    Request dedup: PASS");
}

async function testMissingTargetFailClosed(page) {
  console.log("  5. Missing target fail-closed...");

  await page.evaluate(() => window.PageAgentMockModel.resetSession());
  await resetDiag(page);

  // Browser state WITHOUT the needed data-action-target
  const browserState = `[0]<a class=unrelated>Some link</a>`;

  const resp = await callRespond(page, "공동주택과 연락처 찾아줘", browserState);
  assert.ok(isToolCall(resp), "Missing target: expected tool_call");
  const action = getToolAction(resp);
  assertDoneAction(action, false, "Missing target");

  // Verify diagnostics
  const diag = await getDiagnostics(page);
  assert.strictEqual(diag.callCount, 1, "Diag: 1 call");
  assert.strictEqual(diag.lastActionName, "done", "Diag: action is done");
  assert.strictEqual(diag.lastSuccess, false, "Diag: success=false");
  assert.strictEqual(diag.taskIds[0], "apartment_contact", "Diag: task ID matches");

  console.log("    Missing target fail-closed: PASS");
}

async function testRouteValidation(page) {
  console.log("  6. Route validation (wrong route → success=false)...");

  await page.evaluate(() => window.PageAgentMockModel.resetSession());
  await resetDiag(page);

  const browserState = browserStateWithTargets();
  const requestText = "공동주택과 연락처 찾아줘";

  // Click the nav target (canvas is still on "home" route)
  const resp1 = await callRespond(page, requestText, browserState);
  assert.ok(isToolCall(resp1), "Route test: expected tool_call (click)");
  assertClickAction(getToolAction(resp1), "Route test click");

  // Complete nav → route check → canvas is on "home", expected "apartment-dept"
  const resp2 = await callRespond(page, requestText, "");
  assert.ok(isToolCall(resp2), "Route test: expected tool_call (done)");
  const action = getToolAction(resp2);
  assertDoneAction(action, false, "Route test (canvas=home, expected=apartment-dept)");

  // Verify diagnostics reflect the failure
  const diag = await getDiagnostics(page);
  assert.strictEqual(diag.callCount, 2, "Diag: 2 calls");
  assert.strictEqual(diag.lastActionName, "done", "Diag: last action is done");
  assert.strictEqual(diag.lastSuccess, false, "Diag: last success=false (wrong route)");
  assert.strictEqual(diag.taskIds[1], "apartment_contact", "Diag: task ID matches");

  console.log("    Route validation (wrong route → success=false): PASS");
}

async function testFiveScenariosSequential(page) {
  console.log("  7. Five scenarios sequential without page reload...");

  const scenarios = [
    { text: "공동주택과 연락처 찾아줘", id: "apartment_contact", navSteps: 1 },
    { text: "대형폐기물 신청 메뉴 찾아줘", id: "bulky_waste_menu", navSteps: 1 },
    { text: "여권 발급 절차를 찾아줘", id: "passport_procedure", navSteps: 1 },
    { text: "민원 작성 화면을 열어줘", id: "complaint_screen", navSteps: 2 },
    { text: "구청장에게 제안할 글 작성을 도와줘", id: "mayor_proposal_writing", navSteps: 2 },
  ];

  for (const sc of scenarios) {
    await page.evaluate(() => window.PageAgentMockModel.resetSession());
    await resetDiag(page);
    const browserState = browserStateWithTargets();

    // All nav steps
    for (let step = 0; step < sc.navSteps; step++) {
      const resp = await callRespond(page, sc.text, browserState);
      assert.ok(isToolCall(resp), `${sc.id} step ${step}: expected tool_call`);
      const action = getToolAction(resp);
      assertClickAction(action, `${sc.id} step ${step}`);
    }

    // Final call without browser state → nav complete → done
    const doneResp = await callRespond(page, sc.text, "");
    assert.ok(isToolCall(doneResp), `${sc.id}: expected tool_call for done`);
    const doneAction = getToolAction(doneResp);
    assertDoneAction(doneAction, false, `${sc.id} (no canvas, route mismatch)`);

    // Verify diagnostics
    const diag = await getDiagnostics(page);
    const expectedCallCount = sc.navSteps + 1;
    assert.strictEqual(
      diag.callCount,
      expectedCallCount,
      `${sc.id}: expected ${expectedCallCount} calls`
    );
    assert.strictEqual(
      diag.actionNames[diag.actionNames.length - 1],
      "done",
      `${sc.id}: last action is done`
    );
    assert.strictEqual(
      diag.lastSuccess,
      false,
      `${sc.id}: last success=false (no canvas match)`
    );
    assert.strictEqual(
      diag.lastActionName,
      "done",
      `${sc.id}: lastActionName is done`
    );

    console.log(`    ${sc.id} (${sc.navSteps} step(s)): OK`);
  }

  console.log("    5 scenarios sequential: PASS");
}

async function testComplaintTwoStep(page) {
  console.log("  8. Complaint 2-step flow...");

  await page.evaluate(() => window.PageAgentMockModel.resetSession());
  await resetDiag(page);
  const browserState = browserStateWithTargets();

  // Step 1: nav-complaint-board (index 3 in browserStateWithTargets)
  const resp1 = await callRespond(page, "민원 작성 화면을 열어줘", browserState);
  assert.ok(isToolCall(resp1), "Complaint step 1: expected tool_call");
  const action1 = getToolAction(resp1);
  assertClickAction(action1, "Complaint step 1");
  const idx1 = action1.click_element_by_index.index;
  console.log(`    Complaint step 1: index ${idx1} (should be nav-complaint-board)`);

  // Step 2: complaint-write (index 4 in browserStateWithTargets)
  // Must NOT complete on complaint-board — must require a second click
  const resp2 = await callRespond(page, "민원 작성 화면을 열어줘", browserState);
  assert.ok(isToolCall(resp2), "Complaint step 2: expected tool_call (not done)");
  const action2 = getToolAction(resp2);
  assertClickAction(action2, "Complaint step 2");
  const idx2 = action2.click_element_by_index.index;
  console.log(`    Complaint step 2: index ${idx2} (should be complaint-write)`);

  // Two different click indexes
  assert.notStrictEqual(idx1, idx2, "Complaint steps must have different click targets");

  // Step 3: done (no more nav steps)
  const resp3 = await callRespond(page, "민원 작성 화면을 열어줘", "");
  assert.ok(isToolCall(resp3), "Complaint step 3: expected tool_call (done)");
  const action3 = getToolAction(resp3);
  assertDoneAction(action3, false, "Complaint step 3 (no canvas, route mismatch)");

  // Verify diagnostics: 3 calls (2 clicks + 1 done)
  const diag = await getDiagnostics(page);
  assert.strictEqual(diag.callCount, 3, "Complaint: expected 3 calls");
  assert.strictEqual(diag.lastActionName, "done", "Complaint: last action is done");

  console.log("    Complaint 2-step: PASS");
}

async function testDiagnosticsIntegrity(page) {
  console.log("  9. Diagnostics integrity...");

  await page.evaluate(() => window.PageAgentMockModel.resetSession());
  await resetDiag(page);

  // Run a full scenario and check all diag fields
  const browserState = browserStateWithTargets();
  await callRespond(page, "공동주택과 연락처 찾아줘", browserState);
  await callRespond(page, "공동주택과 연락처 찾아줘", "");

  const diag = await getDiagnostics(page);

  assert.ok(diag.callCount > 0, "Diagnostics callCount > 0");
  assert.strictEqual(diag.toolNames.length, diag.callCount, "toolNames.length == callCount");
  assert.strictEqual(diag.actionNames.length, diag.callCount, "actionNames.length == callCount");
  assert.strictEqual(diag.successValues.length, diag.callCount, "successValues.length == callCount");

  // First call: click → actionName=click_element_by_index, success=null
  assert.strictEqual(diag.actionNames[0], "click_element_by_index");
  assert.strictEqual(diag.successValues[0], null);

  // Second call: done with route mismatch → actionName=done, success=false
  assert.strictEqual(diag.actionNames[1], "done");
  assert.strictEqual(diag.successValues[1], false);

  // last* fields must match last entry
  assert.strictEqual(diag.lastActionName, diag.actionNames[diag.callCount - 1]);
  assert.strictEqual(diag.lastSuccess, diag.successValues[diag.callCount - 1]);

  console.log("    Diagnostics integrity: PASS");
}

// ── Main ──────────────────────────────────────────────────────────────────

async function main() {
  const { server, baseUrl } = await createStaticServer();
  const residentUrl = baseUrl.replace(/\/$/, "") + RESIDENT_ROUTE;

  console.log(`Static server at ${baseUrl}`);
  console.log(`Resident demo at ${residentUrl}`);

  const browser = await launchBrowser();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    locale: "ko-KR",
  });
  const page = await context.newPage();

  let allPassed = false;
  try {
    await page.goto(residentUrl, { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForFunction(
      () =>
        typeof window.PageAgentMockModel !== "undefined" &&
        typeof window.PageAgentMockModel.respond === "function",
      { timeout: 10000 }
    );

    console.log("\n=== Mock Model Unit Tests ===\n");

    await testResetSessionExport(page);
    await testSessionIsolation(page);
    await testAutomaticSessionIsolation(page);
    await testSameRequestRestart(page);
    await testRequestDedup(page);
    await testMissingTargetFailClosed(page);
    await testRouteValidation(page);
    await testFiveScenariosSequential(page);
    await testComplaintTwoStep(page);
    await testDiagnosticsIntegrity(page);

    allPassed = true;
    console.log("\n=== ALL TESTS PASSED ===\n");
  } catch (err) {
    console.error("\n=== TEST FAILED ===");
    console.error(err.message || err);
    process.exitCode = 1;
  } finally {
    await browser.close();
    server.close();
  }

  if (allPassed) {
    process.exit(0);
  } else {
    process.exit(1);
  }
}

main();
