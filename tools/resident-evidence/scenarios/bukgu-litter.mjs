// tools/resident-evidence/scenarios/bukgu-litter.mjs
//
// Buk-gu Litter scenario spec — checkpoint architecture.
// Captures each semantic state AT THE ACTUAL STATE TIME.
//
// Checkpoint timeline:
//   beforeStep 0 → ENTRY
//   afterStep 0  → CONFIRMATION (question submitted, confirm-run visible)
//   afterStep 1  → CHOICE (confirm-run clicked, waiting_choice, conversation surface)
//   afterStep 2  → PRE_SUBMIT_CONVERSATION (AI-help clicked, draft populated, conversation surface)
//   afterStep 3  → PRE_SUBMIT_GUIDANCE (switched to guidance surface)
//   afterStep 3  → FINAL_STABLE_STATE (NOT_SEPARATELY_OBSERVABLE — aliases PRE_SUBMIT_CONVERSATION)

import { pollUntil } from "../src/orchestrator.mjs";

export const litterScenario = Object.freeze({
  id: "BUKGU_LITTER",
  product: "bukgu",
  question: "쓰레기 무단투기 신고할래 (AI 도움)",
  action: "litter_ai_assist",
  journeyId: "litter_ai_assist",
  answer: "쓰레기 무단투기 신고를 도와드립니다.",
  viewport: { width: 390, height: 844 },

  checkpoints: [
    { state: "ENTRY", beforeStep: 0, expected: "ACCEPTED" },
    { state: "CONFIRMATION", afterStep: 0, expected: "ACCEPTED" },
    { state: "CHOICE", afterStep: 1, expected: "ACCEPTED" },
    { state: "PRE_SUBMIT_CONVERSATION", afterStep: 2, expected: "ACCEPTED" },
    { state: "PRE_SUBMIT_GUIDANCE", afterStep: 3, expected: "ACCEPTED" },
    { state: "FINAL_STABLE_STATE", afterStep: 3, expected: "NOT_SEPARATELY_OBSERVABLE" },
  ],

  steps: [
    // ── Step 0: Type the question and submit ──
    async function typeQuestion(page) {
      await page.fill("#chat-composer-input", "쓰레기 무단투기 신고할래 (AI 도움)");
      await page.click("#chat-composer-send");
      await pollUntil(
        page,
        async () => (await page.getAttribute("body", "data-first-use-state")) === "split",
        { label: "litter split state", timeoutMs: 12000 },
      );
      await pollUntil(
        page,
        async () => !!(await page.locator('[data-msg-type="confirm-run"]').count()),
        { label: "litter confirm-run visible", timeoutMs: 8000 },
      );
    },

    // ── Step 1: Click "예, 안내해 주세요", wait for waiting_choice ──
    async function confirmRun(page) {
      await page.evaluate(() => {
        const btns = Array.from(document.querySelectorAll("button"));
        const yesBtn = btns.find((b) => b.textContent.includes("예, 안내해 주세요"));
        if (yesBtn) yesBtn.click();
      });
      await pollUntil(
        page,
        async () => (await page.getAttribute("body", "data-choreography-state")) === "waiting_choice",
        { label: "litter waiting_choice", timeoutMs: 15000 },
      );
      // Switch to conversation so CHOICE buttons are visible
      const surface = await page.getAttribute("body", "data-mobile-surface");
      if (surface === "guidance") {
        await page.evaluate(() => {
          const tab = document.getElementById("tab-conversation");
          if (tab) tab.click();
        });
        await pollUntil(
          page,
          async () => (await page.getAttribute("body", "data-mobile-surface")) === "conversation",
          { label: "litter switch to conversation for choice", timeoutMs: 5000 },
        );
      }
    },

    // ── Step 2: Click "AI 도움 받기", wait for draft + confirmation prompt ──
    async function chooseAiHelp(page) {
      await page.evaluate(() => {
        const btns = Array.from(document.querySelectorAll(".chat-decision__button"));
        const aiBtn = btns.find((b) => b.textContent.includes("AI 도움 받기"));
        if (aiBtn) aiBtn.click();
      });
      await pollUntil(
        page,
        async () => {
          const el = await page.locator("#board-write-title").first();
          if (!(await el.count())) return false;
          const val = await el.inputValue();
          return val && val.length > 0;
        },
        { label: "litter title populated", timeoutMs: 25000 },
      );
      await pollUntil(
        page,
        async () => {
          const el = await page.locator("#board-write-content").first();
          if (!(await el.count())) return false;
          const val = await el.inputValue();
          return val && val.length > 0;
        },
        { label: "litter content populated", timeoutMs: 25000 },
      );
      await pollUntil(
        page,
        async () => (await page.getAttribute("body", "data-choreography-state")) === "waiting_confirmation",
        { label: "litter waiting_confirmation", timeoutMs: 15000 },
      );
      // Wait for confirmation prompt text
      await pollUntil(
        page,
        async () => {
          const thread = await page.locator("#chat-thread").first();
          if (!(await thread.count())) return false;
          const text = await thread.textContent();
          return text !== null && text.includes("검토했고, 제출하기");
        },
        { label: "litter confirmation prompt", timeoutMs: 15000 },
      );
      // Ensure conversation surface for PRE_SUBMIT_CONVERSATION
      const surface = await page.getAttribute("body", "data-mobile-surface");
      if (surface === "guidance") {
        await page.evaluate(() => {
          const tab = document.getElementById("tab-conversation");
          if (tab) tab.click();
        });
        await pollUntil(
          page,
          async () => (await page.getAttribute("body", "data-mobile-surface")) === "conversation",
          { label: "litter switch to conversation for pre-submit", timeoutMs: 5000 },
        );
      }
    },

    // ── Step 3: Switch to guidance for PRE_SUBMIT_GUIDANCE ──
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
          { label: "litter switch to guidance", timeoutMs: 5000 },
        );
      }
    },
  ],
});
