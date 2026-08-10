from pathlib import Path

STUB = '''  await page.addInitScript(() => {\n    window.CitizenTurnstile = Object.freeze({\n      acquireToken() { return Promise.resolve(\"\"); },\n      reset() {},\n      cancel() {},\n    });\n  });\n'''
ROUTE_ANCHOR = '  await page.route("**/api/mvp/ask", async (route) => {'


def patch_before_mock_routes(path: str, expected_count: int) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    replacement = STUB + ROUTE_ANCHOR
    existing = text.count(replacement)
    if existing == expected_count:
        print(f"already patched: {path} ({existing})")
        return
    if existing:
        raise SystemExit(f"{path}: partial patch detected ({existing}/{expected_count})")
    count = text.count(ROUTE_ANCHOR)
    if count != expected_count:
        raise SystemExit(
            f"{path}: expected {expected_count} API mock route anchors, got {count}"
        )
    file.write_text(text.replace(ROUTE_ANCHOR, replacement), encoding="utf-8")
    print(f"patched: {path} ({count})")


patch_before_mock_routes("tests/browser/verify_housing_quest_e2e.mjs", 1)
patch_before_mock_routes("tests/browser/verify_mayor_writing_e2e.mjs", 4)
patch_before_mock_routes("tests/browser/verify_two_stage_bilingual_draft_e2e.mjs", 1)
