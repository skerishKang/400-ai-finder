import {
  CONCRETE_SIGNAL_KINDS,
  EVIDENCE_POLICY_VERSION,
  SUPPORTED_INTERNATIONAL_PHONE_COUNTRY_CODES,
  SUPPORTED_MONEY_CURRENCIES,
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

function claimMap(text) {
  return new Map(extractConcreteClaims(text).map((claim) => [`${claim.kind}:${claim.normalized}`, claim]));
}

console.log('\n=== Cloudflare MVP concrete evidence policy contract ===\n');

await check('policy version and closed signal/currency/phone vocabularies are stable', async () => {
  equal(EVIDENCE_POLICY_VERSION, '2026-08-11.1', 'policy version');
  equal(JSON.stringify(CONCRETE_SIGNAL_KINDS), JSON.stringify([
    'phone', 'url', 'clock_time', 'money', 'calendar_date',
  ]), 'signal kinds');
  equal(JSON.stringify(SUPPORTED_MONEY_CURRENCIES), JSON.stringify(['KRW', 'USD', 'EUR']), 'currencies');
  equal(JSON.stringify(SUPPORTED_INTERNATIONAL_PHONE_COUNTRY_CODES), JSON.stringify(['82', '84', '66', '62']), 'phone country codes');
});

await check('only declared verified evidence levels can authorize concrete values', async () => {
  equal(normalizeEvidenceLevel('official_snapshot'), 'canonical_snapshot', 'official snapshot');
  equal(normalizeEvidenceLevel('canonical_snapshot'), 'canonical_snapshot', 'canonical snapshot');
  equal(normalizeEvidenceLevel('verified_live_source'), 'verified_live_source', 'verified live');
  equal(normalizeEvidenceLevel('live_official'), 'model_only', 'undocumented live alias');
  equal(normalizeEvidenceLevel('future_verified_level'), 'model_only', 'unknown level');
  equal(normalizeEvidenceLevel('snapshot_unavailable'), 'model_only', 'unavailable');
  equal(isVerifiedEvidenceLevel('official_snapshot'), true, 'verified snapshot');
  equal(isVerifiedEvidenceLevel('verified_live_source'), true, 'verified live source');
  equal(isVerifiedEvidenceLevel('live_official'), false, 'live_official not verified');
  equal(isVerifiedEvidenceLevel('future_verified_level'), false, 'unknown not verified');
  equal(isVerifiedEvidenceLevel('supplementary_official_citation'), false, 'supplementary only');
});

await check('detector extracts normalized phone URL time KRW money and date claims', async () => {
  const text = [
    '전화 062-410-6841',
    'https://bukgu.gwangju.kr/menu.es?mid=a10101010000#section',
    '09:30',
    '수수료 5,000원',
    '2026년 8월 20일',
  ].join(' / ');
  const map = claimMap(text);
  for (const key of [
    'phone:0624106841',
    'url:https://bukgu.gwangju.kr/menu.es?mid=a10101010000#section',
    'clock_time:09:30',
    'money:KRW:5000',
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

await check('canonical snapshot blocks a hallucinated phone value without leaking it', async () => {
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

await check('bounded currencies preserve identity and plain numbers are not money', async () => {
  const map = claimMap('KRW 50 / USD 50 / EUR 50 / ₩60 / US$ 70 / €80 / reference 999');
  for (const key of [
    'money:KRW:50',
    'money:USD:50',
    'money:EUR:50',
    'money:KRW:60',
    'money:USD:70',
    'money:EUR:80',
  ]) {
    if (!map.has(key)) throw new Error(`missing ${key}`);
  }
  if (Array.from(map.keys()).some((key) => key === 'money:999')) throw new Error('plain number became money');
  if (claimMap('$50').has('money:USD:50')) throw new Error('bare dollar silently treated as USD');
});

await check('model-only KRW USD and EUR values all fail closed', async () => {
  for (const answer of ['수수료는 5,000원입니다.', 'The fee is USD 50.', 'The fee is EUR 50.']) {
    const result = assessConcreteEvidence(answer, { freshnessState: 'model_only', evidence: '' });
    equal(result.ok, false, answer);
    equal(result.reason, 'verified_evidence_required', `${answer} reason`);
  }
});

await check('same-currency verified amount allows but same numeric amount in another currency blocks', async () => {
  equal(assessConcreteEvidence('The fee is USD 50.', verified('Verified fee: USD 50.')).ok, true, 'USD exact');
  equal(assessConcreteEvidence('The fee is EUR 50.', verified('Verified fee: €50.')).ok, true, 'EUR exact');
  equal(assessConcreteEvidence('수수료는 50 KRW입니다.', verified('수수료: ₩50')).ok, true, 'KRW exact');
  equal(assessConcreteEvidence('The fee is USD 50.', verified('Verified fee: EUR 50.')).ok, false, 'cross-currency');
});

await check('bounded calendar forms canonicalize only the same actual date', async () => {
  for (const text of ['2026-08-20', '2026년 8월 20일', 'August 20, 2026', '20/08/2026']) {
    if (!claimMap(text).has('calendar_date:2026-08-20')) throw new Error(`date not canonicalized: ${text}`);
  }
  equal(assessConcreteEvidence('Submit by August 20, 2026.', verified('기준일 2026-08-20')).ok, true, 'English month match');
  equal(assessConcreteEvidence('Submit by 20/08/2026.', verified('기준일 2026년 8월 20일')).ok, true, 'day-first match');
});

await check('ambiguous numeric date is detected and always fails closed without guessing', async () => {
  const claims = extractConcreteClaims('Submit by 08/09/2026.');
  const ambiguous = claims.find((claim) => claim.kind === 'calendar_date');
  if (!ambiguous || ambiguous.ambiguous !== true) throw new Error(`ambiguous date not detected: ${JSON.stringify(claims)}`);
  for (const evidence of ['Date 2026-08-09', 'Date 2026-09-08', 'Date 08/09/2026']) {
    const result = assessConcreteEvidence('Submit by 08/09/2026.', verified(evidence));
    equal(result.ok, false, `ambiguous against ${evidence}`);
    equal(result.reason, 'ambiguous_concrete_value', `ambiguous reason ${evidence}`);
    equal(JSON.stringify(result.signalKinds), JSON.stringify(['calendar_date']), 'signals');
  }
});

await check('unsupported month-first numeric syntax is detected and fails closed rather than guessed', async () => {
  const result = assessConcreteEvidence('Submit by 08/20/2026.', verified('Date 2026-08-20'));
  equal(result.ok, false, 'ok');
  equal(result.reason, 'ambiguous_concrete_value', 'reason');
  equal(JSON.stringify(result.signalKinds), JSON.stringify(['calendar_date']), 'signals');
});

await check('international phone coverage normalizes supported locale country codes', async () => {
  const cases = [
    ['+82 10-1234-5678', '+821012345678'],
    ['+84 (28) 1234-5678', '+842812345678'],
    ['+66 81 234 5678', '+66812345678'],
    ['+62 812-3456-7890', '+6281234567890'],
  ];
  for (const [raw, normalized] of cases) {
    if (!claimMap(raw).has(`phone:${normalized}`)) throw new Error(`missing normalized phone ${raw}`);
  }
});

await check('international model-only phone blocks and verified formatting variant allows', async () => {
  equal(assessConcreteEvidence('Call +82 10-1234-5678 for help.', { freshnessState: 'model_only', evidence: '' }).ok, false, '+82 model only');
  equal(assessConcreteEvidence('Call +84 28 1234 5678 for help.', { freshnessState: 'model_only', evidence: '' }).ok, false, '+84 model only');
  equal(assessConcreteEvidence('Call +84 28 1234 5678 for help.', verified('Phone +84 (28) 1234-5678')).ok, true, 'format equivalent');
});

await check('ordinary long identifiers are not classified as phones', async () => {
  const claims = extractConcreteClaims('Case 12345678901234567890 / tracking 202608201234567890');
  if (claims.some((claim) => claim.kind === 'phone')) throw new Error(`identifier became phone: ${JSON.stringify(claims)}`);
});

await check('AM PM semantics preserve meridiem meaning and 12-hour edges', async () => {
  const map = claimMap('9:00 PM / 9:00 AM / 12:00 AM / 12:00 PM');
  for (const key of ['clock_time:21:00', 'clock_time:09:00', 'clock_time:00:00', 'clock_time:12:00']) {
    if (!map.has(key)) throw new Error(`missing ${key}`);
  }
  equal(assessConcreteEvidence('Office closes at 9:00 PM.', verified('Hours 09:00')).ok, false, '09 mismatch');
  equal(assessConcreteEvidence('Office closes at 9:00 PM.', verified('Hours 21:00')).ok, true, '21 match');
  equal(assessConcreteEvidence('Opens at 12:00 AM.', verified('Open 00:00')).ok, true, '12 AM');
  equal(assessConcreteEvidence('Opens at 12:00 PM.', verified('Open 12:00')).ok, true, '12 PM');
});

await check('URL fragment identity is preserved for matching', async () => {
  const exact = 'https://site.example/page#state-a';
  if (!claimMap(exact).has(`url:${exact}`)) throw new Error('fragment not preserved');
  equal(assessConcreteEvidence('Use https://site.example/page#state-a', verified('Use https://site.example/page')).ok, false, 'fragment vs none');
  equal(assessConcreteEvidence('Use https://site.example/page#state-a', verified('Use https://site.example/page#state-b')).ok, false, 'fragment mismatch');
  equal(assessConcreteEvidence('Use https://site.example/page#state-a', verified('Use https://site.example/page#state-a')).ok, true, 'fragment exact');
});

await check('verified_live_source is supported without treating domain labels as proof', async () => {
  const result = assessConcreteEvidence(
    '확인된 안내 시간은 14:30입니다.',
    verified('공식 확인 시간 14:30', 'verified_live_source'),
  );
  equal(result.ok, true, 'ok');
  equal(result.evidenceLevel, 'verified_live_source', 'level');
});

await check('live_official and unknown evidence state do not authorize matching concrete values', async () => {
  for (const freshnessState of ['live_official', 'future_verified_level']) {
    const result = assessConcreteEvidence('확인 시간은 14:30입니다.', verified('확인 시간 14:30', freshnessState));
    equal(result.ok, false, `${freshnessState} ok`);
    equal(result.reason, 'verified_evidence_required', `${freshnessState} reason`);
    equal(result.evidenceLevel, 'model_only', `${freshnessState} level`);
  }
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

await check('invalid dates and times are not misclassified as valid concrete claims', async () => {
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
