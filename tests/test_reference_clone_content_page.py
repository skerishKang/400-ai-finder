"""Offline contracts for #1357 generic CMS content-page capability.

Exercises the site-agnostic content-page model extractor and renderer added to
``reference_clone_model.py`` / ``reference_clone_renderer.py``. The generic core
must contain ZERO site-specific literals (no 여권 / 서구 / passport / phone /
#1356), must preserve inline-markup continuity, must render deterministically,
must bound extraction to the real article body (no chrome), and must leave the
existing home / list / detail / chart / directory surfaces untouched.

Zero network: a socket/urlopen block is enforced on every test.
"""

from __future__ import annotations

import importlib.util
import json
import re
import socket
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = REPO_ROOT / "src" / "official_clone" / "reference_clone_model.py"
RENDERER_PATH = REPO_ROOT / "src" / "official_clone" / "reference_clone_renderer.py"

# Capture used to exercise the real Seo-gu passport informational page.
CAPTURE_ROOT_1357 = (
    REPO_ROOT / "data" / "official_captures" / "seogu_gwangju" / "g1" / "20260820T011047-0900"
)
# Existing committed capture whose fixtures must stay byte-identical.
FIXTURE_132 = (
    REPO_ROOT / "data" / "official_clone_fixtures" / "seogu_gwangju"
    / "g1" / "20260812T231018-0900" / "clone-model.json"
)

# Site-specific literals that must NEVER appear in the generic core logic.
_FORBIDDEN_LITERALS = (
    "여권", "서구", "passport", "passport-guidance", "062-360-7613",
    "민원실 4번 창구", "민원봉사과 민원여권", "#1356", "seogu",
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mod = _load(MODEL_PATH, "reference_clone_model_content_page_test")
rmod = _load(RENDERER_PATH, "reference_clone_renderer_content_page_test")


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch):
    def _blocked(*_a, **_k):
        raise AssertionError("network access is forbidden in content-page tests")

    monkeypatch.setattr(socket, "socket", _blocked)
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _blocked)
    return None


def _rc_main_text(html: str) -> str:
    m = re.search(r'<main class="rc-main">(.*?)</main>', html, re.S)
    assert m, "rendered page has no rc-main"
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()


# ---------------------------------------------------------------------------
# Genericity proof (#1357 / #1232): no site-specific literals in core logic.
# ---------------------------------------------------------------------------
def test_generic_core_has_no_site_specific_literals():
    for path in (MODEL_PATH, RENDERER_PATH):
        text = path.read_text(encoding="utf-8")
        for lit in _FORBIDDEN_LITERALS:
            assert lit not in text, f"{lit!r} found in {path.name}"


# ---------------------------------------------------------------------------
# A. Nested inline markup preserves semantic text continuity.
# ---------------------------------------------------------------------------
_SYNTH_INLINE = """<html><body><main><section id="contents">
<div class="info-box"><div class="txt"><strong class="tt">제목</strong>
<div class="con">민원봉사과 <strong>민원여권</strong> 안내</div></div></div>
<div class="contents_info"><article class="duty"><h2 class="title">콘텐츠 정보책임자</h2>
<ul class="list"><li><strong class="label">담당부서</strong><span class="part">민원봉사과 <strong>민원여권</strong></span></li>
<li><strong class="label">연락처</strong><span class="tel">062-360-7613</span></li></ul></article></div>
</section></main></body></html>"""


def test_inline_markup_continuity_preserved():
    page = mod._extract_content_page(_SYNTH_INLINE)
    assert page is not None
    # Paragraph keeps the strong-split phrase contiguous.
    paras = [b["text"] for b in page["blocks"] if b["type"] == "paragraph"]
    assert any("민원봉사과 민원여권" in p for p in paras)
    # Duty box value keeps the strong-split phrase contiguous.
    duty = (page.get("contents_info") or {}).get("items", [])
    dept = next((it["value"] for it in duty if it["label"] == "담당부서"), "")
    assert dept == "민원봉사과 민원여권"


# ---------------------------------------------------------------------------
# B. Heading / paragraph / list ordering is deterministic.
# ---------------------------------------------------------------------------
_SYNTH_ORDER = """<html><body><main><section id="contents">
<div class="info-box">
<h2 class="tt">안내제목</h2>
<div class="con">본문입니다</div>
<ul class="dep03"><li>항목1</li><li>항목2</li></ul>
</div></section></main></body></html>"""


