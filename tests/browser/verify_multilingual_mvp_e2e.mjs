import assert from "assert";
import { chromium } from "playwright";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, statSync, readFileSync } from "node:fs";
import { join, extname } from "node:path";
import { tmpdir } from "node:os";
import http from "node:http";

// #1155 — deterministic geometry contract: the chat header must never overlap
// the conversation content (greeting / answer / metadata / acknowledgement /
// confirmation actions) on any supported viewport. Header is in normal document
// flow; the first VISIBLE conversation rect top must sit at or below the header
// bottom. Content scrolled above the thread's visible area (clipped by overflow)
// is excluded — only elements that intersect the thread's scrollport count.
// TOL absorbs sub-pixel rounding.
const GEOM_TOL = 1.0;
function assertNoHeaderContentOverlap(page, ctx) {
  return page.evaluate((tol) => {
    const header = document.querySelector(".chat-shell__header");
    const headerRect = header ? header.getBoundingClientRect() : null;
    if (!headerRect) return { ok: true, skip: "no-header" };
    const headerBottom = headerRect.bottom;
    const thread = document.querySelector(".chat-thread");
    const threadRect = thread ? thread.getBoundingClientRect() : null;
    const threadTop = threadRect ? threadRect.top : 0;
    const threadBottom = threadRect ? threadRect.bottom : Infinity;
    // First visible conversation element: greeting/answer bubble or answer meta.
    const candidates = [
      ...Array.from(document.querySelectorAll(".chat-msg")),
      ...Array.from(document.querySelectorAll(".chat-answer-meta")),
    ].filter((el) => {
      const r = el.getBoundingClientRect();
      return r.height > 0 && r.width > 0;
    });
    // Pick the topmost candidate that intersects the thread's visible scrollport
    // (at least partially visible — not fully scrolled above or below).
    const visible = candidates
      .map((el) => {
        const r = el.getBoundingClientRect();
        return { el, top: r.top, bottom: r.bottom };
      })
      .filter((c) => {
        const visibleTop = Math.max(c.top, threadTop);
        const visibleBottom = Math.min(c.bottom, threadBottom);
        return visibleBottom - visibleTop > 0; // at least 1px visible
      })
      .sort((a, b) => a.top - b.top);
    const first = visible[0];
    if (!first) return { ok: true, skip: "no-content" };
    // The visible portion of this element starts at its intersection with thread.
    const contentTop = Math.max(first.top, threadTop);
    const gap = contentTop - headerBottom;
    return {
      ok: gap >= -tol,
      viewport: `${Math.round(window.innerWidth)}x${Math.round(window.innerHeight)}`,
      headerBottom: Math.round(headerBottom),
      contentTop: Math.round(contentTop),
      gap: Math.round(gap),
    };
  }, GEOM_TOL).then((res) => {
    if (res.skip) return;
    assert.ok(
      res.ok,
      `chat content must not overlap header: ${JSON.stringify({
        viewport: res.viewport,
        headerBottom: res.headerBottom,
        contentTop: res.contentTop,
        gap: res.gap,
        ctx,
      })}`,
    );
  });
}

// Forbidden stale Korean journey copy (allowed only when locale === ko).
const FORBIDDEN_KO = [
  "질문을 확인했습니다",
  "현재 AI 안내를 연결하지 못했습니다",
  "새 질문을 입력할 수 있습니다",
  "북구청 안내 화면에서 경로를 진행하고 있습니다",
  "최신 공식자료 확인",
  "북구청 공식 스냅샷",
  "공식 출처",
  "참고 출처",
  "예, 안내해 주세요",
  "아니요",
];

