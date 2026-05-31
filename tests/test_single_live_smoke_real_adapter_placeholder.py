import pytest

from scripts.run_smoke_eval import DEFAULT_MATRIX_PATH, load_matrix, validate_matrix
from scripts.single_live_smoke_adapter import (
    DEFAULT_SINGLE_SCENARIO_ADAPTER_NAME,
    SingleLiveSmokeAdapterError,
    get_single_scenario_adapter,
)
from scripts.single_live_smoke_fake_adapter import FAKE_SINGLE_LIVE_ADAPTER_NAME
from scripts.single_live_smoke_real_adapter import (
    REAL_SINGLE_LIVE_ADAPTER_NAME,
    SingleLiveSmokeRealAdapterNotImplementedError,
    build_real_single_live_result_payload,
)


def _scenario_by_id(scenario_id: str) -> dict:
    scenarios = validate_matrix(load_matrix(DEFAULT_MATRIX_PATH))
    return next(scenario for scenario in scenarios if scenario["id"] == scenario_id)


def test_stage74_real_adapter_placeholder_has_explicit_name() -> None:
    assert REAL_SINGLE_LIVE_ADAPTER_NAME == "real-single-scenario-live-adapter"


def test_stage74_real_adapter_placeholder_is_non_executing() -> None:
    scenario = _scenario_by_id("bukgu-01")

    with pytest.raises(
        SingleLiveSmokeRealAdapterNotImplementedError,
        match="not implemented",
    ):
        build_real_single_live_result_payload(scenario)


def test_stage74_default_adapter_remains_fake() -> None:
    assert DEFAULT_SINGLE_SCENARIO_ADAPTER_NAME == FAKE_SINGLE_LIVE_ADAPTER_NAME
    assert get_single_scenario_adapter() is not build_real_single_live_result_payload


def test_stage74_real_adapter_is_not_selectable_yet() -> None:
    with pytest.raises(SingleLiveSmokeAdapterError, match="Unsupported single-scenario adapter"):
        get_single_scenario_adapter(REAL_SINGLE_LIVE_ADAPTER_NAME)


def test_stage112_real_adapter_placeholder_error_message_points_to_fake_path() -> None:
    scenario = _scenario_by_id("bukgu-01")

    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError) as exc_info:
        build_real_single_live_result_payload(scenario)

    assert str(exc_info.value) == (
        "Real single-scenario adapter is not implemented. Use the fake adapter path."
    )


def test_stage114_real_adapter_placeholder_error_is_not_implemented_error_subclass() -> None:
    assert issubclass(SingleLiveSmokeRealAdapterNotImplementedError, NotImplementedError)


def test_stage116_real_adapter_placeholder_raises_base_not_implemented_error() -> None:
    scenario = _scenario_by_id("bukgu-01")

    with pytest.raises(NotImplementedError):
        build_real_single_live_result_payload(scenario)


def test_stage118_real_adapter_placeholder_does_not_mutate_scenario() -> None:
    scenario = _scenario_by_id("bukgu-01")
    expected_scenario = dict(scenario)

    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(scenario)

    assert scenario == expected_scenario
