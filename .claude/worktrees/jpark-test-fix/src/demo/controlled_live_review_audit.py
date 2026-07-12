"""Audit snapshot for a Stage #831 controlled-live review packet.

This module produces a non-executable, closed-vocabulary audit snapshot from
a single ``ControlledLiveReviewPacket`` object. It never accepts a raw request
payload, never re-validates the raw request, never reaches a runner, network,
provider, LLM, or I/O subsystem, and never grants execution authority.

The snapshot:

* copies sanitized packet metadata only when every normal-snapshot condition
  (packet identity, invariants, strict request validity, closed-vocabulary
  allowlists, and the Stage #829 decision contract) is satisfied;
* otherwise returns a blocked snapshot whose metadata fields are cleared and
  whose reason codes stay within a closed vocabulary;
* never echoes raw repr, key names, tokens, headers, bodies, URL userinfo, or
  exception text. Unknown values and types collapse to the
  ``request_invalid`` / ``invalid_packet`` family.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.demo.controlled_live_review_decision import (
    ControlledLiveReviewDecision,
    summarize_controlled_live_review_packet,
)
from src.demo.controlled_live_review_packet import ControlledLiveReviewPacket


SCHEMA_VERSION: str = "controlled_live_review_audit_v1"
EXECUTION_STATE_REVIEW_ONLY: str = "review_only"

REVIEW_STATE_BLOCKED: str = "blocked"
REVIEW_STATE_HUMAN_REVIEW_REQUIRED: str = "human_review_required"

NEXT_ACTION_CORRECT_CONTRACT: str = "correct_contract"
NEXT_ACTION_MANUAL_REVIEW: str = "manual_review"

REASON_REQUEST_CONTRACT_VALID: str = "request_contract_valid"
REASON_REQUEST_INVALID: str = "request_invalid"
REASON_UNKNOWN_KEYS: str = "unknown_keys"
REASON_MISSING_KEYS: str = "missing_keys"
REASON_INVALID_PACKET: str = "invalid_packet"
REASON_HUMAN_REVIEW_REQUIRED: str = "human_review_required"
REASON_EXECUTION_PROHIBITED: str = "execution_prohibited"

_REASON_ORDER: tuple[str, ...] = (
    REASON_REQUEST_CONTRACT_VALID,
    REASON_REQUEST_INVALID,
    REASON_UNKNOWN_KEYS,
    REASON_MISSING_KEYS,
    REASON_INVALID_PACKET,
    REASON_HUMAN_REVIEW_REQUIRED,
    REASON_EXECUTION_PROHIBITED,
)

_ALLOWED_REASON_CODES: frozenset[str] = frozenset(_REASON_ORDER)

_ALLOWED_SITE_IDS: frozenset[str] = frozenset({"bukgu_gwangju"})
_ALLOWED_FETCH_PROVIDERS: frozenset[str] = frozenset({"requests"})
_ALLOWED_LLM_PROVIDERS: frozenset[str] = frozenset({"stub"})
_ALLOWED_FETCH_MODES: frozenset[str] = frozenset({"subprocess_process_group"})
_ALLOWED_ANSWER_STATUSES: frozenset[str] = frozenset(
    {
        "answered_with_evidence",
        "fallback_no_match",
        "fallback_unavailable",
        "error",
    }
)


@dataclass(frozen=True)
class ControlledLiveReviewAuditSnapshot:
    schema_version: str
    request_valid: bool
    review_state: str
    reason_codes: tuple[str, ...]
    next_action: str
    question_length: Optional[int]
    site_id: Optional[str]
    fetch_provider: Optional[str]
    llm_provider: Optional[str]
    fetch_mode: Optional[str]
    expected_answer_status: Optional[str]
    acknowledgement_present: bool
    rollback_no_persist_accepted: bool
    execution_allowed: bool
    human_review_required: bool


def _sanitize_reason_codes(codes: object) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    if isinstance(codes, (tuple, list)):
        for code in codes:
            if isinstance(code, str) and code in _ALLOWED_REASON_CODES:
                normalized = code
            else:
                normalized = REASON_REQUEST_INVALID
            if normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
    ordered.sort(key=lambda value: _REASON_ORDER.index(value))
    return tuple(ordered)


def _is_strict_bool_true(value: object) -> bool:
    return type(value) is bool and value is True


def _packet_invariants_hold(packet: ControlledLiveReviewPacket) -> bool:
    if packet.execution_state != EXECUTION_STATE_REVIEW_ONLY:
        return False
    if packet.execution_allowed is not False:
        return False
    if packet.human_review_required is not True:
        return False
    return True


def _request_validity_holds(packet: ControlledLiveReviewPacket) -> bool:
    if not _is_strict_bool_true(packet.request_valid):
        return False
    if not isinstance(packet.validation_errors, tuple):
        return False
    if packet.validation_errors != ():
        return False
    return True


def _metadata_allowlists_hold(packet: ControlledLiveReviewPacket) -> bool:
    if type(packet.question_length) is not int or packet.question_length < 0:
        return False
    if packet.site_id not in _ALLOWED_SITE_IDS:
        return False
    if packet.fetch_provider not in _ALLOWED_FETCH_PROVIDERS:
        return False
    if packet.llm_provider not in _ALLOWED_LLM_PROVIDERS:
        return False
    if packet.fetch_mode not in _ALLOWED_FETCH_MODES:
        return False
    if packet.expected_answer_status not in _ALLOWED_ANSWER_STATUSES:
        return False
    if type(packet.acknowledgement_present) is not bool:
        return False
    if type(packet.rollback_no_persist_accepted) is not bool:
        return False
    return True


def _decision_contract_holds(decision: ControlledLiveReviewDecision) -> bool:
    if not _is_strict_bool_true(decision.request_valid):
        return False
    if decision.review_state != REVIEW_STATE_HUMAN_REVIEW_REQUIRED:
        return False
    if decision.next_action != NEXT_ACTION_MANUAL_REVIEW:
        return False
    if decision.execution_allowed is not False:
        return False
    if decision.human_review_required is not True:
        return False
    if not isinstance(decision.reason_codes, tuple):
        return False
    for code in decision.reason_codes:
        if not (isinstance(code, str) and code in _ALLOWED_REASON_CODES):
            return False
    return True


def _normal_snapshot_allowed(
    packet: object, decision: ControlledLiveReviewDecision
) -> bool:
    if not isinstance(packet, ControlledLiveReviewPacket):
        return False
    if not _packet_invariants_hold(packet):
        return False
    if not _request_validity_holds(packet):
        return False
    if not _metadata_allowlists_hold(packet):
        return False
    if not _decision_contract_holds(decision):
        return False
    return True


def _build_normal_snapshot(
    packet: ControlledLiveReviewPacket, decision: ControlledLiveReviewDecision
) -> ControlledLiveReviewAuditSnapshot:
    return ControlledLiveReviewAuditSnapshot(
        schema_version=SCHEMA_VERSION,
        request_valid=True,
        review_state=REVIEW_STATE_HUMAN_REVIEW_REQUIRED,
        reason_codes=_sanitize_reason_codes(decision.reason_codes),
        next_action=NEXT_ACTION_MANUAL_REVIEW,
        question_length=packet.question_length,
        site_id=packet.site_id,
        fetch_provider=packet.fetch_provider,
        llm_provider=packet.llm_provider,
        fetch_mode=packet.fetch_mode,
        expected_answer_status=packet.expected_answer_status,
        acknowledgement_present=packet.acknowledgement_present,
        rollback_no_persist_accepted=packet.rollback_no_persist_accepted,
        execution_allowed=False,
        human_review_required=True,
    )


def _collect_block_reasons(
    packet: object, decision: ControlledLiveReviewDecision
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(packet, ControlledLiveReviewPacket):
        reasons.append(REASON_INVALID_PACKET)
    else:
        if not _packet_invariants_hold(packet):
            reasons.append(REASON_INVALID_PACKET)
        if not _is_strict_bool_true(packet.request_valid):
            if type(packet.request_valid) is not bool:
                reasons.append(REASON_INVALID_PACKET)
            else:
                reasons.append(REASON_REQUEST_INVALID)
        if not isinstance(packet.validation_errors, tuple) or (
            packet.validation_errors != ()
        ):
            reasons.append(REASON_REQUEST_INVALID)
        if (
            type(packet.question_length) is not int
            or packet.question_length < 0
        ):
            reasons.append(REASON_INVALID_PACKET)
        if packet.site_id not in _ALLOWED_SITE_IDS:
            reasons.append(REASON_INVALID_PACKET)
        if packet.fetch_provider not in _ALLOWED_FETCH_PROVIDERS:
            reasons.append(REASON_INVALID_PACKET)
        if packet.llm_provider not in _ALLOWED_LLM_PROVIDERS:
            reasons.append(REASON_INVALID_PACKET)
        if packet.fetch_mode not in _ALLOWED_FETCH_MODES:
            reasons.append(REASON_INVALID_PACKET)
        if packet.expected_answer_status not in _ALLOWED_ANSWER_STATUSES:
            reasons.append(REASON_INVALID_PACKET)
        if type(packet.acknowledgement_present) is not bool:
            reasons.append(REASON_INVALID_PACKET)
        if type(packet.rollback_no_persist_accepted) is not bool:
            reasons.append(REASON_INVALID_PACKET)
        if not _decision_contract_holds(decision):
            reasons.append(REASON_INVALID_PACKET)
    reasons.append(REASON_HUMAN_REVIEW_REQUIRED)
    reasons.append(REASON_EXECUTION_PROHIBITED)
    return _sanitize_reason_codes(reasons)


def _build_blocked_snapshot(
    packet: object, decision: ControlledLiveReviewDecision
) -> ControlledLiveReviewAuditSnapshot:
    return ControlledLiveReviewAuditSnapshot(
        schema_version=SCHEMA_VERSION,
        request_valid=False,
        review_state=REVIEW_STATE_BLOCKED,
        reason_codes=_collect_block_reasons(packet, decision),
        next_action=NEXT_ACTION_CORRECT_CONTRACT,
        question_length=None,
        site_id=None,
        fetch_provider=None,
        llm_provider=None,
        fetch_mode=None,
        expected_answer_status=None,
        acknowledgement_present=False,
        rollback_no_persist_accepted=False,
        execution_allowed=False,
        human_review_required=True,
    )


def build_controlled_live_review_audit_snapshot(
    packet: object,
) -> ControlledLiveReviewAuditSnapshot:
    """Build a closed-vocabulary audit snapshot from a review packet.

    The function never grants execution authority: every returned snapshot has
    ``execution_allowed = False`` and ``human_review_required = True``. It only
    accepts a ``ControlledLiveReviewPacket`` object (never a raw payload) and
    derives its decision internally from
    ``summarize_controlled_live_review_packet``.
    """

    decision = summarize_controlled_live_review_packet(packet)
    if _normal_snapshot_allowed(packet, decision):
        return _build_normal_snapshot(packet, decision)
    return _build_blocked_snapshot(packet, decision)
