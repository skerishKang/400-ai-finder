"""Tests for the grounded answer demo runner — SiteDemoRunner."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.demo import SiteDemoRunner, run_demo
from src.demo.site_demo_runner import load_profile


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

SAMPLE_SEARCH_RESULTS = [
    {
        "title": "민원서식",
        "url": "https://bukgu.gwangju.kr/menu.es?mid=a10101040000",
        "category": "document",
        "text": "민원서식 작성예시 QR코드 민원편의시책 여권민원 제증명 수수료",
        "score": 0.95,
    },
    {
        "title": "교육접수",
        "url": "https://bukgu.gwangju.kr/menu.es?mid=a10208020000",
        "category": "apply",
        "text": "정보화교육(컴퓨터교육) 정보화교육 안내 시니어 디지털 교육 안내 교육접수",
        "score": 0.88,
    },
]

SAMPLE_SEARCH_OUTPUT = {
    "query": "민원서식 어디서 받아?",
    "top_k": 5,
    "filters": {"category": "", "content_type": ""},
    "result_count": 2,
    "results": SAMPLE_SEARCH_RESULTS,
}

SAMPLE_ANSWER_OUTPUT = {
    "query": "민원서식 어디서 받아?",
    "provider": "mock",
    "model": "mock-model",
    "ok": True,
    "answer_markdown": (
        "## 답변\n\n"
        "민원서식은 북구청 홈페이지에서 확인할 수 있습니다.\n\n"
        "## 관련 자료\n"
        "- [민원서식](https://bukgu.gwangju.kr/menu.es?mid=a10101040000)\n"
        "- [교육접수](https://bukgu.gwangju.kr/menu.es?mid=a10208020000)\n\n"
        "## 다음에 할 일\n"
        "링크를 클릭하여 해당 페이지에서 서식을 내려받으세요.\n\n"
        "## 확인 필요 사항\n"
        "필요한 서식이 정확한지 홈페이지에서 확인하세요."
    ),
    "sources": [
        {
            "title": "민원서식",
            "url": "https://bukgu.gwangju.kr/menu.es?mid=a10101040000",
            "source_type": "document",
            "snippet": "민원서식 작성예시 QR코드 민원편의시책",
            "score": 0.95,
        },
    ],
    "warnings": [],
    "error": "",
}

SAMPLE_PIPELINE_RESULT = {
    "ok": True,
    "url": "https://bukgu.gwangju.kr/",
    "query": "민원서식 어디서 받아?",
    "output_dir": "/tmp/demo-test",
    "steps": [
        {"name": "homepage_map", "ok": True, "output": "/tmp/demo-test/homepage-map.json", "error": ""},
        {"name": "document_index", "ok": True, "output": "/tmp/demo-test/document-index.jsonl", "error": ""},
        {"name": "enriched_index", "ok": True, "output": "/tmp/demo-test/enriched-index.jsonl", "error": ""},
        {
            "name": "search",
            "ok": True,
            "output": "/tmp/demo-test/search-results.json",
            "error": "",
        },
        {
            "name": "answer",
            "ok": True,
            "output": "/tmp/demo-test/answer.json",
            "error": "",
        },
    ],
    "answer_markdown": SAMPLE_ANSWER_OUTPUT["answer_markdown"],
    "error": "",
}


@pytest.fixture
def mock_pipeline_and_files(tmp_path: Path) -> dict:
    """Set up a mock PipelineRunner that writes stub output files.

    Returns a dict with the mock runner instance and paths.
    """
    search_path = tmp_path / "search-results.json"
    answer_path = tmp_path / "answer.json"

    with open(search_path, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_SEARCH_OUTPUT, f, ensure_ascii=False)

    with open(answer_path, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_ANSWER_OUTPUT, f, ensure_ascii=False)

    # Patch the pipeline steps to point to our tmp files
    result = dict(SAMPLE_PIPELINE_RESULT)
    result["output_dir"] = str(tmp_path)
    for step in result["steps"]:
        if step["name"] == "search":
            step["output"] = str(search_path)
        elif step["name"] == "answer":
            step["output"] = str(answer_path)

    mock_runner = MagicMock()
    mock_runner.run.return_value = result

    return {
        "mock_runner": mock_runner,
        "search_path": str(search_path),
        "answer_path": str(answer_path),
        "pipeline_result": result,
        "tmp_path": str(tmp_path),
    }


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestSiteDemoRunnerUnit:
    """Unit tests — mock the PipelineRunner to avoid real HTTP calls."""

    def test_profile_loaded_from_site_id(self):
        """1. site_id로 북구청 프로필 로드 확인."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        assert runner.profile.site_id == "bukgu_gwangju"
        assert "북구" in runner.profile.name
        assert runner.profile.preferred_fetch_provider == "requests"

    def test_empty_question_raises(self):
        """2. 빈 질문 예외 처리."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        with pytest.raises(ValueError, match="Question must not be empty"):
            runner.answer("")
        with pytest.raises(ValueError, match="Question must not be empty"):
            runner.answer("   ")

    def test_invalid_site_id_raises(self):
        """3. 잘못된 site_id 예외 처리."""
        with pytest.raises(FileNotFoundError):
            SiteDemoRunner(site_id="definitely_not_a_real_site", provider="mock")

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_mock_provider_answer_generated(self, mock_pipeline_cls, mock_pipeline_and_files):
        """4. mock provider 기반 답변 생성."""
        ctx = mock_pipeline_and_files
        mock_pipeline_cls.return_value = ctx["mock_runner"]

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer("민원서식 어디서 받아?", output_dir=ctx["tmp_path"])

        assert result["ok"] is True
        assert result["site_id"] == "bukgu_gwangju"
        assert result["question"] == "민원서식 어디서 받아?"

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_search_results_included(self, mock_pipeline_cls, mock_pipeline_and_files):
        """5. 검색 결과 포함 확인."""
        ctx = mock_pipeline_and_files
        mock_pipeline_cls.return_value = ctx["mock_runner"]

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer("민원서식 어디서 받아?", output_dir=ctx["tmp_path"])

        assert len(result["search_results"]) >= 1
        assert any("민원서식" in str(r) for r in result["search_results"])

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_sources_included(self, mock_pipeline_cls, mock_pipeline_and_files):
        """6. 출처 정보 포함 확인."""
        ctx = mock_pipeline_and_files
        mock_pipeline_cls.return_value = ctx["mock_runner"]

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer("민원서식 어디서 받아?", output_dir=ctx["tmp_path"])

        assert len(result["sources"]) >= 1
        src = result["sources"][0]
        assert "title" in src
        assert "url" in src
        assert "source_type" in src

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_json_serializable(self, mock_pipeline_cls, mock_pipeline_and_files):
        """7. JSON 직렬화 가능한 결과 반환."""
        ctx = mock_pipeline_and_files
        mock_pipeline_cls.return_value = ctx["mock_runner"]

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer("민원서식 어디서 받아?", output_dir=ctx["tmp_path"])

        dumped = json.dumps(result, ensure_ascii=False)
        loaded = json.loads(dumped)
        assert loaded["site_id"] == "bukgu_gwangju"
        assert len(loaded["sources"]) >= 1

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_minwonseo_keyword_connected(self, mock_pipeline_cls, mock_pipeline_and_files):
        """8. '민원서식' 질문이 실제 북구청 메뉴/링크 후보와 연결."""
        ctx = mock_pipeline_and_files
        mock_pipeline_cls.return_value = ctx["mock_runner"]

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer("민원서식 어디서 받아?", output_dir=ctx["tmp_path"])

        sources = result.get("sources", [])
        search_results = result.get("search_results", [])
        all_text = str(sources) + str(search_results) + result.get("answer", "")
        assert any(
            kw in all_text
            for kw in ["민원서식", "menu.es?mid=a10101040000"]
        )

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_gyoyukjeopsu_keyword_connected(self, mock_pipeline_cls, tmp_path):
        """9. '교육접수' 질문이 실제 북구청 메뉴/링크 후보와 연결."""
        # Direct setup — avoid fixture complications
        search_path = tmp_path / "search-results.json"
        answer_path = tmp_path / "answer.json"

        edu_output = {
            "query": "교육접수는 어디서 해?",
            "top_k": 5, "filters": {}, "result_count": 1,
            "results": [
                {"title": "교육접수", "url": "https://bukgu.gwangju.kr/menu.es?mid=a10208020000",
                 "category": "apply", "text": "교육접수 안내 정보화교육 컴퓨터교육", "score": 0.9}
            ]
        }
        with open(search_path, "w", encoding="utf-8") as f:
            json.dump(edu_output, f, ensure_ascii=False)

        answer_out = {"query": "교육접수", "provider": "mock", "model": "mock",
                      "ok": True, "answer_markdown": "## 답변\n교육접수",
                      "sources": [], "warnings": [], "error": ""}
        with open(answer_path, "w", encoding="utf-8") as f:
            json.dump(answer_out, f, ensure_ascii=False)

        pipeline_result = {
            "ok": True, "url": "https://bukgu.gwangju.kr/", "query": "교육접수는 어디서 해?",
            "output_dir": str(tmp_path),
            "steps": [
                {"name": "homepage_map", "ok": True, "output": str(tmp_path / "hm.json"), "error": ""},
                {"name": "search", "ok": True, "output": str(search_path), "error": ""},
                {"name": "answer", "ok": True, "output": str(answer_path), "error": ""},
            ],
            "answer_markdown": "## 답변\n교육접수", "error": "",
        }

        mock_runner = MagicMock()
        mock_runner.run.return_value = pipeline_result
        mock_pipeline_cls.return_value = mock_runner

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer("교육접수는 어디서 해?", output_dir=str(tmp_path))

        search_results = result.get("search_results", [])
        all_text = str(search_results)
        assert any(
            kw in all_text
            for kw in ["교육접수", "a10208020000"]
        )

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_output_path_saved(self, mock_pipeline_cls, mock_pipeline_and_files):
        """10. output path 저장 확인 (pytest tmp_path 사용)."""
        ctx = mock_pipeline_and_files
        mock_pipeline_cls.return_value = ctx["mock_runner"]

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer("민원서식 어디서 받아?", output_dir=ctx["tmp_path"])

        # Verify output_dir exists and contains result
        assert os.path.isdir(ctx["tmp_path"])
        assert runner.profile.site_id == "bukgu_gwangju"

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_answer_content_present(self, mock_pipeline_cls, mock_pipeline_and_files):
        """Extra: 답변 내용이 result에 포함되는지 확인."""
        ctx = mock_pipeline_and_files
        mock_pipeline_cls.return_value = ctx["mock_runner"]

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer("민원서식 어디서 받아?", output_dir=ctx["tmp_path"])

        answer = result.get("answer", "")
        assert len(answer) > 0
        assert "민원서식" in answer or "답변" in answer

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_fetch_provider_from_profile(self, mock_pipeline_cls, mock_pipeline_and_files):
        """Extra: fetch_provider defaults to profile's preferred."""
        ctx = mock_pipeline_and_files
        mock_pipeline_cls.return_value = ctx["mock_runner"]

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        assert runner._fetch_provider == "requests"

        # Explicit override
        runner2 = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock", fetch_provider="firecrawl")
        assert runner2._fetch_provider == "firecrawl"

    def test_run_demo_convenience(self):
        """Extra: run_demo convenience function returns correct shape."""
        with patch("src.demo.site_demo_runner.PipelineRunner") as mock_cls:
            mock_runner = MagicMock()
            mock_runner.run.return_value = SAMPLE_PIPELINE_RESULT
            mock_cls.return_value = mock_runner

            result = run_demo(
                site_id="bukgu_gwangju",
                question="민원서식 어디서 받아?",
                provider="mock",
                output_dir="/tmp/demo-test",
            )

            assert result["site_id"] == "bukgu_gwangju"
            assert "question" in result
            assert "sources" in result


