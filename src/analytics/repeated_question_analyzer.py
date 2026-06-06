"""Repeated-question analytics and scenario-cache promotion planning helper.

Reads sanitized QuestionLogEvent objects to identify repeated user questions
and generate promotion candidates or retrieval gap reports for human review.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Any


@dataclass(frozen=True)
class RepeatedQuestionGroup:
    """Group of repeated questions with normalized key and metadata summary."""
    normalized_key: str
    example_questions: tuple[str, ...]
    count: int
    site_ids: tuple[str, ...]
    answer_statuses: tuple[str, ...]
    source_domains: tuple[str, ...]
    fallback_count: int
    no_results_count: int
    guard_statuses: tuple[str, ...]


@dataclass(frozen=True)
class PromotionCandidate:
    """Candidate for scenario or cache promotion, or retrieval gap review."""
    normalized_key: str
    representative_question: str
    count: int
    reason: str
    confidence: str  # "low" | "medium" | "high"
    recommended_action: str  # "review_for_cache" | "review_for_scenario" | "monitor" | "retrieval_gap"
    source_domains: tuple[str, ...]
    warnings: tuple[str, ...]


def analyze_repeated_questions(
    events: Sequence[Mapping[str, Any]],
    *,
    min_count: int = 3,
) -> tuple[PromotionCandidate, ...]:
    """Group and analyze question log events to find repeated patterns.

    Returns:
        Tuple of PromotionCandidate objects sorted by frequency count descending.
        Does not automatically write files or modify database configs.
    """
    from .question_logger import sanitize_text, _normalize_question

    groups: dict[str, list[Mapping[str, Any]]] = {}
    for event in events:
        norm_key = event.get("normalized_question")
        if not norm_key:
            raw_q = str(event.get("raw_question", ""))
            norm_key = _normalize_question(raw_q)
            
        if not norm_key:
            continue
            
        groups.setdefault(norm_key, []).append(event)

    candidates: list[PromotionCandidate] = []

    for norm_key, group_events in groups.items():
        count = len(group_events)
        if count < min_count:
            continue
            
        raw_qs: list[str] = []
        site_ids: list[str] = []
        answer_statuses: list[str] = []
        source_domains: list[str] = []
        guard_statuses: list[str] = []
        fallback_count = 0
        no_results_count = 0
        
        for e in group_events:
            raw_q = str(e.get("raw_question", ""))
            san_q = sanitize_text(raw_q)
            if san_q and san_q not in raw_qs:
                raw_qs.append(san_q)
                
            sid = e.get("site_id")
            if sid and str(sid) not in site_ids:
                site_ids.append(str(sid))
                
            ans_status = e.get("answer_status") or "unknown"
            if str(ans_status) not in answer_statuses:
                answer_statuses.append(str(ans_status))
                
            guard_status = e.get("guard_status")
            if guard_status and str(guard_status) not in guard_statuses:
                guard_statuses.append(str(guard_status))
                
            if e.get("fallback_used") is True:
                fallback_count += 1
                
            if ans_status == "no_results" or guard_status == "no_results":
                no_results_count += 1
                
            domains = e.get("source_domains") or ()
            for d in domains:
                san_d = sanitize_text(str(d))
                if san_d and san_d not in source_domains:
                    source_domains.append(san_d)
                    
        # 1. Determine recommended action
        if no_results_count >= count / 2:
            rec_action = "retrieval_gap"
            reason = f"Repeated question resulting in NO_RESULTS ({no_results_count}/{count} times)"
            confidence = "high"
        elif "success" in answer_statuses and not any(gs == "no_results" for gs in guard_statuses):
            if fallback_count <= count / 3:
                rec_action = "review_for_cache"
                reason = "Highly repeated successful official-domain query"
                confidence = "high" if count >= min_count + 2 else "medium"
            else:
                rec_action = "review_for_scenario"
                reason = "Repeated question with fallback/navigation sources used"
                confidence = "medium"
        else:
            rec_action = "monitor"
            reason = "Repeated question with weak or mixed signals"
            confidence = "low"
            
        repr_question = raw_qs[0] if raw_qs else norm_key
        
        candidates.append(PromotionCandidate(
            normalized_key=norm_key,
            representative_question=repr_question,
            count=count,
            reason=reason,
            confidence=confidence,
            recommended_action=rec_action,
            source_domains=tuple(sorted(source_domains)),
            warnings=()
        ))
        
    # Sort candidates by count descending
    candidates.sort(key=lambda c: -c.count)
    return tuple(candidates)
