"""Base fetch provider abstraction for the 400-ai-finder system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
