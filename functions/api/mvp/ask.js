// Cloudflare Pages Function for the live Buk-gu civic assistant.
// GEMINI_API_KEY is stored as a Pages secret; no user question is persisted.

export const VALID_ACTIONS = Object.freeze([
  'illegal_parking',
  'housing_department',
  'bulky_waste',
  'passport_guidance',
  'unmanned_kiosk',
  'streetlight_report',
  'litter_ai_assist',
  'none',
]);

export const DEFAULT_MODEL = 'gemini-3.5-flash';

const ACTION_RULES = Object.freeze([
  { action: 'illegal_parking', terms: ['불법 주정차', '불법주정차', '주차 단속', '주정차 신고'] },
  { action: 'housing_department', terms: ['공동주택', '아파트 부서', '아파트 문의'] },
  { action: 'bulky_waste', terms: ['대형폐기물', '매트리스', '가구 버리', '침대 버리'] },
  { action: 'passport_guidance', terms: ['여권'] },
  { action: 'unmanned_kiosk', terms: ['무인민원발급기', '무인 발급기'] },
  { action: 'streetlight_report', terms: ['가로등 고장', '가로등 신고', '가로등이 고장'] },
  { action: 'litter_ai_assist', terms: ['쓰레기 무단투기', '무단 투기 신고', '방치 쓰레기 신고'] },
]);

function jsonResponse(payload, status, headers) {
  return new Response(JSON.stringify(payload), { status, headers });
}

function buildHeaders(request) {
  const productionOrigin = 'https://cgbukku.pages.dev';
  const origin = request.headers.get('Origin') || '';
  let allowedOrigin = productionOrigin;

  try {
    const parsed = new URL(origin);
    const isPagesOrigin = parsed.protocol === 'https:' &&
      (parsed.hostname === 'cgbukku.pages.dev' || parsed.hostname.endsWith('.cgbukku.pages.dev'));
    const isLocal = (parsed.protocol === 'http:' || parsed.protocol === 'https:') &&
      (parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1');
    if (isPagesOrigin || isLocal) allowedOrigin = origin;
  } catch (_) {
    // Missing or malformed Origin uses the production origin.
  }

  return {
    'Access-Control-Allow-Origin': allowedOrigin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Cache-Control': 'no-store',
    'Vary': 'Origin',
    'Content-Type': 'application/json; charset=utf-8',
  };
}

export function classifyAction(question) {
  const normalized = String(question || '').replace(/\s+/g, ' ').trim().toLowerCase();
  for (const rule of ACTION_RULES) {
    if (rule.terms.some((term) => normalized.includes(term.toLowerCase()))) {
      return rule.action;
    }
  }
  return 'none';
}

function formatSeoulTime(date) {
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date);
}

function buildGroundedPrompt(question, currentTime) {
  return [
    '당신은 광주 북구 주민을 돕는 "북구 도우미"입니다.',
    `현재 대한민국 표준시각은 ${currentTime}입니다. 이 시각을 기준으로 답하세요.`,
    '',
    '반드시 Google 검색 도구로 현재 정보를 확인하세요.',
    '북구 행정, 일정, 공고, 연락처, 비용, 신청 방법에 관한 질문은 bukgu.gwangju.kr,',
    'search.bukgu.gwangju.kr 및 대한민국 공식 공공기관 도메인의 최신 자료를 우선 사용하세요.',
    '가능하면 site:bukgu.gwangju.kr 또는 site:search.bukgu.gwangju.kr 검색을 먼저 수행하세요.',
    '현재 공식 근거를 찾지 못했거나 자료가 서로 다르면 확인하지 못했다고 분명히 말하고 추측하지 마세요.',
    '주민에게 바로 도움이 되도록 자연스러운 한국어 2~5문장으로 답하세요.',
    '링크 목록은 시스템이 별도로 표시하므로 답변 본문에 긴 URL을 나열하지 마세요.',
    '',
    `주민 질문: ${question}`,
  ].join('\n');
}

function isOfficialUrl(value) {
  try {
    const hostname = new URL(value).hostname.toLowerCase();
    return hostname === 'bukgu.gwangju.kr' ||
      hostname.endsWith('.bukgu.gwangju.kr') ||
      hostname.endsWith('.gwangju.kr') ||
      hostname.endsWith('.go.kr') ||
      hostname.endsWith('.gov.kr');
  } catch (_) {
    return false;
  }
}

function safeSource(annotation) {
  if (!annotation || annotation.type !== 'url_citation' || typeof annotation.url !== 'string') {
    return null;
  }
  try {
    const url = new URL(annotation.url);
    if (url.protocol !== 'https:' && url.protocol !== 'http:') return null;
    return {
      title: typeof annotation.title === 'string' && annotation.title.trim()
        ? annotation.title.trim().slice(0, 160)
        : url.hostname,
      url: url.toString(),
      official: isOfficialUrl(url.toString()),
    };
  } catch (_) {
    return null;
  }
}

export function parseGroundedInteraction(data) {
  const textParts = [];
  const sources = [];
  const searchQueries = [];
  const seenSources = new Set();
  const steps = data && Array.isArray(data.steps) ? data.steps : [];

  for (const step of steps) {
    if (step && step.type === 'google_search_call') {
      const queries = step.arguments && Array.isArray(step.arguments.queries)
        ? step.arguments.queries
        : [];
      for (const query of queries) {
        if (typeof query === 'string' && query.trim()) searchQueries.push(query.trim());
      }
    }
    if (!step || step.type !== 'model_output' || !Array.isArray(step.content)) continue;
    for (const block of step.content) {
      if (!block || block.type !== 'text') continue;
      if (typeof block.text === 'string' && block.text.trim()) textParts.push(block.text.trim());
      const annotations = Array.isArray(block.annotations) ? block.annotations : [];
      for (const annotation of annotations) {
        const source = safeSource(annotation);
        if (!source || seenSources.has(source.url)) continue;
        seenSources.add(source.url);
        sources.push(source);
      }
    }
  }

  return {
    answer: textParts.join('\n').trim(),
    sources: sources.slice(0, 5),
    searchQueries: searchQueries.slice(0, 5),
  };
}

