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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from typing import Any

from src.fetch.compat_diagnostics import (
    FetchCategory,
    FetchDiagnostic,
    classify_exception,
    format_operator_safe,
)
from src.fetch.sanitization import safe_pipeline_failure_message, sanitize_warning

from ..pipeline.pipeline_runner import PipelineRunner
from ..site_profiles import load_profile


def _timeout_diagnostic(budget_s: float) -> FetchDiagnostic:
    """Build a :class:`FetchDiagnostic` for a budget-only timeout.

    Used when the pipeline worker is still running and there is no
    exception to classify. We surface the budget as part of the
    category but never as raw text — the ``short_reason`` is closed
    vocabulary.
    """
    # We keep the short_reason stable across budgets; callers that need
    # the exact number can read ``error`` from ``_build_timeout_pipeline_result``.
    return FetchDiagnostic(
        category=FetchCategory.TIMEOUT,
        short_reason="Request exceeded its deadline.",
        retry_hint="retry",
        is_transient=True,
    )
from src.answer.answer_status import normalize_answer_status
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


# Provider names that do not need a real LLM and therefore should not
# trigger router provider construction. Keeping router creation off for
# ``mock``/``stub`` ensures tests and demos using those providers do not
# need any external LLM configuration to run.
_NON_LIVE_LLM_PROVIDERS = frozenset({"mock", "stub", ""})


def _is_live_llm_provider(provider: str | None) -> bool:
    name = (provider or "").strip().lower()
    if not name or name in _NON_LIVE_LLM_PROVIDERS:
        return False
    return True


