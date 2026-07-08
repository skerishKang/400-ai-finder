"""Quest registry loading and duplicate-ID validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.agent.quest_schema import Quest, QuestValidationError, validate_quest_payload


DEFAULT_QUESTS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "quests" / "bukgu_gwangju_quests.json"
)


class QuestRegistryError(ValueError):
    """Raised when a quest registry file is invalid."""


@dataclass(frozen=True)
class QuestRegistry:
    site_id: str
    version: int
    quests: tuple[Quest, ...]

    @classmethod
    def from_path(cls, path: str | Path = DEFAULT_QUESTS_PATH) -> "QuestRegistry":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise QuestRegistryError(f"invalid quest registry JSON: {exc.msg}") from exc
        return cls.from_payload(raw)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "QuestRegistry":
        if not isinstance(payload, Mapping):
            raise QuestRegistryError("quest registry must be an object")
        site_id = payload.get("site_id")
        if type(site_id) is not str or not site_id.strip():
            raise QuestRegistryError("site_id must be a non-empty string")
        version = payload.get("version")
        if type(version) is not int or version < 1:
            raise QuestRegistryError("version must be a positive integer")
        raw_quests = payload.get("quests")
        if not isinstance(raw_quests, list) or not raw_quests:
            raise QuestRegistryError("quests must be a non-empty list")

        quests: list[Quest] = []
        seen: set[str] = set()
        for raw_quest in raw_quests:
            try:
                quest = validate_quest_payload(raw_quest)
            except QuestValidationError as exc:
                raise QuestRegistryError(str(exc)) from exc
            if quest.quest_id in seen:
                raise QuestRegistryError(f"duplicate quest_id: {quest.quest_id}")
            seen.add(quest.quest_id)
            quests.append(quest)
        return cls(site_id=site_id.strip(), version=version, quests=tuple(quests))

    def get(self, quest_id: str) -> Quest | None:
        for quest in self.quests:
            if quest.quest_id == quest_id:
                return quest
        return None

    def iter_quests(self) -> Iterable[Quest]:
        return iter(self.quests)


def load_default_bukgu_registry() -> QuestRegistry:
    return QuestRegistry.from_path(DEFAULT_QUESTS_PATH)
