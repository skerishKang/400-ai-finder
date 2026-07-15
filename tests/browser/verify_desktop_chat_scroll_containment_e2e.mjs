/**
 * #1173 — permanent desktop chat scroll containment contract.
 *
 * Root cause under test:
 *   desktop transitioning/split `.chat-shell` must keep `height: 100vh`
 *   and must NOT be overridden by a trailing `height: 100%` that lets the
 *   shell grow with chat history (document/body scroll hijack).
 *
 * Also locks:
 *   - chat-thread internal overflow (not document overflow)
 *   - composer remains viewport-visible + operable after 15 turns
 *   - left civic canvas height is not driven by chat history
 *   - bottom-pinned auto-scroll of new replies
 *   - reading-history scroll position is preserved across DOM updates
 *   - 1024×768 same containment
 *   - 390×844 baseline conversation + internal scroll regression only
 *     (#1174 multi-step "예" composer collapse is intentionally out of scope)
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

// Warmup uses one exact product prompt so desktop reaches split (left canvas).
// The 15-turn mixed sequence intentionally avoids SUPPORTED_QUESTION_ACTIONS
// exact keys so each turn stays chat-only (no re-entrant cinematic split /
// confirm stack). Supported vs unsupported is still mixed KO/EN content.
const WARMUP_SPLIT_QUESTION = "공동주택 관련 문의는 어느 부서에 해야 하나요?";

// Mixed 15-turn sequence: KO/EN × supported/unsupported, no pure repeats.
const FIFTEEN_TURNS = Object.freeze([
  { q: "공동주택과 담당 연락처를 알려주세요", kind: "ko-supported" },
  { q: "내일 날씨가 어때?", kind: "ko-unsupported" },
  { q: "Please explain how illegal parking reports work in Buk-gu", kind: "en-supported" },
  { q: "What will the weather be tomorrow?", kind: "en-unsupported" },
  { q: "대형폐기물 수수료 납부 방법을 알려줘", kind: "ko-supported" },
  { q: "How do passport applications work at the district office?", kind: "en-supported" },
  { q: "비트코인 가격 알려줘", kind: "ko-unsupported" },
  { q: "Tell me a joke please", kind: "en-unsupported" },
  { q: "주정차 단속 기준이 궁금해요", kind: "ko-supported" },
  { q: "Where can residents find unmanned certificate kiosks?", kind: "en-supported" },
  { q: "여권 사진 규격이 어떻게 되나요?", kind: "ko-supported" },
  { q: "Recommend a restaurant nearby", kind: "en-unsupported" },
  { q: "주식 종목 추천해줘", kind: "ko-unsupported" },
  { q: "What steps are needed for bulky waste pickup?", kind: "en-supported" },
  { q: "민원서류 무인발급 가능 시간을 알려주세요", kind: "ko-supported" },
]);

const LONG_ANSWER_PAD =
  " 안내 경로와 담당 부서, 신청 방법, 준비 서류, 유의사항을 순서대로 확인하세요. " +
  "이 답변은 로컬 정적 픽스처로 제공되며 실제 관공서 사이트나 외부 API를 호출하지 않습니다. " +
  "대화가 길어져도 chat-shell 높이는 viewport에 고정되어야 하고 스크롤은 chat-thread 내부에서만 발생해야 합니다. ";

function buildMockAnswer(kind, question) {
  const supported = kind === "ko-supported" || kind === "en-supported";
  // Always return ok:true with a long body so chat-thread scrollHeight grows.
  // action:"none" keeps the 15-turn sequence in chat-only mode (no re-split).
  // Warmup split is driven by the exact product prompt map, not this action.
  if (!supported) {
    return {
      ok: true,
      question,
      answer:
        "현재 안내 범위 밖의 질문입니다. 북구청 민원 안내 범위의 질문을 다시 입력해 주세요. " +
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
      `「${question}」에 대한 공식 안내입니다. 담당 창구와 신청 절차를 확인하세요.` +
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
      // Favicon / benign aborts are not product asset failures.
      if (/favicon\.ico$/i.test(url)) return;
      if (req.failure() && /net::ERR_ABORTED/i.test(req.failure().errorText || "")) {
        // aborted by our route handler for external URLs
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
        /* ignore */
      }
    });
    page.on("popup", () => {
      state.popups += 1;
    });
  }

  return { state, attach };
}

