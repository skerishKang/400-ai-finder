/*
 * seogu-resident-journey-registry.js
 * Seo-gu (서구) site-specific resident journey + recommendation-chip registry
 * (#1343 Seo-gu MVP — Buk-gu parity slice).
 *
 * THIS FILE IS THE SITE-SPECIFIC DATA/CONFIG ISLAND. It holds every Seo-gu
 * question phrase, clone route, evidence marker and substitution/capture
 * status. NO Buk-gu-specific fact, question or route is hardcoded anywhere in
 * shared shell code — the shared shell reads this registry instead of
 * branching on an institution id.
 *
 * The 8 entries are the Seo-gu mapping of the Buk-gu canonical 8 scenarios.
 * Two already-proven Seo-gu journeys (notice social-economy, organization
 * leadership) are ALSO registered here so they remain reachable by typed
 * question — they are preserved, never re-implemented.
 *
 * Status contract (gate-required vocabulary):
 *   DIRECT_REUSE                          Seo-gu has equivalent official
 *                                          page/route + committed evidence;
 *                                          wire directly to route + READ.
 *   SOURCE_CAPTURE_NEEDED                 Real Seo-gu purpose, but the specific
 *                                          clone page/evidence is not yet
 *                                          captured; chip must NOT fake success.
 *   SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED No identical Seo-gu service; substitute
 *                                          the closest real Seo-gu service while
 *                                          preserving the resident's purpose.
 *
 * For SOURCE_CAPTURE_NEEDED (no committed route) the shell shows an honest
 * "근거 자료 미확보" state and never navigates to a fabricated page. For
 * substitution journeys with a real route, the shell navigates + READs; if the
 * required marker is absent it fails grounded (no fabricated answer).
 */
