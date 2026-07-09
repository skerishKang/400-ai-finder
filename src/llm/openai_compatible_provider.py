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


# ------------------------------------------------------------------
# Closed-vocabulary failure classification
# ------------------------------------------------------------------
# Every failure path maps to exactly one of these sanitized codes. None of
# these values ever contain raw exception text, URLs, API keys, authorization
# headers, or upstream response bodies. The operator-facing endpoint only ever
# surfaces these fixed strings (never the ``error`` text).
FAILURE_CONFIGURATION = "configuration"
FAILURE_TIMEOUT = "timeout"
FAILURE_AUTH_OR_PERMISSION = "auth_or_permission"
FAILURE_RATE_LIMITED = "rate_limited"
FAILURE_UPSTREAM_4XX = "upstream_4xx"
FAILURE_UPSTREAM_5XX = "upstream_5xx"
FAILURE_TRANSPORT_ERROR = "transport_error"
FAILURE_INVALID_UPSTREAM_RESPONSE = "invalid_upstream_response"
FAILURE_INVALID_MVP_DECISION = "invalid_mvp_decision"
FAILURE_PROVIDER_EXCEPTION = "provider_exception"
FAILURE_UNKNOWN = "unknown"

_FAILURE_VOCABULARY = frozenset({
    FAILURE_CONFIGURATION,
    FAILURE_TIMEOUT,
    FAILURE_AUTH_OR_PERMISSION,
    FAILURE_RATE_LIMITED,
    FAILURE_UPSTREAM_4XX,
    FAILURE_UPSTREAM_5XX,
    FAILURE_TRANSPORT_ERROR,
    FAILURE_INVALID_UPSTREAM_RESPONSE,
    FAILURE_INVALID_MVP_DECISION,
    FAILURE_PROVIDER_EXCEPTION,
    FAILURE_UNKNOWN,
})


def is_valid_failure_code(code: str) -> bool:
    """Return True if ``code`` is part of the closed failure vocabulary."""
    return code in _FAILURE_VOCABULARY


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
                error="LLM base URL is not configured.",
                failure_code=FAILURE_CONFIGURATION,
            )
        if not self._api_key:
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error="LLM API key is not configured.",
                failure_code=FAILURE_CONFIGURATION,
            )
        if not self._model:
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error="LLM model is not configured.",
                failure_code=FAILURE_CONFIGURATION,
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
                error="LLM request timed out.",
                failure_code=FAILURE_TIMEOUT,
            )
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            try:
                status_int = int(status)
            except (TypeError, ValueError):
                status_int = None
            if status_int == 401 or status_int == 403:
                code = FAILURE_AUTH_OR_PERMISSION
            elif status_int == 429:
                code = FAILURE_RATE_LIMITED
            elif status_int is not None and 500 <= status_int <= 599:
                code = FAILURE_UPSTREAM_5XX
            else:
                code = FAILURE_UPSTREAM_4XX
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error="LLM API returned an HTTP error.",
                failure_code=code,
                raw={"http_status": status},
            )
        except requests.exceptions.RequestException:
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error="LLM request could not be completed.",
                failure_code=FAILURE_TRANSPORT_ERROR,
            )
        except (json.JSONDecodeError, ValueError):
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error="LLM returned an unparseable response.",
                failure_code=FAILURE_INVALID_UPSTREAM_RESPONSE,
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
            # Guard against non-dict top-level payloads (e.g. a JSON list or
            # scalar). These are malformed upstream responses, not provider
            # runtime errors — never map them to provider_exception.
            if not isinstance(data, dict):
                return ProviderResult(
                    ok=False,
                    provider=self._provider_label,
                    model=self._model_label,
                    content="",
                    error="LLM response is not a JSON object.",
                    failure_code=FAILURE_INVALID_UPSTREAM_RESPONSE,
                )
            choices = data.get("choices", [])
            if not choices:
                return ProviderResult(
                    ok=False,
                    provider=self._provider_label,
                    model=self._model_label,
                    content="",
                    error="LLM response has no choices.",
                    failure_code=FAILURE_INVALID_UPSTREAM_RESPONSE,
                )
            content = choices[0].get("message", {}).get("content") or ""
            if not content:
                return ProviderResult(
                    ok=False,
                    provider=self._provider_label,
                    model=self._model_label,
                    content="",
                    error="LLM response content is empty or null (reasoning model may have exhausted token budget).",
                    failure_code=FAILURE_INVALID_UPSTREAM_RESPONSE,
                )
            return ProviderResult(
                ok=True,
                provider=self._provider_label,
                model=self._model_label,
                content=content,
            )
        except (KeyError, IndexError, TypeError, AttributeError):
            # Any unexpected structure error (including AttributeError from a
            # malformed payload) is a sanitizable upstream-response failure,
            # never a provider_exception that could carry raw context.
            return ProviderResult(
                ok=False,
                provider=self._provider_label,
                model=self._model_label,
                content="",
                error="LLM response has an unexpected structure.",
                failure_code=FAILURE_INVALID_UPSTREAM_RESPONSE,
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