const LOCALE_ASSERTIONS = {
  ko: {
    shellTitle: "네비게이터",
    chipPrefix: "구청장에게 제안",
    yesText: "예, 안내해 주세요",
    noText: "아니요",
    ack: "질문을 확인했습니다",
    allowForbidden: true,
    expectedAnswer: "공동주택 관련 문의는 공동주택과에서 안내합니다.",
  },
  en: {
    shellTitle: "BUKGU AI CIVIC NAVIGATOR",
    chipPrefix: "I want to propose",
    yesText: "Yes, please guide me",
    noText: "No",
    ack: "I have your question",
    allowForbidden: false,
    expectedAnswer: "The Apartment Housing Division handles apartment-related inquiries.",
  },
  vi: {
    shellTitle: "BUKGU AI CIVIC NAVIGATOR",
    chipPrefix: "gửi đề xuất",
    yesText: "Vâng, hãy hướng dẫn tôi",
    noText: "Không",
    ack: "Tôi đã nhận câu hỏi",
    allowForbidden: false,
    expectedAnswer: "Phòng Quản lý nhà chung cư phụ trách các yêu cầu liên quan đến chung cư.",
  },
  th: {
    shellTitle: "BUKGU AI CIVIC NAVIGATOR",
    chipPrefix: "ฉันอยากส่งข้อเสนอ",
    yesText: "ใช่ ค่อยแนะนำด้วย",
    noText: "ไม่",
    ack: "ได้รับคำถาม",
    allowForbidden: false,
    expectedAnswer: "ฝ่ายที่อยู่อาศัยรวมดูแลคำถามที่เกี่ยวข้องกับอาคารชุด",
  },
  id: {
    shellTitle: "BUKGU AI CIVIC NAVIGATOR",
    chipPrefix: "Saya ingin mengusulkan",
    yesText: "Ya, bantu saya",
    noText: "Tidak",
    ack: "Pertanyaan sudah saya terima",
    allowForbidden: false,
    expectedAnswer: "Divisi Perumahan menangani pertanyaan terkait apartemen.",
  },
};

function buildAndServe() {
  const tmpDir = mkdtempSync(join(tmpdir(), "cf-mvp-e2e-"));
  console.log("Building to tmp dir:", tmpDir);
  const res = spawnSync("python", ["scripts/build_cloudflare_pages.py", "--mode", "live", "--out-dir", tmpDir], { stdio: "inherit", env: process.env });
  if (res.error || res.status !== 0) {
    throw new Error("Build failed");
  }

  const server = http.createServer((req, res) => {
    try {
      const urlPath = new URL(req.url, "http://127.0.0.1").pathname;
      let filePath = join(tmpDir, urlPath === "/" ? "index.html" : urlPath);

      let stat;
      try {
        stat = statSync(filePath);
      } catch (e) {
        try {
          stat = statSync(filePath + ".html");
          filePath = filePath + ".html";
        } catch (e2) {
          try {
             stat = statSync(join(filePath, "index.html"));
             filePath = join(filePath, "index.html");
          } catch(e3) {
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
         } catch(e) {
             res.writeHead(404);
             res.end("Not found");
             return;
         }
      }

      const content = readFileSync(filePath);
      const ext = extname(filePath);
      const mime = ext === ".js" ? "application/javascript" : ext === ".css" ? "text/css" : "text/html";
      res.writeHead(200, { "Content-Type": mime });
      res.end(content);
    } catch (e) {
      console.error(e);
      res.writeHead(500);
      res.end(e.toString());
    }
  });

  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      console.log(`Server listening on port ${port}`);
      resolve({
        origin: `http://127.0.0.1:${port}`,
        cleanup: () => {
          server.close();
          rmSync(tmpDir, { recursive: true, force: true });
        }
      });
    });
  });
}

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch {
    return chromium.launch({ headless: true, channel: "chrome" });
  }
}

function localeFromBody(text) {
  try {
    return JSON.parse(text).locale || null;
  } catch {
    return null;
  }
}

