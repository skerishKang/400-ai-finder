/**
 * citizen-action-executor.js
 * Visible allowlisted click-through action executor for the demo canvas.
 */

(function () {
  "use strict";

  var ACTION_TYPES = Object.freeze({
    HIGHLIGHT: "HIGHLIGHT_ALLOWLISTED_ELEMENT",
    SCROLL: "SCROLL_TO_ALLOWLISTED_ELEMENT",
    OPEN_ROUTE: "OPEN_ALLOWLISTED_ROUTE",
    CLICK: "CLICK_ALLOWLISTED_ELEMENT",
    PREFILL: "PREFILL_APPROVED_DRAFT",
    STOP: "STOP_FOR_USER_CONFIRMATION",
  });

  var FORBIDDEN_TYPES = Object.freeze([
    "LOGIN", "SUBMIT", "UPLOAD_FILE", "PAY", "ENTER_IDENTITY",
  ]);

  var ALLOWED_CHOICE_IDS = Object.freeze([
    "illegal-parking",
    "public-parking-inconvenience",
    "residential-parking",
    "traffic-or-facility-safety",
    "other-or-unsure",
  ]);

  var EXECUTION_DELAY = 1200;

  var EXPLANATIONS = Object.freeze({
    "nav-civil-service": "민원 신청 페이지로 이동합니다.",
    "nav-complaint-category": "민원 유형 선택 영역으로 이동합니다.",
    "complaint-category-illegal-parking": "불법 주정차 신고 유형을 선택합니다.",
    "complaint-category-public-parking-inconvenience": "공용주차장 불편 유형을 선택합니다.",
    "complaint-category-residential-parking": "공동주택 주차 관련 유형을 선택합니다.",
    "complaint-category-traffic-or-facility-safety": "교통·시설 안전 유형을 선택합니다.",
    "complaint-category-other-or-unsure": "기타 유형을 선택합니다.",
    "complaint-body": "민원 내용을 자동으로 채웁니다.",
    "general-stop": "사용자의 확인이 필요하여 동작을 멈춥니다.",
    "route-transition": "페이지를 전환하는 중입니다...",
  });

  var PREFILL_TEXT = "본 시연을 위해 자동으로 생성된 민원 초안 내용입니다. 실제 제출 시에는 상세 내용을 직접 입력하셔야 합니다.";

  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------
  var _state = "ready"; // ready, running, paused, waiting, stopped, cancelled, blocked
  var _queue = [];
  var _index = 0;
  var _pendingTimer = null;
  var _runToken = 0;
  var _confirmationListener = null;
  var _currentLi = null;

  var _dom = {
    status: document.getElementById("executor-status"),
    trace: document.getElementById("action-trace"),
    btnNav: document.getElementById("btn-exec-nav"),
    btnPrefill: document.getElementById("btn-exec-prefill"),
    btnPause: document.getElementById("btn-exec-pause"),
    btnResume: document.getElementById("btn-exec-resume"),
    btnCancel: document.getElementById("btn-exec-cancel"),
    btnConfirmApprove: document.getElementById("btn-confirm-approve"),
    btnConfirmCancel: document.getElementById("btn-confirm-cancel"),
  };

  function _escHtml(str) {
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // -----------------------------------------------------------------------
  // Normalizer & Validator
  // -----------------------------------------------------------------------
  function _normalizePlan(rawPlan) {
    if (!rawPlan || typeof rawPlan !== "object") return null;

    var normalized = {
      plan_status: rawPlan.plan_status === "guided" ? "guided" : null,
      actions: [],
      requires_user_confirmation: !!rawPlan.requires_user_confirmation,
      hard_stop_required: !!rawPlan.hard_stop_required,
      reason_codes: Array.isArray(rawPlan.reason_codes) ? rawPlan.reason_codes.slice() : [],
    };

    if (!normalized.plan_status) return null;
    if (!Array.isArray(rawPlan.actions)) return null;

    for (var i = 0; i < rawPlan.actions.length; i++) {
      var act = rawPlan.actions[i];
      if (!act || typeof act !== "object") return null;

      // Exact shape check: must have these fields and NO others
      var expectedFields = ["action_type", "route_id", "target_id", "explanation_id", "requires_user_confirmation", "choice_ids"];
      var actualFields = Object.keys(act);
      if (actualFields.length !== expectedFields.length) return null;
      for (var j = 0; j < expectedFields.length; j++) {
        if (actualFields.indexOf(expectedFields[j]) === -1) return null;
      }

      var type = act.action_type;
      if (FORBIDDEN_TYPES.indexOf(type) !== -1) return null;
      if (Object.values(ACTION_TYPES).indexOf(type) === -1) return null;

      if (type === ACTION_TYPES.OPEN_ROUTE) {
        if (!window.CitizenActionDemoMap.isValidRoute(act.route_id)) return null;
      } else if (type === ACTION_TYPES.HIGHLIGHT || type === ACTION_TYPES.SCROLL || type === ACTION_TYPES.CLICK) {
        if (!window.CitizenActionDemoMap.isValidTarget(act.target_id)) return null;
      } else if (act.choice_ids) {
        if (!Array.isArray(act.choice_ids)) return null;
        for (var k = 0; k < act.choice_ids.length; k++) {
          if (ALLOWED_CHOICE_IDS.indexOf(act.choice_ids[k]) === -1) return null;
        }
      }

      normalized.actions.push(Object.freeze({
        action_type: type,
        route_id: act.route_id,
        target_id: act.target_id,
        explanation_id: act.explanation_id,
        requires_user_confirmation: !!act.requires_user_confirmation,
        choice_ids: act.choice_ids ? act.choice_ids.slice() : [],
      }));
    }

    var hasStop = false;
    var hasPrefill = false;
    for (var m = 0; m < normalized.actions.length; m++) {
      var a = normalized.actions[m];
      if (a.action_type === ACTION_TYPES.STOP) {
        hasStop = true;
        if (m < normalized.actions.length - 1) return null;
      }
      if (a.action_type === ACTION_TYPES.PREFILL) {
        hasPrefill = true;
      }
    }

    if (!hasStop) return null;
    if (hasPrefill) {
      var stopIdx = normalized.actions.length - 1;
      var prefillIdx = -1;
      for (var n = 0; n < normalized.actions.length; n++) {
        if (normalized.actions[n].action_type === ACTION_TYPES.PREFILL) prefillIdx = n;
      }
      if (prefillIdx !== stopIdx - 1) return null;
    }

    return Object.freeze(normalized);
  }

  // -----------------------------------------------------------------------
  // UI Helpers
  // -----------------------------------------------------------------------
  function _updateStatus(text) {
    if (_dom.status) _dom.status.textContent = text;
  }

  function _appendTrace(index, label, explanation, outcome) {
    if (!_dom.trace) return null;
    var li = document.createElement("li");
    li.className = "trace-item trace-item--active";
    li.setAttribute("data-action-index", index);
    li.innerHTML = '<span class="trace-icon" aria-hidden="true">&#x25B6;</span> ' +
                   '<strong>' + _escHtml(label) + '</strong>: ' + _escHtml(explanation);
    _dom.trace.appendChild(li);
    return li;
  }

  function _markTraceDone(li) {
    if (!li) return;
    li.className = "trace-item trace-item--done";
    li.innerHTML = li.innerHTML.replace(/&#x25B6;/, '&#x2713;');
  }

  function _markTraceOutcome(li, outcome) {
    if (!li) return;
    li.innerHTML += ' <span class="trace-outcome">(' + _escHtml(outcome) + ')</span>';
  }

  // -----------------------------------------------------------------------
  // Queue Driver
  // -----------------------------------------------------------------------
  function _scheduleNext() {
    if (_state !== "running" || _pendingTimer !== null) return;

    var token = _runToken;
    _pendingTimer = setTimeout(function () {
      _pendingTimer = null;
      if (token !== _runToken || _state !== "running") return;
      _runNextAction();
    }, EXECUTION_DELAY);
  }

  function _runNextAction() {
    if (_index >= _queue.length) {
      _state = "ready";
      _updateStatus("대기 중");
      return;
    }

    var action = _queue[_index];
    var label = "동작 " + (_index + 1);
    var exp = EXPLANATIONS[action.target_id] || EXPLANATIONS[action.route_id] || EXPLANATIONS["general-stop"] || "동작을 수행합니다.";
    var li = _appendTrace(_index, label, exp, "");
    _currentLi = li;

    if (action.action_type === ACTION_TYPES.PREFILL) {
      _state = "waiting";
      _updateStatus("초안 채우기 승인 대기 중...");
      _markTraceOutcome(li, "확인 대기");
      _attachConfirmationListener();
      return;
    }

    if (action.action_type === ACTION_TYPES.STOP) {
      _updateStatus("시연 종료");
      _markTraceDone(li);
      _markTraceOutcome(li, "stopped");
      _index++;
      _pendingTimer = null;
      _runToken++;
      _state = "stopped";
      return;
    }

    // Execute non-terminal actions
    try {
      _executeAction(action);
      _markTraceDone(li);
      _markTraceOutcome(li, "executed");
      _index++;
      _scheduleNext();
    } catch (e) {
      _state = "ready";
      _updateStatus("오류 발생: " + e.message);
      _markTraceOutcome(li, "오류");
    }
  }

  function _executeAction(action) {
    var targetEl = null;
    if (action.target_id) {
      targetEl = window.CitizenActionDemoCanvas.getTargetElement(action.target_id);
    }

    switch (action.action_type) {
      case ACTION_TYPES.HIGHLIGHT:
        if (!targetEl) throw new Error("Target not found");
        targetEl.classList.add("executor-highlight");
        targetEl.focus();
        break;
      case ACTION_TYPES.SCROLL:
        if (!targetEl) throw new Error("Target not found");
        targetEl.scrollIntoView({ behavior: "smooth", block: "center" });
        break;
      case ACTION_TYPES.OPEN_ROUTE:
        _updateStatus(EXPLANATIONS["route-transition"]);
        window.CitizenActionDemoCanvas.navigateToRoute(action.route_id);
        break;
      case ACTION_TYPES.CLICK:
        if (!targetEl) throw new Error("Target not found");
        if (targetEl.tagName !== "BUTTON") throw new Error("Target is not a button");
        var currentRoute = window.CitizenActionDemoCanvas.getCurrentRouteId();
        var routeDef = window.CitizenActionDemoMap.getRoute(currentRoute);
        if (!routeDef || routeDef.navTargets.indexOf(action.target_id) === -1) {
          throw new Error("Target is not a valid nav target for current route");
        }
        targetEl.classList.add("executor-pending-click");
        targetEl.click();
        break;
      default:
        throw new Error("Unsupported action type: " + action.action_type);
    }
  }

  function _attachConfirmationListener() {
    _confirmationListener = function (e) {
      if (e.target.id === "btn-confirm-approve") {
        e.stopPropagation();
        _approvePendingPrefill();
      } else if (e.target.id === "btn-confirm-cancel") {
        e.stopPropagation();
        _cancel();
      }
    };
    document.addEventListener("click", _confirmationListener, true);
  }

  function _approvePendingPrefill() {
    if (_state !== "waiting") return;

    var action = _queue[_index];
    if (!action || action.action_type !== ACTION_TYPES.PREFILL) return;

    document.removeEventListener("click", _confirmationListener, true);
    _confirmationListener = null;

    var body = window.CitizenActionDemoCanvas.getTargetElement("complaint-body");
    if (body) {
      body.textContent = PREFILL_TEXT;
    }

    if (_currentLi) {
      _markTraceDone(_currentLi);
      _markTraceOutcome(_currentLi, "approved");
    }

    _index++;
    _state = "running";
    _updateStatus("초안이 채워졌습니다.");
    _scheduleNext();
  }

  function _startPlan(rawPlan) {
    var plan = _normalizePlan(rawPlan);
    if (!plan) {
      _updateStatus("유효하지 않은 시연 계획입니다.");
      return;
    }

    _state = "running";
    _queue = plan.actions;
    _index = 0;
    _runToken++;
    _pendingTimer = null;
    if (_dom.trace) _dom.trace.innerHTML = "";
    _scheduleNext();
  }

  function _pause() {
    if (_state !== "running") return;
    _state = "paused";
    _updateStatus("일시정지됨");
    if (_pendingTimer) {
      clearTimeout(_pendingTimer);
      _pendingTimer = null;
    }
    if (_dom.btnPause) _dom.btnPause.style.display = "none";
    if (_dom.btnResume) _dom.btnResume.style.display = "inline-block";
  }

  function _resume() {
    if (_state !== "paused") return;
    _state = "running";
    _updateStatus("재개 중...");
    if (_dom.btnPause) _dom.btnPause.style.display = "inline-block";
    if (_dom.btnResume) _dom.btnResume.style.display = "none";
    _scheduleNext();
  }

  function _cancel() {
    _runToken++;
    if (_pendingTimer) {
      clearTimeout(_pendingTimer);
      _pendingTimer = null;
    }
    _queue = [];
    _index = 0;
    _state = "cancelled";
    _updateStatus("시연이 취소되었습니다.");
    if (_dom.trace) {
      var li = _appendTrace(-1, "취소", "사용자에 의해 시연이 취소되었습니다.", "cancelled");
      if (li) _markTraceDone(li);
    }
    if (_dom.btnPause) _dom.btnPause.style.display = "inline-block";
    if (_dom.btnResume) _dom.btnResume.style.display = "none";
  }

  window.CitizenActionDemoExecutor = Object.freeze({
    startPlan: _startPlan,
    pause: _pause,
    resume: _resume,
    cancel: _cancel,
    getSnapshot: function () {
      return Object.freeze({
        status: _state,
        actionIndex: _index,
        pendingTimer: _pendingTimer !== null,
        traceCount: (_dom.trace && _dom.trace._children) ? _dom.trace._children.length : 0
      });
    }
  });

  // Fixtures for the UI buttons
  var FIXTURES = {
    navigation: {
      plan_status: "guided",
      actions: [
        { action_type: ACTION_TYPES.OPEN_ROUTE, route_id: "civil-service", target_id: null, explanation_id: "open_route", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.HIGHLIGHT, target_id: "nav-complaint-category", route_id: null, explanation_id: "highlight_cat", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.SCROLL, target_id: "nav-complaint-category", route_id: null, explanation_id: "scroll_cat", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.CLICK, target_id: "nav-complaint-category", route_id: null, explanation_id: "click_cat", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.HIGHLIGHT, target_id: "complaint-category-illegal-parking", route_id: null, explanation_id: "highlight_parking", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.SCROLL, target_id: "complaint-category-illegal-parking", route_id: null, explanation_id: "scroll_parking", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.CLICK, target_id: "complaint-category-illegal-parking", route_id: null, explanation_id: "click_parking", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.STOP, route_id: null, target_id: null, explanation_id: "stop_conf", requires_user_confirmation: true, choice_ids: [] },
      ],
      requires_user_confirmation: true,
      hard_stop_required: true,
      reason_codes: [],
    },
    prefill: {
      plan_status: "guided",
      actions: [
        { action_type: ACTION_TYPES.OPEN_ROUTE, route_id: "complaint-intake", target_id: null, explanation_id: "open_route", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.HIGHLIGHT, target_id: "complaint-body", route_id: null, explanation_id: "highlight_body", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.SCROLL, target_id: "complaint-body", route_id: null, explanation_id: "scroll_body", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.PREFILL, route_id: null, target_id: "complaint-body", explanation_id: "prefill_draft", requires_user_confirmation: true, choice_ids: [] },
        { action_type: ACTION_TYPES.STOP, route_id: null, target_id: null, explanation_id: "stop_conf", requires_user_confirmation: true, choice_ids: [] },
      ],
      requires_user_confirmation: true,
      hard_stop_required: true,
      reason_codes: [],
    },
  };

  if (_dom.btnNav) _dom.btnNav.addEventListener("click", function () { window.CitizenActionDemoExecutor.startPlan(FIXTURES.navigation); });
  if (_dom.btnPrefill) _dom.btnPrefill.addEventListener("click", function () { window.CitizenActionDemoExecutor.startPlan(FIXTURES.prefill); });
  if (_dom.btnPause) _dom.btnPause.addEventListener("click", window.CitizenActionDemoExecutor.pause);
  if (_dom.btnResume) _dom.btnResume.addEventListener("click", window.CitizenActionDemoExecutor.resume);
  if (_dom.btnCancel) _dom.btnCancel.addEventListener("click", window.CitizenActionDemoExecutor.cancel);

})();
