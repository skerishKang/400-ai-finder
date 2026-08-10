export const EVIDENCE_POLICY_VERSION = '2026-08-11.1';

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
  'ambiguous_concrete_value',
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

export const SUPPORTED_MONEY_CURRENCIES = Object.freeze(['KRW', 'USD', 'EUR']);
export const SUPPORTED_INTERNATIONAL_PHONE_COUNTRY_CODES = Object.freeze(['82', '84', '66', '62']);

const LOCAL_KR_PHONE_RE = /(?:^|[^0-9])((?:0(?:2|\d{2}))[-.\s]?\d{3,4}[-.\s]?\d{4})(?=$|[^0-9])/g;
const INTERNATIONAL_PHONE_RE = /(?:^|[^\d+])(\+(?:82|84|66|62)(?:[\s().-]*\d){8,11})(?=$|[^\d])/g;
const URL_RE = /https?:\/\/[^\s<>"'`]+/gi;
const CLOCK_TIME_MERIDIEM_RE = /(?:^|[^0-9])((0?[1-9]|1[0-2]):([0-5]\d)\s*([ap])\.?m\.?)(?=$|[^A-Za-z0-9])/gi;
const CLOCK_TIME_24H_RE = /(?:^|[^0-9])([01]?\d|2[0-3]):([0-5]\d)(?=$|[^0-9])/g;
const MONEY_AMOUNT = '([0-9][0-9,]*(?:\\.[0-9]{1,2})?)';
const MONEY_PATTERNS = Object.freeze([
  Object.freeze({ currency: 'KRW', re: new RegExp(`(?:₩\\s*${MONEY_AMOUNT}|\\bKRW\\s*${MONEY_AMOUNT}|${MONEY_AMOUNT}\\s*(?:KRW\\b|원|won\\b))`, 'gi') }),
  Object.freeze({ currency: 'USD', re: new RegExp(`(?:US\\$\\s*${MONEY_AMOUNT}|\\bUSD\\s*${MONEY_AMOUNT}|${MONEY_AMOUNT}\\s*USD\\b)`, 'gi') }),
  Object.freeze({ currency: 'EUR', re: new RegExp(`(?:€\\s*${MONEY_AMOUNT}|\\bEUR\\s*${MONEY_AMOUNT}|${MONEY_AMOUNT}\\s*(?:EUR\\b|€))`, 'gi') }),
]);
const DATE_YMD_RE = /(?:^|[^0-9])(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])(?=$|[^0-9])/g;
const DATE_KO_RE = /(?:^|[^0-9])(20\d{2})년\s*(0?[1-9]|1[0-2])월\s*(0?[1-9]|[12]\d|3[01])일(?=$|[^0-9])/g;
const DATE_MD_RE = /(?:^|[^0-9])(0?[1-9]|1[0-2])월\s*(0?[1-9]|[12]\d|3[01])일(?=$|[^0-9])/g;
const DATE_DMY_RE = /(?:^|[^0-9])(0?[1-9]|[12]\d|3[01])\/(0?[1-9]|1[0-2])\/(20\d{2})(?=$|[^0-9])/g;
const DATE_EN_RE = /\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(0?[1-9]|[12]\d|3[01]),\s*(20\d{2})\b/gi;

const EN_MONTHS = Object.freeze({
  january: 1,
  february: 2,
  march: 3,
  april: 4,
  may: 5,
  june: 6,
  july: 7,
  august: 8,
  september: 9,
  october: 10,
  november: 11,
  december: 12,
});

