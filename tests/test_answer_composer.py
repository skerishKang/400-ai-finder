"""Tests for AnswerComposer — answer composition from search results.

All tests use MockProvider — no real API calls.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.llm import MockProvider
from src.answer.answer_composer import AnswerComposer, compose_answer

# ------------------------------------------------------------------
# Sample search result data
# ------------------------------------------------------------------

SAMPLE_SEARCH_RESULTS = {
    "query": "신청서 제출서류",
    "top_k": 5,
    "filters": {"category": "", "content_type": ""},
    "result_count": 2,
    "results": [
        {
            "rank": 1,
            "id": "doc-000002",
            "title": "신청서 양식",
            "url": "https://example.com/files/form.pdf",
            "canonical_url": "https://example.com/files/form.pdf",
            "category": "document",
            "content_type": "attachment",
            "score": 15.0,
            "matched_terms": ["신청서"],
            "matched_fields": ["metadata.link_texts", "title"],
            "snippet": "신청서 양식",
            "metadata": {
                "source_types": ["attachment"],
                "fetch_status": "skipped",
                "description": "",
            },
        },
        {
            "rank": 2,
            "id": "doc-000001",
            "title": "지원사업 신청 안내",
            "url": "https://example.com/apply",
            "canonical_url": "https://example.com/apply",
            "category": "apply",
            "content_type": "page",
            "score": 5.0,
            "matched_terms": ["신청서", "제출서류"],
            "matched_fields": ["text"],
            "snippet": (
                "이 페이지는 중소기업 지원사업 신청 방법과 제출서류를 안내합니다. "
                "신청서는 자료실에서 내려받을 수 있습니다."
            ),
            "metadata": {
                "source_types": ["navigation", "sitemap"],
                "fetch_status": "fetched",
                "description": "지원사업 신청 안내",
            },
        },
    ],
}

EMPTY_SEARCH_RESULTS = {
    "query": "존재하지 않는 문서",
    "top_k": 5,
    "filters": {"category": "", "content_type": ""},
    "result_count": 0,
    "results": [],
}


# ======================================================================
# Source context generation
# ======================================================================

class TestBuildSourceContext:
    def test_two_sources(self):
        """Two search results become [Source 1] and [Source 2]."""
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(SAMPLE_SEARCH_RESULTS["results"], 5)
        ctx = composer._build_source_context(sources)
        assert "[Source 1]" in ctx
        assert "[Source 2]" in ctx
        assert "신청서 양식" in ctx
        assert "https://example.com/files/form.pdf" in ctx
        assert "지원사업 신청 안내" in ctx
        assert "https://example.com/apply" in ctx

    def test_fields_present(self):
        """Each source has title, url, category, content_type."""
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(SAMPLE_SEARCH_RESULTS["results"], 5)
        ctx = composer._build_source_context(sources)
        assert "title:" in ctx
        assert "url:" in ctx
        assert "category:" in ctx
        assert "content_type:" in ctx

    def test_evidence_fields_in_context(self):
        """Source context includes evidence fields."""
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(SAMPLE_SEARCH_RESULTS["results"], 5)
        ctx = composer._build_source_context(sources)
        assert "score:" in ctx
        assert "matched_terms:" in ctx
        assert "matched_fields:" in ctx
        assert "fetch_status:" in ctx
        assert "source_types:" in ctx
        assert "description:" in ctx
        assert "snippet:" in ctx

    def test_matched_terms_joined(self):
        """matched_terms list is joined as comma-separated string."""
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(SAMPLE_SEARCH_RESULTS["results"], 5)
        ctx = composer._build_source_context(sources)
        assert "신청서, 제출서류" in ctx

    def test_matched_fields_joined(self):
        """matched_fields list is joined as comma-separated string."""
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(SAMPLE_SEARCH_RESULTS["results"], 5)
        ctx = composer._build_source_context(sources)
        assert "metadata.link_texts, title" in ctx

    def test_source_types_joined(self):
        """source_types list is joined as comma-separated string."""
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(SAMPLE_SEARCH_RESULTS["results"], 5)
        ctx = composer._build_source_context(sources)
        assert "navigation, sitemap" in ctx

    def test_snippet_truncation(self):
        """Snippet longer than 500 chars is truncated."""
        long_snippet = "x" * 600
        results = [
            {
                "rank": 1,
                "id": "doc-long",
                "title": "긴 문서",
                "url": "https://example.com/long",
                "category": "document",
                "content_type": "page",
                "score": 10.0,
                "matched_terms": ["테스트"],
                "matched_fields": ["text"],
                "snippet": long_snippet,
                "metadata": {
                    "description": "",
                    "fetch_status": "fetched",
                    "source_types": ["page"],
                },
            }
        ]
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(results, 5)
        ctx = composer._build_source_context(sources)
        assert "x" * 500 in ctx
        assert "x" * 501 not in ctx
        assert "..." in ctx

    def test_description_truncation(self):
        """Description longer than 300 chars is truncated."""
        long_desc = "y" * 400
        results = [
            {
                "rank": 1,
                "id": "doc-desc",
                "title": "긴 설명",
                "url": "https://example.com/desc",
                "category": "document",
                "content_type": "page",
                "score": 10.0,
                "matched_terms": ["테스트"],
                "matched_fields": ["text"],
                "snippet": "snippet",
                "metadata": {
                    "description": long_desc,
                    "fetch_status": "fetched",
                    "source_types": ["page"],
                },
            }
        ]
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(results, 5)
        ctx = composer._build_source_context(sources)
        assert "y" * 300 in ctx
        assert "y" * 301 not in ctx
        assert "..." in ctx

    def test_max_sources_truncation(self):
        """Only up to max_sources are included."""
        many_results = SAMPLE_SEARCH_RESULTS["results"] * 5  # 10 items
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(many_results, 3)
        assert len(sources) == 3


# ======================================================================
# Messages generation
# ======================================================================

class TestBuildMessages:
    def test_system_and_user_messages(self):
        """Messages contain a system message and a user message."""
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(SAMPLE_SEARCH_RESULTS["results"], 5)
        ctx = composer._build_source_context(sources)
        messages = composer._build_messages("신청서 제출서류", ctx)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_system_prompt_grounding_principle(self):
        """System prompt includes the grounding principle."""
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(SAMPLE_SEARCH_RESULTS["results"], 5)
        ctx = composer._build_source_context(sources)
        messages = composer._build_messages("신청서 제출서류", ctx)
        sys_prompt = messages[0]["content"]
        assert "source context" in sys_prompt.lower()
        assert "추측" in sys_prompt

    def test_user_message_contains_query_and_context(self):
        """User message includes the query and source context."""
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(SAMPLE_SEARCH_RESULTS["results"], 5)
        ctx = composer._build_source_context(sources)
        messages = composer._build_messages("신청서 제출서류", ctx)
        user_prompt = messages[1]["content"]
        assert "신청서 제출서류" in user_prompt
        assert "Source Context" in user_prompt


# ======================================================================
# No search results handling
# ======================================================================

class TestNoSearchResults:
    def test_empty_results_returns_no_source_answer(self):
        """When results are empty, return improved no-source guidance."""
        composer = AnswerComposer(provider="mock")
        result = composer.compose(EMPTY_SEARCH_RESULTS)
        assert result["ok"] is True
        assert "공식 홈페이지에서 답변 근거 자료를 찾지 못했습니다" in result["answer_markdown"]
        assert result["sources"] == []
        assert "no search results" in result["warnings"]
        assert "no_source_guidance" in result["warnings"]
        assert result["provider"] == "none"
        assert result["guard_status"] == "no_results"
        assert "query_hints" in result

    def test_empty_results_skips_llm_call(self):
        """No search results means no LLM provider call."""
        class SpyProvider(MockProvider):
            def __init__(self):
                super().__init__()
                self.called = False

            def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
                self.called = True
                return super().complete(messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout)

        spy = SpyProvider()
        composer = AnswerComposer(provider=spy)
        result = composer.compose(EMPTY_SEARCH_RESULTS)
        assert spy.called is False
        assert "no_source_guidance" in result["warnings"]
        assert result["provider"] == "none"

    def test_json_string_input(self):
        """Accept search results as a JSON string."""
        composer = AnswerComposer(provider="mock")
        json_str = json.dumps(EMPTY_SEARCH_RESULTS, ensure_ascii=False)
        result = composer.compose(json_str)
        assert result["ok"] is True
        assert "공식 홈페이지에서 답변 근거 자료를 찾지 못했습니다" in result["answer_markdown"]
        assert "no_source_guidance" in result["warnings"]
        assert result["provider"] == "none"


# ======================================================================
# Full composition with mock provider
# ======================================================================

class TestComposeWithMock:
    def test_mock_compose_returns_answer(self):
        """Mock provider compose returns a valid answer."""
        composer = AnswerComposer(provider="mock")
        result = composer.compose(SAMPLE_SEARCH_RESULTS)
        assert result["ok"] is True
        assert result["answer_markdown"]  # non-empty
        assert result["provider"] == "mock"
        assert result["model"] == "mock"

    def test_sources_preserved(self):
        """Sources list is preserved in the output."""
        composer = AnswerComposer(provider="mock")
        result = composer.compose(SAMPLE_SEARCH_RESULTS)
        assert len(result["sources"]) == 2
        assert result["sources"][0]["title"] == "신청서 양식"
        assert result["sources"][1]["title"] == "지원사업 신청 안내"

    def test_sources_evidence_fields_preserved(self):
        """Evidence fields are preserved in output sources."""
        composer = AnswerComposer(provider="mock")
        result = composer.compose(SAMPLE_SEARCH_RESULTS)
        s1 = result["sources"][0]
        assert s1["score"] == 15.0
        assert s1["matched_terms"] == ["신청서"]
        assert s1["matched_fields"] == ["metadata.link_texts", "title"]
        assert s1["snippet"] == "신청서 양식"
        assert s1["fetch_status"] == "skipped"
        assert s1["source_types"] == ["attachment"]

    def test_query_preserved(self):
        """Query string is preserved in the output."""
        composer = AnswerComposer(provider="mock")
        result = composer.compose(SAMPLE_SEARCH_RESULTS)
        assert result["query"] == "신청서 제출서류"


# ======================================================================
# Source extraction
# ======================================================================

class TestExtractSources:
    def test_source_fields_preserved(self):
        """All required source fields are present."""
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(SAMPLE_SEARCH_RESULTS["results"], 5)
        assert len(sources) == 2
        s1 = sources[0]
        assert s1["rank"] == 1
        assert s1["id"] == "doc-000002"
        assert s1["title"] == "신청서 양식"
        assert s1["url"] == "https://example.com/files/form.pdf"
        assert s1["category"] == "document"
        assert s1["content_type"] == "attachment"

    def test_evidence_fields_preserved(self):
        """Evidence fields (score, matched_terms, etc.) are preserved."""
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(SAMPLE_SEARCH_RESULTS["results"], 5)
        s1 = sources[0]
        assert s1["score"] == 15.0
        assert s1["matched_terms"] == ["신청서"]
        assert s1["matched_fields"] == ["metadata.link_texts", "title"]
        assert s1["snippet"] == "신청서 양식"
        assert s1["description"] == ""
        assert s1["fetch_status"] == "skipped"
        assert s1["source_types"] == ["attachment"]

        s2 = sources[1]
        assert s2["score"] == 5.0
        assert s2["matched_terms"] == ["신청서", "제출서류"]
        assert s2["matched_fields"] == ["text"]
        assert "중소기업 지원사업" in s2["snippet"]
        assert s2["description"] == "지원사업 신청 안내"
        assert s2["fetch_status"] == "fetched"
        assert s2["source_types"] == ["navigation", "sitemap"]

    def test_max_sources(self):
        """Only max_sources sources are extracted."""
        results = SAMPLE_SEARCH_RESULTS["results"]
        composer = AnswerComposer(provider="mock")
        sources = composer._extract_sources(results, max_sources=1)
        assert len(sources) == 1
        assert sources[0]["rank"] == 1


# ======================================================================
# Convenience function
# ======================================================================

class TestComposeAnswerFunction:
    def test_compose_answer_returns_result(self):
        """compose_answer() convenience function works."""
        result = compose_answer(
            SAMPLE_SEARCH_RESULTS, provider="mock",
        )
        assert result["ok"] is True
        assert "답변" in result["answer_markdown"]

    def test_compose_answer_empty(self):
        """compose_answer() with empty results works."""
        result = compose_answer(EMPTY_SEARCH_RESULTS, provider="mock")
        assert result["ok"] is True
        assert "공식 홈페이지에서 답변 근거 자료를 찾지 못했습니다" in result["answer_markdown"]
        assert "no_source_guidance" in result["warnings"]
        assert result["provider"] == "none"


# ======================================================================
# No source guidance validation
# ======================================================================

class TestNoSourceGuidance:
    def test_empty_results_returns_helpful_guidance(self):
        """No-results path returns improved guidance without inventing facts."""
        composer = AnswerComposer(provider="mock")
        result = composer.compose(EMPTY_SEARCH_RESULTS)
        assert result["ok"] is True
        assert "공식 홈페이지에서 답변 근거 자료를 찾지 못했습니다" in result["answer_markdown"]
        assert "## 확인해 볼 만한 경로" in result["answer_markdown"]
        assert result["sources"] == []
        assert "no search results" in result["warnings"]
        assert "no_source_guidance" in result["warnings"]
        assert result["provider"] == "none"
        assert result["guard_status"] == "no_results"

    def test_mayor_question_returns_menu_hints_not_names(self):
        """Mayor questions must show menu hints in answer text and not invent facts."""
        composer = AnswerComposer(provider="mock")
        result = composer.compose({"query": "구청장이 누구야?", "results": []})
        assert result["ok"] is True
        text = result["answer_markdown"]
        assert "근거 자료를 찾지 못했습니다" in text
        assert "- 구청장실" in text
        assert "- 기관장 소개" in text
        assert "- 인사말" in text
        assert result["provider"] == "none"
        assert result["guard_status"] == "no_results"

    def test_contact_question_returns_org_hints_not_numbers(self):
        """Contact questions must show org-menu hints and no phone numbers."""
        composer = AnswerComposer(provider="mock")
        result = composer.compose({"query": "담당자 연락처 알려줘", "results": []})
        assert result["ok"] is True
        text = result["answer_markdown"]
        assert "- 조직도" in text
        assert "- 직원검색" in text
        assert "- 부서안내" in text
        phone_prefixes = ["010", "070", "02-", "031-", "032-", "042-", "051-", "053-", "062-", "063-", "064-"]
        assert all(p not in text for p in phone_prefixes)
        assert result["guard_status"] == "no_results"

    def test_parking_question_returns_location_hints_only(self):
        """Parking questions must show location menu hints."""
        composer = AnswerComposer(provider="mock")
        result = composer.compose({"query": "주차장이 어디있어?", "results": []})
        assert result["ok"] is True
        text = result["answer_markdown"]
        assert "- 청사안내" in text
        assert "- 오시는 길" in text
        assert "- 주차안내" in text
        assert result["guard_status"] == "no_results"

    def test_application_question_returns_service_hints(self):
        """Application questions must show service menu hints without procedure claims."""
        composer = AnswerComposer(provider="mock")
        result = composer.compose({"query": "민원서식 어디서 받아?", "results": []})
        assert result["ok"] is True
        text = result["answer_markdown"]
        assert "- 민원" in text
        assert "- 민원서식" in text
        assert "- 신청/접수" in text
        assert "- 자주찾는 서비스" in text
        assert result["guard_status"] == "no_results"

    def test_source_backed_answer_behavior_unchanged(self):
        """Composer still returns source-backed answer with sources."""
        composer = AnswerComposer(provider="mock")
        result = composer.compose(SAMPLE_SEARCH_RESULTS)
        assert result["ok"] is True
        assert result["answer_markdown"]
        assert len(result["sources"]) == 2

    def test_no_source_path_seals_provider_completion(self):
        """No-results path must not call provider complete."""
        provider_calls: list[list[Any]] = []

        class SealingProvider(MockProvider):
            def complete(self, messages, temperature=0.2, max_tokens=1200, timeout=60):
                provider_calls.append([messages, temperature, max_tokens, timeout])
                return super().complete(messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout)

        composer = AnswerComposer(provider=SealingProvider())
        result = composer.compose(EMPTY_SEARCH_RESULTS)
        assert result["ok"] is True
        assert result["provider"] == "none"
        assert provider_calls == []
