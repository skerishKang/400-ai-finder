"""Model preset registry and resolver for model-first selection.

Defines default preset combinations (DeepSeek -> MiMo -> Step) and
allows resolving model/provider/preset selections.
"""

from __future__ import annotations

import os
from typing import Any

# Recommended preset order: 1. DeepSeek, 2. MiMo, 3. Step
PRESETS: dict[str, dict[str, Any]] = {
    "deepseek-primary": {
        "name": "deepseek-primary",
        "description": "DeepSeek Primary Preset (1순위)",
        "model": "deepseek-v4-flash",
        "provider": "opencode-go",
        "recommended_order": 1,
    },
    "mimo-primary": {
        "name": "mimo-primary",
        "description": "MiMo Primary Preset (2순위)",
        "model": "mimo-v2.5-pro",
        "provider": "opengateway",
        "recommended_order": 2,
    },
    "step-primary": {
        "name": "step-primary",
        "description": "Step Primary Preset (3순위)",
        "model": "stepfun-ai/step-3.5-flash",
        "provider": "nvidia",
        "recommended_order": 3,
    },
}

PROVIDER_MODELS: dict[str, list[str]] = {
    "kilocode": [
        "deepseek/deepseek-v4-flash:free",
        "moonshotai/kimi-k2.6:free",
        "stepfun/step-3.5-flash:free",
        "poolside/laguna-m.1:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "poolside/laguna-xs.2:free",
    ],
    "nvidia": [
        "stepfun-ai/step-3.5-flash",
        "stepfun-ai/step-3.7-flash",
        "openai/gpt-oss-120b",
        "nvidia/nemotron-3-super-120b-a12b",
        "minimaxai/minimax-m2.7",
        "minimaxai/minimax-m2.5",
    ],
    "opengateway": [
        "mimo-v2.5-pro",
    ],
    "opencode-go": [
        "deepseek-v4-flash",
    ],
    "opencode-zen": [
        "deepseek-v4-flash-free",
        "minimax-m2.5-free",
        "nemotron-3-super-free",
        "qwen3.6-plus-free",
    ],
    "nous": [
        "deepseek/deepseek-v4-flash:free",
    ],
    "mistral": [
        "mistral-medium-3.5",
        "devstral-small",
    ],
    "groq": [
        "openai/gpt-oss-120b",
    ],
    "mock": [
        "mock",
    ],
    "stub": [
        "stub",
    ]
}

def list_model_presets() -> list[dict[str, Any]]:
    """Return a list of all model presets sorted by recommended order."""
    return sorted(PRESETS.values(), key=lambda x: x["recommended_order"])

def get_model_preset(name: str) -> dict[str, Any] | None:
    """Get preset details by name."""
    return PRESETS.get(name)

def list_models_for_provider(provider: str) -> list[str]:
    """List recommended models for a specific provider."""
    return PROVIDER_MODELS.get(provider.lower().strip(), [])

def resolve_provider_model(
    model: str | None = None,
    provider: str | None = None,
    preset: str | None = None,
) -> tuple[str, str]:
    """Resolve model, provider, and preset into a final (provider, model) combination.

    If the resolved provider is pending/not fully configured, raises ValueError.
    """
    # 1. Resolve from preset first
    if preset:
        p_info = get_model_preset(preset)
        if not p_info:
            raise ValueError(f"Unknown preset: '{preset}'")
        provider = p_info["provider"]
        model = p_info["model"]

    # 2. Resolve from model-first if model is provided but provider is missing or mock
    if model and (provider is None or provider == "mock"):
        found = False
        # Look in presets first
        for p_info in list_model_presets():
            if p_info["model"] == model:
                provider = p_info["provider"]
                found = True
                break
        if not found:
            # Look in PROVIDER_MODELS
            for prov, models in PROVIDER_MODELS.items():
                if model in models:
                    provider = prov
                    found = True
                    break

    # 3. Fallbacks
    final_provider = (provider or "mock").strip().lower()
    final_model = (model or "").strip()

    # 4. Check for pending providers
    pending_providers = ["opencode-go", "opencode-zen", "nous"]
    if final_provider in pending_providers:
        # Check environment variables
        env_prefix = final_provider.upper().replace("-", "_")
        has_base_url = bool(
            os.environ.get(f"AI_FINDER_{env_prefix}_BASE_URL")
            or os.environ.get(f"{env_prefix}_BASE_URL")
        )
        has_api_key = bool(
            os.environ.get(f"AI_FINDER_{env_prefix}_API_KEY")
            or os.environ.get(f"{env_prefix}_API_KEY")
            or (final_provider == "opencode-go" and os.environ.get("OPENCODE_API_KEY"))
        )
        if not (has_base_url and has_api_key):
            raise ValueError(
                f"Provider '{final_provider}' is pending configuration. "
                f"Missing environment variables: AI_FINDER_{env_prefix}_BASE_URL and/or API key."
            )

    return final_provider, final_model
