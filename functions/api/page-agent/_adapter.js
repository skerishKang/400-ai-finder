// ═════════════════════════════════════════════════════════════════════════
// functions/api/page-agent/_adapter.js
//
// Fail-closed server-side adapter for the Stage 4 Page Agent.
//
// Contract:
//   POST /api/page-agent/v1/chat/completions
//     inbound  : OpenAI-compatible chat.completions (PageAgent runtime)
//     outbound : exactly ONE provider call (gemini | hy3), no retry,
//                behind a strict validation + policy gateway.
//
// The browser NEVER receives a provider key. The raw inbound payload is
// parsed, normalised, and validated; a NEW provider payload is built.
// The provider response is re-validated; only an approved action is
// rebuilt into an OpenAI-compatible AgentOutput tool call.
//
// Any policy / validation / safety failure returns a safe `done(success:false)`
// so the PageAgent loop terminates gracefully (upstream call count 0 where
// the failure is pre-provider). Protocol misuse returns a compact 4xx.
// ═════════════════════════════════════════════════════════════════════════

import * as P from './_policy.js';

// ── Low-level helpers ───────────────────────────────────────────

function headerGet(request, name) {
  const h = request && request.headers;
  if (!h) return null;
  if (typeof h.get === 'function') return h.get(name);
  if (typeof h[name] === 'string') return h[name];
  return null;
}

function byteLength(s) {
  try {
    return new TextEncoder().encode(s).length;
  } catch (_) {
    return String(s).length;
  }
}

function clampInt(value, fallback, min, max) {
  const n = parseInt(value, 10);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, n));
}

function newRequestId() {
  try {
    return crypto.randomUUID();
  } catch (_) {
    return 'req-' + Date.now();
  }
}

function corsHeaders(request) {
  const origin = headerGet(request, 'Origin') || '';
  let allowed = P.PRODUCTION_ORIGIN;
  if (P.isAllowedOrigin(origin)) allowed = origin;
  return {
    'Access-Control-Allow-Origin': allowed,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Cache-Control': 'no-store',
    'Vary': 'Origin',
    'X-Content-Type-Options': 'nosniff',
    'Content-Type': 'application/json; charset=utf-8',
  };
}

function jsonResponse(payload, status, headers) {
  return new Response(JSON.stringify(payload), { status: status, headers: headers });
}

// Logs ONLY whitelisted fields, and only when debug is enabled.
// Never logs raw request / messages / tools / browser state / user prompt /
// provider response / secrets.
function safeLog(env, fields) {
  if (!env || env.PAGE_AGENT_LLM_DEBUG !== '1') return;
  const out = {};
  for (const k of P.LOG_FIELD_WHITELIST) {
    if (Object.prototype.hasOwnProperty.call(fields, k)) out[k] = fields[k];
  }
  try {
    console.log('[page-agent-adapter] ' + JSON.stringify(out));
  } catch (_) {
    // never throw from logging
  }
}

// ── Provider configuration resolution ──────────────────────────────

