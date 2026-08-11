// #1225-D2 — checked-in Cloudflare runtime projection of the canonical
// SiteSpec for Buk-gu (bukgu_gwangju).
//
// AUTHORITATIVE SOURCE: configs/sites/bukgu_gwangju.sitespec.json
// This file is a checked-in projection for Cloudflare runtime packaging
// ONLY. It is NOT an authoritative source. Do not edit it as the source of
// truth — edit the SiteSpec and update this projection. The drift contract
// in tests/functions/test_cloudflare_mvp_ask_contract.mjs fails CI if the
// two diverge.
//
// Every nested object/array is deep-frozen so runtime code cannot mutate
// projection state.

export const SITE_METADATA = Object.freeze({
  schema_version: '1.0.0',
  site_id: 'bukgu_gwangju',
  legacy_ids: Object.freeze(['bukgu']),
  jurisdiction: Object.freeze({
    canonical_name: '전남광주통합특별시 북구',
    short_name: '북구',
    effective_from: '2026-07-01',
    historical_aliases: Object.freeze([
      Object.freeze({
        value: '광주광역시 북구',
        effective_until: '2026-06-30',
      }),
    ]),
  }),
  display: Object.freeze({
    default_label: '북구청',
    locale_labels: Object.freeze({
      ko: '북구청',
      en: 'Gwangju Buk-gu',
    }),
  }),
  domains: Object.freeze({
    public: Object.freeze(['bukgu.gwangju.kr']),
  }),
  runtime: Object.freeze({
    python_profile: 'bukgu_gwangju',
    cloudflare_adapter: 'bukgu',
  }),
});

// NOTE: `clone.golden_commit` / `clone.golden_commit_subject` from the
// SiteSpec are intentionally NOT projected here: they describe Python-side
// official-clone provenance and are not consumed by the Cloudflare runtime.
// `search.bukgu.gwangju.kr` is a separate search-service endpoint, not a
// SiteSpec institution domain, and stays a code-owned runtime constant in
// ask.js (see SEARCH_SERVICE_DOMAIN).
