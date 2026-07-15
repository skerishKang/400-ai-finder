"""#1170: fixture-to-canvas home renderer parity (Node sandbox)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
CANONICAL = ROOT / "data" / "official_clone_fixtures" / "bukgu_gwangju" / "home.json"

EXPECTED_FIXTURE_SHA = (
    "81b27b98fadc091ca852079f89ea93da45b93f250372835b8b352726b2faeaed"
)
REGION_ORDER = [
    "utility_navigation",
    "main_banner",
    "resident_service_shortcuts",
    "notice_news",
    "related_site_controls",
    "footer_identity_contact",
]


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def _run_node(script: str, timeout: int = 30) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(script)
        path = handle.name
    try:
        return subprocess.run(
            ["node", path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    finally:
        os.unlink(path)


def _render_home_html() -> str:
    script = """
'use strict';
var vm = require('vm');
var capturedHTML = '';
function makeElement(id) {
  return {
    id: id,
    style: {},
    offsetHeight: 0,
    get innerHTML() { return capturedHTML; },
    set innerHTML(v) { capturedHTML = v; },
    addEventListener: function() {},
    querySelector: function() { return null; }
  };
}
var sandbox = {
  document: {
    getElementById: function(id) {
      if (id === 'demo-canvas') return makeElement('demo-canvas');
      return null;
    }
  },
  console: { log: function() {}, error: function() {} },
  setTimeout: function(fn) { fn(); return 1; },
  clearTimeout: function() {},
  URLSearchParams: URLSearchParams
};
sandbox.window = sandbox;
var cx = vm.createContext(sandbox);
vm.runInContext(%s, cx);
vm.runInContext(%s, cx);
vm.runInContext(%s, cx);
vm.runInContext(%s, cx);
sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
process.stdout.write(capturedHTML);
""" % (
        json.dumps(_read("bukgu-official-snapshots.js")),
        json.dumps(_read("bukgu-home-clone-fixture.js")),
        json.dumps(_read("citizen-action-demo-map.js")),
        json.dumps(_read("citizen-action-demo-canvas.js")),
    )
    result = _run_node(script)
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.fixture(scope="module")
def home_html():
    return _render_home_html()


@pytest.fixture(scope="module")
def fixture():
    return json.loads(CANONICAL.read_text(encoding="utf-8"))


def test_home_fixture_root_and_sha(home_html):
    assert 'data-home-fixture-sha256="%s"' % EXPECTED_FIXTURE_SHA in home_html
    assert 'data-home-clone-status="capture_required"' in home_html
    assert 'data-home-exact-clone="false"' in home_html
    assert "bg-home-fixture-root" in home_html
    assert "bg-page--home-fixture-unavailable" not in home_html


def test_region_order_and_counts(home_html, fixture):
    positions = []
    by_id = {r["region_id"]: r for r in fixture["regions"]}
    for rid in REGION_ORDER:
        marker = 'data-home-region-id="%s"' % rid
        assert marker in home_html
        positions.append(home_html.index(marker))
        src = by_id[rid]
        count = len(src["items"])
        assert 'data-home-item-count="%d"' % count in home_html
        for item in src["items"]:
            assert 'data-home-item-id="%s"' % item["item_id"] in home_html
    assert positions == sorted(positions)


def test_visible_and_hidden_utility_items(home_html, fixture):
    util = next(r for r in fixture["regions"] if r["region_id"] == "utility_navigation")
    hidden = [
        i
        for i in util["items"]
        if (i.get("effective_variant") or i.get("variant")) == "hidden"
    ]
    desktop = [
        i
        for i in util["items"]
        if (i.get("effective_variant") or i.get("variant")) == "desktop"
    ]
    assert len(hidden) == 3
    assert len(desktop) == 18
    for item in hidden:
        assert item["text"] in ("ENG", "CHN", "JPN")
        # Hidden items still in DOM with hidden class/attrs
        assert 'data-home-item-id="%s"' % item["item_id"] in home_html
        # Opening tag ends before the item body; scan a wider window around the id.
        idx = home_html.index('data-home-item-id="%s"' % item["item_id"])
        open_idx = home_html.rfind("<", 0, idx)
        close_idx = home_html.find(">", idx)
        snippet = home_html[open_idx : close_idx + 1]
        assert "bg-home-fixture-item--hidden" in snippet
        assert 'aria-hidden="true"' in snippet


def test_exact_text_and_dates(home_html, fixture):
    notice = next(r for r in fixture["regions"] if r["region_id"] == "notice_news")
    for item in notice["items"]:
        if item.get("text"):
            assert item["text"] in home_html
        if item.get("date_text"):
            assert item["date_text"] in home_html


def test_fragment_sha_and_source_metadata(home_html, fixture):
    for rid in REGION_ORDER:
        region = next(r for r in fixture["regions"] if r["region_id"] == rid)
        frag = (region.get("source_evidence") or {}).get("fragment_sha256")
        if frag:
            assert 'data-source-fragment-sha256="%s"' % frag in home_html
    # sample same_origin metadata
    for rid in REGION_ORDER:
        region = next(r for r in fixture["regions"] if r["region_id"] == rid)
        for item in region["items"][:5]:
            if item.get("href") is not None:
                assert 'data-home-item-id="%s"' % item["item_id"] in home_html


def test_page_agent_targets_present(home_html):
    for target in [
        "nav-civil-service",
        "nav-complaint-board",
        "nav-apartment-dept",
        "nav-passport-guidance",
        "nav-bulky-waste-disposal",
        "mayor-office-open",
    ]:
        assert 'data-action-target="%s"' % target in home_html


def test_cross_origin_items_are_inert(home_html, fixture):
    for rid in REGION_ORDER:
        region = next(r for r in fixture["regions"] if r["region_id"] == rid)
        for item in region["items"]:
            if item.get("same_origin") is False:
                idx = home_html.index('data-home-item-id="%s"' % item["item_id"])
                # look backward for opening tag
                open_idx = home_html.rfind("<", 0, idx)
                snippet = home_html[open_idx : idx + 120]
                assert "bg-home-fixture-item--inert" in snippet or "data-action-target" not in snippet
                assert 'data-action-target="' not in snippet.split(">")[0]


def test_no_remote_asset_img_src(home_html, fixture):
    assert re.search(r'<img[^>]+src=["\']https?://', home_html) is None
    for rid in REGION_ORDER:
        region = next(r for r in fixture["regions"] if r["region_id"] == rid)
        for item in region["items"]:
            asset = item.get("asset_url")
            if asset:
                assert 'data-source-asset-url="%s"' % asset in home_html
                assert 'src="%s"' % asset not in home_html


def test_fail_closed_without_global():
    script = """
