import copy

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


class _ExplodingScenario(dict):
    def __getitem__(self, key: object) -> object:
        raise AssertionError(f"scenario field should not be read: {key}")

    def items(self):  # type: ignore[override]
        raise AssertionError("scenario fields should not be iterated")


class _ExplodingReprScenario:
    def __repr__(self) -> str:
        raise AssertionError("scenario repr should not be called")


class _ExplodingBoolScenario:
    def __bool__(self) -> bool:
        raise AssertionError("scenario truthiness should not be evaluated")


class _ExplodingLenScenario:
    def __len__(self) -> int:
        raise AssertionError("scenario length should not be checked")


class _ExplodingGetScenario:
    def get(self, key: object, default: object = None) -> object:
        raise AssertionError(f"scenario get lookup should not be called: {key}")


class _ExplodingKeysScenario:
    def keys(self):
        raise AssertionError("scenario keys should not be listed")


class _ExplodingValuesScenario:
    def values(self):
        raise AssertionError("scenario values should not be listed")


class _RaisingContainsScenario:
    def __contains__(self, key: object) -> bool:
        raise AssertionError(f"scenario containment lookup should not be called: {key}")


class _RaisingAttributeScenario:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"scenario attribute lookup should not be called: {name}")


class _RaisingIterScenario:
    def __iter__(self):
        raise AssertionError("scenario iteration should not be started")


class _RaisingStrScenario:
    def __str__(self) -> str:
        raise AssertionError("scenario string conversion should not be called")


class _RaisingEqScenario:
    def __eq__(self, other: object) -> bool:
        raise AssertionError(f"scenario equality comparison should not be called: {other}")


class _RaisingHashScenario:
    def __hash__(self) -> int:
        raise AssertionError("scenario hash lookup should not be called")


class _RaisingFormatScenario:
    def __format__(self, format_spec: str) -> str:
        raise AssertionError(f"scenario format conversion should not be called: {format_spec}")


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


def test_stage120_real_adapter_placeholder_does_not_mutate_nested_scenario_data() -> None:
    scenario = _scenario_by_id("bukgu-01")
    expected_scenario = copy.deepcopy(scenario)

    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(scenario)

    assert scenario == expected_scenario


def test_stage122_real_adapter_placeholder_does_not_require_scenario_shape() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload({})


def test_stage124_real_adapter_placeholder_does_not_inspect_scenario_fields() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_ExplodingScenario())


def test_stage126_real_adapter_placeholder_does_not_iterate_scenario_fields() -> None:
    scenario = _ExplodingScenario({"id": "boom"})

    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(scenario)


def test_stage128_real_adapter_placeholder_does_not_require_dict_like_scenario() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(object())  # type: ignore[arg-type]


def test_stage130_real_adapter_placeholder_does_not_validate_none_scenario() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(None)  # type: ignore[arg-type]


def test_stage132_real_adapter_placeholder_does_not_repr_scenario() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_ExplodingReprScenario())  # type: ignore[arg-type]


def test_stage134_real_adapter_placeholder_does_not_evaluate_scenario_truthiness() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_ExplodingBoolScenario())  # type: ignore[arg-type]


def test_stage136_real_adapter_placeholder_does_not_check_scenario_length() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_ExplodingLenScenario())  # type: ignore[arg-type]


def test_stage138_real_adapter_placeholder_does_not_call_scenario_get() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_ExplodingGetScenario())  # type: ignore[arg-type]


def test_stage140_real_adapter_placeholder_does_not_call_scenario_keys() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_ExplodingKeysScenario())  # type: ignore[arg-type]


def test_stage142_real_adapter_placeholder_does_not_call_scenario_values() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_ExplodingValuesScenario())  # type: ignore[arg-type]


def test_stage144_real_adapter_placeholder_does_not_call_scenario_contains() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_RaisingContainsScenario())  # type: ignore[arg-type]


def test_stage146_real_adapter_placeholder_does_not_call_scenario_attribute() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_RaisingAttributeScenario())  # type: ignore[arg-type]


def test_stage148_real_adapter_placeholder_does_not_start_scenario_iteration() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_RaisingIterScenario())  # type: ignore[arg-type]


def test_stage150_real_adapter_placeholder_does_not_stringify_scenario() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_RaisingStrScenario())  # type: ignore[arg-type]


def test_stage152_real_adapter_placeholder_does_not_compare_scenario_equality() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_RaisingEqScenario())  # type: ignore[arg-type]


def test_stage154_real_adapter_placeholder_does_not_hash_scenario() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_RaisingHashScenario())  # type: ignore[arg-type]


def test_stage156_real_adapter_placeholder_does_not_format_scenario() -> None:
    with pytest.raises(SingleLiveSmokeRealAdapterNotImplementedError):
        build_real_single_live_result_payload(_RaisingFormatScenario())  # type: ignore[arg-type]
