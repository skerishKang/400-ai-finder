"""SiteDemoRunner — grounded answer demo for a site profile.

Loads a site profile by site_id, runs the full pipeline
(→ homepage_map → document_index → enrich → search → answer),
and returns a structured result with sources.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any

from ..pipeline.pipeline_runner import PipelineRunner
from ..site_profiles import load_profile
from src.demo.demo_helpers import fallback_sources_from_homepage_map
from src.demo.metadata_helper import resolve_preset_from_model_provider
from src.demo.snapshot_helper import (
    save_snapshot as _save_snapshot,
    load_snapshot as _load_snapshot,
    answer_from_snapshot_helper,
)
from src.llm.runtime_status import resolve_llm_runtime_status


class SiteDemoRunner:
    """Run a pipeline demo against a site profile.

    Args:
        site_id: Site profile ID (e.g. ``bukgu_gwangju``).
        provider: LLM provider name (default: ``mock``).
        fetch_provider: Fetch provider name (default: from profile).
        output_dir: Pipeline output directory. If None, uses a temp dir.
        **pipeline_kwargs: Additional PipelineRunner args (top_k, max_sources, etc.).
    """

    def __init__(
        self,
        site_id: str,
        provider: str = "mock",
        fetch_provider: str | None = None,
        output_dir: str | None = None,
        model: str | None = None,
        **pipeline_kwargs: Any,
    ) -> None:
        self.site_id = site_id
        self.provider = provider
        self.model = model
        self._fetch_provider = fetch_provider
        self._output_dir = output_dir
        self._pipeline_kwargs = pipeline_kwargs

        # Load profile
        self.profile = load_profile(site_id)

        # Resolve fetch provider
        if self._fetch_provider is None:
            self._fetch_provider = self.profile.preferred_fetch_provider

    def answer(self, question: str, output_dir: str | None = None) -> dict[str, Any]:
        """Answer a natural-language question against the site profile."""
        if not question or not question.strip():
            raise ValueError("Question must not be empty")

        run_dir = output_dir or self._output_dir or tempfile.mkdtemp(prefix="demo_")

        try:
            runner = PipelineRunner(
                output_dir=run_dir,
                provider=self.provider,
                fetch_provider=self._fetch_provider,
                model=self.model,
                **self._pipeline_kwargs,
            )

            pipeline_result = runner.run(
                url=self.profile.base_url,
                query=question,
            )
        except Exception as e:
            pipeline_result = {
                "ok": False,
                "url": self.profile.base_url,
                "query": question,
                "output_dir": run_dir,
                "steps": [
                    {"name": "search", "ok": False, "output": "", "error": str(e)},
                    {"name": "answer", "ok": False, "output": "", "error": str(e)},
                ],
                "answer_markdown": "",
                "error": str(e),
            }

        # Build the demo result
        demo_result = self._build_result(question, pipeline_result, run_dir)
        return demo_result

    def _build_result(
        self,
        question: str,
        pipeline_result: dict[str, Any],
        run_dir: str,
    ) -> dict[str, Any]:
        """Build the final structured demo result dict."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Extract search results from pipeline output
        search_results: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        warnings: list[str] = []
        fallback_used = False

        for step in pipeline_result.get("steps", []):
            if step["name"] == "search" and step["ok"]:
                sp = step.get("output", "")
                if sp and os.path.exists(sp):
                    try:
                        with open(sp, "r", encoding="utf-8") as f:
                            search_data = json.load(f)
                        search_results = search_data.get("results", [])
                    except (json.JSONDecodeError, OSError):
                        pass
                break

        # Build sources from search results
        for r in search_results:
            source = {
                "title": r.get("title", r.get("text", "")),
                "url": r.get("url", ""),
                "source_type": r.get("category", "web"),
                "snippet": (r.get("text", "") or "")[:200],
                "score": r.get("score", 0),
            }
            sources.append(source)

        # Fallback: when search_results is empty, try homepage_map menu candidates
        if not search_results:
            homepage_map = self._load_homepage_map(run_dir)
            if homepage_map:
                fallback_candidates = fallback_sources_from_homepage_map(
                    homepage_map,
                    question,
                    self.profile.important_keywords,
                )
                for fc in fallback_candidates:
                    fallback_result = {
                        "id": f"fb-{len(search_results):05d}",
                        "title": fc["title"],
                        "url": fc["url"],
                        "canonical_url": fc["url"],
                        "category": fc.get("source_type", "menu"),
                        "content_type": "page",
                        "score": fc.get("score", 5.0),
                        "matched_terms": [],
                        "matched_fields": ["title", "metadata.link_texts"],
                        "snippet": fc["title"],
                        "metadata": {
                            "source_types": [fc.get("source_type", "menu")],
                            "fetch_status": "fallback",
                            "description": "Menu/navigation fallback from homepage map",
                        },
                    }
                    search_results.append(fallback_result)
                    sources.append({
                        "title": fc["title"],
                        "url": fc["url"],
                        "source_type": fc.get("source_type", "menu"),
                        "snippet": fc["title"][:200],
                        "score": fc.get("score", 5.0),
                    })

                if fallback_candidates:
                    fallback_used = True
                    warnings.append(
                        f"Search returned 0 results; used {len(fallback_candidates)} "
                        f"homepage map fallback candidates"
                    )

        # Extract answer
        answer = ""
        answer_ok = False
        answer_data = None
        for step in pipeline_result.get("steps", []):
            if step["name"] == "answer":
                answer_ok = step["ok"]
                if answer_ok:
                    ap = step.get("output", "")
                    if ap and os.path.exists(ap):
                        try:
                            with open(ap, "r", encoding="utf-8") as f:
                                answer_data = json.load(f)
                            answer = answer_data.get("answer_markdown", "")
                        except (json.JSONDecodeError, OSError):
                            pass
                break

        if not answer:
            answer = pipeline_result.get("answer_markdown", "")

        # Timeout/exception/pending error fallback handling
        if not answer_ok or not answer:
            answer = "현재 AI 답변을 생성할 수 없습니다. 잠시 후 다시 시도하거나 관련 홈페이지를 직접 확인해 주세요."
            answer_ok = False

        if not pipeline_result.get("ok", False):
            err_msg = pipeline_result.get("error", "unknown error")
            warnings.append(f"Pipeline partially failed: {err_msg}")

        # Resolve preset
        current_model = self.model or (answer_data.get("model", "") if answer_data else "")
        resolved_preset = resolve_preset_from_model_provider(self.provider, current_model)

        llm_status = resolve_llm_runtime_status(
            provider=self.provider,
            model=current_model,
            ok=pipeline_result.get("ok", False),
            answer_ok=answer_ok,
            warnings=warnings,
        )

        return {
            "site_id": self.site_id,
            "site_name": self.profile.name,
            "question": question,
            "answer": answer,
            "sources": sources,
            "search_results": search_results,
            "ok": pipeline_result.get("ok", False),
            "answer_ok": answer_ok,
            "provider": self.provider,
            "model": current_model,
            "preset": resolved_preset,
            "fetch_provider": self._fetch_provider,
            "output_dir": run_dir,
            "fetched_at": now,
            "fallback_used": fallback_used,
            "warnings": warnings,
            "llm_live": llm_status["llm_live"],
            "llm_status": llm_status["llm_status"],
            "llm_label": llm_status["llm_label"],
        }

    @staticmethod
    def _load_homepage_map(run_dir: str) -> dict[str, Any] | None:
        """Load homepage-map.json from the pipeline run directory."""
        path = os.path.join(run_dir, "homepage-map.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def save_snapshot(result: dict[str, Any], path: str) -> str:
        """Save a demo result dict as a reusable JSON snapshot."""
        return _save_snapshot(result, path)

    @staticmethod
    def load_snapshot(path: str) -> dict[str, Any]:
        """Load a demo result from a JSON snapshot file."""
        return _load_snapshot(path)

    def answer_from_snapshot(
        self,
        snapshot_path: str,
        question: str | None = None,
    ) -> dict[str, Any]:
        """Answer using a pre-saved snapshot instead of live pipeline."""
        return answer_from_snapshot_helper(self, snapshot_path, question)


def run_demo(
    site_id: str,
    question: str,
    provider: str = "mock",
    fetch_provider: str | None = None,
    output_dir: str | None = None,
    snapshot: str | None = None,
    save_snapshot: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """One-shot convenience function around SiteDemoRunner."""
    runner = SiteDemoRunner(
        site_id=site_id,
        provider=provider,
        fetch_provider=fetch_provider,
        output_dir=output_dir,
        **kwargs,
    )

    if snapshot:
        result = runner.answer_from_snapshot(snapshot, question=question)
    else:
        result = runner.answer(question)

    if save_snapshot:
        SiteDemoRunner.save_snapshot(result, save_snapshot)

    return result
