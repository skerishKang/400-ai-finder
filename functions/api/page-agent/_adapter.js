// ═════════════════════════════════════════════════════════════════════════
// functions/api/page-agent/_adapter.js
//
// Stage 4 disabled-by-default Page Agent model adapter.
//
//   POST /api/page-agent/plan
//
// Responsibilities:
//   * CORS / method gate (same family as /api/mvp/ask)
//   * server-side enable flag only (never browser query)
//   * strict request schema validation
//   * provider-neutral stub interface (NO network, NO secrets)
//   * plan validation (allowlist, max steps, same-origin navigate,
//     repeated-action detection, timeout / cancellation structure)
//
// Deterministic browser mock mode (examples/page-agent mock-model.js) is
// intentionally untouched and remains the default offline path.
// ═════════════════════════════════════════════════════════════════════════

import * as S from './_schema.js';

const PRODUCTION_ORIGIN = 'https://cgbukku.pages.dev';

function jsonResponse(payload, status, headers) {
  return new Response(JSON.stringify(payload), { status: status, headers: headers });
}

export function buildHeaders(request) {
  const origin = request.headers.get('Origin') || '';
  let allowedOrigin = PRODUCTION_ORIGIN;
  try {
    const parsed = new URL(origin);
    const isPagesOrigin =
      parsed.protocol === 'https:' &&
      (parsed.hostname === 'cgbukku.pages.dev' ||
        parsed.hostname.endsWith('.cgbukku.pages.dev'));
    const isLocal =
      (parsed.protocol === 'http:' || parsed.protocol === 'https:') &&
      (parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1');
    if (isPagesOrigin || isLocal) allowedOrigin = origin;
  } catch (_) {
    // Missing / malformed Origin falls back to production origin.
  }
  return {
    'Access-Control-Allow-Origin': allowedOrigin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Cache-Control': 'no-store',
    Vary: 'Origin',
    'Content-Type': 'application/json; charset=utf-8',
  };
}

/**
 * Enable only via server env. Browser query/body flags are ignored.
 * Truthy values: "1", "true", "yes", "on" (case-insensitive).
 */
export function isModelAdapterEnabled(env) {
  if (!env || typeof env !== 'object') return false;
  const raw = env[S.ENABLE_FLAG];
  if (raw === true || raw === 1) return true;
  if (typeof raw !== 'string') return false;
  const v = raw.trim().toLowerCase();
  return v === '1' || v === 'true' || v === 'yes' || v === 'on';
}

function resolveTimeoutMs(env) {
  const raw = env && env.PAGE_AGENT_MODEL_TIMEOUT_MS;
  const n = typeof raw === 'string' || typeof raw === 'number' ? Number(raw) : NaN;
  if (!Number.isFinite(n) || n < 1) return S.DEFAULT_TIMEOUT_MS;
  return Math.min(Math.floor(n), S.ABS_MAX_TIMEOUT_MS);
}

/**
 * Provider-neutral interface. Stage 4 ships only a non-network stub.
 * Real OpenAI/Gemini/Claude/Firecrawl implementations are intentionally
 * absent and must not be added without separate controlled-live approval.
 */
export class PageAgentModelProvider {
  /**
   * @param {object} _request validated plan request
   * @param {{ signal?: AbortSignal }} _options
   * @returns {Promise<{ ok: boolean, plan?: object, error?: string, detail?: string }>}
   */
  async createPlan(_request, _options) {
    throw new Error('page_agent_provider_not_implemented');
  }
}

/**
 * Default stub: never performs network I/O and never loads secrets.
 * When the adapter is enabled without a real provider binding, this stub
 * fails closed with a structured provider error (not a plan).
 */
export class DisabledStubProvider extends PageAgentModelProvider {
  async createPlan(_request, options) {
    const signal = options && options.signal;
    if (signal && signal.aborted) {
      const err = new Error('page_agent_cancelled');
      err.code = 'page_agent_cancelled';
      throw err;
    }
    // Explicit non-implementation: Stage 4 forbids live provider calls.
    return {
      ok: false,
      error: 'page_agent_provider_not_configured',
      detail: 'stage4_stub_only',
    };
  }
}

/**
 * Optional pure validator helper for offline unit tests / future wiring:
 * if a candidate plan is supplied (e.g. from a future mock provider),
 * enforce the same fail-closed schema.
 */
export function validateProviderPlanResult(candidate, requestValue) {
  if (!candidate || typeof candidate !== 'object') {
    return { ok: false, error: 'provider_error', detail: 'malformed_provider_result' };
  }
  if (candidate.ok === false) {
    return {
      ok: false,
      error: candidate.error || 'provider_error',
      detail: candidate.detail || 'provider_reported_error',
    };
  }
  if (!candidate.plan) {
    return { ok: false, error: 'provider_error', detail: 'missing_plan' };
  }
  return S.validatePlan(candidate.plan, {
    max_steps: requestValue.max_steps,
    available_actions: requestValue.available_actions,
  });
}

async function readJsonBody(request) {
  const text = await request.text();
  if (!text || !String(text).trim()) {
    return { ok: false, error: 'invalid_request', detail: 'empty_body' };
  }
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch (_) {
    return { ok: false, error: 'invalid_request', detail: 'malformed_json' };
  }
}

/**
 * Run a provider stub under timeout + cancellation. Never retries.
 */
export async function runWithTimeout(factory, timeoutMs, externalSignal) {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  const onExternalAbort = () => controller.abort();
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort();
    else externalSignal.addEventListener('abort', onExternalAbort, { once: true });
  }

  try {
    const result = await factory(controller.signal);
    return { ok: true, value: result, timedOut: false, cancelled: false };
  } catch (err) {
    if (timedOut) {
      return { ok: false, error: 'page_agent_timeout', detail: 'provider_timeout' };
    }
    if (controller.signal.aborted || (err && err.code === 'page_agent_cancelled')) {
      return { ok: false, error: 'page_agent_cancelled', detail: 'request_aborted' };
    }
    return {
      ok: false,
      error: 'provider_error',
      detail: err && err.message ? String(err.message).slice(0, 120) : 'provider_threw',
    };
  } finally {
    clearTimeout(timer);
    if (externalSignal) {
      externalSignal.removeEventListener('abort', onExternalAbort);
    }
  }
}

