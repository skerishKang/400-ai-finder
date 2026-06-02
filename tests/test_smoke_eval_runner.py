from pathlib import Path

import pytest

from scripts.run_smoke_eval import (
    DEFAULT_MATRIX_PATH,
    LIVE_EVAL_ENV_VAR,
    LIVE_PREFLIGHT_CONFIG_NAMES,
    SmokeLiveEvalGuardError,
    SmokeResponseFixtureError,
    SmokeScenarioMatrixError,
    build_live_eval_preflight,
    build_response_eval_summary,
    build_summary,
    evaluate_response,
    evaluate_response_fixture,
    format_live_eval_preflight,
    is_live_eval_enabled,
    load_matrix,
    load_response_fixture,
    run_live_eval_guard,
    run_live_eval_preflight,
    run_response_eval,
    run_schema_eval,
    validate_matrix,
    validate_response_fixture,
)

RESPONSE_FIXTURE_PATH = Path("tests/fixtures/smoke_eval_responses.json")


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


def _scenario_list() -> list[dict]:
    matrix = load_matrix(DEFAULT_MATRIX_PATH)
    return validate_matrix(matrix)


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


def test_stage203_evaluate_response_requires_source_title_for_source_domain() -> None:
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["source_domain"] is False
    assert result["checks"]["no_cross_site_urls"] is True
    assert "source_domain" in result["failures"]
    assert "no_cross_site_urls" not in result["failures"]


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
        "answer": "주민등록등본 발급 관련 출처가 부족하므로 홈페이지에서 직접 확인해 주세요.",
        "sources": [],
        "fallback": True,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["checks"]["fallback_when_no_source"] is True


def test_stage201_evaluate_response_accepts_fallback_marker_without_flag() -> None:
    scenario = _scenario_by_id("bukgu-03")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "주민등록등본 발급 관련 출처가 부족하므로 홈페이지에서 직접 확인해 주세요.",
        "sources": [],
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


def test_response_fixture_loads_and_passes_all_scenarios() -> None:
    scenarios = _scenario_list()
    fixture = load_response_fixture(RESPONSE_FIXTURE_PATH)
    responses_by_id = validate_response_fixture(fixture, scenarios)
    results = evaluate_response_fixture(scenarios, responses_by_id)
    summary = build_response_eval_summary(results)

    assert len(responses_by_id) == 14
    assert summary["total"] == 14
    assert summary["passed"] == 14
    assert summary["failed"] == 0
    assert summary["failed_results"] == []


def test_run_response_eval_returns_passed_report() -> None:
    report, passed = run_response_eval(DEFAULT_MATRIX_PATH, RESPONSE_FIXTURE_PATH)

    assert passed is True
    assert "Smoke response eval loaded" in report
    assert "Evaluated responses: 14" in report
    assert "Passed: 14" in report
    assert "Failed: 0" in report
    assert "Status: response eval passed" in report


def test_response_eval_reports_failed_scenario() -> None:
    scenarios = _scenario_list()
    fixture = load_response_fixture(RESPONSE_FIXTURE_PATH)
    responses_by_id = validate_response_fixture(fixture, scenarios)
    responses_by_id["bukgu-01"] = {
        "scenario_id": "bukgu-01",
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청에서 확인할 수 있습니다.",
        "sources": [{"title": "민원서식", "url": "https://gwangju.go.kr/example"}],
        "fallback": False,
    }

    results = evaluate_response_fixture(scenarios, responses_by_id)
    summary = build_response_eval_summary(results)

    assert summary["passed"] == 13
    assert summary["failed"] == 1
    assert summary["failed_results"][0]["scenario_id"] == "bukgu-01"
    assert "source_domain" in summary["failed_results"][0]["failures"]
    assert "no_cross_site_urls" in summary["failed_results"][0]["failures"]


def test_validate_response_fixture_rejects_duplicate_scenario_id() -> None:
    scenarios = _scenario_list()
    fixture = load_response_fixture(RESPONSE_FIXTURE_PATH)
    duplicate = dict(fixture["responses"][0])
    fixture["responses"].append(duplicate)

    with pytest.raises(SmokeResponseFixtureError, match="Duplicate response scenario_id"):
        validate_response_fixture(fixture, scenarios)


def test_validate_response_fixture_rejects_unknown_scenario_id() -> None:
    scenarios = _scenario_list()
    fixture = load_response_fixture(RESPONSE_FIXTURE_PATH)
    fixture["responses"][0] = dict(fixture["responses"][0], scenario_id="unknown-01")

    with pytest.raises(SmokeResponseFixtureError, match="Unknown response scenario_id"):
        validate_response_fixture(fixture, scenarios)


def test_validate_response_fixture_rejects_missing_scenario_id() -> None:
    scenarios = _scenario_list()
    fixture = load_response_fixture(RESPONSE_FIXTURE_PATH)
    fixture["responses"] = fixture["responses"][:-1]

    with pytest.raises(SmokeResponseFixtureError, match="missing scenario_id values"):
        validate_response_fixture(fixture, scenarios)


def test_stage64_live_opt_in_defaults_to_disabled() -> None:
    env = {}

    assert is_live_eval_enabled(env) is False

    with pytest.raises(SmokeLiveEvalGuardError, match=LIVE_EVAL_ENV_VAR):
        run_live_eval_guard(env)


def test_stage64_live_guard_remains_non_executing_even_when_enabled() -> None:
    env = {LIVE_EVAL_ENV_VAR: "true"}

    report = run_live_eval_guard(env)

    assert "explicitly enabled" in report
    assert "not implemented" in report
    assert "No live provider, fetch, or pipeline calls were made." in report


def test_stage64_preflight_reports_missing_config_without_values() -> None:
    summary = build_live_eval_preflight({})
    report = format_live_eval_preflight(summary)

    assert summary["live_enabled"] is False
    assert summary["missing"] == list(LIVE_PREFLIGHT_CONFIG_NAMES)
    assert "Live opt-in: disabled" in report
    for name in LIVE_PREFLIGHT_CONFIG_NAMES:
        assert f"- {name}: missing" in report
    assert "No live provider, fetch, network, or pipeline calls were made." in report


def test_stage64_preflight_reports_set_missing_only_and_redacts_values() -> None:
    env = {
        LIVE_EVAL_ENV_VAR: "true",
        "AI_FINDER_LIVE_PROVIDER": "secret-provider-token-123",
        "AI_FINDER_LIVE_FETCH_PROVIDER": "secret-fetch-token-456",
    }

    summary = build_live_eval_preflight(env)
    report = run_live_eval_preflight(env)

    assert summary["live_enabled"] is True
    assert summary["missing"] == []
    for name in LIVE_PREFLIGHT_CONFIG_NAMES:
        assert f"- {name}: set" in report
    assert "secret-provider-token-123" not in report
    assert "secret-fetch-token-456" not in report
    assert "Status: preflight completed" in report
    assert "No live provider, fetch, network, or pipeline calls were made." in report


def test_stage64_preflight_does_not_treat_non_true_opt_in_as_enabled() -> None:
    env = {
        LIVE_EVAL_ENV_VAR: "1",
        "AI_FINDER_LIVE_PROVIDER": "provider-name-should-not-print",
        "AI_FINDER_LIVE_FETCH_PROVIDER": "fetch-name-should-not-print",
    }

    summary = build_live_eval_preflight(env)
    report = format_live_eval_preflight(summary)

    assert summary["live_enabled"] is False
    assert summary["missing"] == []
    assert "Live opt-in: disabled" in report
    assert "provider-name-should-not-print" not in report
    assert "fetch-name-should-not-print" not in report
