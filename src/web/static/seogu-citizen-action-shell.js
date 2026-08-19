/*
 * seogu-citizen-action-shell.js
 * Seo-gu (서구) MVP resident-shell orchestration (#1343 Buk-gu parity slice).
 *
 * This is the Seo-gu-SPECIFIC orchestration layer. It reuses the SHARED,
 * site-parameterized machinery (MunicipalSiteSurfaceRegistry,
 * MunicipalCloneSurface, MunicipalResidentJourney, citizen-mvp-bridge) and the
 * Seo-gu site-data/config island (SeoguSiteSpecMetadata,
 * SeoguResidentJourneyRegistry). It contains NO Buk-gu facts, questions or
 * routes — those live in the config island. The Buk-gu canonical shell
 * STRUCTURE (CSS/layout) is reused via the linked stylesheets; only the
 * Seo-gu resident surface behaviour is implemented here.
 *
 * Behaviour contract:
 * - capture_needed with no committed route  -> honest "근거 자료 미확보" state,
 *   never navigates to a fabricated page, never fakes success.
 * - substitution / DIRECT_REUSE with a real route -> navigate + READ; if the
 *   required evidence marker is absent it fails grounded (no fabricated answer).
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

  // ── Generic EXTERNAL_OFFICIAL_HANDOFF runner (local-evidence-first) ────────
  // One config-driven data/action contract shared by S2/S7/S8. The shell never
  // branches per scenario — it reads journey.handoff (frozen in the registry
  // config island) and executes the same bounded flow:
  //   repository-controlled local evidence (navigate + bounded clone READ)
  //   → required-marker validation
  //   → explain verified vs unverified scope
  //   → FAIL-CLOSED evidence gate: the external official destination anchor is
  //     rendered ONLY when evidence.ok === true && missingMarkers.length === 0.
  //     On gate failure the journey stops with a bounded STOP row that exposes
  //     the configured stop boundary and renders NO external destination
  //     control (no anchor, no href, no auto-open/prefill/submit, no model
  //     fallback, no success semantics).
  //   → resident-activated official destination anchor (explicit, never auto)
  //   → STOP (no submission, no success semantics, no external request).
  // auto_open / auto_prefill / submit_capability are all false by contract.

  // Poll for bounded READ evidence on the handoff local-evidence route. Mirrors
  // MunicipalResidentJourney._waitForEvidence (same 25ms poll contract) so the
  // handoff flow reuses the proven evidence-wait semantics instead of racing a
  // raw iframe load event.
  function _waitForHandoffEvidence(route, timeoutMs) {
    return new Promise(function (resolve) {
      var deadline = Date.now() + (timeoutMs || 8000);
      function check() {
        var evidence = surface ? surface.readEvidence() : null;
        if (evidence && evidence.ok && evidence.route === route) {
          resolve(evidence);
          return;
        }
        if (Date.now() >= deadline) {
          resolve(evidence || null);
          return;
        }
        window.setTimeout(check, 25);
      }
      check();
    });
  }

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

  async function _runExternalOfficialHandoff(journey) {
    var handoff = journey.handoff || {};
    document.body.setAttribute("data-journey-state", "handoff_evidence_running");

    // 1. Navigate to the repository-controlled local evidence route (bounded,
    //    same-origin clone). No external request is made.
    var navigated = false;
    if (surface && handoff.local_evidence_route) {
      navigated = surface.navigate(handoff.local_evidence_route);
    }

    // 2. Bounded READ of the local evidence region (main.rc-main innerText),
    //    polled until the route's evidence is readable (same contract as the
    //    shared journey orchestrator).
    var evidence = null;
    if (navigated) {
      evidence = await _waitForHandoffEvidence(handoff.local_evidence_route);
    }
    latestEvidence = evidence && evidence.ok ? evidence : latestEvidence;

    // 3. Required-marker validation against the READ text.
    var evidenceText = evidence && evidence.ok ? String(evidence.text || "") : "";
    var missingMarkers = (handoff.required_markers || []).filter(function (m) {
      return evidenceText.indexOf(m) === -1;
    });

    // 4. Explain verified vs unverified scope (config-driven, grounded).
    _appendHandoffEvidenceRow(journey, handoff, evidence, missingMarkers);

    // 5. FAIL-CLOSED evidence gate. The external official handoff may be
    //    rendered ONLY after successful local evidence validation — exactly
    //    evidence.ok === true AND every required marker confirmed in the READ
    //    region. On gate success: explicit resident-activated official
    //    destination row, then STOP. On gate failure: the journey stops here
    //    with the evidence explanation + a bounded STOP row that exposes the
    //    configured stop boundary but renders NO external destination control
    //    (no anchor, no href, no auto-open/prefill/submit, no model fallback,
    //    no success/receipt semantics). No window.open / auto-navigation ever.
    var evidenceGatePassed =
      Boolean(evidence) && evidence.ok === true && missingMarkers.length === 0;
    if (evidenceGatePassed) {
      // 5a. Explicit resident-activated official handoff, then STOP.
      _appendHandoffDestinationRow(journey, handoff);
      document.body.setAttribute("data-journey-state", "safe_handoff");
      return;
    }

    // 5b. Fail-closed STOP with no actionable external destination.
    _appendHandoffBlockedRow(journey, handoff);
    document.body.setAttribute("data-journey-state", "handoff_evidence_failed");
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
  // ── Grounded guidance hierarchy transform ─────────────────────────────
  // For DIRECT_REUSE journeys, convert the raw evidence excerpt into a
  // concise, resident-useful guidance hierarchy instead of exposing the
  // long source/menu dump as the primary answer.
  function _buildGroundedGuidance(result, journey) {
    if (!result || !result.ok || !result.grounded) return null;
    if (!result.excerpt || typeof result.excerpt !== "string") return null;

    var excerpt = result.excerpt;
    var markers = (journey.required_markers || []);

    // Extract meaningful lines from the excerpt that contain markers
    var lines = excerpt.split(/\n/).filter(function (line) {
      var t = line.trim();
      return t.length > 0;
    });

    // Identify the primary department marker
    var deptMarker = markers.find(function (m) {
      return excerpt.indexOf(m) !== -1 && (m === "주택과" || m === "공동주택관리");
    }) || markers[0] || "";

    // Build concise hierarchy
    // Build concise hierarchy
    var guidance = [];
    // 1. Department context (most important for resident decision)
    if (deptMarker) {
      guidance.push("담당 부서: " + deptMarker);
    }

    // 2. Service context from markers
    var serviceMarkers = markers.filter(function (m) {
      return m !== deptMarker;
    });
    if (serviceMarkers.length > 0) {
      guidance.push("관련 서비스: " + serviceMarkers.join(", "));
    }

    // 3. Key evidence lines (up to 3 meaningful lines, excluding boilerplate and menu items)
    var keyLines = lines.filter(function (line) {
      var t = line.trim();
      // Skip the boilerplate prefix
      if (t.indexOf("왼쪽 저장소") === 0) return false;
      if (t.indexOf("확인한 내용") !== -1 && t.length < 30) return false;
      // Skip lines that look like menu items (contain dates, numbers, or navigation text)
      if (/\d{4}\/\d{2}\/\d{2}/.test(t)) return false; // Date patterns
      if (/^\d+$/.test(t)) return false; // Pure numbers
      if (t.length > 100) return false; // Very long lines (likely menu dumps)
      // Keep lines that contain actual information
      return t.length > 5;
    }).slice(0, 3);
    if (keyLines.length > 0) {
      guidance.push("");
      guidance.push("안내 내용:");
      keyLines.forEach(function (line) {
        guidance.push("• " + line.trim());
      });
    }

    // 4. Resident action hint (only if supported by evidence)
    guidance.push("");
    guidance.push("위 담당 부서에 문의하시면 공동주택 관련 처리를 안내받으실 수 있습니다.");

    return guidance.join("\n");
  }

  async function _answerQuestion(question) {
    latestJourneyResult = null;
    latestGeneralResult = null;

    var journey = null;
    if (window.SeoguResidentJourneyRegistry) {
      journey = window.SeoguResidentJourneyRegistry.match(question);
    }

    if (journey) {
      // EXTERNAL_OFFICIAL_HANDOFF journeys (신고 intake 등): local-evidence-first,
      // then explicit resident-activated official handoff, then STOP.
      // Never auto-open, never prefill, never present submission as completed.
      if (journey.handoff) {
        await _runExternalOfficialHandoff(journey);
        return;
      }
      // No committed route + capture needed → honest, no fake navigation.
      if (journey.capture_needed && !journey.entry_route) {
        document.body.setAttribute("data-journey-state", "capture_needed");
        _appendCaptureNeeded(journey);
        return;
      }
      if (!window.MunicipalResidentJourney || !surface) {
        document.body.setAttribute("data-journey-state", "failed");
        _appendMessage("ai", "안내 화면에서 근거를 확인하지 못해 답변하지 않습니다.");
        return;
      }
      document.body.setAttribute("data-journey-state", "running");
      var result = await window.MunicipalResidentJourney.run(journey, surface);
      latestJourneyResult = result;
      if (result && result.ok && result.grounded) {
        document.body.setAttribute("data-journey-state", "grounded");
        // #1351: Transform raw excerpt into concise guidance for housing journey
        var guidance = _buildGroundedGuidance(result, journey);
        var answerText = guidance || result.answer;
        _appendMessage("ai", answerText, result);
      } else {
        document.body.setAttribute("data-journey-state", "failed");
        _appendMessage(
          "ai",
          result && result.answer
            ? result.answer
            : "안내 화면에서 근거를 확인하지 못해 답변하지 않습니다.",
          result && result.failure_code ? { failure_code: result.failure_code } : null
        );
      }
      return;
    }

    // Explicit opt-in boundary: unmatched question never calls a model silently.
    document.body.setAttribute("data-journey-state", "general_model_offer");
    _appendGeneralOffer(question);
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

  function _handleQuestion(question) {
    if (!surface) return;
    _enterSplit();
    _appendMessage("user", question);
    input.value = "";
    input.disabled = true;
    send.disabled = true;
    Promise.resolve(_answerQuestion(question))
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
