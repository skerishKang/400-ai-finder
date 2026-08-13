"""Offline contracts for the #1303 G2-B generic faithful-clone renderer.

The renderer consumes ONLY the G2-A semantic ``clone-model.json`` and the
VALIDATED ``visual-contract.json``. These tests prove:

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
  * lifecycle markers are correct (hidden JSON-LD only), and
    ``faithful_clone_candidate`` is False without a validated visual contract
    and True only with a validated, measured contract;
  * resident-visible output carries no developer/debug metadata (no site_id=,
    capture_id=, state_id=, captured_at, HTTP status, visual-input gap,
    표면, or guessed theme tokens);
  * CSS values are derived from the visual contract (no hand-authored
    colors/radii/breakpoints);
  * a second synthetic site model renders with the SAME generic renderer and
    a DIFFERENT synthetic visual contract.

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
VALIDATOR_PATH = REPO_ROOT / "src" / "official_clone" / "visual_contract.py"
FIXTURE_PATH = (
    REPO_ROOT
    / "data"
    / "official_clone_fixtures"
    / "seogu_gwangju"
    / "g1"
    / "20260812T231018-0900"
    / "clone-model.json"
)
VISUAL_CONTRACT_PATH = (
    REPO_ROOT
    / "data"
    / "official_clone_visual_inputs"
    / "seogu_gwangju"
    / "g1"
    / "20260812T231018-0900"
    / "visual-contract.json"
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
    sys.path.insert(0, str(REPO_ROOT / "src"))
    spec = importlib.util.spec_from_file_location(
        "official_clone.reference_clone_renderer", MODULE_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_validator():
    sys.path.insert(0, str(REPO_ROOT / "src"))
    spec = importlib.util.spec_from_file_location(
        "official_clone.visual_contract", VALIDATOR_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()
validator = _load_validator()


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


def _load_validated_contract():
    model = _load_model()
    contract = json.loads(VISUAL_CONTRACT_PATH.read_text(encoding="utf-8"))
    return validator.validate_visual_contract(contract, model)


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
    # list_no is an internal identifier, NOT proven resident-visible content:
    # it must stay out of the resident view (hidden evidence only).
    assert "list_no=143106" not in detail
    assert "list_no=" not in detail
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
    assert "list_no=143010" not in detail
    assert "list_no=" not in detail
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
def test_lifecycle_markers_present_and_correct_with_validated_contract():
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
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


def test_null_visual_contract_faithful_clone_candidate_false():
    """G2-B faithful gate: without a validated visual contract the candidate
    flag MUST be False (no faithful claim from unmeasured styling)."""
    model = _load_model()
    html = mod.render_state(model, "home.desktop.default", route_prefix=_ROUTE_PREFIX)
    assert 'id="rc-lifecycle"' in html
    start = html.index('id="rc-lifecycle"')
    end = html.index("</script>", start)
    payload = json.loads(html[start:end].split(">", 1)[1])
    assert payload["faithful_clone_candidate"] is False
    assert payload["visual_review"] == "pending"


def test_pending_visual_contract_faithful_clone_candidate_false():
    """A contract whose required measured fields are null is NOT faithful-ready."""
    model = _load_model()
    contract = json.loads(VISUAL_CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["colors"]["background"] = None
    contract["layout"]["header"]["height_px"] = None
    # Drop the corresponding measurement entries so null accounting is honest.
    contract["measurements"] = [
        m for m in contract.get("measurements", [])
        if m.get("field") not in ("colors.background", "layout.header.height_px")
    ]
    assert validator.faithful_ready(contract) is False
    html = mod.render_state(
        model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    start = html.index('id="rc-lifecycle"')
    end = html.index("</script>", start)
    payload = json.loads(html[start:end].split(">", 1)[1])
    assert payload["faithful_clone_candidate"] is False


# ── Semantic fields used (hidden machine-readable only) ─────────────────
def test_semantics_are_hidden_not_resident_visible():
    """Evidence (state_id, captured_at, HTTP status, ...) must be hidden
    machine-readable JSON only — never resident-visible text."""
    model = _load_model()
    html = mod.render_state(model, "home.desktop.default", route_prefix=_ROUTE_PREFIX)
    assert 'id="rc-evidence"' in html
    # Capture evidence is inside the hidden JSON script.
    start = html.index('id="rc-evidence"')
    end = html.index("</script>", start)
    payload = json.loads(html[start:end].split(">", 1)[1])
    assert payload["state_id"] == "home.desktop.default"
    assert payload["device_class"] == "desktop"
    assert payload["captured_at"]
    assert payload["final_http_status"] == 200
    # Structural landmarks still present.
    assert "<header" in html
    assert "<nav" in html
    assert "<main" in html
    assert "<footer" in html


def test_resident_visible_has_no_debug_diagnostics():
    """No developer/evidence metadata may be visible to residents."""
    model = _load_model()
    contract = _load_validated_contract()
    for state_id in REQUIRED_11:
        html = mod.render_state(
            model, state_id, route_prefix=_ROUTE_PREFIX, visual_contract=contract
        )
        # Visible text must not expose audit/evidence fields.
        for token in (
            "site_id=",
            "capture_id=",
            "captured_at=",
            "source_updated_at=",
            "final_http_status=",
            "visual-input gap",
            "표면",
            "rc-meta",
            "<dt>state_id</dt>",
            "list_no=",
        ):
            assert token not in html, f"resident-visible debug leaked {token!r} in {state_id}"


def test_list_no_kept_in_hidden_evidence_only():
    """Internal identifiers (list_no) stay in hidden QA evidence, never on the
    resident-visible surface."""
    model = _load_model()
    detail = mod.render_state(model, "notice.detail.desktop", route_prefix=_ROUTE_PREFIX)
    assert "list_no=" not in detail
    # The hidden rc-evidence JSON carries the identifier for QA.
    start = detail.index('id="rc-evidence"')
    end = detail.index("</script>", start)
    payload = json.loads(detail[start:end].split(">", 1)[1])
    assert payload["list_no"] == "143106"


def test_non_fidelity_defaults_classified_not_faithful():
    """Renderer presentation defaults are explicitly classified as
    non-fidelity accessibility defaults and do not gate the faithful claim."""
    assert mod.NON_FIDELITY_PRESENTATION_DEFAULTS["font_size"] == "browser-default"
    assert mod.NON_FIDELITY_PRESENTATION_DEFAULTS["border_radius"] is None
    assert mod.NON_FIDELITY_PRESENTATION_DEFAULTS["responsive_breakpoint"] is None
    # faithful_ready depends only on measured contract values, not on defaults.
    model = _load_model()
    contract = _load_validated_contract()
    assert mod.faithful_ready(contract) is True


# ── CSS derived strictly from the validated contract ────────────────────
def test_css_values_derive_from_contract():
    """Every rendered CSS value must come from the validated visual contract
    (max-width 1400px, 1px border, measured colors) — never guessed."""
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "home.desktop.default", route_prefix=_ROUTE_PREFIX, visual_contract=contract
    )
    assert "max-width:1400px" in html
    assert "border:1px solid #dcdcdc" in html
    assert "background:#f8f8f8" in html
    assert "background:#083878" in html  # GNB bg measured
    assert "background:#f0f0f8" in html  # header bg measured
    assert "min-height:692px" in html    # header height measured
    assert "font-family:" in html


def test_forbidden_guessed_css_tokens_absent():
    """The exact hand-authored tokens from the pre-correction renderer must
    never appear in output CSS (colors, radii, max-width, breakpoint)."""
    model = _load_model()
    contract = _load_validated_contract()
    pages = mod.render_site(model, route_prefix=_ROUTE_PREFIX, visual_contract=contract)
    for html in pages.values():
        for token in (
            "#e6e6ea",
            "#8a8a93",
            "#1f6feb",
            "980px",
            "999px",
            "border-radius",
            "max-width:600px",
            "@media (max-width",
            "font-size:.85rem",
            "font-size:1.25rem",
            "font-size:1.4rem",
            "padding:14px 18px",
            "padding:22px 18px 60px",
        ):
            assert token not in html, f"guessed CSS token present: {token!r}"


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
        assert "visual-input gap" not in html, "developer text must be removed"
        assert "표면" not in html, "developer text must be removed"
        assert "캡처 메타데이터" not in html, "developer text must be removed"


# ── Org/staff render without gap diagnostics or fake UI ─────────────────
def test_org_staff_render_label_without_gap_text_or_fake_ui():
    model = _load_model()
    org = mod.render_state(model, "organization.chart.desktop", route_prefix=_ROUTE_PREFIX)
    staff = mod.render_state(model, "staff.directory.desktop", route_prefix=_ROUTE_PREFIX)
    # No fake metadata counts.
    assert "캡처된 컨트롤 수" not in org
    assert "캡처된 컨트롤 수" not in staff
    assert "랜드마크 수" not in org
    assert "랜드마크 수" not in staff
    # Visual-input gap wording must NOT be shown to residents.
    assert "visual-input gap" not in org
    assert "visual-input gap" not in staff
    # The captured surface label is rendered.
    assert "행정조직도" in org
    assert "직원 업무안내" in staff


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
        "document_geometry": {
            "viewport": {"width": 1440, "height": 900},
            "full_page_screenshot": {
                "artifact_id": f"states/{state_id}/source.png",
                "width": 1440,
                "height": 900,
                "sha256": "a" * 64,
            },
        },
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


def _synthetic_visual_contract():
    """A second-site visual contract with DIFFERENT measured values.

    Every required field carries a 1:1 evidence record. Provenance references
    the synthetic state's own committed screenshot SHA (a synthetic sha256 is
    fine for the validator identity check: the checker only verifies the
    referenced screenshot SHA matches the model geometry).

    Mobile measurements (responsive.mobile.*) correctly target the mobile
    provenance state (home.mobile.default), not the desktop default.
    """
    desktop_shot = "a" * 64
    mobile_shot = "a" * 64
    values = {
        "layout.header.height_px": 120,
        "layout.gnb.height_px": 48,
        "layout.main.max_width_px": 1200,
        "layout.footer.height_px": 90,
        "colors.primary": "#123456",
        "colors.background": "#fafafa",
        "colors.header_bg": "#e8e8ec",
        "colors.gnb_bg": "#123456",
        "colors.gnb_text": "#ffffff",
        "colors.footer_bg": "#e8e8ec",
        "colors.text": "#111111",
        "colors.text_muted": "#666666",
        "colors.border": "#cccccc",
        "typography.font_family": "Noto Sans KR",
        "typography.text_color": "#111111",
        "border.width": 2,
        "border.color": "#cccccc",
        "responsive.mobile.header_height_px": 100,
        "responsive.mobile.gnb_height_px": 44,
        "responsive.mobile.max_width_px": 1000,
        "responsive.mobile.main_padding_x": 12,
    }
    measurements = []
    for field, value in values.items():
        if field.endswith("_px") or field.endswith("_padding_x") or field == "border.width":
            unit = "px"
        elif field.startswith("colors.") or field == "border.color" or field == "typography.text_color":
            unit = "hex"
        else:
            unit = None
        is_mobile = field.startswith("responsive.mobile.")
        measurements.append({
            "field": field,
            "value": value,
            "unit": unit,
            "evidence_type": "pixel_analysis",
            "source_state_id": "home.mobile.default" if is_mobile else "home.desktop.default",
            "artifact_sha256": mobile_shot if is_mobile else desktop_shot,
            "method": "pixel_analysis",
        })
    return {
        "schema_version": 2,
        "contract_kind": "visual_input",
        "site_id": "northville",
        "capture_id": "20260101T000000-0900",
        "model_checksum": None,  # filled after model load below
        "layout": {
            "header": {"height_px": 120, "provenance_state_id": "home.desktop.default"},
            "gnb": {"height_px": 48, "provenance_state_id": "home.desktop.default"},
            "main": {"max_width_px": 1200, "padding_x": 32, "provenance_state_id": "home.desktop.default"},
            "footer": {"height_px": 90, "provenance_state_id": "home.desktop.default"},
        },
        "colors": {
            "primary": "#123456",
            "background": "#fafafa",
            "header_bg": "#e8e8ec",
            "gnb_bg": "#123456",
            "gnb_text": "#ffffff",
            "footer_bg": "#e8e8ec",
            "text": "#111111",
            "text_muted": "#666666",
            "border": "#cccccc",
            "provenance_state_id": "home.desktop.default",
        },
        "typography": {
            "font_family": "Noto Sans KR",
            "text_color": "#111111",
            "provenance_state_id": "home.desktop.default",
        },
        "spacing": {
            "provenance_state_id": "home.desktop.default",
        },
        "border": {"width": 2, "color": "#cccccc", "provenance_state_id": "home.desktop.default"},
        "responsive": {
            "mobile": {
                "header_height_px": 100,
                "gnb_height_px": 44,
                "max_width_px": 1000,
                "main_padding_x": 12,
                "provenance_state_id": "home.mobile.default",
            },
            "provenance_state_id": "home.mobile.default",
        },
        "gaps": [],
        "measurements": measurements,
    }


def _validated_synthetic_contract():
    synthetic = _synthetic_model()
    contract = _synthetic_visual_contract()
    contract["model_checksum"] = validator.compute_model_checksum(synthetic)
    return validator.validate_visual_contract(contract, synthetic)


def test_second_synthetic_site_renders_generically():
    synthetic = _synthetic_model()
    contract = _validated_synthetic_contract()
    prefix = "/x/"
    assert mod.route_for_state("news.list.desktop", prefix) == "/x/news/"
    assert mod.route_for_state("news.detail.desktop", prefix) == "/x/news/detail/"
    assert mod.route_for_state("org.chart.desktop", prefix) == "/x/org/"

    pages = mod.render_site(synthetic, route_prefix=prefix, visual_contract=contract)
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


def test_second_synthetic_site_css_derives_from_its_own_contract():
    """A different visual contract must produce a different, contract-derived
    theme (max-width 1200px, 2px border, custom colors) — never the seogu
    measurements or any guessed tokens."""
    synthetic = _synthetic_model()
    contract = _validated_synthetic_contract()
    html = mod.render_state(
        synthetic, "home.desktop.default", route_prefix="/x/", visual_contract=contract
    )
    assert "max-width:1200px" in html
    assert "border:2px solid #cccccc" in html
    assert "background:#fafafa" in html
    assert "background:#123456" in html
    assert "background:#e8e8ec" in html
    for token in ("#083878", "max-width:1400px", "980px", "999px", "600px", "e6e6ea", "8a8a93", "1f6feb"):
        assert token not in html, f"foreign/guessed token leaked into synthetic render: {token}"


def test_second_synthetic_site_unready_fails_closed():
    synthetic = _synthetic_model()
    synthetic["claim_gates"]["reference_baseline_ready"] = False
    with pytest.raises(mod.ReferenceCloneRendererError):
        mod.render_site(synthetic, route_prefix="/x/")


# ---------------------------------------------------------------------------
# Renderer must require validator-produced contract (CTO review 4923964659)
# ---------------------------------------------------------------------------
def test_raw_but_valid_contract_now_accepted_by_renderer():
    """A committed raw (unvalidated) visual-contract.json passed directly to the
    renderer IS now faithfully validated by re-validation at the render entry
    point — the renderer no longer depends on a pre-validated readiness block."""
    model = _load_model()
    raw_contract = json.loads(VISUAL_CONTRACT_PATH.read_text(encoding="utf-8"))
    # The raw contract has no 'readiness' section — only
    # validate_visual_contract() adds it.
    assert "readiness" not in raw_contract
    html = mod.render_state(
        model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
        visual_contract=raw_contract,
    )
    start = html.index('id="rc-lifecycle"')
    end = html.index("</script>", start)
    payload = json.loads(html[start:end].split(">", 1)[1])
    assert payload["faithful_clone_candidate"] is True, (
        "raw but valid contract must be accepted by renderer re-validation"
    )


def test_tampered_contract_raises_at_render_entry():
    """A complete contract with a value/evidence mismatch passed directly to
    the renderer must raise VisualContractValidationError (re-validation
    catches the mismatch)."""
    model = _load_model()
    raw_contract = json.loads(VISUAL_CONTRACT_PATH.read_text(encoding="utf-8"))
    raw_contract["layout"]["header"]["height_px"] = 999
    with pytest.raises(validator.VisualContractValidationError, match="field/value mismatch"):
        mod.render_state(
            model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
            visual_contract=raw_contract,
        )


def test_validated_contract_maintains_faithful_candidate_true():
    """The validated visual contract must still produce faithful_clone_candidate
    True after all correction tests pass."""
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    start = html.index('id="rc-lifecycle"')
    end = html.index("</script>", start)
    payload = json.loads(html[start:end].split(">", 1)[1])
    assert payload["faithful_clone_candidate"] is True


# ---------------------------------------------------------------------------
# Renderer trust / readiness spoof prevention (CTO review 4924580210 — correction 2)
# ---------------------------------------------------------------------------
def test_readiness_block_copy_spoof_raises():
    """Raw contract with tampered data + copied valid readiness block must
    NOT produce faithful_clone_candidate=True — re-validation catches the
    underlying data tampering."""
    model = _load_model()
    raw = json.loads(VISUAL_CONTRACT_PATH.read_text(encoding="utf-8"))
    validated = _load_validated_contract()
    raw["readiness"] = validated["readiness"]
    raw["layout"]["header"]["height_px"] = 999
    with pytest.raises(validator.VisualContractValidationError, match="field/value mismatch"):
        mod.render_state(
            model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
            visual_contract=raw,
        )


def test_post_validation_field_mutation_raises():
    """A validated contract whose layout.header.height_px is mutated after
    validation must NOT produce faithful_clone_candidate=True — re-validation
    catches the mutation."""
    model = _load_model()
    contract = _load_validated_contract()
    contract["layout"]["header"]["height_px"] = 999
    with pytest.raises(validator.VisualContractValidationError, match="field/value mismatch"):
        mod.render_state(
            model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
            visual_contract=contract,
        )


def test_post_validation_evidence_mutation_raises():
    """A validated contract whose measurement evidence value or SHA is mutated
    after validation must NOT produce faithful_clone_candidate=True."""
    model = _load_model()
    contract = _load_validated_contract()
    for entry in contract["measurements"]:
        if entry["field"] == "layout.gnb.height_px":
            entry["value"] = 999
    with pytest.raises(validator.VisualContractValidationError, match="field/value mismatch"):
        mod.render_state(
            model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
            visual_contract=contract,
        )


def test_forged_readiness_dict_ignored_by_revalidation():
    """A raw contract with a directly forged readiness.faithful_ready=True
    dict must NOT produce faithful_clone_candidate=True — re-validation
    computes readiness from the actual data, not the forged block."""
    model = _load_model()
    raw = json.loads(VISUAL_CONTRACT_PATH.read_text(encoding="utf-8"))
    raw["readiness"] = {
        "schema_version": 2,
        "required_measured_count": 21,
        "measured_required_count": 21,
        "missing_required": [],
        "measured_value_count": 30,
        "gap_count": 8,
        "faithful_ready": True,
    }
    # Tamper underlying data so forged readiness is the only thing that would
    # make it look faithful.
    raw["layout"]["header"]["height_px"] = 999
    with pytest.raises(validator.VisualContractValidationError, match="field/value mismatch"):
        mod.render_state(
            model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
            visual_contract=raw,
        )
