// tests/browser/verify_page_agent_lab_runtime.mjs
//
// Runtime verification for the #1090 Page Agent lab.
// No Playwright, no external network, no real fetch.
// Uses only node:assert, node:fs, node:vm, node:crypto.

import { readFileSync, existsSync } from "node:fs";
import assert from "node:assert";
import vm from "node:vm";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..", "..");
const EXAMPLES_BASE = join(REPO_ROOT, "src", "web", "examples", "page-agent");

const mockModelCode = readFileSync(join(EXAMPLES_BASE, "mock-model.js"), "utf8");

// ── VM Context ───────────────────────────────────────────────────────────

function createContext() {
  const ctx = {
    window: {
      location: {
        origin: "http://localhost:8765",
        href: "http://localhost:8765/examples/page-agent/",
      },
      addEventListener() {},
      PageAgent: undefined,
      PageAgentMockModel: undefined,
      setTimeout,
      clearTimeout,
      setInterval,
      clearInterval,
      Promise,
      Math,
      Object,
      String,
      Boolean,
      Array,
      JSON,
      Number,
      Date,
      URL,
      fetch: undefined,
      document: {
        getElementById(id) {
          if (
            id === "quick-start" ||
            id === "vs-browser-use" ||
            id === "license" ||
            id === "architecture"
          ) {
            return { scrollIntoView() {}, style: {} };
          }
          return null;
        },
        addEventListener() {},
      },
      console,
      setTimeout,
      clearTimeout,
      setInterval,
      clearInterval,
    },
    Response,
    URL,
  };
  ctx.window.globalThis = ctx.window;
  return ctx;
}

function runInContext(code, context) {
  vm.createContext(context);
  vm.runInContext(code, context);
  return context;
}

// ── Tests ────────────────────────────────────────────────────────────────

function testMockModelExports() {
  const ctx = createContext();
  runInContext(mockModelCode, ctx);
  const model = ctx.window.PageAgentMockModel;

  assert.ok(model, "PageAgentMockModel must be defined");
  assert.strictEqual(typeof model.handleCompletion, "function", "handleCompletion must be a function");
  assert.strictEqual(typeof model.isBlocked, "function", "isBlocked must be a function");
  assert.strictEqual(typeof model.getSupportedTaskIds, "function", "getSupportedTaskIds must be a function");
  assert.strictEqual(typeof model.getTask, "function", "getTask must be a function");
  assert.strictEqual(typeof model.isSupportedTask, "function", "isSupportedTask must be a function");
  assert.strictEqual(typeof model.getAllTasks, "function", "getAllTasks must be a function");
  assert.strictEqual(typeof model.respond, "function", "respond must be a function");

  console.log("  [1] Mock model exports: OK");
}

function testSupportedTasksCount() {
  const ctx = createContext();
  runInContext(mockModelCode, ctx);
  const model = ctx.window.PageAgentMockModel;

  const taskIds = model.getSupportedTaskIds();
  assert.ok(taskIds.length >= 4, `expected at least 4 tasks, got ${taskIds.length}: ${taskIds.join(", ")}`);

  console.log(`  [2] Supported task count (${taskIds.length}): OK`);
}

function testTaskLookup() {
  const ctx = createContext();
  runInContext(mockModelCode, ctx);
  const model = ctx.window.PageAgentMockModel;

  const tasks = model.getAllTasks();
  for (const task of tasks) {
    const found = model.getTask(task.id);
    assert.ok(found, `task '${task.id}' must be retrievable`);
    assert.strictEqual(found.id, task.id);
    assert.ok(Array.isArray(found.triggers), `task '${task.id}' must have triggers array`);
    assert.ok(found.triggers.length > 0, `task '${task.id}' must have at least one trigger`);
    assert.ok(found.sectionId, `task '${task.id}' must have a sectionId`);
    assert.ok(found.response, `task '${task.id}' must have a response`);
  }

  console.log("  [3] Task lookup: OK");
}

