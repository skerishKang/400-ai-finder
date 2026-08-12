"""Offline generic structural preview tests (#1232).

Pure stdlib + pytest. No network / provider / Firecrawl / API calls.

Consumes the checked-in Seo-gu Site Model bundle
(tests/fixtures/platform/site-model/seogu.json) produced by the Site Model
stage and verifies the deterministic static structural preview renderer
(src.site_profiles.offline_preview.build_offline_preview).

Positive coverage: determinism, no input mutation, exact route/file/link
counts, metadata + capability parity, provenance parity, asset parity, HTML
safety, frozen-manifest exact equality, and all production/live/control/visual
claim flags false.

Negative coverage: fail-closed rejection of malformed bundles.

Genericity coverage: synthetic non-root action graphs (chains, cycles, fan-out,
root-less graphs) prove navigation is rendered on each action's own
``from_route_id`` page with hrefs relative to that page - not root-star
hard-coded.

Strictness coverage: nested ``qa_manifest`` gate flags are required exactly,
with no top-level fallback rescue.

CLI coverage: ``scripts/build_offline_site_preview.py`` fails closed on
symlinked out-dirs, symlinked intermediate components and symlinked targets,
writing zero files outside the out-dir.
"""

import copy
import importlib.util
import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

import pytest

from src.site_profiles.offline_preview import (
    OfflinePreviewError,
    build_offline_preview,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "platform" / "site-model" / "seogu.json"
MANIFEST_FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "platform" / "site-preview" / "seogu-manifest.json"
)
CLI_SCRIPT = REPO_ROOT / "scripts" / "build_offline_site_preview.py"

HREF_RE = re.compile(r'href="([^"]*)"', re.IGNORECASE)
SRC_RE = re.compile(r'src="([^"]*)"', re.IGNORECASE)
ANCHOR_RE = re.compile(r"<a\b[^>]*>", re.IGNORECASE)
TAG_RE = re.compile(r"<([a-zA-Z0-9]+)\b", re.IGNORECASE)
EXTERNAL_RE = re.compile(r'^(https?:|//|data:|javascript:|vbscript:|file:|blob:)', re.IGNORECASE)
NAV_RE = re.compile(r"<nav\b.*?</nav>", re.IGNORECASE | re.DOTALL)
NAV_LINK_RE = re.compile(r'<a\s+href="([^"]*)"\s*>(.*?)</a>', re.IGNORECASE | re.DOTALL)

ROOT_ROUTE_ID = "route-homepage"


