from pathlib import Path

ASK = Path('functions/api/mvp/ask.js')
TEST = Path('tests/functions/test_cloudflare_mvp_ask_contract.mjs')
ENV = Path('.env.example')


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one anchor, found {count}')
    return text.replace(old, new, 1)


ask = ASK.read_text(encoding='utf-8')
ask = replace_once(
    ask,
    "import { BUKGU_OFFICIAL_SNAPSHOTS } from './bukgu-official-snapshots.js';\n",
    "import { BUKGU_OFFICIAL_SNAPSHOTS } from './bukgu-official-snapshots.js';\n"
    "import {\n"
    "  MAX_QUESTION_CHARS,\n"
    "  assessQuestionPrivacy,\n"
    "  readBoundedJsonBody,\n"
    "  validateRequestShape,\n"
    "} from './request-safety.js';\n",
    'request-safety import',
)

ask = replace_once(
    ask,
    "  const providerAttempts = [];\n  const headers = buildHeaders(request, requestId);\n",
    "  const providerAttempts = [];\n"
    "  let privacyMeta = {\n"
    "    sensitive_input_detected: false,\n"
    "    categories: [],\n"
    "    redacted: false,\n"
    "    session_id_present: false,\n"
    "  };\n"
    "  const headers = buildHeaders(request, requestId);\n",
    'privacy meta init',
)

ask = replace_once(
    ask,
    "      disabled_providers: disabledProviders.slice(),\n      cost: {\n",
    "      disabled_providers: disabledProviders.slice(),\n"
    "      privacy: {\n"
    "        sensitive_input_detected: privacyMeta.sensitive_input_detected === true,\n"
    "        categories: Array.isArray(privacyMeta.categories) ? privacyMeta.categories.slice(0, 8) : [],\n"
    "        redacted: privacyMeta.redacted === true,\n"
    "        session_id_present: privacyMeta.session_id_present === true,\n"
    "      },\n"
    "      cost: {\n",
    'privacy meta envelope',
)

old_parse = """  let body;\n  try {\n    body = await request.json();\n  } catch (_) {\n    return jsonResponse(withRuntimeMeta(Object.assign(\n      failurePayload('', primaryConfig.provider, primaryConfig.model, 'invalid_input', retrievedAt, currentTime, 'ko'),\n      { answer: localizedFailureAnswer('ko', 'invalid_input') },\n    )), 200, headers);\n  }\n\n  const requestLocale = normalizeLocale(body && typeof body.locale === 'string' ? body.locale : 'ko');\n\n  if (!body || typeof body !== 'object' || Array.isArray(body) || typeof body.question !== 'string') {\n    if (body && typeof body === 'object' && !Array.isArray(body) && !Object.prototype.hasOwnProperty.call(body, 'question')) {\n      return jsonResponse(withRuntimeMeta({ ok: false, error: 'Missing question' }), 400, headers);\n    }\n    return jsonResponse(withRuntimeMeta(Object.assign(\n      failurePayload('', primaryConfig.provider, primaryConfig.model, 'invalid_input', retrievedAt, currentTime, requestLocale),\n      { answer: localizedFailureAnswer(requestLocale, 'invalid_input') },\n    )), 200, headers);\n  }\n\n  const question = body.question.trim();\n  if (!question) return jsonResponse(withRuntimeMeta({ ok: false, error: 'Missing question' }), 400, headers);\n  if (question.length > 300) {\n    return jsonResponse(withRuntimeMeta(Object.assign(\n      failurePayload(question, primaryConfig.provider, primaryConfig.model, 'invalid_input', retrievedAt, currentTime, requestLocale),\n      { answer: localizedFailureAnswer(requestLocale, 'too_long') },\n    )), 200, headers);\n  }\n"""

