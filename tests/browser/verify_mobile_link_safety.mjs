/**
 * Browser E2E verifier for #1102 mobile link safety.
 *
 * The mobile demo renders untrusted answer markdown and untrusted source
 * URLs into the DOM. Both paths must go through `sanitizeMobileUrl`, which
 * allows only http(s) schemes and rejects javascript:, data:, vbscript:,
 * file:, blob:, protocol-relative (//host), credentialed, and malformed
 * URLs.
 *
 *   - Unsafe answer markdown links render as inert text (no <a>, no href).
 *   - Unsafe source cards are omitted entirely (no <a>, no exposed URL).
 *
 * Usage:
 *   node tests/browser/verify_mobile_link_safety.mjs http://127.0.0.1:8769
 *
 * Screenshots:
 *   /tmp/400-ai-finder-1102/mobile-link-safety.png
 */

import assert from "assert";
import { mkdirSync } from "fs";
import { join } from "path";
import { chromium } from "playwright";

const requestedBase = process.argv[2] || "http://127.0.0.1:8769";
const SCREENSHOT_DIR = "/tmp/400-ai-finder-1102";
mkdirSync(SCREENSHOT_DIR, { recursive: true });

function validateOrigin(raw) {
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(`Invalid URL: ${raw}`);
  }
  const hostname = parsed.hostname.replace(/^\[|\]$/g, "");
  const allowedHosts = new Set(["127.0.0.1", "localhost", "::1"]);
  if (parsed.protocol !== "http:") throw new Error("Only local http:// is allowed.");
  if (!allowedHosts.has(hostname)) throw new Error(`Non-local host rejected: ${parsed.hostname}`);
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error("Credentials, query, and hash are not allowed in baseUrl.");
  }
  return parsed.origin;
}

const BASE_ORIGIN = validateOrigin(requestedBase);
const PAGE_URL = `${BASE_ORIGIN}/`;

// Controlled /api/ask response. `answer` carries mixed-markdown links that
// exercise both the safe and every unsafe scheme; `sources` carries one safe
// and two unsafe source cards.
const MOCK_ANSWER = [
  "정상 안내는 [정상링크](https://bukgu.gwangju.kr/safe) 여기를 보세요.",
  "위험 링크: [자바스크립트공격](javascript:alert(1))",
  "위험 링크: [데이터공격](data:text/html,x)",
  "위험 링크: [프로토콜상대공격](//evil.example.com/p)",
].join("\n\n");

const MOCK_SOURCES = [
  { url: "https://bukgu.gwangju.kr/source", title: "정상출처" },
  { url: "javascript:alert(1)", title: "악성출처" },
  { url: "data:text/html,x", title: "데이터출처" },
];

const MOCK_RESPONSE = {
  ok: true,
  answer_ok: true,
  answer_status: "ok",
  site_id: "bukgu_gwangju",
  site_name: "전남광주통합특별시 북구",
  question: "링크 테스트",
  answer: MOCK_ANSWER,
  sources: MOCK_SOURCES,
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

function isLocalRequest(url) {
  if (url.startsWith("data:")) return true;
  try {
    return new URL(url).origin === BASE_ORIGIN;
  } catch {
    return false;
  }
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
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  page.on("request", (request) => requests.push(request.url()));
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  // Intercept the ask endpoint so we fully control the untrusted payload.
  await page.route(`${BASE_ORIGIN}/api/ask`, async (route, request) => {
    console.log(`[ROUTE] Intercepted ${request.method()} ${request.url()}`);
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(MOCK_RESPONSE),
    });
  });

  await page.goto(PAGE_URL, { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForSelector("#input", { timeout: 10000 });

  // Submit a question through the real UI to exercise the actual render path.
  await page.fill("#input", "링크 안전 테스트");
  await page.click("#sendBtn");

  // Assistant message must appear.
  await page.waitForSelector(".msg-row.assistant", { timeout: 10000 });
  await waitForText(page, ".msg-row.assistant .msg-content", "정상링크", 10000);

  // ── Answer markdown links ──────────────────────────────────────────────
  const answerHrefs = await page.evaluate(() => {
    const content = document.querySelector(".msg-row.assistant .msg-content");
    if (!content) return null;
    return Array.from(content.querySelectorAll("a")).map((a) => a.getAttribute("href"));
  });
  assert.ok(answerHrefs !== null, "assistant message content must exist");

  // Safe link renders as an external <a>.
  const safeHref = answerHrefs.find((h) => h && h.startsWith("https://bukgu.gwangju.kr/safe"));
  assert.ok(safeHref, `safe answer link must render as <a href>; got ${JSON.stringify(answerHrefs)}`);

  // No unsafe href anywhere in the answer.
  const unsafeAnswerHref = answerHrefs.find(
    (h) => h && (h.startsWith("javascript:") || h.startsWith("data:") || h.startsWith("//")),
  );
  assert.strictEqual(
    unsafeAnswerHref,
    undefined,
    `unsafe answer link must NOT render as <a href>: ${unsafeAnswerHref}`,
  );

  // Unsafe link labels survive as inert text (no anchor).
  const bodyText = await page.textContent(".msg-row.assistant .msg-content");
  assert.ok(bodyText.includes("자바스크립트공격"), "javascript: label must remain as text");
  assert.ok(bodyText.includes("데이터공격"), "data: label must remain as text");
  assert.ok(bodyText.includes("프로토콜상대공격"), "protocol-relative label must remain as text");

  // ── Source cards ───────────────────────────────────────────────────────
  const sourceLinks = await page.evaluate(() => {
    const wrap = document.querySelector(".msg-row.assistant .sources-wrap");
    if (!wrap) return [];
    return Array.from(wrap.querySelectorAll("a.source-link")).map((a) => ({
      href: a.getAttribute("href"),
      target: a.getAttribute("target"),
      rel: a.getAttribute("rel"),
      text: a.textContent,
    }));
  });

  // Exactly one (safe) source card must render; the two unsafe ones omitted.
  assert.strictEqual(
    sourceLinks.length,
    1,
    `only the safe source card must render; got ${sourceLinks.length}: ${JSON.stringify(sourceLinks)}`,
  );
  assert.strictEqual(sourceLinks[0].href, "https://bukgu.gwangju.kr/source");
  assert.strictEqual(sourceLinks[0].target, "_blank");
  assert.ok(
    (sourceLinks[0].rel || "").includes("noopener"),
    `safe source link must set rel=noopener; got ${sourceLinks[0].rel}`,
  );
  assert.ok(sourceLinks[0].text.includes("정상출처"), "safe source title must render");

  // The unsafe source titles/cards must be entirely absent from the DOM.
  const fullText = await page.textContent(".msg-row.assistant");
  assert.ok(!fullText.includes("악성출처"), "unsafe javascript: source card must be omitted");
  assert.ok(!fullText.includes("데이터출처"), "unsafe data: source card must be omitted");

  // No non-local network requests must have leaked from the mocked payloads.
  const nonLocal = requests.filter((url) => !isLocalRequest(url));
  assert.deepStrictEqual(nonLocal, [], `non-local requests: ${nonLocal.join(", ")}`);
  assert.deepStrictEqual(errors, [], `browser errors: ${errors.join("\n")}`);

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
