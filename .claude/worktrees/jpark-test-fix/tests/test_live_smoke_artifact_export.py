import json
from pathlib import Path

import pytest

from scripts.export_live_smoke_artifact import (
    LiveSmokeArtifactExportError,
    export_live_artifact_to_pipeline_results,
    load_live_smoke_artifact,
    run_export,
    run_export_eval,
)


LIVE_ARTIFACT_PATH = Path(__file__).resolve().parent / "fixtures" / "live_smoke_result_artifact.json"


def test_export_live_artifact_to_pipeline_results_preserves_14_results() -> None:
    artifact = load_live_smoke_artifact(LIVE_ARTIFACT_PATH)
    exported = export_live_artifact_to_pipeline_results(artifact)

    assert exported["_meta"]["stage"] == 58
    assert len(exported["results"]) == 14
    assert exported["results"][0]["scenario_id"] == "bukgu-01"
    assert exported["results"][0]["result"] == {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "ok": True,
        "answer_ok": True,
        "fallback_used": False,
    }


def test_run_export_writes_pipeline_result_file(tmp_path: Path) -> None:
    output_path = tmp_path / "live_pipeline_results.json"

    message = run_export(LIVE_ARTIFACT_PATH, output_path)

    assert "Exported live smoke artifact results" in message
    exported = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(exported["results"]) == 14
    assert exported["results"][0]["scenario_id"] == "bukgu-01"


def test_run_export_eval_reports_all_live_artifact_responses_passed() -> None:
    report, passed = run_export_eval(LIVE_ARTIFACT_PATH)

    assert passed is True
    assert "Smoke response eval loaded" in report
    assert "Evaluated responses: 14" in report
    assert "Passed: 14" in report
    assert "Failed: 0" in report
    assert "Status: response eval passed" in report


def test_live_artifact_export_rejects_wrong_artifact_type() -> None:
    artifact = load_live_smoke_artifact(LIVE_ARTIFACT_PATH)
    artifact["_meta"]["artifact_type"] = "wrong"

    with pytest.raises(LiveSmokeArtifactExportError, match="artifact_type"):
        export_live_artifact_to_pipeline_results(artifact)


def test_live_artifact_export_rejects_redaction_violation() -> None:
    artifact = load_live_smoke_artifact(LIVE_ARTIFACT_PATH)
    artifact["_meta"]["redaction"]["secrets_persisted"] = True

    with pytest.raises(LiveSmokeArtifactExportError, match="secrets_persisted"):
        export_live_artifact_to_pipeline_results(artifact)


def test_live_artifact_export_rejects_duplicate_scenario_id() -> None:
    artifact = load_live_smoke_artifact(LIVE_ARTIFACT_PATH)
    artifact["results"][1]["scenario_id"] = artifact["results"][0]["scenario_id"]

    with pytest.raises(LiveSmokeArtifactExportError, match="Duplicate live artifact"):
        export_live_artifact_to_pipeline_results(artifact)


def test_load_live_smoke_artifact_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(LiveSmokeArtifactExportError, match="not found"):
        load_live_smoke_artifact(tmp_path / "missing.json")
