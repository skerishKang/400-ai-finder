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
    // #1363 Lane B: S7 mayor-proposal writing journey (Buk-gu
    // mayor-complaint-write/receipt shape, #1375 pattern).
    "mayor-office-entry",
    "mayor-office",
    "mayor-complaint-write",
    "mayor-complaint-receipt",
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

  // ── #1363 Lane B: S7 mayor-proposal routes ─────────────────────────────────
  // Mirrors the Buk-gu mayor-complaint-write/receipt journey shape
  // (열린구청장실 → 구청장에게 제안 → AI 제안작성 → 주민 검토 → 사전제출 STOP
  //  → 수령) with Seo-gu branding and data. App-owned surface only: no real
  // submit, no transport, no auth, no PII, no external channel anchor.

  function _renderMayorOfficeEntry() {
    var host = _viewHost();
    if (!host) return;
    host.innerHTML = "";

    var page = document.createElement("div");
    page.className = "bg-page bg-page--full bg-page--mayor";
    page.setAttribute("data-complaint-route", "mayor-office-entry");

    var main = document.createElement("main");
    main.className = "bg-mayor-hero";

    var copy = document.createElement("div");
    copy.className = "bg-mayor-hero__copy";
    copy.innerHTML =
      '<p class="bg-product-eyebrow">SEO-GU MAYOR PROPOSAL</p>' +
      '<h1>주민의 제안을 함께 작성합니다</h1>' +
      '<p>서구청 홈페이지의 주민제안 안내(참여대상·참여방법·처리절차)를 근거로 ' +
        'AI가 제안 초안 작성을 도와드립니다. 실제 접수는 서구청 공식 채널에서 ' +
        '주민이 직접 확인하고 진행해야 합니다.</p>';
    main.appendChild(copy);

    var actions = document.createElement("div");
    actions.className = "bg-mayor-hero__actions";

    var openBtn = document.createElement("button");
    openBtn.type = "button";
    openBtn.className = "bg-mayor-cta";
    openBtn.id = "btn-open-mayor-office";
    openBtn.setAttribute("data-action-target", "mayor-office");
    openBtn.innerHTML = '열린 구청장실 바로가기 <span aria-hidden="true">→</span>';
    actions.appendChild(openBtn);

    main.appendChild(actions);
    page.appendChild(main);

    var facts = document.createElement("section");
    facts.className = "bg-receipt-card";
    facts.setAttribute("data-grounded-facts", "mayor-proposal-guidance");
    facts.innerHTML =
      '<div><span>참여대상</span><strong>전 주민 (연령·거주지 제한 없음, 단체 가능)</strong></div>' +
      '<div><span>참여방법</span><strong>서구청 홈페이지 · 우편 · 팩스</strong></div>' +
      '<div><span>처리절차</span><strong>주민제안 접수 → 검토 → 처리결과 회신</strong></div>';
    page.appendChild(facts);

    host.appendChild(page);
  }

  function _renderMayorOffice() {
    var host = _viewHost();
    if (!host) return;
    host.innerHTML = "";

    var page = document.createElement("div");
    page.className = "bg-page bg-page--full bg-page--mayor";
    page.setAttribute("data-complaint-route", "mayor-office");

    var main = document.createElement("main");
    main.className = "bg-mayor-hero";

    var copy = document.createElement("div");
    copy.className = "bg-mayor-hero__copy";
    copy.innerHTML =
      '<p class="bg-product-eyebrow">MAYOR OFFICE</p>' +
      '<h1>열린 구청장실</h1>' +
      '<p>주민과 함께 만드는 서구의 비전과 소통 창구입니다.\n' +
        '아래에서 주민제안 작성을 시작할 수 있습니다.</p>';
    main.appendChild(copy);

    var actions = document.createElement("div");
    actions.className = "bg-mayor-hero__actions";
    actions.setAttribute("data-mayor-office-actions", "true");

    var proposeBtn = document.createElement("button");
    proposeBtn.type = "button";
    proposeBtn.className = "bg-mayor-cta";
    proposeBtn.id = "btn-mayor-message";
    proposeBtn.setAttribute("data-action-target", "mayor-complaint-write");
    proposeBtn.innerHTML = '구청장에게 제안하기 <span aria-hidden="true">→</span>';
    actions.appendChild(proposeBtn);

    main.appendChild(actions);
    page.appendChild(main);
    host.appendChild(page);
  }

  function _renderMayorComplaintWrite() {
    var host = _viewHost();
    if (!host) return;
    host.innerHTML = "";

    var page = document.createElement("div");
    page.className = "bg-page bg-page--full bg-page--mayor bg-page--mayor-writing";
    page.setAttribute("data-complaint-route", "mayor-complaint-write");

    var main = document.createElement("main");
    main.className = "bg-writing-main";

    var breadcrumb = document.createElement("nav");
    breadcrumb.className = "bg-product-breadcrumb";
    breadcrumb.setAttribute("aria-label", "경로");
    breadcrumb.innerHTML =
      '<span>홈</span><span aria-hidden="true">&rsaquo;</span>' +
      '<span>열린 구청장실</span><span aria-hidden="true">&rsaquo;</span>' +
      '<span>주민제안</span><span aria-hidden="true">&rsaquo;</span>' +
      '<span>AI 제안작성</span>';
    main.appendChild(breadcrumb);

    var heading = document.createElement("header");
    heading.className = "bg-writing-heading";
    heading.innerHTML =
      '<div><p class="bg-product-eyebrow">AI WRITING ASSIST</p><h1>구청장에게 제안하기</h1>' +
        '<p>주민의 제안을 편하게 말씀하시면 제목과 본문 초안으로 정리해 드립니다. 제출 전 반드시 내용을 직접 확인해 주세요.</p></div>' +
      '<span class="bg-writing-heading__badge">주민제안</span>';
    main.appendChild(heading);

    var layout = document.createElement("div");
    layout.className = "bg-writing-layout";

    var card = document.createElement("section");
    card.className = "bg-writing-card";
    card.setAttribute("aria-labelledby", "mayor-writing-title");
    card.setAttribute("data-pre-submit", "true");
    card.innerHTML =
      '<div class="bg-writing-card__top"><div><span>작성 단계</span><strong id="mayor-writing-title">제안 내용을 확인해 주세요</strong></div>' +
        '<div class="bg-writing-progress" aria-label="작성 진행률"><span class="is-done"></span><span class="is-active"></span><span></span></div></div>' +
      '<div class="bg-writing-field"><label for="mayor-write-title">제목 <b>필수</b></label>' +
        '<p>담당자가 내용을 빠르게 파악할 수 있도록 핵심을 담아 주세요.</p>' +
        '<input type="text" class="bg-dept-search__input bg-writing-input" id="mayor-write-title" maxlength="100" autocomplete="off" /></div>' +
      '<div class="bg-writing-field"><div class="bg-writing-field__label"><label for="mayor-write-content">내용 <b>필수</b></label><span>최대 2,000자</span></div>' +
        '<p>제안 배경, 원하는 조치를 편하게 말씀해 주세요. AI가 제안 문장으로 다듬습니다.</p>' +
        '<textarea id="mayor-write-content" maxlength="2000"></textarea></div>' +
      '<div class="bg-writing-consent"><span aria-hidden="true">✓</span><p><strong>제출 전 주민 확인</strong>AI는 초안만 작성하며 주민이 확인 버튼을 누르기 전에는 제출되지 않습니다.</p></div>';

    var actions = document.createElement("div");
    actions.className = "bg-writing-actions";
    actions.setAttribute("data-writing-actions", "true");

    var backBtn = document.createElement("button");
    backBtn.type = "button";
    backBtn.className = "bg-action-btn bg-action-btn--secondary";
    backBtn.setAttribute("data-action-target", "mayor-office");
    backBtn.textContent = "이전으로";
    actions.appendChild(backBtn);

    var submitBtn = document.createElement("button");
    submitBtn.type = "button";
    submitBtn.className = "bg-action-btn bg-action-btn--primary";
    submitBtn.id = "btn-mayor-submit";
    submitBtn.disabled = true;
    submitBtn.setAttribute("aria-disabled", "true");
    submitBtn.setAttribute("data-default-label", "검토 후 제출 가능");
    submitBtn.textContent = "검토 후 제출 가능";
    actions.appendChild(submitBtn);

    card.appendChild(actions);
    layout.appendChild(card);

    var assistant = document.createElement("aside");
    assistant.className = "bg-writing-assistant";
    assistant.setAttribute("aria-label", "AI 작성 도움 상태");
    assistant.innerHTML =
      '<div class="bg-writing-assistant__orb"><span>AI</span></div>' +
      '<p class="bg-product-eyebrow">SEOGU AI</p><h2>주민의 말은 그대로,<br>제안 문장은 더 명확하게</h2>' +
      '<ol><li class="is-done"><b>1</b><span><strong>핵심 내용 파악</strong>제안 배경과 요청사항을 구분합니다.</span></li>' +
        '<li class="is-active"><b>2</b><span><strong>제안 문장 작성</strong>정중하고 구체적인 문장으로 다듬습니다.</span></li>' +
        '<li><b>3</b><span><strong>주민 최종 확인</strong>수정하거나 제출 여부를 선택합니다.</span></li></ol>' +
      '<div class="bg-writing-assistant__tip"><span aria-hidden="true">✦</span><p>실제 주민제안 접수는 서구청 공식 채널에서 주민이 직접 진행해야 합니다.</p></div>';
    layout.appendChild(assistant);

    main.appendChild(layout);

    var safety = document.createElement("section");
    safety.className = "bg-writing-consent";
    safety.setAttribute("data-safety-notice", "true");
    safety.innerHTML =
      '<span aria-hidden="true">!</span><p><strong>STOP boundary</strong>이 화면은 AI 보조 초안 작성 영역입니다. ' +
        '실제 주민제안 접수는 서구청 공식 채널에서 주민이 직접 확인하고 진행해야 하며, 본 MVP는 제출을 대행하지 않습니다.</p>';
    main.appendChild(safety);

    page.appendChild(main);
    host.appendChild(page);

    backBtn.addEventListener("click", function () {
      navigateToRoute("mayor-office");
    });
  }

  function _renderMayorComplaintReceipt() {
    var host = _viewHost();
    if (!host) return;
    host.innerHTML = "";

    var page = document.createElement("div");
    page.className = "bg-page bg-page--full bg-page--mayor bg-page--mayor-receipt";
    page.setAttribute("data-complaint-route", "mayor-complaint-receipt");
    page.setAttribute("data-receipt-route", "mayor-complaint-receipt");

    var main = document.createElement("main");
    main.className = "bg-receipt-main";

    var mark = document.createElement("div");
    mark.className = "bg-receipt-mark";
    mark.setAttribute("aria-hidden", "true");
    mark.innerHTML = "<span>✓</span>";
    main.appendChild(mark);

    var eyebrow = document.createElement("p");
    eyebrow.className = "bg-product-eyebrow";
    eyebrow.textContent = "PROPOSAL READY";
    main.appendChild(eyebrow);

    var h1 = document.createElement("h1");
    h1.textContent = "제안 초안이 준비되었습니다";
    main.appendChild(h1);

    var desc = document.createElement("p");
    desc.innerHTML = "작성한 내용을 확인했습니다.<br>공식 제출은 서구청 공식 채널에서 시민이 직접 확인하고 진행합니다.";
    main.appendChild(desc);

    var card = document.createElement("section");
    card.className = "bg-receipt-card";
    card.setAttribute("data-receipt-summary", "true");
    card.innerHTML =
      '<div><span>작성 유형</span><strong>주민제안 (구청장에게 제안)</strong></div>' +
      '<div><span>현재 상태</span><strong class="is-accent">공식 제출 전</strong></div>' +
      '<div><span>다음 단계</span><strong>공식 채널에서 확인 및 제출</strong></div>';
    main.appendChild(card);

    page.appendChild(main);
    host.appendChild(page);
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
    } else if (routeId === "mayor-office-entry") {
      _clearHighlights();
      _renderMayorOfficeEntry();
    } else if (routeId === "mayor-office") {
      _clearHighlights();
      _renderMayorOffice();
    } else if (routeId === "mayor-complaint-write") {
      _clearHighlights();
      _renderMayorComplaintWrite();
    } else if (routeId === "mayor-complaint-receipt") {
      _clearHighlights();
      _renderMayorComplaintReceipt();
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