def _load_bundle():
    with open(MODEL_FIXTURE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _all_hrefs(pages):
    hrefs = []
    for html in pages.values():
        hrefs.extend(HREF_RE.findall(html))
    return hrefs


def _count_anchors(pages):
    return sum(len(ANCHOR_RE.findall(html)) for html in pages.values())


# --------------------------------------------------------------------------- #
# Positive
# --------------------------------------------------------------------------- #


def test_deterministic():
    b = _load_bundle()
    r1 = build_offline_preview(b)
    r2 = build_offline_preview(b)
    assert r1 == r2


def test_no_input_mutation():
    b = _load_bundle()
    before = copy.deepcopy(b)
    build_offline_preview(b)
    assert b == before


def test_route_count():
    r = build_offline_preview(_load_bundle())
    assert r["manifest"]["route_count"] == 10


def test_root_index_html_present():
    r = build_offline_preview(_load_bundle())
    assert "index.html" in r["pages"]


def test_nine_route_files_present():
    r = build_offline_preview(_load_bundle())
    route_files = [k for k in r["pages"] if k.startswith("routes/")]
    assert len(route_files) == 9
    for i in range(1, 10):
        assert f"routes/route-{i:06d}.html" in r["pages"]


def test_nine_modeled_actions_and_links():
    r = build_offline_preview(_load_bundle())
    assert r["manifest"]["action_count"] == 9
    assert _count_anchors(r["pages"]) == 9


def test_every_link_resolves():
    r = build_offline_preview(_load_bundle())
    for href in _all_hrefs(r["pages"]):
        assert href in r["pages"], f"link target missing: {href}"


def test_no_extra_route_or_link():
    r = build_offline_preview(_load_bundle())
    assert len(r["pages"]) == 10
    assert _count_anchors(r["pages"]) == 9
    for href in _all_hrefs(r["pages"]):
        assert not EXTERNAL_RE.match(href), f"unexpected external href: {href}"


def test_document_metadata_parity():
    bundle = _load_bundle()
    r = build_offline_preview(bundle)
    routes = {rt["route_id"]: rt for rt in bundle["site_model"]["routes"]}
    for rt in bundle["site_model"]["routes"]:
        rid = rt["route_id"]
        if rid == ROOT_ROUTE_ID:
            continue
        html = r["pages"][f"routes/{rid}.html"]
        for key in ("title", "category", "content_type", "document_id"):
            val = rt.get(key)
            if val is not None:
                assert _esc_substr(val) in html, f"{rid}: {key} not rendered"
        st = rt.get("source_types")
        if st is not None:
            assert _esc_substr(", ".join(st) if isinstance(st, list) else st) in html


def test_capability_parity():
    bundle = _load_bundle()
    r = build_offline_preview(bundle)
    html = r["pages"]["index.html"]
    for b in bundle["capability_bindings"]:
        assert b["capability_id"] in html
        assert b["candidate_state"] in html
        assert b["binding_state"] in html


def test_directory_stays_review_required():
    r = build_offline_preview(_load_bundle())
    html = r["pages"]["index.html"]
    # directory is review_required in both candidate and binding state.
    assert html.count("review_required") >= 2
    # review_required must NOT be expressed as "supported".
    assert "supported" not in html


def test_provenance_exact():
    bundle = _load_bundle()
    r = build_offline_preview(bundle)
    expected = list(bundle["provenance"]["source_refs"])
    assert r["manifest"]["provenance"]["source_refs"] == expected


def test_asset_parity():
    r = build_offline_preview(_load_bundle())
    assert r["manifest"]["assets"] == []
    assert r["manifest"]["external_assets"] == []


def test_no_external_href_or_src():
    r = build_offline_preview(_load_bundle())
    for html in r["pages"].values():
        for href in HREF_RE.findall(html):
            assert not EXTERNAL_RE.match(href), f"external href: {href}"
        for src in SRC_RE.findall(html):
            assert not EXTERNAL_RE.match(src), f"external src: {src}"


def test_no_script_iframe_form_input():
    r = build_offline_preview(_load_bundle())
    for html in r["pages"].values():
        lowered = html.lower()
        assert "<script" not in lowered
        assert "<iframe" not in lowered
        assert "<form" not in lowered
        assert "<input" not in lowered
        assert "<button" not in lowered
        assert "onclick" not in lowered
        assert "javascript:" not in lowered


def test_html_escaping():
    bundle = _load_bundle()
    malicious = '<script>alert(1)</script>"><img src=x onerror=alert(2)>'
    # Inject via a route title (free string; passes validation).
    bundle["site_model"]["routes"][1]["title"] = malicious
    r = build_offline_preview(bundle)
    html = r["pages"]["routes/route-000001.html"]
    assert malicious not in html
    assert "&lt;script&gt;" in html
    assert "<script>" not in html


def test_frozen_manifest_exact_equality():
    r = build_offline_preview(_load_bundle())
    with open(MANIFEST_FIXTURE, "r", encoding="utf-8") as fh:
        frozen = json.load(fh)
    assert r["manifest"] == frozen


def test_all_claim_flags_false():
    r = build_offline_preview(_load_bundle())
    m = r["manifest"]
    assert m["offline_only"] is True
    assert m["live_network_authorized"] is False
    assert m["actual_site_control_authorized"] is False
    assert m["production_ready"] is False
    assert m["production_promotion_requested"] is False
    assert m["visual_parity_claimed"] is False


# --------------------------------------------------------------------------- #
# Negative (fail-closed)
# --------------------------------------------------------------------------- #


def _mutate(fn):
    b = _load_bundle()
    fn(b)
    return b


def test_reject_missing_root():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(_mutate(lambda b: b["site_model"].pop("root_route_id")))


def test_reject_duplicate_route_id():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                lambda b: b["site_model"]["routes"].append(
                    dict(b["site_model"]["routes"][1])
                )
            )
        )


def test_reject_unsafe_route_id():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                lambda b: b["site_model"]["routes"].append(
                    {
                        "route_id": "../escape",
                        "document_id": None,
                        "url": "x",
                        "canonical_url": "x",
                        "title": None,
                        "category": None,
                        "content_type": None,
                        "source_types": None,
                    }
                )
            )
        )


