/**
 * citizen-action-demo-map.js
 * Closed local configuration for the Buk-gu-inspired demo canvas.
 *
 * Uses ONLY the exact closed vocabulary from citizen_action_plan.py.
 * No arbitrary route, target, selector, URL, or executable command input.
 *
 * Vocabulary source (read-only, not modified):
 *   Route IDs:  home, civil-service, bulky-waste-disposal,
 *               complaint-category, complaint-intake,
 *               complaint-review, handoff-stop
 *   Target IDs: nav-civil-service, nav-complaint-category,
 *               complaint-category-illegal-parking,
 *               complaint-category-public-parking-inconvenience,
 *               complaint-category-residential-parking,
 *               complaint-category-traffic-or-facility-safety,
 *               complaint-category-other-or-unsure,
 *               complaint-illegal-parking-report,
 *               bulky-waste-guidance-card,
 *               complaint-body, complaint-draft-review,
 *               confirm-draft-prefill, handoff-notice
 */

(function () {
  "use strict";

  // -----------------------------------------------------------------------
  // Closed vocabulary (mirror of citizen_action_plan.py)
  // -----------------------------------------------------------------------
  var CLOSED_ROUTE_IDS = Object.freeze([
    "home",
    "civil-service",
    "complaint-category",
    "complaint-illegal-parking",
    "complaint-intake",
    "handoff-stop",
    "complaint-review",
"bulky-waste-disposal",
    "move-in-report-guidance",
    "public-health-center-guidance",
  ]);

  var CLOSED_TARGET_IDS = Object.freeze([
    "nav-civil-service",
    "nav-complaint-category",
    "complaint-category-illegal-parking",
    "complaint-category-public-parking-inconvenience",
    "complaint-category-residential-parking",
    "complaint-category-traffic-or-facility-safety",
    "complaint-category-other-or-unsure",
    "complaint-illegal-parking-report",
    "complaint-body",
    "complaint-draft-review",
    "confirm-draft-prefill",
    "handoff-notice",
    "bulky-waste-guidance-card",
    "move-in-guidance-card",
    "health-center-guidance-card",
  ]);

  // -----------------------------------------------------------------------
  // Route definitions — local static fixture content only
  // -----------------------------------------------------------------------
  var ROUTES = Object.freeze({
    home: Object.freeze({
      id: "home",
      title: "시민 행정 도우미",
      purpose: "북구청 행정서비스를 안내합니다.",
      navTargets: Object.freeze(["nav-civil-service"]),
      breadcrumbLabel: "홈",
    }),

    "civil-service": Object.freeze({
      id: "civil-service",
      title: "민원 신청",
      purpose: "북구청 주요 민원 서비스를 안내합니다.",
      navTargets: Object.freeze(["nav-complaint-category"]),
      breadcrumbLabel: "민원 신청",
    }),

    "complaint-category": Object.freeze({
      id: "complaint-category",
      title: "민원 유형 선택",
      purpose: "해당 상황에 맞는 민원 유형을 선택해 주세요.",
      navTargets: Object.freeze([
        "complaint-category-illegal-parking",
        "complaint-category-public-parking-inconvenience",
        "complaint-category-residential-parking",
        "complaint-category-traffic-or-facility-safety",
        "complaint-category-other-or-unsure",
      ]),
      breadcrumbLabel: "유형 선택",
    }),

    "complaint-illegal-parking": Object.freeze({
      id: "complaint-illegal-parking",
      title: "지도단속",
      purpose: "차량교통 분야 지도단속 안내. 실제 신고는 안전신문고 등 공식 채널에서 직접 진행해야 합니다.",
      navTargets: Object.freeze([
        "complaint-illegal-parking-report",
      ]),
      breadcrumbLabel: "지도단속",
    }),

    "complaint-intake": Object.freeze({
      id: "complaint-intake",
      title: "민원 작성",
      purpose: "선택한 유형에 따라 내용을 작성해 주세요.",
      navTargets: Object.freeze(["complaint-draft-review"]),
      breadcrumbLabel: "민원 작성",
    }),

    "complaint-review": Object.freeze({
      id: "complaint-review",
      title: "민원 내용 확인",
      purpose: "작성된 내용을 확인해 주세요.",
      navTargets: Object.freeze(["confirm-draft-prefill"]),
      breadcrumbLabel: "내용 확인",
    }),

    "handoff-stop": Object.freeze({
      id: "handoff-stop",
      title: "데모 종료",
      purpose: "실제 민원 신청은 북구청 공식 채널을 이용하세요.",
      navTargets: Object.freeze([]),
      breadcrumbLabel: "종료",
    }),

    "bulky-waste-disposal": Object.freeze({
      id: "bulky-waste-disposal",
      title: "대형폐기물 배출방법",
      purpose: "수탁업체(녹색환경) 전화 신고 또는 여기로 어플을 통한 대형폐기물 배출방법을 안내합니다.",
      navTargets: Object.freeze(["bulky-waste-guidance-card"]),
      breadcrumbLabel: "대형폐기물 배출방법",
    }),

    "move-in-report-guidance": Object.freeze({
      id: "move-in-report-guidance",
      title: "정부24 전입신고 연결 안내",
      purpose: "북구청 종합민원 → 전자민원창구 → 정부24 경로로 전입신고 연결을 안내합니다.",
      navTargets: Object.freeze(["move-in-guidance-card"]),
      breadcrumbLabel: "정부24 전입신고 연결 안내",
    }),

    "public-health-center-guidance": Object.freeze({
      id: "public-health-center-guidance",
      title: "보건소 위치·진료 안내",
      purpose: "보건소 위치, 운영시간, 진료과목, 예방접종, 검사 경로를 안내합니다.",
      navTargets: Object.freeze(["health-center-guidance-card"]),
      breadcrumbLabel: "보건소 위치·진료 안내",
    }),
  });

  // -----------------------------------------------------------------------
  // Category label map (Korean)
  // -----------------------------------------------------------------------
  var CATEGORY_LABELS = Object.freeze({
    "complaint-category-illegal-parking": "불법 주정차 신고",
    "complaint-category-public-parking-inconvenience": "공용주차장 불편",
    "complaint-category-residential-parking": "공동주택 주차 관련",
    "complaint-category-traffic-or-facility-safety": "교통·시설 안전",
    "complaint-category-other-or-unsure": "기타",
  });

  // -----------------------------------------------------------------------
  // Immutable public API
  // -----------------------------------------------------------------------
  window.CitizenActionDemoMap = Object.freeze({
    /** @type {string[]} */
    getRouteIds: function () {
      return CLOSED_ROUTE_IDS.slice();
    },

    /** @type {string[]} */
    getTargetIds: function () {
      return CLOSED_TARGET_IDS.slice();
    },

    /**
     * @param {string} routeId
     * @returns {object|undefined}
     */
    getRoute: function (routeId) {
      if (ROUTES[routeId] !== undefined) {
        return ROUTES[routeId];
      }
      return undefined;
    },

    /**
     * @param {string} targetId
     * @returns {string|undefined} Korean label for category targets
     */
    getCategoryLabel: function (targetId) {
      return CATEGORY_LABELS[targetId];
    },

    /**
     * Validate that a routeId is in the closed vocabulary.
     * @param {string} routeId
     * @returns {boolean}
     */
    isValidRoute: function (routeId) {
      return CLOSED_ROUTE_IDS.indexOf(routeId) !== -1;
    },

    /**
     * Validate that a targetId is in the closed vocabulary.
     * @param {string} targetId
     * @returns {boolean}
     */
    isValidTarget: function (targetId) {
      return CLOSED_TARGET_IDS.indexOf(targetId) !== -1;
    },
  });

})();
