"""Offline contracts for the #1303 G2-B generic faithful-clone renderer.

The renderer consumes ONLY the G2-A semantic ``clone-model.json``. These tests
prove:

  * the 11 accepted states render deterministically;
  * model-readiness fail-closed (reference_baseline_ready False -> raise);
  * no raw G1 artifact is read (source scan + output scan);
  * no network is performed;
  * the renderer is generic (NO site-specific branch); no screenshot runtime
    use; no external asset auto-fetch;
  * all modeled routes are deterministic;
  * the GNB-open state is distinguishable from / reachable via the default;
  * notice / gosi / civil-form list & detail surfaces are distinct;
  * attachment affordances are preserved;
  * lifecycle markers are correct (hidden JSON-LD only);
  * a second synthetic site model renders with the SAME generic renderer.

No network, no live site, no provider, no Firecrawl, no API calls.
"""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "official_clone" / "reference_clone_renderer.py"
FIXTURE_PATH = (
    REPO_ROOT
    / "data"
    / "official_clone_fixtures"
    / "seogu_gwangju"
    / "g1"
    / "20260812T231018-0900"
    / "clone-model.json"
)

REQUIRED_11 = [
    "home.desktop.default",
    "home.mobile.default",
    "home.desktop.gnb_open",
    "notice.list.desktop",
    "notice.detail.desktop",
    "gosi.list.desktop",
    "gosi.detail.desktop",
    "civil_form.list.desktop",
    "civil_form.detail.desktop",
    "organization.chart.desktop",
    "staff.directory.desktop",
]

_ROUTE_PREFIX = "/seogu/"


def _load_module():
    spec = importlib.util.spec_from_file_location("reference_clone_renderer", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch):
    """Fail immediately if any routine test attempts network I/O."""
    def _blocked(*_a, **_k):
        raise AssertionError("network access is forbidden in G2-B renderer tests")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    try:
        import urllib.request as ureq

        monkeypatch.setattr(ureq, "urlopen", _blocked)
    except Exception:
        pass
    try:
        import http.client as http_client

        monkeypatch.setattr(http_client.HTTPConnection, "connect", _blocked)
        monkeypatch.setattr(http_client.HTTPSConnection, "connect", _blocked)
    except Exception:
        pass


def _load_model():
    return mod.load_model(FIXTURE_PATH)


# ── Source-level genericity / safety scans ────────────────────────────────
def test_renderer_source_is_not_site_specific():
    source = MODULE_PATH.read_text(encoding="utf-8")
    forbidden = (
        "seogu_gwangju",
        "site_id ==",
        '== "seogu',
        "== 'seogu",
        'site_id=="',
        "Gwangju",
        "Seogu",
    )
    for token in forbidden:
        assert token not in source, f"renderer must not hardcode site literal: {token!r}"
    assert "if site_id" not in source


def test_renderer_source_reads_only_clone_model():
    source = MODULE_PATH.read_text(encoding="utf-8")
    for token in (
        "page.html",
        "screenshot.png",
        "inventory.json",
        "ledger.json",
        "provenance.json",
        "data/official_captures",
        "https://www.seogu.gwangju.kr",
    ):
        assert token not in source, f"renderer must not reference raw G1 artifact: {token!r}"


def test_renderer_source_has_no_external_fetch_logic():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "http://" not in source
    assert "https://" not in source
    assert "urlopen" not in source
    assert "urllib" not in source
    assert "requests." not in source


# ── Determinism / state set ───────────────────────────────────────────────
def test_renders_all_11_required_states():
    model = _load_model()
    for state_id in REQUIRED_11:
        html = mod.render_state(model, state_id, route_prefix=_ROUTE_PREFIX)
        assert isinstance(html, str) and html.strip().startswith("<!DOCTYPE html>")
        assert f'data-state-id="{state_id}"' in html


def test_render_site_produces_unique_deterministic_routes():
    model = _load_model()
    pages_a = mod.render_site(model, route_prefix=_ROUTE_PREFIX)
    pages_b = mod.render_site(model, route_prefix=_ROUTE_PREFIX)
    assert set(pages_a.keys()) == set(pages_b.keys())
    for route in pages_a:
        assert pages_a[route] == pages_b[route], f"non-deterministic render for {route}"
    assert len(pages_a) == 11


def test_model_checksum_is_stable():
    model = _load_model()
    assert mod.model_checksum(model) == mod.model_checksum(model)


