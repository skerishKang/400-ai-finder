// ═════════════════════════════════════════════════════════════════════════
// functions/api/page-agent/_schema.js
//
// Provider-neutral request/response schema and pure fail-closed validators
// for the Stage 4 Page Agent server-side plan adapter.
//
// No network. No secrets. Safe to import from Node contract tests later.
// ═════════════════════════════════════════════════════════════════════════

/** Server-side enable flag only (Cloudflare Pages env / secret). */
export const ENABLE_FLAG = 'PAGE_AGENT_MODEL_ENABLED';

/** Optional explicit provider name (never read from the browser body). */
export const PROVIDER_ENV = 'PAGE_AGENT_MODEL_PROVIDER';

export const ALLOWED_ACTIONS = Object.freeze([
  'click',
  'input',
  'select',
  'scroll',
  'read',
  'navigate',
]);

export const ALLOWED_REQUEST_KEYS = Object.freeze([
  'request_id',
  'question',
  'current_route',
  'available_actions',
  'max_steps',
]);

export const RESULT_BOUNDARY = 'STOP_FOR_USER_CONFIRMATION';

export const DEFAULT_MAX_STEPS = 10;
export const ABS_MAX_STEPS = 10;
export const MAX_QUESTION_CHARS = 500;
export const MAX_REQUEST_ID_CHARS = 128;
export const MAX_ROUTE_CHARS = 200;
export const MAX_TARGET_CHARS = 300;
export const MAX_VALUE_CHARS = 500;
export const DEFAULT_TIMEOUT_MS = 15000;
export const ABS_MAX_TIMEOUT_MS = 30000;

export const FORBIDDEN_TARGET_KEYWORDS = Object.freeze([
  'password',
  'passwd',
  'token',
  'secret',
  'api_key',
  'apikey',
  'authorization',
  'credit',
  'card',
  'cvv',
  'ssn',
  'submit',
  'payment',
  'pay',
  'login',
  'signin',
  'sign-in',
  'auth',
  'delete',
  'destroy',
  'javascript:',
  'data:',
  'vbscript:',
]);

export const FORBIDDEN_BODY_KEYS = Object.freeze([
  'api_key',
  'apiKey',
  'authorization',
  'Authorization',
  'password',
  'secret',
  'token',
  'access_token',
  'refresh_token',
  'private_key',
  'provider_key',
  'gemini_key',
  'openai_key',
]);

/**
 * Same-origin internal route / selector navigation only.
 * Accepts:
 *   - empty / # / relative path (/mvp/, ./x)
 *   - internal route id tokens (passport-guidance)
 *   - query-only strings (?journey=...)
 * Rejects absolute external URLs, protocol-relative, javascript:, data:.
 */
export function isSameOriginInternalTarget(raw) {
  if (typeof raw !== 'string') return false;
  const value = raw.trim();
  if (!value) return false;
  if (value.length > MAX_TARGET_CHARS) return false;

  const lower = value.toLowerCase();
  if (
    lower.startsWith('javascript:') ||
    lower.startsWith('data:') ||
    lower.startsWith('vbscript:') ||
    lower.startsWith('blob:') ||
    lower.startsWith('file:')
  ) {
    return false;
  }
  // Protocol-relative or absolute URL.
  if (lower.startsWith('//') || /^[a-z][a-z0-9+.-]*:/i.test(value)) {
    try {
      const u = new URL(value, 'http://127.0.0.1');
      // Only allow same-origin style when host is loopback placeholder and path is relative-ish —
      // absolute http(s) to any host is rejected for navigate.
      if (u.protocol === 'http:' || u.protocol === 'https:') {
        return false;
      }
    } catch (_) {
      return false;
    }
    return false;
  }
  // Fragment / relative path / route id / CSS selector for click/input/read.
  return true;
}

