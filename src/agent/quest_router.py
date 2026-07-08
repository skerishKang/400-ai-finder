"""Local quest matching for Buk-gu guided journeys."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.agent.quest_registry import QuestRegistry
from src.agent.quest_schema import Quest


_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


@dataclass(frozen=True)
class QuestRouteResult:
    status: str
    quest: Quest | None
    confidence: float
    reason: str

    @property
    def quest_id(self) -> str:
        return self.quest.quest_id if self.quest else ""

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "quest_id": self.quest_id,
            "confidence": self.confidence,
            "reason": self.reason,
        }


def normalize_question(value: str) -> str:
    return " ".join(_TOKEN_RE.findall(str(value or "").lower()))


def _compact(value: str) -> str:
    return "".join(_TOKEN_RE.findall(str(value or "").lower()))


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(str(value or "").lower()))


def _phrase_score(question: str, phrase: str) -> float:
    question_norm = normalize_question(question)
    phrase_norm = normalize_question(phrase)
    if question_norm == phrase_norm:
        return 1.0
    question_compact = _compact(question)
    phrase_compact = _compact(phrase)
    if phrase_compact and phrase_compact in question_compact:
        return 0.96
    if question_compact and question_compact in phrase_compact:
        return 0.92

    phrase_tokens = tuple(token for token in _tokens(phrase) if len(token) >= 2)
    question_tokens = _tokens(question)
    if not phrase_tokens or not question_tokens:
        return 0.0

    matched = 0
    for phrase_token in phrase_tokens:
        for question_token in question_tokens:
            if phrase_token in question_token or question_token in phrase_token:
                matched += 1
                break
    if matched < 2:
        return 0.0
    return min(0.9, matched / max(len(phrase_tokens), 1))


def _term_score(question: str, quest: Quest) -> float:
    terms_raw = quest.extra.get("match_terms", ())
    if not isinstance(terms_raw, list):
        return 0.0
    terms = tuple(term for term in terms_raw if isinstance(term, str) and term.strip())
    if not terms:
        return 0.0
    question_compact = _compact(question)
    matched_terms = tuple(term for term in terms if _compact(term) in question_compact)
    if len(matched_terms) < 2:
        return 0.0

    # Require one domain term and one intent term. Both groups live in quest
    # data, so adding more quests does not add router branches.
    domain_raw = quest.extra.get("domain_terms", ())
    intent_raw = quest.extra.get("intent_terms", ())
    domain_terms = tuple(
        term for term in domain_raw
        if isinstance(term, str) and term.strip()
    ) if isinstance(domain_raw, list) else ()
    intent_terms = tuple(
        term for term in intent_raw
        if isinstance(term, str) and term.strip()
    ) if isinstance(intent_raw, list) else ()
    has_domain = any(_compact(term) in question_compact for term in domain_terms)
    has_intent = any(_compact(term) in question_compact for term in intent_terms)
    if not (has_domain and has_intent):
        return 0.0
    return min(0.88, 0.55 + (0.08 * len(matched_terms)))


def match_quest(question: str, registry: QuestRegistry) -> QuestRouteResult:
    question_norm = normalize_question(question)
    if not question_norm:
        return QuestRouteResult(
            status="unsupported",
            quest=None,
            confidence=0.0,
            reason="empty_question",
        )

    best_quest: Quest | None = None
    best_score = 0.0
    best_reason = "no_match"
    for quest in registry.iter_quests():
        phrase_scores = [_phrase_score(question, phrase) for phrase in quest.user_phrases]
        phrase_best = max(phrase_scores) if phrase_scores else 0.0
        term_best = _term_score(question, quest)
        score = max(phrase_best, term_best)
        if score > best_score:
            best_quest = quest
            best_score = score
            best_reason = "phrase_match" if phrase_best >= term_best else "term_match"

    if best_quest is not None and best_score >= 0.72:
        return QuestRouteResult(
            status="matched",
            quest=best_quest,
            confidence=round(best_score, 3),
            reason=best_reason,
        )

    return QuestRouteResult(
        status="unsupported",
        quest=None,
        confidence=0.0,
        reason="unsupported_or_needs_confirmation",
    )