const FAILURE_MESSAGES = Object.freeze({
  ko: '구체적인 연락처·URL·시간·금액·날짜는 확인된 공식 근거가 부족해 안내하지 않았습니다. 표시된 공식 출처에서 최신 정보를 확인해 주세요.',
  en: 'I did not provide the specific contact, URL, time, fee, or date because verified official evidence was insufficient. Please confirm the latest details in the displayed official source.',
  vi: 'Tôi không cung cấp thông tin cụ thể về liên hệ, URL, thời gian, lệ phí hoặc ngày vì chưa có đủ bằng chứng chính thức đã xác minh. Vui lòng kiểm tra thông tin mới nhất trong nguồn chính thức được hiển thị.',
  th: 'ไม่ได้แสดงข้อมูลติดต่อ URL เวลา ค่าธรรมเนียม หรือวันที่แบบเจาะจง เนื่องจากหลักฐานทางการที่ยืนยันแล้วยังไม่เพียงพอ โปรดตรวจสอบข้อมูลล่าสุดจากแหล่งข้อมูลทางการที่แสดง',
  id: 'Saya tidak memberikan kontak, URL, waktu, biaya, atau tanggal tertentu karena bukti resmi terverifikasi belum memadai. Silakan periksa informasi terbaru pada sumber resmi yang ditampilkan.',
});

function pushUniqueClaim(claims, kind, normalized, options = {}) {
  if (!kind || !normalized) return;
  if (claims.some((claim) => claim.kind === kind && claim.normalized === normalized)) return;
  claims.push({ kind, normalized, ...(options.ambiguous ? { ambiguous: true } : {}) });
}

function safeUrl(value) {
  const raw = String(value || '').replace(/[),.;!?\]}]+$/g, '');
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return '';
    return parsed.toString();
  } catch (_) {
    return '';
  }
}

function digits(value) {
  return String(value || '').replace(/\D/g, '');
}

