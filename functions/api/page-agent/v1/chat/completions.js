// ═════════════════════════════════════════════════════════════════════════
// functions/api/page-agent/v1/chat/completions.js
//
// Cloudflare Pages Function entry for the Stage 4 Page Agent
// server-side model adapter.
//
//   Route : /api/page-agent/v1/chat/completions
//   Method: OPTIONS (preflight) | POST (chat completion)
//
// This file is intentionally tiny: all policy + validation + provider
// orchestration lives in the sibling `_adapter.js` / `_policy.js` modules so
// they can be unit-tested in isolation under Node without a Workers
// runtime. The adapter never receives a provider key from the browser and
// never proxies the raw inbound payload.
// ═════════════════════════════════════════════════════════════════════════

import { onRequest } from '../../_adapter.js';

export { onRequest };
