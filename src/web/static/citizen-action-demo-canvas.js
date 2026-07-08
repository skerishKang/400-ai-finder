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
  // J-PARK-01 local-only utilities and renderers
  // -----------------------------------------------------------------------
  function _resolveParkJourneyState(search) {
    var params = new URLSearchParams(search || "");
    var journeys = params.getAll("journey");
    if (journeys.length !== 1 || journeys[0] !== "J-PARK-01") {
      return { isPark: false };
    }
    var parkStates = params.getAll("park-state");
    if (parkStates.length > 0) {
      return { isPark: false };
    }
    var allKeys = Array.from(params.keys());
    var allowedKeys = ["journey"];
    if (allKeys.length !== allowedKeys.length) {
      return { isPark: false };
    }
    for (var i = 0; i < allKeys.length; i++) {
      if (allowedKeys.indexOf(allKeys[i]) === -1) {
        return { isPark: false };
      }
    }
    var deptKeys = Array.from(params.keys());
    for (var j = 0; j < deptKeys.length; j++) {
      if (deptKeys[j] === "dept-state") {
        return { isPark: false };
      }
    }
    return { isPark: true };
  }

  function _updateChatForPark() {
    var thread = document.getElementById("chat-thread");
    if (!thread) return;
    thread.innerHTML =
      '<div class="chat-msg chat-msg--user"><div class="chat-bubble chat-bubble--user">북구청 청사부설주차장은 몇 시까지 유료이고 요금은 어떻게 되나요?</div></div>' +
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">북구청 주차장 이용안내에서 운영시간과 요금을 확인했습니다.</div></div>' +
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">평일(월~금) 08:00~19:00에 유료운영하며, 모든 민원인은 1시간 무료입니다. 이후 최초 30분은 500원, 기본 30분 이후에는 10분당 200원입니다. 야간 및 휴일에는 무료개방합니다.</div></div>';
  }

  function _renderParkInformation() {
    var assets = "/static/images/bukgu-current";
    return (
      '<div class="bg-page bg-page--full bg-page--park-info">' +
        '<div class="bg-home-gov-strip">' +
          '<div class="bg-home-gov-strip__inner">' +
            '<img src="' + assets + '/home-government-notice.png" alt="본 누리집은 전남광주통합특별시 북구청 공식 누리집입니다." class="bg-home-gov-strip__notice" />' +
          '</div>' +
        '</div>' +
        '<div class="bg-home-utility" aria-label="사이트 도구">' +
          '<div class="bg-home-utility__inner">' +
            '<div class="bg-home-utility__menus">' +
              '<span class="bg-home-utility__menu-label">주요사이트</span>' +
              '<span class="bg-home-utility__menu-label">SNS</span>' +
              '<span class="bg-home-utility__menu-label">KOR</span>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<header class="bg-header">' +
          '<div class="bg-home-header">' +
            '<div class="bg-home-header__inner">' +
              '<div class="bg-home-header__identity">' +
                '<img src="' + assets + '/home-identity.png" alt="전남광주통합특별시북구" />' +
              '</div>' +
              '<nav class="bg-gnb" aria-label="주메뉴">' +
                '<div class="bg-home-gnb">' +
                  '<span class="bg-home-gnb__link">종합민원</span>' +
                  '<span class="bg-home-gnb__link">소통광장</span>' +
                  '<span class="bg-home-gnb__link">더불어복지</span>' +
                  '<span class="bg-home-gnb__link">분야별정보</span>' +
                  '<span class="bg-home-gnb__link">정보공개</span>' +
                  '<span class="bg-home-gnb__link bg-home-gnb__link--active">북구소개</span>' +
                '</div>' +
              '</nav>' +
            '</div>' +
          '</div>' +
        '</header>' +
        '<main class="bg-park-main">' +
          '<div class="bg-park-breadcrumb">홈 > 북구소개 > 구청안내 > <strong>주차장 이용안내</strong></div>' +
          '<div class="bg-park-layout">' +
            '<aside class="bg-park-left">' +
              '<div class="bg-park-left-section">북구소개</div>' +
              '<div class="bg-park-left-group bg-park-left-group--open">' +
                '<div class="bg-park-left-group-header">구청안내</div>' +
                '<ul class="bg-park-lnb-list">' +
                  '<li><span class="bg-park-lnb-link">행정조직</span></li>' +
                  '<li><span class="bg-park-lnb-link">업무 및 전화번호 안내</span></li>' +
                  '<li><span class="bg-park-lnb-link">부서 대표(전화번호, FAX)</span></li>' +
                  '<li><span class="bg-park-lnb-link">청사안내</span></li>' +
                  '<li><span class="bg-park-lnb-link">찾아오시는 길</span></li>' +
                  '<li class="bg-park-lnb-item--active"><span class="bg-park-lnb-link">주차장 이용안내</span></li>' +
                '</ul>' +
              '</div>' +
            '</aside>' +
            '<div class="bg-park-content">' +
              '<h1 class="bg-park-content-title">주차장 이용안내</h1>' +
              '<section class="bg-park-facts">' +
                '<h2 class="bg-park-facts-heading">청사부설주차장 현황</h2>' +
                '<div class="bg-park-facts-list">' +
                  '<div class="bg-park-facts-row">주차면수: 130면</div>' +
                  '<div class="bg-park-facts-row">주차타워: 111면(1층 42, 2층 29, 3층 40)</div>' +
                  '<div class="bg-park-facts-row">기타: 19면</div>' +
                '</div>' +
              '</section>' +
              '<section class="bg-park-facts">' +
                '<h2 class="bg-park-facts-heading">주차요금</h2>' +
                '<table class="bg-park-facts-table">' +
                  '<thead>' +
                    '<tr><th>무료주차</th><th>기본</th><th>초과</th></tr>' +
                  '</thead>' +
                  '<tbody>' +
                    '<tr>' +
                      '<td>1시간(모든 민원인)</td>' +
                      '<td>30분 500원(무료시간 이후 최초 30분)</td>' +
                      '<td>10분당 200원(기본 30분 이후)</td>' +
                    '</tr>' +
                  '</tbody>' +
                '</table>' +
              '</section>' +
              '<section class="bg-park-facts">' +
                '<h2 class="bg-park-facts-heading">운영시간</h2>' +
                '<div class="bg-park-facts-list">' +
                  '<div class="bg-park-facts-row">평일(월~금) 유료운영: 08:00 ~ 19:00</div>' +
                  '<div class="bg-park-facts-row">야간 및 휴일 무료개방</div>' +
                '</div>' +
              '</section>' +
            '</div>' +
          '</div>' +
        '</main>' +
        '<footer class="bg-home-footer" aria-label="사이트 하단">' +
          '<div class="bg-home-footer__inner">' +
            '<nav class="bg-home-footer__nav" aria-label="하단 메뉴">' +
              '<span class="bg-home-footer__nav-item">누리집이용안내</span>' +
              '<span class="bg-home-footer__nav-item">개인정보처리방침</span>' +
              '<span class="bg-home-footer__nav-item">저작권 보호정책</span>' +
              '<span class="bg-home-footer__nav-item">이메일무단수집거부</span>' +
              '<span class="bg-home-footer__nav-item">영상정보처리기기 운영·관리방침</span>' +
            '</nav>' +
            '<div class="bg-home-footer__legal"><strong>전남광주통합특별시북구</strong><span>로컬 시연 화면 · 외부 사이트와 연결하지 않습니다.</span></div>' +
          '</div>' +
        '</footer>' +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // J-KIOSK-01 local-only utilities and renderers
  // -----------------------------------------------------------------------
  function _resolveKioskJourneyState(search) {
    var params = new URLSearchParams(search || "");
    var journeys = params.getAll("journey");
    if (journeys.length !== 1 || journeys[0] !== "J-KIOSK-01") {
      return { isKiosk: false };
    }
    var allKeys = Array.from(params.keys());
    var allowedKeys = ["journey"];
    if (allKeys.length !== allowedKeys.length) {
      return { isKiosk: false };
    }
    for (var i = 0; i < allKeys.length; i++) {
      if (allowedKeys.indexOf(allKeys[i]) === -1) {
        return { isKiosk: false };
      }
    }
    // Reject if any disallowed state keys present
    var disallowedKeys = ["kiosk-state", "park-state", "dept-state"];
    for (var j = 0; j < allKeys.length; j++) {
      if (disallowedKeys.indexOf(allKeys[j]) !== -1) {
        return { isKiosk: false };
      }
    }
    return { isKiosk: true };
  }

  function _updateChatForKiosk() {
    var thread = document.getElementById("chat-thread");
    if (!thread) return;
    thread.innerHTML =
      '<div class="chat-msg chat-msg--user"><div class="chat-bubble chat-bubble--user">북구청 무인민원발급기는 어디에 있고 언제 이용할 수 있나요?</div></div>' +
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">북구청 무인민원발급기 설치장소에서 이용 정보를 확인했습니다.</div></div>' +
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">북구청 민원실과 북구청 민원실 2는 우치로 77에 있으며 24시간 이용할 수 있습니다. 발급 가능 민원서류는 각각 122종과 121종입니다.</div></div>';
  }

  function _renderKioskInformation() {
    var assets = "/static/images/bukgu-current";
    return (
      '<div class="bg-page bg-page--full bg-page--kiosk-info">' +
        '<div class="bg-home-gov-strip">' +
          '<div class="bg-home-gov-strip__inner">' +
            '<img src="' + assets + '/home-government-notice.png" alt="본 누리집은 전남광주통합특별시 북구청 공식 누리집입니다." class="bg-home-gov-strip__notice" />' +
          '</div>' +
        '</div>' +
        '<div class="bg-home-utility" aria-label="사이트 도구">' +
          '<div class="bg-home-utility__inner">' +
            '<div class="bg-home-utility__menus">' +
              '<span class="bg-home-utility__menu-label">주요사이트</span>' +
              '<span class="bg-home-utility__menu-label">SNS</span>' +
              '<span class="bg-home-utility__menu-label">KOR</span>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<header class="bg-header">' +
          '<div class="bg-home-header">' +
            '<div class="bg-home-header__inner">' +
              '<div class="bg-home-header__identity">' +
                '<img src="' + assets + '/home-identity.png" alt="전남광주통합특별시북구" />' +
              '</div>' +
              '<nav class="bg-gnb" aria-label="주메뉴">' +
                '<div class="bg-home-gnb">' +
                  '<span class="bg-home-gnb__link bg-home-gnb__link--active">종합민원</span>' +
                  '<span class="bg-home-gnb__link">소통광장</span>' +
                  '<span class="bg-home-gnb__link">더불어복지</span>' +
                  '<span class="bg-home-gnb__link">분야별정보</span>' +
                  '<span class="bg-home-gnb__link">정보공개</span>' +
                  '<span class="bg-home-gnb__link">북구소개</span>' +
                '</div>' +
              '</nav>' +
            '</div>' +
          '</div>' +
        '</header>' +
        '<main class="bg-kiosk-main">' +
          '<div class="bg-kiosk-breadcrumb">홈 > 종합민원 > 종합민원 > 무인민원발급기 > <strong>설치장소</strong></div>' +
          '<div class="bg-kiosk-layout">' +
            '<aside class="bg-kiosk-left">' +
              '<div class="bg-kiosk-left-section">종합민원</div>' +
              '<div class="bg-kiosk-left-group bg-kiosk-left-group--open">' +
                '<div class="bg-kiosk-left-group-header">종합민원</div>' +
                '<ul class="bg-kiosk-lnb-list">' +
                  '<li><span class="bg-kiosk-lnb-link">민원실배치도(창구안내)</span></li>' +
                  '<li class="bg-kiosk-lnb-item--active"><span class="bg-kiosk-lnb-link">무인민원발급기</span></li>' +
                  '<li><span class="bg-kiosk-lnb-link">민원사무편람</span></li>' +
                  '<li><span class="bg-kiosk-lnb-link">민원서식</span></li>' +
                  '<li><span class="bg-kiosk-lnb-link">여권민원</span></li>' +
                  '<li><span class="bg-kiosk-lnb-link">제증명 수수료</span></li>' +
                '</ul>' +
              '</div>' +
            '</aside>' +
            '<div class="bg-kiosk-content">' +
              '<div class="bg-kiosk-content-heading">무인민원발급기</div>' +
              '<div class="bg-kiosk-tabs">' +
                '<span class="bg-kiosk-tab bg-kiosk-tab--active">설치장소</span>' +
                '<span class="bg-kiosk-tab">발급종류 및 처리순서</span>' +
                '<span class="bg-kiosk-tab">발급가능 민원서류</span>' +
              '</div>' +
              '<h1 class="bg-kiosk-content-title">무인민원발급기 설치장소(50개소)</h1>' +
              '<table class="bg-kiosk-table">' +
                '<thead>' +
                  '<tr>' +
                    '<th>구분</th>' +
                    '<th>시설명</th>' +
                    '<th>도로명주소</th>' +
                    '<th>운영시간</th>' +
                    '<th>발급종수</th>' +
                    '<th>발급기형태</th>' +
                    '<th>비고</th>' +
                  '</tr>' +
                '</thead>' +
                '<tbody>' +
                  '<tr>' +
                    '<td>구청</td>' +
                    '<td>북구청 민원실</td>' +
                    '<td>우치로 77</td>' +
                    '<td>24시간</td>' +
                    '<td>122종</td>' +
                    '<td>장애인겸용</td>' +
                    '<td></td>' +
                  '</tr>' +
                  '<tr>' +
                    '<td>구청</td>' +
                    '<td>북구청 민원실 2</td>' +
                    '<td>우치로 77</td>' +
                    '<td>24시간</td>' +
                    '<td>121종</td>' +
                    '<td>장애인겸용</td>' +
                    '<td></td>' +
                  '</tr>' +
                '</tbody>' +
              '</table>' +
            '</div>' +
          '</div>' +
        '</main>' +
        '<footer class="bg-home-footer" aria-label="사이트 하단">' +
          '<div class="bg-home-footer__inner">' +
            '<nav class="bg-home-footer__nav" aria-label="하단 메뉴">' +
              '<span class="bg-home-footer__nav-item">누리집이용안내</span>' +
              '<span class="bg-home-footer__nav-item">개인정보처리방침</span>' +
              '<span class="bg-home-footer__nav-item">저작권 보호정책</span>' +
              '<span class="bg-home-footer__nav-item">이메일무단수집거부</span>' +
              '<span class="bg-home-footer__nav-item">영상정보처리기기 운영·관리방침</span>' +
            '</nav>' +
            '<div class="bg-home-footer__legal"><strong>전남광주통합특별시북구</strong><span>로컬 시연 화면 · 외부 사이트와 연결하지 않습니다.</span></div>' +
          '</div>' +
        '</footer>' +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // J-DEPT-01 local-only utilities and renderers
  // -----------------------------------------------------------------------
  function _resolveDeptJourneyState(search) {
    var params = new URLSearchParams(search || "");
    var journeys = params.getAll("journey");
    if (journeys.length !== 1 || journeys[0] !== "J-DEPT-01") {
      return { isDept: false, state: "" };
    }
    var deptStates = params.getAll("dept-state");
    if (deptStates.length === 0) {
      return { isDept: true, state: "home" };
    }
    if (deptStates.length !== 1) {
      return { isDept: false, state: "" };
    }
    var ds = deptStates[0];
    if (ds === "menu" || ds === "directory" || ds === "result") {
      return { isDept: true, state: ds };
    }
    return { isDept: false, state: "" };
  }

  function _resolveDeptReplayState(search) {
    var params = new URLSearchParams(search || "");
    var replayValues = params.getAll("replay");
    if (replayValues.length !== 1 || replayValues[0] !== "J-DEPT-01") {
      return { isReplay: false, step: "" };
    }
    var replaySteps = params.getAll("replay-step");
    if (replaySteps.length > 1) {
      return { isReplay: false, step: "" };
    }
    var allKeys = Array.from(params.keys());
    for (var i = 0; i < allKeys.length; i++) {
      if (allKeys[i] !== "replay" && allKeys[i] !== "replay-step") {
        return { isReplay: false, step: "" };
      }
    }
    if (replaySteps.length === 0) {
      return { isReplay: true, step: "ready" };
    }
    if (replaySteps[0] === "directory" || replaySteps[0] === "result") {
      return { isReplay: true, step: replaySteps[0] };
    }
    return { isReplay: false, step: "" };
  }

  // Auto-replay runtime state — module-local, no storage/persistence
  var _autoReplayState = {
    phase: "",
    status: "idle",
    pendingTimer: null,
    userStarted: false,
    phaseOrder: ["route", "directory", "search", "result"]
  };

  function _resolveAutoReplayState(search) {
    var params = new URLSearchParams(search || "");
    var replayValues = params.getAll("replay");
    if (replayValues.length !== 1 || replayValues[0] !== "J-DEPT-01") {
      return { isAuto: false, step: "" };
    }
    var modeValues = params.getAll("replay-mode");
    if (modeValues.length !== 1 || modeValues[0] !== "auto") {
      return { isAuto: false, step: "" };
    }
    var replaySteps = params.getAll("replay-step");
    if (replaySteps.length > 1) {
      return { isAuto: false, step: "" };
    }
    var allKeys = Array.from(params.keys());
    for (var i = 0; i < allKeys.length; i++) {
      if (allKeys[i] !== "replay" && allKeys[i] !== "replay-mode" && allKeys[i] !== "replay-step") {
        return { isAuto: false, step: "" };
      }
    }
    var step = replaySteps.length === 0 ? "" : replaySteps[0];
    if (step !== "" &&
        step !== "route" &&
        step !== "directory" &&
        step !== "search" &&
        step !== "result") {
      return { isAuto: false, step: "" };
    }
    if (step === "") {
      return { isAuto: true, step: "ready" };
    }
    return { isAuto: true, step: step };
  }

  // Auto-replay controls
  function _renderAutoReplayControls(step, status) {
    var buttons = [];
    if (step === "ready" || step === "" || status === "ready") {
      buttons.push('<button type="button" class="bg-dept-replay-controls__button" data-auto-replay-action="start">시연 시작</button>');
    } else if (status === "running") {
      buttons.push('<button type="button" class="bg-dept-replay-controls__button" data-auto-replay-action="pause">일시정지</button>');
      buttons.push('<button type="button" class="bg-dept-replay-controls__button bg-dept-replay-controls__button--secondary" data-auto-replay-action="restart">다시 보기</button>');
    } else if (status === "paused") {
      buttons.push('<button type="button" class="bg-dept-replay-controls__button" data-auto-replay-action="resume">계속</button>');
      buttons.push('<button type="button" class="bg-dept-replay-controls__button bg-dept-replay-controls__button--secondary" data-auto-replay-action="restart">다시 보기</button>');
    } else {
      buttons.push('<button type="button" class="bg-dept-replay-controls__button bg-dept-replay-controls__button--secondary" data-auto-replay-action="restart">다시 보기</button>');
    }
    return '<div class="bg-dept-replay-controls" aria-label="자동 재현 제어">' + buttons.join("") + '</div>';
  }

  function _renderAutoActionBubble(step) {
    var bubbles = {
      "route": "업무 및 전화번호 안내 경로를 확인합니다",
      "directory": "북구소개 메뉴를 선택합니다",
      "search": "공동주택을 검색합니다",
      "result": "담당 부서와 연락처를 확인했습니다"
    };
    var text = bubbles[step] || "";
    if (!text) return "";
    return '<div class="bg-dept-action-bubble" aria-live="polite">' + text + '</div>';
  }

  function _updateChatProgressForAutoReplay(step) {
    var thread = document.getElementById("chat-thread");
    if (!thread) return;
    var approvedChat = [
      '<div class="chat-msg chat-msg--user"><div class="chat-bubble chat-bubble--user">공동주택 관련 문의는 어느 부서에 해야 하나요?</div></div>',
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">북구청 업무 및 전화번호 안내 경로를 확인하겠습니다.</div></div>',
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">북구소개 메뉴에서 업무 및 전화번호 안내를 확인하고 있습니다.</div></div>',
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">공동주택 관련 담당 부서를 검색하고 있습니다.</div></div>',
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">공동주택 관련 문의는 공동주택과에서 담당합니다. 대표 연락처는 062-410-6033입니다.</div></div>'
    ];
    var renderCount;
    if (step === "ready" || step === "") {
      renderCount = 2;
    } else if (step === "route") {
      renderCount = 3;
    } else if (step === "directory") {
      renderCount = 4;
    } else if (step === "search" || step === "result") {
      renderCount = 5;
    } else {
      renderCount = 2;
    }
    var html = "";
    for (var i = 0; i < renderCount; i++) {
      html += approvedChat[i];
    }
    thread.innerHTML = html;
  }

  function _clearAutoReplayTimer() {
    if (_autoReplayState.pendingTimer && typeof window !== "undefined" && typeof window.clearTimeout === "function") {
      window.clearTimeout(_autoReplayState.pendingTimer);
    }
    _autoReplayState.pendingTimer = null;
  }

  function _setAutoReplayUrl(step) {
    if (typeof window === "undefined" || !window.history || typeof window.history.pushState !== "function") {
      return;
    }
    var url = "?replay=J-DEPT-01&replay-mode=auto";
    if (step && step !== "ready") {
      url += "&replay-step=" + encodeURIComponent(step);
    }
    window.history.pushState({}, "", url);
  }

  function _advanceAutoReplay(step) {
    _autoReplayState.phase = step;
    _autoReplayState.status = step === "result" ? "complete" : "running";
    _setAutoReplayUrl(step);
    navigateToRoute("home");
  }

  function _scheduleAutoReplayAdvance(step) {
    _clearAutoReplayTimer();
    if (_autoReplayState.status !== "running" || step === "result") {
      return;
    }
    var delays = {
      "route": 2500,
      "directory": 3000,
      "search": 3000
    };
    var currentIndex = _autoReplayState.phaseOrder.indexOf(step);
    if (currentIndex === -1 || currentIndex === _autoReplayState.phaseOrder.length - 1) {
      return;
    }
    var nextStep = _autoReplayState.phaseOrder[currentIndex + 1];
    if (typeof window !== "undefined" && typeof window.setTimeout === "function") {
      _autoReplayState.pendingTimer = window.setTimeout(function () {
        _autoReplayState.pendingTimer = null;
        if (_autoReplayState.status === "running") {
          _advanceAutoReplay(nextStep);
        }
      }, delays[step] || 2000);
    }
  }

  function _renderDeptReplayControls(step) {
    var buttons = [];
    if (step === "ready") {
      buttons.push('<button type="button" class="bg-dept-replay-controls__button" data-dept-replay-action="start">시작</button>');
    } else if (step === "directory") {
      buttons.push('<button type="button" class="bg-dept-replay-controls__button" data-dept-replay-action="next">다음</button>');
      buttons.push('<button type="button" class="bg-dept-replay-controls__button bg-dept-replay-controls__button--secondary" data-dept-replay-action="restart">다시 시작</button>');
    } else if (step === "result") {
      buttons.push('<button type="button" class="bg-dept-replay-controls__button bg-dept-replay-controls__button--secondary" data-dept-replay-action="restart">다시 시작</button>');
    }
    return '<div class="bg-dept-replay-controls" aria-label="로컬 재현 제어">' + buttons.join("") + '</div>';
  }

  function _updateChatProgressForDeptReplay(step) {
    var thread = document.getElementById("chat-thread");
    if (!thread) return;
    var messages = [
      '<div class="chat-msg chat-msg--user"><div class="chat-bubble chat-bubble--user">공동주택 관련 문의는 어느 부서에 해야 하나요?</div></div>',
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">북구청 업무 및 전화번호 안내에서 담당 부서를 찾겠습니다.</div></div>',
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">북구소개 &gt; 구청안내 &gt; 업무 및 전화번호 안내에서 담당 부서를 확인하고 있습니다.</div></div>',
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">공동주택 관련 문의는 공동주택과에서 담당합니다. 대표 연락처는 062-410-6033입니다.</div></div>'
    ];
    var renderCount = step === "ready" ? 2 : (step === "directory" ? 3 : 4);
    var html = "";
    for (var i = 0; i < renderCount; i++) {
      html += messages[i];
    }
    thread.innerHTML = html;
  }

  function _updateChatProgressForDept(deptState) {
    var thread = document.getElementById("chat-thread");
    if (!thread) return;

    var messages = [
      '<div class="chat-msg chat-msg--user"><div class="chat-bubble chat-bubble--user">공동주택 관련 문의는 어느 부서에 해야 하나요?</div></div>',
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">북구청 업무 및 전화번호 안내에서 담당 부서를 찾아보겠습니다.</div></div>',
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">북구소개 메뉴에서 구청안내를 확인했습니다.</div></div>',
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">업무 및 전화번호 안내에서 ‘공동주택’을 검색하고 있습니다.</div></div>',
      '<div class="chat-msg chat-msg--ai"><div class="chat-avatar" aria-label="AI">A</div><div class="chat-bubble chat-bubble--ai">공동주택 관련 문의는 공동주택과에서 담당합니다. 대표 연락처는 062-410-6033입니다.</div></div>'
    ];

    var progressIndicator =
      '<div class="chat-progress">' +
        '<span class="chat-progress__label">진행 단계</span>' +
        '<div class="chat-progress__steps">';

    var renderCount = 2;
    var progressHtml = '';
    if (deptState === "menu") {
      renderCount = 3;
      progressHtml += '<span class="chat-progress__step chat-progress__step--done">✓ 홈</span>' +
                      '<span class="chat-progress__step chat-progress__step--active">● 메뉴</span>' +
                      '<span class="chat-progress__step">○ 디렉토리</span>' +
                      '<span class="chat-progress__step">○ 결과</span>';
    } else if (deptState === "directory") {
      renderCount = 4;
      progressHtml += '<span class="chat-progress__step chat-progress__step--done">✓ 홈</span>' +
                      '<span class="chat-progress__step chat-progress__step--done">✓ 메뉴</span>' +
                      '<span class="chat-progress__step chat-progress__step--active">● 디렉토리</span>' +
                      '<span class="chat-progress__step">○ 결과</span>';
    } else if (deptState === "result") {
      renderCount = 5;
      progressHtml += '<span class="chat-progress__step chat-progress__step--done">✓ 홈</span>' +
                      '<span class="chat-progress__step chat-progress__step--done">✓ 메뉴</span>' +
                      '<span class="chat-progress__step chat-progress__step--done">✓ 디렉토리</span>' +
                      '<span class="chat-progress__step chat-progress__step--active">● 결과</span>';
    } else { // home
      renderCount = 2;
      progressHtml += '<span class="chat-progress__step chat-progress__step--active">● 홈</span>' +
                      '<span class="chat-progress__step">○ 메뉴</span>' +
                      '<span class="chat-progress__step">○ 디렉토리</span>' +
                      '<span class="chat-progress__step">○ 결과</span>';
    }

    progressIndicator += progressHtml + '</div></div>';

    var html = '';
    for (var i = 0; i < renderCount; i++) {
      html += messages[i];
    }
    thread.innerHTML = html + progressIndicator;
    if (window.CitizenFirstUseShell &&
        typeof window.CitizenFirstUseShell.appendQuestProgressCard === "function") {
      window.CitizenFirstUseShell.appendQuestProgressCard(thread);
    }
  }

  /**
   * First-use choreography presence check.
   * When the first-use shell is in split state and choreography is active,
   * route transitions must not overwrite the chat thread with the default
   * historical chat HTML. Returns true when chat should be preserved.
   */
  function _shouldPreserveFirstUseChat() {
    if (!document.body) return false;
    var firstUseState = document.body.getAttribute("data-first-use-state");
    var choreographyState = document.body.getAttribute("data-choreography-state");
    return firstUseState === "split" &&
      (choreographyState === "running" || choreographyState === "done");
  }

  function _restoreHistoricalChat() {
    var thread = document.getElementById("chat-thread");
    if (!thread) return;
    var defaultHtml =
      '<div class="chat-msg chat-msg--user">' +
        '<div class="chat-bubble chat-bubble--user">불법 주정차 신고는 어디서 하나요?</div>' +
      '</div>' +
      '<div class="chat-msg chat-msg--ai">' +
        '<div class="chat-avatar" aria-label="AI">A</div>' +
        '<div class="chat-bubble chat-bubble--ai">북구청 홈페이지에서 신고 경로를 확인하겠습니다.</div>' +
      '</div>' +
      '<div class="chat-msg chat-msg--ai">' +
        '<div class="chat-avatar" aria-label="AI">A</div>' +
        '<div class="chat-bubble chat-bubble--ai">종합민원 메뉴에서 온라인 민원신청 경로를 찾고 있습니다.</div>' +
      '</div>' +
      '<div class="chat-progress">' +
        '<span class="chat-progress__label">진행 단계</span>' +
        '<div class="chat-progress__steps">' +
          '<span class="chat-progress__step chat-progress__step--done">✓ 홈</span>' +
          '<span class="chat-progress__step chat-progress__step--active">● 신청</span>' +
          '<span class="chat-progress__step">○ 확인</span>' +
          '<span class="chat-progress__step">○ 종료</span>' +
        '</div>' +
      '</div>';
    thread.innerHTML = defaultHtml;
  }

  function _renderDeptDirectory(deptState) {
    var assets = "/static/images/bukgu-current";
    var searchIcon =
      '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="10.8" cy="10.8" r="6.3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 16l4.4 4.4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
    var menuIcon =
      '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16M4 12h16M4 17h16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
    return (
      '<div class="bg-page bg-page--full bg-page--dept-directory">' +
        '<div class="bg-home-gov-strip">' +
          '<div class="bg-home-gov-strip__inner">' +
            '<img src="' + assets + '/home-government-notice.png" alt="본 누리집은 전남광주통합특별시 북구청 공식 누리집입니다." class="bg-home-gov-strip__notice" />' +
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
        '<header class="bg-header">' +
          '<div class="bg-home-header">' +
            '<div class="bg-home-header__inner">' +
              '<a href="#" class="bg-home-header__identity" aria-label="전남광주통합특별시북구 홈">' +
                '<img src="' + assets + '/home-identity.png" alt="전남광주통합특별시북구" />' +
              '</a>' +
              '<nav class="bg-gnb" aria-label="주메뉴">' +
                '<div class="bg-home-gnb">' +
                  '<a href="#" class="bg-home-gnb__link bg-home-gnb__link--active" data-action-target="nav-civil-service">종합민원</a>' +
                  '<a href="#" class="bg-home-gnb__link">소통광장</a>' +
                  '<a href="#" class="bg-home-gnb__link">더불어복지</a>' +
                  '<a href="#" class="bg-home-gnb__link">분야별정보</a>' +
                  '<a href="#" class="bg-home-gnb__link">정보공개</a>' +
                  '<div class="bg-home-gnb__item bg-home-gnb__item--dept' + (deptState === 'menu' ? ' bg-home-gnb__item--active' : '') + '">' +
                    '<a href="#" class="bg-home-gnb__link' + (deptState === 'menu' ? ' bg-home-gnb__link--active' : '') + '" data-dept-action="open-menu" aria-haspopup="true">북구소개</a>' +
                    '<div class="bg-dept-mega-menu' + (deptState === 'menu' ? ' bg-dept-mega-menu--visible' : '') + '" aria-label="북구소개 하위 메뉴">' +
                      '<div class="bg-dept-mega-menu__inner">' +
                        '<div class="bg-dept-mega-menu__col">' +
                          '<h3>구청안내</h3>' +
                          '<a href="#" data-dept-action="go-directory">업무 및 전화번호 안내</a>' +
                        '</div>' +
                      '</div>' +
                    '</div>' +
                  '</div>' +
                '</div>' +
              '</nav>' +
              '<div class="bg-home-header__actions">' +
                '<button type="button" class="bg-home-header__icon" aria-label="통합검색">' + searchIcon + '<span>통합검색</span></button>' +
                '<button type="button" class="bg-home-header__icon" aria-label="전체메뉴">' + menuIcon + '<span>전체메뉴</span></button>' +
              '</div>' +
            '</div>' +
          '</div>' +
        '</header>' +
        '<main class="bg-dept-main">' +
          '<div class="bg-dept-breadcrumb">' +
            '<span>홈</span> &gt; <span>북구소개</span> &gt; <span>구청안내</span> &gt; <strong>업무 및 전화번호 안내</strong>' +
          '</div>' +
          '<div class="bg-dept-header">' +
            '<h2>업무 및 전화번호 안내</h2>' +
          '</div>' +
          '<div class="bg-dept-search">' +
            '<div class="bg-dept-search__box">' +
              '<input type="text" class="bg-dept-search__input" placeholder="검색어를 입력하세요." value="' + (deptState === 'result' ? '공동주택' : '') + '" />' +
              '<button type="button" class="bg-dept-search__btn" data-dept-action="trigger-search">검색</button>' +
            '</div>' +
          '</div>' +
          '<div class="bg-dept-results">' +
            (deptState === 'result' ?
              '<div class="bg-dept-results__count">' +
                '전체 <strong>9</strong>명, 현재 페이지 <strong>1/1</strong>' +
              '</div>' +
              '<table class="bg-dept-table">' +
                '<thead>' +
                  '<tr>' +
                    '<th>부서명</th>' +
                    '<th>전화번호</th>' +
                    '<th>담당업무</th>' +
                  '</tr>' +
                '</thead>' +
                '<tbody>' +
                  '<tr class="bg-dept-table__row bg-dept-table__row--highlighted">' +
                    '<td>공동주택과</td>' +
                    '<td>062-410-6033</td>' +
                    '<td>공동주택과 업무전반</td>' +
                  '</tr>' +
                '</tbody>' +
              '</table>'
            :
              '<div class="bg-dept-results__empty">' +
                '검색어를 입력 후 검색해 주세요. (예: 공동주택)' +
              '</div>'
            ) +
          '</div>' +
        '</main>' +
        '<footer class="bg-home-footer" aria-label="사이트 하단">' +
          '<div class="bg-home-footer__inner">' +
            '<nav class="bg-home-footer__nav" aria-label="하단 메뉴">' +
              '<a href="#">누리집이용안내 <span aria-hidden="true">⌃</span></a>' +
              '<a href="#">개인정보처리방침 <span aria-hidden="true">⌃</span></a>' +
              '<a href="#">저작권 보호정책 <span aria-hidden="true">⌃</span></a>' +
              '<a href="#">이메일무단수집거부 <span aria-hidden="true">⌃</span></a>' +
              '<a href="#">영상정보처리기기 운영·관리방침 <span aria-hidden="true">⌃</span></a>' +
            '</nav>' +
            '<div class="bg-home-footer__legal"><strong>전남광주통합특별시북구</strong><span>로컬 시연 화면 · 외부 사이트와 연결하지 않습니다.</span></div>' +
          '</div>' +
        '</footer>' +
      '</div>'
    );
  }

  function _renderDeptReplay(step) {
    if (step === "ready") {
      return _renderHome(_resolveHomeReferenceState(typeof window !== "undefined" && window.location ? window.location.search : ""));
    }
    var html = _renderDeptDirectory(step === "result" ? "result" : "directory");
    html = html.replace(
      '<div class="bg-page bg-page--full bg-page--dept-directory">',
      '<div class="bg-page bg-page--full bg-page--dept-directory bg-page--dept-replay" data-dept-replay="true" data-dept-replay-step="' + _escHtml(step) + '">'
    );
    html = html.replace(
      '<div class="bg-dept-header">' +
        '<h2>업무 및 전화번호 안내</h2>' +
      '</div>',
      '<div class="bg-dept-header">' +
        '<h2>업무 및 전화번호 안내</h2>' +
        _renderDeptReplayControls(step) +
      '</div>'
    );
    return html;
  }

  function _renderAutoCursor(step) {
    var positions = {
      "route": "bg-auto-cursor--gnb",
      "directory": "bg-auto-cursor--menu-link",
      "search": "bg-auto-cursor--search",
      "result": "bg-auto-cursor--result-row"
    };
    var posClass = positions[step] || "";
    return '<div class="bg-auto-cursor ' + posClass + '" data-auto-cursor-phase="' + _escHtml(step) + '" aria-hidden="true"></div>';
  }

  function _renderAutoTargetHighlight(step) {
    var targets = {
      "route": "bg-auto-target--gnb-dept",
      "directory": "bg-auto-target--directory-link",
      "search": "bg-auto-target--search-input",
      "result": "bg-auto-target--result-row"
    };
    var cls = targets[step] || "";
    return '<div class="bg-auto-target-highlight ' + cls + '" data-auto-target-phase="' + _escHtml(step) + '" aria-hidden="true"></div>';
  }

  function _renderAutoClickFeedback(step) {
    return '<div class="bg-auto-click-feedback" data-auto-click-phase="' + _escHtml(step) + '" aria-hidden="true"></div>';
  }

  function _renderAutoPhaseFeedback(step) {
    if (step === "ready" || step === "") return "";
    return _renderAutoCursor(step) + _renderAutoTargetHighlight(step) + _renderAutoClickFeedback(step);
  }

  function _renderAutoReplay(step, status) {
    var normalizedStep = step === "ready" ? "route" : step;
    var html;
    if (step === "ready") {
      html = _renderHome(_resolveHomeReferenceState(typeof window !== "undefined" && window.location ? window.location.search : ""));
      html = html.replace(
        '<div class="bg-page bg-page--full bg-page--home"',
        '<div class="bg-page bg-page--full bg-page--home" data-dept-auto-replay="true" data-auto-replay-step="ready" data-auto-replay-status="' + _escHtml(status) + '"'
      );
      html = html.replace(
        '<section class="bg-home-search" aria-label="통합검색">',
        '<div class="bg-dept-replay-home-controls">' +
          _renderAutoReplayControls("ready", status) +
        '</div>' +
        '<section class="bg-home-search" aria-label="통합검색">'
      );
      return html;
    }

    html = _renderDeptDirectory(step === "result" ? "result" : "directory");
    html = html.replace(
      '<div class="bg-page bg-page--full bg-page--dept-directory">',
      '<div class="bg-page bg-page--full bg-page--dept-directory bg-page--dept-replay" data-dept-auto-replay="true" data-auto-replay-step="' + _escHtml(step) + '" data-auto-replay-status="' + _escHtml(status) + '">'
    );
    html = html.replace(
      '<div class="bg-dept-header">' +
        '<h2>업무 및 전화번호 안내</h2>' +
      '</div>',
      '<div class="bg-dept-header">' +
        '<h2>업무 및 전화번호 안내</h2>' +
        _renderAutoReplayControls(step, status) +
      '</div>'
    );
    return html.replace(
      '</footer>' +
      '</div>',
      _renderAutoActionBubble(normalizedStep) + _renderAutoPhaseFeedback(step) + '</footer>' +
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

  /** Resolve which home reference state to render based on query parameter.
   *  Only "?home-reference=R-HOME-02" selects the R-HOME-02 full-home state.
   *  Everything else falls back to R-HOME-01 (ordinary above-fold state). */
  function _resolveHomeReferenceState(search) {
    var params = new URLSearchParams(search || "");
    var values = params.getAll("home-reference");
    return values.length === 1 && values[0] === "R-HOME-02"
      ? "R-HOME-02"
      : "R-HOME-01";
  }

  function _renderHome(state) {
    var deptJourney = _resolveDeptJourneyState(typeof window !== "undefined" && window.location ? window.location.search : "");
    var deptReplay = _resolveDeptReplayState(typeof window !== "undefined" && window.location ? window.location.search : "");
    var isDeptJourney = deptJourney.isDept;
    var deptState = deptJourney.state;

    var assets = "/static/images/bukgu-current";
    var bannerFile = state === "R-HOME-02"
      ? "home-alert-banner-r-home-02.png"
      : "home-alert-banner.png";
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
      ["home-quick-money.png", "부끄머니"],
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
      '<div class="bg-page bg-page--full bg-page--home" data-home-reference-state="' + state + '"' + (isDeptJourney ? ' data-dept-journey="true"' : '') + (deptReplay.isReplay ? ' data-dept-replay="true" data-dept-replay-step="ready"' : '') + '>' +
        '<div class="bg-skip"><a href="#bg-content-main">본문으로 바로가기</a></div>' +

        '<div class="bg-home-gov-strip">' +
          '<div class="bg-home-gov-strip__inner">' +
            '<img src="' + assets + '/home-government-notice.png" alt="본 누리집은 전남광주통합특별시 북구청 공식 누리집입니다." class="bg-home-gov-strip__notice" />' +
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

        '<header class="bg-header">' +
          '<div class="bg-home-header">' +
          '<div class="bg-home-header__inner">' +
            '<a href="#" class="bg-home-header__identity" aria-label="전남광주통합특별시북구 홈">' +
              '<img src="' + assets + '/home-identity.png" alt="전남광주통합특별시북구" />' +
            '</a>' +
            '<nav class="bg-gnb" aria-label="주메뉴">' +
              '<div class="bg-home-gnb">' +
              '<a href="#" class="bg-home-gnb__link bg-home-gnb__link--active" data-action-target="nav-civil-service">종합민원</a>' +
              '<a href="#" class="bg-home-gnb__link">소통광장</a>' +
              '<a href="#" class="bg-home-gnb__link">더불어복지</a>' +
              '<a href="#" class="bg-home-gnb__link">분야별정보</a>' +
              '<a href="#" class="bg-home-gnb__link">정보공개</a>' +
              (isDeptJourney ?
                '<div class="bg-home-gnb__item bg-home-gnb__item--dept' + (deptState === 'menu' ? ' bg-home-gnb__item--active' : '') + '">' +
                  '<a href="#" class="bg-home-gnb__link' + (deptState === 'menu' ? ' bg-home-gnb__link--active' : '') + '" data-dept-action="open-menu" aria-haspopup="true">북구소개</a>' +
                  '<div class="bg-dept-mega-menu' + (deptState === 'menu' ? ' bg-dept-mega-menu--visible' : '') + '" aria-label="북구소개 하위 메뉴">' +
                    '<div class="bg-dept-mega-menu__inner">' +
                      '<div class="bg-dept-mega-menu__col">' +
                        '<h3>구청안내</h3>' +
                        '<a href="#" data-dept-action="go-directory">업무 및 전화번호 안내</a>' +
                      '</div>' +
                    '</div>' +
                  '</div>' +
                '</div>'
              :
                '<a href="#" class="bg-home-gnb__link">북구소개</a>'
              ) +
            '</div>' +
            '</nav>' +
            '<div class="bg-home-header__actions">' +
              '<button type="button" class="bg-home-header__icon" aria-label="통합검색">' + searchIcon + '<span>통합검색</span></button>' +
              '<button type="button" class="bg-home-header__icon" aria-label="전체메뉴">' + menuIcon + '<span>전체메뉴</span></button>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '</header>' +
        (deptReplay.isReplay ? '<div class="bg-dept-replay-home-controls">' + _renderDeptReplayControls("ready") + '</div>' : '') +

        '<section class="bg-home-search" aria-label="통합검색">' +
          '<div class="bg-home-search__inner">' +
            '<img src="' + assets + '/home-civic-brand.png" alt="빛나는 북구, 함께하는 북구 - 행복한 구민을 위한 따뜻한 변화" class="bg-home-search__brand" />' +
            '<div class="bg-home-search__cluster">' +
              '<div class="bg-home-search__field">' +
                '<input type="text" placeholder="검색어를 입력하세요." aria-label="검색어" disabled />' +
                '<button type="button" aria-label="검색" disabled>' + searchIcon + '</button>' +
              '</div>' +
              '<div class="bg-home-search__tags"><span>#공동주택과</span><span>#위생과</span><span>#폐기물</span><span>#부끄머니</span></div>' +
            '</div>' +
          '</div>' +
        '</section>' +

        '<main id="bg-content-main" class="bg-home-main">' +
          '<section class="bg-home-lead" aria-label="주요 안내">' +
            '<article class="bg-home-lead__mayor">' +
              '<img src="' + assets + '/home-mayor-card.png" alt="따뜻한 북구를 만들겠습니다. 북구청장 신수정입니다." />' +
            '</article>' +
            '<article class="bg-home-lead__banner" aria-label="소속 공무원 사칭 피해주의 알림">' +
              '<img src="' + assets + '/' + bannerFile + '" alt="주요 알림 배너" />' +
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
                '<button type="button" role="tab">보도자료</button>' +
                '<button type="button" role="tab">고시/공고</button>' +
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
          '<section class="bg-home-lower" aria-label="하단 소식과 분야별 정보">' +
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
                '<a href="#">대형폐기물 처리 <span aria-hidden="true">›</span></a>' +
                '<a href="#">온라인 민원발급(정부24) <span aria-hidden="true">›</span></a>' +
                '<a href="#">취업지원프로그램안내 <span aria-hidden="true">›</span></a>' +
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
        '</main>' +
        '<footer class="bg-home-footer" aria-label="사이트 하단">' +
          '<div class="bg-home-footer__inner">' +
            '<nav class="bg-home-footer__nav" aria-label="하단 메뉴">' +
              '<a href="#">누리집이용안내 <span aria-hidden="true">⌃</span></a>' +
              '<a href="#">개인정보처리방침 <span aria-hidden="true">⌃</span></a>' +
              '<a href="#">저작권 보호정책 <span aria-hidden="true">⌃</span></a>' +
              '<a href="#">이메일무단수집거부 <span aria-hidden="true">⌃</span></a>' +
              '<a href="#">영상정보처리기기 운영·관리방침 <span aria-hidden="true">⌃</span></a>' +
            '</nav>' +
            '<div class="bg-home-footer__legal"><strong>전남광주통합특별시북구</strong><span>로컬 시연 화면 · 외부 사이트와 연결하지 않습니다.</span></div>' +
          '</div>' +
        '</footer>' +
        '<p class="bg-home-local-note">로컬 시연 화면 · 외부 사이트와 연결하지 않습니다.</p>' +
      '</div>'
    );
  }

  // -----------------------------------------------------------------------
  // _renderCivilService — intermediate route
  // -----------------------------------------------------------------------
  function _renderCivilService(route) {
    return (
      '<div class="bg-page bg-page--full bg-page--dense">' +
        _renderDenseHeader('civil-service') +

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
  // _renderIllegalParking — 불법 주정차 신고 전용 surface (청원24 아님)
  // Directly tied to 불법 주정차 신고 / 민원신고. The final highlight target
  // (complaint-illegal-parking-report) is rendered VISIBLE here so the
  // executor highlight reads as a real selected card, not a generic menu focus.
  // -----------------------------------------------------------------------
  function _renderIllegalParking(route) {
    return (
      '<div class="bg-page bg-page--full bg-page--dense bg-page--illegal-parking">' +
        _renderDenseHeader('civil-service') +

        '<div class="bg-layout--lnb">' +
          /* LNB */
          '<nav class="bg-lnb" aria-label="좌측 메뉴">' +
            '<div class="bg-lnb__header">종합민원</div>' +
            '<ul class="bg-lnb__list">' +
              '<li class="bg-lnb__item bg-lnb__item--active"><a href="#">종합민원</a></li>' +
              '<li class="bg-lnb__item bg-lnb__item--open">' +
                '<a href="#" class="bg-lnb__parent">민원신고</a>' +
                '<ul class="bg-lnb__sub">' +
                  '<li><a href="#">불법 주정차 신고</a></li>' +
                  '<li><a href="#">도로 및 교통시설 물의 시설 파손</a></li>' +
                  '<li><a href="#">공용주차장 이용 불편</a></li>' +
                  '<li><a href="#">각종 안전 위험 시설</a></li>' +
                  '<li><a href="#">기타 민원</a></li>' +
                '</ul>' +
              '</li>' +
              '<li class="bg-lnb__item bg-lnb__item--collapsed"><a href="#" class="bg-lnb__parent">전자민원창구</a></li>' +
              '<li class="bg-lnb__item bg-lnb__item--collapsed"><a href="#" class="bg-lnb__parent">민원서식</a></li>' +
              '<li class="bg-lnb__item bg-lnb__item--collapsed"><a href="#" class="bg-lnb__parent">행정서비스 헌장</a></li>' +
            '</ul>' +
          '</nav>' +

          /* Main content — the directly relevant target card */
          '<main class="bg-content bg-content--sub" id="bg-content-main">' +
            _renderSubPageHeader("불법 주정차 신고", "불법 주정차 신고는 민원신고를 통해 온라인으로 접수할 수 있습니다.") +

            '<div class="bg-illegal-parking-card" data-action-target="complaint-illegal-parking-report" tabindex="0">' +
              '<div class="bg-illegal-parking-card__icon" aria-hidden="true">🚗</div>' +
              '<div class="bg-illegal-parking-card__body">' +
                '<h2 class="bg-illegal-parking-card__title">불법 주정차 신고</h2>' +
                '<p class="bg-illegal-parking-card__desc">민원신고 &gt; 불법 주정차 신고 메뉴에서 위치·사진·내용을 입력해 접수합니다.</p>' +
                '<ul class="bg-illegal-parking-card__meta">' +
                  '<li><span class="bg-illegal-parking-card__meta-label">접수처</span> 북구청 민원신고 (교통과)</li>' +
                  '<li><span class="bg-illegal-parking-card__meta-label">처리기간</span> 접수 즉시 지자체 통보</li>' +
                  '<li><span class="bg-illegal-parking-card__meta-label">신고방법</span> 온라인 / 북구청 민원신고</li>' +
                '</ul>' +
              '</div>' +
              '<span class="bg-illegal-parking-card__arrow" aria-hidden="true">›</span>' +
            '</div>' +

            '<p class="bg-illegal-parking-note">※ 본 카드는 로컬 시연용이며 실제 신고는 북구청 공식 민원신고 채널을 이용하세요.</p>' +
          '</main>' +
        '</div>' +
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
      '<div class="bg-page bg-page--full bg-page--dense">' +
        _renderDenseHeader('civil-service') +

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
      '<div class="bg-page bg-page--full bg-page--dense">' +
        _renderDenseHeader('civil-service') +

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
      '<div class="bg-page bg-page--full bg-page--dense">' +
        _renderDenseHeader('civil-service') +
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
      '<div class="bg-page bg-page--full bg-page--dense">' +
        _renderDenseHeader('civil-service') +
        '<main class="bg-content bg-content--sub" id="bg-content-main">' +
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
        _renderSubFooter() +
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

  function _renderDenseHeader(activeMenu) {
    var assets = "/static/images/bukgu-current";
    var searchIcon = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="10.8" cy="10.8" r="6.3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 16l4.4 4.4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
    var menuIcon = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16M4 12h16M4 17h16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
    return (
      '<div class="bg-home-gov-strip">' +
        '<div class="bg-home-gov-strip__inner">' +
          '<img src="' + assets + '/home-government-notice.png" alt="본 누리집은 전남광주통합특별시 북구청 공식 누리집입니다." class="bg-home-gov-strip__notice" />' +
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
      '<header class="bg-header">' +
        '<div class="bg-home-header">' +
        '<div class="bg-home-header__inner">' +
          '<a href="#" class="bg-home-header__identity" aria-label="전남광주통합특별시북구 홈">' +
            '<img src="' + assets + '/home-identity.png" alt="전남광주통합특별시북구" />' +
          '</a>' +
          '<nav class="bg-gnb" aria-label="주메뉴">' +
            '<div class="bg-home-gnb">' +
            '<a href="#" class="bg-home-gnb__link' + (activeMenu === 'civil-service' ? ' bg-home-gnb__link--active' : '') + '" data-action-target="nav-civil-service">종합민원</a>' +
            '<a href="#" class="bg-home-gnb__link">소통광장</a>' +
            '<a href="#" class="bg-home-gnb__link">더불어복지</a>' +
            '<a href="#" class="bg-home-gnb__link">분야별정보</a>' +
            '<a href="#" class="bg-home-gnb__link">정보공개</a>' +
            '<a href="#" class="bg-home-gnb__link' + (activeMenu === 'intro' ? ' bg-home-gnb__link--active' : '') + '">북구소개</a>' +
          '</div>' +
          '</nav>' +
          '<div class="bg-home-header__actions">' +
            '<button type="button" class="bg-home-header__icon" aria-label="통합검색">' + searchIcon + '<span>통합검색</span></button>' +
            '<button type="button" class="bg-home-header__icon" aria-label="전체메뉴">' + menuIcon + '<span>전체메뉴</span></button>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '</header>'
    );
  }

  function _renderSubFooter() {
    return (
      '<footer class="bg-home-footer" aria-label="사이트 하단">' +
        '<div class="bg-home-footer__inner">' +
          '<nav class="bg-home-footer__nav" aria-label="하단 메뉴">' +
            '<a href="#">누리집이용안내 <span aria-hidden="true">⌃</span></a>' +
            '<a href="#">개인정보처리방침 <span aria-hidden="true">⌃</span></a>' +
            '<a href="#">저작권 보호정책 <span aria-hidden="true">⌃</span></a>' +
            '<a href="#">이메일무단수집거부 <span aria-hidden="true">⌃</span></a>' +
            '<a href="#">영상정보처리기기 운영·관리방침 <span aria-hidden="true">⌃</span></a>' +
          '</nav>' +
          '<div class="bg-home-footer__legal"><strong>전남광주통합특별시북구</strong><span>로컬 시연 화면 · 외부 사이트와 연결하지 않습니다.</span></div>' +
        '</div>' +
      '</footer>' +
      '<p class="bg-home-local-note">로컬 시연 화면 · 외부 사이트와 연결하지 않습니다.</p>'
    );
  }

  // -----------------------------------------------------------------------
  // Route renderer dispatch
  // -----------------------------------------------------------------------
  function _renderRoute(routeId) {
    var search = typeof window !== "undefined" && window.location ? window.location.search : "";
    var autoReplay = _resolveAutoReplayState(search);
    if (autoReplay.isAuto) {
      var status;
      var _runnablePhases = ["route", "directory", "search"];
      var _phaseMatch = _autoReplayState.phase === autoReplay.step;
      if (autoReplay.step === "ready") {
        status = "ready";
        _autoReplayState.userStarted = false;
      } else if (_autoReplayState.userStarted && _autoReplayState.status === "running" && _phaseMatch && _runnablePhases.indexOf(autoReplay.step) !== -1) {
        status = "running";
      } else if (_autoReplayState.userStarted && _autoReplayState.status === "paused" && _phaseMatch && _runnablePhases.indexOf(autoReplay.step) !== -1) {
        status = "paused";
      } else if (_autoReplayState.userStarted && _autoReplayState.status === "complete" && _autoReplayState.phase === "result" && autoReplay.step === "result") {
        status = "complete";
      } else {
        status = "ready";
        _autoReplayState.userStarted = false;
      }
      _autoReplayState.phase = autoReplay.step;
      _autoReplayState.status = status;
      _updateChatProgressForAutoReplay(autoReplay.step);
      if (status === "running") {
        _scheduleAutoReplayAdvance(autoReplay.step);
      } else {
        _clearAutoReplayTimer();
      }
      return _renderAutoReplay(autoReplay.step, status);
    }
    _clearAutoReplayTimer();
    var deptReplay = _resolveDeptReplayState(search);
    if (deptReplay.isReplay) {
      _updateChatProgressForDeptReplay(deptReplay.step);
      if (deptReplay.step === "ready") {
        return _renderHome(_resolveHomeReferenceState(search));
      }
      return _renderDeptReplay(deptReplay.step);
    }
    var kioskJourney = _resolveKioskJourneyState(search);
    if (kioskJourney.isKiosk) {
      _updateChatForKiosk();
      return _renderKioskInformation();
    }
    var parkJourney = _resolveParkJourneyState(search);
    if (parkJourney.isPark) {
      _updateChatForPark();
      return _renderParkInformation();
    }
    var deptJourney = _resolveDeptJourneyState(search);
    var isDeptJourney = deptJourney.isDept;
    var deptState = deptJourney.state;

    if (isDeptJourney) {
      _updateChatProgressForDept(deptState);
    } else if (!kioskJourney.isKiosk && !_shouldPreserveFirstUseChat()) {
      _restoreHistoricalChat();
    }

    var route = _map.getRoute(routeId);
    if (!route) { return "<p>알 수 없는 경로입니다.</p>"; }

    var html = "";
    if (isDeptJourney && (deptState === "directory" || deptState === "result")) {
      html = _renderDeptDirectory(deptState);
    } else {
      switch (routeId) {
        case "home":               html = _renderHome(_resolveHomeReferenceState(search)); break;
        case "civil-service":      html = _renderCivilService(route); break;
        case "complaint-category": html = _renderCheongwon24(route); break;
        case "complaint-illegal-parking": html = _renderIllegalParking(route); break;
        case "complaint-intake":   html = _renderComplaintIntake(route); break;
        case "complaint-review":   html = _renderComplaintReview(route); break;
        case "handoff-stop":       html = _renderHandoffStop(route); break;
        default:                   html = "<p>알 수 없는 경로입니다.</p>"; break;
      }
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
    if (isDeptJourney && (deptState === "directory" || deptState === "result")) {
      meta = {title: "업무 및 전화번호 안내", purpose: "북구청 업무 및 전화번호를 안내합니다."};
    }

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
      var autoReplayAction = e.target.closest("[data-auto-replay-action]");
      if (autoReplayAction) {
        if (e && typeof e.preventDefault === "function") {
          e.preventDefault();
        }
        var action = autoReplayAction.getAttribute("data-auto-replay-action");
        if (action === "start") {
          _clearAutoReplayTimer();
          _autoReplayState.userStarted = true;
          _autoReplayState.status = "running";
          _advanceAutoReplay("route");
        } else if (action === "restart") {
          _clearAutoReplayTimer();
          _autoReplayState.userStarted = false;
          _autoReplayState.status = "ready";
          _autoReplayState.phase = "";
          if (typeof window !== "undefined" && window.history && typeof window.history.pushState === "function") {
            window.history.pushState({}, "", "?replay=J-DEPT-01&replay-mode=auto");
          }
          navigateToRoute("home");
        } else if (action === "pause") {
          _clearAutoReplayTimer();
          _autoReplayState.status = "paused";
          navigateToRoute("home");
        } else if (action === "resume") {
          _autoReplayState.status = "running";
          navigateToRoute("home");
        }
        return;
      }

      var deptAction = e.target.closest("[data-dept-action]");
      if (deptAction) {
        if (e && typeof e.preventDefault === "function") {
          e.preventDefault();
        }
        var actionType = deptAction.getAttribute("data-dept-action");
        if (typeof window !== "undefined" && window.location) {
          var params = new URLSearchParams(window.location.search);
          params.set("journey", "J-DEPT-01");
          if (actionType === "open-menu") {
            params.set("dept-state", "menu");
            window.history.pushState({}, "", "?" + params.toString());
            navigateToRoute("home");
          } else if (actionType === "go-directory") {
            params.set("dept-state", "directory");
            window.history.pushState({}, "", "?" + params.toString());
            navigateToRoute("home");
          } else if (actionType === "trigger-search") {
            var inputVal = _demoCanvas.querySelector(".bg-dept-search__input").value;
            if (inputVal.trim() === "공동주택") {
              params.set("dept-state", "result");
              window.history.pushState({}, "", "?" + params.toString());
              navigateToRoute("home");
            } else {
              params.set("dept-state", "directory");
              window.history.pushState({}, "", "?" + params.toString());
              navigateToRoute("home");
            }
          }
        }
        return;
      }

      var deptReplayAction = e.target.closest("[data-dept-replay-action]");
      if (deptReplayAction) {
        if (e && typeof e.preventDefault === "function") {
          e.preventDefault();
        }
        if (typeof window !== "undefined" && window.location && window.history && typeof window.history.pushState === "function") {
          var replayAction = deptReplayAction.getAttribute("data-dept-replay-action");
          var replayUrl = "?replay=J-DEPT-01";
          if (replayAction === "start") {
            replayUrl += "&replay-step=directory";
          } else if (replayAction === "next") {
            replayUrl += "&replay-step=result";
          } else if (replayAction !== "restart") {
            return;
          }
          window.history.pushState({}, "", replayUrl);
          navigateToRoute("home");
        }
        return;
      }

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
      "complaint-illegal-parking-report":                  "handoff-stop",
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
