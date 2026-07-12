/**
 * scripts/validate_page_agent_live_adapter.mjs
 *
 * Controlled-live validation for the Stage 4 Page Agent server adapter.
 *
 * Gated behind:
 *   RUN_PAGE_AGENT_LIVE_VALIDATION=1
 *   PAGE_AGENT_LLM_ENABLED=true
 *   GEMINI_API_KEY or KILOCODE_API_KEY present
 *   PAGE_AGENT_LLM_PROVIDER=gemini (default) | hy3
 *
 * Validates ONE scenario with ONE provider, ONE model, bounded steps.
 * No submission, no PII, no external navigation.
 */

const RUN = process.env.RUN_PAGE_AGENT_LIVE_VALIDATION;
if (RUN !== '1') {
  console.log('[skip] RUN_PAGE_AGENT_LIVE_VALIDATION not set');
  process.exit(0);
}

const ENABLED = process.env.PAGE_AGENT_LLM_ENABLED;
if (ENABLED !== 'true') {
  console.log('[skip] PAGE_AGENT_LLM_ENABLED not true');
  process.exit(0);
}

const PROVIDER = process.env.PAGE_AGENT_LLM_PROVIDER || 'gemini';
const geminiKey = process.env.GEMINI_API_KEY;
const hy3Key = process.env.KILOCODE_API_KEY;
const hasKey = (PROVIDER === 'gemini' && geminiKey) || (PROVIDER === 'hy3' && hy3Key);

if (!hasKey) {
  console.log('[skip] no configured secret for ' + PROVIDER);
  process.exit(0);
}

// ---- import the adapter functions that can run standalone ----
const { buildProviderRequestBody, validateProviderResponse, resolveConfig } = await import(
  new URL('../functions/api/page-agent/_adapter.js', import.meta.url).pathname
);

const env = {
  PAGE_AGENT_LLM_ENABLED: 'true',
  PAGE_AGENT_LLM_PROVIDER: PROVIDER,
  PAGE_AGENT_LLM_MAX_STEPS: '3',
  ...(PROVIDER === 'gemini' ? { GEMINI_API_KEY: geminiKey } : { KILOCODE_API_KEY: hy3Key }),
};

const config = resolveConfig(env);
if (!config.usable) {
  console.log('[fail] config not usable: enabled=' + config.enabled +
    ' provider=' + config.provider + ' secret=' + !!config.secret);
  process.exit(1);
}

// ---- safe scenario: 공동주택과 연락처 찾아줘 ----
const userRequest = '공동주택과 연락처 찾아줘';
const browserState =
  '[0]<a href="#" data-action-target="nav-civil-service">종합민원</a>\n' +
  '[1]<div data-action-target="apartment-guidance-card" tabindex="0">공동주택과</div>';

const body = buildProviderRequestBody(config, userRequest, browserState);
const started = Date.now();
let result;
try {
  result = await callProvider(config, body, config.timeoutMs);
} catch (e) {
  console.log('[fail] provider threw: ' + (e.message || e));
  process.exit(1);
}
const duration = Date.now() - started;

if (!result.ok) {
  console.log('[fail] provider returned error: ' + result.failureCode);
  process.exit(1);
}

const validated = validateProviderResponse(result.data);
if (!validated.ok) {
  console.log('[fail] response validation failed: ' + validated.failureCode);
  process.exit(1);
}

const actionKey = Object.keys(validated.action)[0];
console.log('provider=' + config.provider);
console.log('model=' + config.model);
console.log('result_category=success');
console.log('validated_action_name=' + actionKey);
console.log('duration_ms=' + duration);

// Usage totals if the provider supplied them
const usage = result.data && result.data.usage;
if (usage) {
  console.log('usage_prompt_tokens=' + (usage.prompt_tokens ?? 0));
  console.log('usage_completion_tokens=' + (usage.completion_tokens ?? 0));
}

// Safe scenario should return a click or done action, never external nor submit
if (actionKey === 'done') {
  console.log('action=done (valid but unexpected for this scenario; ok for validation)');
} else if (actionKey === 'click_element_by_index') {
  const idx = validated.action.click_element_by_index.index;
  console.log('action=click_element_by_index index=' + idx);
} else {
  console.log('action=' + actionKey + ' (validated ok)');
}

console.log('PII transmitted: no');
console.log('submission performed: no');
console.log('');

async function callProvider(config, body, timeoutMs) {
  let signal;
  try {
    if (typeof AbortSignal !== 'undefined' && AbortSignal.timeout) {
      signal = AbortSignal.timeout(timeoutMs);
    } else {
      const ctrl = new AbortController();
      signal = ctrl.signal;
      setTimeout(() => ctrl.abort(), timeoutMs);
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
    signal,
  });
  if (!upstream.ok) {
    return { ok: false, failureCode: 'upstream_error' };
  }
  let data;
  try {
    data = await upstream.json();
  } catch (_) {
    return { ok: false, failureCode: 'malformed_response' };
  }
  return { ok: true, data };
}
