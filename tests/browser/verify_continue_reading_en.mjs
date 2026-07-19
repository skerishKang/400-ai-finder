/**
 * E2E: English MVP "Continue reading" + settled-state baseline/feature parity.
 *
 * Settled state = long MVP answer + split.ready + confirm-run (Yes/No) present.
 * Not a 3-message early capture.
 *
 * Production JS/CSS are not modified by this harness.
 *
 * Usage:
 *   node tests/browser/verify_continue_reading_en.mjs
 */

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import http from "node:http";
import { tmpdir } from "node:os";
import { dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const SCREEN_DIR = join(REPO_ROOT, "artifacts", "continue-reading-en");
const QUESTION =
  "Where can residents use an unmanned civil document kiosk in Buk-gu?";

const ENGLISH_LONG_ANSWER = [
  "# Unmanned Civil Document Kiosk Guide (Buk-gu)",
  "",
  "Buk-gu residents can issue selected certificates at unmanned civil document kiosks without waiting at a service counter. These machines are intended for standard certificates that do not require in-person counseling.",
  "",
  "## Where to go",
  "Kiosks are installed at Buk-gu Office and at designated community facilities. Hours may differ by location, so check the posted machine schedule before you travel. Bring a valid resident registration card or other accepted identification.",
  "",
  "## What you may need",
  "Prepare your identification card, and if a fee applies, a card payment method accepted by the machine. Some certificates require additional verification steps shown on the kiosk screen.",
  "",
  "## Typical steps",
  "1. Select the certificate type on the touch screen.",
  "2. Authenticate with your identification as instructed by the machine.",
  "3. Confirm the personal details shown on screen carefully.",
  "4. Pay any required fee and wait for printing to finish.",
  "5. Collect both the printed certificate and your identification card before leaving.",
  "",
  "## Cautions",
  "If the machine is offline, displays an error, or cannot complete authentication, use the civil service counter during office hours instead of forcing a retry. Do not leave personal documents on the tray.",
  "",
  "This guidance summarizes the standard unmanned kiosk flow for Buk-gu residents. For exceptions, restricted certificates, or special status documents, staff assistance at the official counter is required.",
].join("\n");

/** Same stub for baseline + feature; action triggers split + confirm-run. */
const FIXTURE = Object.freeze({
  ok: true,
  answer: ENGLISH_LONG_ANSWER,
  action: "unmanned_kiosk",
  confidence: 1,
  failure_code: "",
  provider: "continue-reading-fixture",
  model: "none",
  freshness_state: "official_snapshot",
  sources: [],
  captured_at: "2026-07-15T01:00:00.000Z",
  verified_at: "2026-07-15T01:00:00.000Z",
});

const SPLIT_READY_EN =
  "I have your question. The Bukgu-gu guide screen is now open on the left.";
const YES_GUIDE_EN = "Yes, please guide me";
const NO_EN = "No";
const CHOREO_DONE_SNIPPET = "안내를 마쳤습니다";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".json": "application/json",
  ".woff2": "font/woff2",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
};

function gitShow(pathInRepo) {
  const r = spawnSync("git", ["show", `origin/main:${pathInRepo}`], {
    cwd: REPO_ROOT,
    encoding: "utf8",
    maxBuffer: 12 * 1024 * 1024,
  });
  if (r.status !== 0) throw new Error(`git show failed for ${pathInRepo}`);
  return r.stdout;
}

function buildTo(outDir) {
  const res = spawnSync(
    process.platform === "win32" ? "python" : "python3",
    ["scripts/build_cloudflare_pages.py", "--mode", "live", "--out-dir", outDir],
    {
      cwd: REPO_ROOT,
      env: { ...process.env, PYTHONPATH: REPO_ROOT },
      encoding: "utf8",
    },
  );
  if (res.status !== 0) {
    console.error(res.stdout || "");
    console.error(res.stderr || "");
    throw new Error("build_cloudflare_pages failed");
  }
}