export function resolveConfig(env) {
  const envObj = env && typeof env === 'object' ? env : {};
  const enabledRaw = envObj[P.ENABLE_FLAG];
  const enabled = String(enabledRaw).toLowerCase() === 'true' || enabledRaw === true;

  const providerRaw =
    typeof envObj[P.PROVIDER_ENV] === 'string'
      ? envObj[P.PROVIDER_ENV].trim().toLowerCase()
      : '';
  const provider = P.ALLOWED_PROVIDERS.includes(providerRaw) ? providerRaw : '';

  const secretName = provider ? P.SECRET_ENV[provider] : '';
  const secret =
    provider && typeof envObj[secretName] === 'string' ? envObj[secretName] : '';

  const modelEnv = provider ? P.MODEL_ENV[provider] : '';
  const model =
    provider && typeof envObj[modelEnv] === 'string' && envObj[modelEnv].trim()
      ? envObj[modelEnv].trim()
      : P.DEFAULT_MODELS[provider] || '';

  let endpoint = provider ? P.DEFAULT_ENDPOINTS[provider] : '';
  const overrideEnv = provider ? P.ENDPOINT_OVERRIDE_ENV[provider] : '';
  const override =
    typeof envObj[overrideEnv] === 'string' ? envObj[overrideEnv].trim() : '';
  if (override) {
    try {
      const u = new URL(override);
      if (u.protocol === 'https:' && P.ENDPOINT_ALLOWLIST_HOSTS.includes(u.hostname)) {
        endpoint = u.toString();
      }
    } catch (_) {
      // ignore invalid override; keep default
    }
  }

  const maxTokens = clampInt(
    envObj.PAGE_AGENT_LLM_MAX_OUTPUT_TOKENS,
    P.DEFAULT_MAX_OUTPUT_TOKENS,
    1,
    P.ABS_MAX_OUTPUT_TOKENS
  );
  const timeoutMs = clampInt(
    envObj.PAGE_AGENT_LLM_TIMEOUT_MS,
    P.DEFAULT_TIMEOUT_MS,
    1,
    P.ABS_MAX_TIMEOUT_MS
  );
  const maxSteps = clampInt(
    envObj.PAGE_AGENT_LLM_MAX_STEPS,
    P.DEFAULT_MAX_STEPS,
    1,
    P.ABS_MAX_STEPS
  );
  const maxBrowserState = clampInt(
    envObj.PAGE_AGENT_LLM_MAX_BROWSER_STATE_CHARS,
    P.MAX_BROWSER_STATE_CHARS,
    1,
    P.MAX_BROWSER_STATE_CHARS
  );
  const maxUserReq = clampInt(
    envObj.PAGE_AGENT_LLM_MAX_USER_REQUEST_CHARS,
    P.MAX_USER_REQUEST_CHARS,
    1,
    P.MAX_USER_REQUEST_CHARS
  );

  const maxReqBytes = P.MAX_REQUEST_BYTES;
  const usable = !!(enabled && provider && secret && endpoint);
  return {
    enabled: enabled,
    provider: provider,
    secret: secret,
    model: model,
    endpoint: endpoint,
    maxTokens: maxTokens,
    timeoutMs: timeoutMs,
    maxSteps: maxSteps,
    maxBrowserState: maxBrowserState,
    maxUserReq: maxUserReq,
    maxReqBytes: maxReqBytes,
    usable: usable,
  };
}

// ── Request parsing / extraction ──────────────────────────────────

export function parseMessages(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return null;
  const messages = body.messages;
  if (!Array.isArray(messages)) return null;
  return messages;
}

export function extractTextFromMessage(msg) {
  if (!msg || typeof msg !== 'object') return '';
  const c = msg.content;
  if (typeof c === 'string') return c;
  if (Array.isArray(c)) {
    return c
      .map(function (p) {
        return p && typeof p.text === 'string' ? p.text : '';
      })
      .join('\n')
      .trim();
  }
  return '';
}

export function getLastUserMessageText(messages) {
  if (!Array.isArray(messages)) return '';
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i] && messages[i].role === 'user') {
      return extractTextFromMessage(messages[i]);
    }
  }
  return '';
}

export function extractUserRequest(text) {
  if (typeof text !== 'string') return null;
  const openTag = '<user_request>';
  const closeTag = '</user_request>';
  const firstOpen = text.indexOf(openTag);
  if (firstOpen < 0) return null;
  // reject duplicate opening tags
  if (text.indexOf(openTag, firstOpen + 1) >= 0) return null;
  const close = text.indexOf(closeTag);
  if (close <= firstOpen) return null;
  // reject malformed close tag (e.g., </user_request  >)
  const extracted = text.slice(firstOpen, close + closeTag.length);
  if (extracted.includes('<', 1) && extracted.indexOf('<', 1) < close) return null;
  return text.slice(firstOpen + openTag.length, close).trim();
}

export function extractBrowserState(text) {
  if (typeof text !== 'string') return null;
  const openTag = '<browser_state>';
  const closeTag = '</browser_state>';
  const firstOpen = text.indexOf(openTag);
  if (firstOpen < 0) return null;
  // reject duplicate opening tags
  if (text.indexOf(openTag, firstOpen + 1) >= 0) return null;
  const close = text.indexOf(closeTag);
  if (close <= firstOpen) return null;
  return text.slice(firstOpen + openTag.length, close);
}

function stripControlChars(s) {
  let out = '';
  for (let i = 0; i < s.length; i++) {
    const code = s.charCodeAt(i);
    if (code < 32 || code === 127) continue;
    out += s[i];
  }
  return out;
}

