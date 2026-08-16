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

import importlib
import json
import re
import socket
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_src_on_path() -> None:
    if str(REPO_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "src"))


def _load_module():
    _ensure_src_on_path()
    return importlib.import_module("official_clone.reference_clone_renderer")


def _load_validator():
    _ensure_src_on_path()
    return importlib.import_module("official_clone.visual_contract")


mod = _load_module()
validator = _load_validator()

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
    # #1312 source-backed attachment: the captured file name and the inert
    # download/preview affordances are rendered (never the raw record id).
    assert "[공고문] 사회연대경제 청년일경험사업 참여청년 모집 공고(3차).hwpx" in detail
    assert 'data-attachment-ext="hwpx"' in detail
    assert "다운로드" in detail
    assert "미리보기" in detail
    assert 'data-attachment-ext="hwpx"' not in listing


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
    assert "rc-list-link" not in gosi_list  # no list row matches the captured gosi detail record_id
    # #1312 source-backed attachment (the captured file name), not a guessed
    # extension chip: the single 고시 attachment is a .hwpx file.
    assert "지속가능관광지방정부협의회 규약 고시.hwpx" in gosi_detail
    assert 'data-attachment-ext="hwpx"' in gosi_detail
    assert "다운로드" in gosi_detail
    assert "disabled" in gosi_detail
    assert "고시합니다" in gosi_detail  # #1312 recovered full 고시 body text


def test_civil_form_detail_captures_hwp_attachment():
    model = _load_model()
    detail = mod.render_state(model, "civil_form.detail.desktop", route_prefix=_ROUTE_PREFIX)
    assert "list_no=143010" not in detail
    assert "list_no=" not in detail
    assert "자동차 등록 위임장" in detail
    # #1312 source-backed attachment (captured file name), inert download.
    assert "자동차등록 위임장.hwp" in detail
    assert 'data-attachment-ext="hwp"' in detail
    assert "다운로드" in detail
    assert "disabled" in detail


# ── Record-ID backed list→detail matching (regression) ──────────────────
def test_notice_list_linked_row_count_and_record_id():
    model = _load_model()
    listing = mod.render_state(model, "notice.list.desktop", route_prefix=_ROUTE_PREFIX)
    links = re.findall(r'data-detail="1"', listing)
    assert len(links) == 1, f"notice list should have exactly 1 linked row (record_id matching detail), got {len(links)}"
    # Verify the linked row's text matches the detail title.
    assert '[공고문]사회연대경제 청년 일경험 시범사업 모집공고_참여청년(3차 모집)' in listing
    # Verify the href targets the notice detail route.
    hrefs = re.findall(r'href="([^"]*)"', listing)
    detail_hrefs = [h for h in hrefs if h != '.' and not h.startswith('#')]
    assert any('detail/' in h for h in detail_hrefs)


def test_gosi_list_has_no_linked_rows():
    model = _load_model()
    listing = mod.render_state(model, "gosi.list.desktop", route_prefix=_ROUTE_PREFIX)
    links = re.findall(r'data-detail="1"', listing)
    assert len(links) == 0, (
        f"gosi list must have 0 linked rows (no list-row record_id matches "
        f"the captured detail record_id not_ancmt_mgt_no=55667), got {len(links)}"
    )


def test_civil_form_list_linked_row_count_and_record_id():
    model = _load_model()
    listing = mod.render_state(model, "civil_form.list.desktop", route_prefix=_ROUTE_PREFIX)
    links = re.findall(r'data-detail="1"', listing)
    assert len(links) == 1, f"civil_form list should have exactly 1 linked row, got {len(links)}"
    # Verify the linked row's text matches the detail title.
    assert '자동차 등록 위임장' in listing
    hrefs = re.findall(r'href="([^"]*)"', listing)
    assert any('detail/' in h for h in hrefs)


def test_synthetic_news_list_linked_row_count():
    model = _synthetic_model()
    contract = _validated_synthetic_contract()
    listing = mod.render_state(model, "news.list.desktop", route_prefix="/x/", visual_contract=contract)
    links = re.findall(r'data-detail="1"', listing)
    assert len(links) == 1, f"synthetic news list should have exactly 1 linked row (list_no=555 matches detail), got {len(links)}"
    assert 'breaking news item' in listing


def test_synthetic_alert_list_linked_row_count():
    model = _synthetic_model()
    contract = _validated_synthetic_contract()
    listing = mod.render_state(model, "alert.list.desktop", route_prefix="/x/", visual_contract=contract)
    links = re.findall(r'data-detail="1"', listing)
    assert len(links) == 1, f"synthetic alert list should have exactly 1 linked row (list_no=777 matches detail), got {len(links)}"
    assert 'alert one' in listing


def test_synthetic_permit_list_no_detail_record_id_no_linked_rows():
    model = _synthetic_model()
    contract = _validated_synthetic_contract()
    listing = mod.render_state(model, "permit.list.desktop", route_prefix="/x/", visual_contract=contract)
    links = re.findall(r'data-detail="1"', listing)
    assert len(links) == 0, (
        f"synthetic permit list must have 0 linked rows "
        f"(no general_links in list state), got {len(links)}"
    )


