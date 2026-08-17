/* Generic institution clone + AI resident shell (#1333 / #1335 / #1337 / #1328). */
(function () {
  "use strict";

  var frame = document.getElementById("municipal-clone-frame");
  var title = document.getElementById("municipal-ai-title");
  var sourceState = document.getElementById("clone-source-state");
  var form = document.getElementById("municipal-chat-form");
  var input = document.getElementById("municipal-chat-input");
  var send = document.getElementById("municipal-chat-send");
  var thread = document.getElementById("municipal-chat-thread");
  var surface = null;
  var siteId = "";
  var config = null;
  var latestEvidence = null;
  var latestJourneyResult = null;
  var latestGeneralResult = null;

  function _appendMessage(kind, text, metadata) {
    var row = document.createElement("div");
    row.className = "message message--" + kind;
    var stack = document.createElement("div");
    stack.className = "message-stack";
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = String(text || "");
    stack.appendChild(bubble);

    if (metadata && metadata.grounded === true) {
      row.setAttribute("data-grounded", "true");
      row.setAttribute("data-source-kind", String(metadata.source_kind || ""));
      row.setAttribute("data-evidence-kind", String(metadata.evidence_kind || ""));
      row.setAttribute("data-evidence-route", String(metadata.route || ""));
      row.setAttribute("data-journey-id", String(metadata.journey_id || ""));

      var cloneSource = document.createElement("div");
      cloneSource.className = "message-source message-source--clone";
      cloneSource.setAttribute("data-grounded-source", "true");
      cloneSource.textContent = "근거 · 저장소 기반 기관 안내 · " + (metadata.route || "홈");
      stack.appendChild(cloneSource);
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

      var generalSource = document.createElement("div");
      generalSource.className = "message-source message-source--general";
      generalSource.setAttribute("data-general-model-source", "true");
      generalSource.textContent = "근거 · 일반 AI 모델 · 기관 안내 화면 근거 아님";
      stack.appendChild(generalSource);
    }

    row.appendChild(stack);
    thread.appendChild(row);
    thread.scrollTop = thread.scrollHeight;
    return row;
  }

  function _appendGeneralFallbackOffer(question) {
    var row = _appendMessage(
      "ai",
      "현재 지원되는 저장소 기반 기관 안내 근거에서는 이 질문의 답을 확인하지 못했습니다. 원하시면 기관 홈페이지 근거가 아닌 일반 AI 모델 답변을 별도로 볼 수 있습니다.",
    );
    row.setAttribute("data-general-fallback-offer", "true");
    var stack = row.querySelector(".message-stack");
    var button = document.createElement("button");
    button.type = "button";
    button.className = "general-model-offer";
    button.textContent = "일반 AI 답변 보기";
    button.setAttribute("data-general-model-action", "request");
    stack.appendChild(button);

    button.addEventListener("click", function () {
      if (!window.CitizenMvpBridge || typeof window.CitizenMvpBridge.askGeneralModel !== "function") {
        button.disabled = true;
        _appendMessage("ai", "현재 일반 AI 답변을 연결하지 못했습니다.");
        return;
      }
      button.disabled = true;
      document.body.setAttribute("data-journey-state", "general_model_running");
      latestGeneralResult = null;
      Promise.resolve(
        window.CitizenMvpBridge.askGeneralModel(question, { site_id: siteId }),
      ).then(function (result) {
        latestGeneralResult = result;
        var exactProvenance =
          result &&
          result.grounded === false &&
          result.source_kind === "general_model" &&
          result.evidence_kind === "none" &&
          result.answer_scope === "general_model";
        if (result && result.ok && exactProvenance) {
          document.body.setAttribute("data-journey-state", "general_model");
          _appendMessage("ai", result.answer, result);
          return;
        }
        document.body.setAttribute("data-journey-state", "general_model_failed");
        _appendMessage(
          "ai",
          result && typeof result.answer === "string" && result.answer.trim()
            ? result.answer
            : "현재 일반 AI 답변을 연결하지 못했습니다.",
          exactProvenance ? result : null,
        );
      }).catch(function () {
        latestGeneralResult = null;
        document.body.setAttribute("data-journey-state", "general_model_failed");
        _appendMessage("ai", "현재 일반 AI 답변을 연결하지 못했습니다.");
      });
    });
    return row;
  }

  function _setUnavailable(message) {
    document.body.setAttribute("data-surface-state", "unavailable");
    sourceState.setAttribute("data-state", "unavailable");
    sourceState.textContent = message || "기관 안내 화면을 연결할 수 없습니다.";
    input.disabled = true;
    send.disabled = true;
    frame.removeAttribute("src");
  }

  function _setEvidenceState(evidence) {
    latestEvidence = evidence && typeof evidence === "object" ? evidence : null;
    if (latestEvidence && latestEvidence.ok) {
      sourceState.setAttribute("data-state", "ready");
      var routeLabel = latestEvidence.route || "홈";
      sourceState.textContent = "저장소 기반 안내 화면 연결됨 · " + routeLabel + " · " + (latestEvidence.title || config.label);
      return;
    }
    sourceState.setAttribute("data-state", "loading");
    sourceState.textContent = "안내 화면에서 읽을 수 있는 내용을 확인하는 중입니다.";
  }

  function _boot() {
    if (!window.MunicipalSiteSurfaceRegistry || !window.MunicipalCloneSurface) {
      _setUnavailable("기관 안내 구성요소를 불러오지 못했습니다.");
      return;
    }
    var params = new URLSearchParams(window.location.search || "");
    var resolved = window.MunicipalSiteSurfaceRegistry.resolve(params.get("site_id") || "");
    if (!resolved.ok) {
      _setUnavailable("지원하지 않는 기관입니다. 기관을 임의로 대체하지 않습니다.");
      return;
    }

    siteId = resolved.site_id;
    config = resolved.config;
    title.textContent = config.label + " AI 안내";
    document.title = config.label + " AI 안내";
    document.body.setAttribute("data-site-id", siteId);
    document.body.setAttribute("data-surface-state", "ready");
    document.body.setAttribute("data-journey-state", "idle");

    surface = window.MunicipalCloneSurface.create({ iframe: frame, config: config });
    window.addEventListener("municipal-clone-evidence", function (event) {
      if (!event || !event.detail || event.detail.site_id !== siteId) return;
      _setEvidenceState(event.detail);
    });

    if (!surface.navigate("")) {
      _setUnavailable("기관 안내 홈 경로를 열 수 없습니다.");
    }
  }

  async function _answerQuestion(question) {
    latestJourneyResult = null;
    latestGeneralResult = null;
    var journey = null;
    if (window.MunicipalResidentJourneyRegistry) {
      journey = window.MunicipalResidentJourneyRegistry.match(siteId, question);
    }

    if (journey) {
      if (!window.MunicipalResidentJourney) {
        var runtimeFailure = {
          ok: false,
          grounded: false,
          handled: true,
          journey_id: journey.journey_id,
          answer: "안내 화면에서 근거를 확인하지 못해 답변하지 않습니다.",
          failure_code: "journey_runtime_missing",
        };
        latestJourneyResult = runtimeFailure;
        document.body.setAttribute("data-journey-state", "failed");
        _appendMessage("ai", runtimeFailure.answer);
        return;
      }

      document.body.setAttribute("data-journey-state", "running");
      var result = await window.MunicipalResidentJourney.run(journey, surface);
      latestJourneyResult = result;
      if (result && result.ok && result.grounded) {
        document.body.setAttribute("data-journey-state", "grounded");
        _appendMessage("ai", result.answer, result);
      } else {
        document.body.setAttribute("data-journey-state", "failed");
        _appendMessage(
          "ai",
          result && result.answer ? result.answer : "안내 화면에서 근거를 확인하지 못해 답변하지 않습니다.",
        );
      }
      return;
    }

    // Explicit opt-in boundary: an unmatched clone question never calls a
    // general model automatically. The resident must activate the button.
    document.body.setAttribute("data-journey-state", "general_model_offer");
    _appendGeneralFallbackOffer(question);
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (!siteId || !config) return;
    var question = String(input.value || "").trim();
    if (!question) return;
    input.value = "";
    _appendMessage("user", question);
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
  });

  window.MunicipalAiShell = Object.freeze({
    getSiteId: function () { return siteId; },
    getEvidence: function () {
      if (!surface) return latestEvidence;
      latestEvidence = surface.readEvidence();
      return latestEvidence;
    },
    getLastJourneyResult: function () { return latestJourneyResult; },
    getLastGeneralResult: function () { return latestGeneralResult; },
    navigate: function (route) {
      return surface ? surface.navigate(route) : false;
    },
    getSurfaceState: function () {
      return document.body.getAttribute("data-surface-state") || "";
    },
  });

  _boot();
})();
