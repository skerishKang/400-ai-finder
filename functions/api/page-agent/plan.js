// ═════════════════════════════════════════════════════════════════════════
// functions/api/page-agent/plan.js
//
// Cloudflare Pages Function entry for Stage 4 Page Agent plan adapter.
//
//   Route : /api/page-agent/plan
//   Method: OPTIONS | POST
//
// Default state is DISABLED (PAGE_AGENT_MODEL_ENABLED unset/false).
// Browser query parameters cannot enable the adapter.
// No provider network calls are performed in Stage 4.
//
// Deterministic Page Agent mock mode under examples/page-agent/ remains
// the default offline/CI path and is not replaced by this endpoint.
// ═════════════════════════════════════════════════════════════════════════

import { onRequest } from './_adapter.js';

export { onRequest };
