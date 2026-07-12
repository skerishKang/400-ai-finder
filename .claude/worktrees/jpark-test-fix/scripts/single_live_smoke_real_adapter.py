"""Non-executing placeholder for a future single-scenario real adapter.

Stage 74 intentionally does not implement real execution. The placeholder is
importable for interface tests, but calling it raises immediately so the current
successful path remains the deterministic fake adapter.
"""

from __future__ import annotations

from typing import Any

REAL_SINGLE_LIVE_ADAPTER_NAME = "real-single-scenario-live-adapter"


class SingleLiveSmokeRealAdapterNotImplementedError(NotImplementedError):
    """Raised when the future real adapter placeholder is called."""


def build_real_single_live_result_payload(_: dict[str, Any]) -> dict[str, Any]:
    """Reject real adapter execution until an explicit future stage implements it."""
    raise SingleLiveSmokeRealAdapterNotImplementedError(
        "Real single-scenario adapter is not implemented. Use the fake adapter path."
    )
