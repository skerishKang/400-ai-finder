"""Quest-to-action-plan tests for the phase-1 housing department quest."""

from __future__ import annotations

from src.agent.quest_registry import load_default_bukgu_registry
from src.agent.quest_to_action_plan import build_quest_action_plan
from src.llm.bukgu_mvp_router import decide_bukgu_quest_action


def _housing_quest():
    quest = load_default_bukgu_registry().get("housing_department_lookup")
    assert quest is not None
    return quest


def test_housing_quest_converts_to_valid_action_plan():
    plan = build_quest_action_plan(_housing_quest())
    assert plan.plan_status == "guided"
    assert plan.quest_id == "housing_department_lookup"
    assert plan.quest_name == "공동주택 담당부서 찾기"
    assert plan.client_action == "housing_department"
    assert plan.official_path == (
        "북구소개",
        "구청안내",
        "업무 및 전화번호 안내",
        "공동주택과",
    )
    assert plan.result["department"] == "공동주택과"
    assert plan.result["phone"] == "062-410-6033"


def test_housing_quest_ends_with_stop_after_result():
    plan = build_quest_action_plan(_housing_quest())
    assert plan.stop_condition == "STOP_AFTER_RESULT"
    assert plan.browser_actions[-1].action_type == "STOP_AFTER_RESULT"
    assert plan.requires_user_confirmation is False


def test_decide_bukgu_quest_action_returns_local_static_housing_decision():
    decision = decide_bukgu_quest_action("공동주택 문의는 어디로 해요?")
    assert decision is not None
    assert decision.action == "housing_department"
    assert decision.answer == "공동주택 관련 문의는 공동주택과에서 담당합니다. 대표 연락처는 062-410-6033입니다."
    assert decision.quest is not None
    assert decision.quest["quest_id"] == "housing_department_lookup"
    assert decision.quest["source_mode"] == "local_static"
    assert decision.action_plan is not None
    assert decision.action_plan["stop_condition"] == "STOP_AFTER_RESULT"
