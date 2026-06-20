"""Pure unit tests for the Stage #807 controlled-live smoke contract."""

from __future__ import annotations

import ast
import dataclasses
import importlib
import math
from pathlib import Path
from typing import Any

import pytest

from src.demo import controlled_live_smoke_contract as contract_module
from src.demo.controlled_live_smoke_contract import (
    ControlledLiveSmokeContractError,
    ControlledLiveSmokePlan,
    ControlledLiveSmokeRequest,
    validate_controlled_live_smoke_request,
)


FORBIDDEN_IMPORTS = {
    "requests",
    "subprocess",
    "threading",
    "asyncio",
    "concurrent",
    "concurrent.futures",
    "firecrawl",
}

SECRET_CANARIES = (
    "Bearer secret-token",
    "Authorization: Bearer token-abc123",
    "https://user:pass@example.test/path",
    "header-like: x-api-key=abc123",
    "body-like secret=abc123",
)


def _approved_request(**overrides: Any) -> ControlledLiveSmokeRequest:
    data = {
        "site_id": "bukgu_gwangju",
        "fetch_provider": "requests",
        "llm_provider": "stub",
        "max_pages": 1,
        "max_depth": 0,
        "max_sitemaps": 0,
        "max_enrich_pages": 0,
        "retry_count": 0,
        "request_timeout_s": 5.0,
        "total_budget_s": 10.0,
        "persist_scenarios": False,
        "persist_snapshots": False,
        "persist_cache": False,
        "persist_config": False,
        "persist_source_grounding": False,
        "temp_only_output": True,
        "deterministic_cleanup": True,
        "audit_path": None,
        "retain_artifacts": False,
        "execution_mode": "subprocess_process_group",
        "isolated_process_group": True,
        "kill_process_group_on_timeout": True,
        "explicit_user_post_count": 1,
        "separate_fetch_attempts_observable": True,
    }
    data.update(overrides)
    return ControlledLiveSmokeRequest(**data)


def _expect_code(request: ControlledLiveSmokeRequest, code: str) -> None:
    with pytest.raises(ControlledLiveSmokeContractError) as exc_info:
        validate_controlled_live_smoke_request(request)
    assert exc_info.value.code == code
    rendered = str(exc_info.value)
    assert rendered == code
    assert code in repr(exc_info.value)


def test_approved_envelope_normalizes_to_immutable_plan() -> None:
    request = _approved_request()

    plan = validate_controlled_live_smoke_request(request)

    assert isinstance(plan, ControlledLiveSmokePlan)
    assert dataclasses.is_dataclass(plan)
    assert dataclasses.fields(plan)
    assert plan.site_id == "bukgu_gwangju"
    assert plan.fetch_provider == "requests"
    assert plan.llm_provider == "stub"
    assert plan.max_pages == 1
    assert plan.max_depth == 0
    assert plan.max_sitemaps == 0
    assert plan.max_enrich_pages == 0
    assert plan.retry_count == 0
    assert plan.request_timeout_s == 5.0
    assert plan.total_budget_s == 10.0
    assert plan.persist_scenarios is False
    assert plan.persist_snapshots is False
    assert plan.persist_cache is False
    assert plan.persist_config is False
    assert plan.persist_source_grounding is False
    assert plan.temp_only_output is True
    assert plan.deterministic_cleanup is True
    assert plan.audit_path is None
    assert plan.retain_artifacts is False
    assert plan.execution_mode == "subprocess_process_group"
    assert plan.isolated_process_group is True
    assert plan.kill_process_group_on_timeout is True
    assert plan.explicit_user_post_count == 1
    assert plan.separate_fetch_attempts_observable is True
    assert dataclasses.is_dataclass(ControlledLiveSmokePlan)
    assert dataclasses.fields(ControlledLiveSmokePlan)


