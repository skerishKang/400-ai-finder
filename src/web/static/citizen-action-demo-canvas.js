/**
 * citizen-action-demo-canvas.js
 * Local route-rendered administrative-page canvas.
 *
 * Implements a high-fidelity virtual browser viewport of the Buk-gu office.
 * Uses window.CitizenActionDemoMap for closed vocabulary.
 * Validates all route/target operations against the closed map.
 * No fetch, no persistence, no external URLs, no runner/provider.
 */

(function () {
  "use strict";

  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------
  var _currentRouteId = "home";
  var _selectedCategory = null;  // local UI state only

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
  // Required structural renderers (Satisfies automated contract tests)
  // -----------------------------------------------------------------------

  function _renderNavBar() {
    var currentUrl = "/index.es?sid=a1";
    if (_currentRouteId === "civil-service") {
      currentUrl = "/menu.es?mid=a10100000000";
    } else if (_currentRouteId === "complaint-category") {
      currentUrl = "/menu.es?mid=a10102000000";
    } else if (_currentRouteId === "complaint-intake") {
      currentUrl = "/complaint.es?mid=a10103000000";
    } else if (_currentRouteId === "complaint-review") {
      currentUrl = "/complaint.es?mid=a10104000000";
    } else if (_currentRouteId === "handoff-stop") {
      currentUrl = "/complaint.es?mid=a10109000000";
    }

    var activeMenu = (_currentRouteId === "home") ? "종합민원" : "온라인민원신청";
    var menus = ["북구소개", "종합민원", "온라인민원신청", "정보공개", "구정소식", "분야별정보", "행정참여"];
    var gnbHtml = '<nav class="bukgu-header__gnb" aria-label="북구청 GNB">';
    for (var i = 0; i < menus.length; i++) {
      var activeCls = (menus[i] === activeMenu) ? ' bukgu-header__gnb-item--active' : '';
      gnbHtml += '<a href="#" class="bukgu-header__gnb-item' + activeCls + '" onclick="return false;">' + _escHtml(menus[i]) + '</a>';
    }
    gnbHtml += '</nav>';

    return (
      '<div class="browser-bar">' +
        '<div class="browser-controls">' +
          '<span class="browser-dot browser-dot--red"></span>' +
          '<span class="browser-dot browser-dot--yellow"></span>' +
          '<span class="browser-dot browser-dot--green"></span>' +
        '</div>' +
        '<div class="browser-nav-btns">' +
          '<button class="browser-nav-btn" type="button" aria-label="뒤로 가기">&#x2190;</button>' +
          '<button class="browser-nav-btn" type="button" aria-label="앞으로 가기">&#x2192;</button>' +
          '<button class="browser-nav-btn" type="button" aria-label="새로고침">&#x21bb;</button>' +
        '</div>' +
        '<div class="browser-address">' +
          '<span class="browser-address__icon">🔒</span>' +
          '<span>https://www.bukgu.gwangju.kr' + _escHtml(currentUrl) + '</span>' +
        '</div>' +
      '</div>' +
      '<header class="canvas-nav">' +
        '<div class="bukgu-header__utility">' +
          '<a href="#" class="bukgu-header__utility-link" onclick="return false;">로그인</a>' +
          '<a href="#" class="bukgu-header__utility-link" onclick="return false;">회원가입</a>' +
          '<a href="#" class="bukgu-header__utility-link" onclick="return false;">사이트맵</a>' +
          '<a href="#" class="bukgu-header__utility-link" onclick="return false;">ENGLISH</a>' +
        '</div>' +
        '<div class="bukgu-header__main">' +
          '<div class="bukgu-header__logo-wrap">' +
            '<div class="bukgu-header__symbol">💻</div>' +
            '<div class="bukgu-header__brand">' +
              '<span class="bukgu-header__office-name">광주광역시 북구</span>' +
            '</div>' +
          '</div>' +
          '<div class="bukgu-header__search">' +
            '<input type="text" class="bukgu-header__search-input" placeholder="검색어를 입력하세요" readonly>' +
            '<button class="bukgu-header__search-btn" type="button" aria-label="검색">🔍</button>' +
          '</div>' +
        '</div>' +
        gnbHtml +
      '</header>'
    );
  }

  function _renderBreadcrumb(label) {
    var midPath = (_currentRouteId === "home")
      ? ''
      : '<span class="canvas-breadcrumb__sep" aria-hidden="true">&rsaquo;</span>' +
        '<span class="canvas-breadcrumb__item">종합민원</span>' +
        '<span class="canvas-breadcrumb__sep" aria-hidden="true">&rsaquo;</span>' +
        '<span class="canvas-breadcrumb__item">온라인 민원신청</span>';

    return (
      '<div class="canvas-breadcrumb" aria-label="현재 위치">' +
        '<span class="canvas-breadcrumb__item">홈</span>' +
        midPath +
        '<span class="canvas-breadcrumb__sep" aria-hidden="true">&rsaquo;</span>' +
        '<span class="canvas-breadcrumb__item">' + _escHtml(label) + '</span>' +
      '</div>'
    );
  }

  function _renderPageHeader(route) {
    return (
      '<div class="canvas-page-header">' +
        '<h1 class="canvas-page-title">' + _escHtml(route.title) + '</h1>' +
        '<p class="canvas-page-purpose">' + _escHtml(route.purpose) + '</p>' +
      '</div>'
    );
  }

  function _renderPocBanner() {
    return (
      '<div class="canvas-poc-banner" role="note" aria-label="데모 고지">' +
        '<span class="canvas-poc-banner__label">⚠️ 로컬 개념 시연 (PoC) 안내</span>' +
        '<p class="canvas-poc-banner__text">' +
        '이 페이지는 실제 북구청 공식 사이트가 아니며, 로컬 개념 시연 (PoC) 목적으로 제작되었습니다.<br>' +
        '본 데모에서는 어떠한 데이터도 실제로 제출되거나 처리되지 않습니다.<br>' +
        '인증 및 실제 민원 제출은 시민의 책임 하에 북구청 공식 채널을 통해 진행하시기 바랍니다.' +
        '</p>' +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // Page renderers — one per route
  // Each returns an HTML string.
  // -----------------------------------------------------------------------

  function _renderHome(route) {
    return (
      '<div class="browser-viewport">' +
        _renderNavBar() +
        _renderBreadcrumb(route.breadcrumbLabel) +
        '<div class="canvas-body">' +
          _renderPageHeader(route) +
          _renderPocBanner() +
          '<div class="bukgu-hero">' +
            '<h2 class="bukgu-hero__title">광주광역시 북구 홈페이지</h2>' +
            '<p class="bukgu-hero__subtitle">구민과 소통하고 공감하는 신뢰받는 열린 행정을 실현합니다.</p>' +
          '</div>' +
          '<div class="bukgu-quick-grid" role="group" aria-label="자주찾는 서비스">' +
            '<div class="bukgu-quick-card">' +
              '<span class="bukgu-quick-card__icon">📋</span>' +
              '<span class="bukgu-quick-card__label">민원안내</span>' +
            '</div>' +
            '<div class="bukgu-quick-card">' +
              '<span class="bukgu-quick-card__icon">✈️</span>' +
              '<span class="bukgu-quick-card__label">여권발급</span>' +
            '</div>' +
            '<div class="bukgu-quick-card">' +
              '<span class="bukgu-quick-card__icon">🗑️</span>' +
              '<span class="bukgu-quick-card__label">대형폐기물</span>' +
            '</div>' +
            '<button class="bukgu-quick-card bukgu-quick-card--primary" ' +
              'data-action-target="nav-civil-service" data-demo-route="civil-service" type="button">' +
              '<span class="bukgu-quick-card__icon">⚖️</span>' +
              '<span class="bukgu-quick-card__label">민원 신청하기</span>' +
            '</button>' +
          '</div>' +
          '<div class="bukgu-board-section">' +
            '<div class="bukgu-card">' +
              '<div class="bukgu-card__title">공지사항 <span class="bukgu-card__more">+</span></div>' +
              '<ul class="bukgu-list">' +
                '<li class="bukgu-list-item"><span class="bukgu-list-item__text">2026 광주 북구 평생학습 프로그램 수강생 모집</span><span class="bukgu-list-item__date">07.01</span></li>' +
                '<li class="bukgu-list-item"><span class="bukgu-list-item__text">관내 어린이 보호구역 내 주정차 위반 단속 안내</span><span class="bukgu-list-item__date">06.28</span></li>' +
              '</ul>' +
            '</div>' +
            '<div class="bukgu-card">' +
              '<div class="bukgu-card__title">고시공고 <span class="bukgu-card__more">+</span></div>' +
              '<ul class="bukgu-list">' +
                '<li class="bukgu-list-item"><span class="bukgu-list-item__text">도시계획시설 개설공사 실시계획 고시</span><span class="bukgu-list-item__date">07.03</span></li>' +
                '<li class="bukgu-list-item"><span class="bukgu-list-item__text">무단방치 차량 강제견인 및 폐차 계획 공고</span><span class="bukgu-list-item__date">06.30</span></li>' +
              '</ul>' +
            '</div>' +
          '</div>' +
        '</div>' +
      '</div>'
    );
  }

  function _renderCivilService(route) {
    return (
      '<div class="browser-viewport">' +
        _renderNavBar() +
        _renderBreadcrumb(route.breadcrumbLabel) +
        '<div class="canvas-body">' +
          '<div class="bukgu-split-layout">' +
            '<aside class="bukgu-sidebar">' +
              '<div class="bukgu-sidebar__title">종합민원</div>' +
              '<ul class="bukgu-sidebar__menu">' +
                '<li class="bukgu-sidebar__item"><a href="#" class="bukgu-sidebar__link" onclick="return false;">민원안내 및 발급</a></li>' +
                '<li class="bukgu-sidebar__item"><a href="#" class="bukgu-sidebar__link" onclick="return false;">민원서식 다운로드</a></li>' +
                '<li class="bukgu-sidebar__item"><a href="#" class="bukgu-sidebar__link bukgu-sidebar__link--active" onclick="return false;">온라인 민원신청</a></li>' +
                '<li class="bukgu-sidebar__item"><a href="#" class="bukgu-sidebar__link" onclick="return false;">무료법률상담</a></li>' +
              '</ul>' +
            '</aside>' +
            '<main class="bukgu-main">' +
              _renderPageHeader(route) +
              _renderPocBanner() +
              '<div class="bukgu-intro-box">' +
                '<div class="bukgu-intro-box__title">온라인 민원 안내</div>' +
                '<p class="bukgu-intro-box__desc">본 페이지는 북구 주민들이 온라인으로 간편하게 생활 민원을 신청하실 수 있는 전용 창구입니다. 아래 버튼을 통해 필요한 분류를 조회하십시오.</p>' +
              '</div>' +
              '<div class="canvas-targets" style="margin-top: 10px;">' +
                '<button class="canvas-target" data-action-target="nav-complaint-category" data-demo-route="complaint-category" type="button">' +
                  '<span>민원 유형 선택하기</span>' +
                  '<span class="canvas-target__arrow">&rsaquo;</span>' +
                '</button>' +
              '</div>' +
            '</main>' +
          '</div>' +
        '</div>' +
      '</div>'
    );
  }

  function _renderComplaintCategory(route) {
    var html =
      '<div class="browser-viewport">' +
        _renderNavBar() +
        _renderBreadcrumb(route.breadcrumbLabel) +
        '<div class="canvas-body">' +
          '<div class="bukgu-split-layout">' +
            '<aside class="bukgu-sidebar">' +
              '<div class="bukgu-sidebar__title">종합민원</div>' +
              '<ul class="bukgu-sidebar__menu">' +
                '<li class="bukgu-sidebar__item"><a href="#" class="bukgu-sidebar__link" onclick="return false;">민원안내 및 발급</a></li>' +
                '<li class="bukgu-sidebar__item"><a href="#" class="bukgu-sidebar__link" onclick="return false;">민원서식 다운로드</a></li>' +
                '<li class="bukgu-sidebar__item"><a href="#" class="bukgu-sidebar__link bukgu-sidebar__link--active" onclick="return false;">온라인 민원신청</a></li>' +
              '</ul>' +
            '</aside>' +
            '<main class="bukgu-main">' +
              _renderPageHeader(route) +
              _renderPocBanner() +
              '<div class="bukgu-intro-box">' +
                '<p class="bukgu-intro-box__desc">원활한 접수를 위해 현재 겪고 계신 불편 사항의 정확한 유형을 선택하여 주시기 바랍니다.</p>' +
              '</div>' +
              '<div class="bukgu-category-grid" role="group" aria-label="민원 카테고리 선택">';

    for (var i = 0; i < route.navTargets.length; i++) {
      var tid = route.navTargets[i];
      var label = _map.getCategoryLabel(tid) || tid;
      var selectedCls = _selectedCategory === tid ? " bukgu-category-card--selected" : "";
      html +=
        '<button class="bukgu-category-card' + selectedCls + '" ' +
        'data-action-target="' + _escHtml(tid) + '" ' +
        'data-demo-route="complaint-intake" ' +
        'tabindex="0" type="button">' +
        '<span class="bukgu-category-card__label">' + _escHtml(label) + '</span>' +
        '<span class="bukgu-category-card__arrow">&rsaquo;</span>' +
        '</button>';
    }

    html += '</div></main></div></div></div></div>';
    return html;
  }

  function _renderComplaintIntake(route) {
    return (
      '<div class="browser-viewport">' +
        _renderNavBar() +
        _renderBreadcrumb(route.breadcrumbLabel) +
        '<div class="canvas-body">' +
          '<div class="bukgu-split-layout">' +
            '<aside class="bukgu-sidebar">' +
              '<div class="bukgu-sidebar__title">종합민원</div>' +
              '<ul class="bukgu-sidebar__menu">' +
                '<li class="bukgu-sidebar__item"><a href="#" class="bukgu-sidebar__link" onclick="return false;">민원안내 및 발급</a></li>' +
                '<li class="bukgu-sidebar__item"><a href="#" class="bukgu-sidebar__link bukgu-sidebar__link--active" onclick="return false;">온라인 민원신청</a></li>' +
              '</ul>' +
            '</aside>' +
            '<main class="bukgu-main">' +
              _renderPageHeader(route) +
              _renderPocBanner() +
              '<div class="bukgu-steps">' +
                '<div class="bukgu-step">01. 유형 선택</div>' +
                '<div class="bukgu-step bukgu-step--active">02. 내용 작성 및 확인</div>' +
                '<div class="bukgu-step">03. 신청 완료</div>' +
              '</div>' +
              '<div class="bukgu-intake-card">' +
                '<div class="bukgu-intake-header">' +
                  '<span class="bukgu-intake-header__badge">민원 접수용</span>' +
                  '<span>아래 텍스트 상자에 작성된 초안이 표기됩니다.</span>' +
                '</div>' +
                '<div class="canvas-intake-field__input" data-action-target="complaint-body" id="complaint-body" style="min-height:120px;">' +
                  '우측 AI 민원비서의 초안 작성 과정을 진행해 주세요. 작성이 끝난 후 로컬에 반영되면 이곳에 출력됩니다.' +
                '</div>' +
              '</div>' +
              '<div class="bukgu-agreement">' +
                '<input type="checkbox" id="bukgu-agree-chk" checked disabled>' +
                '<label for="bukgu-agree-chk">개인정보 수집 및 동의서 약관에 확인하였으며 이에 동의합니다. (시연용 강제 동의)</label>' +
              '</div>' +
              '<div class="canvas-targets">' +
                '<button class="canvas-target" data-action-target="complaint-draft-review" data-demo-route="complaint-review" type="button">' +
                  '<span>민원 내용 최종 검토하기</span>' +
                  '<span class="canvas-target__arrow">&rsaquo;</span>' +
                '</button>' +
              '</div>' +
            '</main>' +
          '</div>' +
        '</div>' +
      '</div>'
    );
  }

  function _renderComplaintReview(route) {
    var categoryLabel = _selectedCategory
      ? (_map.getCategoryLabel(_selectedCategory) || _selectedCategory)
      : "불법 주정차 신고";

    return (
      '<div class="browser-viewport" style="position: relative;">' +
        _renderNavBar() +
        _renderBreadcrumb(route.breadcrumbLabel) +
        '<div class="canvas-body">' +
          '<div class="bukgu-split-layout">' +
            '<aside class="bukgu-sidebar">' +
              '<div class="bukgu-sidebar__title">종합민원</div>' +
              '<ul class="bukgu-sidebar__menu">' +
                '<li class="bukgu-sidebar__item"><a href="#" class="bukgu-sidebar__link" onclick="return false;">민원안내 및 발급</a></li>' +
                '<li class="bukgu-sidebar__item"><a href="#" class="bukgu-sidebar__link bukgu-sidebar__link--active" onclick="return false;">온라인 민원신청</a></li>' +
              '</ul>' +
            '</aside>' +
            '<main class="bukgu-main">' +
              _renderPageHeader(route) +
              _renderPocBanner() +
              '<div class="bukgu-table-card">' +
                '<table class="bukgu-table">' +
                  '<tbody>' +
                    '<tr><th>신청 구분</th><td>온라인 민원 접수</td></tr>' +
                    '<tr><th>민원 분류</th><td>' + _escHtml(categoryLabel) + '</td></tr>' +
                    '<tr><th>접수 상태</th><td>제출 전 최종 확인 단계 (로컬 데모)</td></tr>' +
                    '<tr><th>고지 사항</th><td>본 서비스는 PoC 용도로 실제 공무원에게 발송되지 않습니다.</td></tr>' +
                  '</tbody>' +
                '</table>' +
              '</div>' +
              '<div class="canvas-targets">' +
                '<button class="canvas-target" disabled data-action-target="confirm-draft-prefill" data-demo-route="handoff-stop" type="button" style="background-color: #94a3b8; cursor: not-allowed;" title="개념 시연 보안 중지로 인해 제출이 비활성화되었습니다.">' +
                  '<span>제출 비활성화 (보안 중지)</span>' +
                '</button>' +
              '</div>' +
            '</main>' +
          '</div>' +
        '</div>' +
        '<!-- 제출 전 안전 중지 (Safety Stop) 오버레이 -->' +
        '<div class="bukgu-safety-overlay">' +
          '<div class="bukgu-safety-card">' +
            '<div class="bukgu-safety-icon">⚠️</div>' +
            '<h3 class="bukgu-safety-title">제출 전 안전 중지 (Safety Stop)</h3>' +
            '<p class="bukgu-safety-text">' +
              '개념 시연(PoC) 보안 정책에 의해 실제 민원 제출 단계 직전에 작동이 안전하게 중단되었습니다.<br>' +
              '본 시스템은 가상의 로컬 모의 환경이므로, 실제 민원 전송이나 개인정보 저장은 발생하지 않습니다.' +
            '</p>' +
            '<button class="bukgu-safety-close-btn" data-action-target="confirm-draft-prefill" data-demo-route="handoff-stop" type="button">' +
              '확인 및 데모 종료' +
            '</button>' +
          '</div>' +
        '</div>' +
      '</div>'
    );
  }

  function _renderHandoffStop(route) {
    return (
      '<div class="browser-viewport">' +
        _renderNavBar() +
        _renderBreadcrumb(route.breadcrumbLabel) +
        '<div class="canvas-body">' +
          '<div class="bukgu-split-layout">' +
            '<aside class="bukgu-sidebar">' +
              '<div class="bukgu-sidebar__title">종합민원</div>' +
              '<ul class="bukgu-sidebar__menu">' +
                '<li class="bukgu-sidebar__item"><a href="#" class="bukgu-sidebar__link bukgu-sidebar__link--active" onclick="return false;">온라인 민원신청</a></li>' +
              '</ul>' +
            '</aside>' +
            '<main class="bukgu-main">' +
              _renderPageHeader(route) +
              _renderPocBanner() +
              '<div class="bukgu-hero" style="background: linear-gradient(135deg, #10b981 0%, #065f46 100%);">' +
                '<h2 class="bukgu-hero__title">시연이 정상 완료되었습니다</h2>' +
                '<p class="bukgu-hero__subtitle">본 로컬 개념 검증(PoC) 흐름이 여기서 마무리되었습니다.</p>' +
              '</div>' +
              '<div data-action-target="handoff-notice" class="bukgu-intro-box" style="border-left-color: #10b981; margin-top: 10px;">' +
                '<div class="bukgu-intro-box__title" style="color: #10b981;">안내 및 확인</div>' +
                '<p class="bukgu-intro-box__desc">' +
                  '이 가상 브라우저 화면은 북구청 공식 서비스 모사 화면으로, 실제 민원을 제출하지 않습니다.<br>' +
                  '인증 정보나 개인 정보를 서버로 전송하지 않는 안전한 모의 오프라인 환경입니다.' +
                '</p>' +
              '</div>' +
            '</main>' +
          '</div>' +
        '</div>' +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // Route renderer dispatch
  // -----------------------------------------------------------------------
  function _renderRoute(routeId) {
    var route = _map.getRoute(routeId);
    if (!route) { return "<p>알 수 없는 경로입니다.</p>"; }

    switch (routeId) {
      case "home":               return _renderHome(route);
      case "civil-service":      return _renderCivilService(route);
      case "complaint-category": return _renderComplaintCategory(route);
      case "complaint-intake":   return _renderComplaintIntake(route);
      case "complaint-review":   return _renderComplaintReview(route);
      case "handoff-stop":       return _renderHandoffStop(route);
      default:                   return "<p>알 수 없는 경로입니다.</p>";
    }
  }

  // -----------------------------------------------------------------------
  // Navigation API (only public interface)
  // -----------------------------------------------------------------------

  /**
   * Navigate to a route by ID.
   * @param {string} routeId
   */
  function navigateToRoute(routeId) {
    if (!_map.isValidRoute(routeId)) {
      _assert(false, "invalid routeId: " + routeId);
      return;
    }
    _currentRouteId = routeId;
    if (_demoCanvas) {
      _demoCanvas.innerHTML = _renderRoute(routeId);
      _attachDelegation();
    }
  }

  /** @returns {string} */
  function getCurrentRouteId() {
    return _currentRouteId;
  }

  /**
   * Get an element by its closed target ID within the canvas.
   * @param {string} targetId
   * @returns {Element|null}
   */
  function getTargetElement(targetId) {
    if (!_map.isValidTarget(targetId)) {
      return null;
    }
    if (!_demoCanvas) { return null; }
    return _demoCanvas.querySelector('[data-action-target="' + targetId + '"]');
  }

  // -----------------------------------------------------------------------
  // Event delegation for data-action-target clicks
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

      // Navigate to next route based on target
      var nextRoute = _targetToNextRoute(targetId);
      if (nextRoute) {
        navigateToRoute(nextRoute);
      }
    });
  }

  /** Map closed target ID to the next route ID. */
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
      "confirm-draft-prefill":         "handoff-stop",
      "handoff-notice":               null,
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
    _demoCanvas.innerHTML = _renderRoute(_currentRouteId);
    _attachDelegation();
  }

})();
