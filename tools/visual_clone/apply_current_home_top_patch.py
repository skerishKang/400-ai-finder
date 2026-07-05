#!/usr/bin/env python3
"""Apply the exact #868 current Buk-gu home top-viewport source patch.

This is a one-time, offline-only mechanical patch. It refuses to run unless the
current JS/CSS/test files match the audited pre-patch Git blob IDs. It does not
contact a network service and it does not alter reference source captures.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANVAS_JS = ROOT / "src/web/static/citizen-action-demo-canvas.js"
CANVAS_CSS = ROOT / "src/web/static/citizen-action-demo-canvas.css"
TEST_FILE = ROOT / "tests/test_current_bukgu_home_top_contract.py"

EXPECTED_CANVAS_JS_BLOB = "b1ca54584edf5a9a709732f76eb96186067aeed4"
EXPECTED_CANVAS_CSS_BLOB = "d4a6b39919d9ad1ff64efaa9099b7eb93c87a203"
PATCH_MARKER = "/* #868 current Buk-gu home top viewport */"

HOME_FUNCTION = r'''  function _renderHome() {
    var assets = "/static/images/bukgu-current";
    var searchIcon =
      '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="10.8" cy="10.8" r="6.3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 16l4.4 4.4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
    var menuIcon =
      '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16M4 12h16M4 17h16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
    var arrowLeft =
      '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M14.5 5.5L8 12l6.5 6.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    var arrowRight =
      '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M9.5 5.5L16 12l-6.5 6.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    var quickItems = [
      ["home-quick-work.png", "업무검색"],
      ["home-quick-office.png", "청사안내"],
      ["home-quick-donation.png", "고향사랑기부제"],
      ["home-quick-money.png", "부꾸머니"],
      ["home-quick-reservation.png", "통합예약"],
      ["home-quick-waiting.png", "일반민원 대기현황"],
    ];
    var quickHtml = "";
    for (var i = 0; i < quickItems.length; i++) {
      quickHtml +=
        '<a href="#" class="bg-home-quick-link">' +
          '<img src="' + assets + '/' + quickItems[i][0] + '" alt="" class="bg-home-quick-link__icon" />' +
          '<span class="bg-home-quick-link__label">' + _escHtml(quickItems[i][1]) + '</span>' +
        '</a>';
    }

    return (
      '<div class="bg-page bg-page--full bg-page--home">' +
        '<div class="bg-skip"><a href="#bg-content-main">본문으로 바로가기</a></div>' +

        '<div class="bg-home-gov-strip">' +
          '<div class="bg-home-gov-strip__inner">' +
            '<img src="' + assets + '/home-government-notice.png" alt="이 누리집은 대한민국 공식 전자정부 누리집입니다." class="bg-home-gov-strip__notice" />' +
          '</div>' +
        '</div>' +

        '<div class="bg-home-utility" aria-label="사이트 도구">' +
          '<div class="bg-home-utility__inner">' +
            '<div class="bg-home-utility__weather">' +
              '<strong>26°C</strong>' +
              '<span>미세먼지 <b>좋음</b></span>' +
              '<span>초미세먼지 <b>좋음</b></span>' +
            '</div>' +
            '<div class="bg-home-utility__menus">' +
              '<a href="#">주요사이트 <span aria-hidden="true">▾</span></a>' +
              '<a href="#">SNS <span aria-hidden="true">▾</span></a>' +
              '<a href="#">KOR <span aria-hidden="true">▾</span></a>' +
            '</div>' +
          '</div>' +
        '</div>' +

        '<header class="bg-home-header bg-header">' +
          '<div class="bg-home-header__inner">' +
            '<a href="#" class="bg-home-header__identity" aria-label="전남광주통합특별시북구 홈">' +
              '<img src="' + assets + '/home-identity.png" alt="전남광주통합특별시북구" />' +
            '</a>' +
            '<nav class="bg-home-gnb bg-gnb" aria-label="주메뉴">' +
              '<a href="#" class="bg-home-gnb__link bg-home-gnb__link--active" data-action-target="nav-civil-service">종합민원</a>' +
              '<a href="#" class="bg-home-gnb__link">소통광장</a>' +
              '<a href="#" class="bg-home-gnb__link">더불어복지</a>' +
              '<a href="#" class="bg-home-gnb__link">분야별정보</a>' +
              '<a href="#" class="bg-home-gnb__link">정보공개</a>' +
              '<a href="#" class="bg-home-gnb__link">북구소개</a>' +
            '</nav>' +
            '<div class="bg-home-header__actions">' +
              '<button type="button" class="bg-home-header__icon" aria-label="통합검색">' + searchIcon + '<span>통합검색</span></button>' +
              '<button type="button" class="bg-home-header__icon" aria-label="전체메뉴">' + menuIcon + '<span>전체메뉴</span></button>' +
            '</div>' +
          '</div>' +
        '</header>' +

        '<section class="bg-home-search" aria-label="통합검색">' +
          '<div class="bg-home-search__inner">' +
            '<img src="' + assets + '/home-civic-brand.png" alt="내 삶이 행복한 주민주권도시 으뜸북구" class="bg-home-search__brand" />' +
            '<div class="bg-home-search__cluster">' +
              '<div class="bg-home-search__field">' +
                '<input type="text" placeholder="검색어를 입력하세요." aria-label="검색어" disabled />' +
                '<button type="button" aria-label="검색" disabled>' + searchIcon + '</button>' +
              '</div>' +
              '<div class="bg-home-search__tags"><span>#폐기물</span><span>#주정차</span><span>#채용</span><span>#건축과</span></div>' +
            '</div>' +
          '</div>' +
        '</section>' +

        '<main id="bg-content-main" class="bg-home-main">' +
          '<section class="bg-home-lead" aria-label="주요 안내">' +
            '<article class="bg-home-lead__mayor">' +
              '<img src="' + assets + '/home-mayor-card.png" alt="따뜻한 북구를 만들겠습니다. 북구청장 신수정입니다." />' +
            '</article>' +
            '<article class="bg-home-lead__banner" aria-label="소속 공무원 사칭 피해주의 알림">' +
              '<img src="' + assets + '/home-alert-banner.png" alt="소속 공무원 사칭 피해주의 알림" />' +
            '</article>' +
          '</section>' +

          '<nav class="bg-home-quick" aria-label="빠른 서비스">' +
            '<button type="button" class="bg-home-quick__arrow" aria-label="이전" disabled>' + arrowLeft + '</button>' +
            '<div class="bg-home-quick__items">' + quickHtml + '</div>' +
            '<button type="button" class="bg-home-quick__arrow" aria-label="다음" disabled>' + arrowRight + '</button>' +
          '</nav>' +

          '<section class="bg-home-notice-sites" aria-label="공지와 주요 사이트">' +
            '<article class="bg-home-notice">' +
              '<div class="bg-home-notice__tabs" role="tablist" aria-label="게시판">' +
                '<button type="button" role="tab" aria-selected="true">공지사항</button>' +
                '<button type="button" role="tab">고시공고</button>' +
                '<button type="button" role="tab">입찰공고</button>' +
                '<button type="button" role="tab">채용공고</button>' +
                '<button type="button" role="tab">보도자료</button>' +
                '<button type="button" role="tab">문화행사</button>' +
                '<button type="button" class="bg-home-notice__more" aria-label="더보기">+</button>' +
              '</div>' +
              '<ul class="bg-home-notice__list">' +
                '<li><b>03</b><span>2026년 국적취득비용(수수료) 지원사업 진행 안내</span></li>' +
                '<li><b>03</b><span>2026년 축산물이력제 식육포장처리업소 이력번호 표시 지원사업 안내</span></li>' +
                '<li><b>03</b><span>전남광주통합특별시 북구 소속 공무원 사칭 피해 주의 안내</span></li>' +
                '<li><b>03</b><span>2026년도 위기 청소년 특별지원 사업 대상자 추가 모집 안내</span></li>' +
              '</ul>' +
            '</article>' +
            '<article class="bg-home-sites">' +
              '<div class="bg-home-sites__head"><h2>주요사이트</h2><span>‹&nbsp;&nbsp;3 / 4&nbsp;&nbsp;Ⅱ&nbsp;&nbsp;›</span></div>' +
              '<div class="bg-home-sites__grid">' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--chart"></i>통계정보</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--school"></i>평생학습관</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--sun"></i>청년센터</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--culture"></i>문화센터</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--park"></i>공원시설<br>예약</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--sport"></i>체육시설<br>예약</a>' +
              '</div>' +
            '</article>' +
          '</section>' +
        '</main>' +
        '<p class="bg-home-local-note">로컬 시연 화면 · 외부 사이트와 연결하지 않습니다.</p>' +
      '</div>'
    );
  }'''

HOME_CSS = r'''

/* #868 current Buk-gu home top viewport */
.bg-page--home {
  --bg-home-width: 914px;
  background: #fff;
  color: #171717;
  min-width: 0;
}
.bg-page--home .bg-home-gov-strip {
  height: 31px;
  background: #f5f5f5;
  border-bottom: 1px solid #e3e3e3;
}
.bg-page--home .bg-home-gov-strip__inner,
.bg-page--home .bg-home-utility__inner,
.bg-page--home .bg-home-header__inner,
.bg-page--home .bg-home-search__inner,
.bg-page--home .bg-home-main {
  width: min(var(--bg-home-width), calc(100% - 32px));
  margin: 0 auto;
  box-sizing: border-box;
}
.bg-page--home .bg-home-gov-strip__inner {
  height: 100%;
  display: flex;
  align-items: center;
}
.bg-page--home .bg-home-gov-strip__notice {
  width: 200px;
  height: 20px;
  display: block;
  object-fit: contain;
  object-position: left center;
}
.bg-page--home .bg-home-utility {
  height: 24px;
  border-bottom: 1px solid #ececec;
  background: #fff;
}
.bg-page--home .bg-home-utility__inner {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 28px;
  font-size: 11px;
  color: #5f5f5f;
}
.bg-page--home .bg-home-utility__weather {
  display: flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;
}
.bg-page--home .bg-home-utility__weather strong {
  color: #152c64;
  font-size: 14px;
  font-weight: 700;
}
.bg-page--home .bg-home-utility__weather b {
  display: inline-block;
  margin-left: 2px;
  padding: 1px 6px;
  border-radius: 9px;
  color: #fff;
  background: #4296dc;
  font-size: 9px;
  font-weight: 600;
}
.bg-page--home .bg-home-utility__menus {
  display: flex;
  height: 100%;
  border-left: 1px solid #ededed;
}
.bg-page--home .bg-home-utility__menus a {
  min-width: 84px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #555;
  text-decoration: none;
  border-right: 1px solid #ededed;
}
.bg-page--home .bg-home-utility__menus span { margin-left: 3px; font-size: 9px; }

.bg-page--home .bg-home-header {
  height: 68px;
  background: #fff;
  border: 0;
  border-bottom: 1px solid #e7e7e7;
}
.bg-page--home .bg-home-header__inner {
  height: 100%;
  display: grid;
  grid-template-columns: 188px minmax(0, 1fr) 108px;
  align-items: center;
  gap: 18px;
}
.bg-page--home .bg-home-header__identity { display: block; line-height: 0; }
.bg-page--home .bg-home-header__identity img {
  display: block;
  width: 170px;
  height: 42px;
  object-fit: contain;
  object-position: left center;
}
.bg-page--home .bg-home-gnb {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-width: 0;
  background: transparent;
  border: 0;
}
.bg-page--home .bg-home-gnb__link {
  color: #101010;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.75px;
  text-decoration: none;
  white-space: nowrap;
}
.bg-page--home .bg-home-gnb__link--active { color: #101010; }
.bg-page--home .bg-home-header__actions {
  display: flex;
  justify-content: flex-end;
  gap: 14px;
}
.bg-page--home .bg-home-header__icon {
  width: 38px;
  border: 0;
  padding: 0;
  background: transparent;
  color: #008b68;
  display: grid;
  justify-items: center;
  gap: 1px;
  font-size: 8px;
  cursor: default;
}
.bg-page--home .bg-home-header__icon svg { width: 20px; height: 20px; }

.bg-page--home .bg-home-search {
  min-height: 135px;
  background: linear-gradient(90deg, #fff 0%, #fbfdfd 72%, #eff8f6 100%);
}
.bg-page--home .bg-home-search__inner {
  min-height: 135px;
  display: grid;
  grid-template-columns: 345px minmax(0, 1fr);
  align-items: center;
  gap: 52px;
}
.bg-page--home .bg-home-search__brand {
  display: block;
  width: 285px;
  height: 55px;
  object-fit: contain;
  object-position: left center;
}
.bg-page--home .bg-home-search__cluster { padding-top: 6px; }
.bg-page--home .bg-home-search__field {
  height: 42px;
  display: flex;
  overflow: visible;
  border: 2px solid #193b85;
  border-radius: 23px;
  background: #fff;
}
.bg-page--home .bg-home-search__field input {
  min-width: 0;
  flex: 1;
  border: 0;
  padding: 0 18px;
  color: #333;
  background: transparent;
  font-size: 11px;
  outline: none;
}
.bg-page--home .bg-home-search__field input::placeholder { color: #9c9c9c; }
.bg-page--home .bg-home-search__field button {
  width: 44px;
  height: 44px;
  margin: -3px -3px -3px 0;
  border: 0;
  border-radius: 50%;
  color: #fff;
  background: #117f91;
  display: grid;
  place-items: center;
}
.bg-page--home .bg-home-search__field button svg { width: 24px; height: 24px; }
.bg-page--home .bg-home-search__tags {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 8px;
  color: #5b5b5b;
  font-size: 10px;
}

.bg-page--home .bg-home-main { padding: 0; }
.bg-page--home .bg-home-lead {
  display: grid;
  grid-template-columns: 345px 561px;
  gap: 8px;
  margin-top: 0;
}
.bg-page--home .bg-home-lead__mayor,
.bg-page--home .bg-home-lead__banner {
  margin: 0;
  overflow: hidden;
  border-radius: 16px;
  box-shadow: 0 7px 17px rgba(20, 39, 75, 0.14);
  line-height: 0;
  background: #fff;
}
.bg-page--home .bg-home-lead__mayor { height: 297px; }
.bg-page--home .bg-home-lead__banner { height: 297px; }
.bg-page--home .bg-home-lead img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.bg-page--home .bg-home-quick {
  height: 110px;
  box-sizing: border-box;
  margin-top: 30px;
  padding: 0 24px;
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) 42px;
  align-items: center;
  gap: 8px;
  border: 1px solid #e4e6e8;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.95);
}
.bg-page--home .bg-home-quick__arrow {
  width: 34px;
  height: 34px;
  padding: 7px;
  border: 1px solid #e0e3e4;
  border-radius: 50%;
  color: #69747e;
  background: #fff;
}
.bg-page--home .bg-home-quick__arrow svg { width: 100%; height: 100%; }
.bg-page--home .bg-home-quick__items {
  height: 76px;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  align-items: center;
}
.bg-page--home .bg-home-quick-link {
  min-width: 0;
  height: 70px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border-right: 1px solid #edf0f2;
  color: #383838;
  text-align: center;
  text-decoration: none;
  font-size: 11px;
  letter-spacing: -0.5px;
}
.bg-page--home .bg-home-quick-link:last-child { border-right: 0; }
.bg-page--home .bg-home-quick-link__icon { width: 41px; height: 41px; object-fit: contain; }
.bg-page--home .bg-home-quick-link__label { white-space: nowrap; }

.bg-page--home .bg-home-notice-sites {
  display: grid;
  grid-template-columns: 548px 358px;
  gap: 8px;
  margin-top: 20px;
  padding-bottom: 30px;
}
.bg-page--home .bg-home-notice,
.bg-page--home .bg-home-sites {
  min-height: 183px;
  box-sizing: border-box;
  overflow: hidden;
  border: 1px solid #e3e5e7;
  border-radius: 6px;
  background: #fff;
}
.bg-page--home .bg-home-notice__tabs {
  height: 39px;
  display: flex;
  align-items: stretch;
  border-bottom: 1px solid #e9e9e9;
}
.bg-page--home .bg-home-notice__tabs button {
  position: relative;
  border: 0;
  padding: 0 14px;
  color: #333;
  background: transparent;
  font-size: 12px;
  font-weight: 700;
}
.bg-page--home .bg-home-notice__tabs button[aria-selected="true"] { color: #009e6d; }
.bg-page--home .bg-home-notice__tabs button[aria-selected="true"]::after {
  position: absolute;
  right: 0;
  bottom: -1px;
  left: 0;
  height: 2px;
  content: "";
  background: #009e6d;
}
.bg-page--home .bg-home-notice__tabs .bg-home-notice__more {
  width: 28px;
  height: 28px;
  margin: 5px 8px 0 auto;
  padding: 0;
  border-radius: 50%;
  color: #fff;
  background: #009e6d;
  font-size: 18px;
  line-height: 1;
}
.bg-page--home .bg-home-notice__list { margin: 0; padding: 4px 16px; list-style: none; }
.bg-page--home .bg-home-notice__list li {
  display: grid;
  grid-template-columns: 44px 1fr;
  align-items: center;
  min-height: 31px;
  border-bottom: 1px solid #f1f1f1;
  color: #6a6a6a;
  font-size: 10px;
}
.bg-page--home .bg-home-notice__list b { color: #1e1e1e; font-size: 14px; }
.bg-page--home .bg-home-notice__list span { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.bg-page--home .bg-home-sites__head {
  height: 39px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid #e9e9e9;
}
.bg-page--home .bg-home-sites__head h2 { margin: 0; font-size: 14px; }
.bg-page--home .bg-home-sites__head span { color: #333; font-size: 11px; }
.bg-page--home .bg-home-sites__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: 67px;
  padding: 6px 10px;
}
.bg-page--home .bg-home-sites__grid a {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  color: #4d4d4d;
  text-align: center;
  text-decoration: none;
  font-size: 10px;
  line-height: 1.15;
}
.bg-page--home .bg-home-sites__glyph {
  width: 21px;
  height: 21px;
  display: block;
  position: relative;
  box-sizing: border-box;
  border: 2px solid #888;
  border-radius: 3px;
}
.bg-page--home .bg-home-sites__glyph--chart { border-radius: 0; border-top: 0; }
.bg-page--home .bg-home-sites__glyph--chart::before,
.bg-page--home .bg-home-sites__glyph--chart::after {
  position: absolute;
  bottom: 0;
  width: 3px;
  content: "";
  background: #d47272;
}
.bg-page--home .bg-home-sites__glyph--chart::before { left: 3px; height: 8px; }
.bg-page--home .bg-home-sites__glyph--chart::after { right: 3px; height: 14px; }
.bg-page--home .bg-home-sites__glyph--school { border-top: 0; border-radius: 0; }
.bg-page--home .bg-home-sites__glyph--school::before { position: absolute; top: -6px; left: 2px; width: 13px; height: 13px; content: ""; border-top: 2px solid #888; border-left: 2px solid #888; transform: rotate(45deg); }
.bg-page--home .bg-home-sites__glyph--sun { border-radius: 50%; border-color: #d47272; }
.bg-page--home .bg-home-sites__glyph--culture { border-radius: 50% 50% 50% 0; border-color: #d47272; }
.bg-page--home .bg-home-sites__glyph--park { border-radius: 50%; border-color: #708a79; }
.bg-page--home .bg-home-sites__glyph--sport { border-radius: 50%; border-color: #d47272; }
.bg-page--home .bg-home-local-note {
  width: min(var(--bg-home-width), calc(100% - 32px));
  margin: 0 auto 10px;
  color: #777;
  text-align: right;
  font-size: 9px;
}
@media (max-width: 940px) {
  .bg-page--home .bg-home-header__inner,
  .bg-page--home .bg-home-search__inner,
  .bg-page--home .bg-home-lead,
  .bg-page--home .bg-home-notice-sites { min-width: var(--bg-home-width); }
  .bg-page--home { overflow-x: auto; }
}
'''

TEST_CONTENT = r'''"""Contract checks for the #868 current Buk-gu home top viewport."""

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
        assert f"/bukgu-current/{asset}" in home
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
'''


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("utf-8") + data).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write the audited patch.")
    return parser.parse_args()


def require_blob(path: Path, expected: str) -> None:
    actual = git_blob_sha1(path)
    if actual != expected:
        raise RuntimeError(f"{path}: expected blob {expected}, found {actual}")


def main() -> int:
    args = parse_args()
    try:
        require_blob(CANVAS_JS, EXPECTED_CANVAS_JS_BLOB)
        require_blob(CANVAS_CSS, EXPECTED_CANVAS_CSS_BLOB)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    js = CANVAS_JS.read_text(encoding="utf-8")
    css = CANVAS_CSS.read_text(encoding="utf-8")
    start_marker = "  function _renderHome() {"
    end_marker = "  // -----------------------------------------------------------------------\n  // _renderCivilService"
    start = js.find(start_marker)
    end = js.find(end_marker, start)
    if start < 0 or end < 0:
        print("ERROR: audited home renderer markers are missing", file=sys.stderr)
        return 3
    if PATCH_MARKER in css:
        print("ERROR: home top patch marker already exists", file=sys.stderr)
        return 4
    if TEST_FILE.exists():
        print(f"ERROR: refusing to replace existing test file: {TEST_FILE}", file=sys.stderr)
        return 5

    if not args.apply:
        print("CHECK OK: audited source blobs and insertion markers match")
        print("PLAN: replace only _renderHome; append scoped home CSS; add one contract test")
        return 0

    CANVAS_JS.write_text(js[:start] + HOME_FUNCTION + "\n\n" + js[end:], encoding="utf-8")
    CANVAS_CSS.write_text(css.rstrip() + HOME_CSS + "\n", encoding="utf-8")
    TEST_FILE.write_text(TEST_CONTENT, encoding="utf-8")
    print("APPLIED: current Buk-gu home top viewport patch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
