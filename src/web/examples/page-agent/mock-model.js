// ═══════════════════════════════════════════════════════════════════════════
// mock-model.js — Local deterministic model adapter for Page Agent lab
//
// This module provides a deterministic mock model that speaks the exact
// OpenAI-compatible *tool-call* contract the real PageAgent expects:
//
//   POST <baseURL>/chat/completions
//     → tool_choice: { function: { name: "AgentOutput" } }
//     → response: message.tool_calls[0].function = {
//         name: "AgentOutput",
//         arguments: JSON.stringify({ action: { <toolName>: <toolInput> } })
//       }
//
// The agent loop (PageAgentCore → PageController) executes the returned
// action as a real DOM operation. For a supported task the mock drives a
// real `execute_javascript` PageController action that scrolls the target
// section into view, then a `done` action to complete the task.
//
// Task support:
//   - "Show the Quick Start section"        → scroll to #quick-start
//   - "Compare page-agent with browser-use"  → scroll to #vs-browser-use
//   - "Show the MIT license section"         → scroll to #license
//   - "Find the custom UI architecture"      → scroll to #architecture
//   - Unknown/bound tasks                    → bounded "unsupported" done
//
// MULTI-TURN SUPPORT:
//   After returning a done action, the mock sets turnComplete=true.  Any
//   subsequent request without a genuinely new user message returns a stop
//   response (no tool calls, finish_reason="stop") to halt the agent loop.
//   When a new user message is detected, turnComplete resets.
// ═══════════════════════════════════════════════════════════════════════════

