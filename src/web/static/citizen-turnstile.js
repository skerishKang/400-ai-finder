/*
 * citizen-turnstile.js
 * Browser-side Turnstile token lifecycle for the MVP AI bridge (#1224-B).
 *
 * Security boundaries:
 * - fetches only the public site key/action from same-origin config
 * - never receives or stores the Turnstile secret
 * - obtains a fresh, single-use token for each protected ask
 * - never stores challenge tokens in localStorage/sessionStorage/cookies
 * - resets the widget after each protected request/cancel
 */
(function () {
  "use strict";

  var CONFIG_URL = "/api/mvp/turnstile-config";
  var SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
  var SCRIPT_MARKER = "data-citizen-turnstile-api";
  var WIDGET_ID = "citizen-turnstile-widget";
  var TOKEN_MAX_CHARS = 2048;

  var _configPromise = null;
  var _scriptPromise = null;
  var _container = null;
  var _widgetId = null;
  var _widgetExecuted = false;
  var _pending = null;

  function _abortError() {
    var error = new Error("TURNSTILE_ABORTED");
    error.name = "AbortError";
    return error;
  }

  function _clientError(code) {
    var error = new Error(code || "TURNSTILE_CLIENT_ERROR");
    error.code = code || "turnstile_client_error";
    return error;
  }

  function _safeToken(value) {
    var token = typeof value === "string" ? value.trim() : "";
    if (!token || token.length > TOKEN_MAX_CHARS || /\s/.test(token)) return "";
    return token;
  }

  function _safeAction(value) {
    var action = typeof value === "string" ? value.trim() : "";
    return /^[A-Za-z0-9_-]{1,32}$/.test(action) ? action : "";
  }

  function _safeSiteKey(value) {
    var key = typeof value === "string" ? value.trim() : "";
    return key && key.length <= 512 && !/\s/.test(key) ? key : "";
  }

  function _loadConfig() {
    if (_configPromise) return _configPromise;
    _configPromise = fetch(CONFIG_URL, {
      method: "GET",
      headers: { "Accept": "application/json" },
      cache: "no-store",
      credentials: "same-origin"
    }).then(function (response) {
      if (!response || !response.ok) throw _clientError("turnstile_config_unavailable");
      return response.json();
    }).then(function (data) {
      if (!data || data.ok !== true || typeof data.enabled !== "boolean") {
        throw _clientError("turnstile_config_invalid");
      }
      if (data.enabled === false) {
        return Object.freeze({ enabled: false, siteKey: "", action: _safeAction(data.action) || "mvp_ask" });
      }
      var siteKey = _safeSiteKey(data.site_key);
      var action = _safeAction(data.action);
      if (data.configured !== true || !siteKey || !action) {
        throw _clientError("turnstile_config_invalid");
      }
      return Object.freeze({ enabled: true, siteKey: siteKey, action: action });
    }).catch(function (error) {
      _configPromise = null;
      throw error;
    });
    return _configPromise;
  }

  function _loadScript() {
    if (window.turnstile && typeof window.turnstile.render === "function") {
      return Promise.resolve(window.turnstile);
    }
    if (_scriptPromise) return _scriptPromise;
    _scriptPromise = new Promise(function (resolve, reject) {
      if (!document || !document.head || typeof document.createElement !== "function") {
        reject(_clientError("turnstile_document_unavailable"));
        return;
      }
      var existing = document.querySelector
        ? document.querySelector('script[' + SCRIPT_MARKER + '="1"]')
        : null;
      var script = existing || document.createElement("script");
      var settled = false;
      function done(fn, value) {
        if (settled) return;
        settled = true;
        fn(value);
      }
      function onLoad() {
        if (window.turnstile && typeof window.turnstile.render === "function") {
          done(resolve, window.turnstile);
        } else {
          done(reject, _clientError("turnstile_api_unavailable"));
        }
      }
      function onError() {
        done(reject, _clientError("turnstile_script_failed"));
      }
      if (existing) {
        existing.addEventListener("load", onLoad, { once: true });
        existing.addEventListener("error", onError, { once: true });
        window.setTimeout(function () {
          if (window.turnstile && typeof window.turnstile.render === "function") onLoad();
        }, 0);
        return;
      }
      script.src = SCRIPT_URL;
      script.async = true;
      script.defer = true;
      script.setAttribute(SCRIPT_MARKER, "1");
      script.onload = onLoad;
      script.onerror = onError;
      document.head.appendChild(script);
    }).catch(function (error) {
      _scriptPromise = null;
      throw error;
    });
    return _scriptPromise;
  }

  function _ensureContainer() {
    if (_container && _container.parentNode) return _container;
    if (!document || typeof document.createElement !== "function") {
      throw _clientError("turnstile_document_unavailable");
    }
    var existing = document.getElementById ? document.getElementById(WIDGET_ID) : null;
    if (existing) {
      _container = existing;
      return _container;
    }
    var container = document.createElement("div");
    container.id = WIDGET_ID;
    container.className = "citizen-turnstile-widget";
    container.setAttribute("aria-label", "Security verification");
    var form = document.getElementById ? document.getElementById("chat-composer-form") : null;
    if (form && form.parentNode && typeof form.parentNode.insertBefore === "function") {
      form.parentNode.insertBefore(container, form);
    } else if (document.body && typeof document.body.appendChild === "function") {
      document.body.appendChild(container);
    } else {
      throw _clientError("turnstile_mount_unavailable");
    }
    _container = container;
    return container;
  }

  function _settlePending(kind, value) {
    var pending = _pending;
    if (!pending) return;
    _pending = null;
    if (pending.signal && pending.abortListener && typeof pending.signal.removeEventListener === "function") {
      pending.signal.removeEventListener("abort", pending.abortListener);
    }
    if (kind === "resolve") pending.resolve(value);
    else pending.reject(value);
  }

  function _ensureWidget(config) {
    if (_widgetId !== null && _widgetId !== undefined) return _widgetId;
    if (!window.turnstile || typeof window.turnstile.render !== "function") {
      throw _clientError("turnstile_api_unavailable");
    }
    var container = _ensureContainer();
    _widgetId = window.turnstile.render(container, {
      sitekey: config.siteKey,
      action: config.action,
      execution: "execute",
      appearance: "interaction-only",
      callback: function (token) {
        var safe = _safeToken(token);
        if (!safe) {
          _settlePending("reject", _clientError("turnstile_token_invalid"));
          return;
        }
        _widgetExecuted = true;
        _settlePending("resolve", safe);
      },
      "expired-callback": function () {
        _settlePending("reject", _clientError("turnstile_token_expired"));
      },
      "timeout-callback": function () {
        _settlePending("reject", _clientError("turnstile_interaction_timeout"));
      },
      "error-callback": function () {
        _settlePending("reject", _clientError("turnstile_challenge_error"));
        return true;
      }
    });
    if (_widgetId === null || _widgetId === undefined || _widgetId === "") {
      _widgetId = null;
      throw _clientError("turnstile_render_failed");
    }
    return _widgetId;
  }

  function _resetWidget() {
    if (_widgetId === null || _widgetId === undefined) return;
    if (!window.turnstile || typeof window.turnstile.reset !== "function") return;
    try {
      window.turnstile.reset(_widgetId);
      _widgetExecuted = false;
    } catch (_) {
      // A future acquire will fail closed if the widget cannot execute again.
    }
  }

  function acquireToken(options) {
    options = options || {};
    var signal = options.signal || null;
    return _loadConfig().then(function (config) {
      if (!config.enabled) return "";
      return _loadScript().then(function () {
        var widgetId = _ensureWidget(config);
        if (signal && signal.aborted) throw _abortError();
        if (_pending) {
          _settlePending("reject", _abortError());
        }
        if (_widgetExecuted) _resetWidget();
        return new Promise(function (resolve, reject) {
          var abortListener = function () {
            _settlePending("reject", _abortError());
            _resetWidget();
          };
          _pending = {
            resolve: resolve,
            reject: reject,
            signal: signal,
            abortListener: abortListener
          };
          if (signal && typeof signal.addEventListener === "function") {
            signal.addEventListener("abort", abortListener, { once: true });
          }
          try {
            window.turnstile.execute(widgetId);
          } catch (_) {
            _settlePending("reject", _clientError("turnstile_execute_failed"));
          }
        });
      });
    });
  }

  function reset() {
    if (_pending) _settlePending("reject", _abortError());
    _resetWidget();
  }

  function cancel() {
    reset();
  }

  window.CitizenTurnstile = Object.freeze({
    acquireToken: acquireToken,
    reset: reset,
    cancel: cancel,
    CONFIG_URL: CONFIG_URL,
    SCRIPT_URL: SCRIPT_URL
  });
})();
