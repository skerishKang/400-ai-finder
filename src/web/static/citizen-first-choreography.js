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
  //   focusSearch    — true: focus + highlight the directory search input
  //   typeQuery      — string: set value of the directory search input
  //   submitSearch   — true: click the directory search button
  //   delayMs        — pause before next step; omitted/0 = terminal
  // ═══════════════════════════════════════════════════════════════════
  var JOURNEY_MAP = Object.freeze({
    "불법 주정차 신고는 어디서 하나요?": Object.freeze({
      id: "complaint-illegal-parking",
      description: "불법 주정차 신고 경로 안내 (지도단속/안전신문고)",
      steps: Object.freeze([
        Object.freeze({ message: "불법 주정차 신고 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "지도단속 안내 화면으로 이동합니다.", routeId: "complaint-illegal-parking", delayMs: 1200 }),
        Object.freeze({ message: "안전신문고 등 공식 신고 채널을 안내합니다.", targetId: "complaint-illegal-parking-report", delayMs: 2000 }),
        Object.freeze({ message: "실제 외부 신고, 본인인증, 사진·위치·차량번호 입력, 제출은 사용자가 직접 진행해야 하므로 데모는 안내 단계에서 멈춥니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    // #927 MVP action aliases — same deterministic local clone as above.
    "illegal_parking": Object.freeze({
      id: "complaint-illegal-parking",
      description: "불법 주정차 신고 경로 안내 (지도단속/안전신문고, MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "불법 주정차 신고 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "지도단속 안내 화면으로 이동합니다.", routeId: "complaint-illegal-parking", delayMs: 1200 }),
        Object.freeze({ message: "안전신문고 등 공식 신고 채널을 안내합니다.", targetId: "complaint-illegal-parking-report", delayMs: 2000 }),
        Object.freeze({ message: "실제 외부 신고, 본인인증, 사진·위치·차량번호 입력, 제출은 사용자가 직접 진행해야 하므로 데모는 안내 단계에서 멈춥니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    // #988 — 아파트정보/아파트생활정보 안내 choreography
    "공동주택 관련 문의는 어느 부서에 해야 하나요?": Object.freeze({
      id: "apartment-info",
      description: "아파트정보 아파트현황 및 아파트생활정보 안내 (아파트정보 페이지)",
      steps: Object.freeze([
        Object.freeze({ message: "아파트 정보를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "아파트정보 아파트현황 화면으로 이동합니다.", routeId: "apartment-info", delayMs: 1200 }),
        Object.freeze({ message: "아파트명, 주소, 세대수, 관리사무소 정보를 확인합니다.", targetId: "apartment-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "하자나 관리비 등 생활정보는 아파트생활정보에서 추가로 확인할 수 있습니다.", targetId: "apartment-life-card", delayMs: 2000 }),
        Object.freeze({ message: "실제 아파트 정보 확인, 민원 제출, 하자 신청은 사용자가 공식 채널에서 직접 진행해야 하므로 데모는 안내 단계에서 멈춥니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "housing_department": Object.freeze({
      id: "apartment-info",
      description: "아파트정보 아파트현황 및 아파트생활정보 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "아파트 정보를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "아파트정보 아파트현황 화면으로 이동합니다.", routeId: "apartment-info", delayMs: 1200 }),
        Object.freeze({ message: "아파트명, 주소, 세대수, 관리사무소 정보를 확인합니다.", targetId: "apartment-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "하자나 관리비 등 생활정보는 아파트생활정보에서 추가로 확인할 수 있습니다.", targetId: "apartment-life-card", delayMs: 2000 }),
        Object.freeze({ message: "실제 아파트 정보 확인, 민원 제출, 하자 신청은 사용자가 공식 채널에서 직접 진행해야 하므로 데모는 안내 단계에서 멈춥니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "bulky_waste": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "실제 품목 선택, 주소·연락처 입력, 수수료 결제, 배출번호 발급은 공식 채널에서 사용자가 직접 진행해야 하므로 데모는 안내 단계에서 멈춥니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "침대 매트리스 버리고 싶어요": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "실제 품목 선택, 주소·연락처 입력, 수수료 결제, 배출번호 발급은 공식 채널에서 사용자가 직접 진행해야 하므로 데모는 안내 단계에서 멈춥니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "대형폐기물은 어떻게 버리나요?": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "실제 품목 선택, 주소·연락처 입력, 수수료 결제, 배출번호 발급은 공식 채널에서 사용자가 직접 진행해야 하므로 데모는 안내 단계에서 멈춥니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "가구 버리려면 어디서 신청해요?": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "실제 품목 선택, 주소·연락처 입력, 수수료 결제, 배출번호 발급은 공식 채널에서 사용자가 직접 진행해야 하므로 데모는 안내 단계에서 멈춥니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "매트리스 폐기 신청은 어디서 하나요?": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "실제 품목 선택, 주소·연락처 입력, 수수료 결제, 배출번호 발급은 공식 채널에서 사용자가 직접 진행해야 하므로 데모는 안내 단계에서 멈춥니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
"move_in_report": Object.freeze({
      id: "move-in-report-guidance",
      description: "정부24 전입신고 연결 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "정부24 전입신고 연결 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200 }),
        Object.freeze({ message: "전자민원창구의 정부24 연결 안내 화면으로 이동합니다.", routeId: "move-in-report-guidance", delayMs: 1200 }),
        Object.freeze({ message: "정부24 전입신고 연결 안내를 확인합니다. 실제 본인인증, 주소·세대주·가족관계 정보 입력, 제출은 사용자가 정부24/주민센터에서 직접 진행해야 합니다.", targetId: "move-in-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "안내가 완료되었습니다. 실제 전입신고, 본인인증, 세대주·주소·가족관계 등 개인정보 입력, 정부24 또는 주민센터 제출은 사용자가 직접 확인해야 합니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "이사 왔는데 전입신고는 어떻게 해요?": Object.freeze({
      id: "move-in-report-guidance",
      description: "정부24 전입신고 연결 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "정부24 전입신고 연결 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200 }),
        Object.freeze({ message: "전자민원창구의 정부24 연결 안내 화면으로 이동합니다.", routeId: "move-in-report-guidance", delayMs: 1200 }),
        Object.freeze({ message: "정부24 전입신고 연결 안내를 확인합니다. 실제 본인인증, 주소·세대주·가족관계 정보 입력, 제출은 사용자가 정부24/주민센터에서 직접 진행해야 합니다.", targetId: "move-in-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "안내가 완료되었습니다. 실제 전입신고, 본인인증, 세대주·주소·가족관계 등 개인정보 입력, 정부24 또는 주민센터 제출은 사용자가 직접 확인해야 합니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "전입신고 어디서 하나요?": Object.freeze({
      id: "move-in-report-guidance",
      description: "정부24 전입신고 연결 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "정부24 전입신고 연결 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200 }),
        Object.freeze({ message: "전자민원창구의 정부24 연결 안내 화면으로 이동합니다.", routeId: "move-in-report-guidance", delayMs: 1200 }),
        Object.freeze({ message: "정부24 전입신고 연결 안내를 확인합니다. 실제 본인인증, 주소·세대주·가족관계 정보 입력, 제출은 사용자가 정부24/주민센터에서 직접 진행해야 합니다.", targetId: "move-in-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "안내가 완료되었습니다. 실제 전입신고, 본인인증, 세대주·주소·가족관계 등 개인정보 입력, 정부24 또는 주민센터 제출은 사용자가 직접 확인해야 합니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "이사 왔는데 전입신고는 어떻게 해요?": Object.freeze({
      id: "move-in-report-guidance",
      description: "전입신고 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "전입신고 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200 }),
        Object.freeze({ message: "전입신고 안내 화면으로 이동합니다.", routeId: "move-in-report-guidance", delayMs: 1200 }),
        Object.freeze({ message: "전입신고 안내를 확인합니다. 실제 본인인증, 주소·세대주·가족관계 정보 입력, 정부24/주민센터 제출 전 사용자 확인이 필요합니다.", targetId: "move-in-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "안내가 완료되었습니다. 실제 전입신고, 본인인증, 세대주·주소·가족관계 등 개인정보 입력, 정부24 또는 주민센터 제출은 사용자가 직접 확인해야 합니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "public_health_center": Object.freeze({
      id: "public-health-center-guidance",
      description: "보건소 위치·진료 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "보건소 위치·진료 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "북구청 홈의 주요사이트에서 보건소로 이동합니다.", targetId: "nav-civil-service", delayMs: 1500 }),
        Object.freeze({ message: "보건소 위치·진료 안내 화면으로 이동합니다.", routeId: "public-health-center-guidance", delayMs: 1200 }),
        Object.freeze({ message: "보건소 위치·진료 안내를 확인합니다. 실제 이용 정보는 공식 채널에서 직접 확인해야 합니다.", targetId: "health-center-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "안내가 완료되었습니다. 실제 보건소 이용, 진료 예약, 본인인증, 건강정보 입력, 제출은 사용자가 공식 채널에서 직접 확인해야 합니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "보건소 어디에 있어요?": Object.freeze({
      id: "public-health-center-guidance",
      description: "보건소 위치·진료 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "보건소 위치·진료 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "북구청 홈의 주요사이트에서 보건소로 이동합니다.", targetId: "nav-civil-service", delayMs: 1500 }),
        Object.freeze({ message: "보건소 위치·진료 안내 화면으로 이동합니다.", routeId: "public-health-center-guidance", delayMs: 1200 }),
        Object.freeze({ message: "보건소 위치·진료 안내를 확인합니다. 실제 이용 정보는 공식 채널에서 직접 확인해야 합니다.", targetId: "health-center-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "안내가 완료되었습니다. 실제 보건소 이용, 진료 예약, 본인인증, 건강정보 입력, 제출은 사용자가 공식 채널에서 직접 확인해야 합니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "북구 보건소 진료는 어떻게 확인해요?": Object.freeze({
      id: "public-health-center-guidance",
      description: "보건소 위치·진료 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "보건소 위치·진료 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "북구청 홈의 주요사이트에서 보건소로 이동합니다.", targetId: "nav-civil-service", delayMs: 1500 }),
        Object.freeze({ message: "보건소 위치·진료 안내 화면으로 이동합니다.", routeId: "public-health-center-guidance", delayMs: 1200 }),
        Object.freeze({ message: "보건소 위치·진료 안내를 확인합니다. 실제 이용 정보는 공식 채널에서 직접 확인해야 합니다.", targetId: "health-center-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "안내가 완료되었습니다. 실제 보건소 이용, 진료 예약, 본인인증, 건강정보 입력, 제출은 사용자가 공식 채널에서 직접 확인해야 합니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "보건소 위치랑 진료 안내 알려줘": Object.freeze({
      id: "public-health-center-guidance",
      description: "보건소 위치·진료 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "보건소 위치·진료 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "북구청 홈의 주요사이트에서 보건소로 이동합니다.", targetId: "nav-civil-service", delayMs: 1500 }),
        Object.freeze({ message: "보건소 위치·진료 안내 화면으로 이동합니다.", routeId: "public-health-center-guidance", delayMs: 1200 }),
        Object.freeze({ message: "보건소 위치·진료 안내를 확인합니다. 실제 이용 정보는 공식 채널에서 직접 확인해야 합니다.", targetId: "health-center-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "안내가 완료되었습니다. 실제 보건소 이용, 진료 예약, 본인인증, 건강정보 입력, 제출은 사용자가 공식 채널에서 직접 확인해야 합니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "예방접종이나 진료 보려면 어디로 가야 해요?": Object.freeze({
      id: "public-health-center-guidance",
      description: "보건소 위치·진료 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "보건소 위치·진료 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "북구청 홈의 주요사이트에서 보건소로 이동합니다.", targetId: "nav-civil-service", delayMs: 1500 }),
        Object.freeze({ message: "보건소 위치·진료 안내 화면으로 이동합니다.", routeId: "public-health-center-guidance", delayMs: 1200 }),
        Object.freeze({ message: "보건소 위치·진료 안내를 확인합니다. 실제 이용 정보는 공식 채널에서 직접 확인해야 합니다.", targetId: "health-center-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "안내가 완료되었습니다. 실제 보건소 이용, 진료 예약, 본인인증, 건강정보 입력, 제출은 사용자가 공식 채널에서 직접 확인해야 합니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
    "전입신고 어디서 하나요?": Object.freeze({
      id: "move-in-report-guidance",
      description: "전입신고 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "전입신고 경로를 안내해 드립니다.", delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200 }),
        Object.freeze({ message: "전입신고 안내 화면으로 이동합니다.", routeId: "move-in-report-guidance", delayMs: 1200 }),
        Object.freeze({ message: "전입신고 안내를 확인합니다. 실제 본인인증, 주소·세대주·가족관계 정보 입력, 정부24/주민센터 제출 전 사용자 확인이 필요합니다.", targetId: "move-in-guidance-card", delayMs: 2000 }),
        Object.freeze({ message: "안내가 완료되었습니다. 실제 전입신고, 본인인증, 세대주·주소·가족관계 등 개인정보 입력, 정부24 또는 주민센터 제출은 사용자가 직접 확인해야 합니다. STOP_FOR_USER_CONFIRMATION" }),
      ]),
    }),
  });

  // ═══════════════════════════════════════════════════════════════════
  // Internal helpers
  // ═══════════════════════════════════════════════════════════════════

  function _appendChatMessage(role, text) {
    if (!_chatThread) return;
    var messageEl = document.createElement("div");
    messageEl.className = "chat-msg chat-msg--" + role;
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
  }

  function _clearHighlights() {
    for (var i = 0; i < _highlightedEls.length; i++) {
      if (_highlightedEls[i]) {
        _highlightedEls[i].classList.remove(HIGHLIGHT_CLASS);
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

    if (step.typeQuery) {
      var demoEl = _getCanvasEl();
      if (demoEl) {
        var input = demoEl.querySelector(".bg-dept-search__input");
        if (input) {
          input.value = step.typeQuery;
          input.classList.add(TYPING_CLASS);
          _highlightedEls.push(input);
        }
      }
    }

    if (step.submitSearch) {
      var demoEl = _getCanvasEl();
      if (demoEl) {
        var btn = demoEl.querySelector(".bg-dept-search__btn");
        if (btn) {
          btn.click();
        }
      }
    }

    // Show chat message AFTER DOM actions so the left-pane state is visible
    // before the explanation text.
    _appendChatMessage("ai", step.message);

    // Schedule next step or terminate
    if (typeof step.delayMs === "number" && step.delayMs > 0) {
      _timer = window.setTimeout(function () {
        _timer = null;
        _executeStep(index + 1);
      }, step.delayMs);
    } else {
      // No delay → terminal step (done message)
      _setState(STATE_DONE);
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

  window.CitizenFirstChoreography = Object.freeze({
    start: start,
    cancel: cancel,
    getState: getState,
    getCurrentJourneyId: getCurrentJourneyId,
    hasJourney: hasJourney,
    states: Object.freeze({
      idle: STATE_IDLE,
      running: STATE_RUNNING,
      done: STATE_DONE,
      cancelled: STATE_CANCELLED,
    }),
  });
})();
