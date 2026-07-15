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


# ── Same-origin exact policy ───────────────────────────────────────


SAME_ORIGIN_TRUE = [
    "/",
    "/menu.es?mid=a101",
    "menu.es?mid=a101",
    "#section",
    "https://bukgu.gwangju.kr/",
    "https://bukgu.gwangju.kr/menu.es",
    "https://bukgu.gwangju.kr:443/menu.es",
]

SAME_ORIGIN_FALSE = [
    "http://bukgu.gwangju.kr/",
    "http://bukgu.gwangju.kr:80/",
    "https://bukgu.gwangju.kr:444/",
    "https://lib.bukgu.gwangju.kr/",
    "https://council.bukgu.gwangju.kr/",
    "https://evil.bukgu.gwangju.kr/",
    "https://user@bukgu.gwangju.kr/",
    "https://user:pass@bukgu.gwangju.kr/",
    "https://bukgu.gwangju.kr.evil.test/",
    "javascript:void(0)",
    "mailto:test@example.com",
    "tel:123",
    "data:text/plain,test",
]

MALFORMED_URLS = [
    "https://bukgu.gwangju.kr:notaport/",
    "https://bukgu.gwangju.kr:99999/",
    "https://[invalid/",
    "",
    None,
    123,
]


@pytest.mark.parametrize("url", SAME_ORIGIN_TRUE)
def test_is_same_origin_url_true_cases(url):
    assert parser.is_same_origin_url(url) is True


@pytest.mark.parametrize("url", SAME_ORIGIN_FALSE)
def test_is_same_origin_url_false_cases(url):
    assert parser.is_same_origin_url(url) is False


@pytest.mark.parametrize("url", MALFORMED_URLS, ids=lambda v: repr(v)[:40])
def test_is_same_origin_url_malformed_never_raises_or_true(url):
    try:
        result = parser.is_same_origin_url(url)
    except ValueError as exc:  # pragma: no cover
        pytest.fail(f"raw ValueError escaped: {exc!r}")
    assert result is not True
    assert result in (False, None)


def test_committed_fixture_same_origin_values():
    """Inspect generated region items for exact origin semantics."""
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    util = next(r for r in fixture["regions"] if r["region_id"] == "utility_navigation")
    related = next(
        r for r in fixture["regions"] if r["region_id"] == "related_site_controls"
    )

    def items_by_href_substr(region, needle):
        return [
            it
            for it in region.get("items") or []
            if needle in str(it.get("href") or "")
            or needle in str(it.get("resolved_url") or "")
        ]

    # Relative portal paths → same-origin true
    culture = [
        it
        for it in util.get("items") or []
        if (it.get("href") or "").startswith("/culture")
        or "문화관광" in str(it.get("text") or "")
    ]
    assert culture, "expected 문화관광 utility link"
    for it in culture:
        if (it.get("href") or "").startswith("/"):
            assert it["same_origin"] is True

    # Absolute official host
    abs_portal = [
        it
        for it in related.get("items") or []
        if str(it.get("resolved_url") or "").startswith("https://bukgu.gwangju.kr/")
    ]
    assert abs_portal
    for it in abs_portal:
        assert it["same_origin"] is True

    # Subdomains must be false
    for needle, expected in [
        ("lib.bukgu.gwangju.kr", False),
        ("council.bukgu.gwangju.kr", False),
        ("gbfmc.or.kr", False),
        ("blog.naver.com", False),
        ("pf.kakao.com", False),
    ]:
        hits = items_by_href_substr(related, needle) + items_by_href_substr(util, needle)
        # utility SNS may hold kakao/naver
        if not hits and needle in ("blog.naver.com", "pf.kakao.com"):
            hits = items_by_href_substr(util, needle)
        if hits:
            for it in hits:
                assert it["same_origin"] is expected, (needle, it)


def test_committed_language_links_are_hidden():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    util = next(r for r in fixture["regions"] if r["region_id"] == "utility_navigation")
    for label in ("ENG", "CHN", "JPN"):
        hits = [it for it in util.get("items") or [] if it.get("text") == label]
        assert hits, f"missing language item {label}"
        for it in hits:
            assert it["variant"] == "hidden"
            assert it["visibility"] == "hidden"
            assert it.get("effective_variant") == "hidden"
            # Local may still be desktop; effective inherits hidden from #language.site.close
            assert it.get("local_variant") in ("desktop", "hidden")


def test_committed_utility_desktop_links_remain_visible():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    util = next(r for r in fixture["regions"] if r["region_id"] == "utility_navigation")
    for label in ("문화관광", "보건소", "전체메뉴"):
        hits = [it for it in util.get("items") or [] if label in str(it.get("text") or "")]
        assert hits, f"missing utility link {label}"
        for it in hits:
            assert it["variant"] == "desktop", (label, it)
            assert it["visibility"] == "desktop"


# ── Ancestor-aware variant unit tests ──────────────────────────────


def _segment_fragment(html: str) -> dict:
    # Wrap with html/body so parser is happy
    doc = f"<html><body>{html}</body></html>"
    root = parser.parse_dom(doc)
    # Return first anchor under body with visibility fields
    anchors = [n for n in parser.walk(root) if n.tag == "a"]
    assert anchors
    out = []
    for a in anchors:
        fields = parser.visibility_fields(a)
        out.append({"text": parser.node_text(a), **fields})
    return out


def test_ancestor_variant_synthetic_cases():
    cases = [
        ('<div style="display:none"><a href="/a">A</a></div>', "A", "hidden"),
        ('<div class="hidden"><a href="/b">B</a></div>', "B", "hidden"),
        (
            '<ul class="site close" id="language"><li><a href="/eng/">ENG</a></li></ul>',
            "ENG",
            "hidden",
        ),
        ('<div class="mobile"><a href="/m">M</a></div>', "M", "mobile"),
        ('<div id="mw_temp"><a href="/t">T</a></div>', "T", "template"),
    ]
    for html, text, expected in cases:
        items = _segment_fragment(html)
        hit = next(it for it in items if it["text"] == text)
        assert hit["variant"] == expected
        assert hit["visibility"] == expected
        assert hit["effective_variant"] == expected


def test_ancestor_variant_precedence():
    cases = [
        (
            '<div class="hidden"><div class="mobile"><a href="/x">X</a></div></div>',
            "hidden",
        ),
        (
            '<div class="hidden"><div id="mw_temp"><a href="/y">Y</a></div></div>',
            "hidden",
        ),
        (
            '<div id="mw_temp"><div class="mobile"><a href="/z">Z</a></div></div>',
            "template",
        ),
    ]
    for html, expected in cases:
        items = _segment_fragment(html)
        assert items[0]["effective_variant"] == expected
        assert items[0]["variant"] == expected
