"""PipelineRunner — orchestrates Stage 2-6 into a single end-to-end run.

Usage::

    runner = PipelineRunner(output_dir="data/runs/example", provider="mock")
    result = runner.run(url="https://example.com", query="신청서 제출서류")
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any

from ..crawler.homepage_mapper import HomepageMapper
from ..indexer.document_indexer import DocumentIndexer
from ..indexer.document_enricher import DocumentEnricher
from ..search.keyword_searcher import KeywordSearcher
from ..search.query_rewriter import rewrite_query_candidates
from ..answer.answer_composer import AnswerComposer
from ..analytics.question_logger import QuestionLogger, NoOpQuestionLogger
from ..fetch.sanitization import safe_failure_message
from ..observability import get_event_logger, log_pipeline_event, new_correlation_id


class PipelineRunner:
    """Orchestrates the full search-and-answer pipeline."""

    def __init__(
        self,
        output_dir: str,
        provider: str | None = None,
        fetch_provider: str | None = None,
        max_sitemap_urls: int = 200,
        max_sitemaps: int = 10,
        max_enrich_pages: int = 20,
        top_k: int = 5,
        max_sources: int = 5,
        max_chars: int = 12000,
        model: str | None = None,
        question_logger: QuestionLogger | None = None,
    ):
        self.output_dir = output_dir
        self.provider = provider or "mock"
        self.model = model
        self.fetch_provider = fetch_provider  # None = original behavior
        self.max_sitemap_urls = max_sitemap_urls
        self.max_sitemaps = max_sitemaps
        self.max_enrich_pages = max_enrich_pages
        self.top_k = top_k
        self.max_sources = max_sources
        self.max_chars = max_chars
        self.question_logger = question_logger or NoOpQuestionLogger()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, url: str, query: str, correlation_id: str | None = None) -> dict[str, Any]:
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
        event_logger = get_event_logger(__name__)
        run_correlation_id = correlation_id if correlation_id is not None else new_correlation_id()
        run_started_at = time.perf_counter()
        final_result: dict[str, Any] | None = None

        # Stage 369: resolve site_id once per run so it can be forwarded
        # to query rewrite and question logging consistently.
        site_id = self._resolve_site_id(url)

        def _duration_ms(started_at: float) -> int:
            return int((time.perf_counter() - started_at) * 1000)

        def _log_stage_start(stage: str) -> float:
            started_at = time.perf_counter()
            log_pipeline_event(
                event_logger,
                event="pipeline_stage_start",
                correlation_id=run_correlation_id,
                stage=stage,
                site_id=site_id,
            )
            return started_at

        def _log_stage_end(stage: str, started_at: float, ok: bool) -> None:
            event_name = "pipeline_stage_end" if ok else "pipeline_stage_fail"
            kwargs: dict[str, Any] = {}
            if not ok:
                kwargs["failure_code"] = "pipeline_step_failed"
            log_pipeline_event(
                event_logger,
                event=event_name,
                correlation_id=run_correlation_id,
                stage=stage,
                ok=ok,
                duration_ms=_duration_ms(started_at),
                site_id=site_id,
                **kwargs,
            )

        log_pipeline_event(
            event_logger,
            event="pipeline_run_start",
            correlation_id=run_correlation_id,
            site_id=site_id,
        )

        try:
            # Step 1 — homepage map
            stage_started_at = _log_stage_start("homepage_map")
            step = self._step_homepage_map(url, correlation_id=run_correlation_id)
            steps.append(step)
            _log_stage_end("homepage_map", stage_started_at, step["ok"])
            if not step["ok"]:
                final_result = self._final_result(url, query, steps, overall_ok=False)
                return final_result

            homepage_map = self._load_json(step["output"])

            # Step 2 — document index
            stage_started_at = _log_stage_start("document_index")
            step = self._step_document_index(homepage_map)
            steps.append(step)
            _log_stage_end("document_index", stage_started_at, step["ok"])
            if not step["ok"]:
                final_result = self._final_result(url, query, steps, overall_ok=False)
                return final_result

            # Step 3 — enriched index
            stage_started_at = _log_stage_start("enriched_index")
            step = self._step_enriched_index(step["output"])
            steps.append(step)
            _log_stage_end("enriched_index", stage_started_at, step["ok"])
            if not step["ok"]:
                final_result = self._final_result(url, query, steps, overall_ok=False)
                return final_result

            # Step 4 — search
            stage_started_at = _log_stage_start("search")
            step = self._step_search(query, step["output"], site_id=site_id)
            steps.append(step)
            _log_stage_end("search", stage_started_at, step["ok"])
            if not step["ok"]:
                final_result = self._final_result(url, query, steps, overall_ok=False)
                return final_result

            # Step 5 — answer
            stage_started_at = _log_stage_start("answer")
            step = self._step_answer(query, step["output"])
            steps.append(step)
            _log_stage_end("answer", stage_started_at, step["ok"])

            # Emit question log event
            self._emit_question_log(
                url,
                query,
                steps,
                site_id=site_id,
                correlation_id=run_correlation_id,
            )

            if not step["ok"]:
                final_result = self._final_result(url, query, steps, overall_ok=False)
                return final_result

            answer_markdown = self._load_json(step["output"]).get("answer_markdown", "")
            final_result = self._final_result(
                url,
                query,
                steps,
                overall_ok=True,
                answer_markdown=answer_markdown,
            )
            return final_result
        finally:
            ok = bool(final_result and final_result.get("ok"))
            log_pipeline_event(
                event_logger,
                event="pipeline_run_end",
                correlation_id=run_correlation_id,
                ok=ok,
                duration_ms=_duration_ms(run_started_at),
            )

    def _emit_question_log(
        self,
        url: str,
        query: str,
        steps: list[dict[str, Any]],
        site_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Helper to build and log the QuestionLogEvent after a run."""
        try:
            from ..analytics.question_logger import build_question_log_event

            # Resolve site_id from url if not already provided.
            if site_id is None:
                site_id = self._resolve_site_id(url)

            # Find search step output
            search_data = {}
            for step in steps:
                if step.get("name") == "search" and step.get("ok"):
                    search_data = self._load_json(step["output"])
                    break

            # Find answer step output
            answer_data = {}
            answer_ok = False
            for step in steps:
                if step.get("name") == "answer":
                    answer_ok = step.get("ok", False)
                    if answer_ok:
                        answer_data = self._load_json(step["output"])
                    break

            # Determine statuses
            answer_status = "success" if answer_ok else "error"
            if answer_data.get("guard_status") == "no_results":
                answer_status = "no_results"

            fallback_used = False
            for res in search_data.get("results", []):
                if res.get("category") in ("navigation", "main") or "홈페이지" in res.get("title", ""):
                    fallback_used = True
                    break

            event = build_question_log_event(
                site_id=site_id,
                question=query,
                provider_mode=self.provider,
                retrieval_mode="live" if self.fetch_provider else "snapshot",
                query_rewrite=search_data.get("query_rewrite"),
                search_results=search_data.get("results", []),
                sources=answer_data.get("sources", []),
                answer_status=answer_status,
                fallback_used=fallback_used,
                guard_status=answer_data.get("guard_status"),
                guard_reason=answer_data.get("guard_reason"),
                warnings=answer_data.get("warnings", []),
                correlation_id=correlation_id,
            )
            self.question_logger.log(event)
        except Exception:
            # Silently ignore errors during logging to prevent pipeline crash
            pass


    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    def _resolve_site_id(self, url: str) -> str | None:
        """Resolve a site_id for a URL using configured site profiles.

        Returns None if no profile matches or loading fails. Never raises.
        """
        try:
            from ..site_profiles.site_profile import SiteProfileLoader
            loader = SiteProfileLoader()
            for sid in loader.list_ids():
                try:
                    p = loader.load_by_id(sid)
                    if p.match_url(url):
                        return p.site_id
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def _step_homepage_map(self, url: str, correlation_id: str | None = None) -> dict[str, Any]:
        output = os.path.join(self.output_dir, "homepage-map.json")
        try:
            # Stage 391: Resolve site profile to pass crawl_filters to HomepageMapper
            crawl_filters = None
            site_id = self._resolve_site_id(url)
            if site_id:
                try:
                    from ..site_profiles.site_profile import SiteProfileLoader
                    loader = SiteProfileLoader()
                    profile = loader.load_by_id(site_id)
                    crawl_filters = profile.crawl_filters
                except Exception:
                    pass

            # Stage 36: retry build_map if nav links are empty (intermittent timeouts)
            max_retries = 2
            result = None
            for attempt in range(max_retries):
                mapper = HomepageMapper(
                    max_sitemaps=self.max_sitemaps,
                    max_sitemap_urls=self.max_sitemap_urls,
                    fetch_provider=self.fetch_provider,
                    crawl_filters=crawl_filters,
                )
                result = mapper.build_map(url, correlation_id=correlation_id)
                nav_count = len(result.get("homepage", {}).get("navigation_links", []))
                if nav_count > 0 or attempt == max_retries - 1:
                    break
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

    def _step_search(
        self,
        query: str,
        enriched_path: str,
        site_id: str | None = None,
    ) -> dict[str, Any]:
        output = os.path.join(self.output_dir, "search-results.json")
        try:
            searcher = KeywordSearcher(index_path=enriched_path)

            # Use query rewriter to get retrieval candidates.
            # Stage 369: forward site_id so site-specific synonym
            # dictionaries can be applied to retrieval term expansion.
            rewrite_result = rewrite_query_candidates(
                query,
                site_id=site_id,
                max_queries=self.top_k,
            )
            query_candidates = list(rewrite_result.queries)

            # Run search for each query candidate and merge results
            all_results = self._search_for_candidates(searcher, query_candidates)

            search_output = {
                "query": query,
                "top_k": self.top_k,
                "filters": {"category": "", "content_type": ""},
                "result_count": len(all_results),
                "results": all_results,
                "query_rewrite": {
                    "strategy": rewrite_result.strategy,
                    "original_question": rewrite_result.original_question,
                    "queries": list(rewrite_result.queries),
                    "warnings": list(rewrite_result.warnings),
                    "site_id": site_id,
                },
            }
            self._write_json(output, search_output)
            return _step_ok("search", output)
        except Exception as e:
            return _step_fail("search", output, e)

    def _search_for_candidates(
        self, searcher: KeywordSearcher, query_candidates: list[str]
    ) -> list[dict[str, Any]]:
        """Run search for each query candidate and merge results.

        Args:
            searcher: Initialized KeywordSearcher instance.
            query_candidates: List of query strings to search for.

        Returns:
            Merged and deduplicated results (by canonical_url).
        """
        all_results = []
        seen_urls = set()

        for q in query_candidates:
            results = searcher.search(q, top_k=self.top_k)
            for result in results:
                canon_url = result.get("canonical_url") or result.get("url", "")
                if canon_url and canon_url not in seen_urls:
                    seen_urls.add(canon_url)
                    all_results.append(result)

        # Sort by score descending, then by canonical_url for determinism
        all_results.sort(key=lambda r: (-r.get("score", 0), r.get("canonical_url", "")))

        # Limit to top_k
        if len(all_results) > self.top_k:
            all_results = all_results[:self.top_k]

        # Re-assign ranks
        for rank, res in enumerate(all_results, start=1):
            res["rank"] = rank

        return all_results

    def _step_answer(self, query: str, search_path: str) -> dict[str, Any]:
        output = os.path.join(self.output_dir, "answer.json")
        md_output = os.path.join(self.output_dir, "answer.md")
        try:
            search_data = self._load_json(search_path)
            composer = AnswerComposer(
                provider=self.provider,
                max_sources=self.max_sources,
                model=self.model,
            )
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
    safe_error = safe_failure_message(error, prefix="Pipeline step failed")
    return {"name": name, "ok": False, "output": output, "error": safe_error}


# ------------------------------------------------------------------
# Default output dir helper
# ------------------------------------------------------------------

def make_default_output_dir(base: str = "data/runs") -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return os.path.join(base, f"run-{timestamp}")
