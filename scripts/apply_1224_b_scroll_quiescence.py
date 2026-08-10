from pathlib import Path

# Triggered only by the temporary branch workflow; removed in the same validated commit.
path = Path("tests/browser/verify_desktop_chat_scroll_containment_e2e.mjs")
text = path.read_text(encoding="utf-8")

marker = "await waitForChatScrollQuiescence(page);"
if marker not in text:
    helper_anchor = "\nasync function collectCounts(page) {"
    helper = '''\nasync function waitForChatScrollQuiescence(page) {\n  // #1173/#1231: product auto-scroll deliberately schedules one rAF\n  // correction after appending a message. Wait for that correction and the\n  // following paint before simulating a resident scroll into history. This is\n  // event/frame synchronization, not a timing sleep or relaxed assertion.\n  await page.evaluate(() => new Promise((resolve) => {\n    window.requestAnimationFrame(() => {\n      window.requestAnimationFrame(resolve);\n    });\n  }));\n}\n'''
    if text.count(helper_anchor) != 1:
        raise SystemExit(f"helper anchor count={text.count(helper_anchor)}")
    text = text.replace(helper_anchor, helper + helper_anchor, 1)

    block_anchor = '''  console.log(\n    `  bottom-pinned: PASS distBottom=${bottomPinRes.distBottom} nearBottom=${bottomPinRes.nearBottom}`,\n  );\n\n  // Reading-history → explicit turn: #1200 ensures composer submit always\n'''
    replacement = '''  console.log(\n    `  bottom-pinned: PASS distBottom=${bottomPinRes.distBottom} nearBottom=${bottomPinRes.nearBottom}`,\n  );\n  await waitForChatScrollQuiescence(page);\n\n  // Reading-history → explicit turn: #1200 ensures composer submit always\n'''
    if text.count(block_anchor) != 1:
        raise SystemExit(f"block anchor count={text.count(block_anchor)}")
    text = text.replace(block_anchor, replacement, 1)

path.write_text(text, encoding="utf-8")
print("#1224-B/#1173 scroll quiescence synchronization applied")
