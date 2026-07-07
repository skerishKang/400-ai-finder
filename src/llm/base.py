"""Base provider abstraction for the 400-ai-finder LLM system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResult:
    """Standard result format for all LLM providers."""
    ok: bool
    provider: str
    model: str
    content: str
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    # Sanitized, closed-vocabulary failure classification. Empty string on
    # success. Never contains raw exception text, URLs, API keys, headers, or
    # upstream response bodies. See the closed vocabulary in
    # ``OpenAICompatibleProvider`` and ``bukgu_mvp_router``.
    failure_code: str = ""


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
        timeout: int = 60,
    ) -> ProviderResult:
        """Send a chat completion request and return the result.

        Args:
            messages: List of {"role": "system"|"user"|"assistant", "content": "..."}
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in the response
            timeout: Request timeout in seconds

        Returns:
            ProviderResult with ok=True on success, ok=False on failure.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier string."""
        ...
