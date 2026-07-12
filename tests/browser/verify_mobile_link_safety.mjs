/**
 * Browser E2E verifier for #1102 mobile link safety.
 *
 * The mobile demo renders untrusted answer markdown and untrusted source
 * URLs into the DOM. Both paths go through `sanitizeMobileUrl`, the single
 * canonical sanitizer that:
 *
 *   - allows only http(s) absolute URLs and explicitly-approved same-origin
 *     relative forms (/path, ?query, #fragment);
 *   - rejects javascript:, data:, vbscript:, file:, blob:, protocol-relative
 *     (//host), credentialed, control-character, backslash, malformed and
 *     bare-relative URLs (fail-closed);
 *
 * Unsafe answer markdown links render as inert text (no <a>, no href).
 * Unsafe source cards are omitted entirely; if every source is unsafe the
 * `.sources-wrap` section is absent from the DOM.
 *
 * This runs against the REAL live Cloudflare Pages build (not the Python dev
 * server) and intercepts the live `/api/mvp/ask` function.
 *
 * Usage:
 *   node tests/browser/verify_mobile_link_safety.mjs http://127.0.0.1:8769/mobile.html
 *
 * Screenshots:
 *   <os-tmp>/400-ai-finder-1102/mobile-link-safety.png
 */

import assert from "assert";
import { mkdirSync, readFileSync } from "fs";
import { join } from "path";
import os from "os";
import { chromium } from "playwright";

const PAGE_URL = process.argv[2] || "http://127.0.0.1:8769/mobile.html";
const SCREENSHOT_DIR = join(os.tmpdir(), "400-ai-finder-1102");
mkdirSync(SCREENSHOT_DIR, { recursive: true });

// ── Known browser executable paths for fallback (no browser download) ─────
// GitHub runners do not have the Playwright-bundled Chromium installed
// (npm ci runs with --ignore-scripts), so fall back to a browser already
// present on the host before giving up.
const KNOWN_BROWSER_PATHS = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
];

async function launchBrowser() {
  const launchAttempts = [];
  const errors = [];

  const envPath = process.env.MOBILE_LINK_BROWSER_EXECUTABLE;
  if (envPath) {
    launchAttempts.push({
      name: `env: ${envPath}`,
      launch: () => chromium.launch({ headless: true, executablePath: envPath }),
    });
  }

  launchAttempts.push({
    name: "channel: chrome",
    launch: () => chromium.launch({ headless: true, channel: "chrome" }),
  });

  for (const p of KNOWN_BROWSER_PATHS) {
    let exists = false;
    try { readFileSync(p); exists = true; } catch (_) {}
    if (exists) {
      launchAttempts.push({
        name: `path: ${p}`,
        launch: () => chromium.launch({ headless: true, executablePath: p }),
      });
    }
  }

  launchAttempts.push({
    name: "default playwright chromium",
    launch: () => chromium.launch({ headless: true }),
  });

  for (const attempt of launchAttempts) {
    try {
      const browser = await attempt.launch();
      let version = "unknown";
      try {
        if (browser && typeof browser.version === "function") {
          version = await browser.version();
        }
      } catch (_) {
        version = "unknown";
      }
      console.log(`  Browser launched (${attempt.name}, v${version}) ✓`);
      return { browser, launchInfo: { source: attempt.name, version } };
    } catch (e) {
      errors.push(`  [${attempt.name}] ${e.message}`);
    }
  }

  throw new Error(`Cannot launch any browser. Attempts:\n${errors.join("\n")}`);
}

function validateOrigin(rawUrl) {
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch {
    throw new Error(`Invalid URL: ${rawUrl}`);
  }
  const hostname = parsed.hostname.replace(/^\[|\]$/g, "");
  const allowedHosts = new Set(["127.0.0.1", "localhost", "::1"]);
  if (parsed.protocol !== "http:") throw new Error("Only local http:// is allowed.");
  if (!allowedHosts.has(hostname)) throw new Error(`Non-local host rejected: ${parsed.hostname}`);
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error("Credentials, query, and hash are not allowed in the page URL.");
  }
  return parsed.origin;
}

