/**
 * citizen-action-executor.js
 * Visible allowlisted click-through action executor for the demo canvas.
 */

(function () {
  "use strict";

  var ACTION_TYPES = Object.freeze({
    ASK_CLARIFYING_QUESTION: "ASK_CLARIFYING_QUESTION",
    PRESENT_CHOICES: "PRESENT_CHOICES",
    HIGHLIGHT: "HIGHLIGHT_ALLOWLISTED_ELEMENT",
    SCROLL: "SCROLL_TO_ALLOWLISTED_ELEMENT",
    OPEN_ROUTE: "OPEN_ALLOWLISTED_ROUTE",
    CLICK: "CLICK_ALLOWLISTED_ELEMENT",
    PREFILL: "PREFILL_APPROVED_DRAFT",
    STOP: "STOP_FOR_USER_CONFIRMATION",
  });

  var CLOSED_CHOICE_IDS = Object.freeze([
    "illegal-parking",
    "public-parking-inconvenience",
    "residential-parking",
    "traffic-or-facility-safety",
    "other-or-unsure",
  ]);

  var EXPLANATIONS = Object.freeze({
    "ask_clarifying_question": "추가 정보가 필요하여 질문을 드립니다.",
    "present_category_choices": "적절한 카테고리를 선택해 주세요.",
    "highlight_element": "해당 요소를 강조 표시합니다.",
    "scroll_to_element": "해당 요소로 화면을 이동합니다.",
    "open_route": "관련 페이지로 이동합니다.",
    "click_element": "해당 항목을 클릭합니다.",
    "prefill_draft": "민원 내용을 자동으로 채웁니다.",
    "stop_for_confirmation": "사용자의 확인이 필요하여 동작을 멈춥니다.",
  });

  var PREFILL_TEXT = "본 시연을 위해 자동으로 생성된 민원 초안 내용입니다. 실제 제출 시에는 상세 내용을 직접 입력하셔야 합니다.";
  var EXECUTION_DELAY = 1200;

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
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // -----------------------------------------------------------------------
  // Normalizer & Validator
  // -----------------------------------------------------------------------
  function _normalizePlan(rawPlan) {
    if (!rawPlan || typeof rawPlan !== "object" || Array.isArray(rawPlan)) return null;

    // Plan Field Check
    var planFields = Object.keys(rawPlan);
    var expectedPlanFields = ["plan_status", "actions", "requires_user_confirmation", "hard_stop_required", "reason_codes"];
    if (planFields.length !== expectedPlanFields.length) return null;
    for (var i = 0; i < expectedPlanFields.length; i++) {
      if (planFields.indexOf(expectedPlanFields[i]) === -1) return null;
    }

    if (rawPlan.plan_status !== "guided") return null;
    if (!Array.isArray(rawPlan.actions)) return null;
    if (rawPlan.actions.length < 1 || rawPlan.actions.length > 12) return null;
    if (rawPlan.hard_stop_required !== true) return null;
    if (!Array.isArray(rawPlan.reason_codes) || rawPlan.reason_codes.length !== 0) return null;
    if (typeof rawPlan.requires_user_confirmation !== "boolean") return null;

    var normalizedActions = [];
    var anyRequiresConfirmation = false;

    for (var j = 0; j < rawPlan.actions.length; j++) {
      var act = rawPlan.actions[j];
      if (!act || typeof act !== "object" || Array.isArray(act)) return null;

      // Action Field Check
      var actFields = Object.keys(act);
      var expectedActFields = ["action_type", "route_id", "target_id", "explanation_id", "requires_user_confirmation", "choice_ids"];
      if (actFields.length !== expectedActFields.length) return null;
      for (var k = 0; k < expectedActFields.length; k++) {
        if (actFields.indexOf(expectedActFields[k]) === -1) return null;
      }

      var type = act.action_type;
      var rid = act.route_id;
      var tid = act.target_id;
      var eid = act.explanation_id;
      var reqConf = act.requires_user_confirmation;
      var cids = act.choice_ids;

      if (typeof reqConf !== "boolean") return null;
      if (!Array.isArray(cids)) return null;

      // Strict Type Mapping
      if (type === ACTION_TYPES.ASK_CLARIFYING_QUESTION) {
        if (rid !== null || tid !== null || cids.length !== 0 || reqConf !== false || eid !== "ask_clarifying_question") return null;
      } else if (type === ACTION_TYPES.PRESENT_CHOICES) {
        if (rid !== null || tid !== null || cids.length === 0 || reqConf !== false || eid !== "present_category_choices") return null;
        // Unique choice IDs check
        if (new Set(cids).size !== cids.length) return null;
        // Closed allowlist check
        for (var ci = 0; ci < cids.length; ci++) {
          if (CLOSED_CHOICE_IDS.indexOf(cids[ci]) === -1) return null;
        }
      } else if (type === ACTION_TYPES.HIGHLIGHT || type === ACTION_TYPES.SCROLL || type === ACTION_TYPES.CLICK) {
        if (rid !== null || !window.CitizenActionDemoMap.isValidTarget(tid) || cids.length !== 0 || reqConf !== false) return null;
        if (type === ACTION_TYPES.HIGHLIGHT && eid !== "highlight_element") return null;
        if (type === ACTION_TYPES.SCROLL && eid !== "scroll_to_element") return null;
        if (type === ACTION_TYPES.CLICK && eid !== "click_element") return null;
      } else if (type === ACTION_TYPES.OPEN_ROUTE) {
        if (!window.CitizenActionDemoMap.isValidRoute(rid) || tid !== null || cids.length !== 0 || reqConf !== false || eid !== "open_route") return null;
      } else if (type === ACTION_TYPES.PREFILL) {
        if (rid !== null || tid !== "complaint-body" || cids.length !== 0 || reqConf !== true || eid !== "prefill_draft") return null;
      } else if (type === ACTION_TYPES.STOP) {
        if (tid !== null || (rid !== null && rid !== "handoff-stop") || cids.length !== 0 || reqConf !== true || eid !== "stop_for_confirmation") return null;
      } else {
        return null; // Unknown type
      }

      if (reqConf) anyRequiresConfirmation = true;

      normalizedActions.push(Object.freeze({
        action_type: type,
        route_id: rid,
        target_id: tid,
        explanation_id: eid,
        requires_user_confirmation: reqConf,
        choice_ids: cids.slice(),
      }));
    }

    // Sequence Checks
    var lastAction = normalizedActions[normalizedActions.length - 1];
    if (lastAction.action_type !== ACTION_TYPES.STOP) return null;

    for (var m = 0; m < normalizedActions.length - 1; m++) {
      if (normalizedActions[m].action_type === ACTION_TYPES.STOP) return null;
    }

    if (normalizedActions.length > 1) {
      var penultimateAction = normalizedActions[normalizedActions.length - 2];
      var hasPrefill = false;
      var prefillIdx = -1;
      var prefillCount = 0;
      for (var n = 0; n < normalizedActions.length; n++) {
        if (normalizedActions[n].action_type === ACTION_TYPES.PREFILL) {
          hasPrefill = true;
          prefillIdx = n;
          prefillCount++;
        }
      }
      if (prefillCount > 1) return null;
      if (hasPrefill && prefillIdx !== normalizedActions.length - 2) return null;
    }

    if (rawPlan.requires_user_confirmation !== anyRequiresConfirmation) return null;

    return Object.freeze({
      plan_status: "guided",
      actions: Object.freeze(normalizedActions),
      requires_user_confirmation: anyRequiresConfirmation,
      hard_stop_required: true,
      reason_codes: Object.freeze([]),
    });
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
    if (outcome) {
      li.innerHTML += ' <span class="trace-outcome">(' + _escHtml(outcome) + ')</span>';
    }
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
    var outcomeSpan = li.querySelector(".trace-outcome");
    if (outcomeSpan) {
      outcomeSpan.textContent = "(" + _escHtml(outcome) + ")";
    } else {
      li.innerHTML += ' <span class="trace-outcome">(' + _escHtml(outcome) + ')</span>';
    }
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
    var label = "순서 " + String(_index + 1).padStart(2, "0");
    var elapsed = "T+" + _index;
    var exp = EXPLANATIONS[action.explanation_id] || "동작을 수행합니다.";

    var li = _appendTrace(_index, label + " (" + elapsed + ")", exp, "");
    _currentLi = li;

    if (action.action_type === ACTION_TYPES.ASK_CLARIFYING_QUESTION || action.action_type === ACTION_TYPES.PRESENT_CHOICES) {
      _updateStatus(exp);
      _markTraceDone(li);
      _markTraceOutcome(li, "displayed");
      _index++;
      _scheduleNext();
      return;
    }

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

    try {
      _executeAction(action);
      _markTraceDone(li);
      _markTraceOutcome(li, "executed");
      _index++;
      _scheduleNext();
    } catch (e) {
      _handleBlocked("허용되지 않은 동작으로 안전하게 중단했습니다.");
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
        _updateStatus(EXPLANATIONS["open_route"]);
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
        throw new Error("Unsupported action type");
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

    var body = window.CitizenActionDemoCanvas.getTargetElement("complaint-body");
    if (!body) {
      _handleBlocked("허용되지 않은 동작으로 안전하게 중단했습니다.");
      return;
    }

    document.removeEventListener("click", _confirmationListener, true);
    _confirmationListener = null;

    body.textContent = PREFILL_TEXT;

    if (_currentLi) {
      _markTraceDone(_currentLi);
      _markTraceOutcome(_currentLi, "approved");
    }

    _index++;
    _state = "running";
    _updateStatus("초안이 채워졌습니다.");
    _scheduleNext();
  }

  function _handleBlocked(safeText) {
    if (_pendingTimer) {
      clearTimeout(_pendingTimer);
      _pendingTimer = null;
    }
    _queue = [];
    _index = 0;
    _runToken++;
    _state = "blocked";
    _updateStatus(safeText);
    if (_dom.trace) {
      var li = _appendTrace(-1, "중단", safeText, "blocked");
      if (li) _markTraceDone(li);
    }
  }

  function _startPlan(rawPlan) {
    // Cleanup prior state
    if (_confirmationListener) {
      document.removeEventListener("click", _confirmationListener, true);
      _confirmationListener = null;
    }
    if (_pendingTimer) {
      clearTimeout(_pendingTimer);
      _pendingTimer = null;
    }
    _runToken++;

    var plan = _normalizePlan(rawPlan);
    if (!plan) {
      _handleBlocked("시연 계획을 실행할 수 없습니다.");
      return;
    }

    _state = "running";
    _queue = plan.actions;
    _index = 0;
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
    if (_confirmationListener) {
      document.removeEventListener("click", _confirmationListener, true);
      _confirmationListener = null;
    }
    if (_pendingTimer) {
      clearTimeout(_pendingTimer);
      _pendingTimer = null;
    }
    _runToken++;
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
        { action_type: ACTION_TYPES.HIGHLIGHT, target_id: "nav-complaint-category", route_id: null, explanation_id: "highlight_element", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.SCROLL, target_id: "nav-complaint-category", route_id: null, explanation_id: "scroll_to_element", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.CLICK, target_id: "nav-complaint-category", route_id: null, explanation_id: "click_element", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.HIGHLIGHT, target_id: "complaint-category-illegal-parking", route_id: null, explanation_id: "highlight_element", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.SCROLL, target_id: "complaint-category-illegal-parking", route_id: null, explanation_id: "scroll_to_element", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.CLICK, target_id: "complaint-category-illegal-parking", route_id: null, explanation_id: "click_element", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.STOP, route_id: null, target_id: null, explanation_id: "stop_for_confirmation", requires_user_confirmation: true, choice_ids: [] },
      ],
      requires_user_confirmation: true,
      hard_stop_required: true,
      reason_codes: [],
    },
    prefill: {
      plan_status: "guided",
      actions: [
        { action_type: ACTION_TYPES.OPEN_ROUTE, route_id: "complaint-intake", target_id: null, explanation_id: "open_route", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.HIGHLIGHT, target_id: "complaint-body", route_id: null, explanation_id: "highlight_element", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.SCROLL, target_id: "complaint-body", route_id: null, explanation_id: "scroll_to_element", requires_user_confirmation: false, choice_ids: [] },
        { action_type: ACTION_TYPES.PREFILL, route_id: null, target_id: "complaint-body", explanation_id: "prefill_draft", requires_user_confirmation: true, choice_ids: [] },
        { action_type: ACTION_TYPES.STOP, route_id: null, target_id: null, explanation_id: "stop_for_confirmation", requires_user_confirmation: true, choice_ids: [] },
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
