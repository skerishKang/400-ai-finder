import json
from pathlib import Path

from scripts.export_live_smoke_artifact import export_live_artifact_to_pipeline_results
from scripts.export_smoke_responses import export_pipeline_results_fixture
from scripts.run_smoke_eval import (
    DEFAULT_MATRIX_PATH,
    build_response_eval_summary,
    evaluate_response_fixture,
    load_matrix,
    validate_matrix,
    validate_response_fixture,
)


LIVE_ARTIFACT_PATH = Path("tests/fixtures/live_smoke_result_artifact.json")
FORBIDDEN_VALUE_SUBSTRINGS = (
    "api_key=",
    "authorization:",
    "bearer ",
    "cookie:",
    "set-cookie:",
    "sessionid=",
    "secret=",
    "token=",
    "sk-",
    "raw request",
    "raw response",
)
REQUIRED_RESULT_KEYS = {
    "scenario_id",
    "site_id",
    "query",
    "status",
    "answer",
    "sources",
    "fallback_used",
    "ok",
    "answer_ok",
    "diagnostics",
}
ALLOWED_STATUSES = {
    "answered",
    "fallback",
    "error",
    "skipped",
    "pending_configuration",
}


def load_live_artifact() -> dict:
    return json.loads(LIVE_ARTIFACT_PATH.read_text(encoding="utf-8"))


def test_live_artifact_metadata_matches_stage56_schema() -> None:
    artifact = load_live_artifact()

    assert artifact["_meta"]["version"] == "1.0.0"
    assert artifact["_meta"]["artifact_type"] == "live_smoke_eval_results"
    assert artifact["_meta"]["stage"] == 57
    assert artifact["_meta"]["matrix_path"] == str(DEFAULT_MATRIX_PATH)
    assert artifact["_meta"]["scenario_count"] == 14
    assert artifact["_meta"]["offline_boundary"] is False
    assert artifact["run"]["status"] == "completed"
    assert artifact["run"]["live_opt_in"] is True
    assert artifact["run"]["duration_ms"] > 0


def test_live_artifact_redaction_flags_are_false() -> None:
    artifact = load_live_artifact()
    redaction = artifact["_meta"]["redaction"]

    assert redaction == {
        "secrets_persisted": False,
        "cookies_persisted": False,
        "request_headers_persisted": False,
        "raw_provider_payloads_persisted": False,
        "raw_prompts_persisted": False,
    }


def test_live_artifact_covers_all_matrix_scenarios() -> None:
    artifact = load_live_artifact()
    scenarios = validate_matrix(load_matrix(DEFAULT_MATRIX_PATH))

    artifact_ids = {result["scenario_id"] for result in artifact["results"]}
    matrix_ids = {scenario["id"] for scenario in scenarios}

    assert len(artifact["results"]) == 14
    assert artifact_ids == matrix_ids
    assert artifact["_meta"]["scenario_count"] == len(scenarios)


def test_live_artifact_result_shape_is_redaction_safe() -> None:
    artifact = load_live_artifact()
    serialized = json.dumps(artifact, ensure_ascii=False).lower()

    for forbidden in FORBIDDEN_VALUE_SUBSTRINGS:
        assert forbidden not in serialized

    for result in artifact["results"]:
        assert REQUIRED_RESULT_KEYS <= result.keys()
        assert result["status"] in ALLOWED_STATUSES
        assert isinstance(result["sources"], list)
        assert isinstance(result["fallback_used"], bool)
        assert isinstance(result["ok"], bool)
        assert isinstance(result["answer_ok"], bool)
        assert isinstance(result["diagnostics"], dict)
        assert "source_count" in result["diagnostics"]
        assert "normalized_source_count" in result["diagnostics"]

        for source in result["sources"]:
            assert source["title"]
            assert source["url"].startswith("https://")


def test_live_artifact_converts_to_existing_response_judge_path() -> None:
    artifact = load_live_artifact()
    scenarios = validate_matrix(load_matrix(DEFAULT_MATRIX_PATH))

    pipeline_results = export_live_artifact_to_pipeline_results(artifact)
    exported_fixture = export_pipeline_results_fixture(pipeline_results)
    responses_by_id = validate_response_fixture(exported_fixture, scenarios)
    results = evaluate_response_fixture(scenarios, responses_by_id)
    summary = build_response_eval_summary(results)

    assert summary["total"] == 14
    assert summary["passed"] == 14
    assert summary["failed"] == 0
    assert summary["failed_results"] == []
