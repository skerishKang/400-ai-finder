/*
 * seogu-citizen-action-shell.js
 * Seo-gu (서구) MVP resident-shell thin bootstrap (#1343 / #1365 / #1366).
 *
 * THIN ADAPTER / BOOTSTRAP LAYER:
 *
 * This file is purely site-specific configuration, copy, DOM wiring, and rendering
 * callbacks. It contains NO top-level resident state progression or handoff
 * state machine — the shared MunicipalResidentInformationalController owns the
 * canonical ANSWER → CONFIRM → (YES/NO) → NAVIGATE / RUNNING → RESULT / SAFE_HANDOFF / STOP
 * lifecycle.
 *
 * Behaviour contract:
 * - capture_needed with no committed route  -> honest "근거 자료 미확보" state,
 *   never navigates to a fabricated page, never fakes success.
 * - substitution / DIRECT_REUSE with a real route -> delegated to shared controller;
 *   if the required evidence marker is absent it fails grounded (no fabricated answer).
 * - unmatched question -> explicit opt-in general-model offer (never silent).
 */
(function () {
  "use strict";

  var SITE_ID = "seogu_gwangju";

  var frame = document.getElementById("seogu-clone-frame");
  var titleEl = document.getElementById("chat-title");
  var greetingEl = document.getElementById("chat-greeting");
  var hintEl = document.getElementById("composer-hint");
  var privacyEl = document.getElementById("chat-privacy-warning");
  var disclosureEl = document.getElementById("shell-disclosure");
  var canvasLoading = document.getElementById("demo-canvas-loading");
  var canvas = document.getElementById("demo-canvas");
  var thread = document.getElementById("chat-thread");
  var chipsEl = document.getElementById("chat-chips");
  var form = document.getElementById("chat-composer-form");
  var input = document.getElementById("chat-composer-input");
  var send = document.getElementById("chat-composer-send");
  var surfaceSwitch = document.getElementById("mobile-surface-switch");

  var surface = null;
  var siteConfig = null;
  var latestEvidence = null;
  var latestJourneyResult = null;
  var latestGeneralResult = null;

  // ── Site-data-ize the static shell copy from the Seo-gu metadata island ──
  function _applySiteCopy() {
    var meta = window.SeoguSiteSpecMetadata;
    if (!meta) return;
    var copy = meta.copy || {};
    if (titleEl && copy.chat_title) titleEl.textContent = copy.chat_title;
    if (greetingEl && copy.greeting) greetingEl.textContent = copy.greeting;
    if (hintEl && copy.composer_hint) hintEl.textContent = copy.composer_hint;
    if (privacyEl && copy.privacy_warning) privacyEl.textContent = copy.privacy_warning;
    if (disclosureEl && copy.disclosure) disclosureEl.textContent = copy.disclosure;
    if (canvasLoading && copy.canvas_loading) canvasLoading.textContent = copy.canvas_loading;
    document.title = copy.product_title || "서구청 AI 민원 네비게이터";
  }

  // ── Chat message rendering (mirrors municipal-ai-shell contract) ───────────
  function _appendMessage(kind, text, metadata) {
    var row = document.createElement("div");
    row.className = "chat-msg chat-msg--" + kind;
    var avatar = document.createElement("div");
    avatar.className = "chat-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = kind === "ai" ? "A" : "You";
    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--" + kind;
    bubble.textContent = String(text || "");
    row.appendChild(avatar);
    row.appendChild(bubble);

    if (metadata && metadata.grounded === true) {
      row.setAttribute("data-grounded", "true");
      row.setAttribute("data-source-kind", String(metadata.source_kind || ""));
      row.setAttribute("data-evidence-kind", String(metadata.evidence_kind || ""));
      row.setAttribute("data-evidence-route", String(metadata.route || ""));
      row.setAttribute("data-journey-id", String(metadata.journey_id || ""));
      var src = document.createElement("div");
      src.className = "message-source message-source--clone";
      src.setAttribute("data-grounded-source", "true");
      src.textContent = "근거 · 저장소 기반 기관 안내 · " + (metadata.route || "홈");
      row.appendChild(src);
    } else if (
      metadata &&
      metadata.grounded === false &&
      metadata.source_kind === "general_model" &&
      metadata.evidence_kind === "none" &&
      metadata.answer_scope === "general_model"
    ) {
      row.setAttribute("data-grounded", "false");
      row.setAttribute("data-source-kind", "general_model");
      row.setAttribute("data-evidence-kind", "none");
      row.setAttribute("data-answer-scope", "general_model");
      var gsrc = document.createElement("div");
      gsrc.className = "message-source message-source--general";
      gsrc.setAttribute("data-general-model-source", "true");
      gsrc.textContent = "근거 · 일반 AI 모델 · 기관 안내 화면 근거 아님";
      row.appendChild(gsrc);
    }
    thread.appendChild(row);
    thread.scrollTop = thread.scrollHeight;
    return row;
  }

  function _appendCaptureNeeded(journey) {
    var row = _appendMessage(
      "ai",
      "이 시나리오는 아직 서구청 안내 화면 근거 자료가 없어 안내할 수 없습니다. " +
        "(SOURCE_CAPTURE_NEEDED — 실제 화면 이동 없이 답변하지 않습니다.)"
    );
    row.setAttribute("data-journey-id", journey.journey_id);
    row.setAttribute("data-status", journey.status);
    row.setAttribute("data-capture-needed", "true");
    return row;
  }

  // ── Generic EXTERNAL_OFFICIAL_HANDOFF rendering callbacks ─────────────────
  // Site-specific DOM rendering for handoff evidence, destination, and blocked rows.
  // The shared controller owns the handoff execution, evidence validation, and STOP decisions.
  function _appendHandoffEvidenceRow(journey, handoff, evidence, missingMarkers) {
    var verified = Boolean(evidence && evidence.ok && missingMarkers.length === 0);
    var routeText = evidence && evidence.ok ? evidence.route : handoff.local_evidence_route || "";
    var head = verified
      ? "서구청 저장소 기반 안내 화면에서 다음 내용을 직접 확인했습니다. "
      : "서구청 저장소 기반 안내 화면에서 이 신고의 전용 접수 창구는 확인하지 못했습니다. ";
    var markerLine = (handoff.required_markers || []).length
      ? "\n확인 항목: " + Array.prototype.join.call(handoff.required_markers, ", ")
      : "";
    var missingLine = missingMarkers.length
      ? "\n확인하지 못한 항목: " + missingMarkers.join(", ")
      : "";
    var note = handoff.local_evidence_note ? "\n\n" + handoff.local_evidence_note : "";
    var row = _appendMessage(
      "ai",
      head + markerLine + missingLine + note,
      evidence && evidence.ok
        ? {
            grounded: true,
            source_kind: evidence.source_kind,
            evidence_kind: evidence.evidence_kind,
            route: evidence.route,
            journey_id: journey.journey_id,
          }
        : null
    );
    row.setAttribute("data-handoff-evidence", "true");
    row.setAttribute("data-handoff-evidence-verified", String(verified));
    row.setAttribute("data-handoff-local-evidence-route", String(routeText));
    return row;
  }

  function _appendHandoffDestinationRow(journey, handoff) {
    var row = document.createElement("div");
    row.className = "chat-msg chat-msg--ai";
    var avatar = document.createElement("div");
    avatar.className = "chat-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "A";
    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--ai";
    bubble.textContent =
      "이 신고의 실제 제출은 여기까지 안내합니다 (STOP boundary). " +
      "이 MVP는 제출을 대행하지 않으며, 아래 공식 채널에서 주민이 직접 진행해야 합니다.";
    row.appendChild(avatar);
    row.appendChild(bubble);

    var link = document.createElement("a");
    link.className = "external-handoff-link";
    link.href = handoff.destination_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.setAttribute("data-handoff-action", "explicit-open");
    link.textContent =
      (handoff.destination_label || "공식 채널") + "에서 직접 진행하기";
    row.appendChild(link);

    var authority = document.createElement("div");
    authority.className = "message-source message-source--handoff";
    authority.setAttribute("data-handoff-authority", "true");
    authority.textContent = "공식 채널 · " + (handoff.destination_authority || handoff.destination_label || "");
    row.appendChild(authority);

    row.setAttribute("data-safe-handoff", "true");
    row.setAttribute("data-journey-id", journey.journey_id);
    row.setAttribute("data-status", journey.status);
    row.setAttribute("data-handoff-action-kind", handoff.action_kind || "");
    row.setAttribute("data-handoff-destination-url", handoff.destination_url || "");
    row.setAttribute("data-handoff-destination-label", handoff.destination_label || "");
    row.setAttribute("data-handoff-destination-authority", handoff.destination_authority || "");
    row.setAttribute("data-handoff-claim-scope", handoff.claim_scope || "HANDOFF_ONLY");
    row.setAttribute("data-handoff-stop-boundary", handoff.stop_boundary_code || "");
    thread.appendChild(row);
    thread.scrollTop = thread.scrollHeight;
    return row;
  }

  function _appendHandoffBlockedRow(journey, handoff) {
    var row = document.createElement("div");
    row.className = "chat-msg chat-msg--ai";
    var avatar = document.createElement("div");
    avatar.className = "chat-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "A";
    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--ai";
    bubble.textContent =
      "이 신고의 전용 접수 창구를 로컬 안내 근거에서 확인하지 못해, " +
      "외부 공식 채널 안내를 제공하지 않고 여기서 안내를 종료합니다 (STOP). " +
      "이 MVP는 제출을 대행하지 않으며, 해당 기관 안내 화면을 직접 방문해 주세요.";
    row.appendChild(avatar);
    row.appendChild(bubble);

    row.setAttribute("data-handoff-blocked", "true");
    row.setAttribute("data-journey-id", journey.journey_id);
    row.setAttribute("data-status", journey.status);
    row.setAttribute("data-handoff-action-kind", handoff.action_kind || "");
    row.setAttribute("data-handoff-claim-scope", handoff.claim_scope || "HANDOFF_ONLY");
    row.setAttribute("data-handoff-stop-boundary", handoff.stop_boundary_code || "");
    thread.appendChild(row);
    thread.scrollTop = thread.scrollHeight;
    return row;
  }

  function _appendGeneralOffer(question) {
    var row = _appendMessage(
      "ai",
      "현재 지원되는 저장소 기반 기관 안내 근거에서는 이 질문의 답을 확인하지 못했습니다. " +
        "원하시면 기관 홈페이지 근거가 아닌 일반 AI 모델 답변을 별도로 볼 수 있습니다."
    );
    row.setAttribute("data-general-fallback-offer", "true");
    var button = document.createElement("button");
    button.type = "button";
    button.className = "general-model-offer";
    button.textContent = "일반 AI 답변 보기";
    button.setAttribute("data-general-model-action", "request");
    row.appendChild(button);

    button.addEventListener("click", function () {
      if (!window.CitizenMvpBridge || typeof window.CitizenMvpBridge.askGeneralModel !== "function") {
        button.disabled = true;
        _appendMessage("ai", "현재 일반 AI 답변을 연결하지 못했습니다.");
        return;
      }
      button.disabled = true;
      document.body.setAttribute("data-journey-state", "general_model_running");
      Promise.resolve(window.CitizenMvpBridge.askGeneralModel(question, { site_id: SITE_ID }))
        .then(function (result) {
          latestGeneralResult = result;
          var exact =
            result &&
            result.grounded === false &&
            result.source_kind === "general_model" &&
            result.evidence_kind === "none" &&
            result.answer_scope === "general_model";
          if (result && result.ok && exact) {
            document.body.setAttribute("data-journey-state", "general_model");
            _appendMessage("ai", result.answer, result);
          } else {
            document.body.setAttribute("data-journey-state", "general_model_failed");
            _appendMessage(
              "ai",
              result && typeof result.answer === "string" && result.answer.trim()
                ? result.answer
                : "현재 일반 AI 답변을 연결하지 못했습니다.",
              null
            );
          }
        })
        .catch(function () {
          latestGeneralResult = null;
          document.body.setAttribute("data-journey-state", "general_model_failed");
          _appendMessage("ai", "현재 일반 AI 답변을 연결하지 못했습니다.");
        });
    });
    return row;
  }

  function _setEvidenceState(evidence) {
    latestEvidence = evidence && typeof evidence === "object" ? evidence : null;
    if (canvasLoading) {
      if (latestEvidence && latestEvidence.ok) {
        canvasLoading.style.display = "none";
        canvasLoading.textContent = "";
      } else {
        canvasLoading.style.display = "";
        canvasLoading.textContent = "서구청 안내 화면을 준비하는 중…";
      }
    }
  }

  // ── Chip rendering from the Seo-gu config island ───────────────────────────
  function _renderChips() {
    if (!window.SeoguResidentJourneyRegistry || !chipsEl) return;
    var chips = window.SeoguResidentJourneyRegistry.chips();
    chipsEl.innerHTML = "";
    chips.forEach(function (chip) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chat-chip" + (chip.variant ? " chat-chip--" + chip.variant : "");
      btn.setAttribute("data-chip-question", chip.question);
      btn.setAttribute("data-journey-id", chip.journey_id);
      btn.setAttribute("data-status", chip.status);
      btn.setAttribute("title", chip.label);

      var icon = document.createElement("span");
      icon.className = "chat-chip__icon";
      icon.innerHTML =
        '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3">' +
        '<path d="' + (chip.icon || "") + '"/></svg>';
      var label = document.createElement("span");
      label.className = "chat-chip__label";
      label.textContent = chip.label;

      btn.appendChild(icon);
      btn.appendChild(label);
      btn.addEventListener("click", function () {
        _handleQuestion(chip.question);
      });
      chipsEl.appendChild(btn);
    });
  }

  // ── Grounded guidance hierarchy transform (S1 housing only) ────────────
  function _buildGroundedGuidance(result, journey) {
    if (!result || !result.ok || !result.grounded) return null;
    if (!journey || journey.journey_id !== "seogu_apartment_housing_dept") return null;
    if (!result.excerpt || typeof result.excerpt !== "string") return null;

    var grounded = (journey.excerpt_markers || []).filter(function (m) {
      return result.excerpt.indexOf(m) !== -1;
    });
    if (grounded.length === 0) return null;

    var guidance = [];
    guidance.push("담당 부서: " + grounded[0]);
    if (grounded.length > 1) {
      guidance.push("관련 항목: " + grounded.slice(1).join(", "));
    }

    return guidance.join("\n");
  }

  // ── Canvas availability (canonical Buk-gu semantics, narrow glue) ────────
  function _setCanvasAvailability(isAvailable) {
    if (!canvas) return;
    if (isAvailable) {
      canvas.removeAttribute("inert");
      canvas.setAttribute("aria-hidden", "false");
    } else {
      canvas.setAttribute("inert", "");
      canvas.setAttribute("aria-hidden", "true");
    }
  }

  function _enterSplit() {
    if (document.body.getAttribute("data-first-use-state") !== "split") {
      document.body.setAttribute("data-first-use-state", "split");
    }
    if (surfaceSwitch) {
      surfaceSwitch.removeAttribute("hidden");
    }
    _setCanvasAvailability(true);
  }

  // ── ONE SHARED INFORMATIONAL RESIDENT CONTROLLER (#1365/#1366) ─────────────
  // Seo-gu is a THIN BOOTSTRAP/ADAPTER. The shared
  // MunicipalResidentInformationalController owns the canonical top-level
  // sequence: ANSWER → CONFIRM → (YES|NO) → NAVIGATE → execute lower-level
  // journey → RESULT/STOP.
  var seoguInfoController = window.MunicipalResidentInformationalController.createInformationalController({
    getThread: function () { return thread; },
    getInput: function () { return input; },
    getSend: function () { return send; },
    getSurface: function () { return surface; },
    displayName: function (question) {
      var j = window.SeoguResidentJourneyRegistry
        ? window.SeoguResidentJourneyRegistry.match(question)
        : null;
      if (j && j.chip && j.chip.label) return j.chip.label;
      return question;
    },
    setJourneyState: function (state) {
      document.body.setAttribute("data-journey-state", state);
    },
    isMobileSurfaceMode: function () {
      try {
        return !!window.matchMedia && window.matchMedia("(max-width: 767px)").matches;
      } catch (_) {
        return false;
      }
    },
    onYesSurfacePrepare: function () {
      _setCanvasAvailability(true);
      if (typeof window !== "undefined" && window.matchMedia &&
          window.matchMedia("(max-width: 767px)").matches) {
        document.body.setAttribute("data-mobile-surface", "guidance");
      }
    },
    onNo: function () {
      _setCanvasAvailability(false);
    },
    renderHandoffEvidence: _appendHandoffEvidenceRow,
    renderHandoffDestination: _appendHandoffDestinationRow,
    renderHandoffBlocked: _appendHandoffBlockedRow,
    renderGroundedResult: function (result, journey) {
      latestJourneyResult = result;
      var guidance = _buildGroundedGuidance(result, journey);
      var answerText = guidance || result.answer;
      _appendMessage("ai", answerText, result);
    },
    renderGroundedFailure: function (result) {
      latestJourneyResult = result;
      _appendMessage(
        "ai",
        result && result.answer
          ? result.answer
          : "안내 화면에서 근거를 확인하지 못해 답변하지 않습니다.",
        result && result.failure_code ? { failure_code: result.failure_code } : null
      );
    },
    renderError: function () {
      latestJourneyResult = null;
      _appendMessage("ai", "현재 AI 안내를 연결하지 못했습니다.");
    },
    onEvidence: function (ev) {
      latestEvidence = ev;
    },
    onJourneyResult: function (res) {
      latestJourneyResult = res;
    },
  });

  function _handleQuestion(question) {
    if (!surface) return;
    seoguInfoController.invalidate();

    var journey = null;
    if (window.SeoguResidentJourneyRegistry) {
      journey = window.SeoguResidentJourneyRegistry.match(question);
    }

    _enterSplit();
    _appendMessage("user", question);
    input.value = "";

    // ── Canonical ONE SHARED INFORMATIONAL CONTROLLER sequence (#1365/#1366) ──
    // For informational journeys (S1, S2, S5, S6, S7, S8), the shared controller
    // owns the complete top-level sequence:
    //   ANSWER → CONFIRM → (YES/NO) → NAVIGATE / RUNNING → RESULT / SAFE_HANDOFF / STOP
    if (journey && (journey.entry_route || journey.handoff)) {
      seoguInfoController.startConfirmFlow({
        question: question,
        journey: journey,
        surface: surface,
        delay: 300,
        renderAnswer: function () {
          _appendMessage("ai", "질문을 확인했습니다. 왼쪽에 서구청 안내 화면을 준비했습니다.");
        },
      });
      return;
    }

    // capture_needed without route: honest capture needed state
    if (journey && journey.capture_needed && !journey.entry_route) {
      document.body.setAttribute("data-journey-state", "capture_needed");
      _appendCaptureNeeded(journey);
      return;
    }

    // Explicit opt-in boundary: unmatched question never calls a model silently
    document.body.setAttribute("data-journey-state", "general_model_offer");
    _appendGeneralOffer(question);
  }

  // ── Mobile surface switch (conversation / guidance) ───────────────────────
  function _wireMobileSwitch() {
    if (!surfaceSwitch) return;
    var chat = document.getElementById("chat-shell");
    surfaceSwitch.querySelectorAll("[data-mobile-surface-tab]").forEach(function (tab) {
      tab.addEventListener("click", function () {
        var target = tab.getAttribute("data-mobile-surface-tab");
        var conv = target === "conversation";
        surfaceSwitch.querySelectorAll("[data-mobile-surface-tab]").forEach(function (t) {
          t.setAttribute("aria-pressed", String(t === tab));
        });
        document.body.setAttribute("data-mobile-surface", target);
        document.body.setAttribute("data-first-use-state", conv ? "entry" : "split");
        if (chat) chat.removeAttribute("hidden");
        if (canvas) canvas.removeAttribute("hidden");
        _setCanvasAvailability(!conv);
      });
    });
  }

  // ── Boot ───────────────────────────────────────────────────────────────────
  function _boot() {
    _applySiteCopy();
    if (window.MunicipalSiteSurfaceRegistry) {
      var resolved = window.MunicipalSiteSurfaceRegistry.resolve(SITE_ID);
      if (resolved.ok) {
        siteConfig = resolved.config;
        document.body.setAttribute("data-surface-state", "ready");
        document.body.setAttribute("data-journey-state", "idle");
        surface = window.MunicipalCloneSurface.create({ iframe: frame, config: siteConfig });
        window.addEventListener("municipal-clone-evidence", function (event) {
          if (!event || !event.detail || event.detail.site_id !== SITE_ID) return;
          _setEvidenceState(event.detail);
        });
        if (!surface.navigate("")) {
          document.body.setAttribute("data-surface-state", "unavailable");
        }
      } else {
        document.body.setAttribute("data-surface-state", "unavailable");
      }
    } else {
      document.body.setAttribute("data-surface-state", "unavailable");
    }
    _renderChips();
    _wireMobileSwitch();
    document.body.setAttribute("data-mobile-surface", "conversation");
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (!surface) return;
    var question = String(input.value || "").trim();
    if (!question) return;
    _handleQuestion(question);
  });

  window.SeoguCitizenActionShell = Object.freeze({
    getSiteId: function () { return SITE_ID; },
    getEvidence: function () {
      if (!surface) return latestEvidence;
      latestEvidence = surface.readEvidence();
      return latestEvidence;
    },
    getLastJourneyResult: function () {
      return seoguInfoController.getLastJourneyResult() || latestJourneyResult;
    },
    getLastGeneralResult: function () { return latestGeneralResult; },
    navigate: function (route) { return surface ? surface.navigate(route) : false; },
    getSurfaceState: function () { return document.body.getAttribute("data-surface-state") || ""; },
  });

  _boot();
})();
