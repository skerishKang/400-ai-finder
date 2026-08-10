from pathlib import Path

ASK = Path('functions/api/mvp/ask.js')
BRIDGE = Path('src/web/static/citizen-mvp-bridge.js')
SAFETY_TEST = Path('tests/functions/test_cloudflare_mvp_request_safety_contract.mjs')
FUNCTION_TEST = Path('tests/functions/test_cloudflare_mvp_ask_contract.mjs')


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one anchor, found {count}')
    return text.replace(old, new, 1)


ask = ASK.read_text(encoding='utf-8')
ask = replace_once(
    ask,
    "failurePayload(rawQuestion, primaryConfig.provider, primaryConfig.model, 'invalid_input', retrievedAt, currentTime, requestLocale),",
    "failurePayload('', primaryConfig.provider, primaryConfig.model, 'invalid_input', retrievedAt, currentTime, requestLocale),",
    'too-long raw question echo',
)
ASK.write_text(ask, encoding='utf-8', newline='\n')

bridge = BRIDGE.read_text(encoding='utf-8')
bridge = replace_once(
    bridge,
    '  var _controller = null;\n',
    '''  var _controller = null;\n  var SESSION_STORAGE_KEY = "citizen_mvp_anonymous_session_id";\n  var _sessionIdMemory = "";\n\n  function _safeSessionId(value) {\n    var text = typeof value === "string" ? value.trim() : "";\n    return /^[A-Za-z0-9_-]{16,128}$/.test(text) ? text : "";\n  }\n\n  function _generateSessionId() {\n    var cryptoObj = window.crypto;\n    if (cryptoObj && typeof cryptoObj.randomUUID === "function") {\n      var uuid = _safeSessionId(cryptoObj.randomUUID());\n      if (uuid) return uuid;\n    }\n    if (cryptoObj && typeof cryptoObj.getRandomValues === "function") {\n      var bytes = new Uint8Array(16);\n      cryptoObj.getRandomValues(bytes);\n      return "sid_" + Array.prototype.map.call(bytes, function (value) {\n        return value.toString(16).padStart(2, "0");\n      }).join("");\n    }\n    // Compatibility fallback only. Anonymous session IDs are not an auth or\n    // rate-limit boundary by themselves and never derive from resident input.\n    return ("sid_" + Date.now().toString(36) + "_" +\n      Math.random().toString(36).slice(2).padEnd(24, "0")).slice(0, 128);\n  }\n\n  function _anonymousSessionId() {\n    var memoryId = _safeSessionId(_sessionIdMemory);\n    if (memoryId) return memoryId;\n    try {\n      if (window.sessionStorage && typeof window.sessionStorage.getItem === "function") {\n        var stored = _safeSessionId(window.sessionStorage.getItem(SESSION_STORAGE_KEY));\n        if (stored) {\n          _sessionIdMemory = stored;\n          return stored;\n        }\n      }\n    } catch (_) {\n      // Storage can be unavailable in privacy modes; use page-lifetime memory.\n    }\n    var generated = _safeSessionId(_generateSessionId());\n    if (!generated) {\n      generated = "sid_fallback_0000000000000000";\n    }\n    _sessionIdMemory = generated;\n    try {\n      if (window.sessionStorage && typeof window.sessionStorage.setItem === "function") {\n        window.sessionStorage.setItem(SESSION_STORAGE_KEY, generated);\n      }\n    } catch (_) {\n      // Page-lifetime memory remains the fallback; never use localStorage.\n    }\n    return generated;\n  }\n''',
    'anonymous session helpers',
)
bridge = replace_once(
    bridge,
    '    var requestLocale = _captureLocale();\n\n    var fetchOpts = {\n',
    '    var requestLocale = _captureLocale();\n    var sessionId = _anonymousSessionId();\n\n    var fetchOpts = {\n',
    'capture session id',
)
bridge = replace_once(
    bridge,
    '      body: JSON.stringify({ question: question || "", locale: requestLocale }),\n',
    '      body: JSON.stringify({ question: question || "", locale: requestLocale, session_id: sessionId }),\n',
    'request session field',
)
BRIDGE.write_text(bridge, encoding='utf-8', newline='\n')

safety_test = SAFETY_TEST.read_text(encoding='utf-8')
stream_test = '''await check('streamed body stops reading and cancels after byte cap', async () => {\n  const chunks = [new Uint8Array(700), new Uint8Array(700), new Uint8Array(700)];\n  let index = 0;\n  let cancelled = false;\n  const request = {\n    headers: new Headers({ 'Content-Type': 'application/json' }),\n    body: {\n      getReader() {\n        return {\n          async read() {\n            if (index >= chunks.length) return { done: true, value: undefined };\n            return { done: false, value: chunks[index++] };\n          },\n          async cancel() { cancelled = true; },\n        };\n      },\n    },\n    text: async () => { throw new Error('stream path should not call text()'); },\n  };\n  const result = await safety.readBoundedJsonBody(request, { MVP_MAX_BODY_BYTES: '1024' });\n  equal(result.status, 413, 'status');\n  equal(result.failureCode, 'payload_too_large', 'failure');\n  equal(cancelled, true, 'reader cancelled');\n  equal(index, 2, 'chunks read before rejection');\n});\n\n'''
if "streamed body stops reading and cancels after byte cap" not in safety_test:
    safety_test = replace_once(
        safety_test,
        "await check('malformed JSON is invalid_input', async () => {\n",
        stream_test + "await check('malformed JSON is invalid_input', async () => {\n",
        'stream test insertion',
    )
SAFETY_TEST.write_text(safety_test, encoding='utf-8', newline='\n')

function_test = FUNCTION_TEST.read_text(encoding='utf-8')
bridge_import = "await import('./test_citizen_mvp_bridge_session_contract.mjs');"
if bridge_import not in function_test:
    function_test = function_test.rstrip() + "\n\n// #1224-A browser anonymous-session contract.\n" + bridge_import + "\n"
FUNCTION_TEST.write_text(function_test, encoding='utf-8', newline='\n')

print('1224-A follow-up anchors applied successfully')