export async function onRequest(context) {
  const { request, env } = context;
  const headers = buildHeaders(request);
  const model = typeof env.GEMINI_MODEL === 'string' && env.GEMINI_MODEL.trim()
    ? env.GEMINI_MODEL.trim()
    : DEFAULT_MODEL;

  if (request.method === 'OPTIONS') return new Response(null, { status: 200, headers });
  if (request.method !== 'POST') {
    return jsonResponse({ ok: false, error: 'Method not allowed' }, 405, headers);
  }

  let body;
  try {
    body = await request.json();
  } catch (_) {
    return jsonResponse({ ok: false, answer: '잘못된 요청 형식입니다.', action: 'none', confidence: 0.0, provider: 'gemini', model, failure_code: 'invalid_input' }, 200, headers);
  }

  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return jsonResponse({ ok: false, answer: '잘못된 요청 형식입니다.', action: 'none', confidence: 0.0, provider: 'gemini', model, failure_code: 'invalid_input' }, 200, headers);
  }
  if (!Object.prototype.hasOwnProperty.call(body, 'question')) {
    return jsonResponse({ ok: false, error: 'Missing question' }, 400, headers);
  }
  if (typeof body.question !== 'string') {
    return jsonResponse({ ok: false, answer: '잘못된 요청 형식입니다.', action: 'none', confidence: 0.0, provider: 'gemini', model, failure_code: 'invalid_input' }, 200, headers);
  }

  const question = body.question.trim();
  if (!question) return jsonResponse({ ok: false, error: 'Missing question' }, 400, headers);
  if (question.length > 300) {
    return jsonResponse({ ok: false, answer: '질문이 너무 깁니다. 300자 이내로 입력해 주세요.', action: 'none', confidence: 0.0, provider: 'gemini', model, failure_code: 'invalid_input' }, 200, headers);
  }

  const action = classifyAction(question);
  const retrievedAt = new Date();
  const currentTime = formatSeoulTime(retrievedAt);

  if (!env.GEMINI_API_KEY) {
    return jsonResponse({
      ok: false,
      question,
      answer: '현재 AI 안내 설정을 확인하고 있습니다.',
      action,
      confidence: action === 'none' ? 0.0 : 1.0,
      provider: 'gemini',
      model,
      failure_code: 'config_error',
      retrieved_at: retrievedAt.toISOString(),
      freshness_state: 'unavailable',
      source_url: '',
      sources: [],
    }, 200, headers);
  }

  try {
    const upstream = await fetch('https://generativelanguage.googleapis.com/v1beta/interactions', {
      method: 'POST',
      headers: {
        'x-goog-api-key': env.GEMINI_API_KEY,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model,
        input: buildGroundedPrompt(question, currentTime),
        tools: [{ type: 'google_search' }],
        store: false,
      }),
    });

    if (!upstream.ok) {
      await upstream.text();
      return jsonResponse({
        ok: false,
        question,
        answer: '최신 공식 정보를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
        action,
        confidence: action === 'none' ? 0.0 : 1.0,
        provider: 'gemini',
        model,
        failure_code: 'upstream_error',
        retrieved_at: retrievedAt.toISOString(),
        freshness_state: 'unavailable',
        source_url: '',
        sources: [],
      }, 200, headers);
    }

    const parsed = parseGroundedInteraction(await upstream.json());
    if (!parsed.answer) {
      return jsonResponse({
        ok: false,
        question,
        answer: '최신 공식 정보를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
        action,
        confidence: action === 'none' ? 0.0 : 1.0,
        provider: 'gemini',
        model,
        failure_code: 'empty_response',
        retrieved_at: retrievedAt.toISOString(),
        freshness_state: 'unavailable',
        source_url: '',
        sources: [],
      }, 200, headers);
    }

    const officialSources = parsed.sources.filter((source) => source.official);
    const freshnessState = officialSources.length
      ? 'live_official'
      : (parsed.sources.length ? 'live_web' : 'model_only');
    const primarySource = officialSources[0] || parsed.sources[0] || null;

    return jsonResponse({
      ok: true,
      question,
      answer: parsed.answer,
      action,
      confidence: action === 'none' ? 0.72 : 1.0,
      provider: 'gemini',
      model,
      failure_code: '',
      current_time: currentTime,
      retrieved_at: retrievedAt.toISOString(),
      freshness_state: freshnessState,
      source_url: primarySource ? primarySource.url : '',
      sources: parsed.sources,
      search_queries: parsed.searchQueries,
    }, 200, headers);
  } catch (_) {
    return jsonResponse({
      ok: false,
      question,
      answer: '서버 오류로 최신 공식 정보를 확인하지 못했습니다.',
      action,
      confidence: action === 'none' ? 0.0 : 1.0,
      provider: 'gemini',
      model,
      failure_code: 'internal_error',
      retrieved_at: retrievedAt.toISOString(),
      freshness_state: 'unavailable',
      source_url: '',
      sources: [],
    }, 200, headers);
  }
}
