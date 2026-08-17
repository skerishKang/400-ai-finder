// tests/browser/test_comparison_browser_launch_ownership.mjs
//
// #1289 regression: browser-launch ownership.
//
// The harness must OWN every launched browser process. The previous defect raced
// `chromium.launch({ channel: "chrome" })` against a manual `setTimeout`; when the
// timer won, the real launch kept running unsupervised and was left dangling after
// the harness exited. The fix removes the race and relies on Playwright's native
// `timeout`, so a failed/slow preferred launch is owned and terminated by Playwright
// and the fallback chain is entered cleanly.
//
// This test does NOT start a real browser. It extracts the `launchBrowser` source
// from the harness, evaluates it inside a `vm` with a fake `chromium`/`existsSync`,
// and asserts the exact launch order and ownership semantics.

import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import test from "node:test";
import vm from "node:vm";

const __dirname = dirname(fileURLToPath(import.meta.url));
const HARNESS = join(__dirname, "..", "..", "scripts", "run_page_agent_comparison.mjs");

// ── Extract only the launchBrowser function source (balanced braces) ──────────
function extractLaunchBrowser(src) {
  const start = src.indexOf("async function launchBrowser()");
  assert.ok(start !== -1, "launchBrowser() not found in harness");
  let depth = 0;
  let inStr = null;
  let i = src.indexOf("{", start);
  for (; i < src.length; i++) {
    const c = src[i];
    if (inStr) {
      if (c === "\\") { i++; continue; }
      if (c === inStr) inStr = null;
      continue;
    }
    if (c === '"' || c === "'" || c === "`") { inStr = c; continue; }
    if (c === "{") depth++;
    else if (c === "}") { depth--; if (depth === 0) { i++; break; } }
  }
  return src.slice(start, i);
}

const launchSource = extractLaunchBrowser(readFileSync(HARNESS, "utf8"));

// ── Helpers ───────────────────────────────────────────────────────────────────

// plan: ordered array describing each chromium.launch() outcome.
//   { reject: false, browser?: <obj> }  -> resolves with browser
//   { reject: true, error?: <string> }  -> rejects
function buildLaunch(plan, { envExec = null, knownPaths = [], existsSet = new Set() } = {}) {
  const calls = [];
  let idx = 0;
  const fakeBrowser = () => ({ version: async () => "1.0.0" });
  const chromium = {
    launch(opts) {
      // Record a MAIN-realm copy with only the keys actually passed. Objects
      // created inside the vm context would otherwise fail deepStrictEqual
      // against main-realm literals due to a different Object.prototype.
      const rec = {};
      if ("headless" in opts) rec.headless = opts.headless;
      if ("channel" in opts) rec.channel = opts.channel;
      if ("executablePath" in opts) rec.executablePath = opts.executablePath;
      if ("timeout" in opts) rec.timeout = opts.timeout;
      calls.push(rec);
      const step = plan[idx++] || { reject: false, browser: fakeBrowser() };
      if (step.reject) return Promise.reject(new Error(step.error || "launch failed"));
      return Promise.resolve(step.browser || fakeBrowser());
    },
  };
  const context = {
    chromium,
    existsSync: (p) => existsSet.has(p),
    process: { env: envExec ? { PAGE_AGENT_BROWSER_EXECUTABLE: envExec } : {} },
    console: { log: () => {} },
    KNOWN_BROWSER_PATHS: knownPaths,
    BROWSER_TIMEOUT_MS: 15000,
    module: { exports: {} },
  };
  vm.createContext(context);
  vm.runInContext(`${launchSource}\nmodule.exports.launchBrowser = launchBrowser;`, context);
  return { launchBrowser: context.module.exports.launchBrowser, calls: () => calls };
}

function failAfter(ms, label) {
  return new Promise((_, rej) => setTimeout(() => rej(new Error("hang: " + label)), ms));
}

// ── 1. Preferred channel:chrome success -> NO fallback ─────────────────────────
test("preferred channel:chrome launch succeeds and skips all fallback attempts", async () => {
  const env = { envExec: null, knownPaths: ["/a", "/b"], existsSet: new Set(["/a", "/b"]) };
  const { launchBrowser, calls } = buildLaunch([{ reject: false }], env);

  const result = await launchBrowser();

  assert.equal(calls().length, 1, "exactly one launch must occur on preferred success");
  assert.deepStrictEqual(
    calls()[0],
    { headless: true, channel: "chrome", timeout: 15000 },
    "preferred launch must use headless/channel:chrome/native timeout"
  );
  assert.equal(result.source, "channel: chrome");
});

