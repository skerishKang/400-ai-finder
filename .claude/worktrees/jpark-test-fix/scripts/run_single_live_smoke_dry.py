"""Build a single-scenario live smoke dry-run artifact.

Stage 65 is still fully offline. This module does not call live providers,
fetch providers, external networks, Firecrawl, or the app pipeline. It only
selects one scenario from the smoke matrix, builds one Stage 62-compatible
result payload through the Stage 72 adapter interface defaulting to fake data,
and writes it through the Stage 60 artifact writer.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from scripts.run_smoke_eval import DEFAULT_MATRIX_PATH, load_matrix, validate_matrix
from scripts.single_live_smoke_adapter import build_single_live_adapter_payload
from scripts.write_live_smoke_artifact import build_live_smoke_artifact


class SingleLiveSmokeDryRunError(ValueError):
    """Raised when the single-scenario dry-run contract is violated."""


def find_single_scenario(scenarios: list[dict[str, Any]], scenario_id: str) -> dict[str, Any]:
    """Return exactly one scenario by id, or raise a narrow dry-run error."""
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise SingleLiveSmokeDryRunError("A non-empty scenario id is required.")
    if scenario_id.strip().lower() in {"all", "*"}:
        raise SingleLiveSmokeDryRunError("Single-scenario dry-run cannot execute all scenarios.")

    matches = [scenario for scenario in scenarios if scenario["id"] == scenario_id]
    if not matches:
        raise SingleLiveSmokeDryRunError(f"Unknown smoke scenario id: {scenario_id}")
    if len(matches) != 1:
        raise SingleLiveSmokeDryRunError(f"Scenario id is not unique: {scenario_id}")
    return matches[0]


def build_single_scenario_payload(scenario: dict[str, Any]) -> dict[str, Any]:
    """Build one Stage 62-compatible dry result payload without live calls."""
    return build_single_live_adapter_payload(scenario)


def build_single_live_smoke_dry_payload(
    scenario_id: str,
    *,
    matrix_path: Path = DEFAULT_MATRIX_PATH,
) -> dict[str, Any]:
    """Load the matrix and build a one-result Stage 62-compatible payload."""
    scenarios = validate_matrix(load_matrix(matrix_path))
    scenario = find_single_scenario(scenarios, scenario_id)
    return build_single_scenario_payload(scenario)


def build_single_live_smoke_dry_artifact(
    scenario_id: str,
    *,
    matrix_path: Path = DEFAULT_MATRIX_PATH,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a one-result artifact through the Stage 60 writer boundary."""
    payload = build_single_live_smoke_dry_payload(scenario_id, matrix_path=matrix_path)
    return build_live_smoke_artifact(
        [payload],
        matrix_path=str(matrix_path),
        created_at=created_at,
        run_status="completed",
        live_opt_in=False,
        provider_name="offline-dry-run",
        fetch_provider_name="offline-dry-run",
    )


def write_single_live_smoke_dry_artifact(
    scenario_id: str,
    output_path: Path,
    *,
    matrix_path: Path = DEFAULT_MATRIX_PATH,
    created_at: str | None = None,
) -> str:
    """Write one single-scenario dry artifact to disk."""
    artifact = build_single_live_smoke_dry_artifact(
        scenario_id,
        matrix_path=matrix_path,
        created_at=created_at,
    )
    import json

    output_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return f"Wrote single-scenario live smoke dry artifact: {output_path}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build one offline single-scenario live smoke dry-run artifact."
    )
    parser.add_argument(
        "--scenario-id",
        required=True,
        help="Exactly one smoke scenario id. Values such as 'all' are rejected.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output live artifact JSON path.",
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        default=DEFAULT_MATRIX_PATH,
        help=f"Path to smoke scenario matrix JSON. Default: {DEFAULT_MATRIX_PATH}",
    )
    parser.add_argument(
        "--created-at",
        default=None,
        help="Optional UTC timestamp for deterministic tests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        print(
            write_single_live_smoke_dry_artifact(
                args.scenario_id,
                args.output,
                matrix_path=args.matrix,
                created_at=args.created_at,
            )
        )
    except SingleLiveSmokeDryRunError as exc:
        print(f"Single live smoke dry-run failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
