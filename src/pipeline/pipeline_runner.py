"""PipelineRunner — orchestrates Stage 2-6 into a single end-to-end run.

Usage::

    runner = PipelineRunner(output_dir="data/runs/example", provider="mock")
    result = runner.run(url="https://example.com", query="신청서 제출서류")
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from ..crawler.homepage_mapper import HomepageMapper
from ..indexer.document_indexer import DocumentIndexer
from ..indexer.document_enricher import DocumentEnricher
from ..search.keyword_searcher import KeywordSearcher
from ..answer.answer_composer import AnswerComposer


class PipelineRunner:
    """Orchestrates the full search-and-answer pipeline."""

    def __init__(
        self,
        output_dir: str,
        provider: str | None = None,
        max_sitemap_urls: int = 200,
        max_sitemaps: int = 10,
        max_enrich_pages: int = 20,
        top_k: int = 5,
        max_sources: int = 5,
        max_chars: int = 12000,
    ):
        self.output_dir = output_dir
        self.provider = provider or "mock"
        self.max_sitemap_urls = max_sitemap_urls
        self.max_sitemaps = max_sitemaps
        self.max_enrich_pages = max_enrich_pages
        self.top_k = top_k
        self.max_sources = max_sources
        self.max_chars = max_chars

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, url: str, query: str) -> dict[str, Any]:
        """Execute the full pipeline.

        Steps:
            1. HomepageMapper.build_map  → homepage-map.json
            2. DocumentIndexer.build_index → document-index.jsonl
            3. DocumentEnricher.enrich_records → enriched-index.jsonl
            4. KeywordSearcher.search → search-results.json
            5. AnswerComposer.compose → answer.json, answer.md
        """
        os.makedirs(self.output_dir, exist_ok=True)

        steps: list[dict[str, Any]] = []
        overall_ok = True

        # Step 1 — homepage map
        step = self._step_homepage_map(url)
        steps.append(step)
        if not step["ok"]:
            return self._final_result(url, query, steps, overall_ok=False)

        homepage_map = self._load_json(step["output"])

        # Step 2 — document index
        step = self._step_document_index(homepage_map)
        steps.append(step)
        if not step["ok"]:
            return self._final_result(url, query, steps, overall_ok=False)

        # Step 3 — enriched index
        step = self._step_enriched_index(step["output"])
        steps.append(step)
        if not step["ok"]:
            return self._final_result(url, query, steps, overall_ok=False)

        # Step 4 — search
        step = self._step_search(query, step["output"])
        steps.append(step)
        if not step["ok"]:
            return self._final_result(url, query, steps, overall_ok=False)

        # Step 5 — answer
        step = self._step_answer(query, step["output"])
        steps.append(step)
        if not step["ok"]:
            return self._final_result(url, query, steps, overall_ok=False)

        answer_markdown = self._load_json(step["output"]).get("answer_markdown", "")
        return self._final_result(url, query, steps, overall_ok=True, answer_markdown=answer_markdown)

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    def _step_homepage_map(self, url: str) -> dict[str, Any]:
        output = os.path.join(self.output_dir, "homepage-map.json")
        try:
            mapper = HomepageMapper(
                max_sitemaps=self.max_sitemaps,
                max_sitemap_urls=self.max_sitemap_urls,
            )
            result = mapper.build_map(url)
            self._write_json(output, result)
            return _step_ok("homepage_map", output)
        except Exception as e:
            return _step_fail("homepage_map", output, e)

    def _step_document_index(self, homepage_map: dict) -> dict[str, Any]:
        output = os.path.join(self.output_dir, "document-index.jsonl")
        try:
            indexer = DocumentIndexer()
            docs = indexer.build_index(homepage_map)
            self._write_jsonl(output, docs)
            return _step_ok("document_index", output)
        except Exception as e:
            return _step_fail("document_index", output, e)

    def _step_enriched_index(self, index_path: str) -> dict[str, Any]:
        output = os.path.join(self.output_dir, "enriched-index.jsonl")
        try:
            docs = self._load_jsonl(index_path)
            enricher = DocumentEnricher()
            enriched = enricher.enrich_records(docs, max_chars=self.max_chars, limit=self.max_enrich_pages)
            self._write_jsonl(output, enriched)
            return _step_ok("enriched_index", output)
        except Exception as e:
            return _step_fail("enriched_index", output, e)

    def _step_search(self, query: str, enriched_path: str) -> dict[str, Any]:
        output = os.path.join(self.output_dir, "search-results.json")
        try:
            searcher = KeywordSearcher(index_path=enriched_path)
            results = searcher.search(query, top_k=self.top_k)
            search_output = {
                "query": query,
                "top_k": self.top_k,
                "filters": {"category": "", "content_type": ""},
                "result_count": len(results),
                "results": results,
            }
            self._write_json(output, search_output)
            return _step_ok("search", output)
        except Exception as e:
            return _step_fail("search", output, e)

    def _step_answer(self, query: str, search_path: str) -> dict[str, Any]:
        output = os.path.join(self.output_dir, "answer.json")
        md_output = os.path.join(self.output_dir, "answer.md")
        try:
            search_data = self._load_json(search_path)
            composer = AnswerComposer(provider=self.provider, max_sources=self.max_sources)
            result = composer.compose(search_data, max_sources=self.max_sources)
            self._write_json(output, result)
            with open(md_output, "w", encoding="utf-8") as f:
                f.write(result.get("answer_markdown", ""))
            step = _step_ok("answer", output)
            step["markdown_output"] = md_output
            return step
        except Exception as e:
            step = _step_fail("answer", output, e)
            step["markdown_output"] = md_output
            return step

    # ------------------------------------------------------------------
    # Final result
    # ------------------------------------------------------------------

    def _final_result(
        self,
        url: str,
        query: str,
        steps: list[dict[str, Any]],
        overall_ok: bool,
        answer_markdown: str = "",
    ) -> dict[str, Any]:
        error = ""
        if not overall_ok:
            for s in steps:
                if not s["ok"]:
                    error = s["error"]
                    break

        result = {
            "ok": overall_ok,
            "url": url,
            "query": query,
            "output_dir": self.output_dir,
            "steps": steps,
            "answer_markdown": answer_markdown,
            "error": error,
        }
        pipeline_result_path = os.path.join(self.output_dir, "pipeline-result.json")
        self._write_json(pipeline_result_path, result)
        return result

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_json(path: str, data: Any) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _write_jsonl(path: str, records: list[dict]) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    @staticmethod
    def _load_json(path: str) -> Any:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _load_jsonl(path: str) -> list[dict]:
        docs = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    docs.append(json.loads(line))
        return docs


# ------------------------------------------------------------------
# Step result helpers
# ------------------------------------------------------------------

def _step_ok(name: str, output: str) -> dict[str, Any]:
    return {"name": name, "ok": True, "output": output, "error": ""}


def _step_fail(name: str, output: str, error: Exception) -> dict[str, Any]:
    return {"name": name, "ok": False, "output": output, "error": str(error)}


# ------------------------------------------------------------------
# Default output dir helper
# ------------------------------------------------------------------

def make_default_output_dir(base: str = "data/runs") -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return os.path.join(base, f"run-{timestamp}")
