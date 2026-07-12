#!/usr/bin/env python3
"""Stage #802 CLI — aggregate ``logs/conversations.jsonl`` into a
sanitized summary report.

The CLI reads the local JSONL file produced by
``src/demo.conversation_log.log_conversation`` and emits either:

* a JSON summary (with ``--json``), or
* a human-readable text report (default).

It never prints the raw ``question``, ``answer``, ``warnings``,
exception text, headers, bodies, provider payloads, API keys, or
URL credentials. The report is count-based only.

Usage::

    PYTHONPATH=. python3 scripts/report_conversation_diagnostics.py \\
        --log-path logs/conversations.jsonl \\
        --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate a conversation-log JSONL into a sanitized "
            "summary report. Never prints raw question / answer / "
            "warning / exception text."
        )
    )
    parser.add_argument(
        "--log-path",
        default="logs/conversations.jsonl",
        help=(
            "Path to the JSONL log produced by "
            "src.demo.conversation_log.log_conversation "
            "(default: logs/conversations.jsonl)."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit the summary as a JSON object instead of text.",
    )
    args = parser.parse_args()

    from src.demo.conversation_log_report import (
        format_text_summary,
        summarize_conversation_log,
    )

    summary = summarize_conversation_log(args.log_path)

    if args.as_json:
        # ``ensure_ascii=False`` so non-ASCII category names stay
        # readable. The helper itself never includes raw text fields,
        # so this is purely cosmetic for the bucket keys.
        sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(format_text_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
