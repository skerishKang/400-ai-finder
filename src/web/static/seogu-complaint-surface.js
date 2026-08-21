/*
 * seogu-complaint-surface.js
 * Seo-gu (서구) app-owned complaint-board / complaint-write surface renderer.
 *
 * Purpose:
 *   Provide an app-owned UI inside #demo-canvas for S3/S4 complaint-writing
 *   journeys so that the Buk-gu canonical choreography (CitizenFirstChoreography)
 *   can execute the complaint-board → complaint-write → draft → pre-submit flow
 *   without any EXTERNAL_OFFICIAL_HANDOFF or iframe-based route.
 *
 * Architecture:
 *   - Renders two states inside #demo-canvas (not inside the clone iframe):
 *       complaint-board  : title panel + #btn-board-write (no write fields)
 *       complaint-write  : #board-write-title, #board-write-content,
 *                          #btn-board-submit (disabled / pre-submit only)
 *   - Implements the COMPATIBILITY_DRIVER API that CitizenFirstChoreography
 *     calls through window.CitizenActionDemoCanvas:
 *       navigateToRoute(routeId)
 *       getCurrentRouteId()
 *       hasRoute(routeId)
 *       getTargetElement(selectorOrEl)
 *       showCursorAt(selectorOrEl)
 *       hideCursor()
 *       clickAnimation(selectorOrEl)
 *   - Seo-gu branded. Does NOT imitate the official complaint website:
 *     no real submit, no transport, no auth, no PII, no external origin.
 *     The surface is an AI-assisted draft-preparation area only.
 *
 * Integration:
 *   Loaded BEFORE citizen-first-choreography.js so that when the choreography
 *   module initialises it finds window.CitizenActionDemoCanvas already set.
 *   The shell drives this surface only for S3/S4 complaint-writing journeys
 *   after the shared controller's evidence gate passes.
 *
 * Guarantees:
 *   - No fetch / XHR / WebSocket / sendBeacon.
 *   - No storage, cookie, URL hash, query string.
 *   - No auto-open, auto-prefill, auto-submit, receipt, or success semantics.
 *   - #btn-board-submit stays disabled throughout — the surface is pre-submit only.
 */
