"""MVP no-live tests for the Stage #811 locked controlled-live UX runner.

The Stage #811 MVP implements only the dry-run surface:

* Question input (str, nonblank, <= MAX_QUESTION_LEN).
* Fixed bukgu_gwangju + requests + stub plan output.
* Dry-run envelope with execution_allowed=False.
* Zero actual network / process / thread execution.

Deliberately NOT covered here (deferred to the next issues):

* The double opt-in gate (allow flag + acknowledgement match).
* The injected execution_boundary test seam and its timeout /
  error / evidence normalization.

These tests verify the MVP-only contract: the runner is a pure
validator + envelope builder with no side effects and no leakage of
the raw question or secret canaries into the response, the plan, the
exception, or the repr.
"""

from __future__ import annotations

import ast
import importlib
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest

from src.demo import controlled_live_ux_runner as runner_module
from src.demo.controlled_live_smoke_contract import (
    APPROVED_EXECUTION_MODE,
    APPROVED_FETCH_PROVIDER,
    APPROVED_LLM_PROVIDER,
    APPROVED_SITE_ID,
)
from src.demo.controlled_live_ux_runner import (
    DRY_RUN_MODE,
    INVALID_REQUEST_CODE,
    LockedControlledLiveUxError,
    LockedControlledLiveUxRequest,
    LockedControlledLiveUxResponse,
    MAX_QUESTION_LEN,
    QUESTION_INVALID_CODE,
    REQUIRED_ACKNOWLEDGEMENT,
    run_locked_controlled_live_ux,
)


FORBIDDEN_IMPORTS = {
    "requests",
    "httpx",
    "urllib",
    "urllib.request",
    "subprocess",
    "threading",
    "asyncio",
    "concurrent",
    "concurrent.futures",
    "firecrawl",
    "playwright",
    "scrapy",
    "crawl4ai",
    "browser_use",
    "browser",
}


SECRET_CANARIES = (
    "Bearer secret-token",
    "Authorization: Bearer token-abc123",
    "https://user:pass@example.test/path",
    "header-like: x-api-key=abc123",
    "body-like secret=abc123",
)


# --- Helpers --------------------------------------------------------------

def _request(
    question: str = "민원서식 어디서 받아?",
    *,
    allow: bool = False,
    ack: str | None = None,
) -> LockedControlledLiveUxRequest:
    return LockedControlledLiveUxRequest(
        question=question,
        allow_controlled_live=allow,
        acknowledgement=ack,
    )


def _check_plan(plan: Any) -> None:
    assert plan.site_id == APPROVED_SITE_ID
    assert plan.fetch_provider == APPROVED_FETCH_PROVIDER
    assert plan.llm_provider == APPROVED_LLM_PROVIDER
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
    assert plan.execution_mode == APPROVED_EXECUTION_MODE
    assert plan.isolated_process_group is True
    assert plan.kill_process_group_on_timeout is True
    assert plan.explicit_user_post_count == 1
    assert plan.separate_fetch_attempts_observable is True


# --- MVP: dry-run with valid question returns fixed plan + envelope -----

def test_dry_run_returns_fixed_plan_and_envelope() -> None:
    response = run_locked_controlled_live_ux(request=_request())

    assert isinstance(response, LockedControlledLiveUxResponse)
    assert response.mode == DRY_RUN_MODE
    assert response.execution_allowed is False
    _check_plan(response.plan)

    result = response.result
    assert result["ok"] is True
    assert result["answer_ok"] is False
    assert result["answer_status"] == "fallback_no_match"
    assert result["source_weak"] is True
    assert result["sources"] == []
    assert result["fetch_diagnostic"] is None


# --- MVP: dry-run regardless of any opt-in flag values ------------------

@pytest.mark.parametrize(
    "allow, ack",
    [
        (False, None),
        (False, ""),
        (False, REQUIRED_ACKNOWLEDGEMENT),
        (True, None),
        (True, ""),
        (True, REQUIRED_ACKNOWLEDGEMENT),
        (True, "wrong-acknowledgement"),
    ],
)
def test_dry_run_returned_regardless_of_opt_in_flags(
    allow: bool,
    ack: str | None,
) -> None:
    response = run_locked_controlled_live_ux(
        request=_request(allow=allow, ack=ack),
    )

    assert response.mode == DRY_RUN_MODE
    assert response.execution_allowed is False
    _check_plan(response.plan)

    result = response.result
    assert result["ok"] is True
    assert result["answer_ok"] is False
    assert result["answer_status"] == "fallback_no_match"
    assert result["source_weak"] is True


# --- MVP: question validation -------------------------------------------

@pytest.mark.parametrize(
    "question",
    [
        None,
        42,
        True,
        False,
        "",
        "   ",
        "\n\t  ",
        "x" * (MAX_QUESTION_LEN + 1),
        ["a", "b"],
        {"question": "x"},
    ],
)
def test_invalid_question_raises_fixed_safe_code(question: Any) -> None:
    with pytest.raises(LockedControlledLiveUxError) as exc_info:
        run_locked_controlled_live_ux(
            request=LockedControlledLiveUxRequest(question=question),
        )
    assert exc_info.value.code == QUESTION_INVALID_CODE
    assert str(exc_info.value) == QUESTION_INVALID_CODE
    assert QUESTION_INVALID_CODE in repr(exc_info.value)