new_parse = """  const ingress = await readBoundedJsonBody(request, env);\n  if (!ingress.ok) {\n    const ingressFailure = failurePayload(\n      '',\n      primaryConfig.provider,\n      primaryConfig.model,\n      ingress.failureCode || 'invalid_input',\n      retrievedAt,\n      currentTime,\n      'ko',\n    );\n    ingressFailure.answer = localizedFailureAnswer('ko', 'invalid_input');\n    return jsonResponse(withRuntimeMeta(ingressFailure), ingress.status || 200, headers);\n  }\n\n  const body = ingress.body;\n  const requestLocale = normalizeLocale(body && typeof body.locale === 'string' ? body.locale : 'ko');\n  const shape = validateRequestShape(body);\n  if (!shape.ok) {\n    if (shape.reason === 'missing_question') {\n      return jsonResponse(withRuntimeMeta({ ok: false, error: 'Missing question' }), 400, headers);\n    }\n    return jsonResponse(withRuntimeMeta(Object.assign(\n      failurePayload('', primaryConfig.provider, primaryConfig.model, 'invalid_input', retrievedAt, currentTime, requestLocale),\n      { answer: localizedFailureAnswer(requestLocale, 'invalid_input') },\n    )), shape.status || 200, headers);\n  }\n\n  const rawQuestion = body.question.trim();\n  if (!rawQuestion) return jsonResponse(withRuntimeMeta({ ok: false, error: 'Missing question' }), 400, headers);\n  if (rawQuestion.length > MAX_QUESTION_CHARS) {\n    return jsonResponse(withRuntimeMeta(Object.assign(\n      failurePayload(rawQuestion, primaryConfig.provider, primaryConfig.model, 'invalid_input', retrievedAt, currentTime, requestLocale),\n      { answer: localizedFailureAnswer(requestLocale, 'too_long') },\n    )), 200, headers);\n  }\n\n  const privacy = assessQuestionPrivacy(rawQuestion);\n  privacyMeta = {\n    sensitive_input_detected: privacy.categories.length > 0,\n    categories: privacy.categories.slice(),\n    redacted: privacy.redacted === true,\n    session_id_present: typeof body.session_id === 'string' && body.session_id.length > 0,\n  };\n  if (!privacy.ok) {\n    return jsonResponse(withRuntimeMeta(Object.assign(\n      failurePayload('', primaryConfig.provider, primaryConfig.model, privacy.failureCode || 'sensitive_input_rejected', retrievedAt, currentTime, requestLocale),\n      { answer: localizedFailureAnswer(requestLocale, 'invalid_input') },\n    )), 200, headers);\n  }\n  const question = privacy.question;\n"""

ask = replace_once(ask, old_parse, new_parse, 'ingress parser block')

ask = replace_once(
    ask,
    "    token_usage: sanitizeNormalizedTokenUsage(meta.token_usage),\n    cost: meta.cost && typeof meta.cost === 'object'\n",
    "    token_usage: sanitizeNormalizedTokenUsage(meta.token_usage),\n"
    "    privacy: {\n"
    "      sensitive_input_detected: Boolean(meta.privacy && meta.privacy.sensitive_input_detected),\n"
    "      categories: meta.privacy && Array.isArray(meta.privacy.categories)\n"
    "        ? meta.privacy.categories.filter((value) => typeof value === 'string').slice(0, 8)\n"
    "        : [],\n"
    "      redacted: Boolean(meta.privacy && meta.privacy.redacted),\n"
    "      session_id_present: Boolean(meta.privacy && meta.privacy.session_id_present),\n"
    "    },\n"
    "    cost: meta.cost && typeof meta.cost === 'object'\n",
    'sanitized log privacy',
)

ASK.write_text(ask, encoding='utf-8', newline='\n')

test = TEST.read_text(encoding='utf-8')
marker = "await import('./test_cloudflare_mvp_request_safety_contract.mjs');"
if marker not in test:
    test = test.rstrip() + "\n\n// #1224-A request byte/schema/privacy boundary contracts.\n" + marker + "\n"
TEST.write_text(test, encoding='utf-8', newline='\n')

env = ENV.read_text(encoding='utf-8')
section = """\n# --- Public MVP request safety (#1224-A) ---\n# Application-level JSON request body limit. Valid range: 1024..32768 bytes.\n# Invalid/out-of-range values fall back to the safe 8192-byte default.\nMVP_MAX_BODY_BYTES=8192\n"""
if 'MVP_MAX_BODY_BYTES=' not in env:
    env = env.rstrip() + "\n" + section
ENV.write_text(env, encoding='utf-8', newline='\n')

print('1224-A anchors applied successfully')