def test_reject_unresolved_document():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                lambda b: b["site_model"]["routes"].__setitem__(
                    1, dict(b["site_model"]["routes"][1], document_id="doc-MISSING")
                )
            )
        )


def test_reject_unresolved_action_from():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                lambda b: b["action_graph"]["actions"].__setitem__(
                    0, dict(b["action_graph"]["actions"][0], from_route_id="route-MISSING")
                )
            )
        )


def test_reject_unresolved_action_to():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                lambda b: b["action_graph"]["actions"].__setitem__(
                    0, dict(b["action_graph"]["actions"][0], to_route_id="route-MISSING")
                )
            )
        )


def test_reject_non_navigate_action():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                lambda b: b["action_graph"]["actions"].__setitem__(
                    0, dict(b["action_graph"]["actions"][0], action_type="click")
                )
            )
        )


def test_reject_unresolved_detected_capability_route():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                lambda b: b["capability_bindings"].__setitem__(
                    0, dict(b["capability_bindings"][0], route_ids=["route-MISSING"])
                )
            )
        )


def test_reject_falsely_bound_review_required():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                lambda b: b["capability_bindings"].__setitem__(
                    2, dict(b["capability_bindings"][2], binding_state="bound")
                )
            )
        )


# --------------------------------------------------------------------------- #
# Capability binding state contract (ISSUE #1232 fail-closed correction)
#
# For candidate_state in {configured, detected}: binding_state must be exactly
# "bound" and route_ids must hold >= 1 resolved route. For candidate_state
# "review_required": binding_state must be exactly "review_required" and
# route_ids must be empty. Any other combination is rejected.
# --------------------------------------------------------------------------- #


def _set_binding(capability_id, **fields):
    """Mutate one capability binding (matched by capability_id) in a frozen copy."""

    def _fn(b):
        for cb in b["capability_bindings"]:
            if cb.get("capability_id") == capability_id:
                cb.update(fields)
                break
        else:
            b["capability_bindings"].append(
                {
                    "capability_id": capability_id,
                    **fields,
                }
            )

    return _fn


def test_reject_review_required_with_supported_state():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(_set_binding("directory", binding_state="supported", route_ids=[]))
        )


def test_reject_review_required_with_unbound_state():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(_set_binding("directory", binding_state="unbound", route_ids=[]))
        )


def test_reject_review_required_with_arbitrary_state():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(_set_binding("directory", binding_state="anything", route_ids=[]))
        )


def test_reject_review_required_carrying_route():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                _set_binding(
                    "directory", binding_state="review_required", route_ids=["route-000001"]
                )
            )
        )


def test_reject_detected_bound_with_empty_routes():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(_set_binding("notice_board", binding_state="bound", route_ids=[]))
        )


def test_reject_detected_bound_document_library_empty_routes():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                _set_binding("document_library", binding_state="bound", route_ids=[])
            )
        )


def test_reject_configured_bound_with_empty_routes():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                _set_binding(
                    "synthetic_configured",
                    candidate_state="configured",
                    binding_state="bound",
                    route_ids=[],
                )
            )
        )


def test_reject_route_ids_string_instead_of_list():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                _set_binding("notice_board", binding_state="bound", route_ids="route-000003")
            )
        )


def test_reject_route_ids_none_for_detected():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(_set_binding("notice_board", binding_state="bound", route_ids=None))
        )


def test_frozen_seogu_capability_bindings_remain_green():
    r = build_offline_preview(_load_bundle())
    bindings = {
        cb["capability_id"]: cb for cb in r["manifest"]["capability_bindings"]
    }
    assert bindings["notice_board"] == {
        "capability_id": "notice_board",
        "candidate_state": "detected",
        "binding_state": "bound",
        "route_ids": ["route-000003"],
    }
    assert bindings["document_library"] == {
        "capability_id": "document_library",
        "candidate_state": "detected",
        "binding_state": "bound",
        "route_ids": ["route-000006"],
    }
    assert bindings["directory"] == {
        "capability_id": "directory",
        "candidate_state": "review_required",
        "binding_state": "review_required",
        "route_ids": [],
    }


def test_reject_live_network_true():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                lambda b: b["qa_manifest"].__setitem__("live_network_authorized", True)
            )
        )


def test_reject_actual_site_control_true():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                lambda b: b["qa_manifest"].__setitem__(
                    "actual_site_control_authorized", True
                )
            )
        )


