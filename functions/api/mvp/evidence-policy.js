export const EVIDENCE_POLICY_VERSION = '2026-08-10.2';

export const EVIDENCE_LEVELS = Object.freeze([
  'canonical_snapshot',
  'verified_live_source',
  'supplementary_official_citation',
  'model_only',
]);

export const VERIFIED_EVIDENCE_LEVELS = Object.freeze([
  'canonical_snapshot',
  'verified_live_source',
]);

export const EVIDENCE_DECISIONS = Object.freeze([
  'not_assessed',
  'allow',
  'block',
]);

export const EVIDENCE_REASONS = Object.freeze([
  'not_assessed',
  'no_concrete_high_risk_value',
  'verified_evidence_required',
  'concrete_value_not_in_verified_evidence',
  'all_concrete_values_verified',
]);

export const CONCRETE_SIGNAL_KINDS = Object.freeze([
  'phone',
  'url',
  'clock_time',
  'money',
  'calendar_date',
]);

const PHONE_RE = /(?:^|[^0-9])((?:0(?:2|\d{2}))[-.\s]?\d{3,4}[-.\s]?\d{4})(?=$|[^0-9])/g;
const URL_RE = /https?:\/\/[^\s<>"'`]+/gi;
const CLOCK_TIME_RE = /(?:^|[^0-9])([01]?\d|2[0-3]):([0-5]\d)(?=$|[^0-9])/g;
const MONEY_RE = /(?:₩\s*([0-9][0-9,]*)|(?:KRW\s*)([0-9][0-9,]*)|([0-9][0-9,]*)\s*(?:원|won\b))/gi;
const DATE_YMD_RE = /(?:^|[^0-9])(20\d{2})[-./년\s]+(0?[1-9]|1[0-2])[-./월\s]+(0?[1-9]|[12]\d|3[01])(?:일)?(?=$|[^0-9])/g;
const DATE_MD_RE = /(?:^|[^0-9])(0?[1-9]|1[0-2])월\s*(0?[1-9]|[12]\d|3[01])일(?=$|[^0-9])/g;

const FAILURE_MESSAGES = Object.freeze({
  ko: '구체적인 연락처·URL·시간·금액·날짜는 확인된 공식 근거가 부족해 안내하지 않았습니다. 표시된 공식 출처에서 최신 정보를 확인해 주세요.',
  en: 'I did not provide the specific contact, URL, time, fee, or date because verified official evidence was insufficient. Please confirm the latest details in the displayed official source.',
  vi: 'Tôi không cung cấp thông tin cụ thể về liên hệ, URL, thời gian, lệ phí hoặc ngày vì chưa có đủ bằng chứng chính thức đã xác minh. Vui lòng kiểm tra thông tin mới nhất trong nguồn chính thức được hiển thị.',
  th: 'ไม่ได้แสดงข้อมูลติดต่อ URL เวลา ค่าธรรมเนียม หรือวันที่แบบเจาะจง เนื่องจากหลักฐานทางการที่ยืนยันแล้วยังไม่เพียงพอ โปรดตรวจสอบข้อมูลล่าสุดจากแหล่งข้อมูลทางการที่แสดง',
  id: 'Saya tidak memberikan kontak, URL, waktu, biaya, atau tanggal tertentu karena bukti resmi terverifikasi belum memadai. Silakan periksa informasi terbaru pada sumber resmi yang ditampilkan.',
});

function pushUniqueClaim(claims, kind, normalized) {
  if (!kind || !normalized) return;
  if (claims.some((claim) => claim.kind === kind && claim.normalized === normalized)) return;
  claims.push({ kind, normalized });
}

function safeUrl(value) {
  const raw = String(value || '').replace(/[),.;!?\]}]+$/g, '');
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return '';
    parsed.hash = '';
    return parsed.toString();
  } catch (_) {
    return '';
  }
}

function digits(value) {
  return String(value || '').replace(/\D/g, '');
}

function validCalendarDate(year, month, day) {
  const y = Number(year);
  const m = Number(month);
  const d = Number(day);
  if (!Number.isInteger(y) || y < 2000 || y > 2099 || !Number.isInteger(m) || !Number.isInteger(d)) return false;
  const date = new Date(Date.UTC(y, m - 1, d));
  return date.getUTCFullYear() === y && date.getUTCMonth() === m - 1 && date.getUTCDate() === d;
}

function validMonthDay(month, day) {
  const m = Number(month);
  const d = Number(day);
  if (!Number.isInteger(m) || !Number.isInteger(d) || m < 1 || m > 12 || d < 1 || d > 31) return false;
  return validCalendarDate(2024, m, d);
}

