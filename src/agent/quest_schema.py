"""Quest schema validation for local Buk-gu guided journeys."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


REQUIRED_QUEST_FIELDS: frozenset[str] = frozenset({
    "quest_id",
    "quest_name",
    "status",
    "category",
    "risk_level",
    "user_phrases",
    "required_slots",
    "official_path",
    "browser_actions",
    "ai_can_answer",
    "ai_can_click",
    "ai_can_prefill",
    "ai_can_submit",
    "stop_condition",
    "final_warning",
})

ALLOWED_RISK_LEVELS: frozenset[str] = frozenset({"low", "medium", "high"})
ALLOWED_STOP_CONDITIONS: frozenset[str] = frozenset({
    "STOP_AFTER_RESULT",
    "STOP_FOR_USER_CONFIRMATION",
})
ALLOWED_BROWSER_ACTION_TYPES: frozenset[str] = frozenset({
    "OPEN_ALLOWLISTED_ROUTE",
    "SEARCH_ALLOWLISTED_QUERY",
    "SHOW_ALLOWLISTED_RESULT",
    "STOP_AFTER_RESULT",
    "STOP_FOR_USER_CONFIRMATION",
})

FORBIDDEN_BROWSER_ACTION_TYPES: frozenset[str] = frozenset({
    "LOGIN",
    "SUBMIT",
    "UPLOAD_FILE",
    "PAY",
    "ENTER_IDENTITY",
    "PREFILL_APPROVED_DRAFT",
})


class QuestValidationError(ValueError):
    """Raised when a quest definition does not satisfy the local schema."""


@dataclass(frozen=True)
class BrowserAction:
    action_type: str
    route_id: str | None = None
    target_id: str | None = None
    query: str | None = None
    journey_state: str | None = None
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "route_id": self.route_id,
            "target_id": self.target_id,
            "query": self.query,
            "journey_state": self.journey_state,
            "label": self.label,
        }


@dataclass(frozen=True)
class FinalWarning:
    warning_text: str
    requires_user_confirmation: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "warning_text": self.warning_text,
            "requires_user_confirmation": self.requires_user_confirmation,
        }


@dataclass(frozen=True)
class Quest:
    quest_id: str
    quest_name: str
    status: str
    category: str
    risk_level: str
    user_phrases: tuple[str, ...]
    required_slots: tuple[str, ...]
    official_path: tuple[str, ...]
    browser_actions: tuple[BrowserAction, ...]
    ai_can_answer: bool
    ai_can_click: bool
    ai_can_prefill: bool
    ai_can_submit: bool
    stop_condition: str
    final_warning: FinalWarning | None
    extra: Mapping[str, Any]

    @property
    def client_action(self) -> str:
        value = self.extra.get("client_action", "")
        return value if isinstance(value, str) else ""

    @property
    def official_snapshot_ref(self) -> str:
        value = self.extra.get("official_snapshot_ref", "")
        return value if isinstance(value, str) else ""

    @property
    def answer(self) -> str:
        if self.official_snapshot_ref:
            from src.bukgu_official_snapshot import build_snapshot_answer

            return build_snapshot_answer(self.official_snapshot_ref)
        value = self.extra.get("answer", "")
        return value if isinstance(value, str) else ""

    @property
    def result(self) -> Mapping[str, Any]:
        if self.official_snapshot_ref:
            from src.bukgu_official_snapshot import build_snapshot_result

            return build_snapshot_result(self.official_snapshot_ref)
        value = self.extra.get("result", {})
        return value if isinstance(value, Mapping) else {}

    @property
    def source_mode(self) -> str:
        value = self.extra.get("source_mode", "local_static")
        return value if isinstance(value, str) else "local_static"

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "quest_id": self.quest_id,
            "quest_name": self.quest_name,
            "status": self.status,
            "category": self.category,
            "risk_level": self.risk_level,
            "official_path": list(self.official_path),
            "stop_condition": self.stop_condition,
            "result": dict(self.result),
            "source_mode": self.source_mode,
        }


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise QuestValidationError(f"{label} must be an object")
    return value


def _require_str(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise QuestValidationError(f"{label} must be a non-empty string")
    return value.strip()


def _require_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise QuestValidationError(f"{label} must be a boolean")
    return value


def _require_str_tuple(value: object, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise QuestValidationError(f"{label} must be a list")
    if not value and not allow_empty:
        raise QuestValidationError(f"{label} must not be empty")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_require_str(item, f"{label}[{index}]"))
    return tuple(result)


def _validate_final_warning(value: object, risk_level: str) -> FinalWarning | None:
    if value is None:
        if risk_level == "high":
            raise QuestValidationError("high-risk quest requires final_warning")
        return None

    warning = _require_mapping(value, "final_warning")
    warning_text = _require_str(warning.get("warning_text"), "final_warning.warning_text")
    requires_user_confirmation = _require_bool(
        warning.get("requires_user_confirmation"),
        "final_warning.requires_user_confirmation",
    )
    if risk_level == "high" and not requires_user_confirmation:
        raise QuestValidationError("high-risk final_warning must require user confirmation")
    return FinalWarning(
        warning_text=warning_text,
        requires_user_confirmation=requires_user_confirmation,
    )


def _validate_browser_action(value: object, index: int) -> BrowserAction:
    data = _require_mapping(value, f"browser_actions[{index}]")
    action_type = _require_str(data.get("action_type"), f"browser_actions[{index}].action_type")
    if action_type in FORBIDDEN_BROWSER_ACTION_TYPES:
        raise QuestValidationError(f"forbidden browser action type: {action_type}")
    if action_type not in ALLOWED_BROWSER_ACTION_TYPES:
        raise QuestValidationError(f"unknown browser action type: {action_type}")

    route_id = data.get("route_id")
    target_id = data.get("target_id")
    query = data.get("query")
    journey_state = data.get("journey_state")
    label = data.get("label", "")

    if route_id is not None and type(route_id) is not str:
        raise QuestValidationError(f"browser_actions[{index}].route_id must be string or null")
    if target_id is not None and type(target_id) is not str:
        raise QuestValidationError(f"browser_actions[{index}].target_id must be string or null")
    if query is not None and type(query) is not str:
        raise QuestValidationError(f"browser_actions[{index}].query must be string or null")
    if journey_state is not None and type(journey_state) is not str:
        raise QuestValidationError(f"browser_actions[{index}].journey_state must be string or null")
    if type(label) is not str:
        raise QuestValidationError(f"browser_actions[{index}].label must be a string")

    if action_type == "OPEN_ALLOWLISTED_ROUTE" and not route_id:
        raise QuestValidationError("OPEN_ALLOWLISTED_ROUTE requires route_id")
    if action_type == "SEARCH_ALLOWLISTED_QUERY" and (not target_id or not query):
        raise QuestValidationError("SEARCH_ALLOWLISTED_QUERY requires target_id and query")
    if action_type == "SHOW_ALLOWLISTED_RESULT" and not target_id:
        raise QuestValidationError("SHOW_ALLOWLISTED_RESULT requires target_id")
    if action_type.startswith("STOP_") and any((route_id, target_id, query, journey_state)):
        raise QuestValidationError(f"{action_type} cannot carry route/target/query/journey_state")

    return BrowserAction(
        action_type=action_type,
        route_id=route_id,
        target_id=target_id,
        query=query,
        journey_state=journey_state,
        label=label.strip(),
    )


def validate_quest_payload(payload: Mapping[str, Any]) -> Quest:
    """Validate and normalize one quest JSON object."""
    data = _require_mapping(payload, "quest")
    missing = sorted(REQUIRED_QUEST_FIELDS - set(data.keys()))
    if missing:
        raise QuestValidationError("missing required quest fields: " + ", ".join(missing))

    quest_id = _require_str(data.get("quest_id"), "quest_id")
    quest_name = _require_str(data.get("quest_name"), "quest_name")
    status = _require_str(data.get("status"), "status")
    category = _require_str(data.get("category"), "category")
    risk_level = _require_str(data.get("risk_level"), "risk_level")
    if risk_level not in ALLOWED_RISK_LEVELS:
        raise QuestValidationError(f"invalid risk_level: {risk_level}")

    user_phrases = _require_str_tuple(data.get("user_phrases"), "user_phrases")
    required_slots = _require_str_tuple(
        data.get("required_slots"),
        "required_slots",
        allow_empty=True,
    )
    official_path = _require_str_tuple(data.get("official_path"), "official_path")

    actions_raw = data.get("browser_actions")
    if not isinstance(actions_raw, list) or not actions_raw:
        raise QuestValidationError("browser_actions must be a non-empty list")
    browser_actions = tuple(
        _validate_browser_action(action, index)
        for index, action in enumerate(actions_raw)
    )

    ai_can_answer = _require_bool(data.get("ai_can_answer"), "ai_can_answer")
    ai_can_click = _require_bool(data.get("ai_can_click"), "ai_can_click")
    ai_can_prefill = _require_bool(data.get("ai_can_prefill"), "ai_can_prefill")
    ai_can_submit = _require_bool(data.get("ai_can_submit"), "ai_can_submit")
    if ai_can_prefill:
        raise QuestValidationError("phase1 quests must not enable ai_can_prefill")
    if ai_can_submit:
        raise QuestValidationError("phase1 quests must not enable ai_can_submit")

    stop_condition = _require_str(data.get("stop_condition"), "stop_condition")
    if stop_condition not in ALLOWED_STOP_CONDITIONS:
        raise QuestValidationError(f"invalid stop_condition: {stop_condition}")
    if browser_actions[-1].action_type != stop_condition:
        raise QuestValidationError("last browser action must match stop_condition")

    final_warning = _validate_final_warning(data.get("final_warning"), risk_level)

    extras = {key: value for key, value in data.items() if key not in REQUIRED_QUEST_FIELDS}
    return Quest(
        quest_id=quest_id,
        quest_name=quest_name,
        status=status,
        category=category,
        risk_level=risk_level,
        user_phrases=user_phrases,
        required_slots=required_slots,
        official_path=official_path,
        browser_actions=browser_actions,
        ai_can_answer=ai_can_answer,
        ai_can_click=ai_can_click,
        ai_can_prefill=ai_can_prefill,
        ai_can_submit=ai_can_submit,
        stop_condition=stop_condition,
        final_warning=final_warning,
        extra=extras,
    )
