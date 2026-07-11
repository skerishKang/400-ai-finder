"""Model-backed MVP action decision router for the Buk-gu local demo.

This module routes natural-language questions into the seven interactive MVP
journeys or a chat-only response:

  - ``illegal_parking``   : illegal parking report / complaint guidance
  - ``housing_department``: apartment (공동주택) department & phone guidance
  - ``bulky_waste``       : large waste disposal guidance
  - ``passport_guidance``  : passport issuance guidance
  - ``unmanned_kiosk``     : unmanned kiosk guidance
  - ``streetlight_report`` : AI-assisted streetlight complaint drafting
  - ``litter_ai_assist``   : AI-assisted illegal-dumping complaint drafting
  - ``none``              : unrelated / no left-pane navigation needed

The model call is performed only through an *injectable* ``LLMProvider`` so the
logic can be unit-tested with fake providers and without any real API, fetch,
crawler, or live Buk-gu origin call. Any provider error, malformed JSON, empty
answer, or disallowed action is forced to ``action="none"`` with a concise,
honest Korean failure message — never an action that could trigger the existing
local choreography.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from .base import LLMProvider, ProviderResult
from .openai_compatible_provider import (
    FAILURE_INVALID_MVP_DECISION,
    FAILURE_PROVIDER_EXCEPTION,
    FAILURE_UNKNOWN,
    is_valid_failure_code,
)

MVP_ACTIONS = (
    "illegal_parking",
    "housing_department",
    "bulky_waste",
    "passport_guidance",
    "unmanned_kiosk",
    "streetlight_report",
    "litter_ai_assist",
    "none",
)

MVP_FAILURE_ANSWER = "현재 AI 안내를 연결하지 못했습니다."

MVP_SYSTEM_PROMPT = (
    "당신은 광주광역시 북구청 정보 안내 로컬 데모의 안내 결정 모델입니다. "
    "사용자의 한국어 질문을 받고, 아래 여덟 가지 안내 범위 중 하나로만 분류하세요.\n"
    "\n"
    "⚠️ 중요 — 반드시 아래 지정된 JSON 형식으로만 응답하세요. "
    "JSON 외의 텍스트, 설명, 인사말, 마크다운 코드 블록(```)을 절대 포함하지 마세요. "
    "출력 전체가 오직 하나의 유효한 JSON 객체여야 합니다. "
    "생각 과정이나 추가 설명을 출력하지 마세요.\n"
    "\n"
    "[안내 범위]\n"
    "1. illegal_parking — 불법 주정차 신고·민원 안내\n"
    "   - 로컬 데모가 '종합민원 → 민원 유형 선택 → 불법 주정차 신고' 화면을 "
    "시각적으로 안내할 수 있음을 안내하세요.\n"
    "   - 실제 신고 완료나 외부 사이트 처리는 주장하지 마세요.\n"
    "2. housing_department — 공동주택 담당 부서·전화번호 안내\n"
    "   - 담당 부서: 공동주택과\n"
    "   - 대표 연락처: 062-410-6033\n"
    "   - 로컬 데모가 담당 부서·전화번호 탐색 화면을 시각적으로 안내할 수 있음을 "
    "안내하세요.\n"
    "3. bulky_waste — 대형폐기물 배출 신청 안내\n"
    "   - 가구, 매트리스, 가전제품 등 대형폐기물 배출 신청 경로를 안내하세요.\n"
    "   - 로컬 데모가 대형폐기물 배출 안내 화면을 시각적으로 안내할 수 있음을 "
    "안내하세요.\n"
    "   - 실제 결제·제출·개인정보 입력은 데모에서 수행하지 않음을 명확히 하세요.\n"
    "4. passport_guidance — 여권 발급·안내\n"
    "   - 여권 종류, 유효기간, 발급 수수료, 신청절차, 구비서류를 안내하세요.\n"
    "   - 로컬 데모가 여권민원 안내 화면을 시각적으로 안내할 수 있음을 안내하세요.\n"
    "   - 실제 신청·본인인증·수수료 결제는 북구청 민원실 방문 또는 정부24에서 직접 "
    "진행해야 함을 명확히 하세요.\n"
    "5. unmanned_kiosk — 무인민원발급기 안내\n"
    "   - 무인민원발급기 설치장소, 발급 가능한 민원서류 종류, 이용방법을 안내하세요.\n"
    "   - 로컬 데모가 무인민원발급기 안내 화면을 시각적으로 안내할 수 있음을 안내하세요.\n"
    "   - 실제 민원서류 발급은 현장에서 본인인증 후 직접 진행해야 함을 명확히 하세요.\n"
    "6. streetlight_report — 가로등 고장 신고 글쓰기 보조\n"
    "   - 민원게시판 글쓰기 화면에서 제목과 본문 초안을 준비하고 최종 제출 전에 멈춥니다.\n"
    "7. litter_ai_assist — 쓰레기 무단투기 신고 글쓰기 보조\n"
    "   - 주민의 쉬운 표현을 정중한 민원 문장으로 다듬고 최종 제출 전에 멈춥니다.\n"
    "8. none — 그 밖의 질문\n"
    "   - 북구청 정보 안내 로컬 데모의 범위를 자연스럽게 설명하고, 북구청 민원·"
    "부서·시설·공고 등 질문을 안내할 수 있다고 제안하세요.\n"
    "   - 좌측 화면 이동은 필요 없음을 의미합니다.\n"
    "\n"
    "[JSON 출력 형식 — 정확히 이 형식만 사용하세요]\n"
    "반드시 아래 JSON만 출력하고, 앞뒤에 어떤 텍스트도 추가하지 마세요.\n"
    '{\n'
    '  "answer": "사용자에게 보여줄 자연스러운 한국어 답변",\n'
    '  "action": "illegal_parking",\n'
    '  "confidence": 0.95\n'
    '}\n'
    "\n"
    "※ action 값은 다음 8개 중 정확히 하나여야 합니다:\n"
    '  "illegal_parking", "housing_department", "bulky_waste",\n'
    '  "passport_guidance", "unmanned_kiosk", "streetlight_report",\n'
    '  "litter_ai_assist", "none"\n'
    "※ confidence 값은 0.0 (낮은 확신) ~ 1.0 (높은 확신) 사이의 숫자입니다.\n"
    "\n"
    "[fallback 규칙 — 모르거나 확신 없을 때]\n"
    "질문이 위 8개 안내 범위 중 어디에도 해당하지 않거나 판단이 어렵다면\n"
    'action: "none", confidence: 0.0으로 응답하세요.\n'
)


@dataclass(frozen=True)
class MvpActionDecision:
    """Frozen MVP decision contract returned by :func:`decide_mvp_action`."""
    answer: str
    action: Literal[
        "illegal_parking",
        "housing_department",
        "bulky_waste",
        "passport_guidance",
        "unmanned_kiosk",
        "streetlight_report",
        "litter_ai_assist",
        "none",
    ]
    confidence: float
    # Sanitized, closed-vocabulary failure classification. Empty string on a
    # normal successful action; otherwise one of the fixed failure codes. Never
    # carries raw exception text, URLs, API keys, headers, or upstream bodies.
    failure_code: str = ""
    quest: dict | None = None
    action_plan: dict | None = None

    def to_dict(self) -> dict:
        payload = {
            "answer": self.answer,
            "action": self.action,
            "confidence": self.confidence,
            "failure_code": self.failure_code,
        }
        if self.quest is not None:
            payload["quest"] = self.quest
        if self.action_plan is not None:
            payload["action_plan"] = self.action_plan
        return payload


def is_mvp_failure(decision: MvpActionDecision) -> bool:
    """Return True when the decision is the forced-fallback failure case."""
    return decision.answer == MVP_FAILURE_ANSWER and decision.action == "none"


def _as_confidence(value: object) -> float:
    """Normalize a model-supplied confidence into a safe [0.0, 1.0] float.

    - ``None``, non-numeric strings, and non-finite values (``NaN``,
      ``Infinity``, ``-Infinity``) -> ``0.0``
    - negative values -> ``0.0``
    - values above ``1.0`` -> ``1.0``
    - otherwise the value is clamped to ``[0.0, 1.0]``
    """
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(f):
        return 0.0
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


def decide_bukgu_quest_action(question: str) -> MvpActionDecision | None:
    """Return a deterministic local quest decision when the question matches.

    This is intentionally registry-backed and contains no provider, crawler, or
    live-origin call. Unsupported or invalid registry state returns ``None`` so
    the existing provider-backed MVP router can handle non-quest questions.
    """
    try:
        from src.agent.quest_registry import load_default_bukgu_registry
        from src.agent.quest_router import match_quest
        from src.agent.quest_to_action_plan import build_quest_action_plan

        registry = load_default_bukgu_registry()
        route = match_quest(question, registry)
        if route.status != "matched" or route.quest is None:
            return None
        plan = build_quest_action_plan(route.quest)
        if plan.client_action not in MVP_ACTIONS:
            return None
        return MvpActionDecision(
            answer=plan.answer,
            action=plan.client_action,  # type: ignore[arg-type]
            confidence=route.confidence,
            quest=route.quest.to_public_dict() | {
                "match_status": route.status,
                "match_reason": route.reason,
            },
            action_plan=plan.to_dict(),
        )
    except Exception:
        return None


def parse_mvp_decision(raw: str) -> MvpActionDecision:
    """Parse a model response into a :class:`MvpActionDecision`.

    Any JSON parse failure, non-dict payload, disallowed action, empty answer,
    or missing/invalid confidence is forced to ``action="none"`` with the honest
    failure message. This guarantees that a malformed or adversarial model
    response can never produce an action that would launch the local
    choreography.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError):
        return MvpActionDecision(
            answer=MVP_FAILURE_ANSWER,
            action="none",
            confidence=0.0,
            failure_code=FAILURE_INVALID_MVP_DECISION,
        )

    if not isinstance(data, dict):
        return MvpActionDecision(
            answer=MVP_FAILURE_ANSWER,
            action="none",
            confidence=0.0,
            failure_code=FAILURE_INVALID_MVP_DECISION,
        )

    action = data.get("action")
    if action not in MVP_ACTIONS:
        return MvpActionDecision(
            answer=MVP_FAILURE_ANSWER,
            action="none",
            confidence=0.0,
            failure_code=FAILURE_INVALID_MVP_DECISION,
        )

    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return MvpActionDecision(
            answer=MVP_FAILURE_ANSWER,
            action="none",
            confidence=0.0,
            failure_code=FAILURE_INVALID_MVP_DECISION,
        )

    return MvpActionDecision(
        answer=answer.strip(),
        action=action,  # type: ignore[arg-type]
        confidence=_as_confidence(data.get("confidence", 0.0)),
    )