async function testAgentOutputToolCallFormat() {
  const ctx = createContext();
  runInContext(mockModelCode, ctx);
  const model = ctx.window.PageAgentMockModel;

  const url = "http://localhost:8765/examples/page-agent/mock-llm/v1/chat/completions";
  const payload = {
    model: "page-agent-lab-local",
    messages: [{ role: "user", content: "Show the Quick Start section" }],
    tools: [{ function: { name: "AgentOutput" } }],
    tool_choice: { type: "function", function: { name: "AgentOutput" } },
  };

  // First call (no <step_1> in history) → execute_javascript
  const resp1 = await model.respond(url, { body: JSON.stringify(payload) });
  assert.ok(resp1 instanceof Response, "respond must return a Response");
  const data1 = await resp1.json();

  assert.ok(data1.choices, "response must have choices array");
  assert.strictEqual(data1.choices.length, 1, "must have exactly 1 choice");
  const choice1 = data1.choices[0];
  assert.ok(choice1.message.tool_calls, "first response must have tool_calls");
  assert.strictEqual(choice1.message.tool_calls.length, 1);
  const tc1 = choice1.message.tool_calls[0];
  assert.strictEqual(tc1.function.name, "AgentOutput");
  const args1 = JSON.parse(tc1.function.arguments);
  assert.ok(args1.action.execute_javascript, "first step must call execute_javascript");
  assert.ok(args1.action.execute_javascript.script.includes("quick-start"));
  assert.strictEqual(choice1.finish_reason, "tool_calls");

  // Second call (with <step_1> in history) → done
  const payload2 = { ...payload, messages: [{ role: "user", content: "<step_1>..." }] };
  const resp2 = await model.respond(url, { body: JSON.stringify(payload2) });
  const data2 = await resp2.json();
  const choice2 = data2.choices[0];
  const tc2 = choice2.message.tool_calls[0];
  const args2 = JSON.parse(tc2.function.arguments);
  assert.ok(args2.action.done, "second step must call done");
  assert.strictEqual(args2.action.done.success, true);

  console.log("  [4] AgentOutput tool-call format (execute_javascript → done): OK");
}

function testUrlBlocking() {
  const ctx = createContext();
  runInContext(mockModelCode, ctx);
  const model = ctx.window.PageAgentMockModel;

  const blockedHosts = [
    "https://cdn.jsdelivr.net/npm/page-agent/package.json",
    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "https://api.openai.com/v1/chat/completions",
    "https://generativelanguage.googleapis.com/v1/models",
    "https://alibaba.github.io/page-agent/",
    "https://raw.githubusercontent.com/alibaba/page-agent/main/README.md",
  ];

  for (const url of blockedHosts) {
    assert.ok(model.isBlocked(url), `URL should be blocked: ${url}`);
  }

  const allowedUrls = [
    "http://localhost:8765/examples/page-agent/mock-model.js",
    "http://127.0.0.1:8765/page-agent-lab.css",
  ];

  for (const url of allowedUrls) {
    assert.strictEqual(model.isBlocked(url), false, `URL should not be blocked: ${url}`);
  }

  console.log("  [5] URL blocking: OK");
}

function testProvenanceConstants() {
  const ctx = createContext();
  runInContext(mockModelCode, ctx);
  const model = ctx.window.PageAgentMockModel;

  assert.ok(Array.isArray(model.BLOCKED_HOSTS), "BLOCKED_HOSTS must be an array");
  assert.ok(model.BLOCKED_HOSTS.includes("cdn.jsdelivr.net"), "must block jsdelivr");
  assert.ok(model.BLOCKED_HOSTS.includes("dashscope.aliyuncs.com"), "must block dashscope");
  assert.ok(model.BLOCKED_HOSTS.includes("api.openai.com"), "must block openai");

  console.log("  [6] Provenance constants: OK");
}

async function testDiagnosticsIncrement() {
  const ctx = createContext();
  runInContext(mockModelCode, ctx);
  const model = ctx.window.PageAgentMockModel;

  const url = "http://localhost:8765/examples/page-agent/mock-llm/v1/chat/completions";
  const payload = {
    model: "page-agent-lab-local",
    messages: [{ role: "user", content: "Show the Quick Start section" }],
    tools: [{ function: { name: "AgentOutput" } }],
    tool_choice: { type: "function", function: { name: "AgentOutput" } },
  };

  const d1 = model.getDiagnostics();
  assert.strictEqual(d1.callCount, 0);
  await model.respond(url, { body: JSON.stringify(payload) });
  const d2 = model.getDiagnostics();
  assert.strictEqual(d2.callCount, 1);
  assert.strictEqual(d2.lastActionName, "execute_javascript");
  await model.respond(url, { body: JSON.stringify({ ...payload, messages: [{ role: "user", content: "<step_1>" }] }) });
  const d3 = model.getDiagnostics();
  assert.strictEqual(d3.callCount, 2);
  assert.strictEqual(d3.lastActionName, "done");

  console.log("  [7] Diagnostics increment across calls: OK");
}

