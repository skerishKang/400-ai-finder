/*
 * citizen-first-use-shell.js
 * Local deterministic controller for the first chat-only entry transition.
 *
 * Guarantees:
 * - no fetch/XHR/WebSocket/EventSource/sendBeacon;
 * - no browser persistence or cookie access;
 * - no provider, runner, live-site, or external-origin behavior;
 * - choreography delegation to CitizenFirstChoreography (no direct clone actions).
 */

(function () {
  "use strict";

  var STATE_ENTRY = "entry";
  var STATE_TRANSITIONING = "transitioning";
  var STATE_SPLIT = "split";
  var TRANSITION_DURATION_MS = 360;
  var DEFAULT_SUPPORTED_ACTION = "illegal_parking";
  var SUPPORTED_QUESTIONS = {
    "불법 주정차 신고는 어디서 하나요?": true,
    "공동주택 관련 문의는 어느 부서에 해야 하나요?": true
  };
  var SPLIT_FOLLOW_UP_MESSAGE =
    "북구청 안내 화면을 왼쪽에 열어두었습니다. 메뉴 이동과 세부 안내를 이어서 보여드리겠습니다. 새 질문을 시작하려면 '새 대화'를 선택해 주세요.";

  var body = document.body;
  var canvas = document.getElementById("demo-canvas");
  var chatShell = document.getElementById("chat-shell");
  var chatThread = document.getElementById("chat-thread");
  var chatForm = document.getElementById("chat-composer-form");
  var chatInput = document.getElementById("chat-composer-input");
  var chatSend = document.getElementById("chat-composer-send");
  var resetButton = document.getElementById("chat-reset");
  var chipsContainer = document.getElementById("chat-chips");
  var splitTimer = null;
  var lastSplitQuestion = null;
  var currentState = STATE_ENTRY;

  // ── MVP mode (#925 / #927) ──────────────────────────────────────
  // Enabled only with ?mvp=1. In MVP mode the shell calls the model-backed
  // /api/mvp/ask endpoint (via citizen-mvp-bridge.js) and uses the returned
  // action to drive the EXISTING local choreography. The default static flow
  // below is completely unchanged when ?mvp=1 is absent, and this file performs
  // no fetch itself (the bridge file does, and is loaded only in MVP mode).
  var _mvpRequestToken = 0;

  function isMvpMode() {
    if (!window.location || !window.location.search) return false;
    try {
      return new URLSearchParams(window.location.search).get("mvp") === "1";
    } catch (_) {
      return false;
    }
  }

  function normalizeMvpAction(result) {
    if (!result || result.ok !== true) return "none";
    var a = result.action;
    if (a === "illegal_parking" || a === "housing_department" || a === "none") {
      return a;
    }
    return "none";
  }

  function resolveMvpActionForQuestion(question, result, hasUsableMvpResult) {
    if (!hasUsableMvpResult) return "none";
    var action = normalizeMvpAction(result);
    if (action !== "none") return action;
    if (isSupportedQuestion(question)) return DEFAULT_SUPPORTED_ACTION;
    return "none";
  }

  function _withMvpBridge(onReady) {
    if (window.CitizenMvpBridge && typeof window.CitizenMvpBridge.ask === "function") {
      onReady(window.CitizenMvpBridge);
      return;
    }
    var existing = document.querySelector('script[data-mvp-bridge="1"]');
    if (!existing) {
      var s = document.createElement("script");
      s.src = "/static/citizen-mvp-bridge.js";
      s.setAttribute("data-mvp-bridge", "1");
      s.onload = function () { onReady(window.CitizenMvpBridge); };
      s.onerror = function () { onReady(null); };
      document.head.appendChild(s);
    } else {
      var tries = 0;
      var iv = window.setInterval(function () {
        tries++;
        if (window.CitizenMvpBridge && typeof window.CitizenMvpBridge.ask === "function") {
          window.clearInterval(iv);
          onReady(window.CitizenMvpBridge);
        } else if (tries > 20) {
          window.clearInterval(iv);
          onReady(null);
        }
      }, 50);
    }
  }

  function normalizeQuestion(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function isSupportedQuestion(value) {
    return Boolean(SUPPORTED_QUESTIONS[normalizeQuestion(value)]);
  }

  function prefersReducedMotion() {
    return Boolean(
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function isLegacyJourneyLoad() {
    if (!window.location || !window.location.search) {
      return false;
    }
    var params = new URLSearchParams(window.location.search);
    return params.getAll("journey").length === 1;
  }

  function setCanvasAvailability(isAvailable) {
    if (!canvas) {
      return;
    }
    if (isAvailable) {
      canvas.removeAttribute("inert");
      canvas.setAttribute("aria-hidden", "false");
    } else {
      canvas.setAttribute("inert", "");
      canvas.setAttribute("aria-hidden", "true");
    }
  }

  function setComposerDisabled(isDisabled) {
    if (chatInput) {
      chatInput.disabled = isDisabled;
    }
    if (chatSend) {
      chatSend.disabled = isDisabled;
    }
    if (chatShell) {
      chatShell.setAttribute("data-chat-busy", isDisabled ? "true" : "false");
      chatShell.setAttribute("aria-busy", isDisabled ? "true" : "false");
    }
  }

  function setState(nextState) {
    currentState = nextState;
    body.setAttribute("data-first-use-state", nextState);

    if (nextState === STATE_ENTRY) {
      setCanvasAvailability(false);
      setComposerDisabled(false);
      if (resetButton) {
        resetButton.hidden = true;
      }
      if (chipsContainer) {
        chipsContainer.hidden = false;
      }
      return;
    }

    if (nextState === STATE_TRANSITIONING) {
      setCanvasAvailability(false);
      setComposerDisabled(true);
      if (resetButton) {
        resetButton.hidden = true;
      }
      if (chipsContainer) {
        chipsContainer.hidden = true;
      }
      return;
    }

    setCanvasAvailability(true);
    setComposerDisabled(false);
    if (resetButton) {
      resetButton.hidden = false;
    }
    if (chipsContainer) {
      chipsContainer.hidden = true;
    }
  }

  function scrollChatToLatest() {
    if (chatThread) {
      chatThread.scrollTop = chatThread.scrollHeight;
    }
  }

  function appendChatMessage(role, text) {
    if (!chatThread) {
      return;
    }

    var message = document.createElement("div");
    message.className = "chat-msg chat-msg--" + role;

    if (role === "ai") {
      var avatar = document.createElement("div");
      avatar.className = "chat-avatar";
      avatar.setAttribute("aria-label", "AI");
      avatar.textContent = "A";
      message.appendChild(avatar);
    }

    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--" + role;
    bubble.textContent = text;
    message.appendChild(bubble);
    chatThread.appendChild(message);
    scrollChatToLatest();
  }

  function renderEntryConversation() {
    if (!chatThread) {
      return;
    }
    chatThread.innerHTML = "";
    appendChatMessage(
      "ai",
      "안녕하세요. 북구청 민원 안내 AI입니다. 궁금한 민원을 물어보시면 관련 화면을 함께 열어 경로를 안내해 드립니다."
    );
  }

  function completeSplit() {
    splitTimer = null;
    setState(STATE_SPLIT);
    appendChatMessage(
      "ai",
      "질문을 확인했습니다. 왼쪽에 북구청 안내 화면을 열었습니다. 이제 메뉴 이동과 확인 위치를 순서대로 보여드리겠습니다."
    );
    if (window.CitizenFirstChoreography && lastSplitQuestion) {
      window.CitizenFirstChoreography.start(lastSplitQuestion);
    }
    lastSplitQuestion = null;
    if (chatInput) {
      chatInput.focus();
    }
  }

  function beginSupportedTransition(question) {
    lastSplitQuestion = question;
    appendChatMessage("user", question);
    if (chatInput) {
      chatInput.value = "";
    }

    setState(STATE_TRANSITIONING);

    if (prefersReducedMotion()) {
      completeSplit();
      return;
    }

    splitTimer = window.setTimeout(completeSplit, TRANSITION_DURATION_MS);
  }

  function handleSubmission(event) {
    if (event) {
      event.preventDefault();
    }

    if (currentState === STATE_TRANSITIONING || !chatInput) {
      return;
    }

    var question = normalizeQuestion(chatInput.value);
    if (!question) {
      chatInput.focus();
      return;
    }

    if (isMvpMode()) {
      handleMvpSubmission(question);
      return;
    }

    if (currentState === STATE_SPLIT) {
      appendChatMessage("user", question);
      chatInput.value = "";
      appendChatMessage("ai", SPLIT_FOLLOW_UP_MESSAGE);
      chatInput.focus();
      return;
    }

    if (isSupportedQuestion(question)) {
      beginSupportedTransition(question);
      return;
    }

    appendChatMessage("user", question);
    chatInput.value = "";
    appendChatMessage(
      "ai",
      "현재 첫 화면에서는 불법 주정차 신고 경로 안내를 준비했습니다. 예시 질문으로 다시 입력해 주세요."
    );
    chatInput.focus();
  }

  // ── MVP submission (#925 / #927) ───────────────────────────────

  function handleMvpSubmission(question) {
    // 1. echo user message
    appendChatMessage("user", question);
    if (chatInput) chatInput.value = "";
    // 2. lock composer against duplicate submission
    setComposerDisabled(true);

    var token = ++_mvpRequestToken;

    _withMvpBridge(function (bridge) {
      if (token !== _mvpRequestToken) return; // superseded by a newer submit/reset
      if (!bridge || typeof bridge.ask !== "function") {
        setComposerDisabled(false);
        appendChatMessage("ai", "현재 AI 안내를 연결하지 못했습니다.");
        return;
      }
      bridge.ask(question).then(function (result) {
        if (token !== _mvpRequestToken) return; // late/aborted response ignored
        setComposerDisabled(false);
        // 5. assistant bubble MUST show the server's model answer, but only
        // for an explicit success. Any other result (ok:false, missing,
        // malformed, rejected, or ok:true with a blank answer) fails closed to
        // the generic Korean message so untrusted diagnostic/answer text never
        // reaches the citizen chat DOM.
        var isExplicitSuccess = result && result.ok === true;
        var normalizedAnswer = (
          isExplicitSuccess &&
          typeof result.answer === "string"
        )
          ? result.answer.trim()
          : "";

        // A non-empty answer is the only signal that the result is usable. A
        // blank (or missing/non-string) answer fails closed: no answer is
        // rendered and the action is degraded to "none" so no split or
        // choreography can start from an untrusted/blank success.
        var hasUsableMvpResult = Boolean(normalizedAnswer);

        var answer = hasUsableMvpResult
          ? normalizedAnswer
          : "현재 AI 안내를 연결하지 못했습니다.";
        appendChatMessage("ai", answer);
        // 4. inspect action; only approved local actions move the clone. If a
        // usable MVP answer misses the action for the supported first question,
        // fall back to the existing deterministic local journey instead of
        // leaving the citizen-facing MVP stuck in chat-only mode.
        var action = resolveMvpActionForQuestion(question, result, hasUsableMvpResult);
        if (action === "illegal_parking") {
          beginMvpSplitThenChoreography(question, "illegal_parking");
        } else if (action === "housing_department") {
          beginMvpSplitThenChoreography(question, "housing_department");
        } else if (action === "none") {
          // Keep the entry chat; do not move the clone or start a choreography.
        }
        // Any other value: treated as none (no split, no clone move).
      }).catch(function () {
        if (token !== _mvpRequestToken) return;
        setComposerDisabled(false);
        appendChatMessage("ai", "현재 AI 안내를 연결하지 못했습니다.");
      });
    });
  }

  function beginMvpSplitThenChoreography(question, action) {
    lastSplitQuestion = question;
    setState(STATE_TRANSITIONING);
    if (prefersReducedMotion()) {
      completeMvpSplit(action);
      return;
    }
    splitTimer = window.setTimeout(function () {
      splitTimer = null;
      completeMvpSplit(action);
    }, TRANSITION_DURATION_MS);
  }

  function completeMvpSplit(action) {
    splitTimer = null;
    setState(STATE_SPLIT);
    appendChatMessage(
      "ai",
      "질문을 확인했습니다. 왼쪽에 북구청 안내 화면을 열었습니다."
    );
    // 6. run the existing local choreography for the resolved action
    if (window.CitizenFirstChoreography && action) {
      window.CitizenFirstChoreography.start(action);
    }
    if (chatInput) chatInput.focus();
  }

  function resetToEntry() {
    // Invalidate any in-flight MVP response so a late answer cannot re-open the
    // clone or restart an action after the user reset.
    _mvpRequestToken++;
    if (window.CitizenMvpBridge && typeof window.CitizenMvpBridge.cancel === "function") {
      window.CitizenMvpBridge.cancel();
    }
    if (window.CitizenFirstChoreography) {
      window.CitizenFirstChoreography.cancel();
    }
    lastSplitQuestion = null;
    if (splitTimer !== null) {
      window.clearTimeout(splitTimer);
      splitTimer = null;
    }

    body.classList.add("first-use-shell--no-motion");
    setState(STATE_ENTRY);
    renderEntryConversation();
    if (chatInput) {
      chatInput.value = "";
      chatInput.focus();
    }
    window.requestAnimationFrame(function () {
      body.classList.remove("first-use-shell--no-motion");
    });
  }

  if (chatForm) {
    chatForm.addEventListener("submit", handleSubmission);
  }

  if (resetButton) {
    resetButton.addEventListener("click", resetToEntry);
  }

  // #965: chip click → submit question
  if (chipsContainer) {
    chipsContainer.addEventListener("click", function (e) {
      var chip = e.target.closest("[data-chip-question]");
      if (!chip) return;
      var question = chip.getAttribute("data-chip-question");
      if (!question) return;
      if (chatInput) {
        chatInput.value = question;
      }
      // Trigger submission
      if (chatForm) {
        chatForm.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });
  }

  if (isLegacyJourneyLoad()) {
    setState(STATE_SPLIT);
  } else {
    setState(STATE_ENTRY);
    renderEntryConversation();
  }

  window.CitizenFirstUseShell = Object.freeze({
    getState: function () { return currentState; },
    isSupportedQuestion: isSupportedQuestion,
    reset: resetToEntry,
    states: Object.freeze({
      entry: STATE_ENTRY,
      transitioning: STATE_TRANSITIONING,
      split: STATE_SPLIT
    })
  });
})();