def test_board_list_rows_without_detail_record_id_are_inert():
    model = _load_model()
    for sid in ("notice.list.desktop", "gosi.list.desktop", "civil_form.list.desktop"):
        h = mod.render_state(model, sid, route_prefix=_ROUTE_PREFIX)
        # Non-linked rows must be inert spans, not navigable anchors.
        inert_spans = re.findall(
            r'<span class="rc-list-item" aria-disabled="true" role="link" tabindex="-1">(.*?)</span></td>',
            h,
        )
        total_links = h.count('data-detail="1"')
        total_rows = h.count('<tr class="rc-board-row">')
        assert total_links + len(inert_spans) == total_rows, (
            f"{sid}: linked rows ({total_links}) + inert spans ({len(inert_spans)}) "
            f"must equal total rows ({total_rows})"
        )


def test_board_list_no_detail_state_fails_closed_zero_links():
    model = _load_model()
    # Remove the detail state for civil_form.
    model["states"] = [
        s for s in model["states"]
        if s.get("state_id") != "civil_form.detail.desktop"
    ]
    h = mod.render_state(model, "civil_form.list.desktop", route_prefix=_ROUTE_PREFIX)
    links = re.findall(r'data-detail="1"', h)
    assert len(links) == 0, "no detail state -> zero linked rows (fail-closed)"


def test_board_list_mismatched_detail_record_id_fails_closed_zero_links():
    model = _load_model()
    # Corrupt the detail final_url so its record_id cannot match any list row.
    for s in model["states"]:
        if s.get("state_id") == "notice.detail.desktop":
            s["final_url"] = "https://example.invalid/view?list_no=99999999"
            break
    h = mod.render_state(model, "notice.list.desktop", route_prefix=_ROUTE_PREFIX)
    links = re.findall(r'data-detail="1"', h)
    assert len(links) == 0, "non-matching detail record_id -> zero linked rows (fail-closed)"


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
    assert "background:#ffffff" in html
    assert "background:#1663b6" in html  # primary action blue measured
    assert "background:#f0f0ff" in html  # hero background measured
    assert "min-height:274px" in html    # semantic header height measured
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


# ── #1325 generic organization / staff_directory rendering ──────────────────
def test_org_renders_nested_semantic_dom():
    model = _load_model()
    html = mod.render_state(model, "organization.chart.desktop", route_prefix=_ROUTE_PREFIX)
    # Nested semantic org DOM (not a flat text list).
    assert 'class="rc-org-tree' in html
    assert "rc-org-children" in html
    assert "rc-org-depth-3" in html
    assert "rc-org-depth-2" in html
    # Captured hierarchy labels visible.
    assert "구청장" in html
    assert "부구청장" in html
    assert "기획실" in html
    assert "의회사무국" in html
    assert "행정복지센터" in html
    # Separate organization sections preserved as labelled regions.
    assert "rc-org-section" in html
    # No live links: node target identity is provenance only, not navigated.
    assert "tel:" not in html
    assert "organizationView.es" not in html


def test_staff_renders_search_and_table_dom():
    model = _load_model()
    html = mod.render_state(model, "staff.directory.desktop", route_prefix=_ROUTE_PREFIX)
    # Search controls + table + count + pager all present.
    assert "rc-staff-search" in html
    assert "rc-staff-select" in html
    assert "rc-staff-input" in html
    assert "rc-staff-table" in html
    assert "전체 1,322건" in html
    assert "현재 페이지 1/133" in html
    for col in ("부서명", "직책", "전화번호", "담당업무"):
        assert col in html
    # Captured rows (verbatim) rendered; phone as inert text, not a tel: link.
    assert "062-360-7201" in html
    assert "tel:" not in html
    # Department options captured verbatim.
    assert "구청장" in html and "양동" in html


def test_no_screenshot_runtime_org_staff():
    model = _load_model()
    for sid in ("organization.chart.desktop", "staff.directory.desktop"):
        html = mod.render_state(model, sid, route_prefix=_ROUTE_PREFIX)
        # No <img> screenshot consumption; evidence stays hidden JSON.
        assert "<img" not in html or "source.png" not in html
        assert 'id="rc-evidence"' in html


def test_no_active_external_post_org_staff():
    model = _load_model()
    for sid in ("organization.chart.desktop", "staff.directory.desktop"):
        html = mod.render_state(model, sid, route_prefix=_ROUTE_PREFIX)
        # No active action to the official endpoint (no POST, no external URL).
        assert 'action="/organization.es' not in html
        assert 'action="http' not in html
        assert "organizationView.es" not in html
        if sid == "staff.directory.desktop":
            # The staff search form is rendered inert: onsubmit aborts submission.
            assert 'onsubmit="return false"' in html
            # Search affordances are inert (disabled) controls.
            assert html.count('aria-disabled="true"') >= 1


