"""Run smoke scenario evals for the AI homepage finder.

Stage 47 keeps live smoke eval guarded. Offline schema and response fixture evals
remain the default behavior. The ``--live`` flag never calls providers, fetchers,
or the app pipeline in this stage; it only verifies that live execution is
explicitly opted in and then reports that live execution is not implemented yet.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

DEFAULT_MATRIX_PATH = Path("tests/fixtures/smoke_scenario_matrix.json")
LIVE_EVAL_ENV_VAR = "AI_FINDER_LIVE_EVAL"
LIVE_PREFLIGHT_CONFIG_NAMES = (
    LIVE_EVAL_ENV_VAR,
    "AI_FINDER_LIVE_PROVIDER",
    "AI_FINDER_LIVE_FETCH_PROVIDER",
)
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
REQUIRED_BOOLEAN_PASS_CRITERIA_KEYS = (
    "site_id_match",
    "no_cross_site_urls",
)
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


class SmokeResponseFixtureError(ValueError):
    """Raised when a smoke response fixture is structurally invalid."""


class SmokeLiveEvalGuardError(ValueError):
    """Raised when live smoke eval is requested without explicit opt-in."""


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


def load_response_fixture(path: Path) -> dict[str, Any]:
    """Load an offline smoke response fixture JSON file."""
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as exc:
        raise SmokeResponseFixtureError(f"Response fixture file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SmokeResponseFixtureError(
            f"Response fixture file is not valid JSON: {path}"
        ) from exc

    if not isinstance(data, dict):
        raise SmokeResponseFixtureError("Response fixture root must be a JSON object.")
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

        for key in REQUIRED_BOOLEAN_PASS_CRITERIA_KEYS:
            value = pass_criteria.get(key)
            if type(value) is not bool:
                raise SmokeScenarioMatrixError(
                    f"Scenario {scenario_id} pass_criteria.{key} must be a boolean."
                )

        min_sources = pass_criteria.get("min_sources")
        if type(min_sources) is not int or min_sources < 0:
            raise SmokeScenarioMatrixError(
                f"Scenario {scenario_id} pass_criteria.min_sources must be a non-negative integer."
            )

        source_domain = pass_criteria.get("source_domain")
        if source_domain and not isinstance(source_domain, str):
            raise SmokeScenarioMatrixError(
                f"Scenario {scenario_id} pass_criteria.source_domain must be a string."
            )

    return scenarios


def validate_response_fixture(
    data: dict[str, Any], scenarios: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Validate response fixture entries and index them by scenario_id."""
    responses = data.get("responses")
    if not isinstance(responses, list) or not responses:
        raise SmokeResponseFixtureError(
            "Response fixture must include a non-empty responses list."
        )

    scenario_ids = {str(scenario["id"]) for scenario in scenarios}
    indexed: dict[str, dict[str, Any]] = {}
    for index, response in enumerate(responses, start=1):
        if not isinstance(response, dict):
            raise SmokeResponseFixtureError(f"Response #{index} must be an object.")

        scenario_id = response.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise SmokeResponseFixtureError(f"Response #{index} has an invalid scenario_id.")
        if scenario_id in indexed:
            raise SmokeResponseFixtureError(f"Duplicate response scenario_id: {scenario_id}")
        if scenario_id not in scenario_ids:
            raise SmokeResponseFixtureError(f"Unknown response scenario_id: {scenario_id}")

        indexed[scenario_id] = response

    missing = sorted(scenario_ids - indexed.keys())
    if missing:
        raise SmokeResponseFixtureError(
            f"Response fixture missing scenario_id values: {', '.join(missing)}"
        )

    return indexed


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
    """Evaluate one pipeline-shaped response against a smoke scenario."""
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


