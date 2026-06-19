"""Conversation log helper for MVP dialog operation mode.

Saves JSONL conversation logs under ``logs/conversations.jsonl``.
For MVP analysis, question/answer/source metadata are persisted.
Auth headers, raw transport metadata, raw provider responses, and
secrets are not written.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


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
        }
        line = json.dumps(record, ensure_ascii=False)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return True
    except Exception:
        return False
