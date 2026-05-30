"""Helper functions for saving, loading, and answering from snapshots."""

from __future__ import annotations
import os
import json
from typing import Any
from src.demo.demo_helpers import fallback_sources_from_homepage_map, generate_answer_from_sources
from src.demo.metadata_helper import resolve_preset_from_model_provider

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

        snapshot["question"] = q
        snapshot["answer"] = generate_answer_from_sources(
            q, snapshot.get("sources", []), runner.profile.name,
        )

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

    snapshot.setdefault("warnings", []).append(
        "홈페이지 메뉴와 저장된 데모 자료를 기준으로 안내합니다."
    )
    return snapshot
