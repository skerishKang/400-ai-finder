from pathlib import Path

path = Path("tests/browser/verify_desktop_chat_scroll_containment_e2e.mjs")
text = path.read_text(encoding="utf-8")

helper = '''\nasync function installTurnstileDisabledStub(page) {\n  // This E2E isolates chat scroll containment. Dedicated #1224-B browser\n  // contracts own the Turnstile lifecycle, so this harness supplies the\n  // explicit no-token client shape before application scripts execute.\n  await page.addInitScript(() => {\n    window.CitizenTurnstile = Object.freeze({\n      acquireToken() { return Promise.resolve(""); },\n      reset() {},\n      cancel() {},\n    });\n  });\n}\n'''

if "async function installTurnstileDisabledStub(page)" not in text:
    anchor = "\nasync function collectCounts(page) {"
    if text.count(anchor) != 1:
        raise SystemExit(f"unexpected helper anchor count: {text.count(anchor)}")
    text = text.replace(anchor, helper + anchor, 1)

page_anchor = "  const page = await context.newPage();\n  safety.attach(page);"
replacement = (
    "  const page = await context.newPage();\n"
    "  await installTurnstileDisabledStub(page);\n"
    "  safety.attach(page);"
)

if "await installTurnstileDisabledStub(page);" not in text:
    count = text.count(page_anchor)
    if count != 2:
        raise SystemExit(f"unexpected page anchor count: {count}")
    text = text.replace(page_anchor, replacement)
else:
    call_count = text.count("await installTurnstileDisabledStub(page);")
    if call_count != 2:
        raise SystemExit(f"unexpected existing stub call count: {call_count}")

path.write_text(text, encoding="utf-8")
print("#1224-B scroll Turnstile isolation applied")
