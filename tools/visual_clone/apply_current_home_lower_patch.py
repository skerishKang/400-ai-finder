#!/usr/bin/env python3
"""Apply the exact #868 R-HOME-02 lower-home semantic patch.

Offline only. The patch refuses to run unless the audited JS/CSS base blobs and
four approved derived lower-card assets match exactly. It never reads a live
site or writes an image asset.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANVAS_JS = ROOT / "src/web/static/citizen-action-demo-canvas.js"
CANVAS_CSS = ROOT / "src/web/static/citizen-action-demo-canvas.css"
TEST_FILE = ROOT / "tests/test_current_bukgu_home_lower_contract.py"

EXPECTED_JS_BLOB = "3d9c49b6acb0fec257236948a2e32d62c07ccbe7"
EXPECTED_CSS_BLOB = "ab70495dbc2aa31428e0bc01cb23524a7c5ebee2"
MARKER = "/* #868 current Buk-gu home lower */"

ASSETS = {
    "home-lower-hometown-donation.png": "a35d11843bd41d4f8ef39601b40295e0969fe0eefdd05e173c21bb1d7d6315e2",
    "home-lower-field-sketch.png": "51ce2739a0cab763f461129ce82411b7d31409d6e8ebb78d83db8c4b4bc038a1",
    "home-lower-card-news.png": "0261d751f7915b2dda341cbfac957e31a76bd7b5b70208177328f0304bafa437",
    "home-lower-notifier.png": "a9b71d1a0231e5341e796b282caecf809c6925ddca95ef0d1d7ff3c87a1afe51",
}

LOWER_HTML = r'''          '<section class="bg-home-lower" aria-label="하단 소식과 분야별 정보">' +
            '<section class="bg-home-lower-cards" aria-label="주요 소식">' +
              '<article class="bg-home-lower-card bg-home-lower-card--donation">' +
                '<div class="bg-home-lower-card__head"><h2>고향사랑기부제</h2><span aria-hidden="true">‹&nbsp;Ⅱ&nbsp;›&nbsp;+</span></div>' +
                '<img src="' + assets + '/home-lower-hometown-donation.png" alt="고향사랑기부제 안내" />' +
              '</article>' +
              '<article class="bg-home-lower-card bg-home-lower-card--sketch">' +
                '<div class="bg-home-lower-card__head"><h2>현장스케치</h2><span aria-hidden="true">‹&nbsp;<b>1</b> / 4&nbsp;Ⅱ&nbsp;›&nbsp;+</span></div>' +
                '<img src="' + assets + '/home-lower-field-sketch.png" alt="현장스케치" />' +
              '</article>' +
              '<article class="bg-home-lower-card bg-home-lower-card--news">' +
                '<div class="bg-home-lower-card__head"><h2>카드뉴스</h2><span aria-hidden="true">+</span></div>' +
                '<img src="' + assets + '/home-lower-card-news.png" alt="카드뉴스" />' +
              '</article>' +
              '<article class="bg-home-lower-card bg-home-lower-card--notifier">' +
                '<div class="bg-home-lower-card__head"><h2>알리미</h2><span aria-hidden="true">‹&nbsp;<b>1</b> / 4&nbsp;Ⅱ&nbsp;›&nbsp;+</span></div>' +
                '<img src="' + assets + '/home-lower-notifier.png" alt="알리미" />' +
              '</article>' +
            '</section>' +

            '<section class="bg-home-field-info" aria-labelledby="bg-home-field-info-title">' +
              '<div class="bg-home-field-info__head">' +
                '<div><h2 id="bg-home-field-info-title">분야별 정보</h2><p>각 분야별로 자주찾는 메뉴에 빠르게 이동할 수 있습니다.</p></div>' +
                '<nav class="bg-home-field-info__tabs" aria-label="분야 선택">' +
                  '<button type="button" aria-pressed="true"><span aria-hidden="true">☺</span>구민</button>' +
                  '<button type="button" aria-pressed="false"><span aria-hidden="true">▦</span>기업/경제</button>' +
                  '<button type="button" aria-pressed="false"><span aria-hidden="true">♜</span>관광</button>' +
                '</nav>' +
              '</div>' +
              '<div class="bg-home-field-info__links">' +
                '<a href="#">행정조직도 <span aria-hidden="true">›</span></a>' +
                '<a href="#">주정차단속문자알림 <span aria-hidden="true">›</span></a>' +
                '<a href="#">여권 발급 <span aria-hidden="true">›</span></a>' +
                '<a href="#">보건증 발급 <span aria-hidden="true">›</span></a>' +
                '<a href="#">대형 폐기물 처리 <span aria-hidden="true">›</span></a>' +
                '<a href="#">온라인 민원발급(정부24) <span aria-hidden="true">›</span></a>' +
                '<a href="#">취업알프로그램안내 <span aria-hidden="true">›</span></a>' +
                '<a href="#">소화기 사용법 <span aria-hidden="true">›</span></a>' +
                '<a href="#">정보화교육 <span aria-hidden="true">›</span></a>' +
                '<a href="#">공공데이터 <span aria-hidden="true">›</span></a>' +
              '</div>' +
            '</section>' +

            '<section class="bg-home-partners" aria-label="배너 모음">' +
              '<div class="bg-home-partners__head"><h2>배너모음</h2><span aria-hidden="true">‹&nbsp;Ⅱ&nbsp;›&nbsp;+</span></div>' +
              '<div class="bg-home-partners__items">' +
                '<a href="#">농림축산식품부</a>' +
                '<a href="#" class="bg-home-partners__smart">Smart K-Factory</a>' +
                '<a href="#" class="bg-home-partners__pis">PIS <small>행정정보공동이용센터</small></a>' +
                '<a href="#">소비자24</a>' +
                '<a href="#">수유시설</a>' +
              '</div>' +
            '</section>' +
          '</section>' +
'''

FOOTER_HTML = r'''        '<footer class="bg-home-footer" aria-label="사이트 하단">' +
          '<div class="bg-home-footer__inner">' +
            '<nav class="bg-home-footer__nav" aria-label="하단 메뉴">' +
              '<a href="#">부서안내 <span aria-hidden="true">⌃</span></a>' +
              '<a href="#">통합행정복지센터 <span aria-hidden="true">⌃</span></a>' +
              '<a href="#">주요사이트 <span aria-hidden="true">⌃</span></a>' +
              '<a href="#">유관기관 <span aria-hidden="true">⌃</span></a>' +
            '</nav>' +
            '<div class="bg-home-footer__legal"><strong>전남광주통합특별시북구</strong><span>로컬 시연 화면 · 외부 사이트와 연결하지 않습니다.</span></div>' +
          '</div>' +
        '</footer>' +
'''

LOWER_CSS = r'''

/* #868 current Buk-gu home lower */
.bg-page--home .bg-home-lower {
  margin-top: 50px;
  padding-bottom: 28px;
}
.bg-page--home .bg-home-lower-cards {
  display: grid;
  grid-template-columns: 168px 238px 168px minmax(0, 1fr);
  gap: 13px;
}
.bg-page--home .bg-home-lower-card { min-width: 0; }
.bg-page--home .bg-home-lower-card__head {
  height: 32px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 6px;
  color: #121212;
}
.bg-page--home .bg-home-lower-card__head h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -1px;
  white-space: nowrap;
}
.bg-page--home .bg-home-lower-card__head span {
  color: #1f2a32;
  font-size: 11px;
  letter-spacing: -0.25px;
  white-space: nowrap;
}
.bg-page--home .bg-home-lower-card__head b { color: #009d68; }
.bg-page--home .bg-home-lower-card img {
  display: block;
  width: 100%;
  height: 168px;
  border-radius: 6px;
  object-fit: cover;
  background: #f4f4f4;
}

.bg-page--home .bg-home-field-info {
  position: relative;
  margin-top: 71px;
  padding: 0 0 38px;
}
.bg-page--home .bg-home-field-info::before {
  position: absolute;
  inset: 29px -118px 0 345px;
  z-index: 0;
  content: "";
  pointer-events: none;
  opacity: 0.38;
  background:
    linear-gradient(118deg, transparent 0 15%, rgba(198, 213, 216, 0.40) 15.4% 15.8%, transparent 16.2% 100%),
    repeating-linear-gradient(90deg, transparent 0 35px, rgba(199, 214, 218, 0.28) 36px 38px, transparent 39px 72px),
    repeating-linear-gradient(0deg, transparent 0 26px, rgba(199, 214, 218, 0.23) 27px 29px, transparent 30px 54px);
}
.bg-page--home .bg-home-field-info__head,
.bg-page--home .bg-home-field-info__links { position: relative; z-index: 1; }
.bg-page--home .bg-home-field-info__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 20px;
}
.bg-page--home .bg-home-field-info__head h2 {
  margin: 0 0 4px;
  color: #181818;
  font-size: 18px;
  letter-spacing: -1px;
}
.bg-page--home .bg-home-field-info__head p {
  margin: 0;
  color: #747474;
  font-size: 11px;
  letter-spacing: -0.55px;
}
.bg-page--home .bg-home-field-info__tabs {
  display: flex;
  gap: 10px;
}
.bg-page--home .bg-home-field-info__tabs button {
  width: 68px;
  height: 68px;
  border: 0;
  border-radius: 12px;
  color: #666;
  background: rgba(255, 255, 255, 0.75);
  font-size: 11px;
  cursor: default;
}
.bg-page--home .bg-home-field-info__tabs button span {
  display: block;
  margin-bottom: 4px;
  font-size: 18px;
}
.bg-page--home .bg-home-field-info__tabs button[aria-pressed="true"] {
  color: #7d5910;
  background: #ffbf47;
}
.bg-page--home .bg-home-field-info__links {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  margin-top: 35px;
}
.bg-page--home .bg-home-field-info__links a {
  min-width: 0;
  height: 38px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 13px;
  overflow: hidden;
  border: 1px solid #e2e5e6;
  border-radius: 7px;
  color: #646464;
  background: rgba(255, 255, 255, 0.93);
  text-decoration: none;
  font-size: 11px;
  letter-spacing: -0.55px;
  white-space: nowrap;
}
.bg-page--home .bg-home-field-info__links a span { color: #3c3c3c; font-size: 18px; }

.bg-page--home .bg-home-partners {
  display: flex;
  align-items: center;
  gap: 28px;
  min-height: 84px;
  border-top: 1px solid #eceff0;
}
.bg-page--home .bg-home-partners__head {
  min-width: 135px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.bg-page--home .bg-home-partners__head h2 {
  margin: 0;
  color: #232323;
  font-size: 13px;
  letter-spacing: -0.7px;
}
.bg-page--home .bg-home-partners__head span { color: #263039; font-size: 12px; white-space: nowrap; }
.bg-page--home .bg-home-partners__items {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}
.bg-page--home .bg-home-partners__items a {
  color: #6d7376;
  text-decoration: none;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}
.bg-page--home .bg-home-partners__items .bg-home-partners__smart { color: #438fb2; font-size: 17px; }
.bg-page--home .bg-home-partners__items .bg-home-partners__pis { color: #345b91; font-size: 20px; }
.bg-page--home .bg-home-partners__pis small { color: #777; font-size: 9px; font-weight: 500; }

.bg-page--home .bg-home-footer {
  width: 100%;
  color: #f7f9fb;
  background: #33445c;
}
.bg-page--home .bg-home-footer__inner {
  width: min(var(--bg-home-width), calc(100% - 32px));
  margin: 0 auto;
}
.bg-page--home .bg-home-footer__nav {
  min-height: 62px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  border-right: 1px solid rgba(255, 255, 255, 0.16);
}
.bg-page--home .bg-home-footer__nav a {
  min-height: 62px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 19px;
  border-left: 1px solid rgba(255, 255, 255, 0.16);
  color: #fff;
  text-decoration: none;
  font-size: 12px;
  font-weight: 700;
}
.bg-page--home .bg-home-footer__nav span { color: #bdc8d6; }
.bg-page--home .bg-home-footer__legal {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 19px 0 26px;
  color: #d6dee6;
  font-size: 10px;
}
.bg-page--home .bg-home-footer__legal strong { color: #fff; font-size: 12px; }

@media (max-width: 940px) {
  .bg-page--home .bg-home-lower-cards,
  .bg-page--home .bg-home-field-info__links,
  .bg-page--home .bg-home-partners,
  .bg-page--home .bg-home-footer__inner { min-width: var(--bg-home-width); }
}
'''

TEST_CONTENT = r'''"""Contract checks for the #868 current Buk-gu lower-home structure."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
JS = (STATIC / "citizen-action-demo-canvas.js").read_text(encoding="utf-8")
CSS = (STATIC / "citizen-action-demo-canvas.css").read_text(encoding="utf-8")


