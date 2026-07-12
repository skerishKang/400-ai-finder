(function () {
  'use strict';

  var SCENARIOS = [
    // ── apartment_contact (navigate to civil-service, click-approved) ──
    {
      id: 'apartment_contact',
      triggers: ['공동주택과 연락처 찾아줘','공동주택 연락처','아파트 연락처','공동주택과','apartment contact'],
      routeId: 'apartment-dept',
      navSteps: [
        { target: 'nav-civil-service', description: '종합민원 → 민원 신청하기' },
      ],
      response: '공동주택과 조직 및 업무안내 화면입니다. 종합민원 메뉴에서 공동주택과 담당 업무와 연락처를 확인할 수 있습니다.',
    },
    // ── bulky_waste_menu (navigate to civil-service, click-approved) ──
    {
      id: 'bulky_waste_menu',
      triggers: ['대형폐기물 신청 메뉴 찾아줘','대형폐기물 신청','대형폐기물 배출','폐기물 신청','bulky waste'],
      routeId: 'bulky-waste-disposal',
      navSteps: [
        { target: 'nav-civil-service', description: '종합민원 → 민원 신청하기' },
      ],
      response: '대형폐기물 배출방법 안내 화면입니다. 종합민원 메뉴에서 대형폐기물 배출 신청 방법과 수수료를 확인할 수 있습니다.',
    },
    // ── passport_procedure (navigate to civil-service, click-approved) ──
    {
      id: 'passport_procedure',
      triggers: ['여권 발급 절차를 찾아줘','여권 발급','여권 절차','여권','passport'],
      routeId: 'passport-guidance',
      navSteps: [
        { target: 'nav-civil-service', description: '종합민원 → 민원 신청하기' },
      ],
      response: '여권민원 안내 화면입니다. 종합민원 메뉴에서 여권 종류, 유효기간, 발급수수료, 신청절차, 구비서류를 확인할 수 있습니다.',
    },
    // ── complaint_screen (multi-step click navigation) ──
    {
      id: 'complaint_screen',
      triggers: ['민원 작성 화면을 열어줘','민원 작성','민원 신청','민원 게시판','complaint'],
      routeId: 'complaint-write',
      navSteps: [
        { target: 'nav-civil-service', description: '종합민원 → 민원 신청하기' },
        { target: 'nav-complaint-category', description: '민원 유형 선택' },
      ],
      response: '민원 글쓰기 화면입니다. 종합민원 → 민원 유형 선택 후 민원 게시판에서 글쓰기를 통해 AI가 민원 초안 작성을 도와드립니다.',
    },
    // ── mayor_proposal_writing (multi-step click navigation) ──
    {
      id: 'mayor_proposal_writing',
      triggers: ['구청장에게 제안할 글 작성을 도와줘','구청장에게 바란다','구청장 제안','구청장 글 작성','mayor proposal'],
      routeId: 'mayor-complaint-write',
      navSteps: [
        { target: 'mayor-office-open', description: '열린구청장실 바로가기' },
        { target: 'mayor-message-write', description: '구청장에게 바란다' },
      ],
      response: '구청장에게 바란다 작성 화면입니다. 열린구청장실에서 구청장에게 바란다를 통해 AI와 함께 구정 제안을 작성하고 제출 전에 직접 검토합니다.',
    },
  ];

  var UNKNOWN_RESPONSE =
    '다음 항목 중 하나를 선택해 주세요: 공동주택과 연락처 찾기, 대형폐기물 신청 메뉴 찾기, 여권 발급 절차 찾기, 민원 작성 화면 열기, 구청장에게 제안 글 작성';

  // ── Diagnostics ──────────────────────────────────────────────────────────
  var _diag = {
    callCount: 0,
    toolNames: [],
    actionNames: [],
    taskIds: [],
    successValues: [],
    completionTexts: [],
    lastSuccess: null,
    lastCompletionText: null,
    lastActionName: null,
  };

  function resetDiagnostics() {
    _diag = {
      callCount: 0, toolNames: [], actionNames: [], taskIds: [],
      successValues: [], completionTexts: [],
      lastSuccess: null, lastCompletionText: null, lastActionName: null,
    };
  }

  function recordDiag(toolName, actionName, taskId, success, completionText) {
    _diag.callCount++;
    _diag.toolNames.push(toolName);
    _diag.actionNames.push(actionName);
    _diag.taskIds.push(taskId);
    _diag.successValues.push(success);
    _diag.completionTexts.push(completionText);
    _diag.lastActionName = actionName;
    _diag.lastSuccess = success;
    _diag.lastCompletionText = completionText;
  }

  // ── Helpers ──────────────────────────────────────────────────────────────
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

  function extractUserRequest(raw) {
    var m = raw.match(/<user_request>([\s\S]*?)<\/user_request>/);
    return m ? m[1].trim() : '';
  }

  function extractBrowserState(raw) {
    var m = raw.match(/<browser_state>([\s\S]*?)<\/browser_state>/);
    return m ? m[1] : '';
  }

  function findElementIndexByTarget(state, targetId) {
    var lines = state.split('\n');
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (line.indexOf('data-action-target=') === -1) continue;
      var m = line.match(/data-action-target=([^\s>]+)/);
      if (m) {
        var val = m[1];
        if (val.indexOf('...') !== -1) val = val.slice(0, val.indexOf('...'));
        if (targetId.indexOf(val) === 0) {
          var idxMatch = line.match(/\[(\d+)\]/);
          if (idxMatch) return parseInt(idxMatch[1], 10);
        }
      }
    }
    return null;
  }

  // ── Navigation state ─────────────────────────────────────────────────────
  var _sessionTask = null;       // Current scenario object
  var _sessionNavIdx = 0;        // Current nav step index
  var _sessionDone = false;      // Has returned done already?
    var _lastSessionKey = '';  // Last seen user request (session dedup)

  function resetSession() {
    _sessionTask = null;
    _sessionNavIdx = 0;
    _sessionDone = false;
    _lastSessionKey = '';
  }

  // ── Response builders ────────────────────────────────────────────────────
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

  function buildStopResponse(text) {
    return {
      id: 'chatcmpl-resident-stop-' + Date.now(),
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: 'resident-mock',
      choices: [{
        index: 0,
        message: { role: 'assistant', content: text || '작업을 완료했습니다.' },
        finish_reason: 'stop',
      }],
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
    };
  }

  // ── Main respond handler ────────────────────────────────────────────────
  function respond(input, init) {
    var body = {};
    try { body = JSON.parse((init && init.body) || '{}'); } catch (e) { body = {}; }

    var macroToolName = 'AgentOutput';
    if (body.tools && body.tools.length && body.tools[0] && body.tools[0].function && body.tools[0].function.name) {
      macroToolName = body.tools[0].function.name;
    }

    var rawMessage = getLastUserMessage(body);
    var userRequest = extractUserRequest(rawMessage);
    var browserState = extractBrowserState(rawMessage);
    var sessionKey = userRequest || rawMessage;

    // Dedup: if same session was already completed, return stop
    if (_sessionDone && sessionKey === _lastSessionKey) {
      return new Response(JSON.stringify(buildStopResponse()), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // New user request → reset navigation progress (but keep across turns with same request)
    if (sessionKey !== _lastSessionKey) {
      _lastSessionKey = sessionKey;
      _sessionNavIdx = 0;
      _sessionDone = false;
    }

    var scenario = _sessionTask || findScenario(userRequest);

    if (!scenario) {
      // ── Unknown / unsupported request ──
      _sessionDone = true;
      var unknownAction = { done: { text: UNKNOWN_RESPONSE, success: false } };
      recordDiag(macroToolName, 'done', null, false, UNKNOWN_RESPONSE);

      return new Response(JSON.stringify(buildToolResponse(macroToolName, unknownAction)), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    _sessionTask = scenario;

    // Check if we have nav steps remaining and can find the target element
    if (_sessionNavIdx < scenario.navSteps.length && browserState) {
      var step = scenario.navSteps[_sessionNavIdx];
      var elementIndex = findElementIndexByTarget(browserState, step.target);

      if (elementIndex !== null) {
        // Found target → click it
        _sessionNavIdx++;
        var clickAction = { click_element_by_index: { index: elementIndex } };
        recordDiag(macroToolName, 'click_element_by_index', scenario.id, null, null);

        return new Response(JSON.stringify(buildToolResponse(macroToolName, clickAction)), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      } else {
        // Target element not found in page state → skip to next step or done
        _sessionNavIdx++;
      }
    }

    // ── No more nav steps → done ──
    _sessionDone = true;
    var doneAction = { done: { text: scenario.response, success: true } };
    recordDiag(macroToolName, 'done', scenario.id, true, scenario.response);

    return new Response(JSON.stringify(buildToolResponse(macroToolName, doneAction)), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Try to elide {navSteps} from serialization for clean JSON test assertions.
  // We still keep navSteps on SCENARIOS for internal logic.
  function getPublicScenarios() {
    return SCENARIOS.map(function (s) {
      return {
        id: s.id,
        triggers: s.triggers,
        routeId: s.routeId,
        response: s.response,
      };
    });
  }

  // ── Exports ──────────────────────────────────────────────────────────────
  window.PageAgentMockModel = {
    SCENARIOS: SCENARIOS,
    getPublicScenarios: getPublicScenarios,
    getDiagnostics: function () { return _diag; },
    resetDiagnostics: resetDiagnostics,
    respond: respond,
    handleCompletion: function (url, payload) {
      return respond(url, { body: JSON.stringify(payload || {}) }).then(function (r) { return r.json(); });
    },
  };

  window.PageAgentLabMockModel = window.PageAgentMockModel;
})();