def test_reject_production_ready_true():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(lambda b: b["qa_manifest"].__setitem__("production_ready", True))
        )


def test_reject_production_promotion_true():
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(
            _mutate(
                lambda b: b["qa_manifest"].__setitem__(
                    "production_promotion_requested", True
                )
            )
        )


def _esc_substr(value):
    import html as _html

    return _html.escape(str(value), quote=True)


# --------------------------------------------------------------------------- #
# Generic action-graph navigation (BLOCKER 1 + 2)
#
# The renderer must place each modeled action on the page of its own
# from_route_id and compute the href relative to that source page. These tests
# are deliberately independent of Seo-gu's root-star topology.
# --------------------------------------------------------------------------- #


def _act(index, from_route_id, to_route_id):
    return {
        "action_id": f"action-{index:06d}",
        "action_type": "navigate",
        "from_route_id": from_route_id,
        "to_route_id": to_route_id,
        "safety_level": "navigate",
        "requires_user_confirmation": False,
    }


def _bundle_with_actions(pairs):
    """Frozen fixture bundle with its action graph replaced by ``pairs``."""
    bundle = _load_bundle()
    bundle["action_graph"]["actions"] = [
        _act(i, src, dst) for i, (src, dst) in enumerate(pairs, start=1)
    ]
    bundle["action_graph"]["action_count"] = len(pairs)
    return bundle


def _output_path_for(root_route_id, route_id):
    return "index.html" if route_id == root_route_id else f"routes/{route_id}.html"


def _resolve_href(source_output_path, href):
    """Resolve a rendered href the way a browser would, from its source page."""
    base = posixpath.dirname(source_output_path)
    return posixpath.normpath(posixpath.join(base, href))


def _nav_links(html):
    """[(href, text)] inside the page's <nav>, or None when the page has none."""
    nav = NAV_RE.search(html)
    if nav is None:
        return None
    return NAV_LINK_RE.findall(nav.group(0))


def _nav_hrefs(html):
    links = _nav_links(html)
    return None if links is None else [href for href, _text in links]


# route-000001 .. route-000009 exist in the frozen fixture; the synthetic
# topologies below only rewire actions between already-modeled routes.
TOPOLOGIES = {
    # required synthetic graph: root -> 1 -> 2 -> root
    "cycle_root_1_2": [
        (ROOT_ROUTE_ID, "route-000001"),
        ("route-000001", "route-000002"),
        ("route-000002", ROOT_ROUTE_ID),
    ],
    # no action leaves root at all: root must render no nav
    "non_root_chain_only": [
        ("route-000001", "route-000002"),
        ("route-000002", "route-000003"),
    ],
    # a non-root route with several outgoing actions, including back to root
    "non_root_fanout": [
        ("route-000004", "route-000005"),
        ("route-000004", "route-000006"),
        ("route-000004", ROOT_ROUTE_ID),
    ],
    # mutual sibling links
    "sibling_pair": [
        ("route-000007", "route-000008"),
        ("route-000008", "route-000007"),
    ],
    # mixed root and non-root sources
    "mixed_root_and_non_root": [
        (ROOT_ROUTE_ID, "route-000005"),
        ("route-000005", ROOT_ROUTE_ID),
        ("route-000005", "route-000009"),
        ("route-000009", "route-000005"),
    ],
    # self link stays on its own page
    "self_link": [("route-000003", "route-000003")],
}


