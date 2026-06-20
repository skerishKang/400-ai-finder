"""Locked UX runner MVP — Stage #811.

Scope of THIS stage (deliberately small):

* Accept a real user question (str, nonblank, ≤ ``MAX_QUESTION_LEN``).
* Build the approved Stage #807 envelope (``bukgu_gwangju + requests +
  stub``) and return the sanitized plan.
* Return the Stage #806 ``fallback_no_match`` dry-run envelope.
* Mark ``execution_allowed = False`` and ``mode = "dry_run"`` — live
  execution is unconditionally "locked" in this stage.

Deliberately deferred to the next issues (NOT implemented here):

* The double opt-in gate (``allow_controlled_live`` + the exact
  ``I_ACKNOWLEDGE_CONTROLLED_LIVE`` acknowledgement). The Request
  dataclass carries the fields for forward compatibility, but the MVP
  runner does not enforce them.
* The injected ``execution_boundary`` test seam.
* Boundary-result state correction (timeout / error / evidence).

This module is intentionally free of real fetch, live LLM, subprocess,
threading, asyncio, browser, and crawler SDK imports. The raw user
question is never echoed into the plan, the result, any exception, or
any repr.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from src.demo.controlled_live_smoke_contract import (
    APPROVED_EXECUTION_MODE,
    APPROVED_FETCH_PROVIDER,
    APPROVED_LLM_PROVIDER,
    APPROVED_SITE_ID,
    ControlledLiveSmokePlan,
    ControlledLiveSmokeRequest,
    validate_controlled_live_smoke_request,
)


# --- Closed-vocabulary constants ----------------------------------------

REQUIRED_ACKNOWLEDGEMENT: Final[str] = "I_ACKNOWLEDGE_CONTROLLED_LIVE"
DRY_RUN_MODE: Final[str] = "dry_run"

MAX_QUESTION_LEN: Final[int] = 500
QUESTION_INVALID_CODE: Final[str] = "question_invalid"
INVALID_REQUEST_CODE: Final[str] = "invalid_request"

_ANSWER_STATUS_FALLBACK: Final[str] = "fallback_no_match"


# --- Error ---------------------------------------------------------------

class LockedControlledLiveUxError(ValueError):
    """Closed-vocabulary validation error for the locked UX runner."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


# --- Dataclasses ---------------------------------------------------------

@dataclass(frozen=True)
class LockedControlledLiveUxRequest:
    """User-facing request envelope.

    ``allow_controlled_live`` and ``acknowledgement`` are accepted for
    forward compatibility but are NOT enforced in this MVP. The opt-in
    gate is deferred to the next issue.
    """

    question: str
    allow_controlled_live: bool = False
    acknowledgement: str | None = None


@dataclass(frozen=True)
class LockedControlledLiveUxResponse:
    """Locked UX runner MVP response.

    ``plan`` is the approved Stage #807 envelope; ``result`` is the
    sanitized Stage #806 ``fallback_no_match`` dry-run envelope.
    """

    mode: str
    execution_allowed: bool
    plan: ControlledLiveSmokePlan
    result: dict


# --- Helpers -------------------------------------------------------------

def _build_approved_envelope() -> ControlledLiveSmokeRequest:
    """Return the only envelope this runner is allowed to feed forward."""
    return ControlledLiveSmokeRequest(
        site_id=APPROVED_SITE_ID,
        fetch_provider=APPROVED_FETCH_PROVIDER,
        llm_provider=APPROVED_LLM_PROVIDER,
        max_pages=1,
        max_depth=0,
        max_sitemaps=0,
        max_enrich_pages=0,
        retry_count=0,
        request_timeout_s=5.0,
        total_budget_s=10.0,
        persist_scenarios=False,
        persist_snapshots=False,
        persist_cache=False,
        persist_config=False,
        persist_source_grounding=False,
        temp_only_output=True,
        deterministic_cleanup=True,
        audit_path=None,
        retain_artifacts=False,
        execution_mode=APPROVED_EXECUTION_MODE,
        isolated_process_group=True,
        kill_process_group_on_timeout=True,
        explicit_user_post_count=1,
        separate_fetch_attempts_observable=True,
    )


def _validate_question(question: Any) -> str:
    """Validate the question and fail with a fixed safe code on any
    type/blank/length violation. The raw value is never echoed.
    """
    if isinstance(question, bool) or not isinstance(question, str):
        raise LockedControlledLiveUxError(QUESTION_INVALID_CODE)
    if not question.strip():
        raise LockedControlledLiveUxError(QUESTION_INVALID_CODE)
    if len(question) > MAX_QUESTION_LEN:
        raise LockedControlledLiveUxError(QUESTION_INVALID_CODE)
    return question


def _dry_run_envelope() -> dict:
    return {
        "ok": True,
        "answer_ok": False,
        "answer_status": _ANSWER_STATUS_FALLBACK,
        "source_weak": True,
        "sources": [],
        "fetch_diagnostic": None,
    }


# --- Public API ----------------------------------------------------------

def run_locked_controlled_live_ux(
    request: LockedControlledLiveUxRequest,
) -> LockedControlledLiveUxResponse:
    """MVP dry-run: validate the question, build the approved plan,
    and return the dry-run envelope.

    Live execution is unconditionally "locked" in this stage. The
    double opt-in gate and the injected execution boundary are
    deferred to the next issue.
    """
    if not isinstance(request, LockedControlledLiveUxRequest):
        raise LockedControlledLiveUxError(INVALID_REQUEST_CODE)

    _validate_question(request.question)

    envelope = _build_approved_envelope()
    plan = validate_controlled_live_smoke_request(envelope)

    return LockedControlledLiveUxResponse(
        mode=DRY_RUN_MODE,
        execution_allowed=False,
        plan=plan,
        result=_dry_run_envelope(),
    )


__all__ = [
    "REQUIRED_ACKNOWLEDGEMENT",
    "DRY_RUN_MODE",
    "MAX_QUESTION_LEN",
    "QUESTION_INVALID_CODE",
    "INVALID_REQUEST_CODE",
    "LockedControlledLiveUxError",
    "LockedControlledLiveUxRequest",
    "LockedControlledLiveUxResponse",
    "run_locked_controlled_live_ux",
]