#!/usr/bin/env python3
"""validate_retrieval_gaps.py — Retrieval-only validation CLI for gap checks.

Retrieval-only design:

    - Runs pipeline stages up to search only (homepage map → document index →
      enrich → search).
    - Does NOT run _step_answer() / AnswerComposer.compose() / provider.complete().
    - Does NOT generate answer.md / answer.json.
    - Reports source counts, guard status, query rewrite metadata, and
      sanitized source summaries.

Safe defaults:

    - Default provider is ``mock``.
    - Default fetch provider is ``mock``.
    - Live fetch/network behavior requires explicit ``--allow-live`` plus
      an explicit non-mock provider or fetch provider.

Usage::

    # Offline validation:
    python scripts/validate_retrieval_gaps.py \
        --site-id bukgu_gwangju \
        --questions-file gap_questions.json

    # Live validation (explicit opt-in):
    python scripts/validate_retrieval_gaps.py \
        --site-id bukgu_gwangju \
        --questions-file gap_questions.json \
        --allow-live \
        --fetch-provider requests
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Safety constants
# ---------------------------------------------------------------------------

_OFFLINE_LLM_PROVIDERS = frozenset({"mock", "stub"})
_OFFLINE_FETCH_PROVIDERS = frozenset({"mock"})

_REQUIRED_REPORT_FIELDS = {
    "question",
    "site_id",
    "ok",
    "error",
    "source_count",
    "guard_status",
    "guard_reason",
    "top_sources",
    "query_rewrite",
}

_REQUIRED_SOURCE_FIELDS = {"title", "url", "category", "content_type", "score"}

_PROHIBITED_REPORT_FIELDS = {
    "full_text",
    "text",
    "prompt",
    "raw_provider_response",
    "api_key",
    "secret",
    "cookie",
    "authorization",
    "auth_header",
}

# Answer-generation fields that must not appear in validation reports.
_ANSWER_GENERATION_FIELDS = {
    "answer",
    "answer_markdown",
    "answer_md",
    "prompt",
    "messages",
    "raw_provider_response",
    "provider_response",
    "completion",
    "full_text",
    "text",
}


# ---------------------------------------------------------------------------
# Guard helpers
# ---------------------------------------------------------------------------


def _requires_live_opt_in(provider: str | None, fetch_provider: str | None) -> bool:
    if provider not in _OFFLINE_LLM_PROVIDERS:
        return True
    if fetch_provider not in _OFFLINE_FETCH_PROVIDERS:
        return True
    return False


def _enforce_live_opt_in(
    parser_or_provider: Any,
    *,
    provider: str | None,
    fetch_provider: str | None,
    allow_live: bool,
) -> None:
    # Avoid argparse coupling: accept argparse parser or string msg.
    if allow_live:
        return
    if not _requires_live_opt_in(provider=provider, fetch_provider=fetch_provider):
        return
    msg = (
        "validate_retrieval_gaps.py may execute live provider/fetch/network/API paths. "
        "Pass --allow-live to opt in explicitly, or use --provider mock "
        "and --fetch-provider mock for offline/no-network execution."
    )
    if hasattr(parser_or_provider, "error"):
        parser_or_provider.error(msg)
    raise SystemExit(msg)


# ---------------------------------------------------------------------------
# Questions file parsing / validation
# ---------------------------------------------------------------------------


def load_questions_file(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        print(f"Error reading questions file: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Malformed questions file (invalid JSON): {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict):
        print("Malformed questions file: root must be a JSON object.", file=sys.stderr)
        sys.exit(1)

    if "questions" not in data:
        print("Malformed questions file: missing 'questions' key.", file=sys.stderr)
        sys.exit(1)

    questions = data["questions"]
    if not isinstance(questions, list):
        print("Malformed questions file: 'questions' must be a list.", file=sys.stderr)
        sys.exit(1)

    if not questions:
        print("Malformed questions file: 'questions' list is empty.", file=sys.stderr)
        sys.exit(1)

    validated: list[str] = []
    for idx, item in enumerate(questions):
        if not isinstance(item, str) or not item.strip():
            print(
                f"Malformed questions file: item {idx} is not a non-empty string.",
                file=sys.stderr,
            )
            sys.exit(1)
        validated.append(item.strip())

    return validated


# ---------------------------------------------------------------------------
# Report sanitization
# ---------------------------------------------------------------------------


def sanitize_sources(search_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for result in search_results:
        source: dict[str, Any] = {
            "title": (result.get("title") or "")[:200],
            "url": result.get("url") or result.get("canonical_url", ""),
            "category": result.get("category", ""),
            "content_type": result.get("content_type", ""),
            "score": result.get("score", 0.0),
        }
        cleaned.append(source)
    return cleaned


def _assert_no_answer_fields(report: dict[str, Any]) -> None:
    extra = _ANSWER_GENERATION_FIELDS & set(report.keys())
    if extra:
        raise ValueError(
            f"Validation report must not contain answer-generation fields: {sorted(extra)}"
        )


def build_validation_report(
    *,
    site_id: str,
    question: str,
    ok: bool,
    error: str | None,
    source_count: int,
    guard_status: str | None,
    guard_reason: str | None,
    search_results: list[dict[str, Any]],
    query_rewrite: dict[str, Any] | None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "question": question,
        "site_id": site_id,
        "ok": ok,
        "error": error or "",
        "source_count": source_count,
        "guard_status": guard_status,
        "guard_reason": guard_reason or "",
        "top_sources": sanitize_sources(search_results),
        "query_rewrite": {
            "queries": list((query_rewrite or {}).get("queries", [])),
            "site_id": (query_rewrite or {}).get("site_id"),
            "strategy": (query_rewrite or {}).get("strategy"),
            "warnings": list((query_rewrite or {}).get("warnings", [])),
        },
    }

    missing = _REQUIRED_REPORT_FIELDS - set(report.keys())
    if missing:
        raise ValueError(f"Report missing required fields: {missing}")

    extra = _PROHIBITED_REPORT_FIELDS & set(report.keys())
    if extra:
        raise ValueError(f"Report contains prohibited fields: {extra}")

    _assert_no_answer_fields(report)
    return report


# ---------------------------------------------------------------------------
# Retrieval-only pipeline execution
# ---------------------------------------------------------------------------


def _retrieval_only(
    *,
    site_id: str,
    question: str,
    provider: str | None = None,
    model: str | None = None,
    fetch_provider: str | None = None,
    top_k: int = 5,
    max_sources: int = 5,
    max_chars: int = 12000,
    max_enrich_pages: int = 20,
) -> dict[str, Any]:
    """Run retrieval stages only (up to search).

    This never invokes AnswerComposer or any provider .complete() call.
    """
    try:
        from src.site_profiles import load_profile
        from src.pipeline.pipeline_runner import PipelineRunner
        from src.answer.answer_composer import AnswerComposer
        from src.search.source_match_guard import assess_source_match
    except Exception as e:  # pragma: no cover - import safety fallback
        return {
            "ok": False,
            "error": f"Import error during retrieval setup: {e}",
            "search_results": [],
            "sources": [],
            "query_rewrite": None,
            "guard_status": "error",
            "guard_reason": str(e),
        }

    try:
        profile = load_profile(site_id)
        url = profile.base_url
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to load site profile '{site_id}': {e}",
            "search_results": [],
            "sources": [],
            "query_rewrite": None,
            "guard_status": "error",
            "guard_reason": str(e),
        }

    run_dir = tempfile.mkdtemp(prefix="validate_gaps_")
    try:
        runner = PipelineRunner(
            output_dir=run_dir,
            provider=provider or "mock",
            fetch_provider=fetch_provider,
            max_chars=max_chars,
            max_enrich_pages=max_enrich_pages,
            top_k=top_k,
            max_sources=max_sources,
            model=model,
        )

        # Stage 1-4 only. Intentionally skip _step_answer() / AnswerComposer.
        step_map = runner._step_homepage_map(url)
        if not step_map["ok"]:
            return {
                "ok": False,
                "error": step_map.get("error", "homepage_map failed"),
                "search_results": [],
                "sources": [],
                "query_rewrite": None,
                "guard_status": "error",
                "guard_reason": step_map.get("error", "homepage_map failed"),
            }

        homepage_map = runner._load_json(step_map["output"])
        step_index = runner._step_document_index(homepage_map)
        if not step_index["ok"]:
            return {
                "ok": False,
                "error": step_index.get("error", "document_index failed"),
                "search_results": [],
                "sources": [],
                "query_rewrite": None,
                "guard_status": "error",
                "guard_reason": step_index.get("error", "document_index failed"),
            }

        step_enrich = runner._step_enriched_index(step_index["output"])
        if not step_enrich["ok"]:
            return {
                "ok": False,
                "error": step_enrich.get("error", "enriched_index failed"),
                "search_results": [],
                "sources": [],
                "query_rewrite": None,
                "guard_status": "error",
                "guard_reason": step_enrich.get("error", "enriched_index failed"),
            }

        step_search = runner._step_search(
            query=question,
            enriched_path=step_enrich["output"],
            site_id=site_id,
        )
        if not step_search["ok"]:
            return {
                "ok": False,
                "error": step_search.get("error", "search failed"),
                "search_results": [],
                "sources": [],
                "query_rewrite": None,
                "guard_status": "error",
                "guard_reason": step_search.get("error", "search failed"),
            }

        search_path = step_search["output"]
        search_data = runner._load_json(search_path)
        search_results = search_data.get("results", [])
        query_rewrite = search_data.get("query_rewrite")

        # Extract sources without invoking AnswerComposer.compose().
        sources = AnswerComposer._extract_sources(search_results, max_sources=max_sources)
        source_count = len(sources)

        if source_count == 0:
            guard_status = "no_results"
            guard_reason = "No sources retrieved."
        else:
            assessment = assess_source_match(
                question,
                sources,
                query_rewrite_queries=(query_rewrite or {}).get("queries", []),
            )
            guard_status = assessment.status
            guard_reason = assessment.reason or ""

        return {
            "ok": True,
            "error": "",
            "search_results": search_results,
            "sources": sources,
            "query_rewrite": query_rewrite,
            "source_count": source_count,
            "guard_status": guard_status,
            "guard_reason": guard_reason,
        }
    finally:
        try:
            for name in os.listdir(run_dir):
                os.remove(os.path.join(run_dir, name))
            os.rmdir(run_dir)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Public validation API used by CLI / tests
# ---------------------------------------------------------------------------


def validate_question(
    *,
    site_id: str,
    question: str,
    provider: str | None = None,
    model: str | None = None,
    fetch_provider: str | None = None,
    allow_live: bool = False,
    top_k: int = 5,
    max_sources: int = 5,
) -> dict[str, Any]:
    if not allow_live and _requires_live_opt_in(
        provider=provider,
        fetch_provider=fetch_provider,
    ):
        return build_validation_report(
            site_id=site_id,
            question=question,
            ok=False,
            error="Live validation requires --allow-live.",
            source_count=0,
            guard_status="blocked",
            guard_reason="--allow-live not set.",
            search_results=[],
            query_rewrite=None,
        )

    pipeline_out = _retrieval_only(
        site_id=site_id,
        question=question,
        provider=provider,
        model=model,
        fetch_provider=fetch_provider,
        top_k=top_k,
        max_sources=max_sources,
    )

    return build_validation_report(
        site_id=site_id,
        question=question,
        ok=pipeline_out["ok"],
        error=pipeline_out.get("error", ""),
        source_count=pipeline_out.get("source_count", 0),
        guard_status=pipeline_out.get("guard_status"),
        guard_reason=pipeline_out.get("guard_reason", ""),
        search_results=pipeline_out.get("sources", []),
        query_rewrite=pipeline_out.get("query_rewrite"),
    )


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------


def write_json_report(report: dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def write_text_report(report: dict[str, Any], path: str) -> None:
    lines: list[str] = []
    lines.append(f"Question : {report.get('question', '')}")
    lines.append(f"Site     : {report.get('site_id', '')}")
    lines.append(f"OK       : {report.get('ok', False)}")
    lines.append(f"Error    : {report.get('error', '')}")
    lines.append(f"Sources  : {report.get('source_count', 0)}")
    lines.append(f"Guard    : {report.get('guard_status', '')}")
    lines.append(f"Reason   : {report.get('guard_reason', '')}")
    lines.append("")

    query_rewrite = report.get("query_rewrite") or {}
    lines.append(f"Queries  : {', '.join(query_rewrite.get('queries', []))}")
    lines.append(f"Strategy : {query_rewrite.get('strategy', '')}")
    lines.append("")

    sources = report.get("top_sources", [])
    if sources:
        lines.append("Top sources:")
        for i, src in enumerate(sources[:5], 1):
            lines.append(f"  [{i}] {src.get('title', '')}")
            lines.append(f"       URL      : {src.get('url', '')}")
            lines.append(f"       Category : {src.get('category', '')}")
            lines.append(f"       Type     : {src.get('content_type', '')}")
            lines.append(f"       Score    : {src.get('score', 0.0)}")
    else:
        lines.append("Top sources: (none)")

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Controlled live validation CLI for retrieval-gap checks.",
    )
    parser.add_argument(
        "--site-id",
        required=True,
        help="Site profile ID (e.g. bukgu_gwangju)",
    )
    parser.add_argument(
        "--questions-file",
        required=True,
        help="Path to JSON file with a 'questions' array",
    )
    parser.add_argument(
        "--provider",
        default="mock",
        help="LLM provider name (default: mock)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="LLM model name/ID (default: None)",
    )
    parser.add_argument(
        "--fetch-provider",
        default="mock",
        help="Fetch provider name (default: mock)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Search top_k (default: 5)",
    )
    parser.add_argument(
        "--max-sources",
        type=int,
        default=5,
        help="Max sources to retain in report (default: 5)",
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "text"],
        default="json",
        help="Report output format (default: json)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the report JSON or text (default: stdout)",
    )
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help=(
            "Allow validate_retrieval_gaps.py to execute live provider/fetch/network "
            "paths. Without this flag, only offline mock/stub paths are allowed."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if not args.allow_live and _requires_live_opt_in(
        provider=args.provider,
        fetch_provider=args.fetch_provider,
    ):
        print(
            "validate_retrieval_gaps.py may execute live provider/fetch/network/API paths. "
            "Pass --allow-live to opt in explicitly, or use --provider mock "
            "and --fetch-provider mock for offline/no-network execution.",
            file=sys.stderr,
        )
        sys.exit(1)

    questions = load_questions_file(args.questions_file)

    aggregated: dict[str, Any] = {
        "site_id": args.site_id,
        "allow_live": args.allow_live,
        "provider": args.provider,
        "model": args.model,
        "fetch_provider": args.fetch_provider,
        "questions": [],
    }

    for question in questions:
        report = validate_question(
            site_id=args.site_id,
            question=question,
            provider=args.provider,
            model=args.model,
            fetch_provider=args.fetch_provider,
            allow_live=args.allow_live,
            top_k=args.top_k,
            max_sources=args.max_sources,
        )
        aggregated["questions"].append(report)

    if args.output:
        if args.output_format == "json":
            write_json_report(aggregated, args.output)
        else:
            lines: list[str] = []
            lines.append(f"Site   : {aggregated.get('site_id', '')}")
            lines.append(f"Live   : {aggregated.get('allow_live', False)}")
            lines.append("")
            for q_report in aggregated.get("questions", []):
                lines.append(f"Q: {q_report.get('question', '')}")
                lines.append(f"  Sources : {q_report.get('source_count', 0)}")
                lines.append(f"  Guard   : {q_report.get('guard_status', '')}")
                lines.append(f"  Reason  : {q_report.get('guard_reason', '')}")
                lines.append("")
            os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        print(f"Report written to: {args.output}")
    else:
        if args.output_format == "json":
            print(json.dumps(aggregated, ensure_ascii=False, indent=2))
        else:
            lines = []
            lines.append(f"Site   : {aggregated.get('site_id', '')}")
            lines.append(f"Live   : {aggregated.get('allow_live', False)}")
            lines.append("")
            for q_report in aggregated.get("questions", []):
                lines.append(f"Q: {q_report.get('question', '')}")
                lines.append(f"  Sources : {q_report.get('source_count', 0)}")
                lines.append(f"  Guard   : {q_report.get('guard_status', '')}")
                lines.append(f"  Reason  : {q_report.get('guard_reason', '')}")
                lines.append("")
            print("\n".join(lines))


if __name__ == "__main__":
    main()