function testVendorBundleExists() {
  const bundlePath = join(EXAMPLES_BASE, "vendor", "page-agent.iife.js");
  const licensePath = join(EXAMPLES_BASE, "vendor", "LICENSE");
  assert.ok(existsSync(bundlePath), "vendor bundle must exist");
  assert.ok(existsSync(licensePath), "vendor LICENSE must exist");

  const bundleSize = readFileSync(bundlePath).length;
  assert.ok(bundleSize > 100000, "bundle should be substantial (>100KB)");

  console.log("  [8] Vendor bundle exists and is substantial: OK");
}

function testManifestShaParity() {
  const manifestPath = join(EXAMPLES_BASE, "vendor-manifest.json");
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));

  assert.ok(manifest.vendored_files, "manifest must have vendored_files");
  assert.ok(manifest.vendored_files.length >= 2, "at least 2 vendored files");

  for (const entry of manifest.vendored_files) {
    const filePath = join(EXAMPLES_BASE, entry.path);
    assert.ok(existsSync(filePath), `vendored file must exist: ${entry.path}`);

    const content = readFileSync(filePath);
    const actualSha = createHash("sha256").update(content).digest("hex");
    assert.strictEqual(
      actualSha.toUpperCase(),
      entry.sha256.toUpperCase(),
      `SHA-256 mismatch for ${entry.path}: expected ${entry.sha256}, got ${actualSha}`
    );
    assert.strictEqual(content.length, entry.bytes, `byte count mismatch for ${entry.path}`);
  }

  console.log("  [9] Manifest SHA-256 parity: OK");
}

function testNoDemoStrings() {
  const bundlePath = join(EXAMPLES_BASE, "vendor", "page-agent.iife.js");
  const labPath = join(EXAMPLES_BASE, "page-agent-lab.js");
  const indexPath = join(EXAMPLES_BASE, "index.html");

  // Vendor bundle and lab init must not contain demo strings
  for (const path of [bundlePath, labPath]) {
    const text = readFileSync(path, "utf8");
    assert.ok(!text.includes("page-ag-testing-ohftxirgbn"), `${path} must not contain demo testing API key`);
    assert.ok(!text.includes("DEMO_BASE_URL"), `${path} must not contain DEMO_BASE_URL`);
    assert.ok(!text.includes("autoInit"), `${path} must not contain autoInit`);
    assert.ok(!text.includes("page-agent.demo.js"), `${path} must not reference demo bundle`);
  }

  // index.html may contain documentation code examples showing upstream usage.
  // Only check for active script loads (already covered by Python test_no_auto_init_script).
  const indexText = readFileSync(indexPath, "utf8");
  assert.ok(!indexText.includes("page-ag-testing-ohftxirgbn"), "index must not contain demo testing API key");
  assert.ok(!indexText.includes("DEMO_BASE_URL"), "index must not contain DEMO_BASE_URL");
  assert.ok(!indexText.includes("autoInit"), "index must not contain autoInit");
  // page-agent.demo.js reference in documentation code blocks is allowed;
  // only active <script src=...> loads are forbidden (tested in Python suite).

  console.log("  [10] No demo strings in bundle/lab/index: OK");
}

function testPageAgentLabActualInit() {
  const labPath = join(EXAMPLES_BASE, "page-agent-lab.js");
  const text = readFileSync(labPath, "utf8");

  assert.ok(text.includes("window.PageAgent"), "must reference window.PageAgent");
  assert.ok(text.includes("new window.PageAgent"), "must instantiate actual PageAgent");
  assert.ok(text.includes("agent.panel.show()"), "must show built-in Panel");
  assert.ok(text.includes("customFetch:"), "must provide customFetch");
  assert.ok(text.includes("experimentalScriptExecutionTool: true"), "must enable execute_javascript tool");
  assert.ok(text.includes("localCustomFetch"), "must use local customFetch");
  assert.ok(text.includes("mock-llm/v1"), "must point to local mock endpoint");
  assert.ok(text.includes("PageAgentLabMockModel.respond"), "must call mock model's respond");
  assert.ok(!text.includes("fetch("), "must not use native fetch directly");
  assert.ok(!text.includes("scrollIntoView"), "lab must not directly call scrollIntoView");

  console.log("  [11] page-agent-lab.js uses actual PageAgent + customFetch + Panel: OK");
}

