/**
 * #1173 — permanent desktop chat scroll containment contract (fail-closed).
 *
 * Root cause under test:
 *   desktop transitioning/split `.chat-shell` must keep `height: 100vh`
 *   and must NOT be overridden by a trailing `height: 100%` that lets the
 *   shell grow with chat history (document/body scroll hijack).
 *
 * Fail-closed rules:
 *   - every turn waits for a real 200 /api/mvp/ask response (no swallowed timeouts)
 *   - user + assistant counts must each increase by exactly +1 per turn
 *   - last assistant message must contain that turn's deterministic marker
 *   - containment deltas are measured against viewport/baseline, not loose caps
 *
 * Safety:
 *   - repository-controlled static build only
 *   - /api/mvp/ask mocked
 *   - external requests/navigation/popups aborted & counted
 *   - no live provider / Firecrawl / real 북구청 access
 *
 * Usage:
 *   node tests/browser/verify_desktop_chat_scroll_containment_e2e.mjs
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

const VIEWPORTS = {
  desktopLarge: { width: 1440, height: 1000, label: "1440x1000" },
  desktopSmall: { width: 1024, height: 768, label: "1024x768" },
  mobile: { width: 390, height: 844, label: "390x844" },
};

const WARMUP_SPLIT_QUESTION = "공동주택 관련 문의는 어느 부서에 해야 하나요?";
const WARMUP_MARKER = "[[1173-WARMUP-SPLIT-MARKER]]";

// Mixed 15-turn sequence: KO/EN × supported/unsupported, unique markers.
const FIFTEEN_TURNS = Object.freeze([
  { q: "공동주택과 담당 연락처를 알려주세요", kind: "ko-supported", marker: "[[1173-T01-KO-SUP]]" },
  { q: "내일 날씨가 어때?", kind: "ko-unsupported", marker: "[[1173-T02-KO-UNS]]" },
  { q: "Please explain how illegal parking reports work in Buk-gu", kind: "en-supported", marker: "[[1173-T03-EN-SUP]]" },
  { q: "What will the weather be tomorrow?", kind: "en-unsupported", marker: "[[1173-T04-EN-UNS]]" },
  { q: "대형폐기물 수수료 납부 방법을 알려줘", kind: "ko-supported", marker: "[[1173-T05-KO-SUP]]" },
  { q: "How do passport applications work at the district office?", kind: "en-supported", marker: "[[1173-T06-EN-SUP]]" },
  { q: "비트코인 가격 알려줘", kind: "ko-unsupported", marker: "[[1173-T07-KO-UNS]]" },
  { q: "Tell me a joke please", kind: "en-unsupported", marker: "[[1173-T08-EN-UNS]]" },
  { q: "주정차 단속 기준이 궁금해요", kind: "ko-supported", marker: "[[1173-T09-KO-SUP]]" },
  { q: "Where can residents find unmanned certificate kiosks?", kind: "en-supported", marker: "[[1173-T10-EN-SUP]]" },
  { q: "여권 사진 규격이 어떻게 되나요?", kind: "ko-supported", marker: "[[1173-T11-KO-SUP]]" },
  { q: "Recommend a restaurant nearby", kind: "en-unsupported", marker: "[[1173-T12-EN-UNS]]" },
  { q: "주식 종목 추천해줘", kind: "ko-unsupported", marker: "[[1173-T13-KO-UNS]]" },
  { q: "What steps are needed for bulky waste pickup?", kind: "en-supported", marker: "[[1173-T14-EN-SUP]]" },
  { q: "민원서류 무인발급 가능 시간을 알려주세요", kind: "ko-supported", marker: "[[1173-T15-KO-SUP]]" },
]);

const BOTTOM_PIN_TURN = {
  q: "공동주택과 담당 연락처를 알려주세요",
  kind: "ko-supported",
  marker: "[[1173-BOTTOM-PIN]]",
};
const READ_HISTORY_TURN = {
  q: "내일 날씨가 어때?",
  kind: "ko-unsupported",
  marker: "[[1173-READ-HISTORY]]",
};
const REPIN_TURN = {
  q: "Please explain how illegal parking reports work in Buk-gu",
  kind: "en-supported",
  marker: "[[1173-REPIN]]",
};

const MOBILE_TURNS = Object.freeze([
  { q: "공동주택과 담당 연락처를 알려주세요", kind: "ko-supported", marker: "[[1173-MOB-T01]]" },
  { q: "내일 날씨가 어때?", kind: "ko-unsupported", marker: "[[1173-MOB-T02]]" },
  { q: "Please explain how illegal parking reports work in Buk-gu", kind: "en-supported", marker: "[[1173-MOB-T03]]" },
  { q: "What will the weather be tomorrow?", kind: "en-unsupported", marker: "[[1173-MOB-T04]]" },
  { q: "대형폐기물 수수료 납부 방법을 알려줘", kind: "ko-supported", marker: "[[1173-MOB-T05]]" },
  { q: "How do passport applications work at the district office?", kind: "en-supported", marker: "[[1173-MOB-T06]]" },
]);

const LONG_ANSWER_PAD =
  " 안내 경로와 담당 부서, 신청 방법, 준비 서류, 유의사항을 순서대로 확인하세요. " +
  "이 답변은 로컬 정적 픽스처로 제공되며 실제 관공서 사이트나 외부 API를 호출하지 않습니다. " +
  "대화가 길어져도 chat-shell 높이는 viewport에 고정되어야 하고 스크롤은 chat-thread 내부에서만 발생해야 합니다. ";

const DOC_GROWTH_TOL = 48;
const SHELL_GROWTH_TOL = 8;
const CANVAS_GROWTH_TOL = 40;
const SCROLL_TOP_TOL = 40;
const PIN_THRESHOLD = 72;

function turnLookup(question) {
  if (question === WARMUP_SPLIT_QUESTION) {
    return { kind: "ko-supported", marker: WARMUP_MARKER, q: question };
  }
  for (const t of FIFTEEN_TURNS) if (t.q === question) return t;
  for (const t of MOBILE_TURNS) if (t.q === question) return t;
  if (question === BOTTOM_PIN_TURN.q && question.includes("공동주택과")) {
    // Ambiguous with T01; prefer explicit markers from sendTurn options.
  }
  if (question === BOTTOM_PIN_TURN.q) return BOTTOM_PIN_TURN;
  if (question === READ_HISTORY_TURN.q) return READ_HISTORY_TURN;
  if (question === REPIN_TURN.q) return REPIN_TURN;
  return null;
}

function buildMockAnswer(kind, question, marker) {
  const supported = kind === "ko-supported" || kind === "en-supported";
  const tag = marker || "[[1173-UNKNOWN]]";
  if (!supported) {
    return {
      ok: true,
      question,
      answer:
        `${tag} 현재 안내 범위 밖의 질문입니다. 북구청 민원 안내 범위의 질문을 다시 입력해 주세요. ` +
        LONG_ANSWER_PAD.repeat(3),
      action: "none",
      confidence: 0.1,
      failure_code: "",
      provider: "scroll-containment-fixture",
      model: "none",
      sources: [],
    };
  }
  return {
    ok: true,
    question,
    answer:
      `${tag} 「${question}」에 대한 공식 안내입니다. 담당 창구와 신청 절차를 확인하세요.` +
      LONG_ANSWER_PAD.repeat(4),
    action: "none",
    confidence: 1,
    failure_code: "",
    provider: "scroll-containment-fixture",
    model: "none",
    freshness_state: "official_snapshot",
    sources: [
      {
        title: "북구청 안내",
        url: "/mvp/",
        official: true,
      },
    ],
    captured_at: "2026-07-15T01:00:00.000Z",
    verified_at: "2026-07-15T01:00:00.000Z",
  };
}

function buildAndServe() {
  const tmpDir = mkdtempSync(join(tmpdir(), "1173-scroll-contain-"));
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
    throw new Error("Build failed for #1173 scroll containment verifier");
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

/** Pending marker for the next ask fulfillment (set by sendTurn). */
let pendingAskMarker = null;
let pendingAskKind = null;

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
    let question = "";
    try {
      const body = JSON.parse(route.request().postData() || "{}");
      question = body.question || "";
    } catch {
      question = "";
    }
    const kind = pendingAskKind || "ko-unsupported";
    const marker = pendingAskMarker || "[[1173-UNSET]]";
    const payload = buildMockAnswer(kind, question, marker);
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(payload),
    });
  });
}

