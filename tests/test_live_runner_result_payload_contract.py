import json
from pathlib import Path

import pytest

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
from scripts.write_live_smoke_artifact import (
    LiveSmokeArtifactWriterError,
    build_live_smoke_artifact,
)


PAYLOAD_PATH = Path("tests/fixtures/live_runner_result_payloads.json")
CREATED_AT = "2026-05-30T14:00:00Z"
REQUIRED_KEYS = {
    "scenario_id",
    "site_id",
    "query",
    "status",
    "answer",
    "sources",
    "fallback_used",
    "ok",
    "answer_ok",
}
ALLOWED_STATUSES = {
    "answered",
    "fallback",
    "error",
    "skipped",
    "pending_configuration",
}


def load_payload() -> dict:
    return json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))


def test_live_runner_payload_fixture_metadata() -> None:
    payload = load_payload()

    assert payload["_meta"] == {
        "version": "1.0.0",
        "stage": 62,
        "payload_type": "live_runner_result_payloads",
        "description": "Minimal already-produced result payloads expected from a future live runner before Stage 60 artifact writing.",
    }


def test_live_runner_payload_covers_matrix_scenarios() -> None:
    payload = load_payload()
    scenarios = validate_matrix(load_matrix(DEFAULT_MATRIX_PATH))

    payload_ids = {result["scenario_id"] for result in payload["results"]}
    matrix_ids = {scenario["id"] for scenario in scenarios}

    assert len(payload["results"]) == 14
    assert payload_ids == matrix_ids


def test_live_runner_payload_uses_minimal_contract_shape() -> None:
    payload = load_payload()

    for result in payload["results"]:
        assert set(result.keys()) == REQUIRED_KEYS
        assert isinstance(result["scenario_id"], str) and result["scenario_id"]
        assert isinstance(result["site_id"], str) and result["site_id"]
        assert isinstance(result["query"], str) and result["query"]
        assert result["status"] in ALLOWED_STATUSES
        assert isinstance(result["answer"], str)
        assert isinstance(result["sources"], list)
        assert isinstance(result["fallback_used"], bool)
        assert isinstance(result["ok"], bool)
        assert isinstance(result["answer_ok"], bool)

        for source in result["sources"]:
            assert set(source.keys()) == {"title", "url"}
            assert isinstance(source["title"], str)
            assert source["url"].startswith("https://")


def test_live_runner_payload_builds_writer_artifact() -> None:
    payload = load_payload()

    artifact = build_live_smoke_artifact(
        payload["results"],
        matrix_path=str(DEFAULT_MATRIX_PATH),
        created_at=CREATED_AT,
    )

    assert artifact["_meta"]["artifact_type"] == "live_smoke_eval_results"
    assert artifact["_meta"]["stage"] == 60
    assert artifact["_meta"]["scenario_count"] == 14
    assert artifact["_meta"]["redaction"] == {
        "secrets_persisted": False,
        "cookies_persisted": False,
        "request_headers_persisted": False,
        "raw_provider_payloads_persisted": False,
        "raw_prompts_persisted": False,
    }
    assert len(artifact["results"]) == 14
    assert artifact["results"][0]["diagnostics"] == {
        "source_count": 1,
        "normalized_source_count": 1,
        "error_type": None,
        "error_message": None,
    }


def test_live_runner_payload_roundtrips_through_export_judge_path() -> None:
    payload = load_payload()
    scenarios = validate_matrix(load_matrix(DEFAULT_MATRIX_PATH))

    artifact = build_live_smoke_artifact(
        payload["results"],
        matrix_path=str(DEFAULT_MATRIX_PATH),
        created_at=CREATED_AT,
    )
    pipeline_results = export_live_artifact_to_pipeline_results(artifact)
    exported_fixture = export_pipeline_results_fixture(pipeline_results)
    responses_by_id = validate_response_fixture(exported_fixture, scenarios)
    results = evaluate_response_fixture(scenarios, responses_by_id)
    summary = build_response_eval_summary(results)

    assert summary["total"] == 14
    assert summary["passed"] == 14
    assert summary["failed"] == 0
    assert summary["failed_results"] == []


def test_live_runner_payload_rejects_missing_required_field() -> None:
    payload = load_payload()
    bad_result = dict(payload["results"][0])
    bad_result.pop("query")

    with pytest.raises(LiveSmokeArtifactWriterError, match="query"):
        build_live_smoke_artifact([bad_result], matrix_path=str(DEFAULT_MATRIX_PATH))


def test_live_runner_payload_rejects_non_boolean_flags() -> None:
    payload = load_payload()
    bad_result = {**payload["results"][0], "ok": "true"}

    with pytest.raises(LiveSmokeArtifactWriterError, match="ok"):
        build_live_smoke_artifact([bad_result], matrix_path=str(DEFAULT_MATRIX_PATH))
