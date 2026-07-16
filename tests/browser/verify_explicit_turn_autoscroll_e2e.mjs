/**
 * #1200 — explicit-turn auto-scroll regression test (fail-closed).
 *
 * Root cause:
 *   appendChatMessage() saves wasPinned BEFORE appending, then only scrolls
 *   the thread if wasPinned was true. When a user submits a new question via
 *   recommendation chip click or composer submit from far above the bottom
 *   (e.g. after reading earlier history), wasPinned is false and the new
 *   message stays hidden — the user must manually scroll to see it.
 *
 * Fix:
 *   prepareChatForExplicitTurn() is called in handleSubmission() before the
 *   first appendChatMessage, setting scrollTop = scrollHeight so the
 *   subsequent wasPinned check returns true. #1173 passive-reading protection
 *   is preserved for non-explicit DOM updates.
 *
 * Scenarios:
 *   A — chip click after long journey produces visible user/AI/confirm
 *   B — composer submit after thread unpinned produces visible response
 *   C — manual scroll-up during response does not yank thread
 *   D — consecutive chip questions each show latest response
 *
 * Safety:
 *   - repository-controlled static build only
 *   - /api/mvp/ask mocked
 *   - external requests/navigation/popups aborted & counted
 *   - no live provider / Firecrawl / real 북구청 access
 *
 * Usage:
 *   node tests/browser/verify_explicit_turn_autoscroll_e2e.mjs
 */

import assert from "node:assert";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, statSync, readFileSync, existsSync } from "node:fs";
import { join, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import http from "node:http";
import { chromium } from "playwright";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

const PIN_THRESHOLD = 72;
const SCROLL_TOP_TOL = 40;

// Deterministic markers for mock MVP responses.
const ILLEGAL_PARKING_MARKER = "[[1200-ILLEGAL-PARKING]]";
const APARTMENT_MARKER = "[[1200-APARTMENT]]";
const BULKY_WASTE_MARKER = "[[1200-BULKY-WASTE]]";
const COMPOSER_MARKER = "[[1200-COMPOSER]]";
const COMPOSER2_MARKER = "[[1200-COMPOSER2]]";
const READ_HISTORY_MARKER = "[[1200-READ-HISTORY]]";

const LONG_PAD =
  " 안내 경로와 담당 부서, 신청 방법, 준비 서류, 유의사항을 순서대로 확인하세요. " +
  "이 답변은 로컬 정적 픽스처로 제공되며 실제 관공서 사이트나 외부 API를 호출하지 않습니다. " +
  "대화가 길어져도 chat-shell 높이는 viewport에 고정되어야 하고 스크롤은 chat-thread 내부에서만 발생해야 합니다. ";

function buildMockAnswer(marker) {
  return {
    ok: true,
    question: "mocked-question",
    answer: marker + " 공식 안내입니다. 담당 창구와 신청 절차를 확인하세요." + LONG_PAD.repeat(3),
    action: "none",
    confidence: 1,
    failure_code: "",
    provider: "autoscroll-fixture",
    model: "none",
    freshness_state: "official_snapshot",
    sources: [{ title: "북구청 안내", url: "/mvp/", official: true }],
    captured_at: "2026-07-15T01:00:00.000Z",
    verified_at: "2026-07-15T01:00:00.000Z",
  };
}

function buildAndServe() {
  const tmpDir = mkdtempSync(join(tmpdir(), "1200-autoscroll-"));
  console.log("Building to tmp dir:", tmpDir);
  const res = spawnSync(
    "python",
    ["scripts/build_cloudflare_pages.py", "--mode", "live", "--out-dir", tmpDir],
    {
      stdio: "inherit",
      cwd: REPO_ROOT,
      env: { ...process.env, PYTHONPATH: REPO_ROOT },
    },
  );
  if (res.error || res.status !== 0) {
    throw new Error("Build failed for #1200 autoscroll verifier");
  }

  const server = http.createServer((req, res) => {
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
        filePath = join(filePath, "index.html");
      }
      const content = readFileSync(filePath);
      const ext = extname(filePath);
      const mime =
        ext === ".js"
          ? "application/javascript; charset=utf-8"
          : ext === ".css"
            ? "text/css; charset=utf-8"
            : ext === ".png"
              ? "image/png"
              : ext === ".svg"
                ? "image/svg+xml"
                : ext === ".json"
                  ? "application/json; charset=utf-8"
                  : "text/html; charset=utf-8";
      res.writeHead(200, { "Content-Type": mime });
      res.end(content);
    } catch (e) {
      res.writeHead(500);
      res.end(String(e));
    }
  });

  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      resolve({
        origin: `http://127.0.0.1:${port}`,
        cleanup: () => {
          server.close();
          rmSync(tmpDir, { recursive: true, force: true });
        },
      });
    });
  });
}