async function collectCounts(page) {
  return page.evaluate(() => {
    const user = document.querySelectorAll(".chat-msg--user").length;
    const ai = document.querySelectorAll(".chat-msg--ai").length;
    const thread = document.getElementById("chat-thread");
    const input =
      document.getElementById("chat-composer-input") ||
      document.querySelector(".chat-composer__input");
    const lastAi = document.querySelector(".chat-msg--ai:last-of-type") ||
      Array.from(document.querySelectorAll(".chat-msg--ai")).at(-1);
    return {
      user,
      ai,
      total: document.querySelectorAll(".chat-msg").length,
      scrollTop: thread ? thread.scrollTop : -1,
      scrollHeight: thread ? thread.scrollHeight : 0,
      clientHeight: thread ? thread.clientHeight : 0,
      composerDisabled: !!(input && input.disabled),
      lastAiText: lastAi ? (lastAi.textContent || "").trim() : "",
      journey: document.body.getAttribute("data-journey-state") || "",
      firstUse: document.body.getAttribute("data-first-use-state") || "",
    };
  });
}

async function collectMetrics(page) {
  return page.evaluate(() => {
    const html = document.documentElement;
    const body = document.body;
    const thread = document.getElementById("chat-thread");
    const composer =
      document.getElementById("chat-composer-form") ||
      document.querySelector(".chat-composer");
    const input =
      document.getElementById("chat-composer-input") ||
      document.querySelector(".chat-composer__input");
    const send =
      document.getElementById("chat-composer-send") ||
      document.querySelector(".chat-composer__send");
    const canvas =
      document.getElementById("demo-canvas") ||
      document.querySelector(".demo-canvas");
    const shell =
      document.getElementById("chat-shell") ||
      document.querySelector(".chat-shell");
    const lastAi =
      Array.from(document.querySelectorAll(".chat-msg--ai")).at(-1) || null;

    const rect = (el) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return {
        left: r.left,
        top: r.top,
        right: r.right,
        bottom: r.bottom,
        width: r.width,
        height: r.height,
      };
    };
    const composerRect = rect(composer);
    const lastAiRect = rect(lastAi);
    const vh = window.innerHeight;
    const vw = window.innerWidth;
    const composerInViewport = !!(
      composerRect &&
      composerRect.width > 0 &&
      composerRect.height > 0 &&
      composerRect.top >= -1 &&
      composerRect.bottom <= vh + 1 &&
      composerRect.left >= -1 &&
      composerRect.right <= vw + 1
    );
    const inputEnabled = !!(
      input &&
      !input.disabled &&
      !input.readOnly &&
      input.offsetParent !== null
    );
    const sendEnabled = !!(send && !send.disabled);

    return {
      state: body.getAttribute("data-first-use-state") || "",
      documentScrollHeight: html.scrollHeight,
      bodyScrollHeight: body.scrollHeight,
      viewportHeight: vh,
      viewportWidth: vw,
      pageScrollX: window.scrollX || window.pageXOffset || 0,
      pageScrollY: window.scrollY || window.pageYOffset || 0,
      threadClientHeight: thread ? thread.clientHeight : 0,
      threadScrollHeight: thread ? thread.scrollHeight : 0,
      threadScrollTop: thread ? thread.scrollTop : 0,
      threadOverflowY: thread ? getComputedStyle(thread).overflowY : "",
      shellHeight: shell ? shell.getBoundingClientRect().height : 0,
      shellClientHeight: shell ? shell.clientHeight : 0,
      composer: composerRect,
      composerInViewport,
      inputEnabled,
      sendEnabled,
      canvas: rect(canvas),
      canvasHeight: canvas ? canvas.getBoundingClientRect().height : 0,
      userCount: document.querySelectorAll(".chat-msg--user").length,
      aiCount: document.querySelectorAll(".chat-msg--ai").length,
      msgCount: document.querySelectorAll(".chat-msg").length,
      lastAi: lastAiRect,
      lastAiText: lastAi ? (lastAi.textContent || "").trim() : "",
    };
  });
}

