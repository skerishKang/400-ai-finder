// functions/api/mvp/ask.js
// Gemini 3.1 Flash Lite LLM 프록시 — Cloudflare Pages Functions
// API 키는 GEMINI_API_KEY secrets에 저장

/** 허용된 action 값 목록 (src/llm/bukgu_mvp_router.py의 MVP_ACTIONS와 동일) */
var VALID_ACTIONS = ['illegal_parking', 'housing_department', 'bulky_waste', 'passport_guidance', 'unmanned_kiosk', 'none'];

export async function onRequest(context) {
  const { request, env } = context;

  // CORS headers
  // CORS: cgbukku.pages.dev만 허용, 개발환경(localhost)도 허용
  const ALLOWED_ORIGINS = ['https://cgbukku.pages.dev', 'http://localhost:8000', 'http://127.0.0.1:8000'];
  const origin = request.headers.get('Origin') || '';
  const corsOrigin = ALLOWED_ORIGINS.includes(origin) ? origin : 'https://cgbukku.pages.dev';
  const headers = {
    'Access-Control-Allow-Origin': corsOrigin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Vary': 'Origin',
    'Content-Type': 'application/json',
  };

  // Preflight
  if (request.method === 'OPTIONS') {
    return new Response(null, { headers });
  }

  if (request.method !== 'POST') {
    return new Response(JSON.stringify({ ok: false, error: 'Method not allowed' }), {
      status: 405, headers
    });
  }

  try {
    const body = await request.json();

    // Body 타입 검증 — object가 아니면 fail-closed
    if (!body || typeof body !== 'object' || Array.isArray(body)) {
      return new Response(JSON.stringify({
        ok: false, answer: '잘못된 요청 형식입니다.',
        action: 'none', confidence: 0.0,
        provider: 'gemini', model: 'gemini-3.1-flash-lite', failure_code: 'invalid_input'
      }), { status: 200, headers });
    }

    // 질문 타입 검증 — 문자열이 아니면 fail-closed
    if (body.question !== undefined && typeof body.question !== 'string') {
      return new Response(JSON.stringify({
        ok: false, answer: '잘못된 요청 형식입니다.',
        action: 'none', confidence: 0.0,
        provider: 'gemini', model: 'gemini-3.1-flash-lite', failure_code: 'invalid_input'
      }), { status: 200, headers });
    }

    // 질문 길이 제한 (300자 초과 시 fail-closed)
    const q = (body.question || '').trim();
    if (q.length > 300) {
      return new Response(JSON.stringify({
        ok: false, answer: '질문이 너무 깁니다. 300자 이내로 입력해 주세요.',
        action: 'none', confidence: 0.0,
        provider: 'gemini', model: 'gemini-3.1-flash-lite', failure_code: 'invalid_input'
      }), { status: 200, headers });
    }

    if (!q) {
      return new Response(JSON.stringify({ ok: false, error: 'Missing question' }), {
        status: 400, headers
      });
    }

    const apiKey = env.GEMINI_API_KEY;
    if (!apiKey) {
      return new Response(JSON.stringify({
        ok: false, answer: 'API key not configured.',
        action: 'none', confidence: 0.0,
        provider: 'gemini', model: 'gemini-3.1-flash-lite', failure_code: 'config_error'
      }), { status: 200, headers });
    }

    const systemPrompt = `당신은 광주광역시 북구청 민원 안내 직원입니다. 반드시 아래 JSON 형식으로만 응답하세요:

{"action": "(action)", "answer": "(간결한 한국어 1~2문장)", "confidence": (0.0~1.0)}

action 목록: illegal_parking(불법주정차/주차단속), housing_department(공동주택/아파트), bulky_waste(대형폐기물/폐기물), passport_guidance(여권발급/여권), unmanned_kiosk(무인민원발급기/민원서류), none(기타/인사/일반)

규칙: 북구청 직원처럼 친절하고 정중하게. answer는 간결하게 1~2문장. JSON 외 텍스트 금지.`;

    const response = await fetch('https://generativelanguage.googleapis.com/v1beta/openai/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'gemini-3.1-flash-lite',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: q }
        ],
        temperature: 0.1,
        max_tokens: 500,
      }),
    });

    if (!response.ok) {
      // Consumed but not exposed (security: no raw body leak)
      await response.text();
      return new Response(JSON.stringify({
        ok: false, answer: 'AI 응답을 가져오지 못했습니다.',
        action: 'none', confidence: 0.0,
        provider: 'gemini', model: 'gemini-3.1-flash-lite',
        failure_code: 'upstream_error'
      }), { status: 200, headers });
    }

    const data = await response.json();
    const content = data?.choices?.[0]?.message?.content || '';

    // Try to parse JSON from the response
    let action = 'none', answer = '', confidence = 0.0;
    let failureCode = '';
    if (!content) {
      answer = '죄송합니다. 답변을 준비하지 못했습니다. 다른 질문을 해 주세요.';
    } else {
      try {
        const parsed = JSON.parse(content);

        // Action allowlist validation — 알 수 없는 action은 'none'으로 강제
        action = VALID_ACTIONS.includes(parsed.action) ? parsed.action : 'none';

        // Answer blank fail-closed
        answer = (parsed.answer || '').trim();
        if (!answer) {
          answer = '죄송합니다. 답변을 준비하지 못했습니다. 다른 질문을 해 주세요.';
        }

        // Confidence clamp (0.0 ~ 1.0)
        confidence = typeof parsed.confidence === 'number' ? Math.max(0, Math.min(1, parsed.confidence)) : 0.0;
      } catch {
        // Non-JSON response: use raw content (LLM may not always output valid JSON)
        answer = content || '죄송합니다. 답변을 준비하지 못했습니다. 다른 질문을 해 주세요.';
      }
    }

    return new Response(JSON.stringify({
      ok: true, question: q, answer, action, confidence,
      provider: 'gemini', model: 'gemini-3.1-flash-lite', failure_code: failureCode
    }), { status: 200, headers });

  } catch (error) {
    return new Response(JSON.stringify({
      ok: false, answer: '서버 오류가 발생했습니다.',
      action: 'none', confidence: 0.0,
      provider: 'gemini', model: 'gemini-3.1-flash-lite', failure_code: 'internal_error'
    }), { status: 200, headers });
  }
}
