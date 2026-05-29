"""SiteDemoRunner — grounded answer demo for a site profile.

Loads a site profile by site_id, runs the full pipeline
(→ homepage_map → document_index → enrich → search → answer),
and returns a structured result with sources.

Usage::

    runner = SiteDemoRunner(site_id="bukgu_gwangju", provider="mock")
    result = runner.answer("민원서식 어디서 받아?")
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any

from ..pipeline.pipeline_runner import PipelineRunner
from ..site_profiles import load_profile


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
        **pipeline_kwargs: Any,
    ) -> None:
        self.site_id = site_id
        self.provider = provider
        self._fetch_provider = fetch_provider
        self._output_dir = output_dir
        self._pipeline_kwargs = pipeline_kwargs

        # Load profile
        self.profile = load_profile(site_id)

        # Resolve fetch provider
        if self._fetch_provider is None:
            self._fetch_provider = self.profile.preferred_fetch_provider

    def answer(self, question: str, output_dir: str | None = None) -> dict[str, Any]:
        """Answer a natural-language question against the site profile.

        Args:
            question: The user's question (e.g. ``민원서식 어디서 받아?``).
            output_dir: Override output directory for this run.

        Returns:
            A dict with answer, sources, search_results, and metadata.

        Raises:
            ValueError: If question is empty.
        """
        if not question or not question.strip():
            raise ValueError("Question must not be empty")

        run_dir = output_dir or self._output_dir or tempfile.mkdtemp(prefix="demo_")

        runner = PipelineRunner(
            output_dir=run_dir,
            provider=self.provider,
            fetch_provider=self._fetch_provider,
            **self._pipeline_kwargs,
        )

        pipeline_result = runner.run(
            url=self.profile.base_url,
            query=question,
        )

        # Build the demo result
        demo_result = self._build_result(question, pipeline_result, run_dir)
        return demo_result

    # ------------------------------------------------------------------
    # Result builder
    # ------------------------------------------------------------------

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

        # Extract answer
        answer = ""
        answer_ok = False
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

        warnings: list[str] = []
        if not pipeline_result.get("ok", False):
            warnings.append(f"Pipeline partially failed: {pipeline_result.get('error', 'unknown')}")

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
            "fetch_provider": self._fetch_provider,
            "output_dir": run_dir,
            "fetched_at": now,
            "warnings": warnings,
        }


# ------------------------------------------------------------------
# Convenience function
# ------------------------------------------------------------------


def run_demo(
    site_id: str,
    question: str,
    provider: str = "mock",
    fetch_provider: str | None = None,
    output_dir: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """One-shot convenience function around SiteDemoRunner.

    Args:
        site_id: Site profile ID.
        question: Natural-language question.
        provider: LLM provider name (default: ``mock``).
        fetch_provider: Fetch provider name (default: from profile).
        output_dir: Output directory (default: temp dir).
        **kwargs: Additional PipelineRunner args.

    Returns:
        A dict with answer, sources, and metadata.
    """
    runner = SiteDemoRunner(
        site_id=site_id,
        provider=provider,
        fetch_provider=fetch_provider,
        output_dir=output_dir,
        **kwargs,
    )
    return runner.answer(question)