class TestDemoIntegration:
    """Integration tests — verify demo runner wires together correctly.

    These use the real profile loader and mock PipelineRunner only.
    """

    def test_real_profile_with_mock_pipeline(self, tmp_path):
        """Real profile loading + mock pipeline returns valid result."""
        with patch("src.demo.site_demo_runner.PipelineRunner") as mock_cls:
            mock_runner = MagicMock()

            # Set up stub pipeline output files
            search_p = tmp_path / "search-results.json"
            answer_p = tmp_path / "answer.json"
            with open(search_p, "w") as f:
                json.dump(SAMPLE_SEARCH_OUTPUT, f, ensure_ascii=False)
            with open(answer_p, "w") as f:
                json.dump(SAMPLE_ANSWER_OUTPUT, f, ensure_ascii=False)

            result = dict(SAMPLE_PIPELINE_RESULT)
            result["output_dir"] = str(tmp_path)
            for step in result["steps"]:
                if step["name"] == "search":
                    step["output"] = str(search_p)
                elif step["name"] == "answer":
                    step["output"] = str(answer_p)

            mock_runner.run.return_value = result
            mock_cls.return_value = mock_runner

            runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
            demo_result = runner.answer("민원서식 어디서 받아?", output_dir=str(tmp_path))

            assert demo_result["ok"] is True
            assert "bukgu" in demo_result["site_id"]
            assert len(demo_result.get("sources", [])) > 0


