/*
 * citizen-sitespec-metadata.js
 * Checked-in browser-side projection of the canonical SiteSpec display
 * identity for the citizen UI (#1225-D3).
 *
 * AUTHORITATIVE SOURCE: configs/sites/bukgu_gwangju.sitespec.json
 * This file is a checked-in projection for the browser citizen UI ONLY.
 * It is NOT an authoritative source. Do not edit it as the source of truth —
 * edit the SiteSpec and update this projection. The drift contract in
 * tests/test_citizen_sitespec_parity.py fails CI if the two diverge.
 *
 * Synchronous + offline: classic script, no fetch / XHR / modules / dynamic
 * import. Loaded before citizen-i18n.js so the citizen shell can read it
 * synchronously at load time.
 *
 * Locale fallback rule: vi / th / id have no SiteSpec locale institution
 * label, so their derived names deterministically fall back to the approved
 * English display label "Gwangju Buk-gu". No new translations are invented
 * here.
 */

(function () {
  "use strict";

  var INSTITUTION = Object.freeze({
    default_label: "북구청",
    locale_labels: Object.freeze({
      ko: "북구청",
      en: "Gwangju Buk-gu",
    }),
    // Derived per-locale resident-facing current institution name. ko uses
    // display.default_label; en uses display.locale_labels.en; vi/th/id have
    // no SiteSpec locale label and deterministically use the en label.
    names: Object.freeze({
      ko: "북구청",
      en: "Gwangju Buk-gu",
      vi: "Gwangju Buk-gu",
      th: "Gwangju Buk-gu",
      id: "Gwangju Buk-gu",
    }),
  });

  window.CitizenSiteSpecMetadata = Object.freeze({
    site_id: "bukgu_gwangju",
    schema_version: "1.0.0",
    display: INSTITUTION,
  });
})();
