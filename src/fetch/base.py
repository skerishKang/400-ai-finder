"""Base fetch provider abstraction for the 400-ai-finder system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import math
from typing import Any


@dataclass
class FetchResult:
    """Standard result format for all fetch providers."""
    url: str
    ok: bool
    provider: str
    fetched_at: str
    status_code: int | str = ""
    content_type: str = ""
    markdown: str = ""
    html: str = ""
    text: str = ""
    title: str = ""
    description: str = ""
    links: list[dict[str, str]] = field(default_factory=list)
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FetchConfig:
    timeout: float = 15.0
    max_retries: int = 0
    retry_backoff: float = 0.0
    retry_on_status: tuple[int, ...] = (408, 429, 500, 502, 503, 504)

    def __post_init__(self) -> None:
        if isinstance(self.timeout, bool):
            raise TypeError("timeout must be an int or float, not bool")
        if not isinstance(self.timeout, (int, float)):
            raise TypeError("timeout must be an int or float")
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("timeout must be > 0")

        if isinstance(self.max_retries, bool):
            raise TypeError("max_retries must be an int, not bool")
        if not isinstance(self.max_retries, int):
            raise TypeError("max_retries must be an int")
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")

        if isinstance(self.retry_backoff, bool):
            raise TypeError("retry_backoff must be an int or float, not bool")
        if not isinstance(self.retry_backoff, (int, float)):
            raise TypeError("retry_backoff must be an int or float")
        if not math.isfinite(self.retry_backoff) or self.retry_backoff < 0:
            raise ValueError("retry_backoff must be >= 0")

        if not isinstance(self.retry_on_status, tuple):
            raise TypeError("retry_on_status must be a tuple of ints")
        for status_code in self.retry_on_status:
            if isinstance(status_code, bool):
                raise TypeError("retry_on_status must contain ints only")
            if not isinstance(status_code, int):
                raise TypeError("retry_on_status must contain ints only")
            if status_code < 100 or status_code > 599:
                raise ValueError("retry_on_status values must be between 100 and 599")


class FetchProvider(ABC):
    """Abstract base class for all fetch providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier string."""
        ...

    @abstractmethod
    def fetch(self, url: str, **kwargs: Any) -> FetchResult:
        """Fetch a URL and return the result.

        Args:
            url: The URL to fetch.
            **kwargs: Provider-specific options (timeout, formats, etc.).

        Returns:
            FetchResult with ok=True on success, ok=False on failure.
        """
        ...
