"""Locked UX runner — Stage #813.

Extends the Stage #811 MVP with:

* Double opt-in gate (``allow_controlled_live is True`` AND exact
  ``acknowledgement == REQUIRED_ACKNOWLEDGEMENT``).
* Test-only ``execution_boundary`` keyword-only seam: invoked *exactly
  once* and *only* when both opt-in conditions are satisfied AND a
  boundary callable is supplied. The default behavior with no boundary
  returns a safe "execution not enabled" envelope.
* Boundary-result state correction (Stage #806 contract):
  - ``ok and answer_ok and nonblank answer_markdown and non-empty sources``
    -> ``answered_with_evidence``
  - everything else under ``ok=True`` -> ``fallback_no_match``
  - ``TimeoutError`` -> ``fallback_unavailable``
  - other ``Exception`` -> ``error``
* Canary-safe source / fetch_diagnostic filtering: only ``id`` and
  ``url`` survive in sources (with URL userinfo stripped); only
  ``category`` survives in fetch_diagnostic. Arbitrary fields that
  could carry tokens, headers, bodies, or raw question text are
  dropped before the envelope is built.

The raw user question is never echoed into the plan, the result, any
exception, or any repr. No real fetch, no live LLM, no subprocess,
no threading, no asyncio, no browser/crawler SDK is imported.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Final

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
CONTROLLED_LIVE_REQUESTED_MODE: Final[str] = "controlled_live_requested"

MAX_QUESTION_LEN: Final[int] = 500
QUESTION_INVALID_CODE: Final[str] = "question_invalid"
INVALID_REQUEST_CODE: Final[str] = "invalid_request"

_ANSWER_STATUS_TIMEOUT: Final[str] = "fallback_unavailable"
_ANSWER_STATUS_ERROR: Final[str] = "error"
_ANSWER_STATUS_FALLBACK: Final[str] = "fallback_no_match"
_ANSWER_STATUS_EVIDENCE: Final[str] = "answered_with_evidence"

_FETCH_CATEGORY_TIMEOUT: Final[str] = "timeout"

_SAFE_SOURCE_FIELDS: Final[tuple[str, ...]] = ("id", "url")
_SAFE_DIAGNOSTIC_FIELDS: Final[tuple[str, ...]] = ("category",)


# --- Error ---------------------------------------------------------------

class LockedControlledLiveUxError(ValueError):
    """Closed-vocabulary validation error for the locked UX runner."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


# --- Dataclasses ---------------------------------------------------------

@dataclass(frozen=True)
class LockedControlledLiveUxRequest:
    """User-facing request envelope."""

    question: str
    allow_controlled_live: bool = False
    acknowledgement: str | None = None


@dataclass(frozen=True)
class LockedControlledLiveUxResponse:
    """Locked UX runner response.

    ``plan`` is the approved Stage #807 envelope; ``result`` is the
    sanitized Stage #806 answer envelope.
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


def _opt_in_satisfied(request: LockedControlledLiveUxRequest) -> bool:
    """Return True iff both opt-in conditions are explicitly satisfied."""
    if request.allow_controlled_live is not True:
        return False
    if not isinstance(request.acknowledgement, str):
        return False
    if request.acknowledgement != REQUIRED_ACKNOWLEDGEMENT:
        return False
    return True


# --- Envelope factories --------------------------------------------------

def _dry_run_envelope() -> dict:
    return {
        "ok": True,
        "answer_ok": False,
        "answer_status": _ANSWER_STATUS_FALLBACK,
        "source_weak": True,
        "sources": [],
        "fetch_diagnostic": None,
    }


def _execution_not_enabled_envelope() -> dict:
    return {
        "ok": False,
        "answer_ok": False,
        "answer_status": _ANSWER_STATUS_ERROR,
        "source_weak": True,
        "sources": [],
        "fetch_diagnostic": None,
    }


def _timeout_envelope(fetch_diagnostic: Any) -> dict:
    diag: dict | None
    if isinstance(fetch_diagnostic, dict):
        diag = fetch_diagnostic
    else:
        diag = {"category": _FETCH_CATEGORY_TIMEOUT}
    return {
        "ok": False,
        "answer_ok": False,
        "answer_status": _ANSWER_STATUS_TIMEOUT,
        "source_weak": True,
        "sources": [],
        "fetch_diagnostic": diag,
    }


def _error_envelope(fetch_diagnostic: Any) -> dict:
    diag: dict | None
    if isinstance(fetch_diagnostic, dict):
        diag = fetch_diagnostic
    else:
        diag = None
    return {
        "ok": False,
        "answer_ok": False,
        "answer_status": _ANSWER_STATUS_ERROR,
        "source_weak": True,
        "sources": [],
        "fetch_diagnostic": diag,
    }


# --- Canary-safe normalization helpers -----------------------------------

def _strip_url_userinfo(url: Any) -> str:
    """Remove ``user:pass@`` from a URL string to prevent credential
    leakage. Non-string or no-userinfo URLs are returned unchanged
    (or empty string for non-strings).
    """
    if not isinstance(url, str):
        return ""
    if "://" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            _, after_at = rest.split("@", 1)
            return f"{scheme}://{after_at}"
    return url


def _is_valid_source_id(value: Any) -> bool:
    """A source id must be a non-empty string or a non-bool integer."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        return bool(value)
    return False


