"""Source mismatch / weak retrieval guard.

Detects if retrieved sources do not sufficiently match the original question,
allowing the system to safely fallback to a low-confidence/no-results response
rather than compose a confident wrong answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence, Any


@dataclass(frozen=True)
class SourceMatchAssessment:
    """Assessment of retrieved sources against the original question."""
    status: str  # "pass" | "warn" | "no_results"
    reason: str
    matched_terms: tuple[str, ...] = ()


TOPICS = {
    "mayor": {"구청장", "시청장", "군수", "도지사", "청장", "시장", "프로필", "인사말", "열린구청장", "북구청장"},
    "youth_jobs": {"청년", "일자리", "채용", "고용", "취업", "알바", "아르바이트", "경제", "비즈광주북구"},
    "civil": {"민원", "신청", "접수", "서식", "여권", "인감", "가족관계", "발급", "증명", "민원실", "종합민원"},
    "notice": {"고시공고", "고시", "공고", "공지사항", "공지", "입법예고", "새소식"},
    "info_disclosure": {"정보공개", "공개청구", "계약정보", "예산", "재정"},
    "welfare": {"복지", "지원금", "기초수급", "수급", "장애인", "노인", "아동", "지원사업"},
    "education": {"교육", "교육접수", "평생교육", "강좌", "프로그램", "수강"},
}

GENERIC_STOPWORDS = {
    "어디", "어디서", "어떻게", "방법", "알려줘", "확인", "조회", "검색", 
    "홈페이지", "누구", "이름", "누구야", "알려", "좀", "해", "봐", "하고",
    "이", "가", "을", "를", "은", "는", "에", "의", "로", "으로", "에서"
}


def _extract_tokens(text: str) -> set[str]:
    if not text:
        return set()
    cleaned = re.sub(r'[:\s,\.\(\)\[\]/\\\-_?&=~;!@#$^*+`·<>"\']+', ' ', text.lower())
    # Strip common Korean particles
    particles = (
        "은", "는", "이", "가", "을", "를", "에", "의", "로", "으로",
        "과", "와", "도", "만", "에서", "까지", "부터", "이라", "라고",
        "며", "면", "지만", "거나", "든지", "요", "죠", "까요",
    )
    tokens = set()
    for tok in cleaned.split():
        if len(tok) > 1:
            tokens.add(tok)
            for p in particles:
                if tok.endswith(p) and len(tok) > len(p) + 1:
                    tokens.add(tok[:-len(p)])
    return tokens


def assess_source_match(
    question: str,
    sources: Sequence[dict[str, Any]],
    *,
    query_rewrite_queries: Sequence[str] = (),
) -> SourceMatchAssessment:
    """Assess if the retrieved sources match the user question.

    Ensures that if retrieved sources do not sufficiently match the original question,
    the system returns a low-confidence/no-results response.
    """
    if not sources:
        return SourceMatchAssessment(status="no_results", reason="No sources retrieved")

    norm_q = question.lower()
    
    # 1. Detect active predefined topics in the original question
    active_topics = set()
    for topic_name, keywords in TOPICS.items():
        for kw in keywords:
            # Substring match to be robust to compound nouns/particles
            if kw in norm_q:
                active_topics.add(topic_name)
                break

    # 2. If predefined topics are active, check topic matching in sources
    if active_topics:
        topic_matches = {topic: False for topic in active_topics}
        matched_topic_kws = set()
        
        for topic in active_topics:
            keywords = TOPICS[topic]
            for src in sources:
                title = src.get("title", "") or ""
                snippet = src.get("snippet", "") or ""
                category = src.get("category", "") or ""
                description = src.get("description", "") or ""
                matched_terms = src.get("matched_terms", []) or []
                
                src_text = f"{title} {snippet} {category} {description} {' '.join(matched_terms)}".lower()
                for kw in keywords:
                    if kw in src_text:
                        topic_matches[topic] = True
                        matched_topic_kws.add(kw)
        
        # If any active topic in the question is completely unmatched in all sources, it's a mismatch
        unmatched_topics = [t for t, matched in topic_matches.items() if not matched]
        if unmatched_topics:
            return SourceMatchAssessment(
                status="no_results",
                reason=f"Topic mismatch: question topics {unmatched_topics} not found in retrieved sources",
                matched_terms=tuple(sorted(list(matched_topic_kws))),
            )
            
        return SourceMatchAssessment(
            status="pass",
            reason="Topic matches confirmed",
            matched_terms=tuple(sorted(list(matched_topic_kws))),
        )

    # 3. Generic token overlap fallback (for non-predefined topics)
    q_tokens = _extract_tokens(question)
    content_q_tokens = q_tokens - GENERIC_STOPWORDS
    if not content_q_tokens:
        content_q_tokens = q_tokens

    # Collect rewrite tokens
    rewrite_tokens = set()
    for rq in query_rewrite_queries:
        rewrite_tokens.update(_extract_tokens(rq))
    content_rewrite_tokens = rewrite_tokens - GENERIC_STOPWORDS

    # Check matches in sources
    matched_q_tokens = set()
    matched_rewrite_tokens = set()
    
    for src in sources:
        title = src.get("title", "") or ""
        snippet = src.get("snippet", "") or ""
        category = src.get("category", "") or ""
        description = src.get("description", "") or ""
        matched_terms = src.get("matched_terms", []) or []
        
        src_text = f"{title} {snippet} {category} {description} {' '.join(matched_terms)}".lower()
        
        for tok in content_q_tokens:
            if tok in src_text:
                matched_q_tokens.add(tok)
        for tok in content_rewrite_tokens:
            if tok in src_text:
                matched_rewrite_tokens.add(tok)

    # Check if only fallback/navigation sources exist
    all_fallback = True
    for src in sources:
        cat = src.get("category", "").lower()
        title = src.get("title", "").lower()
        is_fallback = cat in ("navigation", "main") or "홈페이지" in title or "바로가기" in title
        if not is_fallback:
            all_fallback = False
            break
            
    if all_fallback:
        if len(matched_q_tokens) < 1:
            return SourceMatchAssessment(
                status="no_results",
                reason="Only navigation/fallback sources returned with weak relevance",
            )

    # Decision logic for generic queries
    if not matched_q_tokens and not matched_rewrite_tokens:
        return SourceMatchAssessment(
            status="no_results",
            reason="No overlapping terms found between question/rewrites and sources",
        )
        
    if not matched_q_tokens and matched_rewrite_tokens:
        return SourceMatchAssessment(
            status="warn",
            reason="Sources match query rewrites but have weak overlap with original question",
            matched_terms=tuple(sorted(list(matched_rewrite_tokens))),
        )

    return SourceMatchAssessment(
        status="pass",
        reason="Grounded search results verified",
        matched_terms=tuple(sorted(list(matched_q_tokens))),
    )
