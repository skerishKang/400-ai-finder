// tools/resident-evidence/src/runtime-observer.mjs
//
// Runtime state snapshot collector — reads actual DOM/runtime truth from the page.
// Does NOT mutate page state. Read-only.

/**
 * Collect a runtime state snapshot from the page.
 * @param {import('playwright').Page} page
 * @returns {Promise<Object>} structured runtime snapshot
 */
export async function collectSnapshot(page) {
  return await page.evaluate(() => {
    const b = document.body;
    const canvas = document.getElementById("demo-canvas");
    const thread = document.getElementById("chat-thread");
    const titleEl = document.querySelector("#board-write-title");
    const contentEl = document.querySelector("#board-write-content");
    const submitBtn = document.getElementById("btn-board-submit");

    // Helper: check element visibility
    function visible(sel) {
      const el = document.querySelector(sel);
      if (!el) return false;
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    }

    // Helper: get element bounding box
    function bbox(sel) {
      const el = document.querySelector(sel);
      if (!el) return null;
      const rect = el.getBoundingClientRect();
      return { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) };
    }

    // Decision buttons
    const decisionPrimary = document.querySelector(".chat-decision__button--primary");
    const decisionSecondary = document.querySelector(".chat-decision__button--secondary");

    // Confirm-run message
    const confirmRun = document.querySelector('[data-msg-type="confirm-run"]');

    // Mobile surface tabs
    const tabConversation = document.getElementById("tab-conversation");
    const tabGuidance = document.getElementById("tab-guidance");

    // Page text scan for forbidden patterns
    const pageText = (document.body.textContent || "").replace(/\s+/g, " ");
    const forbiddenPatterns = ["접수되었습니다", "접수번호", "민원 접수가 완료", "제출이 완료", "처리결과", "등록되었습니다"];
    const forbiddenFound = forbiddenPatterns.filter((p) => pageText.includes(p));

    return {
      url: window.location.href,
      attributes: {
        firstUseState: b.getAttribute("data-first-use-state"),
        journeyState: b.getAttribute("data-journey-state"),
        choreographyState: b.getAttribute("data-choreography-state"),
        draftStage: b.getAttribute("data-draft-stage"),
        mobileSurface: b.getAttribute("data-mobile-surface"),
        questId: b.getAttribute("data-quest-id"),
        questStopCondition: b.getAttribute("data-quest-stop-condition"),
        questSourceMode: b.getAttribute("data-quest-source-mode"),
      },
      form: {
        titleExists: titleEl !== null,
        titleValue: titleEl ? titleEl.value : null,
        titleVisible: titleEl ? visible("#board-write-title") : false,
        titleBbox: titleEl ? bbox("#board-write-title") : null,
        contentExists: contentEl !== null,
        contentValue: contentEl ? contentEl.value : null,
        contentVisible: contentEl ? visible("#board-write-content") : false,
        contentBbox: contentEl ? bbox("#board-write-content") : null,
        submitBtnExists: submitBtn !== null,
        submitBtnDisabled: submitBtn ? submitBtn.disabled : null,
      },
      controls: {
        confirmRunExists: confirmRun !== null,
        confirmRunVisible: confirmRun ? visible('[data-msg-type="confirm-run"]') : false,
        decisionPrimaryExists: decisionPrimary !== null,
        decisionPrimaryText: decisionPrimary ? decisionPrimary.textContent.trim() : null,
        decisionPrimaryVisible: decisionPrimary ? visible(".chat-decision__button--primary") : false,
        decisionSecondaryExists: decisionSecondary !== null,
        decisionSecondaryText: decisionSecondary ? decisionSecondary.textContent.trim() : null,
        decisionSecondaryVisible: decisionSecondary ? visible(".chat-decision__button--secondary") : false,
        decisionMessageExists: document.querySelector(".chat-msg--decision") !== null,
        chatThreadVisible: thread ? visible("#chat-thread") : false,
        chatThreadBbox: thread ? bbox("#chat-thread") : null,
        demoCanvasVisible: canvas ? visible("#demo-canvas") : false,
      },
      mobile: {
        tabConversationPressed: tabConversation ? tabConversation.getAttribute("aria-pressed") : null,
        tabGuidancePressed: tabGuidance ? tabGuidance.getAttribute("aria-pressed") : null,
        switchVisible: (() => {
          const sw = document.getElementById("mobile-surface-switch");
          if (!sw) return false;
          return sw.getBoundingClientRect().width > 0 && !sw.hasAttribute("hidden");
        })(),
      },
      forbidden: {
        successPatternsFound: forbiddenFound,
        submitBtnNotDisabled: submitBtn ? !submitBtn.disabled : false,
      },
    };
  });
}

/**
 * Extract a compact signature for stability comparison.
 * This is a subset of the snapshot used to detect state changes.
 * @param {import('playwright').Page} page
 * @returns {Promise<Object>} compact signature object
 */
export async function collectStabilitySignature(page) {
  return await page.evaluate(() => {
    const b = document.body;
    const titleEl = document.querySelector("#board-write-title");
    const contentEl = document.querySelector("#board-write-content");
    const decisionPrimary = document.querySelector(".chat-decision__button--primary");

    function bboxStr(sel) {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return `${Math.round(r.x)},${Math.round(r.y)},${Math.round(r.width)},${Math.round(r.height)}`;
    }

    return {
      choreo: b.getAttribute("data-choreography-state"),
      journey: b.getAttribute("data-journey-state"),
      firstUse: b.getAttribute("data-first-use-state"),
      mobileSurface: b.getAttribute("data-mobile-surface"),
      questId: b.getAttribute("data-quest-id"),
      titleValue: titleEl ? titleEl.value : null,
      contentValue: contentEl ? contentEl.value : null,
      titleVisible: titleEl ? titleEl.getBoundingClientRect().width > 0 : false,
      contentVisible: contentEl ? contentEl.getBoundingClientRect().width > 0 : false,
      decisionPrimaryText: decisionPrimary ? decisionPrimary.textContent.trim() : null,
      decisionPrimaryVisible: decisionPrimary ? decisionPrimary.getBoundingClientRect().width > 0 : false,
      titleBbox: bboxStr("#board-write-title"),
      contentBbox: bboxStr("#board-write-content"),
      chatThreadVisible: (() => {
        const el = document.getElementById("chat-thread");
        return el ? el.getBoundingClientRect().width > 0 : false;
      })(),
    };
  });
}
