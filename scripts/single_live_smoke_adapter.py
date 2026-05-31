"""Adapter selection skeleton for single-scenario live smoke payloads.

Stage 72 intentionally keeps the only selectable implementation on the
Stage 69 fake adapter. This module exists to define the seam for future
single-scenario adapters without enabling real provider, fetch, network,
Firecrawl, or app pipeline execution.
"""

from __future__ import annotations

from typing import Any, Callable

from scripts.single_live_smoke_fake_adapter import (
    FAKE_SINGLE_LIVE_ADAPTER_NAME,
    build_fake_single_live_result_payload,
)

SingleScenarioAdapter = Callable[[dict[str, Any]], dict[str, Any]]
SUPPORTED_SINGLE_SCENARIO_ADAPTER_NAMES = (FAKE_SINGLE_LIVE_ADAPTER_NAME,)
DEFAULT_SINGLE_SCENARIO_ADAPTER_NAME = FAKE_SINGLE_LIVE_ADAPTER_NAME


class SingleLiveSmokeAdapterError(ValueError):
    """Raised when an unsupported single-scenario adapter is requested."""


def get_single_scenario_adapter_name(adapter_name: str | None = None) -> str:
    """Return the selected adapter name; currently only the fake adapter exists."""
    if adapter_name is None:
        return DEFAULT_SINGLE_SCENARIO_ADAPTER_NAME
    if not isinstance(adapter_name, str):
        raise SingleLiveSmokeAdapterError(
            f"Adapter name must be a string or None: {type(adapter_name).__name__}"
        )
    normalized_name = adapter_name.strip()
    if normalized_name == "":
        return DEFAULT_SINGLE_SCENARIO_ADAPTER_NAME
    return normalized_name


def supported_single_scenario_adapter_names_message() -> str:
    """Return a deterministic display string for supported adapter names."""
    return ", ".join(SUPPORTED_SINGLE_SCENARIO_ADAPTER_NAMES)


def unsupported_single_scenario_adapter_error_message(selected_name: str) -> str:
    """Return the unsupported adapter error message with supported names."""
    return (
        "Unsupported single-scenario adapter: "
        f"{selected_name}. Supported adapters: "
        f"{supported_single_scenario_adapter_names_message()}"
    )


def get_single_scenario_adapter(adapter_name: str | None = None) -> SingleScenarioAdapter:
    """Return the selected single-scenario adapter implementation.

    Stage 72 deliberately supports only the deterministic fake adapter. A future
    real adapter must be added as an explicit opt-in path rather than silently
    changing this default.
    """
    selected_name = get_single_scenario_adapter_name(adapter_name)
    if selected_name not in SUPPORTED_SINGLE_SCENARIO_ADAPTER_NAMES:
        raise SingleLiveSmokeAdapterError(
            unsupported_single_scenario_adapter_error_message(selected_name)
        )
    if selected_name == FAKE_SINGLE_LIVE_ADAPTER_NAME:
        return build_fake_single_live_result_payload
    raise SingleLiveSmokeAdapterError(
        unsupported_single_scenario_adapter_error_message(selected_name)
    )


def build_single_live_adapter_payload(
    scenario: dict[str, Any],
    *,
    adapter_name: str | None = None,
) -> dict[str, Any]:
    """Build one Stage 62-compatible payload through the selected adapter."""
    adapter = get_single_scenario_adapter(adapter_name)
    return adapter(scenario)