def _home_block() -> str:
    start = JS.index("  function _renderHome() {")
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
    ]:
        assert label in home


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
'''


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("utf-8") + data).hexdigest()


def require_equal(actual: str, expected: str, label: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{label}: expected {expected}, found {actual}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write the approved lower-home patch.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        require_equal(git_blob_sha1(CANVAS_JS), EXPECTED_JS_BLOB, "canvas JS blob")
        require_equal(git_blob_sha1(CANVAS_CSS), EXPECTED_CSS_BLOB, "canvas CSS blob")
        for filename in ASSETS:
            path = ROOT / "src/web/static/images/bukgu-current" / filename
            if not path.is_file():
                raise RuntimeError(f"required lower-home asset missing: {path}")
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    js = CANVAS_JS.read_text(encoding="utf-8")
    css = CANVAS_CSS.read_text(encoding="utf-8")
    marker = "          '</section>' +\n        '</main>' +\n        '<p class=\"bg-home-local-note\">"
    if js.count(marker) != 1:
        print("ERROR: audited lower-home insertion marker missing or ambiguous", file=sys.stderr)
        return 3
    if MARKER in css:
        print("ERROR: lower-home CSS marker already exists", file=sys.stderr)
        return 4
    if TEST_FILE.exists():
        print(f"ERROR: refusing to replace existing test file: {TEST_FILE}", file=sys.stderr)
        return 5

    if not args.apply:
        print("CHECK OK: audited JS/CSS/assets and insertion point match")
        print("PLAN: add lower semantic home sections, full-width footer, scoped CSS, and one contract test")
        return 0

    replacement = (
        "          '</section>' +\n" +
        LOWER_HTML +
        "        '</main>' +\n" +
        FOOTER_HTML +
        "        '<p class=\"bg-home-local-note\">"
    )
    CANVAS_JS.write_text(js.replace(marker, replacement, 1), encoding="utf-8")
    CANVAS_CSS.write_text(css.rstrip() + LOWER_CSS + "\n", encoding="utf-8")
    TEST_FILE.write_text(TEST_CONTENT, encoding="utf-8")
    print("APPLIED: #868 current lower-home semantic patch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
