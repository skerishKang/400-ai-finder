/*
 * citizen-first-choreography.js
 * Deterministic local journey choreography for the first-use split shell.
 *
 * Drives the demo-canvas through route transitions, target highlights,
 * search-focused steps, simulated typing, and search submission using
 * only the public CitizenActionDemoCanvas API and DOM access to the
 * public #demo-canvas element.
 *
 * Guarantees:
 * - no fetch/XHR/WebSocket/EventSource/sendBeacon;
 * - no browser persistence or cookie access;
 * - no provider, runner, live-site, or external-origin behavior;
 * - no hidden copilot-rail, executor trace/status, or URL API dependency;
 * - no screenshot layer, fake cursor, or external asset.
 */

(function () {
  "use strict";

  var STATE_IDLE = "idle";
  var STATE_RUNNING = "running";
  var STATE_DONE = "done";
  var STATE_CANCELLED = "cancelled";

  var HIGHLIGHT_CLASS = "executor-highlight";
  var TYPING_CLASS = "executor-typing";
  var SEARCH_BUSY_CLASS = "executor-search-busy";

  var _body = document.body;
  var _chatThread = document.getElementById("chat-thread");
  var _state = STATE_IDLE;
  var _timer = null;
  var _auxTimers = [];
  // #1132: typing timers are separate from substantive action/step timers so
  // runtime normal→reduced can flush in-flight character typing without
  // cancelling route/click/submit progression.
  var _typingTimers = [];
  var _activeTypingOperations = [];
  var _tempIndicatorTimers = [];
  var _canvasScrollTimers = [];
  var _currentStep = -1;
  var _currentJourneyId = null;
  var _steps = [];
  var _highlightedEls = [];
  // #1132: cached reduced-motion flag; shell is canonical owner when present.
  var _reducedMotion = false;
  // #1142: short pause after click visual before route/receipt commit.
  var CLICK_READ_MS = 340;
  // #1143: generation token so delayed click/route commits after cancel or
  // locale reset never resume a stale journey.
  var _journeyGeneration = 0;

  // ═══════════════════════════════════════════════════════════════════
  // #1152: two-stage bilingual draft handoff (non-Korean writing journeys)
  // Stages: idle → resident_draft_review → korean_draft_review → form_populated
  // Public-safe in-memory only — no storage, network, or PII.
  // ═══════════════════════════════════════════════════════════════════
  var DRAFT_STAGE_IDLE = "idle";
  var DRAFT_STAGE_RESIDENT = "resident_draft_review";
  var DRAFT_STAGE_KOREAN = "korean_draft_review";
  var DRAFT_STAGE_FORM = "form_populated";
  var CHOREO_WAITING_RESIDENT_DRAFT = "waiting_resident_draft";
  var CHOREO_WAITING_KOREAN_DRAFT = "waiting_korean_draft";

  var _draftStage = {
    stage: DRAFT_STAGE_IDLE,
    locale: null,
    journeyId: null,
    actionId: null,
    residentTitle: "",
    residentBody: "",
    koreanTitle: "",
    koreanBody: "",
    titleSelector: "",
    contentSelector: "",
    resumeStepIndex: -1,
    revisionIndex: 0,
    generation: 0,
    cardEl: null,
  };

  // Deterministic reviewed fixtures: resident-language source + Korean admin draft.
  // Keys match choreography journey ids.
  var BILINGUAL_DRAFT_FIXTURES = Object.freeze({
    "mayor-message-assist": Object.freeze({
      actionId: "mayor_message_assist",
      titleSelector: "#mayor-write-title",
      contentSelector: "#mayor-write-content",
      koreanTitle: "[안전한 통학로 제안] 학교 앞 횡단보도 조명 개선 요청",
      koreanBody:
        "안녕하세요. 북구의 안전한 통학환경 조성을 위해 학교 앞 횡단보도 조명 개선을 제안드립니다.\n\n현재 일부 통학로는 해가 진 뒤 횡단보도와 보행자 대기 구역이 어두워 운전자와 어린이 모두 시야 확보가 어렵습니다. 현장 밝기와 차량 통행량을 확인해 조명을 보강하고, 필요하다면 바닥형 보행신호등이나 안전표지 설치도 함께 검토해 주시기 바랍니다.\n\n아이와 보호자가 안심하고 걸을 수 있는 통학로가 조성되도록 관련 부서의 현장 점검과 개선 계획을 요청드립니다. 정확한 검토를 위해 학교명과 횡단보도 위치는 제출 전에 추가하겠습니다.",
      resident: Object.freeze({
        en: Object.freeze({
          title: "Please brighten the school crosswalk at night",
          body: "The crosswalk in front of the school is too dark at night.\nPlease improve the lighting so children can cross safely.",
        }),
        vi: Object.freeze({
          title: "Xin làm sáng lối qua đường trước trường vào ban đêm",
          body: "Lối qua đường trước trường quá tối vào ban đêm.\nXin hãy cải thiện hệ thống chiếu sáng để trẻ em có thể qua đường an toàn.",
        }),
        th: Object.freeze({
          title: "กรุณาเพิ่มแสงทางม้าลายหน้าโรงเรียนตอนกลางคืน",
          body: "ทางม้าลายหน้าโรงเรียนมืดเกินไปในเวลากลางคืน\nกรุณาปรับปรุงแสงสว่างเพื่อให้เด็ก ๆ ข้ามถนนได้อย่างปลอดภัย",
        }),
        id: Object.freeze({
          title: "Terangi penyeberangan sekolah di malam hari",
          body: "Penyeberangan di depan sekolah terlalu gelap pada malam hari.\nMohon tingkatkan penerangannya agar anak-anak dapat menyeberang dengan aman.",
        }),
      }),
      revise: Object.freeze({
        en: Object.freeze({
          title: "Safer school route: better crosswalk lighting",
          body: "After sunset the school-front crosswalk is hard to see.\nPlease reinforce lighting so children and caregivers can walk safely.",
        }),
        vi: Object.freeze({
          title: "Lối đến trường an toàn hơn: cải thiện đèn đường",
          body: "Sau hoàng hôn, lối qua đường trước trường khó nhìn thấy.\nXin tăng cường chiếu sáng để trẻ em và người đưa đón đi bộ an toàn.",
        }),
        th: Object.freeze({
          title: "เส้นทางโรงเรียนที่ปลอดภัยขึ้น: ปรับปรุงไฟทางม้าลาย",
          body: "หลังพระอาทิตย์ตก ทางม้าลายหน้าโรงเรียนมองเห็นได้ยาก\nกรุณาเสริมแสงสว่างเพื่อให้เด็กและผู้ปกครองเดินได้อย่างปลอดภัย",
        }),
        id: Object.freeze({
          title: "Rute sekolah lebih aman: penerangan penyeberangan",
          body: "Setelah matahari terbenam, penyeberangan di depan sekolah sulit dilihat.\nMohon perkuat penerangan agar anak dan pendamping dapat berjalan dengan aman.",
        }),
      }),
    }),
    "complaint-ai-assist": Object.freeze({
      actionId: "litter_ai_assist",
      titleSelector: "#board-write-title",
      contentSelector: "#board-write-content",
      koreanTitle: "[환경정비 요청] 공원 내 방치 쓰레기 수거 및 악취 해결 요청",
      koreanBody:
        "안녕하세요. 집 앞 공원에 무단 투기된 쓰레기가 다량 방치되어 있어 심한 악취와 미관 훼손이 발생하고 있습니다. 주민들이 안심하고 공원을 이용할 수 있도록 현장 확인 후 쓰레기 수거와 주변 환경 정비를 요청드립니다. 정확한 처리를 위해 공원 이름이나 위치를 제출 전에 추가해 주세요.",
      resident: Object.freeze({
        en: Object.freeze({
          title: "Please clean dumped trash in the park near my home",
          body: "There is too much dumped trash in the park near my home and it smells bad.\nPlease clean it up soon so residents can use the park safely.",
        }),
        vi: Object.freeze({
          title: "Xin dọn rác bị đổ bừa bãi ở công viên gần nhà",
          body: "Công viên gần nhà tôi có quá nhiều rác bị đổ bừa bãi và mùi hôi rất nặng.\nXin hãy dọn sớm để cư dân yên tâm sử dụng công viên.",
        }),
        th: Object.freeze({
          title: "กรุณาเก็บขยะทิ้งในสวนสาธารณะใกล้บ้าน",
          body: "สวนสาธารณะใกล้บ้านมีขยะทิ้งมากและมีกลิ่นเหม็น\nกรุณาเก็บกวาดโดยเร็วเพื่อให้ผู้อยู่อาศัยใช้สวนได้อย่างปลอดภัย",
        }),
        id: Object.freeze({
          title: "Mohon bersihkan sampah dibuang di taman dekat rumah",
          body: "Taman di dekat rumah saya penuh sampah yang dibuang sembarangan dan baunya menyengat.\nMohon segera dibersihkan agar warga bisa memakai taman dengan aman.",
        }),
      }),
      revise: Object.freeze({
        en: Object.freeze({
          title: "Park cleanup request: illegal dumping and odor",
          body: "Illegal dumping near the park entrance is creating a strong odor.\nPlease remove the trash and restore the area for residents.",
        }),
        vi: Object.freeze({
          title: "Yêu cầu dọn công viên: đổ rác trái phép và mùi hôi",
          body: "Rác đổ trái phép gần lối vào công viên gây mùi hôi nặng.\nXin thu gom rác và khôi phục khu vực cho cư dân.",
        }),
        th: Object.freeze({
          title: "คำขอทำความสะอาดสวน: ทิ้งขยะผิดกฎหมายและกลิ่นเหม็น",
          body: "การทิ้งขยะผิดกฎหมายใกล้ทางเข้าสวนทำให้มีกลิ่นแรง\nกรุณาเก็บขยะและฟื้นฟูพื้นที่เพื่อผู้อยู่อาศัย",
        }),
        id: Object.freeze({
          title: "Permintaan bersihkan taman: buang sampah liar dan bau",
          body: "Pembuangan sampah liar dekat pintu masuk taman menimbulkan bau kuat.\nMohon angkat sampah dan pulihkan area untuk warga.",
        }),
      }),
    }),
    "complaint-board-write": Object.freeze({
      actionId: "streetlight_report",
      titleSelector: "#board-write-title",
      contentSelector: "#board-write-content",
      koreanTitle: "[시설물 정비 요청] 가로등 고장 신고",
      koreanBody:
        "안녕하세요. 생활에 불편을 주는 가로등 고장을 신고합니다. 정확한 위치와 고장 상태를 확인할 수 있도록 아래 내용을 검토해 주세요.\n\n- 위치: [도로명 또는 주변 건물]\n- 고장 상태: [점등 불가 / 깜빡임 / 파손]\n- 발생 시각: [확인한 날짜와 시간]\n\n안전사고 예방을 위해 점검과 수리를 요청드립니다.",
      resident: Object.freeze({
        en: Object.freeze({
          title: "Broken streetlight report near my street",
          body: "A streetlight near my home is broken and the area is too dark at night.\nPlease inspect and repair it for safety.",
        }),
        vi: Object.freeze({
          title: "Báo cáo đèn đường hỏng gần đường nhà tôi",
          body: "Đèn đường gần nhà tôi bị hỏng và khu vực tối vào ban đêm.\nXin kiểm tra và sửa để đảm bảo an toàn.",
        }),
        th: Object.freeze({
          title: "แจ้งโคมไฟถนนเสียใกล้ถนนบ้าน",
          body: "โคมไฟถนนใกล้บ้านเสียและบริเวณมืดในตอนกลางคืน\nกรุณาตรวจสอบและซ่อมเพื่อความปลอดภัย",
        }),
        id: Object.freeze({
          title: "Laporan lampu jalan rusak di dekat rumah",
          body: "Lampu jalan dekat rumah saya rusak dan area menjadi gelap di malam hari.\nMohon diperiksa dan diperbaiki demi keselamatan.",
        }),
      }),
      revise: Object.freeze({
        en: Object.freeze({
          title: "Please fix the non-working streetlight",
          body: "The streetlight no longer turns on and pedestrians feel unsafe.\nPlease schedule a repair after checking the location.",
        }),
        vi: Object.freeze({
          title: "Xin sửa đèn đường không hoạt động",
          body: "Đèn đường không còn sáng và người đi bộ cảm thấy không an toàn.\nXin lên lịch sửa sau khi kiểm tra vị trí.",
        }),
        th: Object.freeze({
          title: "กรุณาซ่อมโคมไฟถนนที่ใช้งานไม่ได้",
          body: "โคมไฟถนนไม่ติดอีกต่อไป และคนเดินเท้าไม่รู้สึกปลอดภัย\nกรุณานัดซ่อมหลังจากตรวจสอบตำแหน่ง",
        }),
        id: Object.freeze({
          title: "Mohon perbaiki lampu jalan yang tidak menyala",
          body: "Lampu jalan tidak menyala lagi dan pejalan kaki merasa tidak aman.\nMohon jadwalkan perbaikan setelah lokasi dicek.",
        }),
      }),
    }),
  });

  function _isNonKoLocale() {
    return Boolean(
      window.CitizenI18n &&
        typeof window.CitizenI18n.getLocale === "function" &&
        window.CitizenI18n.getLocale() !== "ko"
    );
  }

  function _activeLocale() {
    return window.CitizenI18n && typeof window.CitizenI18n.getLocale === "function"
      ? window.CitizenI18n.getLocale()
      : "ko";
  }

  function _isWritingTitleStep(step) {
    if (!step || !step.typeQuery) return false;
    var sel = step.querySelector || step.cursorTarget || "";
    return (
      sel === "#board-write-title" ||
      sel === "#mayor-write-title" ||
      sel.indexOf("write-title") !== -1
    );
  }

  function _getDraftFixture(journeyId) {
    return journeyId && BILINGUAL_DRAFT_FIXTURES[journeyId]
      ? BILINGUAL_DRAFT_FIXTURES[journeyId]
      : null;
  }

  function _syncDraftStageAttr() {
    if (!_body) return;
    if (_draftStage.stage === DRAFT_STAGE_IDLE) {
      _body.removeAttribute("data-draft-stage");
    } else {
      _body.setAttribute("data-draft-stage", _draftStage.stage);
    }
  }

  function _clearWritingFormFields(titleSelector, contentSelector) {
    var demoEl = _getCanvasEl();
    if (!demoEl) return;
    var title = titleSelector ? demoEl.querySelector(titleSelector) : null;
    var content = contentSelector ? demoEl.querySelector(contentSelector) : null;
    if (title && "value" in title) {
      title.value = "";
      try {
        title.dispatchEvent(new Event("input", { bubbles: true }));
      } catch (_) { /* ignore */ }
    }
    if (content && "value" in content) {
      content.value = "";
      try {
        content.dispatchEvent(new Event("input", { bubbles: true }));
      } catch (_) { /* ignore */ }
    }
    var submit =
      demoEl.querySelector("#btn-mayor-submit") ||
      demoEl.querySelector("#btn-board-submit");
    if (submit) {
      submit.disabled = true;
      submit.setAttribute("aria-disabled", "true");
      if (submit.getAttribute("data-default-label")) {
        submit.textContent = submit.getAttribute("data-default-label");
      }
    }
  }

  function _removeDraftCards() {
    if (!_chatThread) return;
    var nodes = _chatThread.querySelectorAll(
      ".chat-msg--bilingual-draft, [data-bilingual-draft-card]"
    );
    for (var i = nodes.length - 1; i >= 0; i--) {
      if (nodes[i] && nodes[i].parentNode) {
        nodes[i].parentNode.removeChild(nodes[i]);
      }
    }
    _draftStage.cardEl = null;
  }

  function _resetDraftStageState(options) {
    options = options || {};
    _draftStage.generation += 1;
    var titleSel = _draftStage.titleSelector;
    var contentSel = _draftStage.contentSelector;
    if (options.clearForm !== false && (titleSel || contentSel)) {
      _clearWritingFormFields(titleSel, contentSel);
    }
    _removeDraftCards();
    _draftStage.stage = DRAFT_STAGE_IDLE;
    _draftStage.locale = null;
    _draftStage.journeyId = null;
    _draftStage.actionId = null;
    _draftStage.residentTitle = "";
    _draftStage.residentBody = "";
    _draftStage.koreanTitle = "";
    _draftStage.koreanBody = "";
    _draftStage.titleSelector = "";
    _draftStage.contentSelector = "";
    _draftStage.resumeStepIndex = -1;
    _draftStage.revisionIndex = 0;
    _syncDraftStageAttr();
  }

  function _readResidentDraftFields() {
    if (!_draftStage.cardEl) return;
    var titleInput = _draftStage.cardEl.querySelector(
      '[data-draft-field="resident-title"]'
    );
    var bodyInput = _draftStage.cardEl.querySelector(
      '[data-draft-field="resident-body"]'
    );
    if (titleInput && typeof titleInput.value === "string") {
      _draftStage.residentTitle = titleInput.value;
    }
    if (bodyInput && typeof bodyInput.value === "string") {
      _draftStage.residentBody = bodyInput.value;
    }
  }

  function _escAttr(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function _escHtmlText(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function _renderResidentDraftCard() {
    if (!_chatThread) return;
    _removeDraftCards();
    var gen = _draftStage.generation;
    var locale = _draftStage.locale || _activeLocale();
    var titleId = "bilingual-draft-title-" + gen;
    var bodyId = "bilingual-draft-body-" + gen;
    var messageEl = document.createElement("div");
    messageEl.className = "chat-msg chat-msg--ai chat-msg--bilingual-draft";
    messageEl.setAttribute("data-bilingual-draft-card", "stage1");
    messageEl.setAttribute("data-draft-role", "original-resident");
    messageEl.setAttribute("data-draft-stage", DRAFT_STAGE_RESIDENT);
    messageEl.innerHTML =
      '<div class="chat-avatar" aria-label="AI">A</div>' +
      '<div class="chat-bubble chat-bubble--ai chat-bilingual-draft">' +
        '<p class="chat-draft-label" data-draft-label="original-resident">' +
          _escHtmlText(_i18nT("draft.residentDraftLabel", "Your draft")) +
        "</p>" +
        '<p class="chat-bilingual-draft__hint" data-draft-hint="stage1">' +
          _escHtmlText(
            _i18nT(
              "draft.stage1Explain",
              "Please check whether this draft matches what you mean. Nothing has been submitted."
            )
          ) +
        "</p>" +
        '<div class="chat-bilingual-draft__fields">' +
          '<div class="chat-bilingual-draft__field">' +
            '<label for="' +
            titleId +
            '">' +
            _escHtmlText(_i18nT("draft.residentTitleLabel", "Title (your language)")) +
            "</label>" +
            '<input type="text" id="' +
            titleId +
            '" class="chat-bilingual-draft__input" data-draft-field="resident-title" maxlength="120" autocomplete="off" value="' +
            _escAttr(_draftStage.residentTitle) +
            '" />' +
          "</div>" +
          '<div class="chat-bilingual-draft__field">' +
            '<label for="' +
            bodyId +
            '">' +
            _escHtmlText(_i18nT("draft.residentBodyLabel", "Body (your language)")) +
            "</label>" +
            '<textarea id="' +
            bodyId +
            '" class="chat-bilingual-draft__textarea" data-draft-field="resident-body" rows="5" maxlength="2000">' +
            _escHtmlText(_draftStage.residentBody) +
            "</textarea>" +
          "</div>" +
        "</div>" +
        '<div class="chat-decision__actions chat-bilingual-draft__actions" data-draft-actions="stage1">' +
          '<button type="button" class="chat-decision__button chat-decision__button--secondary" data-draft-action="revise">' +
            _escHtmlText(_i18nT("action.reviseDraft", "Revise draft")) +
          "</button>" +
          '<button type="button" class="chat-decision__button chat-decision__button--primary" data-draft-action="confirm-content">' +
            _escHtmlText(_i18nT("action.confirmContent", "Yes, the meaning is correct")) +
          "</button>" +
        "</div>" +
        '<p class="chat-bilingual-draft__safety" data-draft-safety="true">' +
          _escHtmlText(
            _i18nT(
              "safety.draftOnly",
              "This screen is for drafting only. No real submission is made."
            )
          ) +
        "</p>" +
      "</div>";
    _chatThread.appendChild(messageEl);
    _draftStage.cardEl = messageEl;
    _bindDraftCardActions(messageEl, gen);
    _scrollChatThreadToLatest(messageEl.querySelector(".chat-bilingual-draft__actions") || messageEl);
    var titleInput = messageEl.querySelector("#" + titleId);
    _focusEditableOnDesktopOnly(titleInput);
  }

  function _renderKoreanDraftCard() {
    if (!_chatThread) return;
    _removeDraftCards();
    var gen = _draftStage.generation;
    var messageEl = document.createElement("div");
    messageEl.className = "chat-msg chat-msg--ai chat-msg--bilingual-draft";
    messageEl.setAttribute("data-bilingual-draft-card", "stage2");
    messageEl.setAttribute("data-draft-stage", DRAFT_STAGE_KOREAN);
    messageEl.innerHTML =
      '<div class="chat-avatar" aria-label="AI">A</div>' +
      '<div class="chat-bubble chat-bubble--ai chat-bilingual-draft chat-bilingual-draft--compare">' +
        '<p class="chat-bilingual-draft__hint" data-draft-hint="stage2">' +
          _escHtmlText(
            _i18nT(
              "draft.stage2Explain",
              "Compare your original draft with the Korean administrative draft. Nothing has been officially submitted."
            )
          ) +
        "</p>" +
        '<div class="chat-bilingual-draft__compare" data-draft-compare="true">' +
          '<section class="chat-bilingual-draft__panel" data-draft-role="original-resident">' +
            '<p class="chat-draft-label" data-draft-label="original-resident">' +
              _escHtmlText(
                _i18nT("draft.originalResidentMessage", "Original resident message")
              ) +
            "</p>" +
            '<p class="chat-bilingual-draft__panel-title" data-draft-original-title="true">' +
              _escHtmlText(_draftStage.residentTitle) +
            "</p>" +
            '<p class="chat-draft-body" data-draft-original-text="true">' +
              _escHtmlText(_draftStage.residentBody) +
            "</p>" +
          "</section>" +
          '<section class="chat-bilingual-draft__panel" data-draft-role="korean-administrative-draft">' +
            '<p class="chat-draft-label" data-draft-label="korean-administrative-draft">' +
              _escHtmlText(
                _i18nT("draft.koreanAdministrativeDraft", "Korean administrative draft")
              ) +
            "</p>" +
            '<p class="chat-bilingual-draft__assist" data-draft-assist="true">' +
              _escHtmlText(
                _i18nT(
                  "draft.translatedForDraft",
                  "Translation for drafting assistance"
                )
              ) +
            "</p>" +
            '<p class="chat-bilingual-draft__panel-title" data-draft-korean-title="true">' +
              _escHtmlText(_draftStage.koreanTitle) +
            "</p>" +
            '<p class="chat-draft-body" data-draft-korean-body="true">' +
              _escHtmlText(_draftStage.koreanBody) +
            "</p>" +
          "</section>" +
        "</div>" +
        '<div class="chat-decision__actions chat-bilingual-draft__actions" data-draft-actions="stage2">' +
          '<button type="button" class="chat-decision__button chat-decision__button--secondary" data-draft-action="back-edit">' +
            _escHtmlText(_i18nT("action.backEditDraft", "Back and edit")) +
          "</button>" +
          '<button type="button" class="chat-decision__button chat-decision__button--primary" data-draft-action="confirm-insert">' +
            _escHtmlText(
              _i18nT(
                "action.confirmInsertForm",
                "Insert Korean draft into the form"
              )
            ) +
          "</button>" +
        "</div>" +
        '<p class="chat-bilingual-draft__safety" data-draft-safety="true">' +
          _escHtmlText(
            _i18nT(
              "safety.noSubmission",
              "Only guidance is provided; no real complaint is submitted."
            )
          ) +
        "</p>" +
      "</div>";
    _chatThread.appendChild(messageEl);
    _draftStage.cardEl = messageEl;
    _bindDraftCardActions(messageEl, gen);
    _scrollChatThreadToLatest(messageEl.querySelector(".chat-bilingual-draft__actions") || messageEl);
  }

  function _bindDraftCardActions(cardEl, gen) {
    if (!cardEl) return;
    var buttons = cardEl.querySelectorAll("[data-draft-action]");
    for (var i = 0; i < buttons.length; i++) {
      (function (btn) {
        btn.addEventListener("click", function () {
          if (gen !== _draftStage.generation) return;
          var action = btn.getAttribute("data-draft-action");
          if (action === "confirm-content") {
            confirmResidentDraftContent();
          } else if (action === "revise") {
            reviseResidentDraft();
          } else if (action === "confirm-insert") {
            confirmKoreanDraftInsert();
          } else if (action === "back-edit") {
            backToResidentDraftEdit();
          }
        });
      })(buttons[i]);
    }
    var titleInput = cardEl.querySelector('[data-draft-field="resident-title"]');
    var bodyInput = cardEl.querySelector('[data-draft-field="resident-body"]');
    function onEdit() {
      if (gen !== _draftStage.generation) return;
      _readResidentDraftFields();
    }
    if (titleInput) titleInput.addEventListener("input", onEdit);
    if (bodyInput) bodyInput.addEventListener("input", onEdit);
  }

  function _disableDraftCardButtons(cardEl) {
    if (!cardEl) return;
    var buttons = cardEl.querySelectorAll("button[data-draft-action]");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].disabled = true;
    }
  }

  function _beginBilingualDraftHandoff(titleStepIndex) {
    var fixture = _getDraftFixture(_currentJourneyId);
    if (!fixture) return false;
    var locale = _activeLocale();
    if (locale === "ko") return false;
    var pack = fixture.resident[locale] || fixture.resident.en;
    if (!pack) return false;

    // Find the paired body-typing step; resume at the step after it.
    var bodyStepIndex = titleStepIndex + 1;
    var resumeAt = titleStepIndex + 2;
    var titleStep = _steps[titleStepIndex] || {};
    var bodyStep = _steps[bodyStepIndex] || {};
    var koreanTitle =
      (bodyStep && titleStep.typeQuery) || fixture.koreanTitle;
    if (titleStep.typeQuery) koreanTitle = titleStep.typeQuery;
    var koreanBody =
      bodyStep && bodyStep.typeContent ? bodyStep.typeContent : fixture.koreanBody;
    var titleSelector =
      titleStep.querySelector ||
      titleStep.cursorTarget ||
      fixture.titleSelector;
    var contentSelector =
      (bodyStep && bodyStep.contentSelector) ||
      (bodyStep && bodyStep.cursorTarget) ||
      fixture.contentSelector;

    _draftStage.generation += 1;
    _draftStage.stage = DRAFT_STAGE_RESIDENT;
    _draftStage.locale = locale;
    _draftStage.journeyId = _currentJourneyId;
    _draftStage.actionId = fixture.actionId || _currentJourneyId;
    _draftStage.residentTitle = pack.title;
    _draftStage.residentBody = pack.body;
    _draftStage.koreanTitle = koreanTitle;
    _draftStage.koreanBody = koreanBody;
    _draftStage.titleSelector = titleSelector;
    _draftStage.contentSelector = contentSelector;
    _draftStage.resumeStepIndex = resumeAt;
    _draftStage.revisionIndex = 0;
    _syncDraftStageAttr();

    // Ensure form remains empty until second confirmation.
    _clearWritingFormFields(titleSelector, contentSelector);

    // Narration + Stage 1 card (no Korean draft yet).
    _removeTempMessages();
    _appendChatMessage(
      "ai",
      _i18nT(
        "draft.stage1Intro",
        "I prepared a draft in your language first. Please review and edit it before any Korean administrative text is created."
      ),
      false
    );
    _renderResidentDraftCard();
    _setState(CHOREO_WAITING_RESIDENT_DRAFT);
    return true;
  }

  function reviseResidentDraft() {
    if (_draftStage.stage !== DRAFT_STAGE_RESIDENT) return;
    if (_state !== CHOREO_WAITING_RESIDENT_DRAFT) return;
    var fixture = _getDraftFixture(_draftStage.journeyId || _currentJourneyId);
    if (!fixture) return;
    var locale = _draftStage.locale || _activeLocale();
    var alt = fixture.revise && (fixture.revise[locale] || fixture.revise.en);
    var base = fixture.resident && (fixture.resident[locale] || fixture.resident.en);
    _draftStage.revisionIndex += 1;
    var pick = _draftStage.revisionIndex % 2 === 1 && alt ? alt : base;
    if (!pick) return;
    _draftStage.residentTitle = pick.title;
    _draftStage.residentBody = pick.body;
    // Stay in Stage 1; do not touch form or Korean draft.
    _renderResidentDraftCard();
    _setState(CHOREO_WAITING_RESIDENT_DRAFT);
  }

  function confirmResidentDraftContent() {
    if (_draftStage.stage !== DRAFT_STAGE_RESIDENT) return;
    if (_state !== CHOREO_WAITING_RESIDENT_DRAFT) return;
    var gen = _draftStage.generation;
    _readResidentDraftFields();
    _disableDraftCardButtons(_draftStage.cardEl);
    // Create Korean draft only after explicit Stage 1 confirmation.
    // Uses deterministic reviewed fixture (not a live translator).
    var fixture = _getDraftFixture(_draftStage.journeyId || _currentJourneyId);
    if (fixture) {
      if (!_draftStage.koreanTitle) _draftStage.koreanTitle = fixture.koreanTitle;
      if (!_draftStage.koreanBody) _draftStage.koreanBody = fixture.koreanBody;
    }
    _draftStage.stage = DRAFT_STAGE_KOREAN;
    _syncDraftStageAttr();
    // Form must still be empty.
    _clearWritingFormFields(_draftStage.titleSelector, _draftStage.contentSelector);
    if (gen !== _draftStage.generation) return;
    _renderKoreanDraftCard();
    _setState(CHOREO_WAITING_KOREAN_DRAFT);
  }

  function backToResidentDraftEdit() {
    if (_draftStage.stage !== DRAFT_STAGE_KOREAN) return;
    if (_state !== CHOREO_WAITING_KOREAN_DRAFT) return;
    _draftStage.stage = DRAFT_STAGE_RESIDENT;
    // Drop Korean exposure when returning to edit source.
    _syncDraftStageAttr();
    _clearWritingFormFields(_draftStage.titleSelector, _draftStage.contentSelector);
    _renderResidentDraftCard();
    _setState(CHOREO_WAITING_RESIDENT_DRAFT);
  }

  function confirmKoreanDraftInsert() {
    if (_draftStage.stage !== DRAFT_STAGE_KOREAN) return;
    if (_state !== CHOREO_WAITING_KOREAN_DRAFT) return;
    var gen = _draftStage.generation;
    var journeyGen = _journeyGeneration;
    _disableDraftCardButtons(_draftStage.cardEl);

    // Populate ONLY Korean title/body fields — no submit, no receipt, no navigation.
    var demoEl = _getCanvasEl();
    var title = demoEl && _draftStage.titleSelector
      ? demoEl.querySelector(_draftStage.titleSelector)
      : null;
    var content = demoEl && _draftStage.contentSelector
      ? demoEl.querySelector(_draftStage.contentSelector)
      : null;
    if (title && "value" in title) {
      title.value = _draftStage.koreanTitle || "";
      try {
        title.dispatchEvent(new Event("input", { bubbles: true }));
      } catch (_) { /* ignore */ }
    }
    if (content && "value" in content) {
      content.value = _draftStage.koreanBody || "";
      try {
        content.dispatchEvent(new Event("input", { bubbles: true }));
      } catch (_) { /* ignore */ }
      _scrollEditableToEnd(content);
    }

    // Keep submit disabled — still pre-submission.
    var submit =
      demoEl &&
      (demoEl.querySelector("#btn-mayor-submit") ||
        demoEl.querySelector("#btn-board-submit"));
    if (submit) {
      submit.disabled = true;
      submit.setAttribute("aria-disabled", "true");
    }

    _draftStage.stage = DRAFT_STAGE_FORM;
    _syncDraftStageAttr();
    _scheduleCanvasScroll(_revealWritingConfirmationInCanvas, 0);

    if (gen !== _draftStage.generation) return;
    if (journeyGen !== _journeyGeneration) return;

    // Keep compare card visible; append a short handoff note.
    _appendChatMessage(
      "ai",
      _i18nT(
        "draft.formPopulatedNotice",
        "I entered the Korean draft into the form on the left. Fields stay editable. Nothing has been submitted yet."
      ),
      false
    );

    // Resume journey at requiresConfirmation (submit remains a later explicit step).
    var resume = _draftStage.resumeStepIndex;
    _setState(STATE_RUNNING);
    if (typeof resume === "number" && resume >= 0) {
      _executeStep(resume);
    }
  }

  function getDraftStageState() {
    return {
      stage: _draftStage.stage,
      locale: _draftStage.locale,
      journeyId: _draftStage.journeyId,
      actionId: _draftStage.actionId,
      residentTitle: _draftStage.residentTitle,
      residentBody: _draftStage.residentBody,
      koreanTitle: _draftStage.koreanTitle,
      koreanBody: _draftStage.koreanBody,
    };
  }

  function _apartmentDeptSnapshot() {
    var snapshots = window.__BUKGU_OFFICIAL_SNAPSHOTS__;
    return snapshots && snapshots["apartment-dept"] ? snapshots["apartment-dept"] : null;
  }

  function _i18nT(key, fallback) {
    var i = window.CitizenI18n;
    if (i) {
      var v = i.t(key);
      if (v && v !== key) return v;
    }
    return fallback;
  }

  function _apartmentDeptFinalMessage() {
    var snapshot = _apartmentDeptSnapshot();
    if (!snapshot || !snapshot.page || !snapshot.representative_contact) {
      return _i18nT("apartment.missing", "공동주택과 공식 스냅샷을 불러오지 못했습니다.");
    }
    return _i18nT("apartment.final.prefix", "공동주택과 부서 대표전화는 ") + snapshot.representative_contact.phone +
      _i18nT("apartment.final.fax", ", FAX는 ") + snapshot.representative_contact.fax +
      _i18nT("apartment.final.suffix", "입니다. 왼쪽 조직 및 업무안내 표에서 전체 ") + snapshot.page.row_count +
      _i18nT("apartment.final.tail", "명의 업무별 연락처를 확인할 수 있습니다.");
  }

  function _apartmentDeptTableMessage() {
    var snapshot = _apartmentDeptSnapshot();
    var count = snapshot && snapshot.page ? snapshot.page.row_count : "전체";
    return _i18nT("apartment.table.prefix", "공식 조직 및 업무안내의 전체 ") + count +
      _i18nT("apartment.table.tail", "명 표를 열고 대표 연락처 행을 확인했습니다.");
  }

  // ═══════════════════════════════════════════════════════════════════
  // Journey map — typed deterministic step lists keyed by question
  // or journey ID. Each step:
  //   message        — chat message to display (required)
  //   routeId        — call navigateToRoute(routeId) (optional)
  //   targetId       — call getTargetElement(targetId) + highlight (optional)
  //   journeyState   — push J-DEPT-01 state via URL params (optional)
  //   journeyStateAfterClick — apply a journey state after the cursor click lands
  //   focusSearch    — true: focus + highlight the directory search input
  //   typeQuery      — string: set value of the directory search input
  //   typeContent    — string: type into the complaint body field
  //   submitSearch   — true: click the directory search button
  //   cursorTarget   — CSS selector: move cursor arrow to this element
  //   clickTarget    — CSS selector: show cursor + click ripple at target element
  //   routeIdAfterClick — navigate after the visible click lands
  //   thinkingText   — (new) temporary AI "thinking" indicator shown before message (optional)
  //   searchingText  — (new) second-phase "searching" indicator after thinking (optional)
  //   thinkingMs     — duration in ms for thinking/searching indicator (default 800)
   //   delayMs        — pause before next step; omitted/0 = terminal
   // ═══════════════════════════════════════════════════════════════════

   // Shared frozen journey objects — the question-text key and the MVP shell
   // action key MUST reference the exact same object so hasJourney()/start()
   // resolve identically regardless of which key the shell passes.
   var STREETLIGHT_REPORT_JOURNEY = Object.freeze({
     id: "complaint-board-write",
     description: "가로등 고장 신고 - 민원게시판 글쓰기 (MVP action)",
     steps: Object.freeze([
       Object.freeze({ message: "가로등 고장 신고를 도와드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 1000 }),
       Object.freeze({ message: "민원게시판으로 이동합니다.", routeId: "complaint-board", delayMs: 2000, thinkingText: "게시판으로 이동 중입니다...", thinkingMs: 700 }),
       Object.freeze({ message: "글쓰기 버튼을 눌러 새 신고 양식을 엽니다.", clickTarget: "#btn-board-write", routeIdAfterClick: "complaint-write", delayMs: 2200, thinkingText: "양식을 준비 중입니다...", thinkingMs: 700 }),
       Object.freeze({ message: "민원 제목을 입력합니다.", focusSearch: true, typeQuery: "[시설물 정비 요청] 가로등 고장 신고", cursorTarget: "#board-write-title", delayMs: 2500, thinkingText: "제목을 다듬는 중입니다...", thinkingMs: 650 }),
       Object.freeze({ message: "말씀하실 내용을 민원 문장으로 정리해 본문에 입력합니다.", typeContent: "안녕하세요. 생활에 불편을 주는 가로등 고장을 신고합니다. 정확한 위치와 고장 상태를 확인할 수 있도록 아래 내용을 검토해 주세요.\n\n- 위치: [도로명 또는 주변 건물]\n- 고장 상태: [점등 불가 / 깜빡임 / 파손]\n- 발생 시각: [확인한 날짜와 시간]\n\n안전사고 예방을 위해 점검과 수리를 요청드립니다.", cursorTarget: "#board-write-content", typeSpeedMs: 18, delayMs: 2600, thinkingText: "민원 문장을 작성하는 중입니다...", thinkingMs: 750, revealWritingConfirm: true }),
       Object.freeze({ message: "제목과 본문 초안을 입력했습니다. 대괄호 부분을 확인한 뒤 제출 여부를 선택해 주세요.", requiresConfirmation: true, delayMs: 1000 }),
        Object.freeze({ message: "민원 초안 작성을 마쳤습니다. 실제 제출은 북구청 공식 채널에서 직접 진행해 주세요." })
     ]),
   });

   var LITTER_AI_ASSIST_JOURNEY = Object.freeze({
     id: "complaint-ai-assist",
     description: "쓰레기 무단투기 신고 - AI 폼 자동 완성 보조",
     steps: Object.freeze([
       Object.freeze({ message: "쓰레기 무단투기 신고 작성을 도와드립니다.", thinkingText: "안내를 준비 중입니다...", thinkingMs: 500, delayMs: 1000 }),
       Object.freeze({ message: "민원게시판의 글쓰기 양식으로 이동합니다.", routeId: "complaint-board", delayMs: 2000, thinkingText: "게시판으로 이동 중입니다...", thinkingMs: 700 }),
       Object.freeze({ message: "직접 작성하시겠습니까, 아니면 AI가 초안 작성을 도와드릴까요?", requiresChoice: true, delayMs: 1000 }),
       Object.freeze({ message: "AI 도움을 선택하셨습니다. 글쓰기 버튼을 누르고 양식을 열겠습니다. 어떤 불편사항인지 편하게 말씀해 주세요.", clickTarget: "#btn-board-write", routeIdAfterClick: "complaint-write", delayMs: 2200, thinkingText: "글쓰기 양식을 여는 중입니다...", thinkingMs: 700 }),
       Object.freeze({ message: "집 앞 공원에 쓰레기가 너무 많고 냄새가 나요. 빨리 치워주세요.", isUserSimulated: true, delayMs: 2500 }),
       Object.freeze({ message: "말씀하신 내용을 바탕으로 민원 접수 양식에 맞게 초안을 작성합니다...", thinkingText: "내용을 분석하고 윤문하는 중입니다...", thinkingMs: 1500, delayMs: 1500 }),
       Object.freeze({ message: "먼저 민원 제목을 입력합니다.", focusSearch: true, typeQuery: "[환경정비 요청] 공원 내 방치 쓰레기 수거 및 악취 해결 요청", cursorTarget: "#board-write-title", delayMs: 2500, thinkingText: "핵심 내용을 제목으로 정리하는 중입니다...", thinkingMs: 650 }),
       Object.freeze({ message: "이어서 주민의 표현을 정중하고 구체적인 민원 문장으로 다듬어 본문에 입력합니다.", typeContent: "안녕하세요. 집 앞 공원에 무단 투기된 쓰레기가 다량 방치되어 있어 심한 악취와 미관 훼손이 발생하고 있습니다. 주민들이 안심하고 공원을 이용할 수 있도록 현장 확인 후 쓰레기 수거와 주변 환경 정비를 요청드립니다. 정확한 처리를 위해 공원 이름이나 위치를 제출 전에 추가해 주세요.", cursorTarget: "#board-write-content", typeSpeedMs: 18, delayMs: 2600, thinkingText: "민원 문장을 작성하는 중입니다...", thinkingMs: 750, revealWritingConfirm: true }),
       Object.freeze({ message: "작성된 초안을 확인한 뒤 오른쪽의 [검토했고, 제출하기]를 선택해 주세요. 확인 전에는 제출되지 않습니다.", requiresConfirmation: true, delayMs: 1000 }),
        Object.freeze({ message: "민원 초안 작성을 마쳤습니다. 실제 제출은 북구청 공식 채널에서 직접 진행해 주세요." })
     ]),
   });

   var MAYOR_MESSAGE_ASSIST_JOURNEY = Object.freeze({
     id: "mayor-message-assist",
     description: "구청장에게 바란다 - AI 구정 제안 작성 보조",
     steps: Object.freeze([
       Object.freeze({ message: "구청장에게 전할 제안을 함께 작성하겠습니다.", thinkingText: "제안 작성 화면을 준비 중입니다...", thinkingMs: 550, delayMs: 900 }),
       Object.freeze({ message: "홈 화면의 열린구청장실로 이동합니다.", clickTarget: "#btn-open-mayor-office", routeIdAfterClick: "mayor-office", delayMs: 2400, thinkingText: "열린구청장실 경로를 찾는 중입니다...", thinkingMs: 650 }),
       Object.freeze({ message: "구청장에게 바란다 제안 작성 화면을 엽니다.", clickTarget: "#btn-mayor-message", routeIdAfterClick: "mayor-complaint-write", delayMs: 2400, thinkingText: "제안 작성 양식을 여는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "아이들이 안심하고 걸을 수 있게 학교 앞 횡단보도 조명을 더 밝게 해주세요.", isUserSimulated: true, residentMessage: true, delayMs: 1800 }),
       Object.freeze({ message: "주민의 문제 제기와 기대 효과가 잘 드러나도록 구정 제안 문장으로 정리합니다.", thinkingText: "제안의 핵심과 기대 효과를 분석하는 중입니다...", thinkingMs: 900, delayMs: 1000 }),
       Object.freeze({ message: "먼저 제안 제목을 입력합니다.", typeQuery: "[안전한 통학로 제안] 학교 앞 횡단보도 조명 개선 요청", querySelector: "#mayor-write-title", cursorTarget: "#mayor-write-title", delayMs: 2100, thinkingText: "제목을 구체화하는 중입니다...", thinkingMs: 550 }),
       Object.freeze({ message: "현장 상황과 기대 효과를 담아 본문을 작성합니다.", typeContent: "안녕하세요. 북구의 안전한 통학환경 조성을 위해 학교 앞 횡단보도 조명 개선을 제안드립니다.\n\n현재 일부 통학로는 해가 진 뒤 횡단보도와 보행자 대기 구역이 어두워 운전자와 어린이 모두 시야 확보가 어렵습니다. 현장 밝기와 차량 통행량을 확인해 조명을 보강하고, 필요하다면 바닥형 보행신호등이나 안전표지 설치도 함께 검토해 주시기 바랍니다.\n\n아이와 보호자가 안심하고 걸을 수 있는 통학로가 조성되도록 관련 부서의 현장 점검과 개선 계획을 요청드립니다. 정확한 검토를 위해 학교명과 횡단보도 위치는 제출 전에 추가하겠습니다.", contentSelector: "#mayor-write-content", cursorTarget: "#mayor-write-content", typeSpeedMs: 15, delayMs: 2600, thinkingText: "설득력 있는 제안 문장을 작성하는 중입니다...", thinkingMs: 700, revealWritingConfirm: true }),
       Object.freeze({ message: "제안 초안을 완성했습니다. 위치 정보를 보완한 뒤 [검토했고, 제출하기]를 선택해 주세요.", requiresConfirmation: true, delayMs: 900 }),
       Object.freeze({ message: "구정 제안서 작성을 마쳤습니다. 공식 제출은 북구청 공식 채널에서 직접 확인하고 진행해 주세요." })
     ])
   });

   var JOURNEY_MAP = Object.freeze({
    "mayor_message_assist": MAYOR_MESSAGE_ASSIST_JOURNEY,
    "구청장에게 제안하고 싶어요": MAYOR_MESSAGE_ASSIST_JOURNEY,
    "불법 주정차 신고는 어디서 하나요?": Object.freeze({
      id: "complaint-illegal-parking",
      description: "불법 주정차 신고 경로 안내 (지도단속/안전신문고)",
      steps: Object.freeze([
        Object.freeze({ message: "불법 주정차 신고 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 1000 }),
        Object.freeze({ message: "지도단속 안내 화면으로 이동합니다.", routeId: "complaint-illegal-parking", delayMs: 2500, cursorTarget: ".bg-illegal-parking-card", thinkingText: "북구청 사이트에 접속 중입니다...", thinkingMs: 700 }),
        Object.freeze({ message: "안전신문고 등 공식 신고 채널을 안내합니다.", targetId: "complaint-illegal-parking-report", delayMs: 2800, clickTarget: ".bg-illegal-parking-card", thinkingText: "신고 채널 정보를 확인 중입니다...", searchingText: "안전신문고 사이트를 검색 중입니다...", thinkingMs: 800 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신고는 안전신문고(safetyreport.go.kr)에서 가능합니다." }),
      ]),
    }),
    // #927 MVP action aliases — same deterministic local clone as above.
    "illegal_parking": Object.freeze({
      id: "complaint-illegal-parking",
      description: "불법 주정차 신고 경로 안내 (지도단속/안전신문고, MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "불법 주정차 신고 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 1000 }),
        Object.freeze({ message: "지도단속 안내 화면으로 이동합니다.", routeId: "complaint-illegal-parking", delayMs: 2500, cursorTarget: ".bg-illegal-parking-card", thinkingText: "북구청 사이트에 접속 중입니다...", thinkingMs: 700 }),
        Object.freeze({ message: "안전신문고 등 공식 신고 채널을 안내합니다.", targetId: "complaint-illegal-parking-report", delayMs: 2800, clickTarget: ".bg-illegal-parking-card", thinkingText: "신고 채널 정보를 확인 중입니다...", searchingText: "안전신문고 사이트를 검색 중입니다...", thinkingMs: 800 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신고는 안전신문고(safetyreport.go.kr)에서 가능합니다." }),
      ]),
    }),
    // Owner-approved flagship flow: show the full menu, search, typing, and
    // grounded-result sequence instead of jumping directly to the answer.
    "공동주택 관련 문의는 어느 부서에 해야 하나요?": Object.freeze({
      id: "apartment-dept",
      description: "공동주택과 조직 및 업무안내",
      steps: Object.freeze([
        Object.freeze({ message: "공동주택 부서 정보를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 1000 }),
        Object.freeze({ message: "먼저 북구소개 메뉴를 열겠습니다.", journeyState: "J-DEPT-01:home", clickTarget: '[data-dept-action="open-menu"]', journeyStateAfterClick: "J-DEPT-01:menu", delayMs: 2400, thinkingText: "북구청 메뉴를 살펴보는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "구청안내에서 행정조직의 공동주택과를 찾습니다.", clickTarget: '[data-dept-action="go-directory"]', journeyStateAfterClick: "J-DEPT-01:directory", delayMs: 2500, thinkingText: "담당 부서 경로를 찾는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "검색창에 공동주택을 입력하겠습니다.", focusSearch: true, typeQuery: "공동주택", cursorTarget: ".bg-dept-search__input", delayMs: 2500, thinkingText: "부서 검색을 준비하는 중입니다...", thinkingMs: 550 }),
        Object.freeze({ message: "입력한 검색어로 담당 부서를 조회합니다.", submitSearch: true, clickTarget: ".bg-dept-search__btn", delayMs: 2500, searchingText: "공동주택 관련 부서를 검색 중입니다...", thinkingText: "검색 조건을 확인하는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "__APARTMENT_TABLE__", cursorTarget: '[data-representative-contact="true"]', delayMs: 2400, thinkingText: "공식 결과를 확인하는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "__APARTMENT_FINAL__" }),
      ]),
    }),
    "housing_department": Object.freeze({
      id: "apartment-dept",
      description: "공동주택과 조직 및 업무안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "공동주택 부서 정보를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 1000 }),
        Object.freeze({ message: "먼저 북구소개 메뉴를 열겠습니다.", journeyState: "J-DEPT-01:home", clickTarget: '[data-dept-action="open-menu"]', journeyStateAfterClick: "J-DEPT-01:menu", delayMs: 2400, thinkingText: "북구청 메뉴를 살펴보는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "구청안내에서 행정조직의 공동주택과를 찾습니다.", clickTarget: '[data-dept-action="go-directory"]', journeyStateAfterClick: "J-DEPT-01:directory", delayMs: 2500, thinkingText: "담당 부서 경로를 찾는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "검색창에 공동주택을 입력하겠습니다.", focusSearch: true, typeQuery: "공동주택", cursorTarget: ".bg-dept-search__input", delayMs: 2500, thinkingText: "부서 검색을 준비하는 중입니다...", thinkingMs: 550 }),
        Object.freeze({ message: "입력한 검색어로 담당 부서를 조회합니다.", submitSearch: true, clickTarget: ".bg-dept-search__btn", delayMs: 2500, searchingText: "공동주택 관련 부서를 검색 중입니다...", thinkingText: "검색 조건을 확인하는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "__APARTMENT_TABLE__", cursorTarget: '[data-representative-contact="true"]', delayMs: 2400, thinkingText: "공식 결과를 확인하는 중입니다...", thinkingMs: 650 }),
        Object.freeze({ message: "__APARTMENT_FINAL__" }),
      ]),
    }),
    "bulky_waste": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200, thinkingText: "대형폐기물 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000, thinkingText: "배출 방법 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다." }),
      ]),
    }),
    "침대 매트리스 버리고 싶어요": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200, thinkingText: "대형폐기물 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000, thinkingText: "배출 방법 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다." }),
      ]),
    }),
    "대형폐기물은 어떻게 버리나요?": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200, thinkingText: "대형폐기물 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000, thinkingText: "배출 방법 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다." }),
      ]),
    }),
    "가구 버리려면 어디서 신청해요?": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200, thinkingText: "대형폐기물 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000, thinkingText: "배출 방법 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다." }),
      ]),
    }),
    "매트리스 폐기 신청은 어디서 하나요?": Object.freeze({
      id: "bulky-waste-disposal-guidance",
      description: "대형폐기물 배출방법 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "대형폐기물 배출방법 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "대형폐기물 배출방법 페이지로 이동합니다.", routeId: "bulky-waste-disposal", delayMs: 1200, thinkingText: "대형폐기물 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "전화 신고와 여기로 신청 경로를 안내합니다.", targetId: "bulky-waste-guidance-card", delayMs: 2000, thinkingText: "배출 방법 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 신청은 여기로 앱 또는 북구청 홈페이지에서 가능합니다." }),
      ]),
    }),
