#!/usr/bin/env node
/**
 * Verify the visible #870 split chat shell against the local fixture only.
 * No product files are edited. The result is review evidence, not a release gate.
 */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const VIEWPORT = Object.freeze({ width: 1644, height: 756 });
const EXPECTED = Object.freeze({ canvasWidth: 1344, chatWidth: 300 });
const REQUIRED_TURNS = Object.freeze([
  "불법 주정차 신고는 어디서 하나요?",
  "북구청 홈페이지에서 신고 경로를 확인하겠습니다.",
  "종합민원 메뉴에서 온라인 민원신청 경로를 찾고 있습니다.",
]);
const FORBIDDEN_COPY = "잠시만 기다려 주세요.";

function parseArgs(argv) {
  const result = { baseUrl: null, output: null };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--base-url") {
      result.baseUrl = argv[index + 1] || null;
      index += 1;
    } else if (arg === "--output") {
      result.output = argv[index + 1] || null;
      index += 1;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  if (!result.baseUrl || !result.output) {
    throw new Error("--base-url and --output are required");
  }
  return result;
}

function requireLocalFixture(baseUrl) {
  const url = new URL(baseUrl);
  const localHost = url.hostname === "localhost" || url.hostname === "127.0.0.1";
  if (!localHost || url.protocol !== "http:" || url.pathname !== "/static/citizen-action-demo.html") {
    throw new Error("Only the http localhost/127.0.0.1 citizen-action local fixture is allowed");
  }
  return url.toString();
}

function writeResult(output, value) {
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const fixtureUrl = requireLocalFixture(args.baseUrl);
  let chromium;
  try {
    ({ chromium } = require("playwright"));
  } catch {
    throw new Error("Local playwright package is required; package installation is not allowed");
  }

  const consoleErrors = [];
  const pageErrors = [];
  const externalRequests = [];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 });
  await context.addInitScript(() => {
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
    window.__splitChatStorageWrites = writes;
  });
  const page = await context.newPage();
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(String(error)));
  page.on("request", (request) => {
    const parsed = new URL(request.url());
    const isLocal = parsed.protocol === "http:" &&
      (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1");
    if (!isLocal) externalRequests.push(request.url());
  });

  await page.goto(fixtureUrl, { waitUntil: "networkidle" });
  await page.waitForTimeout(250);
  const inspection = await page.evaluate(({ expected, requiredTurns, forbiddenCopy }) => {
    const rect = (selector) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const box = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return {
        x: Math.round(box.x), y: Math.round(box.y),
        width: Math.round(box.width), height: Math.round(box.height),
        display: style.display, visibility: style.visibility,
      };
    };
    const chat = document.querySelector("#chat-shell");
    const rail = document.querySelector("#copilot-rail");
    const composer = document.querySelector(".chat-composer__send");
    const text = chat ? chat.textContent.replace(/\s+/g, " ").trim() : "";
    const turnOffsets = requiredTurns.map((turn) => text.indexOf(turn));
    const checks = {
      canvas_geometry: (() => {
        const value = rect("#demo-canvas");
        return Boolean(value && value.x === 0 && value.width === expected.canvasWidth && value.height === 756);
      })(),
      chat_geometry: (() => {
        const value = rect("#chat-shell");
        return Boolean(value && value.x === expected.canvasWidth && value.width === expected.chatWidth && value.height === 756 && value.display !== "none" && value.visibility !== "hidden");
      })(),
      approved_turns: turnOffsets.every((offset) => offset >= 0) && turnOffsets.every((offset, index) => index === 0 || offset > turnOffsets[index - 1]),
      forbidden_waiting_copy_absent: !text.includes(forbiddenCopy),
      disabled_korean_send: Boolean(composer && composer.disabled && composer.textContent.trim() === "보내기"),
      legacy_rail_hidden: Boolean(rail && window.getComputedStyle(rail).display === "none"),
    };
    return {
      canvas: rect("#demo-canvas"),
      chat_shell: rect("#chat-shell"),
      legacy_rail: rect("#copilot-rail"),
      chat_text: text,
      turn_offsets: turnOffsets,
      checks,
      storage: {
        localStorageKeys: Object.keys(window.localStorage),
        sessionStorageKeys: Object.keys(window.sessionStorage),
        writes: window.__splitChatStorageWrites || [],
      },
    };
  }, { expected: EXPECTED, requiredTurns: REQUIRED_TURNS, forbiddenCopy: FORBIDDEN_COPY });
  const cookies = await context.cookies([fixtureUrl]);
  const passed = Object.values(inspection.checks).every(Boolean) &&
    consoleErrors.length === 0 && pageErrors.length === 0 && externalRequests.length === 0 &&
    inspection.storage.writes.length === 0 && inspection.storage.localStorageKeys.length === 0 &&
    inspection.storage.sessionStorageKeys.length === 0 && cookies.length === 0;
  const output = {
    fixture_url: fixtureUrl,
    viewport: VIEWPORT,
    expected: EXPECTED,
    ...inspection,
    console_errors: consoleErrors,
    page_errors: pageErrors,
    external_requests: externalRequests,
    cookies,
    result: passed ? "passed" : "stopped",
  };
  writeResult(args.output, output);
  await browser.close();
  if (!passed) process.exitCode = 10;
}

main().catch((error) => {
  process.stderr.write(`ERROR: ${error.stack || error.message}\n`);
  process.exitCode = 2;
});
