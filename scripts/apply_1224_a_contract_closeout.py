from pathlib import Path

ASK = Path('functions/api/mvp/ask.js')
SAFETY_TEST = Path('tests/functions/test_cloudflare_mvp_request_safety_contract.mjs')
RUNTIME_DOC = Path('docs/operations/MVP_AI_RUNTIME_CONTRACT.md')
SECURITY_DOC = Path('docs/operations/PUBLIC_AI_API_SECURITY_AND_PRIVACY.md')


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one anchor, found {count}')
    return text.replace(old, new, 1)


ask = ASK.read_text(encoding='utf-8')
ask = replace_once(
    ask,
    '  MAX_QUESTION_CHARS,\n  assessQuestionPrivacy,\n',
    '  MAX_QUESTION_CHARS,\n  SENSITIVE_CATEGORIES,\n  assessQuestionPrivacy,\n',
    'sensitive category import',
)
ask = replace_once(
    ask,
    ".filter((value) => typeof value === 'string').slice(0, 8)",
    ".filter((value) => typeof value === 'string' && SENSITIVE_CATEGORIES.includes(value)).slice(0, 8)",
    'log category allowlist',
)
ASK.write_text(ask, encoding='utf-8', newline='\n')

runtime = RUNTIME_DOC.read_text(encoding='utf-8')
runtime = replace_once(
    runtime,
    '| missing/blank question | 400 | `ok:false` |\n| malformed JSON / invalid typed input | 200 | `ok:false`, `failure_code:"invalid_input"` |\n',
    '| missing/blank question | 400 | `ok:false` |\n'
    '| non-JSON media type | 415 | `ok:false`, `failure_code:"unsupported_media_type"` |\n'
    '| request body exceeds configured byte cap | 413 | `ok:false`, `failure_code:"payload_too_large"` |\n'
    '| malformed JSON / invalid typed input | 200 | `ok:false`, `failure_code:"invalid_input"` |\n'
    '| resident-ID-like or fully-redacted high-risk input | 200 | `ok:false`, `failure_code:"sensitive_input_rejected"` |\n',
    'HTTP status table',
)
runtime = replace_once(
    runtime,
    '- `invalid_input`\n- `service_disabled`\n',
    '- `invalid_input`\n- `unsupported_media_type`\n- `payload_too_large`\n- `sensitive_input_rejected`\n- `service_disabled`\n',
    'failure vocabulary',
)
runtime = replace_once(
    runtime,
    'Future public-API controls such as media-type/body-byte rejection, rate limiting, challenge verification, or infrastructure-unavailable responses are owned by #1224. If they introduce 4xx/5xx statuses, the corresponding status + `failure_code` mapping must be documented and contract-tested before deployment.\n',
    '''#1224-A establishes the public request-ingress boundary:\n\n- `Content-Type` must be `application/json`;\n- the default application body limit is 8,192 bytes; `MVP_MAX_BODY_BYTES` may override it only within 1,024..32,768 bytes and invalid values fall back to 8,192;\n- `Content-Length` is rejected before body read when it already exceeds the cap; streamed request bodies are cancelled as soon as accumulated bytes exceed the cap;\n- the separate semantic question limit remains 300 characters;\n- the accepted top-level request fields are only `question`, optional `locale`, and optional `session_id`;\n- `session_id` is a pseudonymous correlation/rate-limit input, not authentication, and its raw value is not emitted in runtime metadata/logs;\n- resident-ID-like input fails closed before provider execution; phone/email/precise-address-like spans are redacted before provider execution.\n\nThe new ingress/privacy failures are non-retryable. Later #1224 rate-limit, challenge-verification, durable budget, and infrastructure controls must add their own documented status + `failure_code` mappings before deployment.\n''',
    '1224 future paragraph',
)
RUNTIME_DOC.write_text(runtime, encoding='utf-8', newline='\n')

security = SECURITY_DOC.read_text(encoding='utf-8')
insert = '''\nCurrent #1224-A request-boundary values:\n\n- default body cap: `8192` bytes\n- operator override: `MVP_MAX_BODY_BYTES`, accepted only from `1024` through `32768` bytes\n- invalid/out-of-range override: fail-safe fallback to `8192` bytes\n- question semantic limit: `300` characters, independent of body bytes\n- accepted top-level fields: `question`, optional `locale`, optional `session_id`\n- anonymous browser session: random/pseudonymous, `sessionStorage` only, page-memory fallback, never `localStorage`\n\nThese numbers cover request ingress only. Rate, concurrency, challenge, and provider budget values remain separate #1224 slices and must not be inferred from this body-size policy.\n'''
anchor = '- Content-Type과 method를 제한한다.\n'
if 'Current #1224-A request-boundary values:' not in security:
    security = replace_once(security, anchor, anchor + insert, 'security numeric policy')
SECURITY_DOC.write_text(security, encoding='utf-8', newline='\n')

test = SAFETY_TEST.read_text(encoding='utf-8')
extra = '''await check('too-long input never echoes raw sensitive text', async () => {\n  const rawPhone = '010-1234-5678';\n  const question = rawPhone + ' ' + 'x'.repeat(301);\n  const { data } = await invoke(JSON.stringify({ question, locale: 'ko' }));\n  equal(data.ok, false, 'ok');\n  equal(data.failure_code, 'invalid_input', 'failure_code');\n  if (String(data.question || '').includes(rawPhone)) throw new Error('raw phone echoed in too-long failure');\n});\n\nawait check('new ingress/privacy failures are explicitly non-retryable', async () => {\n  const wrongTypeRequest = makeRequest(JSON.stringify({ question: '안내' }), { 'Content-Type': 'text/plain' });\n  const wrongTypeResponse = await askModule.onRequest({ request: wrongTypeRequest, env: { MVP_RUNTIME_LOGS: '0' } });\n  const wrongType = JSON.parse(await wrongTypeResponse.text());\n  equal(wrongType.error.retryable, false, 'unsupported media retryable');\n\n  const largeBody = JSON.stringify({ question: '가'.repeat(400) });\n  const large = await invoke(largeBody, { MVP_MAX_BODY_BYTES: '1024' });\n  equal(large.data.error.retryable, false, 'payload too large retryable');\n\n  const sensitive = await invoke(JSON.stringify({ question: '주민번호 900101-1234567', locale: 'ko' }));\n  equal(sensitive.data.error.retryable, false, 'sensitive input retryable');\n});\n\nawait check('sanitized runtime log allowlists privacy categories and excludes raw sensitive data', async () => {\n  const rawEmail = 'secret.person@example.com';\n  const log = askModule.buildSanitizedRuntimeLog({\n    ok: false,\n    question: rawEmail,\n    answer: rawEmail,\n    failure_code: 'sensitive_input_rejected',\n    meta: {\n      privacy: {\n        sensitive_input_detected: true,\n        categories: ['email_like', rawEmail],\n        redacted: true,\n        session_id_present: true,\n      },\n    },\n  });\n  const serialized = JSON.stringify(log);\n  if (serialized.includes(rawEmail)) throw new Error('raw sensitive value leaked into runtime log');\n  equal(log.privacy.categories.length, 1, 'privacy category count');\n  equal(log.privacy.categories[0], 'email_like', 'privacy category');\n});\n\n'''
if "too-long input never echoes raw sensitive text" not in test:
    test = replace_once(
        test,
        "globalThis.fetch = ORIGINAL_FETCH;\n",
        extra + "globalThis.fetch = ORIGINAL_FETCH;\n",
        'privacy closeout tests',
    )
SAFETY_TEST.write_text(test, encoding='utf-8', newline='\n')

print('1224-A contract closeout anchors applied successfully')