function normalizedMoneyAmount(value) {
  const raw = String(value || '').replace(/,/g, '');
  if (!/^\d+(?:\.\d{1,2})?$/.test(raw)) return '';
  const [integerPart, fractionalPart = ''] = raw.split('.');
  const integer = integerPart.replace(/^0+(?=\d)/, '') || '0';
  const fraction = fractionalPart.replace(/0+$/, '');
  return fraction ? `${integer}.${fraction}` : integer;
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

function canonicalDate(year, month, day) {
  return `${year}-${String(Number(month)).padStart(2, '0')}-${String(Number(day)).padStart(2, '0')}`;
}

function rangesOverlap(start, end, ranges) {
  return ranges.some(([rangeStart, rangeEnd]) => start < rangeEnd && end > rangeStart);
}

export function normalizeEvidenceLevel(value) {
  switch (String(value || '').trim().toLowerCase()) {
    case 'official_snapshot':
    case 'canonical_snapshot':
      return 'canonical_snapshot';
    case 'verified_live_source':
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
  const internationalPhoneRanges = [];
  const meridiemTimeRanges = [];
  let match;

  INTERNATIONAL_PHONE_RE.lastIndex = 0;
  while ((match = INTERNATIONAL_PHONE_RE.exec(source)) !== null) {
    const raw = match[1];
    const normalizedDigits = digits(raw);
    if (normalizedDigits.length < 10 || normalizedDigits.length > 13) continue;
    const countryCode = SUPPORTED_INTERNATIONAL_PHONE_COUNTRY_CODES.find((code) => normalizedDigits.startsWith(code));
    if (!countryCode) continue;
    const nationalLength = normalizedDigits.length - countryCode.length;
    if (nationalLength < 8 || nationalLength > 11) continue;
    pushUniqueClaim(claims, 'phone', `+${normalizedDigits}`);
    const start = match.index + match[0].indexOf(raw);
    internationalPhoneRanges.push([start, start + raw.length]);
  }

  LOCAL_KR_PHONE_RE.lastIndex = 0;
  while ((match = LOCAL_KR_PHONE_RE.exec(source)) !== null) {
    const raw = match[1];
    const start = match.index + match[0].indexOf(raw);
    if (rangesOverlap(start, start + raw.length, internationalPhoneRanges)) continue;
    const normalized = digits(raw);
    if (normalized.length >= 9 && normalized.length <= 11) pushUniqueClaim(claims, 'phone', normalized);
  }

  URL_RE.lastIndex = 0;
  while ((match = URL_RE.exec(source)) !== null) {
    const normalized = safeUrl(match[0]);
    if (normalized) pushUniqueClaim(claims, 'url', normalized);
  }

  CLOCK_TIME_MERIDIEM_RE.lastIndex = 0;
  while ((match = CLOCK_TIME_MERIDIEM_RE.exec(source)) !== null) {
    const raw = match[1];
    const hour12 = Number(match[2]);
    const minute = match[3];
    const meridiem = match[4].toLowerCase();
    const hour24 = meridiem === 'a'
      ? (hour12 === 12 ? 0 : hour12)
      : (hour12 === 12 ? 12 : hour12 + 12);
    pushUniqueClaim(claims, 'clock_time', `${String(hour24).padStart(2, '0')}:${minute}`);
    const start = match.index + match[0].indexOf(raw);
    meridiemTimeRanges.push([start, start + raw.length]);
  }

  CLOCK_TIME_24H_RE.lastIndex = 0;
  while ((match = CLOCK_TIME_24H_RE.exec(source)) !== null) {
    const raw = `${match[1]}:${match[2]}`;
    const start = match.index + match[0].lastIndexOf(raw);
    if (rangesOverlap(start, start + raw.length, meridiemTimeRanges)) continue;
    const hour = String(Number(match[1])).padStart(2, '0');
    pushUniqueClaim(claims, 'clock_time', `${hour}:${match[2]}`);
  }

  for (const pattern of MONEY_PATTERNS) {
    pattern.re.lastIndex = 0;
    while ((match = pattern.re.exec(source)) !== null) {
      const amount = match.slice(1).find((value) => typeof value === 'string' && value.length) || '';
      const normalizedAmount = normalizedMoneyAmount(amount);
      if (normalizedAmount) pushUniqueClaim(claims, 'money', `${pattern.currency}:${normalizedAmount}`);
    }
  }

  DATE_YMD_RE.lastIndex = 0;
  while ((match = DATE_YMD_RE.exec(source)) !== null) {
    if (!validCalendarDate(match[1], match[2], match[3])) continue;
    pushUniqueClaim(claims, 'calendar_date', canonicalDate(match[1], match[2], match[3]));
  }

  DATE_KO_RE.lastIndex = 0;
  while ((match = DATE_KO_RE.exec(source)) !== null) {
    if (!validCalendarDate(match[1], match[2], match[3])) continue;
    pushUniqueClaim(claims, 'calendar_date', canonicalDate(match[1], match[2], match[3]));
  }

  DATE_EN_RE.lastIndex = 0;
  while ((match = DATE_EN_RE.exec(source)) !== null) {
    const month = EN_MONTHS[match[1].toLowerCase()];
    if (!month || !validCalendarDate(match[3], month, match[2])) continue;
    pushUniqueClaim(claims, 'calendar_date', canonicalDate(match[3], month, match[2]));
  }

  DATE_DMY_RE.lastIndex = 0;
  while ((match = DATE_DMY_RE.exec(source)) !== null) {
    const first = Number(match[1]);
    const second = Number(match[2]);
    const year = match[3];
    const dmyValid = validCalendarDate(year, second, first);
    const mdyValid = validCalendarDate(year, first, second);
    if (first <= 12 && second <= 12 && dmyValid && mdyValid) {
      pushUniqueClaim(claims, 'calendar_date', `ambiguous:${String(first).padStart(2, '0')}/${String(second).padStart(2, '0')}/${year}`, { ambiguous: true });
      continue;
    }
    if (first > 12 && dmyValid) {
      pushUniqueClaim(claims, 'calendar_date', canonicalDate(year, second, first));
      continue;
    }
    if (mdyValid) {
      pushUniqueClaim(claims, 'calendar_date', `unsupported_numeric:${String(first).padStart(2, '0')}/${String(second).padStart(2, '0')}/${year}`, { ambiguous: true });
    }
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
  return new Set(
    extractConcreteClaims(text)
      .filter((claim) => !claim.ambiguous)
      .map((claim) => `${claim.kind}:${claim.normalized}`),
  );
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

  if (claims.some((claim) => claim.ambiguous)) {
    return {
      ok: false,
      decision: 'block',
      reason: 'ambiguous_concrete_value',
      evidenceLevel,
      signalKinds,
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
