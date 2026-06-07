"""Tests for the source mismatch / weak retrieval guard (Stage 344b)."""

from __future__ import annotations

import json
import os
import pytest
from pathlib import Path

from src.search.source_match_guard import assess_source_match, SourceMatchAssessment
from src.answer.answer_composer import AnswerComposer
from src.pipeline.pipeline_runner import PipelineRunner


# ------------------------------------------------------------------
# Test Cases for assess_source_match
# ------------------------------------------------------------------

def test_source_match_guard_passes_relevant_mayor_source():
    """Question: 구청장이 누구야?
    Source: 북구청장, 구청장 프로필, 열린구청장
    Expected: PASS
    """
    sources = [
        {
            "id": "mayor-01",
            "title": "열린구청장실",
            "snippet": "북구청장 프로필 및 약력 소개",
            "category": "menu",
            "matched_terms": ["구청장"],
        }
    ]
    assessment = assess_source_match("구청장이 누구야?", sources)
    assert assessment.status == "pass"


def test_source_match_guard_blocks_mayor_question_with_civil_form_source():
    """Question: 구청장이 누구야?
    Source: 민원서식, 종합민원, 민원서식 작성예시
    Expected: NO_RESULTS or blocked/downgraded
    """
    sources = [
        {
            "id": "civil-01",
            "title": "민원서식",
            "snippet": "종합민원 및 민원서식 작성예시 안내",
            "category": "document",
            "matched_terms": ["민원서식"],
        }
    ]
    assessment = assess_source_match("구청장이 누구야?", sources)
    assert assessment.status == "no_results"


def test_source_match_guard_passes_civil_service_question_with_civil_sources():
    """Question: 민원 신청 어디서 해?
    Source: 민원, 온라인 민원, 종합민원, 민원서식
    Expected: PASS
    """
    sources = [
        {
            "id": "civil-01",
            "title": "종합민원실",
            "snippet": "온라인 민원 신청 및 민원서식 발급",
            "category": "civil",
            "matched_terms": ["민원", "신청"],
        }
    ]
    assessment = assess_source_match("민원 신청 어디서 해?", sources)
    assert assessment.status == "pass"


def test_source_match_guard_blocks_youth_jobs_question_with_unrelated_information_disclosure_source():
    """Question: 청년 일자리 어디서 봐?
    Source: 정보공개, 사전정보공표
    Expected: NO_RESULTS or WARN
    """
    sources = [
        {
            "id": "info-01",
            "title": "정보공개",
            "snippet": "사전정보공표 및 행정정보공개 청구 안내",
            "category": "information",
            "matched_terms": ["정보공개"],
        }
    ]
    assessment = assess_source_match("청년 일자리 어디서 봐?", sources)
    # The guard can return warn or no_results because it's completely unrelated
    assert assessment.status in ("no_results", "warn")


# ------------------------------------------------------------------
# Pipeline Integration Tests
# ------------------------------------------------------------------

def test_pipeline_does_not_compose_confident_answer_from_mismatched_source(tmp_path):
    """Assert that unrelated-only search results do not compose a confident answer."""
    search_data = {
        "query": "구청장이 누구야?",
        "results": [
            {
                "id": "civil-001",
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10101040000",
                "category": "document",
                "matched_terms": ["민원서식"],
                "snippet": "민원서식 작성예시 안내 페이지",
            }
        ]
    }

    composer = AnswerComposer(provider="mock")
    response = composer.compose(search_data)
    
    # It should not produce a confident answer, but return no-results style response
    assert response["ok"] is True
    assert "답변 근거 자료를 찾지 못했습니다" in response["answer_markdown"]
    assert len(response["sources"]) == 0  # no-results clears the sources list or returns empty sources
    assert any("Topic mismatch" in w for w in response["warnings"])


def test_pipeline_preserves_valid_rewrite_search_results(tmp_path):
    """Build a search result where rewrite candidates produce both relevant and irrelevant results.
    Assert that only relevant sources are composed/passed, or at least they pass the guard.
    """
    search_data = {
        "query": "구청장이 누구야?",
        "query_rewrite": {
            "queries": ["구청장", "민원서식"],
        },
        "results": [
            {
                "id": "mayor-001",
                "title": "열린구청장실",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a20101010000",
                "category": "menu",
                "matched_terms": ["구청장"],
                "snippet": "구청장 프로필 및 열린구청장 소개",
            },
            {
                "id": "civil-001",
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10101040000",
                "category": "document",
                "matched_terms": ["민원서식"],
                "snippet": "민원서식 작성예시 안내 페이지",
            }
        ]
    }

    composer = AnswerComposer(provider="mock")
    response = composer.compose(search_data)
    
    # Since there is a valid relevant source (열린구청장실), the guard should PASS
    assert response["ok"] is True
    assert "관련 정보를 찾지 못했습니다" not in response["answer_markdown"]
    assert len(response["sources"]) > 0
    assert response["sources"][0]["id"] == "mayor-001"


# ------------------------------------------------------------------
# Pure Offline Tests
# ------------------------------------------------------------------

def test_guard_is_offline_and_imports_no_provider_modules():
    """Verify that source_match_guard.py is pure and imports no network/LLM modules."""
    import sys
    
    # Ensure source_match_guard is loaded
    import src.search.source_match_guard
    
    # Check its imports using AST
    import ast
    
    guard_path = Path(__file__).parent.parent / "src" / "search" / "source_match_guard.py"
    with open(guard_path, "r", encoding="utf-8") as f:
        source = f.read()
    
    tree = ast.parse(source)
    banned_prefixes = ("src.llm", "src.fetch", "firecrawl", "requests", "httpx", "urllib3")
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(banned_prefixes):
                    pytest.fail(f"source_match_guard should not import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(banned_prefixes):
                pytest.fail(f"source_match_guard should not import from: {node.module}")