def test_lifecycle_fail_closed_org_staff():
    """Org/staff surfaces inherit the G3 fail-closed lifecycle (not promoted)."""
    model = _load_model()
    for sid in ("organization.chart.desktop", "staff.directory.desktop"):
        html = mod.render_state(model, sid, route_prefix=_ROUTE_PREFIX)
        assert 'id="rc-lifecycle"' in html
        start = html.index('id="rc-lifecycle"')
        end = html.index("</script>", start)
        payload = json.loads(html[start:end].split(">", 1)[1])
        assert payload["faithful_clone_candidate"] is False
        assert payload["visual_review"] == "pending"
        assert payload["clone_mvp_ready"] is False
        assert payload["golden"] is False
        assert payload["actual_site_integrated"] is False
        assert payload["asset_byte_fidelity_complete"] is False


# ── #1325 correction: generic page-title rule + page-head/breadcrumb order ──
_BOARD_TITLE_REGRESSION = {
    "notice.list.desktop": "공지사항",
    "notice.detail.desktop": "공지사항",
    "gosi.list.desktop": "현재 고시/공고",
    "gosi.detail.desktop": "고시/공고",
    "civil_form.list.desktop": "민원서식",
    "civil_form.detail.desktop": "민원서식",
}


def _page_title_h2(html: str) -> str:
    m = re.search(r'<h2 class="rc-page-title">([^<]+)</h2>', html)
    assert m, "missing rc-page-title h2"
    return m.group(1)


def test_org_page_title_is_surface_identity():
    model = _load_model()
    html = mod.render_state(model, "organization.chart.desktop", route_prefix=_ROUTE_PREFIX)
    assert _page_title_h2(html) == "행정조직도"


def test_staff_page_title_is_surface_identity():
    model = _load_model()
    html = mod.render_state(model, "staff.directory.desktop", route_prefix=_ROUTE_PREFIX)
    assert _page_title_h2(html) == "직원 업무안내"


def test_board_surface_titles_unchanged():
    """Regression: board list/detail page titles keep the breadcrumb rule."""
    model = _load_model()
    for sid, expected in _BOARD_TITLE_REGRESSION.items():
        html = mod.render_state(model, sid, route_prefix=_ROUTE_PREFIX)
        assert _page_title_h2(html) == expected, f"{sid} title changed"


def test_synthetic_chart_directory_first_segment_title():
    """Generic rule: chart/directory surfaces use the first page_title segment."""
    model = _synthetic_model()
    for sid, expected in (
        ("org.chart.desktop", "조직도"),
        ("people.directory.desktop", "직원안내"),
    ):
        html = mod.render_state(model, sid, route_prefix="/x/")
        assert _page_title_h2(html) == expected


def test_page_head_precedes_breadcrumb_org_staff():
    """SOURCE ordering: page title, then breadcrumb/location, then content."""
    model = _load_model()
    for sid in ("organization.chart.desktop", "staff.directory.desktop"):
        html = mod.render_state(model, sid, route_prefix=_ROUTE_PREFIX)
        body = html[html.index("<body"):]
        assert body.index('class="rc-page-head"') < body.index(
            'class="rc-subpage-context"'
        ), f"{sid}: page title must precede breadcrumb context"


# ── #1325 correction: organization chart layout (not a serialized list) ────
def test_org_desktop_not_narrow_serialized_vertical_list():
    """Org layout vocabulary: executive chain + peer group grid + flat grid."""
    model = _load_model()
    html = mod.render_state(model, "organization.chart.desktop", route_prefix=_ROUTE_PREFIX)
    assert 'class="rc-org-exec"' in html
    assert 'class="rc-org-groups"' in html
    assert 'class="rc-org-flat"' in html
    # The old margin-indented nested serialization is removed.
    assert "margin:0 0 0 24px" not in html
    # Executive labels are still source-backed.
    for text in ("구청장", "부구청장", "기획실", "홍보실", "감사담당관"):
        assert text in html


def test_org_flat_grid_contains_eighteen_centres():
    model = _load_model()
    html = mod.render_state(model, "organization.chart.desktop", route_prefix=_ROUTE_PREFIX)
    flat = re.search(r'<div class="rc-org-flat">(.*?)</div>', html, re.S)
    assert flat, "org flat grid missing"
    boxes = re.findall(r'class="rc-org-label rc-org-box">([^<]+)</span>', flat.group(1))
    assert len(boxes) == 18, f"expected 18 neighbourhood centres, got {len(boxes)}"


# ── #1325 correction: staff directory bounded polish ──────────────────────
def test_staff_table_four_columns_ten_rows():
    model = _load_model()
    html = mod.render_state(model, "staff.directory.desktop", route_prefix=_ROUTE_PREFIX)
    ths = re.findall(
        r'<th scope="col" class="rc-th rc-col-[^"]*">([^<]+)</th>', html
    )
    assert ths == ["부서명", "직책", "전화번호", "담당업무"]
    rows = re.findall(r'<tr class="rc-board-row">', html)
    assert len(rows) == 10, f"expected 10 captured rows, got {len(rows)}"


