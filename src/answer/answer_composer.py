"""AnswerComposer — generates grounded Markdown answers from search results.

Takes Stage 5 search result JSON and uses an LLM provider to produce
a source-grounded answer.
"""

from __future__ import annotations

import json
import os
from typing import Any

from ..llm import LLMProvider, ProviderResult, get_provider
from .url_guard import assess_url_allowlist

# ------------------------------------------------------------------
# System prompt template (fixed to enforce grounding)
# ------------------------------------------------------------------

SYSTEM_PROMPT = (
    "너는 AI파인더의 답변 작성자다.\n"
    "\n"
    "## 필수 규칙\n"
    "\n"
    "1. 반드시 제공된 source context 안의 정보만 사용해 답변한다.\n"
    "2. source context에 없는 사실은 절대 추측하거나 새로 만들지 않는다.\n"
    "3. URL, 메뉴명, 기관명, 담당자, 연락처, 기한, 금액은 source context에 "
    "근거가 있을 때만 말한다.\n"
    "4. 불확실한 내용은 \"확인 필요\"라고 표시한다.\n"
    "5. 사용자 질문과 무관한 내용을 답변에 포함하지 않는다.\n"
    "6. 존재하지 않는 URL을 만들어 링크를 생성하지 않는다.\n"
    "7. 출처가 하나도 없으면 \"관련 정보를 찾지 못했습니다\"라고 답변한다.\n"
    "\n"
    "## 답변 형식\n"
    "\n"
    "답변은 한국어 존댓말로 작성한다.\n"
    "\n"
    "답변에는 다음 섹션을 포함한다.\n"
    "\n"
    "- ## 답변\n"
    "- ## 관련 자료\n"
    "- ## 다음 단계\n"
    "- ## 확인 필요\n"
    "\n"
    "관련 자료에는 각 자료의 제목과 URL을 포함한다.\n"
    "URL이 있으면 반드시 표시한다.\n"
    "검색 결과가 첨부파일이면 \"첨부문서\"라고 표시한다.\n"
    "\n"
    "## 금지 사항\n"
    "\n"
    "- 사용자를 대신해 신청, 제출, 클릭, 결제를 수행한다고 말하지 않는다.\n"
    "- 자동화 대행처럼 표현하지 않는다.\n"
    "- 출처 없는 확정 표현을 절대 하지 않는다.\n"
    "- 임의로 URL을 생성하거나 링크를 만들지 않는다.\n"
    "\n"
    "## 확인 필요 안내\n"
    "\n"
    "모든 답변에는 마지막에 다음 문구를 포함한다:\n"
    "\"정확한 최신 내용은 연결된 공식 홈페이지에서 확인해 주세요.\""
)


