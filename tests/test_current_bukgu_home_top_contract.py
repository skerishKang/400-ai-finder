"""Contract checks for the #868 current Buk-gu home top viewport."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
JS = (STATIC / "citizen-action-demo-canvas.js").read_text(encoding="utf-8")
CSS = (STATIC / "citizen-action-demo-canvas.css").read_text(encoding="utf-8")


def _home_block() -> str:
    start = JS.index("  function _renderHome() {")
    end = JS.index("  // -----------------------------------------------------------------------\n  // _renderCivilService", start)
    return JS[start:end]


def test_current_home_uses_approved_identity_and_exact_gnb_order():
    home = _home_block()
    assert 'alt="전남광주통합특별시북구"' in home
    assert 'data-action-target="nav-civil-service">종합민원' in home
    expected = ["종합민원", "소통광장", "더불어복지", "분야별정보", "정보공개", "북구소개"]
    offsets = [home.index(label) for label in expected]
    assert offsets == sorted(offsets)


def test_current_home_top_uses_only_approved_derived_assets():
    home = _home_block()
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
        assert asset in home
        assert (STATIC / "images" / "bukgu-current" / asset).is_file()
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