async function runLocaleTest(browser, origin, locale, expectations, viewport) {
  const vp = viewport || { width: 1440, height: 900 };
  const label = `multilingual-${locale}-${vp.width}x${vp.height}`;
  console.log(`[${label}] start`);

  const context = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    reducedMotion: "reduce",
  });

  const page = await context.newPage();
  const errors = [];
  const requestLocales = [];
  let apiRequestCount = 0;

  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  // Check for unwanted external requests
  page.on("request", (req) => {
    const u = new URL(req.url());
    if (u.origin !== origin && u.hostname !== "127.0.0.1" && u.hostname !== "localhost") {
       errors.push(`External request forbidden: ${req.url()}`);
    }
  });

  await page.route("**/api/mvp/ask", async (route) => {
    apiRequestCount++;
    const postBody = route.request().postData();
    const bodyLocale = localeFromBody(postBody);
    if (bodyLocale) requestLocales.push(bodyLocale);
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        ok: true,
        answer: expectations.expectedAnswer,
        action: "housing_department",
        confidence: 1,
        failure_code: "",
        locale: bodyLocale || "ko",
        freshness_state: "official_snapshot",
        sources: [
          { title: "북구청 공동주택 안내", url: "https://bukgu.gwangju.kr/board.es?mid=a10602012601", official: true },
        ],
        captured_at: "2026-07-15T01:00:00.000Z",
        verified_at: "2026-07-15T01:00:00.000Z",
      }),
    });
  });

  // Use bare live entry without mvp=1 explicitly
  await page.goto(`${origin}/mvp/?lang=${locale}`, {
    waitUntil: "networkidle",
    timeout: 20000,
  });

  // 1. window.location.search에 mvp=1이 주입됐는가
  await page.waitForFunction(() => window.location.search.includes("mvp=1"), { timeout: 5000 });
  console.log(`[${label}] mvp=1 injected successfully`);

  // 1b. Shell title localized (wait until attached and populated)
  await page.waitForSelector(".chat-shell__title", { state: "attached", timeout: 8000 });
  await page.waitForFunction((expected) => {
    const el = document.querySelector(".chat-shell__title");
    return el && el.innerText === expected;
  }, expectations.shellTitle, { timeout: 8000 });
  console.log(`[${label}] shell title verified`);

  // 2. document.documentElement.lang
  const docLang = await page.evaluate(() => document.documentElement.lang);
  assert.strictEqual(docLang, locale, `[${label}] documentElement.lang`);

  // 3. Greeting localized (no Korean greeting in non-ko shell)
  await page.waitForSelector(".chat-bubble--ai", { state: "visible" });
  const greeting = await page.evaluate(() => {
    const el = document.querySelector(".chat-bubble--ai");
    return el ? el.innerText : "";
  });
  if (!expectations.allowForbidden) {
    assert.ok(!/안녕하세요/.test(greeting), `[${label}] Korean greeting leaked: ${greeting}`);
  }

  // 4. Recommendation chip localized
  const chip = page.locator(".chat-chip").filter({ hasText: expectations.chipPrefix }).first();
  await chip.waitFor({ state: "visible", timeout: 5000 });
  const chipText = await chip.innerText();
  assert.ok(chipText.includes(expectations.chipPrefix), `[${label}] chip prefix: ${chipText}`);
  console.log(`[${label}] chip verified`);

  // 2. (Requirements) 질문 제출 전 CitizenMvpBridge가 undefined여도 실패 처리하지 않는다
  const bridgeBefore = await page.evaluate(() => typeof window.CitizenMvpBridge);
  console.log(`[${label}] bridge typeof before submit: ${bridgeBefore}`);
  // It's totally fine if it's undefined.

  // 5. Type a question into the composer and submit
  const composer = page.locator("input.chat-composer__input").first();
  await composer.fill("공동주택 관련 문의는 어느 부서에 해야 하나요?");

  const [response] = await Promise.all([
    page.waitForResponse("**/api/mvp/ask", { timeout: 10000 }),
    page.getByRole("button", { name: /보내기|Send|Gửi|ส่ง|Kirim/i }).first().click(),
  ]);

  assert.strictEqual(apiRequestCount > 0, true, `[${label}] /api/mvp/ask was called`);

  // 5. (Requirements) 제출 후 bridge script 또는 window.CitizenMvpBridge가 로드됐는지 확인
  await page.waitForFunction(() => {
    return typeof window.CitizenMvpBridge !== "undefined" || document.querySelector('script[data-mvp-bridge="1"]');
  }, { timeout: 5000 });
  console.log(`[${label}] MVP Bridge loaded after submit`);

  // Verify answer bubble explicitly
  const finalAnswerBubble = page.locator(".chat-bubble--ai").filter({ hasText: expectations.expectedAnswer }).first();
  await finalAnswerBubble.waitFor({ state: "visible", timeout: 10000 });
  const finalAnswerText = await finalAnswerBubble.innerText();
  assert.ok(finalAnswerText.includes(expectations.expectedAnswer), `[${label}] expected answer mismatch. Got: ${finalAnswerText}`);

  // #1155 — answer + metadata + acknowledgement/confirmation must not overlap header.
  await page.waitForTimeout(300);
  await assertNoHeaderContentOverlap(page, `${label} answer`);

  const bodyText = await page.evaluate(() => document.body.innerText);

  // 6a. acknowledgement localized
  assert.ok(bodyText.includes(expectations.ack), `[${label}] split.ready ack missing: ${expectations.ack}`);

  // 6b. no forbidden Korean journey copy in non-Korean shell
  if (!expectations.allowForbidden) {
    for (const lit of FORBIDDEN_KO) {
      assert.ok(!bodyText.includes(lit), `[${label}] forbidden Korean copy: "${lit}"`);
    }
  }

  // 7. yes/no actions localized
  const yesBtn = page.getByRole("button", { name: expectations.yesText, exact: true });
  const noBtn = page.getByRole("button", { name: expectations.noText, exact: true });
  assert.strictEqual(await yesBtn.count(), 1, `[${label}] yes button`);
  assert.strictEqual(await noBtn.count(), 1, `[${label}] no button`);

  // 8. journey status localized
  const journeyStatus = await page.evaluate(() => {
    const el = document.getElementById("chat-journey-status");
    return el ? el.textContent : "";
  });
  if (!expectations.allowForbidden && journeyStatus) {
    for (const lit of FORBIDDEN_KO) {
      assert.ok(!journeyStatus.includes(lit), `[${label}] journey status KO: "${lit}"`);
    }
  }

  // 9. freshness + source label localized
  const freshnessText = await page.evaluate(() => {
    const el = document.querySelector(".chat-answer-meta__status");
    return el ? el.textContent : "";
  });
  if (!expectations.allowForbidden && freshnessText) {
    assert.ok(!/최신 공식자료 확인|북구청 공식 스냅샷/.test(freshnessText),
      `[${label}] freshness Korean: ${freshnessText}`);
  }
  const sourceLabel = await page.evaluate(() => {
    const el = document.querySelector(".chat-answer-meta__source");
    return el ? el.textContent : "";
  });
  if (!expectations.allowForbidden && sourceLabel) {
    assert.ok(!/공식 출처|참고 출처/.test(sourceLabel), `[${label}] source Korean: ${sourceLabel}`);
  }

  // 10. request body carried the locale
  assert.strictEqual(requestLocales.length > 0, true, `[${label}] /api/mvp/ask fired`);
  assert.ok(
    requestLocales.every((l) => l === locale),
    `[${label}] request locale mismatch: ${JSON.stringify(requestLocales)} expected ${locale}`,
  );

  // 11. no errors
  assert.deepStrictEqual(errors, [], `[${label}] no errors: ${errors.join(" | ")}`);

  await context.close();
  console.log(`[${label}] PASS`);
}