const BASE_ORIGIN = validateOrigin(PAGE_URL);

// Real control character that must reach the sanitizer unmodified.
const TAB = "	";

// ── Scenario A: mixed safe + unsafe answer/sources ─────────────────────────
const MIXED_ANSWER = [
  "정상 외부 안내는 [정상외부링크](https://example.com/service?q=1#top) 여기를 보세요.",
  "정상 도움말 경로는 [정상도움말경로](/mobile/help?q=1#top) 입니다.",
  "정상 뷰 쿼리는 [정상뷰쿼리](?view=help) 입니다.",
  "정상 해시는 [정상해시](#details) 입니다.",
  "위험: [자바스크립트공격](javascript:alert(1))",
  "위험: [데이터공격](data:text/html,x)",
  "위험: [브이스크립트공격](vbscript:msgbox(1))",
  "위험: [파일공격](file:///etc/passwd)",
  "위험: [블롭공격](blob:https://example.com/id)",
  "위험: [자격증명공격](https://user:pass@example.com/)",
  "위험: [프로토콜상대공격](//evil.example/p)",
  "위험: [백슬래시공격](\\\\evil.example/path)",
  "위험: [백슬래시스킴공격](https:\\\\evil.example/path)",
  "위험: [제어문자공격](https://example.com/" + TAB + "bad)",
  "위험: [불량형식공격](http://)",
  "위험: [베어상대공격](foo/bar)",
  "위험: [상위상대공격](../relative)",
].join("\n\n");

const MIXED_SOURCES = [
  { url: "https://example.com/source", title: "정상출처" },
  { url: "/mobile/help", title: "도움말출처" },
  { url: "javascript:alert(1)", title: "악성출처" },
  { url: "data:text/html,x", title: "데이터출처" },
  { url: "vbscript:msgbox(1)", title: "브이스크립트출처" },
  { url: "file:///etc/passwd", title: "파일출처" },
  { url: "blob:https://example.com/id", title: "블롭출처" },
  { url: "https://user:pass@example.com/", title: "자격증명출처" },
  { url: "//evil.example/p", title: "프로토콜상대출처" },
  { url: "\\\\evil.example/path", title: "백슬래시출처" },
  { url: "https:\\\\evil.example/path", title: "백슬래시스킴출처" },
  { url: "https://example.com/" + TAB + "bad", title: "제어문자출처" },
  { url: "http://", title: "불량형식출처" },
  { url: "foo/bar", title: "베어상대출처" },
  { url: "../relative", title: "상위상대출처" },
];

const MIXED_RESPONSE = {
  ok: true,
  answer_ok: true,
  answer_status: "ok",
  site_id: "bukgu_gwangju",
  site_name: "전남광주통합특별시 북구",
  question: "링크 테스트",
  answer: MIXED_ANSWER,
  sources: MIXED_SOURCES,
  provider: "mock",
  model: "mock",
  snapshot_mode: true,
  llm_live: false,
  llm_status: "mock",
  llm_label: "mock",
  warnings: [],
  route: "site_search",
  should_search_site: true,
  answer_mode: "retrieval_answer",
  source_weak: false,
  fetch_diagnostic: null,
};

// ── Scenario B: all sources unsafe, answer safe ───────────────────────────
const ALL_UNSAFE_SOURCES_RESPONSE = {
  ...MIXED_RESPONSE,
  answer: "안전한 답변만 있습니다. [정상외부링크](https://example.com/service?q=1#top)",
  sources: [
    { url: "javascript:alert(1)", title: "악성출처" },
    { url: "data:text/html,x", title: "데이터출처" },
    { url: "https://user:pass@example.com/", title: "자격증명출처" },
  ],
};

function isLocalRequest(url) {
  if (url.startsWith("data:")) return true;
  try {
    return new URL(url).origin === BASE_ORIGIN;
  } catch {
    return false;
  }
}