export function sanitizeUserRequest(raw) {
  let s = stripControlChars(String(raw == null ? '' : raw));
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

const VALUE_ATTR_RE = /value\s*=\s*[^>]*/gi;

export function redactBrowserState(state, maxChars) {
  const lines = String(state == null ? '' : state).split('\n');
  const kept = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    let drop = false;
    for (let j = 0; j < P.BROWSER_STATE_REDACT_LINE_PATTERNS.length; j++) {
      if (P.BROWSER_STATE_REDACT_LINE_PATTERNS[j].test(line)) {
        drop = true;
        break;
      }
    }
    if (drop) continue;
    kept.push(line.replace(VALUE_ATTR_RE, ''));
  }
  let s = kept.join('\n');
  const cap = typeof maxChars === 'number' && maxChars > 0 ? maxChars : P.MAX_BROWSER_STATE_CHARS;
  if (s.length > cap) s = s.slice(0, cap);
  return s;
}

// ── Step / repeated-action detection (pre-provider) ───────────────

export function countSteps(text) {
  const s = typeof text === 'string' ? text : '';
  let max = 0;
  let idx = s.indexOf('<step_');
  while (idx >= 0) {
    let j = idx + 6;
    let num = '';
    while (j < s.length && s[j] >= '0' && s[j] <= '9') {
      num += s[j];
      j++;
    }
    if (num) {
      const n = parseInt(num, 10);
      if (n > max) max = n;
    }
    idx = s.indexOf('<step_', j);
  }
  return max;
}

const CLICK_IDX_RE = /click_element_by_index["']?\s*:\s*\{["'\s]*index["']?\s*:\s*(\d+)/g;

export function extractUsedClickIndices(text) {
  const set = new Set();
  const s = typeof text === 'string' ? text : '';
  let m;
  CLICK_IDX_RE.lastIndex = 0;
  while ((m = CLICK_IDX_RE.exec(s))) {
    set.add(parseInt(m[1], 10));
  }
  return set;
}

