// ═════════════════════════════════════════════════════════════════════════
// functions/api/page-agent/_parity_scenarios.js
//
// Server-side plan vocabulary for the five parity scenarios.
// IDs, triggers, and data-action-target steps mirror the browser owner:
//   src/web/examples/page-agent/resident/parity-scenarios.js
//
// Cloudflare Functions cannot import the browser file at runtime, so this
// module holds only the plan-oriented view (targets → click steps). It is
// not a second product map: keep IDs/targets aligned with the resident file.
// ═════════════════════════════════════════════════════════════════════════

import { RESULT_BOUNDARY } from './_schema.js';

function clickStep(actionTarget) {
  return {
    action: 'click',
    target: '[data-action-target="' + actionTarget + '"]',
    value: null,
  };
}

/**
 * @typedef {{
 *   id: string,
 *   triggers: string[],
 *   routeId: string,
 *   actionTargets: string[],
 *   response: string,
 * }} ParityScenario
 */

/** @type {readonly ParityScenario[]} */
export const PARITY_SCENARIOS = Object.freeze([
  Object.freeze({
    id: 'apartment_contact',
    triggers: Object.freeze([
      '공동주택과 연락처 찾아줘',
      '공동주택 연락처',
      '아파트 연락처',
      '공동주택과',
      'apartment contact',
    ]),
    routeId: 'apartment-dept',
    actionTargets: Object.freeze(['nav-apartment-dept']),
    response:
      '공동주택과 조직 및 업무안내 화면입니다. 종합민원 메뉴에서 공동주택과 담당 업무와 연락처를 확인할 수 있습니다.',
  }),
  Object.freeze({
    id: 'bulky_waste_menu',
    triggers: Object.freeze([
      '대형폐기물 신청 메뉴 찾아줘',
      '대형폐기물 신청',
      '대형폐기물 배출',
      '폐기물 신청',
      'bulky waste',
    ]),
    routeId: 'bulky-waste-disposal',
    actionTargets: Object.freeze(['nav-bulky-waste-disposal']),
    response:
      '대형폐기물 배출방법 안내 화면입니다. 종합민원 메뉴에서 대형폐기물 배출 신청 방법과 수수료를 확인할 수 있습니다.',
  }),
  Object.freeze({
    id: 'passport_procedure',
    triggers: Object.freeze([
      '여권 발급 절차를 찾아줘',
      '여권 발급',
      '여권 절차',
      '여권',
      'passport',
    ]),
    routeId: 'passport-guidance',
    actionTargets: Object.freeze(['nav-passport-guidance']),
    response:
      '여권민원 안내 화면입니다. 종합민원 메뉴에서 여권 종류, 유효기간, 발급수수료, 신청절차, 구비서류를 확인할 수 있습니다.',
  }),
  Object.freeze({
    id: 'complaint_screen',
    triggers: Object.freeze([
      '민원 작성 화면을 열어줘',
      '민원 작성',
      '민원 신청',
      '민원 게시판',
      'complaint',
    ]),
    routeId: 'complaint-write',
    actionTargets: Object.freeze(['nav-complaint-board', 'complaint-write']),
    response:
      '민원 글쓰기 화면입니다. 종합민원 → 민원 유형 선택 후 민원 게시판에서 글쓰기를 통해 AI가 민원 초안 작성을 도와드립니다.',
  }),
  Object.freeze({
    id: 'mayor_proposal_writing',
    triggers: Object.freeze([
      '구청장에게 제안할 글 작성을 도와줘',
      '구청장에게 바란다',
      '구청장 제안',
      '구청장 글 작성',
      'mayor proposal',
    ]),
    routeId: 'mayor-complaint-write',
    actionTargets: Object.freeze(['mayor-office-open', 'mayor-message-write']),
    response:
      '구청장에게 바란다 작성 화면입니다. 열린구청장실에서 구청장에게 바란다를 통해 AI와 함께 구정 제안을 작성하고 제출 전에 직접 검토합니다.',
  }),
]);

function normalize(text) {
  return String(text || '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function findParityScenario(question) {
  const n = normalize(question);
  if (!n) return null;
  for (const scenario of PARITY_SCENARIOS) {
    for (const trigger of scenario.triggers) {
      if (n.indexOf(trigger) !== -1 || trigger.indexOf(n) !== -1) {
        return scenario;
      }
    }
  }
  return null;
}

/**
 * Build a strict plan for a known parity scenario.
 * Steps only use allowlisted click targets — never submit/payment/JS.
 */
export function buildPlanForScenario(scenario) {
  const steps = scenario.actionTargets.map(clickStep);
  // Final read keeps the agent in the action loop without claiming submission.
  steps.push({
    action: 'read',
    target: null,
    value: scenario.response,
  });
  return {
    steps: steps,
    result_boundary: RESULT_BOUNDARY,
    // Non-schema metadata is stripped by validatePlan (unknown keys rejected).
    // Keep only schema fields on the returned plan.
  };
}

export function buildValidatedPlanShape(scenario) {
  const steps = scenario.actionTargets.map(clickStep);
  steps.push({
    action: 'read',
    target: null,
    value: scenario.response,
  });
  return {
    steps: steps,
    result_boundary: RESULT_BOUNDARY,
  };
}
