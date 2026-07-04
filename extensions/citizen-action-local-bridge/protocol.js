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

  /** Exact explanation_id mapping — accepted action types only. */
  var EXPLANATION_MAP = Object.freeze({
    HIGHLIGHT_ALLOWLISTED_ELEMENT: "highlight_element",
    SCROLL_TO_ALLOWLISTED_ELEMENT: "scroll_to_element",
    OPEN_ALLOWLISTED_ROUTE: "open_route",
    CLICK_ALLOWLISTED_ELEMENT: "click_element",
    PREFILL_APPROVED_DRAFT: "prefill_draft",
    STOP_FOR_USER_CONFIRMATION: "stop_for_confirmation",
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

  function onlyKeys(obj, allowed) {
    return Object.keys(obj).every(function (k) { return allowed.indexOf(k) !== -1; });
  }

  function reject(msg) { return { ok: false, reason_code: msg }; }

  // -----------------------------------------------------------------------
  // Location guard — protocol + hostname + pathname only; port unrestricted
  // -----------------------------------------------------------------------
  function isLocalFixtureLocation(loc) {
    if (!loc) return false;

    var protocol = "";
    var hostname = "";
    var pathname = "";

    if (isString(loc)) {
      try {
        var parsed = new URL(loc);
        protocol = parsed.protocol;
        hostname = parsed.hostname;
        pathname = parsed.pathname;
      } catch (e) {
        return false;
      }
    } else if (isObj(loc)) {
      // window.location-like object
      protocol = loc.protocol || "";
      hostname = loc.hostname || "";
      pathname = loc.pathname || "";

      // If protocol/hostname missing, try parsing from loc.origin (includes port)
      if ((!protocol || !hostname) && isString(loc.origin)) {
        try {
          var fromOrigin = new URL(loc.origin);
          protocol = protocol || fromOrigin.protocol;
          hostname = hostname || fromOrigin.hostname;
          pathname = pathname || fromOrigin.pathname;
        } catch (e2) {
          return false;
        }
      }
    } else {
      return false;
    }

    var validHosts = Object.freeze(["localhost", "127.0.0.1"]);
    var validPaths = Object.freeze([
      "/static/citizen-action-demo.html",
      "/citizen-action-demo.html",
    ]);

    return (
      protocol === "http:" &&
      validHosts.indexOf(hostname) !== -1 &&
      validPaths.indexOf(pathname) !== -1
    );
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

    // ---- Exact explanation_id validation for all accepted action types ----
    var expectedExp = EXPLANATION_MAP[a.action_type];
    if (!isString(a.explanation_id) || a.explanation_id !== expectedExp) {
      return reject(CODE.BAD_SHAPE);
    }

    // ---- HIGHLIGHT / SCROLL / CLICK ----
    if (a.action_type === "HIGHLIGHT_ALLOWLISTED_ELEMENT" ||
        a.action_type === "SCROLL_TO_ALLOWLISTED_ELEMENT" ||
        a.action_type === "CLICK_ALLOWLISTED_ELEMENT") {
      if (a.route_id !== null)                   return reject(CODE.BAD_SHAPE);
      if (!inSet(a.target_id, VALID.TARGET))    return reject(CODE.BAD_TARGET);
      if (a.requires_user_confirmation !== false) return reject(CODE.BAD_SHAPE);
      if (!Array.isArray(a.choice_ids) || a.choice_ids.length !== 0)
                                               return reject(CODE.BAD_SHAPE);
      return {
        ok: true,
        action: {
          action_type: a.action_type,
          route_id: null,
          target_id: a.target_id,
          explanation_id: expectedExp,
          requires_user_confirmation: false,
          choice_ids: [],
        },
      };
    }

    // ---- OPEN ROUTE ----
    if (a.action_type === "OPEN_ALLOWLISTED_ROUTE") {
      if (!inSet(a.route_id, VALID.ROUTE))      return reject(CODE.BAD_ROUTE);
      if (a.target_id !== null)                  return reject(CODE.BAD_SHAPE);
      if (a.requires_user_confirmation !== false) return reject(CODE.BAD_SHAPE);
      if (!Array.isArray(a.choice_ids) || a.choice_ids.length !== 0)
                                               return reject(CODE.BAD_SHAPE);
      return {
        ok: true,
        action: {
          action_type: a.action_type,
          route_id: a.route_id,
          target_id: null,
          explanation_id: expectedExp,
          requires_user_confirmation: false,
          choice_ids: [],
        },
      };
    }

    // ---- PREFILL ----
    if (a.action_type === "PREFILL_APPROVED_DRAFT") {
      if (a.target_id !== "complaint-body")     return reject(CODE.BAD_TARGET);
      if (a.route_id !== null)                  return reject(CODE.BAD_SHAPE);
      if (a.requires_user_confirmation !== true) return reject(CODE.BAD_SHAPE);
      if (!Array.isArray(a.choice_ids) || a.choice_ids.length !== 0)
                                               return reject(CODE.BAD_SHAPE);
      return {
        ok: true,
        action: {
          action_type: a.action_type,
          route_id: null,
          target_id: "complaint-body",
          explanation_id: expectedExp,
          requires_user_confirmation: true,
          choice_ids: [],
        },
      };
    }

    // ---- STOP ----
    if (a.action_type === "STOP_FOR_USER_CONFIRMATION") {
      if (a.route_id !== null && a.route_id !== "handoff-stop")
                                               return reject(CODE.BAD_ROUTE);
      if (a.target_id !== null)                  return reject(CODE.BAD_SHAPE);
      if (a.requires_user_confirmation !== true) return reject(CODE.BAD_SHAPE);
      if (!Array.isArray(a.choice_ids) || a.choice_ids.length !== 0)
                                               return reject(CODE.BAD_SHAPE);
      return {
        ok: true,
        action: {
          action_type: a.action_type,
          route_id: a.route_id,
          target_id: null,
          explanation_id: expectedExp,
          requires_user_confirmation: true,
          choice_ids: [],
        },
      };
    }

    return reject(CODE.UNSUPPORTED);
  }

  return Object.freeze({
    validateActionMessage: validateActionMessage,
    isLocalFixtureLocation: isLocalFixtureLocation,
  });
}));