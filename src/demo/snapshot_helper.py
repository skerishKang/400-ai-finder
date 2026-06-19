"""Helper functions for saving, loading, and answering from snapshots."""

from __future__ import annotations
import os
import json
from typing import Any
from src.answer.answer_status import normalize_answer_status
from src.demo.demo_helpers import fallback_sources_from_homepage_map, generate_answer_from_sources
from src.demo.metadata_helper import resolve_preset_from_model_provider
from src.llm.runtime_status import resolve_llm_runtime_status

def save_snapshot(result: dict[str, Any], path: str) -> str:
    """Save a demo result dict as a reusable JSON snapshot."""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return os.path.abspath(path)


def load_snapshot(path: str) -> dict[str, Any]:
    """Load a demo result from a JSON snapshot file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Snapshot file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Invalid snapshot file: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Snapshot file must contain a JSON object")

    # Minimal validation
    required = {"site_id", "question"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Snapshot missing required keys: {missing}")

    return data


def answer_from_snapshot_helper(
    runner: Any,
    snapshot_path: str,
    question: str | None = None,
) -> dict[str, Any]:
    """Answer using a pre-saved snapshot instead of live pipeline."""
    snapshot = load_snapshot(snapshot_path)

    q = question or snapshot.get("question", "")
    if not q or not q.strip():
        raise ValueError("Question must not be empty")

    question_changed = question and question != snapshot.get("question")

    if question_changed:
        homepage_map = snapshot.get("homepage_map")
        if homepage_map:
            fb = fallback_sources_from_homepage_map(
                homepage_map, q, runner.profile.important_keywords,
            )
            if fb:
                snapshot["search_results"] = [
                    {
                        "id": f"fb-{i:05d}",
                        "title": c["title"],
                        "url": c["url"],
                        "canonical_url": c["url"],
                        "category": c.get("source_type", "menu"),
                        "content_type": "page",
                        "score": c.get("score", 5.0),
                        "matched_terms": [],
                        "matched_fields": ["title"],
                        "snippet": c["title"],
                        "metadata": {"fetch_status": "snapshot-fallback"},
                    }
                    for i, c in enumerate(fb)
                ]
                snapshot["sources"] = [
                    {
                        "title": c["title"],
                        "url": c["url"],
                        "source_type": c.get("source_type", "menu"),
                        "snippet": c["title"][:200],
                        "score": c.get("score", 5.0),
                    }
                    for c in fb
                ]
                snapshot["fallback_used"] = True
                snapshot.setdefault("warnings", []).append(
                    "홈페이지 메뉴에서 찾은 결과"
                )
            else:
                # Clear stale sources when fallback returns empty
                snapshot["search_results"] = []
                snapshot["sources"] = []
                snapshot["fallback_used"] = False
                snapshot.setdefault("warnings", []).append(
                    "관련 메뉴를 찾지 못했습니다"
                )

        snapshot["question"] = q
        snapshot["answer"] = generate_answer_from_sources(
            q, snapshot.get("sources", []), runner.profile.name,
        )

    # Stage #803: when the question changed and the helper rebuilt the
    # answer from an empty source set, the answer is a generic
    # ``fallback_no_match`` response, not evidence-based. We override
    # ``answer_ok`` and stamp ``answer_status`` accordingly so the demo
    # response, the conversation log, and the aggregation report all
    # agree on the contract. When the question did not change, we keep
    # whatever ``answer_ok`` the snapshot already carried and stamp
    # ``answer_status`` defensively (closed-vocab default = ``error``).
    if question_changed and not snapshot.get("sources"):
        snapshot["answer_ok"] = False
        snapshot["answer_status"] = "fallback_no_match"
    else:
        snapshot["answer_ok"] = bool(snapshot.get("answer_ok", True))
        snapshot["answer_status"] = normalize_answer_status(
            snapshot.get("answer_status")
        )
        if snapshot["answer_ok"] and snapshot["answer_status"] == "error":
            snapshot["answer_status"] = "answered_with_evidence"

    snapshot["snapshot_mode"] = True
    snapshot["provider"] = runner.provider
    if runner.model:
        snapshot["model"] = runner.model
    elif runner.provider == "stub":
        snapshot["model"] = "stub"
    elif runner.provider == "mock":
        snapshot["model"] = ""

    # Resolve preset
    snapshot["preset"] = resolve_preset_from_model_provider(snapshot["provider"], snapshot.get("model") or "")
    snapshot_llm_status = resolve_llm_runtime_status(
        provider=snapshot["provider"],
        model=snapshot.get("model") or "",
        ok=True,
        warnings=snapshot.setdefault("warnings", []),
        snapshot_mode=True,
    )
    snapshot["llm_live"] = snapshot_llm_status["llm_live"]
    snapshot["llm_status"] = snapshot_llm_status["llm_status"]
    snapshot["llm_label"] = snapshot_llm_status["llm_label"]

    snapshot.setdefault("warnings", []).append(
        "홈페이지 메뉴와 저장된 데모 자료를 기준으로 안내합니다."
    )
    # Stage #801: snapshot mode never runs the live fetch pipeline, so
    # there is no fetch diagnostic to record. We set the field to
    # ``None`` explicitly so downstream consumers (conversation_log,
    # dashboards) can rely on the key being present.
    snapshot["fetch_diagnostic"] = None

    # Stage #803: source_weak must be present in the snapshot dict so
    # downstream consumers (conversation_log, admin/mobile demos) see
    # the same shape they get from a live pipeline run. Mirror the
    # rule from ``conversation_log._source_weak_flag``: only true when
    # the route is ``site_search`` AND no sources were attached.
    snapshot_route = str(snapshot.get("route", "site_search")).strip().lower()
    if snapshot_route == "site_search" and not snapshot.get("sources"):
        snapshot["source_weak"] = True
    else:
        snapshot["source_weak"] = False

    return snapshot
