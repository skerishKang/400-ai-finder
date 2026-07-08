"""Schema and router tests for the phase-1 Buk-gu quest registry."""

from __future__ import annotations

import copy

import pytest

from src.agent.quest_registry import QuestRegistry, QuestRegistryError, load_default_bukgu_registry
from src.agent.quest_router import match_quest
from src.agent.quest_schema import QuestValidationError, validate_quest_payload


def _base_registry_payload():
    registry = load_default_bukgu_registry()
    return {
        "site_id": registry.site_id,
        "version": registry.version,
        "quests": [
            {
                "quest_id": q.quest_id,
                "quest_name": q.quest_name,
                "status": q.status,
                "category": q.category,
                "risk_level": q.risk_level,
                "user_phrases": list(q.user_phrases),
                "required_slots": list(q.required_slots),
                "official_path": list(q.official_path),
                "browser_actions": [a.to_dict() for a in q.browser_actions],
                "ai_can_answer": q.ai_can_answer,
                "ai_can_click": q.ai_can_click,
                "ai_can_prefill": q.ai_can_prefill,
                "ai_can_submit": q.ai_can_submit,
                "stop_condition": q.stop_condition,
                "final_warning": q.final_warning.to_dict() if q.final_warning else None,
                **dict(q.extra),
            }
            for q in registry.quests
        ],
    }


def test_default_registry_loads_housing_quest_only_for_phase1_scope():
    registry = load_default_bukgu_registry()
    assert [quest.quest_id for quest in registry.quests] == ["housing_department_lookup"]
    quest = registry.get("housing_department_lookup")
    assert quest is not None
    assert quest.status == "phase1_golden"
    assert quest.risk_level == "low"
    assert quest.ai_can_answer is True
    assert quest.ai_can_click is True
    assert quest.ai_can_prefill is False
    assert quest.ai_can_submit is False


def test_duplicate_quest_id_is_rejected():
    payload = _base_registry_payload()
    payload["quests"].append(copy.deepcopy(payload["quests"][0]))
    with pytest.raises(QuestRegistryError, match="duplicate quest_id"):
        QuestRegistry.from_payload(payload)


def test_missing_required_field_is_rejected():
    payload = _base_registry_payload()["quests"][0]
    del payload["official_path"]
    with pytest.raises(QuestValidationError, match="missing required quest fields"):
        validate_quest_payload(payload)


@pytest.mark.parametrize("question", [
    "공동주택 관련 문의는 어느 부서에 해야 하나요?",
    "공동주택 문의는 어디로 해요?",
    "아파트 관련 문의 담당부서 알려줘",
])
def test_housing_questions_match_housing_department_lookup(question):
    result = match_quest(question, load_default_bukgu_registry())
    assert result.status == "matched"
    assert result.quest_id == "housing_department_lookup"
    assert result.confidence >= 0.72


def test_unknown_question_is_unsupported_or_needs_confirmation():
    result = match_quest("오늘 북구 날씨 알려줘", load_default_bukgu_registry())
    assert result.status == "unsupported"
    assert result.quest is None
    assert result.reason == "unsupported_or_needs_confirmation"


def test_browser_actions_use_allowed_action_types_only():
    payload = _base_registry_payload()["quests"][0]
    payload["browser_actions"][0]["action_type"] = "SUBMIT"
    with pytest.raises(QuestValidationError, match="forbidden browser action type"):
        validate_quest_payload(payload)


def test_high_risk_quest_requires_final_warning_structure():
    payload = _base_registry_payload()["quests"][0]
    payload["quest_id"] = "dangerous_high_risk_fixture"
    payload["risk_level"] = "high"
    payload["final_warning"] = None
    with pytest.raises(QuestValidationError, match="high-risk quest requires final_warning"):
        validate_quest_payload(payload)

    payload["final_warning"] = {
        "warning_text": "사용자 확인 전에는 진행할 수 없습니다.",
        "requires_user_confirmation": True,
    }
    quest = validate_quest_payload(payload)
    assert quest.final_warning is not None
    assert quest.final_warning.requires_user_confirmation is True
