// ═══════════════════════════════════════════════════════════════════════════
// page-agent-lab.js — Initialization script for Page Agent lab
//
// Loads after page-agent.demo.js (IIFE bundle) and mock-model.js.
// Creates a PageAgent instance with a local deterministic mock model
// via the customFetch option. No live LLM, no external API calls.
// ═══════════════════════════════════════════════════════════════════════════

(function () {
  'use strict';

  var LAB = {
    initialized: false,
    agent: null,
    ready: false,
  };

  // ── Parse JSON body from request options ───────────────────────────────

  function parseBody(options) {
    if (!options || !options.body) return {};
    try {
      return JSON.parse(typeof options.body === 'string' ? options.body : '{}');
    } catch (e) {
      return {};
    }
  }

  // ── Build a mock Response object ───────────────────────────────────────

  function mockJsonResponse(data) {
    return Promise.resolve({
      ok: true,
      status: 200,
      headers: { 'content-type': 'application/json' },
      json: function () { return Promise.resolve(data); },
      text: function () { return Promise.resolve(JSON.stringify(data)); },
    });
  }

  // ── Initialize PageAgent with local mock ───────────────────────────────

  function init() {
    if (LAB.initialized) return;
    LAB.initialized = true;

    // Wait for PageAgent class to be available from the IIFE bundle
    function waitForReady() {
      if (typeof window.PageAgent !== 'function' || !window.PageAgentMockModel) {
        setTimeout(waitForReady, 50);
        return;
      }
      setup();
    }
    waitForReady();
  }

  function setup() {
    try {
      var mockBaseURL = window.location.origin + '/examples/page-agent/mock-llm/v1';

      var config = {
        model: 'local-mock',
        baseURL: mockBaseURL,
        apiKey: 'local-test-only',
        language: 'en-US',
        // Route all LLM requests through the deterministic mock model
        customFetch: function (url, options) {
          var urlStr = (typeof url === 'string') ? url : String(url);

          // Intercept chat completion requests to the mock endpoint
          if (urlStr.indexOf('/mock-llm/v1/chat/completions') !== -1) {
            var payload = parseBody(options);
            var result = window.PageAgentMockModel.handleCompletion(urlStr, payload);
            if (!result) {
              return Promise.reject(new Error('Mock model returned no response'));
            }
            return mockJsonResponse(result);
          }

          // Block known non-local hosts
          if (window.PageAgentMockModel.isBlocked(urlStr)) {
            return Promise.reject(
              new Error('Page Agent Lab: blocked request to non-local host (' + urlStr + ')')
            );
          }

          // Fall through to original fetch for local assets
          return window.fetch(url, options);
        },
      };

      LAB.agent = new window.PageAgent(config);
      LAB.ready = true;

      // Show the built-in floating Panel
      if (LAB.agent.panel && typeof LAB.agent.panel.show === 'function') {
        LAB.agent.panel.show();
      }

      console.log('[Page Agent Lab] Initialized with local deterministic mock model.');
      console.log('[Page Agent Lab] Base URL:', mockBaseURL);
      console.log('[Page Agent Lab] Supported tasks:', window.PageAgentMockModel.getSupportedTaskIds().join(', '));
    } catch (err) {
      console.error('[Page Agent Lab] Initialization failed:', err);
    }
  }

  // ── Public API ─────────────────────────────────────────────────────────

  window.PageAgentLab = {
    isReady: function () { return LAB.ready; },
    getAgent: function () { return LAB.agent; },
    getSupportedTaskIds: function () {
      return window.PageAgentMockModel ? window.PageAgentMockModel.getSupportedTaskIds() : [];
    },
  };

  // ── Start on DOMContentLoaded ──────────────────────────────────────────

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