function startServer(rootDir) {
  const server = http.createServer((req, res) => {
    try {
      const urlPath = new URL(req.url || "/", "http://127.0.0.1").pathname;
      const rel =
        urlPath === "/"
          ? "index.html"
          : urlPath.replace(/^\/+/, "").replace(/\/+$/, "") || "index.html";
      let filePath = join(rootDir, rel);
      if (!filePath.startsWith(rootDir)) {
        res.writeHead(403);
        res.end("Forbidden");
        return;
      }
      let st;
      try {
        st = statSync(filePath);
      } catch {
        try {
          st = statSync(filePath + ".html");
          filePath = filePath + ".html";
        } catch {
          try {
            st = statSync(join(filePath, "index.html"));
            filePath = join(filePath, "index.html");
          } catch {
            res.writeHead(404);
            res.end("Not found");
            return;
          }
        }
      }
      if (st.isDirectory()) filePath = join(filePath, "index.html");
      const content = readFileSync(filePath);
      res.writeHead(200, {
        "Content-Type":
          MIME[extname(filePath).toLowerCase()] || "application/octet-stream",
      });
      res.end(content);
    } catch (err) {
      res.writeHead(500);
      res.end(String(err));
    }
  });
  return new Promise((resolve, reject) => {
    server.listen(0, "127.0.0.1", () => {
      resolve({
        server,
        baseUrl: `http://127.0.0.1:${server.address().port}`,
      });
    });
    server.on("error", reject);
  });
}

async function launchBrowser() {
  return chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
}

async function installAskStub(page) {
  await page.route("**/api/mvp/ask", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(FIXTURE),
    });
  });
}

async function gotoMvp(page, baseUrl, locale) {
  await page.goto(`${baseUrl}/mvp/?lang=${locale}&mvp=1`, {
    waitUntil: "commit",
    timeout: 30000,
  });
  await page.waitForFunction(
    (loc) =>
      document.body &&
      document.getElementById("chat-thread") &&
      document.body.getAttribute("data-first-use-state") === "entry" &&
      window.CitizenI18n &&
      window.CitizenI18n.getLocale() === loc,
    locale,
    { timeout: 20000 },
  );
}

async function extractMessages(page) {
  return page.evaluate(() => {
    const thread = document.getElementById("chat-thread");
    if (!thread) return [];
    return Array.from(thread.querySelectorAll(".chat-msg")).map((el) => {
      const role = el.classList.contains("chat-msg--user")
        ? "user"
        : el.classList.contains("chat-msg--ai")
          ? "ai"
          : "other";
      const buttons = Array.from(el.querySelectorAll("button")).map((b) =>
        (b.textContent || "").trim(),
      );
      return {
        role,
        className: el.className,
        textContent: (el.textContent || "").trim(),
        buttonLabels: buttons,
        isTemp: el.classList.contains("chat-msg--temp"),
      };
    });
  });
}

async function buttonState(page) {
  return page.evaluate(() => {
    const btn = document.querySelector(".chat-continue-read");
    if (!btn) return { present: false, visible: false };
    const style = window.getComputedStyle(btn);
    const visible =
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      Number(style.opacity || "1") > 0;
    const thread = document.getElementById("chat-thread");
    const chips = document.getElementById("chat-chips");
    const composer = document.getElementById("chat-composer-form");
    const br = btn.getBoundingClientRect();
    const overlap = (a, bEl) => {
      if (!bEl) return false;
      const b = bEl.getBoundingClientRect();
      return !(
        a.right <= b.left ||
        a.left >= b.right ||
        a.bottom <= b.top ||
        a.top >= b.bottom
      );
    };
    return {
      present: true,
      visible,
      text: (btn.textContent || "").trim(),
      aria: btn.getAttribute("aria-label"),
      buttonType: btn.getAttribute("type"),
      inThread: !!(thread && thread.contains(btn)),
      overlapsChips: overlap(br, chips),
      overlapsComposer: overlap(br, composer),
      remaining: thread
        ? thread.scrollHeight - thread.scrollTop - thread.clientHeight
        : 0,
      scrollTop: thread ? thread.scrollTop : 0,
      clientHeight: thread ? thread.clientHeight : 0,
      scrollHeight: thread ? thread.scrollHeight : 0,
    };
  });
}

/**
 * Wait for true settled state: detailed answer + split.ready + confirm-run Yes/No.
 * No fixed-sleep success.
 */