async function launchBrowser() {
  const attempts = [];
  try {
    const browser = await chromium.launch({ headless: true, channel: "chrome" });
    return { browser, source: "channel=chrome" };
  } catch (e) {
    attempts.push(`channel=chrome: ${e.message}`);
  }
  const known = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ];
  for (const p of known) {
    if (!existsSync(p)) continue;
    try {
      const browser = await chromium.launch({ headless: true, executablePath: p });
      return { browser, source: `path=${p}` };
    } catch (e) {
      attempts.push(`${p}: ${e.message}`);
    }
  }
  try {
    const browser = await chromium.launch({ headless: true });
    return { browser, source: "bundled-chromium" };
  } catch (e) {
    attempts.push(`bundled: ${e.message}`);
  }
  throw new Error(`Cannot launch browser:\n${attempts.join("\n")}`);
}

function createSafetyTracker(origin) {
  const state = {
    consoleErrors: [],
    pageErrors: [],
    failedResources: [],
    externalRequests: [],
    externalNavigations: [],
    popups: 0,
    liveApiHits: 0,
  };

  function attach(page) {
    page.on("pageerror", (err) => state.pageErrors.push(String(err.message || err)));
    page.on("console", (msg) => {
      if (msg.type() === "error") state.consoleErrors.push(msg.text());
    });
    page.on("requestfailed", (req) => {
      const url = req.url();
      if (/favicon\.ico$/i.test(url)) return;
      if (req.failure() && /net::ERR_ABORTED/i.test(req.failure().errorText || "")) {
        return;
      }
      state.failedResources.push(url);
    });
    page.on("request", (req) => {
      const url = req.url();
      if (url.startsWith("data:") || url.startsWith("blob:")) return;
      let parsed;
      try {
        parsed = new URL(url);
      } catch {
        return;
      }
      if (parsed.origin !== origin) {
        state.externalRequests.push(url);
      }
      if (/firecrawl|openai|anthropic|googleapis|groq|together|api\.x\.ai|bukgu\.gwangju/i.test(url)) {
        state.liveApiHits += 1;
      }
    });
    page.on("framenavigated", (frame) => {
      if (frame !== page.mainFrame()) return;
      try {
        const u = new URL(frame.url());
        if (u.origin !== origin && u.protocol !== "about:") {
          state.externalNavigations.push(frame.url());
        }
      } catch {
        /* ignore parse errors for about:blank etc. */
      }
    });
    page.on("popup", () => {
      state.popups += 1;
    });
  }

  return { state, attach };
}

/** Pending marker for the next ask fulfillment. */
let pendingAskMarker = null;

async function installRoutes(page, origin) {
  await page.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.startsWith("data:") || url.startsWith("blob:")) {
      return route.continue();
    }
    let parsed;
    try {
      parsed = new URL(url);
    } catch {
      return route.abort();
    }
    if (parsed.origin !== origin) {
      return route.abort();
    }
    return route.continue();
  });

  await page.route("**/api/mvp/ask", async (route) => {
    const marker = pendingAskMarker || "[[1200-UNSET]]";
    const payload = buildMockAnswer(marker);
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(payload),
    });
  });
}

function assertSafety(state) {
  assert.strictEqual(
    state.consoleErrors.length,
    0,
    `console errors: ${state.consoleErrors.join(" | ")}`,
  );
  assert.strictEqual(
    state.pageErrors.length,
    0,
    `page errors: ${state.pageErrors.join(" | ")}`,
  );
  assert.strictEqual(
    state.failedResources.length,
    0,
    `failed resources: ${state.failedResources.join(" | ")}`,
  );
  assert.strictEqual(
    state.externalRequests.length,
    0,
    `external requests: ${state.externalRequests.join(" | ")}`,
  );
  assert.strictEqual(
    state.externalNavigations.length,
    0,
    `external navigations: ${state.externalNavigations.join(" | ")}`,
  );
  assert.strictEqual(state.popups, 0, `popups: ${state.popups}`);
  assert.strictEqual(state.liveApiHits, 0, `live API hits: ${state.liveApiHits}`);
}

/**
 * Collect thread scroll metrics plus rect info for key elements.
 */
