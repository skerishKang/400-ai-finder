"""Contract-only tests for Stage #829 review-decision summarizer."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from src.demo.controlled_live_review_decision import (
    NEXT_ACTION_CORRECT_CONTRACT,
    NEXT_ACTION_MANUAL_REVIEW,
    REASON_EXECUTION_PROHIBITED,
    REASON_HUMAN_REVIEW_REQUIRED,
    REASON_INVALID_PACKET,
    REASON_MISSING_KEYS,
    REASON_REQUEST_CONTRACT_VALID,
    REASON_REQUEST_INVALID,
    REASON_UNKNOWN_KEYS,
    REVIEW_STATE_BLOCKED,
    REVIEW_STATE_HUMAN_REVIEW_REQUIRED,
    ControlledLiveReviewDecision,
    summarize_controlled_live_review_packet,
)
from src.demo.controlled_live_review_packet import (
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
    "Authorization: Bearer my-secret",
    "https://user:pass@example.test/path",
    "header-like: x-api-key=abc123",
    "body-like secret=abc123",
    "raw payload=abc123",
)


def _valid_packet() -> ControlledLiveReviewPacket:
    return build_controlled_live_review_packet(dict(BASE_PAYLOAD))


def _assert_envelope(decision: ControlledLiveReviewDecision) -> None:
    assert decision.execution_allowed is False
    assert decision.human_review_required is True
    assert decision.review_state in {
        REVIEW_STATE_BLOCKED,
        REVIEW_STATE_HUMAN_REVIEW_REQUIRED,
    }
    assert decision.next_action in {
        NEXT_ACTION_CORRECT_CONTRACT,
        NEXT_ACTION_MANUAL_REVIEW,
    }
    for code in decision.reason_codes:
        assert code in {
            REASON_REQUEST_CONTRACT_VALID,
            REASON_REQUEST_INVALID,
            REASON_UNKNOWN_KEYS,
            REASON_MISSING_KEYS,
            REASON_INVALID_PACKET,
            REASON_HUMAN_REVIEW_REQUIRED,
            REASON_EXECUTION_PROHIBITED,
        }


def _rendered(decision: ControlledLiveReviewDecision) -> str:
    return " ".join(
        [
            str(decision),
            repr(decision),
            str(decision.reason_codes),
            repr(decision.reason_codes),
        ]
    )


def test_valid_packet_yields_human_review_required_decision() -> None:
    decision = summarize_controlled_live_review_packet(_valid_packet())
    _assert_envelope(decision)
    assert decision.request_valid is True
    assert decision.review_state == REVIEW_STATE_HUMAN_REVIEW_REQUIRED
    assert decision.next_action == NEXT_ACTION_MANUAL_REVIEW
    assert REASON_REQUEST_CONTRACT_VALID in decision.reason_codes
    assert REASON_HUMAN_REVIEW_REQUIRED in decision.reason_codes
    assert REASON_EXECUTION_PROHIBITED in decision.reason_codes


def test_request_invalid_packet_yields_blocked_decision() -> None:
    packet = build_controlled_live_review_packet({})
    decision = summarize_controlled_live_review_packet(packet)
    _assert_envelope(decision)
    assert decision.request_valid is False
    assert decision.review_state == REVIEW_STATE_BLOCKED
    assert decision.next_action == NEXT_ACTION_CORRECT_CONTRACT
    assert REASON_MISSING_KEYS in decision.reason_codes
    assert REASON_EXECUTION_PROHIBITED in decision.reason_codes


def test_unknown_keys_packet_yields_blocked_with_unknown_keys_reason() -> None:
    packet = build_controlled_live_review_packet(
        {**BASE_PAYLOAD, "Bearer secret-token": "x"}
    )
    decision = summarize_controlled_live_review_packet(packet)
    _assert_envelope(decision)
    assert decision.request_valid is False
    assert decision.review_state == REVIEW_STATE_BLOCKED
    assert REASON_UNKNOWN_KEYS in decision.reason_codes


@pytest.mark.parametrize(
    "override",
    [
        {"execution_state": "approved"},
        {"execution_state": "ready"},
        {"execution_state": "execution_ready"},
        {"execution_allowed": True},
        {"human_review_required": False},
    ],
)
def test_forged_packet_yields_blocked_and_no_value_leak(override: dict) -> None:
    valid = _valid_packet()
    forged = replace(valid, **override)
    decision = summarize_controlled_live_review_packet(forged)
    _assert_envelope(decision)
    assert decision.request_valid is False
    assert decision.review_state == REVIEW_STATE_BLOCKED
    assert decision.next_action == NEXT_ACTION_CORRECT_CONTRACT
    assert REASON_INVALID_PACKET in decision.reason_codes
    rendered = _rendered(decision)
    for forbidden_word in ("approved", "execution_ready"):
        if forbidden_word in override.get("execution_state", ""):
            assert forbidden_word not in rendered


@pytest.mark.parametrize(
    "bad_input",
    [None, "string", 123, 4.5, [], {"fake": "dict"}, object()],
)
def test_non_packet_input_yields_blocked(bad_input: object) -> None:
    decision = summarize_controlled_live_review_packet(bad_input)
    _assert_envelope(decision)
    assert decision.request_valid is False
    assert decision.review_state == REVIEW_STATE_BLOCKED
    assert decision.next_action == NEXT_ACTION_CORRECT_CONTRACT
    assert REASON_INVALID_PACKET in decision.reason_codes


def test_unsafe_validation_errors_normalize_to_closed_vocabulary() -> None:
    valid = _valid_packet()
    forged = replace(
        valid,
        request_valid=False,
        validation_errors=(
            "Bearer secret-token",
            "https://user:pass@example.test/path",
            "raw payload=abc123",
            REASON_UNKNOWN_KEYS,
            REASON_MISSING_KEYS,
            REASON_REQUEST_INVALID,
            REASON_UNKNOWN_KEYS,
        ),
    )
    decision = summarize_controlled_live_review_packet(forged)
    _assert_envelope(decision)
    assert decision.request_valid is False
    assert decision.review_state == REVIEW_STATE_BLOCKED
    assert REASON_UNKNOWN_KEYS in decision.reason_codes
    assert REASON_MISSING_KEYS in decision.reason_codes
    assert REASON_REQUEST_INVALID in decision.reason_codes
    assert len(decision.reason_codes) == len(set(decision.reason_codes))


def test_reason_codes_are_deterministic_for_same_input() -> None:
    valid = _valid_packet()
    forged = replace(
        valid,
        request_valid=False,
        validation_errors=(
            REASON_MISSING_KEYS,
            REASON_UNKNOWN_KEYS,
            REASON_MISSING_KEYS,
            REASON_REQUEST_INVALID,
        ),
    )
    decision_a = summarize_controlled_live_review_packet(forged)
    decision_b = summarize_controlled_live_review_packet(forged)
    assert decision_a.reason_codes == decision_b.reason_codes
    assert decision_a.reason_codes == tuple(sorted(decision_a.reason_codes, key=lambda c: [
        REASON_REQUEST_CONTRACT_VALID,
        REASON_REQUEST_INVALID,
        REASON_UNKNOWN_KEYS,
        REASON_MISSING_KEYS,
        REASON_INVALID_PACKET,
        REASON_HUMAN_REVIEW_REQUIRED,
        REASON_EXECUTION_PROHIBITED,
    ].index(c)))


@pytest.mark.parametrize("canary", SECRET_LIKE)
def test_secret_canaries_do_not_leak_in_decision(canary: str) -> None:
    valid = _valid_packet()
    forged = replace(
        valid,
        request_valid=False,
        validation_errors=(canary,),
    )
    decision = summarize_controlled_live_review_packet(forged)
    rendered = _rendered(decision)
    assert canary not in rendered
    assert "secret-token" not in rendered
    assert "user:pass" not in rendered


def test_raw_question_length_does_not_leak_question_text() -> None:
    secret = "비밀질문 secret@x.com"
    packet = build_controlled_live_review_packet(
        {**BASE_PAYLOAD, "question": secret}
    )
    decision = summarize_controlled_live_review_packet(packet)
    rendered = _rendered(decision)
    assert "비밀질문" not in rendered
    assert "secret@x.com" not in rendered


@pytest.mark.parametrize(
    "forbidden_word",
    ["approved", "ready", "execution_ready", "allowed", "execute", "schedule"],
)
def test_no_execution_authorization_word_in_decision_strings(
    forbidden_word: str,
) -> None:
    decision = summarize_controlled_live_review_packet(_valid_packet())
    rendered = " ".join(
        [decision.review_state, decision.next_action] + list(decision.reason_codes)
    )
    assert forbidden_word not in rendered
    assert "run " + forbidden_word not in rendered


def test_decision_dataclass_is_frozen() -> None:
    decision = summarize_controlled_live_review_packet(_valid_packet())
    with pytest.raises((AttributeError, Exception)):
        decision.execution_allowed = True  # type: ignore[misc]


def test_no_forbidden_imports() -> None:
    module_path = Path("src/demo/controlled_live_review_decision.py")
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
        "controlled_live_review_decision",
        "summarize_controlled_live_review_packet",
        "controlled_live_review_packet",
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
    content = Path("scripts/run_all_demos.py").read_text(encoding="utf-8")
    for needle in forbidden_substrings:
        assert needle not in content, (
            f"scripts/run_all_demos.py unexpectedly contains {needle!r}"
        )


@pytest.mark.parametrize(
    "override, expected_reasons",
    [
        ({"request_valid": "yes"}, {REASON_INVALID_PACKET, REASON_REQUEST_INVALID}),
        ({"request_valid": 1}, {REASON_INVALID_PACKET, REASON_REQUEST_INVALID}),
        ({"request_valid": 0}, {REASON_INVALID_PACKET, REASON_REQUEST_INVALID}),
        ({"request_valid": None}, {REASON_INVALID_PACKET, REASON_REQUEST_INVALID}),
        ({"validation_errors": []}, {REASON_INVALID_PACKET, REASON_REQUEST_INVALID}),
        ({"validation_errors": ["unexpected"]}, {REASON_INVALID_PACKET, REASON_REQUEST_INVALID}),
        ({"validation_errors": ("unexpected",)}, {REASON_REQUEST_INVALID}),
        ({"validation_errors": ("Bearer secret-token",)}, {REASON_REQUEST_INVALID}),
    ],
)
def test_type_coerced_forgery_is_blocked_without_leak(
    override: dict, expected_reasons: set
) -> None:
    valid = _valid_packet()
    forged = replace(valid, **override)
    decision = summarize_controlled_live_review_packet(forged)
    _assert_envelope(decision)
    assert decision.request_valid is False
    assert decision.review_state == REVIEW_STATE_BLOCKED
    assert decision.next_action == NEXT_ACTION_CORRECT_CONTRACT
    assert expected_reasons.issubset(set(decision.reason_codes))
    rendered = _rendered(decision)
    for forbidden in (
        "yes",
        "Bearer secret-token",
        "secret-token",
        "unexpected",
    ):
        assert forbidden not in rendered, (
            f"forged value {forbidden!r} leaked into decision/repr: {rendered!r}"
        )


def test_request_valid_yes_does_not_satisfy_strict_is_true_check() -> None:
    valid = _valid_packet()
    forged = replace(valid, request_valid="yes")
    decision = summarize_controlled_live_review_packet(forged)
    _assert_envelope(decision)
    assert decision.request_valid is False
    assert decision.review_state == REVIEW_STATE_BLOCKED
    assert REASON_INVALID_PACKET in decision.reason_codes
    rendered = _rendered(decision)
    assert "yes" not in rendered


def test_request_valid_one_does_not_satisfy_strict_is_true_check() -> None:
    valid = _valid_packet()
    forged = replace(valid, request_valid=1)
    decision = summarize_controlled_live_review_packet(forged)
    _assert_envelope(decision)
    assert decision.request_valid is False
    assert decision.review_state == REVIEW_STATE_BLOCKED
    assert REASON_INVALID_PACKET in decision.reason_codes


def test_empty_list_validation_errors_is_blocked_not_human_review() -> None:
    valid = _valid_packet()
    forged = replace(valid, validation_errors=[])
    decision = summarize_controlled_live_review_packet(forged)
    _assert_envelope(decision)
    assert decision.request_valid is False
    assert decision.review_state == REVIEW_STATE_BLOCKED
    assert decision.next_action == NEXT_ACTION_CORRECT_CONTRACT
    assert REASON_INVALID_PACKET in decision.reason_codes


def test_unexpected_string_validation_error_is_normalized_to_request_invalid() -> None:
    valid = _valid_packet()
    forged = replace(valid, validation_errors=("unexpected",))
    decision = summarize_controlled_live_review_packet(forged)
    _assert_envelope(decision)
    assert decision.request_valid is False
    assert decision.review_state == REVIEW_STATE_BLOCKED
    assert REASON_REQUEST_INVALID in decision.reason_codes
    assert "unexpected" not in _rendered(decision)
