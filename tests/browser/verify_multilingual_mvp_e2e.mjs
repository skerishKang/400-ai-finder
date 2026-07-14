/**
 * Browser E2E for MVP multilingual shell — verifies each of the 5 locales
 * (ko, en, vi, th, id) loads with correct localized shell title, chip text,
 * and confirm-run button text.
 */

import assert from "assert";
import { chromium } from "playwright";

const BASE_ORIGIN = (function validate(raw) {
  const parsed = new URL(process.argv[2] || "http://127.0.0.1:8080");
  if (
    parsed.protocol !== "http:" ||
    !new Set(["127.0.0.1", "localhost", "::1"]).has(parsed.hostname)
  ) {
    throw new Error("Multilingual E2E accepts only a local http origin.");
  }
  return parsed.origin;
})();

const LOCALE_ASSERTIONS = {
  // locale: { shellTitle, chipPrefix, confirmText }
  // Values from citizen-i18n.js locale dictionary
  ko: { shellTitle: "북구청 AI 민원 네비게이터", chipPrefix: "구청장에게 제안", confirmText: "예, 안내해 주세요" },
  en: { shellTitle: "BUKGU AI CIVIC NAVIGATOR", chipPrefix: "I want to propose", confirmText: "Yes, please guide me" },
  vi: { shellTitle: "BUKGU AI CIVIC NAVIGATOR", chipPrefix: "gửi đề xuất", confirmText: "Vâng, hãy hướng dẫn tôi" },
  th: { shellTitle: "BUKGU AI CIVIC NAVIGATOR", chipPrefix: "ฉันอยากส่งข้อเสนอ", confirmText: "ใช่ ค่อยแนะนำด้วย" },
  id: { shellTitle: "BUKGU AI CIVIC NAVIGATOR", chipPrefix: "Saya ingin mengusulkan", confirmText: "Ya, bantu saya" },
};

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch {
    return chromium.launch({ headless: true, channel: "chrome" });
  }
}

async function runLocaleTest(browser, locale, expectations) {
  const label = `multilingual-${locale}`;
  console.log(`[${label}] start`);

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const errors = [];

  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  // Mock MVP API — return mayor action for any question
  await page.route("**/api/mvp/ask", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        ok: true,
        answer: "Answer placeholder.",
        action: "mayor_message_assist",
        confidence: 1,
        failure_code: "",
      }),
    });
  });

  await page.goto(`${BASE_ORIGIN}/mvp/?lang=${locale}`, {
    waitUntil: "networkidle",
    timeout: 20000,
  });

  // 1. Shell title is localized
  const shellTitle = page.locator(".chat-shell__title");
  await shellTitle.waitFor({ state: "visible", timeout: 5000 });
  const titleText = await shellTitle.innerText();
  assert.strictEqual(
    titleText,
    expectations.shellTitle,
    `[${label}] shell title matches`,
  );
  console.log(`[${label}] shell title verified`);

  // 2. Mayor chip text is localized
  const mayorChip = page.locator(".chat-chip--mayor-primary").first();
  await mayorChip.waitFor({ state: "visible", timeout: 5000 });
  const chipText = await mayorChip.innerText();
  assert.ok(
    chipText.includes(expectations.chipPrefix),
    `[${label}] chip contains "${expectations.chipPrefix}": ${chipText}`,
  );
  console.log(`[${label}] chip text verified`);

  // 3. Click chip → confirm-run text is localized
  await mayorChip.click();

  const confirmBtn = page.getByRole("button", {
    name: expectations.confirmText,
    exact: true,
  });
  await confirmBtn.waitFor({ state: "visible", timeout: 5000 });
  console.log(`[${label}] confirm button verified`);

  // 4. No browser errors during shell localization
  assert.deepStrictEqual(
    errors,
    [],
    `[${label}] no console/page errors: ${errors.join(" | ")}`,
  );
  console.log(`[${label}] no errors`);

  await context.close();
  console.log(`[${label}] PASS`);
}

async function main() {
  const browser = await launchBrowser();
  try {
    for (const [locale, expectations] of Object.entries(LOCALE_ASSERTIONS)) {
      await runLocaleTest(browser, locale, expectations);
    }
  } finally {
    await browser.close();
  }
  console.log("Multilingual MVP E2E: all 5 locales PASSED.");
}

main().catch((error) => {
  console.error("Multilingual MVP E2E FAILED:");
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
