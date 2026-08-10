export const TURNSTILE_SITEVERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify';
export const TURNSTILE_MAX_TOKEN_CHARS = 2048;
export const TURNSTILE_DEFAULT_ACTION = 'mvp_ask';
export const TURNSTILE_DEFAULT_TIMEOUT_MS = 3000;
export const TURNSTILE_MIN_TIMEOUT_MS = 250;
export const TURNSTILE_MAX_TIMEOUT_MS = 10000;
export const TURNSTILE_MODES = Object.freeze(['required', 'disabled']);

const SAFE_ACTION_RE = /^[A-Za-z0-9_-]{1,32}$/;
const SAFE_HOSTNAME_RE = /^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/;

export function normalizeTurnstileHostname(value) {
  const raw = String(value || '').trim().toLowerCase();
  if (!raw) return '';
  if (raw === 'localhost' || raw === '127.0.0.1' || raw === '::1' || raw === '[::1]') return raw;
  return SAFE_HOSTNAME_RE.test(raw) ? raw : '';
}

export function isLoopbackHostname(value) {
  const host = normalizeTurnstileHostname(value);
  return host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]';
}

export function requestHostnameFromUrl(request) {
  try {
    return normalizeTurnstileHostname(new URL(String(request && request.url || '')).hostname);
  } catch (_) {
    return '';
  }
}

export function resolveTurnstileMode(env, requestHostname) {
  const raw = env && typeof env.MVP_TURNSTILE_MODE === 'string'
    ? env.MVP_TURNSTILE_MODE.trim().toLowerCase()
    : '';
  const loopback = isLoopbackHostname(requestHostname);
  if (raw === 'disabled' && loopback) {
    return { mode: 'disabled', reason: 'explicit_loopback_bypass' };
  }
  if (raw === 'disabled' && !loopback) {
    return { mode: 'required', reason: 'insecure_bypass_rejected' };
  }
  if (raw === 'required') return { mode: 'required', reason: 'explicit_required' };
  if (!raw) return { mode: 'required', reason: 'default_required' };
  return { mode: 'required', reason: 'invalid_mode_fail_closed' };
}

export function resolveTurnstileTimeoutMs(env) {
  const raw = env && typeof env.MVP_TURNSTILE_TIMEOUT_MS === 'string'
    ? env.MVP_TURNSTILE_TIMEOUT_MS.trim()
    : '';
  if (!/^\d+$/.test(raw)) return TURNSTILE_DEFAULT_TIMEOUT_MS;
  const parsed = Number(raw);
  if (!Number.isSafeInteger(parsed) || parsed < TURNSTILE_MIN_TIMEOUT_MS || parsed > TURNSTILE_MAX_TIMEOUT_MS) {
    return TURNSTILE_DEFAULT_TIMEOUT_MS;
  }
  return parsed;
}

export function resolveTurnstileAction(env) {
  const raw = env && typeof env.MVP_TURNSTILE_EXPECTED_ACTION === 'string'
    ? env.MVP_TURNSTILE_EXPECTED_ACTION.trim()
    : '';
  return SAFE_ACTION_RE.test(raw) ? raw : TURNSTILE_DEFAULT_ACTION;
}

export function resolveAllowedTurnstileHostnames(env) {
  const raw = env && typeof env.MVP_TURNSTILE_ALLOWED_HOSTNAMES === 'string'
    ? env.MVP_TURNSTILE_ALLOWED_HOSTNAMES
    : '';
  const result = [];
  for (const part of raw.split(',')) {
    const host = normalizeTurnstileHostname(part);
    if (host && !result.includes(host)) result.push(host);
    if (result.length >= 16) break;
  }
  return result;
}

export function validateTurnstileToken(value) {
  if (typeof value !== 'string') return { ok: false, reason: 'missing_token', token: '' };
  const token = value.trim();
  if (!token) return { ok: false, reason: 'missing_token', token: '' };
  if (token.length > TURNSTILE_MAX_TOKEN_CHARS) {
    return { ok: false, reason: 'token_too_long', token: '' };
  }
  if (/\s/.test(token)) return { ok: false, reason: 'malformed_token', token: '' };
  return { ok: true, reason: 'ok', token };
}

function secretFromEnv(env) {
  const secret = env && typeof env.MVP_TURNSTILE_SECRET_KEY === 'string'
    ? env.MVP_TURNSTILE_SECRET_KEY.trim()
    : '';
  return secret && secret.length <= 4096 ? secret : '';
}

function siteKeyFromEnv(env) {
  const siteKey = env && typeof env.MVP_TURNSTILE_SITE_KEY === 'string'
    ? env.MVP_TURNSTILE_SITE_KEY.trim()
    : '';
  return siteKey && siteKey.length <= 512 ? siteKey : '';
}

