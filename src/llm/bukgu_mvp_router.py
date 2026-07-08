"""Model-backed MVP action decision router for the Buk-gu local demo.

This module implements the #925 Stage 1 "2+1" MVP contract: given a natural
language question, a model decides one of three actions:

  - ``illegal_parking``   : illegal parking report / complaint guidance
  - ``housing_department``: apartment (공동주택) department & phone guidance
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
from typing import Literal

from .base import LLMProvider, ProviderResult
from .openai_compatible_provider import (
    FAILURE_INVALID_MVP_DECISION,
    FAILURE_PROVIDER_EXCEPTION,
    FAILURE_UNKNOWN,
    is_valid_failure_code,
)

MVP_ACTIONS = ("illegal_parking", "housing_department", "bulky_waste", "none")

MVP_FAILURE_ANSWER = "현재 AI 안내를 연결하지 못했습니다."

MVP_SYSTEM_PROMPT = (
    "당신은 광주광역시 북구청 정보 안내 로컬 데모의 안내 결정 모델입니다. "
    "사용자의 한국어 질문을 받고, 아래 네 가지 안내 범위 중 하나로만 분류하세요. "
    "반드시 JSON 객체 하나만 출력하세요. 다른 설명이나 마크다운 코드 블록(```)을 "
    "절대 포함하지 마세요.\n"
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
    "4. none — 그 밖의 질문\n"
    "   - 북구청 정보 안내 로컬 데모의 범위를 자연스럽게 설명하고, 북구청 민원·"
    "부서·시설·공고 등 질문을 안내할 수 있다고 제안하세요.\n"
    "   - 좌측 화면 이동은 필요 없음을 의미합니다.\n"
    "\n"
    "[출력 형식] 반드시 아래 JSON만 출력:\n"
    '{\n'
    '  "answer": "사용자에게 보여줄 자연스러운 한국어 답변",\n'
    '  "action": "illegal_parking | housing_department | bulky_waste | none 중 하나",\n'
    '  "confidence": 0.0\n'
    "}\n"
)


@dataclass(frozen=True)
class MvpActionDecision:
    """Frozen MVP decision contract returned by :func:`decide_mvp_action`."""
    answer: str
    action: Literal["illegal_parking", "housing_department", "bulky_waste", "none"]
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

    messages = [
        {"role": "system", "content": MVP_SYSTEM_PROMPT},
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
