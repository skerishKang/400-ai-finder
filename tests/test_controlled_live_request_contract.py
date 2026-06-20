"""Contract-only tests for Stage 825 controlled-live request validation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.demo.controlled_live_request_contract import (
    ALLOWED_KEYS,
    VALID_ANSWER_STATUSES,
    ControlledLiveRequestValidationResult,
    validate_controlled_live_request,
)


BASE_PAYLOAD = {
    "question": "민원서식 어디서 받아?",
    "site_id": "bukgu_gwangju",
    "fetch_provider": "requests",
    "llm_provider": "stub",
    "fetch_mode": "subprocess_process_group",
    "expected_result_envelope": {
        "answer_status": "fallback_no_match",
    },
    "operator_acknowledgement": "I_ACKNOWLEDGE_CONTROLLED_LIVE",
    "rollback_procedure": "abort and cleanup with no-persist",
}


def _run(payload: dict) -> ControlledLiveRequestValidationResult:
    return validate_controlled_live_request(payload)


def _assert_valid(result: ControlledLiveRequestValidationResult) -> None:
    assert result.valid is True
    assert result.errors == ()
    assert isinstance(result.sanitized_summary, dict)
    assert result.sanitized_summary["site_id"] == "bukgu_gwangju"
    assert result.sanitized_summary["fetch_provider"] == "requests"
    assert result.sanitized_summary["llm_provider"] == "stub"
    assert result.sanitized_summary["fetch_mode"] == "subprocess_process_group"
    assert result.sanitized_summary["question_length"] == len("민원서식 어디서 받아?")
    assert result.sanitized_summary["operator_acknowledgement_present"] is True
    assert result.sanitized_summary["expected_result_envelope"]["answer_status"] in VALID_ANSWER_STATUSES
    assert result.sanitized_summary["rollback_procedure_accepted"] is True


def test_valid_request_passes() -> None:
    _assert_valid(_run(dict(BASE_PAYLOAD)))


@pytest.mark.parametrize("key", sorted(BASE_PAYLOAD))
def test_missing_field_fails(key: str) -> None:
    payload = {k: v for k, v in BASE_PAYLOAD.items() if k != key}
    result = _run(payload)
    assert result.valid is False
    assert result.errors


def test_unknown_key_fails() -> None:
    payload = {**BASE_PAYLOAD, "leaked_token": "secret"}
    result = _run(payload)
    assert result.valid is False
    assert result.errors


@pytest.mark.parametrize(
    "key",
    ["question", "site_id", "fetch_provider", "llm_provider", "fetch_mode", "operator_acknowledgement"],
)
def test_blank_string_fields_fail(key: str) -> None:
    payload = {**BASE_PAYLOAD, key: ""}
    result = _run(payload)
    assert result.valid is False
    assert result.errors


@pytest.mark.parametrize(
    "key,value",
    [
        ("site_id", "gwangju_seo"),
        ("fetch_provider", "firecrawl"),
        ("llm_provider", "openai"),
        ("fetch_mode", "in_process"),
    ],
)
def test_disallowed_values_fail(key: str, value: str) -> None:
    payload = {**BASE_PAYLOAD, key: value}
    result = _run(payload)
    assert result.valid is False
    assert result.errors


def test_bad_acknowledgement_fails() -> None:
    payload = {**BASE_PAYLOAD, "operator_acknowledgement": "wrong"}
    result = _run(payload)
    assert result.valid is False
    assert result.errors


@pytest.mark.parametrize(
    "status",
    ["PASS", "answered", "no_results", "warn"],
)
def test_invalid_result_status_fails(status: str) -> None:
    payload = {**BASE_PAYLOAD, "expected_result_envelope": {"answer_status": status}}
    result = _run(payload)
    assert result.valid is False
    assert result.errors


def test_question_not_leaked_in_summary() -> None:
    payload = {**BASE_PAYLOAD, "question": "민원서식 비밀 질문 foo@bar"}
    result = _run(payload)
    assert result.valid is True
    raw_text = " ".join([str(result), repr(result), repr(result.sanitized_summary)])
    assert "foo@bar" not in raw_text


@pytest.mark.parametrize(
    "leak_key",
    ["headers", "body", "token", "api_key", "provider_payload", "exception_text", "authorization", "cookie", "bearer"],
)
def test_leak_keys_are_not_accepted(leak_key: str) -> None:
    payload = {**BASE_PAYLOAD, leak_key: "bad"}
    result = _run(payload)
    assert result.valid is False
    assert result.errors


def test_no_imports_or_side_effects() -> None:
    module_path = Path("src/demo/controlled_live_request_contract.py")
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                used.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            used.add(node.module)
    for forbidden in ["requests", "httpx", "urllib", "subprocess", "threading", "asyncio", "firecrawl", "browser", "crawl"]:
        assert forbidden not in used


def test_module_api_exports() -> None:
    import src.demo.controlled_live_request_contract as module

    assert hasattr(module, "validate_controlled_live_request")
    assert hasattr(module, "ControlledLiveRequestValidationResult")


def test_run_all_demos_does_not_link_to_controlled_live_path() -> None:
    """scripts/run_all_demos.py must not link the demo runner into any
    controlled-live execution path or provider module."""

    forbidden_substrings = (
        "controlled_live_request_contract",
        "validate_controlled_live_request",
        "controlled_live_ux_runner",
        "controlled_live_command_guard",
        "I_ACKNOWLEDGE_CONTROLLED_LIVE",
        "firecrawl",
        "openai",
        "anthropic",
        "subprocess.run",
    )

    script_path = Path("scripts/run_all_demos.py")
    content = script_path.read_text(encoding="utf-8")

    for needle in forbidden_substrings:
        assert needle not in content, (
            f"scripts/run_all_demos.py unexpectedly contains {needle!r}; "
            "the demo runner must not be wired into any controlled-live path."
        )
