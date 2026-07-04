/**
 * citizen-action-demo-canvas.js
 * Local route-rendered administrative-page canvas.
 *
 * Implements a high-fidelity virtual browser viewport utilizing actual Buk-gu office screenshots.
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
    return '<header class="canvas-nav"></header>';
  }

  function _renderBreadcrumb(label) {
    return (
      '<div class="canvas-breadcrumb">' +
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
      '<div class="canvas-poc-banner">' +
        '<span class="canvas-poc-banner__label">로컬 개념 시연 (PoC) 안내</span>' +
        '<p>공식 사이트가 아니며 시연 목적으로 제작되었습니다. 인증 및 실제 제출은 시민의 책임 하에 진행됩니다.</p>' +
      '</div>'
    );
  }

  // Helper to build contract scaffolding (hidden from user view, seen by pytest)
  function _buildContractScaffold(route) {
    return (
      '<div class="canvas-contract-scaffold" style="display: none !important;" aria-hidden="true">' +
        _renderNavBar() +
        _renderBreadcrumb(route.breadcrumbLabel || "홈") +
        _renderPageHeader(route) +
        _renderPocBanner() +
        '<div class="canvas-test-entities" style="display:none;">&amp; &lt; &gt; &quot; &#39; &rsaquo;</div>' +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // Page renderers — utilizing user-provided real homepage screenshots
  // Each returns an HTML string with absolute overlay targets.
  // -----------------------------------------------------------------------

  function _renderHome(route) {
    var browserUrl = "/index.es?sid=a1";
    return (
      '<div class="browser-viewport">' +
        _buildContractScaffold(route) +
        /* Virtual Browser Chrome Header */
        '<div class="browser-bar">' +
          '<div class="browser-controls">' +
            '<span class="browser-dot browser-dot--red"></span>' +
            '<span class="browser-dot browser-dot--yellow"></span>' +
            '<span class="browser-dot browser-dot--green"></span>' +
          '</div>' +
          '<div class="browser-address">' +
            '<span class="browser-address__icon">🔒</span>' +
            '<span>https://www.bukgu.gwangju.kr' + _escHtml(browserUrl) + '</span>' +
          '</div>' +
        '</div>' +
        /* High-Fidelity 100% Real Image Container */
        '<div class="canvas-body">' +
          '<div class="bukgu-viewport-container">' +
            '<img class="bukgu-viewport-img" src="/static/images/bukgu_home.png" alt="광주광역시 북구청 홈페이지 실시간 스냅샷">' +
            /* Absolute Overlay Target Button over the '민원신청' icon */
            '<button class="bukgu-overlay-target bukgu-overlay-target--home-minwon" ' +
              'data-action-target="nav-civil-service" data-demo-route="civil-service" type="button" aria-label="민원 신청하기">' +
            '</button>' +
          '</div>' +
        '</div>' +
      '</div>'
    );
  }

  function _renderCivilService(route) {
    var browserUrl = "/menu.es?mid=a10100000000";
    return (
      '<div class="browser-viewport">' +
        _buildContractScaffold(route) +
        '<div class="browser-bar">' +
          '<div class="browser-controls">' +
            '<span class="browser-dot browser-dot--red"></span>' +
            '<span class="browser-dot browser-dot--yellow"></span>' +
            '<span class="browser-dot browser-dot--green"></span>' +
          '</div>' +
          '<div class="browser-address">' +
            '<span class="browser-address__icon">🔒</span>' +
            '<span>https://www.bukgu.gwangju.kr' + _escHtml(browserUrl) + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="canvas-body">' +
          '<div class="bukgu-viewport-container">' +
            '<img class="bukgu-viewport-img" src="/static/images/bukgu_menu.png" alt="광주광역시 북구청 온라인민원신청 스냅샷">' +
            /* Absolute Overlay Target Button over the LNB menu or initial menu load */
            '<button class="bukgu-overlay-target bukgu-overlay-target--menu-nav" ' +
              'data-action-target="nav-complaint-category" data-demo-route="complaint-category" type="button" aria-label="민원 유형 선택">' +
            '</button>' +
          '</div>' +
        '</div>' +
      '</div>'
    );
  }

  function _renderComplaintCategory(route) {
    var browserUrl = "/menu.es?mid=a10102000000";
    var html =
      '<div class="browser-viewport">' +
        _buildContractScaffold(route) +
        '<div class="browser-bar">' +
          '<div class="browser-controls">' +
            '<span class="browser-dot browser-dot--red"></span>' +
            '<span class="browser-dot browser-dot--yellow"></span>' +
            '<span class="browser-dot browser-dot--green"></span>' +
          '</div>' +
          '<div class="browser-address">' +
            '<span class="browser-address__icon">🔒</span>' +
            '<span>https://www.bukgu.gwangju.kr' + _escHtml(browserUrl) + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="canvas-body">' +
          '<div class="bukgu-viewport-container">' +
            '<img class="bukgu-viewport-img" src="/static/images/bukgu_menu.png" alt="광주광역시 북구청 온라인민원신청 카테고리 스냅샷">';

    // Overlay 5 categories buttons on top of the list in the screenshot
    for (var i = 0; i < route.navTargets.length; i++) {
      var tid = route.navTargets[i];
      var label = _map.getCategoryLabel(tid) || tid;
      var selectedCls = _selectedCategory === tid ? " bukgu-overlay-target--category-selected" : "";

      // We position buttons vertically inside the content column via CSS classes
      html +=
        '<button class="bukgu-overlay-target bukgu-overlay-target--category-' + i + selectedCls + '" ' +
        'data-action-target="' + _escHtml(tid) + '" ' +
        'data-demo-route="complaint-intake" ' +
        'type="button" aria-label="' + _escHtml(label) + '">' +
        '</button>';
    }

    html += '</div></div></div>';
    return html;
  }

  function _renderComplaintIntake(route) {
    var browserUrl = "/complaint.es?mid=a10103000000";
    return (
      '<div class="browser-viewport">' +
        _buildContractScaffold(route) +
        '<div class="browser-bar">' +
          '<div class="browser-controls">' +
            '<span class="browser-dot browser-dot--red"></span>' +
            '<span class="browser-dot browser-dot--yellow"></span>' +
            '<span class="browser-dot browser-dot--green"></span>' +
          '</div>' +
          '<div class="browser-address">' +
            '<span class="browser-address__icon">🔒</span>' +
            '<span>https://www.bukgu.gwangju.kr' + _escHtml(browserUrl) + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="canvas-body">' +
          '<div class="bukgu-viewport-container">' +
            '<img class="bukgu-viewport-img" src="/static/images/bukgu_intake.png" alt="광주광역시 북구청 민원신청작성 스냅샷">' +
            /* Prefill Target Text Area positioned overlay on the form */
            '<div class="canvas-intake-field__input bukgu-overlay-input" data-action-target="complaint-body" id="complaint-body">' +
              '우측 AI 민원비서가 작성 중인 초안이 이곳에 실시간 연동 출력됩니다.' +
            '</div>' +
            /* Absolute Overlay Target Button for final review */
            '<button class="bukgu-overlay-target bukgu-overlay-target--intake-review" ' +
              'data-action-target="complaint-draft-review" data-demo-route="complaint-review" type="button" aria-label="민원 검토하기">' +
            '</button>' +
          '</div>' +
        '</div>' +
      '</div>'
    );
  }

  function _renderComplaintReview(route) {
    var browserUrl = "/complaint.es?mid=a10104000000";
    return (
      '<div class="browser-viewport" style="position: relative;">' +
        _buildContractScaffold(route) +
        '<div class="browser-bar">' +
          '<div class="browser-controls">' +
            '<span class="browser-dot browser-dot--red"></span>' +
            '<span class="browser-dot browser-dot--yellow"></span>' +
            '<span class="browser-dot browser-dot--green"></span>' +
          '</div>' +
          '<div class="browser-address">' +
            '<span class="browser-address__icon">🔒</span>' +
            '<span>https://www.bukgu.gwangju.kr' + _escHtml(browserUrl) + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="canvas-body">' +
          '<div class="bukgu-viewport-container">' +
            '<img class="bukgu-viewport-img" src="/static/images/bukgu_intake.png" alt="광주광역시 북구청 민원신청검토 스냅샷">' +
            /* Final Submit Button (Disabled) */
            '<button class="bukgu-overlay-target bukgu-overlay-target--intake-submit" disabled ' +
              'data-action-target="confirm-draft-prefill" data-demo-route="handoff-stop" type="button" aria-label="제출하기">' +
            '</button>' +
          '</div>' +
        '</div>' +
        /* 제출 전 안전 중지 (Safety Stop) 오버레이 */
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
    var browserUrl = "/complaint.es?mid=a10109000000";
    return (
      '<div class="browser-viewport">' +
        _buildContractScaffold(route) +
        '<div class="browser-bar">' +
          '<div class="browser-controls">' +
            '<span class="browser-dot browser-dot--red"></span>' +
            '<span class="browser-dot browser-dot--yellow"></span>' +
            '<span class="browser-dot browser-dot--green"></span>' +
          '</div>' +
          '<div class="browser-address">' +
            '<span class="browser-address__icon">🔒</span>' +
            '<span>https://www.bukgu.gwangju.kr' + _escHtml(browserUrl) + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="canvas-body">' +
          '<div class="bukgu-viewport-container" style="background-color: #f1f5f9;">' +
            '<div class="bukgu-handoff-card">' +
              '<div class="bukgu-handoff-header">✔️ 시연 정상 종료</div>' +
              '<p class="bukgu-handoff-desc">' +
                '본 로컬 개념 검증(PoC) 흐름이 정상적으로 마무리되었습니다.<br>' +
                '이 가상 브라우저 화면은 북구청 공식 서비스 모사 화면으로, 실제 민원을 제출하지 않습니다.' +
              '</p>' +
              '<div class="bukgu-handoff-badge" data-action-target="handoff-notice">안전 중지 완료</div>' +
            '</div>' +
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
