"""#1170 / residual #868 asset integrity + home fixture wiring contracts.

R-HOME-02 crop files remain committed for dense-shell history, but home
route rendering is fixture-driven and must not claim exact visual parity.
"""

import json
from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
JS = (STATIC / "citizen-action-demo-canvas.js").read_text(encoding="utf-8")
FIXTURE_JS = (STATIC / "bukgu-home-clone-fixture.js").read_text(encoding="utf-8")

SOURCE = (
    ROOT
    / "docs/artifacts/863-reference/source"
    / "CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png"
)
EXPECTED_SOURCE_SHA = "e0c1d451312056a5314fa2dc5b77d62fb53ef6dc90352797d78e4bb57eae3c49"
EXPECTED_SOURCE_SIZE = (1344, 1833)
BOX = (562, 258, 1123, 555)
EXPECTED_CROP_SIZE = (561, 297)
OUTPUT = STATIC / "images" / "bukgu-current" / "home-alert-banner-r-home-02.png"

EXPECTED_FIXTURE_SHA = (
    "81b27b98fadc091ca852079f89ea93da45b93f250372835b8b352726b2faeaed"
)

RESOLVER_TEST_CASES = [
    ("", "R-HOME-01"),
    ("?", "R-HOME-01"),
    ("?home-reference=", "R-HOME-01"),
    ("?home-reference=R-HOME-01", "R-HOME-01"),
    ("?home-reference=other", "R-HOME-01"),
    ("?foo=R-HOME-02", "R-HOME-01"),
    ("?foo=1&home-reference=R-HOME-02", "R-HOME-02"),
    ("?home-reference=R-HOME-02", "R-HOME-02"),
    ("?home-reference=R-HOME-02&home-reference=R-HOME-01", "R-HOME-01"),
    ("?home-reference=R-HOME-01&home-reference=R-HOME-02", "R-HOME-01"),
    ("?home-reference=R-HOME-02&home-reference=R-HOME-02", "R-HOME-01"),
    ("?home-reference=R-HOME-02&home-reference=R-HOME-02&home-reference=R-HOME-02", "R-HOME-01"),
    ("?home-reference=%E0%A4%A", "R-HOME-01"),
    ("?foo=1&home-reference=R-HOME-02&bar=2", "R-HOME-02"),
]


@pytest.fixture(scope="module")
def resolver_results():
    """Run the resolver via node:vm with full canvas.js in a restricted sandbox."""
    import subprocess
    import tempfile
    import os

    js_abs_path = str(STATIC / "citizen-action-demo-canvas.js")
    cases_json = json.dumps(RESOLVER_TEST_CASES)
    node_script = (
        r'''
const vm = require("vm");
const fs = require("fs");
const jsPath = "'''
        + js_abs_path.replace("\\", "\\\\")
        + r'''";
let source = fs.readFileSync(jsPath, "utf-8");
const inject = 'window.__testResolveHomeReferenceState = _resolveHomeReferenceState;\n';
const insertionPoint = source.indexOf("function _renderHome(");
const instrumented = source.slice(0, insertionPoint) + inject + source.slice(insertionPoint);
const sandbox = {
  window: {},
  document: { getElementById: function() { return null; } },
  CitizenActionDemoMap: {},
  URLSearchParams: URLSearchParams,
  console: { log: function() {}, error: function() {}, warn: function() {} },
};
sandbox.window = sandbox;
const cx = vm.createContext(sandbox);
vm.runInContext(instrumented, cx);
const cases = '''
        + cases_json
        + r''';
const out = {};
for (const [search, expected] of cases) {
  const actual = sandbox.window.__testResolveHomeReferenceState(search);
  out[search] = { expected, actual, pass: actual === expected };
}
process.stdout.write(JSON.stringify(out));
'''
    )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(node_script)
        path = handle.name
    try:
        result = subprocess.run(
            ["node", path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    finally:
        os.unlink(path)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_resolver_r_home_02_cases(resolver_results):
    assert resolver_results["?home-reference=R-HOME-02"]["pass"]
    assert resolver_results["?home-reference=R-HOME-02&home-reference=R-HOME-01"]["pass"]
    assert resolver_results["?home-reference=R-HOME-01&home-reference=R-HOME-02"]["pass"]
    assert resolver_results["?foo=1&home-reference=R-HOME-02"]["pass"]


def test_r_home_02_source_integrity():
    assert SOURCE.is_file(), f"R-HOME-02 source not found: {SOURCE}"
    actual_hash = sha256(SOURCE.read_bytes()).hexdigest()
    assert actual_hash == EXPECTED_SOURCE_SHA, f"SHA mismatch: {actual_hash}"
    with Image.open(SOURCE) as img:
        img.load()
        assert img.size == EXPECTED_SOURCE_SIZE, f"source size: {img.size}"


def test_banner_crop_matches_source_pixels():
    assert OUTPUT.is_file(), f"crop not found: {OUTPUT}"
    with Image.open(OUTPUT) as crop_img:
        crop_img.load()
        assert crop_img.size == EXPECTED_CROP_SIZE, f"crop size: {crop_img.size}"
    with Image.open(SOURCE) as src_img:
        src_img.load()
        expected_pixels = src_img.crop(BOX).convert("RGB").tobytes()
    actual_pixels = Image.open(OUTPUT).convert("RGB").tobytes()
    assert actual_pixels == expected_pixels, "banner crop pixel data mismatch"


def test_home_renderer_is_fixture_driven_not_r_home_banner():
    start = JS.index("  function _renderHome(")
    end = JS.index(
        "  // -----------------------------------------------------------------------\n  // _renderCivilService",
        start,
    )
    home_block = JS[start:end]
    assert "_getCanonicalHomeFixture" in JS
    assert "home-alert-banner-r-home-02.png" not in home_block
    assert "home-alert-banner.png" not in home_block
    assert "bukgu_home.png" not in home_block
    assert EXPECTED_FIXTURE_SHA in FIXTURE_JS


def test_home_state_resolver_function_exists():
    assert "function _resolveHomeReferenceState(search)" in JS


def test_home_root_has_fixture_and_reference_state_attributes():
    assert "data-home-reference-state=" in JS
    assert "data-home-fixture-sha256=" in JS
    assert "data-home-clone-status=" in JS
    assert 'data-home-exact-clone="false"' in JS
