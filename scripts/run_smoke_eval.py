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
from urllib.parse import urlparse

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
FALLBACK_MARKERS = (
    "직접 확인",
    "홈페이지에서 확인",
    "출처가 부족",
    "근거가 부족",
    "확인해 주세요",
    "확인해야 합니다",
)


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


def _source_url(source: Any) -> str:
    if not isinstance(source, dict):
        return ""
    value = source.get("url") or source.get("href") or source.get("link")
    return value if isinstance(value, str) else ""


def _source_title(source: Any) -> str:
    if not isinstance(source, dict):
        return ""
    value = source.get("title") or source.get("name")
    return value if isinstance(value, str) else ""


def _source_matches_domain(source: Any, expected_domain: str) -> bool:
    url = _source_url(source).strip()
    if not url:
        return False
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    expected = expected_domain.lower()
    return host == expected or host.endswith(f".{expected}")


def _valid_sources(response: dict[str, Any]) -> list[dict[str, Any]]:
    sources = response.get("sources")
    if not isinstance(sources, list):
        return []
    return [source for source in sources if isinstance(source, dict)]


def _is_fallback_response(response: dict[str, Any]) -> bool:
    if response.get("fallback") is True:
        return True
    answer = response.get("answer")
    if not isinstance(answer, str):
        return False
    return any(marker in answer for marker in FALLBACK_MARKERS)


def evaluate_response(
    scenario: dict[str, Any], response: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate one pipeline-shaped response against a smoke scenario.

    The expected response shape is intentionally small and provider-neutral:
    {"site_id": str, "answer": str, "sources": [{"title": str, "url": str}],
    "fallback": bool}. Extra keys are ignored so future live/snapshot pipeline
    adapters can reuse the same judge.
    """
    criteria = scenario.get("pass_criteria", {})
    expected_domain = str(scenario.get("expected_domain", ""))
    scenario_id = str(scenario.get("id", ""))
    answer = response.get("answer") if isinstance(response.get("answer"), str) else ""
    sources = _valid_sources(response)
    checks: dict[str, bool] = {}

    if criteria.get("site_id_match") is True:
        checks["site_id_match"] = response.get("site_id") == scenario.get("site_id")

    min_sources = criteria.get("min_sources")
    if isinstance(min_sources, int):
        checks["min_sources"] = len(sources) >= min_sources

    source_domain = criteria.get("source_domain") or expected_domain
    if isinstance(source_domain, str) and source_domain and sources:
        checks["source_domain"] = any(
            _source_title(source).strip() and _source_matches_domain(source, source_domain)
            for source in sources
        )

    if criteria.get("no_cross_site_urls") is True and sources:
        checks["no_cross_site_urls"] = all(
            _source_matches_domain(source, expected_domain) for source in sources
        )

    answer_contains_any = criteria.get("answer_contains_any")
    if isinstance(answer_contains_any, list) and answer_contains_any:
        checks["answer_contains_any"] = any(
            isinstance(keyword, str) and keyword in answer
            for keyword in answer_contains_any
        )

    if criteria.get("answer_not_empty") is True:
        checks["answer_not_empty"] = bool(answer.strip())

    if criteria.get("fallback_required") is True:
        checks["fallback_required"] = _is_fallback_response(response)

    if criteria.get("fallback_when_no_source") is True:
        checks["fallback_when_no_source"] = bool(sources) or _is_fallback_response(response)

    failures = [name for name, passed in checks.items() if not passed]
    return {
        "scenario_id": scenario_id,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
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
