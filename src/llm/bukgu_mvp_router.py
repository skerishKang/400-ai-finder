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
from dataclasses import dataclass
from typing import Literal

from .base import LLMProvider, ProviderResult

MVP_ACTIONS = ("illegal_parking", "housing_department", "none")

MVP_FAILURE_ANSWER = "현재 AI 안내를 연결하지 못했습니다."

MVP_SYSTEM_PROMPT = (
    "당신은 광주광역시 북구청 정보 안내 로컬 데모의 안내 결정 모델입니다. "
    "사용자의 한국어 질문을 받고, 아래 세 가지 안내 범위 중 하나로만 분류하세요. "
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
    "3. none — 그 밖의 질문\n"
    "   - 북구청 정보 안내 로컬 데모의 범위를 자연스럽게 설명하고, 북구청 민원·"
    "부서·시설·공고 등 질문을 안내할 수 있다고 제안하세요.\n"
    "   - 좌측 화면 이동은 필요 없음을 의미합니다.\n"
    "\n"
    "[출력 형식] 반드시 아래 JSON만 출력:\n"
    '{\n'
    '  "answer": "사용자에게 보여줄 자연스러운 한국어 답변",\n'
    '  "action": "illegal_parking | housing_department | none 중 하나",\n'
    '  "confidence": 0.0\n'
    "}\n"
)


@dataclass(frozen=True)
class MvpActionDecision:
    """Frozen MVP decision contract returned by :func:`decide_mvp_action`."""

    answer: str
    action: Literal["illegal_parking", "housing_department", "none"]
    confidence: float

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "action": self.action,
            "confidence": self.confidence,
        }


def is_mvp_failure(decision: MvpActionDecision) -> bool:
    """Return True when the decision is the forced-fallback failure case."""
    return decision.answer == MVP_FAILURE_ANSWER and decision.action == "none"


def _as_confidence(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


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
        return MvpActionDecision(answer=MVP_FAILURE_ANSWER, action="none", confidence=0.0)

    if not isinstance(data, dict):
        return MvpActionDecision(answer=MVP_FAILURE_ANSWER, action="none", confidence=0.0)

    action = data.get("action")
    if action not in MVP_ACTIONS:
        return MvpActionDecision(answer=MVP_FAILURE_ANSWER, action="none", confidence=0.0)

    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return MvpActionDecision(answer=MVP_FAILURE_ANSWER, action="none", confidence=0.0)

    return MvpActionDecision(
        answer=answer.strip(),
        action=action,  # type: ignore[arg-type]
        confidence=_as_confidence(data.get("confidence", 0.0)),
    )


def decide_mvp_action(question: str, provider: LLMProvider) -> MvpActionDecision:
    """Run a model-backed MVP action decision for ``question`` via ``provider``.

    The provider is injected by the caller; no network call is made here except
    through the provider's ``complete()``. Any provider failure degrades safely
    to ``action="none"``.

    Args:
        question: The user's natural-language question (already stripped).
        provider: An injectable :class:`LLMProvider` (e.g. ``MockProvider`` in
            tests or ``OpenAICompatibleProvider`` in production).

    Returns:
        A :class:`MvpActionDecision`. On provider error or unparseable output the
        decision is ``action="none"`` with the honest failure message.
    """
    messages = [
        {"role": "system", "content": MVP_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    result: ProviderResult = provider.complete(messages)
    if not result.ok:
        return MvpActionDecision(answer=MVP_FAILURE_ANSWER, action="none", confidence=0.0)
    return parse_mvp_decision(result.content)


__all__ = [
    "MVP_ACTIONS",
    "MVP_FAILURE_ANSWER",
    "MVP_SYSTEM_PROMPT",
    "MvpActionDecision",
    "is_mvp_failure",
    "parse_mvp_decision",
    "decide_mvp_action",
]
