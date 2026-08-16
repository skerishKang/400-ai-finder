"""Fetch provider abstraction layer — registry and factory.

Built-in providers:
    mock         Fixed response for testing
    requests     Standard HTTP GET via requests + BeautifulSoup
    firecrawl    Firecrawl API (/v1/scrape)
"""

from __future__ import annotations

import os
from typing import Any

from .base import FetchConfig, FetchProvider, FetchResult
from .mock_provider import MockFetchProvider
from .requests_provider import RequestsFetchProvider
from .firecrawl_provider import FirecrawlFetchProvider
from .egress_policy import (
    FULL_REBINDING_PREVENTION,
    EgressPolicy,
    PublicEgressPolicy,
    default_dns_resolver,
    is_safe_public_ip,
    is_valid_firecrawl_service_endpoint,
)


_BUILTIN_FETCH_PROVIDERS = {
    "mock",
    "requests",
    "firecrawl",
}


def get_fetch_provider(
    name: str | None = None, **overrides: Any
) -> FetchProvider:
    """Resolve a fetch provider name to a FetchProvider instance.

    Resolution order:
      1. ``name`` argument
      2. ``AI_FINDER_FETCH_PROVIDER`` env var
      3. Fallback to ``requests``

    Args:
        name: One of: mock, requests, firecrawl
        **overrides: Provider-specific keyword arguments
                     (api_key, base_url, timeout, egress_policy, etc.)

    Returns:
        A configured FetchProvider instance.

    Raises:
        ValueError: If the provider name is unknown.
    """
    provider_name = name or os.environ.get("AI_FINDER_FETCH_PROVIDER", "requests")
    provider_name = provider_name.strip().lower()

    if provider_name == "mock":
        return MockFetchProvider(
            markdown=overrides.get("mock_markdown"),
            html=overrides.get("mock_html"),
            title=overrides.get("mock_title"),
        )

    if provider_name == "requests":
        timeout = overrides.get("timeout", overrides.get("requests_timeout"))
        return RequestsFetchProvider(
            timeout=timeout if timeout is not None else 15,
            user_agent=overrides.get("user_agent"),
            egress_policy=overrides.get("egress_policy"),
        )

    if provider_name == "firecrawl":
        return FirecrawlFetchProvider(
            api_key=overrides.get("api_key"),
            base_url=overrides.get("base_url"),
            timeout=overrides.get("timeout", overrides.get("firecrawl_timeout")),
            egress_policy=overrides.get("egress_policy"),
            allow_test_endpoint=overrides.get("allow_test_endpoint", False),
        )

    raise ValueError(
        f"Unknown fetch provider: '{provider_name}'. "
        f"Available providers: {', '.join(sorted(_BUILTIN_FETCH_PROVIDERS))}. "
        f"Set AI_FINDER_FETCH_PROVIDER env var or pass provider= to get_fetch_provider()."
    )


def list_fetch_providers() -> list[dict[str, Any]]:
    """Return metadata about all available fetch providers."""
    providers = []
    for name in sorted(_BUILTIN_FETCH_PROVIDERS):
        has_key = True
        if name == "firecrawl":
            has_key = bool(os.environ.get("FIRECRAWL_API_KEY"))
        providers.append({
            "name": name,
            "has_api_key": has_key,
        })
    return providers


__all__ = [
    "FetchProvider",
    "FetchConfig",
    "FetchResult",
    "MockFetchProvider",
    "RequestsFetchProvider",
    "FirecrawlFetchProvider",
    "PublicEgressPolicy",
    "EgressPolicy",
    "default_dns_resolver",
    "is_safe_public_ip",
    "is_valid_firecrawl_service_endpoint",
    "FULL_REBINDING_PREVENTION",
    "get_fetch_provider",
    "list_fetch_providers",
]