def _is_fallback_search_result(result: dict[str, Any]) -> bool:
    return (
        result.get("category") in {"navigation", "main"}
        or "홈페이지" in str(result.get("title", ""))
    )


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
        pipeline_timeout_s: float | None = None,
        **pipeline_kwargs: Any,
    ) -> None:
        self.site_id = site_id
        self.provider = provider
        self.model = model
        self._fetch_provider = fetch_provider
        self._output_dir = output_dir
        # Default budget: 30s for the entire pipeline run. When the upstream
        # site is unreachable or extremely slow (e.g. firewalled in offline
        # environments), exceeding this budget is treated as a soft failure:
        # the demo returns a structured JSON result instead of hanging.
        self._pipeline_timeout_s = (
            float(pipeline_timeout_s) if pipeline_timeout_s is not None else 30.0
        )
        self._pipeline_kwargs = pipeline_kwargs

        # Load profile
        self.profile = load_profile(site_id)

        # Resolve fetch provider
        if self._fetch_provider is None:
            self._fetch_provider = self.profile.preferred_fetch_provider

        # Router is created lazily so callers (especially tests) can inject
        # a mock provider by setting ``_router_provider`` after construction.
        # In production, ``_resolve_router()`` builds a real provider from
        # the same LLM factory used by the answer pipeline.
        self._router_provider: Any | None = None
        self._router_model: str | None = None
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
        pipeline_result, pipeline_warning, pipeline_diagnostic = (
            self._run_pipeline_with_timeout(
                run_dir=run_dir,
                search_query=search_query,
            )
        )

        # Build the demo result
        demo_result = self._build_result(
            question=question,
            pipeline_result=pipeline_result,
            run_dir=run_dir,
            router_decision=router_decision,
            pipeline_warning=pipeline_warning,
            pipeline_diagnostic=pipeline_diagnostic,
        )
        return demo_result

    def _run_pipeline_with_timeout(
        self,
        run_dir: str,
        search_query: str,
    ) -> tuple[dict[str, Any], str | None, FetchDiagnostic | None]:
        """Run the pipeline under a wall-clock budget.

        Returns ``(pipeline_result, warning, diagnostic)``.
        ``warning`` is ``None`` on a normal run and a short message
        when the pipeline exceeded ``self._pipeline_timeout_s`` or
        raised. ``diagnostic`` is a closed-vocabulary
        :class:`FetchDiagnostic` for any failure path (timeout, raised
        exception, or budget exhaustion) and ``None`` for normal runs.

        The pipeline runs on a single-thread executor so we can enforce a
        deadline without leaking threads. The executor is always closed via
        ``with``; on timeout the future is cancelled (best-effort — fetch
        sockets may continue in the background, but the demo response no
        longer blocks on them).
        """
        budget = self._pipeline_timeout_s

        def _execute() -> dict[str, Any]:
            runner = PipelineRunner(
                output_dir=run_dir,
                provider=self.provider,
                fetch_provider=self._fetch_provider,
                model=self.model,
                **self._pipeline_kwargs,
            )
            return runner.run(
                url=self.profile.base_url,
                query=search_query,
            )

        try:
            ex = ThreadPoolExecutor(max_workers=1)
            try:
                future = ex.submit(_execute)
                try:
                    pipeline_result = future.result(timeout=budget)
                    # Normal run: no warning, no diagnostic.
                    return pipeline_result, None, None
                except FuturesTimeout:
                    future.cancel()
                    # If the worker raised an exception before timing out,
                    # ``future.exception(timeout=0)`` carries its message —
                    # we surface that in the warning so operators can see
                    # *why* the pipeline failed, not just the budget number.
                    # The ``timeout=0`` is critical: a plain
                    # ``future.exception()`` would block on the still-running
                    # worker and re-introduce the exact hang the budget was
                    # meant to prevent.
                    #
                    # Stage #800: the warning itself must be operator-safe.
                    # We classify the exception into the seven-category
                    # taxonomy and emit only the diagnostic line — never the
                    # raw exception text. Raw exception text is not emitted
                    # to operator-facing output or application log surfaces;
                    # only the sanitized diagnostic is retained.
                    inner_exc: BaseException | None = None
                    try:
                        inner_exc = future.exception(timeout=0)
                    except FuturesTimeout:  # pragma: no cover - defensive
                        inner_exc = None
                    if inner_exc is not None:
                        diagnostic = classify_exception(inner_exc)
                        operator_safe = format_operator_safe(diagnostic)
                        warning = f"Pipeline raised: {operator_safe}"
                        # Stage #800 safety boundary: the log line carries
                        # ONLY the exception class name and the sanitized
                        # diagnostic. We never pass the raw exception object
                        # to the logger (no ``%r`` / ``str(e)`` / ``repr(e)``
                        # / ``exc_info=True``) because debug/warning logs can
                        # be persisted to files, CI logs, or shipped to
                        # downstream services, and exception ``__str__`` may
                        # embed URL fragments, headers, tokens, or body
                        # fragments we do not control.
                        log.warning(
                            "Pipeline raised during site_search fetch "
                            "(site_id=%s) exception_type=%s diagnostic=%s",
                            self.site_id,
                            type(inner_exc).__name__,
                            operator_safe,
                        )
                    else:
                        # Genuine budget timeout (worker still running).
                        # No exception to classify; emit a timeout-flavored
                        # diagnostic so the operator-facing warning carries
                        # a category.
                        diagnostic = _timeout_diagnostic(budget)
                        operator_safe = format_operator_safe(diagnostic)
                        warning = (
                            f"Pipeline timed out after {budget}s during "
                            f"site_search fetch: {operator_safe}"
                        )
                        log.warning("%s (site_id=%s)", warning, self.site_id)
                    pipeline_result = self._build_timeout_pipeline_result(
                        run_dir=run_dir,
                        search_query=search_query,
                        budget_s=budget,
                        diagnostic=diagnostic,
                    )
                    # Stage #801: surface the closed-vocabulary
                    # diagnostic so the caller can persist it alongside
                    # the user-facing warning.
                    return pipeline_result, warning, diagnostic
            finally:
                # ``wait=False`` so a still-running pipeline does not block
                # the demo response. The orphan thread may continue
                # performing fetches in the background but the user-facing
                # JSON has already been produced.
                ex.shutdown(wait=False)
        except Exception as e:  # noqa: BLE001 - never break the user response
            # Stage #800: route the exception through the diagnostic
            # taxonomy so the operator-facing warning and pipeline_result
            # never echo raw exception text, headers, bodies, or URLs.
            diagnostic = classify_exception(e)
            operator_safe = format_operator_safe(diagnostic)
            safe_error = f"Pipeline raised: {operator_safe}"
            pipeline_result = {
                "ok": False,
                "url": self.profile.base_url,
                "query": search_query,
                "output_dir": run_dir,
                "steps": [
                    {"name": "search", "ok": False, "output": "", "error": safe_error},
                    {"name": "answer", "ok": False, "output": "", "error": safe_error},
                ],
                "answer_markdown": "",
                "error": safe_error,
            }
            log.warning(
                "Pipeline raised during site_search fetch "
                "(site_id=%s) exception_type=%s diagnostic=%s",
                self.site_id,
                type(e).__name__,
                format_operator_safe(diagnostic),
            )
            # Stage #801: propagate the closed-vocabulary diagnostic
            # so ``answer()`` can attach it to the demo result and the
            # conversation log.
            return pipeline_result, safe_error, diagnostic

    def _build_timeout_pipeline_result(
        self,
        run_dir: str,
        search_query: str,
        budget_s: float,
        diagnostic: FetchDiagnostic | None = None,
    ) -> dict[str, Any]:
        """Synthesize a pipeline_result dict when the pipeline hits its budget.

        The shape matches what ``PipelineRunner.run`` would have produced so
        ``_build_result`` can consume it uniformly. We mark the search/answer
        steps as failed and surface the timeout reason via ``error``.

        Stage #800: the ``error`` field carries an operator-safe diagnostic
        line (never the raw exception text). When ``diagnostic`` is provided
        we surface its category; otherwise we fall back to the budget-only
        message plus a timeout diagnostic for downstream consumers.
        """
        if diagnostic is not None:
            operator_safe = format_operator_safe(diagnostic)
            msg = f"Pipeline timed out after {budget_s}s during site_search fetch: {operator_safe}"
        else:
            fallback = _timeout_diagnostic(budget_s)
            operator_safe = format_operator_safe(fallback)
            msg = f"Pipeline timed out after {budget_s}s during site_search fetch: {operator_safe}"
        return {
            "ok": False,
            "url": self.profile.base_url,
            "query": search_query,
            "output_dir": run_dir,
            "steps": [
                {"name": "search", "ok": False, "output": "", "error": msg},
                {"name": "answer", "ok": False, "output": "", "error": msg},
            ],
            "answer_markdown": "",
            "error": msg,
        }

    def _build_result(
        self,
        question: str,
        pipeline_result: dict[str, Any],
        run_dir: str,
        router_decision: RouterDecision | None = None,
        pipeline_warning: str | None = None,
        pipeline_diagnostic: FetchDiagnostic | None = None,
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

        if search_results and all(_is_fallback_search_result(r) for r in search_results):
            fallback_used = True

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
            if step.get("name") != "answer":
                continue
            if step.get("ok") is not True:
                break

            answer_path = step.get("output", "")
            if not isinstance(answer_path, str) or not answer_path.strip() or not os.path.exists(answer_path):
                break

            try:
                with open(answer_path, "r", encoding="utf-8") as f:
                    answer_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                break

            if not isinstance(answer_data, dict):
                answer_data = None
                break
            artifact_ok = answer_data.get("ok", True)
            if artifact_ok is not True:
                answer_data = None
                break

            markdown = answer_data.get("answer_markdown", "")
            if not isinstance(markdown, str) or not markdown.strip():
                answer_data = None
                break

            answer_ok = True
            answer = markdown
            break

        top_level_answer = pipeline_result.get("answer_markdown", "")
        if not isinstance(top_level_answer, str):
            top_level_answer = ""

        answer_has_content = bool(answer.strip())
        has_real_source = bool(sources) and not fallback_used
        pipeline_ok = bool(pipeline_result.get("ok", False))
        if not answer_ok or not answer_has_content:
            if pipeline_warning:
                # Surface the timeout in the user-visible answer too, so the
                # chat UI shows a clear "we couldn't reach the homepage right
                # now" message rather than the generic hint.
                site_label = self.profile.name or self.site_id
                answer = (
                    f"현재 공식 홈페이지 응답이 지연되어 상세 내용을 바로 확인하지 못했습니다. "
                    f"질문은 {site_label} 정보 검색 대상으로 분류되었고, "
                    f"다시 시도하거나 공식 홈페이지 접속이 가능한 환경에서 확인이 필요합니다."
                )
            elif pipeline_ok and not has_real_source and top_level_answer.strip():
                answer = top_level_answer
            else:
                answer = "제가 확인한 자료 기준으로는 관련 메뉴가 가장 먼저 필요해 보입니다. 아래 출처를 먼저 확인해 보세요."
            answer_ok = False

        evidence_answer = pipeline_ok and has_real_source and answer_ok and bool(answer.strip())

        # Stage #803: derive the closed-vocab ``answer_status`` and
        # reconcile ``answer_ok`` with evidence semantics.
        #
        # Contract:
        #   ok=true, answer_ok=true,  answer_status=answered_with_evidence
        #     → pipeline succeeded AND at least one non-fallback source
        #   ok=true, answer_ok=false, answer_status=fallback_no_match
        #     → pipeline succeeded but no real source (sources=[] or
        #       only homepage-map menu/navigation fallback was used)
        #   ok=false, answer_ok=false, answer_status=fallback_unavailable
        #     → pipeline timed out (diagnostic.category == "timeout")
        #   ok=false, answer_ok=false, answer_status=error
        #     → pipeline raised a non-timeout exception (any other
        #       closed-vocab fetch diagnostic category)
        #
        # We deliberately key off ``pipeline_diagnostic.category`` rather
        # than the truthiness of ``pipeline_warning`` so that exception
        # paths (which also produce a warning string for operator UI)
        # are still classified as ``error`` rather than as a timeout.
        if not pipeline_ok:
            answer_ok = False
            if (
                pipeline_diagnostic is not None
                and getattr(pipeline_diagnostic, "category", None) is not None
                and getattr(pipeline_diagnostic.category, "value", None) == "timeout"
            ):
                answer_status = "fallback_unavailable"
            else:
                answer_status = "error"
        elif evidence_answer:
            # Evidence-based: real retrieval source plus a usable composer answer.
            answer_ok = True
            answer_status = "answered_with_evidence"
        else:
            # sources=[] / fallback-only source / answer failure / blank answer.
            answer_ok = False
            answer_status = "fallback_no_match"

        if not pipeline_result.get("ok", False):
            warnings.append(safe_pipeline_failure_message(pipeline_diagnostic))

        # Surface the timeout/warning reported by the pipeline runner. We
        # prepend so it is the first thing operators see in the demo UI.
        if pipeline_warning:
            warnings.insert(0, sanitize_warning(pipeline_warning))

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
            "answer_status": answer_status,
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
            # source_weak is computed locally so callers always see the flag,
            # even before conversation_log serializes it. It is true whenever
            # a site_search response cannot be treated as an evidence-backed
            # answer: no real source, fallback-only source, answer failure, or
            # blank answer text.
            "source_weak": (
                router_decision.route == "site_search" and not evidence_answer
            ),
            # Stage #801: persist the closed-vocabulary fetch diagnostic
            # alongside the user-facing response so dashboards and the
            # conversation log can correlate ``source_weak`` with the
            # underlying fetch failure category (timeout, blocked,
            # tls_error, etc.) without ever echoing raw exception text.
            # On the normal / non-failure path the field is ``None``.
            "fetch_diagnostic": (
                pipeline_diagnostic.to_dict() if pipeline_diagnostic is not None else None
            ),
        }

    # ------------------------------------------------------------------
    # Router helpers
    # ------------------------------------------------------------------
    def _resolve_router(self) -> SiteSearchRouter | None:
        """Return a router for the current runner, building it lazily if needed.

        Resolution order:

        1. ``self.router`` (explicit injection, including tests).
        2. ``self._router_provider`` (injected LLM provider handle).
        3. If ``self.provider`` is a live LLM provider name (anything other
           than ``mock``/``stub``/empty), build a provider via
           ``src.llm.get_provider`` and wrap it in a ``SiteSearchRouter``.
        4. Otherwise return ``None`` so the caller falls back to the
           positive ``default_fallback_decision``.
        """
        if self.router is not None:
            return self.router

        if not _is_live_llm_provider(self.provider):
            # No router for non-live providers; tests that want a router
            # can still inject one explicitly via ``self.router = ...``.
            return None

        # Lazy import to avoid loading requests / config at import time
        from src.llm import get_provider  # noqa: WPS433 - lazy import

        try:
            router_provider = get_provider(self.provider, model=self.model)
        except Exception as e:  # noqa: BLE001 - never break the user response
            # Stage #800: never echo the raw exception into the log stream.
            # The class name plus a stable, closed-vocabulary tag keeps the
            # log useful without leaking provider response fragments that
            # exception ``__str__`` may carry.
            log.debug(
                "router provider build failed: exception_type=%s",
                type(e).__name__,
            )
            return None

        return SiteSearchRouter(
            provider=router_provider,
            model=self.model,
            site_name=self.profile.name,
        )

    def _decide_route(self, question: str) -> RouterDecision:
        """Return a RouterDecision using either the injected router, a
        lazily resolved router, or a positive default fallback.
        """
        if self.router is None:
            self.router = self._resolve_router()
        if self.router is not None:
            try:
                return self.router.decide(question)
            except Exception as e:  # noqa: BLE001
                # Stage #800: same boundary as above — never log the raw
                # exception message.
                log.debug(
                    "router decide raised: exception_type=%s",
                    type(e).__name__,
                )
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
            "answer_status": "answered_with_evidence",
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
            # source_weak is False for direct_answer / clarify because
            # the source-weak rule only applies to site_search (see
            # conversation_log._source_weak_flag). We set the key
            # explicitly so downstream consumers always see the flag.
            "source_weak": False,
            # Stage #801: direct_answer and clarify never invoke the
            # fetch pipeline, so there is no fetch diagnostic. We
            # set the field to ``None`` explicitly so callers and
            # conversation-log serialization can rely on the key
            # being present.
            "fetch_diagnostic": None,
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
