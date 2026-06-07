#!/usr/bin/env python3
"""Repeated-question analytics dry-run report generator.

Reads sanitized QuestionLogEvent JSONL files and produces a human-review
Markdown report identifying repeated successful questions (promotion candidates)
and repeated NO_RESULTS/WARN questions (retrieval gaps).

This is a DRY-RUN tool only. It does not create scenarios, snapshots,
caches, pull requests, or commits. Human review is mandatory.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure src is on path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics.repeated_question_analyzer import (
    analyze_repeated_questions,
    PromotionCandidate,
)
from src.analytics.question_logger import sanitize_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate dry-run repeated-question analytics report from JSONL logs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/analyze_question_logs.py --input question-log.jsonl --output report.md
  python scripts/analyze_question_logs.py --input question-log.jsonl --output report.md --min-count 5
  python scripts/analyze_question_logs.py --input question-log.jsonl --output report.md --site-id bukgu_gwangju
        """,
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to sanitized question log JSONL file",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write Markdown report",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=3,
        help="Minimum repeat count to include in report (default: 3)",
    )
    parser.add_argument(
        "--format",
        choices=["markdown"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--site-id",
        help="Optional site ID to filter events (default: all sites)",
    )
    parser.add_argument(
        "--no-redact",
        action="store_true",
        help="Disable secret redaction in output (for testing only, not recommended)",
    )
    return parser.parse_args()


def load_jsonl_events(path: Path) -> list[dict[str, Any]]:
    """Load JSONL events from file, skipping blank lines."""
    events: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {line_num}: {e}") from e
    return events


def filter_by_site(events: list[dict[str, Any]], site_id: str) -> list[dict[str, Any]]:
    """Filter events by site_id."""
    return [e for e in events if e.get("site_id") == site_id]


def group_by_action(candidates: tuple[PromotionCandidate, ...]) -> dict[str, list[PromotionCandidate]]:
    """Group candidates by recommended_action."""
    grouped: dict[str, list[PromotionCandidate]] = {}
    for c in candidates:
        grouped.setdefault(c.recommended_action, []).append(c)
    return grouped


def format_domain_list(domains: tuple[str, ...]) -> str:
    """Format source domains for table display."""
    if not domains:
        return "—"
    return ", ".join(sanitize_text(d) for d in domains)


def format_reason(reason: str, redact: bool = True) -> str:
    """Format reason text, optionally redacting secrets."""
    if redact:
        return sanitize_text(reason)
    return reason


def format_question(q: str, redact: bool = True) -> str:
    """Format question text, optionally redacting secrets."""
    if redact:
        return sanitize_text(q)
    return q


def generate_markdown_report(
    *,
    input_path: Path,
    output_path: Path,
    total_events: int,
    candidates: tuple[PromotionCandidate, ...],
    min_count: int,
    site_filter: str | None,
    redact: bool = True,
) -> str:
    """Generate the Markdown report content."""
    now = datetime.now(timezone.utc).isoformat()

    # Group candidates by action
    grouped = group_by_action(candidates)

    # Separate promotion candidates from retrieval gaps
    promotion_candidates = []
    retrieval_gaps = []

    for action in ("review_for_cache", "review_for_scenario", "monitor"):
        promotion_candidates.extend(grouped.get(action, []))
    retrieval_gaps.extend(grouped.get("retrieval_gap", []))

    lines = [
        "# Repeated Question Analytics Dry-Run Report",
        "",
        "## Summary",
        "",
        f"- Input file: `{input_path.name}`",
        f"- Total events: {total_events}",
        f"- Min count: {min_count}",
        f"- Promotion candidates: {len(promotion_candidates)}",
        f"- Retrieval gaps: {len(retrieval_gaps)}",
        f"- Generated at: {now}",
        "",
    ]

    if site_filter:
        lines.insert(4, f"- Site filter: `{site_filter}`")
        lines.insert(5, "")

    # Promotion candidates section
    lines.extend([
        "## Promotion candidates for human review",
        "",
    ])

    if promotion_candidates:
        lines.append("| Rank | Key | Count | Recommended action | Confidence | Source domains | Reason |")
        lines.append("|---|---:|---:|---|---|---|---|")
        for i, c in enumerate(promotion_candidates, 1):
            key = format_question(c.normalized_key, redact)
            rep_q = format_question(c.representative_question, redact)
            domains = format_domain_list(c.source_domains)
            reason = format_reason(c.reason, redact)
            lines.append(
                f"| {i} | {key} | {c.count} | {c.recommended_action} | "
                f"{c.confidence} | {domains} | {reason} |"
            )
    else:
        lines.append("(No promotion candidates found at this threshold.)")

    lines.extend(["", ""])

    # Retrieval gaps section
    lines.extend([
        "## Retrieval gaps",
        "",
    ])

    if retrieval_gaps:
        lines.append("| Rank | Key | Count | Status pattern | Reason | Suggested next step |")
        lines.append("|---|---:|---:|---|---|---|")
        for i, c in enumerate(retrieval_gaps, 1):
            key = format_question(c.normalized_key, redact)
            status_pattern = ", ".join(sorted(set(c.answer_statuses))) if hasattr(c, 'answer_statuses') else "N/A"
            # Build status pattern from available info
            reason = format_reason(c.reason, redact)
            if c.recommended_action == "retrieval_gap":
                next_step = "Review sitemap, query rewrite, or increase crawl depth"
            elif c.recommended_action == "monitor":
                next_step = "Monitor for signal improvement"
            else:
                next_step = "Review manually"
            lines.append(
                f"| {i} | {key} | {c.count} | {status_pattern} | {reason} | {next_step} |"
            )
    else:
        lines.append("(No retrieval gaps found at this threshold.)")

    lines.extend(["", ""])

    # Notes section
    lines.extend([
        "## Notes",
        "",
        "- This is a **dry-run report**.",
        "- It does **not** create scenarios, snapshots, caches, pull requests, or commits.",
        "- Human review is **required** before any promotion.",
        "- Repeated NO_RESULTS/WARN questions indicate retrieval gaps, not automatic scenario candidates.",
        "- All text fields have been sanitized to redact potential secrets/credentials.",
        "",
    ])

    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    # Load events
    try:
        events = load_jsonl_events(input_path)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not events:
        print("Error: No valid events found in input file", file=sys.stderr)
        return 1

    # Filter by site if requested
    if args.site_id:
        events = filter_by_site(events, args.site_id)
        if not events:
            print(f"Error: No events found for site_id: {args.site_id}", file=sys.stderr)
            return 1

    # Analyze repeated questions
    candidates = analyze_repeated_questions(events, min_count=args.min_count)

    # Generate report
    report = generate_markdown_report(
        input_path=input_path,
        output_path=output_path,
        total_events=len(events),
        candidates=candidates,
        min_count=args.min_count,
        site_filter=args.site_id,
        redact=not args.no_redact,
    )

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"Report generated: {output_path}")
    print(f"Total events analyzed: {len(events)}")
    print(f"Promotion candidates: {len([c for c in candidates if c.recommended_action in ('review_for_cache', 'review_for_scenario', 'monitor')])}")
    print(f"Retrieval gaps: {len([c for c in candidates if c.recommended_action == 'retrieval_gap'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())