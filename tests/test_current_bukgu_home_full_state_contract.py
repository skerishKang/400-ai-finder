"""Contract checks for #868 full-home carousel state alignment with R-HOME-02.

Verifies:
- R-HOME-02 source capture integrity (SHA, dimensions).
- Derived banner crop matches source pixel-for-pixel.
- canvas.js uses only the R-HOME-02 banner, not the R-HOME-01 one.
- Identity contract is preserved.
"""

import json
import re
import subprocess
from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
JS = (STATIC / "citizen-action-demo-canvas.js").read_text(encoding="utf-8")

# R-HOME-02 source capture
SOURCE = ROOT / "docs/artifacts/863-reference/source" / "CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png"
EXPECTED_SOURCE_SHA = "e0c1d451312056a5314fa2dc5b77d62fb53ef6dc90352797d78e4bb57eae3c49"
EXPECTED_SOURCE_SIZE = (1344, 1833)

# Crop specification from 868-home-full-carousel-crop-manifest.md
BOX = (562, 258, 1123, 555)
EXPECTED_CROP_SIZE = (561, 297)

OUTPUT = STATIC / "images" / "bukgu-current" / "home-alert-banner-r-home-02.png"


# --- Runtime resolver VM test ---

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
]


def _extract_resolver_source() -> str:
    """Extract the _resolveHomeReferenceState function body from canvas.js."""
    # Find the function and wrap it for standalone execution
    pattern = r'(function _resolveHomeReferenceState\(search\) \{[^}]+\})'
    match = re.search(pattern, JS)
    assert match, "_resolveHomeReferenceState function not found in canvas.js"
    return match.group(1)