async function dismissConfirmIfPresent(page) {
  // Stay in chat multi-turn mode; do not enter #1174 multi-step mobile flow.
  const noBtn = page.getByRole("button", {
    name: /^(아니요|No)$/i,
    disabled: false,
  });
  const n = await noBtn.count();
  if (n === 0) return;
  const first = noBtn.first();
  const visible = await first.isVisible();
  if (!visible) return;
  await first.click({ force: true });
  await page.waitForTimeout(120);
}

async function ensureConversationSurface(page) {
  const state = await page.evaluate(() => {
    const w = window.innerWidth || 0;
    const surface = document.body.getAttribute("data-mobile-surface") || "";
    const tab = document.getElementById("tab-conversation");
    const input =
      document.getElementById("chat-composer-input") ||
      document.querySelector(".chat-composer__input");
    const inputVisible = !!(
      input &&
      input.offsetParent !== null &&
      getComputedStyle(input).visibility !== "hidden"
    );
    return {
      narrow: w <= 767,
      surface,
      hasTab: !!tab,
      tabPressed: tab ? tab.getAttribute("aria-pressed") === "true" : false,
      tabVisible: !!(
        tab &&
        tab.offsetParent !== null &&
        getComputedStyle(tab).visibility !== "hidden" &&
        tab.getBoundingClientRect().height > 0
      ),
      inputVisible,
    };
  });
  if (!state.narrow) return;
  if (state.surface === "conversation" || state.tabPressed) return;
  // Composer already usable — do not force a hidden tab click.
  if (state.inputVisible && !state.tabVisible) return;
  assert.ok(
    state.hasTab,
    "mobile conversation tab missing when surface switch required",
  );
  const tab = page.locator("#tab-conversation");
  await tab.click({ force: true });
  await page.waitForFunction(
    () => document.body.getAttribute("data-mobile-surface") === "conversation",
    null,
    { timeout: 8000 },
  );
}

/**
 * Fail-closed turn: real 200 /api/mvp/ask, exact +1 user, assistant growth,
 * and the expected marker present in the AI thread.
 *
 * @param {{ exactAiDelta?: boolean }} opts
 *   exactAiDelta (default true): require assistant count +1 and last AI = marker.
 *   Set false for warmup exact-product prompts that also append split/confirm AI bubbles.
 */
