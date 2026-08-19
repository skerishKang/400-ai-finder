// tools/resident-evidence/scenarios/bukgu-litter.mjs
//
// Buk-gu Litter scenario spec for Resident Journey Evidence Harness V1.
// Question: "쓰레기 무단투기 신고할래 (AI 도움)"
// Action: litter_ai_assist
// Journey: complaint-ai-assist (has CHOICE step: 직접 작성 / AI 도움 받기)
//
// This scenario drives the REAL production choreography through:
//   ENTRY → CONFIRMATION → CHOICE → AI-help continuation → DRAFT_POPULATED
//   → PRE_SUBMIT_CONVERSATION → PRE_SUBMIT_GUIDANCE

import { pollUntil } from "../src/orchestrator.mjs";

export const litterScenario = Object.freeze({
  id: "BUKGU_LITTER",
  product: "bukgu",
  question: "쓰레기 무단투기 신고할래 (AI 도움)",
  action: "litter_ai_assist",
  journeyId: "litter_ai_assist",
  answer: "쓰레기 무단투기 신고를 도와드립니다.",
  viewport: { width: 390, height: 844 },
  captureStates: [
    "ENTRY",
    "CONFIRMATION",
    "CHOICE",
    "PRE_SUBMIT_CONVERSATION",
    "PRE_SUBMIT_GUIDANCE",
  ],

  steps: [
    // ── Step 1: Type the question and submit ──
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

    // ── Step 2: Click "예, 안내해 주세요" to start choreography ──
    async function confirmRun(page) {
      await page.evaluate(() => {
        const btns = Array.from(document.querySelectorAll("button"));
        const yesBtn = btns.find((b) => b.textContent.includes("예, 안내해 주세요"));
        if (yesBtn) yesBtn.click();
      });
      // Wait for choreography to reach waiting_choice (litter has a choice step)
      await pollUntil(
        page,
        async () => (await page.getAttribute("body", "data-choreography-state")) === "waiting_choice",
        { label: "litter waiting_choice", timeoutMs: 15000 },
      );
    },

    // ── Step 3: For CHOICE capture — switch to conversation surface ──
    // After confirm-run, the runtime switches to guidance on mobile.
    // The choice buttons are in #chat-thread (conversation surface).
    // The CHOICE capture step runs BETWEEN step 2 and step 4.
    // (The orchestrator evaluates the capture state spec after all steps,
    //  so this step ensures the surface is correct for the CHOICE state.)
    async function switchToConversationForChoice(page) {
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

    // ── Step 4: Click "AI 도움 받기" to continue past choice ──
    async function chooseAiHelp(page) {
      await page.evaluate(() => {
        const btns = Array.from(document.querySelectorAll(".chat-decision__button"));
        const aiBtn = btns.find((b) => b.textContent.includes("AI 도움 받기"));
        if (aiBtn) aiBtn.click();
      });
      // Wait for draft population
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
      // Wait for waiting_confirmation
      await pollUntil(
        page,
        async () => (await page.getAttribute("body", "data-choreography-state")) === "waiting_confirmation",
        { label: "litter waiting_confirmation", timeoutMs: 15000 },
      );
    },

    // ── Step 5: Switch to conversation for PRE_SUBMIT_CONVERSATION capture ──
    async function switchToConversationForPreSubmit(page) {
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
  ],
});