@pytest.mark.parametrize(
    "field_name, value, code",
    [
        ("site_id", "gwangju_seo", "site_not_allowed"),
        ("fetch_provider", "firecrawl", "fetch_provider_not_allowed"),
        ("fetch_provider", "httpx", "fetch_provider_not_allowed"),
        ("llm_provider", "openai", "llm_provider_not_allowed"),
    ],
)
def test_provider_and_site_allowlist_violations_are_stable(
    field_name: str,
    value: str,
    code: str,
) -> None:
    _expect_code(_approved_request(**{field_name: value}), code)


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"max_pages": None}, "limits_invalid"),
        ({"max_pages": True}, "limits_invalid"),
        ({"max_pages": "1"}, "limits_invalid"),
        ({"max_pages": 2}, "limits_invalid"),
        ({"max_pages": -1}, "limits_invalid"),
        ({"max_depth": 1}, "limits_invalid"),
        ({"max_depth": -1}, "limits_invalid"),
        ({"max_depth": True}, "limits_invalid"),
        ({"max_sitemaps": 1}, "limits_invalid"),
        ({"max_enrich_pages": 1}, "limits_invalid"),
        ({"retry_count": 1}, "limits_invalid"),
        ({"retry_count": -1}, "limits_invalid"),
        ({"retry_count": True}, "limits_invalid"),
    ],
)
def test_limits_and_retry_reject_bad_type_range_or_bool(
    overrides: dict[str, Any],
    code: str,
) -> None:
    _expect_code(_approved_request(**overrides), code)


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"request_timeout_s": True}, "time_budget_invalid"),
        ({"request_timeout_s": "5"}, "time_budget_invalid"),
        ({"request_timeout_s": 0}, "time_budget_invalid"),
        ({"request_timeout_s": -1.0}, "time_budget_invalid"),
        ({"request_timeout_s": 5.0001}, "time_budget_invalid"),
        ({"request_timeout_s": math.inf}, "time_budget_invalid"),
        ({"request_timeout_s": -math.inf}, "time_budget_invalid"),
        ({"request_timeout_s": math.nan}, "time_budget_invalid"),
        ({"total_budget_s": True}, "time_budget_invalid"),
        ({"total_budget_s": "10"}, "time_budget_invalid"),
        ({"total_budget_s": 0}, "time_budget_invalid"),
        ({"total_budget_s": -1.0}, "time_budget_invalid"),
        ({"total_budget_s": 10.0001}, "time_budget_invalid"),
        ({"total_budget_s": 4.9999}, "time_budget_invalid"),
        ({"total_budget_s": math.inf}, "time_budget_invalid"),
        ({"total_budget_s": -math.inf}, "time_budget_invalid"),
        ({"total_budget_s": math.nan}, "time_budget_invalid"),
    ],
)
def test_timeout_and_budget_reject_bad_type_range_or_nonfinite(
    overrides: dict[str, Any],
    code: str,
) -> None:
    _expect_code(_approved_request(**overrides), code)


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"persist_scenarios": True}, "persistence_not_allowed"),
        ({"persist_snapshots": True}, "persistence_not_allowed"),
        ({"persist_cache": True}, "persistence_not_allowed"),
        ({"persist_config": True}, "persistence_not_allowed"),
        ({"persist_source_grounding": True}, "persistence_not_allowed"),
        ({"temp_only_output": False}, "persistence_not_allowed"),
        ({"deterministic_cleanup": False}, "persistence_not_allowed"),
        ({"audit_path": "/tmp/audit.jsonl"}, "persistence_not_allowed"),
        ({"audit_path": ""}, "persistence_not_allowed"),
        ({"retain_artifacts": True}, "persistence_not_allowed"),
    ],
)
def test_persistence_retention_and_audit_path_are_rejected(
    overrides: dict[str, Any],
    code: str,
) -> None:
    _expect_code(_approved_request(**overrides), code)


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"execution_mode": "in_process"}, "execution_mode_not_allowed"),
        ({"execution_mode": "thread"}, "execution_mode_not_allowed"),
        ({"execution_mode": "async"}, "execution_mode_not_allowed"),
        ({"execution_mode": "daemon"}, "execution_mode_not_allowed"),
        ({"execution_mode": "subprocess_without_isolation"}, "execution_mode_not_allowed"),
        ({"isolated_process_group": False}, "execution_mode_not_allowed"),
        ({"kill_process_group_on_timeout": False}, "execution_mode_not_allowed"),
        ({"isolated_process_group": "true"}, "execution_mode_not_allowed"),
        ({"kill_process_group_on_timeout": "true"}, "execution_mode_not_allowed"),
    ],
)
def test_execution_mode_and_process_group_flags_are_rejected(
    overrides: dict[str, Any],
    code: str,
) -> None:
    _expect_code(_approved_request(**overrides), code)


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"explicit_user_post_count": 0}, "observability_invalid"),
        ({"explicit_user_post_count": 2}, "observability_invalid"),
        ({"explicit_user_post_count": True}, "observability_invalid"),
        ({"explicit_user_post_count": "1"}, "observability_invalid"),
        ({"separate_fetch_attempts_observable": False}, "observability_invalid"),
        ({"separate_fetch_attempts_observable": "true"}, "observability_invalid"),
    ],
)
def test_observability_contract_is_rejected_when_not_exact(
    overrides: dict[str, Any],
    code: str,
) -> None:
    _expect_code(_approved_request(**overrides), code)


def test_approved_plan_repr_does_not_echo_secret_like_values() -> None:
    request = _approved_request(
        site_id="bukgu_gwangju",
        fetch_provider="requests",
        llm_provider="stub",
    )
    plan = validate_controlled_live_smoke_request(request)
    rendered = repr(plan)

    for canary in SECRET_CANARIES:
        assert canary not in rendered


@pytest.mark.parametrize("canary", SECRET_CANARIES)
@pytest.mark.parametrize(
    "field_name",
    [
        "site_id",
        "fetch_provider",
        "llm_provider",
        "request_timeout_s",
        "total_budget_s",
        "audit_path",
        "execution_mode",
    ],
)
def test_invalid_input_canaries_do_not_leak_in_exception_text(
    canary: str,
    field_name: str,
) -> None:
    request = _approved_request(**{field_name: canary})

    with pytest.raises(ControlledLiveSmokeContractError) as exc_info:
        validate_controlled_live_smoke_request(request)

    rendered = str(exc_info.value)
    assert canary not in rendered
    assert canary not in repr(exc_info.value)


def test_module_ast_has_no_forbidden_execution_network_or_provider_imports() -> None:
    path = Path(contract_module.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))

    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name)
                imported_names.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module)
            imported_names.add(node.module.split(".", 1)[0])

    assert imported_names.isdisjoint(FORBIDDEN_IMPORTS)


def test_import_is_pure_validation_only() -> None:
    imported = importlib.import_module("src.demo.controlled_live_smoke_contract")

    assert imported.ControlledLiveSmokeContractError is ControlledLiveSmokeContractError
    assert imported.ControlledLiveSmokePlan is ControlledLiveSmokePlan
    assert imported.validate_controlled_live_smoke_request is validate_controlled_live_smoke_request
