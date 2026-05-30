import json
from pathlib import Path

import pytest

from scripts.export_smoke_responses import (
    SmokePipelineExportError,
    export_pipeline_result_response,
    export_pipeline_results_fixture,
    load_pipeline_results,
    run_export,
    run_export_eval,
)
from scripts.run_smoke_eval import (
    DEFAULT_MATRIX_PATH,
    build_response_eval_summary,
    evaluate_response_fixture,
    load_matrix,
    validate_matrix,
    validate_response_fixture,
)


def test_export_pipeline_result_response_preserves_core_fields() -> None:
    result = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es",
                "snippet": "extra field ignored",
            }
        ],
        "ok": True,
        "answer_ok": True,
        "fallback_used": False,
    }

    exported = export_pipeline_result_response("bukgu-01", result)

    assert exported == {
        "scenario_id": "bukgu-01",
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es",
            }
        ],
        "fallback": False,
    }


def test_export_pipeline_result_response_marks_fallback_from_result_flags() -> None:
    result = {
        "site_id": "bukgu_gwangju",
        "answer": "홈페이지에서 직접 확인해 주세요.",
        "sources": [],
        "ok": True,
        "answer_ok": True,
        "fallback_used": True,
    }

    exported = export_pipeline_result_response("bukgu-03", result)

    assert exported["fallback"] is True


def test_export_pipeline_results_fixture_wraps_responses() -> None:
    fixture = {
        "results": [
            {
                "scenario_id": "bukgu-01",
                "result": {
                    "site_id": "bukgu_gwangju",
                    "answer": "민원서식 안내",
                    "sources": [{"title": "민원서식", "url": "https://bukgu.gwangju.kr/a"}],
                    "ok": True,
                    "answer_ok": True,
                },
            }
        ]
    }

    exported = export_pipeline_results_fixture(fixture)

    assert exported["_meta"]["stage"] == 43
    assert exported["responses"][0]["scenario_id"] == "bukgu-01"
    assert exported["responses"][0]["site_id"] == "bukgu_gwangju"


def test_export_rejects_duplicate_scenario_id() -> None:
    fixture = {
        "results": [
            {"scenario_id": "bukgu-01", "result": {}},
            {"scenario_id": "bukgu-01", "result": {}},
        ]
    }

    with pytest.raises(SmokePipelineExportError, match="Duplicate pipeline result scenario_id"):
        export_pipeline_results_fixture(fixture)


def test_export_rejects_missing_scenario_id() -> None:
    fixture = {"results": [{"result": {}}]}

    with pytest.raises(SmokePipelineExportError, match="invalid scenario_id"):
        export_pipeline_results_fixture(fixture)


def test_run_export_writes_output_file(tmp_path: Path) -> None:
    input_path = tmp_path / "pipeline_results.json"
    output_path = tmp_path / "smoke_responses.json"
    input_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "scenario_id": "bukgu-01",
                        "result": {
                            "site_id": "bukgu_gwangju",
                            "answer": "민원서식 안내",
                            "sources": [
                                {
                                    "title": "민원서식",
                                    "url": "https://bukgu.gwangju.kr/a",
                                }
                            ],
                            "ok": True,
                            "answer_ok": True,
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    message = run_export(input_path, output_path)

    assert "Exported smoke eval responses" in message
    exported = json.loads(output_path.read_text(encoding="utf-8"))
    assert exported["responses"][0]["scenario_id"] == "bukgu-01"


def test_load_pipeline_results_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SmokePipelineExportError, match="Pipeline results file not found"):
        load_pipeline_results(tmp_path / "missing.json")


ROUNDTRIP_PIPELINE_RESULTS_PATH = Path(
    "tests/fixtures/smoke_pipeline_results_roundtrip.json"
)


def test_exported_roundtrip_fixture_passes_smoke_response_eval() -> None:
    matrix = load_matrix(DEFAULT_MATRIX_PATH)
    scenarios = validate_matrix(matrix)

    pipeline_results = load_pipeline_results(ROUNDTRIP_PIPELINE_RESULTS_PATH)
    exported_fixture = export_pipeline_results_fixture(pipeline_results)

    responses_by_id = validate_response_fixture(exported_fixture, scenarios)
    results = evaluate_response_fixture(scenarios, responses_by_id)
    summary = build_response_eval_summary(results)

    assert len(exported_fixture["responses"]) == 14
    assert summary["total"] == 14
    assert summary["passed"] == 14
    assert summary["failed"] == 0
    assert summary["failed_results"] == []


def test_run_export_eval_reports_all_roundtrip_responses_passed() -> None:
    report, passed = run_export_eval(ROUNDTRIP_PIPELINE_RESULTS_PATH)

    assert passed is True
    assert "Smoke response eval loaded" in report
    assert "Evaluated responses: 14" in report
    assert "Passed: 14" in report
    assert "Failed: 0" in report
    assert "Status: response eval passed" in report