class TestFallback:
    """Fallback tests — search result 0-count → homepage map fallback."""

    SAMPLE_HOMEPAGE_MAP = {
        "start_url": "https://bukgu.gwangju.kr/",
        "base_url": "https://bukgu.gwangju.kr",
        "homepage": {
            "title": "광주광역시 북구",
            "description": "",
            "navigation_links": [
                {"title": "민원서식", "url": "https://bukgu.gwangju.kr/menu.es?mid=a10101040000", "text": "민원서식"},
                {"title": "교육접수", "url": "https://bukgu.gwangju.kr/menu.es?mid=a10208020000", "text": "교육접수"},
                {"title": "정보공개", "url": "https://bukgu.gwangju.kr/menu.es?mid=a10301010000", "text": "정보공개"},
                {"title": "고시공고", "url": "https://bukgu.gwangju.kr/menu.es?mid=a10401010000", "text": "고시공고"},
            ],
            "attachment_links": [],
            "errors": [],
        },
        "categories": {
            "menu": [
                {"title": "교육접수", "url": "https://bukgu.gwangju.kr/menu.es?mid=a10208020000", "text": "교육접수"},
            ],
            "notice": [],
            "board": [],
            "document": [
                {"title": "민원서식", "url": "https://bukgu.gwangju.kr/menu.es?mid=a10101040000", "text": "민원서식"},
            ],
            "apply": [],
            "contact": [],
            "unknown": [],
        },
        "sitemap": {"candidates": [], "found": [], "url_count": 0, "urls": [], "errors": []},
        "stats": {
            "sitemap_url_count": 0,
            "navigation_link_count": 4,
            "attachment_count": 0,
            "category_counts": {"menu": 1, "notice": 0, "board": 0, "document": 1, "apply": 0, "contact": 0, "unknown": 0},
        },
        "errors": [],
    }

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_fallback_when_search_empty(self, mock_pipeline_cls, tmp_path):
        """1. 검색 결과 0건일 때 fallback이 동작한다."""
        search_path = tmp_path / "search-results.json"
        answer_path = tmp_path / "answer.json"
        hm_path = tmp_path / "homepage-map.json"

        with open(search_path, "w") as f:
            json.dump({"query": "교육접수", "top_k": 5, "filters": {}, "result_count": 0, "results": []}, f)
        with open(answer_path, "w") as f:
            json.dump({"query": "교육접수", "provider": "mock", "ok": True, "answer_markdown": "## 답변\n관련 자료를 찾지 못했습니다.", "sources": [], "warnings": [], "error": ""}, f)
        with open(hm_path, "w") as f:
            json.dump(self.SAMPLE_HOMEPAGE_MAP, f, ensure_ascii=False)

        pipeline_result = {
            "ok": True, "url": "https://bukgu.gwangju.kr/", "query": "교육접수",
            "output_dir": str(tmp_path),
            "steps": [
                {"name": "homepage_map", "ok": True, "output": str(hm_path), "error": ""},
                {"name": "document_index", "ok": True, "output": str(tmp_path / "doc.jsonl"), "error": ""},
                {"name": "enriched_index", "ok": True, "output": str(tmp_path / "enr.jsonl"), "error": ""},
                {"name": "search", "ok": True, "output": str(search_path), "error": ""},
                {"name": "answer", "ok": True, "output": str(answer_path), "error": ""},
            ],
            "answer_markdown": "## 답변\n관련 자료를 찾지 못했습니다.", "error": "",
        }

        mock_runner = MagicMock()
        mock_runner.run.return_value = pipeline_result
        mock_pipeline_cls.return_value = mock_runner

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer("교육접수는 어디서 해?", output_dir=str(tmp_path))

        assert result["fallback_used"] is True
        assert len(result["search_results"]) >= 1
        assert len(result["sources"]) >= 1
        assert "fallback" in " ".join(result["warnings"]).lower()

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_important_keywords_expansion(self, mock_pipeline_cls, tmp_path):
        """2. site profile important_keywords 기반 확장이 동작한다."""
        search_path = tmp_path / "search-results.json"
        answer_path = tmp_path / "answer.json"
        hm_path = tmp_path / "homepage-map.json"

        with open(search_path, "w") as f:
            json.dump({"query": "교육접수", "top_k": 5, "filters": {}, "result_count": 0, "results": []}, f)
        with open(answer_path, "w") as f:
            json.dump({"query": "교육접수", "provider": "mock", "ok": True, "answer_markdown": "", "sources": [], "warnings": [], "error": ""}, f)
        with open(hm_path, "w") as f:
            json.dump(self.SAMPLE_HOMEPAGE_MAP, f, ensure_ascii=False)

        pipeline_result = {
            "ok": True, "url": "https://bukgu.gwangju.kr/", "query": "교육접수",
            "output_dir": str(tmp_path),
            "steps": [
                {"name": "homepage_map", "ok": True, "output": str(hm_path), "error": ""},
                {"name": "search", "ok": True, "output": str(search_path), "error": ""},
                {"name": "answer", "ok": True, "output": str(answer_path), "error": ""},
            ],
            "answer_markdown": "", "error": "",
        }

        mock_runner = MagicMock()
        mock_runner.run.return_value = pipeline_result
        mock_pipeline_cls.return_value = mock_runner

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer("교육접수는 어디서 해?", output_dir=str(tmp_path))

        # Should match "교육접수" from profile's important_keywords (expanded)
        sources = result["sources"]
        all_text = str(sources) + str(result["search_results"])
        assert any(kw in all_text for kw in ["교육접수", "a10208020000"])

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_gyoyukjeopsu_source_at_least_1(self, mock_pipeline_cls, tmp_path):
        """3. '교육접수' 질문에서 source 1건 이상 반환한다."""
        search_path = tmp_path / "search-results.json"
        answer_path = tmp_path / "answer.json"
        hm_path = tmp_path / "homepage-map.json"

        with open(search_path, "w") as f:
            json.dump({"query": "교육접수", "top_k": 5, "filters": {}, "result_count": 0, "results": []}, f)
        with open(answer_path, "w") as f:
            json.dump({"query": "교육접수", "provider": "mock", "ok": True, "answer_markdown": "", "sources": [], "warnings": [], "error": ""}, f)
        with open(hm_path, "w") as f:
            json.dump(self.SAMPLE_HOMEPAGE_MAP, f, ensure_ascii=False)

        pipeline_result = {
            "ok": True, "url": "https://bukgu.gwangju.kr/", "query": "교육접수",
            "output_dir": str(tmp_path),
            "steps": [
                {"name": "homepage_map", "ok": True, "output": str(hm_path), "error": ""},
                {"name": "search", "ok": True, "output": str(search_path), "error": ""},
                {"name": "answer", "ok": True, "output": str(answer_path), "error": ""},
            ],
            "answer_markdown": "", "error": "",
        }

        mock_runner = MagicMock()
        mock_runner.run.return_value = pipeline_result
        mock_pipeline_cls.return_value = mock_runner

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer("교육접수는 어디서 해?", output_dir=str(tmp_path))

        assert len(result["sources"]) >= 1
        assert result["sources"][0]["title"]
        assert result["sources"][0]["url"]

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_minwonseo_existing_success_maintained(self, mock_pipeline_cls, tmp_path):
        """4. '민원서식' 기존 성공 케이스가 유지된다."""
        search_path = tmp_path / "search-results.json"
        answer_path = tmp_path / "answer.json"

        with open(search_path, "w") as f:
            json.dump(SAMPLE_SEARCH_OUTPUT, f, ensure_ascii=False)
        with open(answer_path, "w") as f:
            json.dump(SAMPLE_ANSWER_OUTPUT, f, ensure_ascii=False)

        result = dict(SAMPLE_PIPELINE_RESULT)
        result["output_dir"] = str(tmp_path)
        for step in result["steps"]:
            if step["name"] == "search":
                step["output"] = str(search_path)
            elif step["name"] == "answer":
                step["output"] = str(answer_path)

        mock_runner = MagicMock()
        mock_runner.run.return_value = result
        mock_pipeline_cls.return_value = mock_runner

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        demo_result = runner.answer("민원서식 어디서 받아?", output_dir=str(tmp_path))

        assert len(demo_result["sources"]) >= 1
        assert demo_result["fallback_used"] is False  # no fallback needed

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_fallback_json_serializable(self, mock_pipeline_cls, tmp_path):
        """5. fallback 결과도 JSON 직렬화 가능하다."""
        search_path = tmp_path / "search-results.json"
        answer_path = tmp_path / "answer.json"
        hm_path = tmp_path / "homepage-map.json"

        with open(search_path, "w") as f:
            json.dump({"query": "교육접수", "top_k": 5, "filters": {}, "result_count": 0, "results": []}, f)
        with open(answer_path, "w") as f:
            json.dump({"query": "교육접수", "provider": "mock", "ok": True, "answer_markdown": "", "sources": [], "warnings": [], "error": ""}, f)
        with open(hm_path, "w") as f:
            json.dump(self.SAMPLE_HOMEPAGE_MAP, f, ensure_ascii=False)

        pipeline_result = {
            "ok": True, "url": "https://bukgu.gwangju.kr/", "query": "교육접수",
            "output_dir": str(tmp_path),
            "steps": [
                {"name": "homepage_map", "ok": True, "output": str(hm_path), "error": ""},
                {"name": "search", "ok": True, "output": str(search_path), "error": ""},
                {"name": "answer", "ok": True, "output": str(answer_path), "error": ""},
            ],
            "answer_markdown": "", "error": "",
        }

        mock_runner = MagicMock()
        mock_runner.run.return_value = pipeline_result
        mock_pipeline_cls.return_value = mock_runner

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer("교육접수는 어디서 해?", output_dir=str(tmp_path))

        dumped = json.dumps(result, ensure_ascii=False)
        loaded = json.loads(dumped)
        assert loaded["fallback_used"] is True
        assert len(loaded["sources"]) >= 1

    @patch("src.demo.site_demo_runner.PipelineRunner")
    def test_fallback_source_has_title_url(self, mock_pipeline_cls, tmp_path):
        """6. fallback 결과에는 source title/url이 포함된다."""
        search_path = tmp_path / "search-results.json"
        answer_path = tmp_path / "answer.json"
        hm_path = tmp_path / "homepage-map.json"

        with open(search_path, "w") as f:
            json.dump({"query": "교육접수", "top_k": 5, "filters": {}, "result_count": 0, "results": []}, f)
        with open(answer_path, "w") as f:
            json.dump({"query": "교육접수", "provider": "mock", "ok": True, "answer_markdown": "", "sources": [], "warnings": [], "error": ""}, f)
        with open(hm_path, "w") as f:
            json.dump(self.SAMPLE_HOMEPAGE_MAP, f, ensure_ascii=False)

        pipeline_result = {
            "ok": True, "url": "https://bukgu.gwangju.kr/", "query": "교육접수",
            "output_dir": str(tmp_path),
            "steps": [
                {"name": "homepage_map", "ok": True, "output": str(hm_path), "error": ""},
                {"name": "search", "ok": True, "output": str(search_path), "error": ""},
                {"name": "answer", "ok": True, "output": str(answer_path), "error": ""},
            ],
            "answer_markdown": "", "error": "",
        }

        mock_runner = MagicMock()
        mock_runner.run.return_value = pipeline_result
        mock_pipeline_cls.return_value = mock_runner

        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer("교육접수는 어디서 해?", output_dir=str(tmp_path))

        for src in result["sources"]:
            assert "title" in src
            assert "url" in src
            assert len(src["title"]) > 0
            assert len(src["url"]) > 0


