import sys

with open('src/web/static/citizen-first-choreography.js', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add the new scenario to JOURNEY_MAP
scenario = '''    "쓰레기 무단투기 신고할래 (AI 도움)": Object.freeze({
      id: "complaint-ai-assist",
      description: "쓰레기 무단투기 신고 - AI 폼 자동 완성 보조",
      steps: Object.freeze([
        Object.freeze({ message: "쓰레기 무단투기 신고 작성을 도와드립니다.", thinkingText: "안내를 준비 중입니다...", thinkingMs: 500, delayMs: 1000 }),
        Object.freeze({ message: "민원게시판의 글쓰기 양식으로 이동합니다.", routeId: "complaint-write", delayMs: 2000, thinkingText: "게시판으로 이동 중입니다...", thinkingMs: 700 }),
        Object.freeze({ message: "직접 작성하시겠습니까, 아니면 AI가 초안 작성을 도와드릴까요?", requiresChoice: true, delayMs: 1000 }),
        Object.freeze({ message: "[사용자 선택: AI 도움 받기] 어떤 불편사항이 있으신지 편하게 말씀해 주세요.", delayMs: 1500, thinkingText: "답변을 기다리는 중입니다...", thinkingMs: 800 }),
        Object.freeze({ message: "집 앞 공원에 쓰레기가 너무 많고 냄새가 나요. 빨리 치워주세요.", isUserSimulated: true, delayMs: 2500 }),
        Object.freeze({ message: "말씀하신 내용을 바탕으로 민원 접수 양식에 맞게 초안을 작성합니다...", thinkingText: "내용을 분석하고 윤문하는 중입니다...", thinkingMs: 1500, delayMs: 1500 }),
        Object.freeze({ message: "AI가 서식을 모두 채웠습니다.", focusSearch: true, typeQuery: "[환경정비 요청] ○○공원 내 방치 쓰레기 수거 및 악취 해결 요청", cursorTarget: "#board-write-title", delayMs: 1500, typeContent: "구정 발전에 노고가 많으십니다. 다름이 아니오라 집 앞 공원에 무단 투기된 쓰레기가 다량 방치되어 있어 심한 악취와 미관 훼손이 발생하고 있습니다. 조속한 환경 정비 및 수거를 요청드립니다." }),
        Object.freeze({ message: "작성된 내용을 확인하시고 화면의 [제출하기] 버튼을 눌러주세요.", requiresConfirmation: true, delayMs: 1000 }),
        Object.freeze({ message: "민원 신고가 성공적으로 접수되었습니다." })
      ]),
    }),'''

# Inject before the final '});' of JOURNEY_MAP
content = content.replace('  });\n\n  // ═══════════════════════════════════════════════════════════════════', scenario + '\n  });\n\n  // ═══════════════════════════════════════════════════════════════════')

# 2. Add requiresChoice logic in _executeStep
confirm_logic = '''      if (step.requiresChoice) {
        var effectiveDelayChoice = Math.max(step.delayMs || 0, visualActionDelay + 320);
        _timer = window.setTimeout(function () {
          _timer = null;
          _setState("waiting_choice");
          _renderChoicePrompt(index);
        }, effectiveDelayChoice);
      } else if (step.requiresConfirmation) {'''

content = content.replace('      if (step.requiresConfirmation) {', confirm_logic)

# 3. Handle isUserSimulated and typeContent in _executeStep and rendering
simulated_logic = '''      if (step.isUserSimulated && _chatThread) {
        var msgEl = document.createElement("div");
        msgEl.className = "chat-msg chat-msg--user";
        msgEl.textContent = step.message;
        _chatThread.appendChild(msgEl);
        _chatThread.scrollTop = _chatThread.scrollHeight;
      } else if (step.message && _chatThread) {'''

content = content.replace('      if (step.message && _chatThread) {', simulated_logic)

type_content_logic = '''        if (cCanvas && typeof cCanvas.showCursorAt === "function" && step.cursorTarget) {
          cCanvas.showCursorAt(step.cursorTarget, 0);
        }
        if (step.typeQuery) {
          _typeOutQuery(step.typeQuery, step.cursorTarget, step.typeContent, function() {
            if (typeof step.delayMs === "number" && step.delayMs > 0) {'''

content = content.replace('''        if (cCanvas && typeof cCanvas.showCursorAt === "function" && step.cursorTarget) {
          cCanvas.showCursorAt(step.cursorTarget, 0);
        }
        if (step.typeQuery) {
          _typeOutQuery(step.typeQuery, step.cursorTarget, function() {
            if (typeof step.delayMs === "number" && step.delayMs > 0) {''', type_content_logic)


# 4. Modify _typeOutQuery signature to handle typeContent
type_out_def = '''  function _typeOutQuery(text, selector, contentText, callback) {
    if (typeof contentText === "function") {
      callback = contentText;
      contentText = null;
    }
    var input = document.getElementById(selector.replace("#", ""));
    if (!input) {
      if (callback) callback();
      return;
    }
    input.value = "";
    var i = 0;
    var len = text.length;
    var timer = window.setInterval(function() {
      input.value += text.charAt(i);
      i++;
      if (i >= len) {
        window.clearInterval(timer);
        if (contentText) {
           var contentArea = document.getElementById("board-write-content");
           if (contentArea) {
             var j = 0;
             var len2 = contentText.length;
             var timer2 = window.setInterval(function() {
                contentArea.value += contentText.charAt(j);
                j++;
                if (j >= len2) {
                   window.clearInterval(timer2);
                   if (callback) callback();
                }
             }, 30);
           } else {
             if (callback) callback();
           }
        } else {
           if (callback) callback();
        }
      }
    }, 50);
  }'''

# Replace the original _typeOutQuery definition. We will find it by regex or exact match.
# In citizen-first-choreography.js, the original looks like:
orig_type_out = '''  function _typeOutQuery(text, selector, callback) {
    var input = document.getElementById(selector.replace("#", ""));
    if (!input) {
      if (callback) callback();
      return;
    }
    input.value = "";
    var i = 0;
    var len = text.length;
    var timer = window.setInterval(function() {
      input.value += text.charAt(i);
      i++;
      if (i >= len) {
        window.clearInterval(timer);
        if (callback) callback();
      }
    }, 50);
  }'''

content = content.replace(orig_type_out, type_out_def)


# 5. Add _renderChoicePrompt and handleChoice
choice_prompt = '''  function _renderChoicePrompt(index) {
    if (!_chatThread) return;
    var messageEl = document.createElement("div");
    messageEl.className = "chat-msg chat-msg--ai";
    messageEl.innerHTML = '<div class="chat-avatar" aria-label="AI">A</div>' +
      '<div class="chat-bubble chat-bubble--ai" style="display:flex; flex-direction:column; gap:10px;">' +
        '<span>직접 작성하시겠습니까, 아니면 AI가 초안 작성을 도와드릴까요?</span>' +
        '<div style="display:flex; gap:10px;">' +
          '<button type="button" class="bg-dept-search__btn" style="background:#666; padding:5px 10px; font-size:14px;" onclick="window.CitizenFirstChoreography.cancel()">직접 작성</button>' +
          '<button type="button" class="bg-dept-search__btn" style="padding:5px 10px; font-size:14px;" onclick="window.CitizenFirstChoreography.handleChoice(' + index + ')">AI 도움 받기</button>' +
        '</div>' +
      '</div>';
    _chatThread.appendChild(messageEl);
    _chatThread.scrollTop = _chatThread.scrollHeight;
  }

  function handleChoice(index) {
    _setState(STATE_RUNNING);
    _executeStep(index + 1);
  }

  function _renderConfirmationPrompt(index) {'''

content = content.replace('  function _renderConfirmationPrompt(index) {', choice_prompt)

export = '''    hasJourney: hasJourney,
    confirmSubmission: confirmSubmission,
    handleChoice: handleChoice,'''

content = content.replace('''    hasJourney: hasJourney,
    confirmSubmission: confirmSubmission,''', export)

with open('src/web/static/citizen-first-choreography.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("citizen-first-choreography.js patched for AI assist successfully.")
