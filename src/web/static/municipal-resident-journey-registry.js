/*
 * Config-only resident journey registry (#1335 / #1328 Slice C).
 *
 * Shared orchestration must resolve through this registry. Site-specific
 * question phrases, clone routes and evidence markers live here rather than in
 * the generic shell/orchestrator. Final factual answer text is intentionally
 * absent: answers must be derived from post-navigation clone READ evidence.
 */
(function () {
  "use strict";

  function _freezeJourney(value) {
    return Object.freeze({
      journey_id: value.journey_id,
      questions: Object.freeze(value.questions.slice()),
      entry_route: value.entry_route,
      action: value.action ? Object.freeze({
        type: value.action.type,
        expected_route: value.action.expected_route,
      }) : null,
      evidence_route: value.evidence_route,
      required_markers: Object.freeze(value.required_markers.slice()),
      excerpt_markers: Object.freeze(value.excerpt_markers.slice()),
      max_excerpt_chars: value.max_excerpt_chars,
    });
  }

  var JOURNEYS = Object.freeze({
    seogu_gwangju: Object.freeze([
      _freezeJourney({
        journey_id: "seogu_notice_social_economy",
        questions: ["사회연대경제 공고 내용을 알려줘"],
        entry_route: "notice/",
        action: {
          type: "ACTIVATE_CAPTURED_DETAIL",
          expected_route: "notice/detail/",
        },
        evidence_route: "notice/detail/",
        required_markers: ["사회연대경제"],
        excerpt_markers: ["사회연대경제"],
        max_excerpt_chars: 700,
      }),
      _freezeJourney({
        journey_id: "seogu_organization_leadership",
        questions: ["서구청 조직도에서 구청장과 부구청장 구조를 알려줘"],
        entry_route: "organization/",
        action: null,
        evidence_route: "organization/",
        required_markers: ["행정조직도", "구청장", "부구청장"],
        excerpt_markers: ["행정조직도", "구청장", "부구청장"],
        max_excerpt_chars: 700,
      }),
    ]),
  });

  function _normalizeQuestion(value) {
    if (typeof value !== "string") return "";
    return value.replace(/\s+/g, " ").trim();
  }

  function match(siteId, question) {
    if (typeof siteId !== "string") return null;
    var siteJourneys = JOURNEYS[siteId];
    if (!siteJourneys) return null;
    var normalized = _normalizeQuestion(question);
    if (!normalized) return null;

    for (var i = 0; i < siteJourneys.length; i += 1) {
      var journey = siteJourneys[i];
      for (var q = 0; q < journey.questions.length; q += 1) {
        if (_normalizeQuestion(journey.questions[q]) === normalized) {
          return journey;
        }
      }
    }
    return null;
  }

  function list(siteId) {
    var journeys = typeof siteId === "string" ? JOURNEYS[siteId] : null;
    return journeys || Object.freeze([]);
  }

  window.MunicipalResidentJourneyRegistry = Object.freeze({
    match: match,
    list: list,
  });
})();
