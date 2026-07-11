// ═══════════════════════════════════════════════════════════════════════════
// mock-model.js — Local deterministic model adapter for Page Agent lab
//
// This module provides a deterministic mock model that returns bounded
// responses for supported tasks. The actual fetch interception is handled
// by page-agent-lab.js via PageAgent's customFetch option.
//
// Task support:
//   - "Show the Quick Start section"        → scroll to #quick-start
//   - "Compare page-agent with browser-use"  → scroll to #vs-browser-use
//   - "Show the MIT license section"         → scroll to #license
//   - "Find the custom UI architecture"      → scroll to #architecture
//   - Unknown/bound tasks                    → bounded "unsupported" response
// ═══════════════════════════════════════════════════════════════════════════

(function () {
  'use strict';

  // ── Supported task definitions ──────────────────────────────────────────

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
        'I found the Quick Start section. Let me scroll to it now. The Quick Start section shows how to integrate Page Agent with a single script tag. Scrolling to #quick-start.',
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
        'I can see the comparison table between Page Agent and browser-use. Let me scroll to that section. The table compares runtime, integration, DOM access, multi-page support, and use cases. Scrolling to #vs-browser-use.',
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
        'I found the MIT License section. Page Agent is published under the MIT License. Let me scroll to #license to show the full license text.',
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
        'I found the Architecture section. The diagram shows the layered structure: Panel UI, PageAgent orchestrator, PageAgentCore agent loop, LLM Client, PageController DOM engine, and Custom UI layer. Scrolling to #architecture.',
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

  // ── Build OpenAI-compatible chat completion response ────────────────────

  function buildCompletion(content) {
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
            content: content,
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

  // ── Build bounded unsupported response ─────────────────────────────────

  function buildUnsupportedResponse() {
    return buildCompletion(
      'I can only help with the following topics on this page: Show the Quick Start section, ' +
        'Compare page-agent with browser-use, Show the MIT license section, ' +
        'and Find the custom UI architecture. Please try one of the supported tasks listed above.'
    );
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

  // ── Scroll to target section helper ────────────────────────────────────

  function scrollToSection(sectionId) {
    var el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      el.style.transition = 'background 0.3s';
      el.style.background = '#eef2ff';
      setTimeout(function () {
        el.style.background = '';
      }, 2000);
    }
  }

  // ── Public API ─────────────────────────────────────────────────────────

  window.PageAgentMockModel = {
    TASKS: TASKS,
    BLOCKED_HOSTS: BLOCKED_HOSTS,

    /** Handle an OpenAI-compatible chat completion request. */
    handleCompletion: function (url, payload) {
      var userMessage = getLastUserMessage(payload);
      var task = findTask(userMessage);

      if (task) {
        // Schedule scroll to the target section
        setTimeout(function () {
          scrollToSection(task.sectionId);
        }, 100);
        return buildCompletion(task.response);
      }

      return buildUnsupportedResponse();
    },

    /** Check if a URL is in the blocked list. */
    isBlocked: isBlocked,

    /** Get list of supported task IDs. */
    getSupportedTaskIds: function () {
      return TASKS.map(function (t) { return t.id; });
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
  };

})();
