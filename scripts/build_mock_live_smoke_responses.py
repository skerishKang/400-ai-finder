from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.run_smoke_eval import DEFAULT_MATRIX_PATH, load_matrix, validate_matrix


def build_mock_response_for_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    scenario_id = str(scenario["id"])
    site_id = str(scenario["site_id"])
    pass_criteria = scenario.get("pass_criteria", {})
    answer_keywords = pass_criteria.get("answer_contains_any")
    keyword = answer_keywords[0] if isinstance(answer_keywords, list) and answer_keywords else "홈페이지"

    fallback_required = pass_criteria.get("fallback_required") is True
    fallback_when_no_source = pass_criteria.get("fallback_when_no_source") is True
    min_sources = pass_criteria.get("min_sources", 0)

    if fallback_required or fallback_when_no_source or min_sources == 0:
        return {
            "scenario_id": scenario_id,
            "site_id": site_id,
            "answer": f"{keyword} 관련 정보는 출처가 부족하므로 홈페이지에서 직접 확인해 주세요.",
            "sources": [],
            "fallback": True,
        }

    expected_domain = str(scenario["expected_domain"])
    return {
        "scenario_id": scenario_id,
        "site_id": site_id,
        "answer": f"{keyword} 관련 정보는 해당 기관 홈페이지에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": keyword,
                "url": f"https://{expected_domain}/mock-live-smoke-eval/{scenario_id}",
            }
        ],
        "fallback": False,
    }


def build_mock_live_response_fixture(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "_meta": {
            "version": "1.0.0",
            "stage": 51,
            "description": (
                "Mock live smoke eval response fixture generated without provider, "
                "fetch, network, or app pipeline calls."
            ),
        },
        "responses": [build_mock_response_for_scenario(scenario) for scenario in scenarios],
    }


def run_build(matrix_path: Path, output_path: Path | None = None) -> str:
    scenarios = validate_matrix(load_matrix(matrix_path))
    fixture = build_mock_live_response_fixture(scenarios)
    serialized = json.dumps(fixture, ensure_ascii=False, indent=2) + "\n"

    if output_path is not None:
        output_path.write_text(serialized, encoding="utf-8")
        return f"Mock live smoke responses written: {output_path}"

    return serialized.rstrip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build mock live smoke eval responses without external calls."
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        default=DEFAULT_MATRIX_PATH,
        help=f"Path to smoke scenario matrix JSON. Default: {DEFAULT_MATRIX_PATH}",
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(run_build(args.matrix, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
