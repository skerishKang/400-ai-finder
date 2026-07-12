#!/usr/bin/env node
/**
 * Render the local #868 home canvas at the R-HOME-02 viewport.
 * Local fixture only; writes review artifacts and metadata only.
 */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const VIEWPORT = Object.freeze({ width: 1644, height: 1833 });
const EXPECTED_CANVAS = Object.freeze({ width: 1344, height: 1833 });

function parseArgs(argv) {
  const args = { baseUrl: null, outputDir: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--base-url") {
      args.baseUrl = argv[index + 1] || null;
      index += 1;
    } else if (value === "--output-dir") {
      args.outputDir = argv[index + 1] || null;
      index += 1;
    } else {
      throw new Error(`Unknown argument: ${value}`);
    }
  }
  if (!args.baseUrl || !args.outputDir) {
    throw new Error("--base-url and --output-dir are required");
  }
  return args;
}

function assertLocalFixture(baseUrl) {
  const url = new URL(baseUrl);
  const isLoopback = url.hostname === "127.0.0.1" || url.hostname === "localhost";
  if (url.protocol !== "http:" || !isLoopback || url.pathname !== "/static/citizen-action-demo.html") {
    throw new Error("Only http://localhost or http://127.0.0.1 /static/citizen-action-demo.html is allowed");
  }
  return url.toString();
}

function storageInstrumentation() {
  const writes = [];
  for (const method of ["setItem", "removeItem", "clear"]) {
    const original = Storage.prototype[method];
    Object.defineProperty(Storage.prototype, method, {
      configurable: true,
      value(...args) {
        writes.push(`${this === window.localStorage ? "localStorage" : "sessionStorage"}.${method}`);
        return original.apply(this, args);
      },
    });
  }
  window.__fullHomeStorageWrites = writes;
}

function writeJson(outputDir, name, value) {
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(path.join(outputDir, name), `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const fixtureUrl = assertLocalFixture(args.baseUrl);
  const outputDir = path.resolve(args.outputDir);
  let chromium;
  try {
    ({ chromium } = require("playwright"));
  } catch {
    throw new Error("Local playwright package is required; package installation is not allowed");
  }

  const consoleErrors = [];
  const pageErrors = [];
  const externalRequests = [];
  const allRequests = [];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 });
  await context.addInitScript(storageInstrumentation);
  const page = await context.newPage();

  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(String(error)));
  page.on("request", (request) => {
    const requestUrl = request.url();
    allRequests.push(requestUrl);
    try {
      const parsed = new URL(requestUrl);
      const isLoopback = parsed.protocol === "http:" &&
        (parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost");
      if (!isLoopback) externalRequests.push(requestUrl);
    } catch {
      externalRequests.push(requestUrl);
    }
  });

  await page.goto(fixtureUrl, { waitUntil: "networkidle" });
  await page.waitForTimeout(250);
  const canvas = page.locator("#demo-canvas");
  await canvas.evaluate((element) => { element.scrollTop = 0; });
  const box = await canvas.boundingBox();
  if (!box) throw new Error("#demo-canvas is not visible");
  if (Math.round(box.width) !== EXPECTED_CANVAS.width || Math.round(box.height) !== EXPECTED_CANVAS.height) {
    throw new Error(`Canvas geometry mismatch: ${JSON.stringify(box)}`);
  }

  fs.mkdirSync(outputDir, { recursive: true });
  await canvas.screenshot({ path: path.join(outputDir, "home-full-canvas-1344x1833.png") });
  await page.screenshot({ path: path.join(outputDir, "home-full-split-1644x1833.png") });

  const pageState = await page.evaluate(() => {
    const canvasElement = document.querySelector("#demo-canvas");
    const home = document.querySelector(".bg-page--home");
    return {
      canvas_scroll_top: canvasElement ? canvasElement.scrollTop : null,
      canvas_scroll_height: canvasElement ? canvasElement.scrollHeight : null,
      home_root_height: home ? Math.round(home.getBoundingClientRect().height) : null,
      localStorageKeys: Object.keys(window.localStorage),
      sessionStorageKeys: Object.keys(window.sessionStorage),
      storageWrites: window.__fullHomeStorageWrites || [],
    };
  });
  const cookies = await context.cookies([fixtureUrl]);
  const passed = consoleErrors.length === 0 && pageErrors.length === 0 &&
    externalRequests.length === 0 && pageState.storageWrites.length === 0 &&
    pageState.localStorageKeys.length === 0 && pageState.sessionStorageKeys.length === 0 &&
    cookies.length === 0;

  writeJson(outputDir, "home-full-render-metadata.json", {
    fixture_url: fixtureUrl,
    viewport: VIEWPORT,
    expected_canvas: EXPECTED_CANVAS,
    canvas_box: box,
    ...pageState,
    console_errors: consoleErrors,
    page_errors: pageErrors,
    external_requests: externalRequests,
    all_requests: allRequests,
    cookies,
    result: passed ? "passed" : "stopped",
  });
  await browser.close();
  if (!passed) process.exitCode = 10;
}

main().catch((error) => {
  process.stderr.write(`ERROR: ${error.stack || error.message}\n`);
  process.exitCode = 2;
});