def test_max_question_len_at_boundary_is_accepted() -> None:
    response = run_locked_controlled_live_ux(
        request=_request(question="가" * MAX_QUESTION_LEN),
    )
    assert response.mode == DRY_RUN_MODE
    assert response.execution_allowed is False


def test_max_question_len_plus_one_is_rejected() -> None:
    with pytest.raises(LockedControlledLiveUxError) as exc_info:
        run_locked_controlled_live_ux(
            request=_request(question="가" * (MAX_QUESTION_LEN + 1)),
        )
    assert exc_info.value.code == QUESTION_INVALID_CODE


def test_non_request_input_raises_invalid_request() -> None:
    with pytest.raises(LockedControlledLiveUxError) as exc_info:
        run_locked_controlled_live_ux(request="not a request")  # type: ignore[arg-type]
    assert exc_info.value.code == INVALID_REQUEST_CODE


# --- MVP: secret canary not leaked in response / plan / exception -------

@pytest.mark.parametrize("canary", SECRET_CANARIES)
def test_canary_question_does_not_leak_into_response_repr_or_result(
    canary: str,
) -> None:
    response = run_locked_controlled_live_ux(
        request=LockedControlledLiveUxRequest(
            question=canary,
            allow_controlled_live=True,
            acknowledgement=REQUIRED_ACKNOWLEDGEMENT,
        ),
    )

    response_repr = repr(response)
    plan_repr = repr(response.plan)
    result_repr = repr(response.result)
    result_str = str(response.result)

    assert canary not in response_repr
    assert canary not in plan_repr
    assert canary not in result_repr
    assert canary not in result_str


@pytest.mark.parametrize("canary", SECRET_CANARIES)
def test_canary_question_does_not_leak_into_exception_text(
    canary: str,
) -> None:
    # 1. As a too-long question (raises question_invalid).
    long_canary = canary + "x" * (MAX_QUESTION_LEN + 1)
    with pytest.raises(LockedControlledLiveUxError) as exc_info:
        run_locked_controlled_live_ux(
            request=LockedControlledLiveUxRequest(question=long_canary),
        )
    assert canary not in str(exc_info.value)
    assert canary not in repr(exc_info.value)

    # 2. As a list-shaped non-string question (raises question_invalid).
    with pytest.raises(LockedControlledLiveUxError) as exc_info:
        run_locked_controlled_live_ux(
            request=LockedControlledLiveUxRequest(question=[canary]),
        )
    assert canary not in str(exc_info.value)
    assert canary not in repr(exc_info.value)


# --- MVP: no forbidden imports (AST check) ------------------------------

def test_module_ast_has_no_forbidden_imports() -> None:
    path = Path(runner_module.__file__)
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

    leaked = imported_names & FORBIDDEN_IMPORTS
    assert not leaked, f"Forbidden imports detected: {leaked}"


# --- MVP: import + dry-run side-effect check ----------------------------

def test_import_is_pure() -> None:
    imported = importlib.import_module("src.demo.controlled_live_ux_runner")

    assert imported.run_locked_controlled_live_ux is run_locked_controlled_live_ux
    assert imported.LockedControlledLiveUxRequest is LockedControlledLiveUxRequest
    assert imported.LockedControlledLiveUxResponse is LockedControlledLiveUxResponse
    assert imported.LockedControlledLiveUxError is LockedControlledLiveUxError


def test_dry_run_does_not_call_network_or_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    network_calls: list[str] = []
    process_calls: list[str] = []

    original_socket = socket.socket
    original_popen = subprocess.Popen

    def _tracking_socket(*args: Any, **kwargs: Any) -> Any:
        network_calls.append("socket.socket")
        return original_socket(*args, **kwargs)

    def _tracking_popen(*args: Any, **kwargs: Any) -> Any:
        process_calls.append("subprocess.Popen")
        return original_popen(*args, **kwargs)

    monkeypatch.setattr(socket, "socket", _tracking_socket)
    monkeypatch.setattr(subprocess, "Popen", _tracking_popen)

    response = run_locked_controlled_live_ux(request=_request())

    assert response.mode == DRY_RUN_MODE
    assert network_calls == []
    assert process_calls == []


# --- MVP: module exposes the documented public surface -----------------

def test_module_exposes_required_symbols() -> None:
    assert hasattr(runner_module, "REQUIRED_ACKNOWLEDGEMENT")
    assert hasattr(runner_module, "DRY_RUN_MODE")
    assert hasattr(runner_module, "MAX_QUESTION_LEN")
    assert hasattr(runner_module, "QUESTION_INVALID_CODE")
    assert hasattr(runner_module, "INVALID_REQUEST_CODE")
    assert hasattr(runner_module, "LockedControlledLiveUxError")
    assert hasattr(runner_module, "LockedControlledLiveUxRequest")
    assert hasattr(runner_module, "LockedControlledLiveUxResponse")
    assert hasattr(runner_module, "run_locked_controlled_live_ux")