(function () {
  "use strict";

  var HIGHLIGHT_CLASS = "seogu-surface-highlight";
  var CURSOR_CLASS = "seogu-surface-cursor";
  var CLICK_RIPPLE_CLASS = "seogu-surface-click-ripple";

  var _canvas = null;
  var _currentRouteId = "idle";
  var _highlightedEls = [];
  var _surfaceReady = false;

  var _SUPPORTED_ROUTES = Object.freeze([
    "complaint-board",
    "complaint-write",
  ]);

  // ── Helpers ────────────────────────────────────────────────────────────────

  function _findCanvas() {
    if (typeof document === "undefined" || !document) return null;
    return document.getElementById("demo-canvas");
  }

  function _viewHost() {
    if (!_canvas) return null;
    var existing = _canvas.querySelector("[data-seogu-complaint-view]");
    if (existing) return existing;
    var inner = _canvas.querySelector(".demo-canvas__inner");
    if (inner) {
      var host = document.createElement("div");
      host.setAttribute("data-seogu-complaint-view", "true");
      host.className = "seogu-complaint-surface";
      inner.appendChild(host);
      return host;
    }
    var host = document.createElement("div");
    host.setAttribute("data-seogu-complaint-view", "true");
    host.className = "seogu-complaint-surface";
    _canvas.appendChild(host);
    return host;
  }

  function _escHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function _supportsReducedMotion() {
    try {
      return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    } catch (_) {
      return false;
    }
  }

  function _scrollBehavior() {
    return _supportsReducedMotion() ? "auto" : "smooth";
  }

  // ── Route rendering ────────────────────────────────────────────────────────

  function _renderComplaintBoard() {
    var host = _viewHost();
    if (!host) return;
    host.innerHTML = "";

    var page = document.createElement("div");
    page.className = "seogu-surface-page seogu-surface-page--complaint-board";
    page.setAttribute("data-complaint-route", "complaint-board");

    var header = document.createElement("header");
    header.className = "seogu-surface-header";
    header.innerHTML =
      '<div class="seogu-surface-header__brand">' +
        '<span class="seogu-surface-header__mark">서구청 AI</span>' +
        '<span class="seogu-surface-header__label">생활민원 · 민원게시판</span>' +
      '</div>';
    page.appendChild(header);

    var main = document.createElement("main");
    main.className = "seogu-surface-main";

    var hero = document.createElement("section");
    hero.className = "seogu-surface-hero";
    hero.innerHTML =
      '<p class="seogu-surface-hero__eyebrow">SEO-GU COMPLAINT BOARD</p>' +
      '<h1 class="seogu-surface-hero__title">생활의 불편을<br><strong>함께 작성합니다</strong></h1>' +
      '<p class="seogu-surface-hero__desc">' +
        'AI가 제목과 본문 초안을 도와드립니다. ' +
        '작성 내용은 주민이 직접 확인한 뒤 서구청 공식 채널에서 진행해야 합니다.' +
      '</p>';
    main.appendChild(hero);

    var boardPanel = document.createElement("section");
    boardPanel.className = "seogu-surface-board-panel";
    boardPanel.setAttribute("aria-labelledby", "seogu-complaint-board-title");

    var panelHead = document.createElement("header");
    panelHead.className = "seogu-surface-board-panel__head";
    panelHead.innerHTML =
      '<div>' +
        '<p>주민 생활 민원</p>' +
        '<h2 id="seogu-complaint-board-title">민원게시판</h2>' +
      '</div>' +
      '<button type="button" class="seogu-surface-action-btn seogu-surface-action-btn--primary" ' +
        'data-action-target="complaint-write" id="btn-board-write">' +
        '<span aria-hidden="true">＋</span> 새 민원 작성' +
      '</button>';
    boardPanel.appendChild(panelHead);

    var toolbar = document.createElement("div");
    toolbar.className = "seogu-surface-board-toolbar";
    toolbar.innerHTML =
      '<div class="seogu-surface-board-search" aria-label="민원 검색">' +
        '<span aria-hidden="true">&#128269;</span>' +
        '<input type="search" aria-label="민원 검색" placeholder="제목이나 처리 부서를 검색하세요" disabled>' +
      '</div>';
    boardPanel.appendChild(toolbar);

    var tableWrap = document.createElement("div");
    tableWrap.className = "seogu-surface-board-table-wrap";
    tableWrap.innerHTML =
      '<table class="seogu-surface-board-table" id="board-list-table">' +
        '<thead><tr>' +
          '<th scope="col">번호</th>' +
          '<th scope="col">제목</th>' +
          '<th scope="col">상태</th>' +
        '</tr></thead>' +
        '<tbody id="board-list-body">' +
          '<tr><td colspan="3" class="seogu-surface-board-empty">게시글이 없습니다. 새 민원을 작성해 주세요.</td></tr>' +
        '</tbody>' +
      '</table>';
    boardPanel.appendChild(tableWrap);

    var footer = document.createElement("footer");
    footer.className = "seogu-surface-board-panel__foot";
    footer.innerHTML =
      '<p><span aria-hidden="true">i</span> ' +
        '개인정보와 정확한 위치는 제출 전 직접 확인해 주세요. 이 화면은 초안 작성용입니다.</p>';
    boardPanel.appendChild(footer);

    main.appendChild(boardPanel);
    page.appendChild(main);

    host.appendChild(page);
  }

  function _renderComplaintWrite() {
    var host = _viewHost();
    if (!host) return;
    host.innerHTML = "";

    var page = document.createElement("div");
    page.className = "seogu-surface-page seogu-surface-page--complaint-write";
    page.setAttribute("data-complaint-route", "complaint-write");

    var header = document.createElement("header");
    header.className = "seogu-surface-header";
    header.innerHTML =
      '<div class="seogu-surface-header__brand">' +
        '<span class="seogu-surface-header__mark">서구청 AI</span>' +
        '<span class="seogu-surface-header__label">생활민원 · 글쓰기</span>' +
      '</div>';
    page.appendChild(header);

    var main = document.createElement("main");
    main.className = "seogu-surface-main seogu-surface-writing";

    var breadcrumb = document.createElement("nav");
    breadcrumb.className = "seogu-surface-breadcrumb";
    breadcrumb.setAttribute("aria-label", "경로");
    breadcrumb.innerHTML =
      '<span>홈</span><span aria-hidden="true">&rsaquo;</span>' +
      '<span>소통광장</span><span aria-hidden="true">&rsaquo;</span>' +
      '<span>민원게시판</span><span aria-hidden="true">&rsaquo;</span>' +
      '<span>AI 민원작성</span>';
    main.appendChild(breadcrumb);

    var writingHead = document.createElement("section");
    writingHead.className = "seogu-surface-writing__head";
    writingHead.innerHTML =
      '<p class="seogu-surface-writing__eyebrow">SEO-GU COMPLAINT WRITE</p>' +
      '<h1 id="complaint-writing-title">AI와 함께 민원 쓰기</h1>' +
      '<p class="seogu-surface-writing__desc">' +
        '생활 속 불편을 편하게 말씀하시면 제목과 본문 초안으로 정리해 드립니다. ' +
        '제출 전 반드시 내용을 직접 확인해 주세요.' +
      '</p>';
    main.appendChild(writingHead);

    var formPanel = document.createElement("section");
    formPanel.className = "seogu-surface-writing__form";
    formPanel.setAttribute("data-pre-submit", "true");

    var titleGroup = document.createElement("div");
    titleGroup.className = "seogu-surface-writing__field";
    titleGroup.innerHTML =
      '<label for="board-write-title" class="seogu-surface-writing__label">제목</label>' +
      '<input type="text" id="board-write-title" class="bg-dept-search__input seogu-surface-writing__input" ' +
        'maxlength="120" autocomplete="off" aria-describedby="board-write-title-hint" />' +
      '<span id="board-write-title-hint" class="seogu-surface-writing__hint" role="note">120자 이내</span>';
    formPanel.appendChild(titleGroup);

    var contentGroup = document.createElement("div");
    contentGroup.className = "seogu-surface-writing__field";
    contentGroup.innerHTML =
      '<label for="board-write-content" class="seogu-surface-writing__label">본문</label>' +
      '<textarea id="board-write-content" class="seogu-surface-writing__textarea" ' +
        'rows="8" maxlength="2000" aria-describedby="board-write-content-hint"></textarea>' +
      '<span id="board-write-content-hint" class="seogu-surface-writing__hint" role="note">2000자 이내 · 실제 제출 전 직접 확인</span>';
    formPanel.appendChild(contentGroup);

    var consent = document.createElement("div");
    consent.className = "seogu-surface-writing__consent";
    consent.innerHTML =
      '<p><strong>작성자 동의</strong></p>' +
      '<p>본인은 위 내용이 사실에 기반함을 확인합니다. ' +
        '본 화면은 초안 작성용이며 실제 민원 제출을 대신하지 않습니다.</p>';
    formPanel.appendChild(consent);

    var actions = document.createElement("div");
    actions.className = "seogu-surface-writing__actions";
    actions.setAttribute("data-writing-actions", "true");

    var backBtn = document.createElement("button");
    backBtn.type = "button";
    backBtn.className = "seogu-surface-action-btn";
    backBtn.setAttribute("data-action-target", "complaint-board-return");
    backBtn.textContent = "게시판으로 돌아가기";
    actions.appendChild(backBtn);

    var submitBtn = document.createElement("button");
    submitBtn.type = "button";
    submitBtn.id = "btn-board-submit";
    submitBtn.className = "seogu-surface-action-btn seogu-surface-action-btn--primary";
    submitBtn.disabled = true;
    submitBtn.setAttribute("aria-disabled", "true");
    submitBtn.setAttribute("data-default-label", "제출하기 (비활성)");
    submitBtn.textContent = "제출하기 (비활성)";
    actions.appendChild(submitBtn);

    formPanel.appendChild(actions);
    main.appendChild(formPanel);

    var safety = document.createElement("section");
    safety.className = "seogu-surface-writing__safety";
    safety.setAttribute("data-safety-notice", "true");
    safety.innerHTML =
      '<p><strong>STOP boundary</strong></p>' +
      '<p>이 화면은 AI 보조 초안 작성 영역입니다. ' +
        '실제 민원 제출은 서구청 공식 채널에서 주민이 직접 진행해야 하며, ' +
        '본 MVP는 제출을 대행하지 않습니다.</p>';
    main.appendChild(safety);

    page.appendChild(main);
    host.appendChild(page);

    // Wire back button.
    backBtn.addEventListener("click", function () {
      navigateToRoute("complaint-board");
    });
  }

  // ── Public API (COMPATIBILITY_DRIVER) ──────────────────────────────────────

  function navigateToRoute(routeId) {
    if (_SUPPORTED_ROUTES.indexOf(routeId) === -1) return false;
    var canvas = _findCanvas();
    if (!canvas) return false;
    _currentRouteId = routeId;
    if (routeId === "complaint-board") {
      _clearHighlights();
      _renderComplaintBoard();
    } else if (routeId === "complaint-write") {
      _clearHighlights();
      _renderComplaintWrite();
    }
    try {
      if (window.CustomEvent) {
        window.dispatchEvent(new CustomEvent("seogu:complaint-surface-routechange", {
          detail: { routeId: _currentRouteId },
        }));
      }
    } catch (_) { /* best-effort */ }
    return true;
  }

  function getCurrentRouteId() {
    return _currentRouteId;
  }

  function hasRoute(routeId) {
    return _SUPPORTED_ROUTES.indexOf(routeId) !== -1;
  }

  function getTargetElement(selectorOrEl) {
    if (selectorOrEl && typeof selectorOrEl === "object" && selectorOrEl.nodeType) {
      return selectorOrEl;
    }
    if (typeof selectorOrEl !== "string" || !selectorOrEl) return null;
    var host = _viewHost();
    if (!host) return null;
    try {
      var el = host.querySelector(selectorOrEl);
      if (el) return el;
    } catch (_) { /* invalid selector — fall through */ }
    try {
      return _canvas && _canvas.querySelector(selectorOrEl);
    } catch (_) {
      return null;
    }
  }

  function showCursorAt(selectorOrEl) {
    var el = getTargetElement(selectorOrEl);
    if (!el) return false;
    _clearHighlights();
    el.classList.add(HIGHLIGHT_CLASS);
    el.classList.add(CURSOR_CLASS);
    _highlightedEls.push(el);
    try {
      el.scrollIntoView({ behavior: _scrollBehavior(), block: "center" });
    } catch (_) { /* ignore */ }
    return true;
  }

  function hideCursor() {
    _clearHighlights();
  }

  function _clearHighlights() {
    for (var i = 0; i < _highlightedEls.length; i++) {
      var n = _highlightedEls[i];
      if (n && n.classList) {
        n.classList.remove(HIGHLIGHT_CLASS);
        n.classList.remove(CURSOR_CLASS);
        n.classList.remove(CLICK_RIPPLE_CLASS);
      }
    }
    _highlightedEls = [];
  }

  function clickAnimation(selectorOrEl) {
    var el = getTargetElement(selectorOrEl);
    if (!el) return false;
    _clearHighlights();
    el.classList.add(HIGHLIGHT_CLASS);
    _highlightedEls.push(el);
    try {
      el.scrollIntoView({ behavior: _scrollBehavior(), block: "center" });
    } catch (_) { /* ignore */ }
    if (!_supportsReducedMotion()) {
      el.classList.add(CLICK_RIPPLE_CLASS);
      setTimeout(function () {
        if (el && el.classList) el.classList.remove(CLICK_RIPPLE_CLASS);
      }, 340);
    }
    return true;
  }

  function fitToViewport() {
    var host = _viewHost();
    if (host && _canvas) {
      host.style.height = _canvas.clientHeight + "px";
      host.style.width = _canvas.clientWidth + "px";
    }
  }

  function reset() {
    _currentRouteId = "idle";
    _clearHighlights();
    var host = _viewHost();
    if (host) {
      host.innerHTML = "";
    }
  }

  // ── Expose public API ──────────────────────────────────────────────────────
  // The choreography resolves this at step-execution time, so the surface may
  // be set before the choreography module loads.
  window.SeoguComplaintSurface = Object.freeze({
    navigateToRoute: navigateToRoute,
    getCurrentRouteId: getCurrentRouteId,
    hasRoute: hasRoute,
    getTargetElement: getTargetElement,
    showCursorAt: showCursorAt,
    hideCursor: hideCursor,
    clickAnimation: clickAnimation,
    fitToViewport: fitToViewport,
    reset: reset,
    isReady: function () { return _surfaceReady; },
  });

  // Compatibility driver: CitizenFirstChoreography calls
  // window.CitizenActionDemoCanvas.* for route / cursor / click operations.
  window.CitizenActionDemoCanvas = Object.freeze({
    navigateToRoute: navigateToRoute,
    getCurrentRouteId: getCurrentRouteId,
    hasRoute: hasRoute,
    getTargetElement: getTargetElement,
    showCursorAt: showCursorAt,
    hideCursor: hideCursor,
    clickAnimation: clickAnimation,
    fitToViewport: fitToViewport,
  });

  _canvas = _findCanvas();
  _surfaceReady = !!_canvas;

  if (typeof window !== "undefined" && window.addEventListener) {
    window.addEventListener("resize", fitToViewport);
  }
})();