def test_staff_search_row_summary_and_controls():
    model = _load_model()
    html = mod.render_state(model, "staff.directory.desktop", route_prefix=_ROUTE_PREFIX)
    row_start = html.index('class="rc-staff-search-row"')
    summary_idx = html.index('class="rc-board-summary"')
    form_idx = html.index('form class="rc-staff-search"', row_start)
    assert row_start < summary_idx < form_idx, "summary and controls must share the search row"
    # Readable disabled affordance (white surface, dark text, dark button).
    assert "background:#ffffff;color:#222222;opacity:1" in html
    assert "background:#23201f;color:#ffffff" in html


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


# ---------------------------------------------------------------------------
# Home source-hierarchy / fidelity correction (#1310)
# ---------------------------------------------------------------------------
def _between(html: str, start_token: str, end_token: str) -> str:
    start = html.index(start_token)
    end = html.index(end_token, start)
    return html[start:end]


def test_home_desktop_has_source_ordered_sections():
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    required = (
        "rc-gov-notice",
        "rc-utility-bar",
        "rc-brand-tools",
        "rc-identity-row",
        "rc-section01",
        "rc-mayor-panel",
        "rc-key-visual",
        "rc-primary-slider-controls",
        "rc-section02",
        "rc-quick-carousel-controls",
        "rc-quick-items",
        "rc-section03",
        "rc-notice-panel",
        "rc-story-panel",
        "rc-section04",
        "rc-footer-identity",
    )
    for token in required:
        assert token in html
    assert html.index("rc-section01") < html.index("rc-section02")
    assert html.index("rc-section02") < html.index("rc-section03")
    assert html.index("rc-section03") < html.index("rc-section04")
    # Generic surface-navigation cards are QA-only and no longer pollute home.
    assert '<div class="rc-surface-grid">' not in html


def test_home_primary_and_quick_sliders_are_separate():
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    primary = _between(html, '<div class="rc-primary-slider-controls">', "</div>")
    quick = _between(html, '<div class="rc-quick-carousel">', "</section>")
    assert 'class="prev"' in primary
    assert 'class="pause"' in primary
    assert 'class="next"' in primary
    assert "btn prev" not in primary
    assert "btn next" not in primary
    assert "btn prev" in quick
    assert "btn next" in quick


def test_home_section01_preserves_captured_mayor_actions():
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    section01 = _between(html, 'class="rc-home-section rc-section01"', "</section>")
    assert "내곁에 구청장실" in section01
    assert "매니페스토 (공약)" in section01
    assert "010-3080-8249" in section01
    assert "조직도" not in section01


def test_home_desktop_contains_width_at_narrow_viewports():
    """#1311: desktop home must not force a horizontal scroll at 390px.

    The browser verifier (verify_seogu_reference_clone_e2e.mjs) asserts
    documentElement.scrollWidth <= innerWidth at 390x844. These renderer
    constraints are what keep the fixed-width key-visual column and the
    nowrap utility / GNB items from overflowing when the desktop layout is
    rendered narrower than its source width. This is a CSS-structure contract
    only; it does NOT replace the browser assertion.
    """
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    # Key-visual grid column must be shrinkable (minmax(0, ...)) rather than a
    # fixed pixel column that overflows below its source width.
    assert "grid-template-columns:minmax(0,calc(100% -" in html
    assert "minmax(0," in html
    # Utility bar and GNB must wrap instead of spilling past the viewport.
    assert ".rc-utility-inner{display:flex" in html and "flex-wrap:wrap" in html
    assert ".rc-utility-left,.rc-utility-right{display:flex;flex-wrap:wrap" in html
    assert ".rc-gnb{gap:8px;flex-wrap:wrap;min-width:0;}" in html


def test_home_quick_menu_keeps_rd_box_in_same_carousel():
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    section02 = _between(html, 'class="rc-home-section rc-section02"', "</section>")
    for text in ("조직도", "민원서식", "대형폐기물", "통합예약서비스",
                 "착한공유", "착한동행", "착한나눔"):
        assert text in section02
    assert "rc-quick-card-featured" in section02
    assert "rc-service-grid" not in html
    assert "rc-service-col" not in html


def test_home_information_groups_match_captured_home_links():
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    assert "공지사항" in html
    assert "서구는 지금" in html
    assert "현장 서케치" in html
    assert html.count("rc-notice-item") == 5
    assert "rc-story-card" in html


def test_home_mobile_uses_mobile_source_order_and_geometry():
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "home.mobile.default", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    assert "min-height:175px" in html
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in html
    assert ".rc-section01 .rc-key-visual{order:1;}" in html
    assert ".rc-section01 .rc-mayor-panel{order:2;}" in html
    assert ".rc-gnb .rc-stub{display:none;}" in html
    assert "rc-mobile-search" in html
    assert "rc-mobile-slogan" in html