async function runLocaleTransitionTest(browser, origin, viewport) {
  const vp = viewport || { width: 1440, height: 900 };
  const label = `locale-transition-${vp.width}x${vp.height}`;
  console.log(`[${label}] start`);

  const context = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    reducedMotion: "reduce",
  });

  const page = await context.newPage();
  const errors = [];

  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  let resolveAsk;
  const pendingAsk = new Promise(r => { resolveAsk = r; });

  await page.route("**/api/mvp/ask", async (route) => {
    await pendingAsk;
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        ok: true,
        answer: "Delayed answer ko.",
        action: "housing_department",
        confidence: 1,
        failure_code: "",
        locale: "ko",
        freshness_state: "official_snapshot",
        sources: [],
      }),
    });
  });

  // 1. /mvp/?lang=ko 로드
  await page.goto(`${origin}/mvp/?lang=ko`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => window.location.search.includes("mvp=1"));

  // 3. 한국어 질문 제출
  const composer = page.locator("input.chat-composer__input").first();
  await composer.fill("공동주택 관련 문의");

  // 4. 요청이 실제 시작된 것을 확인 (사전 waiter 등록)
  const [request] = await Promise.all([
    page.waitForRequest("**/api/mvp/ask"),
    page.getByRole("button", { name: "보내기" }).first().click(),
  ]);

  // 5. 같은 페이지의 #chat-lang 에서 언어 변경
  await page.locator("#chat-lang").selectOption("en");

  // 6. 다음 조건이 안정화될 때까지 기다림
  await page.waitForFunction(() => document.documentElement.lang === "en");
  await page.waitForFunction(() => document.body.getAttribute("data-first-use-state") === "entry");

  const expectedEnWelcome = "Hello. I am BUKGU AI CIVIC NAVIGATOR. Ask about a public service and I will open the relevant screen and guide you through the steps.";

  await page.waitForFunction((expected) => {
    const userBubbles = document.querySelectorAll(".chat-bubble--user");
    if (userBubbles.length !== 0) return false;

    const aiBubbles = Array.from(document.querySelectorAll(".chat-bubble--ai"));
    const hasEnWelcome = aiBubbles.some(b => b.innerText && b.innerText.includes(expected));
    const hasKoWelcome = aiBubbles.some(b => b.innerText && b.innerText.includes("안녕하세요"));

    return hasEnWelcome && !hasKoWelcome;
  }, expectedEnWelcome);

  assert.ok(await composer.isEnabled(), `[${label}] composer usable after reset`);

  // 7. 지연된 한국어 응답을 resolve
  resolveAsk();

  // late callback 방지를 위한 짧은 대기
  await page.waitForTimeout(500);

  // 8. 조건 기반으로 확인
  const bodyText = await page.evaluate(() => document.body.innerText);
  assert.ok(!bodyText.includes("Delayed answer ko"), `[${label}] delayed ko leaked`);
  assert.ok(!bodyText.includes("질문을 확인했습니다"), `[${label}] ko ack leaked`);
  assert.ok(bodyText.includes(expectedEnWelcome), `[${label}] english greeting retained`);

  assert.ok(await composer.isEnabled(), `[${label}] composer usable`);
  assert.deepStrictEqual(errors, [], `[${label}] no errors: ${errors.join(" | ")}`);

  // #1155 — after same-page locale change, content must not overlap header.
  await page.waitForTimeout(300);
  await assertNoHeaderContentOverlap(page, `${label} after-locale-change`);

  await context.close();
  console.log(`[${label}] PASS`);
}

