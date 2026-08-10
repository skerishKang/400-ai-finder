from pathlib import Path

path = Path('tests/functions/test_cloudflare_mvp_ask_contract.mjs')
text = path.read_text(encoding='utf-8')
old = "// #1224-A browser anonymous-session contract.\nawait import('./test_citizen_mvp_bridge_session_contract.mjs');"
new = """// #1224-A browser anonymous-session contract.
await import('./test_citizen_mvp_bridge_session_contract.mjs');

// #1224-B Turnstile server validation primitives.
await import('./test_cloudflare_mvp_turnstile_contract.mjs');

// #1224-B protected request -> Siteverify -> provider integration.
await import('./test_cloudflare_mvp_turnstile_integration_contract.mjs');

// #1224-B browser challenge lifecycle and fresh-token contract.
await import('./test_citizen_mvp_turnstile_contract.mjs');"""
count = text.count(old)
if count != 1:
    raise SystemExit(f'expected one import anchor, found {count}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')

integration = Path('tests/functions/test_cloudflare_mvp_turnstile_integration_contract.mjs')
integration_text = integration.read_text(encoding='utf-8')
old_fixture = "function providerResponse(answer = '북구청 여권 안내입니다.') {"
new_fixture = "function providerResponse(answer = '여권 발급 안내입니다.') {"
count = integration_text.count(old_fixture)
if count != 1:
    raise SystemExit(f'expected one provider fixture anchor, found {count}')
integration.write_text(integration_text.replace(old_fixture, new_fixture, 1), encoding='utf-8')

privacy = Path('tests/functions/test_cloudflare_mvp_request_safety_contract.mjs')
privacy_text = privacy.read_text(encoding='utf-8')
old_url = "    url: 'https://cgbukku.pages.dev/api/mvp/ask',"
new_url = "    url: 'http://localhost:8788/api/mvp/ask',"
count = privacy_text.count(old_url)
if count != 1:
    raise SystemExit(f'expected one privacy URL anchor, found {count}')
privacy_text = privacy_text.replace(old_url, new_url, 1)
old_env = "      MVP_RUNTIME_LOGS: '0',\n      ...env,"
new_env = "      MVP_RUNTIME_LOGS: '0',\n      MVP_TURNSTILE_MODE: 'disabled',\n      ...env,"
count = privacy_text.count(old_env)
if count != 1:
    raise SystemExit(f'expected one privacy env anchor, found {count}')
privacy.write_text(privacy_text.replace(old_env, new_env, 1), encoding='utf-8')

print('1224-B contract imports, fixtures, and privacy isolation applied successfully')
