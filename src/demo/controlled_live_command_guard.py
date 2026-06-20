"""No-live command/approval guard for the locked controlled-live runner.

This module is the LAST gate before any real controlled-live execution
is permitted. It is locked to be no-live: it only inspects the
request envelope and returns a closed-vocabulary decision. No real
fetch, no live LLM, no subprocess, no browser/crawler, no logging,
no persistence.

The guard is intentionally separate from the runner itself so that:

* the approval contract can be audited, tested, and reviewed in
  isolation;
* upstream command surfaces (CLI, scheduled jobs, internal admin
  tools) can be wired to this guard without dragging the runner's
  normalization / seam logic along with them;
* future stages can extend the decision (e.g. add audit trail,
  approval tokens, replay protection) without rewriting the runner.

The decision contract is intentionally tiny:

* ``CommandDecision.allowed`` is the single boolean the caller needs
  to gate execution.
* ``CommandDecision.reason`` is a closed-vocabulary string drawn from
  a small allowlist so the caller can route / log / display it
  without ever touching the raw question.

The raw user question is never inspected, logged, or echoed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from src.demo.controlled_live_ux_runner import LockedControlledLiveUxRequest


# --- Closed-vocabulary decision reasons ---------------------------------

DECISION_APPROVED: Final[str] = "approved"
DECISION_DENIED_NO_FLAG: Final[str] = "denied_no_flag"
DECISION_DENIED_ACK_MISSING: Final[str] = "denied_ack_missing"
DECISION_DENIED_WRONG_ACK: Final[str] = "denied_wrong_ack"

ALL_DECISION_REASONS: Final[tuple[str, ...]] = (
    DECISION_APPROVED,
    DECISION_DENIED_NO_FLAG,
    DECISION_DENIED_ACK_MISSING,
    DECISION_DENIED_WRONG_ACK,
)


@dataclass(frozen=True)
class CommandDecision:
    """Closed-vocabulary decision returned by the guard.

    ``allowed`` is True iff the request is fully approved. The
    ``reason`` is a closed-vocabulary code suitable for routing,
    logging, or audit. The raw question is never stored on the
    decision and is never inspected by the guard itself.
    """

    allowed: bool
    reason: str


def _deny(reason: str) -> CommandDecision:
    return CommandDecision(allowed=False, reason=reason)


def _approve() -> CommandDecision:
    return CommandDecision(allowed=True, reason=DECISION_APPROVED)


def evaluate_command(request: "LockedControlledLiveUxRequest") -> CommandDecision:
    """Evaluate whether a controlled-live command is fully approved.

    Both opt-in conditions must hold simultaneously:

    * ``request.allow_controlled_live is True`` (strict identity,
      not just truthy).
    * ``request.acknowledgement == REQUIRED_ACKNOWLEDGEMENT`` (exact
      string match, case-sensitive, whitespace-sensitive).

    Any deviation -- missing flag, missing acknowledgement, wrong
    acknowledgement, wrong type -- is a partial / missing approval
    and is denied. The raw ``question`` is never inspected or
    echoed; only the two opt-in fields are read.

    The import of the runner types is deferred to call time so the
    guard module does not form a circular import with the runner.
    """
    # Lazy import: breaks the runner <-> guard circular import. By
    # the time this function is called, the runner module is fully
    # loaded in sys.modules.
    from src.demo.controlled_live_ux_runner import (
        REQUIRED_ACKNOWLEDGEMENT,
        LockedControlledLiveUxRequest,
    )

    if not isinstance(request, LockedControlledLiveUxRequest):
        return _deny(DECISION_DENIED_NO_FLAG)

    if request.allow_controlled_live is not True:
        return _deny(DECISION_DENIED_NO_FLAG)

    if not isinstance(request.acknowledgement, str):
        return _deny(DECISION_DENIED_ACK_MISSING)

    if request.acknowledgement != REQUIRED_ACKNOWLEDGEMENT:
        return _deny(DECISION_DENIED_WRONG_ACK)

    return _approve()


__all__ = [
    "DECISION_APPROVED",
    "DECISION_DENIED_NO_FLAG",
    "DECISION_DENIED_ACK_MISSING",
    "DECISION_DENIED_WRONG_ACK",
    "ALL_DECISION_REASONS",
    "CommandDecision",
    "evaluate_command",
]
