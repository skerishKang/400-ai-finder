// Shared site-aware MVP runtime identity + fail-closed dispatch seam (#1331, Slice A).
//
// This is the Cloudflare-side mirror of src/llm/site_aware_mvp_dispatch.py. The
// status vocabulary below is mirrored 1:1 with the Python module; the Python web
// handler and this Function MUST agree on these semantics.
//
// This is the ONLY place that enumerates site runtime identity for the Cloudflare
// runtime. Shared code must branch on the resolved status
// (configured / recognized_unconfigured / unknown), never on raw site-id strings.
//
// Resolution rules (must match the Python resolver exactly):
//   - omitted / empty / null / non-string -> default resident runtime (Buk-gu)
//   - well-formed but unrecognized     -> unknown (fail closed, never Buk-gu)
//   - malformed (non-empty, bad shape) -> unknown (fail closed)
//   - recognized, not configured       -> recognized_unconfigured (no execution)
//   - configured                       -> configured (Buk-gu runtime may run)

export const SITE_RUNTIME_CONFIGURED = 'configured';
export const SITE_RUNTIME_RECOGNIZED_UNCONFIGURED = 'recognized_unconfigured';
export const SITE_RUNTIME_UNKNOWN = 'unknown';

export const SUPPORTED_SITE_RUNTIMES = Object.freeze({
  bukgu_gwangju: SITE_RUNTIME_CONFIGURED,
  seogu_gwangju: SITE_RUNTIME_RECOGNIZED_UNCONFIGURED,
});

export const DEFAULT_SITE_ID = 'bukgu_gwangju';

// Closed site-dispatch failure codes. Kept deliberately distinct from the
// provider/model failure_code vocabulary in ask.js / openai_compatible_provider.
export const SITE_FAILURE_UNKNOWN = 'unknown_site';
export const SITE_FAILURE_UNCONFIGURED = 'site_unconfigured_for_slice';

// Site id shape: lowercase letters/digits/underscore, 3..64 chars. Mirrors the
// Python SITE_ID_PATTERN so both runtimes agree on a well-formed site id.
export const SITE_ID_PATTERN = /^[a-z0-9_]{3,64}$/;

export function is_valid_site_id_format(siteId) {
  return typeof siteId === 'string' && SITE_ID_PATTERN.test(siteId);
}

export function resolveSiteRuntime(siteId) {
  // omitted / empty / null / non-string -> default resident runtime (Buk-gu)
  if (siteId === null || siteId === undefined || typeof siteId !== 'string' || siteId.trim() === '') {
    return { siteId: DEFAULT_SITE_ID, status: SITE_RUNTIME_CONFIGURED };
  }
  const resolved = siteId.trim();
  // Malformed identity fails closed instead of defaulting to Buk-gu. This keeps
  // the fail-closed guarantee even if a caller passes a garbage non-empty id.
  if (!is_valid_site_id_format(resolved)) {
    return { siteId: resolved, status: SITE_RUNTIME_UNKNOWN };
  }
  const status = SUPPORTED_SITE_RUNTIMES[resolved];
  if (!status) {
    // Well-formed but unrecognized -> fail closed (never Buk-gu).
    return { siteId: resolved, status: SITE_RUNTIME_UNKNOWN };
  }
  return { siteId: resolved, status };
}