# ── Fail-closed on unready model ──────────────────────────────────────────
def test_unready_model_fails_closed():
    model = _load_model()
    model["claim_gates"] = dict(model.get("claim_gates") or {})
    model["claim_gates"]["reference_baseline_ready"] = False
    with pytest.raises(mod.ReferenceCloneRendererError):
        mod.render_state(model, "home.desktop.default", route_prefix=_ROUTE_PREFIX)
    with pytest.raises(mod.ReferenceCloneRendererError):
        mod.render_site(model, route_prefix=_ROUTE_PREFIX)


# ── No raw G1 / screenshot / external in OUTPUT ──────────────────────────
def test_output_has_no_external_or_screenshot_references():
    model = _load_model()
    pages = mod.render_site(model, route_prefix=_ROUTE_PREFIX)
    for route, html in pages.items():
        assert "http://" not in html, f"external http in {route}"
        assert "https://" not in html, f"external https in {route}"
        assert "screenshot" not in html.lower(), f"screenshot runtime in {route}"
        assert "source.png" not in html, f"raw screenshot artifact in {route}"
        assert "data/official_captures" not in html, f"raw capture path in {route}"
        assert '<script src="http' not in html
        assert '<link href="http' not in html


# ── Routes are generic and match the required scheme ─────────────────────
def test_route_scheme_is_generic_and_required():
    expected = {
        "home.desktop.default": "/seogu/",
        "home.mobile.default": "/seogu/home/mobile/",
        "home.desktop.gnb_open": "/seogu/home/gnb-open/",
        "notice.list.desktop": "/seogu/notice/",
        "notice.detail.desktop": "/seogu/notice/detail/",
        "gosi.list.desktop": "/seogu/gosi/",
        "gosi.detail.desktop": "/seogu/gosi/detail/",
        "civil_form.list.desktop": "/seogu/civil-form/",
        "civil_form.detail.desktop": "/seogu/civil-form/detail/",
        "organization.chart.desktop": "/seogu/organization/",
        "staff.directory.desktop": "/seogu/staff/",
    }
    for state_id, route in expected.items():
        assert mod.route_for_state(state_id, _ROUTE_PREFIX) == route, state_id


# ── GNB interaction: distinguishable + reachable ─────────────────────────
def test_gnb_open_distinguishable_from_default():
    model = _load_model()
    default = mod.render_state(model, "home.desktop.default", route_prefix=_ROUTE_PREFIX)
    opened = mod.render_state(model, "home.desktop.gnb_open", route_prefix=_ROUTE_PREFIX)
    # Default is closed.
    assert 'aria-expanded="false"' in default
    assert 'id="rc-mega-menu"' in default
    assert 'id="rc-mega-menu" aria-label="전체메뉴" hidden' in default
    # Open variant is distinguishable.
    assert 'aria-expanded="true"' in opened
    assert 'id="rc-mega-menu" aria-label="전체메뉴"' in opened
    assert ' hidden' not in opened.split('id="rc-mega-menu"', 1)[1].split(">", 1)[0]
    # Both share the toggle control with aria-expanded + aria-controls.
    assert 'id="rc-gnb-toggle"' in default
    assert 'aria-controls="rc-mega-menu"' in default


def test_gnb_mega_menu_contains_open_only_controls():
    model = _load_model()
    opened = mod.render_state(model, "home.desktop.gnb_open", route_prefix=_ROUTE_PREFIX)
    assert "경제" in opened
    assert "고시/공고" in opened


# ── List / detail distinction + attachment affordance ───────────────────
def test_notice_list_links_to_detail_and_distinct():
    model = _load_model()
    listing = mod.render_state(model, "notice.list.desktop", route_prefix=_ROUTE_PREFIX)
    detail = mod.render_state(model, "notice.detail.desktop", route_prefix=_ROUTE_PREFIX)
    assert "rc-list-link" in listing
    assert 'data-detail="1"' in listing
    assert "list_no=143106" in detail
    assert "다운로드 (.hwpx)" in detail
    assert "미리보기" in detail
    assert "다운로드 (.hwpx)" not in listing


def test_notice_detail_captures_required_attachment():
    model = _load_model()
    detail = mod.render_state(model, "notice.detail.desktop", route_prefix=_ROUTE_PREFIX)
    assert "[공고문]사회연대경제 청년 일경험 시범사업 모집공고_참여청년(3차 모집)" in detail
    assert "disabled" in detail
    assert "aria-disabled" in detail
    assert "http://" not in detail
    assert "https://" not in detail


