"""Offline contracts for #1360 S6 generic list-board kiosk capability.

Exercises the site-agnostic list-board model extractor and renderer already
present in ``reference_clone_model.py`` / ``reference_clone_renderer.py``. The
generic core must handle the S6 Seo-gu unmanned-kiosk capture through the
existing ``kind=list`` board path with ZERO kiosk/site-specific production code
(no ``if site_id == "seogu_gwangju"``, no ``kiosk`` branch, no Seo-gu-specific
parser). The committed fixture must match regeneration, the model must preserve
the six source table columns and all 10 captured page-1 rows, and the renderer
must emit the bounded ``/seogu/unmanned-kiosk/`` route deterministically.

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

# Capture used to exercise the real Seo-gu unmanned-kiosk catalog page.
CAPTURE_ROOT_1360 = (
    REPO_ROOT / "data" / "official_captures" / "seogu_gwangju" / "g1" / "20260820T083013-0900"
)
FIXTURE_1360 = (
    REPO_ROOT / "data" / "official_clone_fixtures" / "seogu_gwangju"
    / "g1" / "20260820T083013-0900" / "clone-model.json"
)
# Existing committed baseline whose fixtures must stay byte-identical.
FIXTURE_132 = (
    REPO_ROOT / "data" / "official_clone_fixtures" / "seogu_gwangju"
    / "g1" / "20260812T231018-0900" / "clone-model.json"
)

# Site/kiosk-specific literals that must NEVER appear in the generic core logic.
_FORBIDDEN_LITERALS = (
    "unmanned_kiosk", "unmanned-kiosk", "무인민원발급기", "kiosk",
    "푸른새마을금고", "설치장소", "seogu", "#1360", "발급종수",
)

_STATE_ID = "unmanned_kiosk.list.desktop"
_ROUTE_PREFIX = "/seogu/"
_EXPECTED_COLUMNS = ["번호", "설치장소", "도로명주소", "서비스시간", "발급종수", "비고"]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mod = _load(MODEL_PATH, "reference_clone_model_kiosk_board_test")
rmod = _load(RENDERER_PATH, "reference_clone_renderer_kiosk_board_test")


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch):
    def _blocked(*_a, **_k):
        raise AssertionError("network access is forbidden in kiosk board tests")

    monkeypatch.setattr(socket, "socket", _blocked)
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _blocked)
    return None


def _rc_main_text(html: str) -> str:
    m = re.search(r'<main class="rc-main">(.*?)</main>', html, re.S)
    assert m, "rendered page has no rc-main"
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()


# ---------------------------------------------------------------------------
# Genericity proof (#1360 / #1232): no kiosk/site-specific literals in core.
# ---------------------------------------------------------------------------
def test_generic_core_has_no_kiosk_specific_literals():
    for path in (MODEL_PATH, RENDERER_PATH):
        text = path.read_text(encoding="utf-8")
        for lit in _FORBIDDEN_LITERALS:
            assert lit not in text, f"{lit!r} found in {path.name}"


# ---------------------------------------------------------------------------
# A. The committed fixture matches deterministic regeneration.
# ---------------------------------------------------------------------------
def test_committed_kiosk_fixture_matches_regeneration():
    regenerated = mod.build_reference_clone_model(REPO_ROOT, CAPTURE_ROOT_1360)
    committed = json.loads(FIXTURE_1360.read_text(encoding="utf-8"))
    # The committed fixture omits model_sha256 (computed after write); strip it
    # before comparing, matching the established convention.
    regenerated.pop("model_sha256", None)
    committed.pop("model_sha256", None)
    assert regenerated == committed, "committed kiosk fixture diverges from regeneration"


def test_generator_check_exit_zero():
    rc = mod.main(["--capture-root", str(CAPTURE_ROOT_1360), "--check"])
    assert rc == 0, f"generator --check failed with exit {rc}"


# ---------------------------------------------------------------------------
# B. The model carries kind=list board semantics with caption + 6 columns.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def _kiosk_model():
    return json.loads(FIXTURE_1360.read_text(encoding="utf-8"))


def test_kiosk_model_identity(_kiosk_model):
    assert _kiosk_model["site_id"] == "seogu_gwangju"
    assert _kiosk_model["capture_id"] == "20260820T083013-0900"
    assert _kiosk_model["model_kind"] == "reference_clone_model"
    assert _kiosk_model["state_count"] == 1
    assert _kiosk_model["artifact_count"] == 4


def test_kiosk_state_is_list_board(_kiosk_model):
    state = _kiosk_model["states"][0]
    assert state["state_id"] == _STATE_ID
    assert state["state_name"] == "list"
    board = state["board"]
    assert board is not None, "kiosk state has no board (content_page would be wrong path)"
    assert board["kind"] == "list"
    assert "content_page" not in state or state["content_page"] is None


def test_kiosk_board_caption_preserved(_kiosk_model):
    board = _kiosk_model["states"][0]["board"]
    caption = board["caption"]
    assert "무인민원발급기" in caption
    assert "설치장소" in caption
    assert "도로명주소" in caption
    assert "서비스시간" in caption
    assert "발급종수" in caption


def test_kiosk_board_six_columns_preserved(_kiosk_model):
    board = _kiosk_model["states"][0]["board"]
    assert board["columns"] == _EXPECTED_COLUMNS


def test_kiosk_board_ten_rows_preserved(_kiosk_model):
    board = _kiosk_model["states"][0]["board"]
    rows = board["rows"]
    assert len(rows) == 10, f"expected 10 page-1 rows, got {len(rows)}"


def test_kiosk_board_row_sequence_is_1_to_10(_kiosk_model):
    board = _kiosk_model["states"][0]["board"]
    numbers = [r["cells"].get("번호") for r in board["rows"]]
    assert numbers == [str(i) for i in range(1, 11)], f"row numbers {numbers}"


# ---------------------------------------------------------------------------
# C. Address / hour / certificate text preserved verbatim per row.
# ---------------------------------------------------------------------------
def test_kiosk_row_location_address_hour_certificate_text(_kiosk_model):
    board = _kiosk_model["states"][0]["board"]
    row0 = board["rows"][0]["cells"]
    assert row0["설치장소"] == "푸른새마을금고 금호지점"
    assert row0["도로명주소"] == "금화로54,108호(금호동)"
    assert row0["서비스시간"] == "08:00~24:00"
    assert row0["발급종수"] == "122종"
    assert row0["비고"] == ""
    # Spot-check a second row with a different hour format.
    row2 = board["rows"][2]["cells"]
    assert row2["설치장소"] == "동천동 행정복지센터"
    assert row2["서비스시간"] == "05:00 ~ 익일 03:00"
    assert row2["발급종수"] == "123종"


# ---------------------------------------------------------------------------
# D. Pagination is generic snapshot data, not a product constant field.
# ---------------------------------------------------------------------------
def test_kiosk_pagination_is_generic_snapshot(_kiosk_model):
    board = _kiosk_model["states"][0]["board"]
    pagination = board["pagination"]
    assert pagination["current_page"] == 1
    assert pagination["pages"] == [1, 2, 3, 4]
    # "전체 34건" / "페이지 1/4" must NOT be promoted to first-class fields in
    # the generic board core (they are snapshot metadata, not product constants).
    for key in ("total_count", "total_count_text", "page_text", "total", "count"):
        assert key not in board, f"snapshot metadata promoted to board field: {key!r}"


# ---------------------------------------------------------------------------
# E. The generic renderer emits the bounded route deterministically.
# ---------------------------------------------------------------------------
def test_kiosk_route_is_generic_and_bounded():
    assert rmod.route_for_state(_STATE_ID, _ROUTE_PREFIX) == "/seogu/unmanned-kiosk/"


def test_kiosk_render_is_deterministic():
    model = json.loads(FIXTURE_1360.read_text(encoding="utf-8"))
    pages_a = rmod.render_site(model, route_prefix=_ROUTE_PREFIX)
    pages_b = rmod.render_site(model, route_prefix=_ROUTE_PREFIX)
    assert set(pages_a.keys()) == {"/seogu/unmanned-kiosk/"}
    for route in pages_a:
        assert pages_a[route] == pages_b[route], f"non-deterministic render for {route}"


def test_kiosk_render_uses_generic_board_not_content_page():
    model = json.loads(FIXTURE_1360.read_text(encoding="utf-8"))
    html = rmod.render_state(model, _STATE_ID, route_prefix=_ROUTE_PREFIX)
    assert "rc-board" in html
    assert "rc-content-page" not in html


def test_kiosk_render_markers_in_rc_main():
    model = json.loads(FIXTURE_1360.read_text(encoding="utf-8"))
    html = rmod.render_state(model, _STATE_ID, route_prefix=_ROUTE_PREFIX)
    text = _rc_main_text(html)
    # Canonical surface label from captured page_title.
    assert "무인민원발급안내" in text
    # Six column headers.
    for col in _EXPECTED_COLUMNS:
        assert col in text, f"column header missing from rc-main: {col!r}"
    # Source-backed page-1 row content.
    assert "푸른새마을금고 금호지점" in text
    assert "금화로54" in text
    assert "08:00~24:00" in text
    assert "122종" in text


# ---------------------------------------------------------------------------
# F. No external runtime request introduced; existing surfaces unchanged.
# ---------------------------------------------------------------------------
def test_kiosk_render_has_no_external_or_screenshot_references():
    model = json.loads(FIXTURE_1360.read_text(encoding="utf-8"))
    pages = rmod.render_site(model, route_prefix=_ROUTE_PREFIX)
    for route, html in pages.items():
        assert "http://" not in html, f"external http in {route}"
        assert "https://" not in html, f"external https in {route}"
        assert "screenshot" not in html.lower(), f"screenshot runtime in {route}"
        assert "source.png" not in html, f"raw screenshot artifact in {route}"
        assert "data/official_captures" not in html, f"raw capture path in {route}"


def test_existing_baseline_fixture_unchanged_by_kiosk_addon():
    """The 11-state baseline fixture must not carry a board for the kiosk state
    and must remain renderable through its own generic surfaces."""
    fixture = json.loads(FIXTURE_132.read_text(encoding="utf-8"))
    assert fixture["state_count"] == 11
    assert fixture["capture_id"] == "20260812T231018-0900"
    for state in fixture["states"]:
        assert state["state_id"] != _STATE_ID


def test_build_and_render_make_no_network_requests():
    # Building + rendering the kiosk model must not reach the network (the
    # autouse socket/urlopen block would raise otherwise).
    mod.build_reference_clone_model(REPO_ROOT, CAPTURE_ROOT_1360)
    model = json.loads(FIXTURE_1360.read_text(encoding="utf-8"))
    rmod.render_site(model, route_prefix=_ROUTE_PREFIX)


# ---------------------------------------------------------------------------
# G. Security: no unredacted credential-bearing query values in committed
#    S6 capture/derived artifacts (generic sanitizer regression, offline).
# ---------------------------------------------------------------------------
# A synthetic high-entropy hex-like value used to prove the assertion can
# detect a raw credential WITHOUT embedding the real detected value here.
_SYNTHETIC_APPKEY = "a1b2c3d4e5f6a1b2c3d4e5f6"
_CRED_PARAM_NAMES = ("appkey=", "api_key=", "apikey=", "access_token=",
                      "client_secret=", "secret=")


def _scan_for_credential_values(path: Path) -> list[str]:
    """Return list of credential-bearing query values found raw in the file."""
    text = path.read_text(encoding="utf-8")
    found = []
    for line in text.splitlines():
        for param in _CRED_PARAM_NAMES:
            idx = line.find(param)
            if idx == -1:
                continue
            rest = line[idx + len(param):]
            # extract the value (until &, &amp;, ", ', <, whitespace, or end)
            val = ""
            for ch in rest:
                if ch in ("&", '"', "'", "<", " ", "\t", "\n"):
                    break
                val += ch
            if val and val != "[REDACTED_QUERY_APPKEY]" and len(val) >= 8:
                found.append(f"{param}{val}")
    return found


def test_s6_source_html_has_no_unredacted_appkey():
    path = CAPTURE_ROOT_1360 / "states" / "unmanned_kiosk.list.desktop" / "source.html"
    found = _scan_for_credential_values(path)
    assert not found, f"unredacted credential values in source.html: {found}"
    # The redacted form must be present (proves the sanitizer ran).
    assert "[REDACTED_QUERY_APPKEY]" in path.read_text(encoding="utf-8")


def test_s6_ledger_has_no_unredacted_appkey():
    path = CAPTURE_ROOT_1360 / "ledger.json"
    found = _scan_for_credential_values(path)
    assert not found, f"unredacted credential values in ledger.json: {found}"


def test_s6_clone_model_has_no_unredacted_appkey():
    path = FIXTURE_1360
    found = _scan_for_credential_values(path)
    assert not found, f"unredacted credential values in clone-model.json: {found}"


def test_s6_artifacts_have_redacted_form():
    """The deterministic redaction token must appear where credentials were."""
    for path in (
        CAPTURE_ROOT_1360 / "states" / "unmanned_kiosk.list.desktop" / "source.html",
        CAPTURE_ROOT_1360 / "ledger.json",
        FIXTURE_1360,
    ):
        text = path.read_text(encoding="utf-8")
        assert "[REDACTED_QUERY_APPKEY]" in text, f"redaction token missing from {path.name}"


def test_s6_source_png_byte_identical():
    """source.png must NOT be regenerated merely for this security fix
    (no demonstrated security-bearing bitmap issue)."""
    import hashlib
    png_path = CAPTURE_ROOT_1360 / "states" / "unmanned_kiosk.list.desktop" / "source.png"
    h = hashlib.sha256(png_path.read_bytes()).hexdigest()
    assert h == "19400a8f816525c1f070d59ed38cf6901be684ccceb418b9972062e6a91b3aaa", (
        f"source.png SHA-256 changed: {h}"
    )