function isUnsafeHref(href) {
  if (!href) return false;
  return (
    href.startsWith("javascript:") ||
    href.startsWith("data:") ||
    href.startsWith("vbscript:") ||
    href.startsWith("file:") ||
    href.startsWith("blob:") ||
    href.startsWith("//") ||
    href.startsWith("\\\\") ||
    /https?:\\/.test(href) ||
    /:\/\/[^/]*@/.test(href) ||
    /\t/.test(href) || /\n/.test(href) || /\x00/.test(href)
  );
}

function deepAssertNoRequestFailures(nonLocal, errors) {
  assert.deepStrictEqual(nonLocal, [], `non-local requests: ${nonLocal.join(", ")}`);
  assert.deepStrictEqual(errors, [], `browser errors: ${errors.join("\n")}`);
}

async function waitForText(page, selector, text, timeout = 10000) {
  await page.waitForFunction(
    ({ selector, text }) => {
      const el = document.querySelector(selector);
      return el && el.textContent && el.textContent.includes(text);
    },
    { selector, text },
    { timeout },
  );
}

async function main() {
  const requests = [];
  const errors = [];
  const { browser, launchInfo } = await launchBrowser();
  console.log(`[browser] source=${launchInfo.source} version=${launchInfo.version}`);
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  page.on("request", (request) => requests.push(request.url()));
  page.on("pageerror", (error) => errors.push("pageerror: " + error.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push("console: " + msg.text());
  });
  page.on("requestfailed", (request) => {
    const failure = request.failure();
    errors.push(
      "requestfailed: " + request.url() + " " + (failure ? failure.errorText : ""),
    );
  });

  let scenario = "mixed";
  await page.route(`${BASE_ORIGIN}/api/mvp/ask`, async (route, request) => {
    const body = scenario === "all-unsafe"
      ? ALL_UNSAFE_SOURCES_RESPONSE
      : MIXED_RESPONSE;
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(body),
    });
  });

  // ── Scenario A: mixed safe + unsafe ──────────────────────────────────────
  await page.goto(PAGE_URL, { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForSelector("#input", { timeout: 10000 });

  // Install the XSS sentinel BEFORE the untrusted payload is rendered.
  await page.evaluate(() => {
    window.__MOBILE_LINK_XSS__ = "safe";
  });

  await page.fill("#input", "링크 안전 테스트");
  await page.click("#sendBtn");

  await page.waitForSelector(".msg-row.assistant", { timeout: 10000 });
  await waitForText(page, ".msg-row.assistant .msg-content", "정상외부링크", 10000);

  const pageOrigin = await page.evaluate(() => window.location.origin);
  assert.strictEqual(pageOrigin, BASE_ORIGIN, "page origin must match base origin");

  // ── Answer anchors ───────────────────────────────────────────────────────
  const answerLinks = await page.evaluate(() => {
    const content = document.querySelector(".msg-row.assistant .msg-content");
    if (!content) return null;
    return Array.from(content.querySelectorAll("a")).map((a) => ({
      href: a.getAttribute("href"),
      target: a.getAttribute("target"),
      rel: a.getAttribute("rel") || "",
      text: a.textContent,
    }));
  });
  assert.ok(answerLinks !== null, "assistant answer content must exist");

  // No unsafe href anywhere in the answer.
  const unsafeAnswerHref = answerLinks.find((l) => isUnsafeHref(l.href));
  assert.strictEqual(
    unsafeAnswerHref,
    undefined,
    `unsafe answer href must NOT render: ${JSON.stringify(unsafeAnswerHref)}`,
  );

  // No anchor with raw "#" fallback.
  const hashFallback = answerLinks.find((l) => l.href === "#");
  assert.strictEqual(hashFallback, undefined, "href=\"#\" fallback must not exist");

  // Safe EXTERNAL answer link.
  const safeExternal = answerLinks.find((l) =>
    (l.href || "").startsWith("https://example.com/service?q=1#top"),
  );
  assert.ok(safeExternal, `safe external answer link must render; got ${JSON.stringify(answerLinks)}`);
  assert.ok(safeExternal.href.startsWith("https://"), "safe external href must stay HTTPS");
  assert.strictEqual(safeExternal.target, "_blank", "safe external link must open in new tab");
  assert.ok(safeExternal.rel.includes("noopener"), "safe external rel must contain noopener");
  assert.ok(safeExternal.rel.includes("noreferrer"), "safe external rel must contain noreferrer");

  // Safe SAME-ORIGIN relative answer links (path / ?, #).
  const relPath = answerLinks.find((l) => (l.href || "").includes("/mobile/help?q=1#top"));
  const relQuery = answerLinks.find((l) => (l.href || "").includes("?view=help"));
  const relHash = answerLinks.find((l) => (l.href || "").endsWith("#details"));
  assert.ok(relPath, "safe relative /mobile/help link must render");
  assert.ok(relQuery, "safe relative ?view=help link must render");
  assert.ok(relHash, "safe relative #details link must render");

  for (const l of [relPath, relQuery, relHash]) {
    assert.ok(l.href.startsWith(pageOrigin), `same-origin link must keep origin (${l.href})`);
    assert.strictEqual(l.target, null, "same-origin link must NOT target _blank");
    assert.strictEqual(l.rel, "", "same-origin link needs no external rel");
  }
  assert.ok(relPath.href.includes("?q=1") && relPath.href.includes("#top"),
    "same-origin link must preserve query/hash");
  assert.ok(relQuery.href.includes("?view=help"), "query relative link must preserve query");
  assert.ok(relHash.href.endsWith("#details"), "hash relative link must preserve hash");

  // Unsafe answer labels survive as inert text (no anchor with that text).
  const answerContent = await page.evaluate(() => {
    const el = document.querySelector(".msg-row.assistant .msg-content");
    return {
      text: el.textContent,
      html: el.innerHTML,
    };
  });
  const unsafeLabels = [
    "자바스크립트공격", "데이터공격", "브이스크립트공격", "파일공격",
    "블롭공격", "자격증명공격", "프로토콜상대공격", "백슬래시공격",
    "백슬래시스킴공격", "제어문자공격", "불량형식공격", "베어상대공격",
    "상위상대공격",
  ];
  for (const label of unsafeLabels) {
    assert.ok(answerContent.text.includes(label), `unsafe label must remain as text: ${label}`);
  }
  // No anchor may carry an unsafe label as its link text.
  const unsafeLabelAnchor = answerLinks.find((l) => unsafeLabels.includes(l.text));
  assert.strictEqual(
    unsafeLabelAnchor,
    undefined,
    `unsafe label must not become an anchor: ${JSON.stringify(unsafeLabelAnchor)}`,
  );

  // Raw dangerous URL strings must not appear in the DOM HTML/text.
  const rawForbidden = [
    "javascript:alert", "data:text/html", "vbscript:msgbox", "file:///etc/passwd",
    "blob:https://example.com", "user:pass@example.com", "//evil.example",
    "https:\\\\evil.example", "../relative", "foo/bar",
  ];
  for (const raw of rawForbidden) {
    assert.ok(
      !answerContent.html.includes(raw) && !answerContent.text.includes(raw),
      `raw dangerous URL must be absent from DOM: ${raw}`,
    );
  }
  // Backslashes must never appear in rendered answer HTML.
  assert.ok(!answerContent.html.includes("\\"), "backslash must not appear in answer HTML");

  // Sentinel must remain unchanged (no script injection via unsafe labels).
  const sentinel = await page.evaluate(() => window.__MOBILE_LINK_XSS__);
  assert.strictEqual(sentinel, "safe", "XSS sentinel must remain 'safe'");

  // ── Source cards ─────────────────────────────────────────────────────────
  const sourceLinks = await page.evaluate(() => {
    const wrap = document.querySelector(".msg-row.assistant .sources-wrap");
    if (!wrap) return [];
    return Array.from(wrap.querySelectorAll("a.source-link")).map((a) => ({
      href: a.getAttribute("href"),
      target: a.getAttribute("target"),
      rel: a.getAttribute("rel") || "",
      text: a.textContent,
    }));
  });

  // Only the two safe source cards must render; all unsafe ones omitted.
  assert.strictEqual(
    sourceLinks.length,
    2,
    `only the safe source cards must render; got ${sourceLinks.length}: ${JSON.stringify(sourceLinks)}`,
  );
  const extSrc = sourceLinks.find((s) => (s.href || "").startsWith("https://example.com/source"));
  const relSrc = sourceLinks.find((s) => (s.href || "").includes("/mobile/help"));
  assert.ok(extSrc, "safe external source card must render");
  assert.ok(relSrc, "safe same-origin source card must render");

  assert.ok(extSrc.href.startsWith("https://"), "safe external source href must stay HTTPS");
  assert.strictEqual(extSrc.target, "_blank", "safe external source must target _blank");
  assert.ok(extSrc.rel.includes("noopener"), "safe external source rel must contain noopener");
  assert.ok(extSrc.rel.includes("noreferrer"), "safe external source rel must contain noreferrer");

  assert.ok(relSrc.href.startsWith(pageOrigin), "safe same-origin source must keep origin");
  assert.strictEqual(relSrc.target, null, "safe same-origin source must not target _blank");
  assert.strictEqual(relSrc.rel, "", "safe same-origin source needs no external rel");

  assert.ok(extSrc.text.includes("정상출처"), "safe external source title must render");
  assert.ok(relSrc.text.includes("도움말출처"), "safe same-origin source title must render");

  // Unsafe source titles/cards must be entirely absent.
  const assistantText = await page.textContent(".msg-row.assistant");
  const unsafeSourceTitles = [
    "악성출처", "데이터출처", "브이스크립트출처", "파일출처", "블롭출처",
    "자격증명출처", "프로토콜상대출처", "백슬래시출처", "백슬래시스킴출처",
    "제어문자출처", "불량형식출처", "베어상대출처", "상위상대출처",
  ];
  for (const title of unsafeSourceTitles) {
    assert.ok(!assistantText.includes(title), `unsafe source title must be omitted: ${title}`);
  }

  // No raw dangerous source URLs in the DOM HTML.
  const assistantHtml = await page.evaluate(() =>
    document.querySelector(".msg-row.assistant").innerHTML,
  );
  for (const raw of rawForbidden) {
    assert.ok(
      !assistantHtml.includes(raw),
      `raw dangerous source URL must be absent from DOM: ${raw}`,
    );
  }
  assert.ok(!assistantHtml.includes("\\"), "backslash must not appear in source HTML");

  // ── Scenario B: all sources unsafe → no .sources-wrap ────────────────────
  scenario = "all-unsafe";
  // Reload so the fresh assistant message reflects the all-unsafe payload.
  await page.goto(PAGE_URL, { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForSelector("#input", { timeout: 10000 });
  await page.evaluate(() => {
    window.__MOBILE_LINK_XSS__ = "safe";
  });
  await page.fill("#input", "전부 불안전 출처");
  await page.click("#sendBtn");

  await page.waitForSelector(".msg-row.assistant", { timeout: 10000 });
  await waitForText(page, ".msg-row.assistant .msg-content", "안전한 답변만 있습니다", 10000);

  const wrapPresent = await page.evaluate(() => {
    const row = document.querySelector(".msg-row.assistant");
    if (!row) return false;
    return !!row.querySelector(".sources-wrap");
  });
  assert.strictEqual(wrapPresent, false, "when all sources unsafe, .sources-wrap must be absent");
  const sentinelB = await page.evaluate(() => window.__MOBILE_LINK_XSS__);
  assert.strictEqual(sentinelB, "safe", "XSS sentinel must remain 'safe' after all-unsafe scenario");

  // ── Common guardrails ─────────────────────────────────────────────────────
  const nonLocal = requests.filter((url) => !isLocalRequest(url));
  deepAssertNoRequestFailures(nonLocal, errors);

  const screenshotPath = join(SCREENSHOT_DIR, "mobile-link-safety.png");
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await browser.close();

  console.log("Mobile link safety E2E passed.");
  console.log(`Screenshot: ${screenshotPath}`);
}

main().catch((error) => {
  console.error("Mobile link safety E2E FAILED:");
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
