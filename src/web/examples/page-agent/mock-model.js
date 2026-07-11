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

  function getLastUserMessage(payload) {
    if (!payload || !payload.messages || !Array.isArray(payload.messages)) {
      return '';
    }
    var msgs = payload.messages;
    for (var i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'user') {
        return msgs[i].content || '';
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

  // ── Diagnostics for verification (no behavior change) ───────────────────

  var callCount = 0;
  var lastToolName = null;
  var lastActionName = null;

  // ── Public API ─────────────────────────────────────────────────────────

  function respond(input, init) {
    // Parse the OpenAI-compatible request body.
    // Note: page-agent-lab.js enforces same-origin via localCustomFetch,
    // so URL validation is handled by the caller.
    var body = {};
    try {
      body = JSON.parse((init && init.body) || '{}');
    } catch (e) {
      body = {};
    }

    // Read the actual macro tool name the runtime requested.
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
    // After the first action records a step, the user prompt embeds <step_1>.
    var firstStep = userMessage.indexOf('<step_1>') === -1;

    var task = findTask(userMessage);
    var action;

    if (!task && firstStep) {
      // Unknown task on first step → report unsupported
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
      // Known task, first step → execute_javascript to scroll to section
      action = {
        execute_javascript: {
          script:
            "document.getElementById('" +
            task.sectionId +
            "').scrollIntoView({block:'center'});",
        },
      };
    } else {
      // Second step (has <step_1> in history) or unknown → done
      action = {
        done: {
          text: task ? task.response : 'Task completed.',
          success: true,
        },
      };
    }

    callCount++;
    lastToolName = macroToolName;
    lastActionName = action && Object.keys(action)[0];

    return new Response(JSON.stringify(buildToolResponse(macroToolName, action)), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  window.PageAgentMockModel = {
    TASKS: TASKS,
    BLOCKED_HOSTS: BLOCKED_HOSTS,

    /** Main entry: returns an OpenAI-compatible tool-call Response. */
    respond: respond,

    /** Convenience wrapper returning the parsed response body. */
    handleCompletion: function (url, payload) {
      return respond(url, { body: JSON.stringify(payload || {}) }).then(function (r) {
        return r.json();
      });
    },

    /** Check if a URL is in the blocked list. */
    isBlocked: isBlocked,

    /** Get list of supported task IDs. */
    getSupportedTaskIds: function () {
      return TASKS.map(function (t) {
        return t.id;
      });
    },

    /** Get a task by ID. */
    getTask: function (id) {
      for (var i = 0; i < TASKS.length; i++) {
        if (TASKS[i].id === id) return TASKS[i];
      }
      return null;
    },

    /** Check if a task ID is supported. */
    isSupportedTask: function (id) {
      return !!this.getTask(id);
    },

    /** Get all task definitions (for testing). */
    getAllTasks: function () {
      return TASKS;
    },

    /** Diagnostics for verification. */
    getDiagnostics: function () {
      return {
        callCount: callCount,
        lastToolName: lastToolName,
        lastActionName: lastActionName,
      };
    },
  };

  // ── Legacy alias for page-agent-lab.js compatibility ──────────────────
  window.PageAgentLabMockModel = window.PageAgentMockModel;
})();