async function installRoutes(page, origin) {
  // Abort any non-origin request (safety net; never hit live providers/sites).
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
    let kind = "ko-unsupported";
    try {
      const body = JSON.parse(route.request().postData() || "{}");
      question = body.question || "";
    } catch {
      /* ignore */
    }
    if (question === WARMUP_SPLIT_QUESTION) {
      kind = "ko-supported";
    } else {
      const turn = FIFTEEN_TURNS.find((t) => t.q === question);
      if (turn) kind = turn.kind;
      else if (/weather|joke|restaurant|bitcoin|주식|날씨|추천/i.test(question)) {
        kind = "en-unsupported";
      } else {
        kind = "ko-supported";
      }
    }
    const payload = buildMockAnswer(kind, question);
    // Warmup exact prompt is resolved via SUPPORTED_QUESTION_ACTIONS in shell.
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(payload),
    });
  });
}

async function collectMetrics(page) {
  return page.evaluate(() => {
    const html = document.documentElement;
    const body = document.body;
    const thread = document.getElementById("chat-thread");
    const composer = document.getElementById("chat-composer-form") ||
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
      msgCount: document.querySelectorAll(".chat-msg").length,
    };
  });
}

async function dismissConfirmIfPresent(page) {
  // Stay in chat multi-turn mode; do not enter #1174 multi-step mobile flow.
  // Only click an *enabled* confirm decline — disabled historical 아니요 buttons
  // remain in the thread and must not be targeted (Playwright can scroll them
  // into view and yank reading position / bottom pin).
  const noBtn = page.getByRole("button", {
    name: /^(아니요|No)$/i,
    disabled: false,
  });
  if ((await noBtn.count()) > 0) {
    const first = noBtn.first();
    if (await first.isVisible().catch(() => false)) {
      await first.click({ force: true }).catch(() => {});
      await page.waitForTimeout(120);
    }
  }
}

async function ensureConversationSurface(page) {
  const needsSwitch = await page.evaluate(() => {
    const w = window.innerWidth || 0;
    if (w > 767) return false;
    return document.body.getAttribute("data-mobile-surface") !== "conversation";
  });
  if (!needsSwitch) return;
  const tab = page.locator("#tab-conversation");
  if ((await tab.count()) > 0) {
    await tab.click({ force: true }).catch(() => {});
    await page
      .waitForFunction(
        () => document.body.getAttribute("data-mobile-surface") === "conversation",
        null,
        { timeout: 5000 },
      )
      .catch(() => {});
  }
}

async function sendTurn(page, question) {
  await ensureConversationSurface(page);
  // Composer must be free (not disabled mid-request).
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
  const input = page.locator("#chat-composer-input, .chat-composer__input").first();
  await input.waitFor({ state: "visible", timeout: 10000 });
  await input.fill(question);
  const prevCount = await page.locator(".chat-msg").count();
  await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes("/api/mvp/ask") && r.status() === 200,
      { timeout: 15000 },
    ).catch(() => null),
    page.locator("#chat-composer-send, .chat-composer__send").first().click(),
  ]);
  await page
    .waitForFunction(
      (prev) => document.querySelectorAll(".chat-msg").length > prev,
      prevCount,
      { timeout: 12000 },
    )
    .catch(() => {});
  // Split/confirm can land after reduced-motion timeouts; wait briefly.
  await page.waitForTimeout(450);
  await dismissConfirmIfPresent(page);
  // Wait for composer unlock after any confirm dismissal.
  await page.waitForFunction(
    () => {
      const input =
        document.getElementById("chat-composer-input") ||
        document.querySelector(".chat-composer__input");
      return input && !input.disabled;
    },
    null,
    { timeout: 10000 },
  ).catch(() => {});
  await page.waitForTimeout(80);
}

function assertContainment(m, ctx, baselineDoc, baselineCanvas) {
  const tol = 4;
  // Document/body must not grow with full chat history (viewport-bounded shell).
  assert.ok(
    m.documentScrollHeight <= m.viewportHeight + 80,
    `[${ctx}] document.scrollHeight ${m.documentScrollHeight} exceeds viewport ${m.viewportHeight}+80`,
  );
  assert.ok(
    m.bodyScrollHeight <= m.viewportHeight + 80,
    `[${ctx}] body.scrollHeight ${m.bodyScrollHeight} exceeds viewport ${m.viewportHeight}+80`,
  );
  if (baselineDoc != null) {
    assert.ok(
      m.documentScrollHeight <= baselineDoc + 40,
      `[${ctx}] document grew with chat history: ${baselineDoc} -> ${m.documentScrollHeight}`,
    );
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
    Math.abs(m.pageScrollY) <= tol,
    `[${ctx}] page scrollY should stay ~0, got ${m.pageScrollY}`,
  );
  if (baselineCanvas != null && m.canvasHeight > 0) {
    assert.ok(
      m.canvasHeight <= baselineCanvas + 40,
      `[${ctx}] left canvas height grew with chat: ${baselineCanvas} -> ${m.canvasHeight}`,
    );
  }
  assert.ok(
    m.shellHeight <= m.viewportHeight + tol,
    `[${ctx}] chat-shell height ${m.shellHeight} exceeds viewport ${m.viewportHeight}`,
  );
}