def _assert_graph_rendered_exactly(bundle):
    """Every action renders once, on its own source page, with a working href."""
    result = build_offline_preview(bundle)
    pages = result["pages"]
    root = bundle["site_model"]["root_route_id"]
    actions = bundle["action_graph"]["actions"]

    expected_by_source = {}
    for action in actions:
        expected_by_source.setdefault(action["from_route_id"], []).append(
            action["to_route_id"]
        )

    rendered_total = 0
    for route in bundle["site_model"]["routes"]:
        rid = route["route_id"]
        out = _output_path_for(root, rid)
        assert out in pages, f"missing generated page for {rid}"
        links = _nav_links(pages[out])
        wanted = expected_by_source.get(rid, [])

        if not wanted:
            # A route with zero outgoing actions must have no nav at all.
            assert links is None, f"{rid}: page must have no nav, got {links}"
            assert not ANCHOR_RE.findall(pages[out]), f"{rid}: unexpected anchor"
            continue

        assert links is not None, f"{rid}: expected nav for {len(wanted)} action(s)"
        assert len(links) == len(wanted), f"{rid}: nav link count mismatch"

        for (href, text), target in zip(links, wanted):
            target_out = _output_path_for(root, target)
            # href must be relative to THIS source page and resolve to target.
            assert _resolve_href(out, href) == target_out, (
                f"{rid}: href {href!r} on {out} resolves to "
                f"{_resolve_href(out, href)!r}, expected {target_out!r}"
            )
            assert _resolve_href(out, href) in pages, f"{rid}: dangling {href!r}"
            assert "routes/routes" not in href, f"{rid}: doubled dir in {href!r}"
            assert "\\" not in href, f"{rid}: backslash separator in {href!r}"
            assert not href.startswith("/"), f"{rid}: absolute href {href!r}"
            assert not EXTERNAL_RE.match(href), f"{rid}: external href {href!r}"
            assert text.strip(), f"{rid}: empty link text for {href!r}"
        rendered_total += len(links)

    # 1:1 mapping: every modeled action -> exactly one rendered link, and no
    # anchor anywhere that is not a modeled action.
    assert rendered_total == len(actions)
    assert _count_anchors(pages) == len(actions)
    return result


@pytest.mark.parametrize("name", sorted(TOPOLOGIES))
def test_synthetic_action_graph_renders_on_source_route(name):
    _assert_graph_rendered_exactly(_bundle_with_actions(TOPOLOGIES[name]))


def test_frozen_seogu_graph_renders_on_source_route():
    # Same generic invariant, applied to the untouched frozen bundle.
    _assert_graph_rendered_exactly(_load_bundle())


def test_required_synthetic_non_root_exact_hrefs():
    """root -> 1 -> 2 -> root with the exact hrefs the contract demands."""
    bundle = _bundle_with_actions(TOPOLOGIES["cycle_root_1_2"])
    pages = build_offline_preview(bundle)["pages"]

    # index.html contains only its own modeled outgoing action.
    assert _nav_hrefs(pages["index.html"]) == ["routes/route-000001.html"]
    # non-root sibling hop is relative to the routes/ dir.
    assert _nav_hrefs(pages["routes/route-000001.html"]) == ["route-000002.html"]
    # non-root -> root climbs out of routes/.
    assert _nav_hrefs(pages["routes/route-000002.html"]) == ["../index.html"]

    # Every other route models no outgoing action -> no nav.
    for i in range(3, 10):
        assert _nav_hrefs(pages[f"routes/route-{i:06d}.html"]) is None

    assert _count_anchors(pages) == 3


def test_no_action_appears_on_foreign_page():
    """A page must never render an action whose from_route_id is another route."""
    bundle = _bundle_with_actions(TOPOLOGIES["cycle_root_1_2"])
    pages = build_offline_preview(bundle)["pages"]

    # root only owns root -> route-000001.
    root_html = pages["index.html"]
    assert "route-000002" not in root_html
    assert root_html.count("route-000001") == 1

    # route-000001 only owns route-000001 -> route-000002 (no root link).
    r1_html = pages["routes/route-000001.html"]
    assert "../index.html" not in r1_html

    # route-000002 only owns route-000002 -> root (no sibling link).
    r2_html = pages["routes/route-000002.html"]
    assert "route-000001.html" not in r2_html


def test_root_without_outgoing_actions_has_no_nav():
    bundle = _bundle_with_actions(TOPOLOGIES["non_root_chain_only"])
    pages = build_offline_preview(bundle)["pages"]
    assert _nav_hrefs(pages["index.html"]) is None
    assert _nav_hrefs(pages["routes/route-000001.html"]) == ["route-000002.html"]
    assert _nav_hrefs(pages["routes/route-000002.html"]) == ["route-000003.html"]
    assert _nav_hrefs(pages["routes/route-000003.html"]) is None


def test_empty_action_graph_renders_no_nav_anywhere():
    bundle = _bundle_with_actions([])
    result = build_offline_preview(bundle)
    assert result["manifest"]["action_count"] == 0
    assert _count_anchors(result["pages"]) == 0
    for path, html in result["pages"].items():
        assert _nav_links(html) is None, f"{path}: unexpected nav"


def test_non_root_multi_outgoing_hrefs_are_sibling_relative():
    bundle = _bundle_with_actions(TOPOLOGIES["non_root_fanout"])
    pages = build_offline_preview(bundle)["pages"]
    assert _nav_hrefs(pages["routes/route-000004.html"]) == [
        "route-000005.html",
        "route-000006.html",
        "../index.html",
    ]


