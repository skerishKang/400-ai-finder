#!/usr/bin/env node
/**
 * verify_mvp_failure_fallback_e2e.mjs
 * MVP failure fallback contract (#1200).
 *
 * When a supported canonical question has a deterministic local action but the
 * MVP bridge/API fails, NO "error.aiUnavailable" bubble should appear.
 * The fallback deterministic journey (split + confirm-run) should proceed
 * directly. For unsupported questions with complete failure, the unavailable
 * bubble should appear exactly once.
 *
 * Scenarios:
 *   1. supported question + bridge missing (script 404)
 *   2. supported question + ask rejection (network error)
 *   3. supported question + result ok=false (200 with ok:false)
 *   4. unsupported question + complete failure (bridge missing)
 */

import { chromium } from "playwright";
import { createServer } from "http";
import { readFileSync, statSync, mkdtempSync } from "fs";
import { join, extname } from "path";
import { tmpdir } from "os";
import { spawnSync } from "child_process";
import assert from "assert/strict";

const BASE_PORT = 0; // dynamic ephemeral port
let BASE_ORIGIN;


// ── Support helpers ────────────────────────────────────────────────

function buildStatic(outDir) {
  const res = spawnSync(
    "python",
    [
      "scripts/build_cloudflare_pages.py",
      "--mode",
      "live",
      "--out-dir",
      outDir,
    ],
    {
      cwd: join(import.meta.dirname, "..", ".."),
      stdio: "pipe",
      timeout: 30000,
    }
  );
  if (res.error || res.status !== 0) {
    throw new Error(
      `Build failed: ${res.stderr?.toString?.() || res.error?.message}`
    );
  }
}

// ── Test runner ────────────────────────────────────────────────────

async function sendQuestionViaTyping(page, label, question) {
  const input = page.locator("#chat-composer-input");
  await input.waitFor({ state: "visible", timeout: 5000 });
  await input.fill(question);
  await page.locator("#chat-composer-send").click();
}

async function runViewport(browser, scenario) {
  const {
    label,
    question,
    chipSelector,
    mvpHandler,
    bridgeMissing,
    expectUnavailable,
    expectSplit,
  } = scenario;

  console.log(`[${label}] start`);
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  const consoleErrors = [];
  const pageErrors = [];
  const externalRequests = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      if (text.includes("ERR_BLOCKED_BY_CLIENT")) return;
      if (text.includes("ERR_CONNECTION_REFUSED")) return;
      consoleErrors.push(text);
    }
  });
  page.on("pageerror", (err) => pageErrors.push(err.message));
  page.on("request", (req) => {
    const url = req.url();
    if (!url.startsWith("data:") && new URL(url).origin !== BASE_ORIGIN) {
      externalRequests.push(url);
    }
  });

  await page.route("**/citizen-mvp-bridge.js", async (route) => {
    if (bridgeMissing) {
      await route.abort("blockedbyclient");
    } else {
      await route.continue();
    }
  });

  if (mvpHandler) {
    await page.route("**/api/mvp/ask", mvpHandler);
  }

  await page.goto(`${BASE_ORIGIN}/mvp/`, {
    waitUntil: "networkidle",
    timeout: 15000,
  });

  const shellTitle = page.locator(".chat-shell__title");
  await shellTitle.waitFor({ state: "visible", timeout: 5000 });
  assert.strictEqual(
    await shellTitle.innerText(),
    "AI 민원 네비게이터",
    `[${label}] shell title`
  );

  const badgeCount = await page.locator(".chat-shell__badge").count();
  assert.strictEqual(badgeCount, 0, `[${label}] badge absent`);

  // Submit the question via chip click or typed input
  if (chipSelector) {
    const chip = page.locator(chipSelector).first();
    await chip.waitFor({ state: "visible", timeout: 5000 });
    await chip.click();
  } else {
    await sendQuestionViaTyping(page, label, question);
  }

  // Wait for user message to appear
  const userMsg = page.locator(".chat-msg--user");
  await userMsg.first().waitFor({ state: "visible", timeout: 8000 });
  await page.waitForTimeout(500);

  const userCount = await userMsg.count();
  assert.strictEqual(
    userCount,
    1,
    `[${label}] user message count: ${userCount}`
  );

  // Wait for the journey to settle (split animation, bridge response)
  if (expectSplit) {
    await page.waitForTimeout(2000);
  } else {
    await page.waitForTimeout(1000);
  }

  // Count unavailable error bubbles
  const allAiBubbles = page.locator(".chat-msg--ai .chat-bubble--ai");
  const allTexts = await allAiBubbles.allTextContents();
  const uvBubbles = allTexts.filter((t) => t.includes("연결하지 못했습니다"));

  if (expectUnavailable) {
    assert.strictEqual(
      uvBubbles.length,
      1,
      `[${label}] unavailable: ${JSON.stringify(uvBubbles)}`
    );
  } else {
    assert.strictEqual(
      uvBubbles.length,
      0,
      `[${label}] unexpected unavailable: ${JSON.stringify(uvBubbles)}`
    );
  }

  // Verify split.ready appears exactly once when expected
  if (expectSplit) {
    const readyBubbles = allTexts.filter((t) =>
      t.includes("질문을 확인했습니다")
    );
    const readyCount = readyBubbles.length;
    assert.strictEqual(
      readyCount,
      1,
      `[${label}] split.ready count: ${readyCount} (texts: ${JSON.stringify(readyBubbles)})`
    );

    // Verify confirm-run message after split-ready
    const confirmBubbles = allTexts.filter((t) => t.includes("안내해 드릴까요"));
    assert.strictEqual(
      confirmBubbles.length,
      1,
      `[${label}] confirm-run count: ${confirmBubbles.length}`
    );
  }

  // Verify 0 console/page errors
  assert.strictEqual(
    consoleErrors.length,
    0,
    `[${label}] console: ${JSON.stringify(consoleErrors)}`
  );
  assert.strictEqual(
    pageErrors.length,
    0,
    `[${label}] page: ${JSON.stringify(pageErrors)}`
  );

  // Verify 0 external requests
  assert.strictEqual(
    externalRequests.length,
    0,
    `[${label}] external: ${JSON.stringify(externalRequests)}`
  );

  console.log(`[${label}] PASS`);
  await context.close();
}

