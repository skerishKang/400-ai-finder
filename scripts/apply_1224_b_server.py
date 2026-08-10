from pathlib import Path


def replace_once(path, old, new):
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected 1 anchor, found {count}: {old[:100]!r}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


safety = Path('functions/api/mvp/request-safety.js')
ask = Path('functions/api/mvp/ask.js')
test = Path('tests/functions/test_cloudflare_mvp_ask_contract.mjs')

replace_once(
    safety,
    "export const DEFAULT_MAX_BODY_BYTES = 8192;\n",
    "import { TURNSTILE_MAX_TOKEN_CHARS } from './turnstile.js';\n\nexport const DEFAULT_MAX_BODY_BYTES = 8192;\n",
)
replace_once(
    safety,
    "export const ALLOWED_REQUEST_FIELDS = Object.freeze(['question', 'locale', 'session_id']);",
    "export const ALLOWED_REQUEST_FIELDS = Object.freeze(['question', 'locale', 'session_id', 'turnstile_token']);",
)
replace_once(
    safety,
    "  if (typeof body.session_id === 'string' && !SESSION_ID_RE.test(body.session_id)) {\n    return { ok: false, failureCode: 'invalid_input', reason: 'session_id_format' };\n  }\n  return { ok: true };",
    "  if (typeof body.session_id === 'string' && !SESSION_ID_RE.test(body.session_id)) {\n    return { ok: false, failureCode: 'invalid_input', reason: 'session_id_format' };\n  }\n  if (Object.prototype.hasOwnProperty.call(body, 'turnstile_token') && typeof body.turnstile_token !== 'string') {\n    return { ok: false, failureCode: 'invalid_input', reason: 'turnstile_token_type' };\n  }\n  if (typeof body.turnstile_token === 'string' && body.turnstile_token.length > TURNSTILE_MAX_TOKEN_CHARS) {\n    return { ok: false, failureCode: 'invalid_input', reason: 'turnstile_token_too_long' };\n  }\n  return { ok: true };",
)

replace_once(
    ask,
    "} from './request-safety.js';\n\n// Cloudflare Pages Function",
    "} from './request-safety.js';\nimport { verifyTurnstileRequest } from './turnstile.js';\n\n// Cloudflare Pages Function",
)

for old, new in [
    (
        "    too_long: '질문이 너무 깁니다. 300자 이내로 입력해 주세요.',",
        "    too_long: '질문이 너무 깁니다. 300자 이내로 입력해 주세요.',\n    bot_verification_required: 'AI 안내를 사용하려면 보안 확인을 완료해 주세요.',\n    bot_verification_failed: '보안 확인이 만료되었거나 유효하지 않습니다. 다시 확인해 주세요.',\n    bot_verification_unavailable: '현재 보안 확인 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.',\n    bot_verification_config_error: '현재 AI 보안 확인 설정을 점검하고 있습니다.',",
    ),
    (
        "    too_long: 'Your question is too long. Please keep it within 300 characters.',",
        "    too_long: 'Your question is too long. Please keep it within 300 characters.',\n    bot_verification_required: 'Please complete the security check before using the AI guide.',\n    bot_verification_failed: 'The security check is invalid or expired. Please verify again.',\n    bot_verification_unavailable: 'The security check service is temporarily unavailable. Please try again.',\n    bot_verification_config_error: 'The AI security check configuration is being reviewed.',",
    ),
    (
        "    too_long: 'Câu hỏi quá dài. Vui lòng nhập dưới 300 ký tự.',",
        "    too_long: 'Câu hỏi quá dài. Vui lòng nhập dưới 300 ký tự.',\n    bot_verification_required: 'Vui lòng hoàn tất bước kiểm tra bảo mật trước khi dùng hướng dẫn AI.',\n    bot_verification_failed: 'Kiểm tra bảo mật không hợp lệ hoặc đã hết hạn. Vui lòng xác minh lại.',\n    bot_verification_unavailable: 'Dịch vụ kiểm tra bảo mật tạm thời không khả dụng. Vui lòng thử lại.',\n    bot_verification_config_error: 'Đang kiểm tra cấu hình bảo mật của hướng dẫn AI.',",
    ),
    (
        "    too_long: 'คำถามยาวเกินไป โปรดระบุไม่เกิน 300 ตัวอักษร',",
        "    too_long: 'คำถามยาวเกินไป โปรดระบุไม่เกิน 300 ตัวอักษร',\n    bot_verification_required: 'โปรดยืนยันความปลอดภัยก่อนใช้คำแนะนำ AI',\n    bot_verification_failed: 'การยืนยันความปลอดภัยไม่ถูกต้องหรือหมดอายุ โปรดยืนยันอีกครั้ง',\n    bot_verification_unavailable: 'บริการยืนยันความปลอดภัยไม่พร้อมใช้งานชั่วคราว โปรดลองอีกครั้ง',\n    bot_verification_config_error: 'กำลังตรวจสอบการตั้งค่าความปลอดภัยของคำแนะนำ AI',",
    ),
    (
        "    too_long: 'Pertanyaan terlalu panjang. Mohon batasi di bawah 300 karakter.',",
        "    too_long: 'Pertanyaan terlalu panjang. Mohon batasi di bawah 300 karakter.',\n    bot_verification_required: 'Selesaikan pemeriksaan keamanan sebelum menggunakan panduan AI.',\n    bot_verification_failed: 'Pemeriksaan keamanan tidak valid atau telah kedaluwarsa. Silakan verifikasi lagi.',\n    bot_verification_unavailable: 'Layanan pemeriksaan keamanan sementara tidak tersedia. Silakan coba lagi.',\n    bot_verification_config_error: 'Konfigurasi pemeriksaan keamanan panduan AI sedang ditinjau.',",
    ),
]:
    replace_once(ask, old, new)

