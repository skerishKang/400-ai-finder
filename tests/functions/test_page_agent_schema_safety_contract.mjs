import assert from 'node:assert/strict';
import test from 'node:test';

import {
  ALLOWED_ACTIONS,
  RESULT_BOUNDARY,
  isForbiddenTargetText,
  validatePlan,
  validatePlanRequest,
} from '../../functions/api/page-agent/_schema.js';

function request(currentRoute) {
  return {
    request_id: 'schema-safety-1291',
    question: 'Show public information safely.',
    current_route: currentRoute,
    available_actions: ALLOWED_ACTIONS.slice(),
    max_steps: 10,
  };
}

function plan(action, target, value = null) {
  return {
    result_boundary: RESULT_BOUNDARY,
    steps: [{ action, target, value }],
  };
}

function expectPlanOk(action, target, value = null) {
  const result = validatePlan(plan(action, target, value));
  assert.equal(result.ok, true, `${action} ${target}: ${JSON.stringify(result)}`);
}

function expectPlanBlocked(action, target, expectedDetail, value = null) {
  const result = validatePlan(plan(action, target, value));
  assert.equal(result.ok, false, `${action} ${target} unexpectedly passed`);
  assert.equal(result.error, 'invalid_plan');
  assert.equal(result.detail, expectedDetail);
}

test('request route permits public high-risk-topic words but rejects external/protocol routes', () => {
  for (const route of ['/payment-guide', '/authentication-help', '/author-card']) {
    const result = validatePlanRequest(request(route));
    assert.equal(result.ok, true, `${route}: ${JSON.stringify(result)}`);
  }

  for (const route of [
    'https://external.example/',
    '//external.example/path',
    'javascript:alert(1)',
    'data:text/plain,x',
  ]) {
    const result = validatePlanRequest(request(route));
    assert.equal(result.ok, false, `${route} unexpectedly passed`);
    assert.equal(result.error, 'invalid_request');
    assert.equal(result.detail, 'current_route_external');
  }
});

test('neutral lexical identifiers do not false-positive on embedded substrings', () => {
  for (const value of [
    'author-profile',
    'authorship',
    'cardinality',
    'payroll',
    'resubmit-guide',
    'undelete-help',
  ]) {
    assert.equal(isForbiddenTargetText(value), false, value);
  }

  expectPlanOk('click', '#service-card');
  expectPlanOk('click', '.author-card');
  expectPlanOk('click', '#cardinality-panel');
  expectPlanOk('click', '#authorship-profile');
  expectPlanOk('click', '#payroll-summary');
  expectPlanOk('click', '#resubmit-guide');
  expectPlanOk('read', '#undelete-help');
});

test('public informational read and same-origin navigation remain allowed', () => {
  expectPlanOk('read', '#credit-card-fee-faq');
  expectPlanOk('read', '#payment-guide');
  expectPlanOk('navigate', '/payment-guide');
  expectPlanOk('navigate', '/authentication-help');
  expectPlanOk('navigate', '/repayment-guide');
  expectPlanOk('click', '#payment-guide');
  expectPlanOk('click', '#authorization-help');
});

test('credential and transaction input targets stay fail-closed across naming conventions', () => {
  const targets = [
    '#password-input',
    '#api-token',
    '#api_key',
    '#APIKey',
    '#credit-card-number',
    '#creditCardNumber',
    '#cvv-input',
    '#login-field',
    '#sign-in-field',
    '#payment-field',
    '[name="password"]',
  ];
  for (const target of targets) {
    expectPlanBlocked('input', target, 'credential_input:0', 'example');
  }

  // Topic text in a normal search value is not a credential by itself.
  expectPlanOk('input', '#search', 'payment guide');
  expectPlanOk('input', '#search', 'authentication help');
  expectPlanOk('input', '#search', 'password reset help');
  expectPlanOk('input', '#service-card', 'public services');
});

test('sensitive input values are rejected by input-specific policy', () => {
  for (const value of [
    'password secret',
    'api_token=example',
    'APIKey example',
    'cvv 123',
    'credit card number',
  ]) {
    expectPlanBlocked('input', '#search', 'credential_input:0', value);
  }

  // Non-input values no longer inherit the input credential policy.
  expectPlanOk('select', '#topic-filter', 'payment guide');
});

test('submit, destructive, login, and payment execution controls remain fail-closed', () => {
  for (const target of [
    '#payment-submit',
    '#paymentSubmit',
    '[type="submit"]',
    '#delete-account',
    '#deleteAccount',
    '#destroy-record',
    '#destroyRecord',
    '#remove-all',
  ]) {
    expectPlanBlocked('click', target, 'destructive_target:0');
  }

  expectPlanBlocked('navigate', '#delete-account', 'destructive_target:0');
  expectPlanBlocked('navigate', '#destroyRecord', 'destructive_target:0');
  expectPlanBlocked('click', '#login-button', 'forbidden_target:0');
  expectPlanBlocked('click', '#signin-button', 'forbidden_target:0');
  expectPlanBlocked('click', '#payment-button', 'forbidden_target:0');
  expectPlanBlocked('navigate', '/login', 'forbidden_target:0');
  expectPlanBlocked('navigate', '/payment', 'forbidden_target:0');
  expectPlanBlocked('read', '#password-input', 'forbidden_target:0');
  expectPlanBlocked('select', '#auth-method', 'forbidden_target:0');
});

test('external and script/data/file targets remain rejected before semantic policy', () => {
  for (const target of [
    'https://external.example/',
    '//external.example/x',
    'javascript:alert(1)',
    'data:text/plain,x',
    'file:///tmp/x',
    'blob:https://example.test/id',
  ]) {
    expectPlanBlocked('navigate', target, 'external_or_unsafe_target:0');
  }
});

test('closed action set, result boundary, and repeated-step guards remain fail-closed', () => {
  const unknown = validatePlan({
    result_boundary: RESULT_BOUNDARY,
    steps: [{ action: 'submit', target: '#safe', value: null }],
  });
  assert.equal(unknown.ok, false);
  assert.equal(unknown.detail, 'unknown_action:submit');

  const boundary = validatePlan({
    result_boundary: 'DONE',
    steps: [{ action: 'read', target: '#safe', value: null }],
  });
  assert.equal(boundary.ok, false);
  assert.equal(boundary.detail, 'result_boundary');

  const repeated = validatePlan({
    result_boundary: RESULT_BOUNDARY,
    steps: [
      { action: 'read', target: '#safe', value: null },
      { action: 'read', target: '#safe', value: null },
    ],
  });
  assert.equal(repeated.ok, false);
  assert.equal(repeated.detail, 'repeated_identical_action:1');
});