async function main() {
  // Build to temp directory
  const tmpDir = mkdtempSync(join(tmpdir(), "mvp-fallback-e2e-"));
  console.log(`Building to tmp dir: ${tmpDir}`);
  buildStatic(tmpDir);

  const server = createServer((req, res) => {
    try {
      const urlPath = new URL(req.url, "http://127.0.0.1").pathname;
      let filePath = join(tmpDir, urlPath === "/" ? "index.html" : urlPath);
      let stat;
      try {
        stat = statSync(filePath);
      } catch {
        try {
          stat = statSync(filePath + ".html");
          filePath = filePath + ".html";
        } catch {
          try {
            stat = statSync(join(filePath, "index.html"));
            filePath = join(filePath, "index.html");
          } catch {
            res.writeHead(404);
            res.end("Not found");
            return;
          }
        }
      }
      if (stat.isDirectory()) {
        try {
          stat = statSync(join(filePath, "index.html"));
          filePath = join(filePath, "index.html");
        } catch {
          res.writeHead(404);
          res.end("Not found");
          return;
        }
      }
      const content = readFileSync(filePath);
      const ext = extname(filePath);
      const mime = ext === ".js" ? "application/javascript" : ext === ".css" ? "text/css" : "text/html; charset=utf-8";
      res.writeHead(200, { "Content-Type": mime });
      res.end(content);
    } catch (e) {
      res.writeHead(500);
      res.end(e.toString());
    }
  });

  await new Promise((resolve) => server.listen(BASE_PORT, "127.0.0.1", () => {
    const port = server.address().port;
    BASE_ORIGIN = `http://127.0.0.1:${port}`;
    console.log(`Server: ${BASE_ORIGIN}`);
    resolve();
  }));

  const browser = await chromium.launch({ channel: "chrome" });

  try {
    // ── Scenario 1: supported question + bridge missing ───────────
    await runViewport(browser, {
      label: "bridge-missing-illegal-parking",
      question: "불법 주정차 신고는 어디서 하나요?",
      chipSelector: '[data-chip-question="불법 주정차 신고는 어디서 하나요?"]',
      bridgeMissing: true,
      expectUnavailable: false,
      expectSplit: true,
    });

    // ── Scenario 2: supported question + ask rejection ────────────
    await runViewport(browser, {
      label: "ask-rejection-apartment",
      question: "공동주택 관련 문의는 어느 부서에 해야 하나요?",
      chipSelector: '[data-chip-question="공동주택 관련 문의는 어느 부서에 해야 하나요?"]',
      bridgeMissing: false,
      mvpHandler: async (route) => {
        await route.abort("connectionrefused");
      },
      expectUnavailable: false,
      expectSplit: true,
    });

    // ── Scenario 3: supported question + result ok=false ──────────
    await runViewport(browser, {
      label: "result-okfalse-bulky-waste",
      question: "매트리스 폐기 신청은 어디서 하나요?",
      chipSelector: '[data-chip-question="매트리스 폐기 신청은 어디서 하나요?"]',
      bridgeMissing: false,
      mvpHandler: async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json; charset=utf-8",
          body: JSON.stringify({
            ok: false,
            answer: "",
            action: "",
            confidence: 0,
            failure_code: "model_error",
          }),
        });
      },
      expectUnavailable: false,
      expectSplit: true,
    });

    // ── Scenario 4: unsupported question + complete failure ───────
    // Type an unsupported question in the input and submit
    await runViewport(browser, {
      label: "unsupported-failure",
      question: "이 동네 맛집 추천해 주세요",
      chipSelector: null, // will type it
      bridgeMissing: true,
      expectUnavailable: true,
      expectSplit: false,
    });

    console.log("\nAll MVP failure fallback tests PASSED.");
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
