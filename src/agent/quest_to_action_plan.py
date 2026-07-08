"""Convert validated quests into local browser choreography plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.agent.quest_schema import (
    ALLOWED_BROWSER_ACTION_TYPES,
    BrowserAction,
    Quest,
)


class QuestActionPlanError(ValueError):
    """Raised when a quest cannot be converted to an executable local plan."""


@dataclass(frozen=True)
class QuestActionPlan:
    plan_status: str
    quest_id: str
    quest_name: str
    client_action: str
    official_path: tuple[str, ...]
    browser_actions: tuple[BrowserAction, ...]
    stop_condition: str
    result: dict[str, Any]
    answer: str
    source_mode: str
    requires_user_confirmation: bool
    final_warning: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_status": self.plan_status,
            "quest_id": self.quest_id,
            "quest_name": self.quest_name,
            "client_action": self.client_action,
            "official_path": list(self.official_path),
            "browser_actions": [action.to_dict() for action in self.browser_actions],
            "stop_condition": self.stop_condition,
            "result": dict(self.result),
            "answer": self.answer,
            "source_mode": self.source_mode,
            "requires_user_confirmation": self.requires_user_confirmation,
            "final_warning": self.final_warning,
        }


def build_quest_action_plan(quest: Quest) -> QuestActionPlan:
    if quest.ai_can_prefill or quest.ai_can_submit:
        raise QuestActionPlanError("phase1 quest cannot prefill or submit")
    if not quest.ai_can_answer:
        raise QuestActionPlanError("quest must allow answer generation")
    if not quest.client_action:
        raise QuestActionPlanError("quest requires client_action for existing choreography")
    if not quest.answer:
        raise QuestActionPlanError("quest requires a deterministic answer")
    if not quest.browser_actions:
        raise QuestActionPlanError("quest requires browser_actions")

    for action in quest.browser_actions:
        if action.action_type not in ALLOWED_BROWSER_ACTION_TYPES:
            raise QuestActionPlanError(f"unknown browser action type: {action.action_type}")

    if quest.browser_actions[-1].action_type != quest.stop_condition:
        raise QuestActionPlanError("last action must match stop_condition")

    requires_user_confirmation = (
        quest.stop_condition == "STOP_FOR_USER_CONFIRMATION"
        or bool(quest.final_warning and quest.final_warning.requires_user_confirmation)
    )
    final_warning = quest.final_warning.to_dict() if quest.final_warning else None

    return QuestActionPlan(
        plan_status="guided",
        quest_id=quest.quest_id,
        quest_name=quest.quest_name,
        client_action=quest.client_action,
        official_path=quest.official_path,
        browser_actions=quest.browser_actions,
        stop_condition=quest.stop_condition,
        result=dict(quest.result),
        answer=quest.answer,
        source_mode=quest.source_mode,
        requires_user_confirmation=requires_user_confirmation,
        final_warning=final_warning,
    )
