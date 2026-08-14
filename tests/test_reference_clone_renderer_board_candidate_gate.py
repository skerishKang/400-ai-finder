"""Focused fail-closed regressions for the #1312 board fidelity correction.

These tests deliberately stay offline. They verify that unresolved board visual
contract gaps cannot promote list/detail surfaces to a faithful-clone candidate,
that the stripped board geometry cannot silently return as hardcoded CSS, and
that list-to-detail navigation is backed by exact record-id correspondence.
"""

from __future__ import annotations

import importlib
import json
import re
import socket
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

renderer = importlib.import_module("official_clone.reference_clone_renderer")
validator = importlib.import_module("official_clone.visual_contract")

MODEL_PATH = (
    REPO_ROOT
    / "data"
    / "official_clone_fixtures"
    / "seogu_gwangju"
    / "g1"
    / "20260812T231018-0900"
    / "clone-model.json"
)
CONTRACT_PATH = (
    REPO_ROOT
    / "data"
    / "official_clone_visual_inputs"
    / "seogu_gwangju"
    / "g1"
    / "20260812T231018-0900"
    / "visual-contract.json"
)
ROUTE_PREFIX = "/seogu/"
BOARD_STATES = (
    "notice.list.desktop",
    "notice.detail.desktop",
    "gosi.list.desktop",
    "gosi.detail.desktop",
    "civil_form.list.desktop",
    "civil_form.detail.desktop",
)


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch):
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network access is forbidden in #1312 regressions")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _blocked)


def _model():
    return renderer.load_model(MODEL_PATH)


def _contract(model):
    raw = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    return validator.validate_visual_contract(raw, model)


def _lifecycle(html: str) -> dict:
    start = html.index('id="rc-lifecycle"')
    end = html.index("</script>", start)
    return json.loads(html[start:end].split(">", 1)[1])


def test_board_gap_is_state_scoped_promotion_blocker():
    model = _model()
    contract = _contract(model)
    board_gaps = [
        gap
        for gap in contract.get("gaps", [])
        if isinstance(gap, dict)
        and gap.get("measurement_method") == "gap"
        and str(gap.get("region") or "").startswith("board_")
    ]
    assert board_gaps, "#1312 contract must retain explicit unresolved board gaps"

    home = renderer.render_state(
        model,
        "home.desktop.default",
        route_prefix=ROUTE_PREFIX,
        visual_contract=contract,
    )
    assert _lifecycle(home)["faithful_clone_candidate"] is True

    for state_id in BOARD_STATES:
        html = renderer.render_state(
            model,
            state_id,
            route_prefix=ROUTE_PREFIX,
            visual_contract=contract,
        )
        assert _lifecycle(html)["faithful_clone_candidate"] is False, state_id
        assert 'data-clone-candidate="false"' in html


def test_board_gap_geometry_is_not_reintroduced_as_magic_css():
    model = _model()
    contract = _contract(model)
    forbidden = (
        ".rc-subpage-body{display:flex;align-items:flex-start;gap:",
        ".rc-snb{display:flex;flex-direction:column;min-width:",
        ".rc-page-title{font-size:",
        ".rc-detail-title{font-size:",
        "table.rc-board th,table.rc-board td{padding:",
        ".rc-board-head .rc-col-번호,.rc-board-row .rc-col-번호{width:",
        ".rc-board-head .rc-col-조회수,.rc-board-row .rc-col-조회수{width:",
        ".rc-board-head .rc-col-등록일,.rc-board-row .rc-col-등록일{width:",
        ".rc-pagination{display:flex;flex-wrap:wrap;align-items:center;gap:",
        ".rc-detail-meta{display:grid;grid-template-columns:auto 1fr;gap:",
    )
    for state_id in BOARD_STATES:
        html = renderer.render_state(
            model,
            state_id,
            route_prefix=ROUTE_PREFIX,
            visual_contract=contract,
        )
        css = html.split("<style>", 1)[1].split("</style>", 1)[0]
        for token in forbidden:
            assert token not in css, (state_id, token)


def test_linked_rows_exactly_match_family_detail_record_id():
    model = _model()
    expected_counts = {
        "notice": 1,
        "gosi": 0,
        "civil_form": 1,
    }
    for family, expected_count in expected_counts.items():
        state_id = f"{family}.list.desktop"
        state = next(s for s in model["states"] if s.get("state_id") == state_id)
        detail_id = renderer._family_detail_record_id(model, family)
        items = renderer._list_items(model, state, ROUTE_PREFIX)
        linked = [item for item in items if item.get("links_to_detail")]
        assert len(linked) == expected_count, family
        for item in linked:
            assert detail_id is not None
            assert item.get("record_id") == detail_id
            assert item.get("detail_route") == f"{ROUTE_PREFIX}{family.replace('_', '-')}/detail/"

        html = renderer.render_state(model, state_id, route_prefix=ROUTE_PREFIX)
        anchors = re.findall(
            r'<a class="rc-list-link" data-detail="1" href="([^"]+)">([^<]+)</a>',
            html,
        )
        assert len(anchors) == expected_count, family
        if linked:
            assert [text for _href, text in anchors] == [item["text"] for item in linked]
            assert all(href == "detail/" for href, _text in anchors)
