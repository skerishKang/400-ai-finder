"""Pure no-live tests for the Stage #819 command/approval guard.

The guard is the LAST gate before any real controlled-live execution.
It is locked to be no-live: it only inspects the request envelope
and returns a closed-vocabulary decision. These tests pin that
contract.
"""

from __future__ import annotations

import ast
import importlib
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest

from src.demo import controlled_live_command_guard as guard_module
from src.demo.controlled_live_command_guard import (
    ALL_DECISION_REASONS,
    CommandDecision,
    DECISION_APPROVED,
    DECISION_DENIED_ACK_MISSING,
    DECISION_DENIED_NO_FLAG,
    DECISION_DENIED_WRONG_ACK,
    evaluate_command,
)
from src.demo.controlled_live_ux_runner import (
    REQUIRED_ACKNOWLEDGEMENT,
    LockedControlledLiveUxRequest,
)


FORBIDDEN_IMPORTS = {
    "requests", "httpx", "urllib", "urllib.request", "subprocess",
    "threading", "asyncio", "concurrent", "concurrent.futures",
    "firecrawl", "playwright", "scrapy", "crawl4ai", "browser_use",
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

def _req(*, allow: bool = False, ack: Any = None) -> LockedControlledLiveUxRequest:
    return LockedControlledLiveUxRequest(
        question="민원서식 어디서 받아?",
        allow_controlled_live=allow,
        acknowledgement=ack,
    )


# --- Closed-vocabulary reasons -------------------------------------------

def test_all_decision_reasons_is_closed_vocabulary() -> None:
    assert ALL_DECISION_REASONS == (
        DECISION_APPROVED,
        DECISION_DENIED_NO_FLAG,
        DECISION_DENIED_ACK_MISSING,
        DECISION_DENIED_WRONG_ACK,
    )


def test_command_decision_is_frozen() -> None:
    decision = CommandDecision(True, DECISION_APPROVED)
    with pytest.raises((AttributeError, Exception)):
        decision.allowed = False  # type: ignore[misc]


# --- Default path: no opt-in -------------------------------------------

def test_guard_default_request_denies_with_no_flag() -> None:
    decision = evaluate_command(_req())
    assert isinstance(decision, CommandDecision)
    assert decision.allowed is False
    assert decision.reason == DECISION_DENIED_NO_FLAG


# --- Partial approval: flag set, ack missing or wrong --------------------

def test_guard_flag_set_ack_missing_denies() -> None:
    decision = evaluate_command(_req(allow=True, ack=None))
    assert decision.allowed is False
    assert decision.reason == DECISION_DENIED_ACK_MISSING


@pytest.mark.parametrize(
    "ack",
    [
        None,
        "",
        "I_ACKNOWLEDGE",  # wrong / incomplete
        "I_ACKNOWLEDGE_CONTROLLED_LIVE ",  # trailing space
        " I_ACKNOWLEDGE_CONTROLLED_LIVE",  # leading space
        "i_acknowledge_controlled_live",  # wrong case
        42,  # wrong type
        True,
        False,
        ["I_ACKNOWLEDGE_CONTROLLED_LIVE"],
    ],
)
def test_guard_partial_approval_denies(ack: Any) -> None:
    decision = evaluate_command(_req(allow=True, ack=ack))
    assert decision.allowed is False
    assert decision.reason in (DECISION_DENIED_ACK_MISSING, DECISION_DENIED_WRONG_ACK)


def test_guard_flag_set_wrong_ack_string_denies_with_wrong_ack_reason() -> None:
    decision = evaluate_command(_req(allow=True, ack="not-the-right-ack"))
    assert decision.allowed is False
    assert decision.reason == DECISION_DENIED_WRONG_ACK


# --- Flag not strictly True ----------------------------------------------

@pytest.mark.parametrize("allow", [False, None, 0, 1, "true", "yes"])
def test_guard_flag_not_strictly_true_denies(allow: Any) -> None:
    decision = evaluate_command(_req(allow=allow, ack=REQUIRED_ACKNOWLEDGEMENT))
    assert decision.allowed is False
    assert decision.reason == DECISION_DENIED_NO_FLAG


# --- Exact approval -------------------------------------------------------

def test_guard_exact_match_allows() -> None:
    decision = evaluate_command(
        _req(allow=True, ack=REQUIRED_ACKNOWLEDGEMENT),
    )
    assert decision.allowed is True
    assert decision.reason == DECISION_APPROVED


def test_guard_non_request_input_denies() -> None:
    decision = evaluate_command("not a request")  # type: ignore[arg-type]
    assert decision.allowed is False
    assert decision.reason == DECISION_DENIED_NO_FLAG


# --- Decision never echoes the raw question ------------------------------

@pytest.mark.parametrize("canary", SECRET_CANARIES)
def test_guard_decision_does_not_echo_canary_question(canary: str) -> None:
    request = LockedControlledLiveUxRequest(
        question=canary,
        allow_controlled_live=True,
        acknowledgement=REQUIRED_ACKNOWLEDGEMENT,
    )
    decision = evaluate_command(request)
    rendered = repr(decision)
    assert canary not in rendered
    assert canary not in str(decision.reason)


@pytest.mark.parametrize("canary", SECRET_CANARIES)
def test_guard_decision_does_not_echo_canary_in_denial(canary: str) -> None:
    request = LockedControlledLiveUxRequest(
        question=canary,
        allow_controlled_live=False,
        acknowledgement=canary,
    )
    decision = evaluate_command(request)
    rendered = repr(decision)
    assert canary not in rendered


# --- Module AST / import / side-effect safety net -----------------------

def test_guard_module_ast_has_no_forbidden_imports() -> None:
    path = Path(guard_module.__file__)
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


def test_guard_module_import_is_pure() -> None:
    imported = importlib.import_module("src.demo.controlled_live_command_guard")
    assert imported.evaluate_command is evaluate_command
    assert imported.CommandDecision is CommandDecision
    assert imported.DECISION_APPROVED == DECISION_APPROVED


def test_guard_evaluate_command_does_not_call_network_or_process(
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

    # Exercise every branch: default deny, partial deny, exact approve.
    evaluate_command(_req())
    evaluate_command(_req(allow=True, ack=None))
    evaluate_command(_req(allow=True, ack="wrong"))
    evaluate_command(_req(allow=True, ack=REQUIRED_ACKNOWLEDGEMENT))

    assert network_calls == []
    assert process_calls == []


def test_guard_module_exposes_required_symbols() -> None:
    assert hasattr(guard_module, "DECISION_APPROVED")
    assert hasattr(guard_module, "DECISION_DENIED_NO_FLAG")
    assert hasattr(guard_module, "DECISION_DENIED_ACK_MISSING")
    assert hasattr(guard_module, "DECISION_DENIED_WRONG_ACK")
    assert hasattr(guard_module, "ALL_DECISION_REASONS")
    assert hasattr(guard_module, "CommandDecision")
    assert hasattr(guard_module, "evaluate_command")
