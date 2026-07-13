// ═════════════════════════════════════════════════════════════════════════
// functions/api/page-agent/_adapter.js
//
// Stage 4 disabled-by-default Page Agent model adapter.
//
//   POST /api/page-agent/plan
//
//   PAGE_AGENT_MODEL_ENABLED  — server-only
//   PAGE_AGENT_MODEL_PROVIDER — server-only ("disabled" | "mock")
//
// Deterministic browser mock mode (resident-mock-model.js) remains the
// default offline path and is not replaced by this endpoint.
// ═════════════════════════════════════════════════════════════════════════

import {
  createProvider,
  isModelAdapterEnabled,
} from './_providers.js';
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

function resolveTimeoutMs(env) {
  const raw = env && env.PAGE_AGENT_MODEL_TIMEOUT_MS;
  const n = typeof raw === 'string' || typeof raw === 'number' ? Number(raw) : NaN;
  if (!Number.isFinite(n) || n < 1) return S.DEFAULT_TIMEOUT_MS;
  return Math.min(Math.floor(n), S.ABS_MAX_TIMEOUT_MS);
}

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

  // Query-string / body flags are ignored. Server env only.
  if (!isModelAdapterEnabled(env)) {
    return jsonResponse(S.disabledErrorBody(), 200, headers);
  }

  const selected = createProvider(env);
  if (selected.kind === 'unsupported') {
    return jsonResponse(
      S.errorBody('page_agent_provider_unsupported', 'provider:' + selected.name),
      200,
      headers
    );
  }
  if (selected.kind === 'not_configured' || !selected.provider) {
    return jsonResponse(
      S.errorBody('page_agent_provider_not_configured', 'provider_missing_or_disabled'),
      200,
      headers
    );
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
  const provider = selected.provider;

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
    return jsonResponse(
      S.errorBody(checked.error || 'provider_error', checked.detail),
      200,
      headers
    );
  }

  return jsonResponse(S.successBody(checked.plan), 200, headers);
}

export { isModelAdapterEnabled, createProvider, S as schema };
