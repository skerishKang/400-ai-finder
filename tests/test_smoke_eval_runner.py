from pathlib import Path

import pytest

from scripts.run_smoke_eval import (
    DEFAULT_MATRIX_PATH,
    SmokeScenarioMatrixError,
    build_summary,
    load_matrix,
    run_schema_eval,
    validate_matrix,
)


def test_stage40_matrix_loads_and_validates() -> None:
    matrix = load_matrix(DEFAULT_MATRIX_PATH)
    scenarios = validate_matrix(matrix)

    assert len(scenarios) == 14


def test_stage40_matrix_summary_counts() -> None:
    matrix = load_matrix(DEFAULT_MATRIX_PATH)
    scenarios = validate_matrix(matrix)
    summary = build_summary(scenarios)

    assert summary["total"] == 14
    assert summary["sites"] == {
        "bukgu_gwangju": 7,
        "gwangju_go_kr": 7,
    }
    assert summary["categories"] == {
        "ambiguous_query": 2,
        "department_contact": 2,
        "document_lookup": 2,
        "fee_hour_location": 2,
        "low_confidence_fallback": 2,
        "service_navigation": 4,
    }


def test_schema_eval_report_is_human_readable() -> None:
    report = run_schema_eval(DEFAULT_MATRIX_PATH)

    assert "Smoke scenario matrix loaded" in report
    assert "Total scenarios: 14" in report
    assert "- bukgu_gwangju: 7" in report
    assert "- gwangju_go_kr: 7" in report
    assert "- service_navigation: 4" in report
    assert "Status: schema-only eval passed" in report


def test_validate_matrix_rejects_missing_required_scenario_key() -> None:
    invalid_matrix = {
        "scenarios": [
            {
                "id": "invalid-01",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": [],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                },
            }
        ]
    }

    with pytest.raises(SmokeScenarioMatrixError, match="missing required keys"):
        validate_matrix(invalid_matrix)


def test_validate_matrix_rejects_duplicate_ids() -> None:
    scenario = {
        "id": "duplicate-01",
        "site_id": "bukgu_gwangju",
        "category": "service_navigation",
        "question": "민원서식 어디서 받아?",
        "expected_domain": "bukgu.gwangju.kr",
        "expected_keywords": [],
        "pass_criteria": {
            "site_id_match": True,
            "min_sources": 1,
            "no_cross_site_urls": True,
        },
    }

    with pytest.raises(SmokeScenarioMatrixError, match="Duplicate scenario id"):
        validate_matrix({"scenarios": [scenario, dict(scenario)]})


def test_load_matrix_rejects_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"

    with pytest.raises(SmokeScenarioMatrixError, match="Matrix file not found"):
        load_matrix(missing_path)
