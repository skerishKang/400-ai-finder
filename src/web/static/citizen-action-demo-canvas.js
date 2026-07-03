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

  function _escHtml(str) {
    return String(str)
      .replace(/&/g, "\x26")
      .replace(/</g, "\x3c")
      .replace(/>/g, "\x3e")
      .replace(/"/g, "\x22")
      .replace(/'/g, "\x27");
  }

  // -----------------------------------------------------------------------
  // Page renderers — one per route
  // Each returns an HTML string.
  // -----------------------------------------------------------------------

  /**
   * Render navigation target buttons.
   * @param {string[]} navTargets
   * @param {string|null} destRoute - destination route ID; only non-null
   *   and valid routes get data-demo-route attribute
   */
  function _renderNavTargets(navTargets, destRoute) {
    var html = '<div class="canvas-targets">';
    var hasDest = destRoute && _map.isValidRoute(destRoute);
    for (var i = 0; i < navTargets.length; i++) {
      var tid = navTargets[i];
      var label = _map.getCategoryLabel(tid) || _getTargetLabel(tid);
      var routeAttr = hasDest
        ? ' data-demo-route="' + _escHtml(destRoute) + '"'
        : '';
      html +=
        '<button class="canvas-target" ' +
        'data-action-target="' + _escHtml(tid) + '"' + routeAttr + ' ' +
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
      "nav-civil-service": "민원 신청하기",
      "nav-complaint-category": "민원 유형 선택",
      "complaint-draft-review": "내용 확인하기",
      "confirm-draft-prefill": "최종 확인 요청",
    };
    return labels[targetId] || targetId;
  }

  function _renderHome(route) {
    return (
      _renderNavBar() +
      _renderBreadcrumb(route.breadcrumbLabel) +
      '<div class="canvas-body">' +
        _renderPocBanner() +
        _renderNavTargets(route.navTargets, "civil-service") +
      '</div>'
    );
  }

  function _renderCivilService(route) {
    return (
      _renderNavBar() +
      _renderBreadcrumb(route.breadcrumbLabel) +
      '<div class="canvas-body">' +
        _renderPocBanner() +
        '<p style="font-size:0.875rem;color:#5d6d7e;line-height:1.6;">' +
        '아래 유익한 민원 서비스를 선택하여 절차를 안내받으세요.</p>' +
        _renderNavTargets(route.navTargets, "complaint-category") +
      '</div>'
    );
  }

  function _renderComplaintCategory(route) {
    var html =
      _renderNavBar() +
      _renderBreadcrumb(route.breadcrumbLabel) +
      '<div class="canvas-body">' +
        _renderPocBanner() +
        '<p style="font-size:0.875rem;color:#5d6d7e;line-height:1.5;margin-bottom:4px;">' +
        '해당 상황에 맞는 민원 유형을 선택해 주세요.</p>' +
        '<div class="canvas-category-grid">';

    for (var i = 0; i < route.navTargets.length; i++) {
      var tid = route.navTargets[i];
      var label = _map.getCategoryLabel(tid) || tid;
      var selectedCls = _selectedCategory === tid ? " canvas-category-card--selected" : "";
      html +=
        '<button class="canvas-category-card' + selectedCls + '" ' +
        'data-action-target="' + _escHtml(tid) + '" ' +
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
      '<div class="canvas-body">' +
        _renderPocBanner() +
        '<div class="canvas-intake-section">' +
          '<div class="canvas-intake-field">' +
            '<label class="canvas-intake-field__label">민원 내용 (예시)</label>' +
            '<div class="canvas-intake-field__input" ' +
            'data-action-target="complaint-body" ' +
            'style="min-height:80px;cursor:text;background:#f0f4f8;">' +
            '이곳에 민원 내용이 표시됩니다. (데모용-fixture 데이터)' +
            '</div>' +
            '<span class="canvas-intake-field__note">민원 초안 미리보기 영역입니다.</span>' +
          '</div>' +
          _renderNavTargets(route.navTargets, "complaint-review") +
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
      '<div class="canvas-body">' +
        _renderPocBanner() +
        '<div class="canvas-review-box">' +
          '<div class="canvas-review-row">' +
            '<span class="canvas-review-row__label">유형</span>' +
            '<span class="canvas-review-row__value">' + _escHtml(categoryLabel) + '</span>' +
          '</div>' +
          '<div class="canvas-review-row">' +
            '<span class="canvas-review-row__label">내용</span>' +
            '<span class="canvas-review-row__value">데모용-fixture 초안</span>' +
          '</div>' +
          '<div class="canvas-review-row">' +
            '<span class="canvas-review-row__label">비고</span>' +
            '<span class="canvas-review-row__value">아직 제출되지 않음</span>' +
          '</div>' +
        '</div>' +
        _renderNavTargets(route.navTargets, "handoff-stop") +
      '</div>'
    );
  }

  function _renderHandoffStop(route) {
    return (
      _renderNavBar() +
      _renderBreadcrumb(route.breadcrumbLabel) +
      '<div class="canvas-body">' +
        '<div class="canvas-handoff-box">' +
          '<div class="canvas-handoff-box__title">데모 종료</div>' +
          '<div class="canvas-handoff-box__body">' +
            '이 데모는 여기서 종료됩니다.<br><br>' +
            '실제 민원 신청은 북구청 공식 채널을 이용하시기 바랍니다.<br>' +
            '인증 및 제출은 시민의 책임이며, 공식 사이트에서 직접 진행해야 합니다.' +
          '</div>' +
        '</div>' +
        '<div data-action-target="handoff-notice" class="canvas-handoff-notice">' +
          '<strong>데모 종료 안내</strong><br>' +
          '이 페이지는 개념 시연용으로, 실제 행정 서비스에 연결되지 않습니다.' +
        '</div>' +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // Shared render pieces
  // -----------------------------------------------------------------------

  function _renderNavBar() {
    return (
      '<nav class="canvas-nav" aria-label="데모 상단 내비게이션">' +
        '<span class="canvas-nav__title">🏠 시민 행정 도우미 (데모)</span>' +
        '<span class="canvas-nav__hint">로컬 개념 시연용</span>' +
      '</nav>'
    );
  }

  function _renderBreadcrumb(label) {
    return (
      '<div class="canvas-breadcrumb" aria-label="현재 위치">' +
        '<span class="canvas-breadcrumb__item">홈</span>' +
        '<span class="canvas-breadcrumb__sep" aria-hidden="true">&rsaquo;</span>' +
        '<span class="canvas-breadcrumb__item">' + _escHtml(label) + '</span>' +
      '</div>'
    );
  }

  function _renderPocBanner() {
    return (
      '<div class="canvas-poc-banner" role="note" aria-label="데모 고지">' +
        '<span class="canvas-poc-banner__label">⚠️ 로컬 개념 시연 (PoC) 안내</span>' +
        '이 페이지는 실제 북구청 공식 사이트가 아닙니다.<br>' +
        '인증 및 민원 제출은 북구청 공식 채널에서 직접 진행하시기 바랍니다.' +
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
      _demoCanvas.innerHTML = '<div class="demo-canvas__inner">' + _renderRoute(routeId) + '</div>';
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
    _demoCanvas.innerHTML = '<div class="demo-canvas__inner">' + _renderRoute(_currentRouteId) + '</div>';
    _attachDelegation();
  }

})();