"""Quest-to-action-plan tests for the phase-1 Buk-gu golden quests."""

from __future__ import annotations

from src.agent.quest_registry import load_default_bukgu_registry
from src.agent.quest_to_action_plan import build_quest_action_plan
from src.llm.bukgu_mvp_router import decide_bukgu_quest_action


def _housing_quest():
    quest = load_default_bukgu_registry().get("housing_department_lookup")
    assert quest is not None
    return quest


def _illegal_parking_quest():
    quest = load_default_bukgu_registry().get("illegal_parking_report_guidance")
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


def test_illegal_parking_quest_converts_to_valid_action_plan():
    plan = build_quest_action_plan(_illegal_parking_quest())
    assert plan.plan_status == "guided"
    assert plan.quest_id == "illegal_parking_report_guidance"
    assert plan.quest_name == "불법 주정차 신고 안내"
    assert plan.client_action == "illegal_parking"
    assert plan.official_path == (
        "종합민원",
        "민원신고",
        "불법 주정차 신고",
    )
    assert plan.result["service"] == "불법 주정차 신고"
    assert plan.result["surface"] == "불법 주정차 신고 카드"
    labels = [action.label for action in plan.browser_actions]
    assert "불법 주정차 신고 화면 이동" in labels
    assert "불법 주정차 신고 카드 확인" in labels


def test_illegal_parking_quest_stops_for_user_confirmation_with_warning():
    plan = build_quest_action_plan(_illegal_parking_quest())
    assert plan.stop_condition == "STOP_FOR_USER_CONFIRMATION"
    assert plan.browser_actions[-1].action_type == "STOP_FOR_USER_CONFIRMATION"
    assert plan.requires_user_confirmation is True
    assert plan.final_warning is not None
    assert plan.final_warning["requires_user_confirmation"] is True
    warning_text = plan.final_warning["warning_text"]
    assert "본인인증" in warning_text
    assert "차량번호" in warning_text
    assert "사진" in warning_text
    assert "위치정보" in warning_text
    assert "첨부파일" in warning_text


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


def test_decide_bukgu_quest_action_returns_local_static_illegal_parking_decision():
    decision = decide_bukgu_quest_action("불법 주정차 신고는 어디서 하나요?")
    assert decision is not None
    assert decision.action == "illegal_parking"
    assert decision.quest is not None
    assert decision.quest["quest_id"] == "illegal_parking_report_guidance"
    assert decision.quest["source_mode"] == "local_static"
    assert decision.action_plan is not None
    assert decision.action_plan["stop_condition"] == "STOP_FOR_USER_CONFIRMATION"
    assert decision.action_plan["requires_user_confirmation"] is True
    assert decision.action_plan["final_warning"]["requires_user_confirmation"] is True
