/*
 * citizen-first-choreography.js
 * Deterministic local journey choreography for the first-use split shell.
 *
 * Drives the demo-canvas through route transitions and target highlights
 * using only the public CitizenActionDemoCanvas API.
 *
 * Guarantees:
 * - no fetch/XHR/WebSocket/EventSource/sendBeacon;
 * - no browser persistence or cookie access;
 * - no provider, runner, live-site, or external-origin behavior;
 * - no hidden copilot-rail, executor trace/status, or URL API dependency;
 * - no screenshot layer, fake cursor, or external asset.
 */

(function () {
  "use strict";

  var STATE_IDLE = "idle";
  var STATE_RUNNING = "running";
  var STATE_DONE = "done";
  var STATE_CANCELLED = "cancelled";

  var HIGHLIGHT_CLASS = "executor-highlight";

  var _body = document.body;
  var _chatThread = document.getElementById("chat-thread");
  var _state = STATE_IDLE;
  var _timer = null;
  var _currentStep = -1;
  var _currentJourneyId = null;
  var _steps = [];
  var _highlightedEls = [];

  // ═══════════════════════════════════════════════════════════════════
  // Journey map — typed deterministic step lists keyed by question
  // or journey ID. Each step:
  //   message   — chat message to display (required)
  //   routeId   — call navigateToRoute(routeId) (optional)
  //   targetId  — call getTargetElement(targetId) + highlight (optional)
  //   delayMs   — pause before next step; omitted/0 = terminal
  // ═══════════════════════════════════════════════════════════════════
  var JOURNEY_MAP = Object.freeze({
    "불법 주정차 신고는 어디서 하나요?": Object.freeze({
      id: "complaint-illegal-parking",
      description: "불법 주정차 신고 민원 신청 경로 안내",
      steps: Object.freeze([
        Object.freeze({ message: "민원 신청 경로를 안내해 드리겠습니다.", delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200 }),
        Object.freeze({ message: "민원 안내를 위해 유형 선택 버튼을 안내합니다.", targetId: "nav-complaint-category", delayMs: 2000 }),
        Object.freeze({ message: "민원 유형 선택 페이지로 이동합니다.", routeId: "complaint-category", delayMs: 1200 }),
        Object.freeze({ message: "안내가 완료되었습니다. 새로운 문의는 '새 대화'를 선택해 주세요." }),
      ]),
    }),
  });

  // ═══════════════════════════════════════════════════════════════════
  // Internal helpers
  // ═══════════════════════════════════════════════════════════════════

  function _appendChatMessage(role, text) {
    if (!_chatThread) return;
    var messageEl = document.createElement("div");
    messageEl.className = "chat-msg chat-msg--" + role;
    if (role === "ai") {
      var avatar = document.createElement("div");
      avatar.className = "chat-avatar";
      avatar.setAttribute("aria-label", "AI");
      avatar.textContent = "A";
      messageEl.appendChild(avatar);
    }
    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--" + role;
    bubble.textContent = text;
    messageEl.appendChild(bubble);
    _chatThread.appendChild(messageEl);
    _chatThread.scrollTop = _chatThread.scrollHeight;
  }

  function _clearHighlights() {
    for (var i = 0; i < _highlightedEls.length; i++) {
      if (_highlightedEls[i]) {
        _highlightedEls[i].classList.remove(HIGHLIGHT_CLASS);
      }
    }
    _highlightedEls = [];
  }

  function _clearTimer() {
    if (_timer !== null) {
      window.clearTimeout(_timer);
      _timer = null;
    }
  }

  function _setState(nextState) {
    _state = nextState;
    _body.setAttribute("data-choreography-state", nextState);
  }

  function _executeStep(index) {
    if (_state !== STATE_RUNNING) return;
    if (index >= _steps.length) {
      _setState(STATE_DONE);
      return;
    }

    _currentStep = index;
    var step = _steps[index];

    // Clear highlights from previous step before executing this one
    _clearHighlights();

    // Show chat message
    _appendChatMessage("ai", step.message);

    // Execute DOM action
    if (step.routeId) {
      var canvas = window.CitizenActionDemoCanvas;
      if (canvas && canvas.navigateToRoute) {
        canvas.navigateToRoute(step.routeId);
      }
    } else if (step.targetId) {
      var canvas = window.CitizenActionDemoCanvas;
      if (canvas && canvas.getTargetElement) {
        var el = canvas.getTargetElement(step.targetId);
        if (el) {
          el.classList.add(HIGHLIGHT_CLASS);
          try { el.scrollIntoView({ behavior: "smooth", block: "center" }); } catch (_) { /* noop */ }
          _highlightedEls.push(el);
        }
      }
    }

    // Schedule next step or terminate
    if (typeof step.delayMs === "number" && step.delayMs > 0) {
      _timer = window.setTimeout(function () {
        _timer = null;
        _executeStep(index + 1);
      }, step.delayMs);
    } else {
      // No delay → terminal step (done message)
      _setState(STATE_DONE);
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  // Public API
  // ═══════════════════════════════════════════════════════════════════

  /**
   * Start a choreography for the given journey key.
   * @param {string} journeyKey — question text or journey ID
   * @returns {boolean} true if a matching journey was found and started
   */
  function start(journeyKey) {
    if (_state === STATE_RUNNING) cancel();

    var entry = JOURNEY_MAP[journeyKey];
    if (!entry) return false;

    _currentJourneyId = entry.id;
    _steps = entry.steps;
    _currentStep = -1;
    _setState(STATE_RUNNING);
    _executeStep(0);
    return true;
  }

  /** Cancel a running choreography. Safe to call in any state. */
  function cancel() {
    if (_state === STATE_IDLE) return;
    _clearTimer();
    _clearHighlights();
    _steps = [];
    _currentStep = -1;
    _currentJourneyId = null;
    _setState(STATE_CANCELLED);
  }

  /** @returns {string} current state */
  function getState() {
    return _state;
  }

  /** @returns {string|null} current journey ID */
  function getCurrentJourneyId() {
    return _currentJourneyId;
  }

  /** @returns {boolean} true if a journey map exists for the key */
  function hasJourney(journeyKey) {
    return Boolean(JOURNEY_MAP[journeyKey]);
  }

  window.CitizenFirstChoreography = Object.freeze({
    start: start,
    cancel: cancel,
    getState: getState,
    getCurrentJourneyId: getCurrentJourneyId,
    hasJourney: hasJourney,
    states: Object.freeze({
      idle: STATE_IDLE,
      running: STATE_RUNNING,
      done: STATE_DONE,
      cancelled: STATE_CANCELLED,
    }),
  });
})();