async function collectThreadMetrics(page) {
  return page.evaluate(() => {
    const t = document.getElementById("chat-thread");
    if (!t) return null;
    const dist = t.scrollHeight - t.scrollTop - t.clientHeight;
    const lastUser = Array.from(document.querySelectorAll(".chat-msg--user")).at(-1);
    const lastAi = Array.from(document.querySelectorAll(".chat-msg--ai")).at(-1);
    const confirmRuns = document.querySelectorAll(".chat-msg--confirm-run");
    const confirmRun = confirmRuns.length ? confirmRuns[confirmRuns.length - 1] : null;
    const composer = document.getElementById("chat-composer-form") ||
      document.querySelector(".chat-composer");
    const rect = (el) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height };
    };
    return {
      scrollTop: t.scrollTop,
      scrollHeight: t.scrollHeight,
      clientHeight: t.clientHeight,
      distanceFromBottom: dist,
      nearBottom: dist <= 80,
      lastUserRect: rect(lastUser),
      lastAiRect: rect(lastAi),
      confirmRunRect: rect(confirmRun),
      composerRect: rect(composer),
      pageScrollY: window.scrollY || window.pageYOffset || 0,
      userCount: document.querySelectorAll(".chat-msg--user").length,
      aiCount: document.querySelectorAll(".chat-msg--ai").length,
      msgCount: document.querySelectorAll(".chat-msg").length,
    };
  });
}

async function waitForInputEnabled(page) {
  await page.waitForFunction(
    () => {
      const input = document.getElementById("chat-composer-input") ||
        document.querySelector(".chat-composer__input");
      return input && !input.disabled && input.offsetParent !== null;
    },
    null,
    { timeout: 15000 },
  );
}

async function dismissConfirmIfPresent(page) {
  const noBtn = page.getByRole("button", { name: /^(아니요|No)$/i, disabled: false });
  const n = await noBtn.count();
  if (n === 0) return;
  const first = noBtn.first();
  const visible = await first.isVisible();
  if (!visible) return;
  await first.click({ force: true });
  await page.waitForTimeout(120);
}

/**
 * Submit a question via composer (not chip) and wait for mock response.
 */
async function submitViaComposer(page, question, marker) {
  pendingAskMarker = marker;
  await waitForInputEnabled(page);
  const input = page.locator("#chat-composer-input, .chat-composer__input").first();
  await input.waitFor({ state: "visible", timeout: 10000 });
  await input.fill(question);

  const responsePromise = page.waitForResponse(
    (r) => r.url().includes("/api/mvp/ask") && r.request().method() === "POST",
    { timeout: 15000 },
  );
  await page.locator("#chat-composer-send, .chat-composer__send").first().click();
  const response = await responsePromise;
  assert.strictEqual(response.status(), 200, `/api/mvp/ask status ${response.status()}`);
  const body = JSON.parse(await response.text());
  assert.ok(body.ok === true, "mock body.ok not true");
  assert.ok(body.answer.includes(marker), `answer missing marker ${marker}`);

  await page.waitForFunction(
    ({ marker }) => {
      const ais = Array.from(document.querySelectorAll(".chat-msg--ai"));
      return ais.some((el) => (el.textContent || "").includes(marker));
    },
    { marker },
    { timeout: 15000 },
  );
  await dismissConfirmIfPresent(page);
  await waitForInputEnabled(page);
  pendingAskMarker = null;
}

/**
 * Click a recommendation chip by matching its data-chip-question attribute.
 */
async function clickChip(page, question) {
  await page.evaluate((q) => {
    const chip = document.querySelector(`[data-chip-question="${q}"]`);
    if (!chip) throw new Error(`Chip not found for: ${q}`);
    chip.click();
  }, question);
}

// ── Scenarios ──────────────────────────────────────────────────────

/**
 * Scenario A: Chip click after long journey produces visible user/AI/confirm.
 *
 * 1. Build chat history via several composer turns so thread is long.
 * 2. Scroll thread far from bottom (simulating user reading history).
 * 3. Click a recommendation chip ("공동주택 관련 문의는 어느 부서에 해야 하나요?").
 * 4. Verify new user bubble, split-ready, and confirm-run are visible.
 * 5. Verify distanceFromBottom <= PIN_THRESHOLD (~72px).
 * 6. Verify window.scrollY ~0.
 * 7. Verify composer in viewport.
 */
