"""Contract checks for the #868 current Buk-gu lower-home structure."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
JS = (STATIC / "citizen-action-demo-canvas.js").read_text(encoding="utf-8")
CSS = (STATIC / "citizen-action-demo-canvas.css").read_text(encoding="utf-8")


def _home_block() -> str:
    start = JS.index("  function _renderHome(")
    end = JS.index("  // -----------------------------------------------------------------------\n  // _renderCivilService", start)
    return JS[start:end]


def test_lower_home_uses_only_the_four_approved_card_assets():
    home = _home_block()
    assets = [
        "home-lower-hometown-donation.png",
        "home-lower-field-sketch.png",
        "home-lower-card-news.png",
        "home-lower-notifier.png",
    ]
    for asset in assets:
        assert asset in home
        assert (STATIC / "images" / "bukgu-current" / asset).is_file()
    assert "CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png" not in home


def test_lower_home_has_semantic_cards_field_info_partner_row_and_footer():
    home = _home_block()
    for class_name in [
        "bg-home-lower-cards",
        "bg-home-field-info",
        "bg-home-field-info__links",
        "bg-home-partners",
        "bg-home-footer",
    ]:
        assert class_name in home
    for label in [
        "고향사랑기부제",
        "현장스케치",
        "카드뉴스",
        "알리미",
        "분야별 정보",
        "행정조직도",
        "온라인 민원발급(정부24)",
        "배너모음",
        "대형폐기물 처리",
        "취업지원프로그램안내",
        "누리집이용안내",
        "개인정보처리방침",
        "저작권 보호정책",
        "이메일무단수집거부",
        "영상정보처리기기 운영·관리방침",
    ]:
        assert label in home

    for old_label in [
        "대형 폐기물 처리",
        "취업알프로그램안내",
        "부서안내",
        "통합행정복지센터",
        "유관기관",
    ]:
        assert old_label not in home


def test_lower_home_css_is_scoped_and_does_not_promote_a_page_capture():
    assert "/* #868 current Buk-gu home lower */" in CSS
    for selector in [
        "bg-home-lower-cards",
        "bg-home-field-info",
        "bg-home-partners",
        "bg-home-footer",
    ]:
        assert f".bg-page--home .{selector}" in CSS
    assert "CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png" not in CSS
