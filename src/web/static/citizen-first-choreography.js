/*
 * citizen-first-choreography.js
 * Deterministic local journey choreography for the first-use split shell.
 *
 * Drives the demo-canvas through route transitions, target highlights,
 * search-focused steps, simulated typing, and search submission using
 * only the public CitizenActionDemoCanvas API and DOM access to the
 * public #demo-canvas element.
 *
 * Guarantees:
 * - no fetch/XHR/WebSocket/EventSource/sendBeacon;
 * - no browser persistence or cookie access;
 * - no provider, runner, live-site, or external-origin behavior;
 * - no hidden copilot-rail, executor trace/status, or URL API dependency;
 * - no screenshot layer, fake cursor, or external asset.
 */

(function () {
  "use strict";

  var STATE_IDLE = "idle";
  var STATE_RUNNING = "running";
  var STATE_DONE = "done";
  var STATE_CANCELLED = "cancelled";

  var HIGHLIGHT_CLASS = "executor-highlight";
  var TYPING_CLASS = "executor-typing";
  var SEARCH_BUSY_CLASS = "executor-search-busy";

  var _body = document.body;
  var _chatThread = document.getElementById("chat-thread");
  var _state = STATE_IDLE;
  var _timer = null;
  var _auxTimers = [];
  var _currentStep = -1;
  var _currentJourneyId = null;
  var _steps = [];
  var _highlightedEls = [];

  // ═══════════════════════════════════════════════════════════════════
  // Journey map — typed deterministic step lists keyed by question
  // or journey ID. Each step:
  //   message        — chat message to display (required)
  //   routeId        — call navigateToRoute(routeId) (optional)
  //   targetId       — call getTargetElement(targetId) + highlight (optional)
  //   journeyState   — push J-DEPT-01 state via URL params (optional)
  //   journeyStateAfterClick — apply a journey state after the cursor click lands
  //   focusSearch    — true: focus + highlight the directory search input
  //   typeQuery      — string: set value of the directory search input
  //   submitSearch   — true: click the directory search button
  //   cursorTarget   — CSS selector: move cursor arrow to this element
  //   clickTarget    — CSS selector: show cursor + click ripple at target element
  //   thinkingText   — (new) temporary AI "thinking" indicator shown before message (optional)
  //   searchingText  — (new) second-phase "searching" indicator after thinking (optional)
  //   thinkingMs     — duration in ms for thinking/searching indicator (default 800)
  //   delayMs        — pause before next step; omitted/0 = terminal
  // ═══════════════════════════════════════════════════════════════════
  var JOURNEY_MAP = Object.freeze({
    "불법 주정차 신고는 어디서 하나요?": Object.freeze({
      id: "complaint-illegal-parking",
      description: "불법 주정차 신고 경로 안내 (지도단속/안전신문고)",
      steps: Object.freeze([
        Object.freeze({ message: "불법 주정차 신고 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 1000 }),
        Object.freeze({ message: "지도단속 안내 화면으로 이동합니다.", routeId: "complaint-illegal-parking", delayMs: 2500, cursorTarget: ".bg-illegal-parking-card", thinkingText: "북구청 사이트에 접속 중입니다...", thinkingMs: 700 }),
        Object.freeze({ message: "안전신문고 등 공식 신고 채널을 안내합니다.", targetId: "complaint-illegal-parking-report", delayMs: 2800, clickTarget: ".bg-illegal-parking-card", thinkingText: "신고 채널 정보를 확인 중입니다...", searchingText: "안전신문고 사이트를 검색 중입니다...", thinkingMs: 800 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신고는 안전신문고(safetyreport.go.kr)에서 가능합니다." }),
      ]),
    }),
    // #927 MVP action aliases — same deterministic local clone as above.
    "illegal_parking": Object.freeze({
      id: "complaint-illegal-parking",
      description: "불법 주정차 신고 경로 안내 (지도단속/안전신문고, MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "불법 주정차 신고 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 1000 }),
        Object.freeze({ message: "지도단속 안내 화면으로 이동합니다.", routeId: "complaint-illegal-parking", delayMs: 2500, cursorTarget: ".bg-illegal-parking-card", thinkingText: "북구청 사이트에 접속 중입니다...", thinkingMs: 700 }),
        Object.freeze({ message: "안전신문고 등 공식 신고 채널을 안내합니다.", targetId: "complaint-illegal-parking-report", delayMs: 2800, clickTarget: ".bg-illegal-parking-card", thinkingText: "신고 채널 정보를 확인 중입니다...", searchingText: "안전신문고 사이트를 검색 중입니다...", thinkingMs: 800 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신고는 안전신문고(safetyreport.go.kr)에서 가능합니다." }),
      ]),
    }),
    // Owner-approved flagship flow: show the full menu, search, typing, and
    // grounded-result sequence instead of jumping directly to the answer.
    "공동주택 관련 문의는 어느 부서에 해야 하나요?": Object.freeze({
      id: "apartment-dept",
      description: "도시관리국 공동주택과 업무 및 연락처 안내",
      steps: Object.freeze([
        Object.freeze({ message: "공동주택 부서 정보를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 1000 }),
        Object.freeze({ message: "먼저 북구소개 메뉴를 열겠습니다.", journeyState: "J-DEPT-01:home", clickTarget: '[data-dept-action="open-menu"]', journeyStateAfterClick: "J-DEPT-01:menu", delayMs: 2400, thinkingText: "북구청 메뉴를 살펴보는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "구청안내에서 업무 및 전화번호 안내를 선택합니다.", clickTarget: '[data-dept-action="go-directory"]', journeyStateAfterClick: "J-DEPT-01:directory", delayMs: 2500, thinkingText: "담당 부서 경로를 찾는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "검색창에 공동주택을 입력하겠습니다.", focusSearch: true, typeQuery: "공동주택", cursorTarget: ".bg-dept-search__input", delayMs: 2500, thinkingText: "부서 검색을 준비하는 중입니다...", thinkingMs: 550 }),
        Object.freeze({ message: "입력한 검색어로 담당 부서를 조회합니다.", submitSearch: true, clickTarget: ".bg-dept-search__btn", delayMs: 2500, searchingText: "공동주택 관련 부서를 검색 중입니다...", thinkingText: "검색 조건을 확인하는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "검색 결과에서 공동주택과와 대표 연락처를 확인했습니다.", cursorTarget: ".bg-dept-table tbody tr:first-child", delayMs: 2400, thinkingText: "공식 결과를 확인하는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "공동주택 관련 문의는 공동주택과에서 담당하며, 대표 연락처는 062-410-6033입니다." }),
      ]),
    }),
    "housing_department": Object.freeze({
      id: "apartment-dept",
      description: "도시관리국 공동주택과 업무 및 연락처 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "공동주택 부서 정보를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 1000 }),
        Object.freeze({ message: "먼저 북구소개 메뉴를 열겠습니다.", journeyState: "J-DEPT-01:home", clickTarget: '[data-dept-action="open-menu"]', journeyStateAfterClick: "J-DEPT-01:menu", delayMs: 2400, thinkingText: "북구청 메뉴를 살펴보는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "구청안내에서 업무 및 전화번호 안내를 선택합니다.", clickTarget: '[data-dept-action="go-directory"]', journeyStateAfterClick: "J-DEPT-01:directory", delayMs: 2500, thinkingText: "담당 부서 경로를 찾는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "검색창에 공동주택을 입력하겠습니다.", focusSearch: true, typeQuery: "공동주택", cursorTarget: ".bg-dept-search__input", delayMs: 2500, thinkingText: "부서 검색을 준비하는 중입니다...", thinkingMs: 550 }),
        Object.freeze({ message: "입력한 검색어로 담당 부서를 조회합니다.", submitSearch: true, clickTarget: ".bg-dept-search__btn", delayMs: 2500, searchingText: "공동주택 관련 부서를 검색 중입니다...", thinkingText: "검색 조건을 확인하는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "검색 결과에서 공동주택과와 대표 연락처를 확인했습니다.", cursorTarget: ".bg-dept-table tbody tr:first-child", delayMs: 2400, thinkingText: "공식 결과를 확인하는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "공동주택 관련 문의는 공동주택과에서 담당하며, 대표 연락처는 062-410-6033입니다." }),
      ]),
    }),
    "bulky_waste": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200, thinkingText: "대형폐기물 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000, thinkingText: "배출 방법 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다." }),
      ]),
    }),
    "침대 매트리스 버리고 싶어요": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200, thinkingText: "대형폐기물 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000, thinkingText: "배출 방법 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다." }),
      ]),
    }),
    "대형폐기물은 어떻게 버리나요?": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200, thinkingText: "대형폐기물 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000, thinkingText: "배출 방법 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다." }),
      ]),
    }),
    "가구 버리려면 어디서 신청해요?": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200, thinkingText: "대형폐기물 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000, thinkingText: "배출 방법 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다." }),
      ]),
    }),
    "매트리스 폐기 신청은 어디서 하나요?": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200, thinkingText: "대형폐기물 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000, thinkingText: "배출 방법 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다." }),
      ]),
    }),
