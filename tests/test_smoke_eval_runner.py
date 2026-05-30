from pathlib import Path

import pytest

from scripts.run_smoke_eval import (
    DEFAULT_MATRIX_PATH,
    SmokeScenarioMatrixError,
    build_summary,
    evaluate_response,
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


def _scenario_by_id(scenario_id: str) -> dict:
    matrix = load_matrix(DEFAULT_MATRIX_PATH)
    scenarios = validate_matrix(matrix)
    return next(scenario for scenario in scenarios if scenario["id"] == scenario_id)


def test_evaluate_response_passes_grounded_pipeline_shaped_response() -> None:
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["failures"] == []
    assert result["checks"] == {
        "site_id_match": True,
        "min_sources": True,
        "source_domain": True,
        "no_cross_site_urls": True,
        "answer_contains_any": True,
    }


def test_evaluate_response_fails_cross_site_source_url() -> None:
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://gwangju.go.kr/example",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert "source_domain" in result["failures"]
    assert "no_cross_site_urls" in result["failures"]


def test_evaluate_response_fails_when_min_sources_not_met() -> None:
    scenario = _scenario_by_id("gwangju-01")
    response = {
        "site_id": "gwangju_go_kr",
        "answer": "고시공고는 광주시청 홈페이지에서 확인할 수 있습니다.",
        "sources": [],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["min_sources"] is False
    assert "min_sources" in result["failures"]


def test_evaluate_response_fails_when_answer_keyword_missing() -> None:
    scenario = _scenario_by_id("gwangju-02")
    response = {
        "site_id": "gwangju_go_kr",
        "answer": "해당 내용은 광주시청 홈페이지에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "정보공개",
                "url": "https://www.gwangju.go.kr/example",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["answer_contains_any"] is False
    assert "answer_contains_any" in result["failures"]


def test_evaluate_response_accepts_fallback_when_sources_are_empty() -> None:
    scenario = _scenario_by_id("bukgu-03")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "출처가 부족하므로 홈페이지에서 직접 확인해 주세요.",
        "sources": [],
        "fallback": True,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["checks"]["fallback_when_no_source"] is True


def test_evaluate_response_requires_fallback_for_low_confidence_case() -> None:
    scenario = _scenario_by_id("gwangju-07")
    response = {
        "site_id": "gwangju_go_kr",
        "answer": "외계인 등록증은 광주시청에서 신청할 수 있습니다.",
        "sources": [],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["fallback_required"] is False
    assert "fallback_required" in result["failures"]


def test_evaluate_response_detects_site_id_mismatch() -> None:
    scenario = _scenario_by_id("bukgu-06")
    response = {
        "site_id": "gwangju_go_kr",
        "answer": "지원금 관련 정보는 홈페이지에서 직접 확인해 주세요.",
        "sources": [],
        "fallback": True,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["site_id_match"] is False
    assert "site_id_match" in result["failures"]
