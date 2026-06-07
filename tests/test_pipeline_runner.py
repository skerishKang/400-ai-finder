"""Tests for PipelineRunner — end-to-end pipeline orchestration.

All tests use fakes/monkeypatch — no real HTTP calls or API keys.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pipeline.pipeline_runner import PipelineRunner, make_default_output_dir

# ------------------------------------------------------------------
# Fake return data
# ------------------------------------------------------------------

FAKE_HOMEPAGE_MAP = {
    "start_url": "https://example.com",
    "base_url": "https://example.com",
    "sitemap": {"candidates": [], "found": [], "url_count": 0, "urls": [], "errors": []},
    "homepage": {
        "title": "Example",
        "description": "Example site",
        "navigation_links": [
            {"text": "신청 안내", "url": "https://example.com/apply", "category": "apply"},
        ],
        "attachment_links": [],
        "errors": [],
    },
    "categories": {
        "menu": [], "notice": [], "board": [], "document": [],
        "apply": ["https://example.com/apply"], "contact": [], "unknown": [],
    },
    "stats": {
        "sitemap_url_count": 0, "navigation_link_count": 1, "attachment_count": 0,
        "category_counts": {
            "menu": 0, "notice": 0, "board": 0, "document": 0,
            "apply": 1, "contact": 0, "unknown": 0,
        },
    },
    "errors": [],
}

FAKE_DOCS = [
    {
        "id": "doc-000001",
        "url": "https://example.com/apply",
        "canonical_url": "https://example.com/apply",
        "title": "신청 안내",
        "category": "apply",
        "source_types": ["navigation"],
        "content_type": "page",
        "text": "",
        "summary": "",
        "metadata": {
            "base_url": "https://example.com",
            "lastmod": "", "changefreq": "", "priority": "",
            "link_texts": ["신청 안내"],
            "file_type": "",
            "discovered_from": ["navigation"],
        },
    },
]

FAKE_ENRICHED_DOCS = [
    {
        **FAKE_DOCS[0],
        "text": "중소기업 지원사업 신청 방법 안내",
        "metadata": {
            **FAKE_DOCS[0]["metadata"],
            "fetched_at": "2026-05-29T12:00:00Z",
            "http_status": 200,
            "response_content_type": "text/html",
            "fetch_status": "fetched",
            "fetch_error": "",
            "description": "지원사업 신청 안내",
        },
    },
]

FAKE_SEARCH_RESULTS = [
    {
        "rank": 1,
        "id": "doc-000001",
        "title": "신청 안내",
        "url": "https://example.com/apply",
        "canonical_url": "https://example.com/apply",
        "category": "apply",
        "content_type": "page",
        "score": 10.0,
        "matched_terms": ["신청"],
        "matched_fields": ["title"],
        "snippet": "중소기업 지원사업 신청 방법 안내",
        "metadata": {
            "source_types": ["navigation"],
            "fetch_status": "fetched",
            "description": "지원사업 신청 안내",
        },
    },
]

FAKE_ANSWER_RESULT = {
    "query": "신청서 제출서류",
    "provider": "mock",
    "model": "mock-model",
    "ok": True,
    "answer_markdown": "## 답변\n\n신청 안내 페이지를 확인하세요.\n\n## 관련 자료\n\n- [신청 안내](https://example.com/apply)\n\n## 다음에 할 일\n\n1. 안내 페이지 확인\n\n## 확인 필요 사항\n\n없음",
    "sources": [
        {
            "rank": 1,
            "id": "doc-000001",
            "title": "신청 안내",
            "url": "https://example.com/apply",
            "category": "apply",
            "content_type": "page",
            "score": 10.0,
            "matched_terms": ["신청"],
            "matched_fields": ["title"],
            "snippet": "중소기업 지원사업 신청 방법 안내",
            "description": "지원사업 신청 안내",
            "fetch_status": "fetched",
            "source_types": ["navigation"],
        }
    ],
    "warnings": [],
    "error": "",
}


# ------------------------------------------------------------------
# Test helpers
# ------------------------------------------------------------------

@pytest.fixture
def tmp_output_dir(tmp_path):
    return str(tmp_path / "run-test")


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestSuccessfulPipeline:
    """Full pipeline run with all fakes."""

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_creates_all_output_files(
        self, MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer, tmp_output_dir
    ):
        # Setup mocks
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
        result = runner.run(url="https://example.com", query="신청서 제출서류")

        assert result["ok"] is True

        expected_files = [
            "homepage-map.json",
            "document-index.jsonl",
            "enriched-index.jsonl",
            "search-results.json",
            "answer.json",
            "answer.md",
            "pipeline-result.json",
        ]
        for fname in expected_files:
            fpath = os.path.join(tmp_output_dir, fname)
            assert os.path.exists(fpath), f"{fname} not created"

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_result_ok_true(
        self, MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer, tmp_output_dir
    ):
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
        result = runner.run(url="https://example.com", query="신청서 제출서류")

        assert result["ok"] is True
        assert result["url"] == "https://example.com"
        assert result["query"] == "신청서 제출서류"
        assert result["error"] == ""

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_answer_markdown_in_result(
        self, MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer, tmp_output_dir
    ):
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
        result = runner.run(url="https://example.com", query="신청서 제출서류")

        assert "신청 안내" in result["answer_markdown"]


class TestOutputPathsIncluded:
    """Each step has its output path in the result."""

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_steps_have_output_paths(
        self, MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer, tmp_output_dir
    ):
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
        result = runner.run(url="https://example.com", query="신청서 제출서류")

        steps = result["steps"]
        assert len(steps) == 5
        assert steps[0]["output"].endswith("homepage-map.json")
        assert steps[1]["output"].endswith("document-index.jsonl")
        assert steps[2]["output"].endswith("enriched-index.jsonl")
        assert steps[3]["output"].endswith("search-results.json")
        assert steps[4]["output"].endswith("answer.json")
        assert steps[4]["markdown_output"].endswith("answer.md")


class TestFailureStopsPipeline:
    """A failing step stops the pipeline."""

    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_homepage_failure_stops_pipeline(
        self, MockMapper, MockIndexer, tmp_output_dir
    ):
        MockMapper.return_value.build_map.side_effect = RuntimeError("network error")

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
        result = runner.run(url="https://example.com", query="신청서 제출서류")

        assert result["ok"] is False
        assert "network error" in result["error"]
        assert len(result["steps"]) == 1
        assert result["steps"][0]["ok"] is False
        # Indexer should not have been called
        MockIndexer.return_value.build_index.assert_not_called()

    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_indexer_failure_stops_pipeline(
        self, MockMapper, MockIndexer, MockEnricher, tmp_output_dir
    ):
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.side_effect = ValueError("bad map")

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
        result = runner.run(url="https://example.com", query="신청서 제출서류")

        assert result["ok"] is False
        assert "bad map" in result["error"]
        assert len(result["steps"]) == 2
        assert result["steps"][0]["ok"] is True
        assert result["steps"][1]["ok"] is False
        # Enricher should not have been called
        MockEnricher.return_value.enrich_records.assert_not_called()

    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_enricher_failure_stops_pipeline(
        self, MockMapper, MockIndexer, MockEnricher, MockSearcher, tmp_output_dir
    ):
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.side_effect = RuntimeError("fetch fail")

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
        result = runner.run(url="https://example.com", query="신청서 제출서류")

        assert result["ok"] is False
        assert len(result["steps"]) == 3
        MockSearcher.return_value.search.assert_not_called()


class TestMaxEnrichPagesPassed:
    """max_enrich_pages is passed to DocumentEnricher.enrich_records."""

    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_limit_param(
        self, MockMapper, MockIndexer, MockEnricher, MockSearcher, tmp_output_dir
    ):
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
        MockSearcher.return_value.search.return_value = []

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock", max_enrich_pages=7)
        # Stop before answer step by making search return empty
        result = runner.run(url="https://example.com", query="test")

        MockEnricher.return_value.enrich_records.assert_called_once()
        call_kwargs = MockEnricher.return_value.enrich_records.call_args
        assert call_kwargs[1]["limit"] == 7 or call_kwargs.kwargs.get("limit") == 7


class TestTopKPassedToSearch:
    """top_k is passed to KeywordSearcher.search.

    Note: With query rewriter integration (Stage 344a), search is called
    once per query candidate. The test verifies top_k is passed correctly.
    """

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_top_k(
        self, MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer, tmp_output_dir
    ):
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock", top_k=3)
        runner.run(url="https://example.com", query="신청서")

        # Search is called for each query candidate (original + rewritten)
        assert MockSearcher.return_value.search.call_count >= 1
        for call in MockSearcher.return_value.search.call_args_list:
            assert call[1]["top_k"] == 3 or call.kwargs.get("top_k") == 3


class TestMaxSourcesPassedToComposer:
    """max_sources is passed to AnswerComposer."""

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_max_sources(
        self, MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer, tmp_output_dir
    ):
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock", max_sources=3)
        runner.run(url="https://example.com", query="신청서")

        MockComposer.assert_called_once()
        call_kwargs = MockComposer.call_args
        assert call_kwargs[1]["max_sources"] == 3 or call_kwargs.kwargs.get("max_sources") == 3


class TestDefaultOutputDir:
    """Default output dir follows data/runs/run-YYYYMMDD-HHMMSS format."""

    def test_format(self):
        path = make_default_output_dir()
        assert path.startswith("data/runs/run-")
        # Should be like data/runs/run-20260529-120000
        suffix = path.replace("data/runs/run-", "")
        assert len(suffix) == 15  # YYYYMMDD-HHMMSS
        assert suffix[8] == "-"


class TestJsonlOutputValid:
    """JSONL files contain valid JSON per line."""

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_jsonl_files_valid(
        self, MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer, tmp_output_dir
    ):
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
        runner.run(url="https://example.com", query="신청서")

        for fname in ["document-index.jsonl", "enriched-index.jsonl"]:
            fpath = os.path.join(tmp_output_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) >= 1
            for line in lines:
                line = line.strip()
                if line:
                    parsed = json.loads(line)
                    assert isinstance(parsed, dict)


class TestPipelineResultSaved:
    """pipeline-result.json is saved with the full result."""

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_pipeline_result_json(
        self, MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer, tmp_output_dir
    ):
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
        result = runner.run(url="https://example.com", query="신청서")

        pipeline_result_path = os.path.join(tmp_output_dir, "pipeline-result.json")
        assert os.path.exists(pipeline_result_path)
        with open(pipeline_result_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["ok"] == result["ok"]
        assert saved["url"] == result["url"]


class TestNoRealProviderCall:
    """No real LLM provider is called — only fakes."""

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_mock_provider_used(
        self, MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer, tmp_output_dir
    ):
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
        result = runner.run(url="https://example.com", query="신청서")

        # Composer was created with "mock" provider
        MockComposer.assert_called_once()
        call_kwargs = MockComposer.call_args
        assert call_kwargs[1]["provider"] == "mock" or call_kwargs.kwargs.get("provider") == "mock"
        assert result["ok"] is True


class TestPipelineFetchProvider:
    """PipelineRunner passes fetch_provider to HomepageMapper."""

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_fetch_provider_passed_to_mapper(
        self, MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer, tmp_output_dir
    ):
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT

        runner = PipelineRunner(
            output_dir=tmp_output_dir,
            provider="mock",
            fetch_provider="requests",
        )
        result = runner.run(url="https://example.com", query="신청서")

        # HomepageMapper was created with fetch_provider="requests"
        MockMapper.assert_called_once()
        call_kwargs = MockMapper.call_args
        assert call_kwargs.kwargs.get("fetch_provider") == "requests"
        assert result["ok"] is True

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    def test_fetch_provider_none_default(
        self, MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer, tmp_output_dir
    ):
        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT

        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
        result = runner.run(url="https://example.com", query="신청서")

        MockMapper.assert_called_once()
        call_kwargs = MockMapper.call_args
        # fetch_provider is None by default
        fp = call_kwargs.kwargs.get("fetch_provider")
        assert fp is None, f"Expected None, got {fp}"
        assert result["ok"] is True


class TestPipelineCrawlFilters:
    """PipelineRunner maps SiteProfile crawl filters into HomepageMapper."""

    @patch("src.pipeline.pipeline_runner.AnswerComposer")
    @patch("src.pipeline.pipeline_runner.KeywordSearcher")
    @patch("src.pipeline.pipeline_runner.DocumentEnricher")
    @patch("src.pipeline.pipeline_runner.DocumentIndexer")
    @patch("src.pipeline.pipeline_runner.HomepageMapper")
    @patch("src.site_profiles.site_profile.SiteProfileLoader")
    def test_pipeline_runner_passes_crawl_filters_from_profile(
        self, MockLoader, MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer, tmp_output_dir
    ):
        from src.site_profiles.site_profile import SiteProfile

        # 1. Setup mock synthetic profile with crawl_filters
        profile = SiteProfile({
            "site_id": "synthetic_gov",
            "name": "Synthetic Gov",
            "base_url": "https://synthetic.gov.kr/",
            "crawl_filters": {
                "deny_patterns": ["print="],
                "protected_patterns": ["mid="]
            }
        })

        MockLoader.return_value.list_ids.return_value = ["synthetic_gov"]
        MockLoader.return_value.load_by_id.return_value = profile

        MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
        MockIndexer.return_value.build_index.return_value = FAKE_DOCS
        MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
        MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
        MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT

        # 2. Run PipelineRunner with matching URL
        runner = PipelineRunner(output_dir=tmp_output_dir, provider="mock")
        result = runner.run(url="https://synthetic.gov.kr/", query="신청서")

        # 3. Assert resolved crawl_filters were passed to HomepageMapper
        MockMapper.assert_called_once()
        call_kwargs = MockMapper.call_args
        assert call_kwargs.kwargs.get("crawl_filters") == {
            "allow_patterns": [],
            "deny_patterns": ["print="],
            "protected_patterns": ["mid="]
        }
        assert result["ok"] is True
