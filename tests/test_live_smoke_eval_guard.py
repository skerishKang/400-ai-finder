import pytest

from scripts.run_smoke_eval import (
    LIVE_EVAL_ENV_VAR,
    SmokeLiveEvalGuardError,
    is_live_eval_enabled,
    run_live_eval_guard,
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