async function sendTurn(page, turnSpec, ctx = "turn", opts = {}) {
  const exactAiDelta = opts.exactAiDelta !== false;
  const question = typeof turnSpec === "string" ? turnSpec : turnSpec.q;
  const marker =
    typeof turnSpec === "string"
      ? (turnLookup(question) || {}).marker || "[[1173-UNSET]]"
      : turnSpec.marker;
  const kind =
    typeof turnSpec === "string"
      ? (turnLookup(question) || {}).kind || "ko-unsupported"
      : turnSpec.kind;

  pendingAskMarker = marker;
  pendingAskKind = kind;

  await ensureConversationSurface(page);
  await page.waitForFunction(
    () => {
      const input =
        document.getElementById("chat-composer-input") ||
        document.querySelector(".chat-composer__input");
      return input && !input.disabled && input.offsetParent !== null;
    },
    null,
    { timeout: 15000 },
  );

  const before = await collectCounts(page);
  const input = page.locator("#chat-composer-input, .chat-composer__input").first();
  await input.waitFor({ state: "visible", timeout: 10000 });
  await input.fill(question);

  const responsePromise = page.waitForResponse(
    (r) => {
      if (!r.url().includes("/api/mvp/ask")) return false;
      if (r.request().method() !== "POST") return false;
      return true;
    },
    { timeout: 15000 },
  );

  await page.locator("#chat-composer-send, .chat-composer__send").first().click();
  const response = await responsePromise;
  assert.strictEqual(
    response.status(),
    200,
    `[${ctx}] /api/mvp/ask status ${response.status()} for ${question}`,
  );
  const bodyText = await response.text();
  let bodyJson;
  try {
    bodyJson = JSON.parse(bodyText);
  } catch (e) {
    throw new Error(`[${ctx}] invalid JSON from /api/mvp/ask: ${bodyText.slice(0, 200)}`);
  }
  assert.ok(bodyJson && bodyJson.ok === true, `[${ctx}] mock body.ok not true`);
  assert.ok(
    typeof bodyJson.answer === "string" && bodyJson.answer.includes(marker),
    `[${ctx}] response answer missing marker ${marker}`,
  );

  await page.waitForFunction(
    ({ prevUser, prevAi, marker, exactAiDelta }) => {
      const user = document.querySelectorAll(".chat-msg--user").length;
      const ai = document.querySelectorAll(".chat-msg--ai").length;
      if (user !== prevUser + 1) return false;
      if (ai < prevAi + 1) return false;
      const ais = Array.from(document.querySelectorAll(".chat-msg--ai"));
      const hasMarker = ais.some((el) => (el.textContent || "").includes(marker));
      if (!hasMarker) return false;
      if (exactAiDelta) {
        if (ai !== prevAi + 1) return false;
        const lastAi = ais.at(-1);
        return !!(lastAi && (lastAi.textContent || "").includes(marker));
      }
      return true;
    },
    { prevUser: before.user, prevAi: before.ai, marker, exactAiDelta },
    { timeout: 15000 },
  );

  await dismissConfirmIfPresent(page);

  await page.waitForFunction(
    () => {
      const input =
        document.getElementById("chat-composer-input") ||
        document.querySelector(".chat-composer__input");
      return input && !input.disabled;
    },
    null,
    { timeout: 10000 },
  );

  const after = await collectCounts(page);
  assert.strictEqual(
    after.user,
    before.user + 1,
    `[${ctx}] user count ${before.user} -> ${after.user}`,
  );
  assert.ok(
    after.ai >= before.ai + 1,
    `[${ctx}] assistant count did not grow: ${before.ai} -> ${after.ai}`,
  );
  if (exactAiDelta) {
    assert.strictEqual(
      after.ai,
      before.ai + 1,
      `[${ctx}] assistant count ${before.ai} -> ${after.ai}`,
    );
    assert.ok(
      after.lastAiText.includes(marker),
      `[${ctx}] last assistant missing marker ${marker}: ${after.lastAiText.slice(0, 120)}`,
    );
  } else {
    const markerPresent = await page.evaluate((m) => {
      return Array.from(document.querySelectorAll(".chat-msg--ai")).some((el) =>
        (el.textContent || "").includes(m),
      );
    }, marker);
    assert.ok(markerPresent, `[${ctx}] assistant marker missing ${marker}`);
  }

  pendingAskMarker = null;
  pendingAskKind = null;
  return { before, after, marker, question };
}

function assertContainment(m, ctx, baseline) {
  assert.ok(m, `[${ctx}] metrics missing`);
  assert.ok(
    m.documentScrollHeight <= m.viewportHeight + DOC_GROWTH_TOL,
    `[${ctx}] document.scrollHeight ${m.documentScrollHeight} > viewport ${m.viewportHeight}+${DOC_GROWTH_TOL}`,
  );
  assert.ok(
    m.bodyScrollHeight <= m.viewportHeight + DOC_GROWTH_TOL,
    `[${ctx}] body.scrollHeight ${m.bodyScrollHeight} > viewport ${m.viewportHeight}+${DOC_GROWTH_TOL}`,
  );
  if (baseline) {
    assert.ok(
      m.documentScrollHeight <= baseline.documentScrollHeight + DOC_GROWTH_TOL,
      `[${ctx}] document grew vs baseline: ${baseline.documentScrollHeight} -> ${m.documentScrollHeight}`,
    );
    assert.ok(
      m.bodyScrollHeight <= baseline.bodyScrollHeight + DOC_GROWTH_TOL,
      `[${ctx}] body grew vs baseline: ${baseline.bodyScrollHeight} -> ${m.bodyScrollHeight}`,
    );
    assert.ok(
      m.shellHeight <= baseline.shellHeight + SHELL_GROWTH_TOL,
      `[${ctx}] shell height grew: ${baseline.shellHeight} -> ${m.shellHeight}`,
    );
    if (baseline.canvasHeight > 0 && m.canvasHeight > 0) {
      assert.ok(
        m.canvasHeight <= baseline.canvasHeight + CANVAS_GROWTH_TOL,
        `[${ctx}] canvas grew with chat: ${baseline.canvasHeight} -> ${m.canvasHeight}`,
      );
    }
  }
  assert.ok(
    m.threadClientHeight > 80,
    `[${ctx}] chat-thread clientHeight not bounded/visible: ${m.threadClientHeight}`,
  );
  assert.ok(
    m.threadClientHeight <= m.viewportHeight,
    `[${ctx}] chat-thread clientHeight ${m.threadClientHeight} > viewport ${m.viewportHeight}`,
  );
  assert.ok(
    m.threadScrollHeight > m.threadClientHeight + 8,
    `[${ctx}] expected internal overflow: scrollHeight ${m.threadScrollHeight} <= clientHeight ${m.threadClientHeight}`,
  );
  assert.ok(
    /auto|scroll/i.test(m.threadOverflowY),
    `[${ctx}] chat-thread overflow-y should be auto/scroll, got ${m.threadOverflowY}`,
  );
  assert.ok(
    m.composerInViewport,
    `[${ctx}] composer not fully inside viewport: ${JSON.stringify(m.composer)}`,
  );
  assert.ok(m.inputEnabled, `[${ctx}] composer input not operable`);
  assert.ok(m.sendEnabled, `[${ctx}] composer send not operable`);
  assert.ok(
    Math.abs(m.pageScrollY) <= 4,
    `[${ctx}] page scrollY should stay ~0, got ${m.pageScrollY}`,
  );
  assert.ok(
    m.shellHeight <= m.viewportHeight + SHELL_GROWTH_TOL,
    `[${ctx}] chat-shell height ${m.shellHeight} exceeds viewport ${m.viewportHeight}`,
  );
}

