/**
 * Shared parity scenario vocabulary for the resident Page Agent demo.
 *
 * Browser owner for scenario IDs, triggers, nav targets, and completion copy.
 * Server mock plans under functions/api/page-agent/_parity_scenarios.js must
 * keep the same IDs / data-action-target steps (not a second product map).
 */
(function () {
  'use strict';

  // Intermediate routes that must never count as final success for #1145.
  var FORBIDDEN_SUCCESS_ROUTES = Object.freeze([
    'home',
    'civil-service',
    'complaint-category',
    'complaint-board',
    'mayor-office',
    'official-content',
  ]);

  var SCENARIOS = [
    {
      id: 'apartment_contact',
      triggers: [
        '공동주택과 연락처 찾아줘',
        '공동주택 연락처',
        '아파트 연락처',
        '공동주택과',
        'apartment contact',
      ],
      routeId: 'apartment-dept',
      // Direct home targets — never stop at nav-civil-service.
      navSteps: [
        { target: 'nav-apartment-dept', description: '홈 → 행정조직도' },
      ],
      // Fail-closed visible content: any one keyword is sufficient.
      requiredVisible: ['공동주택', '연락처', '전화'],
      response:
        '공동주택과 조직 및 업무안내 화면입니다. 종합민원 메뉴에서 공동주택과 담당 업무와 연락처를 확인할 수 있습니다.',
    },
    {
      id: 'bulky_waste_menu',
      triggers: [
        '대형폐기물 신청 메뉴 찾아줘',
        '대형폐기물 신청',
        '대형폐기물 배출',
        '폐기물 신청',
        'bulky waste',
      ],
      routeId: 'bulky-waste-disposal',
      navSteps: [
        { target: 'nav-bulky-waste-disposal', description: '대형폐기물 처리' },
      ],
      requiredVisible: ['대형폐기물', '배출', '신청'],
      response:
        '대형폐기물 배출방법 안내 화면입니다. 종합민원 메뉴에서 대형폐기물 배출 신청 방법과 수수료를 확인할 수 있습니다.',
    },
    {
      id: 'passport_procedure',
      triggers: ['여권 발급 절차를 찾아줘', '여권 발급', '여권 절차', '여권', 'passport'],
      routeId: 'passport-guidance',
      navSteps: [
        { target: 'nav-passport-guidance', description: '여권 발급' },
      ],
      requiredVisible: ['여권', '구비서류', '수수료', '발급'],
      response:
        '여권민원 안내 화면입니다. 종합민원 메뉴에서 여권 종류, 유효기간, 발급수수료, 신청절차, 구비서류를 확인할 수 있습니다.',
    },
    {
      id: 'complaint_screen',
      triggers: [
        '민원 작성 화면을 열어줘',
        '민원 작성',
        '민원 신청',
        '민원 게시판',
        // #1164 stakeholder phrasing observed in Production
        '가로등이 고장 났어요',
        '가로등이 고장났어요',
        '가로등 고장',
        'complaint',
      ],
      routeId: 'complaint-write',
      // Must complete board → write; complaint-board alone is not success.
      navSteps: [
        { target: 'nav-complaint-board', description: '소통광장' },
        { target: 'complaint-write', description: '글쓰기' },
      ],
      requiredVisible: ['제목', '작성', '민원'],
      response:
        '민원 글쓰기 화면입니다. 종합민원 → 민원 유형 선택 후 민원 게시판에서 글쓰기를 통해 AI가 민원 초안 작성을 도와드립니다.',
    },
    {
      id: 'mayor_proposal_writing',
      triggers: [
        '구청장에게 제안할 글 작성을 도와줘',
        '구청장에게 바란다',
        '구청장 제안',
        '구청장 글 작성',
        // #1164 stakeholder phrasing observed in Production
        '북구청장에게 글을 쓰고 싶어요',
        '북구청장에게 글 쓰고 싶어요',
        'mayor proposal',
      ],
      routeId: 'mayor-complaint-write',
      navSteps: [
        { target: 'mayor-office-open', description: '열린구청장실 바로가기' },
        { target: 'mayor-message-write', description: '구청장에게 바란다' },
      ],
      requiredVisible: ['구청장', '제목', '제안'],
      response:
        '구청장에게 바란다 작성 화면입니다. 열린구청장실에서 구청장에게 바란다를 통해 AI와 함께 구정 제안을 작성하고 제출 전에 직접 검토합니다.',
    },
  ];

  window.PageAgentParityScenarios = Object.freeze({
    SCENARIOS: SCENARIOS,
    FORBIDDEN_SUCCESS_ROUTES: FORBIDDEN_SUCCESS_ROUTES,
    UNKNOWN_RESPONSE:
      '다음 항목 중 하나를 선택해 주세요: 공동주택과 연락처 찾기, 대형폐기물 신청 메뉴 찾기, 여권 발급 절차 찾기, 민원 작성 화면 열기, 구청장에게 제안 글 작성',
  });
})();
