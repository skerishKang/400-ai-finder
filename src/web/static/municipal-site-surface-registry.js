/*
 * Generic repository-clone surface registry (#1333 / #1328 Slice B).
 *
 * Data/config only. Shared shell/adapter code must resolve through this registry
 * instead of branching on raw institution ids.
 */
(function () {
  "use strict";

  var SITE_ID_RE = /^[a-z0-9][a-z0-9_]{2,63}$/;

  var SITES = Object.freeze({
    seogu_gwangju: Object.freeze({
      site_id: "seogu_gwangju",
      label: "광주광역시 서구청",
      clone_root: "/seogu/",
      readable_selector: "main.rc-main",
      max_evidence_chars: 6000,
      allowed_routes: Object.freeze([
        "",
        "notice/",
        "notice/detail/",
        "gosi/",
        "gosi/detail/",
        "civil-form/",
        "civil-form/detail/",
        "organization/",
        "staff/",
        "housing/",
        "passport-guidance/",
        "unmanned-kiosk/",
        "illegal-parking-report/",
        "streetlight-report-handoff/",
        "litter-report-handoff/",
        // #1363 Lane B: S7 mayor-proposal informational evidence route
        // (bounded capture of the official 주민제안 participation-method page).
        "mayor-proposal-guidance/",
        // #1364 Lane B: app-owned complaint-board/write surface routes.
        // These routes are NOT served by the clone iframe — they are rendered
        // by SeoguComplaintSurface inside #demo-canvas for S3/S4 complaint-
        // writing journeys after the evidence gate passes. Listed here so the
        // surface registry recognises them as legitimate Seo-gu routes.
        "complaint-board/",
        "complaint-write/",
        // #1363 Lane B: app-owned mayor-proposal writing surface routes
        // (Buk-gu mayor-complaint-write/receipt shape, #1375 pattern).
        "mayor-office-entry/",
        "mayor-office/",
        "mayor-complaint-write/",
        "mayor-complaint-receipt/",
        "home/gnb-open/",
        "home/mobile/",
      ]),
    }),
  });

  function _normalizeSiteId(value) {
    if (typeof value !== "string") return "";
    var text = value.trim();
    return SITE_ID_RE.test(text) ? text : "";
  }

  function resolve(siteId) {
    var normalized = _normalizeSiteId(siteId);
    if (!normalized) {
      return Object.freeze({
        ok: false,
        site_id: "",
        failure_code: "invalid_site_surface",
      });
    }
    var config = SITES[normalized];
    if (!config) {
      return Object.freeze({
        ok: false,
        site_id: normalized,
        failure_code: "unknown_site_surface",
      });
    }
    return Object.freeze({
      ok: true,
      site_id: config.site_id,
      config: config,
      failure_code: "",
    });
  }

  window.MunicipalSiteSurfaceRegistry = Object.freeze({
    resolve: resolve,
    supported_site_ids: Object.freeze(Object.keys(SITES)),
  });
})();