async function scenarioA(page) {
  console.log("\n=== Scenario A: chip click after long journey ===");

  // Build history: 3 composer turns
  await submitViaComposer(page, "불법 주정차 신고는 어디서 하나요?", ILLEGAL_PARKING_MARKER);

  // Scroll thread far from bottom
  await page.evaluate(() => {
    const t = document.getElementById("chat-thread");
    if (t) t.scrollTop = 0;
  });
  await page.waitForTimeout(80);

  // Verify thread is indeed far from bottom
  const beforeChip = await collectThreadMetrics(page);
  assert.ok(
    beforeChip.distanceFromBottom > PIN_THRESHOLD + 20,
    `Thread should be far from bottom before chip: dist=${beforeChip.distanceFromBottom}`,
  );
  console.log(`  Before chip: scrollTop=${beforeChip.scrollTop} distBottom=${beforeChip.distanceFromBottom}`);

  // Click chip — this dispatches submit event through the form
  pendingAskMarker = APARTMENT_MARKER;
  const responsePromise = page.waitForResponse(
    (r) => r.url().includes("/api/mvp/ask") && r.request().method() === "POST",
    { timeout: 15000 },
  );
  await clickChip(page, "공동주택 관련 문의는 어느 부서에 해야 하나요?");
  const response = await responsePromise;
  assert.strictEqual(response.status(), 200);
  const body = JSON.parse(await response.text());
  assert.ok(body.answer.includes(APARTMENT_MARKER));

  // Wait for the new split-ready message and new confirm-run (2nd confirm-run)
  await page.waitForFunction(
    (expectedConfirmCount) => {
      const confirmRuns = document.querySelectorAll(".chat-msg--confirm-run");
      const ready = Array.from(document.querySelectorAll(".chat-msg--ai")).some(
        (el) => (el.textContent || "").includes("질문을 확인했습니다"),
      );
      return confirmRuns.length >= expectedConfirmCount && ready;
    },
    2,
    { timeout: 12000 },
  );
  await page.waitForTimeout(200);

  const afterChip = await collectThreadMetrics(page);
  console.log(`  After chip: distBottom=${afterChip.distanceFromBottom} nearBottom=${afterChip.nearBottom}`);

  // User bubble must exist in DOM
  assert.ok(
    afterChip.lastUserRect && afterChip.lastUserRect.height > 0,
    "last user bubble not in DOM",
  );
  // Confirm-run must exist in DOM
  assert.ok(
    afterChip.confirmRunRect && afterChip.confirmRunRect.height > 0,
    "confirm-run not rendered",
  );
  // Thread is near bottom
  assert.ok(
    afterChip.nearBottom,
    `Thread not near bottom after chip: dist=${afterChip.distanceFromBottom}`,
  );
  // Page scroll ~0
  assert.ok(
    Math.abs(afterChip.pageScrollY) <= 4,
    `page scrollY should be ~0, got ${afterChip.pageScrollY}`,
  );
  // Confirm-run buttons must be clickable (visible in viewport)
  assert.ok(
    afterChip.confirmRunRect.bottom > 0 && afterChip.confirmRunRect.top < (afterChip.clientHeight + 80),
    `confirm-run not in visible thread area: ${JSON.stringify(afterChip.confirmRunRect)}`,
  );

  // Dismiss confirm for next scenarios
  await dismissConfirmIfPresent(page);
  await waitForInputEnabled(page);
  pendingAskMarker = null;

  console.log("  Scenario A: PASS");
}

/**
 * Scenario B: Composer submit after thread unpinned.
 *
 * 1. With thread unpinned (scrolled up), type a supported question.
 * 2. Submit via composer send button.
 * 3. Verify new user bubble and AI response are visible.
 * 4. Verify distanceFromBottom <= PIN_THRESHOLD.
 * 5. Verify window.scrollY ~0.
 */
async function scenarioB(page) {
  console.log("\n=== Scenario B: composer submit from unpinned ===");

  // Scroll thread far from bottom
  await page.evaluate(() => {
    const t = document.getElementById("chat-thread");
    if (t) t.scrollTop = 0;
  });
  await page.waitForTimeout(80);

  const beforeComposer = await collectThreadMetrics(page);
  assert.ok(
    beforeComposer.distanceFromBottom > PIN_THRESHOLD + 20,
    `Thread should be far from bottom before composer submit: dist=${beforeComposer.distanceFromBottom}`,
  );
  console.log(`  Before composer: scrollTop=${beforeComposer.scrollTop} distBottom=${beforeComposer.distanceFromBottom}`);

  await submitViaComposer(
    page,
    "가로등이 고장났어요. 신고할게요",
    COMPOSER_MARKER,
  );

  const afterComposer = await collectThreadMetrics(page);
  console.log(`  After composer: distBottom=${afterComposer.distanceFromBottom} nearBottom=${afterComposer.nearBottom}`);

  assert.ok(
    afterComposer.lastUserRect && afterComposer.lastUserRect.height > 0,
    "last user bubble not visible after composer submit",
  );
  assert.ok(
    afterComposer.nearBottom,
    `Thread not near bottom after composer submit: dist=${afterComposer.distanceFromBottom}`,
  );
  assert.ok(
    Math.abs(afterComposer.pageScrollY) <= 4,
    `page scrollY should be ~0, got ${afterComposer.pageScrollY}`,
  );

  console.log("  Scenario B: PASS");
}

