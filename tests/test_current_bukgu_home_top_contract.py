"""Contract checks for the #868 current Buk-gu home top viewport."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
JS = (STATIC / "citizen-action-demo-canvas.js").read_text(encoding="utf-8")
CSS = (STATIC / "citizen-action-demo-canvas.css").read_text(encoding="utf-8")


def _home_block() -> str:
    start = JS.index("  function _renderHome(")
    # Find end of _renderHome function (next top-level function or utility)
    candidates = ["\n  // -----------------------------------------------------------------------\n  // _renderCivilService",
                  "\n  function _renderCivilService"]
    end = len(JS)
    for c in candidates:
        idx = JS.find(c, start + 50)
        if idx != -1 and idx < end:
            end = idx
    return JS[start:end]


def test_current_home_uses_approved_identity_and_exact_gnb_order():
    home = _home_block()
    assert 'alt="전남광주통합특별시북구"' in home
    assert 'data-action-target="nav-civil-service">종합민원' in home
    expected = ["종합민원", "소통광장", "더불어복지", "분야별정보", "정보공개", "북구소개"]
    offsets = [home.index(label) for label in expected]
    assert offsets == sorted(offsets)

    # Validate quick service order and labels
    expected_quick = [
        "업무검색",
        "청사안내",
        "고향사랑기부제",
        "부끄머니",
        "통합예약",
        "일반민원 대기현황",
    ]
    for label in expected_quick:
        assert label in home
    quick_offsets = [home.index(label) for label in expected_quick]
    assert quick_offsets == sorted(quick_offsets)
    assert "부꾸머니" not in home


def test_current_home_top_uses_only_approved_derived_assets():
    home = _home_block()
    # Default R-HOME-01 asset set
    assets = [
        "home-government-notice.png",
        "home-identity.png",
        "home-civic-brand.png",
        "home-mayor-card.png",
        "home-alert-banner.png",
        "home-quick-work.png",
        "home-quick-office.png",
        "home-quick-donation.png",
        "home-quick-money.png",
        "home-quick-reservation.png",
        "home-quick-waiting.png",
    ]
    for asset in assets:
        assert asset in home, f"default asset {asset} missing from home block"
        assert (STATIC / "images" / "bukgu-current" / asset).is_file(), f"file missing: {asset}"
    # Alternate R-HOME-02 state asset must exist as file (used via ?home-reference=R-HOME-02)
    assert "home-alert-banner-r-home-02.png" in JS, "R-HOME-02 alternate asset not referenced in JS"
    assert (STATIC / "images" / "bukgu-current" / "home-alert-banner-r-home-02.png").is_file(), "R-HOME-02 crop file missing"
    assert "bukgu_home.png" not in home
    assert "bukgu_menu.png" not in home
    assert "bukgu_intake.png" not in home


def test_current_home_has_semantic_top_structure_and_no_legacy_english_utility():
    home = _home_block()
    for class_name in [
        "bg-home-gov-strip",
        "bg-home-utility",
        "bg-home-header",
        "bg-home-gnb",
        "bg-home-search",
        "bg-home-lead",
        "bg-home-quick",
        "bg-home-notice-sites",
    ]:
        assert class_name in home
    for old_label in ["English", "Chinese", "Site Map", "LOGIN", "JOIN"]:
        assert old_label not in home


def test_current_home_css_is_scoped_to_home_root():
    for selector in [
        "bg-home-gov-strip",
        "bg-home-utility",
        "bg-home-header",
        "bg-home-gnb",
        "bg-home-search",
        "bg-home-lead",
        "bg-home-quick",
        "bg-home-notice-sites",
    ]:
        assert f".bg-page--home .{selector}" in CSS
    assert "/* #868 current Buk-gu home top viewport */" in CSS