def evaluate_response_fixture(
    scenarios: list[dict[str, Any]], responses_by_id: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Evaluate all scenarios against indexed pipeline-shaped responses."""
    return [
        evaluate_response(scenario, responses_by_id[str(scenario["id"])])
        for scenario in scenarios
    ]


def build_response_eval_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize response eval pass/fail results."""
    failed = [result for result in results if not result["passed"]]
    return {
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "failed_results": failed,
    }


def is_live_eval_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether live smoke eval has been explicitly enabled."""
    env_values = os.environ if env is None else env
    return env_values.get(LIVE_EVAL_ENV_VAR, "").strip().lower() == "true"


def run_live_eval_guard(env: Mapping[str, str] | None = None) -> str:
    """Guard the not-yet-implemented live smoke eval path."""
    if not is_live_eval_enabled(env):
        raise SmokeLiveEvalGuardError(
            f"--live requires {LIVE_EVAL_ENV_VAR}=true. "
            "No live provider, fetch, or pipeline calls were made."
        )
    return (
        "Live smoke eval is explicitly enabled, but live execution is not "
        "implemented in this stage. No live provider, fetch, or pipeline calls "
        "were made."
    )


def _has_config_value(env: Mapping[str, str], name: str) -> bool:
    value = env.get(name)
    return isinstance(value, str) and bool(value.strip())


def build_live_eval_preflight(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Build a value-redacted live smoke eval preflight summary.

    This function only reports config names and boolean status. It must never
    return or print config values.
    """
    env_values = os.environ if env is None else env
    items = [
        {
            "name": name,
            "present": _has_config_value(env_values, name),
        }
        for name in LIVE_PREFLIGHT_CONFIG_NAMES
    ]
    return {
        "live_enabled": is_live_eval_enabled(env_values),
        "items": items,
        "missing": [item["name"] for item in items if not item["present"]],
    }


def format_live_eval_preflight(summary: dict[str, Any]) -> str:
    """Format a value-redacted live smoke eval preflight report."""
    lines = [
        "Live smoke eval preflight",
        f"Live opt-in: {'enabled' if summary['live_enabled'] else 'disabled'}",
        "Config names:",
    ]
    for item in summary["items"]:
        status = "set" if item["present"] else "missing"
        lines.append(f"- {item['name']}: {status}")

    if summary["missing"]:
        lines.append("")
        lines.append("Missing config names:")
        lines.extend(f"- {name}" for name in summary["missing"])

    lines.extend(
        [
            "",
            "Status: preflight completed",
            "No live provider, fetch, network, or pipeline calls were made.",
        ]
    )
    return "\n".join(lines)


def run_live_eval_preflight(env: Mapping[str, str] | None = None) -> str:
    """Run value-redacted live smoke eval preflight only."""
    return format_live_eval_preflight(build_live_eval_preflight(env))


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


def format_response_eval_summary(summary: dict[str, Any]) -> str:
    """Format response eval summary for CLI output."""
    lines = [
        "Smoke response eval loaded",
        f"Evaluated responses: {summary['total']}",
        f"Passed: {summary['passed']}",
        f"Failed: {summary['failed']}",
    ]
    if summary["failed_results"]:
        lines.extend(["", "Failed scenarios:"])
        for result in summary["failed_results"]:
            failures = ", ".join(result["failures"])
            lines.append(f"- {result['scenario_id']}: {failures}")
        lines.extend(["", "Status: response eval failed"])
    else:
        lines.extend(["", "Status: response eval passed"])
    return "\n".join(lines)


def run_schema_eval(matrix_path: Path) -> str:
    """Load, validate, summarize, and format a schema-only smoke eval."""
    matrix = load_matrix(matrix_path)
    scenarios = validate_matrix(matrix)
    summary = build_summary(scenarios)
    return format_summary(summary)


def run_response_eval(matrix_path: Path, responses_path: Path) -> tuple[str, bool]:
    """Load matrix and response fixtures, evaluate responses, and format report."""
    matrix = load_matrix(matrix_path)
    scenarios = validate_matrix(matrix)
    response_fixture = load_response_fixture(responses_path)
    responses_by_id = validate_response_fixture(response_fixture, scenarios)
    results = evaluate_response_fixture(scenarios, responses_by_id)
    summary = build_response_eval_summary(results)
    return format_response_eval_summary(summary), summary["failed"] == 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run smoke scenario matrix evals.")
    parser.add_argument(
        "--matrix",
        type=Path,
        default=DEFAULT_MATRIX_PATH,
        help=f"Path to smoke scenario matrix JSON. Default: {DEFAULT_MATRIX_PATH}",
    )
    parser.add_argument(
        "--responses",
        type=Path,
        default=None,
        help="Optional path to offline pipeline-shaped response fixture JSON.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Guarded live smoke eval mode. Requires AI_FINDER_LIVE_EVAL=true.",
    )
    parser.add_argument(
        "--live-preflight",
        action="store_true",
        help="Print value-redacted live smoke eval preflight status without live calls.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.live_preflight:
            print(run_live_eval_preflight())
            return 0
        if args.live:
            print(run_live_eval_guard())
            return 1
        if args.responses is None:
            print(run_schema_eval(args.matrix))
            return 0
        report, passed = run_response_eval(args.matrix, args.responses)
        print(report)
        return 0 if passed else 1
    except (SmokeScenarioMatrixError, SmokeResponseFixtureError, SmokeLiveEvalGuardError) as exc:
        print(f"Smoke scenario eval failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