export function isForbiddenTargetText(raw) {
  const text = String(raw || '').toLowerCase();
  if (!text) return false;
  return FORBIDDEN_TARGET_KEYWORDS.some((k) => text.includes(k));
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

/**
 * Unknown top-level keys are rejected fail-closed (strict object contract).
 */
export function validatePlanRequest(body) {
  if (!isPlainObject(body)) {
    return { ok: false, error: 'invalid_request', detail: 'body_must_be_object' };
  }

  for (const key of Object.keys(body)) {
    if (!ALLOWED_REQUEST_KEYS.includes(key)) {
      return { ok: false, error: 'invalid_request', detail: 'unknown_key:' + key };
    }
    if (FORBIDDEN_BODY_KEYS.includes(key)) {
      return { ok: false, error: 'invalid_request', detail: 'forbidden_key:' + key };
    }
  }

  const requestId = body.request_id;
  if (typeof requestId !== 'string' || !requestId.trim()) {
    return { ok: false, error: 'invalid_request', detail: 'request_id_required' };
  }
  if (requestId.length > MAX_REQUEST_ID_CHARS) {
    return { ok: false, error: 'invalid_request', detail: 'request_id_too_long' };
  }
  if (!/^[A-Za-z0-9._:-]+$/.test(requestId.trim())) {
    return { ok: false, error: 'invalid_request', detail: 'request_id_charset' };
  }

  const question = body.question;
  if (typeof question !== 'string' || !question.trim()) {
    return { ok: false, error: 'invalid_request', detail: 'question_required' };
  }
  if (question.length > MAX_QUESTION_CHARS) {
    return { ok: false, error: 'invalid_request', detail: 'question_too_long' };
  }

  const currentRoute = body.current_route;
  if (currentRoute !== undefined && currentRoute !== null) {
    if (typeof currentRoute !== 'string') {
      return { ok: false, error: 'invalid_request', detail: 'current_route_type' };
    }
    if (currentRoute.length > MAX_ROUTE_CHARS) {
      return { ok: false, error: 'invalid_request', detail: 'current_route_too_long' };
    }
    const route = currentRoute.trim();
    // Bare internal route ids (passport-guidance) and relative paths are OK.
    // Absolute / protocol-relative URLs are rejected.
    if (route) {
      if (/^[a-z][a-z0-9+.-]*:/i.test(route) || route.startsWith('//')) {
        return { ok: false, error: 'invalid_request', detail: 'current_route_external' };
      }
      if (isForbiddenTargetText(route)) {
        return { ok: false, error: 'invalid_request', detail: 'current_route_forbidden' };
      }
    }
  }

  let availableActions = body.available_actions;
  if (availableActions === undefined) {
    availableActions = ALLOWED_ACTIONS.slice();
  }
  if (!Array.isArray(availableActions) || availableActions.length === 0) {
    return { ok: false, error: 'invalid_request', detail: 'available_actions_required' };
  }
  for (const action of availableActions) {
    if (typeof action !== 'string' || !ALLOWED_ACTIONS.includes(action)) {
      return { ok: false, error: 'invalid_request', detail: 'available_action_not_allowed:' + String(action) };
    }
  }

  let maxSteps = body.max_steps;
  if (maxSteps === undefined || maxSteps === null) {
    maxSteps = DEFAULT_MAX_STEPS;
  }
  if (typeof maxSteps !== 'number' || !Number.isInteger(maxSteps) || maxSteps < 1) {
    return { ok: false, error: 'invalid_request', detail: 'max_steps_invalid' };
  }
  if (maxSteps > ABS_MAX_STEPS) {
    return { ok: false, error: 'invalid_request', detail: 'max_steps_exceeded' };
  }

  return {
    ok: true,
    value: {
      request_id: requestId.trim(),
      question: question.trim(),
      current_route: typeof currentRoute === 'string' ? currentRoute.trim() : '',
      available_actions: availableActions.slice(),
      max_steps: maxSteps,
    },
  };
}

function stepSignature(step) {
  return [
    String(step.action || ''),
    String(step.target || ''),
    step.value === null || step.value === undefined ? '' : String(step.value),
  ].join('\u0001');
}

/**
 * Validate a provider-neutral plan object.
 * Rejects unknown actions, blank selectors, external navigate, secrets,
 * excessive steps, and consecutive identical steps.
 */
export function validatePlan(plan, options) {
  const opts = options || {};
  const maxSteps = typeof opts.max_steps === 'number' ? opts.max_steps : DEFAULT_MAX_STEPS;
  const available = Array.isArray(opts.available_actions)
    ? opts.available_actions
    : ALLOWED_ACTIONS.slice();

  if (!isPlainObject(plan)) {
    return { ok: false, error: 'invalid_plan', detail: 'plan_must_be_object' };
  }
  if (plan.result_boundary !== RESULT_BOUNDARY) {
    return { ok: false, error: 'invalid_plan', detail: 'result_boundary' };
  }
  if (!Array.isArray(plan.steps)) {
    return { ok: false, error: 'invalid_plan', detail: 'steps_required' };
  }
  if (plan.steps.length === 0) {
    return { ok: false, error: 'invalid_plan', detail: 'steps_empty' };
  }
  if (plan.steps.length > maxSteps || plan.steps.length > ABS_MAX_STEPS) {
    return { ok: false, error: 'invalid_plan', detail: 'steps_exceeded' };
  }

  const normalized = [];
  let prevSig = null;
  for (let i = 0; i < plan.steps.length; i += 1) {
    const step = plan.steps[i];
    if (!isPlainObject(step)) {
      return { ok: false, error: 'invalid_plan', detail: 'step_not_object:' + i };
    }
    const action = step.action;
    if (typeof action !== 'string' || !ALLOWED_ACTIONS.includes(action)) {
      return { ok: false, error: 'invalid_plan', detail: 'unknown_action:' + String(action) };
    }
    if (!available.includes(action)) {
      return { ok: false, error: 'invalid_plan', detail: 'action_not_available:' + action };
    }

    // Reject arbitrary script payloads.
    for (const key of Object.keys(step)) {
      if (!['action', 'target', 'value'].includes(key)) {
        return { ok: false, error: 'invalid_plan', detail: 'unknown_step_key:' + key };
      }
    }

    let target = step.target;
    if (target === undefined || target === null) target = '';
    if (typeof target !== 'string') {
      return { ok: false, error: 'invalid_plan', detail: 'target_type:' + i };
    }
    target = target.trim();

    // read may omit target (page-level); all others need a target/selector/route.
    if (action !== 'read' && action !== 'scroll') {
      if (!target) {
        return { ok: false, error: 'invalid_plan', detail: 'blank_target:' + i };
      }
    }
    if (target && !isSameOriginInternalTarget(target)) {
      return { ok: false, error: 'invalid_plan', detail: 'external_or_unsafe_target:' + i };
    }
    if (target && isForbiddenTargetText(target)) {
      return { ok: false, error: 'invalid_plan', detail: 'forbidden_target:' + i };
    }
    if (action === 'navigate' && (!target || !isSameOriginInternalTarget(target))) {
      return { ok: false, error: 'invalid_plan', detail: 'navigate_not_same_origin:' + i };
    }

    let value = step.value === undefined ? null : step.value;
    if (value !== null && typeof value !== 'string' && typeof value !== 'number') {
      return { ok: false, error: 'invalid_plan', detail: 'value_type:' + i };
    }
    if (typeof value === 'string') {
      if (value.length > MAX_VALUE_CHARS) {
        return { ok: false, error: 'invalid_plan', detail: 'value_too_long:' + i };
      }
      if (isForbiddenTargetText(value)) {
        return { ok: false, error: 'invalid_plan', detail: 'forbidden_value:' + i };
      }
      // input of credentials rejected.
      if (action === 'input' && isForbiddenTargetText(target + ' ' + value)) {
        return { ok: false, error: 'invalid_plan', detail: 'credential_input:' + i };
      }
    }

    // Destructive / submit style actions are never on the allowlist; extra guard
    // for selectors that still look like submit/delete.
    if (/(submit|delete|destroy|remove-all)/i.test(target)) {
      return { ok: false, error: 'invalid_plan', detail: 'destructive_target:' + i };
    }

    const out = { action: action, target: target || null, value: value };
    const sig = stepSignature(out);
    if (prevSig !== null && sig === prevSig) {
      return { ok: false, error: 'invalid_plan', detail: 'repeated_identical_action:' + i };
    }
    prevSig = sig;
    normalized.push(out);
  }

  return {
    ok: true,
    plan: {
      steps: normalized,
      result_boundary: RESULT_BOUNDARY,
    },
  };
}

export function disabledErrorBody() {
  return { ok: false, error: 'page_agent_model_disabled' };
}

export function errorBody(code, detail) {
  const out = { ok: false, error: code };
  if (detail) out.detail = detail;
  return out;
}

export function successBody(plan) {
  return { ok: true, plan: plan };
}
