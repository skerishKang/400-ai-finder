// tools/resident-evidence/scenarios/bukgu-streetlight.mjs
//
// Buk-gu Streetlight scenario spec — checkpoint architecture.
// Captures each semantic state AT THE ACTUAL STATE TIME.
//
// Checkpoint timeline:
//   beforeStep 0 → ENTRY (page loaded, entry state)
//   afterStep 0  → CONFIRMATION (question submitted, confirm-run visible)
//   afterStep 1  → PRE_SUBMIT_CONVERSATION (choreography done, draft populated, conversation surface)
//   afterStep 2  → PRE_SUBMIT_GUIDANCE (switched to guidance surface)
//   afterStep 3  → FINAL_STABLE_STATE (NOT_SEPARATELY_OBSERVABLE — aliases PRE_SUBMIT_CONVERSATION)

import { pollUntil } from "../src/orchestrator.mjs";

export const streetlightScenario = Object.freeze({
  id: "BUKGU_STREETLIGHT",
  product: "bukgu",
  question: "가로등이 고장났어요. 신고할게요",
  action: "streetlight_report",
  journeyId: "streetlight_report",
  answer: "가로등 고장 신고를 도와드립니다.",
  viewport: { width: 390, height: 844 },

  checkpoints: [
    { state: "ENTRY", beforeStep: 0, expected: "ACCEPTED" },
    { state: "CONFIRMATION", afterStep: 0, expected: "ACCEPTED" },
    { state: "PRE_SUBMIT_CONVERSATION", afterStep: 1, expected: "ACCEPTED" },
    { state: "PRE_SUBMIT_GUIDANCE", afterStep: 2, expected: "ACCEPTED" },
    { state: "FINAL_STABLE_STATE", afterStep: 2, expected: "NOT_SEPARATELY_OBSERVABLE" },
  ],

  steps: [
    // ── Step 0: Type the question and submit ──
    async function typeQuestion(page) {
      await page.fill("#chat-composer-input", "가로등이 고장났어요. 신고할게요");
      await page.click("#chat-composer-send");
      await pollUntil(
        page,
        async () => (await page.getAttribute("body", "data-first-use-state")) === "split",
        { label: "streetlight split state", timeoutMs: 12000 },
      );
      await pollUntil(
        page,
        async () => !!(await page.locator('[data-msg-type="confirm-run"]').count()),
        { label: "streetlight confirm-run visible", timeoutMs: 8000 },
      );
    },

    // ── Step 1: Click "예, 안내해 주세요", wait for draft populated ──
    async function confirmRun(page) {
      await page.evaluate(() => {
        const btns = Array.from(document.querySelectorAll("button"));
        const yesBtn = btns.find((b) => b.textContent.includes("예, 안내해 주세요"));
        if (yesBtn) yesBtn.click();
      });
      await pollUntil(
        page,
        async () => (await page.getAttribute("body", "data-choreography-state")) === "waiting_confirmation",
        { label: "streetlight waiting_confirmation", timeoutMs: 30000 },
      );
      await pollUntil(
        page,
        async () => {
          const el = await page.locator("#board-write-title").first();
          if (!(await el.count())) return false;
          const val = await el.inputValue();
          return val && val.length > 0;
        },
        { label: "streetlight title populated", timeoutMs: 25000 },
      );
      await pollUntil(
        page,
        async () => {
          const el = await page.locator("#board-write-content").first();
          if (!(await el.count())) return false;
          const val = await el.inputValue();
          return val && val.length > 0;
        },
        { label: "streetlight content populated", timeoutMs: 25000 },
      );
      // Wait for confirmation prompt text to appear in chat thread
      await pollUntil(
        page,
        async () => {
          const thread = await page.locator("#chat-thread").first();
          if (!(await thread.count())) return false;
          const text = await thread.textContent();
          return text !== null && text.includes("검토했고, 제출하기");
        },
        { label: "streetlight confirmation prompt", timeoutMs: 15000 },
      );
      // Switch to conversation for PRE_SUBMIT_CONVERSATION capture
      const surface = await page.getAttribute("body", "data-mobile-surface");
      if (surface === "guidance") {
        await page.evaluate(() => {
          const tab = document.getElementById("tab-conversation");
          if (tab) tab.click();
        });
        await pollUntil(
          page,
          async () => (await page.getAttribute("body", "data-mobile-surface")) === "conversation",
          { label: "streetlight switch to conversation", timeoutMs: 5000 },
        );
      }
    },

    // ── Step 2: Switch to guidance for PRE_SUBMIT_GUIDANCE capture ──
    async function switchToGuidance(page) {
      const surface = await page.getAttribute("body", "data-mobile-surface");
      if (surface !== "guidance") {
        await page.evaluate(() => {
          const tab = document.getElementById("tab-guidance");
          if (tab) tab.click();
        });
        await pollUntil(
          page,
          async () => (await page.getAttribute("body", "data-mobile-surface")) === "guidance",
          { label: "streetlight switch to guidance", timeoutMs: 5000 },
        );
      }
    },
  ],
});
