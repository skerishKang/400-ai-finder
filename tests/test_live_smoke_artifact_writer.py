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
    extract_results_payload,
    run_write,
)


LIVE_ARTIFACT_PATH = Path("tests/fixtures/live_smoke_result_artifact.json")
PIPELINE_RESULTS_PATH = Path("tests/fixtures/smoke_pipeline_results_roundtrip.json")
CREATED_AT = "2026-05-30T13:15:00Z"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_live_smoke_artifact_from_existing_fixture_results() -> None:
    existing = load_json(LIVE_ARTIFACT_PATH)

    artifact = build_live_smoke_artifact(
        existing["results"],
        matrix_path=str(DEFAULT_MATRIX_PATH),
        created_at=CREATED_AT,
        finished_at=CREATED_AT,
        duration_ms=120000,
    )

    assert artifact["_meta"] == {
        "version": "1.0.0",
        "artifact_type": "live_smoke_eval_results",
        "stage": 60,
        "created_at": CREATED_AT,
        "matrix_path": str(DEFAULT_MATRIX_PATH),
        "scenario_count": 14,
        "offline_boundary": False,
        "redaction": {
            "secrets_persisted": False,
            "cookies_persisted": False,
            "request_headers_persisted": False,
            "raw_provider_payloads_persisted": False,
            "raw_prompts_persisted": False,
        },
    }
    assert artifact["run"]["status"] == "completed"
    assert artifact["run"]["live_opt_in"] is True
    assert artifact["run"]["duration_ms"] == 120000
    assert len(artifact["results"]) == 14
    assert artifact["results"][0]["scenario_id"] == "bukgu-01"


def test_writer_output_roundtrips_through_existing_response_judge() -> None:
    existing = load_json(LIVE_ARTIFACT_PATH)
    scenarios = validate_matrix(load_matrix(DEFAULT_MATRIX_PATH))

    artifact = build_live_smoke_artifact(
        existing["results"],
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


def test_run_write_accepts_pipeline_result_fixture(tmp_path: Path) -> None:
    output_path = tmp_path / "written_live_artifact.json"

    message = run_write(
        PIPELINE_RESULTS_PATH,
        output_path,
        matrix_path=str(DEFAULT_MATRIX_PATH),
        created_at=CREATED_AT,
    )

    assert "Wrote live smoke artifact" in message
    artifact = load_json(output_path)
    assert artifact["_meta"]["artifact_type"] == "live_smoke_eval_results"
    assert artifact["_meta"]["scenario_count"] == 14
    assert artifact["results"][0]["scenario_id"] == "bukgu-01"
    assert artifact["results"][0]["query"] == "bukgu-01"
    assert artifact["results"][0]["status"] == "answered"


def test_extract_results_payload_preserves_direct_result_list() -> None:
    existing = load_json(LIVE_ARTIFACT_PATH)

    extracted = extract_results_payload(existing)

    assert extracted is existing["results"]


def test_build_live_smoke_artifact_rejects_empty_results() -> None:
    with pytest.raises(LiveSmokeArtifactWriterError, match="non-empty list"):
        build_live_smoke_artifact([], matrix_path=str(DEFAULT_MATRIX_PATH))


def test_build_live_smoke_artifact_rejects_duplicate_scenario_id() -> None:
    existing = load_json(LIVE_ARTIFACT_PATH)
    duplicated = list(existing["results"])
    duplicated[1] = {**duplicated[1], "scenario_id": duplicated[0]["scenario_id"]}

    with pytest.raises(LiveSmokeArtifactWriterError, match="duplicate scenario_id"):
        build_live_smoke_artifact(duplicated, matrix_path=str(DEFAULT_MATRIX_PATH))


def test_build_live_smoke_artifact_rejects_unsupported_status() -> None:
    existing = load_json(LIVE_ARTIFACT_PATH)
    bad = [{**existing["results"][0], "status": "not_supported"}]

    with pytest.raises(LiveSmokeArtifactWriterError, match="status is not supported"):
        build_live_smoke_artifact(bad, matrix_path=str(DEFAULT_MATRIX_PATH))
