from pathlib import Path

# Branch-only applicator: the paired workflow validates the production-gap E2E
# and removes this file before committing the product patch.
path = Path("tests/browser/verify_page_agent_production_gaps_e2e.mjs")
text = path.read_text(encoding="utf-8")
anchor = '''    const mvpSafety = createSafetyTracker(mvpSrv.origin);\n    attachSafety(mvpPage, mvpSafety);\n\n    await mvpPage.route("**/api/mvp/ask", async (route) => {\n'''
replacement = '''    const mvpSafety = createSafetyTracker(mvpSrv.origin);\n    attachSafety(mvpPage, mvpSafety);\n\n    // This production-gap suite owns deterministic MVP navigation, not the\n    // Turnstile lifecycle. Dedicated #1224-B contracts cover the challenge,\n    // so isolate this mocked /api/mvp/ask path before application scripts run.\n    await mvpPage.addInitScript(() => {\n      window.CitizenTurnstile = Object.freeze({\n        acquireToken() { return Promise.resolve(""); },\n        reset() {},\n        cancel() {},\n      });\n    });\n\n    await mvpPage.route("**/api/mvp/ask", async (route) => {\n'''
if replacement in text:
    print("already patched")
elif text.count(anchor) == 1:
    path.write_text(text.replace(anchor, replacement, 1), encoding="utf-8")
    print("page-agent deterministic MVP Turnstile isolation applied")
else:
    raise SystemExit(f"unexpected anchor count: {text.count(anchor)}")