export function buildTurnstileClientConfig(env, requestHostname) {
  const mode = resolveTurnstileMode(env, requestHostname);
  if (mode.mode === 'disabled') {
    return {
      ok: true,
      enabled: false,
      configured: true,
      mode: 'disabled',
      reason: mode.reason,
      site_key: '',
      action: resolveTurnstileAction(env),
    };
  }
  const siteKey = siteKeyFromEnv(env);
  return {
    ok: Boolean(siteKey),
    enabled: true,
    configured: Boolean(siteKey),
    mode: 'required',
    reason: siteKey ? mode.reason : 'site_key_missing',
    site_key: siteKey,
    action: resolveTurnstileAction(env),
  };
}

function safeErrorCodes(value) {
  if (!Array.isArray(value)) return [];
  return value.filter((item) => typeof item === 'string' && /^[a-z0-9_-]{1,64}$/i.test(item)).slice(0, 8);
}

function verificationFailure(failureCode, reason, status, extras = {}) {
  return Object.assign({
    ok: false,
    failureCode,
    reason,
    status,
    verified: false,
    bypassed: false,
    action: '',
    hostname: '',
    errorCodes: [],
  }, extras);
}

export async function verifyTurnstileRequest(options = {}) {
  const env = options.env || {};
  const requestHostname = normalizeTurnstileHostname(options.requestHostname);
  const mode = resolveTurnstileMode(env, requestHostname);
  if (mode.mode === 'disabled') {
    return {
      ok: true,
      failureCode: '',
      reason: mode.reason,
      status: 200,
      verified: false,
      bypassed: true,
      action: resolveTurnstileAction(env),
      hostname: requestHostname,
      errorCodes: [],
    };
  }

  const secret = secretFromEnv(env);
  if (!secret) {
    return verificationFailure('bot_verification_config_error', 'secret_missing', 503);
  }

  const tokenState = validateTurnstileToken(options.token);
  if (!tokenState.ok) {
    return verificationFailure('bot_verification_required', tokenState.reason, 403);
  }

  if (typeof options.fetchWithDeadline !== 'function') {
    return verificationFailure('bot_verification_config_error', 'deadline_fetch_missing', 503);
  }

  const configuredTimeout = resolveTurnstileTimeoutMs(env);
  const remainingMs = Number.isFinite(options.remainingRequestBudgetMs)
    ? Math.max(0, Math.floor(options.remainingRequestBudgetMs))
    : configuredTimeout;
  const timeoutMs = Math.min(configuredTimeout, remainingMs);
  if (timeoutMs < TURNSTILE_MIN_TIMEOUT_MS) {
    return verificationFailure('bot_verification_unavailable', 'request_deadline_exhausted', 503);
  }

  let response;
  try {
    response = await options.fetchWithDeadline(TURNSTILE_SITEVERIFY_URL, {
      method: 'POST',
      redirect: 'manual',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        secret,
        response: tokenState.token,
      }),
    }, timeoutMs);
  } catch (error) {
    const timeout = Boolean(error) && (error.code === 'upstream_timeout' || error.name === 'AbortError');
    return verificationFailure(
      'bot_verification_unavailable',
      timeout ? 'siteverify_timeout' : 'siteverify_network_error',
      503,
    );
  }

  if (!response || response.ok !== true) {
    try { if (response && typeof response.text === 'function') await response.text(); } catch (_) { /* noop */ }
    return verificationFailure('bot_verification_unavailable', 'siteverify_http_error', 503);
  }

  let data;
  try {
    data = await response.json();
  } catch (_) {
    return verificationFailure('bot_verification_unavailable', 'siteverify_malformed_response', 503);
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return verificationFailure('bot_verification_unavailable', 'siteverify_malformed_response', 503);
  }

  const errorCodes = safeErrorCodes(data['error-codes']);
  if (data.success !== true) {
    const duplicate = errorCodes.includes('timeout-or-duplicate');
    return verificationFailure(
      'bot_verification_failed',
      duplicate ? 'expired_or_duplicate' : 'siteverify_rejected',
      403,
      { errorCodes },
    );
  }

  const expectedAction = resolveTurnstileAction(env);
  const action = typeof data.action === 'string' ? data.action.trim() : '';
  if (expectedAction && action !== expectedAction) {
    return verificationFailure('bot_verification_failed', 'action_mismatch', 403, { action });
  }

  const allowedHostnames = resolveAllowedTurnstileHostnames(env);
  const hostname = normalizeTurnstileHostname(data.hostname);
  if (allowedHostnames.length && !allowedHostnames.includes(hostname)) {
    return verificationFailure('bot_verification_failed', 'hostname_mismatch', 403, { action, hostname });
  }

  return {
    ok: true,
    failureCode: '',
    reason: 'verified',
    status: 200,
    verified: true,
    bypassed: false,
    action,
    hostname,
    errorCodes: [],
  };
}