(function () {
  "use strict";

  // ── Recommendation-chip icon glyphs (reuse Buk-gu SVG path vocabulary) ──────
  var ICONS = Object.freeze({
    mayor: "M8 14V3M4 6l4-3 4 3M3 11h10M3 14h10",
    parking: "M2 7v5h12V7M3 7l2-3.5h6l2 3.5M4 10.5a1 1 0 1 1 2 0M10 10.5a1 1 0 1 1 2 0",
    building: "M2 14V4l6-3 6 3v10H2zM5.5 14V8h5v6",
    mattress: "M5 8h6M6 8v5M10 8v5",
    passport: "M12 2H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V3a1 1 0 0 0-1-1z M5 5h6M5 8h6M5 11h3",
    kiosk: "M2 3h12v10H2z M8 8a1.5 1.5 0 1 1 0 0.001 M6 11.5h4",
    streetlight: "M4 14h8M8 14V6M5 6l3-3 3 3H5z",
    trash: "M8 8a4 4 0 1 0 0.001 0 M12 4l3-3M4 12l-3 3",
  });

  function _freezeJourney(value) {
    return Object.freeze({
      journey_id: value.journey_id,
      questions: Object.freeze(value.questions.slice()),
      status: value.status,
      entry_route: value.entry_route || "",
      action: value.action
        ? Object.freeze({
            type: value.action.type,
            expected_route: value.action.expected_route,
          })
        : null,
      evidence_route: value.evidence_route || value.entry_route || "",
      required_markers: Object.freeze((value.required_markers || []).slice()),
      excerpt_markers: Object.freeze((value.excerpt_markers || []).slice()),
      max_excerpt_chars: value.max_excerpt_chars || 0,
      capture_needed: Boolean(value.capture_needed),
      substitution_note: value.substitution_note || "",
      handoff: value.handoff
        ? Object.freeze({
            // Generic EXTERNAL_OFFICIAL_HANDOFF data/action contract (#1343
            // final addendum). One config-driven shape shared by S2/S7/S8 — the
            // shell renders it generically, never branching per scenario.
            action_kind: value.handoff.action_kind || "",
            scenario_id: value.handoff.scenario_id || value.journey_id || "",
            local_evidence_route: value.handoff.local_evidence_route || "",
            required_markers: Object.freeze((value.handoff.required_markers || []).slice()),
            destination_url: value.handoff.destination_url || "",
            destination_label: value.handoff.destination_label || "",
            destination_authority: value.handoff.destination_authority || "",
            claim_scope: value.handoff.claim_scope || "HANDOFF_ONLY",
            requires_explicit_resident_activation:
              value.handoff.requires_explicit_resident_activation !== false,
            auto_open: Boolean(value.handoff.auto_open),
            auto_prefill: Boolean(value.handoff.auto_prefill),
            submit_capability: Boolean(value.handoff.submit_capability),
            success_semantics: value.handoff.success_semantics || "NONE",
            stop_boundary_code: value.handoff.stop_boundary_code || "",
            snapshot_captured_at: value.handoff.snapshot_captured_at || "",
            source_urls: Object.freeze((value.handoff.source_urls || []).slice()),
            // Optional config-driven scope note (verified vs unverified), still
            // data — never assembled in shared shell code.
            local_evidence_note: value.handoff.local_evidence_note || "",
          })
        : null,
      chip: value.chip
        ? Object.freeze({
            label: value.chip.label,
            icon: value.chip.icon,
            variant: value.chip.variant || "",
          })
        : null,
    });
  }

  // ── The 8 Buk-gu → Seo-gu mapped scenarios (the MVP chip set) ──────────────
  var SCENARIOS = [
    _freezeJourney({
      journey_id: "seogu_mayor_proposal",
      questions: ["구청장에게 제안하고 싶어요"],
      status: "SOURCE_CAPTURE_NEEDED",
      capture_needed: true,
      substitution_note:
        "서구청 공식 주민제안 페이지가 직접 존재함 (소통/참여 → 주민제안 → 제안하기 참여방법). " +
        "equivalent substitution 대상이 아니며, 현재 clone evidence가 없어 bounded capture 전까지 SOURCE_CAPTURE_NEEDED.",
      chip: { label: "구청장에게 제안하고 싶어요", icon: "mayor", variant: "mayor-primary" },
    }),
    _freezeJourney({
      journey_id: "seogu_illegal_parking_report",
      questions: ["불법 주정차 신고는 어디서 하나요?"],
      status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED",
      capture_needed: false,
      handoff: {
        action_kind: "EXTERNAL_OFFICIAL_HANDOFF",
        local_evidence_route: "illegal-parking-report/",
        required_markers: ["주정차단속조회", "과태료 조회", "과태료 납부", "의견진술"],
        destination_url: "https://www.safetyreport.go.kr/#main",
        destination_label: "안전신문고",
        destination_authority: "행정안전부가 운영하는 안전신문고",
        claim_scope: "HANDOFF_ONLY",
        requires_explicit_resident_activation: true,
        auto_open: false,
        auto_prefill: false,
        submit_capability: false,
        success_semantics: "NONE",
        stop_boundary_code: "EXTERNAL_HANDOFF_STOP_NO_SUBMISSION",
        snapshot_captured_at: "2026-08-18T08:08:08+09:00",
        source_urls: ["https://www.seogu.gwangju.kr/trafficminwon/"],
        local_evidence_note:
          "서구 주정차단속조회 민원시스템은 과태료 조회/납부/의견진술 시스템이며 신고 intake가 아닙니다. " +
          "실제 신고 제출은 공식 안전신문고에서 주민이 직접 진행해야 합니다.",
      },
      substitution_note:
        "EXTERNAL_OFFICIAL_HANDOFF 성격. local evidence route(trafficminwon bounded capture)에서 " +
        "required marker 검증 후 verified/unverified 범위를 설명하고, resident가 직접 선택하는 " +
        "공식 안전신문고 handoff를 제시한 뒤 STOP. 제출 대행/성공 표현 없음.",
      chip: { label: "불법 주정차 신고", icon: "parking", variant: "" },
    }),
    _freezeJourney({
      journey_id: "seogu_apartment_housing_dept",
      questions: ["공동주택 관련 문의는 어느 부서에 해야 하나요?"],
      status: "DIRECT_REUSE",
      entry_route: "housing/",
      evidence_route: "housing/",
      required_markers: ["공동주택", "주택과", "공동주택관리"],
      excerpt_markers: ["주택과", "공동주택관리"],
      max_excerpt_chars: 700,
      substitution_note:
        "서구 공식 공동주택 페이지(menu.es?mid=a10308150000 → board.es?mid=a10308150000&bid=0144)를 " +
        "bounded read-only capture하여 local route housing/로 렌더링. READ evidence(main.rc-main innerText)에서 " +
        "'공동주택'/'주택과'/'공동주택관리' marker 검증 후 READ-derived answer 생성 (답변 문자열 hard-code 없음).",
      chip: { label: "공동주택 부서 문의", icon: "building", variant: "" },
    }),
    _freezeJourney({
      journey_id: "seogu_mattrass_disposal",
      questions: ["매트리스 폐기 신청은 어디서 하나요?"],
      status: "SOURCE_CAPTURE_NEEDED",
      capture_needed: true,
      substitution_note:
        "서구 공식 대형폐기물 신고 페이지가 직접 존재함 (「한손」 홈페이지/앱 접수, 1인용 매트리스 8,000원, 2인용 11,000원). " +
        "civil_form substitute가 아니며, 직접 공식 source를 bounded capture해야 하는 scenario.",
      chip: { label: "대형폐기물 배출", icon: "mattress", variant: "" },
    }),
    _freezeJourney({
      journey_id: "seogu_passport_issuance",
      questions: ["여권 발급은 어디서 하나요?"],
      status: "DIRECT_REUSE",
      capture_needed: false,
      entry_route: "passport-guidance/",
      evidence_route: "passport-guidance/",
      required_markers: ["여권발급", "민원실 4번 창구", "민원봉사과 민원여권", "062-360-7613"],
      excerpt_markers: [
        "여권발급절차",
        "민원실 4번 창구",
        "근무일 기준 8일",
        "민원봉사과 민원여권",
        "062-360-7613",
      ],
      max_excerpt_chars: 700,
      substitution_note:
        "서구 공식 여권민원 안내 페이지(menu.es?mid=a10202020100)를 bounded read-only " +
        "capture하여 local route passport-guidance/로 렌더링. generic CMS content-page " +
        "capability(#1357)가 main.rc-main에 여권발급/민원실 4번 창구/민원봉사과 민원여권/062-360-7613 " +
        "marker를 렌더링. READ evidence(main.rc-main innerText)에서 required/excerpt marker 검증 후 " +
        "READ-derived answer 생성 (답변 문자열 hard-code 없음).",
      chip: { label: "여권 발급 안내", icon: "passport", variant: "" },
    }),
    _freezeJourney({
      journey_id: "seogu_unmanned_kiosk",
      questions: ["무인민원발급기 어디 있어요?"],
      status: "SOURCE_CAPTURE_NEEDED",
      capture_needed: true,
      substitution_note:
        "서구 무인민원발급기 위치 안내 페이지/근거가 클론에 아직 없음. 캡처 후 DIRECT_REUSE 전환 필요.",
      chip: { label: "무인민원발급기 안내", icon: "kiosk", variant: "" },
    }),
    _freezeJourney({
      journey_id: "seogu_streetlight_report",
      questions: ["가로등이 고장났어요. 신고할게요"],
      status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED",
      capture_needed: false,
      handoff: {
        action_kind: "EXTERNAL_OFFICIAL_HANDOFF",
        local_evidence_route: "streetlight-report-handoff/",
        required_markers: ["재난신고", "재난신고센터", "국민재난안전포털"],
        destination_url: "https://www.safetyreport.go.kr/#main",
        destination_label: "안전신문고",
        destination_authority: "행정안전부가 운영하는 안전신문고",
        claim_scope: "HANDOFF_ONLY",
        requires_explicit_resident_activation: true,
        auto_open: false,
        auto_prefill: false,
        submit_capability: false,
        success_semantics: "NONE",
        stop_boundary_code: "EXTERNAL_HANDOFF_STOP_NO_SUBMISSION",
        snapshot_captured_at: "2026-08-18T08:08:08+09:00",
        source_urls: ["https://www.seogu.gwangju.kr/menu.es?mid=a10306030100"],
        local_evidence_note:
          "서구 안전/민방위 재난신고센터는 재난신고 안내 화면이며, 가로등 고장 전용 접수 창구/부서는 " +
          "확인되지 않았습니다. 실제 신고 제출은 공식 안전신문고에서 주민이 직접 진행해야 합니다.",
      },
      substitution_note:
        "EXTERNAL_OFFICIAL_HANDOFF 성격. local evidence route(재난신고센터 bounded capture)에서 " +
        "required marker 검증 후 verified/unverified 범위를 설명하고, resident가 직접 선택하는 " +
        "공식 안전신문고 handoff를 제시한 뒤 STOP. 제출 대행/성공 표현 없음.",
      chip: { label: "가로등 고장 신고 (AI)", icon: "streetlight", variant: "ai-compact" },
    }),
    _freezeJourney({
      journey_id: "seogu_illegal_dumping_report",
      questions: ["쓰레기 무단투기 신고할래"],
      status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED",
      capture_needed: false,
      handoff: {
        action_kind: "EXTERNAL_OFFICIAL_HANDOFF",
        local_evidence_route: "litter-report-handoff/",
        required_markers: ["생활폐기물", "배출/수거", "대형폐기물 신고"],
        // Blocker A correction: the verified Seo-gu chain for litter/dumping is
        // 민원상담 → 국민신문고(epeople), NOT 안전신문고. Exact verified
        // destination from the source-intelligence packet.
        destination_url: "https://www.epeople.go.kr/",
        destination_label: "국민신문고",
        destination_authority: "국민권익위원회가 운영하는 국민신문고",
        claim_scope: "HANDOFF_ONLY",
        requires_explicit_resident_activation: true,
        auto_open: false,
        auto_prefill: false,
        submit_capability: false,
        success_semantics: "NONE",
        stop_boundary_code: "EXTERNAL_HANDOFF_STOP_NO_SUBMISSION",
        snapshot_captured_at: "2026-08-18T08:08:08+09:00",
        source_urls: ["https://www.seogu.gwangju.kr/menu.es?mid=a10308010100"],
        local_evidence_note:
          "서구 생활폐기물 배출/수거 안내 화면은 처리 요령 안내이며 무단투기 전용 접수 창구는 아닙니다. " +
          "쓰레기 무단투기 신고는 서구 민원상담 경유 국민신문고(epeople)에서 주민이 직접 진행해야 합니다.",
      },
      substitution_note:
        "EXTERNAL_OFFICIAL_HANDOFF 성격. local evidence route(생활폐기물처리 bounded capture)에서 " +
        "required marker 검증 후 verified/unverified 범위를 설명하고, resident가 직접 선택하는 " +
        "공식 국민신문고(epeople) handoff를 제시한 뒤 STOP. 안전신문고로 매핑하지 않음(Blocker A). " +
        "제출 대행/성공 표현 없음.",
      chip: { label: "쓰레기 무단투기 (AI)", icon: "trash", variant: "ai-compact" },
    }),
  ];

  // ── Preserved Seo-gu proof journeys (never re-implemented; reachable) ───────
  var PRESERVED = [
    _freezeJourney({
      journey_id: "seogu_notice_social_economy",
      questions: ["사회연대경제 공고 내용을 알려줘"],
      status: "DIRECT_REUSE",
      entry_route: "notice/",
      action: { type: "ACTIVATE_CAPTURED_DETAIL", expected_route: "notice/detail/" },
      evidence_route: "notice/detail/",
      required_markers: ["사회연대경제"],
      excerpt_markers: ["사회연대경제"],
      max_excerpt_chars: 700,
      chip: null,
    }),
    _freezeJourney({
      journey_id: "seogu_organization_leadership",
      questions: ["서구청 조직도에서 구청장과 부구청장 구조를 알려줘"],
      status: "DIRECT_REUSE",
      entry_route: "organization/",
      evidence_route: "organization/",
      required_markers: ["행정조직도", "구청장", "부구청장"],
      excerpt_markers: ["행정조직도", "구청장", "부구청장"],
      max_excerpt_chars: 700,
      chip: null,
    }),
  ];

  var ALL = SCENARIOS.concat(PRESERVED);
  var BY_ID = Object.create(null);
  ALL.forEach(function (j) { BY_ID[j.journey_id] = j; });

  function _normalizeQuestion(value) {
    if (typeof value !== "string") return "";
    return value.replace(/\s+/g, " ").trim();
  }

  function match(question) {
    if (typeof question !== "string") return null;
    var normalized = _normalizeQuestion(question);
    if (!normalized) return null;
    for (var i = 0; i < ALL.length; i += 1) {
      var journey = ALL[i];
      for (var q = 0; q < journey.questions.length; q += 1) {
        if (_normalizeQuestion(journey.questions[q]) === normalized) return journey;
      }
    }
    return null;
  }

  function get(journeyId) {
    return BY_ID[journeyId] || null;
  }

  function chips() {
    return SCENARIOS.filter(function (j) { return j.chip; }).map(function (j) {
      return Object.freeze({
        journey_id: j.journey_id,
        label: j.chip.label,
        icon: ICONS[j.chip.icon] || "",
        variant: j.chip.variant,
        question: j.questions[0],
        status: j.status,
      });
    });
  }

  function list() {
    return ALL.slice();
  }

  function scenarios() {
    return SCENARIOS.slice();
  }

  window.SeoguResidentJourneyRegistry = Object.freeze({
    SITE_ID: "seogu_gwangju",
    ICONS: ICONS,
    match: match,
    get: get,
    list: list,
    scenarios: scenarios,
    chips: chips,
  });
})();
