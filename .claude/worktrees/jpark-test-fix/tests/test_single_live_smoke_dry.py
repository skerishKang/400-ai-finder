import pytest

from scripts.export_live_smoke_artifact import export_live_artifact_to_pipeline_results
from scripts.export_smoke_responses import export_pipeline_results_fixture
from scripts.run_single_live_smoke_dry import (
    SingleLiveSmokeDryRunError,
    build_single_live_smoke_dry_artifact,
    build_single_live_smoke_dry_payload,
    find_single_scenario,
)
from scripts.run_smoke_eval import (
    DEFAULT_MATRIX_PATH,
    build_response_eval_summary,
    evaluate_response_fixture,
    load_matrix,
    validate_matrix,
    validate_response_fixture,
)
from scripts.write_live_smoke_artifact import build_live_smoke_artifact


REQUIRED_PAYLOAD_KEYS = {
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


def _scenarios() -> list[dict]:
    return validate_matrix(load_matrix(DEFAULT_MATRIX_PATH))


@pytest.mark.parametrize(
    "selector",
    ["", "   ", "all", "ALL", " All ", "\tall\n", "*"],
)
def test_stage68_rejects_empty_or_broad_scenario_selectors(selector: str) -> None:
    scenarios = _scenarios()

    with pytest.raises(
        SingleLiveSmokeDryRunError,
        match="non-empty scenario id|required|cannot execute all scenarios",
    ):
        find_single_scenario(scenarios, selector)


@pytest.mark.parametrize("selector", ["all", "ALL", " All ", "\tall\n", "*"])
def test_stage68_broad_selectors_fail_before_artifact_build(selector: str) -> None:
    with pytest.raises(SingleLiveSmokeDryRunError, match="cannot execute all scenarios"):
        build_single_live_smoke_dry_artifact(
            selector,
            created_at="2026-05-30T15:00:00Z",
        )


def test_stage65_rejects_all_scenario_shortcuts() -> None:
    scenarios = _scenarios()

    with pytest.raises(SingleLiveSmokeDryRunError, match="cannot execute all scenarios"):
        find_single_scenario(scenarios, "all")

    with pytest.raises(SingleLiveSmokeDryRunError, match="cannot execute all scenarios"):
        find_single_scenario(scenarios, "*")


def test_stage65_rejects_unknown_scenario_id() -> None:
    scenarios = _scenarios()

    with pytest.raises(SingleLiveSmokeDryRunError, match="Unknown smoke scenario id"):
        find_single_scenario(scenarios, "missing-01")


def test_stage65_builds_stage62_compatible_single_payload() -> None:
    payload = build_single_live_smoke_dry_payload("bukgu-01")

    assert set(payload.keys()) == REQUIRED_PAYLOAD_KEYS
    assert payload["scenario_id"] == "bukgu-01"
    assert payload["site_id"] == "bukgu_gwangju"
    assert payload["query"] == "민원서식 어디서 받아?"
    assert payload["status"] == "answered"
    assert payload["fallback_used"] is False
    assert payload["ok"] is True
    assert payload["answer_ok"] is True
    assert payload["sources"] == [
        {
            "title": "민원서식 service_navigation",
            "url": "https://bukgu.gwangju.kr/stage65-dry/bukgu-01",
        }
    ]


def test_stage65_builds_fallback_payload_without_sources_for_low_confidence() -> None:
    payload = build_single_live_smoke_dry_payload("gwangju-07")

    assert set(payload.keys()) == REQUIRED_PAYLOAD_KEYS
    assert payload["scenario_id"] == "gwangju-07"
    assert payload["site_id"] == "gwangju_go_kr"
    assert payload["status"] == "fallback"
    assert payload["fallback_used"] is True
    assert payload["sources"] == []
    assert "홈페이지에서 직접 확인" in payload["answer"]


def test_stage65_payload_can_be_written_through_stage60_writer() -> None:
    payload = build_single_live_smoke_dry_payload("bukgu-01")
    artifact = build_live_smoke_artifact(
        [payload],
        matrix_path=str(DEFAULT_MATRIX_PATH),
        created_at="2026-05-30T15:00:00Z",
        live_opt_in=False,
        provider_name="offline-dry-run",
        fetch_provider_name="offline-dry-run",
    )

    assert artifact["_meta"]["artifact_type"] == "live_smoke_eval_results"
    assert artifact["_meta"]["scenario_count"] == 1
    assert artifact["run"]["live_opt_in"] is False
    assert artifact["run"]["provider_name"] == "offline-dry-run"
    assert artifact["results"][0]["scenario_id"] == "bukgu-01"


def test_stage65_artifact_exports_to_pipeline_shape() -> None:
    artifact = build_single_live_smoke_dry_artifact(
        "bukgu-01",
        created_at="2026-05-30T15:00:00Z",
    )
    exported = export_live_artifact_to_pipeline_results(artifact)

    assert exported["_meta"]["stage"] == 58
    assert len(exported["results"]) == 1
    assert exported["results"][0] == {
        "scenario_id": "bukgu-01",
        "result": {
            "site_id": "bukgu_gwangju",
            "answer": "민원서식 관련 정보는 bukgu_gwangju 홈페이지의 Stage 65 dry-run 출처에서 확인할 수 있습니다.",
            "sources": [
                {
                    "title": "민원서식 service_navigation",
                    "url": "https://bukgu.gwangju.kr/stage65-dry/bukgu-01",
                }
            ],
            "ok": True,
            "answer_ok": True,
            "fallback_used": False,
        },
    }


def test_stage65_exported_single_result_passes_existing_judge_for_single_slice() -> None:
    artifact = build_single_live_smoke_dry_artifact(
        "bukgu-01",
        created_at="2026-05-30T15:00:00Z",
    )
    exported = export_live_artifact_to_pipeline_results(artifact)
    exported_fixture = export_pipeline_results_fixture(exported)
    scenarios = [scenario for scenario in _scenarios() if scenario["id"] == "bukgu-01"]
    responses_by_id = validate_response_fixture(exported_fixture, scenarios)
    results = evaluate_response_fixture(scenarios, responses_by_id)
    summary = build_response_eval_summary(results)

    assert summary == {
        "total": 1,
        "passed": 1,
        "failed": 0,
        "failed_results": [],
    }
