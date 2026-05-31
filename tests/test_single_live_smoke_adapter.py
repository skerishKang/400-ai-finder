import pytest

from scripts.run_smoke_eval import DEFAULT_MATRIX_PATH, load_matrix, validate_matrix
from scripts.single_live_smoke_adapter import (
    DEFAULT_SINGLE_SCENARIO_ADAPTER_NAME,
    SUPPORTED_SINGLE_SCENARIO_ADAPTER_NAMES,
    SingleLiveSmokeAdapterError,
    build_single_live_adapter_payload,
    get_single_scenario_adapter,
    get_single_scenario_adapter_name,
    supported_single_scenario_adapter_names_message,
    unsupported_single_scenario_adapter_error_message,
)
from scripts.single_live_smoke_fake_adapter import (
    FAKE_SINGLE_LIVE_ADAPTER_NAME,
    build_fake_single_live_result_payload,
)
from scripts.single_live_smoke_real_adapter import REAL_SINGLE_LIVE_ADAPTER_NAME


def _scenario_by_id(scenario_id: str) -> dict:
    scenarios = validate_matrix(load_matrix(DEFAULT_MATRIX_PATH))
    return next(scenario for scenario in scenarios if scenario["id"] == scenario_id)


def test_stage72_default_adapter_name_is_fake_adapter() -> None:
    assert DEFAULT_SINGLE_SCENARIO_ADAPTER_NAME == FAKE_SINGLE_LIVE_ADAPTER_NAME
    assert get_single_scenario_adapter_name() == FAKE_SINGLE_LIVE_ADAPTER_NAME
    assert get_single_scenario_adapter_name("") == FAKE_SINGLE_LIVE_ADAPTER_NAME


def test_stage72_default_adapter_resolves_to_fake_adapter_function() -> None:
    assert get_single_scenario_adapter() is build_fake_single_live_result_payload
    assert get_single_scenario_adapter(FAKE_SINGLE_LIVE_ADAPTER_NAME) is build_fake_single_live_result_payload


def test_stage72_unsupported_adapter_name_is_rejected() -> None:
    with pytest.raises(SingleLiveSmokeAdapterError, match="Unsupported single-scenario adapter"):
        get_single_scenario_adapter("real-provider")


def test_stage72_adapter_payload_matches_fake_payload() -> None:
    scenario = _scenario_by_id("bukgu-01")

    assert build_single_live_adapter_payload(scenario) == build_fake_single_live_result_payload(scenario)


def test_stage72_adapter_payload_preserves_fallback_shape() -> None:
    scenario = _scenario_by_id("gwangju-07")
    payload = build_single_live_adapter_payload(scenario)

    assert payload == build_fake_single_live_result_payload(scenario)
    assert payload["status"] == "fallback"
    assert payload["sources"] == []
    assert payload["fallback_used"] is True


def test_stage76_empty_adapter_name_payload_still_uses_fake_adapter() -> None:
    scenario = _scenario_by_id("bukgu-01")

    assert build_single_live_adapter_payload(
        scenario,
        adapter_name="",
    ) == build_fake_single_live_result_payload(scenario)


def test_stage76_real_placeholder_name_is_rejected_by_payload_helper() -> None:
    scenario = _scenario_by_id("bukgu-01")

    with pytest.raises(SingleLiveSmokeAdapterError, match="Unsupported single-scenario adapter"):
        build_single_live_adapter_payload(
            scenario,
            adapter_name=REAL_SINGLE_LIVE_ADAPTER_NAME,
        )


def test_stage78_supported_adapter_allowlist_contains_only_fake_adapter() -> None:
    assert SUPPORTED_SINGLE_SCENARIO_ADAPTER_NAMES == (FAKE_SINGLE_LIVE_ADAPTER_NAME,)
    assert REAL_SINGLE_LIVE_ADAPTER_NAME not in SUPPORTED_SINGLE_SCENARIO_ADAPTER_NAMES
    assert DEFAULT_SINGLE_SCENARIO_ADAPTER_NAME in SUPPORTED_SINGLE_SCENARIO_ADAPTER_NAMES


def test_stage80_adapter_name_trims_outer_whitespace() -> None:
    padded_name = f"  {FAKE_SINGLE_LIVE_ADAPTER_NAME}\n"

    assert get_single_scenario_adapter_name(padded_name) == FAKE_SINGLE_LIVE_ADAPTER_NAME
    assert get_single_scenario_adapter(padded_name) is build_fake_single_live_result_payload


def test_stage80_adapter_name_matching_remains_case_sensitive() -> None:
    upper_name = FAKE_SINGLE_LIVE_ADAPTER_NAME.upper()

    assert get_single_scenario_adapter_name(upper_name) == upper_name
    with pytest.raises(SingleLiveSmokeAdapterError, match="Unsupported single-scenario adapter"):
        get_single_scenario_adapter(upper_name)


def test_stage80_padded_unknown_adapter_name_is_trimmed_then_rejected() -> None:
    with pytest.raises(SingleLiveSmokeAdapterError, match="Unsupported single-scenario adapter: unknown-adapter"):
        get_single_scenario_adapter("  unknown-adapter\t")


