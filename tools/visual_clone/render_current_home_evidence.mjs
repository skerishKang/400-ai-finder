#!/usr/bin/env node
/**
 * Render local #868 home evidence without contacting an external origin.
 *
 * Preconditions:
 * - `playwright` must already be installed locally.
 * - The local static fixture must be served at a localhost/127.0.0.1 URL.
 *
 * This utility writes review artifacts only. It never edits product sources,
 * opens a remote URL, persists browser storage, or commits/pushes.
 */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const DEFAULT_OUTPUT = path.join(
  ROOT,
  "docs/artifacts/863-reference/render/5b60084"
);
const VIEWPORT = Object.freeze({ width: 1644, height: 756 });
const EXPECTED_CANVAS = Object.freeze({ width: 1344, height: 756 });

function parseArgs(argv) {
  const args = { baseUrl: null, outputDir: DEFAULT_OUTPUT };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--base-url") {
      args.baseUrl = argv[index + 1] || null;
      index += 1;
    } else if (value === "--output-dir") {
      args.outputDir = path.resolve(argv[index + 1] || "");
      index += 1;
    } else {
      throw new Error(`Unknown argument: ${value}`);
    }
  }
  if (!args.baseUrl) {
    throw new Error("--base-url is required");
  }
  return args;
}

function assertLocalFixture(baseUrl) {
  const url = new URL(baseUrl);
  const allowedHost = url.hostname === "127.0.0.1" || url.hostname === "localhost";
  if (url.protocol !== "http:" || !allowedHost) {
    throw new Error("Only http://localhost or http://127.0.0.1 local fixtures are allowed");
  }
  if (url.pathname !== "/static/citizen-action-demo.html") {
    throw new Error("Fixture path must be /static/citizen-action-demo.html");
  }
  return url;
}

function instrumentStorage() {
  const writes = [];
  const mark = (kind) => {
    writes.push(kind);
  };
  const methods = ["setItem", "removeItem", "clear"];
  for (const method of methods) {
    const original = Storage.prototype[method];
    Object.defineProperty(Storage.prototype, method, {
      configurable: true,
      value(...args) {
        mark(`${this === window.localStorage ? "localStorage" : "sessionStorage"}.${method}`);
        return original.apply(this, args);
      },
    });
  }
  window.__visualCloneStorageWrites = writes;
}

function writeMetadata(outputDir, metadata) {
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(
    path.join(outputDir, "home-render-metadata.json"),
    `${JSON.stringify(metadata, null, 2)}\n`,
    "utf8"
  );
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const fixtureUrl = assertLocalFixture(args.baseUrl);
  let chromium;
  try {
    ({ chromium } = require("playwright"));
  } catch (error) {
    throw new Error("Local playwright package is required; do not install packages during this task");
  }

  fs.mkdirSync(args.outputDir, { recursive: true });
  const consoleErrors = [];
  const pageErrors = [];
  const externalRequests = [];
  const allRequests = [];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 1,
  });
  await context.addInitScript(instrumentStorage);
  const page = await context.newPage();

  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    pageErrors.push(String(error));
  });
  page.on("request", (request) => {
    const url = request.url();
    allRequests.push(url);
    try {
      const parsed = new URL(url);
      const isLoopback = parsed.protocol === "http:" &&
        (parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost");
      if (!isLoopback) {
        externalRequests.push(url);
      }
    } catch {
      externalRequests.push(url);
    }
  });

  const normalUrl = fixtureUrl.toString();
  await page.goto(normalUrl, { waitUntil: "networkidle" });
  await page.waitForTimeout(250);
  const canvas = page.locator("#demo-canvas");
  const canvasBox = await canvas.boundingBox();
  if (!canvasBox) {
    throw new Error("#demo-canvas is not visible");
  }
  if (Math.round(canvasBox.width) !== EXPECTED_CANVAS.width ||
      Math.round(canvasBox.height) !== EXPECTED_CANVAS.height) {
    throw new Error(
      `Canvas geometry mismatch: ${JSON.stringify(canvasBox)}; expected ${EXPECTED_CANVAS.width}x${EXPECTED_CANVAS.height}`
    );
  }

  await canvas.screenshot({
    path: path.join(args.outputDir, "home-canvas-1344x756.png"),
  });
  await page.screenshot({
    path: path.join(args.outputDir, "home-split-1644x756.png"),
  });

  const reviewUrl = new URL(normalUrl);
  reviewUrl.searchParams.set("review", "true");
  await page.goto(reviewUrl.toString(), { waitUntil: "networkidle" });
  await page.waitForTimeout(250);
  const reviewCanvas = page.locator("#demo-canvas");
  await reviewCanvas.screenshot({
    path: path.join(args.outputDir, "home-canvas-review-1344x756.png"),
  });

  const storage = await page.evaluate(() => ({
    localStorageKeys: Object.keys(window.localStorage),
    sessionStorageKeys: Object.keys(window.sessionStorage),
    writes: window.__visualCloneStorageWrites || [],
  }));
  const cookies = await context.cookies([normalUrl]);
  const metadata = {
    fixture_url: normalUrl,
    review_url: reviewUrl.toString(),
    viewport: VIEWPORT,
    expected_canvas: EXPECTED_CANVAS,
    canvas_box: canvasBox,
    console_errors: consoleErrors,
    page_errors: pageErrors,
    external_requests: externalRequests,
    all_requests: allRequests,
    storage,
    cookies,
    result: "pending-gate-evaluation",
  };
  metadata.result = consoleErrors.length === 0 &&
    pageErrors.length === 0 &&
    externalRequests.length === 0 &&
    storage.writes.length === 0 &&
    storage.localStorageKeys.length === 0 &&
    storage.sessionStorageKeys.length === 0 &&
    cookies.length === 0
    ? "passed"
    : "stopped";
  writeMetadata(args.outputDir, metadata);
  await browser.close();

  if (metadata.result !== "passed") {
    process.stderr.write(`${JSON.stringify(metadata, null, 2)}\n`);
    process.exitCode = 10;
  }
}

main().catch((error) => {
  process.stderr.write(`ERROR: ${error.stack || error.message}\n`);
  process.exitCode = 2;
});
