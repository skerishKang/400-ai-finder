"""Sanitized one-time review packet builder for a future controlled-live run.

This module produces a non-executable review-only packet from a request
payload. It reuses the Stage #825 contract validator and intentionally
contains no fetch, network, provider, LLM, runner, subprocess, thread,
or I/O side effects. The packet is safe to surface in logs, dashboards,
or pull-request reviews without leaking raw questions, tokens, headers,
or provider payloads.

Validation errors from Stage #825 are normalized to a closed vocabulary
so that user-supplied key names, error payload fragments, or any
unrecognized error code never propagate into the review packet or its
representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from src.demo.controlled_live_request_contract import (
    validate_controlled_live_request,
)

EXECUTION_STATE_REVIEW_ONLY: str = "review_only"

_ALLOWED_ERROR_CODES: frozenset[str] = frozenset(
    {
        "unknown_keys",
        "missing_keys",
        "request_invalid",
    }
)

_PREFIX_UNKNOWN_KEYS: str = "unknown_keys:"
_PREFIX_MISSING_KEYS: str = "missing_keys:"


@dataclass(frozen=True)
class ControlledLiveReviewPacket:
    request_valid: bool
    validation_errors: tuple[str, ...]
    question_length: Optional[int]
    site_id: Optional[str]
    fetch_provider: Optional[str]
    llm_provider: Optional[str]
    fetch_mode: Optional[str]
    expected_answer_status: Optional[str]
    acknowledgement_present: bool
    rollback_no_persist_accepted: bool
    execution_state: str
    execution_allowed: bool
    human_review_required: bool


def _sanitize_validation_errors(errors: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize Stage #825 validation errors to a closed vocabulary.

    The contract validator returns codes such as
    ``unknown_keys:Bearer-secret`` or ``missing_keys:site_id``. Those
    detail suffixes can echo user-supplied key names or future error
    payload fragments. This sanitizer collapses them to a fixed
    vocabulary so the review packet never leaks the raw detail.
    """
    sanitized: list[str] = []
    for code in errors:
        if not isinstance(code, str):
            sanitized.append("request_invalid")
            continue
        if code.startswith(_PREFIX_UNKNOWN_KEYS):
            sanitized.append("unknown_keys")
            continue
        if code.startswith(_PREFIX_MISSING_KEYS):
            sanitized.append("missing_keys")
            continue
        if code in _ALLOWED_ERROR_CODES:
            sanitized.append(code)
            continue
        sanitized.append("request_invalid")
    return tuple(sanitized)


def _safe_packet(
    *,
    request_valid: bool,
    validation_errors: tuple[str, ...],
    question_length: Optional[int],
    site_id: Optional[str],
    fetch_provider: Optional[str],
    llm_provider: Optional[str],
    fetch_mode: Optional[str],
    expected_answer_status: Optional[str],
    acknowledgement_present: bool,
    rollback_no_persist_accepted: bool,
) -> ControlledLiveReviewPacket:
    return ControlledLiveReviewPacket(
        request_valid=request_valid,
        validation_errors=_sanitize_validation_errors(validation_errors),
        question_length=question_length,
        site_id=site_id,
        fetch_provider=fetch_provider,
        llm_provider=llm_provider,
        fetch_mode=fetch_mode,
        expected_answer_status=expected_answer_status,
        acknowledgement_present=acknowledgement_present,
        rollback_no_persist_accepted=rollback_no_persist_accepted,
        execution_state=EXECUTION_STATE_REVIEW_ONLY,
        execution_allowed=False,
        human_review_required=True,
    )


def build_controlled_live_review_packet(payload: object) -> ControlledLiveReviewPacket:
    result = validate_controlled_live_request(payload)

    if not result.valid:
        return _safe_packet(
            request_valid=False,
            validation_errors=result.errors,
            question_length=None,
            site_id=None,
            fetch_provider=None,
            llm_provider=None,
            fetch_mode=None,
            expected_answer_status=None,
            acknowledgement_present=False,
            rollback_no_persist_accepted=False,
        )

    summary: dict[str, Any] = result.sanitized_summary
    expected_envelope = summary.get("expected_result_envelope")
    expected_answer_status: Optional[str] = None
    if isinstance(expected_envelope, dict):
        status = expected_envelope.get("answer_status")
        if isinstance(status, str):
            expected_answer_status = status

    return _safe_packet(
        request_valid=True,
        validation_errors=result.errors,
        question_length=summary.get("question_length") if isinstance(summary.get("question_length"), int) else None,
        site_id=summary.get("site_id") if isinstance(summary.get("site_id"), str) else None,
        fetch_provider=summary.get("fetch_provider") if isinstance(summary.get("fetch_provider"), str) else None,
        llm_provider=summary.get("llm_provider") if isinstance(summary.get("llm_provider"), str) else None,
        fetch_mode=summary.get("fetch_mode") if isinstance(summary.get("fetch_mode"), str) else None,
        expected_answer_status=expected_answer_status,
        acknowledgement_present=bool(summary.get("operator_acknowledgement_present")),
        rollback_no_persist_accepted=bool(summary.get("rollback_procedure_accepted")),
    )
