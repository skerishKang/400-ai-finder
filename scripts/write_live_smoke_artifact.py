"""Write redaction-safe live smoke result artifacts.

This module is fully offline. It does not call live providers, fetch providers,
external networks, or the app pipeline. It only takes already-produced scenario
result dictionaries and serializes them into the Stage 56/57 live smoke artifact
shape.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.export_live_smoke_artifact import LiveSmokeArtifactExportError

REDACTION_FLAGS: dict[str, bool] = {
    "secrets_persisted": False,
    "cookies_persisted": False,
    "request_headers_persisted": False,
    "raw_provider_payloads_persisted": False,
    "raw_prompts_persisted": False,
}
ALLOWED_STATUSES = {
    "answered",
    "fallback",
    "error",
    "skipped",
    "pending_configuration",
}


class LiveSmokeArtifactWriterError(ValueError):
    """Raised when artifact writer input is invalid."""


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LiveSmokeArtifactWriterError(f"Input JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LiveSmokeArtifactWriterError(f"Input JSON file is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise LiveSmokeArtifactWriterError("Input JSON root must be an object.")
    return data


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LiveSmokeArtifactWriterError(f"{label} must be an object.")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LiveSmokeArtifactWriterError(f"{label} must be a non-empty string.")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise LiveSmokeArtifactWriterError(f"{label} must be a boolean.")
    return value


def _optional_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or value < 0:
        raise LiveSmokeArtifactWriterError(f"{label} must be a non-negative integer.")
    return value


def normalize_source(source: Any, scenario_id: str) -> dict[str, Any]:
    source_obj = _require_object(source, f"{scenario_id}.source")
    title = source_obj.get("title")
    url = source_obj.get("url")
    normalized: dict[str, Any] = {
        "title": title if isinstance(title, str) else "",
        "url": url if isinstance(url, str) else "",
    }
    snippet = source_obj.get("snippet")
    if isinstance(snippet, str) and snippet:
        normalized["snippet"] = snippet
    source_rank = source_obj.get("source_rank")
    if isinstance(source_rank, int) and source_rank > 0:
        normalized["source_rank"] = source_rank
    return normalized


def normalize_diagnostics(result: dict[str, Any], source_count: int) -> dict[str, Any]:
    diagnostics = result.get("diagnostics")
    if isinstance(diagnostics, dict):
        error_type = diagnostics.get("error_type")
        error_message = diagnostics.get("error_message")
        return {
            "source_count": diagnostics.get("source_count", source_count),
            "normalized_source_count": diagnostics.get("normalized_source_count", source_count),
            "error_type": error_type if isinstance(error_type, str) else None,
            "error_message": error_message if isinstance(error_message, str) else None,
        }
    return {
        "source_count": source_count,
        "normalized_source_count": source_count,
        "error_type": None,
        "error_message": None,
    }


def normalize_timing(result: dict[str, Any]) -> dict[str, int]:
    timing = result.get("timing_ms")
    if not isinstance(timing, dict):
        return {}
    normalized: dict[str, int] = {}
    for key in ("total", "fetch", "provider"):
        value = timing.get(key)
        if isinstance(value, int) and value >= 0:
            normalized[key] = value
    return normalized


def normalize_live_result(item: Any, index: int) -> dict[str, Any]:
    result = _require_object(item, f"Live writer result #{index}")
    scenario_id = _require_string(result.get("scenario_id"), f"result #{index}.scenario_id")
    site_id = _require_string(result.get("site_id"), f"{scenario_id}.site_id")
    query = _require_string(result.get("query"), f"{scenario_id}.query")
    status = _require_string(result.get("status"), f"{scenario_id}.status")
    if status not in ALLOWED_STATUSES:
        raise LiveSmokeArtifactWriterError(f"{scenario_id}.status is not supported: {status}")

    answer = result.get("answer")
    if not isinstance(answer, str):
        raise LiveSmokeArtifactWriterError(f"{scenario_id}.answer must be a string.")
    sources = result.get("sources")
    if not isinstance(sources, list):
        raise LiveSmokeArtifactWriterError(f"{scenario_id}.sources must be a list.")
    normalized_sources = [normalize_source(source, scenario_id) for source in sources]

    normalized: dict[str, Any] = {
        "scenario_id": scenario_id,
        "site_id": site_id,
        "query": query,
        "status": status,
        "answer": answer,
        "sources": normalized_sources,
        "fallback_used": _require_bool(result.get("fallback_used"), f"{scenario_id}.fallback_used"),
        "ok": _require_bool(result.get("ok"), f"{scenario_id}.ok"),
        "answer_ok": _require_bool(result.get("answer_ok"), f"{scenario_id}.answer_ok"),
        "diagnostics": normalize_diagnostics(result, len(normalized_sources)),
    }
    timing = normalize_timing(result)
    if timing:
        normalized["timing_ms"] = timing
    return normalized


def build_live_smoke_artifact(
    results: list[Any],
    *,
    matrix_path: str,
    created_at: str | None = None,
    run_status: str = "completed",
    live_opt_in: bool = True,
    provider_name: str = "redacted-provider-label",
    fetch_provider_name: str = "redacted-fetch-label",
    started_at: str | None = None,
    finished_at: str | None = None,
    duration_ms: int | None = None,
) -> dict[str, Any]:
    if not isinstance(results, list) or not results:
        raise LiveSmokeArtifactWriterError("Live writer results must be a non-empty list.")
    if run_status not in {"completed", "partial", "failed", "preflight_only"}:
        raise LiveSmokeArtifactWriterError(f"Unsupported run status: {run_status}")

    normalized_results = [
        normalize_live_result(result, index) for index, result in enumerate(results, start=1)
    ]
    scenario_ids = [result["scenario_id"] for result in normalized_results]
    if len(scenario_ids) != len(set(scenario_ids)):
        raise LiveSmokeArtifactWriterError("Live writer results contain duplicate scenario_id values.")

    timestamp = created_at or utc_now_iso()
    started = started_at or timestamp
    run: dict[str, Any] = {
        "status": run_status,
        "live_opt_in": live_opt_in,
        "provider_name": provider_name,
        "fetch_provider_name": fetch_provider_name,
        "started_at": started,
    }
    if finished_at is not None:
        run["finished_at"] = finished_at
    duration = _optional_int(duration_ms, "duration_ms")
    if duration is not None:
        run["duration_ms"] = duration

    return {
        "_meta": {
            "version": "1.0.0",
            "artifact_type": "live_smoke_eval_results",
            "stage": 60,
            "created_at": timestamp,
            "matrix_path": matrix_path,
            "scenario_count": len(normalized_results),
            "offline_boundary": False,
            "redaction": dict(REDACTION_FLAGS),
        },
        "run": run,
        "results": normalized_results,
    }


def extract_results_payload(data: dict[str, Any]) -> list[Any]:
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise LiveSmokeArtifactWriterError("Input JSON must include a non-empty results list.")
    if isinstance(results[0], dict) and "result" in results[0]:
        extracted: list[Any] = []
        for item in results:
            item_obj = _require_object(item, "pipeline result item")
            result = _require_object(item_obj.get("result"), "pipeline result item.result")
            scenario_id = _require_string(item_obj.get("scenario_id"), "pipeline result item.scenario_id")
            merged = {"scenario_id": scenario_id, **result}
            if "query" not in merged:
                merged["query"] = scenario_id
            if "status" not in merged:
                merged["status"] = "fallback" if merged.get("fallback_used") is True else "answered"
            extracted.append(merged)
        return extracted
    return results


def run_write(
    input_path: Path,
    output_path: Path,
    *,
    matrix_path: str,
    created_at: str | None = None,
) -> str:
    data = load_json_object(input_path)
    artifact = build_live_smoke_artifact(
        extract_results_payload(data),
        matrix_path=matrix_path,
        created_at=created_at,
    )
    output_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"Wrote live smoke artifact: {output_path}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a redaction-safe live smoke result artifact from existing results."
    )
    parser.add_argument("input", type=Path, help="Input JSON containing a results list.")
    parser.add_argument("--output", type=Path, required=True, help="Output live artifact JSON path.")
    parser.add_argument(
        "--matrix-path",
        default="tests/fixtures/smoke_scenario_matrix.json",
        help="Matrix path recorded in artifact metadata.",
    )
    parser.add_argument("--created-at", default=None, help="Optional UTC timestamp for deterministic tests.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        print(
            run_write(
                args.input,
                args.output,
                matrix_path=args.matrix_path,
                created_at=args.created_at,
            )
        )
    except (LiveSmokeArtifactWriterError, LiveSmokeArtifactExportError) as exc:
        print(f"Live smoke artifact write failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