def test_stage82_non_string_adapter_name_is_rejected_before_normalization() -> None:
    with pytest.raises(
        SingleLiveSmokeAdapterError,
        match="Adapter name must be a string or None: int",
    ):
        get_single_scenario_adapter(123)  # type: ignore[arg-type]


def test_stage82_non_string_payload_adapter_name_is_rejected() -> None:
    scenario = _scenario_by_id("bukgu-01")

    with pytest.raises(
        SingleLiveSmokeAdapterError,
        match="Adapter name must be a string or None: list",
    ):
        build_single_live_adapter_payload(
            scenario,
            adapter_name=[],  # type: ignore[arg-type]
        )


def test_stage84_supported_adapter_names_message_is_deterministic() -> None:
    assert supported_single_scenario_adapter_names_message() == FAKE_SINGLE_LIVE_ADAPTER_NAME


def test_stage84_unsupported_adapter_error_lists_supported_adapter_names() -> None:
    with pytest.raises(SingleLiveSmokeAdapterError) as exc_info:
        get_single_scenario_adapter("unknown-adapter")

    message = str(exc_info.value)
    assert "Unsupported single-scenario adapter: unknown-adapter" in message
    assert f"Supported adapters: {FAKE_SINGLE_LIVE_ADAPTER_NAME}" in message


def test_stage84_payload_helper_unsupported_adapter_error_lists_supported_names() -> None:
    scenario = _scenario_by_id("bukgu-01")

    with pytest.raises(SingleLiveSmokeAdapterError) as exc_info:
        build_single_live_adapter_payload(
            scenario,
            adapter_name=REAL_SINGLE_LIVE_ADAPTER_NAME,
        )

    message = str(exc_info.value)
    assert f"Unsupported single-scenario adapter: {REAL_SINGLE_LIVE_ADAPTER_NAME}" in message
    assert f"Supported adapters: {FAKE_SINGLE_LIVE_ADAPTER_NAME}" in message


def test_stage86_unsupported_adapter_error_message_helper_matches_selector_error() -> None:
    expected_message = unsupported_single_scenario_adapter_error_message("unknown-adapter")

    with pytest.raises(SingleLiveSmokeAdapterError) as exc_info:
        get_single_scenario_adapter("unknown-adapter")

    assert str(exc_info.value) == expected_message


def test_stage88_padded_real_placeholder_name_is_trimmed_then_rejected() -> None:
    padded_name = f"  {REAL_SINGLE_LIVE_ADAPTER_NAME}\n"

    with pytest.raises(SingleLiveSmokeAdapterError) as exc_info:
        get_single_scenario_adapter(padded_name)

    message = str(exc_info.value)
    assert f"Unsupported single-scenario adapter: {REAL_SINGLE_LIVE_ADAPTER_NAME}" in message
    assert f"Supported adapters: {FAKE_SINGLE_LIVE_ADAPTER_NAME}" in message


def test_stage90_payload_helper_uses_normalized_adapter_name_for_error() -> None:
    scenario = _scenario_by_id("bukgu-01")
    padded_name = f"\t{REAL_SINGLE_LIVE_ADAPTER_NAME}  "

    with pytest.raises(SingleLiveSmokeAdapterError) as exc_info:
        build_single_live_adapter_payload(
            scenario,
            adapter_name=padded_name,
        )

    message = str(exc_info.value)
    assert f"Unsupported single-scenario adapter: {REAL_SINGLE_LIVE_ADAPTER_NAME}" in message
    assert f"Supported adapters: {FAKE_SINGLE_LIVE_ADAPTER_NAME}" in message


def test_stage92_whitespace_payload_adapter_name_uses_fake_adapter() -> None:
    scenario = _scenario_by_id("bukgu-01")

    assert build_single_live_adapter_payload(
        scenario,
        adapter_name=" \t\n ",
    ) == build_fake_single_live_result_payload(scenario)


def test_stage94_none_payload_adapter_name_uses_fake_adapter() -> None:
    scenario = _scenario_by_id("bukgu-01")

    assert build_single_live_adapter_payload(
        scenario,
        adapter_name=None,
    ) == build_fake_single_live_result_payload(scenario)


def test_stage96_none_adapter_selector_uses_fake_adapter() -> None:
    assert get_single_scenario_adapter_name(None) == FAKE_SINGLE_LIVE_ADAPTER_NAME
    assert get_single_scenario_adapter(None) is build_fake_single_live_result_payload


def test_stage98_whitespace_adapter_selector_uses_fake_adapter() -> None:
    whitespace_name = "   "

    assert get_single_scenario_adapter_name(whitespace_name) == FAKE_SINGLE_LIVE_ADAPTER_NAME
    assert get_single_scenario_adapter(whitespace_name) is build_fake_single_live_result_payload


def test_stage100_empty_adapter_selector_uses_fake_adapter_function() -> None:
    assert get_single_scenario_adapter("") is build_fake_single_live_result_payload


def test_stage102_supported_adapter_payload_uses_fake_payload() -> None:
    scenario = _scenario_by_id("bukgu-01")

    assert build_single_live_adapter_payload(
        scenario,
        adapter_name=FAKE_SINGLE_LIVE_ADAPTER_NAME,
    ) == build_fake_single_live_result_payload(scenario)
