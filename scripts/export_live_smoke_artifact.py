"""Convert live smoke result artifacts to offline smoke export input.

This module is fully offline. It does not call live providers, fetch providers,
external networks, or the app pipeline. It only normalizes an already-produced
live smoke result artifact into the Stage 43 exporter input shape.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.export_smoke_responses import evaluate_exported_pipeline_results
from scripts.run_smoke_eval import (
    DEFAULT_MATRIX_PATH,
    SmokeResponseFixtureError,
    SmokeScenarioMatrixError,
)


class LiveSmokeArtifactExportError(ValueError):
    """Raised when a live smoke artifact cannot be exported safely."""


def load_live_smoke_artifact(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as exc:
        raise LiveSmokeArtifactExportError(f"Live smoke artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LiveSmokeArtifactExportError(
            f"Live smoke artifact is not valid JSON: {path}"
        ) from exc

    if not isinstance(data, dict):
        raise LiveSmokeArtifactExportError("Live smoke artifact root must be a JSON object.")
    return data


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LiveSmokeArtifactExportError(f"{label} must be an object.")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LiveSmokeArtifactExportError(f"{label} must be a non-empty string.")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise LiveSmokeArtifactExportError(f"{label} must be a boolean.")
    return value


def _normalize_source(source: Any, scenario_id: str) -> dict[str, str]:
    source_obj = _require_object(source, f"Source for {scenario_id}")
    title = source_obj.get("title")
    url = source_obj.get("url")
    return {
        "title": title if isinstance(title, str) else "",
        "url": url if isinstance(url, str) else "",
    }


def validate_live_smoke_artifact(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    meta = _require_object(artifact.get("_meta"), "Live artifact _meta")
    if meta.get("artifact_type") != "live_smoke_eval_results":
        raise LiveSmokeArtifactExportError(
            "Live artifact _meta.artifact_type must be live_smoke_eval_results."
        )

    redaction = _require_object(meta.get("redaction"), "Live artifact _meta.redaction")
    for key in (
        "secrets_persisted",
        "cookies_persisted",
        "request_headers_persisted",
        "raw_provider_payloads_persisted",
        "raw_prompts_persisted",
    ):
        if redaction.get(key) is not False:
            raise LiveSmokeArtifactExportError(
                f"Live artifact redaction flag must be false: {key}"
            )

    run = _require_object(artifact.get("run"), "Live artifact run")
    _require_string(run.get("status"), "Live artifact run.status")

    results = artifact.get("results")
    if not isinstance(results, list) or not results:
        raise LiveSmokeArtifactExportError(
            "Live artifact results must be a non-empty list."
        )

    scenario_count = meta.get("scenario_count")
    if isinstance(scenario_count, int) and scenario_count != len(results):
        raise LiveSmokeArtifactExportError(
            "Live artifact _meta.scenario_count must match results length."
        )

    seen_ids: set[str] = set()
    normalized_results: list[dict[str, Any]] = []

    for index, item in enumerate(results, start=1):
        result = _require_object(item, f"Live artifact result #{index}")
        scenario_id = _require_string(
            result.get("scenario_id"), f"Live artifact result #{index}.scenario_id"
        )
        if scenario_id in seen_ids:
            raise LiveSmokeArtifactExportError(
                f"Duplicate live artifact scenario_id: {scenario_id}"
            )
        seen_ids.add(scenario_id)

        site_id = _require_string(result.get("site_id"), f"{scenario_id}.site_id")
        answer = result.get("answer")
        if not isinstance(answer, str):
            raise LiveSmokeArtifactExportError(f"{scenario_id}.answer must be a string.")
        sources = result.get("sources")
        if not isinstance(sources, list):
            raise LiveSmokeArtifactExportError(f"{scenario_id}.sources must be a list.")

        normalized_results.append(
            {
                "scenario_id": scenario_id,
                "result": {
                    "site_id": site_id,
                    "answer": answer,
                    "sources": [
                        _normalize_source(source, scenario_id) for source in sources
                    ],
                    "ok": _require_bool(result.get("ok"), f"{scenario_id}.ok"),
                    "answer_ok": _require_bool(
                        result.get("answer_ok"), f"{scenario_id}.answer_ok"
                    ),
                    "fallback_used": _require_bool(
                        result.get("fallback_used"), f"{scenario_id}.fallback_used"
                    ),
                },
            }
        )

    return normalized_results


def export_live_artifact_to_pipeline_results(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "_meta": {
            "version": "1.0.0",
            "stage": 58,
            "description": "Exported Stage 56/57 live smoke artifact to Stage 43 pipeline-shaped results.",
        },
        "results": validate_live_smoke_artifact(artifact),
    }


def run_export(input_path: Path, output_path: Path | None = None) -> str:
    exported = export_live_artifact_to_pipeline_results(load_live_smoke_artifact(input_path))
    serialized = json.dumps(exported, ensure_ascii=False, indent=2) + "\n"

    if output_path is not None:
        output_path.write_text(serialized, encoding="utf-8")
        return f"Exported live smoke artifact results: {output_path}"

    return serialized.rstrip()


def run_export_eval(
    input_path: Path, matrix_path: Path = DEFAULT_MATRIX_PATH
) -> tuple[str, bool]:
    exported = export_live_artifact_to_pipeline_results(load_live_smoke_artifact(input_path))
    return evaluate_exported_pipeline_results(exported, matrix_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a live smoke result artifact to pipeline-shaped results."
    )
    parser.add_argument("input", type=Path, help="Live smoke artifact JSON to export.")
    parser.add_argument(
        "--matrix",
        type=Path,
        default=DEFAULT_MATRIX_PATH,
        help=f"Path to smoke scenario matrix JSON. Default: {DEFAULT_MATRIX_PATH}",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional output JSON path.")
    parser.add_argument(
        "--eval",
        action="store_true",
        help="Export in memory and evaluate immediately without live calls.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.eval:
            report, passed = run_export_eval(args.input, args.matrix)
            print(report)
            return 0 if passed else 1
        print(run_export(args.input, args.output))
    except (
        LiveSmokeArtifactExportError,
        SmokeResponseFixtureError,
        SmokeScenarioMatrixError,
    ) as exc:
        print(f"Live smoke artifact export failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
