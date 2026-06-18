"""SiteDemoRunner — grounded answer demo for a site profile.

Loads a site profile by site_id, runs the full pipeline
(→ homepage_map → document_index → enrich → search → answer),
and returns a structured result with sources.
"""

from __future__ import annotations

import json
import logging
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
from src.llm.site_search_router import (
    SiteSearchRouter,
    RouterDecision,
    default_fallback_decision,
    greeting_fallback_direct_answer,
    clarify_fallback_direct_answer,
)


log = logging.getLogger(__name__)


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

        # Router is created lazily so callers (especially tests) can inject
        # a mock provider by setting ``_router_provider`` after construction.
        self._router_provider = None
        self._router_model = None
        self.router: SiteSearchRouter | None = None

    def answer(self, question: str, output_dir: str | None = None) -> dict[str, Any]:
        """Answer a natural-language question against the site profile."""
        if not question or not question.strip():
            raise ValueError("Question must not be empty")

        run_dir = output_dir or self._output_dir or tempfile.mkdtemp(prefix="demo_")

        # 1) LLM-first positive site-search router decides the route.
        router_decision = self._decide_route(question)

        # 2) Non-search routes short-circuit and skip the pipeline.
        if router_decision.route in ("direct_answer", "clarify"):
            return self._build_non_search_result(
                question=question,
                run_dir=run_dir,
                decision=router_decision,
            )

        # 3) site_search: run the pipeline with the router-supplied query.
        search_query = router_decision.search_query or question
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
                query=search_query,
            )
        except Exception as e:
            pipeline_result = {
                "ok": False,
                "url": self.profile.base_url,
                "query": search_query,
                "output_dir": run_dir,
                "steps": [
                    {"name": "search", "ok": False, "output": "", "error": str(e)},
                    {"name": "answer", "ok": False, "output": "", "error": str(e)},
                ],
                "answer_markdown": "",
                "error": str(e),
            }

        # Build the demo result
        demo_result = self._build_result(
            question=question,
            pipeline_result=pipeline_result,
            run_dir=run_dir,
            router_decision=router_decision,
        )
        return demo_result

    def _build_result(
        self,
        question: str,
        pipeline_result: dict[str, Any],
        run_dir: str,
        router_decision: RouterDecision | None = None,
    ) -> dict[str, Any]:
        """Build the final structured demo result dict."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if router_decision is None:
            router_decision = default_fallback_decision(question, self.profile.name)
        site_name = self.profile.name

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

        # Relaxed fallback: use a soft source hint only when there is no answer yet.
        # We do not block non-empty answers just because the provider returned
        # `answer_ok=false` or `ok=false`; we only substitute when the final
        # answer text is empty.
        if not answer:
            answer = "제가 확인한 자료 기준으로는 관련 메뉴가 가장 먼저 필요해 보입니다. 아래 출처를 먼저 확인해 보세요."
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
            "route": router_decision.route,
            "should_search_site": router_decision.should_search_site,
            "route_confidence": router_decision.confidence,
            "route_reason": router_decision.reason,
            "search_query": router_decision.search_query or question,
            "answer_mode": "retrieval_answer",
        }

    # ------------------------------------------------------------------
    # Router helpers
    # ------------------------------------------------------------------
    def _decide_route(self, question: str) -> RouterDecision:
        """Return a RouterDecision using either the injected router or a
        positive default fallback.
        """
        if self.router is not None:
            try:
                return self.router.decide(question)
            except Exception as e:  # noqa: BLE001
                log.debug("router decide raised: %s", e)
        return default_fallback_decision(question, self.profile.name)

    def _build_non_search_result(
        self,
        question: str,
        run_dir: str,
        decision: RouterDecision,
    ) -> dict[str, Any]:
        """Build a result for direct_answer or clarify routes (no pipeline)."""
        site_name = self.profile.name
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if decision.route == "direct_answer":
            answer_text = decision.direct_answer or greeting_fallback_direct_answer(site_name)
            answer_mode = "direct_answer"
        else:  # clarify
            answer_text = decision.direct_answer or clarify_fallback_direct_answer(site_name)
            answer_mode = "clarify"

        current_model = self.model or ""
        resolved_preset = resolve_preset_from_model_provider(self.provider, current_model)
        llm_status = resolve_llm_runtime_status(
            provider=self.provider,
            model=current_model,
            ok=True,
            answer_ok=True,
            warnings=[],
        )
        return {
            "site_id": self.site_id,
            "site_name": site_name,
            "question": question,
            "answer": answer_text,
            "sources": [],
            "search_results": [],
            "ok": True,
            "answer_ok": True,
            "provider": self.provider,
            "model": current_model,
            "preset": resolved_preset,
            "fetch_provider": self._fetch_provider,
            "output_dir": run_dir,
            "fetched_at": now,
            "fallback_used": False,
            "warnings": [],
            "llm_live": llm_status["llm_live"],
            "llm_status": llm_status["llm_status"],
            "llm_label": llm_status["llm_label"],
            "route": decision.route,
            "should_search_site": decision.should_search_site,
            "route_confidence": decision.confidence,
            "route_reason": decision.reason,
            "search_query": decision.search_query or "",
            "answer_mode": answer_mode,
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
