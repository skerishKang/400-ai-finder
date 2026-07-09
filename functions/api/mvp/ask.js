// functions/api/mvp/ask.js
// hy3 LLM 프록시 — Cloudflare Pages Functions
// API 키는 KILOCODE_API_KEY secrets에 저장

/** 허용된 action 값 목록 (src/llm/bukgu_mvp_router.py의 MVP_ACTIONS와 동일) */
var VALID_ACTIONS = ['illegal_parking', 'housing_department', 'bulky_waste', 'move_in_report', 'public_health_center', 'none'];

export async function onRequest(context) {
  const { request, env } = context;

  // CORS headers
  // TODO: production 시 CORS를 cgbukku.pages.dev로 제한
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
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

    // 질문 길이 제한 (300자 초과 시 fail-closed)
    const q = (body.question || '').trim();
    if (q.length > 300) {
      return new Response(JSON.stringify({
        ok: false, answer: '질문이 너무 깁니다. 300자 이내로 입력해 주세요.',
        action: 'none', confidence: 0.0,
        provider: 'kilocode', model: 'tencent/hy3:free', failure_code: 'invalid_input'
      }), { status: 200, headers });
    }

    if (!q) {
      return new Response(JSON.stringify({ ok: false, error: 'Missing question' }), {
        status: 400, headers
      });
    }

    const apiKey = env.KILOCODE_API_KEY;
    if (!apiKey) {
      return new Response(JSON.stringify({
        ok: false, answer: 'API key not configured.',
        action: 'none', confidence: 0.0,
        provider: 'kilocode', model: 'tencent/hy3:free', failure_code: 'config_error'
      }), { status: 200, headers });
    }

    const systemPrompt = `당신은 광주광역시 북구청 정보 안내 도우미입니다. 사용자의 질문에 친절하게 한국어로 답변하세요. 답변은 JSON 형식으로만 출력하세요: {"action": "none", "answer": "한국어 답변", "confidence": 0.0}. action은 illegal_parking, housing_department, bulky_waste, move_in_report, public_health_center, none 중 하나입니다. confidence는 0.0~1.0입니다. JSON 외의 텍스트를 출력하지 마세요. 모르면 action: none, confidence: 0.0으로 응답하세요.`;

    const response = await fetch('https://api.kilo.ai/api/gateway/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'tencent/hy3:free',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: q }
        ],
        temperature: 0.1,
        max_tokens: 1000,
      }),
    });

    if (!response.ok) {
      // Consumed but not exposed (security: no raw body leak)
      await response.text();
      return new Response(JSON.stringify({
        ok: false, answer: 'AI 응답을 가져오지 못했습니다.',
        action: 'none', confidence: 0.0,
        provider: 'kilocode', model: 'tencent/hy3:free',
        failure_code: 'upstream_error'
      }), { status: 200, headers });
    }

    const data = await response.json();
    const content = data?.choices?.[0]?.message?.content || '';

    // Try to parse JSON from the response
    let action = 'none', answer = '', confidence = 0.0;
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
      answer = content;
    }

    return new Response(JSON.stringify({
      ok: true, question: q, answer, action, confidence,
      provider: 'kilocode', model: 'tencent/hy3:free', failure_code: ''
    }), { status: 200, headers });

  } catch (error) {
    return new Response(JSON.stringify({
      ok: false, answer: '서버 오류가 발생했습니다.',
      action: 'none', confidence: 0.0,
      provider: 'kilocode', model: 'tencent/hy3:free', failure_code: 'internal_error'
    }), { status: 200, headers });
  }
}