def test_home_gnb_open_is_six_group_hierarchy():
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "home.desktop.gnb_open", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    assert 'aria-expanded="true"' in html
    assert html.count('class="rc-mega-group"') == 6
    for heading in ("열린민원", "소통참여", "정보공개", "구정소식", "서구소개", "분야별정보"):
        assert f'aria-label="{heading}"' in html
    assert "민원안내" in html
    assert "공공데이터 개방" in html
    assert "고향사랑기부제" in html



def test_home_gnb_open_uses_source_backed_viewport_overlay_geometry():
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "home.desktop.gnb_open", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    assert 'html[data-content="gnb_open"] #rc-mega-menu{' in html
    assert 'position:static!important;min-height:900px;' in html
    assert 'grid-template-columns:repeat(6,minmax(0,1fr))!important;' in html
    assert 'html[data-content="gnb_open"] .rc-identity-row{display:none!important;}' in html
    assert 'html[data-content="gnb_open"] .rc-section01{display:none!important;}' in html


def test_home_notice_board_contains_board_items():
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "home.desktop.default", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    assert html.count("rc-notice-item") == 5
    assert 'aria-disabled="true"' in html
    assert "2026.08.11" in html


def test_synthetic_home_fails_gracefully_without_source_section_markers():
    synthetic = _synthetic_model()
    html = mod.render_state(synthetic, "home.desktop.default", route_prefix="/x/")
    assert "rc-hero" in html
    assert "rc-site-title" in html
    assert "rc-gnb" in html
    assert "rc-section01" in html
    assert '<section class="rc-home-section rc-section02"' not in html
    assert "http://" not in html
    assert "https://" not in html


def test_validated_contract_maintains_faithful_candidate_true():
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


@pytest.mark.parametrize(
    "field_path",
    (
        "layout.home.hero_height_px",
        "layout.home.quick_columns",
        "layout.gnb_open.panel_height_px",
        "layout.gnb_open.columns",
        "responsive.mobile.header_padding_x",
        "responsive.mobile.home.quick_columns",
    ),
)
def test_home_fidelity_promotion_requires_new_source_backed_fields(field_path):
    """#1310 home promotion fails closed if a new source-backed home field is absent."""
    model = _load_model()
    raw = json.loads(VISUAL_CONTRACT_PATH.read_text(encoding="utf-8"))
    node = raw
    parts = field_path.split(".")
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = None
    raw["measurements"] = [
        item for item in raw["measurements"] if item.get("field") != field_path
    ]
    validated = validator.validate_visual_contract(raw, model)
    assert validated["readiness"]["faithful_ready"] is True
    assert mod.faithful_ready(validated) is False


def test_home_fidelity_required_field_set_covers_desktop_and_mobile_geometry():
    required = set(mod.REQUIRED_HOME_FIDELITY_FIELDS)
    assert {
        "layout.header.search_width_px",
        "layout.home.key_visual_width_px",
        "layout.home.quick_item_width_px",
        "layout.gnb_open.panel_height_px",
        "layout.gnb_open.columns",
        "colors.key_visual_bg",
        "responsive.mobile.footer_height_px",
        "responsive.mobile.home.hero_height_px",
        "responsive.mobile.home.quick_item_width_px",
        "responsive.mobile.home.info_columns",
    } <= required


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


# ---------------------------------------------------------------------------
# #1312 — Seo-gu G3 board fidelity (notice / gosi / civil-form list + detail)
# ---------------------------------------------------------------------------
_BOARD_LIST_STATES = [
    "notice.list.desktop", "gosi.list.desktop", "civil_form.list.desktop",
]
_BOARD_DETAIL_STATES = [
    "notice.detail.desktop", "gosi.detail.desktop", "civil_form.detail.desktop",
]
_BOARD_STATES = _BOARD_LIST_STATES + _BOARD_DETAIL_STATES

_EXPECTED_HEADERS = {
    "notice.list.desktop": ["번호", "제목", "담당부서", "등록일", "첨부파일", "조회수"],
    "gosi.list.desktop": ["번호", "제목", "부서명", "등록일", "조회수"],
    "civil_form.list.desktop": ["번호", "분류", "제목", "담당부서", "등록일", "첨부파일", "조회수"],
}


def _render_board(state_id, contract=None):
    model = _load_model()
    kw = {"route_prefix": _ROUTE_PREFIX}
    if contract is not None:
        kw["visual_contract"] = contract
    return mod.render_state(model, state_id, **kw)


def _board_contents(state_id):
    model = _load_model()
    for s in model["states"]:
        if s.get("state_id") == state_id:
            for lm in s.get("landmarks", []):
                if lm.get("id") == "contents":
                    return lm.get("text") or ""
    return ""


def test_1312_six_states_render_deterministically():
    for sid in _BOARD_STATES:
        a = _render_board(sid)
        b = _render_board(sid)
        assert a.startswith("<!DOCTYPE html>")
        assert a == b


