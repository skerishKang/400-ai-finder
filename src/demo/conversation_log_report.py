"""Aggregation helper for Stage #802.

Reads the JSONL conversation log produced by ``conversation_log.log_conversation``
and returns a sanitized summary report. **The report never includes raw
question text, answer text, warning text, exception messages, headers,
bodies, provider payloads, API keys, or URL credentials** — only counts
and other closed-vocabulary fields.

This module exists so operators can answer the questions:

* How many conversations ran today?
* How many were site_search vs direct_answer vs clarify?
* How many were ``source_weak`` (i.e. the search pipeline could not
  produce sources)?
* What was the distribution of ``fetch_diagnostic_category`` values?
* Are we seeing timeouts, blocks, parse errors, or connection issues?
* How many records failed to parse?
* What ``llm_status`` did the runtime report?

without ever reading the raw conversation text.

The helper is **read-only** — it does not perform any live fetch, network
call, provider call, or Firecrawl call. It only reads a local JSONL
file.
"""

from __future__ import annotations

import json
import os
from typing import Any


# Sentinel bucket used when a closed-vocabulary field is missing or
# ``None``. We never invent fake values; we just bucket them under
# ``"none"`` so operators can see "this record had no diagnostic" at a
# glance.
_NONE_BUCKET = "none"


def _bucket(value: Any) -> str:
    """Coerce a value into a bucket key, mapping ``None`` / missing to
    ``"none"``.

    Booleans are returned as ``"true"`` / ``"false"`` so the resulting
    keys are JSON-friendly. Strings are returned unchanged.
    """
    if value is None:
        return _NONE_BUCKET
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return str(value)


def summarize_conversation_log(log_path: str) -> dict[str, Any]:
    """Aggregate ``log_path`` into a sanitized summary dict.

    Returns an empty-summary shape if the file is missing or empty.
    Malformed JSONL lines are skipped and counted; their raw content is
    never returned.
    """
    empty: dict[str, Any] = {
        "total_records": 0,
        "malformed_line_count": 0,
        "route_counts": {},
        "site_id_counts": {},
        "llm_status_counts": {},
        "source_weak_count": 0,
        "answer_ok_false_count": 0,
        "records_with_warnings_count": 0,
        "fetch_diagnostic_category_counts": {},
        "fetch_diagnostic_retry_hint_counts": {},
        "fetch_diagnostic_transient_count": 0,
    }

    if not log_path:
        return empty
    if not os.path.exists(log_path):
        return dict(empty)

    route_counts: dict[str, int] = {}
    site_id_counts: dict[str, int] = {}
    llm_status_counts: dict[str, int] = {}
    fetch_diagnostic_category_counts: dict[str, int] = {}
    fetch_diagnostic_retry_hint_counts: dict[str, int] = {}

    total_records = 0
    malformed_line_count = 0
    source_weak_count = 0
    answer_ok_false_count = 0
    records_with_warnings_count = 0
    fetch_diagnostic_transient_count = 0

    with open(log_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                # Blank lines (e.g. trailing newline) are not malformed.
                continue
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                malformed_line_count += 1
                continue
            if not isinstance(record, dict):
                malformed_line_count += 1
                continue

            total_records += 1

            route = _bucket(record.get("route"))
            route_counts[route] = route_counts.get(route, 0) + 1

            site_id = _bucket(record.get("site_id"))
            site_id_counts[site_id] = site_id_counts.get(site_id, 0) + 1

            llm_status = _bucket(record.get("llm_status"))
            llm_status_counts[llm_status] = (
                llm_status_counts.get(llm_status, 0) + 1
            )

            if bool(record.get("source_weak", False)):
                source_weak_count += 1
            if not bool(record.get("answer_ok", True)):
                answer_ok_false_count += 1

            warnings = record.get("warnings")
            if isinstance(warnings, list) and len(warnings) > 0:
                records_with_warnings_count += 1

            # Stage #801 columns. The four closed-vocabulary fields are
            # already flattened in the JSONL record. We bucket each one
            # individually so operators can spot patterns even when the
            # upstream helper produced different categories.
            category = _bucket(record.get("fetch_diagnostic_category"))
            fetch_diagnostic_category_counts[category] = (
                fetch_diagnostic_category_counts.get(category, 0) + 1
            )

            retry_hint = _bucket(record.get("fetch_diagnostic_retry_hint"))
            fetch_diagnostic_retry_hint_counts[retry_hint] = (
                fetch_diagnostic_retry_hint_counts.get(retry_hint, 0) + 1
            )

            # ``is_transient`` is a bool column — we count only the true
            # bucket because the false / none bucket is the trivial
            # default and would dilute operator signal.
            is_transient = record.get("fetch_diagnostic_is_transient")
            if is_transient is True:
                fetch_diagnostic_transient_count += 1

    return {
        "total_records": total_records,
        "malformed_line_count": malformed_line_count,
        "route_counts": route_counts,
        "site_id_counts": site_id_counts,
        "llm_status_counts": llm_status_counts,
        "source_weak_count": source_weak_count,
        "answer_ok_false_count": answer_ok_false_count,
        "records_with_warnings_count": records_with_warnings_count,
        "fetch_diagnostic_category_counts": fetch_diagnostic_category_counts,
        "fetch_diagnostic_retry_hint_counts": fetch_diagnostic_retry_hint_counts,
        "fetch_diagnostic_transient_count": fetch_diagnostic_transient_count,
    }


def format_text_summary(summary: dict[str, Any]) -> str:
    """Render ``summary`` as a human-readable multi-line text report.

    The text format is intentionally narrow (counts and bucketed values
    only). Raw question / answer / warning / exception text never
    appears here.
    """
    lines: list[str] = []

    def _fmt_counts(title: str, counts: dict[str, int]) -> None:
        if not counts:
            lines.append(f"  {title}: (none)")
            return
        lines.append(f"  {title}:")
        # Stable ordering: by descending count, then alphabetic key.
        for key, value in sorted(
            counts.items(), key=lambda kv: (-kv[1], kv[0])
        ):
            lines.append(f"    {key}: {value}")

    lines.append("Conversation log summary")
    lines.append("=" * 40)
    lines.append(f"  total_records: {summary.get('total_records', 0)}")
    lines.append(f"  malformed_line_count: {summary.get('malformed_line_count', 0)}")
    lines.append(
        f"  source_weak_count: {summary.get('source_weak_count', 0)}"
    )
    lines.append(
        f"  answer_ok_false_count: {summary.get('answer_ok_false_count', 0)}"
    )
    lines.append(
        f"  records_with_warnings_count: {summary.get('records_with_warnings_count', 0)}"
    )
    lines.append(
        f"  fetch_diagnostic_transient_count: "
        f"{summary.get('fetch_diagnostic_transient_count', 0)}"
    )
    lines.append("")
    _fmt_counts("route_counts", summary.get("route_counts", {}))
    lines.append("")
    _fmt_counts("site_id_counts", summary.get("site_id_counts", {}))
    lines.append("")
    _fmt_counts("llm_status_counts", summary.get("llm_status_counts", {}))
    lines.append("")
    _fmt_counts(
        "fetch_diagnostic_category_counts",
        summary.get("fetch_diagnostic_category_counts", {}),
    )
    lines.append("")
    _fmt_counts(
        "fetch_diagnostic_retry_hint_counts",
        summary.get("fetch_diagnostic_retry_hint_counts", {}),
    )
    return "\n".join(lines) + "\n"
