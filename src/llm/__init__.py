"""LLM provider abstraction layer with registry and factory.

Built-in providers include:

  Provider              Description
  ─────────────────────────────────────────────────────────────
  mock                  Fixed response for testing
  openai_compatible     Generic OpenAI-compatible API provider
  mistral               Mistral AI (api.mistral.ai/v1)
  opengateway           OpenGateway / OpenCodeGo gateway
  kilocode              KiloCode (api.kilo.ai/api/gateway)
  nvidia                NVIDIA (integrate.api.nvidia.com/v1)
  groq                  Groq (api.groq.com/openai/v1)

To add a new built-in provider, add an entry to ``BUILTIN_PROVIDERS``.
"""

from __future__ import annotations

import os
from typing import Any

from .base import LLMProvider, ProviderResult
from .mock_provider import MockProvider
from .stub_provider import StubProvider
from .openai_compatible_provider import OpenAICompatibleProvider

# ------------------------------------------------------------------
# Built-in provider definitions
# Each entry maps a provider name → config dict.
# Config keys:
#   default_model : fallback model if not overridden by env
#   env_prefix    : prefix for env-var override of provider-specific settings
#   env_base_url  : env var name for base URL override
#   env_api_key   : env var name for API key
#   env_model     : env var name for model override
#   base_url      : default base URL (hard-coded)
#   api_key       : default API key (fallback, usually empty — read from env)
#   model         : default model name
# ------------------------------------------------------------------

BUILTIN_PROVIDERS: dict[str, dict[str, Any]] = {
    "openai_compatible": {
        "description": "Generic OpenAI-compatible provider",
        "default_model": "gpt-4o-mini",
        "env_prefix": "AI_FINDER_LLM",
    },
    "mistral": {
        "description": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "env_api_key": "MISTRAL_API_KEY",
        "default_model": "mistral-medium-3.5",
    },
    "opengateway": {
        "description": "OpenGateway / OpenCodeGo Gateway",
        "base_url": "https://opengateway.gitlawb.com/v1",
        "env_api_key": "OPENGATEWAY_API_KEY",
        "default_model": "mimo-v2.5-pro",
    },
    "kilocode": {
        "description": "KiloCode",
        "base_url": "https://api.kilo.ai/api/gateway",
        "env_api_key": "KILOCODE_API_KEY",
        "default_model": "deepseek/deepseek-v4-flash:free",
    },
    "nvidia": {
        "description": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "env_api_key": "NVIDIA_API_KEY",
        "default_model": "openai/gpt-oss-120b",
    },
    "groq": {
        "description": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "env_api_key": "GROQ_API_KEY",
        "default_model": "gpt-oss-120b",
    },
}


# ------------------------------------------------------------------
# Provider URL model mapping for OpenGateway / OpenCodeGo
# These are well-known models available through the gateway.
# ------------------------------------------------------------------

OPENGATEWAY_MODELS = {
    "mimo-v2.5-pro": "Mimo v2.5 Pro",
    "mimo-v2.5-max": "Mimo v2.5 Max",
}

KILOCODE_MODELS = {
    "x-ai/grok-code-fast-1:optimized:free": "Grok Code Fast",
    "deepseek/deepseek-v4-flash:free": "DeepSeek V4 Flash",
    "poolside/laguna-m.1:free": "Poolside Laguna M.1",
    "poolside/laguna-xs.2:free": "Poolside Laguna XS.2",
    "inclusionai/ring-2.6-1t:free": "InclusionAI Ring 2.6",
    "nvidia/nemotron-3-super-120b-a12b:free": "Nemotron Super 120B",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free": "Nemotron Nano 30B",
    "baidu/cobuddy:free": "Baidu CoBuddy",
    "stepfun/step-3.5-flash:free": "StepFun Step 3.5 Flash",
    "arcee-ai/trinity-large-thinking:free": "Arcee Trinity Large",
    "openrouter/free": "OpenRouter Free",
    "openrouter/owl-alpha": "OpenRouter Owl Alpha",
}

NVIDIA_MODELS = {
    "stepfun-ai/step-3.5-flash": "StepFun Step 3.5 Flash",
    "openai/gpt-oss-120b": "GPT-OSS 120B",
    "minimaxai/minimax-m2.7": "MiniMax M2.7",
    "minimaxai/minimax-m2.5": "MiniMax M2.5",
    "deepseek-ai/deepseek-v4-flash": "DeepSeek V4 Flash",
    "deepseek-ai/deepseek-v4-pro": "DeepSeek V4 Pro",
    "nvidia/nemotron-3-super-120b-a12b": "Nemotron Super 120B",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning": "Nemotron Nano 30B",
}

