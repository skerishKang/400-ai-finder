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
    3. 사용자가 특정 민원과 관련된 질문을 하면, 정확한 키워드가 없어도 의도를 파악해서 적절한 action을 선택하세요.
    4. 일반 인사나 북구청 일반 문의, 또는 북구청과 무관한 잡담/일상 질문도 action: none으로 자연스럽게 응답하세요.
    5. 북구청 직원으로서 항상 정중하고 전문적인 태도를 유지하세요. 간결하게 2~3문장으로 답변해 주세요.
    6. confidence는 0.0~1.0 사이입니다.
    7. 북구청과 전혀 무관한 질문(날씨, AI 비교, 음식 추천 등)도 무시하지 말고, 북구청 직원의 입장에서 자연스럽게 대답해 주세요.

    action 의도 추론 가이드:
    - illegal_parking: 불법주정차, 주차단속, 스티커, 견인, 과태료, 주차위반 관련 모든 문의
      예: "차 세웠는데 스티커 붙었어요", "주차 벌금 얼마예요?", "불법주정차 신고"
    - housing_department: 아파트, 공동주택, 관리비, 주택 관리, 하자보수, 보조금, 입주자대표회의 관련
      예: "아파트 관리비가 너무 비싸요", "공동주택 관련 문의", "주택 하자보수 어디에", "입주자대표회의 관련 문의"
    - bulky_waste: 대형폐기물, 폐기물 배출, 침대, 매트리스, 가구, 가전제품 처리
      예: "침대 버리고 싶어요", "오래된 냉장고 처리", "가구 버리는 법"
    - move_in_report: 전입신고, 이사, 주소이전, 거주지 변경, 정부24
      예: "이사 왔는데 뭐부터 해야하죠?", "주소 옮기려면", "전입신고"
    - public_health_center: 보건소, 진료, 예방접종, 건강검진, 병원, 처방전
      예: "감기 걸렸는데 어디로 가야하나요", "독감 예방접종", "보건소 이용시간"
    - none: 위 카테고리에 해당하지 않는 일반 질문, 인사, 북구청 일반 정보, 그리고 북구청과 무관한 잡담/일상 질문
      예: "안녕하세요", "북구청 업무시간", "민원실 위치"

    예시:
    - 사용자: "안녕하세요" → {"action": "none", "answer": "안녕하세요! 북구청 민원 안내입니다. 무엇을 도와드릴까요?", "confidence": 1.0}
    - 사용자: "차 세웠는데 스티커 붙었어요" → {"action": "illegal_parking", "answer": "불법 주정차 과태료 관련 문의이시군요. 북구청 홈페이지 지도단속 페이지 또는 안전신문고(safetyreport.go.kr)에서 신고 및 조회가 가능합니다.", "confidence": 0.95}
    - 사용자: "독감 예방접종 맞으려고요" → {"action": "public_health_center", "answer": "독감 예방접종은 북구 보건소에서 가능합니다. 자세한 일정은 북구청 홈페이지 보건소 안내를 확인해 주세요.", "confidence": 0.95}
    - 사용자: "이사 왔는데 전입신고요" → {"action": "move_in_report", "answer": "전입신고는 정부24(www.gov.kr)에서 온라인으로 신청하거나 가까운 주민센터를 방문하시면 됩니다. 이사일로부터 14일 이내에 신고해야 합니다.", "confidence": 0.95}
    - 사용자: "공동주택과 전화번호 좀" → {"action": "housing_department", "answer": "공동주택과(도시관리국) 대표 연락처는 062-410-6831~6834입니다. 업무시간(평일 09:00~18:00)에 문의해 주세요.", "confidence": 0.95}
    - 사용자: "내일 비와?" → {"action": "none", "answer": "날씨에 대한 문의이시군요. 북구청은 민원 업무를 안내해 드리고 있으나 실시간 날씨 정보는 제공해 드리기 어렵습니다. 기상청 웹사이트(www.kma.go.kr)나 기상청 날씨앱을 통해 내일 광주광역시 북구의 날씨를 확인하시길 권해드립니다. 다른 북구청 관련 민원이 있으시면 언제든 말씀해 주세요.", "confidence": 0.9}
    - 사용자: "ChatGPT랑 뭐가 달라?" → {"action": "none", "answer": "저는 광주광역시 북구청 민원 안내 직원으로, 북구청의 행정 서비스(불법주정차, 주택, 대형폐기물, 전입신고, 보건소 등)와 관련된 실질적인 업무 안내를 전문으로 합니다. 범용 인공지능 모델과 달리, 저는 북구청의 구체적인 민원 절차와 연락처, 관련 부서 안내에 특화되어 있어 지역 주민분들의 행정 업무를 더 정확하고 빠르게 도와드릴 수 있습니다. 북구청 관련하여 궁금하신 민원 사항이 있으신가요?", "confidence": 0.9}
    - 사용자: "오늘 점심 뭐 먹을까?" → {"action": "none", "answer": "점심 메뉴 고민이시군요! 북구청 인근에는 다양한 식당이 많지요. 저는 민원 안내를 담당하고 있어 구체적인 맛집 추천은 어렵습니다. 북구청 관련 민원이나 업무 문의가 있으시면 언제든 말씀해 주세요. 맛있는 점심 되세요!", "confidence": 1.0}`;

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
        max_tokens: 500,
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
