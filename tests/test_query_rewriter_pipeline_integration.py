"""Tests for Stage 344a: query rewriter integration into pipeline search.

Verifies that:
- Query rewrite candidates are used for retrieval
- Original question remains preserved for answer composition
- Results across rewritten queries are deduplicated
- Existing keyword search behavior is preserved
- No live provider/LLM/API calls are made
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.search.query_rewriter import rewrite_query_candidates
from src.search.keyword_searcher import KeywordSearcher


# ------------------------------------------------------------------
# Fixture: in-memory document index with known terms
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

MINWON_DOC = {
    "id": "minwon-001",
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
    "text": "고시공고 입법예고 공지사항",
    "summary": "고시공고 공지사항 페이지",
    "metadata": {
        "link_texts": ["고시공고"],
        "fetch_status": "fetched",
    },
}


# ------------------------------------------------------------------
# Helper: build a KeywordSearcher from in-memory docs
# ------------------------------------------------------------------

def _build_searcher(docs: list[dict], tmp_path: Path) -> KeywordSearcher:
    """Create a KeywordSearcher from in-memory document list."""
    index_path = tmp_path / "test-index.jsonl"
    with open(index_path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    searcher = KeywordSearcher(index_path=str(index_path))
    assert len(searcher.docs) == len(docs)
    return searcher


class TestQueryRewriterPipelineIntegration:
    """Integration tests for query rewriter + pipeline search."""

    def test_pipeline_search_uses_query_rewriter_candidates_for_mayor_question(
        self, tmp_path
    ):
        """구청장 질문이 rewrite candidate를 통해 mayor source를 검색할 수 있어야 함."""
        from src.pipeline.pipeline_runner import PipelineRunner

        docs = [MAYOR_DOC, MINWON_DOC, NOTICE_DOC]
        index_path = tmp_path / "enriched-index.jsonl"
        with open(index_path, "w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

        runner = PipelineRunner(
            output_dir=str(tmp_path), provider="mock", top_k=5
        )
        result = runner._step_search("구청장이 누구야?", str(index_path))

        assert result["ok"] is True
        search_output = json.load(open(result["output"]))
        all_results = search_output.get("results", [])
        all_urls = [r.get("url", "") for r in all_results]

        # Without rewrite, "구청장이 누구야?" would not match "열린구청장실"
        # With rewrite, should find it via "북구청장", "구청장 프로필", "열린구청장", etc.
        assert any(
            "a20101010000" in url for url in all_urls
        ), f"Expected mayor URL in results, got URLs: {all_urls}"

        # Should NOT return only 민원서식 as the top result for mayor question
        # It may include minwon if scored, but should also include mayor
        assert any(
            "열린구청장" in r.get("title", "") for r in all_results
        ), f"Expected mayor-related title, got: {[r.get('title') for r in all_results]}"

    def test_pipeline_search_preserves_original_question_for_answer_composition(
        self, tmp_path
    ):
        """원본 질문은 query_rewrite metadata에 보존되어야 함."""
        from src.pipeline.pipeline_runner import PipelineRunner

        docs = [MAYOR_DOC, MINWON_DOC, NOTICE_DOC]
        index_path = tmp_path / "enriched-index.jsonl"
        with open(index_path, "w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

        runner = PipelineRunner(
            output_dir=str(tmp_path), provider="mock", top_k=5
        )
        result = runner._step_search("구청장이 누구야?", str(index_path))

        assert result["ok"] is True
        search_output = json.load(open(result["output"]))

        # Original question preserved in top-level query field
        assert search_output["query"] == "구청장이 누구야?"

        # Query rewrite metadata contains original question
        qr = search_output.get("query_rewrite", {})
        assert qr.get("original_question") == "구청장이 누구야?"
        assert qr.get("strategy") == "deterministic_v1"

    def test_pipeline_search_deduplicates_results_across_rewritten_queries(
        self, tmp_path
    ):
        """여러 rewrite query candidate가 같은 URL을 반환하면 중복 제거되어야 함."""
        from src.pipeline.pipeline_runner import PipelineRunner

        # Create a searcher with docs where multiple query candidates match the same URL
        docs = [MAYOR_DOC, MINWON_DOC]
        index_path = tmp_path / "enriched-index.jsonl"
        with open(index_path, "w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

        # "북구청장" and "구청장 프로필" both match MAYOR_DOC
        # Deduplication should keep only one entry per canonical_url
        mock_candidates = ["북구청장", "구청장 프로필", "열린구청장"]

        runner = PipelineRunner(
            output_dir=str(tmp_path), provider="mock", top_k=5
        )
        searcher = KeywordSearcher(index_path=str(index_path))
        results = runner._search_for_candidates(searcher, mock_candidates)

        # Find the mayor URL
        mayor_url = "https://bukgu.gwangju.kr/menu.es?mid=a20101010000"
        mayor_results = [r for r in results if r.get("canonical_url") == mayor_url or r.get("url") == mayor_url]
        assert len(mayor_results) == 1, (
            f"Expected exactly 1 result for mayor URL (deduplicated), "
            f"got {len(mayor_results)}: {mayor_results}"
        )

    def test_pipeline_search_preserves_existing_keyword_search_behavior(
        self, tmp_path
    ):
        """기존 키워드 검색(민원서식, 고시공고)은 여전히 정상 동작해야 함."""
        from src.pipeline.pipeline_runner import PipelineRunner

        docs = [MAYOR_DOC, MINWON_DOC, NOTICE_DOC]
        index_path = tmp_path / "enriched-index.jsonl"
        with open(index_path, "w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

        runner = PipelineRunner(
            output_dir=str(tmp_path), provider="mock", top_k=5
        )

        # Test 민원서식
        result_minwon = runner._step_search("민원서식 어디서 받아?", str(index_path))
        assert result_minwon["ok"] is True
        minwon_output = json.load(open(result_minwon["output"]))
        minwon_urls = [r.get("url", "") for r in minwon_output.get("results", [])]
        assert any(
            "a10101040000" in url for url in minwon_urls
        ), f"Expected minwon URL, got: {minwon_urls}"

        # Test 고시공고
        result_notice = runner._step_search("고시공고 어디서 봐?", str(index_path))
        assert result_notice["ok"] is True
        notice_output = json.load(open(result_notice["output"]))
        notice_urls = [r.get("url", "") for r in notice_output.get("results", [])]
        assert any(
            "a10401010000" in url for url in notice_urls
        ), f"Expected notice URL, got: {notice_urls}"

    def test_pipeline_search_does_not_import_or_call_live_provider(self):
        """Integration이 live provider/LLM/fetch modules을 import하지 않아야 함."""
        import ast

        pipeline_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "pipeline", "pipeline_runner.py"
        )
        with open(os.path.abspath(pipeline_path), "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)

        banned_prefixes = (
            "src.llm", "src.fetch", "firecrawl",
            "requests", "httpx", "urllib3",
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(banned_prefixes):
                        pytest.fail(
                            f"pipeline_runner should not import live module: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith(banned_prefixes):
                    pytest.fail(
                        f"pipeline_runner should not import from live module: {node.module}"
                    )

        # Verify no rewrite_query_candidates import removal
        assert "rewrite_query_candidates" in source, (
            "pipeline_runner must import rewrite_query_candidates"
        )


class TestQueryRewriteMetadata:
    """Query rewrite metadata in search output tests."""

    def test_search_output_contains_query_rewrite_metadata(self, tmp_path):
        """검색 결과에 query_rewrite metadata가 포함되어야 함."""
        from src.pipeline.pipeline_runner import PipelineRunner

        docs = [MAYOR_DOC, MINWON_DOC]
        index_path = tmp_path / "enriched-index.jsonl"
        with open(index_path, "w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

        runner = PipelineRunner(
            output_dir=str(tmp_path), provider="mock", top_k=5
        )
        result = runner._step_search("구청장이 누구야?", str(index_path))

        assert result["ok"] is True
        search_output = json.load(open(result["output"]))
        qr = search_output.get("query_rewrite", {})

        assert qr.get("strategy") == "deterministic_v1"
        assert qr.get("original_question") == "구청장이 누구야?"
        assert isinstance(qr.get("queries"), list)
        assert len(qr["queries"]) >= 1
        assert isinstance(qr.get("warnings"), list)

    def test_query_rewrite_metadata_not_added_for_search_failure(self, tmp_path):
        """검색 실패 시에도 query_rewrite 없이 정상 오류 처리를 확인."""
        from src.pipeline.pipeline_runner import PipelineRunner

        runner = PipelineRunner(
            output_dir=str(tmp_path), provider="mock", top_k=5
        )
        result = runner._step_search("test query", "/nonexistent/path.json")

        assert result["ok"] is False
        assert "error" in result


class TestQueryRewriterNoProvider:
    """Ensure query rewriter integration doesn't pull in provider modules."""

    def test_query_rewriter_integration_no_provider_modules(self):
        """rewrite_query_candidates는 독립적으로 import되어야 함."""
        import sys

        # Fresh check: query_rewriter should not have any provider deps
        rewriter_mod = sys.modules.get("src.search.query_rewriter")
        assert rewriter_mod is not None

        # Check source for prohibited imports
        import ast

        rewriter_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "search", "query_rewriter.py"
        )
        with open(os.path.abspath(rewriter_path), "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(m in alias.name for m in ["src.llm", "src.fetch", "src.answer"]):
                        pytest.fail(
                            f"query_rewriter should not import: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and any(m in node.module for m in ["src.llm", "src.fetch", "src.answer"]):
                    pytest.fail(
                        f"query_rewriter should not import from: {node.module}"
                    )