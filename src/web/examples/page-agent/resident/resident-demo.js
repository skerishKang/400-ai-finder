(function () {
  "use strict";

  var chatMessages = document.getElementById("chat-messages");
  var chatInput = document.getElementById("chat-input");
  var chatSend = document.getElementById("chat-send");
  var chatCancel = document.getElementById("chat-cancel");
  var statusEl = document.getElementById("chat-status");
  var modeBadge = document.getElementById("plan-mode-badge");
  var planStatusEl = document.getElementById("page-agent-plan-status");

  var mobileSwitch = document.getElementById("page-agent-mobile-switch");
  var tabConversation = document.getElementById("page-agent-tab-conversation");
  var tabGuidance = document.getElementById("page-agent-tab-guidance");
  var mobileCancel = document.getElementById("page-agent-mobile-cancel");
  var guidanceSurface = document.getElementById("page-agent-guidance-surface");
  var conversationSurface = document.getElementById("page-agent-conversation-surface");

  var agent = null;
  var isRunning = false;
  var timeoutId = null;
  var TIMEOUT_MS = 60000;
  var _planFetchAdapter = null;
  var _sendToken = 0;
  var _planState = "idle";
  var _userCancelled = false;
  var _activeRequestId = null;

  /** Independent of plan mode/state: "conversation" | "guidance" */
  var _mobileSurface = "conversation";
  var _isMobileViewport = false;
  var MOBILE_MQ = "(max-width: 768px)";

  var PLAN_STATES = {
    idle: "무엇을 도와드릴까요?",
    planning: "요청을 이해하고 안전한 안내 단계를 준비하고 있습니다.",
    executing: "북구청 화면에서 안내 경로를 확인하고 있습니다.",
    result: "안내 화면에 도착했습니다. 최종 제출은 주민이 직접 확인해야 합니다.",
    unsupported: "현재 준비된 안내 범위에 없는 요청입니다.",
    disabled: "현재 서버 안내 모드는 사용할 수 없습니다. 기본 오프라인 안내를 이용해 주세요.",
    error: "안내 단계를 준비하지 못했습니다. 다시 시도해 주세요.",
    cancelled: "안내 진행을 취소했습니다.",
  };

  var SUGGESTIONS = [
    "공동주택과 연락처 찾아줘",
    "대형폐기물 신청 메뉴 찾아줘",
    "여권 발급 절차를 찾아줘",
    "민원 작성 화면을 열어줘",
    "구청장에게 제안할 글 작성을 도와줘",
  ];

  function getPlanMode() {
    if (
      window.PageAgentServerPlanClient &&
      typeof window.PageAgentServerPlanClient.getPlanMode === "function"
    ) {
      return window.PageAgentServerPlanClient.getPlanMode();
    }
    return "local";
  }

  function serverPlanEnabled() {
    return getPlanMode() === "server";
  }

  function setPlanModeAttr(mode) {
    var value = mode === "server" ? "server" : "local";
    document.documentElement.setAttribute("data-page-agent-plan-mode", value);
    document.body.setAttribute("data-page-agent-plan-mode", value);
  }

  /**
   * Single resident-visible status region. Does not append chat history.
   * Same state+message is not rewritten (avoids noisy live-region churn).
   */
  function setPlanState(state, options) {
    options = options || {};
    var next = PLAN_STATES[state] ? state : "idle";
    var message = options.message || PLAN_STATES[next] || PLAN_STATES.idle;

    if (_planState === next && planStatusEl && planStatusEl.textContent === message) {
      return;
    }

    _planState = next;
    document.documentElement.setAttribute("data-page-agent-plan-state", next);
    document.body.setAttribute("data-page-agent-plan-state", next);

    if (planStatusEl) {
      planStatusEl.setAttribute("data-state", next);
      planStatusEl.textContent = message;
    }
  }

  function getPlanState() {
    return _planState;
  }

  function getActiveRequestId() {
    if (
      window.PageAgentServerPlanClient &&
      typeof window.PageAgentServerPlanClient.getActiveRequestId === "function"
    ) {
      return window.PageAgentServerPlanClient.getActiveRequestId() || _activeRequestId;
    }
    return _activeRequestId;
  }

  function getMobileSurface() {
    return _mobileSurface;
  }

  /**
   * Mobile surface only. Never touches plan mode/state, agent run, route,
   * history, or focus. Accepts only "conversation" | "guidance".
   */
  function setMobileSurface(surface) {
    if (surface !== "conversation" && surface !== "guidance") {
      return;
    }
    _mobileSurface = surface;
    document.documentElement.setAttribute("data-page-agent-mobile-surface", surface);
    document.body.setAttribute("data-page-agent-mobile-surface", surface);
    applyMobileSurfacePresentation();
  }

  function revealSurface(el) {
    if (!el) return;
    el.hidden = false;
    el.inert = false;
    el.removeAttribute("aria-hidden");
  }

  function concealSurface(el) {
    if (!el) return;
    el.hidden = true;
    el.inert = true;
    el.setAttribute("aria-hidden", "true");
  }

  function updateMobileCancelVisibility() {
    if (!mobileCancel) return;
    if (_isMobileViewport && isRunning) {
      mobileCancel.hidden = false;
    } else {
      mobileCancel.hidden = true;
    }
  }

  /**
   * Owns hidden/inert/aria presentation for mobile vs desktop.
   * Does not mutate plan state, agent, messages, or call .focus().
   */
  function applyMobileSurfacePresentation() {
    if (mobileSwitch) {
      mobileSwitch.hidden = !_isMobileViewport;
    }

    if (tabConversation) {
      tabConversation.setAttribute(
        "aria-pressed",
        _mobileSurface === "conversation" ? "true" : "false"
      );
    }
    if (tabGuidance) {
      tabGuidance.setAttribute(
        "aria-pressed",
        _mobileSurface === "guidance" ? "true" : "false"
      );
    }

    if (_isMobileViewport) {
      if (_mobileSurface === "conversation") {
        revealSurface(conversationSurface);
        concealSurface(guidanceSurface);
      } else {
        revealSurface(guidanceSurface);
        concealSurface(conversationSurface);
      }
    } else {
      // Desktop: both surfaces always visible and interactive.
      revealSurface(conversationSurface);
      revealSurface(guidanceSurface);
    }

    updateMobileCancelVisibility();
  }

  function syncViewportMode() {
    var mq = window.matchMedia(MOBILE_MQ);
    _isMobileViewport = !!mq.matches;
    applyMobileSurfacePresentation();
  }

  function initMobileSurfaces() {
    // Materialize initial surface attribute (conversation).
    document.documentElement.setAttribute("data-page-agent-mobile-surface", _mobileSurface);
    document.body.setAttribute("data-page-agent-mobile-surface", _mobileSurface);

    if (tabConversation) {
      tabConversation.addEventListener("click", function () {
        setMobileSurface("conversation");
      });
    }
    if (tabGuidance) {
      tabGuidance.addEventListener("click", function () {
        setMobileSurface("guidance");
      });
    }
    // Same cancel owner as #chat-cancel — no separate cancellation path.
    if (mobileCancel) {
      mobileCancel.addEventListener("click", onCancel);
    }

    var mq = window.matchMedia(MOBILE_MQ);
    _isMobileViewport = !!mq.matches;
    applyMobileSurfacePresentation();

    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", function () {
        syncViewportMode();
      });
    } else if (typeof mq.addListener === "function") {
      mq.addListener(function () {
        syncViewportMode();
      });
    }
  }

  /**
   * Map structured plan-client errors to resident plan states.
   * Returns null when the result must not update UI (stale token).
   */
  function classifyPlanError(result) {
    if (!result) return { state: "error", chat: false };
    if (result.stale || result.detail === "stale_token") return null;

    var code = String(result.error || "");
    var detail = String(result.detail || "");

    if (
      code === "page_agent_cancelled" ||
      code === "AbortError" ||
      detail === "aborted" ||
      detail === "stale_token"
    ) {
      return { state: "cancelled", chat: false };
    }

    if (
      code === "page_agent_model_disabled" ||
      code === "page_agent_provider_not_configured" ||
      code === "page_agent_provider_unsupported" ||
      code === "page_agent_server_mode_disabled"
    ) {
      return { state: "disabled", chat: true };
    }

    if (code === "page_agent_unsupported_task") {
      return { state: "unsupported", chat: true };
    }

    if (
      code === "page_agent_timeout" ||
      code === "provider_error" ||
      code === "invalid_plan" ||
      code === "invalid_request" ||
      code === "page_agent_malformed_response" ||
      code === "page_agent_http_failure" ||
      code === "page_agent_network_error" ||
      code === "page_agent_plan_failed" ||
      code === "page_agent_origin_blocked" ||
      detail.indexOf("http_") === 0
    ) {
      return { state: "error", chat: true };
    }

    return { state: "error", chat: true };
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
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.className = "chat-header__status" + (className ? " " + className : "");
  }

  function setRunning(running) {
    isRunning = running;
    chatInput.disabled = running;
    chatSend.disabled = running;
    if (chatCancel) chatCancel.style.display = running ? "inline-flex" : "none";
    updateMobileCancelVisibility();
    if (running) {
      chatInput.placeholder = "안내를 진행하는 중입니다...";
    } else {
      chatInput.placeholder = "무엇을 도와드릴까요?";
      // Desktop: preserve existing post-run focus restore.
      // Mobile: never auto-focus composer (avoids soft keyboard).
      if (!_isMobileViewport && chatInput && !chatInput.disabled) {
        chatInput.focus();
      }
    }
  }

  function addThinkingMessage() {
    if (document.getElementById("thinking-indicator")) return;
    var div = document.createElement("div");
    div.className = "chat-msg chat-msg--status";
    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--status";
    bubble.id = "thinking-indicator";
    bubble.innerHTML = '<span class="spinner"></span>안내 경로를 확인하고 있습니다...';
    div.appendChild(bubble);
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function removeThinkingMessage() {
    var el = document.getElementById("thinking-indicator");
    if (el && el.parentElement) el.parentElement.remove();
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
        label = "화면 요소 확인";
        if (detail && typeof detail.index === "number") label += " (단계 " + (detail.index + 1) + ")";
        break;
      case "scroll":
        icon = "📜";
        label = "화면 이동";
        break;
      default:
        icon = "⚙️";
        label = "안내 동작";
    }
    bubble.textContent = icon + " " + label;
    div.appendChild(bubble);
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function clearActiveWork() {
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
    _planFetchAdapter = null;
    _activeRequestId = null;
    if (
      window.PageAgentServerPlanClient &&
      typeof window.PageAgentServerPlanClient.cancel === "function"
    ) {
      window.PageAgentServerPlanClient.cancel();
    }
  }

  function stopAgent(options) {
    options = options || {};
    _userCancelled = true;
    _sendToken += 1;
    clearActiveWork();
    if (agent && isRunning) {
      try {
        agent.stop();
      } catch (_) {}
    }
    removeThinkingMessage();
    setRunning(false);
    if (options.silent) return;
    setStatus("취소됨", "");
    setPlanState("cancelled");
    // Show cancelled status in conversation; no auto composer focus.
    setMobileSurface("conversation");
  }

  function localCustomFetch(input, init) {
    // Server plan armed → drive real Page Agent tool loop from plan steps.
    if (_planFetchAdapter && typeof _planFetchAdapter.respond === "function") {
      var raw = input instanceof Request ? input.url : String(input);
      var url = new URL(raw, window.location.href);
      if (url.origin !== window.location.origin) {
        return Promise.reject(new Error("Blocked external Page Agent request"));
      }
      return _planFetchAdapter.respond(input, init);
    }

    // Default offline deterministic mock (PageAgentMockModel).
    var mockBaseUrl = new URL("./mock-llm/v1", window.location.href);
    mockBaseUrl.pathname = mockBaseUrl.pathname.replace(/\/$/, "");
    var raw2 = input instanceof Request ? input.url : String(input);
    var url2 = new URL(raw2, window.location.href);
    var expectedPath = mockBaseUrl.pathname + "/chat/completions";
    if (url2.origin !== window.location.origin) {
      return Promise.reject(new Error("Blocked external Page Agent request"));
    }
    if (url2.pathname !== expectedPath) {
      return Promise.reject(new Error("Blocked unexpected request"));
    }
    return window.PageAgentMockModel.respond(input, init);
  }

  function initAgent() {
    if (typeof window.PageAgent !== "function") {
      addErrorMessage("안내 실행 환경을 불러올 수 없습니다.");
      setPlanState("error");
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
        setPlanState("executing");
        addThinkingMessage();
      } else if (status === "completed") {
        removeThinkingMessage();
        var result = agent.lastResult;
        if (result && result.success) {
          setStatus("완료", "chat-header__status--done");
          addMessage(result.text || "안내를 마쳤습니다.", "agent");
          setPlanState("result");
        } else {
          setStatus("완료", "");
          addMessage(result ? result.text : "안내를 완료하지 못했습니다.", "agent");
          // Unsupported-style completion from local mock still uses agent text.
          if (result && result.success === false) {
            setPlanState("unsupported");
          } else {
            setPlanState("result");
          }
        }
        _planFetchAdapter = null;
        _activeRequestId = null;
        setRunning(false);
        _userCancelled = false;
        // Result keeps guidance surface; resident may manually switch to 대화.
      } else if (status === "error" || status === "stopped") {
        removeThinkingMessage();
        _planFetchAdapter = null;
        _activeRequestId = null;
        setRunning(false);
        if (status === "stopped") {
          setStatus("취소됨", "");
          // User cancel already set cancelled; agent stop after cancel should not
          // flip success/history. If stop arrived without user cancel, mark cancelled.
          if (_userCancelled || _planState === "cancelled") {
            setPlanState("cancelled");
          } else {
            setPlanState("cancelled");
          }
          setMobileSurface("conversation");
        } else {
          setStatus("오류", "chat-header__status--error");
          if (!_userCancelled) {
            addErrorMessage("안내 진행 중 오류가 발생했습니다.");
            setPlanState("error");
          }
          // Keep conversation so resident can read the error copy.
          setMobileSurface("conversation");
        }
        _userCancelled = false;
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
          setPlanState("executing");
        }
      }
    });

    var mode = getPlanMode();
    setPlanModeAttr(mode);
    if (modeBadge) {
      modeBadge.textContent = mode === "server" ? "서버 안내" : "기본 안내";
      modeBadge.className = "badge " + (mode === "server" ? "badge--server" : "badge--offline");
    }

    setStatus("준비", "");
    setPlanState("idle");
  }

  function startAgentExecute(text) {
    if (!agent) {
      addErrorMessage("안내 실행 환경이 아직 준비되지 않았습니다.");
      setPlanState("error");
      setRunning(false);
      return;
    }
    if (timeoutId) clearTimeout(timeoutId);
    timeoutId = setTimeout(function () {
      if (isRunning) {
        addErrorMessage("안내 시간이 초과되어 중단되었습니다.");
        stopAgent({ silent: true });
        setPlanState("error");
        setStatus("오류", "chat-header__status--error");
        setMobileSurface("conversation");
      }
    }, TIMEOUT_MS);
    setPlanState("executing");
    // Local + valid-server: switch to guidance immediately before action loop.
    // No focus — avoids soft keyboard on mobile guidance.
    setMobileSurface("guidance");
    agent.execute(text);
  }

  function sendMessage(text) {
    if (!text.trim() || isRunning) return;

    // New question invalidates previous work (token + abort).
    _userCancelled = false;
    _sendToken += 1;
    var token = _sendToken;
    if (
      window.PageAgentServerPlanClient &&
      typeof window.PageAgentServerPlanClient.cancel === "function"
    ) {
      // Invalidate in-flight plan without forcing cancelled UI yet.
      window.PageAgentServerPlanClient.cancel();
    }
    _planFetchAdapter = null;
    _activeRequestId = null;

    addMessage(text, "user");

    // ── Local deterministic mock path (default) ──
    if (!serverPlanEnabled()) {
      setPlanState("executing");
      setRunning(true);
      // Guidance switch happens in startAgentExecute, just before DOM work.
      startAgentExecute(text);
      return;
    }

    // ── Explicit server plan path ──
    // Stay on conversation during planning so residents can read status.
    setRunning(true);
    setStatus("준비 중...", "chat-header__status--active");
    setPlanState("planning");
    addThinkingMessage();

    window.PageAgentServerPlanClient.requestPlan(text, { maxSteps: 10 }).then(function (result) {
      // Stale / superseded request must not overwrite active UI.
      // _sendToken is the resident UI generation; client token is separate.
      if (token !== _sendToken) return;
      if (result && (result.stale || result.detail === "stale_token")) return;

      removeThinkingMessage();
      _activeRequestId = (result && result.request_id) || null;

      if (!result || result.ok !== true) {
        var mapped = classifyPlanError(result);
        if (!mapped) {
          // Ignore stale/cancel noise for UI.
          return;
        }
        setRunning(false);
        setStatus(mapped.state === "cancelled" ? "취소됨" : "안내 중단", "chat-header__status--error");
        setPlanState(mapped.state);
        // Resident chat: only surface human status copy for terminal failures,
        // not provider/env technical names.
        if (mapped.chat && mapped.state !== "cancelled") {
          addErrorMessage(PLAN_STATES[mapped.state] || PLAN_STATES.error);
        }
        _planFetchAdapter = null;
        // disabled / unsupported / error / cancelled: keep conversation surface.
        setMobileSurface("conversation");
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
      // Never jump to final route — Page Agent executes clicks in the canvas.
      setPlanState("executing");
      // Guidance switch is inside startAgentExecute, just before action loop.
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
    setPlanModeAttr(getPlanMode());
    setPlanState("idle");
    initMobileSurfaces();

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

  // Read-only diagnostic API (no enable/provider setters, no secrets).
  // setMobileSurface accepts only conversation|guidance and never focuses.
  window.PageAgentResidentRuntime = Object.freeze({
    getPlanMode: getPlanMode,
    getPlanState: getPlanState,
    getActiveRequestId: getActiveRequestId,
    getMobileSurface: getMobileSurface,
    setMobileSurface: setMobileSurface,
    cancel: function () {
      stopAgent();
    },
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
