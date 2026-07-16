"""#1170: home lower contracts — fixture regions replace #868 synthetic lower home."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
JS = (STATIC / "citizen-action-demo-canvas.js").read_text(encoding="utf-8")
CSS = (STATIC / "citizen-action-demo-canvas.css").read_text(encoding="utf-8")
FIXTURE_JS = (STATIC / "bukgu-home-clone-fixture.js").read_text(encoding="utf-8")


def test_lower_home_no_longer_uses_synthetic_card_assets_in_home_renderer():
    start = JS.index("  function _renderHome(")
    end = JS.index(
        "  // -----------------------------------------------------------------------\n  // _renderCivilService",
        start,
    )
    home = JS[start:end]
    for asset in [
        "home-lower-hometown-donation.png",
        "home-lower-field-sketch.png",
        "home-lower-card-news.png",
        "home-lower-notifier.png",
    ]:
        assert asset not in home
    assert "CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png" not in home


def test_fixture_includes_footer_and_related_site_regions():
    assert "footer_identity_contact" in FIXTURE_JS
    assert "related_site_controls" in FIXTURE_JS
    assert "notice_news" in FIXTURE_JS
    # exact fixture texts that replace synthetic lower labels
    assert "누리집 이용안내" in FIXTURE_JS or "누리집이용안내" in FIXTURE_JS
    assert "개인정보처리방침" in FIXTURE_JS
    assert "대형폐기물" in FIXTURE_JS


def test_home_fixture_css_scoped_and_no_page_capture():
    assert ".bg-page--home .bg-home-fixture-region--footer_identity_contact" in CSS
    assert ".bg-page--home .bg-home-fixture-region--related_site_controls" in CSS or (
        ".bg-page--home .bg-home-fixture-region" in CSS
    )
    assert "CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png" not in CSS