async function assertLatestMessageVisible(page, ctx) {
  const res = await page.evaluate(() => {
    const thread = document.getElementById("chat-thread");
    const msgs = thread ? thread.querySelectorAll(".chat-msg") : [];
    const last = msgs[msgs.length - 1];
    if (!thread || !last) return { ok: false, reason: "missing" };
    const tr = thread.getBoundingClientRect();
    const mr = last.getBoundingClientRect();
    const visible =
      mr.bottom > tr.top + 2 &&
      mr.top < tr.bottom - 2 &&
      mr.height > 0;
    return {
      ok: visible,
      threadTop: tr.top,
      threadBottom: tr.bottom,
      msgTop: mr.top,
      msgBottom: mr.bottom,
      scrollTop: thread.scrollTop,
      scrollHeight: thread.scrollHeight,
      clientHeight: thread.clientHeight,
    };
  });
  assert.ok(res.ok, `[${ctx}] latest message not visible: ${JSON.stringify(res)}`);
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

  const firstMetrics = await collectMetrics(page);
  const baselineDoc = firstMetrics.documentScrollHeight;

  // Warmup: exact product prompt → split layout (left canvas baseline).
  await sendTurn(page, WARMUP_SPLIT_QUESTION);
  await page.waitForFunction(
    () => document.body.getAttribute("data-first-use-state") === "split",
    null,
    { timeout: 10000 },
  ).catch(() => {});
  // Snap to bottom after split ack settles so the 15-turn run starts pinned.
  await page.evaluate(async () => {
    const t = document.getElementById("chat-thread");
    if (!t) return;
    t.scrollTop = t.scrollHeight;
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    t.scrollTop = t.scrollHeight;
  });
  const warmupMetrics = await collectMetrics(page);
  const baselineCanvas = warmupMetrics.canvasHeight;
  console.log(
    `  warmup split: state=${warmupMetrics.state} canvas=${Math.round(baselineCanvas)} ` +
      `thread c=${warmupMetrics.threadClientHeight}/s=${warmupMetrics.threadScrollHeight}/top=${Math.round(warmupMetrics.threadScrollTop)}`,
  );

  const turnMetrics = [];
  for (let i = 0; i < FIFTEEN_TURNS.length; i++) {
    const turn = FIFTEEN_TURNS[i];
    await sendTurn(page, turn.q);
    const m = await collectMetrics(page);
    turnMetrics.push(m);
    console.log(
      `  turn ${i + 1}/${FIFTEEN_TURNS.length} [${turn.kind}] ` +
        `doc=${m.documentScrollHeight} body=${m.bodyScrollHeight} ` +
        `thread c=${m.threadClientHeight}/s=${m.threadScrollHeight}/top=${Math.round(m.threadScrollTop)} ` +
        `shell=${Math.round(m.shellHeight)} canvas=${Math.round(m.canvasHeight)} ` +
        `composerInVp=${m.composerInViewport}`,
    );
  }

  const after15 = turnMetrics[turnMetrics.length - 1];
  assertContainment(after15, `${label} after-15`, baselineDoc, baselineCanvas);
  assert.ok(
    after15.msgCount >= 15,
    `[${label}] expected accumulated messages, got ${after15.msgCount}`,
  );

  // 7. bottom-pinned: latest message visible after a fresh chat-only send.
  await page.evaluate(async () => {
    const t = document.getElementById("chat-thread");
    if (!t) return;
    t.scrollTop = t.scrollHeight;
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    t.scrollTop = t.scrollHeight;
  });
  const pinCheck = await page.evaluate(() => {
    const t = document.getElementById("chat-thread");
    if (!t) return { ok: false };
    const dist = t.scrollHeight - t.scrollTop - t.clientHeight;
    return { ok: dist <= 72, dist, scrollTop: t.scrollTop, scrollHeight: t.scrollHeight };
  });
  assert.ok(pinCheck.ok, `[${label}] failed to pin to bottom before send: ${JSON.stringify(pinCheck)}`);
  await sendTurn(page, "공동주택과 담당 연락처를 알려주세요");
  await page.waitForTimeout(250);
  await assertLatestMessageVisible(page, `${label} bottom-pinned`);
  console.log(`  bottom-pinned: PASS`);

  // 8. reading-history: scroll up, append via send, scrollTop must not jump to bottom.
  await page.evaluate(() => {
    const t = document.getElementById("chat-thread");
    if (t) t.scrollTop = 0;
  });
  await page.waitForTimeout(80);
  const beforeRead = await page.evaluate(() => {
    const t = document.getElementById("chat-thread");
    return {
      scrollTop: t ? t.scrollTop : -1,
      scrollHeight: t ? t.scrollHeight : 0,
      clientHeight: t ? t.clientHeight : 0,
    };
  });
  assert.ok(
    beforeRead.scrollHeight - beforeRead.clientHeight > 80,
    `[${label}] not enough internal scroll range to test reading-history`,
  );
  // Send while scrolled to top — must preserve reading position (not yank to bottom).
  await sendTurn(page, "내일 날씨가 어때?");
  await page.waitForTimeout(200);
  const afterRead = await page.evaluate(() => {
    const t = document.getElementById("chat-thread");
    return {
      scrollTop: t ? t.scrollTop : -1,
      scrollHeight: t ? t.scrollHeight : 0,
      clientHeight: t ? t.clientHeight : 0,
      distanceFromBottom: t
        ? t.scrollHeight - t.scrollTop - t.clientHeight
        : -1,
    };
  });
  assert.ok(
    afterRead.distanceFromBottom > 72,
    `[${label}] reading-history yanked to bottom: ${JSON.stringify({ beforeRead, afterRead })}`,
  );
  assert.ok(
    afterRead.scrollTop <= beforeRead.scrollTop + 40,
    `[${label}] reading-history scrollTop jumped: ${beforeRead.scrollTop} -> ${afterRead.scrollTop}`,
  );
  console.log(`  reading-history preserve: PASS`);

  // 9. return near bottom + send → auto-scroll restores latest visibility.
  await page.evaluate(async () => {
    const t = document.getElementById("chat-thread");
    if (!t) return;
    t.scrollTop = t.scrollHeight;
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    t.scrollTop = t.scrollHeight;
  });
  await page.waitForTimeout(80);
  await sendTurn(page, "Please explain how illegal parking reports work in Buk-gu");
  await page.waitForTimeout(250);
  await assertLatestMessageVisible(page, `${label} re-pin auto-scroll`);
  console.log(`  re-pin auto-scroll: PASS`);

  const finalMetrics = await collectMetrics(page);
  assertContainment(finalMetrics, `${label} final`, baselineDoc, baselineCanvas);

  await context.close();
  return {
    label,
    after15,
    finalMetrics,
    baselineDoc,
    baselineCanvas,
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

  // #1174 boundary: only basic conversation — never click "예".
  // Avoid exact SUPPORTED map prompts that open multi-step guidance.
  const mobileTurns = [
    "공동주택과 담당 연락처를 알려주세요",
    "내일 날씨가 어때?",
    "Please explain how illegal parking reports work in Buk-gu",
  ];
  for (const q of mobileTurns) {
    await sendTurn(page, q);
  }

  const m = await collectMetrics(page);
  assert.ok(
    m.composer && m.composer.width > 40 && m.composer.height > 20,
    `[${label}] composer collapsed: ${JSON.stringify(m.composer)}`,
  );
  assert.ok(m.inputEnabled, `[${label}] input not operable`);
  assert.ok(m.sendEnabled, `[${label}] send not operable`);
  assert.ok(
    m.threadClientHeight > 40,
    `[${label}] thread clientHeight regression: ${m.threadClientHeight}`,
  );
  // Internal scroll should exist after a few long answers (or at least not explode document).
  assert.ok(
    m.documentScrollHeight < 4000,
    `[${label}] document scrollHeight exploded: ${m.documentScrollHeight}`,
  );
  assert.ok(
    m.msgCount >= 3,
    `[${label}] expected conversation messages, got ${m.msgCount}`,
  );
  console.log(
    `  mobile baseline: composer=${Math.round(m.composer.width)}x${Math.round(m.composer.height)} ` +
      `thread c=${m.threadClientHeight}/s=${m.threadScrollHeight} doc=${m.documentScrollHeight} PASS`,
  );

  await context.close();
  return { label, metrics: m };
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
  console.log("#1173 desktop chat scroll containment E2E");
  console.log(`warmup split: ${WARMUP_SPLIT_QUESTION}`);
  console.log("15-turn request list:");
  FIFTEEN_TURNS.forEach((t, i) => {
    console.log(`  ${i + 1}. [${t.kind}] ${t.q}`);
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
    await browser.close().catch(() => {});
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
        },
        smallAfter15: {
          doc: results.small.after15.documentScrollHeight,
          body: results.small.after15.bodyScrollHeight,
          threadClient: results.small.after15.threadClientHeight,
          threadScroll: results.small.after15.threadScrollHeight,
          shell: results.small.after15.shellHeight,
          canvas: results.small.after15.canvasHeight,
        },
        mobile: {
          doc: results.mobile.metrics.documentScrollHeight,
          threadClient: results.mobile.metrics.threadClientHeight,
          composer: results.mobile.metrics.composer,
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
