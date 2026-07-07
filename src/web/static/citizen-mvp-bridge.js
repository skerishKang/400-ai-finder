/*
 * citizen-mvp-bridge.js
 * MVP model-action bridge for the first-use local demo (#925 / #927).
 *
 * This file is loaded ONLY in MVP mode (?mvp=1) by citizen-first-use-shell.js.
 * It performs the single model-backed call to POST /api/mvp/ask and normalizes
 * the response into a stable contract. The default static flow never loads this
 * file, so the deterministic Stage 921 flow stays fetch-free.
 *
 * Guarantees:
 * - one in-flight request at a time (superseding previous requests)
 * - abortable via cancel()
 * - never throws to the caller; network/HTTP failures degrade to a stable
 *   { ok: false, action: "none", answer: "<honest ko message>" } envelope
 */

(function () {
  "use strict";

  var MVP_FAILURE_ANSWER = "현재 AI 안내를 연결하지 못했습니다.";
  var _controller = null;

  function _stableFailure() {
    return {
      ok: false,
      answer: MVP_FAILURE_ANSWER,
      action: "none",
      confidence: 0.0,
      provider: "",
      model: "",
    };
  }

  function ask(question) {
    if (_controller) {
      _controller.abort();
    }
    var controller = ("AbortController" in window) ? new AbortController() : null;
    _controller = controller;

    var fetchOpts = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question || "" }),
    };
    if (controller) {
      fetchOpts.signal = controller.signal;
    }

    return fetch("/api/mvp/ask", fetchOpts)
      .then(function (resp) {
        return resp.json().then(function (data) {
          if (!resp.ok) {
            return _stableFailure();
          }
          return {
            ok: data && data.ok !== false,
            answer: data ? data.answer : MVP_FAILURE_ANSWER,
            action: data ? data.action : "none",
            confidence: data ? data.confidence : 0.0,
            provider: data ? data.provider : "",
            model: data ? data.model : "",
          };
        }, function () {
          // JSON parse failure → treat as malformed model response.
          return _stableFailure();
        });
      })
      .catch(function () {
        // Network failure / abort → honest failure envelope.
        return _stableFailure();
      })
      .then(function (result) {
        if (_controller === controller) {
          _controller = null;
        }
        return result;
      }, function () {
        if (_controller === controller) {
          _controller = null;
        }
        return _stableFailure();
      });
  }

  function cancel() {
    if (_controller) {
      try { _controller.abort(); } catch (_) { /* noop */ }
      _controller = null;
    }
  }

  window.CitizenMvpBridge = Object.freeze({
    ask: ask,
    cancel: cancel,
    FAILURE_ANSWER: MVP_FAILURE_ANSWER,
  });
})();
