/**
 * citizen-action-demo-canvas.js
 * Local route-rendered canvas — semantic HTML/CSS reconstruction of Buk-gu Office.
 * Uses real capture screenshots as reference only (no full-page img overlay).
 * No fetch, no persistence, no external URLs, no runner/provider.
 */

(function () {
  "use strict";

  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------
  var _currentRouteId = "home";
  var _selectedCategory = null;

  // -----------------------------------------------------------------------
  // DOM references
  // -----------------------------------------------------------------------
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
  // Route renderers — semantic Buk-gu Office HTML reconstruction
  // Reference: actual screenshots in src/web/static/images/bukgu_*.png
  // -----------------------------------------------------------------------

  /** Home — Buk-gu Office main portal with GNB, search, quick services */
  function _renderHome() {
    return (
      '<div class="bg-page">' +
        /* skip nav */
        '<div class="bg-skip"><a href="#bg-content">본문으로 바로가기</a></div>' +

        /* header: logo + weather + tools */
        '<header class="bg-header">' +
          '<div class="bg-header__inner">' +
            '<h1 class="bg-logo">' +
              '<a href="#">광주광역시 북구</a>' +
            '</h1>' +
            '<div class="bg-header__tools">' +
              '<span class="bg-weather">구름많음 24℃</span>' +
              '<div class="bg-header-links">' +
                '<a href="#" class="bg-hlink">주요사이트▼</a>' +
                '<a href="#" class="bg-hlink">SNS▼</a>' +
                '<a href="#" class="bg-hlink">KOR▼</a>' +
              '</div>' +
              '<button class="bg-search-btn" type="button">통합검색</button>' +
              '<button class="bg-menu-btn" type="button">전체메뉴</button>' +
            '</div>' +
          '</div>' +
        '</header>' +

        /* GNB */
        '<nav class="bg-gnb" aria-label="주메뉴">' +
          '<ul>' +
            '<li><a href="#" data-action-target="nav-civil-service">종합민원</a></li>' +
            '<li><a href="#">소통광장</a></li>' +
            '<li><a href="#">더불어복지</a></li>' +
            '<li><a href="#">분야별정보</a></li>' +
            '<li><a href="#">정보공개</a></li>' +
            '<li><a href="#">북구소개</a></li>' +
          '</ul>' +
        '</nav>' +

        /* main content */
        '<main id="bg-content" class="bg-content">' +

          /* search */
          '<div class="bg-search-section">' +
            '<div class="bg-search-form">' +
              '<input type="text" class="bg-search-input" placeholder="검색어 입력" aria-label="통합검색" />' +
              '<button class="bg-search-submit" type="button">검색</button>' +
            '</div>' +
            '<div class="bg-tags">' +
              '<a href="#" class="bg-tag">#공동주택과</a>' +
              '<a href="#" class="bg-tag">#위생과</a>' +
              '<a href="#" class="bg-tag">#폐기물</a>' +
              '<a href="#" class="bg-tag">#부끄머니</a>' +
            '</div>' +
          '</div>' +

          /* main visual */
          '<div class="bg-main-visual">' +
            '<div class="bg-welcome-card">' +
              '<h2 class="bg-welcome-title">따뜻한 북구를<br>만들겠습니다.</h2>' +
              '<p class="bg-welcome-mayor">북구청장 신수정 입니다.</p>' +
              '<div class="bg-welcome-actions">' +
                '<a href="#" class="bg-btn bg-btn--primary">열린구청장실 바로가기</a>' +
                '<a href="#" class="bg-btn bg-btn--outline">매니페스토 바로가기</a>' +
              '</div>' +
            '</div>' +
            '<div class="bg-slider">' +
              '<div class="bg-slider-item">' +
                '<div class="bg-slider-placeholder">' +
                  '<strong>2025년 기준 경제총조사</strong><br>' +
                  '2026. 6. 1. ~ 7. 22.' +
                '</div>' +
              '</div>' +
              '<div class="bg-slider-controls">' +
                '<button type="button" class="bg-slider-btn">◀ 이전</button>' +
                '<span class="bg-slider-page"><strong>1</strong> / 5</span>' +
                '<button type="button" class="bg-slider-btn">다음 ▶</button>' +
              '</div>' +
            '</div>' +
          '</div>' +

          /* quick services */
          '<div class="bg-quick-services">' +
            '<a href="#" class="bg-quick-item">업무검색</a>' +
            '<a href="#" class="bg-quick-item">청사안내</a>' +
            '<a href="#" class="bg-quick-item">고향사랑기부제</a>' +
            '<a href="#" class="bg-quick-item">부끄머니</a>' +
            '<a href="#" class="bg-quick-item">통합예약</a>' +
            '<a href="#" class="bg-quick-item">일반민원 대기현황</a>' +
          '</div>' +

          /* info grid — two equal columns */
          '<div class="bg-info-grid">' +
            /* left: 공지사항 */
            '<section class="bg-card bg-card--notice">' +
              '<h3 class="bg-card-title"><a href="#">공지사항</a></h3>' +
              '<ul class="bg-card-list">' +
                '<li><a href="#">2026.07.03 2026년 국적취득비용(수수료) 지원사업 진행 안내</a></li>' +
                '<li><a href="#">2026.07.03 2026년 축산물이력제 식육포장처리업소 이력번호 표시 지원사업 안내</a></li>' +
                '<li><a href="#">2026.07.03 전남광주통합특별시 북구 소속 공무원 사칭 피해 주의 안내</a></li>' +
              '</ul>' +
              '<a href="#" class="bg-more">더보기</a>' +
            '</section>' +
            /* right: 주요사이트 */
            '<section class="bg-card bg-card--sites">' +
              '<h3 class="bg-card-title">주요사이트</h3>' +
              '<div class="bg-site-items">' +
                '<a href="#" class="bg-site-item">통계정보</a>' +
                '<a href="#" class="bg-site-item">평생학습관</a>' +
                '<a href="#" class="bg-site-item">청년센터</a>' +
                '<a href="#" class="bg-site-item">문화센터</a>' +
                '<a href="#" class="bg-site-item">공원시설 예약</a>' +
                '<a href="#" class="bg-site-item">체육시설 예약</a>' +
              '</div>' +
            '</section>' +
          '</div>' +

          /* field info */
          '<div class="bg-field-info">' +
            '<h3 class="bg-field-heading">분야별 정보</h3>' +
            '<div class="bg-field-tabs">' +
              '<button type="button" class="bg-field-tab bg-field-tab--active">구민</button>' +
              '<button type="button" class="bg-field-tab">기업/경제</button>' +
              '<button type="button" class="bg-field-tab">관광</button>' +
            '</div>' +
            '<ul class="bg-field-links">' +
              '<li><a href="#">행정조직도</a></li>' +
              '<li><a href="#">주정차단속문자알림</a></li>' +
              '<li><a href="#">여권 발급</a></li>' +
              '<li><a href="#">보건증 발급</a></li>' +
              '<li><a href="#">대형 폐기물 처리</a></li>' +
              '<li><a href="#" data-action-target="nav-civil-service">온라인 민원발급(정부24)</a></li>' +
              '<li><a href="#">洞운영프로그램안내</a></li>' +
              '<li><a href="#">소화기 사용법</a></li>' +
              '<li><a href="#">정보화교육</a></li>' +
              '<li><a href="#">공공데이터</a></li>' +
            '</ul>' +
          '</div>' +

        '</main>' +

        /* footer */
        '<footer class="bg-footer">' +
          '<div class="bg-footer-nav">' +
            '<a href="#">부서안내</a>' +
            '<a href="#">동 행정복지센터</a>' +
            '<a href="#">주요 사이트</a>' +
            '<a href="#">유관기관</a>' +
          '</div>' +
          '<div class="bg-footer-body">' +
            '<div class="bg-footer-info">' +
              '<p>61187 전남광주통합특별시 북구 우치로 77 (용봉동) | 대표전화: 062-410-8000</p>' +
              '<p>운영시간: 평일 09:00~18:00 (점심시간 12:00~13:00) ※ 주말, 공휴일 휴무</p>' +
            '</div>' +
          '</div>' +
          '<div class="bg-footer-legal">' +
            '<a href="#">누리집 이용안내</a>' +
            '<span>|</span>' +
            '<a href="#">개인정보처리방침</a>' +
            '<span>|</span>' +
            '<a href="#">저작권 보호정책</a>' +
            '<span>|</span>' +
            '<a href="#">이메일무단수집거부</a>' +
            '<span>|</span>' +
            '<a href="#">영상정보처리기기 운영·관리 방침</a>' +
          '</div>' +
          '<div class="bg-footer-copy">' +
            '<p>Copyright © Jeonnam-Gwangju Special Metropolitan City BUKGU. all rights reserved.</p>' +
          '</div>' +
        '</footer>' +
      '</div>'
    );
  }

  /** Civil service landing — intermediate route between home and category */
  function _renderCivilService(route) {
    return (
      '<div class="bg-page">' +
        _renderSubHeader("민원 신청") +
        _renderBreadcrumb([{label:"홈"},{label:route.breadcrumbLabel}]) +
        '<main class="bg-content bg-content--sub">' +
          _renderSubPageHeader(route.title, route.purpose) +
          _renderPocBanner() +
          '<p class="bg-guide-text">아래 유익한 민원 서비스를 선택하여 절차를 안내받으세요.</p>' +
          _renderNavTargets(route.navTargets, "complaint-category") +
        '</main>' +
        _renderSubFooter() +
      '</div>'
    );
  }

  /** Complaint category — LNB + category cards */
  function _renderComplaintCategory(route) {
    var categoryHtml = "";
    for (var i = 0; i < route.navTargets.length; i++) {
      var tid = route.navTargets[i];
      var label = _map.getCategoryLabel(tid) || tid;
      categoryHtml +=
        '<button class="bg-category-card" ' +
        'data-action-target="' + _escHtml(tid) + '" ' +
        'tabindex="0" type="button">' +
        '<span class="bg-category-card__icon">📋</span>' +
        '<span class="bg-category-card__label">' + _escHtml(label) + '</span>' +
        '<span class="bg-category-card__arrow" aria-hidden="true">›</span>' +
        '</button>';
    }

    return (
      '<div class="bg-page">' +
        _renderSubHeader("종합민원") +
        _renderBreadcrumb([{label:"홈"},{label:"종합민원"},{label:"전자민원창구"}]) +
        '<div class="bg-layout bg-layout--lnb">' +
          /* LNB — matches actual site structure */
          '<nav class="bg-lnb" aria-label="좌측 메뉴">' +
            '<div class="bg-lnb__header">종합민원</div>' +
            '<ul class="bg-lnb__list">' +
              '<li class="bg-lnb__item"><a href="#">종합민원</a></li>' +
              '<li class="bg-lnb__item bg-lnb__item--open">' +
                '<a href="#" class="bg-lnb__parent">전자민원창구</a>' +
                '<ul class="bg-lnb__sub">' +
                  '<li><a href="#">민원처리공개</a></li>' +
                  '<li><a href="#">민원상담(국민신문고)</a></li>' +
                  '<li><a href="#">정부24</a></li>' +
                  '<li><a href="#">청원24(온라인청원제도)</a></li>' +
                  '<li><a href="#">온라인 행정심판이용안내</a></li>' +
                  '<li><a href="#">110수화(화상)상담</a></li>' +
                '</ul>' +
              '</li>' +
              '<li class="bg-lnb__item"><a href="#">민원신고</a></li>' +
              '<li class="bg-lnb__item"><a href="#">행정서비스 헌장</a></li>' +
            '</ul>' +
          '</nav>' +

          /* Content */
          '<main class="bg-content bg-content--sub">' +
            _renderSubPageHeader(route.title, route.purpose) +
            _renderPocBanner() +
            '<p class="bg-guide-text">해당 상황에 맞는 민원 유형을 선택해 주세요.</p>' +
            '<div class="bg-category-cards">' +
              _renderCategoryCards(route.navTargets) +
            '</div>' +
          '</main>' +
        '</div>' +
        _renderSubFooter() +
      '</div>'
    );
  }

  /** Complaint intake — 민원서식 목록 reconstruction with table */
  function _renderComplaintIntake(route) {
    return (
      '<div class="bg-page">' +
        _renderSubHeader("종합민원") +
        _renderBreadcrumb([{label:"홈"},{label:"종합민원"},{label:"민원서식"}]) +
        '<div class="bg-layout bg-layout--lnb">' +
          /* LNB */
          '<nav class="bg-lnb" aria-label="좌측 메뉴">' +
            '<div class="bg-lnb__header">종합민원</div>' +
            '<ul class="bg-lnb__list">' +
              '<li class="bg-lnb__item"><a href="#">종합민원</a></li>' +
              '<li class="bg-lnb__item"><a href="#">전자민원창구</a></li>' +
              '<li class="bg-lnb__item bg-lnb__item--active">' +
                '<a href="#">민원서식</a></li>' +
              '<li class="bg-lnb__item"><a href="#">민원신고</a></li>' +
            '</ul>' +
          '</nav>' +

          /* Content: form list table */
          '<main class="bg-content bg-content--sub">' +
            _renderSubPageHeader("민원서식", "민원 업무에 필요한 각종 서식을 검색하고 다운로드할 수 있습니다.") +
            _renderPocBanner() +

            /* search filter */
            '<div class="bg-table-filter">' +
              '<select class="bg-filter-select" aria-label="검색 구분">' +
                '<option>전체</option>' +
                '<option>민원사무명</option>' +
                '<option>내용</option>' +
              '</select>' +
              '<input type="text" class="bg-filter-input" placeholder="검색어를 입력하세요" aria-label="검색어" />' +
              '<button type="button" class="bg-filter-btn">검색</button>' +
            '</div>' +

            /* form table */
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
                  '<td><a href="#" data-action-target="complaint-draft-review">불법 주정차 신고서</a></td>' +
                  '<td>교통과</td>' +
                  '<td><a href="#" class="bg-file-link">HWP</a></td>' +
                '</tr>' +
                '<tr>' +
                  '<td>2</td>' +
                  '<td><a href="#">공용주차장 불편 신고서</a></td>' +
                  '<td>교통과</td>' +
                  '<td><a href="#" class="bg-file-link">HWP</a></td>' +
                '</tr>' +
                '<tr>' +
                  '<td>3</td>' +
                  '<td><a href="#">공동주택 주차 관련 민원</a></td>' +
                  '<td>건축과</td>' +
                  '<td><a href="#" class="bg-file-link">PDF</a></td>' +
                '</tr>' +
                '<tr>' +
                  '<td>4</td>' +
                  '<td><a href="#">교통·시설 안전 신고서</a></td>' +
                  '<td>안전총괄과</td>' +
                  '<td><a href="#" class="bg-file-link">HWP</a></td>' +
                '</tr>' +
                '<tr>' +
                  '<td>5</td>' +
                  '<td><a href="#">기타 민원 신청서</a></td>' +
                  '<td>민원여권과</td>' +
                  '<td><a href="#" class="bg-file-link">PDF</a></td>' +
                '</tr>' +
              '</tbody>' +
            '</table>' +

            /* pagination */
            '<div class="bg-pagination">' +
              '<span class="bg-page-current">1</span>' +
              '<a href="#" class="bg-page-link">2</a>' +
              '<a href="#" class="bg-page-link">3</a>' +
              '<a href="#" class="bg-page-link">다음</a>' +
            '</div>' +
          '</main>' +
        '</div>' +
        _renderSubFooter() +
      '</div>'
    );
  }

  /** Complaint review — pre-submit page with Safety Stop modal */
  function _renderComplaintReview(route) {
    var categoryLabel = _selectedCategory
      ? (_map.getCategoryLabel(_selectedCategory) || _selectedCategory)
      : "선택된 유형 없음";

    return (
      '<div class="bg-page">' +
        _renderSubHeader("종합민원") +
        _renderBreadcrumb([{label:"홈"},{label:"종합민원"},{label:"민원 신청"}]) +
        '<div class="bg-layout bg-layout--lnb">' +
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

            /* review summary */
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

            /* submit area (disabled for demo) */
            '<div class="bg-submit-area">' +
              '<button type="button" class="bg-submit-btn" disabled aria-disabled="true">제출하기 (데모)</button>' +
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
          '</main>' +
        '</div>' +
        _renderSubFooter() +
      '</div>'
    );
  }

  /** Handoff stop — demo end screen */
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

  /** Sub-page header reused across route pages */
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

  function _renderCategoryCards(navTargets) {
    var html = '';
    for (var i = 0; i < navTargets.length; i++) {
      var tid = navTargets[i];
      var label = _map.getCategoryLabel(tid) || tid;
      html +=
        '<button class="bg-category-card" ' +
        'data-action-target="' + _escHtml(tid) + '" ' +
        'tabindex="0" type="button">' +
        '<span class="bg-category-card__icon">📋</span>' +
        '<span class="bg-category-card__label">' + _escHtml(label) + '</span>' +
        '<span class="bg-category-card__arrow" aria-hidden="true">›</span>' +
        '</button>';
    }
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
      '<footer class="bg-footer bg-footer--sub">' +
        '<div class="bg-footer-body">' +
          '<p>대표전화: 062-410-8000</p>' +
        '</div>' +
        '<div class="bg-footer-legal">' +
          '<a href="#">누리집 이용안내</a>' +
          '<span>|</span>' +
          '<a href="#">개인정보처리방침</a>' +
        '</div>' +
      '</footer>'
    );
  }

  // -----------------------------------------------------------------------
  // Route renderer dispatch
  // -----------------------------------------------------------------------
  function _renderRoute(routeId) {
    var route = _map.getRoute(routeId);
    if (!route) { return "<p>알 수 없는 경로입니다.</p>"; }

    switch (routeId) {
      case "home":               return _renderHome();
      case "civil-service":      return _renderCivilService(route);
      case "complaint-category": return _renderComplaintCategory(route);
      case "complaint-intake":   return _renderComplaintIntake(route);
      case "complaint-review":   return _renderComplaintReview(route);
      case "handoff-stop":       return _renderHandoffStop(route);
      default:                   return "<p>알 수 없는 경로입니다.</p>";
    }
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

      // Handle category selection
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
