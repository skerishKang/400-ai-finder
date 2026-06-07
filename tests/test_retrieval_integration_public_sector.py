"""Integration and regression tests for public-sector volatile questions.

Asserts the behavior of query rewrite candidate generation, offline search integration,
and the source mismatch fallback UX gap based on the Stage 380 audit findings.

Contains both passing contract assertions and expected target behaviors marked with xfail.
No live providers, fetch, network, or API calls are used.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.search.query_rewriter import rewrite_query_candidates
from src.search.keyword_searcher import KeywordSearcher
from src.pipeline.pipeline_runner import PipelineRunner
from src.answer.answer_composer import AnswerComposer

# ------------------------------------------------------------------
# Mock Public-Sector Documents
# ------------------------------------------------------------------

MAYOR_DOC = {
    "id": "mayor-001",
    "title": "열린구청장실",
    "url": "https://bukgu.gwangju.kr/menu.es?mid=a20101010000",
    "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a20101010000",
    "category": "menu",
    "content_type": "page",
    "score": 0.0,
    "text": "열린구청장실 구청장 인사말 구청장 프로필 북구청장 소개",
    "summary": "북구청장 인사말 및 프로필 페이지",
    "metadata": {
        "link_texts": ["열린구청장실", "구청장 인사말", "구청장 프로필"],
        "fetch_status": "fetched",
    },
}

CONTACTS_DOC = {
    "id": "contacts-001",
    "title": "조직도 및 직원검색",
    "url": "https://bukgu.gwangju.kr/menu.es?mid=a10103000000",
    "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a10103000000",
    "category": "menu",
    "content_type": "page",
    "score": 0.0,
    "text": "조직도 직원검색 부서안내 담당업무 부서별 전화번호 및 팩스번호",
    "summary": "구청 조직도 및 직원 업무/전화번호 안내",
    "metadata": {
        "link_texts": ["조직도", "직원검색", "부서안내"],
        "fetch_status": "fetched",
    },
}

LOCATION_DOC = {
    "id": "location-001",
    "title": "찾아오시는길",
    "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
    "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
    "category": "menu",
    "content_type": "page",
    "score": 0.0,
    "text": "청사안내 오시는 길 주차안내 대중교통 이용안내 위치도",
    "summary": "구청 청사 위치 및 주차안내",
    "metadata": {
        "link_texts": ["오시는 길", "청사안내", "주차안내"],
        "fetch_status": "fetched",
    },
}

CIVIL_DOC = {
    "id": "civil-001",
    "title": "민원서식",
    "url": "https://bukgu.gwangju.kr/menu.es?mid=a10101040000",
    "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a10101040000",
    "category": "document",
    "content_type": "page",
    "score": 0.0,
    "text": "민원서식 작성예시 QR코드 민원편의시책 여권민원 제증명 수수료",
    "summary": "민원서식 안내 페이지",
    "metadata": {
        "link_texts": ["민원서식"],
        "fetch_status": "fetched",
    },
}

NOTICE_DOC = {
    "id": "notice-001",
    "title": "고시공고",
    "url": "https://bukgu.gwangju.kr/menu.es?mid=a10401010000",
    "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a10401010000",
    "category": "notice",
    "content_type": "page",
    "score": 0.0,
    "text": "고시공고 입법예고 공지사항 새소식",
    "summary": "고시공고 및 공지사항 페이지",
    "metadata": {
        "link_texts": ["고시공고"],
        "fetch_status": "fetched",
    },
}

JOBS_DOC = {
    "id": "jobs-001",
    "title": "청년 일자리 지원",
    "url": "https://bukgu.gwangju.kr/menu.es?mid=a10204000000",
    "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a10204000000",
    "category": "menu",
    "content_type": "page",
    "score": 0.0,
    "text": "청년 일자리 채용 고용 취업 아르바이트 비즈광주북구",
    "summary": "청년 취업 및 일자리 정보 지원사업 안내",
    "metadata": {
        "link_texts": ["청년 일자리", "채용", "고용"],
        "fetch_status": "fetched",
    },
}

# ------------------------------------------------------------------
# Test Helper
# ------------------------------------------------------------------

def _build_searcher(docs: list[dict], tmp_path: Path) -> KeywordSearcher:
    """Create a KeywordSearcher from in-memory document list."""
    index_path = tmp_path / "test-index.jsonl"
    with open(index_path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    searcher = KeywordSearcher(index_path=str(index_path))
    return searcher

# ------------------------------------------------------------------
# Test Target 1: Query Rewrite Candidate Generation
# ------------------------------------------------------------------

class TestQueryRewriteGeneration:
    """Target 1: Verify rewrite query expansion results and candidate limits."""

    def test_leadership_query_rewrite(self):
        """구청장/기관장 질문이 기존 global rule을 통해 leadership 후보를 생성하는지 확인."""
        result = rewrite_query_candidates("구청장이 누구야?")
        assert len(result.queries) > 0
        assert "구청장" in result.queries
        assert "북구청장" in result.queries
        # Ensure it does not fabricate/hallucinate names or volatile facts
        for q in result.queries:
            assert "문인" not in q
            assert "<기관장명>" not in q

    def test_contacts_query_rewrite_expected_behavior(self):
        """담당자/연락처 질문에 대해 기대하는 target rewrite 후보 생성을 검증."""
        result = rewrite_query_candidates("담당자 연락처 알려줘")
        expected_candidates = {"조직도", "직원검색", "부서안내"}
        assert expected_candidates.issubset(set(result.queries))

    def test_location_query_rewrite_expected_behavior(self):
        """주차/위치/오시는 길 질문에 대해 기대하는 target rewrite 후보 생성을 검증."""
        result = rewrite_query_candidates("주차장이 어디있어?")
        expected_candidates = {"청사안내", "오시는 길", "주차안내"}
        assert expected_candidates.issubset(set(result.queries))

    def test_civil_service_query_rewrite(self):
        """민원/신청/서식 질문이 기존 global rule을 통해 후보를 잘 생성하는지 확인.
        
        Note: Under max_queries=5, '민원서식' (the 6th candidate) is truncated.
        """
        result_truncated = rewrite_query_candidates("민원서식 어디서 받아?", max_queries=5)
        assert "민원" in result_truncated.queries
        assert "민원서식" not in result_truncated.queries

        result_full = rewrite_query_candidates("민원서식 어디서 받아?", max_queries=6)
        assert "민원" in result_full.queries
        assert "민원서식" in result_full.queries

    def test_announcement_truncation_current_limit(self):
        """'채용공고' 검색 시 max_queries=5 제약으로 인해 뒤쪽 '고시공고' 계열 후보가 잘리는 현재 한계 확인."""
        result = rewrite_query_candidates("채용공고 어디서 봐?", max_queries=5)
        # Matches Jobs (청년, 일자리, 채용...) & Notice (고시, 공고, 공지...)
        # Combined order: ['채용공고 어디서 봐', '청년', '일자리', '청년 일자리', '채용', '고용', '경제', '고시공고', '공지사항', '공고', '새소식']
        # Sliced to 5: ['채용공고 어디서 봐', '청년', '일자리', '청년 일자리', '채용']
        assert "고시공고" not in result.queries
        assert "공지사항" not in result.queries

    def test_announcement_truncation_prevention_with_higher_limit(self):
        """max_queries를 12로 크게 줄 경우, 잘렸던 공고/공지사항 계열 후보가 생성되는지 검증."""
        result = rewrite_query_candidates("채용공고 어디서 봐?", max_queries=12)
        assert "고시공고" in result.queries
        assert "공지사항" in result.queries


# ------------------------------------------------------------------
# Test Target 2: Offline Retrieval/Search Integration
# ------------------------------------------------------------------

class TestOfflineRetrievalIntegration:
    """Target 2: Verify search integration against a mock document index."""

    def test_search_mayor_retrieves_correct_document(self, tmp_path):
        """구청장 질문이 query rewriter 후보를 거쳐 '열린구청장실' 문서를 정상 검색하는지 확인."""
        docs = [MAYOR_DOC, CIVIL_DOC, NOTICE_DOC]
        searcher = _build_searcher(docs, tmp_path)
        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock", top_k=5)

        # "구청장이 누구야?" expands to leadership candidates matching MAYOR_DOC
        candidates = list(rewrite_query_candidates("구청장이 누구야?", max_queries=5).queries)
        results = runner._search_for_candidates(searcher, candidates)

        assert len(results) > 0
        assert results[0]["id"] == "mayor-001"
        assert "열린구청장" in results[0]["title"]

    def test_search_contacts_expected_success(self, tmp_path):
        """Contacts rewrite rule이 주어졌을 때, '조직도' 문서 검색에 성공하는지 검증."""
        docs = [CONTACTS_DOC, CIVIL_DOC]
        searcher = _build_searcher(docs, tmp_path)
        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock", top_k=5)

        # If contacts/staff rule existed, it would generate "직원검색" or "조직도" candidates
        candidates = list(rewrite_query_candidates("세무과 연락처 알려줘", max_queries=5).queries)
        # Assert target behavior (should contain "직원검색" or "조직도")
        assert any(k in candidates for k in ["조직도", "직원검색", "부서안내"])

        results = runner._search_for_candidates(searcher, candidates)
        assert any(r["id"] == "contacts-001" for r in results)

    def test_search_location_expected_success(self, tmp_path):
        """Location rewrite/synonym rule이 주어졌을 때, '찾아오시는길' 문서 검색에 성공하는지 검증."""
        docs = [LOCATION_DOC, CIVIL_DOC]
        searcher = _build_searcher(docs, tmp_path)
        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock", top_k=5)

        candidates = list(rewrite_query_candidates("주차장이 어디있어?", max_queries=5).queries)
        # Assert target behavior (should contain location menu search terms)
        assert any(k in candidates for k in ["오시는 길", "청사안내", "주차안내"])

        results = runner._search_for_candidates(searcher, candidates)
        assert any(r["id"] == "location-001" for r in results)

    def test_search_truncation_loses_notice_document(self, tmp_path):
        """max_queries=5 제약으로 '고시공고' 후보가 잘려, NOTICE_DOC을 검색하지 못하는 한계 재현."""
        docs = [JOBS_DOC, NOTICE_DOC]
        searcher = _build_searcher(docs, tmp_path)
        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock", top_k=5)

        candidates = list(rewrite_query_candidates("채용공고 어디서 봐?", max_queries=5).queries)
        results = runner._search_for_candidates(searcher, candidates)

        # Retrieves JOBS_DOC because '청년', '일자리', '채용' are in candidates
        assert any(r["id"] == "jobs-001" for r in results)
        # Fails to retrieve NOTICE_DOC because notice-related candidates ('고시공고', '공지사항') were truncated
        assert not any(r["id"] == "notice-001" for r in results)

    def test_search_no_truncation_retrieves_notice_document(self, tmp_path):
        """max_queries=12로 제약을 완화할 경우, '고시공고' 후보를 통해 NOTICE_DOC을 정상 검색하는지 검증."""
        docs = [JOBS_DOC, NOTICE_DOC]
        searcher = _build_searcher(docs, tmp_path)
        runner = PipelineRunner(output_dir=str(tmp_path), provider="mock", top_k=5)

        candidates = list(rewrite_query_candidates("채용공고 어디서 봐?", max_queries=12).queries)
        results = runner._search_for_candidates(searcher, candidates)

        # Successfully retrieves both documents
        assert any(r["id"] == "jobs-001" for r in results)
        assert any(r["id"] == "notice-001" for r in results)


# ------------------------------------------------------------------
# Test Target 3: Source Mismatch Fallback UX Gap
# ------------------------------------------------------------------

class TestSourceMismatchFallbackUXGap:
    """Target 3: Verify the UX discrepancy between search failure (no results) and mismatch."""

    def test_mismatch_fallback_degrades_to_generic_no_results(self):
        """검색 결과가 존재하지만 mismatch된 경우, generic no-results fallback이 사용되는 현재 상태 검증.

        Stage 378의 카테고리별 guidance menu hint가 노출되지 않는 UX gap을 확인한다.
        """
        composer = AnswerComposer(provider="mock")

        # Mock search output containing query and unrelated results (mismatch)
        search_data = {
            "query": "구청장이 누구야?",
            "top_k": 5,
            "results": [
                {
                    "id": "unrelated-001",
                    "title": "건설 도로 공사 안내",
                    "url": "https://bukgu.gwangju.kr/menu.es?mid=a10500000000",
                    "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a10500000000",
                    "category": "notice",
                    "score": 10.0,
                    "matched_terms": ["안내"],
                    "matched_fields": ["title"],
                    "snippet": "도로 정비 공사에 따른 통행 제한 안내문",
                }
            ],
            "query_rewrite": {
                "queries": ["구청장이 누구야", "구청장", "북구청장"],
            }
        }

        response = composer.compose(search_data, max_sources=5)

        # Confirm guard blocks it as mismatch
        assert response.get("guard_status") == "no_results"
        assert "mismatch" in response.get("guard_reason", "").lower()

        # Confirms the UX gap: uses _no_results_answer() instead of _build_no_source_guidance()
        # This generic response lacks the "구청장실", "기관장 소개" specialized navigation hints.
        markdown = response.get("answer_markdown", "")
        assert "관련 자료를 찾지 못했습니다." in markdown
        assert "구청장실" not in markdown
        assert "기관장 소개" not in markdown

    @pytest.mark.xfail(reason="Stage 380 audit: mismatched sources fallback does not display specialized category guidance menu hints")
    def test_mismatch_fallback_retains_specialized_guidance(self):
        """Source mismatch fallback 시에도 카테고리별 specialized guidance menu hint가 보존되는 기대 동작 (xfail)."""
        composer = AnswerComposer(provider="mock")

        search_data = {
            "query": "구청장이 누구야?",
            "top_k": 5,
            "results": [
                {
                    "id": "unrelated-001",
                    "title": "건설 도로 공사 안내",
                    "url": "https://bukgu.gwangju.kr/menu.es?mid=a10500000000",
                    "canonical_url": "https://bukgu.gwangju.kr/menu.es?mid=a10500000000",
                    "category": "notice",
                    "score": 10.0,
                    "matched_terms": ["안내"],
                    "matched_fields": ["title"],
                    "snippet": "도로 정비 공사에 따른 통행 제한 안내문",
                }
            ],
            "query_rewrite": {
                "queries": ["구청장이 누구야", "구청장", "북구청장"],
            }
        }

        response = composer.compose(search_data, max_sources=5)

        # Assert target behavior: should contain category-specific guidance hints
        markdown = response.get("answer_markdown", "")
        assert any(hint in markdown for hint in ["구청장실", "기관장 소개", "인사말"])
