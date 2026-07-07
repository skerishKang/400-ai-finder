/*
 * citizen-first-use-shell.js
 * Local deterministic controller for the first chat-only entry transition.
 *
 * Guarantees:
 * - no fetch/XHR/WebSocket/EventSource/sendBeacon;
 * - no browser persistence or cookie access;
 * - no provider, runner, live-site, or external-origin behavior;
 * - no clone route/choreography actions (reserved for #920).
 */

(function () {
  "use strict";

  var STATE_ENTRY = "entry";
  var STATE_TRANSITIONING = "transitioning";
  var STATE_SPLIT = "split";
  var TRANSITION_DURATION_MS = 360;
  var SUPPORTED_QUESTIONS = {
    "불법 주정차 신고는 어디서 하나요?": true
  };
  var SPLIT_FOLLOW_UP_MESSAGE =
    "현재 로컬 안내 화면을 준비했습니다. 메뉴 이동과 세부 안내는 다음 단계에서 순서대로 제공됩니다. 새 질문을 시작하려면 '새 대화'를 선택해 주세요.";

  var body = document.body;
  var canvas = document.getElementById("demo-canvas");
  var chatShell = document.getElementById("chat-shell");
  var chatThread = document.getElementById("chat-thread");
  var chatForm = document.getElementById("chat-composer-form");
  var chatInput = document.getElementById("chat-composer-input");
  var chatSend = document.getElementById("chat-composer-send");
  var resetButton = document.getElementById("chat-reset");
  var splitTimer = null;
  var currentState = STATE_ENTRY;

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
      return;
    }

    if (nextState === STATE_TRANSITIONING) {
      setCanvasAvailability(false);
      setComposerDisabled(true);
      if (resetButton) {
        resetButton.hidden = true;
      }
      return;
    }

    setCanvasAvailability(true);
    setComposerDisabled(false);
    if (resetButton) {
      resetButton.hidden = false;
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
      "안녕하세요. 북구청 정보 안내 로컬 시연입니다. 지원되는 질문을 입력하면 안내 화면을 함께 보여드립니다."
    );
  }

  function completeSplit() {
    splitTimer = null;
    setState(STATE_SPLIT);
    appendChatMessage(
      "ai",
      "질문을 확인했습니다. 왼쪽의 로컬 안내 화면을 준비했습니다. 다음 단계의 메뉴 안내는 이 데모에서 순서대로 보여드릴 예정입니다."
    );
    if (chatInput) {
      chatInput.focus();
    }
  }

  function beginSupportedTransition(question) {
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
      "현재 이 로컬 시연에서 준비된 안내 질문이 아닙니다. 지원 범위의 질문으로 다시 입력해 주세요."
    );
    chatInput.focus();
  }

  function resetToEntry() {
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

  if (isLegacyJourneyLoad()) {
    setState(STATE_SPLIT);
  } else {
    setState(STATE_ENTRY);
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