/**
 * Bottom-pinned acceptance: last assistant (with marker) visible in thread,
 * composer in viewport, document not scrolled, and thread actually near bottom.
 * Must NOT be used for reading-history (unpinned) paths.
 */
async function assertLatestAssistantVisible(page, marker, ctx) {
  const res = await page.evaluate(
    ({ marker, pinThreshold }) => {
      const thread = document.getElementById("chat-thread");
      const ais = Array.from(document.querySelectorAll(".chat-msg--ai"));
      const last = ais[ais.length - 1];
      const composer =
        document.getElementById("chat-composer-form") ||
        document.querySelector(".chat-composer");
      if (!thread || !last) {
        return {
          ok: false,
          reason: "missing-thread-or-assistant",
          nearBottom: false,
          distBottom: -1,
          pageScrollY: window.scrollY || 0,
        };
      }
      const text = last.textContent || "";
      if (!text.includes(marker)) {
        return {
          ok: false,
          reason: "marker-mismatch",
          text: text.slice(0, 160),
          nearBottom: false,
          distBottom:
            thread.scrollHeight - thread.scrollTop - thread.clientHeight,
          pageScrollY: window.scrollY || 0,
        };
      }
      const tr = thread.getBoundingClientRect();
      const mr = last.getBoundingClientRect();
      const cr = composer ? composer.getBoundingClientRect() : null;
      const vh = window.innerHeight;
      const assistantVisible =
        mr.bottom > tr.top + 2 && mr.top < tr.bottom - 2 && mr.height > 0;
      const composerInVp = !!(
        cr &&
        cr.width > 0 &&
        cr.height > 0 &&
        cr.top >= -1 &&
        cr.bottom <= vh + 1
      );
      const distBottom =
        thread.scrollHeight - thread.scrollTop - thread.clientHeight;
      // Fail-closed: partial intersection of a tall bubble is not enough;
      // the thread must actually be bottom-pinned.
      const nearBottom = distBottom <= pinThreshold + 8;
      return {
        ok: assistantVisible && composerInVp && nearBottom,
        assistantVisible,
        composerInVp,
        distBottom,
        nearBottom,
        pinThreshold,
        threadTop: tr.top,
        threadBottom: tr.bottom,
        msgTop: mr.top,
        msgBottom: mr.bottom,
        pageScrollY: window.scrollY || 0,
      };
    },
    { marker, pinThreshold: PIN_THRESHOLD },
  );
  assert.ok(
    res.ok,
    `[${ctx}] latest assistant not properly bottom-pinned/visible: ${JSON.stringify(res)}`,
  );
  assert.ok(
    res.nearBottom === true,
    `[${ctx}] chat thread is not bottom-pinned: distBottom=${res.distBottom}`,
  );
  assert.ok(
    Math.abs(res.pageScrollY) <= 4,
    `[${ctx}] document scroll required for composer/assistant: pageScrollY=${res.pageScrollY}`,
  );
  return res;
}

async function pinThreadToBottom(page) {
  await page.evaluate(async () => {
    const t = document.getElementById("chat-thread");
    if (!t) throw new Error("chat-thread missing");
    t.scrollTop = t.scrollHeight;
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    t.scrollTop = t.scrollHeight;
  });
  const pinCheck = await page.evaluate((threshold) => {
    const t = document.getElementById("chat-thread");
    if (!t) return { ok: false };
    const dist = t.scrollHeight - t.scrollTop - t.clientHeight;
    return { ok: dist <= threshold, dist, scrollTop: t.scrollTop };
  }, PIN_THRESHOLD);
  assert.ok(pinCheck.ok, `failed to pin chat to bottom: ${JSON.stringify(pinCheck)}`);
}