def test_self_link_href_is_own_file():
    bundle = _bundle_with_actions(TOPOLOGIES["self_link"])
    pages = build_offline_preview(bundle)["pages"]
    assert _nav_hrefs(pages["routes/route-000003.html"]) == ["route-000003.html"]


def test_generated_hrefs_never_use_windows_separator():
    for pairs in TOPOLOGIES.values():
        pages = build_offline_preview(_bundle_with_actions(pairs))["pages"]
        for path, html in pages.items():
            for href in HREF_RE.findall(html):
                assert "\\" not in href, f"{path}: backslash in {href!r}"
                assert "routes/routes" not in href, f"{path}: doubled {href!r}"


def test_frozen_seogu_nav_distribution_preserved():
    """Frozen Seo-gu stays root-star: 9 links on root, 0 on the 9 route pages."""
    pages = build_offline_preview(_load_bundle())["pages"]
    assert len(_nav_hrefs(pages["index.html"])) == 9
    for i in range(1, 10):
        assert _nav_hrefs(pages[f"routes/route-{i:06d}.html"]) is None
    assert _count_anchors(pages) == 9


# --------------------------------------------------------------------------- #
# Strict nested qa_manifest gate flags (BLOCKER 3)
#
# qa_manifest must be a mapping carrying every gate flag with the exact
# expected boolean. A top-level duplicate must never rescue a missing or
# malformed nested value.
# --------------------------------------------------------------------------- #

QA_REQUIRED_FLAGS = {
    "offline_preview_input_ready": True,
    "production_ready": False,
    "production_promotion_requested": False,
    "actual_site_control_authorized": False,
    "live_network_authorized": False,
}


def test_frozen_bundle_carries_nested_qa_flags_only():
    bundle = _load_bundle()
    for flag, expected in QA_REQUIRED_FLAGS.items():
        assert bundle["qa_manifest"][flag] is expected
        # the positive fixture must not rely on a top-level duplicate
        assert flag not in bundle


@pytest.mark.parametrize("flag", sorted(QA_REQUIRED_FLAGS))
def test_reject_missing_qa_flag(flag):
    bundle = _load_bundle()
    del bundle["qa_manifest"][flag]
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(bundle)


@pytest.mark.parametrize("flag,expected", sorted(QA_REQUIRED_FLAGS.items()))
def test_top_level_duplicate_cannot_rescue_missing_qa_flag(flag, expected):
    bundle = _load_bundle()
    del bundle["qa_manifest"][flag]
    bundle[flag] = expected  # correct value, but at the wrong level
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(bundle)


def test_reject_missing_qa_offline_preview_input_ready_with_top_level_true():
    """Regression A."""
    bundle = _load_bundle()
    del bundle["qa_manifest"]["offline_preview_input_ready"]
    bundle["offline_preview_input_ready"] = True
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(bundle)


def test_reject_missing_qa_production_ready_with_top_level_false():
    """Regression B."""
    bundle = _load_bundle()
    del bundle["qa_manifest"]["production_ready"]
    bundle["production_ready"] = False
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(bundle)


@pytest.mark.parametrize(
    "malformed",
    [None, [], ["offline_preview_input_ready"], (), "", "ready", 0, 1, True, 3.5],
    ids=[
        "none",
        "empty_list",
        "list",
        "empty_tuple",
        "empty_string",
        "string",
        "zero",
        "one",
        "true",
        "float",
    ],
)
def test_reject_malformed_qa_manifest(malformed):
    """Regression C."""
    bundle = _load_bundle()
    bundle["qa_manifest"] = malformed
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(bundle)


def test_reject_absent_qa_manifest_key():
    bundle = _load_bundle()
    del bundle["qa_manifest"]
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(bundle)


def test_reject_absent_qa_manifest_with_full_top_level_flags():
    bundle = _load_bundle()
    del bundle["qa_manifest"]
    for flag, expected in QA_REQUIRED_FLAGS.items():
        bundle[flag] = expected
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(bundle)