replace_once(
    ask,
    "  let privacyMeta = {\n    sensitive_input_detected: false,\n    categories: [],\n    redacted: false,\n    session_id_present: false,\n  };\n  const headers = buildHeaders(request, requestId);",
    "  let privacyMeta = {\n    sensitive_input_detected: false,\n    categories: [],\n    redacted: false,\n    session_id_present: false,\n  };\n  let botDefenseMeta = {\n    mode: 'not_applicable',\n    verified: false,\n    bypassed: false,\n    reason: '',\n    action: '',\n    hostname: '',\n  };\n  const headers = buildHeaders(request, requestId);",
)
replace_once(
    ask,
    "      privacy: {\n        sensitive_input_detected: privacyMeta.sensitive_input_detected === true,\n        categories: Array.isArray(privacyMeta.categories) ? privacyMeta.categories.slice(0, 8) : [],\n        redacted: privacyMeta.redacted === true,\n        session_id_present: privacyMeta.session_id_present === true,\n      },\n      cost:",
    "      privacy: {\n        sensitive_input_detected: privacyMeta.sensitive_input_detected === true,\n        categories: Array.isArray(privacyMeta.categories) ? privacyMeta.categories.slice(0, 8) : [],\n        redacted: privacyMeta.redacted === true,\n        session_id_present: privacyMeta.session_id_present === true,\n      },\n      bot_defense: {\n        mode: botDefenseMeta.mode,\n        verified: botDefenseMeta.verified === true,\n        bypassed: botDefenseMeta.bypassed === true,\n        reason: botDefenseMeta.reason,\n        action: botDefenseMeta.action,\n        hostname: botDefenseMeta.hostname,\n      },\n      cost:",
)
replace_once(
    ask,
    "        retryable: decorated.failure_code === 'upstream_timeout' || decorated.failure_code === 'upstream_error',",
    "        retryable: decorated.failure_code === 'upstream_timeout' ||\n          decorated.failure_code === 'upstream_error' ||\n          decorated.failure_code === 'bot_verification_unavailable',",
)
replace_once(
    ask,
    "  const privacy = assessQuestionPrivacy(rawQuestion);",
    "  if (runtimeMode.mode === 'enabled' && disabledProviders.length !== providerOrder.length) {\n    const botVerification = await verifyTurnstileRequest({\n      env,\n      requestHostname: reqHostname,\n      token: body.turnstile_token,\n      fetchWithDeadline,\n      remainingRequestBudgetMs: remainingRequestBudgetMs(),\n    });\n    botDefenseMeta = {\n      mode: botVerification.bypassed ? 'disabled' : 'required',\n      verified: botVerification.verified === true,\n      bypassed: botVerification.bypassed === true,\n      reason: botVerification.reason || '',\n      action: botVerification.action || '',\n      hostname: botVerification.hostname || '',\n    };\n    if (!botVerification.ok) {\n      return jsonResponse(withRuntimeMeta(Object.assign(\n        failurePayload('', primaryConfig.provider, primaryConfig.model, botVerification.failureCode, retrievedAt, currentTime, requestLocale),\n        { answer: localizedFailureAnswer(requestLocale, botVerification.failureCode) },\n      )), botVerification.status || 403, headers);\n    }\n  } else {\n    botDefenseMeta = {\n      mode: 'not_applicable',\n      verified: false,\n      bypassed: false,\n      reason: runtimeMode.mode !== 'enabled' ? `ai_mode_${runtimeMode.mode}` : 'all_providers_disabled',\n      action: '',\n      hostname: '',\n    };\n  }\n\n  const privacy = assessQuestionPrivacy(rawQuestion);",
)

