"""OpenAI-compatible provider for any chat completions API.

Supports any provider that exposes an OpenAI-compatible /chat/completions endpoint.
Works with: OpenAI, Mistral, OpenGateway (OpenCodeGo), KiloCode, NVIDIA, Groq, etc.
"""

from __future__ import annotations

import json
import os
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

from .base import LLMProvider, ProviderResult


class OpenAICompatibleProvider(LLMProvider):
    """Generic provider for OpenAI-compatible chat completion APIs.

    Configuration (in priority order: constructor arg > env var > default):

        base_url:   Base URL of the API (e.g. https://api.openai.com/v1)
        api_key:   API key for authentication
        model:     Model identifier string
        timeout:   Request timeout in seconds (default: 60)
        temperature: Sampling temperature (default: 0.2)
        max_tokens: Max tokens in response (default: 1200)
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provider_label: str | None = None,
        model_label: str | None = None,
    ):
        if requests is None:
            raise ImportError(
                "The 'requests' library is required for OpenAICompatibleProvider. "
                "Install it with: pip install requests"
            )

        self._base_url = (
            base_url
            or os.environ.get("AI_FINDER_LLM_BASE_URL")
            or ""
        )
        self._api_key = (
            api_key
            or os.environ.get("AI_FINDER_LLM_API_KEY")
            or ""
        )
        self._model = (
            model
            or os.environ.get("AI_FINDER_LLM_MODEL")
            or ""
        )
        self._timeout = (
            timeout
            or _int_env("AI_FINDER_LLM_TIMEOUT", 60)
        )
        self._temperature = (
            temperature
            or _float_env("AI_FINDER_LLM_TEMPERATURE", 0.2)
        )
        self._max_tokens = (
            max_tokens
            or _int_env("AI_FINDER_LLM_MAX_TOKENS", 1200)
        )
        self._provider_label = provider_label or "openai_compatible"
        self._model_label = model_label or self._model or "unknown"

    def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int | None = None,
    ) -> ProviderResult:
        """Send a chat completion request to the OpenAI-compatible endpoint."""

        # --- Validate configuration before making any network call ---
        if not self._base_url:
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error="LLM base URL is not configured. "
                      "Set AI_FINDER_LLM_BASE_URL or pass base_url to the provider.",
            )
        if not self._api_key:
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error="LLM API key is not configured. "
                      "Set AI_FINDER_LLM_API_KEY or pass api_key to the provider.",
            )
        if not self._model:
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error="LLM model is not configured. "
                      "Set AI_FINDER_LLM_MODEL or pass model to the provider.",
            )

        # --- Build request ---
        endpoint = self._build_endpoint()
        body = self._build_request_body(messages, temperature, max_tokens)
        headers = self._build_headers()
        req_timeout = timeout if timeout is not None else self._timeout

        try:
            resp = requests.post(
                endpoint,
                headers=headers,
                json=body,
                timeout=req_timeout,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except requests.exceptions.Timeout:
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error=f"LLM request timed out after {req_timeout}s. "
                      "Try increasing AI_FINDER_LLM_TIMEOUT.",
            )
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error=f"LLM API returned HTTP {status}. "
                      "Check your API key and endpoint URL.",
                raw={"http_status": status},
            )
        except requests.exceptions.RequestException as e:
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error=f"LLM request failed: {e}",
            )
        except json.JSONDecodeError:
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error="LLM returned invalid JSON response.",
            )

        # --- Parse response ---
        return self._parse_response(data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_endpoint(self) -> str:
        base = self._base_url.rstrip("/")
        return f"{base}/chat/completions"

    def _build_request_body(
        self,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        return {
            "model": self._model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
        }

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _parse_response(self, data: dict[str, Any]) -> ProviderResult:
        try:
            choices = data.get("choices", [])
            if not choices:
                return ProviderResult(
                    ok=False,
                    provider=self._provider_label,
                    model=self._model_label,
                    content="",
                    error="LLM response has no choices.",
                    raw=data,
                )
            content = choices[0].get("message", {}).get("content", "")
            if not content:
                return ProviderResult(
                    ok=False,
                    provider=self._provider_label,
                    model=self._model_label,
                    content="",
                    error="LLM response has empty content in choices[0].message.",
                    raw=data,
                )
            return ProviderResult(
                ok=True,
                provider=self._provider_label,
                model=self._model_label,
                content=content,
                raw=data,
            )
        except (KeyError, IndexError, TypeError) as e:
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error=f"Unexpected LLM response structure: {e}",
                raw=data,
            )

    @property
    def provider_name(self) -> str:
        return self._provider_label

    @property
    def model_name(self) -> str:
        return self._model_label


# ------------------------------------------------------------------
# Utility helpers
# ------------------------------------------------------------------

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
