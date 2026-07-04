/**
 * protocol.js — MV3 local fixture bridge protocol contract.
 * UMD: Node `require()` and browser `window.CitizenActionMV3LocalBridgeProtocol`.
 * Public API: validateActionMessage(message), isLocalFixtureLocation(locationLike)
 * No DOM, no network, no storage. Closed vocabulary only.
 */
(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define([], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.CitizenActionMV3LocalBridgeProtocol = factory();
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // -----------------------------------------------------------------------
  // Closed vocabulary
  // -----------------------------------------------------------------------
  var VALID = Object.freeze({
    ACTION: Object.freeze([
      "HIGHLIGHT_ALLOWLISTED_ELEMENT", "SCROLL_TO_ALLOWLISTED_ELEMENT",
      "OPEN_ALLOWLISTED_ROUTE", "CLICK_ALLOWLISTED_ELEMENT",
      "PREFILL_APPROVED_DRAFT", "STOP_FOR_USER_CONFIRMATION",
    ]),
    BLOCKED: Object.freeze([
      "ASK_CLARIFYING_QUESTION", "PRESENT_CHOICES",
      "LOGIN", "SUBMIT", "UPLOAD_FILE", "PAY", "ENTER_IDENTITY",
    ]),
    ROUTE: Object.freeze([
      "home", "civil-service", "complaint-category",
      "complaint-intake", "complaint-review", "handoff-stop",
    ]),
    TARGET: Object.freeze([
      "nav-civil-service", "nav-complaint-category",
      "complaint-category-illegal-parking",
      "complaint-category-public-parking-inconvenience",
      "complaint-category-residential-parking",
      "complaint-category-traffic-or-facility-safety",
      "complaint-category-other-or-unsure",
      "complaint-body", "complaint-draft-review",
      "confirm-draft-prefill", "handoff-notice",
    ]),
  });

  var CODE = Object.freeze({
    MALFORMED: "malformed_message",
    UNKNOWN_TYPE: "unknown_message_type",
    UNSUPPORTED: "unsupported_action",
    BAD_SHAPE: "invalid_action_shape",
    BAD_ROUTE: "unallowlisted_route",
    BAD_TARGET: "unallowlisted_target",
    SENSITIVE: "sensitive_action_blocked",
    INACTIVE: "inactive_fixture",
  });

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------
  function isString(v) { return typeof v === "string"; }
  function isObj(v)    { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function inSet(s, s2) { return isString(s) && s2.indexOf(s) !== -1; }
  function keys(obj)   { return Object.keys(obj); }

  function onlyKeys(obj, allowed) {
    return keys(obj).every(function (k) { return allowed.indexOf(k) !== -1; });
  }

  function reject(msg) { return { ok: false, reason_code: msg }; }

  function ok(action) { return { ok: true, action: action }; }

  function baseAction(a) {
    return {
      action_type: a.action_type,
      route_id: a.route_id,
      target_id: a.target_id,
      explanation_id: a.explanation_id || "highlight_element",
      requires_user_confirmation: a.requires_user_confirmation,
      choice_ids: [],
    };
  }

  // -----------------------------------------------------------------------
  // Location guard
  // -----------------------------------------------------------------------
  function isLocalFixtureLocation(loc) {
    if (!loc) return false;
    var origin, pathname;
    if (isString(loc)) {
      try { var u = new URL(loc); origin = u.origin; pathname = u.pathname; }
      catch (e) { return false; }
    } else if (isObj(loc)) {
      origin = loc.origin || ""; pathname = loc.pathname || "";
    } else { return false; }
    var hosts = Object.freeze(["http://localhost", "http://127.0.0.1"]);
    var paths = Object.freeze(["/static/citizen-action-demo.html", "/citizen-action-demo.html"]);
    return hosts.indexOf(origin) !== -1 && paths.indexOf(pathname) !== -1;
  }

  // -----------------------------------------------------------------------
  // Message validation
  // -----------------------------------------------------------------------
  function validateActionMessage(msg) {
    if (!isObj(msg))                              return reject(CODE.MALFORMED);
    if (!isString(msg.type) ||
        msg.type !== "CITIZEN_ACTION_BRIDGE_EXECUTE_V1")
                                               return reject(CODE.UNKNOWN_TYPE);
    if (!isObj(msg.action))                       return reject(CODE.MALFORMED);
    if (!onlyKeys(msg, ["type", "action"]))       return reject(CODE.BAD_SHAPE);

    var a = msg.action;
    if (!isString(a.action_type))                 return reject(CODE.BAD_SHAPE);

    if (!inSet(a.action_type, VALID.ACTION)) {
      if (inSet(a.action_type, VALID.BLOCKED))   return reject(CODE.SENSITIVE);
      return reject(CODE.UNSUPPORTED);
    }
    if (!onlyKeys(a, ["action_type", "route_id", "target_id",
                      "explanation_id", "requires_user_confirmation", "choice_ids"]))
                                               return reject(CODE.BAD_SHAPE);

    // ---- HIGHLIGHT / SCROLL / CLICK ----
    if (a.action_type === "HIGHLIGHT_ALLOWLISTED_ELEMENT" ||
        a.action_type === "SCROLL_TO_ALLOWLISTED_ELEMENT" ||
        a.action_type === "CLICK_ALLOWLISTED_ELEMENT") {
      if (a.route_id !== null)                   return reject(CODE.BAD_SHAPE);
      if (!inSet(a.target_id, VALID.TARGET))    return reject(CODE.BAD_TARGET);
      if (a.requires_user_confirmation !== false) return reject(CODE.BAD_SHAPE);
      if (!Array.isArray(a.choice_ids) || a.choice_ids.length !== 0)
                                               return reject(CODE.BAD_SHAPE);
      var expMap = {
        HIGHLIGHT_ALLOWLISTED_ELEMENT: "highlight_element",
        SCROLL_TO_ALLOWLISTED_ELEMENT: "scroll_to_element",
        CLICK_ALLOWLISTED_ELEMENT: "click_element",
      };
      var out = baseAction(a);
      out.explanation_id = expMap[a.action_type];
      return ok(out);
    }

    // ---- OPEN ROUTE ----
    if (a.action_type === "OPEN_ALLOWLISTED_ROUTE") {
      if (!inSet(a.route_id, VALID.ROUTE))      return reject(CODE.BAD_ROUTE);
      if (a.target_id !== null)                  return reject(CODE.BAD_SHAPE);
      if (a.requires_user_confirmation !== false) return reject(CODE.BAD_SHAPE);
      if (!Array.isArray(a.choice_ids) || a.choice_ids.length !== 0)
                                               return reject(CODE.BAD_SHAPE);
      return ok(baseAction(a));
    }

    // ---- PREFILL ----
    if (a.action_type === "PREFILL_APPROVED_DRAFT") {
      if (a.target_id !== "complaint-body")     return reject(CODE.BAD_TARGET);
      if (a.route_id !== null)                  return reject(CODE.BAD_SHAPE);
      if ((a.explanation_id || "") !== "prefill_draft")
                                               return reject(CODE.BAD_SHAPE);
      if (a.requires_user_confirmation !== true) return reject(CODE.BAD_SHAPE);
      if (!Array.isArray(a.choice_ids) || a.choice_ids.length !== 0)
                                               return reject(CODE.BAD_SHAPE);
      var out2 = baseAction(a);
      out2.explanation_id = "prefill_draft";
      return ok(out2);
    }

    // ---- STOP ----
    if (a.action_type === "STOP_FOR_USER_CONFIRMATION") {
      if (a.route_id !== null && a.route_id !== "handoff-stop")
                                               return reject(CODE.BAD_ROUTE);
      if (a.target_id !== null)                  return reject(CODE.BAD_SHAPE);
      if ((a.explanation_id || "") !== "stop_for_confirmation")
                                               return reject(CODE.BAD_SHAPE);
      if (a.requires_user_confirmation !== true) return reject(CODE.BAD_SHAPE);
      if (!Array.isArray(a.choice_ids) || a.choice_ids.length !== 0)
                                               return reject(CODE.BAD_SHAPE);
      return ok(baseAction(a));
    }

    return reject(CODE.UNSUPPORTED);
  }

  return Object.freeze({
    validateActionMessage: validateActionMessage,
    isLocalFixtureLocation: isLocalFixtureLocation,
  });
}));