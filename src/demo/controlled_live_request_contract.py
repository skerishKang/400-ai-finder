"""Contract-only validator for a future controlled-live request payload.

This module contains no network, subprocess, thread, LLM, or I/O side effects.
It only validates a closed vocabulary of allowed request fields and returns
a sanitized summary without leaking request secrets or raw questions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ALLOWED_KEYS = frozenset(
    {
        "question",
        "site_id",
        "fetch_provider",
        "llm_provider",
        "fetch_mode",
        "expected_result_envelope",
        "operator_acknowledgement",
        "rollback_procedure",
    }
)

VALID_ANSWER_STATUSES = frozenset(
    {
        "answered_with_evidence",
        "fallback_no_match",
        "fallback_unavailable",
        "error",
    }
)


@dataclass(frozen=True)
class ControlledLiveRequestValidationResult:
    valid: bool
    errors: tuple[str, ...]
    sanitized_summary: dict[str, Any]


def _fail(error: str, sanitized_summary: dict[str, Any]) -> ControlledLiveRequestValidationResult:
    return ControlledLiveRequestValidationResult(
        valid=False,
        errors=(error,),
        sanitized_summary=sanitized_summary,
    )


class ControlledLiveRequestValidationError(Exception):
    def __init__(self, errors: tuple[str, ...]) -> None:
        self.errors = errors
        super().__init__(errors)


def validate_controlled_live_request(payload: object) -> ControlledLiveRequestValidationResult:
    summary: dict[str, Any] = {"received_type": type(payload).__name__}

    if not isinstance(payload, dict):
        return _fail("payload_type_invalid", summary.copy())

    unknown = sorted(set(payload) - ALLOWED_KEYS)
    if unknown:
        return _fail(f"unknown_keys:{','.join(unknown)}", {**summary, "unknown_keys": unknown})

    missing = [name for name in sorted(ALLOWED_KEYS) if name not in payload]
    if missing:
        return _fail(f"missing_keys:{','.join(missing)}", {**summary, "missing_keys": missing})

    question = payload.get("question")
    if not isinstance(question, str) or not question:
        return _fail("question_invalid", {**summary, "question_length": 0})
    if len(question) > 500:
        return _fail("question_too_long", {**summary, "question_length": len(question)})

    site_id = payload.get("site_id")
    if not isinstance(site_id, str) or not site_id:
        return _fail("site_id_invalid", summary.copy())
    if site_id != "bukgu_gwangju":
        return _fail("site_id_not_allowed", summary.copy())

    fetch_provider = payload.get("fetch_provider")
    if not isinstance(fetch_provider, str) or fetch_provider != "requests":
        return _fail("fetch_provider_not_allowed", summary.copy())

    llm_provider = payload.get("llm_provider")
    if not isinstance(llm_provider, str) or llm_provider != "stub":
        return _fail("llm_provider_not_allowed", summary.copy())

    fetch_mode = payload.get("fetch_mode")
    if not isinstance(fetch_mode, str) or fetch_mode != "subprocess_process_group":
        return _fail("fetch_mode_not_allowed", summary.copy())

    operator_acknowledgement = payload.get("operator_acknowledgement")
    if not isinstance(operator_acknowledgement, str) or operator_acknowledgement != "I_ACKNOWLEDGE_CONTROLLED_LIVE":
        return _fail("operator_acknowledgement_invalid", summary.copy())

    expected_result_envelope = payload.get("expected_result_envelope")
    if not isinstance(expected_result_envelope, dict):
        return _fail("expected_result_envelope_invalid", summary.copy())

    answer_status = expected_result_envelope.get("answer_status")
    if not isinstance(answer_status, str) or answer_status not in VALID_ANSWER_STATUSES:
        return _fail("answer_status_invalid", summary.copy())

    rollback_procedure = payload.get("rollback_procedure")
    if not isinstance(rollback_procedure, str) or "no-persist" not in rollback_procedure:
        return _fail("rollback_procedure_invalid", summary.copy())

    sanitized_summary: dict[str, Any] = {
        "question_length": len(question),
        "site_id": "bukgu_gwangju",
        "fetch_provider": "requests",
        "llm_provider": "stub",
        "fetch_mode": "subprocess_process_group",
        "operator_acknowledgement_present": True,
        "expected_result_envelope": {"answer_status": answer_status},
        "rollback_procedure_accepted": True,
    }
    return ControlledLiveRequestValidationResult(
        valid=True,
        errors=(),
        sanitized_summary=sanitized_summary,
    )