GROQ_MODELS = {
    "gpt-oss-120b": "GPT-OSS 120B",
    "llama3-70b-8192": "Llama 3 70B",
    "llama3-8b-8192": "Llama 3 8B",
    "gemma2-9b-it": "Gemma 2 9B",
    "mixtral-8x7b-32768": "Mixtral 8x7B",
}


# ------------------------------------------------------------------
# Provider factory
# ------------------------------------------------------------------

def get_provider(provider_name: str | None = None, **overrides: Any) -> LLMProvider:
    """Resolve a provider name to an LLMProvider instance.

    Resolution order:
      1. ``provider_name`` argument
      2. ``AI_FINDER_LLM_PROVIDER`` env var
      3. Fallback to ``mock``

    Args:
        provider_name: One of the keys in ``BUILTIN_PROVIDERS``, or ``"mock"``.
        **overrides: Per-provider keyword arguments passed to the constructor.
                     Common overrides include ``base_url``, ``api_key``, ``model``.

    Returns:
        A configured LLMProvider instance.

    Raises:
        ValueError: If the provider name is unknown.
    """
    name = provider_name or os.environ.get("AI_FINDER_LLM_PROVIDER", "mock")
    name = name.strip().lower()

    # --- Mock is a standalone implementation ---
    if name == "mock":
        return MockProvider(
            response=overrides.get("response") or overrides.get("mock_response"),
        )

    # --- Stub is a standalone implementation (test-only) ---
    if name == "stub":
        return StubProvider(
            fail_on=overrides.get("fail_on"),
        )

    # --- Built-in providers ---
    if name in BUILTIN_PROVIDERS:
        return _build_provider(name, **overrides)

    raise ValueError(
        f"Unknown LLM provider: '{name}'. "
        f"Available providers: mock, stub, {', '.join(sorted(BUILTIN_PROVIDERS))}. "
        f"Set AI_FINDER_LLM_PROVIDER env var or pass provider= to get_provider()."
    )


def list_providers() -> list[dict[str, Any]]:
    """Return a list of all available providers with metadata."""
    result = []
    for name, cfg in BUILTIN_PROVIDERS.items():
        env_api_key = cfg.get("env_api_key", f"{cfg.get('env_prefix', 'AI_FINDER_LLM')}_API_KEY")
        has_key = bool(os.environ.get(env_api_key))
        result.append({
            "name": name,
            "description": cfg.get("description", ""),
            "default_model": cfg.get("default_model", ""),
            "base_url": cfg.get("base_url", "(env: see config)"),
            "has_api_key": has_key,
        })
    # Add mock at the top
    result.insert(0, {
        "name": "mock",
        "description": "Fixed response for testing (no API key required)",
        "default_model": "mock",
        "base_url": "",
        "has_api_key": True,
    })
    # Add stub (test-only, no API key required)
    result.insert(1, {
        "name": "stub",
        "description": "Simulated grounded answer for testing (no API key required)",
        "default_model": "stub",
        "base_url": "",
        "has_api_key": True,
    })
    return result


def _build_provider(name: str, **overrides: Any) -> LLMProvider:
    """Build an OpenAICompatibleProvider from a built-in provider config."""
    cfg = BUILTIN_PROVIDERS[name]

    # Determine each setting: override > env > cfg default
    base_url = (
        overrides.get("base_url")
        or os.environ.get(f"AI_FINDER_{name.upper()}_BASE_URL")
        or os.environ.get(f"{name.upper()}_BASE_URL")
        or cfg.get("base_url", "")
    )

    env_api_key = cfg.get("env_api_key", f"{name.upper()}_API_KEY")
    api_key = (
        overrides.get("api_key")
        or os.environ.get(f"AI_FINDER_{name.upper()}_API_KEY")
        or os.environ.get(env_api_key)
        or ""
    )

    default_model = cfg.get("default_model", "")
    model = (
        overrides.get("model")
        or os.environ.get(f"AI_FINDER_{name.upper()}_MODEL")
        or os.environ.get(f"{name.upper()}_MODEL")
        or default_model
    )

    timeout = overrides.get("timeout") or _int_env("AI_FINDER_LLM_TIMEOUT", 60)
    temperature = overrides.get("temperature") or _float_env("AI_FINDER_LLM_TEMPERATURE", 0.2)
    max_tokens = overrides.get("max_tokens") or _int_env("AI_FINDER_LLM_MAX_TOKENS", 1200)

    return OpenAICompatibleProvider(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout=timeout,
        temperature=temperature,
        max_tokens=max_tokens,
        provider_label=name,
        model_label=model or default_model or "unknown",
    )


def _int_env(key: str, default: int) -> int:
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _float_env(key: str, default: float) -> float:
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


__all__ = [
    "LLMProvider",
    "ProviderResult",
    "MockProvider",
    "StubProvider",
    "OpenAICompatibleProvider",
    "get_provider",
    "list_providers",
    "BUILTIN_PROVIDERS",
]
