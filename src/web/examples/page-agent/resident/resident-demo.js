(function () {
  "use strict";

  var chatMessages = document.getElementById("chat-messages");
  var chatInput = document.getElementById("chat-input");
  var chatSend = document.getElementById("chat-send");
  var chatCancel = document.getElementById("chat-cancel");
  var statusEl = document.getElementById("chat-status");

  var agent = null;
  var isRunning = false;
  var timeoutId = null;
  var TIMEOUT_MS = 60000; // 60-second bounded timeout

  var SUGGESTIONS = [
    "공동주택과 연락처 찾아줘",
    "대형폐기물 신청 메뉴 찾아줘",
    "여권 발급 절차를 찾아줘",
    "민원 작성 화면을 열어줘",
    "구청장에게 제안할 글 작성을 도와줘",
  ];

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

  function stopAgent() {
    if (timeoutId) { clearTimeout(timeoutId); timeoutId = null; }
    if (agent && isRunning) {
      agent.stop();
    }
  }

  var DISABLED_DONE_TEXT = "서버 모델이 비활성 상태입니다.";

  function initAgent() {
    if (typeof window.PageAgent !== "function") {
      addErrorMessage("PageAgent runtime을 불러올 수 없습니다.");
      return;
    }

    var params = new URLSearchParams(window.location.search);
    var isServer = params.get("page_agent_adapter") === "server";

    if (isServer) {
      var serverBaseUrl = new URL("/api/page-agent/v1", window.location.href);
      serverBaseUrl.pathname = serverBaseUrl.pathname.replace(/\/$/, "");

      var badgeMode = document.getElementById("badge-mode");
      if (badgeMode) badgeMode.textContent = "☁️ 서버 모델";
      var badgeSub = document.querySelector(".chat-header__sub");
      if (badgeSub) badgeSub.textContent = "주민용 비교 데모 · 서버 모델 어댑터";

      function serverCustomFetch(input, init) {
        var raw = input instanceof Request ? input.url : String(input);
        var url = new URL(raw, window.location.href);
        var expectedPath = serverBaseUrl.pathname + "/chat/completions";
        if (url.origin !== window.location.origin) {
          return Promise.reject(new Error("Blocked external Page Agent request: " + url.href));
        }
        if (url.pathname !== expectedPath) {
          return Promise.reject(new Error("Blocked unexpected request: " + url.pathname));
        }
        var mergedInit = init || {};
        var headers;
        if (mergedInit.headers instanceof Headers) {
          headers = new Headers(mergedInit.headers);
        } else if (Array.isArray(mergedInit.headers)) {
          headers = new Headers(mergedInit.headers);
        } else if (mergedInit.headers && typeof mergedInit.headers === 'object') {
          headers = new Headers(Object.entries(mergedInit.headers));
        } else {
          headers = new Headers();
        }
        var toDelete = [];
        headers.forEach(function (value, key) {
          if (key.toLowerCase() === 'authorization') toDelete.push(key);
        });
        toDelete.forEach(function (key) { headers.delete(key); });
        return fetch(input, Object.assign({}, mergedInit, { headers: headers, credentials: 'same-origin' }));
      }

      agent = new window.PageAgent({
        model: "resident-server-adapter",
        baseURL: serverBaseUrl.href,
        apiKey: "same-origin-server-adapter",
        customFetch: serverCustomFetch,
        language: "ko",
        enableMask: false,
        includeAttributes: ["data-action-target"],
        maxSteps: 20,
      });
    } else {
      var mockBaseUrl = new URL("./mock-llm/v1", window.location.href);
      mockBaseUrl.pathname = mockBaseUrl.pathname.replace(/\/$/, "");

      function localCustomFetch(input, init) {
        var raw = input instanceof Request ? input.url : String(input);
        var url = new URL(raw, window.location.href);
        var expectedPath = mockBaseUrl.pathname + "/chat/completions";
        if (url.origin !== window.location.origin) {
          return Promise.reject(new Error("Blocked external Page Agent request: " + url.href));
        }
        if (url.pathname !== expectedPath) {
          return Promise.reject(new Error("Blocked unexpected request: " + url.pathname));
        }
        return window.PageAgentMockModel.respond(input, init);
      }

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
    }

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
        setRunning(false);
        if (isServer && result && result.text === DISABLED_DONE_TEXT) {
          var badgeMode = document.getElementById("badge-mode");
          if (badgeMode) badgeMode.textContent = "☁️ 서버 모델 비활성";
        }
      } else if (status === "error" || status === "stopped") {
        removeThinkingMessage();
        if (status === "stopped") {
          setStatus("취소됨", "");
          addMessage("작업이 취소되었습니다.", "agent");
        } else {
          setStatus("오류", "chat-header__status--error");
          addErrorMessage("작업 중 오류가 발생했습니다.");
        }
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

    setStatus("준비", "");
  }

  function sendMessage(text) {
    if (!text.trim() || isRunning) return;
    addMessage(text, "user");
    if (agent) {
      // Bounded timeout
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(function () {
        if (isRunning) {
          addErrorMessage("60초가 초과되어 작업이 중단되었습니다.");
          stopAgent();
        }
      }, TIMEOUT_MS);
      agent.execute(text);
    } else {
      addErrorMessage("PageAgent가 아직 초기화되지 않았습니다.");
    }
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
      btn.addEventListener("click", function () { sendMessage(s); });
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
