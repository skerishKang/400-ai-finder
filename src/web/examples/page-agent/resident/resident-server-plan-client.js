/**
 * Same-origin client for POST /api/page-agent/plan.
 *
 * Explicit server mode only (DOM data attribute / injected config).
 * Query-string alone never enables this client.
 * Plans are executed through the existing Page Agent action loop — never by
 * jumping directly to a final route.
 */
(function () {
  'use strict';

  var PLAN_PATH = '/api/page-agent/plan';
  var _controller = null;
  var _token = 0;
  var _activeToken = 0;

  function readExplicitMode() {
    // 1) Build/runtime injected config (highest priority for controlled deploys).
    var cfg = window.__PAGE_AGENT_PLAN_CONFIG__;
    if (cfg && typeof cfg === 'object' && typeof cfg.mode === 'string') {
      return String(cfg.mode).trim().toLowerCase();
    }
    // 2) Explicit DOM data attribute on <html> or <body>.
    var root = document.documentElement;
    var body = document.body;
    var fromDom =
      (root && root.getAttribute('data-page-agent-plan-mode')) ||
      (body && body.getAttribute('data-page-agent-plan-mode')) ||
      '';
    return String(fromDom || '').trim().toLowerCase();
  }

  /**
   * Server planning is enabled only by explicit config/attribute.
   * A bare ?plan=server (or similar) query flag alone is ignored.
   */
  function isEnabled() {
    var mode = readExplicitMode();
    return mode === 'server' || mode === 'plan-server' || mode === 'server-plan';
  }

  function cancel() {
    _token += 1;
    _activeToken = _token;
    if (_controller) {
      try {
        _controller.abort();
      } catch (_) {}
      _controller = null;
    }
  }

  function currentRouteId() {
    try {
      if (
        window.CitizenActionDemoCanvas &&
        typeof window.CitizenActionDemoCanvas.getCurrentRouteId === 'function'
      ) {
        return String(window.CitizenActionDemoCanvas.getCurrentRouteId() || '');
      }
    } catch (_) {}
    return '';
  }

  /**
   * @param {string} question
   * @param {{ maxSteps?: number }} [opts]
   * @returns {Promise<{ ok: true, plan: object, token: number } | { ok: false, error: string, detail?: string, token: number }>}
   */
  function requestPlan(question, opts) {
    opts = opts || {};
    if (!isEnabled()) {
      return Promise.resolve({
        ok: false,
        error: 'page_agent_server_mode_disabled',
        detail: 'explicit_mode_required',
        token: _activeToken,
      });
    }

    cancel();
    _token += 1;
    var token = _token;
    _activeToken = token;
    _controller = new AbortController();

    var body = {
      request_id: 'resident-' + Date.now() + '-' + token,
      question: String(question || ''),
      current_route: currentRouteId(),
      available_actions: ['click', 'input', 'select', 'scroll', 'read', 'navigate'],
      max_steps: typeof opts.maxSteps === 'number' ? opts.maxSteps : 10,
    };

    var url = new URL(PLAN_PATH, window.location.origin);
    if (url.origin !== window.location.origin) {
      return Promise.resolve({
        ok: false,
        error: 'page_agent_origin_blocked',
        detail: 'cross_origin_endpoint',
        token: token,
      });
    }

    return fetch(url.pathname, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: _controller.signal,
      credentials: 'same-origin',
      cache: 'no-store',
    })
      .then(function (res) {
        if (token !== _activeToken) {
          return { ok: false, error: 'page_agent_cancelled', detail: 'stale_token', token: token };
        }
        return res.text().then(function (text) {
          var data = null;
          try {
            data = text ? JSON.parse(text) : null;
          } catch (_) {
            return {
              ok: false,
              error: 'page_agent_malformed_response',
              detail: 'json_parse',
              token: token,
            };
          }
          if (!data || typeof data !== 'object') {
            return {
              ok: false,
              error: 'page_agent_malformed_response',
              detail: 'empty_body',
              token: token,
            };
          }
          if (data.ok === true && data.plan && Array.isArray(data.plan.steps)) {
            return { ok: true, plan: data.plan, token: token };
          }
          return {
            ok: false,
            error: data.error || 'page_agent_plan_failed',
            detail: data.detail || ('http_' + res.status),
            token: token,
          };
        });
      })
      .catch(function (err) {
        if (token !== _activeToken) {
          return { ok: false, error: 'page_agent_cancelled', detail: 'stale_token', token: token };
        }
        if (err && err.name === 'AbortError') {
          return { ok: false, error: 'page_agent_cancelled', detail: 'aborted', token: token };
        }
        return {
          ok: false,
          error: 'page_agent_network_error',
          detail: err && err.message ? String(err.message).slice(0, 120) : 'fetch_failed',
          token: token,
        };
      })
      .then(function (result) {
        if (token === _activeToken) {
          _controller = null;
        }
        return result;
      });
  }

  /**
   * Convert a validated server plan into a PageAgent customFetch responder
   * that drives the real tool loop (click_element_by_index / done).
   * Does not navigate directly to the final route.
   */
  function createPlanFetchAdapter(plan, completionText) {
    var steps = (plan && plan.steps ? plan.steps : []).slice();
    var stepIdx = 0;
    var finished = false;

    function extractBrowserState(raw) {
      var m = String(raw || '').match(/<browser_state>([\s\S]*?)<\/browser_state>/);
      return m ? m[1] : '';
    }

    function extractUserRequest(raw) {
      var m = String(raw || '').match(/<user_request>([\s\S]*?)<\/user_request>/);
      return m ? m[1].trim() : '';
    }

    function getLastUserMessage(payload) {
      if (!payload || !payload.messages || !Array.isArray(payload.messages)) return '';
      for (var i = payload.messages.length - 1; i >= 0; i--) {
        if (payload.messages[i].role === 'user') {
          var content = payload.messages[i].content;
          if (typeof content === 'string') return content;
          return String(content || '');
        }
      }
      return '';
    }

    function findElementIndexByTarget(state, actionTarget) {
      var lines = String(state || '').split('\n');
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        if (line.indexOf('data-action-target=') === -1) continue;
        var m = line.match(/data-action-target=([^\s>"']+)/);
        if (!m) continue;
        var val = m[1];
        if (val.indexOf('...') !== -1) val = val.slice(0, val.indexOf('...'));
        if (actionTarget === val || actionTarget.indexOf(val) === 0 || val.indexOf(actionTarget) === 0) {
          var idxMatch = line.match(/\[(\d+)\]/);
          if (idxMatch) return parseInt(idxMatch[1], 10);
        }
      }
      return null;
    }

    function actionTargetFromSelector(selector) {
      if (!selector) return '';
      var m = String(selector).match(/data-action-target\s*=\s*["']?([^"'\]]+)/);
      return m ? m[1] : String(selector).replace(/^\[data-action-target="/, '').replace(/"\]$/, '');
    }

    function buildToolResponse(macroToolName, action) {
      return {
        id: 'chatcmpl-server-plan-' + Date.now(),
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: 'page-agent-server-plan',
        choices: [
          {
            index: 0,
            message: {
              role: 'assistant',
              content: null,
              tool_calls: [
                {
                  id: 'call_server_plan_' + Date.now(),
                  type: 'function',
                  function: {
                    name: macroToolName,
                    arguments: JSON.stringify({ action: action }),
                  },
                },
              ],
            },
            finish_reason: 'tool_calls',
          },
        ],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
      };
    }

    function respond(input, init) {
      var body = {};
      try {
        body = JSON.parse((init && init.body) || '{}');
      } catch (_) {
        body = {};
      }

      var macroToolName = 'AgentOutput';
      if (
        body.tools &&
        body.tools.length &&
        body.tools[0] &&
        body.tools[0].function &&
        body.tools[0].function.name
      ) {
        macroToolName = body.tools[0].function.name;
      }

      var rawMessage = getLastUserMessage(body);
      var browserState = extractBrowserState(rawMessage);
      extractUserRequest(rawMessage);

      if (finished) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: 'chatcmpl-server-plan-stop',
              object: 'chat.completion',
              created: Math.floor(Date.now() / 1000),
              model: 'page-agent-server-plan',
              choices: [
                {
                  index: 0,
                  message: {
                    role: 'assistant',
                    content: completionText || '작업을 완료했습니다.',
                  },
                  finish_reason: 'stop',
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        );
      }

      // Walk plan steps; map click targets into Page Agent click_element_by_index.
      while (stepIdx < steps.length) {
        var step = steps[stepIdx];
        stepIdx += 1;

        if (step.action === 'click') {
          var targetId = actionTargetFromSelector(step.target);
          var elementIndex = findElementIndexByTarget(browserState, targetId);
          if (elementIndex !== null) {
            var clickAction = { click_element_by_index: { index: elementIndex } };
            return Promise.resolve(
              new Response(JSON.stringify(buildToolResponse(macroToolName, clickAction)), {
                status: 200,
                headers: { 'Content-Type': 'application/json' },
              })
            );
          }
          // Target not visible yet — skip and try next planned step.
          continue;
        }

        if (step.action === 'scroll') {
          var scrollAction = { scroll: { pages: 1 } };
          return Promise.resolve(
            new Response(JSON.stringify(buildToolResponse(macroToolName, scrollAction)), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            })
          );
        }

        if (step.action === 'read' || step.action === 'navigate') {
          // Terminal boundary inside the tool loop (done), not a direct route jump.
          finished = true;
          var doneText =
            (step.value && String(step.value)) ||
            completionText ||
            '안내 화면을 확인했습니다. 제출은 사용자가 직접 진행합니다.';
          var doneAction = { done: { text: doneText, success: true } };
          return Promise.resolve(
            new Response(JSON.stringify(buildToolResponse(macroToolName, doneAction)), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            })
          );
        }
      }

      finished = true;
      var fallback = {
        done: {
          text: completionText || '작업을 완료했습니다.',
          success: true,
        },
      };
      return Promise.resolve(
        new Response(JSON.stringify(buildToolResponse(macroToolName, fallback)), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    }

    return { respond: respond };
  }

  window.PageAgentServerPlanClient = Object.freeze({
    isEnabled: isEnabled,
    requestPlan: requestPlan,
    cancel: cancel,
    createPlanFetchAdapter: createPlanFetchAdapter,
    PLAN_PATH: PLAN_PATH,
  });
})();
