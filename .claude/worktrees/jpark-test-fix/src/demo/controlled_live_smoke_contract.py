"""Validation contract for a future bounded controlled-live smoke runner.

This module intentionally contains no runner, launcher, network client, or
filesystem side effects. It only normalizes and validates the request envelope
that a future controlled-live smoke runner must satisfy before it may execute.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


APPROVED_SITE_ID = "bukgu_gwangju"
APPROVED_FETCH_PROVIDER = "requests"
APPROVED_LLM_PROVIDER = "stub"
APPROVED_EXECUTION_MODE = "subprocess_process_group"


class ControlledLiveSmokeContractError(ValueError):
    """Closed-vocabulary validation error for the smoke contract."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ControlledLiveSmokeRequest:
    site_id: str
    fetch_provider: str
    llm_provider: str
    max_pages: int
    max_depth: int
    max_sitemaps: int
    max_enrich_pages: int
    retry_count: int
    request_timeout_s: float
    total_budget_s: float
    persist_scenarios: bool
    persist_snapshots: bool
    persist_cache: bool
    persist_config: bool
    persist_source_grounding: bool
    temp_only_output: bool
    deterministic_cleanup: bool
    audit_path: str | None
    retain_artifacts: bool
    execution_mode: str
    isolated_process_group: bool
    kill_process_group_on_timeout: bool
    explicit_user_post_count: int
    separate_fetch_attempts_observable: bool


@dataclass(frozen=True)
class ControlledLiveSmokePlan(ControlledLiveSmokeRequest):
    """Normalized approved smoke envelope.

    The plan intentionally contains no executable command, URL, request body,
    header, token, or provider payload.
    """


def _is_int_not_bool(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number_not_bool(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _fail(code: str) -> None:
    raise ControlledLiveSmokeContractError(code)


def _validate_int_cap(value: Any, code: str) -> int:
    if not _is_int_not_bool(value):
        _fail(code)
    return int(value)


def _validate_positive_int(value: Any, code: str) -> int:
    cap = _validate_int_cap(value, code)
    if cap < 0:
        _fail(code)
    return cap


def _validate_timeout(value: Any, code: str) -> float:
    if not _is_number_not_bool(value):
        _fail(code)
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        _fail(code)
    return number


def _validate_budget(value: Any, code: str) -> float:
    if not _is_number_not_bool(value):
        _fail(code)
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        _fail(code)
    return number


def _validate_bool(value: Any, code: str) -> bool:
    if not _is_bool(value):
        _fail(code)
    return bool(value)


def validate_controlled_live_smoke_request(
    request: ControlledLiveSmokeRequest,
) -> ControlledLiveSmokePlan:
    """Validate and normalize the approved no-persist smoke envelope."""

    if not isinstance(request, ControlledLiveSmokeRequest):
        _fail("invalid_request")

    if request.site_id != APPROVED_SITE_ID:
        _fail("site_not_allowed")
    if request.fetch_provider != APPROVED_FETCH_PROVIDER:
        _fail("fetch_provider_not_allowed")
    if request.llm_provider != APPROVED_LLM_PROVIDER:
        _fail("llm_provider_not_allowed")

    max_pages = _validate_int_cap(request.max_pages, "limits_invalid")
    max_depth = _validate_positive_int(request.max_depth, "limits_invalid")
    max_sitemaps = _validate_positive_int(request.max_sitemaps, "limits_invalid")
    max_enrich_pages = _validate_positive_int(request.max_enrich_pages, "limits_invalid")
    retry_count = _validate_positive_int(request.retry_count, "limits_invalid")
    if (
        max_pages != 1
        or max_depth != 0
        or max_sitemaps != 0
        or max_enrich_pages != 0
        or retry_count != 0
    ):
        _fail("limits_invalid")

    request_timeout_s = _validate_timeout(request.request_timeout_s, "time_budget_invalid")
    total_budget_s = _validate_budget(request.total_budget_s, "time_budget_invalid")
    if request_timeout_s > 5 or total_budget_s > 10 or total_budget_s < request_timeout_s:
        _fail("time_budget_invalid")

    persist_scenarios = _validate_bool(request.persist_scenarios, "persistence_not_allowed")
    persist_snapshots = _validate_bool(request.persist_snapshots, "persistence_not_allowed")
    persist_cache = _validate_bool(request.persist_cache, "persistence_not_allowed")
    persist_config = _validate_bool(request.persist_config, "persistence_not_allowed")
    persist_source_grounding = _validate_bool(
        request.persist_source_grounding,
        "persistence_not_allowed",
    )
    temp_only_output = _validate_bool(request.temp_only_output, "persistence_not_allowed")
    deterministic_cleanup = _validate_bool(request.deterministic_cleanup, "persistence_not_allowed")
    retain_artifacts = _validate_bool(request.retain_artifacts, "persistence_not_allowed")

    if (
        persist_scenarios
        or persist_snapshots
        or persist_cache
        or persist_config
        or persist_source_grounding
        or not temp_only_output
        or not deterministic_cleanup
        or request.audit_path is not None
        or retain_artifacts
    ):
        _fail("persistence_not_allowed")

    if request.execution_mode != APPROVED_EXECUTION_MODE:
        _fail("execution_mode_not_allowed")
    isolated_process_group = _validate_bool(
        request.isolated_process_group,
        "execution_mode_not_allowed",
    )
    kill_process_group_on_timeout = _validate_bool(
        request.kill_process_group_on_timeout,
        "execution_mode_not_allowed",
    )
    if not isolated_process_group or not kill_process_group_on_timeout:
        _fail("execution_mode_not_allowed")

    explicit_user_post_count = _validate_positive_int(
        request.explicit_user_post_count,
        "observability_invalid",
    )
    separate_fetch_attempts_observable = _validate_bool(
        request.separate_fetch_attempts_observable,
        "observability_invalid",
    )
    if explicit_user_post_count != 1 or not separate_fetch_attempts_observable:
        _fail("observability_invalid")

    return ControlledLiveSmokePlan(
        site_id=request.site_id,
        fetch_provider=request.fetch_provider,
        llm_provider=request.llm_provider,
        max_pages=max_pages,
        max_depth=max_depth,
        max_sitemaps=max_sitemaps,
        max_enrich_pages=max_enrich_pages,
        retry_count=retry_count,
        request_timeout_s=request_timeout_s,
        total_budget_s=total_budget_s,
        persist_scenarios=persist_scenarios,
        persist_snapshots=persist_snapshots,
        persist_cache=persist_cache,
        persist_config=persist_config,
        persist_source_grounding=persist_source_grounding,
        temp_only_output=temp_only_output,
        deterministic_cleanup=deterministic_cleanup,
        audit_path=request.audit_path,
        retain_artifacts=retain_artifacts,
        execution_mode=request.execution_mode,
        isolated_process_group=isolated_process_group,
        kill_process_group_on_timeout=kill_process_group_on_timeout,
        explicit_user_post_count=explicit_user_post_count,
        separate_fetch_attempts_observable=separate_fetch_attempts_observable,
    )
