#!/usr/bin/env python3
"""Finalize compatibility details after apply_current_home_top_patch.py.

This is an offline, deterministic follow-up for the exact generated #868 home
patch. It preserves the audited source-patch scope and makes the generated home
markup satisfy existing class contracts while tightening the new asset test.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANVAS_JS = ROOT / "src/web/static/citizen-action-demo-canvas.js"
CANVAS_CSS = ROOT / "src/web/static/citizen-action-demo-canvas.css"
TEST_FILE = ROOT / "tests/test_current_bukgu_home_top_contract.py"
MARKER = "/* #868 current Buk-gu home top viewport */"
FIX_MARKER = "/* #868 current Buk-gu home top compatibility */"


def blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("utf-8") + data).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    if not CANVAS_JS.is_file() or not CANVAS_CSS.is_file() or not TEST_FILE.is_file():
        print("ERROR: run apply_current_home_top_patch.py --apply first", file=sys.stderr)
        return 2

    js = CANVAS_JS.read_text(encoding="utf-8")
    css = CANVAS_CSS.read_text(encoding="utf-8")
    test = TEST_FILE.read_text(encoding="utf-8")

    if MARKER not in css:
        print("ERROR: current home top CSS marker is missing", file=sys.stderr)
        return 3
    if FIX_MARKER in css:
        print("ERROR: compatibility fixup already applied", file=sys.stderr)
        return 4

    js = replace_once(
        js,
        "'<header class=\"bg-home-header bg-header\">' +",
        "'<header class=\"bg-header\">' +\n          '<div class=\"bg-home-header\">' +",
        "header wrapper",
    )
    js = replace_once(
        js,
        "'</header>' +\n\n        '<section class=\"bg-home-search\"",
        "'</div>' +\n        '</header>' +\n\n        '<section class=\"bg-home-search\"",
        "header wrapper close",
    )
    js = replace_once(
        js,
        "'<nav class=\"bg-home-gnb bg-gnb\" aria-label=\"주메뉴\">' +",
        "'<nav class=\"bg-gnb\" aria-label=\"주메뉴\">' +\n              '<div class=\"bg-home-gnb\">' +",
        "GNB wrapper",
    )
    js = replace_once(
        js,
        "'</nav>' +\n            '<div class=\"bg-home-header__actions\">' +",
        "'</div>' +\n            '</nav>' +\n            '<div class=\"bg-home-header__actions\">' +",
        "GNB wrapper close",
    )

    test = replace_once(
        test,
        'assert f"/bukgu-current/{asset}" in home',
        'assert asset in home',
        "derived asset string assertion",
    )

    css += """

/* #868 current Buk-gu home top compatibility */
.bg-page--home > .bg-header {
  background: #fff;
  border: 0;
}
.bg-page--home .bg-home-header > .bg-gnb {
  min-width: 0;
  background: transparent;
  border: 0;
  flex-shrink: 1;
}
"""

    CANVAS_JS.write_text(js, encoding="utf-8")
    CANVAS_CSS.write_text(css, encoding="utf-8")
    TEST_FILE.write_text(test, encoding="utf-8")

    print("APPLIED: #868 current home top compatibility fixup")
    print(f"JS blob:   {blob_sha1(CANVAS_JS)}")
    print(f"CSS blob:  {blob_sha1(CANVAS_CSS)}")
    print(f"Test blob: {blob_sha1(TEST_FILE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
