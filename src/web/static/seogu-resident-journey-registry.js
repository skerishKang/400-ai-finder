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
            type: value.action.type || "",
            choreography_key: value.action.choreography_key || "",
            expected_route: value.action.expected_route || "",
          })
        : null,
      // #1380 S-final: post-answer presentation contract (GUIDANCE_NAVIGATION).
      // Kept OUT of `action` — the generic journey runner treats any action as
      // a clone-detail activation and would fail-closed.
      presentation: value.presentation
        ? Object.freeze({
            type: value.presentation.type || "",
            choreography_key: value.presentation.choreography_key || "",
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
      status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED",
      capture_needed: false,
      // #1363 Lane B (CTO rework 2026-08-21): S7 mirrors the Buk-gu
      // 구청장에게 제안하고 싶어요 mayor-complaint-write/receipt journey via the
      // #1375 complaint-writing pattern. The bounded 주민제안 capture grounds
      // the guidance facts (참여대상·참여방법·처리절차) before the app-owned
      // proposal-writing surface opens. NO external channel anchor, NO
      // safe_handoff destination — EXTERNAL_CHANNEL_REPLACES_CANONICAL_FLOW=NO.
      handoff: {
        action_kind: "COMPLAINT_EVIDENCE_GATE",
        scenario_id: "seogu_mayor_proposal",
        local_evidence_route: "mayor-proposal-guidance/",
        required_markers: ["주민제안", "참여방법", "참여대상", "제안하기"],
        claim_scope: "EVIDENCE_GATE_ONLY",
        stop_boundary_code: "COMPLAINT_EVIDENCE_FAILED_STOP",
        snapshot_captured_at: "2026-08-21T02:11:12.864Z",
        source_urls: ["https://www.seogu.gwangju.kr/menu.es?mid=a10401030100"],
        local_evidence_note:
          "서구청 주민제안 안내 화면은 참여대상(전 주민, 단체 가능)·참여방법" +
          "(홈페이지 제안하기, 우편, 팩스)·처리절차 등 주민제안 작성에 필요한 " +
          "안내 사실을 제공합니다. 이 근거는 초안 작성 흐름의 안내에만 사용되며, " +
          "실제 접수는 서구청 공식 채널에서 주민이 직접 진행해야 합니다.",
      },
      action: {
        type: "COMPLAINT_AI_ASSIST",
        // Canonical shared-choreography JOURNEY_MAP key (hasJourney()/start()
        // resolve JOURNEY_MAP keys, not journey ids). Buk-gu mayor-proposal
        // golden scenario: office → AI 제안작성 → 주민 검토 → 사전제출 STOP → 수령.
        choreography_key: "mayor_message_assist",
      },
      substitution_note:
        "Buk-gu mayor-complaint-write/receipt 시나리오와 동일한 관측 상태 그래프. " +
        "Seo-gu 데이터/근거(주민제안 bounded capture)/브랜딩만 치환. external 채널 " +
        "치환 없음 — 수령 화면의 안내 문구(공식 제출은 서구청 공식 채널에서 시민이 " +
        "직접 확인하고 진행)가 안전 경계.",
      chip: { label: "구청장에게 제안하고 싶어요", icon: "mayor", variant: "mayor-primary" },
    }),
    _freezeJourney({
      journey_id: "seogu_illegal_parking_report",
      questions: ["불법 주정차 신고는 어디서 하나요?"],
      status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED",
      capture_needed: false,
      // #1380 S-final (owner decision 2026-08-21): Buk-gu 동일 시나리오 복사 —
      // 외부 채널 anchor/링크 표면 없음. trafficminwon bounded capture가
      // grounding 근거(과태료 조회/납부/의견진술 시스템이며 신고 intake가
      // 아님)를 제공하고, 앱 소유 guidance surface(지도단속 안내 card)와
      // handoff-stop 단말이 Buk-gu Golden 형태를 그대로 재현한다. 실제 신고는
      // 안전신문고에서 주민이 직접 진행한다는 안내 '텍스트'로만 언급된다.
      entry_route: "illegal-parking-report/",
      evidence_route: "illegal-parking-report/",
      required_markers: ["주정차단속조회", "과태료 조회", "과태료 납부", "의견진술"],
      excerpt_markers: ["주정차단속조회", "과태료 조회", "과태료 납부", "의견진술"],
      max_excerpt_chars: 700,
      presentation: {
        type: "GUIDANCE_NAVIGATION",
        // Canonical shared-choreography JOURNEY_MAP key (hasJourney()/start()
        // resolve JOURNEY_MAP keys, not journey ids). Buk-gu 불법주정차 golden:
        // 지도단속 안내 surface → card → handoff-stop 단말.
        choreography_key: "illegal_parking",
      },
      substitution_note:
        "Buk-gu 불법주정차 신고 시나리오와 동일한 관측 상태 그래프 (안내 채팅 → " +
        "지도단속 안내 surface → card → handoff-stop 단말). Seo-gu 데이터 치환: " +
        "trafficminwon bounded capture(2026-08-18) 근거 — 서구 시스템은 과태료 " +
        "조회/납부/의견진술이며 신고 intake가 아님. 실제 신고는 안전신문고에서 " +
        "주민이 직접 진행한다는 안내 텍스트만 제공 (링크/anchor 표면 없음).",
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
      journey_id: "seogu_mattress_disposal",
      questions: ["매트리스 폐기 신청은 어디서 하나요?"],
      status: "DIRECT_REUSE",
      capture_needed: false,
      entry_route: "bulky-waste-guidance/",
      evidence_route: "bulky-waste-guidance/",
      required_markers: [
        "대형폐기물 신고",
        "한손",
        "시설관리공단",
        "374-9446",
        "자원순환과",
        "062-360-7287",
        "1인용 매트리스",
        "8,000",
        "2인용 매트리스",
        "11,000",
        "4~7일",
      ],
      excerpt_markers: [
        "대형폐기물 신고",
        "한손",
        "1인용 매트리스",
        "8,000",
        "2인용 매트리스",
        "11,000",
        "4~7일",
      ],
      max_excerpt_chars: 1200,
      substitution_note:
        "#1376 S8 DIRECT_REUSE. 서구 공식 대형폐기물 신고 페이지(menu.es?mid=a10308010200)를 " +
        "bounded read-only capture(20260821T143931-0900)하여 local route bulky-waste-guidance/로 " +
        "렌더링. generic CMS content-page capability(#1357)가 main.rc-main에 대형폐기물 신고/한손/" +
        "시설관리공단/374-9446/자원순환과/062-360-7287 marker와 수수료 표(1인용 매트리스 8,000원 · " +
        "2인용 매트리스 11,000원 — Buk-gu 폴백 하드코딩 5,000원이 아닌 신규 캡처에서 조달)를 렌더링. " +
        "READ evidence(main.rc-main innerText)에서 required/excerpt marker 검증 후 READ-derived " +
        "answer 생성 (답변 문자열 hard-code 없음). 실제 신청/결제는 「한손」 앱·홈페이지(24시간)에서 " +
        "주민이 직접 진행 — clone 밖 경계 유지, 처리기간 평균 4~7일.",
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
      status: "DIRECT_REUSE",
      capture_needed: false,
      entry_route: "unmanned-kiosk/",
      evidence_route: "unmanned-kiosk/",
      required_markers: [
        "무인민원발급안내",
        "설치장소",
        "도로명주소",
        "서비스시간",
        "발급종수",
      ],
      excerpt_markers: [
        "설치장소",
        "도로명주소",
        "서비스시간",
        "발급종수",
      ],
      max_excerpt_chars: 1200,
      substitution_note:
        "서구 공식 무인민원발급안내 페이지(menu.es?mid=a10201040000)를 bounded read-only " +
        "capture하여 local route unmanned-kiosk/로 렌더링. generic list-board capability가 " +
        "main.rc-main에 무인민원발급안내/설치장소/도로명주소/서비스시간/발급종수 marker와 " +
        "page-1 설치장소/도로명주소/서비스시간/발급종수 행을 렌더링. READ evidence(main.rc-main " +
        "innerText)에서 required/excerpt marker 검증 후 READ-derived answer 생성 (답변 문자열 " +
        "hard-code 없음). 전체 34건/페이지 1/4는 captured snapshot metadata이며 permanent " +
        "business truth로 단정하지 않음.",
      chip: { label: "무인민원발급기 안내", icon: "kiosk", variant: "" },
    }),
    _freezeJourney({
      journey_id: "seogu_streetlight_report",
      questions: ["가로등이 고장났어요. 신고할게요"],
      status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED",
      capture_needed: false,
      // #1364 Lane B: S3 complaint-writing recovery. The Buk-gu canonical
      // interaction graph for 가로등 is complaint-board → write → draft →
      // pre-submit STOP. Seo-gu preserves this graph by first validating its
      // own official evidence, then rendering the app-owned complaint surface
      // and running the shared choreography. No external handoff destination.
      action: {
        type: "COMPLAINT_BOARD_WRITE",
        // Canonical shared-choreography JOURNEY_MAP key (hasJourney()/start()
        // resolve JOURNEY_MAP keys, not journey ids).
        choreography_key: "streetlight_report",
      },
      handoff: {
        // Used as the evidence gate: the shared controller navigates to this
        // local clone route, READs the region, and validates required_markers
        // before the complaint-writing choreography may begin. This is a gate,
        // not a destination — no safe_handoff destination row is rendered.
        action_kind: "COMPLAINT_EVIDENCE_GATE",
        local_evidence_route: "streetlight-report-handoff/",
        required_markers: ["재난신고", "재난신고센터", "국민재난안전포털"],
        claim_scope: "EVIDENCE_GATE_ONLY",
        stop_boundary_code: "COMPLAINT_EVIDENCE_FAILED_STOP",
        snapshot_captured_at: "2026-08-18T08:08:08+09:00",
        source_urls: ["https://www.seogu.gwangju.kr/menu.es?mid=a10306030100"],
        local_evidence_note:
          "서구 안전/민방위 재난신고센터 화면은 가로등 고장 전용 접수 창구가 아닙니다. " +
          "이 증거 검증은 서구청 공식 안내의 존재와 범위를 확인하는 용도이며, " +
          "아래 AI 보조 초안 작성 화면으로 이어집니다.",
      },
      substitution_note:
        "COMPLAINT_BOARD_WRITE 타입. evidence gate(재난신고센터 bounded capture)를 " +
        "통과한 뒤 앱 소유의 민원게시판/글쓰기 표면에서 AI 보조 초안을 작성하고 " +
        "PRE_SUBMIT STOP boundary에서 종료. 외부 제출/대행/성공 표현 없음.",
      chip: { label: "가로등 고장 신고 (AI)", icon: "streetlight", variant: "ai-compact" },
    }),
    _freezeJourney({
      journey_id: "seogu_illegal_dumping_report",
      questions: ["쓰레기 무단투기 신고할래"],
      status: "SEO_GU_EQUIVALENT_SUBSTITUTION_NEEDED",
      capture_needed: false,
      // #1364 Lane B: S4 complaint-writing recovery. The Buk-gu canonical
      // interaction graph for 쓰레기 무단투기 is complaint-board → AI-choice →
      // write → draft → pre-submit STOP. Seo-gu preserves this graph by first
      // validating its own official evidence, then rendering the app-owned
      // complaint surface and running the shared choreography.
      action: {
        type: "COMPLAINT_AI_ASSIST",
        // Canonical shared-choreography JOURNEY_MAP key (hasJourney()/start()
        // resolve JOURNEY_MAP keys, not journey ids).
        choreography_key: "litter_ai_assist",
      },
      handoff: {
        // Used as the evidence gate only. No safe_handoff destination row.
        action_kind: "COMPLAINT_EVIDENCE_GATE",
        local_evidence_route: "litter-report-handoff/",
        required_markers: ["생활폐기물", "배출/수거", "대형폐기물 신고"],
        claim_scope: "EVIDENCE_GATE_ONLY",
        stop_boundary_code: "COMPLAINT_EVIDENCE_FAILED_STOP",
        snapshot_captured_at: "2026-08-18T08:08:08+09:00",
        source_urls: ["https://www.seogu.gwangju.kr/menu.es?mid=a10308010100"],
        local_evidence_note:
          "서구 생활폐기물 배출/수거 안내 화면은 무단투기 전용 접수 창구가 아닙니다. " +
          "이 증거 검증은 서구청 공식 안내의 존재와 범위를 확인하는 용도이며, " +
          "아래 AI 보조 초안 작성 화면으로 이어집니다.",
      },
      substitution_note:
        "COMPLAINT_AI_ASSIST 타입. evidence gate(생활폐기물처리 bounded capture)를 " +
        "통과한 뒤 앱 소유의 민원게시판/글쓰기 표면에서 AI 보조 초안을 작성하고 " +
        "PRE_SUBMIT STOP boundary에서 종료. 외부 제출/대행/성공 표현 없음.",
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
