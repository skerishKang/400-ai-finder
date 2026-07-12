import pytest

from scripts.run_smoke_eval import (
    LIVE_EVAL_ENV_VAR,
    LIVE_PREFLIGHT_CONFIG_NAMES,
    SmokeLiveEvalGuardError,
    build_live_eval_preflight,
    is_live_eval_enabled,
    run_live_eval_guard,
    run_live_eval_preflight,
)


def test_live_eval_is_disabled_by_default() -> None:
    assert is_live_eval_enabled({}) is False


def test_live_eval_requires_exact_true_opt_in() -> None:
    assert is_live_eval_enabled({LIVE_EVAL_ENV_VAR: "true"}) is True
    assert is_live_eval_enabled({LIVE_EVAL_ENV_VAR: "TRUE"}) is True
    assert is_live_eval_enabled({LIVE_EVAL_ENV_VAR: " false "}) is False
    assert is_live_eval_enabled({LIVE_EVAL_ENV_VAR: "1"}) is False


def test_live_eval_guard_rejects_missing_opt_in() -> None:
    with pytest.raises(SmokeLiveEvalGuardError, match="AI_FINDER_LIVE_EVAL=true"):
        run_live_eval_guard({})


def test_live_eval_guard_reports_not_implemented_after_opt_in() -> None:
    message = run_live_eval_guard({LIVE_EVAL_ENV_VAR: "true"})

    assert "explicitly enabled" in message
    assert "not implemented" in message
    assert "No live provider, fetch, or pipeline calls were made" in message


def test_live_preflight_reports_missing_config_names_without_values() -> None:
    summary = build_live_eval_preflight({})

    assert summary["live_enabled"] is False
    assert summary["missing"] == list(LIVE_PREFLIGHT_CONFIG_NAMES)
    assert all(item["present"] is False for item in summary["items"])


def test_live_preflight_reports_present_config_names_without_values() -> None:
    env = {
        LIVE_EVAL_ENV_VAR: "true",
        "AI_FINDER_LIVE_PROVIDER": "very-sensitive-provider-value",
        "AI_FINDER_LIVE_FETCH_PROVIDER": "very-sensitive-fetch-value",
    }

    report = run_live_eval_preflight(env)

    assert "Live smoke eval preflight" in report
    assert "Live opt-in: enabled" in report
    assert f"- {LIVE_EVAL_ENV_VAR}: set" in report
    assert "- AI_FINDER_LIVE_PROVIDER: set" in report
    assert "- AI_FINDER_LIVE_FETCH_PROVIDER: set" in report
    assert "very-sensitive-provider-value" not in report
    assert "very-sensitive-fetch-value" not in report


def test_live_preflight_does_not_enable_live_execution() -> None:
    report = run_live_eval_preflight({LIVE_EVAL_ENV_VAR: "true"})

    assert "Status: preflight completed" in report
    assert "No live provider, fetch, network, or pipeline calls were made." in report
