"""Run a schema-only smoke scenario eval for the AI homepage finder.

Stage 41 intentionally does not call live providers, Firecrawl, or the app
pipeline. It validates the Stage 40 scenario matrix and prints a stable
summary that can become the foundation for later live/snapshot evals.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_MATRIX_PATH = Path("tests/fixtures/smoke_scenario_matrix.json")
REQUIRED_SCENARIO_KEYS = {
    "id",
    "site_id",
    "category",
    "question",
    "expected_domain",
    "expected_keywords",
    "pass_criteria",
}
REQUIRED_PASS_CRITERIA_KEYS = {
    "site_id_match",
    "min_sources",
    "no_cross_site_urls",
}


class SmokeScenarioMatrixError(ValueError):
    """Raised when the smoke scenario matrix is structurally invalid."""


def load_matrix(path: Path) -> dict[str, Any]:
    """Load a smoke scenario matrix JSON file."""
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as exc:
        raise SmokeScenarioMatrixError(f"Matrix file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SmokeScenarioMatrixError(f"Matrix file is not valid JSON: {path}") from exc

    if not isinstance(data, dict):
        raise SmokeScenarioMatrixError("Matrix root must be a JSON object.")
    return data


def validate_matrix(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate and return scenarios from a schema-only matrix."""
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise SmokeScenarioMatrixError("Matrix must include a non-empty scenarios list.")

    seen_ids: set[str] = set()
    for index, scenario in enumerate(scenarios, start=1):
        if not isinstance(scenario, dict):
            raise SmokeScenarioMatrixError(f"Scenario #{index} must be an object.")

        missing = REQUIRED_SCENARIO_KEYS - scenario.keys()
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise SmokeScenarioMatrixError(
                f"Scenario #{index} is missing required keys: {missing_list}"
            )

        scenario_id = scenario["id"]
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise SmokeScenarioMatrixError(f"Scenario #{index} has an invalid id.")
        if scenario_id in seen_ids:
            raise SmokeScenarioMatrixError(f"Duplicate scenario id: {scenario_id}")
        seen_ids.add(scenario_id)

        for key in ("site_id", "category", "question", "expected_domain"):
            value = scenario[key]
            if not isinstance(value, str) or not value.strip():
                raise SmokeScenarioMatrixError(
                    f"Scenario {scenario_id} has an invalid {key}."
                )

        expected_keywords = scenario["expected_keywords"]
        if not isinstance(expected_keywords, list):
            raise SmokeScenarioMatrixError(
                f"Scenario {scenario_id} expected_keywords must be a list."
            )

        pass_criteria = scenario["pass_criteria"]
        if not isinstance(pass_criteria, dict):
            raise SmokeScenarioMatrixError(
                f"Scenario {scenario_id} pass_criteria must be an object."
            )
        missing_criteria = REQUIRED_PASS_CRITERIA_KEYS - pass_criteria.keys()
        if missing_criteria:
            missing_list = ", ".join(sorted(missing_criteria))
            raise SmokeScenarioMatrixError(
                f"Scenario {scenario_id} pass_criteria missing: {missing_list}"
            )

    return scenarios


def build_summary(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    """Build stable summary counts for the schema-only eval report."""
    by_site = Counter(str(scenario["site_id"]) for scenario in scenarios)
    by_category = Counter(str(scenario["category"]) for scenario in scenarios)
    return {
        "total": len(scenarios),
        "sites": dict(sorted(by_site.items())),
        "categories": dict(sorted(by_category.items())),
    }


def format_summary(summary: dict[str, Any]) -> str:
    """Format the eval summary for human-readable CLI output."""
    lines = [
        "Smoke scenario matrix loaded",
        f"Total scenarios: {summary['total']}",
        "Sites:",
    ]
    lines.extend(f"- {site_id}: {count}" for site_id, count in summary["sites"].items())
    lines.append("Categories:")
    lines.extend(
        f"- {category}: {count}"
        for category, count in summary["categories"].items()
    )
    lines.extend(["", "Status: schema-only eval passed"])
    return "\n".join(lines)


def run_schema_eval(matrix_path: Path) -> str:
    """Load, validate, summarize, and format a schema-only smoke eval."""
    matrix = load_matrix(matrix_path)
    scenarios = validate_matrix(matrix)
    summary = build_summary(scenarios)
    return format_summary(summary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a schema-only smoke scenario matrix eval."
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        default=DEFAULT_MATRIX_PATH,
        help=f"Path to smoke scenario matrix JSON. Default: {DEFAULT_MATRIX_PATH}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        print(run_schema_eval(args.matrix))
    except SmokeScenarioMatrixError as exc:
        print(f"Smoke scenario eval failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