async function runDesktopViewport(browser, origin, safety, viewport) {
  const label = viewport.label;
  console.log(`\n=== desktop containment ${label} ===`);
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  safety.attach(page);
  await installRoutes(page, origin);

  await page.goto(`${origin}/mvp/?lang=ko`, {
    waitUntil: "domcontentloaded",
    timeout: 20000,
  });
  await page.waitForSelector("#chat-composer-input, .chat-composer__input", {
    timeout: 10000,
  });

  const entryBaseline = await collectMetrics(page);
  const countsAtEntry = await collectCounts(page);

  // Warmup: exact product prompt → split layout (extra AI bubbles after answer).
  await sendTurn(
    page,
    { q: WARMUP_SPLIT_QUESTION, kind: "ko-supported", marker: WARMUP_MARKER },
    `${label} warmup`,
    { exactAiDelta: false },
  );
  await page.waitForFunction(
    () => document.body.getAttribute("data-first-use-state") === "split",
    null,
    { timeout: 12000 },
  );
  await pinThreadToBottom(page);
  const splitBaseline = await collectMetrics(page);
  console.log(
    `  warmup split: state=${splitBaseline.state} canvas=${Math.round(splitBaseline.canvasHeight)} ` +
      `doc=${splitBaseline.documentScrollHeight} shell=${Math.round(splitBaseline.shellHeight)} ` +
      `thread c=${splitBaseline.threadClientHeight}/s=${splitBaseline.threadScrollHeight}`,
  );

  const countsAfterWarmup = await collectCounts(page);
  const turnMetrics = [];
  const seenMarkers = new Set([WARMUP_MARKER]);

  for (let i = 0; i < FIFTEEN_TURNS.length; i++) {
    const turn = FIFTEEN_TURNS[i];
    const result = await sendTurn(page, turn, `${label} turn-${i + 1}`);
    assert.ok(!seenMarkers.has(turn.marker), `duplicate marker ${turn.marker}`);
    seenMarkers.add(turn.marker);
    const m = await collectMetrics(page);
    assertContainment(m, `${label} turn-${i + 1}`, splitBaseline);
    turnMetrics.push({ ...m, marker: turn.marker, user: result.after.user, ai: result.after.ai });
    console.log(
      `  turn ${i + 1}/${FIFTEEN_TURNS.length} [${turn.kind}] ` +
        `user=${result.after.user} ai=${result.after.ai} marker=${turn.marker} ` +
        `doc=${m.documentScrollHeight} body=${m.bodyScrollHeight} ` +
        `thread c=${m.threadClientHeight}/s=${m.threadScrollHeight}/top=${Math.round(m.threadScrollTop)} ` +
        `shell=${Math.round(m.shellHeight)} canvas=${Math.round(m.canvasHeight)} ` +
        `composerInVp=${m.composerInViewport}`,
    );
  }

  const after15 = turnMetrics[turnMetrics.length - 1];
  assertContainment(after15, `${label} after-15`, splitBaseline);
  const countsAfter15 = await collectCounts(page);
  assert.strictEqual(
    countsAfter15.user,
    countsAfterWarmup.user + 15,
    `[${label}] user messages after 15 turns: expected ${countsAfterWarmup.user + 15}, got ${countsAfter15.user}`,
  );
  assert.strictEqual(
    countsAfter15.ai,
    countsAfterWarmup.ai + 15,
    `[${label}] assistant messages after 15 turns: expected ${countsAfterWarmup.ai + 15}, got ${countsAfter15.ai}`,
  );
  for (const t of FIFTEEN_TURNS) {
    const present = await page.evaluate((marker) => {
      return Array.from(document.querySelectorAll(".chat-msg--ai")).some((el) =>
        (el.textContent || "").includes(marker),
      );
    }, t.marker);
    assert.ok(present, `[${label}] missing assistant marker ${t.marker}`);
  }

  // Bottom-pinned: latest assistant visible.
  await pinThreadToBottom(page);
  await sendTurn(page, BOTTOM_PIN_TURN, `${label} bottom-pin`);
  const bottomPinRes = await assertLatestAssistantVisible(
    page,
    BOTTOM_PIN_TURN.marker,
    `${label} bottom-pinned`,
  );
  console.log(
    `  bottom-pinned: PASS distBottom=${bottomPinRes.distBottom} nearBottom=${bottomPinRes.nearBottom}`,
  );

  // Reading-history → explicit turn: #1200 ensures composer submit always
  // follows the latest message. Scroll up, submit, verify yank to bottom.
  await page.evaluate(() => {
    const t = document.getElementById("chat-thread");
    if (!t) throw new Error("chat-thread missing");
    t.scrollTop = 0;
  });
  await page.waitForTimeout(80);
  const beforeRead = await page.evaluate(() => {
    const t = document.getElementById("chat-thread");
    return {
      scrollTop: t.scrollTop,
      scrollHeight: t.scrollHeight,
      clientHeight: t.clientHeight,
      distBottom: t.scrollHeight - t.scrollTop - t.clientHeight,
    };
  });
  assert.ok(
    beforeRead.distBottom > PIN_THRESHOLD + 20,
    `[${label}] not far enough from bottom for reading-history: ${JSON.stringify(beforeRead)}`,
  );
  await sendTurn(page, READ_HISTORY_TURN, `${label} reading-history`);
  const afterRead = await page.evaluate(() => {
    const t = document.getElementById("chat-thread");
    const lastAi = Array.from(document.querySelectorAll(".chat-msg--ai")).at(-1);
    return {
      scrollTop: t.scrollTop,
      scrollHeight: t.scrollHeight,
      clientHeight: t.clientHeight,
      distBottom: t.scrollHeight - t.scrollTop - t.clientHeight,
      lastAiText: lastAi ? lastAi.textContent || "" : "",
    };
  });
  assert.ok(
    afterRead.lastAiText.includes(READ_HISTORY_TURN.marker),
    `[${label}] reading-history assistant marker missing`,
  );
  // #1200: explicit composer submit while reading history now yanks to latest.
  assert.ok(
    afterRead.distBottom <= PIN_THRESHOLD + 8,
    `[${label}] explicit turn should yank to bottom: ${JSON.stringify({ beforeRead, afterRead })}`,
  );
  console.log(`  reading-history explicit-turn yank: PASS`);

  // Re-pin + auto-scroll.
  await pinThreadToBottom(page);
  await sendTurn(page, REPIN_TURN, `${label} re-pin`);
  const repinRes = await assertLatestAssistantVisible(
    page,
    REPIN_TURN.marker,
    `${label} re-pin auto-scroll`,
  );
  console.log(
    `  re-pin auto-scroll: PASS distBottom=${repinRes.distBottom} nearBottom=${repinRes.nearBottom}`,
  );

  const finalMetrics = await collectMetrics(page);
  assertContainment(finalMetrics, `${label} final`, splitBaseline);

  await context.close();
  return {
    label,
    entryBaseline,
    splitBaseline,
    after15,
    finalMetrics,
    countsAtEntry,
    countsAfterWarmup,
    countsAfter15,
    userDelta15: countsAfter15.user - countsAfterWarmup.user,
    aiDelta15: countsAfter15.ai - countsAfterWarmup.ai,
    bottomPinDistBottom: bottomPinRes.distBottom,
    repinDistBottom: repinRes.distBottom,
    readingHistoryDistBottom: afterRead.distBottom,
  };
}