export function normalizeEvidenceLevel(value) {
  switch (String(value || '').trim().toLowerCase()) {
    case 'official_snapshot':
    case 'canonical_snapshot':
      return 'canonical_snapshot';
    case 'verified_live_source':
    case 'live_official':
      return 'verified_live_source';
    case 'supplementary_official_citation':
      return 'supplementary_official_citation';
    case 'snapshot_unavailable':
    case 'model_only':
    case 'unavailable':
    default:
      return 'model_only';
  }
}

export function isVerifiedEvidenceLevel(value) {
  return VERIFIED_EVIDENCE_LEVELS.includes(normalizeEvidenceLevel(value));
}

export function extractConcreteClaims(text) {
  const source = String(text || '');
  const claims = [];
  let match;

  PHONE_RE.lastIndex = 0;
  while ((match = PHONE_RE.exec(source)) !== null) {
    const normalized = digits(match[1]);
    if (normalized.length >= 9 && normalized.length <= 11) pushUniqueClaim(claims, 'phone', normalized);
  }

  URL_RE.lastIndex = 0;
  while ((match = URL_RE.exec(source)) !== null) {
    const normalized = safeUrl(match[0]);
    if (normalized) pushUniqueClaim(claims, 'url', normalized);
  }

  CLOCK_TIME_RE.lastIndex = 0;
  while ((match = CLOCK_TIME_RE.exec(source)) !== null) {
    const hour = String(Number(match[1])).padStart(2, '0');
    const minute = match[2];
    pushUniqueClaim(claims, 'clock_time', `${hour}:${minute}`);
  }

  MONEY_RE.lastIndex = 0;
  while ((match = MONEY_RE.exec(source)) !== null) {
    const amount = (match[1] || match[2] || match[3] || '').replace(/,/g, '');
    if (/^\d+$/.test(amount)) pushUniqueClaim(claims, 'money', amount.replace(/^0+(?=\d)/, ''));
  }

  DATE_YMD_RE.lastIndex = 0;
  while ((match = DATE_YMD_RE.exec(source)) !== null) {
    if (!validCalendarDate(match[1], match[2], match[3])) continue;
    pushUniqueClaim(
      claims,
      'calendar_date',
      `${match[1]}-${String(Number(match[2])).padStart(2, '0')}-${String(Number(match[3])).padStart(2, '0')}`,
    );
  }

  DATE_MD_RE.lastIndex = 0;
  while ((match = DATE_MD_RE.exec(source)) !== null) {
    if (!validMonthDay(match[1], match[2])) continue;
    pushUniqueClaim(
      claims,
      'calendar_date',
      `--${String(Number(match[1])).padStart(2, '0')}-${String(Number(match[2])).padStart(2, '0')}`,
    );
  }

  return claims;
}

function claimSet(text) {
  return new Set(extractConcreteClaims(text).map((claim) => `${claim.kind}:${claim.normalized}`));
}

export function assessConcreteEvidence(answer, officialContext = {}) {
  const claims = extractConcreteClaims(answer);
  const signalKinds = CONCRETE_SIGNAL_KINDS.filter((kind) => claims.some((claim) => claim.kind === kind));
  const evidenceLevel = normalizeEvidenceLevel(officialContext.freshnessState);

  if (!claims.length) {
    return {
      ok: true,
      decision: 'allow',
      reason: 'no_concrete_high_risk_value',
      evidenceLevel,
      signalKinds: [],
      policyVersion: EVIDENCE_POLICY_VERSION,
    };
  }

  if (!isVerifiedEvidenceLevel(evidenceLevel)) {
    return {
      ok: false,
      decision: 'block',
      reason: 'verified_evidence_required',
      evidenceLevel,
      signalKinds,
      policyVersion: EVIDENCE_POLICY_VERSION,
    };
  }

  const evidenceText = typeof officialContext.evidence === 'string' ? officialContext.evidence : '';
  const evidenceClaims = claimSet(evidenceText);
  const unsupported = claims.some((claim) => !evidenceClaims.has(`${claim.kind}:${claim.normalized}`));
  if (unsupported) {
    return {
      ok: false,
      decision: 'block',
      reason: 'concrete_value_not_in_verified_evidence',
      evidenceLevel,
      signalKinds,
      policyVersion: EVIDENCE_POLICY_VERSION,
    };
  }

  return {
    ok: true,
    decision: 'allow',
    reason: 'all_concrete_values_verified',
    evidenceLevel,
    signalKinds,
    policyVersion: EVIDENCE_POLICY_VERSION,
  };
}

export function localizedEvidenceRequiredAnswer(locale) {
  const normalized = String(locale || '').trim().toLowerCase();
  return FAILURE_MESSAGES[normalized] || FAILURE_MESSAGES.ko;
}
