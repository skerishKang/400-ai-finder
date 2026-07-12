"""Helper functions for resolving presets and building metadata for demo results."""

from __future__ import annotations
from src.llm.model_presets import PRESETS

def resolve_preset_from_model_provider(provider: str, model: str) -> str | None:
    """Find a matching preset name for a given provider and model."""
    for p_name, p_info in PRESETS.items():
        if p_info["provider"] == provider and p_info["model"] == (model or ""):
            return p_name
    return None
