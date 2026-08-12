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
"""

import copy
import json
import re
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

HREF_RE = re.compile(r'href="([^"]*)"', re.IGNORECASE)
SRC_RE = re.compile(r'src="([^"]*)"', re.IGNORECASE)
ANCHOR_RE = re.compile(r"<a\b[^>]*>", re.IGNORECASE)
TAG_RE = re.compile(r"<([a-zA-Z0-9]+)\b", re.IGNORECASE)
EXTERNAL_RE = re.compile(r'^(https?:|//|data:|javascript:|vbscript:|file:|blob:)', re.IGNORECASE)

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
