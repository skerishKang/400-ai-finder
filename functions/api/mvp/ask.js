// functions/api/mvp/ask.js
// hy3 LLM 프록시 — Cloudflare Pages Functions
// API 키는 CF_PAGES_KILOCODE_API_KEY secrets에 저장

export async function onRequest(context) {
  const { request, env } = context;

  // CORS headers
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
    const { question } = await request.json();
    if (!question || typeof question !== 'string' || !question.trim()) {
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
          { role: 'user', content: question }
        ],
        temperature: 0.1,
        max_tokens: 1000,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
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
      action = parsed.action || 'none';
      answer = parsed.answer || content;
      confidence = typeof parsed.confidence === 'number' ? parsed.confidence : 0.0;
    } catch {
      answer = content;
    }

    return new Response(JSON.stringify({
      ok: true, question, answer, action, confidence,
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
