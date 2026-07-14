export const TEMPORAL_TERMS = [
  '현재', '최신', '지금', '오늘', '최근', '이번 주', '이번 달',
  '현 구청장', '공지', '채용공고', '행사 일정', '모집 중', '시행 중'
];

export function classifyTemporalIntent(question) {
  const normalized = String(question || '').replace(/\s+/g, ' ').trim().toLowerCase();
  for (const term of TEMPORAL_TERMS) {
    if (normalized.includes(term.toLowerCase())) {
      return 'temporal';
    }
  }
  return 'none';
}

function isOfficialHostname(hostname) {
  const lower = hostname.toLowerCase();
  return lower === 'bukgu.gwangju.kr' || lower.endsWith('.bukgu.gwangju.kr');
}

export async function fetchOfficialPage(urlStr) {
  let url;
  try {
    url = new URL(urlStr);
  } catch (_) {
    return { ok: false, failureCode: 'invalid_url' };
  }
  if (url.protocol !== 'https:' || !isOfficialHostname(url.hostname)) {
    return { ok: false, failureCode: 'invalid_domain' };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 3000);

  let response;
  try {
    response = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'User-Agent': 'Bukgu-MVP-Freshness-Bot/1.0',
        'Accept': 'text/html',
      },
      redirect: 'follow',
      signal: controller.signal,
    });
  } catch (error) {
    clearTimeout(timeoutId);
    return { ok: false, failureCode: error.name === 'AbortError' ? 'timeout' : 'network_error' };
  }
  clearTimeout(timeoutId);

  try {
    const finalUrl = new URL(response.url);
    if (!isOfficialHostname(finalUrl.hostname)) {
      return { ok: false, failureCode: 'invalid_domain' };
    }
  } catch (_) {
    return { ok: false, failureCode: 'invalid_url' };
  }

  if (!response.ok) {
    return { ok: false, failureCode: 'upstream_error' };
  }
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('text/html')) {
    return { ok: false, failureCode: 'invalid_content_type' };
  }

  const text = await response.text();
  if (text.length > 5 * 1024 * 1024) {
    return { ok: false, failureCode: 'oversized_response' };
  }

  return { ok: true, html: text, finalUrl: response.url };
}

export function extractFacts(html, url) {
  const plainText = String(html || '')
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<(?:br|hr)\s*\/?>/gi, '\n')
    .replace(/<\/(?:p|li|tr|h[1-6]|section|article|div)>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  const facts = [];

  const jurMatch = plainText.match(/([가-힣]+통합특별시\s*북구)/);
  if (jurMatch) {
    facts.push(`jurisdiction: ${jurMatch[1]}`);
  }

  const mayorMatch = plainText.match(/북구청장\s+([가-힣]{2,4})|구청장\s*:\s*([가-힣]{2,4})/);
  if (mayorMatch) {
    facts.push(`mayor: ${mayorMatch[1] || mayorMatch[2]}`);
  } else {
    const m2 = plainText.match(/([가-힣]{2,4})\s*구청장/);
    if (m2 && !["현", "전", "부", "신임", "전임"].includes(m2[1])) {
       facts.push(`mayor: ${m2[1]}`);
    }
  }

  // extract simple search result snippets (up to 3) if it's a search page
  if (url && url.includes('Search.jsp')) {
    const resultsMatch = plainText.match(/검색결과[:\s]*(.*)/);
    if (resultsMatch) {
       facts.push(`search_results: ${resultsMatch[1].slice(0, 500)}`);
    } else if (plainText.length > 0) {
       // if it's a search page, we can just return the body
       facts.push(`content: ${plainText.slice(0, 500)}`);
    }
  }

  return facts.length > 0 ? facts.join('\n') : '';
}

// Simple in-memory cache
const CACHE_TTL_MS = 60 * 1000;
const requestCache = new Map();

export async function retrieveLiveFreshness(question) {
  const now = Date.now();
  const retrievedAt = new Date(now).toISOString();
  
  let targetUrl = 'https://bukgu.gwangju.kr/';
  if (question.includes('공지') || question.includes('채용') || question.includes('행사') || question.includes('모집') || question.includes('시행')) {
    let query = '공지';
    if (question.includes('채용')) query = '채용';
    if (question.includes('행사')) query = '행사';
    if (question.includes('모집')) query = '모집';
    targetUrl = 'https://search.bukgu.gwangju.kr/RSA/front/Search.jsp?qt=' + encodeURIComponent(query);
  }

  const cacheKey = targetUrl;
  const cached = requestCache.get(cacheKey);
  if (cached && now - cached.timestamp < CACHE_TTL_MS) {
    return {
      ok: true,
      evidence: cached.evidence,
      sourceTitle: '북구청 공식 홈페이지',
      sourceUrl: cached.finalUrl,
      searchQueries: [targetUrl],
      retrievedAt,
    };
  }

  const fetchResult = await fetchOfficialPage(targetUrl);
  if (!fetchResult.ok) {
    return { ok: false, failureCode: fetchResult.failureCode, retrievedAt };
  }

  const evidence = extractFacts(fetchResult.html, fetchResult.finalUrl);
  
  if (!evidence || evidence.trim() === '') {
    return { ok: false, failureCode: 'missing_fact', retrievedAt };
  }

  requestCache.set(cacheKey, {
    timestamp: now,
    evidence,
    finalUrl: fetchResult.finalUrl
  });

  return {
    ok: true,
    evidence,
    sourceTitle: '북구청 공식 홈페이지',
    sourceUrl: fetchResult.finalUrl,
    searchQueries: [targetUrl],
    retrievedAt,
  };
}
export function _clearCache() { requestCache.clear(); }
