from pathlib import Path

STUB = '''  await page.addInitScript(() => {\n    window.CitizenTurnstile = Object.freeze({\n      acquireToken() { return Promise.resolve(\"\"); },\n      reset() {},\n      cancel() {},\n    });\n  });\n'''


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        print(f"already patched: {path}")
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, got {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched: {path}")


replace_once(
    "tests/browser/verify_housing_quest_e2e.mjs",
    '  const page = await context.newPage();\n  page.on("request",',
    '  const page = await context.newPage();\n' + STUB + '  page.on("request",',
)

replace_once(
    "tests/browser/verify_mayor_writing_e2e.mjs",
    '  const page = await context.newPage();\n  const errors = [];',
    '  const page = await context.newPage();\n' + STUB + '  const errors = [];',
)

replace_once(
    "tests/browser/verify_two_stage_bilingual_draft_e2e.mjs",
    'async function mockMayorAsk(page) {\n  await page.route("**/api/mvp/ask", async (route) => {',
    'async function mockMayorAsk(page) {\n' + STUB + '  await page.route("**/api/mvp/ask", async (route) => {',
)