def test_gosi_list_detail_distinct_with_attachment():
    model = _load_model()
    gosi_list = mod.render_state(model, "gosi.list.desktop", route_prefix=_ROUTE_PREFIX)
    gosi_detail = mod.render_state(model, "gosi.detail.desktop", route_prefix=_ROUTE_PREFIX)
    assert gosi_list != gosi_detail
    assert "rc-list-link" in gosi_list
    assert "다운로드 (.doc)" in gosi_detail
    assert "다운로드 (.hwpx)" in gosi_detail
    assert "disabled" in gosi_detail


def test_civil_form_detail_captures_hwp_attachment():
    model = _load_model()
    detail = mod.render_state(model, "civil_form.detail.desktop", route_prefix=_ROUTE_PREFIX)
    assert "list_no=143010" in detail
    assert "자동차 등록 위임장" in detail
    assert "다운로드 (.hwp)" in detail
    assert "disabled" in detail


def test_organization_and_staff_distinct():
    model = _load_model()
    org = mod.render_state(model, "organization.chart.desktop", route_prefix=_ROUTE_PREFIX)
    staff = mod.render_state(model, "staff.directory.desktop", route_prefix=_ROUTE_PREFIX)
    assert org != staff
    assert "행정조직도" in org
    assert "직원 업무안내" in staff


# ── Lifecycle markers ────────────────────────────────────────────────────
def test_lifecycle_markers_present_and_correct():
    model = _load_model()
    html = mod.render_state(model, "home.desktop.default", route_prefix=_ROUTE_PREFIX)
    assert 'id="rc-lifecycle"' in html
    start = html.index('id="rc-lifecycle"')
    end = html.index("</script>", start)
    payload = json.loads(html[start:end].split(">", 1)[1])
    assert payload["faithful_clone_candidate"] is True
    assert payload["visual_review"] == "pending"
    assert payload["clone_mvp_ready"] is False
    assert payload["resident_default"] is False
    assert payload["exact"] is False
    assert payload["golden"] is False
    assert payload["actual_site_integrated"] is False
    assert payload["production_ready"] is False
    assert payload["asset_byte_fidelity_complete"] is False


# ── Semantic fields used ─────────────────────────────────────────────────
def test_captured_semantics_present_in_output():
    model = _load_model()
    html = mod.render_state(model, "home.desktop.default", route_prefix=_ROUTE_PREFIX)
    for token in ("state_id", "device_class", "captured_at", "final_http_status"):
        assert f"<dt>{token}</dt>" in html
    assert "<header" in html
    assert "<nav" in html
    assert "<main" in html
    assert "<footer" in html


# ── No developer-facing text in output ───────────────────────────────────
def test_no_developer_text_in_output():
    model = _load_model()
    pages = mod.render_site(model, route_prefix=_ROUTE_PREFIX)
    for html in pages.values():
        assert "모델 GNB" not in html, "developer text must be removed"
        assert "참조 복제 후보" not in html, "developer text must be removed"
        assert "참조 복제 표면" not in html, "developer text must be removed"
        assert "모델 복제 표면" not in html, "developer text must be removed"
        assert "Faithful clone candidate" not in html, "developer text must be removed"
        assert "visual review pending" not in html, "developer text must be removed"


# ── Org/staff are visual-input gaps ──────────────────────────────────────
def test_org_staff_are_visual_input_gaps():
    model = _load_model()
    org = mod.render_state(model, "organization.chart.desktop", route_prefix=_ROUTE_PREFIX)
    staff = mod.render_state(model, "staff.directory.desktop", route_prefix=_ROUTE_PREFIX)
    # No fake metadata counts.
    assert "캡처된 컨트롤 수" not in org
    assert "캡처된 컨트롤 수" not in staff
    assert "랜드마크 수" not in org
    assert "랜드마크 수" not in staff
    # Visual-input gap message present.
    assert "visual-input gap" in org
    assert "visual-input gap" in staff


