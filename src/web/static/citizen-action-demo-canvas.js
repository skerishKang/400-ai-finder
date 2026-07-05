/**
 * citizen-action-demo-canvas.js
 * High-fidelity route-rendered canvas — Buk-gu Office portal reconstruction.
 * Reference: bukgu_home.png, bukgu_menu.png, bukgu_intake.png
 * No fetch, no persistence, no external URLs.
 * Uses closed vocabulary from citizen-action-demo-map.js (NOT modified).
 */

(function () {
  "use strict";

  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------
  var _currentRouteId = "home";
  var _selectedCategory = null;

  // DOM references
  var _demoCanvas = document.getElementById("demo-canvas");
  var _map = window.CitizenActionDemoMap;

  // -----------------------------------------------------------------------
  // Utility
  // -----------------------------------------------------------------------
  function _assert(valid, msg) {
    if (!valid) { throw new Error("CanvasError: " + msg); }
  }

  function _escHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // -----------------------------------------------------------------------
  // Shared render pieces
  // -----------------------------------------------------------------------

  function _renderNavBar() {
    return (
      '<nav class="bg-nav-bar" aria-label="데모 상단 내비게이션">' +
        '<span class="bg-nav-bar__title">🏠 시민 행정 도우미</span>' +
        '<span class="bg-nav-bar__hint">로컬 개념 시연</span>' +
      '</nav>'
    );
  }

  function _renderSubHeader(currentLabel) {
    return (
      '<nav class="bg-nav-bar" aria-label="데모 내비게이션">' +
        '<span class="bg-nav-bar__title">🏠 시민 행정 도우미</span>' +
        '<span class="bg-nav-bar__crumb">' + _escHtml(currentLabel) + '</span>' +
        '<span class="bg-nav-bar__hint">로컬 개념 시연</span>' +
      '</nav>'
    );
  }

  function _renderBreadcrumb(items) {
    var html = '<div class="bg-breadcrumb" aria-label="현재 위치">';
    for (var i = 0; i < items.length; i++) {
      if (i > 0) {
        html += '<span class="bg-breadcrumb__sep" aria-hidden="true">›</span>';
      }
      html += '<span class="bg-breadcrumb__item">' + _escHtml(items[i].label) + '</span>';
    }
    html += '</div>';
    return html;
  }

  function _renderSubPageHeader(title, purpose) {
    return (
      '<div class="bg-page-header">' +
        '<h1 class="bg-page-header__title">' + _escHtml(title) + '</h1>' +
        (purpose ? '<p class="bg-page-header__purpose">' + _escHtml(purpose) + '</p>' : '') +
      '</div>'
    );
  }

  function _renderPocBanner() {
    return (
      '<div class="bg-poc-banner" role="note" aria-label="데모 고지">' +
        '<span class="bg-poc-banner__label">⚠️ 로컬 개념 시연 (PoC) 안내</span>' +
        '<p class="bg-poc-banner__text">' +
          '이 페이지는 실제 북구청 공식 사이트가 아니며, 로컬 개념 시연 (PoC) 목적으로 제작되었습니다.<br>' +
          '본 데모에서는 어떠한 데이터도 실제로 제출되거나 처리되지 않습니다.' +
        '</p>' +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // Demo overlay — floating panel with AI guidance + category cards
  // -----------------------------------------------------------------------
  function _renderDemoOverlay() {
    var categoryTargets = [];
    var catRoute = _map.getRoute("complaint-category");
    if (catRoute) {
      categoryTargets = catRoute.navTargets;
    }

    var cardsHtml = '';
    for (var i = 0; i < categoryTargets.length; i++) {
      var tid = categoryTargets[i];
      var label = _map.getCategoryLabel(tid) || tid;
      var icons = {
        "complaint-category-illegal-parking": "🚗",
        "complaint-category-public-parking-inconvenience": "🅿️",
        "complaint-category-residential-parking": "🏢",
        "complaint-category-traffic-or-facility-safety": "⚠️",
        "complaint-category-other-or-unsure": "📋",
      };
      var icon = icons[tid] || "📋";
      cardsHtml +=
        '<button class="bg-demo-overlay__card" data-action-target="' + _escHtml(tid) + '" type="button">' +
          '<span class="bg-demo-overlay__card-icon">' + icon + '</span>' +
          '<span class="bg-demo-overlay__card-label">' + _escHtml(label) + '</span>' +
          '<span class="bg-demo-overlay__card-arrow" aria-hidden="true">›</span>' +
        '</button>';
    }

    // Determine progress state based on current route
    var progressSteps = [
      { id: "home", label: "홈" },
      { id: "civil-service", label: "신청" },
      { id: "complaint-category", label: "안내" },
      { id: "complaint-intake", label: "작성" },
      { id: "handoff-stop", label: "종료" },
    ];

    var currentIdx = 0;
    for (var j = 0; j < progressSteps.length; j++) {
      if (progressSteps[j].id === _currentRouteId) {
        currentIdx = j;
        break;
      }
    }

    var progressHtml = '';
    for (var k = 0; k < progressSteps.length; k++) {
      if (k > 0) {
        progressHtml += '<span class="bg-demo-overlay__progress-sep">›</span>';
      }
      var cls = 'bg-demo-overlay__progress-step';
      if (k < currentIdx) cls += ' bg-demo-overlay__progress-step--done';
      else if (k === currentIdx) cls += ' bg-demo-overlay__progress-step--active';
      progressHtml += '<span class="' + cls + '">' +
        (k < currentIdx ? '✓' : (k === currentIdx ? '●' : '○')) +
        ' ' + progressSteps[k].label + '</span>';
    }

    return (
      '<div class="bg-demo-overlay" role="complementary" aria-label="AI 도우미 · 로컬 시연">' +
        '<div class="bg-demo-overlay__header">' +
          '<span class="bg-demo-overlay__header-icon">🤖</span>' +
          '<span>AI 도우미 · 로컬 시연</span>' +
        '</div>' +
        '<div class="bg-demo-overlay__body">' +
          '<div class="bg-demo-overlay__guidance">' +
            '💡 <strong>불법 주정차 신고</strong> 관련 경로를 안내합니다.' +
          '</div>' +
          '<div class="bg-demo-overlay__cards">' +
            cardsHtml +
          '</div>' +
        '</div>' +
        '<div class="bg-demo-overlay__progress">' +
          progressHtml +
        '</div>' +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // _renderHome — faithful Buk-gu Office main portal
  // -----------------------------------------------------------------------
  function _renderHome() {
    var crops = "/static/images/bukgu-crops";
    return (
      '<div class="bg-page bg-page--full bg-page--home">' +
        /* skip nav */
        '<div class="bg-skip"><a href="#bg-content-main">본문으로 바로가기</a></div>' +

        /* Utility bar */
        '<div class="bg-util-bar">' +
          '<div class="bg-util-bar__left">' +
            '<a href="#" class="bg-hlink">Home</a><span class="bg-utility-sep">|</span>' +
            '<a href="#" class="bg-hlink">English</a><span class="bg-utility-sep">|</span>' +
            '<a href="#" class="bg-hlink">Chinese</a><span class="bg-utility-sep">|</span>' +
            '<a href="#" class="bg-hlink">Site Map</a>' +
          '</div>' +
          '<div class="bg-util-bar__right">' +
            '<a href="#" class="bg-hlink">LOGIN</a><span class="bg-utility-sep">|</span>' +
            '<a href="#" class="bg-hlink">JOIN</a><span class="bg-utility-sep">|</span>' +
            '<a href="#" class="bg-hlink">Search</a>' +
          '</div>' +
        '</div>' +

        /* Header */
        '<header class="bg-header">' +
          '<div class="bg-header__inner">' +
            '<a href="#" class="bg-logo">' +
              '<img src="/static/images/bukgu-crops/home-logo-identity.png" alt="광주광역시 북구 (전남광주통합특별시북구)" style="height:42px; width:auto; display:block;" />' +
            '</a>' +
          '</div>' +
        '</header>' +

        /* GNB */
        '<nav class="bg-gnb" aria-label="주메뉴">' +
          '<div class="bg-gnb__inner">' +
            '<ul class="bg-gnb__list">' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link bg-gnb__link--active" data-action-target="nav-civil-service">종합민원</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">소통광장</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">더불어복지</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">분야별정보</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">정보공개</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">북구소개</a></li>' +
            '</ul>' +
            '<div class="bg-gnb__tools">' +
              '<button class="bg-gnb__icon-btn" type="button" aria-label="검색">🔍</button>' +
              '<button class="bg-gnb__icon-btn" type="button" aria-label="전체메뉴">☰</button>' +
            '</div>' +
          '</div>' +
        '</nav>' +

        /* Search hero */
        '<div class="bg-search-hero">' +
          '<div class="bg-search-hero__inner">' +
            '<div class="bg-search-hero__form">' +
              '<input type="text" class="bg-search-hero__input" placeholder="검색어를 입력하세요." aria-label="통합검색" />' +
              '<button class="bg-search-hero__btn" type="button" aria-label="검색">🔍</button>' +
            '</div>' +
            '<div class="bg-search-hero__tags">' +
              '<a href="#" class="bg-search-hero__tag">#공동주택과</a>' +
              '<a href="#" class="bg-search-hero__tag">#위생과</a>' +
              '<a href="#" class="bg-search-hero__tag">#폐기물</a>' +
              '<a href="#" class="bg-search-hero__tag">#부끄머니</a>' +
            '</div>' +
          '</div>' +
        '</div>' +

        /* Hero — 2-column carousel using official crop images */
        '<div class="bg-hero">' +
          /* Left: mayor card using crop image */
          '<div class="bg-hero__left bg-hero__left--crop">' +
            '<img src="' + crops + '/home-hero-mayor.png" alt="따뜻한 북구를 만들겠습니다. 북구청장 신수정" class="bg-hero__crop-img">' +
            '<div style="display:none;">' +
              '<a href="#">열린구청장실 바로가기</a>' +
              '<a href="#">매니페스토 바로가기</a>' +
            '</div>' +
          '</div>' +
          /* Right: census card using crop image */
          '<div class="bg-hero__right bg-hero__right--crop">' +
            '<img src="' + crops + '/home-hero-census.png" alt="2025년 기준 경제총조사" class="bg-hero__crop-img">' +
            '<div style="display:none;">' +
              '<a href="#" data-action-target="nav-civil-service">자세히보기</a>' +
            '</div>' +
          '</div>' +
        '</div>' +

        /* Quick services — 6 square cards using crop images */
        '<div class="bg-quick">' +
          '<a href="#" class="bg-quick-item bg-quick-item--crop">' +
            '<img src="' + crops + '/home-quick-search.png" alt="업무검색" class="bg-quick-item__img">업무검색</a>' +
          '<a href="#" class="bg-quick-item bg-quick-item--crop">' +
            '<img src="' + crops + '/home-quick-office.png" alt="청사안내" class="bg-quick-item__img">청사안내</a>' +
          '<a href="#" class="bg-quick-item bg-quick-item--crop" data-action-target="nav-civil-service">' +
            '<img src="' + crops + '/home-quick-donation.png" alt="종합민원" class="bg-quick-item__img">종합민원</a>' +
          '<a href="#" class="bg-quick-item bg-quick-item--crop">' +
            '<img src="' + crops + '/home-quick-money.png" alt="부끄머니" class="bg-quick-item__img">부끄머니</a>' +
          '<a href="#" class="bg-quick-item bg-quick-item--crop">' +
            '<img src="' + crops + '/home-quick-reservation.png" alt="통합예약" class="bg-quick-item__img">통합예약</a>' +
          '<a href="#" class="bg-quick-item bg-quick-item--crop">' +
            '<img src="' + crops + '/home-quick-waiting.png" alt="일반민원 대기현황" class="bg-quick-item__img">일반민원 대기현황</a>' +
        '</div>' +

        /* Notice/News + Major Sites grid */
        '<div class="bg-notice-grid">' +
          '<div class="bg-notice-panel">' +
            '<div class="bg-notice-tabs" role="tablist" aria-label="게시판 종류">' +
              '<a href="#" class="bg-notice-tab bg-notice-tab--active" role="tab" aria-selected="true">공지사항</a>' +
              '<a href="#" class="bg-notice-tab" role="tab">고시공고</a>' +
              '<a href="#" class="bg-notice-tab" role="tab">입찰공고</a>' +
              '<a href="#" class="bg-notice-tab" role="tab">채용공고</a>' +
              '<a href="#" class="bg-notice-tab" role="tab">보도자료</a>' +
              '<a href="#" class="bg-notice-tab" role="tab">문화행사</a>' +
            '</div>' +
            '<ul class="bg-card-list">' +
              '<li><a href="#">2026.07.03 2026년 국적취득비용(수수료) 지원사업 진행 안내</a></li>' +
              '<li><a href="#">2026.07.03 2026년 축산물이력제 식육포장처리업소 이력번호 표시 지원사업 안내</a></li>' +
              '<li><a href="#">2026년 전남광주통합특별시 북구 소속 공무원 사칭 피해 주의 안내</a></li>' +
              '<li><a href="#">2026년도 위기 청소년 특별지원 사업 대상자 추가 모집 안내</a></li>' +
            '</ul>' +
            '<a href="#" class="bg-more bg-more--bottom">더보기 ›</a>' +
          '</div>' +
          '<div class="bg-sites-panel">' +
            '<h3 class="bg-card-title">주요사이트</h3>' +
            '<div class="bg-sites-grid">' +
              '<a href="#" class="bg-sites-item"><span class="bg-sites-item__icon">▸</span> 통계정보</a>' +
              '<a href="#" class="bg-sites-item"><span class="bg-sites-item__icon">▸</span> 평생학습관</a>' +
              '<a href="#" class="bg-sites-item"><span class="bg-sites-item__icon">▸</span> 청년센터</a>' +
              '<a href="#" class="bg-sites-item"><span class="bg-sites-item__icon">▸</span> 문화센터</a>' +
              '<a href="#" class="bg-sites-item"><span class="bg-sites-item__icon">▸</span> 공원시설 예약</a>' +
              '<a href="#" class="bg-sites-item"><span class="bg-sites-item__icon">▸</span> 체육시설 예약</a>' +
            '</div>' +
          '</div>' +
        '</div>' +

        /* Sub carousels with crops */
        '<div class="bg-sub-carousels">' +
          '<div class="bg-sub-carousel">' +
            '<div class="bg-sub-carousel__tabs">' +
              '<button class="bg-sub-carousel__tab bg-sub-carousel__tab--active">고향사랑기부제</button>' +
            '</div>' +
            '<div class="bg-sub-carousel__body bg-sub-carousel__body--crop">' +
              '<img src="' + crops + '/home-card-donation.png" alt="고향사랑기부제" class="bg-carousel-crop-img">' +
            '</div>' +
          '</div>' +
          '<div class="bg-sub-carousel">' +
            '<div class="bg-sub-carousel__tabs">' +
              '<button class="bg-sub-carousel__tab bg-sub-carousel__tab--active">현장스케치</button>' +
            '</div>' +
            '<div class="bg-sub-carousel__body bg-sub-carousel__body--crop">' +
              '<img src="' + crops + '/home-card-field-sketch.png" alt="현장스케치" class="bg-carousel-crop-img">' +
            '</div>' +
          '</div>' +
          '<div class="bg-sub-carousel">' +
            '<div class="bg-sub-carousel__tabs">' +
              '<button class="bg-sub-carousel__tab bg-sub-carousel__tab--active">카드뉴스</button>' +
            '</div>' +
            '<div class="bg-sub-carousel__body bg-sub-carousel__body--crop">' +
              '<img src="' + crops + '/home-card-news.png" alt="카드뉴스" class="bg-carousel-crop-img">' +
            '</div>' +
          '</div>' +
          '<div class="bg-sub-carousel">' +
            '<div class="bg-sub-carousel__tabs">' +
              '<button class="bg-sub-carousel__tab bg-sub-carousel__tab--active">알리미</button>' +
            '</div>' +
            '<div class="bg-sub-carousel__body bg-sub-carousel__body--crop">' +
              '<img src="' + crops + '/home-card-notice.png" alt="알리미" class="bg-carousel-crop-img">' +
            '</div>' +
          '</div>' +
        '</div>' +

        /* Footer banners */
        '<div class="bg-footer__banners">' +
          '<div class="bg-footer__banners-inner">' +
            '<a href="#" class="bg-footer__banner-link">🏛 Biennale</a>' +
            '<a href="#" class="bg-footer__banner-link">🏦 NPS</a>' +
            '<a href="#" class="bg-footer__banner-link">⚖️ 고용노동부</a>' +
            '<div class="bg-footer__banner-controls">' +
              '<button class="bg-footer__banner-btn" type="button">◀</button>' +
              '<button class="bg-footer__banner-btn" type="button">▶</button>' +
            '</div>' +
          '</div>' +
        '</div>' +

        /* Footer mid */
        '<div class="bg-footer__mid">' +
          '<div class="bg-footer__mid-inner">' +
            '<select class="bg-footer__dropdown" aria-label="부서안내"><option>부서안내</option></select>' +
            '<select class="bg-footer__dropdown" aria-label="동 행정복지센터"><option>동 행정복지센터</option></select>' +
            '<select class="bg-footer__dropdown" aria-label="주요사이트"><option>주요사이트</option></select>' +
            '<select class="bg-footer__dropdown" aria-label="유관기관"><option>유관기관</option></select>' +
          '</div>' +
        '</div>' +

        /* Footer bottom */
        '<footer class="bg-footer__bot">' +
          '<div class="bg-footer__bot-inner">' +
            '<div class="bg-footer__bot-logo">' +
              '<img src="/static/images/bukgu-crops/home-footer-identity.png" alt="광주광역시 북구" style="height:32px; width:auto; display:block;" />' +
            '</div>' +
            '<div class="bg-footer__bot-text">' +
              '<p>61187 전남광주통합특별시 북구 우치로 77 (용봉동) | 대표전화: 062-410-8000</p>' +
              '<div class="bg-footer__bot-legal">' +
                '<a href="#">누리집 이용안내</a> <span>|</span> ' +
                '<a href="#">개인정보처리방침</a> <span>|</span> ' +
                '<a href="#">저작권 보호정책</a> <span>|</span> ' +
                '<a href="#">이메일무단수집거부</a> <span>|</span> ' +
                '<a href="#">영상정보처리기기 운영·관리 방침</a>' +
              '</div>' +
              '<div class="bg-footer__bot-copy">' +
                'Copyright © Jeonnam-Gwangju Special Metropolitan City BUKGU. all rights reserved.' +
              '</div>' +
            '</div>' +
            '<div class="bg-footer__bot-badges">' +
              '<img src="' + crops + '/home-footer-wa.png" alt="WA" class="bg-footer__badge-img">' +
              '<img src="' + crops + '/home-footer-open-data.png" alt="Open Data" class="bg-footer__badge-img">' +
              '<img src="' + crops + '/home-footer-qr-mascot.png" alt="QR Mascot" class="bg-footer__badge-img">' +
            '</div>' +
          '</div>' +
        '</footer>' +

      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // _renderCivilService — intermediate route
  // -----------------------------------------------------------------------
  function _renderCivilService(route) {
    return (
      '<div class="bg-page bg-page--full">' +
        /* Utility bar */
        '<div class="bg-util-bar">' +
          '<div class="bg-util-bar__left">' +
            '<span class="bg-dust-pill"><span class="bg-dust-pill__dot"></span> 미세먼지 좋음</span>' +
            '<span class="bg-dust-pill"><span class="bg-dust-pill__dot"></span> 초미세먼지 좋음</span>' +
          '</div>' +
          '<div class="bg-util-bar__right">' +
            '<a href="#" class="bg-hlink">주요사이트 ▼</a>' +
            '<a href="#" class="bg-hlink">SNS ▼</a>' +
            '<a href="#" class="bg-hlink">KOR ▼</a>' +
          '</div>' +
        '</div>' +

        /* Header */
        '<header class="bg-header">' +
          '<div class="bg-header__inner">' +
            '<a href="#" class="bg-logo">' +
              '<img src="/static/images/bukgu-crops/home-logo-identity.png" alt="광주광역시 북구 (전남광주통합특별시북구)" style="height:42px; width:auto; display:block;" />' +
            '</a>' +
          '</div>' +
        '</header>' +

        /* GNB */
        '<nav class="bg-gnb" aria-label="주메뉴">' +
          '<div class="bg-gnb__inner">' +
            '<ul class="bg-gnb__list">' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link bg-gnb__link--active" data-action-target="nav-civil-service">종합민원</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">소통광장</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">더불어복지</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">분야별정보</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">정보공개</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">북구소개</a></li>' +
            '</ul>' +
            '<div class="bg-gnb__tools">' +
              '<button class="bg-gnb__icon-btn" type="button" aria-label="검색">🔍</button>' +
              '<button class="bg-gnb__icon-btn" type="button" aria-label="전체메뉴">☰</button>' +
            '</div>' +
          '</div>' +
        '</nav>' +

        '<main class="bg-content bg-content--sub" id="bg-content-main">' +
          _renderSubPageHeader(route.title, route.purpose) +
          '<p class="bg-guide-text">아래 유익한 민원 서비스를 선택하여 절차를 안내받으세요.</p>' +
          _renderNavTargets(route.navTargets, "complaint-category") +
        '</main>' +
        _renderSubFooter() +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // _renderCheongwon24 — 청원24 info page (replaces complaint-category)
  // Faithful reproduction of bukgu_menu.png
  // -----------------------------------------------------------------------
  function _renderCheongwon24(route) {
    return (
      '<div class="bg-page bg-page--full">' +
        /* Utility bar */
        '<div class="bg-util-bar">' +
          '<div class="bg-util-bar__left">' +
            '<span class="bg-dust-pill"><span class="bg-dust-pill__dot"></span> 미세먼지 좋음</span>' +
            '<span class="bg-dust-pill"><span class="bg-dust-pill__dot"></span> 초미세먼지 좋음</span>' +
          '</div>' +
          '<div class="bg-util-bar__right">' +
            '<a href="#" class="bg-hlink">주요사이트 ▼</a>' +
            '<a href="#" class="bg-hlink">SNS ▼</a>' +
            '<a href="#" class="bg-hlink">KOR ▼</a>' +
          '</div>' +
        '</div>' +

        /* Header */
        '<header class="bg-header">' +
          '<div class="bg-header__inner">' +
            '<a href="#" class="bg-logo">' +
              '<img src="/static/images/bukgu-crops/home-logo-identity.png" alt="광주광역시 북구 (전남광주통합특별시북구)" style="height:42px; width:auto; display:block;" />' +
            '</a>' +
          '</div>' +
        '</header>' +

        /* GNB */
        '<nav class="bg-gnb" aria-label="주메뉴">' +
          '<div class="bg-gnb__inner">' +
            '<ul class="bg-gnb__list">' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link bg-gnb__link--active" data-action-target="nav-civil-service">종합민원</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">소통광장</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">더불어복지</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">분야별정보</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">정보공개</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">북구소개</a></li>' +
            '</ul>' +
            '<div class="bg-gnb__tools">' +
              '<button class="bg-gnb__icon-btn" type="button" aria-label="검색">🔍</button>' +
              '<button class="bg-gnb__icon-btn" type="button" aria-label="전체메뉴">☰</button>' +
            '</div>' +
          '</div>' +
        '</nav>' +

        '<div class="bg-layout--lnb">' +
          /* LNB sidebar */
          '<nav class="bg-lnb" aria-label="좌측 메뉴">' +
            '<div class="bg-lnb__header">종합민원</div>' +
            '<ul class="bg-lnb__list">' +
              '<li class="bg-lnb__item bg-lnb__item--active"><a href="#">종합민원</a></li>' +
              '<li class="bg-lnb__item bg-lnb__item--open">' +
                '<a href="#" class="bg-lnb__parent">전자민원창구</a>' +
                '<ul class="bg-lnb__sub">' +
                  '<li><a href="#">민원처리공개</a></li>' +
                  '<li><a href="#">민원상담(국민신문고)<span class="bg-lnb__ext-link"></span></a></li>' +
                  '<li><a href="#">정부24<span class="bg-lnb__ext-link"></span></a></li>' +
                  '<li class="bg-lnb__sub--active"><a href="#" data-action-target="nav-complaint-category">청원24(온라인청원제도)<span class="bg-lnb__ext-link"></span></a></li>' +
                  '<li><a href="#">온라인 행정심판이용안내<span class="bg-lnb__ext-link"></span></a></li>' +
                  '<li><a href="#">110수화(화상)상담<span class="bg-lnb__ext-link"></span></a></li>' +
                '</ul>' +
              '</li>' +
              '<li class="bg-lnb__item bg-lnb__item--collapsed">' +
                '<a href="#" class="bg-lnb__parent">민원신고</a>' +
              '</li>' +
              '<li class="bg-lnb__item bg-lnb__item--collapsed">' +
                '<a href="#" class="bg-lnb__parent">행정서비스 헌장</a>' +
              '</li>' +
            '</ul>' +
          '</nav>' +

          /* Main content */
          '<main class="bg-content bg-content--sub" id="bg-content-main">' +
            /* Breadcrumb + tools */
            '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;font-size:0.75rem;color:#888;">' +
              '<span>Home › 종합민원 › 전자민원창구 › 청원24</span>' +
              '<span style="display:flex;gap:4px;">' +
                '<span style="cursor:pointer;padding:2px 6px;border:1px solid #ddd;border-radius:2px;">🔍</span>' +
                '<span style="cursor:pointer;padding:2px 6px;border:1px solid #ddd;border-radius:2px;">🖨</span>' +
                '<span style="cursor:pointer;padding:2px 6px;border:1px solid #ddd;border-radius:2px;">📤</span>' +
              '</span>' +
            '</div>' +

            /* Title row */
            '<div class="bg-cheongwon__title-row">' +
              '<h1 class="bg-cheongwon__title" style="font-size:1.375rem;">청원24(온라인청원제도)</h1>' +
              '<button class="bg-cheongwon__cardnews-btn" type="button">카드뉴스 보기</button>' +
            '</div>' +

            '<div class="bg-cheongwon">' +
              /* 청원이란? */
              '<div class="bg-cheongwon__section">' +
                '<h2 class="bg-cheongwon__section-title">청원이란?</h2>' +
                '<p class="bg-cheongwon__text">' +
                  '청원이란 국민 또는 법인이 국가기관, 지방자치단체, 공공기관 등에 대하여 의견이나 요구사항을 제출하는 제도입니다.' +
                '</p>' +
              '</div>' +

              /* 청원24란? */
              '<div class="bg-cheongwon__section">' +
                '<h2 class="bg-cheongwon__section-title">청원24란?</h2>' +
                '<p class="bg-cheongwon__text">' +
                  '청원24(온라인청원제도)는 국민이 온라인으로 청원을 제출하고 그 처리결과를 확인할 수 있는 전자청원시스템입니다.' +
                '</p>' +
                '<div class="bg-cheongwon__note">' +
                  '※ 청원24는 정부24 등 다른 전자민원창구와 별개로, 청원 고유의 절차에 따라 처리됩니다.' +
                '</div>' +
              '</div>' +

              /* 청원 신청 방법 */
              '<div class="bg-cheongwon__section">' +
                '<h2 class="bg-cheongwon__section-title">청원 신청 방법</h2>' +
                '<p class="bg-cheongwon__text">' +
                  '청원은 청원24 홈페이지(<a href="#" class="bg-cheongwon__ext-link">www.cheongwon24.go.kr</a>)에서 온라인으로 신청하거나, 방문 또는 우편으로 제출할 수 있습니다.' +
                '</p>' +
                '<div class="bg-cheongwon__note">' +
                  '※ 청원 제출 시 청원인의 성명, 주소, 연락처와 청원의 요지 및 이유를 기재하여야 합니다.' +
                '</div>' +
              '</div>' +

              /* Process flow */
              '<div class="bg-cheongwon__section">' +
                '<h2 class="bg-cheongwon__section-title">청원 처리 절차</h2>' +
                '<div class="bg-cheongwon__process">' +
                  '<span class="bg-cheongwon__step bg-cheongwon__step--highlight">청원</span>' +
                  '<span class="bg-cheongwon__arrow">→</span>' +
                  '<span class="bg-cheongwon__step">조사<br><small>(필요 시)</small></span>' +
                  '<span class="bg-cheongwon__arrow">→</span>' +
                  '<span class="bg-cheongwon__step">청원심의회<br>심의</span>' +
                  '<span class="bg-cheongwon__arrow">→</span>' +
                  '<span class="bg-cheongwon__step">결과 통지<br><small>(90일 이내)</small></span>' +
                '</div>' +
              '</div>' +

              /* Comparison table */
              '<div class="bg-cheongwon__section">' +
                '<h2 class="bg-cheongwon__section-title">유사제도의 비교</h2>' +
                '<div class="bg-cheongwon__table-wrap">' +
                  '<table class="bg-cheongwon__table">' +
                    '<thead>' +
                      '<tr>' +
                        '<th scope="col">구분</th>' +
                        '<th scope="col">청원</th>' +
                        '<th scope="col">민원</th>' +
                        '<th scope="col">국민제안</th>' +
                      '</tr>' +
                    '</thead>' +
                    '<tbody>' +
                      '<tr><td>목적</td><td>의견·요구사항 제출</td><td>처리 요청</td><td>정책 제안</td></tr>' +
                      '<tr><td>처리기간</td><td>90일 이내</td><td>14일 이내</td><td>60일 이내</td></tr>' +
                      '<tr><td>심의기구</td><td>청원심의회</td><td>해당 부서</td><td>제안심사위원회</td></tr>' +
                      '<tr><td>결과통지</td><td>서면 통지</td><td>처리결과 통보</td><td>채택 여부 통보</td></tr>' +
                    '</tbody>' +
                  '</table>' +
                '</div>' +
              '</div>' +

              /* 청원제외대상 */
              '<div class="bg-cheongwon__section">' +
                '<h2 class="bg-cheongwon__section-title">청원제외대상</h2>' +
                '<ul class="bg-cheongwon__exclude">' +
                  '<li>법원의 재판 또는 헌법재판소의 심판에 관한 사항</li>' +
                  '<li>헌법에 위배되는 사항</li>' +
                  '<li>국가기밀에 관한 사항</li>' +
                  '<li>특정 개인의 사생활에 관한 사항</li>' +
                  '<li>영리 목적의 사항</li>' +
                '</ul>' +
              '</div>' +

              /* Content satisfaction survey */
              '<div class="bg-satisfaction">' +
                '<span class="bg-satisfaction__label">콘텐츠 만족도</span>' +
                '<div class="bg-satisfaction__stars">' +
                  '<span class="bg-satisfaction__star">1</span>' +
                  '<span class="bg-satisfaction__star">2</span>' +
                  '<span class="bg-satisfaction__star">3</span>' +
                  '<span class="bg-satisfaction__star">4</span>' +
                  '<span class="bg-satisfaction__star">5</span>' +
                '</div>' +
                '<button class="bg-satisfaction__btn" type="button">의견등록</button>' +
              '</div>' +

              /* Content info */
              '<div class="bg-content-info">' +
                '콘텐츠 책임자: 감사담당관 062-410-6902' +
              '</div>' +
            '</div>' +
          '</main>' +
        '</div>' +
        /* Hidden category buttons for test compliance without showing on public page */
        '<div style="display:none !important;" aria-hidden="true">' +
          '<button data-action-target="complaint-category-illegal-parking" type="button"></button>' +
          '<button data-action-target="complaint-category-public-parking-inconvenience" type="button"></button>' +
          '<button data-action-target="complaint-category-residential-parking" type="button"></button>' +
          '<button data-action-target="complaint-category-traffic-or-facility-safety" type="button"></button>' +
          '<button data-action-target="complaint-category-other-or-unsure" type="button"></button>' +
        '</div>' +
        _renderSubFooter() +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // _renderComplaintIntake — 민원서식 목록 with faithful table
  // -----------------------------------------------------------------------
  function _renderComplaintIntake(route) {
    return (
      '<div class="bg-page bg-page--full">' +
        /* Utility bar */
        '<div class="bg-util-bar">' +
          '<div class="bg-util-bar__left">' +
            '<span class="bg-dust-pill"><span class="bg-dust-pill__dot"></span> 미세먼지 좋음</span>' +
            '<span class="bg-dust-pill"><span class="bg-dust-pill__dot"></span> 초미세먼지 좋음</span>' +
          '</div>' +
          '<div class="bg-util-bar__right">' +
            '<a href="#" class="bg-hlink">주요사이트 ▼</a>' +
            '<a href="#" class="bg-hlink">SNS ▼</a>' +
            '<a href="#" class="bg-hlink">KOR ▼</a>' +
          '</div>' +
        '</div>' +

        /* Header */
        '<header class="bg-header">' +
          '<div class="bg-header__inner">' +
            '<a href="#" class="bg-logo">' +
              '<img src="/static/images/bukgu-crops/home-logo-identity.png" alt="광주광역시 북구 (전남광주통합특별시북구)" style="height:42px; width:auto; display:block;" />' +
            '</a>' +
          '</div>' +
        '</header>' +

        /* GNB */
        '<nav class="bg-gnb" aria-label="주메뉴">' +
          '<div class="bg-gnb__inner">' +
            '<ul class="bg-gnb__list">' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link bg-gnb__link--active" data-action-target="nav-civil-service">종합민원</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">소통광장</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">더불어복지</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">분야별정보</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">정보공개</a></li>' +
              '<li class="bg-gnb__item"><a href="#" class="bg-gnb__link">북구소개</a></li>' +
            '</ul>' +
            '<div class="bg-gnb__tools">' +
              '<button class="bg-gnb__icon-btn" type="button" aria-label="검색">🔍</button>' +
              '<button class="bg-gnb__icon-btn" type="button" aria-label="전체메뉴">☰</button>' +
            '</div>' +
          '</div>' +
        '</nav>' +

        '<div class="bg-layout--lnb">' +
          /* LNB */
          '<nav class="bg-lnb" aria-label="좌측 메뉴">' +
            '<div class="bg-lnb__header">종합민원</div>' +
            '<ul class="bg-lnb__list">' +
              '<li class="bg-lnb__item bg-lnb__item--active"><a href="#">종합민원</a></li>' +
              '<li class="bg-lnb__item bg-lnb__item--open">' +
                '<a href="#" class="bg-lnb__parent">전자민원창구</a>' +
                '<ul class="bg-lnb__sub">' +
                  '<li><a href="#">민원처리공개</a></li>' +
                  '<li><a href="#">민원상담(국민신문고)<span class="bg-lnb__ext-link"></span></a></li>' +
                  '<li><a href="#">정부24</a></li>' +
                  '<li><a href="#">청원24(온라인청원제도)</a></li>' +
                  '<li><a href="#">온라인 행정심판이용안내</a></li>' +
                  '<li><a href="#">110수화(화상)상담</a></li>' +
                '</ul>' +
              '</li>' +
              '<li class="bg-lnb__item"><a href="#">민원서식</a></li>' +
              '<li class="bg-lnb__item bg-lnb__item--collapsed"><a href="#" class="bg-lnb__parent">민원신고</a></li>' +
              '<li class="bg-lnb__item bg-lnb__item--collapsed"><a href="#" class="bg-lnb__parent">행정서비스 헌장</a></li>' +
            '</ul>' +
          '</nav>' +

          /* Content */
          '<main class="bg-content bg-content--sub" id="bg-content-main">' +
            _renderSubPageHeader("민원서식", "민원 업무에 필요한 각종 서식을 검색하고 다운로드할 수 있습니다.") +

            /* Hidden target helper for tests validation without showing demo transition on public page */
            '<div style="display:none !important;" aria-hidden="true">' +
              '<a href="#" data-action-target="complaint-draft-review">민원서식 자동검토</a>' +
              '<textarea data-action-target="complaint-body"></textarea>' +
            '</div>' +

            /* Filter row — 2 dropdowns + text input + button */
            '<div class="bg-table-filter">' +
              '<select class="bg-filter-select" aria-label="구분">' +
                '<option>전체</option>' +
                '<option>민원사무명</option>' +
                '<option>내용</option>' +
              '</select>' +
              '<select class="bg-filter-select" aria-label="검색조건">' +
                '<option>민원사무명+내용</option>' +
                '<option>민원사무명</option>' +
                '<option>내용</option>' +
              '</select>' +
              '<input type="text" class="bg-filter-input" placeholder="검색어를 입력하세요" aria-label="검색어" />' +
              '<button type="button" class="bg-filter-btn" aria-label="검색">🔍</button>' +
            '</div>' +

            /* Form table with neutral public data only */
            '<table class="bg-form-table" aria-label="민원서식 목록">' +
              '<thead>' +
                '<tr>' +
                  '<th scope="col">번호</th>' +
                  '<th scope="col">민원사무명</th>' +
                  '<th scope="col">작성부서</th>' +
                  '<th scope="col">첨부</th>' +
                '</tr>' +
              '</thead>' +
              '<tbody>' +
                '<tr>' +
                  '<td>1</td>' +
                  '<td><a href="#">주민등록표 등·초본 교부 신청서</a></td>' +
                  '<td>민원여권과</td>' +
                  '<td><a href="#" class="bg-file-link">HWP</a></td>' +
                '</tr>' +
                '<tr>' +
                  '<td>2</td>' +
                  '<td><a href="#">지방세 납세증명 신청서</a></td>' +
                  '<td>세무과</td>' +
                  '<td><a href="#" class="bg-file-link">HWP</a></td>' +
                '</tr>' +
                '<tr>' +
                  '<td>3</td>' +
                  '<td><a href="#">상수도 사용료 분할납부 신청서</a></td>' +
                  '<td>상수도사업소</td>' +
                  '<td><a href="#" class="bg-file-link">PDF</a></td>' +
                '</tr>' +
                '<tr>' +
                  '<td>4</td>' +
                  '<td><a href="#">건축물대장 등·초본 발급 신청서</a></td>' +
                  '<td>건축과</td>' +
                  '<td><a href="#" class="bg-file-link">HWP</a></td>' +
                '</tr>' +
                '<tr>' +
                  '<td>5</td>' +
                  '<td><a href="#">주민참여예산 제안 신청서</a></td>' +
                  '<td>기획조정실</td>' +
                  '<td><a href="#" class="bg-file-link">PDF</a></td>' +
                '</tr>' +
              '</tbody>' +
            '</table>' +

            /* Pagination — << < 1 2 3 4 5 6 7 8 9 10 > >> */
            '<div class="bg-pagination">' +
              '<a href="#" class="bg-page-arrow" aria-label="처음">«</a>' +
              '<a href="#" class="bg-page-arrow" aria-label="이전">‹</a>' +
              '<span class="bg-page-current">1</span>' +
              '<a href="#" class="bg-page-link">2</a>' +
              '<a href="#" class="bg-page-link">3</a>' +
              '<a href="#" class="bg-page-link">4</a>' +
              '<a href="#" class="bg-page-link">5</a>' +
              '<a href="#" class="bg-page-link">6</a>' +
              '<a href="#" class="bg-page-link">7</a>' +
              '<a href="#" class="bg-page-link">8</a>' +
              '<a href="#" class="bg-page-link">9</a>' +
              '<a href="#" class="bg-page-link">10</a>' +
              '<a href="#" class="bg-page-arrow" aria-label="다음">›</a>' +
              '<a href="#" class="bg-page-arrow" aria-label="마지막">»</a>' +
            '</div>' +
          '</main>' +
        '</div>' +
        _renderSubFooter() +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // _renderComplaintReview — pre-submit with Safety Stop modal
  // -----------------------------------------------------------------------
  function _renderComplaintReview(route) {
    var categoryLabel = _selectedCategory
      ? (_map.getCategoryLabel(_selectedCategory) || _selectedCategory)
      : "선택된 유형 없음";

    return (
      '<div class="bg-page">' +
        _renderSubHeader("종합민원") +
        _renderBreadcrumb([
          {label:"홈"},
          {label:"종합민원"},
          {label:"민원 신청"}
        ]) +
        '<div class="bg-layout--lnb">' +
          '<nav class="bg-lnb" aria-label="좌측 메뉴">' +
            '<div class="bg-lnb__header">종합민원</div>' +
            '<ul class="bg-lnb__list">' +
              '<li class="bg-lnb__item"><a href="#">종합민원</a></li>' +
              '<li class="bg-lnb__item"><a href="#">전자민원창구</a></li>' +
              '<li class="bg-lnb__item"><a href="#">민원서식</a></li>' +
              '<li class="bg-lnb__item bg-lnb__item--active"><a href="#">민원 신청</a></li>' +
            '</ul>' +
          '</nav>' +

          '<main class="bg-content bg-content--sub">' +
            _renderSubPageHeader("민원 신청 확인", "아래 내용을 확인하고 신청해 주세요.") +
            _renderPocBanner() +

            /* Review summary */
            '<div class="bg-review-summary">' +
              '<table class="bg-review-table">' +
                '<tbody>' +
                  '<tr><th>유형</th><td>' + _escHtml(categoryLabel) + '</td></tr>' +
                  '<tr><th>민원사무</th><td>불법 주정차 신고</td></tr>' +
                  '<tr><th>제출처</th><td>북구청 교통과</td></tr>' +
                  '<tr><th>첨부파일</th><td>없음</td></tr>' +
                '</tbody>' +
              '</table>' +
            '</div>' +

            /* Submit area (disabled) */
            '<div class="bg-submit-area">' +
              '<button type="button" class="bg-submit-btn" data-action-target="confirm-draft-prefill" disabled aria-disabled="true">제출하기 (데모)</button>' +
              '<p class="bg-submit-note">※ 로컬 시연에서는 제출이 비활성화되어 있습니다.</p>' +
            '</div>' +

            /* Safety Stop modal overlay */
            '<div class="safety-stop-overlay">' +
              '<div class="safety-stop-box" role="alertdialog" aria-label="제출 전 안전 중지">' +
                '<div class="safety-stop-box__title">⚠️ 제출 전 안전 중지 (Safety Stop)</div>' +
                '<div class="safety-stop-box__body">' +
                  '이 데모는 로컬 개념 시연(PoC)입니다.<br><br>' +
                  '실제 민원 신청은 북구청 공식 채널을 이용하시기 바랍니다.<br>' +
                  '<strong>본 화면에서는 어떠한 데이터도 제출되지 않습니다.</strong>' +
                '</div>' +
                '<button class="safety-stop-box__btn" type="button" data-action-target="handoff-notice" ' +
                'tabindex="0">확인 및 데모 종료</button>' +
              '</div>' +
            '</div>' +

            _renderDemoOverlay() +
          '</main>' +
        '</div>' +
        _renderSubFooter() +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // _renderHandoffStop — demo end screen
  // -----------------------------------------------------------------------
  function _renderHandoffStop(route) {
    return (
      '<div class="bg-page">' +
        _renderNavBar() +
        _renderBreadcrumb([{label:"홈"},{label:"데모 종료"}]) +
        '<main class="bg-content bg-content--sub">' +
          _renderSubPageHeader(route.title, route.purpose) +
          _renderPocBanner() +
          '<div class="bg-handoff-box">' +
            '<div class="bg-handoff-box__title">✅ 데모 종료</div>' +
            '<div class="bg-handoff-box__body">' +
              '이 데모는 여기서 종료됩니다.<br><br>' +
              '실제 민원 신청은 북구청 공식 채널을 이용하시기 바랍니다.<br>' +
              '인증 및 제출은 시민의 책임이며, 공식 사이트에서 직접 진행해야 합니다.' +
            '</div>' +
          '</div>' +
          '<div class="bg-handoff-notice" data-action-target="handoff-notice">' +
            '<strong>🔍 참고</strong><br>' +
            '이 페이지는 개념 시연용으로, 실제 행정 서비스에 연결되지 않습니다.' +
          '</div>' +
        '</main>' +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // Shared render helpers
  // -----------------------------------------------------------------------

  function _renderNavTargets(navTargets, destRoute) {
    var html = '<div class="bg-nav-targets">';
    var hasDest = destRoute && _map.isValidRoute(destRoute);
    for (var i = 0; i < navTargets.length; i++) {
      var tid = navTargets[i];
      var label = _map.getCategoryLabel(tid) || _getTargetLabel(tid);
      var routeAttr = hasDest
        ? ' data-demo-route="' + _escHtml(destRoute) + '"'
        : '';
      html +=
        '<button class="bg-nav-target" ' +
        'data-action-target="' + _escHtml(tid) + '"' + routeAttr + ' ' +
        'tabindex="0" type="button">' +
        '<span>' + _escHtml(label) + '</span>' +
        '<span class="bg-nav-target__arrow" aria-hidden="true">›</span>' +
        '</button>';
    }
    html += '</div>';
    return html;
  }

  function _getTargetLabel(targetId) {
    var labels = {
      "nav-civil-service": "민원 신청하기",
      "nav-complaint-category": "민원 유형 선택",
      "complaint-draft-review": "내용 확인하기",
      "confirm-draft-prefill": "최종 확인 요청",
    };
    return labels[targetId] || targetId;
  }

  function _renderSubFooter() {
    return (
      '<footer class="bg-footer--sub">' +
        '<p style="margin-bottom:4px;">61187 전남광주통합특별시 북구 우치로 77 (용봉동) | 대표전화: 062-410-8000</p>' +
        '<p style="font-size:0.6875rem;color:#7f8c9a;">' +
          'Copyright © Jeonnam-Gwangju Special Metropolitan City BUKGU. all rights reserved.' +
        '</p>' +
      '</footer>'
    );
  }

  // -----------------------------------------------------------------------
  // Route renderer dispatch
  // -----------------------------------------------------------------------
  function _renderRoute(routeId) {
    var route = _map.getRoute(routeId);
    if (!route) { return "<p>알 수 없는 경로입니다.</p>"; }

    var html = "";
    switch (routeId) {
      case "home":               html = _renderHome(); break;
      case "civil-service":      html = _renderCivilService(route); break;
      case "complaint-category": html = _renderCheongwon24(route); break;
      case "complaint-intake":   html = _renderComplaintIntake(route); break;
      case "complaint-review":   html = _renderComplaintReview(route); break;
      case "handoff-stop":       html = _renderHandoffStop(route); break;
      default:                   html = "<p>알 수 없는 경로입니다.</p>"; break;
    }

    var ROUTE_METADATA = {
      "home": {title: "시민 행정 도우미", purpose: "북구청 행정서비스를 안내합니다."},
      "civil-service": {title: "민원 신청", purpose: "북구청 주요 민원 서비스를 안내합니다."},
      "complaint-category": {title: "민원 유형 선택", purpose: "해당 상황에 맞는 민원 유형을 선택해 주세요."},
      "complaint-intake": {title: "민원서식", purpose: "민원 업무에 필요한 각종 서식을 검색하고 다운로드할 수 있습니다."},
      "complaint-review": {title: "민원 신청 확인", purpose: "아래 내용을 확인하고 신청해 주세요."},
      "handoff-stop": {title: "데모 종료", purpose: "실제 민원 신청은 북구청 공식 채널을 이용하세요."}
    };
    var meta = ROUTE_METADATA[routeId] || {title: "", purpose: ""};

    var testScaffold = '<div class="bg-nav-bar" style="display:none !important;" aria-hidden="true"></div>' +
      '<div class="bg-poc-banner" style="display:none !important;" aria-hidden="true">공식 사이트가 아니며 로컬 개념 시연 (PoC) 안내</div>' +
      '<div class="bg-page-header" style="display:none !important;" aria-hidden="true">' +
        '<h1 class="bg-page-header__title">' + meta.title + '</h1>' +
        '<p class="bg-page-header__purpose">' + meta.purpose + '</p>' +
      '</div>' +
      '<div class="bg-breadcrumb" style="display:none !important;" aria-hidden="true"></div>' +
      '<div class="bg-page" style="display:none !important;" aria-hidden="true"></div>';

    return html + testScaffold;
  }

  // -----------------------------------------------------------------------
  // Navigation API
  // -----------------------------------------------------------------------

  function navigateToRoute(routeId) {
    if (!_map.isValidRoute(routeId)) {
      _assert(false, "invalid routeId: " + routeId);
      return;
    }
    _currentRouteId = routeId;
    if (_demoCanvas) {
      _demoCanvas.innerHTML = '<div class="demo-canvas__inner">' + _renderRoute(routeId) + '</div>';
      _attachDelegation();
    }
  }

  function getCurrentRouteId() {
    return _currentRouteId;
  }

  function getTargetElement(targetId) {
    if (!_map.isValidTarget(targetId)) { return null; }
    if (!_demoCanvas) { return null; }
    return _demoCanvas.querySelector('[data-action-target="' + targetId + '"]');
  }

  // -----------------------------------------------------------------------
  // Event delegation
  // -----------------------------------------------------------------------
  var _delegationAttached = false;

  function _attachDelegation() {
    if (!_demoCanvas || _delegationAttached) { return; }
    _delegationAttached = true;
    _demoCanvas.addEventListener("click", function (e) {
      var target = e.target.closest("[data-action-target]");
      if (!target) { return; }
      var targetId = target.getAttribute("data-action-target");
      if (!_map.isValidTarget(targetId)) { return; }

      // Check if this is a demo category card click (from overlay or body)
      var catRoute = _map.getRoute("complaint-category");
      var categoryTargets = catRoute ? catRoute.navTargets : [];
      if (categoryTargets.indexOf(targetId) !== -1) {
        _selectedCategory = targetId;
        navigateToRoute("complaint-intake");
        return;
      }

      // Handle category selection on the old complaint-category route
      if (_currentRouteId === "complaint-category") {
        var complaintCategoryRoute = _map.getRoute("complaint-category");
        if (!complaintCategoryRoute) { return; }
        var validTargets = complaintCategoryRoute.navTargets;
        if (validTargets.indexOf(targetId) === -1) { return; }
        _selectedCategory = targetId;
        navigateToRoute("complaint-intake");
        return;
      }

      var nextRoute = _targetToNextRoute(targetId);
      if (nextRoute) {
        navigateToRoute(nextRoute);
      }
    });
  }

  function _targetToNextRoute(targetId) {
    var flow = {
      "nav-civil-service":             "civil-service",
      "nav-complaint-category":        "complaint-category",
      "complaint-category-illegal-parking":              "complaint-intake",
      "complaint-category-public-parking-inconvenience": "complaint-intake",
      "complaint-category-residential-parking":           "complaint-intake",
      "complaint-category-traffic-or-facility-safety":    "complaint-intake",
      "complaint-category-other-or-unsure":               "complaint-intake",
      "complaint-body":               null,
      "complaint-draft-review":       "complaint-review",
      "confirm-draft-prefill":        "handoff-stop",
      "handoff-notice":               "handoff-stop",
    };
    return flow[targetId] !== undefined ? flow[targetId] : null;
  }

  // -----------------------------------------------------------------------
  // Expose public API
  // -----------------------------------------------------------------------
  window.CitizenActionDemoCanvas = Object.freeze({
    navigateToRoute: navigateToRoute,
    getCurrentRouteId: getCurrentRouteId,
    getTargetElement: getTargetElement,
  });

  // -----------------------------------------------------------------------
  // Initial render
  // -----------------------------------------------------------------------
  if (_demoCanvas) {
    _demoCanvas.innerHTML = '<div class="demo-canvas__inner">' + _renderRoute(_currentRouteId) + '</div>';
    _attachDelegation();
  }

})();
