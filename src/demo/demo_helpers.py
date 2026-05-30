"""Helper functions for Korean tokenization, homepage map fallbacks, and answer generation."""

from __future__ import annotations
import re
from typing import Any

def tokenize_korean(text: str) -> list[str]:
    """Simple tokenization for Korean menu keywords."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower()).strip()
    tokens = [t for t in cleaned.split() if len(t) > 1]
    return tokens


def match_keyword_against_links(
    keywords: list[str],
    links: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find links whose title or text matches any keyword."""
    matched = []
    seen_urls: set[str] = set()
    for link in links:
        title = (link.get("title") or link.get("text") or "").strip()
        url = link.get("url", "")
        if not title or not url:
            continue
        if url in seen_urls:
            continue
        title_lower = title.lower()
        for kw in keywords:
            if kw.lower() in title_lower:
                matched.append({"title": title, "url": url})
                seen_urls.add(url)
                break
    return matched


def fallback_sources_from_homepage_map(
    homepage_map: dict[str, Any],
    question: str,
    important_keywords: list[str],
) -> list[dict[str, Any]]:
    """Build fallback sources from homepage_map menu/navigation links."""
    question_tokens = tokenize_korean(question)

    expanded_tokens = list(question_tokens)
    for kw in important_keywords:
        kw_lower = kw.lower()
        for token in question_tokens:
            if token in kw_lower or kw_lower in token:
                if kw not in expanded_tokens:
                    expanded_tokens.append(kw)
                break

    candidates: list[dict[str, Any]] = []

    nav_links = homepage_map.get("homepage", {}).get("navigation_links", [])
    nav_matches = match_keyword_against_links(expanded_tokens, nav_links)
    for m in nav_matches:
        candidates.append({**m, "source_type": "navigation", "score": 10.0})

    categories = homepage_map.get("categories", {})
    priority_cats = ["menu", "apply", "notice", "board", "document"]
    for cat in priority_cats:
        cat_links = categories.get(cat, [])
        cat_matches = match_keyword_against_links(expanded_tokens, cat_links)
        for m in cat_matches:
            candidates.append({**m, "source_type": cat, "score": 8.0})

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for c in candidates:
        if c["url"] not in seen:
            seen.add(c["url"])
            deduped.append(c)

    return deduped[:5]


def extract_topic_from_question(question: str) -> str:
    """Extract the main topic keyword from a Korean question."""
    q = question.strip()
    tokens = tokenize_korean(q)
    if not tokens:
        return q
    topic = tokens[0]
    particles = ("에서는", "에서", "는", "은", "을", "를", "의", "에", "로", "이", "가")
    for p in particles:
        if topic.endswith(p) and len(topic) > len(p) + 1:
            topic = topic[: -len(p)]
            break
    return topic


def generate_answer_from_sources(
    question: str,
    sources: list[dict[str, Any]],
    site_name: str,
) -> str:
    """Generate a user-friendly answer from question + matched sources."""
    topic = extract_topic_from_question(question)

    if not sources:
        return (
            f"## 답변\n\n"
            f"'{topic}' 관련 정보를 찾지 못했습니다.\n\n"
            f"## 다음 단계\n\n"
            f"{site_name} 홈페이지에서 직접 검색해 보시거나, "
            f"다른 키워드로 다시 질문해 주세요.\n\n"
            f"## 확인 필요\n\n"
            f"정확한 최신 내용은 연결된 공식 홈페이지에서 확인해 주세요."
        )

    source_names = []
    for s in sources[:3]:
        title = s.get("title", "").strip()
        if title and title not in source_names:
            source_names.append(title)

    main_source = source_names[0] if source_names else topic

    answer = (
        f"## 답변\n\n"
        f"찾으시는 내용은 '{topic}'에 해당합니다.\n\n"
        f"{site_name} 홈페이지의 {main_source} 메뉴에서 "
        f"관련 정보를 확인할 수 있습니다.\n\n"
        f"아래 관련 홈페이지 바로가기를 눌러 해당 페이지로 이동해 주세요.\n\n"
        f"## 확인 필요\n\n"
        f"정확한 최신 내용은 연결된 공식 홈페이지에서 확인해 주세요."
    )

    return answer
