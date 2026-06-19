"""Conversation log helper for MVP dialog operation mode.

Saves JSONL conversation logs under ``logs/conversations.jsonl``.
For MVP analysis, question/answer/source metadata are persisted.
Auth headers, raw transport metadata, raw provider responses, and
secrets are not written.

Stage #801: sanitized fetch diagnostic fields (closed-vocabulary)
are recorded alongside the existing ``route`` / ``source_weak`` /
``fallback_used`` fields. Raw exception text, headers, bodies,
provider payloads, API keys, and URL credentials are never written.

Stage #803: closed-vocab ``answer_status`` column added. It is
always normalized to one of the four values defined in
``src.answer.answer_status``. Unknown values fall back to
``"error"`` so the conversation log never carries a free-form
string from a legacy or malformed snapshot.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from src.answer.answer_status import normalize_answer_status


DEFAULT_LOG_PATH = os.path.join("logs", "conversations.jsonl")

SAFE_FIELDS = (
    "timestamp",
    "site_id",
    "site_name",
    "question",
    "answer",
    "provider",
    "model",
    "llm_status",
    "llm_live",
    "answer_ok",
    "sources_count",
    "source_weak",
    "sources",
    "fallback_used",
    "warnings",
    "route",
    "should_search_site",
    "route_confidence",
    "route_reason",
    "search_query",
    "answer_mode",
    # Stage #801: sanitized fetch diagnostic. Each field is drawn
    # from a closed vocabulary (FetchCategory enum + retry_hint
    # closed set + bool). We persist them as separate scalar columns
    # so JSONL readers can grep / aggregate on category or retry_hint
    # without parsing nested dicts.
    "fetch_diagnostic_category",
    "fetch_diagnostic_short_reason",
    "fetch_diagnostic_retry_hint",
    "fetch_diagnostic_is_transient",
    # Stage #803: closed-vocab answer_status scalar column. Always
    # one of {answered_with_evidence, fallback_no_match,
    # fallback_unavailable, error} after normalization.
    "answer_status",
)


def _ensure_dir(path: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)


def _sanitize_sources(sources: Any) -> list[dict[str, Any]]:
    if not isinstance(sources, list):
        return []
    safe = []
    for item in sources:
        if not isinstance(item, dict):
            continue
        safe.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
            }
        )
    return safe


def _source_weak_flag(result: dict[str, Any]) -> bool:
    """source_weak only applies when the route is site_search.

    direct_answer and clarify do not run the search pipeline, so they
    have no source list to evaluate.
    """
    route = str(result.get("route", "")).strip().lower()
    if route != "site_search":
        return False
    sources_count = len(result.get("sources", []) or [])
    return sources_count < 1


def _fetch_diagnostic_columns(result: dict[str, Any]) -> dict[str, Any]:
    """Flatten ``fetch_diagnostic`` into four closed-vocabulary columns.

    The runner emits either ``None`` (no diagnostic — direct_answer,
    clarify, snapshot, or a successful site_search) or a small dict
    with the four fields populated by :class:`FetchDiagnostic.to_dict`.
    We never log raw exception text, headers, bodies, provider
    payloads, API keys, or URL credentials — only the values that
    :class:`FetchDiagnostic` was built to carry.
    """
    diag = result.get("fetch_diagnostic")
    if not isinstance(diag, dict):
        # Either None or non-conforming value — record as no diagnostic.
        return {
            "fetch_diagnostic_category": None,
            "fetch_diagnostic_short_reason": None,
            "fetch_diagnostic_retry_hint": None,
            "fetch_diagnostic_is_transient": None,
        }
    return {
        "fetch_diagnostic_category": diag.get("category"),
        "fetch_diagnostic_short_reason": diag.get("short_reason"),
        "fetch_diagnostic_retry_hint": diag.get("retry_hint"),
        "fetch_diagnostic_is_transient": diag.get("is_transient"),
    }


def log_conversation(result: dict[str, Any], log_path: str = DEFAULT_LOG_PATH) -> bool:
    """Append a single conversation record to the JSONL log.

    Returns True on success, False on write failure.
    Failures are silent to the user-facing path; callers can add a warning
    if needed.
    """
    try:
        _ensure_dir(log_path)
        record = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "site_id": result.get("site_id", ""),
            "site_name": result.get("site_name", ""),
            "question": result.get("question", ""),
            "answer": result.get("answer", ""),
            "provider": result.get("provider", ""),
            "model": result.get("model", ""),
            "llm_status": result.get("llm_status", "unknown"),
            "llm_live": bool(result.get("llm_live", False)),
            "answer_ok": bool(result.get("answer_ok", False)),
            "sources_count": len(result.get("sources", []) or []),
            "source_weak": _source_weak_flag(result),
            "sources": _sanitize_sources(result.get("sources")),
            "fallback_used": bool(result.get("fallback_used", False)),
            "warnings": result.get("warnings", []) or [],
            "route": result.get("route", ""),
            "should_search_site": bool(result.get("should_search_site", False)),
            "route_confidence": float(result.get("route_confidence", 0.0)),
            "route_reason": result.get("route_reason", ""),
            "search_query": result.get("search_query", ""),
            "answer_mode": result.get("answer_mode", ""),
            **_fetch_diagnostic_columns(result),
            # Stage #803: normalize the answer_status to one of the
            # four closed-vocab values. Defensive default for
            # malformed snapshots is "error".
            "answer_status": normalize_answer_status(result.get("answer_status")),
        }
        line = json.dumps(record, ensure_ascii=False)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return True
    except Exception:
        return False