def _safe_source_item(item: Any) -> dict:
    """Filter a single source dict down to ``id`` and ``url`` only.

    A source is only kept if it carries a valid (non-empty) ``id``.
    URL is run through userinfo stripping. Any other field is dropped
    so that tokens, headers, bodies, or question text cannot leak.
    """
    if not isinstance(item, dict):
        return {}
    id_value = item.get("id")
    if not _is_valid_source_id(id_value):
        return {}
    safe: dict = {"id": id_value}
    url_value = item.get("url")
    if isinstance(url_value, str) and url_value:
        safe["url"] = _strip_url_userinfo(url_value)
    return safe


def _safe_sources(value: Any) -> list:
    """Filter the sources list to the safe structure defined above."""
    if not isinstance(value, list):
        return []
    return [s for s in (_safe_source_item(item) for item in value) if s]


def _safe_diagnostic(value: Any) -> dict | None:
    """Filter ``fetch_diagnostic`` to ``category`` only."""
    if not isinstance(value, dict):
        return None
    safe: dict = {}
    if "category" in value and isinstance(value["category"], str):
        safe["category"] = value["category"]
    return safe if safe else None


def _safe_answer(value: Any) -> str:
    """Coerce a boundary answer value to a (possibly empty) string."""
    if isinstance(value, str):
        return value
    return ""


# --- Boundary result normalization ---------------------------------------

def _normalize_boundary_result(boundary_result: Any) -> dict:
    """Normalize a test-boundary dict into the Stage #806 envelope.

    Evidence requires all four conditions; anything else under
    ``ok=True`` collapses to ``fallback_no_match``. ``ok=False`` or
    a non-dict boundary output maps to ``error``.
    """
    if not isinstance(boundary_result, dict):
        return _error_envelope(None)

    sources = _safe_sources(boundary_result.get("sources"))
    answer = _safe_answer(
        boundary_result.get("answer_markdown", boundary_result.get("answer"))
    )
    fetch_diagnostic = _safe_diagnostic(boundary_result.get("fetch_diagnostic"))

    raw_ok = boundary_result.get("ok")
    ok = raw_ok is True
    raw_answer_ok = boundary_result.get("answer_ok")
    answer_ok = raw_answer_ok is True

    # Evidence: all four Stage #806 conditions must hold strictly.
    if ok and answer_ok and bool(answer.strip()) and sources:
        return {
            "ok": True,
            "answer_ok": True,
            "answer_status": _ANSWER_STATUS_EVIDENCE,
            "source_weak": False,
            "sources": sources,
            "fetch_diagnostic": fetch_diagnostic,
        }

    # Fallback: ok=True but at least one of the four conditions is missing.
    return {
        "ok": True,
        "answer_ok": False,
        "answer_status": _ANSWER_STATUS_FALLBACK,
        "source_weak": True,
        "sources": sources,
        "fetch_diagnostic": fetch_diagnostic,
    }


# --- Public API ----------------------------------------------------------

def run_locked_controlled_live_ux(
    request: LockedControlledLiveUxRequest,
    *,
    execution_boundary: Callable[[ControlledLiveSmokePlan], Any] | None = None,
) -> LockedControlledLiveUxResponse:
    """Locked UX runner entry point.

    Three branches:

    1. **Dry-run** — opt-in conditions are not both satisfied. The
       boundary is never invoked, regardless of whether one is passed.
    2. **Execution not enabled** — opt-in conditions are met, but no
       ``execution_boundary`` was supplied. A safe error envelope is
       returned.
    3. **Boundary call** — opt-in met AND ``execution_boundary`` is
       supplied. The boundary is invoked *exactly once* and its return
       value (or raised exception) is normalized into the Stage #806
       answer envelope.
    """
    if not isinstance(request, LockedControlledLiveUxRequest):
        raise LockedControlledLiveUxError(INVALID_REQUEST_CODE)

    _validate_question(request.question)

    envelope = _build_approved_envelope()
    plan = validate_controlled_live_smoke_request(envelope)

    # 1. Opt-in gate.
    if not _opt_in_satisfied(request):
        return LockedControlledLiveUxResponse(
            mode=DRY_RUN_MODE,
            execution_allowed=False,
            plan=plan,
            result=_dry_run_envelope(),
        )

    # 2. Opt-in met, no boundary -> safe "execution not enabled" envelope.
    if execution_boundary is None:
        return LockedControlledLiveUxResponse(
            mode=CONTROLLED_LIVE_REQUESTED_MODE,
            execution_allowed=True,
            plan=plan,
            result=_execution_not_enabled_envelope(),
        )

    # 3. Opt-in met + boundary -> call exactly once and normalize.
    try:
        boundary_result = execution_boundary(plan)
    except TimeoutError:
        return LockedControlledLiveUxResponse(
            mode=CONTROLLED_LIVE_REQUESTED_MODE,
            execution_allowed=True,
            plan=plan,
            result=_timeout_envelope({"category": _FETCH_CATEGORY_TIMEOUT}),
        )
    except Exception:
        return LockedControlledLiveUxResponse(
            mode=CONTROLLED_LIVE_REQUESTED_MODE,
            execution_allowed=True,
            plan=plan,
            result=_error_envelope(None),
        )

    return LockedControlledLiveUxResponse(
        mode=CONTROLLED_LIVE_REQUESTED_MODE,
        execution_allowed=True,
        plan=plan,
        result=_normalize_boundary_result(boundary_result),
    )


__all__ = [
    "REQUIRED_ACKNOWLEDGEMENT",
    "DRY_RUN_MODE",
    "CONTROLLED_LIVE_REQUESTED_MODE",
    "MAX_QUESTION_LEN",
    "QUESTION_INVALID_CODE",
    "INVALID_REQUEST_CODE",
    "LockedControlledLiveUxError",
    "LockedControlledLiveUxRequest",
    "LockedControlledLiveUxResponse",
    "run_locked_controlled_live_ux",
]