class AnswerComposer:
    """Composes grounded answers from search results using an LLM provider.

    Usage::

        composer = AnswerComposer(provider="mock")
        result = composer.compose(search_result_data)
    """

    def __init__(
        self,
        provider: LLMProvider | str | None = None,
        max_sources: int = 5,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        model: str | None = None,
    ):
        if provider is None or isinstance(provider, str):
            self._provider: LLMProvider = get_provider(provider, model=model)
        else:
            self._provider = provider

        self._max_sources = max_sources
        self._temperature = temperature
        self._max_tokens = max_tokens

    def compose(
        self,
        search_result_json: str | dict[str, Any],
        max_sources: int | None = None,
    ) -> dict[str, Any]:
        """Run the full composition pipeline.

        Args:
            search_result_json: Either a JSON string or a parsed dict
                                from the Stage 5 keyword search output.
            max_sources: Override the default max_sources for this call.

        Returns:
            A result dict with keys:
                query, provider, model, ok, answer_markdown, sources, warnings, error
        """
        # --- Parse input ---
        data = self._parse_input(search_result_json)
        query = data.get("query", "")
        results = data.get("results", [])

        # --- Extract sources ---
        sources = self._extract_sources(results, max_sources or self._max_sources)

        # --- No results: short-circuit without calling LLM ---
        if not results or not sources:
            guidance = self._build_no_source_guidance(query)
            guidance["guard_status"] = "no_results"
            guidance["guard_reason"] = "No sources retrieved"
            return guidance

        # --- Source match guard ---
        from ..search.source_match_guard import assess_source_match
        query_rewrite = data.get("query_rewrite", {})
        query_rewrite_queries = query_rewrite.get("queries", [])
        assessment = assess_source_match(
            query,
            sources,
            query_rewrite_queries=query_rewrite_queries
        )

        if assessment.status == "no_results":
            no_res = self._build_no_source_guidance(query)
            no_res["warnings"] = [assessment.reason]
            no_res["guard_status"] = assessment.status
            no_res["guard_reason"] = assessment.reason
            return no_res

        guard_warnings = []
        if assessment.status == "warn":
            guard_warnings.append(assessment.reason)

        # --- Build source context and messages ---
        source_context = self._build_source_context(sources)
        messages = self._build_messages(query, source_context)

        # --- Call provider ---
        provider_result = self._provider.complete(
            messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )

        # --- Build output ---
        if not provider_result.ok:
            return {
                "query": query,
                "provider": provider_result.provider,
                "model": provider_result.model,
                "ok": False,
                "answer_markdown": "",
                "sources": sources,
                "warnings": [provider_result.error] + guard_warnings,
                "error": provider_result.error,
                "guard_status": assessment.status,
                "guard_reason": assessment.reason,
            }

        # --- URL allowlist guard ---
        url_assessment = assess_url_allowlist(provider_result.content, sources)

        if not url_assessment["passed"]:
            return {
                "query": query,
                "provider": provider_result.provider,
                "model": provider_result.model,
                "ok": False,
                "answer_markdown": "",
                "sources": sources,
                "warnings": guard_warnings + ["untrusted_output_url"],
                "error": "untrusted_output_url",
                "guard_status": "blocked_untrusted_output_url",
                "guard_reason": "Provider output contained a URL that is not an exact retrieved source URL.",
            }

        return {
            "query": query,
            "provider": provider_result.provider,
            "model": provider_result.model,
            "ok": True,
            "answer_markdown": provider_result.content,
            "sources": sources,
            "warnings": guard_warnings,
            "error": "",
            "guard_status": assessment.status,
            "guard_reason": assessment.reason,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_input(data: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, str):
            return json.loads(data)
        return data

    @staticmethod
    def _extract_sources(
        results: list[dict[str, Any]], max_sources: int
    ) -> list[dict[str, Any]]:
        sources = []
        for res in results[:max_sources]:
            metadata = res.get("metadata", {}) or {}
            sources.append({
                "rank": res.get("rank", 0),
                "id": res.get("id", ""),
                "title": res.get("title", ""),
                "url": res.get("url", ""),
                "canonical_url": res.get("canonical_url", ""),
                "category": res.get("category", ""),
                "content_type": res.get("content_type", ""),
                "score": res.get("score", 0.0),
                "matched_terms": res.get("matched_terms", []),
                "matched_fields": res.get("matched_fields", []),
                "snippet": res.get("snippet", ""),
                "description": metadata.get("description", ""),
                "fetch_status": metadata.get("fetch_status", ""),
                "source_types": metadata.get("source_types", []),
            })
        return sources

    @staticmethod
    def _build_source_context(sources: list[dict[str, Any]]) -> str:
        lines = []
        for src in sources:
            lines.append(f"[Source {src['rank']}]")
            lines.append(f"id: {src['id']}")
            lines.append(f"title: {src['title']}")
            lines.append(f"url: {src['url']}")
            lines.append(f"category: {src['category']}")
            lines.append(f"content_type: {src['content_type']}")
            lines.append(f"score: {src['score']}")
            matched_terms = src.get("matched_terms", [])
            lines.append(f"matched_terms: {', '.join(matched_terms) if isinstance(matched_terms, list) else matched_terms}")
            matched_fields = src.get("matched_fields", [])
            lines.append(f"matched_fields: {', '.join(matched_fields) if isinstance(matched_fields, list) else matched_fields}")
            lines.append(f"fetch_status: {src['fetch_status']}")
            source_types = src.get("source_types", [])
            lines.append(f"source_types: {', '.join(source_types) if isinstance(source_types, list) else source_types}")
            description = src.get("description", "")
            if len(description) > 300:
                description = description[:300] + "..."
            lines.append(f"description: {description}")
            snippet = src.get("snippet", "")
            if len(snippet) > 500:
                snippet = snippet[:500] + "..."
            lines.append(f"snippet: {snippet}")
            lines.append("")  # blank line between sources
        return "\n".join(lines).rstrip("\n")

    def _build_messages(
        self, query: str, source_context: str
    ) -> list[dict[str, str]]:
        user_prompt = (
            f"## 사용자 질문\n\n{query}\n\n"
            f"## Source Context\n\n{source_context}\n\n"
            f"위 Source Context의 정보만 사용하여 답변을 작성하라.\n"
            f"출력은 한국어 존댓말 Markdown으로 한다."
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    @staticmethod
    def _no_results_answer(query: str) -> dict[str, Any]:
        return {
            "query": query,
            "provider": "none",
            "model": "",
            "ok": True,
            "answer_markdown": (
                "## 답변\n\n"
                "관련 자료를 찾지 못했습니다.\n\n"
                "## 다음 단계\n\n"
                "검색어를 바꾸거나 홈페이지 원문을 다시 확인해야 합니다.\n\n"
                "## 확인 필요\n\n"
                "정확한 최신 내용은 연결된 공식 홈페이지에서 확인해 주세요."
            ),
            "sources": [],
            "warnings": ["no search results"],
            "error": "",
            "guard_status": None,
            "guard_reason": None,
        }

    def _build_no_source_guidance(self, query: str) -> dict[str, Any]:
        normalized = (query or "").strip()
        hints: list[str] = []
        lower_query = normalized.lower()

        if any(k in lower_query for k in ["구청장", "기관장", "mayor", "총장", "국장"]):
            hints = ["구청장실", "기관장 소개", "인사말"]
        elif any(k in lower_query for k in ["담당자", "연락처", "전화번호", "부서", "담당", "contact"]):
            hints = ["조직도", "직원검색", "부서안내"]
        elif any(k in lower_query for k in ["주차", "위치", "오시는 길", "주소", "parking", "오시는길"]):
            hints = ["청사안내", "오시는 길", "주차안내"]
        elif any(k in lower_query for k in ["민원", "신청", "서식", "접수", "양식", "form"]):
            hints = ["민원", "민원서식", "신청/접수", "자주찾는 서비스"]
        else:
            hints = ["홈페이지 통합검색", "관련 메뉴"]

        hint_lines = "\n".join(f"- {hint}" for hint in hints)
        answer_markdown = (
            "## 답변\n\n"
            "공식 홈페이지에서 답변 근거 자료를 찾지 못했습니다.\n\n"
            "## 확인해 볼 만한 경로\n\n"
            f"{hint_lines}\n\n"
            "## 다음 단계\n\n"
            "홈페이지 관련 메뉴나 통합검색에서 다시 확인해 주세요.\n\n"
            "## 확인 필요\n\n"
            "정확한 최신 내용은 연결된 공식 홈페이지에서 확인해 주세요."
        )
        return {
            "query": normalized,
            "provider": "none",
            "model": "",
            "ok": True,
            "answer_markdown": answer_markdown,
            "sources": [],
            "warnings": ["no search results", "no_source_guidance"],
            "error": "",
            "guard_status": "no_results",
            "guard_reason": "No official sources retrieved.",
            "query_hints": hints,
        }


# ------------------------------------------------------------------
# Convenience function
# ------------------------------------------------------------------

def compose_answer(
    search_result_json: str | dict[str, Any],
    provider: LLMProvider | str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """One-shot convenience function to compose an answer.

    Args:
        search_result_json: Stage 5 search result JSON (str or dict).
        provider: LLM provider name, instance, or None (= env default).
        **kwargs: Passed through to AnswerComposer (max_sources, etc.).

    Returns:
        The composed answer dict.
    """
    composer = AnswerComposer(provider=provider, **kwargs)
    return composer.compose(search_result_json)