function testIndexHtmlScriptOrder() {
  const indexPath = join(EXAMPLES_BASE, "index.html");
  const html = readFileSync(indexPath, "utf8");

  const bundleIdx = html.indexOf("./vendor/page-agent.iife.js");
  const mockIdx = html.indexOf("./mock-model.js");
  const labIdx = html.indexOf("./page-agent-lab.js");

  assert.ok(bundleIdx > 0 && mockIdx > 0 && labIdx > 0, "all three scripts must be present");
  assert.ok(bundleIdx < mockIdx && mockIdx < labIdx, "load order: bundle → mock-model → lab");

  console.log("  [12] index.html script load order: OK");
}

function testBukguIsolation() {
  const files = ["mock-model.js", "page-agent-lab.js", "page-agent-lab.css", "index.html"];
  for (const fn of files) {
    const text = readFileSync(join(EXAMPLES_BASE, fn), "utf8");
    assert.ok(!text.includes("bukgu"), `${fn} must not reference bukgu`);
    assert.ok(!text.includes("북구"), `${fn} must not reference 북구`);
    assert.ok(!/\bquest\b/i.test(text), `${fn} must not reference quest`);
    assert.ok(!/\bmvp\b/i.test(text), `${fn} must not reference mvp`);
  }
  console.log("  [13] Buk-gu isolation: OK");
}

// ── #1090 NEW: Reset diagnostics ───────────────────────────────────────

async function testResetDiagnostics() {
  const ctx = createContext();
  runInContext(mockModelCode, ctx);
  const model = ctx.window.PageAgentMockModel;

  const url = "http://localhost:8765/examples/page-agent/mock-llm/v1/chat/completions";
  const payload = {
    model: "page-agent-lab-local",
    messages: [{ role: "user", content: "Show the Quick Start section" }],
    tools: [{ function: { name: "AgentOutput" } }],
    tool_choice: { type: "function", function: { name: "AgentOutput" } },
  };

  function isEmptyArray(a) {
    return Array.isArray(a) && a.length === 0;
  }

  // Before any call
  let d = model.getDiagnostics();
  assert.strictEqual(d.callCount, 0);
  assert.ok(isEmptyArray(d.toolNames), "toolNames must be empty before any call");
  assert.ok(isEmptyArray(d.actionNames), "actionNames must be empty before any call");
  assert.ok(isEmptyArray(d.taskIds), "taskIds must be empty before any call");
  assert.ok(isEmptyArray(d.successValues), "successValues must be empty before any call");
  assert.ok(isEmptyArray(d.completionTexts), "completionTexts must be empty before any call");

  // After first call
  await model.respond(url, { body: JSON.stringify(payload) });
  d = model.getDiagnostics();
  assert.strictEqual(d.callCount, 1);
  assert.strictEqual(d.toolNames.length, 1);
  assert.strictEqual(d.actionNames[0], "execute_javascript");

  // Reset
  model.resetDiagnostics();
  d = model.getDiagnostics();
  assert.strictEqual(d.callCount, 0);
  assert.ok(isEmptyArray(d.toolNames), "toolNames must be empty after reset");
  assert.ok(isEmptyArray(d.actionNames), "actionNames must be empty after reset");
  assert.ok(isEmptyArray(d.taskIds), "taskIds must be empty after reset");
  assert.ok(isEmptyArray(d.successValues), "successValues must be empty after reset");
  assert.ok(isEmptyArray(d.completionTexts), "completionTexts must be empty after reset");

  console.log("  [14] Reset diagnostics clears all counters: OK");
}

// ── #1090 NEW: Supported task diagnostic sequence ───────────────────────