# ── Second synthetic site: same generic renderer ────────────────────────
def _make_state(state_id, title, **over):
    family, _dev, content = mod.parse_state_id(state_id)
    state = {
        "state_id": state_id,
        "device_class": "mobile" if "mobile" in state_id else "desktop",
        "state_name": content,
        "captured_at": "2026-01-01T00:00:00+09:00",
        "source_updated_at": None,
        "final_http_status": 200,
        "viewport": {"width": 1440, "height": 900},
        "requested_url": "https://example.invalid/",
        "final_url": "https://example.invalid/",
        "result_status": "success",
        "page_title": title,
        "landmarks": [
            {"tag": "header", "id": "header", "text": title, "class_name": ""},
            {"tag": "nav", "id": "gnb1", "text": "Menu A Menu B", "class_name": ""},
            {"tag": "nav", "id": "gnb2", "text": "전체메뉴", "class_name": ""},
            {"tag": "main", "id": "main", "text": f"{family} main content", "class_name": ""},
        ],
        "controls": [{"tag": "a", "text": "Menu A", "id": None, "class_name": ""}],
        "general_links": [],
        "viewport_geometry": {"width": 1440, "height": 900},
        "document_geometry": {"viewport": {"width": 1440, "height": 900}},
        "list_no": None,
        "download_references": [],
        "attachment_document_extensions": [],
        "public_assets": [],
        "exceptions": [],
        "artifacts": [],
    }
    state.update(over)
    return state


def _synthetic_model():
    states = [
        _make_state("home.desktop.default", "Northville 홈"),
        _make_state("home.mobile.default", "Northville 홈"),
        _make_state(
            "home.desktop.gnb_open",
            "Northville 홈",
            controls=[
                {"tag": "a", "text": "Menu A", "id": None, "class_name": ""},
                {"tag": "a", "text": "Extra GNB Item", "id": None, "class_name": ""},
            ],
        ),
        _make_state(
            "news.list.desktop",
            "목록 | 소식 | 구정소식 : Northville",
            general_links=[
                {"text": " breaking news item", "href": "/view?list_no=555", "order": 1},
            ],
        ),
        _make_state(
            "news.detail.desktop",
            "Breaking headline | 소식 | 구정소식 : Northville",
            final_url="https://example.invalid/view?list_no=555",
            list_no="555",
            download_references=[{"href": "/dl?list_no=555", "ext": "pdf"}],
            attachment_document_extensions=["pdf"],
        ),
        _make_state(
            "alert.list.desktop",
            "목록 | 알림 | 구정소식 : Northville",
            general_links=[
                {"text": " alert one", "href": "/view?list_no=777", "order": 1},
            ],
        ),
        _make_state(
            "alert.detail.desktop",
            "Alert headline | 알림 | 구정소식 : Northville",
            final_url="https://example.invalid/view?list_no=777",
            list_no="777",
            download_references=[{"href": "/dl?list_no=777", "ext": "hwp"}],
            attachment_document_extensions=["hwp"],
        ),
        _make_state("permit.list.desktop", "목록 | 허가 | 민원 : Northville"),
        _make_state("permit.detail.desktop", "Permit title | 허가 | 민원 : Northville", list_no="888"),
        _make_state("org.chart.desktop", "조직도 | 청사안내 | 소개 : Northville"),
        _make_state("people.directory.desktop", "직원안내 | 청사안내 | 소개 : Northville"),
    ]
    return {
        "schema_version": 1,
        "model_kind": "reference_clone_model",
        "site_id": "northville",
        "capture_id": "20260101T000000-0900",
        "claim_gates": {
            "reference_baseline_ready": True,
            "reference_semantic_model_ready": True,
            "faithful_clone_candidate": False,
        },
        "states": states,
    }


def test_second_synthetic_site_renders_generically():
    synthetic = _synthetic_model()
    prefix = "/x/"
    assert mod.route_for_state("news.list.desktop", prefix) == "/x/news/"
    assert mod.route_for_state("news.detail.desktop", prefix) == "/x/news/detail/"
    assert mod.route_for_state("org.chart.desktop", prefix) == "/x/org/"

    pages = mod.render_site(synthetic, route_prefix=prefix)
    assert len(pages) == 11
    assert set(pages.keys()) == {
        "/x/",
        "/x/home/mobile/",
        "/x/home/gnb-open/",
        "/x/news/",
        "/x/news/detail/",
        "/x/alert/",
        "/x/alert/detail/",
        "/x/permit/",
        "/x/permit/detail/",
        "/x/org/",
        "/x/people/",
    }
    assert "소식" in pages["/x/news/"]
    for html in pages.values():
        assert "http://" not in html
        assert "https://" not in html
        assert "screenshot" not in html.lower()
    assert 'class="rc-list-link" data-detail="1"' in pages["/x/news/"]


def test_second_synthetic_site_unready_fails_closed():
    synthetic = _synthetic_model()
    synthetic["claim_gates"]["reference_baseline_ready"] = False
    with pytest.raises(mod.ReferenceCloneRendererError):
        mod.render_site(synthetic, route_prefix="/x/")