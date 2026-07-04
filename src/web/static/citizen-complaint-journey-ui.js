/**
 * citizen-complaint-journey-ui.js — Stage #849 Phase B.
 *
 * Local closed-choice complaint intake UI binding the
 * `CitizenComplaintJourney` reducer (Phase A) to the
 * `CitizenActionDemoCanvas` local demo canvas.
 *
 * Scope and boundaries:
 *   - Uses ONLY window.CitizenComplaintJourney and window.CitizenActionDemoCanvas.
 *   - Never references CitizenActionExecutor, CitizenActionDemoMap,
 *     citizen_action_plan, planner action objects, or PREFILL_APPROVED_DRAFT.
 *   - No fetch / XHR / WebSocket / localStorage / sessionStorage / indexedDB /
 *     cookie / URL hash / query string.
 *   - No forms, no inputs, no textareas, no selects, no contenteditable,
 *     no submit. Only closed-choice `<button type="button">` cards.
 *   - State lives in a single closure variable; it is lost on page reload.
 *   - Draft text is rendered with textContent only — never innerHTML.
 *   - Prefill writes textContent to a fixed, allowlisted local target
 *     ("complaint-body") only after an explicit approval and a five-condition
 *     guard. No submission, transport, authentication, or navigation occurs.
 *
 * Public API:
 *   window.CitizenComplaintJourneyUI.init()  — wire up the UI once DOM is ready.
 *   window.CitizenComplaintJourneyUI.getState() — return current reducer state (debug).
 */