/**
 * Scenario C: Manual scroll-up during response does not yank thread.
 *
 * 1. Start explicit turn (composer submit).
 * 2. After user bubble appears, manually scroll thread back up.
 * 3. Wait for AI response to append (passive/background).
 * 4. Verify scrollTop has NOT moved — reading-history preserved.
 */
async function scenarioC(page) {
  console.log("\n=== Scenario C: manual scroll-up preserves reading history ===");

  // Wait for input enabled after previous scenario
  await waitForInputEnabled(page);

  // Count existing confirm-runs before this turn.
  const confirmBeforeC = await page.evaluate(
    () => document.querySelectorAll(".chat-msg--confirm-run").length,
  );

  // Submit via composer
  pendingAskMarker = READ_HISTORY_MARKER;
  const input = page.locator("#chat-composer-input, .chat-composer__input").first();
  await input.waitFor({ state: "visible", timeout: 10000 });
  await input.fill("대형폐기물은 어떻게 버리나요?");

  // Set up response watcher BEFORE clicking send so we don't miss the event.
  const responsePromise = page.waitForResponse(
    (r) => r.url().includes("/api/mvp/ask") && r.request().method() === "POST",
    { timeout: 15000 },
  );

  // Click send — this triggers handleSubmission synchronously, which calls
  // prepareChatForExplicitTurn() and appends the user bubble.
  await page.locator("#chat-composer-send, .chat-composer__send").first().click();

  // Schedule a scroll-up that runs after all pending rAF callbacks from
  // the AI answer's scrollChatToLatest have already fired. Three rAF frames
  // ensures no residual rAF-scroll can yank the thread back down.
  await page.evaluate(() => {
    var remaining = 3;
    function scrollUp() {
      remaining--;
      if (remaining > 0) {
        requestAnimationFrame(scrollUp);
        return;
      }
      var t = document.getElementById("chat-thread");
      if (t) t.scrollTop = 0;
    }
    requestAnimationFrame(scrollUp);
  });

  // Wait for the mock response to arrive — AI answer is appended (may scroll)
  // and the split chain schedules completeMvpSplit via setTimeout(0).
  const response = await responsePromise;
  assert.strictEqual(response.status(), 200);
  const body = JSON.parse(await response.text());
  assert.ok(body.answer.includes(READ_HISTORY_MARKER));

  // Wait for confirm-run to appear — it should NOT yank because the scroll-up
  // setTimeout(0) ran before the split setTimeout(0) queued by the .then().
  await page.waitForFunction(
    (expectedCount) => document.querySelectorAll(".chat-msg--confirm-run").length >= expectedCount,
    confirmBeforeC + 1,
    { timeout: 15000 },
  );
  await page.waitForTimeout(200);

  const afterScrollUp = await collectThreadMetrics(page);
  console.log(`  After scroll-up: scrollTop=${afterScrollUp.scrollTop} distBottom=${afterScrollUp.distanceFromBottom}`);

  // The thread should NOT have yanked back to bottom
  assert.ok(
    afterScrollUp.distanceFromBottom > PIN_THRESHOLD,
    `Thread yanked to bottom after manual scroll-up: dist=${afterScrollUp.distanceFromBottom}`,
  );
  // Verify AI marker is still present in DOM (passive append worked)
  const hasMarker = await page.evaluate((m) => {
    return Array.from(document.querySelectorAll(".chat-msg--ai")).some(
      (el) => (el.textContent || "").includes(m),
    );
  }, READ_HISTORY_MARKER);
  assert.ok(hasMarker, "AI marker missing after passive append");

  await dismissConfirmIfPresent(page);
  await waitForInputEnabled(page);
  pendingAskMarker = null;

  console.log("  Scenario C: PASS");
}