"passport_guidance": Object.freeze({
      id: "passport-guidance",
      description: "여권민원 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "여권 발급 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "여권민원 안내 화면으로 이동합니다.", routeId: "passport-guidance", delayMs: 1200, thinkingText: "여권민원 안내 화면을 찾는 중입니다...", searchingText: "여권 발급 관련 정보를 검색 중입니다...", thinkingMs: 800 }),
        Object.freeze({ message: "여권민원 안내를 확인합니다. 여권 수수료표, 구비서류, 신청안내를 보실 수 있습니다. 실제 여권 신청은 북구청 민원실 방문 후 직접 진행해야 합니다.", targetId: "passport-guidance-card", delayMs: 2000, thinkingText: "여권 발급 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 여권 신청은 북구청 민원실 또는 정부24에서 가능합니다." }),
      ]),
    }),
    "여권 발급은 어디서 하나요?": Object.freeze({
      id: "passport-guidance",
      description: "여권민원 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "여권 발급 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "여권민원 안내 화면으로 이동합니다.", routeId: "passport-guidance", delayMs: 1200, thinkingText: "여권민원 안내 화면을 찾는 중입니다...", searchingText: "여권 발급 관련 정보를 검색 중입니다...", thinkingMs: 800 }),
        Object.freeze({ message: "여권민원 안내를 확인합니다. 여권 수수료표, 구비서류, 신청안내를 보실 수 있습니다. 실제 여권 신청은 북구청 민원실 방문 후 직접 진행해야 합니다.", targetId: "passport-guidance-card", delayMs: 2000, thinkingText: "여권 발급 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 여권 신청은 북구청 민원실 또는 정부24에서 가능합니다." }),
      ]),
    }),
    "여권 재발급은 어떻게 하나요?": Object.freeze({
      id: "passport-guidance",
      description: "여권민원 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "여권 발급 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "여권민원 안내 화면으로 이동합니다.", routeId: "passport-guidance", delayMs: 1200, thinkingText: "여권민원 안내 화면을 찾는 중입니다...", searchingText: "여권 발급 관련 정보를 검색 중입니다...", thinkingMs: 800 }),
        Object.freeze({ message: "여권민원 안내를 확인합니다. 여권 수수료표, 구비서류, 신청안내를 보실 수 있습니다. 실제 여권 신청은 북구청 민원실 방문 후 직접 진행해야 합니다.", targetId: "passport-guidance-card", delayMs: 2000, thinkingText: "여권 발급 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 여권 신청은 북구청 민원실 또는 정부24에서 가능합니다." }),
      ]),
    }),
    "unmanned_kiosk": Object.freeze({
      id: "unmanned-kiosk-guidance",
      description: "무인민원발급기 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "무인민원발급기 이용 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내 화면으로 이동합니다.", routeId: "unmanned-kiosk-guidance", delayMs: 1200, thinkingText: "무인민원발급기 정보 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.", targetId: "unmanned-kiosk-card", delayMs: 2000, thinkingText: "무인민원발급기 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다." }),
      ]),
    }),
    "무인민원발급기 어디 있어요?": Object.freeze({
      id: "unmanned-kiosk-guidance",
      description: "무인민원발급기 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "무인민원발급기 이용 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내 화면으로 이동합니다.", routeId: "unmanned-kiosk-guidance", delayMs: 1200, thinkingText: "무인민원발급기 정보 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.", targetId: "unmanned-kiosk-card", delayMs: 2000, thinkingText: "무인민원발급기 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다." }),
      ]),
    }),
    "무인민원발급기로 뭘 발급받을 수 있어요?": Object.freeze({
      id: "unmanned-kiosk-guidance",
      description: "무인민원발급기 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "무인민원발급기 이용 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내 화면으로 이동합니다.", routeId: "unmanned-kiosk-guidance", delayMs: 1200, thinkingText: "무인민원발급기 정보 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.", targetId: "unmanned-kiosk-card", delayMs: 2000, thinkingText: "무인민원발급기 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다." }),
      ]),
    }),
    "무인민원발급기 이용방법 알려줘": Object.freeze({
      id: "unmanned-kiosk-guidance",
      description: "무인민원발급기 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "무인민원발급기 이용 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내 화면으로 이동합니다.", routeId: "unmanned-kiosk-guidance", delayMs: 1200, thinkingText: "무인민원발급기 정보 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.", targetId: "unmanned-kiosk-card", delayMs: 2000, thinkingText: "무인민원발급기 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다." }),
      ]),
    }),
    "민원서류 발급받으려면 어디로 가야 해요?": Object.freeze({
      id: "unmanned-kiosk-guidance",
      description: "무인민원발급기 안내 (MVP action)",
      steps: Object.freeze([
        Object.freeze({ message: "무인민원발급기 이용 경로를 안내해 드립니다.", thinkingText: "잠시만 기다려 주세요...", thinkingMs: 600, delayMs: 600 }),
        Object.freeze({ message: "종합민원 메뉴를 확인합니다.", targetId: "nav-civil-service", delayMs: 1500, thinkingText: "메뉴를 탐색 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "종합민원 페이지로 이동합니다.", routeId: "civil-service", delayMs: 1200, thinkingText: "종합민원 페이지로 이동 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내 화면으로 이동합니다.", routeId: "unmanned-kiosk-guidance", delayMs: 1200, thinkingText: "무인민원발급기 정보 페이지를 불러오는 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "무인민원발급기 안내를 확인합니다. 설치장소, 발급종류, 이용방법을 보실 수 있습니다. 실제 서류 발급은 현장에서 본인인증 후 직접 진행해야 합니다.", targetId: "unmanned-kiosk-card", delayMs: 2000, thinkingText: "무인민원발급기 정보를 확인 중입니다...", thinkingMs: 600 }),
        Object.freeze({ message: "안내를 마쳤습니다. 실제 이용은 북구청 및 각 행정복지센터에 설치된 무인민원발급기에서 가능합니다." }),
      ]),
    }),
    // #927 / #1069 MVP action aliases — question text and action code share
    // the exact same frozen journey object so start() resolves identically.
    "가로등이 고장났어요. 신고할게요": STREETLIGHT_REPORT_JOURNEY,
    "streetlight_report": STREETLIGHT_REPORT_JOURNEY,
    // Owner-approved flagship flow: show the full menu, search, typing, and
    // grounded-result sequence instead of jumping directly to the answer.
    "쓰레기 무단투기 신고할래 (AI 도움)": LITTER_AI_ASSIST_JOURNEY,
    "litter_ai_assist": LITTER_AI_ASSIST_JOURNEY,
  });

  // ═══════════════════════════════════════════════════════════════════
  // Internal helpers
  // ═══════════════════════════════════════════════════════════════════

  function _appendChatMessage(role, text, isTemp, opts) {
    if (!_chatThread) return;
    var options = opts || {};
    var messageEl = document.createElement("div");
    messageEl.className = "chat-msg chat-msg--" + role;
    if (isTemp) {
      messageEl.className += " chat-msg--temp";
    }
    if (options.draftRole) {
      messageEl.setAttribute("data-draft-role", options.draftRole);
    }
    if (role === "ai") {
      var avatar = document.createElement("div");
      avatar.className = "chat-avatar";
      avatar.setAttribute("aria-label", "AI");
      avatar.textContent = "A";
      messageEl.appendChild(avatar);
    }
    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--" + role;
    if (options.label) {
      var labelEl = document.createElement("p");
      labelEl.className = "chat-draft-label";
      labelEl.setAttribute("data-draft-label", options.draftRole || "label");
      labelEl.textContent = options.label;
      bubble.appendChild(labelEl);
      var bodyEl = document.createElement("p");
      bodyEl.className = "chat-draft-body";
      bodyEl.textContent = text;
      bubble.appendChild(bodyEl);
    } else {
      bubble.textContent = text;
    }
    messageEl.appendChild(bubble);
    _chatThread.appendChild(messageEl);
    _chatThread.scrollTop = _chatThread.scrollHeight;
    return messageEl;
  }

  function _scrollEditableToEnd(input) {
    if (!input) return;
    try {
      // Textareas must pin the caret region so the last paragraph is readable
      // before confirmation is offered.
      if (typeof input.scrollHeight === "number") {
        input.scrollTop = input.scrollHeight;
      }
      if (typeof input.setSelectionRange === "function" && typeof input.value === "string") {
        var end = input.value.length;
        try {
          input.setSelectionRange(end, end);
        } catch (_) {
          /* some input types reject selection */
        }
      }
    } catch (_) {
      /* best-effort */
    }
  }

  function _appendKoreanDraftLabelNotice() {
    if (!window.CitizenI18n || window.CitizenI18n.getLocale() === "ko") return;
    var label = _i18nT(
      "draft.koreanAdministrativeDraft",
      "한국어 행정 초안"
    );
    var helper = _i18nT(
      "draft.translatedForDraft",
      "작성 보조를 위한 번역"
    );
    _appendChatMessage("ai", helper, false, {
      label: label,
      draftRole: "korean-administrative-draft",
    });
  }

  /** Remove all temporary chat messages (for cleaning up thinking/searching indicators) */
  function _removeTempMessages() {
    if (!_chatThread) return;
    var temps = _chatThread.querySelectorAll(".chat-msg--temp");
    for (var i = temps.length - 1; i >= 0; i--) {
      if (temps[i].parentNode) temps[i].parentNode.removeChild(temps[i]);
    }
  }

  /** Show a temporary thinking/searching indicator, then remove it after delayMs */
  function _showTempIndicator(text, delayMs) {
    var localized = (window.CitizenI18n && text) ? window.CitizenI18n.translateMessage(text) : text;
    var el = _appendChatMessage("ai", localized, true);
    if (el && delayMs > 0) {
      var timerId = window.setTimeout(function () {
        var idx = _tempIndicatorTimers.indexOf(timerId);
        if (idx !== -1) _tempIndicatorTimers.splice(idx, 1);
        if (el.parentNode) el.parentNode.removeChild(el);
      }, delayMs);
      _tempIndicatorTimers.push(timerId);
    }
    return el;
  }

  function _clearTempIndicatorTimers() {
    for (var i = 0; i < _tempIndicatorTimers.length; i++) {
      window.clearTimeout(_tempIndicatorTimers[i]);
    }
    _tempIndicatorTimers = [];
  }

  function _clearHighlights() {
    for (var i = 0; i < _highlightedEls.length; i++) {
      if (_highlightedEls[i]) {
        _highlightedEls[i].classList.remove(HIGHLIGHT_CLASS);
        _highlightedEls[i].classList.remove(TYPING_CLASS);
        _highlightedEls[i].classList.remove(SEARCH_BUSY_CLASS);
        if (_highlightedEls[i].removeAttribute) {
          _highlightedEls[i].removeAttribute("data-agent-typing");
        }
      }
    }
    _highlightedEls = [];
  }

  function _clearTimer() {
    if (_timer !== null) {
      window.clearTimeout(_timer);
      _timer = null;
    }
  }

  function _scheduleAux(callback, delayMs) {
    var timerId = window.setTimeout(function () {
      var timerIndex = _auxTimers.indexOf(timerId);
      if (timerIndex !== -1) _auxTimers.splice(timerIndex, 1);
      if (_state === STATE_RUNNING) callback();
    }, delayMs);
    _auxTimers.push(timerId);
    return timerId;
  }

  function _clearAuxTimers() {
    for (var i = 0; i < _auxTimers.length; i++) {
      window.clearTimeout(_auxTimers[i]);
    }
    _auxTimers = [];
  }

  function _scheduleTyping(callback, delayMs) {
    var timerId = window.setTimeout(function () {
      var timerIndex = _typingTimers.indexOf(timerId);
      if (timerIndex !== -1) _typingTimers.splice(timerIndex, 1);
      if (_state === STATE_RUNNING) callback();
    }, delayMs);
    _typingTimers.push(timerId);
    return timerId;
  }

  function _clearTypingTimers() {
    for (var i = 0; i < _typingTimers.length; i++) {
      window.clearTimeout(_typingTimers[i]);
    }
    _typingTimers = [];
  }

  /**
   * #1132: complete in-flight character typing immediately (decorative only).
   * Does not clear substantive route/click/submit timers.
   */
  function _flushTypingOperations() {
    _clearTypingTimers();
    for (var i = 0; i < _activeTypingOperations.length; i++) {
      var op = _activeTypingOperations[i];
      if (!op || !op.input) continue;
      op.cancelled = true;
      op.input.value = op.finalValue;
      op.input.removeAttribute("data-agent-typing");
      // Keep executor-typing as a static progress cue until next highlight clear.
      _dispatchInputEvent(op.input);
    }
    _activeTypingOperations = [];
  }

  function _readReducedMotionPreference() {
    if (
      window.CitizenFirstUseShell &&
      typeof window.CitizenFirstUseShell.prefersReducedMotion === "function"
    ) {
      return !!window.CitizenFirstUseShell.prefersReducedMotion();
    }
    return Boolean(
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  /**
   * #1132: prefer shell owner, then cached event value, then matchMedia.
   * Does not call .focus().
   */
  function _prefersReducedMotion() {
    if (
      window.CitizenFirstUseShell &&
      typeof window.CitizenFirstUseShell.prefersReducedMotion === "function"
    ) {
      return !!window.CitizenFirstUseShell.prefersReducedMotion();
    }
    return _reducedMotion;
  }

  /**
   * #1132 timing contract:
   * - decorative delays → 0
   * - step progression → 0–100ms task boundary (order preserved)
   * - confirmation never auto-approved
   * - normal motion keeps existing floors
   */
  function _stepProgressionDelayMs(requestedMs, visualActionDelay) {
    if (_prefersReducedMotion()) {
      var reducedBoundary = Math.max(0, visualActionDelay || 0);
      return Math.min(100, reducedBoundary);
    }
    return Math.max(requestedMs || 0, (visualActionDelay || 0) + 120, 320);
  }

  function _decorativeDelayMs(normalMs) {
    return _prefersReducedMotion() ? 0 : normalMs;
  }

  function _scrollBehavior() {
    return _prefersReducedMotion() ? "auto" : "smooth";
  }

  function _applyStaticTargetHighlight(selector) {
    if (!selector) return null;
    var demoEl = _getCanvasEl();
    var el = null;
    try {
      el = demoEl
        ? demoEl.querySelector(selector)
        : document.querySelector(selector);
    } catch (_) {
      el = null;
    }
    if (el) {
      el.classList.add(HIGHLIGHT_CLASS);
      _highlightedEls.push(el);
      try {
        el.scrollIntoView({ behavior: _scrollBehavior(), block: "center" });
      } catch (_) {
        /* noop */
      }
    }
    return el;
  }

  function _onMotionPreferenceChange(event) {
    var next =
      event && event.detail && typeof event.detail.reduced === "boolean"
        ? event.detail.reduced
        : _readReducedMotionPreference();
    _reducedMotion = !!next;
    // Flush decorative typing only — never cancel journey or substantive timers.
    if (_reducedMotion) {
      _flushTypingOperations();
    }
  }

  function _dispatchInputEvent(input) {
    if (!input || typeof input.dispatchEvent !== "function" || typeof Event !== "function") return;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function _clearCanvasScrollTimers() {
    for (var i = 0; i < _canvasScrollTimers.length; i++) {
      window.clearTimeout(_canvasScrollTimers[i]);
    }
    _canvasScrollTimers = [];
  }

  function _scheduleCanvasScroll(fn, delayMs) {
    var id = window.setTimeout(function () {
      var idx = _canvasScrollTimers.indexOf(id);
      if (idx !== -1) _canvasScrollTimers.splice(idx, 1);
      fn();
    }, delayMs || 0);
    _canvasScrollTimers.push(id);
    return id;
  }

  /**
   * #1142: after AI finishes writing, scroll ONLY #demo-canvas so the
   * resident confirmation block is visible. Does not touch chat or window.
   */
  function _revealWritingConfirmationInCanvas() {
    var canvas = _getCanvasEl();
    if (!canvas) return;
    // Pin body draft to the last paragraph before scrolling the consent block.
    var bodyField =
      canvas.querySelector("#mayor-write-content") ||
      canvas.querySelector("#board-write-content");
    _scrollEditableToEnd(bodyField);
    var target =
      canvas.querySelector(".bg-writing-consent") ||
      canvas.querySelector(".bg-writing-actions") ||
      canvas.querySelector("#btn-mayor-submit") ||
      canvas.querySelector("#btn-board-submit");
    if (!target) return;
    var reduced = _prefersReducedMotion();
    try {
      var cRect = canvas.getBoundingClientRect();
      var tRect = target.getBoundingClientRect();
      var pad = 28;
      var delta = 0;
      if (tRect.bottom > cRect.bottom - pad) {
        delta = tRect.bottom - cRect.bottom + pad;
      } else if (tRect.top < cRect.top + pad) {
        delta = tRect.top - cRect.top - pad;
      }
      if (!delta) return;
      if (reduced || typeof canvas.scrollTo !== "function") {
        canvas.scrollTop = canvas.scrollTop + delta;
      } else {
        canvas.scrollTo({ top: canvas.scrollTop + delta, behavior: "smooth" });
      }
    } catch (_) {
      /* scroll is best-effort */
    }
  }

  function _scrollChatThreadToLatest(actionEl) {
    if (!_chatThread) return;
    try {
      if (actionEl && typeof actionEl.scrollIntoView === "function") {
        actionEl.scrollIntoView({ block: "nearest", inline: "nearest" });
      }
      _chatThread.scrollTop = _chatThread.scrollHeight;
      if (typeof window.requestAnimationFrame === "function") {
        window.requestAnimationFrame(function () {
          if (!_chatThread) return;
          if (actionEl && typeof actionEl.scrollIntoView === "function") {
            actionEl.scrollIntoView({ block: "nearest", inline: "nearest" });
          }
          _chatThread.scrollTop = _chatThread.scrollHeight;
        });
      }
    } catch (_) {
      /* scroll is best-effort */
    }
  }

  function _typeIntoSearch(input, value, startDelayMs, requestedCharDelayMs, onComplete) {
    if (!input) return 0;
    var text = String(value || "");
    var reduced = _prefersReducedMotion();
    var charDelayMs = reduced
      ? 0
      : (typeof requestedCharDelayMs === "number" ? Math.max(8, requestedCharDelayMs) : 115);
    var startDelay = reduced ? 0 : startDelayMs;

    input.value = "";
    input.classList.add(TYPING_CLASS);
    input.classList.add(HIGHLIGHT_CLASS);
    input.setAttribute("data-agent-typing", "true");
    _highlightedEls.push(input);

    function _finishTyping() {
      input.removeAttribute("data-agent-typing");
      _scrollEditableToEnd(input);
      if (typeof onComplete === "function") {
        try { onComplete(); } catch (_) { /* noop */ }
      }
    }

    // Reduced motion: full string immediately; keep static typing highlight.
    if (!charDelayMs) {
      input.value = text;
      _dispatchInputEvent(input);
      _scrollEditableToEnd(input);
      _finishTyping();
      return 0;
    }

    var operation = { input: input, finalValue: text, cancelled: false };
    _activeTypingOperations.push(operation);

    for (var i = 0; i < text.length; i++) {
      (function (characterIndex) {
        _scheduleTyping(function () {
          if (operation.cancelled) return;
          input.value = text.slice(0, characterIndex + 1);
          _dispatchInputEvent(input);
          // Keep long body drafts pinned to the latest paragraph while typing.
          if (characterIndex === text.length - 1 || characterIndex % 12 === 0) {
            _scrollEditableToEnd(input);
          }
          if (characterIndex === text.length - 1) {
            var opIndex = _activeTypingOperations.indexOf(operation);
            if (opIndex !== -1) _activeTypingOperations.splice(opIndex, 1);
            _finishTyping();
          }
        }, startDelay + (characterIndex * charDelayMs));
      })(i);
    }

    return startDelay + (text.length * charDelayMs) + 160;
  }

  /**
   * Update internal choreography state and notify same-window listeners.
   * #1067: shell maps these events onto semantic data-journey-state.
   * Local CustomEvent only - no network or persistence.
   */
  function _setState(nextState) {
    _state = nextState;
    if (_body) {
      _body.setAttribute("data-choreography-state", nextState);
    }
    try {
      var detail = {
        state: nextState,
        journeyId: _currentJourneyId,
        stepIndex: _currentStep,
        totalSteps: _steps ? _steps.length : 0
      };
      if (typeof window !== "undefined" && typeof window.CustomEvent === "function") {
        window.dispatchEvent(new CustomEvent("citizen:choreography-statechange", {
          detail: detail
        }));
      }
    } catch (_) {
      /* CustomEvent unavailable - shell will not receive mapping events */
    }
  }

  // #927 / #1133: drive an existing local clone journey state through the
  // public canvas API. History writes are owned by CitizenFirstUseShell —
  // choreography only requests a bounded commit (no direct pushState).
  // Currently supports the approved J-DEPT-01 directory state, which renders
  // the canonical 공동주택과 organization/work snapshot.
  function _applyJourneyState(journeyState) {
    if (!journeyState || typeof journeyState !== "string") return;
    var parts = journeyState.split(":");
    var journey = parts[0];
    var state = parts[1] || "";
    if (journey === "J-DEPT-01" && (state === "directory" || state === "result" || state === "menu")) {
      try {
        if (typeof window !== "undefined" && typeof window.CustomEvent === "function") {
          window.dispatchEvent(new CustomEvent("citizen:history-commit-request", {
            detail: {
              routeId: "home",
              query: {
                journey: "J-DEPT-01",
                deptState: state
              }
            }
          }));
        }
      } catch (_) {
        /* CustomEvent unavailable — shell history commit is best-effort */
      }
      var canvas = window.CitizenActionDemoCanvas;
      if (canvas && canvas.navigateToRoute) {
        canvas.navigateToRoute("home");
      }
    }
  }

  function _getCanvasEl() {
    return document.getElementById("demo-canvas");
  }

  function _isMobileInteractionMode() {
    return Boolean(
      window.matchMedia &&
      window.matchMedia("(max-width: 767px)").matches
    );
  }

  function _isEditableElement(element) {
    return Boolean(
      element &&
      (
        element.matches("input, textarea, [contenteditable='true']") ||
        element.isContentEditable
      )
    );
  }

  function _blurActiveEditableForAutomatedMobileStep() {
    if (!_isMobileInteractionMode()) return;
    var active = document.activeElement;
    if (_isEditableElement(active) && typeof active.blur === "function") {
      active.blur();
    }
  }

  function _focusEditableOnDesktopOnly(element) {
    if (
      element &&
      !_isMobileInteractionMode() &&
      typeof element.focus === "function"
    ) {
      element.focus();
    }
  }

  function _executeStep(index) {
    if (_state !== STATE_RUNNING) return;
    if (index >= _steps.length) {
      // #1132: clear static progress cues so result does not look still-running.
      _clearHighlights();
      _removeTempMessages();
      if (window.CitizenActionDemoCanvas &&
          typeof window.CitizenActionDemoCanvas.hideCursor === "function") {
        window.CitizenActionDemoCanvas.hideCursor();
      }
      _setState(STATE_DONE);
      return;
    }

    _currentStep = index;
    var step = _steps[index];

    // #1152: non-Korean writing journeys open Stage 1 (resident-language draft)
    // before any Korean title/body is typed into the official-looking form.
    if (
      _isNonKoLocale() &&
      _isWritingTitleStep(step) &&
      _getDraftFixture(_currentJourneyId)
    ) {
      _blurActiveEditableForAutomatedMobileStep();
      _clearHighlights();
      if (_beginBilingualDraftHandoff(index)) {
        return;
      }
    }

    // On mobile, an automated step must never steal focus into an editable
    // field — the resident taps fields explicitly. Blur any active editable
    // before the action drives the canvas. Desktop is unaffected.
    _blurActiveEditableForAutomatedMobileStep();

    // Execute DOM action FIRST so left-pane visuals render before
    // the chat message appears — 박사님 choreography ordering requirement (#965).
    // Always clear prior static progress cues so only the current target shows.
    if (
      step.routeId ||
      step.routeIdAfterClick ||
      step.targetId ||
      step.journeyState ||
      step.focusSearch ||
      step.typeQuery ||
      step.typeContent ||
      step.submitSearch ||
      step.cursorTarget ||
      step.clickTarget
    ) {
      _clearHighlights();
    }

    if (step.routeId) {
      var canvas = window.CitizenActionDemoCanvas;
      if (canvas && canvas.navigateToRoute) {
        canvas.navigateToRoute(step.routeId);
      }
    } else if (step.targetId) {
      var canvas = window.CitizenActionDemoCanvas;
      if (canvas && canvas.getTargetElement) {
        var el = canvas.getTargetElement(step.targetId);
        if (el) {
          el.classList.add(HIGHLIGHT_CLASS);
          try {
            el.scrollIntoView({ behavior: _scrollBehavior(), block: "center" });
          } catch (_) { /* noop */ }
          _highlightedEls.push(el);
        }
      }
    } else if (step.journeyState) {
      _applyJourneyState(step.journeyState);
    }

    // #965: search-field interaction steps
    if (step.focusSearch) {
      var demoEl = _getCanvasEl();
      if (demoEl) {
        var input = demoEl.querySelector(".bg-dept-search__input");
        if (input) {
          // Desktop-only: focus the search field. On mobile the automated
          // journey must NOT steal focus into an editable.
          _focusEditableOnDesktopOnly(input);
          input.classList.add(HIGHLIGHT_CLASS);
          _highlightedEls.push(input);
        }
      }
    }

    // ── AI-style thinking/searching indicator ──────────────────────
    // If the step has a thinkingText, show a temporary indicator before
    // the permanent message, simulating AI "thinking" / "searching".
    var stepVisualActionDelay = 0;

    function _showPermanentAndSchedule() {
      // Remove any stale temp indicators
      _removeTempMessages();
      // Show chat message AFTER DOM actions so the left-pane state is visible
      // before the explanation text.
      var _displayText = step.message;
      var _draftOpts = null;
      if (window.CitizenI18n) {
        if (step.residentMessage) {
          _displayText = window.CitizenI18n.getResidentMessage();
          // Non-Korean: label the resident's original-language utterance.
          if (window.CitizenI18n.getLocale() !== "ko") {
            _draftOpts = {
              label: _i18nT(
                "draft.originalResidentMessage",
                "주민 원문 메시지"
              ),
              draftRole: "original-resident",
            };
          }
        } else if (step.message === "__APARTMENT_TABLE__") {
          _displayText = _apartmentDeptTableMessage();
        } else if (step.message === "__APARTMENT_FINAL__") {
          _displayText = _apartmentDeptFinalMessage();
        } else {
          _displayText = window.CitizenI18n.translateMessage(step.message);
        }
      }
      _appendChatMessage(
        step.isUserSimulated ? "user" : "ai",
        _displayText,
        false,
        _draftOpts
      );

      // Cursor, click, typing, and state changes play after the narration so the
      // resident can watch the agent act instead of seeing a finished state pop in.
      // #1132: reduced motion keeps static highlight + immediate commits (no
      // cursor interpolation / click ripple / long decorative waits).
      var visualActionDelay = 0;
      var reduced = _prefersReducedMotion();
      var cursorDelay = _decorativeDelayMs(120);
      var clickDelay = _decorativeDelayMs(180);
      // #1140: normal motion — wait for move(1140)+dwell(300) before advance;
      // route/journey commit ~340ms after click ripple (clickDelay + 1440 + 340).
      var cursorVisualFloorMs = 1440;
      var actionCommitDelay = reduced ? 0 : 1960;

      if (step.cursorTarget) {
        var cCanvas = window.CitizenActionDemoCanvas;
        if (cCanvas && cCanvas.hideCursor) cCanvas.hideCursor();
        if (reduced) {
          // Static progress cue — no cursor animation.
          _applyStaticTargetHighlight(step.cursorTarget);
        } else if (cCanvas && cCanvas.showCursorAt) {
          _scheduleAux(function () {
            cCanvas.showCursorAt(step.cursorTarget);
          }, cursorDelay);
          visualActionDelay = Math.max(visualActionDelay, cursorDelay + cursorVisualFloorMs);
        }
      }
      if (step.clickTarget) {
        if (reduced) {
          // Static highlight only; substantive route/journey commit below.
          _applyStaticTargetHighlight(step.clickTarget);
        } else {
          var kCanvas = window.CitizenActionDemoCanvas;
          if (kCanvas && kCanvas.clickAnimation) {
            _scheduleAux(function () {
              kCanvas.clickAnimation(step.clickTarget);
            }, clickDelay);
            visualActionDelay = Math.max(visualActionDelay, actionCommitDelay);
          }
        }
      }

      if (step.routeIdAfterClick) {
        if (reduced) {
          var routeCanvasNow = window.CitizenActionDemoCanvas;
          if (routeCanvasNow && routeCanvasNow.navigateToRoute) {
            routeCanvasNow.navigateToRoute(step.routeIdAfterClick);
          }
        } else {
          _scheduleAux(function () {
            var routeCanvas = window.CitizenActionDemoCanvas;
            if (routeCanvas && routeCanvas.navigateToRoute) {
              routeCanvas.navigateToRoute(step.routeIdAfterClick);
            }
          }, actionCommitDelay);
          visualActionDelay = Math.max(visualActionDelay, actionCommitDelay + 420);
        }
      }

      if (step.typeQuery) {
        var typeDemoEl = _getCanvasEl();
        var typeInput = typeDemoEl && typeDemoEl.querySelector(step.querySelector || ".bg-dept-search__input");
        var typingStartDelay = reduced ? 0 : (step.cursorTarget ? 1560 : 160);
        visualActionDelay = Math.max(
          visualActionDelay,
          _typeIntoSearch(typeInput, step.typeQuery, typingStartDelay)
        );
        // Desktop-only: focus the search field so the typing caret is
        // visible. On mobile the automated step must NOT pull focus.
        // #1132 helpers never focus under reduced-motion change paths either.
        _focusEditableOnDesktopOnly(typeInput);
      }

      if (step.typeContent) {
        var contentDemoEl = _getCanvasEl();
        var contentInput = contentDemoEl && contentDemoEl.querySelector(step.contentSelector || "#board-write-content");
        var contentTypingStartDelay = reduced ? 0 : (step.cursorTarget ? 1560 : 160);
        // Desktop-only: focus the body field so the typing caret is
        // visible. On mobile the automated step must NOT pull focus.
        _focusEditableOnDesktopOnly(contentInput);
        var revealAfterBody = !!step.revealWritingConfirm;
        visualActionDelay = Math.max(
          visualActionDelay,
          _typeIntoSearch(
            contentInput,
            step.typeContent,
            contentTypingStartDelay,
            step.typeSpeedMs,
            revealAfterBody
              ? function () {
                  // After body typing: pin textarea to last paragraph, show
                  // Korean-admin-draft label for non-ko, then reveal confirm.
                  _scrollEditableToEnd(contentInput);
                  _appendKoreanDraftLabelNotice();
                  _scheduleCanvasScroll(_revealWritingConfirmationInCanvas, reduced ? 0 : 80);
                }
              : null
          )
        );
      }

      if (step.journeyStateAfterClick) {
        if (reduced) {
          _applyJourneyState(step.journeyStateAfterClick);
        } else {
          _scheduleAux(function () {
            _applyJourneyState(step.journeyStateAfterClick);
          }, actionCommitDelay);
          visualActionDelay = Math.max(visualActionDelay, actionCommitDelay + 320);
        }
      }

      if (step.submitSearch) {
        var submitDemoEl = _getCanvasEl();
        var submitButton = submitDemoEl && submitDemoEl.querySelector(".bg-dept-search__btn");
        if (submitButton) {
          submitButton.classList.add(SEARCH_BUSY_CLASS);
          submitButton.classList.add(HIGHLIGHT_CLASS);
          _highlightedEls.push(submitButton);
          if (reduced) {
            // Substantive click immediately; no sweep animation wait.
            submitButton.click();
          } else {
            _scheduleAux(function () {
              submitButton.click();
            }, actionCommitDelay);
            visualActionDelay = Math.max(visualActionDelay, actionCommitDelay + 420);
          }
        }
      }
      stepVisualActionDelay = visualActionDelay;
    }

    // Schedule the next step (or termination) AFTER the permanent message is
    // shown. Kept separate from _showPermanentAndSchedule so it always runs,
    // regardless of which branch above displayed the message.
    function _advanceAfterStep() {
      if (step.requiresChoice) {
        // Confirm/choice boundary: never auto-approve; only shorten pre-prompt wait.
        var effectiveDelayChoice = _stepProgressionDelayMs(
          step.delayMs || 0,
          stepVisualActionDelay
        );
        _timer = window.setTimeout(function () {
          _timer = null;
          _setState("waiting_choice");
          _renderChoicePrompt(index);
        }, effectiveDelayChoice);
      } else if (step.requiresConfirmation) {
        var effectiveDelayConfirm = _stepProgressionDelayMs(
          step.delayMs || 0,
          stepVisualActionDelay
        );
        _timer = window.setTimeout(function () {
          _timer = null;
          _setState("waiting_confirmation");
          _renderConfirmationPrompt(index);
        }, effectiveDelayConfirm);
      } else if (typeof step.delayMs === "number" && step.delayMs > 0) {
        var effectiveDelay = _stepProgressionDelayMs(step.delayMs, stepVisualActionDelay);
        _timer = window.setTimeout(function () {
          _timer = null;
          _executeStep(index + 1);
        }, effectiveDelay);
      } else {
        // No delay → terminal step (done message)
        _clearHighlights();
        _removeTempMessages();
        if (window.CitizenActionDemoCanvas &&
            typeof window.CitizenActionDemoCanvas.hideCursor === "function") {
          window.CitizenActionDemoCanvas.hideCursor();
        }
        _setState(STATE_DONE);
      }
    }

    // #1132: reduced motion skips temporary thinking/searching indicators
    // (no looping dots, no duplicate live-region chatter). Permanent messages stay.
    if (step.thinkingText && !_prefersReducedMotion()) {
      // Show thinking/searching indicator, then replace with permanent message
      var thinkMs = (typeof step.thinkingMs === "number") ? step.thinkingMs : 800;
      var tempEl;
      if (step.searchingText) {
        // Two-phase: show thinking, then searching, then permanent
        tempEl = _showTempIndicator(step.thinkingText, thinkMs);
        _scheduleAux(function () {
          if (tempEl && tempEl.parentNode) tempEl.parentNode.removeChild(tempEl);
          var searchEl = _showTempIndicator(step.searchingText, thinkMs);
          _scheduleAux(function () {
            if (searchEl && searchEl.parentNode) searchEl.parentNode.removeChild(searchEl);
            _showPermanentAndSchedule();
            _advanceAfterStep();
          }, thinkMs);
        }, thinkMs);
      } else {
        // Single-phase: show thinking, then permanent
        tempEl = _showTempIndicator(step.thinkingText, thinkMs);
        _scheduleAux(function () {
          if (tempEl && tempEl.parentNode) tempEl.parentNode.removeChild(tempEl);
          _showPermanentAndSchedule();
          _advanceAfterStep();
        }, thinkMs);
      }
    } else {
      _showPermanentAndSchedule();
      _advanceAfterStep();
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  // Public API
  // ═══════════════════════════════════════════════════════════════════

  /**
   * Start a choreography for the given journey key.
   * @param {string} journeyKey — question text or journey ID
   * @returns {boolean} true if a matching journey was found and started
   */
  function start(journeyKey) {
    if (
      _state === STATE_RUNNING ||
      _state === "waiting_confirmation" ||
      _state === "waiting_choice" ||
      _state === CHOREO_WAITING_RESIDENT_DRAFT ||
      _state === CHOREO_WAITING_KOREAN_DRAFT ||
      _state === STATE_DONE ||
      _state === STATE_CANCELLED
    ) {
      cancel();
    }

    var entry = JOURNEY_MAP[journeyKey];
    if (!entry) return false;

    _journeyGeneration += 1;
    _resetDraftStageState({ clearForm: true });
    _currentJourneyId = entry.id;
    _steps = entry.steps;
    _currentStep = -1;
    _setState(STATE_RUNNING);
    _executeStep(0);
    return true;
  }

  /** Cancel a running choreography. Safe to call in any state. */
  function cancel() {
    if (_state === STATE_IDLE && _draftStage.stage === DRAFT_STAGE_IDLE) return;
    _journeyGeneration += 1;
    _clearTimer();
    _clearAuxTimers();
    _clearTypingTimers();
    _clearTempIndicatorTimers();
    _clearCanvasScrollTimers();
    // Mark typing ops cancelled so late char timers (if any) are no-ops.
    for (var t = 0; t < _activeTypingOperations.length; t++) {
      if (_activeTypingOperations[t]) {
        _activeTypingOperations[t].cancelled = true;
      }
    }
    _activeTypingOperations = [];
    _removeTempMessages();
    _clearHighlights();
    // #1152: clear bilingual draft cards, stage state, and journey-populated fields.
    _resetDraftStageState({ clearForm: true });
    // Emit cancelled while journeyId/step still known, then clear.
    _setState(STATE_CANCELLED);
    _steps = [];
    _currentStep = -1;
    _currentJourneyId = null;
  }

  /** @returns {string} current state */
  function getState() {
    return _state;
  }

  /** @returns {string|null} current journey ID */
  function getCurrentJourneyId() {
    return _currentJourneyId;
  }

  /** @returns {boolean} true if a journey map exists for the key */
  function hasJourney(journeyKey) {
    return Boolean(JOURNEY_MAP[journeyKey]);
  }

  function _renderChoicePrompt(index) {
    if (!_chatThread) return;
    var i18n = window.CitizenI18n;
    var t = i18n ? function (k, f) { var v = i18n.t(k); return v && v !== k ? v : f; } : null;
    var promptText = t ? t("choice.prompt", "직접 작성하시겠습니까, 아니면 AI가 초안 작성을 도와드릴까요?") : "직접 작성하시겠습니까, 아니면 AI가 초안 작성을 도와드릴까요?";
    var writeText = t ? t("action.writeMyself", "직접 작성") : "직접 작성";
    var aiText = t ? t("action.chooseAi", "AI 도움 받기") : "AI 도움 받기";
    var messageEl = document.createElement("div");
    messageEl.className = "chat-msg chat-msg--ai chat-msg--decision";
    messageEl.innerHTML = '<div class="chat-avatar" aria-label="AI">A</div>' +
      '<div class="chat-bubble chat-bubble--ai chat-decision">' +
        '<span>' + promptText + '</span>' +
        '<div class="chat-decision__actions">' +
          '<button type="button" class="chat-decision__button chat-decision__button--secondary" onclick="window.CitizenFirstChoreography.cancel()">' + writeText + '</button>' +
          '<button type="button" class="chat-decision__button chat-decision__button--primary" onclick="window.CitizenFirstChoreography.handleChoice(' + index + ')">' + aiText + '</button>' +
        '</div>' +
      '</div>';
    _chatThread.appendChild(messageEl);
    _chatThread.scrollTop = _chatThread.scrollHeight;
  }

  function handleChoice(index) {
    _setState(STATE_RUNNING);
    _executeStep(index + 1);
  }

  function _renderConfirmationPrompt(index) {
    if (!_chatThread) return;
    var i18n = window.CitizenI18n;
    var t = i18n ? function (k, f) { var v = i18n.t(k); return v && v !== k ? v : f; } : null;
    var isMayorJourney = _currentJourneyId === "mayor-message-assist";
    var promptText = isMayorJourney
      ? (t ? t("confirm.mayor", "작성된 제안의 제목과 본문을 검토했습니다. 이 내용으로 구정 제안서를 최종 확인할까요?") : "작성된 제안의 제목과 본문을 검토했습니다. 이 내용으로 구정 제안서를 최종 확인할까요?")
      : (t ? t("confirm.generic", "작성된 제목과 본문을 검토했습니다. 확인 전에는 제출되지 않습니다. 이 내용으로 진행할까요?") : "작성된 제목과 본문을 검토했습니다. 확인 전에는 제출되지 않습니다. 이 내용으로 진행할까요?");
    var submitText = t ? t("action.confirmSubmit", "검토했고, 제출하기") : "검토했고, 제출하기";
    var editText = t ? t("action.edit", "수정할게요") : "수정할게요";
    var messageEl = document.createElement("div");
    messageEl.className = "chat-msg chat-msg--ai chat-msg--decision";
    messageEl.innerHTML = '<div class="chat-avatar" aria-label="AI">A</div>' +
      '<div class="chat-bubble chat-bubble--ai chat-decision">' +
        '<span>' + promptText + '</span>' +
        '<div class="chat-decision__actions">' +
          '<button type="button" class="chat-decision__button chat-decision__button--primary" onclick="window.CitizenFirstChoreography.confirmSubmission(' + index + ')">' + submitText + '</button>' +
          '<button type="button" class="chat-decision__button chat-decision__button--secondary" onclick="window.CitizenFirstChoreography.cancel()">' + editText + '</button>' +
        '</div>' +
      '</div>';
    _chatThread.appendChild(messageEl);
    // Keep left confirmation in view and ensure chat actions are not obscured.
    _scheduleCanvasScroll(_revealWritingConfirmationInCanvas, 0);
    var actions = messageEl.querySelector(".chat-decision__actions");
    _scrollChatThreadToLatest(actions || messageEl);
  }

  function confirmSubmission(index) {
    if (_state !== "waiting_confirmation" && _state !== STATE_RUNNING) {
      return;
    }
    var gen = _journeyGeneration;
    _setState(STATE_RUNNING);
    var isMayorJourney = _currentJourneyId === "mayor-message-assist";
    var demoEl = document.getElementById("demo-canvas");
    var titleSelector = isMayorJourney ? "#mayor-write-title" : "#board-write-title";
    var contentSelector = isMayorJourney ? "#mayor-write-content" : "#board-write-content";
    var submitSelector = isMayorJourney ? "#btn-mayor-submit" : "#btn-board-submit";
    var title = demoEl && demoEl.querySelector(titleSelector);
    var contentEl = demoEl && demoEl.querySelector(contentSelector);
    var submitButton = demoEl && demoEl.querySelector(submitSelector);
    var cCanvas = window.CitizenActionDemoCanvas;

    // Consume confirmation UI once — prevent double commit.
    if (_chatThread) {
      var decisionBtns = _chatThread.querySelectorAll(
        ".chat-msg--decision .chat-decision__button"
      );
      for (var bi = 0; bi < decisionBtns.length; bi++) {
        decisionBtns[bi].disabled = true;
      }
    }

    if (submitButton) {
      submitButton.disabled = false;
      submitButton.setAttribute("aria-disabled", "false");
      submitButton.textContent = "제출하는 중...";
      if (_prefersReducedMotion()) {
        submitButton.classList.add(HIGHLIGHT_CLASS);
        _highlightedEls.push(submitButton);
      }
    }

    function _commitAfterClickVisual() {
      // Stale after cancel / locale reset / newer start.
      if (gen !== _journeyGeneration) return;
      if (_state === STATE_CANCELLED || _state === STATE_IDLE) return;

      if (isMayorJourney) {
        if (cCanvas && cCanvas.navigateToRoute) {
          cCanvas.navigateToRoute("mayor-complaint-receipt");
        }
        _executeStep(index + 1);
        return;
      }

      // Simulate submission through the adapter
      if (window.CitizenContentAdapter) {
        var data = {
          title: title ? title.value : "가로등 고장 신고",
          content: contentEl ? contentEl.value : "가로등 고장을 신고합니다.",
          author: "주민"
        };

        window.CitizenContentAdapter.submitBoardPost(data).then(function() {
          if (gen !== _journeyGeneration) return;
          if (_state === STATE_CANCELLED || _state === STATE_IDLE) return;
          if (cCanvas && cCanvas.navigateToRoute) {
            cCanvas.navigateToRoute("complaint-review");
          }
          _executeStep(index + 1);
        });
      } else {
        _executeStep(index + 1);
      }
    }

    // #1142: wait for click visual completion before route commit (not a fixed under-wait).
    if (!_prefersReducedMotion() && cCanvas && cCanvas.clickAnimation) {
      var clickPromise = cCanvas.clickAnimation(submitSelector);
      if (clickPromise && typeof clickPromise.then === "function") {
        clickPromise.then(function () {
          window.setTimeout(_commitAfterClickVisual, CLICK_READ_MS);
        }, function () {
          _commitAfterClickVisual();
        });
        return;
      }
      // Fallback if Promise not returned.
      window.setTimeout(_commitAfterClickVisual, 1440 + CLICK_READ_MS);
      return;
    }

    _commitAfterClickVisual();
  }

  /** @returns {number} current step index (-1 if not started) */
  function getCurrentStepIndex() {
    return _currentStep;
  }

  /** @returns {number} total steps in the active journey (0 if none) */
  function getTotalSteps() {
    return _steps ? _steps.length : 0;
  }

  /** @returns {Array} copy of the action step descriptors */
  function getSteps() {
    return _steps ? _steps.slice() : [];
  }

  // #1132: cache motion preference; shell is canonical owner when available.
  _reducedMotion = _readReducedMotionPreference();
  if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
    window.addEventListener("citizen:motion-preferencechange", _onMotionPreferenceChange);
  }

  window.CitizenFirstChoreography = Object.freeze({
    start: start,
    cancel: cancel,
    getState: getState,
    getCurrentJourneyId: getCurrentJourneyId,
    hasJourney: hasJourney,
    confirmSubmission: confirmSubmission,
    handleChoice: handleChoice,
    getCurrentStepIndex: getCurrentStepIndex,
    getTotalSteps: getTotalSteps,
    getSteps: getSteps,
    // #1152 two-stage bilingual draft handoff
    confirmResidentDraftContent: confirmResidentDraftContent,
    confirmKoreanDraftInsert: confirmKoreanDraftInsert,
    reviseResidentDraft: reviseResidentDraft,
    backToResidentDraftEdit: backToResidentDraftEdit,
    getDraftStageState: getDraftStageState,
    states: Object.freeze({
      idle: STATE_IDLE,
      running: STATE_RUNNING,
      done: STATE_DONE,
      cancelled: STATE_CANCELLED,
      waiting_resident_draft: CHOREO_WAITING_RESIDENT_DRAFT,
      waiting_korean_draft: CHOREO_WAITING_KOREAN_DRAFT,
      waiting_confirmation: "waiting_confirmation",
      waiting_choice: "waiting_choice",
    }),
    draftStages: Object.freeze({
      idle: DRAFT_STAGE_IDLE,
      resident_draft_review: DRAFT_STAGE_RESIDENT,
      korean_draft_review: DRAFT_STAGE_KOREAN,
      form_populated: DRAFT_STAGE_FORM,
    }),
  });
})();
