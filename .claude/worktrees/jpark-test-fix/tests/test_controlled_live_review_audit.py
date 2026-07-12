"""Contract-only tests for the Stage #831 controlled-live review audit snapshot."""

from __future__ import annotations

import ast
import dataclasses
from dataclasses import replace
from pathlib import Path

import pytest

from src.demo.controlled_live_review_audit import (
    NEXT_ACTION_CORRECT_CONTRACT,
    NEXT_ACTION_MANUAL_REVIEW,
    REASON_EXECUTION_PROHIBITED,
    REASON_HUMAN_REVIEW_REQUIRED,
    REASON_INVALID_PACKET,
    REASON_REQUEST_CONTRACT_VALID,
    REASON_REQUEST_INVALID,
    REVIEW_STATE_BLOCKED,
    REVIEW_STATE_HUMAN_REVIEW_REQUIRED,
    SCHEMA_VERSION,
    ControlledLiveReviewAuditSnapshot,
    build_controlled_live_review_audit_snapshot,
)
from src.demo.controlled_live_review_decision import (
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


EXPECTED_FIELD_ORDER = (
    "schema_version",
    "request_valid",
    "review_state",
    "reason_codes",
    "next_action",
    "question_length",
    "site_id",
    "fetch_provider",
    "llm_provider",
    "fetch_mode",
    "expected_answer_status",
    "acknowledgement_present",
    "rollback_no_persist_accepted",
    "execution_allowed",
    "human_review_required",
)


def _valid_packet() -> ControlledLiveReviewPacket:
    return build_controlled_live_review_packet(dict(BASE_PAYLOAD))


def _assert_envelope(snapshot: ControlledLiveReviewAuditSnapshot) -> None:
    assert snapshot.schema_version == SCHEMA_VERSION
    assert snapshot.execution_allowed is False
    assert snapshot.human_review_required is True
    assert snapshot.review_state in {
        REVIEW_STATE_BLOCKED,
        REVIEW_STATE_HUMAN_REVIEW_REQUIRED,
    }
    assert snapshot.next_action in {
        NEXT_ACTION_CORRECT_CONTRACT,
        NEXT_ACTION_MANUAL_REVIEW,
    }
    for code in snapshot.reason_codes:
        assert code in {
            REASON_REQUEST_CONTRACT_VALID,
            REASON_REQUEST_INVALID,
            "unknown_keys",
            "missing_keys",
            REASON_INVALID_PACKET,
            REASON_HUMAN_REVIEW_REQUIRED,
            REASON_EXECUTION_PROHIBITED,
        }


def _rendered(snapshot: ControlledLiveReviewAuditSnapshot) -> str:
    return " ".join(
        [
            str(snapshot),
            repr(snapshot),
            str(snapshot.reason_codes),
            repr(snapshot.reason_codes),
            str(snapshot.review_state),
            str(snapshot.next_action),
        ]
    )


def test_snapshot_dataclass_field_order_matches_spec() -> None:
    fields = tuple(field.name for field in dataclasses.fields(ControlledLiveReviewAuditSnapshot))
    assert fields == EXPECTED_FIELD_ORDER


def test_snapshot_dataclass_is_frozen() -> None:
    snapshot = build_controlled_live_review_audit_snapshot(_valid_packet())
    with pytest.raises((AttributeError, Exception)):
        snapshot.execution_allowed = True  # type: ignore[misc]


def test_valid_packet_yields_normal_snapshot_with_copied_metadata() -> None:
    packet = _valid_packet()
    snapshot = build_controlled_live_review_audit_snapshot(packet)
    _assert_envelope(snapshot)
    assert snapshot.request_valid is True
    assert snapshot.review_state == REVIEW_STATE_HUMAN_REVIEW_REQUIRED
    assert snapshot.next_action == NEXT_ACTION_MANUAL_REVIEW
    assert snapshot.question_length == packet.question_length
    assert snapshot.site_id == packet.site_id
    assert snapshot.fetch_provider == packet.fetch_provider
    assert snapshot.llm_provider == packet.llm_provider
    assert snapshot.fetch_mode == packet.fetch_mode
    assert snapshot.expected_answer_status == packet.expected_answer_status
    assert snapshot.acknowledgement_present is packet.acknowledgement_present
    assert snapshot.rollback_no_persist_accepted is packet.rollback_no_persist_accepted


def test_normal_snapshot_reason_codes_match_decision_and_closed_vocab() -> None:
    packet = _valid_packet()
    decision = summarize_controlled_live_review_packet(packet)
    snapshot = build_controlled_live_review_audit_snapshot(packet)
    assert snapshot.reason_codes == decision.reason_codes
    assert REASON_REQUEST_CONTRACT_VALID in snapshot.reason_codes
    assert REASON_HUMAN_REVIEW_REQUIRED in snapshot.reason_codes
    assert REASON_EXECUTION_PROHIBITED in snapshot.reason_codes
    assert len(snapshot.reason_codes) == len(set(snapshot.reason_codes))


def test_normal_snapshot_never_authorizes_execution() -> None:
    snapshot = build_controlled_live_review_audit_snapshot(_valid_packet())
    assert snapshot.execution_allowed is False
    assert snapshot.human_review_required is True
    assert snapshot.schema_version == "controlled_live_review_audit_v1"


def test_invalid_request_packet_yields_blocked_snapshot_with_cleared_metadata() -> None:
    packet = build_controlled_live_review_packet({})
    snapshot = build_controlled_live_review_audit_snapshot(packet)
    _assert_envelope(snapshot)
    assert snapshot.request_valid is False
    assert snapshot.review_state == REVIEW_STATE_BLOCKED
    assert snapshot.next_action == NEXT_ACTION_CORRECT_CONTRACT
    assert snapshot.question_length is None
    assert snapshot.site_id is None
    assert snapshot.fetch_provider is None
    assert snapshot.llm_provider is None
    assert snapshot.fetch_mode is None
    assert snapshot.expected_answer_status is None
    assert snapshot.acknowledgement_present is False
    assert snapshot.rollback_no_persist_accepted is False
    assert REASON_REQUEST_INVALID in snapshot.reason_codes
    assert REASON_HUMAN_REVIEW_REQUIRED in snapshot.reason_codes
    assert REASON_EXECUTION_PROHIBITED in snapshot.reason_codes


@pytest.mark.parametrize(
    "bad_input",
    [None, "string", 123, 4.5, [], {"fake": "dict"}, object()],
)
def test_non_packet_input_yields_blocked_snapshot(bad_input: object) -> None:
    snapshot = build_controlled_live_review_audit_snapshot(bad_input)
    _assert_envelope(snapshot)
    assert snapshot.request_valid is False
    assert snapshot.review_state == REVIEW_STATE_BLOCKED
    assert snapshot.next_action == NEXT_ACTION_CORRECT_CONTRACT
    assert REASON_INVALID_PACKET in snapshot.reason_codes
    assert snapshot.question_length is None
    assert snapshot.site_id is None


def test_raw_payload_dict_is_not_accepted_as_packet() -> None:
    snapshot = build_controlled_live_review_audit_snapshot(dict(BASE_PAYLOAD))
    _assert_envelope(snapshot)
    assert snapshot.request_valid is False
    assert snapshot.review_state == REVIEW_STATE_BLOCKED
    assert REASON_INVALID_PACKET in snapshot.reason_codes


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
def test_forged_invariants_yield_blocked_without_leak(override: dict) -> None:
    valid = _valid_packet()
    forged = replace(valid, **override)
    snapshot = build_controlled_live_review_audit_snapshot(forged)
    _assert_envelope(snapshot)
    assert snapshot.request_valid is False
    assert snapshot.review_state == REVIEW_STATE_BLOCKED
    assert snapshot.next_action == NEXT_ACTION_CORRECT_CONTRACT
    assert REASON_INVALID_PACKET in snapshot.reason_codes
    rendered = _rendered(snapshot)
    for forbidden_word in ("approved", "execution_ready", "ready"):
        if forbidden_word in str(override.get("execution_state", "")):
            assert forbidden_word not in rendered


@pytest.mark.parametrize(
    "override, expected_reason",
    [
        ({"site_id": "evil_site"}, REASON_INVALID_PACKET),
        ({"site_id": "Bearer secret-token"}, REASON_INVALID_PACKET),
        ({"fetch_provider": "urllib"}, REASON_INVALID_PACKET),
        ({"fetch_provider": "firecrawl"}, REASON_INVALID_PACKET),
        ({"llm_provider": "openai"}, REASON_INVALID_PACKET),
        ({"fetch_mode": "direct_subprocess"}, REASON_INVALID_PACKET),
        ({"expected_answer_status": "answered_with_proof"}, REASON_INVALID_PACKET),
        ({"expected_answer_status": "leaked-status"}, REASON_INVALID_PACKET),
    ],
)
def test_allowlist_departure_yields_blocked_without_leak(
    override: dict, expected_reason: str
) -> None:
    valid = _valid_packet()
    forged = replace(valid, **override)
    snapshot = build_controlled_live_review_audit_snapshot(forged)
    _assert_envelope(snapshot)
    assert snapshot.request_valid is False
    assert snapshot.review_state == REVIEW_STATE_BLOCKED
    assert expected_reason in snapshot.reason_codes
    assert snapshot.site_id in (None, "bukgu_gwangju")
    assert snapshot.fetch_provider in (None, "requests")
    assert snapshot.llm_provider in (None, "stub")
    assert snapshot.fetch_mode in (None, "subprocess_process_group")
    rendered = _rendered(snapshot)
    for forbidden in (
        "evil_site",
        "Bearer",
        "secret-token",
        "urllib",
        "firecrawl",
        "openai",
        "direct_subprocess",
        "answered_with_proof",
        "leaked-status",
    ):
        if forbidden in str(override.values()):
            assert forbidden not in rendered, (
                f"value {forbidden!r} leaked into snapshot: {rendered!r}"
            )


@pytest.mark.parametrize(
    "override",
    [
        {"request_valid": "yes"},
        {"request_valid": 1},
        {"request_valid": 0},
        {"request_valid": None},
    ],
)
def test_type_coerced_request_valid_yields_blocked_without_leak(override: dict) -> None:
    valid = _valid_packet()
    forged = replace(valid, **override)
    snapshot = build_controlled_live_review_audit_snapshot(forged)
    _assert_envelope(snapshot)
    assert snapshot.request_valid is False
    assert snapshot.review_state == REVIEW_STATE_BLOCKED
    assert snapshot.next_action == NEXT_ACTION_CORRECT_CONTRACT
    assert REASON_INVALID_PACKET in snapshot.reason_codes
    rendered = _rendered(snapshot)
    for forbidden in ("yes",):
        if forbidden in str(override.values()):
            assert forbidden not in rendered


def test_request_valid_false_yields_blocked_with_request_invalid_reason() -> None:
    valid = _valid_packet()
    forged = replace(valid, request_valid=False)
    snapshot = build_controlled_live_review_audit_snapshot(forged)
    _assert_envelope(snapshot)
    assert snapshot.request_valid is False
    assert snapshot.review_state == REVIEW_STATE_BLOCKED
    assert REASON_REQUEST_INVALID in snapshot.reason_codes


def test_non_empty_validation_errors_block_even_when_request_valid_true() -> None:
    valid = _valid_packet()
    forged = replace(valid, validation_errors=("missing_keys",))
    snapshot = build_controlled_live_review_audit_snapshot(forged)
    _assert_envelope(snapshot)
    assert snapshot.request_valid is False
    assert snapshot.review_state == REVIEW_STATE_BLOCKED
    assert REASON_REQUEST_INVALID in snapshot.reason_codes


def test_validation_errors_list_type_is_blocked() -> None:
    valid = _valid_packet()
    forged = replace(valid, validation_errors=[])
    snapshot = build_controlled_live_review_audit_snapshot(forged)
    _assert_envelope(snapshot)
    assert snapshot.request_valid is False
    assert snapshot.review_state == REVIEW_STATE_BLOCKED
    assert REASON_INVALID_PACKET in snapshot.reason_codes


@pytest.mark.parametrize(
    "override",
    [
        {"question_length": "5"},
        {"question_length": -1},
        {"question_length": None},
        {"acknowledgement_present": "yes"},
        {"acknowledgement_present": 1},
        {"rollback_no_persist_accepted": "no"},
        {"rollback_no_persist_accepted": 0},
    ],
)
def test_metadata_type_tampering_yields_blocked(override: dict) -> None:
    valid = _valid_packet()
    forged = replace(valid, **override)
    snapshot = build_controlled_live_review_audit_snapshot(forged)
    _assert_envelope(snapshot)
    assert snapshot.request_valid is False
    assert snapshot.review_state == REVIEW_STATE_BLOCKED
    assert REASON_INVALID_PACKET in snapshot.reason_codes
    assert snapshot.question_length is None or isinstance(snapshot.question_length, int)


@pytest.mark.parametrize("canary", SECRET_LIKE)
def test_secret_canaries_in_metadata_do_not_leak(canary: str) -> None:
    valid = _valid_packet()
    forged = replace(
        valid,
        site_id=canary,
        fetch_provider=canary,
        llm_provider=canary,
        fetch_mode=canary,
        expected_answer_status=canary,
    )
    snapshot = build_controlled_live_review_audit_snapshot(forged)
    _assert_envelope(snapshot)
    assert snapshot.request_valid is False
    assert snapshot.review_state == REVIEW_STATE_BLOCKED
    rendered = _rendered(snapshot)
    assert canary not in rendered
    assert "secret-token" not in rendered
    assert "user:pass" not in rendered
    assert snapshot.site_id is None
    assert snapshot.fetch_provider is None


@pytest.mark.parametrize("canary", SECRET_LIKE)
def test_secret_canaries_in_validation_errors_do_not_leak(canary: str) -> None:
    valid = _valid_packet()
    forged = replace(
        valid,
        request_valid=False,
        validation_errors=(canary,),
    )
    snapshot = build_controlled_live_review_audit_snapshot(forged)
    _assert_envelope(snapshot)
    assert snapshot.request_valid is False
    assert snapshot.review_state == REVIEW_STATE_BLOCKED
    rendered = _rendered(snapshot)
    assert canary not in rendered
    assert "secret-token" not in rendered
    assert "user:pass" not in rendered


def test_raw_question_text_does_not_leak_into_snapshot() -> None:
    secret = "비밀질문 secret@x.com"
    packet = build_controlled_live_review_packet(
        {**BASE_PAYLOAD, "question": secret}
    )
    snapshot = build_controlled_live_review_audit_snapshot(packet)
    _assert_envelope(snapshot)
    assert snapshot.question_length == len(secret)
    rendered = _rendered(snapshot)
    assert "비밀질문" not in rendered
    assert "secret@x.com" not in rendered
    assert snapshot.question_length is not None


def test_reason_codes_are_deterministic_for_same_input() -> None:
    valid = _valid_packet()
    forged = replace(valid, request_valid=False, validation_errors=("missing_keys",))
    snapshot_a = build_controlled_live_review_audit_snapshot(forged)
    snapshot_b = build_controlled_live_review_audit_snapshot(forged)
    assert snapshot_a.reason_codes == snapshot_b.reason_codes
    assert snapshot_a.reason_codes == tuple(
        sorted(
            snapshot_a.reason_codes,
            key=lambda c: [
                REASON_REQUEST_CONTRACT_VALID,
                REASON_REQUEST_INVALID,
                "unknown_keys",
                "missing_keys",
                REASON_INVALID_PACKET,
                REASON_HUMAN_REVIEW_REQUIRED,
                REASON_EXECUTION_PROHIBITED,
            ].index(c),
        )
    )


def test_blocked_snapshot_always_includes_human_review_and_execution_prohibited() -> None:
    for bad_input in (None, {}, _valid_packet().__class__):
        snapshot = build_controlled_live_review_audit_snapshot(bad_input)
        assert REASON_HUMAN_REVIEW_REQUIRED in snapshot.reason_codes
        assert REASON_EXECUTION_PROHIBITED in snapshot.reason_codes
        assert snapshot.execution_allowed is False
        assert snapshot.human_review_required is True


@pytest.mark.parametrize(
    "forbidden_word",
    ["approved", "ready", "execution_ready", "allowed", "execute", "schedule"],
)
def test_no_execution_authorization_word_in_snapshot_strings(
    forbidden_word: str,
) -> None:
    snapshot = build_controlled_live_review_audit_snapshot(_valid_packet())
    rendered = " ".join(
        [snapshot.review_state, snapshot.next_action] + list(snapshot.reason_codes)
    )
    assert forbidden_word not in rendered


def test_no_forbidden_imports() -> None:
    module_path = Path("src/demo/controlled_live_review_audit.py")
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


def test_run_all_demos_does_not_link_to_audit_path() -> None:
    forbidden_substrings = (
        "controlled_live_review_audit",
        "build_controlled_live_review_audit_snapshot",
        "ControlledLiveReviewAuditSnapshot",
    )
    content = Path("scripts/run_all_demos.py").read_text(encoding="utf-8")
    for needle in forbidden_substrings:
        assert needle not in content, (
            f"scripts/run_all_demos.py unexpectedly contains {needle!r}"
        )
