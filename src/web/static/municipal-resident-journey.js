/*
 * Generic clone-grounded resident journey orchestrator (#1335 / #1328 Slice C).
 *
 * It owns no site-specific questions, routes or facts. A matched registry entry
 * supplies only safe navigation/evidence markers. Final answer content is built
 * from bounded post-navigation clone READ evidence.
 */
(function () {
  "use strict";

  var DEFAULT_TIMEOUT_MS = 5000;

  function _failure(code, journey, evidence) {
    return Object.freeze({
      ok: false,
      grounded: false,
      handled: true,
      journey_id: journey && journey.journey_id ? journey.journey_id : "",
      answer: "안내 화면에서 근거를 확인하지 못해 답변하지 않습니다.",
      excerpt: "",
      site_id: evidence && evidence.site_id ? evidence.site_id : "",
      route: evidence && evidence.route ? evidence.route : "",
      title: evidence && evidence.title ? evidence.title : "",
      evidence_kind: "clone_dom",
      source_kind: "repository_clone",
      failure_code: code || "journey_evidence_unavailable",
    });
  }

  function _lines(text) {
    return String(text || "")
      .split(/\n+/)
      .map(function (line) { return line.replace(/\s+/g, " ").trim(); })
      .filter(Boolean);
  }

  function _selectExcerpt(text, markers, maxChars) {
    var lines = _lines(text);
    if (!lines.length) return "";
    var selected = [];
    var seen = new Set();

    function add(index) {
      if (index < 0 || index >= lines.length || seen.has(index)) return;
      seen.add(index);
      selected.push({ index: index, text: lines[index] });
    }

    markers.forEach(function (marker) {
      var index = lines.findIndex(function (line) { return line.indexOf(marker) !== -1; });
      if (index === -1) return;
      add(index - 1);
      add(index);
      add(index + 1);
    });

    selected.sort(function (a, b) { return a.index - b.index; });
    var excerpt = selected.map(function (item) { return item.text; }).join("\n").trim();
    if (!excerpt) return "";
    return excerpt.length > maxChars ? excerpt.slice(0, maxChars).trim() : excerpt;
  }

  function answerFromEvidence(journey, evidence) {
    if (!journey || typeof journey !== "object") {
      return _failure("journey_config_invalid", journey, evidence);
    }
    if (!evidence || evidence.ok !== true || evidence.grounded !== true) {
      return _failure("journey_evidence_unavailable", journey, evidence);
    }
    if (evidence.source_kind !== "repository_clone" || evidence.evidence_kind !== "clone_dom") {
      return _failure("journey_evidence_source_invalid", journey, evidence);
    }
    if (evidence.route !== journey.evidence_route) {
      return _failure("journey_evidence_route_mismatch", journey, evidence);
    }

    var text = String(evidence.text || "");
    var required = Array.isArray(journey.required_markers) ? journey.required_markers : [];
    for (var i = 0; i < required.length; i += 1) {
      if (!required[i] || text.indexOf(required[i]) === -1) {
        return _failure("journey_evidence_marker_missing", journey, evidence);
      }
    }

    var excerptMarkers = Array.isArray(journey.excerpt_markers)
      ? journey.excerpt_markers
      : required;
    var maxChars = Number(journey.max_excerpt_chars || 0);
    if (!Number.isSafeInteger(maxChars) || maxChars < 120 || maxChars > 2000) {
      return _failure("journey_excerpt_contract_invalid", journey, evidence);
    }
    var excerpt = _selectExcerpt(text, excerptMarkers, maxChars);
    if (!excerpt) return _failure("journey_excerpt_unavailable", journey, evidence);

    return Object.freeze({
      ok: true,
      grounded: true,
      handled: true,
      journey_id: journey.journey_id,
      answer: "왼쪽 저장소 기반 기관 안내 화면에서 확인한 내용입니다.\n\n" + excerpt,
      excerpt: excerpt,
      site_id: evidence.site_id,
      route: evidence.route,
      title: evidence.title || "",
      evidence_kind: evidence.evidence_kind,
      source_kind: evidence.source_kind,
      failure_code: "",
    });
  }

  function _waitForEvidence(surface, route, timeoutMs) {
    return new Promise(function (resolve) {
      var deadline = Date.now() + timeoutMs;
      function check() {
        var evidence = surface.readEvidence();
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

  async function run(journey, surface, options) {
    options = options && typeof options === "object" ? options : {};
    var timeoutMs = Number(options.timeout_ms || DEFAULT_TIMEOUT_MS);
    if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 500 || timeoutMs > 15000) {
      timeoutMs = DEFAULT_TIMEOUT_MS;
    }
    if (!journey || !surface || typeof surface.navigate !== "function" || typeof surface.readEvidence !== "function") {
      return _failure("journey_runtime_invalid", journey, null);
    }

    try {
      if (!surface.navigate(journey.entry_route)) {
        return _failure("journey_entry_route_rejected", journey, null);
      }
      var evidence = await _waitForEvidence(surface, journey.entry_route, timeoutMs);
      if (!evidence || !evidence.ok || evidence.route !== journey.entry_route) {
        return _failure("journey_entry_evidence_unavailable", journey, evidence);
      }

      if (journey.action) {
        if (journey.action.type !== "ACTIVATE_CAPTURED_DETAIL") {
          return _failure("journey_action_unsupported", journey, evidence);
        }
        if (typeof surface.activateCapturedDetail !== "function") {
          return _failure("journey_action_runtime_missing", journey, evidence);
        }
        if (!surface.activateCapturedDetail(journey.action.expected_route)) {
          return _failure("journey_action_rejected", journey, evidence);
        }
        evidence = await _waitForEvidence(surface, journey.action.expected_route, timeoutMs);
        if (!evidence || !evidence.ok || evidence.route !== journey.action.expected_route) {
          return _failure("journey_action_evidence_unavailable", journey, evidence);
        }
      }

      return answerFromEvidence(journey, evidence);
    } catch (_) {
      return _failure("journey_runtime_exception", journey, null);
    }
  }

  window.MunicipalResidentJourney = Object.freeze({
    run: run,
    answerFromEvidence: answerFromEvidence,
  });
})();
