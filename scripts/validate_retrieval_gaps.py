#!/usr/bin/env python3
"""validate_retrieval_gaps.py — Controlled live validation CLI for retrieval-gap checks.

Usage::

    # Offline validation (no live fetch/pipeline):
    python scripts/validate_retrieval_gaps.py \
        --site-id bukgu_gwangju \
        --questions-file gap_questions.json

    # Live validation (requires explicit --allow-live):
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
from typing import Any

# Ensure project root is on sys.path
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
    parser: argparse.ArgumentParser,
    *,
    provider: str | None,
    fetch_provider: str | None,
    allow_live: bool,
) -> None:
    if allow_live:
        return
    if not _requires_live_opt_in(provider=provider, fetch_provider=fetch_provider):
        return
    parser.error(
        "validate_retrieval_gaps.py may execute live provider/fetch/network/API paths. "
        "Pass --allow-live to opt in explicitly, or use --provider mock "
        "and --fetch-provider mock for offline/no-network execution."
    )


# ---------------------------------------------------------------------------
# Questions file parsing / validation
# ---------------------------------------------------------------------------


def load_questions_file(path: str) -> list[str]:
    """Load and validate a questions JSON file.

    Raises SystemExit on any validation failure.
    """
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
        print(
            "Malformed questions file: root must be a JSON object.",
            file=sys.stderr,
        )
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
    """Keep only stable, non-sensitive metadata from search results."""
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
    """Build a single-question validation report with safe metadata only."""
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

    # Sanity check: required fields
    missing = _REQUIRED_REPORT_FIELDS - set(report.keys())
    if missing:
        raise ValueError(f"Report missing required fields: {missing}")

    # Sanity check: prohibited fields
    extra = _PROHIBITED_REPORT_FIELDS & set(report.keys())
    if extra:
        raise ValueError(f"Report contains prohibited fields: {extra}")

    return report


# ---------------------------------------------------------------------------
# Single-question validation logic (pure + testable)
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
    """Run one validation question through the pipeline and return a report.

    This function intentionally does NOT generate or return LLM answers.
    It only returns retrieval metadata: sources, guard status, query rewrite.
    """
    # SAFETY: require explicit opt-in before any live execution path
    if not allow_live and _requires_live_opt_in(
        provider=provider, fetch_provider=fetch_provider
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

    try:
        from src.demo import SiteDemoRunner
        from src.pipeline.pipeline_runner import PipelineRunner

        runner = SiteDemoRunner(
            site_id=site_id,
            provider=provider or "mock",
            model=model,
            fetch_provider=fetch_provider,
            top_k=top_k,
            max_sources=max_sources,
        )

        # Use the pipeline directly to avoid answering; we only need retrieval data
        pipeline_result = runner.answer(question)
        search_results = pipeline_result.get("search_results", [])
        sources = pipeline_result.get("sources", [])
        warnings = pipeline_result.get("warnings", [])
        fallback_used = pipeline_result.get("fallback_used", False)

        # Determine guard status from answer stage or fallback signal
        if not search_results and not sources:
            guard_status = "no_results"
            guard_reason = "No sources retrieved."
        elif fallback_used:
            guard_status = "warn"
            guard_reason = "Homepage map fallback used (no direct retrieval match)."
        else:
            guard_status = "ok"
            guard_reason = ""

        # Extract query rewrite from pipeline output directory if available
        query_rewrite = None
        run_dir = pipeline_result.get("output_dir")
        if run_dir:
            search_path = os.path.join(run_dir, "search-results.json")
            if os.path.exists(search_path):
                try:
                    with open(search_path, "r", encoding="utf-8") as f:
                        search_data = json.load(f)
                    query_rewrite = search_data.get("query_rewrite")
                except (json.JSONDecodeError, OSError):
                    pass

        return build_validation_report(
            site_id=site_id,
            question=question,
            ok=True,
            error="",
            source_count=len(sources),
            guard_status=guard_status,
            guard_reason=guard_reason or (warnings[0] if warnings else ""),
            search_results=sources,
            query_rewrite=query_rewrite,
        )

    except Exception as e:
        return build_validation_report(
            site_id=site_id,
            question=question,
            ok=False,
            error=str(e),
            source_count=0,
            guard_status="error",
            guard_reason=str(e),
            search_results=[],
            query_rewrite=None,
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
        default=None,
        help="LLM provider name (default: None / profile default)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="LLM model name/ID (default: None)",
    )
    parser.add_argument(
        "--fetch-provider",
        default=None,
        help="Fetch provider name (default: from profile)",
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

    # Enforce guard before loading questions or running pipeline
    _enforce_live_opt_in(
        parser=argparse.ArgumentParser(),  # only used for error formatting
        provider=args.provider,
        fetch_provider=args.fetch_provider,
        allow_live=args.allow_live,
    )

    questions = load_questions_file(args.questions_file)

    # Aggregate report
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

    # Write or print report
    if args.output:
        if args.output_format == "json":
            write_json_report(aggregated, args.output)
        else:
            # For text output, write a combined text report
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
