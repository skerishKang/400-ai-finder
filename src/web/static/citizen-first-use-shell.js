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
  var TRANSITION_DURATION_MS = 1100;
  var SUPPORTED_QUESTION_ACTIONS = {
    "불법 주정차 신고는 어디서 하나요?": "illegal_parking",
    "공동주택 관련 문의는 어느 부서에 해야 하나요?": "housing_department",
    "침대 매트리스 버리고 싶어요": "bulky_waste",
    "대형폐기물은 어떻게 버리나요?": "bulky_waste",
    "가구 버리려면 어디서 신청해요?": "bulky_waste",
    "매트리스 폐기 신청은 어디서 하나요?": "bulky_waste",
    "여권 발급은 어디서 하나요?": "passport_guidance",
    "여권 재발급은 어떻게 하나요?": "passport_guidance",
    "무인민원발급기 어디 있어요?": "unmanned_kiosk",
    "무인민원발급기로 뭘 발급받을 수 있어요?": "unmanned_kiosk",
    "무인민원발급기 이용방법 알려줘": "unmanned_kiosk",
    "민원서류 발급받으려면 어디로 가야 해요?": "unmanned_kiosk",
    "가로등이 고장났어요. 신고할게요": "streetlight_report",
    "쓰레기 무단투기 신고할래 (AI 도움)": "litter_ai_assist",
    // #1114 — mayor proposal entry (same journey object as the canonical question)
    "구청장에게 제안하고 싶어요": "mayor_message_assist",
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
    // Live build injects ?mvp=1 into URL before shell init.
    // body data-mvp check is a compatibility path — not the current build activation method.
    if (document.body && document.body.getAttribute("data-mvp") === "1") return true;
    // Fallback: check URL parameter
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
    if (a === "illegal_parking" || a === "housing_department" || a === "bulky_waste" || a === "passport_guidance" || a === "unmanned_kiosk" || a === "streetlight_report" || a === "litter_ai_assist" || a === "mayor_message_assist" || a === "none") {
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

  function sourceModeLabel(value) {
    var sourceMode = textValue(value);
    if (sourceMode === "local_static") return "북구청 공식 화면 기준";
    if (sourceMode === "live_official" || sourceMode === "live") return "북구청 최신 공식 데이터";
    if (sourceMode === "cached_official" || sourceMode === "cache") return "북구청 공식 데이터 사본";
    return sourceMode ? "공식 자료 확인" : "";
  }

  function stopConditionLabel(value) {
    var stopCondition = textValue(value);
    if (stopCondition === "STOP_FOR_USER_CONFIRMATION") return "사용자 확인 후 진행";
    if (stopCondition === "COMPLETE" || stopCondition === "DONE") return "안내 완료";
    if (stopCondition === "RUNNING") return "AI가 안내 중";
    return stopCondition ? "안내 준비 완료" : "";
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
      sourceModeLabel: sourceModeLabel(plan.source_mode || quest.source_mode),
      stopCondition: textValue(plan.stop_condition || quest.stop_condition),
      stopConditionLabel: stopConditionLabel(plan.stop_condition || quest.stop_condition),
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
      makeQuestCardRow("공식 경로", payload.officialPath),
      makeQuestCardRow("확인 결과", payload.resultText),
      makeQuestCardRow("정보 기준", payload.sourceModeLabel),
      makeQuestCardRow("진행 상태", payload.stopConditionLabel),
    ].forEach(function (row) {
      if (row) card.appendChild(row);
    });

    if (payload.actionLabels.length) {
      var actions = document.createElement("div");
      actions.className = "chat-quest-card__actions";
      var actionsLabel = document.createElement("span");
      actionsLabel.className = "chat-quest-card__actions-label";
      actionsLabel.textContent = "AI가 수행할 작업";
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

    var warningRow = makeQuestCardRow("확인 사항", payload.finalWarningText, "chat-quest-card__row--warning");
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
    // Exact presentation prompts are product-owned routes. Keep them stable
    // even when the live model is unavailable or classifies a chip loosely.
    var normalized = normalizeQuestion(question);
    var mapped = SUPPORTED_QUESTION_ACTIONS[normalized];
    if (mapped) return mapped;
    if (!hasUsableMvpResult) return "none";
    var action = normalizeMvpAction(result);
    if (action !== "none") return action;
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
    return Boolean(SUPPORTED_QUESTION_ACTIONS[normalizeQuestion(value)]);
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

  // ── Static Bukgu Homepage Fixture ───────────────────────────────────
  // Renders the Bukgu Office main portal layout as a static fixture for the
  // initial left surface (first visible canvas content on split).
  // Uses existing CSS classes from citizen-action-demo-canvas.css and
  // existing image assets from /static/images/bukgu-current/.

  function _bukguSearchIcon() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="10.8" cy="10.8" r="6.3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 16l4.4 4.4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
  }
  function _bukguMenuIcon() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16M4 12h16M4 17h16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
  }
  function _bukguArrowLeft() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M14.5 5.5L8 12l6.5 6.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  }
  function _bukguArrowRight() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M9.5 5.5L16 12l-6.5 6.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  }

  function _renderBukguHomeFixture() {
    if (!canvas) return;
    // Keep the split reveal on the canonical canvas renderer. The historical
    // fallback below intentionally remains for shells loaded without the
    // canvas module, but must not overwrite newer home controls and routes.
    if (window.CitizenActionDemoCanvas &&
        typeof window.CitizenActionDemoCanvas.navigateToRoute === "function") {
      window.CitizenActionDemoCanvas.navigateToRoute("home");
      return;
    }
    var assets = "/static/images/bukgu-current";
    var searchIcon = _bukguSearchIcon();
    var menuIcon = _bukguMenuIcon();
    var arrowLeft = _bukguArrowLeft();
    var arrowRight = _bukguArrowRight();

    // Quick links
    var quickItems = [
      ["home-quick-work.png", "업무검색"],
      ["home-quick-office.png", "청사안내"],
      ["home-quick-donation.png", "고향사랑기부제"],
      ["home-quick-money.png", "부끄머니"],
      ["home-quick-reservation.png", "통합예약"],
      ["home-quick-waiting.png", "일반민원 대기현황"],
    ];
    var quickHtml = "";
    for (var i = 0; i < quickItems.length; i++) {
      quickHtml +=
        '<a href="#" class="bg-home-quick-link">' +
          '<img src="' + assets + '/' + quickItems[i][0] + '" alt="" class="bg-home-quick-link__icon" />' +
          '<span class="bg-home-quick-link__label">' + quickItems[i][1] + '</span>' +
        '</a>';
    }

    var html =
      '<div class="bg-page bg-page--full bg-page--home" data-home-reference-state="R-HOME-01">' +

        // Skip navigation
        '<div class="bg-skip"><a href="#bg-content-main">본문으로 바로가기</a></div>' +

        // Government strip
        '<div class="bg-home-gov-strip">' +
          '<div class="bg-home-gov-strip__inner">' +
            '<img src="' + assets + '/home-government-notice.png" alt="본 누리집은 전남광주통합특별시 북구청 공식 누리집입니다." class="bg-home-gov-strip__notice" />' +
          '</div>' +
        '</div>' +

        // Utility bar (weather, major sites)
        '<div class="bg-home-utility" aria-label="사이트 도구">' +
          '<div class="bg-home-utility__inner">' +
            '<div class="bg-home-utility__weather">' +
              '<strong>26\u00B0C</strong>' +
              '<span>\uBBF8\uC138\uBA3C\uC9C0 <b>\uC88B\uC74C</b></span>' +
              '<span>\uCD08\uBBF8\uC138\uBA3C\uC9C0 <b>\uC88B\uC74C</b></span>' +
            '</div>' +
            '<div class="bg-home-utility__menus">' +
              '<a href="#">\uC8FC\uC694\uC0AC\uC774\uD2B8 <span aria-hidden="true">\u25BE</span></a>' +
              '<a href="#">SNS <span aria-hidden="true">\u25BE</span></a>' +
              '<a href="#">KOR <span aria-hidden="true">\u25BE</span></a>' +
            '</div>' +
          '</div>' +
        '</div>' +

        // Header + Logo + GNB
        '<header class="bg-header">' +
          '<div class="bg-home-header">' +
          '<div class="bg-home-header__inner">' +
            '<a href="#" class="bg-home-header__identity" aria-label="\uC804\uB0A8\uAD11\uC8FC\uD1B5\uD569\uD2B9\uBCC4\uC2DC\uBD81\uAD6C \uD648">' +
              '<img src="' + assets + '/home-identity.png" alt="\uC804\uB0A8\uAD11\uC8FC\uD1B5\uD569\uD2B9\uBCC4\uC2DC\uBD81\uAD6C" />' +
            '</a>' +
            '<nav class="bg-gnb" aria-label="\uC8FC\uBA54\uB274">' +
              '<div class="bg-home-gnb">' +
              '<a href="#" class="bg-home-gnb__link bg-home-gnb__link--active">\uC885\uD569\uBBFC\uC6D0</a>' +
              '<a href="#" class="bg-home-gnb__link">\uC18C\uD1B5\uAD11\uC7A5</a>' +
              '<a href="#" class="bg-home-gnb__link">\uB354\uBD88\uC5B4\uBCF5\uC9C0</a>' +
              '<a href="#" class="bg-home-gnb__link">\uBD84\uC57C\uBCC4\uC815\uBCF4</a>' +
              '<a href="#" class="bg-home-gnb__link">\uC815\uBCF4\uACF5\uAC1C</a>' +
              '<a href="#" class="bg-home-gnb__link">\uBD81\uAD6C\uC18C\uAC1C</a>' +
            '</div>' +
            '</nav>' +
            '<div class="bg-home-header__actions">' +
              '<button type="button" class="bg-home-header__icon" aria-label="\uD1B5\uD569\uAC80\uC0C9">' + searchIcon + '<span>\uD1B5\uD569\uAC80\uC0C9</span></button>' +
              '<button type="button" class="bg-home-header__icon" aria-label="\uC804\uCCB4\uBA54\uB274">' + menuIcon + '<span>\uC804\uCCB4\uBA54\uB274</span></button>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '</header>' +

        // Search section
        '<section class="bg-home-search" aria-label="\uD1B5\uD569\uAC80\uC0C9">' +
          '<div class="bg-home-search__inner">' +
            '<img src="' + assets + '/home-civic-brand.png" alt="\uBE5B\uB098\uB294 \uBD81\uAD6C, \uD568\uAED8\uD558\uB294 \uBD81\uAD6C - \uD589\uBCF5\uD55C \uAD6C\uBBFC\uC744 \uC704\uD55C \uB530\uB73B\uD55C \uBCC0\uD654" class="bg-home-search__brand" />' +
            '<div class="bg-home-search__cluster">' +
              '<div class="bg-home-search__field">' +
                '<input type="text" placeholder="\uAC80\uC0C9\uC5B4\uB97C \uC785\uB825\uD558\uC138\uC694." aria-label="\uAC80\uC0C9\uC5B4" disabled />' +
                '<button type="button" aria-label="\uAC80\uC0C9" disabled>' + searchIcon + '</button>' +
              '</div>' +
              '<div class="bg-home-search__tags"><span>#\uACF5\uB3D9\uC8FC\uD0DD\uACFC</span><span>#\uC704\uC0DD\uACFC</span><span>#\uD3D0\uAE30\uBB3C</span><span>#\uBD80\uAF34\uBA38\uB2C8</span></div>' +
            '</div>' +
          '</div>' +
        '</section>' +

        // Main content
        '<main id="bg-content-main" class="bg-home-main">' +

          // Lead banners (sliding visual area)
          '<section class="bg-home-lead" aria-label="\uC8FC\uC694 \uC548\uB0B4">' +
            '<article class="bg-home-lead__mayor">' +
              '<img src="' + assets + '/home-mayor-card.png" alt="\uB530\uB73B\uD55C \uBD81\uAD6C\uB97C \uB9CC\uB4E4\uACA0\uC2B5\uB2C8\uB2E4. \uBD81\uAD6C\uCCAD\uC7A5 \uC2E0\uC218\uC815\uC785\uB2C8\uB2E4." />' +
            '</article>' +
            '<article class="bg-home-lead__banner" aria-label="\uC18C\uC18D \uACF5\uBB34\uC6D0 \uC0AC\uCE6D \uD53C\uD574\uC8FC\uC758 \uC54C\uB9BC">' +
              '<img src="' + assets + '/home-alert-banner.png" alt="\uC8FC\uC694 \uC54C\uB9BC \uBC30\uB108" />' +
            '</article>' +
          '</section>' +

          // Quick links
          '<nav class="bg-home-quick" aria-label="\uBE60\uB978 \uC11C\uBE44\uC2A4">' +
            '<button type="button" class="bg-home-quick__arrow" aria-label="\uC774\uC804" disabled>' + arrowLeft + '</button>' +
            '<div class="bg-home-quick__items">' + quickHtml + '</div>' +
            '<button type="button" class="bg-home-quick__arrow" aria-label="\uB2E4\uC74C" disabled>' + arrowRight + '</button>' +
          '</nav>' +

          // Notice board + Major sites
          '<section class="bg-home-notice-sites" aria-label="\uACF5\uC9C0\uC640 \uC8FC\uC694 \uC0AC\uC774\uD2B8">' +
            '<article class="bg-home-notice">' +
              '<div class="bg-home-notice__tabs" role="tablist" aria-label="\uAC8C\uC2DC\uD310">' +
                '<button type="button" role="tab" aria-selected="true">\uACF5\uC9C0\uC0AC\uD56D</button>' +
                '<button type="button" role="tab">\uACE0\uC2DC/\uACF5\uACE0</button>' +
                '<button type="button" role="tab">\uC785\uCC30\uACF5\uACE0</button>' +
                '<button type="button" role="tab">\uCDE4\uC6A9\uACF5\uACE0</button>' +
                '<button type="button" class="bg-home-notice__more" aria-label="\uB354\uBCF4\uAE30">+</button>' +
              '</div>' +
              '<ul class="bg-home-notice__list">' +
                '<li><b>07</b><span>\uCCAD\uC0AC \uC2B9\uAC15\uAE30 \uC815\uAE30\uC810\uAC80 \uC548\uB0B4</span></li>' +
                '<li><b>07</b><span>2026\uB144 \uD558\uBC18\uAE30 \uAD6C\uBBFC \uAD50\uC721 \uD504\uB85C\uADF8\uB7A8 \uC548\uB0B4</span></li>' +
                '<li><b>07</b><span>\uC5EC\uB984\uCCA0 \uC548\uC804\uC218\uC808 \uC2DC\uC124 \uD655\uBCF4 \uC0AC\uC5C5 \uC548\uB0B4</span></li>' +
                '<li><b>07</b><span>\uD3D0\uAE30\uBB3C \uBC30\uCD9C \uC2E0\uCCAD \uC77C\uC790 \uBCC0\uACBD \uC548\uB0B4</span></li>' +
              '</ul>' +
            '</article>' +
            '<article class="bg-home-sites">' +
              '<div class="bg-home-sites__head"><h2>\uC8FC\uC694\uC0AC\uC774\uD2B8</h2><span>\u2039&nbsp;&nbsp;1 / 4&nbsp;&nbsp;\u2161&nbsp;&nbsp;\u203A</span></div>' +
              '<div class="bg-home-sites__grid">' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--chart"></i>\uD1B5\uACC4\uC815\uBCF4</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--school"></i>\uD3C9\uC0DD\uD559\uC2B5\uAD00</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--sun"></i>\uCCAD\uB144\uC13C\uD130</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--culture"></i>\uBB38\uD654\uC13C\uD130</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--park"></i>\uACF5\uC6D0\uC2DC\uC124 \uC608\uC57D</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--sport"></i>\uCCB4\uC721\uC2DC\uC124 \uC608\uC57D</a>' +
              '</div>' +
            '</article>' +
          '</section>' +

          // Lower section
          '<section class="bg-home-lower" aria-label="\uD558\uB2E8 \uC18C\uC2DD\uACFC \uBD84\uC57C\uBCC4 \uC815\uBCF4">' +
            '<section class="bg-home-lower-cards" aria-label="\uC8FC\uC694 \uC18C\uC2DD">' +
              '<article class="bg-home-lower-card">' +
                '<div class="bg-home-lower-card__head"><h2>\uACE0\uD5A5\uC0AC\uB791\uAE30\uBD80\uC81C</h2><span aria-hidden="true">\u2039&nbsp;\u2161&nbsp;\u203A&nbsp;+</span></div>' +
                '<img src="' + assets + '/home-lower-hometown-donation.png" alt="\uACE0\uD5A5\uC0AC\uB791\uAE30\uBD80\uC81C \uC548\uB0B4" />' +
              '</article>' +
              '<article class="bg-home-lower-card">' +
                '<div class="bg-home-lower-card__head"><h2>\uD604\uC7A5\uC2A4\uCF00\uCE58</h2><span aria-hidden="true">\u2039&nbsp;<b>1</b> / 4&nbsp;\u2161&nbsp;\u203A&nbsp;+</span></div>' +
                '<img src="' + assets + '/home-lower-field-sketch.png" alt="\uD604\uC7A5\uC2A4\uCF00\uCE58" />' +
              '</article>' +
              '<article class="bg-home-lower-card">' +
                '<div class="bg-home-lower-card__head"><h2>\uCE74\uB4DC\uB274\uC2A4</h2><span aria-hidden="true">+</span></div>' +
                '<img src="' + assets + '/home-lower-card-news.png" alt="\uCE74\uB4DC\uB274\uC2A4" />' +
              '</article>' +
              '<article class="bg-home-lower-card">' +
                '<div class="bg-home-lower-card__head"><h2>\uC54C\uB9AC\uBBF8</h2><span aria-hidden="true">\u2039&nbsp;<b>1</b> / 4&nbsp;\u2161&nbsp;\u203A&nbsp;+</span></div>' +
                '<img src="' + assets + '/home-lower-notifier.png" alt="\uC54C\uB9AC\uBBF8" />' +
              '</article>' +
            '</section>' +
          '</section>' +

        '</main>' +

        // Footer
        '<footer class="bg-home-footer" aria-label="\uC0AC\uC774\uD2B8 \uD558\uB2E8">' +
          '<div class="bg-home-footer__inner">' +
            '<nav class="bg-home-footer__nav" aria-label="\uD558\uB2E8 \uBA54\uB274">' +
              '<a href="#">\uBD80\uC11C\uC548\uB0B4 <span aria-hidden="true">\u2303</span></a>' +
              '<a href="#">\uB3D9 \uD589\uC815\uBCF5\uC9C0\uC13C\uD130 <span aria-hidden="true">\u2303</span></a>' +
              '<a href="#">\uC8FC\uC694 \uC0AC\uC774\uD2B8 <span aria-hidden="true">\u2303</span></a>' +
              '<a href="#">\uC720\uAD00\uAE30\uAD00 <span aria-hidden="true">\u2303</span></a>' +
            '</nav>' +
            '<div class="bg-home-footer__legal">' +
              '<p><strong>\uC804\uB0A8\uAD11\uC8FC\uD1B5\uD569\uD2B9\uBCC4\uC2DC \uBD81\uAD6C</strong></p>' +
              '<p>61118 \uAD11\uC8FC \uBD81\uAD6C \uC6B0\uCE58\uB85C 77 (\uD50C\uB9BC\uB3D9)</p>' +
              '<p>\uB300\uD45C\uC804\uD654 062-410-8114 | \uD64D\uBCF4\uAD00\uB780\uBA54\uC77C webmaster@bukgu.gwangju.kr</p>' +
              '<p>\uD3C9\uC77C 09:00 ~ 18:00 (\uC811\uC218\uC2DC\uAC04 09:00 ~ 17:30) / \uD1A0/\uC77C\uC694\uC77C \uAD6C\uAD6C\uC815\uC0AC\uBB34\uC548\uB0B4 \uD655\uC778</p>' +
            '</div>' +
          '</div>' +
        '</footer>' +
      '</div>';

    canvas.innerHTML = '<div class="demo-canvas__inner">' + html + '</div>';
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
      chipsContainer.hidden = false;
    }
  }

  function clearChatMotionStyles() {
    if (!chatShell) return;
    chatShell.style.removeProperty("transition");
    chatShell.style.removeProperty("transform");
    chatShell.style.removeProperty("transform-origin");
    body.removeAttribute("data-split-motion");
  }

  function fitOfficialCanvas() {
    if (window.CitizenActionDemoCanvas &&
        typeof window.CitizenActionDemoCanvas.fitToViewport === "function") {
      window.CitizenActionDemoCanvas.fitToViewport();
    }
  }

  function resetOfficialCanvasScroll() {
    if (!canvas) return;
    canvas.scrollTop = 0;
    canvas.scrollLeft = 0;
  }

  function clearPreviousJourneyLocationState() {
    if (!window.location || !window.history || typeof window.history.replaceState !== "function") {
      return;
    }
    try {
      var params = new URLSearchParams(window.location.search || "");
      ["journey", "dept-state", "replay", "replay-mode", "replay-step"].forEach(function (key) {
        params.delete(key);
      });
      var query = params.toString();
      var path = window.location.pathname || "";
      var hash = window.location.hash || "";
      window.history.replaceState({}, "", path + (query ? "?" + query : "") + hash);
    } catch (_) {
      // URL state is an enhancement; the DOM and scroll reset still proceed.
    }
  }

  function startCinematicSplit() {
    if (window.CitizenFirstChoreography &&
        typeof window.CitizenFirstChoreography.cancel === "function") {
      window.CitizenFirstChoreography.cancel();
    }
    if (window.CitizenActionDemoCanvas &&
        typeof window.CitizenActionDemoCanvas.hideCursor === "function") {
      window.CitizenActionDemoCanvas.hideCursor();
    }
    clearPreviousJourneyLocationState();
    resetOfficialCanvasScroll();

    // Paint the official canvas before the reveal starts so the animation
    // exposes a complete page rather than a loading placeholder.
    _renderBukguHomeFixture();
    resetOfficialCanvasScroll();

    if (prefersReducedMotion() || !chatShell || !window.requestAnimationFrame) {
      setState(STATE_TRANSITIONING);
      fitOfficialCanvas();
      resetOfficialCanvasScroll();
      return;
    }

    var firstRect = chatShell.getBoundingClientRect();
    setState(STATE_TRANSITIONING);
    fitOfficialCanvas();
    resetOfficialCanvasScroll();
    var lastRect = chatShell.getBoundingClientRect();
    var scaleX = lastRect.width ? firstRect.width / lastRect.width : 1;
    var scaleY = lastRect.height ? firstRect.height / lastRect.height : 1;
    var translateX = firstRect.left - lastRect.left;
    var translateY = firstRect.top - lastRect.top;

    body.setAttribute("data-split-motion", "active");
    chatShell.style.transition = "none";
    chatShell.style.transformOrigin = "top left";
    chatShell.style.transform =
      "translate(" + translateX + "px," + translateY + "px) " +
      "scale(" + scaleX + "," + scaleY + ")";
    chatShell.getBoundingClientRect();

    window.requestAnimationFrame(function () {
      window.requestAnimationFrame(function () {
        chatShell.style.transition =
          "transform " + TRANSITION_DURATION_MS + "ms cubic-bezier(0.16, 1, 0.3, 1), " +
          "border-radius 900ms ease, box-shadow 900ms ease";
        chatShell.style.transform = "translate(0,0) scale(1,1)";
      });
    });
  }

  function scrollChatToLatest() {
    if (chatThread) {
      chatThread.scrollTop = chatThread.scrollHeight;
    }
  }

  function appendChatMessage(role, text) {
    if (!chatThread) {
      return null;
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
    return message;
  }

  function freshnessLabel(value) {
    if (value === "live_official") return "최신 공식자료 확인";
    if (value === "official_snapshot") return "북구청 공식 스냅샷";
    if (value === "live_web") return "최신 웹자료 확인 · 공식 출처 재확인 필요";
    if (value === "model_only") return "현재 공식 출처 없음";
    return "최신성 확인 불가";
  }

  function formatRetrievedAt(value) {
    if (!value) return "";
    try {
      return new Date(value).toLocaleString("ko-KR", {
        timeZone: "Asia/Seoul",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (_) {
      return "";
    }
  }

  function appendAnswerFreshness(message, result) {
    if (!message || !result || result.ok !== true) return;
    var sources = Array.isArray(result.sources) ? result.sources.slice(0, 3) : [];
    var provenanceTime = result.freshness_state === "official_snapshot"
      ? (result.verified_at || result.captured_at)
      : result.retrieved_at;
    var retrievedAt = formatRetrievedAt(provenanceTime);
    if (!retrievedAt && !sources.length && !result.freshness_state) return;

    var meta = document.createElement("div");
    meta.className = "chat-answer-meta";
    meta.setAttribute("data-freshness-state", result.freshness_state || "unknown");

    var status = document.createElement("span");
    status.className = "chat-answer-meta__status";
    status.textContent = freshnessLabel(result.freshness_state) + (retrievedAt ? " · " + retrievedAt : "");
    meta.appendChild(status);

    sources.forEach(function (source) {
      if (!source || typeof source.url !== "string") return;
      var link;
      try {
        var parsed = new URL(source.url);
        if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return;
        link = document.createElement("a");
        link.href = parsed.toString();
      } catch (_) {
        return;
      }
      link.className = "chat-answer-meta__source";
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = source.official ? "공식 출처" : "참고 출처";
      link.setAttribute("aria-label", (source.title || "답변 출처") + " 새 창 열기");
      meta.appendChild(link);
    });

    var bubble = message.querySelector && message.querySelector(".chat-bubble");
    (bubble || message).appendChild(meta);
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
    if (question.indexOf("여권") !== -1) return "여권 발급 안내";
    if (question.indexOf("무인민원발급기") !== -1 || question.indexOf("민원서류") !== -1) return "무인민원발급기 안내";
    if (question.indexOf("가로등") !== -1) return "가로등 고장 신고";
    if (question.indexOf("쓰레기") !== -1) return "쓰레기 무단투기 신고";
    return "이 안내";
  }

  function _actionDisplayName(action) {
    if (action === "illegal_parking") return "불법 주정차 신고";
    if (action === "housing_department") return "공동주택 부서 문의";
    if (action === "bulky_waste") return "대형폐기물 배출";
    if (action === "passport_guidance") return "여권 발급 안내";
    if (action === "unmanned_kiosk") return "무인민원발급기 안내";
    if (action === "streetlight_report") return "가로등 고장 신고";
    if (action === "litter_ai_assist") return "쓰레기 무단투기 신고";
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

  // MVP confirm-run step: mirrors showConfirmRun but maps an action code to a
  // display name instead of a free-text question. The local choreography must
  // NOT start until the citizen explicitly chooses [예, 안내해 주세요].
  function showConfirmRunForAction(action) {
    var displayName = _actionDisplayName(action);
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
      if (window.CitizenFirstChoreography && action) {
        window.CitizenFirstChoreography.start(action);
      }
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
    clearChatMotionStyles();
    fitOfficialCanvas();
    // Delay chat message slightly so the canvas fade-in is visible first
    setTimeout(function () {
      appendChatMessage(
        "ai",
        "질문을 확인했습니다. 왼쪽에 북구청 안내 화면을 열었습니다."
      );
      if (lastSplitQuestion) {
        showConfirmRun(lastSplitQuestion);
      }
      lastSplitQuestion = null;
    }, 220);
  }

  function beginSupportedTransition(question) {
    lastSplitQuestion = question;
    appendChatMessage("user", question);
    if (chatInput) {
      chatInput.value = "";
    }

    startCinematicSplit();

    if (prefersReducedMotion()) {
      completeSplit();
      return;
    }

    splitTimer = window.setTimeout(completeSplit, TRANSITION_DURATION_MS);
  }

  // ── #1114: central mayor-proposal entry ─────────────────────────
  // Both the chat chip/composer submission of "구청장에게 제안하고 싶어요" and the
  // hero "열린구청장실 바로가기" control activation converge here. The canonical
  // question + action are fixed; the user message is shown exactly once and the
  // existing MAYOR_MESSAGE_ASSIST_JOURNEY is driven through the shared
  // choreography — no duplicate dispatch, no direct final-route jump.
  var MAYOR_CANONICAL_QUESTION = "구청장에게 제안하고 싶어요";
  var MAYOR_CANONICAL_ACTION = "mayor_message_assist";

  function isMayorQuestion(value) {
    return normalizeQuestion(value) === MAYOR_CANONICAL_QUESTION;
  }

  function beginMayorProposalEntry() {
    if (!chatInput || currentState === STATE_TRANSITIONING) return;
    // Idempotent guard: if already splitting for the same question, do nothing.
    if (currentState === STATE_SPLIT && lastSplitQuestion === MAYOR_CANONICAL_QUESTION) {
      return;
    }
    // Single user-message echo, shared by both entry points.
    if (currentState !== STATE_SPLIT) {
      appendChatMessage("user", MAYOR_CANONICAL_QUESTION);
      if (chatInput) chatInput.value = "";
    }
    lastSplitQuestion = MAYOR_CANONICAL_QUESTION;
    startCinematicSplit();
    if (prefersReducedMotion()) {
      completeSplit();
    } else {
      splitTimer = window.setTimeout(completeSplit, TRANSITION_DURATION_MS);
    }
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
      if (isSupportedQuestion(question)) {
        // Cancel current choreography and start new quest (no duplicate message)
        if (window.CitizenFirstChoreography) {
          window.CitizenFirstChoreography.cancel();
        }
        lastSplitQuestion = question;
        startCinematicSplit();
        if (prefersReducedMotion()) {
          completeSplit();
        } else {
          splitTimer = window.setTimeout(completeSplit, TRANSITION_DURATION_MS);
        }
      } else {
        appendChatMessage("ai", SPLIT_FOLLOW_UP_MESSAGE);
        chatInput.focus();
      }
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
"현재 첫 화면에서는 불법 주정차 신고, 공동주택 문의, 대형폐기물 처리, 여권 발급 안내, 무인민원발급기 안내를 준비했습니다. 예시 질문으로 다시 입력해 주세요."
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
        if (chatInput) chatInput.focus();
        appendChatMessage("ai", "현재 AI 안내를 연결하지 못했습니다.");
        return;
      }
      bridge.ask(question).then(function (result) {
        if (token !== _mvpRequestToken) return; // late/aborted response ignored
        setComposerDisabled(false);
        if (chatInput) chatInput.focus();
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
        var answerMessage = appendChatMessage("ai", answer);
        appendAnswerFreshness(answerMessage, result);
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
        } else if (action === "passport_guidance") {
          beginMvpSplitThenChoreography(question, "passport_guidance");
        } else if (action === "unmanned_kiosk") {
          beginMvpSplitThenChoreography(question, "unmanned_kiosk");
        } else if (action === "streetlight_report") {
          beginMvpSplitThenChoreography(question, "streetlight_report");
        } else if (action === "litter_ai_assist") {
          beginMvpSplitThenChoreography(question, "litter_ai_assist");
        } else if (action === "none") {
          // Keep the entry chat; do not move the clone or start a choreography.
        }
        // Any other value: treated as none (no split, no clone move).
      }).catch(function () {
        if (token !== _mvpRequestToken) return;
        setComposerDisabled(false);
        if (chatInput) chatInput.focus();
        appendChatMessage("ai", "현재 AI 안내를 연결하지 못했습니다.");
      });
    });
  }

  function beginMvpSplitThenChoreography(question, action) {
    lastSplitQuestion = question;
    startCinematicSplit();
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
    clearChatMotionStyles();
    fitOfficialCanvas();
    // Delay chat message slightly so the canvas fade-in is visible first
    setTimeout(function () {
      appendChatMessage(
        "ai",
        "질문을 확인했습니다. 왼쪽에 북구청 안내 화면을 열었습니다."
      );
      appendQuestProgressCard(chatThread);
      // MVP confirm-run step: do NOT start the local choreography until the
      // citizen explicitly confirms. The confirm bubble shows the resolved
      // action's display name and only starts Choreography.start(action) when
      // the citizen presses [예, 안내해 주세요]. Pressing [아니요] keeps the
      // chat as-is and never starts the choreography.
      if (window.CitizenFirstChoreography && action) {
        showConfirmRunForAction(action);
      }
      if (chatInput) chatInput.focus();
    }, 220);
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
    clearChatMotionStyles();

    // Clear canvas content so split-state HTML isn't left behind
    if (canvas) {
      canvas.innerHTML = '<div class="demo-canvas__inner"><div class="demo-canvas__loading" aria-live="polite">북구청 안내 화면을 준비하는 중…</div></div>';
    }

    body.classList.add("first-use-shell--no-motion");
    setState(STATE_ENTRY);
    // Reset scroll position to top
    if (chatThread) {
      chatThread.scrollTop = 0;
    }
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

  // #1114: hero "열린구청장실 바로가기" control → same canonical mayor entry.
  // No chat round-trip; converges on beginMayorProposalEntry so the user message
  // is shown exactly once and no second bridge dispatch occurs.
  var mayorControl = document.getElementById("mayor-open-office-control");
  if (mayorControl) {
    mayorControl.addEventListener("click", function (e) {
      e.preventDefault();
      beginMayorProposalEntry();
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