'use strict';
var vm = require('vm');
var capturedHTML = '';
function makeElement(id) {
  return {
    id: id, style: {}, offsetHeight: 0,
    get innerHTML() { return capturedHTML; },
    set innerHTML(v) { capturedHTML = v; },
    addEventListener: function() {},
    querySelector: function() { return null; }
  };
}
var sandbox = {
  document: { getElementById: function(id) {
    if (id === 'demo-canvas') return makeElement('demo-canvas');
    return null;
  }},
  console: { log: function() {}, error: function() {} },
  setTimeout: function(fn) { fn(); return 1; },
  clearTimeout: function() {},
  URLSearchParams: URLSearchParams
};
sandbox.window = sandbox;
var cx = vm.createContext(sandbox);
vm.runInContext(%s, cx);
vm.runInContext(%s, cx);
vm.runInContext(%s, cx);
// intentionally skip home fixture projection
sandbox.window.CitizenActionDemoCanvas.navigateToRoute('home');
process.stdout.write(capturedHTML);
""" % (
        json.dumps(_read("bukgu-official-snapshots.js")),
        json.dumps(_read("citizen-action-demo-map.js")),
        json.dumps(_read("citizen-action-demo-canvas.js")),
    )
    result = _run_node(script)
    assert result.returncode == 0, result.stderr
    html = result.stdout
    assert "bg-page--home-fixture-unavailable" in html
    assert "clone home fixture unavailable" in html
    assert "home-mayor-card.png" not in html
    assert 'data-action-target="nav-civil-service"' not in html
