/*
 * seogu-citizen-action-shell.js
 * Seo-gu (서구) MVP resident thin bootstrap/adapter (#1343/#1365).
 *
 * The shared MunicipalResidentInformationalController owns the canonical
 * informational resident progression. This file supplies only Seo-gu-specific
 * data/surface/rendering hooks plus non-informational fallback UI. It does NOT
 * own confirmation, YES→navigate progression, journey-result policy, or the
 * external-handoff state machine.
 *
 * Behaviour contract:
 * - capture_needed with no committed route  -> honest "근거 자료 미확보" state;
 * - repository-clone evidence/rendering remains Seo-gu-specific data/surface;
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

  // ── EXTERNAL_OFFICIAL_HANDOFF rendering hooks ────────────────────────────
  // The shared informational controller owns evidence navigation/READ, marker
  // validation, safe-handoff/blocked branching and STOP state progression.
  // Seo-gu keeps only municipality-specific rendering of the controller result.

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

    // Explicit resident-activated official destination. Rendered as a real
    // anchor the resident must click — never auto-opened, never prefilled,
    // never submitted on their behalf.
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

  // Fail-closed STOP row. Rendered ONLY when the local-evidence gate FAILS
  // (evidence.ok !== true OR missingMarkers.length > 0). Carries the configured
  // stop boundary for auditability but NO external destination control: no
  // anchor, no href, no destination URL/label/authority, no form/button, no
  // auto-open/prefill/submit, no success/receipt semantics.
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

  // ── Question handling ──────────────────────────────────────────────────────
  // ── Grounded guidance hierarchy transform (S1 housing only) ────────────
  // ONLY for the housing department journey does the shell replace the raw
  // excerpt dump with a concise, resident-useful department/item hierarchy.
  // Every other grounded journey keeps the READ-derived answer untouched
  // (non-S1 behaviour must not regress). No institution fact is hard-coded
  // here: labels come from the journey config markers that actually appear in
  // the READ excerpt, and the route provenance is rendered by _appendMessage.
  function _buildGroundedGuidance(result, journey) {
    if (!result || !result.ok || !result.grounded) return null;
    if (!journey || journey.journey_id !== "seogu_apartment_housing_dept") return null;
    if (!result.excerpt || typeof result.excerpt !== "string") return null;

    // Only markers already verified against the READ excerpt are grounded.
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

  async function _answerNonInformationalQuestion(question) {
    latestJourneyResult = null;
    latestGeneralResult = null;

    var journey = null;
    if (window.SeoguResidentJourneyRegistry) {
      journey = window.SeoguResidentJourneyRegistry.match(question);
    }

    // Informational route/handoff journeys are owned by the shared controller
    // and must never fall through to a site-local execution state machine.
    if (journey && (journey.entry_route || journey.handoff)) {
      throw new Error("informational journey bypassed shared controller");
    }

    if (journey && journey.capture_needed && !journey.entry_route) {
      document.body.setAttribute("data-journey-state", "capture_needed");
      _appendCaptureNeeded(journey);
      return;
    }

    // Explicit opt-in boundary: unmatched question never calls a model silently.
    if (!journey) {
      document.body.setAttribute("data-journey-state", "general_model_offer");
      _appendGeneralOffer(question);
      return;
    }

    // Any remaining unsupported registry state fails closed. Do not invent a
    // route or silently create a second site-specific journey path.
    document.body.setAttribute("data-journey-state", "failed");
    _appendMessage("ai", "안내 화면에서 근거를 확인하지 못해 답변하지 않습니다.");
  }

  // ── Canvas availability (canonical Buk-gu semantics, narrow glue) ────────
  // Mirrors citizen-first-use-shell.js setCanvasAvailability(): the shared
  // canvas CSS hides #demo-canvas[inert] (display:none), so the resident UI
  // only actually SEES the clone once inert is removed and aria-hidden=false.
  // Split/guidance => available; conversation/entry => restored to hidden/inert.
  // This is visibility/availability glue only — no state machine, no layout.
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

  // Reuse the Buk-gu shell CSS state machine (entry → split) WITHOUT pulling in
  // Buk-gu-specific choreography. Setting "split" reveals the clone canvas
  // (left) and docks the chat (right) — the parity layout the CTO wants.
  function _enterSplit() {
    if (document.body.getAttribute("data-first-use-state") !== "split") {
      document.body.setAttribute("data-first-use-state", "split");
    }
    // #1350: Reveal the mobile surface switch only after first supported
    // resident action enters split state. This preserves Buk-gu cold-entry
    // geometry (switch hidden at boot) and avoids the 57px height workaround.
    if (surfaceSwitch) {
      surfaceSwitch.removeAttribute("hidden");
    }
    // Split must make the institution canvas actually visible/available.
    _setCanvasAvailability(true);
  }

  // ── ONE SHARED INFORMATIONAL RESIDENT CONTROLLER (#1365) ───────────────────
  // Seo-gu is a THIN BOOTSTRAP/ADAPTER. The shared
  // MunicipalResidentInformationalController owns the canonical top-level
  // sequence: ANSWER → CONFIRM → (YES|NO) → NAVIGATE → execute lower-level
  // journey → RESULT/STOP. The controller composes MunicipalResidentConfirmGate
  // (which owns confirm UI + YES/NO decision + stale-confirm guard + double
  // action protection). Seo-gu supplies only surface-specific adapter hooks.
  // A chip click is NOT confirmation. answer + confirm are never collapsed.
  var seoguInfoController = window.MunicipalResidentInformationalController.createInformationalController({
    getThread: function () { return thread; },
    getInput: function () { return input; },
    displayName: function (question) {
      var j = window.SeoguResidentJourneyRegistry
        ? window.SeoguResidentJourneyRegistry.match(question)
        : null;
      if (j && j.chip && j.chip.label) return j.chip.label;
      return question;
    },
    setJourneyState: function (state) {
      // #1364 Lane B: while the complaint-writing choreography owns the
      // journey axis, the shared handoff execution/terminal projections must
      // not land on the DOM axis (STATE_OVERWRITE_AUDIT class B). This covers
      // both the terminal safe_handoff write and the transient
      // handoff_evidence_running write emitted by a refused re-activation.
      if (
        _complaintChoreographyActive &&
        (state === "safe_handoff" || state === "handoff_evidence_running")
      ) {
        return;
      }
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
      // Surface-only adapter work. The shared controller owns the YES lifecycle.
      _setCanvasAvailability(true);
      if (typeof window !== "undefined" && window.matchMedia &&
          window.matchMedia("(max-width: 767px)").matches) {
        document.body.setAttribute("data-mobile-surface", "guidance");
      }
    },
    setInteractionDisabled: function (disabled) {
      input.disabled = !!disabled;
      send.disabled = !!disabled;
    },
    focusInput: function () {
      if (input) input.focus();
    },
    prepareExecution: function () {
      latestJourneyResult = null;
      latestGeneralResult = null;
    },
    clearExecutionResult: function () {
      latestJourneyResult = null;
      latestGeneralResult = null;
    },
    navigate: function (route) {
      return surface ? surface.navigate(route) : false;
    },
    readEvidence: function () {
      return surface ? surface.readEvidence() : null;
    },
    setEvidence: function (evidence) {
      if (evidence && evidence.ok) latestEvidence = evidence;
    },
    runJourney: function (journey) {
      if (!window.MunicipalResidentJourney || !surface) return null;
      return window.MunicipalResidentJourney.run(journey, surface);
    },
    setJourneyResult: function (result) {
      latestJourneyResult = result;
    },
    renderGroundedResult: function (result, journey) {
      var guidance = _buildGroundedGuidance(result, journey);
      _appendMessage("ai", guidance || result.answer, result);
    },
    renderJourneyFailure: function (result) {
      _appendMessage(
        "ai",
        result && result.answer
          ? result.answer
          : "안내 화면에서 근거를 확인하지 못해 답변하지 않습니다.",
        result && result.failure_code ? { failure_code: result.failure_code } : null
      );
    },
    renderHandoffEvidence: function (journey, handoff, evidence, missingMarkers) {
      _appendHandoffEvidenceRow(journey, handoff, evidence, missingMarkers);
    },
    renderHandoffDestination: function (journey, handoff) {
      // #1364 Lane B: complaint-writing journeys (S3/S4). After the evidence
      // gate passes, render the app-owned complaint surface and start the
      // shared choreography — no external handoff destination is offered.
      if (_isComplaintWritingJourney(journey)) {
        _startComplaintWriting(journey, handoff);
        return;
      }
      _appendHandoffDestinationRow(journey, handoff);
    },
    renderHandoffBlocked: function (journey, handoff) {
      _appendHandoffBlockedRow(journey, handoff);
    },
    renderUnexpectedFailure: function () {
      latestJourneyResult = null;
      latestGeneralResult = null;
      _appendMessage("ai", "현재 AI 안내를 연결하지 못했습니다.");
    },
    onNo: function () {
      // Surface-only rollback after shared NO→ANSWER/STOP.
      _setCanvasAvailability(false);
    },
  });

  function _handleQuestion(question) {
    if (!surface) return;
    // Invalidate any previously rendered confirm-run so prior YES/NO controls
    // are stale (generation guard). Owned by the shared golden engine.
    seoguInfoController.invalidate();

    var journey = null;
    if (window.SeoguResidentJourneyRegistry) {
      journey = window.SeoguResidentJourneyRegistry.match(question);
    }

    _enterSplit();
    _appendMessage("user", question);
    input.value = "";

    // ── Canonical ONE SHARED INFORMATIONAL CONTROLLER sequence (#1365) ───────
    // chip → first answer → confirm-run (YES/NO) → YES = navigate → grounded
    // A chip click is NOT confirmation. The shared controller owns the
    // answer→confirm scheduling; Seo-gu supplies only renderAnswer callback.
    if (journey && (journey.entry_route || journey.handoff)) {
      seoguInfoController.startConfirmFlow({
        question: question,
        journey: journey,
        delay: 300,
        renderAnswer: function () {
          _appendMessage("ai", "질문을 확인했습니다. 왼쪽에 서구청 안내 화면을 준비했습니다.");
        },
      });
      return;
    }

    // capture_needed or unmatched: no informational confirmation/execution.
    // This branch is intentionally non-informational and never owns the
    // shared YES→navigate→result lifecycle.
    input.disabled = true;
    send.disabled = true;
    Promise.resolve(_answerNonInformationalQuestion(question))
      .catch(function () {
        latestJourneyResult = null;
        latestGeneralResult = null;
        document.body.setAttribute("data-journey-state", "failed");
        _appendMessage("ai", "현재 AI 안내를 연결하지 못했습니다.");
      })
      .finally(function () {
        input.disabled = false;
        send.disabled = false;
        input.focus();
      });
  }

  // ── Mobile surface switch (conversation / guidance) ───────────────────────
  function _wireMobileSwitch() {
    if (!surfaceSwitch) return;
    // #1350: Keep the switch [hidden] at cold entry. The shared CSS exposes it
    // only ≤767px AND only once the [hidden] attribute is removed. We defer
    // removal until the first supported resident action enters split state,
    // matching Buk-gu canonical boot geometry.
    var chat = document.getElementById("chat-shell");
    surfaceSwitch.querySelectorAll("[data-mobile-surface-tab]").forEach(function (tab) {
      tab.addEventListener("click", function () {
        var target = tab.getAttribute("data-mobile-surface-tab");
        var conv = target === "conversation";
        surfaceSwitch.querySelectorAll("[data-mobile-surface-tab]").forEach(function (t) {
          t.setAttribute("aria-pressed", String(t === tab));
        });
        // Drive the shared mobile-surface CSS contract (data-mobile-surface) and
        // the layout state machine (entry/split). No institution branching.
        document.body.setAttribute("data-mobile-surface", target);
        document.body.setAttribute("data-first-use-state", conv ? "entry" : "split");
        if (chat) chat.removeAttribute("hidden");
        if (canvas) canvas.removeAttribute("hidden");
        // Canonical canvas availability: guidance shows the clone (inert
        // removed, aria-hidden=false); conversation restores hidden/inert.
        _setCanvasAvailability(!conv);
      });
    });
  }

  // ── #1364 Lane B: complaint-writing helpers (S3/S4) ────────────────────────
  // These functions are Seo-gu-specific adapters that bridge the shared
  // informational controller (which owns the evidence gate) to the shared
  // choreography engine (which owns the complaint-board → write → draft →
  // pre-submit sequence). They do NOT own the gate, the choreography, or any
  // Buk-gu runtime behaviour.

  var _complaintChoreographyActive = false;

  function _isComplaintWritingJourney(journey) {
    if (!journey || !journey.action) return false;
    var t = journey.action.type || "";
    return t === "COMPLAINT_BOARD_WRITE" || t === "COMPLAINT_AI_ASSIST";
  }

  function _isComplaintEvidenceGate(handoff) {
    if (!handoff) return false;
    return handoff.action_kind === "COMPLAINT_EVIDENCE_GATE";
  }

  function _startComplaintWriting(journey, handoff) {
    if (!window.SeoguComplaintSurface) {
      _appendMessage("ai", "현재 민원 작성 화면을 연결하지 못했습니다.");
      return;
    }
    if (!window.CitizenFirstChoreography) {
      _appendMessage("ai", "현재 민원 작성 안내를 연결하지 못했습니다.");
      return;
    }
    if (_complaintChoreographyActive) {
      // Re-assert the owning complaint state: the refused re-activation's
      // shared handoff projections are suppressed by the setJourneyState
      // guard, so the axis must be restored here explicitly.
      document.body.setAttribute("data-journey-state", "complaint_write");
      _appendMessage("ai", "이미 민원 작성 안내가 진행 중입니다.");
      return;
    }

    var choreoKey = journey.action && journey.action.choreography_key;
    if (!choreoKey) {
      _appendMessage("ai", "현재 이 민원 유형의 작성 안내를 연결하지 못했습니다.");
      return;
    }
    if (!window.CitizenFirstChoreography.hasJourney(choreoKey)) {
      _appendMessage("ai", "현재 이 민원 유형의 작성 안내를 연결하지 못했습니다.");
      return;
    }

    var isS4 = journey.action.type === "COMPLAINT_AI_ASSIST";
    var scenarioLabel = isS4 ? "쓰레기 무단투기 신고" : "가로등 고장 신고";

    // Pre-complaint-write confirmation message — the resident knows they are
    // entering the drafting area and that evidence has been validated.
    _appendMessage(
      "ai",
      "서구청 공식 안내 화면에서 " + scenarioLabel + " 관련 정보를 확인했습니다. " +
        "왼쪽 화면에서 AI 보조 초안 작성을 시작하겠습니다. " +
        "작성 내용은 주민이 직접 확인한 뒤 서구청 공식 채널에서 진행해야 합니다.",
      {
        grounded: true,
        source_kind: "repository_clone",
        evidence_kind: "clone_dom",
        route: handoff.local_evidence_route || "",
        journey_id: journey.journey_id,
      }
    );

    _complaintChoreographyActive = true;
    document.body.setAttribute("data-journey-state", "complaint_write");

    try {
      window.SeoguComplaintSurface.navigateToRoute("complaint-board");
    } catch (_) {
      _complaintChoreographyActive = false;
      _appendMessage("ai", "현재 민원 작성 화면을 연결하지 못했습니다.");
      return;
    }

    var started = window.CitizenFirstChoreography.start(choreoKey);
    if (!started) {
      _complaintChoreographyActive = false;
      window.SeoguComplaintSurface.reset();
      _appendMessage("ai", "현재 민원 작성 안내를 연결하지 못했습니다.");
      document.body.setAttribute("data-journey-state", "failed");
      return;
    }
  }

  function _restoreCloneSurfaceAfterComplaint() {
    _complaintChoreographyActive = false;
    if (window.SeoguComplaintSurface) {
      window.SeoguComplaintSurface.reset();
    }
    if (window.CitizenFirstChoreography) {
      window.CitizenFirstChoreography.cancel();
    }
    if (surface) {
      surface.navigate("");
    }
    _setCanvasAvailability(true);
    _setEvidenceState(latestEvidence);
  }

  function _onChoreographyStateChange(event) {
    if (!event || !event.detail) return;
    var state = event.detail && event.detail.state;
    if (state === "done" || state === "cancelled") {
      _restoreCloneSurfaceAfterComplaint();
    }
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
    // Default mobile surface contract (conversation) — shared CSS uses this to
    // decide which surface is visible on ≤767px; harmless on desktop.
    document.body.setAttribute("data-mobile-surface", "conversation");

    // #1364 Lane B: listen for choreography termination so the app-owned
    // complaint surface is cleaned up and the clone iframe is restored.
    if (typeof window !== "undefined" && window.addEventListener) {
      window.addEventListener("citizen:choreography-statechange", _onChoreographyStateChange);
    }
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
    getLastJourneyResult: function () { return latestJourneyResult; },
    getLastGeneralResult: function () { return latestGeneralResult; },
    navigate: function (route) { return surface ? surface.navigate(route) : false; },
    getSurfaceState: function () { return document.body.getAttribute("data-surface-state") || ""; },
  });

  _boot();
})();
