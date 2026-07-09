// functions/api/mvp/ask.js
// hy3 LLM 프록시 — Cloudflare Pages Functions
// API 키는 KILOCODE_API_KEY secrets에 저장

/** 허용된 action 값 목록 (src/llm/bukgu_mvp_router.py의 MVP_ACTIONS와 동일) */
var VALID_ACTIONS = ['illegal_parking', 'housing_department', 'bulky_waste', 'move_in_report', 'public_health_center', 'none'];

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
        provider: 'kilocode', model: 'tencent/hy3:free', failure_code: 'invalid_input'
      }), { status: 200, headers });
    }

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

    const systemPrompt = `당신은 광주광역시 북구청 민원 안내 직원입니다. 북구청에 관한 모든 문의에 친절하고 전문적으로 답변해 주세요.

응답 규칙:
1. 반드시 JSON 형식으로만 출력하세요: {"action": "...", "answer": "...", "confidence": 0.0}
2. action 필드는 다음 중 하나여야 합니다: illegal_parking, housing_department, bulky_waste, move_in_report, public_health_center, none
3. 사용자가 특정 민원(불법주정차 신고, 공동주택 문의, 대형폐기물 배출, 전입신고, 보건소 안내)을 문의하면 해당 action을 선택하고 관련 정보를 안내해 주세요.
4. 일반 인사("안녕하세요", "하이" 등)나 북구청 관련 일반 질문(업무시간, 위치, 팩스번호 등)은 action: none으로 답변하되, 북구청 직원처럼 자연스럽고 친절하게 응답해 주세요.
5. 북구청 직원으로서 항상 정중하고 전문적인 태도를 유지하세요.
6. confidence는 0.0~1.0 사이의 숫자입니다. 일반 대화는 confidence: 1.0으로 설정하세요.

예시:
- 사용자: "안녕하세요" → {"action": "none", "answer": "안녕하세요! 북구청 민원 안내입니다. 불법주정차, 공동주택, 대형폐기물, 전입신고, 보건소 관련 문의를 도와드릴 수 있습니다.", "confidence": 1.0}
- 사용자: "불법 주정차 신고는 어디서 하나요?" → {"action": "illegal_parking", "answer": "불법 주정차 신고는 북구청 홈페이지 지도단속 페이지나 안전신문고(safetyreport.go.kr)에서 가능합니다.", "confidence": 0.95}`;

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
        // JSON 파싱 실패 → fail-closed
        action = 'none';
        answer = '죄송합니다. 답변을 준비하지 못했습니다. 다른 질문을 해 주세요.';
        confidence = 0.0;
        failureCode = 'parse_error';
      }
    }

    return new Response(JSON.stringify({
      ok: true, question: q, answer, action, confidence,
      provider: 'kilocode', model: 'tencent/hy3:free', failure_code: failureCode
    }), { status: 200, headers });

  } catch (error) {
    return new Response(JSON.stringify({
      ok: false, answer: '서버 오류가 발생했습니다.',
      action: 'none', confidence: 0.0,
      provider: 'kilocode', model: 'tencent/hy3:free', failure_code: 'internal_error'
    }), { status: 200, headers });
  }
}