def test_1312_list_and_detail_dom_differ():
    for lst, det in zip(_BOARD_LIST_STATES, _BOARD_DETAIL_STATES):
        L = _render_board(lst)
        D = _render_board(det)
        assert L != D
        assert '<table class="rc-board"' in L
        assert '<table class="rc-board"' not in D
        assert "rc-detail-meta" in D


def test_1312_source_table_rendered_as_semantic_table():
    for sid in _BOARD_LIST_STATES:
        h = _render_board(sid)
        assert '<table class="rc-board"' in h
        assert "<thead>" in h and "<tbody>" in h
        assert "<th " in h and '<tr class="rc-board-row">' in h


def test_1312_header_labels_come_from_model():
    for sid, expected in _EXPECTED_HEADERS.items():
        h = _render_board(sid)
        headers = re.findall(r"<th[^>]*>([^<]+)</th>", h)
        assert headers == expected, (sid, headers)


def test_1312_row_metadata_source_backed_order_and_values():
    h = _render_board("notice.list.desktop")
    assert re.search(r'<td class="rc-td rc-col-번호">([^<]*)</td>', h).group(1) == "10852"
    assert re.search(r'<td class="rc-td rc-col-담당부서">([^<]*)</td>', h).group(1) == "체육관광과"
    assert re.search(r'<td class="rc-td rc-col-등록일">([^<]*)</td>', h).group(1) == "2026/08/11"
    assert re.search(r'<td class="rc-td rc-col-조회수">([^<]*)</td>', h).group(1) == "144"
    h = _render_board("gosi.list.desktop")
    assert re.search(r'<td class="rc-td rc-col-번호">([^<]*)</td>', h).group(1) == "338"
    assert re.search(r'<td class="rc-td rc-col-부서명">([^<]*)</td>', h).group(1) == "동천동"
    assert re.search(r'<td class="rc-td rc-col-등록일">([^<]*)</td>', h).group(1) == "2026-08-12"
    h = _render_board("civil_form.list.desktop")
    assert re.search(r'<td class="rc-td rc-col-번호">([^<]*)</td>', h).group(1) == "1077"
    assert re.search(r'<td class="rc-td rc-col-분류">([^<]*)</td>', h).group(1) == "교통"


def test_1312_board_helpers_recover_metadata_from_model():
    c = _board_contents("notice.list.desktop")
    cols = mod._detect_board_columns(c)
    assert cols == _EXPECTED_HEADERS["notice.list.desktop"]
    rows = mod._parse_board_blob_rows(c, cols)
    assert rows[0]["번호"] == "10852"
    assert rows[0]["담당부서"] == "체육관광과"
    assert rows[0]["등록일"] == "2026/08/11"
    assert rows[0]["조회수"] == "144"


def test_1312_detail_recovers_metadata_body_attachment_back():
    h = _render_board("notice.detail.desktop")
    assert "작성일시" in h and "2026/08/10 09:59" in h
    assert "작성부서" in h and "일자리청년지원과" in h
    assert "조회수" in h and "242" in h
    assert "[공고문] 사회연대경제 청년일경험사업 참여청년 모집 공고(3차).hwpx" in h
    assert 'data-attachment-ext="hwpx"' in h and "미리보기" in h
    assert "rc-back" in h and "rc-back-link" in h and ">목록<" in h
    h = _render_board("gosi.detail.desktop")
    assert "작성일" in h and "2026-08-10" in h
    assert "분류" in h and "고시" in h
    assert "담당자연락처" in h and "고영관/0623507669" in h
    assert "고시합니다" in h  # recovered body
    h = _render_board("civil_form.detail.desktop")
    assert "작성일시" in h and "2026/07/30 11:23" in h
    assert "분류" in h and "교통" in h
    assert "작성부서" in h and "교통행정과" in h
    assert "조회수" in h and "7" in h
    assert "자동차(이륜자동차) 등록 위임장입니다." in h  # recovered body
    assert "자동차등록 위임장.hwp" in h and 'data-attachment-ext="hwp"' in h


def test_1312_attachments_inert_and_readonly():
    for sid in _BOARD_DETAIL_STATES:
        h = _render_board(sid)
        assert "rc-attach" in h
        assert "disabled" in h and "aria-disabled" in h
        idx = h.find("rc-attachments")
        block = h[idx:idx + 1000]
        assert "<a " not in block  # attachments are not navigable links


def test_1312_no_external_requests_and_same_origin_nav():
    for sid in _BOARD_STATES:
        h = _render_board(sid)
        assert "http://" not in h
        assert "https://" not in h
        for href in re.findall(r'href="([^"]*)"', h):
            # Relative (local) and absolute clone-route hrefs are both same-origin.
            assert not href.startswith("http")
            assert (
                href.startswith("/seogu/")
                or not href.startswith("/")
                or href == ""
                or href.startswith("#")
            ), href