async function runMobileBaseline(browser, origin, safety) {
  const viewport = VIEWPORTS.mobile;
  const label = viewport.label;
  console.log(`\n=== mobile baseline regression ${label} ===`);
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    reducedMotion: "reduce",
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  safety.attach(page);
  await installRoutes(page, origin);

  await page.goto(`${origin}/mvp/?lang=ko`, {
    waitUntil: "domcontentloaded",
    timeout: 20000,
  });
  await ensureConversationSurface(page);
  await page.waitForSelector("#chat-composer-input, .chat-composer__input", {
    timeout: 10000,
  });

  const baseline = await collectMetrics(page);
  const countsStart = await collectCounts(page);

  // #1174 boundary: only basic conversation — never click "예".
  for (let i = 0; i < MOBILE_TURNS.length; i++) {
    const turn = MOBILE_TURNS[i];
    const result = await sendTurn(page, turn, `${label} turn-${i + 1}`);
    const m = await collectMetrics(page);
    assert.strictEqual(result.after.user, countsStart.user + i + 1);
    assert.strictEqual(result.after.ai, countsStart.ai + i + 1);
    assert.ok(
      m.documentScrollHeight <= baseline.documentScrollHeight + DOC_GROWTH_TOL,
      `[${label}] document grew: ${baseline.documentScrollHeight} -> ${m.documentScrollHeight}`,
    );
    assert.ok(
      m.shellHeight <= baseline.shellHeight + SHELL_GROWTH_TOL ||
        m.shellHeight <= m.viewportHeight + SHELL_GROWTH_TOL,
      `[${label}] shell height grew with chat: ${baseline.shellHeight} -> ${m.shellHeight}`,
    );
    console.log(
      `  mobile turn ${i + 1}: user=${result.after.user} ai=${result.after.ai} ` +
        `doc=${m.documentScrollHeight} thread c=${m.threadClientHeight}/s=${m.threadScrollHeight}`,
    );
  }

  const m = await collectMetrics(page);
  const countsEnd = await collectCounts(page);
  assert.strictEqual(countsEnd.user, countsStart.user + MOBILE_TURNS.length);
  assert.strictEqual(countsEnd.ai, countsStart.ai + MOBILE_TURNS.length);
  assert.ok(
    m.composer && m.composer.width > 40 && m.composer.height > 20,
    `[${label}] composer collapsed: ${JSON.stringify(m.composer)}`,
  );
  assert.ok(m.composerInViewport, `[${label}] composer not in viewport`);
  assert.ok(m.inputEnabled, `[${label}] input not operable`);
  assert.ok(m.sendEnabled, `[${label}] send not operable`);
  assert.ok(
    m.threadClientHeight > 40,
    `[${label}] thread clientHeight regression: ${m.threadClientHeight}`,
  );
  assert.ok(
    m.threadScrollHeight > m.threadClientHeight + 8,
    `[${label}] expected internal overflow: s=${m.threadScrollHeight} c=${m.threadClientHeight}`,
  );
  assert.ok(
    m.documentScrollHeight <= baseline.documentScrollHeight + DOC_GROWTH_TOL,
    `[${label}] document scrollHeight grew: ${baseline.documentScrollHeight} -> ${m.documentScrollHeight}`,
  );

  await pinThreadToBottom(page);
  await sendTurn(
    page,
    { q: "공동주택과 담당 연락처를 알려주세요", kind: "ko-supported", marker: "[[1173-MOB-PIN]]" },
    `${label} bottom-pin`,
  );
  const mobPinRes = await assertLatestAssistantVisible(
    page,
    "[[1173-MOB-PIN]]",
    `${label} bottom-pinned`,
  );

  console.log(
    `  mobile baseline: composer=${Math.round(m.composer.width)}x${Math.round(m.composer.height)} ` +
      `thread c=${m.threadClientHeight}/s=${m.threadScrollHeight} ` +
      `doc=${m.documentScrollHeight} (baseline ${baseline.documentScrollHeight}) ` +
      `user+${MOBILE_TURNS.length} ai+${MOBILE_TURNS.length} ` +
      `bottomPin distBottom=${mobPinRes.distBottom} PASS`,
  );

  await context.close();
  return {
    label,
    baseline,
    metrics: m,
    countsStart,
    countsEnd,
    userDelta: countsEnd.user - countsStart.user,
    aiDelta: countsEnd.ai - countsStart.ai,
    bottomPinDistBottom: mobPinRes.distBottom,
  };
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

async function main() {
  console.log("#1173 desktop chat scroll containment E2E (fail-closed)");
  console.log(`warmup split: ${WARMUP_SPLIT_QUESTION} marker=${WARMUP_MARKER}`);
  console.log("15-turn request list:");
  FIFTEEN_TURNS.forEach((t, i) => {
    console.log(`  ${i + 1}. [${t.kind}] ${t.marker} ${t.q}`);
  });

  const { origin, cleanup } = await buildAndServe();
  const { browser, source } = await launchBrowser();
  console.log(`Browser: ${source}`);
  console.log(`Origin: ${origin}`);

  const safety = createSafetyTracker(origin);
  let results;
  try {
    const large = await runDesktopViewport(
      browser,
      origin,
      safety,
      VIEWPORTS.desktopLarge,
    );
    const small = await runDesktopViewport(
      browser,
      origin,
      safety,
      VIEWPORTS.desktopSmall,
    );
    const mobile = await runMobileBaseline(browser, origin, safety);
    assertSafety(safety.state);
    results = { large, small, mobile, safety: safety.state };
  } finally {
    await browser.close();
    cleanup();
  }

  console.log("\n=== SUMMARY ===");
  console.log(
    JSON.stringify(
      {
        largeAfter15: {
          doc: results.large.after15.documentScrollHeight,
          body: results.large.after15.bodyScrollHeight,
          threadClient: results.large.after15.threadClientHeight,
          threadScroll: results.large.after15.threadScrollHeight,
          shell: results.large.after15.shellHeight,
          canvas: results.large.after15.canvasHeight,
          userDelta15: results.large.userDelta15,
          aiDelta15: results.large.aiDelta15,
          baselineDoc: results.large.splitBaseline.documentScrollHeight,
          bottomPinDistBottom: results.large.bottomPinDistBottom,
          repinDistBottom: results.large.repinDistBottom,
          readingHistoryDistBottom: results.large.readingHistoryDistBottom,
        },
        smallAfter15: {
          doc: results.small.after15.documentScrollHeight,
          body: results.small.after15.bodyScrollHeight,
          threadClient: results.small.after15.threadClientHeight,
          threadScroll: results.small.after15.threadScrollHeight,
          shell: results.small.after15.shellHeight,
          canvas: results.small.after15.canvasHeight,
          userDelta15: results.small.userDelta15,
          aiDelta15: results.small.aiDelta15,
          baselineDoc: results.small.splitBaseline.documentScrollHeight,
          bottomPinDistBottom: results.small.bottomPinDistBottom,
          repinDistBottom: results.small.repinDistBottom,
          readingHistoryDistBottom: results.small.readingHistoryDistBottom,
        },
        mobile: {
          doc: results.mobile.metrics.documentScrollHeight,
          baselineDoc: results.mobile.baseline.documentScrollHeight,
          threadClient: results.mobile.metrics.threadClientHeight,
          threadScroll: results.mobile.metrics.threadScrollHeight,
          userDelta: results.mobile.userDelta,
          aiDelta: results.mobile.aiDelta,
          composer: results.mobile.metrics.composer,
          bottomPinDistBottom: results.mobile.bottomPinDistBottom,
        },
        safety: {
          consoleErrors: results.safety.consoleErrors.length,
          pageErrors: results.safety.pageErrors.length,
          failedResources: results.safety.failedResources.length,
          externalRequests: results.safety.externalRequests.length,
          externalNavigations: results.safety.externalNavigations.length,
          popups: results.safety.popups,
          liveApiHits: results.safety.liveApiHits,
        },
      },
      null,
      2,
    ),
  );
  console.log("#1173 PASS");
}

main().catch((err) => {
  console.error("#1173 FAIL:", err);
  process.exitCode = 1;
});
