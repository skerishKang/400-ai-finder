/**
 * Clone renderer approval gate (#1198).
 *
 * Fail-closed selection for resident-default promotion.
 * Registry data lives in clone-renderer-approval-registry.js (loaded first).
 * Preview/debug query never grants approval and never bypasses registry rules
 * for ordinary default selection.
 */
(function (root) {
  "use strict";

  var APPROVED_HOME_RENDERER_ID = "bukgu_gwangju.home.designed.approved";
  var FIXTURE_HOME_RENDERER_ID = "bukgu_gwangju.home.fixture.candidate";

  var FORBIDDEN_SELECTION_PARAMS = [
    "renderer",
    "renderer-id",
    "renderer_id",
    "home-renderer",
    "home_renderer",
    "approval-state",
    "approval_state",
    "resident-default",
    "resident_default",
    "visual-review-state",
    "visual_review_state",
  ];

  function _asObject(value) {
    return value && typeof value === "object" ? value : null;
  }

  function _parseSearch(search) {
    var s = search == null ? "" : String(search);
    if (s.charAt(0) === "?") s = s.slice(1);
    try {
      return new URLSearchParams(s);
    } catch (_e) {
      return null;
    }
  }

  function wantsHomeFixtureProjection(search) {
    var params = _parseSearch(search);
    if (!params) return false;
    return (
      params.get("home-fixture") === "1" ||
      params.get("home-projection") === "fixture"
    );
  }

  function hasForbiddenRendererSelectionQuery(search) {
    var params = _parseSearch(search);
    if (!params) return false;
    for (var i = 0; i < FORBIDDEN_SELECTION_PARAMS.length; i++) {
      var key = FORBIDDEN_SELECTION_PARAMS[i];
      if (params.has(key) && params.get(key) !== null && params.get(key) !== "") {
        return true;
      }
    }
    return false;
  }

  function validateRegistry(registry) {
    if (!_asObject(registry)) {
      return { ok: false, reason: "registry_missing" };
    }
    if (registry.schema_version !== 1) {
      return { ok: false, reason: "registry_schema_invalid" };
    }
    if (registry.registry_kind !== "clone_renderer_approval_registry") {
      return { ok: false, reason: "registry_kind_invalid" };
    }
    if (!_asObject(registry.routes)) {
      return { ok: false, reason: "registry_routes_missing" };
    }
    return { ok: true };
  }

  function getRouteEntry(registry, routeId) {
    var validated = validateRegistry(registry);
    if (!validated.ok) return null;
    var route = registry.routes[routeId];
    return _asObject(route) ? route : null;
  }

  function getRendererEntry(registry, routeId, rendererId) {
    var route = getRouteEntry(registry, routeId);
    if (!route || !_asObject(route.renderers)) return null;
    var entry = route.renderers[rendererId];
    return _asObject(entry) ? entry : null;
  }

  function _requiredApprovedFieldsPresent(entry) {
    if (!entry) return false;
    if (entry.renderer_id !== APPROVED_HOME_RENDERER_ID) return false;
    if (entry.site_id !== "bukgu_gwangju") return false;
    if (entry.route_id !== "home") return false;
    if (entry.renderer_symbol !== "_renderApprovedHome") return false;
    if (
      entry.renderer_source_path !==
      "src/web/static/citizen-action-demo-canvas.js"
    ) {
      return false;
    }
    if (entry.approval_state !== "resident_default_approved") return false;
    if (entry.visual_review_state !== "visual_review_approved") return false;
    if (entry.resident_default_approved !== true) return false;
    if (entry.preview_only === true) return false;
    // Pinned designed-home identity is not an exact-clone claim.
    if (entry.exact !== false) return false;

    var prov = _asObject(entry.approval_provenance);
    if (!prov) return false;
    if (prov.issue !== "#1197") return false;
    if (prov.pull_request !== "#1200") return false;
    if (
      prov.approved_source_commit !==
      "87db3e1ce7d01646a8fc0e8eed6ce2fc63b7ebaa"
    ) {
      return false;
    }

    var integrity = _asObject(entry.renderer_integrity);
    if (!integrity) return false;
    if (integrity.algorithm !== "sha256") return false;
    if (integrity.extraction !== "marker_boundary") return false;
    if (
      typeof integrity.sha256 !== "string" ||
      !/^[a-f0-9]{64}$/.test(integrity.sha256)
    ) {
      return false;
    }
    if (
      integrity.marker_begin !== "CLONE_APPROVED_HOME_RENDERER_BEGIN" ||
      integrity.marker_end !== "CLONE_APPROVED_HOME_RENDERER_END"
    ) {
      return false;
    }
    return true;
  }

  function isResidentDefaultEligible(entry) {
    if (!_asObject(entry)) return false;
    if (entry.resident_default_approved !== true) return false;
    if (entry.visual_review_state !== "visual_review_approved") return false;
    if (entry.approval_state !== "resident_default_approved") return false;
    if (entry.visual_review_state === "visual_review_pending") return false;
    if (entry.visual_review_state === "visual_review_rejected") return false;
    if (entry.preview_only === true) return false;
    if (entry.exact === true && entry.capture_state === "capture_required") {
      return false;
    }
    return _requiredApprovedFieldsPresent(entry);
  }

  /**
   * Resolve home renderer selection.
   *
   * Returns:
   *   { mode: "approved_default", renderer_id, entry }
   *   { mode: "fixture_preview", renderer_id, entry|null, preview_only: true }
   *   { mode: "unavailable", reason }
   *
   * Never falls back to fixture for ordinary routes.
   * Never selects first registry entry, query-supplied renderer, or unknown id.
   */
  function resolveHomeSelection(options) {
    options = options || {};
    var search = options.search;
    if (search == null && typeof root !== "undefined" && root.location) {
      search = root.location.search || "";
    }
    search = search == null ? "" : String(search);
    var registry =
      options.registry !== undefined
        ? options.registry
        : root.__CLONE_RENDERER_APPROVAL_REGISTRY__;

    var fixturePreview = wantsHomeFixtureProjection(search);

    // Arbitrary renderer selection query is never honored for ordinary default.
    // For fixture preview, forbidden selection params still cannot promote to
    // resident default; fixture preview remains preview-only.
    if (!fixturePreview && hasForbiddenRendererSelectionQuery(search)) {
      return {
        mode: "unavailable",
        reason: "arbitrary_renderer_query_forbidden",
      };
    }

    if (fixturePreview) {
      var fixtureRoute = getRouteEntry(registry, "home");
      var fixtureEntry = getRendererEntry(
        registry,
        "home",
        FIXTURE_HOME_RENDERER_ID
      );
      // Fixture preview is independent of resident-default approval eligibility.
      // Registry metadata annotates preview-only/pending when present; missing
      // registry does not invent approval, and still allows explicit preview.
      return {
        mode: "fixture_preview",
        renderer_id: FIXTURE_HOME_RENDERER_ID,
        entry: fixtureEntry,
        route: fixtureRoute,
        preview_only: true,
        visual_review_state:
          fixtureEntry && fixtureEntry.visual_review_state
            ? fixtureEntry.visual_review_state
            : "visual_review_pending",
        resident_default_approved: false,
      };
    }

    var validated = validateRegistry(registry);
    if (!validated.ok) {
      return { mode: "unavailable", reason: validated.reason };
    }

    var route = getRouteEntry(registry, "home");
    if (!route) {
      return { mode: "unavailable", reason: "route_approval_entry_missing" };
    }

    var approvedId = route.resident_default_renderer_id;
    if (!approvedId || typeof approvedId !== "string") {
      return {
        mode: "unavailable",
        reason: "resident_default_renderer_id_missing",
      };
    }

    if (approvedId !== APPROVED_HOME_RENDERER_ID) {
      return {
        mode: "unavailable",
        reason: "approved_renderer_id_mismatch",
      };
    }

    if (!_asObject(route.renderers) || !route.renderers[approvedId]) {
      return { mode: "unavailable", reason: "approved_renderer_id_unknown" };
    }

    var entry = route.renderers[approvedId];
    if (!_asObject(entry)) {
      return { mode: "unavailable", reason: "approved_renderer_entry_invalid" };
    }

    if (entry.visual_review_state === "visual_review_pending") {
      return { mode: "unavailable", reason: "visual_review_pending" };
    }
    if (entry.visual_review_state === "visual_review_rejected") {
      return { mode: "unavailable", reason: "visual_review_rejected" };
    }
    if (entry.resident_default_approved !== true) {
      return {
        mode: "unavailable",
        reason: "resident_default_not_approved",
      };
    }
    if (!_requiredApprovedFieldsPresent(entry)) {
      return {
        mode: "unavailable",
        reason: "approval_provenance_or_identity_missing",
      };
    }
    if (!isResidentDefaultEligible(entry)) {
      return {
        mode: "unavailable",
        reason: "renderer_not_resident_default_eligible",
      };
    }

    return {
      mode: "approved_default",
      renderer_id: APPROVED_HOME_RENDERER_ID,
      entry: entry,
      route: route,
      preview_only: false,
      visual_review_state: "visual_review_approved",
      resident_default_approved: true,
    };
  }

  root.CloneRendererApprovalGate = Object.freeze({
    APPROVED_HOME_RENDERER_ID: APPROVED_HOME_RENDERER_ID,
    FIXTURE_HOME_RENDERER_ID: FIXTURE_HOME_RENDERER_ID,
    wantsHomeFixtureProjection: wantsHomeFixtureProjection,
    hasForbiddenRendererSelectionQuery: hasForbiddenRendererSelectionQuery,
    validateRegistry: validateRegistry,
    getRouteEntry: getRouteEntry,
    getRendererEntry: getRendererEntry,
    isResidentDefaultEligible: isResidentDefaultEligible,
    resolveHomeSelection: resolveHomeSelection,
  });
})(typeof window !== "undefined" ? window : globalThis);