async function waitForSettledConfirmRun(page) {
  await page.waitForFunction(
    ({ answerSnippet, splitReady, yesLabel, noLabel }) => {
      const thread = document.getElementById("chat-thread");
      if (!thread) return false;
      const text = thread.textContent || "";
      if (!text.includes(answerSnippet)) return false;
      if (!text.includes(splitReady)) return false;
      const confirm = thread.querySelector(
        '.chat-msg--confirm-run, .chat-msg[data-msg-type="confirm-run"]',
      );
      if (!confirm) return false;
      const labels = Array.from(confirm.querySelectorAll("button")).map((b) =>
        (b.textContent || "").trim(),
      );
      if (!labels.includes(yesLabel) || !labels.includes(noLabel)) return false;
      // No temp thinking bubbles left in thread
      if (thread.querySelector(".chat-msg--temp")) return false;
      // Layout should have completed split (or at least left entry)
      const st = document.body.getAttribute("data-first-use-state");
      if (st !== "split" && st !== "transitioning") {
        // allow split; transitioning mid-flight is not settled
        if (st !== "split") return false;
      }
      return st === "split";
    },
    {
      answerSnippet: "Unmanned Civil Document Kiosk Guide",
      splitReady: SPLIT_READY_EN,
      yesLabel: YES_GUIDE_EN,
      noLabel: NO_EN,
    },
    { timeout: 25000 },
  );
}

async function submitAndSettle(page, baseUrl, label) {
  await installAskStub(page);
  await gotoMvp(page, baseUrl, "en");

  // Initial: no continue button
  let st = await buttonState(page);
  assert.equal(st.present, false, `[${label}] initial EN: no continue button`);

  await page.locator("#chat-composer-input").fill(QUESTION);
  await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes("/api/mvp/ask") && r.status() === 200,
      { timeout: 15000 },
    ),
    page.locator("#chat-composer-send").click(),
  ]);

  // Detailed answer appears first (may still be before split completes)
  await page.waitForFunction(
    (snippet) => {
      const t = document.getElementById("chat-thread");
      return t && t.textContent && t.textContent.includes(snippet);
    },
    "Unmanned Civil Document Kiosk Guide",
    { timeout: 15000 },
  );

  // Explicit settled DOM — not sleep-based
  await waitForSettledConfirmRun(page);

  const messages = await extractMessages(page);
  assert.ok(messages.length >= 5, `[${label}] settled needs greeting+user+answer+ready+confirm (≥5), got ${messages.length}`);
  assert.ok(
    messages.every((m) => m.isTemp === false),
    `[${label}] no temp messages in settled array`,
  );
  assert.ok(
    messages.every((m) => (m.textContent || "").trim().length > 0),
    `[${label}] no empty message bubbles`,
  );

  // Structure assertions common to both
  const roles = messages.map((m) => m.role);
  assert.equal(roles[0], "ai", "greeting ai");
  assert.equal(roles[1], "user", "user question");
  assert.ok(
    messages.some((m) => m.textContent.includes("Unmanned Civil Document Kiosk Guide")),
    "detailed answer present",
  );
  assert.ok(
    messages.some((m) => m.textContent.includes(SPLIT_READY_EN)),
    "split.ready present",
  );
  const confirm = messages.find(
    (m) =>
      m.className.includes("confirm-run") ||
      m.buttonLabels.includes(YES_GUIDE_EN),
  );
  assert.ok(confirm, "confirm-run message present");
  assert.ok(confirm.buttonLabels.includes(YES_GUIDE_EN));
  assert.ok(confirm.buttonLabels.includes(NO_EN));

  st = await buttonState(page);
  return { messages, continueBtn: st };
}

function assertMessageParity(baseline, feature, tag) {
  assert.equal(
    feature.length,
    baseline.length,
    `${tag}: message count ${feature.length} vs ${baseline.length}`,
  );
  for (let i = 0; i < baseline.length; i++) {
    const b = baseline[i];
    const f = feature[i];
    assert.equal(f.role, b.role, `${tag} role@${i}`);
    assert.equal(f.className, b.className, `${tag} className@${i}`);
    assert.equal(f.textContent, b.textContent, `${tag} text@${i}`);
    assert.deepEqual(f.buttonLabels, b.buttonLabels, `${tag} buttons@${i}`);
    assert.equal(f.isTemp, b.isTemp, `${tag} isTemp@${i}`);
  }
}