def test_1312_no_submit_login_payment_pii():
    for sid in _BOARD_STATES:
        h = _render_board(sid)
        assert "<form" not in h
        assert 'type="password"' not in h
        for tok in ("login", "로그인", "결제", "payment", "카드번호", "주민등록번호"):
            assert tok not in h.lower(), (sid, tok)


def test_1312_subpage_shell_snb_breadcrumb_pagination():
    for sid in _BOARD_LIST_STATES:
        h = _render_board(sid)
        assert "rc-subpage" in h
        assert "rc-snb" in h and "rc-snb-current" in h
        assert "rc-breadcrumb" in h and "홈" in h
        assert "rc-pagination" in h
        assert "전체" in h and "건" in h
        assert "페이지" in h


def test_1312_list_toolbar_inert():
    h = _render_board("notice.list.desktop")
    assert "rc-board-toolbar" in h
    assert '<input type="text" class="rc-search-input"' in h
    idx = h.find('class="rc-search-input"')
    tag = h[idx:h.find(">", idx)]
    assert "disabled" in tag


def test_1312_renderer_source_has_no_site_literals():
    source = MODULE_PATH.read_text(encoding="utf-8")
    for tok in ("서구", "Seogu", "Gwangju", "list_no=", "not_ancmt_mgt_no=",
                "10852", "체육관광과", "2026/08/11"):
        assert tok not in source, f"renderer must not hardcode literal: {tok!r}"


def _visible_breadcrumb(html: str) -> str:
    m = re.search(r'<nav class="rc-breadcrumb"[^>]*>.*?</nav>', html, re.S)
    return m.group(0) if m else ""


def test_1324_visible_breadcrumb_not_from_blind_search_legend():
    # The "분야별정보 > 행정 > 행정소식 > 공지사항" string in the source is a
    # blind (screen-reader-only) search fieldset legend, NOT a location
    # navigation. It must never be promoted into the visible breadcrumb NOR
    # into any navigation landmark of the rendered board page.
    blind_tokens = ("분야별정보", "행정소식", "행정 >", "분야별정보 >")
    for sid in _BOARD_STATES:
        h = _render_board(sid)
        crumb = _visible_breadcrumb(h)
        assert crumb, (sid, "expected a visible rc-breadcrumb nav")
        # Real visible location nav is source-backed and rooted at 홈.
        assert "홈" in crumb, (sid, "visible breadcrumb must preserve 홈 root")
        for tok in blind_tokens:
            assert tok not in crumb, (sid, "blind legend leaked into visible breadcrumb", tok)
        # No invented "›" separator glyph (not source-proven).
        assert "rc-crumb-sep" not in h, (sid, "invented crumb separator must be removed")
        assert "›" not in crumb, (sid, "literal › separator not source-proven")
        # The blind search fieldset legend must not be promoted into a
        # navigation landmark. Check the EXACT source legend string (it is
        # joined by " > " in the source, not rendered as separate menu items):
        # if it were promoted into an rc-location (or any) nav it would appear
        # verbatim. The exact string must be absent from the whole document.
        blind_legend = "분야별정보 > 행정 > 행정소식 > 공지사항"
        assert blind_legend not in h, (
            sid,
            "blind search legend promoted into a navigation landmark",
        )
        # No rc-location navigation element is generated for board states
        # (the CSS rule may still exist, so match the element, not the class
        # token alone).
        assert '<nav class="rc-location"' not in h, (
            sid,
            "blind-legend rc-location nav must not be generated",
        )


def test_1324_new_post_semantic_preserved_no_visible_chip():
    # Source DOM: <i class="xi-new"></i><span class="sr_only">새글</span> + title.
    # The "새글" text must remain as a screen-reader label; the previously
    # fabricated visible bordered "새글" text chip must be gone.
    h = _render_board("notice.list.desktop")
    assert "rc-new-badge" not in h, "bordered visible 새글 chip must be removed"
    assert '<span class="sr_only">새글</span>' in h, "sr-only 새글 label must be preserved"
    assert 'class="xi-new"' in h, "source xi-new element must be present"
    assert "padding:2px 6px" not in h, "arbitrary chip padding must be removed"
    assert "#e74c3c" not in h, "arbitrary chip color must be removed"


def test_1324_attachment_count_preserved_no_bordered_chip():
    # The bordered "첨부 N" chip is not a source treatment. The attachment count
    # semantics must still be preserved; a fake bordered chip is forbidden.
    lst = _render_board("notice.list.desktop")
    assert "rc-attach-indicator" not in lst, "bordered attachment chip must be removed"
    assert "첨부파일 1개" in lst, "attachment count semantics must be preserved"
    assert "data-attachment-ext" not in lst, "list must not expose detail attachment ext"
    det = _render_board("notice.detail.desktop")
    assert "rc-attach" in det, "detail attachment affordance must remain"