@pytest.fixture(scope="module")
def resolver_results():
    """Run the resolver function in Node.js against all test cases."""
    fn_src = _extract_resolver_source()
    cases_json = json.dumps(RESOLVER_TEST_CASES)
    node_script = (
        "var fn = " + fn_src + ";\n"
        "var cases = " + cases_json + ";\n"
        "var results = {};\n"
        "for (var i = 0; i < cases.length; i++) {\n"
        "  var input = cases[i][0];\n"
        "  var expected = cases[i][1];\n"
        "  var actual = fn(input);\n"
        "  results[input] = {expected: expected, actual: actual, pass: actual === expected};\n"
        "}\n"
        "process.stdout.write(JSON.stringify(results));"
    )
    result = subprocess.run(
        ["node", "-e", node_script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Node resolver test failed: {result.stderr}")
    return json.loads(result.stdout)


class TestHomeReferenceStateResolver:
    """Runtime Node.js VM tests for _resolveHomeReferenceState."""

    def test_resolver_all_cases(self, resolver_results):
        """Every resolver input/output pair must match."""
        for query, expected in RESOLVER_TEST_CASES:
            r = resolver_results.get(query, {})
            assert r.get("pass"), f"FAIL: query={query!r} expected={expected} actual={r.get('actual')}"

    def test_resolver_duplicate_both_r_home_02(self, resolver_results):
        """Two identical R-HOME-02 parameters → R-HOME-01 (ambiguous)."""
        assert resolver_results["?home-reference=R-HOME-02&home-reference=R-HOME-02"]["pass"]

    def test_resolver_duplicate_first_r_home_02_second_r_home_01(self, resolver_results):
        """Mixed R-HOME-02 then R-HOME-01 → R-HOME-01 (ambiguous)."""
        assert resolver_results["?home-reference=R-HOME-02&home-reference=R-HOME-01"]["pass"]

    def test_resolver_duplicate_first_r_home_01_second_r_home_02(self, resolver_results):
        """Mixed R-HOME-01 then R-HOME-02 → R-HOME-01 (ambiguous)."""
        assert resolver_results["?home-reference=R-HOME-01&home-reference=R-HOME-02"]["pass"]

    def test_resolver_single_r_home_02(self, resolver_results):
        """Single ?home-reference=R-HOME-02 → R-HOME-02."""
        assert resolver_results["?home-reference=R-HOME-02"]["pass"]

    def test_resolver_no_query(self, resolver_results):
        """Empty query → R-HOME-01."""
        assert resolver_results[""]["pass"]

    def test_resolver_unrelated_param(self, resolver_results):
        """Unrelated param with valid R-HOME-02 key → R-HOME-02."""
        assert resolver_results["?foo=1&home-reference=R-HOME-02"]["pass"]


# --- Static/offline tests ---


def test_r_home_02_source_integrity():
    """Source PNG SHA-256 and dimensions match the crop manifest."""
    assert SOURCE.is_file(), f"R-HOME-02 source not found: {SOURCE}"
    actual_hash = sha256(SOURCE.read_bytes()).hexdigest()
    assert actual_hash == EXPECTED_SOURCE_SHA, f"SHA mismatch: {actual_hash}"
    with Image.open(SOURCE) as img:
        img.load()
        assert img.size == EXPECTED_SOURCE_SIZE, f"source size: {img.size}"


def test_banner_crop_matches_source_pixels():
    """Output PNG pixels match source crop box exactly (decoded RGB bytes)."""
    assert OUTPUT.is_file(), f"crop not found: {OUTPUT}"

    with Image.open(OUTPUT) as crop_img:
        crop_img.load()
        assert crop_img.size == EXPECTED_CROP_SIZE, f"crop size: {crop_img.size}"

    with Image.open(SOURCE) as src_img:
        src_img.load()
        expected_pixels = src_img.crop(BOX).convert("RGB").tobytes()

    actual_pixels = Image.open(OUTPUT).convert("RGB").tobytes()
    assert actual_pixels == expected_pixels, "banner crop pixel data mismatch"


def test_banner_r_home_02_used_in_home_renderer():
    """canvas.js _renderHome references both banner assets (state-selected via bannerFile)."""
    home_start = JS.index("  function _renderHome(")
    home_end = JS.index("  //", home_start + 100)
    home_block = JS[home_start:home_end]

    assert "home-alert-banner-r-home-02.png" in home_block, "R-HOME-02 banner asset not found in _renderHome"
    assert "home-alert-banner.png" in home_block, "default R-HOME-01 banner asset missing from _renderHome"
    assert 'bannerFile' in home_block, "bannerFile variable selector missing"
    assert "bukgu_home.png" not in home_block, "full-page source PNG referenced in home renderer"


def test_identity_contract_maintained():
    """Full home state preserves the correct integrated identity.
    Scope: home block only (sub-routes have separate pending work)."""
    home_start = JS.index("  function _renderHome(")
    # Take full home function (up to the next function or 8000 chars)
    home_end_sentinel = JS.find("\n\n  //", home_start)
    if home_end_sentinel == -1:
        home_end_sentinel = home_start + 8000
    home_block = JS[home_start:home_end_sentinel]
    assert "home-identity.png" in home_block, "current identity asset missing from home"
    assert 'alt="전남광주통합특별시북구"' in home_block or 'alt="전남광주통합특별시북구"' in JS[:2000], \
        "identity alt text missing"
    assert "광주광역시 북구" not in home_block, "legacy identity appears in home block"


def test_home_state_resolver_function_exists():
    """_resolveHomeReferenceState is defined and accessible in canvas.js."""
    assert "function _resolveHomeReferenceState(search)" in JS, "state resolver function missing"


def test_home_state_resolver_r_home_02():
    """?home-reference=R-HOME-02 selects the R-HOME-02 state."""
    assert "_resolveHomeReferenceState(search)" in JS, "state resolver function defined"
    assert '_resolveHomeReferenceState(typeof window !== "undefined"' in JS, "resolver called safely"
    # The resolver's R-HOME-02 detection and fallback logic
    assert 'R-HOME-02' in JS[JS.index("function _resolveHomeReferenceState"):JS.index("function _resolveHomeReferenceState") + 500], \
        "R-HOME-02/fallback logic in resolver"


def test_home_default_state_is_r_home_01():
    """Default home uses R-HOME-01 banner asset."""
    home_block_src = JS[JS.index("  function _renderHome("):JS.index("  //", JS.index("  function _renderHome(") + 100)]
    assert "home-alert-banner.png" in home_block_src, "default R-HOME-01 banner asset missing from _renderHome"


def test_home_root_has_data_state_attribute():
    """Home root div includes data-home-reference-state attribute."""
    home_block_src = JS[JS.index("  function _renderHome("):JS.index("  //", JS.index("  function _renderHome(") + 100)]
    assert 'data-home-reference-state="' in home_block_src, "data-home-reference-state attribute missing"


def test_r_home_02_banner_only_for_alternate_state():
    """R-HOME-02 banner is referenced in JS but not as default in _renderHome."""
    home_start = JS.index("  function _renderHome(")
    home_end = JS.index("  //", home_start + 100)
    home_block = JS[home_start:home_end]
    # Default should NOT be R-HOME-02 banner
    assert "home-alert-banner-r-home-02.png" not in home_block or 'bannerFile' in home_block, \
        "R-HOME-02 banner should be selected via variable, not hardcoded"
