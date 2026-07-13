(function () {
  "use strict";

  var chatMessages = document.getElementById("chat-messages");
  var chatInput = document.getElementById("chat-input");
  var chatSend = document.getElementById("chat-send");
  var chatCancel = document.getElementById("chat-cancel");
  var statusEl = document.getElementById("chat-status");
  var modeBadge = document.getElementById("plan-mode-badge");

  var agent = null;
  var isRunning = false;
  var timeoutId = null;
  var TIMEOUT_MS = 60000; // 60-second bounded timeout
  var _planFetchAdapter = null;
  var _sendToken = 0;

  var SUGGESTIONS = [
    "공동주택과 연락처 찾아줘",
    "대형폐기물 신청 메뉴 찾아줘",
    "여권 발급 절차를 찾아줘",
    "민원 작성 화면을 열어줘",
    "구청장에게 제안할 글 작성을 도와줘",
  ];

  function serverPlanEnabled() {
    return (
      window.PageAgentServerPlanClient &&
      typeof window.PageAgentServerPlanClient.isEnabled === "function" &&
      window.PageAgentServerPlanClient.isEnabled()
    );
  }

  function addMessage(text, role) {
    var div = document.createElement("div");
    div.className = "chat-msg chat-msg--" + role;
    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--" + role;
    bubble.textContent = text;
    div.appendChild(bubble);
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function addErrorMessage(text) {
    var div = document.createElement("div");
    div.className = "chat-msg chat-msg--agent";
    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--agent chat-bubble--error";
    bubble.textContent = "⚠ " + text;
    div.appendChild(bubble);
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function setStatus(text, className) {
    statusEl.textContent = text;
    statusEl.className = "chat-header__status" + (className ? " " + className : "");
  }

  function setRunning(running) {
    isRunning = running;
    chatInput.disabled = running;
    chatSend.disabled = running;
    if (chatCancel) chatCancel.style.display = running ? "inline-flex" : "none";
    if (running) {
      chatInput.placeholder = "Page Agent가 작업 중...";
    } else {
      chatInput.placeholder = "무엇을 도와드릴까요?";
      if (!chatInput.disabled) chatInput.focus();
    }
  }

  function addThinkingMessage() {
    var div = document.createElement("div");
    div.className = "chat-msg chat-msg--status";
    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--status";
    bubble.id = "thinking-indicator";
    bubble.innerHTML = '<span class="spinner"></span>Page Agent가 작업 중입니다...';
    div.appendChild(bubble);
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function removeThinkingMessage() {
    var el = document.getElementById("thinking-indicator");
    if (el) el.parentElement.remove();
  }

  function addActionRecord(actionName, detail) {
    var div = document.createElement("div");
    div.className = "chat-msg chat-msg--status chat-msg--action";
    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--action";
    var icon = "";
    var label = "";
    switch (actionName) {
      case "click_element_by_index":
        icon = "🖱️";
        label = "요소 클릭";
        if (detail && typeof detail.index === "number") label += " (index " + detail.index + ")";
        break;
      case "scroll":
        icon = "📜";
        label = "스크롤";
        break;
      default:
        icon = "⚙️";
        label = actionName;
    }
    bubble.textContent = icon + " " + label;
    div.appendChild(bubble);
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function mapPlanError(errCode) {
    switch (errCode) {
      case "page_agent_model_disabled":
        return "서버 계획 어댑터가 비활성 상태입니다. 오프라인 mock 모드를 사용하거나 서버 설정을 확인하세요.";
      case "page_agent_provider_not_configured":
        return "서버 provider가 구성되지 않았습니다.";
      case "page_agent_provider_unsupported":
        return "지원하지 않는 서버 provider입니다.";
      case "page_agent_unsupported_task":
        return "지원하지 않는 질문입니다. 안내된 다섯 가지 업무 중 하나를 선택해 주세요.";
      case "page_agent_timeout":
        return "서버 계획 요청이 시간 초과되었습니다.";
      case "page_agent_cancelled":
        return "요청이 취소되었습니다.";
      case "page_agent_malformed_response":
        return "서버 응답 형식이 올바르지 않습니다.";
      case "invalid_request":
      case "invalid_plan":
        return "서버 계획 검증에 실패했습니다.";
      default:
        return "서버 계획 요청에 실패했습니다" + (errCode ? " (" + errCode + ")" : "") + ".";
    }
  }

  function stopAgent() {
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
    _sendToken += 1;
    if (window.PageAgentServerPlanClient && typeof window.PageAgentServerPlanClient.cancel === "function") {
      window.PageAgentServerPlanClient.cancel();
    }
    _planFetchAdapter = null;
    if (agent && isRunning) {
      agent.stop();
    }
  }

  function localCustomFetch(input, init) {
    // When a server plan is armed, drive the real Page Agent tool loop from it.
    if (_planFetchAdapter && typeof _planFetchAdapter.respond === "function") {
      var raw = input instanceof Request ? input.url : String(input);
      var url = new URL(raw, window.location.href);
      if (url.origin !== window.location.origin) {
        return Promise.reject(new Error("Blocked external Page Agent request: " + url.href));
      }
      return _planFetchAdapter.respond(input, init);
    }

    // Default offline deterministic mock (unchanged owner: PageAgentMockModel).
    var mockBaseUrl = new URL("./mock-llm/v1", window.location.href);
    mockBaseUrl.pathname = mockBaseUrl.pathname.replace(/\/$/, "");
    var raw2 = input instanceof Request ? input.url : String(input);
    var url2 = new URL(raw2, window.location.href);
    var expectedPath = mockBaseUrl.pathname + "/chat/completions";
    if (url2.origin !== window.location.origin) {
      return Promise.reject(new Error("Blocked external Page Agent request: " + url2.href));
    }
    if (url2.pathname !== expectedPath) {
      return Promise.reject(new Error("Blocked unexpected request: " + url2.pathname));
    }
    return window.PageAgentMockModel.respond(input, init);
  }

  function initAgent() {
    if (typeof window.PageAgent !== "function") {
      addErrorMessage("PageAgent runtime을 불러올 수 없습니다.");
      return;
    }

    var mockBaseUrl = new URL("./mock-llm/v1", window.location.href);
    mockBaseUrl.pathname = mockBaseUrl.pathname.replace(/\/$/, "");

    agent = new window.PageAgent({
      model: "resident-mock-local",
      baseURL: mockBaseUrl.href,
      apiKey: "local-resident-demo",
      customFetch: localCustomFetch,
      language: "ko",
      enableMask: false,
      includeAttributes: ["data-action-target"],
      maxSteps: 20,
    });

    agent.panel.hide();

    agent.addEventListener("statuschange", function () {
      var status = agent.status;
      if (status === "running") {
        setStatus("실행 중...", "chat-header__status--active");
        setRunning(true);
        addThinkingMessage();
      } else if (status === "completed") {
        removeThinkingMessage();
        var result = agent.lastResult;
        if (result && result.success) {
          setStatus("완료", "chat-header__status--done");
          addMessage(result.text || "작업을 완료했습니다.", "agent");
        } else {
          setStatus("완료 (일부 실패)", "");
          addMessage(result ? result.text : "작업을 완료하지 못했습니다.", "agent");
        }
        _planFetchAdapter = null;
        setRunning(false);
      } else if (status === "error" || status === "stopped") {
        removeThinkingMessage();
        if (status === "stopped") {
          setStatus("취소됨", "");
          addMessage("작업이 취소되었습니다.", "agent");
        } else {
          setStatus("오류", "chat-header__status--error");
          addErrorMessage("작업 중 오류가 발생했습니다.");
        }
        _planFetchAdapter = null;
        setRunning(false);
      }
    });

    agent.addEventListener("activity", function (e) {
      var detail = e.detail;
      if (detail && detail.type === "executing") {
        var toolName = detail.tool;
        var toolInput = detail.input;
        if (toolName === "click_element_by_index") {
          removeThinkingMessage();
          addActionRecord(toolName, toolInput);
          addThinkingMessage();
        }
      }
    });

    if (modeBadge) {
      modeBadge.textContent = serverPlanEnabled() ? "서버 plan 경계" : "오프라인/mock";
      modeBadge.className =
        "badge " + (serverPlanEnabled() ? "badge--server" : "badge--offline");
    }

    setStatus("준비", "");
  }

  function startAgentExecute(text) {
    if (!agent) {
      addErrorMessage("PageAgent가 아직 초기화되지 않았습니다.");
      return;
    }
    if (timeoutId) clearTimeout(timeoutId);
    timeoutId = setTimeout(function () {
      if (isRunning) {
        addErrorMessage("60초가 초과되어 작업이 중단되었습니다.");
        stopAgent();
      }
    }, TIMEOUT_MS);
    agent.execute(text);
  }

  function sendMessage(text) {
    if (!text.trim() || isRunning) return;
    addMessage(text, "user");

    // Default path: offline deterministic mock → Page Agent loop.
    if (!serverPlanEnabled()) {
      _planFetchAdapter = null;
      startAgentExecute(text);
      return;
    }

    // Explicit server mode: request plan from same-origin adapter, then run
    // the real Page Agent action loop with a plan-driven customFetch.
    _sendToken += 1;
    var token = _sendToken;
    setRunning(true);
    setStatus("서버 계획 요청...", "chat-header__status--active");
    addThinkingMessage();

    window.PageAgentServerPlanClient.requestPlan(text, { maxSteps: 10 }).then(function (result) {
      if (token !== _sendToken) return; // superseded / cancelled
      removeThinkingMessage();

      if (!result || result.ok !== true) {
        setRunning(false);
        setStatus("오류", "chat-header__status--error");
        addErrorMessage(mapPlanError(result && result.error));
        _planFetchAdapter = null;
        return;
      }

      var doneText = "";
      var steps = result.plan.steps || [];
      for (var i = 0; i < steps.length; i++) {
        if (steps[i].action === "read" && steps[i].value) {
          doneText = String(steps[i].value);
          break;
        }
      }

      _planFetchAdapter = window.PageAgentServerPlanClient.createPlanFetchAdapter(
        result.plan,
        doneText
      );
      // Important: do not jump to final route; Page Agent executes clicks.
      startAgentExecute(text);
    });
  }

  function onSend() {
    var text = chatInput.value.trim();
    if (text) {
      chatInput.value = "";
      sendMessage(text);
    }
  }

  function onCancel() {
    stopAgent();
  }

  function init() {
    chatSend.addEventListener("click", onSend);
    chatInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.isComposing) {
        e.preventDefault();
        onSend();
      }
    });
    if (chatCancel) chatCancel.addEventListener("click", onCancel);

    var suggestionsContainer = document.getElementById("chat-suggestions");
    SUGGESTIONS.forEach(function (s) {
      var btn = document.createElement("button");
      btn.className = "chat-suggestion";
      btn.textContent = s;
      btn.addEventListener("click", function () {
        sendMessage(s);
      });
      suggestionsContainer.appendChild(btn);
    });

    setTimeout(initAgent, 100);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
