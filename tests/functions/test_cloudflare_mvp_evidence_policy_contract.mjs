import {
  CONCRETE_SIGNAL_KINDS,
  EVIDENCE_POLICY_VERSION,
  assessConcreteEvidence,
  extractConcreteClaims,
  isVerifiedEvidenceLevel,
  localizedEvidenceRequiredAnswer,
  normalizeEvidenceLevel,
} from '../../functions/api/mvp/evidence-policy.js';

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

function verified(evidence, freshnessState = 'official_snapshot') {
  return { freshnessState, evidence };
}

console.log('\n=== Cloudflare MVP concrete evidence policy contract ===\n');

await check('policy version and closed signal vocabulary are stable', async () => {
  equal(EVIDENCE_POLICY_VERSION, '2026-08-10.2', 'policy version');
  equal(JSON.stringify(CONCRETE_SIGNAL_KINDS), JSON.stringify([
    'phone', 'url', 'clock_time', 'money', 'calendar_date',
  ]), 'signal kinds');
});

await check('legacy freshness states map to explicit evidence levels', async () => {
  equal(normalizeEvidenceLevel('official_snapshot'), 'canonical_snapshot', 'official snapshot');
  equal(normalizeEvidenceLevel('canonical_snapshot'), 'canonical_snapshot', 'canonical snapshot');
  equal(normalizeEvidenceLevel('verified_live_source'), 'verified_live_source', 'live');
  equal(normalizeEvidenceLevel('snapshot_unavailable'), 'model_only', 'unavailable');
  equal(normalizeEvidenceLevel('model_only'), 'model_only', 'model');
  equal(isVerifiedEvidenceLevel('official_snapshot'), true, 'verified snapshot');
  equal(isVerifiedEvidenceLevel('supplementary_official_citation'), false, 'supplementary only');
});

await check('detector extracts normalized phone URL time money and date claims', async () => {
  const text = [
    '전화 062-410-6841',
    'https://bukgu.gwangju.kr/menu.es?mid=a10101010000',
    '09:30',
    '수수료 5,000원',
    '2026년 8월 20일',
  ].join(' / ');
  const claims = extractConcreteClaims(text);
  const map = new Map(claims.map((claim) => [`${claim.kind}:${claim.normalized}`, true]));
  for (const key of [
    'phone:0624106841',
    'url:https://bukgu.gwangju.kr/menu.es?mid=a10101010000',
    'clock_time:09:30',
    'money:5000',
    'calendar_date:2026-08-20',
  ]) {
    if (!map.has(key)) throw new Error(`missing normalized claim ${key}`);
  }
});

await check('general guidance with no concrete high-risk values remains allowed', async () => {
  const result = assessConcreteEvidence(
    '공동주택 관련 문의는 담당 부서와 공식 홈페이지에서 확인해 주세요.',
    { freshnessState: 'model_only', evidence: '' },
  );
  equal(result.ok, true, 'ok');
  equal(result.reason, 'no_concrete_high_risk_value', 'reason');
  equal(result.evidenceLevel, 'model_only', 'level');
  equal(result.signalKinds.length, 0, 'signals');
});

await check('canonical snapshot allows a phone value present in evidence', async () => {
  const result = assessConcreteEvidence(
    '공동주택과 대표전화는 062-410-6841입니다.',
    verified('부서 대표전화: 062-410-6841\n공식 안내입니다.'),
  );
  equal(result.ok, true, 'ok');
  equal(result.reason, 'all_concrete_values_verified', 'reason');
  equal(result.evidenceLevel, 'canonical_snapshot', 'level');
  equal(JSON.stringify(result.signalKinds), JSON.stringify(['phone']), 'signals');
});

await check('canonical snapshot blocks a hallucinated phone value', async () => {
  const raw = '062-410-9999';
  const result = assessConcreteEvidence(
    `공동주택과 대표전화는 ${raw}입니다.`,
    verified('부서 대표전화: 062-410-6841'),
  );
  equal(result.ok, false, 'ok');
  equal(result.reason, 'concrete_value_not_in_verified_evidence', 'reason');
  equal(result.decision, 'block', 'decision');
  if (JSON.stringify(result).includes(raw)) throw new Error('decision leaked blocked phone value');
});

await check('every detected concrete value must be present in verified evidence', async () => {
  const result = assessConcreteEvidence(
    '전화는 062-410-6841이고 운영시간은 09:00입니다.',
    verified('대표전화 062-410-6841 / 운영시간 10:00'),
  );
  equal(result.ok, false, 'ok');
  equal(result.reason, 'concrete_value_not_in_verified_evidence', 'reason');
  equal(JSON.stringify(result.signalKinds), JSON.stringify(['phone', 'clock_time']), 'signals');
});

await check('verified evidence matches normalized money and calendar formatting', async () => {
  const result = assessConcreteEvidence(
    '수수료는 5000원이며 2026-08-20에 확인하세요.',
    verified('수수료 5,000원 / 기준일 2026년 8월 20일'),
  );
  equal(result.ok, true, 'ok');
  equal(result.reason, 'all_concrete_values_verified', 'reason');
});

await check('model-only concrete values fail closed', async () => {
  const result = assessConcreteEvidence(
    '업무 시간은 09:00이며 자세한 내용은 https://example.com 에서 확인하세요.',
    { freshnessState: 'snapshot_unavailable', evidence: '' },
  );
  equal(result.ok, false, 'ok');
  equal(result.reason, 'verified_evidence_required', 'reason');
  equal(result.evidenceLevel, 'model_only', 'level');
});

await check('official-domain supplementary citations never promote evidence', async () => {
  const result = assessConcreteEvidence(
    '공식 안내 URL은 https://bukgu.gwangju.kr/example 입니다.',
    {
      freshnessState: 'snapshot_unavailable',
      evidence: '',
      sources: [{ url: 'https://bukgu.gwangju.kr/example', official: true }],
    },
  );
  equal(result.ok, false, 'ok');
  equal(result.reason, 'verified_evidence_required', 'reason');
  equal(result.evidenceLevel, 'model_only', 'level');
});

await check('verified_live_source is supported without treating domain labels as proof', async () => {
  const result = assessConcreteEvidence(
    '확인된 안내 시간은 14:30입니다.',
    verified('공식 확인 시간 14:30', 'verified_live_source'),
  );
  equal(result.ok, true, 'ok');
  equal(result.evidenceLevel, 'verified_live_source', 'level');
});

await check('invalid dates and times are not misclassified as concrete claims', async () => {
  const claims = extractConcreteClaims('99:99 / 2026-02-31 / 2026-13-01');
  if (claims.some((claim) => claim.kind === 'clock_time' || claim.kind === 'calendar_date')) {
    throw new Error(`invalid temporal value classified: ${JSON.stringify(claims)}`);
  }
});

await check('localized evidence-required fallback exists for all supported locales', async () => {
  const messages = ['ko', 'en', 'vi', 'th', 'id'].map((locale) => localizedEvidenceRequiredAnswer(locale));
  for (let i = 0; i < messages.length; i += 1) {
    if (typeof messages[i] !== 'string' || messages[i].length < 40) {
      throw new Error(`missing localized fallback at index ${i}`);
    }
  }
  if (new Set(messages).size !== 5) throw new Error('localized fallbacks are not distinct');
  equal(localizedEvidenceRequiredAnswer('unknown'), messages[0], 'unknown locale falls back to ko');
});

if (failed) {
  throw new Error(`evidence policy contracts failed: ${failed}/${passed + failed}\n${failures.join('\n')}`);
}

console.log(`\nEvidence policy contracts: ${passed}/${passed + failed} PASS`);