"passport_guidance": Object.freeze({
      id: "passport-guidance",
      description: "여권민원 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "여권 발급 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "여권민원 안내 화면으로 이동합니다.", routeId: "passport-guidance", delayMs: 1200, thinkingText: "여권민원 안내 화면을 찾는 중입니다...", searchingText: "여권 발급 관련 정보를 검색 중입니다...", thinkingMs: 800 }),
        Object.freeze({ message: "여권민원 안내를 확인합니다. 여권 수수료표, 구비서류, 신청안내를 보실 수 있습니다. 실제 여권 신청은 북구청 민원실 방문 후 직접 진행해야 합니다.", targetId: "passport-guidance-card", delayMs: 2000, thinkingText: "여권 발급 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 여권 신청은 북구청 민원실 또는 정부24에서 가능합니다." }),
      ]),
    }),
    "여권 발급은 어디서 하나요?": Object.freeze({
      id: "passport-guidance",
      description: "여권민원 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "여권 발급 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "여권민원 안내 화면으로 이동합니다.", routeId: "passport-guidance", delayMs: 1200, thinkingText: "여권민원 안내 화면을 찾는 중입니다...", searchingText: "여권 발급 관련 정보를 검색 중입니다...", thinkingMs: 800 }),
        Object.freeze({ message: "여권민원 안내를 확인합니다. 여권 수수료표, 구비서류, 신청안내를 보실 수 있습니다. 실제 여권 신청은 북구청 민원실 방문 후 직접 진행해야 합니다.", targetId: "passport-guidance-card", delayMs: 2000, thinkingText: "여권 발급 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 여권 신청은 북구청 민원실 또는 정부24에서 가능합니다." }),
      ]),
    }),
    "여권 재발급은 어떻게 하나요?": Object.freeze({
      id: "passport-guidance",
      description: "여권민원 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "여권 발급 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "여권민원 안내 화면으로 이동합니다.", routeId: "passport-guidance", delayMs: 1200, thinkingText: "여권민원 안내 화면을 찾는 중입니다...", searchingText: "여권 발급 관련 정보를 검색 중입니다...", thinkingMs: 800 }),
        Object.freeze({ message: "여권민원 안내를 확인합니다. 여권 수수료표, 구비서류, 신청안내를 보실 수 있습니다. 실제 여권 신청은 북구청 민원실 방문 후 직접 진행해야 합니다.", targetId: "passport-guidance-card", delayMs: 2000, thinkingText: "여권 발급 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 여권 신청은 북구청 민원실 또는 정부24에서 가능합니다." }),
      ]),
    }),
    "unmanned_kiosk": Object.freeze({
      id: "unmanned-kiosk-guidance",
      description: "무인민원발급기 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "무인민원발급기 이용 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내 화면으로 이동합니다.", routeId: "unmanned-kiosk-guidance", delayMs: 1200, thinkingText: "무인민원발급기 정보 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.", targetId: "unmanned-kiosk-card", delayMs: 2000, thinkingText: "무인민원발급기 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다." }),
      ]),
    }),
    "무인민원발급기 어디 있어요?": Object.freeze({
      id: "unmanned-kiosk-guidance",
      description: "무인민원발급기 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "무인민원발급기 이용 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내 화면으로 이동합니다.", routeId: "unmanned-kiosk-guidance", delayMs: 1200, thinkingText: "무인민원발급기 정보 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.", targetId: "unmanned-kiosk-card", delayMs: 2000, thinkingText: "무인민원발급기 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다." }),
      ]),
    }),
    "무인민원발급기로 뭘 발급받을 수 있어요?": Object.freeze({
      id: "unmanned-kiosk-guidance",
      description: "무인민원발급기 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "무인민원발급기 이용 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내 화면으로 이동합니다.", routeId: "unmanned-kiosk-guidance", delayMs: 1200, thinkingText: "무인민원발급기 정보 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.", targetId: "unmanned-kiosk-card", delayMs: 2000, thinkingText: "무인민원발급기 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다." }),
      ]),
    }),
    "무인민원발급기 이용방법 알려줘": Object.freeze({
      id: "unmanned-kiosk-guidance",
      description: "무인민원발급기 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "무인민원발급기 이용 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내 화면으로 이동합니다.", routeId: "unmanned-kiosk-guidance", delayMs: 1200, thinkingText: "무인민원발급기 정보 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.", targetId: "unmanned-kiosk-card", delayMs: 2000, thinkingText: "무인민원발급기 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다." }),
      ]),
    }),
    "민원서류 발급받으려면 어디로 가야 해요?": Object.freeze({
      id: "unmanned-kiosk-guidance",
      description: "무인민원발급기 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "무인민원발급기 이용 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내 화면으로 이동합니다.", routeId: "unmanned-kiosk-guidance", delayMs: 1200, thinkingText: "무인민원발급기 정보 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.", targetId: "unmanned-kiosk-card", delayMs: 2000, thinkingText: "무인민원발급기 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다." }),
      ]),
    }),
    "가로등이 고장났어요. 신고할게요": Object.freeze({
      id: "complaint-board-write",
      description: "가로등 고장 신고 - 민원게시판 글쓰기 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "가로등 고장 신고를 도와드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 1000 }),
        Object.freeze({ message: "민원게시판으로 이동합니다.", routeId: "complaint-board", delayMs: 2000, thinkingText: "게시판으로 이동 중입니다...", thinkingMs: 700 }),
        Object.freeze({ message: "새로운 신고 글쓰기 양식을 엽니다.", clickTarget: "#btn-board-write", delayMs: 2000, routeId: "complaint-write", thinkingText: "양식을 준비 중입니다...", thinkingMs: 700 }),
        Object.freeze({ message: "가로등 고장 신고 내용을 초안으로 작성했습니다.", focusSearch: true, typeQuery: "가로등 고장 신고", cursorTarget: "#board-write-title", delayMs: 2500, thinkingText: "내용을 작성하는 중입니다...", thinkingMs: 800 }),
        Object.freeze({ message: "작성된 내용을 확인하시고 제출해 주세요.", requiresConfirmation: true, delayMs: 1000 }),
        Object.freeze({ message: "민원 신고가 성공적으로 접수되었습니다. 처리 결과는 민원게시판에서 확인 가능합니다." })
      ]),
    }),
    "쓰레기 무단투기 신고할래 (AI 도움)": Object.freeze({
      id: "complaint-ai-assist",
      description: "쓰레기 무단투기 신고 - AI 폼 자동 완성 보조",
      steps: Object.freeze([
        Object.freeze({ message: "쓰레기 무단투기 신고 작성을 도와드립니다.", thinkingText: "안내를 준비 중입니다...", thinkingMs: 500, delayMs: 1000 }),
        Object.freeze({ message: "민원게시판의 글쓰기 양식으로 이동합니다.", routeId: "complaint-write", delayMs: 2000, thinkingText: "게시판으로 이동 중입니다...", thinkingMs: 700 }),
        Object.freeze({ message: "직접 작성하시겠습니까, 아니면 AI가 초안 작성을 도와드릴까요?", requiresChoice: true, delayMs: 1000 }),
        Object.freeze({ message: "[사용자 선택: AI 도움 받기] 어떤 불편사항이 있으신지 편하게 말씀해 주세요.", delayMs: 1500, thinkingText: "답변을 기다리는 중입니다...", thinkingMs: 800 }),
        Object.freeze({ message: "집 앞 공원에 쓰레기가 너무 많고 냄새가 나요. 빨리 치워주세요.", isUserSimulated: true, delayMs: 2500 }),
        Object.freeze({ message: "말씀하신 내용을 바탕으로 민원 접수 양식에 맞게 초안을 작성합니다...", thinkingText: "내용을 분석하고 윤문하는 중입니다...", thinkingMs: 1500, delayMs: 1500 }),
        Object.freeze({ message: "AI가 서식을 모두 채웠습니다.", focusSearch: true, typeQuery: "[환경정비 요청] ○○공원 내 방치 쓰레기 수거 및 악취 해결 요청", cursorTarget: "#board-write-title", delayMs: 1500, typeContent: "구정 발전에 노고가 많으십니다. 다름이 아니오라 집 앞 공원에 무단 투기된 쓰레기가 다량 방치되어 있어 심한 악취와 미관 훼손이 발생하고 있습니다. 조속한 환경 정비 및 수거를 요청드립니다." }),
        Object.freeze({ message: "작성된 내용을 확인하시고 화면의 [제출하기] 버튼을 눌러주세요.", requiresConfirmation: true, delayMs: 1000 }),
        Object.freeze({ message: "민원 신고가 성공적으로 접수되었습니다." })
      ]),
    }),
  });

  // ═══════════════════════════════════════════════════════════════════
  // Internal helpers
  // ═══════════════════════════════════════════════════════════════════

  function _appendChatMessage(role, text, isTemp) {
    if (!_chatThread) return;
    var messageEl = document.createElement("div");
    messageEl.className = "chat-msg chat-msg--" + role;
    if (isTemp) {
      messageEl.className += " chat-msg--temp";
    }
    if (role === "ai") {
      var avatar = document.createElement("div");
      avatar.className = "chat-avatar";
      avatar.setAttribute("aria-label", "AI");
      avatar.textContent = "A";
      messageEl.appendChild(avatar);
    }
    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--" + role;
    bubble.textContent = text;
    messageEl.appendChild(bubble);
    _chatThread.appendChild(messageEl);
    _chatThread.scrollTop = _chatThread.scrollHeight;
    return messageEl;
  }

  /** Remove all temporary chat messages (for cleaning up thinking/searching indicators) */
  function _removeTempMessages() {
    if (!_chatThread) return;
    var temps = _chatThread.querySelectorAll(".chat-msg--temp");
    for (var i = temps.length - 1; i >= 0; i--) {
      if (temps[i].parentNode) temps[i].parentNode.removeChild(temps[i]);
    }
  }

  /** Show a temporary thinking/searching indicator, then remove it after delayMs */
  function _showTempIndicator(text, delayMs) {
    var el = _appendChatMessage("ai", text, true);
    if (el && delayMs > 0) {
      window.setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, delayMs);
    }
    return el;
  }

  function _clearHighlights() {
    for (var i = 0; i < _highlightedEls.length; i++) {
      if (_highlightedEls[i]) {
        _highlightedEls[i].classList.remove(HIGHLIGHT_CLASS);
        _highlightedEls[i].classList.remove(TYPING_CLASS);
        _highlightedEls[i].classList.remove(SEARCH_BUSY_CLASS);
        if (_highlightedEls[i].removeAttribute) {
          _highlightedEls[i].removeAttribute("data-agent-typing");
        }
      }
    }
    _highlightedEls = [];
  }

  function _clearTimer() {
    if (_timer !== null) {
      window.clearTimeout(_timer);
      _timer = null;
    }
  }

  function _scheduleAux(callback, delayMs) {
    var timerId = window.setTimeout(function () {
      var timerIndex = _auxTimers.indexOf(timerId);
      if (timerIndex !== -1) _auxTimers.splice(timerIndex, 1);
      if (_state === STATE_RUNNING) callback();
    }, delayMs);
    _auxTimers.push(timerId);
    return timerId;
  }

  function _clearAuxTimers() {
    for (var i = 0; i < _auxTimers.length; i++) {
      window.clearTimeout(_auxTimers[i]);
    }
    _auxTimers = [];
  }

  function _prefersReducedMotion() {
    return Boolean(
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function _dispatchInputEvent(input) {
    if (!input || typeof input.dispatchEvent !== "function" || typeof Event !== "function") return;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function _typeIntoSearch(input, value, startDelayMs) {
    if (!input) return 0;
    var text = String(value || "");
    var charDelayMs = _prefersReducedMotion() ? 0 : 115;
    var startDelay = _prefersReducedMotion() ? 0 : startDelayMs;

    input.value = "";
    input.classList.add(TYPING_CLASS);
    input.setAttribute("data-agent-typing", "true");
    _highlightedEls.push(input);

    if (!charDelayMs) {
      input.value = text;
      input.removeAttribute("data-agent-typing");
      _dispatchInputEvent(input);
      return 0;
    }

    for (var i = 0; i < text.length; i++) {
      (function (characterIndex) {
        _scheduleAux(function () {
          input.value = text.slice(0, characterIndex + 1);
          _dispatchInputEvent(input);
          if (characterIndex === text.length - 1) {
            input.removeAttribute("data-agent-typing");
          }
        }, startDelay + (characterIndex * charDelayMs));
      })(i);
    }

    return startDelay + (text.length * charDelayMs) + 160;
  }

  function _setState(nextState) {
    _state = nextState;
    _body.setAttribute("data-choreography-state", nextState);
  }

  // #927: drive an existing local clone journey state through the public
  // canvas API. Currently supports the approved J-DEPT-01 directory state,
  // which renders the 공동주택과 / 062-410-6033 / 공동주택과 업무전반 facts.
  function _applyJourneyState(journeyState) {
    if (!journeyState || typeof journeyState !== "string") return;
    var parts = journeyState.split(":");
    var journey = parts[0];
    var state = parts[1] || "";
    if (journey === "J-DEPT-01" && (state === "directory" || state === "result" || state === "menu")) {
      if (typeof window !== "undefined" && window.location && window.history
          && typeof window.history.pushState === "function") {
        var params = new URLSearchParams(window.location.search);
        params.set("journey", "J-DEPT-01");
        params.set("dept-state", state);
        window.history.pushState({}, "", "?" + params.toString());
      }
      var canvas = window.CitizenActionDemoCanvas;
      if (canvas && canvas.navigateToRoute) {
        canvas.navigateToRoute("home");
      }
    }
  }

  function _getCanvasEl() {
    return document.getElementById("demo-canvas");
  }

  function _executeStep(index) {
    if (_state !== STATE_RUNNING) return;
    if (index >= _steps.length) {
      _setState(STATE_DONE);
      return;
    }

    _currentStep = index;
    var step = _steps[index];

    // Execute DOM action FIRST so left-pane visuals render before
    // the chat message appears — 박사님 choreography ordering requirement (#965).
    if (step.routeId || step.targetId || step.journeyState || step.focusSearch || step.typeQuery || step.submitSearch) {
      _clearHighlights();
    }

    if (step.routeId) {
      var canvas = window.CitizenActionDemoCanvas;
      if (canvas && canvas.navigateToRoute) {
        canvas.navigateToRoute(step.routeId);
      }
    } else if (step.targetId) {
      var canvas = window.CitizenActionDemoCanvas;
      if (canvas && canvas.getTargetElement) {
        var el = canvas.getTargetElement(step.targetId);
        if (el) {
          el.classList.add(HIGHLIGHT_CLASS);
          try { el.scrollIntoView({ behavior: "smooth", block: "center" }); } catch (_) { /* noop */ }
          _highlightedEls.push(el);
        }
      }
    } else if (step.journeyState) {
      _applyJourneyState(step.journeyState);
    }

    // #965: search-field interaction steps
    if (step.focusSearch) {
      var demoEl = _getCanvasEl();
      if (demoEl) {
        var input = demoEl.querySelector(".bg-dept-search__input");
        if (input) {
          input.focus();
          input.classList.add(HIGHLIGHT_CLASS);
          _highlightedEls.push(input);
        }
      }
    }

    // ── AI-style thinking/searching indicator ──────────────────────
    // If the step has a thinkingText, show a temporary indicator before
    // the permanent message, simulating AI "thinking" / "searching".
    function _showPermanentAndSchedule() {
      // Remove any stale temp indicators
      _removeTempMessages();
      // Show chat message AFTER DOM actions so the left-pane state is visible
      // before the explanation text.
      _appendChatMessage("ai", step.message);

      // Cursor, click, typing, and state changes play after the narration so the
      // resident can watch the agent act instead of seeing a finished state pop in.
      var visualActionDelay = 0;
      var cursorDelay = _prefersReducedMotion() ? 0 : 120;
      var clickDelay = _prefersReducedMotion() ? 0 : 180;
      var actionCommitDelay = _prefersReducedMotion() ? 0 : 1080;

      if (step.cursorTarget) {
        var cCanvas = window.CitizenActionDemoCanvas;
        if (cCanvas) {
          if (cCanvas.hideCursor) cCanvas.hideCursor();
          if (cCanvas.showCursorAt) {
            _scheduleAux(function () {
              cCanvas.showCursorAt(step.cursorTarget);
            }, cursorDelay);
            visualActionDelay = Math.max(visualActionDelay, cursorDelay + 780);
          }
        }
      }
      if (step.clickTarget) {
        var kCanvas = window.CitizenActionDemoCanvas;
        if (kCanvas && kCanvas.clickAnimation) {
          _scheduleAux(function () {
            kCanvas.clickAnimation(step.clickTarget);
          }, clickDelay);
          visualActionDelay = Math.max(visualActionDelay, actionCommitDelay);
        }
      }

      if (step.typeQuery) {
        var typeDemoEl = _getCanvasEl();
        var typeInput = typeDemoEl && typeDemoEl.querySelector(".bg-dept-search__input");
        var typingStartDelay = step.cursorTarget ? 850 : 160;
        visualActionDelay = Math.max(
          visualActionDelay,
          _typeIntoSearch(typeInput, step.typeQuery, typingStartDelay)
        );
      }

      if (step.journeyStateAfterClick) {
        _scheduleAux(function () {
          _applyJourneyState(step.journeyStateAfterClick);
        }, actionCommitDelay);
        visualActionDelay = Math.max(visualActionDelay, actionCommitDelay + 320);
      }

      if (step.submitSearch) {
        var submitDemoEl = _getCanvasEl();
        var submitButton = submitDemoEl && submitDemoEl.querySelector(".bg-dept-search__btn");
        if (submitButton) {
          submitButton.classList.add(SEARCH_BUSY_CLASS);
          _highlightedEls.push(submitButton);
          _scheduleAux(function () {
            submitButton.click();
          }, actionCommitDelay);
          visualActionDelay = Math.max(visualActionDelay, actionCommitDelay + 420);
        }
      }

      // Schedule next step or terminate
      if (step.requiresChoice) {
        var effectiveDelayChoice = Math.max(step.delayMs || 0, visualActionDelay + 320);
        _timer = window.setTimeout(function () {
          _timer = null;
          _setState("waiting_choice");
          _renderChoicePrompt(index);
        }, effectiveDelayChoice);
      } else if (step.requiresConfirmation) {
        var effectiveDelayConfirm = Math.max(step.delayMs || 0, visualActionDelay + 320);
        _timer = window.setTimeout(function () {
          _timer = null;
          _setState("waiting_confirmation");
          _renderConfirmationPrompt(index);
        }, effectiveDelayConfirm);
      } else if (typeof step.delayMs === "number" && step.delayMs > 0) {
        var effectiveDelay = Math.max(step.delayMs, visualActionDelay + 320);
        _timer = window.setTimeout(function () {
          _timer = null;
          _executeStep(index + 1);
        }, effectiveDelay);
      } else {
        // No delay → terminal step (done message)
        _setState(STATE_DONE);
      }
    }

    if (step.thinkingText) {
      // Show thinking/searching indicator, then replace with permanent message
      var thinkMs = (typeof step.thinkingMs === "number") ? step.thinkingMs : 800;
      var tempEl;
      if (step.searchingText) {
        // Two-phase: show thinking, then searching, then permanent
        tempEl = _showTempIndicator(step.thinkingText, thinkMs);
        _scheduleAux(function () {
          if (tempEl && tempEl.parentNode) tempEl.parentNode.removeChild(tempEl);
          var searchEl = _showTempIndicator(step.searchingText, thinkMs);
          _scheduleAux(function () {
            if (searchEl && searchEl.parentNode) searchEl.parentNode.removeChild(searchEl);
            _showPermanentAndSchedule();
          }, thinkMs);
        }, thinkMs);
      } else {
        // Single-phase: show thinking, then permanent
        tempEl = _showTempIndicator(step.thinkingText, thinkMs);
        _scheduleAux(function () {
          if (tempEl && tempEl.parentNode) tempEl.parentNode.removeChild(tempEl);
          _showPermanentAndSchedule();
        }, thinkMs);
      }
    } else {
      _showPermanentAndSchedule();
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  // Public API
  // ═══════════════════════════════════════════════════════════════════

  /**
   * Start a choreography for the given journey key.
   * @param {string} journeyKey — question text or journey ID
   * @returns {boolean} true if a matching journey was found and started
   */
  function start(journeyKey) {
    if (_state === STATE_RUNNING) cancel();

    var entry = JOURNEY_MAP[journeyKey];
    if (!entry) return false;

    _currentJourneyId = entry.id;
    _steps = entry.steps;
    _currentStep = -1;
    _setState(STATE_RUNNING);
    _executeStep(0);
    return true;
  }

  /** Cancel a running choreography. Safe to call in any state. */
  function cancel() {
    if (_state === STATE_IDLE) return;
    _clearTimer();
    _clearAuxTimers();
    _clearHighlights();
    _steps = [];
    _currentStep = -1;
    _currentJourneyId = null;
    _setState(STATE_CANCELLED);
  }

  /** @returns {string} current state */
  function getState() {
    return _state;
  }

  /** @returns {string|null} current journey ID */
  function getCurrentJourneyId() {
    return _currentJourneyId;
  }

  /** @returns {boolean} true if a journey map exists for the key */
  function hasJourney(journeyKey) {
    return Boolean(JOURNEY_MAP[journeyKey]);
  }

  function _renderChoicePrompt(index) {
    if (!_chatThread) return;
    var messageEl = document.createElement("div");
    messageEl.className = "chat-msg chat-msg--ai";
    messageEl.innerHTML = '<div class="chat-avatar" aria-label="AI">A</div>' +
      '<div class="chat-bubble chat-bubble--ai" style="display:flex; flex-direction:column; gap:10px;">' +
        '<span>직접 작성하시겠습니까, 아니면 AI가 초안 작성을 도와드릴까요?</span>' +
        '<div style="display:flex; gap:10px;">' +
          '<button type="button" class="bg-dept-search__btn" style="background:#666; padding:5px 10px; font-size:14px;" onclick="window.CitizenFirstChoreography.cancel()">직접 작성</button>' +
          '<button type="button" class="bg-dept-search__btn" style="padding:5px 10px; font-size:14px;" onclick="window.CitizenFirstChoreography.handleChoice(' + index + ')">AI 도움 받기</button>' +
        '</div>' +
      '</div>';
    _chatThread.appendChild(messageEl);
    _chatThread.scrollTop = _chatThread.scrollHeight;
  }

  function handleChoice(index) {
    _setState(STATE_RUNNING);
    _executeStep(index + 1);
  }

  function _renderConfirmationPrompt(index) {
    if (!_chatThread) return;
    var messageEl = document.createElement("div");
    messageEl.className = "chat-msg chat-msg--ai";
    messageEl.innerHTML = '<div class="chat-avatar" aria-label="AI">A</div>' +
      '<div class="chat-bubble chat-bubble--ai" style="display:flex; flex-direction:column; gap:10px;">' +
        '<span>이대로 제출할까요? (실제 제출 전 확인)</span>' +
        '<div style="display:flex; gap:10px;">' +
          '<button type="button" class="bg-dept-search__btn" style="padding:5px 10px; font-size:14px;" onclick="window.CitizenFirstChoreography.confirmSubmission(' + index + ')">제출하기</button>' +
          '<button type="button" class="bg-dept-search__btn" style="background:#666; padding:5px 10px; font-size:14px;" onclick="window.CitizenFirstChoreography.cancel()">취소하기</button>' +
        '</div>' +
      '</div>';
    _chatThread.appendChild(messageEl);
    _chatThread.scrollTop = _chatThread.scrollHeight;
  }

  function confirmSubmission(index) {
    _setState(STATE_RUNNING);
    
    // Simulate submission through the adapter
    if (window.CitizenContentAdapter) {
      var demoEl = document.getElementById("demo-canvas");
      var title = demoEl.querySelector("#board-write-title");
      var contentEl = demoEl.querySelector("#board-write-content");
      var data = {
        title: title ? title.value : "가로등 고장 신고",
        content: contentEl ? contentEl.value : "가로등 고장을 신고합니다.",
        author: "주민"
      };
      
      var cCanvas = window.CitizenActionDemoCanvas;
      if (cCanvas && cCanvas.clickAnimation) {
         cCanvas.clickAnimation("#btn-board-submit");
      }
      
      window.CitizenContentAdapter.submitBoardPost(data).then(function() {
        if (cCanvas && cCanvas.navigateToRoute) {
          cCanvas.navigateToRoute("complaint-board");
        }
        _executeStep(index + 1);
      });
    } else {
       _executeStep(index + 1);
    }
  }

  window.CitizenFirstChoreography = Object.freeze({
    start: start,
    cancel: cancel,
    getState: getState,
    getCurrentJourneyId: getCurrentJourneyId,
    hasJourney: hasJourney,
    confirmSubmission: confirmSubmission,
    handleChoice: handleChoice,
    states: Object.freeze({
      idle: STATE_IDLE,
      running: STATE_RUNNING,
      done: STATE_DONE,
      cancelled: STATE_CANCELLED,
    }),
  });
})();