/**
 * Cloudflare Pages Function handler.
 * @param {{ request: Request, env?: object }} context
 */
export async function onRequest(context) {
  const request = context.request;
  const env = context.env || {};
  const headers = buildHeaders(request);

  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: headers });
  }
  if (request.method !== 'POST') {
    return jsonResponse(S.errorBody('method_not_allowed'), 405, headers);
  }

  // Query-string activation is intentionally ignored.
  // Only PAGE_AGENT_MODEL_ENABLED on the server enables the adapter.
  if (!isModelAdapterEnabled(env)) {
    return jsonResponse(S.disabledErrorBody(), 200, headers);
  }

  const parsed = await readJsonBody(request);
  if (!parsed.ok) {
    return jsonResponse(S.errorBody(parsed.error, parsed.detail), 400, headers);
  }

  const validated = S.validatePlanRequest(parsed.value);
  if (!validated.ok) {
    return jsonResponse(S.errorBody(validated.error, validated.detail), 400, headers);
  }

  const timeoutMs = resolveTimeoutMs(env);
  const provider = new DisabledStubProvider();

  const timed = await runWithTimeout(
    (signal) => provider.createPlan(validated.value, { signal: signal }),
    timeoutMs,
    request.signal
  );

  if (!timed.ok) {
    return jsonResponse(S.errorBody(timed.error, timed.detail), 200, headers);
  }

  const providerResult = timed.value;
  const checked = validateProviderPlanResult(providerResult, validated.value);
  if (!checked.ok) {
    // Provider stub path: structured fail-closed, never a partial plan.
    if (checked.error === 'invalid_plan') {
      return jsonResponse(S.errorBody(checked.error, checked.detail), 200, headers);
    }
    return jsonResponse(
      S.errorBody(checked.error || 'provider_error', checked.detail),
      200,
      headers
    );
  }

  return jsonResponse(S.successBody(checked.plan), 200, headers);
}

export { S as schema };
