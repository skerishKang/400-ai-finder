// tools/resident-evidence/scenarios/bukgu-streetlight.mjs
//
// Buk-gu Streetlight scenario spec for Resident Journey Evidence Harness V1.
// Question: "가로등이 고장났어요. 신고할게요"
// Action: streetlight_report
// Journey: streetlight_report (no choice step — direct draft)
//
// This scenario drives the REAL production choreography through:
//   ENTRY → BEFORE_CLICK → CONFIRMATION → DRAFT_POPULATED → PRE_SUBMIT_CONVERSATION → PRE_SUBMIT_GUIDANCE
//
// On desktop, DRAFT_POPULATED == PRE_SUBMIT_CONVERSATION (NOT_SEPARATELY_OBSERVABLE).
// On mobile, PRE_SUBMIT_CONVERSATION and PRE_SUBMIT_GUIDANCE are separately observable
// via the mobile surface switch.

import { pollUntil } from "../src/orchestrator.mjs";

export const streetlightScenario = Object.freeze({
  id: "BUKGU_STREETLIGHT",
  product: "bukgu",
  question: "가로등이 고장났어요. 신고할게요",
  action: "streetlight_report",
  journeyId: "streetlight_report",
  answer: "가로등 고장 신고를 도와드립니다.",
  viewport: { width: 390, height: 844 },
  captureStates: [
    "ENTRY",
    "CONFIRMATION",
    "PRE_SUBMIT_CONVERSATION",
    "PRE_SUBMIT_GUIDANCE",
  ],

  // Steps to drive the REAL production choreography to each target state.
  // Each step is an async function (page) => {}.
  steps: [
    // ── Step 1: Type the question and submit ──
    async function typeQuestion(page) {
      await page.fill("#chat-composer-input", "가로등이 고장났어요. 신고할게요");
      await page.click("#chat-composer-send");
      // Wait for split state (choreography not started yet — confirm-run visible)
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

    // ── Step 2: Click "예, 안내해 주세요" to start choreography ──
    async function confirmRun(page) {
      await page.evaluate(() => {
        const btns = Array.from(document.querySelectorAll("button"));
        const yesBtn = btns.find((b) => b.textContent.includes("예, 안내해 주세요"));
        if (yesBtn) yesBtn.click();
      });
      // Wait for choreography to reach waiting_confirmation (streetlight has no choice step)
      await pollUntil(
        page,
        async () => (await page.getAttribute("body", "data-choreography-state")) === "waiting_confirmation",
        { label: "streetlight waiting_confirmation", timeoutMs: 30000 },
      );
      // Wait for title and content fields to be populated
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
    },

    // ── Step 3: Switch to conversation for PRE_SUBMIT_CONVERSATION capture ──
    async function switchToConversation(page) {
      const surface = await page.getAttribute("body", "data-mobile-surface");
      if (surface === "guidance") {
        await page.evaluate(() => {
          const tab = document.getElementById("tab-conversation");
          if (tab) tab.click();
        });
        await pollUntil(
          page,
          async () => (await page.getAttribute("body", "data-mobile-surface")) === "conversation",
          { label: "switch to conversation", timeoutMs: 5000 },
        );
      }
    },
  ],
});