export function parseBrowserStateElements(state) {
  const map = new Map();
  const lines = String(state == null ? '' : state).split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const idxMatch = line.match(/\[(\d+)\]/);
    if (!idxMatch) continue;
    const index = parseInt(idxMatch[1], 10);
    const targetMatch = line.match(/data-action-target=([^\s>]+)/);
    const hrefMatch = line.match(/href=([^\s>]+)/);
    const typeMatch = line.match(/type=([^\s>]+)/);
    function stripQuotes(s) { return s ? s.replace(/^["']|["']$/g, '') : ''; }
    const target = stripQuotes(targetMatch ? targetMatch[1] : '');
    const href = stripQuotes(hrefMatch ? hrefMatch[1] : '');
    const inputType = stripQuotes(typeMatch ? typeMatch[1] : '');
    const inner = line.match(/<([a-z0-9]+)[^>]*>([\s\S]*?)<\/\1>/i);
    const text = inner ? inner[2] : line;
    map.set(index, {
      index: index,
      target: target,
      href: href,
      inputType: inputType,
      text: String(text).replace(/\s+/g, ' ').trim(),
    });
  }
  return map;
}

// ── Action validation gateway ─────────────────────────────────────

export function validateAction(action, stateElements, opts) {
  if (!action || typeof action !== 'object') {
    return { ok: false, failureCode: 'invalid_action' };
  }
  const keys = Object.keys(action);
  if (keys.length !== 1) {
    return { ok: false, failureCode: 'invalid_action' };
  }
  const name = keys[0];
  if (P.ALLOWED_ACTIONS.indexOf(name) === -1) {
    return { ok: false, failureCode: 'unknown_action' };
  }
  const input = action[name];

  if (name === 'click_element_by_index') {
    if (
      !input ||
      typeof input !== 'object' ||
      typeof input.index !== 'number' ||
      !Number.isInteger(input.index) ||
      input.index < 0
    ) {
      return { ok: false, failureCode: 'invalid_action' };
    }
    const el = stateElements.get(input.index);
    if (!el) return { ok: false, failureCode: 'unsafe_target' };
    if (!el.target) return { ok: false, failureCode: 'unsafe_target' };
    if (!P.isSafeTarget(el.target)) return { ok: false, failureCode: 'unsafe_target' };
    if (el.href && el.href !== '#' && el.href !== '') {
      try {
        const u = new URL(el.href, requestOrigin);
        if (u.protocol !== 'http:' && u.protocol !== 'https:') {
          return { ok: false, failureCode: 'unsafe_target' };
        }
        if (u.origin !== requestOrigin) {
          return { ok: false, failureCode: 'unsafe_target' };
        }
      } catch (_) {
        return { ok: false, failureCode: 'unsafe_target' };
      }
    }
    const hay = (el.text + ' ' + el.inputType + ' ' + el.target).toLowerCase();
    for (let i = 0; i < P.FORBIDDEN_ELEMENT_KEYWORDS.length; i++) {
      if (hay.indexOf(P.FORBIDDEN_ELEMENT_KEYWORDS[i].toLowerCase()) !== -1) {
        return { ok: false, failureCode: 'unsafe_target' };
      }
    }
    return {
      ok: true,
      name: name,
      value: { click_element_by_index: { index: input.index } },
    };
  }

  if (name === 'scroll') {
    let pages = 1;
    if (
      input &&
      typeof input === 'object' &&
      typeof input.num_pages === 'number' &&
      Number.isFinite(input.num_pages)
    ) {
      pages = Math.max(P.SCROLL_MIN_PAGES, Math.min(P.SCROLL_MAX_PAGES, input.num_pages));
    }
    return { ok: true, name: name, value: { scroll: { num_pages: pages } } };
  }

  if (name === 'done') {
    if (
      !input ||
      typeof input !== 'object' ||
      typeof input.text !== 'string' ||
      typeof input.success !== 'boolean'
    ) {
      return { ok: false, failureCode: 'invalid_action' };
    }
    let text = input.text;
    if (text.length > P.MAX_DONE_TEXT_CHARS) text = text.slice(0, P.MAX_DONE_TEXT_CHARS);
    if (P.HTML_INJECTION_RE.test(text) || P.JS_INJECTION_RE.test(text)) {
      return { ok: false, failureCode: 'invalid_action' };
    }
    for (let i = 0; i < P.DECEPTIVE_DONE_PATTERNS.length; i++) {
      if (P.DECEPTIVE_DONE_PATTERNS[i].test(text)) {
        return { ok: false, failureCode: 'invalid_action' };
      }
    }
    return {
      ok: true,
      name: name,
      value: { done: { text: text, success: !!input.success } },
    };
  }

  return { ok: false, failureCode: 'unknown_action' };
}

// ── Provider request build + call ─────────────────────────────────

export function buildProviderRequestBody(config, userRequest, browserState) {
  const userContent =
    '<user_request>\n' + userRequest + '\n</user_request>\n' +
    '<browser_state>\n' + browserState + '\n</browser_state>';
  const tools = [
    {
      type: 'function',
      function: {
        name: P.MACRO_TOOL_NAME,
        description: 'Return exactly one Page Agent action as { action: {...} }.',
        parameters: P.AGENT_OUTPUT_PARAMETERS,
      },
    },
  ];
  return {
    model: config.model,
    messages: [
      { role: 'system', content: P.SYSTEM_POLICY },
      { role: 'user', content: userContent },
    ],
    temperature: 0,
    max_tokens: config.maxTokens,
    tools: tools,
    tool_choice: { type: 'function', function: { name: P.MACRO_TOOL_NAME } },
  };
}

export async function callProvider(config, body, timeoutMs) {
  let signal;
  let controller;
  try {
    if (typeof AbortSignal !== 'undefined' && AbortSignal.timeout) {
      signal = AbortSignal.timeout(timeoutMs);
    } else {
      controller = new AbortController();
      signal = controller.signal;
      setTimeout(function () {
        controller.abort();
      }, timeoutMs);
    }
  } catch (_) {
    signal = undefined;
  }
  const upstream = await fetch(config.endpoint, {
    method: 'POST',
    headers: {
      Authorization: 'Bearer ' + config.secret,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
    signal: signal,
  });
  if (!upstream.ok) {
    return { ok: false, failureCode: 'upstream_error', status: upstream.status };
  }
  let data;
  try {
    data = await upstream.json();
  } catch (_) {
    return { ok: false, failureCode: 'malformed_response' };
  }
  return { ok: true, data: data };
}

// ── Provider response validation ───────────────────────────────────

export function validateProviderResponse(data) {
  if (!data || typeof data !== 'object') {
    return { ok: false, failureCode: 'malformed_response' };
  }
  const choices = data.choices;
  if (!Array.isArray(choices) || choices.length !== 1) {
    return { ok: false, failureCode: 'malformed_response' };
  }
  const choice = choices[0];
  if (!choice || typeof choice !== 'object') {
    return { ok: false, failureCode: 'malformed_response' };
  }
  const message = choice.message;
  if (!message || typeof message !== 'object') {
    return { ok: false, failureCode: 'malformed_response' };
  }
  const toolCalls = message.tool_calls;
  if (!Array.isArray(toolCalls) || toolCalls.length !== 1) {
    return { ok: false, failureCode: 'missing_tool_call' };
  }
  const tc = toolCalls[0];
  if (!tc || !tc.function || tc.function.name !== P.MACRO_TOOL_NAME) {
    return { ok: false, failureCode: 'missing_tool_call' };
  }
  let parsed;
  try {
    parsed = JSON.parse(tc.function.arguments);
  } catch (_) {
    return { ok: false, failureCode: 'malformed_response' };
  }
  if (
    !parsed ||
    typeof parsed !== 'object' ||
    Array.isArray(parsed) ||
    !parsed.action ||
    typeof parsed.action !== 'object'
  ) {
    return { ok: false, failureCode: 'malformed_response' };
  }
  const actionKeys = Object.keys(parsed.action);
  if (actionKeys.length !== 1) {
    return { ok: false, failureCode: 'invalid_action' };
  }
  return { ok: true, action: parsed.action };
}

export function actionSignature(action) {
  const key = Object.keys(action || {})[0];
  if (!key) return '';
  const v = action[key];
  if (key === 'click_element_by_index' && v && typeof v.index === 'number') {
    return 'click:' + v.index;
  }
  return key;
}

function buildOpenAIResponse(action) {
  return {
    id: 'chatcmpl-page-agent-' + Date.now(),
    object: 'chat.completion',
    created: Math.floor(Date.now() / 1000),
    model: 'page-agent-server-adapter',
    choices: [
      {
        index: 0,
        message: {
          role: 'assistant',
          content: null,
          tool_calls: [
            {
              id: 'call_page_agent_' + Date.now(),
              type: 'function',
              function: {
                name: P.MACRO_TOOL_NAME,
                arguments: JSON.stringify({ action: action }),
              },
            },
          ],
        },
        finish_reason: 'tool_calls',
      },
    ],
    usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
  };
}

export function buildSafeDone(failureCode) {
  const text = P.SAFE_DONE_TEXT[failureCode] || P.SAFE_DONE_TEXT.general;
  return buildOpenAIResponse({ done: { text: text, success: false } });
}

// ── Entry point ───────────────────────────────────────────────────

export async function onRequest(context) {
  const request = context.request;
  const env = context.env || {};
  const requestId = newRequestId();
  const headers = corsHeaders(request);
  const config = resolveConfig(env);
  safeLog(env, {
    request_id: requestId,
    adapter_enabled: !!config.usable,
    provider: config.provider || null,
  });

  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 200, headers: headers });
  }
  if (request.method !== 'POST') {
    return jsonResponse({ error: 'method_not_allowed' }, 405, headers);
  }

  const ct = headerGet(request, 'Content-Type') || '';
  if (ct.toLowerCase().indexOf('application/json') === -1) {
    return jsonResponse({ error: 'unsupported_media_type' }, 415, headers);
  }

  const origin = headerGet(request, 'Origin') || '';

  // OPTIONS: if origin is present it must be valid; missing origin is allowed for preflight
  // POST: origin MUST be present and MUST be valid
  if (request.method === 'OPTIONS') {
    if (origin && !P.isAllowedOrigin(origin)) {
      return jsonResponse({ error: 'forbidden_origin' }, 403, headers);
    }
  } else {
    if (!origin) {
      return jsonResponse({ error: 'missing_origin' }, 403, headers);
    }
    if (!P.isAllowedOrigin(origin)) {
      return jsonResponse({ error: 'forbidden_origin' }, 403, headers);
    }
  }

  let rawText;
  try {
    rawText = await request.text();
  } catch (_) {
    return jsonResponse({ error: 'invalid_input' }, 400, headers);
  }
  const requestBytes = byteLength(rawText);
  if (requestBytes > config.maxReqBytes) {
    return jsonResponse({ error: 'payload_too_large' }, 413, headers);
  }

  let body;
  try {
    body = JSON.parse(rawText);
  } catch (_) {
    return jsonResponse({ error: 'invalid_json' }, 400, headers);
  }

  const messages = parseMessages(body);
  if (!messages) {
    return jsonResponse({ error: 'missing_messages' }, 400, headers);
  }

  const tools = Array.isArray(body.tools) ? body.tools : null;
  if (!tools || tools.length === 0) {
    return jsonResponse({ error: 'missing_tools' }, 400, headers);
  }
  const macroName =
    (tools[0] && tools[0].function && tools[0].function.name) || P.MACRO_TOOL_NAME;
  if (macroName !== P.MACRO_TOOL_NAME) {
    return jsonResponse({ error: 'wrong_macro_name' }, 400, headers);
  }

  const userText = getLastUserMessageText(messages);
  const lastMsg = messages[messages.length - 1];
  if (!lastMsg || lastMsg.role !== 'user') {
    return jsonResponse(buildSafeDone('invalid_input'), 200, headers);
  }
  const rawRequest = extractUserRequest(userText);
  if (rawRequest === null) {
    return jsonResponse(buildSafeDone('invalid_input'), 200, headers);
  }
  const userRequest = sanitizeUserRequest(rawRequest);

  const pii = P.detectUserRequestPii(userRequest);
  if (pii) {
    safeLog(env, {
      request_id: requestId,
      result_category: 'rejected',
      failure_code: 'pii_risk',
    });
    return jsonResponse(buildSafeDone('pii_risk'), 200, headers);
  }
  if (!userRequest || userRequest.length > config.maxUserReq) {
    return jsonResponse(buildSafeDone('invalid_input'), 200, headers);
  }

  const browserStateRaw = extractBrowserState(userText);
  if (browserStateRaw === null) {
    return jsonResponse(buildSafeDone('invalid_input'), 200, headers);
  }
  const browserState = redactBrowserState(browserStateRaw, config.maxBrowserState);

  const stepCount = countSteps(userText);
  if (stepCount >= config.maxSteps) {
    safeLog(env, {
      request_id: requestId,
      step_number: stepCount,
      result_category: 'rejected',
      failure_code: 'max_step',
    });
    return jsonResponse(buildSafeDone('max_step'), 200, headers);
  }
  const usedClicks = extractUsedClickIndices(userText);

  if (!config.usable) {
    safeLog(env, {
      request_id: requestId,
      adapter_enabled: false,
      result_category: 'disabled',
      failure_code: 'disabled',
    });
    return jsonResponse(buildSafeDone('disabled'), 200, headers);
  }

  const providerBody = buildProviderRequestBody(config, userRequest, browserState);
  const started = Date.now();
  let result;
  try {
    result = await callProvider(config, providerBody, config.timeoutMs);
  } catch (_) {
    result = { ok: false, failureCode: 'provider_timeout' };
  }
  const duration = Date.now() - started;

  if (!result.ok) {
    safeLog(env, {
      request_id: requestId,
      provider: config.provider,
      model: config.model,
      result_category: 'provider_error',
      failure_code: result.failureCode,
      duration_ms: duration,
      request_bytes: requestBytes,
      step_number: stepCount,
    });
    return jsonResponse(buildSafeDone(result.failureCode || 'upstream_error'), 200, headers);
  }

  const validated = validateProviderResponse(result.data);
  if (!validated.ok) {
    safeLog(env, {
      request_id: requestId,
      provider: config.provider,
      model: config.model,
      result_category: 'invalid_response',
      failure_code: validated.failureCode,
      duration_ms: duration,
      request_bytes: requestBytes,
      step_number: stepCount,
    });
    return jsonResponse(buildSafeDone(validated.failureCode || 'malformed_response'), 200, headers);
  }

  const elements = parseBrowserStateElements(browserState);
  const actionCheck = validateAction(validated.action, elements, {
    requestOrigin: origin || 'http://localhost/',
  });
  if (!actionCheck.ok) {
    safeLog(env, {
      request_id: requestId,
      provider: config.provider,
      model: config.model,
      result_category: 'rejected_action',
      failure_code: actionCheck.failureCode,
      duration_ms: duration,
      request_bytes: requestBytes,
      step_number: stepCount,
    });
    return jsonResponse(buildSafeDone(actionCheck.failureCode || 'unsafe_target'), 200, headers);
  }

  const candidateSig = actionSignature(validated.action);
  if (
    candidateSig.indexOf('click:') === 0 &&
    usedClicks.has(parseInt(candidateSig.slice(6), 10))
  ) {
    safeLog(env, {
      request_id: requestId,
      provider: config.provider,
      model: config.model,
      result_category: 'rejected',
      failure_code: 'repeated_action',
      duration_ms: duration,
      request_bytes: requestBytes,
      step_number: stepCount,
      validated_action_name: actionCheck.name,
    });
    return jsonResponse(buildSafeDone('repeated_action'), 200, headers);
  }

  safeLog(env, {
    request_id: requestId,
    provider: config.provider,
    model: config.model,
    result_category: 'success',
    duration_ms: duration,
    request_bytes: requestBytes,
    step_number: stepCount,
    validated_action_name: actionCheck.name,
  });
  return jsonResponse(buildOpenAIResponse(actionCheck.value), 200, headers);
}
