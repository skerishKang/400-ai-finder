import json
from pathlib import Path

from scripts.build_mock_live_smoke_responses import (
    build_mock_live_response_fixture,
    build_mock_response_for_scenario,
    run_build,
)
from scripts.run_smoke_eval import (
    DEFAULT_MATRIX_PATH,
    build_response_eval_summary,
    evaluate_response_fixture,
    load_matrix,
    validate_matrix,
    validate_response_fixture,
)


def _scenarios() -> list[dict]:
    return validate_matrix(load_matrix(DEFAULT_MATRIX_PATH))


def test_build_mock_response_for_grounded_scenario() -> None:
    scenario = next(scenario for scenario in _scenarios() if scenario["id"] == "bukgu-01")

    response = build_mock_response_for_scenario(scenario)

    assert response["scenario_id"] == "bukgu-01"
    assert response["site_id"] == "bukgu_gwangju"
    assert response["fallback"] is False
    assert response["sources"]
    assert response["sources"][0]["url"].startswith("https://bukgu.gwangju.kr/")


def test_build_mock_response_for_fallback_scenario() -> None:
    scenario = next(scenario for scenario in _scenarios() if scenario["id"] == "gwangju-07")

    response = build_mock_response_for_scenario(scenario)

    assert response["scenario_id"] == "gwangju-07"
    assert response["site_id"] == "gwangju_go_kr"
    assert response["fallback"] is True
    assert response["sources"] == []
    assert "직접 확인" in response["answer"]


def test_mock_live_response_fixture_covers_all_scenarios() -> None:
    scenarios = _scenarios()
    fixture = build_mock_live_response_fixture(scenarios)

    assert fixture["_meta"]["stage"] == 51
    assert len(fixture["responses"]) == 14
    assert {response["scenario_id"] for response in fixture["responses"]} == {
        scenario["id"] for scenario in scenarios
    }


def test_mock_live_response_fixture_passes_response_judge() -> None:
    scenarios = _scenarios()
    fixture = build_mock_live_response_fixture(scenarios)

    responses_by_id = validate_response_fixture(fixture, scenarios)
    results = evaluate_response_fixture(scenarios, responses_by_id)
    summary = build_response_eval_summary(results)

    assert summary["total"] == 14
    assert summary["passed"] == 14
    assert summary["failed"] == 0


def test_run_build_writes_output_file(tmp_path: Path) -> None:
    output_path = tmp_path / "mock_live_responses.json"

    message = run_build(DEFAULT_MATRIX_PATH, output_path)

    assert "Mock live smoke responses written" in message
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data["responses"]) == 14