async function main() {
  assert.ok(
    ENGLISH_LONG_ANSWER.length >= 1200 && ENGLISH_LONG_ANSWER.length <= 2000,
  );
  const lines = ENGLISH_LONG_ANSWER.split("\n").filter(Boolean);
  assert.equal(new Set(lines).size, lines.length, "no repeated fixture lines");

  mkdirSync(SCREEN_DIR, { recursive: true });

  const featureDir = mkdtempSync(join(tmpdir(), "cr-feature-"));
  const baselineDir = mkdtempSync(join(tmpdir(), "cr-baseline-"));
  console.log("Building feature →", featureDir);
  buildTo(featureDir);

  console.log("Preparing baseline (origin/main shell assets)");
  spawnSync("cp", ["-a", `${featureDir}/.`, baselineDir], { stdio: "inherit" });
  writeFileSync(
    join(baselineDir, "static/citizen-first-use-shell.js"),
    gitShow("src/web/static/citizen-first-use-shell.js"),
  );
  writeFileSync(
    join(baselineDir, "static/citizen-first-use-shell.css"),
    gitShow("src/web/static/citizen-first-use-shell.css"),
  );
  assert.ok(
    !readFileSync(
      join(baselineDir, "static/citizen-first-use-shell.js"),
      "utf8",
    ).includes("chat-continue-read"),
  );

  const featureSrv = await startServer(featureDir);
  const baselineSrv = await startServer(baselineDir);
  console.log("feature", featureSrv.baseUrl, "baseline", baselineSrv.baseUrl);

  const browser = await launchBrowser();
  const report = {
    fixtureChars: ENGLISH_LONG_ANSWER.length,
    settledBaseline: null,
    settledFeature: null,
    settledParity: null,
    choreoBaseline: null,
    choreoFeature: null,
    choreoParity: null,
  };

  try {
    // ── Settled baseline ──
    let baselineSettled;
    {
      const ctx = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        reducedMotion: "reduce",
      });
      const page = await ctx.newPage();
      baselineSettled = await submitAndSettle(
        page,
        baselineSrv.baseUrl,
        "baseline",
      );
      assert.equal(
        baselineSettled.continueBtn.present,
        false,
        "baseline: no continue button",
      );
      report.settledBaseline = baselineSettled.messages;
      await page.screenshot({
        path: join(SCREEN_DIR, "baseline-english-mvp-answer.png"),
        fullPage: false,
      });
      console.log(
        "[baseline settled] messages:",
        baselineSettled.messages.length,
      );
      await ctx.close();
    }

    // ── Settled feature + continue-reading scenarios + confirm screenshot ──
    let featureSettled;
    let featurePage;
    let featureCtx;
    {
      featureCtx = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        reducedMotion: "reduce",
      });
      featurePage = await featureCtx.newPage();
      featureSettled = await submitAndSettle(
        featurePage,
        featureSrv.baseUrl,
        "feature",
      );
      report.settledFeature = featureSettled.messages;

      // Settled parity (must be > 3 messages)
      assertMessageParity(
        report.settledBaseline,
        report.settledFeature,
        "settled",
      );
      report.settledParity = "MATCH";
      console.log(
        "[settled parity] MATCH count=",
        report.settledFeature.length,
      );

      // A: pinned bottom after settle → continue button hidden (may be present)
      let st = await buttonState(featurePage);
      // scroll to bottom to ensure pin
      await featurePage.evaluate(() => {
        const t = document.getElementById("chat-thread");
        t.scrollTop = t.scrollHeight;
        t.dispatchEvent(new Event("scroll"));
      });
      await featurePage.waitForTimeout(200);
      st = await buttonState(featurePage);
      assert.equal(st.present, true, "A: feature armed button exists");
      assert.equal(st.visible, false, "A: hidden at bottom");
      assert.equal(st.inThread, false, "button outside chat-thread");
      assert.equal(st.buttonType, "button");
      assert.equal(st.aria, "Continue reading");

      // B: scroll up → show
      await featurePage.evaluate(() => {
        const t = document.getElementById("chat-thread");
        t.scrollTop = Math.max(0, t.scrollTop - t.clientHeight * 0.9);
        t.dispatchEvent(new Event("scroll"));
      });
      await featurePage.waitForFunction(
        () => {
          const btn = document.querySelector(".chat-continue-read");
          if (!btn) return false;
          const t = document.getElementById("chat-thread");
          const rem = t.scrollHeight - t.scrollTop - t.clientHeight;
          return rem > 8 && window.getComputedStyle(btn).display !== "none";
        },
        null,
        { timeout: 5000 },
      );
      st = await buttonState(featurePage);
      assert.equal(st.visible, true, "B: visible mid-scroll");
      assert.ok(st.remaining > 8, "B: remainingScroll > 8");
      assert.equal(st.overlapsChips, false);
      assert.equal(st.overlapsComposer, false);

      await featurePage.screenshot({
        path: join(SCREEN_DIR, "feature-english-midscroll-continue.png"),
        fullPage: false,
      });

      // C: click → ~80%
      const beforeTop = st.scrollTop;
      const clientH = st.clientHeight;
      await featurePage.locator(".chat-continue-read").click();
      await featurePage.waitForTimeout(400);
      st = await buttonState(featurePage);
      assert.ok(
        st.scrollTop - beforeTop > clientH * 0.5,
        `C: scroll delta ${st.scrollTop - beforeTop} vs ${clientH}`,
      );

      // D: end → hide; confirm-run still present
      await featurePage.evaluate(() => {
        const t = document.getElementById("chat-thread");
        t.scrollTop = t.scrollHeight;
        t.dispatchEvent(new Event("scroll"));
      });
      await featurePage.waitForFunction(
        () => {
          const btn = document.querySelector(".chat-continue-read");
          if (!btn) return true;
          return window.getComputedStyle(btn).display === "none";
        },
        null,
        { timeout: 5000 },
      );
      st = await buttonState(featurePage);
      assert.equal(st.visible, false, "D: hidden at end");
      // confirm-run + split.ready still in DOM
      const stillSettled = await featurePage.evaluate(
        ({ splitReady, yesLabel }) => {
          const thread = document.getElementById("chat-thread");
          const text = thread ? thread.textContent || "" : "";
          const confirm = thread && thread.querySelector(".chat-msg--confirm-run");
          const labels = confirm
            ? Array.from(confirm.querySelectorAll("button")).map((b) =>
                (b.textContent || "").trim(),
              )
            : [];
          return {
            hasSplit: text.includes(splitReady),
            hasYes: labels.includes(yesLabel),
            confirmPresent: !!confirm,
          };
        },
        { splitReady: SPLIT_READY_EN, yesLabel: YES_GUIDE_EN },
      );
      assert.equal(stillSettled.hasSplit, true, "D: split.ready preserved");
      assert.equal(stillSettled.confirmPresent, true, "D: confirm-run preserved");
      assert.equal(stillSettled.hasYes, true, "D: Yes button preserved");

      await featurePage.screenshot({
        path: join(SCREEN_DIR, "feature-english-answer-end.png"),
        fullPage: false,
      });

      // Confirm-run preserved visual: scroll so answer end + confirm visible
      await featurePage.evaluate(() => {
        const confirm = document.querySelector(".chat-msg--confirm-run");
        if (confirm) confirm.scrollIntoView({ block: "center" });
      });
      await featurePage.waitForTimeout(200);
      await featurePage.screenshot({
        path: join(SCREEN_DIR, "feature-english-confirm-run-preserved.png"),
        fullPage: false,
      });

      // Snapshot settled messages again right before Yes (must still match baseline)
      const preYes = await extractMessages(featurePage);
      assertMessageParity(report.settledBaseline, preYes, "pre-yes settled");

      // E: click Yes → choreography
      await featurePage.getByRole("button", { name: YES_GUIDE_EN }).click();
      await featurePage.waitForFunction(
        (doneSnippet) => {
          const thread = document.getElementById("chat-thread");
          const text = thread ? thread.textContent || "" : "";
          const choreo =
            document.body.getAttribute("data-choreography-state") || "";
          // done state or terminal guidance text present
          return (
            choreo === "done" ||
            text.includes(doneSnippet) ||
            text.includes("안내를 마쳤습니다")
          );
        },
        CHOREO_DONE_SNIPPET,
        { timeout: 45000 },
      );
      // Ensure no temp left
      await featurePage.waitForFunction(
        () => !document.querySelector("#chat-thread .chat-msg--temp"),
        null,
        { timeout: 10000 },
      );
      report.choreoFeature = await extractMessages(featurePage);
      assert.ok(
        report.choreoFeature.length > report.settledFeature.length,
        "choreography added messages",
      );
      assert.ok(
        report.choreoFeature.every((m) => !m.isTemp && m.textContent.trim()),
        "choreo: no temp/empty",
      );
      console.log(
        "[feature choreo] messages:",
        report.choreoFeature.length,
      );
      await featureCtx.close();
    }

    // ── Baseline Yes → choreography parity ──
    {
      const ctx = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        reducedMotion: "reduce",
      });
      const page = await ctx.newPage();
      await submitAndSettle(page, baselineSrv.baseUrl, "baseline-choreo");
      await page.getByRole("button", { name: YES_GUIDE_EN }).click();
      await page.waitForFunction(
        (doneSnippet) => {
          const thread = document.getElementById("chat-thread");
          const text = thread ? thread.textContent || "" : "";
          const choreo =
            document.body.getAttribute("data-choreography-state") || "";
          return (
            choreo === "done" ||
            text.includes(doneSnippet) ||
            text.includes("안내를 마쳤습니다")
          );
        },
        CHOREO_DONE_SNIPPET,
        { timeout: 45000 },
      );
      await page.waitForFunction(
        () => !document.querySelector("#chat-thread .chat-msg--temp"),
        null,
        { timeout: 10000 },
      );
      report.choreoBaseline = await extractMessages(page);
      assertMessageParity(
        report.choreoBaseline,
        report.choreoFeature,
        "choreography",
      );
      report.choreoParity = "MATCH";
      console.log(
        "[choreo parity] MATCH count=",
        report.choreoFeature.length,
      );
      await ctx.close();
    }

    // Source bans
    const prodJs = readFileSync(
      join(REPO_ROOT, "src/web/static/citizen-first-use-shell.js"),
      "utf8",
    );
    assert.ok(!prodJs.includes('querySelectorAll(".chat-msg--ai")'));
    assert.ok(!prodJs.includes("_continueTargetMsg"));
    assert.ok(!prodJs.includes("_markLatestAssistantResponse"));

    // ── Regression: new handleMvpSubmission disarms prior Continue reading ──
    {
      const ctx = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        reducedMotion: "reduce",
      });
      const page = await ctx.newPage();
      let askCount = 0;
      /** @type {null | (() => void)} */
      let releaseSecond = null;
      const secondHeld = new Promise((resolve) => {
        releaseSecond = resolve;
      });
      /** Resolves when the second /api/mvp/ask route handler is entered (askCount === 2). */
      /** @type {null | (() => void)} */
      let markSecondEntered = null;
      const secondRouteEntered = new Promise((resolve) => {
        markSecondEntered = resolve;
      });

      // First success uses action:none so split/confirm does not lock the composer.
      const firstSuccess = {
        ...FIXTURE,
        action: "none",
      };
      const secondUnusable = {
        ok: true,
        answer: "",
        action: "none",
        confidence: 0,
        failure_code: "",
        provider: "continue-reading-fixture",
        model: "none",
        sources: [],
      };

      await page.route("**/api/mvp/ask", async (route) => {
        askCount += 1;
        if (askCount === 1) {
          await route.fulfill({
            status: 200,
            contentType: "application/json; charset=utf-8",
            body: JSON.stringify(firstSuccess),
          });
          return;
        }
        // askCount === 2: signal entry, then hold until the test asserts disarm.
        if (typeof markSecondEntered === "function") markSecondEntered();
        await secondHeld;
        await route.fulfill({
          status: 200,
          contentType: "application/json; charset=utf-8",
          // Unusable: ok true but blank answer → fail-closed, must not re-arm.
          body: JSON.stringify(secondUnusable),
        });
      });

      await gotoMvp(page, featureSrv.baseUrl, "en");

      // 1) First English MVP success → button armed (DOM present after answer).
      await page.locator("#chat-composer-input").fill(QUESTION);
      await Promise.all([
        page.waitForResponse(
          (r) => r.url().includes("/api/mvp/ask") && r.status() === 200,
          { timeout: 15000 },
        ),
        page.locator("#chat-composer-send").click(),
      ]);
      await page.waitForFunction(
        (snippet) => {
          const t = document.getElementById("chat-thread");
          return t && t.textContent && t.textContent.includes(snippet);
        },
        "Unmanned Civil Document Kiosk Guide",
        { timeout: 15000 },
      );
      await page.waitForFunction(
        () => !!document.querySelector(".chat-continue-read"),
        null,
        { timeout: 8000 },
      );
      let st = await buttonState(page);
      assert.equal(st.present, true, "regression: first success arms button DOM");

      // 2) Second request: wait until route handler is pending (askCount === 2),
      // then assert button is gone while the response is still held.
      await page
        .locator("#chat-composer-input")
        .fill("Second question while prior was armed");
      await Promise.all([
        page.locator("#chat-composer-send").click(),
        secondRouteEntered,
      ]);
      assert.equal(askCount, 2, "regression: second route entered (askCount === 2)");
      st = await buttonState(page);
      assert.equal(
        st.present,
        false,
        "regression: button removed while second ask is pending",
      );

      // 3) Release second route; wait for unusable response completion explicitly.
      const secondResponse = page.waitForResponse(
        (r) => r.url().includes("/api/mvp/ask") && r.status() === 200,
        { timeout: 15000 },
      );
      if (typeof releaseSecond === "function") releaseSecond();
      await secondResponse;
      // Composer unlocks after the bridge settles (no fixed sleep success gate).
      await page.waitForFunction(
        () => {
          const input = document.getElementById("chat-composer-input");
          return input && !input.disabled;
        },
        null,
        { timeout: 10000 },
      );

      // Top scroll: button must stay absent after unusable result.
      await page.evaluate(() => {
        const t = document.getElementById("chat-thread");
        if (!t) return;
        t.scrollTop = 0;
        t.dispatchEvent(new Event("scroll"));
      });
      await page.waitForFunction(
        () => !document.querySelector(".chat-continue-read"),
        null,
        { timeout: 5000 },
      );
      st = await buttonState(page);
      assert.equal(
        st.present,
        false,
        "regression: no button after top scroll post-unusable",
      );

      // Mid scroll: still no button DOM.
      await page.evaluate(() => {
        const t = document.getElementById("chat-thread");
        if (!t) return;
        t.scrollTop = Math.max(0, Math.floor(t.scrollHeight / 2));
        t.dispatchEvent(new Event("scroll"));
      });
      await page.waitForFunction(
        () => !document.querySelector(".chat-continue-read"),
        null,
        { timeout: 5000 },
      );
      st = await buttonState(page);
      assert.equal(
        st.present,
        false,
        "regression: no button after mid-thread scroll post-unusable",
      );
      console.log("[regression] new-request disarm + unusable no re-arm PASS");
      await ctx.close();
    }

    writeFileSync(
      join(SCREEN_DIR, "settled-parity-report.json"),
      JSON.stringify(
        {
          fixtureChars: report.fixtureChars,
          settledCount: report.settledFeature.length,
          settledParity: report.settledParity,
          choreoCount: report.choreoFeature.length,
          choreoParity: report.choreoParity,
          settledBaseline: report.settledBaseline,
          settledFeature: report.settledFeature,
          choreoBaseline: report.choreoBaseline,
          choreoFeature: report.choreoFeature,
        },
        null,
        2,
      ),
    );

    console.log("\nSETTLED PARITY MATCH");
    console.log("CHOREOGRAPHY PARITY MATCH");
    console.log("Screenshots:", SCREEN_DIR);
    console.log("PASS verify_continue_reading_en (settled)");
  } finally {
    await browser.close();
    featureSrv.server.close();
    baselineSrv.server.close();
    rmSync(featureDir, { recursive: true, force: true });
    rmSync(baselineDir, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
