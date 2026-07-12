(function () {
  'use strict';

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
      response: '공동주택과 조직 및 업무안내 화면입니다. 공동주택과 담당 업무와 연락처를 확인할 수 있습니다.',
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
      response: '대형폐기물 배출방법 안내 화면입니다. 수탁업체 전화 신고 또는 여기로 어플을 통한 신청 방법을 확인할 수 있습니다.',
    },
    {
      id: 'passport_procedure',
      triggers: [
        '여권 발급 절차를 찾아줘',
        '여권 발급',
        '여권 절차',
        '여권',
        'passport',
      ],
      routeId: 'passport-guidance',
      response: '여권민원 안내 화면입니다. 여권 종류, 유효기간, 발급수수료, 신청절차, 구비서류를 확인할 수 있습니다.',
    },
    {
      id: 'complaint_screen',
      triggers: [
        '민원 작성 화면을 열어줘',
        '민원 작성',
        '민원 신청',
        '민원 게시판',
        'complaint',
      ],
      routeId: 'complaint-write',
      response: '민원 글쓰기 화면입니다. AI가 민원 제목과 본문 초안을 입력하고 제출 전에 주민이 직접 검토합니다.',
    },
    {
      id: 'mayor_proposal_writing',
      triggers: [
        '구청장에게 제안할 글 작성을 도와줘',
        '구청장에게 바란다',
        '구청장 제안',
        '구청장 글 작성',
        'mayor proposal',
      ],
      routeId: 'mayor-complaint-write',
      response: '구청장에게 바란다 작성 화면입니다. AI와 함께 구정 제안을 작성하고 제출 전에 직접 검토합니다.',
    },
  ];

  var UNKNOWN_RESPONSE =
    '다음 항목 중 하나를 선택해 주세요: 공동주택과 연락처 찾기, 대형폐기물 신청 메뉴 찾기, 여권 발급 절차 찾기, 민원 작성 화면 열기, 구청장에게 제안 글 작성';

  function normalize(text) {
    if (typeof text !== 'string') return '';
    return text.replace(/\s+/g, ' ').trim();
  }

  function findScenario(userMessage) {
    var n = normalize(userMessage);
    if (!n) return null;
    for (var i = 0; i < SCENARIOS.length; i++) {
      var s = SCENARIOS[i];
      for (var j = 0; j < s.triggers.length; j++) {
        if (n.indexOf(s.triggers[j]) !== -1 || s.triggers[j].indexOf(n) !== -1) {
          return s;
        }
      }
    }
    return null;
  }

  function getLastUserMessage(payload) {
    if (!payload || !payload.messages || !Array.isArray(payload.messages)) return '';
    var msgs = payload.messages;
    for (var i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'user') {
        var content = msgs[i].content;
        if (typeof content === 'string') return content;
        if (Array.isArray(content)) {
          var parts = [];
          for (var k = 0; k < content.length; k++) {
            if (content[k] && typeof content[k].text === 'string') parts.push(content[k].text);
          }
          return parts.join(' ');
        }
        return String(content);
      }
    }
    return '';
  }

  function buildToolResponse(macroToolName, action) {
    return {
      id: 'chatcmpl-resident-mock-' + Date.now(),
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: 'resident-mock',
      choices: [{
        index: 0,
        message: {
          role: 'assistant',
          content: null,
          tool_calls: [{
            id: 'call_resident_' + Date.now(),
            type: 'function',
            function: {
              name: macroToolName,
              arguments: JSON.stringify({ action: action }),
            },
          }],
        },
        finish_reason: 'tool_calls',
      }],
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
    };
  }

  function buildStopResponse() {
    return {
      id: 'chatcmpl-resident-stop-' + Date.now(),
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: 'resident-mock',
      choices: [{
        index: 0,
        message: { role: 'assistant', content: '작업을 완료했습니다.' },
        finish_reason: 'stop',
      }],
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
    };
  }

  var turnComplete = false;
  var lastUserMessage = '';
  var navigationDone = false;

  function respond(input, init) {
    var body = {};
    try { body = JSON.parse((init && init.body) || '{}'); } catch (e) { body = {}; }

    var macroToolName = 'AgentOutput';
    if (body.tools && body.tools.length && body.tools[0] && body.tools[0].function && body.tools[0].function.name) {
      macroToolName = body.tools[0].function.name;
    }

    var rawMessage = getLastUserMessage(body);
    var userMessage = rawMessage;
    var match = rawMessage.match(/<user_request>([\s\S]*?)<\/user_request>/);
    if (match) userMessage = match[1].trim();

    if (turnComplete && rawMessage === lastUserMessage) {
      return new Response(JSON.stringify(buildStopResponse()), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (rawMessage !== lastUserMessage) {
      turnComplete = false;
      navigationDone = false;
      lastUserMessage = rawMessage;
    }

    var scenario = findScenario(userMessage);
    var action;

    if (!scenario) {
      action = { done: { text: UNKNOWN_RESPONSE, success: false } };
      turnComplete = true;
    } else if (!navigationDone) {
      navigationDone = true;
      action = {
        execute_javascript: {
          script: '(function(){ window.CitizenActionDemoCanvas.navigateToRoute("' + scenario.routeId + '"); return new Promise(function(r){ setTimeout(r, 900); }); })()',
        },
      };
    } else {
      turnComplete = true;
      action = { done: { text: scenario.response, success: true } };
    }

    return new Response(JSON.stringify(buildToolResponse(macroToolName, action)), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  window.PageAgentMockModel = {
    SCENARIOS: SCENARIOS,
    respond: respond,
    handleCompletion: function (url, payload) {
      return respond(url, { body: JSON.stringify(payload || {}) }).then(function (r) { return r.json(); });
    },
  };

  window.PageAgentLabMockModel = window.PageAgentMockModel;
})();
