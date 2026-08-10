from pathlib import Path

STUB = '''  await page.addInitScript(() => {\n    window.CitizenTurnstile = Object.freeze({\n      acquireToken() { return Promise.resolve(\"\"); },\n      reset() {},\n      cancel() {},\n    });\n  });\n'''
ROUTE_ANCHOR = '  await page.route("**/api/mvp/ask", async (route) => {'


def patch_before_mock_route(path: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    replacement = STUB + ROUTE_ANCHOR
    if replacement in text:
        print(f"already patched: {path}")
        return
    count = text.count(ROUTE_ANCHOR)
    if count != 1:
        raise SystemExit(f"{path}: expected one API mock route anchor, got {count}")
    file.write_text(text.replace(ROUTE_ANCHOR, replacement, 1), encoding="utf-8")
    print(f"patched: {path}")


for target in (
    "tests/browser/verify_housing_quest_e2e.mjs",
    "tests/browser/verify_mayor_writing_e2e.mjs",
    "tests/browser/verify_two_stage_bilingual_draft_e2e.mjs",
):
    patch_before_mock_route(target)