@pytest.mark.parametrize(
    "flag,bad_value",
    [
        ("offline_preview_input_ready", 1),
        ("offline_preview_input_ready", "true"),
        ("offline_preview_input_ready", "True"),
        ("offline_preview_input_ready", [True]),
        ("offline_preview_input_ready", None),
        ("production_ready", 0),
        ("production_ready", "false"),
        ("production_ready", None),
        ("production_promotion_requested", 0),
        ("production_promotion_requested", "no"),
        ("actual_site_control_authorized", 0),
        ("actual_site_control_authorized", None),
        ("live_network_authorized", 0),
        ("live_network_authorized", "false"),
    ],
)
def test_reject_wrongly_typed_qa_flag(flag, bad_value):
    bundle = _load_bundle()
    bundle["qa_manifest"][flag] = bad_value
    with pytest.raises(OfflinePreviewError):
        build_offline_preview(bundle)


# --------------------------------------------------------------------------- #
# CLI output-path safety (BLOCKER 4)
#
# scripts/build_offline_site_preview.py must reject symlinked out-dirs,
# symlinked intermediate components and symlinked targets, and must never write
# a single byte outside the out-dir.
# --------------------------------------------------------------------------- #

EXPECTED_CLI_FILES = {"index.html", "preview-manifest.json"} | {
    f"routes/route-{i:06d}.html" for i in range(1, 10)
}


