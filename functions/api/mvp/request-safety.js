export const DEFAULT_MAX_BODY_BYTES = 8192;
export const MIN_MAX_BODY_BYTES = 1024;
export const MAX_MAX_BODY_BYTES = 32768;
export const MAX_QUESTION_CHARS = 300;
export const MAX_SESSION_ID_CHARS = 128;
// #1331 Slice A: `site_id` is an OPTIONAL, forward-compatible field. It is
// accepted here for shape-validation only; the actual site runtime resolution
// and fail-closed dispatch live in site_runtime.js (mirrored from the Python
// resolver). Omitting it preserves the legacy Buk-gu default.
export const ALLOWED_REQUEST_FIELDS = Object.freeze(['question', 'locale', 'session_id', 'site_id']);
export const SENSITIVE_CATEGORIES = Object.freeze([
  'resident_id_like',
  'phone_like',
  'email_like',
  'precise_address_like',
]);

const SESSION_ID_RE = /^[A-Za-z0-9_-]{16,128}$/;
const RESIDENT_ID_RE = /(^|[^0-9])([0-9]{6})[-\s]?([1-4][0-9]{6})(?=$|[^0-9])/g;
const PHONE_RE = /(^|[^0-9])((?:\+82[-.\s]?)?0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4})(?=$|[^0-9])/g;
const EMAIL_RE = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;
const PRECISE_ADDRESS_RE = /(?:[가-힣]{2,}(?:시|도)\s+)?[가-힣]{1,}(?:시|군|구)\s+[가-힣0-9·.-]{1,}(?:(?:로|길)\s*\d{1,4}(?:-\d{1,4})?|동\s+\d{1,4}(?:-\d{1,4})?)/g;

function headerValue(request, name) {
  if (!request || !request.headers || typeof request.headers.get !== 'function') return '';
  return String(request.headers.get(name) || '').trim();
}

export function resolveMaxBodyBytes(env) {
  const raw = env && typeof env.MVP_MAX_BODY_BYTES === 'string'
    ? env.MVP_MAX_BODY_BYTES.trim()
    : '';
  if (!/^\d+$/.test(raw)) return DEFAULT_MAX_BODY_BYTES;
  const parsed = Number(raw);
  if (!Number.isSafeInteger(parsed) || parsed < MIN_MAX_BODY_BYTES || parsed > MAX_MAX_BODY_BYTES) {
    return DEFAULT_MAX_BODY_BYTES;
  }
  return parsed;
}

export function isJsonContentType(request) {
  const raw = headerValue(request, 'Content-Type').toLowerCase();
  if (!raw) return false;
  return raw.split(';', 1)[0].trim() === 'application/json';
}

export function declaredContentLength(request) {
  const raw = headerValue(request, 'Content-Length');
  if (!raw || !/^\d+$/.test(raw)) return null;
  const parsed = Number(raw);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : null;
}

function utf8ByteLength(text) {
  return new TextEncoder().encode(String(text || '')).byteLength;
}

async function readBoundedText(request, maxBodyBytes) {
  const body = request && request.body;
  if (body && typeof body.getReader === 'function') {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let text = '';
    let totalBytes = 0;
    try {
      while (true) {
        const chunk = await reader.read();
        if (!chunk || chunk.done) break;
        const value = chunk.value;
        if (!(value instanceof Uint8Array)) {
          try { await reader.cancel(); } catch (_) { /* noop */ }
          return { ok: false, failureCode: 'invalid_input' };
        }
        totalBytes += value.byteLength;
        if (totalBytes > maxBodyBytes) {
          try { await reader.cancel(); } catch (_) { /* noop */ }
          return { ok: false, failureCode: 'payload_too_large' };
        }
        text += decoder.decode(value, { stream: true });
      }
      text += decoder.decode();
      return { ok: true, text };
    } catch (_) {
      try { await reader.cancel(); } catch (_) { /* noop */ }
      return { ok: false, failureCode: 'invalid_input' };
    }
  }

  try {
    const text = await request.text();
    if (utf8ByteLength(text) > maxBodyBytes) {
      return { ok: false, failureCode: 'payload_too_large' };
    }
    return { ok: true, text };
  } catch (_) {
    return { ok: false, failureCode: 'invalid_input' };
  }
}

