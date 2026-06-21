"""Deterministic human-review decision summary for a Stage #826 review packet.

This module accepts a single ``ControlledLiveReviewPacket`` object and returns
a non-executable, closed-vocabulary decision summary. It never re-validates
the raw request payload, never reaches a runner, network, provider, LLM, or
I/O subsystem, and never grants execution authority. The decision surfaces
``execution_allowed = False`` and ``human_review_required = True`` in every
case, regardless of input shape.

The summarizer:

* treats any non-``ControlledLiveReviewPacket`` input, any forged packet, and
  any packet that violates the Stage #826 invariants as ``blocked``.
* enforces strict identity checks on ``request_valid`` (``is True``) and
  ``validation_errors`` (must be a ``tuple`` and equal to ``()``) before
  allowing the human-review path; any forged type-coerced value blocks
  the packet.
* maps the packet's already-sanitized ``validation_errors`` back to a
  decision-level closed vocabulary, discarding unknown codes and never
  echoing user-supplied strings.
* deduplicates and orders ``reason_codes`` deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.demo.controlled_live_review_packet import ControlledLiveReviewPacket


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


_ALLOWED_REASON_CODES: frozenset[str] = frozenset(
    {
        REASON_REQUEST_CONTRACT_VALID,
        REASON_REQUEST_INVALID,
        REASON_UNKNOWN_KEYS,
        REASON_MISSING_KEYS,
        REASON_INVALID_PACKET,
        REASON_HUMAN_REVIEW_REQUIRED,
        REASON_EXECUTION_PROHIBITED,
    }
)

_REASON_ORDER: tuple[str, ...] = (
    REASON_REQUEST_CONTRACT_VALID,
    REASON_REQUEST_INVALID,
    REASON_UNKNOWN_KEYS,
    REASON_MISSING_KEYS,
    REASON_INVALID_PACKET,
    REASON_HUMAN_REVIEW_REQUIRED,
    REASON_EXECUTION_PROHIBITED,
)

_VALIDATION_ERROR_TO_REASON: dict[str, str] = {
    REASON_UNKNOWN_KEYS: REASON_UNKNOWN_KEYS,
    REASON_MISSING_KEYS: REASON_MISSING_KEYS,
    REASON_REQUEST_INVALID: REASON_REQUEST_INVALID,
}


@dataclass(frozen=True)
class ControlledLiveReviewDecision:
    request_valid: bool
    review_state: str
    reason_codes: tuple[str, ...]
    next_action: str
    execution_allowed: bool
    human_review_required: bool


def _is_well_formed_packet(packet: object) -> bool:
    if not isinstance(packet, ControlledLiveReviewPacket):
        return False
    if packet.execution_state != "review_only":
        return False
    if packet.execution_allowed is not False:
        return False
    if packet.human_review_required is not True:
        return False
    return True


def _is_strict_request_valid_packet(packet: ControlledLiveReviewPacket) -> bool:
    if type(packet.request_valid) is not bool:
        return False
    if packet.request_valid is not True:
        return False
    if not isinstance(packet.validation_errors, tuple):
        return False
    if packet.validation_errors != ():
        return False
    return True


def _sanitize_reason_codes(codes: Iterable[object]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
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


def _map_validation_errors(errors: tuple[object, ...]) -> tuple[str, ...]:
    mapped: list[str] = []
    for code in errors:
        if isinstance(code, str) and code in _VALIDATION_ERROR_TO_REASON:
            mapped.append(_VALIDATION_ERROR_TO_REASON[code])
        else:
            mapped.append(REASON_REQUEST_INVALID)
    return tuple(mapped)


def _build_human_review_decision() -> ControlledLiveReviewDecision:
    return ControlledLiveReviewDecision(
        request_valid=True,
        review_state=REVIEW_STATE_HUMAN_REVIEW_REQUIRED,
        reason_codes=_sanitize_reason_codes(
            [
                REASON_REQUEST_CONTRACT_VALID,
                REASON_HUMAN_REVIEW_REQUIRED,
                REASON_EXECUTION_PROHIBITED,
            ]
        ),
        next_action=NEXT_ACTION_MANUAL_REVIEW,
        execution_allowed=False,
        human_review_required=True,
    )


def _build_blocked_decision(
    *, reason_codes: Iterable[object]
) -> ControlledLiveReviewDecision:
    combined: list[object] = list(reason_codes)
    combined.append(REASON_HUMAN_REVIEW_REQUIRED)
    combined.append(REASON_EXECUTION_PROHIBITED)
    return ControlledLiveReviewDecision(
        request_valid=False,
        review_state=REVIEW_STATE_BLOCKED,
        reason_codes=_sanitize_reason_codes(combined),
        next_action=NEXT_ACTION_CORRECT_CONTRACT,
        execution_allowed=False,
        human_review_required=True,
    )


def summarize_controlled_live_review_packet(
    packet: object,
) -> ControlledLiveReviewDecision:
    """Summarize a Stage #826 review packet into a closed-vocabulary decision.

    The function never grants execution authority: every returned decision
    has ``execution_allowed = False`` and ``human_review_required = True``.
    """

    if not _is_well_formed_packet(packet):
        return _build_blocked_decision(reason_codes=[REASON_INVALID_PACKET])

    assert isinstance(packet, ControlledLiveReviewPacket)

    if _is_strict_request_valid_packet(packet):
        return _build_human_review_decision()

    if (
        type(packet.request_valid) is not bool
        or not isinstance(packet.validation_errors, tuple)
    ):
        return _build_blocked_decision(
            reason_codes=[REASON_INVALID_PACKET, REASON_REQUEST_INVALID]
        )

    mapped = _map_validation_errors(tuple(packet.validation_errors))
    return _build_blocked_decision(reason_codes=mapped)
