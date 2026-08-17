/* Generic institution clone + AI resident shell (#1333 / #1328 Slice B). */
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

  function _appendMessage(kind, text) {
    var row = document.createElement("div");
    row.className = "message message--" + kind;
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = String(text || "");
    row.appendChild(bubble);
    thread.appendChild(row);
    thread.scrollTop = thread.scrollHeight;
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

    surface = window.MunicipalCloneSurface.create({ iframe: frame, config: config });
    window.addEventListener("municipal-clone-evidence", function (event) {
      if (!event || !event.detail || event.detail.site_id !== siteId) return;
      _setEvidenceState(event.detail);
    });

    if (!surface.navigate("")) {
      _setUnavailable("기관 안내 홈 경로를 열 수 없습니다.");
    }
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (!siteId || !config || !window.CitizenMvpBridge) return;
    var question = String(input.value || "").trim();
    if (!question) return;
    input.value = "";
    _appendMessage("user", question);
    input.disabled = true;
    send.disabled = true;

    window.CitizenMvpBridge.ask(question, { site_id: siteId })
      .then(function (result) {
        var answer = result && typeof result.answer === "string" && result.answer.trim()
          ? result.answer
          : "현재 AI 안내를 연결하지 못했습니다.";
        _appendMessage("ai", answer);
      })
      .catch(function () {
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
    navigate: function (route) {
      return surface ? surface.navigate(route) : false;
    },
    getSurfaceState: function () {
      return document.body.getAttribute("data-surface-state") || "";
    },
  });

  _boot();
})();
