import {
  buildTurnstileClientConfig,
  requestHostnameFromUrl,
} from './turnstile.js';

function json(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
    },
  });
}

export function onRequestGet(context) {
  const request = context && context.request;
  const env = context && context.env ? context.env : {};
  const config = buildTurnstileClientConfig(env, requestHostnameFromUrl(request));
  if (!config.ok && config.enabled) {
    return json({
      ok: false,
      enabled: true,
      configured: false,
      mode: config.mode,
      failure_code: 'bot_verification_config_error',
      action: config.action,
      site_key: '',
    }, 503);
  }
  return json({
    ok: true,
    enabled: config.enabled,
    configured: config.configured,
    mode: config.mode,
    action: config.action,
    site_key: config.site_key,
  }, 200);
}

export function onRequest(context) {
  const method = context && context.request ? context.request.method : '';
  if (method !== 'GET') {
    return json({ ok: false, error: 'Method not allowed' }, 405);
  }
  return onRequestGet(context);
}
