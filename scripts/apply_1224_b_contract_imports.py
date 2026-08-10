from pathlib import Path


def ensure_once(path, old, new, label):
    text = path.read_text(encoding='utf-8')
    new_count = text.count(new)
    if new_count == 1:
        print(f'{label}: already applied')
        return False
    if new_count > 1:
        raise SystemExit(f'{label}: expected at most one applied anchor, found {new_count}')
    old_count = text.count(old)
    if old_count != 1:
        raise SystemExit(f'{label}: expected one old anchor, found {old_count}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
    print(f'{label}: applied')
    return True


path = Path('tests/functions/test_cloudflare_mvp_ask_contract.mjs')
old = "// #1224-A browser anonymous-session contract.\nawait import('./test_citizen_mvp_bridge_session_contract.mjs');"
new = """// #1224-A browser anonymous-session contract.
await import('./test_citizen_mvp_bridge_session_contract.mjs');

// #1224-B Turnstile server validation primitives.
await import('./test_cloudflare_mvp_turnstile_contract.mjs');

// #1224-B protected request -> Siteverify -> provider integration.
await import('./test_cloudflare_mvp_turnstile_integration_contract.mjs');

// #1224-B browser challenge lifecycle and fresh-token contract.
await import('./test_citizen_mvp_turnstile_contract.mjs');"""
ensure_once(path, old, new, 'Function contract imports')

integration = Path('tests/functions/test_cloudflare_mvp_turnstile_integration_contract.mjs')
ensure_once(
    integration,
    "function providerResponse(answer = '북구청 여권 안내입니다.') {",
    "function providerResponse(answer = '여권 발급 안내입니다.') {",
    'provider success fixture',
)

privacy = Path('tests/functions/test_cloudflare_mvp_request_safety_contract.mjs')
ensure_once(
    privacy,
    "    url: 'https://cgbukku.pages.dev/api/mvp/ask',",
    "    url: 'http://localhost:8788/api/mvp/ask',",
    'privacy loopback URL',
)
ensure_once(
    privacy,
    "      MVP_RUNTIME_LOGS: '0',\n      ...env,",
    "      MVP_RUNTIME_LOGS: '0',\n      MVP_TURNSTILE_MODE: 'disabled',\n      ...env,",
    'privacy Turnstile isolation',
)

print('1224-B contract applicator complete')