def decide_mvp_action(question: str, provider: LLMProvider) -> MvpActionDecision:
    """Run a model-backed MVP action decision for ``question`` via ``provider``.

    The provider is injected by the caller; no network call is made here except
    through the provider's ``complete()``. Any provider exception, provider
    error, or unparseable output degrades safely to ``action="none"`` with the
    honest failure message. This guarantees the endpoint never raises or returns
    a partial result that could launch the local choreography.
    """
    quest_decision = decide_bukgu_quest_action(question)
    if quest_decision is not None:
        return quest_decision

    current_time = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    messages = [
        {
            "role": "system",
            "content": MVP_SYSTEM_PROMPT + f"\n현재 대한민국 표준시각: {current_time}",
        },
        {"role": "user", "content": question},
    ]
    try:
        result: ProviderResult = provider.complete(messages)
    except Exception:
        return MvpActionDecision(
            answer=MVP_FAILURE_ANSWER,
            action="none",
            confidence=0.0,
            failure_code=FAILURE_PROVIDER_EXCEPTION,
        )
    if not result.ok:
        # Only forward a failure_code that is part of the closed vocabulary.
        # Anything else (empty string, None, numbers, arbitrary strings) is
        # collapsed to FAILURE_UNKNOWN so an upstream/adversarial code can never
        # leak or pollute the operator-facing contract.
        code = result.failure_code
        if isinstance(code, str) and is_valid_failure_code(code):
            failure_code = code
        else:
            failure_code = FAILURE_UNKNOWN
        return MvpActionDecision(
            answer=MVP_FAILURE_ANSWER,
            action="none",
            confidence=0.0,
            failure_code=failure_code,
        )
    return parse_mvp_decision(result.content)


__all__ = [
    "MVP_ACTIONS",
    "MVP_FAILURE_ANSWER",
    "MVP_SYSTEM_PROMPT",
    "MvpActionDecision",
    "decide_bukgu_quest_action",
    "is_mvp_failure",
    "parse_mvp_decision",
    "decide_mvp_action",
    "FAILURE_INVALID_MVP_DECISION",
    "FAILURE_PROVIDER_EXCEPTION",
    "FAILURE_UNKNOWN",
]