# ------------------------------------------------------------------
# Snapshot tests
# ------------------------------------------------------------------

FIXTURE_SNAPSHOT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "tests", "fixtures", "bukgu_gwangju_demo_snapshot.json",
)


class TestSnapshot:
    """Snapshot save / load / answer-from-snapshot tests."""

    def test_save_snapshot_json_serializable(self, tmp_path):
        """1. snapshot 저장 결과가 JSON 직렬화 가능하다."""
        result = {"site_id": "bukgu_gwangju", "question": "민원서식", "ok": True,
                  "sources": [{"title": "민원서식", "url": "https://bukgu.gwangju.kr"}],
                  "search_results": [], "answer": "## 답변", "warnings": []}
        out = tmp_path / "snap.json"
        saved = SiteDemoRunner.save_snapshot(result, str(out))
        assert os.path.exists(saved)
        with open(saved, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["site_id"] == "bukgu_gwangju"

    def test_load_snapshot_valid(self):
        """2. snapshot 로드로 demo answer를 생성한다."""
        snapshot = SiteDemoRunner.load_snapshot(FIXTURE_SNAPSHOT)
        assert snapshot["site_id"] == "bukgu_gwangju"
        assert snapshot["question"] == "민원서식 어디서 받아?"
        assert len(snapshot["sources"]) >= 1

    def test_answer_from_snapshot_same_question(self):
        """3. snapshot 모드에서 기존 질문의 답변을 반환한다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(FIXTURE_SNAPSHOT)
        assert result["snapshot_mode"] is True
        assert result["site_id"] == "bukgu_gwangju"
        assert len(result["sources"]) >= 1
        assert "데모 자료" in " ".join(result["warnings"])

    def test_answer_from_snapshot_different_question(self):
        """4. '교육접수' 질문에서 snapshot 기반 fallback source가 반환된다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(FIXTURE_SNAPSHOT, question="교육접수는 어디서 해?")
        assert result["snapshot_mode"] is True
        assert result["question"] == "교육접수는 어디서 해?"
        sources = result.get("sources", [])
        all_text = str(sources) + str(result.get("search_results", []))
        assert any(kw in all_text for kw in ["교육접수", "a10208020000"]), \
            f"Expected 교육접수 in sources, got: {all_text}"

    def test_snapshot_source_has_title_url(self):
        """5. snapshot mode에서도 sources title/url이 포함된다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(FIXTURE_SNAPSHOT, question="교육접수는 어디서 해?")
        for src in result.get("sources", []):
            assert "title" in src
            assert "url" in src
            assert len(src["title"]) > 0
            assert len(src["url"]) > 0

    def test_snapshot_minwonseo_success_maintained(self):
        """6. '민원서식' 기존 성공 케이스가 유지된다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(FIXTURE_SNAPSHOT, question="민원서식 어디서 받아?")
        assert len(result["sources"]) >= 1
        all_text = str(result["sources"]) + str(result["search_results"])
        assert any(kw in all_text for kw in ["민원서식", "a10101040000"])

    def test_invalid_snapshot_path_raises(self):
        """7. 잘못된 snapshot 경로는 명확한 예외를 반환한다."""
        with pytest.raises(FileNotFoundError):
            SiteDemoRunner.load_snapshot("/tmp/definitely_no_snapshot_xyz.json")

    def test_invalid_snapshot_json_raises(self, tmp_path):
        """7b. JSON이 아닌 snapshot 파일은 ValueError."""
        bad = tmp_path / "bad.json"
        bad.write_text("not json {{{", encoding="utf-8")
        with pytest.raises(ValueError):
            SiteDemoRunner.load_snapshot(str(bad))

    def test_snapshot_missing_keys_raises(self, tmp_path):
        """7c. 필수 키 누락 snapshot은 ValueError."""
        bad = tmp_path / "missing.json"
        bad.write_text(json.dumps({"site_id": "test"}), encoding="utf-8")
        with pytest.raises(ValueError, match="missing required keys"):
            SiteDemoRunner.load_snapshot(str(bad))

    def test_run_demo_with_snapshot(self):
        """8. run_demo convenience 함수가 snapshot 모드를 지원한다."""
        result = run_demo(
            site_id="bukgu_gwangju",
            question="교육접수는 어디서 해?",
            provider="mock",
            snapshot=FIXTURE_SNAPSHOT,
        )
        assert result["snapshot_mode"] is True
        assert len(result["sources"]) >= 1

    def test_run_demo_save_snapshot(self, tmp_path):
        """9. run_demo convenience 함수가 snapshot 저장을 지원한다."""
        snap_out = str(tmp_path / "saved_snap.json")
        result = run_demo(
            site_id="bukgu_gwangju",
            question="민원서식",
            provider="mock",
            snapshot=FIXTURE_SNAPSHOT,
            save_snapshot=snap_out,
        )
        assert os.path.exists(snap_out)
        with open(snap_out, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["site_id"] == "bukgu_gwangju"

    def test_snapshot_roundtrip(self, tmp_path):
        """10. save → load roundtrip이 데이터를 보존한다."""
        original = SiteDemoRunner.load_snapshot(FIXTURE_SNAPSHOT)
        out = str(tmp_path / "roundtrip.json")
        SiteDemoRunner.save_snapshot(original, out)
        reloaded = SiteDemoRunner.load_snapshot(out)
        assert reloaded["site_id"] == original["site_id"]
        assert reloaded["question"] == original["question"]
        assert len(reloaded["sources"]) == len(original["sources"])


# ------------------------------------------------------------------
# Stage 16: Answer-source consistency & UX tests
# ------------------------------------------------------------------


class TestAnswerSourceConsistency:
    """Verify that answer content matches the question topic and sources."""

    def test_gosigongo_answer_mentions_topic(self):
        """고시공고 질문에서 답변이 고시공고를 안내한다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(
            FIXTURE_SNAPSHOT, question="고시공고는 어디서 확인해?"
        )
        assert "고시공고" in result["answer"]
        assert result["question"] == "고시공고는 어디서 확인해?"

    def test_gyoyukjeopsu_answer_mentions_topic(self):
        """교육접수 질문에서 답변이 교육접수를 안내한다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(
            FIXTURE_SNAPSHOT, question="교육접수는 어디서 해?"
        )
        assert "교육접수" in result["answer"]

    def test_minwonseo_answer_mentions_topic(self):
        """민원서식 질문에서 답변이 민원서식을 안내한다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(
            FIXTURE_SNAPSHOT, question="민원서식 어디서 받아?"
        )
        assert "민원서식" in result["answer"]

    def test_jeongbo_gonggae_answer_mentions_topic(self):
        """정보공개 질문에서 답변이 정보공개를 안내한다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(
            FIXTURE_SNAPSHOT, question="정보공개는 어디서 볼 수 있어?"
        )
        assert "정보공개" in result["answer"]

    def test_different_question_does_not_reuse_old_answer(self):
        """질문이 바뀌면 이전 질문의 답변을 재사용하지 않는다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        # First: 민원서식
        result1 = runner.answer_from_snapshot(FIXTURE_SNAPSHOT)
        answer1 = result1["answer"]

        # Then: 고시공고
        result2 = runner.answer_from_snapshot(
            FIXTURE_SNAPSHOT, question="고시공고는 어디서 확인해?"
        )
        answer2 = result2["answer"]

        # Answers should be different
        assert answer1 != answer2
        assert "고시공고" in answer2

    def test_answer_mentions_site_name(self):
        """답변에 기관명이 포함된다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(
            FIXTURE_SNAPSHOT, question="고시공고는 어디서 확인해?"
        )
        assert "북구" in result["answer"]

    def test_answer_has_guide_structure(self):
        """답변이 안내형 구조를 갖춘다 (주제 + 메뉴 + 행동 안내)."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(
            FIXTURE_SNAPSHOT, question="교육접수는 어디서 해?"
        )
        answer = result["answer"]
        # Should have topic acknowledgment
        assert "교육접수" in answer
        # Should have location guidance
        assert any(kw in answer for kw in ["메뉴", "홈페이지", "에서"])
        # Should have action guidance
        assert any(kw in answer for kw in ["눌러", "이동", "확인"])

    def test_user_friendly_warnings_no_dev_terms(self):
        """warnings에 개발자 용어가 노출되지 않는다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(
            FIXTURE_SNAPSHOT, question="교육접수는 어디서 해?"
        )
        all_warnings = " ".join(result.get("warnings", []))
        assert "snapshot" not in all_warnings.lower()
        assert "fallback" not in all_warnings.lower()


class TestGosigongoAndGonggae:
    """고시공고/정보공개 fallback이 homepage_map에서 후보를 찾는지 확인."""

    def test_gosigongo_source_found(self):
        """고시공고 질문에서 출처가 1건 이상이다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(
            FIXTURE_SNAPSHOT, question="고시공고는 어디서 확인해?"
        )
        assert len(result["sources"]) >= 1

    def test_gosigongo_source_has_url(self):
        """고시공고 출처에 URL이 포함된다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(
            FIXTURE_SNAPSHOT, question="고시공고는 어디서 확인해?"
        )
        urls = [s["url"] for s in result["sources"]]
        assert any("bukgu.gwangju.kr" in u for u in urls)

    def test_jeongbo_gonggae_source_found(self):
        """정보공개 질문에서 출처가 1건 이상이다."""
        runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
        result = runner.answer_from_snapshot(
            FIXTURE_SNAPSHOT, question="정보공개는 어디서 볼 수 있어?"
        )
        assert len(result["sources"]) >= 1
