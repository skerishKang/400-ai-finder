(function () {
  "use strict";

  if (typeof window.PageAgent !== "function") {
    throw new Error("PageAgent bundle did not expose window.PageAgent");
  }

  if (typeof window.PageAgentLabMockModel === "undefined" ||
      typeof window.PageAgentLabMockModel.respond !== "function") {
    throw new Error("page-agent lab mock model is not loaded");
  }

  var mockBaseUrl = new URL("./mock-llm/v1", window.location.href);
  mockBaseUrl.pathname = mockBaseUrl.pathname.replace(/\/$/, "");

  function localCustomFetch(input, init) {
    var raw = input instanceof Request ? input.url : String(input);
    var url = new URL(raw, window.location.href);
    var expectedPath = mockBaseUrl.pathname + "/chat/completions";

    if (url.origin !== window.location.origin) {
      return Promise.reject(
        new Error("Blocked non-local Page Agent request: " + url.href)
      );
    }

    if (url.pathname !== expectedPath) {
      return Promise.reject(
        new Error("Blocked unexpected Page Agent request: " + url.pathname)
      );
    }

    return window.PageAgentLabMockModel.respond(input, init);
  }

  var agent = new window.PageAgent({
    model: "page-agent-lab-local",
    baseURL: mockBaseUrl.href,
    apiKey: "local-test-only",
    customFetch: localCustomFetch,
    language: "en-US",
    enableMask: true,
    experimentalScriptExecutionTool: true
  });

  agent.panel.show();

  window.__PAGE_AGENT_LAB__ = Object.freeze({
    agent: agent,
    integration: "actual-page-agent",
    panel: "built-in",
    mockBaseURL: mockBaseUrl.href
  });
})();
