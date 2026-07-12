"""Tests for StubProvider — simulated grounded answer provider.

All tests run without API keys.
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.llm import StubProvider, get_provider, list_providers
from src.answer.answer_composer import AnswerComposer

# Sample data matching the existing test_answer_composer.py
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
            "snippet": "신청서 양식 다운로드 페이지입니다.",
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
            "snippet": "중소기업 지원사업 신청 방법과 제출서류를 안내합니다.",
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
# StubProvider unit tests
# ======================================================================

class TestStubProvider:
    def test_provider_name(self):
        p = StubProvider()
        assert p.provider_name == "stub"

    def test_model_name(self):
        p = StubProvider()
        assert p.model_name == "stub"

    def test_complete_with_sources(self):
        """StubProvider returns a grounded answer with sources."""
        p = StubProvider()
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": (
                "## 사용자 질문\n\n"
                "신청서 어디서 받아?\n\n"
                "## Source Context\n\n"
                "[Source 1]\n"
                "title: 신청서 양식\n"
                "url: https://example.com/files/form.pdf\n"
                "category: document\n"
                "content_type: attachment\n"
                "score: 15.0\n"
                "matched_terms: 신청서\n"
                "matched_fields: title\n"
                "fetch_status: skipped\n"
                "source_types: attachment\n"
                "description: \n"
                "snippet: 신청서 양식 다운로드 페이지입니다.\n\n"
                "[Source 2]\n"
                "title: 지원사업 신청 안내\n"
                "url: https://example.com/apply\n"
                "category: apply\n"
                "content_type: page\n"
                "score: 5.0\n"
                "matched_terms: 신청서, 제출서류\n"
                "matched_fields: text\n"
                "fetch_status: fetched\n"
                "source_types: navigation, sitemap\n"
                "description: 지원사업 신청 안내\n"
                "snippet: 중소기업 지원사업 신청 방법과 제출서류를 안내합니다.\n\n"
                "위 Source Context의 정보만 사용하여 답변을 작성하라."
            )},
        ]
        result = p.complete(messages)
        assert result.ok is True
        assert result.provider == "stub"
        assert result.model == "stub"
        assert "신청서" in result.content
        assert "https://example.com/files/form.pdf" in result.content

    def test_complete_no_sources(self):
        """StubProvider returns 'not found' when no sources."""
        p = StubProvider()
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": (
                "## 사용자 질문\n\n"
                "없는 문서 찾기\n\n"
                "## Source Context\n\n"
                "(no sources)\n\n"
                "위 Source Context의 정보만 사용하여 답변을 작성하라."
            )},
        ]
        result = p.complete(messages)
        assert result.ok is True
        assert "찾지 못했습니다" in result.content

    def test_get_via_factory(self):
        """StubProvider can be obtained via get_provider factory."""
        p = get_provider("stub")
        assert p.provider_name == "stub"
        result = p.complete([{"role": "user", "content": "test"}])
        assert result.ok is True

    def test_list_providers_includes_stub(self):
        """list_providers includes stub."""
        providers = list_providers()
        names = [p["name"] for p in providers]
        assert "stub" in names

    def test_fail_on_trigger(self):
        """StubProvider fail_on triggers provider error."""
        p = StubProvider(fail_on="오류유발")
        messages = [
            {"role": "user", "content": (
                "## 사용자 질문\n\n"
                "test\n\n"
                "## Source Context\n\n"
                "[Source 1]\n"
                "title: 오류유발 문서\n"
                "url: https://example.com/error\n"
                "category: document\n"
                "content_type: page\n"
                "score: 1.0\n"
                "matched_terms: \n"
                "matched_fields: \n"
                "fetch_status: \n"
                "source_types: \n"
                "description: \n"
                "snippet: 오류 테스트 문서입니다.\n\n"
            )},
        ]
        result = p.complete(messages)
        assert result.ok is False


# ======================================================================
# AnswerComposer + StubProvider integration tests
# ======================================================================

class TestComposeWithStub:
    def test_compose_returns_answer_with_sources(self):
        """AnswerComposer with stub returns grounded answer referencing sources."""
        composer = AnswerComposer(provider=get_provider("stub"))
        result = composer.compose(SAMPLE_SEARCH_RESULTS)
        assert result["ok"] is True
        assert result["answer_markdown"]
        assert "신청서" in result["answer_markdown"]
        assert result["provider"] == "stub"
        assert result["model"] == "stub"
        # Sources preserved
        assert len(result["sources"]) == 2

    def test_compose_empty_results(self):
        """Empty search results returns 'not found' with stub."""
        composer = AnswerComposer(provider=get_provider("stub"))
        result = composer.compose(EMPTY_SEARCH_RESULTS)
        assert result["ok"] is True
        assert "찾지 못했습니다" in result["answer_markdown"]
        assert result["sources"] == []

    def test_compose_with_mock_still_works(self):
        """Mock provider still works alongside stub."""
        composer = AnswerComposer(provider="mock")
        result = composer.compose(SAMPLE_SEARCH_RESULTS)
        assert result["ok"] is True
        assert result["provider"] == "mock"

    def test_provider_info_in_result(self):
        """Result contains provider and model info."""
        composer = AnswerComposer(provider=get_provider("stub"))
        result = composer.compose(SAMPLE_SEARCH_RESULTS)
        assert "provider" in result
        assert "model" in result
        assert result["provider"] == "stub"
        assert result["model"] == "stub"

    def test_no_api_key_required(self):
        """No API key needed for stub — tests pass without env vars."""
        import os
        # Ensure no API key is set
        for key in ["OPENAI_API_KEY", "AI_FINDER_LLM_API_KEY",
                     "OPENGATEWAY_API_KEY", "KILOCODE_API_KEY"]:
            os.environ.pop(key, None)
        composer = AnswerComposer(provider=get_provider("stub"))
        result = composer.compose(SAMPLE_SEARCH_RESULTS)
        assert result["ok"] is True
        assert "신청서" in result["answer_markdown"]
