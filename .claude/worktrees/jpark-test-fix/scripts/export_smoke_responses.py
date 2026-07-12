"""Export offline demo/pipeline-shaped results to smoke eval responses.

This adapter does not call live providers, Firecrawl, or the app pipeline.
It only normalizes already-produced structured result dictionaries into
the Stage 42 response fixture shape accepted by:

python scripts/run_smoke_eval.py --responses ...
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.run_smoke_eval import (
    DEFAULT_MATRIX_PATH,
    SmokeResponseFixtureError,
    SmokeScenarioMatrixError,
    build_response_eval_summary,
    evaluate_response_fixture,
    format_response_eval_summary,
    load_matrix,
    validate_matrix,
    validate_response_fixture,
)


class SmokePipelineExportError(ValueError):
    """Raised when pipeline-result export input is structurally invalid."""


def load_pipeline_results(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as exc:
        raise SmokePipelineExportError(f"Pipeline results file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SmokePipelineExportError(
            f"Pipeline results file is not valid JSON: {path}"
        ) from exc

    if not isinstance(data, dict):
        raise SmokePipelineExportError("Pipeline results root must be a JSON object.")
    return data


def _source_value(source: Any, *keys: str) -> str:
    if not isinstance(source, dict):
        return ""
    for key in keys:
        value = source.get(key)
        if isinstance(value, str):
            return value
    return ""


def normalize_source(source: Any) -> dict[str, str]:
    return {
        "title": _source_value(source, "title", "name", "text"),
        "url": _source_value(source, "url", "href", "link", "canonical_url"),
    }


def is_fallback_result(result: dict[str, Any]) -> bool:
    return bool(
        result.get("fallback") is True
        or result.get("fallback_used") is True
        or result.get("answer_ok") is False
        or result.get("ok") is False
    )


def export_pipeline_result_response(
    scenario_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise SmokePipelineExportError(
            "Pipeline result scenario_id must be a non-empty string."
        )
    if not isinstance(result, dict):
        raise SmokePipelineExportError(f"Pipeline result for {scenario_id} must be an object.")

    raw_sources = result.get("sources")
    sources = raw_sources if isinstance(raw_sources, list) else []
    answer = result.get("answer")

    return {
        "scenario_id": scenario_id,
        "site_id": result.get("site_id", ""),
        "answer": answer if isinstance(answer, str) else "",
        "sources": [normalize_source(source) for source in sources],
        "fallback": is_fallback_result(result),
    }


def export_pipeline_results_fixture(data: dict[str, Any]) -> dict[str, Any]:
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise SmokePipelineExportError(
            "Pipeline export input must include a non-empty results list."
        )

    responses: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, item in enumerate(results, start=1):
        if not isinstance(item, dict):
            raise SmokePipelineExportError(f"Pipeline result #{index} must be an object.")

        scenario_id = item.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise SmokePipelineExportError(
                f"Pipeline result #{index} has an invalid scenario_id."
            )
        if scenario_id in seen_ids:
            raise SmokePipelineExportError(f"Duplicate pipeline result scenario_id: {scenario_id}")
        seen_ids.add(scenario_id)

        result = item.get("result", item)
        responses.append(export_pipeline_result_response(scenario_id, result))

    return {
        "_meta": {
            "version": "1.0.0",
            "stage": 43,
            "description": "Exported smoke eval responses from offline demo/pipeline-shaped results.",
        },
        "responses": responses,
    }


def evaluate_exported_pipeline_results(
    data: dict[str, Any], matrix_path: Path = DEFAULT_MATRIX_PATH
) -> tuple[str, bool]:
    """Export pipeline-shaped results in memory and evaluate them with the smoke judge."""
    scenarios = validate_matrix(load_matrix(matrix_path))
    exported_fixture = export_pipeline_results_fixture(data)
    responses_by_id = validate_response_fixture(exported_fixture, scenarios)
    results = evaluate_response_fixture(scenarios, responses_by_id)
    summary = build_response_eval_summary(results)
    return format_response_eval_summary(summary), summary["failed"] == 0


def run_export(input_path: Path, output_path: Path | None = None) -> str:
    exported = export_pipeline_results_fixture(load_pipeline_results(input_path))
    serialized = json.dumps(exported, ensure_ascii=False, indent=2) + "\n"

    if output_path is not None:
        output_path.write_text(serialized, encoding="utf-8")
        return f"Exported smoke eval responses: {output_path}"

    return serialized.rstrip()


def run_export_eval(
    input_path: Path, matrix_path: Path = DEFAULT_MATRIX_PATH
) -> tuple[str, bool]:
    """Load pipeline-shaped results, export them in memory, and run response eval."""
    return evaluate_exported_pipeline_results(load_pipeline_results(input_path), matrix_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export offline demo/pipeline-shaped results to smoke eval responses."
    )
    parser.add_argument("input", type=Path, help="Pipeline/demo result JSON to export.")
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
        SmokePipelineExportError,
        SmokeResponseFixtureError,
        SmokeScenarioMatrixError,
    ) as exc:
        print(f"Smoke response export failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