def test_block_order_is_deterministic():
    page = mod._extract_content_page(_SYNTH_ORDER)
    assert page is not None
    types = [b["type"] for b in page["blocks"]]
    assert types == ["heading", "paragraph", "list"]
    list_block = page["blocks"][2]
    assert list_block["items"] == ["항목1", "항목2"]


# ---------------------------------------------------------------------------
# J. Unsupported / unproven content fails closed (no fabricated page).
# ---------------------------------------------------------------------------
_SYNTH_NOSIGNAL = "<html><body><main><p>그냥 텍스트</p></main></body></html>"
_SYNTH_HOMEISH = """<html><body><main><section id="snb"><h2 class="title">메뉴</h2>
<ul><li>항목</li></ul></section>
<section id="contents"><div class="contents_util"><h2 id="contents_title">홈</h2></div>
<div class="hero">배너</div></section></main></body></html>"""


def test_no_signal_page_fails_closed():
    assert mod._extract_content_page(_SYNTH_NOSIGNAL) is None
    assert mod._extract_content_page(_SYNTH_HOMEISH) is None


# ---------------------------------------------------------------------------
# C. Generic content text appears visibly inside main.rc-main (real capture).
# ---------------------------------------------------------------------------
def test_content_rendered_in_rc_main():
    model = mod.build_reference_clone_model(REPO_ROOT, CAPTURE_ROOT_1357)
    state_id = "passport_guidance.default.desktop"
    html = rmod.render_state(model, state_id, route_prefix="/seogu/")
    text = _rc_main_text(html)
    for mk in (
        "여권발급", "민원실 4번 창구", "민원봉사과 민원여권", "062-360-7613",
        "여권발급절차", "근무일 기준 8일",
    ):
        assert mk in text, f"required marker missing from rc-main: {mk!r}"


# ---------------------------------------------------------------------------
# D-H. Existing surfaces unchanged: no content_page, correct renderer.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def _fixture_132():
    return json.loads(FIXTURE_132.read_text(encoding="utf-8"))


def _render_state_from_fixture(fixture, state_id, route_prefix="/seogu/"):
    return rmod.render_state(fixture, state_id, route_prefix=route_prefix)


def test_home_default_uses_home_renderer(_fixture_132):
    state = next(s for s in _fixture_132["states"] if s["state_id"] == "home.desktop.default")
    assert "content_page" not in state
    html = _render_state_from_fixture(_fixture_132, "home.desktop.default")
    main = _rc_main_text(html)
    assert "rc-home" in html
    assert "rc-content-page" not in html
    assert main  # home renderer produced visible content


def test_board_list_unchanged(_fixture_132):
    state = next(s for s in _fixture_132["states"] if s["state_id"] == "notice.list.desktop")
    assert "content_page" not in state
    html = _render_state_from_fixture(_fixture_132, "notice.list.desktop")
    assert "rc-board" in html
    assert "rc-content-page" not in html


def test_board_detail_unchanged(_fixture_132):
    state = next(s for s in _fixture_132["states"] if s["state_id"] == "notice.detail.desktop")
    assert "content_page" not in state
    html = _render_state_from_fixture(_fixture_132, "notice.detail.desktop")
    assert "rc-board" in html
    assert "rc-content-page" not in html


def test_org_chart_unchanged(_fixture_132):
    state = next(s for s in _fixture_132["states"] if s["state_id"] == "organization.chart.desktop")
    assert "content_page" not in state
    html = _render_state_from_fixture(_fixture_132, "organization.chart.desktop")
    assert "rc-org" in html
    assert "rc-content-page" not in html


def test_staff_directory_unchanged(_fixture_132):
    state = next(s for s in _fixture_132["states"] if s["state_id"] == "staff.directory.desktop")
    assert "content_page" not in state
    html = _render_state_from_fixture(_fixture_132, "staff.directory.desktop")
    assert "rc-staff" in html
    assert "rc-content-page" not in html


def test_no_state_in_existing_fixture_carries_content_page(_fixture_132):
    for state in _fixture_132["states"]:
        assert "content_page" not in state


# ---------------------------------------------------------------------------
# I. No external runtime request introduced.
# ---------------------------------------------------------------------------
def test_build_and_render_make_no_network_requests(_fixture_132):
    # Rendering existing + new surfaces must not reach the network (the
    # autouse socket/urlopen block would raise otherwise).
    for sid in (
        "home.desktop.default", "notice.list.desktop", "notice.detail.desktop",
        "organization.chart.desktop", "staff.directory.desktop",
    ):
        _render_state_from_fixture(_fixture_132, sid)
    # And the real content page builds offline.
    mod.build_reference_clone_model(REPO_ROOT, CAPTURE_ROOT_1357)
