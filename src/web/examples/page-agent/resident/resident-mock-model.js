(function () {
  'use strict';

  // Scenario vocabulary lives in parity-scenarios.js (single browser owner).
  var parity = window.PageAgentParityScenarios || {};
  var SCENARIOS = parity.SCENARIOS || [];
  var UNKNOWN_RESPONSE =
    parity.UNKNOWN_RESPONSE ||
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
  var _lastSessionKey = '';      // Last seen user request (session dedup)

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

    // New user request → reset all navigation progress and stale task
    if (sessionKey !== _lastSessionKey) {
      _lastSessionKey = sessionKey;
      _sessionTask = null;  // Clear stale task from previous request
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
        // Target element not found in page state → fail closed
        _sessionDone = true;
        var missingTargetMsg = '안내 화면에서 필요한 요소를 찾을 수 없습니다: ' + step.target + '. 페이지 상태를 확인해 주세요.';
        var failAction = { done: { text: missingTargetMsg, success: false } };
        recordDiag(macroToolName, 'done', scenario.id, false, missingTargetMsg);

        return new Response(JSON.stringify(buildToolResponse(macroToolName, failAction)), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    }

    // ── No more nav steps → validate final route before success ──
    _sessionDone = true;
    var canvasRoute = null;
    try {
      if (typeof window !== 'undefined' && window.CitizenActionDemoCanvas && typeof window.CitizenActionDemoCanvas.getCurrentRouteId === 'function') {
        canvasRoute = window.CitizenActionDemoCanvas.getCurrentRouteId();
      }
    } catch (_) { /* canvas unavailable */ }

    var expectedRoute = scenario.routeId;
    if (canvasRoute === expectedRoute) {
      var doneAction = { done: { text: scenario.response, success: true } };
      recordDiag(macroToolName, 'done', scenario.id, true, scenario.response);
      return new Response(JSON.stringify(buildToolResponse(macroToolName, doneAction)), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    } else {
      var wrongRouteMsg = '안내 경로가 올바르지 않습니다. 예상 경로: ' + expectedRoute + ', 실제 경로: ' + (canvasRoute || 'unknown') + '. 다시 시도해 주세요.';
      var failAction = { done: { text: wrongRouteMsg, success: false } };
      recordDiag(macroToolName, 'done', scenario.id, false, wrongRouteMsg);
      return new Response(JSON.stringify(buildToolResponse(macroToolName, failAction)), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
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
    resetSession: resetSession,
    respond: respond,
    handleCompletion: function (url, payload) {
      return respond(url, { body: JSON.stringify(payload || {}) }).then(function (r) { return r.json(); });
    },
  };

  window.PageAgentLabMockModel = window.PageAgentMockModel;
})();
