/**
 * citizen-action-demo-canvas.js
 * Local route-rendered administrative-page canvas.
 *
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
  var _delegationAttached = false;

  // -----------------------------------------------------------------------
  // DOM references
  // -----------------------------------------------------------------------
  var _demoCanvas = document.getElementById("demo-canvas");
  var _map = window.CitizenActionDemoMap;

  // -----------------------------------------------------------------------
  // Utility — valid HTML escaping
  // -----------------------------------------------------------------------
  function _escHtml(value) {
    return String(value)
      .replace(/&/g, "\u0026")
      .replace(/</g, "\u003c")
      .replace(/>/g, "\u003e")
      .replace(/"/g, "\u0022")
      .replace(/'/g, "\u0027");
  }

  // -----------------------------------------------------------------------
  // Shared render pieces
  // -----------------------------------------------------------------------

  /** Top navigation bar — present on every route. */
  function _renderNavBar() {
    return (
      '<nav class="canvas-nav" aria-label="데모 상단 메뉴">' +
        '<span class="canvas-nav__title">&#x1F3E8; 시민 행정 도우미 (시연용)</span>' +
        '<span class="canvas-nav__hint">로컬 개념 시연용</span>' +
      '</nav>'
    );
  }

  /** Breadcrumb showing current route position. */
  function _renderBreadcrumb(label) {
    return (
      '<div class="canvas-breadcrumb" aria-label="현재 위치">' +
        '<span class="canvas-breadcrumb__item">홈</span>' +
        '<span class="canvas-breadcrumb__sep" aria-hidden="true">&rsaquo;</span>' +
        '<span class="canvas-breadcrumb__item">' + _escHtml(label) + '</span>' +
      '</div>'
    );
  }

  /** Page header with title and purpose. */
  function _renderPageHeader(route) {
    return (
      '<header class="canvas-header">' +
        '<h1 class="canvas-header__title">' + _escHtml(route.title) + '</h1>' +
        '<p class="canvas-header__purpose">' + _escHtml(route.purpose) + '</p>' +
      '</header>'
    );
  }

  /** Persistent PoC disclosure — present on every route. */
  function _renderPocBanner() {
    return (
      '<div class="canvas-poc-banner" role="note" aria-label="데모 고지">' +
        '<span class="canvas-poc-banner__label">&#x26A0; 로컬 개념 시연 (PoC) 안내</span>' +
        '이 페이지는 북구청 공식 사이트가 아닙니다.<br>' +
        '인증 및 민원 제출은 북구청 공식 행정 채널에서 직접 진행하시기 바랍니다.<br>' +
        '이 데모는 실제 데이터를 제출하거나 처리하지 않습니다.' +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // Page renderers — each route: nav → breadcrumb → header → PoC → body
  // -----------------------------------------------------------------------

  function _renderHome(route) {
    return (
      _renderNavBar() +
      _renderBreadcrumb(route.breadcrumbLabel) +
      _renderPageHeader(route) +
      '<div class="canvas-body">' +
        _renderPocBanner() +
        _renderNavTargets(route.navTargets) +
      '</div>'
    );
  }

  function _renderCivilService(route) {
    return (
      _renderNavBar() +
      _renderBreadcrumb(route.breadcrumbLabel) +
      _renderPageHeader(route) +
      '<div class="canvas-body">' +
        _renderPocBanner() +
        '<p style="font-size:0.875rem;color:#5d6d7e;line-height:1.6;margin-bottom:12px;">' +
        '아래 민원 서비스를 선택하여 절차를 안내받으세요.</p>' +
        _renderNavTargets(route.navTargets) +
      '</div>'
    );
  }

  function _renderComplaintCategory(route) {
    var html =
      _renderNavBar() +
      _renderBreadcrumb(route.breadcrumbLabel) +
      _renderPageHeader(route) +
      '<div class="canvas-body">' +
        _renderPocBanner() +
        '<p style="font-size:0.875rem;color:#5d6d7e;line-height:1.5;margin-bottom:4px;">' +
        '해당 상황에 맞는 민원 유형을 선택해 주세요.</p>' +
        '<div class="canvas-category-grid">';

    for (var i = 0; i < route.navTargets.length; i++) {
      var tid = route.navTargets[i];
      var label = _map.getCategoryLabel(tid) || tid;
      var selectedCls = _selectedCategory === tid ? " canvas-category-card--selected" : "";
      var destRoute = _targetToNextRoute(tid);
      html +=
        '<button class="canvas-category-card' + selectedCls + '" ' +
        'data-action-target="' + _escHtml(tid) + '" ' +
        'data-demo-route="' + _escHtml(destRoute || "") + '" ' +
        'tabindex="0" type="button">' +
        '<span>' + _escHtml(label) + '</span>' +
        '<span class="canvas-category-card__arrow" aria-hidden="true">&#x203A;</span>' +
        '</button>';
    }

    html += '</div></div>';
    return html;
  }

  function _renderComplaintIntake(route) {
    return (
      _renderNavBar() +
      _renderBreadcrumb(route.breadcrumbLabel) +
      _renderPageHeader(route) +
      '<div class="canvas-body">' +
        _renderPocBanner() +
        '<div class="canvas-intake-section">' +
          '<div class="canvas-intake-field">' +
            '<span class="canvas-intake-field__label">민원 내용 (고정 예시)</span>' +
            '<div class="canvas-intake-display">' +
            '이곳에 민원 초안 미리보기 내용이 표시됩니다.<br>' +
            '(데모용 고정 예시 데이터 — 실제 입력 없음)' +
            '</div>' +
          '</div>' +
          _renderNavTargets(route.navTargets) +
        '</div>' +
      '</div>'
    );
  }

  function _renderComplaintReview(route) {
    var categoryLabel = _selectedCategory
      ? (_map.getCategoryLabel(_selectedCategory) || _selectedCategory)
      : "선택된 유형 없음";

    return (
      _renderNavBar() +
      _renderBreadcrumb(route.breadcrumbLabel) +
      _renderPageHeader(route) +
      '<div class="canvas-body">' +
        _renderPocBanner() +
        '<div class="canvas-review-box">' +
          '<div class="canvas-review-row">' +
            '<span class="canvas-review-row__label">유형</span>' +
            '<span class="canvas-review-row__value">' + _escHtml(categoryLabel) + '</span>' +
          '</div>' +
          '<div class="canvas-review-row">' +
            '<span class="canvas-review-row__label">내용</span>' +
            '<span class="canvas-review-row__value">데모용 고정 예시 초안</span>' +
          '</div>' +
          '<div class="canvas-review-row">' +
            '<span class="canvas-review-row__label">비고</span>' +
            '<span class="canvas-review-row__value">아직 제출되지 않음</span>' +
          '</div>' +
        '</div>' +
        _renderNavTargets(route.navTargets) +
      '</div>'
    );
  }

  function _renderHandoffStop(route) {
    return (
      _renderNavBar() +
      _renderBreadcrumb(route.breadcrumbLabel) +
      _renderPageHeader(route) +
      '<div class="canvas-body">' +
        _renderPocBanner() +
        '<div class="canvas-handoff-box">' +
          '<div class="canvas-handoff-box__title">&#x26A0; 데모 종료</div>' +
          '<div class="canvas-handoff-box__body">' +
            '로컬 개념 시연 데모는 여기서 종료됩니다.<br><br>' +
            '인증 및 실제 민원 제출은 북구청 공식 행정 채널에서 직접 진행하셔야 합니다.<br>' +
            '이 데모에서는 어떤 데이터도 제출되지 않으며, 개인 정보 입력을 처리하지 않습니다.' +
          '</div>' +
        '</div>' +
        _renderNavTargets(route.navTargets) +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // Nav target buttons (data-action-target, data-demo-route = destination)
  // -----------------------------------------------------------------------

  function _renderNavTargets(navTargets) {
    var html = '<div class="canvas-targets">';
    for (var i = 0; i < navTargets.length; i++) {
      var tid = navTargets[i];
      var label = _map.getCategoryLabel(tid) || _getTargetLabel(tid);
      var destRoute = _targetToNextRoute(tid);
      html +=
        '<button class="canvas-target" ' +
        'data-action-target="' + _escHtml(tid) + '" ' +
        'data-demo-route="' + _escHtml(destRoute || "") + '" ' +
        'tabindex="0" type="button">' +
        '<span>' + _escHtml(label) + '</span>' +
        '<span class="canvas-target__arrow" aria-hidden="true">&#x203A;</span>' +
        '</button>';
    }
    html += '</div>';
    return html;
  }

  function _getTargetLabel(targetId) {
    var labels = {
      "nav-civil-service":     "민원 신청하기",
      "nav-complaint-category": "민원 유형 선택",
      "complaint-body":          "민원 초안 보기",
      "complaint-draft-review":  "내용 확인하기",
      "confirm-draft-prefill":  "최종 확인 요청",
      "handoff-notice":         "데모 종료 안내",
    };
    return labels[targetId] || targetId;
  }

  // -----------------------------------------------------------------------
  // Route renderer dispatch
  // -----------------------------------------------------------------------

  function _renderRoute(routeId) {
    var route = _map.getRoute(routeId);
    if (!route) {
      return "<p>알 수 없는 경로입니다.</p>";
    }
    switch (routeId) {
      case "home":               return _renderHome(route);
      case "civil-service":     return _renderCivilService(route);
      case "complaint-category": return _renderComplaintCategory(route);
      case "complaint-intake":   return _renderComplaintIntake(route);
      case "complaint-review":   return _renderComplaintReview(route);
      case "handoff-stop":      return _renderHandoffStop(route);
      default:                  return "<p>알 수 없는 경로입니다.</p>";
    }
  }

  // -----------------------------------------------------------------------
  // Event delegation — attach exactly once
  // -----------------------------------------------------------------------

  /**
   * Map closed target ID to the destination route ID.
   * Returns null for targets with no navigation destination.
   * @param {string} targetId
   * @returns {string|null}
   */
  function _targetToNextRoute(targetId) {
    var flow = {
      "nav-civil-service":              "civil-service",
      "nav-complaint-category":         "complaint-category",
      "complaint-category-illegal-parking":              "complaint-intake",
      "complaint-category-public-parking-inconvenience": "complaint-intake",
      "complaint-category-residential-parking":          "complaint-intake",
      "complaint-category-traffic-or-facility-safety":   "complaint-intake",
      "complaint-category-other-or-unsure":              "complaint-intake",
      "complaint-body":                "complaint-intake",
      "complaint-draft-review":         "complaint-review",
      "confirm-draft-prefill":          "handoff-stop",
      "handoff-notice":                 null,
    };
    return flow[targetId] !== undefined ? flow[targetId] : null;
  }

  function _attachDelegation() {
    if (!_demoCanvas || _delegationAttached) {
      return;
    }
    _delegationAttached = true;
    _demoCanvas.addEventListener("click", function (e) {
      var target = e.target.closest("[data-action-target]");
      if (!target) { return; }
      var targetId = target.getAttribute("data-action-target");
      if (!_map.isValidTarget(targetId)) { return; }

      // Category selection — local UI state
      if (_currentRouteId === "complaint-category") {
        _selectedCategory = targetId;
        navigateToRoute("complaint-intake");
        return;
      }

      // Fixed local navigation based on closed target → route map
      var destRoute = _targetToNextRoute(targetId);
      if (destRoute) {
        navigateToRoute(destRoute);
      }
    });
  }

  // -----------------------------------------------------------------------
  // Navigation API — validates against closed map
  // -----------------------------------------------------------------------

  /**
   * Navigate to a route by closed route ID.
   * @param {string} routeId
   */
  function navigateToRoute(routeId) {
    if (!_map.isValidRoute(routeId)) {
      return;
    }
    _currentRouteId = routeId;
    if (_demoCanvas) {
      _demoCanvas.innerHTML =
        '<div class="demo-canvas__inner">' + _renderRoute(routeId) + '</div>';
      // Delegation attaches only once — do NOT re-attach here
    }
  }

  /** @returns {string} */
  function getCurrentRouteId() {
    return _currentRouteId;
  }

  /**
   * Get a canvas element by closed target ID.
   * @param {string} targetId
   * @returns {Element|null}
   */
  function getTargetElement(targetId) {
    if (!_map.isValidTarget(targetId)) { return null; }
    if (!_demoCanvas) { return null; }
    return _demoCanvas.querySelector('[data-action-target="' + targetId + '"]');
  }

  // -----------------------------------------------------------------------
  // Expose public API
  // -----------------------------------------------------------------------
  window.CitizenActionDemoCanvas = Object.freeze({
    navigateToRoute:   navigateToRoute,
    getCurrentRouteId: getCurrentRouteId,
    getTargetElement:  getTargetElement,
  });

  // -----------------------------------------------------------------------
  // Initial render — attach delegation once
  // -----------------------------------------------------------------------
  if (_demoCanvas) {
    _demoCanvas.innerHTML =
      '<div class="demo-canvas__inner">' + _renderRoute(_currentRouteId) + '</div>';
    _attachDelegation();
  }

})();