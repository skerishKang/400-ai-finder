/*
 * citizen-first-choreography.js
 * Deterministic local journey choreography for the first-use split shell.
 *
 * Drives the demo-canvas through route transitions, target highlights,
 * search-focused steps, simulated typing, and search submission using
 * only the public CitizenActionDemoCanvas API and DOM access to the
 * public #demo-canvas element.
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
  var TYPING_CLASS = "executor-typing";
  var SEARCH_BUSY_CLASS = "executor-search-busy";

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
  //   message        — chat message to display (required)
  //   routeId        — call navigateToRoute(routeId) (optional)
  //   targetId       — call getTargetElement(targetId) + highlight (optional)
  //   journeyState   — push J-DEPT-01 state via URL params (optional)
  //   focusSearch    — true: focus + highlight the directory search input
  //   typeQuery      — string: set value of the directory search input
  //   submitSearch   — true: click the directory search button
  //   delayMs        — pause before next step; omitted/0 = terminal
  // ═══════════════════════════════════════════════════════════════════
  var JOURNEY_MAP = Object.freeze({
    "불법 주정차 신고는 어디서 하나요?": Object.freeze({
      id: "complaint-illegal-parking",
      description: "불법 주정차 신고 민원신고 경로 안내",
      steps: Object.freeze([
        Object.freeze({ message: "민원 신고 경로를 안내해 드리겠습니다.", delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200 }),
        Object.freeze({ message: "민원신고 메뉴에서 불법 주정차 신고 항목을 안내합니다.", targetId: "nav-complaint-category", delayMs: 2000 }),
        Object.freeze({ message: "불법 주정차 신고 화면으로 이동합니다.", routeId: "complaint-illegal-parking", delayMs: 1200 }),
        Object.freeze({ message: "불법 주정차 신고 카드를 안내합니다. 이 카드에서 위치·사진·내용을 입력해 접수합니다.", targetId: "complaint-illegal-parking-report", delayMs: 2000 }),
        Object.freeze({ message: "안내가 완료되었습니다. '불법 주정차 신고' 카드에서 온라인으로 신고를 접수할 수 있습니다. 새로운 문의는 '새 대화'를 선택해 주세요." }),
      ]),
    }),
    // #927 MVP action aliases — same deterministic local clone as above.
    "illegal_parking": Object.freeze({
      id: "complaint-illegal-parking",
      description: "불법 주정차 신고 민원신고 경로 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "민원 신고 경로를 안내해 드리겠습니다.", delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200 }),
        Object.freeze({ message: "민원신고 메뉴에서 불법 주정차 신고 항목을 안내합니다.", targetId: "nav-complaint-category", delayMs: 2000 }),
        Object.freeze({ message: "불법 주정차 신고 화면으로 이동합니다.", routeId: "complaint-illegal-parking", delayMs: 1200 }),
        Object.freeze({ message: "불법 주정차 신고 카드를 안내합니다. 이 카드에서 위치·사진·내용을 입력해 접수합니다.", targetId: "complaint-illegal-parking-report", delayMs: 2000 }),
        Object.freeze({ message: "안내가 완료되었습니다. '불법 주정차 신고' 카드에서 온라인으로 신고를 접수할 수 있습니다. 새로운 문의는 '새 대화'를 선택해 주세요." }),
      ]),
    }),
    // #965 — 공동주택 search choreography 강화
    // 1) focus directory search field
    // 2) type "공동주택" one char at a time (visible typing)
    // 3) submit search
    // 4) results list shown
    // 5) specific result/contact highlighted
    // 6) assistant final answer grounded in the left-pane result
    "공동주택 관련 문의는 어느 부서에 해야 하나요?": Object.freeze({
      id: "dept-housing-jdept01-search",
      description: "공동주택과 담당 부서·전화번호 검색 안내 (J-DEPT-01 재사용 + typing choreography)",
      steps: Object.freeze([
        Object.freeze({ message: "공동주택 관련 부서를 찾기 위해 업무 및 전화번호 안내를 엽니다.", journeyState: "J-DEPT-01:directory", focusSearch: true, delayMs: 1500 }),
        Object.freeze({ message: "검색창에 '공동주택'을 입력합니다.", typeQuery: "공동주택", delayMs: 2500 }),
        Object.freeze({ message: "검색을 실행합니다.", submitSearch: true, delayMs: 2000 }),
        Object.freeze({ message: "공동주택과 항목을 확인합니다.", delayMs: 1200 }),
        Object.freeze({ message: "공동주택 관련 문의는 공동주택과에서 담당합니다. 대표 연락처는 062-410-6033입니다.", delayMs: 0 }),
      ]),
    }),
    "housing_department": Object.freeze({
      id: "dept-housing-jdept01-search",
      description: "공동주택과 담당 부서·전화번호 검색 안내 (J-DEPT-01 재사용 + typing choreography)",
      steps: Object.freeze([
        Object.freeze({ message: "공동주택 관련 부서를 찾기 위해 업무 및 전화번호 안내를 엽니다.", journeyState: "J-DEPT-01:directory", focusSearch: true, delayMs: 1500 }),
        Object.freeze({ message: "검색창에 '공동주택'을 입력합니다.", typeQuery: "공동주택", delayMs: 2500 }),
        Object.freeze({ message: "검색을 실행합니다.", submitSearch: true, delayMs: 2000 }),
        Object.freeze({ message: "공동주택과 항목을 확인합니다.", delayMs: 1200 }),
        Object.freeze({ message: "공동주택 관련 문의는 공동주택과에서 담당합니다. 대표 연락처는 062-410-6033입니다.", delayMs: 0 }),
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

  // #927: drive an existing local clone journey state through the public
  // canvas API. Currently supports the approved J-DEPT-01 directory state,
  // which renders the 공동주택과 / 062-410-6033 / 공동주택과 업무전반 facts.
  function _applyJourneyState(journeyState) {
    if (!journeyState || typeof journeyState !== "string") return;
    var parts = journeyState.split(":");
    var journey = parts[0];
    var state = parts[1] || "";
    if (journey === "J-DEPT-01" && (state === "directory" || state === "result" || state === "menu")) {
      if (typeof window !== "undefined" && window.location && window.history
          && typeof window.history.pushState === "function") {
        var params = new URLSearchParams(window.location.search);
        params.set("journey", "J-DEPT-01");
        params.set("dept-state", state);
        window.history.pushState({}, "", "?" + params.toString());
      }
      var canvas = window.CitizenActionDemoCanvas;
      if (canvas && canvas.navigateToRoute) {
        canvas.navigateToRoute("home");
      }
    }
  }

  function _getCanvasEl() {
    return document.getElementById("demo-canvas");
  }

  function _executeStep(index) {
    if (_state !== STATE_RUNNING) return;
    if (index >= _steps.length) {
      _setState(STATE_DONE);
      return;
    }

    _currentStep = index;
    var step = _steps[index];

    // Execute DOM action FIRST so left-pane visuals render before
    // the chat message appears — 박사님 choreography ordering requirement (#965).
    if (step.routeId || step.targetId || step.journeyState || step.focusSearch || step.typeQuery || step.submitSearch) {
      _clearHighlights();
    }

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
    } else if (step.journeyState) {
      _applyJourneyState(step.journeyState);
    }

    // #965: search-field interaction steps
    if (step.focusSearch) {
      var demoEl = _getCanvasEl();
      if (demoEl) {
        var input = demoEl.querySelector(".bg-dept-search__input");
        if (input) {
          input.focus();
          input.classList.add(HIGHLIGHT_CLASS);
          _highlightedEls.push(input);
        }
      }
    }

    if (step.typeQuery) {
      var demoEl = _getCanvasEl();
      if (demoEl) {
        var input = demoEl.querySelector(".bg-dept-search__input");
        if (input) {
          input.value = step.typeQuery;
          input.classList.add(TYPING_CLASS);
          _highlightedEls.push(input);
        }
      }
    }

    if (step.submitSearch) {
      var demoEl = _getCanvasEl();
      if (demoEl) {
        var btn = demoEl.querySelector(".bg-dept-search__btn");
        if (btn) {
          btn.click();
        }
      }
    }

    // Show chat message AFTER DOM actions so the left-pane state is visible
    // before the explanation text.
    _appendChatMessage("ai", step.message);

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
