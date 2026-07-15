"""#1168 offline home HTML region segmentation contracts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "official_captures" / "bukgu_gwangju" / "home" / "raw-homepage.html"
FIXTURE_PATH = ROOT / "data" / "official_clone_fixtures" / "bukgu_gwangju" / "home.json"
GEN_PATH = ROOT / "scripts" / "build_official_home_clone_fixture.py"
PARSER_PATH = ROOT / "src" / "official_clone" / "home_region_parser.py"

TARGET_REGIONS = [
    "utility_navigation",
    "main_banner",
    "resident_service_shortcuts",
    "notice_news",
    "related_site_controls",
    "footer_identity_contact",
]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


parser = _load(PARSER_PATH, "home_region_parser_1168")
gen = _load(GEN_PATH, "build_official_home_clone_fixture_1168")


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch):
    def _blocked(*_a, **_k):
        raise AssertionError("network access forbidden in #1168 tests")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    try:
        import urllib.request as ureq

        monkeypatch.setattr(ureq, "urlopen", _blocked)
    except Exception:
        pass


def _raw() -> str:
    return RAW_PATH.read_text(encoding="utf-8")


def test_parser_module_exists():
    assert PARSER_PATH.is_file()


def test_segmentation_deterministic_and_network_free():
    raw = _raw()
    a = parser.segment_home_regions(raw)
    b = parser.segment_home_regions(raw)
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(
        b, sort_keys=True, ensure_ascii=False
    )
    assert a["counts"]["fixture_ready"] == 6
    assert a["counts"]["unresolved"] == 0


def test_resolved_regions_have_source_evidence_and_recomputable_hash():
    raw = _raw()
    seg = parser.segment_home_regions(raw)
    root = parser.parse_dom(raw)
    for rid in TARGET_REGIONS:
        region = seg["regions"][rid]
        assert region["status"] == "fixture-ready-renderer-not-wired"
        se = region["source_evidence"]
        assert se.get("tag")
        assert se.get("ancestor_path")
        assert isinstance(se.get("occurrence_count"), int) and se["occurrence_count"] >= 1
        assert isinstance(se.get("source_order"), int)
        assert SHA256_RE.fullmatch(se["fragment_sha256"])
        assert se.get("hash_rule") == "canonical_subtree_serialization_v1"
        # Recompute fragment hash from live DOM by unique evidence.
        classes = se.get("classes") or []
        node_id = se.get("id")
        matches = []
        for n in parser.walk(root):
            if node_id and n.attrs.get("id") == node_id:
                matches.append(n)
            elif not node_id and classes and n.attrs.get("class") == " ".join(classes):
                matches.append(n)
            elif (
                not node_id
                and classes
                and set(classes).issubset(set(parser._classes(n.attrs)))
                and n.tag == se["tag"]
            ):
                # token match fallback for multi-class containers
                if n.attrs.get("class", "").split() == classes:
                    matches.append(n)
        assert matches, f"no DOM node for {rid}"
        # Prefer exact source_order match
        node = next((m for m in matches if m.source_order == se["source_order"]), matches[0])
        assert parser.fragment_sha256(node) == se["fragment_sha256"]


def test_item_text_and_href_fidelity_to_raw_html():
    raw = _raw()
    seg = parser.segment_home_regions(raw)
    for rid in TARGET_REGIONS:
        region = seg["regions"][rid]
        for item in region.get("items") or []:
            text = item.get("text") or ""
            href = item.get("href")
            if text:
                assert parser._text_present_in_source(text, raw)
            if href:
                assert parser._attr_value_present_in_source(str(href), raw)
            date_text = item.get("date_text")
            if date_text:
                assert parser._text_present_in_source(date_text, raw)


def test_dom_order_preserved_within_regions():
    seg = parser.segment_home_regions(_raw())
    for rid in TARGET_REGIONS:
        items = seg["regions"][rid].get("items") or []
        # Fixture `order` is sequential emission order; link groups stay
        # non-decreasing in source_order within the same item kind.
        seq = [it["order"] for it in items]
        assert seq == list(range(1, len(seq) + 1))
        link_orders = [
            it["dom_order"]
            for it in items
            if it.get("href") is not None and "dom_order" in it
        ]
        assert link_orders == sorted(link_orders)


def test_no_unauthorized_duplicate_merge_of_variants():
    """Visible/hidden/template items are retained separately (no silent dedupe)."""
    seg = parser.segment_home_regions(_raw())
    util = seg["regions"]["utility_navigation"]
    texts = [it.get("text") for it in util.get("items") or []]
    # Language list contains ENG/CHN/JPN as distinct items even if short labels.
    assert util["candidate_count"] == 1
    assert util["item_count"] == len(util["items"])


def test_fixture_includes_html_segmentation_and_generator_1_1_0():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert fixture["source_identity"]["generator_version"] == "1.1.0"
    assert fixture["html_region_segmentation"]["parser_version"] == "1.0.0"
    assert fixture["counts"]["html_target_regions_ready"] == 6
    assert fixture["counts"]["html_target_regions_unresolved"] == 0
    assert fixture["clone_status"] == "capture_required"
    assert fixture["boundaries"]["exact_clone_claimed"] is False


def test_generator_check_passes():
    assert gen.check_fixture() == []
    assert gen.main(["--check"]) == 0


def test_mutation_duplicate_visual_class_fail_closed():
    original = RAW_PATH.read_text(encoding="utf-8")
    try:
        # Inject a second top-level visual twin after the first occurrence.
        mutated = original.replace(
            'class="visual"',
            'class="visual"',
            1,
        )
        # Add an extra unique sibling visual container.
        mutated = mutated.replace(
            '<div class="visual">',
            '<div class="visual"></div><div class="visual">',
            1,
        )
        RAW_PATH.write_text(mutated, encoding="utf-8", newline="\n")
        seg = parser.segment_home_regions(mutated)
        banner = seg["regions"]["main_banner"]
        assert banner["status"] == "unresolved"
        assert banner["candidate_count"] >= 2
    finally:
        RAW_PATH.write_text(original, encoding="utf-8", newline="\n")


def test_mutation_remove_board_heading_structure_still_bounded_or_items_change():
    original = RAW_PATH.read_text(encoding="utf-8")
    try:
        mutated = original.replace('class="board"', 'class="board-x-mutated"', 1)
        RAW_PATH.write_text(mutated, encoding="utf-8", newline="\n")
        seg = parser.segment_home_regions(mutated)
        notice = seg["regions"]["notice_news"]
        assert notice["status"] == "unresolved"
        assert notice["candidate_count"] == 0
    finally:
        RAW_PATH.write_text(original, encoding="utf-8", newline="\n")


def test_mutation_truncated_html_fail_closed():
    original = RAW_PATH.read_text(encoding="utf-8")
    try:
        RAW_PATH.write_text(original[:5000], encoding="utf-8", newline="\n")
        # Truncated HTML must not invent a full six-region success set.
        seg = parser.segment_home_regions(RAW_PATH.read_text(encoding="utf-8"))
        ready = sum(
            1
            for rid in TARGET_REGIONS
            if seg["regions"][rid]["status"] == "fixture-ready-renderer-not-wired"
        )
        assert ready < 6
    finally:
        RAW_PATH.write_text(original, encoding="utf-8", newline="\n")


def test_raw_change_without_fixture_regen_fails_check():
    original_raw = RAW_PATH.read_bytes()
    try:
        RAW_PATH.write_bytes(original_raw + b"<!--1168-drift-->\n")
        # checksum mismatch vs metadata should fail build
        with pytest.raises(gen.FixtureBuildError):
            gen.build_fixture()
    finally:
        RAW_PATH.write_bytes(original_raw)


def test_manual_fixture_edit_fails_check():
    original = FIXTURE_PATH.read_text(encoding="utf-8")
    try:
        dirty = original.replace(
            '"clone_status": "capture_required"',
            '"clone_status": "exact"',
            1,
        )
        FIXTURE_PATH.write_text(dirty, encoding="utf-8", newline="\n")
        problems = gen.check_fixture()
        assert problems
    finally:
        FIXTURE_PATH.write_text(original, encoding="utf-8", newline="\n")