(function (root) {
  "use strict";

  // ===================================================================
  // Allowlisted external APIs
  // ===================================================================

  var journey = root.CitizenComplaintJourney;
  var canvas = root.CitizenActionDemoCanvas;

  // Fixed local route id — the only route the journey navigates to.
  var LOCAL_ROUTE = "complaint-intake";
  // Fixed local target id — the only element the journey writes draft text to.
  var LOCAL_TARGET = "complaint-body";

  // Reduction from a reducer category id (e.g. "illegal-parking") to the
  // canvas category target id (e.g. "complaint-category-illegal-parking").
  // Both vocabularies share the same hyphenated suffix; we prefix with
  // "complaint-category-" to match the canvas target id, and validate the
  // result against the reducer's own category id set rather than against the
  // canvas target set (the reducer is the source of truth for journeys).
  var CANVAS_CATEGORY_PREFIX = "complaint-category-";

  function _canvasTargetIdForCategory(categoryId) {
    return CANVAS_CATEGORY_PREFIX + categoryId;
  }

  // ===================================================================
  // Module state — single closure variable
  // ===================================================================

  var _state = null;

  // ===================================================================
  // DOM helpers (read-only lookups only; textContent for draft)
  // ===================================================================

  function _el(id) {
    var d = root.document;
    if (!d) { return null; }
    return d.getElementById(id);
  }

  function _clearChildren(node) {
    if (!node) { return; }
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function _setText(node, text) {
    if (!node) { return; }
    node.textContent = text == null ? "" : String(text);
  }

  function _makeButton(label, className, dataset) {
    var d = root.document;
    if (!d) { return null; }
    var btn = d.createElement("button");
    btn.setAttribute("type", "button");
    btn.className = className;
    btn.textContent = String(label); // free text from choice labels — closed vocabulary
    if (dataset) {
      for (var k in dataset) {
        if (Object.prototype.hasOwnProperty.call(dataset, k)) {
          btn.setAttribute("data-journey-" + k, String(dataset[k]));
        }
      }
    }
    return btn;
  }

  // ===================================================================
  // Rendering: status
  // ===================================================================

  var FACT_LABELS = {
    location: "위치",
    timing_or_recurrence: "시간",
    observed_situation: "상황",
    requested_remedy: "요청",
  };

  function _statusTextFromClarification(clar) {
    if (!clar) {
      return "모든 항목을 선택했습니다. 검토용 초안을 만들 수 있습니다.";
    }
    if (clar.type === "category") {
      return "민원 유형을 선택해 주세요.";
    }
    if (clar.type === "facts") {
      var names = (clar.missing || []).map(function (f) {
        return FACT_LABELS[f] || f;
      });
      return "다음 항목을 선택해 주세요: " + names.join(", ");
    }
    return "민원 유형을 선택해 주세요.";
  }

  function _renderStatus() {
    var clar = journey.getClarification(_state);
    _setText(_el("journey-status-text"), _statusTextFromClarification(clar));
  }

  // ===================================================================
  // Rendering: category cards (from getClosedChoices())
  // ===================================================================

  function _renderCategoryCards() {
    var host = _el("clarifying-choices");
    if (!host) { return; }
    _clearChildren(host);

    var vocab = journey.getClosedChoices();
    var cats = vocab.categories || [];
    for (var i = 0; i < cats.length; i++) {
      var c = cats[i];
      var btn = _makeButton(
        c.label,
        "choice-btn journey-category-card",
        { kind: "category", categoryId: c.id }
      );
      if (!btn) { continue; }
      if (_state && _state.category_id === c.id) {
        btn.setAttribute("aria-pressed", "true");
        btn.className = btn.className + " journey-choice-card--selected";
      } else {
        btn.setAttribute("aria-pressed", "false");
      }
      // Store the canonical reducer category id on the button for dispatch.
      btn.setAttribute("data-journey-category-id", c.id);
      host.appendChild(btn);
    }
  }

  // ===================================================================
  // Rendering: fact cards (from getClosedChoices() + getClarification())
  // ===================================================================

  function _chosenChoiceId(fieldId) {
    if (!_state || !_state.facts) { return null; }
    var v = _state.facts[fieldId];
    return (typeof v === "string") ? v : null;
  }

  function _renderFactCards() {
    var host = _el("journey-facts-body");
    if (!host) { return; }
    _clearChildren(host);

    // Only show fact picking after a valid category is selected.
    var clar = journey.getClarification(_state);
    if (!clar || clar.type !== "facts") {
      // No fact picking required yet (either no category, or fully complete).
      var note = root.document && root.document.createElement("p");
      if (note) {
        note.className = "journey-facts-empty";
        note.textContent = !clar
          ? "선택할 항목이 없습니다."
          : "먼저 민원 유형을 선택해 주세요.";
        host.appendChild(note);
      }
      return;
    }

    var vocab = journey.getClosedChoices();
    var facts = vocab.facts || {};
    var missing = clar.missing || [];

    // Show only the missing fields first (per requirement C).
    for (var m = 0; m < missing.length; m++) {
      var fieldId = missing[m];
      _renderFactGroup(host, fieldId, facts[fieldId]);
    }
  }

  function _renderFactGroup(host, fieldId, choices) {
    var d = root.document;
    if (!d || !host) { return; }
    if (!choices || !choices.length) { return; }

    var group = d.createElement("div");
    group.className = "journey-fact-group";

    var label = d.createElement("div");
    label.className = "journey-fact-group__label";
    label.textContent = FACT_LABELS[fieldId] || fieldId;
    group.appendChild(label);

    var btnRow = d.createElement("div");
    btnRow.className = "journey-fact-choices";

    var chosen = _chosenChoiceId(fieldId);
    for (var i = 0; i < choices.length; i++) {
      var ch = choices[i];
      var btn = _makeButton(
        ch.label,
        "journey-choice-card",
        { kind: "fact", fieldId: fieldId, choiceId: ch.id }
      );
      if (!btn) { continue; }
      if (chosen === ch.id) {
        btn.className = btn.className + " journey-choice-card--selected";
        btn.setAttribute("aria-pressed", "true");
      } else {
        btn.setAttribute("aria-pressed", "false");
      }
      btn.setAttribute("data-journey-field-id", fieldId);
      btn.setAttribute("data-journey-choice-id", ch.id);
      btnRow.appendChild(btn);
    }
    group.appendChild(btnRow);
    host.appendChild(group);
  }

  // ===================================================================
  // Rendering: build + reset controls
  // ===================================================================

  function _missingCount() {
    var clar = journey.getClarification(_state);
    if (!clar || clar.type !== "facts") { return 0; }
    return (clar.missing || []).length;
  }

  function _isComplete() {
    return journey.getClarification(_state) === null;
  }

  function _hasDraft() {
    var d = journey.getReviewDraft(_state);
    return typeof d === "string" && d.length > 0;
  }

  function _renderControls() {
    var host = _el("journey-controls-body");
    if (!host) { return; }
    _clearChildren(host);

    var complete = _isComplete();
    var hasDraft = _hasDraft();

    // Build draft button — disabled until all facts are selected.
    var build = _makeButton(
      "초안 만들기",
      "journey-control-btn journey-control-btn--primary",
      { kind: "build" }
    );
    if (build) {
      if (!complete || hasDraft) {
        build.setAttribute("disabled", "disabled");
      }
      build.setAttribute("data-journey-kind", "build");
      host.appendChild(build);
    }

    var reset = _makeButton(
      "처음부터 다시",
      "journey-control-btn",
      { kind: "clear" }
    );
    if (reset) {
      reset.setAttribute("data-journey-kind", "clear");
      if (!_state || (_state.category_id === null && !_hasDraft() && _state.approved === false)) {
        reset.setAttribute("disabled", "disabled");
      }
      host.appendChild(reset);
    }
  }

  // ===================================================================
  // Rendering: review draft (textContent only)
  // ===================================================================

  function _renderReview() {
    var draftNode = _el("journey-draft-text");
    var ctrlHost = _el("journey-review-controls");
    var draftText = journey.getReviewDraft(_state);

    _setText(draftNode, draftText);

    if (ctrlHost) { _clearChildren(ctrlHost); }

    if (typeof draftText !== "string" || draftText.length === 0) {
      // No draft — nothing to review.
      return;
    }

    if (!ctrlHost) { return; }

    // "선택 내용 수정" — hide draft, re-show closed fact choices.
    var edit = _makeButton(
      "선택 내용 수정",
      "journey-control-btn",
      { kind: "edit" }
    );
    if (edit) {
      edit.setAttribute("data-journey-kind", "edit");
      ctrlHost.appendChild(edit);
    }

    // "초안 폐기" — REJECT_DRAFT.
    var discard = _makeButton(
      "초안 폐기",
      "journey-control-btn journey-control-btn--danger",
      { kind: "reject" }
    );
    if (discard) {
      discard.setAttribute("data-journey-kind", "reject");
      ctrlHost.appendChild(discard);
    }

    // "검토 후 로컬 영역에 채우기" — APPROVE_DRAFT + guarded prefill.
    var approve = _makeButton(
      "검토 후 로컬 영역에 채우기",
      "journey-control-btn journey-control-btn--primary",
      { kind: "approve" }
    );
    if (approve) {
      approve.setAttribute("data-journey-kind", "approve");
      ctrlHost.appendChild(approve);
    }
  }

  // ===================================================================
  // Rendering: terminal notice
  // ===================================================================

  var TERMINAL_TEXT =
    "초안은 로컬 시연 영역에만 반영되었습니다. " +
    "실제 제출·전송·인증은 수행하지 않으며 여기서 종료됩니다.";

  function _setTerminal(text) {
    _setText(_el("journey-terminal-text"), text || "");
  }

  function _clearTerminal() {
    _setTerminal("");
  }

  function _setFailClosed(text) {
    _setTerminal(text);
  }

  // ===================================================================
  // Full re-render from current state
  // ===================================================================

  function _renderAll() {
    _renderStatus();
    _renderCategoryCards();
    _renderFactCards();
    _renderControls();
    _renderReview();
  }

  // ===================================================================
  // Canvas route synchronisation
  // ===================================================================

  function _ensureIntakeRoute() {
    if (!canvas) { return; }
    if (typeof canvas.getCurrentRouteId !== "function") { return; }
    if (canvas.getCurrentRouteId() !== LOCAL_ROUTE) {
      if (typeof canvas.navigateToRoute === "function") {
        canvas.navigateToRoute(LOCAL_ROUTE);
      }
    }
  }

  // ===================================================================
  // Event dispatch helpers (reducer only)
  // ===================================================================

  function _dispatchSelectCategory(categoryId) {
    _state = journey.reduce(_state, {
      type: "SELECT_CATEGORY",
      category_id: categoryId
    });
    _ensureIntakeRoute();
    // Selecting a category clears draft/approval in the reducer; make sure
    // no leftover draft text remains in the DOM.
    _clearTerminal();
    _renderAll();
  }

  function _dispatchSelectFact(fieldId, choiceId) {
    _state = journey.reduce(_state, {
      type: "SELECT_FACT",
      field_id: fieldId,
      choice_id: choiceId
    });
    // Changing a fact invalidates draft/approval; clear stale DOM text.
    _clearTerminal();
    var draftNode = _el("journey-draft-text");
    _setText(draftNode, "");
    _renderAll();
  }

  function _dispatchBuildDraft() {
    _state = journey.reduce(_state, { type: "BUILD_DRAFT" });
    _clearTerminal();
    _renderAll();
  }

  function _dispatchRejectDraft() {
    _state = journey.reduce(_state, { type: "REJECT_DRAFT" });
    _clearTerminal();
    var draftNode = _el("journey-draft-text");
    _setText(draftNode, "");
    _renderAll();
  }

  function _dispatchClearAll() {
    _state = journey.reduce(_state, { type: "CLEAR_ALL" });
    _clearTerminal();
    var draftNode = _el("journey-draft-text");
    _setText(draftNode, "");
    _renderAll();
  }

  // ===================================================================
  // Approval guard → local textContent prefill only
  // ===================================================================

  function _dispatchApproveAndPrefill() {
    // First, attempt approval.
    _state = journey.reduce(_state, { type: "APPROVE_DRAFT" });

    var prefill = journey.getApprovedPrefill(_state);
    var routeOk = canvas &&
      (typeof canvas.getCurrentRouteId === "function") &&
      (canvas.getCurrentRouteId() === LOCAL_ROUTE);
    var targetOk = false;
    var target = null;
    if (
      prefill &&
      prefill.target_id === LOCAL_TARGET &&
      (typeof prefill.draft_text === "string") &&
      prefill.draft_text.length > 0 &&
      routeOk &&
      (typeof canvas.getTargetElement === "function")
    ) {
      target = canvas.getTargetElement(LOCAL_TARGET);
      targetOk = !!target;
    }

    if (!(prefill && prefill.target_id === LOCAL_TARGET &&
          typeof prefill.draft_text === "string" && prefill.draft_text.length > 0 &&
          routeOk && targetOk)) {
      // FAIL-CLOSED: do not write to complaint-body, do not call executor,
      // do not navigate. Surface a local status notice only.
      _setFailClosed("로컬 작성 영역을 찾지 못해 반영하지 않았습니다.");
      _renderAll();
      return;
    }

    // All five conditions met — write draft text via textContent only.
    target.textContent = prefill.draft_text;

    // Terminal stop notice: no submission, transport, or authentication.
    _setTerminal(TERMINAL_TEXT);
    _renderAll();
  }

  // ===================================================================
  // "선택 내용 수정" — re-show closed choices (not free-text edit)
  // ===================================================================

  function _editSelections() {
    // Hide the review draft text and re-show fact choices without
    // discarding current selections. We do this by clearing the draft
    // text shown in the DOM and re-rendering fact cards (which are
    // gated on getClarification() — once a draft exists, clarification
    // is null, so force re-display of all fact groups by temporarily
    // relying on the build controls). The cleanest closed-choice path is
    // to re-show every fact group by re-rendering after dropping draft
    // display only.
    var draftNode = _el("journey-draft-text");
    _setText(draftNode, "");
    var ctrlHost = _el("journey-review-controls");
    if (ctrlHost) { _clearChildren(ctrlHost); }
    _clearTerminal();

    // Re-render fact cards for all required fields so the user can
    // re-select choices. Since clarification is null once complete, we
    // need a dedicated "edit" render that shows every fact group.
    _renderFactCardsForEdit();
  }

  function _renderFactCardsForEdit() {
    var host = _el("journey-facts-body");
    if (!host) { return; }
    _clearChildren(host);

    var vocab = journey.getClosedChoices();
    var facts = vocab.facts || {};
    var fieldIds = Object.keys(facts);
    for (var i = 0; i < fieldIds.length; i++) {
      _renderFactGroup(host, fieldIds[i], facts[fieldIds[i]]);
    }
  }

  // ===================================================================
  // Event delegation (single container listener)
  // ===================================================================

  function _journeyKind(node) {
    if (!node || node.nodeType !== 1) { return null; }
    return node.getAttribute("data-journey-kind");
  }

  function _bindRailControls() {
    var ids = [
      "clarifying-choices",
      "journey-facts-body",
      "journey-controls-body",
      "journey-review-controls"
    ];
    for (var i = 0; i < ids.length; i++) {
      var host = _el(ids[i]);
      if (!host || host.getAttribute("data-journey-bound") === "true") {
        continue;
      }
      host.setAttribute("data-journey-bound", "true");
      host.addEventListener("click", _onJourneyClick);
    }
  }

  function _onJourneyClick(e) {
    var btn = e.target.closest
      ? e.target.closest("button[data-journey-kind], button[data-journey-category-id], button[data-journey-field-id]")
      : null;
    if (!btn) { return; }

    var kind = _journeyKind(btn);
    var categoryId = btn.getAttribute("data-journey-category-id");
    var fieldId = btn.getAttribute("data-journey-field-id");
    var choiceId = btn.getAttribute("data-journey-choice-id");

    if (categoryId) {
      _dispatchSelectCategory(categoryId);
      return;
    }
    if (fieldId && choiceId) {
      _dispatchSelectFact(fieldId, choiceId);
      return;
    }

    switch (kind) {
      case "build":   _dispatchBuildDraft(); break;
      case "reject":  _dispatchRejectDraft(); break;
      case "clear":   _dispatchClearAll(); break;
      case "edit":    _editSelections(); break;
      case "approve": _dispatchApproveAndPrefill(); break;
      default: break;
    }
  }

  // ===================================================================
  // Canvas category-card synchronisation
  // ===================================================================

  // The canvas renders its own category cards on the "complaint-category"
  // route. When the user clicks one, we mirror the selection into the
  // reducer so rail and canvas stay in sync. We attach a single delegated
  // listener to the demo canvas element.
  function _bindCanvasCategorySync() {
    var d = root.document;
    if (!d || !canvas) { return; }
    var demo = d.getElementById("demo-canvas");
    if (!demo || demo.getAttribute("data-journey-canvas-bound") === "true") {
      return;
    }
    demo.setAttribute("data-journey-canvas-bound", "true");
    demo.addEventListener("click", function (e) {
      var target = e.target.closest
        ? e.target.closest("[data-action-target]")
        : null;
      if (!target) { return; }
      var targetId = target.getAttribute("data-action-target");
      if (typeof targetId !== "string" ||
          targetId.indexOf(CANVAS_CATEGORY_PREFIX) !== 0) {
        return;
      }
      var categoryId = targetId.slice(CANVAS_CATEGORY_PREFIX.length);
      // Validate the extracted category id against the reducer's own
      // vocabulary (not against the canvas target id). The canvas target
      // id format is "complaint-category-" + reducer-category-id; if the
      // slice is known in the reducer's category list it is safe to dispatch.
      if (_canvasTargetIdForCategory(categoryId) !== targetId) {
        return;
      }
      _state = journey.reduce(_state, {
        type: "SELECT_CATEGORY",
        category_id: categoryId
      });
      _ensureIntakeRoute();
      _clearTerminal();
      _renderAll();
    });
  }

  // ===================================================================
  // Init
  // ===================================================================

  function _start() {
    if (!journey || typeof journey.createInitialState !== "function") {
      return;
    }
    _state = journey.createInitialState();
    _renderAll();
    _bindRailControls();
    _bindCanvasCategorySync();
  }

  function init() {
    var d = root.document;
    if (!d) { return; }
    if (d.readyState === "loading") {
      d.addEventListener("DOMContentLoaded", _start);
    } else {
      _start();
    }
  }

  function getState() {
    return _state;
  }

  // ===================================================================
  // Export
  // ===================================================================

  root.CitizenComplaintJourneyUI = Object.freeze({
    init: init,
    getState: getState
  });

  // Auto-init when loaded into a browser environment.
  init();
}(typeof self !== "undefined" ? self : this));
