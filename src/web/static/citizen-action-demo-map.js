/**
 * citizen-action-demo-map.js
 * Closed local configuration for the Buk-gu-inspired demo canvas.
 *
 * Uses ONLY the exact closed vocabulary from citizen_action_plan.py.
 * No arbitrary route, target, selector, URL, or executable command input.
 *
 * Vocabulary source (read-only, not modified):
 *   Route IDs:  home, civil-service, complaint-category,
 *               complaint-intake, complaint-review, handoff-stop
 *   Target IDs: nav-civil-service, nav-complaint-category,
 *               complaint-category-illegal-parking,
 *               complaint-category-public-parking-inconvenience,
 *               complaint-category-residential-parking,
 *               complaint-category-traffic-or-facility-safety,
 *               complaint-category-other-or-unsure,
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
    "complaint-intake",
    "complaint-review",
    "handoff-stop",
  ]);

  var CLOSED_TARGET_IDS = Object.freeze([
    "nav-civil-service",
    "nav-complaint-category",
    "complaint-category-illegal-parking",
    "complaint-category-public-parking-inconvenience",
    "complaint-category-residential-parking",
    "complaint-category-traffic-or-facility-safety",
    "complaint-category-other-or-unsure",
    "complaint-body",
    "complaint-draft-review",
    "confirm-draft-prefill",
    "handoff-notice",
  ]);

  // -----------------------------------------------------------------------
  // Route definitions — local static fixture content only
  // All navTargets arrays are individually frozen.
  // -----------------------------------------------------------------------
  var ROUTES = Object.freeze({
    home: Object.freeze({
      id: "home",
      title: "시민 행정 도우미",
      purpose: "로컬 개념 시연용으로 행정절차를 안내합니다.",
      navTargets: Object.freeze(["nav-civil-service"]),
      breadcrumbLabel: "홈",
    }),

    "civil-service": Object.freeze({
      id: "civil-service",
      title: "민원 신청",
      purpose: "주요 민원 서비스 절차를 안내합니다.",
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

    "complaint-intake": Object.freeze({
      id: "complaint-intake",
      title: "민원 작성",
      purpose: "선택한 유형의 민원 작성 예를 안내합니다.",
      navTargets: Object.freeze(["complaint-body", "complaint-draft-review"]),
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
      purpose: "로컬 개념 시연 데모가 여기서 종료됩니다.",
      navTargets: Object.freeze(["handoff-notice"]),
      breadcrumbLabel: "종료",
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
    /** @returns {string[]} */
    getRouteIds: function () {
      return CLOSED_ROUTE_IDS.slice();
    },

    /** @returns {string[]} */
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
     * @returns {string|undefined}
     */
    getCategoryLabel: function (targetId) {
      return CATEGORY_LABELS[targetId];
    },

    /**
     * @param {string} routeId
     * @returns {boolean}
     */
    isValidRoute: function (routeId) {
      return CLOSED_ROUTE_IDS.indexOf(routeId) !== -1;
    },

    /**
     * @param {string} targetId
     * @returns {boolean}
     */
    isValidTarget: function (targetId) {
      return CLOSED_TARGET_IDS.indexOf(targetId) !== -1;
    },
  });

})();