def test_1324_pager_uses_source_text_not_invented_glyphs():
    # Source pager uses class="arr first" + "처음", etc. The visible glyph
    # treatment is CSS-driven and not materialized; the literal « ‹ › » glyphs
    # were invented and must not appear in the pager navigation.
    h = _render_board("notice.list.desktop")
    m = re.search(r'<nav class="rc-pagination".*?</nav>', h, re.S)
    assert m, "expected a pager nav"
    pager = m.group(0)
    for glyph in ("«", "‹", "›", "»"):
        assert glyph not in pager, f"invented pager glyph {glyph!r} must be removed"
    for label in ("처음", "이전", "다음", "마지막"):
        assert label in pager, f"source pager label {label!r} must be preserved"


def test_1312_synthetic_site_board_fallback_intact():
    # Generic / Buk-gu golden: the synthetic northville model must still render
    # its news/alert lists via the generic fallback (<ul>), proving board
    # detection is model-driven and does not regress other sites.
    synthetic = _synthetic_model()
    contract = _validated_synthetic_contract()
    news = mod.render_state(synthetic, "news.list.desktop", route_prefix="/x/", visual_contract=contract)
    assert "rc-list-link" in news
    assert '<table class="rc-board"' not in news
    detail = mod.render_state(synthetic, "news.detail.desktop", route_prefix="/x/", visual_contract=contract)
    assert "rc-detail-meta" in detail
    assert "rc-back" in detail


# ---------------------------------------------------------------------------
# #1325 organization hero footprint — source-backed optional reserved space
# ---------------------------------------------------------------------------
def test_org_hero_footprint_reserved_when_present():
    """With the validated org hero footprint in the contract, the org surface
    reserves an inert spacer before the leading executive hierarchy."""
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "organization.chart.desktop", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    measured = contract["layout"]["organization"]["hero_footprint_height_px"]
    assert isinstance(measured, int) and measured > 0
    assert 'class="rc-org-hero-footprint"' in html
    assert f".rc-org-hero-footprint{{display:block;height:{measured}px;}}" in html
    assert html.count('class="rc-org-hero-footprint"') == 1
    # spacer sits directly after the first section heading / before exec chain
    assert html.index('class="rc-org-hero-footprint"') > html.index("서구 행정조직")
    assert html.index('class="rc-org-hero-footprint"') < html.index('class="rc-org-exec"')


def test_org_hero_footprint_is_inert_no_debug_content():
    """The reserved footprint is an empty, aria-hidden semantic spacer — no
    placeholder art, no 'image unavailable' text, no emoji, no debug message."""
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "organization.chart.desktop", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    m = re.search(r'<div class="rc-org-hero-footprint"([^>]*)>', html)
    assert m is not None
    assert "aria-hidden" in m.group(1)
    tail = html[m.end():m.end() + 60]
    assert tail.lstrip().startswith("<")  # no inline text content


def test_org_hero_footprint_absent_no_space_invented():
    """A contract without the optional org field (or no contract at all) must
    not inject any gap or CSS rule."""
    model = _load_model()
    raw = json.loads(VISUAL_CONTRACT_PATH.read_text(encoding="utf-8"))
    raw.get("layout", {}).pop("organization", None)
    raw["measurements"] = [
        m for m in raw["measurements"]
        if m["field"] != "layout.organization.hero_footprint_height_px"
    ]
    stripped = validator.validate_visual_contract(raw, model)
    html = mod.render_state(
        model, "organization.chart.desktop", route_prefix=_ROUTE_PREFIX,
        visual_contract=stripped,
    )
    assert 'class="rc-org-hero-footprint"' not in html
    assert ".rc-org-hero-footprint{" not in html
    html0 = mod.render_state(
        model, "organization.chart.desktop", route_prefix=_ROUTE_PREFIX
    )
    assert 'class="rc-org-hero-footprint"' not in html0
    assert ".rc-org-hero-footprint{" not in html0


def test_org_hero_footprint_preserves_org_topology():
    """The existing organization hierarchy topology/tiering must be preserved
    when the spacer is present."""
    model = _load_model()
    contract = _load_validated_contract()
    html = mod.render_state(
        model, "organization.chart.desktop", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    assert 'class="rc-org-exec"' in html
    assert "rc-org-exec-chain" in html
    assert "rc-org-depth-1" in html
    assert 'class="rc-org-groups"' in html
    assert "rc-org-flat" in html


def test_org_hero_footprint_no_site_literal():
    """The org hero footprint implementation is generic — no site literal and
    no site_id branch."""
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "hero_footprint" in source
    for literal in ("seogu_gwangju", "site_id ==", "== \"seogu", "== 'seogu"):
        assert literal not in source


def test_staff_unchanged_by_org_hero_footprint():
    """Staff output must not carry any org hero footprint spacer or rule."""
    model = _load_model()
    contract = _load_validated_contract()
    staff = mod.render_state(
        model, "staff.directory.desktop", route_prefix=_ROUTE_PREFIX,
        visual_contract=contract,
    )
    assert 'class="rc-org-hero-footprint"' not in staff
    assert ".rc-org-hero-footprint{" not in staff
    # staff table + inert search controls remain intact
    assert "rc-staff-table" in staff
    assert "rc-staff-input" in staff
