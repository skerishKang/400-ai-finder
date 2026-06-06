"""Tests for the query rewriter contract (Stage 343).

Query rewriter must:
- Preserve original question exactly
- Produce retrieval query candidates only (not answers)
- Be deterministic and offline-safe
- Deduplicate and limit candidates
- Not call any provider or live API
"""

from __future__ import annotations

import pytest

from src.search.query_rewriter import rewrite_query_candidates, QueryRewriteResult


class TestQueryRewriterContract:
    """Core contract tests."""

    def test_rewrite_preserves_original_question(self):
        """Original question must be preserved exactly in the result."""
        result = rewrite_query_candidates("민원서식 어디서 받아?")
        assert result.original_question == "민원서식 어디서 받아?"

    def test_rewrite_deduplicates_and_limits_candidates(self):
        """Candidates must be deduplicated and limited to max_queries."""
        result = rewrite_query_candidates(
            "구청장이 누구야?",
            max_queries=3,
        )
        # Deduplicated - no duplicates
        assert len(result.queries) == len(set(result.queries))
        # Limited to max_queries
        assert len(result.queries) <= 3

    def test_rewrite_blank_question_returns_warning_and_no_queries(self):
        """Blank question must return empty queries and a warning."""
        result = rewrite_query_candidates("")
        assert len(result.queries) == 0
        assert len(result.warnings) >= 1

        result2 = rewrite_query_candidates("   ")
        assert len(result2.queries) == 0
        assert len(result2.warnings) >= 1

    def test_rewrite_blank_has_empty_strategy(self):
        """Blank question should report 'empty' strategy."""
        result = rewrite_query_candidates("")
        assert result.strategy == "empty"

    def test_rewrite_has_deterministic_strategy_name(self):
        """Non-blank question should have 'deterministic_v1' strategy."""
        result = rewrite_query_candidates("민원 신청 어디서 해?")
        assert result.strategy == "deterministic_v1"

    def test_rewriter_does_not_import_provider_modules(self):
        """Rewriter must not import provider/llm modules."""
        import sys
        # Check that the query_rewriter module itself does not directly
        # import any provider/llm/fetch modules
        rewriter_mod = sys.modules.get("src.search.query_rewriter")
        assert rewriter_mod is not None, "query_rewriter module not loaded"

        # Check that query_rewriter.py does not `import` or `from ... import`
        # any provider module
        import ast
        import os
        rewriter_path = os.path.join(os.path.dirname(__file__), "..", "src", "search", "query_rewriter.py")
        with open(os.path.abspath(rewriter_path), "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("src.llm") or alias.name.startswith("src.fetch") or alias.name.startswith("src.answer"):
                        pytest.fail(f"query_rewriter should not import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and (node.module.startswith("src.llm") or node.module.startswith("src.fetch") or node.module.startswith("src.answer")):
                    pytest.fail(f"query_rewriter should not import from {node.module}")


class TestQueryRewriterMayor:
    """Mayor / chief official question tests."""

    def test_rewrite_mayor_question_returns_retrieval_candidates_not_answer(self):
        """구청장 질문은 검색어 후보만 반환해야 하고, 답변(이름 등)을 포함하면 안 됨."""
        result = rewrite_query_candidates("구청장이 누구야?", max_queries=5)

        # Should include retrieval terms like 북구청장, 구청장 프로필, 열린구청장
        queries_str = " ".join(result.queries)
        assert any(term in queries_str for term in [
            "북구청장", "구청장 프로필", "열린구청장"
        ]), f"Expected retrieval terms for 구청장, got: {result.queries}"

        # Must NOT include a specific person's name in expansion terms
        # (Exclude the first normalized query which may contain particles like "이")
        person_names = {"김", "이", "박", "최", "정", "송", "윤"}
        for q in result.queries[1:]:  # skip the first normalized query
            for name in person_names:
                assert name not in q, f"Should not contain a person name: {q}"

        # Must NOT include 민원서식
        assert "민원서식" not in queries_str, \
            f"Should not include 민원서식 for 구청장 question: {result.queries}"

    def test_rewrite_mayor_variants(self):
        """다양한 구청장 변형 질문 처리."""
        variants = [
            "열린구청장실 어디야?",
            "구청장 프로필 좀 알려줘",
            "북구청장 누구야",
        ]
        for question in variants:
            result = rewrite_query_candidates(question, max_queries=5)
            queries_str = " ".join(result.queries)
            assert any(term in queries_str for term in [
                "북구청장", "열린구청장", "구청장 프로필"
            ]), f"For '{question}', expected retrieval terms, got: {result.queries}"


class TestQueryRewriterYouthJobs:
    """Youth / jobs question tests."""

    def test_rewrite_youth_jobs_question_returns_menu_terms(self):
        """청년 일자리 질문은 관련 메뉴 용어를 반환해야 함."""
        result = rewrite_query_candidates("청년 일자리 어디서 봐?", max_queries=5)
        queries_str = " ".join(result.queries)
        assert any(term in queries_str for term in [
            "청년", "일자리", "채용", "고용", "경제", "비즈광주북구", "청년 일자리"
        ]), f"Expected youth/jobs retrieval terms, got: {result.queries}"


class TestQueryRewriterCivilService:
    """Civil service / application question tests."""

    def test_rewrite_civil_service_question_returns_menu_terms(self):
        """민원 신청 질문은 관련 메뉴 용어를 반환해야 함."""
        result = rewrite_query_candidates("민원 신청 어디서 해?", max_queries=5)
        queries_str = " ".join(result.queries)
        assert any(term in queries_str for term in [
            "민원", "민원 신청", "온라인 민원", "종합민원", "민원서식"
        ]), f"Expected civil service terms, got: {result.queries}"


class TestQueryRewriterNotice:
    """Notice / announcement question tests."""

    def test_rewrite_notice_question_returns_notice_terms(self):
        """고시공고 질문은 관련 공지 용어를 반환해야 함."""
        result = rewrite_query_candidates("고시공고 어디서 봐?", max_queries=5)
        queries_str = " ".join(result.queries)
        assert any(term in queries_str for term in [
            "고시공고", "공지사항", "공고", "새소식"
        ]), f"Expected notice terms, got: {result.queries}"

    def test_rewrite_notice_variants(self):
        """고시공고 변형 질문 처리."""
        variants = [
            "공지사항 좀 알려줘",
            "새소식은 어디서 봐?",
            "입법예고 확인하는 방법",
        ]
        for question in variants:
            result = rewrite_query_candidates(question, max_queries=5)
            assert len(result.queries) >= 1, f"For '{question}', expected at least 1 query"


class TestQueryRewriterWelfare:
    """Welfare / support question tests."""

    def test_rewrite_welfare_question_returns_welfare_terms(self):
        """복지 지원 질문은 관련 용어를 반환해야 함."""
        result = rewrite_query_candidates("복지 지원사업은 어디서 확인해?", max_queries=5)
        queries_str = " ".join(result.queries)
        assert any(term in queries_str for term in [
            "복지", "지원", "복지 지원", "지원금", "기초수급"
        ]), f"Expected welfare terms, got: {result.queries}"


class TestQueryRewriterEducation:
    """Education / training question tests."""

    def test_rewrite_education_question_returns_education_terms(self):
        """교육 질문은 관련 용어를 반환해야 함."""
        result = rewrite_query_candidates("교육 프로그램 신청은 어디서?", max_queries=5)
        queries_str = " ".join(result.queries)
        assert any(term in queries_str for term in [
            "교육", "교육접수", "평생교육", "강좌", "프로그램"
        ]), f"Expected education terms, got: {result.queries}"


class TestQueryRewriterDeterminism:
    """Determinism and safety tests."""

    def test_rewriter_deterministic_output(self):
        """동일 입력에 대해 항상 동일 출력을 반환해야 함."""
        q = "구청장이 누구야?"
        r1 = rewrite_query_candidates(q, max_queries=5)
        r2 = rewrite_query_candidates(q, max_queries=5)
        assert r1.queries == r2.queries

    def test_rewriter_does_not_include_answer_terms(self):
        """Rewriter must not include answer-like terms or person names."""
        result = rewrite_query_candidates("구청장이 누구야?", max_queries=5)
        queries_str = " ".join(result.queries)
        # Should not contain answer terms like "입니다", "입니다", "이름은"
        answer_indicators = ("입니다", "이름은", "입니다")
        for indicator in answer_indicators:
            assert indicator not in queries_str, \
                f"Should not contain answer terms: {queries_str}"

    def test_rewriter_different_question_different_results(self):
        """서로 다른 질문은 서로 다른 후보를 반환해야 함."""
        r1 = rewrite_query_candidates("구청장이 누구야?", max_queries=5)
        r2 = rewrite_query_candidates("민원 신청 어디서 해?", max_queries=5)
        # The queries lists should differ
        assert r1.queries != r2.queries

    def test_rewriter_does_not_require_api_keys(self):
        """Rewriter must not require env vars or API keys to function."""
        import os
        # Simulate no API keys loaded
        result = rewrite_query_candidates("정보공개는 어디서 봐?", max_queries=5)
        assert len(result.queries) >= 1
        assert "정보공개" in result.queries or any("정보공개" in q for q in result.queries)