replace_once(
    test,
    "function createMockContext(method, body, envOverrides = {}, requestUrl = '') {\n  const request = {\n    method,\n    url: requestUrl,",
    "function createMockContext(method, body, envOverrides = {}, requestUrl = '') {\n  const effectiveUrl = requestUrl || 'http://localhost:8788/api/mvp/ask';\n  let effectiveBody = body;\n  let requestHost = '';\n  try { requestHost = new URL(effectiveUrl).hostname.toLowerCase(); } catch (_) { /* noop */ }\n  const isLoopback = requestHost === 'localhost' || requestHost === '127.0.0.1';\n  if (!isLoopback && method === 'POST' && typeof body === 'string') {\n    try {\n      const parsed = JSON.parse(body);\n      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed) &&\n          !Object.prototype.hasOwnProperty.call(parsed, 'turnstile_token')) {\n        parsed.turnstile_token = 'test-turnstile-token-123456';\n        effectiveBody = JSON.stringify(parsed);\n      }\n    } catch (_) {\n      // Preserve malformed JSON exactly for invalid-input contracts.\n    }\n  }\n  const request = {\n    method,\n    url: effectiveUrl,",
)
replace_once(
    test,
    "    json: async () => (body ? JSON.parse(body) : {}),\n    text: async () => (body ? String(body) : ''),\n  };\n  const env = {\n    GEMINI_API_KEY: '',\n    KILOCODE_API_KEY: '',\n    MVP_RUNTIME_LOGS: '0',\n    ...envOverrides,\n  };",
    "    json: async () => (effectiveBody ? JSON.parse(effectiveBody) : {}),\n    text: async () => (effectiveBody ? String(effectiveBody) : ''),\n  };\n  const env = {\n    GEMINI_API_KEY: '',\n    KILOCODE_API_KEY: '',\n    MVP_RUNTIME_LOGS: '0',\n    MVP_TURNSTILE_MODE: isLoopback ? 'disabled' : 'required',\n    MVP_TURNSTILE_SECRET_KEY: isLoopback ? '' : 'test-turnstile-secret',\n    MVP_TURNSTILE_EXPECTED_ACTION: 'mvp_ask',\n    MVP_TURNSTILE_ALLOWED_HOSTNAMES: isLoopback ? '' : requestHost,\n    ...envOverrides,\n  };",
)
replace_once(
    test,
    "function isOfficialFetchUrl(url) {\n  return url === 'https://bukgu.gwangju.kr/' ||\n    url.startsWith('https://search.bukgu.gwangju.kr/RSA/front/Search.jsp?');\n}\n\nfunction providerFetchCalls() {\n  return fetchCalls.filter((call) => !isOfficialFetchUrl(call.url));\n}",
    "function isOfficialFetchUrl(url) {\n  return url === 'https://bukgu.gwangju.kr/' ||\n    url.startsWith('https://search.bukgu.gwangju.kr/RSA/front/Search.jsp?');\n}\n\nfunction isTurnstileFetchUrl(url) {\n  return url === 'https://challenges.cloudflare.com/turnstile/v0/siteverify';\n}\n\nfunction providerFetchCalls() {\n  return fetchCalls.filter((call) => !isOfficialFetchUrl(call.url) && !isTurnstileFetchUrl(call.url));\n}",
)
replace_once(
    test,
    "    if (resolvedUrl === 'https://bukgu.gwangju.kr/') {\n      response = fixtures.homepageResponse || { body: DEFAULT_HOME_HTML };\n    } else if (resolvedUrl.startsWith('https://search.bukgu.gwangju.kr/RSA/front/Search.jsp?')) {\n      response = fixtures.searchResponse || { body: DEFAULT_SEARCH_HTML };\n    } else {",
    "    if (resolvedUrl === 'https://bukgu.gwangju.kr/') {\n      response = fixtures.homepageResponse || { body: DEFAULT_HOME_HTML };\n    } else if (resolvedUrl.startsWith('https://search.bukgu.gwangju.kr/RSA/front/Search.jsp?')) {\n      response = fixtures.searchResponse || { body: DEFAULT_SEARCH_HTML };\n    } else if (isTurnstileFetchUrl(resolvedUrl)) {\n      response = fixtures.turnstileResponse || {\n        body: { success: true, action: 'mvp_ask', hostname: 'cgbukku.pages.dev' },\n      };\n    } else {",
)

print('1224-B server anchors applied successfully')
