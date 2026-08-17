/*
 * Same-origin repository-clone surface + bounded READ/action evidence seam
 * (#1333 / #1335 / #1328).
 *
 * This adapter never fetches data. It can only navigate to configured local
 * clone routes, activate one captured local detail link under strict guards,
 * and read resident-visible text from one configured semantic content root
 * inside the same-origin iframe.
 */
(function () {
  "use strict";

  var CAPTURED_DETAIL_SELECTOR = "a.rc-list-link[data-detail='1']";

  function _stableFailure(code, siteId) {
    return Object.freeze({
      ok: false,
      grounded: false,
      evidence_kind: "clone_dom",
      source_kind: "repository_clone",
      site_id: siteId || "",
      route: "",
      title: "",
      text: "",
      truncated: false,
      failure_code: code || "clone_evidence_unavailable",
    });
  }

  function _normalizeVisibleText(value) {
    return String(value || "")
      .replace(/\r\n?/g, "\n")
      .replace(/[\t\f\v ]+/g, " ")
      .replace(/ *\n */g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function _normalizeRoute(value) {
    if (typeof value !== "string") return null;
    var route = value.trim().replace(/^\/+/, "");
    if (!route) return "";
    if (route.indexOf("?") !== -1 || route.indexOf("#") !== -1 || route.indexOf("\\") !== -1) {
      return null;
    }
    if (route.split("/").some(function (part) { return part === "." || part === ".."; })) {
      return null;
    }
    if (!/^[a-z0-9][a-z0-9\-/]*\/?$/.test(route)) return null;
    return route.endsWith("/") ? route : route + "/";
  }

  function create(options) {
    options = options && typeof options === "object" ? options : {};
    var iframe = options.iframe;
    var config = options.config;
    if (!iframe || !config || typeof config !== "object") {
      throw new Error("MunicipalCloneSurface requires iframe + site config");
    }

    var siteId = String(config.site_id || "");
    var cloneRoot = String(config.clone_root || "");
    var readableSelector = String(config.readable_selector || "");
    var maxChars = Number(config.max_evidence_chars || 0);
    var allowedRoutes = Array.isArray(config.allowed_routes)
      ? config.allowed_routes.slice()
      : [];
    var allowedRouteSet = new Set(allowedRoutes);

    if (!siteId || !cloneRoot.startsWith("/") || !cloneRoot.endsWith("/")) {
      throw new Error("invalid clone surface config");
    }
    if (!readableSelector || !Number.isSafeInteger(maxChars) || maxChars < 256 || maxChars > 20000) {
      throw new Error("invalid clone evidence config");
    }

    function _currentUrl() {
      try {
        var href = iframe.contentWindow && iframe.contentWindow.location
          ? iframe.contentWindow.location.href
          : "";
        if (!href) return null;
        var parsed = new URL(href, window.location.href);
        if (parsed.origin !== window.location.origin) return null;
        if (!parsed.pathname.startsWith(cloneRoot)) return null;
        if (parsed.search || parsed.hash) return null;
        return parsed;
      } catch (_) {
        return null;
      }
    }

    function currentRoute() {
      var parsed = _currentUrl();
      if (!parsed) return null;
      var route = parsed.pathname.slice(cloneRoot.length);
      route = _normalizeRoute(route);
      if (route === null || !allowedRouteSet.has(route)) return null;
      return route;
    }

    function navigate(route) {
      var normalized = _normalizeRoute(route);
      if (normalized === null || !allowedRouteSet.has(normalized)) {
        return false;
      }
      var target = new URL(cloneRoot + normalized, window.location.origin);
      if (target.origin !== window.location.origin || !target.pathname.startsWith(cloneRoot)) {
        return false;
      }
      iframe.src = target.pathname;
      return true;
    }

    function activateCapturedDetail(expectedRoute) {
      var current = _currentUrl();
      var currentRouteValue = currentRoute();
      var normalizedExpected = _normalizeRoute(expectedRoute);
      if (!current || currentRouteValue === null || normalizedExpected === null) return false;
      if (!allowedRouteSet.has(normalizedExpected)) return false;

      var doc;
      try {
        doc = iframe.contentDocument;
      } catch (_) {
        return false;
      }
      if (!doc) return false;

      var links = doc.querySelectorAll(CAPTURED_DETAIL_SELECTOR);
      if (links.length !== 1) return false;
      var link = links[0];
      if (!link || String(link.tagName || "").toUpperCase() !== "A") return false;
      if (link.hasAttribute("download")) return false;
      var targetAttr = String(link.getAttribute("target") || "").trim();
      if (targetAttr && targetAttr !== "_self") return false;

      var href = String(link.getAttribute("href") || "").trim();
      if (!href) return false;
      var target;
      try {
        target = new URL(href, current.href);
      } catch (_) {
        return false;
      }
      if (target.origin !== window.location.origin) return false;
      if (target.search || target.hash) return false;
      if (!target.pathname.startsWith(cloneRoot)) return false;
      if (target.pathname !== cloneRoot + normalizedExpected) return false;

      link.click();
      return true;
    }

    function readEvidence() {
      var route = currentRoute();
      if (route === null) return _stableFailure("clone_route_out_of_scope", siteId);

      var doc;
      try {
        doc = iframe.contentDocument;
      } catch (_) {
        return _stableFailure("clone_document_inaccessible", siteId);
      }
      if (!doc) return _stableFailure("clone_document_unavailable", siteId);

      var root = doc.querySelector(readableSelector);
      if (!root) return _stableFailure("clone_read_root_missing", siteId);

      // innerText is deliberate: hidden machine-readable JSON/scripts/styles and
      // form values are not part of resident-visible text. No storage/cookies or
      // arbitrary DOM serialization is read.
      var visible = _normalizeVisibleText(root.innerText || "");
      if (!visible) return _stableFailure("clone_visible_text_empty", siteId);

      var truncated = visible.length > maxChars;
      var text = truncated ? visible.slice(0, maxChars) : visible;
      var title = _normalizeVisibleText(doc.title || "").slice(0, 240);

      return Object.freeze({
        ok: true,
        grounded: true,
        evidence_kind: "clone_dom",
        source_kind: "repository_clone",
        site_id: siteId,
        route: route,
        title: title,
        text: text,
        truncated: truncated,
        failure_code: "",
      });
    }

    function _emitEvidence() {
      var detail = readEvidence();
      try {
        window.dispatchEvent(new CustomEvent("municipal-clone-evidence", { detail: detail }));
      } catch (_) {
        // Event delivery is convenience only; explicit readEvidence() remains authoritative.
      }
    }

    function onLoad() {
      _emitEvidence();
    }

    iframe.addEventListener("load", onLoad);

    return Object.freeze({
      site_id: siteId,
      clone_root: cloneRoot,
      navigate: navigate,
      activateCapturedDetail: activateCapturedDetail,
      currentRoute: currentRoute,
      readEvidence: readEvidence,
      refreshEvidence: _emitEvidence,
      destroy: function () {
        iframe.removeEventListener("load", onLoad);
      },
    });
  }

  window.MunicipalCloneSurface = Object.freeze({ create: create });
})();