(function () {
  'use strict';

  // ── Supported task definitions ────────────────────────────────────────

  var TASKS = [
    {
      id: 'quick-start',
      triggers: [
        'show the quick start section',
        'quick start',
        'show quick start',
        'go to quick start',
        'navigate to quick start',
        'find quick start',
      ],
      sectionId: 'quick-start',
      response:
        'I found the Quick Start section. The Quick Start section shows how to integrate Page Agent with a single script tag.',
    },
    {
      id: 'vs-browser-use',
      triggers: [
        'compare page-agent with browser-use',
        'page agent vs browser use',
        'how does page agent compare to browser use',
        'difference between page agent and browser use',
        'page agent browser use comparison',
        'compare',
      ],
      sectionId: 'vs-browser-use',
      response:
        'The comparison table between Page Agent and browser-use compares runtime, integration, DOM access, multi-page support, and use cases.',
    },
    {
      id: 'license',
      triggers: [
        'show the mit license section',
        'mit license',
        'show license',
        'view license',
        'find the license',
        'license information',
        'mit',
      ],
      sectionId: 'license',
      response:
        'Page Agent is published under the MIT License. The MIT License section shows the full license text.',
    },
    {
      id: 'architecture',
      triggers: [
        'find the custom ui architecture',
        'custom ui architecture',
        'architecture diagram',
        'show architecture',
        'page agent architecture',
        'how is page agent structured',
        'architecture',
        'custom ui',
      ],
      sectionId: 'architecture',
      response:
        'The Architecture section shows the layered structure: Panel UI, PageAgent orchestrator, PageAgentCore agent loop, LLM Client, PageController DOM engine, and Custom UI layer.',
    },
  ];

  // ── Normalize text for matching ────────────────────────────────────────

  function normalize(text) {
    if (typeof text !== 'string') return '';
    return text
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  // ── Find matching task ─────────────────────────────────────────────────

  function findTask(userMessage) {
    var n = normalize(userMessage);
    if (!n) return null;
    for (var i = 0; i < TASKS.length; i++) {
      var task = TASKS[i];
      for (var j = 0; j < task.triggers.length; j++) {
        var trigger = normalize(task.triggers[j]);
        if (n.indexOf(trigger) !== -1 || trigger.indexOf(n) !== -1) {
          return task;
        }
      }
    }
    return null;
  }

  // ── Extract the last user message from the request payload ──────────────
  // The PageAgent runtime may send content as either a plain string or an
  // array of content parts (OpenAI multi-modal format).  We always reduce
  // to a plain string for deterministic matching.

  function getLastUserMessage(payload) {
    if (!payload || !payload.messages || !Array.isArray(payload.messages)) {
      return '';
    }
    var msgs = payload.messages;
    for (var i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'user') {
        var content = msgs[i].content;
        if (typeof content === 'string') return content;
        if (Array.isArray(content)) {
          var parts = [];
          for (var k = 0; k < content.length; k++) {
            if (content[k] && typeof content[k].text === 'string') {
              parts.push(content[k].text);
            }
          }
          return parts.join(' ');
        }
        return String(content);
      }
    }
    return '';
  }

  // ── OpenAI-compatible tool-call response (AgentOutput macro) ────────────

  function buildToolResponse(macroToolName, action) {
    return {
      id: 'chatcmpl-local-mock-' + Date.now(),
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: 'local-mock',
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: null,
            tool_calls: [
              {
                id: 'call_local_' + Date.now(),
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
      usage: {
        prompt_tokens: 1,
        completion_tokens: 1,
        total_tokens: 2,
      },
    };
  }

  // ── Stop response (no tool calls) to break the agent loop ───────────────

  function buildStopResponse() {
    return {
      id: 'chatcmpl-local-stop-' + Date.now(),
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: 'local-mock',
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: 'Task processing complete.',
          },
          finish_reason: 'stop',
        },
      ],
      usage: {
        prompt_tokens: 1,
        completion_tokens: 1,
        total_tokens: 2,
      },
    };
  }

  // ── Non-local host blocklist ───────────────────────────────────────────

  var BLOCKED_HOSTS = [
    'cdn.jsdelivr.net',
    'registry.npmmirror.com',
    'dashscope.aliyuncs.com',
    'api.openai.com',
    'generativelanguage.googleapis.com',
    'alibaba.github.io',
    'raw.githubusercontent.com',
    'github.com',
  ];

  function isBlocked(url) {
    try {
      var u = new URL(url, window.location.origin);
      for (var i = 0; i < BLOCKED_HOSTS.length; i++) {
        if (u.hostname === BLOCKED_HOSTS[i] || u.hostname.endsWith('.' + BLOCKED_HOSTS[i])) {
          return true;
        }
      }
      return false;
    } catch (e) {
      return false;
    }
  }

  // ── Diagnostics for verification ───────────────────────────────────────

  var callCount = 0;
  var toolNames = [];
  var actionNames = [];
  var taskIds = [];
  var successValues = [];
  var completionTexts = [];

  function resetDiagnostics() {
    callCount = 0;
    toolNames = [];
    actionNames = [];
    taskIds = [];
    successValues = [];
    completionTexts = [];
    turnComplete = false;
    lastUserMessage = '';
  }

  window.__pageAgentLabResetDiagnostics = resetDiagnostics;

  // ── Multi-turn state tracking ──────────────────────────────────────────

  var turnComplete = false;
  var lastUserMessage = '';

  // ── Public API ─────────────────────────────────────────────────────────

  function respond(input, init) {
    var body = {};
    try {
      body = JSON.parse((init && init.body) || '{}');
    } catch (e) {
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

    var userMessage = getLastUserMessage(body);

    // ── Strip PageAgent's XML wrapper ──────────────────────────────────
    // PageAgent wraps the user's real prompt inside:
    //   <agent_state>
    //     <user_request>actual user prompt</user_request>
    //     ...system-generated sections...
    //   </agent_state>
    // We extract only the content between <user_request> and </user_request>
    // so the deterministic matcher sees the user's actual question, not the
    // XML boilerplate (which may contain unrelated strings like "quick start").
    var strippedMessage = userMessage;
    if (typeof userMessage === 'string') {
      var match = userMessage.match(/<user_request>([\s\S]*?)<\/user_request>/);
      if (match) {
        strippedMessage = match[1].trim();
      }
    }

    // ── DEBUG: log request details ──────────────────────────────────────
    var payloadMsgs = body.messages || [];
    var lastRole = payloadMsgs.length > 0 ? payloadMsgs[payloadMsgs.length - 1].role : 'none';
    var isFirstStep = userMessage.indexOf('<step_1>') === -1;
    console.log(
      '[MockModel] msgCount=' + payloadMsgs.length +
      ' lastRole=' + lastRole +
      ' firstStep=' + isFirstStep +
      ' turnComplete=' + turnComplete +
      ' strippedMsg="' + strippedMessage.substring(0, 80).replace(/"/g, '\\"') + '"'
    );

    // ── Multi-turn detection ──────────────────────────────────────────
    if (turnComplete) {
      if (userMessage === lastUserMessage) {
        console.log('[MockModel] -> stop (same turn, breaking loop)');
        return new Response(JSON.stringify(buildStopResponse()), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      console.log('[MockModel] -> new user message, resetting turn');
      turnComplete = false;
      lastUserMessage = userMessage;
    }

    // After the first action records a step, the user prompt embeds <step_1>.
    var firstStep = isFirstStep;

    var task = findTask(strippedMessage);
    var action;

    if (!task && firstStep) {
      action = {
        done: {
          text:
            'I can only help with the following topics on this page: Show the Quick Start section, ' +
            'Compare page-agent with browser-use, Show the MIT license section, ' +
            'and Find the custom UI architecture. Please try one of the supported tasks.',
          success: false,
        },
      };
    } else if (firstStep && task) {
      action = {
        execute_javascript: {
          script:
            "document.querySelectorAll('.page-agent-target-active').forEach(function(el) {" +
            " el.classList.remove('page-agent-target-active');" +
            " el.removeAttribute('data-page-agent-target');" +
            "});" +
            "document.getElementById('" +
            task.sectionId +
            "').scrollIntoView({block:'center'});" +
            "document.getElementById('" +
            task.sectionId +
            "').classList.add('page-agent-target-active');" +
            "document.getElementById('" +
            task.sectionId +
            "').setAttribute('data-page-agent-target','active');",
        },
      };
    } else {
      turnComplete = true;
      lastUserMessage = userMessage;
      action = {
        done: {
          text: task ? task.response : 'Task completed.',
          success: task ? true : true,
        },
      };
    }

    var actionKey = action && Object.keys(action)[0];
    var actionDetail = action && action[actionKey];

    callCount++;
    toolNames.push(macroToolName);
    actionNames.push(actionKey);
    taskIds.push(task ? task.id : null);
    if (actionKey === 'done') {
      successValues.push(actionDetail ? !!actionDetail.success : true);
      completionTexts.push(
        actionDetail && typeof actionDetail.text === 'string'
          ? actionDetail.text
          : ''
      );
    } else {
      successValues.push(null);
      completionTexts.push(null);
    }

    console.log('[MockModel] -> call#' + callCount + ' action=' + actionKey + ' task=' + (task ? task.id : 'null'));

    return new Response(JSON.stringify(buildToolResponse(macroToolName, action)), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  window.PageAgentMockModel = {
    TASKS: TASKS,
    BLOCKED_HOSTS: BLOCKED_HOSTS,
    respond: respond,
    handleCompletion: function (url, payload) {
      return respond(url, { body: JSON.stringify(payload || {}) }).then(function (r) {
        return r.json();
      });
    },
    isBlocked: isBlocked,
    getSupportedTaskIds: function () { return TASKS.map(function (t) { return t.id; }); },
    getTask: function (id) {
      for (var i = 0; i < TASKS.length; i++) { if (TASKS[i].id === id) return TASKS[i]; }
      return null;
    },
    isSupportedTask: function (id) { return !!this.getTask(id); },
    getAllTasks: function () { return TASKS; },
    getDiagnostics: function () {
      return {
        callCount: callCount,
        lastToolName: toolNames.length > 0 ? toolNames[toolNames.length - 1] : null,
        lastActionName: actionNames.length > 0 ? actionNames[actionNames.length - 1] : null,
        toolNames: toolNames.slice(),
        actionNames: actionNames.slice(),
        taskIds: taskIds.slice(),
        successValues: successValues.slice(),
        lastSuccess: successValues.length > 0 ? successValues[successValues.length - 1] : null,
        completionTexts: completionTexts.slice(),
        lastCompletionText: completionTexts.length > 0 ? completionTexts[completionTexts.length - 1] : null,
      };
    },
    resetDiagnostics: resetDiagnostics,
  };

  window.PageAgentLabMockModel = window.PageAgentMockModel;
})();