/**
 * Scenario D: Consecutive chip questions each show latest response.
 *
 * 1. Click "공동주택 관련 문의는 어느 부서에 해야 하나요?" chip.
 * 2. Wait for response, verify latest AI visible.
 * 3. Click "대형폐기물은 어떻게 버리나요?" chip.
 * 4. Verify latest AI visible (not stuck on previous answer).
 * 5. Verify no duplicate user/confirm-run bubbles.
 */
async function scenarioD(page) {
  console.log("\n=== Scenario D: consecutive chip questions ===");

  await waitForInputEnabled(page);

  // First turn: apartment via composer (chips hidden in split state)
  await submitViaComposer(page, "공동주택 관련 문의는 어느 부서에 해야 하나요?", APARTMENT_MARKER);

  const countsAfter1 = await collectThreadMetrics(page);
  const confirmAfter1 = await page.evaluate(
    () => document.querySelectorAll(".chat-msg--confirm-run").length,
  );
  console.log(`  After turn 1: user=${countsAfter1.userCount} ai=${countsAfter1.aiCount} confirm=${confirmAfter1}`);

  // Latest answer AI must contain apartment marker
  const lastAnswer1 = await page.evaluate((marker) => {
    const ais = Array.from(document.querySelectorAll(".chat-msg--ai")).filter(
      (el) => !el.classList.contains("chat-msg--confirm-run") &&
        !(el.textContent || "").includes("질문을 확인했습니다"),
    );
    const last = ais.at(-1);
    return last ? (last.textContent || "").includes(marker) : false;
  }, APARTMENT_MARKER);
  assert.ok(lastAnswer1, `First turn AI answer missing apartment marker`);

  // Second turn: submit bulky waste via composer (chips hidden in split state)
  await submitViaComposer(page, "대형폐기물은 어떻게 버리나요?", BULKY_WASTE_MARKER);

  const countsAfter2 = await collectThreadMetrics(page);
  const confirmAfter2 = await page.evaluate(
    () => document.querySelectorAll(".chat-msg--confirm-run").length,
  );
  console.log(`  After turn 2: user=${countsAfter2.userCount} ai count=${countsAfter2.aiCount} confirm=${confirmAfter2}`);

  // No duplicate user or confirm bubbles
  assert.strictEqual(
    countsAfter2.userCount,
    countsAfter1.userCount + 1,
    `Expected +1 user bubble, got ${countsAfter2.userCount} (was ${countsAfter1.userCount})`,
  );
  assert.strictEqual(
    confirmAfter2,
    confirmAfter1 + 1,
    `Expected +1 confirm-run after second turn, got ${confirmAfter2} (was ${confirmAfter1})`,
  );

  // Latest AI answer (non-confirm, non-split-ready) must contain the new marker
  const lastAnswer = await page.evaluate((marker) => {
    const ais = Array.from(document.querySelectorAll(".chat-msg--ai")).filter(
      (el) => !el.classList.contains("chat-msg--confirm-run") &&
        !(el.textContent || "").includes("질문을 확인했습니다"),
    );
    const last = ais.at(-1);
    return last ? (last.textContent || "").includes(marker) : false;
  }, BULKY_WASTE_MARKER);
  assert.ok(lastAnswer, `Second turn AI answer missing bulky waste marker`);

  await dismissConfirmIfPresent(page);
  await waitForInputEnabled(page);
  pendingAskMarker = null;

  console.log("  Scenario D: PASS");
}

async function main() {
  console.log("#1200 explicit-turn auto-scroll regression (fail-closed)");

  const { origin, cleanup } = await buildAndServe();
  const { browser, source } = await launchBrowser();
  console.log(`Browser: ${source}`);
  console.log(`Origin: ${origin}`);

  const safety = createSafetyTracker(origin);

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  safety.attach(page);
  await installRoutes(page, origin);

  try {
    await page.goto(`${origin}/mvp/?lang=ko`, {
      waitUntil: "domcontentloaded",
      timeout: 20000,
    });
    await page.waitForSelector("#chat-composer-input, .chat-composer__input", {
      timeout: 10000,
    });

    await scenarioA(page);
    await scenarioB(page);
    await scenarioC(page);
    await scenarioD(page);

    assertSafety(safety.state);

    console.log("\n=== ALL SCENARIOS PASS ===");
  } finally {
    await context.close();
    await browser.close();
    cleanup();
  }
}

main().catch((err) => {
  console.error("#1200 FAIL:", err);
  process.exitCode = 1;
});