def _load_cli_module():
    spec = importlib.util.spec_from_file_location(
        "build_offline_site_preview_under_test", CLI_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_cli(out_dir, bundle=None):
    return subprocess.run(
        [
            sys.executable,
            str(CLI_SCRIPT),
            "--bundle",
            str(bundle or MODEL_FIXTURE),
            "--out-dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _symlink_or_skip(link, target, *, target_is_directory=False):
    """Create a symlink, or skip *only this* test if the OS/account forbids it."""
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - platform
        pytest.skip(f"symlink creation unsupported on this OS/account: {exc}")
    if not link.is_symlink():  # pragma: no cover - platform
        pytest.skip("symlink creation unsupported on this OS/account")


def _relative_files(root):
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and not p.is_symlink()
    }


def _sandbox(tmp_path):
    """OUT and OUTSIDE as siblings, so escapes are countable."""
    out_dir = tmp_path / "OUT"
    outside = tmp_path / "OUTSIDE"
    out_dir.mkdir()
    outside.mkdir()
    return out_dir, outside


def test_cli_writes_exactly_the_expected_files(tmp_path):
    out_dir, outside = _sandbox(tmp_path)
    proc = _run_cli(out_dir)
    assert proc.returncode == 0, proc.stderr
    assert _relative_files(out_dir) == EXPECTED_CLI_FILES
    # nothing escaped into the sibling directory
    assert _relative_files(outside) == set()

    with open(MANIFEST_FIXTURE, "r", encoding="utf-8") as fh:
        frozen = json.load(fh)
    with open(out_dir / "preview-manifest.json", "r", encoding="utf-8") as fh:
        assert json.load(fh) == frozen


def test_cli_rejects_symlinked_out_dir(tmp_path):
    """Symlink regression 1: the out-dir itself is a symlink."""
    outside = tmp_path / "OUTSIDE"
    outside.mkdir()
    link = tmp_path / "OUT"
    _symlink_or_skip(link, outside, target_is_directory=True)

    proc = _run_cli(link)
    assert proc.returncode != 0
    assert "symlink" in proc.stderr.lower()
    assert _relative_files(outside) == set(), "wrote through a symlinked out-dir"


def test_cli_rejects_symlinked_intermediate_component(tmp_path):
    """Symlink regression 2: OUT/routes -> a directory outside OUT."""
    out_dir, outside = _sandbox(tmp_path)
    _symlink_or_skip(out_dir / "routes", outside, target_is_directory=True)

    proc = _run_cli(out_dir)
    assert proc.returncode != 0
    assert "unsafe output path" in proc.stderr.lower()
    # zero files written outside OUT ...
    assert _relative_files(outside) == set()
    # ... and no partially written preview inside OUT either
    assert _relative_files(out_dir) == set()
    # the symlink itself must be rejected, never unlinked or replaced
    assert (out_dir / "routes").is_symlink()


def test_cli_rejects_symlinked_index_html(tmp_path):
    """Symlink regression 3: OUT/index.html -> a file outside OUT."""
    out_dir, outside = _sandbox(tmp_path)
    victim = outside / "victim.html"
    victim.write_text("SENTINEL", encoding="utf-8")
    _symlink_or_skip(out_dir / "index.html", victim)

    proc = _run_cli(out_dir)
    assert proc.returncode != 0
    assert "unsafe output path" in proc.stderr.lower()
    assert victim.read_text(encoding="utf-8") == "SENTINEL", "outside file changed"
    assert _relative_files(outside) == {"victim.html"}
    assert _relative_files(out_dir) == set()
    assert (out_dir / "index.html").is_symlink()


def test_cli_rejects_symlinked_preview_manifest(tmp_path):
    """Symlink regression 4: OUT/preview-manifest.json -> a file outside OUT."""
    out_dir, outside = _sandbox(tmp_path)
    victim = outside / "victim.json"
    victim.write_text("SENTINEL", encoding="utf-8")
    _symlink_or_skip(out_dir / "preview-manifest.json", victim)

    proc = _run_cli(out_dir)
    assert proc.returncode != 0
    assert "unsafe output path" in proc.stderr.lower()
    assert victim.read_text(encoding="utf-8") == "SENTINEL", "outside file changed"
    assert _relative_files(outside) == {"victim.json"}
    # fail-closed before any page write
    assert _relative_files(out_dir) == set()
    assert (out_dir / "preview-manifest.json").is_symlink()


def test_cli_rejects_symlinked_route_page_target(tmp_path):
    out_dir, outside = _sandbox(tmp_path)
    victim = outside / "victim.html"
    victim.write_text("SENTINEL", encoding="utf-8")
    (out_dir / "routes").mkdir()
    _symlink_or_skip(out_dir / "routes" / "route-000001.html", victim)

    proc = _run_cli(out_dir)
    assert proc.returncode != 0
    assert victim.read_text(encoding="utf-8") == "SENTINEL"
    assert _relative_files(outside) == {"victim.html"}
    assert _relative_files(out_dir) == set()


def test_cli_rejects_non_directory_intermediate_component(tmp_path):
    out_dir, _outside = _sandbox(tmp_path)
    (out_dir / "routes").write_text("not a dir", encoding="utf-8")
    proc = _run_cli(out_dir)
    assert proc.returncode != 0
    assert "unsafe output path" in proc.stderr.lower()


def test_cli_rejects_bundle_with_strict_qa_violation(tmp_path):
    out_dir, _outside = _sandbox(tmp_path)
    bad_bundle = tmp_path / "bad-bundle.json"
    bundle = _load_bundle()
    del bundle["qa_manifest"]["offline_preview_input_ready"]
    bundle["offline_preview_input_ready"] = True
    bad_bundle.write_text(json.dumps(bundle), encoding="utf-8")

    proc = _run_cli(out_dir, bundle=bad_bundle)
    assert proc.returncode != 0
    assert "rejected" in proc.stderr.lower()
    assert _relative_files(out_dir) == set()


@pytest.mark.parametrize(
    "rel",
    [
        "",
        "/etc/passwd",
        "../escape.html",
        "routes/../../escape.html",
        "routes//route.html",
        "routes/./route.html",
        "routes\\route.html",
        ".",
        "..",
    ],
)
def test_cli_validate_rel_rejects_unsafe_relative_paths(rel):
    cli = _load_cli_module()
    with pytest.raises(cli.UnsafeOutputPath):
        cli._validate_rel(rel)


def test_cli_validate_rel_accepts_expected_outputs():
    cli = _load_cli_module()
    for rel in sorted(EXPECTED_CLI_FILES):
        assert cli._validate_rel(rel) == rel.split("/")


def test_cli_safe_target_rejects_symlinked_component_without_following(tmp_path):
    cli = _load_cli_module()
    out_dir, outside = _sandbox(tmp_path)
    _symlink_or_skip(out_dir / "routes", outside, target_is_directory=True)
    out_root = out_dir.resolve(strict=True)

    with pytest.raises(cli.UnsafeOutputPath):
        cli._safe_target(
            out_dir, out_root, "routes/route-000001.html", create_parents=False
        )
    # validation must not have created anything through the symlink
    assert _relative_files(outside) == set()


def test_cli_safe_target_accepts_real_paths(tmp_path):
    cli = _load_cli_module()
    out_dir, _outside = _sandbox(tmp_path)
    out_root = out_dir.resolve(strict=True)
    target = cli._safe_target(
        out_dir, out_root, "routes/route-000001.html", create_parents=True
    )
    assert target == out_dir / "routes" / "route-000001.html"
    assert (out_dir / "routes").is_dir()
    assert not (out_dir / "routes").is_symlink()
