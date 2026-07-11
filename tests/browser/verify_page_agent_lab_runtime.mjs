// tests/browser/verify_page_agent_lab_runtime.mjs
//
// Executable runtime verification for the #1090 Page Agent lab.
//
// Constraints:
//   - no Playwright, no external network, no real fetch
//   - uses only node:assert, node:fs, node:vm
//   - reads src/web/examples/page-agent/mock-model.js and verifies
//     its deterministic behavior, task mapping, and URL blocking

import { readFileSync } from "node:fs";
import assert from "node:assert";
import vm from "node:vm";

const EXAMPLES_BASE = new URL(
  "../../src/web/examples/page-agent/",
  import.meta.url,
);

const mockModelCode = readFileSync(
  new URL("mock-model.js", EXAMPLES_BASE),
  "utf8",
);

const labJsCode = readFileSync(
  new URL("page-agent-lab.js", EXAMPLES_BASE),
  "utf8",
);

// ── VM Context ───────────────────────────────────────────────────────────

function createContext() {
  const mockDoc = {
    getElementById(id) { return null; },
    addEventListener() {},
  };
  const ctx = {
    window: {
      location: { origin: "http://localhost:8765", href: "http://localhost:8765/examples/page-agent/" },
      addEventListener() {},
      PageAgent: undefined,
      PageAgentMockModel: undefined,
      PageAgentLab: undefined,
      fetch: (url) => Promise.reject(new Error("fetch not expected: " + url)),
    },
    document: mockDoc,
    console,
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
  };
  ctx.globalThis = ctx;
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

  console.log("  [1] Mock model exports: OK");
}

function testSupportedTasksCount() {
  const ctx = createContext();
  runInContext(mockModelCode, ctx);
  const model = ctx.window.PageAgentMockModel;

  const taskIds = model.getSupportedTaskIds();
  assert.ok(taskIds.length >= 3, `expected at least 3 tasks, got ${taskIds.length}: ${taskIds.join(", ")}`);

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

function testCompletionHandling() {
  const ctx = createContext();
  runInContext(mockModelCode, ctx);
  const model = ctx.window.PageAgentMockModel;

  // Known task
  const result1 = model.handleCompletion(
    "http://localhost/mock-llm/v1/chat/completions",
    { messages: [{ role: "user", content: "Show the Quick Start section" }] },
  );
  assert.ok(result1, "known task must return a response");
  assert.ok(result1.choices, "response must have choices array");
  assert.ok(result1.choices[0].message, "choice must have message");
  assert.ok(result1.choices[0].message.content, "message must have content");
  const content1 = result1.choices[0].message.content;
  assert.ok(
    content1.toLowerCase().includes("quick start"),
    `response must mention the target section: ${content1}`,
  );

  // Unknown task
  const result2 = model.handleCompletion(
    "http://localhost/mock-llm/v1/chat/completions",
    { messages: [{ role: "user", content: "What is the weather today?" }] },
  );
  assert.ok(result2, "unknown task must still return a response");
  assert.ok(result2.choices, "unknown response must have choices");
  const content2 = result2.choices[0].message.content;
  assert.ok(
    content2.toLowerCase().includes("supported tasks") ||
    content2.toLowerCase().includes("cannot help with"),
    `unknown task response must say unsupported: ${content2}`,
  );

  console.log("  [4] Completion handling (known + unknown): OK");
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
    "http://localhost:8765/examples/page-agent/vendor/page-agent.demo.js",
    "http://127.0.0.1:8765/page-agent-lab.css",
  ];

  for (const url of allowedUrls) {
    assert.strictEqual(model.isBlocked(url), false, `URL should not be blocked: ${url}`);
  }

  console.log("  [5] URL blocking: OK");
}

function testLabJsInitializationMarkers() {
  const ctx = createContext();
  // Pre-set PageAgent as a function so the lab JS can detect it
  ctx.window.PageAgent = function PageAgentMock(config) {
    this.config = config;
    this.panel = { show: () => {} };
  };
  ctx.window.PageAgentMockModel = undefined; // Will be set when mock-model runs

  // Run mock-model first
  runInContext(mockModelCode, ctx);
  assert.ok(ctx.window.PageAgentMockModel, "mock model must be loaded before lab JS");

  // Run lab JS
  runInContext(labJsCode, ctx);

  // Check that the lab initialized (PageAgentLab should be defined)
  // Note: initialization is async via DOMContentLoaded, so we may need
  // to check for the lab's public API after a tick.
  return new Promise((resolve) => {
    setTimeout(() => {
      const lab = ctx.window.PageAgentLab;
      assert.ok(lab, "PageAgentLab must be defined after init");
      assert.strictEqual(typeof lab.isReady, "function", "isReady must be a function");
      assert.strictEqual(typeof lab.getAgent, "function", "getAgent must be a function");
      assert.strictEqual(typeof lab.getSupportedTaskIds, "function", "getSupportedTaskIds must be a function");

      // Verify customFetch and local-mock configuration
      const agent = lab.getAgent();
      assert.ok(agent, "agent must be created");
      assert.ok(agent.config, "agent must have config");
      assert.strictEqual(agent.config.model, "local-mock", "model must be local-mock");
      assert.strictEqual(agent.config.apiKey, "local-test-only", "apiKey must be placeholder");
      assert.ok(
        agent.config.baseURL.includes("examples/page-agent/mock-llm/v1"),
        `baseURL must point to local mock: ${agent.config.baseURL}`,
      );
      // customFetch must be a function
      assert.strictEqual(typeof agent.config.customFetch, "function", "customFetch must be defined");
      assert.ok(agent.panel, "agent must have panel property");

      console.log("  [6] Lab initialization markers: OK");
      resolve();
    }, 200);
  });
}

function testProvenanceConstants() {
  const ctx = createContext();
  runInContext(mockModelCode, ctx);
  const model = ctx.window.PageAgentMockModel;

  // Check BLOCKED_HOSTS
  assert.ok(Array.isArray(model.BLOCKED_HOSTS), "BLOCKED_HOSTS must be an array");
  assert.ok(model.BLOCKED_HOSTS.includes("cdn.jsdelivr.net"), "must block jsdelivr");
  assert.ok(model.BLOCKED_HOSTS.includes("dashscope.aliyuncs.com"), "must block dashscope");
  assert.ok(model.BLOCKED_HOSTS.includes("api.openai.com"), "must block openai");

  console.log("  [7] Provenance constants: OK");
}

// ── Main ─────────────────────────────────────────────────────────────────

async function main() {
  console.log("Running Page Agent lab runtime scenarios (no network, no fetch):");
  testMockModelExports();
  testSupportedTasksCount();
  testTaskLookup();
  testCompletionHandling();
  testUrlBlocking();
  await testLabJsInitializationMarkers();
  testProvenanceConstants();
  console.log("All Page Agent lab runtime scenarios passed.");
}

main().catch((err) => {
  console.error("Page Agent lab runtime verification FAILED:");
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
