/*
 * citizen-mvp-bridge.js
 * MVP model-action bridge for the first-use local demo (#925 / #927).
 *
 * The legacy `ask()` path posts to /api/mvp/ask and preserves its existing
 * normalized response shape. #1337 adds a separate explicit
 * `askGeneralModel()` path to /api/mvp/general so model-only provenance cannot
 * be confused with the site-grounded contract.
 *
 * Guarantees:
 * - one in-flight request at a time (superseding previous requests)
 * - abortable via cancel()
 * - never throws to the caller
 * - optional explicit site_id transport; legacy callers that omit it keep the
 *   prior request/response shape
 */

(function () {
  "use strict";

  var SUPPORTED_LOCALES = ["ko", "en", "vi", "th", "id"];

  function _localizedFailAnswer() {
    if (window.CitizenI18n && typeof window.CitizenI18n.t === "function") {
      var v = window.CitizenI18n.t("error.aiUnavailable");
      if (v && v !== "error.aiUnavailable") return v;
    }
    return "현재 AI 안내를 연결하지 못했습니다.";
  }

  var MVP_FAILURE_ANSWER = "현재 AI 안내를 연결하지 못했습니다.";
  var _controller = null;
  var SESSION_STORAGE_KEY = "citizen_mvp_anonymous_session_id";
  var _sessionIdMemory = "";

  function _safeSessionId(value) {
    var text = typeof value === "string" ? value.trim() : "";
    return /^[A-Za-z0-9_-]{16,128}$/.test(text) ? text : "";
  }

  function _safeSiteId(value) {
    var text = typeof value === "string" ? value.trim() : "";
    return /^[a-z0-9][a-z0-9_]{2,63}$/.test(text) ? text : "";
  }

  function _generateSessionId() {
    var cryptoObj = window.crypto;
    if (cryptoObj && typeof cryptoObj.randomUUID === "function") {
      var uuid = _safeSessionId(cryptoObj.randomUUID());
      if (uuid) return uuid;
    }
    if (cryptoObj && typeof cryptoObj.getRandomValues === "function") {
      var bytes = new Uint8Array(16);
      cryptoObj.getRandomValues(bytes);
      return "sid_" + Array.prototype.map.call(bytes, function (value) {
        return value.toString(16).padStart(2, "0");
      }).join("");
    }
    return ("sid_" + Date.now().toString(36) + "_" +
      Math.random().toString(36).slice(2).padEnd(24, "0")).slice(0, 128);
  }

  function _anonymousSessionId() {
    var memoryId = _safeSessionId(_sessionIdMemory);
    if (memoryId) return memoryId;
    try {
      if (window.sessionStorage && typeof window.sessionStorage.getItem === "function") {
        var stored = _safeSessionId(window.sessionStorage.getItem(SESSION_STORAGE_KEY));
        if (stored) {
          _sessionIdMemory = stored;
          return stored;
        }
      }
    } catch (_) {
      // Storage can be unavailable in privacy modes; use page-lifetime memory.
    }
    var generated = _safeSessionId(_generateSessionId());
    if (!generated) generated = "sid_fallback_0000000000000000";
    _sessionIdMemory = generated;
    try {
      if (window.sessionStorage && typeof window.sessionStorage.setItem === "function") {
        window.sessionStorage.setItem(SESSION_STORAGE_KEY, generated);
      }
    } catch (_) {
      // Page-lifetime memory remains the fallback; never use localStorage.
    }
    return generated;
  }

  function _safeRequestId(value) {
    var text = typeof value === "string" ? value.trim() : "";
    return /^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/.test(text) ? text : "";
  }

  function _safeSchemaVersion(value) {
    var text = typeof value === "string" ? value.trim() : "";
    return /^[0-9]+\.[0-9]+(?:\.[0-9]+)?$/.test(text) ? text : "";
  }

  function _responseHeaderRequestId(resp) {
    if (!resp || !resp.headers || typeof resp.headers.get !== "function") return "";
    return _safeRequestId(resp.headers.get("X-Request-ID"));
  }

  function _resolveResponseIdentity(headerRequestId, data) {
    var headerId = _safeRequestId(headerRequestId);
    var bodyId = _safeRequestId(data && data.request_id);
    var requestId = "";
    if (headerId && bodyId) {
      requestId = headerId === bodyId ? headerId : "";
    } else {
      requestId = headerId || bodyId;
    }
    return {
      request_id: requestId,
      schema_version: _safeSchemaVersion(data && data.schema_version),
    };
  }

  function _stableFailure(identity) {
    var safeIdentity = identity && typeof identity === "object" ? identity : {};
    return {
      ok: false,
      answer: _localizedFailAnswer(),
      action: "none",
      confidence: 0.0,
      provider: "",
      model: "",
      quest: null,
      action_plan: null,
      current_time: "",
      retrieved_at: "",
      freshness_state: "unavailable",
      source_url: "",
      sources: [],
      captured_at: "",
      verified_at: "",
      official_route_id: "",
      official_page_id: "",
      snapshot_id: "",
      canonical_sha256: "",
      request_id: _safeRequestId(safeIdentity.request_id),
      schema_version: _safeSchemaVersion(safeIdentity.schema_version),
    };
  }

  function _stableGeneralFailure(identity, answer) {
    var safeIdentity = identity && typeof identity === "object" ? identity : {};
    return {
      ok: false,
      answer: typeof answer === "string" && answer.trim() ? answer : _localizedFailAnswer(),
      action: "none",
      confidence: 0.0,
      provider: "",
      model: "",
      grounded: false,
      source_kind: "general_model",
      evidence_kind: "none",
      answer_scope: "general_model",
      freshness_state: "unavailable",
      source_url: "",
      sources: [],
      search_queries: [],
      site_id: "",
      failure_code: "",
      request_id: _safeRequestId(safeIdentity.request_id),
      schema_version: _safeSchemaVersion(safeIdentity.schema_version),
    };
  }

  function _captureLocale() {
    if (window.CitizenI18n && typeof window.CitizenI18n.getLocale === "function") {
      var loc = window.CitizenI18n.getLocale();
      if (SUPPORTED_LOCALES.indexOf(loc) !== -1) return loc;
    }
    if (window.CitizenI18n && typeof window.CitizenI18n.normalizeLocale === "function") {
      return window.CitizenI18n.normalizeLocale(loc);
    }
    return "ko";
  }

  function _startRequest() {
    if (_controller) _controller.abort();
    var controller = ("AbortController" in window) ? new AbortController() : null;
    _controller = controller;
    return controller;
  }

  function _finishController(controller, result, fallback) {
    if (_controller === controller) _controller = null;
    return result || fallback();
  }

  function ask(question, options) {
    var controller = _startRequest();
    var requestLocale = _captureLocale();
    var sessionId = _anonymousSessionId();
    var requestedSiteId = _safeSiteId(options && options.site_id);
    var requestBody = {
      question: question || "",
      locale: requestLocale,
      session_id: sessionId,
    };
    if (requestedSiteId) requestBody.site_id = requestedSiteId;

    var fetchOpts = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    };
    if (controller) fetchOpts.signal = controller.signal;

    return fetch("/api/mvp/ask", fetchOpts)
      .then(function (resp) {
        var headerRequestId = _responseHeaderRequestId(resp);
        return resp.json().then(function (data) {
          var identity = _resolveResponseIdentity(headerRequestId, data);
          if (!resp.ok) return _stableFailure(identity);
          return {
            ok: data && data.ok !== false,
            answer: data ? data.answer : _localizedFailAnswer(),
            action: data ? data.action : "none",
            confidence: data ? data.confidence : 0.0,
            provider: data ? data.provider : "",
            model: data ? data.model : "",
            quest: data && data.quest ? data.quest : null,
            action_plan: data && data.action_plan ? data.action_plan : null,
            current_time: data && typeof data.current_time === "string" ? data.current_time : "",
            retrieved_at: data && typeof data.retrieved_at === "string" ? data.retrieved_at : "",
            freshness_state: data && typeof data.freshness_state === "string" ? data.freshness_state : "",
            source_url: data && typeof data.source_url === "string" ? data.source_url : "",
            sources: data && Array.isArray(data.sources) ? data.sources : [],
            captured_at: data && typeof data.captured_at === "string" ? data.captured_at : "",
            verified_at: data && typeof data.verified_at === "string" ? data.verified_at : "",
            official_route_id: data && typeof data.official_route_id === "string" ? data.official_route_id : "",
            official_page_id: data && typeof data.official_page_id === "string" ? data.official_page_id : "",
            snapshot_id: data && typeof data.snapshot_id === "string" ? data.snapshot_id : "",
            canonical_sha256: data && typeof data.canonical_sha256 === "string" ? data.canonical_sha256 : "",
            request_id: identity.request_id,
            schema_version: identity.schema_version,
          };
        }, function () {
          return _stableFailure({ request_id: headerRequestId, schema_version: "" });
        });
      })
      .catch(function () { return _stableFailure(); })
      .then(
        function (result) { return _finishController(controller, result, _stableFailure); },
        function () { return _finishController(controller, null, _stableFailure); },
      );
  }

  function askGeneralModel(question, options) {
    var controller = _startRequest();
    var requestLocale = _captureLocale();
    var sessionId = _anonymousSessionId();
    var requestedSiteId = _safeSiteId(options && options.site_id);
    var requestBody = {
      question: question || "",
      locale: requestLocale,
      session_id: sessionId,
    };
    if (requestedSiteId) requestBody.site_id = requestedSiteId;

    var fetchOpts = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    };
    if (controller) fetchOpts.signal = controller.signal;

    return fetch("/api/mvp/general", fetchOpts)
      .then(function (resp) {
        var headerRequestId = _responseHeaderRequestId(resp);
        return resp.json().then(function (data) {
          var identity = _resolveResponseIdentity(headerRequestId, data);
          if (!resp.ok || !data || typeof data !== "object") {
            return _stableGeneralFailure(identity);
          }
          var exactProvenance =
            data.grounded === false &&
            data.source_kind === "general_model" &&
            data.evidence_kind === "none" &&
            data.answer_scope === "general_model" &&
            Array.isArray(data.sources) && data.sources.length === 0 &&
            (typeof data.source_url !== "string" || data.source_url === "");
          if (data.ok === true && !exactProvenance) {
            return _stableGeneralFailure(identity, "일반 AI 답변의 출처 구분을 확인하지 못해 표시하지 않습니다.");
          }
          return {
            ok: data.ok === true,
            answer: typeof data.answer === "string" ? data.answer : _localizedFailAnswer(),
            action: "none",
            confidence: typeof data.confidence === "number" ? data.confidence : 0.0,
            provider: typeof data.provider === "string" ? data.provider : "",
            model: typeof data.model === "string" ? data.model : "",
            grounded: false,
            source_kind: "general_model",
            evidence_kind: "none",
            answer_scope: "general_model",
            freshness_state: typeof data.freshness_state === "string" ? data.freshness_state : "unavailable",
            source_url: "",
            sources: [],
            search_queries: [],
            site_id: typeof data.site_id === "string" ? data.site_id : "",
            failure_code: typeof data.failure_code === "string" ? data.failure_code : "",
            request_id: identity.request_id,
            schema_version: identity.schema_version,
          };
        }, function () {
          return _stableGeneralFailure({ request_id: headerRequestId, schema_version: "" });
        });
      })
      .catch(function () { return _stableGeneralFailure(); })
      .then(
        function (result) { return _finishController(controller, result, _stableGeneralFailure); },
        function () { return _finishController(controller, null, _stableGeneralFailure); },
      );
  }

  function cancel() {
    if (_controller) {
      try { _controller.abort(); } catch (_) { /* noop */ }
      _controller = null;
    }
  }

  window.CitizenMvpBridge = Object.freeze({
    ask: ask,
    askGeneralModel: askGeneralModel,
    cancel: cancel,
    FAILURE_ANSWER: MVP_FAILURE_ANSWER,
  });
})();