export async function readBoundedJsonBody(request, env) {
  const maxBodyBytes = resolveMaxBodyBytes(env);
  if (!isJsonContentType(request)) {
    return { ok: false, status: 415, failureCode: 'unsupported_media_type', maxBodyBytes };
  }

  const declaredBytes = declaredContentLength(request);
  if (declaredBytes !== null && declaredBytes > maxBodyBytes) {
    return { ok: false, status: 413, failureCode: 'payload_too_large', maxBodyBytes };
  }

  const bounded = await readBoundedText(request, maxBodyBytes);
  if (!bounded.ok) {
    return {
      ok: false,
      status: bounded.failureCode === 'payload_too_large' ? 413 : 200,
      failureCode: bounded.failureCode || 'invalid_input',
      maxBodyBytes,
    };
  }

  let body;
  try {
    body = JSON.parse(bounded.text);
  } catch (_) {
    return { ok: false, status: 200, failureCode: 'invalid_input', maxBodyBytes };
  }
  return { ok: true, body, maxBodyBytes };
}

export function validateRequestShape(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return { ok: false, failureCode: 'invalid_input', reason: 'body_not_object' };
  }
  for (const key of Object.keys(body)) {
    if (!ALLOWED_REQUEST_FIELDS.includes(key)) {
      return { ok: false, failureCode: 'invalid_input', reason: 'unknown_field' };
    }
  }
  if (!Object.prototype.hasOwnProperty.call(body, 'question')) {
    return { ok: false, status: 400, failureCode: 'invalid_input', reason: 'missing_question' };
  }
  if (typeof body.question !== 'string') {
    return { ok: false, failureCode: 'invalid_input', reason: 'question_type' };
  }
  if (Object.prototype.hasOwnProperty.call(body, 'locale') && typeof body.locale !== 'string') {
    return { ok: false, failureCode: 'invalid_input', reason: 'locale_type' };
  }
  if (Object.prototype.hasOwnProperty.call(body, 'session_id') && typeof body.session_id !== 'string') {
    return { ok: false, failureCode: 'invalid_input', reason: 'session_id_type' };
  }
  if (typeof body.session_id === 'string' && !SESSION_ID_RE.test(body.session_id)) {
    return { ok: false, failureCode: 'invalid_input', reason: 'session_id_format' };
  }
  if (Object.prototype.hasOwnProperty.call(body, 'site_id') && typeof body.site_id !== 'string') {
    return { ok: false, failureCode: 'invalid_input', reason: 'site_id_type' };
  }
  return { ok: true };
}

export function detectSensitiveInput(question) {
  const text = String(question || '');
  const categories = [];
  const push = (name, re) => {
    re.lastIndex = 0;
    if (re.test(text)) categories.push(name);
    re.lastIndex = 0;
  };
  push('resident_id_like', RESIDENT_ID_RE);
  push('phone_like', PHONE_RE);
  push('email_like', EMAIL_RE);
  push('precise_address_like', PRECISE_ADDRESS_RE);
  return categories;
}

export function redactSensitiveInput(question, categories = detectSensitiveInput(question)) {
  let redacted = String(question || '');
  if (categories.includes('phone_like')) {
    redacted = redacted.replace(PHONE_RE, (match, prefix) => `${prefix || ''}[REDACTED_PHONE]`);
  }
  if (categories.includes('email_like')) {
    redacted = redacted.replace(EMAIL_RE, '[REDACTED_EMAIL]');
  }
  if (categories.includes('precise_address_like')) {
    redacted = redacted.replace(PRECISE_ADDRESS_RE, '[REDACTED_ADDRESS]');
  }
  return redacted.replace(/\s+/g, ' ').trim();
}

export function assessQuestionPrivacy(question) {
  const categories = detectSensitiveInput(question);
  if (categories.includes('resident_id_like')) {
    return {
      ok: false,
      failureCode: 'sensitive_input_rejected',
      categories,
      question: '',
      redacted: false,
    };
  }
  const safeQuestion = redactSensitiveInput(question, categories);
  if (categories.length && !safeQuestion.replace(/\[REDACTED_[A-Z]+\]/g, '').trim()) {
    return {
      ok: false,
      failureCode: 'sensitive_input_rejected',
      categories,
      question: '',
      redacted: true,
    };
  }
  return {
    ok: true,
    failureCode: '',
    categories,
    question: safeQuestion,
    redacted: categories.length > 0,
  };
}
