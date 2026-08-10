const ORIGINAL_FETCH = globalThis.fetch;

let askModule;
let passed = 0;
let failed = 0;
const failures = [];

async function check(name, fn) {
  try {
    await fn();
    passed += 1;
    console.log(`  PASS ${name}`);
  } catch (error) {
    failed += 1;
    failures.push(`${name}: ${error.message}`);
    console.log(`  FAIL ${name}: ${error.message}`);
  }
}

function equal(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function providerResponse(answer, action = 'none') {
  return new Response(JSON.stringify({
    choices: [{
      message: {
        content: JSON.stringify({ answer, action, confidence: 0.9 }),
      },
    }],
    usage: { prompt_tokens: 10, completion_tokens: 20, total_tokens: 30 },
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

async function invoke(question, answer, locale = 'ko', envOverrides = {}) {
  let providerCalls = 0;
  globalThis.fetch = async () => {
    providerCalls += 1;
    return providerResponse(answer);
  };
  const response = await askModule.onRequest({
    request: new Request('http://localhost:8788/api/mvp/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, locale }),
    }),
    env: {
      GEMINI_API_KEY: 'test-key',
      KILOCODE_API_KEY: '',
      MVP_RUNTIME_LOGS: '0',
      ...envOverrides,
    },
  });
  const data = JSON.parse(await response.text());
  return { response, data, providerCalls };
}

console.log('\n=== Cloudflare MVP evidence policy integration contract ===\n');

// Imported after test helpers so the module is evaluated once against the
// network stub installed by individual cases, never against a live provider.
askModule = await import('../../functions/api/mvp/ask.js');

await check('runtime and evidence policy versions have independent ownership', async () => {
  equal(askModule.POLICY_VERSION, '2026-08-10.2', 'runtime policy version');
  const { data } = await invoke(
    '가로등 고장 신고는 어떻게 하나요?',
    'Please use the official reporting path and confirm the current guidance there.',
    'en',
  );
  equal(data.policy_version, '2026-08-10.2', 'public runtime policy version');
  equal(data.meta.policy_version, '2026-08-10.2', 'meta runtime policy version');
  equal(data.meta.evidence_policy.version, '2026-08-11.1', 'evidence policy version');
  if (data.policy_version === data.meta.evidence_policy.version) {
    throw new Error('runtime policy version is still implicitly coupled to evidence policy version');
  }
});

await check('canonical housing phone present in snapshot survives evidence gate', async () => {
  const phone = '062-410-6841';
  const { data, providerCalls } = await invoke(
    '공동주택 관련 문의는 어디에 해야 하나요?',
    `공동주택과 대표전화는 ${phone}입니다. 자세한 내용은 담당 부서에 문의해 주세요.`,
  );
  equal(data.ok, true, 'ok');
  equal(data.failure_code, '', 'failure');
  equal(data.freshness_state, 'official_snapshot', 'freshness');
  equal(data.meta.evidence_policy.decision, 'allow', 'decision');
  equal(data.meta.evidence_policy.evidence_level, 'canonical_snapshot', 'level');
  equal(data.meta.evidence_policy.reason, 'all_concrete_values_verified', 'reason');
  equal(JSON.stringify(data.meta.evidence_policy.signal_kinds), JSON.stringify(['phone']), 'signals');
  equal(providerCalls, 1, 'provider calls');
});

await check('hallucinated housing phone is replaced by evidence_required fallback', async () => {
  const blocked = '062-410-9999';
  const { data, providerCalls } = await invoke(
    '공동주택 관련 문의는 어디에 해야 하나요?',
    `공동주택과 대표전화는 ${blocked}입니다. 이 번호로 문의해 주세요.`,
  );
  equal(data.ok, false, 'ok');
  equal(data.failure_code, 'evidence_required', 'failure');
  equal(data.error.retryable, false, 'retryable');
  equal(data.meta.evidence_policy.decision, 'block', 'decision');
  equal(data.meta.evidence_policy.reason, 'concrete_value_not_in_verified_evidence', 'reason');
  equal(data.freshness_state, 'official_snapshot', 'freshness');
  if (!data.source_url || !Array.isArray(data.sources) || !data.sources.length) {
    throw new Error('official verification path was not preserved');
  }
  const serialized = JSON.stringify(data);
  if (serialized.includes(blocked)) throw new Error('blocked phone leaked into response/metadata');
  equal(providerCalls, 1, 'provider calls');
});

await check('model-only concrete time is blocked while safe general guidance remains allowed', async () => {
  const blocked = await invoke(
    '가로등 고장 신고는 어떻게 하나요?',
    '가로등 신고 접수 시간은 09:00입니다. 해당 시간에 신고해 주세요.',
  );
  equal(blocked.data.failure_code, 'evidence_required', 'blocked failure');
  equal(blocked.data.meta.evidence_policy.evidence_level, 'model_only', 'blocked level');
  if (JSON.stringify(blocked.data).includes('09:00')) throw new Error('blocked time leaked');

  const safe = await invoke(
    '가로등 고장 신고는 어떻게 하나요?',
    '가로등 고장은 공식 신고 경로에서 위치와 상황을 확인해 접수해 주세요.',
  );
  equal(safe.data.ok, true, 'safe ok');
  equal(safe.data.meta.evidence_policy.reason, 'no_concrete_high_risk_value', 'safe reason');
});

await check('ambiguous numeric date is rejected without retry or raw-value leakage', async () => {
  const blocked = '08/09/2026';
  const { data, providerCalls } = await invoke(
    'How should I report a broken streetlight?',
    `Please submit the report by ${blocked} through the official reporting service.`,
    'en',
  );
  equal(data.ok, false, 'ok');
  equal(data.failure_code, 'evidence_required', 'failure');
  equal(data.error.retryable, false, 'retryable');
  equal(data.meta.evidence_policy.reason, 'ambiguous_concrete_value', 'reason');
  equal(JSON.stringify(data.meta.evidence_policy.signal_kinds), JSON.stringify(['calendar_date']), 'signals');
  equal(providerCalls, 1, 'provider calls');
  if (JSON.stringify(data).includes(blocked)) throw new Error('ambiguous blocked date leaked');
});

await check('international model-only phone is rejected without provider fallback', async () => {
  const blocked = '+84 28 1234 5678';
  const { data, providerCalls } = await invoke(
    'How should I report a broken streetlight?',
    `Please call ${blocked} for help with the report.`,
    'en',
  );
  equal(data.failure_code, 'evidence_required', 'failure');
  equal(data.meta.evidence_policy.reason, 'verified_evidence_required', 'reason');
  equal(JSON.stringify(data.meta.evidence_policy.signal_kinds), JSON.stringify(['phone']), 'signals');
  equal(providerCalls, 1, 'provider calls');
  if (JSON.stringify(data).includes(blocked)) throw new Error('blocked international phone leaked');
});

await check('policy metadata and runtime log expose kinds only, never blocked values', async () => {
  const blocked = '062-410-9999';
  const { data } = await invoke(
    '공동주택 문의',
    `대표전화는 ${blocked}입니다. 담당 부서에 문의해 주세요.`,
  );
  equal(data.policy_version, '2026-08-10.2', 'public runtime policy version');
  equal(data.meta.policy_version, '2026-08-10.2', 'meta runtime policy version');
  equal(data.meta.evidence_policy.version, '2026-08-11.1', 'evidence policy version');
  const log = askModule.buildSanitizedRuntimeLog(data);
  equal(log.evidence_policy.decision, 'block', 'log decision');
  equal(JSON.stringify(log.evidence_policy.signal_kinds), JSON.stringify(['phone']), 'log signals');
  if (JSON.stringify(log).includes(blocked)) throw new Error('runtime log leaked blocked value');
});

await check('evidence_required fallback is localized across all five supported locales', async () => {
  const cases = [
    ['ko', '대표전화는 062-410-9999입니다. 담당 부서에 문의해 주세요.'],
    ['en', 'The office phone number is 062-410-9999. Please contact the department for help.'],
    ['vi', 'Số điện thoại của phòng là 062-410-9999. Vui lòng liên hệ phòng để được hướng dẫn.'],
    ['th', 'หมายเลขโทรศัพท์ของสำนักงานคือ 062-410-9999 โปรดติดต่อหน่วยงานเพื่อขอคำแนะนำ'],
    ['id', 'Nomor telepon kantor adalah 062-410-9999. Silakan hubungi kantor untuk informasi lebih lanjut.'],
  ];
  const answers = [];
  for (const [locale, providerAnswer] of cases) {
    const result = await invoke('공동주택 문의', providerAnswer, locale);
    equal(result.data.failure_code, 'evidence_required', `${locale} failure`);
    if (result.data.answer.includes('062-410-9999')) throw new Error(`${locale} leaked blocked phone`);
    answers.push(result.data.answer);
  }
  if (new Set(answers).size !== 5) throw new Error('localized fallbacks were not distinct');
});

await check('provider attempt records evidence rejection without selecting the unsafe draft', async () => {
  const { data, providerCalls } = await invoke(
    '공동주택 문의',
    '공동주택과 대표전화는 062-410-9999입니다. 담당 부서에 문의해 주세요.',
    'ko',
    { KILOCODE_API_KEY: 'second-provider-key', MVP_LLM_ORDER: 'gemini,hy3' },
  );
  equal(data.meta.provider_attempts.length, 1, 'attempt count');
  equal(data.meta.provider_attempts[0].outcome, 'evidence_required', 'attempt outcome');
  equal(data.meta.provider_attempts[0].selected, false, 'selected');
  equal(data.meta.provider_attempts[0].selection_reason, 'evidence_policy_rejected', 'selection reason');
  equal(providerCalls, 1, 'no provider fallback after evidence rejection');
});

globalThis.fetch = ORIGINAL_FETCH;

if (failed) {
  throw new Error(`evidence integration contracts failed: ${failed}/${passed + failed}\n${failures.join('\n')}`);
}

console.log(`\nEvidence integration contracts: ${passed}/${passed + failed} PASS`);
