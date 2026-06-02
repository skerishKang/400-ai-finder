from scripts.run_smoke_eval import DEFAULT_MATRIX_PATH, load_matrix, validate_matrix
from scripts.single_live_smoke_fake_adapter import (
    FAKE_SINGLE_LIVE_ADAPTER_NAME,
    OFFLINE_DRY_RUN_PROVIDER_LABEL,
    answer_keyword_from_scenario,
    build_fake_single_live_result_payload,
    source_title_from_scenario,
)


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


def _scenario_by_id(scenario_id: str) -> dict:
    scenarios = validate_matrix(load_matrix(DEFAULT_MATRIX_PATH))
    return next(scenario for scenario in scenarios if scenario["id"] == scenario_id)


def test_stage69_fake_adapter_is_clearly_named_offline_contract() -> None:
    assert FAKE_SINGLE_LIVE_ADAPTER_NAME == "fake-single-scenario-live-adapter"
    assert OFFLINE_DRY_RUN_PROVIDER_LABEL == "offline-dry-run"


def test_stage69_fake_adapter_extracts_answer_keyword_from_pass_criteria() -> None:
    scenario = _scenario_by_id("bukgu-01")

    assert answer_keyword_from_scenario(scenario) == "민원서식"
    assert source_title_from_scenario(scenario, "민원서식") == "민원서식 service_navigation"


def test_stage69_fake_adapter_builds_answered_payload_with_source() -> None:
    scenario = _scenario_by_id("bukgu-01")
    payload = build_fake_single_live_result_payload(scenario)

    assert set(payload.keys()) == REQUIRED_PAYLOAD_KEYS
    assert payload == {
        "scenario_id": "bukgu-01",
        "site_id": "bukgu_gwangju",
        "query": "민원서식 어디서 받아?",
        "status": "answered",
        "answer": "민원서식 관련 정보는 bukgu_gwangju 홈페이지의 Stage 65 dry-run 출처에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식 service_navigation",
                "url": "https://bukgu.gwangju.kr/stage65-dry/bukgu-01",
            }
        ],
        "fallback_used": False,
        "ok": True,
        "answer_ok": True,
    }


def test_stage69_fake_adapter_builds_fallback_payload_without_source() -> None:
    scenario = _scenario_by_id("gwangju-07")
    payload = build_fake_single_live_result_payload(scenario)

    assert set(payload.keys()) == REQUIRED_PAYLOAD_KEYS
    assert payload["scenario_id"] == "gwangju-07"
    assert payload["site_id"] == "gwangju_go_kr"
    assert payload["status"] == "fallback"
    assert payload["sources"] == []
    assert payload["fallback_used"] is True
    assert payload["ok"] is True
    assert payload["answer_ok"] is True
    assert "홈페이지에서 직접 확인" in payload["answer"]


def test_stage199_fake_adapter_falls_back_to_expected_keywords_when_answer_contains_any_empty() -> None:
    scenario = {
        "pass_criteria": {"answer_contains_any": []},
        "expected_keywords": ["첫번째키워드", "두번째키워드"],
    }
    assert answer_keyword_from_scenario(scenario) == "첫번째키워드"


def test_stage199_fake_adapter_falls_back_to_question_when_expected_keywords_empty() -> None:
    scenario = {
        "pass_criteria": {"answer_contains_any": []},
        "expected_keywords": [],
        "question": "테스트 질문입니다",
    }
    assert answer_keyword_from_scenario(scenario) == "테스트 질문입니다"


def test_stage199_fake_adapter_falls_back_to_default_info_when_all_empty() -> None:
    scenario = {
        "pass_criteria": {"answer_contains_any": []},
        "expected_keywords": [],
        "question": "",
    }
    assert answer_keyword_from_scenario(scenario) == "정보"


def test_stage199_fake_adapter_skips_blank_entries_in_expected_keywords() -> None:
    scenario = {
        "expected_keywords": ["  ", "", "실제키워드"],
    }
    assert answer_keyword_from_scenario(scenario) == "실제키워드"