// ── 2. Preferred TIMEOUT rejection -> exact fallback order ────────────────────
test("preferred timeout rejection falls through to env->paths->default order", async () => {
  const env = { envExec: null, knownPaths: ["/a", "/b"], existsSet: new Set(["/a"]) };
  // preferred: timeout rejection; then path /a: reject; then default: succeed
  const plan = [
    { reject: true, error: "Timeout 15000ms exceeded" },
    { reject: true, error: "no such executable" },
    { reject: false },
  ];
  const { launchBrowser, calls } = buildLaunch(plan, env);

  const result = await launchBrowser();

  const opts = calls();
  assert.deepStrictEqual(
    opts.map((o) => o.channel || o.executablePath || "default"),
    ["chrome", "/a", "default"],
    "fallback order must be: preferred(channel:chrome) -> path:/a -> default"
  );
  assert.equal(opts[0].timeout, 15000, "preferred launch must carry native timeout");
  assert.equal(result.source, "default playwright chromium");
});

// ── 3. Preferred NON-timeout rejection -> identical fallback order ─────────────
test("preferred non-timeout rejection falls through in the same order", async () => {
  const env = { envExec: null, knownPaths: ["/a", "/b"], existsSet: new Set(["/a"]) };
  // preferred rejects with a NON-timeout error; first fallback (path /a) succeeds
  const plan = [
    { reject: true, error: "Executable doesn't exist" },
    { reject: false },
  ];
  const { launchBrowser, calls } = buildLaunch(plan, env);

  const result = await launchBrowser();

  const opts = calls();
  assert.equal(opts[0].channel, "chrome", "preferred must still be attempted first");
  assert.deepStrictEqual(
    opts.map((o) => o.channel || o.executablePath || "default"),
    ["chrome", "/a"],
    "fallback order must be identical whether the preferred failure was a timeout or not"
  );
  assert.equal(result.source, "path: /a");
});

// ── 4. Fallback success returns the selected browser/source ────────────────────
test("fallback selection returns the chosen browser object and accurate source", async () => {
  const envBrowser = { version: async () => "env-9.9" };
  const env = { envExec: "/env/path", knownPaths: ["/a", "/b"], existsSet: new Set() };
  // preferred reject; env attempt succeeds and returns envBrowser
  const plan = [
    { reject: true, error: "Timeout 15000ms exceeded" },
    { reject: false, browser: envBrowser },
  ];
  const { launchBrowser, calls } = buildLaunch(plan, env);

  const result = await launchBrowser();

  assert.equal(result.source, "env: /env/path");
  assert.equal(result.browser, envBrowser, "must return the browser from the winning fallback");
  assert.deepStrictEqual(calls()[1], { headless: true, executablePath: "/env/path" });
});

// ── 5. Every attempt fails -> aggregate fail-closed error ──────────────────────
test("all launch attempts failing throws an aggregated, fail-closed error", async () => {
  const env = { envExec: null, knownPaths: ["/a"], existsSet: new Set(["/a"]) };
  const plan = [
    { reject: true, error: "preferred failed" },
    { reject: true, error: "path failed" },
    { reject: true, error: "default failed" },
  ];
  const { launchBrowser } = buildLaunch(plan, env);

  await assert.rejects(
    () => launchBrowser(),
    /Cannot launch any browser/,
    "must fail closed with an aggregated error when no browser can launch"
  );
});

// ── 6. Source no longer races / uses a custom timer / has the old helper ───────
test("launchBrowser source contains no Promise.race, no custom setTimeout, no tryLaunch helper", () => {
  assert.ok(
    !/Promise\s*\.\s*race/.test(launchSource),
    "preferred launch must not be raced against a manual timer"
  );
  assert.ok(
    !/setTimeout\s*\(/.test(launchSource),
    "launchBrowser must not schedule its own setTimeout"
  );
  assert.ok(
    !/function\s+tryLaunch/.test(launchSource),
    "the old tryLaunch(setTimeout/Promise.race) helper must be removed"
  );
});

// ── 7. Process-exit regression: timeout->fallback must terminate promptly ───────
test("preferred timeout then fallback resolves promptly with no dangling extra launch", async () => {
  const env = { envExec: null, knownPaths: ["/a"], existsSet: new Set() };
  // preferred: timeout rejection; fallback default: succeed. No path attempts exist.
  const plan = [
    { reject: true, error: "Timeout 15000ms exceeded" },
    { reject: false },
  ];
  const { launchBrowser, calls } = buildLaunch(plan, env);

  // If the old setTimeout race were still present, this would hang until the
  // manual timer fired (or leak a dangling launch). Guard with a short ceiling.
  const result = await Promise.race([launchBrowser(), failAfter(500, "preferred-timeout-fallback")]);

  assert.equal(result.source, "default playwright chromium");
  assert.deepStrictEqual(
    calls().map((o) => o.channel || o.executablePath || "default"),
    ["chrome", "default"],
    "only the preferred attempt and the single winning fallback must launch"
  );
});
