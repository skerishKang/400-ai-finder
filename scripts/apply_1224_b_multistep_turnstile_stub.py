from pathlib import Path

path = Path('tests/browser/verify_mobile_multistep_composer_e2e.mjs')
text = path.read_text(encoding='utf-8')

helper_anchor = '''async function measureSnapshot(page, label) {\n  return measureNow(page, label);\n}\n\n'''
helper = '''async function measureSnapshot(page, label) {\n  return measureNow(page, label);\n}\n\nasync function installTurnstileDisabledStub(page) {\n  // This E2E isolates composer/multistep behavior. The Turnstile lifecycle is\n  // covered by dedicated #1224-B browser contracts, so this harness uses the\n  // explicit no-token client shape before application scripts execute.\n  await page.addInitScript(() => {\n    window.CitizenTurnstile = Object.freeze({\n      acquireToken() { return Promise.resolve(\"\"); },\n      reset() {},\n      cancel() {},\n    });\n  });\n}\n\n'''
if helper in text:
    print('helper already applied')
elif text.count(helper_anchor) == 1:
    text = text.replace(helper_anchor, helper, 1)
else:
    raise SystemExit(f'helper anchor mismatch: {text.count(helper_anchor)}')

call_anchor = '''  const page = await context.newPage();\n  safety.attach(page);\n  await installRoutes(page, origin);\n'''
call_replacement = '''  const page = await context.newPage();\n  await installTurnstileDisabledStub(page);\n  safety.attach(page);\n  await installRoutes(page, origin);\n'''
current = text.count(call_anchor)
applied = text.count(call_replacement)
if applied == 2:
    print('page stubs already applied')
elif current == 2 and applied == 0:
    text = text.replace(call_anchor, call_replacement)
else:
    raise SystemExit(f'page anchor mismatch old={current} new={applied}')

path.write_text(text, encoding='utf-8')
print('1224-B multistep Turnstile isolation applied')
