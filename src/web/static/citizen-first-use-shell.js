/*
 * citizen-first-use-shell.js
 * Local deterministic controller for the first chat-only entry transition.
 *
 * Guarantees:
 * - no fetch/XHR/WebSocket/EventSource/sendBeacon;
 * - no browser persistence or cookie access;
 * - no provider, runner, live-site, or external-origin behavior;
 * - choreography delegation to CitizenFirstChoreography (no direct clone actions).
 */

(function () {
  "use strict";

  var STATE_ENTRY = "entry";
  var STATE_TRANSITIONING = "transitioning";
  var STATE_SPLIT = "split";
  var TRANSITION_DURATION_MS = 360;
  var DEFAULT_SUPPORTED_ACTION = "illegal_parking";
  var SUPPORTED_QUESTIONS = {
    "불법 주정차 신고는 어디서 하나요?": true,
    "공동주택 관련 문의는 어느 부서에 해야 하나요?": true,
    "침대 매트리스 버리고 싶어요": true,
    "대형폐기물은 어떻게 버리나요?": true,
    "가구 버리려면 어디서 신청해요?": true,
    "매트리스 폐기 신청은 어디서 하나요?": true,
    "이사 왔는데 전입신고는 어떻게 해요?": true,
    "전입신고 어디서 하나요?": true,
    "보건소 어디에 있어요?": true,
    "북구 보건소 진료는 어떻게 확인해요?": true,
    "보건소 위치랑 진료 안내 알려줘": true,
    "예방접종이나 진료 보려면 어디로 가야 해요?": true,
  };
  var SPLIT_FOLLOW_UP_MESSAGE =
    "북구청 안내 화면을 왼쪽에 열어두었습니다. 메뉴 이동과 세부 안내를 이어서 보여드리겠습니다. 새 질문을 시작하려면 '새 대화'를 선택해 주세요.";

  var body = document.body;
  var canvas = document.getElementById("demo-canvas");
  var chatShell = document.getElementById("chat-shell");
  var chatThread = document.getElementById("chat-thread");
  var chatForm = document.getElementById("chat-composer-form");
  var chatInput = document.getElementById("chat-composer-input");
  var chatSend = document.getElementById("chat-composer-send");
  var resetButton = document.getElementById("chat-reset");
  var chipsContainer = document.getElementById("chat-chips");
  var splitTimer = null;
  var lastSplitQuestion = null;
  var currentState = STATE_ENTRY;

  // ── MVP mode (#925 / #927) ──────────────────────────────────────
  // Enabled only with ?mvp=1. In MVP mode the shell calls the model-backed
  // /api/mvp/ask endpoint (via citizen-mvp-bridge.js) and uses the returned
  // action to drive the EXISTING local choreography. The default static flow
  // below is completely unchanged when ?mvp=1 is absent, and this file performs
  // no fetch itself (the bridge file does, and is loaded only in MVP mode).
  var _mvpRequestToken = 0;
  var _questRuntimeResult = null;

  function isMvpMode() {
    if (!window.location || !window.location.search) return false;
    try {
      return new URLSearchParams(window.location.search).get("mvp") === "1";
    } catch (_) {
      return false;
    }
  }

  function normalizeMvpAction(result) {
    if (!result || result.ok !== true) return "none";
    var a = result.action;
    if (a === "illegal_parking" || a === "housing_department" || a === "bulky_waste" || a === "move_in_report" || a === "public_health_center" || a === "none") {
      return a;
    }
    return "none";
  }

  function clearQuestRuntimeState() {
    if (!body) return;
    _questRuntimeResult = null;
    body.removeAttribute("data-quest-id");
    body.removeAttribute("data-quest-name");
    body.removeAttribute("data-quest-match-status");
    body.removeAttribute("data-quest-stop-condition");
    body.removeAttribute("data-quest-source-mode");
  }

  function applyQuestRuntimeState(result) {
    clearQuestRuntimeState();
    if (!body || !result || !result.quest) return;
    _questRuntimeResult = result;
    var quest = result.quest || {};
    var plan = result.action_plan || {};
    if (typeof quest.quest_id === "string") {
      body.setAttribute("data-quest-id", quest.quest_id);
    }
    if (typeof quest.quest_name === "string") {
      body.setAttribute("data-quest-name", quest.quest_name);
    }
    if (typeof quest.match_status === "string") {
      body.setAttribute("data-quest-match-status", quest.match_status);
    }
    if (typeof plan.stop_condition === "string") {
      body.setAttribute("data-quest-stop-condition", plan.stop_condition);
    } else if (typeof quest.stop_condition === "string") {
      body.setAttribute("data-quest-stop-condition", quest.stop_condition);
    }
    if (typeof plan.source_mode === "string") {
      body.setAttribute("data-quest-source-mode", plan.source_mode);
    } else if (typeof quest.source_mode === "string") {
      body.setAttribute("data-quest-source-mode", quest.source_mode);
    }
  }

  function asObject(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    return value;
  }

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function textValue(value) {
    if (typeof value === "string") return value.trim();
    if (typeof value === "number" || typeof value === "boolean") return String(value);
    return "";
  }

  function resultSummary(value) {
    var obj = asObject(value);
    var parts = [];
    Object.keys(obj).forEach(function (key) {
      var text = textValue(obj[key]);
      if (text) parts.push(text);
    });
    return parts.join(" / ");
  }

  function actionLabels(actions) {
    var labels = [];
    asArray(actions).forEach(function (action) {
      var label = textValue(asObject(action).label);
      if (label) labels.push(label);
    });
    return labels;
  }

  function normalizeQuestCardPayload(result) {
    var source = asObject(result || _questRuntimeResult);
    var quest = asObject(source.quest);
    var plan = asObject(source.action_plan);
    var planResult = Object.keys(asObject(plan.result)).length ? plan.result : quest.result;
    var finalWarning = asObject(plan.final_warning || quest.final_warning);
    var payload = {
      questName: textValue(quest.quest_name || plan.quest_name),
      questId: textValue(quest.quest_id || plan.quest_id),
      officialPath: asArray(plan.official_path || quest.official_path).map(textValue).filter(Boolean).join(" > "),
      actionLabels: actionLabels(plan.browser_actions),
      resultText: resultSummary(planResult),
      sourceMode: textValue(plan.source_mode || quest.source_mode),
      stopCondition: textValue(plan.stop_condition || quest.stop_condition),
      finalWarningText: textValue(finalWarning.warning_text),
    };
    if (!payload.questName && !payload.questId && !payload.officialPath && !payload.resultText) {
      return null;
    }
    return payload;
  }

  function makeQuestCardRow(label, value, modifier) {
    if (!value) return null;
    var row = document.createElement("div");
    row.className = "chat-quest-card__row" + (modifier ? " " + modifier : "");

    var labelEl = document.createElement("span");
    labelEl.textContent = label;
    row.appendChild(labelEl);

    var valueEl = document.createElement("strong");
    valueEl.textContent = value;
    row.appendChild(valueEl);
    return row;
  }

  function renderQuestProgressCard(result) {
    var payload = normalizeQuestCardPayload(result);
    if (!payload) return null;

    var card = document.createElement("div");
    card.className = "chat-quest-card";
    card.setAttribute("data-quest-card", "action_plan");
    if (payload.questId) {
      card.setAttribute("data-quest-id", payload.questId);
    }
    if (payload.sourceMode) {
      card.setAttribute("data-source-mode", payload.sourceMode);
    }

    var title = document.createElement("div");
    title.className = "chat-quest-card__title";
    title.textContent = payload.questName || "Quest";
    card.appendChild(title);

    [
      makeQuestCardRow("quest_id", payload.questId),
      makeQuestCardRow("공식 경로", payload.officialPath),
      makeQuestCardRow("결과", payload.resultText),
      makeQuestCardRow("source", payload.sourceMode),
      makeQuestCardRow("상태", payload.stopCondition),
    ].forEach(function (row) {
      if (row) card.appendChild(row);
    });

    if (payload.actionLabels.length) {
      var actions = document.createElement("div");
      actions.className = "chat-quest-card__actions";
      var actionsLabel = document.createElement("span");
      actionsLabel.className = "chat-quest-card__actions-label";
      actionsLabel.textContent = "진행 동작";
      actions.appendChild(actionsLabel);

      var list = document.createElement("ol");
      list.className = "chat-quest-card__action-list";
      payload.actionLabels.forEach(function (label) {
        var item = document.createElement("li");
        item.className = "chat-quest-card__action";
        item.textContent = label;
        list.appendChild(item);
      });
      actions.appendChild(list);
      card.appendChild(actions);
    }

    var warningRow = makeQuestCardRow("주의", payload.finalWarningText, "chat-quest-card__row--warning");
    if (warningRow) card.appendChild(warningRow);

    return card;
  }

  function appendQuestProgressCard(container, result) {
    if (!container || typeof container.appendChild !== "function") return false;
    var card = renderQuestProgressCard(result);
    if (!card) return false;
    container.appendChild(card);
    return true;
  }

  function resolveMvpActionForQuestion(question, result, hasUsableMvpResult) {
    if (!hasUsableMvpResult) return "none";
    var action = normalizeMvpAction(result);
    if (action !== "none") return action;
    if (isSupportedQuestion(question)) return DEFAULT_SUPPORTED_ACTION;
    return "none";
  }

  function _withMvpBridge(onReady) {
    if (window.CitizenMvpBridge && typeof window.CitizenMvpBridge.ask === "function") {
      onReady(window.CitizenMvpBridge);
      return;
    }
    var existing = document.querySelector('script[data-mvp-bridge="1"]');
    if (!existing) {
      var s = document.createElement("script");
      s.src = "/static/citizen-mvp-bridge.js";
      s.setAttribute("data-mvp-bridge", "1");
      s.onload = function () { onReady(window.CitizenMvpBridge); };
      s.onerror = function () { onReady(null); };
      document.head.appendChild(s);
    } else {
      var tries = 0;
      var iv = window.setInterval(function () {
        tries++;
        if (window.CitizenMvpBridge && typeof window.CitizenMvpBridge.ask === "function") {
          window.clearInterval(iv);
          onReady(window.CitizenMvpBridge);
        } else if (tries > 20) {
          window.clearInterval(iv);
          onReady(null);
        }
      }, 50);
    }
  }

  function normalizeQuestion(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function isSupportedQuestion(value) {
    return Boolean(SUPPORTED_QUESTIONS[normalizeQuestion(value)]);
  }

  function prefersReducedMotion() {
    return Boolean(
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function isLegacyJourneyLoad() {
    if (!window.location || !window.location.search) {
      return false;
    }
    var params = new URLSearchParams(window.location.search);
    return params.getAll("journey").length === 1;
  }

  function setCanvasAvailability(isAvailable) {
    if (!canvas) {
      return;
    }
    if (isAvailable) {
      canvas.removeAttribute("inert");
      canvas.setAttribute("aria-hidden", "false");
    } else {
      canvas.setAttribute("inert", "");
      canvas.setAttribute("aria-hidden", "true");
    }
  }

  function setComposerDisabled(isDisabled) {
    if (chatInput) {
      chatInput.disabled = isDisabled;
    }
    if (chatSend) {
      chatSend.disabled = isDisabled;
    }
    if (chatShell) {
      chatShell.setAttribute("data-chat-busy", isDisabled ? "true" : "false");
      chatShell.setAttribute("aria-busy", isDisabled ? "true" : "false");
    }
  }

  function setState(nextState) {
    currentState = nextState;
    body.setAttribute("data-first-use-state", nextState);

    if (nextState === STATE_ENTRY) {
      setCanvasAvailability(false);
      setComposerDisabled(false);
      if (resetButton) {
        resetButton.hidden = true;
      }
      if (chipsContainer) {
        chipsContainer.hidden = false;
      }
      return;
    }

    if (nextState === STATE_TRANSITIONING) {
      setCanvasAvailability(false);
      setComposerDisabled(true);
      if (resetButton) {
        resetButton.hidden = true;
      }
      if (chipsContainer) {
        chipsContainer.hidden = true;
      }
      return;
    }

    setCanvasAvailability(true);
    setComposerDisabled(false);
    if (resetButton) {
      resetButton.hidden = false;
    }
    if (chipsContainer) {
      chipsContainer.hidden = true;
    }
  }

  function scrollChatToLatest() {
    if (chatThread) {
      chatThread.scrollTop = chatThread.scrollHeight;
    }
  }

  function appendChatMessage(role, text) {
    if (!chatThread) {
      return;
    }

    var message = document.createElement("div");
    message.className = "chat-msg chat-msg--" + role;

    if (role === "ai") {
      var avatar = document.createElement("div");
      avatar.className = "chat-avatar";
      avatar.setAttribute("aria-label", "AI");
      avatar.textContent = "A";
      message.appendChild(avatar);
    }

    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--" + role;
    bubble.textContent = text;
    message.appendChild(bubble);
    chatThread.appendChild(message);
    scrollChatToLatest();
  }

  function renderEntryConversation() {
    if (!chatThread) {
      return;
    }
    chatThread.innerHTML = "";
    appendChatMessage(
      "ai",
      "안녕하세요. 북구청 민원 안내 AI입니다. 궁금한 민원을 물어보시면 관련 화면을 함께 열어 경로를 안내해 드립니다."
    );
  }

  function _questDisplayName(question) {
    if (!question) return "이 안내";
    if (question.indexOf("불법 주정차") !== -1) return "불법 주정차 신고";
    if (question.indexOf("공동주택") !== -1) return "공동주택 부서 문의";
    if (question.indexOf("침대") !== -1 || question.indexOf("매트리스") !== -1) return "대형폐기물 배출";
    if (question.indexOf("대형폐기물") !== -1 || question.indexOf("가구") !== -1) return "대형폐기물 배출";
    if (question.indexOf("전입신고") !== -1 || question.indexOf("이사") !== -1) return "전입신고";
    if (question.indexOf("보건소") !== -1 || question.indexOf("진료") !== -1 || question.indexOf("예방접종") !== -1) return "보건소 위치·진료 안내";
    return "이 안내";
  }

  function startChoreography(question) {
    if (window.CitizenFirstChoreography && question) {
      window.CitizenFirstChoreography.start(question);
    }
    if (chatInput) {
      chatInput.focus();
    }
  }

  function showConfirmRun(question) {
    var displayName = _questDisplayName(question);
    var msgDiv = document.createElement("div");
    msgDiv.className = "chat-msg chat-msg--ai chat-msg--confirm-run";
    msgDiv.setAttribute("data-msg-type", "confirm-run");

    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--ai";

    var text = document.createElement("p");
    text.style.margin = "0 0 10px 0";
    text.textContent = displayName + "에 대해 안내해 드릴까요?";
    bubble.appendChild(text);

    var btnRow = document.createElement("div");
    btnRow.style.display = "flex";
    btnRow.style.gap = "8px";

    var yesBtn = document.createElement("button");
    yesBtn.type = "button";
    yesBtn.textContent = "예, 안내해 주세요";
    yesBtn.style.cssText = "padding:8px 16px;border:0;border-radius:18px;background:#ef6a4c;color:#fff;font:inherit;font-size:0.85rem;font-weight:600;cursor:pointer;";
    yesBtn.addEventListener("click", function () {
      msgDiv.removeAttribute("data-msg-type");
      var btns = bubble.querySelectorAll("button");
      for (var i = 0; i < btns.length; i++) btns[i].disabled = true;
      startChoreography(question);
    });

    var noBtn = document.createElement("button");
    noBtn.type = "button";
    noBtn.textContent = "아니요";
    noBtn.style.cssText = "padding:8px 16px;border:1px solid #d0d0d5;border-radius:18px;background:#fff;color:#0d0d0f;font:inherit;font-size:0.85rem;cursor:pointer;";
    noBtn.addEventListener("click", function () {
      msgDiv.removeAttribute("data-msg-type");
      var btns = bubble.querySelectorAll("button");
      for (var i = 0; i < btns.length; i++) btns[i].disabled = true;
      if (chatInput) chatInput.focus();
    });

    btnRow.appendChild(yesBtn);
    btnRow.appendChild(noBtn);
    bubble.appendChild(btnRow);

    var avatar = document.createElement("div");
    avatar.className = "chat-avatar";
    avatar.setAttribute("aria-label", "AI");
    avatar.textContent = "A";
    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bubble);

    chatThread.appendChild(msgDiv);
    chatThread.scrollTop = chatThread.scrollHeight;
  }

  function completeSplit() {
    splitTimer = null;
    setState(STATE_SPLIT);
    appendChatMessage(
      "ai",
      "질문을 확인했습니다. 왼쪽에 북구청 안내 화면을 열었습니다."
    );
    if (lastSplitQuestion) {
      showConfirmRun(lastSplitQuestion);
    }
    lastSplitQuestion = null;
  }

  function beginSupportedTransition(question) {
    lastSplitQuestion = question;
    appendChatMessage("user", question);
    if (chatInput) {
      chatInput.value = "";
    }

    setState(STATE_TRANSITIONING);

    if (prefersReducedMotion()) {
      completeSplit();
      return;
    }

    splitTimer = window.setTimeout(completeSplit, TRANSITION_DURATION_MS);
  }

  function handleSubmission(event) {
    if (event) {
      event.preventDefault();
    }

    if (currentState === STATE_TRANSITIONING || !chatInput) {
      return;
    }

    var question = normalizeQuestion(chatInput.value);
    if (!question) {
      chatInput.focus();
      return;
    }

    if (isMvpMode()) {
      handleMvpSubmission(question);
      return;
    }

    if (currentState === STATE_SPLIT) {
      appendChatMessage("user", question);
      chatInput.value = "";
      appendChatMessage("ai", SPLIT_FOLLOW_UP_MESSAGE);
      chatInput.focus();
      return;
    }

    if (isSupportedQuestion(question)) {
      beginSupportedTransition(question);
      return;
    }

    appendChatMessage("user", question);
    chatInput.value = "";
    appendChatMessage(
      "ai",
"현재 첫 화면에서는 불법 주정차 신고, 공동주택 문의, 대형폐기물 처리, 전입신고, 보건소 안내를 준비했습니다. 예시 질문으로 다시 입력해 주세요."
    );
    chatInput.focus();
  }

  // ── MVP submission (#925 / #927) ───────────────────────────────

  function handleMvpSubmission(question) {
    clearQuestRuntimeState();
    // 1. echo user message
    appendChatMessage("user", question);
    if (chatInput) chatInput.value = "";
    // 2. lock composer against duplicate submission
    setComposerDisabled(true);

    var token = ++_mvpRequestToken;

    _withMvpBridge(function (bridge) {
      if (token !== _mvpRequestToken) return; // superseded by a newer submit/reset
      if (!bridge || typeof bridge.ask !== "function") {
        setComposerDisabled(false);
        appendChatMessage("ai", "현재 AI 안내를 연결하지 못했습니다.");
        return;
      }
      bridge.ask(question).then(function (result) {
        if (token !== _mvpRequestToken) return; // late/aborted response ignored
        setComposerDisabled(false);
        // 5. assistant bubble MUST show the server's model answer, but only
        // for an explicit success. Any other result (ok:false, missing,
        // malformed, rejected, or ok:true with a blank answer) fails closed to
        // the generic Korean message so untrusted diagnostic/answer text never
        // reaches the citizen chat DOM.
        var isExplicitSuccess = result && result.ok === true;
        var normalizedAnswer = (
          isExplicitSuccess &&
          typeof result.answer === "string"
        )
          ? result.answer.trim()
          : "";

        // A non-empty answer is the only signal that the result is usable. A
        // blank (or missing/non-string) answer fails closed: no answer is
        // rendered and the action is degraded to "none" so no split or
        // choreography can start from an untrusted/blank success.
        var hasUsableMvpResult = Boolean(normalizedAnswer);

        var answer = hasUsableMvpResult
          ? normalizedAnswer
          : "현재 AI 안내를 연결하지 못했습니다.";
        appendChatMessage("ai", answer);
        if (hasUsableMvpResult) {
          applyQuestRuntimeState(result);
        } else {
          clearQuestRuntimeState();
        }
        // 4. inspect action; only approved local actions move the clone. If a
        // usable MVP answer misses the action for the supported first question,
        // fall back to the existing deterministic local journey instead of
        // leaving the citizen-facing MVP stuck in chat-only mode.
        var action = resolveMvpActionForQuestion(question, result, hasUsableMvpResult);
        if (action === "illegal_parking") {
          beginMvpSplitThenChoreography(question, "illegal_parking");
        } else if (action === "housing_department") {
          beginMvpSplitThenChoreography(question, "housing_department");
        } else if (action === "bulky_waste") {
          beginMvpSplitThenChoreography(question, "bulky_waste");
        } else if (action === "move_in_report") {
          beginMvpSplitThenChoreography(question, "move_in_report");
        } else if (action === "public_health_center") {
          beginMvpSplitThenChoreography(question, "public_health_center");
        } else if (action === "none") {
          // Keep the entry chat; do not move the clone or start a choreography.
        }
        // Any other value: treated as none (no split, no clone move).
      }).catch(function () {
        if (token !== _mvpRequestToken) return;
        setComposerDisabled(false);
        appendChatMessage("ai", "현재 AI 안내를 연결하지 못했습니다.");
      });
    });
  }

  function beginMvpSplitThenChoreography(question, action) {
    lastSplitQuestion = question;
    setState(STATE_TRANSITIONING);
    if (prefersReducedMotion()) {
      completeMvpSplit(action);
      return;
    }
    splitTimer = window.setTimeout(function () {
      splitTimer = null;
      completeMvpSplit(action);
    }, TRANSITION_DURATION_MS);
  }

  function completeMvpSplit(action) {
    splitTimer = null;
    setState(STATE_SPLIT);
    appendChatMessage(
      "ai",
      "질문을 확인했습니다. 왼쪽에 북구청 안내 화면을 열었습니다."
    );
    appendQuestProgressCard(chatThread);
    // 6. run the existing local choreography for the resolved action
    if (window.CitizenFirstChoreography && action) {
      window.CitizenFirstChoreography.start(action);
    }
    if (chatInput) chatInput.focus();
  }

  function resetToEntry() {
    // Invalidate any in-flight MVP response so a late answer cannot re-open the
    // clone or restart an action after the user reset.
    _mvpRequestToken++;
    clearQuestRuntimeState();
    if (window.CitizenMvpBridge && typeof window.CitizenMvpBridge.cancel === "function") {
      window.CitizenMvpBridge.cancel();
    }
    if (window.CitizenFirstChoreography) {
      window.CitizenFirstChoreography.cancel();
    }
    lastSplitQuestion = null;
    if (splitTimer !== null) {
      window.clearTimeout(splitTimer);
      splitTimer = null;
    }

    body.classList.add("first-use-shell--no-motion");
    setState(STATE_ENTRY);
    renderEntryConversation();
    if (chatInput) {
      chatInput.value = "";
      chatInput.focus();
    }
    window.requestAnimationFrame(function () {
      body.classList.remove("first-use-shell--no-motion");
    });
  }

  if (chatForm) {
    chatForm.addEventListener("submit", handleSubmission);
  }

  if (resetButton) {
    resetButton.addEventListener("click", resetToEntry);
  }

  // #965: chip click → submit question
  if (chipsContainer) {
    chipsContainer.addEventListener("click", function (e) {
      var chip = e.target.closest("[data-chip-question]");
      if (!chip) return;
      var question = chip.getAttribute("data-chip-question");
      if (!question) return;
      if (chatInput) {
        chatInput.value = question;
      }
      // Trigger submission
      if (chatForm) {
        chatForm.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });
  }

  if (isLegacyJourneyLoad()) {
    setState(STATE_SPLIT);
  } else {
    setState(STATE_ENTRY);
    renderEntryConversation();
  }

  window.CitizenFirstUseShell = Object.freeze({
    getState: function () { return currentState; },
    getQuestRuntimeResult: function () { return _questRuntimeResult; },
    isSupportedQuestion: isSupportedQuestion,
    renderQuestProgressCard: renderQuestProgressCard,
    appendQuestProgressCard: appendQuestProgressCard,
    reset: resetToEntry,
    states: Object.freeze({
      entry: STATE_ENTRY,
      transitioning: STATE_TRANSITIONING,
      split: STATE_SPLIT
    })
  });
})();