async function runBackNavigationTest(browser, origin) {
  const label = "back-navigation";
  console.log(`[${label}] start`);

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
  });

  const page = await context.newPage();

  await page.route("**/api/mvp/ask", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        ok: true,
        answer: "Answer ko",
        action: "none",
        confidence: 1,
        failure_code: "",
        locale: "ko",
        freshness_state: "unavailable",
        sources: []
      })
    });
  });

  await page.goto(`${origin}/mvp/?lang=ko`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => window.location.search.includes("mvp=1"));

  const composer = page.locator("input.chat-composer__input").first();
  await composer.fill("이전 대화 복원 테스트");

  await Promise.all([
    page.waitForResponse("**/api/mvp/ask"),
    page.getByRole("button", { name: "보내기" }).first().click(),
  ]);

  // Wait for the answer to appear
  await page.locator(".chat-bubble--ai").nth(1).waitFor({ state: "visible" });

  // Navigate away
  await page.goto("about:blank");

  // Go back
  await page.goBack({ waitUntil: "networkidle" });

  // Check if old conversation is restored
  const bodyText = await page.evaluate(() => document.body.innerText);
  assert.ok(!bodyText.includes("이전 대화 복원 테스트"), `[${label}] previous conversation restored`);

  await context.close();
  console.log(`[${label}] PASS`);
}

async function main() {
  const { origin, cleanup } = await buildAndServe();
  console.log(`Serving from ${origin}`);

  const browser = await launchBrowser();
  try {
    // #1155 geometry matrix: viewport × locale.
    const GEOM_MATRIX = [
      { width: 390, height: 844, locales: ["ko", "en", "vi", "th", "id"] },
      { width: 360, height: 800, locales: ["vi", "th", "id"] },
      { width: 1440, height: 900, locales: ["ko", "en"] },
    ];
    for (const { width, height, locales } of GEOM_MATRIX) {
      const vp = { width, height };
      for (const locale of locales) {
        await runLocaleTest(browser, origin, locale, LOCALE_ASSERTIONS[locale], vp);
      }
    }
    // Keep the prior full-locale 1440×900 coverage for copy contracts.
    for (const [locale, expectations] of Object.entries(LOCALE_ASSERTIONS)) {
      if (!GEOM_MATRIX[2].locales.includes(locale)) {
        await runLocaleTest(browser, origin, locale, expectations, { width: 1440, height: 900 });
      }
    }
    await runLocaleTransitionTest(browser, origin, { width: 390, height: 844 });
    await runLocaleTransitionTest(browser, origin, { width: 360, height: 800 });
    await runLocaleTransitionTest(browser, origin, { width: 1440, height: 900 });
    await runBackNavigationTest(browser, origin);
  } finally {
    await browser.close();
    cleanup();
  }
  console.log("Multilingual MVP E2E: all locales & transition PASSED.");
}

main().catch((error) => {
  console.error("Multilingual MVP E2E FAILED:");
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
