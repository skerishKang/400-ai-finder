"""Contract-only tests for Stage #826 review-packet builder."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.demo.controlled_live_review_packet import (
    EXECUTION_STATE_REVIEW_ONLY,
    ControlledLiveReviewPacket,
    build_controlled_live_review_packet,
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


SECRET_LIKE = (
    "Bearer secret-token",
    "Authorization: Bearer XXXXX",
    "https://user:pass@example.test/path",
    "header-like: x-api-key=abc123",
    "body-like secret=abc123",
)


def _build(payload: dict) -> ControlledLiveReviewPacket:
    return build_controlled_live_review_packet(payload)


def _packet_fields(packet: ControlledLiveReviewPacket) -> dict[str, object]:
    return {
        "request_valid": packet.request_valid,
        "validation_errors": packet.validation_errors,
        "question_length": packet.question_length,
        "site_id": packet.site_id,
        "fetch_provider": packet.fetch_provider,
        "llm_provider": packet.llm_provider,
        "fetch_mode": packet.fetch_mode,
        "expected_answer_status": packet.expected_answer_status,
        "acknowledgement_present": packet.acknowledgement_present,
        "rollback_no_persist_accepted": packet.rollback_no_persist_accepted,
        "execution_state": packet.execution_state,
        "execution_allowed": packet.execution_allowed,
        "human_review_required": packet.human_review_required,
    }


def _assert_review_only_envelope(packet: ControlledLiveReviewPacket) -> None:
    assert packet.execution_state == EXECUTION_STATE_REVIEW_ONLY
    assert packet.execution_allowed is False
    assert packet.human_review_required is True


def test_valid_request_produces_review_only_packet() -> None:
    packet = _build(dict(BASE_PAYLOAD))
    _assert_review_only_envelope(packet)
    assert packet.request_valid is True
    assert packet.validation_errors == ()
    assert packet.question_length == len("민원서식 어디서 받아?")
    assert packet.site_id == "bukgu_gwangju"
    assert packet.fetch_provider == "requests"
    assert packet.llm_provider == "stub"
    assert packet.fetch_mode == "subprocess_process_group"
    assert packet.expected_answer_status == "fallback_no_match"
    assert packet.acknowledgement_present is True
    assert packet.rollback_no_persist_accepted is True


@pytest.mark.parametrize(
    "status",
    ["answered_with_evidence", "fallback_no_match", "fallback_unavailable", "error"],
)
def test_each_stage806_status_is_preserved_in_packet(status: str) -> None:
    payload = {**BASE_PAYLOAD, "expected_result_envelope": {"answer_status": status}}
    packet = _build(payload)
    _assert_review_only_envelope(packet)
    assert packet.request_valid is True
    assert packet.expected_answer_status == status


@pytest.mark.parametrize("missing_key", sorted(BASE_PAYLOAD))
def test_missing_field_yields_safe_non_executable_packet(missing_key: str) -> None:
    payload = {k: v for k, v in BASE_PAYLOAD.items() if k != missing_key}
    packet = _build(payload)
    _assert_review_only_envelope(packet)
    assert packet.request_valid is False
    assert packet.validation_errors
    assert packet.question_length is None
    assert packet.site_id is None
    assert packet.fetch_provider is None
    assert packet.llm_provider is None
    assert packet.fetch_mode is None
    assert packet.expected_answer_status is None
    assert packet.acknowledgement_present is False
    assert packet.rollback_no_persist_accepted is False


def test_unknown_key_yields_safe_packet() -> None:
    payload = {**BASE_PAYLOAD, "secret_token": "leak"}
    packet = _build(payload)
    _assert_review_only_envelope(packet)
    assert packet.request_valid is False
    assert packet.validation_errors


def test_leak_field_yields_safe_packet() -> None:
    for key in ("headers", "body", "token", "api_key", "provider_payload", "exception_text", "authorization", "cookie", "bearer"):
        packet = _build({**BASE_PAYLOAD, key: "leak"})
        _assert_review_only_envelope(packet)
        assert packet.request_valid is False
        assert packet.validation_errors


def test_invalid_payload_type_yields_safe_packet() -> None:
    packet = _build("not a dict")
    _assert_review_only_envelope(packet)
    assert packet.request_valid is False
    assert packet.validation_errors


def test_raw_question_is_not_in_packet_or_repr() -> None:
    secret = "민원서식 비밀질문 x@y.com"
    packet = _build({**BASE_PAYLOAD, "question": secret})
    fields = _packet_fields(packet)
    rendered = " ".join(
        [
            str(packet),
            repr(packet),
            str(packet.validation_errors),
            repr(packet.validation_errors),
            str(fields),
            repr(fields),
        ]
    )
    assert secret not in rendered
    assert "x@y.com" not in rendered


@pytest.mark.parametrize("canary", SECRET_LIKE)
def test_secret_canaries_do_not_leak_in_packet(canary: str) -> None:
    packet = _build({**BASE_PAYLOAD, "question": canary})
    fields = _packet_fields(packet)
    rendered = " ".join([str(packet), repr(packet), str(fields), repr(fields)])
    assert canary not in rendered


def test_packet_shape_is_deterministic_for_invalid_payloads() -> None:
    packet_a = _build({})
    packet_b = _build("not a dict")
    packet_c = _build({**BASE_PAYLOAD, "leak": "x"})
    for packet in (packet_a, packet_b, packet_c):
        assert set(_packet_fields(packet)) == {
            "request_valid",
            "validation_errors",
            "question_length",
            "site_id",
            "fetch_provider",
            "llm_provider",
            "fetch_mode",
            "expected_answer_status",
            "acknowledgement_present",
            "rollback_no_persist_accepted",
            "execution_state",
            "execution_allowed",
            "human_review_required",
        }


def test_no_forbidden_imports() -> None:
    module_path = Path("src/demo/controlled_live_review_packet.py")
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                used.add(alias.name)
                used.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            used.add(node.module)
            used.add(node.module.split(".", 1)[0])
    forbidden = {
        "requests",
        "httpx",
        "urllib",
        "subprocess",
        "threading",
        "asyncio",
        "concurrent",
        "concurrent.futures",
        "firecrawl",
        "playwright",
        "crawl4ai",
        "scrapy",
    }
    assert used.isdisjoint(forbidden)


def test_run_all_demos_does_not_link_to_controlled_live_path() -> None:
    forbidden_substrings = (
        "controlled_live_review_packet",
        "build_controlled_live_review_packet",
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
            f"scripts/run_all_demos.py unexpectedly contains {needle!r}"
        )


@pytest.mark.parametrize(
    "canary_key",
    [
        "Bearer secret-token",
        "https://user:pass@example.test/path",
    ],
)
def test_user_supplied_canary_key_name_does_not_leak_in_packet(canary_key: str) -> None:
    payload = {**BASE_PAYLOAD, canary_key: "x"}
    packet = _build(payload)
    fields = _packet_fields(packet)
    rendered = " ".join(
        [
            str(packet),
            repr(packet),
            str(packet.validation_errors),
            repr(packet.validation_errors),
            str(fields),
            repr(fields),
        ]
    )
    assert canary_key not in rendered
    if "secret-token" in canary_key:
        assert "secret-token" not in rendered
    if "user:pass" in canary_key:
        assert "user:pass" not in rendered


_ALLOWED_ERROR_VOCAB: frozenset[str] = frozenset(
    {
        "unknown_keys",
        "missing_keys",
        "request_invalid",
    }
)


def test_validation_errors_are_closed_vocabulary_only() -> None:
    packet_missing = _build({})
    packet_unknown = _build({**BASE_PAYLOAD, "Bearer secret-token": "x"})
    packet_url = _build({**BASE_PAYLOAD, "https://user:pass@example.test/path": "x"})
    packet_non_dict = _build("not a dict")
    packet_leak = _build({**BASE_PAYLOAD, "headers": "leak"})

    for packet in (packet_missing, packet_unknown, packet_url, packet_non_dict, packet_leak):
        assert packet.validation_errors, "expected at least one sanitized error code"
        for code in packet.validation_errors:
            assert code in _ALLOWED_ERROR_VOCAB, (
                f"validation_errors must use closed vocabulary only, got {code!r}"
            )


def test_missing_field_error_normalizes_to_missing_keys_only() -> None:
    packet = _build({k: v for k, v in BASE_PAYLOAD.items() if k != "site_id"})
    assert packet.request_valid is False
    assert "missing_keys" in packet.validation_errors
    for code in packet.validation_errors:
        assert ":" not in code
        assert code in _ALLOWED_ERROR_VOCAB