async function testSupportedDiagnosticsSequence() {
  const ctx = createContext();
  runInContext(mockModelCode, ctx);
  const model = ctx.window.PageAgentMockModel;

  const url = "http://localhost:8765/examples/page-agent/mock-llm/v1/chat/completions";
  const payload = {
    model: "page-agent-lab-local",
    messages: [{ role: "user", content: "Show the Quick Start section" }],
    tools: [{ function: { name: "AgentOutput" } }],
    tool_choice: { type: "function", function: { name: "AgentOutput" } },
  };

  // First call (supported, first step) → execute_javascript, no done yet
  await model.respond(url, { body: JSON.stringify(payload) });
  let d = model.getDiagnostics();
  assert.strictEqual(d.callCount, 1);
  assert.strictEqual(d.actionNames.length, 1);
  assert.strictEqual(d.actionNames[0], "execute_javascript");
  assert.strictEqual(d.successValues.length, 1);
  assert.strictEqual(d.successValues[0], null);
  assert.strictEqual(d.completionTexts.length, 1);
  assert.strictEqual(d.completionTexts[0], null);
  assert.strictEqual(d.lastSuccess, null);
  assert.strictEqual(d.lastCompletionText, null);

  // Second call (supported, has <step_1>) → done with success:true + response text
  const quickStartTask = model.getTask("quick-start");
  assert.ok(quickStartTask, "quick-start task must exist");
  const payload2 = {
    ...payload,
    messages: [{ role: "user", content: "<step_1> Show the Quick Start section" }],
  };
  await model.respond(url, { body: JSON.stringify(payload2) });
  d = model.getDiagnostics();
  assert.strictEqual(d.callCount, 2);
  assert.strictEqual(d.actionNames.length, 2);
  assert.strictEqual(d.actionNames[0], "execute_javascript");
  assert.strictEqual(d.actionNames[1], "done");
  assert.strictEqual(d.successValues.length, 2);
  assert.strictEqual(d.successValues[0], null);
  assert.strictEqual(d.successValues[1], true);
  assert.strictEqual(d.lastSuccess, true);
  assert.strictEqual(d.completionTexts[0], null);
  assert.ok(
    typeof d.completionTexts[1] === "string" && d.completionTexts[1].length > 0,
    `completion text must be a non-empty string for done action, got ${typeof d.completionTexts[1]}`
  );
  assert.ok(
    d.lastCompletionText.includes(quickStartTask.response),
    `lastCompletionText must contain the task response. Expected to include: "${quickStartTask.response.substring(0, 40)}..."`
  );

  console.log("  [15] Supported task diagnostic sequence (successValues, completionTexts): OK");
}

// ── #1090 NEW: Unknown task diagnostic sequence ─────────────────────────

async function testUnknownDiagnosticsSequence() {
  const ctx = createContext();
  runInContext(mockModelCode, ctx);
  const model = ctx.window.PageAgentMockModel;

  const url = "http://localhost:8765/examples/page-agent/mock-llm/v1/chat/completions";
  const payload = {
    model: "page-agent-lab-local",
    messages: [{ role: "user", content: "What is the weather today?" }],
    tools: [{ function: { name: "AgentOutput" } }],
    tool_choice: { type: "function", function: { name: "AgentOutput" } },
  };

  // Reset first
  model.resetDiagnostics();

  // Single call for unknown (no <step_1>) → done with success:false + unsupported text
  await model.respond(url, { body: JSON.stringify(payload) });
  const d = model.getDiagnostics();

  assert.strictEqual(d.callCount, 1);
  assert.strictEqual(d.actionNames.length, 1);
  assert.strictEqual(d.actionNames[0], "done");
  assert.strictEqual(d.taskIds.length, 1);
  assert.strictEqual(d.taskIds[0], null);
  assert.strictEqual(d.successValues.length, 1);
  assert.strictEqual(d.successValues[0], false);
  assert.strictEqual(d.lastSuccess, false);
  assert.strictEqual(d.completionTexts[0], d.lastCompletionText);
  assert.ok(
    typeof d.lastCompletionText === "string" && d.lastCompletionText.length > 0,
    "lastCompletionText must be a non-empty string for unknown task"
  );
  assert.ok(
    d.lastCompletionText.includes("I can only help with the following topics on this page"),
    `lastCompletionText must contain unsupported bounded text. Got: "${d.lastCompletionText.substring(0, 80)}..."`
  );
  assert.ok(
    d.lastCompletionText.includes("Show the Quick Start section"),
    "lastCompletionText must list supported tasks"
  );

  console.log("  [16] Unknown task diagnostic sequence (success=false, bounded text): OK");
}

// ── Main ────────────────────────────────────────────────────────────────

async function main() {
  console.log("Running Page Agent lab runtime scenarios (no network, no fetch):");

  testMockModelExports();
  testSupportedTasksCount();
  testTaskLookup();
  await testAgentOutputToolCallFormat();
  testUrlBlocking();
  testProvenanceConstants();
  await testDiagnosticsIncrement();
  testVendorBundleExists();
  testManifestShaParity();
  testNoDemoStrings();
  testPageAgentLabActualInit();
  testIndexHtmlScriptOrder();
  testBukguIsolation();
  await testResetDiagnostics();
  await testSupportedDiagnosticsSequence();
  await testUnknownDiagnosticsSequence();

  console.log("All Page Agent lab runtime scenarios passed.");
}

main().catch((err) => {
  console.error("Page Agent lab runtime verification FAILED:");
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});