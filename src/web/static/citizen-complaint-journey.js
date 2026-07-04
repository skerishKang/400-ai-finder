/**
 * citizen-complaint-journey.js — pure closed-choice complaint intake reducer.
 *
 * UMD: works with Node `require()` and browser `window.CitizenComplaintJourney`.
 *
 * Public API:
 *   createInitialState()
 *   reduce(state, event)
 *   getClarification(state)
 *   getClosedChoices()
 *   getReviewDraft(state)
 *   getApprovedPrefill(state)
 *
 * No DOM, no storage, no network, no fetch, no persistence.
 * All fact values are fixed non-identifying Korean choice IDs.
 * No free-text input, no PII, no login, no attachment, no payment,
 * no legal judgment, no agency promise.
 */

(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define([], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.CitizenComplaintJourney = factory();
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // =========================================================================
  // Constants — closed vocabulary
  // =========================================================================

  /** Canonical category IDs — exactly five, hyphen format. */
  var CATEGORIES = [
    { id: "illegal-parking",            label: "불법주정차" },
    { id: "public-parking-inconvenience", label: "공용주차장 불편" },
    { id: "residential-parking",        label: "공동주택 주차" },
    { id: "traffic-or-facility-safety", label: "교통·시설 안전" },
    { id: "other-or-unsure",            label: "기타" },
  ];

  /** Required intake fact field IDs. */
  var FACT_FIELD_IDS = [
    "location",
    "timing_or_recurrence",
    "observed_situation",
    "requested_remedy",
  ];

  /** Closed choices per field — non-identifying, generalised Korean. */
  var FACT_CHOICES = {
    location: [
      { id: "roadside",                  label: "일반 도로변" },
      { id: "public-parking-area",       label: "공용주차장" },
      { id: "apartment-common-area",     label: "공동주택 공용구역" },
      { id: "intersection-crosswalk",    label: "교차로·횡단보도 주변" },
    ],
    timing_or_recurrence: [
      { id: "right-now",                 label: "현재 진행 중" },
      { id: "recent-once",               label: "최근 1회 발생" },
      { id: "repeated",                  label: "반복적으로 발생" },
      { id: "weekday-repeated",          label: "평일 반복" },
      { id: "unknown-exact",             label: "정확히 알 수 없음" },
    ],
    observed_situation: [
      { id: "vehicle-blocking-passage",   label: "차량 통행 방해" },
      { id: "parking-use-inconvenience",  label: "주차 이용 불편" },
      { id: "safety-risk-observed",       label: "안전 위험 관찰" },
      { id: "facility-obstruction",       label: "시설 훼손·장애" },
    ],
    requested_remedy: [
      { id: "request-site-check",         label: "현장 확인 요청" },
      { id: "request-guidance",           label: "계도 요청" },
      { id: "request-improvement-review", label: "개선 검토 요청" },
      { id: "request-general-review",     label: "일반 검토 요청" },
    ],
  };

  // =========================================================================
  // Helpers
  // =========================================================================

  function _isString(v) {
    return typeof v === "string";
  }

  function _isPlainObject(v) {
    return v !== null && typeof v === "object" && !Array.isArray(v);
  }

  /** Check if a string is a known category ID. */
  function _isValidCategoryId(id) {
    if (!_isString(id)) { return false; }
    for (var i = 0; i < CATEGORIES.length; i++) {
      if (CATEGORIES[i].id === id) { return true; }
    }
    return false;
  }

  /** Check if a choice ID is valid for the given field. */
  function _isValidChoice(fieldId, choiceId) {
    if (!_isString(fieldId) || !_isString(choiceId)) { return false; }
    var choices = FACT_CHOICES[fieldId];
    if (!choices) { return false; }
    for (var i = 0; i < choices.length; i++) {
      if (choices[i].id === choiceId) { return true; }
    }
    return false;
  }

  /** Return the display label for a category ID. */
  function _categoryLabel(id) {
    if (!_isString(id)) { return null; }
    for (var i = 0; i < CATEGORIES.length; i++) {
      if (CATEGORIES[i].id === id) { return CATEGORIES[i].label; }
    }
    return null;
  }

  /** Return the display label for a field choice. */
  function _choiceLabel(fieldId, choiceId) {
    var choices = FACT_CHOICES[fieldId];
    if (!choices) { return null; }
    for (var i = 0; i < choices.length; i++) {
      if (choices[i].id === choiceId) { return choices[i].label; }
    }
    return null;
  }

  /** Collect missing fact field IDs from a state's facts. */
  function _missingFacts(state) {
    var missing = [];
    var facts = state.facts;
    for (var i = 0; i < FACT_FIELD_IDS.length; i++) {
      var fieldId = FACT_FIELD_IDS[i];
      if (!_isString(facts[fieldId]) || !_isValidChoice(fieldId, facts[fieldId])) {
        missing.push(fieldId);
      }
    }
    return missing;
  }

  /** Build the draft text from state. Returns null if missing facts. */
  function _buildDraftText(state) {
    var catLabel = _categoryLabel(state.category_id);
    if (!catLabel) { return null; }

    var locLabel = _choiceLabel("location", state.facts.location);
    var timeLabel = _choiceLabel("timing_or_recurrence", state.facts.timing_or_recurrence);
    var sitLabel = _choiceLabel("observed_situation", state.facts.observed_situation);
    var remLabel = _choiceLabel("requested_remedy", state.facts.requested_remedy);

    if (!locLabel || !timeLabel || !sitLabel || !remLabel) { return null; }

    var lines = [];
    lines.push("[검토용 초안 — 로컬 개념 시연]");
    lines.push("");
    lines.push("유형: " + catLabel);
    lines.push("");
    lines.push("- 위치: " + locLabel);
    lines.push("- 시간: " + timeLabel);
    lines.push("- 상황: " + sitLabel);
    lines.push("- 요청: " + remLabel);
    lines.push("");
    lines.push("(위 내용은 로컬 시연을 위한 검토 초안입니다. 제출 전 확인이 필요합니다.)");

    return lines.join("\n");
  }

  /** Build the clarification object for a given state. */
  function _clarify(state) {
    if (!_isString(state.category_id) || !_isValidCategoryId(state.category_id)) {
      return { type: "category" };
    }
    var missing = _missingFacts(state);
    if (missing.length > 0) {
      return { type: "facts", missing: missing };
    }
    return null;
  }

  /** Check if event has extra unknown keys beyond recognised ones. */
  function _hasExtraKeys(event, knownKeys) {
    for (var key in event) {
      if (Object.prototype.hasOwnProperty.call(event, key)) {
        var allowed = false;
        for (var i = 0; i < knownKeys.length; i++) {
          if (knownKeys[i] === key) { allowed = true; break; }
        }
        if (!allowed) { return true; }
      }
    }
    return false;
  }

  // =========================================================================
  // Public API
  // =========================================================================

  /**
   * createInitialState() → state
   *
   * Returns a clean initial state.
   * State shape:
   *   { category_id: null, facts: { location: null, ... },
   *     draft: null, approved: false, _sealed: false }
   */
  function createInitialState() {
    return {
      category_id: null,
      facts: {
        location: null,
        timing_or_recurrence: null,
        observed_situation: null,
        requested_remedy: null,
      },
      draft: null,
      approved: false,
    };
  }

  /**
   * reduce(state, event) → newState
   *
   * Immutable reducer. Returns a new state (shallow copy).
   * Unknown event types or invalid payloads return state unchanged.
   *
   * Known events:
   *   { type: "SELECT_CATEGORY", category_id }
   *   { type: "SELECT_FACT", field_id, choice_id }
   *   { type: "BUILD_DRAFT" }
   *   { type: "APPROVE_DRAFT" }
   *   { type: "REJECT_DRAFT" }
   *   { type: "CLEAR_ALL" }
   */
  function reduce(state, event) {
    // Guard: state and event must be plain objects
    if (!_isPlainObject(state) || !_isPlainObject(event)) {
      return state;
    }

    // Guard: event must have a string type key; no extra keys
    var baseKnownKeys = ["type"];
    if (!_isString(event.type)) {
      return state;
    }

    switch (event.type) {

      case "SELECT_CATEGORY": {
        var knownKeys = baseKnownKeys.concat(["category_id"]);
        if (_hasExtraKeys(event, knownKeys)) { return state; }
        var catId = event.category_id;
        if (!_isString(catId) || !_isValidCategoryId(catId)) { return state; }
        return {
          category_id: catId,
          facts: { location: null, timing_or_recurrence: null,
                   observed_situation: null, requested_remedy: null },
          draft: null,
          approved: false,
        };
      }

      case "SELECT_FACT": {
        var knownKeys2 = baseKnownKeys.concat(["field_id", "choice_id"]);
        if (_hasExtraKeys(event, knownKeys2)) { return state; }
        var fieldId = event.field_id;
        var choiceId = event.choice_id;
        if (!_isString(fieldId) || !_isString(choiceId)) { return state; }
        // Must be a recognised field and valid choice
        if (!FACT_CHOICES[fieldId]) { return state; }
        if (!_isValidChoice(fieldId, choiceId)) { return state; }
        // Cloning facts
        var newFacts = {};
        for (var k in state.facts) {
          if (Object.prototype.hasOwnProperty.call(state.facts, k)) {
            newFacts[k] = state.facts[k];
          }
        }
        newFacts[fieldId] = choiceId;
        // Changing a fact invalidates draft and approval
        return {
          category_id: state.category_id,
          facts: newFacts,
          draft: null,
          approved: false,
        };
      }

      case "BUILD_DRAFT": {
        if (_hasExtraKeys(event, baseKnownKeys)) { return state; }
        if (!_isString(state.category_id) || !_isValidCategoryId(state.category_id)) {
          return state;
        }
        var missing = _missingFacts(state);
        if (missing.length > 0) { return state; }
        var draftText = _buildDraftText(state);
        if (draftText === null) { return state; }
        return {
          category_id: state.category_id,
          facts: {
            location: state.facts.location,
            timing_or_recurrence: state.facts.timing_or_recurrence,
            observed_situation: state.facts.observed_situation,
            requested_remedy: state.facts.requested_remedy,
          },
          draft: draftText,
          approved: false,
        };
      }

      case "APPROVE_DRAFT": {
        if (_hasExtraKeys(event, baseKnownKeys)) { return state; }
        if (!_isString(state.draft)) { return state; }
        return {
          category_id: state.category_id,
          facts: {
            location: state.facts.location,
            timing_or_recurrence: state.facts.timing_or_recurrence,
            observed_situation: state.facts.observed_situation,
            requested_remedy: state.facts.requested_remedy,
          },
          draft: state.draft,
          approved: true,
        };
      }

      case "REJECT_DRAFT": {
        if (_hasExtraKeys(event, baseKnownKeys)) { return state; }
        return {
          category_id: state.category_id,
          facts: {
            location: state.facts.location,
            timing_or_recurrence: state.facts.timing_or_recurrence,
            observed_situation: state.facts.observed_situation,
            requested_remedy: state.facts.requested_remedy,
          },
          draft: null,
          approved: false,
        };
      }

      case "CLEAR_ALL": {
        if (_hasExtraKeys(event, baseKnownKeys)) { return state; }
        return createInitialState();
      }

      default:
        // Unknown event type — reject silently
        return state;
    }
  }

  /**
   * getClarification(state) → null | { type, ... }
   *
   * Returns null if state is complete (all facts selected).
   * Returns { type: "category" } if no valid category is selected.
   * Returns { type: "facts", missing: [fieldId, ...] } if category is
   * selected but some required facts are missing/invalid.
   */
  function getClarification(state) {
    if (!_isPlainObject(state)) { return { type: "category" }; }
    return _clarify(state);
  }

  /**
   * getClosedChoices() → { categories: [...], facts: {...} }
   *
   * Returns the complete closed-choice vocabulary.
   * Each category: { id, label }
   * Each fact field: { id, label } array.
   */
  function getClosedChoices() {
    var catCopy = [];
    for (var i = 0; i < CATEGORIES.length; i++) {
      catCopy.push({ id: CATEGORIES[i].id, label: CATEGORIES[i].label });
    }

    var factsCopy = {};
    for (var fieldId in FACT_CHOICES) {
      if (Object.prototype.hasOwnProperty.call(FACT_CHOICES, fieldId)) {
        var arr = [];
        var src = FACT_CHOICES[fieldId];
        for (var j = 0; j < src.length; j++) {
          arr.push({ id: src[j].id, label: src[j].label });
        }
        factsCopy[fieldId] = arr;
      }
    }

    return { categories: catCopy, facts: factsCopy };
  }

  /**
   * getReviewDraft(state) → string | null
   *
   * Returns the current draft text if a draft has been built,
   * or null if no draft exists.
   */
  function getReviewDraft(state) {
    if (!_isPlainObject(state)) { return null; }
    return _isString(state.draft) ? state.draft : null;
  }

  /**
   * getApprovedPrefill(state) → { target_id, draft_text } | null
   *
   * Returns a prefill payload only after APPROVE_DRAFT has been called.
   * Before approval, returns null.
   * After REJECT_DRAFT or CLEAR_ALL, returns null (draft and approval gone).
   *
   * Payload shape:
   *   { target_id: "complaint-body", draft_text: "..." }
   *
   * The target_id is a fixed allowlisted element id for Phase B UI binding.
   * Planner/executor do not read this value.
   */
  function getApprovedPrefill(state) {
    if (!_isPlainObject(state)) { return null; }
    if (state.approved !== true) { return null; }
    if (!_isString(state.draft) || state.draft === "") { return null; }
    return {
      target_id: "complaint-body",
      draft_text: state.draft,
    };
  }

  // =========================================================================
  // Export
  // =========================================================================

  return {
    createInitialState: createInitialState,
    reduce: reduce,
    getClarification: getClarification,
    getClosedChoices: getClosedChoices,
    getReviewDraft: getReviewDraft,
    getApprovedPrefill: getApprovedPrefill,
  };
}));
